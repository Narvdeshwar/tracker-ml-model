"""
Unit test suite for Step 7B.1: Actual Historical Subscription Data Ingestion & Source Feasibility.
Tests:
1. Invariant: Model_6B_SME_v1.0 SHA-256 remains strictly identical (no model retraining).
2. Pilot sample integrity: Exactly 30 stratified IPOs across 2020-2026.
3. Ingestion audit dimensions: 120 audit evaluations (30 IPOs * 4 snapshots).
4. Temporal exclusion enforcement: FINAL_SNAPSHOT is marked STRICTLY_BANNED_FROM_PRE_LISTING_PREDICTION.
5. Intraday snapshot absence detection: DAY1, DAY2, DAY3 marked as unavailable in static archives.
6. Zero imputation: Unobserved subscription multiples remain NaN.
7. Unresolved queue accounting: Exactly 1,515 IPOs tracked with appropriate blocker status.
"""

import unittest
import os
import json
import hashlib
import pandas as pd
import numpy as np

class TestStep7B1IngestionAudit(unittest.TestCase):

    def setUp(self):
        self.pilot_sample_file = 'data/processed/step_7b_1_pilot_sample_30.csv'
        self.ingestion_audit_file = 'data/processed/step_7b_1_ingestion_audit.csv'
        self.source_cov_file = 'data/processed/step_7b_1_source_coverage.csv'
        self.unres_queue_file = 'data/processed/step_7b_1_unresolved_queue.csv'
        self.feasibility_report = 'reports/step_7b_1_source_feasibility.md'
        self.frozen_model_file = 'models/frozen/model_6b_sme_v1.joblib'
        self.meta_file = 'models/frozen/model_6b_sme_v1_metadata.json'

    def test_output_files_exist(self):
        """Verify all Step 7B.1 output datasets and reports exist."""
        self.assertTrue(os.path.exists(self.pilot_sample_file))
        self.assertTrue(os.path.exists(self.ingestion_audit_file))
        self.assertTrue(os.path.exists(self.source_cov_file))
        self.assertTrue(os.path.exists(self.unres_queue_file))
        self.assertTrue(os.path.exists(self.feasibility_report))

    def test_frozen_baseline_model_unmodified(self):
        """Verify frozen SME model artifact SHA-256 remains strictly untouched."""
        with open(self.meta_file, 'r') as f:
            meta = json.load(f)

        with open(self.frozen_model_file, 'rb') as f:
            computed_sha = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(computed_sha, meta['sha256_hash'])

    def test_pilot_sample_stratification(self):
        """Verify pilot sample has 30 IPOs representing both Mainboard and SME across multiple years."""
        df_pilot = pd.read_csv(self.pilot_sample_file)
        self.assertEqual(len(df_pilot), 30)
        self.assertEqual(df_pilot['ipo_id'].nunique(), 30)
        self.assertTrue('Mainboard' in df_pilot['board_type'].values)
        self.assertTrue('SME' in df_pilot['board_type'].values)
        years = df_pilot['listing_year'].unique()
        self.assertTrue(len(years) >= 6)

    def test_ingestion_audit_dimensions_and_temporal_invariants(self):
        """Verify ingestion audit evaluates 120 rows and enforces strict temporal restrictions."""
        df_audit = pd.read_csv(self.ingestion_audit_file)
        self.assertEqual(len(df_audit), 120)

        # Check Final Snapshot restriction
        final_snaps = df_audit[df_audit['snapshot_type'] == 'FINAL_SNAPSHOT']
        self.assertEqual(len(final_snaps), 30)
        self.assertTrue((final_snaps['temporal_validity'] == 'STRICTLY_BANNED_FROM_PRE_LISTING_PREDICTION').all())

        # Check Intraday Snapshots status
        intraday_snaps = df_audit[df_audit['snapshot_type'].isin(['DAY1_SNAPSHOT', 'DAY2_SNAPSHOT', 'DAY3_SNAPSHOT'])]
        self.assertEqual(len(intraday_snaps), 90)
        self.assertTrue((intraday_snaps['temporal_validity'] == 'EXCLUDED_FROM_EVALUATION').all())

    def test_zero_imputation_strictly_prohibited(self):
        """Verify that reported multiples for unavailable observations remain NaN, never zero."""
        df_audit = pd.read_csv(self.ingestion_audit_file)
        unavail = df_audit[df_audit['observation_found'] == False]
        self.assertTrue(unavail['reported_multiple'].isna().all())

    def test_unresolved_queue_complete(self):
        """Verify that all 1,515 IPOs are accounted for in the subscription unresolved queue."""
        df_unres = pd.read_csv(self.unres_queue_file)
        self.assertEqual(len(df_unres), 1515)
        self.assertEqual(df_unres['ipo_id'].nunique(), 1515)

if __name__ == '__main__':
    unittest.main()
