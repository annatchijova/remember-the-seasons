"""Cross-service allocator assay using copied Raven API and MCP entry points."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "raven_snapshot"
FIXED_TIME = 1_800_000_000.125
SOURCE_FILES = (
    "api_server.py",
    "mcp_server.py",
    "raven/__init__.py",
    "raven/memory_engine.py",
    "raven/qwen_client.py",
    "raven/sleep_consolidator.py",
    "raven/spectral.py",
)
EXPECTED_SOURCE_HASHES = {
    "api_server.py": "f83a88e1cb6a89b92319184ca4fecc13a5d1223a1ddf904bddabbc01e462a9b5",
    "mcp_server.py": "f89a21558649f9dea6f6768a793e7e6b6e41bb3710167b9bc9485feb537770fc",
    "raven/__init__.py": "f368f8e50937e14e0263f83b9cfcf87f3cffcf6089f5e8819181ae675b460f9b",
    "raven/memory_engine.py": "ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0",
    "raven/qwen_client.py": "ea65cea97188928b0edac243928195e53aa3efdb2facc4f91d940fb17d805472",
    "raven/sleep_consolidator.py": "9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39",
    "raven/spectral.py": "36d5a1198a9f7a817ec8cd540f2f4c8c1c9a0c26e74782c2ef4d38fcf257ca90",
}


class DeterministicSentenceTransformer:
    """Local embedding stand-in: the harness controls vectors, not Raven."""

    def __init__(self, _name: str):
        pass

    @staticmethod
    def encode(texts, normalize_embeddings=True, show_progress_bar=False):
        del normalize_embeddings, show_progress_bar
        import numpy as np

        rows = []
        service_index = 0 if os.environ.get("EXP63_SERVICE") == "api" else 1
        for text in texts:
            vector = np.zeros(384, dtype=np.float32)
            vector[service_index] = 1.0
            rows.append(vector)
        return np.asarray(rows, dtype=np.float32)


def _install_embedding_stub() -> None:
    module = ModuleType("sentence_transformers")
    module.SentenceTransformer = DeterministicSentenceTransformer
    sys.modules["sentence_transformers"] = module


def _prepare_imports(db_path: str, service: str):
    os.environ["RAVEN_DB_PATH"] = db_path
    os.environ["EXP63_SERVICE"] = service
    os.environ["RAVEN_USE_LOCAL_EMBEDDINGS"] = "1"
    os.environ["RAVEN_API_TOKEN"] = ""
    sys.path.insert(0, str(SNAPSHOT))
    _install_embedding_stub()

    import raven.memory_engine as memory_engine

    if service == "api":
        import api_server

        return memory_engine, api_server
    if service == "mcp":
        import mcp_server

        return memory_engine, mcp_server
    raise ValueError(f"unknown service: {service}")


def _engine_counter(memory_engine) -> int:
    return memory_engine.AdaptiveMemoryEngine(
        embedding_dim=384, db_path=Path(os.environ["RAVEN_DB_PATH"])
    )._next_cell_id


def _service_worker(
    service: str,
    db_path: str,
    content: str,
    release,
    ready,
    results,
) -> None:
    try:
        memory_engine, module = _prepare_imports(db_path, service)

        if service == "api":
            async def api_session():
                async with module.lifespan(module.app):
                    ready.put({"service": service, "next_cell_id": module.engine._next_cell_id, "error": None})
                    if not release.wait(30):
                        raise TimeoutError("API release event timed out")
                    async def inline_to_thread(function, *args, **kwargs):
                        return function(*args, **kwargs)

                    # Exp63's recorded assay uses the inline accommodation.
                    # A later diagnostic found quiet-loop to_thread stalls
                    # even without Raven; timer-driven probes let the handler
                    # complete, but do not change this historical run.
                    module.asyncio.to_thread = inline_to_thread
                    clock = SimpleNamespace(time=lambda: FIXED_TIME)
                    with patch.object(memory_engine, "time", clock):
                        response = await module.store_memory(
                            module.StoreRequest(content=content)
                        )
                    results.put({"service": service, **response, "error": None})

            import asyncio

            asyncio.run(api_session())
            return

        # Importing the MCP module constructs its engine before readiness.
        ready.put({"service": service, "next_cell_id": module._engine._next_cell_id, "error": None})
        if not release.wait(30):
            raise TimeoutError("MCP release event timed out")
        clock = SimpleNamespace(time=lambda: FIXED_TIME)
        with patch.object(memory_engine, "time", clock):
            response = module.raven_store(content=content)
        results.put({"service": service, **response, "error": None})
    except BaseException as exc:
        message = f"{type(exc).__name__}: {exc}"
        ready.put({"service": service, "next_cell_id": None, "error": message})
        results.put({"service": service, "error": message})


def _init_db(path: Path) -> None:
    os.environ["RAVEN_DB_PATH"] = str(path)
    sys.path.insert(0, str(SNAPSHOT))
    from raven.memory_engine import AdaptiveMemoryEngine

    AdaptiveMemoryEngine(embedding_dim=384, db_path=path)


def _start(ctx, path: Path, jobs: list[tuple[str, str]], releases):
    ready = ctx.Queue()
    results = ctx.Queue()
    processes = [
        ctx.Process(
            target=_service_worker,
            args=(service, str(path), content, releases[i], ready, results),
        )
        for i, (service, content) in enumerate(jobs)
    ]
    for process in processes:
        process.start()
    ready_messages = [ready.get(timeout=40) for _ in processes]
    if any(message["error"] for message in ready_messages):
        raise RuntimeError(f"service initialization failed: {ready_messages}")
    return processes, ready, results, ready_messages


def _collect(processes, results, count: int) -> list[dict]:
    messages = [results.get(timeout=40) for _ in range(count)]
    for process in processes:
        process.join(timeout=40)
        if process.is_alive():
            process.terminate()
            process.join()
            raise TimeoutError("service worker did not exit")
        if process.exitcode != 0:
            raise RuntimeError(f"service worker exited with {process.exitcode}")
    if any(message.get("error") for message in messages):
        raise RuntimeError(f"service store failed: {messages}")
    return messages


def _rows(path: Path) -> list[dict]:
    with sqlite3.connect(path) as conn:
        return [
            {"memory_id": row[0], "cell_id": row[1], "content": row[2], "embedding_hex": row[3].hex()}
            for row in conn.execute(
                "SELECT memory_id, cell_id, content, embedding FROM memories ORDER BY cell_id"
            )
        ]


def _start_ready(ctx, path: Path, jobs, releases):
    processes, ready_queue, results_queue, ready = _start(ctx, path, jobs, releases)
    return processes, ready_queue, results_queue, ready


def run() -> dict:
    ctx = multiprocessing.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="exp63-") as tmp:
        root = Path(tmp)

        concurrent_path = root / "concurrent.sqlite"
        _init_db(concurrent_path)
        concurrent_gate = ctx.Event()
        processes, ready_q, result_q, ready = _start_ready(
            ctx,
            concurrent_path,
            [("api", "service alpha"), ("mcp", "service beta")],
            [concurrent_gate, concurrent_gate],
        )
        concurrent_gate.set()
        returned = _collect(processes, result_q, 2)
        concurrent_rows = _rows(concurrent_path)
        concurrent = {
            "ready": sorted(
                [[item["service"], item["next_cell_id"]] for item in ready]
            ),
            "returned": sorted(
                [[item["service"], item["memory_id"], item["cell_id"]] for item in returned]
            ),
            "row_count": len(concurrent_rows),
            "surviving_row_is_a_contender": (
                len(concurrent_rows) == 1
                and concurrent_rows[0]["memory_id"] in {item["memory_id"] for item in returned}
            ),
        }
        ready_q.close()
        result_q.close()

        exact_path = root / "exact-id.sqlite"
        _init_db(exact_path)
        gate_api, gate_mcp = ctx.Event(), ctx.Event()
        processes, ready_q, result_q, ready = _start_ready(
            ctx,
            exact_path,
            [("api", "same payload alpha"), ("mcp", "same payload alpha")],
            [gate_api, gate_mcp],
        )
        gate_api.set()
        first = result_q.get(timeout=40)
        if first.get("error"):
            raise RuntimeError(f"API store failed: {first}")
        with sqlite3.connect(exact_path) as conn:
            conn.execute(
                "INSERT INTO audit_log (timestamp, operation, memories_retrieved) "
                "VALUES (?, 'recall', ?)",
                (FIXED_TIME, json.dumps([{"memory_id": first["memory_id"]}])),
            )
            conn.commit()
        from raven_snapshot.raven import sleep_consolidator

        count_before = sleep_consolidator.get_recall_counts(
            exact_path, [first["memory_id"]]
        )[first["memory_id"]]
        gate_mcp.set()
        second = result_q.get(timeout=40)
        if second.get("error"):
            raise RuntimeError(f"MCP store failed: {second}")
        for process in processes:
            process.join(timeout=40)
            if process.is_alive():
                process.terminate()
                process.join()
                raise TimeoutError("service worker did not exit")
            if process.exitcode != 0:
                raise RuntimeError(f"service worker exited with {process.exitcode}")
        count_after = sleep_consolidator.get_recall_counts(
            exact_path, [second["memory_id"]]
        )[second["memory_id"]]
        expected_mcp_embedding = bytes([0] * 4 + [0, 0, 128, 63] + [0] * (384 * 4 - 8)).hex()
        exact_rows = _rows(exact_path)
        exact = {
            "ready": sorted(
                [[item["service"], item["next_cell_id"]] for item in ready]
            ),
            "returned": [
                [first["service"], first["memory_id"], first["cell_id"]],
                [second["service"], second["memory_id"], second["cell_id"]],
            ],
            "same_memory_id": first["memory_id"] == second["memory_id"],
            "audit_count_before_replacement": count_before,
            "audit_count_after_replacement": count_after,
            "replacement_matches_second_store": (
                len(exact_rows) == 1
                and exact_rows[0]["embedding_hex"] == expected_mcp_embedding
            ),
            "rows": exact_rows,
        }
        ready_q.close()
        result_q.close()

        reload_path = root / "reload.sqlite"
        _init_db(reload_path)
        first_gate = ctx.Event()
        first_gate.set()
        processes, ready_a_q, result_a_q, ready_a = _start_ready(
            ctx, reload_path, [("api", "reload alpha")], [first_gate]
        )
        first_reload = _collect(processes, result_a_q, 1)[0]
        ready_a_q.close()
        result_a_q.close()

        second_gate = ctx.Event()
        second_gate.set()
        processes, ready_b_q, result_b_q, ready_b = _start_ready(
            ctx, reload_path, [("mcp", "reload beta")], [second_gate]
        )
        second_reload = _collect(processes, result_b_q, 1)[0]
        reload_control = {
            "ready": [ready_a[0]["next_cell_id"], ready_b[0]["next_cell_id"]],
            "returned": [
                [first_reload["service"], first_reload["memory_id"], first_reload["cell_id"]],
                [second_reload["service"], second_reload["memory_id"], second_reload["cell_id"]],
            ],
            "rows": _rows(reload_path),
        }
        ready_b_q.close()
        result_b_q.close()

    hashes = {
        name: hashlib.sha256((SNAPSHOT / name).read_bytes()).hexdigest()
        for name in SOURCE_FILES
    }
    if hashes != EXPECTED_SOURCE_HASHES:
        raise RuntimeError(f"source-copy hashes differ from pinned snapshot: {hashes}")
    return {
        "experiment": "Exp63",
        "source_commit": "56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f",
        "source_sha256": hashes,
        "fixed_time": FIXED_TIME,
        "scope": (
            "Copied Raven API route handler and MCP store tool in separate spawned processes; "
            "shared temporary SQLite only. HTTP and MCP wire protocols are bypassed."
        ),
        "concurrent_different_content": concurrent,
        "sequential_same_id": exact,
        "cross_service_reload_control": reload_control,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
