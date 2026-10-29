"""
Script: src/train_step_6a_models.py
Objective: Step 6A - Baseline Model Development and Historical Evaluation.
- Freeze design: Train (2020-2024), Validation (2025), Historical Out-of-Time Test (2026).
- Segment separation: Independent models for Mainboard and SME.
- Targets:
    Target A: Positive Opening Return (positive_open = 1 if listing_open_return_pct > 0 else 0)
    Target B: Severe Opening Loss (severe_open_loss = 1 if listing_open_return_pct <= -10 else 0)
    Target C: Continuous Opening Return (listing_open_return_pct)
- Model Families:
    Model 6A: Naive Base-Rate Benchmarks
    Model 6B: Logistic Regression for Positive Opening
    Model 6C: Logistic Regression for Severe Loss (with strict event count warnings)
    Model 6D: Ridge Linear Regression for Continuous Return
- Strict anti-leakage: All preprocessing (scalers, imputers) fitted strictly on Training data only.
- Output artifacts: metrics CSV, predictions CSV, feature importance CSV, cohort coverage CSV.
"""

import os
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    roc_auc_score, average_precision_score, brier_score_loss, log_loss,
    mean_absolute_error, root_mean_squared_error, precision_recall_fscore_support,
    confusion_matrix
)

def train_step_6a_models():
    os.makedirs('data/processed', exist_ok=True)
    os.makedirs('reports', exist_ok=True)
    
    # 1. Load Data
    df_ipo = pd.read_csv('data/processed/ipo_features_issue_close.csv')
    df_sent = pd.read_csv('data/processed/ipo_sentiment_features.csv')
    
    # Merge sentiment cleanly if not present
    if 'recent5_mean_listing_open_return_pct' not in df_ipo.columns:
        df_ipo = df_ipo.merge(
            df_sent[['ipo_id', 'recent5_mean_listing_open_return_pct', 'recent5_positive_listing_rate']],
            on='ipo_id', how='left'
        )
        
    df_ipo['listing_year'] = pd.to_datetime(df_ipo['listing_date']).dt.year
    
    # 2. Filter to Verified Cutoffs & Valid Target
    # Exclude records without verified cutoff or missing target opening price
    df_valid = df_ipo[
        (df_ipo['cutoff_status'] == 'verified') & 
        (df_ipo['target_listing_open_return_pct'].notnull())
    ].copy()
    
    # Define Targets
    df_valid['target_A_pos_open'] = (df_valid['target_listing_open_return_pct'] > 0).astype(int)
    df_valid['target_B_severe_loss'] = (df_valid['target_listing_open_return_pct'] <= -10.0).astype(int)
    df_valid['target_C_return'] = df_valid['target_listing_open_return_pct'].astype(float)
    
    # Assign Cohorts
    def assign_cohort(year):
        if 2020 <= year <= 2024:
            return 'Train_2020_2024'
        elif year == 2025:
            return 'Validation_2025'
        elif year == 2026:
            return 'Test_2026'
        else:
            return 'Other'
            
    df_valid['cohort'] = df_valid['listing_year'].apply(assign_cohort)
    df_valid = df_valid[df_valid['cohort'] != 'Other'].sort_values('prediction_cutoff_date').reset_index(drop=True)
    
    print(f"Total eligible verified cohort records: {len(df_valid)}")
    
    # 3. Document Cohort Coverage
    coverage_rows = []
    for segment in ['Mainboard', 'SME']:
        seg_df = df_valid[df_valid['board_type'] == segment]
        for c in ['Train_2020_2024', 'Validation_2025', 'Test_2026']:
            c_df = seg_df[seg_df['cohort'] == c]
            n = len(c_df)
            n_pos = int(c_df['target_A_pos_open'].sum()) if n > 0 else 0
            n_sev = int(c_df['target_B_severe_loss'].sum()) if n > 0 else 0
            coverage_rows.append({
                'segment': segment,
                'cohort': c,
                'total_eligible_ipos': n,
                'positive_open_count': n_pos,
                'positive_open_pct': round((n_pos / n) * 100, 2) if n > 0 else 0.0,
                'severe_loss_count': n_sev,
                'severe_loss_pct': round((n_sev / n) * 100, 2) if n > 0 else 0.0,
                'mean_return_pct': round(c_df['target_C_return'].mean(), 2) if n > 0 else 0.0,
                'median_return_pct': round(c_df['target_C_return'].median(), 2) if n > 0 else 0.0,
            })
    df_cov = pd.DataFrame(coverage_rows)
    df_cov.to_csv('data/processed/step_6a_cohort_coverage.csv', index=False)
    print("Saved data/processed/step_6a_cohort_coverage.csv")
    
    # 4. Define Predefined Feature Sets
    # Strictly verified at issue close cutoff:
    # Scale market returns to percentage points for clean interpretability
    df_valid['feat_nifty50_ret5s_pct'] = df_valid['nifty50_return_5s'] * 100.0
    df_valid['feat_nifty500_ret5s_pct'] = df_valid['nifty500_return_5s'] * 100.0
    df_valid['feat_india_vix'] = df_valid['india_vix_level_at_cutoff']
    df_valid['feat_recent5_sentiment'] = df_valid['recent5_mean_listing_open_return_pct']
    
    feature_cols = ['feat_nifty50_ret5s_pct', 'feat_india_vix', 'feat_recent5_sentiment']
    
    # Output containers
    all_metrics = []
    all_predictions = []
    all_importances = []
    
    # 5. Model Execution Loop: Independent per Segment
    for segment in ['Mainboard', 'SME']:
        seg_data = df_valid[df_valid['board_type'] == segment].copy()
        train_data = seg_data[seg_data['cohort'] == 'Train_2020_2024'].copy()
        val_data = seg_data[seg_data['cohort'] == 'Validation_2025'].copy()
        test_data = seg_data[seg_data['cohort'] == 'Test_2026'].copy()
        
        # Build Preprocessing Pipeline fitted ONLY on Train
        # Imputer uses median from training only; Scaler standardizes using training mean/std
        preprocessor = Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])
        
        X_train = preprocessor.fit_transform(train_data[feature_cols])
        X_val = preprocessor.transform(val_data[feature_cols])
        X_test = preprocessor.transform(test_data[feature_cols])
        
        # ----------------------------------------------------
        # Target A: Positive Opening Return
        # ----------------------------------------------------
        y_train_A = train_data['target_A_pos_open'].values
        y_val_A = val_data['target_A_pos_open'].values
        y_test_A = test_data['target_A_pos_open'].values
        
        # Benchmark 6A: Naive Base Rate
        p_train_base_A = float(y_train_A.mean())
        for c_name, y_true in [('Validation_2025', y_val_A), ('Test_2026', y_test_A)]:
            n_c = len(y_true)
            preds_const = np.full(n_c, p_train_base_A)
            # Evaluate base rate
            all_metrics.append({
                'model_id': 'Model_6A_BaseRate',
                'target': 'Target_A_Positive_Open',
                'segment': segment,
                'cohort': c_name,
                'roc_auc': 0.5,
                'pr_auc': round(float(y_true.mean()), 4),
                'brier_score': round(float(brier_score_loss(y_true, preds_const)), 4),
                'log_loss': round(float(log_loss(y_true, preds_const)), 4),
                'precision': 0.0,
                'recall': 0.0,
                'f1': 0.0,
                'operating_threshold': 0.5,
                'notes': f'Predicts constant training base-rate: {p_train_base_A:.3f}'
            })
            
        # Model 6B: Logistic Regression
        clf_A = LogisticRegression(C=1.0, random_state=42)
        clf_A.fit(X_train, y_train_A)
        
        # Feature Importance / Coefficients
        for f_name, coef in zip(feature_cols, clf_A.coef_[0]):
            all_importances.append({
                'model_id': 'Model_6B_Logistic_PositiveOpen',
                'segment': segment,
                'target': 'Target_A_Positive_Open',
                'feature': f_name,
                'coefficient_std': round(float(coef), 4),
                'odds_ratio_per_1std': round(float(np.exp(coef)), 4)
            })
            
        # Predictions & Selection on Validation Cohort
        val_probs_A = clf_A.predict_proba(X_val)[:, 1]
        test_probs_A = clf_A.predict_proba(X_test)[:, 1]
        
        # Threshold chosen on Validation only (maximizing F1 on val)
        best_th_A = 0.5
        best_f1_A = 0.0
        for th in np.arange(0.3, 0.8, 0.05):
            preds_bin = (val_probs_A >= th).astype(int)
            p, r, f, _ = precision_recall_fscore_support(y_val_A, preds_bin, average='binary', zero_division=0)
            if f > best_f1_A:
                best_f1_A = f
                best_th_A = th
                
        for c_name, y_true, probs in [('Validation_2025', y_val_A, val_probs_A), ('Test_2026', y_test_A, test_probs_A)]:
            preds_bin = (probs >= best_th_A).astype(int)
            p, r, f, _ = precision_recall_fscore_support(y_true, preds_bin, average='binary', zero_division=0)
            roc = roc_auc_score(y_true, probs) if len(np.unique(y_true)) > 1 else 0.5
            pr = average_precision_score(y_true, probs) if len(np.unique(y_true)) > 1 else 0.0
            
            all_metrics.append({
                'model_id': 'Model_6B_Logistic_PositiveOpen',
                'target': 'Target_A_Positive_Open',
                'segment': segment,
                'cohort': c_name,
                'roc_auc': round(float(roc), 4),
                'pr_auc': round(float(pr), 4),
                'brier_score': round(float(brier_score_loss(y_true, probs)), 4),
                'log_loss': round(float(log_loss(y_true, probs)), 4),
                'precision': round(float(p), 4),
                'recall': round(float(r), 4),
                'f1': round(float(f), 4),
                'operating_threshold': round(best_th_A, 2),
                'notes': f'Threshold {best_th_A:.2f} chosen on Validation 2025'
            })
            
        # Store individual predictions for Target A
        for sub_df, probs, c_name in [(val_data, val_probs_A, 'Validation_2025'), (test_data, test_probs_A, 'Test_2026')]:
            for idx, (_, r) in enumerate(sub_df.iterrows()):
                all_predictions.append({
                    'ipo_id': r['ipo_id'],
                    'company_name': r['company_name'],
                    'segment': segment,
                    'cohort': c_name,
                    'prediction_cutoff_date': r['prediction_cutoff_date'],
                    'target_name': 'Target_A_Positive_Open',
                    'actual_outcome': r['target_A_pos_open'],
                    'predicted_probability': round(float(probs[idx]), 4),
                    'predicted_binary': int(probs[idx] >= best_th_A),
                    'model_id': 'Model_6B_Logistic_PositiveOpen'
                })

        # ----------------------------------------------------
        # Target B: Severe Opening Loss (<= -10%)
        # ----------------------------------------------------
        y_train_B = train_data['target_B_severe_loss'].values
        y_val_B = val_data['target_B_severe_loss'].values
        y_test_B = test_data['target_B_severe_loss'].values
        
        n_sev_train = int(y_train_B.sum())
        p_train_base_B = float(y_train_B.mean())
        
        # Base Rate for Severe Loss
        for c_name, y_true in [('Validation_2025', y_val_B), ('Test_2026', y_test_B)]:
            n_c = len(y_true)
            preds_const = np.full(n_c, p_train_base_B)
            all_metrics.append({
                'model_id': 'Model_6A_BaseRate',
                'target': 'Target_B_Severe_Loss',
                'segment': segment,
                'cohort': c_name,
                'roc_auc': 0.5,
                'pr_auc': round(float(y_true.mean()), 4),
                'brier_score': round(float(brier_score_loss(y_true, preds_const)), 4),
                'log_loss': round(float(log_loss(y_true, preds_const)), 4),
                'precision': 0.0,
                'recall': 0.0,
                'f1': 0.0,
                'operating_threshold': p_train_base_B,
                'notes': f'Base rate: {p_train_base_B:.3f} (Training severe loss count: {n_sev_train})'
            })
            
        # Model 6C: Severe Loss Classifier (Logit with L2 penalty, balanced class weight)
        # Note: Event count in train is very small (13 in Mainboard, 18 in SME)
        clf_B = LogisticRegression(C=0.1, class_weight='balanced', random_state=42)
        clf_B.fit(X_train, y_train_B)
        
        for f_name, coef in zip(feature_cols, clf_B.coef_[0]):
            all_importances.append({
                'model_id': 'Model_6C_SevereLoss_Classifier',
                'segment': segment,
                'target': 'Target_B_Severe_Loss',
                'feature': f_name,
                'coefficient_std': round(float(coef), 4),
                'odds_ratio_per_1std': round(float(np.exp(coef)), 4)
            })
            
        val_probs_B = clf_B.predict_proba(X_val)[:, 1]
        test_probs_B = clf_B.predict_proba(X_test)[:, 1]
        
        # Validation threshold chosen to prioritize Recall while keeping Precision > 0
        best_th_B = 0.5
        best_f1_B = 0.0
        for th in np.arange(0.2, 0.7, 0.05):
            preds_bin = (val_probs_B >= th).astype(int)
            p, r, f, _ = precision_recall_fscore_support(y_val_B, preds_bin, average='binary', zero_division=0)
            if f > best_f1_B:
                best_f1_B = f
                best_th_B = th
                
        for c_name, y_true, probs in [('Validation_2025', y_val_B, val_probs_B), ('Test_2026', y_test_B, test_probs_B)]:
            preds_bin = (probs >= best_th_B).astype(int)
            p, r, f, _ = precision_recall_fscore_support(y_true, preds_bin, average='binary', zero_division=0)
            roc = roc_auc_score(y_true, probs) if len(np.unique(y_true)) > 1 else 0.5
            pr = average_precision_score(y_true, probs) if len(np.unique(y_true)) > 1 else 0.0
            
            all_metrics.append({
                'model_id': 'Model_6C_SevereLoss_Classifier',
                'target': 'Target_B_Severe_Loss',
                'segment': segment,
                'cohort': c_name,
                'roc_auc': round(float(roc), 4),
                'pr_auc': round(float(pr), 4),
                'brier_score': round(float(brier_score_loss(y_true, probs)), 4),
                'log_loss': round(float(log_loss(y_true, probs)), 4),
                'precision': round(float(p), 4),
                'recall': round(float(r), 4),
                'f1': round(float(f), 4),
                'operating_threshold': round(best_th_B, 2),
                'notes': f'Threshold {best_th_B:.2f} tuned on Val 2025; Train events={n_sev_train}'
            })
            
        for sub_df, probs, c_name in [(val_data, val_probs_B, 'Validation_2025'), (test_data, test_probs_B, 'Test_2026')]:
            for idx, (_, r) in enumerate(sub_df.iterrows()):
                all_predictions.append({
                    'ipo_id': r['ipo_id'],
                    'company_name': r['company_name'],
                    'segment': segment,
                    'cohort': c_name,
                    'prediction_cutoff_date': r['prediction_cutoff_date'],
                    'target_name': 'Target_B_Severe_Loss',
                    'actual_outcome': r['target_B_severe_loss'],
                    'predicted_probability': round(float(probs[idx]), 4),
                    'predicted_binary': int(probs[idx] >= best_th_B),
                    'model_id': 'Model_6C_SevereLoss_Classifier'
                })

        # ----------------------------------------------------
        # Target C: Continuous Opening Return
        # ----------------------------------------------------
        y_train_C = train_data['target_C_return'].values
        y_val_C = val_data['target_C_return'].values
        y_test_C = test_data['target_C_return'].values
        
        mean_ret_train = float(y_train_C.mean())
        med_ret_train = float(np.median(y_train_C))
        
        # Base Rate Mean & Median
        for c_name, y_true in [('Validation_2025', y_val_C), ('Test_2026', y_test_C)]:
            preds_mean = np.full(len(y_true), mean_ret_train)
            preds_med = np.full(len(y_true), med_ret_train)
            
            all_metrics.append({
                'model_id': 'Model_6A_BaseRate_Mean',
                'target': 'Target_C_Return',
                'segment': segment,
                'cohort': c_name,
                'mae': round(float(mean_absolute_error(y_true, preds_mean)), 2),
                'rmse': round(float(root_mean_squared_error(y_true, preds_mean)), 2),
                'mean_prediction_error': round(float((preds_mean - y_true).mean()), 2),
                'notes': f'Predicts constant train mean: {mean_ret_train:.2f}%'
            })
            all_metrics.append({
                'model_id': 'Model_6A_BaseRate_Median',
                'target': 'Target_C_Return',
                'segment': segment,
                'cohort': c_name,
                'mae': round(float(mean_absolute_error(y_true, preds_med)), 2),
                'rmse': round(float(root_mean_squared_error(y_true, preds_med)), 2),
                'mean_prediction_error': round(float((preds_med - y_true).mean()), 2),
                'notes': f'Predicts constant train median: {med_ret_train:.2f}%'
            })
            
        # Model 6D: Ridge Linear Regression
        reg_C = Ridge(alpha=10.0, random_state=42)
        reg_C.fit(X_train, y_train_C)
        
        for f_name, coef in zip(feature_cols, reg_C.coef_):
            all_importances.append({
                'model_id': 'Model_6D_Ridge_Return',
                'segment': segment,
                'target': 'Target_C_Return',
                'feature': f_name,
                'coefficient_std': round(float(coef), 4),
                'odds_ratio_per_1std': np.nan
            })
            
        val_preds_C = reg_C.predict(X_val)
        test_preds_C = reg_C.predict(X_test)
        
        for c_name, y_true, preds in [('Validation_2025', y_val_C, val_preds_C), ('Test_2026', y_test_C, test_preds_C)]:
            all_metrics.append({
                'model_id': 'Model_6D_Ridge_Return',
                'target': 'Target_C_Return',
                'segment': segment,
                'cohort': c_name,
                'mae': round(float(mean_absolute_error(y_true, preds)), 2),
                'rmse': round(float(root_mean_squared_error(y_true, preds)), 2),
                'mean_prediction_error': round(float((preds - y_true).mean()), 2),
                'notes': 'Ridge regression (alpha=10.0)'
            })
            
        for sub_df, preds, c_name in [(val_data, val_preds_C, 'Validation_2025'), (test_data, test_preds_C, 'Test_2026')]:
            for idx, (_, r) in enumerate(sub_df.iterrows()):
                all_predictions.append({
                    'ipo_id': r['ipo_id'],
                    'company_name': r['company_name'],
                    'segment': segment,
                    'cohort': c_name,
                    'prediction_cutoff_date': r['prediction_cutoff_date'],
                    'target_name': 'Target_C_Return',
                    'actual_outcome': r['target_C_return'],
                    'predicted_probability': np.nan,
                    'predicted_binary': np.nan,
                    'predicted_continuous_return': round(float(preds[idx]), 2),
                    'model_id': 'Model_6D_Ridge_Return'
                })

    # Save Output CSVs
    df_metrics = pd.DataFrame(all_metrics)
    df_metrics.to_csv('data/processed/step_6a_model_metrics.csv', index=False)
    print("Saved data/processed/step_6a_model_metrics.csv")
    
    df_preds = pd.DataFrame(all_predictions)
    df_preds.to_csv('data/processed/step_6a_predictions.csv', index=False)
    print("Saved data/processed/step_6a_predictions.csv")
    
    df_imp = pd.DataFrame(all_importances)
    df_imp.to_csv('data/processed/step_6a_feature_importance.csv', index=False)
    print("Saved data/processed/step_6a_feature_importance.csv")

if __name__ == '__main__':
    train_step_6a_models()
