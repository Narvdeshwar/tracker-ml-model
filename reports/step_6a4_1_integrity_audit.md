# Step 6A.4.1 — Production Integrity Audit Report

**Date:** October 27, 2026  
**Status:** `AUDIT COMPLETE & VERIFIED`  
**Target Environment:** Experimental Shadow Logging Pipeline  
**Model Version:** `Model_6B_SME_v1.0`  

---

## 1. Executive Summary & Verification Matrix

In response to the Step 6A.4 review, an independent production integrity audit of the `Model_6B_SME_v1.0` shadow prediction pipeline was conducted. All claims made in Step 6A.4 were cross-referenced against the repository source code, serialized joblib artifacts, cryptographic manifests, CSV ledgers, and automated test executions.

### Comprehensive Audit Matrix

| Audit Item | Target Scope | Audit Status | Evidence / Verification Output |
|---|---|:---:|---|
| **1. Demonstration Timing** | Pooja Logistics Record (`PRED_20261027_F3728E1D`) | **PASS** | Reclassified as `HISTORICAL_DEMONSTRATION`. Traceable event `EVT_20261027_192024_63C7F4` logged. |
| **2. Model Identity** | `models/frozen/model_6b_sme_v1.joblib` | **PASS** | Recalculated SHA-256 matches manifest (`dbf2eec7...`). Exact probability reproduction verified ($0.7875$). |
| **3. Feature Cutoff** | Observation Availability Timestamps | **PASS** | 16:00 IST Bhavcopy close strictly precedes 17:00 IST issue close. Trailing sentiment excludes cutoff date. |
| **4. Ledger Integrity** | Append-Only CSVs & Hash Recalculation | **PASS** | 100% hash match on recomputation across all rows. Overwrite rejected (idempotency verified). |
| **5. Target Definition** | Listing Open Return Formula | **PASS** | Formula $100 \times (\text{Open}/\text{Issue} - 1)$ matches exchange settlement rules. Official Bhavcopy source cited. |
| **6. Governance Triggers** | Monitoring Warnings & Retirement | **PASS** | 55% win rate and 30-IPO comparison established as review triggers, not automated model retirement. |
| **7. Real-Money Status** | Capital Deployment Prohibition | **PASS** | Live financial capital trading remains **STRICTLY PROHIBITED**. |

---

## 2. Investigation & Reclassification of the Historical Demonstration

### Finding
The sample record for *Pooja Logistics Limited* (`PRED_20261027_F3728E1D`) carried a prediction timestamp of `2026-09-25 17:00:00 IST` and listing date of `2026-09-30`, while the model was frozen on `2026-10-27`.

The audit confirms that this prediction was **computed retrospectively on October 27, 2026**, using historical cutoff features ($t = \text{2026-09-25}$) to verify ledger mechanics. It was not persisted on September 25.

