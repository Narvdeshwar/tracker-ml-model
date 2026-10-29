"""
Script: src/run_step_7c_experiment.py
Objective: Step 7C - Rigorous chronological incremental-value experiment.
Compares:
  - Model A: Baseline Macro Features (Nifty 50 5s return, India VIX, Trailing Sentiment)
  - Model B: Macro Features + Fundamentals (feat_price_band_spread_pct, feat_issue_priced_at_cap, feat_is_fixed_price_issue)
  - Model C: Fundamentals Only (Ablation diagnostic)
Evaluates separately:
  - Mainboard Positive-Opening Classification
  - SME Positive-Opening Classification
  - Severe Negative Listing-Opening Classification (Loss <= -10%)
Outputs:
  - data/processed/step_7c_model_comparison.csv
  - data/processed/step_7c_predictions.csv
"""

import os
import json
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss, log_loss

def run_experiment():
    print("Running Step 7C Incremental-Value Model Experiment...")
    os.makedirs('data/processed', exist_ok=True)
    
    # 1. Load Data
    df_f = pd.read_csv('data/processed/ipo_features_issue_close.csv')
    df_fund = pd.read_csv('data/processed/step_7c_normalized_fundamentals.csv')
    
    merged = pd.merge(df_f, df_fund[['ipo_id', 'feat_has_price_band', 'feat_price_band_spread_pct', 'feat_issue_priced_at_cap', 'feat_is_fixed_price_issue', 'temporal_eligibility']], on='ipo_id')
    
    # Filter to strictly leakage-safe, cutoff-verified cohort with valid fundamentals
    eligible = merged[merged['temporal_eligibility'] == True].copy()
    eligible['listing_year'] = pd.to_datetime(eligible['listing_date']).dt.year
    
    # Filter rows with non-null target return and features
    eligible = eligible.dropna(subset=['target_listing_open_return_pct', 'nifty50_return_5s', 'india_vix_level_at_cutoff', 'recent5_positive_listing_rate']).copy()
    
    # Impute missing spread/cap using training medians strictly fitted on training set
    train_mask = eligible['listing_year'] <= 2024
    val_mask = eligible['listing_year'] == 2025
    test_mask = eligible['listing_year'] == 2026
    
    # Target definitions
    eligible['target_positive_open'] = (eligible['target_listing_open_return_pct'] > 0).astype(int)
    eligible['target_severe_loss'] = (eligible['target_listing_open_return_pct'] <= -10.0).astype(int)
    
    # Feature sets
    macro_cols = ['nifty50_return_5s', 'india_vix_level_at_cutoff', 'recent5_positive_listing_rate']
    fund_cols = ['feat_price_band_spread_pct', 'feat_issue_priced_at_cap', 'feat_is_fixed_price_issue']
    combined_cols = macro_cols + fund_cols
    
    results = []
    all_preds = []
    
    for board in ['Mainboard', 'SME']:
        df_b = eligible[eligible['board_type'] == board].copy()
        
        tr = df_b[df_b['listing_year'] <= 2024].copy()
        va = df_b[df_b['listing_year'] == 2025].copy()
        te = df_b[df_b['listing_year'] == 2026].copy()
        
        # Fit median imputer on training set only
        med_spread = tr['feat_price_band_spread_pct'].median()
        tr['feat_price_band_spread_pct'] = tr['feat_price_band_spread_pct'].fillna(med_spread)
        va['feat_price_band_spread_pct'] = va['feat_price_band_spread_pct'].fillna(med_spread)
        te['feat_price_band_spread_pct'] = te['feat_price_band_spread_pct'].fillna(med_spread)
        
        for col in ['feat_issue_priced_at_cap', 'feat_is_fixed_price_issue']:
            mode_val = tr[col].mode()[0] if not tr[col].empty else 1.0
            tr[col] = tr[col].fillna(mode_val)
            va[col] = va[col].fillna(mode_val)
            te[col] = te[col].fillna(mode_val)
            
        # Standardize features using training mean & std strictly
        for feat in combined_cols:
            mean = tr[feat].mean()
            std = tr[feat].std()
            if std == 0 or pd.isna(std):
                std = 1.0
            tr[f'z_{feat}'] = (tr[feat] - mean) / std
            va[f'z_{feat}'] = (va[feat] - mean) / std
            te[f'z_{feat}'] = (te[feat] - mean) / std
            
        z_macro = [f'z_{f}' for f in macro_cols]
        z_fund = [f'z_{f}' for f in fund_cols]
        z_comb = [f'z_{f}' for f in combined_cols]
        
        # 1. Target: Positive Opening Return
        y_tr = tr['target_positive_open']
        y_va = va['target_positive_open']
        y_te = te['target_positive_open']
        
        base_rate_te = float(y_te.mean())
        
        models_spec = [
            ('Model_A_Macro_Baseline', z_macro),
            ('Model_B_Macro_Plus_Fundamentals', z_comb),
            ('Model_C_Fundamentals_Only', z_fund)
        ]
        
        for m_name, feat_set in models_spec:
            clf = LogisticRegression(C=1.0, solver='lbfgs', random_state=42)
            clf.fit(tr[feat_set], y_tr)
            
            p_val = clf.predict_proba(va[feat_set])[:, 1]
            p_te = clf.predict_proba(te[feat_set])[:, 1]
            
            roc_val = float(roc_auc_score(y_va, p_val))
            pr_val = float(average_precision_score(y_va, p_val))
            
            roc_te = float(roc_auc_score(y_te, p_te))
            pr_te = float(average_precision_score(y_te, p_te))
            brier_te = float(brier_score_loss(y_te, p_te))
            logloss_te = float(log_loss(y_te, p_te))
            
            # Record predictions
            for idx_t, p_val_i in enumerate(p_te):
                all_preds.append({
                    'ipo_id': te.iloc[idx_t]['ipo_id'],
                    'board_type': board,
                    'model_name': m_name,
                    'target_type': 'positive_open',
                    'actual_outcome': int(y_te.iloc[idx_t]),
                    'predicted_probability': round(float(p_val_i), 4)
                })
                
            results.append({
                'board_type': board,
                'target': 'Positive_Opening_Return',
                'model_name': m_name,
                'features_used': ', '.join(feat_set),
                'train_sample_size': len(tr),
                'validation_sample_size': len(va),
                'test_sample_size': len(te),
                'test_base_rate': round(base_rate_te, 4),
                'val_roc_auc': round(roc_val, 4),
                'val_pr_auc': round(pr_val, 4),
                'test_roc_auc': round(roc_te, 4),
                'test_pr_auc': round(pr_te, 4),
                'test_pr_auc_lift': round(pr_te - base_rate_te, 4),
                'test_brier_score': round(brier_te, 4),
                'test_log_loss': round(logloss_te, 4)
            })
            
        # 2. Target: Severe Negative Opening Return (Loss <= -10%)
        y_tr_sev = tr['target_severe_loss']
        y_va_sev = va['target_severe_loss']
        y_te_sev = te['target_severe_loss']
        sev_base_rate = float(y_te_sev.mean())
        
        for m_name, feat_set in models_spec:
            clf_sev = LogisticRegression(C=1.0, class_weight='balanced', solver='lbfgs', random_state=42)
            clf_sev.fit(tr[feat_set], y_tr_sev)
            
            p_te_sev = clf_sev.predict_proba(te[feat_set])[:, 1]
            try:
                roc_sev = float(roc_auc_score(y_te_sev, p_te_sev))
                pr_sev = float(average_precision_score(y_te_sev, p_te_sev))
            except Exception:
                roc_sev, pr_sev = 0.5, sev_base_rate
                
            brier_sev = float(brier_score_loss(y_te_sev, p_te_sev))
            
            results.append({
                'board_type': board,
                'target': 'Severe_Loss_Risk',
                'model_name': m_name,
                'features_used': ', '.join(feat_set),
                'train_sample_size': len(tr),
                'validation_sample_size': len(va),
                'test_sample_size': len(te),
                'test_base_rate': round(sev_base_rate, 4),
                'val_roc_auc': np.nan,
                'val_pr_auc': np.nan,
                'test_roc_auc': round(roc_sev, 4),
                'test_pr_auc': round(pr_sev, 4),
                'test_pr_auc_lift': round(pr_sev - sev_base_rate, 4),
                'test_brier_score': round(brier_sev, 4),
                'test_log_loss': np.nan
            })
            
    df_res = pd.DataFrame(results)
    out_res = 'data/processed/step_7c_model_comparison.csv'
    df_res.to_csv(out_res, index=False)
    print(f"Saved model comparison results to {out_res}")
    
    df_preds_out = pd.DataFrame(all_preds)
    out_preds = 'data/processed/step_7c_predictions.csv'
    df_preds_out.to_csv(out_preds, index=False)
    print(f"Saved experiment predictions to {out_preds}")
    
    return df_res

if __name__ == '__main__':
    run_experiment()
