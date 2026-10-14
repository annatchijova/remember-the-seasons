"""Falsifiable checks for Exp59 memory-ID reincarnation."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from exp59_raven_memory_id_reincarnation import run_experiment


class Exp59MemoryIdReincarnationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_experiment()

    def test_old_counts_affect_new_content_under_reused_ids(self) -> None:
        assay = self.result["same_id_reincarnation"]
        self.assertTrue(assay["current_state_equal_before_consolidation"])
        self.assertTrue(assay["audit_histories_distinct_before_consolidation"])
        self.assertTrue(all(assay["same_id_directional_effect"].values()))
        self.assertEqual(assay["branches"]["R54"]["counts"], {"C": 5, "D": 4})
        self.assertEqual(assay["branches"]["R45"]["counts"], {"C": 4, "D": 5})

    def test_audit_events_describe_previous_content_incarnations(self) -> None:
        assay = self.result["same_id_reincarnation"]
        for branch in ("R54", "R45"):
            historical = assay["historical_content_hashes"][branch]
            current = assay["current_content_hashes"][branch]
            for memory_id in ("C", "D"):
                self.assertEqual(len(historical[memory_id]), 1)
                self.assertNotEqual(historical[memory_id][0], current[memory_id])

    def test_fresh_ids_do_not_inherit_old_counts(self) -> None:
        control = self.result["fresh_id_control"]
        self.assertTrue(control["current_state_equal_before_consolidation"])
        self.assertTrue(control["audit_histories_distinct_before_consolidation"])
        self.assertTrue(control["fresh_id_outputs_equal"])
        for branch in ("R54", "R45"):
            self.assertEqual(control["branches"][branch]["counts"],
                             {"C_reborn": 0, "D_reborn": 0})

    def test_content_hash_filtered_mutation_removes_effect(self) -> None:
        mutation = self.result["content_hash_mutation_control"]
        self.assertEqual(mutation["mutation_counts"]["R54"], {"C": 0, "D": 0})
        self.assertEqual(mutation["mutation_counts"]["R45"], {"C": 0, "D": 0})
        self.assertTrue(mutation["mutated_embeddings_equal"])

    def test_full_run_replays_canonically(self) -> None:
        replay = run_experiment()
        canonical = lambda value: json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        self.assertEqual(canonical(self.result), canonical(replay))


if __name__ == "__main__":
    unittest.main()
