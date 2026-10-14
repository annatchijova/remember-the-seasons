# Raven Observational Contract for H14

## Purpose and evidence boundary

This document defines candidate observation boundaries for an H14 transfer
assay. It is a static audit of the read-only Raven snapshot pinned at
[`sources/raven-memory/PROVENANCE.md`](../sources/raven-memory/PROVENANCE.md):
commit `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`, exported on 2026-10-02.
It does not describe every deployment or every possible Python caller.

**OBSERVED:** the snapshot exposes HTTP routes, MCP tools, engine methods, and
offline utilities with different outputs and side effects. References below
point to those source files. **UNKNOWN:** whether a live deployment has the
same configuration, callers, storage layout, provider behavior, or route
wrappers. No Raven source, upstream working tree, or live database was changed
or inspected for this contract.

Epistemic labels used here:

- **OBSERVED** — directly supported by the pinned source snapshot or a cited
  experiment artifact.
- **INFERRED** — follows from observed code under the stated conditions; a
  counterexample under those conditions would refute it.
- **PROPOSED** — a contract or experiment design that has not been run.
- **UNKNOWN** — available evidence does not settle the claim.

## Operation surface

### HTTP API

The route handlers are in
[`api_server.py`](../sources/raven-memory/api_server.py). The two routes marked
`include_in_schema=False` still exist even though they are omitted from the
OpenAPI schema (lines 331–346).

