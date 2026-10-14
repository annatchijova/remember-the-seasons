"""Exp56: test whether audit-derived counts suffice for Raven consolidation."""
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
EXP55_DIR = Path(__file__).resolve().parents[1] / "exp55_raven_counter_consolidation"
sys.path.insert(0, str(EXP55_DIR))

from exp55_raven_counter_consolidation import (  # noqa: E402
    NOW,
    SOURCE_COMMIT,
    SOURCE_HASHES,
    _audit_counts,
    _create_fixture,
    _groups,
    _load_seed_engine,
    _query_trace,
    _run_consolidation,
    _source_hashes,
    _vectors,
    sleep_consolidator,
)
from exp53_raven_latent_trace import _clone_database  # noqa: E402

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent
SCHEDULES = {
    "H1": [("C", "canonical")]*5 + [("D", "canonical")]*4,
    "H2": [(memory_id, "canonical") for memory_id in
           ("C", "D", "C", "D", "C", "D", "C", "D", "C")],
    "H3": [("C", "alternate")]*5 + [("D", "alternate")]*4,
    "H4": [("C", "canonical")]*4 + [("D", "canonical")]*5,
}


def _audit_digest(path: Path) -> str:
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY rowid"
        ).fetchall()
        columns = [row[1] for row in conn.execute("PRAGMA table_info(audit_log)")]
    encoded = json.dumps({"columns": columns, "rows": rows}, sort_keys=True,
                         separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _generate_history(path: Path, condition: str) -> dict:
    engine = _load_seed_engine(path)
    schedule = SCHEDULES[condition]
    with patch.object(sleep_consolidator.time, "time", return_value=NOW):
        for ordinal, (memory_id, text_variant) in enumerate(schedule):
            text = f"Exp56 {text_variant} retrieval for {memory_id}"
            results, _audit = engine.recall(
                query_embedding=_vectors()[memory_id],
                query_text=text,
                top_k=1,
                hops=0,
                layer_filter="episodic",
                current_turn_memories=None,
            )
            returned = [result.memory.memory_id for result in results]
            if returned != [memory_id]:
                raise AssertionError(
                    f"{condition} event {ordinal} returned {returned}; expected {[memory_id]}"
                )

    expected = {
        "H1": {"C": 5, "D": 4},
        "H2": {"C": 5, "D": 4},
        "H3": {"C": 5, "D": 4},
        "H4": {"C": 4, "D": 5},
    }[condition]
    audit_counts = _audit_counts(path, ["C", "D"])
    if audit_counts != expected:
        raise AssertionError(f"{condition} audit counts {audit_counts}, expected {expected}")
    with sqlite3.connect(path) as conn:
        row_counts = dict(conn.execute(
            "SELECT memory_id, recall_count FROM memories WHERE memory_id IN ('C','D')"
        ).fetchall())
    expected_rows = {key: 4 + expected[key] for key in ("C", "D")}
    if row_counts != expected_rows:
        raise AssertionError(f"{condition} row counts {row_counts}, expected {expected_rows}")
    if _groups(path) != [["C", "D"]]:
        raise AssertionError(f"{condition} changed the declared merge group")
    return {
        "event_count": len(schedule),
        "audit_counts": audit_counts,
        "persisted_row_counts": row_counts,
        "audit_sha256": _audit_digest(path),
    }


def _base_scores(result: dict) -> dict[str, float]:
    return {
        key: next(row["base_score"] for row in result["retrieval"][key]["scores"]
                  if row["memory_id"] == result["node_id"])
        for key in ("C", "D")
    }


def _run_condition(root: Path, condition: str) -> dict:
    seed = root / f"{condition}_seed.sqlite"
    _create_fixture(seed)
    path = root / f"{condition}.sqlite"
    _clone_database(seed, path)
    history = _generate_history(path, condition)
    outcome = _run_consolidation(path)
    return {
        "history": history,
        "weights": outcome["audit_weight_counts"],
        "merged_embedding_hex": outcome["embedding_hex"],
        "merged_metadata": outcome["metadata"],
        "retrieval": outcome["retrieval"],
        "base_scores": _base_scores(outcome),
    }


def _primary_and_control(root: Path) -> dict:
    branches = {name: _run_condition(root, name) for name in SCHEDULES}
    target_equal = all(
        branches["H1"][field] == branches[name][field]
        for name in ("H2", "H3")
        for field in ("weights", "merged_embedding_hex", "retrieval")
    )
    allocation_control = {
        "embedding_differs": branches["H1"]["merged_embedding_hex"] != branches["H4"]["merged_embedding_hex"],
        "C_score_H1_greater": branches["H1"]["base_scores"]["C"] > branches["H4"]["base_scores"]["C"],
        "D_score_H1_lower": branches["H1"]["base_scores"]["D"] < branches["H4"]["base_scores"]["D"],
    }
    return {
        "branches": branches,
        "same_count_projection_equal_on_target": target_equal,
        "audit_histories_distinct_H1_H2": branches["H1"]["history"]["audit_sha256"] != branches["H2"]["history"]["audit_sha256"],
        "audit_histories_distinct_H1_H3": branches["H1"]["history"]["audit_sha256"] != branches["H3"]["history"]["audit_sha256"],
        "allocation_sensitivity_control": allocation_control,
    }


def _mutation_control() -> dict:
    """Show that the assay detects a deliberately order-sensitive merger."""
    original = sleep_consolidator.get_recall_counts

    def order_sensitive(path: Path, memory_ids: list[str]) -> dict[str, int]:
        counts = original(path, memory_ids)
        with sqlite3.connect(path) as conn:
            row = conn.execute(
                "SELECT memories_retrieved FROM audit_log "
                "WHERE operation='recall' ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
        if row and row[0]:
            last_id = json.loads(row[0])[0].get("memory_id")
            if last_id in counts:
                counts[last_id] += 1
        return counts

    with tempfile.TemporaryDirectory(prefix="exp56-mutation-") as temp:
        root = Path(temp)
        paths = {}
        for condition in ("H1", "H2"):
            seed = root / f"{condition}_seed.sqlite"
            _create_fixture(seed)
            path = root / f"{condition}.sqlite"
            _clone_database(seed, path)
            _generate_history(path, condition)
            paths[condition] = path
        with patch.object(sleep_consolidator, "get_recall_counts", side_effect=order_sensitive):
            mutated = {key: _run_consolidation(path) for key, path in paths.items()}
    detected = mutated["H1"]["embedding_hex"] != mutated["H2"]["embedding_hex"]
    return {
        "deliberate_mutation": "add one consolidation weight to the last retrieved memory",
        "mutant_embedding_diverges_H1_H2": detected,
    }


def run_experiment() -> dict:
    hashes = _source_hashes()
    with tempfile.TemporaryDirectory(prefix="exp56-raven-") as temp:
        primary = _primary_and_control(Path(temp))
    mutation = _mutation_control()
    if not primary["same_count_projection_equal_on_target"]:
        raise AssertionError("Equal audit count vectors diverged on target outputs")
    if not all(primary["allocation_sensitivity_control"].values()):
        raise AssertionError("Per-memory allocation sensitivity control failed")
    if not mutation["mutant_embedding_diverges_H1_H2"]:
        raise AssertionError("Order-sensitive mutation escaped detection")
    return {
        "experiment": "Exp56",
        "title": "Audit Projection Sufficiency for Consolidation",
        "status": "runtime assay",
        "source_commit": SOURCE_COMMIT,
        "source_copy_hashes": hashes,
        "epistemic_scope": "copied Raven snapshot and synthetic Exp51 fixture",
        "parameters": {"threshold": 0.90, "fixed_time": NOW, "backend": "kdtree", "query_keys": ["C", "D"]},
        "primary_and_control": primary,
        "mutation_control": mutation,
        "limitations": [
            "one pinned source snapshot and four-memory synthetic fixture",
            "equivalence covers consolidation weights, merged embedding, and two fixed retrieval traces only",
            "audit logs and other Raven observers intentionally remain distinguishable",
            "does not establish behavior in deployed Raven, MNEME, Stigmergy, or downstream agents",
        ],
    }


def main() -> None:
    result = run_experiment()
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    output = ROOT / "exp56_raven_audit_projection_run.json"
    output.write_text(encoded, encoding="utf-8")
    print(f"wrote {output.name} sha256={hashlib.sha256(encoded.encode()).hexdigest()}")
    print(json.dumps({
        "same_count_projection_equal": result["primary_and_control"]["same_count_projection_equal_on_target"],
        "audit_histories_distinct": result["primary_and_control"]["audit_histories_distinct_H1_H2"],
        "allocation_control": result["primary_and_control"]["allocation_sensitivity_control"],
        "mutation_detected": result["mutation_control"]["mutant_embedding_diverges_H1_H2"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
