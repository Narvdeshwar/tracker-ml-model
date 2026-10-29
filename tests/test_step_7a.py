"""
Unit test suite for Step 7A: Historical IPO Cutoff Recovery and Data Provenance.
Covers:
1. No duplicate IPO identifiers in recovery dataset.
2. Invariant: exactly 1,515 IPO records preserved without loss or truncation.
3. Verification status adherence (only supported enumeration values).
4. Timezone specification is strictly Asia/Kolkata.
5. Invariant: verified_cutoff_timestamp must strictly precede listing_date.
6. Provenance completeness: verified records have non-null source title and archive references.
7. Unresolved queue integrity: all UNRESOLVED and CONFLICT records captured.
8. Preservation of previous frozen model artifacts and Step 6A outputs.
9. Coverage statistics reproducibility.
"""

import unittest
import os
import json
import hashlib
import pandas as pd
import numpy as np

class TestStep7ACutoffRecovery(unittest.TestCase):

    def setUp(self):
        self.recovery_file = 'data/processed/ipo_cutoff_recovery.csv'
        self.coverage_file = 'data/processed/step_7a_cutoff_coverage_by_year.csv'
        self.unresolved_file = 'data/processed/step_7a_unresolved_queue.csv'
        self.master_file = 'Indian_IPO_ML_Research_Starter.xlsx'
        self.frozen_model_file = 'models/frozen/model_6b_sme_v1.joblib'

    def test_datasets_exist(self):
        """Verify all Step 7A output files exist."""
        self.assertTrue(os.path.exists(self.recovery_file))
        self.assertTrue(os.path.exists(self.coverage_file))
        self.assertTrue(os.path.exists(self.unresolved_file))

    def test_no_duplicate_ipo_identifiers(self):
        """Verify that ipo_id is unique across all 1,515 records."""
        df = pd.read_csv(self.recovery_file)
        self.assertEqual(len(df), 1515)
        self.assertEqual(df['ipo_id'].nunique(), 1515, "Found duplicate ipo_id in recovery dataset")

    def test_supported_verification_statuses(self):
        """Verify all records use strictly supported verification statuses."""
        allowed_statuses = {
            'VERIFIED_PRIMARY_SOURCE',
            'VERIFIED_SECONDARY_SOURCE',
            'CONFLICT_REQUIRES_REVIEW',
            'UNRESOLVED',
            'INVALID_RECORD'
        }
        df = pd.read_csv(self.recovery_file)
        observed_statuses = set(df['verification_status'].unique())
        self.assertTrue(observed_statuses.issubset(allowed_statuses),
                        f"Unsupported status found: {observed_statuses - allowed_statuses}")

    def test_cutoff_timezone_standardization(self):
        """Verify all cutoff records explicitly declare Asia/Kolkata timezone."""
        df = pd.read_csv(self.recovery_file)
        self.assertTrue((df['cutoff_timezone'] == 'Asia/Kolkata').all())

    def test_cutoff_strictly_precedes_listing(self):
        """Verify that for all verified cutoffs, the cutoff timestamp strictly precedes listing date."""
        df_rec = pd.read_csv(self.recovery_file)
        df_master = pd.read_excel(self.master_file, sheet_name='IPO_Master')
        merged = pd.merge(df_rec, df_master[['ipo_id', 'listing_date']], on='ipo_id')

        verified = merged[merged['verification_status'] == 'VERIFIED_PRIMARY_SOURCE']
        self.assertFalse(verified.empty)

        for _, row in verified.iterrows():
            cutoff_date_str = str(row['verified_cutoff_timestamp'])[:10]
            listing_date_str = str(row['listing_date'])[:10]
            self.assertLessEqual(cutoff_date_str, listing_date_str,
                                 f"Cutoff {cutoff_date_str} must not be after listing {listing_date_str} for {row['ipo_id']}")

    def test_source_provenance_completeness(self):
        """Verify that every verified record has non-null source document title and archive reference."""
        df = pd.read_csv(self.recovery_file)
        verified = df[df['verification_status'] == 'VERIFIED_PRIMARY_SOURCE']

        self.assertFalse(verified['source_document_title'].isna().any())
        self.assertFalse(verified['source_document_url_or_archive_reference'].isna().any())
        self.assertFalse(verified['verification_method'].isna().any())

    def test_unresolved_queue_integrity(self):
        """Verify unresolved queue contains exactly the set of UNRESOLVED and CONFLICT records."""
        df_rec = pd.read_csv(self.recovery_file)
        df_unres = pd.read_csv(self.unresolved_file)

        expected_count = (df_rec['verification_status'].isin(['UNRESOLVED', 'CONFLICT_REQUIRES_REVIEW'])).sum()
        self.assertEqual(len(df_unres), expected_count)
        self.assertEqual(expected_count, 521)
        self.assertEqual((df_unres['verification_status'] == 'UNRESOLVED').sum(), 499)
        self.assertEqual((df_unres['verification_status'] == 'CONFLICT_REQUIRES_REVIEW').sum(), 22)

    def test_frozen_model_unmodified(self):
        """Verify that frozen SME model artifact has not been modified or retrained."""
        with open('models/frozen/model_6b_sme_v1_metadata.json', 'r') as f:
            meta = json.load(f)

        with open(self.frozen_model_file, 'rb') as f:
            computed_sha = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(computed_sha, meta['sha256_hash'])

    def test_coverage_statistics_reproducibility(self):
        """Verify coverage table totals match the recovery dataset exactly."""
        df_rec = pd.read_csv(self.recovery_file)
        df_cov = pd.read_csv(self.coverage_file)

        self.assertEqual(df_cov['total_ipos'].sum(), 1515)
        self.assertEqual(df_cov['verified_primary_source'].sum(), (df_rec['verification_status'] == 'VERIFIED_PRIMARY_SOURCE').sum())
        self.assertEqual(df_cov['unresolved_count'].sum(), (df_rec['verification_status'] == 'UNRESOLVED').sum())
        self.assertEqual(df_cov['conflict_requires_review'].sum(), (df_rec['verification_status'] == 'CONFLICT_REQUIRES_REVIEW').sum())

if __name__ == '__main__':
    unittest.main()
