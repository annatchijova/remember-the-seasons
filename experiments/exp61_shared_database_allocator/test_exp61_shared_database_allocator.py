import json
import unittest
from pathlib import Path

from exp61_shared_database_allocator import run


class SharedDatabaseAllocatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run()

    def test_single_engine_control_preserves_both_rows(self):
        control = self.result["single_engine_control"]
        self.assertEqual([item[1] for item in control["returned"]], [0, 1])
        self.assertEqual(len(control["rows"]), 2)

    def test_stale_allocators_replace_row_on_unique_cell_conflict(self):
        assay = self.result["stale_allocators_different_content"]
        ids, cells = [x[0] for x in assay["returned"]], [x[1] for x in assay["returned"]]
        self.assertNotEqual(ids[0], ids[1])
        self.assertEqual(cells, [0, 0])
        self.assertEqual(len(assay["rows"]), 1)
        self.assertEqual(assay["rows"][0]["memory_id"], ids[1])

    def test_same_content_and_millisecond_reuses_exact_id_with_audit_trace(self):
        assay = self.result["stale_allocators_same_content"]
        self.assertTrue(assay["same_memory_id"])
        self.assertEqual(assay["returned"][0], assay["returned"][1])
        self.assertEqual(assay["audit_count_before_replacement"], 1)
        self.assertEqual(assay["audit_count_after_replacement"], 1)
        self.assertEqual(len(assay["rows"]), 1)
        self.assertEqual(assay["rows"][0]["embedding_hex"], bytes.fromhex("000000000000803f0000000000000000").hex())

    def test_reload_control_advances_allocator_and_preserves_both_rows(self):
        control = self.result["reloaded_second_engine_control"]
        self.assertEqual([item[1] for item in control["returned"]], [0, 1])
        self.assertNotEqual(control["returned"][0][0], control["returned"][1][0])
        self.assertEqual(len(control["rows"]), 2)

    def test_source_copy_matches_pinned_commit(self):
        self.assertEqual(self.result["copied_engine_sha256"], "ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0")
        self.assertEqual(self.result["copied_spectral_sha256"], "36d5a1198a9f7a817ec8cd540f2f4c8c1c9a0c26e74782c2ef4d38fcf257ca90")
        self.assertEqual(self.result["copied_consolidator_sha256"], "9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39")

    def test_recorded_result_matches_replay(self):
        recorded = json.loads((Path(__file__).parent / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(recorded, self.result)


if __name__ == "__main__":
    unittest.main()
