# Exp61 provenance

## Source copies

Raven snapshot commit: `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`.

| Copied source | SHA-256 |
|---|---|
| `raven_snapshot/memory_engine.py` | `ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0` |
| `raven_snapshot/spectral.py` | `36d5a1198a9f7a817ec8cd540f2f4c8c1c9a0c26e74782c2ef4d38fcf257ca90` |
| `raven_snapshot/sleep_consolidator.py` | `9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39` |

The copies match the pinned snapshot. `sources/` remains unmodified. The
experiment imports the copied engine and consolidator and writes only to
temporary SQLite files.

## Execution

Python 3 with the repository environment's installed NumPy and SciPy. No new
package was installed. From this directory:

```sh
python3 -m unittest -v test_exp61_shared_database_allocator.py
python3 exp61_shared_database_allocator.py
```

`result.json` is the recorded runner output. The tests replay the assay and
compare the complete result object to the artifact. A deliberate mutation in
a separate `/tmp` copy changed the memory-row statement from `INSERT OR
REPLACE` to `INSERT OR IGNORE`; the two replacement-specific tests failed,
while the single-engine, reload, and provenance controls passed.
