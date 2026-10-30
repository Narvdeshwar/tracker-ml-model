# Phase 10.27 — Scheduler Activation, Deterministic Regression and Five-Day Soak Test Audit Report

**Date**: 2026-10-30  
**Evaluation Timestamp**: `2026-10-30 11:15:00 IST`  
**Operating Mode**: `STRICT SHADOW VALIDATION ONLY`  
**Repository**: `D:\personal\st-ai\ipo-record`  
**Latest Report Commit**: `b3aec59`  
**Overall Verdict**: **`PASS (Deterministic Regression Resolved, Production Ledgers Verified) / SOAK TEST IN PROGRESS`**  
**Final Production Recommendation**: **`CONDITIONAL GO`** (Automated collection runner, process locking, and telemetry verified; Windows Task Scheduler host activation and five-day continuous soak test remain pending operator elevation)

---

## 1. Executive Verdict & Invariant Preservations

Phase 10.27 closed the deterministic regression gap, resolved time-dependent test failures from historical suites, verified frozen model and manifest hashes, checked production ledger integrity, and audited live candidate cutoff boundaries.

### Invariant & Compliance Checklist
| Governance Requirement | Expected Value / Policy | Measured Value / Audit Result | Verdict |
|---|---|---|---|
| **Frozen SME Model Hash** | `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` | `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` | **`EXACT MATCH`** |
| **Baseline Manifest Hash** | `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` | `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` | **`EXACT MATCH`** |
| **Retraining / Weight Modification** | STRICTLY PROHIBITED | Zero weights, features, thresholds, or calibration files modified | **`STRICT PASS`** |
| **Mainboard Scoring Prohibition** | Non-scoring only (`BLOCKED_GOVERNANCE`) | Model_6B_SME_v1.0 is never evaluated on Mainboard candidates | **`STRICT PASS`** |
| **Broker Integration & Trading** | Prohibited | Zero order routing, broker APIs, or real-money execution capabilities | **`STRICT PASS`** |
| **Retroactive Decision Commits** | Prohibited | Expired candidates cannot be committed retroactively | **`STRICT PASS`** |

---

## 2. Step A — Initial & Final Git / Artifact State

- **Initial Commit**: `b3aec59` (`docs(audit): publish Phase 10.26 scheduler activation, connectivity diagnostics, and regression gate report`)
- **Working Tree Integrity**:
  - `src/api/main.py`: Enhanced `get_ipo_detail()` endpoint to accept an optional `evaluation_timestamp_ist` query parameter for point-in-time evaluation consistency.
  - Historical test suites: Injected explicit pre-cutoff point-in-time timestamps (`2026-10-28 12:00:00 IST`) into the 7 historical tests that previously failed due to wall-clock time passing Wiscon's cutoff.
- **Production Ledgers**:
  - `data/processed/prospective_decisions.jsonl`: **0 records**
  - `data/processed/prospective_outcomes.jsonl`: **0 records**
  - `data/processed/prospective_evaluation_records.jsonl`: **0 records**
  - `data/processed/governance_audit_events.jsonl`: **0 records**
  - `data/processed/operational_run_ledger.jsonl`: **6 records**, hash chain verified (`valid: True`).

---

## 3. Step B — Deterministic Regression: Resolution of the 7 Historical Failures

### Root Cause Analysis
During Phase 10.26, 7 historical tests written in Phases 10.11 through 10.16 failed with:
`AssertionError: 'EXPIRED_WITHOUT_COMMIT' != 'BLOCKED_CUTOFF'`

When these tests were authored, Wiscon Industries Ltd (`wiscon-industries-sme-20261029`) had an asserted cutoff in the future (`2026-10-29 16:00:00 IST`). When run under real wall-clock time after 16:00 IST on 2026-10-29 or on 2026-10-30, the strict boundary rule $t_{\text{now}} \ge t_{\text{cutoff}}$ correctly triggered `EXPIRED_WITHOUT_COMMIT`. Without an explicit point-in-time timestamp, the tests relied on `datetime.now()`, creating a nondeterministic test failure.

