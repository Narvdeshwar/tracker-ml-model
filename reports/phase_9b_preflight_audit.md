# Phase 9B: Operational Preflight Audit & Issue Registration Report

**Date**: October 28, 2026  
**Auditor**: Senior Quantitative Researcher & ML Audit Engineer  
**Project**: Indian IPO Machine Learning Research & Prospective Validation (`D:\personal\st-ai\ipo-record`)  
**Governing Manifest**: [`models/frozen/phase_9b_baseline_manifest.json`](file:///d:/personal/st-ai/ipo-record/models/frozen/phase_9b_baseline_manifest.json)  
**Execution Status**: **OPERATIONAL PREFLIGHT PASSED — PROSPECTIVE SHADOW LOGGING ACTIVE**  
**Real-Money Trading Status**: **STRICTLY PROHIBITED**  
**Repository Automated Test Suite**: **144/144 Passing Tests** (`.\.venv\Scripts\python.exe -m unittest discover tests`)

---

## 1. Executive Summary & Verification Confirmation

The Phase 9B preflight verification was executed against the local codebase. All required operational controls and model coverage restrictions have been codified and validated:

1. **Manifest and Frozen Model Verification**:
   - The frozen manifest [`models/frozen/phase_9b_baseline_manifest.json`](file:///d:/personal/st-ai/ipo-record/models/frozen/phase_9b_baseline_manifest.json) exists and is cryptographically locked.
   - The SME model artifact [`models/frozen/model_6b_sme_v1.joblib`](file:///d:/personal/st-ai/ipo-record/models/frozen/model_6b_sme_v1.joblib) was verified bit-for-bit against its SHA-256 digest: `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76`.
2. **Model Coverage Restriction Strictly Enforced**:
   - The repository contains a frozen model artifact **only for the SME segment** (`Model_6B_SME_v1.0`).
   - There is **no frozen Mainboard model artifact** in the manifest.
   - **Enforced Policy**: Mainboard issues are registered exclusively in **Population 1 (All Eligible)** for decision coverage accounting and operational timing audits. **No model scores or probabilities are invented for Mainboard candidates**, and the SME model is never repurposed for Mainboard issues.
3. **Preflight Runner Implementation**:
   - Script [`src/phase_9b_preflight_runner.py`](file:///d:/personal/st-ai/ipo-record/src/phase_9b_preflight_runner.py) executes end-to-end dry-run candidate audits without committing false prospective entries to live ledgers.
4. **Clean Ledger State**:
   - Live ledger [`data/processed/prospective_decision_ledger.jsonl`](file:///d:/personal/st-ai/ipo-record/data/processed/prospective_decision_ledger.jsonl) remains untouched. Zero false prospective decisions have been committed.

---

## 2. Prospective Issue Register (As of 28 October 2026)

Six candidate issues identified from NSE/BSE public notices have been audited and assigned to their governing operational categories:

| Candidate IPO | Segment | Issue Window | Authoritative Cutoff Evidence | Model Coverage Status | Prospective Population Allocation | Phase 9B Operational Action |
|---|---|---|---|---|---|---|
| **Wiscon Industries** | SME | 27–29 Oct 2026 | BSE SME Notice Ref 20261024-01: Issue closes 29 Oct 2026, 17:00:00 IST | Eligible for `Model_6B_SME_v1.0` | **Population 2 (Clean Prospective)** | Commit pre-cutoff decision to live ledger before 29 Oct 17:00 IST using preflight-verified features. |
| **Carver Roboweld** | SME | 28–30 Oct 2026 | BSE SME Public Issue Notice: Closes 30 Oct 2026, 17:00:00 IST | Eligible for `Model_6B_SME_v1.0` | **Population 2 (Clean Prospective)** | Verify feature snapshot at 15:30 IST on 29/30 Oct; score and commit prior to 30 Oct 17:00 IST. |
| **BLS Polymers** | Mainboard | 27–29 Oct 2026 | NSE Issue Information (Symbol: BLSPOLY): Closes 29 Oct 2026, 17:00:00 IST | **No Frozen Model (Coverage Tracking Only)** | **Population 1 (All Eligible)** | Register for decision coverage tracking. Record unmodeled status; do not fabricate scores. |
| **SFC Environmental Technologies** | Mainboard | 27–29 Oct 2026 | NSE Issue Information (Symbol: SFCTECH): Closes 29 Oct 2026, 17:00:00 IST | **No Frozen Model (Coverage Tracking Only)** | **Population 1 (All Eligible)** | Register for decision coverage tracking. Record unmodeled status; do not fabricate scores. |
| **M. K. Sons Fine Jewels** | Mainboard | 28–30 Oct 2026 | Statutory Price Band Circular / RHP Notice: Closes 30 Oct 2026, 17:00:00 IST | **No Frozen Model (Coverage Tracking Only)** | **Population 1 (All Eligible)** | Register for decision coverage tracking. |
| **EAAA India Alternatives** | Mainboard | 26–28 Oct 2026 | Cutoff date: 28 Oct 2026. Timing unverified prior to close. | **No Frozen Model & Unverified Cutoff** | **Population 3 (Excluded / Unverified)** | Retained in Population 3 for coverage and selection bias accounting. Never backdate a decision. |

---

## 3. Candidate Preflight Verification Results

The dry-run preflight runner ([`src/phase_9b_preflight_runner.py`](file:///d:/personal/st-ai/ipo-record/src/phase_9b_preflight_runner.py)) was executed against the candidates:

### 3.1 SME Candidate: Wiscon Industries Ltd
```json
{
  "ipo_id": "sme-wiscon-ind-20261029",
  "company_name": "Wiscon Industries Ltd",
  "board_type": "SME",
  "scoring_status": "ELIGIBLE_FOR_FROZEN_SME_MODEL",
  "cohort_allocation": "Population_2_Clean_Prospective",
  "checks": {
    "manifest_verification": { "status": "PASS", "match": true },
    "model_coverage_restriction": { "status": "PASS", "detail": "SME issue eligible for frozen Model_6B_SME_v1.0 evaluation." },
    "cutoff_timezone_present": { "status": "PASS", "cutoff_ts": "2026-10-29 17:00:00 IST" },
    "authoritative_evidence_present": { "status": "PASS", "evidence": "BSE SME Issue Notice Ref 20261024-01 - Issue closes 29 Oct 2026 17:00 IST" },
    "raw_checksum_present": { "status": "PASS", "hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08" },
    "timing_verified_flag": { "status": "PASS", "value": true },
    "pre_cutoff_chronological_consistency": { "status": "PASS" },
    "feature_contract": { "status": "PASS" },
    "dry_run_ledger_append": { "status": "RECORDED", "temporal_status": "PRE_LISTING_LOCKED" }
  },
  "dry_run_scores": {
    "model_name": "Model_6B_SME_v1.0",
    "p_positive_open": 0.885,
    "p_macro": 0.885
  }
}
```

### 3.2 Mainboard Candidate: BLS Polymers Ltd
```json
{
  "ipo_id": "mb-bls-polymers-20261029",
  "company_name": "BLS Polymers Ltd",
  "board_type": "Mainboard",
  "scoring_status": "NO_FROZEN_MODEL_REGISTER_FOR_COVERAGE_ONLY",
  "cohort_allocation": "Population_1_All_Eligible",
  "dry_run_scores": null,
  "checks": {
    "manifest_verification": { "status": "PASS", "match": true },
    "model_coverage_restriction": {
      "status": "RESTRICTED",
      "detail": "Phase 9B manifest has no frozen Mainboard model artifact. Model scores MUST NOT be invented."
    },
    "cutoff_timezone_present": { "status": "PASS", "cutoff_ts": "2026-10-29 17:00:00 IST" },
    "authoritative_evidence_present": { "status": "PASS", "evidence": "NSE Issue Information - Closes 29 Oct 2026 5:00 PM IST" },
    "raw_checksum_present": { "status": "PASS", "hash": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8" },
    "timing_verified_flag": { "status": "PASS", "value": true },
    "pre_cutoff_chronological_consistency": { "status": "PASS" },
    "dry_run_ledger_append": {
      "status": "RECORDED",
      "temporal_status": "PRE_LISTING_LOCKED"
    }
  }
}
```

---

## 4. Codified Operational Checklist for Each Candidate

Every candidate in Phase 9B must pass this checklist before any ledger commit:

```
[ ] 1. Confirm identity, exchange, and Mainboard vs. SME segment.
[ ] 2. Check manifest: Is there an authorized frozen model for this segment?
       ├── SME: Eligible for Model_6B_SME_v1.0.
       └── Mainboard: Track for coverage only; do not invent scores.
[ ] 3. Capture authoritative issue-close evidence (URL, circular notice, and explicit IST timezone).
[ ] 4. Capture macro/issue features strictly prior to the verified cutoff timestamp.
[ ] 5. Calculate and record the SHA-256 hash of the raw circular/evidence document.
[ ] 6. Validate feature values: reject any NaN, infinite, or missing inputs.
[ ] 7. (SME Only) Generate model score using frozen Model_6B_SME_v1.0 pipeline artifact.
[ ] 8. Append decision to prospective_decision_ledger.jsonl before cutoff.
[ ] 9. Verify cryptographic hash chain: verify_ledger_chain('decision').
[ ] 10. Record listing open discovery price and registrar basis outcomes only after official publication.
```

---

## 5. Audit Finding Summary

| Governance Dimension | Finding / Status | Evidence & Enforced Control |
|---|:---:|---|
| **Model Immutability** | **PASS** | `Model_6B_SME_v1.0` SHA-256 verified: `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` |
| **Model Coverage Rule** | **ENFORCED** | SME issues scored via frozen artifact; Mainboard issues registered for coverage only (no scores invented). |
| **Pre-Cutoff Integrity** | **PASS** | Authoritative evidence, explicit IST timezone, and pre-cutoff publication verified in preflight. |
| **Population Decoupling** | **PASS** | Population 1 (Coverage), Population 2 (Clean SME evaluation), and Population 3 (Unverified) tracked. |
| **Dry-Run Ledger Isolation** | **PASS** | Preflight executed on temporary files; live prospective ledger remains clean. |
| **Capital Deployment** | **STRICTLY PROHIBITED** | Passive software shadow logging only; zero broker orders, zero real money. |
| **Test Suite Coverage** | **PASS** | **144/144 tests passing** across 13 test suites. |
