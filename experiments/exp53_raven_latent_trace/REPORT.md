# Exp53 Results: Raven Latent Trace Activation Assay

## Scope

**OBSERVED, copied Raven source with synthetic fixture:** Exp53 compared two
database states that differed only in `C.recall_count` (5 versus 4), while
`B.recall_count` was 4 in both. All other memory columns, cell links, and audit
rows matched exactly. It tested retrieval, inspection/telemetry, graph export,
one update, and the sleep consolidator's dry-run path.

The run artifact is
[`exp53_raven_latent_trace_run.json`](exp53_raven_latent_trace_run.json).

## Operation inventory

The following classifications are **OBSERVED** in the pinned source snapshot.

| Operation | Use of `recall_count` | Evidence |
|---|---|---|
| Retrieval score/rank | No read by `_recall_core()`; its score formula uses similarity, state, hop decay, link contribution, and recency | [`memory_engine.py:1795-1831`](../../sources/raven-memory/raven/memory_engine.py:1795) |
| State update | `update_activation(s)` increments it on memories returned by recall | [`memory_engine.py:1031-1047`](../../sources/raven-memory/raven/memory_engine.py:1031); public recall invokes updates at [`memory_engine.py:1979-1982`](../../sources/raven-memory/raven/memory_engine.py:1979) |
| Stats/telemetry | `count_stats()` sums it as `total_recalls`; `get_stats()` exposes the sum | [`memory_engine.py:962-1006`](../../sources/raven-memory/raven/memory_engine.py:962), [`memory_engine.py:2220-2253`](../../sources/raven-memory/raven/memory_engine.py:2220) |
| Inspection API | `/memories` serializes the per-memory count; `/memories/{id}` serializes `MemoryEntry.to_dict()` | [`api_server.py:431-459`](../../sources/raven-memory/api_server.py:431), [`api_server.py:462-472`](../../sources/raven-memory/api_server.py:462), [`memory_engine.py:171-177`](../../sources/raven-memory/raven/memory_engine.py:171) |
| Truncated graph export | `load_top_recalled()` orders rows by count; `export_graph()` uses it when node count exceeds the limit and includes the count in each node | [`memory_engine.py:952-960`](../../sources/raven-memory/raven/memory_engine.py:952), [`memory_engine.py:2257-2286`](../../sources/raven-memory/raven/memory_engine.py:2257) |
| Sleep consolidation | Does not load the memory-row count. It derives counts from `audit_log.memories_retrieved` and uses those counts for merge weights | [`sleep_consolidator.py:56-95`](../../sources/raven-memory/raven/sleep_consolidator.py:56), [`sleep_consolidator.py:170-224`](../../sources/raven-memory/raven/sleep_consolidator.py:170), [`sleep_consolidator.py:416-436`](../../sources/raven-memory/raven/sleep_consolidator.py:416) |
| Persistence/portability | Stored, deserialized, and included in the portability memory columns | [`memory_engine.py:856-875`](../../sources/raven-memory/raven/memory_engine.py:856), [`memory_engine.py:1238-1259`](../../sources/raven-memory/raven/memory_engine.py:1238), [`portability.py:40-44`](../../sources/raven-memory/raven/portability.py:40) |

The sleep-consolidator input name `recall_count` is assigned from audit-log
counts after loading episodic rows; it is not the persisted counter being
varied by this experiment. **INFERRED, bounded:** with audit rows fixed, the
consolidator's dry-run output should be insensitive to this column. The paired
dry-run below confirms that prediction for the tested fixture.

## Paired experiment results

**OBSERVED:** the exact score components and rankings matched for all four
fixed core queries (`A`, `B`, `C`, `D`). This supports retrieval invariance
for those inputs and this copied scoring implementation; it does not establish
invariance for every operation or future query.

**OBSERVED:** the field was externally visible. `get_stats()` reported 9
total recalls in S5 and 8 in S4. The memory inspection serialization exposed
C's values 5 and 4. `export_graph(max_nodes=1)` selected C in S5 (count 5)
and B in S4 (both B and C count 4). In this fixture SQLite returned B first
for the tied rows; the source SQL has no secondary sort key, so this particular
tie outcome is not guaranteed across database implementations or plans. The
counter values themselves are directly serialized either way.

**OBSERVED:** applying the same activation update changed C's counts from
5→6 and 4→5, while setting the same `last_activation` timestamp. The gap
persisted; this update did not otherwise make the count affect retrieval.

**OBSERVED:** sleep-consolidator dry-run outputs were identical for the two
states with the same empty audit log. After equalizing `C.recall_count` to 5,
retrieval, stats, inspection, graph export, and consolidation outputs all
matched between the control copies.

## Interpretation

The broad claim that the counter is observationally redundant is **FALSIFIED**
for Raven's full declared interface: stats, memory inspection, and graph
export expose or consume it. The narrower claim that this counter does not
affect the tested retrieval scores or ranks is **OBSERVED, supported** for four
fixed queries. The dry-run consolidation path was also invariant because it
reconstructs frequencies from audit rows, not from the memory column.

Exp53 therefore distinguishes a telemetry/export consequence from a
retrieval-decision consequence. It does not establish that a downstream agent
uses those telemetry outputs, nor that this count represents an unmodeled
latent memory mechanism. The result is fully explained by explicit stored
state and declared consumers.

## Test integrity

- **OBSERVED:** 7 tests pass: only-counter state isolation, exact retrieval
  invariance, visible stats and graph selection, consolidation invariance,
  equalized-counter control, a deliberate hypothetical count-dependent score
  mutation detected by the exact-vector oracle, and deterministic replay.
- **OBSERVED:** the complete JSON result reproduced with SHA-256
  `d8b045f9fe215450839b8422639bcfdabd8fbb7ddf68b0761ece1146cbfc6823`.
- **OBSERVED:** no test was skipped. No copied Raven source files were edited.

## Limits

The assay covers one Raven snapshot, the four-row Exp51 fixture, four core
queries, one exact KDTree backend, one SQLite implementation, and the
consolidator dry-run path. The API route itself was source-inspected; its
serialization was exercised through the same `MemoryEntry.to_dict()` field,
not through a live HTTP server. Other dynamic callers or downstream consumers
were not tested. See [`PREREGISTRATION.md`](PREREGISTRATION.md) and
[`PROVENANCE.md`](PROVENANCE.md).
