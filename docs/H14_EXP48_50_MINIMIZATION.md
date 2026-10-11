# H14 Exp48–50: Observational Quotient and Bounded Minimality

## Status and claim boundary

**OBSERVED:** Exp48–50 are deterministic synthetic assays. Their transition
code is the Exp47 model; they do not execute Raven, MNEME, or a deployed agent.
The Exp50 run artifact is
[`h14_exp50_run.json`](../experiments/exp50_h14_partition_refinement/h14_exp50_run.json)
(canonical SHA-256 `2356b7d553fdf947993ade857491c1527b716e69f6fb7ed48a4ada28af6495b5`).
Its generator, tests, and command are in
[`exp50_h14_partition_refinement.py`](../experiments/exp50_h14_partition_refinement/exp50_h14_partition_refinement.py)
and [`test_exp50_h14_partition_refinement.py`](../experiments/exp50_h14_partition_refinement/test_exp50_h14_partition_refinement.py).

**INFERRED, scoped:** within the finite machine, seed closure, inputs, and
observables defined below, Exp50 supports a minimal behavioral quotient of
118 classes. This statement is conditional on the enumerated transition
system and output functions being the intended model semantics.

**UNKNOWN:** whether the same quotient, mechanisms, or result applies to
Raven, MNEME, other seeds, other update rules, or real agents.

## Machine definition

Let a state be the Exp47 tuple

\[
s=(n,w,\ell,r),
\]

where `n` is capped reinforcement count, `w` is scalar association, `ℓ` is
link presence, and `r` is recency age. The seed is produced by
`construct_history(F(0), 3)`: three paired updates and zero reinforcement-only
events. The resulting seed has count 3 and association `3/8`. Exp48's closure
contains every state reachable from that seed under
the two choices C and K. Exp50 checks that its shared-score inputs remain
inside the same 172-state closure.

An Exp50 input is a challenger score `q`, not an action label. The Exp47
transition computes the state's scalar score and chooses C when the state
score is greater than `q`; otherwise it chooses K. Thus two states given the
same score may choose different actions. This is the semantic distinction
between Exp49's forced-action audit and Exp50's input machine.

The finite input alphabet `Σ` contains the 22 distinct exact rational scores
appearing in Exp48's 24 probe schedules. Those values comprise the two extreme
scores and midpoints between adjacent scalar-score levels. The transition
uses a challenger score only to select C or K. The result is therefore stated
for this declared alphabet and the choice regions it represents, not for an
unspecified scoring rule.

For each state, the initial observation is propagation and causal contribution
before a new query. Each transition emits `(choice, propagation,
causal_C_to_D)`. Fractions are represented exactly. A query sequence's trace
contains the initial observation followed by the transition outputs.

## Exp48 observational partition

**OBSERVED:** Exp48 defines two states as equivalent when their exact traces
agree under each of 24 fixed challenger-score schedules. Restricting this
partition to the 172-state closure yields 118 classes. This is initially a
finite-suite equivalence: by itself, it does not establish stability under
arbitrary future inputs.

## Exp50 refinement method

Exp50 starts with blocks that agree on the initial observation and on each
immediate transition output for every `q ∈ Σ`. It repeatedly refines a state's
block key with, for every input, both the immediate output and the current
block of the successor:

\[
K_{i+1}(s)=\left(K_i(s), I(s),
  \left[(q, O(s,q), K_i(T(s,q)))\right]_{q\in\Sigma}\right).
\]

Refinement stops when the new keys induce the same partition as the previous
round. The implementation raises an error if an input leaves the declared
closure or if refinement does not reach a fixed point.

**OBSERVED:** the class counts by round were `68 → 93 → 118 → 118`. The fixed
point partition exactly matches the Exp48 partition restricted to the
reachable closure. An additional exhaustive check covered all 2,376
same-Exp48-class state-pair/input combinations. It found zero immediate-output
mismatches and zero successor-class mismatches under the 22 shared scores.

## Bounded minimality argument

**INFERRED:** the fixed-point property gives output preservation and
successor-class preservation for every input in `Σ`. Since the state set is
closed under those inputs, induction on sequence length gives identical
observable traces for any two states in the same fixed-point class under any
finite sequence from `Σ`.

For the lower bound, Exp50 selects one representative from each fixed-point
class and examines every unordered pair of distinct classes. For each pair it
uses breadth-first search over the product transition system. The queue starts
at the state pair and explores all 22 inputs in nondecreasing sequence length.
The first edge with different outputs is recorded; if initial observations
already differ, the witness has length zero. A visited set over state pairs
preserves the first, shortest route to each product state. Therefore the
algorithm returns a shortest distinguishing sequence within this finite input
alphabet when it finds a witness.

**OBSERVED:** certificates were generated for all `118 × 117 / 2 = 6,903`
distinct class pairs. Of these, 6,169 differ on the initial observation. The
other 734 require later inputs: 659 shortest witnesses have length one, 50
have length two, and 25 have length three. Tests replay all certificates
against the transition function. A separate exhaustive test enumerates every
shorter sequence for each of the 734 nonempty witnesses; none distinguishes
its pair. The maximum shortest-witness length in this run is three.

**INFERRED:** every pair of distinct classes is behaviorally distinguishable
by an allowed observation trace. Any exact state encoding that preserves
these traces must therefore keep all 118 classes separate. Together with the
congruence result, this supports 118 as the minimum number of behavioral
classes for this particular seeded finite machine and declared outputs and
inputs. It does not claim the 118-class representation is the only possible
encoding of those classes.

## Verification and falsifiers

Run from the experiment directory:

```sh
python3 -m unittest -v
python3 exp50_h14_partition_refinement.py
```

**OBSERVED:** 11 tests pass. They check the pinned Exp49 artifact, the
state-dependent meaning of a shared query score, closure and partition
counts, congruence, replay of all certificates, and shortestness of all
nonempty certificates. A deliberate constant-observation mutation collapses
the partition to one class and is detected. Two generated JSON files compared
byte-for-byte equal; this checks reproducibility of these executions, not
external validity.

The conclusion would be reopened by any of the following:

- a state in the enumerated closure that escapes under a declared input;
- an Exp48-equivalent pair with different immediate outputs or successor
  classes under a shared score;
- a replay failure, or a shorter distinguishing sequence than a certificate;
- a different fixed point when independently implementing the stated
  transition, observation, or refinement rules.

Changes to the input alphabet, transition rules, observables, or seed define a
different machine and require a new claim. This result is not evidence for a
biological mechanism or for restoration of memory function in Raven/MNEME.
