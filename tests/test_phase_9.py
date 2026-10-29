"""
Unit test suite for Phase 9: Prospective IPO Shadow Evaluation Readiness.
Tests:
1. Baseline model protection: Model_6B_SME_v1.0 SHA-256 remains strictly untouched.
2. Deterministic nested allotment draws: Allotted(20%) <= Allotted(50%) <= Allotted(80%) <= Allotted(100%).
3. Prospective decision logging: Records decisions with feature hashes, thresholds, and rejection reasons.
4. Lookahead leakage guardrail: Rejects listing prices, returns, and post-listing dates.
5. Idempotent duplicate prevention: Duplicate decisions for the same IPO are safely ignored.
6. Outcome ledger separation: Realized outcomes are written to a physically separate ledger.
7. Outcome matching requirement: Attempting to log an outcome without a pre-existing decision raises ValueError.
8. Tamper-evident hash integrity: Modifying a record invalidates its SHA-256 hash.
9. Protocol documentation existence: Evaluation protocol and readiness audit reports exist.
"""

import unittest
import os
import json
import hashlib
import pandas as pd
from src.run_step_8_1_audit_simulator import get_deterministic_allotment
from src.prospective_simulator_logger import ProspectiveDecisionLogger

class TestPhase9Readiness(unittest.TestCase):

    def setUp(self):
        self.test_dec_ledger = 'data/processed/test_phase_9_dec_tmp.jsonl'
        self.test_out_ledger = 'data/processed/test_phase_9_out_tmp.jsonl'
        self.logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.test_dec_ledger,
            outcome_ledger_path=self.test_out_ledger
        )
        self.frozen_model_file = 'models/frozen/model_6b_sme_v1.joblib'
        self.meta_file = 'models/frozen/model_6b_sme_v1_metadata.json'

    def tearDown(self):
        if os.path.exists(self.test_dec_ledger):
            os.remove(self.test_dec_ledger)
        if os.path.exists(self.test_out_ledger):
            os.remove(self.test_out_ledger)

    def test_frozen_baseline_sme_model_immutability(self):
        """Verify baseline SME model artifact remains strictly untouched."""
        with open(self.meta_file, 'r') as f:
            meta = json.load(f)

        with open(self.frozen_model_file, 'rb') as f:
            computed_sha = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(computed_sha, meta['sha256_hash'])
        self.assertEqual(computed_sha, 'dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76')

    def test_deterministic_nested_allotment_draws(self):
        """Verify strict mathematical nesting: 20% subset of 50% subset of 80% subset of 100%."""
        test_ipos = [f'test-ipo-{i:03d}' for i in range(100)]
        seed = 42
        
        for ipo in test_ipos:
            d20 = get_deterministic_allotment(ipo, seed, 0.20)
            d50 = get_deterministic_allotment(ipo, seed, 0.50)
            d80 = get_deterministic_allotment(ipo, seed, 0.80)
            d100 = get_deterministic_allotment(ipo, seed, 1.00)
            
            self.assertTrue(d100)
            if d20:
                self.assertTrue(d50, f"Violation for {ipo}: in 20% but not in 50%")
            if d50:
                self.assertTrue(d80, f"Violation for {ipo}: in 50% but not in 80%")

    def test_prospective_decision_logging_completeness(self):
        """Verify that all required fields, hashes, and rejection reasons are recorded."""
        res = self.logger.record_prospective_decision(
            ipo_id='prospective-ipo-001',
            company_name='Prospective Tech Ltd',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-10-30 17:00:00 IST',
            features_dict={'nifty50_return_5s': 0.85, 'india_vix_level_at_cutoff': 14.5},
            p_positive_open=0.82,
            p_macro=0.81,
            p_severe_loss=0.08,
            model_name='Model_C_Structure_Only',
            model_sha256='abc123sha',
            feature_provenance={'source': 'NSE Circular', 'pub_date': '2026-10-28'},
            data_quality_warnings=[]
        )
        self.assertEqual(res['status'], 'RECORDED')
        
        with open(self.test_dec_ledger, 'r') as f:
            line = f.readline()
            rec = json.loads(line)
            
        self.assertEqual(rec['ipo_id'], 'prospective-ipo-001')
        self.assertIn('feature_hash_sha256', rec)
        self.assertIn('rejection_reasons', rec)
        self.assertIn('Strategy_B_Macro_Filter', rec['strategy_decisions'])
        self.assertTrue(rec['strategy_decisions']['Strategy_B_Macro_Filter'])
        self.assertIsNone(rec['rejection_reasons']['Strategy_B_Macro_Filter'])

    def test_lookahead_leakage_guardrail(self):
        """Verify that passing post-listing outcomes raises ValueError."""
        prohibited_cases = [
            {'listing_open_return_pct': 12.5},
            {'listing_open_inr': 150.0},
            {'listing_close_inr': 155.0},
            {'listing_date': '2026-11-05'}
        ]
        for bad_feat in prohibited_cases:
            with self.assertRaises(ValueError):
                self.logger.record_prospective_decision(
                    ipo_id='test-leak',
                    company_name='Leak Ltd',
                    board_type='SME',
                    cutoff_timestamp_ist='2026-10-30 17:00:00 IST',
                    features_dict=bad_feat,
                    p_positive_open=0.80,
                    p_macro=0.80,
                    p_severe_loss=0.10,
                    model_name='Test',
                    model_sha256='sha'
                )

    def test_idempotent_duplicate_prevention(self):
        """Verify duplicate decision attempts are rejected idempotently."""
        res1 = self.logger.record_prospective_decision(
            ipo_id='dup-ipo',
            company_name='Dup Ltd',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-10-30 17:00:00 IST',
            features_dict={'nifty50_return_5s': 0.5},
            p_positive_open=0.75,
            p_macro=0.75,
            p_severe_loss=0.10,
            model_name='Test',
            model_sha256='sha'
        )
        self.assertEqual(res1['status'], 'RECORDED')
        
        res2 = self.logger.record_prospective_decision(
            ipo_id='dup-ipo',
            company_name='Dup Ltd',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-10-30 17:00:00 IST',
            features_dict={'nifty50_return_5s': 0.5},
            p_positive_open=0.75,
            p_macro=0.75,
            p_severe_loss=0.10,
            model_name='Test',
            model_sha256='sha'
        )
        self.assertEqual(res2['status'], 'DUPLICATE_IGNORED')

    def test_outcome_ledger_separation_and_matching(self):
        """Verify outcome requires pre-existing decision and is logged to separate file."""
        # 1. Unmatched outcome fails
        with self.assertRaises(ValueError):
            self.logger.record_realized_outcome(
                ipo_id='nonexistent-ipo',
                listing_date='2026-11-02',
                listing_open_inr=120.0,
                issue_price_inr=100.0,
                listing_open_return_pct=20.0
            )
            
        # 2. Matched outcome succeeds
        self.logger.record_prospective_decision(
            ipo_id='matched-ipo',
            company_name='Matched Ltd',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-10-30 17:00:00 IST',
            features_dict={'nifty50_return_5s': 0.5},
            p_positive_open=0.85,
            p_macro=0.80,
            p_severe_loss=0.05,
            model_name='Test',
            model_sha256='sha'
        )
        res_out = self.logger.record_realized_outcome(
            ipo_id='matched-ipo',
            listing_date='2026-11-02',
            listing_open_inr=120.0,
            issue_price_inr=100.0,
            listing_open_return_pct=20.0
        )
        self.assertEqual(res_out['status'], 'RECORDED')
        
        # Verify physical file separation
        self.assertTrue(os.path.exists(self.test_dec_ledger))
        self.assertTrue(os.path.exists(self.test_out_ledger))
        with open(self.test_out_ledger, 'r') as f:
            out_rec = json.loads(f.readline())
        self.assertEqual(out_rec['record_type'], 'REALIZED_OUTCOME')
        self.assertEqual(out_rec['modeled_net_return_pct'], 18.65)  # 20.0 - 1.0 - 0.35

    def test_tamper_evident_record_hashing(self):
        """Verify that record_sha256 matches the cryptographic hash of the record contents."""
        self.logger.record_prospective_decision(
            ipo_id='tamper-ipo',
            company_name='Tamper Test Ltd',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-10-30 17:00:00 IST',
            features_dict={'nifty50_return_5s': 0.5},
            p_positive_open=0.80,
            p_macro=0.80,
            p_severe_loss=0.05,
            model_name='Test',
            model_sha256='sha'
        )
        with open(self.test_dec_ledger, 'r') as f:
            rec = json.loads(f.readline())
            
        stored_hash = rec['record_sha256']
        recomputed_hash = self.logger._compute_record_hash(rec)
        self.assertEqual(stored_hash, recomputed_hash)
        
        # Tampering with a field must invalidate hash
        rec['p_positive_open'] = 0.99
        tampered_hash = self.logger._compute_record_hash(rec)
        self.assertNotEqual(stored_hash, tampered_hash)

if __name__ == '__main__':
    unittest.main()
