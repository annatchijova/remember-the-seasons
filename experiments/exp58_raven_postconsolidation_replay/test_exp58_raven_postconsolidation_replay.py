"""Falsifiable checks for Exp58 post-consolidation replay."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from exp58_raven_postconsolidation_replay import run_experiment


class Exp58PostConsolidationReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_experiment()

    def test_same_inputs_preserve_behavior_and_memory_state(self) -> None:
        assay = self.result["trajectory_assay"]
        self.assertTrue(assay["initial_memory_and_link_state_equal"])
        self.assertTrue(assay["all_steps_equal"])
        self.assertEqual(assay["per_step_observations_and_state_equal"], [True] * 8)

    def test_audit_histories_and_each_new_audit_hash_remain_distinct(self) -> None:
        assay = self.result["trajectory_assay"]
        self.assertTrue(assay["initial_audit_histories_distinct"])
        self.assertTrue(assay["final_audit_histories_distinct"])
        self.assertTrue(assay["all_step_audit_hashes_distinct"])

    def test_both_audit_chains_remain_valid(self) -> None:
        verdicts = self.result["trajectory_assay"]["audit_chain_verification"]
        self.assertEqual(set(verdicts), {"T1", "T2"})
        for verdict in verdicts.values():
            self.assertTrue(verdict["chain_intact"])
            self.assertTrue(verdict["hash_integrity"])
            self.assertEqual(verdict["issue_count"], 0)

    def test_state_sensitivity_control_is_detected(self) -> None:
        self.assertTrue(self.result["state_sensitivity_control"]["state_change_detected"])

    def test_full_run_replays_canonically(self) -> None:
        replay = run_experiment()
        canonical = lambda value: json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        self.assertEqual(canonical(self.result), canonical(replay))


if __name__ == "__main__":
    unittest.main()
