"""Exact predictions and ablation-collision oracles for Exp45."""
import unittest
from fractions import Fraction as F

from exp45_h14_sufficient_state import COMPONENTS, make_factorial, pinned_exp43_values, run


class TestExp45(unittest.TestCase):
    def test_anchor_values_are_loaded_from_hash_verified_exp43(self):
        self.assertEqual(pinned_exp43_values(), {
            "residual_association": F(3, 8),
            "no_residual_association": F(0),
        })

    def test_full_factorial_contains_all_sixteen_unique_states(self):
        states = make_factorial()
        self.assertEqual(len(states), 16)
        self.assertEqual(len(set(states)), 16)

    def test_expected_recovery_times_under_declared_rules(self):
        cases = {(
            case["initial_state"]["reinforcement"],
            case["initial_state"]["association"],
            case["initial_state"]["link_present"],
            case["initial_state"]["recency_age"],
        ): case["first_recovery_step"] for case in run()["factorial_cases"]}
        self.assertEqual(cases[(True, "3/8", True, 0)], 1)
        self.assertEqual(cases[(True, "3/8", True, 3)], 2)
        self.assertEqual(cases[(False, "3/8", True, 0)], 2)
        self.assertEqual(cases[(True, "0/1", True, 0)], 4)
        self.assertEqual(cases[(False, "0/1", True, 0)], 5)
        self.assertEqual(cases[(False, "0/1", True, 3)], 5)
        self.assertIsNone(cases[(True, "3/8", False, 0)])

    def test_each_ablated_component_merges_states_with_different_trajectories(self):
        audit = run()["leave_one_component_out"]
        self.assertEqual(set(audit), set(COMPONENTS))
        self.assertEqual({name: item["collision_groups_with_different_recovery_trajectories"]
                          for name, item in audit.items()}, {
            "reinforcement": 4,
            "association": 4,
            "link": 8,
            "recency": 4,
        })
        self.assertTrue(all(item["necessary_for_exact_prediction_in_sample"]
                            for item in audit.values()))

    def test_missing_link_blocks_causal_effect_even_when_association_crosses(self):
        case = next(case for case in run()["factorial_cases"]
                    if case["initial_state"] == {
                        "reinforcement": True,
                        "association": "3/8",
                        "link_present": False,
                        "recency_age": 0,
                    })
        self.assertEqual(case["timeline"][-1]["association"], "1/1")
        self.assertFalse(any(point["propagation"] for point in case["timeline"]))
        self.assertTrue(all(point["causal_C_to_D"] == "0/1" for point in case["timeline"]))

    def test_recency_changes_recovery_and_causal_trajectory(self):
        cases = run()["factorial_cases"]
        fresh = next(case for case in cases if case["initial_state"] == {
            "reinforcement": True, "association": "0/1", "link_present": True, "recency_age": 0})
        stale = next(case for case in cases if case["initial_state"] == {
            "reinforcement": True, "association": "0/1", "link_present": True, "recency_age": 3})
        self.assertEqual((fresh["first_recovery_step"], stale["first_recovery_step"]), (4, 5))
        self.assertNotEqual(fresh["timeline"][1]["association"],
                            stale["timeline"][1]["association"])

    def test_reinforcement_flag_changes_learning_speed(self):
        cases = run()["factorial_cases"]
        reinforced = next(case for case in cases if case["initial_state"] == {
            "reinforcement": True, "association": "0/1", "link_present": True, "recency_age": 0})
        neutral = next(case for case in cases if case["initial_state"] == {
            "reinforcement": False, "association": "0/1", "link_present": True, "recency_age": 0})
        self.assertEqual((reinforced["first_recovery_step"], neutral["first_recovery_step"]), (4, 5))

    def test_all_result_trajectories_are_deterministic(self):
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