### Resolution & Verification
Per Phase 10.27 instructions, point-in-time timestamps (`evaluation_timestamp_ist="2026-10-28 12:00:00 IST"`) were injected into these unit tests. All 7 tests now run deterministically and pass:

| Test Identifier | Previous Status | Resolution Applied | New Status |
|---|---|---|---|
| `test_phase_10_11_readiness.py::test_api_detail_returns_three_distinct_milestones` | FAIL (`EXPIRED_WITHOUT_COMMIT`) | Parameterized with `evaluation_timestamp_ist` | **`PASS`** |
| `test_phase_10_11_readiness.py::test_candidate_lifecycle_states_reconciliation` | FAIL (`EXPIRED_WITHOUT_COMMIT`) | Evaluated at pre-cutoff timestamp | **`PASS`** |
| `test_phase_10_13_point_in_time.py::test_14_official_evidence_tied_to_wrong_ipo` | FAIL (`EXPIRED_WITHOUT_COMMIT`) | Evaluated at pre-cutoff timestamp | **`PASS`** |
| `test_phase_10_13_point_in_time.py::test_22_api_dashboard_readiness_consistency` | FAIL (`EXPIRED_WITHOUT_COMMIT`) | Parameterized with `evaluation_timestamp_ist` | **`PASS`** |
| `test_phase_10_14_independent_gate.py::test_16_tracked_sme_candidates_remain_blocked_cutoff` | FAIL (`EXPIRED_WITHOUT_COMMIT`) | Evaluated at pre-cutoff timestamp | **`PASS`** |
| `test_phase_10_15_candidate_resolution.py::test_21_api_dashboard_consistency` | FAIL (`EXPIRED_WITHOUT_COMMIT`) | Parameterized with `evaluation_timestamp_ist` | **`PASS`** |
| `test_phase_10_16_persistence_assurance.py::test_15_wiscon_and_carver_remain_blocked_cutoff` | FAIL (`EXPIRED_WITHOUT_COMMIT`) | Evaluated at pre-cutoff timestamp | **`PASS`** |

### Full Repository Regression Gate
- **Total Discovered Tests**: **491**
- **Passed Tests**: **491**
- **Failed Tests**: **0**
- **Errors**: **0**
- **Full Discovery Exit Code**: **0 (100% PASS RATE)**

---

## 4. Step C & D — Scheduled Task Activation & Host Collector Verification

### 1. Task Scheduler Status
Executing `scripts/verify_scheduled_tasks.ps1` confirms:
```
==================================================================
 Phase 10.25 Scheduled Tasks Verification & Inspection
 Operating Mode: STRICT SHADOW VALIDATION ONLY (Read-Only)
==================================================================

--- Checking Task: IPORecord_NoticeCollector ---
  Status: NOT INSTALLED

--- Checking Task: IPORecord_DeadlineSweeper ---
  Status: NOT INSTALLED

--- Checking Task: IPORecord_MonitoringReport ---
  Status: NOT INSTALLED

==================================================================
 Summary Status: ONE OR MORE TASKS NOT INSTALLED
 To deploy, run: .\scripts\deploy_scheduled_tasks.ps1
==================================================================
```
- **Deployment Status**: **`BLOCKED_DEPLOYMENT_PERMISSIONS`**.
- Registering scheduled tasks via Windows PowerShell CIM cmdlets requires an elevated Administrator or batch-job user session.
- **Operator Command**:
  ```powershell
  # Run in PowerShell as Administrator:
  powershell -ExecutionPolicy Bypass -File .\scripts\deploy_scheduled_tasks.ps1
  ```

