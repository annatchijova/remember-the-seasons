# Exp61: Shared-Database Allocator Collision Assay

## Result

**OBSERVED — runtime on copied Raven source:** two independent engine objects
initialized against the same empty SQLite database each held `_next_cell_id`
at zero. When the first stored one content and the second stored different
content, both returned `cell_id = 0`; the second `INSERT OR REPLACE` left one
row, containing the second content. Their generated `memory_id` values differed
because the content hashes differed.

**OBSERVED — exact-ID boundary case:** with the same two stale instances, equal
content, and a frozen millisecond timestamp, both returned the same
`memory_id` and `cell_id`. After an audit event referencing that ID was
recorded, the second store replaced the memory row. Raven's copied
`get_recall_counts()` still counted the old audit event for the new row's ID
(1 before and 1 after replacement).

**OBSERVED — controls:** two sequential stores through one engine produced two
rows with cell IDs 0 and 1. Constructing the second engine after the first
write also loaded cell ID 1 and preserved both rows.

## Source basis

- `sources/raven-memory/raven/memory_engine.py:1267-1274` applies an `RLock`
  stored on an engine instance; line 1378 initializes that lock on the
  instance.
- `sources/raven-memory/raven/memory_engine.py:1341` initializes the local
  cell allocator; lines 1413 and 1426-1427 reset it from persisted memories
  and set it to `max(cell_id) + 1`.
- `sources/raven-memory/raven/memory_engine.py:1541-1544` derives
  `memory_id` from a content-hash prefix, millisecond timestamp, and local
  allocator, then increments the allocator.
- `sources/raven-memory/raven/memory_engine.py:746-754` declares
  `memory_id` as primary key and `cell_id` as unique.
- `sources/raven-memory/raven/memory_engine.py:856-875` writes with
  `INSERT OR REPLACE`.
- `sources/raven-memory/raven/sleep_consolidator.py:79-96` counts audit
  retrievals by the `memory_id` field in `memories_retrieved`.

The copied files are hash-pinned in `PROVENANCE.md`. The recorded JSON is
reproducible under the experiment's frozen clock and isolated databases.

## Interpretation

**INFERRED:** if two live engine instances share a database while retaining
allocator state loaded before either write, a stale `cell_id` can cause one
memory row to replace another even when their generated `memory_id` values
differ. If equal content is also stored within the same generated millisecond,
the ID repeats and historical audit entries keyed only by that ID are counted
for the replacement row. The evidence confirms this condition in the copied
engine; it does not establish that a deployed Raven configuration creates the
condition.

Exp60 found that the inspected HTTP and MCP entrypoints do not take a
caller-supplied `memory_id`. Exp61 shows a different possible route: ID reuse
can arise from engine-generated values under the controlled stale-allocator
condition. It does not overturn Exp60's bounded signature finding.

**OBSERVED — source configuration:** the API engine uses `RAVEN_DB_PATH`
(`sources/raven-memory/api_server.py:160-165`), and the separate MCP engine
uses the same variable (`sources/raven-memory/mcp_server.py:67-68`). **INFERRED:**
the two services can be configured to share a SQLite file. Whether an actual
deployment does so was not checked here; Exp62 tests the conditional behavior
with independent processes and a temporary shared database.

## Falsification and limits

The stale-allocator predictions survived the runtime assay; the benign
single-engine and reload controls preserved both records. In a separate
temporary copy, mutating `INSERT OR REPLACE` to `INSERT OR IGNORE` caused both
replacement-specific tests to fail. This supports the test oracle for the
replacement behavior.

The writes were sequential calls on two engine objects in one process, with a
frozen clock for determinism. This was not a simultaneous-thread or
cross-process race test, did not start HTTP/MCP transports, and does not
estimate natural collision frequency. The audit row was inserted as a
synthetic fixture; the copied consolidator's actual ID-counting function was
used to check its carryover. Whether production deployments share a database
between multiple live engine instances, whether they reload state around
writes, and how often same-content writes land in one millisecond remain
**UNKNOWN**.

Six tests passed, including exact result replay and the two controls. H14
remains open; this assay is bounded to the pinned Raven implementation.
