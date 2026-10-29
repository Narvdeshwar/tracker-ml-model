# Step 5B Validation Report: IPO Market Feature Alignment

## 1. Executive Summary

Step 5B has been implemented and validated inside the repository. The feature join strictly enforces **backward-only alignment** to prevent lookahead leakage into downstream statistical analysis and machine learning models:
- **Output Dataset**: `data/processed/ipo_market_features.csv`
- **Workbook Sheet Added**: `Indian_IPO_ML_Research_Starter.xlsx` (`IPO_Market_Features` sheet with 1,515 rows and 40 columns).
- **Core Pipeline Script**: `src/build_ipo_market_features.py`
- **Automated Test Suite**: `tests/test_ipo_market_features.py` (All 5 test suites passed: row preservation, unresolved cutoff discipline, backward-only anti-leakage guarantee, market value fidelity, board segment separation).

---

## 2. Records Ingested & Cutoff Status

- **Total IPO Master Records**: 1,515 (463 Mainboard, 1,052 SME)
- **Unique IPO Identifiers (`ipo_id`)**: 1,515 (0 duplicates, 0 dropped records)
- **Cutoff Policy**: `issue_close_date_after_required_data_available`
  - **Verified Cutoffs**: **987** records (445 Mainboard, 542 SME)
  - **Unresolved Cutoffs**: **528** records (18 Mainboard, 510 SME)
- **Discipline on Unresolved Cutoffs**: Preserved without synthetic inference or duration guesswork. All unresolved records have `prediction_cutoff_date = None` and feature values set to `NaN` with `feature_missing_reason = 'Unresolved prediction cutoff date'`.

---

## 3. Strict Anti-Leakage Verification

1. **Backward-Only Rule Check**:
   $$\text{source\_observation\_date} \le \text{prediction\_cutoff\_date}$$
   - **Records with Observation Date > Cutoff Date**: **0 (0.0%)** (100% compliant).
2. **Observation Age Statistics** (for the 987 verified cutoffs):
   - **Calendar Days Age**: Mean = 0.0 days (all 987 cutoff dates coincided with active trading sessions).
   - **Session Age**: 0 sessions lag from the latest valid settlement.
   - **Earliest Cutoff Date**: `2020-01-17`
   - **Latest Cutoff Date**: `2026-09-30`

---

## 4. Coverage by Market Segment & Index

### Mainboard IPOs (Total: 463)
- Verified Cutoffs: 445 (96.1%)
- Unresolved Cutoffs: 18 (3.9%)
- `nifty50_return_5s` coverage: 445 (100% of verified)
- `nifty500_return_5s` coverage: 445 (100% of verified)
- `india_vix_level_at_cutoff` coverage: 443 (99.6% of verified; 2 missing VIX exchange computation sessions)

### SME IPOs (Total: 1,052)
- Verified Cutoffs: 542 (51.5%)
- Unresolved Cutoffs: 510 (48.5% — BSE SME direct listings pending circular date verification)
- `nifty50_return_5s` coverage: 542 (100% of verified)
- `nifty_sme_emerge_return_5s` coverage: 540 (99.6% of verified)
- `bse_sme_ipo_return_5s` coverage: 539 (99.4% of verified)

*Segment Rule*: Broad market features are available across both segments, while SME index metrics are retained separately without cross-substitution.

---

## 5. Predictor vs Target Segregation

In strict accordance with anti-leakage best practices:
- Predictor columns capture pre-issue market levels and returns (`nifty50_return_1d`, `nifty50_return_5s`, `nifty50_return_20s`, `india_vix_change_5s`, etc.).
- Target variables (`target_listing_open_return_pct`, `target_listing_close_return_pct`) are explicitly prefixed and segregated to prevent accidental inclusion as features.

---

## 6. Next Steps for Step 5C

1. Ingest verified subscription history (QIB, NII, Retail subscription multiples at issue close).
2. Ingest timestamped GMP observations (strictly pre-close vs post-close tracking).
3. Compute the **Recent IPO Sentiment** indicator across the preceding 5 and 10 IPOs whose listings occurred strictly prior to each cutoff.
