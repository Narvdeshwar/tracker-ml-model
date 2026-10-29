"""
Validation test suite for Step 5A Market_Daily dataset.
"""

import unittest
import pandas as pd
import numpy as np

class TestMarketDaily(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = pd.read_csv('data/processed/market_daily.csv')

    def test_chronological_and_no_duplicates(self):
        # Dates must be strictly strictly increasing
        dates = pd.to_datetime(self.df['date'])
        self.assertTrue(dates.is_monotonic_increasing, "Market dates are not strictly monotonic increasing")
        self.assertEqual(self.df['date'].duplicated().sum(), 0, "Duplicate dates detected in Market_Daily")

    def test_positive_closes(self):
        # All closing levels must be strictly positive
        for col in ['nifty50_close', 'nifty500_close', 'india_vix_close']:
            valid = self.df[col].dropna()
            self.assertTrue((valid > 0).all(), f"Non-positive values found in {col}")

    def test_return_calculations_accuracy(self):
        # Verify 5s and 20s calculations on sample of rows
        for idx in [50, 100, 500, 1000, 1500]:
            # Nifty 50 5s return
            p_t = self.df.loc[idx, 'nifty50_close']
            p_t5 = self.df.loc[idx - 5, 'nifty50_close']
            expected_ret_5s = round(p_t / p_t5 - 1, 6)
            self.assertAlmostEqual(self.df.loc[idx, 'nifty50_return_5s'], expected_ret_5s, places=5)
            
            # Nifty 50 20s return
            p_t20 = self.df.loc[idx - 20, 'nifty50_close']
            expected_ret_20s = round(p_t / p_t20 - 1, 6)
            self.assertAlmostEqual(self.df.loc[idx, 'nifty50_return_20s'], expected_ret_20s, places=5)

            # India VIX change 5s
            v_t = self.df.loc[idx, 'india_vix_close']
            v_t5 = self.df.loc[idx - 5, 'india_vix_close']
            expected_vix_chg_5s = round(v_t - v_t5, 4)
            self.assertAlmostEqual(self.df.loc[idx, 'india_vix_change_5s'], expected_vix_chg_5s, places=4)

    def test_date_range_coverage(self):
        self.assertEqual(self.df['date'].min(), '2019-12-02')
        self.assertTrue(self.df['date'].max() >= '2026-10-25')

if __name__ == '__main__':
    unittest.main()
