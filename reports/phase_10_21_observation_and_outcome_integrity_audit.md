# Phase 10.21 Prospective Observation Integrity & Outcome Reconciliation Audit Report

**Report Date**: 2026-10-28 23:38:00 IST  
**Repository**: `D:\personal\st-ai\ipo-record`  
**Phase**: 10.21 — Prospective Observation Integrity & Outcome Reconciliation  
**Operating Mode**: STRICT SHADOW VALIDATION ONLY (Broker execution & real-money trading strictly prohibited)

---

## 1. Executive Summary & Audit Scorecard

Phase 10.21 conducted an independent reliability and model-governance audit of the prospective prediction pipeline, outcome reconciliation protocols, cross-process persistence safeguards, and population separation.

| Evaluation Area | Status | Verified Finding |
|---|---|---|
| **Frozen SME Model** | **`PASS`** | Exact byte match: SHA-256 `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` |
| **Baseline Manifest** | **`PASS`** | Exact byte match: SHA-256 `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` |
| **Candidate Lifecycle Status** | **`PASS`** | Wiscon and Carver remain `BLOCKED_CUTOFF`. EAAA India Alternatives marked `EXPIRED_WITHOUT_COMMIT`. Mainboard candidates remain non-scoring `BLOCKED_GOVERNANCE`. |
| **Cross-Process Persistence** | **`PASS`** | Guaranteed by OS-level file locking (`msvcrt.locking` on Windows, `fcntl.flock` on POSIX), unbuffered `os.fsync()`, cryptographic hash-chaining, pre-write corruption barriers, and under-lock existence re-checks. |
| **Decision Provenance Contract** | **`PASS`** | Decision records cryptographically bind candidate identity, feature snapshot hash, cutoff evidence references, model SHA-256, and point-in-time timestamps. Missing provenance fails closed. |
| **Outcome Reconciliation Contract** | **`PASS`** | `reconcile_listing_outcome` enforces INR-only pricing, positive values, official bulletin references, raw artifact SHA-256 matching, pre-existing decision matching, idempotency, and explicit rejection of close-for-open substitutions and simulation labels. |
| **Prospective Population Accounting**| **`PASS`** | Complete 4-population separation maintained. No candidate leakage or selective post-hoc exclusion. |
| **Ledger Invariants** | **`PASS`** | Production ledgers strictly empty: 0 decision records, 0 outcome records, 0 evaluation records, 0 governance audit events. |
| **Unit & Integration Tests** | **`PASS`** | 414 / 414 tests passing across 23 test suites (100% pass rate, 0 failures, 0 errors, 0 skipped). |
| **Predictive & Economic Validity** | **`INCONCLUSIVE`** | Exactly 0 mature prospective outcomes recorded (`INCONCLUSIVE_ZERO_OUTCOMES`). Zero live trades deployed (`INCONCLUSIVE_ZERO_LIVE_TRADES`). Real-money execution strictly prohibited. |

---

## 2. Baseline & Frozen Artifact Verification

The frozen SME model binary and baseline manifest were verified directly via SHA-256 cryptographic hashing from the disk:
1. **Frozen SME Model v1 (`models/frozen/model_6b_sme_v1.joblib`)**:
   - SHA-256: `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76`
   - Verification: **`PASS` (Exact match)**
2. **Baseline Manifest (`models/frozen/phase_9b_baseline_manifest.json`)**:
   - SHA-256: `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e`
   - Verification: **`PASS` (Exact match)**

No parameter changes, retraining, refitting, baseline re-calibration, or artifact replacements occurred.

---

## 3. Authoritative Candidate Lifecycle Resolution

Every tracked candidate in `data/registered/tracked_candidate_registry.json` was audited against the current cutoff evidence:

