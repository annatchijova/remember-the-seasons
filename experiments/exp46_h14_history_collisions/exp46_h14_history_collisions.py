#!/usr/bin/env python3
"""Exp46: test whether Exp45's four-field projection predicts future paths.

Two distinct synthetic histories converge on the same Exp45 state but retain
different scalar reinforcement counts. Identical future queries are then
evaluated under binary and scalar ranking variants. This is a cross-assay toy
falsifier, not a Raven, MNEME, or deployed-agent experiment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from fractions import Fraction as F
from pathlib import Path

EXP45_RESULT = (Path(__file__).resolve().parents[1] /
                "exp45_h14_sufficient_state" / "h14_exp45_run.json")
EXP45_SHA256 = "427e502fbb0ec443685302cd161691bd3c9dc70b861cd5badf1fd03d6e5a1acd"
ASSOCIATION_INCREMENT = F(1, 8)
PROPAGATION_THRESHOLD = F(1, 2)
BASE_SCORE_C = F(7, 10)
BASE_SCORE_K = F(4, 5)
FUTURE_QUERIES = 4


@dataclass(frozen=True)
class ProjectedState:
    reinforcement: bool
    association: F
    link: bool
    recency: int


@dataclass(frozen=True)
class FullState:
    projected: ProjectedState
    reinforcement_count: int


def verify_exp45() -> str:
    artifact = json.loads(EXP45_RESULT.read_text(encoding="utf-8"))
    digest = artifact.pop("sha256")
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
    observed = hashlib.sha256(canonical.encode()).hexdigest()
    if digest != EXP45_SHA256 or observed != digest:
        raise ValueError("Exp45 canonical artifact hash does not match the pinned value")
    return digest


def make_history(initial_association: F, paired_reactivations: int) -> tuple[FullState, dict]:
    """Apply proposed paired experiences; count is retained as omitted state."""
    association = initial_association
    count = 0
    for _ in range(paired_reactivations):
        association = min(F(1), association + ASSOCIATION_INCREMENT)
        count += 1
    projected = ProjectedState(True, association, True, 0)
    return FullState(projected, count), {
        "initial_association": fraction(initial_association),
        "paired_reactivations": paired_reactivations,
    }


def score_c(state: FullState, variant: str) -> F:
    if variant == "binary":
        multiplier = F(3, 2) if state.projected.reinforcement else F(1)
    elif variant == "scalar":
        multiplier = F(1) + F(1, 20) * min(state.reinforcement_count, 20)
    else:
        raise ValueError(f"unsupported ranking variant: {variant}")
    return BASE_SCORE_C * multiplier


def simulate(state: FullState, variant: str) -> dict:
    association = state.projected.association
    count = state.reinforcement_count
    timeline = []
    for step in range(1, FUTURE_QUERIES + 1):
        c_score = score_c(FullState(state.projected, count), variant)
        choice = "C" if c_score > BASE_SCORE_K else "K"
        if choice == "C":
            association = min(F(1), association + ASSOCIATION_INCREMENT)
            count += 1
        propagates = state.projected.link and association >= PROPAGATION_THRESHOLD
        timeline.append({
            "step": step,
            "score_C": fraction(c_score),
            "score_K": fraction(BASE_SCORE_K),
            "choice": choice,
            "association_C_to_D": fraction(association),
            "reinforcement_count": count,
            "propagation_C_to_D": propagates,
            "causal_C_to_D": fraction(association if propagates else F(0)),
        })
    return {"variant": variant, "timeline": timeline}


def fraction(value: F) -> str:
    return f"{value.numerator}/{value.denominator}"


def trajectory_signature(result: dict) -> tuple:
    return tuple((row["choice"], row["association_C_to_D"],
                  row["propagation_C_to_D"], row["causal_C_to_D"])
                 for row in result["timeline"])


def run() -> dict:
    exp45_hash = verify_exp45()
    low, low_history = make_history(F(1, 4), 1)
    high, high_history = make_history(F(0), 3)
    matched_a, matched_history_a = make_history(F(1, 4), 1)
    matched_b, matched_history_b = make_history(F(1, 4), 1)

    projected_low = asdict(low.projected)
    projected_high = asdict(high.projected)
    assert projected_low == projected_high
    assert low.reinforcement_count != high.reinforcement_count

    branches = {"short_history": low, "long_history": high}
    results = {}
    for variant in ("binary", "scalar"):
        results[variant] = {
            name: simulate(state, variant) for name, state in branches.items()
        }
    results["scalar_equal_count_control"] = {
        "history_a": simulate(matched_a, "scalar"),
        "history_b": simulate(matched_b, "scalar"),
    }

    binary_equal = (trajectory_signature(results["binary"]["short_history"])
                    == trajectory_signature(results["binary"]["long_history"]))
    scalar_diverges = (trajectory_signature(results["scalar"]["short_history"])
                       != trajectory_signature(results["scalar"]["long_history"]))
    matched_equal = (trajectory_signature(results["scalar_equal_count_control"]["history_a"])
                     == trajectory_signature(results["scalar_equal_count_control"]["history_b"]))

    data = {
        "experiment": "Exp46",
        "title": "History collisions under a four-field state projection",
        "status": "EXECUTED_SYNTHETIC_CROSS_ASSAY_FALSIFIER",
        "epistemic_status": {
            "OBSERVED": (
                "Exp25 stores a scalar reinforcement count and defines binary and scalar "
                "score boosts in experiments/exp25_state_amputation.py:57-63,96-104; "
                "its trajectory reinforces the top recalled memory at lines 215-217. "
                "Exp45's pinned artifact has canonical SHA256 " + exp45_hash + "."
            ),
            "PROPOSED": (
                "The two history generators, paired-association update, two-item ranking "
                "harness, downstream propagation threshold, and causal readout are this "
                "assay's synthetic bridge between Exp45 and Exp25."
            ),
            "INFERRED": (
                "If the identical projected states diverge only when the Exp25 scalar "
                "count semantics are retained, the four fields are insufficient across "
                "these two declared ranking semantics; an omitted count predicts the split."
            ),
            "UNKNOWN": (
                "Whether Raven, MNEME, or deployed agent memory retains this count or "
                "follows any of these cross-assay dynamics."
            ),
        },
        "source_provenance": {
            "exp25": {
                "path": "experiments/exp25_state_amputation.py",
                "lines": "57-63, 96-104, 215-217",
                "use": "Scalar count field, binary/scalar boost definitions, top-result reinforcement.",
            },
            "exp45": {
                "path": "experiments/exp45_h14_sufficient_state/h14_exp45_run.json",
                "canonical_sha256": exp45_hash,
                "use": "Pinned four-field state schema and scoped sufficiency result.",
            },
        },
        "design": {
            "projected_fields": ["reinforcement", "association", "link", "recency"],
            "shared_projected_state": {
                "reinforcement": True,
                "association": "3/8",
                "link": True,
                "recency": 0,
            },
            "history_generators": {
                "short_history": {**low_history, "reinforcement_count": low.reinforcement_count},
                "long_history": {**high_history, "reinforcement_count": high.reinforcement_count},
            },
            "future_schedule": {
                "queries": FUTURE_QUERIES,
                "base_score_C": fraction(BASE_SCORE_C),
                "base_score_K": fraction(BASE_SCORE_K),
                "paired_experience_when_C_selected": fraction(ASSOCIATION_INCREMENT),
                "propagation_threshold": fraction(PROPAGATION_THRESHOLD),
            },
            "exp25_semantics": {
                "binary_multiplier": "3/2 iff count > 0",
                "scalar_multiplier": "1 + (1/20) * min(count, 20)",
            },
        },
        "results": results,
        "controls": {
            "same_projected_state": projected_low == projected_high,
            "different_history_counts": low.reinforcement_count != high.reinforcement_count,
            "binary_trajectories_equal": binary_equal,
            "scalar_trajectories_diverge": scalar_diverges,
            "equal_count_control_trajectories_equal": matched_equal,
            "first_scalar_divergence_step": 1 if scalar_diverges else None,
            "first_scalar_divergence_has_causal_propagation_split": (
                results["scalar"]["short_history"]["timeline"][0]["propagation_C_to_D"]
                != results["scalar"]["long_history"]["timeline"][0]["propagation_C_to_D"]
            ),
        },
        "limits": (
            "This is a deterministic synthetic cross-assay harness, not an Exp25 rerun "
            "and not Raven/MNEME validation. Its histories and association updates are "
            "proposed. The finding is conditional on the Exp25 scalar ranking formula "
            "and the declared toy downstream threshold. Equal histories under a different "
            "update rule may erase the divergence."
        ),
    }
    return data


def canonical_json(data: dict) -> str:
    unsigned = json.dumps(data, sort_keys=True, separators=(",", ":"))
    data["sha256"] = hashlib.sha256(unsigned.encode()).hexdigest()
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("h14_exp46_run.json"))
    args = parser.parse_args()
    args.output.write_text(canonical_json(run()), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
