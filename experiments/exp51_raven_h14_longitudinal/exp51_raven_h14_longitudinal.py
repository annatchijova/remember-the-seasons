"""Exp51: isolated longitudinal Raven restoration pilot.

The copied Raven scoring and STDP implementation is the system under study.
This module supplies only the fixture, controlled clock, branch policy, and
canonical result serializer; it is not a Raven feature or product adapter.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path

os.environ["RAVEN_ANN_BACKEND"] = "kdtree"

from vendor.raven.memory_engine import (
    AdaptiveMemoryEngine,
    LinkType,
    MemoryEntry,
    MemoryState,
    MemoryStore,
)
import numpy as np


ROOT = Path(__file__).resolve().parent
DIM = 8
TOP_K = 4
HOPS = 2
ABSENCE_STEPS = {1, 2, 3, 4}
POST_STEPS = {5, 6, 7, 8}
WASHOUT_STEPS = {9, 10, 11, 12, 13}
SCHEDULE = ("A", "B", "A", "C", "B", "A", "D", "B", "C", "D", "A", "C", "B")
ARM_NAMES = (
    "no_absence", "reexposure", "strict_local_restore", "links_only_restore",
    "complete_local_restore", "relearning",
)


def _vectors() -> dict[str, np.ndarray]:
    return {
        "A": np.array([1.0, 0.0, 0, 0, 0, 0, 0, 0], dtype=np.float64),
        "B": np.array([0.9, 0.1, 0, 0, 0, 0, 0, 0], dtype=np.float64),
        "C": np.array([0.4, 0.916515138991168, 0, 0, 0, 0, 0, 0], dtype=np.float64),
        "D": np.array([0.0, 1.0, 0, 0, 0, 0, 0, 0], dtype=np.float64),
    }


def _entry(memory_id: str, cell_id: int, embedding: np.ndarray,
           state: MemoryState = MemoryState.NEUTRAL) -> MemoryEntry:
    return MemoryEntry(
        memory_id=memory_id,
        layer="semantic",
        content=f"Synthetic fixture memory {memory_id}",
        content_hash=hashlib.sha256(memory_id.encode()).hexdigest(),
        embedding=embedding.copy(),
        state=state,
        cell_id=cell_id,
        created_at=1000.0,
        session_id="exp51-synthetic",
        author_id="fixture",
        metadata={"fixture": "synthetic"},
        synaptic_links={},
        last_activation=0.0,
        recall_count=0,
        fingerprint=None,
    )


def build_seed_engine(db_path: Path) -> tuple[AdaptiveMemoryEngine, dict[str, str]]:
    """Create the same deterministic, synthetic Raven field for every arm."""
    store = MemoryStore(db_path)
    ids = {name: name for name in ("A", "B", "C", "D")}
    entries = (
        _entry("A", 0, _vectors()["A"], MemoryState.REINFORCED),
        _entry("B", 1, _vectors()["B"]),
        _entry("C", 2, _vectors()["C"]),
        _entry("D", 3, _vectors()["D"]),
    )
    for entry in entries:
        store.store_memory(entry)
    # These associations are explicit fixture state, not learned data.
    store.update_synaptic_links("A", {"B": 0.8, "C": 0.6})
    store.update_synaptic_links("B", {"A": 0.8, "C": 0.7})
    store.update_synaptic_links("C", {"D": 0.8, "A": 0.3})
    with store._connect() as conn:
        conn.executemany(
            "INSERT INTO cell_links (from_cell_id,to_cell_id,link_type,created_at,auto_generated) "
            "VALUES (?,?,?,?,?)",
            [(0, 2, "RESONANT", 1000.0, 0), (2, 3, "RESONANT", 1000.0, 0)],
        )
        conn.commit()
    engine = AdaptiveMemoryEngine(embedding_dim=DIM, k_neighbors=0, db_path=db_path)
    if engine._ann_backend != "kdtree":
        raise RuntimeError(f"Expected exact KDTree, got {engine._ann_backend}")
    return engine, ids


def _load_seed_engine(db_path: Path) -> AdaptiveMemoryEngine:
    engine = AdaptiveMemoryEngine(embedding_dim=DIM, k_neighbors=0, db_path=db_path)
    if engine._ann_backend != "kdtree":
        raise RuntimeError(f"Expected exact KDTree, got {engine._ann_backend}")
    return engine


def _canonical_database_digest(db_path: Path) -> str:
    with sqlite3.connect(db_path) as conn:
        memories = conn.execute(
            "SELECT memory_id,layer,content,content_hash,hex(embedding),state,cell_id,created_at,"
            "session_id,author_id,metadata,synaptic_links,last_activation,recall_count "
            "FROM memories ORDER BY cell_id"
        ).fetchall()
        links = conn.execute(
            "SELECT from_cell_id,to_cell_id,link_type,created_at,auto_generated "
            "FROM cell_links ORDER BY from_cell_id,to_cell_id"
        ).fetchall()
    canonical = json.dumps({"memories": memories, "cell_links": links},
                           separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _score_rows(outcome) -> list[dict]:
    return [
        {
            "memory_id": row.memory.memory_id,
            "score": row.final_score,
            "base_score": row.base_score,
            "state_boost": row.state_boost,
            "hop_decay": row.hop_decay,
            "synaptic_boost": row.synaptic_boost,
            "recency_bonus": row.recency_bonus,
            "hop_distance": row.hop_distance,
            "source": row.source,
        }
        for row in outcome.scored
    ]


def _ranked_ids(outcome) -> list[str]:
    return [row.memory.memory_id for row in outcome.top]


def _core(engine: AdaptiveMemoryEngine, query_key: str, now: float,
          current_turn_memories: list[str], suppressed: frozenset[int] = frozenset()):
    engine._ensure_kdtree()
    # Raven's raw core currently allows a suppressed cell to act as a source
    # through current_turn_memories. The adapter closes that separate entry path.
    silenced_ids = {engine._cell_to_memid[cell] for cell in suppressed
                    if cell in engine._cell_to_memid}
    current_turn_memories = [mid for mid in current_turn_memories
                             if mid not in silenced_ids]
    return engine._recall_core(
        _vectors()[query_key], now=now,
        top_k=TOP_K, hops=HOPS,
        current_turn_memories=current_turn_memories,
        suppressed=suppressed,
    )


def _persist_recall_effects(engine: AdaptiveMemoryEngine, outcome, previous: list[str],
                            now: float, excluded_ids: set[str]) -> None:
    """Apply Raven recall's STDP and activation writes under the branch policy."""
    current = [mid for mid in _ranked_ids(outcome) if mid not in excluded_ids]
    previous = [mid for mid in previous if mid not in excluded_ids]
    if previous:
        engine._update_stdp(previous, current)
    engine._db.update_activations(current, now)


