"""Exp53: isolate Raven's persisted recall_count and test its consumers."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

os.environ["RAVEN_ANN_BACKEND"] = "kdtree"
EXP51_DIR = Path(__file__).resolve().parents[1] / "exp51_raven_h14_longitudinal"
sys.path.insert(0, str(EXP51_DIR))

from exp51_raven_h14_longitudinal import (  # noqa: E402
    _canonical_database_digest,
    _core,
    _load_seed_engine,
    _ranked_ids,
    _score_rows,
    build_seed_engine,
)
import vendor.raven as copied_raven  # noqa: E402

# The copied consolidator uses the upstream absolute import spelling
# `raven.memory_engine`. Alias it to the already-loaded vendor package so the
# process does not initialize a second copy of Raven or BLAS.
sys.modules.setdefault("raven", copied_raven)
sys.modules.setdefault("raven.memory_engine", sys.modules["vendor.raven.memory_engine"])
from vendor.raven import sleep_consolidator  # noqa: E402


ROOT = Path(__file__).resolve().parent
QUERY_KEYS = ("A", "B", "C", "D")
NOW = 2000.0
TOP_K = 4
HOPS = 2


def _clone_database(source_path: Path, target_path: Path) -> None:
    with sqlite3.connect(source_path) as source, sqlite3.connect(target_path) as target:
        source.backup(target)


def _set_recall_count(db_path: Path, memory_id: str, value: int) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE memories SET recall_count=? WHERE memory_id=?",
                     (value, memory_id))
        conn.commit()


def _set_consolidation_fixture(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE memories SET layer='episodic', state='NEUTRAL'")
        conn.commit()


def _non_counter_snapshot(db_path: Path) -> dict:
    columns = (
        "memory_id", "layer", "content", "content_hash", "hex(embedding)",
        "state", "cell_id", "created_at", "session_id", "author_id",
        "metadata", "synaptic_links", "last_activation", "fingerprint",
    )
    with sqlite3.connect(db_path) as conn:
        memories = conn.execute(
            "SELECT " + ",".join(columns) + " FROM memories ORDER BY memory_id"
        ).fetchall()
        links = conn.execute(
            "SELECT from_cell_id,to_cell_id,link_type,created_at,auto_generated "
            "FROM cell_links ORDER BY from_cell_id,to_cell_id"
        ).fetchall()
        audit = conn.execute(
            "SELECT id,timestamp,operation,memories_retrieved,audit_hash,prev_hash "
            "FROM audit_log ORDER BY id"
        ).fetchall()
    return {"memories_without_recall_count": memories,
            "cell_links": links, "audit_log": audit}


def _readout(db_path: Path, include_consolidation: bool = False) -> dict:
    engine = _load_seed_engine(db_path)
    retrieval = {}
    for query_key in QUERY_KEYS:
        outcome = _core(engine, query_key, NOW, [], suppressed=frozenset())
        retrieval[query_key] = {
            "ranked_ids": _ranked_ids(outcome),
            "scores": _score_rows(outcome),
        }

    memories = {mem.memory_id: mem for mem in engine.list_memories()}
    inspection = {
        "C_to_dict_recall_count": memories["C"].to_dict()["recall_count"],
        "listed_counts": {mid: mem.to_dict()["recall_count"]
                          for mid, mem in sorted(memories.items())},
    }
    graph = engine.export_graph(max_nodes=1)
    output = {
        "retrieval": retrieval,
        "stats": engine.get_stats(),
        "inspection": inspection,
        "truncated_graph": graph,
        "seed_digest": _canonical_database_digest(db_path),
    }
    if include_consolidation:
        _set_consolidation_fixture(db_path)
        output["sleep_consolidator_dry_run"] = sleep_consolidator.run_consolidation(
            db_path, threshold=0.0, dry_run=True, rebuild_spectral=False,
        )
    return output


def _post_equal_update(db_path: Path) -> dict:
    engine = _load_seed_engine(db_path)
    engine._db.update_activations(["C"], NOW + 1)
    target = engine._db.load_memory("C")
    return {"C_recall_count": target.recall_count,
            "C_last_activation": target.last_activation}


def _build_pair(root: Path) -> tuple[Path, Path, str]:
    seed_path = root / "seed.sqlite"
    seed_engine, _ = build_seed_engine(seed_path)
    seed_engine._ensure_kdtree()
    seed_digest = _canonical_database_digest(seed_path)
    s5_path = root / "state_c5.sqlite"
    s4_path = root / "state_c4.sqlite"
    _clone_database(seed_path, s5_path)
    _clone_database(seed_path, s4_path)
    # The only differences in the pair are C.recall_count and the shared
    # comparator B.recall_count=4. All other fields remain byte-identical.
    _set_recall_count(s5_path, "B", 4)
    _set_recall_count(s4_path, "B", 4)
    _set_recall_count(s5_path, "C", 5)
    _set_recall_count(s4_path, "C", 4)
    return s5_path, s4_path, seed_digest


def _equalized_pair(s5_path: Path, s4_path: Path) -> tuple[Path, Path]:
    root = s5_path.parent
    equal5 = root / "equalized_c5_a.sqlite"
    equal5_b = root / "equalized_c5_b.sqlite"
    _clone_database(s5_path, equal5)
    _clone_database(s4_path, equal5_b)
    _set_recall_count(equal5_b, "C", 5)
    return equal5, equal5_b


def run_experiment() -> dict:
    with tempfile.TemporaryDirectory(prefix="exp53-raven-") as work:
        root = Path(work)
        s5_path, s4_path, seed_digest = _build_pair(root)
        s5_state = _non_counter_snapshot(s5_path)
        s4_state = _non_counter_snapshot(s4_path)
        s5 = _readout(s5_path, include_consolidation=True)
        s4 = _readout(s4_path, include_consolidation=True)
        equal5_path, equal5_b_path = _equalized_pair(s5_path, s4_path)
        equalized_a = _readout(equal5_path, include_consolidation=True)
        equalized_b = _readout(equal5_b_path, include_consolidation=True)
        update = {
            "C5_state": _post_equal_update(s5_path),
            "C4_state": _post_equal_update(s4_path),
        }

    score_equivalence = {
        query: s5["retrieval"][query] == s4["retrieval"][query]
        for query in QUERY_KEYS
    }
    equalized_outputs = {
        "retrieval": equalized_a["retrieval"] == equalized_b["retrieval"],
        "stats": equalized_a["stats"] == equalized_b["stats"],
        "inspection": equalized_a["inspection"] == equalized_b["inspection"],
        "truncated_graph": equalized_a["truncated_graph"] == equalized_b["truncated_graph"],
        "sleep_consolidator_dry_run": (
            equalized_a["sleep_consolidator_dry_run"]
            == equalized_b["sleep_consolidator_dry_run"]
        ),
    }
    return {
        "experiment": "Exp53",
        "title": "Raven Latent Trace Activation Assay",
        "source_commit": "56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f",
        "exp51_seed_sha256": seed_digest,
        "paired_state_differences": {
            "S5_recall_counts": {"B": 4, "C": 5},
            "S4_recall_counts": {"B": 4, "C": 4},
            "all_non_counter_fields_and_audit_rows_equal": s5_state == s4_state,
            "S5_non_counter_sha256": hashlib.sha256(json.dumps(
                s5_state, sort_keys=True, separators=(",", ":")
            ).encode()).hexdigest(),
            "S4_non_counter_sha256": hashlib.sha256(json.dumps(
                s4_state, sort_keys=True, separators=(",", ":")
            ).encode()).hexdigest(),
        },
        "retrieval_score_and_rank_equivalence_by_query": score_equivalence,
        "retrieval_outputs": {"S5": s5["retrieval"], "S4": s4["retrieval"]},
        "telemetry_and_export": {
            "S5_total_recalls": s5["stats"]["total_recalls"],
            "S4_total_recalls": s4["stats"]["total_recalls"],
            "S5_C_inspection_recall_count": s5["inspection"]["C_to_dict_recall_count"],
            "S4_C_inspection_recall_count": s4["inspection"]["C_to_dict_recall_count"],
            "S5_truncated_graph": s5["truncated_graph"],
            "S4_truncated_graph": s4["truncated_graph"],
        },
        "sleep_consolidator": {
            "S5_dry_run": s5["sleep_consolidator_dry_run"],
            "S4_dry_run": s4["sleep_consolidator_dry_run"],
            "dry_run_outputs_equal_with_identical_audit_logs": (
                s5["sleep_consolidator_dry_run"]
                == s4["sleep_consolidator_dry_run"]
            ),
        },
        "equalized_counter_control": equalized_outputs,
        "same_activation_update": update,
        "interpretation_limits": [
            "one pinned Raven source snapshot and synthetic four-memory fixture",
            "four read-only retrieval queries and one deterministic dry-run maintenance path",
            "API behavior is source-inspected; serialization behavior is tested through MemoryEntry.to_dict",
            "no downstream agent action, concurrency, live API server, or production data",
        ],
    }


def main() -> None:
    result = run_experiment()
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path = ROOT / "exp53_raven_latent_trace_run.json"
    path.write_text(encoded, encoding="utf-8")
    print(f"wrote {path.name} sha256={hashlib.sha256(encoded.encode()).hexdigest()}")
    print(json.dumps({
        "only_counter_differs": result["paired_state_differences"][
            "all_non_counter_fields_and_audit_rows_equal"
        ],
        "retrieval_equivalent": result["retrieval_score_and_rank_equivalence_by_query"],
        "total_recalls_S5_S4": [
            result["telemetry_and_export"]["S5_total_recalls"],
            result["telemetry_and_export"]["S4_total_recalls"],
        ],
        "graph_top_ids_S5_S4": [
            result["telemetry_and_export"]["S5_truncated_graph"]["nodes"][0]["memory_id"],
            result["telemetry_and_export"]["S4_truncated_graph"]["nodes"][0]["memory_id"],
        ],
        "consolidation_equal": result["sleep_consolidator"][
            "dry_run_outputs_equal_with_identical_audit_logs"
        ],
        "equalized_control": result["equalized_counter_control"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
