# Exp57: Temporal Recency Through Consolidation

## Verdict

**OBSERVED, copied Raven snapshot and synthetic fixture:** assigning the same
C=5/D=4 recall counts to different timestamps changed pre-consolidation
recency bonuses and scores. Equalizing the two memories' `last_activation`
fields made the pre-consolidation traces match. After non-dry-run
consolidation, both branches had the same weights, merged embedding bytes, and
fixed C/D retrieval traces; the new consolidated node had
`last_activation=0.0`. A temporary zero-recency mutation removed the temporal
contrast. The full result replayed deterministically in the test.

The interpretation is deliberately narrow: the count projection from Exp56
remained sufficient for the tested consolidation-derived outputs, while
`last_activation` independently affected retrieval before consolidation. This
assay does not establish that all history is encoded in these fields or that
the entire system becomes equivalent after consolidation. The audit histories
remain different.

## Results

| Measurement | T1: C recent, D old | T2: C old, D recent |
|---|---:|---:|
| Audit-derived weights | C=5, D=4 | C=5, D=4 |
| Persisted recall counters | C=9, D=8 | C=9, D=8 |
| C recency bonus on C query | 0.05 | 0.0000030517578125000014 |
| D recency bonus on D query | 0.0000030517578125000014 | 0.05 |
| Consolidated `last_activation` | 0.0 | 0.0 |
| Post-merge embedding and C/D traces | Equal | Equal |

The older event timestamp was 790400 seconds and the fixed observation time
was 2000000 seconds, a 14-day age difference. Equalizing `last_activation`
before the query probes made both complete pre-consolidation traces equal. With
`RECENCY_WEIGHT=0.0`, the same temporal contrast also disappeared.

## Epistemic assessment

- **OBSERVED:** Raven's update path writes the recall time to
  `last_activation` and increments `recall_count` at
  [`memory_engine.py:1031–1047`](../../sources/raven-memory/raven/memory_engine.py#L1031).
- **OBSERVED:** the scoring core derives the recency bonus from elapsed age at
  [`memory_engine.py:1810–1822`](../../sources/raven-memory/raven/memory_engine.py#L1810).
- **OBSERVED:** the consolidator initializes the merged node's
  `last_activation` to zero at
  [`sleep_consolidator.py:263–276`](../../sources/raven-memory/raven/sleep_consolidator.py#L263).
- **INFERRED:** in this fixture, timestamp allocation changes pre-merge
  retrieval through the recency term, and the tested consolidation path drops
  that measured distinction from the merged node and these later probes. The
  equalization and mutation controls support the mediator interpretation.
- **UNKNOWN:** whether this temporal state affects other retrieval queries,
  future state updates, audit observers, alternate consolidation settings, or
  downstream agent decisions.

## Reproduction

Run from the repository root:

```sh
python3 -m unittest -v experiments/exp57_raven_temporal_recency/test_exp57_raven_temporal_recency.py
python3 experiments/exp57_raven_temporal_recency/exp57_raven_temporal_recency.py
```

The runner checks source-copy hashes, validates all nine recalled IDs and the
count/merge gates, records complete score components and ranks, and stores a
canonical JSON artifact. Five tests cover the temporal effect, its equalized
control, post-merge equality, the zero-recency mutation, and deterministic
replay.

This is not evidence about deployed Raven, MNEME, Stigmergy, or any live agent.
