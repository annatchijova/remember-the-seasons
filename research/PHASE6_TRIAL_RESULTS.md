# Pre-clinical trial results

> Three discriminating experiments run against a minimal raven-faithful engine.
> All experiments use synthetic fields on a unit circle in high-dimensional space.
> The engine (`experiments/minimal_raven.py`) reproduces raven's exact scoring
> formula, BFS, rescue loop, and k-NN symmetrization from commit 56df6cf.
>
> Epistemic status: OBSERVED (these are actual runs, not predictions).

---

## Summary

| Experiment | Question | Verdict | Strength |
|---|---|---|---|
| Exp1 (small field) | Does propagation change the SET? | FALSIFIED | strong |
| Exp1b (large field, best case) | Does propagation change the SET? | SURVIVES | bounded |
| Exp2 | Is rescue a post-hoc filter? | FALSIFIED | strong |
| Exp3 | Is suppress == remove? | SURVIVES | weak |

Bottom line: propagation CAN change set composition that B1 cannot
reproduce, but only under specific conditions (large field, multiple
RESONANT links, REINFORCED target, positive-but-low cosine). Rescue is
definitively a post-hoc filter. Suppression differs from removal only in
score magnitudes, not in set or order (for non-seed targets).

---

## Exp1: Set composition (small field)

### Configuration

- 16 memories on a 16-dim unit circle
- Query at 0 degrees
- RESONANT links A->D (85deg) and B->C (80deg)
- K_NEIGHBORS=6, hops=2, top_k=5

### Result

```
B0 (flat top-k):     ['A', 'B', 'N5', 'N6', 'N7']
B1 (top-k + meta):   ['A', 'B', 'N5', 'N6', 'N7']
B4 (full dynamics):  ['A', 'B', 'N5', 'N6', 'N7']
```

B4 sources show B, N5, N6, N7 came from "propagation" (hop 1), but they
are already in B0's flat top-k. The RESONANT links to C and D did not
bring them in because their cosine sim is too low (cos(80deg)=0.17,
cos(85deg)=0.087) and the resonant boost (0.5 * sim) is also low.

### Verdict: FALSIFIED

With a small field and dense k-NN graph, propagation does not change the
result set. B0, B1, and B4 return identical sets. Propagation only
affects the order (which memories are labeled "propagation" vs
"similarity"), not the composition.

### Why

With 16 memories and K=6, the k-NN graph is nearly complete. BFS reaches
all cells within 2 hops through k-NN alone. RESONANT links add no new
cells — they only boost already-reachable cells. And the boosted cells'
scores (after hop decay) don't beat the closer cells that flat top-k
already returns.

---

## Exp1b: Set composition (large field, best case)

### Configuration

- 62 memories on a 32-dim unit circle
- Query at 0 degrees
- X at 78 degrees (cos = 0.208), REINFORCED
- 5 anchors at 3-20 degrees, each with RESONANT link to X
- 56 noise memories spread around the circle (avoiding 0-22 and 70-86)
- K_NEIGHBORS=6, hops=2, top_k=10

### Result

```
B0 (flat top-k):     ['A0','A1','A2','A3','A4','N17','N18','N32','N39','N5']
B1 (top-k + meta):   ['A0','A1','A2','A3','A4','N17','N18','N32','N39','N5']
B4 (full dynamics):  ['A0','A1','A2','A3','A4','N17','N32','N39','N5','X']
  X in B4: source=propagation, hop=1, score=0.788206
```

X appears in B4 but NOT in B0 or B1.

### Verdict: SURVIVES (bounded)

Propagation brought X into the result set that BOTH flat top-k AND
metadata-aware reranking (B1) missed.

### Why B1 cannot reproduce this

X's flat cosine score: 0.208
X's B1 score (with REINFORCED multiplier): 0.208 * 1.5 = 0.312
X's B4 score (with 5 RESONANT links at hop 1):
  sim * state_boost * hop_decay + resonant_boost * sim
  = 0.208 * 1.5 * exp(-0.15) + 5 * 0.5 * 0.208
  = 0.208 * 1.5 * 0.861 + 0.520
  = 0.268 + 0.520
  = 0.788

The k-th B1 score is ~0.4 (a noise memory at ~65 degrees). X's B1 score
(0.312) is below this threshold. X's B4 score (0.788) is above it.

B1 has no mechanism to produce the RESONANT boost. The boost is
`RESONANT_BOOST * n_in_edges * sim`, which requires the graph structure
(links + propagation) to compute. B1 only has `sim * state_boost +
recency`, which is a per-memory function with no inter-memory
interaction.

