# Exp60: Public Memory-ID Reuse Reachability Audit

## Result

**OBSERVED — pinned source snapshot:** the inspected HTTP and MCP ingestion
signatures do not accept `memory_id`. The HTTP `/memories` handler forwards
content and other fields to `eng.store()` through `asyncio.to_thread`; MCP
`raven_store()` calls `_engine.store()`. `AdaptiveMemoryEngine.store()` creates
the ID internally. In the Python files in this snapshot, the only call to
`store_memory()` is from `AdaptiveMemoryEngine.store()`.

**INFERRED — bounded reachability conclusion:** Exp59's direct same-ID
replacement setup is not shown reachable through these declared HTTP or MCP
ingestion paths, because those paths provide no ID parameter and terminate at
the generated-ID engine method. A wrapper or another route could change this
conclusion; such paths were not inspected.

## Source observations

- `sources/raven-memory/api_server.py:203-209` declares `StoreRequest` fields;
  none is `memory_id`.
- `sources/raven-memory/api_server.py:383-414` defines the `/memories` handler
  and forwards request data to `eng.store()` without an ID.
- `sources/raven-memory/mcp_server.py:110-117` declares `raven_store()` inputs;
  none is `memory_id`. Lines 152-159 forward those values to `_engine.store()`.
- `sources/raven-memory/raven/memory_engine.py:1526-1535` declares
  `AdaptiveMemoryEngine.store()` without a `memory_id` parameter. Lines
  1541-1544 derive an ID from a content-hash prefix, millisecond timestamp, and
  cell sequence.
- `sources/raven-memory/raven/memory_engine.py:1562` is the sole
  `store_memory()` callsite found by the snapshot-wide AST scan.
- `sources/raven-memory/raven/memory_engine.py:856-875` implements that lower
  level method with `INSERT OR REPLACE`.

The inspected source is pinned to commit
`56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`; the three analyzed file hashes are
recorded in `PROVENANCE.md` and checked by the runner.

## Falsification status

The preregistered public-ID hypothesis was not supported for the two declared
ingestion signatures: neither accepts or forwards a caller-selected ID, and
both use the ID-generating engine method. This does not falsify Exp59's storage
layer result. It narrows its demonstrated reachability.

## Unknowns and limits

**UNKNOWN:** whether time-based generated IDs can collide in practice, how
likely any collision is under concurrency or restart conditions, and whether
live deployments expose additional wrappers or ingestion routes. The audit
does not start either server, exercise a transport, inspect authorization or
proxy configuration, or survey deployment code. The ID construction's
operational collision behavior needs a separate runtime assay.

Five tests passed. This is static evidence about one pinned source snapshot,
not a runtime API security guarantee or a claim about every Raven deployment.
