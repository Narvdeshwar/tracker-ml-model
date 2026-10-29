"""
Test suite for Step 6A.1: Model Metrics Integrity Audit.
"""

import unittest
import pandas as pd
import numpy as np

class TestStep6A1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df_recalc = pd.read_csv('data/processed/step_6a1_recalculated_metrics.csv')
        cls.df_cm = pd.read_csv('data/processed/step_6a1_confusion_matrices.csv')
        cls.df_preds = pd.read_csv('data/processed/step_6a_predictions.csv')

    def test_confusion_matrix_arithmetic(self):
        # TN + FP + FN + TP must strictly equal total_evaluated
        for _, r in self.df_cm.iterrows():
            total = r['true_negatives'] + r['false_positives'] + r['false_negatives'] + r['true_positives']
            self.assertEqual(total, r['total_evaluated'])
            self.assertEqual(r['true_positives'] + r['false_negatives'], r['actual_positive_count'])
            self.assertEqual(r['true_positives'] + r['false_positives'], r['predicted_positive_count'])

    def test_base_rate_audited_f1_reconciliation(self):
        # Model_6A_BaseRate_Audited at threshold 0.50 predicts all positive for Target A
        # Therefore, TP = actual_positives, FP = actual_negatives, FN = 0
        base_A = self.df_cm[(self.df_cm['model_id'] == 'Model_6A_BaseRate_Audited') & (self.df_cm['target'] == 'Target_A_Positive_Open')]
        for _, r in base_A.iterrows():
            self.assertEqual(r['false_negatives'], 0)
            self.assertEqual(r['true_positives'], r['actual_positive_count'])
            # F1 must be > 0.70
            rec_row = self.df_recalc[
                (self.df_recalc['model_id'] == 'Model_6A_BaseRate_Audited') & 
                (self.df_recalc['target'] == 'Target_A_Positive_Open') &
                (self.df_recalc['segment'] == r['segment']) &
                (self.df_recalc['cohort'] == r['cohort'])
            ].iloc[0]
            self.assertGreater(rec_row['f1'], 0.70)
            self.assertEqual(rec_row['recall'], 1.0)

    def test_no_probabilities_outside_unit_interval(self):
        # All probabilities must be in [0, 1]
        probs = self.df_preds['predicted_probability'].dropna()
        self.assertTrue((probs >= 0.0).all())
        self.assertTrue((probs <= 1.0).all())

    def test_ridge_regression_reproducibility(self):
        # Check MAE for Ridge on Mainboard Test_2026 matches 25.08
        r = self.df_recalc[
            (self.df_recalc['model_id'] == 'Model_6D_Ridge_Return') & 
            (self.df_recalc['segment'] == 'Mainboard') & 
            (self.df_recalc['cohort'] == 'Test_2026')
        ].iloc[0]
        self.assertEqual(r['mae'], 25.08)

if __name__ == '__main__':
    unittest.main()
