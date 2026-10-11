# Proposed Study: Memory Re-exposure, Restoration, and Relearning

Status: **H14 protocol PROPOSED and not preregistered. An independent toy assay (Exp36) has been implemented and run; it is not Raven/MNEME evidence.**

The verification, toy result, provenance, and protocol deviations are recorded in
[the Phase 11 review](../research/PHASE11_H14_TOY_ASSAY.md).

This document records the reasoning and proposed design for a follow-up
experimental question in Remember the Seasons. It does not authorize product
implementation or claim a biological analogue.

## 1. How the question narrowed

The discussion began with a broad metaphor: temporary "drugs" that could
modulate agent memory by suppressing, rescuing, reinforcing, or changing decay
and consolidation. The first scope decision was to avoid a catalogue of
fictional substances and ask what property the interventions should help us
measure.

The focus narrowed to the distinction between memory availability and memory
function. Reintroducing a memory may make its content retrievable without
restoring its former causal influence. During its absence, other memories can
change, decisions can differ, and the system can follow another trajectory.

The maintainer chose to treat links incident to the target memory as shared
system state rather than as an exclusive property of that memory. Restoring
those links is retained as a separate experimental factor because it changes
relationships involving other memories.

The working term in this document is **memory intervention**. "Drug" or
"pharmacology" may remain an informal analogy, but neither is evidence of a
biological mechanism. No neurodegenerative disease or clinical treatment is
being modeled.

## 2. Research question and epistemic status

**PROPOSED — primary question:** After target memory A undergoes functional
absence, how much of its pre-absence causal influence returns under re-exposure,
restoration of A's intrinsic state, restoration of incident links, or
relearning, compared with a matched trajectory in which A was never absent?

