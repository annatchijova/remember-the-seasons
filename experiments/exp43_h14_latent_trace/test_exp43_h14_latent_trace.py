"""Exact falsifiers for the Exp43 latent-trace recovery assay."""
import unittest

from exp43_h14_latent_trace import load_exp42_worlds, run, trajectory


class TestExp43(unittest.TestCase):
    def test_input_is_the_hash_verified_exp42_post_washout_state(self):
        worlds = load_exp42_worlds()
        self.assertEqual(worlds["during_bfs"].association.numerator, 3)
        self.assertEqual(worlds["during_bfs"].association.denominator, 8)
        self.assertEqual(worlds["post_bfs"].association, 0)
        self.assertEqual(worlds["during_bfs"].state_c.value, "NEUTRAL")
        self.assertEqual(worlds["post_bfs"].state_d.value, "NEUTRAL")

    def test_both_histories_are_functionally_inactive_before_reactivation(self):
        data = run()["paired_reactivation"]
        for timeline in data.values():
            self.assertFalse(timeline[0]["propagation_probe"]["C_propagates_to_D"])
            self.assertFalse(timeline[0]["propagation_probe"]["D_candidate"])

    def test_residual_trace_recovers_propagation_before_zero_trace(self):
        timelines = run()["paired_reactivation"]
        high = timelines["during_bfs"]
        zero = timelines["post_bfs"]
        self.assertTrue(high[1]["propagation_probe"]["C_propagates_to_D"])
        self.assertEqual(high[1]["association_C_to_D"], "1/2")
        self.assertFalse(zero[1]["propagation_probe"]["C_propagates_to_D"])
        self.assertEqual(zero[1]["association_C_to_D"], "1/8")
        self.assertTrue(zero[4]["propagation_probe"]["C_propagates_to_D"])
        self.assertEqual(zero[4]["association_C_to_D"], "1/2")

    def test_causal_effect_tracks_the_recovered_indirect_contribution(self):
        timelines = run()["paired_reactivation"]
        high_step1 = timelines["during_bfs"][1]["causal_C_effect"]
        zero_step1 = timelines["post_bfs"][1]["causal_C_effect"]
        self.assertEqual(high_step1["delta_by_action"], {"X": "1/1", "Y": "1/2"})
        self.assertEqual(zero_step1["delta_by_action"], {"X": "1/1", "Y": "0/1"})

    def test_equalized_histories_recover_on_the_same_step(self):
        timelines = run()["equalized_history_control"]
        first = timelines["during_bfs"]
        second = timelines["post_bfs"]
        self.assertEqual([row["association_C_to_D"] for row in first],
                         [row["association_C_to_D"] for row in second])
        self.assertEqual([row["propagation_probe"]["C_propagates_to_D"] for row in first],
                         [row["propagation_probe"]["C_propagates_to_D"] for row in second])
        self.assertFalse(first[3]["propagation_probe"]["C_propagates_to_D"])
        self.assertTrue(first[4]["propagation_probe"]["C_propagates_to_D"])

    def test_sham_without_D_coactivation_does_not_recover_propagation(self):
        timelines = run()["sham_reactivation"]
        for history in timelines.values():
            self.assertFalse(any(row["propagation_probe"]["C_propagates_to_D"]
                                 for row in history))
        self.assertEqual(timelines["during_bfs"][-1]["association_C_to_D"], "3/8")
        self.assertEqual(timelines["post_bfs"][-1]["association_C_to_D"], "0/1")

    def test_reactivation_is_deterministic_and_does_not_change_its_input(self):
        world = load_exp42_worlds()["during_bfs"]
        before = vars(world).copy()
        self.assertEqual(trajectory(world), trajectory(world))
        self.assertEqual(vars(world), before)

    def test_association_update_is_exact_and_bounded_by_fractional_values(self):
        timelines = run()["paired_reactivation"]
        self.assertEqual(timelines["during_bfs"][-1]["association_C_to_D"], "7/8")
        self.assertEqual(timelines["post_bfs"][-1]["association_C_to_D"], "1/2")


if __name__ == "__main__":
    unittest.main()
