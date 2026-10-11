# Exp51 Preregistration Amendment 4

**PROPOSED amendment, recorded after auditing the candidate final run and
before the corrected execution.** The candidate output is superseded.
**OBSERVED:** code review found that the
re-exposure helper cleared A's outgoing synaptic map but left incoming entries
keyed by A in other memory rows. That did not satisfy the declared
“no incident links” operation.

The corrected helper clears both outgoing and incoming synaptic entries for A,
deletes all directed cell links incident to A, and rebuilds Raven's copied
in-memory indices. A regression test asserts the full incident-link set is
empty immediately after re-exposure. No source snapshot was changed.
