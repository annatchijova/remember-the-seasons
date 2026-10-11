import os
import tempfile
import unittest
from pathlib import Path

os.environ["RAVEN_ANN_BACKEND"] = "kdtree"

from exp51_raven_h14_longitudinal import (
    _probe,
    _raw_suppression_leak,
    _state,
    build_seed_engine,
    _neutralize_for_reexposure,
    run_absence_step,
)
from vendor.raven.memory_engine import AdaptiveMemoryEngine


class AbsenceContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine, self.ids = build_seed_engine(Path(self.tmp.name) / "seed.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_absent_target_cannot_seed_or_rank_and_is_not_updated(self):
        target = self.engine._db.load_memory(self.ids["A"])
        before = (target.state, target.last_activation, target.recall_count,
                  dict(target.synaptic_links))
        result = run_absence_step(
            self.engine, self.ids["A"], self.ids["B"],
            query_key="A", now=1000.0,
        )
        after = self.engine._db.load_memory(self.ids["A"])
        self.assertNotIn(self.engine._cell_to_memid.get(target.cell_id), result["ranked_ids"])
        self.assertNotIn(self.ids["A"], result["ranked_ids"])
        self.assertEqual(before, (after.state, after.last_activation,
                                  after.recall_count, dict(after.synaptic_links)))

    def test_full_replay_is_canonical_and_has_six_arms(self):
        from exp51_raven_h14_longitudinal import run_experiment
        first = run_experiment()
        second = run_experiment()
        self.assertEqual(first, second)
        self.assertEqual(set(first["arms"]), {
            "no_absence", "reexposure", "strict_local_restore",
            "links_only_restore", "complete_local_restore", "relearning",
        })

    def test_mutation_bypass_suppression_is_detected(self):
        # Negative control: a broken adapter that evaluates without suppressing
        # the target must violate the declared absence invariant.
        result = run_absence_step(
            self.engine, self.ids["A"], self.ids["B"],
            query_key="A", now=1000.0, mutation_bypass_suppression=True,
        )
        with self.assertRaises(AssertionError):
            self.assertNotIn(self.ids["A"], result["ranked_ids"])

    def test_raw_raven_suppression_leaks_current_turn_source_but_adapter_blocks_it(self):
        finding = _raw_suppression_leak(self.engine, self.ids["A"], "B", 1001.0)
        self.assertTrue(finding["raw_core_emits_linked_C"])
        self.assertFalse(finding["adapted_emits_linked_C"])

    def test_causal_readout_includes_signed_effects_on_other_memories(self):
        measured = _probe(self.engine, self.ids["A"], "A", 1001.0, [])
        self.assertIn("C", measured["target_indirect_score_effect_by_memory"])
        self.assertNotEqual(measured["target_indirect_score_effect_by_memory"]["C"], 0.0)

    def test_reexposure_clears_all_incoming_and_outgoing_incident_links(self):
        _neutralize_for_reexposure(self.engine, self.ids["A"])
        state = _state(self.engine, self.ids["A"])
        self.assertEqual(state["state"], "NEUTRAL")
        self.assertEqual(state["target_synaptic_links"], {})
        self.assertTrue(all(not links for links in state["incident_synaptic_links"].values()))
        self.assertEqual(state["incident_cell_links"], [])


if __name__ == "__main__":
    unittest.main()
