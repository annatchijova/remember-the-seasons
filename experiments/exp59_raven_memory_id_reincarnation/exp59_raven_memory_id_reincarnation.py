"""Exp59: test whether old audit counts attach to a reissued memory ID."""
from __future__ import annotations

import copy
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
from exp53_raven_latent_trace import _clone_database, _load_seed_engine  # noqa: E402
from vendor.raven import MemoryState  # noqa: E402

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent
NOW = 2000.0
THRESHOLD = 0.90
NEW_IDS = {"C": "C_reborn", "D": "D_reborn"}


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _current_state(path: Path) -> dict:
    def encode(value):
        return {"blob_hex": value.hex()} if isinstance(value, bytes) else value

    with sqlite3.connect(path) as conn:
        memory_rows = conn.execute("SELECT * FROM memories ORDER BY memory_id").fetchall()
        memory_columns = [r[1] for r in conn.execute("PRAGMA table_info(memories)")]
        links = conn.execute(
            "SELECT * FROM cell_links ORDER BY from_cell_id,to_cell_id,link_type"
        ).fetchall()
        link_columns = [r[1] for r in conn.execute("PRAGMA table_info(cell_links)")]
    return {
        "memories": {"columns": memory_columns,
                     "rows": [[encode(v) for v in row] for row in memory_rows]},
        "cell_links": {"columns": link_columns,
                       "rows": [[encode(v) for v in row] for row in links]},
    }


def _prepare_base(root: Path, name: str) -> Path:
    seed = root / f"{name}_seed.sqlite"
    _create_fixture(seed)
    path = root / f"{name}.sqlite"
    _clone_database(seed, path)
    return path


def _recall_history(path: Path, counts: dict[str, int]) -> None:
    engine = _load_seed_engine(path)
    for memory_id in ("C", "D"):
        for _ in range(counts[memory_id]):
            with patch.object(sleep_consolidator.time, "time", return_value=NOW):
                results, _audit = engine.recall(
                    query_embedding=_vectors()[memory_id],
                    query_text=f"Exp59 pre-reissue recall {memory_id}",
                    top_k=1,
                    hops=0,
                    layer_filter="episodic",
                    current_turn_memories=None,
                )
            ids = [row.memory.memory_id for row in results]
            if ids != [memory_id]:
                raise AssertionError(f"Expected {[memory_id]}, got {ids}")
    actual = _audit_counts(path, ["C", "D"])
    if actual != counts:
        raise AssertionError(f"Generated counts {actual}, expected {counts}")


def _reissued_entry(path: Path, original_id: str, new_id: str | None = None):
    engine = _load_seed_engine(path)
    entry = next(m for m in engine.list_memories() if m.memory_id == original_id)
    entry = copy.deepcopy(entry)
    entry.memory_id = new_id or original_id
    entry.content = f"Exp59 reincarnated content for {original_id}"
    entry.content_hash = hashlib.sha256(entry.content.encode()).hexdigest()
    entry.layer = "episodic"
    entry.state = MemoryState.NEUTRAL
    entry.last_activation = 0.0
    entry.recall_count = 0
    entry.synaptic_links = {}
    entry.metadata = {"incarnation": "Exp59-1"}
    return entry


def _replace_memories(path: Path, *, fresh_ids: bool) -> dict[str, str]:
    before = {mid: _reissued_entry(path, mid, NEW_IDS[mid] if fresh_ids else None)
              for mid in ("C", "D")}
    engine = _load_seed_engine(path)
    if fresh_ids:
        cell_ids = [before[mid].cell_id for mid in ("C", "D")]
        with sqlite3.connect(path) as conn:
            placeholders = ",".join("?" for _ in cell_ids)
            conn.execute(
                f"DELETE FROM cell_links WHERE from_cell_id IN ({placeholders}) "
                f"OR to_cell_id IN ({placeholders})", cell_ids + cell_ids,
            )
            conn.execute("DELETE FROM memories WHERE memory_id IN ('C','D')")
            conn.commit()
    for entry in before.values():
        engine._db.store_memory(entry)
    hashes = {entry.memory_id: entry.content_hash for entry in before.values()}
    expected_ids = list(NEW_IDS.values()) if fresh_ids else ["C", "D"]
    if _groups(path) != [sorted(expected_ids)]:
        raise AssertionError(f"Replacement fixture merge group was {_groups(path)}")
    return hashes


