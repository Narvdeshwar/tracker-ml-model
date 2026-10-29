# Phase 10.20 Deadline Watch, Candidate Expiry & First-Decision Release Gate Report

**Report Date**: 2026-10-28 23:20:00 IST  
**Repository**: `D:\personal\st-ai\ipo-record`  
**Phase**: 10.20 — Deadline Watch, Candidate Expiry & First-Decision Release Gate  
**Operating Mode**: STRICT SHADOW VALIDATION ONLY (Broker execution & real-money trading strictly prohibited)

---

## 1. Executive Summary & Audit Scorecard

Phase 10.20 established comprehensive deadline monitoring, cutoff expiry lifecycle management, and strict time-of-check/time-of-use (TOCTOU) release-gate enforcement for the prospective shadow IPO prediction system.

| Evaluation Area | Status | Verified Finding |
|---|---|---|
| **Frozen SME Model** | **`PASS`** | Exact byte match: SHA-256 `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` |
| **Baseline Manifest** | **`PASS`** | Exact byte match: SHA-256 `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` |
| **Asserted vs Verified Cutoff** | **`PASS`** | Registry cutoffs are strictly marked as unverified (`is_cutoff_verified=False`, `cutoff_verification_status="UNVERIFIED"`). Distinguishes asserted deadline from confirmed exchange schedule. |
| **Cutoff Expiry Lifecycle** | **`PASS`** | Candidates at or past cutoff immediately transition to `EXPIRED_WITHOUT_COMMIT`. Evaluated boundary conditions: $t_{\text{eval}} = t_{\text{cutoff}} - 1\text{s}$ (unexpired), $t_{\text{eval}} = t_{\text{cutoff}}$ (expired), $t_{\text{eval}} = t_{\text{cutoff}} + 1\text{s}$ (expired). |
| **TOCTOU Release Gate** | **`PASS`** | Persistence boundary re-checks cutoff expiry under thread lock immediately prior to ledger writes. A candidate ready at $t_1$ is rejected if clock reaches $t_2 \ge t_{\text{cutoff}}$ before commit. |
| **Authorization Boundaries** | **`PASS`** | Model hash mismatch, manifest hash mismatch, invalid auth token, unverified cutoff evidence, and missing feature provenance block commits fail-closed. |
| **Ledger Invariants** | **`PASS`** | Production ledgers remain strictly empty: 0 decision records, 0 outcome records, 0 evaluation records, 0 governance audit events. |
| **Unit & Integration Tests** | **`PASS`** | 390 / 390 passing tests across 22 test suites (100% pass rate, 0 failures, 0 errors, 0 skipped). |
| **Predictive & Economic Validity** | **`INCONCLUSIVE`** | 0 mature prospective outcomes observed. Live predictive power and economic alpha unestablished. Real-money deployment prohibited. |

---

## 2. Immutable Frozen Artifact Verification

Both frozen artifacts were verified directly via SHA-256 cryptographic hashing from the disk:
1. **Frozen SME Model v1 (`models/frozen/model_6b_sme_v1.joblib`)**:
   - Expected: `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76`
   - Actual: `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76`
   - Match: **VERIFIED EXACT MATCH**
2. **Baseline Manifest (`models/frozen/phase_9b_baseline_manifest.json`)**:
   - Expected: `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e`
   - Actual: `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e`
   - Match: **VERIFIED EXACT MATCH**

No retraining, refitting, parameter tuning, or artifact replacement was performed.

---

## 3. Read-Only Deadline Monitoring Implementation

