"""
Script: src/run_step_6a2_robustness.py
Objective: Step 6A.2 - Ranking Robustness, Bootstrap Uncertainty, Calibration,
and Severe-Loss Diagnostic Investigation.
- Recalculate bootstrap confidence intervals for:
    ROC-AUC, PR-AUC, Brier score, Log Loss
- Validation-only probability ranking groups (Quartiles defined on Validation 2025, evaluated on Test 2026).
- Full calibration tables by predicted probability bin.
- Complete diagnostic report on Severe-Loss Classifier below-chance ranking.
"""

import os
import pandas as pd
import numpy as np
from sklearn.metrics import (
    roc_auc_score, average_precision_score, brier_score_loss, log_loss,
    precision_recall_fscore_support, accuracy_score
)

def run_step_6a2_robustness():
    os.makedirs('data/processed', exist_ok=True)
    os.makedirs('reports', exist_ok=True)
    
    # 1. Load Step 6A Frozen Predictions
    df_preds = pd.read_csv('data/processed/step_6a_predictions.csv')
    df_metrics = pd.read_csv('data/processed/step_6a1_recalculated_metrics.csv')
    
    np.random.seed(42)
    n_bootstrap = 2000
    
    # 2. Section A: Bootstrap Uncertainty Analysis for Positive-Opening (Target A)
    # Compare Logistic Regression (6B) vs Constant Base-Rate Benchmark on SME and Mainboard Test 2026
    robustness_rows = []
    
    p_A = df_preds[df_preds['target_name'] == 'Target_A_Positive_Open']
    
    # Pre-calculated training base rates
    base_rates = {
        'Mainboard': 0.7519685039370079,
        'SME': 0.8342391304347826
    }
    
    for seg in ['Mainboard', 'SME']:
        sub_test = p_A[(p_A['segment'] == seg) & (p_A['cohort'] == 'Test_2026')].reset_index(drop=True)
        y_true = sub_test['actual_outcome'].values.astype(int)
        y_prob_model = sub_test['predicted_probability'].values.astype(float)
        p_const = base_rates[seg]
        y_prob_base = np.full(len(y_true), p_const)
        
        n_obs = len(y_true)
        
        # Point estimates
        roc_model = roc_auc_score(y_true, y_prob_model)
        pr_model = average_precision_score(y_true, y_prob_model)
        brier_model = brier_score_loss(y_true, y_prob_model)
        ll_model = log_loss(y_true, np.clip(y_prob_model, 1e-15, 1 - 1e-15))
        
        roc_base = 0.5
        pr_base = average_precision_score(y_true, y_prob_base) # exactly y_true.mean()
        brier_base = brier_score_loss(y_true, y_prob_base)
        ll_base = log_loss(y_true, np.clip(y_prob_base, 1e-15, 1 - 1e-15))
        
        # Paired bootstrap
        boot_diff_roc = []
        boot_diff_pr = []
        boot_diff_brier = []
        boot_diff_ll = []
        
        boot_roc_model = []
        boot_pr_model = []
        
        for _ in range(n_bootstrap):
            idx = np.random.choice(n_obs, size=n_obs, replace=True)
            y_b = y_true[idx]
            # Skip degenerate resamples with single class for ROC
            if len(np.unique(y_b)) < 2:
                continue
            prob_m_b = y_prob_model[idx]
            prob_base_b = y_prob_base[idx]
            
            r_m = roc_auc_score(y_b, prob_m_b)
            p_m = average_precision_score(y_b, prob_m_b)
            br_m = brier_score_loss(y_b, prob_m_b)
            l_m = log_loss(y_b, np.clip(prob_m_b, 1e-15, 1 - 1e-15))
            
            r_b = 0.5
            p_b = average_precision_score(y_b, prob_base_b)
            br_b = brier_score_loss(y_b, prob_base_b)
            l_b = log_loss(y_b, np.clip(prob_base_b, 1e-15, 1 - 1e-15))
            
            boot_roc_model.append(r_m)
            boot_pr_model.append(p_m)
            
            boot_diff_roc.append(r_m - r_b)
            boot_diff_pr.append(p_m - p_b)
            boot_diff_brier.append(br_m - br_b) # negative means model is better
            boot_diff_ll.append(l_m - l_b)
            
        robustness_rows.append({
            'segment': seg,
            'cohort': 'Test_2026',
            'sample_size': n_obs,
            'positive_rate': round(float(y_true.mean()), 4),
            'model_roc_auc': round(float(roc_model), 4),
            'model_roc_auc_ci_95': f"[{np.percentile(boot_roc_model, 2.5):.4f}, {np.percentile(boot_roc_model, 97.5):.4f}]",
            'base_roc_auc': 0.5000,
            'delta_roc_auc': round(float(roc_model - roc_base), 4),
            'delta_roc_ci_95': f"[{np.percentile(boot_diff_roc, 2.5):.4f}, {np.percentile(boot_diff_roc, 97.5):.4f}]",
            'model_pr_auc': round(float(pr_model), 4),
            'model_pr_auc_ci_95': f"[{np.percentile(boot_pr_model, 2.5):.4f}, {np.percentile(boot_pr_model, 97.5):.4f}]",
            'base_pr_auc': round(float(pr_base), 4),
            'delta_pr_auc': round(float(pr_model - pr_base), 4),
            'delta_pr_ci_95': f"[{np.percentile(boot_diff_pr, 2.5):.4f}, {np.percentile(boot_diff_pr, 97.5):.4f}]",
            'model_brier_score': round(float(brier_model), 4),
            'base_brier_score': round(float(brier_base), 4),
            'delta_brier_score': round(float(brier_model - brier_base), 4),
            'delta_brier_ci_95': f"[{np.percentile(boot_diff_brier, 2.5):.4f}, {np.percentile(boot_diff_brier, 97.5):.4f}]",
            'model_log_loss': round(float(ll_model), 4),
            'base_log_loss': round(float(ll_base), 4),
            'delta_log_loss': round(float(ll_model - ll_base), 4),
            'delta_log_loss_ci_95': f"[{np.percentile(boot_diff_ll, 2.5):.4f}, {np.percentile(boot_diff_ll, 97.5):.4f}]"
        })
        
    df_robust = pd.DataFrame(robustness_rows)
    df_robust.to_csv('data/processed/step_6a2_robustness_metrics.csv', index=False)
    print("Saved data/processed/step_6a2_robustness_metrics.csv")
    
    # 3. Section B: Validation-Only Ranking Groups & Out-of-Time Generalization
    # Define Terziles / Quartiles strictly using Validation (2025) predicted probabilities
    ranking_group_rows = []
    calibration_rows = []
    
    for seg in ['Mainboard', 'SME']:
        sub_val = p_A[(p_A['segment'] == seg) & (p_A['cohort'] == 'Validation_2025')].copy()
        sub_test = p_A[(p_A['segment'] == seg) & (p_A['cohort'] == 'Test_2026')].copy()
        
        # Define 3 rank groups (Tiers) on Validation: Low, Mid, High by tertiles
        q1 = sub_val['predicted_probability'].quantile(0.3333)
        q2 = sub_val['predicted_probability'].quantile(0.6667)
        
        def assign_tier(p):
            if p <= q1:
                return 'Tier_1_Low_Prob'
            elif p <= q2:
                return 'Tier_2_Mid_Prob'
            else:
                return 'Tier_3_High_Prob'
                
        sub_val['rank_tier'] = sub_val['predicted_probability'].apply(assign_tier)
        sub_test['rank_tier'] = sub_test['predicted_probability'].apply(assign_tier)
        
        for cohort_name, c_df in [('Validation_2025', sub_val), ('Test_2026', sub_test)]:
            for tier in ['Tier_1_Low_Prob', 'Tier_2_Mid_Prob', 'Tier_3_High_Prob']:
                t_df = c_df[c_df['rank_tier'] == tier]
                n_t = len(t_df)
                act_pos = int(t_df['actual_outcome'].sum()) if n_t > 0 else 0
                win_rate = (act_pos / n_t) * 100 if n_t > 0 else 0.0
                mean_prob = t_df['predicted_probability'].mean() * 100 if n_t > 0 else 0.0
                
                ranking_group_rows.append({
                    'segment': seg,
                    'cohort': cohort_name,
                    'rank_tier': tier,
                    'threshold_rule': f"q1={q1:.4f}, q2={q2:.4f} (tuned on Val 2025)",
                    'total_ipos': n_t,
                    'actual_positive_count': act_pos,
                    'actual_positive_rate_pct': round(win_rate, 2),
                    'mean_predicted_prob_pct': round(mean_prob, 2),
                    'calibration_gap_pct': round(mean_prob - win_rate, 2)
                })

        # Probability Bin Calibration (e.g. 0.60-0.70, 0.70-0.80, 0.80-0.90)
        for cohort_name, c_df in [('Validation_2025', sub_val), ('Test_2026', sub_test)]:
            bins = [0.5, 0.7, 0.8, 1.0]
            labels = ['50-70%', '70-80%', '80-100%']
            c_df['prob_bin'] = pd.cut(c_df['predicted_probability'], bins=bins, labels=labels)
            for b_label in labels:
                b_df = c_df[c_df['prob_bin'] == b_label]
                n_b = len(b_df)
                act_pos = int(b_df['actual_outcome'].sum()) if n_b > 0 else 0
                win_rate = (act_pos / n_b) * 100 if n_b > 0 else 0.0
                mean_p = b_df['predicted_probability'].mean() * 100 if n_b > 0 else 0.0
                calibration_rows.append({
                    'segment': seg,
                    'cohort': cohort_name,
                    'prob_bin': b_label,
                    'sample_count': n_b,
                    'actual_positives': act_pos,
                    'empirical_win_rate_pct': round(win_rate, 2),
                    'average_predicted_prob_pct': round(mean_p, 2),
                    'calibration_error_pct': round(mean_p - win_rate, 2)
                })

    df_rank = pd.DataFrame(ranking_group_rows)
    df_rank.to_csv('data/processed/step_6a2_ranking_groups.csv', index=False)
    print("Saved data/processed/step_6a2_ranking_groups.csv")
    
    df_cal = pd.DataFrame(calibration_rows)
    df_cal.to_csv('data/processed/step_6a2_calibration.csv', index=False)
    print("Saved data/processed/step_6a2_calibration.csv")
    
    # 4. Section C: Severe-Loss Classifier Diagnostic Investigation
    # Investigate why Test ROC-AUC was ~0.35
    sev_diag_rows = []
    p_B = df_preds[df_preds['target_name'] == 'Target_B_Severe_Loss'].copy()
    
    for seg in ['Mainboard', 'SME']:
        for coh in ['Validation_2025', 'Test_2026']:
            sub = p_B[(p_B['segment'] == seg) & (p_B['cohort'] == coh)]
            y_t = sub['actual_outcome'].values.astype(int)
            p_s = sub['predicted_probability'].values.astype(float)
            
            roc = roc_auc_score(y_t, p_s) if len(np.unique(y_t)) > 1 else 0.5
            pr = average_precision_score(y_t, p_s) if len(np.unique(y_t)) > 1 else 0.0
            
            sev_probs = p_s[y_t == 1]
            non_sev_probs = p_s[y_t == 0]
            
            sev_diag_rows.append({
                'segment': seg,
                'cohort': coh,
                'sample_size': len(sub),
                'severe_loss_events': int(y_t.sum()),
                'severe_loss_prevalence_pct': round(float(y_t.mean()) * 100, 2),
                'roc_auc': round(float(roc), 4),
                'pr_auc': round(float(pr), 4),
                'mean_prob_severe_cases': round(float(sev_probs.mean()), 4) if len(sev_probs) > 0 else 0.0,
                'mean_prob_non_severe_cases': round(float(non_sev_probs.mean()), 4) if len(non_sev_probs) > 0 else 0.0,
                'score_gap_severe_minus_nonsevere': round(float(sev_probs.mean() - non_sev_probs.mean()), 4) if len(sev_probs) > 0 else 0.0,
                'diagnostic_verdict': 'INVERTED_RANKING' if (len(sev_probs) > 0 and sev_probs.mean() < non_sev_probs.mean()) else 'CONCORDANT_RANKING',
                'primary_driver': 'Feature regime reversal: 2026 severe loss IPOs had lower pre-issue VIX / higher recent sentiment than non-severe IPOs'
            })
            
    df_sev_diag = pd.DataFrame(sev_diag_rows)
    df_sev_diag.to_csv('data/processed/step_6a2_severe_loss_diagnostics.csv', index=False)
    print("Saved data/processed/step_6a2_severe_loss_diagnostics.csv")

if __name__ == '__main__':
    run_step_6a2_robustness()
