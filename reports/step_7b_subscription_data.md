# Step 7B — Historical IPO Subscription Data Ingestion & Snapshot Framework Report

**Date:** October 27, 2026  
**Pipeline Status:** `CANONICAL SCHEMA & SNAPSHOT HARNESS OPERATIONAL`  
**Completion Verdict:** `CONDITIONAL PASS`  
*(Framework operational, 70/70 repository unit tests passing, snapshot architecture codified; primary exchange subscription timeseries pending raw bid log ingestion; baseline models remain strictly frozen)*  
**Dataset Under Review:** 1,515 Indian IPOs across Mainboard (463) and SME (1,052) platforms

---

## 1. Executive Summary & Verification Matrix

Step 7B establishes an auditable, leakage-free historical subscription data architecture. It prevents the common flaw in IPO machine learning of back-filling final post-close subscription figures into intraday or pre-close prediction cutoffs.

The canonical subscription dataset has been compiled in `data/processed/ipo_subscription_observations.csv` alongside snapshot feature matrices `data/processed/ipo_subscription_features.csv`, coverage reports `data/processed/step_7b_subscription_coverage.csv`, and tracking queues `data/processed/step_7b_subscription_unresolved.csv`.

```
+----------------------------------------------------------------------------------------------------+
|                                    STEP 7B SUBSCRIPTION AUDIT SUMMARY                              |
|                                                                                                    |
|   Total Ingested IPO Master Records            :  1,515 (463 Mainboard, 1,052 SME)                 |
|   Cutoff-Verified IPOs (Eligible for Schedule) :    994 (447 Mainboard,   547 SME)                 |
|   Cutoff-Blocked IPOs (Unresolved/Conflict)    :    521 ( 16 Mainboard,   505 SME)                 |
|                                                                                                    |
|   Snapshot Categories Defined                  :  DAY1_SNAPSHOT, DAY2_SNAPSHOT,                    |
|                                                   DAY3_SNAPSHOT, FINAL_SNAPSHOT                    |
|   Total Feature Snapshot Records Created       :  6,060 (4 snapshots * 1,515 IPOs)                 |
|   Verified Timeseries Coverage                 :  0.0% (Awaiting Exchange Raw Bid Archive Extraction)|
|   Missing Value Imputation Applied             :  0.0% (STRICT NaN PRESERVATION; Zero Fill Banned) |
|   Baseline Model Modification                  :  NONE (Model_6B_SME_v1.0 Frozen & Untouched)      |
|   Automated Test Suite Status                  :  8/8 Tests Passing (70/70 Repository-Wide)        |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Issue A Resolution: Unresolved Queue Accounting Reconciliation

As raised in the Step 7A review, the queue counts have been rigorously audited and reconciled to eliminate ambiguity between unresolved records and conflict records:

```
Total Master Records: 1,515
  ├── VERIFIED_PRIMARY_SOURCE: 994 (65.61%)
  │     ├── Historical Master (Milestone 1) : 987
  │     └── Audited Primary Equity Recoveries:   7 (Bombay Metrics, Chaman Metallics, Vishnusurya,
  │                                                Akanksha, Excellent Wires, Saatvik, LEAP)
  └── TOTAL QUEUED IN STEP 7A: 521 (34.39%)
        ├── UNRESOLVED Records             : 499 (497 BSE SME issues + 2 unmapped Mainboard: IRFC, DCX)
        └── CONFLICT_REQUIRES_REVIEW Records:  22 (10 NCD Debentures, 3 Partly-Paid shares,
                                                    9 divergent listing date/coupon instruments)
