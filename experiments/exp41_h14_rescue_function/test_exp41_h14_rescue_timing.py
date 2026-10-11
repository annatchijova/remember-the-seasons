"""Exact checks distinguishing candidate rescue from resumed propagation."""
import unittest
from fractions import Fraction as F

from exp41_h14_rescue_timing import (
    RESCUE_MODES, assay_world, measure_C_effect, recall, run,
)


class TestExp41(unittest.TestCase):
    def test_all_treatments_start_from_the_same_world(self):
        result = run()
        self.assertEqual(set(result["arms"]), set(RESCUE_MODES))
        self.assertTrue(all(arm["world_equals_common_start"] for arm in result["arms"].values()))

    def test_no_rescue_leaves_C_inhibited(self):
        result = recall(assay_world(), rescue_mode="disabled")
        self.assertIn("C", result["inhibited"])
        self.assertNotIn("C", result["candidates"])
        self.assertNotIn("D", result["activated"])

    def test_post_bfs_rescue_restores_availability_without_D_propagation(self):
        result = recall(assay_world(), rescue_mode="post_bfs")
        self.assertIn("C", result["rescued"])
        self.assertIn("C", result["candidates"])
        self.assertNotIn("C", result["processed"])
        self.assertNotIn("D", result["activated"])

    def test_during_bfs_reactivation_propagates_from_C_to_D(self):
        result = recall(assay_world(), rescue_mode="during_bfs")
        self.assertIn("C", result["rescued"])
        self.assertIn("C", result["processed"])
        self.assertIn("D", result["activated"])

    def test_C_score_effect_distinguishes_post_and_during_rescue(self):
        world = assay_world()
        post = measure_C_effect(world, "post_bfs")
        during = measure_C_effect(world, "during_bfs")
        self.assertEqual(post["delta_by_action"], {"X": F(1), "Y": F(0)})
        self.assertEqual(post["delta_margin_X_minus_Y"], F(1))
        self.assertEqual(during["delta_by_action"], {"X": F(1), "Y": F(1)})
        self.assertEqual(during["delta_margin_X_minus_Y"], F(0))
        self.assertEqual(post["choice_with_C"], "X")
        self.assertEqual(during["choice_with_C"], "Y")

    def test_inhibited_arm_has_zero_C_effect_under_this_readout(self):
        effect = measure_C_effect(assay_world(), "disabled")
        self.assertEqual(effect["delta_by_action"], {"X": F(0), "Y": F(0)})
        self.assertEqual(effect["choice_with_C"], effect["choice_C_suppressed"])

    def test_invalid_treatment_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "rescue_mode must be one of"):
            recall(assay_world(), rescue_mode="restore_whole_agent")

    def test_probes_are_read_only_and_result_is_reproducible(self):
        world = assay_world()
        before = (dict(world.states), {node: set(v) for node, v in world.neighbors.items()}, dict(world.links))
        for mode in RESCUE_MODES:
            recall(world, rescue_mode=mode)
            measure_C_effect(world, mode)
        after = (dict(world.states), {node: set(v) for node, v in world.neighbors.items()}, dict(world.links))
        self.assertEqual(before, after)
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
