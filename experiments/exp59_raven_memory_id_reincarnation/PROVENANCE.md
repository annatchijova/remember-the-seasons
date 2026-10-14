# Exp59 provenance

## Source snapshot

The assay imports the copied Raven source through Exp56/Exp55/Exp53/Exp51,
pinned at commit `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f` and recorded in
[`sources/raven-memory/PROVENANCE.md`](../../sources/raven-memory/PROVENANCE.md).
The runner verifies the copied source hashes before each run:

| Source file | SHA-256 |
|---|---|
| `memory_engine.py` | `ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0` |
| `sleep_consolidator.py` | `9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39` |

Source observations:

- `sources/raven-memory/raven/sleep_consolidator.py:79–95` counts retrieved
  entries by `memory_id` and does not compare their recorded content hash to
  the current row.
- `sources/raven-memory/raven/memory_engine.py:856–875` stores rows using
  `INSERT OR REPLACE`; it does not clear audit events when replacing a row.
- `sources/raven-memory/raven/sleep_consolidator.py:170–183` uses the resulting
  counts as weights for the merged embedding.

## Isolation and epistemic status

All histories and replacements use synthetic memories in temporary SQLite
clones. The runner uses the copied store layer, offline consolidator, fixed
vectors, and fixed clock. No file under `sources/`, upstream working tree,
live service, network, provider, personal data, or credentials are modified or
used.

- **OBSERVED:** same-ID replacement of different content left the previous
  audit rows intact; their old counts were applied to the current row at the
  next consolidation in this fixture.
- **OBSERVED:** fresh IDs did not inherit those counts; filtering audit entries
  by current content hash also removed the observed merge difference.
- **INFERRED:** the historical effect is mediated by joining audit records to
  current memories by ID without incarnation/content validation.
- **UNKNOWN:** whether memory IDs are intended to represent stable logical
  identities across content replacement in Raven's public contract, and
  whether this pattern is reachable through any deployed API.
