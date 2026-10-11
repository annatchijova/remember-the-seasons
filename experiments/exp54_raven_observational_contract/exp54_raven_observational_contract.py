"""Exp54: observable-contract and tie-order probes on copied Raven source."""
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
sys.path.insert(0, str(EXP51_DIR))

from exp53_raven_latent_trace import (  # noqa: E402
    NOW,
    QUERY_KEYS,
    _canonical_database_digest,
    _clone_database,
    _core,
    _load_seed_engine,
    _ranked_ids,
    _score_rows,
    _set_recall_count,
    build_seed_engine,
)
from exp51_raven_h14_longitudinal import _vectors  # noqa: E402
from vendor.raven.memory_engine import LinkType, MemoryState  # noqa: E402
from vendor.raven import memory_engine as raven_engine_module  # noqa: E402

ROOT = Path(__file__).resolve().parent
SOURCE_COMMIT = "56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f"
ACTION_NAMES = ("recall", "store", "reinforce", "forget", "create_cell_link")


def _make_s4_pair(root: Path) -> tuple[Path, Path]:
    seed = root / "seed.sqlite"
    engine, _ = build_seed_engine(seed)
    engine._ensure_kdtree()
    normal = root / "s4_normal.sqlite"
    reverse = root / "s4_reverse.sqlite"
    _clone_database(seed, normal)
    _clone_database(seed, reverse)
    for path in (normal, reverse):
        _set_recall_count(path, "B", 4)
        _set_recall_count(path, "C", 4)
    _reverse_memory_row_order(reverse)
    return normal, reverse


def _reverse_memory_row_order(db_path: Path) -> None:
    """Reinsert identical memory rows in reverse rowid order, in a clone."""
    with sqlite3.connect(db_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(memories)")]
        names = ",".join(f'"{name}"' for name in columns)
        conn.execute("CREATE TEMP TABLE exp54_rows AS SELECT rowid AS exp54_rowid, * FROM memories")
        conn.execute("DELETE FROM memories")
        conn.execute(
            f"INSERT INTO memories ({names}) SELECT {names} FROM exp54_rows "
            "ORDER BY exp54_rowid DESC"
        )
        conn.execute("DROP TABLE exp54_rows")
        conn.commit()


def _row_order(db_path: Path) -> list[list[object]]:
    with sqlite3.connect(db_path) as conn:
        return [list(row) for row in conn.execute(
            "SELECT memory_id,rowid FROM memories ORDER BY rowid"
        )]


def _logical_memory_rows(db_path: Path) -> list[list[object]]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT memory_id,layer,content,content_hash,hex(embedding),state,cell_id,"
            "created_at,session_id,author_id,metadata,synaptic_links,last_activation,"
            "recall_count,fingerprint FROM memories ORDER BY memory_id"
        ).fetchall()
    return [list(row) for row in rows]


def _retrieval_signature(db_path: Path) -> dict:
    engine = _load_seed_engine(db_path)
    signature = {}
    for query in QUERY_KEYS:
        outcome = _core(engine, query, NOW, [], suppressed=frozenset())
        signature[query] = {"scores": _score_rows(outcome), "ranked_ids": _ranked_ids(outcome)}
    return signature


def _deterministic_truncated_ids(db_path: Path, limit: int) -> list[str]:
    """Experimental comparator for export_graph's truncated-node selection."""
    with sqlite3.connect(db_path) as conn:
        return [row[0] for row in conn.execute(
            "SELECT memory_id FROM memories "
            "ORDER BY recall_count DESC, memory_id ASC LIMIT ?", (limit,)
        )]


def _graph_ids(db_path: Path, max_nodes: int) -> list[str]:
    return [node["memory_id"] for node in _load_seed_engine(db_path)
            .export_graph(max_nodes=max_nodes)["nodes"]]


def _stats_inspection(db_path: Path) -> dict:
    engine = _load_seed_engine(db_path)
    return {
        "stats": engine.get_stats(),
        "inspection": {
            item.memory_id: item.to_dict()["recall_count"]
            for item in engine.list_memories()
        },
    }


