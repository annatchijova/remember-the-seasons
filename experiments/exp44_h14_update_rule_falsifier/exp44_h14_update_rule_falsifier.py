#!/usr/bin/env python3
"""Exp44: test whether Exp43's recovery lead survives update-rule changes.

The hash-verified Exp43 post-washout associations are replayed through four
declared synthetic update rules. This assay asks whether the high-residual
branch's earlier threshold crossing is robust, and whether any advantage
remains after the initial scalar association is equalized.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

EXP43_RESULT = Path(__file__).resolve().parents[1] / "exp43_h14_latent_trace" / "h14_exp43_run.json"
EXP43_SHA256 = "40070dc233cb54abd31a630637b4fa13fa7ad1e1a35e00ce2df705b54ac6cadb"
INITIALS = ("during_bfs", "post_bfs")
THRESHOLD = F(1, 2)
EVIDENCE = F(1, 8)
ALPHA = F(1, 4)
MAX_STEPS = 12


def parse_fraction(value: str) -> F:
    numerator, denominator = value.split("/", 1)
    return F(int(numerator), int(denominator))


def load_initials() -> dict[str, F]:
    data = json.loads(EXP43_RESULT.read_text(encoding="utf-8"))
    digest = data.pop("sha256")
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    computed = hashlib.sha256(canonical.encode()).hexdigest()
    if digest != EXP43_SHA256 or computed != digest:
        raise ValueError("Exp43 result hash does not match the pinned artifact")
    return {
        "during_bfs": parse_fraction(data["exp42_input"]["source_branches"]["during_bfs"]["association_C_to_D"]),
        "post_bfs": parse_fraction(data["exp42_input"]["source_branches"]["post_bfs"]["association_C_to_D"]),
    }


def update(rule: str, association: F, exposure_count: int) -> F:
    if rule == "additive_fixed":
        return min(F(1), association + EVIDENCE)
    if rule == "proportional_saturating":
        return association + (F(1) - association) * ALPHA
    if rule == "history_reset_additive":
        # The caller supplies session-local cumulative exposure count. This
        # rule discards the incoming value and relearns only within this run.
        return min(F(1), F(exposure_count) * EVIDENCE)
    if rule == "evidence_average":
        # Each paired experience contributes an evidence estimate of 1/8;
        # update by averaging current value and the new estimate.
        return (association + EVIDENCE) / 2
    raise ValueError(f"unknown rule: {rule}")


RULES = ("additive_fixed", "proportional_saturating",
         "history_reset_additive", "evidence_average")


def row(step: int, association: F) -> dict:
    return {
        "step": step,
        "association_C_to_D": association,
        "distance_to_threshold": max(F(0), THRESHOLD - association),
        "propagation_enabled": association >= THRESHOLD,
        "causal_C_effect_on_Y": association if association >= THRESHOLD else F(0),
    }


def run_trajectory(rule: str, start: F, paired: bool = True,
                   equalize_at_start: bool = False) -> list[dict]:
    association = F(0) if equalize_at_start else start
    timeline = [row(0, association)]
    for step in range(1, MAX_STEPS + 1):
        if paired:
            association = update(rule, association, step)
        timeline.append(row(step, association))
    return timeline


def fraction(value: F) -> str:
    return f"{value.numerator}/{value.denominator}"


def encode_timeline(timeline: list[dict]) -> list[dict]:
    return [{key: fraction(value) if isinstance(value, F) else value
             for key, value in point.items()} for point in timeline]


def crossing_step(timeline: list[dict]) -> int | None:
    return next((point["step"] for point in timeline if point["propagation_enabled"]), None)


def run() -> dict:
    initial = load_initials()
    by_rule = {}
    for rule in RULES:
        timelines = {name: run_trajectory(rule, start) for name, start in initial.items()}
        equalized = {name: run_trajectory(rule, start, equalize_at_start=True)
                     for name, start in initial.items()}
        sham = {name: run_trajectory(rule, start, paired=False) for name, start in initial.items()}
        by_rule[rule] = {
            "paired_reactivation": {name: encode_timeline(timeline)
                                    for name, timeline in timelines.items()},
            "first_propagation_step": {name: crossing_step(timeline)
                                        for name, timeline in timelines.items()},
            "recovery_lead_steps": (
                crossing_step(timelines["post_bfs"]) - crossing_step(timelines["during_bfs"])
                if all(crossing_step(timelines[name]) is not None for name in INITIALS)
                else None
            ),
            "equalized_history_control": {
                name: encode_timeline(timeline) for name, timeline in equalized.items()
            },
            "sham_no_coactivation": {name: encode_timeline(timeline)
                                     for name, timeline in sham.items()},
        }

    return seal({
        "status": "EXECUTED_SYNTHETIC_UPDATE_RULE_FALSIFIER",
        "epistemic_labels": {
            "OBSERVED": "The deterministic threshold crossings and association trajectories emitted by this harness.",
            "PROPOSED": "The four update rules are alternative synthetic learning hypotheses; none is asserted to model a real agent or biology.",
            "INFERRED": "If a recovery lead appears only under rules that preserve initial association, Exp43's result is explained by scalar distance to threshold within those rules; equalized-history controls test for any separate history signal.",
            "UNKNOWN": "Which, if any, update rule resembles Raven, MNEME, or deployed agent memory dynamics.",
        },
        "exp43_input": {
            "artifact": "experiments/exp43_h14_latent_trace/h14_exp43_run.json",
            "sha256": EXP43_SHA256,
            "initial_association": {name: fraction(value) for name, value in initial.items()},
        },
        "design": {
            "threshold": fraction(THRESHOLD),
            "common_paired_experience_evidence": fraction(EVIDENCE),
            "proportional_learning_rate": fraction(ALPHA),
            "max_reactivation_steps": MAX_STEPS,
            "rules": {
                "additive_fixed": "w' = min(1, w + 1/8)",
                "proportional_saturating": "w' = w + (1 - w) * 1/4",
                "history_reset_additive": "Discard incoming w, then set w' = min(1, exposure_count * 1/8)",
                "evidence_average": "w' = (w + 1/8) / 2",
            },
            "primary_falsifier": "The claimed robustness is falsified if the high-residual branch does not cross before the zero-residual branch under update rules that use the starting association. The independent-history interpretation is unsupported if equalized starts produce equal trajectories, as predicted by all state-only rules.",
            "sham": "Without paired C/D coactivation, no rule receives an update; this checks that exposure alone does not trigger recovery.",
        },
        "results_by_rule": by_rule,
        "interpretation_limit": "All differences are produced by declared scalar update equations and one threshold. These results can distinguish rule sensitivity inside the toy model, but cannot establish an additional biological or deployed-agent mechanism.",
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
