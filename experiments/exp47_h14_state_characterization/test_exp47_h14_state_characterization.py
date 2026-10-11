from __future__ import annotations

import unittest
from fractions import Fraction as F

from exp47_h14_state_characterization import (
    State,
    all_states,
    collision_audit,
    construct_history,
    probe_schedules,
    run,
    run_schedule,
    transition,
    verify_exp46,
)


class Exp47StateCharacterizationTests(unittest.TestCase):
    def test_pinned_exp46_artifact_verifies(self):
        self.assertEqual(verify_exp46(), "10e84c100d8ca3c9c74b723b051baf0b9ff39833c96ad8b7c37d953fdae70c36")

    def test_domain_is_exhaustive_for_declared_ranges(self):
        self.assertEqual(len(all_states()), 1512)
        self.assertEqual(len(probe_schedules()), 24)

    def test_binary_flag_is_derived_from_count(self):
        self.assertFalse(State(0, F(0), True, 0).reinforced)
        self.assertTrue(State(1, F(0), True, 0).reinforced)
        self.assertTrue(State(20, F(0), True, 0).reinforced)

    def test_each_canonical_component_is_needed_in_the_enumerated_domain(self):
        audit = collision_audit(all_states())
        self.assertEqual(set(audit), {"reinforcement_count", "association", "link", "recency_age"})
        for component, result in audit.items():
            with self.subTest(component=component):
                self.assertGreater(result["groups_with_observably_different_futures"], 0)

    def test_recency_probe_separates_fresh_and_stale_updates(self):
        fresh = State(20, F(3, 8), True, 0)
        stale = State(20, F(3, 8), True, 3)
        schedule = (F(0),)
        _, fresh_out = run_schedule(fresh, schedule)
        _, stale_out = run_schedule(stale, schedule)
        self.assertNotEqual(fresh_out, stale_out)
        self.assertFalse(dict(fresh_out[0])["propagation"])
        self.assertFalse(dict(stale_out[0])["propagation"])
        self.assertTrue(dict(fresh_out[1])["propagation"])
        self.assertFalse(dict(stale_out[1])["propagation"])

    def test_distinct_histories_converged_to_same_full_state_have_same_future(self):
        same_state_from_path_a, history_a = construct_history(F(0), 3)
        same_state_from_path_b, history_b = construct_history(
            F(1, 8), 2, reinforcement_only_events=1)
        self.assertNotEqual(history_a, history_b)
        self.assertEqual(same_state_from_path_a, same_state_from_path_b)
        for schedule in probe_schedules():
            self.assertEqual(run_schedule(same_state_from_path_a, schedule),
                             run_schedule(same_state_from_path_b, schedule))

    def test_saturating_count_and_age_invariants(self):
        at_cap, observation = transition(State(20, F(0), True, 0), F(0))
        self.assertEqual(at_cap.reinforcement_count, 20)
        self.assertEqual(at_cap.recency_age, 0)
        aged, _ = transition(State(0, F(0), True, 3), F(3, 2))
        self.assertEqual(aged.recency_age, 3)
        self.assertEqual(observation["choice"], "C")

    def test_verdict_matches_collision_audit(self):
        result = run()
        self.assertTrue(result["verdict"]["sufficient_in_enumerated_model"])
        self.assertTrue(result["verdict"]["all_four_components_necessary_in_enumerated_model"])
        self.assertTrue(result["verdict"]["reinforcement_flag_is_redundant_given_count"])


if __name__ == "__main__":
    unittest.main()
