"""Exp55: test whether Raven's stored recall counter acts through consolidation."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ["RAVEN_ANN_BACKEND"] = "kdtree"
EXP53_DIR = Path(__file__).resolve().parents[1] / "exp53_raven_latent_trace"
EXP51_DIR = Path(__file__).resolve().parents[1] / "exp51_raven_h14_longitudinal"
sys.path.insert(0, str(EXP53_DIR))

from exp53_raven_latent_trace import (  # noqa: E402
    NOW,
    _clone_database,
    _load_seed_engine,
    _ranked_ids,
    _score_rows,
    _set_recall_count,
    build_seed_engine,
    sleep_consolidator,
)
from exp51_raven_h14_longitudinal import _vectors  # noqa: E402

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent
SOURCE_COMMIT = "56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f"
SOURCE_HASHES = {
    "memory_engine.py": "ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0",
    "sleep_consolidator.py": "9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39",
}
THRESHOLD = 0.90
TOP_K = 4
HOPS = 0
QUERY_KEYS = ("C", "D")


def _create_fixture(path: Path) -> None:
    seed = path.with_name(f"{path.stem}.seed.sqlite")
    engine, _ = build_seed_engine(seed)
    del engine
    _clone_database(seed, path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE memories SET layer='episodic',state='NEUTRAL' "
            "WHERE memory_id IN ('C','D')"
        )
        conn.execute(
            "UPDATE memories SET recall_count=4 WHERE memory_id IN ('C','D')"
        )
        conn.commit()


def _set_treatment(path: Path, c_count: int) -> None:
    _set_recall_count(path, "C", c_count)
    _set_recall_count(path, "D", 4)


def _logical_snapshot(path: Path) -> dict:
    """Return all logical table contents, independent of SQLite row order."""
    def encode(value):
        if isinstance(value, bytes):
            return {"blob_hex": value.hex()}
        return value

    with sqlite3.connect(path) as conn:
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        snapshot = {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            columns = [row[1] for row in conn.execute(f"PRAGMA table_info({quoted})")]
            rows = conn.execute(f"SELECT * FROM {quoted}").fetchall()
            values = [[encode(value) for value in row] for row in rows]
            values.sort(key=lambda row: json.dumps(
                row, sort_keys=True, separators=(",", ":"), allow_nan=False
            ))
            snapshot[table] = {"columns": columns, "rows": values}
    return snapshot


def _snapshot_without_counter(path: Path) -> dict:
    snapshot = _logical_snapshot(path)
    memory_table = snapshot["memories"]
    count_index = memory_table["columns"].index("recall_count")
    memory_table["columns"] = [
        column for column in memory_table["columns"] if column != "recall_count"
    ]
    memory_table["rows"] = [
        row[:count_index] + row[count_index + 1:] for row in memory_table["rows"]
    ]
    return snapshot


def _digest_json(value: dict) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"),
                           allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _audit_counts(path: Path, memory_ids: list[str]) -> dict[str, int]:
    return sleep_consolidator.get_recall_counts(path, memory_ids)


def _groups(path: Path) -> list[list[str]]:
    memories = sleep_consolidator.load_episodic_neutral(path)
    grouped = sleep_consolidator.cluster_by_similarity(memories, THRESHOLD)
    return [sorted(memory["memory_id"] for memory in group) for group in grouped]


def _query_trace(path: Path) -> dict:
    engine = _load_seed_engine(path)
    engine._ensure_kdtree()
    trace = {}
    for key in QUERY_KEYS:
        outcome = engine._recall_core(
            _vectors()[key], now=NOW, top_k=TOP_K, hops=HOPS,
            current_turn_memories=None,
        )
        trace[key] = {
            "ranked_ids": _ranked_ids(outcome),
            "scores": _score_rows(outcome),
        }
    return trace


def _run_consolidation(path: Path) -> dict:
    counts = _audit_counts(path, ["C", "D"])
    with patch.object(sleep_consolidator.time, "time", return_value=NOW):
        result = sleep_consolidator.run_consolidation(
            path, threshold=THRESHOLD, dry_run=False, rebuild_spectral=False,
        )

    engine = _load_seed_engine(path)
    consolidated = [
        memory for memory in engine.list_memories()
        if memory.memory_id.startswith("cons_")
    ]
    if len(consolidated) != 1:
        raise AssertionError(f"Expected one consolidated node, found {len(consolidated)}")
    node = consolidated[0]
    metadata = node.metadata
    sources = sorted(metadata.get("consolidated_from", []))
    if sources != ["C", "D"]:
        raise AssertionError(f"Unexpected consolidation sources: {sources}")
    embedding = np.asarray(node.embedding, dtype=np.float32)
    return {
        "run_result": result,
        "audit_weight_counts": counts,
        "node_id": node.memory_id,
        "sources": sources,
        "metadata": metadata,
        "embedding_hex": embedding.tobytes().hex(),
        "embedding": embedding.tolist(),
        "retrieval": _query_trace(path),
        "logical_database": _logical_snapshot(path),
    }


def _build_primary_pair(root: Path) -> tuple[Path, Path, Path]:
    seed = root / "primary_seed.sqlite"
    _create_fixture(seed)
    s5, s4, equalized = (
        root / "primary_s5.sqlite",
        root / "primary_s4.sqlite",
        root / "primary_equalized.sqlite",
    )
    for path in (s5, s4, equalized):
        _clone_database(seed, path)
    _set_treatment(s5, 5)
    _set_treatment(s4, 4)
    _set_treatment(equalized, 4)
    return s5, s4, equalized


def _make_primary(root: Path) -> dict:
    s5, s4, equalized = _build_primary_pair(root)
    if _snapshot_without_counter(s5) != _snapshot_without_counter(s4):
        raise AssertionError("Primary branches differ outside C.recall_count")
    if _audit_counts(s5, ["C", "D"]) != {"C": 0, "D": 0}:
        raise AssertionError("S5 must start with an empty recall audit history")
    if _audit_counts(s4, ["C", "D"]) != {"C": 0, "D": 0}:
        raise AssertionError("S4 must start with an empty recall audit history")
    groups = _groups(s5)
    if groups != [["C", "D"]]:
        raise AssertionError(f"Fixture gate expected exactly group C/D; got {groups}")
    cosine = float(np.dot(_vectors()["C"], _vectors()["D"]))
    if cosine <= THRESHOLD:
        raise AssertionError(f"Fixture cosine {cosine} does not exceed {THRESHOLD}")

    pre5, pre4 = _query_trace(s5), _query_trace(s4)
    if pre5 != pre4:
        raise AssertionError("Counter-only branches differ before consolidation")

    result5 = _run_consolidation(s5)
    result4 = _run_consolidation(s4)
    result_equalized = _run_consolidation(equalized)
    normalized_db_equal = result5["logical_database"] == result4["logical_database"]
    retrieval_equal = result5["retrieval"] == result4["retrieval"]
    return {
        "common_pre_treatment_state_sha256": _digest_json(_snapshot_without_counter(s5)),
        "counter_values": {"S5": {"C": 5, "D": 4}, "S4": {"C": 4, "D": 4}},
        "fixture_cosine_C_D": cosine,
        "fixture_groups": groups,
        "non_counter_state_equal_before": True,
        "pre_consolidation_retrieval_equal": pre5 == pre4,
        "S5": result5,
        "S4": result4,
        "equalized_control": result_equalized,
        "merged_embedding_equal": result5["embedding_hex"] == result4["embedding_hex"],
        "logical_database_equal_after": normalized_db_equal,
        "retrieval_equal_after": retrieval_equal,
        "equalized_matches_S4": (
            result_equalized["logical_database"] == result4["logical_database"]
            and result_equalized["retrieval"] == result4["retrieval"]
        ),
    }


def _generate_recall_history(path: Path, c_recalls: int, d_recalls: int) -> None:
    engine = _load_seed_engine(path)
    with patch.object(sleep_consolidator.time, "time", return_value=NOW):
        for memory_id, key, count in (("C", "C", c_recalls), ("D", "D", d_recalls)):
            for _ in range(count):
                results, _audit = engine.recall(
                    query_embedding=_vectors()[key],
                    query_text=f"Exp55 audit canary {memory_id}",
                    top_k=1, hops=0, layer_filter="episodic",
                    current_turn_memories=None,
                )
                result_ids = [result.memory.memory_id for result in results]
                if result_ids != [memory_id]:
                    raise AssertionError(
                        f"Canary query {key} returned {result_ids}, expected {[memory_id]}"
                    )

    actual = _audit_counts(path, ["C", "D"])
    expected = {"C": c_recalls, "D": d_recalls}
    if actual != expected:
        raise AssertionError(f"Audit canary counts {actual} do not match {expected}")
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE memories SET recall_count=4 WHERE memory_id IN ('C','D')")
        conn.commit()
    with sqlite3.connect(path) as conn:
        persisted = dict(conn.execute(
            "SELECT memory_id,recall_count FROM memories WHERE memory_id IN ('C','D')"
        ).fetchall())
    if persisted != {"C": 4, "D": 4}:
        raise AssertionError(f"Canary persisted counters were not equalized: {persisted}")


def _make_canary(root: Path) -> dict:
    seed = root / "canary_seed.sqlite"
    _create_fixture(seed)
    a54, a44 = root / "canary_a54.sqlite", root / "canary_a44.sqlite"
    _clone_database(seed, a54)
    _clone_database(seed, a44)
    _generate_recall_history(a54, 5, 4)
    _generate_recall_history(a44, 4, 4)
    if _snapshot_without_counter(a54) == _snapshot_without_counter(a44):
        raise AssertionError("Canary fixture failed to preserve different audit histories")
    if _groups(a54) != [["C", "D"]] or _groups(a44) != [["C", "D"]]:
        raise AssertionError("Canary fixture changed the predeclared merge group")

    result54 = _run_consolidation(a54)
    result44 = _run_consolidation(a44)
    node54 = np.asarray(result54["embedding"], dtype=np.float64)
    node44 = np.asarray(result44["embedding"], dtype=np.float64)
    query_c = _vectors()["C"]
    query_d = _vectors()["D"]
    scores54 = {
        key: next(row["base_score"] for row in result54["retrieval"][key]["scores"]
                  if row["memory_id"] == result54["node_id"])
        for key in QUERY_KEYS
    }
    scores44 = {
        key: next(row["base_score"] for row in result44["retrieval"][key]["scores"]
                  if row["memory_id"] == result44["node_id"])
        for key in QUERY_KEYS
    }
    return {
        "audit_counts_A54": result54["audit_weight_counts"],
        "audit_counts_A44": result44["audit_weight_counts"],
        "persisted_counts_equal_before_consolidation": True,
        "A54": result54,
        "A44": result44,
        "merged_embedding_different": result54["embedding_hex"] != result44["embedding_hex"],
        "cosine_C_A54_greater": float(np.dot(query_c, node54)) > float(np.dot(query_c, node44)),
        "cosine_D_A54_lower": float(np.dot(query_d, node54)) < float(np.dot(query_d, node44)),
        "base_score_C_A54_greater": scores54["C"] > scores44["C"],
        "base_score_D_A54_lower": scores54["D"] < scores44["D"],
        "base_scores": {"A54": scores54, "A44": scores44},
    }


def _source_hashes() -> dict:
    vendor = EXP51_DIR / "vendor" / "raven"
    result = {
        name: hashlib.sha256((vendor / name).read_bytes()).hexdigest()
        for name in SOURCE_HASHES
    }
    if result != SOURCE_HASHES:
        raise AssertionError(f"Exp51 Raven copy hash mismatch: {result}")
    return result


def run_experiment() -> dict:
    hashes = _source_hashes()
    with tempfile.TemporaryDirectory(prefix="exp55-raven-") as temp:
        root = Path(temp)
        primary = _make_primary(root)
        canary = _make_canary(root)
    return {
        "experiment": "Exp55",
        "title": "Raven Recall Counter Through Consolidation",
        "status": "runtime assay",
        "source_commit": SOURCE_COMMIT,
        "source_copy_hashes": hashes,
        "epistemic_scope": "copied Raven snapshot and synthetic Exp51 fixture",
        "primary_counter_only_comparison": primary,
        "audit_weight_sensitivity_canary": canary,
        "interpretation_limits": [
            "one pinned Raven snapshot and synthetic four-memory fixture",
            "only C/D are consolidation-eligible at cosine threshold 0.90",
            "engine and offline consolidator paths only; no FastAPI or MCP runtime",
            "no live provider, personal data, network, or downstream agent decisions",
            "results apply to this consolidation schedule and fixed C/D queries only",
        ],
    }


def main() -> None:
    result = run_experiment()
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path = ROOT / "exp55_raven_counter_consolidation_run.json"
    path.write_text(encoded, encoding="utf-8")
    print(f"wrote {path.name} sha256={hashlib.sha256(encoded.encode()).hexdigest()}")
    primary = result["primary_counter_only_comparison"]
    canary = result["audit_weight_sensitivity_canary"]
    print(json.dumps({
        "primary_merge_embedding_equal": primary["merged_embedding_equal"],
        "primary_retrieval_equal_after": primary["retrieval_equal_after"],
        "primary_database_equal_after": primary["logical_database_equal_after"],
        "audit_canary_embedding_differs": canary["merged_embedding_different"],
        "canary_C_score_increases": canary["base_score_C_A54_greater"],
        "canary_D_score_decreases": canary["base_score_D_A54_lower"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
