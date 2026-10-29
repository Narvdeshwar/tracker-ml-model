"""
Unit test suite for Step 7D: Historical IPO Valuation, Financial Quality, and Incremental-Value Audit.
Tests:
1. Baseline model protection: Model_6B_SME_v1.0 SHA-256 remains strictly untouched.
2. Pilot manifest integrity: Exactly 60 IPOs (30 Mainboard, 30 SME) stratified across 2020-2026.
3. Raw valuation dataset dimensions: Exactly 1,515 IPOs with comprehensive provenance tracking.
4. Normalized features schema: Numeric bounds (spread >= 0, flags in {0, 1}, log_issue_price valid).
5. Target isolation: Zero realized listing outcomes or returns in normalized feature dataset.
6. Temporal eligibility enforcement: Ineligible/unverified records marked temporal_eligibility = False.
7. Model comparison accounting: Exactly 20 evaluations (2 boards x 2 targets x 5 models).
8. Identical cohort enforcement: Test sample sizes are strictly 90 for Mainboard and 58 for SME across all models.
9. Predictions integrity: Exactly 1,480 test prediction records, probabilities bounded in [0, 1].
10. Feature coefficients accounting: Learned weights stored for all evaluated model configurations.
"""

import unittest
import os
import json
import hashlib
import pandas as pd
import numpy as np

