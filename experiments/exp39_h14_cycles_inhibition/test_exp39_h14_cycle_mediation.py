"""Exact checks for cyclic propagation, inhibition, and finite path sums."""
import unittest
from fractions import Fraction as F

from exp39_h14_cycle_mediation import (
    NODES, QUERY, World, assay_world, contraction_bound, finite_walk_sum,
    fixed_point, neutralization_effect, one_step_effect, run, verify_fixed_point,
)


class TestExp39(unittest.TestCase):
    def test_stable_signed_cycle_has_exact_fixed_point(self):
        world = assay_world()
        activation = fixed_point(world, QUERY)
        self.assertEqual(activation, {
            "A": F(8, 9), "B": F(4, 9), "C": F(5, 9), "D": F(1)
        })
        self.assertTrue(verify_fixed_point(world, QUERY, activation))
        self.assertEqual(contraction_bound(world, world.available), F(5, 6))

    def test_neutralizing_A_keeps_independent_D_path_and_measures_signed_feedback(self):
        result = neutralization_effect(assay_world(), QUERY, target="A")
        self.assertEqual(result["activation_neutralized"], {
            "A": F(0), "B": F(0), "C": F(1, 3), "D": F(1)
        })
        self.assertEqual(result["delta_by_node"], {
            "A": F(8, 9), "B": F(4, 9), "C": F(2, 9), "D": F(0)
        })
        self.assertEqual(result["delta_by_action"], {"X": F(10, 9), "Y": F(4, 9)})
        self.assertEqual(result["delta_margin_X_minus_Y"], F(2, 3))

    def test_exp37_one_step_misses_cycle_and_downstream_effects(self):
        world = assay_world()
        one_step = one_step_effect(world, QUERY, target="A")
        exact = neutralization_effect(world, QUERY, target="A")["delta_by_node"]
        self.assertEqual(one_step, {"A": F(1), "B": F(1, 2), "C": F(0), "D": F(0)})
        self.assertEqual(exact["C"], F(2, 9))

    def test_finite_signed_walk_prefixes_approach_but_do_not_equal_fixed_point(self):
        world = assay_world()
        exact = neutralization_effect(world, QUERY, target="A")["delta_by_node"]["C"]
        values = [finite_walk_sum(world, QUERY, "A", hops)["by_node"]["C"]
                  for hops in (2, 4, 6, 8, 10)]
        self.assertEqual(values, [F(1, 4), F(7, 32), F(57, 256), F(455, 2048), F(3641, 16384)])
        self.assertTrue(all(value != exact for value in values))
        self.assertTrue(all(abs(values[i + 1] - exact) < abs(values[i] - exact)
                            for i in range(len(values) - 1)))

    def test_inhibitory_mediator_has_negative_effect_on_A_activation(self):
        result = neutralization_effect(assay_world(), QUERY, target="B")
        self.assertEqual(result["delta_by_node"], {
            "A": F(-1, 9), "B": F(4, 9), "C": F(2, 9), "D": F(0)
        })

    def test_noncontractive_cycles_are_rejected(self):
        world = World(links={("A", "B"): F(1), ("B", "A"): F(1)})
        with self.assertRaisesRegex(ValueError, "absolute incoming-weight bound must be < 1"):
            fixed_point(world, {node: F(0) for node in NODES})

    def test_run_is_reproducible_and_matches_predeclared_values(self):
        first = run()
        self.assertEqual(first, run())
        self.assertEqual(first["fixed_point_A_effect_by_node"]["C"], "2/9")
        self.assertEqual(first["exp37_one_step_A_effect_by_node"]["C"], "0/1")
        self.assertTrue(first["fixed_point_equation_verified"])


if __name__ == "__main__":
    unittest.main()
