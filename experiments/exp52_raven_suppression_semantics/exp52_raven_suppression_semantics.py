"""Exp52: test Raven suppression contracts on an isolated synthetic fixture."""
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
    _vectors,
    build_seed_engine,
)


ROOT = Path(__file__).resolve().parent
TARGET = "A"
POST_QUERIES = ("B", "C", "D", "B")


def _all_scores(outcome) -> dict[str, float]:
    return {row.memory.memory_id: row.final_score for row in outcome.scored}


def _score_vector(outcome, excluded: set[str] | None = None) -> dict[str, float]:
    excluded = excluded or set()
    return {mid: score for mid, score in sorted(_all_scores(outcome).items())
            if mid not in excluded}


def _influence_excluded_core(engine, query_key: str, now: float,
                             current_turn_memories: list[str],
                             suppressed_cell: int,
                             mutation_bypass_source_filter: bool = False):
    """Experiment policy: suppression plus filtering silenced source IDs."""
    silenced = {engine._cell_to_memid[suppressed_cell]}
    sources = (list(current_turn_memories) if mutation_bypass_source_filter else
               [mid for mid in current_turn_memories if mid not in silenced])
    if mutation_bypass_source_filter:
        engine._ensure_kdtree()
        return engine._recall_core(
            _vectors()[query_key], now=now, top_k=4, hops=2,
            current_turn_memories=sources,
            suppressed=frozenset({suppressed_cell}),
        )
    return _core(engine, query_key, now, sources,
                 suppressed=frozenset({suppressed_cell}))


def _suppression_contracts(engine) -> dict:
    target = engine._db.load_memory(TARGET)
    engine._ensure_kdtree()
    query = _vectors()["B"]
    raw = engine._recall_core(
        query, now=1001.0, top_k=4, hops=2,
        current_turn_memories=[TARGET],
        suppressed=frozenset({target.cell_id}),
    )
    isolated = _influence_excluded_core(
        engine, "B", 1001.0, [TARGET], target.cell_id,
    )
    no_source = _core(
        engine, "B", 1001.0, [], suppressed=frozenset({target.cell_id}),
    )
    raw_vector = _score_vector(raw, {TARGET})
    isolated_vector = _score_vector(isolated, {TARGET})
    control_vector = _score_vector(no_source, {TARGET})
    return {
        "query": "B",
        "suppressed_target_cell": target.cell_id,
        "result_exclusion": {
            "target_absent_from_ranked": TARGET not in _ranked_ids(raw),
            "ranked_ids": _ranked_ids(raw),
            "synaptic_C_present": any(
                row.memory.memory_id == "C" and row.source == "synaptic"
                for row in raw.scored
            ),
            "score_rows": _score_rows(raw),
        },
        "raw_suppressed_source_non_target_scores": raw_vector,
        "influence_exclusion_non_target_scores": isolated_vector,
        "no_source_negative_control_non_target_scores": control_vector,
        "influence_policy_matches_negative_control": isolated_vector == control_vector,
        "raw_source_differs_from_negative_control": raw_vector != control_vector,
        "raw_minus_no_source": {
            memory_id: raw_vector.get(memory_id, 0.0) - control_vector.get(memory_id, 0.0)
            for memory_id in sorted(set(raw_vector) | set(control_vector))
        },
    }


def _erase_target_and_incident_links(engine, target_id: str) -> None:
    target = engine._db.load_memory(target_id)
    if target is None:
        raise ValueError(f"target {target_id} missing before operational erasure")
    for memory in engine._db.load_memories():
        if memory.memory_id == target_id or target_id in memory.synaptic_links:
            links = dict(memory.synaptic_links)
            if memory.memory_id == target_id:
                links.clear()
            else:
                links.pop(target_id, None)
            engine._db.update_synaptic_links(memory.memory_id, links)
    with engine._db._connect() as conn:
        conn.execute("DELETE FROM cell_links WHERE from_cell_id=? OR to_cell_id=?",
                     (target.cell_id, target.cell_id))
        conn.execute("DELETE FROM memories WHERE memory_id=?", (target_id,))
        conn.commit()


def _persistent_non_target_state(engine) -> dict:
    return {
        memory.memory_id: {
            "state": memory.state.name,
            "last_activation": memory.last_activation,
            "recall_count": memory.recall_count,
            "synaptic_links": dict(sorted(memory.synaptic_links.items())),
        }
        for memory in sorted(engine._db.load_memories(), key=lambda item: item.memory_id)
    }


