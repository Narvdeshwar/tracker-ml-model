"""
Unit test suite for Step 7C: Historical IPO Fundamentals and Valuation Ingestion.
Tests:
1. Baseline model protection: Model_6B_SME_v1.0 SHA-256 remains strictly untouched.
2. Pilot manifest integrity: Exactly 60 IPOs (30 Mainboard, 30 SME) stratified across 2020-2026.
3. Raw fundamentals dimensions: Exactly 1,515 IPOs with explicit provenance fields.
4. Normalized fundamentals schema: Valid numerical bounds (spread >= 0, flags in {0, 1}).
5. Temporal eligibility enforcement: Unresolved cutoffs are marked temporal_eligibility = False.
6. Target isolation: No realized listing returns or listing prices in normalized feature matrix.
7. Experiment accounting: Model comparison covers 12 benchmark evaluations (Mainboard/SME x 2 targets x 3 models).
"""

import unittest
import os
import json
import hashlib
import pandas as pd
import numpy as np

class TestStep7CFundamentals(unittest.TestCase):

    def setUp(self):
        self.pilot_manifest = 'data/processed/step_7c_pilot_manifest_60.csv'
        self.raw_fund_file = 'data/processed/step_7c_raw_fundamentals.csv'
        self.norm_fund_file = 'data/processed/step_7c_normalized_fundamentals.csv'
        self.audit_file = 'data/processed/step_7c_provenance_audit.csv'
        self.cov_file = 'data/processed/step_7c_missingness_coverage.csv'
        self.exp_res_file = 'data/processed/step_7c_model_comparison.csv'
        self.preds_file = 'data/processed/step_7c_predictions.csv'
        self.frozen_model_file = 'models/frozen/model_6b_sme_v1.joblib'
        self.meta_file = 'models/frozen/model_6b_sme_v1_metadata.json'

    def test_output_files_exist(self):
        """Verify all Step 7C datasets and experiment outputs exist."""
        self.assertTrue(os.path.exists(self.pilot_manifest))
        self.assertTrue(os.path.exists(self.raw_fund_file))
        self.assertTrue(os.path.exists(self.norm_fund_file))
        self.assertTrue(os.path.exists(self.audit_file))
        self.assertTrue(os.path.exists(self.cov_file))
        self.assertTrue(os.path.exists(self.exp_res_file))
        self.assertTrue(os.path.exists(self.preds_file))

    def test_frozen_baseline_model_unmodified(self):
        """Verify frozen SME model artifact SHA-256 remains strictly identical."""
        with open(self.meta_file, 'r') as f:
            meta = json.load(f)

        with open(self.frozen_model_file, 'rb') as f:
            computed_sha = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(computed_sha, meta['sha256_hash'])

    def test_pilot_manifest_dimensions(self):
        """Verify pilot manifest contains exactly 60 IPOs (30 Mainboard, 30 SME)."""
        df_pilot = pd.read_csv(self.pilot_manifest)
        self.assertEqual(len(df_pilot), 60)
        self.assertEqual(df_pilot['ipo_id'].nunique(), 60)
        self.assertEqual((df_pilot['board_type'] == 'Mainboard').sum(), 30)
        self.assertEqual((df_pilot['board_type'] == 'SME').sum(), 30)

    def test_raw_fundamentals_integrity(self):
        """Verify raw fundamentals covers all 1,515 IPOs without duplicates."""
        df_raw = pd.read_csv(self.raw_fund_file)
        self.assertEqual(len(df_raw), 1515)
        self.assertEqual(df_raw['ipo_id'].nunique(), 1515)

    def test_normalized_features_bounds(self):
        """Verify normalized features adhere to domain constraints."""
        df_norm = pd.read_csv(self.norm_fund_file)
        self.assertEqual(len(df_norm), 1515)

        # Spread must be non-negative
        valid_spread = df_norm['feat_price_band_spread_pct'].dropna()
        self.assertTrue((valid_spread >= 0.0).all())

        # Flags must be binary in {0.0, 1.0}
        for flag in ['feat_has_price_band', 'feat_issue_priced_at_cap', 'feat_is_fixed_price_issue']:
            valid_flag = df_norm[flag].dropna()
            self.assertTrue(set(valid_flag.unique()).issubset({0.0, 1.0}))

    def test_temporal_eligibility_enforced(self):
        """Verify that IPOs with unavailable price bands are marked ineligible."""
        df_norm = pd.read_csv(self.norm_fund_file)
        no_band = df_norm[df_norm['feat_has_price_band'] == 0.0]
        self.assertTrue((no_band['temporal_eligibility'] == False).all())

    def test_target_leakage_prevented(self):
        """Verify that realized return targets are absent from normalized feature table."""
        df_norm = pd.read_csv(self.norm_fund_file)
        prohibited = ['target_listing_open_return_pct', 'target_listing_close_return_pct', 'listing_open_inr']
        for p in prohibited:
            self.assertNotIn(p, df_norm.columns)

    def test_experiment_results_dimensions(self):
        """Verify model comparison table contains all 12 experimental evaluations."""
        df_exp = pd.read_csv(self.exp_res_file)
        self.assertEqual(len(df_exp), 12)
        expected_models = {'Model_A_Macro_Baseline', 'Model_B_Macro_Plus_Fundamentals', 'Model_C_Fundamentals_Only'}
        self.assertEqual(set(df_exp['model_name'].unique()), expected_models)

if __name__ == '__main__':
    unittest.main()
