#!/usr/bin/env python3
"""Exp40: falsify causal measurement under thresholded inhibition and rescue.

The thresholded query seed and directed test graph are PROPOSED harness
choices, not observed Raven rules. The BFS treatment of active cells,
inhibition, suppression, and post-BFS rescue follows the bounded code pattern
cited in this artifact's JSON metadata. This is not a Raven implementation.

Predictions fixed before execution:
1. With tau=1, raising A's seed from 99/100 to 1 activates A -> B; B inhibits
   neutral C, so C's candidate status changes discontinuously.
2. Suppressing A at seed 1 leaves the A-B structural path untouched but stops
   its activation. An independent query seed reaches C through R-X-Y-C, so C
   becomes a candidate while the original A-B pathway stays inactive.
3. If C is REINFORCED, post-BFS rescue puts C back in candidates, but does not
   resume propagation from C to D because BFS has already ended.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction as F
from typing import Dict, Set, Tuple

NODES = ("A", "B", "R", "X", "Y", "C", "D")
THRESHOLD = F(1)
MAX_HOPS = 4


class MemoryState(str, Enum):
    REINFORCED = "REINFORCED"
    NEUTRAL = "NEUTRAL"
    FORGOTTEN = "FORGOTTEN"


class LinkType(str, Enum):
    NEUTRAL = "NEUTRAL"
    RESONANT = "RESONANT"
    INHIBITORY = "INHIBITORY"


@dataclass
class World:
    states: Dict[str, MemoryState] = field(default_factory=lambda: {
        node: MemoryState.NEUTRAL for node in NODES
    })
    # Undirected neighborhood edges mirror the traversal role of cell_neighbors.
    neighbors: Dict[str, Set[str]] = field(default_factory=lambda: {node: set() for node in NODES})
    # Typed directed associations are separate from neighborhood adjacency.
    links: Dict[Tuple[str, str], LinkType] = field(default_factory=dict)


def assay_world(c_state: MemoryState = MemoryState.NEUTRAL) -> World:
    world = World()
    world.states["C"] = c_state
    for left, right in (("A", "B"), ("R", "X"), ("X", "Y"),
                        ("Y", "C"), ("C", "D")):
        world.neighbors[left].add(right)
        world.neighbors[right].add(left)
    world.links[("B", "C")] = LinkType.INHIBITORY
    return world


def choose_seeds(seed_scores: Dict[str, F], threshold: F,
                 suppressed: frozenset[str]) -> set[str]:
    return {node for node, score in seed_scores.items()
            if score >= threshold and node not in suppressed}


def recall(world: World, seed_scores: Dict[str, F], threshold: F = THRESHOLD,
           hops: int = MAX_HOPS, suppressed: frozenset[str] = frozenset()) -> dict:
    """Read-only BFS recall with typed inhibition and a post-BFS rescue pass."""
    if hops < 0:
        raise ValueError("hops must be >= 0")
    if threshold < 0:
        raise ValueError("threshold must be >= 0")
    if set(seed_scores) - set(NODES):
        raise ValueError("seed scores contain unknown nodes")
    if suppressed - set(NODES):
        raise ValueError("suppression contains unknown nodes")

    seeds = choose_seeds(seed_scores, threshold, suppressed)
    activated: set[str] = set()
    inhibited: set[str] = set()
    frontier = set(seeds)
    first_hop = {node: 0 for node in seeds}

    for hop_index in range(hops + 1):
        next_frontier: set[str] = set()
        for cell in sorted(frontier):
            if cell in inhibited or cell in suppressed:
                continue
            activated.add(cell)

            for neighbor in sorted(world.neighbors[cell]):
                if neighbor in suppressed:
                    continue
                next_frontier.add(neighbor)
                first_hop.setdefault(neighbor, hop_index + 1)

            for (src, dst), link_type in sorted(world.links.items()):
                if src != cell or dst in suppressed:
                    continue
                if link_type == LinkType.INHIBITORY:
                    inhibited.add(dst)
                else:
                    next_frontier.add(dst)
                    first_hop.setdefault(dst, hop_index + 1)

        frontier = next_frontier - activated - inhibited - set(suppressed)

    rescued: set[str] = set()
    for node in sorted(inhibited):
        if world.states[node] == MemoryState.REINFORCED:
            inhibited.discard(node)
            activated.add(node)
            rescued.add(node)

    candidates = {node for node in activated
                  if world.states[node] != MemoryState.FORGOTTEN and node not in inhibited}
    exclusions = {node: "INHIBITED" for node in sorted(inhibited)}
    exclusions.update({node: "DIRECT_SUPPRESSION" for node in sorted(suppressed)})
    exclusions.update({node: "STATE_FILTER" for node in NODES
                       if node in activated and world.states[node] == MemoryState.FORGOTTEN})
    return {
        "seeds": seeds,
        "activated": activated,
        "inhibited": inhibited,
        "rescued": rescued,
        "candidates": candidates,
        "exclusions": exclusions,
        "first_hop": first_hop,
    }


def fraction(value: F) -> str:
    return f"{value.numerator}/{value.denominator}"


def sorted_map(values: dict) -> dict:
    return {key: values[key] for key in sorted(values)}


def encode_result(result: dict) -> dict:
    return {key: sorted(values) if isinstance(values, set) else sorted_map(values)
            for key, values in result.items()}


def run() -> dict:
    world = assay_world()
    low = {"A": F(99, 100), "R": F(1)}
    boundary = {"A": F(1), "R": F(1)}
    high = {"A": F(101, 100), "R": F(1)}

    threshold_sweep = {
        "below": encode_result(recall(world, low)),
        "at": encode_result(recall(world, boundary)),
        "above": encode_result(recall(world, high)),
    }
    suppressed_a = encode_result(recall(world, boundary, suppressed=frozenset({"A"})))
    reinforced_world = assay_world(MemoryState.REINFORCED)
    rescued_c = encode_result(recall(reinforced_world, boundary))

    return seal({
        "status": "EXECUTED_SYNTHETIC_DISCRETE_MECHANISM_ASSAY",
        "epistemic_labels": {
            "OBSERVED": "Raven snapshot code uses BFS propagation, inhibitory links, suppression, and post-BFS rescue as cited below.",
            "PROPOSED": "Thresholded multiple seed scores and this seven-node graph are experimental choices, not Raven's seed-selection implementation.",
            "INFERRED": "In this harness, crossing the seed threshold changes C's inhibition/candidate status; suppressing A lets the independent R-X-Y-C route recover C.",
            "UNKNOWN": "Whether these exact threshold and rescue interactions occur in Raven, MNEME, or a deployed agent under equivalent inputs.",
        },
        "raven_snapshot": {
            "repo": "sources/raven-memory",
            "commit": "56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f",
            "provenance_file": "sources/raven-memory/PROVENANCE.md",
            "observed_code": [
                {"file": "sources/raven-memory/raven/memory_engine.py", "lines": "125-134", "claim": "Ternary memory and link enum values include FORGOTTEN=0.0 and INHIBITORY=-1.0."},
                {"file": "sources/raven-memory/raven/memory_engine.py", "lines": "1635-1639", "claim": "The field suppression contract blocks a cell from seeding, relaying, firing links, and ranking."},
                {"file": "sources/raven-memory/raven/memory_engine.py", "lines": "1682-1714", "claim": "Recall uses bounded BFS frontiers; inhibitory links mark targets inhibited, while resonant and neutral links add traversal targets."},
                {"file": "sources/raven-memory/raven/memory_engine.py", "lines": "1718-1730", "claim": "After BFS, inhibited REINFORCED cells are removed from inhibition and added to activated cells."},
                {"file": "sources/raven-memory/raven/memory_engine.py", "lines": "1649-1671", "claim": "The production recall seed is selected as the nearest eligible cell; it is not chosen by the threshold used in this experiment."},
            ],
        },
        "experiment_parameters": {
            "threshold": fraction(THRESHOLD),
            "max_hops": MAX_HOPS,
            "A_to_B": "undirected neighborhood edge",
            "B_to_C": LinkType.INHIBITORY.value,
            "alternate_route": ["R", "X", "Y", "C"],
            "C_to_D": "undirected neighborhood edge",
            "A_edge_recorded_during_suppression": True,
        },
        "threshold_sweep": threshold_sweep,
        "high_query_with_A_suppressed": suppressed_a,
        "high_query_with_REINFORCED_C_rescue": rescued_c,
        "predictions": {
            "C_candidate_below_threshold": True,
            "C_excluded_at_threshold_when_NEUTRAL": True,
            "A_suppression_recovers_C_via_alternate_route": True,
            "REINFORCED_C_is_rescued_after_BFS": True,
            "post_BFS_rescue_does_not_activate_D_from_C": True,
        },
        "limits": "Finite-hop discrete harness; thresholded multi-seed logic is proposed, not Raven's nearest-cell seeding. No persistent state update, ranking score, stochastic model, or MNEME/Raven runtime integration is measured.",
    })


def seal(payload: dict) -> dict:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return {**payload, "sha256": hashlib.sha256(canonical.encode()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="write JSON to this path instead of stdout")
    args = parser.parse_args()
    rendered = json.dumps(run(), indent=2, sort_keys=True) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as stream:
            stream.write(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
