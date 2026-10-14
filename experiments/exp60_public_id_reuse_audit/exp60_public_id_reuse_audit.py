"""Static AST audit of caller-selected memory IDs in the pinned Raven snapshot."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "sources" / "raven-memory"
PINNED_COMMIT = "56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f"
EXPECTED_HASHES = {
    "api_server.py": "f83a88e1cb6a89b92319184ca4fecc13a5d1223a1ddf904bddabbc01e462a9b5",
    "mcp_server.py": "f89a21558649f9dea6f6768a793e7e6b6e41bb3710167b9bc9485feb537770fc",
    "raven/memory_engine.py": "ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0",
}


def _read(relative: str) -> str:
    return (SOURCE / relative).read_text(encoding="utf-8")


def _tree(relative: str) -> ast.Module:
    return ast.parse(_read(relative), filename=relative)


def _class(tree: ast.Module, name: str) -> ast.ClassDef:
    return next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    return next(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def _arg_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    a = node.args
    return [x.arg for x in (*a.posonlyargs, *a.args, *a.kwonlyargs)]


def _calls(node: ast.AST, attribute: str) -> list[ast.Call]:
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == attribute]


def _kwargs(call: ast.Call) -> list[str]:
    return [kw.arg for kw in call.keywords if kw.arg is not None]


def audit() -> dict:
    hashes = {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() for name in EXPECTED_HASHES}
    if hashes != EXPECTED_HASHES:
        raise RuntimeError(f"Pinned source hash mismatch: {hashes}")

    api_tree = _tree("api_server.py")
    mcp_tree = _tree("mcp_server.py")
    engine_tree = _tree("raven/memory_engine.py")
    request = _class(api_tree, "StoreRequest")
    request_fields = [n.target.id for n in request.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)]
    api_handler = _function(api_tree, "store_memory")
    api_store_calls = []
    for call in _calls(api_handler, "to_thread"):
        if call.args and isinstance(call.args[0], ast.Attribute) and call.args[0].attr == "store":
            api_store_calls.append(call)
    if len(api_store_calls) != 1:
        raise RuntimeError("Expected one asyncio.to_thread call forwarding to engine.store")
    api_forwarded = sorted({key for call in api_store_calls for key in _kwargs(call)})

    mcp_store = _function(mcp_tree, "raven_store")
    mcp_store_calls = _calls(mcp_store, "store")
    mcp_forwarded = sorted({key for call in mcp_store_calls for key in _kwargs(call)})

    engine_store = _function(engine_tree, "store")
    engine_params = _arg_names(engine_store)
    generated_assignments = [n for n in ast.walk(engine_store) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "memory_id" for t in n.targets)]
    if len(generated_assignments) != 1:
        raise RuntimeError("Expected exactly one generated memory_id assignment in engine.store")
    generated_id_line = generated_assignments[0].lineno

    low_level_calls = []
    for path in sorted(SOURCE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path.relative_to(SOURCE)))
        for call in _calls(tree, "store_memory"):
            owner = next((n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and call in ast.walk(n)), "<module>")
            low_level_calls.append({"file": str(path.relative_to(SOURCE)), "line": call.lineno, "owner": owner})

    storage = next(n for n in ast.walk(engine_tree) if isinstance(n, ast.FunctionDef) and n.name == "store_memory")
    storage_sql = " ".join(ast.get_source_segment(_read("raven/memory_engine.py"), n) or "" for n in ast.walk(storage) if isinstance(n, ast.Constant) and isinstance(n.value, str))

    if "memory_id" in request_fields or "memory_id" in api_forwarded:
        raise RuntimeError("HTTP ingestion exposes or forwards memory_id")
    if "memory_id" in _arg_names(mcp_store) or "memory_id" in mcp_forwarded:
        raise RuntimeError("MCP ingestion exposes or forwards memory_id")
    if "memory_id" in engine_params:
        raise RuntimeError("AdaptiveMemoryEngine.store accepts caller-selected memory_id")

    return {
        "experiment": "Exp60",
        "source_commit": PINNED_COMMIT,
        "source_file_sha256": hashes,
        "http_store_request_fields": request_fields,
        "http_store_forwarded_kwargs": api_forwarded,
        "mcp_store_parameters": _arg_names(mcp_store),
        "mcp_store_forwarded_kwargs": mcp_forwarded,
        "engine_store_parameters": engine_params,
        "generated_memory_id_assignment_line": generated_id_line,
        "low_level_store_memory_callsites": low_level_calls,
        "low_level_store_uses_insert_or_replace": "INSERT OR REPLACE" in storage_sql.upper(),
        "verdict": "Caller-selected memory_id is absent from the inspected HTTP and MCP ingestion signatures; both delegate to engine.store(), which generates the ID.",
        "inferred_scope": "The direct same-ID replacement tested in Exp59 is not shown reachable through these declared ingestion paths.",
        "unknowns": ["Automatic-ID collision possibility and operational likelihood", "Live server or MCP transport behavior", "Deployment wrappers, proxies, and uninspected ingestion paths"],
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
