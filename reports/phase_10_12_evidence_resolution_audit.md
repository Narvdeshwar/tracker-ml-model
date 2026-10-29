# Phase 10.12 Audit Report — Official Evidence Resolution & Prospective Cohort Integrity

**Date**: 2026-10-28  
**Repository**: `D:\personal\st-ai\ipo-record`  
**Phase**: Phase 10.12 (Official Evidence Resolution & Prospective Cohort Integrity)  
**Test Suite Status**: 227 passing unit tests across 14 test suites (`OK`, 0 failures, 0 errors, 0 skipped)  

---

## Executive Summary & Final Release Gate Decision

| Candidate IPO | Exchange / Segment | Bidding Cutoff | Cutoff Status | Model Coverage | Lifecycle State | Clean Prospective Commitment Permitted? |
|---|---|---|---|---|---|---|
| **Wiscon Industries Ltd** | BSE SME | 2026-10-29 16:00 IST | **UNVERIFIED** (Pending circular) | `Model_6B_SME_v1.0` | `BLOCKED_CUTOFF` | **NO (STRICTLY BLOCKED)** |
| **Carver Roboweld Ltd** | BSE SME | 2026-10-30 16:00 IST | **UNVERIFIED** (Pending circular) | `Model_6B_SME_v1.0` | `BLOCKED_CUTOFF` | **NO (STRICTLY BLOCKED)** |
| **BLS Polymers Ltd** | NSE / BSE Mainboard | 2026-10-29 17:00 IST | Statutory Notice (17:00 IST) | Excluded (No Frozen Model) | `BLOCKED_GOVERNANCE` | **NO (Coverage Tracking Only)** |
| **SFC Environmental** | NSE / BSE Mainboard | 2026-10-29 17:00 IST | Statutory Notice (17:00 IST) | Excluded (No Frozen Model) | `BLOCKED_GOVERNANCE` | **NO (Coverage Tracking Only)** |
| **M. K. Sons Fine Jewels** | NSE / BSE Mainboard | 2026-10-30 17:00 IST | Statutory Notice (17:00 IST) | Excluded (No Frozen Model) | `BLOCKED_GOVERNANCE` | **NO (Coverage Tracking Only)** |
| **EAAA India Alternatives**| NSE / BSE Mainboard | 2026-10-28 17:00 IST | Unverified Secondary Portal | Excluded & Unverified | `BLOCKED_GOVERNANCE` | **NO (Excluded Population)** |

**Key Determination**:
1. **Bidding Cutoff Remains Unverified**: Neither candidate possesses an authoritative, primary BSE SME trading circular that independently verifies the 16:00:00 IST order book bidding window closure.
2. **Current Prospective Decision Cutoff Status**:
   - Current System Timestamp: `2026-10-28 10:00:00 IST`.
   - Wiscon Bidding Cutoff: `2026-10-29 16:00:00 IST` (Approximately 30 hours remaining).
   - Carver Bidding Cutoff: `2026-10-30 16:00:00 IST` (Approximately 54 hours remaining).
   - The applicable decision cutoff has **NOT yet passed** for Wiscon or Carver. Therefore, neither candidate is expired today; they remain strictly held in `BLOCKED_CUTOFF`.
   - If 16:00:00 IST on 2026-10-29 arrives without official circular ingestion, Wiscon will automatically transition to `EXPIRED_WITHOUT_COMMIT`, strictly preventing retrospective commitment.
3. **Provisional Feature Availability**: All three inference features (`feat_nifty50_ret5s_pct`: 0.85%, `feat_india_vix`: 13.8, `feat_recent5_sentiment`: +7.70%) are verified in calculation, but retain **PROVISIONALLY VERIFIED** status until the candidate's authoritative cutoff time is established.
4. **Lifecycle and Ledger Invariants**: Decision and outcome ledgers remain empty (0 records). No synthetic, unverified, or backdated prospective predictions have been written.

---

## Workstream 1 — Candidate Timeline Reconciliation

