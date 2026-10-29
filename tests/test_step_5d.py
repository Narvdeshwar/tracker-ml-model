"""
Test suite for Step 5D: Statistical Calculations, Targets, and Downside Integrity.
"""

import unittest
import pandas as pd
import numpy as np

class TestStep5D(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df_base = pd.read_csv('data/processed/step_5d_baseline_statistics.csv')
        cls.df_downside = pd.read_csv('data/processed/step_5d_downside_risk.csv')
        cls.df_market = pd.read_csv('data/processed/step_5d_market_analysis.csv')
        cls.df_cov = pd.read_csv('data/processed/step_5d_feature_coverage.csv')
        cls.df_ipo = pd.read_csv('data/processed/ipo_features_issue_close.csv')

    def test_total_sample_integrity(self):
        # Overall Listing Close N must equal 1515
        overall_close = self.df_base[self.df_base['group'] == 'Overall_Listing_Close'].iloc[0]
        self.assertEqual(overall_close['n_obs'], 1515)
        # Sum of positive, negative, and flat must equal total n_obs
        self.assertEqual(overall_close['positive_count'] + overall_close['negative_count'] + overall_close['flat_count'], 1515)

    def test_target_return_precision(self):
        # Listing Open Return has 3 missing in SME
        overall_open = self.df_base[self.df_base['group'] == 'Overall_Listing_Open'].iloc[0]
        self.assertEqual(overall_open['n_obs'], 1512)

    def test_downside_consistency(self):
        # Probability of loss <= -20% must be <= probability of loss <= -10% <= probability of loss < 0%
        for _, r in self.df_downside.iterrows():
            self.assertGreaterEqual(r['prob_loss_pct'], r['prob_loss_gt_10pct'])
            self.assertGreaterEqual(r['prob_loss_gt_10pct'], r['prob_loss_gt_20pct'])

    def test_feature_coverage_schema(self):
        self.assertIn('ipo_id', self.df_cov['feature'].tolist())
        self.assertIn('total_subscription_multiple', self.df_cov['feature'].tolist())
        self.assertIn('gmp_amount_inr', self.df_cov['feature'].tolist())

if __name__ == '__main__':
    unittest.main()
