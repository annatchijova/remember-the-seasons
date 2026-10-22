# Exp63 provenance

## Source snapshot

- Repository: `https://github.com/annatchijova/raven-memory.git`
- Commit: `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`
- Snapshot path: `sources/raven-memory/`
- Experiment code runs only against the copied files under `raven_snapshot/`.
- The `sources/` tree was not modified.

| Copied file | SHA-256 |
|---|---|
| `api_server.py` | `f83a88e1cb6a89b92319184ca4fecc13a5d1223a1ddf904bddabbc01e462a9b5` |
| `mcp_server.py` | `f89a21558649f9dea6f6768a793e7e6b6e41bb3710167b9bc9485feb537770fc` |
| `raven/__init__.py` | `f368f8e50937e14e0263f83b9cfcf87f3cffcf6089f5e8819181ae675b460f9b` |
| `raven/memory_engine.py` | `ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0` |
| `raven/qwen_client.py` | `ea65cea97188928b0edac243928195e53aa3efdb2facc4f91d940fb17d805472` |
| `raven/sleep_consolidator.py` | `9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39` |
| `raven/spectral.py` | `36d5a1198a9f7a817ec8cd540f2f4c8c1c9a0c26e74782c2ef4d38fcf257ca90` |

The runner checks each copied-file hash before returning a result.

## Runtime environment

- Python multiprocessing `spawn`
- Separate process for each Raven service entry point
- Fresh temporary SQLite file per arm
- Deterministic local embedding stand-in; no model download or API key
- Frozen engine clock: `1800000000.125`
- Installed FastAPI, MCP, NumPy, SciPy, and Pydantic packages; no dependencies
  were added by this experiment

## Reproduction

From this directory:

```sh
python3 -m unittest -v test_exp63_raven_service_shared_database.py
python3 exp63_raven_service_shared_database.py
```

The test suite runs the assay once and checks the result against `result.json`.
