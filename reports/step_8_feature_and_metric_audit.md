# Step 8 — Pre-Simulation Feature, Metric, and Data Audit

**Date:** October 27, 2026  
**Auditor:** Antigravity Research & Verification Engine  
**Scope:** Repository Inventory, Resolution of Step 7D Interpretations, and Data Governance Prior to Decision Simulation  
**Status:** **AUDIT PASSED — PROCEED TO SIMULATION FRAMEWORK**

---

## 1. Project & Repository Data Inventory

An exhaustive audit of the actual repository storage (`D:\personal\st-ai\ipo-record`) confirms the underlying data structures, schemas, and models:

| Component | Storage Path | Certified Row Count | Key Verified Fields | Provenance / Integrity Status |
|---|---|:---:|---|---|
| **Master IPO Dataset** | `Indian_IPO_ML_Research_Starter.xlsx` (`IPO_Master`) | 1,515 | `ipo_id`, `company_name`, `board_type`, `issue_price_inr`, `listing_date` | Base registry for Indian IPOs (2020–2026) |
| **Realized Outcomes** | `Indian_IPO_ML_Research_Starter.xlsx` (`Listing_Outcomes`) | 1,515 | `listing_open_inr`, `listing_close_inr`, `listing_open_return_pct` | Certified exchange listing prices and returns |
| **Cutoff Recovery Ledger** | [data/processed/ipo_cutoff_recovery.csv](file:///d:/personal/st-ai/ipo-record/data/processed/ipo_cutoff_recovery.csv) | 1,515 | `issue_close_date`, `verification_status` | 1,003 verified cutoffs; 512 queued/conflict records |
| **Pre-Cutoff Features** | [data/processed/ipo_features_issue_close.csv](file:///d:/personal/st-ai/ipo-record/data/processed/ipo_features_issue_close.csv) | 1,515 | `nifty50_return_5s`, `india_vix_level_at_cutoff`, `recent5_positive_listing_rate` | Leakage-safe macro momentum & trailing sentiment |
| **Step 7D Normalized Features**| [data/processed/step_7d_normalized_features.csv](file:///d:/personal/st-ai/ipo-record/data/processed/step_7d_normalized_features.csv) | 1,515 | `log_issue_price`, `feat_price_band_spread_pct`, `temporal_eligibility` | Strictly pre-listing price-band and price features |
| **Baseline SME Model** | [models/frozen/model_6b_sme_v1.joblib](file:///d:/personal/st-ai/ipo-record/models/frozen/model_6b_sme_v1.joblib) | 1 artifact | SHA-256: `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` | **FROZEN & IMMUTABLE** (Step 6B SME baseline) |
| **Automated Unit Tests** | `tests/` | 95 tests | 95/95 passing tests across 13 test modules | Verified repository integrity |

---

## 2. Resolution of Step 7D Interpretations & Corrections

### Correction A: Re-labeling `log_issue_price` & Audit of Scale Data Availability
- **Finding:** The variable `log_issue_price` was computed as $\ln(\text{issue\_price\_inr})$, which is strictly the natural logarithm of the **per-share issue price (in ₹)**.
- **Economic Reality:** A per-share nominal price is determined arbitrarily by the company's share face value and the total number of shares issued; it does not measure company enterprise value, balance-sheet scale, or issue size. A company issuing shares at ₹500 may raise ₹50 Cr, while a company issuing shares at ₹100 may raise ₹1,000 Cr.
- **Repository Availability Audit:** An inspection of `Indian_IPO_ML_Research_Starter.xlsx` and `IPO-PastIssue-01-01-2020-to-27-10-2026.csv` reveals that columns `issue_size_cr`, `fresh_issue_cr`, `ofs_cr`, and post-issue market capitalization are unpopulated ($0 / 1,515$ non-null records) in static public archives.
- **Corrective Action for Step 8:**
  1. The variable is strictly re-labeled as `log_issue_price` (Nominal Per-Share Issue Price) and **must never be interpreted or labeled as company scale or enterprise valuation**.
  2. No rule or strategy in Step 8 shall assume that higher per-share price indicates lower fundamental risk.

---

### Correction B: Reconciling Absolute PR-AUC Difference vs. Relative Percentage Lift
In Step 7D, the SME severe-loss model (Model B) achieved a test PR-AUC of $0.3595$ against a test base rate of $0.2069$. The report incorrectly phrased the difference ($0.1526$) as a "$15.26\%$ lift over the base rate".

To maintain mathematical precision, all future metrics, code, and reports strictly segregate and define:

$$\text{PR-AUC Absolute Difference } (\Delta_{\text{abs}}) = \text{PR-AUC} - \text{Base Rate} \quad (\text{expressed in percentage points, pp})$$
$$\text{PR-AUC Relative Lift } (\text{Lift}_{\text{rel}}) = \frac{\text{PR-AUC} - \text{Base Rate}}{\text{Base Rate}} \times 100\% \quad (\text{expressed as a percentage, } \%)$$

For the SME severe-loss model:
- **Test Base Rate:** $20.69\%$
- **Test PR-AUC:** $35.95\%$ ($0.3595$)
- **Absolute Difference ($\Delta_{\text{abs}}$):** $+15.26\text{ pp}$ ($+0.1526$)
- **Relative Lift ($\text{Lift}_{\text{rel}}$):** $+73.76\%$ ($0.1526 / 0.2069 \approx 73.76\%$)

---

### Correction C: Formal Retirement of "Priced at Cap" Feature
- **Distributional Finding:** Out of 995 verified price-band records, **991 issues ($99.60\%$) were priced at the exact upper cap**. Exactly 4 issues cleared below cap in 7 years.
- **Instability & Separation:** In multivariable modeling, this feature exhibits quasi-complete separation with variance explosion ($\text{SE} \approx 9,658.9$).
- **Regulatory Reality:** Indian book-building under SEBI ICDR regulations operates such that retail and institutional investors almost universally bid at "CUT-OFF", ensuring 100% price discovery at the upper boundary.
- **Corrective Action for Step 8:** `issue_priced_at_cap` is formally preserved in audit ledgers for historical record-keeping, but is **retired from all decision strategy ranking engines**.

---

### Investigation: Mainboard Severe-Loss Model D Validation vs. Test Drop
An audit was conducted into why Mainboard Model D achieved a validation ROC-AUC of $0.6835$ (PR-AUC $0.3075$) in 2025, but collapsed to $0.4832$ (PR-AUC $0.1454$) in 2026 test holdout:

| Cohort | Total IPOs | Severe Loss Events ($\le -10\%$) | Severe Loss Base Rate | Non-Severe Mean Price | Severe Loss Mean Price | Model D ROC-AUC |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **2025 Validation** | 98 | **4** | $4.08\%$ | ₹353.17 | ₹130.25 | **$0.6835$** |
| **2026 Test Holdout** | 90 | **8** | $8.89\%$ | ₹297.39 | ₹240.13 | **$0.4832$** |

**Root Cause:** In the 2025 validation cohort, exactly 4 IPOs suffered severe listing losses, and all 4 happened by chance to have lower nominal issue prices (mean ₹130.25 vs. ₹353.17 for non-severe). The logistic regression overfit to these 4 rare events ($\beta = -0.4447$). In 2026, severe losses occurred across high-priced and low-priced issues alike (mean ₹240.13 vs. ₹297.39).
**Audit Verdict:** Validation metrics on rare events ($N=4$) exhibit extreme small-sample noise. High per-share issue price is not protective on Mainboard, and using it as an investment selection rule is strongly rejected.

---

*Certified by Antigravity Autonomous Research Engine.*
