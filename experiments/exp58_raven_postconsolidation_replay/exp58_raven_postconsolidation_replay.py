"""Exp58: compare post-consolidation recall trajectories across audit histories."""
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
EXP57_DIR = Path(__file__).resolve().parents[1] / "exp57_raven_temporal_recency"
sys.path.insert(0, str(EXP57_DIR))

from exp57_raven_temporal_recency import (  # noqa: E402
    NOW,
    SOURCE_COMMIT,
    _consolidate_and_trace,
    _generate_history,
    _make_branch,
    _source_hashes,
    sleep_consolidator,
)
from exp53_raven_latent_trace import _clone_database, _load_seed_engine  # noqa: E402
from exp51_raven_h14_longitudinal import _vectors  # noqa: E402
from vendor.raven import memory_engine  # noqa: E402

ROOT = Path(__file__).resolve().parent
QUERY_SEQUENCE = ("C", "D", "D", "C", "D", "C", "C", "D")
STEP_SECONDS = 21_600.0
TOP_K = 4


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         allow_nan=False, default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _operational_state(path: Path) -> dict:
    """Capture mutable memory and link state, excluding the audit ledger."""
    def encode(value):
        return {"blob_hex": value.hex()} if isinstance(value, bytes) else value

    with sqlite3.connect(path) as conn:
        memories = conn.execute(
            "SELECT * FROM memories ORDER BY memory_id"
        ).fetchall()
        memory_columns = [row[1] for row in conn.execute("PRAGMA table_info(memories)")]
        links = conn.execute(
            "SELECT * FROM cell_links ORDER BY from_cell_id,to_cell_id,link_type"
        ).fetchall()
        link_columns = [row[1] for row in conn.execute("PRAGMA table_info(cell_links)")]
    return {
        "memories": {"columns": memory_columns,
                     "rows": [[encode(value) for value in row] for row in memories]},
        "cell_links": {"columns": link_columns,
                       "rows": [[encode(value) for value in row] for row in links]},
    }


def _audit_digest(path: Path) -> str:
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
        columns = [row[1] for row in conn.execute("PRAGMA table_info(audit_log)")]
    return _canonical_hash({"columns": columns, "rows": rows})


def _recall(path: Path, query_key: str, ordinal: int) -> dict:
    timestamp = NOW + ordinal * STEP_SECONDS
    engine = _load_seed_engine(path)
    with patch.object(sleep_consolidator.time, "time", return_value=timestamp):
        results, audit = engine.recall(
            query_embedding=_vectors()[query_key],
            query_text=f"Exp58 shared longitudinal query {ordinal}",
            top_k=TOP_K,
            hops=0,
            layer_filter=None,
            current_turn_memories=None,
        )
    rows = [
        {
            "rank": rank,
            "memory_id": item.memory.memory_id,
            "base_score": item.base_score,
            "state_boost": item.state_boost,
            "hop_decay": item.hop_decay,
            "synaptic_boost": item.synaptic_boost,
            "recency_bonus": item.recency_bonus,
            "score": item.final_score,
            "hop_distance": item.hop_distance,
            "source": item.source,
        }
        for rank, item in enumerate(results, start=1)
    ]
    return {
        "query": query_key,
        "timestamp": timestamp,
        "returned": rows,
        "audit_entry_hash": audit.audit_hash,
    }


def _prepare_branches(root: Path) -> dict[str, Path]:
    paths = {}
    for name in ("T1", "T2"):
        path = _make_branch(root, f"{name}_longitudinal")
        _generate_history(path, name)
        _consolidate_and_trace(path)
        paths[name] = path
    return paths


def _chain_verdict(path: Path) -> dict:
    engine = _load_seed_engine(path)
    verdict = memory_engine.verify_audit_chain(engine._db.get_audit_trail(limit=1000))
    return {
        "chain_intact": verdict["chain_intact"],
        "hash_integrity": verdict["hash_integrity"],
        "issue_count": len(verdict["issues"]),
    }


def _run_sequence(path: Path) -> list[dict]:
    trace = []
    for ordinal, key in enumerate(QUERY_SEQUENCE, start=1):
        outcome = _recall(path, key, ordinal)
        trace.append({
            "behavioral_output": {
                key: value for key, value in outcome.items()
                if key != "audit_entry_hash"
            },
            "audit_entry_hash": outcome["audit_entry_hash"],
            "operational_state_sha256": _canonical_hash(_operational_state(path)),
        })
    return trace


