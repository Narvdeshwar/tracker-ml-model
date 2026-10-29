# Step 7D — Feature Dictionary: Valuation, Financial Quality & Governance

**Date:** October 27, 2026  
**Version:** `v2.0 (Step 7D Unified Schema)`  
**Scope:** Canonical Financial Ratios, P/E Valuation Multiples, Balance Sheet Leverage, Issue Size, and Provenance

---

## 1. Feature Specifications

| Feature Name | Feature Group | Units | Source Document Reference | Calculation / Formula | Temporal Guardrail |
|---|---|:---:|---|---|---|
| `issue_price_inr` | Valuation | INR | Price Band Notice / Prospectus | Certified final allotment price | Available $\ge 2\text{ business days}$ prior to open |
| `price_band_spread_pct` | Issue Structure | $\%$ | Price Band Notice | $100 \times (\text{high\_band} - \text{low\_band}) / \text{low\_band}$ | Available $\ge 2\text{ business days}$ prior to open |
| `is_fixed_price_issue` | Issue Structure | Binary | Exchange Issue Notice | $1$ if $\text{low\_band} == \text{high\_band}$ else $0$ | Available $\ge 2\text{ business days}$ prior to open |
| `issue_size_cr` | Scale | ₹ Cr | Statutory RHP Section *The Offer* | Total gross public proceeds | Disclosed in RHP filed before open |
| `fresh_issue_pct` | Issue Structure | $\%$ | Statutory RHP Capital Structure | $100 \times (\text{fresh\_issue\_cr} / \text{issue\_size\_cr})$ | Disclosed in RHP filed before open |
| `ofs_pct` | Issue Structure | $\%$ | Statutory RHP Capital Structure | $100 \times (\text{ofs\_cr} / \text{issue\_size\_cr})$ | Disclosed in RHP filed before open |
| `restated_eps_inr` | Earnings | INR | RHP Section *Basis for Issue Price* | Basic EPS of trailing audited fiscal year | Pre-issue audited financial statement |
| `issue_pe_multiple` | Valuation | Multiplier | RHP Section *Basis for Issue Price* | $\text{Issue Price} / \text{Restated EPS}$ | Pre-issue audited multiple |
| `peer_median_pe` | Valuation | Multiplier | RHP Section *Basis for Issue Price* | Median P/E of listed comparable peers | Pre-issue peer multiple at announcement |
| `pe_premium_to_peers_pct`| Valuation | $\%$ | Derived from RHP disclosures | $100 \times (\text{issue\_pe} - \text{peer\_median}) / \text{peer\_median}$| Derived strictly from RHP inputs |
| `pat_margin_pct` | Profitability | $\%$ | RHP Restated Financials | $100 \times (\text{PAT} / \text{Total Revenue})$ | Trailing audited fiscal year in RHP |
| `debt_to_equity` | Leverage | Multiplier | RHP Capital Structure / Financials | $\text{Total Borrowings} / \text{Net Worth}$ | Pre-issue audited balance sheet |

---

## 2. Ingestion & Quality Control Rules

1. **Negative Earnings Handling:** For companies reporting negative restated EPS (loss-making), `issue_pe_multiple` and `pe_premium_to_peers_pct` are undefined (`NaN`) and flagged with `negative_earnings_flag = 1`.
2. **Peer Group Continuity:** Peer companies must be identical to those cited in the statutory offer document approved by SEBI. No retrospective peer substitution is permitted.
3. **Audit Trail Requirement:** Every observation carries `document_publication_date` and `prediction_cutoff_timestamp`. Any observation published after the prediction cutoff is marked `TIMING_UNVERIFIED` and excluded from model matrices.