class TestStep7DFinancialQuality(unittest.TestCase):

    def setUp(self):
        self.pilot_manifest = 'data/processed/step_7c_pilot_manifest_60.csv'
        self.raw_val_file = 'data/processed/step_7d_raw_valuation_quality.csv'
        self.norm_val_file = 'data/processed/step_7d_normalized_features.csv'
        self.audit_file = 'data/processed/step_7d_provenance_timing_audit.csv'
        self.cov_file = 'data/processed/step_7d_missingness_coverage.csv'
        self.exp_res_file = 'data/processed/step_7d_model_comparison.csv'
        self.preds_file = 'data/processed/step_7d_predictions.csv'
        self.coef_file = 'data/processed/step_7d_feature_coefficients.csv'
        self.reconcile_report = 'reports/step_7d_1_reconciliation_audit.md'
        self.feat_dict_file = 'reports/step_7d_feature_dictionary.md'
        self.frozen_model_file = 'models/frozen/model_6b_sme_v1.joblib'
        self.meta_file = 'models/frozen/model_6b_sme_v1_metadata.json'

    def test_step_7d_artifacts_exist(self):
        """Verify all Step 7D datasets, audit ledgers, reports, and experiment outputs exist."""
        self.assertTrue(os.path.exists(self.raw_val_file))
        self.assertTrue(os.path.exists(self.norm_val_file))
        self.assertTrue(os.path.exists(self.audit_file))
        self.assertTrue(os.path.exists(self.cov_file))
        self.assertTrue(os.path.exists(self.exp_res_file))
        self.assertTrue(os.path.exists(self.preds_file))
        self.assertTrue(os.path.exists(self.coef_file))
        self.assertTrue(os.path.exists(self.reconcile_report))
        self.assertTrue(os.path.exists(self.feat_dict_file))

    def test_frozen_baseline_sme_model_untouched(self):
        """Verify frozen SME baseline model artifact SHA-256 remains strictly identical."""
        with open(self.meta_file, 'r') as f:
            meta = json.load(f)

        with open(self.frozen_model_file, 'rb') as f:
            computed_sha = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(computed_sha, meta['sha256_hash'])
        self.assertEqual(computed_sha, 'dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76')

    def test_pilot_manifest_60_integrity(self):
        """Verify 60-IPO pilot manifest contains 30 Mainboard and 30 SME IPOs without duplicates."""
        df_pilot = pd.read_csv(self.pilot_manifest)
        self.assertEqual(len(df_pilot), 60)
        self.assertEqual(df_pilot['ipo_id'].nunique(), 60)
        self.assertEqual((df_pilot['board_type'] == 'Mainboard').sum(), 30)
        self.assertEqual((df_pilot['board_type'] == 'SME').sum(), 30)

    def test_raw_valuation_quality_dimensions(self):
        """Verify raw valuation dataset covers all 1,515 IPOs with required provenance fields."""
        df_raw = pd.read_csv(self.raw_val_file)
        self.assertEqual(len(df_raw), 1515)
        self.assertEqual(df_raw['ipo_id'].nunique(), 1515)
        required_cols = [
            'ipo_id', 'company_name', 'market_segment', 'issue_price_inr',
            'price_band_spread_pct', 'issue_priced_at_cap', 'is_fixed_price_issue',
            'source_document', 'verification_status', 'temporal_eligibility'
        ]
        for col in required_cols:
            self.assertIn(col, df_raw.columns)

    def test_normalized_features_schema_and_bounds(self):
        """Verify normalized features adhere to numerical constraints."""
        df_norm = pd.read_csv(self.norm_val_file)
        self.assertEqual(len(df_norm), 1515)

        # Spread must be non-negative
        valid_spread = df_norm['feat_price_band_spread_pct'].dropna()
        self.assertTrue((valid_spread >= 0.0).all())

        # Flags must be binary in {0.0, 1.0}
        for flag in ['feat_has_price_band', 'feat_issue_priced_at_cap', 'feat_is_fixed_price_issue']:
            valid_flag = df_norm[flag].dropna()
            self.assertTrue(set(valid_flag.unique()).issubset({0.0, 1.0}))

        # Log price must be finite where issue price > 0
        valid_log = df_norm['log_issue_price'].dropna()
        self.assertTrue(np.isfinite(valid_log).all())

    def test_no_target_leakage(self):
        """Verify realized listing returns and outcomes are strictly absent from feature table."""
        df_norm = pd.read_csv(self.norm_val_file)
        prohibited = [
            'target_listing_open_return_pct', 'target_listing_close_return_pct',
            'listing_open_inr', 'listing_close_inr', 'listing_date'
        ]
        for p in prohibited:
            self.assertNotIn(p, df_norm.columns)

    def test_temporal_eligibility_enforcement(self):
        """Verify that IPOs lacking price band information are marked ineligible."""
        df_norm = pd.read_csv(self.norm_val_file)
        no_band = df_norm[df_norm['feat_has_price_band'] == 0.0]
        self.assertTrue((no_band['temporal_eligibility'] == False).all())

    def test_model_comparison_accounting(self):
        """Verify exactly 20 model evaluations (2 boards x 2 targets x 5 models)."""
        df_exp = pd.read_csv(self.exp_res_file)
        self.assertEqual(len(df_exp), 20)
        expected_models = {
            'Model_A_Macro_Baseline',
            'Model_B_Macro_Plus_Structure',
            'Model_C_Structure_Only',
            'Model_D_Macro_Plus_Scale',
            'Model_E_Unified_Enriched'
        }
        self.assertEqual(set(df_exp['model_name'].unique()), expected_models)
        self.assertEqual(set(df_exp['board_type'].unique()), {'Mainboard', 'SME'})
        self.assertEqual(set(df_exp['target'].unique()), {'Positive_Opening_Return', 'Severe_Loss_Risk'})

    def test_identical_cohort_enforcement(self):
        """Verify identical test sample sizes (90 for Mainboard, 58 for SME) across all models."""
        df_exp = pd.read_csv(self.exp_res_file)
        mb_runs = df_exp[df_exp['board_type'] == 'Mainboard']
        self.assertTrue((mb_runs['test_sample_size'] == 90).all())

        sme_runs = df_exp[df_exp['board_type'] == 'SME']
        self.assertTrue((sme_runs['test_sample_size'] == 58).all())

    def test_predictions_integrity(self):
        """Verify predictions file has exactly 1,480 rows and valid probability bounds."""
        df_preds = pd.read_csv(self.preds_file)
        # 90 MB test * 2 targets * 5 models = 900
        # 58 SME test * 2 targets * 5 models = 580
        # Total = 1,480
        self.assertEqual(len(df_preds), 1480)
        self.assertTrue((df_preds['predicted_probability'] >= 0.0).all())
        self.assertTrue((df_preds['predicted_probability'] <= 1.0).all())

    def test_feature_coefficients_accounting(self):
        """Verify feature coefficients are logged for all model evaluations."""
        df_coef = pd.read_csv(self.coef_file)
        self.assertGreater(len(df_coef), 0)
        self.assertEqual(set(df_coef['board_type'].unique()), {'Mainboard', 'SME'})
        self.assertEqual(set(df_coef['target'].unique()), {'Positive_Opening_Return', 'Severe_Loss_Risk'})

if __name__ == '__main__':
    unittest.main()
