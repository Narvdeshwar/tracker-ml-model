import pandas as pd

df_b = pd.read_csv('data/processed/step_6a3_bootstrap_audit.csv')
print("=== Bootstrap Audit ===")
for _, r in df_b.iterrows():
    print(f"{r['metric']}: PointEst={r['point_estimate']}, BootMean={r['bootstrap_mean']}, CI_95=[{r['bootstrap_ci_95_low']}, {r['bootstrap_ci_95_high']}], ZeroExcluded={r['zero_excluded_in_ci']}, DegenerateSkipped={r['degenerate_resamples_skipped']}")

df_t = pd.read_csv('data/processed/step_6a3_tier_uncertainty.csv')
print("\n=== Small-Sample Tier Uncertainty (Wilson Intervals) ===")
for _, r in df_t.iterrows():
    print(f"{r['rank_tier']}: N={r['total_ipos']}, PosEvents={r['positive_open_count']}, WinRate={r['empirical_win_rate_pct']}%, Wilson_95=[{r['wilson_ci_95_low_pct']}%, {r['wilson_ci_95_high_pct']}%], PredProb={r['mean_predicted_prob_pct']}%, Gap={r['calibration_overconfidence_gap_pct']}%")

df_c = pd.read_csv('data/processed/step_6a3_cohort_comparison.csv')
print("\n=== Cohort Distribution Shift Audit ===")
for _, r in df_c.iterrows():
    print(f"[{r['segment']}] {r['cohort']}: N={r['total_verified_ipos']}, PosOpen%={r['positive_open_rate_pct']}%, SevLoss%={r['severe_loss_rate_pct']}%, MedRet={r['median_open_return_pct']}%, Nifty5s%={r['mean_nifty50_5s_pct']}%, VIX={r['mean_india_vix_level']}, Sent5%={r['mean_recent5_sentiment_pct']}%")