### Boundary conditions

This result required:
1. Large field (62 memories) so k-NN doesn't reach everything in 2 hops
2. X at a specific angle (78 deg) where cosine is positive but low
3. 5 RESONANT in-edges (the maximum practical boost)
4. X REINFORCED (1.5x state multiplier)
5. X NOT in the k-NN graph of any anchor (only reachable via RESONANT)

With fewer RESONANT links (1-2), X's score drops below the threshold.
With a smaller field, k-NN reaches X anyway and B0 gets it. With X at a
negative-cosine angle (>90 deg), the resonant boost amplifies a negative
sim and clamps to 0.

This is a constructed best-case, not a naturalistic result. It proves
the mechanism CAN produce set-composition differences that B1 cannot
reproduce, but it does not prove this happens frequently in practice.

### The discriminating question (answered)

> Does propagation change the set of returned memories, not merely the
> ranking?

Answer: YES, but only when:
- the field is large enough that k-NN doesn't reach the target
- the target has positive-but-low cosine to the query
- the target has multiple RESONANT in-edges
- the target is REINFORCED

Under these conditions, B1 (metadata reranking) cannot reproduce the
result because it has no inter-memory interaction term. The RESONANT
boost is a graph-structural property that requires propagation to compute.

---

## Exp2: Rescue vs post-hoc filter

### Configuration

- V (REINFORCED) and W (NEUTRAL) with same topic, different claims
  -> auto INHIBITORY link
- Query near W. W inhibits V during BFS.
- 6 noise memories
- K_NEIGHBORS=6, hops=2, top_k=10

### Result

```
A (rescue ON):       ['V', 'W', 'N0', 'N5', 'N1', 'N2', 'N3', 'N4']
A scores:            V=1.271, W=0.996, N0=0.430, N5=0.430, rest=0.0
B (rescue OFF):      ['N0','N1','N2','N3','N4','N5','W']  (V excluded)
C (post-hoc filter): ['V', 'W', 'N0', 'N5', 'N1', 'N2', 'N3', 'N4']
C scores:            V=1.271, W=0.996, N0=0.430, N5=0.430, rest=0.0

A == C (set):        True
A == C (order):      True
A == C (scores):     True
```

### Verdict: FALSIFIED

A == C exactly. The rescue rule is functionally equivalent to a post-hoc
metadata filter: "if REINFORCED and excluded as INHIBITED -> add back
with the same score."

### Why they are identical

The rescue loop runs AFTER BFS and BEFORE scoring. It moves REINFORCED
cells from `inhibited_cells` to `activated_cells`. The rescued cell:
1. Was reached during BFS (has a hop_dist in cell_hops)
2. Was inhibited (its links were NOT traversed)
3. Is moved to activated_cells for scoring
4. Is scored with the same formula as any other activated cell

The post-hoc filter (variant C) does the same thing AFTER scoring
instead of BEFORE. But since scoring is independent per memory (no
cross-memory interaction during scoring — resonant boosts were
accumulated during BFS, not during scoring), the order doesn't matter.

The rescued cell's score depends only on:
- its own cosine sim to the query
- its own state_boost
- its hop_dist (from BFS)
- its resonant_boost (from BFS — which is 0 because it was inhibited
  before it could receive RESONANT boosts)
- its recency_bonus

All of these are the same whether the cell is added before or after
scoring. The result is bit-identical.

### Implication

The rescue rule provides NO property beyond what a metadata filter
provides. It is not a propagation mechanism — it does not restore the
rescued cell's ability to propagate its links. It is a post-hoc
reinclusion filter that happens to run before scoring instead of after,
which makes no difference to the outcome.

H7 is FALSIFIED: the rescue rule is a post-hoc filter, not a
propagation mechanism.

---

## Exp3: Intervention vs removal

### Configuration

- 12 memories on a 16-dim unit circle
- RESONANT links: M0->M8, M1->M9, M2->M11
- K_NEIGHBORS=6, hops=2, top_k=10
- 5 non-seed targets tested + 1 degenerate seed case

### Result (non-seed targets)

| Target | Set match | Order match | Score match |
|---|---|---|---|
| M1 | True | True | False |
| M10 | True | True | True |
| M2 | True | True | False |
| M3 | True | True | False |
| M4 | True | True | False |

Score differences (example, target=M1):
```
M7: suppress=0.191738  remove=0.222768
```

