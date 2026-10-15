import json
import unittest
from pathlib import Path

from exp62_cross_process_allocator import run


class CrossProcessAllocatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run()

    def test_concurrent_processes_share_stale_cell_allocator(self):
        assay = self.result["simultaneous_different_content_processes"]
        self.assertEqual(assay["ready_counters"], [0, 0])
        self.assertEqual([item[1] for item in assay["returned"]], [0, 0])
        self.assertEqual(len({item[0] for item in assay["returned"]}), 2)
        self.assertEqual(assay["row_count"], 1)
        self.assertTrue(assay["surviving_row_is_a_contender"])

    def test_separate_processes_can_reuse_exact_id_and_audit_count(self):
        assay = self.result["sequential_same_id_processes"]
        self.assertEqual(assay["ready_counters"], [0, 0])
        self.assertTrue(assay["same_memory_id"])
        self.assertEqual(assay["returned"][0], assay["returned"][1])
        self.assertEqual(assay["audit_count_before_replacement"], 1)
        self.assertEqual(assay["audit_count_after_replacement"], 1)
        self.assertEqual(len(assay["rows"]), 1)
        self.assertEqual(assay["rows"][0]["embedding_hex"], "000000000000803f0000000000000000")

    def test_starting_second_process_after_first_write_preserves_rows(self):
        control = self.result["reload_control"]
        self.assertEqual(control["ready_counters"], [0, 1])
        self.assertEqual([item[1] for item in control["returned"]], [0, 1])
        self.assertEqual(len(control["rows"]), 2)

    def test_source_copies_match_pinned_snapshot(self):
        hashes = self.result["copied_source_sha256"]
        self.assertEqual(hashes["memory_engine.py"], "ae6527e4b7f7bd444e982971aeffbe8d122eca28e0ebe8ea70149cb89d5d1af0")
        self.assertEqual(hashes["spectral.py"], "36d5a1198a9f7a817ec8cd540f2f4c8c1c9a0c26e74782c2ef4d38fcf257ca90")
        self.assertEqual(hashes["sleep_consolidator.py"], "9e2a0fa1c8b2c5b68bd691511b708644ff1419e5afc04ac1fb692da5729bab39")

    def test_recorded_result_matches_replay(self):
        recorded = json.loads((Path(__file__).parent / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(recorded, self.result)


if __name__ == "__main__":
    unittest.main()
