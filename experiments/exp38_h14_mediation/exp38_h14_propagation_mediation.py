#!/usr/bin/env python3
"""Exp38: falsify whether one-step neutralization captures mediated effects.

Prediction fixed before execution: in A -> B -> C with edge weights 1/2,
query seed A=1, and a separate D -> C path, Exp37's one-step scorer omits
the A-mediated contribution of 1/4 at C. In a linear acyclic propagation
model, recursively neutralizing A should remove exactly the sum of all
directed path contributions that pass through A; an independent path
enumerator is the oracle. This bounded toy assay is not Raven or MNEME.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from fractions import Fraction as F
from typing import Dict, Tuple

NODES = ("A", "B", "C", "D")
ACTION = {"A": "X", "B": "Y", "C": "X", "D": "Y"}
QUERY = {"A": F(1), "B": F(0), "C": F(0), "D": F(1)}


@dataclass
class World:
    strength: Dict[str, F] = field(default_factory=lambda: {node: F(1) for node in NODES})
    links: Dict[Tuple[str, str], F] = field(default_factory=dict)
    available: set[str] = field(default_factory=lambda: set(NODES))


def assay_world() -> World:
    """A two-hop A-mediated path plus a separate D -> C contribution."""
    return World(links={
        ("A", "B"): F(1, 2),
        ("B", "C"): F(1, 2),
        ("D", "C"): F(1, 3),
    })


def visible_nodes(world: World, neutralize: str | None = None) -> set[str]:
    return world.available - ({neutralize} if neutralize else set())


def topological_order(world: World, visible: set[str]) -> list[str]:
    indegree = {node: 0 for node in visible}
    outgoing = {node: [] for node in visible}
    for (src, dst), _weight in sorted(world.links.items()):
        if src in visible and dst in visible:
            outgoing[src].append(dst)
            indegree[dst] += 1
    ready = sorted(node for node, degree in indegree.items() if degree == 0)
    order = []
    while ready:
        src = ready.pop(0)
        order.append(src)
        for dst in outgoing[src]:
            indegree[dst] -= 1
            if indegree[dst] == 0:
                ready.append(dst)
                ready.sort()
    if len(order) != len(visible):
        raise ValueError("propagation graph must be acyclic")
    return order


def propagate(world: World, query: Dict[str, F], neutralize: str | None = None) -> Dict[str, F]:
    """Propagate accumulated activation through a directed acyclic graph."""
    visible = visible_nodes(world, neutralize)
    order = topological_order(world, visible)
    activation = {node: (query[node] * world.strength[node] if node in visible else F(0))
                  for node in NODES}
    for src in order:
        for (edge_src, dst), weight in sorted(world.links.items()):
            if edge_src == src and dst in visible:
                activation[dst] += activation[src] * weight
    return activation


def one_step_scores(world: World, query: Dict[str, F], neutralize: str | None = None) -> Dict[str, F]:
    """Exp37-style direct seed plus one edge hop; no recursive activation."""
    visible = visible_nodes(world, neutralize)
    scores = {node: (query[node] * world.strength[node] if node in visible else F(0))
              for node in NODES}
    for (src, dst), weight in sorted(world.links.items()):
        if src in visible and dst in visible:
            scores[dst] += query[src] * world.strength[src] * weight
    return scores


def action_scores(node_values: Dict[str, F]) -> Dict[str, F]:
    return {action: sum((node_values[node] for node in NODES if ACTION[node] == action), F(0))
            for action in ("X", "Y")}


def neutralization_effect(world: World, query: Dict[str, F], target: str = "A") -> dict:
    active = propagate(world, query)
    neutralized = propagate(world, query, neutralize=target)
    by_node = {node: active[node] - neutralized[node] for node in NODES}
    full_actions = action_scores(active)
    neutralized_actions = action_scores(neutralized)
    delta_actions = {action: full_actions[action] - neutralized_actions[action]
                     for action in ("X", "Y")}
    return {
        "activation_with_target": active,
        "activation_neutralized": neutralized,
        "delta_by_node": by_node,
        "delta_by_action": delta_actions,
        "delta_margin_X_minus_Y": delta_actions["X"] - delta_actions["Y"],
    }


def enumerate_target_paths(world: World, query: Dict[str, F], target: str = "A") -> dict:
    """Independent path-sum oracle grouped by destination and path length."""
    visible = visible_nodes(world)
    topological_order(world, visible)  # Reject cycles before enumeration.
    outgoing = {node: [] for node in visible}
    for (src, dst), weight in sorted(world.links.items()):
        if src in visible and dst in visible:
            outgoing[src].append((dst, weight))

    by_destination = {node: F(0) for node in NODES}
    by_length: Dict[str, Dict[int, F]] = {node: {} for node in NODES}
    paths = []

    def walk(source: str, current: str, seen_target: bool, path: tuple[str, ...],
             product: F, seed: F) -> None:
        contains_target = seen_target or current == target
        if contains_target:
            value = seed * product
            length = len(path) - 1
            by_destination[current] += value
            by_length[current][length] = by_length[current].get(length, F(0)) + value
            paths.append({"nodes": list(path), "value": value})
        for dst, weight in outgoing[current]:
            if dst not in path:
                walk(source, dst, contains_target, path + (dst,), product * weight, seed)

    for source in sorted(visible):
        seed = query[source] * world.strength[source]
        if seed:
            walk(source, source, source == target, (source,), F(1), seed)
    return {"by_destination": by_destination, "by_length": by_length, "paths": paths}


def one_step_effect(world: World, query: Dict[str, F], target: str = "A") -> dict[str, F]:
    full = one_step_scores(world, query)
    neutralized = one_step_scores(world, query, neutralize=target)
    return {node: full[node] - neutralized[node] for node in NODES}


def fraction(value: F) -> str:
    return f"{value.numerator}/{value.denominator}"


def encode_map(values: Dict[str, F]) -> dict[str, str]:
    return {key: fraction(value) for key, value in values.items()}


def run() -> dict:
    world = assay_world()
    total = neutralization_effect(world, QUERY, target="A")
    mediation = neutralization_effect(world, QUERY, target="B")
    path_oracle = enumerate_target_paths(world, QUERY, target="A")
    one_hop = one_step_effect(world, QUERY, target="A")
    if total["delta_by_node"] != path_oracle["by_destination"]:
        raise AssertionError("recursive neutralization differs from independent path sum")
    return seal({
        "status": "EXECUTED_BOUNDED_SYNTHETIC_INSTRUMENT_FALSIFIER",
        "epistemic_labels": {
            "OBSERVED": "Exact values produced by this deterministic run.",
            "PROPOSED": "Linear propagation over an acyclic directed graph is the declared test model.",
            "INFERRED": "The one-step score rule omits the A-mediated two-hop contribution in this graph because its second hop is not computed.",
            "UNKNOWN": "Whether Raven, MNEME, or another agent has equivalent propagation or mediation semantics.",
        },
        "graph": {f"{src}->{dst}": fraction(weight)
                  for (src, dst), weight in sorted(world.links.items())},
        "query_seed": encode_map(QUERY),
        "predeclared_prediction": {
            "A_to_C_two_hop_effect": "1/4",
            "D_is_not_affected_by_neutralizing_A": "0/1",
            "recursive_neutralization_equals_independent_path_sum": True,
            "one_step_scorer_omits_second_hop_effect": True,
        },
        "one_step_A_effect_by_node": encode_map(one_hop),
        "recursive_A_effect_by_node": encode_map(total["delta_by_node"]),
        "recursive_A_effect_by_action": encode_map(total["delta_by_action"]),
        "recursive_A_effect_on_X_minus_Y_margin": fraction(total["delta_margin_X_minus_Y"]),
        "path_oracle_A_effect_by_node": encode_map(path_oracle["by_destination"]),
        "path_oracle_A_effect_by_length": {
            node: {str(length): fraction(value) for length, value in sorted(lengths.items())}
            for node, lengths in path_oracle["by_length"].items()
        },
        "path_oracle_paths": [
            {"nodes": path["nodes"], "value": fraction(path["value"])}
            for path in path_oracle["paths"]
        ],
        "mediator_B_effect_by_node": encode_map(mediation["delta_by_node"]),
        "limits": "Linear exact-rational DAG only; no cycles, threshold gates, learned edge dynamics, Raven/MNEME equivalence, or statistical generalization.",
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
