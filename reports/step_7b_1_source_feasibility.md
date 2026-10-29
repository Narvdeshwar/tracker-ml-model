# Step 7B.1 — Source Feasibility Study: Historical IPO Subscription Data

**Date:** October 27, 2026  
**Auditor:** Antigravity Research & Verification Engine  
**Project:** Indian IPO Listing-Gain Machine Learning Research  
**Target:** Historical Subscription Ingestion across 1,515 IPOs (994 Cutoff-Verified Issues)

---

## 1. Executive Summary: The Subscription Data Dilemma

In equity machine learning research, investor subscription demand (QIB, NII, Retail) is frequently proposed as a strong predictive signal. However, our feasibility audit reveals a fundamental structural difference between **Final Subscription Summaries** and **Intraday / Cumulative Historical Snapshots**:

```
+----------------------------------------------------------------------------------------------------+
|                                  SUBSCRIPTION SOURCE FEASIBILITY MATRIX                            |
|                                                                                                    |
|  Dimension                  | Final Basis of Allotment       | Intraday / Daily Bid Logs (Day 1-3) |
|-----------------------------+--------------------------------+-------------------------------------|
|  Primary Exchange Provider  | NSE / BSE / Registrar Archive  | NSE / BSE Consolidated Bid Details  |
|  Availability Timing        | Day T+1 to T+3 Post-Close      | Day 1, Day 2, Day 3 at 17:00 IST    |
|  Temporal Leakage Risk      | SEVERE (Must NOT enter pre-    | ZERO (Eligible if timestamped and   |
|                             | listing prediction cutoffs)    | verified pre-close)                 |
|  Historical Depth (Online)  | High (Accessible via circulars)| Very Low (Intraday bid books not   |
|                             |                                | preserved in static public CSVs)    |
|  Current Local Repository   | 0 records in local storage     | 0 records in local storage          |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. In-Depth Evaluation of Primary & Secondary Sources

### A. Source 1: NSE Consolidated Bid Details & Past Issues Portal
- **Provider:** National Stock Exchange of India (`nseindia.com`)
- **Document Type:** Daily Cumulative Bidding Reports (`.html` / `.json` API)
- **Content:** Total bids received across QIB (excluding anchor), Non-Institutional (NII), and Retail Individual Investors (RII).
- **Publication Schedule:** Published at approximately $17:30\text{ to }18:30\text{ IST}$ on each bidding day.
- **Feasibility & Limitations:**
  - Active issues have live scraping endpoints.
  - **Historical Archive Limitation:** Historical day-by-day bidding updates from 2020–2023 are **not maintained as open bulk CSV downloads**. NSE archives only the *Past Issues* summary table (which lists price and dates, but omits subscription multiples).
  - Bulk historical retrieval requires querying archived registrar allotments or commercial data licenses (e.g. Accord Fintech / CMIE Prowess).

### B. Source 2: BSE SME Bidding Data & Public Issue Notices
- **Provider:** Bombay Stock Exchange (`bseindia.com`)
- **Document Type:** Individual SME Public Issue Circulars (`.pdf`)
- **Content:** Final Basis of Allotment notices stating total valid applications and times subscribed.
- **Publication Schedule:** Published $2\text{ to }4\text{ days}$ post-issue close, prior to listing.
- **Feasibility & Limitations:**
  - Day 1 and Day 2 snapshots are **absent** from exchange circular PDFs (only final cumulative subscription is recorded in the basis of allotment).
  - For the 497 BSE SME-exclusive issues in our dataset, intraday bidding logs are completely unobservable historically from public circulars.

### C. Source 3: Registrar Allotment Archives (Link Intime, KFintech, Bigshare)
- **Provider:** Official Registrars to the Issue
- **Document Type:** Basis of Allotment Press Notices
- **Content:** Audited shares offered vs. shares bid by category (QIB, Corporate/NII, Retail).
- **Feasibility & Limitations:**
  - Highest evidence standard for final subscription (`VERIFIED_PRIMARY`).
  - **Severe Temporal Restriction:** Because registrars compute these figures during allotment ($T+2\text{ days}$ after issue close), this data is **prohibited** from entering Day 1, Day 2, or Day 3 pre-close prediction cutoffs.

### D. Source 4: Secondary Aggregators (Chittorgarh / IPO Watch / Prime Database)
- **Provider:** Commercial Aggregators
- **Content:** Historical Day 1, Day 2, and Day 3 demand estimates.
- **Feasibility & Limitations:**
  - Often capture day-end subscription multiples for historical IPOs.
  - **Provenance Limitation:** Secondary aggregator figures often lack auditable publication timestamps and frequently revise Day 2 provisional figures retrospectively when final registrar numbers are published.
  - Under project governance, secondary sources must be tagged as `VERIFIED_SECONDARY` and excluded from strict primary-source benchmark cohorts.

---

## 3. The 30-IPO Pilot Protocol

To test the feasibility of historical subscription extraction, a balanced pilot cohort of **30 IPOs** has been selected and saved to `data/processed/step_7b_1_pilot_sample_30.csv`:
- **Stratification:** Exactly 15 Mainboard and 15 SME IPOs across 7 calendar years (2020 through 2026).
- **Cutoff Eligibility:** 100% of pilot IPOs have verified primary-source cutoffs (`VERIFIED_PRIMARY_SOURCE`).
- **Target Ingestion Battery:** For each pilot issue, we attempt to locate primary or secondary records for:
  1. `DAY1_SNAPSHOT` (Day 1 demand at $17:00\text{ IST}$)
  2. `DAY2_SNAPSHOT` (Day 2 cumulative demand at $17:00\text{ IST}$)
  3. `DAY3_SNAPSHOT` (Day 3 pre-close demand)
  4. `FINAL_SNAPSHOT` (Post-close basis of allotment)

---

## 4. Key Strategic Recommendations

1. **Do Not Synthesize Data:** Never fabricate intraday subscription multiples or assume Day 2 equals a fraction of the final subscription.
2. **Treat Final Subscription as an Upper-Bound Benchmark:** Final subscription multiples can be evaluated in Step 8 to establish the theoretical maximum predictive value of investor demand, but must be explicitly labeled as a retrospective upper-bound experiment.
3. **Prioritize Issuer Fundamentals in Step 7C:** While historical daily bidding logs are difficult to recover from public exchange archives for older SME issues, **issuer fundamentals (P/E, revenue, issue size, OFS%) are universally documented in filed prospectuses (DRHP/RHP)**. Advancing Step 7C in parallel will yield higher data recovery rates.
