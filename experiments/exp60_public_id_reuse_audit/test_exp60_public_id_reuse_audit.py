import json
import unittest
from pathlib import Path

from exp60_public_id_reuse_audit import audit


class Exp60PublicIdReuseAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = audit()

    def test_http_request_and_forwarding_do_not_accept_memory_id(self):
        self.assertNotIn("memory_id", self.result["http_store_request_fields"])
        self.assertNotIn("memory_id", self.result["http_store_forwarded_kwargs"])
        self.assertEqual(
            self.result["http_store_forwarded_kwargs"],
            ["author_id", "content", "embedding", "layer", "metadata", "session_id", "state"],
        )

    def test_mcp_signature_and_forwarding_do_not_accept_memory_id(self):
        self.assertNotIn("memory_id", self.result["mcp_store_parameters"])
        self.assertNotIn("memory_id", self.result["mcp_store_forwarded_kwargs"])

    def test_engine_generates_id_and_low_level_replace_is_internal_callsite(self):
        self.assertNotIn("memory_id", self.result["engine_store_parameters"])
        self.assertEqual(self.result["generated_memory_id_assignment_line"], 1542)
        self.assertEqual(self.result["low_level_store_memory_callsites"], [
            {"file": "raven/memory_engine.py", "line": 1562, "owner": "store"}
        ])
        self.assertTrue(self.result["low_level_store_uses_insert_or_replace"])

    def test_source_hashes_match_pinned_snapshot(self):
        self.assertEqual(self.result["source_commit"], "56df6cfdd7f3dd3000bfd7ce8cc42606d66a191f")
        self.assertEqual(len(self.result["source_file_sha256"]), 3)

    def test_replay_is_deterministic(self):
        self.assertEqual(audit(), self.result)

    def test_committed_result_matches_runner(self):
        artifact = json.loads((Path(__file__).parent / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(artifact, self.result)


if __name__ == "__main__":
    unittest.main()
