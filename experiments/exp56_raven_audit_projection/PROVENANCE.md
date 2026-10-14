# Exp56 provenance

## Source snapshot

The experiment imports the copied Raven engine through Exp55/Exp53/Exp51.
The source snapshot is Raven commit
`56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`, recorded in
[`sources/raven-memory/PROVENANCE.md`](../../sources/raven-memory/PROVENANCE.md).

The runtime verifies these files in Exp51's vendored copy before executing:

| Source file | SHA-256 |
|---|---|
| `memory_engine.py` | `ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0` |
| `sleep_consolidator.py` | `9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39` |

The relevant source observations are:

- `sources/raven-memory/raven/sleep_consolidator.py:79–95`: recall counts are
  reconstructed from `audit_log.memories_retrieved`.
- `sources/raven-memory/raven/sleep_consolidator.py:170–183`: those counts
  weight the merged embedding and are included in consolidation metadata.
- `sources/raven-memory/raven/sleep_consolidator.py:416–436`: the consolidator
  obtains the counts and executes the declared consolidation path.

## Experiment artifacts

All database clones are created in temporary directories. The runner writes a
canonical JSON result to this directory only when invoked directly. The tests
rebuild fresh fixtures and replay the result. No file under `sources/` is
modified; no upstream working tree, live service, network, provider, personal
data, or credential is used.

## Epistemic status

- **OBSERVED:** the pinned source implements the cited count projection and
  count-weighted merge behavior.
- **OBSERVED:** the report records the outcome of the synthetic runtime assay.
- **INFERRED:** matching tested downstream outputs when order and query text
  vary supports sufficiency of the count vector for those outputs in this
  fixture. It does not establish sufficiency for other Raven operations.
- **UNKNOWN:** whether the same result holds for other snapshots, production
  databases, other merge groups, or agent-level outcomes.