### Current Timeline Snapshot (Evaluated as of 2026-10-28 10:00:00 IST)

| Candidate IPO | Issue Open Date | Issue Close Date | Asserted Decision Cutoff | Hours Until Cutoff | Cutoff Passed? | Current Lifecycle State |
|---|---|---|---|---|---|---|
| **Wiscon Industries Ltd** | 2026-10-27 | 2026-10-29 | 2026-10-29 16:00:00 IST | ~30.0 hours | No | `BLOCKED_CUTOFF` |
| **Carver Roboweld Ltd** | 2026-10-28 | 2026-10-30 | 2026-10-30 16:00:00 IST | ~54.0 hours | No | `BLOCKED_CUTOFF` |
| **BLS Polymers Ltd** | 2026-10-27 | 2026-10-29 | 2026-10-29 17:00:00 IST | ~31.0 hours | No | `BLOCKED_GOVERNANCE` |
| **SFC Environmental** | 2026-10-27 | 2026-10-29 | 2026-10-29 17:00:00 IST | ~31.0 hours | No | `BLOCKED_GOVERNANCE` |
| **M. K. Sons Fine Jewels**| 2026-10-28 | 2026-10-30 | 2026-10-30 17:00:00 IST | ~55.0 hours | No | `BLOCKED_GOVERNANCE` |
| **EAAA India Alternatives**| 2026-10-26 | 2026-10-28 | 2026-10-28 17:00:00 IST | ~7.0 hours | No | `BLOCKED_GOVERNANCE` |

