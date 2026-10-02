# STOP conditions — when NOT to build Remember the Seasons

The research package is complete. Per the transition gate, we STOP and review
before any implementation. These are the conditions under which we should
**not** proceed to build Remember the Seasons as a product/system. Any one is
sufficient.

## Hard STOP (do not build)

1. **H0 unsupported.** If, after the experimental matrix, every sub-hypothesis
   H1-H7 is falsified — i.e. competent retrieval (B0/B1/B2) is sufficient for
   every tested property — the premise is unsupported. Report it. Do not
   build a product on a falsified hypothesis.

2. **No mechanism beats the metadata-rerank baseline.** If B1 (top-k + metadata
   rerank) reproduces every property the dynamics claim (contradiction
   resistance, preference replacement, forgetting) using only metadata flags,
   then the "dynamics" are recoverable as retrieval+metadata and H0 is false
   in its strong form.

3. **Causal influence is vacuous.** If the intervention Δ (H2) is always 0, or
   fully derivable from retrieval-only outputs, the causal-attribution
   property does not exist as a distinct contribution.

4. **The rescue rule is vacuous and cannot be made discriminating.** If the
   only invariant the dynamics claim to protect (rescue) cannot be constructed
   to fail, the property is vacuously true and is not evidence of anything.

## Soft STOP (re-scope, do not build the full system)

5. **Only provenance/auditability survives.** If the only property beyond
   retrieval is verifiability (E9), then the contribution is a custody layer,
   not a memory architecture. Build (at most) a custody layer over a retrieval
   system, not "Remember the Seasons."

6. **Only multi-agent propagation survives (H6).** If the only distinct
   property is stigmergic collective memory, the single-agent premise is
   unsupported; the work belongs to a multi-agent project, not a general
   persistent-memory system.

7. **Systemic interventions are just parameter tuning.** If Y1-Y5 change
   recall only in directions a reranking baseline (B2) matches, the
   "intervention" research adds no contribution beyond hyperparameter search.

8. **The three systems should remain separate.** If no composition of
   mechanisms produces a property that no single system produces alone, do not
   integrate them. Keep them as separate tools.

## Proceed condition (the only gate to building)

Proceed to design Remember the Seasons **only if**:
- At least one sub-hypothesis H1-H7 survives its falsifier with evidence, AND
- that surviving property is not reproducible by B1/B2 (competent retrieval +
  metadata/reranking), AND
- the maintainer explicitly approves moving from research workspace to product.

Until then, this repository stays a lab. Nothing here is the product.
