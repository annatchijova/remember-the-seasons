# Research package review — three corrections

> This document corrects three issues found by auditing the research package
> against the live code before authorizing experiments. Each correction
> states what was wrong, what the code actually shows, and the fix.

---

## Correction 1 — The rescue invariant: not vacuous, but equivalent to a
## post-hoc metadata filter

### What I claimed (wrong framing)

I wrote that the rescue rule's fuzzer has an unreachable violation branch and
that "the invariant may be vacuously true." That framing conflates two
distinct things and misleads.

### What the code actually shows (OBSERVED)

The rescue loop (`memory_engine.py:1718-1730`) runs **after** the BFS loop
(`memory_engine.py:1682-1714`):

```
BFS (1682-1714):  populate activated_cells and inhibited_cells
                   a cell in inhibited_cells is skipped (1685): its links
                   are NOT traversed, so its RESONANT neighbors are NOT boosted
Rescue (1718-1730): for each inhibited cell:
                     if REINFORCED → discard from inhibited, add to activated
                     else → write INHIBITED exclusion
Scoring (1738+):   score all activated_cells (including rescued ones)
```

Two facts follow from this ordering:

1. **The fuzzer's violation branch is unreachable by construction.** The
   rescue loop removes all REINFORCED cells from `inhibited_cells` before the
   scoring-phase INHIBITED check (line 1762). A REINFORCED memory can never
   get `ExclusionReason.INHIBITED`. The fuzzer (`intervention.py:273`) checks
   for exactly that, so `violations` is always empty. This is OBSERVED and
   the authors already document it honestly as red-team finding RT-1
   (`intervention.py:221-232`).

2. **The rescue rule is functionally a post-hoc filter, not a propagation
   mechanism.** The rescued cell is added to `activated_cells` for scoring,
   but its links were NOT traversed during BFS (it was inhibited during BFS,
   so line 1685 skipped it). Its RESONANT neighbors did not get boosted. The
   rescue saves the memory's presence in results but does NOT restore its
   field effect.

### Why the original framing was wrong

"Vacuously true" suggests the invariant is meaningless. It is not — the
rescue loop does real work: without it, a REINFORCED memory WOULD be silenced
by an INHIBITORY link. The invariant is **true by construction**, which is
the strongest form of correctness, not vacuity.

But the deeper issue is different: the rescue rule is a **self-correction
mechanism for a problem that only exists in the dynamics system.** A
retrieval-only system (B1) does not have INHIBITORY links, so it does not
need rescue. And because the rescue happens after BFS (no re-propagation),
it is equivalent to a post-hoc filter: "if REINFORCED and inhibited → add
back to results." B1 can do the same with metadata: "if trust_flag and
contradicted → keep."

### Corrected claim

The rescue rule is:
- NOT vacuous as a correctness property (it prevents a bad outcome that
  would occur without it in the dynamics system).
- NOT a property that distinguishes dynamics from retrieval (retrieval
  doesn't have the bad behavior; and the rescue is a post-hoc filter, not a
  propagation effect).
- The fuzzer's vacuity is a SYMPTOM of the structural enforcement, not the
  research finding.

### Corrected H7

**Old H7:** "rescue rule is non-vacuous" — falsifier: "violation branch
unreachable by construction." This is not a falsifier; it is an observation.

**New H7:** The rescue rule's effect on the result set is indistinguishable
from a post-hoc metadata filter that deprioritizes non-validated
contradictions.

