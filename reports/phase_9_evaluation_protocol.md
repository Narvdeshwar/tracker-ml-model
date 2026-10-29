# Phase 9 — Prospective IPO Shadow Evaluation Protocol (Frozen)

**Date of Protocol Freeze:** October 27, 2026  
**Protocol Version:** `v1.0-FROZEN`  
**Governing Auditor:** Antigravity Research & Verification Engine  
**Project:** Indian IPO Machine Learning Research & Prospective Validation  
**Phase:** Phase 9 (Prospective Shadow-Mode Logging & Out-of-Time Verification)  
**Execution Mode:** **SHADOW EVALUATION ONLY (NO REAL-MONEY TRADING, NO BROKER EXECUTION)**

---

## 1. Objective & Non-Negotiable Governance Principles

The objective of Phase 9 is to collect immutable, tamper-evident prospective predictions and strategy decisions on upcoming Indian IPOs **strictly prior to listing**, record realized outcomes independently post-listing, and evaluate out-of-time model discrimination and strategy performance without lookahead leakage or mid-evaluation threshold drift.

### Non-Negotiable Principles:
1. **Zero Real-Money Risk:** Phase 9 operates in shadow mode only. No capital shall be committed, no brokerage orders submitted, and no financial advice provided.
2. **Baseline Model Immutability:** Baseline model artifact `Model_6B_SME_v1.0` ([models/frozen/model_6b_sme_v1.joblib](file:///d:/personal/st-ai/ipo-record/models/frozen/model_6b_sme_v1.joblib)) remains permanently frozen (SHA-256: `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76`).
3. **Threshold Freeze:** Decision hurdles derived from the 2025 historical validation cohort are permanently locked and cannot be adjusted based on accumulating prospective outcomes.
4. **Physical Ledger Separation:** Prospective decisions are recorded in [prospective_decision_ledger.jsonl](file:///d:/personal/st-ai/ipo-record/data/processed/prospective_decision_ledger.jsonl), while realized listing outcomes are recorded in [prospective_outcome_ledger.jsonl](file:///d:/personal/st-ai/ipo-record/data/processed/prospective_outcome_ledger.jsonl). Neither file can cross-contaminate the other.
5. **No Selective Omission:** Every eligible IPO closing during the evaluation window—whether approved or rejected by the models—must be recorded. Unfavorable predictions cannot be pruned.

---

## 2. Eligible Universe & Decision Cutoff Policy

### 2.1 Eligible IPO Universe
Any equity IPO listing on the National Stock Exchange (NSE) or Bombay Stock Exchange (BSE), across:
- **Mainboard Segment:** Standard book-built issues (retail lot size $\approx ₹15,000$).
- **SME Segment:** NSE Emerge or BSE SME platform issues (statutory minimum ticket size $\ge ₹100,000$, default modeled at $₹125,000$).

*Exclusions:* Non-convertible debentures (NCDs), rights issues, preferential allotments, and issues lacking statutory exchange price band circulars.

### 2.2 Decision Cutoff Timestamp
- **Cutoff Deadline:** Exactly **17:00:00 IST on Issue Close Date** ($T_{\text{close}}$).
- **Enforcement Rule:** Every decision record must be persisted and hashed at or before $T_{\text{close}}$. Any record logged after 17:00 IST on issue close date is marked `LATE_DECISION_EXCLUDED` and disqualified from prospective performance reporting.

---

## 3. Frozen Feature Set & Models

### 3.1 Feature Definitions & Provenance Guardrails

| Feature Name | Category | Exact Definition | Source Document Reference | Provenance Rule |
|---|---|---|---|---|
| `nifty50_return_5s` | Macro | 5-session percentage return of Nifty 50 | NSE Index Closing File | Evaluated at 15:30 IST on cutoff date |
| `india_vix_level_at_cutoff` | Macro | India VIX closing level at cutoff | NSE VIX Daily File | Evaluated at 15:30 IST on cutoff date |
| `recent5_positive_listing_rate`| Sentiment | Fraction of previous 5 listings opening $>0$ | Exchange Listing Outcomes | Evaluated strictly on listings prior to cutoff |
| `log_issue_price` | Valuation | Natural logarithm of nominal per-share issue price | Statutory Price Band Circular | Disclosed $\ge 2$ days before open |
| `feat_price_band_spread_pct` | Structure| $100 \times (\text{Cap} - \text{Floor}) / \text{Floor}$ | Statutory Price Band Circular | Disclosed $\ge 2$ days before open |
| `feat_is_fixed_price_issue` | Structure| Binary flag ($1$ if fixed price, $0$ if book built) | Exchange Issue Notice | Disclosed $\ge 2$ days before open |

> [!WARNING]
> **Prohibited Variables:**
> No realized listing returns (`listing_open_return_pct`, `listing_close_return_pct`), listing prices (`listing_open_inr`), post-close allotment figures, or post-listing subscription multiples may be provided as inputs to the decision API.

### 3.2 Frozen Models & Calibrated Thresholds
Thresholds are permanently frozen based on the 2025 historical validation cohort:

```
Mainboard Architecture:
  ├── Positive Opening: Model C (Structure Only: Spread %, Fixed Price Flag)
  │     Hurdle: P(Positive Open) >= 0.7756 (Validation 60th Percentile)
  ├── Downside Risk:    Unified Model E (Macro + Scale/Price + Structure)
  │     Hurdle: P(Severe Loss) < 0.4868 (Validation 80th Percentile)
  └── Macro Filter:     Model A (Macro Momentum)
        Hurdle: P(Macro) >= 0.7904 (Validation Median)

SME Architecture:
  ├── Positive Opening: Model D (Macro Momentum + Scale/Price + Spread %)
  │     Hurdle: P(Positive Open) >= 0.9234 (Validation 60th Percentile)
  ├── Downside Risk:    Unified Model E (Macro + Scale/Price + Structure)
  │     Hurdle: P(Severe Loss) < 0.3323 (Validation 80th Percentile)
  └── Macro Filter:     Model A (Macro Momentum)
        Hurdle: P(Macro) >= 0.8619 (Validation Median)
```

---

## 4. Evaluated Application Strategies

The decision logger evaluates and records six concurrent strategies for every eligible IPO:

1. **Strategy A (Apply to All):** Unconditional baseline. Applies to every candidate if capital allows.
2. **Strategy B (Macro Filter):** Applies if $P_{\text{macro}} \ge \theta_{\text{macro}}$.
3. **Strategy C (Positive-Opening Ranking):** Applies if $P_{\text{pos}} \ge \theta_{\text{pos}}$.
4. **Strategy D (Downside-Risk Filter):** Applies to all, but rejects candidates where $P_{\text{loss}} \ge \theta_{\text{loss}}$.
5. **Strategy E (Combined Ranking & Risk Filter):** Applies only if $P_{\text{pos}} \ge \theta_{\text{pos}}$ AND $P_{\text{loss}} < \theta_{\text{loss}}$.
6. **Strategy F (Liquid Cash Benchmark):** Zero applications; 100% capital preserved in liquid cash.

---

## 5. Outcome Recording & Execution Assumptions

### 5.1 Outcome Recording on Listing Date ($T_{\text{list}}$)
Following official exchange listing, the outcome logger records:
- Official opening discovery price ($P_{\text{open}}$) from official NSE/BSE price feeds.
- Nominal issue price ($P_{\text{issue}}$).
- Gross listing-open return: $R_{\text{gross}} = 100 \times (P_{\text{open}} - P_{\text{issue}}) / P_{\text{issue}}$.
- Exact binary outcome realization label ($y$):
  $$y = \begin{cases} 1 & \text{if } R_{\text{gross}} > 0 \\ 0 & \text{if } R_{\text{gross}} \le 0 \end{cases}$$
  *(Note: Flat opening return $R_{\text{gross}} = 0$ is strictly classified as negative class $y=0$ in accordance with the binary classification objective `target_positive_open`).*
- Binary severe loss outcome ($y_{\text{loss}}$):
  $$y_{\text{loss}} = \begin{cases} 1 & \text{if } R_{\text{gross}} \le -10.0\% \\ 0 & \text{if } R_{\text{gross}} > -10.0\% \end{cases}$$
- Modeled execution return: $R_{\text{net}} = R_{\text{gross}} - \text{Slippage} (1.0\%) - \text{Roundtrip Costs} (0.35\%)$.
- Observed allotment status (if available from registrar basis of allotment, otherwise marked `UNKNOWN`).

### 5.2 Deterministic Monotonic Allotment Simulation
Where empirical retail allotment records are unavailable, allotment sensitivity is evaluated using strictly nested deterministic uniform draws:
$$u = \frac{\text{hash}(\text{ipo\_id} + \text{seed})}{\text{0xFFFFFFFF}} \in [0, 1)$$
- Conservative Scenario: Allotted if $u < 0.20$.
- Central Scenario: Allotted if $u < 0.50$.
- Optimistic Scenario: Allotted if $u < 0.80$.
- Guaranteed Benchmark: Allotted if $u < 1.00$.

*Guaranteed nesting:* $\text{Allotted}_{20\%} \subseteq \text{Allotted}_{50\%} \subseteq \text{Allotted}_{80\%} \subseteq \text{Allotted}_{100\%}$.

---

## 6. The 30-IPO Monitoring Checkpoint & Review Criteria

The evaluation protocol explicitly treats the completion of **30 consecutive eligible IPO decisions** as an **initial monitoring checkpoint**, not an automatic authorization for live production trading.

### Checkpoint Evaluation Metrics:
1. **Decision Coverage:** $100\%$ of eligible IPOs closing during the window must have valid pre-cutoff records.
2. **Discrimination Metrics:**
   - ROC-AUC and PR-AUC evaluated out-of-time (with 95% Wilson confidence intervals).
   - Base-rate comparison against the unselected eligible cohort.
3. **Severe Loss Avoidance:** Number and rate of severe listing losses ($\le -10\%$) in Strategy C/E versus Strategy A.
4. **Calibration (Brier Score):** Mean squared error between predicted probabilities and observed binary outcomes.
5. **Modeled Net PnL & Drawdown:** Net portfolio performance under the calibrated shared-ledger engine.

### Gate to Production Capital Deployment:
Advancement to real-world capital trials requires a separate formal audit and must satisfy all of the following hurdles across a statistically meaningful sample ($N \ge 30$):
- **Decision Integrity:** Zero lookahead violations and zero late decision logs.
- **Out-of-Time Win Rate:** Realized positive opening rate $\ge 60.0\%$ among model-selected IPOs.
- **Severe Loss Frequency:** Severe loss frequency $< 15.0\%$ in model-selected IPOs (vs. baseline).
- **Positive Net Expectancy:** Positive simulated net profit after statutory transaction costs ($0.35\%$) and adverse slippage ($-1.0\%$).

---
*Protocol locked and certified by Antigravity Autonomous Research & Verification Engine.*
