# Exp52: Raven Suppression Semantics and Causal Isolation

## Status and scope

**PROPOSED, preregistered before execution.** This isolated experiment uses
only the copied Raven implementation and synthetic fixture from Exp51. It does
not edit `sources/`, product code, or an original Raven working tree. No
personal memories, network, models, credentials, or external services are
used.

## Question and rival explanations

Does excluding a memory from returned results also prevent it from changing
other retrieval results? After a memory participates in one controlled
experience, do its effects remain observable in the other stored memory rows
after deleting it and all of its incident links?

The simpler alternatives are that result filtering already removes all causal
influence, and that deleting A plus its incident links restores the same
observable state as a matched branch in which A was suppressed from the
experience. A null result counts against the stronger claim that this fixture
retains an observable history after that deletion operation.

## Contracts under test

1. **Result exclusion:** A is absent from the returned ranked memories. This
   contract says nothing about A's influence on other rows.
2. **Influence exclusion:** A cannot alter scores or ranking of any non-A
   memory through the tested recall paths. For this test, field suppression
   and removal of A from `current_turn_memories` define the experiment-only
   policy. The paired oracle compares the full non-A score vector with the
   vector from the same suppressed query with no current-turn source.
3. **Operational historical erasure:** after a paired history, delete A and
   all synaptic and cell links incident to A in both branches, then apply the
   same post-deletion schedule. The branches are equivalent only if their
   remaining persistent state and their scored outputs match exactly at every
   checkpoint. This finite operational test does not claim metaphysical or
   universal erasure.

## Fixture and fixed inputs

- Reuse Exp51's four synthetic entries, vectors, explicit links, exact KDTree,
  and fixed clock. Record the Exp51 seed digest and source commit in the run
  artifact.
- Suppression probe: query `B`, `top_k=4`, `hops=2`, `now=1001`, and A as the
  sole `current_turn_memories` source. Compare raw Raven suppression,
  experiment-only influence suppression, and a no-current-source negative
  control on the same immutable database state.
- Paired-history probe: clone the same seed into two branches. Both receive
  query `B` at step 1. The exposed branch allows A to participate as the
  current-turn source; the control branch suppresses A and filters it from
  current-turn sources. Apply Raven's ordinary STDP and activation updates
  using each branch's resulting retrieval. Then delete A and all incident
  synaptic and cell links in both copies.
- Apply the same four post-deletion queries (`B`, `C`, `D`, `B`) at fixed
  times. Use `B` as the same current-turn source in both branches at every
  step so the future input schedule is fixed rather than branch-derived.
- Read-only score probes use `_recall_core()` and do not apply writes.

## Predictions and falsifiers

- The result-exclusion prediction is that raw suppression omits A but may
  still return C through a synaptic pull from A. If A is returned, result
  exclusion itself failed. If no such C pull occurs, the claimed leak is
  falsified for this fixture and input.
- The influence-exclusion prediction is that the non-A score vector under
  the experiment-only policy equals the no-current-source negative control
  exactly. Any mismatch falsifies the adapter's claimed isolation. The raw
  suppressed-source vector is recorded separately; if it matches the
  negative control, the influence-leak hypothesis is falsified for this
  fixture.
- The historical-erasure prediction is that deleting A and incident links
  yields exact equality between the branches in remaining persistent rows and
  all post-deletion output score vectors. Any discrepancy falsifies this
  operational erasure claim for the measured state and schedule. Equality
  does not prove universal erasure or absence of unobserved state.

## Analysis limits

This tests one source snapshot, one synthetic four-memory field, one
experience before deletion, and four fixed post-deletion queries. It does not
measure downstream agent decisions, real workload embeddings, concurrent
calls, every public API path, or arbitrary later schedules. All non-trivial
claims in the report must be marked OBSERVED, INFERRED, PROPOSED, or UNKNOWN
and source mechanism claims must cite `sources/raven-memory/` lines.
