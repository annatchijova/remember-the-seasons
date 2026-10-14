# Exp57 provenance

## Source snapshot

This assay imports the copied Raven engine through Exp56/Exp55/Exp53/Exp51.
The pinned source is Raven commit
`56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`, recorded in
[`sources/raven-memory/PROVENANCE.md`](../../sources/raven-memory/PROVENANCE.md).
The runner checks the copied source hashes before execution:

| Source file | SHA-256 |
|---|---|
| `memory_engine.py` | `ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0` |
| `sleep_consolidator.py` | `9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39` |

Source observations underlying the prediction:

- `sources/raven-memory/raven/memory_engine.py:1031–1047` writes an activation
  timestamp and increments the persisted recall counter.
- `sources/raven-memory/raven/memory_engine.py:1810–1822` computes an
  age-dependent recency bonus from `last_activation`.
- `sources/raven-memory/raven/sleep_consolidator.py:263–276` inserts a merged
  node with `last_activation=0.0`.

## Isolation and artifacts

All branches and controls use disposable SQLite clones in temporary
directories. Only the canonical JSON result is written to this experiment
directory by the runner. No `sources/` file, upstream working tree, live
service, network, provider, personal data, or credentials are modified or
used.

## Epistemic status

- **OBSERVED:** the pinned source updates `last_activation`, consumes it in
  retrieval scoring, and initializes the merged node's field to zero.
- **OBSERVED:** the runtime assay compares two timestamp allocations, an
  equalization control, a zero-recency mutation, and post-consolidation traces.
- **INFERRED:** a pre-consolidation score difference that disappears when the
  timestamps are equalized and when recency is disabled is mediated by the
  tested recency path in this fixture.
- **UNKNOWN:** whether other Raven snapshots or deployed agents preserve,
  expose, or use temporal history in the same way.
