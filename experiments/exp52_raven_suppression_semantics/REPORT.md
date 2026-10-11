# Exp52 Results: Raven Suppression Semantics and Causal Isolation

## Result in scope

**OBSERVED, copied Raven implementation with synthetic fixture:** Exp52
compared result exclusion, suppression of A as a current-turn synaptic source,
and a paired operational deletion of A followed by four fixed queries. The
machine-readable output is
[`exp52_raven_suppression_semantics_run.json`](exp52_raven_suppression_semantics_run.json).

## Suppression contracts

The raw core omitted A from ranked results, but returned C through a synaptic
pull from A. At query `B`, C's score was `0.18` with raw suppressed A as the
current-turn source and absent with no current-turn source. A's `A→B` weight
also added `0.24` to B's score. The complete signed score-vector difference
is in the artifact.

**OBSERVED:** result exclusion and influence exclusion are separate properties
in this probe. Result exclusion held (`A` was absent); raw suppression did not
prevent A from changing non-A scores (`C` was emitted as `source="synaptic"`).
The experiment-only policy that also removes suppressed A from
`current_turn_memories` exactly matched the no-source negative control for all
non-A scores. This confirms that the source filter isolates the tested path
for this input; it does not establish the completeness of every Raven call
path.

The code-level finding is bounded to the pinned source snapshot:
`_recall_core()` documents suppression as preventing a cell from firing links
(`sources/raven-memory/raven/memory_engine.py:1635-1639`), while the synaptic
source loop iterates `current_turn_memories` without checking whether the
source cell is suppressed (`sources/raven-memory/raven/memory_engine.py:1857-1888`).
This report does not claim a live deployment or all configurations are
affected.

## Paired history and operational deletion

The branches began from one Exp51 seed. Both received query `B` at the same
fixed time. A participated as a current-turn source in one branch; A was
field-suppressed and removed from current-turn sources in the control. After
the normal recall-state updates, both branches had A's row and every incident
synaptic and cell link deleted. Both then received identical queries
`B, C, D, B`, with the same current-turn input `B` at each step.

**OBSERVED:** the non-target persistent states did not become identical.
At the final checkpoint, C's `recall_count` was 5 in the A-participated
history and 4 in the suppressed control; the other measured non-target fields
matched. This is a residual in an explicitly represented counter, not
evidence of an additional latent historical variable.

**OBSERVED:** despite that state difference, all four post-deletion query
score vectors and ranked IDs were exactly equal between branches. Raven's
tested score path did not distinguish these histories under the fixed
queries. Therefore the operational erasure criterion requiring both state
and observed-output equality failed, while finite retrieval equivalence held
for the four declared inputs.

**INFERRED, bounded:** A's participation can leave a represented state
difference after deleting A and its incident links, while that difference
does not alter the four tested retrieval outputs. Since `recall_count` is
recorded but is not used by the scoring terms exercised here, this is
consistent with a history trace that is currently behaviorally inert under
the chosen inputs. A new schedule or a mechanism that consumes this counter
could falsify that interpretation.

## Test integrity and reproducibility

Exp51's four post-observation amendments and pilot runs are documented in its
own package and are not treated as confirmatory evidence here. Exp52 has a
separate preregistration written before its first behavioral execution; its
fixture, controls, predictions, and limits are listed there.

- **OBSERVED:** 5 tests pass: result exclusion with a source leak, exact match
  between the influence-isolation adapter and its no-source control, a
  deliberate source-filter bypass that produces a differing score vector,
  deletion of A and all incident links in both histories, and deterministic
  serialization across repeated runs.
- **OBSERVED:** the experiment JSON was emitted twice with the same SHA-256:
  `32400cae533cb7bca021e339aa0081b1ee38121342b787dc902eb38fe1039e75`.
- **OBSERVED:** the copied implementation is from Raven source commit
  `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`; provenance and copied-source
  hashes are recorded in [`PROVENANCE.md`](PROVENANCE.md).

## Limits and next falsifier

The experiment covers one source snapshot, one synthetic four-memory field,
one exposure event, four post-deletion queries, no ANN, no concurrency, no
model, and no downstream agent action. The residual `recall_count` does not
demonstrate a functionally consequential historical trace. The next falsifier
should use a preregistered input schedule whose query score or ranking depends
on a post-exposure non-target state field, or show that no supported Raven
retrieval path consumes the differing counter. A null behavioral difference
under that stronger schedule would count against functional persistence in
this Raven snapshot.

Exp52 is not evidence about clinical memory, a production Raven deployment,
MNEME, Stigmergy, or H14 in downstream agent behavior.
