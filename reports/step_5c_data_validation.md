# Step 5C Validation Report: Subscription, GMP, and Recent IPO Sentiment

## 1. Executive Summary

Step 5C has been implemented with strict data provenance, timestamp discipline, and anti-leakage safeguards:
- **Output Datasets Created**:
  1. `data/processed/ipo_sentiment_features.csv` (1,515 records; chronological trailing sentiment).
  2. `data/processed/subscription_observations.csv` (Standardized observation schema with timestamp tracking).
  3. `data/processed/gmp_observations.csv` (Standardized GMP observation schema).
  4. `data/processed/ipo_features_issue_close.csv` (Experiment A: Pre-close / Issue-close information set).
  5. `data/processed/ipo_features_post_close.csv` (Experiment B: Post-close / Listing-eve information set).
- **Workbook Updated**: [`Indian_IPO_ML_Research_Starter.xlsx`](file:///d:/personal/st-ai/ipo-record/Indian_IPO_ML_Research_Starter.xlsx) (`IPO_Sentiment_Features` sheet added with 1,515 records).
- **Automated Tests**: [`tests/test_step_5c.py`](file:///d:/personal/st-ai/ipo-record/tests/test_step_5c.py) (All 5 tests passed).

---

## 2. Recent IPO Sentiment Feature Implementation

The rolling sentiment metrics (`recent5_mean_listing_open_return_pct`, `recent5_positive_listing_rate`, `recent10_*`) were constructed strictly chronologically:
- **Strict Anti-Leakage Gate**: A prior IPO was eligible for inclusion in sentiment calculation if and only if:
  $$\text{prior\_ipo.listing\_date} < \text{target\_ipo.prediction\_cutoff\_date}$$
- **Coverage**:
  - Out of 987 verified cutoff IPOs, **986** have valid recent 5 and recent 10 sentiment indicators (the very first verified IPO in Jan 2020 had fewer than 5 preceding 2020 listings and was preserved as missing with `Insufficient prior listing history`).
  - All 528 unresolved cutoff IPOs remain strictly `NaN` with `sentiment_missing_reason = 'Unresolved prediction cutoff date'`.
- **Zero Lookahead Check**: Verified via automated tests that no IPO listed on or after the cutoff date was included in sentiment averages.

---

## 3. Subscription & GMP Data Provenance & Discipline

In strict compliance with the research safeguards:
1. **No Silent Zero Imputation**: Missing or unverified subscription and GMP fields remain strictly `NaN` rather than 0.0, avoiding severe misspecification in ML models.
2. **Experiment Separation**:
   - **Experiment A (`ipo_features_issue_close.csv`)**: Prediction timestamp fixed at Issue Close (17:00 IST). Only verified intraday / pre-close metrics will be permitted.
   - **Experiment B (`ipo_features_post_close.csv`)**: Prediction timestamp fixed after allotment basis publication (e.g., Listing Eve 18:00 IST).
3. **Availability Classification Established**: All observation schemas classify data as `PRE_ISSUE_CLOSE`, `AT_ISSUE_CLOSE`, `POST_ISSUE_CLOSE`, or `AVAILABILITY_UNKNOWN`.

---

## 4. Test Suite Verification

`tests/test_step_5c.py` validated:
1. **Full Record Preservation**: 1,515 rows preserved across all datasets.
2. **Sentiment Correctness**: Hand-recalculated sample sentiment means match pipeline outputs to 2 decimal places.
3. **Unresolved Handling**: Unresolved cutoff records have null sentiment.
4. **Experiment Isolation**: Experiment A and B maintain separate identifiers and timestamps.
5. **Zero Imputation Defense**: Verified 0 records replaced missing values with synthetic zeros.
