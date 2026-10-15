"""Runtime assay for independent Raven engines sharing one SQLite database."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from raven_snapshot import memory_engine

sys.modules.setdefault("raven", sys.modules["raven_snapshot"])
sys.modules.setdefault("raven.memory_engine", memory_engine)
from raven_snapshot import sleep_consolidator


PINNED_ENGINE_SHA256 = "ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0"
FIXED_TIME = 1_800_000_000.125


def _engine(path: Path):
    return memory_engine.AdaptiveMemoryEngine(embedding_dim=4, db_path=path)


def _store(engine, content: str, values: list[float]):
    return engine.store(content, memory_engine.np.asarray(values, dtype=memory_engine.np.float32))


def _rows(path: Path) -> list[dict]:
    with sqlite3.connect(path) as conn:
        return [
            {"memory_id": row[0], "cell_id": row[1], "content": row[2], "embedding_hex": row[3].hex()}
            for row in conn.execute(
                "SELECT memory_id, cell_id, content, embedding FROM memories ORDER BY cell_id"
            )
        ]


def _audit_count_for(path: Path, memory_id: str) -> int:
    return sleep_consolidator.get_recall_counts(path, [memory_id])[memory_id]


def run() -> dict:
    with tempfile.TemporaryDirectory(prefix="exp61-") as tmp:
        root = Path(tmp)
        fixed_clock = SimpleNamespace(time=lambda: FIXED_TIME)

        # Negative control: one instance advances its own allocator.
        one_path = root / "single.sqlite"
        one = _engine(one_path)
        with patch.object(memory_engine, "time", fixed_clock):
            one_a = _store(one, "control alpha", [1, 0, 0, 0])
            one_b = _store(one, "control beta", [0, 1, 0, 0])
        single = {"returned": [[one_a.memory_id, one_a.cell_id], [one_b.memory_id, one_b.cell_id]], "rows": _rows(one_path)}

        # Two instances initialized against the same empty DB retain stale
        # independent allocators. Distinct IDs still collide on UNIQUE cell_id.
        stale_path = root / "stale-different-content.sqlite"
        stale_a_engine = _engine(stale_path)
        stale_b_engine = _engine(stale_path)
        with patch.object(memory_engine, "time", fixed_clock):
            stale_a = _store(stale_a_engine, "stale alpha", [1, 0, 0, 0])
            stale_b = _store(stale_b_engine, "stale beta", [0, 1, 0, 0])
        stale_different = {
            "returned": [[stale_a.memory_id, stale_a.cell_id], [stale_b.memory_id, stale_b.cell_id]],
            "rows": _rows(stale_path),
        }

        # Exact generated-ID collision. Insert one recall history row after
        # the first store, then replace the row through the second stale engine.
        exact_path = root / "stale-same-content.sqlite"
        exact_a_engine = _engine(exact_path)
        exact_b_engine = _engine(exact_path)
        with patch.object(memory_engine, "time", fixed_clock):
            exact_a = _store(exact_a_engine, "same payload", [1, 0, 0, 0])
            with sqlite3.connect(exact_path) as conn:
                conn.execute(
                    "INSERT INTO audit_log (timestamp, operation, memories_retrieved) VALUES (?, 'recall', ?)",
                    (FIXED_TIME, json.dumps([{"memory_id": exact_a.memory_id}])),
                )
                conn.commit()
            before_count = _audit_count_for(exact_path, exact_a.memory_id)
            exact_b = _store(exact_b_engine, "same payload", [0, 1, 0, 0])
        exact = {
            "returned": [[exact_a.memory_id, exact_a.cell_id], [exact_b.memory_id, exact_b.cell_id]],
            "same_memory_id": exact_a.memory_id == exact_b.memory_id,
            "audit_count_before_replacement": before_count,
            "audit_count_after_replacement": _audit_count_for(exact_path, exact_b.memory_id),
            "rows": _rows(exact_path),
        }

        # Reload control: the second engine observes the first committed cell.
        reload_path = root / "reload.sqlite"
        reload_a_engine = _engine(reload_path)
        with patch.object(memory_engine, "time", fixed_clock):
            reload_a = _store(reload_a_engine, "reload alpha", [1, 0, 0, 0])
            reload_b_engine = _engine(reload_path)
            reload_b = _store(reload_b_engine, "reload beta", [0, 1, 0, 0])
        reloaded = {"returned": [[reload_a.memory_id, reload_a.cell_id], [reload_b.memory_id, reload_b.cell_id]], "rows": _rows(reload_path)}

        copied = Path(__file__).with_name("raven_snapshot")
        source_hash = hashlib.sha256((copied / "memory_engine.py").read_bytes()).hexdigest()
        spectral_hash = hashlib.sha256((copied / "spectral.py").read_bytes()).hexdigest()
        consolidator_hash = hashlib.sha256((copied / "sleep_consolidator.py").read_bytes()).hexdigest()
        if source_hash != PINNED_ENGINE_SHA256:
            raise RuntimeError(f"Copied engine hash differs from pinned source: {source_hash}")
        if spectral_hash != "36d5a1198a9f7a817ec8cd540f2f4c8c1c9a0c26e74782c2ef4d38fcf257ca90":
            raise RuntimeError(f"Copied spectral hash differs from pinned source: {spectral_hash}")
        if consolidator_hash != "9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39":
            raise RuntimeError(f"Copied consolidator hash differs from pinned source: {consolidator_hash}")

        return {
            "experiment": "Exp61",
            "source_commit": "56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f",
            "copied_engine_sha256": source_hash,
            "copied_spectral_sha256": spectral_hash,
            "copied_consolidator_sha256": consolidator_hash,
            "fixed_time": FIXED_TIME,
            "single_engine_control": single,
            "stale_allocators_different_content": stale_different,
            "stale_allocators_same_content": exact,
            "reloaded_second_engine_control": reloaded,
            "audit_count_note": "The audit row uses Raven's memories_retrieved JSON shape and is counted by memory_id, matching the ID aggregation at sources/raven-memory/raven/sleep_consolidator.py:79-96.",
            "scope": "Same-process independent engine instances using separate instance locks and a shared temporary SQLite file; no service transport or cross-process run.",
        }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
