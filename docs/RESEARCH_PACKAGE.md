# Remember the Seasons — Research Package

> STATUS: research complete. STOP at the transition gate. This is NOT the
> product. Implementation is NOT authorized. Awaiting maintainer review.
>
> Epistemic convention throughout: **OBSERVED** (cited to `sources/` or
> original commit), **INFERRED** (derived, not directly stated), **PROPOSED**
> (our hypothesis, untested), **UNKNOWN** (we lack evidence). No inference is
> silently promoted into a fact.

This package indexes the 12 required deliverables. Each points to the
detailed document that carries the evidence.

---

## 1. Source / provenance inventory for Raven, MNEME, STIGMERGY

See `sources/<system>/PROVENANCE.md` for each, and `README.md` §"Source material".

- **raven-memory** — `sources/raven-memory/`, snapshot of
  `https://github.com/annatchijova/raven-memory.git` @ `56df6cf` (main, clean,
  77 tracked files → 55 after image cleanup). Content sha256 recorded.
- **mneme** — `sources/mneme/`, snapshot of
  `https://github.com/annatchijova/mneme.git` @ `bde801a` (main, clean,
  45 tracked files). Content sha256 recorded. (Note: a related older repo
  `mneme_memory_mcp` and a partial `Downloads/MNEME` copy exist; canonical is
  `mneme`.)
- **stigmergy** — `sources/stigmergy/`, snapshot of
  `https://github.com/annatchijova/stigmergy.git` @ `b80a7f9` (main, one
  untracked `.aws-sam/` not exported; 147 tracked → 81 after image cleanup;
  `.env` is gitignored and absent by construction). Content sha256 recorded.

Snapshots are read-only research material. Originals were never modified.

## 2. Mechanism map

