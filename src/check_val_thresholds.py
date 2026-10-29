"""
Script: src/check_val_thresholds.py
Examines 2025 validation cohort predictions to tune thresholds strictly prior to 2026 test evaluation.
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression

df_f = pd.read_csv('data/processed/ipo_features_issue_close.csv')
df_fund = pd.read_csv('data/processed/step_7d_normalized_features.csv')
merged = pd.merge(df_f, df_fund[['ipo_id', 'log_issue_price', 'feat_price_band_spread_pct', 'feat_is_fixed_price_issue', 'temporal_eligibility']], on='ipo_id')
eligible = merged[merged['temporal_eligibility'] == True].copy()
eligible['listing_year'] = pd.to_datetime(eligible['listing_date']).dt.year
eligible = eligible.dropna(subset=['target_listing_open_return_pct', 'nifty50_return_5s', 'india_vix_level_at_cutoff', 'recent5_positive_listing_rate']).copy()

eligible['target_positive_open'] = (eligible['target_listing_open_return_pct'] > 0).astype(int)
eligible['target_severe_loss'] = (eligible['target_listing_open_return_pct'] <= -10.0).astype(int)

for board in ['Mainboard', 'SME']:
    print(f"\n==================== {board} ====================")
    df_b = eligible[eligible['board_type'] == board].copy()
    tr = df_b[df_b['listing_year'] <= 2024].copy()
    va = df_b[df_b['listing_year'] == 2025].copy()
    te = df_b[df_b['listing_year'] == 2026].copy()
    
    # Impute
    med_spread = tr['feat_price_band_spread_pct'].median()
    med_log_price = tr['log_issue_price'].median()
    for d in [tr, va, te]:
        d['feat_price_band_spread_pct'] = d['feat_price_band_spread_pct'].fillna(med_spread)
        d['log_issue_price'] = d['log_issue_price'].fillna(med_log_price)
        d['feat_is_fixed_price_issue'] = d['feat_is_fixed_price_issue'].fillna(0.0)
        
    feats = ['nifty50_return_5s', 'india_vix_level_at_cutoff', 'recent5_positive_listing_rate', 
             'log_issue_price', 'feat_price_band_spread_pct', 'feat_is_fixed_price_issue']
    for f in feats:
        m, s = tr[f].mean(), tr[f].std()
        if s == 0 or pd.isna(s): s = 1.0
        tr['z_'+f] = (tr[f] - m) / s
        va['z_'+f] = (va[f] - m) / s
        te['z_'+f] = (te[f] - m) / s
        
    macro_z = ['z_nifty50_return_5s', 'z_india_vix_level_at_cutoff', 'z_recent5_positive_listing_rate']
    structure_z = ['z_feat_price_band_spread_pct', 'z_feat_is_fixed_price_issue']
    scale_z = ['z_nifty50_return_5s', 'z_india_vix_level_at_cutoff', 'z_recent5_positive_listing_rate', 'z_log_issue_price', 'z_feat_price_band_spread_pct']
    unified_z = ['z_nifty50_return_5s', 'z_india_vix_level_at_cutoff', 'z_recent5_positive_listing_rate', 'z_log_issue_price', 'z_feat_price_band_spread_pct', 'z_feat_is_fixed_price_issue']
    
    # 1. Positive Opening Models
    # Mainboard best positive: Model C (structure only); SME best positive: Model D (macro + scale) or Model A (macro)
    clf_pos_mb = LogisticRegression(C=1.0, solver='lbfgs', random_state=42).fit(tr[structure_z], tr['target_positive_open'])
    clf_pos_sme = LogisticRegression(C=1.0, solver='lbfgs', random_state=42).fit(tr[scale_z], tr['target_positive_open'])
    
    # 2. Severe Loss Models
    clf_loss = LogisticRegression(C=1.0, class_weight='balanced', solver='lbfgs', random_state=42).fit(tr[unified_z], tr['target_severe_loss'])
    
    p_pos_va = clf_pos_mb.predict_proba(va[structure_z])[:, 1] if board == 'Mainboard' else clf_pos_sme.predict_proba(va[scale_z])[:, 1]
    p_loss_va = clf_loss.predict_proba(va[unified_z])[:, 1]
    
    print(f"2025 Val Size: {len(va)}")
    print(f"Predicted Positive Prob (Val): Mean={p_pos_va.mean():.4f}, 25%={np.percentile(p_pos_va, 25):.4f}, Median={np.percentile(p_pos_va, 50):.4f}, 75%={np.percentile(p_pos_va, 75):.4f}")
    print(f"Predicted Severe Loss Prob (Val): Mean={p_loss_va.mean():.4f}, 25%={np.percentile(p_loss_va, 25):.4f}, Median={np.percentile(p_loss_va, 50):.4f}, 75%={np.percentile(p_loss_va, 75):.4f}, 90%={np.percentile(p_loss_va, 90):.4f}")
    
    # Test precision across potential thresholds on validation
    for q in [50, 60, 70, 75]:
        th = np.percentile(p_pos_va, q)
        sel = va[p_pos_va >= th]
        win_rate = sel['target_positive_open'].mean() if len(sel) > 0 else 0
        print(f"  Positive Thresh (q={q}, th={th:.4f}): Selected={len(sel)}, Win Rate={win_rate:.4f}")
        
    for q_loss in [60, 70, 75, 80, 90]:
        th_l = np.percentile(p_loss_va, q_loss)
        sel_l = va[p_loss_va < th_l]
        sev_rate = sel_l['target_severe_loss'].mean() if len(sel_l) > 0 else 0
        print(f"  Risk Filter (reject >= q={q_loss}, th={th_l:.4f}): Remaining={len(sel_l)}, Severe Rate={sev_rate:.4f} (Base={va['target_severe_loss'].mean():.4f})")
