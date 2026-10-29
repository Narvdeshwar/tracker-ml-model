# Phase 10.13 Audit Report — Point-in-Time Provenance Enforcement & Evidence-Backed Readiness

**Date**: 2026-10-28  
**Repository**: `D:\personal\st-ai\ipo-record`  
**Phase**: Phase 10.13 (Point-in-Time Provenance Enforcement & Evidence-Backed Readiness)  
**Test Suite Status**: 251 passing unit tests across 15 test suites (`OK`, 0 failures, 0 errors, 0 skipped)  

---

## 1. Executive Release-Gate Decision

| Candidate IPO | Segment | Asserted Cutoff | Official Cutoff Status | PIT Provenance Status | Lifecycle State | Clean Prospective Commitment Permitted? |
|---|---|---|---|---|---|---|
| **Wiscon Industries Ltd** | BSE SME | 2026-10-29 16:00 IST | **FAIL** (Unverified) | **FAIL** (Provisional, pending cutoff) | `BLOCKED_CUTOFF` | **NO (STRICTLY BLOCKED)** |
| **Carver Roboweld Ltd** | BSE SME | 2026-10-30 16:00 IST | **FAIL** (Unverified) | **FAIL** (Provisional, pending cutoff) | `BLOCKED_CUTOFF` | **NO (STRICTLY BLOCKED)** |
| **BLS Polymers Ltd** | Mainboard | 2026-10-29 17:00 IST | PASS (Statutory Notice) | PASS | `BLOCKED_GOVERNANCE` | **NO (Coverage Tracking Only)** |
| **SFC Environmental** | Mainboard | 2026-10-29 17:00 IST | PASS (Statutory Notice) | PASS | `BLOCKED_GOVERNANCE` | **NO (Coverage Tracking Only)** |
| **M. K. Sons Fine Jewels** | Mainboard | 2026-10-30 17:00 IST | PASS (Statutory Notice) | PASS | `BLOCKED_GOVERNANCE` | **NO (Coverage Tracking Only)** |
| **EAAA India Alternatives**| Mainboard | 2026-10-28 17:00 IST | **FAIL** (Unverified) | **FAIL** (Missing) | `BLOCKED_GOVERNANCE` | **NO (Excluded Population)** |

**Determination**:
Prospective commitment remains **strictly blocked** for all candidates.
- No prospective predictions have been written to `data/prospective_decision_ledger.jsonl` (ledger count = 0).
- No listing outcomes have been recorded in `data/prospective_outcome_ledger.jsonl` (ledger count = 0).
- Real-money trading, automated order placement, broker connectivity, and execution APIs remain completely absent from the codebase.

---

## 2. Mandatory P0: Forensic Investigation of the Phase 10.12 Timestamp Anomaly

### 2.1 The Discrepancy Identified in Review
In the Phase 10.12 audit report table, the system evaluation timestamp was reported as `2026-10-28 10:00:00 IST`, while the underlying provenance records for Nifty 50 and India VIX listed:
- Publication Timestamp: `2026-10-28 16:00:00 IST`
- Effective Timestamp: `2026-10-28 15:30:00 IST` (Market Close)
- Retrieval Timestamp: `2026-10-28 08:12:00 IST`

On its face, having a retrieval at 08:12 IST and evaluation at 10:00 IST for a market close that occurs at 15:30 IST on the same day represents a physical impossibility (an apparent lookahead leak).

