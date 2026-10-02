"""
Minimal raven-faithful engine for the three discriminating experiments.

Faithful to sources/raven-memory/raven/memory_engine.py at commit 56df6cf.
Constants, scoring formula, BFS, rescue, and k-NN symmetrization are lifted
directly from the source. No SQLite, no audit chain, no stylometry, no
spectral field, no STDP cross-turn pull — only the mechanisms under test.

Constants (OBSERVED, memory_engine.py:89-118):
    K_NEIGHBORS = 6, HOP_LAMBDA = 0.15, RESONANT_BOOST = 0.5,
    SYNAPTIC_SCORE_WEIGHT = 0.3, RECENCY_HALFLIFE = 86400.0,
    RECENCY_WEIGHT = 0.05, REINFORCED = 1.5, NEUTRAL = 1.0, FORGOTTEN = 0.0

Scoring (memory_engine.py:1825-1831):
    final = sim * state_boost * hop_decay + resonant_contribution
            + synaptic_boost * 0.3 + recency_bonus
    final = max(0.0, final)

BFS (memory_engine.py:1682-1714): seed → frontier expansion through k-NN
graph + explicit links. INHIBITORY → inhibited_cells. RESONANT → frontier +
boost. Suppressed/inhibited cells are skipped (links not traversed).

Rescue (memory_engine.py:1718-1730): after BFS, REINFORCED cells in
inhibited_cells are moved to activated_cells. Runs AFTER BFS, so the
rescued cell re-enters scoring but NOT propagation.

k-NN graph (memory_engine.py:1487-1494): symmetrized —
    cell_neighbors[n_cell].add(cell_id)

Sort (memory_engine.py:1904): key=(-final_score, memory_id) — deterministic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
from scipy.spatial import KDTree

# ---- Constants (OBSERVED from memory_engine.py:89-118, 126) ----
K_NEIGHBORS = 6
HOP_LAMBDA = 0.15
RESONANT_BOOST = 0.5
SYNAPTIC_SCORE_WEIGHT = 0.3
RECENCY_HALFLIFE = 86400.0
RECENCY_WEIGHT = 0.05


class State(Enum):
    REINFORCED = 1.5
    NEUTRAL = 1.0
    FORGOTTEN = 0.0


RESONANT = 1
NEUTRAL_LINK = 0
INHIBITORY = -1


@dataclass
class Memory:
    memory_id: str
    cell_id: int
    embedding: np.ndarray
    state: State = State.NEUTRAL
    topic: str = ""
    claim: str = ""
    last_activation: float = 0.0
    # explicit links: {target_cell_id: link_type}
    links: Dict[int, int] = field(default_factory=dict)
    # STDP synaptic links: {target_memory_id: weight}
    synaptic_links: Dict[str, float] = field(default_factory=dict)


@dataclass
class RecallResult:
    memory: Memory
    final_score: float
    hop_distance: int
    source: str  # "similarity" or "propagation" or "rescued"


@dataclass
class RecallOutcome:
    results: List[RecallResult]
    activated_cells: Set[int]
    inhibited_cells: Set[int]
    exclusions: Dict[str, str]  # memory_id -> reason


class MinimalRaven:
    """Faithful minimal raven engine with configurable mechanism flags."""

    def __init__(
        self,
        hops: int = 2,
        links_on: bool = True,
        state_on: bool = True,
        recency_on: bool = True,
        rescue_on: bool = True,
        auto_contradiction: bool = True,
        k_neighbors: int = K_NEIGHBORS,
    ):
        self.hops = hops
        self.links_on = links_on
        self.state_on = state_on
        self.recency_on = recency_on
        self.rescue_on = rescue_on
        self.auto_contradiction = auto_contradiction
        self.k_neighbors = k_neighbors

        self.memories: Dict[str, Memory] = {}
        self._cell_to_memory: Dict[int, str] = {}
        self._next_cell_id = 0
        self._active_cells: Set[int] = set()
        self._points: Dict[int, np.ndarray] = {}
        self.cell_neighbors: Dict[int, Set[int]] = {}
        self._kdtree: Optional[KDTree] = None
        self._kdtree_idx_to_cell: List[int] = []
        self._kdtree_dirty = True
        self._topic_index: Dict[str, List[Tuple[str, int, str]]] = {}

    def store(
        self,
        memory_id: str,
        embedding: np.ndarray,
        state: State = State.NEUTRAL,
        topic: str = "",
        claim: str = "",
        last_activation: float = 0.0,
    ) -> Memory:
        cell_id = self._next_cell_id
        self._next_cell_id += 1
        mem = Memory(
            memory_id=memory_id,
            cell_id=cell_id,
            embedding=embedding.astype(np.float64),
            state=state,
            topic=topic,
            claim=claim,
            last_activation=last_activation,
        )
        self.memories[memory_id] = mem
        self._cell_to_memory[cell_id] = memory_id
        self._active_cells.add(cell_id)
        self._points[cell_id] = mem.embedding
        self._kdtree_dirty = True

        if topic:
            self._topic_index.setdefault(topic, []).append(
                (memory_id, cell_id, claim)
            )

        if self.auto_contradiction and topic and claim:
            self._auto_link_contradictions(mem)

        return mem

    def _auto_link_contradictions(self, new_mem: Memory):
        """OBSERVED memory_engine.py:1568-1596: same topic + different claim
        -> bidirectional INHIBITORY link."""
        for mem_id, cell_id, claim in self._topic_index.get(new_mem.topic, []):
            if mem_id == new_mem.memory_id:
                continue
            if claim and claim != new_mem.claim:
                new_mem.links[cell_id] = INHIBITORY
                self.memories[mem_id].links[new_mem.cell_id] = INHIBITORY

    def add_link(self, mem_id_a: str, mem_id_b: str, link_type: int):
        a = self.memories[mem_id_a]
        b = self.memories[mem_id_b]
        a.links[b.cell_id] = link_type
        b.links[a.cell_id] = link_type

    def _ensure_kdtree(self):
        if not self._kdtree_dirty:
            return
        self._kdtree_dirty = False
        if not self._active_cells:
            self._kdtree = None
            self.cell_neighbors = {}
            self._kdtree_idx_to_cell = []
            return

        self._kdtree_idx_to_cell = sorted(self._active_cells)
        arr = np.array([self._points[c] for c in self._kdtree_idx_to_cell])
        self._kdtree = KDTree(arr)

        k = min(self.k_neighbors, len(self._kdtree_idx_to_cell) - 1)
        if k <= 0:
            self.cell_neighbors = {c: set() for c in self._kdtree_idx_to_cell}
            return

        _, indices = self._kdtree.query(arr, k=k + 1)
        self.cell_neighbors = {}
        for arr_i, neighbors in enumerate(indices):
            cell_id = self._kdtree_idx_to_cell[arr_i]
            real = {
                self._kdtree_idx_to_cell[int(n)]
                for n in neighbors
                if n != arr_i
            }
            self.cell_neighbors[cell_id] = real
            # OBSERVED memory_engine.py:1493-1494: symmetrize
            for n_cell in real:
                self.cell_neighbors.setdefault(n_cell, set()).add(cell_id)

    @staticmethod
    def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
        dot = float(np.dot(a, b))
        na = math.sqrt(float(np.dot(a, a)))
        nb = math.sqrt(float(np.dot(b, b)))
        if na == 0 or nb == 0:
            return 0.0
        s = dot / (na * nb)
        return max(-1.0, min(1.0, s))

    def _bfs(
        self,
        query_cell: int,
        suppressed: Set[int],
    ) -> Tuple[Set[int], Set[int], Dict[int, float], Dict[int, int]]:
        """Core BFS. Returns (activated, inhibited, resonant_boosts, cell_hops).
        cell_hops includes ALL reached cells (activated AND inhibited), so a
        post-hoc rescue can score an inhibited cell with its real hop_dist."""
        activated_cells: Set[int] = set()
        inhibited_cells: Set[int] = set()
        resonant_boosts: Dict[int, float] = {}
        cell_hops: Dict[int, int] = {query_cell: 0}
        frontier = {query_cell}

        for hop_idx in range(self.hops + 1):
            new_frontier: Set[int] = set()
            for cell in frontier:
                if cell in inhibited_cells or cell in suppressed:
                    continue
                activated_cells.add(cell)

                for neighbor in self.cell_neighbors.get(cell, set()):
                    if neighbor in suppressed:
                        continue
                    new_frontier.add(neighbor)
                    if neighbor not in cell_hops:
                        cell_hops[neighbor] = hop_idx + 1

                if self.links_on:
                    mem = self.memories.get(self._cell_to_memory.get(cell, ""))
                    if mem:
                        for target_id, link_type in mem.links.items():
                            if target_id in suppressed:
                                continue
                            if link_type == INHIBITORY:
                                inhibited_cells.add(target_id)
                                if target_id not in cell_hops:
                                    cell_hops[target_id] = hop_idx + 1
                            elif link_type == RESONANT:
                                new_frontier.add(target_id)
                                resonant_boosts[target_id] = (
                                    resonant_boosts.get(target_id, 0.0)
                                    + RESONANT_BOOST
                                )
                                if target_id not in cell_hops:
                                    cell_hops[target_id] = hop_idx + 1
                            else:
                                new_frontier.add(target_id)
                                if target_id not in cell_hops:
                                    cell_hops[target_id] = hop_idx + 1

            frontier = new_frontier - activated_cells - inhibited_cells - suppressed

        return activated_cells, inhibited_cells, resonant_boosts, cell_hops

    def _score_cell(
        self,
        cell_id: int,
        query_embedding: np.ndarray,
        cell_hops: Dict[int, int],
        resonant_boosts: Dict[int, float],
        now: float,
        query_cell: int,
    ) -> float:
        """Score a single cell using raven's formula."""
        mem_id = self._cell_to_memory.get(cell_id, "")
        mem = self.memories.get(mem_id)
        if mem is None:
            return 0.0

        sim = self._cosine_sim(query_embedding, mem.embedding)
        state_boost = mem.state.value if self.state_on else 1.0
        hop_dist = cell_hops.get(cell_id, 0)
        hop_decay = math.exp(-HOP_LAMBDA * hop_dist) if hop_dist >= 0 else 1.0
        resonant_boost = resonant_boosts.get(cell_id, 0.0)

        recency_bonus = 0.0
        if self.recency_on and mem.last_activation > 0:
            age = max(0.0, now - mem.last_activation)
            recency_bonus = RECENCY_WEIGHT * math.exp(
                -math.log(2) * age / RECENCY_HALFLIFE
            )

        resonant_contribution = resonant_boost * min(sim, 1.0)
        final_score = (
            sim * state_boost * hop_decay
            + resonant_contribution
            + recency_bonus
        )
        return max(0.0, final_score)

    def recall(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        now: float = 0.0,
        suppressed: Optional[Set[int]] = None,
    ) -> RecallOutcome:
        """Faithful recall: seed -> BFS -> rescue -> score -> sort."""
        if suppressed is None:
            suppressed = set()

        self._ensure_kdtree()
        if self._kdtree is None or not self._active_cells:
            return RecallOutcome([], set(), set(), {})

        _, idx = self._kdtree.query(query_embedding.reshape(1, -1))
        query_cell = self._kdtree_idx_to_cell[int(idx[0])]

        activated_cells, inhibited_cells, resonant_boosts, cell_hops = (
            self._bfs(query_cell, suppressed)
        )

        exclusions: Dict[str, str] = {}

        # Rescue (OBSERVED memory_engine.py:1718-1730): BEFORE scoring,
        # move REINFORCED from inhibited to activated.
        if self.rescue_on and inhibited_cells:
            for cell_id in list(inhibited_cells):
                mem_id = self._cell_to_memory.get(cell_id, "")
                mem = self.memories.get(mem_id)
                if mem and mem.state == State.REINFORCED:
                    inhibited_cells.discard(cell_id)
                    activated_cells.add(cell_id)
                else:
                    exclusions[mem_id] = "INHIBITED"

        for cell_id in suppressed:
            mem_id = self._cell_to_memory.get(cell_id, "")
            if mem_id:
                exclusions[mem_id] = "DIRECT_SUPPRESSION"

        # Score
        results: List[RecallResult] = []
        for cell_id in activated_cells:
            mem_id = self._cell_to_memory.get(cell_id, "")
            mem = self.memories.get(mem_id)
            if mem is None:
                continue
            if mem.state == State.FORGOTTEN:
                exclusions[mem_id] = "STATE_FILTER"
                continue
            if cell_id in inhibited_cells and cell_id != query_cell:
                exclusions[mem_id] = "INHIBITED"
                continue

            final_score = self._score_cell(
                cell_id, query_embedding, cell_hops, resonant_boosts, now, query_cell
            )
            hop_dist = cell_hops.get(cell_id, 0)
            source = "similarity" if hop_dist == 0 else "propagation"
            results.append(
                RecallResult(
                    memory=mem,
                    final_score=final_score,
                    hop_distance=hop_dist,
                    source=source,
                )
            )

        results.sort(key=lambda r: (-r.final_score, r.memory.memory_id))
        return RecallOutcome(
            results=results[:top_k],
            activated_cells=activated_cells,
            inhibited_cells=inhibited_cells,
            exclusions=exclusions,
        )

    def recall_post_hoc_rescue(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        now: float = 0.0,
        suppressed: Optional[Set[int]] = None,
    ) -> RecallOutcome:
        """Variant C: rescue OFF during BFS, but AFTER scoring, add REINFORCED
        memories that were excluded as INHIBITED back into results, scored with
        their real hop_dist from the BFS. This is the post-hoc metadata filter
        that would make rescue redundant if it produces identical outcomes."""
        if suppressed is None:
            suppressed = set()

        self._ensure_kdtree()
        if self._kdtree is None or not self._active_cells:
            return RecallOutcome([], set(), set(), {})

        _, idx = self._kdtree.query(query_embedding.reshape(1, -1))
        query_cell = self._kdtree_idx_to_cell[int(idx[0])]

        # BFS with rescue OFF
        original_rescue = self.rescue_on
        self.rescue_on = False
        activated_cells, inhibited_cells, resonant_boosts, cell_hops = (
            self._bfs(query_cell, suppressed)
        )
        self.rescue_on = original_rescue

        exclusions: Dict[str, str] = {}
        for cell_id in inhibited_cells:
            mem_id = self._cell_to_memory.get(cell_id, "")
            if mem_id:
                exclusions[mem_id] = "INHIBITED"
        for cell_id in suppressed:
            mem_id = self._cell_to_memory.get(cell_id, "")
            if mem_id:
                exclusions[mem_id] = "DIRECT_SUPPRESSION"

        # Score activated cells (no rescue)
        results: List[RecallResult] = []
        for cell_id in activated_cells:
            mem_id = self._cell_to_memory.get(cell_id, "")
            mem = self.memories.get(mem_id)
            if mem is None:
                continue
            if mem.state == State.FORGOTTEN:
                exclusions[mem_id] = "STATE_FILTER"
                continue

            final_score = self._score_cell(
                cell_id, query_embedding, cell_hops, resonant_boosts, now, query_cell
            )
            hop_dist = cell_hops.get(cell_id, 0)
            source = "similarity" if hop_dist == 0 else "propagation"
            results.append(
                RecallResult(
                    memory=mem,
                    final_score=final_score,
                    hop_distance=hop_dist,
                    source=source,
                )
            )

        # Post-hoc rescue: score REINFORCED inhibited cells and add to results
        for cell_id in inhibited_cells:
            mem_id = self._cell_to_memory.get(cell_id, "")
            mem = self.memories.get(mem_id)
            if mem is None or mem.state != State.REINFORCED:
                continue

            final_score = self._score_cell(
                cell_id, query_embedding, cell_hops, resonant_boosts, now, query_cell
            )
            hop_dist = cell_hops.get(cell_id, 0)
            results.append(
                RecallResult(
                    memory=mem,
                    final_score=final_score,
                    hop_distance=hop_dist,
                    source="rescued_post_hoc",
                )
            )

        results.sort(key=lambda r: (-r.final_score, r.memory.memory_id))
        return RecallOutcome(
            results=results[:top_k],
            activated_cells=activated_cells,
            inhibited_cells=inhibited_cells,
            exclusions=exclusions,
        )

    def recall_flat_topk(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        now: float = 0.0,
        state_on: bool = False,
        recency_on: bool = False,
    ) -> List[RecallResult]:
        """B0/B1 baseline: compute cosine similarity to ALL active memories,
        apply optional state multiplier and recency, return top-k. This is
        competent top-k retrieval, NOT BFS-with-0-hops (which only returns
        the seed cell)."""
        self._ensure_kdtree()
        if not self._active_cells:
            return []

        results: List[RecallResult] = []
        for cell_id in self._active_cells:
            mem_id = self._cell_to_memory.get(cell_id, "")
            mem = self.memories.get(mem_id)
            if mem is None or mem.state == State.FORGOTTEN:
                continue

            sim = self._cosine_sim(query_embedding, mem.embedding)
            state_boost = mem.state.value if state_on else 1.0
            recency_bonus = 0.0
            if recency_on and mem.last_activation > 0:
                age = max(0.0, now - mem.last_activation)
                recency_bonus = RECENCY_WEIGHT * math.exp(
                    -math.log(2) * age / RECENCY_HALFLIFE
                )
            final_score = max(0.0, sim * state_boost + recency_bonus)
            results.append(
                RecallResult(
                    memory=mem,
                    final_score=final_score,
                    hop_distance=0,
                    source="flat_topk",
                )
            )

        results.sort(key=lambda r: (-r.final_score, r.memory.memory_id))
        return results[:top_k]

    def list_memory_ids(self) -> List[str]:
        return sorted(self.memories.keys())

    def snapshot_state(self) -> dict:
        """Snapshot the full mutable engine state for later restore.
        Used by Exp14 causal-state replay counterfactuals."""
        import copy
        return {
            "memories": {
                mid: {
                    "state": mem.state,
                    "last_activation": mem.last_activation,
                    "links": dict(mem.links),
                    "synaptic_links": dict(mem.synaptic_links),
                }
                for mid, mem in self.memories.items()
            },
            "active_cells": set(self._active_cells),
        }

    def restore_state(self, snap: dict):
        """Restore engine state from a snapshot."""
        for mid, mem_data in snap["memories"].items():
            mem = self.memories.get(mid)
            if mem:
                mem.state = mem_data["state"]
                mem.last_activation = mem_data["last_activation"]
                mem.links = dict(mem_data["links"])
                mem.synaptic_links = dict(mem_data["synaptic_links"])
        self._active_cells = set(snap["active_cells"])
        self._kdtree_dirty = True

    def remove_memory(self, memory_id: str):
        """Physically remove a memory from the corpus (for Exp3)."""
        mem = self.memories.pop(memory_id, None)
        if mem is None:
            return
        self._active_cells.discard(mem.cell_id)
        self._points.pop(mem.cell_id, None)
        self._cell_to_memory.pop(mem.cell_id, None)
        # Remove links pointing to this cell
        for other in self.memories.values():
            other.links.pop(mem.cell_id, None)
        self._kdtree_dirty = True

    # ---- Learning mechanisms (OBSERVED from memory_engine.py:2131-2164) ----
    # STDP constants
    STDP_MAX_WEIGHT = 2.0
    STDP_MIN_WEIGHT = 0.0
    STDP_POTENTIATION = 0.10
    STDP_DEPRESSION = 0.02
    STDP_PRUNE_EPS = 1e-9

    def reinforce(self, memory_id: str):
        """Set memory state to REINFORCED (OBSERVED memory_engine.py:2171-2186)."""
        mem = self.memories.get(memory_id)
        if mem is None:
            return
        mem.state = State.REINFORCED
        if mem.cell_id not in self._active_cells:
            self._active_cells.add(mem.cell_id)
            self._points[mem.cell_id] = mem.embedding
            self._kdtree_dirty = True

    def update_activations(self, memory_ids, now: float):
        """Set last_activation for recalled memories."""
        for mid in memory_ids:
            mem = self.memories.get(mid)
            if mem:
                mem.last_activation = now

    def update_stdp(self, previous_ids, current_ids):
        """STDP LTP + LTD (OBSERVED memory_engine.py:2131-2164).

        LTP: co-activated pairs strengthen by STDP_POTENTIATION.
        LTD: previously linked but absent weaken by STDP_DEPRESSION.
        """
        curr_set = set(current_ids)
        for prev_id in previous_ids:
            prev_mem = self.memories.get(prev_id)
            if prev_mem is None:
                continue
            links = prev_mem.synaptic_links
            for curr_id in curr_set:
                if curr_id == prev_id:
                    continue
                links[curr_id] = min(
                    self.STDP_MAX_WEIGHT,
                    links.get(curr_id, 0.0) + self.STDP_POTENTIATION,
                )
            for eid in list(links.keys()):
                if eid not in curr_set and eid != prev_id:
                    links[eid] = max(
                        self.STDP_MIN_WEIGHT,
                        links[eid] - self.STDP_DEPRESSION,
                    )
                    if links[eid] <= self.STDP_PRUNE_EPS:
                        del links[eid]

    def recall_with_learning(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        now: float = 0.0,
        current_turn_memories=None,
        suppressed=None,
    ):
        """Recall with STDP synaptic pull (OBSERVED memory_engine.py:1855-1896).

        If current_turn_memories is provided, memories linked via synaptic_links
        with weight >= 0.5 are pulled in (bypassing BFS).
        """
        outcome = self.recall(query_embedding, top_k, now, suppressed)

        if current_turn_memories:
            # Synaptic pull
            existing_ids = {r.memory.memory_id for r in outcome.results}
            link_candidates = {}
            for act_id in current_turn_memories:
                act_mem = self.memories.get(act_id)
                if not act_mem:
                    continue
                for linked_id, weight in act_mem.synaptic_links.items():
                    if weight >= 0.5 and linked_id not in existing_ids:
                        link_candidates[linked_id] = max(
                            link_candidates.get(linked_id, 0.0), weight
                        )

            for linked_id, weight in link_candidates.items():
                linked = self.memories.get(linked_id)
                if not linked or linked.state == State.FORGOTTEN:
                    continue
                if linked.cell_id in (suppressed or set()):
                    continue
                # Add to results
                from minimal_raven import RecallResult
                outcome.results.append(
                    RecallResult(
                        memory=linked,
                        final_score=weight * SYNAPTIC_SCORE_WEIGHT,
                        hop_distance=-1,
                        source="synaptic",
                    )
                )
                existing_ids.add(linked_id)

            outcome.results.sort(
                key=lambda r: (-r.final_score, r.memory.memory_id)
            )
            outcome.results = outcome.results[:top_k]

        return outcome
