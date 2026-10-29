"""
Script: src/run_step_7d_experiment.py
Objective: Step 7D - Historical IPO Valuation, Financial Quality, Scale, and Issue Structure Incremental-Value Experiment.
Compares:
  - Model A: Macro Baseline (Nifty 50 5s return, India VIX, Trailing Sentiment)
  - Model B: Macro + Step 7C Issue Structure (Spread %, Priced at Cap, Fixed Price)
  - Model C: Issue Structure Only (Ablation Diagnostic)
  - Model D: Macro + Scale/Valuation (Log Issue Price, Price Band Spread)
  - Model E: Unified Enriched Model (Macro + Scale + Structure)
Evaluates separately:
  - Mainboard Positive-Opening Classification
  - Mainboard Severe-Loss Classification (Loss <= -10%)
  - SME Positive-Opening Classification
  - SME Severe-Loss Classification (Loss <= -10%)
Outputs:
  - data/processed/step_7d_model_comparison.csv
  - data/processed/step_7d_predictions.csv
  - data/processed/step_7d_feature_coefficients.csv
"""

import os
import json
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss, log_loss

def run_step_7d_experiment():
    print("Running Step 7D Incremental-Value Model Experiment...")
    os.makedirs('data/processed', exist_ok=True)
    
    # 1. Load Data
    df_f = pd.read_csv('data/processed/ipo_features_issue_close.csv')
    df_fund = pd.read_csv('data/processed/step_7d_normalized_features.csv')
    
    # Merge required columns
    cols_to_merge = [
        'ipo_id', 'log_issue_price', 'feat_has_price_band', 
        'feat_price_band_spread_pct', 'feat_issue_priced_at_cap', 
        'feat_is_fixed_price_issue', 'temporal_eligibility'
    ]
    merged = pd.merge(df_f, df_fund[cols_to_merge], on='ipo_id')
    
    # Filter strictly to leakage-safe, cutoff-verified cohort with valid pricing data
    eligible = merged[merged['temporal_eligibility'] == True].copy()
    eligible['listing_year'] = pd.to_datetime(eligible['listing_date']).dt.year
    
    # Ensure non-null realized target returns and baseline macro features
    req_cols = ['target_listing_open_return_pct', 'nifty50_return_5s', 'india_vix_level_at_cutoff', 'recent5_positive_listing_rate']
    eligible = eligible.dropna(subset=req_cols).copy()
    
    # Targets
    eligible['target_positive_open'] = (eligible['target_listing_open_return_pct'] > 0).astype(int)
    eligible['target_severe_loss'] = (eligible['target_listing_open_return_pct'] <= -10.0).astype(int)
    
    # Model Feature Sets
    macro_cols = ['nifty50_return_5s', 'india_vix_level_at_cutoff', 'recent5_positive_listing_rate']
    structure_cols = ['feat_price_band_spread_pct', 'feat_issue_priced_at_cap', 'feat_is_fixed_price_issue']
    scale_cols = ['log_issue_price', 'feat_price_band_spread_pct']
    unified_cols = ['nifty50_return_5s', 'india_vix_level_at_cutoff', 'recent5_positive_listing_rate', 'log_issue_price', 'feat_price_band_spread_pct', 'feat_is_fixed_price_issue']
    
    all_possible_features = list(set(macro_cols + structure_cols + scale_cols + unified_cols))
    
    results = []
    all_preds = []
    coef_records = []
    
    for board in ['Mainboard', 'SME']:
        df_b = eligible[eligible['board_type'] == board].copy()
        
        tr = df_b[df_b['listing_year'] <= 2024].copy()
        va = df_b[df_b['listing_year'] == 2025].copy()
        te = df_b[df_b['listing_year'] == 2026].copy()
        
        print(f"\nCohort for {board}: Train={len(tr)}, Val={len(va)}, Test={len(te)}")
        
        # Training-only imputation
        med_spread = tr['feat_price_band_spread_pct'].median()
        med_log_price = tr['log_issue_price'].median()
        
        for d in [tr, va, te]:
            d['feat_price_band_spread_pct'] = d['feat_price_band_spread_pct'].fillna(med_spread)
            d['log_issue_price'] = d['log_issue_price'].fillna(med_log_price)
            for flag_col in ['feat_issue_priced_at_cap', 'feat_is_fixed_price_issue']:
                mode_val = tr[flag_col].mode()[0] if not tr[flag_col].empty else 1.0
                d[flag_col] = d[flag_col].fillna(mode_val)
                
        # Standardize strictly using training parameters
        for feat in all_possible_features:
            mean = tr[feat].mean()
            std = tr[feat].std()
            if std == 0 or pd.isna(std):
                std = 1.0
            tr[f'z_{feat}'] = (tr[feat] - mean) / std
            va[f'z_{feat}'] = (va[feat] - mean) / std
            te[f'z_{feat}'] = (te[feat] - mean) / std
            
        # Model specifications with standardized names
        model_defs = {
            'Model_A_Macro_Baseline': [f'z_{f}' for f in macro_cols],
            'Model_B_Macro_Plus_Structure': [f'z_{f}' for f in macro_cols + structure_cols],
            'Model_C_Structure_Only': [f'z_{f}' for f in structure_cols],
            'Model_D_Macro_Plus_Scale': [f'z_{f}' for f in macro_cols + scale_cols],
            'Model_E_Unified_Enriched': [f'z_{f}' for f in unified_cols]
        }
        
        targets = [
            ('Positive_Opening_Return', 'target_positive_open', False),
            ('Severe_Loss_Risk', 'target_severe_loss', True)
        ]
        
        for target_label, target_col, is_balanced in targets:
            y_tr = tr[target_col]
            y_va = va[target_col]
            y_te = te[target_col]
            
            base_rate_tr = float(y_tr.mean())
            base_rate_va = float(y_va.mean())
            base_rate_te = float(y_te.mean())
            
            for m_name, feat_set in model_defs.items():
                if is_balanced:
                    clf = LogisticRegression(C=1.0, class_weight='balanced', solver='lbfgs', random_state=42)
                else:
                    clf = LogisticRegression(C=1.0, solver='lbfgs', random_state=42)
                    
                clf.fit(tr[feat_set], y_tr)
                
                # Coefficients
                for f_name, coef in zip(feat_set, clf.coef_[0]):
                    coef_records.append({
                        'board_type': board,
                        'target': target_label,
                        'model_name': m_name,
                        'feature': f_name.replace('z_', ''),
                        'coefficient': round(float(coef), 4),
                        'intercept': round(float(clf.intercept_[0]), 4)
                    })
                    
                # Predictions
                p_va = clf.predict_proba(va[feat_set])[:, 1]
                p_te = clf.predict_proba(te[feat_set])[:, 1]
                
                # Validation metrics
                try:
                    roc_va = float(roc_auc_score(y_va, p_va))
                    pr_va = float(average_precision_score(y_va, p_va))
                except Exception:
                    roc_va, pr_va = 0.5, base_rate_va
                brier_va = float(brier_score_loss(y_va, p_va))
                
                # Test metrics
                try:
                    roc_te = float(roc_auc_score(y_te, p_te))
                    pr_te = float(average_precision_score(y_te, p_te))
                except Exception:
                    roc_te, pr_te = 0.5, base_rate_te
                brier_te = float(brier_score_loss(y_te, p_te))
                logloss_te = float(log_loss(y_te, p_te))
                
                # Save individual predictions on test cohort
                for idx_i, p_val in enumerate(p_te):
                    all_preds.append({
                        'ipo_id': te.iloc[idx_i]['ipo_id'],
                        'company_name': te.iloc[idx_i]['company_name'],
                        'board_type': board,
                        'listing_date': str(te.iloc[idx_i]['listing_date'])[:10],
                        'model_name': m_name,
                        'target_type': target_label,
                        'actual_return_pct': round(float(te.iloc[idx_i]['target_listing_open_return_pct']), 2),
                        'actual_outcome': int(y_te.iloc[idx_i]),
                        'predicted_probability': round(float(p_val), 4)
                    })
                    
                results.append({
                    'board_type': board,
                    'target': target_label,
                    'model_name': m_name,
                    'features_used': ', '.join([f.replace('z_', '') for f in feat_set]),
                    'feature_count': len(feat_set),
                    'train_sample_size': len(tr),
                    'train_base_rate': round(base_rate_tr, 4),
                    'val_sample_size': len(va),
                    'val_base_rate': round(base_rate_va, 4),
                    'val_roc_auc': round(roc_va, 4),
                    'val_pr_auc': round(pr_va, 4),
                    'val_brier_score': round(brier_va, 4),
                    'test_sample_size': len(te),
                    'test_base_rate': round(base_rate_te, 4),
                    'test_roc_auc': round(roc_te, 4),
                    'test_pr_auc': round(pr_te, 4),
                    'test_pr_auc_lift': round(pr_te - base_rate_te, 4),
                    'test_brier_score': round(brier_te, 4),
                    'test_log_loss': round(logloss_te, 4)
                })
                
    # Output 1: Model Comparison Table
    df_results = pd.DataFrame(results)
    out_res = 'data/processed/step_7d_model_comparison.csv'
    df_results.to_csv(out_res, index=False)
    print(f"Saved Step 7D model comparison results to {out_res} ({len(df_results)} rows)")
    
    # Output 2: Predictions Table
    df_preds = pd.DataFrame(all_preds)
    out_preds = 'data/processed/step_7d_predictions.csv'
    df_preds.to_csv(out_preds, index=False)
    print(f"Saved Step 7D predictions to {out_preds} ({len(df_preds)} rows)")
    
    # Output 3: Coefficients Table
    df_coef = pd.DataFrame(coef_records)
    out_coef = 'data/processed/step_7d_feature_coefficients.csv'
    df_coef.to_csv(out_coef, index=False)
    print(f"Saved Step 7D feature coefficients to {out_coef} ({len(df_coef)} rows)")
    
    print("\nStep 7D Model Experiment Completed Successfully.")
    return df_results, df_preds, df_coef

if __name__ == '__main__':
    run_step_7d_experiment()
