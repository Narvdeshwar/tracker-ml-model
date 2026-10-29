# Phase 10.22 Official Notice Ingestion, Deadline Monitoring & Lifecycle Reconciliation Audit Report

**Report Date**: 2026-10-29 14:16:00 IST  
**Repository**: `D:\personal\st-ai\ipo-record`  
**Phase**: 10.22 — Official Notice Ingestion, Deadline Monitoring & Lifecycle Reconciliation  
**Operating Mode**: STRICT SHADOW VALIDATION ONLY (Broker execution & real-money trading strictly prohibited)

---

## 1. Executive Summary & Audit Scorecard

Phase 10.22 implemented an official exchange notice collector adapter, robust raw artifact normalization and validation, an idempotent cross-process deadline expiry sweeper, and comprehensive extensions to operational monitoring without modifying frozen predictive artifacts.

| Evaluation Area | Status | Verified Finding |
|---|---|---|
| **Frozen SME Model** | **`PASS`** | Exact byte match: SHA-256 `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` |
| **Baseline Manifest** | **`PASS`** | Exact byte match: SHA-256 `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e` |
| **Notice Ingestion Adapter** | **`PASS`** | Implemented in [`src/exchange_notice_collector.py`](file:///d:/personal/st-ai/ipo-record/src/exchange_notice_collector.py). Features bounded exponential backoff, rate limiting, connection/read timeouts, size verification, deterministic dependency injection for hermetic unit testing, and raw byte retention. |
| **Evidence Normalization & Authority** | **`PASS`** | Raw artifact checksum verified against SHA-256 byte digest prior to parsing. Distinguishes primary exchange circulars from secondary portals, retail order-book closure from UPI mandate deadlines, and equity issues from debt/rights instruments. |
| **Deadline Expiry Sweeper** | **`PASS`** | Implemented `sweep_deadline_expiries()` in [`src/prospective_lifecycle.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_lifecycle.py). Safely scans candidate deadlines, enforces boundary rule $t_{\text{now}} \ge t_{\text{cutoff}}$, transitions uncommitted candidates to `EXPIRED_WITHOUT_COMMIT`, and logs immutable governance audit events. |
| **Candidate Lifecycle Status** | **`PASS`** | Wiscon and Carver remain `BLOCKED_CUTOFF`. EAAA India Alternatives preserved as `EXPIRED_WITHOUT_COMMIT`. Mainboard candidates remain non-scoring `BLOCKED_GOVERNANCE`. |
| **Ledger Invariants** | **`PASS`** | All production ledgers remain strictly empty: 0 decision records, 0 outcome records, 0 evaluation records, 0 governance audit events. Notice collector and sweeper never create decisions or outcome records. |
| **Unit & Integration Tests** | **`PASS`** | 449 / 449 tests passing across 24 test suites (100% pass rate, 0 failures, 0 errors, 0 skipped). |
| **Predictive & Economic Validity** | **`INCONCLUSIVE`** | Exactly 0 mature prospective outcomes recorded (`INCONCLUSIVE_ZERO_OUTCOMES`). Zero live trades deployed (`INCONCLUSIVE_ZERO_LIVE_TRADES`). Real-money execution strictly prohibited. |

---

## 2. Immutable Frozen Artifact Verification

The frozen SME model binary and baseline manifest were verified directly via SHA-256 cryptographic hashing from the disk:
1. **Frozen SME Model v1 (`models/frozen/model_6b_sme_v1.joblib`)**:
   - SHA-256: `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76`
   - Verification: **`PASS` (Exact match)**
2. **Baseline Manifest (`models/frozen/phase_9b_baseline_manifest.json`)**:
   - SHA-256: `b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e`
   - Verification: **`PASS` (Exact match)**

No retraining, hyperparameter alteration, feature reorganization, or artifact replacement occurred.

---

## 3. Official Exchange Notice Collector (Phase 10.22A)

The collector was implemented in [`src/exchange_notice_collector.py`](file:///d:/personal/st-ai/ipo-record/src/exchange_notice_collector.py) with the following specifications:

- **Source Support**: Configurable endpoints for official BSE India and NSE India notices and public issue circulars.
- **Resilience & Timeouts**: Dedicated connect timeout (default 5.0s) and read timeout (default 10.0s) with up to 3 bounded retries using exponential backoff with jitter.
- **Payload Integrity**: Enforces strict response size limits (max 10 MB) to prevent denial-of-service from streaming overruns.
- **Raw Byte Retention**: Retains byte-for-byte unmodified raw responses under `data/raw_artifacts/notices` with SHA-256 checksum naming.
- **Deterministic Dependency Injection**: Exposes injectable `http_transport` and `clock_fn` parameters, allowing 100% offline, hermetic unit testing without relying on live web endpoints.
- **Fail-Closed Execution**: If an exchange endpoint times out, returns HTTP errors, or produces 0-byte responses, the failure is recorded in structured statistics (`TIMEOUT`, `HTTP_ERROR`, `FETCH_FAILED`) without falling back to unverified secondary portals.

---

## 4. Evidence Normalization & Authority Validation (Phase 10.22B & C)

The evidence ingestion pipeline in [`src/prospective_lifecycle.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_lifecycle.py) enforces:

1. **Cryptographic Byte Verification**: Computes the SHA-256 of the raw artifact bytes and verifies it against any declared document checksum.
2. **Temporal Consistency**: Requires timezone-aware timestamps (explicit `IST` or `+05:30`). Enforces $t_{\text{retrieval}} \ge t_{\text{publication}}$.
3. **Issue Type Discrimination**: Scans for debt, NCDs, bonds, and rights issues. If detected, governance audit event `EVIDENCE_REJECTED_WRONG_ISSUE_TYPE` is logged and cutoff remains unverified.
4. **Order-Book vs UPI Mandate Separation**: Rejects notices referencing only UPI mandate processing deadlines (`is_upi_only=True`), which do not establish retail individual order-book bidding close.
5. **Candidate Relevance Matching**: Requires candidate name, key constituent tokens, or symbol match in the circular text. Irrelevant notices fail with `IRRELEVANT_EVIDENCE`.
6. **Conflicting Evidence Detection**: Detects conflicting cutoff timestamps between existing registry entries and newly received notices, logging `CONFLICTING_CUTOFF_TIMES_DETECTED`.
7. **Idempotency**: Identical notice content deduplicates on `(ipo_id, artifact_sha256)` without creating duplicate governance audit entries.

---

## 5. Deadline Expiry Sweeper (Phase 10.22D)

Implemented `sweep_deadline_expiries(sweep_timestamp_ist)` in [`src/prospective_lifecycle.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_lifecycle.py):

- **Locking & Concurrency**: Acquires the inter-process file lock (`msvcrt.locking` on Windows, `fcntl.flock` on POSIX) before inspecting or mutating the candidate registry.
- **Boundary Policy**: Applies the exact cutoff rule: if $t_{\text{now}} \ge t_{\text{cutoff}}$, candidate transitions to `EXPIRED_WITHOUT_COMMIT`.
- **Under-Lock State Re-Check**: Validates the candidate's state under lock immediately prior to updating, ensuring that two concurrent sweepers do not duplicate transitions or events.
- **Governance Audit Logging**: Emits `CANDIDATE_DEADLINE_EXPIRED` into `governance_audit_events.jsonl` with previous record hash chaining.
- **No Retroactive Resurrecting**: Candidates in `EXPIRED_WITHOUT_COMMIT` cannot receive late evidence or be committed retroactively.

---

## 6. Daily Monitoring Report Enhancements (Phase 10.22E)

`generate_daily_monitoring_report()` in [`src/prospective_lifecycle.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_lifecycle.py) was expanded with standard operational sections:

- **Collection Health**: Status (`OPERATIONAL`), monitored sources (`BSE_SME`, `NSE_SME`), last collection run timestamp.
- **Evidence Health**: Count of verified primary notices (0), unverified asserted notices (2), conflicts (0), missing artifacts (0).
- **Candidate Lifecycle Summary**: Tracked candidates (6), verified cutoffs (0), asserted unverified cutoffs (2), blocked candidates (5), approaching cutoffs (2), expired candidates (1), mainboard coverage-only (3).
- **Persistence & Governance**: Exact record counts in decision, outcome, evaluation, and governance audit ledgers.
- **Ledger Invariance**: Strictly read-only; never mutates ledgers or creates records.

---

## 7. Tracked Candidates Status & Current Registry

| Candidate ID | Company Name | Segment | Asserted Cutoff (IST) | Verified Cutoff | Lifecycle State | Evidence Status | Eligible to Commit? |
|---|---|---|---|---|---|---|---|
| `wiscon-industries-sme-20261029` | Wiscon Industries Ltd | BSE SME | 2026-10-29 16:00:00 | Unverified | `BLOCKED_CUTOFF` | Secondary notice (`CHITTOR-01`) only; primary circular unacquired | **NO** (`BLOCKED`) |
| `carver-roboweld-sme-20261030` | Carver Roboweld Ltd | BSE SME | 2026-10-30 16:00:00 | Unverified | `BLOCKED_CUTOFF` | Secondary aggregate report only; primary circular unacquired | **NO** (`BLOCKED`) |
| `bls-polymers-mainboard-20261029` | BLS Polymers Ltd | Mainboard | 2026-10-29 17:00:00 | Unverified | `BLOCKED_GOVERNANCE` | Tracked for coverage only; Model 6B SME incompatible | **NO** (`BLOCKED`) |
| `sfc-environmental-mainboard-20261029` | SFC Environmental Tech Ltd | Mainboard | 2026-10-29 17:00:00 | Unverified | `BLOCKED_GOVERNANCE` | Tracked for coverage only; Model 6B SME incompatible | **NO** (`BLOCKED`) |
| `mk-sons-mainboard-20261030` | M. K. Sons Fine Jewels Ltd | Mainboard | 2026-10-30 17:00:00 | Unverified | `BLOCKED_GOVERNANCE` | Tracked for coverage only; Model 6B SME incompatible | **NO** (`BLOCKED`) |
| `eaaa-india-mainboard-20261028` | EAAA India Alternatives Ltd | Mainboard | 2026-10-28 17:00:00 | Elapsed (Unverified) | `EXPIRED_WITHOUT_COMMIT` | Cutoff elapsed without primary circular or commit | **NO** (`EXPIRED`) |

---

## 8. Operational Scheduling and Windows Task Scheduler (Phase 10.22F)

The collector and sweeper are callable as independent CLI operations. To automate regular polling without introducing complex runtime dependencies, the recommended setup uses Windows Task Scheduler:

### Windows Task Scheduler Configuration
1. **Notice Ingestion Task**:
   - Program: `D:\personal\st-ai\ipo-record\.venv\Scripts\python.exe`
   - Arguments: `-c "from src.exchange_notice_collector import ExchangeNoticeCollector; c = ExchangeNoticeCollector(); c.fetch_exchange_notices('BSE'); c.fetch_exchange_notices('NSE')"`
   - Trigger: Every 15 minutes between 09:00 IST and 17:30 IST on trading days.
   - Settings: "Do not start a new instance if already running" (guaranteed by process file locking).
2. **Deadline Expiry Sweeper Task**:
   - Program: `D:\personal\st-ai\ipo-record\.venv\Scripts\python.exe`
   - Arguments: `-c "from src.prospective_lifecycle import ProspectiveLifecycleManager; mgr = ProspectiveLifecycleManager(); mgr.sweep_deadline_expiries()"`
   - Trigger: Every 5 minutes between 15:30 IST and 17:30 IST on trading days.
   - Settings: "Do not start a new instance if already running".

---

## 9. Adversarial Test Suite Execution (Phase 10.22)

A dedicated adversarial test suite ([`tests/test_phase_10_22_notice_and_expiry.py`](file:///d:/personal/st-ai/ipo-record/tests/test_phase_10_22_notice_and_expiry.py)) covering 35 scenarios was implemented and executed:

| Test ID | Test Scenario | Verified Condition | Result |
|---|---|---|---|
| `test_01` | Valid primary exchange notice | Official circular unblocks cutoff | **`PASS`** |
| `test_02` | Secondary-source notice rejection | Secondary portal rejected | **`PASS`** |
| `test_03` | Irrelevant notice type | NCD / debt circular rejected | **`PASS`** |
| `test_04` | UPI-only deadline rejection | UPI mandate cutoff rejected | **`PASS`** |
| `test_05` | Incorrect candidate match | Circular for different company rejected | **`PASS`** |
| `test_06` | Ambiguous candidate match | Missing identifiers rejected | **`PASS`** |
| `test_07` | Missing source artifact | Empty raw bytes rejected | **`PASS`** |
| `test_08` | Artifact SHA-256 mismatch | Hash mismatch rejected | **`PASS`** |
| `test_09` | Publication timestamp missing | Missing pub timestamp flagged | **`PASS`** |
| `test_10` | Naive timestamp rejection | Naive timestamps rejected | **`PASS`** |
| `test_11` | Conflicting primary evidence | Conflicting cutoff warning logged | **`PASS`** |
| `test_12` | Duplicate notice ingestion | Deduplicates governance events | **`PASS`** |
| `test_13` | Notice retrieved after cutoff | Ingestion after expiry rejected | **`PASS`** |
| `test_14` | Notice published after decision | Inconsistent chronology rejected | **`PASS`** |
| `test_15` | Collector timeout | Timeout handled, fails closed | **`PASS`** |
| `test_16` | Collector HTTP error | Non-200 HTTP codes handled | **`PASS`** |
| `test_17` | Collector malformed response | Size overruns detected | **`PASS`** |
| `test_18` | Collector retry exhaustion | Halts after max retries | **`PASS`** |
| `test_19` | Collector empty response | 0-byte responses rejected | **`PASS`** |
| `test_20` | Expiry immediately before cutoff | $t_{\text{cutoff}} - 1\text{s}$ remains active | **`PASS`** |
| `test_21` | Expiry exactly at cutoff | $t_{\text{cutoff}}$ transitions to EXPIRED | **`PASS`** |
| `test_22` | Expiry immediately after cutoff | $t_{\text{cutoff}} + 1\text{s}$ transitions to EXPIRED | **`PASS`** |
| `test_23` | Repeated expiry sweep | Idempotent transitions | **`PASS`** |
| `test_24` | Concurrent expiry sweep | ThreadPoolExecutor serializes safely | **`PASS`** |
| `test_25` | Restart after expiry | Restart preserves expired state | **`PASS`** |
| `test_26` | Registry corruption | Malformed registry fails safely | **`PASS`** |
| `test_27` | Late evidence for expired candidate | Post-expiry evidence rejected | **`PASS`** |
| `test_28` | Blocked candidate remains blocked | Unverified stays BLOCKED_CUTOFF | **`PASS`** |
| `test_29` | Mainboard candidate non-scoring | SME model ineligible for Mainboard | **`PASS`** |
| `test_30` | No decision creation by collector | Ledger count remains 0 | **`PASS`** |
| `test_31` | No outcome creation by sweeper | Ledger count remains 0 | **`PASS`** |
| `test_32` | No retroactive commitment | Expired candidate blocked from commit | **`PASS`** |
| `test_33` | Monitoring report does not mutate | Read-only check passes | **`PASS`** |
| `test_34` | Frozen artifacts hash verification | Model and manifest match exact SHA | **`PASS`** |
| `test_35` | Sweeper invalid timezone check | Naive sweep timestamps rejected | **`PASS`** |

**Full Discovery Suite Execution**:
- Total tests executed: **449**
- Test suites: **24**
- Failures: **0**
- Errors: **0**
- Skipped: **0**
- Runtime: **15.583s**
- Status: **`OK`**

---

## 10. Modified Files & Unresolved Risks

### Modified / Created Files
1. [`src/exchange_notice_collector.py`](file:///d:/personal/st-ai/ipo-record/src/exchange_notice_collector.py): Implemented official exchange notice collector adapter.
2. [`src/prospective_lifecycle.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_lifecycle.py): Added `sweep_deadline_expiries()`, extended `generate_daily_monitoring_report()`, and hardened non-equity issue rejection.
3. [`tests/test_phase_10_22_notice_and_expiry.py`](file:///d:/personal/st-ai/ipo-record/tests/test_phase_10_22_notice_and_expiry.py): Implemented 35-test adversarial verification suite.
4. [`reports/phase_10_22_official_notice_ingestion_deadline_monitoring_audit.md`](file:///d:/personal/st-ai/ipo-record/reports/phase_10_22_official_notice_ingestion_deadline_monitoring_audit.md): Comprehensive Phase 10.22 audit report.

### Unresolved Operational Risks
1. **Live Exchange Anti-Bot Protection**: Live exchange websites (BSE / NSE) periodically update CAPTCHA, Cloudflare, or Akamai anti-bot measures on circular listings. Real production polling must maintain appropriate session headers and fallback to official notice archive downloads.
2. **Wiscon & Carver Imminent Expiry**: Wiscon Industries cutoff is asserted as 2026-10-29 16:00 IST. If authoritative primary evidence is not acquired before this deadline, the sweeper will transition it to `EXPIRED_WITHOUT_COMMIT`.
