#!/usr/bin/env python3
"""Exp42: longitudinal rescue timing, shared experiences, and washout.

Three clones receive the same four A/R-cued experiences under the Exp41
rescue policies, then the same five washout experiences under post-BFS rescue.
The model updates node familiarity from BFS processing and a C->D association
from co-processing. These are explicit synthetic rules, not Raven or MNEME
semantics. A no-learning run is the negative control for persistence.
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
SEEDS = {"A": F(1), "R": F(1)}
TRAINING_STEPS = 4
WASHOUT_STEPS = 5
REINFORCEMENT = F(1, 4)
FAMILIARITY_DECAY = F(1, 8)
ASSOCIATION_INCREMENT = F(1, 8)
ASSOCIATION_DECAY = F(1, 8)
PROPAGATION_THRESHOLD = F(1, 2)
MODES = ("disabled", "post_bfs", "during_bfs")


class State(str, Enum):
    NEUTRAL = "NEUTRAL"
    REINFORCED = "REINFORCED"


@dataclass
class World:
    familiarity: Dict[str, F] = field(default_factory=lambda: {node: F(0) for node in NODES})
    states: Dict[str, State] = field(default_factory=lambda: {node: State.NEUTRAL for node in NODES})
    neighbors: Dict[str, Set[str]] = field(default_factory=lambda: {node: set() for node in NODES})
    inhibitory_links: Set[Tuple[str, str]] = field(default_factory=set)
    cd_association: F = F(1, 2)


def initial_world() -> World:
    world = World()
    world.familiarity["C"] = F(1)
    world.states["C"] = State.REINFORCED
    for left, right in (("A", "B"), ("R", "X"), ("X", "Y"), ("Y", "C")):
        world.neighbors[left].add(right)
        world.neighbors[right].add(left)
    world.inhibitory_links.add(("B", "C"))
    return world


def recall(world: World, mode: str, seeds: Dict[str, F] = SEEDS,
           hops: int = 4, suppressed: frozenset[str] = frozenset()) -> dict:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if hops < 0:
        raise ValueError("hops must be >= 0")
    if set(seeds) - set(NODES) or suppressed - set(NODES):
        raise ValueError("unknown node in seeds or suppression")

    frontier = {node for node, score in seeds.items() if score > 0 and node not in suppressed}
    activated: set[str] = set()
    processed: set[str] = set()
    inhibited: set[str] = set()
    rescued: set[str] = set()
    for _depth in range(hops + 1):
        following: set[str] = set()
        for node in sorted(frontier):
            if node in inhibited or node in suppressed:
                continue
            activated.add(node)
            processed.add(node)
            for neighbor in sorted(world.neighbors[node]):
                if neighbor not in suppressed:
                    following.add(neighbor)
            if node == "C" and world.cd_association >= PROPAGATION_THRESHOLD and "D" not in suppressed:
                following.add("D")
            for src, dst in sorted(world.inhibitory_links):
                if src == node and dst not in suppressed:
                    inhibited.add(dst)
                    if mode == "during_bfs" and world.states[dst] == State.REINFORCED:
                        inhibited.discard(dst)
                        rescued.add(dst)
                        following.add(dst)
        frontier = following - activated - inhibited - set(suppressed)

    if mode == "post_bfs":
        for node in sorted(inhibited):
            if world.states[node] == State.REINFORCED:
                inhibited.discard(node)
                activated.add(node)
                rescued.add(node)
    candidates = {node for node in activated if node not in inhibited}
    return {
        "activated": activated,
        "processed": processed,
        "inhibited": inhibited,
        "rescued": rescued,
        "candidates": candidates,
    }


def score(result: dict, world: World) -> dict[str, F]:
    candidates = result["candidates"]
    return {
        "X": F(1) if "C" in candidates else F(0),
        "Y": F(1, 4) + (world.cd_association if "D" in candidates else F(0)),
    }


def causal_effect(world: World, mode: str) -> dict:
    full = recall(world, mode)
    without_c = recall(world, mode, suppressed=frozenset({"C"}))
    full_score = score(full, world)
    control_score = score(without_c, world)
    delta = {name: full_score[name] - control_score[name] for name in ("X", "Y")}
    return {
        "delta_by_action": delta,
        "delta_margin_X_minus_Y": delta["X"] - delta["Y"],
        "C_candidate": "C" in full["candidates"],
        "C_processed": "C" in full["processed"],
        "D_activated": "D" in full["activated"],
        "score_with_C": full_score,
        "score_C_suppressed": control_score,
    }


def propagation_probe(world: World) -> dict:
    """Read-only standardized probe of C->D transmission after each checkpoint."""
    active = world.cd_association >= PROPAGATION_THRESHOLD
    return {
        "C_to_D_association": world.cd_association,
        "threshold": PROPAGATION_THRESHOLD,
        "C_can_propagate_to_D": active,
        "D_reached_when_C_is_standardized_seed": active,
    }


def apply_experience(world: World, result: dict, washout: bool,
                     learning_enabled: bool = True) -> None:
    if not learning_enabled:
        return
    processed = result["processed"]
    for node in NODES:
        if node in processed:
            world.familiarity[node] = min(F(1), world.familiarity[node] + REINFORCEMENT)
        elif washout:
            world.familiarity[node] = max(F(0), world.familiarity[node] - FAMILIARITY_DECAY)
        world.states[node] = (State.REINFORCED
                              if world.familiarity[node] >= F(1, 2)
                              else State.NEUTRAL)

    if "C" in processed and "D" in processed:
        world.cd_association = min(F(1), world.cd_association + ASSOCIATION_INCREMENT)
    elif washout:
        world.cd_association = max(F(0), world.cd_association - ASSOCIATION_DECAY)


def fraction(value: F) -> str:
    return f"{value.numerator}/{value.denominator}"


def encode(value):
    if isinstance(value, F):
        return fraction(value)
    if isinstance(value, State):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, dict):
        return {key: encode(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    return value


def checkpoint(world: World, label: str, mode: str, learning_enabled: bool) -> dict:
    outcome = recall(world, mode)
    return {
        "label": label,
        "mode": mode,
        "learning_enabled": learning_enabled,
        "recall": encode(outcome),
        "causal_C_effect": encode(causal_effect(world, mode)),
        "propagation_probe": encode(propagation_probe(world)),
        "states": encode(world.states),
        "familiarity": encode(world.familiarity),
    }


def simulate(mode: str, learning_enabled: bool = True) -> dict:
    world = initial_world()
    timeline = [checkpoint(world, "baseline", mode, learning_enabled)]
    for index in range(1, TRAINING_STEPS + 1):
        result = recall(world, mode)
        apply_experience(world, result, washout=False, learning_enabled=learning_enabled)
        timeline.append(checkpoint(world, f"training_{index}", mode, learning_enabled))
    for index in range(1, WASHOUT_STEPS + 1):
        result = recall(world, "post_bfs")
        apply_experience(world, result, washout=True, learning_enabled=learning_enabled)
        timeline.append(checkpoint(world, f"washout_{index}", "post_bfs", learning_enabled))
    return {"timeline": timeline, "final_world": world}


def run() -> dict:
    runs = {mode: simulate(mode) for mode in MODES}
    control_runs = {mode: simulate(mode, learning_enabled=False) for mode in MODES}
    final = {mode: run_data["timeline"][-1] for mode, run_data in runs.items()}
    control_final = {mode: run_data["timeline"][-1] for mode, run_data in control_runs.items()}
    return seal({
        "status": "EXECUTED_SYNTHETIC_LONGITUDINAL_ASSAY",
        "epistemic_labels": {
            "OBSERVED": "The exact deterministic trajectories and readouts generated by this synthetic harness.",
            "PROPOSED": "Experience consolidation, association strengthening, decay, and the washout schedule are model rules, not Raven/MNEME behavior.",
            "INFERRED": "Any trajectory divergence follows from the declared processing-dependent update rules; the no-learning control tests whether those rules create the persistence.",
            "UNKNOWN": "Whether comparable longitudinal effects occur in Raven, MNEME, or deployed agents.",
        },
        "design": {
            "common_start": "Deep copies of the Exp41 topology and memory state.",
            "common_training_sequence": ["A/R cue experience"] * TRAINING_STEPS,
            "common_washout_sequence": ["A/R cue experience under post_bfs"] * WASHOUT_STEPS,
            "training_modes": list(MODES),
            "familiarity_update_per_processed_experience": fraction(REINFORCEMENT),
            "washout_familiarity_decay_when_not_processed": fraction(FAMILIARITY_DECAY),
            "C_to_D_association_increment_when_both_processed": fraction(ASSOCIATION_INCREMENT),
            "C_to_D_association_washout_decay": fraction(ASSOCIATION_DECAY),
            "propagation_threshold": fraction(PROPAGATION_THRESHOLD),
            "state_rule": "REINFORCED iff familiarity >= 1/2; otherwise NEUTRAL.",
            "falsification_criterion": "The longitudinal distinction fails if during_bfs and post_bfs do not diverge in propagation capacity during training, or if the operational capacity difference vanishes at washout_1. Persistence is supported only while the standardized C->D probe remains different after treatment is removed.",
            "washout_interpretation": "Treatment timing is removed; all branches receive the post_bfs policy. Read-only standardized propagation probes do not mutate state.",
        },
        "timeline_by_training_mode": {
            mode: run_data["timeline"] for mode, run_data in runs.items()
        },
        "final_washout_comparison": {
            mode: {
                "cd_association": final[mode]["propagation_probe"]["C_to_D_association"],
                "propagation_enabled": final[mode]["propagation_probe"]["C_can_propagate_to_D"],
                "D_state": final[mode]["states"]["D"],
                "D_familiarity": final[mode]["familiarity"]["D"],
                "C_causal_effect": final[mode]["causal_C_effect"],
            } for mode in MODES
        },
        "no_learning_negative_control": {
            "purpose": "Check whether a persistent state/association difference appears without the declared experience updates.",
            "final_by_training_mode": {
                mode: {
                    "cd_association": control_final[mode]["propagation_probe"]["C_to_D_association"],
                    "propagation_enabled": control_final[mode]["propagation_probe"]["C_can_propagate_to_D"],
                    "states": control_final[mode]["states"],
                    "familiarity": control_final[mode]["familiarity"],
                } for mode in MODES
            },
        },
        "limits": "Deterministic hand-built graph and update rules; no stochasticity, agent decisions, persistent external memory engine, Raven runtime, or MNEME integration. The numerical persistence is a property of this declared model until tested elsewhere.",
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