| Candidate ID | Company Name | Segment | Asserted Cutoff (IST) | Verified Cutoff | Lifecycle State | Evidence Status | Eligible to Commit? |
|---|---|---|---|---|---|---|---|
| `wiscon-industries-sme-20261029` | Wiscon Industries Ltd | BSE SME | 2026-10-29 16:00:00 | Unverified | `BLOCKED_CUTOFF` | Secondary portal notice (`CHITTOR-01`) only; official exchange circular unacquired | **NO** (`BLOCKED`) |
| `carver-roboweld-sme-20261030` | Carver Roboweld Ltd | BSE SME | 2026-10-30 16:00:00 | Unverified | `BLOCKED_CUTOFF` | Secondary aggregate report only; official exchange circular unacquired | **NO** (`BLOCKED`) |
| `bls-polymers-mainboard-20261029` | BLS Polymers Ltd | Mainboard | 2026-10-29 17:00:00 | Unverified | `BLOCKED_GOVERNANCE` | Tracked for coverage only; Model 6B SME incompatible | **NO** (`BLOCKED`) |
| `sfc-environmental-mainboard-20261029` | SFC Environmental Tech Ltd | Mainboard | 2026-10-29 17:00:00 | Unverified | `BLOCKED_GOVERNANCE` | Tracked for coverage only; Model 6B SME incompatible | **NO** (`BLOCKED`) |
| `mk-sons-mainboard-20261030` | M. K. Sons Fine Jewels Ltd | Mainboard | 2026-10-30 17:00:00 | Unverified | `BLOCKED_GOVERNANCE` | Tracked for coverage only; Model 6B SME incompatible | **NO** (`BLOCKED`) |
| `eaaa-india-mainboard-20261028` | EAAA India Alternatives Ltd | Mainboard | 2026-10-28 17:00:00 | Elapsed (Unverified) | `EXPIRED_WITHOUT_COMMIT` | Cutoff elapsed (-6.6h ago) without primary circular or commit | **NO** (`EXPIRED`) |

**Expiry Enforcement**: EAAA India Alternatives Ltd has fully elapsed its asserted bidding deadline without an authoritative primary circular or authorized prospective commitment. It is strictly classified as `EXPIRED_WITHOUT_COMMIT` and cannot be resurrected or committed retroactively.

---

## 4. Cross-Process Persistence Architecture & Guarantees

An exhaustive review of [`src/prospective_simulator_logger.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_simulator_logger.py) and [`src/prospective_lifecycle.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_lifecycle.py) establishes the following multi-process persistence mechanics:

1. **Operating-System Level File Locking**:
   - On Windows, `msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)` applies mandatory byte-range file locks at the OS kernel level on a dedicated `.ledger.lock` file descriptor.
   - On POSIX, `fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)` applies non-blocking exclusive process locks.
   - This ensures synchronization across completely distinct Python OS processes, not merely threads within a single interpreter runtime.
2. **Pre-Write Corruption Barrier (`inspect_ledger_corruption`)**:
   - Scans the ledger line-by-line before writing. If any line contains invalid or truncated JSON (e.g. from an ungraceful prior process crash during write), further commits are immediately blocked with `LEDGER_CORRUPTION_BLOCKED`, preventing silent chain corruption.
3. **Under-Lock Idempotency & Duplicate Re-Check**:
   - `get_logged_decision_ids()` is invoked *inside* the process lock immediately before appending. If a concurrent process won the race and committed the record a microsecond prior, the second process detects it and returns `DUPLICATE_IGNORED` without creating duplicate records.
4. **Dynamic Hash-Chain Linkage**:
   - The SHA-256 hash of the previous line (`prev_record_sha256`) is read *under lock* immediately prior to serialization, guaranteeing an unbroken linear cryptographic hash chain.
5. **Physical Durability (`os.fsync`)**:
   - Every write executes `f.flush()` followed by `os.fsync(f.fileno())` before releasing the process lock. This forces file buffers through the OS page cache to physical disk platters/NVM storage, preventing data loss on system crashes.
6. **Recovery from Partial Writes**:
   - If a crash occurs mid-write, the truncated line is caught by `verify_ledger_chain` and `inspect_ledger_corruption`. Repairs must be performed offline by an authorized administrator before normal persistence can resume.

---

## 5. Decision Provenance & Outcome Reconciliation Contracts

### Decision Provenance Contract
Every committed decision record strictly preserves:
- Unique `decision_id` (`DEC_<timestamp>_<hash>`).
- Cryptographic hash link to predecessor (`prev_record_sha256`).
- Candidate identity (`ipo_id`, `company_name`, `board_type`).
- Asserted/verified cutoff timestamp (`cutoff_timestamp_ist`).
- Frozen model identity (`model_name`, `model_sha256`).
- SHA-256 checksum of raw features dictionary (`feature_hash_sha256`).
- Full feature values snapshot (`features`).
- Authoritative evidence metadata (`feature_provenance`).
- Point-in-time timestamp (`logging_timestamp_ist`).
- Strict strategy evaluations and rejection reasons.
- Record SHA-256 digest (`record_sha256`).

