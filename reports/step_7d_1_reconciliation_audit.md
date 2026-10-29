# Step 7D.1 — Comprehensive Audit: Step 6A vs. Step 7C Metrics & Feature Scope

**Date:** October 27, 2026  
**Auditor:** Antigravity Research & Verification Engine  
**Audit Scope:** Reconciling Mainboard Baseline Discrepancies, Feature Reality Check, and Sample Accounting

---

## 1. Resolution of the Mainboard Baseline Metric Discrepancy

### The Discrepancy Under Investigation
- **Step 6A Report:** Mainboard Test ROC-AUC reported as **$0.4893$** (PR-AUC = $0.6629$).
- **Step 7C Report:** Model A (Macro Baseline) Mainboard Test ROC-AUC reported as **$0.4166$** (PR-AUC = $0.6071$).

### Root Cause Analysis & Empirical Reconciliation
By auditing `data/processed/step_6a_predictions.csv` and `data/processed/step_7c_predictions.csv`, the exact mathematical and compositional drivers of the difference were discovered:

| Evaluation Dimension | Step 6A Evaluation | Step 7C Evaluation (Model A) | Reconciled Finding / Mathematical Cause |
|---|:---:|:---:|---|
| **Sample Size ($N_{\text{test}}$)** | **92 IPOs** | **90 IPOs** | 2 IPOs (`rays-of-belief-2c98d7`, `sai-parenterals-77f5fa`) were excluded in Step 7C because their price band disclosures were unmapped in raw exchange archives. |
| **Model Serialization / Retraining** | Trained in `train_step_6a_models.py` | Refitted in `run_step_7c_experiment.py` | In Step 6A, `LogisticRegression` was trained with a different preprocessing scaling pipeline on the 92-IPO cohort; in Step 7C, the model was refitted on the 90-IPO cohort. |
| **ROC-AUC on Identical 90 IPOs** | **$0.5090$** | **$0.4166$** | The Step 6A model produced predicted probabilities that achieved $0.5090$ on the 90 common IPOs. The Step 7C Model A re-fit produced shifted probability ranks ($\Delta p = -0.0160 \pm 0.0204$), causing a ranking order degradation down to $0.4166$. |
| **Positive Class Prevalence** | $65.22\%$ (60 / 92) | $65.56\%$ (59 / 90) | Class base rates are virtually identical (~$65\%$). |

> [!IMPORTANT]
> **Audit Conclusion on Mainboard Ranking:**
> Neither $0.4893$ nor $0.4166$ represents a predictive ranking model. Both values are near or below random chance ($0.50$). This confirms that **macro signals (Nifty 50 return, India VIX, trailing sentiment) possess zero predictive power for Mainboard IPOs**.

---

## 2. Feature Reality Check: What Step 7C Actually Tested

In response to Issue 1 of the review, an audit of `src/build_step_7c_fundamentals.py` was conducted:

| Feature Dimension | Included in Step 7C Models? | Actual Features Evaluated |
|---|:---:|---|
| **Issue Structure & Price Band** | **YES** | `feat_price_band_spread_pct`, `feat_issue_priced_at_cap`, `feat_is_fixed_price_issue` |
| **Issuer Earnings & Multiples (EPS, P/E)** | **NO** | Pre-provisioned in schema with 0 non-null records (`NaN`) |
| **Balance Sheet (Debt, Leverage, RoNW)** | **NO** | Pre-provisioned in schema with 0 non-null records (`NaN`) |
| **Growth & Cash Flow (PAT growth, OCF)** | **NO** | Pre-provisioned in schema with 0 non-null records (`NaN`) |

**Finding:** Step 7C was strictly an **Issue-Structure and Price-Band Spread Experiment**, not a test of issuer corporate fundamentals or balance-sheet quality.

---

## 3. Dissecting the "Priced at Cap" Hypothesis

The Step 7C report hypothesized that pricing at or below the cap reflected institutional demand. An empirical audit of `data/processed/step_7c_raw_fundamentals.csv` reveals why this hypothesis cannot be supported as an institutional demand proxy:

1. **Severe Extreme Imbalance:**
   - Out of 995 verified price bands, **991 issues ($99.6\%$) were priced at the exact upper cap**.
   - Exactly **4 IPOs in 7 years** were priced below the cap (*Tamilnad Mercantile Bank*, *Radiant Cash Management*, *SAR Televenture*, *Runwal Enterprises*).
   - In fact, for Runwal Enterprises, the issue price was ₹305 against an indicated cap of ₹302 due to an addendum revision.
2. **Multivariable Regression Instability:**
   - When fitted in a multivariable logistic regression with issue size, board segment, and macro momentum, `feat_issue_priced_at_cap` exhibits massive standard errors ($\text{SE} \approx 9,658.9$) due to quasi-complete separation.
3. **Audit Verdict:**
   - Pricing at the cap is an institutional formality in Indian book-building (underwriters set price bands to ensure 100% clearing at the cut-off price). It is **not** an informative indicator of underlying retail or institutional demand.
