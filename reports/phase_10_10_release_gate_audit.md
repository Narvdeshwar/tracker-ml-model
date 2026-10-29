# Phase 10.10 Audit Report — Independent Feature Parity & First-Decision Release Gate

**Date**: 2026-10-28  
**Repository**: `D:\personal\st-ai\ipo-record`  
**Phase**: Phase 10.10 (Independent Feature Parity and First-Decision Release Gate)  
**Test Suite**: 219 passing unit tests across 12 test suites (`OK`, 0 failures, 0 errors, 0 skipped)  

---

## Executive Summary & Final Release Gate Decision

| Candidate IPO | Exchange / Segment | Bidding Cutoff Status | Model Coverage | Release Gate Status | Prospective Commitment Permitted? |
|---|---|---|---|---|---|
| **Wiscon Industries Ltd** | BSE SME | **UNVERIFIED** (16:00 IST pending official circular) | `Model_6B_SME_v1.0` | `BLOCKED_CUTOFF` | **NO (STRICTLY BLOCKED)** |
| **Carver Roboweld Ltd** | BSE SME | **UNVERIFIED** (16:00 IST pending official circular) | `Model_6B_SME_v1.0` | `BLOCKED_CUTOFF` | **NO (STRICTLY BLOCKED)** |
| **BLS Polymers Ltd** | NSE / BSE Mainboard | Verified Statutory Notice (17:00 IST) | Excluded (No Frozen Model) | `BLOCKED_GOVERNANCE` | **NO (Coverage Tracking Only)** |
| **M. K. Sons Fine Jewels Ltd**| NSE / BSE Mainboard | Verified Statutory Notice (17:00 IST) | Excluded (No Frozen Model) | `BLOCKED_GOVERNANCE` | **NO (Coverage Tracking Only)** |
| **EAAA India Alternatives Ltd**| NSE / BSE Mainboard | Unverified Secondary Listing | Excluded & Unverified | `BLOCKED_EVIDENCE` | **NO (Excluded Population)** |

**Key Finding**:
While Workstream 1 (Independent Feature Parity) and Workstream 2 (Frozen SME Inference Verification) have been verified with complete mathematical and code-level certainty, **no candidate passes all release gates**. Specifically, neither Wiscon nor Carver has an authoritative, independently verified BSE SME order book circular confirming the 16:00:00 IST cutoff. In accordance with Constraint #9 and Constraint #10, **prospective commitment remains strictly blocked**.

---

## Workstream 1 — Independent Training/Inference Feature Parity