See `research/PHASE1_ARCHAEOLOGY.md` §1-4. Per-system inventories (mechanism,
location, property, determinism, state, I/O, tests, limitations, reusability)
plus a cross-system map that disambiguates storage / retrieval / ranking /
memory state / learning / provenance / authorization / causal attribution /
counterfactual / collective memory (§4). Key OBSERVED finding: the three
systems share an ancestor (raven's field mechanics); MNEME inherits them,
STIGMERGY ports MNEME's custody; they differ on determinism (float vs exact),
causality (retrieval-influence vs decision-closure), and collective memory
(STIGMERGY alone).

## 3. Dependency audit

See `research/PHASE2_PRUNING.md` §1. OBSERVED: raven core = numpy+scipy (rest
optional extras); mneme core = stdlib only; stigmergy = psycopg + CockroachDB
(heavy, justified only for multi-agent). PROPOSED research core = numpy+scipy
+ pinned embeddings; remove REST/MCP/gradio/Qwen-client; defer CockroachDB to
multi-agent experiments.

## 4. Keep / remove / reimplement recommendations

See `research/PHASE2_PRUNING.md` §2-5. Per-mechanism verdicts with the six
required questions (which hypothesis, observable property, ablatability,
falsifier). Headline PROPOSED: keep raven field+intervention, keep MNEME
custody/counterfactual/decision-closure, keep STIGMERGY recruitment only for
multi-agent; remove stylometric/spectral from core; flag STDP and rescue as
suspect (STDP likely weakest; rescue currently vacuous).

## 5. Explicit research hypotheses

See `docs/HYPOTHESES.md`. H0 (retrieval not sufficient) decomposed into H1-H7,
each with a falsifier, plus the list of valid negative outcomes.

## 6. Strong baseline plan

See `research/PHASE3_BASELINES.md`. Baseline ladder B0-B7 (flat top-k,
metadata-rerank, hybrid/reranking, propagation-only, raven full, MNEME exact,
individual mechanisms, stigmergic). Variable control (same corpus/embeddings/
context-budget/model/tasks/pinned-configs). Tasks where retrieval SHOULD win
(§3) and where dynamics MIGHT win (§4). B0 is the primary baseline; B1/B2 are
the strongest null-hypothesis challengers.

## 7. Experimental matrix

See `research/PHASE4_EXPERIMENTAL_MATRIX.md` §1. Eleven experiments E1-E11
(retrieval quality, preference replacement, contradiction resistance,
temporal validity, catastrophic interference, consolidation, causal effect on
decisions, contamination/containment, historical reconstruction, multi-agent
propagation, latency/storage/cost), each with baselines, separate metrics,
and a falsifier.

## 8. Ablation plan

See `research/PHASE4_EXPERIMENTAL_MATRIX.md` §2. Ablations remove one mechanism
from the full candidate and measure the delta on that mechanism's target
dimension. Explicit note: do NOT expect every ablation to hurt accuracy;
custody/provenance ablations are scored on auditability, not recall.

## 9. Intervention model candidates

See `research/PHASE5_INTERVENTION_MODEL.md`. Selective (S1 suppress
[implemented in raven], S2 excite, S3 link-cut, S4 cluster-silence) and
systemic (Y1 propagation depth, Y2 reinforcement/threshold, Y3 decay,
Y4 gate strictness, Y5 recruitment/cooldown). Each has target/mechanism/
duration/effect/measure/side-effects/control/counterfactual/falsifier.
Authority boundaries inherited from raven (probe ≠ stimulation ≠ learning).
No biological-equivalence claims.

## 10. Known confounders and threats to validity

See `research/PHASE4_EXPERIMENTAL_MATRIX.md` §4. Embedding variance,
hyperparameter tuning asymmetry, task-design bias, vacuous invariants
(OBSERVED: rescue fuzzer violation branch unreachable), shim-vs-substrate
(STIGMERGY on SQLite ≠ on CockroachDB), LLM variance, float determinism,
single-author conformance (MNEME's two verifiers share an author, OBSERVED
SPEC §0).

## 11. Proposed minimal architecture IF the evidence supports proceeding

See `research/PHASE2_PRUNING.md` §5. PROPOSED (not a design, to be falsified):
raven field (states+links+BFS, numpy/scipy) + MNEME exact ranking IF sealed
claims needed + raven intervention primitive + MNEME counterfactual/decision-
closure IF decision-causality tested + STIGMERGY shared-state shim IF multi-
agent tested (promoted to real substrate after validation). A valid outcome is
that the minimal core is even smaller than this.

## 12. STOP conditions

See `docs/STOP_CONDITIONS.md`. Hard STOP (do not build): H0 unsupported; no
mechanism beats metadata-rerank; causal influence vacuous; rescue vacuous and
non-discriminable. Soft STOP (re-scope): only provenance survives; only
multi-agent propagation survives; systemic interventions are just parameter
tuning; systems should remain separate. Proceed only if a sub-hypothesis
survives its falsifier, is not reproducible by B1/B2, AND the maintainer
explicitly approves.

---

## Headline findings to review (mixed epistemic levels)

> **Three corrections were applied after auditing the research package
> against the live code.** See `research/REVIEW_CORRECTIONS.md` for the full
> audit. Summary: (1) the rescue invariant is not "vacuous" — it is true by
> construction, but functionally a post-hoc filter (rescue runs after BFS,
> no re-propagation), so the research question is whether it differs from a
> metadata filter, not whether the fuzzer can violate it; (2) B1/B2 were too
> vague — B1 is now concretized as raven's scoring formula minus dynamics
> terms with the same metadata, and B2' (B2+B1) is the strongest adversary;
> (3) H7's falsifier was an observation, not a falsifier — it is now a real
> ablation test, and H2's falsifier is now concrete.

- **OBSERVED:** raven already implements a falsifiable selective intervention
  model (retrieval causal influence) with honest scope (retrieval, not agent
  answer). This is the most directly research-ready mechanism.
- **OBSERVED:** MNEME makes raven's ranking bit-reproducible (Fraction, sqrt
  eliminated via t²/n) and adds decision-causal closure + counterfactual
  worlds. Its contribution is verifiability, not recall quality (INFERRED —
  needs E1/E5 to confirm).
- **OBSERVED:** STIGMERGY is the only system with collective memory
  (stigmergic propagation); its value is inert for single-agent studies and
  its CockroachDB dependency is heavy.
- **OBSERVED (corrected):** the rescue rule is true by construction (not
  vacuous), but the rescue loop runs after BFS (`memory_engine.py:1718-1730`),
  so the rescued cell re-enters scoring but NOT propagation. It is
  functionally a post-hoc filter. The fuzzer's vacuity (RT-1,
  `intervention.py:221-232`) is a symptom of this, not the research finding.
  The corrected H7 tests whether the rescue differs from a metadata filter.