def run_absence_step(engine: AdaptiveMemoryEngine, target_id: str,
                     previous_id: str, query_key: str, now: float,
                     mutation_bypass_suppression: bool = False) -> dict:
    """One declared absence transition, exposed for direct invariant tests."""
    target = engine._db.load_memory(target_id)
    suppressed = frozenset() if mutation_bypass_suppression else frozenset({target.cell_id})
    outcome = _core(engine, query_key, now, [previous_id], suppressed=suppressed)
    _persist_recall_effects(engine, outcome, [previous_id], now, {target_id})
    return {"ranked_ids": _ranked_ids(outcome), "scores": _score_rows(outcome)}


def _state(engine: AdaptiveMemoryEngine, target_id: str) -> dict:
    target = engine._db.load_memory(target_id)
    incident_synaptic = {}
    for mem in engine._db.load_memories():
        if mem.memory_id == target_id or target_id in mem.synaptic_links:
            incident_synaptic[mem.memory_id] = dict(sorted(mem.synaptic_links.items()))
    links = [
        [src, dst, kind]
        for src, dst, kind in engine._db.load_all_cell_links()
        if src == target.cell_id or dst == target.cell_id
    ]
    return {
        "state": target.state.name,
        "last_activation": target.last_activation,
        "recall_count": target.recall_count,
        "target_synaptic_links": dict(sorted(target.synaptic_links.items())),
        "incident_synaptic_links": incident_synaptic,
        "incident_cell_links": sorted(links),
    }