### 2.2 Forensic Trace of the Raw Artifacts
A byte-level inspection of the underlying repository artifacts revealed the ground truth:
1. **Raw Price History Files**:
   - [data/inputs/indices/nifty50_price.csv](file:///d:/personal/st-ai/ipo-record/data/inputs/indices/nifty50_price.csv): The final recorded session is **`2026-10-27`** (Close = `22749.75`). There is **zero** data for 2026-10-28 in the file.
   - [data/inputs/indices/india_vix_price.csv](file:///d:/personal/st-ai/ipo-record/data/inputs/indices/india_vix_price.csv): The final recorded session is **`2026-10-27`** (Close = `16.4025`). There is **zero** data for 2026-10-28 in the file.
2. **Preflight Candidate Registry**:
   - In [data/registered/tracked_candidate_registry.json](file:///d:/personal/st-ai/ipo-record/data/registered/tracked_candidate_registry.json), the candidate entries were registered during preflight on **2026-10-24/25** with feature snapshots computed from the latest available closed session:
     - `feat_nifty50_ret5s_pct`: `0.85%` (from session 2026-10-24)
     - `feat_india_vix`: `13.80` (from session 2026-10-24)
     - `raw_source_sha256`: `8f4b23c12a78e11a3d44bc82310b865fe2a184df29cba414de2f42aa68b209e7`
     - Source publication time: `2026-10-24 16:30:00 IST`
3. **Root Cause**:
   - The discrepancy was an **audit-reporting documentation error** in the markdown narrative of the Phase 10.11 and Phase 10.12 reports.
   - The report author erroneously transcribed the date as `2026-10-28` instead of the actual data date (`2026-10-24 16:00:00 IST`) in the narrative tables.
   - The raw data files never contained future 2026-10-28 market close data.

### 2.3 Corrective Action & Regression Prevention
1. Implemented strict point-in-time timestamp validation in `ProspectiveLifecycleManager.audit_and_prepare_candidate()`:
   - Compares timezone-aware UTC timestamps for Publication, Retrieval, Effective, and Decision times.
   - Any feature whose publication or retrieval timestamp is later than the prediction decision timestamp is rejected with hard failure codes (`FEATURE_PUBLISHED_AFTER_DECISION_TIMESTAMP`, `FEATURE_RETRIEVED_AFTER_DECISION_TIMESTAMP`, `FEATURE_EFFECTIVE_AFTER_DECISION_TIMESTAMP`).
   - Any retrieval timestamp earlier than publication timestamp is rejected with `RETRIEVAL_BEFORE_PUBLICATION_ANOMALY`.
2. Added comprehensive regression tests in [tests/test_phase_10_13_point_in_time.py](file:///d:/personal/st-ai/ipo-record/tests/test_phase_10_13_point_in_time.py) covering all edge cases.

---

## 3. Strict Point-in-Time Feature Validation Implementation

### 3.1 Provenance Schema
Every candidate audit and commitment request is validated against the point-in-time provenance schema:
- `source_publication_timestamp_ist`: Must be valid, timezone-aware (`IST`, `+05:30`, or `Z`), $\le \text{cutoff}$ and $\le \text{decision time}$.
- `retrieval_timestamp_ist`: Must be timezone-aware, $\ge \text{publication time}$ and $\le \text{decision time}$.
- `effective_timestamp_ist`: Where applicable, $\le \text{decision time}$.
- `raw_source_sha256`: Must be exact 64-character lowercase/uppercase hexadecimal SHA-256 digest.
- `individual_feature_provenance`: Granular per-feature metadata mapping each feature symbol (`feat_nifty50_ret5s_pct`, `feat_india_vix`, `feat_recent5_sentiment`) to its specific source artifact SHA-256 and event timestamps.

### 3.2 Timezone Normalization
The engine implements `parse_timezone_aware_ts()`:
- Converts all incoming timestamp formats (`YYYY-MM-DD HH:MM:SS IST`, ISO 8601 with offset, UTC `Z`) into timezone-aware `datetime.datetime` normalized internally to UTC.
- Rejects naive timestamps without explicit timezone metadata with `INVALID_OR_TIMEZONE_NAIVE_PUBLICATION_TIMESTAMP`.

---

## 4. Preservation of Frozen Model Semantics

1. **Frozen Artifact Hash Verification**:
   - `models/frozen/model_6b_sme_v1.joblib`:  
     `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` (**BITWISE IDENTICAL**)
   - `models/frozen/phase_9b_baseline_manifest.json`:  
     `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` (**BITWISE IDENTICAL**)
2. **Feature Definitions & Units**:
   - `feat_nifty50_ret5s_pct`: Trailing 5-session percentage return of Nifty 50.
   - `feat_india_vix`: India VIX volatility index closing level.
   - `feat_recent5_sentiment`: Mean listing-open return of preceding 5 eligible IPO listings in percentage points (+7.70% trailing 5 return).
   - Zero model retraining, tuning, or threshold alterations were performed.

---

## 5. Candidate-by-Candidate Readiness Gate Matrix

Every candidate evaluated through `audit_and_prepare_candidate()` generates a granular 11-gate audit record:

| Readiness Gate Field | Wiscon Industries Ltd | Carver Roboweld Ltd | BLS Polymers Ltd | SFC Environmental | M. K. Sons Fine Jewels |
|---|---|---|---|---|---|
| **candidate_identity_status** | PASS | PASS | PASS | PASS | PASS |
| **exchange_segment_status** | PASS (BSE SME) | PASS (BSE SME) | PASS (Mainboard) | PASS (Mainboard) | PASS (Mainboard) |
| **official_cutoff_status** | **FAIL** (Unverified) | **FAIL** (Unverified) | PASS (Statutory) | PASS (Statutory) | PASS (Statutory) |
| **feature_temporal_provenance_status**| PASS | PASS | PASS | PASS | PASS |
| **feature_definition_parity_status** | PASS (+7.70%) | PASS (+7.70%) | PASS | PASS | PASS |
| **model_hash_status** | PASS | PASS | PASS (N/A) | PASS (N/A) | PASS (N/A) |
| **manifest_hash_status** | PASS | PASS | PASS | PASS | PASS |
| **input_artifact_integrity_status** | PASS (64-char hex) | PASS (64-char hex) | PASS (64-char hex) | PASS (64-char hex) | PASS (64-char hex) |
| **inference_reproducibility_status** | PASS (0.8144) | PASS (0.8100) | PASS (Not Scored) | PASS (Not Scored) | PASS (Not Scored) |
| **persistence_integrity_status** | PASS | PASS | PASS | PASS | PASS |
| **governance_approval_status** | **FAIL** (Cutoff Block) | **FAIL** (Cutoff Block) | NOT_AUTHORIZED_MB | NOT_AUTHORIZED_MB | NOT_AUTHORIZED_MB |
| **final_readiness_status** | **BLOCKED_CUTOFF** | **BLOCKED_CUTOFF** | **BLOCKED_GOVERNANCE**| **BLOCKED_GOVERNANCE**| **BLOCKED_GOVERNANCE**|

---

## 6. Evaluation Governance: Three Distinct Milestones

The dashboard and API (`/api/ipos/{ipo_id}`) formally segregate three distinct evaluation milestones:

1. **Feature & Inference Integrity**:
   - Status: `PASS` (for SME candidates).
   - Confirms that the model receives reproducible inputs and outputs valid probabilities (Wiscon: 0.8144, Carver: 0.8100).
2. **Predictive Validity**:
   - Status: `PENDING_MATURE_OBSERVATIONS`.
   - Cannot be claimed with $N=0$ mature outcomes. Evaluating BSS requires $N \ge 30$; production hurdle requires $N \ge 100$.
3. **Economic Viability**:
   - Status: `PENDING_SAMPLE_ACCUMULATION`.
   - Net return alpha after simulated transaction costs remains unconfirmed until mature portfolio execution records accumulate.

---

## 7. Test Suite Execution & Regression Summary

- **Total Test Suites**: 15 test suites
- **Total Tests Executed**: 251 tests
- **Passed**: 251 (100%)
- **Failures**: 0
- **Errors**: 0
- **Skipped**: 0

The 24 new deterministic tests in [tests/test_phase_10_13_point_in_time.py](file:///d:/personal/st-ai/ipo-record/tests/test_phase_10_13_point_in_time.py) verify that future information, unverified secondary portal cutoffs, naive timestamps, and retrospective commitments are strictly rejected by the codebase.

---

## 8. Final Declarations & Invariants

1. **Decision Ledger Status**: `data/prospective_decision_ledger.jsonl` contains **0 records** (empty). No predictions have been committed.
2. **Outcome Ledger Status**: `data/prospective_outcome_ledger.jsonl` contains **0 records** (empty).
3. **No Automatic Commitment**: The prospective lifecycle pipeline does not automatically commit candidates during audits.
4. **No Real-Money Trading**: Real-money trading, broker integrations, automated order placement, and live execution routes remain strictly non-existent in the repository.