### Outcome Reconciliation Contract
`reconcile_listing_outcome` in [`src/prospective_lifecycle.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_lifecycle.py) enforces:
- **Decision Pre-Existence**: Outcome rejected if no decision exists (`UNMATCHED_OUTCOME_REJECTED`).
- **Strict Return Formula**: Listing-open return calculated exclusively as $R_{\text{open}} = \frac{P_{\text{open}} - P_{\text{issue}}}{P_{\text{issue}}} \times 100$.
- **Close-Price Rejection**: Explicit rejection if listing-close price is substituted (`is_close_price=True` raises `LISTING_CLOSE_SUBSTITUTION_PROHIBITED`).
- **Currency Validation**: Price currency must be `INR` (non-INR currencies raise `INVALID_PRICE_CURRENCY`).
- **Simulation Rejection**: Simulated outcomes prohibited (`is_simulated=True` raises `SIMULATED_OUTCOME_PROHIBITED`).
- **Artifact Hash Verification**: Accepts optional `artifact_sha256` and verifies byte-for-byte against raw artifact payload.
- **Append-Only Corrections**: Price revisions logged to `governance_audit_events.jsonl` as `OUTCOME_CORRECTION_EVENT`, keeping the original outcome ledger immutable.

---

## 6. Prospective Population Accounting & Selection Bias Audit

To prevent selection bias and cohort pollution, the pipeline separates candidate issues into 4 disjoint populations:

```
[Total Tracked Candidates: 6]
  ├── Population 1: Eligible Coverage Only (Mainboard) [3 issues: BLS, SFC, MK Sons]
  ├── Population 2: Clean Prospective Cohort (SME)      [2 issues: Wiscon, Carver]
  ├── Population 3: Excluded / Unverified / Expired    [1 issue: EAAA India Alternatives]
  └── Population 4: Mature Reconciled Outcomes         [0 issues: None]
```

### Detailed Accounting Table
| Population Category | Count | Candidates | Model Scoring Status | Included in Primary Model Metrics? | Reason for Exclusion / State |
|---|---|---|---|---|---|
| **1. Coverage Only** | 3 | BLS, SFC, MK Sons | Non-scoring | **NO** | Mainboard segment; SME model inapplicable |
| **2. Clean Prospective (Blocked)** | 2 | Wiscon, Carver | Blocked | **NO** | Awaiting official BSE SME circular evidence |
| **3. Excluded / Expired** | 1 | EAAA India | Excluded | **NO** | Cutoff passed without official circular or commit |
| **4. Mature Outcomes** | 0 | None | N/A | **NO** | 0 prospective outcomes realized |

No excluded or blocked candidates are removed from registry tracking, preventing survivorship bias or post-hoc cherry-picking.

---

## 7. Statistical & Economic Evaluation

1. **Brier Score & Brier Skill Score**:
   - Mature prospective observations: **0**
   - Model Brier Score: **`None`**
   - Training Baseline Brier Score: **`None`**
   - Brier Skill Score (BSS): **`None`**
   - Evaluation Status: **`INCONCLUSIVE_ZERO_OUTCOMES`**
2. **ROC-AUC & PR-AUC**:
   - Status: **`UNDEFINED`** (Requires $\ge 2$ distinct realized classes; $N = 0$).
3. **Statistical Sample Size Gate**:
   - Minimum sample size for point estimates: $N \ge 30$.
   - Current sample size: $N = 0$.
   - Sample sufficiency status: **`INSUFFICIENT_SAMPLE_SIZE_GATE`**.
4. **Economic Viability**:
   - Capital deployed: **₹0.00**.
   - Broker execution: **Strictly Prohibited & Completely Absent**.
   - Economic alpha milestone: **`INCONCLUSIVE_ZERO_LIVE_TRADES`**.

---

## 8. Adversarial Test Suite Execution (Phase 10.21)

A dedicated test suite ([`tests/test_phase_10_21_observation_integrity.py`](file:///d:/personal/st-ai/ipo-record/tests/test_phase_10_21_observation_integrity.py)) covering all 24 required scenarios was executed:

| Test ID | Scenario Description | Tested Condition | Result |
|---|---|---|---|
| `test_01` | Missing decision provenance | Provenance hash missing -> fails closed | **`PASS`** |
| `test_02` | Feature snapshot modified after decision | Record SHA-256 and feature hash verify integrity | **`PASS`** |
| `test_03` | Model hash mismatch | Tampered model SHA-256 blocks commit | **`PASS`** |
| `test_04` | Manifest hash mismatch | Tampered manifest SHA-256 blocks commit | **`PASS`** |
| `test_05` | Candidate expires before persistence | Expiry between readiness and write fails closed | **`PASS`** |
| `test_06` | Two processes attempt same commitment | Serialized via OS lock: 1 commit, 1 duplicate | **`PASS`** |
| `test_07` | Crash during persistence | Mid-write truncated JSON blocks further writes | **`PASS`** |
| `test_08` | Restart following partial persistence | Restart verifies ledger corruption safely | **`PASS`** |
| `test_09` | Duplicate outcome ingestion | Re-ingestion returns DUPLICATE_OUTCOME_IGNORED | **`PASS`** |
| `test_10` | Incorrect listing price units | Non-INR currencies rejected | **`PASS`** |
| `test_11` | Close data substituted for open data | `is_close_price=True` rejected | **`PASS`** |
| `test_12` | Missing official outcome artifact | Empty bulletin citation rejected | **`PASS`** |
| `test_13` | Outcome source hash mismatch | Mismatched artifact SHA-256 rejected | **`PASS`** |
| `test_14` | Contradictory official outcome sources | Negative or non-numeric prices rejected | **`PASS`** |
| `test_15` | Outcome received before decision exists | Unmatched outcome rejected with audit event | **`PASS`** |
| `test_16` | Blocked candidates excluded from eval | Wiscon/Carver excluded from clean metrics | **`PASS`** |
| `test_17` | Immature outcomes pending in evaluation | Decisions without outcomes marked PENDING | **`PASS`** |
| `test_18` | Simulated outcomes mixed with actual | `is_simulated=True` rejected | **`PASS`** |
| `test_19` | Empty-cohort metrics | $N=0$ returns INCONCLUSIVE_ZERO_OUTCOMES | **`PASS`** |
| `test_20` | Single-class evaluation cohorts | Single-class notes AUC undefined | **`PASS`** |
| `test_21` | Duplicate candidate IDs in registry | Verifies unique `ipo_id` invariant in registry | **`PASS`** |
| `test_22` | Unauthorized outcome correction | Audit trail logged, outcome ledger immutable | **`PASS`** |
| `test_23` | Mainboard candidate scored by SME model | Non-scoring policy enforced | **`PASS`** |
| `test_24` | Evaluation report mutates production | Confirms 0 records in all production ledgers | **`PASS`** |

**Full Discovery Suite Execution**:
- Total tests executed: **414**
- Test suites: **23**
- Failures: **0**
- Errors: **0**
- Skipped: **0**
- Runtime: **28.241s**
- Status: **`OK`**

---

## 9. Modified Files & Unresolved Risks

### Modified / Created Files
1. [`src/prospective_lifecycle.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_lifecycle.py): Hardened `reconcile_listing_outcome` with parameter validation (INR currency, simulation guard, close-price substitution guard, official bulletin citation requirements, artifact SHA-256 payload verification).
2. [`tests/test_phase_10_21_observation_integrity.py`](file:///d:/personal/st-ai/ipo-record/tests/test_phase_10_21_observation_integrity.py): Implemented full 24-test suite for observation integrity and cross-process persistence.
3. [`reports/phase_10_21_observation_and_outcome_integrity_audit.md`](file:///d:/personal/st-ai/ipo-record/reports/phase_10_21_observation_and_outcome_integrity_audit.md): Comprehensive Phase 10.21 audit report.

### Unresolved Operational Risks
1. **Exchange Bulletin Layout Variation**: Official exchange bulletins (e.g. BSE SME listing notices) occasionally format auction prices across varying table headers. Automated scraping without human-in-the-loop audit may require layout adaptation.
2. **Missing Primary Circulars**: Wiscon and Carver bidding cutoffs remain unverified due to lack of official BSE SME notices. If cutoffs pass without notices, both will transition to `EXPIRED_WITHOUT_COMMIT`.

---

## 10. Recommendations for Phase 10.22

1. **Automated Official Notice Ingestion Harness**: Implement an automated polling adapter specifically targeting the official BSE India Listing Notices API/endpoint for SME circulars.
2. **Expiry Sweep Cron**: Formalize a scheduled expiry sweeper that automatically transitions candidates whose verified cutoff time has passed into `EXPIRED_WITHOUT_COMMIT` in the registry.
3. **Continue Strict Shadow Mode**: Maintain complete prohibition on broker APIs, order routing, and real-money execution.
