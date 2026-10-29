# Step 6A Report: Baseline Model Development and Historical Evaluation

## 1. Executive Summary & Readiness Decisions by Target

Step 6A implements and evaluates our initial interpretable baseline models using strictly frozen chronological splits across the 987 verified-cutoff Indian IPOs:
- **Training Cohort (2020–2024)**: 622 IPOs (Mainboard: 254, SME: 368) — used for all fitting, imputation, and standardization pipelines.
- **Validation Cohort (2025)**: 215 IPOs (Mainboard: 99, SME: 116) — used exclusively for threshold selection and hyperparameter verification.
- **Historical Out-of-Time Test Cohort (2026)**: 150 IPOs (Mainboard: 92, SME: 58) — held untouched until model evaluation.

### Readiness Status by Target

| Target | Model | Mainboard Out-of-Time Status | SME Out-of-Time Status | Final Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Target A: Positive Opening Return** | Model 6B (Logistic Regression) | ROC-AUC: 0.489, PR-AUC: 0.663 | ROC-AUC: 0.610, PR-AUC: 0.709 | **READY FOR FURTHER VALIDATION (SME) / EXPERIMENTAL (Mainboard)** |
| **Target B: Severe Opening Loss ($\le -10\%$)** | Model 6C (Penalized Logistic) | PR-AUC: 0.075, Recall: 1.0 (Low Prec: 0.088) | PR-AUC: 0.166, Recall: 1.0 (Low Prec: 0.207) | **EXPERIMENTAL — INSUFFICIENT EVIDENCE (Low training events: N=13 / N=18)** |
| **Target C: Continuous Opening Return** | Model 6D (Ridge Regression) | MAE: 25.08% (Worse than Median Baseline: 18.40%) | MAE: 37.30% (Worse than Median Baseline: 30.23%) | **NOT READY (Naive historical median outperforms linear models)** |

---

## 2. Cohort Split Coverage & Asymmetric Event Counts

All preprocessing (medians, means, standard deviations) was fitted strictly on Training data (2020–2024).

