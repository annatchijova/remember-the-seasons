"""Exact outcomes and counterfactual controls for the Exp44 rule comparison."""
import unittest
from fractions import Fraction as F

from exp44_h14_update_rule_falsifier import RULES, THRESHOLD, load_initials, run


class TestExp44(unittest.TestCase):
    def test_initial_values_are_pinned_to_exp43_artifact(self):
        initial = load_initials()
        self.assertEqual(initial, {"during_bfs": F(3, 8), "post_bfs": F(0)})

    def test_fixed_increment_reproduces_exp43_recovery_lead(self):
        rule = run()["results_by_rule"]["additive_fixed"]
        self.assertEqual(rule["first_propagation_step"], {"during_bfs": 1, "post_bfs": 4})
        self.assertEqual(rule["recovery_lead_steps"], 3)

    def test_proportional_rule_preserves_but_changes_the_lead(self):
        rule = run()["results_by_rule"]["proportional_saturating"]
        self.assertEqual(rule["first_propagation_step"], {"during_bfs": 1, "post_bfs": 3})
        self.assertEqual(rule["recovery_lead_steps"], 2)

    def test_reset_rule_erases_the_recovery_lead(self):
        rule = run()["results_by_rule"]["history_reset_additive"]
        self.assertEqual(rule["first_propagation_step"], {"during_bfs": 4, "post_bfs": 4})
        self.assertEqual(rule["recovery_lead_steps"], 0)

    def test_evidence_average_rule_does_not_recover_within_horizon(self):
        rule = run()["results_by_rule"]["evidence_average"]
        self.assertEqual(rule["first_propagation_step"], {"during_bfs": None, "post_bfs": None})
        high = rule["paired_reactivation"]["during_bfs"]
        low = rule["paired_reactivation"]["post_bfs"]
        self.assertEqual(high[1]["association_C_to_D"], "1/4")
        self.assertEqual(low[1]["association_C_to_D"], "1/16")
        self.assertLess(F(high[-1]["association_C_to_D"]), F(1, 2))

    def test_equalized_history_removes_any_branch_difference_for_every_rule(self):
        results = run()["results_by_rule"]
        for rule_name in RULES:
            equalized = results[rule_name]["equalized_history_control"]
            self.assertEqual(equalized["during_bfs"], equalized["post_bfs"])

    def test_sham_exposure_without_pairing_does_not_change_association(self):
        results = run()["results_by_rule"]
        for rule_name in RULES:
            sham = results[rule_name]["sham_no_coactivation"]
            self.assertEqual(sham["during_bfs"][0]["association_C_to_D"],
                             sham["during_bfs"][-1]["association_C_to_D"])
            self.assertEqual(sham["post_bfs"][0]["association_C_to_D"],
                             sham["post_bfs"][-1]["association_C_to_D"])
            self.assertFalse(any(row["propagation_enabled"] for row in sham["during_bfs"]))
            self.assertFalse(any(row["propagation_enabled"] for row in sham["post_bfs"]))

    def test_rule_catalog_and_reproducibility(self):
        self.assertEqual(set(run()["results_by_rule"]), set(RULES))
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