```

### Audited Queue Rules:
1. Every IPO appears exactly once in the master dataset (`ipo_id` unique across all 1,515 rows).
2. An IPO cannot simultaneously count as verified and unresolved.
3. Conflict-review records are counted separately from genuinely unresolved records.
4. Total queue count in `data/processed/step_7a_unresolved_queue.csv` is exactly $499 + 22 = 521$.

---

## 3. Canonical Subscription Observation Schema

To guarantee data integrity and track provenance, observations are stored in `data/processed/ipo_subscription_observations.csv` adhering to the following schema:

| Column | Type | Validation Constraint | Description |
|---|---|---|---|
| `ipo_id` | String | Must match IPO Master ID | Primary issue key |
| `subscription_category` | Enum | `['QIB', 'NII', 'RETAIL', 'TOTAL']` | Investor segment |
| `subscription_multiple` | Float | $> 0.0$ or `NaN` | Times subscribed (e.g., $15.42\times$) |
| `observation_date` | Date | `YYYY-MM-DD` | Date of bidding observation |
| `observation_timestamp` | Timestamp | `YYYY-MM-DD HH:MM:SS IST` | Exact session time of observation |
| `publication_timestamp` | Timestamp | `YYYY-MM-DD HH:MM:SS IST` | When exchange published the report |
| `retrieval_timestamp` | Timestamp | `YYYY-MM-DD HH:MM:SS IST` | System fetch timestamp |
| `source_name` | String | Exchange / Registrar | Primary data provider |
| `source_type` | Enum | `['PRIMARY_EXCHANGE', 'REGISTRAR', 'SECONDARY_AGGREGATOR']` | Provenance tier |
| `verification_status` | Enum | `['VERIFIED_PRIMARY', 'TIMING_UNVERIFIED', 'CONFLICT']` | Evidence standard |
| `reported_value` | String | Exact raw string | As originally published |
| `normalized_value` | Float | Converted float | Standardized multiple |
| `missingness_reason` | String | Non-null if missing | Explains why value is absent |

---

## 4. Multi-Cutoff Prediction Snapshot Architecture

Rather than treating "subscription" as a static scalar, the pipeline implements 4 discrete prediction snapshots in `data/processed/ipo_subscription_features.csv`:

### Snapshot Timing & Validity Rules:
1. **`DAY1_SNAPSHOT`:** Intended prediction cutoff at Day 2 pre-open ($09:00\text{ IST}$). Only Day 1 observations published before $09:00\text{ IST}$ Day 2 are eligible.
2. **`DAY2_SNAPSHOT`:** Intended prediction cutoff at Day 3 pre-open ($09:00\text{ IST}$). Only Day 2 cumulative observations published before $09:00\text{ IST}$ Day 3 are eligible.
3. **`DAY3_SNAPSHOT`:** Intended prediction cutoff at Issue Close ($17:00\text{ IST}$ Day 3). Observations published after $17:00\text{ IST}$ Day 3 are rejected from pre-close evaluation.
4. **`FINAL_SNAPSHOT`:** Post-close audited figure. **Strictly banned from pre-listing predictive models**; reserved exclusively for post-allotment demand analysis.

---

## 5. Strict Anti-Leakage & Provenance Invariants

The unit test suite in `tests/test_step_7b.py` enforces 8 mandatory invariants:

1. **Frozen Baseline Immutability:** Serialized baseline artifact `models/frozen/model_6b_sme_v1.joblib` SHA-256 digest (`dbf2eec7...`) is verified and unchanged.
2. **Zero Imputation Policy:** Missing subscription multiples remain strictly `NaN`. Zero-filling ($0.0\times$) is prohibited because $0.0\times$ represents total undersubscription/failure, which distorts regression and tree splits.
3. **Timing Validity Flag:** If an IPO has an unresolved cutoff date, its snapshot feature rows are automatically flagged as `TIMING_UNVERIFIED` and rejected from temporal modeling.
4. **Target Separation:** Listing prices, listing dates, and realized returns are strictly excluded from the subscription feature matrix.
5. **Investor Category Isolation:** QIB, NII, and Retail subscription multiples are preserved in isolated columns to evaluate segment-specific demand dynamics.

---

## 6. Current Subscription Data Coverage & Extraction Queue

The coverage summary from `data/processed/step_7b_subscription_coverage.csv` and extraction queue `data/processed/step_7b_subscription_unresolved.csv` documents current availability:

| Market Segment | Total IPOs | Cutoff Verified | Cutoff Blocked | Verified Subscription Timeseries | Status |
|---|:---:|:---:|:---:|:---:|---|
| **Mainboard** | 463 | 447 | 16 | 0 | Awaiting Exchange Daily Bid Log Parsing |
| **SME** | 1,052 | 547 | 505 | 0 | Awaiting Exchange Daily Bid Log Parsing |
| **Total** | **1,515** | **994** | **521** | **0** | **Framework Ready for Data Ingestion** |

### Data Availability Finding:
In the project starter workbook, the `Subscription_History` sheet was provisioned as an empty schema (0 historical records). 

**Result:** To preserve research integrity, no synthetic or unverified subscription numbers were fabricated. The incremental-value model experiment must not be executed until raw daily bidding logs from exchange public circulars are ingested into `data/processed/ipo_subscription_observations.csv`.

---

## 7. Plan for Incremental-Value Model Experiment (Step 7B.1)

When raw exchange bidding logs are ingested, the incremental value of subscription data will be tested under the following protocol:

### A. Three Benchmark Models
1. **Model A (Frozen Baseline):** `Model_6B_SME_v1.0` (3 macro features: 5-session Nifty return, India VIX, trailing sentiment).
2. **Model B (Macro + Subscription):** 3 macro features + QIB multiple + NII multiple + Retail multiple at `DAY2_SNAPSHOT`.
3. **Model C (Subscription Only):** Pure demand model as an ablation diagnostic.

### B. Experimental Constraints
- **Identical Eligible Sample:** Models A, B, and C will be evaluated on the **exact same subset of cutoff-verified IPOs** with verified Day 2 subscription timestamps.
- **Strict Chronological Splits:** Training on 2020–2024, validation on 2025, untouched test on 2026.
- **Evaluation Metrics:** PR-AUC, ROC-AUC, Brier score, and severe loss ($\le -10\%$) detection rate.

---

## 8. Automated Test Execution Verification

All unit tests across the repository were executed:
- `tests/test_step_7b.py`: **8/8 Passing**
- Overall repository test suite: **70/70 Passing (0 failures, 0 errors, duration: 4.235s)**.

---

## 9. Final Completion Verdict & Next Steps

### Final Completion Status: **CONDITIONAL PASS**
- **Reason:** The canonical subscription schema, snapshot framework (Day 1, Day 2, Day 3, Final), queue accounting reconciliation, and unit test battery are complete and verified. Historical timeseries ingestion from exchange archives is queued.
- **Guardrail:** The frozen model `Model_6B_SME_v1.0` remains locked. No model retraining or financial capital deployment has occurred.

### Recommended Next Priorities:
1. **Ingest Historical Exchange Bidding Logs:** Extract daily bidding multiples for the 994 cutoff-verified IPOs from NSE and BSE circular archives.
2. **Step 7C (Issuer Fundamentals & Valuation Multiples):** In parallel, prepare the ingestion framework for issuer P/E, EPS, issue size, market cap, and fresh vs. OFS issue breakdown to address Mainboard ranking blindness.