**Falsifier (now actually discriminating):** ablate the rescue loop
(remove `memory_engine.py:1718-1730`) and replace it with a post-scoring
filter that adds REINFORCED memories back to results if they were excluded
as INHIBITED. If the outcomes (result set + ranking) are identical across
all test queries, the rescue rule is a post-hoc filter in disguise and
provides no property beyond what B1 can do with metadata. If they differ
(because the rescue loop's modification of `inhibited_cells` before scoring
affects something other than the rescued memory's own presence), the
rescue rule has a propagation effect worth investigating.

**Why this is now falsifiable:** the test has two outcomes — identical
(rescue = post-hoc filter, H7 falsified) or different (rescue has a
propagation effect, H7 survives). Both are observable.

---

## Correction 2 — B1 and B2: concretize or they are strawmen

### What I claimed (too vague)

I defined B1 as "top-k + metadata rerank" and B2 as "hybrid/reranking
retrieval" without specifying what metadata, what reranking policy, or what
makes them fair. A vague baseline is a strawman by omission.

### What makes B1 a strong adversary (PROPOSED, concretized)

B1 must have access to the SAME metadata the dynamics system uses, and a
reasonable reranking policy. From the code (OBSERVED):

- raven detects contradictions by metadata: same `topic` + different `claim`
  → INHIBITORY link (`memory_engine.py:1568-1596`). No NLI, no semantic
  inference. B1 can do the same detection with the same metadata.
- raven's scoring formula is: `cosine × state_boost × decay^hop +
  resonant_boost + synaptic × 0.3 + recency`. B1 gets the same formula
  WITHOUT the dynamics terms (no hop decay, no resonant boost, no synaptic
  weight): `cosine × state_boost + recency`.

**Concrete B1:**
- Retrieve top-k by cosine (same embedder, same k).
- Apply the state multiplier: REINFORCED ×1.5, NEUTRAL ×1.0, FORGOTTEN ×0.0
  (same as raven, OBSERVED `memory_engine.py:126`).
- Apply contradiction detection: if two retrieved memories share `topic` and
  differ in `claim`, the non-validated one is deprioritized (multiplier ×0.0
  or filtered). This is the metadata equivalent of the rescue rule.
- Apply recency bonus: `+0.05 × exp(-ln2 × age / 24h)` (same as raven).
- Same context budget (same k).

This is the fairest possible B1: it is raven's own scoring formula with the
dynamics terms (propagation, links, STDP) removed. It isolates the dynamics
as the only difference. It is NOT a strawman because it has the same
metadata, the same scoring shape, and the same contradiction detection.

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

### What makes B2 a strong adversary (PROPOSED, concretized)

B2 is a stronger retrieval method. It is the right adversary for E1
(retrieval quality) but NOT for dynamics properties:

- **B2 = hybrid retrieval:** BM25 + vector fusion, or a cross-encoder
  reranker over the top-N. Better retrieval quality than B0.
- **B2 does NOT have metadata reranking.** It is a pure-retrieval adversary.
  It tests whether better retrieval alone closes the gap.
- **B2' = B2 + B1's metadata reranking.** This is the strongest adversary:
  competent hybrid retrieval + metadata-aware reranking. If dynamics cannot
  beat B2', the hypothesis is dead.

The baseline ladder should be: B0 < B1 < B2 < B2' (strongest). B2' is the
champion of the null hypothesis. A mechanism that does not beat B2' has no
evidence it is needed.

### Correction to Phase 3

Add B2' (B2 + B1 metadata) as the strongest baseline. Make B1's concrete
specification (scoring formula minus dynamics terms, same metadata, same
contradiction detection) part of the baseline definition. State explicitly
that the discriminating question for B1 vs dynamics is SET COMPOSITION
(does propagation change who gets returned), not just ranking.

---

## Correction 3 — Falsifier audit for H1-H7

### H1 — dynamics over retrieval

**Falsifier:** "B1 reproduces collapse-around-truth and preference
replacement using only metadata flags."

**Audit:** Discriminating IF B1 is the concretized version above (same
metadata, same contradiction detection). The test is: on contradiction/
preference tasks, does B4 (full dynamics) produce a different result SET
than B1? If same set, different order → B1 matches. If different set →
dynamics win. **Verdict: OK with concretized B1.**

### H2 — causal attribution requires intervention

**Falsifier:** "Δ is always 0, OR the same Δ is derivable from
retrieval-only outputs without intervention."

**Audit:** The first clause (Δ always 0) is a valid falsifier. The second
clause is vague — "derivable from retrieval-only outputs" needs to be
concrete. **Correction:** the concrete test is: remove the target memory
from the corpus, re-run B0 top-k, and compare the result-set delta to the
intervention Δ. If they match, the intervention is equivalent to
"retrieve without this memory" — which is a retrieval operation, not a
distinct causal probe. If they differ (because the intervention suppresses
the memory during propagation, not just removing it from results), the
intervention has a propagation-specific effect. **Verdict: needs
concretization, now done.**

### H3 — decision causality requires closure

**Falsifier:** "a retrieval-only system can answer 'which memories caused
this decision' as accurately as the closure layer."

**Audit:** Discriminating. The closure layer provides EXACT attribution
(which memories were served, which the decision cited). A retrieval-only
system would have to infer attribution from the prompt context, which is
not exact. The test is: on a decision audit, does retrieval-only
attribution match closure attribution? Metric: precision/recall of
attributed memories. **Verdict: OK.**

### H4 — graph-gate vs serve-only filter

**Falsifier:** "serve-only metadata filter matches graph-gate on
clean-memory ranking under contamination."

**Audit:** Strongly discriminating. This is the OBSERVED risk
(`ARCHITECTURE.md:243-246`): a tainted node on a RESONANT path can perturb
a clean memory's ranking if only serving is gated. The graph-gate
prevents traversal of tainted nodes during BFS. A serve-only filter
removes tainted memories from results but leaves their links active.
The test is: under contamination, does a clean memory's ranking change
when a tainted neighbor's RESONANT link is active (serve-only) vs
inactive (graph-gate)? **Verdict: OK — this is the strongest falsifier
in the set.**

### H5 — exactness is verifiability, not recall

**Falsifier:** "exact ranking changes recall@k/nDCG measurably."

**Audit:** Valid but near-tautological. The hypothesis predicts NO change;
the falsifier is ANY change. This is easy to falsify (just show a
difference) but hard to use as evidence FOR the hypothesis (confirming
the null is weak). **Verdict: OK but weak. The value is in the
confirmation, not the falsification. State this honestly.**

### H6 — collective memory requires shared state

**Falsifier:** "per-agent B0 retrieval matches stigmergic propagation on
late-agent success."

**Audit:** Discriminating, but only in a multi-agent setting on a real
shared substrate. The shim-vs-substrate confounder applies. **Verdict: OK
with the caveat that the shim must be validated first.**

### H7 — rescue rule (corrected above)

**Old falsifier:** "violation branch unreachable by construction." NOT a
falsifier — it is an observation.

**New falsifier:** "ablate the rescue loop, replace with a post-scoring
filter that adds REINFORCED memories back if excluded as INHIBITED, and
outcomes are identical." This IS falsifiable: identical → rescue is a
post-hoc filter (H7 falsified); different → rescue has a propagation
effect (H7 survives). **Verdict: corrected, now discriminating.**

---

## Summary of corrections

| Issue | Was | Now |
|---|---|---|
| Rescue invariant | "may be vacuously true" | True by construction (not vacuous); but functionally a post-hoc filter (rescue runs after BFS, no re-propagation). The research question is whether it differs from a metadata filter, not whether the fuzzer can violate it. |
| B1/B2 | Vague "metadata rerank" / "hybrid retrieval" | B1 = raven's scoring formula minus dynamics terms, same metadata, same contradiction detection. B2' = B2 + B1 metadata = strongest adversary. Discriminating question: set composition, not just ranking. |
| H7 falsifier | "violation branch unreachable" (observation, not falsifier) | "ablate rescue, replace with post-hoc filter, outcomes identical" (real falsifier) |
| H2 falsifier | "derivable from retrieval-only outputs" (vague) | "remove target from corpus, re-run top-k, compare delta to intervention delta" (concrete) |
