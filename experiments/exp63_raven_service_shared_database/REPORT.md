# Exp63: Cross-Service Shared-Database Allocator Assay

## Result

**OBSERVED — copied Raven service entry points, controlled local harness:**
the API route handler and MCP store tool, each running in a separate spawned
process against the same temporary SQLite file, reproduced the allocator
collision under the preregistered startup condition.

- Both service engines reported `_next_cell_id = 0` before either concurrent
  write. Different-content stores from API and MCP both returned cell ID zero;
  SQLite retained one row whose ID belonged to one of the two contenders.
- With identical content, both preinitialized services returned the same
  memory ID and cell ID at the frozen millisecond. The processes received
  different deterministic vectors for that content. The retained row matched
  the second MCP write, showing that replacement occurred. The copied
  consolidator counted the earlier audit event for the reused ID both before
  and after replacement (1 and 1).
- In the cross-service reload control, the API stored first and exited. MCP
  then loaded allocator value one, stored at cell ID one, and both rows
  remained.

Five tests passed, including the pre-write counters, replacement canary,
reload control, source hashes, and recorded-result replay.

## Interpretation

**INFERRED:** the API/MCP boundary itself did not prevent Exp62's conditional
stale-allocator behavior when both copied entry points were configured to
share a file and initialized before writes. The prediction that the service
entry points would avoid the collision is falsified for this setup.

This does not establish that a deployed API and MCP server share a database,
that they have this startup/write schedule, or how frequently real requests
collide. The result also does not estimate natural same-content, same-
millisecond collisions.

## Harness accommodations and limits

- The test invoked the copied FastAPI `store_memory` route handler and the
  registered MCP `raven_store` function directly. It bypassed HTTP networking,
  FastAPI middleware/dependency injection, and MCP JSON-RPC framing.
- Embeddings were replaced with deterministic 384-dimensional vectors. The
  same-content arm gave API and MCP different vectors so the stored vector
  identifies whether `INSERT OR REPLACE` replaced the first row.
- The engine clock was frozen only around each store.
- The original Exp63 API worker replaced `asyncio.to_thread` with an inline
  async executor after the unmodified handler appeared to stall. Follow-up
  probes identified the cause of that local stall:
  - **OBSERVED, sandboxed process:** a local `socketpair.send()` raised
    `PermissionError(EPERM)` from both the main thread and a worker thread.
    The same local send probe succeeded when run outside the sandbox.
  - **OBSERVED, installed Python 3.12 standard library:**
    `BaseEventLoop.call_soon_threadsafe()` enqueues a callback and invokes
    `_write_to_self()`; `BaseSelectorEventLoop._write_to_self()` sends a byte
    on its internal socket and catches `OSError`, logging it only in debug
    mode (`/usr/lib/python3.12/asyncio/base_events.py:838-847`;
    `/usr/lib/python3.12/asyncio/selector_events.py:141-157`).
  - **INFERRED:** the sandbox-denied socket write explains why the worker
    completed and queued its result callback while the quiet event loop stayed
    asleep until a timer woke it. The inference would be refuted if the same
    `to_thread` stall reproduced outside the sandbox with socket writes
    allowed.
  - **OBSERVED, copied Raven API:** the actual `store_memory` handler returned
    when a periodic asyncio timer ran alongside it, without replacing
    `asyncio.to_thread`.
  This diagnosis is specific to the sandboxed assay environment; it is not
  evidence of a Raven or unsandboxed Python defect. Exp63's recorded result
  remains an inline-executor assay and does not test normal API thread-pool
  behavior or the HTTP runtime.
- The concurrent writer is nondeterministic; the assay asserts only that one
  contender survives, not which one wins.

## Source basis

The copied API lifespan reads `RAVEN_DB_PATH` when constructing its engine;
the copied MCP module reads the same environment variable when constructing a
separate module-level engine. Their storage entry points call `engine.store`.
The copied engine allocates IDs from process-local state and persists memory
rows through SQLite's replacement statement. The source paths and exact
hashes are listed in [provenance](PROVENANCE.md).

H14 remains open. This is evidence about a conditional storage behavior in a
copied Raven snapshot, not evidence of restoration effects in a deployed
agent.