def _apply_action(db_path: Path, action: str) -> dict:
    engine = _load_seed_engine(db_path)
    with patch.object(raven_engine_module.time, "time", return_value=NOW):
        if action == "recall":
            results, audit = engine.recall(
                _vectors()["B"], query_text="Exp54 fixed recall",
                top_k=4, hops=2, current_turn_memories=[],
            )
            return {
                "ranked_ids": [result.memory.memory_id for result in results],
                "scores": [
                    {"memory_id": r.memory.memory_id, "score": r.final_score,
                     "synaptic_boost": r.synaptic_boost,
                     "hop_distance": r.hop_distance}
                    for r in results
                ],
                "audit_operation": audit.operation,
            }
        if action == "store":
            entry = engine.store(
                content="Exp54 deterministic stored fixture",
                embedding=_vectors()["D"], layer="semantic",
                state=MemoryState.NEUTRAL, session_id="exp54",
                author_id="fixture", metadata={"experiment": "exp54"},
            )
            return {"memory_id": entry.memory_id, "cell_id": entry.cell_id,
                    "state": entry.state.name, "recall_count": entry.recall_count}
        if action == "reinforce":
            entry = engine.reinforce("C")
            return {"memory_id": entry.memory_id, "state": entry.state.name}
        if action == "forget":
            entry = engine.forget("C")
            return {"memory_id": entry.memory_id, "state": entry.state.name}
        if action == "create_cell_link":
            engine.create_cell_link(1, 3, LinkType.INHIBITORY)
            return {"from": 1, "to": 3, "type": "INHIBITORY"}
    raise ValueError(f"Unknown action: {action}")


def _build_counter_pair(root: Path) -> tuple[Path, Path]:
    seed = root / "counter_seed.sqlite"
    engine, _ = build_seed_engine(seed)
    engine._ensure_kdtree()
    s5, s4 = root / "counter_s5.sqlite", root / "counter_s4.sqlite"
    _clone_database(seed, s5)
    _clone_database(seed, s4)
    for path in (s5, s4):
        _set_recall_count(path, "B", 4)
    _set_recall_count(s5, "C", 5)
    _set_recall_count(s4, "C", 4)
    return s5, s4


def _action_congruence(root: Path) -> dict:
    rows = {}
    for action in ACTION_NAMES:
        action_root = root / action
        action_root.mkdir()
        s5, s4 = _build_counter_pair(action_root)
        out5 = _apply_action(s5, action)
        out4 = _apply_action(s4, action)
        retrieval5 = _retrieval_signature(s5)
        retrieval4 = _retrieval_signature(s4)
        rows[action] = {
            "immediate_outputs_equal": out5 == out4,
            "S5_immediate_output": out5,
            "S4_immediate_output": out4,
            "successor_retrieval_equivalent": retrieval5 == retrieval4,
            "S5_successor_retrieval": retrieval5,
            "S4_successor_retrieval": retrieval4,
            "successor_total_recalls": [
                _stats_inspection(s5)["stats"]["total_recalls"],
                _stats_inspection(s4)["stats"]["total_recalls"],
            ],
        }
    return rows


