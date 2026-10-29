# Step 6A.3 Report: SME Ranking Robustness, Distribution Shift Audit, and Prospective Shadow Evaluation Design

## 1. Executive Summary & Status Decisions

Step 6A.3 conducts a rigorous methodological audit of the SME positive-opening baseline, investigates distribution shifts across temporal regimes, calculates small-sample Wilson score intervals for probability tiers, and specifies the architecture for prospective shadow evaluation:
- **Output Audit Datasets Created**:
  1. [`data/processed/step_6a3_bootstrap_audit.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_6a3_bootstrap_audit.csv): Verified paired bootstrap analysis ($N = 2,000$ iterations) with in-sample prevalence recalculation and zero-degenerate exclusions.
  2. [`data/processed/step_6a3_tier_uncertainty.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_6a3_tier_uncertainty.csv): 95% Wilson score confidence bounds for empirical tier win rates.
  3. [`data/processed/step_6a3_cohort_comparison.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_6a3_cohort_comparison.csv): Regime shift comparison across 2020–2024 (Train), 2025 (Validation), and 2026 (Test).
  4. [`data/processed/step_6a3_prospective_log_schema.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_6a3_prospective_log_schema.csv): Immutable append-only schema for live prospective shadow logging.
- **Automated Test Suite**: [`tests/test_step_6a3.py`](file:///d:/personal/st-ai/ipo-record/tests/test_step_6a3.py) (All 4 tests passed).

### Final Status Decisions

| Task / Model | Evaluation Status | Key Findings |
| :--- | :--- | :--- |
| **SME Positive-Opening Ranking** | **PROMISING — EXPERIMENTAL** | Statistically significant PR-AUC lift of $+0.1235$ (95% CI: $[+0.0165, +0.2536]$). Tier 3 point estimate is $75.0\%$, but small-sample 95% Wilson interval is wide ($[53.1\%, 88.8\%]$). |
| **Mainboard Positive-Opening Ranking** | **NO DEMONSTRATED ADVANTAGE** | ROC-AUC ($0.489$) and tier separation are indistinguishable from chance. Macro features cannot differentiate large-cap IPOs. |
| **Severe-Loss Prediction** | **INSUFFICIENT EVIDENCE (FAILED BASELINE)** | Structural regime inversion: 2026 severe loss IPOs had lower pre-issue VIX than safe IPOs due to complacent bull-market conditions. |
| **Continuous-Return Prediction** | **NO DEMONSTRATED ADVANTAGE** | Naive historical training median ($+14.2\%$ Mainboard, $+24.6\%$ SME) strictly beats linear regression MAE. |
| **Prospective Shadow Logging** | **READY FOR SHADOW EVALUATION** | Append-only schema defined with pre-listing cutoff timestamps, frozen model versioning, and post-listing settlement tracking. |

---

## 2. Methodological Audit of the Step 6A.2 Bootstrap Procedure

To verify whether the PR-AUC significance claim holds under strict methodological scrutiny, the paired bootstrap was audited against three potential vulnerabilities:
1. **Paired Observation Guarantee**: Verified that each resample drew identical $(y_i, \hat{p}_{i, \text{model}}, \hat{p}_{i, \text{base}})$ tuples, preserving outcome-prediction alignment.
2. **In-Sample Benchmark Recalculation**: In every resample, the baseline average precision was recalculated dynamically as the resample's true prevalence ($\bar{y}_{\text{resample}}$), preventing artificial inflation.
3. **Degenerate Sample Handling**: 0 out of 2,000 resamples contained a single class (the 2026 SME holdout has 34 positive and 24 negative outcomes; $P(\text{all one class}) \approx 0$).

### Audited Bootstrap Results on SME 2026 Holdout ($N = 58$)

| Metric | Point Estimate | Bootstrap Mean | 95% Percentile CI | Zero Excluded? | Methodological Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PR-AUC Lift (vs Resample Prevalence)** | **+0.1235** | **+0.1308** | **$[+0.0165, +0.2536]$** | **YES** | **Statistically Significant ($p < 0.05$)** |
| **ROC-AUC Lift (vs Chance 0.50)** | +0.1109 | +0.1086 | $[-0.0393, +0.2574]$ | NO | Spans zero due to small sample size ($N=58$) |
| **Brier Score Delta (vs Train Constant Base)** | -0.0147 | -0.0146 | $[-0.0306, -0.0001]$ | **YES** | **Statistically Significant Improvement** |

*Takeaway*: The PR-AUC lift of $+12.35\%$ is robust to paired resampling and in-sample prevalence adjustment. However, because $N = 58$, the sample represents repeated draws from the same 58 IPOs—not 2,000 independent historical events.

---

## 3. Small-Sample Tier Uncertainty (Wilson Score Intervals)

While the SME model achieved an empirical win rate of **$75.0\%$** in Tier 3 on the 2026 holdout, the tier sample size ($N = 20$) introduces substantial binomial variance.

Applying the standard **Wilson Score Interval** ($\alpha = 0.05$):
$$\tilde{p} = \frac{x + \frac{z^2}{2}}{n + z^2} \pm \frac{z}{n + z^2} \sqrt{\frac{x(n - x)}{n} + \frac{z^2}{4}}$$

| Rank Tier | Evaluated IPOs ($N$) | Observed Wins | Empirical Win Rate | 95% Wilson Confidence Interval | Mean Predicted Probability | Overconfidence Gap |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 1 (Low Prob)** | 20 | 9 | **45.00%** | **$[25.82\%, 65.79\%]$** | 74.69% | $+29.69\%$ |
| **Tier 2 (Mid Prob)** | 18 | 10 | **55.56%** | **$[33.72\%, 75.44\%]$** | 82.54% | $+26.98\%$ |
| **Tier 3 (High Prob)** | 20 | 15 | **75.00%** | **$[53.13\%, 88.81\%]$** | 83.85% | $+8.85\%$ |

> [!WARNING]
> **Practical Uncertainty Notice**: Because Tier 3 contains only 20 IPOs, its true long-run success rate could plausibly be as low as **$53.1\%$** or as high as **$88.8\%$**. An observed $75\%$ rate in a 20-IPO cohort is encouraging evidence of separation, but **it cannot be interpreted as a guaranteed future probability of success**.

---

## 4. Cohort Distribution Shift Audit

Comparing the three temporal cohorts reveals a profound macro regime shift from 2020 to 2026:

| Segment | Cohort Period | Sample ($N$) | Positive Open Rate (%) | Severe Loss Rate ($\le -10\%$) | Median Return (%) | Trailing Nifty 5s Return | India VIX Level | Trailing 5-IPO Sentiment |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SME** | **Train (2020–2024)** | 368 | **83.42%** | **4.89%** | **+24.57%** | +0.40% | 14.82 | +39.94% |
| **SME** | **Validation (2025)** | 116 | **62.93%** | **13.79%** | **+5.50%** | -0.04% | 12.78 | +9.79% |
| **SME** | **Test (2026)** | 58 | **58.62%** | **20.69%** | **+2.33%** | -0.67% | 13.90 | +10.61% |
| **Mainboard** | **Train (2020–2024)** | 254 | **75.20%** | **5.12%** | **+14.21%** | -0.12% | 15.56 | +36.11% |
| **Mainboard** | **Validation (2025)** | 99 | **69.70%** | **4.04%** | **+5.96%** | -0.14% | 12.14 | +15.10% |
| **Mainboard** | **Test (2026)** | 92 | **65.22%** | **8.70%** | **+8.29%** | -0.91% | 13.39 | +18.68% |

### Diagnosis of the Model's Probability Overconfidence
1. **Base-Rate Deflation**: In SME IPOs, the empirical base rate collapsed by **$-24.8$ percentage points** (from $83.4\%$ during 2020–2024 down to $58.6\%$ in 2026).
2. **Sentiment Compression**: Trailing IPO listing sentiment collapsed from an average of $+39.9\%$ in training down to $+10.6\%$ in 2026.
3. **Severe Loss Acceleration**: Severe loss frequency rose four-fold in SME (from $4.9\%$ to $20.7\%$).
4. **Conclusion**: The model's $+9\%$ to $+30\%$ probability overconfidence is primarily a **base-rate shift artifact**. When trained on a 5-year bull market, uncalibrated logistic regression outputs reflect the prior era's base rate.

---

## 5. Architecture for Prospective Shadow Evaluation

To ensure future evaluation is 100% immune to retrospective lookahead bias, an **immutable, append-only Prospective Shadow Log** has been designed ([`step_6a3_prospective_log_schema.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_6a3_prospective_log_schema.csv)):

```
[At Issue Close 17:00 IST]
   │
   ├─► Log prediction_id, ipo_id, model_version (Model_6B_SME_v1.0)
   ├─► Log cutoff market features (Nifty 5s, VIX, Recent 5 Sentiment)
   ├─► Record raw_predicted_prob & predicted_rank_tier (Tier 1 / 2 / 3)
   └─► Lock status: LOGGED_PRE_LISTING (Immutable record hash)
   │
   ▼
[Post-Listing Settlement Day]
   │
   ├─► Record official Bhavcopy listing_open_price
   ├─► Compute actual_positive_open & brier_error
   └─► Update status: OUTCOME_RECORDED
```

### Prospective Evaluation Protocol
- **No In-Flight Retraining**: Predictions will be generated by the frozen `Model_6B_SME_v1.0` pipeline.
- **Reporting Gate**: Evaluate performance in blocks of 25 prospectively logged IPOs.
- **De-Registration Rule**: If the prospective Tier 3 win rate falls below the cohort base rate over 30 consecutive prospective listings, the model will be formally retired.