In [`src/prospective_lifecycle.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_lifecycle.py), `generate_daily_monitoring_report()` was extended with an injectable clock (`evaluation_timestamp_ist`) and explicit cutoff verification labeling:

- **Asserted Cutoff**: Recorded in the registry as `asserted_cutoff_timestamp_ist`.
- **Verification Status**: If authoritative primary exchange circular evidence has not been acquired and verified, `is_cutoff_verified` is set to `False` and `cutoff_verification_status` to `"UNVERIFIED"`.
- **Clock Rollback Guard**: Any attempted evaluation where clock time has moved backwards relative to last processed evidence fails closed.

---

## 4. Cutoff Expiry Lifecycle & Boundary Conditions

Candidates are continuously monitored against their cutoff timestamps. If a candidate reaches or exceeds its cutoff time without official verified evidence enabling a valid commitment, it transitions to `EXPIRED_WITHOUT_COMMIT`:

- **At $t_{\text{cutoff}} - 1\text{s}$**: `is_late = False`. The candidate remains in its active evaluation state (`BLOCKED_CUTOFF`).
- **At $t_{\text{cutoff}}$**: `is_late = True`. The candidate immediately transitions to `EXPIRED_WITHOUT_COMMIT`.
- **At $t_{\text{cutoff}} + 1\text{s}$**: `is_late = True`. Late submission rejected with `COMMIT_BLOCKED_UNREADY_CANDIDATE: Candidate ... cutoff elapsed`.
- **Clock Rollback Guard**: A publication timestamp after the evaluation timestamp ($t_{\text{pub}} > t_{\text{eval}}$) or attempted backdating fails closed with `REJECTED_FUTURE_PUBLICATION`.

---

## 5. TOCTOU First-Decision Release Gate

A critical vulnerability in distributed prospective systems is the Time-of-Check to Time-of-Use (TOCTOU) gap, where a pre-commit check at $t_1 < t_{\text{cutoff}}$ marks a candidate ready, but delays (serialization, I/O, lock contention) cause the write to occur at $t_2 \ge t_{\text{cutoff}}$.

In [`src/prospective_lifecycle.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_lifecycle.py), `commit_prospective_decision()` was hardened with an atomic pre-write guard:
```python
with self._evidence_lock:
    # Atomic re-verification under lock right before persistence
    now_ts = get_ist_now()
    cutoff_ts = candidate.bidding_cutoff_time_ist
    if cutoff_ts is not None:
        if now_ts >= cutoff_ts:
            raise ValueError(
                f"COMMIT_BLOCKED_UNREADY_CANDIDATE: Candidate '{candidate_id}' cutoff elapsed at persistence boundary: "
                f"now={now_ts.isoformat()} >= cutoff={cutoff_ts.isoformat()}"
            )
```
This guarantees that no prospective prediction can ever be committed post-cutoff.

---

## 6. Tracked Candidates Status & Current Registry

| Candidate ID | Company Name | Segment | Asserted Cutoff (IST) | Evidence Status | Current Lifecycle State | Scoring Permitted? |
|---|---|---|---|---|---|---|
| `wiscon-industries-sme-20261029` | Wiscon Industries Ltd | BSE SME | 2026-10-29 16:00:00 | Unverified Asserted | `BLOCKED_CUTOFF` | **NO** (Blocked until primary exchange evidence verified) |
| `carver-roboweld-sme-20261030` | Carver Roboweld Ltd | BSE SME | 2026-10-30 16:00:00 | Unverified Asserted | `BLOCKED_CUTOFF` | **NO** (Blocked until primary exchange evidence verified) |
| `bls-e-services-202401` | BLS E-Services Ltd | Mainboard | 2024-02-01 17:00:00 | N/A | `BLOCKED_GOVERNANCE` | **NO** (Coverage tracking only; SME model incompatible) |
| `sfc-environmental-202402` | SFC Environmental Tech | Mainboard | 2024-02-15 17:00:00 | N/A | `BLOCKED_GOVERNANCE` | **NO** (Coverage tracking only; SME model incompatible) |
| `mk-sons-engineering-202403` | MK Sons Engineering | Mainboard | 2024-03-01 17:00:00 | N/A | `BLOCKED_GOVERNANCE` | **NO** (Coverage tracking only; SME model incompatible) |
| `eaaa-technologies-202403` | EAAA Technologies | Mainboard | 2024-03-15 17:00:00 | N/A | `BLOCKED_GOVERNANCE` | **NO** (Coverage tracking only; SME model incompatible) |

