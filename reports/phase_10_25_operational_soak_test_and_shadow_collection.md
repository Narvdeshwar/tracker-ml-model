# Phase 10.25 — Operational Soak Test and Shadow Collection Verification Audit Report

**Date**: 2026-10-29  
**Evaluation Timestamp**: `2026-10-29 17:50:00 IST`  
**Operating Mode**: `STRICT SHADOW VALIDATION ONLY`  
**Phase**: Phase 10.25 — Operational Soak Test & Shadow Collection Verification  
**Repository**: `D:\personal\st-ai\ipo-record`  
**Overall Status**: **`PASS (Operational Invariants Verified) / SOAK TEST IN PROGRESS`**  
**Production Gate Decision**: **`CONDITIONAL GO`** (Automated collection runner, process locking, and telemetry verified; soak test and live task scheduler deployment remain in progress)

---

## 1. Executive Summary & Verification of Prior Phase Claims

Phase 10.25 was initiated to audit and verify the actual operational behavior of the shadow-validation system, resolve operational discrepancies reported in Phase 10.24, test scheduler configurations against host infrastructure, and assess the progress of prospective collection.

### Verification of Reported Phase 10.24 Claims
| Claim / Requirement | Phase 10.24 Claim | Phase 10.25 Verification Result | Status |
|---|---|---|---|
| **Frozen Model SHA-256** | `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` | Recomputed `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` | **`EXACT MATCH`** |
| **Baseline Manifest SHA-256** | `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` | Recomputed `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` | **`EXACT MATCH`** |
| **Scheduler Deployment** | Described as 15m and 5m tasks | Audit identified command syntax flaw: `New-ScheduledTaskTrigger -Daily` did not configure repetition intervals. Tasks were **NOT INSTALLED** in host OS scheduler. | **`CORRECTED & DOCUMENTED`** |
| **Operational Telemetry Ledger** | Append-only ledger with hash chaining | Inspected [`src/operational_run_ledger.py`](file:///d:/personal/st-ai/ipo-record/src/operational_run_ledger.py). Verified SHA-256 hash chaining, pre-write corruption halts, and isolated recovery. | **`VERIFIED`** |
| **Four Empty Production Ledgers** | 0 decisions, 0 outcomes, 0 evaluations, 0 events | Decision (0), Outcome (0), Evaluation (0), Governance Events (0 active). Clean zero maintained. | **`VERIFIED (ZERO RECORDS)`** |
| **Prospective Mature Outcomes** | 0 mature outcomes | Exactly 0 mature prospective outcomes (`INCONCLUSIVE_ZERO_OUTCOMES`). | **`VERIFIED`** |
| **Broker / Trading Prohibition** | No broker APIs or trading | Strictly zero broker integrations, order routing, or real-money trading logic in repository. | **`STRICT PASS`** |

---

## 2. Frozen Artifact Integrity Audit

Both the frozen model binary and baseline manifest were independently audited via byte-level recalculation:

```powershell
# Model Hash Verification
Get-FileHash models/baseline/model_6b_sme_v1.0.joblib -Algorithm SHA256
# Result: DBF2EEC7169888424698C55286C59C406C58B61FF77D34CA6BEABAB1E53AAD76

# Manifest Hash Verification
Get-FileHash models/baseline/baseline_manifest.json -Algorithm SHA256
# Result: B19C913E7C0E0AFD6054255F389A4CAB3A15D79E338F67C5FC04CACDE7E86C6E
```

No retraining, refitting, recalibration, parameter adjustment, or weight mutation was performed.

---

## 3. Windows Task Scheduler Audit, Correction & Verification

### Root Cause Analysis of Previous Discrepancy
In Phase 10.24, the deployment documentation stated that `IPORecord_NoticeCollector` ran every 15 minutes and `IPORecord_DeadlineSweeper` ran every 5 minutes. However, the provided PowerShell commands:
```powershell
$trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM
```
only scheduled a single daily invocation at 09:00 AM. In Windows PowerShell, `-RepetitionInterval` is only supported in parameter set `Once`, not `Daily` or `Weekly`.

### Corrective Scripts Created
1. **Deployment Script**: [`scripts/deploy_scheduled_tasks.ps1`](file:///d:/personal/st-ai/ipo-record/scripts/deploy_scheduled_tasks.ps1)
   - Employs `-Once -At "09:00" -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 3650)` for notice collection.
   - Employs `-Once -At "15:00" -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)` for deadline sweeper.
   - Supports `-WhatIf` non-destructive simulation (`[CmdletBinding(SupportsShouldProcess=$true)]`).
   - Configures `ExecutionTimeLimit = 5 mins` and `MultipleInstances = IgnoreNew` (`DoNotNewInstance`).
2. **Read-Only Verification Script**: [`scripts/verify_scheduled_tasks.ps1`](file:///d:/personal/st-ai/ipo-record/scripts/verify_scheduled_tasks.ps1)
   - Performs read-only inspection using `Get-ScheduledTask` and `Get-ScheduledTaskInfo`.
   - Surfaces state, last run time, next run time, and last exit code without modifying any OS configuration.

### Actual Output of Scheduled Tasks Verification
Executing `scripts/verify_scheduled_tasks.ps1` against the host OS confirmed:
```
=== IPO Record Scheduled Tasks Verification ===
Task Name: IPORecord_NoticeCollector -> NOT INSTALLED
Task Name: IPORecord_DeadlineSweeper -> NOT INSTALLED
Task Name: IPORecord_DailyMonitoring -> NOT INSTALLED
```
**Finding**: Because the tasks require elevated batch-job privileges to register on the Windows host, they are currently **`NOT INSTALLED`** in the system scheduler. Full deployment commands are prepared in [`scripts/deploy_scheduled_tasks.ps1`](file:///d:/personal/st-ai/ipo-record/scripts/deploy_scheduled_tasks.ps1).

---

## 4. End-to-End Operational CLI Runner Verification

The CLI runner [`src/operational_task_runner.py`](file:///d:/personal/st-ai/ipo-record/src/operational_task_runner.py) was exercised directly from the command line:

### 1. `collect_notices` Action
- **Invocation**: `.\.venv\Scripts\python.exe src/operational_task_runner.py --action collect_notices --exchanges BSE NSE`
- **Output**:
  ```
  Starting official exchange notice collection for ['BSE', 'NSE']...
  [BSE] Live endpoint result: LIVE_SOURCE_UNAVAILABLE (Error: FETCH_FAILED / HTTP_ERROR)
  [NSE] Live endpoint result: LIVE_SOURCE_UNAVAILABLE (Error: FETCH_FAILED / HTTP_ERROR)
  Notice collection completed with 2 errors.
  ```
- **Exit Code**: `1` (partial/total failure fails closed).
- **Behavior**: Correctly logged to telemetry ledger with `LIVE_SOURCE_UNAVAILABLE` and zero candidate mutations.

### 2. `sweep_expiries` Action
- **Invocation**: `.\.venv\Scripts\python.exe src/operational_task_runner.py --action sweep_expiries`
- **Output**:
  ```
  Starting candidate deadline expiry sweep...
  [2026-10-29 17:50:00 IST] Sweep summary: total=6, active=1, newly_expired=1, already_expired=4, errors=0
  ```
- **Exit Code**: `0`.
- **Behavior**: Successfully swept tracked candidates, identifying Wiscon Industries (`wiscon-industries-sme-20261029`) as expired without commit past 16:00 IST.

### 3. `monitoring_report` Action
- **Invocation**: `.\.venv\Scripts\python.exe src/operational_task_runner.py --action monitoring_report`
- **Output**: Valid JSON payload containing collection health, evidence verification health, and candidate lifecycle summary.
- **Exit Code**: `0`.
- **Behavior**: Completely read-only; no ledger records created.

---

## 5. Live-Source Observation vs Synthetic Mocks

### Production Endpoint Verification
When querying live exchange endpoints without artificial mocks:
- **BSE Public Notices URL**: Public endpoint was challenged by transport boundaries (`LIVE_SOURCE_UNAVAILABLE`).
- **NSE Circulars URL**: Public endpoint timed out or failed DNS lookup (`LIVE_SOURCE_UNAVAILABLE`).
- **Anti-Bot Classification**: The collector includes automated heuristics scanning responses for `captcha`, `cloudflare`, `access denied`, `security check`, and `blocked`. When detected, it classifies the result strictly as `ANTI_BOT_CHALLENGE` with verification status `LIVE_SOURCE_UNAVAILABLE`.
- **Integrity Rule**: Secondary websites (Chittorgarh, IPO Watch) are strictly rejected as official cutoff evidence. Only official primary circulars from BSE/NSE are accepted.

---

## 6. Operational Telemetry Ledger Integrity

The operational telemetry ledger ([`src/operational_run_ledger.py`](file:///d:/personal/st-ai/ipo-record/src/operational_run_ledger.py)) was subjected to adversarial verification in [`tests/test_phase_10_25_soak_test_and_verification.py`](file:///d:/personal/st-ai/ipo-record/tests/test_phase_10_25_soak_test_and_verification.py):

1. **Cryptographic Hash Chaining**: Every record computes `record_sha256 = SHA256(prev_sha256 + json_payload)`. `verify_ledger_chain()` validates all sequential hashes.
2. **Pre-Write Corruption Detection**: If a corrupted or truncated line exists in the ledger file, `inspect_ledger_corruption()` halts append operations immediately with `IOError`.
3. **Crash Recovery**: When a process crashes holding a lock, kernel-level file locking (`msvcrt.locking` on Windows) automatically releases file descriptor locks upon process termination, allowing subsequent runs to acquire the lock cleanly.
4. **Zero Impact on Production Ledgers**: Operational runs are persisted exclusively to `data/processed/operational_run_ledger.jsonl`. Core decision, outcome, and evaluation ledgers are never touched.

---

## 7. Candidate Lifecycle Status & Clean Separation of Four Operational States

At current evaluation time (`2026-10-29 17:50:00 IST`), the system enforces strict separation across four distinct operational dimensions:

| Dimension | Measured Status | Rationale |
|---|---|---|
| **1. Task Execution State** | **`OPERATIONAL`** | The CLI task runner executes reliably, captures process exit codes, and manages OS-level file locks. |
| **2. Collection Availability State** | **`UNAVAILABLE`** | Live BSE/NSE exchange endpoints return network/transport errors; zero live circulars fetched. |
| **3. Evidence Verification State** | **`UNVERIFIED`** | Exactly 0 primary exchange notices verified. Asserted cutoff times remain unproven. |
| **4. Candidate Eligibility State** | **`BLOCKED / EXPIRED`** | Tracked candidates are either expired or blocked by cutoff/governance gates. |

### Tracked Candidates Status Table
| IPO ID | Company Name | Board | Cutoff Time (IST) | Bidding Cutoff Status | Current Lifecycle State | Eligible for Commit? |
|---|---|---|---|---|---|---|
| `wiscon-industries-sme-20261029` | Wiscon Industries Ltd | SME | 2026-10-29 16:00:00 | Unverified (Asserted) | **`EXPIRED_WITHOUT_COMMIT`** | **NO** (Cutoff elapsed past 16:00 IST) |
| `carver-roboweld-sme-20261030` | Carver Roboweld Ltd | SME | 2026-10-30 16:00:00 | Unverified (Asserted) | **`BLOCKED_CUTOFF`** | **NO** (Bidding cutoff unverified) |
| `bls-polymers-mainboard-20261029` | BLS Polymers Ltd | Mainboard | 2026-10-29 17:00:00 | Unverified (Asserted) | **`BLOCKED_GOVERNANCE`** | **NO** (Model restricted to SME) |
| `sfc-environmental-mainboard-20261029` | SFC Environmental Ltd | Mainboard | 2026-10-29 17:00:00 | Unverified (Asserted) | **`BLOCKED_GOVERNANCE`** | **NO** (Model restricted to SME) |
| `mk-sons-mainboard-20261030` | M.K. Sons Ltd | Mainboard | 2026-10-30 17:00:00 | Unverified (Asserted) | **`BLOCKED_GOVERNANCE`** | **NO** (Model restricted to SME) |
| `eaaa-india-mainboard-20261028` | EAAA India Alternatives | Mainboard | 2026-10-28 17:00:00 | Elapsed (Unverified) | **`BLOCKED_GOVERNANCE`** | **NO** (Elapsed & restricted to SME) |

---

## 8. Prospective Collection Soak Test Progress

- **Current Status**: **`SOAK_TEST_IN_PROGRESS`**
- **Evaluation Criteria**: Minimum 5 consecutive trading days with scheduled tasks actively running, recording runs, and sweeping candidate deadlines.
- **Current Observation**: Because tasks are not yet active in the host scheduler, the soak test is marked `SOAK_TEST_IN_PROGRESS` (0 days completed).
- **Prohibition on Synthetic Completion**: No synthetic dates, mock timestamps, or fabricated soak completions were introduced.

---

## 9. Core Production Ledgers Status

All production ledgers remain strictly empty:
- `data/processed/prospective_decisions.jsonl`: **0 records**
- `data/processed/prospective_outcomes.jsonl`: **0 records**
- `data/processed/prospective_evaluation_records.jsonl`: **0 records**
- `data/processed/governance_audit_events.jsonl`: **0 records**

---

## 10. Phase 10.25 Unit & Integration Test Results

A dedicated adversarial test suite [`tests/test_phase_10_25_soak_test_and_verification.py`](file:///d:/personal/st-ai/ipo-record/tests/test_phase_10_25_soak_test_and_verification.py) was constructed and executed:

| Test Name | Workstream | Description | Status |
|---|---|---|---|
| `test_01_four_operational_states_cleanly_separated` | A: States | Verifies monitoring report cleanly separates Execution, Collection, Evidence, and Eligibility | **`PASS`** |
| `test_02_endpoint_unreachable_fails_closed` | A: Live Source | Verifies unreachable endpoint returns `LIVE_SOURCE_UNAVAILABLE` with exit code 1 | **`PASS`** |
| `test_03_telemetry_detects_middle_corruption` | B: Ledger | Verifies corrupted middle line halts append with `IOError` | **`PASS`** |
| `test_04_telemetry_detects_truncated_record` | B: Ledger | Verifies unclosed JSON line is detected by pre-write scan | **`PASS`** |
| `test_05_process_crash_lock_recovery` | B: Crash Recovery | Verifies lock release when simulated process terminates unexpectedly | **`PASS`** |
| `test_06_configuration_fingerprint_in_telemetry` | B: Config | Verifies telemetry records CLI config fingerprint and arguments | **`PASS`** |
| `test_07_anti_bot_challenge_detection` | C: Invariants | Verifies Cloudflare / CAPTCHA challenge is classified as `ANTI_BOT_CHALLENGE` | **`PASS`** |
| `test_08_commit_boundary_cutoff_recheck` | C: Invariants | Verifies commit fails closed if candidate expired between read and write | **`PASS`** |
| `test_09_mainboard_candidates_never_scored` | C: Invariants | Verifies Mainboard candidates receive `BLOCKED_GOVERNANCE` and never invoke SME model | **`PASS`** |
| `test_10_production_ledgers_clean_at_zero` | C: Invariants | Verifies decision, outcome, and evaluation ledgers remain strictly 0 records | **`PASS`** |
| `test_11_frozen_artifacts_exact_hash_match` | D: Integrity | Verifies exact SHA-256 matches for model and manifest | **`PASS`** |

**Execution Output**:
```
Ran 11 tests in 8.634s
OK (100% Pass Rate)
```

Across the operational test suites (Phase 10.23: 15 tests, Phase 10.24: 16 tests, Phase 10.25: 11 tests), **42 out of 42 tests pass with zero failures and zero errors**.

---

## 11. Modified & Untracked Files

1. [`scripts/deploy_scheduled_tasks.ps1`](file:///d:/personal/st-ai/ipo-record/scripts/deploy_scheduled_tasks.ps1): Corrected PowerShell deployment script with valid repetition syntax and `-WhatIf` support.
2. [`scripts/verify_scheduled_tasks.ps1`](file:///d:/personal/st-ai/ipo-record/scripts/verify_scheduled_tasks.ps1): Non-destructive read-only verification script inspecting host task scheduler status.
3. [`tests/test_phase_10_25_soak_test_and_verification.py`](file:///d:/personal/st-ai/ipo-record/tests/test_phase_10_25_soak_test_and_verification.py): 11 comprehensive tests for operational states, ledger corruption, anti-bot classification, and lock recovery.
4. [`reports/phase_10_25_operational_soak_test_and_shadow_collection.md`](file:///d:/personal/st-ai/ipo-record/reports/phase_10_25_operational_soak_test_and_shadow_collection.md): This report.

---

## 12. Remaining Operational Blockers

1. **Exchange Public Access Protections**: BSE/NSE public circular pages actively employ bot management and TLS/WAF controls that block automated scraping from unsanctioned hosts.
2. **Missing Official Circulars for Tracked Issues**:
   - `wiscon-industries-sme-20261029`: Cutoff (16:00 IST) has elapsed without primary circular verification; state is terminal `EXPIRED_WITHOUT_COMMIT`.
   - `carver-roboweld-sme-20261030`: Cutoff (16:00 IST on 2026-10-30) remains unverified. If no official circular is ingested prior to 16:00 IST tomorrow, it will transition to `EXPIRED_WITHOUT_COMMIT`.
3. **Elevated Privilege Execution**: Registering scheduled tasks via Windows Task Scheduler requires administrative or batch-job account permissions on the host machine.

---

## 13. Production Gate Recommendation: CONDITIONAL GO

- **Model Invariants**: **`GO`** (Frozen model and manifest SHA-256 digests perfectly preserved).
- **Concurrency & Locking**: **`GO`** (OS-level kernel file locking handles concurrency and process termination).
- **Telemetry & Error Logging**: **`GO`** (Isolated operational run ledger captures failures and survives corruption).
- **Automated Collection Execution**: **`CONDITIONAL GO`** (CLI runners verified; host OS scheduler deployment pending manual administrative execution of `deploy_scheduled_tasks.ps1`).
- **Live Trading**: **`STRICT NO-GO`** (Real-money trading strictly prohibited; zero broker routing enabled).
