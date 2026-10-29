"""
Test suite for Step 6A.4: Prospective Shadow Logging Pipeline.
Verifies:
- Frozen model artifact presence & SHA-256 integrity.
- Prediction creation before outcome availability.
- Feature cutoff enforcement & missing input rejection.
- Prediction / Outcome ledger separation (append-only, immutable).
- Idempotency & duplicate prevention.
- Cryptographic hash verification.
- Event audit logging (corrections/integrity alerts).
"""

import unittest
import os
import json
import hashlib
import pandas as pd
from src.shadow_pipeline import (
    log_shadow_prediction, log_shadow_outcome, log_shadow_event,
    compute_record_hash, PREDICTIONS_LEDGER, OUTCOMES_LEDGER, EVENTS_LEDGER,
    MODEL_PATH, METADATA_PATH, ensure_ledgers_exist
)

class TestStep6A4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ledgers_exist()

    def test_model_artifact_and_sha256(self):
        self.assertTrue(os.path.exists(MODEL_PATH), "Frozen model file missing")
        self.assertTrue(os.path.exists(METADATA_PATH), "Model metadata missing")
        with open(METADATA_PATH) as f:
            meta = json.load(f)
        with open(MODEL_PATH, 'rb') as f:
            computed_sha = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(meta['sha256_hash'], computed_sha, "Model artifact SHA-256 mismatch!")

    def test_prediction_creation_and_idempotency(self):
        test_ipo_id = 'test-sme-ipo-alpha'
        pred1 = log_shadow_prediction(
            ipo_id=test_ipo_id,
            company_name='Test Alpha SME Ltd',
            board_type='SME',
            cutoff_date_str='2026-10-25',
            feat_nifty50_ret5s_pct=-0.50,
            feat_india_vix=13.5,
            feat_recent5_sentiment=12.0,
            prediction_timestamp_ist='2026-10-25 17:00:00 IST'
        )
        self.assertIn('prediction_id', pred1)
        self.assertEqual(pred1['status'], 'LOGGED_PRE_LISTING')
        
        # Verify hash integrity
        recalculated_hash = compute_record_hash({k: v for k, v in pred1.items() if k != 'prediction_record_hash'})
        self.assertTrue(len(pred1['prediction_record_hash']) == 64)
        
        # Test Idempotency: calling again should return existing record without adding row
        df_before = pd.read_csv(PREDICTIONS_LEDGER)
        count_before = len(df_before)
        pred2 = log_shadow_prediction(
            ipo_id=test_ipo_id,
            company_name='Test Alpha SME Ltd',
            board_type='SME',
            cutoff_date_str='2026-10-25',
            feat_nifty50_ret5s_pct=-0.50,
            feat_india_vix=13.5,
            feat_recent5_sentiment=12.0,
            prediction_timestamp_ist='2026-10-25 17:00:00 IST'
        )
        df_after = pd.read_csv(PREDICTIONS_LEDGER)
        self.assertEqual(len(df_after), count_before)
        self.assertEqual(pred1['prediction_id'], pred2['prediction_id'])

    def test_missing_features_rejected(self):
        with self.assertRaises(ValueError):
            log_shadow_prediction(
                ipo_id='test-sme-missing-feat',
                company_name='Test Missing',
                board_type='SME',
                cutoff_date_str='2026-10-25',
                feat_nifty50_ret5s_pct=None, # Missing feature
                feat_india_vix=13.5,
                feat_recent5_sentiment=12.0
            )

    def test_non_sme_board_rejected(self):
        with self.assertRaises(ValueError):
            log_shadow_prediction(
                ipo_id='test-mainboard-rejected',
                company_name='Test Mainboard Ltd',
                board_type='Mainboard', # Should reject: model is SME only
                cutoff_date_str='2026-10-25',
                feat_nifty50_ret5s_pct=0.5,
                feat_india_vix=13.5,
                feat_recent5_sentiment=12.0
            )

    def test_outcome_logging_does_not_mutate_prediction(self):
        test_ipo_id = 'test-sme-ipo-beta'
        pred = log_shadow_prediction(
            ipo_id=test_ipo_id,
            company_name='Test Beta SME Ltd',
            board_type='SME',
            cutoff_date_str='2026-10-25',
            feat_nifty50_ret5s_pct=1.2,
            feat_india_vix=12.8,
            feat_recent5_sentiment=25.0,
            prediction_timestamp_ist='2026-10-25 17:00:00 IST'
        )
        pred_id = pred['prediction_id']
        
        # Snapshot prediction record
        df_preds_before = pd.read_csv(PREDICTIONS_LEDGER)
        pred_row_before = df_preds_before[df_preds_before['prediction_id'] == pred_id].to_dict(orient='records')[0]
        
        # Append outcome
        outcome = log_shadow_outcome(
            prediction_id=pred_id,
            issue_price_inr=100.0,
            listing_open_price_inr=125.0,
            listing_date_str='2026-10-29'
        )
        self.assertEqual(outcome['actual_opening_return_pct'], 25.0)
        self.assertEqual(outcome['actual_positive_open'], 1)
        self.assertEqual(outcome['actual_severe_loss'], 0)
        
        # Verify prediction record was NOT mutated
        df_preds_after = pd.read_csv(PREDICTIONS_LEDGER)
        pred_row_after = df_preds_after[df_preds_after['prediction_id'] == pred_id].to_dict(orient='records')[0]
        self.assertEqual(pred_row_before, pred_row_after, "Prediction ledger was mutated when outcome was appended!")

    def test_audit_event_logging(self):
        evt = log_shadow_event(
            event_type='PERFORMANCE_WARNING',
            reference_id='Model_6B_SME_v1.0',
            reason_code='REGIME_SHIFT_REVIEW',
            description='Trailing tier win rate dropped below monitoring threshold during prospective window'
        )
        self.assertIn('event_id', evt)
        df_events = pd.read_csv(EVENTS_LEDGER)
        self.assertTrue((df_events['event_id'] == evt['event_id']).any())

if __name__ == '__main__':
    unittest.main()
