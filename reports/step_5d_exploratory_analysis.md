# Step 5D Report: Exploratory Statistical Analysis of Indian IPOs

## 1. Executive Summary

Step 5D provides an empirical baseline and statistical evaluation of the 1,515 Indian IPOs (covering 2020 through October 2026) before any predictive model selection or training:
- **Output Tables**:
  - `data/processed/step_5d_baseline_statistics.csv`: Complete distributional percentiles, means, and 95% bootstrap confidence intervals for listing-open and listing-close returns.
  - `data/processed/step_5d_downside_risk.csv`: Empirical downside loss frequencies (<-5%, <-10%, <-20%), tail loss percentiles (P5), and severe drawdowns.
  - `data/processed/step_5d_market_analysis.csv`: Univariate regressions, effect sizes, and logistic odds ratios against pre-issue market conditions and sentiment.
  - `data/processed/step_5d_feature_coverage.csv`: Audit of candidate feature availability and verified observation counts.
- **Figures Generated**: `reports/figures/` (Return distributions, downside risk by segment, sentiment momentum scatterplot).
- **Automated Tests**: `tests/test_step_5d.py` (All 4 test suites passed).

---

## 2. Data Audit & Coverage

| Candidate Feature | Total Records | Verified Observations | Missing / Unresolved | Mainboard Verified | SME Verified | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Listing Close Return** | 1,515 | 1,515 (100.0%) | 0 (0.0%) | 463 | 1,052 | Complete target |
| **Listing Open Return** | 1,515 | 1,512 (99.8%) | 3 (0.2%) | 463 | 1,049 | 3 SME missing pre-open quotes |
| **Prediction Cutoff Date** | 1,515 | 987 (65.1%) | 528 (34.9%) | 445 (96.1%) | 542 (51.5%) | Preserved without synthetic fill |
| **Nifty 50 (5s return)** | 1,515 | 987 (65.1%) | 528 (34.9%) | 445 | 542 | Cutoff-aligned market signal |
| **India VIX Level** | 1,515 | 984 (64.9%) | 531 (35.1%) | 443 | 541 | Excludes non-settlement sessions |
| **Recent 5 Sentiment** | 1,515 | 986 (65.1%) | 529 (34.9%) | 445 | 541 | Trailing prior listings strictly < cutoff |
| **Verified Subscription**| 1,515 | 0 (Schema ready)| 1,515 | 0 | 0 | Excluded from models until audited |
| **Verified GMP** | 1,515 | 0 (Schema ready)| 1,515 | 0 | 0 | Excluded from models until audited |

> [!IMPORTANT]
> **Data Integrity Rule Upheld**: Unverified subscription multiples and unofficial web-scraped GMP figures without timestamp audit trails have been kept strictly blank (`NaN`). They are **not** imputed as zero and will not be passed into baseline machine learning algorithms.

---

## 3. Historical Baseline & Board Comparison

Returns are defined as:
$$\text{Return (\%)} = \left(\frac{\text{Price}}{\text{Issue Price}} - 1\right) \times 100$$

### Listing-Day Close Return Baseline

| Cohort | N | Positive Rate (>0%) | Flat Rate (=0%) | Negative Rate (<0%) | Mean (95% CI) | Median | P5 (Worst 5%) | Worst Observed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Overall** | 1,515 | 74.0% | 0.5% | **25.5%** | +27.0% (+24.7%, +29.5%) | **+10.4%** | -18.7% | -47.5% |
| **Mainboard** | 463 | 72.6% | 0.0% | **27.4%** | +21.2% (+18.4%, +24.1%) | **+12.0%** | -12.3% | -36.6% |
| **SME Board** | 1,052 | 74.6% | 0.7% | **24.7%** | +29.6% (+26.5%, +32.9%) | **+9.8%** | -21.4% | -47.5% |

### Listing-Day Open Return Baseline (Actionable Opening Price)

