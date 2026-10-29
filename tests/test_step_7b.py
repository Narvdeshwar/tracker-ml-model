"""
Unit test suite for Step 7B: Historical IPO Subscription Data Ingestion & Snapshot Framework.
Covers:
1. Invariant: Baseline model artifact (Model_6B_SME_v1.0) remains frozen and untouched.
2. Invariant: Zero imputation - missing subscription values must remain NaN, never zero.
3. Queue accounting integrity: 499 unresolved + 22 conflict = 521 queued records in Step 7A queue.
4. Subscription snapshots integrity: Exactly 4 snapshots per IPO (6,060 snapshot rows across 1,515 IPOs).
5. Look-ahead leakage prevention: TIMING_UNVERIFIED flag applied when cutoff or timing cannot be proven.
6. Target/Outcome separation: No listing prices or returns present in subscription features.
7. Category isolation: Schema separates QIB, NII, Retail, and Total cleanly.
"""

import unittest
import os
import json
import hashlib
import pandas as pd
import numpy as np

class TestStep7BSubscriptionPipeline(unittest.TestCase):

    def setUp(self):
        self.obs_file = 'data/processed/ipo_subscription_observations.csv'
        self.feat_file = 'data/processed/ipo_subscription_features.csv'
        self.cov_file = 'data/processed/step_7b_subscription_coverage.csv'
        self.conflicts_file = 'data/processed/step_7b_subscription_conflicts.csv'
        self.unres_file = 'data/processed/step_7b_subscription_unresolved.csv'
        self.cutoff_file = 'data/processed/ipo_cutoff_recovery.csv'
        self.frozen_model_file = 'models/frozen/model_6b_sme_v1.joblib'
        self.meta_file = 'models/frozen/model_6b_sme_v1_metadata.json'

    def test_datasets_exist(self):
        """Verify all Step 7B output files exist."""
        self.assertTrue(os.path.exists(self.obs_file))
        self.assertTrue(os.path.exists(self.feat_file))
        self.assertTrue(os.path.exists(self.cov_file))
        self.assertTrue(os.path.exists(self.conflicts_file))
        self.assertTrue(os.path.exists(self.unres_file))

    def test_frozen_baseline_model_unmodified(self):
        """Verify frozen SME model artifact SHA-256 is strictly preserved."""
        with open(self.meta_file, 'r') as f:
            meta = json.load(f)

        with open(self.frozen_model_file, 'rb') as f:
            computed_sha = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(computed_sha, meta['sha256_hash'])
        self.assertEqual(meta['model_version'], 'Model_6B_SME_v1.0')

    def test_queue_accounting_resolution(self):
        """Verify accounting: 499 UNRESOLVED + 22 CONFLICT_REQUIRES_REVIEW = 521 in cutoff recovery queue."""
        df_cutoff = pd.read_csv(self.cutoff_file)
        self.assertEqual(len(df_cutoff), 1515)
        self.assertEqual((df_cutoff['verification_status'] == 'UNRESOLVED').sum(), 499)
        self.assertEqual((df_cutoff['verification_status'] == 'CONFLICT_REQUIRES_REVIEW').sum(), 22)
        self.assertEqual((df_cutoff['verification_status'] == 'VERIFIED_PRIMARY_SOURCE').sum(), 994)

    def test_snapshot_features_dimensions(self):
        """Verify feature snapshot file has exactly 4 snapshots per IPO (6,060 total)."""
        df_feats = pd.read_csv(self.feat_file)
        self.assertEqual(len(df_feats), 1515 * 4)
        self.assertEqual(df_feats['ipo_id'].nunique(), 1515)
        allowed_snaps = {'DAY1_SNAPSHOT', 'DAY2_SNAPSHOT', 'DAY3_SNAPSHOT', 'FINAL_SNAPSHOT'}
        self.assertEqual(set(df_feats['snapshot_type'].unique()), allowed_snaps)

    def test_missing_values_are_nan_not_zero(self):
        """Verify missing subscription multiples remain NaN and are never zero-filled."""
        df_feats = pd.read_csv(self.feat_file)
        for col in ['qib_subscription_multiple', 'nii_subscription_multiple', 'retail_subscription_multiple', 'total_subscription_multiple']:
            # Non-null values must not be blindly imputed as 0.0
            non_null = df_feats[df_feats[col].notna()]
            if not non_null.empty:
                # If any exist, ensure they are positive multiples
                self.assertTrue((non_null[col] > 0).all())

    def test_timing_unverified_flag_enforced(self):
        """Verify unverified cutoffs have TIMING_UNVERIFIED flag in feature snapshots."""
        df_feats = pd.read_csv(self.feat_file)
        df_cutoff = pd.read_csv(self.cutoff_file)
        unres_ids = set(df_cutoff[df_cutoff['verification_status'] != 'VERIFIED_PRIMARY_SOURCE']['ipo_id'])

        unres_feats = df_feats[df_feats['ipo_id'].isin(unres_ids)]
        self.assertTrue((unres_feats['timing_validity_status'] == 'TIMING_UNVERIFIED').all())

    def test_no_listing_outcomes_in_subscription_features(self):
        """Verify zero leakage: listing open/close returns are strictly prohibited in subscription features."""
        df_feats = pd.read_csv(self.feat_file)
        prohibited = ['target_listing_open_return_pct', 'target_listing_close_return_pct', 'listing_open_inr', 'listing_close_inr']
        for col in prohibited:
            self.assertNotIn(col, df_feats.columns)

    def test_category_isolation(self):
        """Verify QIB, NII, Retail, and Total categories are segregated columns."""
        df_feats = pd.read_csv(self.feat_file)
        required_cols = [
            'qib_subscription_multiple', 'nii_subscription_multiple',
            'retail_subscription_multiple', 'total_subscription_multiple'
        ]
        for col in required_cols:
            self.assertIn(col, df_feats.columns)

if __name__ == '__main__':
    unittest.main()
