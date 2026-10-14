# Memory Lab: Temporary Interventions in Agent Memory

Memory Lab is the research track asking what happens when an agent's stored
memories, associations, or learning dynamics are changed for a limited time.
It treats each intervention as a falsifiable operation on a memory system and
asks what remains after the intervention ends.

This is a research guide, not a clinical analogy, a product specification, or
an intervention API. The word *pharmacology* appeared as an informal design
metaphor. The working term in this repository is **agent-memory intervention**:
it names a computational operation without implying that it reproduces a
biological drug or mechanism.

## The question

Can a memory become available again without regaining the causal role it had
before it was absent?

The experiments distinguish three operations:

| Operation | Meaning in this research |
|---|---|
| **Re-exposure** | Make the memory's content available again in the current system state. |
| **Restoration** | Reinstate selected saved fields from an earlier state. The rest of the agent is not rewound. |
| **Relearning** | Let later experiences build new associations and reinforcement under the declared transition rules. |

These operations may yield the same immediate retrieval result while producing
different future trajectories. They may also converge. Either outcome is
valid; the experiments are designed to allow the distinction to disappear.

## Intervention vocabulary

The earlier design discussion used pharmacology-inspired names for candidate
operations. They remain **PROPOSED** computational interventions, not
implemented Raven capabilities or claims about biology.

| Candidate operation | Computational question |
|---|---|
| Selective inhibition | Can one memory, association, or cluster be prevented from influencing a defined operation? |
| Reactivation or rescue | Can a stored memory become available again, and does it regain propagation or causal influence? |
| Reinforcement blocking | What changes if retrieved experiences do not strengthen future state? |
| Decay modulation | How does changing a declared decay rule affect later retrieval and state? |
| Consolidation modulation | Which experiences become persistent under a changed consolidation rule? |
| Propagation modulation | How does changing association spread affect other memories and decisions? |
| Systemic intervention | Does changing multiple declared dynamics produce an effect that cannot be reduced to a static ranking-weight change? |

Names such as dopamine, serotonin, noradrenaline, or acetylcholine are not
mechanism labels for this system. They may be analogies for shared modulatory
signals, but that connection remains **PROPOSED** and would need an explicit
computational definition and falsifier.

## The causal model

H14 asks whether restoring a memory restores its former causal influence. Its
comparison keeps these components separate:

```text
intervention
    → memory state and links
    → retrieval and propagation
    → later state updates
    → decision-relevant observations
    → comparison with a matched counterfactual branch
```

Restoring the state of one memory does not rewind the rest of the agent.
Other memories may have changed during the absence, so those differences are
outcomes of the intervention history. Re-exposure, local state restoration,
link restoration, and relearning therefore remain separate branches.

An experiment must say which observations define equivalence. Exp48–50
minimized a finite synthetic machine under a declared query alphabet. Exp51–54
show why a Raven transfer assay needs a wider contract: score/rank outputs,
inspection, telemetry, export, and state-changing operations can distinguish
states that fixed retrieval queries do not. See the individual reports for
their finite scopes and source citations.
The source-grounded inventory and proposed nested contracts are in the
[Raven observational contract](RAVEN_OBSERVATIONAL_CONTRACT.md).

## What has been tested

All claims below are scoped to the cited experiment. `OBSERVED` means the
recorded run or inspected snapshot supports the statement; it does not imply
transfer to another implementation.