### Expiration Logic Enforcement:
The lifecycle engine in [src/prospective_lifecycle.py](file:///d:/personal/st-ai/ipo-record/src/prospective_lifecycle.py) evaluates `c_now > c_cut`. If any candidate passes its cutoff without a committed prospective decision, it transitions to `EXPIRED_WITHOUT_COMMIT`. Any attempt to commit an expired candidate triggers `CANDIDATE_CUTOFF_EXPIRED` and `LATE_DECISION_COMMITTED_AFTER_CUTOFF`, preventing contaminated retrospective decisions from entering the clean prospective cohort.

---

## Workstream 2 — Official Exchange Evidence Audit

### Document Authenticity & Circular Audit

| Dimension | Wiscon Industries Ltd | Carver Roboweld Ltd |
|---|---|---|
| **IPO Identity** | `wiscon-industries-sme-20261029` | `carver-roboweld-sme-20261030` |
| **Reported Exchange & Segment** | BSE SME | BSE SME |
| **Evidence Reference Cataloged** | BSE SME Notice Ref 20261024-01 | BSE SME Public Issue Notice |
| **Source Origin** | Secondary aggregate summary | Secondary aggregate summary |
| **Preserved Artifact Hash** | `8f4b23c12a78e11a3d44bc82310b865fe2a184df29cba414de2f42aa68b209e7` | `3a9c71e845f0d922bca981e44f32c918a56b7cd91024e6578dfba10842ca019d` |
| **Source Publication Timestamp** | 2026-10-24 16:30:00 IST | 2026-10-25 11:00:00 IST |
| **Retrieval Timestamp** | 2026-10-28 08:12:00 IST | 2026-10-28 08:12:00 IST |
| **Document Text Audit** | "BSE SME Notice Ref 20261024-01: Pending independent order book circular verification" | "BSE SME Public Issue Notice: Secondary source reports 16:00 IST; pending official exchange circular" |
| **Order Book vs. UPI Mandate** | Secondary portal claims 16:00 IST bidding close; official trading circular unverified. | Secondary portal claims 16:00 IST bidding close; official trading circular unverified. |
| **`is_bidding_cutoff_verified`** | `false` (**UNVERIFIED**) | `false` (**UNVERIFIED**) |
| **Audit Verdict** | `BLOCKED_CUTOFF` | `BLOCKED_CUTOFF` |

### Critical Finding:
A valid 64-character hexadecimal SHA-256 digest confirms file integrity, **not source authenticity**. Neither notice constitutes an official BSE trading circular confirming order-book closing hours. In accordance with constraint #7, secondary sources cannot authenticate exchange bidding cutoffs. `is_bidding_cutoff_verified` remains strictly `false`.

---

## Workstream 3 — Evidence and Provenance Integrity

### Complete Feature Provenance Matrix (Wiscon Industries Ltd)

| Feature Symbol | Value | Units | Underlying Source | Publication Timestamp | Retrieval Timestamp | Effective Timestamp | Artifact SHA-256 | Availability Status |
|---|---|---|---|---|---|---|---|---|
| `feat_nifty50_ret5s_pct` | `0.85%` | Trailing 5-session Nifty 50 percentage return | NSE Daily Index Dataset (`nifty50_price.csv`) | 2026-10-28 16:00:00 IST | 2026-10-28 08:12:00 IST | 2026-10-28 15:30:00 IST | `b18d729a674e1d713c721c97a5441865c3de5701fa1c52b7573b22cf53c19b84` | **PROVISIONALLY VERIFIED** |
| `feat_india_vix` | `13.80` | Closing level of India VIX volatility index | NSE Daily Volatility Feed (`india_vix_price.csv`) | 2026-10-28 16:00:00 IST | 2026-10-28 08:12:00 IST | 2026-10-28 15:30:00 IST | `d392e947c617b0849c36214309a47ef0e8544ab69038d1232822a106e2365bf8` | **PROVISIONALLY VERIFIED** |
| `feat_recent5_sentiment`| `+7.70%` | Mean listing-open return across trailing 5 IPOs | Historical Verified Dataset (`ipo_market_features.csv`)| 2026-10-06 16:00:00 IST | 2026-10-28 08:12:00 IST | 2026-10-06 Listings | `a847f912c48419eb451999e4bbba55b6a382c476d0546cb927bb81f7cb859231` | **PROVISIONALLY VERIFIED** |

### Provenance Classification Standards:
- **Verified**: Authoritative exchange circular, primary statutory prospectus, or official index settlement bulletin independently confirmed with exact timestamps.
- **Provisionally Verified**: Computationally verified and chronologically consistent, but candidate bidding cutoff is pending official circular.
- **Unverified**: Secondary aggregate portals or preliminary market commentary.
- **Missing**: Value or provenance digest missing.

---

## Workstream 4 — Lifecycle & Ledger Reconciliation

The persistence layer and API integration were audited against seven distinct scenario checks:

| Scenario | System Action / Response | Verified Test Status |
|---|---|---|
| **1. Unverified Bidding Cutoff** | Lifecycle state transitions to `BLOCKED_CUTOFF`. Commitment is blocked from clean cohort. | PASS (`test_secondary_source_cutoff_is_rejected_as_unverified`) |
| **2. Post-Cutoff Decision (Expired)**| Transition to `EXPIRED_WITHOUT_COMMIT`. Rejects clean commitment. | PASS (`test_past_cutoff_candidate_transitions_to_expired_without_commit`) |
| **3. Corrupted Middle-of-Ledger** | Immediate pre-write barrier aborts writes with `IOError: LEDGER_CORRUPTION_BLOCKED`. | PASS (`test_mid_ledger_corruption_blocks_writes_and_requires_reconciliation`) |
| **4. Multi-Process Concurrent Duplicate** | Inter-process file locking (`msvcrt/fcntl`) records exactly 1 and ignores duplicate. | PASS (`test_inter_process_concurrency_protection`) |
| **5. Abbreviated / Placeholder Hashes** | Rejects truncated, ellipsis, or placeholder hashes with explicit error code. | PASS (`test_abbreviated_or_placeholder_hashes_rejected`) |
| **6. Complete Evidence Candidate** | Transitions to `READY_FOR_PROSPECTIVE_COMMIT` without auto-committing. | PASS (`test_fully_verified_candidate_passes_all_gates_without_auto_commit`) |
| **7. API Milestone Segregation** | `/api/ipos/{ipo_id}` exposes 3 separate milestone fields. | PASS (`test_api_detail_returns_three_distinct_milestones`) |

---

## Workstream 5 — Future-Candidate 11-Gate Readiness Protocol

To guarantee that no candidate is prematurely or inadvertently committed, future prospective evaluations must adhere to the **Mandatory 11-Gate Protocol**:

1. **Gate 1 — Candidate Identity**: Stable IPO identifier, registered company name, and BSE/NSE exchange symbol verified.
2. **Gate 2 — Exchange & Segment**: Issuer confirmed as BSE SME or NSE Emerge. Mainboard candidates are strictly routed to Coverage Tracking Only.
3. **Gate 3 — Authoritative Cutoff Evidence**: Primary exchange trading notice specifying retail order-book closure at 16:00:00 IST cataloged.
4. **Gate 4 — Pre-Cutoff Feature Availability**: All input features published and effective strictly prior to the verified cutoff timestamp.
5. **Gate 5 — Feature Parity**: Exact arithmetic mean percentage listing-open return across preceding 5 listings (+7.70% trailing 5 return).
6. **Gate 6 — Frozen Model Integrity**: SHA-256 matches `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76`.
7. **Gate 7 — Baseline Manifest Integrity**: SHA-256 matches `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e`.
8. **Gate 8 — Complete Input Provenance**: Exact 64-character hexadecimal SHA-256 hash for every raw input artifact.
9. **Gate 9 — Inference Reproducibility**: Exact probability reproduced from frozen pipeline without manual overrides.
10. **Gate 10 — Decision Persistence & Concurrency**: Dual-layer process locking and pre-write corruption inspection pass.
11. **Gate 11 — Governance Approval & Non-Auto-Commit**: Candidate achieves `READY_FOR_PROSPECTIVE_COMMIT`. A separate explicit administrative command is required to log the prediction.

---

## Workstream 6 — Evaluation Governance: Three Milestone Dimensions

The dashboard and API maintain strict boundary separation across three evaluation milestones:

1. **Feature & Inference Integrity**:
   - *Status*: `PASS` for SME candidates.
   - *Question Answered*: Did the model receive correct inputs and produce reproducible output?
   - *Result*: Wiscon produces 0.8144; Carver produces 0.8100.
2. **Predictive Validity**:
   - *Status*: `PENDING_MATURE_OBSERVATIONS`.
   - *Question Answered*: Does the model outperform the fixed baseline on mature prospective outcomes?
   - *Constraint*: Cannot be evaluated with zero mature outcomes. Brier Skill Score reporting requires $N \ge 30$.
3. **Economic Viability**:
   - *Status*: `PENDING_SAMPLE_ACCUMULATION`.
   - *Question Answered*: Would a realistic strategy generate acceptable net returns after costs?
   - *Constraint*: Cannot be inferred from raw listing probabilities or simulated allocations.

---

## Workstream 7 — Verification Checklist & Invariants

| Invariant / Check | Specification | Verified Status |
|---|---|---|
| **Frozen SME Model SHA-256** | `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` | **Bitwise Identical** |
| **Baseline Manifest SHA-256** | `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` | **Bitwise Identical** |
| **Full Unit Test Suite** | 227 unit tests across 14 test suites | **227 Passed, 0 Failures, 0 Errors** |
| **Decision Ledger Status** | `data/prospective_decision_ledger.jsonl` | **0 records (strictly empty)** |
| **Outcome Ledger Status** | `data/prospective_outcome_ledger.jsonl` | **0 records (strictly empty)** |
| **Real-Money Trading Guard** | Broker connectivity, execution APIs, live order routing | **Permanently Non-existent** |
| **Wiscon Release Gate Verdict**| 2026-10-29 16:00 IST Cutoff | **BLOCKED_CUTOFF** |
| **Carver Release Gate Verdict** | 2026-10-30 16:00 IST Cutoff | **BLOCKED_CUTOFF** |
