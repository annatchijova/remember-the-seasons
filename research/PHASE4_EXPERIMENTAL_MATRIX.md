# Phase 4 — Experimental matrix and ablation plan

> Design only. Not implemented. Every experiment states the property, the
> baselines, the metric, the control, and the falsifier. Keep evaluation
> dimensions separate: custody/provenance may improve auditability without
> improving recall — do not fold them into one "accuracy" number.

---

## 1. Property → experiment matrix (PROPOSED)

| # | Property | Primary baselines | Metric (separate dimensions) | Control / falsifier |
|---|---|---|---|---|
| E1 | retrieval quality | B0, B2, B4, B5 | recall@k, nDCG@k, MRR | Falsifier: B4/B5 do not beat B0/B2 on conflict-free lookup (expected loss — bounds scope). |
| E2 | preference replacement | B0, B1, B4, B5 | (a) does newer preference win the ranking? (b) is old evidence preserved (binary)? | Control: B1 with a `superseded` metadata flag. Falsifier: B1 matches B5 on (a) AND (b). |
| E3 | contradiction resistance | B0, B1, B4, B5 | (a) validated claim rank vs contradicted claim rank; (b) both-served rate | Control: B1 with a `trust` flag rerank. Falsifier: metadata trust flag reproduces collapse-around-truth. |
| E4 | temporal validity / forgetting | B0, B4 | (a) stale-memory serve rate over time; (b) recall of still-relevant old memories (forgetting must not over-forget) | Falsifier: decay/forgetting hurts recall of genuinely-relevant old memories more than it helps. |
| E5 | catastrophic interference | B0, B4 | recall degradation after inserting many conflicting memories | Falsifier: B4 degrades no less than B0 (dynamics don't protect). |
| E6 | consolidation / reinforcement | B0, B4 (+ consolidation) | recall quality after a consolidation pass vs without | Falsifier: consolidation does not improve later recall (E1-equivalent) — it only compresses. |
| E7 | causal effect on decisions | B0, B4 (intervention), B5 (counterfactual) | retrieval causal influence Δ (decomposed: disappeared/appeared/rank_displacement/score_delta) AND decision-closure (did the decision cite only served memories?) | Negative control: `targets=[]` → Δ=0 exactly. Falsifier: Δ is always 0 (no memory has retrieval influence) OR decision-closure adds no measurable property. |
| E8 | contamination & containment | B0, B5 (taint/gate) | (a) tainted memory serve rate (must be 0 with gate); (b) blast-radius grading correctness (DIRECT/EXPOSED/CLEAN); (c) over-quarantine rate (clean memories wrongly withheld) | Control: B1 with a `quarantined` metadata filter. Falsifier: binary metadata filter matches graded exposure on (a) and (c). |
| E9 | historical reconstruction | B0, B5 | can a third party reconstruct what was served/decided offline? (binary + receipt recompute rate) | Falsifier: B0 cannot; B5 can — but this is a verifiability dimension, scored separately from recall. |
| E10 | multi-agent experience propagation | B0-per-agent, B7 (stigmergic) | late-agent task success with vs without access to earlier agents' recruitment signals | Falsifier: propagation adds nothing over each agent's own B0 retrieval. Only valid on a real shared substrate (shim must be validated first). |
| E11 | latency / storage / cost | all | p50/p99 recall latency; storage bytes; tokens injected | Falsifier: dynamics cost more than B0 with no property gain (overhead without benefit). |

## 2. Ablation plan (PROPOSED)

Ablations remove one mechanism from the full candidate (B4 or B5) and measure
the delta on the property that mechanism claims to produce. The candidate is
the *full* system; ablations subtract.

| Ablation | Removed from | Measured on | Expected if mechanism matters |
|---|---|---|---|
| -propagation (hops=0) | B4 | E1, E3, E7 | recall/contradiction/causal-influence drop toward B0 |
| -states (all NEUTRAL) | B4 | E2, E3, E4 | collapse-around-truth and preference replacement fail |
| -links (no RESONANT/INHIBITORY) | B4 | E3, E5 | contradiction resistance fails |
| -STDP (freeze weights) | B4 | E1, E6 | association learning has no effect (suspected) |
| -rescue | B4 | E3 | REINFORCED memory can be silenced by NEUTRAL (note: currently unreachable — see vacuity) |
| -graph-gate (serve-only gate) | B5 | E8 | tainted node can still perturb clean memory's ranking (OBSERVED risk, ARCHITECTURE.md:243-246) |
| -custody (no chains) | B5 | E9 | offline reconstruction impossible |
| -exact-ranking (float) | B5 | E9 | receipts not bit-reproducible across processes |
| -counterfactual | B5 | E7 | "what did the poison do" unanswerable exactly |
| -recruitment (no signals) | B7 | E10 | no propagation to late agents |
| -cooldown | B7 | E10 | oscillation A→C→A→C under noise |

**Do NOT expect every ablation to hurt accuracy.** Per the brief:
custody/provenance may improve auditability without improving recall. Score
each ablation on the dimension its mechanism targets, not on a global
accuracy. An ablation that does not move its target dimension is evidence the
mechanism is not earning its place.

## 3. Evaluation dimensions kept separate (PROPOSED)

- **Recall quality:** recall@k, nDCG@k, MRR (E1, E2, E3, E4, E6).
- **Decision quality:** downstream task accuracy/faithfulness when retrieved
  context feeds a pinned LLM (E2, E3, E7 end-to-end).
- **Causal attribution:** Δ decomposed (E7) — never collapsed to one scalar.
- **Provenance/auditability:** offline reconstruction rate, receipt recompute
  rate (E9) — a separate axis; do not average with recall.
- **Containment:** serve rate of tainted, blast-radius grading correctness,
  over-quarantine rate (E8).
- **Cost:** latency, storage, tokens (E11).

A system that improves provenance but not recall is reported as "improves
provenance, not recall" — not as "improves memory".

## 4. Confounders and threats to validity (PROPOSED)

- **Embedding variance:** if embeddings differ across systems, the comparison
  tests the embedder, not the mechanism. Fix one pinned embedder.
- **Hyperparameter tuning asymmetry:** if B4 is tuned and B0 is not, B4 wins
  by tuning. Give every system the same tuning budget (ideally none — pin).
- **Task-design bias:** tasks written by the author of the dynamics system
  bias toward dynamics. Include retrieval-favorable tasks (§Phase3.3) and,
  where possible, an independent task source.
- **Vacuous invariants:** the rescue-rule fuzzer's violation branch is
  currently unreachable by construction (OBSERVED). An invariant that cannot
  fail is not evidence of a property; it is evidence of vacuity. Test the
  *discriminating* form, not the vacuous one.
- **Shim vs substrate:** STIGMERGY on a SQLite shim is not STIGMERGY on
  CockroachDB. Validate the shim against the real substrate before any
  collective-memory claim.
- **LLM variance:** end-to-end tasks add model variance. Use temp=0, pinned
  model, multiple seeds, report intervals not point estimates.
- **Float determinism:** raven's float ranking is not bit-reproducible across
  processes. Any sealed-claim comparison must use MNEME's exact ranking or
  acknowledge the non-determinism.
- **Single-author conformance:** MNEME's two verifiers share an author
  (OBSERVED SPEC §0). A third implementation disagreeing is the real test;
  absent that, conformance is necessary not sufficient.
