# Technical README — Remember the Seasons

Deep architecture, protocol contracts, invariants, determinism scope,
and the honest list of what this system does not guarantee. Audience:
the reader auditing or extending the product layer (`product/`).

## 1. Architecture

Three decoupled layers, each independently inspectable:

```
┌─ operational state ──────────────────────────────────────────┐
│  field.py — adaptive memory: confidence, promotion (STATE_    │
│  CHANGED at 3/4), taint propagation, RESONANT links, recall   │
│  ranking (similarity + field_state + confidence, quantized    │
│  embedding + deterministic weights)                           │
├─ forensic trajectory ────────────────────────────────────────┤
│  custody.py — per-memory hash-linked chains (genesis hash,    │
│  seq-dense, prev_hash linked, closed event vocabulary)        │
│  authority.py — per-actor ledger: capability grants,          │
│  quarantine as write barrier                                  │
│  receipts/claims/decisions — every recall sealed, every       │
│  decision records declared + corroborated use                 │
├─ counterfactual replay ──────────────────────────────────────┤
│  trajectory.py — do(T_i=∅): excise one custody event,         │
│  recompute the counterfactual world, run production recall    │
│  inside a SAVEPOINT, rollback, return a sealed delta report   │
└──────────────────────────────────────────────────────────────┘
```

The write path never lets the model touch state: `ask()` calls the
LLM, takes its declared `used` set, and only the *deterministically
corroborated* subset is reinforced. `served ≠ used ≠ reinforced` is
load-bearing — reinforcement is the payoff a memory-poisoning attack
wants, so it follows evidence, not narrative.

## 2. Causal ontology 2.0.0 (`cf-cascade/v2`)

Events declare antecedents in `payload.causes[]` (PROV-inspired):

```json
{"kind": "decision", "id": "dec-0002"}              causal antecedent
{"kind": "event", "memory_id": "mem-0000", "seq": 8} event antecedent
{"kind": "receipt", "id": "sha256…"}                informational grounding
```

Cascade rule — fixpoint over the declared graph, not over event type
or position:

```
Dead(n+1) = Dead(n) ∪ { e | ∃ c ∈ causes(e) : c references Dead(n) }
```

- Two node classes die: events `(memory_id, seq)` and decisions `id`
  (a decision dies when its evidence base recomputes as ungrounded —
  the semantic verdict decides, never position).
- Receipt causes are informational: grounding is recomputed, not
  propagated.
- Legacy evidence (no `causes[]`) keeps `caused_by_decision_id` as an
  implicit decision-cause, plus bounded adjacency — **only when both
  the DU and its neighbour are fully legacy**. With explicit causes,
  proximity never kills (the DISCORDIA fix: a clock is not a cause).
- Multi-hop works: `decision → REINFORCED@8 → STATE_CHANGED@9` — the
  promotion dies with its causing reinforcement.

Spec: `product/spec/causal-ontology-v2.md`. Frozen corpus:
`product/conformance/cf/v1/` (18 artifacts: 6 positives including a
true v1-form bundle, 12 mutants).

## 3. Protocol versions (closed vocabulary)

| protocol | current |
|---|---|
| bundle_protocol | mneme-cf-bundle/v1 |
| causal_rewind_protocol | cf-cascade/v2 |
| causal_ontology | 2.0.0 |
| canonicalization_protocol | mneme-cjson/1.0.0 |
| payload_type | …/cf-bundle+json;version=1 |
| signature_profile | dsse-ed25519-rfc8032/v1 |
| custody/replay | 1.1.0 (1.0.0 still supported for sealed bundles) |
| ranking | 1.0.0 · taint 2.0.0 · authority 1.3.0 · receipt 2.0.0 · claim 1.1.0 |

Unknown protocol names or versions are rejected — a verifier answers
only for versions it implemented and tested.

## 4. Cryptographic envelope and canonicalization

- **DSSE**: `{payload, payloadType, signatures[], keyid?}` — signature
  over `PAE(payloadType, payload_bytes)`; base64 std and urlsafe;
  extra envelope fields ignored; multi-sig: ≥1 trusted signature wins.
  With no trusted key set: integrity and semantics still verified,
  verdict `VERIFIED_ORIGIN_UNTRUSTED` (not rejection).
- **mneme-cjson/1.0.0**: deterministic canonical JSON — key-sorted,
  no floats anywhere in sealed paths (confidence is a `Fraction` with
  Decimal-scale-10 quantization), codepoint ordering. Deliberately
  *not* RFC 8785 JCS: differs in decimal handling and ordering;
  existing hashes depend on it.
- Strict JSON: duplicate keys rejected at parse.

## 5. Conformance discipline