| Experiments | Status and contribution |
|---|---|
| [Exp36](../experiments/exp36_h14/) · [Exp37](../experiments/exp37_h14_measurement/) | **OBSERVED, synthetic:** the first restoration assay and a signed contribution measure. Exp36 is retained as historical evidence; its limitations are documented. |
| [Exp38](../experiments/exp38_h14_mediation/) · [Exp39](../experiments/exp39_h14_cycles_inhibition/) · [Exp40](../experiments/exp40_h14_threshold_rescue/) | **OBSERVED, synthetic:** successive falsifiers showed that one-step neutralization, finite path expansion, and rescue availability each miss different propagation behavior in the tested models. |
| [Exp41](../experiments/exp41_h14_rescue_function/) · [Exp42](../experiments/exp42_h14_longitudinal/) · [Exp43](../experiments/exp43_h14_latent_trace/) · [Exp44](../experiments/exp44_h14_update_rule_falsifier/) | **OBSERVED, synthetic:** separated availability from propagation, followed trajectories through washout, and tested whether residual associations added predictive information beyond the represented state. The update-rule controls bounded the latent-trace claim. |
| [Exp45](../experiments/exp45_h14_sufficient_state/) · [Exp46](../experiments/exp46_h14_history_collisions/) · [Exp47](../experiments/exp47_h14_state_characterization/) · [Exp48](../experiments/exp48_h14_observational_quotient/) · [Exp49](../experiments/exp49_h14_quotient_congruence/) · [Exp50](../experiments/exp50_h14_partition_refinement/) | **OBSERVED, finite synthetic machine:** state projections were challenged with history collisions, observational quotients, transition congruence, and a partition-refinement certificate. The minimality result applies only to that declared machine, seed closure, input alphabet, and observations. See the [Exp48–50 report](H14_EXP48_50_MINIMIZATION.md). |
| [Exp51](../experiments/exp51_raven_h14_longitudinal/) · [Exp52](../experiments/exp52_raven_suppression_semantics/) | **OBSERVED, copied Raven snapshot and synthetic fixture:** suppression as result exclusion did not guarantee source-influence exclusion in the tested path. Deleting a memory and incident links left a counter difference, while four fixed retrieval probes matched. |
| [Exp53](../experiments/exp53_raven_latent_trace/) · [Exp54](../experiments/exp54_raven_observational_contract/) | **OBSERVED, copied Raven snapshot and synthetic fixture:** `recall_count` was visible outside retrieval; five selected same-input actions preserved the four-query retrieval equivalence. Reversing physical SQLite row order changed the tied winner of the truncated graph export in this fixture. |
| [Exp55](../experiments/exp55_raven_counter_consolidation/) | **OBSERVED, copied Raven snapshot and synthetic fixture:** a stored `recall_count` difference alone did not change real consolidation or later C/D retrieval. A canary that changed audit-derived counts did change the merged embedding and later scores. Five tests passed, including a counter-source mutation check. |
| [Exp56](../experiments/exp56_raven_audit_projection/) | **OBSERVED, copied Raven snapshot and synthetic fixture:** changing audit event order or query text at fixed per-memory counts did not change consolidation-derived retrieval outputs; changing count allocation did. Audit histories stayed distinguishable. Four tests passed, including an order-sensitive mutation and replay check. |
| [Exp57](../experiments/exp57_raven_temporal_recency/) | **OBSERVED, copied Raven snapshot and synthetic fixture:** assigning identical per-memory recall counts to different timestamps changed pre-consolidation retrieval through recency. Equalizing timestamps removed the difference; consolidation produced matching merged embeddings/traces with zero recency. Five tests passed, including a zero-recency mutation and replay check. |
| [Exp58](../experiments/exp58_raven_postconsolidation_replay/) | **OBSERVED, copied Raven snapshot and synthetic fixture:** eight identical post-consolidation recall calls preserved equal outputs and memory/link state across branches with different audit histories. Each branch's audit chain remained valid, and a recency-state mutation was detected. Five tests passed, including replay. |

**INFERRED:** the experiments establish that observational equivalence depends
on the operations and outputs included in the observer. They do not establish
that agent memory interventions have a useful downstream effect, that
Raven's behavior generalizes beyond the copied snapshot, or that H14 is true.

## Naming and scope

Use **Memory Lab** as the friendly name for this research line and
**agent-memory intervention** for an individual operation. Use *computational
pharmacology* only when discussing the motivating metaphor, and identify it as
a metaphor. Avoid naming an operation after a clinical drug or condition
unless a later study provides a precise, justified mapping.

The following boundaries are part of the research record:

- No experiment in this series treats a person or models clinical treatment.
- Synthetic fixtures and copied source snapshots are not deployed agents.
- A changed score, ranking, counter, or export is not automatically a changed
  decision or a beneficial effect.
- A washout is an experimental schedule, not proof that every effect has ended.
- A restoration branch changes only the fields declared by that branch; it
  does not reconstruct a full no-absence counterfactual unless that branch is
  explicitly maintained.

## Threat model for future intervention tooling

An intervention interface could be abused to suppress or amplify selected
memories, implant persistent associations, bias later decisions, or hide those
changes behind an apparently temporary operation. Those are **PROPOSED threat
scenarios**, not findings that an existing Memory Lab API is vulnerable; no
such API has been built.

Candidate safeguards for any future research harness are **PROPOSED**:

1. Run on disposable, synthetic or explicitly authorized snapshots; never
   silently target a live agent's personal memory.
2. Restrict operations to a reviewed allowlist with explicit target scope,
   duration, intensity, and affected state fields. Do not accept executable
   intervention code from an untrusted caller.
3. Require an authorized operator and record the intervention definition,
   input state digest, execution, washout, and resulting state differences.
4. Keep branches isolated; enforce resource limits and prevent one branch from
   writing into another or into the source snapshot.
5. Define a reversal or recovery procedure before running an intervention,
   while recording that rollback of stored fields cannot erase downstream
   decisions already made.
6. Test both intended and adversarial cases, including hidden persistence,
   scope expansion, repeated dosing, and combinations that bypass individual
   limits.

These safeguards are design proposals, not implemented controls. Security
claims require a separate threat model and falsifiable tests before any
intervention tooling is exposed.

## How to follow the work

- [Experiment index](EXPERIMENTS.md) — sequence and current research record.
- [H14 real-system transfer audit](H14_REAL_SYSTEM_TRANSFER_AUDIT.md) — what
  source inspection does and does not support for Raven, MNEME, and Stigmergy.
- [Raven observational contract](RAVEN_OBSERVATIONAL_CONTRACT.md) —
  observed REST/MCP/engine surfaces and proposed equivalence scopes for a
  future bounded assay.
- [Exp48–50 minimization report](H14_EXP48_50_MINIMIZATION.md) — formal scope
  for the synthetic finite-machine result.
- [Hypotheses](HYPOTHESES.md) and [stop conditions](STOP_CONDITIONS.md) —
  falsifiers and research boundaries.

**Current status — OBSERVED:** Exp58 is the latest recorded assay in this
line. H14 remains open; there is no demonstrated transfer of restoration
effects to a deployed agent. The Exp54–58 results are bounded to selected
operations in one copied Raven snapshot and synthetic fixtures.
