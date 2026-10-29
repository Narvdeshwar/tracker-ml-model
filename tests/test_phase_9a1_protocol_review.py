"""
Unit test suite for Phase 9A.1: Evaluation Protocol & Benchmark Review.
Tests:
1. Cutoff Validation:
   - Accepts authoritative non-17:00 cutoffs (e.g. 16:00 IST, 16:30 +05:30, or Day 4/5 extensions).
   - Rejects/flags cutoff missing explicit timezone (IST or +05:30).
   - Rejects/flags cutoff missing authoritative evidence document.
   - Rejects/flags post-cutoff feature publication timestamps.
2. Brier Score and Brier Skill Score:
   - Evaluates model Brier score vs. fixed training constant baseline (MB: 0.7583, SME: 0.8306).
   - Verifies baseline is not refitted on prospective outcomes.
   - Verifies BSS calculation and segmentation by board type.
3. Missing / Pending Outcome Handling:
   - Tracks eligible, known, and pending outcomes cleanly without distorting denominators.
4. Sample-Size Aware Calibration:
   - Flags N < 50 as INCONCLUSIVE_INSUFFICIENT_SAMPLE and suppresses noisy decile bins and slopes.
   - Allows calibration slope evaluation only when N >= 50.
5. Severe Loss Evaluation:
   - Standardizes severe loss as listing-open return <= -10.0%.
   - Computes recall, precision, FPR, and Wilson score 95% confidence intervals.
   - Flags LOW_EVENT_COUNT_CAUTION when severe events < 5.
6. 30-IPO Checkpoint Governance:
   - Classifies metrics into operational, early diagnostic, and inconclusive checks.
   - Confirms automatic production authorization is strictly False.
"""

import unittest
import os
import json
import numpy as np
import pandas as pd

from src.prospective_simulator_logger import (
    ProspectiveDecisionLogger,
    compute_wilson_score_interval,
    compute_bootstrap_brier_ci
)

