"""
Script: src/run_step_8_simulator.py
Objective: Step 8 - Historical IPO Decision and Allocation Simulator.
Simulates realistic historical IPO investment strategies under:
  - Capital constraints (starting capital = INR 500,000)
  - Application ticket sizes (Mainboard: INR 15,000; SME: INR 125,000)
  - ASBA capital lock-up timing (issue close to listing date)
  - Configurable allotment probabilities (Conservative 20%, Central 50%, Optimistic 80%, Naive 100%)
  - Realistic transaction costs (STT, exchange turnover, stamp duty, GST = 0.35%)
  - Adverse slippage on listing open (-1.0%)
Strategies Evaluated:
  - Strategy A: Apply to All Eligible IPOs (Baseline)
  - Strategy B: Macro-Only Filter
  - Strategy C: Positive-Opening Ranking (Validation-tuned threshold)
  - Strategy D: Downside-Risk Filter (Validation-tuned threshold)
  - Strategy E: Combined Ranking + Downside Filter
  - Strategy F: No Application (Liquid Cash Benchmark)
Outputs:
  - data/processed/step_8_strategy_performance.csv
  - data/processed/step_8_capital_event_ledger.csv
  - data/processed/step_8_sensitivity_analysis.csv
  - data/processed/step_8_exclusions_and_missingness.csv
"""

import os
import json
import datetime
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression

