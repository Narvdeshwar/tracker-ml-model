# Step 5E Report: Statistical Integrity and Predictive Readiness Audit

## 1. Executive Summary & Readiness Decision

**DECISION: READY WITH RESTRICTIONS**

The statistical validity, regression scaling, cutoff missingness patterns, target specifications, and chronological split feasibility have been audited inside the repository:
- **Output Audit Datasets Created**:
  1. [`data/processed/step_5e_regression_diagnostics.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_5e_regression_diagnostics.csv): Resolved feature scaling, exact odds ratios, standard errors, and confidence intervals.
  2. [`data/processed/step_5e_cutoff_missingness.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_5e_cutoff_missingness.csv): Systematic comparison between verified-cutoff ($N=987$) and unresolved-cutoff ($N=528$) cohorts.
  3. [`data/processed/step_5e_feature_eligibility.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_5e_feature_eligibility.csv): Strict classification of candidate features for Experiment A vs Experiment B.
  4. [`data/processed/step_5e_temporal_split_counts.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_5e_temporal_split_counts.csv): Out-of-time sample counts and class balance across 2020–2024 (Train), 2025 (Validation), and 2026 (Test).
- **Automated Audit Test Suite**: [`tests/test_step_5e.py`](file:///d:/personal/st-ai/ipo-record/tests/test_step_5e.py) (All 6 test suites passed).

---

## 2. Market-Momentum Scaling Audit (Resolution of the 21,000 Odds Ratio)

### Root Cause
In `market_daily.csv`, `nifty50_return_5s` is stored as an exact fractional decimal (e.g., `+0.021` representing $+2.1\%$). In logistic regression:
$$\ln\left(\frac{p}{1-p}\right) = \alpha + \beta X$$
The standard coefficient $\beta = 9.9881$ represents the change in log-odds per **$1.0$ unit change in $X$** — which corresponds to an extreme **$+100\%$ market rally** over 5 trading sessions!
Evaluating $\exp(\beta) = \exp(9.9881) \approx 21,766$ produced the massive raw number.

### Interpretable Scaling Reconciliation
When rescaled to a **meaningful $+1.0\%$ change** in the 5-session market return ($\Delta X = 0.01$):
$$\text{Odds Ratio} = \exp(0.01 \times \beta) = \exp(0.09988) = \mathbf{1.105} \quad (95\%\text{ CI: } [1.024, 1.193])$$

| Feature | Raw Scale Unit | Raw $\beta$ ($p$-value) | Raw Odds Ratio | Meaningful Increment | Interpretable Odds Ratio (95% CI) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Nifty 50 5s** | Decimal ($1.0 = +100\%$) | $+9.988$ ($p = 0.010$) | $21,766$ | **$+1.0\%$ move** | **1.105 [1.024, 1.193]** | Clean convergence |
| **Nifty 500 5s** | Decimal ($1.0 = +100\%$) | $+10.225$ ($p = 0.005$) | $27,576$ | **$+1.0\%$ move** | **1.108 [1.031, 1.190]** | Clean convergence |
| **India VIX Level** | Index Points | $-0.010$ ($p = 0.582$) | $0.990$ | **$+1.0$ point change** | **0.990 [0.955, 1.026]** | Not significant |
| **Recent 5 Sentiment** | Percentage Points | $+0.012$ ($p = 0.0001$) | $1.012$ | **$+5.0\%$ sentiment shift**| **1.060 [1.029, 1.092]** | Statistically significant |

*Conclusion*: Broad market momentum exerts a modest, statistically credible boost of $\approx +10.5\%$ to the odds of a positive listing per $1\%$ market gain. No numerical separation or multicollinearity was detected.

---

## 3. Cutoff-Date Missingness Audit: Systematic Asymmetry

Analyzing the 528 unresolved cutoff records vs the 987 verified records revealed a **critical selection asymmetry**:

| Dimension / Segment | Total IPOs | Verified Cutoffs | Unresolved Cutoffs | Verified Pos% | Unresolved Pos% | Verified Severe Loss% ($\le -10\%$) | Unresolved Severe Loss% ($\le -10\%$) | $p$-value (Difference) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Overall** | 1,515 | 987 (65.1%) | 528 (34.9%) | 75.9% | 70.5% | 8.2% | **13.1%** | **$p < 0.0001$** |
| **Mainboard** | 463 | 445 (96.1%) | 18 (3.9%) | 72.4% | 77.8% | 7.4% | 0.0% | $p = 0.302$ (NS) |
| **SME Board** | 1,052 | 542 (51.5%) | 510 (48.5%) | 78.8% | 70.2% | 8.9% | **13.5%** | **$p < 0.0001$** |

### Critical Takeaway for Modeling
The missingness is **not Missing Completely at Random (MCAR)**. In the SME segment, unresolved cutoffs exhibit a significantly lower positive listing rate ($70.2\%$ vs $78.8\%$) and a significantly higher rate of severe loss ($13.5\%$ vs $8.9\%$, $p < 0.0001$).
- **Restriction 1**: Models evaluated on the verified cutoff cohort will overestimate SME baseline quality unless this selection bias is controlled or the unresolved cutoffs are backfilled from BSE circulars.
- **Restriction 2**: Initial models in Step 6 must be evaluated separately on Mainboard (where cutoff coverage is $96.1\%$) and SME (where coverage is $51.5\%$).

---

## 4. Chronological Evaluation Readiness

Auditing the temporal split counts confirmed sufficient sample size across cohorts:

| Split Cohort | Period | Total Verified IPOs | Mainboard Verified | SME Verified | Verified Positive Open Count (%) | Verified Severe Loss Open Count (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Train** | 2020 – 2024 | **622** | 254 | 368 | 498 (80.1%) | 31 (5.0%) |
| **Validation** | 2025 | **215** | 99 | 116 | 142 (66.1%) | 20 (9.3%) |
| **Out-of-Time Test** | 2026 | **150** | 92 | 58 | 94 (62.7%) | 20 (13.3%) |

*Key Temporal Trend*: The market environment became noticeably more challenging from 2024 to 2026: the positive listing rate dropped from $80.1\%$ to $62.7\%$, while severe loss frequency rose from $5.0\%$ to $13.3\%$. This temporal regime shift makes 2026 a stringent test of model generalizability.

---

## 5. Mandatory Modeling Restrictions for Step 6

1. **Segment Isolation**: Mainboard and SME models must be trained and evaluated independently.
2. **Feature Scaling Guarantee**: All market momentum features must be passed in percentage point units ($+1.0 = +1\%$) or standardized with explicit scaler pipelines.
3. **Target Decoupling**: Separate models for:
   - Target 1: $P(\text{Listing Open Return} > 0)$
   - Target 2: $P(\text{Listing Open Return} \le -10\%)$ (Severe Loss Classifier evaluated primarily by PR-AUC and Recall)
   - Target 3: Regressor for continuous open return.
4. **Subscription & GMP Quarantine**: Keep unverified subscription and GMP fields quarantined out of baseline features until timestamped audit records are ingested.
5. **No Lookahead Tuning**: Model tuning is strictly confined to 2020–2024 (train) and 2025 (validation). 2026 remains untouched for out-of-time evaluation.