| Operation | Returned observation | Effects visible in source | Evidence |
|---|---|---|---|
| `GET /api`, `GET /health` | Service/version; health, embedding-provider status and, when auth is disabled, engine stats/configuration | `GET /health` reads provider and engine state; no persistent write is shown | [`api_server.py:349–374`](../sources/raven-memory/api_server.py#L349) |
| `GET /memories`, `GET /memories/{id}` | Memory metadata, content preview/full content, counters, timestamps; embeddings are omitted by the single-item route | Database reads; no persistent write is shown in handlers | [`api_server.py:431–471`](../sources/raven-memory/api_server.py#L431) |
| `POST /memories` | New ID, cell, state, layer, timestamp, provider | Calls embedder and `engine.store`; changes persistent and in-memory field state, field-generation cache key, process metrics, and may emit a WebSocket event | [`api_server.py:381–428`](../sources/raven-memory/api_server.py#L381) |
| `POST /recall` | Recalled memories, scores, answer, audit and stats, provider status, cache indicator and latency | Cache hits update LRU order and a counter. Cache misses call `process_message`, which recalls, updates session histories, may write an audit entry and activation/STDP state, may call an LLM, and optionally stores the query. The handler changes process metrics/cache and broadcasts an event. | [`api_server.py:508–563`](../sources/raven-memory/api_server.py#L508); [`qwen_client.py:385–487`](../sources/raven-memory/raven/qwen_client.py#L385); [`memory_engine.py:1930–1991`](../sources/raven-memory/raven/memory_engine.py#L1930) |
| `POST /memories/{id}/reinforce`, `/forget`; `POST /cell-links` | New state or link declaration | Changes persistent field state and in-memory indices; handlers bump field-generation counter; reinforce/forget also read stats and broadcast | [`api_server.py:474–501`](../sources/raven-memory/api_server.py#L474); [`api_server.py:570–580`](../sources/raven-memory/api_server.py#L570); [`memory_engine.py:2171–2213`](../sources/raven-memory/raven/memory_engine.py#L2171) |
| `POST /consolidate` | Consolidation preview or counts | Default request is mutating (`dry_run=False`); actual changes reload engine indexes. The handler changes counters and broadcasts when rows are created. | [`api_server.py:275–279`](../sources/raven-memory/api_server.py#L275); [`api_server.py:594–611`](../sources/raven-memory/api_server.py#L594); [`memory_engine.py:2433–2451`](../sources/raven-memory/raven/memory_engine.py#L2433) |
| `GET /graph` | Nodes, edges, truncation flag, total node count | Reads persistent memory/link data. When truncated, selection is by `recall_count DESC` without a declared secondary tie-break. | [`memory_engine.py:952–960`](../sources/raven-memory/raven/memory_engine.py#L952); [`memory_engine.py:2257–2294`](../sources/raven-memory/raven/memory_engine.py#L2257) |
| `GET /stats`, `/audit`, `/metrics`, `/alerts` | Aggregate stats, verified audit rows, process/provider metrics, alerts | Read persistent and/or process-local state. `/metrics` includes counters, cache size, and WebSocket client count; `/audit` verifies returned rows. | [`api_server.py:618–702`](../sources/raven-memory/api_server.py#L618) |
| `GET /`, `GET /demo` | Static file or service fallback; demo file or 404 | File/system configuration dependent; no memory-field write is shown | [`api_server.py:331–346`](../sources/raven-memory/api_server.py#L331) |
| `WS /ws` | Connection/stats/pong messages and pushed events | Adds/removes a process-local client registration; reads stats; broadcasts carry timestamps. Connection state and emitted event stream are observable. | [`api_server.py:297–317`](../sources/raven-memory/api_server.py#L297); [`api_server.py:709–755`](../sources/raven-memory/api_server.py#L709) |

**OBSERVED:** the recall cache, generation counter, process counters, and
WebSocket registry live in process memory ([`api_server.py:214–249`](../sources/raven-memory/api_server.py#L214)). Rate limiting also records request hits for protected routes
([`api_server.py:82–124`](../sources/raven-memory/api_server.py#L82)).
Authentication is conditional on configuration; `require_token` permits
requests when no token is configured ([`api_server.py:67–79`](../sources/raven-memory/api_server.py#L67)). These details mean HTTP method names alone do not define observational purity.

### MCP tools

The MCP server declares the following tools in
[`mcp_server.py`](../sources/raven-memory/mcp_server.py). This is a separate
interface from HTTP; an assay using one does not automatically cover the
other.

| Tool | Output and source-visible effects | Evidence |
|---|---|---|
| `raven_store` | New memory identifiers, state and provider; embeds and stores a memory | [`mcp_server.py:110–168`](../sources/raven-memory/mcp_server.py#L110) |
| `raven_recall` | Scored recalled rows and audit hash; embeds query, invokes effectful `engine.recall`, then optionally filters results by topic | [`mcp_server.py:172–252`](../sources/raven-memory/mcp_server.py#L172) |
| `raven_reinforce`, `raven_forget`, `raven_create_link` | Updated state or link; mutate engine/store state | [`mcp_server.py:256–352`](../sources/raven-memory/mcp_server.py#L256) |
| `raven_stats`, `raven_get_memory`, `raven_audit_trail`, `raven_verify_chain`, `raven_info` | Stats, a memory record, audit/verification results, or engine description; source shows reads | [`mcp_server.py:355–424`](../sources/raven-memory/mcp_server.py#L355); [`mcp_server.py:445–510`](../sources/raven-memory/mcp_server.py#L445) |
| `raven_export_graph` | Truncated graph; uses the engine graph export and inherits its tie-selection behavior | [`mcp_server.py:427–442`](../sources/raven-memory/mcp_server.py#L427) |
| `raven_consolidate` | Preview by default; with `dry_run=False`, applies consolidation | [`mcp_server.py:468–488`](../sources/raven-memory/mcp_server.py#L468) |

### Engine, provider, and offline operations

**OBSERVED:** `AdaptiveMemoryEngine.recall()` invokes the retrieval core and
then applies pending alerts, optional enforcement-forget behavior, STDP and
activation updates, and audit persistence
([`memory_engine.py:1930–1991`](../sources/raven-memory/raven/memory_engine.py#L1930)).
The lower-level `_recall_core()` is the narrower scoring/propagation operation
used by the paired `intervene()` method. `intervene()` runs baseline and
suppressed retrieval over one field snapshot and timestamp, returns detailed
scored results/deltas, and writes an audit row; its documentation limits its
claim to Raven retrieval, not downstream agent answers
([`memory_engine.py:2026–2108`](../sources/raven-memory/raven/memory_engine.py#L2026)).

**OBSERVED:** the embedding provider reports active/preferred provider,
fallback count, and degraded status ([`qwen_client.py:120–127`](../sources/raven-memory/raven/qwen_client.py#L120)). The orchestration method also calls the LLM and updates bounded per-session turn and conversation histories ([`qwen_client.py:385–487`](../sources/raven-memory/raven/qwen_client.py#L385)). Those provider and session effects are outside a retrieval-core-only observation.

**OBSERVED:** offline utilities add distinct operations. `export_field` writes
an export artifact; `import_field` writes into a database
([`portability.py:59–165`](../sources/raven-memory/raven/portability.py#L59)).
Sleep consolidation can preview or apply merges; a non-dry run writes state
and audit data ([`sleep_consolidator.py:385–444`](../sources/raven-memory/raven/sleep_consolidator.py#L385)). These are not equivalent to the HTTP or MCP contracts.

## Exp54 connection and its limit

**OBSERVED, bounded to Exp54's copied snapshot and synthetic fixture:**
retrieval scores/rankings matched on four fixed probes, and the tested five
mutating actions preserved that retrieval equivalence. Inspection and stats
distinguished states. Reversing physical SQLite row order changed a tied
winner in a truncated graph export for that fixture. See the
[Exp54 report and preregistration](../experiments/exp54_raven_observational_contract/).

**INFERRED:** Raven's behavior cannot be represented by one unqualified
"equivalent" relation. The relation changes with the selected operations,
outputs, state transitions, and treatment of volatile/environmental values.
The Exp54 tie result is a concrete reason to control or normalize storage
ordering when graph export is included; it does not establish that every
export or database layout diverges.

## Proposed equivalence contracts

These are **PROPOSED** definitions for future preregistration. None has yet
been exhaustively checked over Raven's state space.

Let a Raven state be split into persistent field state `P`, process-local
application/session state `V`, and external provider/environment state `E`.
For the same declared input `x`, transition action `a`, and controlled
environment, compare both the immediate observation `O` and successor state
`T`:

`s ~_C t` iff for every permitted input/action sequence in contract `C`, the
normalized observations are equal at each step and successor states remain in
the same equivalence class.

| Contract | Observations retained | Intended claim |
|---|---|---|
| **Retrieval-core equivalence** | Full candidate scores, ordering, activation/propagation trace, exclusions, and intervention delta from `_recall_core`; fixed stored query vector, clock, parameters, and field snapshot | Same retrieval mechanism behavior for a declared query set |
| **Adapter-response equivalence** | Declared HTTP or MCP response fields after normalization; specify whether answer text, provider status, cache indicators, IDs, timestamps, and errors are included | Same behavior at one selected external interface |
| **Operational-trace equivalence** | Adapter responses plus persistent-state diffs, process-local state diffs, emitted events, and declared external calls/results over action sequences | Same behavior across the chosen complete operation surface |

The contracts are nested only when the broader contract explicitly includes
the narrower outputs and transitions. HTTP and MCP are separate alphabets.
An assay must state which interface it exercises. It must also state how it
handles timestamps, random/generated identifiers, floating-point tolerances,
provider calls, cache state, concurrency, rate limits, and database order.
Silently dropping one of these fields can make two traces appear equivalent.

## Exp55 result and remaining boundary

**OBSERVED, copied Raven snapshot and synthetic fixture:** Exp55 exercised
non-dry-run consolidation on states differing only in the persisted
`C.recall_count` while holding the audit history fixed. The merged node,
logical database, and C/D retrieval traces matched. The preregistered canary
changed audit-derived weights and produced a different merged embedding and
the predicted opposing C/D score shifts. The five-test suite also detected a
temporary mutant that made consolidation read row counters instead of audit
counts. See the [Exp55 report and artifacts](../experiments/exp55_raven_counter_consolidation/).

**INFERRED, bounded:** the stored counter difference did not affect later
retrieval through this consolidation schedule. The audit history did. This
does not establish equivalence for Raven's complete operation surface,
generalize to a deployed agent, or close H14. The proposed equivalence
contracts above remain definitions for future assays, not a computed Raven
quotient.
