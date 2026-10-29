# Phase 10.9 Audit Report — Candidate Evidence Repair & First-Decision Readiness

**Status**: Verified Complete & Hardened  
**Date**: 2026-10-28  
**Repository**: `D:\personal\st-ai\ipo-record`  
**Test Suite**: 211 passing tests across 11 test modules (`OK`, 0 errors, 0 failures)  

---

## Executive Summary

Phase 10.9 addresses the critical discrepancies identified during Phase 10.8 auditing:
1. **Feature Parity Resolution**: Resolved the definition mismatch in `feat_recent5_sentiment`. The frozen SME model (`Model_6B_SME_v1.0`) was trained on the **mean listing-open return of the previous five IPOs in percentage points** ($\mu = 39.93\%$, $\sigma = 30.15\%$), *not* the fraction of positive openings multiplied by 100.
2. **Empirical Trailing-5 Reconstruction**: Reconstructed the trailing five listing outcomes prior to 2026-10-29 directly from the verified historical dataset (`data/processed/ipo_market_features.csv`). The reconstructed average listing-open return is **$+7.70\%$** (replacing the invalid substitute `80.0`).
3. **Source Provenance & Hash Enforcement**: Enforced exact 64-character lowercase hexadecimal SHA-256 digests across all candidate registry records and lifecycle calls. Replaced placeholder/abbreviated hashes with verified SHA-256 digests.
4. **Cutoff Integrity & Strict Gatekeeping**: Formally bifurcated the exchange order book bidding cutoff (16:00 IST) from the UPI payment mandate deadline (17:00 IST). Prospective commitment remains **strictly blocked** for all upcoming candidates (`Wiscon Industries Ltd` and `Carver Roboweld Ltd`) pending official exchange bidding circulars.
5. **Persistence Hardening**: Added re-entrant threading locks (`threading.Lock()`), explicit buffer flushes (`f.flush()`), and kernel-level filesystem synchronization (`os.fsync()`) to protect decision and outcome ledgers against crash corruption and torn writes.
6. **Threat Model Clarification**: Accurately classified `SHA256_SEALED_DIGEST` as a multi-file snapshot digest and hash seal (not an asymmetric cryptographic digital signature).

---

## 1. Feature Parity Resolution: `feat_recent5_sentiment`

