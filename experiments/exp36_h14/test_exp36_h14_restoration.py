"""Focused invariants and regression tests for the H14 toy harness."""
import unittest
from fractions import Fraction as F
from exp36_h14_restoration import (
    QUERIES, base_world, contribution, decision, influence_vector, learn,
    reinstate, run, shared_link_aging, suppress,
)


class TestH14(unittest.TestCase):
    def test_neutralization_is_read_only_and_blocks_incident_paths(self):
        w = base_world()
        before = w.clone()
        q = QUERIES[0]
        zero = contribution(w, q, neutralize="A")
        for edge, strength in w.links.items():
            if "A" in edge:
                self.assertNotEqual(strength, F(0))
        self.assertEqual(zero["A"], 0)
        self.assertEqual(w, before)
        self.assertEqual(zero, contribution(w, q, neutralize="A"))

    def test_absence_does_not_train_intrinsic_A(self):
        w = base_world()
        original = w.strength["A"]
        suppress(w)
        for q in QUERIES:
            learn(w, q)
            shared_link_aging(w)
        self.assertEqual(w.strength["A"], original)
        self.assertNotIn("A", w.available)
        self.assertIn(("A", "B"), w.links)  # retained in shared record

    def test_factorial_is_orthogonal_at_intervention(self):
        historic = base_world()
        current = historic.clone()
        suppress(current)
        for _ in range(4):
            shared_link_aging(current)
        for own in (False, True):
            for edges in (False, True):
                w = current.clone()
                reinstate(w, historic, own, edges)
                self.assertEqual(w.strength["A"], historic.strength["A"] if own else F(1))
                self.assertEqual(w.strength["B"], current.strength["B"])
                expected = historic.links[("A", "B")] if edges else (current.links[("A", "B")] if own else None)
                self.assertEqual(w.links.get(("A", "B")), expected)

    def test_reproducible_and_six_arms(self):
        first = run()
        self.assertEqual(first, run())
        self.assertEqual(set(first["initial"]), {"no_absence", "reexposure", "strict", "links_only", "state_and_links", "relearning"})
        self.assertEqual(first["hamming_to_no_absence"]["no_absence"], 0)

    def test_no_replay_mutation_from_measurement(self):
        w = base_world()
        before = w.clone()
        for _ in range(4):
            influence_vector(w)
            decision(w, QUERIES[0], neutralize="A")
        self.assertEqual(w, before)


if __name__ == "__main__":
    unittest.main()