def _historical_hashes(path: Path, ids: list[str]) -> dict[str, list[str]]:
    found = {mid: set() for mid in ids}
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            "SELECT memories_retrieved FROM audit_log WHERE operation='recall'"
        ).fetchall()
    for (raw,) in rows:
        for item in json.loads(raw or "[]"):
            memory_id = item.get("memory_id")
            if memory_id in found:
                found[memory_id].add(item.get("content_hash", ""))
    return {mid: sorted(values) for mid, values in found.items()}


def _audit_digest(path: Path) -> str:
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
        columns = [r[1] for r in conn.execute("PRAGMA table_info(audit_log)")]
    return _digest({"columns": columns, "rows": rows})


def _consolidate(path: Path, memory_ids: list[str]) -> dict:
    counts = sleep_consolidator.get_recall_counts(path, memory_ids)
    with patch.object(sleep_consolidator.time, "time", return_value=NOW):
        run = sleep_consolidator.run_consolidation(
            path, threshold=THRESHOLD, dry_run=False, rebuild_spectral=False,
        )
    engine = _load_seed_engine(path)
    nodes = [mem for mem in engine.list_memories() if mem.memory_id.startswith("cons_")]
    target_nodes = [node for node in nodes
                    if sorted(node.metadata.get("consolidated_from", [])) == sorted(memory_ids)]
    if len(target_nodes) != 1:
        raise AssertionError(f"Expected one node from {memory_ids}, found {len(target_nodes)}")
    node = target_nodes[0]
    return {
        "run": run,
        "counts": counts,
        "merged_node_id": node.memory_id,
        "sources": sorted(node.metadata["consolidated_from"]),
        "merge_metadata": node.metadata,
        "embedding_hex": node.embedding.astype(np.float32).tobytes().hex(),
        "embedding": node.embedding.astype(np.float64).tolist(),
    }


def _directional_result(c54: dict, c45: dict) -> dict:
    c_vec = _vectors()["C"]
    d_vec = _vectors()["D"]
    c54_vec = np.asarray(c54["embedding"], dtype=np.float64)
    c45_vec = np.asarray(c45["embedding"], dtype=np.float64)
    return {
        "different_embeddings": c54["embedding_hex"] != c45["embedding_hex"],
        "C_similarity_R54_greater": float(np.dot(c_vec, c54_vec)) > float(np.dot(c_vec, c45_vec)),
        "D_similarity_R54_lower": float(np.dot(d_vec, c54_vec)) < float(np.dot(d_vec, c45_vec)),
    }


def _historical_id_assay(root: Path, *, fresh_ids: bool) -> dict:
    counts_by_branch = {"R54": {"C": 5, "D": 4}, "R45": {"C": 4, "D": 5}}
    paths, new_hashes, old_hashes = {}, {}, {}
    for branch, counts in counts_by_branch.items():
        path = _prepare_base(root, f"{branch}_{'fresh' if fresh_ids else 'same'}")
        _recall_history(path, counts)
        ids = [NEW_IDS[mid] for mid in ("C", "D")] if fresh_ids else ["C", "D"]
        old_hashes[branch] = _historical_hashes(path, ["C", "D"])
        new_hashes[branch] = _replace_memories(path, fresh_ids=fresh_ids)
        paths[branch] = path
        expected = counts if not fresh_ids else {ids[0]: 0, ids[1]: 0}
        actual = _audit_counts(path, ids)
        if actual != expected:
            raise AssertionError(f"Unexpected reissued-ID counts in {branch}")

    current_states_equal = _current_state(paths["R54"]) == _current_state(paths["R45"])
    if not current_states_equal:
        raise AssertionError("Current state differs before consolidation")
    if fresh_ids:
        ids = [NEW_IDS[mid] for mid in ("C", "D")]
    else:
        ids = ["C", "D"]
    merged = {branch: _consolidate(path, ids) for branch, path in paths.items()}
    result = {
        "fresh_id_control": fresh_ids,
        "current_state_equal_before_consolidation": current_states_equal,
        "audit_histories_distinct_before_consolidation": (
            _audit_digest(paths["R54"]) != _audit_digest(paths["R45"])
        ),
        "historical_content_hashes": old_hashes,
        "current_content_hashes": new_hashes,
        "branches": merged,
    }
    if fresh_ids:
        result["fresh_id_outputs_equal"] = (
            merged["R54"]["counts"] == merged["R45"]["counts"]
            and merged["R54"]["embedding_hex"] == merged["R45"]["embedding_hex"]
        )
    else:
        result["same_id_directional_effect"] = _directional_result(merged["R54"], merged["R45"])
    return result


