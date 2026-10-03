# mneme-cf-bundle/v1 — Counterfactual Bundle Verification Spec

Normative document for a **clean-room implementation** of the
counterfactual bundle verifier, incorporated by reference into
`../SPEC.md` (the normative root — custody, replay, ranking,
canonicalization are defined there and not restated here). A
conforming implementation reads a signed bundle and independently
derives the causal result — it does not consume the claimed result
as input.

Nothing here requires the producing codebase. The producer is
`seasons/` + `mneme/`; the reference verifier is
`product/verify_cf_offline.py`. This document is the contract
between them. The conformance corpus it answers to lives in
`../conformance/cf/v1/`; the generator is deterministic — the clock
does not participate.

## 1. Trust model

Hostile: the bundle, its report, its propagation graph, all declared
hashes, `keyid`, JSON ordering, timestamps, embeddings, all
counterfactual fields.

Trusted: the verifier code, its protocol-version table, and an
out-of-band Ed25519 trust set (`trusted_keys.json`).

Verdicts are two-mode:

- `VERIFIED_AUTHENTICATED` — DSSE signature verifies under a trusted
  key AND all semantic checks pass.
- `VERIFIED_INTEGRITY_AND_SEMANTICS — ORIGIN_UNTRUSTED` — all semantic
  checks pass but no trusted signature exists. A well-formed forgery
  can reach this verdict; it must never be printed as merely
  "VERIFIED".

## 2. Canonicalization — mneme-canonical-json/v1

All hashed bytes are produced by ONE canonicalizer:

- Top level MUST be a JSON object.
- Object keys sorted ascending (byte order), separators `","` and
  `":"` — no whitespace.
- `ensure_ascii=false`: non-ASCII content is literal UTF-8.
- Numbers in evidence are fixed-point **strings** at scale 10
  (`"0.7812500000"`). JSON floats are forbidden anywhere in hashed
  content. `true`/`false`/`null`/`int`/strings/arrays/objects are
  permitted.
- Stored `payload_json` MUST byte-equal `canonical(parse(payload_json))`.
- Duplicate object names MUST be rejected at parse time (RFC 8785's
  uniqueness rule applied to every layer, not just the envelope).

## 3. Custody chain integrity (custody_protocol 1.1.0)

For each chain, seqs are dense `0..N-1`. The genesis hash:

```
prev(0) = sha256("MNEME_CUSTODY_GENESIS:" + memory_id).hexdigest
```

Each event's hash recomputes from its canonical envelope:

```
envelope = {
  "memory_id":  string,
  "seq":        int,
  "event_type": string,
  "actor_id":   string,
  "reason":     string,
  "created_at": string,   # canonical UTC microseconds, "+00:00"
  "payload":    object    # parsed payload_json
}
entry_hash = sha256(ascii(prev_hash) + utf8(canonical(envelope)))
```

Verify: `prev_hash[i] == entry_hash[i-1]` AND
`entry_hash[i] == recomputed`. Linkage alone is not integrity — a
forged event with borrowed hashes must die here.

## 4. Replay state machine (replay_protocol 1.1.0)

Per chain, per as-of truncation (`created_at < as_of`), skipping dead
seqs — exact Fraction arithmetic:

```
status  = CLEAN
fstate  = NEUTRAL
conf    = 1/2

QUARANTINED      → status = QUARANTINED            (terminal)
SUPERSEDED_BY    → status = SUPERSEDED             (terminal)
TAINT_FLAGGED    → status = TAINT_FLAGGED if status == CLEAN
REHABILITATED    → status = CLEAN                  (from any non-terminal)
REINFORCED       → conf += (1/4)·(1−conf)
STATE_CHANGED    → if from==NEUTRAL and to==REINFORCED:
                       fstate = REINFORCED iff conf >= 3/4
                   else if "to" present: fstate = payload.to
```

`DECISION_USED_MEMORY`, `STORED`, `CONTRADICTED_BY` do not move state.

## 5. Recall (ranking_protocol 1.0.0)

Exact Fraction arithmetic over quantized vectors (components are
scale-10 fixed-point strings, parsed via exact Decimal→Fraction).

1. Servable = `custody_status == "CLEAN"`.
2. Candidates: servable and `field_state != "FORGOTTEN"`, parsed
   embedding with non-zero norm.
