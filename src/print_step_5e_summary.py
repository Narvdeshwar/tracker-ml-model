import pandas as pd

df_diag = pd.read_csv('data/processed/step_5e_regression_diagnostics.csv')
print("=== Regression Diagnostics Details ===")
for _, r in df_diag.iterrows():
    print(f"{r['label']}: beta={r['logistic_beta']}, p={r['p_value']}, raw_OR={r['raw_odds_ratio']}, increment='{r['interpretable_increment']}', interpretable_OR={r['interpretable_odds_ratio']} (95% CI: [{r['interpretable_ci_low']}, {r['interpretable_ci_high']}])")

df_miss = pd.read_csv('data/processed/step_5e_cutoff_missingness.csv')
print("\n=== Cutoff Missingness Comparison ===")
for _, r in df_miss[df_miss['dimension'] == 'Board'].iterrows():
    print(f"Board: {r['group']} | Total={r['total_ipos']}, Verified={r['verified_cutoffs']}, Unresolved={r['unresolved_cutoffs']} ({r['unresolved_pct']}%)")
    print(f"   Verified Pos%={r['verified_positive_close_rate']}%, Unresolved Pos%={r['unresolved_positive_close_rate']}%")
    print(f"   Verified Severe Loss%={r['verified_severe_loss_rate']}%, Unresolved Severe Loss%={r['unresolved_severe_loss_rate']}%")
    print(f"   Outcome diff p-val={r['p_value_outcome_difference']}")

df_split = pd.read_csv('data/processed/step_5e_temporal_split_counts.csv')
print("\n=== Temporal Split Counts ===")
for _, r in df_split.iterrows():
    print(f"{r['split_name']} [{r['board']}]: Total={r['total_cohort_ipos']}, Verified={r['verified_cutoff_ipos']}, PosOpen%={r['verified_positive_open_pct']}%, SevereLossOpen%={r['verified_severe_loss_open_pct']}% (N_severe={r['verified_severe_loss_open_count']})")
