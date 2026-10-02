# Phase 5 — Intervention model candidates

> These are EXPERIMENTAL ANALOGIES, not biological claims. We do not claim
> biological fidelity, do not claim an agent has a brain, and do not import
> biological mechanisms because the analogy is attractive. Every intervention
> corresponds to an explicit computational mechanism and a measurable
> hypothesis. Avoid biological terminology where it implies biological
> equivalence we have not established.
>
> raven-memory already implements a selective intervention primitive
> (`InterventionSpec`, `raven/intervention.py`). It is the starting point,
> not a blank slate. MNEME's counterfactual worlds are the systemic-side
> complement. This phase proposes the candidate set; it does not implement.

---

## 0a. Prior art — we are not the first to "drug" an agent (OBSERVED)

Computational neuromodulation for memory/agents is an existing line of work.
This changes our research question from "can we drug an agent?" (answered:
yes, others do) to "can we do it with causal attribution, dose, duration,
washout, provenance, and verifiable counterfactuals, and demonstrate what
properties it produces vs strong retrieval?"

- **ZenBrain** describes a `NeuromodulatorEngine` with channels inspired by
  dopamine, noradrenaline, serotonin, and acetylcholine, modulating memory
  lifecycle. Reports ablations and comparison against static RAG.
  (TD Commons dpubs_series/9732)
- **Living Mind Cortex** implements a "Hormone Bus" with nine signals
  (dopamine, serotonin, cortisol, adrenaline, noradrenaline, acetylcholine,
  endorphin, melatonin, etc.) altering behavior and memory dynamics.
  (github.com/NovasPlace/living-mind-cortex)
- **Optogenetics as experimental paradigm** (PubMed 29742814): the analogy
  has foundation as an experimental paradigm — optogenetics allows
  selective activation/inhibition to observe causal effects on
  learning/memory. We adopt the paradigm structure, not the biology.

### What this changes

The question is no longer "can we drug an agent" — it is:

> Can we define selective and systemic computational interventions over
> persistent memory with causality, dose, duration, washout, provenance,
> and verifiable counterfactuals, and demonstrate experimentally what
> properties they produce vs strong retrieval?

MNEME becomes load-bearing here: it lets us trace
**what state altered → what memories were affected → what recalls changed
→ what decision consumed those memories → what the decision would have
been in the control world.** That is a protocol, not a `dopamine = 0.7`
variable.

### The slider-vs-pharmacology cruelty test (PROPOSED)

Every systemic intervention must pass this test:

> If `reinforcement *= 0.6 for five decisions` produces exactly what
> statically modifying a reranker weight produces, we invented a slider,
> not agent pharmacology.

The intervention earns its name only if a temporal intervention leaves a
**different trajectory after washout** — because it changed consolidation,
plasticity, or future relations:

```
t0 ─────── t1 ─────────── t2 ─────────── t3
 baseline   intervention    washout        later recall
                │
                └── state transition
                              │
                              └──────────────► persistent downstream effect
```

If post-washout behavior is identical to baseline, the intervention was a
temporary reranker change with extra steps. If it differs, the intervention
altered the memory system's future state — that is qualitatively different
from "during t1 we used a different ranking."

This criterion applies to ALL systemic interventions (Y1-Y5 below).

---

## 0b. What already exists (OBSERVED)

- **Selective, raven:** `InterventionSpec(mode="suppress", targets=[memory_ids],
  stage="field")`. Read-only probe. Measures retrieval causal influence
  `I(c,q)=D(R(q), R(q|do(c=0)))`, decomposed (disappeared/appeared/
  rank_displacement/score_delta). Authority: probe ≠ stimulation ≠ learning;
  no STDP, no state transition, no reinforcement. Single `now`, single lock
  → deterministic Δ. `intervention.py`, `memory_engine.py:2026`.
- **Systemic, MNEME:** counterfactual worlds produce exact deltas between two
  sealed field states. Quarantine is a systemic containment (write barrier +
  retrospective sweep). Reinforcement α=1/4 and promotion threshold 3/4 are
  systemic parameters. `counterfactual.py`, `custody.py`.
