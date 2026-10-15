# Exp62: Cross-Process Shared-Database Allocator Assay

## Result

**OBSERVED — copied Raven runtime:** two spawned Python processes each
constructed an engine against the same empty temporary database before either
store. Both reported `_next_cell_id = 0`. After simultaneous writes of
different contents, both returned `cell_id = 0` with different memory IDs;
SQLite contained one row, and it belonged to one of the two returned IDs.
Which process's row survived is intentionally not asserted because writer
ordering can vary.

**OBSERVED — exact generated-ID case:** both processes were initialized before
writing the same content. With the engine clock frozen to the same
millisecond, they returned the same `memory_id` and `cell_id`. After the first
write, the harness inserted a synthetic recall audit row for that ID; after
the second store, the copied consolidator's actual `get_recall_counts()` still
counted that prior event for the replacement ID (1 before and 1 after).
SQLite retained one row, with the second process's embedding.

**OBSERVED — reload control:** process A wrote and exited before process B
started. B loaded `_next_cell_id = 1`; the two stores received cell IDs 0 and
1, and both rows remained.

**Five tests passed** in the recorded suite, including artifact replay and
source-hash checks. The JSON result also reproduced byte-for-byte in a
separate runner invocation.

## Source basis and deployment relevance

- `sources/raven-memory/raven/memory_engine.py:1267-1274` wraps each engine
  operation in its instance's `RLock`; line 1378 constructs that lock.
- `sources/raven-memory/raven/memory_engine.py:1413,1426-1427` initializes
  the cell allocator from persisted `max(cell_id) + 1`.
- `sources/raven-memory/raven/memory_engine.py:1541-1544` forms IDs from a
  content-hash prefix, millisecond timestamp, and allocator value.
- `sources/raven-memory/raven/memory_engine.py:746-754,856-875` declares
  `cell_id` unique and stores rows with `INSERT OR REPLACE`.
- `sources/raven-memory/api_server.py:160-165` configures the API engine from
  `RAVEN_DB_PATH`; `sources/raven-memory/mcp_server.py:67-68` configures a
  separate module-level MCP engine from the same environment variable.
- `sources/raven-memory/raven/sleep_consolidator.py:79-96` counts audit
  entries by memory ID; Exp62 invokes this copied function for its canary.

**INFERRED:** the source supports configuring separate API and MCP engine
instances to the same SQLite path. Exp62 demonstrates the resulting allocator
condition across OS processes when both load before writes. **UNKNOWN:**
whether a particular deployment actually runs both services against the same
file, their startup/write schedule, and the natural frequency of same-content
stores within one millisecond.

## Falsification, scope, and limits

The preregistered predictions survived this forced shared-file condition; the
post-write reload control preserved both rows. A mutation from `INSERT OR
REPLACE` to `INSERT OR IGNORE` caused the exact-ID test's expected second
embedding to fail. The recorded-result parity check also detected the mutated
source hash. The simultaneous different-content outcome establishes the
one-row invariant, not which writer wins.

This was a controlled runtime test of copied Raven code using spawned local
processes, a temporary SQLite file, and a frozen clock. It did not launch
Raven's HTTP or MCP servers, test a production deployment, or estimate event
frequency. The synthetic audit row was used only to test ID-based counting;
the actual copied consolidator counting function was called. Exp60's finding
that the two inspected ingestion signatures do not accept caller-selected IDs
still stands: Exp62 tests collisions from internally generated values.

H14 remains open. This assay demonstrates a conditional implementation
behavior, not a deployed-agent memory effect or an estimate of real-world
incidence.
