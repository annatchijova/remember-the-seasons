"""Falsifiable checks for the Exp57 temporal-recency assay."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from exp57_raven_temporal_recency import run_experiment


class Exp57TemporalRecencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_experiment()

    def test_temporal_assignment_changes_preconsolidation_scores(self) -> None:
        assay = self.result["assay"]
        self.assertTrue(assay["pre_retrieval_temporal_difference"])
        self.assertTrue(assay["pre_retrieval_recency_directions_match"])
        branches = assay["branches"]
        self.assertEqual(branches["T1"]["history"]["audit_counts"], {"C": 5, "D": 4})
        self.assertEqual(branches["T2"]["history"]["audit_counts"], {"C": 5, "D": 4})

    def test_equalizing_last_activation_removes_prequery_difference(self) -> None:
        self.assertTrue(
            self.result["assay"]["equalized_pre_retrieval_traces_match"]
        )

    def test_consolidation_drops_the_measured_recency_difference(self) -> None:
        assay = self.result["assay"]
        self.assertTrue(assay["post_consolidation_outputs_match"])
        self.assertTrue(assay["merged_nodes_start_without_recency"])
        self.assertEqual(
            assay["consolidated"]["T1"]["merged_embedding_hex"],
            assay["consolidated"]["T2"]["merged_embedding_hex"],
        )

    def test_zero_recency_mutation_removes_temporal_contrast(self) -> None:
        self.assertTrue(
            self.result["mutation_control"]["temporal_trace_difference_removed"]
        )

    def test_full_run_replays_byte_for_byte(self) -> None:
        replay = run_experiment()
        canonical = lambda value: json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        self.assertEqual(canonical(self.result), canonical(replay))


if __name__ == "__main__":
    unittest.main()
