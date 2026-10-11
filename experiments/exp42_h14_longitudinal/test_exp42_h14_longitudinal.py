"""Falsifiable invariants and exact predictions for Exp42."""
import unittest
from fractions import Fraction as F

from exp42_h14_longitudinal import MODES, State, initial_world, recall, run, simulate


class TestExp42(unittest.TestCase):
    def test_training_branches_diverge_only_after_shared_experience_updates(self):
        data = run()
        timelines = data["timeline_by_training_mode"]
        for mode in MODES:
            self.assertEqual(len(timelines[mode]), 10)
            self.assertEqual(timelines[mode][0]["label"], "baseline")
            self.assertTrue(timelines[mode][0]["propagation_probe"]["C_can_propagate_to_D"])
        during = timelines["during_bfs"]
        post = timelines["post_bfs"]
        self.assertEqual(during[1]["propagation_probe"]["C_to_D_association"], "5/8")
        self.assertEqual(post[1]["propagation_probe"]["C_to_D_association"], "1/2")
        self.assertEqual(during[4]["states"]["D"], State.REINFORCED.value)
        self.assertEqual(post[4]["states"]["D"], State.NEUTRAL.value)

    def test_same_experience_schedule_and_washout_policy_for_all_branches(self):
        data = run()
        for timeline in data["timeline_by_training_mode"].values():
            self.assertEqual([item["label"] for item in timeline],
                             ["baseline"] + [f"training_{i}" for i in range(1, 5)]
                             + [f"washout_{i}" for i in range(1, 6)])
            self.assertTrue(all(item["mode"] == "post_bfs" for item in timeline[5:]))

    def test_propagation_difference_survives_initial_washout_steps_then_expires(self):
        data = run()["timeline_by_training_mode"]
        during = data["during_bfs"]
        post = data["post_bfs"]
        self.assertEqual(during[5]["propagation_probe"]["C_to_D_association"], "7/8")
        self.assertTrue(during[5]["propagation_probe"]["C_can_propagate_to_D"])
        self.assertEqual(post[5]["propagation_probe"]["C_to_D_association"], "3/8")
        self.assertFalse(post[5]["propagation_probe"]["C_can_propagate_to_D"])
        self.assertEqual(during[8]["states"]["D"], State.REINFORCED.value)
        self.assertEqual(post[8]["states"]["D"], State.NEUTRAL.value)
        self.assertFalse(during[9]["propagation_probe"]["C_can_propagate_to_D"])
        self.assertFalse(post[9]["propagation_probe"]["C_can_propagate_to_D"])
        self.assertEqual(during[9]["states"]["D"], State.NEUTRAL.value)
        self.assertNotEqual(during[9]["propagation_probe"]["C_to_D_association"],
                            post[9]["propagation_probe"]["C_to_D_association"])

    def test_causal_scores_separate_during_treatment_but_converge_in_washout(self):
        timelines = run()["timeline_by_training_mode"]
        during_training = timelines["during_bfs"][4]["causal_C_effect"]
        post_training = timelines["post_bfs"][4]["causal_C_effect"]
        self.assertEqual(during_training["delta_by_action"], {"X": "1/1", "Y": "1/1"})
        self.assertEqual(post_training["delta_by_action"], {"X": "1/1", "Y": "0/1"})
        during_washout = timelines["during_bfs"][5]["causal_C_effect"]
        post_washout = timelines["post_bfs"][5]["causal_C_effect"]
        self.assertEqual(during_washout, post_washout)
        self.assertEqual(during_washout["delta_by_action"], {"X": "1/1", "Y": "0/1"})

    def test_no_learning_control_has_no_persistent_state_or_association_difference(self):
        controls = run()["no_learning_negative_control"]["final_by_training_mode"]
        values = list(controls.values())
        self.assertTrue(all(item["cd_association"] == "1/2" for item in values))
        self.assertTrue(all(item["states"] == values[0]["states"] for item in values))
        self.assertTrue(all(item["familiarity"] == values[0]["familiarity"] for item in values))

    def test_recall_and_measurement_probes_do_not_mutate_world(self):
        world = initial_world()
        before = (dict(world.familiarity), dict(world.states),
                  {node: set(items) for node, items in world.neighbors.items()},
                  set(world.inhibitory_links), world.cd_association)
        for mode in MODES:
            recall(world, mode)
        after = (dict(world.familiarity), dict(world.states),
                 {node: set(items) for node, items in world.neighbors.items()},
                 set(world.inhibitory_links), world.cd_association)
        self.assertEqual(before, after)

    def test_causal_score_effect_uses_exact_rational_association_weight(self):
        timeline = run()["timeline_by_training_mode"]["during_bfs"]
        self.assertEqual(timeline[4]["causal_C_effect"]["score_with_C"]["Y"], "5/4")
        self.assertEqual(timeline[4]["causal_C_effect"]["score_C_suppressed"]["Y"], "1/4")
        self.assertEqual(timeline[4]["causal_C_effect"]["delta_margin_X_minus_Y"], "0/1")

    def test_invalid_mode_and_negative_hops_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "mode must be one of"):
            recall(initial_world(), "restore_all")
        with self.assertRaisesRegex(ValueError, "hops must be >= 0"):
            recall(initial_world(), "disabled", hops=-1)

    def test_no_learning_trajectory_is_deterministic(self):
        self.assertEqual(simulate("during_bfs", learning_enabled=False),
                         simulate("during_bfs", learning_enabled=False))


if __name__ == "__main__":
    unittest.main()