class TestPhase9A1ProtocolReview(unittest.TestCase):

    def setUp(self):
        self.test_dec_ledger = 'data/processed/test_phase_9a1_dec_tmp.jsonl'
        self.test_out_ledger = 'data/processed/test_phase_9a1_out_tmp.jsonl'
        self.logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.test_dec_ledger,
            outcome_ledger_path=self.test_out_ledger
        )

    def tearDown(self):
        if os.path.exists(self.test_dec_ledger):
            os.remove(self.test_dec_ledger)
        if os.path.exists(self.test_out_ledger):
            os.remove(self.test_out_ledger)

    def test_cutoff_logic_authoritative_non_1700_and_extensions(self):
        """Verify that legitimate non-17:00 cutoffs (e.g. 16:00 IST for retail, or Day 4 extensions) pass with authoritative evidence."""
        # Legitimate 16:00 IST close for retail book
        res_1600 = self.logger.record_prospective_decision(
            ipo_id='ipo-cutoff-1600',
            company_name='Retail Early Close Ltd',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-11-04 16:00:00 IST',
            features_dict={'feat': 1.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
            model_name='Model_C', model_sha256='sha',
            feature_provenance={
                'source_url_or_doc': 'https://www.nseindia.com/circulars/retail_close_1600.pdf',
                'cutoff_source_evidence': 'NSE Circular Ref 2026/IPO/881 - Retail Window Close 16:00 IST',
                'source_publication_timestamp_ist': '2026-11-04 15:30:00 IST',
                'retrieval_timestamp_ist': '2026-11-04 15:45:00 IST',
                'raw_source_sha256': 'abc123rawhash',
                'is_timing_verified': True
            }
        )
        self.assertEqual(res_1600['timing_verification_status'], 'VERIFIED_PRE_CUTOFF')
        self.assertTrue(res_1600['eligible_for_clean_prospective_cohort'])

        # Extended issue (Day 4 close due to holiday/undersubscription)
        res_ext = self.logger.record_prospective_decision(
            ipo_id='ipo-cutoff-day4',
            company_name='Extended Close Ltd',
            board_type='SME',
            cutoff_timestamp_ist='2026-11-06 17:00:00 +05:30',
            features_dict={'feat': 1.0},
            p_positive_open=0.85, p_macro=0.85, p_severe_loss=0.05,
            model_name='Model_D', model_sha256='sha',
            feature_provenance={
                'source_url_or_doc': 'BSE SME Notice 2026-11-03/01',
                'cutoff_source_evidence': 'Exchange Extension Notice: Issue period extended to Nov 6, 2026, 17:00 IST',
                'source_publication_timestamp_ist': '2026-11-06 14:00:00 IST',
                'raw_source_sha256': 'def456rawhash',
                'is_timing_verified': True
            }
        )
        self.assertEqual(res_ext['timing_verification_status'], 'VERIFIED_PRE_CUTOFF')
        self.assertTrue(res_ext['eligible_for_clean_prospective_cohort'])

    def test_cutoff_rejection_missing_timezone_and_missing_evidence(self):
        """Verify that cutoffs lacking timezone or authoritative evidence are flagged TIMING_UNVERIFIED."""
        # Missing timezone
        res_no_tz = self.logger.record_prospective_decision(
            ipo_id='ipo-no-tz',
            company_name='No Timezone Ltd',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-11-04 17:00:00',  # Missing IST / +05:30
            features_dict={'feat': 1.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
            model_name='Model_C', model_sha256='sha',
            feature_provenance={
                'source_url_or_doc': 'Circular 1',
                'raw_source_sha256': 'hash1',
                'is_timing_verified': True
            }
        )
        self.assertEqual(res_no_tz['timing_verification_status'], 'TIMING_UNVERIFIED')
        self.assertFalse(res_no_tz['eligible_for_clean_prospective_cohort'])

        # Missing cutoff source evidence
        res_no_doc = self.logger.record_prospective_decision(
            ipo_id='ipo-no-doc',
            company_name='No Doc Ltd',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-11-04 17:00:00 IST',
            features_dict={'feat': 1.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
            model_name='Model_C', model_sha256='sha',
            feature_provenance={
                'raw_source_sha256': 'hash1',
                'is_timing_verified': True
            }
        )
        self.assertEqual(res_no_doc['timing_verification_status'], 'TIMING_UNVERIFIED')
        self.assertFalse(res_no_doc['eligible_for_clean_prospective_cohort'])

    def test_cutoff_rejection_post_cutoff_feature_publication(self):
        """Verify that features published after the issue close cutoff are flagged TIMING_UNVERIFIED."""
        res_post = self.logger.record_prospective_decision(
            ipo_id='ipo-post-cutoff',
            company_name='Late News Ltd',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-11-04 17:00:00 IST',
            features_dict={'feat': 1.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
            model_name='Model_C', model_sha256='sha',
            feature_provenance={
                'source_url_or_doc': 'NSE Circular 2026',
                'cutoff_source_evidence': 'Official Issue Master',
                'source_publication_timestamp_ist': '2026-11-04 17:45:00 IST',  # 45 minutes POST-CUTOFF!
                'raw_source_sha256': 'hash_post',
                'is_timing_verified': True
            }
        )
        self.assertEqual(res_post['timing_verification_status'], 'TIMING_UNVERIFIED')
        self.assertFalse(res_post['eligible_for_clean_prospective_cohort'])

    def test_brier_score_and_skill_score_fixed_training_baseline(self):
        """Verify Brier score and BSS against fixed historical training baseline without refitting on prospective data."""
        # Log 4 Mainboard decisions
        # Mainboard training base rate is 0.7583
        for i, (p_pos, actual_open_ret) in enumerate([
            (0.80, 20.0),   # y = 1
            (0.70, 10.0),   # y = 1
            (0.60, -5.0),   # y = 0
            (0.90, 15.0),   # y = 1
        ]):
            ipo_id = f"brier-mb-{i}"
            self.logger.record_prospective_decision(
                ipo_id=ipo_id,
                company_name=f"Brier MB Co {i}",
                board_type='Mainboard',
                cutoff_timestamp_ist='2026-11-04 17:00:00 IST',
                features_dict={'feat': 1.0},
                p_positive_open=p_pos, p_macro=0.80, p_severe_loss=0.05,
                model_name='Model_C', model_sha256='sha',
                feature_provenance={'source': 'NSE', 'raw_source_sha256': 'h', 'is_timing_verified': True}
            )
            self.logger.record_realized_outcome(ipo_id, '2026-11-08', 120.0, 100.0, actual_open_ret)

        eval_brier = self.logger.evaluate_prospective_brier_and_skill('Mainboard', require_clean_cohort=True)
        self.assertEqual(eval_brier['status'], 'EVALUATED')
        self.assertEqual(eval_brier['n_known_outcomes'], 4)
        self.assertEqual(eval_brier['positive_outcomes_count'], 3)
        self.assertEqual(eval_brier['negative_outcomes_count'], 1)
        self.assertEqual(eval_brier['fixed_train_baseline_probability'], 0.7583)

        # Expected model Brier: mean([(0.8-1)^2, (0.7-1)^2, (0.6-0)^2, (0.9-1)^2])
        # = mean([0.04, 0.09, 0.36, 0.01]) = 0.50 / 4 = 0.1250
        self.assertEqual(eval_brier['model_brier_score'], 0.1250)

        # Expected baseline Brier: mean([(0.7583-1)^2 * 3 + (0.7583-0)^2 * 1])
        # = mean([0.05842 * 3 + 0.57502]) = (0.17526 + 0.57502) / 4 = 0.75028 / 4 = 0.1876
        self.assertAlmostEqual(eval_brier['train_baseline_brier_score'], 0.1876, places=3)

        # BSS = 1 - (0.1250 / 0.1876) = 1 - 0.6663 = +0.3337 > 0
        self.assertGreater(eval_brier['brier_skill_score'], 0.0)

    def test_missing_outcome_handling_and_pending_cohort(self):
        """Verify that pending IPOs awaiting listing are cleanly segregated and do not distort denominators."""
        # 1. Log decision with realized outcome
        self.logger.record_prospective_decision(
            ipo_id='listed-ipo',
            company_name='Listed Co',
            board_type='SME',
            cutoff_timestamp_ist='2026-11-04 17:00:00 IST',
            features_dict={'feat': 1.0},
            p_positive_open=0.85, p_macro=0.85, p_severe_loss=0.05,
            model_name='Model_D', model_sha256='sha',
            feature_provenance={'source': 'BSE', 'raw_source_sha256': 'h', 'is_timing_verified': True}
        )
        self.logger.record_realized_outcome('listed-ipo', '2026-11-08', 125.0, 100.0, 25.0)

        # 2. Log decision whose issue closed but has NOT listed yet (pending)
        self.logger.record_prospective_decision(
            ipo_id='pending-ipo',
            company_name='Pending Co',
            board_type='SME',
            cutoff_timestamp_ist='2026-11-05 17:00:00 IST',
            features_dict={'feat': 1.0},
            p_positive_open=0.90, p_macro=0.90, p_severe_loss=0.05,
            model_name='Model_D', model_sha256='sha',
            feature_provenance={'source': 'BSE', 'raw_source_sha256': 'h', 'is_timing_verified': True}
        )

        eval_brier = self.logger.evaluate_prospective_brier_and_skill('SME', require_clean_cohort=True)
        self.assertEqual(eval_brier['n_eligible_decisions'], 2)
        self.assertEqual(eval_brier['n_known_outcomes'], 1)
        self.assertEqual(eval_brier['n_pending_listing'], 1)
        # Brier score is computed ONLY over the 1 known outcome
        self.assertIsNotNone(eval_brier['model_brier_score'])

    def test_sample_size_aware_calibration_inconclusive_when_small(self):
        """Verify that sample size < 50 labels calibration evaluation INCONCLUSIVE_INSUFFICIENT_SAMPLE."""
        # Record 10 decisions and outcomes
        for i in range(10):
            ipo_id = f"small-cal-{i}"
            self.logger.record_prospective_decision(
                ipo_id=ipo_id,
                company_name=f"Small Cal Co {i}",
                board_type='Mainboard',
                cutoff_timestamp_ist='2026-11-04 17:00:00 IST',
                features_dict={'feat': 1.0},
                p_positive_open=0.70 + (i * 0.02), p_macro=0.80, p_severe_loss=0.05,
                model_name='Model_C', model_sha256='sha',
                feature_provenance={'source': 'NSE', 'raw_source_sha256': 'h', 'is_timing_verified': True}
            )
            self.logger.record_realized_outcome(ipo_id, '2026-11-08', 110.0, 100.0, 10.0)

        cal_eval = self.logger.evaluate_prospective_calibration('Mainboard', require_clean_cohort=True)
        self.assertEqual(cal_eval['status'], 'INCONCLUSIVE_INSUFFICIENT_SAMPLE')
        self.assertIsNone(cal_eval['calibration_slope'])
        self.assertEqual(len(cal_eval['calibration_bins']), 0)
        self.assertFalse(cal_eval['recalibration_recommended'])
        self.assertIn("insufficient", cal_eval['message'].lower())

    def test_severe_loss_evaluation_wilson_ci_and_low_event_caution(self):
        """Verify severe loss metrics: catch rate, precision, Wilson score CIs, and low event count warning."""
        # Mainboard severe loss threshold theta_loss = 0.4868
        # Simulate 5 IPOs:
        # IPO 0: p_loss=0.60 (flagged), ret=-15% (actual severe) -> True Positive
        # IPO 1: p_loss=0.55 (flagged), ret=+10% (non-severe)    -> False Positive
        # IPO 2: p_loss=0.20 (not flg), ret=-12% (actual severe) -> False Negative
        # IPO 3: p_loss=0.10 (not flg), ret=+20% (non-severe)    -> True Negative
        # IPO 4: p_loss=0.15 (not flg), ret=+05% (non-severe)    -> True Negative
        data = [
            ('sl-0', 0.60, -15.0),
            ('sl-1', 0.55, 10.0),
            ('sl-2', 0.20, -12.0),
            ('sl-3', 0.10, 20.0),
            ('sl-4', 0.15, 5.0),
        ]
        for ipo_id, p_loss, ret in data:
            self.logger.record_prospective_decision(
                ipo_id=ipo_id,
                company_name=f"SL Co {ipo_id}",
                board_type='Mainboard',
                cutoff_timestamp_ist='2026-11-04 17:00:00 IST',
                features_dict={'feat': 1.0},
                p_positive_open=0.70, p_macro=0.70, p_severe_loss=p_loss,
                model_name='Model_E', model_sha256='sha',
                feature_provenance={'source': 'NSE', 'raw_source_sha256': 'h', 'is_timing_verified': True}
            )
            self.logger.record_realized_outcome(ipo_id, '2026-11-08', 100.0 * (1 + ret / 100.0), 100.0, ret)

        loss_eval = self.logger.evaluate_prospective_severe_loss('Mainboard', require_clean_cohort=True)
        self.assertEqual(loss_eval['status'], 'EVALUATED')
        self.assertEqual(loss_eval['n_severe_events'], 2)
        self.assertEqual(loss_eval['confusion_matrix']['true_positives_caught'], 1)
        self.assertEqual(loss_eval['confusion_matrix']['false_positives_rejected'], 1)
        self.assertEqual(loss_eval['confusion_matrix']['false_negatives_missed'], 1)
        self.assertEqual(loss_eval['confusion_matrix']['true_negatives_passed'], 2)

        # Recall = 1 / 2 = 50.0%
        self.assertEqual(loss_eval['recall_catch_rate_pct'], 50.0)
        # Precision = 1 / 2 = 50.0%
        self.assertEqual(loss_eval['precision_pct'], 50.0)
        # FPR = 1 / 3 = 33.33%
        self.assertEqual(loss_eval['false_positive_rate_pct'], 33.33)

        # Wilson score intervals must be populated tuples
        self.assertIsNotNone(loss_eval['recall_95_wilson_ci'][0])
        self.assertIsNotNone(loss_eval['precision_95_wilson_ci'][0])

        # Event count = 2 (< 5), so caution flag must be present
        self.assertIsNotNone(loss_eval['caution_flag'])
        self.assertIn("LOW_EVENT_COUNT_CAUTION", loss_eval['caution_flag'])

    def test_30_ipo_checkpoint_metric_classification_and_governance(self):
        """Verify 30-IPO checkpoint audits operational metrics, diagnostic metrics, and inconclusive categories."""
        chk = self.logger.evaluate_30_ipo_checkpoint(require_clean_cohort=True)

        # 1. Governance mandate
        self.assertEqual(chk['governance_mandate']['execution_mode'], 'OPERATIONAL_SHADOW_LOGGING_ONLY')
        self.assertEqual(chk['governance_mandate']['real_money_trading'], 'STRICTLY_PROHIBITED')
        self.assertFalse(chk['governance_mandate']['automatic_production_authorization'])

        # 2. Check structure
        self.assertIn('operational_pass_fail_checks', chk)
        self.assertIn('early_performance_diagnostics', chk)
        self.assertIn('inconclusive_statistical_checks', chk)

        # 3. Inconclusive checks documented
        incon = chk['inconclusive_statistical_checks']
        self.assertEqual(incon['calibration_slope_and_deciles']['status'], 'INCONCLUSIVE_INSUFFICIENT_SAMPLE')
        self.assertEqual(incon['hypothesis_testing_statistical_superiority']['status'], 'INCONCLUSIVE_UNDERPOWERED')
        self.assertEqual(incon['severe_loss_statistical_significance']['status'], 'INCONCLUSIVE_LOW_EVENT_COUNT')

if __name__ == '__main__':
    unittest.main()
