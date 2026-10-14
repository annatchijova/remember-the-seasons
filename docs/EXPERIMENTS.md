# Experiments index

For the H14 intervention vocabulary, evidence map, and scope boundaries, see
the [Memory Lab research guide](MEMORY_LAB.md).
For the source-level operation and observation inventory behind Exp54–55, see
[Raven observational contract](RAVEN_OBSERVATIONAL_CONTRACT.md).

All 36 numbered experiment scripts in `experiments/`, grouped by phase. Verdicts are
observed results, not aspirations. `PASS` means the property survived
falsification; `FALSIFIED` means the experiment killed the hypothesis.

Research question: where does retrieval stop being a sufficient model
of persistent agent memory, and what additional mechanisms produce
measurable properties that retrieval alone does not represent?

## Phase 1-3: archaeology and baselines

| Script | Question | Verdict |
|---|---|---|
| `minimal_raven.py` | Faithful minimal implementation of Raven (graph + STDP + rescue + state + recency) | — |
| `run_trials.py` | Trial runner for statistical experiments | — |

## Phase 4-7: core falsification battery

| Script | Experiment | Verdict |
|---|---|---|
| `exp1b_set_composition.py` | H1: does propagation change the recall SET vs B1? | SURVIVES (bounded: positive cosine required) |
| `exp4_b2prime_challenge.py` | H1 hard test: B2' with recency+state on retrieval | SURVIVES |
| `exp5_washout.py` | H2: does intervention differ from removal? | SURVIVES (weak: scores only) |
| `exp6_real_embeddings.py` | Robustness with real embeddings | SURVIVES |
| `exp7_robustness.py` | Robustness across noise/seeds | SURVIVES |
| `exp8_dose_response.py` | Dose-response: does divergence scale with dose? | YES |
| `exp9_washout_curve.py` | H8: does divergence persist post-washout? | SURVIVES (persistent within observed horizon) |

## Phase 8-9: downstream impact and collective memory

| Script | Experiment | Verdict |
|---|---|---|
| `exp10_chess_control.py` | H8a: cross-domain leak control | WEAK (filters but not orthogonal) |
| `exp11_downstream_decision.py` | H8b: do recall changes flip decisions? | WEAK (2.3% flips) |
| `exp12_mneme_causal_closure.py` | H9: per-instance causal closure via custody | WEAK (56.5% — CF0 set-membership only) |
| `exp13_stigmergy_collective.py` | H10: collective path dependence | FALSIFIED (tautological — global state mutation) |
| `exp14_causal_replay.py` | H9 upgraded: causal-state replay | SURVIVES (CF2a: 100% closure, state-only) |
| `exp15_stigmergy_factorial.py` | Factorial decomposition of Exp13 | DECOMPOSED (de-reinforcement is the active ingredient) |
| `exp16_provenance.py` | Per-agent provenance | FALSIFIED collective contagion |
| `exp17_resilience_curve.py` | Collective resilience curve | SURVIVES (but see Exp21-23) |
| `exp18_chess_real.py` | Chess with python-chess + material/mobility | PIPELINE CHECK (not behavioral specificity) |

## Phase 10: the amputation

