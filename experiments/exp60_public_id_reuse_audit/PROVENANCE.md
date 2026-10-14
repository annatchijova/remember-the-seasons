# Exp60 provenance

## Source material

- Raven snapshot: `sources/raven-memory/`
- Pinned upstream commit: `56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f`
- `api_server.py` SHA-256: `f83a88e1cb6a89b92319184ca4fecc13a5d1223a1ddf904bddabbc01e462a9b5`
- `mcp_server.py` SHA-256: `f89a21558649f9dea6f6768a793e7e6b6e41bb3710167b9bc9485feb537770fc`
- `raven/memory_engine.py` SHA-256: `ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0`

The snapshot is read-only. The assay parses it with Python's standard-library
AST module; it does not import or execute Raven.

## Procedure

The preregistration was written before implementing and running the AST checks.
The run artifact is `result.json`. Re-run from this directory with:

```sh
python3 -m unittest -v test_exp60_public_id_reuse_audit.py
python3 exp60_public_id_reuse_audit.py
```

The five tests verify the inspected request fields, forwarding chain, ID
generation location, unique low-level storage callsite, pinned source hashes,
and deterministic replay.