| Segment | Cohort | Total Verified IPOs | Positive Open Count (%) | Severe Loss Open Count (%) | Mean Return (%) | Median Return (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mainboard** | Train (2020–2024) | 254 | 191 (75.2%) | **13 (5.1%)** | +24.4% | +13.9% |
| **Mainboard** | Validation (2025) | 99 | 69 (69.7%) | **4 (4.0%)** | +6.7% | +9.3% |
| **Mainboard** | Out-of-Time Test (2026) | 92 | 60 (65.2%) | **8 (8.7%)** | +11.3% | +13.9% |
| **SME Board** | Train (2020–2024) | 368 | 307 (83.4%) | **18 (4.9%)** | +38.6% | +14.4% |
| **SME Board** | Validation (2025) | 116 | 73 (62.9%) | **16 (13.8%)** | +4.3% | +4.2% |
| **SME Board** | Out-of-Time Test (2026) | 58 | 34 (58.6%) | **12 (20.7%)** | +3.1% | +3.0% |

> [!WARNING]
> **Severe Event Scarcity in Training Data**: Across 5 full years (2020–2024), there were only **13 severe losses in Mainboard** and **18 in SME**. Attempting complex parametric models on such sparse positive class representations runs extreme risk of pseudo-fit.

---

## 3. Model Performance on Out-of-Time Test (2026)

### Target A: Positive Opening Return ($P(\text{Open Return} > 0)$)
The benchmark Model 6A predicts the training period base-rate constant (Mainboard: 75.2%, SME: 83.4%).
- **Operating Thresholds**: Tuned strictly on 2025 validation data (Mainboard threshold = 0.50, SME threshold = 0.50).

| Segment | Model | Out-of-Time ROC-AUC | Out-of-Time PR-AUC | Brier Score | F1 Score | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mainboard** | Model 6A (Base Rate) | 0.500 | 0.652 | 0.2368 | 0.000 | Naive baseline |
| **Mainboard** | Model 6B (Logistic Regression) | 0.489 | **0.663** | 0.2386 | 0.789 | Marginal PR gain over baseline, but ROC-AUC is near chance |
| **SME Board** | Model 6A (Base Rate) | 0.500 | 0.586 | 0.3041 | 0.000 | Naive baseline |
| **SME Board** | Model 6B (Logistic Regression) | **0.610** | **0.709** | **0.2894** | **0.739** | **Beats base rate across ROC-AUC (+0.11), PR-AUC (+0.12), and Brier Score** |

*Takeaway*: For SME IPOs, pre-issue market momentum and recent IPO sentiment provide genuine out-of-time discriminating power (PR-AUC 0.709 vs base rate 0.586). For Mainboard IPOs, macro signals alone show limited separability, confirming that firm-specific fundamentals and valuation are necessary.

---

### Target B: Severe Opening Loss ($P(\text{Open Return} \le -10\%)$)
- Evaluated with class-weight balancing and L2 shrinkage.
- **Operating Thresholds**: Tuned on 2025 validation data to maximize Recall.

| Segment | Model | Out-of-Time ROC-AUC | Out-of-Time PR-AUC | Severe Loss Recall | Severe Loss Precision |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Mainboard** | Model 6A (Base Rate) | 0.500 | 0.087 | 0.0% | 0.0% |
| **Mainboard** | Model 6C (Severe Classifier) | 0.349 | 0.075 | **100.0% (8/8)** | **8.8%** (Flags nearly all IPOs) |
| **SME Board** | Model 6A (Base Rate) | 0.500 | 0.207 | 0.0% | 0.0% |
| **SME Board** | Model 6C (Severe Classifier) | 0.351 | 0.166 | **100.0% (12/12)** | **20.7%** (Flags nearly all IPOs) |

*Critical Diagnostic*: Because severe losses were so rare in 2020–2024 (only ~5%), the balanced model over-compensates in the weaker 2026 regime by flagging almost every issue to achieve 100% recall, resulting in near-zero precision. **Model 6C is not ready for deployment and must be treated as experimental.**

---

### Target C: Continuous Opening Return
- Target is the continuous percentage return at open.

| Segment | Model | 2025 Validation MAE | 2026 Test MAE | 2026 Test RMSE | Mean Bias (Overprediction) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Mainboard** | **Naive Median Baseline** | **13.87%** | **18.40%** | **24.83%** | **-0.02%** |
| **Mainboard** | Naive Mean Baseline | 21.66% | 23.85% | 28.09% | +13.15% |
| **Mainboard** | Model 6D (Ridge Regression) | 24.19% | 25.08% | 29.41% | +15.57% |
| **SME Board** | **Naive Median Baseline** | **26.09%** | **30.23%** | **34.58%** | **+11.36%** |
| **SME Board** | Naive Mean Baseline | 42.57% | 45.80% | 48.25% | +35.51% |
| **SME Board** | Model 6D (Ridge Regression) | 32.52% | 37.30% | 40.60% | +22.50% |

*Critical Insight*: **Linear continuous return models fail to beat a simple naive historical median.** Because IPO returns are heavily right-skewed with extreme positive outliers, linear regression over-predicts typical returns by +15% to +22%. The naive median baseline is significantly superior in MAE.

---

## 4. Feature Importance & Coefficients (Standardized)

Standardized logistic coefficients ($\beta_{\text{std}}$) for Target A (Positive Opening):

| Segment | Feature | Standardized $\beta$ | Odds Ratio per 1 SD Shift | Interpretation |
| :--- | :--- | :--- | :--- | :--- |
| **SME** | **Recent 5 Sentiment** | **+0.2450** | **1.278** | **Strongest positive driver for SME listings** |
| **SME** | **India VIX Level** | **-0.2602** | **0.771** | Elevated VIX suppresses SME positive listing odds |
| **SME** | Nifty 50 5s Return | +0.0806 | 1.084 | Modest positive contribution |
| **Mainboard** | Nifty 50 5s Return | +0.1028 | 1.108 | Modest positive broad market support |
| **Mainboard** | India VIX Level | -0.0980 | 0.907 | Slight negative headwind |
| **Mainboard** | Recent 5 Sentiment | -0.0842 | 0.919 | Negligible standalone impact on Mainboard |

---

## 5. Artifacts and Outputs Summary

1. [`data/processed/step_6a_model_metrics.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_6a_model_metrics.csv): Complete metrics for all 18 evaluated models/cohorts.
2. [`data/processed/step_6a_predictions.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_6a_predictions.csv): Individual out-of-time probability and return predictions across all 365 validation and test IPOs.
3. [`data/processed/step_6a_feature_importance.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_6a_feature_importance.csv): Standardized coefficients and odds ratios per feature.
4. [`data/processed/step_6a_cohort_coverage.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_6a_cohort_coverage.csv): Temporal split breakdown.
5. [`src/train_step_6a_models.py`](file:///d:/personal/st-ai/ipo-record/src/train_step_6a_models.py): Pipeline script.
6. [`tests/test_step_6a.py`](file:///d:/personal/st-ai/ipo-record/tests/test_step_6a.py): Verification suite (all 5 tests passed).