### 1.1 Model Training Specification vs. Registry Input
Inspection of the frozen pipeline artifact [model_6b_sme_v1.joblib](file:///d:/personal/st-ai/ipo-record/models/frozen/model_6b_sme_v1.joblib) revealed the exact `StandardScaler` parameters:
- **Feature 1 (`feat_nifty50_ret5s_pct`)**: $\text{mean} = 0.3963\%$, $\text{var} = 3.4542$ ($\sigma = 1.8585\%$)
- **Feature 2 (`feat_india_vix`)**: $\text{mean} = 14.8206$, $\text{var} = 16.7544$ ($\sigma = 4.0932$)
- **Feature 3 (`feat_recent5_sentiment`)**: $\text{mean} = 39.9282\%$, $\text{var} = 909.2531$ ($\sigma = 30.1538\%$)

In the training pipeline, `recent5_mean_listing_open_return_pct` represents the arithmetic mean percentage gain/loss at market open across the preceding 5 IPO listings. 

Passing `80.0` (derived from an 80% positive opening rate) into the scaler produced:
$$z = \frac{80.0 - 39.9282}{30.1538} = +1.3289\sigma$$
This inflated Wiscon's predicted probability to $0.8458$ and Carver's to $0.8415$.

### 1.2 Deterministic Reconstruction of Preceding 5 Listings
Querying the verified historical dataset [ipo_market_features.csv](file:///d:/personal/st-ai/ipo-record/data/processed/ipo_market_features.csv) for the 5 most recent listing outcomes prior to 2026-10-29 yields:

| # | IPO ID | Listing Date | Listing Open Return (%) |
|---|---|---|---|
| 1 | `ipo-2026-10-06-ine029n01014` | 2026-10-06 | $+2.40\%$ |
| 2 | `ipo-2026-10-06-ine0rnf01016` | 2026-10-06 | $-20.00\%$ |
| 3 | `ipo-2026-10-06-ine18cu01023` | 2026-10-06 | $0.00\%$ |
| 4 | `ipo-2026-10-06-ine1kul01020` | 2026-10-06 | $+42.25\%$ |
| 5 | `ipo-2026-10-06-ine307k01028` | 2026-10-06 | $+13.85\%$ |

$$\text{Trailing-5 Mean Return} = \frac{2.40 - 20.00 + 0.00 + 42.25 + 13.85}{5} = \mathbf{+7.70\%}$$

Standardized with the frozen model's scaler:
$$z = \frac{7.70 - 39.9282}{30.1538} = -1.0688\sigma$$

### 1.3 Calibrated Probability Comparison

| Candidate | Pre-Parity (Invalid $80.0$) | Post-Parity ($+7.70\%$) | Absolute Shift | Status |
|---|---|---|---|---|
| **Wiscon Industries Ltd** | $0.8458$ ($84.58\%$) | **$0.8144$ ($81.44\%$)** | $-3.14\%$ | BLOCKED |
| **Carver Roboweld Ltd** | $0.8415$ ($84.15\%$) | **$0.8100$ ($81.00\%$)** | $-3.15\%$ | BLOCKED |

The feature calculation has been codified in `calculate_trailing_5_sentiment(cutoff_date_str)` within [src/prospective_lifecycle.py](file:///d:/personal/st-ai/ipo-record/src/prospective_lifecycle.py) and verified by unit tests.

---

## 2. Provenance & Hash Hardening

1. **Strict 64-Character Hexadecimal Regex**:
   `validate_prospective_evidence()` now strictly enforces `^[0-9a-f]{64}$`. Any record containing placeholders (`"pending"`, `"hash123"`), abbreviated strings, or upper-case characters is rejected with `MISSING_OR_INVALID_PROVENANCE_HASH`.
2. **Authoritative Evidence Verification**:
   All candidates in [data/registered/tracked_candidate_registry.json](file:///d:/personal/st-ai/ipo-record/data/registered/tracked_candidate_registry.json) now contain verified 64-character SHA-256 hashes of the preflight notices and statutory filings.

---

## 3. Cutoff Integrity & Gatekeeping

1. **16:00 IST vs 17:00 IST Boundary Separation**:
   In Indian equity market microstructure, the exchange order book bidding window for retail/HNI bids closes at **16:00:00 IST** on the final issue day. The **17:00:00 IST** deadline is exclusively for UPI payment mandate approvals via the sponsor bank / NPCI gateway.
2. **Preflight Registration vs Decision Gate**:
   - `is_timing_verified: true` confirms that preflight filing data, board categorization, and prospectus dates have been reviewed.
   - `is_bidding_cutoff_verified: false` enforces that the official exchange circular confirming order book cutoff and live pre-cutoff book data has not yet been ingested.
   - `commit_prospective_decision()` enforces both flags. If `is_bidding_cutoff_verified` is false, commitment is aborted with `UNVERIFIED_BIDDING_CUTOFF`.

---

## 4. Durability & Crash Recovery

The prospective persistence layer in [src/prospective_simulator_logger.py](file:///d:/personal/st-ai/ipo-record/src/prospective_simulator_logger.py) has been upgraded:
- **Thread Safety**: Wrapped file appending operations in `threading.Lock()` to prevent race conditions during concurrent API requests.
- **Kernel-Level Sync**: Implemented `f.flush()` followed immediately by `os.fsync(f.fileno())` after every write operation, ensuring records reach physical disk storage before returning.
- **Idempotency & Replay Protection**: Exact candidate prediction and outcome lookups check existing ledger contents before writing. Duplicate attempts return the existing record ID.
- **Fault-Tolerant Scanning**: Leading/trailing blank lines or corrupted trailing lines in JSONL ledgers trigger audit warnings without crashing the reader.

---

## 5. Security & Threat Model

- **Digest Seal Classification**: `SHA256_SEALED_DIGEST` is explicitly documented as a multi-file SHA-256 snapshot seal. It verifies data integrity against accidental file tampering, hardware corruption, or out-of-band file edits. It is not an asymmetric PKI signature (which would require private key infrastructure).
- **Execution Safeguards**: Real-money trading, live order routing, and broker APIs remain strictly non-existent in the codebase.

---

## 6. Verification & Invariant Audit

| Check | Specification | Verified Status |
|---|---|---|
| **Frozen SME Model SHA-256** | `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` | Bitwise Identical |
| **Baseline Manifest SHA-256** | `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` | Bitwise Identical |
| **Full Unit Test Suite** | 211 tests across 11 test modules | **211 Passed, 0 Failed, 0 Errors** |
| **Decision Ledger Status** | `data/prospective_decision_ledger.jsonl` | 0 records (empty / uncommitted) |
| **Outcome Ledger Status** | `data/prospective_outcome_ledger.jsonl` | 0 records (empty / uncommitted) |
| **Wiscon Decision Status** | Blocked Pending Official Circular Audit & Live Pre-Cutoff Features | Strictly Enforced |
| **Carver Decision Status** | Blocked Pending Official Circular Audit & Live Pre-Cutoff Features | Strictly Enforced |
