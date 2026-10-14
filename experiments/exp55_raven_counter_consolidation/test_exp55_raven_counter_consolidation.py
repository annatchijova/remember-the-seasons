"""Falsifiable integration checks for the preregistered Exp55 assay."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import exp55_raven_counter_consolidation as exp55  # noqa: E402


class CounterConsolidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = exp55.run_experiment()

    def test_primary_counter_only_difference_does_not_change_real_consolidation(self):
        primary = self.result["primary_counter_only_comparison"]
        self.assertEqual(primary["fixture_groups"], [["C", "D"]])
        self.assertEqual(len(primary["common_pre_treatment_state_sha256"]), 64)
        self.assertTrue(primary["non_counter_state_equal_before"])
        self.assertTrue(primary["pre_consolidation_retrieval_equal"])
        self.assertTrue(primary["merged_embedding_equal"])
        self.assertTrue(primary["logical_database_equal_after"])
        self.assertTrue(primary["retrieval_equal_after"])
        self.assertTrue(primary["equalized_matches_S4"])
        for branch in (primary["S5"], primary["S4"]):
            self.assertEqual(branch["run_result"]["merged"], 2)
            self.assertEqual(branch["run_result"]["created"], 1)
            self.assertEqual(branch["sources"], ["C", "D"])
            self.assertEqual(branch["audit_weight_counts"], {"C": 0, "D": 0})
            self.assertEqual(branch["metadata"]["recall_counts"], {"C": 0, "D": 0})

    def test_audit_weight_canary_changes_merged_vector_and_both_query_scores(self):
        canary = self.result["audit_weight_sensitivity_canary"]
        self.assertEqual(canary["audit_counts_A54"], {"C": 5, "D": 4})
        self.assertEqual(canary["audit_counts_A44"], {"C": 4, "D": 4})
        self.assertTrue(canary["persisted_counts_equal_before_consolidation"])
        self.assertTrue(canary["merged_embedding_different"])
        self.assertTrue(canary["cosine_C_A54_greater"])
        self.assertTrue(canary["cosine_D_A54_lower"])
        self.assertTrue(canary["base_score_C_A54_greater"])
        self.assertTrue(canary["base_score_D_A54_lower"])

    def test_raven_copy_matches_exp51_source_provenance(self):
        self.assertEqual(self.result["source_commit"], exp55.SOURCE_COMMIT)
        self.assertEqual(self.result["source_copy_hashes"], exp55.SOURCE_HASHES)

    def test_runner_replays_to_identical_canonical_json(self):
        first = json.dumps(self.result, sort_keys=True, separators=(",", ":"),
                           allow_nan=False)
        second_result = exp55.run_experiment()
        second = json.dumps(second_result, sort_keys=True, separators=(",", ":"),
                            allow_nan=False)
        self.assertEqual(first, second)

    def test_mutant_using_persisted_row_counters_is_detected(self):
        """The primary oracle must turn red if consolidation reads the wrong source."""
        with tempfile.TemporaryDirectory(prefix="exp55-mutant-") as temp:
            root = Path(temp)
            s5, s4, _equalized = exp55._build_primary_pair(root)

            def mutated_counter_reader(db_path: Path, memory_ids: list[str]) -> dict[str, int]:
                placeholders = ",".join("?" for _ in memory_ids)
                with sqlite3.connect(db_path) as conn:
                    rows = conn.execute(
                        f"SELECT memory_id,recall_count FROM memories "
                        f"WHERE memory_id IN ({placeholders})",
                        memory_ids,
                    ).fetchall()
                return dict(rows)

            with patch.object(
                exp55.sleep_consolidator,
                "get_recall_counts",
                side_effect=mutated_counter_reader,
            ):
                mutant_s5 = exp55._run_consolidation(s5)
                mutant_s4 = exp55._run_consolidation(s4)

            self.assertNotEqual(mutant_s5["embedding_hex"], mutant_s4["embedding_hex"])
            self.assertNotEqual(mutant_s5["retrieval"], mutant_s4["retrieval"])
            self.assertGreater(
                mutant_s5["retrieval"]["C"]["scores"][0]["base_score"],
                mutant_s4["retrieval"]["C"]["scores"][0]["base_score"],
            )


if __name__ == "__main__":
    unittest.main()
