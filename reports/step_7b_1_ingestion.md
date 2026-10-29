# Step 7B.1 — Historical Subscription Ingestion & Pilot Audit Report

**Date:** October 27, 2026  
**Pipeline Status:** `AUDITED & PILOT EVALUATED`  
**Completion Verdict:** `CONDITIONAL PASS`  
*(Source feasibility audited, 30-IPO pilot verified, 76/76 unit tests passing; intraday bid books confirmed absent from static public archives; baseline model preserved untouched; strategic shift recommended)*  
**Dataset Under Review:** 1,515 Indian IPOs (994 Cutoff-Verified Issues)

---

## 1. Executive Summary & Verification Matrix

In Step 7B.1, we transitioned from abstract framework design to empirical feasibility verification. We audited primary exchange records, public circulars, and registrar archives to determine how much genuine historical subscription data can be recovered.

All deliverables have been compiled:
- `reports/step_7b_1_source_feasibility.md` (Detailed Source Feasibility Study)
- `data/processed/step_7b_1_pilot_sample_30.csv` (Stratified Pilot Cohort of 30 IPOs)
- `data/processed/step_7b_1_ingestion_audit.csv` (120 Pilot Snapshot Evaluations)
- `data/processed/step_7b_1_source_coverage.csv` (Yearly & Segment Coverage Matrix)
- `data/processed/step_7b_1_unresolved_queue.csv` (Prioritized Extraction Queue)
- `tests/test_step_7b_1.py` (6/6 tests passing; 76/76 repository-wide)

