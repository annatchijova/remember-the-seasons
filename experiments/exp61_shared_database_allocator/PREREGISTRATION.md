# Exp61: Shared-Database Allocator Collision Assay

## Status and scope

**PROPOSED — preregistered before the runtime assay.** This experiment will
exercise the pinned Raven source snapshot in an isolated temporary SQLite
database. It will not alter `sources/`, an upstream working tree, or a product
implementation. It will use the repository's existing Python dependencies;
no dependency will be added.

Source snapshot: Raven commit `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.

## Question and rival

When two independent `AdaptiveMemoryEngine` instances open the same database
before either writes, can their per-instance `_next_cell_id` allocators create
a uniqueness conflict that replaces a stored row? Under the stricter case of
identical content, the same frozen millisecond, and the same stale counter,
does the generated `memory_id` also repeat and retain audit history attached
to that ID?

The benign alternative is that shared-database writes remain distinct and
preserve both rows even when instances were initialized from the same state.
The competing prediction follows from the declared source behavior: each
engine has an instance-local lock and allocator; the ID includes a content-hash
prefix, millisecond timestamp, and local cell sequence; SQLite declares both
`memory_id` primary-key and `cell_id` unique constraints, and uses
`INSERT OR REPLACE` for storage.

## Frozen predictions

1. **Single-engine control:** two sequential stores through one engine allocate
   distinct cell IDs and leave two database rows.
2. **Stale independent allocators, different content:** two engines opened
   before either store start from the same next cell ID. After the first write,
   the second uses that stale cell ID. Regardless of whether timestamps match,
   the unique-cell conflict will leave one of the two rows in SQLite after
   `INSERT OR REPLACE`.
3. **Exact generated-ID collision:** in the stale-allocator setup, same content
   plus a frozen clock yields the same generated memory ID. Two writes leave
   one memory row under that ID. A preexisting audit event keyed to the ID
   remains present and therefore can be counted by ID-based aggregation.
4. **Reload control:** after the first engine writes, constructing a second
   engine from the same database reloads the next cell ID; a later store with
   different content persists as a second row with a distinct cell ID.

The assay is falsified if the source-backed runtime does not show the predicted
row and identifier outcomes. It will not convert a matching identifier into a
claim about production frequency.

## Procedure

- Use a fresh temporary database for each arm.
- Pin the engine clock during stores requiring exact millisecond control.
- Give each engine a separate `AdaptiveMemoryEngine` object backed by the same
  SQLite path; no external API server or MCP transport is started.
- Record generated IDs, cell IDs, SQLite rows, and audit rows after each write.
- Run a negative control through one shared engine and a reload control that
  constructs the second engine only after the first write.
- If the pinned engine cannot be imported with already installed dependencies,
  stop and report the environment limitation instead of substituting a hand
  implementation.

## Limits

This is an isolated same-process runtime assay over two engine instances and a
temporary database, not a deployed multi-process frequency study. A frozen
clock deliberately creates a boundary condition; it does not estimate how
often that condition occurs naturally. It does not test process crashes,
distributed filesystems, production server wiring, or arbitrary wrappers.
