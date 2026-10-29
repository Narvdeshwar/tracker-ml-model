"""
Test suite for Step 5B: IPO Market Features and Anti-Leakage Validation.
"""

import unittest
import pandas as pd
import numpy as np

class TestIPOMarketFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = pd.read_csv('data/processed/ipo_market_features.csv')
        cls.df_market = pd.read_csv('data/processed/market_daily.csv')

    def test_total_records_preserved(self):
        # 1515 records must be completely preserved, no dropped rows
        self.assertEqual(len(self.df), 1515, f"Expected 1515 rows, found {len(self.df)}")
        # Unique IPO identifier
        self.assertEqual(self.df['ipo_id'].nunique(), 1515, "ipo_id is not unique in the output")

    def test_cutoff_policy_and_unresolved_handling(self):
        # Check unresolved cutoffs
        unresolved = self.df[self.df['cutoff_status'] == 'unresolved']
        self.assertEqual(len(unresolved), 528, f"Expected 528 unresolved cutoff records, got {len(unresolved)}")
        
        # All unresolved must have None/NaN prediction_cutoff_date and features
        self.assertTrue(unresolved['prediction_cutoff_date'].isnull().all(), "Unresolved cutoff has non-null cutoff date!")
        self.assertTrue(unresolved['nifty50_return_5s'].isnull().all(), "Unresolved cutoff has non-null market features!")

    def test_anti_leakage_backward_only(self):
        # Crucial check: For all verified records, source_observation_date <= prediction_cutoff_date
        verified = self.df[self.df['cutoff_status'] == 'verified'].dropna(subset=['source_observation_date', 'prediction_cutoff_date'])
        
        obs_dates = pd.to_datetime(verified['source_observation_date'])
        cutoff_dates = pd.to_datetime(verified['prediction_cutoff_date'])
        
        leakage = verified[obs_dates > cutoff_dates]
        self.assertTrue(leakage.empty, f"LEAKAGE DETECTED: {len(leakage)} records have observation date > cutoff date!")

    def test_market_close_feature_match(self):
        # Check that joined features match exactly the market_daily values for that observation date
        verified = self.df[self.df['cutoff_status'] == 'verified'].dropna(subset=['source_observation_date']).head(20)
        market_map = self.df_market.set_index('date')
        
        for _, row in verified.iterrows():
            obs_dt = row['source_observation_date']
            expected_n50_ret5s = market_map.loc[obs_dt, 'nifty50_return_5s']
            if pd.notnull(expected_n50_ret5s):
                self.assertAlmostEqual(row['nifty50_return_5s'], expected_n50_ret5s, places=5)

    def test_segment_separation(self):
        # Verify both Mainboard and SME rows are present
        boards = self.df['board_type'].value_counts()
        self.assertIn('Mainboard', boards)
        self.assertIn('SME', boards)
        self.assertEqual(boards['Mainboard'], 463)
        self.assertEqual(boards['SME'], 1052)

if __name__ == '__main__':
    unittest.main()
