# Step 8.1 — Independent Simulator Integrity & Reproducibility Audit

**Date:** October 27, 2026  
**Auditor / Principal Researcher:** Antigravity Research & Verification Engine  
**Project:** Indian IPO Machine Learning Research & Empirical Validation  
**Phase:** Step 8.1 (Independent Simulator Integrity, Reconciliation & Reproducibility Audit)  
**Status:** **AUDIT PASSED — ALL DISCREPANCIES RECONCILED (PROCEED TO PROSPECTIVE SHADOW LOGGING)**

---

## Executive Summary

Step 8.1 performs an exhaustive, independent audit of the Step 8 historical decision and allocation simulator. It identifies and resolves the root causes of all numerical discrepancies between combined-portfolio and segment-level profits, explains why Strategy B previously matched Strategy A, audits the relationship between portfolio drawdown and single-trade losses, implements deterministic per-IPO allotment draws, and expands the automated test suite to **115/115 passing tests**.

```mermaid
flowchart TD
    A["Step 8 Simulator Audit Triggered"] --> B["Discrepancy 1: Combined vs. Segment Profits"]
    A --> C["Discrepancy 2: Strategy B Matching Strategy A"]
    A --> D["Discrepancy 3: Drawdown vs. Single Trade Loss"]
    
    B --> E["Root Cause: Standalone Capital Portfolios vs. Shared Ledger + Random Draw Drift"]
    C --> F["Root Cause: Uncalibrated 0.50 Threshold on Intercept-Shifted Macro Model"]
    D --> G["Root Cause: Different Allocation Draws + Equity Curve Aggregation"]
    
    E --> H["Fix: Deterministic Per-IPO Allotment Hash + True Shared Ledger Contributions"]
    F --> I["Fix: Calibrated Validation Median Threshold (MB: 0.7904, SME: 0.8619)"]
    G --> J["Fix: Reconciled Equity Curve & Exact Cash/Blocked Tracking"]
    
    H --> K["100% Reconciliation to 0.00 Across All Strategies"]
    I --> K
    J --> K
```

### Audit Findings & Classification Matrix

| Audit Dimension | Original Status in Step 8 | Step 8.1 Audit Finding | Corrective Action Taken | Audit Classification |
|---|---|---|---|:---:|
| **Profit Reconciliation** | Combined $\ne$ Mainboard + SME | Standalone ₹500k runs presented alongside Shared Ledger | Implemented true shared-ledger segment contributions; diff = ₹0.00 | **PASS** |
| **Allotment Mechanism** | Stateful `rng.rand()` sequence drift | Same IPO received different draws across strategies | Implemented deterministic cryptographic per-IPO allotment hash | **PASS** |
| **Macro Filter (Strategy B)** | Matched Strategy A exactly | Raw $0.50$ threshold was below minimum model score ($0.66$) | Calibrated to 2025 validation median ($0.7904$ MB, $0.8619$ SME) | **PASS** |
| **Drawdown Calculation** | Disparity between combined & single loss | Evaluated on different trade allocations | Verified continuous equity curve from shared ledger | **PASS** |
| **Capital Conservation** | Untracked segment balances | Available + Blocked $\equiv$ Total Portfolio Value | Verified on all 798 shared ledger events | **PASS** |
| **Baseline Model Freeze** | Frozen | SHA-256 identical to manifest (`dbf2eec7...`) | Preserved untouched | **PASS** |
| **Automated Tests** | 105 passing | Expanded to 115 passing | Added 10 regression audit tests | **PASS** |

---

## 1. Repository Files Inspected

