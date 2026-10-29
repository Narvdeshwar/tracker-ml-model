# Phase 9 — Prospective Shadow Evaluation Readiness Audit

**Date:** October 27, 2026  
**Auditor / Principal Researcher:** Antigravity Research & Verification Engine  
**Project:** Indian IPO Machine Learning Research & Prospective Validation  
**Phase:** Phase 9 Readiness Audit (Protocol Freeze, Nested Allotment & Decision Logger Verification)  
**Status:** **READY FOR PROSPECTIVE SHADOW LOGGING (LIVE TRADING STRICTLY PROHIBITED)**

---

## Executive Summary

This readiness audit formally certifies the system for **Phase 9 Prospective Shadow Evaluation**. All requirements specified by the research review have been resolved:
1. **Deterministic Monotonic Allotment Draws:** Corrected the allocation generator in [`src/run_step_8_1_audit_simulator.py`](file:///d:/personal/st-ai/ipo-record/src/run_step_8_1_audit_simulator.py) so that uniform draws depend solely on `(ipo_id, scenario_seed)`. This mathematically guarantees strict subset nesting across allotment probability scenarios:
   $$\text{Allotted}(20\%) \subseteq \text{Allotted}(50\%) \subseteq \text{Allotted}(80\%) \subseteq \text{Allotted}(100\%)$$
2. **Evaluation Protocol Frozen:** Codified in [reports/phase_9_evaluation_protocol.md](file:///d:/personal/st-ai/ipo-record/reports/phase_9_evaluation_protocol.md). Feature definitions, model versions, issue-close cutoffs, and validation-tuned thresholds are locked permanently.
3. **Enhanced Prospective Logger Operational:** Upgraded [`src/prospective_simulator_logger.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_simulator_logger.py) to capture feature SHA-256 hashes, source provenance, calibrated strategy hurdles, and explicit rejection reasons for all candidate IPOs (both approved and rejected).
4. **Physical Ledger Separation:** Decisions are logged to [prospective_decision_ledger.jsonl](file:///d:/personal/st-ai/ipo-record/data/processed/prospective_decision_ledger.jsonl) prior to listing, while realized outcomes are logged independently to [prospective_outcome_ledger.jsonl](file:///d:/personal/st-ai/ipo-record/data/processed/prospective_outcome_ledger.jsonl) post-listing.
5. **The 30-IPO Checkpoint Formalized:** Defined strictly as an initial monitoring and calibration review milestone—not an automatic authorization for live production deployment.
6. **Automated Unit Test Suite:** Expanded to **122/122 passing tests** across 15 test modules.

---

## 1. Audit of Deterministic Nested Allotment Mechanism

### 1.1 The Issue Resolved
In Step 8.1, the hash input included `p_allotment` in the key (`f"{ipo_id}_{scenario_seed}_{p_allotment}"`). Because the cryptographic hash changed with `p_allotment`, the underlying uniform value $u$ differed across scenarios, creating noise where an issue could theoretically be allotted under a $20\%$ scenario but rejected under an $80\%$ scenario.

### 1.2 Mathematical Correction
The generator was refactored in [`src/run_step_8_1_audit_simulator.py`](file:///d:/personal/st-ai/ipo-record/src/run_step_8_1_audit_simulator.py):
```python
def get_deterministic_allotment(ipo_id, scenario_seed, p_allotment):
  if p_allotment >= 1.0:
    return True
  if p_allotment <= 0.0:
    return False
  # Cryptographic uniform draw u in [0, 1) independent of p_allotment
  key = f'{ipo_id}_{scenario_seed}'
  h = int(hashlib.md5(key.encode('utf-8')).hexdigest()[:8], 16)
  uniform_draw = h / float(0xFFFFFFFF)
  return uniform_draw < p_allotment
```

### 1.3 Empirical Verification
A test across all 148 test IPOs confirmed:
- For every IPO, $u < 0.20 \implies u < 0.50 \implies u < 0.80 \implies u \le 1.00$.
- Zero instances of subset violation.
- All sensitivity evaluations in [data/processed/step_8_1_reconciled_sensitivity.csv](file:///d:/personal/st-ai/ipo-record/data/processed/step_8_1_reconciled_sensitivity.csv) now reflect strictly monotonic sensitivity curves.

---

## 2. Frozen Protocol & Calibrated Decision Thresholds

In accordance with [reports/phase_9_evaluation_protocol.md](file:///d:/personal/st-ai/ipo-record/reports/phase_9_evaluation_protocol.md), decision hurdles derived from the 2025 historical validation cohort are permanently locked:

```
Mainboard Architecture (Ticket Size = INR 15,000):
  ├── Positive Ranking (Model C - Structure Only): Hurdle = 0.7756
  ├── Downside Filter  (Model E - Unified):        Hurdle = 0.4868 (Reject if >= 0.4868)
  └── Macro Filter     (Model A - Macro):          Hurdle = 0.7904 (Validation Median)

SME Architecture (Ticket Size = INR 125,000):
  ├── Positive Ranking (Model D - Macro + Scale):  Hurdle = 0.9234
  ├── Downside Filter  (Model E - Unified):        Hurdle = 0.3323 (Reject if >= 0.3323)
  └── Macro Filter     (Model A - Macro):          Hurdle = 0.8619 (Validation Median)
```

*Rule on 2026 Test Cohort:* The 2026 cohort is formally cataloged as an **exploratory historical diagnostic cohort**. No strategy selection or threshold adjustments made during Step 8/8.1 shall be construed as independent confirmation of prospective performance. Genuine validation begins with Phase 9.

---

## 3. Prospective Decision Logger Architecture

The upgraded [`src/prospective_simulator_logger.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_simulator_logger.py) enforces the following production-grade capabilities:

### 3.1 Decision Ledger Record Schema ([prospective_decision_ledger.jsonl](file:///d:/personal/st-ai/ipo-record/data/processed/prospective_decision_ledger.jsonl))
Every prospective entry records:
- `decision_id`: Unique identifier (`DEC_YYYYMMDDHHMMSS_<hash>`).
- `ipo_id`: Canonical IPO identifier.
- `board_type`: Mainboard or SME.
- `cutoff_timestamp_ist`: Statutory Issue Close deadline (17:00:00 IST).
- `logging_timestamp_ist`: System timestamp when record was persisted.
- `model_name` & `model_sha256`: Explicit model artifact version tracking.
- `feature_hash_sha256`: Cryptographic fingerprint of input feature dictionary.
- `features`: Full pre-cutoff feature payload.
- `predicted_probabilities`: `p_positive_open`, `p_macro`, `p_severe_loss`.
- `calibrated_thresholds`: Locked validation hurdles.
- `strategy_decisions`: Boolean decisions for Strategies A through F.
- `rejection_reasons`: Detailed human-readable rejection explanations for every strategy.
- `data_quality_warnings`: Flags for missing data or anomalous spreads.
- `record_sha256`: Tamper-evident hash of the entire record.

### 3.2 Lookahead Leakage Guardrails
The logger programmatically inspects every incoming feature dictionary. If any of the following fields are present, execution is immediately aborted with a `ValueError`:
- `listing_open_inr`
- `listing_close_inr`
- `listing_open_return_pct`
- `listing_close_return_pct`
- `listing_date`

---

## 4. Physical Outcome Ledger Architecture

Following listing day, realized outcomes are ingested into [prospective_outcome_ledger.jsonl](file:///d:/personal/st-ai/ipo-record/data/processed/prospective_outcome_ledger.jsonl):
- **Decision Matching Requirement:** The outcome logger verifies that a pre-existing prospective decision record exists before allowing an outcome to be written. Unmatched outcomes are rejected.
- **Execution Modeling:** Records official opening price ($P_{\text{open}}$), gross return, modeled adverse slippage ($-1.0\%$), statutory transaction costs ($0.35\%$), and modeled net return.
- **Observed Allotment:** Stores empirical allotment data where available from registrar circulars, or marks status as `UNKNOWN`.

---

## 5. Formalization of the 30-IPO Monitoring Checkpoint

The protocol explicitly rejects treating 30 prospective IPOs as automatic authorization to invest real capital. Instead, the 30-IPO checkpoint serves as an **initial monitoring and calibration gate**:

| Evaluation Dimension | Metric / Hurdle | Minimum Requirement for Advancement |
|---|---|---|
| **Coverage & Timing** | Decision Coverage | $100\%$ of eligible closing IPOs logged prior to 17:00 IST cutoff |
| **Leakage Audit** | Lookahead Violations | Exactly $0$ violations |
| **Out-of-Time Win Rate** | Model-Selected Allotment Win Rate | $\ge 60.0\%$ (with 95% Wilson confidence intervals reported) |
| **Downside Risk** | Severe Listing Losses ($\le -10\%$) | $< 15.0\%$ frequency in model-selected candidates |
| **Probability Calibration**| Brier Score Loss | Brier score superior to historical segment base rate |
| **Execution Reality** | Net Modeled Expectancy | Positive simulated PnL after $1.0\%$ slippage and $0.35\%$ costs |

---

## 6. Automated Unit Test Verification

The test suite was expanded via [`tests/test_phase_9.py`](file:///d:/personal/st-ai/ipo-record/tests/test_phase_9.py), bringing total repository passing tests to **122/122**:
- `test_frozen_baseline_sme_model_immutability`: PASSED (`dbf2eec7...` intact)
- `test_deterministic_nested_allotment_draws`: PASSED (Monotonic subset nesting verified)
- `test_prospective_decision_logging_completeness`: PASSED (All hashes and rejection reasons recorded)
- `test_lookahead_leakage_guardrail`: PASSED (Raises ValueError on listing outcomes)
- `test_idempotent_duplicate_prevention`: PASSED (Duplicate decisions ignored safely)
- `test_outcome_ledger_separation_and_matching`: PASSED (Separate ledgers; unmatched outcomes fail)
- `test_tamper_evident_record_hashing`: PASSED (Tampering invalidates record SHA-256)

---

## 7. Strict Operational Restrictions & Next Steps

### Operational Restrictions:
- **Shadow Mode Only:** System must never be connected to live brokerage APIs.
- **No Mid-Evaluation Tuning:** Strategies A through F must execute under the locked protocol.

### Operational Next Steps:
1. Initialize prospective ledgers for upcoming Indian IPOs.
2. Ingest statutory price-band circulars and cutoff dates at Issue Close.
3. Call `ProspectiveDecisionLogger.record_prospective_decision()` on upcoming issues.
4. Convene the formal review audit upon reaching the 30-IPO monitoring milestone.

---
*Audit certified by Antigravity Autonomous Research & Verification Engine.*
