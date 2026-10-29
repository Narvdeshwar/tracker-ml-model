"""
Unit test suite for Phase 9A: Operational Shadow Logging Pre-Launch Audit.
Validates:
1. Baseline model protection: Model_6B_SME_v1.0 SHA-256 remains strictly untouched.
2. Uniform draw bounds: u in [0, 1) strictly using SHA-256 64-bit integer draw.
3. Deterministic allotment boundary conditions: p=0.0 -> False, p=1.0 -> True, p<0 or p>1 -> ValueError.
4. Deterministic allotment nested monotonicity across all probability levels.
5. Fail-safe input validation: NaN, Inf, None, or out-of-bounds probability safely rejects all applications.
6. Strict downside operator: P(Severe Loss) >= theta_loss strictly rejects.
7. Provenance and timing audit: Validates pre-cutoff availability flags (VERIFIED_PRE_CUTOFF vs TIMING_UNVERIFIED).
8. Append-only cryptographic hash chaining and full ledger integrity verification.
9. Metric denominator separation: IPO-level prediction win rate vs. allotment-conditioned realized win rate.
"""

import unittest
import os
import json
import hashlib
import numpy as np
import pandas as pd

from src.run_step_8_1_audit_simulator import get_uniform_draw, get_deterministic_allotment
from src.prospective_simulator_logger import ProspectiveDecisionLogger

