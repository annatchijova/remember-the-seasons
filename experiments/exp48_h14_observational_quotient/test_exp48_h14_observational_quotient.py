from __future__ import annotations

import unittest
from fractions import Fraction

from exp48_h14_observational_quotient import (
    quotient,
    reachable_closure,
    run,
    verify_exp47,
)
import exp47_h14_state_characterization as exp47


class Exp48ObservationalQuotientTests(unittest.TestCase):
    def test_pinned_exp47_artifact_verifies(self):
        self.assertEqual(verify_exp47(), "a340d939e0ef41ab2090d5efb94492161108894c2275118168720d187b17dfd7")

    def test_exp47_domain_is_cartesian_and_differs_from_seed_reachability(self):
        result = run()
        reach = result["reachability_audit"]
        self.assertEqual(reach["exp47_cartesian_state_count"], 1512)
        self.assertLess(reach["states_reachable_from_exp47_documented_seed"], 1512)
        self.assertFalse(reach["cartesian_product_equals_reachable_set"])
        self.assertFalse(reach["reachable_states_are_subset_of_cartesian_product"])
        self.assertEqual(reach["cartesian_states_not_reachable_from_seed_count"],
                         1512 - (reach["states_reachable_from_exp47_documented_seed"]
                                 - reach["reachable_states_not_in_cartesian_product_count"]))
        self.assertEqual(reach["reachable_states_not_in_cartesian_product_count"], 60)
        self.assertEqual(reach["states_reachable_from_exp47_documented_seed"], 172)

    def test_quotient_has_distinct_state_witnesses_with_equal_observations(self):
        result = run()
        self.assertEqual(result["cartesian_product_quotient"]["observational_class_count"], 441)
        self.assertEqual(result["reachable_seed_closure_quotient"]["observational_class_count"], 118)
        witnesses = result["cartesian_product_quotient"]["equivalent_distinct_state_witnesses"]
        self.assertGreater(len(witnesses), 0)
        for witness in witnesses:
            self.assertTrue(witness["representation_distinguishes_pair"])
            self.assertTrue(witness["observations_equivalent_for_all_probe_schedules"])

    def test_every_quotient_class_has_one_signature_and_witnesses_are_exact(self):
        states = exp47.all_states()
        result = quotient(states)
        self.assertEqual(result["observational_class_count"],
                         len({exp47.state_signature(state) for state in states}))
        for witness in result["equivalent_distinct_state_witnesses"]:
            state_a = _decode_state(witness["state_a"])
            state_b = _decode_state(witness["state_b"])
            self.assertNotEqual(state_a, state_b)
            self.assertEqual(exp47.state_signature(state_a), exp47.state_signature(state_b))

    def test_reachable_closure_is_closed_under_both_actions(self):
        seed, _ = exp47.construct_history(Fraction(0), 3)
        reachable = reachable_closure(seed)
        for state in reachable:
            for challenger in (0, Fraction(3, 2)):
                successor, _ = exp47.transition(state, challenger)
                self.assertIn(successor, reachable)

    def test_report_limits_minimality_to_finite_protocol(self):
        result = run()
        self.assertEqual(result["minimality_statement"]["cartesian_product_minimum_classes_for_exact_prediction"], 441)
        self.assertEqual(result["minimality_statement"]["reachable_seed_closure_minimum_classes_for_exact_prediction"], 118)
        self.assertTrue(result["minimality_statement"]["quotient_achieves_finite_protocol_lower_bound"])
        self.assertFalse(result["minimality_statement"]["universal_or_arbitrary_horizon_minimality_established"])
        self.assertTrue(result["cartesian_product_quotient"]["compression_possible_for_this_protocol"])


def _decode_state(value):
    from fractions import Fraction
    return exp47.State(value["reinforcement_count"], Fraction(value["association"]),
                       value["link"], value["recency_age"])


if __name__ == "__main__":
    unittest.main()
