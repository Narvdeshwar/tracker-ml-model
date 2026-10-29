# Phase 10.7 Audit: Prospective Data Collection & First-Outcome Validation

**Repository**: `D:\personal\st-ai\ipo-record`  
**Date**: October 28, 2026  
**Auditor**: Senior Quantitative Researcher & ML Audit Engineer  
**Status**: **VERIFIED & OPERATIONAL (Prospective Shadow Logging Only)**  
**Real-Money Live Trading**: **STRICTLY PROHIBITED (Zero Broker Connections)**

---

## Executive Summary

Phase 10.7 formally validates the complete prospective IPO lifecycle—from pre-cutoff evidence capture through committed prediction, official listing-outcome reconciliation, and evaluation-record generation.

Crucially, this phase prioritizes **real evidence, temporal integrity, and reproducibility** over new model development:
1. **Decision Commitment Pipeline**: Codified in `src/prospective_lifecycle.py`, enforcing authoritative issue-specific cutoffs, timezone compliance (`+05:30` / `IST`), feature source publication verification, frozen model inference (`Model_6B_SME_v1.0`), and exclusion of late or unverified records.
2. **Outcome Reconciliation**: Reconciles realized listing outcomes strictly from verified exchange bulletins (BSE/NSE Bhavcopy), calculates listing-open returns strictly as ((P_open - P_issue) / P_issue) * 100, rejects non-positive prices or unmatched outcomes, and preserves corrections as linked governance audit events.
3. **Evaluation-Record Generation**: Creates granular observation-level records containing model and baseline Brier score contributions, preventing any aggregate performance claim when mature sample size is insufficient.
4. **End-to-End Deterministic Verification**: 11 new comprehensive lifecycle tests in `tests/test_phase_10_7_lifecycle.py` test every lifecycle edge case, bringing total passing repository tests to **203 / 203 (100% pass rate)**.
5. **Frozen Artifact Immutability**: The frozen SME model (`Model_6B_SME_v1.0`) and baseline manifest (`phase_9b_baseline_manifest.json`) remain bit-for-bit identical to their Phase 9B baselines.

---

## 1. Frozen Model & Baseline Manifest Integrity

Bitwise verification confirms zero tampering or modifications across test and execution sessions:

| Artifact | Path | SHA-256 Digest | Status |
| :--- | :--- | :--- | :--- |
| **Frozen SME Model** | `models/frozen/model_6b_sme_v1.joblib` | `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` | **BITWISE UNCHANGED** |
| **Baseline Manifest** | `models/frozen/phase_9b_baseline_manifest.json` | `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` | **BITWISE UNCHANGED** |
| **Cryptographic Checkpoint** | `data/processed/governance_checkpoint_signature.json` | Sealed ID `CHK_20261028084517` | **CHECKPOINT_VERIFIED** |

---

## 2. Implementation Overview (Phase 10.7 Workstreams)

### Workstream 1: Pre-Cutoff Decision Capture
- **Module**: `src/prospective_lifecycle.py` -> `audit_and_prepare_candidate()`, `commit_prospective_decision()`
- **Controls Enforced**:
  - Authoritative cutoff timestamp must explicitly specify IST or `+05:30`.
  - Feature source document must be published prior to or at the cutoff ($T_{\text{pub}} \le T_{\text{cutoff}}$).
  - Prohibited variables (`listing_open_inr`, `listing_close_inr`, `listing_open_return_pct`, `listing_close_return_pct`, `listing_date`) are strictly rejected.
  - Frozen model SHA-256 is verified prior to scoring.
  - Non-compliant or late decisions are automatically rejected or excluded from the clean prospective cohort with explicit failure reason codes.

### Workstream 2: First-Outcome Reconciliation
- **Module**: `src/prospective_lifecycle.py` -> `reconcile_listing_outcome()`, `record_outcome_correction()`
- **Controls Enforced**:
  - Reconciles listing open price only against pre-existing committed decisions (`UNMATCHED OUTCOME` exception if missing).
  - Issue price and opening price must be strictly positive floats ($P_{\text{issue}} > 0$, $P_{\text{open}} > 0$).
  - Return is computed strictly on listing-open prices; listing-close prices are never substituted or mixed.
  - Corrigendum or official revisions are recorded as linked audit events (`OUTCOME_CORRECTION_EVENT`) in `governance_audit_events.jsonl` without mutating historical records.

### Workstream 3: Evaluation-Record Generation
- **Module**: `src/prospective_lifecycle.py` -> `generate_evaluation_records()`
- **Endpoint**: `GET /api/evaluation/records`
- **Output Record Schema**:
  - IPO ID, board, and company name.
  - Decision ID, committed timestamp, and cutoff timestamp.
  - Frozen model identity and SHA-256 digest.
  - Predicted probability ($p_{\text{pos}}$) and verified outcome label ($y \in \{0, 1\}$).
  - Listing-open return percentage.
  - Model Brier contribution: $(p_{\text{model}} - y)^2$.
  - Baseline Brier contribution: $(p_{\text{base\_ref}} - y)^2$ (where $p_{\text{base\_ref}} = 0.8306$ for SME).
  - Evaluation inclusion status (`INCLUDED_CLEAN_EVALUATION`, `PENDING_REALIZED_OUTCOME`, `EXCLUDED_FROM_PRIMARY_EVALUATION`).
  - Sample sufficiency gate: `performance_claim_allowed = False` when mature $N < 100$.