def _post_deletion_branch(db_path: Path, history: str) -> dict:
    engine = _load_seed_engine(db_path)
    target = engine._db.load_memory(TARGET)
    now = 1001.0
    if history == "A_participated":
        outcome = _core(engine, "B", now, [TARGET])
    elif history == "A_suppressed":
        outcome = _influence_excluded_core(
            engine, "B", now, [TARGET], target.cell_id,
        )
    else:
        raise ValueError(f"unknown history: {history}")

    ranked = _ranked_ids(outcome)
    previous = [TARGET] if history == "A_participated" else []
    if previous:
        engine._update_stdp(previous, ranked)
    engine._db.update_activations(ranked, now)

    _erase_target_and_incident_links(engine, TARGET)
    engine = _load_seed_engine(db_path)
    if TARGET in {memory.memory_id for memory in engine._db.load_memories()}:
        raise AssertionError("operational erasure left target row in the database")
    checkpoints = []
    for step, query_key in enumerate(POST_QUERIES, start=1):
        now = 1001.0 + step
        engine._ensure_kdtree()
        post = _core(engine, query_key, now, ["B"])
        engine._update_stdp(["B"], _ranked_ids(post))
        engine._db.update_activations(_ranked_ids(post), now)
        state = _persistent_non_target_state(engine)
        # A read-only repeated evaluation at the same time yields the recorded
        # output without introducing additional activation or learning writes.
        measured = _core(engine, query_key, now, ["B"])
        yield_checkpoint = {
            "step": step,
            "query": query_key,
            "ranked_ids": _ranked_ids(measured),
            "scores": _score_vector(measured),
            "state": state,
            "state_sha256": hashlib.sha256(json.dumps(
                state, sort_keys=True, separators=(",", ":")
            ).encode()).hexdigest(),
        }
        checkpoints.append(yield_checkpoint)
    return {
        "history": history,
        "post_deletion_checkpoints": checkpoints,
        "final_state": _persistent_non_target_state(engine),
        "final_database_digest": _canonical_database_digest(db_path),
        "a_row_absent": TARGET not in {
            memory.memory_id for memory in engine._db.load_memories()
        },
        "a_incident_synaptic_links_absent": all(
            TARGET not in memory.synaptic_links
            for memory in engine._db.load_memories()
        ),
        "a_incident_cell_links_absent": all(
            src != target.cell_id and dst != target.cell_id
            for src, dst, _ in engine._db.load_all_cell_links()
        ),
    }


def run_experiment() -> dict:
    with tempfile.TemporaryDirectory(prefix="exp52-raven-") as work:
        root = Path(work)
        seed_path = root / "seed.sqlite"
        seed_engine, _ = build_seed_engine(seed_path)
        seed_engine._ensure_kdtree()
        seed_digest = _canonical_database_digest(seed_path)
        contracts = _suppression_contracts(seed_engine)

        histories = {}
        for name in ("A_participated", "A_suppressed"):
            branch = root / f"{name}.sqlite"
            with sqlite3.connect(seed_path) as source, sqlite3.connect(branch) as target:
                source.backup(target)
            histories[name] = _post_deletion_branch(branch, name)

    controls = histories["A_suppressed"]["post_deletion_checkpoints"]
    exposed = histories["A_participated"]["post_deletion_checkpoints"]
    histories["exact_observational_equivalence_each_checkpoint"] = [
        exposed[i]["scores"] == controls[i]["scores"]
        and exposed[i]["ranked_ids"] == controls[i]["ranked_ids"]
        for i in range(len(POST_QUERIES))
    ]
    histories["exact_persistent_state_equivalence_each_checkpoint"] = [
        exposed[i]["state"] == controls[i]["state"]
        for i in range(len(POST_QUERIES))
    ]
    return {
        "experiment": "Exp52",
        "title": "Raven Suppression Semantics and Causal Isolation",
        "source_commit": "56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f",
        "exp51_seed_sha256": seed_digest,
        "backend": "exact scipy KDTree",
        "contracts": contracts,
        "paired_history": histories,
        "interpretation_limits": [
            "one copied source snapshot",
            "one synthetic four-memory field",
            "one pre-deletion experience and four fixed post-deletion queries",
            "retrieval and stored state only; no downstream agent behavior",
            "operational deletion does not prove universal historical erasure",
        ],
    }


def main() -> None:
    result = run_experiment()
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path = ROOT / "exp52_raven_suppression_semantics_run.json"
    path.write_text(encoded, encoding="utf-8")
    print(f"wrote {path.name} sha256={hashlib.sha256(encoded.encode()).hexdigest()}")
    print(json.dumps({
        "result_exclusion": result["contracts"]["result_exclusion"],
        "influence_policy_matches_control": result["contracts"][
            "influence_policy_matches_negative_control"
        ],
        "raw_source_differs_from_control": result["contracts"][
            "raw_source_differs_from_negative_control"
        ],
        "historical_observational_equivalence": result["paired_history"][
            "exact_observational_equivalence_each_checkpoint"
        ],
        "historical_state_equivalence": result["paired_history"][
            "exact_persistent_state_equivalence_each_checkpoint"
        ],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
