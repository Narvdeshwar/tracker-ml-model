import pandas as pd

df_m = pd.read_csv('data/processed/step_6a_model_metrics.csv')
print("=== Step 6A Model Metrics Summary ===")
for _, r in df_m.iterrows():
    tgt = str(r['target'])
    seg = r['segment']
    coh = r['cohort']
    mid = r['model_id']
    if 'Target_A' in tgt:
        print(f"[{tgt}] {seg} | {coh} | {mid} | ROC={r['roc_auc']}, PR={r['pr_auc']}, Brier={r['brier_score']}, F1={r['f1']}")
    elif 'Target_B' in tgt:
        print(f"[{tgt}] {seg} | {coh} | {mid} | ROC={r['roc_auc']}, PR={r['pr_auc']}, Rec={r['recall']}, Prec={r['precision']}")
    elif 'Target_C' in tgt:
        print(f"[{tgt}] {seg} | {coh} | {mid} | MAE={r['mae']}, RMSE={r['rmse']}, Bias={r['mean_prediction_error']}")

df_imp = pd.read_csv('data/processed/step_6a_feature_importance.csv')
print("\n=== Feature Coefficients (Standardized) ===")
for _, r in df_imp.iterrows():
    print(f"{r['segment']} | {r['target']} | {r['feature']}: std_coef={r['coefficient_std']}, OR_per_std={r['odds_ratio_per_1std']}")
