# Phase 10.6 Audit: Prospective Evidence Integrity & Statistical Validation

**Repository**: `D:\personal\st-ai\ipo-record`  
**Date**: October 28, 2026  
**Auditor**: Senior Quantitative Researcher & ML Audit Engineer  
**Status**: **VERIFIED & OPERATIONAL (Prospective Shadow Logging Only)**  
**Real-Money Live Trading**: **STRICTLY PROHIBITED (Zero Broker Connections)**

---

## Executive Summary

Phase 10.6 establishes cryptographic evidence traceability, mathematically rigorous comparative evaluation, non-parametric drift detection, and tamper-resistant audit checkpoints for the Indian IPO machine learning system.

While Phase 10.5 established operational health and basic surveillance, Phase 10.6 guarantees that the empirical evidence accumulated during prospective surveillance meets strict quantitative research standards. Specifically:
1. Every prospective decision is traced back to its immutable source document SHA-256 digest, pre-cutoff timestamp, model identity, verified outcome, and clean-cohort classification.
2. The prospective Brier Skill Score ($BSS$) is guaranteed to evaluate the frozen model and constant reference baseline on the exact same prospective observations and labels.
3. Uncertainty quantification utilizes seed-locked paired bootstrap replicates (`seed=42`) with explicit handling of single-class realization states (`INCONCLUSIVE_SINGLE_CLASS`).
4. Distributional drift surveillance is upgraded with non-parametric diagnostics (observed median, IQR, percentiles, and two-sample Kolmogorov-Smirnov tests).
5. All critical ledgers, events, baseline manifest, and frozen models are cryptographically sealed into a multi-file signature snapshot (`CHK_20261028084517`), rendering any historical ledger truncation or rewriting immediately detectable.

---

## 1. Frozen Model & Baseline Manifest Integrity

All frozen artifacts remain byte-for-byte immutable and bitwise identical to their Phase 9B baseline specifications:

| Artifact | Path | SHA-256 Digest | Status |
| :--- | :--- | :--- | :--- |
| **Frozen SME Model** | `models/frozen/model_6b_sme_v1.joblib` | `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` | **BYTE-FOR-BYTE IDENTICAL** |
| **Baseline Manifest** | `models/frozen/phase_9b_baseline_manifest.json` | `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` | **BYTE-FOR-BYTE IDENTICAL** |

---

## 2. Implementation Overview (Phase 10.6 Workstreams)

### Workstream 1: Observation-Level Evidence Traceability
- **Engine**: `src/evidence_audit_protocol.py` -> `audit_observation_level_evidence()`
- **Endpoint**: `GET /api/audit/observation-level`
- **Capabilities**:
  - Connects each tracked IPO to its pre-cutoff decision record, SHA-256 hash, authoritative cutoff timestamp, model parameters, and verified realization outcome.
  - Documents exact clean cohort inclusion or exclusion reasons (`POPULATION_2_CLEAN_PROSPECTIVE`, `UNVERIFIED_CUTOFF_SOURCE`, `EXCLUDED_UNVERIFIED_TIMING`).

### Workstream 2: Mathematical Evaluation Protocol & Baseline Pairing
- **Engine**: `src/evidence_audit_protocol.py` -> `evaluate_prospective_metrics_rigorous()`
- **Endpoint**: `GET /api/metrics/rigorous-eval`
- **Mathematical Specification**:
  - Model Brier Score: $BS_{\text{model}} = \frac{1}{N} \sum_{i=1}^N (p_i - y_i)^2$
  - Baseline Constant Brier Score: $BS_{\text{base}} = \frac{1}{N} \sum_{i=1}^N (p_{\text{base}} - y_i)^2$ where $p_{\text{base}} = 0.8306$ (SME)
  - Prospective Brier Skill Score: $BSS = 1 - \frac{BS_{\text{model}}}{BS_{\text{base}}}$
  - **Zero Fabrication Rule**: When $N = 0$ mature listing outcomes are recorded, the endpoint returns `INCONCLUSIVE_ZERO_MATURE_OUTCOMES`. Metrics are never set to 0.0 or fabricated.

### Workstream 3: Paired Bootstrap Confidence Intervals & Single-Class Handling
- **Engine**: `_compute_paired_bootstrap(..., n_bootstraps=1000, seed=42)`
- **Behavior**:
  - Evaluates deterministic, seed-locked 95% bootstrap confidence intervals for Brier scores and BSS.
  - Automatically identifies degenerate outcome realizations ($y \in \{0\}^N$ or $y \in \{1\}^N$). In such cases, ROC-AUC and PR-AUC are mathematically undefined; the engine returns `INCONCLUSIVE_SINGLE_CLASS` with `None` values rather than arbitrary defaults.

