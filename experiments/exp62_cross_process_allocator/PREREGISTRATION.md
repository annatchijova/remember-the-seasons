# Exp62: Cross-Process Shared-Database Allocator Assay

## Status and scope

**PROPOSED — preregistered before the cross-process runtime assay.** Exp61
observed stale allocator replacement with separate engine objects in one
process. Exp62 will test whether the same property survives process isolation
using the pinned Raven engine copy and a temporary SQLite file. It will not
start HTTP/MCP transports or edit `sources/`.

Pinned Raven commit: `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.

## Question and rival

Do independently started processes that initialize Raven against the same
SQLite database retain stale local cell allocators, such that later writes
replace rows? Under identical content and a frozen millisecond, do those
processes return the same generated `memory_id`, leaving prior ID-keyed audit
counts associated with the replacement row?

The benign alternative is that process boundaries or SQLite serialization
prevent the collision and preserve both rows. The source-based prediction is
that the lock and allocator are process-local while the database constraints
and `INSERT OR REPLACE` behavior are shared.

## Frozen predictions

1. Start two child processes and wait until both have constructed an engine
   from the same empty database. Then release their different-content writes
   concurrently. Both report the same `cell_id`; SQLite ends with one row.
   The winner may vary, but the surviving row must be one of the returned IDs.
2. Start two child processes and wait until both engines have loaded the empty
   database. Release the first same-content write, insert a synthetic recall
   audit fixture for its ID, then release the second write. With the same
   frozen millisecond, both report the same ID and cell ID, and the actual
   copied consolidator count for that ID remains one after replacement.
3. Reload control: allow process A to write and exit before process B starts.
   Process B must load the advanced allocator, and both rows must remain.

The cross-process hypothesis is falsified for this setup if the first two
conditions preserve two rows or produce distinct cell IDs despite both
children confirming that they initialized before any write. Errors, timeouts,
or lock failures are reported as outcomes, not retried into success.

## Procedure and controls

- Use a fresh temporary SQLite database for every arm and initialize its
  schema in the parent before spawning workers.
- Use Python's `spawn` multiprocessing context so children have independent
  address spaces and engine locks.
- Use events/barriers to establish that both engines are initialized before
  the test writes; freeze the engine module clock only around each store.
- Record readiness counters, returned IDs/cell IDs, row count, surviving
  contender membership, and the copied consolidator's audit count.
- Do not estimate collision frequency from this forced timing condition.

## Limits

This is a controlled runtime assay of the copied engine, not a live Raven
deployment or HTTP/MCP transport test. It establishes behavior only when
independent processes share the same SQLite path and initialize before the
writes. It does not establish whether a specific production deployment does
so or how often identical-content requests land in the same millisecond.