def _capture_target(engine: AdaptiveMemoryEngine, target_id: str) -> dict:
    mem = engine._db.load_memory(target_id)
    return {
        "state": mem.state.name,
        "last_activation": mem.last_activation,
        "recall_count": mem.recall_count,
        "synaptic_links": dict(mem.synaptic_links),
    }


def _capture_incident_links(engine: AdaptiveMemoryEngine, target_id: str) -> dict:
    target = engine._db.load_memory(target_id)
    synaptic = {}
    for mem in engine._db.load_memories():
        if mem.memory_id == target_id or target_id in mem.synaptic_links:
            synaptic[mem.memory_id] = dict(mem.synaptic_links)
    cell = [row for row in engine._db.load_all_cell_links()
            if row[0] == target.cell_id or row[1] == target.cell_id]
    return {"synaptic": synaptic, "cell": cell}


def _restore_target_row(engine: AdaptiveMemoryEngine, target_id: str,
                        snapshot: dict, include_links: bool) -> None:
    links_sql = ", synaptic_links=?" if include_links else ""
    values = [snapshot["state"], snapshot["last_activation"], snapshot["recall_count"]]
    if include_links:
        values.append(json.dumps(snapshot["synaptic_links"], sort_keys=True))
    values.append(target_id)
    with engine._db._connect() as conn:
        conn.execute(
            "UPDATE memories SET state=?, last_activation=?, recall_count=?" +
            links_sql + " WHERE memory_id=?", values,
        )
        conn.commit()
    engine._load_from_db()


def _restore_incident_links(engine: AdaptiveMemoryEngine, target_id: str,
                            snapshot: dict) -> None:
    target = engine._db.load_memory(target_id)
    for mem_id, links in snapshot["synaptic"].items():
        current = engine._db.load_memory(mem_id)
        updated = dict(current.synaptic_links)
        if mem_id == target_id:
            updated = dict(links)
        else:
            if target_id in links:
                updated[target_id] = links[target_id]
            else:
                updated.pop(target_id, None)
        engine._db.update_synaptic_links(mem_id, updated)
    with engine._db._connect() as conn:
        conn.execute("DELETE FROM cell_links WHERE from_cell_id=? OR to_cell_id=?",
                     (target.cell_id, target.cell_id))
        for src, dst, kind in snapshot["cell"]:
            conn.execute(
                "INSERT INTO cell_links (from_cell_id,to_cell_id,link_type,created_at,auto_generated) "
                "VALUES (?,?,?,?,?)", (src, dst, kind, 1000.0, 0),
            )
        conn.commit()
    engine._load_from_db()


def _neutralize_for_reexposure(engine: AdaptiveMemoryEngine, target_id: str) -> None:
    mem = engine._db.load_memory(target_id)
    engine._db.update_state(target_id, MemoryState.NEUTRAL)
    with engine._db._connect() as conn:
        conn.execute("UPDATE memories SET last_activation=0.0, recall_count=0 WHERE memory_id=?",
                     (target_id,))
        conn.execute("DELETE FROM cell_links WHERE from_cell_id=? OR to_cell_id=?",
                     (mem.cell_id, mem.cell_id))
        conn.commit()
    for row in engine._db.load_memories():
        links = dict(row.synaptic_links)
        if row.memory_id == target_id:
            links.clear()
        else:
            links.pop(target_id, None)
        if links != row.synaptic_links:
            engine._db.update_synaptic_links(row.memory_id, links)
    engine._load_from_db()