### 2. Host Collector Diagnostics
Host execution directly outside the sandbox confirms:
- **DNS Resolution**: `www.bseindia.com` -> `23.195.105.25`, `www.nseindia.com` -> `23.217.111.10`
- **TLS Handshake**: Negotiated `TLSv1.3`
- **HTTP Status**: HTTP 200 (BSE: 16,191 bytes, NSE: 324,852 bytes)
- **Anti-Bot Check**: No CAPTCHA or Cloudflare challenge pages detected.
- **Verification Rule**: While exchange pages are accessible, neither BSE nor NSE has issued official retail bidding circulars for tracked candidates. Bidding cutoffs remain strictly unverified.

---

## 5. Step E — Five-Trading-Day Soak Test Status

- **Status**: **`SOAK_TEST_IN_PROGRESS`** (Elapsed Days: 0 of 5 required trading days).
- **Start Criteria**: The soak test clock begins once `IPORecord_NoticeCollector` and `IPORecord_DeadlineSweeper` are installed and run autonomously under the host scheduler.
- **Prohibition on Synthetic Completion**: No synthetic dates, mock timestamps, or fabricated runs were added. All metrics reflect true zero-soak elapsed days.

---

## 6. Step F & H — Candidate Lifecycle Reconciliation

Current candidate status in [`data/registered/tracked_candidate_registry.json`](file:///d:/personal/st-ai/ipo-record/data/registered/tracked_candidate_registry.json) at `2026-10-30 11:15:00 IST`:

| IPO ID | Company Name | Segment | Cutoff Time (IST) | Current Lifecycle State | Clean Eligible? | Reason Code |
|---|---|---|---|---|---|---|
| `wiscon-industries-sme-20261029` | Wiscon Industries Ltd | SME | 2026-10-29 16:00:00 | **`EXPIRED_WITHOUT_COMMIT`** | **`False`** | `CANDIDATE_CUTOFF_EXPIRED: Cutoff elapsed without commit` |
| `carver-roboweld-sme-20261030` | Carver Roboweld Ltd | SME | 2026-10-30 16:00:00 | **`BLOCKED_CUTOFF`** | **`False`** | `EXCHANGE_BIDDING_CUTOFF_UNVERIFIED` |
| `bls-polymers-mainboard-20261029` | BLS Polymers Ltd | Mainboard | 2026-10-29 17:00:00 | **`BLOCKED_GOVERNANCE`** | **`False`** | `MAINBOARD_CANDIDATE_NON_SCORING: Restricted to SME` |
| `sfc-environmental-mainboard-20261029` | SFC Environmental Ltd | Mainboard | 2026-10-29 17:00:00 | **`BLOCKED_GOVERNANCE`** | **`False`** | `MAINBOARD_CANDIDATE_NON_SCORING: Restricted to SME` |
| `mk-sons-mainboard-20261030` | M.K. Sons Ltd | Mainboard | 2026-10-30 17:00:00 | **`BLOCKED_GOVERNANCE`** | **`False`** | `MAINBOARD_CANDIDATE_NON_SCORING: Restricted to SME` |
| `eaaa-india-mainboard-20261028` | EAAA India Alternatives | Mainboard | 2026-10-28 17:00:00 | **`BLOCKED_GOVERNANCE`** | **`False`** | `MAINBOARD_CANDIDATE_NON_SCORING: Restricted to SME` |

*Today's Active Cutoff*: Carver Roboweld Ltd (`carver-roboweld-sme-20261030`) closes today at 16:00 IST. If no primary circular is ingested prior to 16:00 IST, it will transition to `EXPIRED_WITHOUT_COMMIT`.

---

## 7. Production Gate Recommendation: CONDITIONAL GO

- **Deterministic Test Gate**: **`GO`** (491 / 491 tests pass with 0 failures, 0 errors).
- **Frozen Artifacts**: **`GO`** (Exact SHA-256 match).
- **Concurrency & Locking**: **`GO`** (Kernel-level file locking verified).
- **Production Ledgers**: **`GO`** (Clean zero records maintained).
- **Scheduler Deployment & Soak Test**: **`CONDITIONAL GO`** (Pending operator installation with elevated permissions).
- **Broker & Order Routing**: **`STRICT NO-GO`** (Prohibited; zero broker integrations).
