# Step 5A Validation Report: Market Timeseries Engine

## 1. Executive Summary

Step 5A of the Indian IPO Machine Learning Research pipeline has been constructed and validated inside the repository:
- **Output File**: `data/processed/market_daily.csv`
- **Workbook Updated**: `Indian_IPO_ML_Research_Starter.xlsx` (`Market_Daily` sheet populated with 1,708 trading sessions).
- **Core Pipeline Script**: `src/build_market_daily.py`
- **Automated Test Suite**: `tests/test_market_daily.py` (All 4 test suites passed: chronological integrity, positive closes, return calculation precision, date range coverage).

---

## 2. Dataset Provenance & Coverage

The historical market dataset covers **1,708 official trading sessions** from **2019-12-02 to 2026-10-27**.

| Series | Primary Source | Date Range | Total Observations | Missingness | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Nifty 50** | Official Exchange Timeseries / Nifty Indices | 2019-12-02 to 2026-10-27 | 1,708 | 0 (0.0%) | Master calendar anchor |
| **Nifty 500** | GitHub Verified Repo (`nifty500_price.csv`) + Oct 2026 Extension | 2019-12-02 to 2026-10-27 | 1,708 | 0 (0.0%) | Spliced seamlessly (max variance < 0.0008) |
| **India VIX** | Official Exchange Timeseries / NSE India VIX | 2019-12-02 to 2026-10-27 | 1,691 | 17 (1.0%) | 17 non-computation / special holiday sessions |
| **Nifty SME Emerge** | Official NSE SME Index (`nifty_sme_emerge_price.csv`) | 2019-12-02 to 2026-09-28 | 1,689 | 19 (1.1%) | Baseline for NSE SME issues |
| **BSE SME IPO Index**| Official BSE SME Index (`bse_sme_ipo_price.csv`) | 2019-12-02 to 2026-09-25 | 1,687 | 21 (1.2%) | Baseline for BSE SME issues |

---

## 3. Strict Anti-Leakage Rules Applied

1. **Trading Session Basis**: Returns are calculated strictly across **$t$ vs $t-1$ (1d)**, **$t$ vs $t-5$ (5s)**, and **$t$ vs $t-20$ (20s)** trading sessions, **never calendar days**.
   $$\text{return\_5s} = \frac{P_t}{P_{t-5}} - 1, \quad \text{return\_20s} = \frac{P_t}{P_{t-20}} - 1$$
2. **No Forward Imputation**: Missing observations are left as `NaN`/null rather than forward or backward filled, preventing synthetic lookahead data from entering ML models.
3. **India VIX Metrics**: Computed both absolute level changes ($\text{VIX}_t - \text{VIX}_{t-k}$) and percentage changes ($\frac{\text{VIX}_t}{\text{VIX}_{t-k}} - 1$).
4. **Calendar Realities**: Muhurat trading sessions, exchange-specific non-trading sessions, and statutory holidays are preserved exactly as reported by the exchange.

---

## 4. Verification & Automated Test Results

The test suite executed via `unittest` confirmed:
- **Monotonicity**: Dates are 100% strictly chronological and unique (0 duplicate trading dates).
- **Domain Validity**: Closing prices are strictly positive ($> 0$).
- **Return Calculation Precision**: Verified exact match between formula calculations and dataset columns across randomized sample indices (tolerance $< 10^{-5}$).

---

## 5. Next Steps for Step 5B

1. Reconcile and audit `issue_close_date` for the 528 SME IPO records from exchange circulars without synthetic guesswork.
2. Join `Market_Daily` rolling features (Nifty 50, Nifty 500, India VIX, SME indices) to each IPO strictly as of its **Issue Close Date** ($T$ or $T-1$).
3. Formulate the rolling **Recent IPO Sentiment** indicator (listing return of preceding 5 and 10 IPOs whose listings occurred strictly prior to the issue close date).
