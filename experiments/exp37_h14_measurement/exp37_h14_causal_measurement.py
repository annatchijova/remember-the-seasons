#!/usr/bin/env python3
"""Exp37: richer causal measurement for the H14 toy restoration assay.

This is a separate, deterministic, stdlib-only research harness. Exp36 remains
unchanged as the historical run. This assay freezes A-incident links during
functional absence and records signed action-score effects, not only choice
flips. It is not a Raven or MNEME implementation.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import dataclass, field
from fractions import Fraction as F
from typing import Dict, Tuple

NODES = ("A", "B", "C", "D")
QUERIES = (
    {"A": F(8, 10), "B": F(6, 10), "C": F(4, 10), "D": F(2, 10)},
    {"A": F(5, 10), "B": F(7, 10), "C": F(6, 10), "D": F(3, 10)},
    {"A": F(7, 10), "B": F(3, 10), "C": F(6, 10), "D": F(5, 10)},
    {"A": F(4, 10), "B": F(6, 10), "C": F(3, 10), "D": F(8, 10)},
)
ACTION = {"A": "X", "B": "Y", "C": "Y", "D": "X"}


@dataclass
class World:
    strength: Dict[str, F] = field(default_factory=lambda: {n: F(1) for n in NODES})
    links: Dict[Tuple[str, str], F] = field(default_factory=dict)
    available: set[str] = field(default_factory=lambda: set(NODES))
    prior_choice: str | None = None

    def clone(self) -> "World":
        return copy.deepcopy(self)


def base_world() -> World:
    world = World()
    world.strength.update({"A": F(3, 2), "B": F(1), "C": F(5, 4), "D": F(1)})
    world.links.update({("A", "B"): F(1, 3), ("B", "A"): F(1, 4),
                        ("A", "D"): F(1, 4), ("C", "A"): F(1, 3),
                        ("B", "C"): F(1, 5)})
    return world


def node_scores(world: World, query: Dict[str, F], neutralize: str | None = None) -> Dict[str, F]:
    visible = world.available - ({neutralize} if neutralize else set())
    scores = {node: F(0) for node in NODES}
    for node in visible:
        scores[node] += query[node] * world.strength[node]
    for (src, dst), weight in sorted(world.links.items()):
        if src in visible and dst in visible:
            scores[dst] += query[src] * world.strength[src] * weight
    return scores


def action_scores(world: World, query: Dict[str, F], neutralize: str | None = None) -> Dict[str, F]:
    by_node = node_scores(world, query, neutralize)
    return {action: sum((by_node[n] for n in NODES if ACTION[n] == action), F(0))
            for action in ("X", "Y")}


def choose(scores: Dict[str, F]) -> str:
    return "X" if scores["X"] >= scores["Y"] else "Y"


def causal_effect(world: World, query: Dict[str, F]) -> dict:
    """Controlled effect of A on each action score and on the score margin."""
    with_a = action_scores(world, query)
    without_a = action_scores(world, query, neutralize="A")
    delta = {action: with_a[action] - without_a[action] for action in ("X", "Y")}
    return {
        "with_A": with_a,
        "neutralized_A": without_a,
        "delta_by_action": delta,
        "delta_margin_X_minus_Y": delta["X"] - delta["Y"],
        "choice_with_A": choose(with_a),
        "choice_neutralized_A": choose(without_a),
    }


def measure(world: World) -> list[dict]:
    if "A" not in world.available:
        raise ValueError("causal measurement requires A to be available")
    return [causal_effect(world, query) for query in QUERIES]


def learn(world: World, query: Dict[str, F], frozen_link_nodes: frozenset[str] = frozenset()) -> None:
    scores = node_scores(world, query)
    eligible = sorted(world.available)
    if not eligible:
        return
    winner = min(eligible, key=lambda n: (-scores[n], n))
    world.strength[winner] = min(F(2), world.strength[winner] + F(1, 8))
    if world.prior_choice and world.prior_choice != winner:
        edge = (world.prior_choice, winner)
        if not (set(edge) & frozen_link_nodes):
            world.links[edge] = min(F(1, 2), world.links.get(edge, F(0)) + F(1, 16))
    world.prior_choice = winner


def suppress(world: World) -> None:
    world.available.discard("A")


def reinstate(world: World, historic: World, own_state: bool, edges: bool) -> None:
    world.available.add("A")
    world.strength["A"] = historic.strength["A"] if own_state else F(1)
    if edges or not own_state:
        for edge in tuple(world.links):
            if "A" in edge:
                del world.links[edge]
        if edges:
            for edge, value in historic.links.items():
                if "A" in edge:
                    world.links[edge] = value


def fraction(value: F) -> str:
    return f"{value.numerator}/{value.denominator}"


def encode_measurements(measurements: list[dict]) -> list[dict]:
    encoded = []
    for row in measurements:
        encoded.append({
            "with_A": {k: fraction(v) for k, v in row["with_A"].items()},
            "neutralized_A": {k: fraction(v) for k, v in row["neutralized_A"].items()},
            "delta_by_action": {k: fraction(v) for k, v in row["delta_by_action"].items()},
            "delta_margin_X_minus_Y": fraction(row["delta_margin_X_minus_Y"]),
            "choice_with_A": row["choice_with_A"],
            "choice_neutralized_A": row["choice_neutralized_A"],
        })
    return encoded


def run(absence_steps: int = 8, followup_steps: int = 12) -> dict:
    historic = base_world()
    for i in range(6):
        learn(historic, QUERIES[i % len(QUERIES)])
    before = historic.clone()
    no_absence = before.clone()
    absent = before.clone()
    suppress(absent)
    incident_links_at_absence = {e: v for e, v in absent.links.items() if "A" in e}
    for i in range(absence_steps):
        query = QUERIES[(i + 1) % len(QUERIES)]
        learn(no_absence, query)
        learn(absent, query, frozen_link_nodes=frozenset({"A"}))
    incident_links_after_absence = {e: v for e, v in absent.links.items() if "A" in e}
    if incident_links_after_absence != incident_links_at_absence:
        raise AssertionError("A-incident links changed during functional absence")

    baseline = absent.clone()
    arms = {"no_absence": no_absence, "reexposure": baseline.clone(),
            "strict": baseline.clone(), "links_only": baseline.clone(),
            "state_and_links": baseline.clone(), "relearning": baseline.clone()}
    reinstate(arms["reexposure"], before, False, False)
    reinstate(arms["strict"], before, True, False)
    reinstate(arms["links_only"], before, False, True)
    reinstate(arms["state_and_links"], before, True, True)
    reinstate(arms["relearning"], before, False, False)

    initial = {name: encode_measurements(measure(w)) for name, w in arms.items()}
    for i in range(followup_steps):
        query = QUERIES[(i + absence_steps + 1) % len(QUERIES)]
        for name, world in arms.items():
            learn(world, query)
            if name == "relearning" and i in (0, 3, 6, 9):
                world.strength["A"] = min(F(2), world.strength["A"] + F(1, 8))
                peer = world.prior_choice
                if peer is not None and peer != "A":
                    edge = ("A", peer)
                    world.links[edge] = min(F(1, 2), world.links.get(edge, F(0)) + F(1, 16))
    final = {name: encode_measurements(measure(w)) for name, w in arms.items()}
    return seal({
        "status": "EXECUTED_TOY_ASSAY_NOT_RAVEN",
        "absence_steps": absence_steps,
        "followup_steps": followup_steps,
        "query_count": len(QUERIES),
        "arms": list(arms),
        "absence_link_policy": "freeze_all_A_incident_links_at_pre_absence_values",
        "incident_links_unchanged_during_absence": incident_links_after_absence == incident_links_at_absence,
        "measurement": "exact_fraction_action_score_deltas_plus_signed_X_minus_Y_margin_and_choices",
        "initial": initial,
        "final": final,
        "limits": "One deterministic synthetic configuration; no Raven/MNEME equivalence or statistical generalization claimed.",
    })


def seal(payload: dict) -> dict:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return {**payload, "sha256": hashlib.sha256(canonical.encode()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--absence", type=int, default=8)
    parser.add_argument("--followup", type=int, default=12)
    parser.add_argument("--output", help="write JSON to this path instead of stdout")
    args = parser.parse_args()
    if args.absence < 1 or args.followup < 0:
        parser.error("--absence >= 1 and --followup >= 0 required")
    rendered = json.dumps(run(args.absence, args.followup), indent=2, sort_keys=True) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as stream:
            stream.write(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
