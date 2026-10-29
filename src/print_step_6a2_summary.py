import pandas as pd

df_rob = pd.read_csv('data/processed/step_6a2_robustness_metrics.csv')
print("=== Step 6A.2 Robustness & Bootstrap Metrics ===")
for _, r in df_rob.iterrows():
    print(f"[{r['segment']}] N={r['sample_size']}, PosRate={r['positive_rate']:.1%}")
    print(f"   ROC-AUC: Model={r['model_roc_auc']} (95% CI: {r['model_roc_auc_ci_95']}) | Delta_ROC={r['delta_roc_auc']} (CI: {r['delta_roc_ci_95']})")
    print(f"   PR-AUC:  Model={r['model_pr_auc']} (95% CI: {r['model_pr_auc_ci_95']}) | Delta_PR={r['delta_pr_auc']} (CI: {r['delta_pr_ci_95']})")
    print(f"   Brier:   Model={r['model_brier_score']} vs Base={r['base_brier_score']} | Delta_Brier={r['delta_brier_score']} (CI: {r['delta_brier_ci_95']})")

df_rank = pd.read_csv('data/processed/step_6a2_ranking_groups.csv')
print("\n=== Validation-Defined Ranking Groups ===")
for _, r in df_rank.iterrows():
    print(f"{r['segment']} | {r['cohort']} | {r['rank_tier']}: N={r['total_ipos']}, ActPos%={r['actual_positive_rate_pct']}%, MeanProb%={r['mean_predicted_prob_pct']}%, Gap={r['calibration_gap_pct']}%")

df_sev = pd.read_csv('data/processed/step_6a2_severe_loss_diagnostics.csv')
print("\n=== Severe Loss Diagnostics ===")
for _, r in df_sev.iterrows():
    print(f"{r['segment']} | {r['cohort']}: N={r['sample_size']}, SevEvents={r['severe_loss_events']} ({r['severe_loss_prevalence_pct']}%) | ROC={r['roc_auc']}, PR={r['pr_auc']}")
    print(f"   SevMeanProb={r['mean_prob_severe_cases']}, NonSevMeanProb={r['mean_prob_non_severe_cases']} | Gap={r['score_gap_severe_minus_nonsevere']} -> {r['diagnostic_verdict']}")
