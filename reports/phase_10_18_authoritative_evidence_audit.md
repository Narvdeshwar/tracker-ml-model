# Phase 10.18 Authoritative Evidence Verification & Prospective Readiness Audit Report

**Report Date**: 2026-10-28 22:18:00 IST  
**Repository**: `D:\personal\st-ai\ipo-record`  
**Phase**: 10.18 — Authoritative Evidence Verification & Prospective Readiness  
**Operating Mode**: STRICT SHADOW VALIDATION (Broker execution & real-money trading strictly prohibited)

---

## 1. Executive Summary & Verification Scorecard

Phase 10.18 conducted an exhaustive audit and hardening of the evidence-verification pipeline, evaluating the system's defenses against secondary announcements falsely labelled as primary evidence, irrelevant candidate circulars, UPI mandate notices masquerading as order-book cutoffs, contradictory metadata, post-decision publication anomalies, and post-cutoff evidence injection attempts.

| Evaluation Domain | Baseline Reported | Phase 10.18 Verified Status | Audit Verdict |
|---|---|---|---|
| **Frozen SME Model** | SHA-256 `dbf2eec7...` | Byte-for-byte exact match (`dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76`) | **`PASS`** |
| **Baseline Manifest** | SHA-256 `b19c913e...` | Byte-for-byte exact match (`b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e`) | **`PASS`** |
| **Total Test Suite** | 332 tests (19 suites) | **346 tests passing across 20 test suites** (14 new adversarial & boundary tests in Phase 10.18) | **`PASS`** |
| **Adversarial Evidence Defenses** | Basic portal string check | Deep inspection: portal validation, target relevance check, UPI-only notice detection, conflicting cutoff alerts | **`PASS`** |
| **Post-Cutoff Evidence Ingestion** | Allowed candidate update | **Strictly blocked**: Attempt to ingest evidence for expired candidate fails closed with `CANDIDATE_EXPIRED` | **`PASS`** |
| **Cutoff Boundary Trichotomy** | Defined boundary | Exhaustively verified: `t - 1s` is open; `t == cutoff` is expired; `t + 1s` is expired | **`PASS`** |
| **Prospective Decision Ledger** | 0 records | **0 records (strictly preserved empty)** | **`PASS`** |
| **Prospective Outcome Ledger** | 0 records | **0 records (strictly preserved empty)** | **`PASS`** |
| **Evaluation Records Ledger** | 0 records | **0 records (strictly preserved empty)** | **`PASS`** |
| **Governance Events Ledger** | 0 production events | **0 production events (clean audit log)** | **`PASS`** |
| **Wiscon Industries Status** | `BLOCKED_CUTOFF` | **`BLOCKED_CUTOFF`** (Asserted cutoff: `2026-10-29 16:00:00 IST`, ~17.7h remaining) | **`PASS`** |
| **Carver Roboweld Status** | `BLOCKED_CUTOFF` | **`BLOCKED_CUTOFF`** (Asserted cutoff: `2026-10-30 16:00:00 IST`, ~41.7h remaining) | **`PASS`** |
| **Mainboard Candidates** | Coverage only | **Coverage only (`BLOCKED_GOVERNANCE` / non-scoring)** | **`PASS`** |
| **Predictive / Economic Validity** | Inconclusive | **Inconclusive (Zero mature prospective observations)** | **`PASS`** |

---

## 2. Tracked Candidate Lifecycle & Readiness Table

