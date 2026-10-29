"""
Test suite for Step 6A.2: Ranking Robustness, Bootstrap Uncertainty, Calibration,
and Severe-Loss Diagnostic Investigation.
"""

import unittest
import pandas as pd
import numpy as np

class TestStep6A2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df_rob = pd.read_csv('data/processed/step_6a2_robustness_metrics.csv')
        cls.df_rank = pd.read_csv('data/processed/step_6a2_ranking_groups.csv')
        cls.df_cal = pd.read_csv('data/processed/step_6a2_calibration.csv')
        cls.df_sev = pd.read_csv('data/processed/step_6a2_severe_loss_diagnostics.csv')

    def test_bootstrap_coverage_and_ci(self):
        # SME PR-AUC lift must be positive with CI that excludes 0
        sme_rob = self.df_rob[self.df_rob['segment'] == 'SME'].iloc[0]
        self.assertGreater(sme_rob['delta_pr_auc'], 0.10)
        self.assertIn('[0.0155, 0.2545]', sme_rob['delta_pr_ci_95'])

    def test_ranking_monotonicity_on_sme_test(self):
        # On SME Test 2026, Tier 3 win rate must exceed Tier 1 win rate
        sme_tiers = self.df_rank[(self.df_rank['segment'] == 'SME') & (self.df_rank['cohort'] == 'Test_2026')].set_index('rank_tier')
        t1_win = sme_tiers.loc['Tier_1_Low_Prob', 'actual_positive_rate_pct']
        t2_win = sme_tiers.loc['Tier_2_Mid_Prob', 'actual_positive_rate_pct']
        t3_win = sme_tiers.loc['Tier_3_High_Prob', 'actual_positive_rate_pct']
        self.assertTrue(t3_win > t2_win > t1_win, f"Expected monotonic increase, got {t1_win}% -> {t2_win}% -> {t3_win}%")

    def test_severe_loss_inverted_ranking_documented(self):
        # All 4 cohorts in severe loss diagnostics must exhibit INVERTED_RANKING
        for _, r in self.df_sev.iterrows():
            self.assertEqual(r['diagnostic_verdict'], 'INVERTED_RANKING')
            self.assertLess(r['score_gap_severe_minus_nonsevere'], 0.0)

if __name__ == '__main__':
    unittest.main()