- **INFERRED:** the strongest null-hypothesis challenger is B2' (B2 hybrid
  retrieval + B1 metadata reranking). If dynamics cannot beat B2', H0 is
  dead. The discriminating question for B1 vs dynamics is SET COMPOSITION
  (does propagation change who gets returned), not just ranking.
- **UNKNOWN:** whether any composition of the three systems produces a
  property no single system produces alone. Not yet testable without the
  experimental matrix.

## Transition gate

Pre-clinical + extended + statistical trials authorized and completed.
See `research/PHASE6_TRIAL_RESULTS.md`, `research/PHASE6B_EXTENDED_TRIALS.md`,
and `research/PHASE7_STATISTICAL_TRIALS.md` for full results.

### Trial verdicts (OBSERVED)

| Experiment | Verdict | Key finding |
|---|---|---|
| Exp1 (small field) | FALSIFIED | Propagation doesn't change set in small/dense fields |
| Exp1b (large field) | SURVIVES | Propagation brings in X that B0 AND B1 miss |
| Exp2 (rescue) | FALSIFIED | Rescue == post-hoc filter, bit-identical (A == C) |
| Exp3 (intervention) | SURVIVES (weak) | Suppress != remove, but only in score magnitudes |
| Exp4 (B2' challenge) | SURVIVES | No B2' variant recovers X (proper two-stage) |
| Exp5-A (block reinf) | SURVIVES | Path dependence: divergence GROWS after washout |
| Exp5-B (STDP scale) | FALSIFIED | Slider: no path dependence from STDP scaling |
| Exp6-BoW (real emb) | SURVIVES | Generalizes to bag-of-words (positive cosine) |
| Exp6-Gauss (no struct) | FALSIFIED | RESONANT boost can't help orthogonal memories |
| Exp7 (robustness) | SURVIVES | Robust across seeds/sizes/durations/intensities/dists |
| Exp8 (dose-response) | SURVIVES | Clean monotonic dose-response (0% to 100%) |
| Exp9 (washout curve) | PERSISTENT (observed) | No convergence in 130 steps; not proven permanent |
| Exp10 (cross-domain) | WEAK | Off-target leak (20%); NOT an orthogonal behavioral control |
| Exp11 (downstream) | WEAK | 2.3% decision flip rate (real but modest) |
| Exp12 (MNEME closure) | WEAK | 56.5% per-instance causal closure (CF0) |
| Exp13 (STIGMERGY) | FALSIFIED | Exp13 was tautological; Exp16 corrected |
| Exp14 (causal replay) | SURVIVES | CF2a: 100% closure with state-only replay |
| Exp15 (factorial) | DECOMPOSED | De-reinf active; shared state primary transport |
| Exp16 (provenance) | FALSIFIED | Per-agent provenance kills collective effect |
| Exp17 (resilience) | SURVIVES | Collective memory amortizes partial perturbations |
| Exp18 (chess) | PIPELINE CHECK | Chess quality identical (0.0000) — pipeline integrity, NOT behavioral specificity |
| Exp19 (stateful baseline) | BASELINE REPRODUCES | Retrieval + state suffices for H8; Raven amplifies ~2x |
| Exp20 (chess behavioral) | INCONCLUSIVE | Preliminary evidence consistent with specificity; n=1 seed, no equivalence test |
| Exp24 (chess TOST) | INCONCLUSIVE | Preregistered + TOST; CI [-37.9,+10.1] crosses δ=30cp; 87% move agreement, mixed-sign diffs |
| Exp28 (variance decomp) | MARGINAL SIGNAL | D(C,I)=0.129 vs noise floor 0.067 (1.9x); deterministic context effects exist on a minority of positions |
| Exp21 (threshold sweep) | MOSTLY ALGEBRAIC | k* = N-T for T=1,2; resilience is mechanical, not emergent |
| Exp22 (topology prediction) | MOSTLY DERIVABLE | Per-memory topology predicts threshold (8/9); magnitude underestimated ~30-70% |
| Exp23 (residual decomposition) | DERIVABLE | 100% of unexplained flips are late bloomers; no emergent mechanism |
| Exp25 (state amputation) | SURVIVES | Smallest tested sufficient state: binary accumulating persistent flag |
| Exp26 (state compression) | FALSIFIED | Exp26b: no clean threshold; location claim not confirmed — noisy/non-monotonic |
| Exp26b (falsification) | COMPLETE | No threshold; location claim falsified; scattered >= coherent |
| Exp27 (why 7 vs 8) | OBSERVED | Late-flagged group + feedback loop; partition accident, not bit count |
| Exp29 (feedback mechanism) | WEAK | Top-1 flips 20% of flag-diff steps; ng=7 grows slowly, ng=11/25 self-correct |
| Exp30 (mediator intervention) | CONFIRMED | Rescue=0.0000 (necessary), induce=21/24 (sufficient), top1_swap=0.029 (channel mediates) |

### Hypothesis scoreboard

| Hypothesis | Verdict | Strength |
|---|---|---|
| H1 (dynamics over B1) | SURVIVES | bounded (positive cosine required) |
| H2 (intervention vs removal) | SURVIVES | weak (scores only, not set/order) |
| H7 (rescue is post-hoc) | FALSIFIED | strong |
| H8 (path dependence) | SURVIVES | strong (robust, dose-dependent, persistent in observed horizon) |
| H8a (domain specificity) | WEAK | leaks across domains; NOT an orthogonal behavioral control |
| H8b (downstream impact) | WEAK | 2.3% decision flips (not proven to be a lower bound) |
| H9 (MNEME closure) | SURVIVES | CF2a: 100% closure with state-only replay (upgraded from WEAK) |
| H10 (STIGMERGY collective) | FALSIFIED | Exp13 was tautological; Exp16 corrected with per-agent provenance |
| H10a (collective resilience) | DERIVABLE | Exp21/22/23: threshold rule + topology + dynamics fully explain; no emergent mechanism |
| H11 (chess orthogonal) | INCONCLUSIVE | Exp24: preregistered TOST, CI crosses δ=30cp. Exp28: D(C,I) exceeds noise 1.9x — real context effects on a minority of positions, mixed signs |
| H12 (stateful retrieval suffices) | SURVIVES | NEW (Exp19): retrieval + state reproduces H8; Raven amplifies ~2x but not necessary |
| H13 (minimum sufficient state) | SURVIVES (corrected) | Exp25: binary flag suffices; Exp26b: no clean threshold — noisy curve |
| H3-H6 | PARTIALLY TESTED | minimal MNEME/STIGMERGY only; full systems untested |

### Key findings

1. **Propagation changes set composition** (H1): the RESONANT boost is a
   graph-structural property that B1/B2' cannot reproduce. Survives the
   B2' challenge. Generalizes to realistic embeddings when cosine is
   positive. Does NOT work for orthogonal memories (negative cosine).

2. **Reinforcement blocking produces robust path dependence** (H8):
   the intervention changes which memories get consolidated (REINFORCED).
   After washout, the trajectory diverges and the divergence is
   PERSISTENT (doesn't decay over 130 steps). The effect is robust
   across 81 configurations (53% show divergence), has a clean
   dose-response (monotonic 0% to 100%), and the negative control passes
   consistently (nearest_diff ~0.0003).

3. **STDP scaling is a slider** (H8 falsifier for STDP): scaling STDP
   potentiation alone doesn't change the result set. The active
   ingredient is reinforcement blocking (state consolidation), not
   synaptic plasticity.

4. **Rescue is a post-hoc filter** (H7): definitively falsified.
   Bit-identical to a metadata filter.

5. **The effect leaks across domains** (H8a): a domain-A intervention
   produces 56% washout set_diff in domain A but 20% in domain B. The
   graph structure creates cross-domain off-target effects. The
   nearest-memory probe passes in both domains — the leak is in
   lower-ranked memories, not the top match. The drug has off-target
   effects.

6. **The operational impact is modest** (H8b): only 2.3% of decisions
   flip post-washout. The memory change is real but rarely changes
   what the agent would DO in this simple weighted-vote model.

7. **MNEME causal closure upgraded to 100%** (H9, Exp14): restoring
   ONLY the REINFORCED/NEUTRAL state from control and re-running the
   recall dynamics restores the control decision in ALL cases (CF2a:
   100%). The memory state is the complete causal antecedent. STDP and
   explicit links are not needed. CF0 (set membership) only achieved
   56.5% because score-only flips need the state, not just the set. See
   `research/PHASE9_CAUSAL_RESILIENCE.md`.

8. **STIGMERGY collective path dependence FALSIFIED** (H10, Exp16): the
   Exp13 result was tautological. The de-reinforcement set
   mem.state = NEUTRAL globally, erasing B/C's contributions too. With
   per-agent provenance (zero ONLY A's contributions), the collective
   effect disappears (B: 0.0025, C: 0.0015). The Exp13/15 effect was
   "wrote a global perturbation in a shared structure and others saw
   it" — not genuine stigmergic transmission. See
   `research/PHASE9_CAUSAL_RESILIENCE.md`.

9. **Collective resilience is fully derivable** (H10a, Exp21/22/23):
    Exp17 found k* = N-1. Exp21 varied the threshold T and found
    k* = N-T for T=1,2 — the resilience follows the threshold rule.
    Exp22 showed per-memory contributor topology predicts the
    threshold (8/9 configs, 91% precision). Exp23 showed the
    residual is 100% "late bloomers" — memories that crossed the
    threshold during the intervention window in control but not in
    intervention, due to direct contributor loss (present in 141/142,
    99.3%) or behavioral cascade (present in 48/142, 33.8%). No
    emergent mechanism needed. See `research/PHASE10_AMPUTATION.md`.

10. **Exp18 is a pipeline check, not behavioral specificity** (H11):
    Chess quality is identical (0.0000) but this is expected by
    construction (independent task, same seed). `material + mobility`
    is NOT ground truth of optimal play. For true behavioral
    specificity, we need a common agent (LLM) behind both arms with
    Stockfish/tablebase ground truth (Exp20, owed). Frankenstein did
    not hang the queen, but mainly because we haven't given
    Frankenstein a queen yet. See `research/PHASE9_CAUSAL_RESILIENCE.md`.

11. **Path dependence does NOT require Raven — stateful retrieval
    suffices** (H12, Exp19): the amputation knife. A baseline with
    retrieval + persistent adaptive state (NO graph, NO STDP, NO
    rescue) reproduces path dependence (washout 0.0112, 11 flips).
    Raven amplifies it ~2x (washout 0.0214, 23 flips) but is not
    necessary. The surviving organ is stateful retrieval. The causal
    mechanism is the same in both (CF2a 100% closure). See
    `research/PHASE10_AMPUTATION.md`.

12. **Behavioral chess assay is INCONCLUSIVE** (H11, Exp20):
    LLM (hermes3:8b) + Stockfish 16 (depth 15). Only 1/5 seeds
    produced sufficient memory divergence (seed 7, mem_diff=0.0500).
    For that seed, no chess-quality difference was observed. This is
    consistent with behavioral specificity but does NOT establish it
    — n=1 informative condition, no equivalence test. A proper
    version needs preregistered divergent conditions and an
    equivalence test (TOST) with a predefined margin. See
    `research/PHASE10_AMPUTATION.md`.

13. **The minimum sufficient state is a persistent accumulating
    binary flag** (H13, Exp25): binary REINFORCED/NEUTRAL suffices
    for H8 (0.0112, 11 flips). Scalar amplifies ~4x. Accumulation
    beyond 1 step required. Permanence not required (decay changes
    mechanism to state wipe). Persistence across queries required.
    Exp26's compression claims were FALSIFIED by Exp26b: no clean
    bit-budget threshold (noisy/non-monotonic curve), and "semantic
    coherence" is not the driver (scattered assignments produce
    comparable or larger divergence). What survives: some persistent
    binary state is necessary (0 bits = 0); the exact budget is
    noisy and assignment-dependent.

### Next gate decision

STOP. Report to maintainer. Do not implement Remember the Seasons. Do not
add Nebius/NVIDIA integration. Await explicit approval for next phase.

Potential next steps (if authorized):
1. Test path dependence with more complex decision models (multi-way,
   sequential, threshold-dependent) — may show higher flip rates
2. Test whether domain-specific graph partitioning reduces cross-domain
   leak
3. Full MNEME implementation (SQLite, sealed receipts, trust propagation)
   — the minimal custody chain only covers set-difference flips; Exp14's
   CF2a achieves 100% but is not integrated into the custody chain
4. Test collective resilience with weighted contributions (not binary
   any-agent-keeps-REINFORCED) — may show different threshold dynamics
5. Test persistence over much longer trajectories (1000+ steps)
6. Test the RESONANT boost boundary condition: is the positive-cosine
   requirement fundamental or an artifact of the formula?
7. Test whether the chess agent USING the memory field to inform moves
   would show intervention effects (conflates memory and chess, but
   more ecologically valid)