| Script | Experiment | Verdict |
|---|---|---|
| `exp19_stateful_baseline.py` | H12: retrieval + state, no Raven machinery | BASELINE REPRODUCES H8; Raven amplifies ~2x |
| `exp20_chess_behavioral.py` | H11: LLM + Stockfish behavioral assay | INCONCLUSIVE (n=1 informative seed) |
| `exp24_chess_tost.py` | H11 done properly — preregistered + TOST | INCONCLUSIVE (CI crosses δ=30cp; 87% agreement, mixed-sign diffs) |
| `exp28_variance_decomposition.py` | Does C↔I exceed LLM noise floor? | MARGINAL SIGNAL (D(C,I)=1.9x noise; deterministic context effects on minority of positions) |
| `exp21_threshold_sweep.py` | Is k*=N-1 emergent or algebraic? | MOSTLY ALGEBRAIC (k*=N-T for T=1,2) |
| `exp22_topology_prediction.py` | Can per-memory topology predict flips? | MOSTLY DERIVABLE (8/9 thresholds, 91% precision) |
| `exp23_residual_decomposition.py` | What explains the residual? | DERIVABLE (100% late bloomers: direct loss 99.3% + cascade 33.8%) |
| `exp25_state_amputation.py` | What is the minimum sufficient state? | Binary flag suffices; accumulation required; persistence across queries required |
| `exp26_state_compression.py` | How many bits does H8 need? | PREMATURE — see Exp26b |
| `exp26b_falsification.py` | Is the threshold real? Does location matter? | BOTH FALSIFIED — no clean threshold; scattered ≥ coherent |
| `exp27_explain_7v8.py` | Why does ng=7 produce H8 and ng=8 not? | OBSERVED — late-flagged group + feedback loop; partition accident |
| `exp29_feedback_mechanism.py` | When does flag divergence self-amplify? | WEAK FEEDBACK — top-1 flips 20% of flag-diff steps; ng=7 grows slowly, ng=11/25 self-correct |
| `exp30_mediator_intervention.py` | Does the late-flag→top-1→reinforcement chain mediate? | CONFIRMED (scoped) — rescue kills, induce creates, top1_swap converges; audited |
| `exp31_asymmetry_duration.py` | Does asymmetry duration predict divergence? | PERSISTENCE MODULATES — P(div) saturates d≥4, magnitude scales with hold; duration vs blocked-transitions confound unresolved → Exp32 |
| `exp32_duration_vs_count.py` | Duration per se vs blocked-transition count? | COUNT EXPLAINS GRADIENT, NOT FULL EFFECT — equal count ≡ equal washout across arms, but early>late at same k; count is not a sufficient statistic |
| `exp33_transition_leverage.py` | What makes a transition's causal leverage? | REVISED DOWN by Exp34 — supp_rate varied by position (opportunity selection); real early premium ~0.05 not 5x |
| `exp34_event_indexed_leverage.py` | Event-indexed leverage, one realized block | NEITHER dominates — j≤3 premium ~0.15 vs ~0.10; shadow hypothesis dead; accumulation > position |
| `exp35_dose_position_factorial.py` | Dose x position factorial | Placement matters at equal realized count: k=1 gives early 0.152 vs late 0.004 (n=24); realized_k is post-treatment — coefficients descriptive only |

## Runner infrastructure

| Script | Role |
|---|---|
| `sweep_infra.py` | Shared sweep infrastructure |

## Phase 11: H14 restoration (independent toy assay)

| Script | Question | Verdict |
|---|---|---|
| `exp36_h14/exp36_h14_restoration.py` | Do re-exposure, state restoration, link restoration, and relearning recover A's measured influence? | RUNTIME-CONFIRMED toy execution; H14 verdict OPEN (one synthetic configuration) |
| `exp37_h14_measurement/exp37_h14_causal_measurement.py` | Does a signed action-score instrument preserve effects hidden by choice flips, with frozen A-incident links? | RUNTIME-CONFIRMED instrument checks; H14 verdict OPEN (one synthetic configuration) |

See [`research/PHASE11_H14_TOY_ASSAY.md`](../research/PHASE11_H14_TOY_ASSAY.md) for Exp36's provenance and limits, and [`research/PHASE11_H14_EXP37_MEASUREMENT.md`](../research/PHASE11_H14_EXP37_MEASUREMENT.md) for Exp37's measurement definition, test evidence, and limits.

## H14 follow-up: observational quotient and transition stability

**OBSERVED, synthetic:** Exp48 groups states by exact traces from 24 fixed
challenger-score schedules. Exp49 tests transition congruence for two forced
choices, C and K. Exp50 repeats the stability and minimization check with
shared challenger-score inputs, leaving the state-dependent choice inside the
Exp47 transition function.

From one documented Exp47 seed, Exp50 enumerates a closed 172-state reachable
set. Its 22-score input alphabet covers the distinct C/K choice regions at the
declared reinforcement-count levels. Partition refinement yields 68, 93, then
118 classes, and reaches a fixed point on the next round. This partition
matches Exp48's 118 observational classes on that closure. Across 2,376
equivalent-state-pair/input checks, there were no immediate-output mismatches
or successor-class mismatches.

The run includes certificates for all 6,903 pairs of distinct classes: 6,169
pairs differ on the initial observation, and the remaining 734 have shortest
distinguishing input sequences of one to three steps. All certificates replay
against the transition function. A deliberate constant-observation mutation
collapses the machine to one class and is detected by the test suite (12 tests
pass, including that mutation control). The result supports 118 as the minimum behavioral
class count for this finite machine, seed, input alphabet, and declared
observables. It does not establish minimality for other seeds, arbitrary
transition rules, Raven, or MNEME. Exp50 code, tests, and the reproducible JSON
are in [`experiments/exp50_h14_partition_refinement/`](../experiments/exp50_h14_partition_refinement/).
See the [Exp48–50 minimality report](H14_EXP48_50_MINIMIZATION.md) for the
machine definition, refinement, certificates, and bounded claim.

## H14 follow-up: Raven longitudinal transfer pilot