- **Systemic, STIGMERGY:** recruitment decay rate, migration cooldown,
  hysteresis thresholds are systemic parameters. `controller.py`, `ops/`.

## 1. Distinction (PROPOSED)

- **SELECTIVE intervention:** target a specific memory / relation / cluster /
  pathway and alter its ability to participate in recall or influence.
  raven's `suppress` is the implemented example.
- **SYSTEMIC intervention:** temporarily modify a defined memory-dynamics
  parameter or policy across the field (decay rate, reinforcement rate,
  promotion threshold, gate strictness, propagation depth).

Both must be explicit, inspectable, and reversible where possible.

## 2. Candidate selective interventions (PROPOSED)

For each: target, mechanism, duration, expected effect, measurable outcome,
side effects, control, counterfactual, falsifier.

### S1 — suppress (implemented in raven)
- target: a set of memory_ids (resolved to cells).
- mechanism: remove targets from seed/propagation/readout (stage=field).
- duration: one recall (transient, read-only).
- expected effect: targets' contribution to R(q) drops; dependents demoted.
- measure: decomposed Δ (disappeared/appeared/rank_displacement/score_delta).
- side effects: none on persisted state (read-only by construction).
- control: `targets=[]` → Δ=0 exactly (negative control, OBSERVED).
- counterfactual: R(q) vs R(q|do(c=0)).
- falsifier: Δ is always 0 for every target set (no memory has retrieval
  influence). NOTE: raven already found influence manifests as rank descent,
  not deletion — so "disappeared=0" is expected; "rank_displacement=0" is the
  real falsifier.

### S2 — excite / boost (NOT implemented; reserved in raven's type)
- target: a memory_id / cluster.
- mechanism: transiently raise a target's state multiplier or synaptic weight
  for one recall (read-only w.r.t. persisted state — a *probe* boost, not a
  *learning* boost).
- duration: one recall.
- expected effect: target and its RESONANT neighbours rise in ranking.
- measure: rank improvement of target + neighbours; spread via propagation.
- side effects: must NOT write STDP/activations (authority boundary).
- control: boost a random irrelevant memory → no systematic change.
- counterfactual: R(q) vs R(q|do(c=boost)).
- falsifier: excitation changes nothing that suppression didn't already
  explain (symmetric, redundant).

### S3 — link cut (PROPOSED)
- target: a specific RESONANT/INHIBITORY link.
- mechanism: temporarily disable one edge during BFS.
- duration: one recall.
- expected effect: the pathway through that edge stops carrying
  amplification/suppression.