3. Seed: argmax of sign-aware squared similarity — `(1, d²/nv)` if
   `d>0` else `(0,0)`, where `d = q·v`, `nv = v·v`. Ties: memory_id ASC.
4. BFS from seed, depth ≤ `min(hops, 10)`, over links where BOTH
   endpoints are servable:
   - `INHIBITORY` edge → target silenced,
   - `RESONANT` edge → target joins frontier, +1/2 boost per in-edge,
   - others → target joins frontier.
   Frontier each level = next − visited − inhibited.
5. Score: inhibited candidates die unless `field_state == "REINFORCED"`
   (rescue) or they are the seed. `decay = (43/50)^hop` (`hop≥0`, else
   `1`); `m = STATE_BOOST[state]·decay + resonant_boost`;
   `t = d·m`; `rank = t²/nv` if `t>0` else `0`.
   `STATE_BOOST = {REINFORCED: 3/2, NEUTRAL: 1, FORGOTTEN: 0}`.
6. Sort `(-rank, memory_id ASC)`; served = first `top_k` memory_ids.

## 6. Intervention and cascade (cf-cascade/v1)

`intervention = {memory_id, seq}` excises exactly one event.
`dead = {(memory_id, seq)}` grows by cascade.

Precedence rule: a decision `d` at `t_d` is judged against each chain
truncated at `t_d` minus `dead` minus **its own consequences** —
identified structurally, never by timestamp:

- `DECISION_USED_MEMORY` whose payload `decision_id == d.id`;
- `REINFORCED` whose payload `caused_by_decision_id == d.id`, OR
  (legacy fallback only) the REINFORCED immediately following such a
  `DECISION_USED` when it carries no `caused_by_decision_id`.

For each decision with `created_at > t(excised)` in order
`(created_at, decision_id)`:

1. `served_cf = recall(world_at(t_d) minus dead minus own, query)`.
2. `fallen = sorted(used − served_cf)`. If empty: grounded, continue.
3. Else: receipt diverges, decision ungrounded; its endogenous
   consequences on every used chain die:
   - every `DECISION_USED_MEMORY` naming it;
   - every `REINFORCED` caused by it (explicit reference first,
     adjacency fallback for legacy events).
4. Propagation edge: `{decision_id, invalidated: [[mid, seq], ...]}`.

Divergent/ungrounded/invalidated lists preserve decision order;
`invalidated` within a decision follows `sorted(used)` chain order
and ascending seq within a chain. `counterfactual_states` is the
replay of every chain carrying dead events, over its FULL length.

## 7. Envelope and signature (DSSE + Ed25519)

```
payloadType = "application/vnd.mneme.cf-bundle+json;version=1"
payload     = base64(canonical_json(bundle))
signatures  = [{keyid, sig}]   # Ed25519 over PAE:
PAE = "DSSEv1" SP len(type) SP type SP len(payload_bytes) SP payload
```

`keyid` selects candidate keys only — it is a hint, never an
authentication decision. A signature verifies under ANY trusted key.

## 8. Check order (each must fail closed)

| ID | Check |
|---|---|
| CF-1 | DSSE envelope verifies under the trusted set — checked only when a trusted set is provided; an absent trust set yields `ORIGIN_UNTRUSTED`, never a false reject and never silent trust |
| CF0 | `bundle_sha256` recomputes over canonical bytes |
| CF0.5 | every declared semantics version is implemented; unknown → reject |
| CF1 | dense seqs + `prev_hash` linkage + `entry_hash` recomputation + stored payload canonicality |
| CF1.5 | `query_embedding_sha256` recomputes AND equals `receipt.query_sha256` (the historical commitment made at recall time) |
| CF2 | every decision-cited receipt's `served` recomputes from the evidence at `t_d` — the "actual world" must not be theatre |
| CF3 | divergent receipts, ungrounded decisions, invalidated set, propagation edges, cf states, and `report_sha256` all recompute |

## 9. Conformance

`golden/` holds a signed bundle, the test trust key, and the expected
verdict. A conforming verifier prints `VERIFIED_AUTHENTICATED` on
`golden_bundle.dsse.json` under `trusted_keys.json`, and REJECTS each
corpus mutant. `expected_verdict.json` records the recomputed
counters for cross-implementation comparison.
