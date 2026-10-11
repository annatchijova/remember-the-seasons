# Exp51 Results: Raven Longitudinal Restoration Pilot

## Result in scope

**OBSERVED, copied Raven implementation with synthetic fixture:** the six
declared arms were executed from copies of one fixed seed snapshot. The run
recorded full scheduled retrieval scores, signed effects on non-target memory
scores under paired suppression, a standardized propagation probe, and
persistent row/link state at four post-window and five washout checkpoints.

**UNKNOWN:** whether these results generalize to a Raven deployment, any
downstream agent action, or a workload with real memories and production
embeddings.

## Source-level suppression finding

**OBSERVED:** the copied Raven source documents that a suppressed cell cannot
fire links (`sources/raven-memory/raven/memory_engine.py:1635-1639`). The
current-turn synaptic pull loop reads `current_turn_memories` as sources and
does not filter a source merely because its cell is suppressed; it filters
suppressed linked targets (`sources/raven-memory/raven/memory_engine.py:1855-1888`). In the synthetic
fixture, raw suppression allowed A to pull C into the result when A appeared
as a current-turn source. The amended experiment adapter removes suppressed
memory IDs from that source list and the regression test observes no C pull.

This is a source-snapshot implementation finding, not a claim about a live
deployment. It is also why the result is labelled as an adapter protocol, not
native Raven persistent suppression.

## Longitudinal observations

The primary score effect is the sum of signed differences on memories other
than A between a full Raven-core query and the same query with A suppressed.
The complete per-memory vectors are in the JSON artifact. The standardized
propagation probe independently queries with A's fixed vector and records the
activated memories without writes.

| Arm | Step 5 effect sum | First washout (step 9) | Final washout (step 13) | Final standardized propagation |
|---|---:|---:|---:|---|
| No absence | 0.300000 | 0.648000 | 0.540000 | A, C, D |
| Re-exposure | 0.000000 | 0.000000 | 0.000000 | A |
| Strict local restoration | 0.000000 | 0.510000 | 0.432000 | A, C, D |
| Links-only restoration | 0.000000 | 0.522000 | 0.450000 | A, C, D |
| Complete local restoration | 0.000000 | 0.522000 | 0.450000 | A, C, D |
| Relearning | 0.000000 | 0.090000 | 0.000000 | A |

**OBSERVED:** nonzero signed score effects remained after five washout
experiences in the no-absence, strict-restoration, links-only, and complete
restoration arms. Re-exposure and relearning had zero summed indirect effect
at the final checkpoint and activated A alone under the standardized
propagation probe. The full per-memory signed vector must be inspected because
a sum can cancel positive and negative effects.

**OBSERVED:** strict restoration differed from complete/link-only restoration
in the final score effect (0.432 versus 0.450). Complete restoration and
links-only restoration were identical on the measured values in this fixture.
Re-exposure and relearning also converged to identical measured values by the
last checkpoint, although their availability differed at step 5. These are
valid protocol-specific equalities; they do not prove general equivalence.

**INFERRED:** the persistent differences are explained by the recorded
availability, state, link, activation, and ordinary STDP trajectories in this
fixture. Raven's public recall path applies STDP and activation writes after
retrieval (`sources/raven-memory/raven/memory_engine.py:1979-1989`); the harness invokes those copied
operations while excluding the absent target. No additional latent historical
variable was tested. Replaying these same rules and states is the direct
alternative explanation, so the result does not establish memory persistence
beyond the represented Raven state.

## Falsification and test integrity

- **OBSERVED:** 6 tests passed, including the six-arm replay equality check and the complete
  incident-link clearing check for re-exposure.
- **OBSERVED:** the initial test invocation happened before the experiment
  module existed and failed during import, so it did not count as a behavioral
  red run. The causal-readout zeroing mutation below provided the intended
  failing oracle check after implementation.
- **OBSERVED:** the raw-core negative control reproduced the current-turn suppression leak;
  the adapter's filter blocked it.
- **OBSERVED:** a deliberate zeroing mutation of the signed indirect readout caused the
  targeted causal-readout test to fail; the mutation was reverted before the
  final run.
- **OBSERVED:** a deliberate bypass-suppression path caused the absence invariant to fail;
  the test explicitly checks that failure.
- **OBSERVED:** the result JSON was generated twice inside the replay test and compared as
  an exact Python structure. A separate runner execution also reproduced the
  same artifact SHA-256, recorded in `PROVENANCE.md`.
- **OBSERVED:** no tests were skipped. **UNKNOWN:** behavior beyond the tested
  boundary of four memories, one query schedule, one source snapshot, no
  concurrency, no ANN, no downstream model, and no external validation.

## Conclusion

**INFERRED, narrow:** Raven's copied retrieval and STDP mechanisms can produce
different post-absence retrieval score trajectories in this controlled
synthetic field, and those differences can remain after five washout
experiences. The result is consistent with causal history carried by the
current represented state. It does not establish transfer of Exp50's state
abstraction, H14 in an agent's downstream behavior, or a mechanism beyond
Raven's existing state and link updates.

**UNKNOWN:** whether the current-turn source leak occurs in every supported
Raven call path, whether upstream code has changed since the snapshot, and
whether any result persists in MNEME, Stigmergy, or a deployed Raven system.
