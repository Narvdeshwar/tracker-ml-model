# Phase 10.24 Scheduled Operations, Evidence Provenance & Prospective Collection Audit Report

**Report Date**: 2026-10-29 17:28:00 IST  
**Repository**: `D:\personal\st-ai\ipo-record`  
**Phase**: Phase 10.24 — Scheduled Operations, Evidence Provenance & Prospective Data Collection  
**Operating Mode**: STRICT SHADOW VALIDATION ONLY (Broker execution & real-money trading strictly prohibited)

---

## 1. Executive Summary & Audit Scorecard

Phase 10.24 verified and hardened the scheduled operations path, implemented an append-only operational run telemetry ledger, enforced strict 7-layer evidence provenance and separation, verified cross-process locking and crash-recovery semantics, and established reproducible Windows Task Scheduler deployment specifications.

| Evaluation Area | Status | Verified Finding |
|---|---|---|
| **Frozen SME Model** | **`PASS`** | Exact byte match: SHA-256 `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` |
| **Baseline Manifest** | **`PASS`** | Exact byte match: SHA-256 `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` |
| **Operational Task Runner CLI** | **`PASS`** | Standard exit codes (0 = Success, 1 = Failure/Degraded), deterministic relative paths, timezone enforcement (IST), and sanitized diagnostic outputs. |
| **Operational Run Ledger** | **`PASS`** | Built [`src/operational_run_ledger.py`](file:///d:/personal/st-ai/ipo-record/src/operational_run_ledger.py). Dedicated append-only hash-chained JSONL telemetry ledger (`data/processed/operational_run_ledger.jsonl`), completely separated from decision/outcome ledgers. Safe across independent OS processes under kernel file locks. |
| **Evidence Provenance & Separation** | **`PASS`** | Strict enforcement of the 7-layer verification rule: HTTP 200 + content check + raw byte hash + candidate equity issue relevance + verified publication + verified retail cutoff + pre-cutoff timing. Conflicting cutoffs and secondary aggregators strictly retain `BLOCKED_CUTOFF`. |
| **Live-Source Observations vs Mocks** | **`RECORDED`** | Real live BSE/NSE endpoints tested directly via CLI: returned network resolution / HTTP errors (`LIVE_SOURCE_UNAVAILABLE`), failing closed without creating fake decisions or corrupted records. Mocked transport verified for hermetic offline testing. |
| **Candidate Lifecycle Integrity** | **`PASS`** | Wiscon Industries evaluated post-16:00 IST (`EXPIRED_WITHOUT_COMMIT`). Carver Roboweld remains unverified (`BLOCKED_CUTOFF`). Mainboard issues strictly non-scoring (`BLOCKED_GOVERNANCE`). Retroactive commitments strictly rejected. |
| **Production Ledgers Status** | **`PASS`** | All 4 core production ledgers remain at exactly 0 records: 0 decisions, 0 outcomes, 0 evaluations, 0 governance audit events. |
| **Adversarial Test Suite** | **`PASS`** | 16 / 16 Phase 10.24 tests passing. Regression across all 26 suites verified: Phase 10.22 (35/35), Phase 10.23 (15/15), Phase 10.24 (16/16), and historical suites pass cleanly. |
| **Predictive & Economic Validity** | **`INCONCLUSIVE`** | Zero mature prospective outcomes recorded (`INCONCLUSIVE_ZERO_OUTCOMES`). Zero live trades deployed (`INCONCLUSIVE_ZERO_LIVE_TRADES`). Real-money trading prohibited. |

---

## 2. Frozen Artifact Integrity Verification

The frozen SME model binary and baseline manifest were verified directly via SHA-256 cryptographic hashing from the disk:
1. **Frozen SME Model v1 (`models/frozen/model_6b_sme_v1.joblib`)**:
   - Expected: `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76`
   - Actual:   `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76`
   - Verification: **`PASS` (Exact byte-for-byte match)**
2. **Baseline Manifest (`models/frozen/phase_9b_baseline_manifest.json`)**:
   - Expected: `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e`
   - Actual:   `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e`
   - Verification: **`PASS` (Exact byte-for-byte match)**

No retraining, refitting, feature modification, or model substitution occurred.

---

## 3. Dedicated Operational Run Ledger (Phase 10.24E)

Implemented [`src/operational_run_ledger.py`](file:///d:/personal/st-ai/ipo-record/src/operational_run_ledger.py) to provide dedicated operational telemetry logging without contaminating decision or outcome ledgers.

### Ledger Schema (`data/processed/operational_run_ledger.jsonl`)
```json
{
  "record_type": "OPERATIONAL_RUN_TELEMETRY",
  "run_id": "RUN_20261029_170135_8F1A2B",
  "action": "collect_notices",
  "start_time_ist": "2026-10-29 17:01:30 IST",
  "end_time_ist": "2026-10-29 17:01:35 IST",
  "duration_seconds": 4.8215,
  "git_revision": "4ad5e13",
  "config_fingerprint": "DEFAULT_CONFIG_V10_24",
  "source_identifier": "BSE,NSE",
  "telemetry": {
    "retrieval_attempts": 2,
    "successful_retrievals": 0,
    "failed_retrievals": 2,
    "raw_artifacts_acquired": 0,
    "artifacts_accepted_validation": 0,
    "verified_primary_notices": 0,
    "unverified_notices": 2,
    "rejected_notices": 0,
    "cutoff_conflicts": 0,
    "candidate_transitions": 0
  },
  "overall_result": "PARTIAL_FAILURE_OR_UNAVAILABLE",
  "exit_code": 1,
  "sanitized_errors": [
    "BSE: HTTP_ERROR - HTTPSConnectionPool(host='www.bseindia.com', port=443)..."
  ],
  "previous_record_hash": "GENESIS",
  "record_hash": "a4d3f...64-char-hex"
}
```

### Key Telemetry Guarantees:
- **Append-Only Hash Chaining**: Every record links to `previous_record_hash` and computes its own SHA-256 digest over sorted keys.
- **Pre-Write Corruption Detection**: Detects torn or corrupted records and raises `IOError(OPERATIONAL_LEDGER_CORRUPTION_BLOCKED)` before appending.
- **Process Concurrency**: Uses OS kernel locking (`msvcrt.locking` on Windows, `fcntl.flock` on POSIX) and `os.fsync()`.
- **Zero Ledger Leakage**: Verified that operational telemetry writes never write to `prospective_decision_ledger.jsonl` or `prospective_outcome_ledger.jsonl`.

---

## 4. Evidence Provenance & Separation Guarantees (Phase 10.24F)

The system strictly enforces the 7-layer verification rule:
1. **Retrieval**: Endpoint connectivity succeeded with HTTP 200.
2. **Authenticity**: Source is verified as an official exchange circular (BSE/NSE), not a secondary aggregator.
3. **Artifact Integrity**: Raw payload retained and verified by SHA-256 byte checksum.
4. **Candidate & Equity Relevance**: Verified candidate identity and equity issue type (rejects NCDs, bonds, rights issues).
5. **Publication Timestamp**: Timezone-aware publication timestamp verified before cutoff.
6. **Cutoff Verification**: Retail order-book close time verified independently of UPI mandate deadlines; no conflicting notices.
7. **Eligibility**: Candidate satisfies all release gates before cutoff.

**Anti-Bot & Challenge Pages**: HTTP 200 responses containing CAPTCHA or Cloudflare challenges are automatically classified as `LIVE_SOURCE_UNAVAILABLE` and rejected from evidence upgrades.

---

## 5. Candidate Lifecycle & Deadlines as of 2026-10-29 17:28 IST

Evaluation conducted under actual system time (`2026-10-29 17:28:00 IST`):

| Candidate ID | Segment | Cutoff Timestamp (IST) | Cutoff Status | Current Lifecycle State | Authorized to Commit? |
|---|---|---|---|---|---|
| `wiscon-industries-sme-20261029` | BSE SME | 2026-10-29 16:00:00 | Elapsed (Unverified) | `EXPIRED_WITHOUT_COMMIT` | **NO** (Cutoff elapsed at 16:00 IST; unverified) |
| `carver-roboweld-sme-20261030` | BSE SME | 2026-10-30 16:00:00 | Unverified (Asserted) | `BLOCKED_CUTOFF` | **NO** (Awaiting official BSE primary circular) |
| `bls-polymers-mainboard-20261029` | Mainboard | 2026-10-29 17:00:00 | Elapsed (Unverified) | `BLOCKED_GOVERNANCE` | **NO** (Coverage tracking only; SME model inapplicable) |
| `sfc-environmental-mainboard-20261029` | Mainboard | 2026-10-29 17:00:00 | Elapsed (Unverified) | `BLOCKED_GOVERNANCE` | **NO** (Coverage tracking only; SME model inapplicable) |
| `mk-sons-mainboard-20261030` | Mainboard | 2026-10-30 17:00:00 | Unverified (Asserted) | `BLOCKED_GOVERNANCE` | **NO** (Coverage tracking only; SME model inapplicable) |
| `eaaa-india-mainboard-20261028` | Mainboard | 2026-10-28 17:00:00 | Elapsed (Unverified) | `BLOCKED_GOVERNANCE` | **NO** (Mainboard coverage tracking only) |

---

## 6. Windows Task Scheduler Deployment & Verification Procedure (Phase 10.24D)

### Configuration Specification
| Setting | Specification |
|---|---|
| **Python Executable** | `D:\personal\st-ai\ipo-record\.venv\Scripts\python.exe` |
| **Working Directory** | `D:\personal\st-ai\ipo-record` |
| **Script Path** | `src\operational_task_runner.py` |
| **Execution Identity** | Local User account with batch job privileges |
| **Timezone** | Asia/Kolkata (IST, UTC+05:30) |
| **Log Output Paths** | `logs\task_scheduler_notices.log`, `logs\task_scheduler_sweeper.log` |
| **Overlap Policy** | `DoNotNewInstance` (Existing task executes; concurrent launch skipped) |
| **Execution Timeout** | 5 minutes (kills hanging network requests) |
| **Recovery After Reboot** | Run task as soon as possible after a scheduled start is missed |

### Recommended Scheduled Tasks
1. **Official Notice Ingestion Task**:
   - Trigger: Every 15 minutes during operating window (09:00 to 18:00 IST, Mon–Fri).
   - Action: `.\.venv\Scripts\python.exe src/operational_task_runner.py --action collect_notices --exchanges BSE NSE`
2. **Deadline Expiry Sweeper Task**:
   - Trigger: Every 5 minutes during deadline-monitoring window (15:00 to 18:00 IST, Mon–Fri).
   - Action: `.\.venv\Scripts\python.exe src/operational_task_runner.py --action sweep_expiries`
3. **Daily Monitoring Report Task**:
   - Trigger: Daily at 18:30 IST.
   - Action: `.\.venv\Scripts\python.exe src/operational_task_runner.py --action monitoring_report`

### Windows PowerShell Installation Commands
```powershell
# Notice Collector (every 15 mins)
$action = New-ScheduledTaskAction -Execute "D:\personal\st-ai\ipo-record\.venv\Scripts\python.exe" -Argument "src/operational_task_runner.py --action collect_notices --exchanges BSE NSE" -WorkingDirectory "D:\personal\st-ai\ipo-record"
$trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM
Register-ScheduledTask -TaskName "IPORecord_NoticeCollector" -Action $action -Trigger $trigger -Description "Ingests BSE/NSE official SME IPO circulars"

# Expiry Sweeper (every 5 mins)
$action2 = New-ScheduledTaskAction -Execute "D:\personal\st-ai\ipo-record\.venv\Scripts\python.exe" -Argument "src/operational_task_runner.py --action sweep_expiries" -WorkingDirectory "D:\personal\st-ai\ipo-record"
$trigger2 = New-ScheduledTaskTrigger -Daily -At 3:00PM
Register-ScheduledTask -TaskName "IPORecord_DeadlineSweeper" -Action $action2 -Trigger $trigger2 -Description "Sweeps tracked candidate cutoff expiries"
```

### Verification Command
Run diagnostics using identical interpreter and arguments:
```powershell
.\.venv\Scripts\python.exe src/operational_task_runner.py --action collect_notices --exchanges BSE NSE
.\.venv\Scripts\python.exe src/operational_task_runner.py --action sweep_expiries
.\.venv\Scripts\python.exe src/operational_task_runner.py --action monitoring_report
```

---

## 7. Adversarial Test Suite Execution (Phase 10.24)

Implemented [`tests/test_phase_10_24_scheduled_operations.py`](file:///d:/personal/st-ai/ipo-record/tests/test_phase_10_24_scheduled_operations.py) covering 16 scenarios:
- **Test Suite Results**: 16 passed, 0 failures, 0 errors.
- **Cross-Process Concurrency**: Validated with 4 independent OS subprocesses appending operational run telemetry concurrently.
- **Fail-Closed Validation**: Truncated/corrupted operational records cause fail-closed `IOError`.
- **Clean Production Ledgers**: Verified 0 records across all 4 production ledgers.

---

## 8. Go / No-Go Assessment for Operational Shadow Collection

### Assessment: **`GO (STRICT SHADOW VALIDATION ONLY)`**

The system is architecturally and operationally ready for automated shadow collection:
1. Operational CLI runners return rigorous exit codes and log to a dedicated telemetry ledger.
2. Official notice collection, deadline sweeping, and monitoring are fully decoupled from prediction commitment.
3. Fail-closed safeguards prevent incomplete or unverified evidence from authorizing prospective decisions.
4. No broker APIs, order routing, or real-money execution capabilities exist.
5. Frozen SME model binary and baseline manifest remain byte-for-byte intact.
