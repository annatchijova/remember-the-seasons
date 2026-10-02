# Phase 3 — Baseline design

> Do not construct a weak RAG strawman. The point of a strong baseline is that
> if a mechanism beats it, the mechanism earned it. Control as many variables
> as possible: same underlying information, same model where relevant, same
> context budget, same tasks, same evaluation semantics, pinned configs.
> Identify tasks where retrieval SHOULD win.

---

## 1. Baseline ladder (PROPOSED)

Each baseline is a configuration over the *same* corpus and *same* evaluation.
They differ only in the memory mechanism. This isolates the mechanism as the
independent variable.

| ID | Baseline | What it tests | Mechanism |
|---|---|---|---|
| **B0** | Flat top-k cosine | the competent retrieval floor | embed query → top-k by cosine, return k docs. No state, no links, no propagation. This is the "retrieval is sufficient" champion. |
| **B1** | top-k + metadata rerank | retrieval plus reasonable metadata/state | B0 + rerank by the SAME metadata the dynamics system uses (see concrete spec below). Tests whether "state-as-flag" already captures what ternary-state-as-multiplier claims. |
| **B2** | Hybrid / reranking retrieval | stronger retrieval where appropriate | B0 + a cross-encoder reranker (or BM25+vector fusion) over the top-N. Tests whether *better retrieval* closes the gap that dynamics claims to close. No metadata reranking. |
| **B2'** | B2 + B1 metadata reranking | the strongest null-hypothesis adversary | B2's hybrid retrieval + B1's metadata-aware reranking (state multiplier, contradiction detection, recency). This is the champion of "retrieval done competently with reasonable metadata is sufficient." If dynamics cannot beat B2', the hypothesis is dead. |
| **B3** | top-k + graph propagation only | propagation without state | raven BFS hop expansion but all states NEUTRAL, no links. Isolates propagation from state/link effects. |
| **B4** | raven full field (float) | the complete single-agent dynamic memory | raven's full scoring (states, links, STDP, rescue, recency). The candidate system, not a baseline. |
| **B5** | MNEME exact field | same field, exact ranking + custody | B4 with Fraction ranking + custody chains. Tests whether exactness/custody changes *quality* or only *verifiability*. |
| **B6** | individual mechanisms | each mechanism alone over B0 | e.g. B0+STDP-only, B0+links-only, B0+states-only. Ablation anchors. |
| **B7** | STIGMERGY shared-state (multi-agent only) | collective memory | only meaningful in multi-agent tasks; in single-agent tasks it reduces to B0/B4. |

**B0 is the primary baseline.** A mechanism that does not beat B0 on the
property it claims to produce has no evidence it is needed. B1 and B2 are the
"retrieval is already enough if you do it competently" challengers — the
strongest form of the null hypothesis. **B2' is the strongest adversary**: if
dynamics cannot beat B2' (competent hybrid retrieval + metadata-aware
reranking), the hypothesis is dead.

### Concrete B1 specification (not a strawman)

B1 must have access to the SAME metadata the dynamics system uses, and a
reasonable reranking policy. From the code (OBSERVED):

- raven detects contradictions by metadata: same `topic` + different `claim`
  → INHIBITORY link (`memory_engine.py:1568-1596`). No NLI. B1 can do the same
  detection with the same metadata.