def _content_hash_mutation(root: Path) -> dict:
    paths = {}
    for branch, counts in (("R54", {"C": 5, "D": 4}), ("R45", {"C": 4, "D": 5})):
        path = _prepare_base(root, f"mut_{branch}")
        _recall_history(path, counts)
        _replace_memories(path, fresh_ids=False)
        paths[branch] = path

    original_reader = sleep_consolidator.get_recall_counts

    def generation_aware_reader(path: Path, memory_ids: list[str]) -> dict[str, int]:
        current = {}
        with sqlite3.connect(path) as conn:
            current.update(conn.execute(
                f"SELECT memory_id,content_hash FROM memories WHERE memory_id IN "
                f"({','.join('?' for _ in memory_ids)})", memory_ids,
            ).fetchall())
            current = dict(current)
            rows = conn.execute(
                "SELECT memories_retrieved FROM audit_log WHERE operation='recall'"
            ).fetchall()
        counts = {mid: 0 for mid in memory_ids}
        for (raw,) in rows:
            for item in json.loads(raw or "[]"):
                mid = item.get("memory_id")
                if mid in counts and item.get("content_hash") == current.get(mid):
                    counts[mid] += 1
        return counts

    with patch.object(sleep_consolidator, "get_recall_counts", side_effect=generation_aware_reader):
        mutated = {branch: _consolidate(path, ["C", "D"])
                   for branch, path in paths.items()}
    return {
        "mutation": "ignore audit recalls whose content hash differs from the current row",
        "mutation_counts": {branch: value["counts"] for branch, value in mutated.items()},
        "mutated_embeddings_equal": mutated["R54"]["embedding_hex"] == mutated["R45"]["embedding_hex"],
    }


def run_experiment() -> dict:
    source_hashes = _source_hashes()
    with tempfile.TemporaryDirectory(prefix="exp59-raven-") as temp:
        root = Path(temp)
        same_id = _historical_id_assay(root, fresh_ids=False)
        fresh_id = _historical_id_assay(root, fresh_ids=True)
        mutation = _content_hash_mutation(root)
    require = (
        same_id["current_state_equal_before_consolidation"],
        same_id["audit_histories_distinct_before_consolidation"],
        all(same_id["same_id_directional_effect"].values()),
        fresh_id["current_state_equal_before_consolidation"],
        fresh_id["audit_histories_distinct_before_consolidation"],
        fresh_id["fresh_id_outputs_equal"],
        mutation["mutated_embeddings_equal"],
    )
    if not all(require):
        raise AssertionError(f"Exp59 preregistered checks failed: {require}")
    return {
        "experiment": "Exp59",
        "title": "Recall History Across Memory-ID Reuse",
        "status": "runtime assay",
        "source_commit": SOURCE_COMMIT,
        "source_copy_hashes": source_hashes,
        "parameters": {"threshold": THRESHOLD, "fixed_time": NOW, "total_prior_recalls": 9},
        "epistemic_scope": "copied Raven snapshot and synthetic Exp51 fixture",
        "same_id_reincarnation": same_id,
        "fresh_id_control": fresh_id,
        "content_hash_mutation_control": mutation,
        "limitations": [
            "one pinned snapshot and four-memory synthetic fixture",
            "memory rows replaced through the copied store layer with same or fresh IDs",
            "only audit-derived consolidation weights and merged embeddings measured",
            "does not establish deployed-service exploitability or downstream agent effects",
        ],
    }


def main() -> None:
    result = run_experiment()
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    output = ROOT / "exp59_raven_memory_id_reincarnation_run.json"
    output.write_text(encoded, encoding="utf-8")
    print(f"wrote {output.name} sha256={hashlib.sha256(encoded.encode()).hexdigest()}")
    print(json.dumps({
        "same_id_effect": result["same_id_reincarnation"]["same_id_directional_effect"],
        "fresh_id_control_equal": result["fresh_id_control"]["fresh_id_outputs_equal"],
        "content_hash_mutation_equal": result["content_hash_mutation_control"]["mutated_embeddings_equal"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
