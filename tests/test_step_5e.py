"""
Test suite for Step 5E: Statistical Integrity and Predictive Readiness Audit.
"""

import unittest
import pandas as pd
import numpy as np

class TestStep5E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df_diag = pd.read_csv('data/processed/step_5e_regression_diagnostics.csv')
        cls.df_miss = pd.read_csv('data/processed/step_5e_cutoff_missingness.csv')
        cls.df_elig = pd.read_csv('data/processed/step_5e_feature_eligibility.csv')
        cls.df_split = pd.read_csv('data/processed/step_5e_temporal_split_counts.csv')
        cls.df_ipo = pd.read_csv('data/processed/ipo_features_issue_close.csv')

    def test_reproducibility_of_step_5d_counts(self):
        # 1515 records must remain exact
        self.assertEqual(len(self.df_ipo), 1515)
        # 987 verified cutoffs, 528 unresolved
        self.assertEqual((self.df_ipo['cutoff_status'] == 'verified').sum(), 987)
        self.assertEqual((self.df_ipo['cutoff_status'] == 'unresolved').sum(), 528)

    def test_scaling_odds_ratio_reconciliation(self):
        # Check that interpretable OR for +1% move in Nifty 50 is ~1.105 (not ~21,000)
        n50_pct = self.df_diag[self.df_diag['feature'] == 'nifty50_return_5s_pct'].iloc[0]
        self.assertAlmostEqual(n50_pct['interpretable_odds_ratio'], 1.105, places=2)
        # Check that Decimal raw OR matches exp(beta) within rounding tolerance
        n50_dec = self.df_diag[self.df_diag['feature'] == 'nifty50_return_5s'].iloc[0]
        self.assertAlmostEqual(np.exp(n50_dec['logistic_beta']), n50_dec['raw_odds_ratio'], delta=2.0)

    def test_no_future_features_relative_to_cutoff(self):
        verified = self.df_ipo[self.df_ipo['cutoff_status'] == 'verified'].dropna(subset=['source_observation_date', 'prediction_cutoff_date'])
        leakage = verified[pd.to_datetime(verified['source_observation_date']) > pd.to_datetime(verified['prediction_cutoff_date'])]
        self.assertTrue(leakage.empty, "Future-dated observation relative to cutoff detected!")

    def test_missing_cutoffs_remain_unresolved(self):
        unresolved = self.df_ipo[self.df_ipo['cutoff_status'] == 'unresolved']
        self.assertTrue(unresolved['prediction_cutoff_date'].isnull().all())
        self.assertTrue(unresolved['nifty50_return_5s'].isnull().all())

    def test_no_fabricated_subscription_or_gmp(self):
        # Subscription and GMP must be 100% missing in strict feature set
        sub_elig = self.df_elig[self.df_elig['feature_name'] == 'total_subscription_multiple'].iloc[0]
        self.assertFalse(sub_elig['eligible_experiment_a'])
        self.assertEqual(sub_elig['missingness_pct'], 100.0)

    def test_temporal_split_integrity(self):
        # Total counts across Train + Val + Test must equal 1515 for cohort
        splits_all = self.df_split[self.df_split['board'] == 'All']
        total_ipos = splits_all['total_cohort_ipos'].sum()
        self.assertEqual(total_ipos, 1515)
        # Verified cutoffs sum must equal 987
        verified_sum = splits_all['verified_cutoff_ipos'].sum()
        self.assertEqual(verified_sum, 987)

if __name__ == '__main__':
    unittest.main()
