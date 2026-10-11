#!/usr/bin/env python3
"""Exp39: probe cyclic feedback and inhibition in the H14 measurement.

Predeclared prediction: a stable A <-> B cycle with an inhibitory B -> A
edge creates an infinite, alternating path expansion. The exact rational
fixed point should match recursive neutralization, while any finite path
prefix should retain a residual. A separate D -> C path must remain active
when A is neutralized. This is a bounded synthetic model, not Raven/MNEME.
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
    """A stable signed cycle, two-hop mediation, and an independent path."""
    return World(links={
        ("A", "B"): F(1, 2),
        ("B", "A"): F(-1, 4),  # inhibitory feedback
        ("B", "C"): F(1, 2),
        ("D", "C"): F(1, 3),
    })


def visible_nodes(world: World, neutralize: str | None = None) -> set[str]:
    return world.available - ({neutralize} if neutralize else set())


def contraction_bound(world: World, visible: set[str]) -> F:
    """Infinity-norm bound: largest incoming absolute-weight sum."""
    incoming = {node: F(0) for node in visible}
    for (src, dst), weight in world.links.items():
        if src in visible and dst in visible:
            incoming[dst] += abs(weight)
    return max(incoming.values(), default=F(0))


def solve_linear_system(matrix: list[list[F]], rhs: list[F]) -> list[F]:
    """Exact Gauss-Jordan solver; raises when the fixed point is not unique."""
    size = len(rhs)
    augmented = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(size):
        pivot = next((row for row in range(col, size) if augmented[row][col]), None)
        if pivot is None:
            raise ValueError("fixed-point equations are singular")
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        divisor = augmented[col][col]
        augmented[col] = [value / divisor for value in augmented[col]]
        for row in range(size):
            if row == col:
                continue
            factor = augmented[row][col]
            if factor:
                augmented[row] = [left - factor * right
                                  for left, right in zip(augmented[row], augmented[col])]
    return [augmented[i][-1] for i in range(size)]


def fixed_point(world: World, query: Dict[str, F], neutralize: str | None = None) -> Dict[str, F]:
    """Solve x = seed + W x for a declared contractive signed graph."""
    visible = visible_nodes(world, neutralize)
    bound = contraction_bound(world, visible)
    if bound >= 1:
        raise ValueError(f"absolute incoming-weight bound must be < 1 (got {bound})")
    ordered = sorted(visible)
    index = {node: i for i, node in enumerate(ordered)}
    matrix = [[F(int(i == j)) for j in range(len(ordered))]
              for i in range(len(ordered))]
    rhs = [query[node] * world.strength[node] for node in ordered]
    for (src, dst), weight in sorted(world.links.items()):
        if src in visible and dst in visible:
            matrix[index[dst]][index[src]] -= weight
    solution = solve_linear_system(matrix, rhs)
    values = {node: F(0) for node in NODES}
    values.update({node: solution[index[node]] for node in ordered})
    return values


def verify_fixed_point(world: World, query: Dict[str, F], values: Dict[str, F],
                       neutralize: str | None = None) -> bool:
    """Check the solved vector against the original recurrence equation."""
    visible = visible_nodes(world, neutralize)
    for dst in NODES:
        if dst not in visible:
            if values[dst] != 0:
                return False
            continue
        expected = query[dst] * world.strength[dst]
        for (src, edge_dst), weight in world.links.items():
            if edge_dst == dst and src in visible:
                expected += values[src] * weight
        if values[dst] != expected:
            return False
    return True


def action_scores(values: Dict[str, F]) -> Dict[str, F]:
    return {action: sum((values[node] for node in NODES if ACTION[node] == action), F(0))
            for action in ("X", "Y")}


def neutralization_effect(world: World, query: Dict[str, F], target: str = "A") -> dict:
    full = fixed_point(world, query)
    neutralized = fixed_point(world, query, neutralize=target)
    delta_nodes = {node: full[node] - neutralized[node] for node in NODES}
    full_actions = action_scores(full)
    neutralized_actions = action_scores(neutralized)
    delta_actions = {action: full_actions[action] - neutralized_actions[action]
                     for action in ("X", "Y")}
    return {
        "activation_with_target": full,
        "activation_neutralized": neutralized,
        "delta_by_node": delta_nodes,
        "delta_by_action": delta_actions,
        "delta_margin_X_minus_Y": delta_actions["X"] - delta_actions["Y"],
    }


def one_step_effect(world: World, query: Dict[str, F], target: str = "A") -> Dict[str, F]:
    """The Exp37 one-hop formula, evaluated on the same signed graph."""
    def score(neutralize: str | None) -> Dict[str, F]:
        visible = visible_nodes(world, neutralize)
        result = {node: (query[node] * world.strength[node] if node in visible else F(0))
                  for node in NODES}
        for (src, dst), weight in sorted(world.links.items()):
            if src in visible and dst in visible:
                result[dst] += query[src] * world.strength[src] * weight
        return result

    full, neutralized = score(None), score(target)
    return {node: full[node] - neutralized[node] for node in NODES}


def finite_walk_sum(world: World, query: Dict[str, F], target: str = "A",
                    max_hops: int = 0) -> dict:
    """Enumerate finite signed walks through target, including repeated nodes."""
    if max_hops < 0:
        raise ValueError("max_hops must be >= 0")
    visible = visible_nodes(world)
    outgoing = {node: [] for node in visible}
    for (src, dst), weight in sorted(world.links.items()):
        if src in visible and dst in visible:
            outgoing[src].append((dst, weight))
    by_node = {node: F(0) for node in NODES}
    by_length: Dict[str, Dict[int, F]] = {node: {} for node in NODES}

    def walk(current: str, path: tuple[str, ...], product: F, seed: F) -> None:
        if target in path:
            hops = len(path) - 1
            contribution = seed * product
            by_node[current] += contribution
            by_length[current][hops] = by_length[current].get(hops, F(0)) + contribution
        if len(path) - 1 == max_hops:
            return
        for dst, weight in outgoing[current]:
            walk(dst, path + (dst,), product * weight, seed)

    for source in sorted(visible):
        seed = query[source] * world.strength[source]
        if seed:
            walk(source, (source,), F(1), seed)
    return {"by_node": by_node, "by_length": by_length}


def fraction(value: F) -> str:
    return f"{value.numerator}/{value.denominator}"


def encode_map(values: Dict[str, F]) -> dict[str, str]:
    return {node: fraction(value) for node, value in values.items()}


def run() -> dict:
    world = assay_world()
    visible = visible_nodes(world)
    bound = contraction_bound(world, visible)
    total = neutralization_effect(world, QUERY, target="A")
    mediator = neutralization_effect(world, QUERY, target="B")
    partials = {str(hops): finite_walk_sum(world, QUERY, "A", hops)
                for hops in (0, 1, 2, 4, 8, 16)}
    equation_check = verify_fixed_point(world, QUERY, total["activation_with_target"])
    if not equation_check:
        raise AssertionError("fixed-point vector fails recurrence verification")
    return seal({
        "status": "EXECUTED_BOUNDED_SYNTHETIC_CYCLE_ASSAY",
        "epistemic_labels": {
            "OBSERVED": "Exact rational outputs and recurrence checks from this run.",
            "PROPOSED": "A contractive linear fixed-point model with signed edges represents the tested cyclic propagation semantics.",
            "INFERRED": "In this model, the infinite signed walk sum equals the exact fixed point, while every reported finite prefix leaves a residual.",
            "UNKNOWN": "Whether Raven, MNEME, or another agent follows these cyclic update semantics.",
        },
        "graph": {f"{src}->{dst}": fraction(weight)
                  for (src, dst), weight in sorted(world.links.items())},
        "query_seed": encode_map(QUERY),
        "absolute_incoming_weight_bound": fraction(bound),
        "fixed_point_equation_verified": equation_check,
        "predeclared_prediction": {
            "A_activation": "8/9",
            "B_activation": "4/9",
            "A_effect_on_C": "2/9",
            "D_effect_on_C_survives_A_neutralization": True,
            "finite_walk_prefix_equals_fixed_point": False,
        },
        "exp37_one_step_A_effect_by_node": encode_map(one_step_effect(world, QUERY, "A")),
        "fixed_point_A_effect_by_node": encode_map(total["delta_by_node"]),
        "fixed_point_A_effect_by_action": encode_map(total["delta_by_action"]),
        "fixed_point_A_effect_on_X_minus_Y_margin": fraction(total["delta_margin_X_minus_Y"]),
        "fixed_point_B_neutralization_effect_by_node": encode_map(mediator["delta_by_node"]),
        "finite_walk_prefixes_A_through_target": {
            hops: {
                "by_node": encode_map(result["by_node"]),
                "C_by_path_length": {str(length): fraction(value)
                                     for length, value in sorted(result["by_length"]["C"].items())},
            }
            for hops, result in partials.items()
        },
        "limits": "Exact linear rational system under strict contraction only; no nonlinear thresholds, saturation, time-varying updates, or Raven/MNEME claim.",
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
