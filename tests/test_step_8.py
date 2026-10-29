"""
Unit test suite for Step 8: Historical IPO Decision and Allocation Simulator.
Tests:
1. Baseline model protection: Model_6B_SME_v1.0 SHA-256 remains strictly untouched.
2. Dataset outputs existence: All simulation ledgers, strategy tables, sensitivity matrices, and exclusion ledgers exist.
3. Exclusions accounting: All 1,515 IPOs are accounted for in the exclusion register.
4. Strategy performance accounting: Exactly 18 evaluations (3 segment views x 6 strategies).
5. Strategy F invariants: Cash benchmark has zero applications, zero allotments, and zero net PnL.
6. Capital conservation: On every simulated event, available_cash + blocked_cash == total_portfolio_val.
7. Non-negative balances: Blocked cash and available cash remain non-negative throughout execution.
8. Lookahead leakage guardrail: ProspectiveDecisionLogger raises ValueError if listing return fields are passed.
9. Ledger separation & idempotency: Decision and outcome ledgers are separate; duplicate decisions are ignored.
10. Sensitivity completeness: Exactly 108 scenario evaluations in sensitivity matrix.
"""

import unittest
import os
import json
import hashlib
import pandas as pd
import numpy as np
from src.prospective_simulator_logger import ProspectiveDecisionLogger

