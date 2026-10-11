"""Falsifiable invariants for the Exp37 measurement instrument."""
import unittest
from fractions import Fraction as F

from exp37_h14_causal_measurement import (
    QUERIES, World, action_scores, base_world, causal_effect, learn, measure, run,
    suppress,
)


class TestExp37(unittest.TestCase):
    def test_signed_effect_retains_magnitude_when_choice_does_not_flip(self):
        world = World()
        world.strength = {n: F(1) for n in ("A", "B", "C", "D")}
        world.links = {("A", "B"): F(1)}
        query = {"A": F(1), "B": F(0), "C": F(0), "D": F(0)}
        effect = causal_effect(world, query)
        self.assertEqual(effect["with_A"], {"X": F(1), "Y": F(1)})
        self.assertEqual(effect["neutralized_A"], {"X": F(0), "Y": F(0)})
        self.assertEqual(effect["delta_by_action"], {"X": F(1), "Y": F(1)})
        self.assertEqual(effect["delta_margin_X_minus_Y"], F(0))
        self.assertEqual(effect["choice_with_A"], effect["choice_neutralized_A"])

    def test_neutralization_effect_has_signed_direction(self):
        world = World()
        world.strength = {n: F(1) for n in ("A", "B", "C", "D")}
        query = {"A": F(1), "B": F(0), "C": F(0), "D": F(0)}
        effect = causal_effect(world, query)
        self.assertEqual(effect["delta_by_action"], {"X": F(1), "Y": F(0)})
        self.assertEqual(effect["delta_margin_X_minus_Y"], F(1))

    def test_incident_links_are_frozen_during_absence_updates(self):
        world = base_world()
        incident_before = {e: v for e, v in world.links.items() if "A" in e}
        suppress(world)
        for i in range(8):
            learn(world, QUERIES[i % len(QUERIES)], frozen_link_nodes=frozenset({"A"}))
        incident_after = {e: v for e, v in world.links.items() if "A" in e}
        self.assertEqual(incident_after, incident_before)

    def test_measurement_does_not_mutate_state(self):
        world = base_world()
        before = world.clone()
        measure(world)
        self.assertEqual(world, before)

    def test_six_arms_and_deterministic_exact_output(self):
        first = run()
        self.assertEqual(first, run())
        self.assertEqual(set(first["arms"]), {
            "no_absence", "reexposure", "strict", "links_only", "state_and_links", "relearning"
        })
        self.assertTrue(first["incident_links_unchanged_during_absence"])
        self.assertEqual(len(first["initial"]["strict"]), len(QUERIES))

    def test_no_measurement_for_unavailable_target(self):
        world = base_world()
        suppress(world)
        with self.assertRaisesRegex(ValueError, "requires A to be available"):
            measure(world)


if __name__ == "__main__":
    unittest.main()
