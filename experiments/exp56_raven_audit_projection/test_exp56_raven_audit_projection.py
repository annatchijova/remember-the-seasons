"""Falsifiable checks for the Exp56 audit projection assay."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from exp56_raven_audit_projection import run_experiment


class Exp56AuditProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_experiment()

    def test_equal_count_histories_match_consolidation_and_retrieval(self) -> None:
        assay = self.result["primary_and_control"]
        self.assertTrue(assay["same_count_projection_equal_on_target"])
        self.assertTrue(assay["audit_histories_distinct_H1_H2"])
        self.assertTrue(assay["audit_histories_distinct_H1_H3"])
        branches = assay["branches"]
        self.assertEqual(branches["H1"]["weights"], {"C": 5, "D": 4})
        for condition in ("H2", "H3"):
            self.assertEqual(branches["H1"]["merged_embedding_hex"],
                             branches[condition]["merged_embedding_hex"])
            self.assertEqual(branches["H1"]["retrieval"], branches[condition]["retrieval"])

    def test_equal_total_with_changed_allocation_is_detected(self) -> None:
        canary = self.result["primary_and_control"]["allocation_sensitivity_control"]
        self.assertEqual(
            self.result["primary_and_control"]["branches"]["H1"]["history"]["event_count"],
            self.result["primary_and_control"]["branches"]["H4"]["history"]["event_count"],
        )
        self.assertTrue(all(canary.values()))

    def test_order_sensitive_mutation_is_detected(self) -> None:
        self.assertTrue(
            self.result["mutation_control"]["mutant_embedding_diverges_H1_H2"]
        )

    def test_complete_result_is_reproducible(self) -> None:
        replay = run_experiment()
        canonical = lambda value: json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        self.assertEqual(canonical(self.result), canonical(replay))


if __name__ == "__main__":
    unittest.main()
