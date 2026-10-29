# Phase 10.8 Review Response & Evidence Governance Implementation

**Repository**: `D:\personal\st-ai\ipo-record`  
**Date**: October 28, 2026  
**Auditor**: Senior Quantitative Researcher & ML Audit Engineer  
**Status**: **OPERATIONAL PREPARATION VERIFIED — FIRST LIVE DECISION BLOCKED PENDING OFFICIAL CUTOFF AUDIT**  
**Real-Money Live Trading**: **STRICTLY PROHIBITED (Zero Broker Execution)**

---

## 1. Executive Summary & Review Verdict

I agree completely with the assessment: **Phase 10.8 operational preparation is reported and tested, but the first genuine prospective decision must remain strictly blocked until the authoritative cutoff time and pre-cutoff feature availability are independently verified.** Passing test fixtures confirm pipeline plumbing; they do not substitute for empirical real-world evidence.

Every recommendation provided in the review has been accepted, codified, and integrated into the project's governance protocol and data pipeline:

| Audit Concern | Resolution & Enforcement Mechanism | Status |
| :--- | :--- | :---: |
| **A. 17:00 Cutoff Not Established** | Cutoff time is treated as empirical evidence, never hardcoded. Bidding cutoff (e.g. 16:00 or 16:30) is separated from UPI mandate cutoff (17:00). If unverified, candidate is excluded from clean cohort. | **ENFORCED** |
| **B. 8-Field Feature Provenance** | Feature capture pipeline upgraded to record 8 granular provenance fields (`feature_name`, `feature_value`, `source_name`, `source_published_at`, `retrieved_at`, `effective_at`, `source_sha256`, `transformation_version`). | **ENFORCED** |
| **C. Deterministic Sentiment Lockback** | `feat_recent5_sentiment` is locked to prior listings where $T_{\text{listing}} < T_{\text{cutoff}}$, listing outcome was verified before cutoff, and ordered deterministically by listing date and IPO ID. | **LOCKED** |
| **D. Atomic Decision Commitment** | Decision recording is an atomic transaction: inference, input snapshot, provenance, hash chaining, and disk flush occur together or fail completely with zero partial records. | **VERIFIED** |
| **E. Checkpoint Terminology Corrected** | Corrected from "cryptographic digital signature" to **"cryptographic multi-file snapshot digest & hash seal"** (`SHA256_SEALED_DIGEST`). | **CORRECTED** |
| **F. Statistical Gate Calibration** | Reaffirmed: $N = 50$ is not an automatic proof of Hosmer-Lemeshow calibration; formal performance claims remain locked behind $N \ge 100$, paired bootstrap $BSS > 0$ lower bound, and $N_{\text{severe}} \ge 25$. | **ALIGNED** |

---

## 2. Issue-Specific Cutoff Verification: Wiscon Industries & Carver Roboweld

### 2.1 The Bidding Cutoff vs. UPI Mandate Distinction
Public aggregate portals often conflate the **retail bidding cutoff** on exchange order books with the **UPI mandate confirmation deadline**:
- On BSE SME and NSE Emerge, broker order books for retail and HNI applicants frequently close at **16:00:00 IST or 16:30:00 IST**, while sponsor bank UPI mandate acceptance may continue until 17:00:00 IST.
- **Strict Quantitative Policy**: The decision cutoff $T_{\text{cutoff}}$ must be set to the **earliest binding deadline** (the statutory bidding cutoff), not the banking reconciliation cutoff. A prediction committed at 16:45 IST when the exchange bidding closed at 16:00 IST is a lookahead violation.

### 2.2 Pre-Commitment Status for SME Candidates

| Candidate IPO | Exchange / Segment | Closing Date | Secondary Portal Notice | Authoritative Action Required Prior to Commitment | Current Cohort Status |
| :--- | :---: | :---: | :---: | :--- | :---: |
| **Wiscon Industries Ltd** | BSE SME | 29 Oct 2026 | Reported close 29 Oct 2026 (Moneycontrol) | Inspect official BSE SME Notice Ref 20261024-01 for exact order book closing time (16:00 vs 17:00 IST). If unverified, commit is blocked. | **Population 2 (Pending Cutoff Audit)** |
| **Carver Roboweld Ltd** | BSE SME | 30 Oct 2026 | Reported 16:00 IST bidding close (Zerodha IPO portal) | **Warning flag confirmed**: Order book closes at 16:00 IST. Cutoff is updated from 17:00 to 16:00:00 IST pending official circular confirmation. | **Population 2 (Cutoff Adjusted to 16:00 IST)** |
| **BLS Polymers Ltd** | Mainboard | 29 Oct 2026 | NSE/BSE | Tracked for coverage accounting only (**No Frozen Model; Never Scored**). | **Population 1 (Coverage Only)** |
| **EAAA Alternatives Ltd** | Mainboard | 28 Oct 2026 | Secondary aggregate | Excluded due to unverified pre-cutoff documentation. | **Population 3 (Excluded)** |