- measure: Δ on memories reachable only through that edge.
- side effects: none persisted.
- control: cut a link on an irrelevant path → no change.
- counterfactual: R(q) vs R(q|do(edge=absent)).
- falsifier: single-link cuts never change R(q) (graph is too redundant —
  consistent with raven's symmetrized k-NN finding, OBSERVED).

### S4 — cluster silence (PROPOSED)
- target: a cluster (e.g. a topic's memories, or a region).
- mechanism: suppress all cells in a cluster at once.
- duration: one recall.
- expected effect: the cluster's whole contribution drops; tests whether
  influence is per-cell or per-pathway (combinatorial ablation, raven already
  has the runner).
- measure: Δ; classify REDUNDANT_PATHS / SINGLE_NECESSARY / MULTIPLE_NECESSARY.
- side effects: none persisted.
- control: silence a random cluster of equal size.
- counterfactual: R(q) vs R(q|do(cluster=0)).
- falsifier: REDUNDANT_PATHS never observed (already an open hypothesis,
  OBSERVED INTERVENTION_DESIGN.md:369-371).

## 3. Candidate systemic interventions (PROPOSED)

### Y1 — propagation depth (hops)
- target: the BFS hop budget (raven `HOP_LAMBDA`/hop count).
- mechanism: set hops=0 (flat top-k) … hops=N.
- duration: a run / a phase.
- expected effect: deeper propagation → more rank displacement under
  suppression; recall quality may rise or fall.
- measure: recall@k across hop settings; causal-influence magnitude.
- side effects: latency rises with hops; risk of noise propagation.
- control: hops=0 (B0-equivalent).
- counterfactual: same field, same queries, varying hop budget.
- falsifier: recall quality is flat across hop settings (propagation adds
  nothing to retrieval).

### Y2 — reinforcement rate / promotion threshold (MNEME α, threshold)
- target: REINFORCEMENT_ALPHA (1/4) and PROMOTION_THRESHOLD (3/4).
- mechanism: vary α and threshold; observe how fast/loose memories promote.
- duration: a learning phase.
- expected effect: looser promotion → faster collapse-around-truth but more
  false promotions; tighter → slower but safer.
- measure: collapse latency; false-promotion rate; contradiction resistance.
- side effects: over-promotion can silence valid alternatives.
- control: α=0 (no reinforcement) → B0-with-states-NEUTRAL.
- counterfactual: same evidence stream, varying α.
- falsifier: collapse-around-truth happens at the same rate with α=0 (states
  do nothing without reinforcement).

### Y3 — decay / forgetting rate
- target: recency half-life (raven) / forgetting policy.
- mechanism: vary half-life; observe stale-memory serve rate vs recall of
  genuinely-relevant old memories.
- duration: a time-advanced simulation.
- expected effect: faster decay → fewer stale memories served, but risk of
  forgetting relevant old ones.
- measure: stale-serve rate; recall of relevant-old; interference behaviour.
- side effects: over-forgetting (the failure mode to watch for).
- control: infinite half-life (no decay) → B0-like.
- counterfactual: same corpus aged, varying decay.
- falsifier: decay hurts recall of relevant-old memories more than it helps
  stale-suppression (forgetting is net negative).

### Y4 — gate strictness (MNEME containment)
- target: the recall gate (CLEAN-only) and graph-gate (both endpoints CLEAN).
- mechanism: serve-only gate vs serve+graph gate vs no gate.
- duration: a contamination scenario.
- expected effect: graph-gate prevents tainted nodes from perturbing clean
  rankings (OBSERVED risk: serve-only gate leaves this hole).
- measure: tainted-influence rate on clean memories' rankings.
- side effects: over-gating (clean memories wrongly excluded).
- control: no gate (B0).
- counterfactual: same tainted field, varying gate strictness.
- falsifier: graph-gate changes no clean-memory ranking that serve-only didn't
  already handle (the hole is theoretical).

### Y5 — recruitment decay / cooldown (STIGMERGY, multi-agent only)
- target: recruitment signal decay rate; migration cooldown.
- mechanism: vary decay; observe propagation to late agents and oscillation.
- duration: a multi-agent run.
- expected effect: slower decay → late agents benefit more; no cooldown →
  oscillation.
- measure: late-agent task success; oscillation count.
- side effects: stale signals mislead late agents if decay too slow.
- control: no recruitment (B0-per-agent).
- counterfactual: same task sequence, varying decay.
- falsifier: propagation adds nothing over per-agent B0 (collective memory
  not needed) OR oscillation occurs regardless of cooldown.

## 4. Authority boundaries (PROPOSED, inherited from raven OBSERVED)

- A probe is read-only: no STDP, no state transition, no reinforcement, no
  persisted links, no activation timestamps. (raven's invariant.)
- Stimulation (writing plasticity via intervention) is a *different operation*
  with its own name and authority — never shares the probe type.
- Systemic parameter changes during a run must be recorded in the audit chain
  so the run's configuration is reconstructable.
- An intervention that could fabricate associations (false engrams) is the
  primary security risk and is out of scope for the probe class.

## 5. What would falsify the intervention research program (PROPOSED)

- If S1 (suppress) Δ is always 0: memories have no causal influence on
  retrieval → the "causal attribution" property is vacuous.
- If every selective intervention's effect is fully reproduced by a metadata
  filter in B1: the dynamics add no causal power that retrieval+metadata lacks.
- If systemic interventions (Y1-Y3) change recall but never in a direction
  that a reranking baseline (B2) couldn't match: dynamics are parameter tuning
  with extra steps — "pharmacological intervention adds no research
  contribution" (a valid outcome per the brief).
- If graph-gate (Y4) changes nothing over serve-only: the containment property
  is already captured by a metadata filter.

Any of these is a successful research result if supported by evidence.
