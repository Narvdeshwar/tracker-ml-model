import pandas as pd

df_d = pd.read_csv('data/processed/step_5d_downside_risk.csv')
print("=== Downside Risk Metrics ===")
for _, r in df_d.iterrows():
    print(f"{r['segment']} ({r['target']}): Total={r['total_obs']}, Prob Loss={r['prob_loss_pct']}%, Loss<-10%={r['prob_loss_gt_10pct']}%, Loss<-20%={r['prob_loss_gt_20pct']}%, p5={r['p5_worst_pct']}%, Worst={r['worst_observed_loss_pct']}%, Mean Loss={r['mean_loss_when_negative_pct']}%")

df_m = pd.read_csv('data/processed/step_5d_market_analysis.csv')
print("\n=== Market & Sentiment Regressions ===")
for _, r in df_m.iterrows():
    print(f"{r['feature_label']}: N={r['sample_size']}, OLS Coef={r['ols_coefficient']} (pval={r['ols_pvalue']}), R2={r['ols_r_squared']}, Logit OR={r['logit_odds_ratio']} (pval={r['logit_pvalue']})")
