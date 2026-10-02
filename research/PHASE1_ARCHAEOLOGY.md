# Phase 1 — Archaeology: evidence-backed inventory of the three source systems

> Epistemic convention: **OBSERVED** = read directly from code/tests/docs in
> `sources/` (cited as `file:line`). **INFERRED** = derived but not directly
> stated. **PROPOSED** = our hypothesis, not yet tested. **UNKNOWN** = we lack
> evidence. No inference is silently promoted into a fact.
>
> Provenance: all citations point into `sources/<system>/`, which are snapshots
> of the canonical repos at the commits recorded in each `PROVENANCE.md`
> (raven-memory `56df6cf`, mneme `bde801a`, stigmergy `b80a7f9`).

---

## 0. Lineage (OBSERVED)

The three systems are not independent. They share an ancestor and a discipline.

- **raven-memory** is the origin of the "adaptive memory field" mechanics
  (ternary states, RESONANT/INHIBITORY links, BFS propagation, rescue rule,
  STDP, audit chain). OBSERVED in `sources/raven-memory/raven/memory_engine.py`.
- **MNEME** explicitly *inherits* raven's field mechanics and states they are
  "not the contribution"; its contribution is forensic verifiability.
  OBSERVED: `sources/mneme/ARCHITECTURE.md:39-42` ("The adaptive-field
  mechanics ... are inherited from raven-memory and are not the contribution").
- **STIGMERGY** ports MNEME's per-memory `custody_chain` and reuses raven's
  state/link vocabulary, but adds multi-agent stigmergic coordination.
  OBSERVED: `sources/stigmergy/ARCHITECTURE.md:82` ("`custody_chain` ...
  Ported from MNEME"); `sources/stigmergy/ARCHITECTURE.md:76-78` (state/tier).

All three enforce "LLM out of the decision path" with a deterministic core.
All three keep tamper-evident hash chains. All three refuse deletion (forgetting
/ quarantine / orphaning are states, not row removal).

---

## 1. raven-memory — adaptive memory field + causal probes

### 1.1 Mechanism inventory

| Mechanism | Location (OBSERVED) | Property claimed | Deterministic? | State required | I/O |
|---|---|---|---|---|---|
| KDTree seed + BFS hop expansion | `memory_engine.py:1466` `_rebuild_kdtree`, recall path | query lands on nearest active cell, propagates through k-NN graph (K=6) + explicit links for N hops | deterministic given embeddings | in-memory KDTree + `_active_cells` set + SQLite | embedding→ranked memories |
| Ternary memory states | `memory_engine.py` constants; README §states | REINFORCED ×1.5, NEUTRAL ×1.0, FORGOTTEN ×0.0 as a *multiplier* on similarity | deterministic | per-memory `state` column | state transition via reinforce/forget |
| RESONANT/INHIBITORY links | `memory_engine.py` link tables | amplify/suppress branches during BFS; INHIBITORY auto-created on claim conflict | deterministic | `cell_links` table | link creation / traversal |
| Claim-tagged contradiction | README §links; store path | same `topic`+different `claim` → bidirectional INHIBITORY link | deterministic, metadata-driven (no NLI) | topic+claim metadata on store | store→link |
| STDP synaptic learning | `memory_engine.py:2131` `_update_stdp` | LTP `weight=min(2.0,w+0.10)`, LTD `weight=max(0.0,w-0.02)`, prune ≤1e-9 | deterministic | synaptic weights table | recall co-activation→weight update |
| Rescue rule | `memory_engine.py` (rescue loop, cited `1455-1463` in INTERVENTION_DESIGN) | a REINFORCED memory cannot be silenced by a non-REINFORCED claim | deterministic | states + links | BFS exclusion→restoration |
| Scoring pipeline | README §scoring; constants `memory_engine.py:89-118` | `sim×state×exp(-0.15·hop)+resonant+synaptic×0.3+recency` | **float-based** (cosine, exp) | per-memory fields | scored ranking |
| Audit chain | `memory_engine.py:425` `compute_audit_hash`, `:484` `verify_audit_chain` | SHA-256 over canonical key-sorted JSON, prev-hash linked, recomputable from DB columns | deterministic | `audit_log` table | recall→sealed entry |
| Sleep consolidation | `raven/sleep_consolidator.py` | agglomerative cosine clustering, merge inside single `BEGIN IMMEDIATE` txn | deterministic | SQLite | episodic→consolidated node |
| Stylometric verification | README §stylometric | author fingerprinting, per-language rolling profile, forensic alert; quarantine opt-in | deterministic | per-author profiles | recall→alert/optional quarantine |
| Spectral field | `raven/spectral.py` | SVD eigenmodes, resonance/coherence as read-only metadata (NOT in ranking) | best_effort (declared `determinism_level:"best_effort"`) | persisted mean vector | recall→metadata |
| Honest degradation (embeddings) | `raven/qwen_client.py` | 3-tier fallback local→Qwen→SHA-256 dummy, `degraded:true` stamped | deterministic | provider config | text→embedding |
| InterventionSpec (causal probes) | `raven/intervention.py`; `memory_engine.py:2026` `intervene`, `:1614` `_recall_core` | `I(c,q)=D(R(q),R(q|do(c=0)))` — **retrieval causal influence**, NOT agent-answer causality | deterministic (single `now`, single lock) | read-only probe | spec→decomposed Δ |

### 1.2 Key properties and assumptions

- **Assumption:** similarity (cosine) is a meaningful proximity for memory
  relevance. The whole field is built on top of an embedding space.
- **Assumption:** float arithmetic in the scoring path is acceptable because
  raven's outputs are rankings + audit, not Daubert-admissible forensic
  verdicts. (MNEME later rejects this assumption — see §2.)
- **Determinism:** scoring is float-based and therefore **not** bit-for-bit
  reproducible across platforms/processes. The audit chain is recomputable
  from stored columns, but the *ranking* that produced a recall is not sealed
  as exact. OBSERVED: constants are floats (`HOP_LAMBDA=0.15`, etc.).
- **Intervention scope (OBSERVED, important):** the design explicitly limits
  the causal claim to `(intervention → RAVEN retrieval)`, NOT
  `(intervention → agent answer)`. `intervention.py:8-11`,
  `INTERVENTION_DESIGN.md:20-40`. This is the honest scope we must preserve.
- **Empirical finding (OBSERVED in INTERVENTION_DESIGN.md:349-371):** on a
  42-cell synthetic field, influence manifests as **rank descent, not
  deletion**, because the k-NN graph is symmetrized so cells rarely become
  topologically isolated. `REDUNDANT_PATHS` is implemented and tested but
  **not yet observed in a real field** — open hypothesis.

### 1.3 Tests present (OBSERVED)

`tests/test_intervention.py`, `tests/test_intervention_properties.py`
(adversarial metamorphic properties), `tests/test_fuzz_oracle.py` (rescue
fuzzer with stubbed-engine counterfactual), `tests/test_recency_bounds.py`
(negative-age clamp), `tests/test_state_witness*.py`, `tests/test_db_adversary.py`,
`tests/test_digest_coverage.py`. CI: `.github/workflows/ci.yml` (3.11/3.12).

### 1.4 Known limitations (OBSERVED / INFERRED)

- Float scoring → ranking not bit-reproducible across processes (INFERRED
  from float constants; MNEME confirms this is the gap it closes).
- `now` is fixed *within* a probe but not *between* probes; cross-probe score
  comparison needs an injectable `now` that does not exist yet.
  OBSERVED: `INTERVENTION_DESIGN.md:387-397`.
- Spectral field is best-effort across processes (declared).
- Stylometric quarantine is opt-in; detection and action are decoupled.

### 1.5 Reusability (INFERRED)

The field mechanics (states, links, BFS, rescue, STDP) are a self-contained
SQLite+numpy engine with no external service required. The intervention
primitive is the most directly research-relevant mechanism here. The
float scoring is a liability for any sealed/forensic claim and would need
MNEME-style exactification to compose with a custody layer.

---

## 2. MNEME — forensic memory substrate (custody, authority, causality)

### 2.1 Mechanism inventory

| Mechanism | Location (OBSERVED) | Property claimed | Deterministic? | State required |
|---|---|---|---|---|
| Canonical JSON + exact numbers | `mneme/canonical.py`; SPEC §1 | keys sorted, floats **refused**, Decimals at scale 10 verified by exponent, one quantize fn | deterministic | — |
| Per-memory custody chains | `mneme/custody.py`; SPEC §2-3 | hash-chained, genesis-bound to memory_id, append-only, seq dense from 0, closed versioned vocabulary | deterministic | `custody_chain` table |
| Authority / capability model | `mneme/authority.py`; SPEC §4 | 12 capabilities, per-actor chains, grants/revocations, quarantine = empty capability set (write barrier) | deterministic | `authority_chain` table |
| Claims (propositions ≠ documents) | `mneme/claims.py`; SPEC §5 (C1-C6) | statement immutable, standing **derived not stored**, bilateral relations | deterministic | `claim_chain` table |
| Exact ranking | `mneme/field.py:53-129` | raven's formula with `Fraction`; sqrt eliminated via `t²/n` ordering; ties on memory_id | **bit-for-bit deterministic** | embeddings as Fractions |
| Recall gate (WHERE clause) | `ARCHITECTURE.md:236-250` | `custody_status='CLEAN'` pushed into SQL predicate; gate extends to graph (both endpoints CLEAN to traverse) | deterministic | custody_status |
| Recall receipts | `mneme/causality.py` (receipts); SPEC §7 | sealed digest over query/seed/served ids/withheld counts by cause | deterministic | receipt columns |
| Recall→decision causal closure | `mneme/causality.py`; `DECISION_USED_MEMORY` event | decision cites a non-counterfactual receipt, claims only memories recall actually SERVED, bilateral | deterministic | decision records |
| Counterfactual worlds | `mneme/counterfactual.py` | exact delta between two sealed worlds (ranking is exact) | deterministic | sealed worlds |
| Taint / quarantine / rehabilitation | `mneme/custody.py` taint model; `ARCHITECTURE.md:172-234` | graded exposure (exact rational budget), write barrier, taint re-derived from evidence (taint 2.0.0) | deterministic | taint_sweeps |
| Blast-radius analysis | `influence_exposure()` `ARCHITECTURE.md:215-222` | DIRECT_TAINT/INFLUENCE_EXPOSED/CLEAN, INHIBITORY conveys nothing | deterministic | links |
| Temporal reconstruction | SPEC §1.4, §2.5 | timestamps fixed-width UTC µs, lexicographic=chronological, non-decreasing along seq | deterministic | timestamps |
| Offline verification | `verify_offline.py`; conformance vectors | stdlib-only verifier, two-verifier discipline, conformance/ reproduces digests | deterministic | bundle |
| Protocol versioning | SPEC §11; `ARCHITECTURE.md:280-293` | a bundle declares the semantics it commits to; verifier refuses unknown versions | deterministic | bundle version |

### 2.2 Key properties and assumptions

- **Assumption (OBSERVED, SPEC §0.3):** a hash chain proves bytes were not
  edited; it does **not** prove the history is true. An adversary controlling
  every write can emit a perfectly-verifying field that never happened.
  Binding to external time/identity is a deployment decision MNEME does not
  make. This is the central honesty boundary.
- **Assumption:** the field mechanics are inherited from raven and are not
  the contribution (OBSERVED `ARCHITECTURE.md:39`). MNEME's contribution is
  that *every claim the field makes about itself is checkable by someone who
  distrusts it*.
- **Determinism (OBSERVED):** M5 — floats never decide. Confidence,
  promotion thresholds, and ranking are exact `Fraction`; `Decimal` at scale
  10 only at the hash/SQL boundary via one quantize function. The one
  sanctioned float crossing is embedding ingestion (a measurement),
  quantized once. `field.py:85-117`.
- **Promotion rule (OBSERVED):** `PROMOTION_THRESHOLD=3/4`; a STATE_CHANGED
  NEUTRAL→REINFORCED is valid only when confidence has reached the threshold
  (replay 1.1.0). This closed a mutant that survived every 1.0.0 check.
  `SPEC.md:372-392`, `field.py:76`.

### 2.3 Tests present (OBSERVED)

`tests/test_*_pure.py` (authority, bundle, causality, claims, counterfactual,
custody, field, influence, provenance), `tests/test_conformance.py`,
`tests/test_protocol_vectors.py`, `tests/test_semantic_mutants.py` (semantic
mutation testing — would a reimplementation with a wrong rule still verify?),
`tests/test_spec_agreement.py`. Conformance vectors in `conformance/`.

### 2.4 Known limitations (OBSERVED)

- See `KNOWN_LIMITATIONS.md` (not fully read yet — TODO for deeper pass).
- Transitive taint is advisory (one-hop RESONANT neighbours reported, never
  auto-flagged). `ARCHITECTURE.md:232-234`.
- Descent (`derived_from_decision`) is unilateral, a stated limitation not
  oversight. `SPEC.md:418-420`.

### 2.5 Reusability (INFERRED)

MNEME is the most self-contained *forensic* layer. Its custody/authority/
claim/counterfactual modules are pure-Python, stdlib-verifiable, and designed
to compose with a field. The exact-ranking `field.py` is a drop-in
replacement for raven's float scoring if sealed/forensic claims are needed.
**However:** MNEME does not itself provide retrieval-quality improvements
over raven — it provides *verifiability* of whatever the field does. The
research question is whether verifiability/provenance produces measurable
properties retrieval alone lacks (e.g. contamination containment, causal
attribution to decisions).

---

## 3. STIGMERGY — shared memory as indirect coordination substrate

### 3.1 Mechanism inventory

| Mechanism | Location (OBSERVED) | Property claimed | Deterministic? | State required |
|---|---|---|---|---|
| Stigmergic coordination | `ARCHITECTURE.md:25-30` | agents communicate only by writing/observing shared state; no agent coordinates another | deterministic | CockroachDB shared state |
| memory_regions (living entities) | `schema.sql`; `ARCHITECTURE.md:46-49` | regions carry `generation`/`parent_region` lineage; splits/merges reconstructable | deterministic | `memory_regions` |
| state × tier independent axes | `ARCHITECTURE.md:76` | state (REINFORCED/NEUTRAL/FORGOTTEN) and tier (SHORT_TERM/REGIONAL/GLOBAL/ORPHANED) are separate | deterministic | `memories` |
| recruitment_signals (pheromones) | `ARCHITECTURE.md:62-66,78` | write-only stigmergic protocol, decays over time (`signal_strength`+`decay_rate`) | **float exp() decay** (documented departure) | `recruitment_signals` |
| agent_search_state (hysteresis) | `ops/controller.py:64-101` | pure Fraction hysteresis (β=1/4, enter=3/5, exit=2/5) over resonance density | deterministic (Fraction) | `agent_search_state` |
| resonance_density | `ops/controller.py:149-174` | exact Fraction, counts REINFORCED | deterministic | pairs |
| Migration cooldown | `ARCHITECTURE.md:57-60` | a memory never migrates twice within cooldown; weighted recruitment consensus | deterministic | cooldown window |
| Orphaning / rediscovery | `ops/orphans.py`; `ARCHITECTURE.md:67-69` | stale→ORPHANED (not deleted); REDISCOVERED is audited | deterministic | tier |
| Per-node audit_chain | `audit/chain.py`; `ARCHITECTURE.md:80` | per-node tamper-evident hash chain | deterministic | `audit_chain` |
| Per-memory custody_chain | `audit/custody.py`; `ARCHITECTURE.md:82-96` | ported from MNEME, genesis-bound to memory_id | deterministic | `custody_chain` |
| Merkle snapshots (ledger of ledgers) | `audit/merkle.py`; `ARCHITECTURE.md:81` | chained Merkle roots over all nodes' chain heads; no global sequence | deterministic | `merkle_snapshots` |
| Taint sweeps | `ops/trust.py`; `ARCHITECTURE.md:83,98-108` | quarantine_actor flags memories a node's chain names, seals flagged set, recall gates on CLEAN | deterministic | `taint_sweeps` |
| CockroachDB as load-bearing | `ARCHITECTURE.md:117-129` | vector index prefix (region-constrained search), changefeeds (not polling), multi-region locality | deterministic | CockroachDB |
| Embeddings | `embeddings/minilm.py`, `embeddings/deterministic.py` | minilm + deterministic fallback | mixed | baked vector table |

### 3.2 Key properties and assumptions

- **Assumption (OBSERVED):** shared state is the coordination medium; no
  direct agent-to-agent messaging. This is the defining stigmergic property.
- **Determinism (OBSERVED):** decision path uses Fraction/DECIMAL
  (`controller.py` hysteresis). **Documented departure:** recruitment signal
  decay uses `exp()` over floats, justified because it affects reinforcement
  dynamics, not a forensic verdict. `ARCHITECTURE.md:137-141`.
- **LLM out of decision path (OBSERVED):** invariant 2 — LLMs may label/narrate
  but never decide reinforce/migrate/consolidate/split/merge.
  `ARCHITECTURE.md:31-36`.
- **CockroachDB is load-bearing, not swappable (OBSERVED):** vector index
  prefix, changefeeds, multi-region locality are part of the algorithm.
  `ARCHITECTURE.md:117-129`. This is a heavy infrastructure dependency.

### 3.3 Tests present (OBSERVED)

`tests/test_*_pure.py` (audit, authority, bundle, console_contract, controller,
custody, lambdas, ops, orphans, recruitment, regions_demo, trust),
`tests/test_authority_integration.py`, `tests/test_lambda_authority_integration.py`,
`tests/INTEGRATION_CHECKLIST.md`. **Caveat (OBSERVED):** custody/trust layer
is pure-tested but NOT yet exercised against a real cluster
(`ARCHITECTURE.md:110-115`). Do not claim Cloud-verified.

### 3.4 Known limitations (OBSERVED)

- Byzantine consensus out of scope; multiple compromised credentials can
  represent multiple legitimate regions. `ARCHITECTURE.md:133-136,157-163`.
- Split/merge of regions is a stretch goal, not Phase 1 core.
- Float decay in recruitment (documented departure).
- Custody layer not cluster-verified yet.

### 3.5 Reusability (INFERRED)

STIGMERGY's *unique* contribution is the multi-agent stigmergic coordination
model (recruitment signals, regions, hysteresis controller, Merkle ledger of
ledgers). Its custody/audit layers are ports of MNEME/raven. **For a
single-agent memory study, most of STIGMERGY's value is inert** — the
multi-agent propagation is its differentiator. The CockroachDB dependency is
heavy and only justified if multi-agent shared-state experiments are in
scope. The Fraction hysteresis controller is small and reusable.

---

## 4. Cross-system mechanism map (terminology disambiguation)

The user warned: do not call all of these "memory". They are distinct
mechanisms producing distinct properties.

| Category | raven-memory | MNEME | STIGMERGY |
|---|---|---|---|
| **storage** | SQLite memories + KDTree index | SQLite memories + chains | CockroachDB memories + regions |
| **retrieval** | KDTree seed + BFS top-k | gated BFS (CLEAN only) top-k | region-constrained vector search |
| **ranking** | float composite score | **exact Fraction** score (same formula) | resonance density (Fraction) for control |
| **memory state** | ternary (REINFORCED/NEUTRAL/FORGOTTEN) | same ternary + custody_status (CLEAN/QUARANTINED/TAINTED/SUPERSEDED) | same ternary state + independent tier axis |
| **learning/adaptation** | STDP (LTP/LTD), reinforcement, decay, consolidation | reinforcement (exact α=1/4), promotion threshold | recruitment decay, migration, orphaning, region dynamics |
| **provenance** | audit chain (per-recall) | per-memory custody chain + per-actor authority chain | per-node audit + per-memory custody + Merkle ledger |
| **authorization** | none (single trust domain) | capability model (12 caps, grants/revocations) | node principals + regional capabilities |
| **causal attribution** | retrieval causal influence (intervention Δ) | recall→decision closure (DECISION_USED_MEMORY + receipts) | none direct (coordination is indirect) |
| **counterfactual analysis** | intervention: R(q) vs R(q\|do(c=0)) | counterfactual worlds (exact sealed deltas) | none |
| **collective/shared memory** | none (single agent) | none (single agent) | **yes — stigmergic shared state** |
| **contamination/containment** | stylometric quarantine (opt-in) | taint model, graded exposure, write barrier, rehabilitation | taint sweeps (ported from MNEME) |
| **historical reconstruction** | audit chain recompute from DB | full offline bundle verification | audit + custody + Merkle |
| **determinism level** | float ranking (not bit-reproducible) | **exact** (Fraction, bit-reproducible) | Fraction decisions + float recruitment decay |

### 4.1 Where the systems genuinely differ (OBSERVED)

1. **raven vs MNEME on determinism:** raven ranks with floats; MNEME ranks the
   same formula with Fractions and eliminates sqrt via `t²/n` ordering
   (`field.py:19-31`). MNEME can seal a ranking; raven cannot (bit-for-bit).
2. **raven vs MNEME on causality:** raven measures *retrieval* causal
   influence (intervention on the field). MNEME measures *decision* causal
   closure (which memories a decision actually consumed, bilaterally bound).
   These are different causal questions at different layers.
3. **MNEME vs STIGMERGY on custody:** STIGMERGY ported MNEME's custody_chain
   but adds a per-node audit_chain + Merkle ledger because there are multiple
   nodes with no global ordering. MNEME has one logical writer domain.
4. **STIGMERGY alone has collective memory:** recruitment signals let one
   agent's experience propagate to others through shared state, never
   directly. This is the only mechanism addressing multi-agent memory
   propagation.

### 4.2 Where terminology collides but semantics differ (OBSERVED)

- "REINFORCED" means ×1.5 multiplier in raven, a custody event + exact
  confidence in MNEME, and a state axis independent of tier in STIGMERGY.
  Same word, three semantic payloads.
- "rescue rule" exists in raven and is *inherited* by MNEME (same logic),
  but MNEME additionally gates the *graph* on CLEAN so a tainted node can
  neither inhibit nor resonate. STIGMERGY inherits the raven semantics.
- "audit chain" is per-recall in raven, per-memory+per-actor in MNEME,
  per-node+per-memory+Merkle in STIGMERGY. Different subjects, same name.
- "forgetting" is exclusion-from-KDTree (preserved) in raven; in MNEME it is
  a STATE_CHANGED custody event; in STIGMERGY it is a state on one axis while
  tier may still be REGIONAL.

---

## 5. Open questions for Phase 2+ (UNKNOWN / INFERRED)

- Does MNEME's exact ranking change *retrieval quality* vs raven's float
  ranking, or only its *verifiability*? (INFERRED: only verifiability — same
  formula. Needs experimental confirmation.)
- Does the rescue rule produce a measurable property that retrieval+metadata
  cannot? (UNKNOWN — raven's own fuzzer found the violation branch is
  currently *unreachable* by construction, `intervention.py:221-232`. The
  invariant may be vacuously true under current semantics.)
- Does STIGMERGY's stigmergic propagation produce collective-memory
  properties that single-agent retrieval cannot represent? (INFERRED yes, but
  only testable in a multi-agent setting — which is a different experiment
  class.)
- Is raven's intervention model already a sufficient "optogenetics analog",
  or does it need MNEME's counterfactual worlds to attribute *decision*
  effects? (INFERRED: they answer different questions; both may be needed.)

These feed Phase 2 (dependency pruning) and Phase 3 (baselines).
