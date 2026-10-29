"""
Test suite for Step 5C: Subscription, GMP, Sentiment, and Experiment Separation.
"""

import unittest
import pandas as pd
import numpy as np

class TestStep5C(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df_sent = pd.read_csv('data/processed/ipo_sentiment_features.csv')
        cls.df_exp_a = pd.read_csv('data/processed/ipo_features_issue_close.csv')
        cls.df_exp_b = pd.read_csv('data/processed/ipo_features_post_close.csv')
        cls.df_ipo = pd.read_csv('data/processed/ipo_market_features.csv')

    def test_record_preservation(self):
        self.assertEqual(len(self.df_sent), 1515)
        self.assertEqual(len(self.df_exp_a), 1515)
        self.assertEqual(len(self.df_exp_b), 1515)
        self.assertEqual(self.df_exp_a['ipo_id'].nunique(), 1515)

    def test_sentiment_chronological_anti_leakage(self):
        # For all verified records with sentiment, make sure no sentiment used outcomes after cutoff
        candidates = self.df_ipo.dropna(subset=['listing_date', 'target_listing_open_return_pct']).set_index('ipo_id')
        
        verified_sent = self.df_sent[self.df_sent['recent5_mean_listing_open_return_pct'].notnull()]
        for _, row in verified_sent.head(50).iterrows():
            cutoff_dt = pd.to_datetime(row['prediction_cutoff_date'])
            # Verify eligible count
            eligible = candidates[pd.to_datetime(candidates['listing_date']) < cutoff_dt]
            self.assertGreaterEqual(len(eligible), 5)
            # Recompute mean and assert equality
            expected_mean = round(float(eligible.tail(5)['target_listing_open_return_pct'].mean()), 2)
            self.assertAlmostEqual(row['recent5_mean_listing_open_return_pct'], expected_mean, places=2)

    def test_unresolved_cutoff_sentiment_missing(self):
        unresolved = self.df_sent[self.df_sent['cutoff_status'] == 'unresolved']
        self.assertTrue(unresolved['recent5_mean_listing_open_return_pct'].isnull().all())

    def test_experiment_segregation(self):
        # Experiment A and B must be distinct
        self.assertEqual(self.df_exp_a['experiment_name'].iloc[0], 'Experiment_A_Issue_Close')
        self.assertEqual(self.df_exp_b['experiment_name'].iloc[0], 'Experiment_B_Post_Close')

    def test_no_zero_imputation_for_missing_gmp_sub(self):
        # Critical test: unverified / missing subscription/GMP must NOT be silently replaced with 0
        self.assertTrue(self.df_exp_a['total_subscription_multiple'].isnull().all())
        self.assertTrue(self.df_exp_a['gmp_amount_inr'].isnull().all())

if __name__ == '__main__':
    unittest.main()
