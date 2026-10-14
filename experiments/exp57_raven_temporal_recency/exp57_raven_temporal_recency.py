"""Exp57: test timestamp allocation and recency across Raven consolidation."""
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
EXP56_DIR = Path(__file__).resolve().parents[1] / "exp56_raven_audit_projection"
sys.path.insert(0, str(EXP56_DIR))

from exp56_raven_audit_projection import (  # noqa: E402
    SOURCE_COMMIT,
    _audit_counts,
    _create_fixture,
    _groups,
    _source_hashes,
    _vectors,
    sleep_consolidator,
)
from exp53_raven_latent_trace import (  # noqa: E402
    _clone_database,
    _load_seed_engine,
    _ranked_ids,
    _score_rows,
)
from vendor.raven import memory_engine  # noqa: E402

ROOT = Path(__file__).resolve().parent
NOW = 2_000_000.0
OLD = NOW - 14 * 86_400.0
THRESHOLD = 0.90
TOP_K = 4


def _make_branch(root: Path, name: str) -> Path:
    seed = root / f"{name}_seed.sqlite"
    _create_fixture(seed)
    target = root / f"{name}.sqlite"
    _clone_database(seed, target)
    return target


def _timestamp_schedule(branch: str) -> list[tuple[str, float]]:
    if branch == "T1":
        return [("D", OLD)] * 4 + [("C", NOW)] * 5
    if branch == "T2":
        return [("C", OLD)] * 5 + [("D", NOW)] * 4
    raise ValueError(f"Unknown branch {branch}")


def _generate_history(path: Path, branch: str) -> dict:
    engine = _load_seed_engine(path)
    schedule = _timestamp_schedule(branch)
    for ordinal, (memory_id, timestamp) in enumerate(schedule):
        with patch.object(sleep_consolidator.time, "time", return_value=timestamp):
            results, _audit = engine.recall(
                query_embedding=_vectors()[memory_id],
                query_text="Exp57 fixed temporal-assignment probe",
                top_k=1,
                hops=0,
                layer_filter="episodic",
                current_turn_memories=None,
            )
        result_ids = [result.memory.memory_id for result in results]
        if result_ids != [memory_id]:
            raise AssertionError(
                f"{branch} event {ordinal} returned {result_ids}; expected {[memory_id]}"
            )

    counts = _audit_counts(path, ["C", "D"])
    if counts != {"C": 5, "D": 4}:
        raise AssertionError(f"{branch} audit counts differ: {counts}")
    with sqlite3.connect(path) as conn:
        rows = dict(conn.execute(
            "SELECT memory_id, recall_count FROM memories WHERE memory_id IN ('C','D')"
        ).fetchall())
        activation = dict(conn.execute(
            "SELECT memory_id, last_activation FROM memories WHERE memory_id IN ('C','D')"
        ).fetchall())
        event_count = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE operation='recall'"
        ).fetchone()[0]
    if rows != {"C": 9, "D": 8} or event_count != 9:
        raise AssertionError(f"{branch} row counts/events incorrect: {rows}, {event_count}")
    if activation != ({"C": NOW, "D": OLD} if branch == "T1" else {"C": OLD, "D": NOW}):
        raise AssertionError(f"{branch} activation timestamps incorrect: {activation}")
    if _groups(path) != [["C", "D"]]:
        raise AssertionError(f"{branch} did not preserve the declared C/D merge group")
    return {
        "audit_counts": counts,
        "persisted_row_counts": rows,
        "last_activation": activation,
        "event_count": event_count,
    }


def _trace(path: Path, now: float = NOW) -> dict:
    engine = _load_seed_engine(path)
    engine._ensure_kdtree()
    trace = {}
    for key in ("C", "D"):
        outcome = engine._recall_core(
            _vectors()[key], now=now, top_k=TOP_K, hops=0,
            current_turn_memories=None,
        )
        trace[key] = {
            "ranked_ids": _ranked_ids(outcome),
            "scores": _score_rows(outcome),
        }
    return trace


def _memory_score(trace: dict, query: str, memory_id: str, field: str) -> float:
    return next(row[field] for row in trace[query]["scores"]
                if row["memory_id"] == memory_id)


def _consolidate_and_trace(path: Path) -> dict:
    counts = _audit_counts(path, ["C", "D"])
    with patch.object(sleep_consolidator.time, "time", return_value=NOW):
        run = sleep_consolidator.run_consolidation(
            path, threshold=THRESHOLD, dry_run=False, rebuild_spectral=False,
        )
    engine = _load_seed_engine(path)
    nodes = [m for m in engine.list_memories() if m.memory_id.startswith("cons_")]
    if len(nodes) != 1:
        raise AssertionError(f"Expected one merged node; found {len(nodes)}")
    node = nodes[0]
    trace = _trace(path)
    return {
        "run": run,
        "audit_counts": counts,
        "merged_node_id": node.memory_id,
        "merged_embedding_hex": node.embedding.tobytes().hex(),
        "merged_last_activation": node.last_activation,
        "merged_metadata": node.metadata,
        "post_retrieval": trace,
    }