def _trajectory_assay(root: Path) -> dict:
    paths = _prepare_branches(root)
    initial_state_equal = _operational_state(paths["T1"]) == _operational_state(paths["T2"])
    initial_audit_digests = {name: _audit_digest(path) for name, path in paths.items()}
    initial_history_distinct = initial_audit_digests["T1"] != initial_audit_digests["T2"]
    trajectories = {name: _run_sequence(path) for name, path in paths.items()}
    step_equal = [
        (
            trajectories["T1"][index]["behavioral_output"]
            == trajectories["T2"][index]["behavioral_output"]
            and trajectories["T1"][index]["operational_state_sha256"]
            == trajectories["T2"][index]["operational_state_sha256"]
        )
        for index in range(len(QUERY_SEQUENCE))
    ]
    audit_hash_equal = [
        trajectories["T1"][index]["audit_entry_hash"]
        == trajectories["T2"][index]["audit_entry_hash"]
        for index in range(len(QUERY_SEQUENCE))
    ]
    final_audit_digests = {name: _audit_digest(path) for name, path in paths.items()}
    chains = {name: _chain_verdict(path) for name, path in paths.items()}
    return {
        "query_sequence": list(QUERY_SEQUENCE),
        "initial_memory_and_link_state_equal": initial_state_equal,
        "initial_audit_histories_distinct": initial_history_distinct,
        "initial_audit_sha256": initial_audit_digests,
        "trajectories": trajectories,
        "per_step_observations_and_state_equal": step_equal,
        "all_steps_equal": all(step_equal),
        "per_step_audit_hashes_distinct": [not equal for equal in audit_hash_equal],
        "all_step_audit_hashes_distinct": all(not equal for equal in audit_hash_equal),
        "final_audit_histories_distinct": final_audit_digests["T1"] != final_audit_digests["T2"],
        "final_audit_sha256": final_audit_digests,
        "audit_chain_verification": chains,
    }


def _state_sensitivity_control(root: Path) -> dict:
    source = _make_branch(root, "mutation_source")
    _generate_history(source, "T2")
    _consolidate_and_trace(source)
    control = root / "mutation_control.sqlite"
    mutant = root / "mutation_state.sqlite"
    _clone_database(source, control)
    _clone_database(source, mutant)
    with sqlite3.connect(mutant) as conn:
        conn.execute("UPDATE memories SET last_activation=? WHERE memory_id LIKE 'cons_%'", (NOW,))
        conn.commit()
    base = _recall(control, "C", 1)
    changed = _recall(mutant, "C", 1)
    base_row = next(row for row in base["returned"] if row["memory_id"].startswith("cons_"))
    changed_row = next(row for row in changed["returned"] if row["memory_id"].startswith("cons_"))
    return {
        "mutation": "set merged node last_activation to the query timestamp",
        "baseline_recency_bonus": base_row["recency_bonus"],
        "mutant_recency_bonus": changed_row["recency_bonus"],
        "state_change_detected": base_row["recency_bonus"] != changed_row["recency_bonus"],
    }


def run_experiment() -> dict:
    source_hashes = _source_hashes()
    with tempfile.TemporaryDirectory(prefix="exp58-raven-") as temp:
        root = Path(temp)
        trajectory = _trajectory_assay(root)
        sensitivity = _state_sensitivity_control(root)
    valid_chains = all(
        verdict["chain_intact"] and verdict["hash_integrity"]
        for verdict in trajectory["audit_chain_verification"].values()
    )
    required = (
        trajectory["initial_memory_and_link_state_equal"],
        trajectory["initial_audit_histories_distinct"],
        trajectory["all_steps_equal"],
        trajectory["final_audit_histories_distinct"],
        valid_chains,
        sensitivity["state_change_detected"],
    )
    if not all(required):
        raise AssertionError(f"Exp58 preregistered checks failed: {required}")
    return {
        "experiment": "Exp58",
        "title": "Post-Consolidation Longitudinal Replay",
        "status": "runtime assay",
        "source_commit": SOURCE_COMMIT,
        "source_copy_hashes": source_hashes,
        "epistemic_scope": "copied Raven snapshot and synthetic Exp51 fixture",
        "parameters": {
            "query_sequence": list(QUERY_SEQUENCE),
            "step_seconds": STEP_SECONDS,
            "top_k": TOP_K,
            "hops": 0,
            "timestamp_schedule": "NOW + ordinal * 21600 seconds",
        },
        "trajectory_assay": trajectory,
        "state_sensitivity_control": sensitivity,
        "limitations": [
            "one pinned source snapshot and four-memory synthetic fixture",
            "eight fixed real recall operations after one consolidation pass",
            "memory rows and cell links compared; audit histories remain intentionally distinct",
            "does not test arbitrary Raven operations, deployed agents, MNEME, or Stigmergy",
        ],
    }


def main() -> None:
    result = run_experiment()
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    output = ROOT / "exp58_raven_postconsolidation_replay_run.json"
    output.write_text(encoded, encoding="utf-8")
    print(f"wrote {output.name} sha256={hashlib.sha256(encoded.encode()).hexdigest()}")
    print(json.dumps({
        "initial_state_equal": result["trajectory_assay"]["initial_memory_and_link_state_equal"],
        "audit_histories_distinct": result["trajectory_assay"]["initial_audit_histories_distinct"],
        "all_longitudinal_steps_equal": result["trajectory_assay"]["all_steps_equal"],
        "chains_valid": all(x["chain_intact"] and x["hash_integrity"] for x in result["trajectory_assay"]["audit_chain_verification"].values()),
        "state_mutation_detected": result["state_sensitivity_control"]["state_change_detected"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
