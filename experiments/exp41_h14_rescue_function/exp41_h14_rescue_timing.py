#!/usr/bin/env python3
"""Exp41: availability rescue versus propagation-capable reactivation.

Predeclared comparison: three branches clone one identical world in which C
is REINFORCED and inhibited by B. Only rescue timing changes: disabled,
post-BFS (the source snapshot rule), or immediately when inhibition fires
(a proposed extension). Measure C's intervention effect on fixed decision
scores and whether activation reaches D. The score mapping is a toy oracle,
not a Raven decision rule.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction as F
from typing import Dict, Set, Tuple

NODES = ("A", "B", "R", "X", "Y", "C", "D")
SEED_SCORES = {"A": F(1), "R": F(1)}
HOPS = 4
RESCUE_MODES = ("disabled", "post_bfs", "during_bfs")


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
    neighbors: Dict[str, Set[str]] = field(default_factory=lambda: {node: set() for node in NODES})
    links: Dict[Tuple[str, str], LinkType] = field(default_factory=dict)


def assay_world() -> World:
    world = World()
    world.states["C"] = MemoryState.REINFORCED
    for left, right in (("A", "B"), ("R", "X"), ("X", "Y"),
                        ("Y", "C"), ("C", "D")):
        world.neighbors[left].add(right)
        world.neighbors[right].add(left)
    world.links[("B", "C")] = LinkType.INHIBITORY
    return world


def recall(world: World, seed_scores: Dict[str, F] = SEED_SCORES,
           rescue_mode: str = "post_bfs", hops: int = HOPS,
           suppressed: frozenset[str] = frozenset()) -> dict:
    """Read-only BFS with the rescue timing as the sole treatment factor."""
    if rescue_mode not in RESCUE_MODES:
        raise ValueError(f"rescue_mode must be one of {RESCUE_MODES}")
    if hops < 0:
        raise ValueError("hops must be >= 0")
    if set(seed_scores) - set(NODES) or suppressed - set(NODES):
        raise ValueError("unknown node in seeds or suppression")

    seeds = {node for node, value in seed_scores.items()
             if value > 0 and node not in suppressed}
    activated: set[str] = set()
    processed: set[str] = set()
    inhibited: set[str] = set()
    rescued: set[str] = set()
    activation_hop: dict[str, int] = {}
    frontier = set(seeds)

    for hop_index in range(hops + 1):
        next_frontier: set[str] = set()
        for cell in sorted(frontier):
            if cell in inhibited or cell in suppressed:
                continue
            activated.add(cell)
            processed.add(cell)
            activation_hop.setdefault(cell, hop_index)

            for neighbor in sorted(world.neighbors[cell]):
                if neighbor not in suppressed:
                    next_frontier.add(neighbor)

            for (src, dst), link_type in sorted(world.links.items()):
                if src != cell or dst in suppressed:
                    continue
                if link_type == LinkType.INHIBITORY:
                    inhibited.add(dst)
                    if (rescue_mode == "during_bfs"
                            and world.states[dst] == MemoryState.REINFORCED):
                        inhibited.discard(dst)
                        rescued.add(dst)
                        next_frontier.add(dst)
                else:
                    next_frontier.add(dst)

        frontier = next_frontier - activated - inhibited - set(suppressed)

    if rescue_mode == "post_bfs":
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
        "processed": processed,
        "inhibited": inhibited,
        "rescued": rescued,
        "candidates": candidates,
        "exclusions": exclusions,
        "activation_hop": activation_hop,
    }


def decision_scores(result: dict) -> Dict[str, F]:
    """Declared downstream oracle: C votes X; D votes Y; Y has a 1/4 bias."""
    candidates = result["candidates"]
    return {
        "X": F(1) if "C" in candidates else F(0),
        "Y": F(1, 4) + (F(1) if "D" in candidates else F(0)),
    }


def choose(scores: Dict[str, F]) -> str:
    return "X" if scores["X"] > scores["Y"] else "Y"


def measure_C_effect(world: World, rescue_mode: str) -> dict:
    full = recall(world, rescue_mode=rescue_mode)
    without_c = recall(world, rescue_mode=rescue_mode, suppressed=frozenset({"C"}))
    full_scores = decision_scores(full)
    without_scores = decision_scores(without_c)
    delta = {action: full_scores[action] - without_scores[action] for action in ("X", "Y")}
    return {
        "decision_scores_with_C": full_scores,
        "decision_scores_C_suppressed": without_scores,
        "delta_by_action": delta,
        "delta_margin_X_minus_Y": delta["X"] - delta["Y"],
        "choice_with_C": choose(full_scores),
        "choice_C_suppressed": choose(without_scores),
        "C_processed_during_BFS": "C" in full["processed"],
        "D_activated": "D" in full["activated"],
        "C_candidate": "C" in full["candidates"],
    }


def encoded(result: dict) -> dict:
    return {key: sorted(value) if isinstance(value, set) else dict(sorted(value.items()))
            for key, value in result.items()}


def fraction(value: F) -> str:
    return f"{value.numerator}/{value.denominator}"


def encode_scores(values: Dict[str, F]) -> dict[str, str]:
    return {key: fraction(value) for key, value in values.items()}


def encode_effect(effect: dict) -> dict:
    encoded_effect = dict(effect)
    for key in ("decision_scores_with_C", "decision_scores_C_suppressed", "delta_by_action"):
        encoded_effect[key] = encode_scores(effect[key])
    encoded_effect["delta_margin_X_minus_Y"] = fraction(effect["delta_margin_X_minus_Y"])
    return encoded_effect


def run() -> dict:
    original = assay_world()
    arms = {}
    for mode in RESCUE_MODES:
        branch = copy.deepcopy(original)
        arms[mode] = {
            "world_equals_common_start": branch == original,
            "recall": encoded(recall(branch, rescue_mode=mode)),
            "causal_C_effect": encode_effect(measure_C_effect(branch, mode)),
        }
    return seal({
        "status": "EXECUTED_SYNTHETIC_RESCUE_TIMING_ASSAY",
        "epistemic_labels": {
            "OBSERVED": "The three deterministic branches, candidate sets, downstream score effects, and test outputs produced by this harness.",
            "PROPOSED": "During-BFS reactivation and the downstream decision-score mapping are experimental interventions, not observed Raven behavior.",
            "INFERRED": "In this setup, post-BFS rescue restores C's candidate availability while during-BFS rescue additionally restores propagation to D.",
            "UNKNOWN": "Whether this timing distinction predicts retrieval or decisions in Raven, MNEME, or a deployed agent.",
        },
        "raven_snapshot": {
            "repo": "sources/raven-memory",
            "commit": "56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f",
            "observed_rule": "An inhibited REINFORCED cell is rescued after BFS by removing it from inhibited_cells and adding it to activated_cells.",
            "source_file": "sources/raven-memory/raven/memory_engine.py",
            "source_lines": "1718-1730",
        },
        "common_start": {
            "states": {node: state.value for node, state in original.states.items()},
            "inhibitory_link": "B->C",
            "alternate_activation_route": ["R", "X", "Y", "C"],
            "downstream_node": "D",
            "all_branches_clone_same_state": True,
        },
        "decision_oracle": {
            "C_contribution": "1/1 to X when C is a candidate",
            "D_contribution": "1/1 to Y when D is a candidate",
            "Y_baseline_bias": "1/4",
            "warning": "A declared synthetic readout used to compare causal score effects; not Raven ranking or an agent decision model.",
        },
        "arms": arms,
        "limits": "One finite-hop graph and one deterministic score oracle; no model noise, persistent learning, downstream LLM, Raven runtime execution, or MNEME validation.",
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
