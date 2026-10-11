"""Exact and counterfactual checks for threshold, inhibition, and rescue."""
import unittest
from fractions import Fraction as F

from exp40_h14_discrete_rescue import (
    LinkType, MemoryState, THRESHOLD, World, assay_world, recall, run,
)


class TestExp40(unittest.TestCase):
    def test_threshold_crossing_discontinuously_changes_C_candidate_state(self):
        world = assay_world()
        below = recall(world, {"A": F(99, 100), "R": F(1)})
        at = recall(world, {"A": THRESHOLD, "R": F(1)})
        self.assertIn("C", below["candidates"])
        self.assertEqual(at["exclusions"].get("C"), "INHIBITED")
        self.assertNotIn("C", at["candidates"])
        self.assertIn("B", at["activated"])

    def test_suppressing_A_recovers_C_via_alternate_path_without_restoring_A_path(self):
        world = assay_world()
        before_edges = {edge: kind for edge, kind in world.links.items()}
        result = recall(world, {"A": F(1), "R": F(1)}, suppressed=frozenset({"A"}))
        self.assertIn("A", result["exclusions"])
        self.assertNotIn("B", result["activated"])
        self.assertIn("C", result["candidates"])
        self.assertIn("D", result["activated"])
        self.assertEqual(world.links, before_edges)
        self.assertEqual(result["first_hop"]["C"], 3)

    def test_reinforced_rescue_restores_candidate_but_does_not_resume_BFS(self):
        world = assay_world(MemoryState.REINFORCED)
        result = recall(world, {"A": F(1), "R": F(1)})
        self.assertIn("B", result["activated"])
        self.assertIn("C", result["rescued"])
        self.assertIn("C", result["candidates"])
        self.assertNotIn("D", result["activated"])
        self.assertEqual(result["first_hop"].get("C"), 3)

    def test_neutral_memory_is_not_rescued_and_forgotten_state_is_not_candidate(self):
        neutral = recall(assay_world(MemoryState.NEUTRAL), {"A": F(1), "R": F(1)})
        forgotten = recall(assay_world(MemoryState.FORGOTTEN), {"A": F(1), "R": F(1)})
        self.assertNotIn("C", neutral["rescued"])
        self.assertNotIn("C", neutral["candidates"])
        self.assertNotIn("C", forgotten["candidates"])

    def test_suppressed_cell_cannot_seed_or_fire_its_inhibitory_link(self):
        world = assay_world()
        result = recall(world, {"A": F(1), "R": F(1)}, suppressed=frozenset({"B"}))
        self.assertNotIn("B", result["activated"])
        self.assertNotIn("C", result["inhibited"])

    def test_neutral_and_resonant_links_each_extend_the_frontier(self):
        for link_type in (LinkType.NEUTRAL, LinkType.RESONANT):
            with self.subTest(link_type=link_type):
                world = World()
                world.links[("A", "B")] = link_type
                result = recall(world, {"A": F(1)})
                self.assertIn("B", result["activated"])

    def test_threshold_is_inclusive_and_nonnegative(self):
        world = assay_world()
        result = recall(world, {"A": THRESHOLD, "R": F(1)})
        self.assertIn("A", result["seeds"])
        with self.assertRaisesRegex(ValueError, "threshold must be >= 0"):
            recall(world, {"A": F(1)}, threshold=F(-1))

    def test_probe_is_read_only_and_output_is_reproducible(self):
        world = assay_world()
        before = (dict(world.states), {n: set(v) for n, v in world.neighbors.items()}, dict(world.links))
        recall(world, {"A": F(1), "R": F(1)})
        after = (dict(world.states), {n: set(v) for n, v in world.neighbors.items()}, dict(world.links))
        self.assertEqual(before, after)
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
