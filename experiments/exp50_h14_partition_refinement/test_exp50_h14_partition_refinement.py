from __future__ import annotations

import itertools
import unittest
from fractions import Fraction as F
from unittest.mock import patch

import exp50_h14_partition_refinement as exp50
from exp50_h14_partition_refinement import (
    QUERY_SCORES,
    _decode_state,
    apply_query,
    refine_partition,
    run,
    shortest_distinguishing_sequence,
    verify_exp49,
)
import exp48_h14_observational_quotient as exp48


class Exp50PartitionRefinementTests(unittest.TestCase):
    def test_pinned_exp49_artifact_verifies(self):
        self.assertEqual(verify_exp49(), "bc321768caab06edaf09eefbc8a02e61c141cb4a6fc6a550ad2b65c1dbbda4ed")

    def test_shared_query_scores_preserve_state_dependent_choice(self):
        state_c, _ = exp48.exp47.construct_history(F(0), 3)
        state_k = exp48.exp47.State(20, state_c.association, True, state_c.recency_age)
        # The same raw query score is interpreted through each state's own scalar score.
        query = F(1)
        _, output_c = apply_query(state_c, query)
        _, output_k = apply_query(state_k, query)
        self.assertNotEqual(dict(output_c)["choice"], dict(output_k)["choice"])

    def test_documented_seed_history_is_exact(self):
        seed, history = exp48.exp47.construct_history(F(0), 3)
        self.assertEqual(history["paired_updates"], 3)
        self.assertEqual(history["reinforcement_only_events"], 0)
        self.assertEqual(seed.reinforcement_count, 3)
        self.assertEqual(seed.association, F(3, 8))

    def test_refinement_matches_exp48_partition_on_seed_closure(self):
        result = run()
        self.assertEqual(result["model"]["reachable_state_count"], 172)
        self.assertEqual(result["model"]["input_alphabet_size"], len(QUERY_SCORES))
        self.assertEqual(result["refinement"]["fixed_point_class_count"], 118)
        self.assertEqual(result["refinement"]["exp48_restricted_class_count"], 118)
        self.assertTrue(result["refinement"]["partitions_match_exactly"])
        self.assertEqual(result["refinement"]["class_count_by_round"], [68, 93, 118, 118])

    def test_exp48_partition_is_congruent_under_shared_query_alphabet(self):
        result = run()["exp48_congruence_audit"]
        self.assertEqual(result["equivalent_state_pair_query_checks"], 2376)
        self.assertEqual(result["immediate_output_mismatches"], 0)
        self.assertEqual(result["successor_exp48_class_mismatches"], 0)
        self.assertIsNone(result["first_counterexample"])

    def test_every_distinct_class_pair_has_a_query_sequence_certificate(self):
        certificate = run()["minimality_certificate"]
        self.assertEqual(certificate["distinct_class_pairs"], 6903)
        self.assertEqual(certificate["certificates_generated"], 6903)
        self.assertTrue(certificate["all_distinct_class_pairs_have_distinguishing_sequence"])

    def test_certificate_replays_and_diverges_at_its_last_query(self):
        result = run()["minimality_certificate"]
        classes = {
            block["class_id"]: [_decode_state(state) for state in block["members"]]
            for block in result["refined_classes"]
        }
        certificate = next(item for item in result["certificates"] if item["length"] > 0)
        left = classes[certificate["class_a"]][0]
        right = classes[certificate["class_b"]][0]
        outputs_left, outputs_right = [], []
        for encoded_score in certificate["query_scores"]:
            score = F(encoded_score)
            left, output_left = apply_query(left, score)
            right, output_right = apply_query(right, score)
            outputs_left.append(output_left)
            outputs_right.append(output_right)
        self.assertEqual(outputs_left[:-1], outputs_right[:-1])
        self.assertNotEqual(outputs_left[-1], outputs_right[-1])
        self.assertEqual(outputs_left[-1], tuple(certificate["output_a"]))
        self.assertEqual(outputs_right[-1], tuple(certificate["output_b"]))

    def test_all_pair_certificates_replay(self):
        certificate = run()["minimality_certificate"]
        classes = {
            block["class_id"]: [_decode_state(state) for state in block["members"]]
            for block in certificate["refined_classes"]
        }
        for item in certificate["certificates"]:
            left = classes[item["class_a"]][0]
            right = classes[item["class_b"]][0]
            if not item["query_scores"]:
                self.assertNotEqual(exp50.initial_output(left), exp50.initial_output(right))
                self.assertEqual(exp50.initial_output(left), tuple(item["output_a"]))
                self.assertEqual(exp50.initial_output(right), tuple(item["output_b"]))
                continue
            left_outputs, right_outputs = [], []
            for score in item["query_scores"]:
                left, out_left = apply_query(left, F(score))
                right, out_right = apply_query(right, F(score))
                left_outputs.append(tuple(out_left))
                right_outputs.append(tuple(out_right))
            self.assertEqual(left_outputs[:-1], right_outputs[:-1])
            self.assertNotEqual(left_outputs[-1], right_outputs[-1])
            self.assertEqual(left_outputs[-1], tuple(item["output_a"]))
            self.assertEqual(right_outputs[-1], tuple(item["output_b"]))

    def test_all_nonempty_certificates_are_shortest(self):
        certificate = run()["minimality_certificate"]
        classes = {
            block["class_id"]: [_decode_state(state) for state in block["members"]]
            for block in certificate["refined_classes"]
        }
        checked = 0
        for item in certificate["certificates"]:
            length = item["length"]
            if length == 0:
                continue
            left0 = classes[item["class_a"]][0]
            right0 = classes[item["class_b"]][0]
            self.assertEqual(exp50.initial_output(left0), exp50.initial_output(right0))
            for shorter_length in range(1, length):
                for sequence in itertools.product(QUERY_SCORES, repeat=shorter_length):
                    left, right = left0, right0
                    traces_equal = True
                    for score in sequence:
                        left, out_left = apply_query(left, score)
                        right, out_right = apply_query(right, score)
                        if out_left != out_right:
                            traces_equal = False
                            break
                    self.assertTrue(traces_equal)
            checked += 1
        self.assertEqual(checked, 734)

    def test_shortest_witness_for_sampled_pair(self):
        states = exp48.reachable_closure(exp48.exp47.construct_history(F(0), 3)[0])
        colors, _, _ = refine_partition(states)
        blocks = {}
        for state, color in colors.items():
            blocks.setdefault(color, []).append(state)
        left, right = next(iter(itertools.combinations(blocks.values(), 2)))
        witness = shortest_distinguishing_sequence(left[0], right[0])
        self.assertEqual(witness["length"], len(witness["query_scores"]))
        self.assertLessEqual(witness["length"], len(states) ** 2)

    def test_verdict_is_scoped_to_closed_seeded_machine(self):
        result = run()
        self.assertTrue(result["model"]["reachable_set_closed_under_input_alphabet"])
        self.assertTrue(result["verdict"]["exp48_partition_is_dynamically_sufficient_for_query_inputs"])
        self.assertEqual(result["verdict"]["minimal_behavioral_class_count_for_this_seeded_machine"], 118)
        self.assertTrue(result["verdict"]["minimality_supported_by_pair_certificates"])

    def test_deliberate_observation_mutation_changes_the_partition(self):
        states = exp48.reachable_closure(exp48.exp47.construct_history(F(0), 3)[0])
        real_colors, _, _ = refine_partition(states)

        def constant_transition(state, challenger_score):
            return state, (("choice", "C"), ("propagation", False), ("causal_C_to_D", "0/1"))

        with patch.object(exp50, "initial_output", return_value=(False, "0/1")), \
             patch.object(exp50, "apply_query", side_effect=constant_transition):
            mutated_colors, _, _ = refine_partition(states)
        self.assertEqual(len(set(real_colors.values())), 118)
        self.assertEqual(len(set(mutated_colors.values())), 1)


if __name__ == "__main__":
    unittest.main()
