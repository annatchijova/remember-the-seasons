# Exp51 Preregistration Amendment 3

**Recorded before the final reported execution.** Earlier outputs are
superseded and are not used for the final interpretation because their
“propagation” field only indicated whether A was reached by the current
experience query; it did not measure A's propagation capacity.

At every post-window and washout checkpoint, add a read-only standardized
propagation probe: query with A's fixed stored vector, use an empty
`current_turn_memories` list, hold `now` fixed to that checkpoint, and record
the complete activated-memory set. This measures propagation through the
field's cell links without applying learning or changing state. Keep it
separate from (1) the scheduled experience retrieval, (2) the paired signed
indirect score effect, and (3) persistent row/link state.

This remains an implementation-specific capacity probe; it is not a
downstream decision or behavioral outcome.
