# Exp58 provenance

## Source snapshot

Exp58 imports the copied Raven engine and consolidator through Exp57, pinned at
Raven commit `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`. Provenance is recorded
in [`sources/raven-memory/PROVENANCE.md`](../../sources/raven-memory/PROVENANCE.md).
The runner verifies the copied files against these SHA-256 values:

| Source file | SHA-256 |
|---|---|
| `memory_engine.py` | `ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0` |
| `sleep_consolidator.py` | `9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39` |

Source-level observations used to bound the outcome:

- The scoring path consumes `last_activation` for the recency term:
  `sources/raven-memory/raven/memory_engine.py:1810–1822`.
- `recall()` persists the top results' activation timestamp and writes an audit
  entry: `sources/raven-memory/raven/memory_engine.py:1930–1985`.
- The memory update stores `last_activation` and increments `recall_count`:
  `sources/raven-memory/raven/memory_engine.py:1031–1047`.
- Audit-chain verification checks row linkage and hash integrity:
  `sources/raven-memory/raven/memory_engine.py:484–525`.

## Isolation and epistemic status

All treatments, consolidation, and longitudinal calls run on independent
temporary SQLite clones with synthetic vectors. The only repository artifact
written by the runner is the canonical JSON result. No file under `sources/`,
upstream working tree, live service, network, provider, personal data, or
credential is modified or used.

- **OBSERVED:** the assay found matching per-step memory outputs and memory/link
  state digests while audit hashes stayed different; both audit chains verified.
- **INFERRED:** within this finite input sequence, the retained audit-history
  difference did not cause divergence in the selected retrieval outputs or
  mutable memory/link state.
- **UNKNOWN:** behavior for other Raven operations, arbitrary sequences,
  concurrent calls, other snapshots, or downstream agents.
