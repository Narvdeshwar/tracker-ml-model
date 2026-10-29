# Phase 10.8 Audit: Pre-Commitment Integrity Hardening & Discrepancy Resolution

**Repository**: `D:\personal\st-ai\ipo-record`  
**Date**: October 28, 2026  
**Auditor**: Senior Quantitative Researcher & ML Audit Engineer  
**Status**: **INTEGRITY HARDENING VERIFIED (211/211 Passing Tests) — REAL PROSPECTIVE COMMITMENT STRICTLY BLOCKED PENDING OFFICIAL CIRCULAR AUDIT**  
**Real-Money Live Trading**: **STRICTLY PROHIBITED (Zero Broker Connections)**

---

## Executive Summary

Phase 10.8 resolves critical data integrity, feature parity, and operational cutoff questions prior to committing any real prospective prediction. 

This phase focuses exclusively on **verification, hardening, fault injection, and discrepancy resolution**:
1. **Critical Feature Discrepancy Resolved**:
   - Traced `feat_recent5_sentiment` directly through historical training files and the frozen pipeline artifact.
   - Identified a critical discrepancy: the frozen pipeline's StandardScaler mean ($\mu = 39.9282$, $\sigma = 30.1538$) reflects **average listing-open return in percentage points** (`recent5_mean_listing_open_return_pct`), *not* positive opening rate ($0.0 - 1.0$).
   - In `src/phase_9b_preflight_runner.py` and `data/registered/tracked_candidate_registry.json`, sentiment was improperly recorded as `80.0` (derived from multiplying an 80% positive rate by 100).
   - This unit discrepancy is formally documented, regression-tested, and candidate prospective commitment is **strictly blocked** until verified mean opening returns are captured.
2. **Provenance Guardrails Hardened**:
   - Rejects placeholder, abbreviated (< 64 characters), or non-hex hashes (`MISSING_OR_INVALID_PROVENANCE_HASH`).
   - Requires 8 granular provenance fields (`feature_name`, `feature_value`, `source_name`, `source_published_at`, `retrieved_at`, `effective_at`, `source_sha256`, `transformation_version`).
   - Rejects observations where feature publication timestamp exceeds decision cutoff ($T_{\text{pub}} > T_{\text{cutoff}}$).
3. **Atomic Commitment & Fault Injection Verified**:
   - Added atomic persistence (`flush()` and `os.fsync()`) in `ProspectiveDecisionLogger`.
   - Validated through fault injection that corrupt/interrupted lines break ledger validation immediately and duplicate retries cannot append records or alter hash chains.
4. **Accurate Checkpoint Threat Modeling**:
   - Reframed from digital signature to **"Cryptographic Multi-File Snapshot Digest & Hash Seal"** (`SHA256_SEALED_DIGEST`).
   - Documented exact threats detected vs. threats not detected by aggregate SHA-256 seals.
5. **Enforced Candidate Cutoff Gates**:
   - Disallowed assuming 16:00, 16:30, or 17:00 IST by default. Separates exchange bidding cutoff from UPI mandate deadlines.
   - Requires `is_bidding_cutoff_verified = True` from authoritative BSE SME circulars. Candidates lacking independent circular verification are retained in Population 3 (Excluded).
6. **Test Coverage**:
   - Total test suite expanded to **211 / 211 passing tests** across 30 test modules.
   - Frozen SME model and baseline manifest remain bit-for-bit unchanged.

---

## 1. Feature Parity & Discrepancy Audit (`feat_recent5_sentiment`)

### 1.1 Complete Traceability from Step 5C to Frozen Model Artifact

| Layer | Source File / Artifact | Definition & Target Column | Empirical Distribution (SME 2020-2024, N=367) |
| :--- | :--- | :--- | :--- |
| **Ingestion (Step 5C)** | `src/build_recent_ipo_sentiment.py` | `recent5_mean_listing_open_return_pct` vs `recent5_positive_listing_rate` | Mean return: $\mu = 39.94\%$, $\sigma = 30.24\%$<br/>Positive rate: $\mu = 0.805$, $\sigma = 0.194$ |
| **Model Training (Step 6A)** | `src/export_frozen_sme_model.py` | `df_sme_train['feat_recent5_sentiment'] = df_sme_train['recent5_mean_listing_open_return_pct']` | Fitted on mean percentage return ($\mu = 39.93\%$) |
| **Frozen Pipeline Artifact** | `models/frozen/model_6b_sme_v1.joblib` | `StandardScaler().mean_[2] = 39.92817935`<br/>`StandardScaler().var_[2] = 909.25313065` | **Exact match to `recent5_mean_listing_open_return_pct`** |
| **Candidate Registry (Preflight)** | `data/registered/tracked_candidate_registry.json` | `"feat_recent5_sentiment": 80.0` | **DISCREPANCY DETECTED: Positive rate (0.80) was multiplied by 100 instead of computing actual trailing open return** |
| **Manifest Documentation** | `models/frozen/phase_9b_baseline_manifest.json` | Listed as `"recent5_positive_listing_rate"` | **DOCUMENTATION AMBIGUITY**: Manifest text references positive rate, but binary model artifact was trained on mean return. |