- `product/conformance/cf/v1/generate.py` produces the whole corpus
  deterministically (fixed test-only signing seed);
  `--check` proves byte-for-byte regeneration.
- `differential.sh` builds the clean-room Go verifier in-tree and
  compares exit code + normalized verdict per artifact: **18/18 AGREE**
  covering signature variants, mutants (tampered events, dropped
  edges, phantom ungrounding, wrong seq, unknown protocol, missing
  payloadType, causes-stripped, transitivity-break, dup-keys), an
  unsigned bundle, multi-sig, and a legacy-v1-form bundle proving
  backward compatibility.
- CI (`.github/workflows/ci.yml`): python suite + `--check` +
  differential on every push/PR.

## 6. Stigmergy series — adversarial findings, in order

`product/tests/test_stigmergy_pure.py` — 16 checks. The point of the
series was falsification; three of its findings falsified something:

| step | attack | result |
|---|---|---|
| S2 | two agents, zero shared process state | survived — ids became
field state (`COUNT` at write time) |
| S3 | concurrent distinct-memory writes | **falsified** id allocation:
2/12 lost to UNIQUE races → bounded retry, 16/16 |
| S4 | concurrent same-chain writes | chain dense+linked; a serialized
neighbour is not a cause — both writer orders identical verdict |
| S5 | legality under serialization | **falsified** write path: an
illegal transition (REHAB from CLEAN) could seal |
| S6 | atomic legality | `append_legal_event` validates inside the
caller's transaction + `BEGIN IMMEDIATE`; stale transitions never
seal |
| S11 | both-legal non-commuting pair | **non-confluence, honestly**:
QUAR→SUP vs SUP→QUAR, both legal, different final states |
| S12 | 16 identical concurrent runs | 9 SUPERSEDED / 7 QUARANTINED —
`state = f(scheduler)` |
| S13 | can a verifier detect concurrency? | **no** — `prev_hash`
seals where the event landed, not the head the writer observed;
`observed_head` is not recorded. `E(W1)=E(W2), W1≠W2` |

## 7. Determinism and reproducibility

- No floats in sealed/decision paths; `Fraction` for ratios,
  Decimal scale-10 for confidence.
- Canonical encoder is the single serializer for anything hashed;
  stored `payload_json` bytes are byte-identical to hashed bytes.
- Corpus, demo (offline mode), and tests are seed-free or
  fixed-seed; `generate.py --check` is the drift proof.
- Scope limit: determinism is over *sealed artifacts and replay*, not
  over wall-clock `created_at` (recorded, never trusted semantically).

## 8. Trust boundaries and threat model

- The LLM has zero epistemic authority: it declares, the engine
  corroborates. A steered model can lie — the lie lands on the chain
  as evidence, not as state.
- The model cannot grant itself write capability (authority ledger
  gates STORE/REINFORCE/DECIDE per actor).
- Bundle verification is implementation-independent: the Go verifier
  never imports the producer.
- Untrusted-but-intact evidence is reported as such
  (`VERIFIED_ORIGIN_UNTRUSTED`), never silently promoted.
- Not covered: multi-process/multi-host partial order, byzantine
  actors, key management, the `observed_head` gap (S13) — see limits.

## 9. Honest limits and non-goals

- **Concurrency scope**: demonstrated under threads + SQLite + one
  host (WAL + busy_timeout). Multi-process/multi-host ordering is out
  of scope — no vector clocks, no CRDT, no merge rules.
- **Confluence is not a property**: unconditional transitions can
  legally diverge (S11/S12); last-write-wins is a documented
  consequence of serialization, not a semantic decision.
- **Evidence gap (S13)**: the sealed record cannot distinguish
  "B observed A then acted" from "B never saw A" — the observed head
  is not recorded. Deliberately unfixed: whether concurrency needs a
  verdict is a design question, and the experiment showed *why* the
  evidence would be needed, not which representation is right.
- **Scale**: recall scans the field; at ~10k notes it approaches
  seconds — an embedding index fixes it without protocol change.
- **Not built**: hosted demo, MCP deployment, real-time multi-agent
  sync, cryptographic actor identity beyond DSSE bundle signing.

## 10. Reproduce everything

```bash
cd product
python3 demo.py                              # offline, deterministic
NEBIUS_API_KEY=... python3 demo.py           # Nemotron + Qwen, live
for t in tests/test_*.py; do python3 "$t"; done
python3 conformance/cf/v1/generate.py --check
bash conformance/cf/v1/differential.sh
```

Specs: `product/spec/cf-bundle-v1.md`, `product/spec/causal-ontology-v2.md`,
`product/SPEC.md` (protocol governance, §11). Experiment narrative:
`docs/EXPERIMENTS.md`, `docs/HYPOTHESES.md`, `docs/STOP_CONDITIONS.md`.