**OBSERVED, copied Raven source plus synthetic fixture:** Exp51 ran six
longitudinal arms against a copy of source commit
`56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`. Its raw-core negative control
found that a suppressed memory can still emit a synaptic pull when included in
`current_turn_memories`; the experiment-only adapter filters this source and
does not change the read-only snapshot. The amended run records retrieval,
signed non-target score effects, standardized propagation, and state at each
checkpoint. Several branches differ after five washout experiences, while
re-exposure and relearning converge on the measured values in this fixture.
This is not downstream agent behavior or a deployed Raven evaluation, and the
differences remain explainable by the stored Raven state/link trajectory.
See the [preregistration, amendments, report, tests, provenance, and run
artifact](../experiments/exp51_raven_h14_longitudinal/).

## H14 follow-up: suppression semantics and operational erasure

**OBSERVED, copied Raven source plus synthetic fixture:** Exp52 separates
result exclusion from influence exclusion. With A suppressed as a field cell,
the raw core omitted A but still returned C from A's `current_turn_memories`
synaptic link; C scored `0.18`, and A's `A→B` link added `0.24` to B's score.
The no-source control omitted C. Filtering A from that source list made the
non-A score vector match the no-source control exactly. The finding is bounded
to the copied source snapshot and tested input.

Exp52 also compared two histories from one seed, then deleted A and all
incident synaptic and cell links in both. One remaining value differed after
the matched post-deletion schedule: C's `recall_count` was 5 after A
participated and 4 in the suppressed control. All four post-deletion query
score vectors and rankings nevertheless matched exactly. This falsifies exact
persistent-state equivalence for the operational deletion protocol while
supporting observed retrieval equivalence for only the four fixed queries.
It does not demonstrate functionally consequential historical persistence or
universal erasure. See the [Exp52 preregistration, report, tests, provenance,
and run artifact](../experiments/exp52_raven_suppression_semantics/).

## H14 follow-up: `recall_count` consumers

**OBSERVED, copied Raven source plus synthetic fixture:** Exp53 compared two
states whose only difference was C's persisted `recall_count` (5 versus 4),
with B held at 4 in both. Four fixed `_recall_core()` queries had identical
score components and rankings. This supports retrieval invariance only for
those inputs.

The count was observable through stats and memory serialization. With
`export_graph(max_nodes=1)`, S5 selected C and S4 selected B: S4 tied B and C
at count 4, and this SQLite fixture returned B first. The source query has no
secondary tie-break, so that exact tied selection is database-plan dependent.
Exp53's sleep-consolidator dry runs matched because that code derives
consolidation counts from `audit_log.memories_retrieved`, held identical in
both branches, rather than reading this row field. Equalizing the counter
made all measured output groups match.

The assay therefore falsifies broad observational redundancy for the
declared stats/inspection/export interfaces, while finding no retrieval score
or rank effect in the four tested queries. It does not establish downstream
agent impact. See the [Exp53 preregistration, operation inventory, report,
tests, provenance, and run artifact](../experiments/exp53_raven_latent_trace/).

## H14 follow-up: observable contract and transition congruence

**OBSERVED, copied Raven source plus synthetic fixture:** Exp54 inventoried
the FastAPI routes and MCP tools, distinguishing declared external operations
from engine/storage helpers. It compared S5/S4 after five same-input mutating
engine actions: `recall`, `store`, `reinforce`, `forget`, and
`create_cell_link`. Immediate action outputs matched, and the states remained
equivalent for the four fixed retrieval score/rank probes. Stats and serialized
memory inspection still distinguished the counter values. This supports
transition congruence of retrieval equivalence only for that finite action and
query set; it is not whole-system operational equivalence.

Exp54 also reversed physical SQLite row order in a clone with identical
logical memory rows. The four retrieval probes and full graph output remained
equal, while the original truncated graph export selected B versus C when
their recall counts tied. An experiment-only selector ordered by
`recall_count DESC, memory_id ASC` selected B in both copies. This demonstrates
row-order sensitivity for this fixture and SQLite query plan, not across all
SQLite versions or database layouts. No upstream Raven file was changed.

The route inventory is source inspection, not exhaustive runtime tracing.
Exp54 does not test arbitrary inputs, live API/MCP behavior, concurrency,
non-dry-run consolidation, provider behavior, or agent decisions. See the
[Exp54 preregistration, report, tests, provenance, and run artifact](../experiments/exp54_raven_observational_contract/).

**OBSERVED, copied Raven snapshot plus synthetic fixture:** Exp55 applied
non-dry-run consolidation to branches differing only in C's persisted
`recall_count` while holding audit history fixed. The merged embeddings,
logical databases, and complete C/D retrieval traces matched. Its audit-weight
canary changed the merged embedding and shifted C/D scores in the predicted
directions. The result supports a bounded negative for the row counter's path
through this consolidation schedule; it does not generalize to other Raven
operations or deployed agents. Five tests passed, including a mutation check
that made the primary branches diverge when a temporary mutant read row
counters instead of audit counts. See the [Exp55 preregistration, runner,
tests, report, provenance, and JSON result](../experiments/exp55_raven_counter_consolidation/).

