import pandas as pd

df_cm = pd.read_csv('data/processed/step_6a1_confusion_matrices.csv')
print("=== Confusion Matrices ===")
for _, r in df_cm.iterrows():
    print(f"{r['model_id']} | {r['target']} | {r['segment']} | {r['cohort']} | N={r['total_evaluated']} | TN={r['true_negatives']}, FP={r['false_positives']}, FN={r['false_negatives']}, TP={r['true_positives']} | ActPos={r['actual_positive_count']}, PredPos={r['predicted_positive_count']}")

df_rec = pd.read_csv('data/processed/step_6a1_recalculated_metrics.csv')
print("\n=== Recalculated Metrics (Audited) ===")
for _, r in df_rec.iterrows():
    if 'Target_A' in str(r['target']):
        print(f"[{r['target']}] {r['segment']} | {r['cohort']} | {r['model_id']} | Acc={r['accuracy']}, Prec={r['precision']}, Rec={r['recall']}, F1={r['f1']}, Brier={r['brier_score']}, PR={r['pr_auc_average_precision']}")
    elif 'Target_B' in str(r['target']):
        print(f"[{r['target']}] {r['segment']} | {r['cohort']} | {r['model_id']} | Acc={r['accuracy']}, Prec={r['precision']}, Rec={r['recall']}, F1={r['f1']}, ROC={r['roc_auc']}, PR={r['pr_auc_average_precision']}")
    elif 'Target_C' in str(r['target']):
        print(f"[{r['target']}] {r['segment']} | {r['cohort']} | {r['model_id']} | MAE={r['mae']}, RMSE={r['rmse']}, Bias={r['mean_prediction_error']}")