```
+----------------------------------------------------------------------------------------------------+
|                                    STEP 7B.1 PILOT AUDIT SUMMARY                                   |
|                                                                                                    |
|   Total Ingested IPO Master Records            :  1,515 (463 Mainboard, 1,052 SME)                 |
|   Cutoff-Verified Eligible Issues              :    994 (447 Mainboard,   547 SME)                 |
|   Pilot Sample Size                            :     30 ( 15 Mainboard,    15 SME; 2020–2026)      |
|                                                                                                    |
|   Snapshot Categories Evaluated                :  Day 1, Day 2, Day 3 Pre-Close, Final Basis       |
|   Intraday Bidding Log Coverage (Static CSV)   :   0.0% (Omitted from exchange public past-issues) |
|   Final Basis of Allotment Documented          : 100.0% (Available in Registrar Allotment Notices) |
|   Final Allotment Usability for Pre-Listing ML : STRICTLY BANNED (Published T+2 Post-Close)        |
|   Baseline Model Modification                  :   NONE (Model_6B_SME_v1.0 Frozen & Untouched)     |
|   Automated Unit Test Status                   :  6/6 Tests Passing (76/76 Repository-Wide)        |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Key Empirical Findings: Source Feasibility & The "Intraday Void"

Our feasibility audit evaluated primary exchanges (NSE, BSE), statutory registrars (Link Intime, KFintech, Bigshare), and secondary aggregators:

### Critical Provenance Limitations Identified:
1. **The Intraday Void in Public Exchange Records:**
   - Both the NSE Past Issues portal and BSE circular archives preserve only the *final summary* or static prospectus data.
   - The consolidated live bid book—which tallies hourly or daily cumulative bids for QIB, NII, and Retail during the 3-day issue—is **not archived as a historical time series in open exchange reports**.
   - Consequently, true historical `DAY1_SNAPSHOT` and `DAY2_SNAPSHOT` multiples for 2020–2024 cannot be retrieved without specialized commercial historical tick/bid data licenses (e.g. CMIE Prowess or Accord Fintech).
2. **The "Final Subscription" Lookahead Trap:**
   - Final subscription figures (e.g. "Over-subscribed $85\times$") are universally documented in registrar basis of allotment notices.
   - **However, these figures are certified and published on Day $T+2$ or $T+3$ after bidding closes.**
   - In accordance with research integrity standards, feeding final subscription multiples into a model intended to make decisions at issue close ($17:00\text{ IST}$ Day 3) represents **severe lookahead leakage**.
   - As verified in `tests/test_step_7b_1.py`, final subscription multiples are marked `STRICTLY_BANNED_FROM_PRE_LISTING_PREDICTION`.

---

## 3. The 30-IPO Stratified Pilot Results

A balanced pilot of 30 IPOs was evaluated in `data/processed/step_7b_1_ingestion_audit.csv`:

| Snapshot Type | Pilot IPOs Evaluated | Verified Primary Observations Found | Audit & Governance Status | Temporal Validity |
|---|:---:|:---:|---|---|
| **`DAY1_SNAPSHOT`** | 30 | 0 | `UNAVAILABLE_IN_STATIC_ARCHIVE` | `EXCLUDED_FROM_EVALUATION` |
| **`DAY2_SNAPSHOT`** | 30 | 0 | `UNAVAILABLE_IN_STATIC_ARCHIVE` | `EXCLUDED_FROM_EVALUATION` |
| **`DAY3_SNAPSHOT`** | 30 | 0 | `UNAVAILABLE_IN_STATIC_ARCHIVE` | `EXCLUDED_FROM_EVALUATION` |
| **`FINAL_SNAPSHOT`** | 30 | 30 (Documented) | `PENDING_REGISTRAR_PARSING` | `STRICTLY_BANNED_FROM_PRE_LISTING` |

### Pilot Finding:
Not a single IPO in the pilot possessed verifiable, primary-source day-by-day bid books in static public CSV archives. To claim that we have historical Day 1 or Day 2 subscription data would require fabricating numbers or using unverified secondary aggregator snapshots that lack verifiable publication timestamps.

In accordance with user guidelines, **no data was fabricated, and missing values remain strictly `NaN`**.

---

## 4. Coverage Matrix & Unresolved Queue Accounting

The complete coverage distribution across cohort years is documented in `data/processed/step_7b_1_source_coverage.csv`:

| Cohort Year | Market Segment | Total IPOs | Cutoff Verified | Primary Intraday Bids | Primary Final Allotment | Feasibility Status |
|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **2020** | Mainboard / SME | 44 | 20 | 0 | 20 | Intraday Bid Logs Unavailable Without Commercial Feed |
| **2021** | Mainboard / SME | 119 | 83 | 0 | 83 | Intraday Bid Logs Unavailable Without Commercial Feed |
| **2022** | Mainboard / SME | 146 | 89 | 0 | 89 | Intraday Bid Logs Unavailable Without Commercial Feed |
| **2023** | Mainboard / SME | 238 | 173 | 0 | 173 | Intraday Bid Logs Unavailable Without Commercial Feed |
| **2024** | Mainboard / SME | 335 | 262 | 0 | 262 | Intraday Bid Logs Unavailable Without Commercial Feed |
| **2025** | Mainboard / SME | 372 | 216 | 0 | 216 | Intraday Bid Logs Unavailable Without Commercial Feed |
| **2026** | Mainboard / SME | 261 | 151 | 0 | 151 | Intraday Bid Logs Unavailable Without Commercial Feed |
| **Total** | **All Cohorts** | **1,515** | **994** | **0** | **994** | **Intraday Timeseries = 0.0% Available** |

The 1,515 IPOs are tracked in `data/processed/step_7b_1_unresolved_queue.csv`:
- **994 Cutoff-Verified Issues:** `AWAITING_EXCHANGE_BID_LOG_SOURCE`
- **521 Blocked Issues:** `BLOCKED_BY_UNRESOLVED_CUTOFF` (Must resolve issue open/close dates first)

---

## 5. Answers to the Core Audit Questions

1. **How many IPOs have verified QIB, NII, and retail subscription observations?**
   - **0 / 1,515** for pre-close prediction snapshots. Final basis of allotment figures exist in registrar files for the 994 verified issues, but cannot be used before listing.
2. **How many observations have trustworthy publication timestamps?**
   - **0** for intraday bidding snapshots in the public CSV records.
3. **How much data is available separately for Day 1, Day 2, and Day 3 predictions?**
   - **0.0%** across all historical years. The public exchange archives purge daily bid books post-listing.
4. **Does the enriched dataset improve performance compared with the macro-only baseline?**
   - **Empirical evaluation cannot be run honestly without data.** Running an ML model on backfilled final multiples would produce artificially inflated accuracy driven entirely by lookahead bias.
5. **Does the improvement survive chronological testing?**
   - N/A until genuine timestamped bid logs are acquired.

---

## 6. Strategic Pivot & Recommendation: Advance to Step 7C (Issuer Fundamentals)

Given that historical daily subscription bid logs are unavailable in open public exchange records without commercial licenses, continuing to pursue daily subscription timeseries risks stagnation or fabricating data.

In contrast, **Issuer Fundamentals (Step 7C) represent universally available, legally mandated historical disclosures**:

### Strategic Recommendations:
1. **Maintain Subscription Architecture for Prospective Shadow Logging:** The snapshot framework built in Step 7B will capture **live** Day 1, Day 2, and Day 3 subscription data as upcoming prospective IPOs bid, where live exchange APIs are operational.
2. **Advance Immediately to Step 7C (Issuer Fundamentals & Valuation Ingestion):** Ingest P/E multiples relative to peer medians, EPS, revenue growth, issue size, market cap, and fresh vs. OFS share breakdown from filed prospectuses. This directly targets the Mainboard ranking failure and downside risk detection identified in Step 6A.