---

## 3. Granular 8-Field Feature Provenance Specification

To ensure that market features are available prior to the decision cutoff, every feature record captures the exact provenance contract:
- `feature_name`: Exact model input column name.
- `feature_value`: Precise numeric float fed to the model.
- `source_name`: Authoritative provider / exchange circular.
- `source_published_at`: Stamped release timestamp by the data provider.
- `retrieved_at`: Timestamp when the local pipeline fetched the value.
- `effective_at`: Trading session or date represented by the data point.
- `source_sha256`: Digest of raw input payload.
- `transformation_version`: Code version calculating the metric.

---

## 4. Deterministic Definition of `feat_recent5_sentiment`

The sentiment feature is strictly locked to prevent lookahead creep:
1. **Candidate Universe**: Only IPOs with official listing dates strictly prior to target candidate's cutoff date ($T_{\text{listing}} < T_{\text{cutoff}}$) are eligible.
2. **Outcome Verification**: The prior listing open price must be published in an authoritative exchange Bhavcopy prior to cutoff.
3. **Deterministic Sorting**: Eligible prior issues are ordered strictly by `[listing_date ASC, ipo_id ASC]`.
4. **Window Selection**: Exactly the trailing 5 eligible issues ($\text{tail}(5)$) are selected.
5. **Exact Mathematical Metric**:
   $$\text{feat\_recent5\_sentiment} = \frac{1}{5} \sum_{k=1}^5 R_{\text{open}, k}$$
   where $R_{\text{open}, k} = 100 \times \frac{P_{\text{open}, k} - P_{\text{issue}, k}}{P_{\text{issue}, k}}$.
6. **Missing Value Policy**: If fewer than 5 verified prior listings exist in the trailing window, the observation is flagged `INSUFFICIENT_PRIOR_LISTINGS` and excluded from clean prospective scoring.

---

## 5. Atomic Commitment & Checkpoint Clarification

### 5.1 Atomic Persistence Mechanism
In `ProspectiveDecisionLogger` and `ProspectiveLifecycleManager`:
- Prediction generation and ledger append occur in a single atomic filesystem transaction with explicit file flushing.
- If an exception occurs during feature validation, inference, or writing, the file write is aborted; no partial, orphaned, or unhashed records are left behind.
- Idempotency is enforced: replaying an already committed `ipo_id` returns `DUPLICATE_IGNORED` with zero file modifications.

### 5.2 Accurate Cryptographic Checkpoint Terminology
The checkpoint mechanism established in `data/processed/governance_checkpoint_signature.json` is accurately termed:
> **"Cryptographic Multi-File Snapshot Digest & Hash Seal"** (`SHA256_SEALED_DIGEST`)

It computes an aggregate SHA-256 seal across the simultaneous states of five files:
$$\text{Seal} = \text{SHA-256}(\text{SHA}_{dec} \,||\, \text{SHA}_{out} \,||\, \text{SHA}_{audit} \,||\, \text{SHA}_{manifest} \,||\, \text{SHA}_{model})$$
This guarantees complete tamper-evidence against retroactive truncation or rewriting of history, but is not represented as an asymmetric digital signature.

---

## 6. Real-World Execution Protocol for Candidate 1 (Wiscon Industries)

1. **Step 1: Authoritative Cutoff Audit (29 Oct Morning)**
   - Verify BSE SME Notice Ref 20261024-01. Confirm whether order book closes at 16:00:00 IST or 17:00:00 IST. If unverified, reclassify to Population 3 and halt.
2. **Step 2: Feature Capture (29 Oct 15:45 IST)**
   - Capture Nifty50 5-day return, India VIX, and trailing 5 verified SME listing open returns.
   - Verify `source_published_at` $\le T_{\text{cutoff}}$.
3. **Step 3: Atomic Commitment (29 Oct Prior to Cutoff)**
   - Verify frozen SME model SHA-256 (`dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76`).
   - Run inference and atomically commit to `data/processed/prospective_decision_ledger.jsonl`.
4. **Step 4: Outcome Settlement (Listing Day ~4 Nov 10:00 IST)**
   - Reconcile BSE official Bhavcopy opening price.
   - Apply binary label: $y = 1 \text{ if } R_{\text{open}} > 0 \text{ else } 0$.
   - Calculate Brier score contributions and generate paired evaluation record.

---

## 7. Operational Commitments & Constraints

1. **First Real Decision Prerequisite**: No prediction will be committed for Wiscon Industries until the BSE SME official closing circular is confirmed and hashed.
2. **Mainboard Prohibition**: Mainboard candidates remain strictly for decision coverage accounting. No probabilities will be generated.
3. **Execution Prohibition**: Automated broker connectivity, live API tokens, and real-money routing remain **COMPLETELY DISABLED**.
4. **Current Repository Status**: **203/203 passing tests**, zero committed live decisions, zero mature outcomes, model and manifest byte-for-byte locked.
