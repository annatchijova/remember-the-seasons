#!/usr/bin/env python3
"""Exp50: minimize the reachable synthetic query-score machine.

Inputs are shared challenger scores. The state-dependent Exp47 transition
chooses C or K; treating the choice itself as an exogenous input changes the
machine semantics and is not used here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, deque
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path

EXP49_DIR = Path(__file__).resolve().parents[1] / "exp49_h14_quotient_congruence"
EXP48_DIR = Path(__file__).resolve().parents[1] / "exp48_h14_observational_quotient"
sys.path.insert(0, str(EXP49_DIR))
sys.path.insert(0, str(EXP48_DIR))
import exp49_h14_quotient_congruence as exp49  # noqa: E402
import exp48_h14_observational_quotient as exp48  # noqa: E402

EXP49_RESULT = EXP49_DIR / "h14_exp49_run.json"
EXP49_SHA256 = "bc321768caab06edaf09eefbc8a02e61c141cb4a6fc6a550ad2b65c1dbbda4ed"
QUERY_SCORES = tuple(sorted({score for schedule in exp48.exp47.probe_schedules()
                             for score in schedule}))


def verify_exp49() -> str:
    artifact = json.loads(EXP49_RESULT.read_text(encoding="utf-8"))
    digest = artifact.pop("sha256")
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
    actual = hashlib.sha256(canonical.encode()).hexdigest()
    if digest != EXP49_SHA256 or actual != digest:
        raise ValueError("Exp49 canonical artifact hash does not match the pinned value")
    return digest


def initial_output(state) -> tuple:
    propagation = state.link and state.association >= exp48.exp47.THRESHOLD
    causal = state.association if propagation else F(0)
    return (propagation, exp48.exp47.fraction(causal))


def apply_query(state, challenger_score: F):
    successor, output = exp48.exp47.transition(state, challenger_score)
    return successor, tuple(sorted(output.items()))


def encoded_key(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def assign_colors(keys: dict) -> dict:
    serialized = {state: encoded_key(key) for state, key in keys.items()}
    unique = {value: index for index, value in enumerate(sorted(set(serialized.values())))}
    return {state: unique[value] for state, value in serialized.items()}


def blocks_from_colors(colors: dict) -> list[list]:
    blocks = {}
    for state, color in colors.items():
        blocks.setdefault(color, []).append(state)
    return [sorted(members, key=exp49.state_key) for _, members in
            sorted(blocks.items(), key=lambda item: item[0])]


def same_partition(colors_a: dict, colors_b: dict) -> bool:
    return all((colors_a[left] == colors_a[right]) ==
               (colors_b[left] == colors_b[right])
               for left in colors_a for right in colors_a)


def refine_partition(states: set) -> tuple[dict, int, list[int]]:
    colors = assign_colors({
        state: (initial_output(state), tuple(
            (exp48.exp47.fraction(score), apply_query(state, score)[1])
            for score in QUERY_SCORES))
        for state in states
    })
    class_counts = [len(set(colors.values()))]
    for _ in range(len(states) + 1):
        keys = {}
        for state in states:
            transitions = []
            for score in QUERY_SCORES:
                successor, output = apply_query(state, score)
                if successor not in states:
                    raise ValueError("query-score transition escaped the reachable closure")
                transitions.append((exp48.exp47.fraction(score), output, colors[successor]))
            keys[state] = (colors[state], initial_output(state), tuple(transitions))
        refined = assign_colors(keys)
        class_counts.append(len(set(refined.values())))
        if same_partition(colors, refined):
            return refined, len(class_counts) - 1, class_counts
        colors = refined
    raise RuntimeError("partition refinement did not reach a fixed point")


def canonical_blocks(blocks: list[list]) -> list[dict]:
    result = []
    for members in blocks:
        encoded_members = [exp48.exp47.encode(state) for state in members]
        key = json.dumps(encoded_members, sort_keys=True, separators=(",", ":"))
        result.append({
            "class_id": hashlib.sha256(key.encode()).hexdigest(),
            "member_count": len(members),
            "members": encoded_members,
        })
    return sorted(result, key=lambda item: item["class_id"])


def exp48_blocks(states: set) -> list[list]:
    grouped = {}
    for state in states:
        grouped.setdefault(exp48.exp47.state_signature(state), []).append(state)
    return [sorted(members, key=exp49.state_key) for members in grouped.values()]


def partition_as_sets(blocks: list[list]) -> set[frozenset]:
    return {frozenset(exp49.state_key(state) for state in members) for members in blocks}


def check_q_congruence(states: set) -> dict:
    groups = {}
    for state in states:
        groups.setdefault(exp48.exp47.state_signature(state), []).append(state)
    output_mismatches = successor_mismatches = checks = 0
    witness = None
    signatures = {state: exp48.exp47.state_signature(state) for state in states}
    for members in groups.values():
        for left, right in combinations(members, 2):
            for score in QUERY_SCORES:
                checks += 1
                next_left, out_left = apply_query(left, score)
                next_right, out_right = apply_query(right, score)
                out_diff = out_left != out_right
                successor_diff = signatures[next_left] != signatures[next_right]
                output_mismatches += out_diff
                successor_mismatches += successor_diff
                if witness is None and (out_diff or successor_diff):
                    witness = {
                        "state_a": exp48.exp47.encode(left),
                        "state_b": exp48.exp47.encode(right),
                        "challenger_score": exp48.exp47.fraction(score),
                        "immediate_outputs_equal": not out_diff,
                        "successors_exp48_equivalent": not successor_diff,
                        "successor_a": exp48.exp47.encode(next_left),
                        "successor_b": exp48.exp47.encode(next_right),
                    }
    return {
        "equivalent_state_pair_query_checks": checks,
        "immediate_output_mismatches": output_mismatches,
        "successor_exp48_class_mismatches": successor_mismatches,
        "exp48_partition_is_congruent_for_query_alphabet": (
            output_mismatches == 0 and successor_mismatches == 0),
        "first_counterexample": witness,
    }


def shortest_distinguishing_sequence(state_a, state_b) -> dict:
    if initial_output(state_a) != initial_output(state_b):
        return {
            "query_scores": [], "length": 0, "divergence_index": 0,
            "output_a": initial_output(state_a), "output_b": initial_output(state_b),
        }
    queue = deque([(state_a, state_b, ())])
    visited = {(state_a, state_b)}
    while queue:
        left, right, prefix = queue.popleft()
        for score in QUERY_SCORES:
            next_left, output_left = apply_query(left, score)
            next_right, output_right = apply_query(right, score)
            sequence = prefix + (score,)
            if output_left != output_right:
                return {
                    "query_scores": [exp48.exp47.fraction(value) for value in sequence],
                    "length": len(sequence), "divergence_index": len(sequence),
                    "output_a": output_left, "output_b": output_right,
                }
            pair = (next_left, next_right)
            if pair not in visited:
                visited.add(pair)
                queue.append((next_left, next_right, sequence))
    raise RuntimeError("distinct refined classes had no distinguishing query sequence")


def minimality_certificates(blocks: list[list]) -> tuple[list[dict], dict]:
    ordered = canonical_blocks(blocks)
    member_by_id = {
        block["class_id"]: [_decode_state(value) for value in block["members"]]
        for block in ordered
    }
    certificates = []
    lengths = Counter()
    for class_a, class_b in combinations(sorted(member_by_id), 2):
        witness = shortest_distinguishing_sequence(
            member_by_id[class_a][0], member_by_id[class_b][0])
        lengths[witness["length"]] += 1
        certificates.append({"class_a": class_a, "class_b": class_b, **witness})
    return certificates, {str(length): lengths[length] for length in sorted(lengths)}


def _decode_state(value):
    return exp48.exp47.State(
        value["reinforcement_count"], F(value["association"]),
        value["link"], value["recency_age"])


def run() -> dict:
    exp49_hash = verify_exp49()
    seed, seed_history = exp48.exp47.construct_history(F(0), 3)
    states = exp48.reachable_closure(seed)
    refined_colors, refinement_rounds, class_counts = refine_partition(states)
    refined_blocks = blocks_from_colors(refined_colors)
    q_blocks = exp48_blocks(states)
    partitions_match = partition_as_sets(refined_blocks) == partition_as_sets(q_blocks)
    q_congruence = check_q_congruence(states)
    certificates, length_histogram = minimality_certificates(refined_blocks)
    pair_count = len(refined_blocks) * (len(refined_blocks) - 1) // 2
    closed = all(apply_query(state, score)[0] in states
                 for state in states for score in QUERY_SCORES)
    return {
        "experiment": "Exp50",
        "title": "Partition refinement and minimality certificate",
        "status": "EXECUTED_SYNTHETIC_REACHABLE_QUERY_MACHINE_MINIMIZATION",
        "epistemic_status": {
            "OBSERVED": (
                "The pinned Exp49 artifact verifies with canonical SHA256 " + exp49_hash +
                ". The shared Exp47 transition accepts a challenger score and selects C or K "
                "from the current state's scalar score. Exp48 signatures use that transition."
            ),
            "INFERRED": (
                "The unique challenger scores in Exp48's schedules induce all choice "
                "threshold regions on the enumerated count levels: score 0 and 3/2 cover "
                "the extremes, and adjacent-level midpoints cover each intermediate split. "
                "Thus this finite input alphabet spans the C/K transition patterns of this model."
            ),
            "PROPOSED": (
                "Refine by baseline observations, immediate outputs, and successor blocks "
                "for every shared challenger-score input; compare the fixed point with Exp48."
            ),
            "UNKNOWN": (
                "Whether this synthetic machine's state space or quotient describes any "
                "other seed, Raven, MNEME, or deployed agent memory."
            ),
        },
        "source_provenance": {
            "exp49": {"path": "experiments/exp49_h14_quotient_congruence/exp49_h14_quotient_congruence.py",
                      "artifact": "experiments/exp49_h14_quotient_congruence/h14_exp49_run.json",
                      "canonical_sha256": exp49_hash},
            "shared_transition_source": "experiments/exp47_h14_state_characterization/exp47_h14_state_characterization.py",
            "equivalence_source": "experiments/exp48_h14_observational_quotient/exp48_h14_observational_quotient.py",
        },
        "model": {
            "seed_history": seed_history, "seed": exp48.exp47.encode(seed),
            "reachable_state_count": len(states),
            "input_alphabet": [exp48.exp47.fraction(score) for score in QUERY_SCORES],
            "input_alphabet_size": len(QUERY_SCORES),
            "input_semantics": "Shared challenger score; Exp47 state-dependent transition chooses C or K.",
            "exp48_query_schedule_count": len(exp48.exp47.probe_schedules()),
            "observables": ["choice", "propagation", "causal_C_to_D"],
            "reachable_set_closed_under_input_alphabet": closed,
        },
        "exp48_congruence_audit": q_congruence,
        "refinement": {
            "algorithm": "Deterministic Mealy partition refinement under shared challenger-score inputs.",
            "round_count_including_initial_partition": len(class_counts),
            "class_count_by_round": class_counts,
            "fixed_point_class_count": len(refined_blocks),
            "exp48_restricted_class_count": len(q_blocks),
            "partitions_match_exactly": partitions_match,
        },
        "minimality_certificate": {
            "distinct_class_pairs": pair_count,
            "certificates_generated": len(certificates),
            "all_distinct_class_pairs_have_distinguishing_sequence": len(certificates) == pair_count,
            "shortest_sequence_length_histogram": length_histogram,
            "certificates": certificates,
            "refined_classes": canonical_blocks(refined_blocks),
        },
        "verdict": {
            "exp48_classes_equal_query_machine_fixed_point": partitions_match,
            "minimal_behavioral_class_count_for_this_seeded_machine": len(refined_blocks),
            "minimality_supported_by_pair_certificates": len(certificates) == pair_count,
            "exp48_partition_is_dynamically_sufficient_for_query_inputs": q_congruence["exp48_partition_is_congruent_for_query_alphabet"],
        },
        "limits": (
            "The result covers one documented seed and its reachable closure under the "
            "finite challenger-score alphabet. The alphabet spans the choice regions of "
            "the declared count levels in this synthetic scorer; the result does not cover "
            "other initial histories, alternative transition semantics, Raven, or MNEME."
        ),
    }


def canonical_json(data: dict) -> str:
    unsigned = json.dumps(data, sort_keys=True, separators=(",", ":"))
    data["sha256"] = hashlib.sha256(unsigned.encode()).hexdigest()
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("h14_exp50_run.json"))
    args = parser.parse_args()
    args.output.write_text(canonical_json(run()), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
