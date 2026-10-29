"""
Unit test suite for Phase 9B: Prospective Shadow Evaluation Setup & Governance Hardening.
Tests:
1. Three-population tracking (all eligible, clean prospective, excluded unverified).
2. Selection bias audit across clean vs excluded cohorts.
3. Four-tier performance reporting separation (prediction vs allotment vs execution vs simulation).
4. Brier Skill Score acceptance rule differentiation (checkpoint diagnostic vs production hurdle).
5. Phase 9B baseline manifest existence, contents, and frozen model SHA-256 match.
"""

import unittest
import os
import json
import hashlib
import pandas as pd

from src.prospective_simulator_logger import ProspectiveDecisionLogger

class TestPhase9BSetup(unittest.TestCase):

    def setUp(self):
        self.test_dec_ledger = 'data/processed/test_phase_9b_dec_tmp.jsonl'
        self.test_out_ledger = 'data/processed/test_phase_9b_out_tmp.jsonl'
        self.logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.test_dec_ledger,
            outcome_ledger_path=self.test_out_ledger
        )
        self.manifest_path = 'models/frozen/phase_9b_baseline_manifest.json'
        self.frozen_model_path = 'models/frozen/model_6b_sme_v1.joblib'

    def tearDown(self):
        if os.path.exists(self.test_dec_ledger):
            os.remove(self.test_dec_ledger)
        if os.path.exists(self.test_out_ledger):
            os.remove(self.test_out_ledger)

    def test_three_population_tracking(self):
        """Verify that all eligible, clean prospective, and excluded unverified cohorts are tracked as three distinct populations."""
        # 1. Log Clean IPO
        self.logger.record_prospective_decision(
            ipo_id='pop-clean-1', company_name='Clean One Ltd', board_type='Mainboard',
            cutoff_timestamp_ist='2026-11-04 17:00:00 IST', features_dict={'feat': 1.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
            model_name='Model_C', model_sha256='sha',
            feature_provenance={'source': 'NSE', 'raw_source_sha256': 'hash1', 'is_timing_verified': True}
        )
        # 2. Log another Clean IPO
        self.logger.record_prospective_decision(
            ipo_id='pop-clean-2', company_name='Clean Two Ltd', board_type='SME',
            cutoff_timestamp_ist='2026-11-04 17:00:00 IST', features_dict={'feat': 1.0},
            p_positive_open=0.85, p_macro=0.85, p_severe_loss=0.05,
            model_name='Model_D', model_sha256='sha',
            feature_provenance={'source': 'BSE', 'raw_source_sha256': 'hash2', 'is_timing_verified': True}
        )
        # 3. Log Excluded/Unverified IPO (missing timing verification)
        self.logger.record_prospective_decision(
            ipo_id='pop-unver-1', company_name='Unverified Ltd', board_type='SME',
            cutoff_timestamp_ist='2026-11-04 17:00:00 IST', features_dict={'feat': 1.0},
            p_positive_open=0.90, p_macro=0.90, p_severe_loss=0.05,
            model_name='Model_D', model_sha256='sha',
            feature_provenance={'source': 'BSE', 'is_timing_verified': False}
        )

        pops = self.logger.get_cohort_populations()
        counts = pops['counts']
        self.assertEqual(counts['n_all_eligible'], 3)
        self.assertEqual(counts['n_clean_prospective'], 2)
        self.assertEqual(counts['n_excluded_unverified'], 1)
        self.assertAlmostEqual(counts['clean_coverage_pct'], 66.67, places=1)

    def test_selection_bias_audit(self):
        """Verify that audit_selection_bias correctly detects cohort mix differences and exclusion reasons."""
        # Clean: Mainboard
        self.logger.record_prospective_decision(
            ipo_id='bias-clean-1', company_name='Clean MB Ltd', board_type='Mainboard',
            cutoff_timestamp_ist='2026-11-04 17:00:00 IST', features_dict={'feat': 1.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
            model_name='Model_C', model_sha256='sha',
            feature_provenance={'source': 'NSE', 'raw_source_sha256': 'h1', 'is_timing_verified': True}
        )
        # Excluded: SME missing timing
        self.logger.record_prospective_decision(
            ipo_id='bias-excl-1', company_name='Excluded SME Ltd', board_type='SME',
            cutoff_timestamp_ist='2026-11-04 17:00:00 IST', features_dict={'feat': 1.0},
            p_positive_open=0.85, p_macro=0.85, p_severe_loss=0.05,
            model_name='Model_D', model_sha256='sha',
            feature_provenance={'source': 'BSE', 'is_timing_verified': False}
        )

        audit_res = self.logger.audit_selection_bias()
        self.assertEqual(audit_res['status'], 'EVALUATED')
        self.assertEqual(audit_res['n_clean_prospective'], 1)
        self.assertEqual(audit_res['n_excluded_unverified'], 1)
        self.assertEqual(audit_res['clean_segment_mix']['Mainboard'], 1)
        self.assertEqual(audit_res['excluded_segment_mix']['SME'], 1)
        self.assertIn('MISSING_PROVENANCE_HASH', audit_res['exclusion_reasons_breakdown'])

    def test_four_tier_performance_reporting_separation(self):
        """Verify strict separation into Tier 1 (prediction), Tier 2 (allotment), Tier 3 (execution), and Tier 4 (simulated scenario)."""
        # Record 1 clean IPO and outcome
        self.logger.record_prospective_decision(
            ipo_id='tier-ipo-1', company_name='Tier Test Co', board_type='Mainboard',
            cutoff_timestamp_ist='2026-11-04 17:00:00 IST', features_dict={'feat': 1.0},
            p_positive_open=0.85, p_macro=0.85, p_severe_loss=0.05,
            model_name='Model_C', model_sha256='sha',
            feature_provenance={'source': 'NSE', 'raw_source_sha256': 'h', 'is_timing_verified': True}
        )
        self.logger.record_realized_outcome(
            ipo_id='tier-ipo-1', listing_date='2026-11-08', listing_open_inr=120.0,
            issue_price_inr=100.0, listing_open_return_pct=20.0, observed_allotment='ALLOTTED'
        )

        tier_rep = self.logger.generate_four_tier_performance_report('Strategy_E_Combined')

        # Tier 1: Prediction results
        t1 = tier_rep['tier_1_model_prediction']
        self.assertEqual(t1['applied_ipo_count'], 1)
        self.assertEqual(t1['ipo_prediction_win_rate_pct'], 100.0)

        # Tier 2: Observed allotment results
        t2 = tier_rep['tier_2_observed_allotment']
        self.assertTrue(t2['empirical_records_available'])
        self.assertEqual(t2['allotted_applications_count'], 1)

        # Tier 3: Actual execution results (Prohibited in shadow mode)
        t3 = tier_rep['tier_3_actual_execution']
        self.assertEqual(t3['execution_mode'], 'SHADOW_MODE_ONLY')
        self.assertEqual(t3['real_capital_deployed_inr'], 0.0)
        self.assertEqual(t3['status'], 'REAL_EXECUTION_STRICTLY_PROHIBITED')

        # Tier 4: Simulated scenario analysis
        t4 = tier_rep['tier_4_simulated_scenario']
        self.assertIn('HYPOTHETICAL_SIMULATION_ONLY', t4['disclaimer'])

    def test_bss_acceptance_rule_clarification_in_checkpoint(self):
        """Verify that evaluate_30_ipo_checkpoint clearly differentiates checkpoint monitoring from production hurdle."""
        chk = self.logger.evaluate_30_ipo_checkpoint(require_clean_cohort=True)
        rules = chk['governance_mandate']['brier_skill_score_acceptance_rules']
        self.assertIn('checkpoint_monitoring_standard', rules)
        self.assertIn('future_statistical_production_hurdle', rules)
        self.assertIn('lower bound > 0.0', rules['future_statistical_production_hurdle'])

    def test_phase_9b_baseline_manifest_immutability(self):
        """Verify Phase 9B baseline manifest exists and frozen model SHA-256 matches bit-for-bit."""
        self.assertTrue(os.path.exists(self.manifest_path))
        with open(self.manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        self.assertEqual(manifest['execution_mode'], 'OPERATIONAL_SHADOW_LOGGING_ONLY')
        self.assertEqual(manifest['real_money_trading'], 'STRICTLY_PROHIBITED')

        # Verify frozen model hash
        sme_model_info = manifest['frozen_baseline_models']['Model_6B_SME_v1.0']
        with open(self.frozen_model_path, 'rb') as f:
            actual_sha = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(actual_sha, sme_model_info['sha256'])
        self.assertEqual(actual_sha, 'dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76')

if __name__ == '__main__':
    unittest.main()
