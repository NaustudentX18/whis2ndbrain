"""Pure-function tests for the latency harness (Lane C2 / WB-052 prep).

No model, no subprocess: statistics and budget-verdict logic only, so CI
stays green without weights. The real-model harness itself is manual-run
(synthetic silence; real-voice measurement waits on WB-004 consent).
"""

from __future__ import annotations

import unittest

from scripts.latency_harness import budget_verdict, percentile, summarise


class PercentileTests(unittest.TestCase):
    def test_percentile_matches_linear_interpolation(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        self.assertEqual(percentile(values, 50), 5.5)
        self.assertAlmostEqual(percentile(values, 95), 9.55)
        self.assertEqual(percentile(values, 0), 1.0)
        self.assertEqual(percentile(values, 100), 10.0)

    def test_single_value_and_unsorted_input(self):
        self.assertEqual(percentile([7.0], 95), 7.0)
        self.assertEqual(percentile([3.0, 1.0, 2.0], 50), 2.0)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            percentile([], 50)


class SummariseTests(unittest.TestCase):
    def test_summary_reports_sample_size_and_spread(self):
        stats = summarise([2.0, 4.0, 6.0, 8.0])
        self.assertEqual(stats["n"], 4)
        self.assertEqual(stats["min_s"], 2.0)
        self.assertEqual(stats["max_s"], 8.0)
        self.assertEqual(stats["p50_s"], 5.0)
        self.assertEqual(stats["mean_s"], 5.0)
        self.assertGreaterEqual(stats["p95_s"], stats["p50_s"])


class BudgetVerdictTests(unittest.TestCase):
    def test_placeholder_budgets_never_fail(self):
        budgets = {"status": "placeholder-until-BP2", "transcribe_p95_s_for_30s_audio": 0.001}
        stats = {"p95_s": 999.0}
        verdict, budget = budget_verdict(stats, budgets, 30)
        self.assertEqual(verdict, "within (placeholder)")
        self.assertEqual(budget, 0.001)

    def test_real_budgets_pass_and_fail(self):
        budgets = {"status": "owner-agreed", "transcribe_p95_s_for_5s_audio": 10.0}
        self.assertEqual(budget_verdict({"p95_s": 9.9}, budgets, 5)[0], "within")
        self.assertEqual(budget_verdict({"p95_s": 10.1}, budgets, 5)[0], "exceeded")

    def test_missing_budget_key_is_reported_not_failed(self):
        verdict, budget = budget_verdict({"p95_s": 1.0}, {}, 15)
        self.assertEqual(verdict, "no-budget")
        self.assertIsNone(budget)


if __name__ == "__main__":
    unittest.main()