### Workstream 4: Non-Parametric Feature Drift Surveillance
- **Engine**: `audit_drift_methodology_enhanced()`
- **Behavior**:
  - Extends parametric z-score shifts by computing empirical medians, Interquartile Ranges (IQR, 25th to 75th percentiles), and non-parametric two-sample Kolmogorov-Smirnov tests (`scipy.stats.ks_2samp`) where candidate sample size $N \ge 20$.
  - Detects non-normal, skewed, or fat-tailed shifts in market volatility (`feat_india_vix`), short-term momentum (`feat_nifty50_ret5s_pct`), and IPO sentiment (`feat_recent5_sentiment`).

### Workstream 5: Cryptographic Audit Checkpoint Sealing
- **Engine**: `generate_and_seal_audit_checkpoint()` & `verify_sealed_checkpoint()`
- **Sealed File**: `data/processed/governance_checkpoint_signature.json`
- **Endpoint**: `GET /api/audit/checkpoint-verification`
- **Tamper Evidence**:
  - Computes and seals an aggregate signature across:
    1. Decision ledger SHA-256
    2. Outcome ledger SHA-256
    3. Governance audit events SHA-256
    4. Baseline manifest SHA-256
    5. Frozen model binary SHA-256
  - Verification reports `CHECKPOINT_VERIFIED` with individual file match booleans. Any unauthorized truncation or file rewriting breaks the cryptographic seal immediately.

### Workstream 6: UI Dashboard Audit Stream Integration
- **File**: `src/dashboard/static/index.html`
- **Features**:
  - Live observation-level audit table rendering in the Model Performance screen.
  - Real-time cryptographic checkpoint status pill (`✓ SEALED CHECKPOINT VERIFIED`).
  - Observation-level traceability badges (`TRACED` / `PARTIAL`).

---

## 3. Test Suite Verification & Coverage

The automated test suite passes completely with zero errors, zero failures, and zero regressions:

```text
D:\personal\st-ai\ipo-record\.venv\Scripts\python.exe -m unittest discover tests
Ran 192 tests in 2.998s
OK
```

### Dedicated Phase 10.6 Test Module
- Test File: `tests/test_phase_10_6_evidence_validation.py`
  - `test_01_observation_level_traceability_links`: Verifies end-to-end evidence linking from decision to outcome.
  - `test_02_rigorous_evaluation_identical_cohort`: Verifies identical sample pairing between model and baseline.
  - `test_03_single_class_auc_handling`: Verifies that single-class cohorts yield `INCONCLUSIVE_SINGLE_CLASS`.
  - `test_04_paired_bootstrap_determinism`: Verifies deterministic bootstrap outputs under seed lock (`seed=42`).
  - `test_05_enhanced_drift_nonparametric_diagnostics`: Verifies median, IQR, and Kolmogorov-Smirnov detection.
  - `test_06_cryptographic_checkpoint_sealing_and_tamper_detection`: Verifies tamper detection upon ledger modification.
  - `test_07_fastapi_endpoints_read_only_safety`: Verifies that all Phase 10.6 API endpoints are read-only and idempotent.

---

## 4. Current Population Accounting & Metric Status

| Cohort | Definition | Count | Metric Readiness Status |
| :--- | :--- | :--- | :--- |
| **Population 1** | Tracked Eligible Candidates | **6** | Coverage and monitoring active |
| **Population 2** | Clean Prospective Candidates | **2** | Pre-cutoff timing and documents verified |
| **Population 3** | Excluded / Unverified Issues | **4** | Excluded from primary statistical scoring |
| **Mature Listings** | Realized Exchange Outcomes | **0** | `INCONCLUSIVE_ZERO_MATURE_OUTCOMES` |

---

## 5. Governance Declarations

1. **Model Immutability**: `Model_6B_SME_v1.0` remains locked. No retraining, parameter tuning, or hyperparameter searching occurred.
2. **Read-Only Operation**: All monitoring, surveillance, and audit endpoints are purely read-only `GET` operations.
3. **Prohibition of Real-Money Trading**: All live broker routing, order dispatch, and live capital execution remain disabled.
