# Exp51 Preregistration Amendment 1

**Recorded after an initial pilot and before the amended rerun.** The initial
pilot output was superseded and is not retained as a machine-readable result.
Only the direct suppression-leak diagnostic is preserved in this amendment and
in the final run artifact.

## Reason

The copied Raven `_recall_core()` checks `suppressed` for cells reached through
the geometric/BFS path and for synaptic targets, but its current-turn synaptic
source loop does not exclude a suppressed memory from `current_turn_memories`.
An initial direct check found that A can still emit a synaptic pull while A is
listed as a current-turn source and its cell is suppressed. This contradicts
the source docstring's stated suppression semantics for that call shape.

This finding makes the initial preregistered description (“passing the target
through Raven's existing `suppressed` argument is sufficient”) false for that
input. No source snapshot was changed.

## Amended treatment

For every suppressed core evaluation, the experiment adapter removes memories
whose cell IDs are suppressed from `current_turn_memories` before calling the
copied Raven core. During absence, it also excludes the target from STDP source
and activation writes. The adapter therefore enforces absence across both
Raven entry paths; the raw-core leak is recorded as a separate source-level
falsifier and regression oracle.

The paired causal probe applies the same rule to the suppressed branch while
keeping the full branch's current-turn inputs unchanged. Its primary causal
outcomes exclude A's own score and report signed changes to every other
memory's score. A's direct availability score is recorded separately.

## Updated interpretation

Any longitudinal difference applies to the amended harness protocol, which
adds a current-turn filter absent from the copied source implementation. It
does not show that Raven's public `intervene()` or raw `suppressed` argument
implements persistent functional absence by itself. The initial pilot is
retained but superseded; only the amended replay is used in the report.
