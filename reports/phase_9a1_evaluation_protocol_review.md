# Phase 9A.1: Prospective Evaluation Protocol & Benchmark Review

**Audit Date**: October 28, 2026  
**Auditor**: Senior Quantitative Researcher & ML Audit Engineer  
**Project**: Indian IPO Machine Learning Research & Prospective Validation  
**Target Repository**: `D:\personal\st-ai\ipo-record`  
**Governing Documents**:
- Phase 9 Evaluation Protocol: [`reports/phase_9_evaluation_protocol.md`](file:///d:/personal/st-ai/ipo-record/reports/phase_9_evaluation_protocol.md)
- Phase 9A Pre-Launch Audit: [`reports/phase_9a_prelaunch_audit.md`](file:///d:/personal/st-ai/ipo-record/reports/phase_9a_prelaunch_audit.md)
- Frozen SME Model: [`models/frozen/model_6b_sme_v1.joblib`](file:///d:/personal/st-ai/ipo-record/models/frozen/model_6b_sme_v1.joblib) (SHA-256: `dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76`)
- Evaluator Engine: [`src/prospective_simulator_logger.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_simulator_logger.py)
- Protocol Review Test Suite: [`tests/test_phase_9a1_protocol_review.py`](file:///d:/personal/st-ai/ipo-record/tests/test_phase_9a1_protocol_review.py)

---

## Executive Summary & Final Verdict

### Final Status: **READY WITH DOCUMENTED LIMITATIONS (OPERATIONAL SHADOW LOGGING ONLY)**

> [!CAUTION]
> **Strict Capital Deployment Prohibition**: Live broker integration, automated order execution, client-facing signal generation, and real-money trading remain **100% strictly prohibited**. The system is authorized exclusively for passive, pre-cutoff prospective shadow logging in software ledgers.

This audit executes a line-by-line verification of the evaluation benchmarks, Brier score baselines, calibration criteria, severe-loss metrics, cutoff logic, and governance gates for prospective shadow evaluation. 

The audit identified and corrected a critical transcription error in previous documentation:
- In `phase_9a_prelaunch_audit.md`, SME positive opening Brier score was erroneously transcribed as `0.2019` with a target of $\le 0.2200$. 
- Tracing to the empirical training data (2020–2024) reveals the SME positive base rate is **$83.06\%$** ($N=360$), yielding a constant training base-rate Brier score on the 2026 test cohort of **$0.3041$** (and model Brier of **$0.2894 - 0.3054$**). 
- Imposing a target of Brier $\le 0.2200$ on SME positive opening return when test base rate is $\approx 58.62\%$ is **mathematically impossible** (the theoretical floor for a constant $p=0.5862$ forecast is $0.2426$).
- The evaluation benchmark has been reformulated to compare model Brier scores directly against a **fixed training constant baseline** ($\bar{y}_{\text{train}}$) via the **Brier Skill Score (BSS)**, without refitting on prospective data.

The repository test suite now stands at **139 passing automated unit tests** (0 failures, 0 errors).

---

## 1. Comprehensive Benchmark Audit & Traceability Matrix

Every prospective benchmark has been audited against its underlying historical data, mathematical definition, and sample size requirements:

| Benchmark Metric | Exact Mathematical Definition | Population & Denominator | Baseline Period & Source | Metric Classification | Sample Size for Statistical Power | Primary Limitations |
|---|---|---|---|:---:|---|---|
| **IPO Decision Coverage** | $\frac{N_{\text{logged}}}{N_{\text{eligible}}}$ | All eligible IPOs closing during evaluation window ($N_{\text{eligible}}$) | 100% Statutory Requirement | **Operational Pass/Fail** | $N \ge 1$ (Evaluated on every IPO) | Requires timely monitoring of exchange notices. |
| **Pre-Cutoff Provenance Rate** | $\frac{N_{\text{clean}}}{N_{\text{logged}}}$ | All logged decision records ($N_{\text{logged}}$) | 100% Target; $\ge 90\%$ Pass | **Operational Pass/Fail** | $N \ge 30$ | Dependent on registrar / exchange circular publication speed. |
| **Model Brier Score (Positive Open)** | $\frac{1}{N} \sum_{i=1}^N (p_i - y_i)^2$ | Known listing outcomes with valid probabilities ($N_{\text{known}}$) | Mainboard Train: $0.2364$; SME Train: $0.3041$ ([`step_6a_model_metrics.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_6a_model_metrics.csv)) | **Diagnostic Target** | $N \ge 100$ ($N=30$ has $\text{SE} \approx \pm 0.05$) | Brier score is sensitive to base-rate drift. Cannot be compared across segments. |
| **Brier Skill Score (BSS)** | $1 - \frac{\text{BS}_{\text{model}}}{\text{BS}_{\text{train\_base}}}$ | Known listing outcomes ($N_{\text{known}}$) | Train Constant: MB $0.7583$, SME $0.8306$ | **Diagnostic Target** | $N \ge 100$ | Small-sample noise in $N=30$ can produce wide BSS swings $[-0.30, +0.40]$. |
| **Severe Loss Catch Rate (Recall)** | $\frac{TP_{\text{loss}}}{TP_{\text{loss}} + FN_{\text{loss}}}$ | Actual severe losses ($R_{\text{open}} \le -10\%$) | MB Test: $N=8/90$; SME Test: $N=12/58$ ([`step_7d_model_comparison.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_7d_model_comparison.csv)) | **Early Performance Diagnostic** | $N_{\text{events}} \ge 25$ ($\sim 250-300$ total IPOs) | At $N=30$, expected severe losses are only $1-3$. One missed loss swings recall by $33-50\%$. |
| **Downside Filter Precision** | $\frac{TP_{\text{loss}}}{TP_{\text{loss}} + FP_{\text{loss}}}$ | Candidates flagged by filter ($P_{\text{loss}} \ge \theta_{\text{loss}}$) | Mainboard Val: $0.0476$; Test: $0.0879$ ([`step_6a_model_metrics.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_6a_model_metrics.csv)) | **Early Performance Diagnostic** | $N_{\text{flagged}} \ge 30$ | Rare event precision is low due to severe base-rate class imbalance ($5-9\%$). |
| **Calibration Slope ($\beta$)** | $\text{logit}(y) = \alpha + \beta \text{logit}(p)$ | Known outcomes ($N_{\text{known}}$) | Theoretical Target: $1.0$ | **Inconclusive at $N < 50$** | $N \ge 50$ per segment (minimum 10 per bin) | Uninterpretable at $N=30$. Binomial noise creates artificial slope distortions. |
| **IPO Prediction Win Rate** | $\frac{\sum_{i \in \text{Applied}} \mathbf{1}_{\{R_{\text{gross}, i} > 0\}}}{N_{\text{applied}}}$ | IPOs selected for application by strategy ($N_{\text{applied}}$) | Historical Diagnostic: $73.5\% - 77.3\%$ ([`step_8_1_reconciled_strategy_performance.csv`](file:///d:/personal/st-ai/ipo-record/data/processed/step_8_1_reconciled_strategy_performance.csv)) | **Early Performance Diagnostic** | $N_{\text{applied}} \ge 50$ | Does not account for allotment allocation or capital lockup. |
| **Allotment Realized Win Rate** | $\frac{\sum_{i \in \text{Allotted}} \mathbf{1}_{\{R_{\text{net}, i} > 0\}}}{N_{\text{allotted}}}$ | Applications actually allotted shares ($N_{\text{allotted}}$) | Historical Diagnostic: $73.5\% - 77.8\%$ | **Early Performance Diagnostic** | $N_{\text{allotted}} \ge 30$ | Subject to stochastic allotment lottery and adverse selection in oversubscribed issues. |

---

## 2. Correct Brier Score & Skill Score Formulation

### 2.1 The Mathematical Base-Rate Floor
For any binary outcome $y \in \{0, 1\}$ with test base rate $\bar{y}$, the Brier score of a constant prediction $p = c$ is:
$$\text{BS}(c) = \bar{y} (c - 1)^2 + (1 - \bar{y}) c^2$$
The theoretical minimum Brier score achievable by a naive constant model occurs at $c = \bar{y}$, where $\text{BS}_{\min} = \bar{y}(1 - \bar{y})$.

- **SME Test Cohort (2026)**: $\bar{y}_{\text{test}} = 0.5862 \implies \text{BS}_{\min} = 0.5862 \times 0.4138 = \mathbf{0.2426}$.
- Therefore, setting an arbitrary target of $\text{Brier} \le 0.2200$ on SME positive opening is **mathematically impossible** unless the true market positive rate exceeds $85\%$.
- The historical transcription of `0.2019` in `phase_9a_prelaunch_audit.md` was traced to a transposition of SME Severe Loss Model A Brier score ($0.2090$) or Mainboard Structure Only Severe Loss Brier ($0.2006$).

### 2.2 Formal Brier Skill Score Standard
To ensure scientific validity, model calibration is evaluated strictly against a **fixed training constant baseline**:
$$\text{BS}_{\text{base}} = \frac{1}{N_{\text{known}}} \sum_{i=1}^{N_{\text{known}}} (\bar{y}_{\text{train}} - y_i)^2$$
where $\bar{y}_{\text{train}}$ is fixed permanently from the 2020–2024 training cohort:
- **Mainboard Fixed Base Rate**: $\bar{y}_{\text{train, MB}} = \mathbf{0.7583}$ ($182 / 240$)
- **SME Fixed Base Rate**: $\bar{y}_{\text{train, SME}} = \mathbf{0.8306}$ ($299 / 360$)

The **Brier Skill Score (BSS)** measures the relative percentage improvement in mean squared error over the naive training base-rate forecast:
$$\text{BSS} = 1 - \frac{\text{BS}_{\text{model}}}{\text{BS}_{\text{base}}}$$

**Interpretation Rules**:
- $\text{BSS} > 0$: Model probabilities exhibit genuine predictive skill beyond predicting the climatological training base rate.
- $\text{BSS} = 0$: Model forecast exhibits zero skill over the constant training base rate.
- $\text{BSS} < 0$: Model forecast exhibits negative skill (worse than simply predicting the historical base rate).
- **No Refitting**: Prospective observations must **never** be used to refit $\bar{y}_{\text{train}}$.
- **Missing Outcome Policy**: Decisions awaiting listing ($N_{\text{pending}}$) are tracked separately and excluded from both the numerator and denominator of the Brier score until listing occurs.

---

## 3. Sample-Size Aware Calibration & Uncertainty Reporting

### 3.1 The $N < 50$ Calibration Fallacy
At the 30-IPO checkpoint, dividing 30 IPOs into Mainboard ($\sim 15$) and SME ($\sim 15$) results in fewer than 3 observations per decile bin. Binomial sampling noise at this scale causes extreme scatter in reliability diagrams. 

Fitting a calibration slope $\text{logit}(y) = \alpha + \beta \text{logit}(p)$ on $N < 50$ observations produces standard errors $\text{SE}(\beta) > 0.60$. A slope of $\beta = 0.40$ or $\beta = 1.60$ under $N=30$ is statistically indistinguishable from $\beta = 1.0$ ($p > 0.25$).

### 3.2 Codified Calibration Policy
In [`src/prospective_simulator_logger.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_simulator_logger.py#L380-L425):
1. **Sample Size Gate**: If $N_{\text{known}} < 50$, `evaluate_prospective_calibration()` automatically returns:
   - `status = 'INCONCLUSIVE_INSUFFICIENT_SAMPLE'`
   - `calibration_slope = None`
   - `calibration_bins = []`
   - `recalibration_recommended = False`
2. **Explicit Prohibition**: Under no circumstances shall the model be recalibrated or retrained solely because a small cohort ($N < 50$) misses an empirical calibration-slope target.
3. **Bootstrap Uncertainty**: When evaluated, Brier score and BSS are accompanied by 1,000-resample bootstrap 95% confidence intervals.

---

## 4. Severe-Loss Evaluation Standards

### 4.1 Consistent Definition & Thresholds
- **Severe Loss Event Definition**: Listing opening return $\le -10.0\%$ ($R_{\text{open}} \le -10.0\%$).
- **Frozen Hurdle Rates**:
  - Mainboard Downside Filter: $P(\text{Severe Loss}) \ge \mathbf{0.4868}$ (Validation 80th percentile)
  - SME Downside Filter: $P(\text{Severe Loss}) \ge \mathbf{0.3323}$ (Validation 80th percentile)
- **Candidate Flagged**: Any issue where $P(\text{Severe Loss}) \ge \theta_{\text{loss}}$ is flagged and rejected by Strategies D and E.

### 4.2 Small-Sample Caution & Wilson Confidence Intervals
In a 30-IPO prospective sample, with an expected severe loss rate of $5-10\%$, only **$1$ to $3$ severe loss events** are expected:
- If $N_{\text{severe}} = 3$ and the model flags $2$ of them:
  $$\text{Observed Catch Rate} = \frac{2}{3} = 66.67\%$$
  $$\text{95\% Wilson Confidence Interval} = \mathbf{[20.77\%, 93.85\%]}$$
- A confidence interval spanning $20.8\%$ to $93.9\%$ demonstrates that an observed catch rate of $66.7\%$ does **not** prove effective downside protection.
- Codified Guardrail: If $N_{\text{severe}} < 5$, the evaluator automatically appends:
  `LOW_EVENT_COUNT_CAUTION: Severe-loss event count (N < 5) is too small for statistical inference. Downside protection cannot be confirmed from small event counts.`
- Frozen thresholds $\theta_{\text{loss}}$ must **never** be retuned using prospective evaluation outcomes.

---

## 5. Audit of the 30-IPO Checkpoint

The 30-IPO monitoring milestone is codified in [`src/prospective_simulator_logger.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_simulator_logger.py#L480-L550) as an **operational sanity check and early diagnostic review**, strictly separated into three categories:

```mermaid
flowchart TD
    subgraph CheckpointAudit ["30-IPO Checkpoint Audit Structure"]
        subgraph Cat1 ["1. Operational Pass/Fail Checks"]
            Op1["Pre-Cutoff Logging Coverage: 100%"]
            Op2["Timing & Provenance Verified: >= 90%"]
            Op3["Cryptographic Hash-Chain Continuity: 100% Valid"]
            Op4["Lookahead Contamination: 0 Violations"]
        end

        subgraph Cat2 ["2. Early Performance Diagnostics"]
            Diag1["Model Brier Score vs Fixed Train Baseline"]
            Diag2["Brier Skill Score (BSS) Directional Check"]
            Diag3["IPO Win Rate vs Realized Win Rate"]
            Diag4["Severe Losses Observed vs Flagged Count"]
        end

        subgraph Cat3 ["3. Inconclusive Statistical Checks"]
            Inc1["Calibration Slope & Decile Bins: INCONCLUSIVE (N < 50)"]
            Inc2["Statistical Superiority Hypothesis Tests: UNDERPOWERED"]
            Inc3["Severe Loss Catch Rate Statistical CIs: LOW EVENT COUNT"]
        end
    end

    Cat1 --> Mandate["Governance Gate: SHADOW MONITORING ONLY
    Real-Money Trading: STRICTLY PROHIBITED
    Automatic Production Authorization: FALSE"]
    Cat2 --> Mandate
    Cat3 --> Mandate
```

### Governance Mandate:
Reaching the 30-IPO milestone does **NOT** authorize live trading or capital deployment. Any future decision to transition beyond shadow mode requires:
1. Completion of a separate, formal post-checkpoint audit.
2. Accumulation of a statistically powered sample ($N \ge 100$ total, $N_{\text{severe}} \ge 25$).
3. Demonstrated positive Brier Skill Score ($\text{BSS} > 0$) with bootstrap lower bound $> -0.05$.
4. Independent verification of broker execution slippage and cash drag.

---

## 6. Cutoff Logic & Feature Provenance Verification

### 6.1 Non-17:00 Cutoff Realities
Indian IPOs do not universally close at 17:00 IST on Day 3:
- **Retail Bidding Window**: Some exchange circulars close retail bidding at 16:00 or 16:30 IST while keeping institutional bidding open until 17:00 IST.
- **Issue Extensions**: Undersubscribed or holiday-affected issues are frequently extended to Day 4 or Day 5 by official exchange notice.
- **Fixed-Price Issues**: Fixed-price SME issues often follow distinct cutoff timetables.

### 6.2 Authoritative Cutoff Contract
In [`src/prospective_simulator_logger.py`](file:///d:/personal/st-ai/ipo-record/src/prospective_simulator_logger.py#L110-L160):
1. **Explicit Timezone Mandate**: `cutoff_timestamp_ist` must explicitly state `IST` or `+05:30`. Missing timezone flags `MISSING_CUTOFF_TIMEZONE` and marks the record `TIMING_UNVERIFIED`.
2. **Authoritative Evidence Document**: `feature_provenance` must provide `cutoff_source_evidence` or `source_url_or_doc` citing the official circular or notice establishing the cutoff. Missing evidence flags `MISSING_CUTOFF_SOURCE_EVIDENCE`.
3. **Pre-Cutoff Chronological Consistency**: The source publication timestamp (`source_publication_timestamp_ist`) must be strictly $\le$ `cutoff_timestamp_ist`. Any feature source published after cutoff flags `DATA_QUALITY_POST_CUTOFF_FEATURE`.
4. **Clean Cohort Eligibility**: Only records meeting all provenance and cutoff criteria are marked `eligible_for_clean_prospective_cohort = True`. All others are retained in the ledger for decision-coverage tracking but excluded from clean model evaluation.
5. **No Data Substitution**: Silent substitution of later market data is prohibited and blocked by lookahead guardrails.

---

## 7. Frozen-Model Discipline & Reporting Separation

1. **Frozen SME Baseline Artifact**: `Model_6B_SME_v1.0` remains permanently locked and bit-for-bit identical to its frozen manifest (`dbf2eec716...`).
2. **Frozen Decision Thresholds**: All thresholds ($\theta_{\text{pos}}$, $\theta_{\text{macro}}$, $\theta_{\text{loss}}$) remain fixed as derived from the 2025 validation cohort. No retuning against historical 2026 data.
3. **Decision Coverage Denominator**: All eligible IPOs closing during the window—including those rejected by models—are included in the denominator for decision coverage reporting.
4. **Metric Separation**:
   - **IPO-Level Prediction Win Rate**: Denominator = $N_{\text{applied}}$ (measures pure classification accuracy).
   - **Allotment-Conditioned Realized Win Rate**: Denominator = $N_{\text{allotted}}$ (measures net trading experience).
   - **Unallotted Refunds**: 100% capital returned, zero PnL, tracked separately.

---

## 8. Summary Table of Audit Findings

| Audit Section | Finding / Component | Verdict | Evidence & Verification Reference |
|---|---|:---:|---|
| **Section 1: Benchmarks** | Mathematical definition of all benchmarks | **PASS** | Exact formulas codified in protocol and evaluator |
| **Section 1: Benchmarks** | Denominator decoupling (IPO vs Allotment) | **PASS** | $N_{\text{applied}}$ vs $N_{\text{allotted}}$ strictly separated |
| **Section 1: Benchmarks** | Historical baseline traceability | **PASS** | Traced to Step 6A and 7D; debunked 0.2019 transcription error |
| **Section 2: Brier Score** | Model Brier score calculation | **PASS** | [`test_phase_9a1_protocol_review.py`](file:///d:/personal/st-ai/ipo-record/tests/test_phase_9a1_protocol_review.py#L125-L162) |
| **Section 2: Brier Score** | Fixed training constant baseline ($\bar{y}_{\text{train}}$) | **PASS** | Mainboard: 0.7583; SME: 0.8306 (never refitted) |
| **Section 2: Brier Score** | Brier Skill Score (BSS) formulation | **PASS** | $\text{BSS} = 1 - \text{BS}_{\text{model}} / \text{BS}_{\text{base}}$ |
| **Section 2: Brier Score** | Missing / pending outcome isolation | **PASS** | $N_{\text{pending}}$ tracked separately without distorting Brier |
| **Section 3: Calibration** | Sample-size aware calibration ($N < 50$) | **PASS** | Labels `INCONCLUSIVE_INSUFFICIENT_SAMPLE`; suppresses noisy bins |
| **Section 3: Calibration** | Prohibition on small-sample recalibration | **PASS** | Recalibration trigger blocked when sample is inconclusive |
| **Section 4: Severe Loss** | Consistent definition ($R_{\text{open}} \le -10\%$) | **PASS** | Standardized across all models and ledgers |
| **Section 4: Severe Loss** | Confusion matrix, recall, precision, FPR | **PASS** | Full confusion matrix and metrics computed |
| **Section 4: Severe Loss** | Wilson score 95% confidence intervals | **PASS** | Analytical Wilson score interval implemented |
| **Section 4: Severe Loss** | Low event count caution ($N_{\text{severe}} < 5$) | **PASS** | Appends `LOW_EVENT_COUNT_CAUTION` flag |
| **Section 5: 30-IPO Check** | Metric classification into 3 categories | **PASS** | Operational, Early Diagnostic, and Inconclusive separation |
| **Section 5: 30-IPO Check** | Live trading authorization prohibition | **ENFORCED** | Checkpoint is diagnostic only; trading strictly prohibited |
| **Section 6: Cutoff Logic** | Support for non-17:00 cutoffs and extensions | **PASS** | Authoritative timestamps (16:00, 16:30, Day 4/5) supported |
| **Section 6: Cutoff Logic** | Explicit timezone requirement (IST / +05:30) | **PASS** | Missing timezone flags `TIMING_UNVERIFIED` |
| **Section 6: Cutoff Logic** | Authoritative cutoff evidence requirement | **PASS** | Missing circular/notice flags `TIMING_UNVERIFIED` |
| **Section 6: Cutoff Logic** | Post-cutoff feature publication rejection | **PASS** | `source_pub > cutoff` flags `TIMING_UNVERIFIED` |
| **Section 7: Frozen Model** | Baseline `Model_6B_SME_v1.0` immutability | **PASS** | SHA-256 matches manifest (`dbf2eec716...`) |
| **Test Suite** | Comprehensive automated test coverage | **PASS** | **139/139 unit tests passing** across 13 test modules |

---

## 9. List of Unresolved Methodological Limitations

1. **Small-Sample Severe Loss Statistical Power**:
   - Because severe losses occur at an empirical base rate of $5-9\%$, an interim cohort of 30 IPOs will yield only $1-3$ events. Statistical confirmation of downside protection requires $N_{\text{severe}} \ge 25$ ($\sim 250-300$ total IPOs).
2. **Retail Bidding Window Dispersion**:
   - While the logger enforces authoritative circular verification, exchange circulars occasionally update retail close times intraday. Pipeline monitoring must poll exchange circular feeds continuously up to cutoff.
3. **Synthetic Allotment Assumption in Shadow Mode**:
   - In prospective shadow logging, true retail allotment is unknown until post-allotment basis circulars are published by the registrar (typically 2 days after close). Until basis records are obtained, strategy performance relies on deterministic uniform draws.
4. **Execution Slippage Variability**:
   - Modeled net returns assume a fixed $-1.0\%$ opening auction slippage and $-0.35\%$ roundtrip costs. In highly volatile or illiquid SME listings, realized opening auction slippage can deviate substantially from $-1.0\%$.

---

## 10. Conclusion & Final Authorization

The prospective evaluation protocol is **APPROVED AS READY WITH DOCUMENTED LIMITATIONS FOR OPERATIONAL SHADOW LOGGING**.

All benchmarks have been mathematically verified, baseline comparisons corrected, cutoff logic hardened against non-standard issue closings, and sample-size limitations explicitly codified.

The team is authorized to proceed with passive shadow logging of upcoming Indian IPOs in software ledgers. No real capital shall be committed.
