from __future__ import annotations

import unittest

from exp49_h14_quotient_congruence import check_domain, run, verify_exp48
import exp48_h14_observational_quotient as exp48


class Exp49QuotientCongruenceTests(unittest.TestCase):
    def test_pinned_exp48_artifact_verifies(self):
        self.assertEqual(verify_exp48(), "f143334a0bb89cac6c806e94c0af7ffc767459ce06dac2025c6f92a4997c8914")

    def test_cartesian_quotient_has_a_transition_counterexample(self):
        result = check_domain(exp48.exp47.all_states())
        self.assertEqual(result["equivalence_class_count"], 441)
        self.assertEqual(result["equivalent_unordered_state_pairs"], 24822)
        self.assertEqual(result["pair_action_checks"], 49644)
        self.assertEqual(result["immediate_output_mismatch_count"], 0)
        self.assertEqual(result["successor_class_mismatch_count"], 3843)
        self.assertTrue(result["counterexamples"])

    def test_counterexample_starts_from_observationally_equivalent_states(self):
        result = check_domain(exp48.exp47.all_states())
        witness = result["counterexamples"][0]
        state_a = _decode_state(witness["state_a"])
        state_b = _decode_state(witness["state_b"])
        self.assertEqual(exp48.exp47.state_signature(state_a),
                         exp48.exp47.state_signature(state_b))
        self.assertTrue(witness["immediate_outputs_equal"])
        self.assertFalse(witness["successors_equivalent_under_exp48_protocol"])

    def test_reachable_seed_closure_is_checked_separately(self):
        result = run()["reachable_seed_closure"]
        self.assertEqual(result["state_count"], 172)
        self.assertEqual(result["equivalence_class_count"], 118)
        self.assertEqual(result["pair_action_checks"],
                         result["equivalent_unordered_state_pairs"] * 2)
        self.assertEqual(result["immediate_output_mismatch_count"], 0)
        self.assertEqual(result["successor_class_mismatch_count"], 0)

    def test_verdict_matches_pair_action_audit(self):
        result = run()
        self.assertEqual(result["verdict"]["exp48_quotient_is_congruent_on_cartesian_domain"],
                         result["cartesian_domain"]["transition_congruence_holds_for_checked_domain"])
        self.assertEqual(result["verdict"]["exp48_quotient_is_congruent_on_reachable_seed_closure"],
                         result["reachable_seed_closure"]["transition_congruence_holds_for_checked_domain"])
        self.assertTrue(result["verdict"]["reachable_seed_closure_is_closed_under_actions"])
        self.assertTrue(result["verdict"]["reachable_seed_closure_quotient_supports_all_finite_action_sequences"])
        self.assertEqual(result["verdict"]["reachable_seed_closure_minimum_classes_for_behavioral_prediction"], 118)


def _decode_state(value):
    from fractions import Fraction
    return exp48.exp47.State(value["reinforcement_count"], Fraction(value["association"]),
                             value["link"], value["recency_age"])


if __name__ == "__main__":
    unittest.main()
