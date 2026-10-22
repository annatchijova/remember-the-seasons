# Exp63: Cross-Service Shared-Database Allocator Assay

## Status and scope

**PROPOSED — preregistered before runtime execution.** Exp62 showed that
independent Raven engine processes can reuse allocator state when they open
the same SQLite file before either writes. Exp63 will test that condition
through the copied Raven API and MCP store entry points in separate
processes. It will use a temporary database and copied source only.

Pinned source commit: `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.

## Question and rival

When the API and MCP entry points initialize independently against the same
SQLite path before writes, do their actual store handlers reproduce Exp62's
stale-allocator row replacement?

The benign alternative is that entry-point initialization, embedding,
request handling, or SQLite coordination prevents the collision and keeps
both rows.

## Source observations

- **OBSERVED:** the API lifespan constructs an engine from
  `RAVEN_DB_PATH` (`raven_snapshot/api_server.py:160-165`).
- **OBSERVED:** the MCP module constructs a separate engine from
  `RAVEN_DB_PATH` at import (`raven_snapshot/mcp_server.py:67-68`).
- **OBSERVED:** the API `store_memory` handler calls `eng.store` after
  embedding (`raven_snapshot/api_server.py:383-420`); the MCP
  `raven_store` tool calls `_engine.store` after embedding
  (`raven_snapshot/mcp_server.py:110-166`).
- **OBSERVED:** the engine builds IDs from content hash, millisecond time,
  and its in-memory allocator, and persists through the copied storage path
  (`raven_snapshot/raven/memory_engine.py:1526-1565`,
  `:746-754`, `:856-875`).

These source observations motivate the assay; they do not establish that any
deployment launches both entry points against one file.

## Frozen predictions

1. Start one API process and one MCP process against a fresh shared database.
   Wait until each reports allocator value zero, then release different
   content stores concurrently. Both should return cell ID zero, while the
   database retains one memory row whose ID belongs to one of the two
   results.
2. In a separate database, initialize both processes first. Release the API
   store for identical content, add a synthetic audit event for its returned
   ID, and then release the MCP store. With the same frozen millisecond, both
   should return the same memory ID; the row should be replaced and the
   copied consolidator should still count the earlier audit event for that
   ID.
3. Negative control: let the API process store and exit before starting the
   MCP process. MCP should load allocator value one, allocate cell ID one,
   and preserve both rows.

The cross-service prediction is falsified for this harness if, after both
processes confirm initialization at zero, the two stores preserve separate
rows with distinct cell IDs. Initialization failures, request failures,
timeouts, and lock errors count as assay failures, not as evidence for or
against the allocator prediction.

## Harness boundaries

- Spawn independent Python processes and use only fresh temporary SQLite
  files.
- Invoke the copied API route handler and registered MCP tool function
  directly. This exercises their store entry-point code, but bypasses HTTP
  networking, API middleware/dependency injection, and MCP JSON-RPC framing.
- Replace only embedding output with deterministic 384-dimensional vectors
  and freeze the copied engine clock around each store. These controls remove
  model downloads and timing variance without changing allocator or SQLite
  behavior. API and MCP processes receive different vectors for the same
  content, so the surviving embedding identifies whether replacement took
  place.
- In the API child, replace `asyncio.to_thread` with an async inline executor
  for the handler call. The unmodified handler's thread-offloaded engine store
  stalled repeatedly in this local harness even in an isolated call. This
  accommodation preserves the handler's validation, embedding, store, metric,
  and response logic, but excludes API thread-offload behavior from Exp63.
- Preserve the concurrent winner as nondeterministic; assert only that it
  is one of the contenders.
- Do not estimate natural collision frequency or infer deployment topology.

## Interpretation limits

A reproduced collision would establish a conditional cross-entry-point
behavior in the copied snapshot under a shared file and controlled startup
order. It would not establish that a deployed API/MCP pair shares a database,
that its normal embedding provider returns the same vectors, or how often a
collision occurs. A falsified prediction would bound the result to Exp62's
lower-level harness and require inspection of the entry-point differences.