### Workstream 4: Deterministic End-to-End Lifecycle Verification
- **Module**: `tests/test_phase_10_7_lifecycle.py`
- 11 new tests covering:
  - Full valid pre-cutoff through outcome cycle.
  - Late decision rejection.
  - Post-cutoff feature publication exclusion.
  - Missing evidence / hash handling.
  - Non-positive listing price rejection.
  - Unmatched outcome rejection.
  - Decision and outcome idempotency (duplicate ignoring).
  - Outcome correction event preservation.
  - Empty cohort and single-observation evaluation gates.
  - Frozen model/manifest immutability.
  - FastAPI read-only endpoints.

### Workstream 5: Baseline and Metric Verification
- Evaluates the frozen SME model and fixed constant climatology baseline ($p = 0.8306$) on the exact same prospective observations and labels.
- Preserves explicit inconclusive statuses (`INCONCLUSIVE_ZERO_MATURE_OUTCOMES`, `INSUFFICIENT_SAMPLE_SIZE_GATE`).
- Prohibits claiming predictive skill from a single observation or small sample ($N < 100$).

### Workstream 6: Dashboard Surveillance Integration
- **File**: `src/dashboard/static/index.html`
- Added live stage counter tracking for the 5 lifecycle phases:
  - `COMMITTED`: 0
  - `AWAITING LISTING`: 0
  - `PENDING VERIF`: 0
  - `OUTCOME VERIFIED`: 0
  - `EVALUATION READY`: 0
- Execution controls remain disabled (`EXECUTE ORDER (DISABLED IN SHADOW MODE)`), and permanent shadow-mode warning banners are active.

---

## 3. Test Results & Verification

All test suites pass with zero regressions:

```text
D:\personal\st-ai\ipo-record\.venv\Scripts\python.exe -m unittest discover tests
Ran 203 tests in 3.158s
OK
```

Total test count progressed from **192 tests** (Phase 10.6) to **203 tests** (Phase 10.7).

---

## 4. Current Candidate & Ledger Accounting

As of October 28, 2026:

| Category | Population / Cohort | Count | Current Status |
| :--- | :--- | :--- | :--- |
| **Tracked Candidates** | Population 1 (Eligible Coverage) | **6** | Preflight registered; timing monitored |
| **Clean SME Candidates** | Population 2 (Clean Prospective) | **2** | Wiscon Industries & Carver Roboweld |
| **Excluded / Unverified** | Population 3 (Excluded) | **4** | EAAA Alternatives (unverified) + 3 Mainboard (coverage-only) |
| **Committed Decisions** | Live Decision Ledger | **0** | Awaiting authoritative issue close cutoffs (29 & 30 Oct 17:00 IST) |
| **Mature Listing Outcomes** | Live Outcome Ledger | **0** | Awaiting listing dates |
| **Evaluation Records** | Live Evaluation Cohort | **0** | `INCONCLUSIVE_ZERO_MATURE_OUTCOMES` |

---

## 5. First-Outcome Reconciliation Details

- No genuine prospective candidate has listed as of October 28, 2026.
- The outcome reconciliation pipeline has been verified via deterministic test fixtures (`test_01_valid_pre_cutoff_decision_through_verified_outcome`), confirming that when BSE/NSE official Bhavcopy bulletins are published on listing day, the system reconciles prices, calculates open returns, and generates paired evaluation records without lookahead bias.

---

## 6. Metrics Remaining Inconclusive

Due to zero mature prospective outcomes to date, the following metrics remain strictly inconclusive:
- Prospective Brier Score ($BS_{\text{model}}$)
- Constant Baseline Brier Score ($BS_{\text{base}}$)
- Prospective Brier Skill Score ($BSS$)
- ROC-AUC and PR-AUC
- Grouped calibration curves and Hosmer-Lemeshow statistics ($N < 50$)
- Severe-loss Wilson score confidence intervals ($N < 25$)

---

## 7. Remaining Limitations

1. **Mainboard Segment**: No frozen Mainboard model exists in the manifest; Mainboard issues remain tracked strictly for coverage accounting without model scoring.
2. **Sample Size**: Prospective sample size ($N=0$ mature) is insufficient to evaluate out-of-time predictive edge. Formal statistical evaluation requires Stage 1 ($N=30$), Stage 2 ($N=50$), and Stage 3 ($N \ge 100$).
3. **External Dependencies**: Cutoff and outcome capture rely on authoritative exchange notices and official Bhavcopy bulletins.

---

## 8. Governance Affirmation

- Real-money live trading remains **STRICTLY PROHIBITED**.
- Automated broker order routing, API keys, and order execution capabilities remain **COMPLETELY DISABLED**.
- The system operates strictly as an out-of-time quantitative shadow research platform.