---

## 7. Adversarial Test Suite Results

A dedicated adversarial test suite ([`tests/test_phase_10_20_release_gate.py`](file:///d:/personal/st-ai/ipo-record/tests/test_phase_10_20_release_gate.py)) containing 24 test scenarios was implemented and verified:

1. `test_01_baseline_frozen_hashes`: Verifies frozen model and manifest hashes directly on disk.
2. `test_02_production_ledgers_empty`: Verifies all 4 production ledgers contain exactly 0 lines.
3. `test_03_wiscon_initial_status_unverified`: Confirms Wiscon starts in `BLOCKED_CUTOFF` with unverified cutoff.
4. `test_04_carver_initial_status_unverified`: Confirms Carver starts in `BLOCKED_CUTOFF` with unverified cutoff.
5. `test_05_mainboard_candidates_remain_governance_blocked`: Confirms mainboard candidates cannot be scored.
6. `test_06_monitoring_report_distinguishes_asserted_vs_verified`: Validates reporting of `asserted_cutoff_timestamp_ist`.
7. `test_07_monitoring_report_injectable_clock`: Verifies injectable clock in monitoring report generation.
8. `test_08_evidence_acceptance_requires_official_exchange`: Rejects non-official sources (e.g. `chittorgarh_ipo_tracker`).
9. `test_09_evidence_acceptance_rejects_wrong_candidate_circular`: Rejects BSE notice for different company.
10. `test_10_evidence_acceptance_rejects_upi_mandate_time`: Rejects secondary UPI deadline evidence.
11. `test_11_evidence_acceptance_rejects_future_publication_time`: Rejects publication timestamp after evaluation time.
12. `test_12_evidence_acceptance_rejects_sha256_payload_mismatch`: Rejects tampered raw payload.
13. `test_13_cutoff_expiry_at_t_minus_1s`: Confirms candidate unexpired at $t_{\text{cutoff}} - 1\text{s}$.
14. `test_14_cutoff_expiry_at_t_equals_cutoff`: Confirms candidate expired at $t_{\text{cutoff}}$.
15. `test_15_cutoff_expiry_at_t_plus_1s`: Confirms candidate expired at $t_{\text{cutoff}} + 1\text{s}$.
16. `test_16_cutoff_expiry_persists_expired_without_commit`: Confirms persistence of expiry state.
17. `test_17_cutoff_expiry_idempotent`: Multiple expiry evaluations remain idempotent.
18. `test_18_release_gate_rejects_unverified_cutoff`: Commits blocked if cutoff evidence is unverified.
19. `test_19_release_gate_rejects_invalid_auth_token`: Commits blocked with invalid administrative token.
20. `test_20_release_gate_rejects_tampered_model_hash`: Commits blocked if model hash tampered.
21. `test_21_release_gate_rejects_missing_feature_provenance`: Commits blocked if feature provenance incomplete.
22. `test_22_release_gate_prevents_toctou_persistence_boundary`: Confirms TOCTOU guard blocks late commit.
23. `test_23_release_gate_atomic_concurrency_serialization`: Concurrent commit requests safely serialized.
24. `test_24_release_gate_duplicate_commit_protection`: Rejects duplicate prospective commitment for candidate.

**Full Test Suite Execution**:
- Total tests executed: **390**
- Test suites: **22**
- Failures: **0**
- Errors: **0**
- Skipped: **0**
- Execution time: **41.418s**
- Status: **`OK`**

---

## 8. Governance, Statistical & Economic Validity Statement

1. **Strict Shadow Operation**: Live broker APIs, execution hooks, order routing, and capital deployment are completely absent and prohibited.
2. **Predictive Validity Inconclusive**: With 0 mature prospective outcomes, the out-of-sample directional accuracy and ranking efficacy of the frozen model are statistically unestablished.
3. **Economic Viability Unestablished**: No claims of real-money edge, sharpe ratio, or profitability are permitted. The system remains strictly in pre-observation shadow validation.
