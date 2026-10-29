"""
Test suite for Step 6A: Baseline Model Development and Historical Evaluation.
"""

import unittest
import pandas as pd
import numpy as np

class TestStep6A(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df_metrics = pd.read_csv('data/processed/step_6a_model_metrics.csv')
        cls.df_preds = pd.read_csv('data/processed/step_6a_predictions.csv')
        cls.df_cov = pd.read_csv('data/processed/step_6a_cohort_coverage.csv')
        cls.df_imp = pd.read_csv('data/processed/step_6a_feature_importance.csv')
        cls.df_ipo = pd.read_csv('data/processed/ipo_features_issue_close.csv')

    def test_cohort_split_preservation(self):
        # Sum of total eligible IPOs across cohorts must equal 987 verified cutoffs
        total_eligible = self.df_cov['total_eligible_ipos'].sum()
        self.assertEqual(total_eligible, 987, f"Expected 987 verified IPOs, got {total_eligible}")

    def test_no_test_cohort_leakage_in_metrics(self):
        # Verify that all operating thresholds in test_2026 were chosen from Validation 2025
        test_metrics = self.df_metrics[self.df_metrics['cohort'] == 'Test_2026']
        val_metrics = self.df_metrics[self.df_metrics['cohort'] == 'Validation_2025']
        
        for model in ['Model_6B_Logistic_PositiveOpen', 'Model_6C_SevereLoss_Classifier']:
            for seg in ['Mainboard', 'SME']:
                val_th = val_metrics[(val_metrics['model_id'] == model) & (val_metrics['segment'] == seg)]['operating_threshold'].iloc[0]
                test_th = test_metrics[(test_metrics['model_id'] == model) & (test_metrics['segment'] == seg)]['operating_threshold'].iloc[0]
                self.assertEqual(val_th, test_th, f"Threshold discrepancy detected for {model} in {seg}")

    def test_predictions_completeness(self):
        # Validation has 215 records, Test has 150 records -> Total per target = 365
        preds_A = self.df_preds[self.df_preds['target_name'] == 'Target_A_Positive_Open']
        self.assertEqual(len(preds_A), 365)
        # Check probabilities within [0, 1]
        self.assertTrue((preds_A['predicted_probability'] >= 0.0).all())
        self.assertTrue((preds_A['predicted_probability'] <= 1.0).all())

    def test_model_families_present(self):
        models = self.df_metrics['model_id'].unique().tolist()
        self.assertIn('Model_6A_BaseRate', models)
        self.assertIn('Model_6B_Logistic_PositiveOpen', models)
        self.assertIn('Model_6C_SevereLoss_Classifier', models)
        self.assertIn('Model_6D_Ridge_Return', models)

    def test_severe_loss_event_accounting(self):
        # Mainboard severe loss events in train must equal 13
        mb_train = self.df_cov[(self.df_cov['segment'] == 'Mainboard') & (self.df_cov['cohort'] == 'Train_2020_2024')].iloc[0]
        self.assertEqual(mb_train['severe_loss_count'], 13)
        # SME severe loss events in train must equal 18
        sme_train = self.df_cov[(self.df_cov['segment'] == 'SME') & (self.df_cov['cohort'] == 'Train_2020_2024')].iloc[0]
        self.assertEqual(sme_train['severe_loss_count'], 18)

if __name__ == '__main__':
    unittest.main()
