# Exp51 Source Provenance

## Source

- **OBSERVED:** upstream repository snapshot: `sources/raven-memory/`
- **OBSERVED:** source commit: `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`
- **OBSERVED:** source snapshot digest: `4eee9af6a22ec8311b0bf3d289bce166cb7d6a7b83c99687d004a490dcd302f4`
- **OBSERVED:** the package copied into `vendor/raven/` is the `raven/`
  directory from that snapshot. The source snapshot remains read-only.
- **OBSERVED:** SHA-256 hashes for each copied Python file are recorded below.

| Copied file | SHA-256 |
|---|---|
| `vendor/raven/__init__.py` | `f368f8e50937e14e0263f83b9cfcf87f3cffcf6089f5e8819181ae675b460f9b` |
| `vendor/raven/intervention.py` | `b5f34cbea5410225a64518837ce76d02e99e7e9eedb566c76e285bd5c1f339a6` |
| `vendor/raven/memory_engine.py` | `ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0` |
| `vendor/raven/portability.py` | `2747a81180612ca775e25353278533bd4196d4a3fb280c1b66f4cb5a0a2e6869` |
| `vendor/raven/qwen_client.py` | `ea65cea97188928b0edac243928195e53aa3efdb2facc4f91d940fb17d805472` |
| `vendor/raven/sleep_consolidator.py` | `9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39` |
| `vendor/raven/spectral.py` | `36d5a1198a9f7a817ec8cd540f2f4c8c1c9a0c26e74782c2ef4d38fcf257ca90` |

## Source-grounded mechanism claims

- **OBSERVED:** `MemoryEntry` stores an embedding, state, activation metadata,
  and `synaptic_links` (`sources/raven-memory/raven/memory_engine.py:153-169`).
- **OBSERVED:** `_recall_core()` documents `suppressed` cells as unable to seed,
  relay, fire links, or rank (`sources/raven-memory/raven/memory_engine.py:1614-1639`). In the copied
  implementation, however, the current-turn synaptic-source loop iterates
  `current_turn_memories` without filtering suppressed source cells, and only
  checks whether a synaptic *target* is suppressed
  (`sources/raven-memory/raven/memory_engine.py:1855-1888`). The synthetic fixture test reproduces a
  suppressed A still emitting a synaptic pull to C when A is passed as a
  current-turn source.
- **OBSERVED:** normal `recall()` runs the core, applies STDP from
  `current_turn_memories`, updates activation timestamps/counts, and writes an
  audit row (`sources/raven-memory/raven/memory_engine.py:1953-1989`). The harness applies the copied
  STDP and activation operations itself so it can omit target writes during
  absence; it does not call public `recall()`.
- **OBSERVED:** `intervene()` pairs baseline and suppressed core evaluations
  over one snapshot and one `now`, writes an audit row, and limits its claim to
  retrieval rather than downstream agent answers
  (`sources/raven-memory/raven/memory_engine.py:2025-2050`, `2062-2075`).
- **INFERRED:** current-turn source filtering is needed to make a longitudinal
  “A cannot influence retrieval” treatment consistent with the documented
  suppression contract. This inference is confirmed for the tested fixture by
  comparing raw core output with the experiment adapter; other input shapes
  remain untested.

## Environment and fixture

- **OBSERVED:** Python 3.12, NumPy 1.26.4, SciPy 1.11.4 at execution time.
- **OBSERVED:** exact SciPy KDTree selected through `RAVEN_ANN_BACKEND=kdtree`.
- **OBSERVED:** no HNSW, model, embedding provider, network, credential, personal memory, or
  external service used.
- **OBSERVED:** four synthetic rows, fixed 8-dimensional vectors, fixed SQLite timestamps,
  fixed query schedule, and fixed core `now` values.
- **OBSERVED:** final seed snapshot logical digest is in the run JSON. Each arm is made from
  the same SQLite seed using SQLite's backup API.
- **OBSERVED:** runner artifact SHA-256 is
  `32f7e0cd225b8bcfde9ebcbfd8997de4fe2fb239eee8581605fd09e22dcb3dc0`.
