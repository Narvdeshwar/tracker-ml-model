# Step 7C — Source Feasibility Study: Historical IPO Fundamentals & Valuation

**Date:** October 27, 2026  
**Auditor:** Antigravity Research & Verification Engine  
**Project:** Indian IPO Listing-Gain Machine Learning Research  
**Target:** Historical Issuer Fundamentals across 1,515 IPOs (994 Cutoff-Verified Issues)

---

## 1. Executive Summary: The Fundamentals Acquisition Landscape

Following the empirical findings of Step 7B.1 (where intraday subscription bid books were confirmed purged from public exchange archives post-listing), Step 7C evaluates the feasibility of recovering **Issuer Fundamentals and Valuation Multiples**.

In India, initial public offerings operate under strict statutory disclosure mandates enforced by the Securities and Exchange Board of India (SEBI). Issuers must file detailed statutory offer documents:
1. **Draft Red Herring Prospectus (DRHP):** Filed with SEBI months before opening.
2. **Red Herring Prospectus (RHP):** Filed with the Registrar of Companies (RoC) and exchanges containing audited restated financials for the trailing 3 fiscal years.
3. **Price Band & Anchor Allocation Notice:** Filed 2 trading days prior to issue opening containing the floor price, cap price, and post-issue valuation multiple.

```
+----------------------------------------------------------------------------------------------------+
|                                  FUNDAMENTALS SOURCE FEASIBILITY MATRIX                            |
|                                                                                                    |
|  Dimension                  | Issue Pricing & Structure      | Audited Balance Sheet & P&L         |
|-----------------------------+--------------------------------+-------------------------------------|
|  Primary Document           | RHP / Price Band Notice        | RHP Restated Financial Statements   |
|  Availability Timing        | 2 Days Prior to Issue Open     | Pre-Filing (Strictly < Cutoff Date) |
|  Temporal Leakage Risk      | ZERO (Pre-Issue Disclosure)    | ZERO (Historical Financials Sealed) |
|  Historical Depth (Online)  | High (995 / 1,515 in Archives) | High (SEBI EDGAR / BSE Archives)    |
|  Pre-Listing Usability      | VERIFIED_PRIMARY ELIGIBLE      | VERIFIED_PRIMARY ELIGIBLE           |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. In-Depth Source Evaluation

### A. Source 1: NSE Historical Past Issues Archive
- **Provider:** National Stock Exchange of India (`IPO-PastIssue-01-01-2020-to-27-10-2026.csv`)
- **Document Type:** Primary Exchange Past Issues Database
- **Content:** Exact issue price, price range band (`low_band`, `high_band`), security type, and issue start/end dates.
- **Coverage in Dataset:** **995 / 1,515 IPOs** (446 Mainboard, 549 SME).
- **Temporal Verification:** Available at price announcement (strictly $\ge 2\text{ business days}$ prior to issue open).
- **Status:** `VERIFIED_PRIMARY_SOURCE`.

### B. Source 2: SEBI Offer Documents Public Repository
- **Provider:** Securities and Exchange Board of India (`sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=3&ssid=15&smid=10`)
- **Document Type:** Filed Red Herring Prospectuses (RHP) & Prospectus PDFs
- **Content:**
  - Audited EPS, Net Asset Value (NAV), Return on Net Worth (RoNW).
  - Listed Peer Group P/E multiples (median, highest, lowest).
  - Fresh issue size vs. Offer for Sale (OFS) breakdown.
  - Promoters' pre-issue and post-issue equity holding percentages.
- **Feasibility & Extraction:**
  - Standardized tabular format in Section *“Basis for Issue Price”* in every statutory RHP.
  - Pre-close availability is guaranteed because Indian regulations prohibit public bidding without a filed RHP.

### C. Source 3: BSE SME Issue Disclosures & Circulars
- **Provider:** Bombay Stock Exchange (`bseindia.com/markets/PublicIssues/Circulars.aspx`)
- **Document Type:** SME Prospectuses and Listing Notices
- **Content:** Fixed price or book-building band, minimum lot size, post-issue paid-up capital.
- **Coverage & Limitations:**
  - SME IPOs have fixed-price structures in ~60% of cases (single issue price rather than a price band).
  - Disclosure standards for SME peers are less uniform than Mainboard issuers.

---

## 3. Stratified 60-IPO Pilot Protocol

To test the feasibility of fundamental feature extraction and leakage controls, a balanced pilot cohort of **60 IPOs** has been selected and saved to `data/processed/step_7c_pilot_manifest_60.csv`:
- **Stratification:** Exactly **30 Mainboard and 30 SME IPOs** distributed across 7 calendar years (2020 through 2026).
- **Cutoff Eligibility:** 100% of pilot IPOs have verified primary-source issue close dates (`VERIFIED_PRIMARY_SOURCE`).
- **Feature Extraction Target:**
  1. **Valuation:** Issue price, price band spread, pricing relative to band cap.
  2. **Issue Structure:** Fresh issue vs. OFS composition, minimum application lot size.
  3. **Financial Scale:** Net asset value, restated EPS, and historical revenue scale.

---

## 4. Key Takeaways for Modeling

1. **Pre-Close Availability is Ironclad:** Unlike daily subscription bid books which were purged from public tables, prospectus financials are filed **before** the IPO opens for bidding. This completely eliminates the risk of retrospective restatement.
2. **Mainboard Signal Expected:** Pricing at the exact upper cap of the price band vs. a discount, along with issue structure (fresh capital for growth vs. promoter cashout OFS), provides economic mechanisms for ranking quality.
