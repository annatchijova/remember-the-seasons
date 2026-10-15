# Exp62 provenance

## Source copies

Raven snapshot commit: `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.

| Copied source | SHA-256 |
|---|---|
| `raven_snapshot/memory_engine.py` | `ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0` |
| `raven_snapshot/spectral.py` | `36d5a1198a9f7a817ec8cd540f2f4c8c1c9a0c26e74782c2ef4d38fcf257ca90` |
| `raven_snapshot/sleep_consolidator.py` | `9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39` |

The experiment imports only these copied Raven files and writes temporary
SQLite databases. `sources/` remains unchanged.

## Execution

Run from this directory with Python 3 and the already installed NumPy/SciPy:

```sh
python3 -m unittest -v test_exp62_cross_process_allocator.py
python3 exp62_cross_process_allocator.py
```

The five tests verify both pre-write process counters, concurrent cell-ID
collision, exact generated-ID reuse and audit-count continuity, the reload
control, source-copy hashes, and replay against `result.json`.

A mutation in a temporary `/tmp` copy changed `INSERT OR REPLACE` to
`INSERT OR IGNORE`. The exact-ID replacement's stored-embedding assertion
failed; the complete-result replay check also failed because the mutated copy
had a different recorded source hash. The unmodified experiment directory
was not changed by that mutation.