def _probe(engine: AdaptiveMemoryEngine, target_id: str, query_key: str,
           now: float, previous: list[str]) -> dict:
    target = engine._db.load_memory(target_id)
    full = _core(engine, query_key, now, previous)
    suppressed = _core(engine, query_key, now, previous,
                       suppressed=frozenset({target.cell_id}))
    full_scores = {r.memory.memory_id: r.final_score for r in full.scored}
    suppressed_scores = {r.memory.memory_id: r.final_score for r in suppressed.scored}
    ids = sorted(set(full_scores) | set(suppressed_scores))
    indirect = {mid: full_scores.get(mid, 0.0) - suppressed_scores.get(mid, 0.0)
                for mid in ids if mid != target_id}
    return {
        "ranked_ids": _ranked_ids(full),
        "activated_ids": sorted(engine._cell_to_memid[cell]
                                 for cell in full.activated_cells
                                 if cell in engine._cell_to_memid),
        "scores": _score_rows(full),
        "target_direct_score": full_scores.get(target_id, 0.0),
        "target_indirect_score_effect_by_memory": indirect,
        "target_indirect_score_effect_sum": sum(indirect.values()),
        "target_active_in_experience": target.cell_id in full.activated_cells,
    }


def _raw_suppression_leak(engine: AdaptiveMemoryEngine, target_id: str,
                          query_key: str, now: float) -> dict:
    target = engine._db.load_memory(target_id)
    raw = engine._recall_core(
        _vectors()[query_key], now=now,
        top_k=TOP_K, hops=HOPS, current_turn_memories=[target_id],
        suppressed=frozenset({target.cell_id}),
    )
    adapted = _core(engine, query_key, now, [target_id],
                    suppressed=frozenset({target.cell_id}))
    return {
        "raw_core_current_turn_source_ids": _ranked_ids(raw),
        "adapted_current_turn_source_ids": _ranked_ids(adapted),
        "raw_core_emits_linked_C": any(r.memory.memory_id == "C" and r.source == "synaptic"
                                       for r in raw.scored),
        "adapted_emits_linked_C": any(r.memory.memory_id == "C" and r.source == "synaptic"
                                      for r in adapted.scored),
    }