class TestPhase9APrelaunchAudit(unittest.TestCase):

    def setUp(self):
        self.test_dec_ledger = 'data/processed/test_phase_9a_dec_tmp.jsonl'
        self.test_out_ledger = 'data/processed/test_phase_9a_out_tmp.jsonl'
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

    def test_baseline_model_immutability(self):
        """Verify baseline SME model artifact remains strictly untouched with matching SHA-256."""
        with open(self.meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        with open(self.frozen_model_file, 'rb') as f:
            computed_sha = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(computed_sha, meta['sha256_hash'])
        self.assertEqual(computed_sha, 'dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76')

    def test_uniform_draw_range_bounds(self):
        """Verify get_uniform_draw strictly produces u in [0, 1) and never reaches 1.0."""
        for i in range(1000):
            u = get_uniform_draw(f"ipo-test-{i}", 42)
            self.assertGreaterEqual(u, 0.0)
            self.assertLess(u, 1.0)

        # Theoretical boundary test: maximum 53-bit integer divided by 2**53
        max_uint53 = (1 << 53) - 1
        max_draw = max_uint53 / float(1 << 53)
        self.assertLess(max_draw, 1.0)
        self.assertGreater(max_draw, 0.999999999999999)

    def test_deterministic_allotment_boundary_conditions(self):
        """Verify boundary behavior for p_allotment: 0.0, 1.0, and out-of-bounds inputs."""
        ipo = "test-ipo-boundary"
        seed = 101

        # Strict 0.0 and 1.0 behavior
        self.assertFalse(get_deterministic_allotment(ipo, seed, 0.0))
        self.assertTrue(get_deterministic_allotment(ipo, seed, 1.0))

        # Out-of-bounds raises ValueError
        with self.assertRaises(ValueError):
            get_deterministic_allotment(ipo, seed, -0.01)

        with self.assertRaises(ValueError):
            get_deterministic_allotment(ipo, seed, 1.01)

        with self.assertRaises(ValueError):
            get_deterministic_allotment(ipo, seed, np.nan)

        with self.assertRaises(ValueError):
            get_deterministic_allotment(ipo, seed, None)

    def test_deterministic_allotment_nested_monotonicity(self):
        """Verify mathematical nesting across the entire probability continuum: p1 < p2 => allotted(p1) <= allotted(p2)."""
        seeds = [1, 42, 100, 999]
        probs = [0.10, 0.25, 0.50, 0.75, 0.90]

        for s in seeds:
            for i in range(100):
                ipo_id = f"ipo-nest-{i}"
                results = [get_deterministic_allotment(ipo_id, s, p) for p in probs]
                # If True at index k, all subsequent indices must be True
                for k in range(len(results) - 1):
                    if results[k]:
                        self.assertTrue(results[k+1], f"Monotonicity violation for {ipo_id} at seed {s}")

    def test_fail_safe_rejection_on_nan_and_inf_probability(self):
        """Verify that NaN, inf, or out-of-bounds probabilities trigger fail-safe rejection of all applications."""
        invalid_cases = [
            (np.nan, 0.80, 0.10),
            (0.80, float('inf'), 0.10),
            (0.80, 0.80, None),
            (1.50, 0.80, 0.10),
            (-0.10, 0.80, 0.10)
        ]

        for idx, (p_pos, p_mac, p_loss) in enumerate(invalid_cases):
            ipo_id = f"fail-safe-ipo-{idx}"
            res = self.logger.record_prospective_decision(
                ipo_id=ipo_id,
                company_name=f"Fail Safe Co {idx}",
                board_type='Mainboard',
                cutoff_timestamp_ist='2026-10-30 17:00:00 IST',
                features_dict={'nifty50_return_5s': 0.5},
                p_positive_open=p_pos,
                p_macro=p_mac,
                p_severe_loss=p_loss,
                model_name='Model_Test',
                model_sha256='sha_test'
            )
            self.assertEqual(res['status'], 'RECORDED')
            self.assertEqual(res['temporal_status'], 'FAIL_SAFE_REJECTED')

            # Verify in ledger that all applications are False
            with open(self.test_dec_ledger, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                rec = json.loads(lines[-1])

            self.assertEqual(rec['ipo_id'], ipo_id)
            self.assertFalse(rec['strategy_decisions']['Strategy_A_Apply_All'])
            self.assertFalse(rec['strategy_decisions']['Strategy_B_Macro_Filter'])
            self.assertFalse(rec['strategy_decisions']['Strategy_C_Positive_Ranking'])
            self.assertFalse(rec['strategy_decisions']['Strategy_D_Downside_Filter'])
            self.assertFalse(rec['strategy_decisions']['Strategy_E_Combined'])
            self.assertIn("FAIL_SAFE_REJECT", rec['rejection_reasons']['Strategy_A_Apply_All'])
            self.assertTrue(any('FAIL_SAFE' in w for w in rec['data_quality_warnings']))

    def test_strict_comparison_operator_downside_filter(self):
        """Verify strict inequality: reject application if P(Severe Loss) >= theta_loss."""
        th_loss_mb = self.logger.thresholds['Mainboard']['th_loss']  # 0.4868
        
        # Exact equality must be REJECTED
        self.logger.record_prospective_decision(
            ipo_id='boundary-loss-eq',
            company_name='Boundary Equal Co',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-10-30 17:00:00 IST',
            features_dict={'feat': 1.0},
            p_positive_open=0.85,
            p_macro=0.85,
            p_severe_loss=th_loss_mb,  # Exactly equal to threshold
            model_name='Test',
            model_sha256='sha'
        )
        with open(self.test_dec_ledger, 'r', encoding='utf-8') as f:
            rec_eq = json.loads(f.readlines()[-1])
        self.assertFalse(rec_eq['strategy_decisions']['Strategy_D_Downside_Filter'])
        self.assertIn(">=", rec_eq['rejection_reasons']['Strategy_D_Downside_Filter'])

        # Strictly less than threshold must PASS
        self.logger.record_prospective_decision(
            ipo_id='boundary-loss-pass',
            company_name='Boundary Pass Co',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-10-30 17:00:00 IST',
            features_dict={'feat': 1.0},
            p_positive_open=0.85,
            p_macro=0.85,
            p_severe_loss=th_loss_mb - 0.001,
            model_name='Test',
            model_sha256='sha'
        )
        with open(self.test_dec_ledger, 'r', encoding='utf-8') as f:
            rec_pass = json.loads(f.readlines()[-1])
        self.assertTrue(rec_pass['strategy_decisions']['Strategy_D_Downside_Filter'])
        self.assertIsNone(rec_pass['rejection_reasons']['Strategy_D_Downside_Filter'])

    def test_provenance_and_timing_verification_status(self):
        """Verify that timing verification flags accurately distinguish verified vs unverified records."""
        # 1. Verified prospective input
        res_ver = self.logger.record_prospective_decision(
            ipo_id='verified-prov-ipo',
            company_name='Verified Co',
            board_type='SME',
            cutoff_timestamp_ist='2026-10-30 17:00:00 IST',
            features_dict={'feat': 1.0},
            p_positive_open=0.95,
            p_macro=0.90,
            p_severe_loss=0.05,
            model_name='Model_6B_SME_v1.0',
            model_sha256='dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76',
            feature_provenance={
                'source_url_or_doc': 'https://www.bseindia.com/markets/publicIssues/BSEIPO.aspx',
                'source_publication_timestamp_ist': '2026-10-28 10:00:00 IST',
                'retrieval_timestamp_ist': '2026-10-30 16:30:00 IST',
                'raw_source_sha256': '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
                'is_timing_verified': True
            }
        )
        self.assertEqual(res_ver['timing_verification_status'], 'VERIFIED_PRE_CUTOFF')
        self.assertTrue(res_ver['eligible_for_clean_prospective_cohort'])

        # 2. Unverified input (missing timing confirmation or hash)
        res_unver = self.logger.record_prospective_decision(
            ipo_id='unverified-prov-ipo',
            company_name='Unverified Co',
            board_type='SME',
            cutoff_timestamp_ist='2026-10-30 17:00:00 IST',
            features_dict={'feat': 1.0},
            p_positive_open=0.95,
            p_macro=0.90,
            p_severe_loss=0.05,
            model_name='Model_6B_SME_v1.0',
            model_sha256='dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76',
            feature_provenance={
                'source_url_or_doc': 'Public website',
                'is_timing_verified': False
            }
        )
        self.assertEqual(res_unver['timing_verification_status'], 'TIMING_UNVERIFIED')
        self.assertFalse(res_unver['eligible_for_clean_prospective_cohort'])

    def test_cryptographic_hash_chaining_and_ledger_audit(self):
        """Verify sequential hash chaining across records and tamper detection."""
        # Record 3 sequential decisions
        self.logger.record_prospective_decision(
            ipo_id='chain-ipo-1',
            company_name='Chain One Ltd',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-10-30 17:00:00 IST',
            features_dict={'feat': 1.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.10,
            model_name='Test', model_sha256='sha'
        )
        self.logger.record_prospective_decision(
            ipo_id='chain-ipo-2',
            company_name='Chain Two Ltd',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-10-30 17:00:00 IST',
            features_dict={'feat': 2.0},
            p_positive_open=0.85, p_macro=0.85, p_severe_loss=0.05,
            model_name='Test', model_sha256='sha'
        )
        self.logger.record_prospective_decision(
            ipo_id='chain-ipo-3',
            company_name='Chain Three Ltd',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-10-30 17:00:00 IST',
            features_dict={'feat': 3.0},
            p_positive_open=0.70, p_macro=0.70, p_severe_loss=0.20,
            model_name='Test', model_sha256='sha'
        )

        # Audit initial chain
        audit_res = self.logger.verify_ledger_chain('decision')
        self.assertTrue(audit_res['valid'])
        self.assertEqual(audit_res['count'], 3)
        self.assertEqual(len(audit_res['errors']), 0)

        # Inspect individual records for genesis and link continuity
        with open(self.test_dec_ledger, 'r', encoding='utf-8') as f:
            lines = [json.loads(l) for l in f if l.strip()]

        self.assertEqual(lines[0]['prev_record_sha256'], 'GENESIS_BLOCK')
        self.assertEqual(lines[1]['prev_record_sha256'], lines[0]['record_sha256'])
        self.assertEqual(lines[2]['prev_record_sha256'], lines[1]['record_sha256'])

        # Tampering with record 1 must break audit
        lines[0]['company_name'] = 'Tampered One Ltd'
        with open(self.test_dec_ledger, 'w', encoding='utf-8') as f:
            for l in lines:
                f.write(json.dumps(l) + '\n')

        audit_tampered = self.logger.verify_ledger_chain('decision')
        self.assertFalse(audit_tampered['valid'])
        self.assertGreater(len(audit_tampered['errors']), 0)

    def test_metrics_separation_applied_vs_allotted_win_rates(self):
        """Verify strict mathematical separation between IPO-level prediction win rate and allotment-conditioned portfolio win rate."""
        # 1. Prospective decisions
        ipos = [
            ('metric-ipo-1', 0.85, 0.85, 0.05),  # Strategy E Applies
            ('metric-ipo-2', 0.82, 0.82, 0.08),  # Strategy E Applies
            ('metric-ipo-3', 0.80, 0.80, 0.06),  # Strategy E Applies
            ('metric-ipo-4', 0.60, 0.60, 0.50),  # Strategy E Rejects
        ]
        for ipo_id, p_pos, p_mac, p_loss in ipos:
            self.logger.record_prospective_decision(
                ipo_id=ipo_id,
                company_name=f"Metric Co {ipo_id}",
                board_type='Mainboard',
                cutoff_timestamp_ist='2026-10-30 17:00:00 IST',
                features_dict={'feat': 1.0},
                p_positive_open=p_pos,
                p_macro=p_mac,
                p_severe_loss=p_loss,
                model_name='Model_C',
                model_sha256='sha_metric',
                feature_provenance={
                    'source_url_or_doc': 'NSE Circular',
                    'raw_source_sha256': 'raw_hash_test',
                    'is_timing_verified': True
                }
            )

        # 2. Realized outcomes
        # IPO 1: Applied, Allotted, gross +25.0%, net +23.65%
        self.logger.record_realized_outcome('metric-ipo-1', '2026-11-04', 125.0, 100.0, 25.0, observed_allotment='ALLOTTED')
        # IPO 2: Applied, Allotted, gross -15.0%, net -16.35%
        self.logger.record_realized_outcome('metric-ipo-2', '2026-11-04', 85.0, 100.0, -15.0, observed_allotment='ALLOTTED')
        # IPO 3: Applied, Unallotted, gross +30.0% (Prediction is Win, but Allotment is UNALLOTTED)
        self.logger.record_realized_outcome('metric-ipo-3', '2026-11-04', 130.0, 100.0, 30.0, observed_allotment='UNALLOTTED')
        # IPO 4: Rejected, Allotted (deliberate non-participation)
        self.logger.record_realized_outcome('metric-ipo-4', '2026-11-04', 90.0, 100.0, -10.0, observed_allotment='ALLOTTED')

        eval_res = self.logger.evaluate_prospective_metrics('Strategy_E_Combined', require_clean_cohort=True)

        # Check explicit denominators and counts
        self.assertEqual(eval_res['applied_ipo_count'], 3)
        self.assertEqual(eval_res['allotted_application_count'], 2)
        self.assertEqual(eval_res['unallotted_refund_count'], 1)

        # IPO-level prediction win rate: 2 wins (IPO 1, IPO 3) out of 3 applied IPOs = 66.67%
        self.assertEqual(eval_res['ipo_prediction_win_rate_pct'], 66.67)

        # Allotment-conditioned realized win rate: 1 win (IPO 1) out of 2 allotted IPOs = 50.0%
        self.assertEqual(eval_res['allotment_realized_win_rate_pct'], 50.0)

        # Descriptions present
        self.assertIn('applied_denominator_description', eval_res)
        self.assertIn('allotted_denominator_description', eval_res)

if __name__ == '__main__':
    unittest.main()
