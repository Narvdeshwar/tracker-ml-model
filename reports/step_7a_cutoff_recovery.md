# Step 7A — Historical IPO Cutoff Recovery and Data Provenance Report

**Date:** October 27, 2026  
**Pipeline Status:** `AUDITED & OPERATIONAL`  
**Completion Verdict:** `CONDITIONAL PASS` (Pipeline operational; 16 cutoffs recovered, 13 conflicts audited, 499 BSE SME records queued for exchange circular ingestion)  
**Dataset Under Review:** 1,515 Indian IPOs (2020–2026) across Mainboard and SME platforms

---

## 1. Executive Summary & Verification Breakdown

In Step 7A, an exhaustive audit and recovery analysis was executed on the 528 IPOs (510 SME, 18 Mainboard) previously lacking verified issue close dates. 

The cutoff recovery dataset has been compiled in `data/processed/ipo_cutoff_recovery.csv` alongside the yearly coverage breakdown `data/processed/step_7a_cutoff_coverage_by_year.csv` and unresolved tracking queue `data/processed/step_7a_unresolved_queue.csv`.

```
+----------------------------------------------------------------------------------------------------+
|                                    STEP 7A CUTOFF RECOVERY SUMMARY                                 |
|                                                                                                    |
|   Total Ingested IPO Master Records            :  1,515 (463 Mainboard, 1,052 SME)                 |
|   Previously Verified Cutoffs (Milestone 1)    :    987 (445 Mainboard,   542 SME)                 |
|   Previously Unresolved Cutoffs                :    528 ( 18 Mainboard,   510 SME)                 |
|                                                                                                    |
|   [✓] Successfully Recovered (Primary Source)  :     16 (  6 Mainboard,    10 SME)                 |
|   [!] Instrument Conflict / Review Required    :     13 ( 10 Mainboard,     3 SME)                 |
|   [-] Retained in Unresolved Queue             :    499 (  2 Mainboard,   497 SME)                 |
|                                                                                                    |
|   New Confirmed Cutoff Cohort                  :  1,003 (451 Mainboard,   552 SME)                 |
|   Automated Unit Test Suite Coverage           :  9/9 Tests Passing (62/62 Repository-Wide)        |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Methodology & Primary Source Cross-Verification

Cutoff recovery was conducted by cross-referencing candidate records against official National Stock Exchange of India (NSE) past issue archives (`IPO-PastIssue-01-01-2020-to-27-10-2026.csv`) and exchange Bhavcopy settlement records:

### Verification Criteria Applied:
1. **Instrument Identity:** The matched instrument must be equity shares (`SECURITY TYPE` = `'EQ'` or `'SME'`). Non-convertible debentures (`N0`, `DEBT`) were rejected and flagged.
2. **Settlement Lag Plausibility:** Historical Indian equity IPO settlement lag between issue closing and exchange listing spans **3 to 12 calendar days** (mean = 5.8 days for SME, 6.8 days for Mainboard). Matches with lags $< 2$ days or $> 15$ days were preserved as conflicts rather than silently accepted.
3. **Price Band & Issue Price Alignment:** The issue price in the master must match or fall within the price band of the primary issue notice.

---

## 3. Detailed Audit of Recovered and Conflicted Records

### A. Recovered Equity IPOs (`VERIFIED_PRIMARY_SOURCE`, $N = 16$)
These records had exact equity instrument matches with plausible listing lags (3–8 days) and identical issue prices:

| IPO ID | Issuer Name | Board | Issue Close Date | Listing Date | Lag Days | Verified Source Reference |
|---|---|:---:|:---:|:---:|:---:|---|
| `bombay-metrics-supply-chain-6ab5d0` | Bombay Metrics Supply Chain Ltd | SME | 2021-10-04 | 2021-10-12 | 8 | NSE Archive (Symbol: `BMETRICS`, Price: ₹93) |
| `chaman-metallics-c42fe2` | Chaman Metallics Ltd | SME | 2023-01-06 | 2023-01-16 | 10 | NSE Archive (Symbol: `CML`, Price: ₹38) |
| `vishnusurya-projects-infra-0f1853` | Vishnusurya Projects and Infra Ltd | SME | 2023-10-05 | 2023-10-10 | 5 | NSE Archive (Symbol: `VISHNUINFR`, Price: ₹68) |
| `akanksha-power-infrastructure-a1a57e` | Akanksha Power & Infrastructure Ltd | SME | 2023-12-29 | 2024-01-03 | 5 | NSE Archive (Symbol: `AKANKSHA`, Price: ₹55) |
| `excellent-wires-packaging-518ddd` | Excellent Wires and Packaging Ltd | SME | 2024-09-13 | 2024-09-19 | 6 | NSE Archive (Symbol: `EXCELLENT`, Price: ₹90) |
| `computer-age-management-services-b007e0` | Computer Age Management Services Ltd | Mainboard | 2020-09-23 | 2020-10-01 | 8 | NSE Archive (Symbol: `CAMS`, Price: ₹1,230) |
| `saatvik-green-energy-e10681` | Saatvik Green Energy Ltd | Mainboard | 2025-09-23 | 2025-09-26 | 3 | NSE Archive (Symbol: `SAATVIK`, Price: ₹465) |
| `leap-india-8d237b` | LEAP India Ltd | Mainboard | 2026-08-11 | 2026-08-14 | 3 | NSE Archive (Symbol: `LEAP`, Price: ₹159) |
| *(+8 Additional Verified Issues)* | — | Both | — | — | 3–8 | Full details in `ipo_cutoff_recovery.csv` |

### B. Flagged Instrument Conflicts (`CONFLICT_REQUIRES_REVIEW`, $N = 13$)
The audit revealed critical cross-instrument matching traps in historical exchange data:

1. **Non-Convertible Debenture (NCD) Collisions ($N = 10$ Mainboard):**
   - In raw exchange databases, public bond offerings share the corporate issuer name. For example, *Tata Capital Limited* has records for `SECURITY TYPE` = `N0` (Symbol: `805TACA29`, Face Value: ₹1,000) closing on 2025-10-08.
   - Similarly, *Akme Fintrade* (`116AFIL29A`), *Northern Arc Capital* (`904NACL28`), *Afcons Infrastructure* (`84AIL28`), and *NTPC Green Energy* (`727NGEL36`) match debt issues with listing dates months or years later.
   - **Resolution:** These records were rejected from cutoff recovery and flagged as `CONFLICT_REQUIRES_REVIEW`.
2. **Partly-Paid / Warrant Collisions ($N = 3$ SME):**
   - *Party Cruisers Limited* matched `PARTYPP` closing on 2021-02-25 with an exchange listing date of 2026-10-21 (a rights/call-money listing, not the original 2021-03-05 IPO listing).
   - *Varanium Cloud* (`CLOUDPP`) and *Rockingdeals* (`ROCKPP`) exhibited identical partly-paid listing anomalies.
   - **Resolution:** Retained in conflict review; original equity IPO cutoff remains unconfirmed.

---

## 4. Before-and-After Cutoff Coverage Analysis

The yearly coverage breakdown from `data/processed/step_7a_cutoff_coverage_by_year.csv` demonstrates the distribution of verified vs. unresolved cutoffs:

| Listing Year | Market Segment | Total IPOs | Verified Cutoffs | Conflict / Review | Unresolved Queue | Final Coverage % |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **2020** | Mainboard | 14 | 14 | 0 | 0 | **100.0%** |
| **2020** | SME | 30 | 7 | 0 | 23 | **23.3%** |
| **2021** | Mainboard | 64 | 62 | 1 | 1 | **96.9%** |
| **2021** | SME | 55 | 21 | 1 | 33 | **38.2%** |
| **2022** | Mainboard | 38 | 37 | 0 | 1 | **97.4%** |
| **2022** | SME | 108 | 54 | 1 | 53 | **50.0%** |
| **2023** | Mainboard | 59 | 57 | 2 | 0 | **96.6%** |
| **2023** | SME | 179 | 117 | 1 | 61 | **65.4%** |
| **2024** | Mainboard | 90 | 86 | 4 | 0 | **95.6%** |
| **2024** | SME | 245 | 178 | 0 | 67 | **72.7%** |
| **2025** | Mainboard | 104 | 101 | 3 | 0 | **97.1%** |
| **2025** | SME | 268 | 117 | 0 | 151 | **43.7%** |
| **2026** | Mainboard | 94 | 94 | 0 | 0 | **100.0%** |
| **2026** | SME | 167 | 58 | 0 | 109 | **34.7%** |
| **Total** | **All Cohorts** | **1,515** | **1,003** | **13** | **499** | **66.2%** |

### Key Observations:
- **Mainboard Cutoffs are near-universal (97.4% overall coverage):** Only 2 IPOs remain unresolved (*IRFC* and *DCX Systems*, pending circular lookup).
- **SME Cutoffs have substantial structural gaps (52.5% overall coverage):** While recovery added 10 verified issues, 497 SME IPOs remain unresolved because they listed exclusively on BSE SME, where circulars are distributed as PDF notices rather than centralized past-issues tables.

---

## 5. Selection Bias & Outcome Divergence Audit

A critical finding from Step 5E and re-verified here is that **missingness is not random** ($p < 0.0001$):

| Market Segment | Cohort Group | Sample Size | Mean Opening Return | Positive Open Rate | Severe Loss Rate ($\le -10\%$) |
|---|---|:---:|:---:|:---:|:---:|
| **Mainboard** | Cutoff Verified | 445 | $+20.72\%$ | $71.91\%$ | $5.62\%$ |
| **Mainboard** | Cutoff Missing | 18 | $+8.98\%$ | $61.11\%$ | $5.56\%$ |
| **SME** | Cutoff Verified | 542 | $+37.57\%$ | $76.38\%$ | $8.49\%$ |
| **SME** | Cutoff Missing | 510 | $+17.43\%$ | $67.25\%$ | **$12.55\%$** |

> **Selection Bias Guardrail:** SME IPOs with missing cutoffs experience **$1.5\times$ higher severe opening losses** ($12.55\%$ vs $8.49\%$) and half the mean opening gain ($+17.43\%$ vs $+37.57\%$). If models are trained exclusively on cutoff-verified records without adjusting for this gap, they will overestimate prospective success rates.

---

## 6. Downstream Anti-Leakage Invariants Enforced

1. **Strict Temporal Separation:** For all verified cutoffs, the cutoff timestamp ($17:00\text{ IST}$ on Issue Close Date) strictly precedes the exchange listing date ($T_{\text{cutoff}} \le T_{\text{listing}} - 2\text{ days}$).
2. **Feature Publication Realism:** Market features (e.g. Nifty 50 close, India VIX) published at $16:00\text{ IST}$ on Day $T$ are eligible for $17:00\text{ IST}$ cutoffs. Any intraday observation published after $17:00\text{ IST}$ remains excluded.
3. **Preservation of Gaps:** Unresolved records remain strictly preserved as `NaN` in feature matrices. Zero synthetic imputation or listing-date substitution is permitted.
4. **Frozen Model Protection:** Serialized model artifact `models/frozen/model_6b_sme_v1.joblib` and its SHA-256 digest (`dbf2eec7...`) remain strictly untouched.

---

## 7. Deliverables & Test Verification

All required Step 7A files have been generated and committed:
1. `data/processed/ipo_cutoff_recovery.csv` (1,515 records with standardized provenance)
2. `data/processed/step_7a_cutoff_coverage_by_year.csv` (Coverage statistics by year and segment)
3. `data/processed/step_7a_unresolved_queue.csv` (512 queued unresolved and conflict records)
4. `reports/step_7a_cutoff_recovery.md` (Formal project report)
5. `tests/test_step_7a.py` (**9/9 unit tests passing**)
6. Full test suite: `python -m unittest discover tests` (**62/62 tests passing, 0 errors**)

---

## 8. Final Completion Status & Recommended Next Step

### Final Completion Status: **CONDITIONAL PASS**
- **Reason:** The recovery pipeline, provenance schema, conflict detection, and unit test suite are fully operational. However, 499 records (497 BSE SME) remain unresolved pending direct BSE circular PDF scraping.
- **Decision:** As mandated by the governance protocol, **no automated retraining or threshold adjustment has been executed**.

### Recommended Next Priority (Step 7B — Subscription Multiples & Provenance):
With cutoff provenance formalized, we recommend advancing to **Step 7B**:
1. Ingest audited subscription multiples (QIB, NII, Retail) with explicit observation timestamps ($17:00\text{ IST}$ Day 1, Day 2, Day 3).
2. Enforce strict anti-lookahead rules (exclude final subscription updates published on Day $T+1$ post-close).
3. Evaluate whether investor demand multiples provide incremental ranking power over the frozen macro-only baseline.
