import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from exp54_raven_observational_contract import run_experiment


class RavenObservationalContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_experiment()

    def test_counter_pair_is_retrieval_equivalent_but_operationally_visible(self):
        pair = self.result["initial_counter_pair"]
        self.assertTrue(pair["retrieval_equivalent"])
        self.assertNotEqual(pair["S5_total_recalls"], pair["S4_total_recalls"])
        self.assertEqual(pair["S5_memory_recall_counts"]["C"], 5)
        self.assertEqual(pair["S4_memory_recall_counts"]["C"], 4)

    def test_every_selected_mutating_action_preserves_bounded_retrieval_equivalence(self):
        actions = self.result["selected_action_congruence"]
        self.assertEqual(set(actions), {
            "recall", "store", "reinforce", "forget", "create_cell_link",
        })
        for name, record in actions.items():
            with self.subTest(action=name):
                self.assertTrue(record["immediate_outputs_equal"])
                self.assertTrue(record["successor_retrieval_equivalent"])
                self.assertEqual(
                    record["successor_total_recalls"][0]
                    - record["successor_total_recalls"][1], 1,
                )

    def test_row_permutation_preserves_logical_state_retrieval_and_full_graph(self):
        probe = self.result["sqlite_row_order_probe"]
        self.assertTrue(probe["logical_memory_rows_equal"])
        self.assertNotEqual(
            probe["physical_row_order"]["normal"],
            probe["physical_row_order"]["reversed"],
        )
        self.assertTrue(probe["retrieval_equivalent_after_permutation"])
        self.assertTrue(probe["full_graph_node_order_equal"])

    def test_truncated_export_tie_is_sensitive_and_secondary_key_is_stable(self):
        probe = self.result["sqlite_row_order_probe"]
        original = probe["original_truncated_graph_ids"]
        fixed = probe["experimental_secondary_key_ids"]
        self.assertEqual(original["normal"], ["B"])
        self.assertEqual(original["reversed"], ["C"])
        self.assertFalse(original["equal"])
        self.assertEqual(fixed, {"normal": ["B"], "reversed": ["B"], "equal": True})

    def test_unfixed_order_is_a_negative_control_for_the_secondary_key(self):
        """Removing the secondary key restores the observed row-order divergence."""
        probe = self.result["sqlite_row_order_probe"]
        original = probe["original_truncated_graph_ids"]
        fixed = probe["experimental_secondary_key_ids"]
        self.assertNotEqual(original["normal"], original["reversed"])
        self.assertEqual(fixed["normal"], fixed["reversed"])

    def test_action_inventory_and_scope_are_explicit(self):
        inventory = self.result["source_inventory"]
        self.assertIn("POST /recall", inventory["fastapi_public_routes"][
            "mutating_or_observation_with_possible_write"
        ])
        self.assertIn("GET /metrics", inventory["fastapi_public_routes"]["read_or_observe"])
        self.assertIn("raven_export_graph", inventory["mcp_tools"])
        self.assertIn("not enumerated", inventory["classification_limit"])

    def test_result_is_byte_stable_as_canonical_json(self):
        one = json.dumps(self.result, sort_keys=True, separators=(",", ":"))
        two = json.dumps(run_experiment(), sort_keys=True, separators=(",", ":"))
        self.assertEqual(one, two)


if __name__ == "__main__":
    unittest.main()