def run_experiment() -> dict:
    with tempfile.TemporaryDirectory(prefix="exp54-raven-") as temp:
        root = Path(temp)
        normal, reversed_db = _make_s4_pair(root)
        logical_normal = _logical_memory_rows(normal)
        logical_reversed = _logical_memory_rows(reversed_db)
        normal_full = _graph_ids(normal, max_nodes=10)
        reversed_full = _graph_ids(reversed_db, max_nodes=10)
        original_normal = _graph_ids(normal, max_nodes=1)
        original_reversed = _graph_ids(reversed_db, max_nodes=1)
        stable_normal = _deterministic_truncated_ids(normal, 1)
        stable_reversed = _deterministic_truncated_ids(reversed_db, 1)
        retrieval_normal = _retrieval_signature(normal)
        retrieval_reversed = _retrieval_signature(reversed_db)
        physical_order = {"normal": _row_order(normal), "reversed": _row_order(reversed_db)}
        s5_path, s4_path = _build_counter_pair(root)
        pre_action = _retrieval_signature(s5_path) == _retrieval_signature(s4_path)
        action_results = _action_congruence(root)
        baseline_stats = {
            "S5": _stats_inspection(s5_path),
            "S4": _stats_inspection(s4_path),
        }

    return {
        "experiment": "Exp54",
        "title": "Raven Observational Contract and Transition Congruence",
        "source_commit": SOURCE_COMMIT,
        "epistemic_scope": "copied Raven snapshot and synthetic Exp51 fixture",
        "source_inventory": {
            "fastapi_public_routes": {
                "read_or_observe": ["GET /", "GET /demo", "GET /api", "GET /health",
                                    "GET /memories", "GET /memories/{memory_id}",
                                    "GET /graph", "GET /stats", "GET /audit",
                                    "GET /metrics", "GET /alerts", "WS /ws"],
                "mutating_or_observation_with_possible_write": [
                    "POST /memories", "POST /memories/{memory_id}/reinforce",
                    "POST /memories/{memory_id}/forget", "POST /recall",
                    "POST /cell-links", "POST /consolidate",
                ],
            },
            "mcp_tools": ["raven_store", "raven_recall", "raven_reinforce",
                           "raven_forget", "raven_create_link", "raven_stats",
                           "raven_get_memory", "raven_audit_trail",
                           "raven_export_graph", "raven_verify_chain",
                           "raven_consolidate", "raven_info"],
            "classification_limit": "route and tool declarations inventoried; all dynamic consumers and external clients not enumerated",
        },
        "equivalence_definition": {
            "retrieval": "exact equality of all score rows and ranked IDs for A/B/C/D fixed probes",
            "operational_observations": ["stats", "serialized memory inspection",
                                         "truncated graph", "selected action outputs"],
            "transition_congruence_domain": list(ACTION_NAMES),
        },
        "initial_counter_pair": {
            "retrieval_equivalent": pre_action,
            "S5_total_recalls": baseline_stats["S5"]["stats"]["total_recalls"],
            "S4_total_recalls": baseline_stats["S4"]["stats"]["total_recalls"],
            "S5_memory_recall_counts": baseline_stats["S5"]["inspection"],
            "S4_memory_recall_counts": baseline_stats["S4"]["inspection"],
        },
        "selected_action_congruence": action_results,
        "sqlite_row_order_probe": {
            "logical_memory_rows_equal": logical_normal == logical_reversed,
            "logical_state_sha256_normal": hashlib.sha256(json.dumps(
                logical_normal, separators=(",", ":")
            ).encode()).hexdigest(),
            "logical_state_sha256_reversed": hashlib.sha256(json.dumps(
                logical_reversed, separators=(",", ":")
            ).encode()).hexdigest(),
            "physical_row_order": physical_order,
            "full_graph_node_order_equal": normal_full == reversed_full,
            "retrieval_equivalent_after_permutation": retrieval_normal == retrieval_reversed,
            "original_truncated_graph_ids": {
                "normal": original_normal, "reversed": original_reversed,
                "equal": original_normal == original_reversed,
            },
            "experimental_secondary_key_ids": {
                "normal": stable_normal, "reversed": stable_reversed,
                "equal": stable_normal == stable_reversed,
            },
            "experimental_order_clause": "recall_count DESC, memory_id ASC",
        },
        "interpretation_limits": [
            "static route/tool inventory plus five direct engine action schedules",
            "synthetic four-memory fixture; no FastAPI/MCP server or real agent execution",
            "no arbitrary request inputs, concurrency, live cache, embedding provider, or non-dry-run consolidation",
            "retrieval congruence is bounded to four fixed queries and the selected action inputs",
            "the secondary-key selector is an experimental comparator, not an upstream Raven fix",
        ],
    }


def main() -> None:
    result = run_experiment()
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path = ROOT / "exp54_raven_observational_contract_run.json"
    path.write_text(encoded, encoding="utf-8")
    print(f"wrote {path.name} sha256={hashlib.sha256(encoded.encode()).hexdigest()}")
    print(json.dumps({
        "pre_action_retrieval_equivalent": result["initial_counter_pair"]["retrieval_equivalent"],
        "action_congruence": {
            name: {
                "immediate_outputs_equal": row["immediate_outputs_equal"],
                "successor_retrieval_equivalent": row["successor_retrieval_equivalent"],
            }
            for name, row in result["selected_action_congruence"].items()
        },
        "row_order": result["sqlite_row_order_probe"]["original_truncated_graph_ids"],
        "deterministic_selector": result["sqlite_row_order_probe"]["experimental_secondary_key_ids"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
