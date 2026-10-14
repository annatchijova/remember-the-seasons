# Exp56: Audit Projection Sufficiency for Consolidation

## Status and scope

**PROPOSED — preregistered before implementation and execution.** This is a
bounded assay against the copied Raven snapshot pinned by Exp51. It uses
synthetic vectors and disposable SQLite clones. It does not modify
`sources/`, upstream Raven, product code, or add dependencies.

Source commit: `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.

## Question and rival

Exp55 showed that actual consolidation responds to per-memory counts derived
from the recall audit log, while an isolated stored `recall_count` difference
did not alter the tested merge. Exp56 asks:

> When the audit-derived count for each memory is held fixed, do audit event
> order or query text affect the consolidated embedding or later retrieval?

The simple projection hypothesis is that consolidation depends on the count
vector only. The rival is that event sequence or query text has a direct effect
even when the per-memory count vector is identical. Source inspection gives a
specific prediction: `get_recall_counts()` sums IDs in
`memories_retrieved`; `merge_group()` uses those counts as embedding weights.
The cited implementation is
[`sleep_consolidator.py:79–95`](../../sources/raven-memory/raven/sleep_consolidator.py#L79)
and [`sleep_consolidator.py:170–183`](../../sources/raven-memory/raven/sleep_consolidator.py#L170).
This is **OBSERVED** about the pinned source; the Exp56 outcomes remain
**PROPOSED** until execution.

## Conditions and predictions

Each condition starts from an independent clone of the same Exp51 fixture.
C and D are the only consolidation-eligible memories and must form exactly one
merge group at cosine threshold 0.90. Recall uses fixed vectors, a fixed clock,
`top_k=1`, `hops=0`, and `layer_filter='episodic'`.

| Condition | Audit schedule | Audit counts | Purpose |
|---|---|---:|---|
| H1 | Five C recalls, then four D recalls; canonical per-memory text | C=5, D=4 | Reference |
| H2 | Interleaved C/D recalls; same per-memory text as H1 | C=5, D=4 | Order contrast |
| H3 | Same schedule as H1; distinct query text | C=5, D=4 | Text contrast |
| H4 | Four C recalls, then five D recalls | C=4, D=5 | Positive sensitivity control |

The count-projection prediction is that H1, H2, and H3 produce identical
merged embedding bytes, consolidation weights, and fixed C/D retrieval score
and rank traces. Their audit records are expected to differ; the target
equivalence is specifically the consolidation-derived retrieval path, not
whole-system or audit-log equivalence.

H4 preserves total recalls (nine) while changing the allocation by memory. It
must produce a different merged embedding and the source-predicted directional
score change: C's base score rises under 5:4 relative to 4:5, and D's falls.
If H1/H2/H3 diverge in the target outputs, count-vector sufficiency is
falsified for this fixture. If H4 fails to diverge directionally, the assay is
inconclusive as a sensitivity instrument.

## Fixture and measurement contract

1. Reuse the copied Exp51 Raven engine through Exp53's import harness; verify
   both source file hashes before a run.
2. Create each branch by cloning the same seed. Change only the declared
   eligibility fields before recall; do not edit source snapshots.
3. Freeze source-visible time reads to Exp55's `NOW`; use the exact KDTree
   backend and fixed vectors. No model, provider, network, or personal data.
4. Assert each recall returns exactly its scheduled memory ID. Confirm audit
   counts, persisted row counters, total event count, and fixed merge group
   before consolidation.
5. Apply non-dry-run consolidation to each disposable clone. Reopen the
   database and record merged embedding bytes and complete fixed-query score
   and rank traces for C and D.
6. Record audit-log digests separately. Do not treat differing audit logs as a
   failure of retrieval-path equivalence.
7. Replay from fresh clones and require canonical JSON byte-for-byte equality.

## Falsifiers and controls

- **Order/text falsifier:** any mismatch among H1/H2/H3 in merge embedding,
  source weights, or fixed-query retrieval traces falsifies count-vector
  sufficiency for the declared outcomes.
- **Allocation sensitivity control:** H4 must differ in embedding and show the
  preregistered C/D score directions relative to H1.
- **Mutation control:** a temporary, deliberately order-sensitive mutation
  adds one unit of merge weight to the memory appearing last in the audit
  sequence. The assay must detect divergence between H1 and H2. The mutation
  is never included in the unmodified run.
- **Fixture gate:** an unexpected retrieval ID, count, merge group, or source
  hash invalidates the run; it is not a negative result.

## Interpretation limits

Any result applies only to this pinned source snapshot, copied engine and
offline consolidator, synthetic fixture, exact query vectors, and declared
retrieval outcomes. Raven audit inspection, telemetry, graph export, and other
operations may distinguish histories even when the consolidation-derived
retrieval traces match. No claim is made about deployed Raven, MNEME, Stigmergy,
downstream agent decisions, or universal sufficiency of event counts.