def _run_arm(arm: str, db_path: Path) -> dict:
    engine = _load_seed_engine(db_path)
    target_id = "A"
    target_cell = engine._db.load_memory(target_id).cell_id
    target_snapshot = _capture_target(engine, target_id)
    link_snapshot = _capture_incident_links(engine, target_id)
    prior: list[str] = []
    checkpoints = []
    branch_non_target_before = {
        m.memory_id: (m.state.name, m.last_activation, m.recall_count,
                      dict(m.synaptic_links))
        for m in engine._db.load_memories() if m.memory_id != target_id
    }

    for step_number, query_key in enumerate(SCHEDULE, start=1):
        absent = ((step_number in ABSENCE_STEPS or
                   (arm == "relearning" and step_number == 5))
                  and arm != "no_absence")
        if step_number == 5:
            if arm == "reexposure":
                _neutralize_for_reexposure(engine, target_id)
            elif arm == "strict_local_restore":
                _restore_target_row(engine, target_id, target_snapshot, include_links=False)
            elif arm == "links_only_restore":
                # Keep the current intrinsic row; restore only links incident to A.
                _restore_incident_links(engine, target_id, link_snapshot)
            elif arm == "complete_local_restore":
                _restore_target_row(engine, target_id, target_snapshot, include_links=False)
                _restore_incident_links(engine, target_id, link_snapshot)
        if step_number == 6 and arm == "relearning":
            _neutralize_for_reexposure(engine, target_id)

        suppressed = frozenset({target_cell}) if absent else frozenset()
        outcome = _core(engine, query_key, 1000.0 + step_number, prior, suppressed)
        excluded = {target_id} if absent else set()
        _persist_recall_effects(engine, outcome, prior, 1000.0 + step_number, excluded)
        prior = _ranked_ids(outcome)
        if absent:
            prior = [mid for mid in prior if mid != target_id]

        if step_number in POST_STEPS or step_number in WASHOUT_STEPS:
            probe = _probe(engine, target_id, query_key, 1000.0 + step_number, prior)
            propagation = _core(
                engine, "A", 1000.0 + step_number, [],
                suppressed=frozenset({target_cell}) if absent else frozenset(),
            )
            state = _state(engine, target_id)
            non_target = {
                m.memory_id: (m.state.name, m.last_activation, m.recall_count,
                              dict(m.synaptic_links))
                for m in engine._db.load_memories() if m.memory_id != target_id
            }
            checkpoints.append({
                "step": step_number,
                "phase": "post_window" if step_number in POST_STEPS else "washout",
                "query": query_key,
                "retrieval": probe,
                "standardized_propagation": {
                    "query": "A",
                    "target_suppressed": absent,
                    "activated_ids": sorted(
                        engine._cell_to_memid[cell]
                        for cell in propagation.activated_cells
                        if cell in engine._cell_to_memid
                    ),
                    "reaches_C": engine._db.load_memory("C").cell_id
                    in propagation.activated_cells,
                    "reaches_D": engine._db.load_memory("D").cell_id
                    in propagation.activated_cells,
                },
                "state": state,
                "non_target_state_digest": hashlib.sha256(
                    json.dumps(non_target, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
            })

    final_non_target = {
        m.memory_id: (m.state.name, m.last_activation, m.recall_count,
                      dict(m.synaptic_links))
        for m in engine._db.load_memories() if m.memory_id != target_id
    }
    return {
        "checkpoints": checkpoints,
        "final_non_target_state": final_non_target,
        "non_target_state_changed_from_seed": final_non_target != branch_non_target_before,
    }


def run_experiment() -> dict:
    with tempfile.TemporaryDirectory(prefix="exp51-raven-") as work:
        base = Path(work)
        seed_path = base / "seed.sqlite"
        seed_engine, _ = build_seed_engine(seed_path)
        seed_engine._ensure_kdtree()
        seed_digest = _canonical_database_digest(seed_path)
        arms = {}
        for arm in ARM_NAMES:
            branch_path = base / f"{arm}.sqlite"
            with sqlite3.connect(seed_path) as source, sqlite3.connect(branch_path) as target:
                source.backup(target)
            arms[arm] = _run_arm(arm, branch_path)
        source_leak = _raw_suppression_leak(seed_engine, "A", "B", 1001.0)
    result = {
        "experiment": "Exp51",
        "title": "Raven Longitudinal Restoration Pilot",
        "source_commit": "56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f",
        "backend": "exact scipy KDTree",
        "neighbor_graph": "disabled with k_neighbors=0; only declared cell links propagate",
        "embedding_dimension": DIM,
        "clock": "fixed now=1000+step for scoring; fixture timestamps=1000",
        "query_schedule": list(SCHEDULE),
        "vectors": {key: vector.tolist() for key, vector in _vectors().items()},
        "seed_snapshot_sha256": seed_digest,
        "absence_steps": sorted(ABSENCE_STEPS),
        "post_window_steps": sorted(POST_STEPS),
        "washout_steps": sorted(WASHOUT_STEPS),
        "raw_raven_suppression_probe": source_leak,
        "arms": arms,
        "interpretation": {
            "retrieval_only": True,
            "downstream_agent_behavior_measured": False,
            "evidence_scope": "one synthetic field and one deterministic schedule",
        },
    }
    return result


def main() -> None:
    result = run_experiment()
    path = ROOT / "exp51_raven_h14_run.json"
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.write_text(encoded, encoding="utf-8")
    print(f"wrote {path.name} sha256={hashlib.sha256(encoded.encode()).hexdigest()}")
    print(json.dumps({
        name: [checkpoint["retrieval"]["target_indirect_score_effect_sum"]
               for checkpoint in arm["checkpoints"]]
        for name, arm in result["arms"].items()
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