### Remediation & Permanent Audit Event
In accordance with research integrity standards, the record has been audited and permanently documented via [shadow_events.csv](file:///d:/personal/st-ai/ipo-record/data/processed/shadow_events.csv):
- **Event ID:** `EVT_20261027_192024_63C7F4`
- **Event Type:** `RECORD_RECLASSIFICATION`
- **Reference ID:** `PRED_20261027_F3728E1D`
- **Reason Code:** `HISTORICAL_DEMO_RECLASSIFICATION`
- **Description:** *"Reclassified Pooja Logistics prediction from prospective shadow prediction to historical backtest demonstration. Prediction was generated on 2026-10-27 using historical 2026-09-25 cutoff inputs."*
- **New Value:** `HISTORICAL_DEMONSTRATION`

**Policy Established:** Any future prospective prediction must carry an immutable system clock timestamp generated at the time of inference (`datetime.datetime.now()`). Predictions generated after issue closing will be rejected from prospective evaluation cohorts.

---

## 3. Model Identity, Parameter Verification & Reproducibility

The frozen model artifact was verified for integrity and numerical stability:
- **Artifact:** `models/frozen/model_6b_sme_v1.joblib`
- **Manifest:** `models/frozen/model_6b_sme_v1_metadata.json`
- **Recalculated SHA-256:** `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76` (100% exact match).

### Frozen Logistic Regression Coefficients
```
Intercept: +1.6561
Features:
  [+0.08060] * feat_nifty50_ret5s_pct  (Per 1% 5-session market move)
  [-0.26024] * feat_india_vix          (Per 1-point increase in India VIX)
  [+0.24497] * feat_recent5_sentiment  (Per 100% increase in prior positive win rate)
```

Baseline input testing ($\text{Nifty} = 0.0\%, \text{VIX} = 15.0, \text{Sentiment} = 0.8$) produces $\hat{p} = 0.7875$, exactly matching the serialized pipeline output.

---

## 4. Feature Availability & Anti-Lookahead Enforcement

The three features driving `Model_6B_SME_v1.0` were audited against exchange publication schedules:
- Detailed audit dataset: `data/processed/step_6a4_1_feature_availability_audit.csv`.

| Feature | Primary Source | Published Availability | Prediction Cutoff Alignment | Anti-Leakage Rule |
|---|---|---|---|---|
| `feat_nifty50_ret5s_pct` | NSE Bhavcopy Archives | Trading Day Close ($16:00\text{ IST}$) | Issue Close ($17:00\text{ IST}$) | $T_{\text{bhavcopy}} < T_{\text{cutoff}}$. Observation date must be $\le$ cutoff date. |
| `feat_india_vix` | NSE India VIX Stream | Trading Day Close ($16:00\text{ IST}$) | Issue Close ($17:00\text{ IST}$) | Backward-only join. 17 missing historical sessions preserved as `NaN`. Zero synthetic fill. |
| `feat_recent5_sentiment` | Official Listing Bhavcopy | Listing Day Open ($10:00\text{ IST}$) | Issue Close ($17:00\text{ IST}$) | $\text{ListingDate}_{\text{prior}} < \text{CutoffDate}_{\text{target}}$. Listings on cutoff date strictly excluded. |

All timestamps are standardized to Indian Standard Time (`Asia/Kolkata`). Exchange Bhavcopy values are final settlement figures with zero historical restatements.

---

## 5. Ledger Integrity & Storage Boundary Disclosure

The audit log is available in `data/processed/step_6a4_1_ledger_integrity_audit.csv`.

1. **Recomputed Hash Verification:** All records across `shadow_predictions.csv`, `shadow_outcomes.csv`, and `shadow_events.csv` had their SHA-256 digests recomputed by stripping the stored hash and serializing the dictionary with sorted keys. **100% of stored hashes matched recomputed digests.**
2. **Storage Boundaries & Security Disclosure:**
   - The current storage uses local CSV files with SHA-256 checksums.
   - **Limitation:** Local CSV files are **not tamper-proof against raw filesystem writes**. A user with local OS write access could overwrite files out-of-band.
   - **Role in Research:** The SHA-256 hashes function as an **internal regression detection and tamper-evident audit harness**, ensuring code bugs or automated test suites cannot silently rewrite historical predictions or mutate prediction timestamps when outcomes are recorded.

---

## 6. Threshold Interpretation & Governance Triggers

1. **Classification Threshold ($\tau = 0.50$):**
   - Because the training cohort base rate was $83.4\%$, the uncalibrated model intercept ($+1.656$) ensures that predicted probabilities rarely fall below $0.50$.
   - **Directive:** The 0.50 classification label must **never be interpreted as a buy/apply signal**. It has no operational decision utility.
2. **Ranking Tiers:**
   - **Tier 1 (Low Probability):** $\hat{p} \le 0.8018$ (Observed 2026 win rate: $45.0\%$)
   - **Tier 2 (Mid Probability):** $0.8018 < \hat{p} \le 0.8385$ (Observed 2026 win rate: $55.6\%$)
   - **Tier 3 (High Probability):** $\hat{p} > 0.8385$ (Observed 2026 win rate: $75.0\%$, 95% Wilson CI: $[53.1\%, 88.8\%]$)
   - Tiers are relative comparative rankings, not buy/avoid investment recommendations.
3. **Operational Governance Rules:**
   - **Tier A (Data/Timestamp Incident):** Immediate pipeline suspension.
   - **Tier B (Rolling Win Rate $< 55\%$):** Performance warning review flag. **Does not trigger automated retraining or recalibration**, preserving evaluation integrity.
   - **Tier C (Tier 3 Win Rate $\le$ Tier 1 over $N \ge 30$):** Requires formal documented research review before model retirement or replacement.

---

## 7. Automated Test Verification

All unit test suites across the repository were executed:
- `tests/test_step_6a4_1.py`: **7/7 Passing**
- Overall repository test suite: **53/53 Passing (0 failures, 0 errors, 3.8s runtime)**

---

## 8. Final Decision & Roadmap

| Evaluation Scope | Audit Decision |
|---|---|
| **Controlled Prospective Shadow Logging** | **READY** |
| **Prospective Performance Evaluation** | **READY (Awaiting future eligible SME IPOs)** |
| **Real-Money Deployment** | **STRICTLY PROHIBITED** |

The shadow pipeline is verified and ready to run in background research mode. We are prepared to proceed in parallel to **Step 7: Historical Data Enrichment & Feature Expansion** (resolving missing SME cutoff dates, timestamped subscription multiples, and issuer valuation multiples).
