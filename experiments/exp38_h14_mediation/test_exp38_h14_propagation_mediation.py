"""Exact oracles for mediated influence under bounded DAG propagation."""
import unittest
from fractions import Fraction as F

from exp38_h14_propagation_mediation import (
    NODES, QUERY, World, assay_world, enumerate_target_paths, neutralization_effect,
    one_step_effect, propagate, run,
)


class TestExp38(unittest.TestCase):
    def test_two_hop_path_is_absent_from_exp37_one_step_measure(self):
        world = assay_world()
        one_hop = one_step_effect(world, QUERY, target="A")
        recursive = neutralization_effect(world, QUERY, target="A")["delta_by_node"]
        self.assertEqual(one_hop["C"], F(0))
        self.assertEqual(recursive["C"], F(1, 4))

    def test_neutralizing_A_changes_only_nodes_reached_through_A(self):
        result = neutralization_effect(assay_world(), QUERY, target="A")
        self.assertEqual(result["delta_by_node"], {
            "A": F(1), "B": F(1, 2), "C": F(1, 4), "D": F(0)
        })
        # The independent D -> C path remains in the neutralized world.
        self.assertEqual(result["activation_neutralized"]["C"], F(1, 3))
        self.assertEqual(result["delta_by_action"], {"X": F(5, 4), "Y": F(1, 2)})
        self.assertEqual(result["delta_margin_X_minus_Y"], F(3, 4))

    def test_independent_path_enumerator_matches_recursive_counterfactual(self):
        world = assay_world()
        observed = neutralization_effect(world, QUERY, target="A")["delta_by_node"]
        oracle = enumerate_target_paths(world, QUERY, target="A")["by_destination"]
        self.assertEqual(observed, oracle)

    def test_path_decomposition_contains_direct_one_hop_and_two_hop_terms(self):
        decomposition = enumerate_target_paths(assay_world(), QUERY, target="A")
        self.assertEqual(decomposition["by_length"]["A"], {0: F(1)})
        self.assertEqual(decomposition["by_length"]["B"], {1: F(1, 2)})
        self.assertEqual(decomposition["by_length"]["C"], {2: F(1, 4)})
        self.assertEqual(decomposition["by_length"]["D"], {})

    def test_neutralizing_mediator_B_blocks_its_downstream_path(self):
        result = neutralization_effect(assay_world(), QUERY, target="B")
        self.assertEqual(result["delta_by_node"], {
            "A": F(0), "B": F(1, 2), "C": F(1, 4), "D": F(0)
        })

    def test_cycles_are_rejected_instead_of_silently_truncated(self):
        world = World(links={("A", "B"): F(1, 2), ("B", "A"): F(1, 2)})
        with self.assertRaisesRegex(ValueError, "must be acyclic"):
            propagate(world, {node: F(0) for node in NODES})

    def test_run_is_reproducible_and_reports_predeclared_falsifier(self):
        self.assertEqual(run(), run())
        result = run()
        self.assertEqual(result["recursive_A_effect_by_node"]["C"], "1/4")
        self.assertEqual(result["one_step_A_effect_by_node"]["C"], "0/1")
        self.assertTrue(result["predeclared_prediction"]["recursive_neutralization_equals_independent_path_sum"])


if __name__ == "__main__":
    unittest.main()