| Cohort | N | Positive Rate (>0%) | Flat Rate (=0%) | Negative Rate (<0%) | Mean (95% CI) | Median | P5 (Worst 5%) | Worst Observed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Overall** | 1,512 | 78.4% | 2.2% | **19.4%** | +28.9% (+26.6%, +31.3%) | **+12.0%** | -20.0% | -50.0% |
| **Mainboard** | 463 | 77.3% | 1.3% | **21.4%** | +23.8% (+21.0%, +26.8%) | **+14.0%** | -10.2% | -39.6% |
| **SME Board** | 1,049 | 78.8% | 2.6% | **18.5%** | +31.1% (+28.0%, +34.5%) | **+10.0%** | -20.0% | -50.0% |

---

## 4. Downside Risk Analysis: Tail Risk is Asymmetric

A key research question is loss severity. While positive listing rates exceed 70%, tail risk differs significantly between segments:

| Segment | Target | Prob Loss (<0%) | Loss $\le -10\%$ | Loss $\le -20\%$ | Mean Loss When Negative |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Mainboard** | Listing Open | 21.4% | **5.6%** | **1.3%** | -8.1% |
| **SME Board** | Listing Open | 18.5% | **10.5%** | **7.2%** | **-12.7%** |
| **Mainboard** | Listing Close | 27.4% | **7.1%** | **2.2%** | -8.5% |
| **SME Board** | Listing Close | 24.7% | **11.1%** | **5.5%** | **-11.4%** |

> [!WARNING]
> **SME Tail Asymmetry**: Although SME IPOs exhibit a slightly lower headline loss rate at open (18.5% vs 21.4%), their **probability of a severe loss ($\le -10\%$) is nearly double** that of Mainboard issues (10.5% vs 5.6%), and extreme drawdowns ($\le -20\%$) are **over 5 times more frequent** (7.2% vs 1.3%).

---

## 5. Market Conditions & Recent Sentiment Findings

Using the verified cutoff sample ($N = 984$ to $986$):

1. **Pre-Issue Market Momentum**:
   - **Nifty 50 (5-session return)**: OLS coefficient = $+173.2$ ($p = 0.046$, $R^2 = 0.004$). Logistic Odds Ratio = $2.10 \times 10^4$ ($p = 0.010$). Positive broad market momentum into issue close significantly increases the odds of a positive listing.
   - **Nifty 500 (5-session return)**: OLS coefficient = $+211.0$ ($p = 0.0098$, $R^2 = 0.007$). Logistic Odds Ratio = $2.63 \times 10^4$ ($p = 0.005$).
2. **India VIX (Pre-Issue Volatility Level)**:
   - OLS coefficient = $+0.326$ ($p = 0.440$, not statistically significant). Logit Odds Ratio = $0.990$ ($p = 0.582$).
   - *Interpretation*: The raw level of India VIX at issue close alone does not exhibit a simple linear relationship with listing return, likely due to cyclical regime shifts and structural market interventions.
3. **Recent IPO Sentiment Momentum**:
   - **Recent 5 IPOs Mean Open Return**: OLS coefficient = $+0.434$ ($p < 0.0001$, $R^2 = 0.054$). Logistic Odds Ratio = $1.012$ per 1% increase in trailing return ($p = 0.00013$).
   - *Key Finding*: Trailing IPO listing sentiment exhibits strong, statistically significant clustering ($R^2 \approx 5.4\%$). Periods where preceding IPOs list strongly are substantially more likely to yield positive subsequent listings.

---

## 6. Recommendations for Initial Model Selection (Step 6)

1. **Keep Segments Separate**: Build separate or interaction-explicit models for Mainboard and SME due to stark liquidity, lot-size, and tail-loss divergence.
2. **Dual Model Objective**:
   - Model A: **Classifier** for probability of positive listing ($P(\text{Return} > 0)$) and severe loss ($P(\text{Return} \le -10\%)$).
   - Model B: **Regressor** for expected listing return distribution.
3. **Strict Chronological Evaluation**: Train on earlier vintages (e.g., 2020–2024), tune on 2025, and evaluate out-of-time on 2026.