All score differences are on M7. M7 is at 75 degrees. Its hop_dist
changes because:
- Suppress M1: M1 is still in the k-NN graph, so M7's k-NN neighbors
  include M1 (which is skipped during BFS). M7's hop_dist is determined
  by its OTHER neighbors.
- Remove M1: M1 is gone from the k-NN graph, so M7's k-NN neighbors
  shift (the next-nearest cell replaces M1). M7's hop_dist may change.

### Degenerate case (suppress the seed)

```
suppress M0 (seed): result set = []  (BFS has no starting point)
remove M0:          result set = ['M1','M10','M11','M2','M3','M4','M5','M6','M7','M8']
```

Suppressing the seed kills BFS entirely because the seed is still in the
KDTree (selected as nearest) but skipped (in suppressed set). Removing
the seed rebuilds the KDTree without it, so the next-nearest cell
becomes the seed.

### Verdict: SURVIVES (weak)

Suppression != removal. But the difference is:
- For non-seed targets: only SCORES differ (set and order are identical)
- For the seed: a degenerate case (BFS dies entirely)

### Interpretation

The score difference is a real propagation-specific effect: the k-NN
graph topology changes differently under suppression (cell still in
graph, edges inert) vs removal (cell gone, graph rebuilt). This changes
hop distances, which changes hop_decay, which changes scores.

But the set and order are the same for non-seed targets. So the
intervention does not change WHICH memories are returned or in WHAT
order — it only changes the score magnitudes. Whether this matters
depends on whether downstream decisions use the scores (e.g., for
thresholding or weighting) or only the ranking.

The seed case is degenerate and arguably a bug in the intervention
design (the seed selection should skip suppressed cells). It is not a
meaningful propagation effect.

### The cruelty test

> If inhibiting the influence of the target maintaining its existence
> produces effects distinct from removing it from the informational
> universe, a more interesting causal notion begins to appear.

Answer: PARTIALLY. The intervention produces a distinct effect (score
magnitudes) but not a distinct observable outcome (set + order). The
"interesting causal notion" is present but weak — it operates on score
magnitudes through graph topology, not on which memories are accessible.

---

## Cross-experiment synthesis

### What survived

1. **Propagation can change set composition** (Exp1b) — but only under
   specific conditions: large field, multiple RESONANT links, REINFORCED
   target, positive-but-low cosine. B1 (metadata reranking) cannot
   reproduce this because it has no inter-memory interaction term.

2. **Suppression != removal** (Exp3) — but only in score magnitudes, not
   in set or order (for non-seed targets). The difference is a
   second-order graph-topology effect.

### What was falsified

1. **Rescue is a post-hoc filter** (Exp2) — definitively. A == C
   bit-identically. The rescue rule provides no property beyond what a
   metadata filter provides.

2. **Propagation doesn't always change the set** (Exp1) — in small fields
   with dense k-NN, propagation only reorders. The set-composition
   effect requires specific boundary conditions.

### What this means for the hypothesis

The central hypothesis ("retrieval is not necessarily sufficient") gets
partial support:

- H1 (dynamic mechanisms produce properties not reproduced by B1):
  SURVIVES, bounded. The RESONANT boost is a graph-structural property
  that B1 cannot reproduce. But it requires specific conditions and
  may be rare in practice.

- H2 (causal attribution requires intervention): SURVIVES, weak.
  Suppression != removal, but the difference is in score magnitudes,
  not in observable outcomes. The "optogenetic" probe is not simply
  "delete a row" — it has a graph-topology-specific effect — but the
  effect is subtle.

- H7 (rescue is a post-hoc filter): FALSIFIED. The rescue rule is
  definitively a post-hoc metadata filter.

### What we still don't know

- Whether the Exp1b result generalizes to naturalistic fields (real
  embeddings, real memory distributions) or is an artifact of the
  unit-circle construction.
- Whether B2' (hybrid retrieval + B1 metadata reranking) can recover X
  in the Exp1b configuration through better initial retrieval.
- Whether the Exp3 score differences matter for downstream decisions
  (do they change LLM outputs? do they change agent behavior?).
- Whether systemic interventions (washout criterion) produce
  trajectory differences — this requires temporal experiments not yet
  run.

### Next steps (if authorized)

1. Test B2' against the Exp1b configuration: can hybrid retrieval
   recover X without propagation?
2. Run Exp1b with real embeddings (not unit circle) to check
   generalization.
3. Run temporal washout experiments: does a systemic intervention
   (e.g., reinforcement *= 0.6 for 5 decisions) leave a different
   trajectory after washout?
4. Test whether the Exp3 score differences change downstream decisions
   (threshold-based filtering, LLM context assembly).
