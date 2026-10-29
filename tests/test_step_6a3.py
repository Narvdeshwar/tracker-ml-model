"""
Test suite for Step 6A.3: SME Ranking Robustness, Distribution Shift Audit,
and Prospective Shadow Evaluation Design.
"""

import unittest
import pandas as pd
import numpy as np

class TestStep6A3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df_audit = pd.read_csv('data/processed/step_6a3_bootstrap_audit.csv')
        cls.df_tier = pd.read_csv('data/processed/step_6a3_tier_uncertainty.csv')
        cls.df_shift = pd.read_csv('data/processed/step_6a3_cohort_comparison.csv')
        cls.df_schema = pd.read_csv('data/processed/step_6a3_prospective_log_schema.csv')

    def test_bootstrap_audit_consistency(self):
        # PR-AUC lift CI must strictly exclude 0 under paired resampling
        pr_row = self.df_audit[self.df_audit['metric'].str.contains('PR-AUC')].iloc[0]
        self.assertTrue(pr_row['zero_excluded_in_ci'])
        self.assertGreater(pr_row['bootstrap_ci_95_low'], 0.0)

    def test_tier_uncertainty_wilson_bounds(self):
        # High prob tier (Tier 3) Wilson interval must contain the 75% point estimate
        t3 = self.df_tier[self.df_tier['rank_tier'] == 'Tier_3_High_Prob'].iloc[0]
        self.assertEqual(t3['empirical_win_rate_pct'], 75.0)
        self.assertLess(t3['wilson_ci_95_low_pct'], 75.0)
        self.assertGreater(t3['wilson_ci_95_high_pct'], 75.0)
        # Verify wide interval due to N=20: low bound should be ~53%, high ~89%
        self.assertAlmostEqual(t3['wilson_ci_95_low_pct'], 53.13, delta=1.0)
        self.assertAlmostEqual(t3['wilson_ci_95_high_pct'], 88.81, delta=1.0)

    def test_distribution_shift_data_reproducibility(self):
        # Total SME verified IPOs across cohorts must sum to 542
        sme_shift = self.df_shift[self.df_shift['segment'] == 'SME']
        self.assertEqual(sme_shift['total_verified_ipos'].sum(), 542)
        # SME Train PosOpen% must be 83.42%, Test 2026 PosOpen% must be 58.62%
        self.assertAlmostEqual(sme_shift[sme_shift['cohort'] == 'Train_2020_2024']['positive_open_rate_pct'].iloc[0], 83.42, places=1)
        self.assertAlmostEqual(sme_shift[sme_shift['cohort'] == 'Test_2026']['positive_open_rate_pct'].iloc[0], 58.62, places=1)

    def test_prospective_schema_integrity(self):
        fields = self.df_schema['field_name'].tolist()
        self.assertIn('prediction_id', fields)
        self.assertIn('ipo_id', fields)
        self.assertIn('prediction_timestamp_ist', fields)
        self.assertIn('actual_listing_open_inr', fields)
        self.assertIn('status', fields)

if __name__ == '__main__':
    unittest.main()
