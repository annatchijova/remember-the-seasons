"""Cross-process runtime assay for independent Raven engines sharing SQLite."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from raven_snapshot import memory_engine

sys.modules.setdefault("raven", sys.modules["raven_snapshot"])
sys.modules.setdefault("raven.memory_engine", memory_engine)
from raven_snapshot import sleep_consolidator


FIXED_TIME = 1_800_000_000.125
SOURCE_HASHES = {
    "memory_engine.py": "ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0",
    "spectral.py": "36d5a1198a9f7a817ec8cd540f2f4c8c1c9a0c26e74782c2ef4d38fcf257ca90",
    "sleep_consolidator.py": "9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39",
}


def _engine(path: str):
    return memory_engine.AdaptiveMemoryEngine(embedding_dim=4, db_path=Path(path))


def _worker(path: str, content: str, vector: list[float], release, ready, results):
    """Construct before signaling readiness, then store only after release."""
    try:
        engine = _engine(path)
        ready.put({"next_cell_id": engine._next_cell_id, "error": None})
        if not release.wait(20):
            raise TimeoutError("worker release event timed out")
        fixed_clock = SimpleNamespace(time=lambda: FIXED_TIME)
        with patch.object(memory_engine, "time", fixed_clock):
            entry = engine.store(content, memory_engine.np.asarray(vector, dtype=memory_engine.np.float32))
        results.put({"memory_id": entry.memory_id, "cell_id": entry.cell_id, "error": None})
    except BaseException as exc:
        ready.put({"next_cell_id": None, "error": f"{type(exc).__name__}: {exc}"})
        results.put({"memory_id": None, "cell_id": None, "error": f"{type(exc).__name__}: {exc}"})


def _single_worker(path: str, content: str, vector: list[float], ready, results):
    release = type("Released", (), {"wait": staticmethod(lambda _timeout: True)})()
    _worker(path, content, vector, release, ready, results)


def _initialize_db(path: Path):
    engine = memory_engine.AdaptiveMemoryEngine(embedding_dim=4, db_path=path)
    del engine


def _start_workers(ctx, path: Path, inputs: list[tuple[str, list[float]]], releases):
    ready = ctx.Queue()
    results = ctx.Queue()
    processes = [
        ctx.Process(target=_worker, args=(str(path), content, vector, releases[i], ready, results))
        for i, (content, vector) in enumerate(inputs)
    ]
    for process in processes:
        process.start()
    ready_messages = [ready.get(timeout=30) for _ in processes]
    if any(item["error"] for item in ready_messages):
        raise RuntimeError(f"worker initialization failed: {ready_messages}")
    return processes, ready, results, ready_messages


def _collect(processes, results, count: int) -> list[dict]:
    messages = [results.get(timeout=30) for _ in range(count)]
    for process in processes:
        process.join(timeout=30)
        if process.is_alive():
            process.terminate()
            process.join()
            raise TimeoutError("Raven worker did not exit")
        if process.exitcode != 0:
            raise RuntimeError(f"Raven worker exit code {process.exitcode}")
    if any(item["error"] for item in messages):
        raise RuntimeError(f"worker store failed: {messages}")
    return messages


def _rows(path: Path) -> list[dict]:
    with sqlite3.connect(path) as conn:
        return [
            {"memory_id": row[0], "cell_id": row[1], "content": row[2], "embedding_hex": row[3].hex()}
            for row in conn.execute("SELECT memory_id, cell_id, content, embedding FROM memories ORDER BY cell_id")
        ]


def run() -> dict:
    ctx = multiprocessing.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="exp62-") as tmp:
        root = Path(tmp)

        # Simultaneous writes after both processes have loaded the empty DB.
        concurrent_path = root / "concurrent.sqlite"
        _initialize_db(concurrent_path)
        gate = ctx.Event()
        processes, ready_q, results_q, ready = _start_workers(
            ctx,
            concurrent_path,
            [("process alpha", [1, 0, 0, 0]), ("process beta", [0, 1, 0, 0])],
            [gate, gate],
        )
        gate.set()
        concurrent_returns = _collect(processes, results_q, 2)
        concurrent_rows = _rows(concurrent_path)
        concurrent = {
            "ready_counters": sorted(item["next_cell_id"] for item in ready),
            "returned": sorted([[x["memory_id"], x["cell_id"]] for x in concurrent_returns]),
            "row_count": len(concurrent_rows),
            "surviving_row_is_a_contender": len(concurrent_rows) == 1 and concurrent_rows[0]["memory_id"] in {x["memory_id"] for x in concurrent_returns},
        }
        ready_q.close()
        results_q.close()

        # Both same-content processes are initialized first; order stores so a
        # historical audit reference exists before the second replacement.
        exact_path = root / "exact-id.sqlite"
        _initialize_db(exact_path)
        release_a, release_b = ctx.Event(), ctx.Event()
        processes, ready_q, results_q, ready = _start_workers(
            ctx, exact_path, [("same payload", [1, 0, 0, 0]), ("same payload", [0, 1, 0, 0])], [release_a, release_b]
        )
        release_a.set()
        first = results_q.get(timeout=30)
        if first["error"]:
            raise RuntimeError(f"first worker store failed: {first}")
        with sqlite3.connect(exact_path) as conn:
            conn.execute(
                "INSERT INTO audit_log (timestamp, operation, memories_retrieved) VALUES (?, 'recall', ?)",
                (FIXED_TIME, json.dumps([{"memory_id": first["memory_id"]}])),
            )
            conn.commit()
        count_before = sleep_consolidator.get_recall_counts(exact_path, [first["memory_id"]])[first["memory_id"]]
        release_b.set()
        second = results_q.get(timeout=30)
        if second["error"]:
            raise RuntimeError(f"second worker store failed: {second}")
        for process in processes:
            process.join(timeout=30)
            if process.is_alive():
                process.terminate()
                process.join()
                raise TimeoutError("Raven worker did not exit")
            if process.exitcode != 0:
                raise RuntimeError(f"Raven worker exit code {process.exitcode}")
        count_after = sleep_consolidator.get_recall_counts(exact_path, [second["memory_id"]])[second["memory_id"]]
        exact_rows = _rows(exact_path)
        exact = {
            "ready_counters": sorted(item["next_cell_id"] for item in ready),
            "returned": [[first["memory_id"], first["cell_id"]], [second["memory_id"], second["cell_id"]]],
            "same_memory_id": first["memory_id"] == second["memory_id"],
            "audit_count_before_replacement": count_before,
            "audit_count_after_replacement": count_after,
            "rows": exact_rows,
        }
        ready_q.close()
        results_q.close()

        # Negative control: process B is initialized only after A has written.
        reload_path = root / "reload.sqlite"
        _initialize_db(reload_path)
        first_release = ctx.Event()
        first_release.set()
        p_a, ready_a, result_a, ready_a_messages = _start_workers(
            ctx, reload_path, [("reload alpha", [1, 0, 0, 0])], [first_release]
        )
        first_reload = _collect(p_a, result_a, 1)[0]
        ready_a.close()
        result_a.close()
        second_release = ctx.Event()
        second_release.set()
        p_b, ready_b, result_b, ready_b_messages = _start_workers(
            ctx, reload_path, [("reload beta", [0, 1, 0, 0])], [second_release]
        )
        second_reload = _collect(p_b, result_b, 1)[0]
        ready_b.close()
        result_b.close()
        reload_control = {
            "ready_counters": [ready_a_messages[0]["next_cell_id"], ready_b_messages[0]["next_cell_id"]],
            "returned": [[first_reload["memory_id"], first_reload["cell_id"]], [second_reload["memory_id"], second_reload["cell_id"]]],
            "rows": _rows(reload_path),
        }

        copied = Path(__file__).with_name("raven_snapshot")
        observed_hashes = {name: hashlib.sha256((copied / name).read_bytes()).hexdigest() for name in SOURCE_HASHES}
        if observed_hashes != SOURCE_HASHES:
            raise RuntimeError(f"Source-copy hash mismatch: {observed_hashes}")

        return {
            "experiment": "Exp62",
            "source_commit": "56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f",
            "copied_source_sha256": observed_hashes,
            "fixed_time": FIXED_TIME,
            "simultaneous_different_content_processes": concurrent,
            "sequential_same_id_processes": exact,
            "reload_control": reload_control,
            "scope": "Independent spawned Python processes, copied Raven engine and consolidator, temporary shared SQLite; no API/MCP transport or production deployment.",
        }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