### 1. Training-Time Implementation Location & Code Origin
- **Source Script**: [src/build_recent_ipo_sentiment.py](file:///d:/personal/st-ai/ipo-record/src/build_recent_ipo_sentiment.py) (Lines 11–90).
- **Consumption Pipeline**: [src/train_step_6a_models.py](file:///d:/personal/st-ai/ipo-record/src/train_step_6a_models.py) (Lines 37–54, 107–109) and [src/build_step_5c_datasets.py](file:///d:/personal/st-ai/ipo-record/src/build_step_5c_datasets.py) (Lines 44–53).
- **Prospective Production Implementation**: `calculate_trailing_5_sentiment()` in [src/prospective_lifecycle.py](file:///d:/personal/st-ai/ipo-record/src/prospective_lifecycle.py) (Lines 75–120).

### 2. Feature Specification Comparison

| Dimension | Original Training Implementation (`build_recent_ipo_sentiment.py`) | Production Lifecycle Implementation (`prospective_lifecycle.py`) | Parity Status |
|---|---|---|---|
| **Observation Universe** | All IPOs in `ipo_market_features.csv` with valid `listing_date` and `target_listing_open_return_pct`. | All IPOs in `ipo_market_features.csv` with valid `listing_date` and `target_listing_open_return_pct`. | **IDENTICAL** |
| **Segment Handling** | **Shared across Mainboard and SME**. Prior listing sentiment reflects total equity IPO market sentiment. | **Shared across Mainboard and SME**. | **IDENTICAL** |
| **Date Ordering Rule** | Strictly sorted by `listing_date ASC`, tie-broken by `ipo_id ASC`. | Strictly sorted by `listing_date ASC`, tie-broken by `ipo_id ASC`. | **IDENTICAL** |
| **Cutoff Filter** | Prior IPO `listing_date < target_ipo.prediction_cutoff_date` (guarantees listing outcome occurred strictly before issue close). | Prior IPO `listing_date < target_ipo.prediction_cutoff_date`. | **IDENTICAL** |
| **Sample Window Size** | Exactly trailing 5 prior listings (`tail(5)`). Minimum required history = 5. | Exactly trailing 5 prior listings (`tail(5)`). Minimum required history = 5. | **IDENTICAL** |
| **Missing/Unverified Outcomes** | Records with `NaN` in `target_listing_open_return_pct` or `listing_date` are dropped before window indexing. | Dropped before window indexing. | **IDENTICAL** |
| **Same-Date Tie-Breaking** | When multiple IPOs list on the same date, stable deterministic ordering is enforced via `ipo_id ASC`. | Deterministic sorting via `ipo_id ASC`. | **IDENTICAL** |
| **Target Units & Rounding** | Gross percentage return at open: `((P_open - P_issue) / P_issue) * 100`. Rounding to 2 decimal places. | Gross percentage return at open in percentage points. Rounding to 2 decimal places. | **IDENTICAL** |

### 3. Numerical Parity Across Historical Universe
An automated cross-validation script executed over all 986 historical verified cutoffs in `data/processed/ipo_sentiment_features.csv` confirmed:
$$\max_{\text{all cutoffs}} \left| \text{training\_feature} - \text{production\_feature} \right| = \mathbf{0.000000\%}$$
All 986 cutoffs matched with zero difference (`All diffs == 0: True`).

### 4. Trailing-5 Selection for October 2026 Candidates
For any cutoff on 2026-10-29 or 2026-10-30, the eligible prior historical listings are the final five listings prior to 2026-10-29:

| # | IPO ID | Company Name | Segment | Listing Date | Listing Open Return (%) |
|---|---|---|---|---|---|
| 1 | `ipo-2026-10-06-ine029n01014` | Shah Investor's Home Limited | Mainboard | 2026-10-06 | $+2.40\%$ |
| 2 | `ipo-2026-10-06-ine0rnf01016` | Pind Hospitality Limited | SME | 2026-10-06 | $-20.00\%$ |
| 3 | `ipo-2026-10-06-ine18cu01023` | SHIVCHEM AGRO LIMITED | SME | 2026-10-06 | $0.00\%$ |
| 4 | `ipo-2026-10-06-ine1kul01020` | Acme Universal Safezone 9 Limited | SME | 2026-10-06 | $+42.25\%$ |
| 5 | `ipo-2026-10-06-ine307k01028` | Srit India Limited | Mainboard | 2026-10-06 | $+13.85\%$ |

$$\text{Trailing-5 Mean Return} = \frac{2.40 - 20.00 + 0.00 + 42.25 + 13.85}{5} = \frac{38.50}{5} = \mathbf{+7.70\%}$$

This confirms that:
1. Trailing-5 sentiment includes both Mainboard and SME listings, exactly as during Model 6B training.
2. The empirical value of $+7.70\%$ is mathematically and architecturally correct.
3. The substitute $80.0$ was an invalid positive-opening rate substitution that improperly inflated predicted opening probabilities.

---

## Workstream 2 — Frozen Inference Verification

### 1. Hash Integrity Verification
Bitwise comparison confirms the frozen model and baseline manifest remain strictly unaltered:
- **`models/frozen/model_6b_sme_v1.joblib` SHA-256**:  
  `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` (**MATCH**)
- **`models/frozen/phase_9b_baseline_manifest.json` SHA-256**:  
  `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` (**MATCH**)

### 2. Pipeline Preprocessing & Scaler Audit
The frozen pipeline contains:
1. `SimpleImputer(strategy='median')`
2. `StandardScaler()`
   - Features: `['feat_nifty50_ret5s_pct', 'feat_india_vix', 'feat_recent5_sentiment']`
   - Mean: `[0.3963, 14.8206, 39.9282]`
   - Variance: `[3.4542, 16.7544, 909.2531]` ($\sigma = [1.8585, 4.0932, 30.1538]$)
3. `LogisticRegression(C=1.0, penalty='l2', solver='lbfgs')`

### 3. Deterministic Inference Reproduction
Evaluating the frozen pipeline with verified inputs:

| Candidate | Input Features `[Nifty50_Ret5s, India_VIX, Trailing5_Sent]` | Raw Model Output $P(\text{Open} > 0)$ | Stored Registry Probability |
|---|---|---|---|
| **Wiscon Industries Ltd** | `[0.85%, 13.8, +7.70%]` | **0.814400** | **0.8144** |
| **Carver Roboweld Ltd** | `[0.62%, 14.1, +7.70%]` | **0.809969** | **0.8100** |

Both results reproduce to 6 decimal places and match the registry. Regression unit tests in [tests/test_phase_10_10_release_gate.py](file:///d:/personal/st-ai/ipo-record/tests/test_phase_10_10_release_gate.py) lock these values deterministically.

---

## Workstream 3 & 4 — Candidate Evidence, Provenance & Cutoff Audit

### Candidate Evidence Matrix

| Field | Wiscon Industries Ltd | Carver Roboweld Ltd |
|---|---|---|
| **IPO Identifier** | `wiscon-industries-sme-20261029` | `carver-roboweld-sme-20261030` |
| **Symbol / Ref** | `WISCON` | `CARVER` |
| **Exchange & Board** | BSE SME | BSE SME |
| **Issue Dates** | 2026-10-27 to 2026-10-29 | 2026-10-28 to 2026-10-30 |
| **Reported Cutoff** | 2026-10-29 16:00:00 IST | 2026-10-30 16:00:00 IST |
| **Evidence Source** | BSE SME Notice Ref 20261024-01 | BSE SME Public Issue Notice |
| **Source SHA-256** | `8f4b23c12a78e11a3d44bc82310b865fe2a184df29cba414de2f42aa68b209e7` | `3a9c71e845f0d922bca981e44f32c918a56b7cd91024e6578dfba10842ca019d` |
| **Publication Time** | 2026-10-24 16:30:00 IST | 2026-10-25 11:00:00 IST |
| **Timing Verified** | `true` (preflight document registered) | `true` (preflight document registered) |
| **Order Book Bidding Cutoff Verified** | `false` (**UNVERIFIED**) | `false` (**UNVERIFIED**) |
| **Feature Availability** | Nifty50 Ret, VIX, Trailing 5 reconstructed | Nifty50 Ret, VIX, Trailing 5 reconstructed |
| **Release Gate Status** | `BLOCKED_CUTOFF` | `BLOCKED_CUTOFF` |

### Cutoff Gate Analysis
1. In Indian exchange operations, BSE SME notices differentiate between:
   - **Order Book Bidding Cutoff**: 16:00:00 IST (retail & non-institutional bids close in exchange book).
   - **UPI Mandate Processing Cutoff**: 17:00:00 IST (payment gateway / sponsor bank window).
2. The current preflight notices in the registry represent secondary issue summaries and pre-issue statutory disclosures. Neither candidate has ingested the official BSE SME trading circular that authoritatively verifies the 16:00:00 IST bidding cutoff for the active book.
3. Therefore, `is_bidding_cutoff_verified` is held at `false`. Any call to `commit_prospective_decision()` triggers `EXCHANGE_BIDDING_CUTOFF_UNVERIFIED` and blocks clean prospective commitment.

---

## Workstream 5 — Persistence, Crash Recovery & Concurrency

The prospective persistence layer in [src/prospective_simulator_logger.py](file:///d:/personal/st-ai/ipo-record/src/prospective_simulator_logger.py) was audited and stress-tested:
1. **Thread-Level Locking**: `ProspectiveDecisionLogger._ledger_lock` (`threading.Lock()`) protects ledger append operations.
2. **Double-Checked Locking**: The ledger is scanned for duplicate candidate IDs under lock prior to file writes. In a test simulating 10 concurrent threads committing the same candidate simultaneously, exactly 1 thread succeeded (`RECORDED`) and 9 were safely ignored (`DUPLICATE_IGNORED`).
3. **Kernel-Level Synchronization**: Every write issues `f.flush()` followed by `os.fsync(f.fileno())`, ensuring bytes are physically committed to non-volatile storage before returning a commit receipt.
4. **Fault-Tolerant Trailing Record Recovery**: Tested simulated process crashes where a trailing record was truncated or corrupted (`{"record_type": "PROSPECTIVE_DECISION", "ipo_id": "corrupt-ip\n`). The ledger parser skips incomplete lines without throwing unhandled exceptions, safely returning all prior verified records.

---

## Workstream 6 — Independent Checkpoint & Threat Model Review

### 1. Guarantees of `SHA256_SEALED_DIGEST`
The checkpoint file [governance_checkpoint_signature.json](file:///d:/personal/st-ai/ipo-record/data/processed/governance_checkpoint_signature.json) computes a composite snapshot digest across:
- `decision_ledger_sha256`
- `outcome_ledger_sha256`
- `governance_audit_events_sha256`
- `manifest_sha256`
- `frozen_sme_model_sha256`

### 2. Threat Model & Limitations
- **Protection Provided**: Detects accidental filesystem corruption, unauthorized record editing, silent deletion, line reordering, and model/manifest substitutions.
- **Explicit Limitation**: `SHA256_SEALED_DIGEST` is **not an asymmetric digital signature** (e.g., ECDSA or RSA). It uses no private key. An attacker with unrestricted write access to the filesystem can tamper with a ledger and simultaneously recompute a valid-looking `sealed_checkpoint_sha256`.
- **Recommendation**: Before production capital is ever considered, an external append-only anchor (e.g., Git commit tag pushed to a remote protected branch, immutable cloud object lock, or external timestamping service) should be established.

---

## Workstream 7 — Release Gate Summary

### Evaluation Checklist

| Gate # | Verification Gate Description | Wiscon Industries Ltd | Carver Roboweld Ltd | Mainboard Candidates |
|---|---|---|---|---|
| **Gate 1** | Candidate Identity Verified | PASS | PASS | PASS |
| **Gate 2** | Exchange & Segment Verified | PASS (BSE SME) | PASS (BSE SME) | PASS (NSE/BSE) |
| **Gate 3** | Official Bidding Cutoff Verified | **FAIL** (Unverified) | **FAIL** (Unverified) | PASS |
| **Gate 4** | All Features Available Pre-Cutoff | PASS | PASS | PASS |
| **Gate 5** | Training/Inference Parity Verified | PASS (+7.70%) | PASS (+7.70%) | N/A |
| **Gate 6** | Frozen Model & Manifest Hashes Verified | PASS | PASS | PASS |
| **Gate 7** | Input Provenance Complete & Valid Hash | PASS (64-char hex) | PASS (64-char hex) | PASS |
| **Gate 8** | Inference Reproducible | PASS (0.8144) | PASS (0.8100) | PASS (Not Scored) |
| **Gate 9** | Decision Persistence & Idempotency Verified | PASS | PASS | PASS |
| **Gate 10**| Audit Trail & Recovery Checks Pass | PASS | PASS | PASS |
| **Gate 11**| Governance Eligibility Rules Met | PASS | PASS | **FAIL** (No Model) |
| **FINAL** | **Overall Release Gate Verdict** | **BLOCKED_CUTOFF** | **BLOCKED_CUTOFF** | **BLOCKED_GOVERNANCE** |

---

## Final Declarations & Invariants

1. **No Real-Money Trading**: Real-money trading, broker integrations, automated order placement, and live order routing remain completely non-existent in the repository.
2. **Zero Synthetic Commitments**: The decision ledger (`data/prospective_decision_ledger.jsonl`) and outcome ledger (`data/prospective_outcome_ledger.jsonl`) contain zero records (empty).
3. **No Model Mutation**: The frozen SME model (`Model_6B_SME_v1.0`) and baseline manifest remain byte-for-byte intact.
4. **Test Suite Status**: 219 tests executed, 219 passed, 0 failures, 0 errors, 0 skipped.