- raven's scoring formula: `cosine × state_boost × decay^hop + resonant_boost
  + synaptic × 0.3 + recency`. B1 gets the same formula WITHOUT the dynamics
  terms (no hop decay, no resonant boost, no synaptic weight).

**B1 = `cosine × state_boost + recency_bonus`**, where:
- `state_boost`: REINFORCED ×1.5, NEUTRAL ×1.0, FORGOTTEN ×0.0 (same as
  raven, `memory_engine.py:126`).
- `recency_bonus`: `+0.05 × exp(-ln2 × age / 24h)` (same as raven).
- Contradiction handling: if two retrieved memories share `topic` and differ
  in `claim`, the non-validated one is deprioritized (multiplier ×0.0 or
  filtered). This is the metadata equivalent of the rescue rule.
- Same embedder, same k, same context budget as B4.

This is the fairest possible B1: it is raven's own scoring formula with the
dynamics terms removed. It isolates the dynamics as the only difference.

**What B1 cannot do (the discriminating question):** B1 does not have
propagation. An INHIBITORY link in raven removes a memory from the activated
set, which means its RESONANT neighbors don't get boosted, which changes
which OTHER memories enter the result set. B1 only reranks the top-k that
cosine already returned. The discriminating question is: **does propagation
change the SET of memories returned, not just the ranking?** If the result
set is the same (only the order differs), B1 matches dynamics. If
propagation brings in memories that flat top-k missed (or excludes memories
that flat top-k would have returned), dynamics have a set-composition
advantage that B1 cannot reproduce.

## 2. Variable control (PROPOSED)

To make a comparison valid, fix everything except the mechanism:

- **Same corpus / same facts.** One frozen corpus per task family. Versioned
  and hashed. Every baseline reads the same bytes.
- **Same embeddings.** One pinned embedding model (or a deterministic stub)
  for all systems. Embedding is a measurement, not the variable.
- **Same context budget.** Every system returns the same k (or same token
  budget). A system that wins by returning more context is winning a
  different game.
- **Same downstream model.** Where a downstream LLM consumes the retrieved
  context, use the same model, same prompt template, same temperature (0 for
  determinism), pinned version. The LLM is out of the decision path but IS
  the measurement instrument for end-to-end tasks.
- **Same tasks / same evaluation semantics.** One metric family per property
  (see Phase 4). Do not let each system be evaluated by its own metric.
- **Pinned configs.** Hyperparameters (K_NEIGHBORS, HOP_LAMBDA, decay, α,
  thresholds) pinned and recorded per run. No per-system tuning that the
  other systems don't get.

## 3. Tasks where retrieval SHOULD win (PROPOSED — to confirm)

A system that only wins benchmarks designed for itself proves little. We must
include tasks where the strong baseline is expected to dominate, and report
those losses honestly.

- **Fresh-fact lookup:** "what is the value of X?" over a corpus with no
  conflicts, no staleness, no contradictions. B0/B2 should win or tie. Any
  dynamic mechanism that loses here is paying overhead for nothing.
- **Large-corpus nearest-neighbour recall:** pure semantic similarity at
  scale. Better retrieval (B2) should win; dynamics should not help.
- **Single-source summarisation:** no conflict, no authority question.
  Retrieval quality dominates.

If B4/B5 lose to B0/B2 on these, that is the *expected* result and is reported
as such — it bounds where dynamics are *not* needed.

## 4. Tasks where dynamics MIGHT win (PROPOSED — to test)

These are where the hypothesis predicts retrieval-alone is insufficient:

- **Contradiction resistance:** corpus contains A and ¬A; the system must
  prefer the validated/reinforced one and suppress the other. B0 returns
  both ranked by similarity; dynamics should collapse around truth.
- **Preference replacement:** a stale preference must be replaced by a newer
  one *without destroying the historical evidence*. B0 has no notion of
  supersession; custody/supersession should win on "evidence preserved".
- **Contamination containment:** a poisoned source is quarantined; the system
  must not serve its memories and must trace blast radius. B0 has no
  containment; taint/gate should win.
- **Causal attribution:** "did this memory cause this decision?" B0 cannot
  answer; intervention/counterfactual should.
- **Forgetting under interference:** old memories should fade when superseded,
  not persist forever. B0 returns everything; decay/forgetting should win.
- **Multi-agent experience propagation (STIGMERGY only):** a late agent
  benefits from an earlier agent's experience through shared state. B0 per
  agent cannot propagate; stigmergic recruitment should win.

## 5. Honest expectation (PROPOSED)

- On lookup/summarisation: B0 ≈ B2 ≥ B4. Dynamics lose or tie. Expected.
- On contradiction/preference/containment/attribution: B4/B5 > B0, but B1
  (metadata rerank) may close part of the gap. The interesting question is
  *how much* of the gap is closed by competent metadata retrieval vs dynamics.
- On provenance/auditability: B0 cannot compete by construction; this is a
  different dimension, scored separately (see Phase 4 §3).
