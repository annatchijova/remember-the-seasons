# Exp60: Public Memory-ID Reuse Reachability Audit

## Status and scope

**PROPOSED — preregistered before the AST audit checks and execution.** This
bounded static assay inspects the pinned Raven source snapshot under
`sources/raven-memory/`. It is read-only, uses the Python standard library,
and does not edit source snapshots, upstream worktrees, or product code.

Pinned source commit: `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.

## Question and rival

Exp59 demonstrated that calling the copied storage layer with a reused ID
allows prior audit counts to affect a new content incarnation in a synthetic
fixture. Exp60 asks:

> Do Raven's inspected HTTP or MCP memory-ingestion entrypoints accept a
> caller-selected `memory_id` or otherwise call the ID-replacing storage
> method directly?

The benign alternative is that clients cannot select IDs through these
entrypoints: the engine generates IDs inside `store()`, while the lower-level
`MemoryStore.store_memory()` replacement method remains an internal storage
primitive. The rival is that a public ingestion signature exposes the ID or
routes caller-controlled IDs into that replacement method.

## Static checks

Parse the pinned `api_server.py`, `mcp_server.py`, and
`raven/memory_engine.py` with Python's AST and record:

1. Fields declared by HTTP `StoreRequest` and keyword arguments forwarded by
   its `/memories` handler to `engine.store()`.
2. Parameters accepted by MCP `raven_store()` and keyword arguments forwarded
   to `_engine.store()`.
3. Parameters accepted by `AdaptiveMemoryEngine.store()` and the generated-ID
   assignment.
4. Every callsite of `.store_memory()` and its owning function.
5. The SQL conflict behavior in `MemoryStore.store_memory()`.

The public-ID hypothesis is supported if either ingestion signature accepts
`memory_id` or if an endpoint forwards a caller-selected ID to the low-level
replace path. It is refuted for these declared signatures if neither accepts
that field, both delegate to generated-ID `store()`, and the only
`store_memory()` callsite is inside that engine method.

## Limits and invalidation rules

This audit does not run an HTTP server or MCP transport and does not inspect
authorization configuration, proxy behavior, live deployment wiring, or
external wrappers. The generated ID combines a content-hash prefix, a
millisecond timestamp, and a cell sequence; this audit will not claim that
collisions are mathematically impossible or operationally unreachable.

If source hashes differ from the pinned copy, an expected function or route is
missing, or AST checks cannot find the declared call chain, the run is invalid
and requires source-specific review rather than a negative finding.
