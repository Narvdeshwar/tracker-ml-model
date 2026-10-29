"""
Script: src/run_step_5d_analysis.py
Objective: Comprehensive exploratory statistical analysis for Step 5D.
Calculates historical baseline distributions, downside risks, market condition effects,
recent IPO sentiment momentum, and board segment comparisons.
Outputs structured summary CSVs and visualizations.
"""

import os
import pandas as pd
import numpy as np
from scipy import stats
import statsmodels.api as sm
import statsmodels.formula.api as smf
import matplotlib.pyplot as plt

def run_step_5d_analysis():
    os.makedirs('data/processed', exist_ok=True)
    os.makedirs('reports/figures', exist_ok=True)
    
    # 1. Load Datasets
    df_ipo = pd.read_csv('data/processed/ipo_features_issue_close.csv')
    df_cohort = pd.read_csv('data_verified/ipo_cohort_verified.csv')
    
    # Merge listing prices if needed
    if 'listing_open_inr' not in df_ipo.columns:
        df_ipo = df_ipo.merge(
            df_cohort[['issue_id', 'listing_open_inr', 'listing_close_inr']],
            left_on='ipo_id', right_on='issue_id', how='left'
        )
    
    print(f"Loaded {len(df_ipo)} IPO records.")
    
    # Standardize Targets & Binary Labels
    # target_listing_open_return_pct and target_listing_close_return_pct
    df_ipo['listing_year'] = pd.to_datetime(df_ipo['listing_date']).dt.year
    
    # 2. Section 1: Feature Coverage Audit
    coverage_rows = []
    features_to_audit = [
        ('ipo_id', 'Identifier'),
        ('prediction_cutoff_date', 'Cutoff Date'),
        ('target_listing_open_return_pct', 'Target Open Return'),
        ('target_listing_close_return_pct', 'Target Close Return'),
        ('nifty50_return_5s', 'Market Nifty50 5s'),
        ('nifty500_return_5s', 'Market Nifty500 5s'),
        ('india_vix_level_at_cutoff', 'Market India VIX'),
        ('nifty_sme_emerge_return_5s', 'SME Emerge 5s'),
        ('bse_sme_ipo_return_5s', 'BSE SME IPO 5s'),
        ('recent5_mean_listing_open_return_pct', 'Recent 5 Sentiment'),
        ('total_subscription_multiple', 'Total Subscription (Verified)'),
        ('gmp_amount_inr', 'GMP (Verified)')
    ]
    
    for col, label in features_to_audit:
        non_null = df_ipo[col].notnull().sum()
        null_count = df_ipo[col].isnull().sum()
        pct = (non_null / len(df_ipo)) * 100
        coverage_rows.append({
            'feature': col,
            'label': label,
            'total_records': len(df_ipo),
            'non_missing': non_null,
            'missing': null_count,
            'coverage_pct': round(pct, 2),
            'mainboard_non_missing': df_ipo[df_ipo['board_type'] == 'Mainboard'][col].notnull().sum(),
            'sme_non_missing': df_ipo[df_ipo['board_type'] == 'SME'][col].notnull().sum(),
        })
    df_cov = pd.DataFrame(coverage_rows)
    df_cov.to_csv('data/processed/step_5d_feature_coverage.csv', index=False)
    print("Saved data/processed/step_5d_feature_coverage.csv")

    # 3. Section 2: Historical Baseline Statistics
    def compute_distribution_metrics(series, name):
        s = series.dropna()
        n = len(s)
        if n == 0:
            return {}
        pos = (s > 0).sum()
        neg = (s < 0).sum()
        flat = (s == 0).sum()
        mean = s.mean()
        std = s.std()
        med = s.median()
        # Bootstrap 95% CI for median and mean
        boot_means = [np.random.choice(s, size=n, replace=True).mean() for _ in range(1000)]
        mean_ci_low, mean_ci_high = np.percentile(boot_means, [2.5, 97.5])
        
        return {
            'group': name,
            'n_obs': n,
            'positive_count': pos,
            'positive_rate_pct': round((pos / n) * 100, 2),
            'negative_count': neg,
            'negative_rate_pct': round((neg / n) * 100, 2),
            'flat_count': flat,
            'flat_rate_pct': round((flat / n) * 100, 2),
            'mean_pct': round(mean, 2),
            'mean_ci_95_low': round(mean_ci_low, 2),
            'mean_ci_95_high': round(mean_ci_high, 2),
            'median_pct': round(med, 2),
            'std_pct': round(std, 2),
            'p5_pct': round(np.percentile(s, 5), 2),
            'p10_pct': round(np.percentile(s, 10), 2),
            'p25_pct': round(np.percentile(s, 25), 2),
            'p75_pct': round(np.percentile(s, 75), 2),
            'p90_pct': round(np.percentile(s, 90), 2),
            'iqr_pct': round(np.percentile(s, 75) - np.percentile(s, 25), 2),
            'min_pct': round(s.min(), 2),
            'max_pct': round(s.max(), 2),
        }

    baseline_rows = []
    # All, Mainboard, SME, by Year
    for target_col, target_label in [('target_listing_open_return_pct', 'Listing_Open'), ('target_listing_close_return_pct', 'Listing_Close')]:
        # Overall
        res = compute_distribution_metrics(df_ipo[target_col], f"Overall_{target_label}")
        baseline_rows.append(res)
        # Mainboard
        res_mb = compute_distribution_metrics(df_ipo[df_ipo['board_type'] == 'Mainboard'][target_col], f"Mainboard_{target_label}")
        baseline_rows.append(res_mb)
        # SME
        res_sme = compute_distribution_metrics(df_ipo[df_ipo['board_type'] == 'SME'][target_col], f"SME_{target_label}")
        baseline_rows.append(res_sme)
        # Yearly
        for yr, grp in df_ipo.groupby('listing_year'):
            res_yr = compute_distribution_metrics(grp[target_col], f"Year_{yr}_{target_label}")
            baseline_rows.append(res_yr)

    df_base = pd.DataFrame(baseline_rows)
    df_base.to_csv('data/processed/step_5d_baseline_statistics.csv', index=False)
    print("Saved data/processed/step_5d_baseline_statistics.csv")

    # 4. Section 3: Downside Risk Analysis
    downside_rows = []
    for target_col, target_label in [('target_listing_open_return_pct', 'Listing_Open'), ('target_listing_close_return_pct', 'Listing_Close')]:
        for segment_name, segment_df in [('Overall', df_ipo), ('Mainboard', df_ipo[df_ipo['board_type'] == 'Mainboard']), ('SME', df_ipo[df_ipo['board_type'] == 'SME'])]:
            s = segment_df[target_col].dropna()
            n = len(s)
            neg = s[s < 0]
            downside_rows.append({
                'segment': segment_name,
                'target': target_label,
                'total_obs': n,
                'prob_loss_pct': round((len(neg) / n) * 100, 2),
                'prob_loss_gt_5pct': round(((s <= -5).sum() / n) * 100, 2),
                'prob_loss_gt_10pct': round(((s <= -10).sum() / n) * 100, 2),
                'prob_loss_gt_20pct': round(((s <= -20).sum() / n) * 100, 2),
                'p5_worst_pct': round(np.percentile(s, 5), 2),
                'worst_observed_loss_pct': round(s.min(), 2),
                'mean_loss_when_negative_pct': round(neg.mean(), 2) if len(neg) > 0 else 0.0,
                'median_loss_when_negative_pct': round(neg.median(), 2) if len(neg) > 0 else 0.0
            })
    df_downside = pd.DataFrame(downside_rows)
    df_downside.to_csv('data/processed/step_5d_downside_risk.csv', index=False)
    print("Saved data/processed/step_5d_downside_risk.csv")

    # 5. Section 4: Market Conditions & Recent Sentiment Regression Analysis
    # Filter to verified cutoff cohort (N = 987)
    df_verified = df_ipo[df_ipo['cutoff_status'] == 'verified'].dropna(subset=['nifty50_return_5s', 'india_vix_level_at_cutoff', 'target_listing_close_return_pct']).copy()
    
    market_res_rows = []
    # Regress listing_close_return on:
    # 1. Nifty 50 5s
    # 2. India VIX level
    # 3. SME index 5s (for SME)
    # 4. Recent 5 IPO Sentiment Mean
    # Run univariate and multivariate regressions
    
    # Univariate regressions
    candidate_features = [
        ('nifty50_return_5s', 'Nifty 50 (5s return)'),
        ('nifty500_return_5s', 'Nifty 500 (5s return)'),
        ('india_vix_level_at_cutoff', 'India VIX Level'),
        ('recent5_mean_listing_open_return_pct', 'Recent 5 IPO Open Return Mean')
    ]
    
    for feat, feat_label in candidate_features:
        sub = df_verified.dropna(subset=[feat, 'target_listing_close_return_pct'])
        X = sm.add_constant(sub[feat])
        y = sub['target_listing_close_return_pct']
        model = sm.OLS(y, X).fit()
        
        # Binary logistic regression for positive listing
        y_binary = (y > 0).astype(int)
        logit_model = sm.Logit(y_binary, X).fit(disp=False)
        odds_ratio = np.exp(logit_model.params[feat])
        
        market_res_rows.append({
            'feature': feat,
            'feature_label': feat_label,
            'sample_size': len(sub),
            'ols_coefficient': round(model.params[feat], 4),
            'ols_pvalue': round(model.pvalues[feat], 5),
            'ols_r_squared': round(model.rsquared, 4),
            'logit_odds_ratio': round(odds_ratio, 4),
            'logit_pvalue': round(logit_model.pvalues[feat], 5)
        })
        
    df_market_analysis = pd.DataFrame(market_res_rows)
    df_market_analysis.to_csv('data/processed/step_5d_market_analysis.csv', index=False)
    print("Saved data/processed/step_5d_market_analysis.csv")

    # 6. Generate Informative Figures
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    
    # Figure 1: Return Distributions (Mainboard vs SME)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    mb_ret = df_ipo[df_ipo['board_type'] == 'Mainboard']['target_listing_close_return_pct'].dropna()
    sme_ret = df_ipo[df_ipo['board_type'] == 'SME']['target_listing_close_return_pct'].dropna()
    
    # Clip extreme returns for display purposes
    ax1.hist(mb_ret.clip(lower=-50, upper=150), bins=35, color='#1f77b4', alpha=0.7, edgecolor='black')
    ax1.axvline(0, color='red', linestyle='--', linewidth=1.5, label='Breakeven')
    ax1.axvline(mb_ret.median(), color='darkgreen', linestyle='-', linewidth=2, label=f'Median: {mb_ret.median():.1f}%')
    ax1.set_title(f'Mainboard Listing Returns (N={len(mb_ret)})', fontsize=12, fontweight='bold')
    ax1.set_xlabel('Listing Day Close Return (%)')
    ax1.set_ylabel('Number of IPOs')
    ax1.legend()
    
    ax2.hist(sme_ret.clip(lower=-50, upper=150), bins=35, color='#ff7f0e', alpha=0.7, edgecolor='black')
    ax2.axvline(0, color='red', linestyle='--', linewidth=1.5, label='Breakeven')
    ax2.axvline(sme_ret.median(), color='darkgreen', linestyle='-', linewidth=2, label=f'Median: {sme_ret.median():.1f}%')
    ax2.set_title(f'SME Board Listing Returns (N={len(sme_ret)})', fontsize=12, fontweight='bold')
    ax2.set_xlabel('Listing Day Close Return (%)')
    ax2.legend()
    
    plt.tight_layout()
    plt.savefig('reports/figures/figure1_return_distributions.png', dpi=200)
    plt.close()
    
    # Figure 2: Downside Frequency by Segment
    fig, ax = plt.subplots(figsize=(8, 5))
    metrics = ['Loss (<0%)', 'Severe (<-10%)', 'Extreme (<-20%)']
    mb_probs = [(mb_ret < 0).mean() * 100, (mb_ret <= -10).mean() * 100, (mb_ret <= -20).mean() * 100]
    sme_probs = [(sme_ret < 0).mean() * 100, (sme_ret <= -10).mean() * 100, (sme_ret <= -20).mean() * 100]
    
    x = np.arange(len(metrics))
    width = 0.35
    ax.bar(x - width/2, mb_probs, width, label='Mainboard', color='#1f77b4')
    ax.bar(x + width/2, sme_probs, width, label='SME Board', color='#ff7f0e')
    ax.set_ylabel('Empirical Probability (%)')
    ax.set_title('Downside Risk Comparison by Market Segment', fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.legend()
    for i in range(len(metrics)):
        ax.annotate(f"{mb_probs[i]:.1f}%", (x[i] - width/2, mb_probs[i] + 0.8), ha='center', fontsize=10)
        ax.annotate(f"{sme_probs[i]:.1f}%", (x[i] + width/2, sme_probs[i] + 0.8), ha='center', fontsize=10)
    plt.tight_layout()
    plt.savefig('reports/figures/figure2_downside_risk.png', dpi=200)
    plt.close()
    
    # Figure 3: Sentiment vs Listing Performance
    fig, ax = plt.subplots(figsize=(8, 5))
    sent_sub = df_verified.dropna(subset=['recent5_mean_listing_open_return_pct', 'target_listing_close_return_pct'])
    ax.scatter(sent_sub['recent5_mean_listing_open_return_pct'].clip(-20, 100), sent_sub['target_listing_close_return_pct'].clip(-50, 150), alpha=0.4, color='#2ca02c')
    ax.axhline(0, color='red', linestyle='--', linewidth=1)
    ax.axvline(0, color='red', linestyle='--', linewidth=1)
    ax.set_xlabel('Recent 5 IPOs Mean Open Return (%)')
    ax.set_ylabel('Target Listing Close Return (%)')
    ax.set_title('Recent IPO Sentiment vs Listing Performance', fontsize=12, fontweight='bold')
    plt.tight_layout()
    plt.savefig('reports/figures/figure3_sentiment_vs_return.png', dpi=200)
    plt.close()
    
    print("Saved figures under reports/figures/")

if __name__ == '__main__':
    run_step_5d_analysis()
