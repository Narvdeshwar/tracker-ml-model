# Step 7C — Feature Dictionary: Issuer Fundamentals & Valuation

**Date:** October 27, 2026  
**Version:** `v1.0`  
**Schema Scope:** Historical Issuer Fundamentals, Valuation Multiples, Issue Structure, and Provenance

---

## 1. Feature Specifications

| Feature Name | Category | Data Type | Units / Range | Formula / Definition | Temporal Availability Requirement |
|---|---|---|---|---|---|
| `issue_price_inr` | Valuation | Float | INR ($\ge 1.0$) | Final certified issue price per equity share | Announced at Issue Open ($T_{\text{open}}$) |
| `price_band_low_inr` | Valuation | Float | INR ($\ge 1.0$) | Floor price of the book-building price band | Announced at least 2 days prior to open |
| `price_band_high_inr` | Valuation | Float | INR ($\ge 1.0$) | Cap price of the book-building price band | Announced at least 2 days prior to open |
| `price_band_spread_pct` | Valuation | Float | $\%$ ($\ge 0.0$) | $100 \times (\text{high\_band} - \text{low\_band}) / \text{low\_band}$ | Announced at least 2 days prior to open |
| `issue_priced_at_cap` | Valuation | Binary | $\{0, 1\}$ | $1$ if `issue_price_inr == price_band_high_inr` else $0$ | Determined at Issue Close ($17:00\text{ IST}$) |
| `is_fixed_price_issue` | Issue Structure | Binary | $\{0, 1\}$ | $1$ if `price_band_low_inr == price_band_high_inr` else $0$ | Fixed price issue common in SME issues |
| `issue_size_cr` | Issue Structure | Float | ₹ Crores | Total public issue size | Documented in Statutory RHP |
| `fresh_issue_cr` | Issue Structure | Float | ₹ Crores | New capital raised by issuer for expansion | Documented in Statutory RHP |
| `ofs_cr` | Issue Structure | Float | ₹ Crores | Offer for Sale (secondary sale by existing promoters) | Documented in Statutory RHP |
| `fresh_issue_pct` | Issue Structure | Float | $\%$ ($0 \text{ to } 100$) | $100 \times (\text{fresh\_issue\_cr} / \text{issue\_size\_cr})$ | Documented in Statutory RHP |
| `ofs_pct` | Issue Structure | Float | $\%$ ($0 \text{ to } 100$) | $100 \times (\text{ofs\_cr} / \text{issue\_size\_cr})$ | Documented in Statutory RHP |
| `promoter_holding_pre_pct` | Governance | Float | $\%$ ($0 \text{ to } 100$) | Promoter equity percentage prior to issue | Disclosed in Capital Structure section of RHP |
| `promoter_holding_post_pct` | Governance | Float | $\%$ ($0 \text{ to } 100$) | Diluted promoter equity percentage post-issue | Disclosed in Capital Structure section of RHP |
| `eps_inr` | Financial Scale | Float | INR / share | Basic Earnings Per Share (restated trailing FY) | Basis for Issue Price in RHP |
| `issue_pe` | Valuation | Float | Multiplier | $\text{Issue Price} / \text{Restated EPS}$ | Basis for Issue Price in RHP |
| `peer_median_pe` | Valuation | Float | Multiplier | Median P/E of listed industry peers disclosed in RHP | Basis for Issue Price in RHP |
| `pe_premium_to_peers_pct` | Valuation | Float | $\%$ | $100 \times (\text{issue\_pe} - \text{peer\_median\_pe}) / \text{peer\_median\_pe}$ | Derived relative valuation |

---

## 2. Provenance & Verification Metadata Fields

Every record in the raw fundamentals extraction table carries:
1. `ipo_id`: Unique canonical issue identifier.
2. `source_document`: Document name (e.g., `NSE Past Issues Archive`, `SEBI Statutory RHP`).
3. `source_publication_timestamp`: Date and time when the document was published.
4. `retrieval_timestamp`: System timestamp when the datum was ingested.
5. `verification_status`: `['VERIFIED_PRIMARY', 'VERIFIED_SECONDARY', 'TIMING_UNVERIFIED', 'UNAVAILABLE']`.
6. `temporal_eligibility`: Flag indicating whether the datum strictly precedes the prediction cutoff.
