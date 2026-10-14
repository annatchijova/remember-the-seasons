# Exp57: Temporal Recency Through Consolidation

## Status and scope

**PROPOSED — preregistered before implementation and execution.** This bounded
assay uses the copied Raven snapshot pinned by Exp51, synthetic vectors, and
independent temporary SQLite clones. It will not edit `sources/`, upstream
Raven, product code, or add dependencies.

Source commit: `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.

## Question and rival

Exp56 found that event order and query text did not affect the merged embedding
or fixed retrieval traces when per-memory audit counts matched. Exp57 tests a
different state variable that retrieval itself updates:

> With the same per-memory recall counts, can assigning the same recall events
> to different times change pre-consolidation retrieval, and does that
> difference survive consolidation?

The benign alternative is that counts and resulting embeddings fully explain
all retrieval consequences. Source inspection supplies a falsifiable rival:
recall writes the supplied clock value to `last_activation`, while retrieval
adds an age-dependent recency term. The relevant pinned-source locations are
[`memory_engine.py:1031–1047`](../../sources/raven-memory/raven/memory_engine.py#L1031)
and [`memory_engine.py:1810–1822`](../../sources/raven-memory/raven/memory_engine.py#L1810).
The consolidator inserts the merged node with `last_activation=0.0` at
[`sleep_consolidator.py:263–276`](../../sources/raven-memory/raven/sleep_consolidator.py#L263).
These are **OBSERVED** source facts; outcome predictions are **PROPOSED**.

## Conditions and predictions

Use two branches with identical initial databases, fixed vectors, query text,
event counts, and total event count. C and D remain the sole eligible merge
group. Each branch receives five C recalls and four D recalls, with `top_k=1`,
`hops=0`, `layer_filter='episodic'`:

| Branch | Older events (`NOW - 14 days`) | Recent events (`NOW`) | Counts |
|---|---|---|---:|
| T1 | D four times | C five times | C=5, D=4 |
| T2 | C five times | D four times | C=5, D=4 |

Before consolidation, query the fixed C and D vectors at `NOW`, `top_k=4`,
`hops=0`. The preregistered prediction is that the branch with a more recent
memory has a higher recency component and score for that memory. The full
score/rank traces need not otherwise be equal.

Then apply non-dry-run consolidation with identical settings and fixed
consolidation time. The source-derived prediction is that both branches use
the same 5:4 audit-derived weights and therefore produce identical merged
embedding bytes and fixed-query retrieval traces. The merged node is predicted
to start with zero `last_activation`, so the recency difference in the source
rows will not carry into that merged node. Audit histories and state snapshots
remain distinguishable; the equivalence target is only the declared
consolidation and retrieval behavior.

## Controls and falsifiers

- **Temporal assignment falsifier:** if pre-consolidation score components and
  traces do not differ as predicted, the assay fails to establish that the
  timestamp intervention reached Raven's retrieval mechanism.
- **Count/fixture gate:** both branches must have audit counts C=5/D=4, row
  counters C=9/D=8, nine recall events, and exactly the C/D merge group.
- **Timestamp equalization control:** clone T1/T2 after history generation,
  set C and D `last_activation` to the same declared timestamp in both, and
  require equal pre-consolidation score/rank traces. This tests mediation by
  the field that retrieval reads.
- **Post-consolidation prediction:** embedding bytes, consolidation weights,
  and fixed C/D retrieval traces must match between T1 and T2. A mismatch
  falsifies the prediction that consolidation discards this temporal
  distinction for these outputs.
- **Mutation control:** set the copied engine's recency weight to zero in a
  separate assay run. The pre-consolidation temporal contrast must disappear;
  otherwise the score difference is not specifically mediated by recency.
- **Replay:** rebuild from fresh clones and compare canonical result JSON
  byte-for-byte.

Any source-hash, target-return, count, merge-group, or replay failure invalidates
the run rather than counting as support for either hypothesis.

## Measurement and limits

Record each branch's timestamp assignments, persisted `last_activation`, audit
counts, pre- and post-consolidation score components and ranks, merged
embedding bytes, and audit-log digest. Compare deterministic outputs exactly
within the same runtime.

The result can establish only whether this copied Raven snapshot's
`last_activation` field affects the selected retrieval probes and whether the
tested consolidation path carries that field into its merged node. It cannot
establish deployed-agent behavior, all retrieval operations, other snapshots,
or whether audit-history differences affect other observers. It is not a
clinical memory model.