### 1.2 Mathematical Impact of Unit Discrepancy
Evaluating the frozen pipeline on historical validation samples revealed:
- When passing mean returns ($\approx 35\% - 45\%$), the model outputs calibrated probabilities ($p \approx 0.75 - 0.85$).
- When passing `80.0` (from an 80% positive rate scaled by 100), the sentiment z-score is inflated by $+1.33\sigma$, shifting predicted opening probabilities by an absolute average of **$4.27\%$ (up to $11.91\%$ maximum shift)**.

### 1.3 Governance Policy & Blocking Action
- **Rule**: In accordance with the prompt's mandatory constraint, we do **not guess, retrain, or silently change the frozen model**.
- **Enforcement**:
  1. The frozen model artifact strictly expects **average listing-open return in percentage points** (`feat_recent5_sentiment`).
  2. Candidate preflight values of `80.0` derived from positive rate are invalid inputs.
  3. **Prospective scoring for Wiscon Industries and Carver Roboweld is BLOCKED** until the exact trailing 5 listing outcomes are deterministically calculated from verified exchange Bhavcopy files and expressed as mean percentage returns.

---

## 2. Source Provenance Hardening & Lookahead Guardrails

### 2.1 Rejection of Placeholder or Abbreviated Hashes
`src/prospective_lifecycle.py` now validates that `raw_source_sha256` is an exact 64-character hexadecimal SHA-256 digest:
```python
has_raw_hash = bool(raw_hash and isinstance(raw_hash, str) and len(raw_hash) == 64 and all(c in '0123456789abcdefABCDEF' for c in raw_hash))
```
Any record containing abbreviated (e.g. 8-character), placeholder (`PLACEHOLDER_...`), or missing hashes is excluded from `Population_2_Clean_Prospective` with:
`MISSING_OR_INVALID_PROVENANCE_HASH: Must be exact 64-char hex SHA-256`.

### 2.2 Eight-Field Provenance Record
Every prospective feature snapshot requires:
1. `feature_name`: Exact column name.
2. `feature_value`: Valid, finite float.
3. `source_name`: Authoritative provider / exchange circular.
4. `source_published_at`: Timestamp stamped by provider.
5. `retrieved_at`: Local retrieval timestamp.
6. `effective_at`: Effective trading date.
7. `source_sha256`: Digest of raw payload.
8. `transformation_version`: Code version calculating metric (`v1.0_step5c`).

---

## 3. Atomic Commitment & Fault Injection

### 3.1 Persistence Implementation
In `src/prospective_simulator_logger.py`, ledger appending incorporates explicit kernel-level synchronization:
```python
with open(self.decision_ledger, 'a', encoding='utf-8') as f:
    f.write(json.dumps(record) + '\n')
    f.flush()
    os.fsync(f.fileno())
```

### 3.2 Fault-Injection Regression Test Results
Validated in `tests/test_phase_10_8_integrity_hardening.py`:
- `test_05_atomic_commitment_fault_injection`: Injected partial/truncated JSON lines simulating mid-write process crashes or disk full errors. `verify_ledger_chain()` immediately catches syntax corruption and halts downstream evaluation.
- `test_06_idempotent_retry_cannot_mutate_or_duplicate`: Validated that retrying an already committed decision returns `DUPLICATE_IGNORED` with zero file modifications or hash chain breaks.

---

## 4. Cryptographic Checkpoint Threat Analysis

The checkpoint established in `data/processed/governance_checkpoint_signature.json` is accurately termed a **Cryptographic Multi-File Snapshot Digest & Hash Seal** (`SHA256_SEALED_DIGEST`).

### 4.1 Threat Modeling Matrix

