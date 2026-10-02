# Experiments index

All 23 experiments in `experiments/`, grouped by phase. Verdicts are
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

## Supporting infrastructure

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

See `docs/HYPOTHESES.md` for the hypothesis ledger and
`research/PHASE*.md` for full experimental writeups.
