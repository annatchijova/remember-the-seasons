import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ["RAVEN_ANN_BACKEND"] = "kdtree"

from exp52_raven_suppression_semantics import (  # noqa: E402
    _influence_excluded_core,
    _score_vector,
    _suppression_contracts,
    run_experiment,
)
from exp51_raven_h14_longitudinal import build_seed_engine  # noqa: E402


class SuppressionSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="exp52-test-")
        self.engine, _ = build_seed_engine(Path(self.tmp.name) / "seed.sqlite")

    def tearDown(self):
        self.tmp.cleanup()

    def test_result_exclusion_can_coexist_with_influence_leak(self):
        result = _suppression_contracts(self.engine)
        self.assertTrue(result["result_exclusion"]["target_absent_from_ranked"])
        self.assertTrue(result["result_exclusion"]["synaptic_C_present"])
        self.assertTrue(result["raw_source_differs_from_negative_control"])

    def test_influence_policy_matches_no_source_negative_control(self):
        result = _suppression_contracts(self.engine)
        self.assertTrue(result["influence_policy_matches_negative_control"])
        self.assertEqual(
            result["influence_exclusion_non_target_scores"],
            result["no_source_negative_control_non_target_scores"],
        )

    def test_mutation_bypassing_source_filter_is_detected(self):
        target = self.engine._db.load_memory("A")
        mutant = _influence_excluded_core(
            self.engine, "B", 1001.0, ["A"], target.cell_id,
            mutation_bypass_source_filter=True,
        )
        clean = _influence_excluded_core(
            self.engine, "B", 1001.0, [], target.cell_id,
        )
        self.assertNotEqual(_score_vector(mutant, {"A"}),
                            _score_vector(clean, {"A"}))

    def test_paired_history_deletes_target_and_incident_links(self):
        result = run_experiment()["paired_history"]
        for arm in ("A_participated", "A_suppressed"):
            self.assertTrue(result[arm]["a_row_absent"])
            self.assertTrue(result[arm]["a_incident_synaptic_links_absent"])
            self.assertTrue(result[arm]["a_incident_cell_links_absent"])
            self.assertEqual(len(result[arm]["post_deletion_checkpoints"]), 4)

    def test_artifact_is_deterministic(self):
        first = json.dumps(run_experiment(), sort_keys=True, separators=(",", ":"))
        second = json.dumps(run_experiment(), sort_keys=True, separators=(",", ":"))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
