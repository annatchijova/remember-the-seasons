import copy
import json
import unittest

from exp53_raven_latent_trace import run_experiment


class LatentTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_experiment()

    def test_paired_states_differ_only_in_declared_counter(self):
        pair = self.result["paired_state_differences"]
        self.assertTrue(pair["all_non_counter_fields_and_audit_rows_equal"])
        self.assertEqual(pair["S5_non_counter_sha256"], pair["S4_non_counter_sha256"])

    def test_counter_does_not_change_fixed_core_scores_or_rankings(self):
        equivalent = self.result["retrieval_score_and_rank_equivalence_by_query"]
        self.assertEqual(equivalent, {"A": True, "B": True, "C": True, "D": True})

    def test_telemetry_and_truncated_graph_expose_counter_difference(self):
        outputs = self.result["telemetry_and_export"]
        self.assertEqual(outputs["S5_total_recalls"], 9)
        self.assertEqual(outputs["S4_total_recalls"], 8)
        self.assertEqual(outputs["S5_C_inspection_recall_count"], 5)
        self.assertEqual(outputs["S4_C_inspection_recall_count"], 4)
        self.assertEqual(outputs["S5_truncated_graph"]["nodes"][0]["memory_id"], "C")
        self.assertEqual(outputs["S4_truncated_graph"]["nodes"][0]["memory_id"], "B")

    def test_sleep_consolidator_uses_same_audit_counts_and_matches(self):
        result = self.result["sleep_consolidator"]
        self.assertTrue(result["dry_run_outputs_equal_with_identical_audit_logs"])
        self.assertEqual(result["S5_dry_run"]["groups"], result["S4_dry_run"]["groups"])

    def test_equalized_counter_control_removes_output_differences(self):
        control = self.result["equalized_counter_control"]
        self.assertEqual(set(control), {
            "retrieval", "stats", "inspection", "truncated_graph",
            "sleep_consolidator_dry_run",
        })
        self.assertTrue(all(control.values()))

    def test_counter_dependent_score_mutation_is_detected(self):
        outputs = self.result["retrieval_outputs"]
        s5 = copy.deepcopy(outputs["S5"]["C"]["scores"])
        s4 = copy.deepcopy(outputs["S4"]["C"]["scores"])
        # Deliberate hypothetical scoring mutation: add 0.001 per persisted
        # recall to each score. The exact-vector equality oracle must turn red.
        counts_s5 = {"A": 0, "B": 4, "C": 5, "D": 0}
        counts_s4 = {"A": 0, "B": 4, "C": 4, "D": 0}
        mutated_s5 = {
            row["memory_id"]: row["score"] + 0.001 * counts_s5[row["memory_id"]]
            for row in s5
        }
        mutated_s4 = {
            row["memory_id"]: row["score"] + 0.001 * counts_s4[row["memory_id"]]
            for row in s4
        }
        self.assertNotEqual(mutated_s5, mutated_s4)

    def test_full_result_is_deterministic(self):
        first = json.dumps(self.result, sort_keys=True, separators=(",", ":"))
        second = json.dumps(run_experiment(), sort_keys=True, separators=(",", ":"))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