def build_and_run_simulator():
    print("======================================================================")
    print("STEP 8: HISTORICAL IPO DECISION AND ALLOCATION SIMULATOR")
    print("======================================================================")
    os.makedirs('data/processed', exist_ok=True)
    
    # ---------------------------------------------------------
    # 1. Load Data & Provenance
    # ---------------------------------------------------------
    df_f = pd.read_csv('data/processed/ipo_features_issue_close.csv')
    df_fund = pd.read_csv('data/processed/step_7d_normalized_features.csv')
    df_cutoff = pd.read_csv('data/processed/ipo_cutoff_recovery.csv')
    
    # Merge features
    cols_to_merge = [
        'ipo_id', 'log_issue_price', 'feat_has_price_band', 
        'feat_price_band_spread_pct', 'feat_is_fixed_price_issue', 
        'temporal_eligibility'
    ]
    merged = pd.merge(df_f, df_fund[cols_to_merge], on='ipo_id')
    
    # Date formatting & temporal splitting
    merged['issue_close_dt'] = pd.to_datetime(merged['issue_close_date'])
    merged['listing_dt'] = pd.to_datetime(merged['listing_date'])
    merged['listing_year'] = merged['listing_dt'].dt.year
    
    # Exclusion accounting
    exclusion_records = []
    for idx, row in merged.iterrows():
        reasons = []
        if row['temporal_eligibility'] != True:
            reasons.append("Unverified prediction cutoff or missing price band circular")
        if pd.isna(row['target_listing_open_return_pct']):
            reasons.append("Missing realized listing opening return")
        if pd.isna(row['nifty50_return_5s']) or pd.isna(row['india_vix_level_at_cutoff']):
            reasons.append("Missing macro market indicators at cutoff")
            
        is_inc = (len(reasons) == 0)
        exclusion_records.append({
            'ipo_id': row['ipo_id'],
            'company_name': row['company_name'],
            'board_type': row['board_type'],
            'listing_date': str(row['listing_date'])[:10],
            'included_in_simulation': is_inc,
            'exclusion_reason': '; '.join(reasons) if not is_inc else 'ELIGIBLE'
        })
    df_exclusions = pd.DataFrame(exclusion_records)
    out_excl = 'data/processed/step_8_exclusions_and_missingness.csv'
    df_exclusions.to_csv(out_excl, index=False)
    print(f"Saved exclusion & missingness ledger to {out_excl} ({len(df_exclusions)} IPOs)")
    
    # Eligible dataset
    req_cols = ['target_listing_open_return_pct', 'nifty50_return_5s', 'india_vix_level_at_cutoff', 'recent5_positive_listing_rate']
    eligible = merged[(merged['temporal_eligibility'] == True)].dropna(subset=req_cols).copy()
    
    eligible['target_positive_open'] = (eligible['target_listing_open_return_pct'] > 0).astype(int)
    eligible['target_severe_loss'] = (eligible['target_listing_open_return_pct'] <= -10.0).astype(int)
    
    print(f"Total Eligible IPOs across 2020-2026: {len(eligible)} ({len(eligible[eligible['board_type']=='Mainboard'])} Mainboard, {len(eligible[eligible['board_type']=='SME'])} SME)")

    # ---------------------------------------------------------
    # 2. Chronological Model Fitting & Out-of-Time Prediction
    # ---------------------------------------------------------
    # Train: <= 2024, Val: 2025, Test Diagnostic: 2026
    # Train separate models for Mainboard and SME strictly on training set
    feature_cols = ['nifty50_return_5s', 'india_vix_level_at_cutoff', 'recent5_positive_listing_rate', 
                    'log_issue_price', 'feat_price_band_spread_pct', 'feat_is_fixed_price_issue']
    
    prob_predictions = []
    val_thresholds = {}
    
    for board in ['Mainboard', 'SME']:
        df_b = eligible[eligible['board_type'] == board].copy()
        tr = df_b[df_b['listing_year'] <= 2024].copy()
        va = df_b[df_b['listing_year'] == 2025].copy()
        te = df_b[df_b['listing_year'] == 2026].copy()
        
        # Training-set median imputation
        med_spread = tr['feat_price_band_spread_pct'].median()
        med_log_price = tr['log_issue_price'].median()
        for d in [tr, va, te, df_b]:
            d['feat_price_band_spread_pct'] = d['feat_price_band_spread_pct'].fillna(med_spread)
            d['log_issue_price'] = d['log_issue_price'].fillna(med_log_price)
            d['feat_is_fixed_price_issue'] = d['feat_is_fixed_price_issue'].fillna(0.0)
            
        # Standardize strictly on training mean & std
        for f in feature_cols:
            m = tr[f].mean()
            s = tr[f].std()
            if s == 0 or pd.isna(s): s = 1.0
            for d in [tr, va, te, df_b]:
                d[f'z_{f}'] = (d[f] - m) / s
                
        macro_z = ['z_nifty50_return_5s', 'z_india_vix_level_at_cutoff', 'z_recent5_positive_listing_rate']
        structure_z = ['z_feat_price_band_spread_pct', 'z_feat_is_fixed_price_issue']
        scale_spread_z = ['z_nifty50_return_5s', 'z_india_vix_level_at_cutoff', 'z_recent5_positive_listing_rate', 'z_log_issue_price', 'z_feat_price_band_spread_pct']
        unified_z = ['z_nifty50_return_5s', 'z_india_vix_level_at_cutoff', 'z_recent5_positive_listing_rate', 'z_log_issue_price', 'z_feat_price_band_spread_pct', 'z_feat_is_fixed_price_issue']
        
        # Best model specs verified in Step 7D:
        # Mainboard Positive: Model C (structure only)
        # Mainboard Severe Loss: Model E (unified)
        # SME Positive: Model D (macro + scale/price)
        # SME Severe Loss: Model E (unified)
        pos_feats = structure_z if board == 'Mainboard' else scale_spread_z
        loss_feats = unified_z
        
        clf_pos = LogisticRegression(C=1.0, solver='lbfgs', random_state=42).fit(tr[pos_feats], tr['target_positive_open'])
        clf_macro = LogisticRegression(C=1.0, solver='lbfgs', random_state=42).fit(tr[macro_z], tr['target_positive_open'])
        clf_loss = LogisticRegression(C=1.0, class_weight='balanced', solver='lbfgs', random_state=42).fit(tr[loss_feats], tr['target_severe_loss'])
        
        # Predict on validation to select decision thresholds
        p_pos_va = clf_pos.predict_proba(va[pos_feats])[:, 1]
        p_loss_va = clf_loss.predict_proba(va[loss_feats])[:, 1]
        
        # Calibrated thresholds on validation:
        # Positive rank threshold: top 40% (q=60) on validation
        th_pos = float(np.percentile(p_pos_va, 60))
        # Severe loss rejection threshold: worst 20% on validation (q=80)
        th_loss = float(np.percentile(p_loss_va, 80))
        
        val_thresholds[board] = {
            'th_pos': th_pos,
            'th_loss': th_loss,
            'val_sample': len(va),
            'val_base_pos': float(va['target_positive_open'].mean()),
            'val_base_loss': float(va['target_severe_loss'].mean())
        }
        
        # Predict on all eligible records in board
        p_pos_all = clf_pos.predict_proba(df_b[pos_feats])[:, 1]
        p_macro_all = clf_macro.predict_proba(df_b[macro_z])[:, 1]
        p_loss_all = clf_loss.predict_proba(df_b[loss_feats])[:, 1]
        
        for idx_k, (_, r) in enumerate(df_b.iterrows()):
            prob_predictions.append({
                'ipo_id': r['ipo_id'],
                'board_type': board,
                'p_positive_open': round(float(p_pos_all[idx_k]), 4),
                'p_macro': round(float(p_macro_all[idx_k]), 4),
                'p_severe_loss': round(float(p_loss_all[idx_k]), 4)
            })
            
    df_probs = pd.DataFrame(prob_predictions)
    eligible = pd.merge(eligible, df_probs, on=['ipo_id', 'board_type'])
    print(f"Validation-tuned thresholds: {json.dumps(val_thresholds, indent=2)}")

    # ---------------------------------------------------------
    # 3. Decision Simulation Engine
    # ---------------------------------------------------------
    def simulate_strategy(cohort_df, strategy_name, start_capital=500000.0, 
                          p_allotment=0.50, slippage_pct=1.0, roundtrip_cost_pct=0.35, 
                          random_seed=42):
        """
        Executes calendar-aware simulation respecting ASBA capital blocking and release.
        """
        rng = np.random.RandomState(random_seed)
        df_sim = cohort_df.sort_values('issue_close_dt').copy()
        
        # State variables
        available_cash = start_capital
        blocked_cash = 0.0
        peak_portfolio_val = start_capital
        max_drawdown_amt = 0.0
        max_drawdown_pct = 0.0
        
        # Active locked applications: list of dicts
        # {ipo_id, application_amount, release_dt, is_allotted, net_pnl, net_return_pct}
        active_blocks = []
        
        # History logs
        event_ledger = []
        allotment_returns = []
        application_returns = []
        
        total_applications_attempted = 0
        total_applications_blocked_by_capital = 0
        total_applications_submitted = 0
        total_allotments_won = 0
        total_severe_losses_incurred = 0
        total_profitable_allotments = 0
        
        # Unique dates in calendar order
        all_dates = sorted(list(set(df_sim['issue_close_dt'].tolist() + df_sim['listing_dt'].tolist())))
        
        for curr_dt in all_dates:
            # 1. First process any unlocks/listings occurring on or before curr_dt
            still_active = []
            for item in active_blocks:
                if item['release_dt'] <= curr_dt:
                    # Fund unlock event
                    if item['is_allotted']:
                        # Position liquidated at listing open
                        returned_funds = item['application_amount'] + item['net_pnl']
                        available_cash += returned_funds
                        blocked_cash -= item['application_amount']
                        allotment_returns.append(item['net_return_pct'])
                        application_returns.append(item['net_return_pct'])
                        if item['net_return_pct'] > 0:
                            total_profitable_allotments += 1
                        if item['net_return_pct'] <= -10.0:
                            total_severe_losses_incurred += 1
                            
                        event_ledger.append({
                            'date': str(curr_dt)[:10],
                            'ipo_id': item['ipo_id'],
                            'event_type': 'LISTING_AND_CAPITAL_RETURN',
                            'application_amount': item['application_amount'],
                            'allotment_status': 'ALLOTTED',
                            'gross_return_pct': item['gross_return_pct'],
                            'net_return_pct': round(item['net_return_pct'], 2),
                            'net_pnl_inr': round(item['net_pnl'], 2),
                            'available_cash': round(available_cash, 2),
                            'blocked_cash': round(blocked_cash, 2),
                            'total_portfolio_val': round(available_cash + blocked_cash, 2)
                        })
                    else:
                        # Non-allotted application: 100% refund unblocked
                        available_cash += item['application_amount']
                        blocked_cash -= item['application_amount']
                        application_returns.append(0.0)
                        
                        event_ledger.append({
                            'date': str(curr_dt)[:10],
                            'ipo_id': item['ipo_id'],
                            'event_type': 'UNBLOCK_REFUND',
                            'application_amount': item['application_amount'],
                            'allotment_status': 'NOT_ALLOTTED',
                            'gross_return_pct': 0.0,
                            'net_return_pct': 0.0,
                            'net_pnl_inr': 0.0,
                            'available_cash': round(available_cash, 2),
                            'blocked_cash': round(blocked_cash, 2),
                            'total_portfolio_val': round(available_cash + blocked_cash, 2)
                        })
                else:
                    still_active.append(item)
            active_blocks = still_active
            
            # Update peak value and drawdown
            current_total_val = available_cash + blocked_cash
            if current_total_val > peak_portfolio_val:
                peak_portfolio_val = current_total_val
            dd_amt = peak_portfolio_val - current_total_val
            dd_pct = (dd_amt / peak_portfolio_val) * 100.0 if peak_portfolio_val > 0 else 0.0
            if dd_amt > max_drawdown_amt:
                max_drawdown_amt = dd_amt
            if dd_pct > max_drawdown_pct:
                max_drawdown_pct = dd_pct
                
            # 2. Check for new IPOs closing on curr_dt
            closing_today = df_sim[df_sim['issue_close_dt'] == curr_dt]
            if closing_today.empty:
                continue
                
            # Candidate filter based on strategy rule
            for _, ipo in closing_today.iterrows():
                board = ipo['board_type']
                req_app_amt = 15000.0 if board == 'Mainboard' else 125000.0
                
                # Decision logic
                apply_decision = False
                reason = "REJECTED_BY_STRATEGY"
                
                if strategy_name == 'Strategy_A_Apply_All':
                    apply_decision = True
                    reason = "APPLY_ALL_RULE"
                    
                elif strategy_name == 'Strategy_B_Macro_Filter':
                    # Macro probability >= 0.50 or favorable macro
                    if ipo['p_macro'] >= 0.50:
                        apply_decision = True
                        reason = "MACRO_FAVORABLE"
                    else:
                        reason = "MACRO_UNFAVORABLE"
                        
                elif strategy_name == 'Strategy_C_Positive_Ranking':
                    # Validation threshold
                    th = val_thresholds[board]['th_pos']
                    if ipo['p_positive_open'] >= th:
                        apply_decision = True
                        reason = f"POS_PROB_ABOVE_THRESHOLD_{th:.2f}"
                    else:
                        reason = f"POS_PROB_BELOW_THRESHOLD_{th:.2f}"
                        
                elif strategy_name == 'Strategy_D_Downside_Filter':
                    # Reject if severe loss prob >= validation threshold
                    th_l = val_thresholds[board]['th_loss']
                    if ipo['p_severe_loss'] < th_l:
                        apply_decision = True
                        reason = f"LOSS_PROB_SAFE_BELOW_{th_l:.2f}"
                    else:
                        reason = f"SEVERE_LOSS_RISK_ABOVE_{th_l:.2f}"
                        
                elif strategy_name == 'Strategy_E_Combined':
                    th_p = val_thresholds[board]['th_pos']
                    th_l = val_thresholds[board]['th_loss']
                    if (ipo['p_positive_open'] >= th_p) and (ipo['p_severe_loss'] < th_l):
                        apply_decision = True
                        reason = "COMBINED_QUALIFIED"
                    else:
                        reason = "COMBINED_FAILED"
                        
                elif strategy_name == 'Strategy_F_No_Application':
                    apply_decision = False
                    reason = "CASH_BENCHMARK_NO_ACTION"
                    
                total_applications_attempted += 1 if strategy_name != 'Strategy_F_No_Application' else 0
                
                if not apply_decision:
                    continue
                    
                # Capital check
                if available_cash >= req_app_amt:
                    # Application accepted!
                    available_cash -= req_app_amt
                    blocked_cash += req_app_amt
                    total_applications_submitted += 1
                    
                    # Determine allotment outcome
                    # Stochastic draw with probability p_allotment
                    is_allotted = (rng.rand() < p_allotment)
                    if is_allotted:
                        total_allotments_won += 1
                        
                    # Calculate net listing return
                    gross_ret = float(ipo['target_listing_open_return_pct'])
                    net_ret = gross_ret - slippage_pct - roundtrip_cost_pct
                    net_pnl = req_app_amt * (net_ret / 100.0) if is_allotted else 0.0
                    
                    active_blocks.append({
                        'ipo_id': ipo['ipo_id'],
                        'board_type': board,
                        'application_amount': req_app_amt,
                        'release_dt': ipo['listing_dt'],
                        'is_allotted': is_allotted,
                        'gross_return_pct': gross_ret,
                        'net_return_pct': net_ret,
                        'net_pnl': net_pnl
                    })
                    
                    event_ledger.append({
                        'date': str(curr_dt)[:10],
                        'ipo_id': ipo['ipo_id'],
                        'event_type': 'APPLICATION_SUBMITTED',
                        'application_amount': req_app_amt,
                        'allotment_status': 'PENDING',
                        'gross_return_pct': np.nan,
                        'net_return_pct': np.nan,
                        'net_pnl_inr': 0.0,
                        'available_cash': round(available_cash, 2),
                        'blocked_cash': round(blocked_cash, 2),
                        'total_portfolio_val': round(available_cash + blocked_cash, 2)
                    })
                else:
                    total_applications_blocked_by_capital += 1
                    event_ledger.append({
                        'date': str(curr_dt)[:10],
                        'ipo_id': ipo['ipo_id'],
                        'event_type': 'REJECTED_CAPITAL_EXHAUSTION',
                        'application_amount': req_app_amt,
                        'allotment_status': 'REJECTED',
                        'gross_return_pct': np.nan,
                        'net_return_pct': np.nan,
                        'net_pnl_inr': 0.0,
                        'available_cash': round(available_cash, 2),
                        'blocked_cash': round(blocked_cash, 2),
                        'total_portfolio_val': round(available_cash + blocked_cash, 2)
                    })
                    
        # Flush any remaining blocks at end of period
        for item in active_blocks:
            if item['is_allotted']:
                available_cash += (item['application_amount'] + item['net_pnl'])
                allotment_returns.append(item['net_return_pct'])
                application_returns.append(item['net_return_pct'])
                if item['net_return_pct'] > 0:
                    total_profitable_allotments += 1
                if item['net_return_pct'] <= -10.0:
                    total_severe_losses_incurred += 1
            else:
                available_cash += item['application_amount']
                application_returns.append(0.0)
            blocked_cash -= item['application_amount']
            
        final_portfolio_val = available_cash + blocked_cash
        net_profit_inr = final_portfolio_val - start_capital
        roi_total_pct = (net_profit_inr / start_capital) * 100.0
        
        # Calculate summary metrics
        mean_allotment_ret = float(np.mean(allotment_returns)) if len(allotment_returns) > 0 else 0.0
        median_allotment_ret = float(np.median(allotment_returns)) if len(allotment_returns) > 0 else 0.0
        worst_allotment_loss = float(np.min(allotment_returns)) if len(allotment_returns) > 0 else 0.0
        allotment_win_rate = (total_profitable_allotments / total_allotments_won * 100.0) if total_allotments_won > 0 else 0.0
        severe_loss_rate = (total_severe_losses_incurred / total_allotments_won * 100.0) if total_allotments_won > 0 else 0.0
        
        return {
            'strategy_name': strategy_name,
            'start_capital_inr': start_capital,
            'final_portfolio_val_inr': round(final_portfolio_val, 2),
            'net_profit_inr': round(net_profit_inr, 2),
            'roi_total_pct': round(roi_total_pct, 2),
            'max_drawdown_amt_inr': round(max_drawdown_amt, 2),
            'max_drawdown_pct': round(max_drawdown_pct, 2),
            'applications_attempted': total_applications_attempted,
            'applications_submitted': total_applications_submitted,
            'applications_blocked_capital': total_applications_blocked_by_capital,
            'allotments_won': total_allotments_won,
            'allotment_win_rate_pct': round(allotment_win_rate, 2),
            'mean_allotment_return_pct': round(mean_allotment_ret, 2),
            'median_allotment_return_pct': round(median_allotment_ret, 2),
            'worst_allotment_loss_pct': round(worst_allotment_loss, 2),
            'severe_losses_incurred': total_severe_losses_incurred,
            'severe_loss_frequency_pct': round(severe_loss_rate, 2),
            'event_ledger': event_ledger
        }

    # ---------------------------------------------------------
    # 4. Execute Benchmark & Strategy Comparison on 2026 Cohort
    # ---------------------------------------------------------
    test_2026 = eligible[eligible['listing_year'] == 2026].copy()
    print(f"\nRunning Primary Strategy Simulation on 2026 Holdout Cohort ({len(test_2026)} IPOs)...")
    
    strategies = [
        'Strategy_A_Apply_All',
        'Strategy_B_Macro_Filter',
        'Strategy_C_Positive_Ranking',
        'Strategy_D_Downside_Filter',
        'Strategy_E_Combined',
        'Strategy_F_No_Application'
    ]
    
    perf_rows = []
    combined_ledgers = []
    
    for board_eval in ['Combined', 'Mainboard', 'SME']:
        cohort = test_2026 if board_eval == 'Combined' else test_2026[test_2026['board_type'] == board_eval]
        
        for strat in strategies:
            res = simulate_strategy(cohort, strat, start_capital=500000.0, p_allotment=0.50, slippage_pct=1.0, roundtrip_cost_pct=0.35)
            
            perf_rows.append({
                'market_segment': board_eval,
                'strategy': res['strategy_name'],
                'eligible_ipo_universe': len(cohort),
                'start_capital': res['start_capital_inr'],
                'final_portfolio_val': res['final_portfolio_val_inr'],
                'net_profit_inr': res['net_profit_inr'],
                'roi_pct': res['roi_total_pct'],
                'max_drawdown_pct': res['max_drawdown_pct'],
                'applications_submitted': res['applications_submitted'],
                'applications_capital_rejected': res['applications_blocked_capital'],
                'allotments_won': res['allotments_won'],
                'allotment_win_rate_pct': res['allotment_win_rate_pct'],
                'mean_return_per_allotment': res['mean_allotment_return_pct'],
                'median_return_per_allotment': res['median_allotment_return_pct'],
                'worst_single_loss_pct': res['worst_allotment_loss_pct'],
                'severe_losses_incurred': res['severe_losses_incurred'],
                'severe_loss_freq_pct': res['severe_loss_frequency_pct']
            })
            
            if board_eval == 'Combined':
                for ev in res['event_ledger']:
                    ev['strategy'] = strat
                    combined_ledgers.append(ev)
                    
    df_perf = pd.DataFrame(perf_rows)
    out_perf = 'data/processed/step_8_strategy_performance.csv'
    df_perf.to_csv(out_perf, index=False)
    print(f"Saved Strategy Performance Table to {out_perf} ({len(df_perf)} evaluations)")
    
    df_ledger = pd.DataFrame(combined_ledgers)
    out_ledger = 'data/processed/step_8_capital_event_ledger.csv'
    df_ledger.to_csv(out_ledger, index=False)
    print(f"Saved Capital Event Ledger to {out_ledger} ({len(df_ledger)} transaction events)")

    # ---------------------------------------------------------
    # 5. Sensitivity Analysis Across Allotment & Costs
    # ---------------------------------------------------------
    print("\nRunning Sensitivity Analysis across Allotment Rates, Slippage, and Costs...")
    sens_rows = []
    
    allotment_scenarios = [0.20, 0.50, 0.80, 1.00]
    slippage_scenarios = [0.0, 1.0, 2.0]
    cost_scenarios = [0.0, 0.35, 0.70]
    
    for strat in ['Strategy_A_Apply_All', 'Strategy_C_Positive_Ranking', 'Strategy_E_Combined']:
        for p_allot in allotment_scenarios:
            for slip in slippage_scenarios:
                for cost in cost_scenarios:
                    s_res = simulate_strategy(test_2026, strat, start_capital=500000.0, 
                                              p_allotment=p_allot, slippage_pct=slip, roundtrip_cost_pct=cost)
                    sens_rows.append({
                        'strategy': strat,
                        'allotment_prob': p_allot,
                        'slippage_pct': slip,
                        'roundtrip_cost_pct': cost,
                        'net_profit_inr': s_res['net_profit_inr'],
                        'roi_pct': s_res['roi_total_pct'],
                        'max_drawdown_pct': s_res['max_drawdown_pct'],
                        'allotments_won': s_res['allotments_won'],
                        'mean_allotment_return_pct': s_res['mean_allotment_return_pct'],
                        'severe_losses_incurred': s_res['severe_losses_incurred']
                    })
                    
    df_sens = pd.DataFrame(sens_rows)
    out_sens = 'data/processed/step_8_sensitivity_analysis.csv'
    df_sens.to_csv(out_sens, index=False)
    print(f"Saved Sensitivity Analysis Matrix to {out_sens} ({len(df_sens)} scenario runs)")
    
    print("\nStep 8 Simulation Engine Execution Complete.")
    return df_perf, df_ledger, df_sens

if __name__ == '__main__':
    build_and_run_simulator()