def _audit_digest(path: Path) -> str:
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
        columns = [row[1] for row in conn.execute("PRAGMA table_info(audit_log)")]
    payload = json.dumps({"columns": columns, "rows": rows}, sort_keys=True,
                         separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _assay(root: Path) -> dict:
    branches = {}
    paths = {}
    for name in ("T1", "T2"):
        path = _make_branch(root, name)
        paths[name] = path
        history = _generate_history(path, name)
        pre = _trace(path)
        branches[name] = {
            "history": history,
            "pre_retrieval": pre,
            "audit_sha256": _audit_digest(path),
        }

    recency_assignment_differs = any(
        branches["T1"]["pre_retrieval"][key] != branches["T2"]["pre_retrieval"][key]
        for key in ("C", "D")
    )
    expected_directions = (
        _memory_score(branches["T1"]["pre_retrieval"], "C", "C", "recency_bonus")
        > _memory_score(branches["T2"]["pre_retrieval"], "C", "C", "recency_bonus")
        and _memory_score(branches["T2"]["pre_retrieval"], "D", "D", "recency_bonus")
        > _memory_score(branches["T1"]["pre_retrieval"], "D", "D", "recency_bonus")
    )

    equalized_paths = {}
    for name, source in paths.items():
        clone = root / f"{name}_equalized.sqlite"
        _clone_database(source, clone)
        with sqlite3.connect(clone) as conn:
            conn.execute("UPDATE memories SET last_activation=? WHERE memory_id IN ('C','D')", (NOW,))
            conn.commit()
        equalized_paths[name] = _trace(clone)
    timestamp_equalization_works = equalized_paths["T1"] == equalized_paths["T2"]

    consolidated = {
        name: _consolidate_and_trace(paths[name]) for name in ("T1", "T2")
    }
    post_match = all(
        consolidated["T1"][key] == consolidated["T2"][key]
        for key in ("audit_counts", "merged_embedding_hex", "post_retrieval")
    )
    node_activation_zero = all(
        consolidated[name]["merged_last_activation"] == 0.0 for name in ("T1", "T2")
    )

    return {
        "branches": branches,
        "pre_retrieval_temporal_difference": recency_assignment_differs,
        "pre_retrieval_recency_directions_match": expected_directions,
        "equalized_pre_retrieval_traces_match": timestamp_equalization_works,
        "post_consolidation_outputs_match": post_match,
        "merged_nodes_start_without_recency": node_activation_zero,
        "consolidated": consolidated,
    }


def _recency_mutation(root: Path) -> dict:
    paths = {}
    for name in ("T1", "T2"):
        path = _make_branch(root, f"mut_{name}")
        _generate_history(path, name)
        paths[name] = path
    with patch.object(memory_engine, "RECENCY_WEIGHT", 0.0):
        traces = {name: _trace(path) for name, path in paths.items()}
    return {
        "mutation": "set copied engine RECENCY_WEIGHT to zero",
        "temporal_trace_difference_removed": traces["T1"] == traces["T2"],
    }


def run_experiment() -> dict:
    source_hashes = _source_hashes()
    with tempfile.TemporaryDirectory(prefix="exp57-raven-") as temp:
        root = Path(temp)
        assay = _assay(root)
        mutation = _recency_mutation(root)
    required = (
        assay["pre_retrieval_temporal_difference"],
        assay["pre_retrieval_recency_directions_match"],
        assay["equalized_pre_retrieval_traces_match"],
        assay["post_consolidation_outputs_match"],
        assay["merged_nodes_start_without_recency"],
        mutation["temporal_trace_difference_removed"],
    )
    if not all(required):
        raise AssertionError(f"Exp57 preregistered checks failed: {required}")
    return {
        "experiment": "Exp57",
        "title": "Temporal Recency Through Consolidation",
        "status": "runtime assay",
        "source_commit": SOURCE_COMMIT,
        "source_copy_hashes": source_hashes,
        "parameters": {
            "threshold": THRESHOLD,
            "old_timestamp": OLD,
            "recent_timestamp": NOW,
            "fixed_observation_time": NOW,
            "backend": "kdtree",
            "top_k_retrieval_probe": TOP_K,
        },
        "epistemic_scope": "copied Raven snapshot and synthetic Exp51 fixture",
        "assay": assay,
        "mutation_control": mutation,
        "limitations": [
            "one pinned source snapshot and four-memory synthetic fixture",
            "fixed C/D query vectors and one 14-day timestamp contrast",
            "only the selected engine retrieval and offline consolidation paths were measured",
            "audit histories remain distinguishable after consolidation",
            "no deployed agent, MNEME, Stigmergy, or downstream decision validation",
        ],
    }


def main() -> None:
    result = run_experiment()
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    output = ROOT / "exp57_raven_temporal_recency_run.json"
    output.write_text(encoded, encoding="utf-8")
    print(f"wrote {output.name} sha256={hashlib.sha256(encoded.encode()).hexdigest()}")
    print(json.dumps({
        "pre_temporal_difference": result["assay"]["pre_retrieval_temporal_difference"],
        "timestamp_equalization": result["assay"]["equalized_pre_retrieval_traces_match"],
        "post_consolidation_match": result["assay"]["post_consolidation_outputs_match"],
        "mutation_detected": result["mutation_control"]["temporal_trace_difference_removed"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
