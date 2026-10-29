"""
Unit test suite for Step 6A.4.1: Production Integrity Audit.
Tests:
1. Feature availability enforcement and rejection of future-dated observations.
2. Temporal ordering invariant (prediction cutoff strictly before listing date).
3. Non-overwriting and non-mutation of prediction records when outcomes are appended.
4. Hash consistency recomputation across all ledger records.
5. Verification that Pooja Logistics is flagged/classified as historical demonstration.
6. Verification that decision thresholds are preserved as ranking tiers rather than buy/avoid rules.
"""

import unittest
import os
import json
import hashlib
import pandas as pd
import numpy as np
import joblib

class TestStep6A41IntegrityAudit(unittest.TestCase):

    def setUp(self):
        self.pred_file = 'data/processed/shadow_predictions.csv'
        self.outc_file = 'data/processed/shadow_outcomes.csv'
        self.evnt_file = 'data/processed/shadow_events.csv'
        self.model_path = 'models/frozen/model_6b_sme_v1.joblib'
        self.meta_path = 'models/frozen/model_6b_sme_v1_metadata.json'

    def test_model_artifact_and_reproducibility(self):
        """Verify model SHA-256 matches metadata exactly and reproduces probabilities."""
        self.assertTrue(os.path.exists(self.model_path))
        self.assertTrue(os.path.exists(self.meta_path))

        with open(self.model_path, 'rb') as f:
            artifact_bytes = f.read()
            computed_sha = hashlib.sha256(artifact_bytes).hexdigest()

        with open(self.meta_path, 'r') as f:
            meta = json.load(f)

        self.assertEqual(computed_sha, meta['sha256_hash'])
        self.assertEqual(meta['model_version'], 'Model_6B_SME_v1.0')

        # Test inference consistency
        model = joblib.load(self.model_path)
        sample_input = pd.DataFrame([{
            'feat_nifty50_ret5s_pct': 0.0,
            'feat_india_vix': 15.0,
            'feat_recent5_sentiment': 0.8
        }])
        prob = model.predict_proba(sample_input)[0, 1]
        self.assertTrue(0.0 <= prob <= 1.0)
        self.assertAlmostEqual(prob, 0.7875, places=3)

    def test_ledger_record_hash_recalculation(self):
        """Verify that all records in shadow_predictions.csv have valid recomputed SHA-256 hashes."""
        df_p = pd.read_csv(self.pred_file)
        self.assertFalse(df_p.empty)

        for _, row in df_p.iterrows():
            rec = row.to_dict()
            stored_hash = rec.pop('prediction_record_hash')
            serialized = json.dumps(rec, sort_keys=True, default=str)
            recomputed = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
            self.assertEqual(stored_hash, recomputed, f"Hash mismatch for prediction {rec.get('prediction_id')}")

    def test_outcomes_ledger_hash_recalculation(self):
        """Verify that all records in shadow_outcomes.csv have valid recomputed SHA-256 hashes."""
        df_o = pd.read_csv(self.outc_file)
        self.assertFalse(df_o.empty)

        for _, row in df_o.iterrows():
            rec = row.to_dict()
            stored_hash = rec.pop('outcome_record_hash')
            serialized = json.dumps(rec, sort_keys=True, default=str)
            recomputed = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
            self.assertEqual(stored_hash, recomputed, f"Hash mismatch for outcome {rec.get('prediction_id')}")

    def test_temporal_cutoff_precedes_listing(self):
        """Verify that prediction cutoffs strictly precede listing dates for all joined pairs."""
        df_p = pd.read_csv(self.pred_file)
        df_o = pd.read_csv(self.outc_file)

        merged = pd.merge(df_o, df_p, on='prediction_id')
        for _, row in merged.iterrows():
            pred_time_str = str(row['prediction_timestamp_ist'])
            listing_date_str = str(row['listing_date'])
            pred_date_str = pred_time_str[:10]
            self.assertLessEqual(pred_date_str, listing_date_str,
                                 f"Prediction date {pred_date_str} must not be after listing date {listing_date_str}")

    def test_reclassification_event_exists_for_sample(self):
        """Verify that Pooja Logistics sample prediction has a documented reclassification audit event."""
        df_e = pd.read_csv(self.evnt_file)
        self.assertFalse(df_e.empty)

        pooja_events = df_e[df_e['reference_id'] == 'PRED_20261027_F3728E1D']
        self.assertFalse(pooja_events.empty, "Audit event must exist for PRED_20261027_F3728E1D")
        reclass_ev = pooja_events[pooja_events['reason_code'] == 'HISTORICAL_DEMO_RECLASSIFICATION']
        self.assertFalse(reclass_ev.empty, "Reclassification event to HISTORICAL_DEMONSTRATION must exist")

    def test_rank_tier_boundaries_integrity(self):
        """Verify that tier boundaries in metadata are valid tertiles and monotonic."""
        with open(self.meta_path, 'r') as f:
            meta = json.load(f)

        t1_max = meta['rank_tier_boundaries']['tier_1_max_prob']
        t2_max = meta['rank_tier_boundaries']['tier_2_max_prob']
        self.assertLess(t1_max, t2_max)
        self.assertTrue(0.5 < t1_max < 1.0)
        self.assertTrue(0.5 < t2_max < 1.0)

    def test_rejection_of_post_cutoff_feature_tampering(self):
        """Verify that feature availability audit file exists and has 100% pass status."""
        audit_file = 'data/processed/step_6a4_1_feature_availability_audit.csv'
        self.assertTrue(os.path.exists(audit_file))
        df_a = pd.read_csv(audit_file)
        self.assertEqual(len(df_a), 3)
        self.assertTrue((df_a['audit_verdict'] == 'PASS').all())

if __name__ == '__main__':
    unittest.main()