As of evaluation timestamp **`2026-10-28 22:15:00 IST`**, the state of all tracked candidates in [tracked_candidate_registry.json](file:///d:/personal/st-ai/ipo-record/data/registered/tracked_candidate_registry.json) is:

| Candidate ID | Company Name | Segment | Asserted Cutoff (IST) | Verified Cutoff Status | Current Lifecycle State | Model Scoring Eligibility | Outstanding Blocker / Next Action |
|---|---|---|---|---|---|---|---|
| `wiscon-industries-sme-20261029` | Wiscon Industries Ltd | BSE SME | 2026-10-29 16:00:00 IST | **UNVERIFIED** | **`BLOCKED_CUTOFF`** | Eligible (`Model_6B_SME_v1.0`) | Primary exchange trading circular verifying retail order book close not yet retrieved from official BSE SME website. |
| `carver-roboweld-sme-20261030` | Carver Roboweld Ltd | BSE SME | 2026-10-30 16:00:00 IST | **UNVERIFIED** | **`BLOCKED_CUTOFF`** | Eligible (`Model_6B_SME_v1.0`) | Primary exchange trading circular verifying order book close not yet retrieved from official BSE SME website. |
| `bls-polymers-mainboard-20261029` | BLS Polymers Ltd | Mainboard | 2026-10-29 17:00:00 IST | Secondary only | **`BLOCKED_GOVERNANCE`** | **Coverage Only (Non-scoring)** | Mainboard candidate; strictly non-scoring under frozen SME model governance. |
| `sfc-environmental-mainboard-20261029` | SFC Environmental Tech Ltd | Mainboard | 2026-10-29 17:00:00 IST | Secondary only | **`BLOCKED_GOVERNANCE`** | **Coverage Only (Non-scoring)** | Mainboard candidate; strictly non-scoring under frozen SME model governance. |
| `mk-sons-mainboard-20261030` | M. K. Sons Fine Jewels Ltd | Mainboard | 2026-10-30 17:00:00 IST | Secondary only | **`BLOCKED_GOVERNANCE`** | **Coverage Only (Non-scoring)** | Mainboard candidate; strictly non-scoring under frozen SME model governance. |
| `eaaa-india-mainboard-20261028` | EAAA India Alternatives Ltd | Mainboard | 2026-10-28 17:00:00 IST | Unverified | **`BLOCKED_GOVERNANCE`** | **Coverage Only (Non-scoring)** | Excluded cohort candidate; tracked for registry coverage only. |

---

## 3. Adversarial Evidence Verification & Defense Mechanisms

### 3.1 Defenses Implemented in `process_evidence_update()`
In [src/prospective_lifecycle.py](file:///d:/personal/st-ai/ipo-record/src/prospective_lifecycle.py):
1. **Source Origin Validation**:
   - Rejects documents from non-official sources falsely claiming `PRIMARY_EXCHANGE_CIRCULAR`. Only portals containing `"BSE"` or `"NSE"` qualify. Secondary aggregators (e.g. `IPOCENTRAL_AGGREGATOR`, `CHITTORGARH_SECONDARY`) are classified as secondary and retain `BLOCKED_CUTOFF`.
2. **Target Candidate Relevance Enforcement**:
   - Inspects the decoded text of the document. If the document describes a different candidate (e.g. `ABC Steels Ltd` instead of `Wiscon Industries Ltd`), the document is rejected with `IRRELEVANT_EVIDENCE` and an audit event (`EVIDENCE_REJECTED_IRRELEVANT_CANDIDATE`) is recorded.
3. **UPI Mandate vs Order-Book Closure Discrimination**:
   - Documents mentioning UPI mandate acceptance deadlines, payment processing cutoffs, or sponsor bank clearance without stating retail order book closure are classified as `is_upi_only = True` and retain `BLOCKED_CUTOFF`.
4. **Conflicting Cutoff Detection**:
   - If a new document asserts a cutoff time that contradicts the registry cutoff, an alert event (`CONFLICTING_CUTOFF_TIMES_DETECTED`) is logged to governance audit events to prevent silent cutoff tampering.
5. **Post-Expiry Ingestion Prohibition**:
   - If a candidate has already crossed its cutoff (`EXPIRED_WITHOUT_COMMIT`), late evidence ingestion is strictly prohibited with `CANDIDATE_EXPIRED`. Late documents cannot resurrect expired candidates or permit retrospective commitment.

---

## 4. Cutoff Lifecycle & Trichotomy Boundary Verification

The cutoff equality rule was tested at microscopic granularity:
1. **$t - 1\text{s}$ (`2026-10-29 15:59:59 IST`)**: Candidate is pre-cutoff; remains in `BLOCKED_CUTOFF` awaiting verified primary evidence.
2. **$t = \text{cutoff}$ (`2026-10-29 16:00:00 IST`)**: Exact boundary equality. Retail order books are closed at the strike of `16:00:00 IST`. The candidate deterministically transitions to `EXPIRED_WITHOUT_COMMIT`.
3. **$t + 1\text{s}$ (`2026-10-29 16:00:01 IST`)**: Past cutoff. Candidate is strictly `EXPIRED_WITHOUT_COMMIT`.
4. **Post-Cutoff Restart**: Re-instantiating `ProspectiveLifecycleManager` after cutoff preserves `EXPIRED_WITHOUT_COMMIT`.
5. **Post-Cutoff Commitment Attempt**: Under `strict_clean_only=True`, any commitment attempt for an expired candidate fails closed with `COMMIT_BLOCKED_UNREADY_CANDIDATE`.

---

## 5. Governance Invariants and Ledger Verification

1. **Frozen SME Model Digest**:
   - Path: `models/frozen/model_6b_sme_v1.joblib`
   - Hash: `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76`
   - Status: **`PASS` (Verified byte-for-byte)**

2. **Baseline Manifest Digest**:
   - Path: `models/frozen/phase_9b_baseline_manifest.json`
   - Hash: `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e`
   - Status: **`PASS` (Verified byte-for-byte)**

3. **Production Ledger Immutability**:
   - `data/processed/prospective_decision_ledger.jsonl`: **0 records**
   - `data/processed/prospective_outcome_ledger.jsonl`: **0 records**
   - `data/processed/prospective_evaluation_records.jsonl`: **0 records**
   - `data/processed/governance_audit_events.jsonl`: **0 records**
   - **No mock, backdated, or unverified decisions were recorded.**

---

## 6. Comprehensive Test Execution Results

The full deterministic test suite was executed in the Windows virtual environment (`.\.venv\Scripts\python.exe -m unittest discover tests`):

```text
Ran 346 tests in 42.331s

OK
```

### Passing Test Suites Summary (20 suites, 346 tests):
1. `tests/test_phase_10_18_evidence_verification.py`: **14 tests (NEW)** — Adversarial evidence defense, candidate relevance verification, UPI-only notice handling, trichotomy boundary conditions, restart persistence, and graceful error handling.
2. `tests/test_phase_10_17_candidate_monitoring.py`: 17 tests — Daily monitoring report generation, cutoff boundary equality, idempotent evidence ingestion, authorization token boundaries.
3. `tests/test_phase_10_16_persistence_assurance.py`: 19 tests — Partial record handling, lock recovery, concurrent write serialization, Mainboard governance blocks.
4. `tests/test_phase_10_15_candidate_resolution.py`: 22 tests — Pre-cutoff feature parity, audit readiness.
5. `tests/test_phase_10_14_independent_gate.py`: 21 tests — Independent gate checks, baseline verification.
6. `tests/test_phase_10_13_point_in_time.py`: 24 tests — Temporal provenance, publication ordering.
7. `tests/test_phase_10_12_evidence_resolution.py`: 8 tests — Primary vs secondary exchange evidence.
8. `tests/test_phase_10_11_readiness.py`: 8 tests — Gate evaluations.
9. `tests/test_phase_10_10_release_gate.py`: 12 tests — First-decision release gate safeguards.
10. `tests/test_phase_10_8_integrity_hardening.py`: 11 tests — Feature parity across historical IPOs.
11. `tests/test_phase_10_7_lifecycle.py`: 18 tests — Ledger hash chaining and observation records.
12. `tests/test_phase_10_6_evidence_validation.py`: 12 tests — Official circular provenance rules.
13. `tests/test_phase_10_5_surveillance.py`: 12 tests — Operational health and drift surveillance.
14. `tests/test_phase_10_4_prospective_validation.py`: 14 tests — Population accounting and prospective simulation.
15. `tests/test_phase_10_3_explorer_audit.py`: 15 tests — Explorer API and dashboard integrity.
16. `tests/test_phase_10_2_integration.py`: 14 tests — Dashboard integration endpoints.
17. `tests/test_phase_9b_setup.py`: 16 tests — Manifest and frozen artifact validation.
18. `tests/test_phase_9a1_protocol_review.py`: 12 tests — Protocol review verification.
19. `tests/test_market_daily.py`: 22 tests — Market daily indices and returns calculation.
20. `tests/test_ipo_market_features.py`: 55 tests — Historical dataset parity and feature extraction.

---

## 7. Audit Verdict and Next Governance Milestones

### Audit Verdict
**Phase 10.18 is APPROVED and COMPLETE.**  
The evidence ingestion and verification layer successfully rejects synthetic, irrelevant, conflicting, and post-cutoff evidence while maintaining byte-for-byte model immutability and empty production ledgers.

### Status and Upcoming Decision Windows:
1. **Wiscon Industries Ltd** (`wiscon-industries-sme-20261029`):
   - Asserted Cutoff: **`2026-10-29 16:00:00 IST`** (~17.7 hours remaining).
   - If an official BSE SME trading circular explicitly stating retail book closure at 16:00:00 IST is discovered prior to cutoff, it can be ingested and authorized.
   - If no official BSE SME document is obtained before `16:00:00 IST`, candidate transitions irreversibly to **`EXPIRED_WITHOUT_COMMIT`**.
2. **Carver Roboweld Ltd** (`carver-roboweld-sme-20261030`):
   - Asserted Cutoff: **`2026-10-30 16:00:00 IST`** (~41.7 hours remaining).
   - Awaiting official BSE SME trading circular verification.
3. **Zero Mature Observations**:
   - Model predictive validity and economic viability remain strictly **`INCONCLUSIVE`** until clean prospective decisions mature into verified listing outcomes.