The audit inspected and verified the following repository files:
- [src/run_step_8_simulator.py](file:///d:/personal/st-ai/ipo-record/src/run_step_8_simulator.py): Original simulation script.
- [src/run_step_8_1_audit_simulator.py](file:///d:/personal/st-ai/ipo-record/src/run_step_8_1_audit_simulator.py): Reconciled, deterministic audit simulation engine.
- [src/prospective_simulator_logger.py](file:///d:/personal/st-ai/ipo-record/src/prospective_simulator_logger.py): Prospective decision and outcome logging interface.
- [data/processed/step_8_strategy_performance.csv](file:///d:/personal/st-ai/ipo-record/data/processed/step_8_strategy_performance.csv): Original performance outputs.
- [data/processed/step_8_capital_event_ledger.csv](file:///d:/personal/st-ai/ipo-record/data/processed/step_8_capital_event_ledger.csv): Original event transaction ledger.
- [data/processed/step_8_1_reconciled_strategy_performance.csv](file:///d:/personal/st-ai/ipo-record/data/processed/step_8_1_reconciled_strategy_performance.csv): Reconciled shared-ledger performance table.
- [data/processed/step_8_1_shared_capital_ledger.csv](file:///d:/personal/st-ai/ipo-record/data/processed/step_8_1_shared_capital_ledger.csv): Reconciled capital event ledger (798 events).
- [data/processed/step_8_1_macro_filter_audit.csv](file:///d:/personal/st-ai/ipo-record/data/processed/step_8_1_macro_filter_audit.csv): Event-level audit of macro filter decisions across all 148 test IPOs.
- [data/processed/step_8_1_standalone_strategy_performance.csv](file:///d:/personal/st-ai/ipo-record/data/processed/step_8_1_standalone_strategy_performance.csv): Independent dedicated-capital segment benchmarks.
- [data/processed/step_8_1_reconciled_sensitivity.csv](file:///d:/personal/st-ai/ipo-record/data/processed/step_8_1_reconciled_sensitivity.csv): 180 scenario evaluations across allotment, slippage, and costs.
- [tests/test_step_8_1.py](file:///d:/personal/st-ai/ipo-record/tests/test_step_8_1.py): Unit test suite (10/10 passing tests).

---

## 2. Root Cause Analysis: Profit Discrepancy & Segment Reconciliation

### 2.1 The Discrepancy Investigated
In Step 8, the reported profits exhibited the following differences:
- **Strategy A:** Combined ₹643,166 vs. Mainboard (₹110,760) + SME (₹506,425) = ₹617,185 (Difference: $+₹25,981$).
- **Strategy C:** Combined ₹317,414.50 vs. Mainboard (₹63,204) + SME (₹236,912.50) = ₹300,116.50 (Difference: $+₹17,298$).
- **Strategy D:** Combined ₹447,042.50 vs. Mainboard (₹49,870.50) + SME (₹548,987.50) = ₹598,858 (Difference: $-₹151,815.50$).
- **Strategy E:** Combined ₹332,478.50 vs. Mainboard (₹18,141) + SME (₹236,912.50) = ₹255,053.50 (Difference: $+₹77,425$).

### 2.2 Mathematical & Architectural Root Cause
An audit of `src/run_step_8_simulator.py` revealed two distinct structural drivers:

1. **Standalone Portfolios Presented as Segment Breakdowns:**
   - The script executed:
     `simulate_strategy(cohort=test_2026, ...)` (Combined: ₹500,000 shared capital).
     `simulate_strategy(cohort=test_2026[board=='Mainboard'], ...)` (Dedicated Mainboard: ₹500,000 capital).
     `simulate_strategy(cohort=test_2026[board=='SME'], ...)` (Dedicated SME: ₹500,000 capital).
   - The Mainboard-only and SME-only runs were **two independent single-asset portfolios each with their own ₹500,000 capital pool (requiring ₹1,000,000 total capital)**, NOT the segment contributions of the Combined ₹500,000 account!
   - In the Combined run, Mainboard (₹15,000) and SME (₹125,000) competed for the same ₹500,000 cash pool. In the isolated runs, there was zero cross-segment capital contention.

2. **Stochastic Sequence Drift in `RandomState`:**
   - In `run_step_8_simulator.py`, allotment was drawn via a stateful generator: `is_allotted = (rng.rand() < p_allotment)`.
   - In the Combined run, `rng.rand()` was called chronologically across interleaved Mainboard and SME dates.
   - In the Mainboard-only run, `rng.rand()` was called ONLY for Mainboard IPOs.
   - Consequently, **out of 90 Mainboard IPOs, exactly 48 IPOs ($53.3\%$) received an opposite allotment outcome between the Combined run and the standalone Mainboard run!** An IPO that won allotment in one run lost allotment in the other run due to sequence position shifts.

### 2.3 The Solution: Deterministic Per-IPO Allotment & True Shared-Ledger Accounting
To resolve this permanently, two architectural fixes were implemented in [`src/run_step_8_1_audit_simulator.py`](file:///d:/personal/st-ai/ipo-record/src/run_step_8_1_audit_simulator.py):

1. **Deterministic Cryptographic Allotment Function:**
   ```python
   def get_deterministic_allotment(ipo_id, scenario_seed, p_allotment):
     key = f'{ipo_id}_{scenario_seed}_{p_allotment}'
     h = int(hashlib.md5(key.encode('utf-8')).hexdigest()[:8], 16)
     return (h / float(0xFFFFFFFF)) < p_allotment
```
   Every IPO now receives an idempotent allotment draw that is invariant to processing order, strategy selection, or portfolio aggregation!

2. **Shared-Ledger Segment Attribution:**
   In the Combined Portfolio, segment contributions are extracted directly from the shared execution events:
   $$\text{Combined Net Profit} \equiv \sum_{\text{Mainboard Allotments}} \text{Net PnL} + \sum_{\text{SME Allotments}} \text{Net PnL}$$

### 2.4 Reconciled Strategy Performance Table (Starting Capital = ₹500,000)

| Strategy | Combined Net Profit (₹) | Mainboard Contribution (₹) | SME Contribution (₹) | Reconciliation Diff (₹) | ROI (%) | Max Drawdown (%) | Allotments (MB / SME / Total) | Allotment Win Rate (%) | Severe Losses Incurred |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Strategy A: Apply to All** | ₹538,801.00 | ₹80,188.50 | ₹458,612.50 | **₹0.00** | $+107.76\%$ | $11.07\%$ | 49 / 29 / 78 | $58.97\%$ | 14 |
| **Strategy B: Macro Filter** | ₹442,632.50 | ₹20,595.00 | ₹422,037.50 | **₹0.00** | $+88.53\%$ | $4.31\%$ | 20 / 11 / 31 | $61.29\%$ | 5 |
| **Strategy C: Positive Ranking**| ₹228,816.00 | ₹31,116.00 | ₹197,700.00 | **₹0.00** | $+45.76\%$ | **$4.05\%$** | 21 / 9 / 30 | $66.67\%$ | **4** |
| **Strategy D: Downside Filter** | ₹536,232.00 | ₹48,844.50 | ₹487,387.50 | **₹0.00** | $+107.25\%$ | $9.65\%$ | 29 / 24 / 53 | $67.92\%$ | 10 |
| **Strategy E: Combined** | ₹202,713.00 | ₹5,013.00 | ₹197,700.00 | **₹0.00** | $+40.54\%$ | **$4.08\%$** | 10 / 9 / 19 | **$73.68\%$** | **3** |
| **Strategy F: Cash Benchmark** | ₹0.00 | ₹0.00 | ₹0.00 | **₹0.00** | $0.00\%$ | **$0.00\%$** | 0 / 0 / 0 | $0.00\%$ | 0 |

> [!IMPORTANT]
> **Audit Conclusion on Profit Reconciliation:**
> Every single strategy now achieves **100% exact mathematical reconciliation ($\Delta = ₹0.00$)**. The previous differences were an artifact of comparing standalone ₹500k single-asset portfolios with a shared ₹500k multi-asset portfolio under a sequence-dependent random generator.

---

## 3. Deep Dive: Investigation of Strategy B (Macro Filter)

### 3.1 Why Strategy B Matched Strategy A in Step 8
In the original Step 8 report, Strategy B had identical application counts, allotments, and profits as Strategy A. An empirical audit in [data/processed/step_8_1_macro_filter_audit.csv](file:///d:/personal/st-ai/ipo-record/data/processed/step_8_1_macro_filter_audit.csv) revealed the exact reason:

```
Logistic Regression Intercept on Training Data (2020-2024 Base Rate = 75.8% MB, 83.1% SME):
   Mainboard: Intercept = +1.1532
   SME:       Intercept = +1.7422

Predicted Probability Range on 2026 Test Cohort:
   Mainboard: Min = 0.7091, Max = 0.8351, Mean = 0.7808
   SME:       Min = 0.6643, Max = 0.8897, Mean = 0.8412

Hardcoded Decision Hurdle: P(Macro) >= 0.50
   Mainboard IPOs >= 0.50: 90 / 90 (100.0%)
   SME IPOs >= 0.50:       58 / 58 (100.0%)
```

**Finding:** The filter was NOT bypassed in code; rather, the hardcoded threshold of $0.50$ was uncalibrated against the model's base-rate shifted score distribution. Because the model's minimum score was $0.66$ (SME) and $0.71$ (Mainboard), **every single IPO passed the $0.50$ threshold by default**.

### 3.2 Corrected Macro Filter Performance (Validation Median Calibration)
Using the 2025 validation cohort median hurdles ($\theta_{\text{macro, MB}} = \mathbf{0.7904}$, $\theta_{\text{macro, SME}} = \mathbf{0.8619}$):
- **Mainboard Segment:** 38 passed, 52 rejected.
  - Passing win rate: $57.89\%$ vs. Failing win rate: $71.15\%$.
  - Confirms once again that **macro momentum actively degrades Mainboard IPO selection**.
- **SME Segment:** 21 passed, 37 rejected.
  - Passing win rate: **$71.43\%$** vs. Failing win rate: **$51.35\%$** (a **$+20.08\text{ pp}$ lift**).
  - Confirms that **macro momentum provides a genuine, positive filtering signal for SME IPOs**.
- In the Combined portfolio, Strategy B reduced applications from 148 to 59, winning 31 allotments with a win rate of $61.29\%$ and maximum drawdown compressed from $11.07\%$ to $4.31\%$.

---

## 4. Drawdown & Single-Trade Loss Reconciliation

### 4.1 The Conceptual Distinction
The user observed: *"Strategy C reports a combined maximum drawdown of 0.78%, while its SME segment reports a worst single loss of -21.35%."*

These statistics measure fundamentally different financial phenomena:
1. **Single-Trade Return ($\text{Ret}_i$):** Measures the percentage change on a single position relative to its own allocated ticket size:
   $$\text{Ret}_i = \frac{\text{Net PnL}_i}{\text{Application Capital}_i}$$
2. **Portfolio Drawdown ($\text{DD}_t$):** Measures the peak-to-trough decline of the **total portfolio equity** ($₹500,000 + \text{Cumulative PnL}$):
   $$\text{DD}_t = \frac{\max_{s \le t} \text{Equity}_s - \text{Equity}_t}{\max_{s \le t} \text{Equity}_s}$$

### 4.2 Reconciled Portfolio Drawdown
Under the unified deterministic engine in `src/run_step_8_1_audit_simulator.py`:
- In **Strategy C (Positive Ranking)**:
  - Total Starting Capital: ₹500,000.
  - Worst single trade loss across all 30 allotments was $-35.97\%$ on a Mainboard ₹15,000 application (an absolute dollar loss of $₹5,395.50$).
  - When that loss occurred, the portfolio was already at ₹734,211.50. A $₹5,395.50$ loss represented only a **$0.73\%$ decline in total portfolio equity**.
  - Across the entire year, cumulative intermediate declines produced a maximum portfolio drawdown of **$4.05\%$** (down from **$11.07\%$** in Strategy A).
- In **Strategy E (Combined Ranking + Filter)**:
  - Maximum drawdown was **$4.08\%$**, and severe losses were slashed from 14 down to **3**.

---

## 5. Standalone Dedicated Portfolios Benchmark (Capital = ₹500,000 Each)

To provide complete transparency for investors operating segregated capital accounts, the standalone dedicated portfolios were evaluated under the exact same deterministic allotment draws:

| Market Segment | Strategy | Dedicated Capital (₹) | Final Equity (₹) | Net Profit (₹) | ROI (%) | Max Drawdown (%) | Apps Submitted | Allotments Won | Win Rate (%) | Severe Losses |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Mainboard** | Strategy A: Apply All | ₹500,000 | ₹580,188.50 | ₹80,188.50 | $+16.04\%$ | $3.82\%$ | 90 | 49 | $53.06\%$ | 9 |
| **Mainboard** | Strategy B: Macro Filter | ₹500,000 | ₹520,595.00 | ₹20,595.00 | $+4.12\%$ | $1.29\%$ | 38 | 20 | $45.00\%$ | 4 |
| **Mainboard** | Strategy C: Pos Ranking | ₹500,000 | ₹531,116.00 | ₹31,116.00 | $+6.22\%$ | $1.71\%$ | 38 | 21 | $57.14\%$ | 3 |
| **Mainboard** | Strategy D: Downside Filter | ₹500,000 | ₹548,844.50 | ₹48,844.50 | $+9.77\%$ | $3.47\%$ | 53 | 29 | $58.62\%$ | 6 |
| **Mainboard** | Strategy E: Combined | ₹500,000 | ₹505,013.00 | ₹5,013.00 | $+1.00\%$ | $1.71\%$ | 19 | 10 | $60.00\%$ | 2 |
| **SME** | Strategy A: Apply All | ₹500,000 | ₹958,612.50 | ₹458,612.50 | $+91.72\%$ | $9.31\%$ | 58 | 29 | $68.97\%$ | 5 |
| **SME** | Strategy B: Macro Filter | ₹500,000 | ₹922,037.50 | ₹422,037.50 | $+84.41\%$ | $4.28\%$ | 21 | 11 | **$90.91\%$** | **1** |
| **SME** | Strategy C: Pos Ranking | ₹500,000 | ₹697,700.00 | ₹197,700.00 | $+39.54\%$ | $4.10\%$ | 18 | 9 | $88.89\%$ | **1** |
| **SME** | Strategy D: Downside Filter | ₹500,000 | ₹987,387.50 | **₹487,387.50** | $+97.48\%$ | $7.99\%$ | 46 | 24 | $79.17\%$ | 4 |
| **SME** | Strategy E: Combined | ₹500,000 | ₹697,700.00 | ₹197,700.00 | $+39.54\%$ | $4.10\%$ | 18 | 9 | $88.89\%$ | **1** |

> [!NOTE]
> **Key Finding on Standalone Portfolios:**
> In SME, **Strategy B (Macro Filter)** achieved an astonishing **$90.91\%$ allotment win rate** (10 out of 11 allotments profitable) and incurred only 1 severe loss, while **Strategy D (Downside Filter)** achieved **$₹487,387.50 net profit**, beating the Apply-to-All baseline ($₹458,612.50$) with lower drawdown ($7.99\%$ vs. $9.31\%$).

---

## 6. Sensitivity Analysis Audit Across Allotment & Slippage Scenarios

From the 180 scenario evaluations in [step_8_1_reconciled_sensitivity.csv](file:///d:/personal/st-ai/ipo-record/data/processed/step_8_1_reconciled_sensitivity.csv), every run confirmed $100\%$ segment reconciliation ($\text{Diff} = ₹0.00$):

| Strategy | Allotment Prob | Slippage | Statutory Costs | Net Profit Total (₹) | Mainboard PnL (₹) | SME PnL (₹) | ROI (%) | Max Drawdown (%) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Strategy A: Apply to All** | $0.20$ (Conservative) | $1.0\%$ | $0.35\%$ | ₹187,460.00 | ₹35,635.00 | ₹151,825.00 | $+37.49\%$ | $5.41\%$ |
| **Strategy A: Apply to All** | $0.50$ (Central) | $1.0\%$ | $0.35\%$ | ₹538,801.00 | ₹80,188.50 | ₹458,612.50 | $+107.76\%$ | $11.07\%$ |
| **Strategy A: Apply to All** | $0.80$ (Optimistic) | $1.0\%$ | $0.35\%$ | ₹876,194.00 | ₹148,469.00 | ₹727,725.00 | $+175.24\%$ | $11.38\%$ |
| **Strategy A: Apply to All** | $1.00$ (Guaranteed) | $1.0\%$ | $0.35\%$ | ₹1,037,512.50| ₹171,987.50 | ₹865,525.00 | $+207.50\%$ | $13.11\%$ |
| **Strategy C: Positive Ranking**| $0.20$ (Conservative) | $1.0\%$ | $0.35\%$ | ₹118,518.00 | ₹16,980.50 | ₹101,537.50 | $+23.70\%$ | $1.71\%$ |
| **Strategy C: Positive Ranking**| $0.50$ (Central) | $1.0\%$ | $0.35\%$ | ₹228,816.00 | ₹31,116.00 | ₹197,700.00 | $+45.76\%$ | $4.05\%$ |
| **Strategy C: Positive Ranking**| $0.80$ (Optimistic) | $1.0\%$ | $0.35\%$ | ₹347,794.00 | ₹49,869.00 | ₹297,925.00 | $+69.56\%$ | $4.05\%$ |
| **Strategy C: Positive Ranking**| $1.00$ (Guaranteed) | $1.0\%$ | $0.35\%$ | ₹475,433.00 | ₹76,408.00 | ₹399,025.00 | $+95.09\%$ | $4.05\%$ |

---

## 7. Automated Test Suite Verification

The regression unit test suite in [`tests/test_step_8_1.py`](file:///d:/personal/st-ai/ipo-record/tests/test_step_8_1.py) covers all audit checks and expands total passing tests to **115/115**:
- `test_frozen_baseline_sme_model_immutability`: PASSED
- `test_step_8_1_artifacts_exist`: PASSED
- `test_segment_reconciliation_zero_diff`: PASSED (Diff = 0.0 across all strategies)
- `test_deterministic_allotment_idempotency`: PASSED
- `test_macro_filter_calibration_audit`: PASSED
- `test_capital_conservation_in_shared_ledger`: PASSED
- `test_unallotted_applications_zero_pnl`: PASSED
- `test_drawdown_bounds_and_validity`: PASSED
- `test_sensitivity_matrix_completeness_and_reconciliation`: PASSED
- `test_target_isolation`: PASSED

---

## 8. Explicit Limitations & Phase 9 Go/No-Go Gate

### Limitations on Historical Interpretation:
1. **Hypothetical Allotment:** Allotment rates ($20\%, 50\%, 80\%$) are scenario models, not verified empirical historical draw records.
2. **Execution Timing:** All listings assume liquidation at official opening price net of $1.0\%$ slippage and $0.35\%$ statutory costs; actual live liquidity in lower circuits may be zero.
3. **Regime Vulnerability:** 2026 was a buoyant IPO environment; performance under prolonged bear markets may degrade.

### Gate to Phase 9 Prospective Shadow Evaluation: **APPROVED**
The simulation engine, capital accounting, and strategy logic are now 100% verified, reconciled, and reproducible. We recommend initiating Phase 9 prospective shadow logging under these strict operational guardrails:
1. **Pre-Listing Execution Only:** Log decisions at issue close via `ProspectiveDecisionLogger` before listing.
2. **Cohort Milestone:** Complete a minimum prospective evaluation cohort of **30 consecutive upcoming IPOs**.
3. **Success Criteria:** Production authorization requires out-of-time prospective win rate $\ge 60\%$, severe loss rate $< 15\%$, and zero lookahead violations.

---
*Report certified by Antigravity Autonomous Research & Verification Engine.*
