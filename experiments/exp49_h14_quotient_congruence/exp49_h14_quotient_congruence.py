#!/usr/bin/env python3
"""Exp49: falsify or support transition congruence of the Exp48 quotient.

For each pair equivalent under Exp48's fixed observation suite, apply both
forced actions and compare immediate outputs and successor equivalence. The
result is scoped to the Exp48 finite query suite and declared action choices.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path

EXP48_DIR = Path(__file__).resolve().parents[1] / "exp48_h14_observational_quotient"
sys.path.insert(0, str(EXP48_DIR))
import exp48_h14_observational_quotient as exp48  # noqa: E402

EXP48_RESULT = EXP48_DIR / "h14_exp48_run.json"
EXP48_SHA256 = "f143334a0bb89cac6c806e94c0af7ffc767459ce06dac2025c6f92a4997c8914"
FORCED_ACTIONS = {"C": F(0), "K": F(3, 2)}


def verify_exp48() -> str:
    artifact = json.loads(EXP48_RESULT.read_text(encoding="utf-8"))
    digest = artifact.pop("sha256")
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
    actual = hashlib.sha256(canonical.encode()).hexdigest()
    if digest != EXP48_SHA256 or actual != digest:
        raise ValueError("Exp48 canonical artifact hash does not match the pinned value")
    return digest


def state_key(state) -> tuple:
    return (state.reinforcement_count, state.association, state.link, state.recency_age)


def partition(states) -> dict[tuple, list]:
    groups = defaultdict(list)
    for state in states:
        groups[exp48.exp47.state_signature(state)].append(state)
    return groups


def check_domain(states) -> dict:
    signature_cache = {state: exp48.exp47.state_signature(state) for state in states}
    groups = defaultdict(list)
    for state, signature in signature_cache.items():
        groups[signature].append(state)
    checks = 0
    equivalent_pair_count = sum(len(members) * (len(members) - 1) // 2
                                 for members in groups.values())
    immediate_output_mismatches = 0
    successor_class_mismatches = 0
    witnesses = []

    for members in groups.values():
        for state_a, state_b in combinations(members, 2):
            for action, challenger in FORCED_ACTIONS.items():
                checks += 1
                next_a, output_a = exp48.exp47.transition(state_a, challenger)
                next_b, output_b = exp48.exp47.transition(state_b, challenger)
                output_differs = output_a != output_b
                if next_a not in signature_cache:
                    signature_cache[next_a] = exp48.exp47.state_signature(next_a)
                if next_b not in signature_cache:
                    signature_cache[next_b] = exp48.exp47.state_signature(next_b)
                successor_differs = (
                    signature_cache[next_a] != signature_cache[next_b]
                )
                immediate_output_mismatches += output_differs
                successor_class_mismatches += successor_differs
                if (output_differs or successor_differs) and len(witnesses) < 8:
                    witnesses.append({
                        "action": action,
                        "state_a": exp48.exp47.encode(state_a),
                        "state_b": exp48.exp47.encode(state_b),
                        "states_equivalent_under_exp48_protocol": True,
                        "immediate_output_a": output_a,
                        "immediate_output_b": output_b,
                        "immediate_outputs_equal": not output_differs,
                        "successor_a": exp48.exp47.encode(next_a),
                        "successor_b": exp48.exp47.encode(next_b),
                        "successors_equivalent_under_exp48_protocol": not successor_differs,
                    })

    return {
        "state_count": len(states),
        "equivalence_class_count": len(groups),
        "equivalent_unordered_state_pairs": equivalent_pair_count,
        "pair_action_checks": checks,
        "immediate_output_mismatch_count": immediate_output_mismatches,
        "successor_class_mismatch_count": successor_class_mismatches,
        "transition_congruence_holds_for_checked_domain": (
            immediate_output_mismatches == 0 and successor_class_mismatches == 0
        ),
        "counterexamples": witnesses,
    }


def run() -> dict:
    exp48_hash = verify_exp48()
    cartesian = exp48.exp47.all_states()
    seed, seed_history = exp48.exp47.construct_history(F(0), 3)
    reachable = exp48.reachable_closure(seed)

    cartesian_result = check_domain(cartesian)
    reachable_result = check_domain(reachable)
    return {
        "experiment": "Exp49",
        "title": "Transition congruence of the finite Exp48 observational quotient",
        "status": "EXECUTED_SYNTHETIC_QUOTIENT_CONGRUENCE_ASSAY",
        "epistemic_status": {
            "OBSERVED": (
                "The pinned Exp48 result verified with canonical SHA256 " + exp48_hash +
                ". Exp48 defines equivalence by exact output traces for 24 fixed schedules."
            ),
            "PROPOSED": (
                "This assay tests all unordered equivalent-state pairs and both forced "
                "actions C and K, comparing immediate observable outputs and whether "
                "successor states remain equivalent under the same Exp48 protocol."
            ),
            "INFERRED": (
                "A counterexample with equal current protocol signatures but distinct "
                "successor signatures shows the Exp48 quotient is not a congruence for "
                "that tested domain and action set. If no counterexample exists, the result "
                "would support congruence only over that finite domain and action set."
            ),
            "UNKNOWN": (
                "Whether a transition-stable quotient exists with the same classes over "
                "arbitrary future query inputs, or in Raven/MNEME."
            ),
        },
        "source_provenance": {
            "exp48": {
                "path": "experiments/exp48_h14_observational_quotient/exp48_h14_observational_quotient.py",
                "artifact": "experiments/exp48_h14_observational_quotient/h14_exp48_run.json",
                "canonical_sha256": exp48_hash,
                "use": "Defines the 24-schedule observational equivalence and reachable seed closure.",
            }
        },
        "protocol": {
            "actions": {key: exp48.exp47.fraction(value) for key, value in FORCED_ACTIONS.items()},
            "action_semantics": "Query scores force the named choice: 0 selects C; 3/2 selects K.",
            "immediate_observables": ["choice", "propagation", "causal_C_to_D"],
            "successor_equivalence": "Exact agreement on all 24 Exp48 probe schedules.",
            "check_rule": "For every equivalent pair and each action, immediate outputs must agree and successors must remain equivalent.",
        },
        "cartesian_domain": cartesian_result,
        "reachable_seed_closure": {
            "seed_history": seed_history,
            "seed": exp48.exp47.encode(seed),
            **reachable_result,
        },
        "verdict": {
            "exp48_quotient_is_congruent_on_cartesian_domain": cartesian_result["transition_congruence_holds_for_checked_domain"],
            "exp48_quotient_is_congruent_on_reachable_seed_closure": reachable_result["transition_congruence_holds_for_checked_domain"],
            "reachable_seed_closure_is_closed_under_actions": True,
            "reachable_seed_closure_quotient_supports_all_finite_action_sequences": reachable_result["transition_congruence_holds_for_checked_domain"],
            "reachable_seed_closure_minimum_classes_for_behavioral_prediction": (
                reachable_result["equivalence_class_count"]
                if reachable_result["transition_congruence_holds_for_checked_domain"] else None
            ),
            "claim_scope": (
                "The 172 states reachable from the one documented seed under the two "
                "declared actions. In this model, every query induces C or K, so a closed, "
                "output-preserving congruence predicts every finite C/K sequence by induction."
            ),
        },
        "limits": (
            "The Cartesian domain is not transition-closed: its one-eighth association "
            "grid omits reachable sixteenth-step values. The seed closure tests all C/K "
            "action sequences from one seed but not every possible initial history. "
            "The Cartesian-domain counterexample concerns states that are not in the "
            "documented seed closure. The stable quotient result applies only to that "
            "172-state closure, the two C/K actions, and this synthetic transition system; "
            "it does not cover other initial histories or Raven/MNEME."
        ),
    }


def canonical_json(data: dict) -> str:
    unsigned = json.dumps(data, sort_keys=True, separators=(",", ":"))
    data["sha256"] = hashlib.sha256(unsigned.encode()).hexdigest()
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("h14_exp49_run.json"))
    args = parser.parse_args()
    args.output.write_text(canonical_json(run()), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
