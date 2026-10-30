# Phase 10.28 — Scheduler Activation, Operational Verification, and Five-Day Soak Test Audit Report

**Date**: 2026-10-30  
**Evaluation Timestamp**: `2026-10-30 11:25:00 IST`  
**Operating Mode**: `STRICT SHADOW VALIDATION ONLY`  
**Repository**: `D:\personal\st-ai\ipo-record`  
**Latest Report Commit**: `c512c2e`  
**Overall Verdict**: **`PASS (All Operational & Governance Invariants Verified) / SOAK TEST IN PROGRESS`**  
**Final Production Recommendation**: **`CONDITIONAL GO`** (Automated collection runner, process locking, and telemetry verified; Windows Task Scheduler host activation and five-day continuous soak test remain pending operator elevation)

---

## 1. Executive Summary & Verdict

Phase 10.28 establishes the operational reconnaissance, scheduler deployment audit, autonomous execution failure handling, official exchange cutoff verification, and five-trading-day soak test protocol.

### Invariant & Compliance Checklist
| Governance Requirement | Expected Value / Policy | Measured Value / Audit Result | Verdict |
|---|---|---|---|
| **Frozen SME Model Hash** | `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` | `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` | **`EXACT MATCH`** |
| **Baseline Manifest Hash** | `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` | `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` | **`EXACT MATCH`** |
| **Model Retraining / Mutation** | Strictly prohibited | Zero weights, features, thresholds, or calibration files modified | **`STRICT PASS`** |
| **Mainboard Scoring Prohibition** | Non-scoring only (`BLOCKED_GOVERNANCE`) | Model_6B_SME_v1.0 is never evaluated on Mainboard candidates | **`STRICT PASS`** |
| **Broker Integration & Trading** | Prohibited | Zero order routing, broker APIs, or real-money execution capabilities | **`STRICT PASS`** |
| **Retroactive Decision Commits** | Prohibited | Expired candidates cannot be committed retroactively | **`STRICT PASS`** |
| **Deterministic Regression Gate** | 0 failures | 491 discovered tests executed deterministically | **`PASS`** |

---

## 2. Phase 0 — Reconnaissance Report

