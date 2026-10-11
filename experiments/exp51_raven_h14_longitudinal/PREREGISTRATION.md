# Exp51: Raven Longitudinal Restoration Pilot — Preregistration

## Status

**PROPOSED, preregistered before execution.** This is an isolated experiment
against a copied Raven source snapshot. It is not product code and does not
modify the read-only source snapshot.

## Research question

Under a fixed Raven implementation, fixed synthetic memory field, fixed query
vectors, fixed clock, and fixed experience schedule, does a temporary,
functional absence of one memory produce later retrieval-contribution or
memory-state differences that remain after re-exposure/restoration and washout?

The simpler alternative is that ordinary retrieval plus Raven's declared
state, ranking, and STDP rules fully explain all observed differences. A null
result, equivalence of all branches, or differences explained entirely by
those recorded variables counts against the stronger H14 transfer claim.

## Epistemic boundary

- **OBSERVED:** Raven's copied `_recall_core()` accepts `suppressed` cell IDs
  and does not itself persist state. `recall()` applies activation and STDP
  effects; `intervene()` compares baseline and suppression against one field
  snapshot and one clock value. Source locations are recorded in
  `PROVENANCE.md`.
- **PROPOSED:** the harness driver applies functional absence over a sequence
  by passing the target through Raven's existing `suppressed` argument and
  applying only the non-target update effects described below.
- **UNKNOWN:** whether the synthetic mechanism and query schedule represent
  any deployed agent workload or downstream agent decision.

## Fixture and controls

- Synthetic IDs and contents only; no personal memories, credentials, network,
  model calls, or external services.
- Fixed, hand-authored 8-dimensional vectors; exact KDTree backend; fixed
  `now` values supplied to `_recall_core()`.
- One identical SQLite seed snapshot is copied for each arm.
- Identical ordered experience/query schedule in all arms.
- Each step records separately: full scored retrieval output, target's signed
  contribution measured by paired suppression on a frozen step snapshot, and
  persistent memory/link state.
- Probe calls use the pure core, do not apply learning, and do not write audit
  rows. They are made after the experience update for that checkpoint.
- No language model or downstream action is used. The outcome is Raven
  retrieval and stored state, not agent behavior.

## Arms

Target memory `A` is present in the initial field.

1. **No absence:** A participates throughout.
2. **Re-exposure:** A is suppressed for the absence window; on re-exposure it
   is made available with neutral state and no incident synaptic/cell links.
3. **Strict local restoration:** A is suppressed during the window; restore its
   pre-absence memory row fields while retaining the branch's evolved state
   everywhere else. Incident links remain at their end-of-window values.
4. **Links-only restoration:** A is suppressed during the window; restore the
   pre-absence synaptic and cell links incident to A while preserving current
   intrinsic A fields and all other branch state.
5. **Complete local restoration:** restore A's pre-absence row and incident
   links; do not restore any other row or global index/state.
6. **Relearning:** A is suppressed during the window; then make it available
   with neutral state and no incident links, and let the common post-window
   experiences update it normally.

The absent window spans experience steps 1–4. Steps 5–8 are common
post-window learning experiences. Steps 9–13 are common washout experiences.
The exact schedule and vectors are encoded in the experiment source and result
artifact.

## Treatment semantics and limitations

The harness implements persistent absence with Raven's field-level suppression
argument, not with Raven's public `forget()` API. During the window, A cannot
seed, relay, fire links, or rank. The driver excludes A from both sides of
STDP updates and activation writes, so the target receives no updates. Other
memories use Raven's ordinary STDP update function on the same experience
inputs, with the target ID removed from current-turn results. The driver is
experiment code; Raven does not expose this longitudinal treatment natively.

For edge restoration, “incident links” means both (a) A's `synaptic_links`
map and other memories' synaptic entries keyed by A's memory ID, and (b)
directed `cell_links` whose source or destination is A's cell. This makes
shared-edge edits explicit. Cell-link restoration updates the copied Raven
database and the engine's in-memory link indices together.

Restoration changes only A and explicitly selected incident links. It never
restores any non-target memory row, global database snapshot, query history,
clock, or branch state. Re-exposure/relearning reset A to neutral, with empty
synaptic links and counters; these are operational arms, not claims about a
biological process.

## Primary outcomes

At each post-window and washout checkpoint:

1. **Retrieval:** ordered memory IDs and every Raven score component for the
   standard query.
2. **Causal retrieval contribution:** signed per-memory score differences
   between the full core and a paired core with A suppressed, measured on the
   same snapshot, query, and `now`. This remains a retrieval-level measure.
3. **State:** A's state, activation time, recall count, synaptic links, all
   directed cell links incident to A, and a digest of non-target rows.
4. **Persistence:** whether any branch differences survive all five washout
   experiences; report exact differences, including zero.

## Falsifiers declared before execution

The transfer claim is not supported by this pilot if any of the following
holds:

- all six arms have identical recorded post-window and washout retrieval
  contribution vectors and relevant state, or restoration arms are equivalent
  to no absence at every measured checkpoint;
- any apparent branch difference vanishes when the stored state and links that
  Raven actually uses are equalized;
- differences occur only in rank/selection while the signed full-score
  contribution vector and state remain equal;
- repeated runs from the same seed produce unequal canonical result artifacts;
- the absence driver permits A to seed, relay, rank, or receive an update during
  the declared absence window;
- mutation controls that bypass suppression or erase the target contribution
  are not detected by tests.

An observed difference alone is not evidence for H14 if it is fully explained
by the recorded Raven state transition, the query schedule, or ordinary
retrieval scoring. This pilot has no downstream decision outcome and cannot
establish persistence in a deployed agent.

## Test integrity plan

- Red-first: assert persistent suppression and update exclusion before
  implementing the driver; run those tests red, then green.
- Negative controls: deliberately bypass suppression and deliberately zero
  the paired contribution readout; the relevant assertions must fail.
- Oracle: exact expected traces for fixed vectors where feasible, plus
  invariants for absence, branch isolation, deterministic replay, and mutation
  detection.
- No mocks for Raven's scoring, database, or STDP implementation. The only
  fixed boundary is the clock, supplied directly to the pure scoring core.
- Known blind spots: finite synthetic field, eight hand-authored dimensions,
  one transition schedule, no LLM/downstream action, no ANN, no concurrent
  writes, and no claim of generalization beyond this copied source version.
