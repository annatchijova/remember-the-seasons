#!/usr/bin/env python3
"""Exp45: minimum state needed to predict causal recovery in a toy assay.

This is a 2^4 factorial over a persistent reinforcement flag, C->D association,
structural link, and recency. Matched states receive identical paired C/D
reactivation experiences. Leave-one-component-out collisions test whether the
remaining representation can predict the recovery trajectory. The update
rules are proposed H14 toy semantics, informed by the dimensions in Exp25;
they are not an implementation of Exp25, Raven, or MNEME.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path

EXP43_RESULT = Path(__file__).resolve().parents[1] / "exp43_h14_latent_trace" / "h14_exp43_run.json"
EXP43_SHA256 = "40070dc233cb54abd31a630637b4fa13fa7ad1e1a35e00ce2df705b54ac6cadb"
STEPS = 12
THRESHOLD = F(1, 2)
REINFORCED_INCREMENT = F(1, 8)
NEUTRAL_INCREMENT = F(1, 16)
STALE_AGE = 3
RECENCY_WINDOW = 2
COMPONENTS = ("reinforcement", "association", "link", "recency")


def parse_fraction(value: str) -> F:
    numerator, denominator = value.split("/", 1)
    return F(int(numerator), int(denominator))


@dataclass(frozen=True)
class InitialState:
    reinforced: bool
    association: F
    link_present: bool
    recency_age: int


def pinned_exp43_values() -> dict[str, F]:
    data = json.loads(EXP43_RESULT.read_text(encoding="utf-8"))
    digest = data.pop("sha256")
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    if digest != EXP43_SHA256 or hashlib.sha256(canonical.encode()).hexdigest() != digest:
        raise ValueError("Exp43 result hash does not match the pinned artifact")
    return {
        "residual_association": parse_fraction(
            data["exp42_input"]["source_branches"]["during_bfs"]["association_C_to_D"]),
        "no_residual_association": parse_fraction(
            data["exp42_input"]["source_branches"]["post_bfs"]["association_C_to_D"]),
    }


def make_factorial() -> list[InitialState]:
    associations = tuple(pinned_exp43_values().values())
    return [InitialState(reinforced, association, link, age)
            for reinforced, association, link, age in itertools.product(
                (False, True), associations, (False, True), (0, STALE_AGE))]


def predicted_output(state: InitialState) -> dict:
    """Simulate a common reactivation schedule and exact causal readout."""
    reinforced = state.reinforced
    association = state.association
    age = state.recency_age
    first_recovery = 0 if state.link_present and association >= THRESHOLD else None
    timeline = [{
        "step": 0,
        "reinforced": reinforced,
        "association": association,
        "link_present": state.link_present,
        "recency_age": age,
        "propagation": state.link_present and association >= THRESHOLD,
        "causal_C_to_D": association if state.link_present and association >= THRESHOLD else F(0),
    }]

    for step in range(1, STEPS + 1):
        increment = REINFORCED_INCREMENT if reinforced else NEUTRAL_INCREMENT
        if age > RECENCY_WINDOW:
            increment /= 2
        association = min(F(1), association + increment)
        # The same paired reactivation is also a retrieval event: the binary
        # flag persists after its first update, following Exp25's abstraction.
        reinforced = True
        age = 0
        propagation = state.link_present and association >= THRESHOLD
        if propagation and first_recovery is None:
            first_recovery = step
        timeline.append({
            "step": step,
            "reinforced": reinforced,
            "association": association,
            "link_present": state.link_present,
            "recency_age": age,
            "propagation": propagation,
            "causal_C_to_D": association if propagation else F(0),
        })

    return {"first_recovery_step": first_recovery, "timeline": timeline}


def encode(value):
    if isinstance(value, F):
        return f"{value.numerator}/{value.denominator}"
    if isinstance(value, dict):
        return {key: encode(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [encode(item) for item in value]
    return value


def observable_signature(output: dict) -> tuple:
    return (output["first_recovery_step"],
            tuple((point["propagation"], point["causal_C_to_D"])
                  for point in output["timeline"]))


def component_collision_audit(cases: list[tuple[InitialState, dict]]) -> dict:
    audit = {}
    for omitted in COMPONENTS:
        keys_and_signatures = {}
        for state, output in cases:
            key = tuple((name, getattr(state, {
                "reinforcement": "reinforced",
                "association": "association",
                "link": "link_present",
                "recency": "recency_age",
            }[name])) for name in COMPONENTS if name != omitted)
            keys_and_signatures.setdefault(key, []).append(observable_signature(output))
        disagreeing = sum(1 for signatures in keys_and_signatures.values()
                          if len(set(signatures)) > 1)
        audit[omitted] = {
            "projected_state_count": len(keys_and_signatures),
            "collision_groups_with_different_recovery_trajectories": disagreeing,
            "necessary_for_exact_prediction_in_sample": disagreeing > 0,
        }
    return audit


def fraction(value: F) -> str:
    return f"{value.numerator}/{value.denominator}"


def run() -> dict:
    states = make_factorial()
    cases = [(state, predicted_output(state)) for state in states]
    encoded_cases = []
    for state, output in cases:
        encoded_cases.append({
            "initial_state": {
                "reinforcement": state.reinforced,
                "association": fraction(state.association),
                "link_present": state.link_present,
                "recency_age": state.recency_age,
            },
            "first_recovery_step": output["first_recovery_step"],
            "timeline": encode(output["timeline"]),
        })
    return seal({
        "status": "EXECUTED_SYNTHETIC_MINIMUM_STATE_ASSAY",
        "epistemic_labels": {
            "OBSERVED": "The 16 factorial states, exact recovery trajectories, and ablation-collision counts generated by this harness.",
            "PROPOSED": "The update increments, recency discount, persistent binary reinforcement update, fixed structural link, and 1/2 propagation threshold are this assay's declared rules.",
            "INFERRED": "A component is necessary for exact prediction in this sampled model when omitting it merges states with different recovery trajectories under the same future schedule.",
            "UNKNOWN": "Whether these four components or update rules are necessary or sufficient in Raven, MNEME, or deployed agent memory.",
        },
        "exp25_connection": {
            "source": "experiments/exp25_state_amputation.py",
            "source_lines": "8-43, 57-63, 96-113",
            "observed_scope": "Exp25 varies binary/scalar reinforcement, accumulating/last-touch history, and persistence in a retrieval-ranking assay; it does not test H14 association or topology restoration.",
            "reuse": "Exp45 includes a persistent binary reinforcement flag and a recency field as explicit factors, without importing Exp25's ranking engine or claiming equivalent semantics.",
        },
        "exp43_anchor": {
            "artifact": "experiments/exp43_h14_latent_trace/h14_exp43_run.json",
            "sha256": EXP43_SHA256,
            "association_values_used": {"residual": "3/8", "no_residual": "0/1"},
        },
        "design": {
            "factorial_dimensions": {
                "reinforcement": [False, True],
                "association": ["0/1", "3/8"],
                "link": [False, True],
                "recency_age": [0, STALE_AGE],
            },
            "all_memories_available_for_external_C_D_reactivation": True,
            "paired_experience_schedule": STEPS,
            "propagation_threshold": fraction(THRESHOLD),
            "increments": {
                "reinforced": fraction(REINFORCED_INCREMENT),
                "neutral": fraction(NEUTRAL_INCREMENT),
                "stale_first_experience_multiplier": "1/2",
            },
            "recency_rule": f"If age > {RECENCY_WINDOW}, halve the first update; paired reactivation then resets age to 0.",
            "reinforcement_rule": "A paired reactivation changes NEUTRAL to REINFORCED; the flag then persists for this trajectory.",
            "link_rule": "The structural link is held fixed during this assay; paired reactivation updates association weight but does not recreate a deleted link.",
            "primary_falsifier": "A dropped component is not necessary for exact prediction in this sampled protocol if every pair of full states collapsed by its ablation has the same recovery step and causal-effect trajectory.",
        },
        "factorial_cases": encoded_cases,
        "leave_one_component_out": component_collision_audit(cases),
        "limits": "A deterministic, hand-built 2^4 model. Necessity is conditional on the sampled values and declared dynamics; this is not an information-theoretic minimum, a Raven/MNEME validation, or evidence of a biological mechanism.",
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