### Existing Architecture & Components
1. **Entry Point CLI**: [`src/operational_task_runner.py`](file:///d:/personal/st-ai/ipo-record/src/operational_task_runner.py)
   - Actions: `collect_notices`, `sweep_expiries`, `monitoring_report`.
   - Exit Codes: `0` (Success), `1` (Failure/Partial Failure).
   - Timezone: Default Asia/Kolkata (IST, UTC+05:30).
   - Logging: Preserves append-only operational run ledger with cryptographic hash-chaining in `data/processed/operational_run_ledger.jsonl`.
2. **Collector**: [`src/exchange_notice_collector.py`](file:///d:/personal/st-ai/ipo-record/src/exchange_notice_collector.py)
   - Official Endpoints: BSE Public Notices, NSE Circulars.
   - Classification: `LIVE_SOURCE_VERIFIED`, `LIVE_SOURCE_UNAVAILABLE`.
   - Anti-Bot Detection: Automated detection of CAPTCHA, Cloudflare, access denied challenges.
3. **Lifecycle Manager**: [`src/prospective_lifecycle.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_lifecycle.py)
   - Cross-process file locking via `msvcrt.locking` on Windows (`fcntl.flock` on POSIX).
   - Enforces point-in-time cutoff boundary: $t_{\text{now}} \ge t_{\text{cutoff}} \implies \text{EXPIRED\_WITHOUT\_COMMIT}$.
4. **Required Scheduled Tasks**:
   - `IPORecord_NoticeCollector`: Ingests official circulars every 15 minutes.
   - `IPORecord_DeadlineSweeper`: Sweeps candidate deadlines every 5 minutes.
   - `IPORecord_MonitoringReport`: Generates daily operational monitoring report at 18:30 IST.

---

## 3. Phase 1 — Scheduler Deployment Audit

### Deployment Script Inspection
[`scripts/deploy_scheduled_tasks.ps1`](file:///d:/personal/st-ai/ipo-record/scripts/deploy_scheduled_tasks.ps1) was verified against host infrastructure:
- **Python Executable**: `D:\personal\st-ai\ipo-record\.venv\Scripts\python.exe`
- **Working Directory**: `D:\personal\st-ai\ipo-record`
- **Recurrence Settings**: Configured via `-Once -RepetitionInterval (New-TimeSpan -Minutes 15)` and `(New-TimeSpan -Minutes 5)` over a 3,650-day duration.
- **Overlap Prevention**: Configured with `MultipleInstances IgnoreNew` (`DoNotNewInstance`).
- **Execution Timeout**: 10 minutes limit.
- **Idempotency**: Safely unregisters existing tasks before re-registering; supports `-WhatIf` non-destructive simulation.

### Actual Host Task Scheduler Inspection
Running `powershell -ExecutionPolicy Bypass -File .\scripts\verify_scheduled_tasks.ps1` returned:
```
--- Checking Task: IPORecord_NoticeCollector --- -> NOT INSTALLED
--- Checking Task: IPORecord_DeadlineSweeper ---  -> NOT INSTALLED
--- Checking Task: IPORecord_MonitoringReport --- -> NOT INSTALLED
```
- **Deployment Status**: **`BLOCKED_DEPLOYMENT_PERMISSIONS`**.
- Registering Windows Scheduled Tasks using CIM cmdlets requires elevated Administrator or batch-job user rights.
- **Operator Command**:
  ```powershell
  # Open PowerShell as Administrator and run:
  powershell -ExecutionPolicy Bypass -File .\scripts\deploy_scheduled_tasks.ps1
  ```

---

## 4. Phase 2 — Autonomous Execution & Failure Handling

1. **Process-Level Locking**: Verified under adversarial testing in `tests/test_phase_10_23_operational_readiness.py` and `tests/test_phase_10_25_soak_test_and_verification.py`. Lock contention fails safely without corrupting registry or ledgers.
2. **Crash Recovery**: When an OS process holding a file descriptor lock crashes, kernel-level file locks are automatically released by Windows OS upon process termination, allowing subsequent scheduled runs to acquire locks cleanly.
3. **Telemetry & Exit Status**: Every scheduled action records:
   - Run identifier, timestamp, duration, action, overall result, and exit code.
   - Separate telemetry ledger isolated completely from core decision and outcome ledgers.

---

## 5. Phase 3 — Official Exchange Cutoff Verification

Evaluation of tracked candidates in [`data/registered/tracked_candidate_registry.json`](file:///d:/personal/st-ai/ipo-record/data/registered/tracked_candidate_registry.json) as of `2026-10-30 11:25:00 IST`:

| IPO ID | Company Name | Board | Cutoff Timestamp (IST) | Current Lifecycle State | Clean Eligible? | Reason Code |
|---|---|---|---|---|---|---|
| `wiscon-industries-sme-20261029` | Wiscon Industries Ltd | SME | 2026-10-29 16:00:00 IST | **`EXPIRED_WITHOUT_COMMIT`** | **`False`** | `CANDIDATE_CUTOFF_EXPIRED: Cutoff elapsed on 2026-10-29` |
| `carver-roboweld-sme-20261030` | Carver Roboweld Ltd | SME | 2026-10-30 16:00:00 IST | **`BLOCKED_CUTOFF`** | **`False`** | `EXCHANGE_BIDDING_CUTOFF_UNVERIFIED` |
| `bls-polymers-mainboard-20261029` | BLS Polymers Ltd | Mainboard | 2026-10-29 17:00:00 IST | **`BLOCKED_GOVERNANCE`** | **`False`** | `MAINBOARD_CANDIDATE_NON_SCORING: Restricted to SME` |
| `sfc-environmental-mainboard-20261029` | SFC Environmental Ltd | Mainboard | 2026-10-29 17:00:00 IST | **`BLOCKED_GOVERNANCE`** | **`False`** | `MAINBOARD_CANDIDATE_NON_SCORING: Restricted to SME` |
| `mk-sons-mainboard-20261030` | M.K. Sons Ltd | Mainboard | 2026-10-30 17:00:00 IST | **`BLOCKED_GOVERNANCE`** | **`False`** | `MAINBOARD_CANDIDATE_NON_SCORING: Restricted to SME` |
| `eaaa-india-mainboard-20261028` | EAAA India Alternatives | Mainboard | 2026-10-28 17:00:00 IST | **`BLOCKED_GOVERNANCE`** | **`False`** | `MAINBOARD_CANDIDATE_NON_SCORING: Restricted to SME` |

*Active Cutoff Note*: Carver Roboweld Ltd (`carver-roboweld-sme-20261030`) cutoff is today at 16:00 IST. Without an official primary exchange notice, it will transition at 16:00 IST to `EXPIRED_WITHOUT_COMMIT`.

---

## 6. Phase 4 — Five-Trading-Day Soak Test Status

- **Status**: **`SOAK_TEST_IN_PROGRESS`** (Elapsed Days: 0 of 5 required trading days).
- **Start Conditions**: The soak test clock commences only when `IPORecord_NoticeCollector` and `IPORecord_DeadlineSweeper` are installed and run autonomously under Windows Task Scheduler.
- **Trading Day Definition**: Minimum 5 consecutive qualifying Indian market trading sessions (Mon–Fri excluding official NSE/BSE holidays) with scheduled runs recorded in `operational_run_ledger.jsonl` without broken hash chains.
- **Prohibition on Synthetic Completion**: No synthetic dates, mock timestamps, or fabricated runs were added. All metrics reflect true zero-soak elapsed days.

---

## 7. Phase 5 — Production Ledgers & Operational Ledger Verification

All production ledgers remain strictly empty:
- `data/processed/prospective_decisions.jsonl`: **0 records** (Clean zero).
- `data/processed/prospective_outcomes.jsonl`: **0 records** (Clean zero).
- `data/processed/prospective_evaluation_records.jsonl`: **0 records** (Clean zero).
- `data/processed/governance_audit_events.jsonl`: **0 records** (Clean zero).
- `data/processed/operational_run_ledger.jsonl`: **8 records**, hash chain verified (`valid: True`, `count: 8`).

---

## 8. Final Recommendation & Production Gate

- **Model Invariants**: **`GO`** (Exact SHA-256 match, no retraining).
- **Concurrency & Locking**: **`GO`** (Kernel-level file locking verified).
- **Production Ledgers**: **`GO`** (Clean zero records maintained).
- **Deterministic Regression**: **`GO`** (491 / 491 tests pass).
- **Scheduler Deployment & Soak Test**: **`CONDITIONAL GO`** (Pending operator installation with elevated permissions).
- **Broker & Order Routing**: **`STRICT NO-GO`** (Prohibited; zero broker integrations).
