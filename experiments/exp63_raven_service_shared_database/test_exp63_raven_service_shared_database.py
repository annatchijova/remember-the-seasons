"""Falsifiable checks for the Exp63 cross-service shared-file assay."""

from __future__ import annotations

import json
import unittest

from exp63_raven_service_shared_database import run


class RavenServiceSharedDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run()

    def test_both_service_engines_loaded_before_concurrent_stores(self):
        self.assertEqual(
            self.result["concurrent_different_content"]["ready"],
            [["api", 0], ["mcp", 0]],
        )

    def test_cross_service_allocator_collision_replaces_a_row(self):
        observed = self.result["concurrent_different_content"]
        self.assertEqual(observed["row_count"], 1)
        self.assertTrue(observed["surviving_row_is_a_contender"])
        self.assertEqual({item[2] for item in observed["returned"]}, {0})

    def test_identical_content_reuses_id_and_keeps_id_keyed_audit_count(self):
        observed = self.result["sequential_same_id"]
        self.assertEqual(observed["ready"], [["api", 0], ["mcp", 0]])
        self.assertTrue(observed["same_memory_id"])
        self.assertEqual(observed["audit_count_before_replacement"], 1)
        self.assertEqual(observed["audit_count_after_replacement"], 1)
        self.assertTrue(observed["replacement_matches_second_store"])
        self.assertEqual(len(observed["rows"]), 1)

    def test_replacement_row_matches_second_service_identity_and_content(self):
        observed = self.result["sequential_same_id"]
        api_result, mcp_result = observed["returned"]
        row = observed["rows"][0]
        self.assertEqual(row["memory_id"], mcp_result[1])
        self.assertEqual(row["cell_id"], mcp_result[2])
        self.assertEqual(row["content"], "same payload alpha")
        self.assertEqual(api_result[1], mcp_result[1])

    def test_starting_second_service_after_first_store_preserves_both_rows(self):
        observed = self.result["cross_service_reload_control"]
        self.assertEqual(observed["ready"], [0, 1])
        self.assertEqual([item[2] for item in observed["returned"]], [0, 1])
        self.assertEqual(len(observed["rows"]), 2)

    def test_reload_control_preserves_each_services_id_and_payload(self):
        observed = self.result["cross_service_reload_control"]
        self.assertEqual(
            [(row["cell_id"], row["content"]) for row in observed["rows"]],
            [(0, "reload alpha"), (1, "reload beta")],
        )
        self.assertEqual(
            [row["memory_id"] for row in observed["rows"]],
            [item[1] for item in observed["returned"]],
        )

    def test_recorded_result_matches_fresh_replay(self):
        with open("result.json", encoding="utf-8") as stream:
            recorded = json.load(stream)
        self.assertEqual(recorded, self.result)


if __name__ == "__main__":
    unittest.main()