class TestStep8DecisionSimulator(unittest.TestCase):

    def setUp(self):
        self.perf_file = 'data/processed/step_8_strategy_performance.csv'
        self.ledger_file = 'data/processed/step_8_capital_event_ledger.csv'
        self.sens_file = 'data/processed/step_8_sensitivity_analysis.csv'
        self.excl_file = 'data/processed/step_8_exclusions_and_missingness.csv'
        self.frozen_model_file = 'models/frozen/model_6b_sme_v1.joblib'
        self.meta_file = 'models/frozen/model_6b_sme_v1_metadata.json'

    def test_frozen_baseline_sme_model_immutability(self):
        """Verify baseline SME model artifact remains strictly untouched."""
        with open(self.meta_file, 'r') as f:
            meta = json.load(f)

        with open(self.frozen_model_file, 'rb') as f:
            computed_sha = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(computed_sha, meta['sha256_hash'])
        self.assertEqual(computed_sha, 'dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76')

    def test_step_8_output_files_exist(self):
        """Verify all Step 8 simulation outputs exist on disk."""
        self.assertTrue(os.path.exists(self.perf_file))
        self.assertTrue(os.path.exists(self.ledger_file))
        self.assertTrue(os.path.exists(self.sens_file))
        self.assertTrue(os.path.exists(self.excl_file))

    def test_exclusions_accounting_dimensions(self):
        """Verify that exclusions table accounts for all 1,515 IPOs."""
        df_excl = pd.read_csv(self.excl_file)
        self.assertEqual(len(df_excl), 1515)
        self.assertEqual(df_excl['ipo_id'].nunique(), 1515)
        self.assertTrue(set(df_excl['included_in_simulation'].unique()).issubset({True, False}))

    def test_strategy_performance_accounting(self):
        """Verify exactly 18 strategy evaluations (3 segments x 6 strategies)."""
        df_perf = pd.read_csv(self.perf_file)
        self.assertEqual(len(df_perf), 18)
        expected_strats = {
            'Strategy_A_Apply_All',
            'Strategy_B_Macro_Filter',
            'Strategy_C_Positive_Ranking',
            'Strategy_D_Downside_Filter',
            'Strategy_E_Combined',
            'Strategy_F_No_Application'
        }
        self.assertEqual(set(df_perf['strategy'].unique()), expected_strats)
        self.assertEqual(set(df_perf['market_segment'].unique()), {'Combined', 'Mainboard', 'SME'})

    def test_strategy_f_cash_invariants(self):
        """Verify that Strategy F (Cash Benchmark) incurs zero actions and zero PnL."""
        df_perf = pd.read_csv(self.perf_file)
        strat_f = df_perf[df_perf['strategy'] == 'Strategy_F_No_Application']
        self.assertTrue((strat_f['applications_submitted'] == 0).all())
        self.assertTrue((strat_f['allotments_won'] == 0).all())
        self.assertTrue((strat_f['net_profit_inr'] == 0.0).all())
        self.assertTrue((strat_f['max_drawdown_pct'] == 0.0).all())

    def test_capital_conservation_in_ledger(self):
        """Verify capital accounting equality holds on every single transaction event."""
        df_ledger = pd.read_csv(self.ledger_file)
        self.assertGreater(len(df_ledger), 0)
        
        # available_cash + blocked_cash == total_portfolio_val within floating tolerance
        diff = (df_ledger['available_cash'] + df_ledger['blocked_cash']) - df_ledger['total_portfolio_val']
        self.assertTrue((diff.abs() < 0.05).all())

    def test_non_negative_capital_balances(self):
        """Verify blocked cash and available cash never drop below zero."""
        df_ledger = pd.read_csv(self.ledger_file)
        self.assertTrue((df_ledger['available_cash'] >= 0.0).all())
        self.assertTrue((df_ledger['blocked_cash'] >= 0.0).all())

    def test_lookahead_leakage_prevention(self):
        """Verify prospective logger strictly prohibits post-listing return inputs."""
        test_dec_path = 'data/processed/test_prospective_dec_tmp.jsonl'
        logger = ProspectiveDecisionLogger(decision_ledger_path=test_dec_path)
        
        # Passing forbidden target field must trigger ValueError
        with self.assertRaises(ValueError):
            logger.record_prospective_decision(
                ipo_id='test-leakage-ipo',
                company_name='Leakage Test Ltd',
                board_type='Mainboard',
                cutoff_timestamp_ist='2026-10-27 17:00:00 IST',
                features_dict={'listing_open_return_pct': 15.0},
                p_positive_open=0.75,
                p_macro=0.60,
                p_severe_loss=0.10,
                model_name='TestModel',
                model_sha256='abc123'
            )
            
        if os.path.exists(test_dec_path):
            os.remove(test_dec_path)

    def test_prospective_logger_idempotency_and_recording(self):
        """Verify clean recording and duplicate prevention in prospective logger."""
        test_dec_path = 'data/processed/test_prospective_dec_tmp.jsonl'
        test_out_path = 'data/processed/test_prospective_out_tmp.jsonl'
        logger = ProspectiveDecisionLogger(decision_ledger_path=test_dec_path, outcome_ledger_path=test_out_path)
        
        # 1. Record decision
        res1 = logger.record_prospective_decision(
            ipo_id='test-safe-ipo-001',
            company_name='Safe Test Ltd',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-10-27 17:00:00 IST',
            features_dict={'nifty50_return_5s': 0.85},
            p_positive_open=0.82,
            p_macro=0.65,
            p_severe_loss=0.08,
            model_name='TestModel',
            model_sha256='abc123'
        )
        self.assertEqual(res1['status'], 'RECORDED')
        
        # 2. Duplicate decision ignored
        res2 = logger.record_prospective_decision(
            ipo_id='test-safe-ipo-001',
            company_name='Safe Test Ltd',
            board_type='Mainboard',
            cutoff_timestamp_ist='2026-10-27 17:00:00 IST',
            features_dict={'nifty50_return_5s': 0.85},
            p_positive_open=0.82,
            p_macro=0.65,
            p_severe_loss=0.08,
            model_name='TestModel',
            model_sha256='abc123'
        )
        self.assertEqual(res2['status'], 'DUPLICATE_IGNORED')
        
        # 3. Record outcome
        res3 = logger.record_realized_outcome(
            ipo_id='test-safe-ipo-001',
            listing_date='2026-10-30',
            listing_open_inr=120.0,
            issue_price_inr=100.0,
            listing_open_return_pct=20.0
        )
        self.assertEqual(res3['status'], 'RECORDED')
        
        # Cleanup
        if os.path.exists(test_dec_path):
            os.remove(test_dec_path)
        if os.path.exists(test_out_path):
            os.remove(test_out_path)

    def test_sensitivity_matrix_completeness(self):
        """Verify sensitivity matrix contains exactly 108 scenario evaluations."""
        df_sens = pd.read_csv(self.sens_file)
        # 3 strategies x 4 allotment probs x 3 slippage levels x 3 cost levels = 108
        self.assertEqual(len(df_sens), 108)
        self.assertEqual(set(df_sens['allotment_prob'].unique()), {0.2, 0.5, 0.8, 1.0})
        self.assertEqual(set(df_sens['slippage_pct'].unique()), {0.0, 1.0, 2.0})
        self.assertEqual(set(df_sens['roundtrip_cost_pct'].unique()), {0.0, 0.35, 0.7})

if __name__ == '__main__':
    unittest.main()
