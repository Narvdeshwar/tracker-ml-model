"""
Unit test suite for Step 8.1: Independent Simulator Integrity and Reproducibility Audit.
Tests:
1. Baseline model protection: Model_6B_SME_v1.0 SHA-256 remains strictly untouched.
2. Step 8.1 output artifacts exist.
3. Perfect segment reconciliation: net_profit_total == mainboard_contribution + sme_contribution (diff == 0.0) across all strategies.
4. Deterministic allotment idempotency: Hash-based allotment draws are 100% reproducible.
5. Macro filter calibration audit: Explains raw 0.50 threshold behavior vs. calibrated validation median.
6. Capital conservation: available_cash + blocked_cash == total_portfolio_val on all shared ledger events.
7. Zero PnL on unallotted refunds: Non-allotted applications produce zero gain or loss.
8. Maximum drawdown validity: Drawdowns are mathematically bounded in [0%, 100%].
9. Sensitivity matrix completeness: Exactly 180 scenario runs with perfect segment reconciliation.
10. Target isolation: No realized return fields in pre-cutoff simulation features.
"""

import unittest
import os
import json
import hashlib
import pandas as pd
import numpy as np
from src.run_step_8_1_audit_simulator import get_deterministic_allotment

class TestStep81SimulatorIntegrity(unittest.TestCase):

    def setUp(self):
        self.perf_file = 'data/processed/step_8_1_reconciled_strategy_performance.csv'
        self.ledger_file = 'data/processed/step_8_1_shared_capital_ledger.csv'
        self.macro_audit_file = 'data/processed/step_8_1_macro_filter_audit.csv'
        self.standalone_file = 'data/processed/step_8_1_standalone_strategy_performance.csv'
        self.sens_file = 'data/processed/step_8_1_reconciled_sensitivity.csv'
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

    def test_step_8_1_artifacts_exist(self):
        """Verify all Step 8.1 audit outputs exist on disk."""
        self.assertTrue(os.path.exists(self.perf_file))
        self.assertTrue(os.path.exists(self.ledger_file))
        self.assertTrue(os.path.exists(self.macro_audit_file))
        self.assertTrue(os.path.exists(self.standalone_file))
        self.assertTrue(os.path.exists(self.sens_file))

    def test_segment_reconciliation_zero_diff(self):
        """Verify that total net profit equals mainboard + SME contributions exactly (diff == 0.0)."""
        df_perf = pd.read_csv(self.perf_file)
        self.assertEqual(len(df_perf), 6)
        for _, row in df_perf.iterrows():
            calc_diff = round(row['net_profit_total'] - (row['mainboard_contribution'] + row['sme_contribution']), 4)
            self.assertEqual(calc_diff, 0.0, f"Reconciliation failed for {row['strategy']}: diff = {calc_diff}")
            self.assertEqual(row['reconciliation_diff'], 0.0)

    def test_deterministic_allotment_idempotency(self):
        """Verify that get_deterministic_allotment is completely reproducible and deterministic."""
        ipo_test = 'ipo-test-deterministic-123'
        seed = 42
        prob = 0.50
        
        # Multiple calls on identical inputs must yield identical boolean results
        draw1 = get_deterministic_allotment(ipo_test, seed, prob)
        draw2 = get_deterministic_allotment(ipo_test, seed, prob)
        self.assertEqual(draw1, draw2)
        
        # Prob = 1.0 must always be True; Prob = 0.0 must always be False
        self.assertTrue(get_deterministic_allotment(ipo_test, seed, 1.0))
        self.assertFalse(get_deterministic_allotment(ipo_test, seed, 0.0))

    def test_macro_filter_calibration_audit(self):
        """Verify the exact reason why Strategy B matched Strategy A under raw 0.50 threshold."""
        df_macro = pd.read_csv(self.macro_audit_file)
        self.assertEqual(len(df_macro), 148)
        
        # Raw 0.50 threshold accepted 100% of candidate IPOs due to positive training base rate
        self.assertTrue((df_macro['passed_raw_050'] == True).all())
        
        # Calibrated validation median threshold actively discriminates
        pass_calib = df_macro['passed_calibrated'].sum()
        fail_calib = (~df_macro['passed_calibrated']).sum()
        self.assertEqual(pass_calib, 59)
        self.assertEqual(fail_calib, 89)

    def test_capital_conservation_in_shared_ledger(self):
        """Verify available_cash + blocked_cash == total_portfolio_val on every event."""
        df_ledger = pd.read_csv(self.ledger_file)
        diff = (df_ledger['available_cash'] + df_ledger['blocked_cash']) - df_ledger['total_portfolio_val']
        self.assertTrue((diff.abs() < 0.05).all())
        self.assertTrue((df_ledger['available_cash'] >= 0.0).all())
        self.assertTrue((df_ledger['blocked_cash'] >= 0.0).all())

    def test_unallotted_applications_zero_pnl(self):
        """Verify unallotted applications produce exactly zero trading PnL and 100% capital return."""
        df_ledger = pd.read_csv(self.ledger_file)
        unblocks = df_ledger[df_ledger['event_type'] == 'UNBLOCK_REFUND']
        self.assertGreater(len(unblocks), 0)
        self.assertTrue((unblocks['net_pnl_inr'] == 0.0).all())
        self.assertTrue((unblocks['net_return_pct'] == 0.0).all())

    def test_drawdown_bounds_and_validity(self):
        """Verify maximum drawdown percentages are bounded between 0% and 100%."""
        df_perf = pd.read_csv(self.perf_file)
        self.assertTrue((df_perf['max_drawdown_pct'] >= 0.0).all())
        self.assertTrue((df_perf['max_drawdown_pct'] <= 100.0).all())
        strat_f = df_perf[df_perf['strategy'] == 'Strategy_F_No_Application'].iloc[0]
        self.assertEqual(strat_f['max_drawdown_pct'], 0.0)
        self.assertEqual(strat_f['net_profit_total'], 0.0)

    def test_sensitivity_matrix_completeness_and_reconciliation(self):
        """Verify 180 sensitivity evaluations and zero reconciliation diff across all runs."""
        df_sens = pd.read_csv(self.sens_file)
        # 5 strategies x 4 allotment probs x 3 slippages x 3 costs = 180
        self.assertEqual(len(df_sens), 180)
        self.assertTrue((df_sens['reconciliation_diff'] == 0.0).all())

    def test_target_isolation(self):
        """Verify that normalized pre-cutoff features do not contain realized listing returns."""
        df_norm = pd.read_csv('data/processed/step_7d_normalized_features.csv')
        prohibited = ['target_listing_open_return_pct', 'target_listing_close_return_pct', 'listing_open_inr']
        for p in prohibited:
            self.assertNotIn(p, df_norm.columns)

if __name__ == '__main__':
    unittest.main()
