#!/usr/bin/env python3
"""Exp47: characterize a minimal sufficient state in a finite toy model.

The candidate state is capped reinforcement count, association, link presence,
and recency age. The binary reinforcement flag is derived from count > 0.
Exhaustive collision checks are scoped to this model and its declared probes.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path

EXP46_RESULT = (Path(__file__).resolve().parents[1] /
                "exp46_h14_history_collisions" / "h14_exp46_run.json")
EXP46_SHA256 = "10e84c100d8ca3c9c74b723b051baf0b9ff39833c96ad8b7c37d953fdae70c36"
MAX_COUNT = 20
MAX_AGE = 3
ASSOCIATION_VALUES = tuple(F(i, 8) for i in range(9))
LINK_VALUES = (False, True)
AGE_VALUES = tuple(range(MAX_AGE + 1))
COUNT_VALUES = tuple(range(MAX_COUNT + 1))
INCREMENT = F(1, 8)
STALE_INCREMENT = F(1, 16)
THRESHOLD = F(1, 2)
BASE_SCORE = F(7, 10)
K_SCORE = F(3, 2)
C_SCORE_CHALLENGER = F(0)


@dataclass(frozen=True)
class State:
    reinforcement_count: int
    association: F
    link: bool
    recency_age: int

    @property
    def reinforced(self) -> bool:
        return self.reinforcement_count > 0


def verify_exp46() -> str:
    artifact = json.loads(EXP46_RESULT.read_text(encoding="utf-8"))
    digest = artifact.pop("sha256")
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
    actual = hashlib.sha256(canonical.encode()).hexdigest()
    if digest != EXP46_SHA256 or actual != digest:
        raise ValueError("Exp46 canonical artifact hash does not match the pinned value")
    return digest


def all_states() -> list[State]:
    return [State(count, association, link, age)
            for count, association, link, age in itertools.product(
                COUNT_VALUES, ASSOCIATION_VALUES, LINK_VALUES, AGE_VALUES)]


def construct_history(initial_association: F, paired_updates: int,
                      reinforcement_only_events: int = 0) -> tuple[State, dict]:
    association = initial_association
    count = 0
    for _ in range(paired_updates):
        association = min(F(1), association + INCREMENT)
        count = min(MAX_COUNT, count + 1)
    count = min(MAX_COUNT, count + reinforcement_only_events)
    state = State(count, association, True, 0)
    return state, {
        "initial_association": fraction(initial_association),
        "paired_updates": paired_updates,
        "reinforcement_only_events": reinforcement_only_events,
    }


def scalar_score(state: State) -> F:
    multiplier = F(1) + F(1, 20) * state.reinforcement_count
    return BASE_SCORE * multiplier


def transition(state: State, challenger_score: F) -> tuple[State, dict]:
    """One deterministic query; selecting C pairs C and D for reactivation."""
    c_score = scalar_score(state)
    choice = "C" if c_score > challenger_score else "K"
    count = state.reinforcement_count
    association = state.association
    age = state.recency_age
    if choice == "C":
        association = min(F(1), association + (STALE_INCREMENT if age > 2 else INCREMENT))
        count = min(MAX_COUNT, count + 1)
        age = 0
    else:
        age = min(MAX_AGE, age + 1)
    next_state = State(count, association, state.link, age)
    propagates = next_state.link and next_state.association >= THRESHOLD
    observation = {
        "choice": choice,
        "propagation": propagates,
        "causal_C_to_D": fraction(next_state.association if propagates else F(0)),
    }
    return next_state, observation


def run_schedule(state: State, schedule: tuple[F, ...]) -> tuple[State, tuple]:
    current = state
    initially_propagates = current.link and current.association >= THRESHOLD
    observations = [tuple(sorted({
        "step": 0,
        "propagation": initially_propagates,
        "causal_C_to_D": fraction(current.association if initially_propagates else F(0)),
    }.items()))]
    for challenger in schedule:
        current, observation = transition(current, challenger)
        observations.append(tuple(sorted(observation.items())))
    return current, tuple(observations)


def probe_schedules() -> tuple[tuple[F, ...], ...]:
    # Delay C reactivation by zero through three K wins, then select C.
    recency_probes = tuple((K_SCORE,) * delay + (C_SCORE_CHALLENGER,)
                           for delay in range(MAX_AGE + 1))
    # A midpoint query separates every adjacent scalar score level.
    count_probes = tuple(((scalar_score(State(count, F(0), True, 0))
                           + scalar_score(State(count + 1, F(0), True, 0))) / 2,)
                         for count in range(MAX_COUNT))
    return recency_probes + count_probes


def state_signature(state: State) -> tuple:
    return tuple(run_schedule(state, schedule)[1] for schedule in probe_schedules())


def collision_audit(states: list[State]) -> dict:
    names = ("reinforcement_count", "association", "link", "recency_age")
    audit = {}
    for omitted in names:
        groups: dict[tuple, list[tuple]] = {}
        for state in states:
            key = tuple((name, getattr(state, name)) for name in names if name != omitted)
            groups.setdefault(key, []).append(state_signature(state))
        disagreements = sum(len(set(signatures)) > 1 for signatures in groups.values())
        audit[omitted] = {
            "projection_groups": len(groups),
            "groups_with_observably_different_futures": disagreements,
            "necessary_for_exact_prediction_in_enumerated_domain": disagreements > 0,
        }
    return audit


def fraction(value: F) -> str:
    return f"{value.numerator}/{value.denominator}"


def encode(value):
    if isinstance(value, F):
        return fraction(value)
    if isinstance(value, State):
        return {"reinforcement_count": value.reinforcement_count,
                "reinforced": value.reinforced,
                "association": fraction(value.association),
                "link": value.link, "recency_age": value.recency_age}
    if isinstance(value, dict):
        return {key: encode(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    return value


def run() -> dict:
    exp46_hash = verify_exp46()
    states = all_states()
    schedules = probe_schedules()

    # Distinct experience paths converge on the same full candidate state.
    path_a, history_a = construct_history(F(0), 3)
    path_b, history_b = construct_history(F(1, 8), 2, reinforcement_only_events=1)
    histories_equal = path_a == path_b
    convergent_path_outputs_equal = all(
        run_schedule(path_a, schedule) == run_schedule(path_b, schedule)
        for schedule in schedules)

    audit = collision_audit(states)
    return {
        "experiment": "Exp47",
        "title": "Finite-domain characterization of a sufficient state",
        "status": "EXECUTED_SYNTHETIC_FINITE_DOMAIN_CHARACTERIZATION",
        "epistemic_status": {
            "OBSERVED": (
                "The pinned Exp46 artifact verified with canonical SHA256 " + exp46_hash +
                "; Exp46 used a scalar reinforcement count in a synthetic cross-assay."
            ),
            "PROPOSED": (
                "This assay defines a finite transition model with capped scalar count, "
                "association, link, and recency age. Scores, updates, thresholds, and "
                "probe schedules are declared toy semantics."
            ),
            "INFERRED": (
                "If all full-state collisions agree and omitting each candidate component "
                "creates at least one discrepant future in the exhaustive domain, the four "
                "component representation is sufficient and component-wise irreducible "
                "for exact prediction under this model and observation set."
            ),
            "UNKNOWN": (
                "Whether this representation is sufficient or minimal in Raven, MNEME, "
                "or any deployed agent memory system."
            ),
        },
        "source_provenance": {
            "exp46": {
                "path": "experiments/exp46_h14_history_collisions/h14_exp46_run.json",
                "canonical_sha256": exp46_hash,
                "use": "Anchors the four-field projection and candidate omitted count.",
            },
            "exp25": {
                "path": "experiments/exp25_state_amputation.py",
                "lines": "57-63, 96-104",
                "use": "Source for the capped scalar count and score multiplier form."
            },
        },
        "model": {
            "state_components": ["reinforcement_count_capped", "association", "link", "recency_age"],
            "reinforced_flag": "derived as reinforcement_count_capped > 0; not an independent component",
            "domain": {
                "reinforcement_count_capped": {"min": 0, "max": MAX_COUNT, "levels": len(COUNT_VALUES)},
                "association": {"values": [fraction(value) for value in ASSOCIATION_VALUES]},
                "link": {"values": list(LINK_VALUES)},
                "recency_age": {"min": 0, "max": MAX_AGE, "levels": len(AGE_VALUES)},
                "state_count": len(states),
            },
            "transition_rules": {
                "score_C": "7/10 * (1 + reinforcement_count_capped/20)",
                "select_C": "score_C > challenger_score; ties select K",
                "C_selected": "association += 1/8 if recency_age <= 2 else 1/16; count += 1 capped at 20; age = 0",
                "K_selected": "association and count unchanged; age += 1 capped at 3",
                "propagation": "link and association >= 1/2",
                "behavioral_observables": ["choice", "propagation", "causal_C_to_D"],
            },
            "probe_schedules": [[fraction(value) for value in schedule] for schedule in schedules],
        },
        "collision_audit": audit,
        "history_collision_control": {
            "history_a": history_a,
            "history_b": history_b,
            "converged_state": encode(path_a),
            "same_full_state": histories_equal,
            "same_future_outputs_for_all_probe_schedules": convergent_path_outputs_equal,
        },
        "verdict": {
            "sufficient_in_enumerated_model": histories_equal and convergent_path_outputs_equal,
            "all_four_components_necessary_in_enumerated_model": all(
                item["necessary_for_exact_prediction_in_enumerated_domain"]
                for item in audit.values()),
            "reinforcement_flag_is_redundant_given_count": True,
        },
        "limits": (
            "Exhaustive only over the declared 1,512 states and 24 probe schedules. "
            "Minimality is component-wise within this representation and observation set, "
            "not information-theoretic or universal. The full-state collision control "
            "covers two constructed histories; the transition implementation still "
            "defines the synthetic system. No Raven/MNEME code was executed."
        ),
    }


def canonical_json(data: dict) -> str:
    unsigned = json.dumps(encode(data), sort_keys=True, separators=(",", ":"))
    encoded = encode(data)
    encoded["sha256"] = hashlib.sha256(unsigned.encode()).hexdigest()
    return json.dumps(encoded, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("h14_exp47_run.json"))
    args = parser.parse_args()
    args.output.write_text(canonical_json(run()), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
