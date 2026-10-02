# Phase 6b — Extended trial results (Exp4-6)

> Three additional experiments authorized after the pre-clinical trials.
> Exp4: B2' challenge. Exp5: temporal washout. Exp6: real embeddings.
> All experiments use the same minimal raven-faithful engine.
>
> Epistemic status: OBSERVED (actual runs).

---

## Summary

| Experiment | Question | Verdict | Strength |
|---|---|---|---|
| Exp4 (B2' challenge) | Can strongest retrieval-only recover X? | SURVIVES | strong |
| Exp5-A (block reinforcement) | Path dependence after washout? | SURVIVES | strong |
| Exp5-B (STDP *= 0.6) | Path dependence after washout? | FALSIFIED | strong |
| Exp5-C (both) | Path dependence after washout? | SURVIVES | same as A |
| Exp6-BoW (real embeddings) | Generalizes to bag-of-words? | SURVIVES | bounded |
| Exp6-Gauss (no structure) | Generalizes to random Gaussian? | FALSIFIED | informative |

Bottom line: the RESONANT boost survives the B2' challenge and generalizes
to realistic embeddings (when cosine is positive). Blocking reinforcement
produces genuine path dependence — the trajectory diverges after washout.
STDP scaling alone is a slider. Rescue remains a post-hoc filter.

---

## Exp4: B2' challenge

### Question

Can the strongest retrieval-only adversary (B2' = hybrid retrieval + B1
metadata reranking) recover X without propagation?

### Variants tested

- B2'a: broader retrieval (top-N by cosine, N=k*2..ALL) + B1 reranking
  (proper two-stage: retrieve by cosine, rerank with B1, take top-k)
- B2'b: query expansion (retrieve top-M, expand query, re-retrieve) + B1
- B2'c: hybrid lexical (tag match) + vector (cosine) + B1 reranking
- B2'd: ALL combined (broader + expansion + hybrid + B1)

### Result

```
X cosine rank: 24/62
X in B0:       False
X in B1:       False
X in B2'a (ALL): False  (X is rank 24 by cosine, but B1 score 0.31 < k-th)
X in B2'b:      False  (query expansion moves toward anchors, away from X)
X in B2'c:      False  (X tag doesn't match query tag)
X in B2'd:      False  (all combined, X still rank 20/62)
X in B4:        True   (score 0.788, source=propagation)
```

### Verdict: SURVIVES

No B2' variant recovers X. The RESONANT boost is a graph-structural
property that no retrieval-only method can reproduce.

### Why B2' fails

B2'a (two-stage): X is rank 24/62 by cosine. After B1 reranking, X's
score is 0.21 * 1.5 = 0.31. The k-th B1 score is ~0.4. X doesn't make
top-10. Even with N=ALL (retrieve everything by cosine, rerank with B1),
X's B1 score is too low.

B2'b (query expansion): expanding the query with top-M results shifts
the query toward the anchors (near 0 degrees), which moves AWAY from X
(at 78 degrees). Query expansion cannot help.

B2'c (hybrid lexical): X's tag ("beta") doesn't match the query tag
("alpha"). The lexical signal hurts X. Even with alpha=0.1 (mostly
lexical), X's hybrid score is 0.03 (rank 30/62).

B2'd (all combined): even with broader retrieval + expansion + hybrid +
B1, X is rank 20/62. The combined score (0.42) is still below the k-th.

### Key insight

B4's advantage is the RESONANT boost: `RESONANT_BOOST * n_links * sim`.
With 5 RESONANT links, this adds 5 * 0.5 * 0.21 = 0.52 to X's score,
pushing it from 0.31 (B1) to 0.79 (B4). No retrieval-only method has
this inter-memory interaction term.

---

## Exp5: Temporal washout

### Question

Does a systemic intervention (blocking reinforcement during a window)
leave a different trajectory after washout?

### Design

```
Phase 1 (steps 0-39):   baseline — both runs identical
Phase 2 (steps 40-69):  intervention — control keeps reinforcing,
                        intervention blocks reinforcement
Phase 3 (steps 70-99):  washout — both runs back to normal
```

100 memories, 100 decisions, same query sequence for both runs.

Three intervention variants:
- A: block reinforcement (don't reinforce top result during intervention)
- B: scale STDP potentiation by 0.6 during intervention
- C: both A and B

### Result: Intervention A (block reinforcement)

```
State evolution:
  Step  39 (baseline):   Ctrl REINF=14  Int REINF=14  (identical)
  Step  69 (intervention): Ctrl REINF=19  Int REINF=14  (5 fewer)
  Step  99 (washout):     Ctrl REINF=20  Int REINF=17  (3 fewer, persistent)

Trajectory comparison:
  During intervention:  set_diff=1/30, score_diff=13/30
  Post-washout:         set_diff=6/30, score_diff=13/30

  -> Divergence GROWS after washout (1 -> 6 set differences)
  -> Path dependence confirmed

Negative control (nearest-memory probe):
  Post-washout nearest differences: 0/30
  -> PASS: intervention is memory-specific, not a general poison
```

### Verdict: SURVIVES — path dependence confirmed

Blocking reinforcement during the intervention window changes which
memories get consolidated (REINFORCED). After washout, the different
REINFORCED population leads to different rescue behavior (different
memories get rescued from inhibition), which changes the result SET.

The divergence grows from 1/30 during intervention to 6/30 after
washout. This is the signature of path dependence: the intervention
changed the consolidated state, and the different state produces
different results even after the intervention is removed.

### Result: Intervention B (STDP *= 0.6)

```
During intervention:  set_diff=0/30, score_diff=0/30
Post-washout:         set_diff=0/30, score_diff=0/30

  -> FALSIFIED: slider (no path dependence)
```

### Verdict: FALSIFIED — slider

Scaling STDP potentiation by 0.6 doesn't change the result set or
scores. The link weights don't cross the 0.5 threshold for synaptic
pull differently. STDP scaling alone is parameter tuning with extra
steps.

### Result: Intervention C (both)

Same as A. The STDP scaling adds nothing — the reinforcement blocking
is the active ingredient.

### The slider-vs-pharmacology test (answered)

> If reinforcement *= 0.6 only changes results while the multiplier is
> active and then returns exactly to control, it's a slider.

Answer: blocking reinforcement does NOT return to control after
washout. The trajectory diverges and the divergence GROWS. This is
genuinely temporal, not a slider.

> If it changes what got consolidated during that window and therefore
> the system follows a different trajectory after washout, there
> appears something genuinely temporal.

Answer: YES. The intervention changed which memories got consolidated
(REINFORCED). The different consolidated state produces different
recall results after washout. Path dependence is confirmed.

### The chess negative control (answered)

> If our anti-reinforcement-0.4 makes Frankenstein also start hanging
> the queen, we didn't discover a drug for memory. We poisoned it.

Answer: the nearest-memory probe passes (0/30 differences). The
intervention doesn't degrade the ability to recall the closest match.
It's memory-specific (changes which memories are REINFORCED), not a
general poison.

---

## Exp6: Real embeddings generalization

### Question

Does the Exp1b result (B4 gets X that B0/B1/B2' miss) generalize
outside the unit circle?

### Approach

Two embedding methods (no new dependencies):
1. Bag-of-words + random projection (semantic structure, non-unit-norm)
2. Random Gaussian (no structure, non-unit-norm)

### Result: Bag-of-words + projection

X shares one keyword ("data") with the query domain. X's cosine sim
to query: 0.10 (positive but low, rank 31/62).

```
X in B0:   False
X in B1:   False
X in B2':  False
X in B4:   True   (score 0.387, source=propagation)
```

### Verdict: SURVIVES (bounded)

The Exp1b result generalizes to realistic embeddings when the target
has positive cosine to the query. B4 brings in X via RESONANT
propagation that no retrieval-only method can reproduce.

### Result: Random Gaussian

X is orthogonal to the query. X's cosine sim: -0.09 (negative).

```
X in B0:   False
X in B1:   False
X in B2':  False
X in B4:   False  (RESONANT boost amplifies negative sim -> clamps to 0)
```

### Verdict: FALSIFIED (informative)

The RESONANT boost formula `RESONANT_BOOST * min(sim, 1.0)` amplifies
the cosine similarity. When sim is negative, the boost is negative,
which HURTS the score rather than helping it. B4 cannot bring in
memories that are semantically orthogonal to the query.

### Boundary condition

The RESONANT boost only helps when the target has positive cosine to
the query. This is a feature, not a bug: in a real system, you
shouldn't bring in completely unrelated memories. The boost amplifies
related-but-distant memories, not orthogonal ones.

In realistic embeddings:
- Cross-domain memories sharing SOME concepts (positive cosine) CAN
  be brought in by propagation
- Completely orthogonal memories (negative cosine) CANNOT

---

## Cross-experiment synthesis

### What survived across all experiments

1. **Propagation changes set composition** (Exp1b, Exp4, Exp6-BoW):
   the RESONANT boost is a graph-structural property that B1/B2' cannot
   reproduce. It requires positive cosine to the query.

2. **Reinforcement blocking produces path dependence** (Exp5-A):
   the intervention changes which memories get consolidated, and the
   trajectory diverges after washout. The divergence GROWS, confirming
   path dependence rather than a transient effect.

3. **The intervention is memory-specific** (Exp5 negative control):
   the nearest-memory probe passes. The intervention doesn't degrade
   general recall capability.

### What was falsified

1. **Rescue is a post-hoc filter** (Exp2): definitively. A == C
   bit-identically.

2. **STDP scaling is a slider** (Exp5-B): scaling STDP potentiation
   alone doesn't change the result set. It's parameter tuning.

3. **Propagation doesn't help orthogonal memories** (Exp6-Gauss):
   the RESONANT boost can't bring in memories with negative cosine.

4. **Propagation doesn't help in small/dense fields** (Exp1): with a
   dense k-NN graph, propagation only reorders.

### What this means for the hypothesis

H0 ("retrieval is not necessarily sufficient") gets stronger support:

- H1 (dynamics over B1): SURVIVES across Exp1b, Exp4, Exp6-BoW. The
  RESONANT boost is a genuine graph-structural property.
- H2 (intervention vs removal): SURVIVES weakly (Exp3). Suppression
  differs from removal in scores.
- H7 (rescue is post-hoc): FALSIFIED (Exp2).

NEW finding (not in original hypotheses):
- H8 (path dependence): blocking reinforcement produces a trajectory
  that diverges after washout. This is the strongest evidence that
  dynamic memory mechanisms produce properties retrieval alone cannot
  represent — not in the static sense (set composition) but in the
  temporal sense (consolidation changes future trajectories).

### The washout criterion (answered)

The user's criterion was:

> If reinforcement *= 0.6 only changes results while active and returns
> to control → slider with farmacología cosplay.
> If it changes what got consolidated → different trajectory after
> washout → genuinely temporal.

Answer: blocking reinforcement changes what gets consolidated. The
trajectory diverges after washout and the divergence GROWS. This is
genuinely temporal, not a slider.

The "drug" works. But it works through reinforcement blocking (changing
which memories get the 1.5x state boost), not through STDP scaling
(changing link weights). The active ingredient is state consolidation,
not synaptic plasticity.

### What we still don't know

- Whether the path dependence effect is robust across different query
  distributions, field sizes, and intervention durations.
- Whether the effect matters for downstream decisions (does the
  different result set change what an agent would DO?).
- Whether MNEME's custody/counterfactual machinery adds verifiability
  to this path dependence (can we prove the trajectory diverged
  because of the intervention, not noise?).
- Whether STIGMERGY's shared-state multi-agent dynamics produce
  collective path dependence.
- Whether the Exp6 boundary condition (positive cosine required) is
  a fundamental limitation or an artifact of the RESONANT boost formula.