**OBSERVED — prior work in this repository:** Persistent adaptive state can
produce path dependence in the minimal retrieval baseline, with Raven machinery
amplifying the observed effect. Therefore, the follow-up must not treat
path-dependence alone as novel evidence for a distinct pharmacological
mechanism. See [the experiment summary](EXPERIMENTS.md#current-state-of-the-research)
and [the H12/H13 ledger](HYPOTHESES.md).

**UNKNOWN:** Whether restoring A and all of its pre-absence incident links
restores A's causal influence when the rest of the agent has evolved during
A's absence. If it does not, the state components of the rest of the agent
that explain the residual are also unknown.

## 3. Keep the operations distinct

| Operation | A's intrinsic state | Incident links | Learning after return |
|---|---|---|---|
| Re-exposure | Initialized as new under the declared engine rule | Historical links are not restored | Normal learning resumes |
| Strict local restoration | Restored from the pre-absence snapshot | Kept at their post-absence state; no historical link restoration | Normal learning resumes |
| Link restoration | Factorial combination with intrinsic-state restoration on/off | Pre-absence links restored as a separate system-state intervention | Normal learning resumes |
| Relearning | Initialized without importing pre-absence state | New links arise from post-return experience | The target is encountered through new experiences |

"Strict local" describes the scope of the restored object, not the causal
scope of the outcome. The rest of the agent is not reset. Link restoration is
not fully local because it changes shared relationships.

The factorial portion is a 2 × 2 comparison:

| Intrinsic state restored? | Historical links restored? | Interpretation |
|---|---|---|
| No | No | Re-exposure baseline |
| Yes | No | Strict local restoration |
| No | Yes | Link-only restoration |
| Yes | Yes | Intrinsic state plus link restoration |

Relearning is a separate process arm, not a cell in this factorial. Match the
number and schedule of new target exposures to a declared protocol; do not copy
the target's old state or links into this arm.

## 4. Absence interventions

### Primary: functional absence

During the intervention window, A remains present in the historical and
forensic record but is functionally absent:

- A is not retrieved and cannot contribute directly or indirectly to a
  decision.
- A receives no reinforcement, inhibition, or associative updates.
- Incident links remain recorded but do not transmit activation through A.
- The rest of the agent receives no direct reset or forced state change; its
  normal updates continue. Differences in its later state are outcomes of the
  trajectory, not additional manipulations.

In the primary protocol, freeze each incident link at its last valid
pre-absence value and disable propagation through A. This prevents unrecorded
link drift while A is excluded. Decide before applying the protocol elsewhere
whether that system's edge-update rules require different semantics.

Exp36 does not follow this freeze rule: it explicitly ages incident links
during absence. Exp37 is a separate toy assay that freezes those links and
records signed action-score effects. See the Phase 11 assay records for each
run and their respective limits.

### Secondary, deferred: retrieval absence only

A is blocked from influencing decisions but may continue to receive updates
under rules declared in advance. This isolates loss of access from loss of
plasticity, but adds another variable. Keep it out of the first factorial and
test it in a later comparison against functional absence.

## 5. Counterfactual and measurement

Create paired branches from the same initial field, target, exogenous task
stream, intervention start, and random seed. The reference branch keeps A
available and lets it evolve normally for the same interval. Do not compare
only with A's initial influence: A may have changed naturally during that
interval even without absence.

At the end of the window, fork the absent branch into the four factorial
conditions and the separate relearning arm. The rest of each branch retains
the state it naturally reached. Do not copy the reference branch's other
memories into a restoration arm.

For each branch and each fixed probe query, record the paired decision with A
active and with A's contribution neutralized in a frozen copy of that exact
branch state. Neutralization must suppress A's activation and propagation
without deleting its node, deleting edges, rebuilding the graph, or changing
other memories. This estimates A's total direct-plus-propagated influence in
that branch. Edge effects are separately identified by the factorial arms.

Measure a **query-indexed vector of paired decision effects**, not a
retrieval rank or a single average accuracy score. Preserve each decision's
choice and direction. If the downstream decision model is stochastic, use
matched seeds and repeated runs to estimate its noise floor; do not collapse
model noise into a memory effect.

Exp36 records only a binary flip/no-flip indicator per query. Exp37 records
the action scores with A active and neutralized, the signed score difference
for each action, the signed X-minus-Y margin effect, and both choices. These
are exact quantities in a synthetic scoring rule; they are not yet validated
as an appropriate measure for Raven or MNEME. See the Phase 11 assay reports.

Use two measurement modes and report them separately:

1. **Frozen-state probes:** apply the same probe set to snapshots without
   allowing probes to update memory. This estimates current causal influence.
2. **Longitudinal continuation:** resume normal updates under a shared
   exogenous task schedule. Decisions may differ and later memory changes may
   follow from those decisions; those are trajectory effects to explain, not
   confounds to erase.

The main restoration comparison is each post-absence influence vector against
the no-absence reference at the same elapsed time. A pre-absence measurement
is also retained as a descriptive baseline, not used as the sole
counterfactual.

## 6. Hypotheses and falsifiers

### H14 — Reintroduction does not necessarily restore causal function

**PROPOSED:** Re-exposure, intrinsic-state restoration, incident-link
restoration, and relearning can yield distinguishable influence vectors after
functional absence. Restoring A and its historical links may still fail to
match the no-absence reference because the rest of the agent followed another
trajectory.

**Simpler alternative:** These operations are equivalent under the tested
system, or any differences are fully explained by a static retrieval/ranking
change. Restoration of A and its links is sufficient to recover its
pre-absence causal influence.

**Falsifier:** Under a preregistered equivalence margin and adequate power, all
post-absence operations reproduce the no-absence influence vector, or the
observed differences are reproduced by the declared static retrieval/state
baseline. Either outcome narrows or refutes H14 for this protocol.

**Secondary question:** If the combined A-plus-links arm differs from the
reference, which changed state elsewhere in the agent explains the residual?
Correlations in logs are not enough. First localize candidate state
differences; then intervene on one candidate component at a time, or use
factorial replay, while holding other components fixed. A component counts as
a causal explanation only if its controlled restoration changes the
influence vector as predicted.

## 7. Threats to validity and safeguards

- **Absence conflated with deletion:** keep A and all events in the forensic
  record; disable participation through an explicit intervention state.
- **Graph rebuild changes topology:** retain the graph and node during
  neutralization; do not recompute neighbors as if A had never existed.
- **Whole-world rewind hidden inside restoration:** restore only the declared
  A-state and/or link-state factor. Never reset the rest of the branch in the
  primary comparison.
- **Endogenous branch divergence erased:** share exogenous inputs, not
  decisions or state updates that are consequences of prior branch decisions.
- **Probe contamination:** use frozen snapshots for direct influence
  measurement; report longitudinal behavior separately.
- **LLM randomness mistaken for a treatment effect:** paired seeds, repeated
  runs, a sham/no-treatment noise estimate, and preregistered outcome margins.
- **Biological analogy overstated:** report computational state transitions
  and behavioral effects only. A resemblance in vocabulary is not a validated
  biological mechanism.

For misuse resistance, treat intervention definitions as inert experimental
data. An agent, retrieved memory, web page, tool result, or other agent's
message must not be able to authorize, expand, or compose interventions.
Any later harness should enforce scope, target, duration, and intensity in
deterministic policy outside the model; record the authorizing principal and
the full intervention provenance; and begin with isolated synthetic fields
without secrets or external side effects. This is a research constraint,
not an implementation specification.

## 8. Decision trail and alternatives

| Choice | Reason | Alternative deferred or rejected |
|---|---|---|
| Study rescue/restoration before a catalogue of interventions | It gives one discriminating question: availability versus recovered causal influence | A broad list of fictional substances would multiply mechanisms before the target property is clear |
| Make functional absence the primary intervention | It blocks both decision influence and target plasticity, testing loss of influence plus consolidation opportunity | Retrieval-only absence is retained as a later comparator because it isolates access but leaves plasticity active |
| Keep A in the forensic history | Deletion would conflate functional absence with loss of evidence and would obstruct reconstruction | Physical erasure is outside this experiment |
| Treat incident links as shared state | A link describes a relation involving other memories; restoring it changes shared state | Bundling links into A's local snapshot would hide that extra intervention |
| Leave the rest of the agent on its branch-specific trajectory | Other-memory changes are plausible consequences of A's absence and part of the question | Copying the control world's rest state would erase the trajectory under study |
| Avoid biological and clinical claims | No biological mechanism is being measured | Neurodegenerative disease and medication analogies are not evidence for the computational result |

These choices are **PROPOSED and reversible**. Reopen them if the target
engine's update semantics make functional absence internally inconsistent,
if the history-preserving intervention cannot be represented, or if a
preliminary discrimination test shows that the proposed causal measure cannot
separate the arms.

## 9. Decisions still required before preregistration

- Enumerate exactly which fields count as A's intrinsic state in the chosen
  engine; keep incident links outside that list.
- Specify how a re-exposed instance is identified and linked to A's historical
  record without importing old state.
- Specify exposure matching for the relearning arm and what evidence counts as
  a learning opportunity.
- Freeze probe queries, downstream decision rule, random seeds, sample size,
  equivalence margin, and the primary vector-distance/statistical procedure.
- Declare treatment duration, washout duration, intervention intensity, and
  the rule that resumes normal updates.
- Decide which candidate non-A state components can be tested in a later
  mediator experiment.

Until these are fixed, the full H14 study remains a proposed question, not
a registered experiment or a result. The independent Exp36 toy assay is
exploratory and does not implement Raven or MNEME. No product implementation,
clinical claim, or novelty claim is authorized by this document.
