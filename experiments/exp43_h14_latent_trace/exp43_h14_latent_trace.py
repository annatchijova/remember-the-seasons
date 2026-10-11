#!/usr/bin/env python3
"""Exp43: can a latent C->D association recover function sooner?

This assay loads the exact post-washout states from Exp42, applies identical
externally cued C/D co-reactivation experiences, and runs a separate read-only
C-seeded propagation probe after each experience. The co-reactivation cue is
external, so it does not depend on the association being tested. All learning
and threshold semantics here are proposed synthetic rules.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction as F
from pathlib import Path

EXP42_RESULT = Path(__file__).resolve().parents[1] / "exp42_h14_longitudinal" / "h14_exp42_run.json"
EXP42_SHA256 = "ffd85a7ad396e029ceff5e0438b60dfb085c7b2b099760873ca52ce995a98cbd"
REACTIVATION_STEPS = 4
ASSOCIATION_INCREMENT = F(1, 8)
FAMILIARITY_INCREMENT = F(1, 4)
PROPAGATION_THRESHOLD = F(1, 2)


class State(str, Enum):
    NEUTRAL = "NEUTRAL"
    REINFORCED = "REINFORCED"


@dataclass
class LatentWorld:
    source_mode: str
    association: F
    familiarity_c: F
    familiarity_d: F
    state_c: State
    state_d: State


def parse_fraction(value: str) -> F:
    numerator, denominator = value.split("/", 1)
    return F(int(numerator), int(denominator))


def load_exp42_worlds() -> dict[str, LatentWorld]:
    data = json.loads(EXP42_RESULT.read_text(encoding="utf-8"))
    digest = data.pop("sha256")
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    computed = hashlib.sha256(canonical.encode()).hexdigest()
    if digest != EXP42_SHA256 or computed != digest:
        raise ValueError("Exp42 result hash does not match the pinned artifact")
    worlds = {}
    for mode in ("during_bfs", "post_bfs"):
        final = data["timeline_by_training_mode"][mode][-1]
        worlds[mode] = LatentWorld(
            source_mode=mode,
            association=parse_fraction(final["propagation_probe"]["C_to_D_association"]),
            familiarity_c=parse_fraction(final["familiarity"]["C"]),
            familiarity_d=parse_fraction(final["familiarity"]["D"]),
            state_c=State(final["states"]["C"]),
            state_d=State(final["states"]["D"]),
        )
    return worlds


def refresh_state(familiarity: F) -> State:
    return State.REINFORCED if familiarity >= F(1, 2) else State.NEUTRAL


def reactivation_experience(world: LatentWorld, pair_c_and_d: bool = True,
                            learning_enabled: bool = True) -> None:
    """External cues expose C and optionally D; then apply declared updates."""
    if not learning_enabled:
        return
    world.familiarity_c = min(F(1), world.familiarity_c + FAMILIARITY_INCREMENT)
    world.state_c = refresh_state(world.familiarity_c)
    if pair_c_and_d:
        world.familiarity_d = min(F(1), world.familiarity_d + FAMILIARITY_INCREMENT)
        world.state_d = refresh_state(world.familiarity_d)
        world.association = min(F(1), world.association + ASSOCIATION_INCREMENT)


def propagation_probe(world: LatentWorld) -> dict:
    enabled = world.association >= PROPAGATION_THRESHOLD
    # This is an isolated source-seed assay: C is supplied as the probe seed,
    # and only C->D transmission is under test.
    return {
        "C_seeded": True,
        "C_to_D_association": world.association,
        "threshold": PROPAGATION_THRESHOLD,
        "C_propagates_to_D": enabled,
        "D_candidate": enabled,
    }


def causal_effect(world: LatentWorld) -> dict:
    probe = propagation_probe(world)
    with_c = {"X": F(1), "Y": F(1, 4) + (world.association if probe["D_candidate"] else F(0))}
    c_suppressed = {"X": F(0), "Y": F(1, 4)}
    delta = {action: with_c[action] - c_suppressed[action] for action in ("X", "Y")}
    return {
        "delta_by_action": delta,
        "delta_margin_X_minus_Y": delta["X"] - delta["Y"],
        "score_with_C": with_c,
        "score_C_suppressed": c_suppressed,
    }


def fraction(value: F) -> str:
    return f"{value.numerator}/{value.denominator}"


def encode(value):
    if isinstance(value, F):
        return fraction(value)
    if isinstance(value, State):
        return value.value
    if isinstance(value, dict):
        return {key: encode(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [encode(item) for item in value]
    return value


def snapshot(world: LatentWorld, label: str, learning_enabled: bool = True) -> dict:
    return {
        "label": label,
        "learning_enabled": learning_enabled,
        "association_C_to_D": fraction(world.association),
        "familiarity": {"C": fraction(world.familiarity_c), "D": fraction(world.familiarity_d)},
        "states": {"C": world.state_c.value, "D": world.state_d.value},
        "propagation_probe": encode(propagation_probe(world)),
        "causal_C_effect": encode(causal_effect(world)),
    }


def trajectory(initial: LatentWorld, pair_c_and_d: bool = True,
               learning_enabled: bool = True) -> list[dict]:
    world = LatentWorld(**vars(initial))
    timeline = [snapshot(world, "post_washout_baseline", learning_enabled)]
    for index in range(1, REACTIVATION_STEPS + 1):
        reactivation_experience(world, pair_c_and_d, learning_enabled)
        timeline.append(snapshot(world, f"reactivation_{index}", learning_enabled))
    return timeline


def run() -> dict:
    initial = load_exp42_worlds()
    paired = {name: trajectory(world) for name, world in initial.items()}
    sham = {name: trajectory(world, pair_c_and_d=False) for name, world in initial.items()}

    # Equal-history control: clone the different source branches but overwrite
    # only their residual association before the exact same paired experience.
    equalized = {}
    for name, world in initial.items():
        clone = LatentWorld(**vars(world))
        clone.association = F(0)
        equalized[name] = trajectory(clone)

    return seal({
        "status": "EXECUTED_SYNTHETIC_LATENT_TRACE_RECOVERY_ASSAY",
        "epistemic_labels": {
            "OBSERVED": "The exact Exp42 post-washout values loaded from the hash-verified result, and the deterministic trajectories generated here.",
            "PROPOSED": "An external paired C/D reactivation increments their association by 1/8; propagation is enabled at association >= 1/2; the causal score oracle is synthetic.",
            "INFERRED": "Any earlier threshold crossing in the high-residual branch is caused by its different initial association under the declared equal updates; equal-history and sham controls test this explanation.",
            "UNKNOWN": "Whether an analogous latent trace or accelerated functional recovery occurs in Raven, MNEME, or deployed agents.",
        },
        "exp42_input": {
            "artifact": "experiments/exp42_h14_longitudinal/h14_exp42_run.json",
            "sha256": EXP42_SHA256,
            "source_branches": {
                name: {
                    "association_C_to_D": fraction(world.association),
                    "familiarity_C": fraction(world.familiarity_c),
                    "familiarity_D": fraction(world.familiarity_d),
                    "state_C": world.state_c.value,
                    "state_D": world.state_d.value,
                } for name, world in initial.items()
            },
        },
        "design": {
            "reactivation_event": "A common external cue pair presents C and D together; a separate C-seeded probe measures C->D transmission after the experience context is cleared.",
            "steps": REACTIVATION_STEPS,
            "association_increment_per_paired_experience": fraction(ASSOCIATION_INCREMENT),
            "familiarity_increment_per_presented_memory": fraction(FAMILIARITY_INCREMENT),
            "state_rule": "REINFORCED iff familiarity >= 1/2; otherwise NEUTRAL.",
            "propagation_threshold": fraction(PROPAGATION_THRESHOLD),
            "primary_falsifier": "The latent-trace recovery claim is falsified in this protocol if the high-residual branch does not regain C->D propagation before the zero-residual branch under the same paired experiences.",
            "controls": {
                "equalized_history": "Set both branches' C->D association to zero before the same paired reactivation schedule; their recovery timing should match.",
                "sham": "Present C without D; the declared pair-dependent rule predicts no association recovery in either branch.",
            },
        },
        "paired_reactivation": paired,
        "sham_reactivation": sham,
        "equalized_history_control": equalized,
        "limits": "A deterministic threshold model and hand-authored reactivation rule; no noisy retrieval, alternative learning rules, persistent memory engine, Raven runtime, MNEME, or human data.",
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
