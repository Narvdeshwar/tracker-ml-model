"""
Script: src/run_step_6a1_audit.py
Objective: Step 6A.1 - Model Metrics Integrity Audit.
- Audit Base-Rate F1 inconsistency: trace root cause (hardcoded 0.0 in manual dict construction).
- Recalculate full confusion matrix and metrics for:
    1. Base-Rate Benchmarks (Model 6A)
    2. Positive-Opening Classifier (Model 6B)
    3. Severe-Loss Classifier (Model 6C)
    4. Continuous-Return Regressors (Model 6D & Median Baseline)
- Produce step_6a1_recalculated_metrics.csv, step_6a1_confusion_matrices.csv.
"""

import os
import pandas as pd
import numpy as np
from sklearn.metrics import (
    roc_auc_score, average_precision_score, brier_score_loss, log_loss,
    mean_absolute_error, root_mean_squared_error, precision_recall_fscore_support,
    confusion_matrix, accuracy_score
)

def run_step_6a1_audit():
    os.makedirs('data/processed', exist_ok=True)
    os.makedirs('reports', exist_ok=True)
    
    # 1. Load Step 6A Outputs
    df_preds = pd.read_csv('data/processed/step_6a_predictions.csv')
    df_orig_metrics = pd.read_csv('data/processed/step_6a_model_metrics.csv')
    df_cov = pd.read_csv('data/processed/step_6a_cohort_coverage.csv')
    df_ipo = pd.read_csv('data/processed/ipo_features_issue_close.csv')
    
    # Compute true training base rates from training data
    df_valid = df_ipo[
        (df_ipo['cutoff_status'] == 'verified') & 
        (df_ipo['target_listing_open_return_pct'].notnull())
    ].copy()
    df_valid['listing_year'] = pd.to_datetime(df_valid['listing_date']).dt.year
    df_train = df_valid[(df_valid['listing_year'] >= 2020) & (df_valid['listing_year'] <= 2024)]
    
    train_base_rates = {}
    for seg in ['Mainboard', 'SME']:
        seg_tr = df_train[df_train['board_type'] == seg]
        train_base_rates[seg] = {
            'pos_open': float((seg_tr['target_listing_open_return_pct'] > 0).mean()),
            'severe_loss': float((seg_tr['target_listing_open_return_pct'] <= -10.0).mean()),
            'mean_return': float(seg_tr['target_listing_open_return_pct'].mean()),
            'median_return': float(seg_tr['target_listing_open_return_pct'].median())
        }
        
    print("Training base rates:", train_base_rates)
    
    # 2. Recalculate Confusion Matrices and Metrics
    recalculated_metrics = []
    confusion_matrices = []
    
    # A. Audit Classification Models
    # Group predictions by model_id, target_name, segment, cohort
    for (model_id, target_name, segment, cohort), grp in df_preds.groupby(['model_id', 'target_name', 'segment', 'cohort']):
        if 'Return' in target_name:
            continue
            
        y_true = grp['actual_outcome'].values.astype(int)
        y_prob = grp['predicted_probability'].values.astype(float)
        y_pred = grp['predicted_binary'].values.astype(int)
        
        # Calculate confusion matrix
        # [[TN, FP], [FN, TP]]
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
        
        prec, rec, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='binary', zero_division=0)
        acc = accuracy_score(y_true, y_pred)
        
        roc = roc_auc_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else 0.5
        pr_auc = average_precision_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else 0.0
        brier = brier_score_loss(y_true, y_prob)
        # Numerical safeguard for log loss: clip probabilities to [1e-15, 1 - 1e-15]
        prob_clipped = np.clip(y_prob, 1e-15, 1 - 1e-15)
        ll = log_loss(y_true, prob_clipped)
        
        # Determine operating threshold
        # Find threshold where y_pred was generated
        min_p_pos = y_prob[y_pred == 1].min() if (y_pred == 1).any() else 1.0
        max_p_neg = y_prob[y_pred == 0].max() if (y_pred == 0).any() else 0.0
        
        confusion_matrices.append({
            'model_id': model_id,
            'target': target_name,
            'segment': segment,
            'cohort': cohort,
            'total_evaluated': len(y_true),
            'true_negatives': int(tn),
            'false_positives': int(fp),
            'false_negatives': int(fn),
            'true_positives': int(tp),
            'actual_positive_count': int(y_true.sum()),
            'predicted_positive_count': int(y_pred.sum())
        })
        
        recalculated_metrics.append({
            'model_id': model_id,
            'target': target_name,
            'segment': segment,
            'cohort': cohort,
            'roc_auc': round(float(roc), 4),
            'pr_auc_average_precision': round(float(pr_auc), 4),
            'brier_score': round(float(brier), 4),
            'log_loss': round(float(ll), 4),
            'accuracy': round(float(acc), 4),
            'precision': round(float(prec), 4),
            'recall': round(float(rec), 4),
            'f1': round(float(f1), 4),
            'mae': np.nan,
            'rmse': np.nan,
            'mean_prediction_error': np.nan,
            'status': 'VERIFIED'
        })

    # B. Explicitly audit Model 6A Base-Rate Benchmarks under Standard Classification Threshold 0.50
    # Also evaluate under the Exact Base-Rate Probability
    for target_name, target_key, base_key in [
        ('Target_A_Positive_Open', 'target_A_pos_open', 'pos_open'),
        ('Target_B_Severe_Loss', 'target_B_severe_loss', 'severe_loss')
    ]:
        for segment in ['Mainboard', 'SME']:
            p_const = train_base_rates[segment][base_key]
            for cohort in ['Validation_2025', 'Test_2026']:
                # Filter predictions from that cohort
                sub_cohort = df_preds[(df_preds['segment'] == segment) & (df_preds['cohort'] == cohort) & (df_preds['target_name'] == target_name)]
                y_true = sub_cohort['actual_outcome'].values.astype(int)
                n = len(y_true)
                probs_const = np.full(n, p_const)
                
                # Evaluation under standard threshold 0.50
                preds_th50 = (probs_const >= 0.50).astype(int)
                cm50 = confusion_matrix(y_true, preds_th50, labels=[0, 1])
                tn50, fp50, fn50, tp50 = cm50.ravel()
                prec50, rec50, f150, _ = precision_recall_fscore_support(y_true, preds_th50, average='binary', zero_division=0)
                acc50 = accuracy_score(y_true, preds_th50)
                
                brier = brier_score_loss(y_true, probs_const)
                ll = log_loss(y_true, np.clip(probs_const, 1e-15, 1 - 1e-15))
                # For constant probabilities, ROC-AUC is undefined or 0.5; Average precision is baseline prevalence y_true.mean()
                pr_auc_val = float(y_true.mean())
                
                confusion_matrices.append({
                    'model_id': 'Model_6A_BaseRate_Audited',
                    'target': target_name,
                    'segment': segment,
                    'cohort': cohort,
                    'total_evaluated': n,
                    'true_negatives': int(tn50),
                    'false_positives': int(fp50),
                    'false_negatives': int(fn50),
                    'true_positives': int(tp50),
                    'actual_positive_count': int(y_true.sum()),
                    'predicted_positive_count': int(preds_th50.sum())
                })
                
                recalculated_metrics.append({
                    'model_id': 'Model_6A_BaseRate_Audited',
                    'target': target_name,
                    'segment': segment,
                    'cohort': cohort,
                    'roc_auc': 0.5,
                    'pr_auc_average_precision': round(pr_auc_val, 4),
                    'brier_score': round(float(brier), 4),
                    'log_loss': round(float(ll), 4),
                    'accuracy': round(float(acc50), 4),
                    'precision': round(float(prec50), 4),
                    'recall': round(float(rec50), 4),
                    'f1': round(float(f150), 4),
                    'mae': np.nan,
                    'rmse': np.nan,
                    'mean_prediction_error': np.nan,
                    'status': 'CORRECTED_BASE_RATE_METRICS'
                })

    # C. Audit Continuous Return Models (Model 6D & Median Baseline)
    p_ret = df_preds[df_preds['target_name'] == 'Target_C_Return']
    for (model_id, segment, cohort), grp in p_ret.groupby(['model_id', 'segment', 'cohort']):
        y_true = grp['actual_outcome'].values.astype(float)
        y_pred = grp['predicted_continuous_return'].values.astype(float)
        mae = mean_absolute_error(y_true, y_pred)
        rmse = root_mean_squared_error(y_true, y_pred)
        bias = (y_pred - y_true).mean()
        
        recalculated_metrics.append({
            'model_id': model_id,
            'target': 'Target_C_Return',
            'segment': segment,
            'cohort': cohort,
            'roc_auc': np.nan,
            'pr_auc_average_precision': np.nan,
            'brier_score': np.nan,
            'log_loss': np.nan,
            'accuracy': np.nan,
            'precision': np.nan,
            'recall': np.nan,
            'f1': np.nan,
            'mae': round(float(mae), 2),
            'rmse': round(float(rmse), 2),
            'mean_prediction_error': round(float(bias), 2),
            'status': 'VERIFIED'
        })
        
    # Also evaluate Naive Median Baseline
    for segment in ['Mainboard', 'SME']:
        med_train = train_base_rates[segment]['median_return']
        for cohort in ['Validation_2025', 'Test_2026']:
            sub = p_ret[(p_ret['segment'] == segment) & (p_ret['cohort'] == cohort)]
            y_true = sub['actual_outcome'].values.astype(float)
            preds_med = np.full(len(y_true), med_train)
            mae = mean_absolute_error(y_true, preds_med)
            rmse = root_mean_squared_error(y_true, preds_med)
            bias = (preds_med - y_true).mean()
            
            recalculated_metrics.append({
                'model_id': 'Model_6A_BaseRate_Median_Audited',
                'target': 'Target_C_Return',
                'segment': segment,
                'cohort': cohort,
                'roc_auc': np.nan,
                'pr_auc_average_precision': np.nan,
                'brier_score': np.nan,
                'log_loss': np.nan,
                'accuracy': np.nan,
                'precision': np.nan,
                'recall': np.nan,
                'f1': np.nan,
                'mae': round(float(mae), 2),
                'rmse': round(float(rmse), 2),
                'mean_prediction_error': round(float(bias), 2),
                'status': 'VERIFIED'
            })

    # Save outputs
    df_recalc = pd.DataFrame(recalculated_metrics)
    df_recalc.to_csv('data/processed/step_6a1_recalculated_metrics.csv', index=False)
    print("Saved data/processed/step_6a1_recalculated_metrics.csv")
    
    df_cm = pd.DataFrame(confusion_matrices)
    df_cm.to_csv('data/processed/step_6a1_confusion_matrices.csv', index=False)
    print("Saved data/processed/step_6a1_confusion_matrices.csv")

if __name__ == '__main__':
    run_step_6a1_audit()
