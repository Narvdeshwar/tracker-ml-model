# Step 6A.1 Report: Model Metrics Integrity Audit

## 1. Executive Summary & Audit Decision

**DECISION: METRICS VERIFIED WITH CORRECTIONS**

The independent metric audit of Step 6A has resolved the exact cause of the base-rate F1 discrepancy, independently recalculated all confusion matrices, and verified metric reproducibility across all 365 validation and holdout test IPOs:
- **Output Audit Datasets Created**:
  1. [`data/processed/step_6a1_recalculated_metrics.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_6a1_recalculated_metrics.csv): Full reconciliation of original vs recalculated metrics across all 24 model/segment/cohort configurations.
  2. [`data/processed/step_6a1_confusion_matrices.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_6a1_confusion_matrices.csv): Exact counts of True Positives (TP), False Positives (FP), False Negatives (FN), and True Negatives (TN).
- **Automated Audit Test Suite**: [`tests/test_step_6a1.py`](file:///d:/personal/st-ai/ipo-record/tests/test_step_6a1.py) (All 4 tests passed).

---

## 2. Investigation of the Base-Rate F1 Inconsistency

### Root Cause Identified
In `src/train_step_6a_models.py` (lines 147–161 and 244–258), the dictionary for `Model_6A_BaseRate` evaluated `brier_score_loss` and `log_loss` dynamically, but **hardcoded classification metrics (`'precision': 0.0, 'recall': 0.0, 'f1': 0.0`)** because the naive model was treated purely as a continuous probability benchmark rather than being passed through an explicit decision threshold binary evaluation function.

### The True Base-Rate Benchmark Under Standard Threshold $\tau = 0.50$
Because the historical training base rates exceed 0.50:
- Mainboard Training Base Rate: **$75.2\%$** ($> 0.50$)
- SME Training Base Rate: **$83.4\%$** ($> 0.50$)

Under standard binary classification threshold $\tau = 0.50$, **the base-rate benchmark predicts $\hat{y} = 1$ for 100% of IPOs**.
Thus, the base-rate benchmark produces:
$$\text{False Negatives} = 0, \quad \text{True Positives} = N_{\text{actual positive}}, \quad \text{Recall} = \mathbf{100.0\%}$$

### Corrected Reconciliation Table (Target A: Positive Opening Return)

| Segment | Cohort | Model | Threshold | TP | FP | FN | TN | Actual Positives | Precision | Recall | F1 Score | Brier Score | PR-AUC (Average Precision) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mainboard** | Validation (2025) | Base Rate (Audited) | 0.50 | 69 | 30 | 0 | 0 | 69 | 69.7% | 100.0% | **0.8214** | 0.2142 | 0.6970 |
| **Mainboard** | Validation (2025) | Logistic Reg (6B) | 0.50 | 69 | 30 | 0 | 0 | 69 | 69.7% | 100.0% | **0.8214** | 0.2184 | 0.7255 |
| **Mainboard** | Test (2026) | Base Rate (Audited) | 0.50 | 60 | 32 | 0 | 0 | 60 | 65.2% | 100.0% | **0.7895** | 0.2368 | 0.6522 |
| **Mainboard** | Test (2026) | Logistic Reg (6B) | 0.50 | 60 | 32 | 0 | 0 | 60 | 65.2% | 100.0% | **0.7895** | 0.2386 | 0.6631 |
| **SME Board** | Validation (2025) | Base Rate (Audited) | 0.50 | 73 | 43 | 0 | 0 | 73 | 62.9% | 100.0% | **0.7725** | 0.2753 | 0.6293 |
| **SME Board** | Validation (2025) | Logistic Reg (6B) | 0.50 | 73 | 43 | 0 | 0 | 73 | 62.9% | 100.0% | **0.7725** | 0.2695 | 0.6308 |
| **SME Board** | Test (2026) | Base Rate (Audited) | 0.50 | 34 | 24 | 0 | 0 | 34 | 58.6% | 100.0% | **0.7391** | 0.3041 | 0.5862 |
| **SME Board** | Test (2026) | Logistic Reg (6B) | 0.50 | 34 | 24 | 0 | 0 | 34 | 58.6% | 100.0% | **0.7391** | 0.2894 | **0.7097** |

---

## 3. Crucial Strategic Discovery: Why F1 Scores Were Identical

Notice the striking finding above: **at the naive threshold $\tau = 0.50$, Logistic Regression Model 6B produced the exact same confusion matrix as the naive base rate** (100% predicted positive)!
- In both Mainboard and SME, the predicted probabilities from Model 6B ranged from **$0.596$ to $0.850$** (never dropping below $0.50$).
- Therefore, at threshold $\tau = 0.50$, Model 6B simply predicted positive for every single IPO, matching the base rate's F1 score of **$0.7391$** (SME) and **$0.7895$** (Mainboard).

### What Truly Distinguishes the SME Model?
The real difference between the baseline and Model 6B is **Ranking and Probability Discrimination**, not thresholded F1 at 0.50:
1. **Average Precision (PR-AUC)**: The SME Model 6B achieves **$0.7097$** vs. the base-rate benchmark of **$0.5862$** (a **$+12.35$ percentage point lift** in ranking positive listings).
2. **ROC-AUC**: **$0.6103$** vs **$0.5000$** for base rate.
3. **Brier Score**: **$0.2894$** vs **$0.3041$** (better calibrated probabilities).

---

## 4. Verification of Severe Loss (Target B) and Return Models (Target C)

### Target B: Severe Loss ($\le -10\%$)
- In Model 6C, class balancing shifted probabilities upwards ($0.28$ to $0.62$).
- At the validation-selected thresholds ($\tau = 0.30$ for Mainboard, $\tau = 0.20$ for SME), the model flagged nearly all IPOs (91 out of 92 in Mainboard, 58 out of 58 in SME).
- This achieved 100% recall artificially with catastrophic precision (8.8% Mainboard, 20.7% SME), yielding ROC-AUC of ~0.35 (worse than coin flip).
- **Audit Verdict**: Confirmed experimental and unready.

### Target C: Continuous Return
- Recalculated MAE and RMSE confirmed the reported figures exactly:
  - Mainboard: Naive Median MAE = **18.40%** vs. Ridge MAE = **25.08%** (Ridge Mean Overprediction Bias = $+15.57\%$).
  - SME Board: Naive Median MAE = **30.23%** vs. Ridge MAE = **37.30%** (Ridge Mean Overprediction Bias = $+22.50\%$).
- **Audit Verdict**: Confirmed that naive historical median strictly dominates ordinary linear regression.

---

## 5. Summary of Required Modifications to Project Documentation

1. **Base-Rate Benchmarks Corrected**: Update project records to reflect that under standard threshold 0.50, the constant base-rate benchmark achieves an F1 score of $0.7895$ (Mainboard) and $0.7391$ (SME) by predicting all positive, rather than $0.000$.
2. **Evaluation Metrics Hierarchy**:
   - For Target A, rely on **PR-AUC (Average Precision)** and **Brier Score** rather than F1 at 0.50.
   - For Target B, severe loss models require asymmetric cost-matrix optimization or quantile survival modeling rather than standard logistic class weighting.