| Threat Category | Specific Attack Vector | Detected by SHA-256 Seal? | Detection Mechanism |
| :--- | :--- | :---: | :--- |
| **Historical Ledger Truncation** | Deleting past unfavorable decisions or failed trades. | **YES** | Decision ledger SHA-256 mismatch upon checkpoint verification. |
| **Line Mutation** | Editing timestamps, probabilities, or outcomes in-place. | **YES** | Content SHA-256 breaks individual line hash and overall file digest. |
| **Record Reordering** | Swapping chronology of two committed decisions. | **YES** | Ledger previous-hash chain breaks (`prev_record_sha256` mismatch). |
| **Model Substitution** | Replacing frozen SME model with retrained or tuned binary. | **YES** | Model binary SHA-256 digest mismatch. |
| **Manifest Tampering** | Altering baseline probabilities or decision hurdles. | **YES** | Manifest SHA-256 digest mismatch. |
| **Attacker Replaces Data AND Checkpoint** | Malicious local process overwrites all ledgers and recomputes local checkpoint. | **NO (Local Only)** | Local hash verification cannot detect total local overwrite without an external, independently controlled anchor. |
| **Identity Authentication** | Proving who authorized or generated a specific commitment. | **NO (Hash Only)** | Symmetric SHA-256 does not provide asymmetric public-key signature or non-repudiation. |

---

## 5. Candidate Cutoff Verification & Gate Status

### 5.1 Enforced Bidding Cutoff Policy
- On Indian exchanges, retail order books frequently close at **16:00:00 IST or 16:30:00 IST**, whereas UPI mandate acceptance continues until 17:00:00 IST.
- The pipeline now strictly enforces:
  ```python
  bidding_cutoff_verified = prov.get('is_bidding_cutoff_verified', False)
  if not bidding_cutoff_verified:
      reasons.append("EXCHANGE_BIDDING_CUTOFF_UNVERIFIED: Authoritative order book close not verified independently of UPI mandate")
      is_clean_eligible = False
  ```

### 5.2 Status of Current Active Candidates

| Candidate IPO | Segment | Current Registry Status | Cutoff Gate Status | Feature Parity Status | Operational Commitment Authorization |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Wiscon Industries Ltd** | BSE SME | Population 2 (Clean) | **BLOCKED** (Official BSE circular pending confirmation of 16:00 vs 17:00 IST) | **BLOCKED** (`feat_recent5_sentiment` must be reconciled to mean return) | **PROSPECTIVE COMMITMENT STRICTLY BLOCKED** |
| **Carver Roboweld Ltd** | BSE SME | Population 2 (Clean) | **BLOCKED** (Portal reports 16:00 IST; circular unverified) | **BLOCKED** (`feat_recent5_sentiment` must be reconciled to mean return) | **PROSPECTIVE COMMITMENT STRICTLY BLOCKED** |
| **BLS Polymers Ltd** | Mainboard | Population 1 (Coverage) | Tracked for coverage only | N/A (No Frozen Model) | Scored: **NO** (Coverage tracking only) |
| **EAAA Alternatives Ltd** | Mainboard | Population 3 (Excluded) | Excluded (Unverified) | N/A (Excluded) | Scored: **NO** (Excluded) |

---

## 6. Test Results & Verification

All automated tests across the codebase pass completely:

```text
D:\personal\st-ai\ipo-record\.venv\Scripts\python.exe -m unittest discover tests
Ran 211 tests in 4.852s
OK
```

Total passing tests expanded from **203 tests** (Phase 10.7) to **211 tests** (Phase 10.8).

### Bitwise Verification of Frozen Artifacts:
- `models/frozen/model_6b_sme_v1.joblib` SHA-256: `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` (Bitwise identical).
- `models/frozen/phase_9b_baseline_manifest.json` SHA-256: `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` (Bitwise identical).
- Live decision ledger: **0 committed decisions** (Untouched).
- Live outcome ledger: **0 mature outcomes** (Untouched).

---

## 7. Mandatory Governance Declaration

1. **Prospective Commitment Remains Blocked**: In accordance with mandatory constraint #6, prospective scoring for Wiscon Industries and Carver Roboweld remains **blocked** until official BSE SME bidding circulars and empirical trailing mean returns are verified.
2. **Real-Money Trading Prohibition**: All broker connectivity, automated order dispatch, and live execution remain **permanently disabled**.
3. **Model Immutability**: `Model_6B_SME_v1.0` remains locked; no retraining or tuning took place.
