from __future__ import annotations

import unittest
from fractions import Fraction as F

from exp46_h14_history_collisions import (
    make_history,
    run,
    simulate,
    trajectory_signature,
    verify_exp45,
)


class Exp46HistoryCollisionTests(unittest.TestCase):
    def test_pinned_exp45_artifact_verifies(self):
        self.assertEqual(verify_exp45(), "427e502fbb0ec443685302cd161691bd3c9dc70b861cd5badf1fd03d6e5a1acd")

    def test_distinct_histories_collide_on_all_four_projected_fields(self):
        short, _ = make_history(F(1, 4), 1)
        long, _ = make_history(F(0), 3)
        self.assertEqual(short.projected, long.projected)
        self.assertEqual(short.projected.association, F(3, 8))
        self.assertNotEqual(short.reinforcement_count, long.reinforcement_count)

    def test_binary_ranking_predicts_identical_trajectories(self):
        short, _ = make_history(F(1, 4), 1)
        long, _ = make_history(F(0), 3)
        self.assertEqual(trajectory_signature(simulate(short, "binary")),
                         trajectory_signature(simulate(long, "binary")))

    def test_scalar_count_splits_decision_and_function_at_first_step(self):
        short, _ = make_history(F(1, 4), 1)
        long, _ = make_history(F(0), 3)
        short_first = simulate(short, "scalar")["timeline"][0]
        long_first = simulate(long, "scalar")["timeline"][0]
        self.assertEqual(short_first["score_C"], "147/200")
        self.assertEqual(long_first["score_C"], "161/200")
        self.assertEqual((short_first["choice"], long_first["choice"]), ("K", "C"))
        self.assertEqual((short_first["association_C_to_D"], long_first["association_C_to_D"]),
                         ("3/8", "1/2"))
        self.assertEqual((short_first["propagation_C_to_D"], long_first["propagation_C_to_D"]),
                         (False, True))

    def test_equal_count_control_has_identical_trajectories(self):
        first, _ = make_history(F(1, 4), 1)
        second, _ = make_history(F(1, 4), 1)
        self.assertEqual(trajectory_signature(simulate(first, "scalar")),
                         trajectory_signature(simulate(second, "scalar")))

    def test_report_claims_are_supported_by_the_run(self):
        report = run()
        self.assertTrue(report["controls"]["same_projected_state"])
        self.assertTrue(report["controls"]["different_history_counts"])
        self.assertTrue(report["controls"]["binary_trajectories_equal"])
        self.assertTrue(report["controls"]["scalar_trajectories_diverge"])
        self.assertTrue(report["controls"]["equal_count_control_trajectories_equal"])
        self.assertTrue(report["controls"]["first_scalar_divergence_has_causal_propagation_split"])


if __name__ == "__main__":
    unittest.main()