**OBSERVED, copied Raven snapshot plus synthetic fixture:** Exp56 held the
per-memory audit-derived counts at C=5/D=4 while changing audit event order or
query text. The three histories had different audit-log digests but identical
merge weights, embedding bytes, and fixed C/D retrieval traces. A same-total
control that changed allocation to C=4/D=5 changed the embedding and shifted
scores in the predicted directions. A deliberately order-sensitive mutation
was detected; 4 tests passed, including a full-run replay check. This supports
the count vector as a sufficient projection only for those consolidation and
retrieval outputs in the declared fixture. It does not imply full operational
equivalence. See the [Exp56 preregistration, runner, tests, report, provenance,
and JSON result](../experiments/exp56_raven_audit_projection/).

**OBSERVED, copied Raven snapshot plus synthetic fixture:** Exp57 kept the
same C=5/D=4 recall counts but assigned those events to opposite timestamp
windows. This changed pre-consolidation recency bonuses and scores; an
equalized-`last_activation` control removed the difference. After consolidation,
the merged embeddings and fixed C/D traces matched, and both new nodes had
`last_activation=0`. A zero-recency mutation removed the pre-merge contrast.
Five tests passed, including a full-run replay check. This supports a narrow
claim that the tested consolidator drops this measured recency distinction
from its merged node; audit histories remain different. See the [Exp57
preregistration, runner, tests, report, provenance, and JSON result](../experiments/exp57_raven_temporal_recency/).

**OBSERVED, copied Raven snapshot plus synthetic fixture:** Exp58 replayed
eight identical real recalls through the Exp57 post-consolidation branches.
At every step, returned IDs, score components, memory rows, and cell links
matched. The preexisting histories and every new audit-entry hash remained
different; both audit chains still passed linkage and hash-integrity checks.
A recency-state mutation changed the measured score. Five tests passed,
including a canonical full-run replay. This bounds the result to the selected
post-consolidation recall sequence; it does not establish congruence for all
Raven operations. See the [Exp58 preregistration, runner, tests, report,
provenance, and JSON result](../experiments/exp58_raven_postconsolidation_replay/).


| Script | Role |
|---|---|
| `sweep_infra.py` | Shared sweep infrastructure |

## Current state of the research

The surviving organ after amputation: **retrieval + persistent
adaptive state** (REINFORCED/NEUTRAL that changes what gets recalled).

- H8 path dependence: reproduced by stateful baseline, amplified ~2x
  by Raven machinery.
- H9 causal closure: the discrete state is the full causal antecedent
  of observed decision flips.
- H10 collective contagion: falsified.
- H10a collective resilience: fully derivable (threshold + topology +
  intervention-window dynamics).
- H11 behavioral specificity: inconclusive for equivalence (TOST
  fails at δ=30cp), but Exp28 found real deterministic context
  effects on a minority of positions (D(C,I) = 1.9x noise floor).
- H1 structural (RESONANT boost): not reproduced by retrieval-only
  baselines evaluated so far — but impossibility not shown.
- H13 minimum state: binary flag suffices; accumulation and
  persistence across queries required. Compression claims
  (Exp26) were falsified by Exp26b — no clean threshold, location
  doesn't drive the effect.

Boundary discovered: **stateless retrieval vs stateful adaptive
retrieval** — not retrieval vs memory. The minimum state is a
persistent accumulating flag; exact bit budget is noisy.

The hypothesis ledger is in `docs/HYPOTHESES.md`; full phase writeups are
in `research/PHASE*.md`.

## H14 status

H14 remains OPEN. Exp36–50 are synthetic restoration and finite-state assays;
Exp51–58 are isolated experiments against a copied Raven snapshot with
synthetic fixtures. Exp51–58 provide bounded evidence about selected Raven
operations and observables, not a deployed-agent validation or a sufficient
or minimal Raven state representation. The current vocabulary and research
map are in [`MEMORY_LAB.md`](MEMORY_LAB.md). The protocol origin and historic
Exp36/37 records remain in [`REINTRODUCTION_RESTORATION.md`](REINTRODUCTION_RESTORATION.md),
[`research/PHASE11_H14_TOY_ASSAY.md`](../research/PHASE11_H14_TOY_ASSAY.md), and
[`research/PHASE11_H14_EXP37_MEASUREMENT.md`](../research/PHASE11_H14_EXP37_MEASUREMENT.md).
