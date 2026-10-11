# Research hypotheses (PROPOSED — to falsify)

The overarching hypothesis under investigation:

> **H0:** Retrieval is not necessarily a sufficient model of persistent agent
> memory. Where retrieval stops being sufficient, additional mechanisms produce
> measurable properties that retrieval alone does not represent.

The job is to **falsify** H0, not confirm it. The null is "retrieval
(competently done, with reasonable metadata) is sufficient for the tested
properties." Each sub-hypothesis is independently falsifiable; H0 survives only
if at least one sub-hypothesis survives its falsifier.

## Sub-hypotheses

- **H1 — dynamics over retrieval (raven mechanisms):** ternary states +
  RESONANT/INHIBITORY links + BFS propagation produce contradiction resistance,
  preference replacement, and forgetting properties that flat top-k + metadata
  rerank (B1) does not. **Falsifier:** B1 reproduces collapse-around-truth and
  preference replacement using only metadata flags.

- **H2 — causal attribution requires intervention (raven):** suppressing a
  memory produces a non-zero retrieval causal influence Δ that a retrieval-only
  system cannot compute. **Falsifier:** Δ is always 0, OR removing the target
  memory from the corpus and re-running B0 top-k produces the same result-set
  delta as the intervention (the intervention is then equivalent to "retrieve
  without this memory," a retrieval operation, not a distinct causal probe).

- **H3 — decision causality requires closure (MNEME):** attributing a decision
  to the memories that actually fed it requires recall→decision closure
  (receipts + DECISION_USED_MEMORY), which retrieval alone does not provide.
  **Falsifier:** a retrieval-only system can answer "which memories caused
  this decision" as accurately as the closure layer.

- **H4 — containment requires a gate, not a filter (MNEME):** preventing a
  tainted memory from perturbing clean memories' rankings requires a graph-gate
  (both endpoints CLEAN to traverse), not just a serve-time filter.
  **Falsifier:** a serve-only metadata filter matches the graph-gate on
  clean-memory ranking under contamination.

- **H5 — exactness is a verifiability property, not a recall property (MNEME):**
  exact Fraction ranking changes *verifiability* (bit-reproducible receipts)
  but not *recall quality* vs float ranking. **Falsifier:** exact ranking
  changes recall@k/nDCG measurably (either direction).

- **H6 — collective memory requires shared state (STIGMERGY):** in a
  multi-agent setting, experience propagates to late agents through shared
  stigmergic state in a way per-agent retrieval cannot reproduce. **Falsifier:**
  per-agent B0 retrieval matches stigmergic propagation on late-agent success.
  Only testable on a real shared substrate (shim must be validated first).

- **H7 — rescue rule is a post-hoc filter, not a propagation mechanism
  (raven):** the rescue rule's effect on the result set is indistinguishable
  from a post-hoc metadata filter that adds REINFORCED memories back if they
  were excluded as INHIBITED. The rescue loop runs after BFS
  (`memory_engine.py:1718-1730`), so the rescued cell's links are NOT
  re-traversed — it re-enters scoring but not propagation. **Falsifier:**
  ablate the rescue loop and replace it with a post-scoring filter that adds
  REINFORCED memories back to results if excluded as INHIBITED. If outcomes
  (result set + ranking) are identical across all test queries, the rescue
  rule is a post-hoc filter in disguise and provides no property beyond what
  B1 can do with metadata. If they differ, the rescue loop's modification of
  `inhibited_cells` before scoring has a propagation effect worth
  investigating.

  **Experimental verdict (OBSERVED): FALSIFIED.** A == C bit-identically
  (set, order, scores). The rescue rule is a post-hoc metadata filter.
  See `research/PHASE6_TRIAL_RESULTS.md` Exp2.

- **H8 — reinforcement consolidation produces path dependence (raven):**
  a systemic intervention that blocks reinforcement during a temporal
  window changes which memories get consolidated (REINFORCED state).
  After the intervention is removed (washout), the different consolidated
  state produces different recall results — the trajectory diverges and
  the divergence grows. This is path dependence: the intervention altered
  the memory system's future state, not just its current output. **Falsifier
  (slider test):** if post-washout recall converges back to the control
  trajectory (same result sets, same scores), the intervention was a slider
  — parameter tuning with extra steps, not genuine pharmacology. If
  post-washout recall diverges, the intervention changed consolidation and
  the system follows a different trajectory. **Negative control:** the
  nearest-memory probe (closest match by cosine) should be unaffected —
  if the intervention degrades this, it's a general poison, not a
  memory-specific drug.

  **Experimental verdict (OBSERVED): SURVIVES.** Blocking reinforcement
  produces 6/30 set differences after washout (growing from 1/30 during
  intervention). STDP scaling alone is a slider (0 differences). Negative
  control passes (0/30 nearest differences). See
  `research/PHASE6B_EXTENDED_TRIALS.md` Exp5.

## Pre-clinical trial verdicts (OBSERVED)

| Hypothesis | Verdict | Strength | Experiment |
|---|---|---|---|
| H1 (dynamics over B1) | SURVIVES | bounded | Exp1b, Exp4, Exp6-BoW |
| H2 (intervention vs removal) | SURVIVES | weak | Exp3 |
| H7 (rescue is post-hoc) | FALSIFIED | strong | Exp2 |
| H8 (path dependence) | SURVIVES | strong | Exp5-A, Exp7, Exp8, Exp9 |
| H8a (domain specificity) | WEAK | leaks | Exp10 |
| H8b (downstream impact) | WEAK | 2.3% flips | Exp11 |

H1 survives the B2' challenge (Exp4): no retrieval-only variant recovers
X. Generalizes to bag-of-words embeddings (Exp6-BoW) when cosine is
positive. Does NOT generalize to orthogonal memories (Exp6-Gauss) — the
RESONANT boost requires positive cosine.

H2 survives weakly: suppression != removal, but the difference is in
score magnitudes (graph topology), not in set or order (for non-seed
targets).

H7 is definitively falsified: rescue == post-hoc filter, bit-identical.

H8 (path dependence) is confirmed as robust (Exp7: 53% of configs show
divergence across seeds/sizes/durations/intensities/distributions),
dose-dependent (Exp8: clean monotonic 0% to 100%), and persistent
within the observed horizon (Exp9: no convergence in 130 steps of
washout; whether this is permanent or merely very long-lived requires
1000+ step testing). The negative control passes consistently
(nearest_diff ~0.0003). STDP scaling alone is a slider (no path
dependence). See `research/PHASE7_STATISTICAL_TRIALS.md`.

H8a (domain specificity): the path dependence is NOT perfectly
domain-specific. A domain-A intervention produces 56% washout set_diff
in domain A but 20% in domain B (Exp10). This is a cross-domain /
off-target memory-domain effect, NOT an orthogonal behavioral control.
The nearest-memory probe passes in both domains (0% nearest_diff) —
the leak is in lower-ranked memories, not the top match. A true
orthogonal behavioral control (independent task with external ground
truth, e.g., chess positions) is still owed.

H8b (downstream impact): the memory change produces only 2.3% decision
flips post-washout (Exp11). The effect is operationally real but modest
in this simple weighted-vote decision model. We do not know whether
2.3% is a lower bound — a more complex decision model could amplify,
attenuate, or eliminate the differences.

H3, H4, H5, H6 remain untested in the full MNEME system. Exp12 tested a
minimal MNEME-style custody chain for per-instance causal closure (see
below). Full MNEME custody/counterfactual verification (with SQLite,
sealed receipts, trust propagation) was not implemented.

### MNEME causal closure (Exp12, OBSERVED)

A minimal MNEME-style custody chain (per-memory, append-only, hash-linked)
was implemented on top of the minimal raven engine. For each decision
that flipped between control and intervention, a counterfactual was run:
restore the missing memories from control's evidence base to the
intervention's, recompute the decision.

Results: 56.5% of post-washout flips achieved causal closure (the
counterfactual restored the control's decision). The remaining 43.5%
were score-only flips (same evidence base, different scores) that the
simple counterfactual cannot capture.

Verdict: WEAK. The custody chain provides per-instance causal claims
for set-difference flips but not for score-only flips. A complete
counterfactual would need to restore both the memory set AND the scores.

### STIGMERGY collective path dependence (Exp13, OBSERVED then CORRECTED)

Exp13 initially reported collective path dependence (B 17.2%, C 16.6%
washout divergence). However, Exp16 (per-agent provenance) FALSIFIED
this: the effect was tautological. The de-reinforcement set
mem.state = NEUTRAL globally, erasing B/C's contributions too. When we
zero ONLY A's contributions (not B/C's), the collective effect
disappears (B: 0.0025, C: 0.0015 — essentially zero).

Exp15 (factorial decomposition) further showed:
- Blocking alone produces ZERO divergence (de-reinforcement is the
  active ingredient)
- Shared state is the primary transport (somewhat tautological)
- Shared STDP is NOT a transport channel (AB-noSTDP = AB)
- The residual in AB-private-state cannot be attributed to STDP
- Duration 30 vs 40 doesn't matter

Verdict: FALSIFIED. The Exp13 "collective path dependence" was an
artifact of global state mutation.

### Collective resilience (Exp17, OBSERVED — NEW property)

Exp16's per-agent provenance revealed a different property: the
collective memory amortizes partial perturbations. With N agents,
intervening a fraction of them produces near-zero divergence until
the fraction approaches 1.0. The threshold scales with N:

- N=2: 1 agent (50%) -> small divergence (0.0170)
- N=5: 3 agents (60%) -> near zero (0.0037)
- N=10: 7 agents (70%) -> near zero (0.0004)
- All N: ALL agents -> full divergence (0.15-0.16)

This is collective resilience: the non-intervened agents'
contributions keep memories REINFORCED, compensating for the
intervened agents' lost contributions.

Verdict: SURVIVES. A genuine collective property, distinct from the
falsified "collective path dependence." The reparametrized experiment
(k_intervened directly, not fractions) shows the threshold is at
k=N-1 (all but one agent), not a fixed fraction:
- N=2: threshold at k=1 (50%)
- N=5: threshold at k=4 (80%)
- N=10: threshold at k=9 (90%)

With 2+ non-intervened agents, the effect is zero or near-zero. The
collective memory is resilient until only 1 agent is left
non-intervened.

### MNEME causal-state replay (Exp14, OBSERVED)

Exp12's 56.5% closure rate (CF0: restore set membership) was upgraded
by Exp14's deeper counterfactuals:

- CF0 (set membership): 56.5%
- CF1 (set + scores): 100% [partially circular]
- CF2a (state only, re-run dynamics): 100% [proper causal CF]

Restoring ONLY the REINFORCED/NEUTRAL state from control and
re-running the recall dynamics restores the control decision in ALL
cases. The memory state is the complete causal antecedent. STDP and
explicit links are not needed.

Verdict: SURVIVES (upgraded from WEAK). The causal chain is:
intervention -> memory states -> state multiplier -> scores ->
decision.

### Orthogonal behavioral control — chess (Exp18, PIPELINE CHECK)

Exp18 used python-chess for move quality evaluation. However, this is
a pipeline negative control, NOT a behavioral off-target assay:

1. The chess task is completely independent of the memory field (same
   random seed for move selection in both arms), so identical chess
   quality is almost expected by construction.
2. `material + mobility` is NOT ground truth of optimal play. For true
   ground truth we need Stockfish (fixed version, fixed nodes/depth) or
   Syzygy tablebase positions.
3. There is no general chess-playing capability to poison —
   Frankenstein is just the memory engine. For a real off-target
   cognitive test, we need a common agent (LLM) behind both arms with
   the intervention as the only difference.

Results: chess quality is identical (0.0000 difference). This confirms
pipeline integrity (no general computation corruption) but does NOT
demonstrate behavioral specificity.

Verdict: PIPELINE CHECK PASS. Behavioral specificity still owed (Exp20).
Frankenstein did not hang the queen, but mainly because we haven't
given Frankenstein a queen yet.

### Stateful retrieval baseline — the amputation (Exp19, OBSERVED)

Exp14 found that the ENTIRE causal effect of decision flips is
reproduced by restoring ONLY the REINFORCED/NEUTRAL state. This
raised the question: does path dependence need Raven at all?

The stateful retrieval baseline has:
- vector retrieval (cosine similarity, top-k)
- per-memory reinforcement state (REINFORCED/NEUTRAL)
- same state transition rule and multiplier
- same intervention and washout

It does NOT have: graph propagation, RESONANT boost, STDP, rescue,
explicit links, recency.

Results (20 seeds):
- Baseline washout: 0.0112 (11 flips)
- Raven washout: 0.0214 (23 flips)
- Both CF2a closure: 100%

Verdict: BASELINE REPRODUCES — Raven AMPLIFIES (~2x). Path dependence
is a property of retrieval + persistent adaptive state, NOT of
Raven's machinery. The surviving organ is stateful retrieval.

### Behavioral chess assay with LLM (Exp20, OBSERVED — INCONCLUSIVE)

Real behavioral test: LLM (hermes3:8b, temperature=0) receives
recalled memories + chess position in context. Stockfish 16 (depth
15) evaluates move quality. The probe is memory-irrelevant (chess
positions don't write to memory).

Results (5 seeds, 20 positions each):
- Only 1/5 seeds produced sufficient memory divergence (seed 7,
  mem_diff=0.0500)
- For that seed, chess quality was identical (0.0000 difference)

INCONCLUSIVE — preliminary evidence consistent with specificity.
n=1 informative condition. A result of 0.0000 does NOT establish
equivalence — an equivalence test (TOST) with a predefined margin
delta would be needed to claim "chess quality is preserved."

The post-hoc seed selection (selecting seeds that produce
divergence) is appropriate for exploration but not for a final
experiment. A proper version should preregister conditions where
control and intervention are known to produce divergent states
before looking at chess performance.

### Reinforcement threshold sweep (Exp21, OBSERVED)

Exp17 found k* = N-1 (all but one agent intervened needed for
divergence). Is this emergent or algebraic?

Test: vary the reinforcement threshold T (distinct contributors
needed for REINFORCED). If algebraic, k* = N - T.

Results:
- T=1: k* = N-1 exactly (N=3→2, N=5→4, N=8→7)
- T=2: k* = N-2 exactly (N=3→1, N=5→3, N=8→6)
- T=3: k* < N-T (observed lower than predicted because
  contribution distribution is sparse)

Verdict: MOSTLY ALGEBRAIC. The "collective resilience" is the
algebraic consequence of the reinforcement threshold rule for low
T. For high T, the transition is earlier than predicted because
sparse contributions make the threshold fragile.

### Per-memory topology decomposition (Exp22, OBSERVED)

Exp22 decomposed the aggregate curve into per-memory predictions:
for each memory, track its contributor set before intervention,
predict which memories flip given the intervened set, and compare
predicted vs observed recall divergence.

Results:
- Flip prediction: 91% precision, 71% recall (topology predicts
  most flips but dynamics amplify during intervention)
- Threshold prediction: 8/9 configs match (predicted k* from
  topology vs observed k*)
- Predicted divergence underestimates observed by ~30-70%
- T=3 residual explained by sparse contributor topology: few
  memories have 3+ contributors, so each flip is disproportionately
  impactful

Verdict: MOSTLY DERIVABLE. The "collective resilience" is derivable
from per-memory contributor topology + the reinforcement threshold
rule. The apparent emergence is an artifact of aggregating over a
heterogeneous contributor distribution.

### Residual decomposition (Exp23, OBSERVED)

Exp22's static topology prediction missed ~29% of flips (71%
recall). Exp23 decomposed the false negatives (F_obs \ F_pred)
with full per-step logging.

Key structural fact: in this model, a memory with |C_m(39) \ I| >= T
can NEVER flip (non-intervened contributions are never removed).
Therefore every false negative must be a "late bloomer": c_m(39) < T.

Results (142 false negatives):
- 100% are late bloomers (c39 < T)
- Direct loss present (A1): 141/142 (99.3%)
- Cascade present (A2): 48/142 (33.8%)
- A1 only: 94 (66.2%); A2 only: 1 (0.7%); both: 47 (33.1%)
- Unexplained: 0

Verdict: DERIVABLE DYNAMICALLY. Every unexplained flip is a late
bloomer explained by contributor loss during the intervention
window. Direct contributor loss is nearly universal (141/142,
99.3%); cascade effects co-occur in 48/142 (33.8%), but pure
cascade accounts for only 1/142 (0.7%). The cascade is real but
small — it does not rescue H10. No emergent mechanism needed.

### Minimum sufficient state (Exp25, OBSERVED)

Exp19 found that retrieval + binary adaptive state suffices for H8.
Exp25 dissected "state" factorially along three axes:

  DISCRETENESS:  binary vs scalar magnitude
  HISTORY:       accumulates vs last-touch only
  PERSISTENCE:   permanent vs decays vs reset-per-query

Results (20 seeds, washout set_diff / flips):

```
binary     0.0112   11 flips   (Exp19 baseline)
scalar     0.0496   43 flips   (magnitude amplifies ~4x)
last_only  0.0012    1 flip    (accumulation required)
decay      0.2476  182 flips   (state wipe, not freeze)
reset      0.0000    0 flips   (inert without carry-over)
stateless  0.0000    0 flips   (B0 sanity)
```

Verdict: the minimum sufficient state is a persistent accumulating
flag per memory — as little as 1 bit, updated on recall. Accumulation
beyond 1 step is required. Permanence is NOT required (decay shows
more divergence via a different mechanism: state wipe + rebuild).
Persistence across queries is required. CF closure is 100% across
all variants that produce flips.

### State compression (Exp26, OBSERVED)

Exp25 found that 1 bit per memory suffices. But 100 memories = 100
bits of history. How much persistent information is required?

Compress the state vector by sharing flags across groups:

```
Groups   Bits   Washout  Flips
  100    100     0.0112     11
   50     50     0.0068      4
   25     25     0.0188     10
   10     10     0.0206      2
    5      5     0.0000      0
    1      1     0.0000      0
    0      0     0.0000      0
```

Initial interpretation (premature): threshold at ~10 bits, contiguous
> hash.

**Exp26b falsification:**
- Fine-grained sweep (5-12, 30 seeds): NO clean threshold. Present
  at {6,7,11,15,25,50,100}, absent at {5,8,9,10,12,20}. Non-monotonic
  and noisy.
- index_contiguous on SHUFFLED field (scattered geometry) produces
  MORE divergence than on ordered field (0.0228 vs 0.0140 at 10
  groups). "Semantic coherence" is NOT the driver.
- sha256 (deterministic scatter) produces MORE divergence than
  angular at 10 groups (0.0297 vs 0.0140).
- The Exp26 "contiguous > hash" contrast was an artifact of unstable
  Python hash() + coarse sampling.

Verdict: the Exp26 interpretation was premature. No clean threshold.
Some persistent binary state is necessary (0 bits = 0), but the
compression curve is noisy and assignment-dependent. The "location
matters" claim is falsified — scattered groups produce comparable
or larger divergence at some budgets.

### Why 7 groups works and 8 doesn't (Exp27, OBSERVED)

Exp27 traced the ng=7 vs ng=8 difference query-by-query:

```
                        ng=7       ng=8
mean washout            0.0805     0.0049
total flips                24          3
mean late flags (40-70)   0.23       0.03
seeds w/ divergence        6          1
feedback events             83          0
```

Mechanism: a group that stays unflagged through step 39 is the
causal substrate — control flags it during the intervention window,
intervention can't. Post-washout, flag difference → recall
difference → different groups reinforced → flag sets diverge
further (feedback loop).

The 7-vs-8 difference is a partition accident: at ng=8, the
boundaries land such that almost no group stays unflagged at
step 39. No substrate → no divergence. It is not a property of
"8 bits"; it is this particular partition's early saturation.

Verdict: feedback loop confirmed (83 events at ng=7). The noisy
Exp26b curve is a lottery of late-flagged groups — same structural
phenomenon as Exp23's late bloomers, at the group level.

### H11 done properly (Exp24, INCONCLUSIVE)

Exp20 was inconclusive (n=1 seed, no equivalence test). Exp24
preregistered the full design before any chess evaluation:

- Candidate seeds 0..15; calibration gate mem_diff >= 0.02
- 15 fixed positions (same FENs both arms), hermes3:8b temp=0
- Stockfish 16 depth 15 ground truth; metric = regret (cp)
- Equivalence margin delta = 30 cp; TOST alpha = 0.05
- Sham: same context twice (noise floor)

Results: 3/16 seeds selected (2, 7, 11). Sham 14/15 (1cp noise).
Move agreement 39/45 (87%). Nonzero diffs have mixed signs: +1,
+32, -20, -41, -639, +41. Mean -13.9 cp, 90% CI [-37.9, +10.1],
TOST p=0.133.

Verdict: INCONCLUSIVE — CI crosses -30cp. Most positions identical;
nonzero diffs have mixed signs; no consistent directional
degradation was observed. One -639 outlier prevents equivalence at
delta=30. Resolution requires more power under the SAME protocol —
widening delta or filtering positions post hoc would move the
goalposts.

### Variance decomposition (Exp28, OBSERVED)

Does D(C,I) exceed the LLM's own stochasticity? 4 reps per
condition per position, 3 seeds, 15 FENs, 360 calls:

```
D(C,C) = 18/270 = 0.067   <- LLM noise
D(I,I) = 15/270 = 0.056   <- LLM noise
D(C,I) = 93/720 = 0.129   <- noise + context effect
ratio = 1.94x
```

Per-position detail separates noise from signal:
- Marginal positions (e.g., pos 14): internally unstable in BOTH
  conditions (cc=3/6, ii=3/6) — pure nondeterminism.
- Real context effects (pos 8 seed 11): deterministic within each
  condition (cc=0/6, ii=0/6) but different between (ci=16/16).
  The Exp24 -639 outlier is a deterministic context effect, not
  noise.

Verdict: MARGINAL SIGNAL — the memory context causally affects a
minority of chess decisions beyond LLM stochasticity, in mixed
directions. H11 remains inconclusive for equivalence.

## Valid negative outcomes (any is a successful result)

- RAG (B0/B1/B2) is sufficient for most tested properties.
- Only one raven mechanism matters; the rest are overhead.
- MNEME improves provenance but not memory performance.
- STIGMERGY is useful only for multi-agent experiments and should not enter
  the single-agent core.
- "Pharmacological" systemic intervention is merely parameter tuning and adds
  no research contribution.
- The three systems should remain separate.
- A very small new core is sufficient.
- The overall premise (H0) remains unsupported.

## Proposed follow-up hypothesis (not registered)

**H14 — Reintroduction does not necessarily restore causal function.**
Re-exposure, intrinsic-state restoration, incident-link restoration, and
relearning may produce different causal-influence vectors after functional
absence; restoring the target and its links may still fail to match the
no-absence trajectory. H14 remains PROPOSED and unregistered. Exp36 is retained as a historical
toy assay with known measurement limitations; Exp37 adds a separate
signed-score instrument check with frozen A-incident links. Neither evaluates
Raven/MNEME. The operational definitions and open decisions are in
[`REINTRODUCTION_RESTORATION.md`](REINTRODUCTION_RESTORATION.md); see
[`PHASE11_H14_TOY_ASSAY.md`](../research/PHASE11_H14_TOY_ASSAY.md) and
[`PHASE11_H14_EXP37_MEASUREMENT.md`](../research/PHASE11_H14_EXP37_MEASUREMENT.md)
for the two toy assay records.
