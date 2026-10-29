"""
Script: src/run_step_8_1_audit_simulator.py
Objective: Step 8.1 - Independent Simulator Integrity Audit and Reconciliation.
Implements:
  1. Fully deterministic per-IPO allotment draws (cryptographic hash based on ipo_id and scenario).
  2. Complete shared-ledger segment reconciliation (Combined Profit == Mainboard Contribution + SME Contribution).
  3. Calibrated validation threshold for Strategy B (Macro Filter) alongside audit of uncalibrated 0.50 threshold.
  4. Precise equity curve and maximum drawdown calculation.
  5. Standalone dedicated portfolio comparison with explicit capital denominators.
Outputs:
  - data/processed/step_8_1_reconciled_strategy_performance.csv
  - data/processed/step_8_1_shared_capital_ledger.csv
  - data/processed/step_8_1_macro_filter_audit.csv
  - data/processed/step_8_1_reconciled_sensitivity.csv
"""

import os
import json
import hashlib
import datetime
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression

def get_uniform_draw(ipo_id, scenario_seed):
    """
    Computes an idempotent, deterministic uniform draw u in [0, 1) using SHA-256.
    Uses 53 bits (matching IEEE-754 double precision mantissa) divided by 2**53,
    mathematically and floating-point guaranteeing u in [0, 1) without rounding to 1.0.
    """
    key = f"{ipo_id}_{scenario_seed}".encode('utf-8')
    h64 = int.from_bytes(hashlib.sha256(key).digest()[:8], byteorder='big')
    h53 = h64 >> 11
    return h53 / float(1 << 53)

def get_deterministic_allotment(ipo_id, scenario_seed, p_allotment):
    """
    Computes an idempotent, deterministic, and strictly nested allotment outcome for an IPO.
    The underlying uniform draw u depends strictly on (ipo_id, scenario_seed).
    Ensures mathematical nesting: Allotted(20%) c Allotted(50%) c Allotted(80%) c Allotted(100%).
    Raises ValueError if p_allotment is outside [0.0, 1.0] or is NaN/None.
    """
    if p_allotment is None or (isinstance(p_allotment, float) and np.isnan(p_allotment)):
        raise ValueError(f"p_allotment cannot be None or NaN, got {p_allotment}")
    if p_allotment < 0.0 or p_allotment > 1.0:
        raise ValueError(f"p_allotment must be strictly in [0.0, 1.0], got {p_allotment}")
    if p_allotment >= 1.0:
        return True
    if p_allotment <= 0.0:
        return False
    # Stable cryptographic uniform draw u in [0, 1) independent of p_allotment
    uniform_draw = get_uniform_draw(ipo_id, scenario_seed)
    return uniform_draw < p_allotment

def run_step_8_1_audit():
    print("======================================================================")
    print("STEP 8.1: INDEPENDENT SIMULATOR INTEGRITY & RECONCILIATION AUDIT")
    print("======================================================================")
    os.makedirs('data/processed', exist_ok=True)
    
    # 1. Load Data
    df_f = pd.read_csv('data/processed/ipo_features_issue_close.csv')
    df_fund = pd.read_csv('data/processed/step_7d_normalized_features.csv')
    cols_to_merge = ['ipo_id', 'log_issue_price', 'feat_has_price_band', 'feat_price_band_spread_pct', 'feat_is_fixed_price_issue', 'temporal_eligibility']
    merged = pd.merge(df_f, df_fund[cols_to_merge], on='ipo_id')
    
    merged['issue_close_dt'] = pd.to_datetime(merged['issue_close_date'])
    merged['listing_dt'] = pd.to_datetime(merged['listing_date'])
    merged['listing_year'] = merged['listing_dt'].dt.year
    
    req_cols = ['target_listing_open_return_pct', 'nifty50_return_5s', 'india_vix_level_at_cutoff', 'recent5_positive_listing_rate']
    eligible = merged[(merged['temporal_eligibility'] == True)].dropna(subset=req_cols).copy()
    eligible['target_positive_open'] = (eligible['target_listing_open_return_pct'] > 0).astype(int)
    eligible['target_severe_loss'] = (eligible['target_listing_open_return_pct'] <= -10.0).astype(int)
    
    print(f"Total Eligible IPOs: {len(eligible)} ({len(eligible[eligible['board_type']=='Mainboard'])} Mainboard, {len(eligible[eligible['board_type']=='SME'])} SME)")

    # 2. Chronological Modeling & Threshold Calibration
    feature_cols = ['nifty50_return_5s', 'india_vix_level_at_cutoff', 'recent5_positive_listing_rate', 
                    'log_issue_price', 'feat_price_band_spread_pct', 'feat_is_fixed_price_issue']
    macro_cols = ['nifty50_return_5s', 'india_vix_level_at_cutoff', 'recent5_positive_listing_rate']
    
    val_thresholds = {}
    macro_audit_records = []
    prob_predictions = []
    
    for board in ['Mainboard', 'SME']:
        df_b = eligible[eligible['board_type'] == board].copy()
        tr = df_b[df_b['listing_year'] <= 2024].copy()
        va = df_b[df_b['listing_year'] == 2025].copy()
        te = df_b[df_b['listing_year'] == 2026].copy()
        
        med_spread = tr['feat_price_band_spread_pct'].median()
        med_log_price = tr['log_issue_price'].median()
        for d in [tr, va, te, df_b]:
            d['feat_price_band_spread_pct'] = d['feat_price_band_spread_pct'].fillna(med_spread)
            d['log_issue_price'] = d['log_issue_price'].fillna(med_log_price)
            d['feat_is_fixed_price_issue'] = d['feat_is_fixed_price_issue'].fillna(0.0)
            
        for f in feature_cols:
            m = tr[f].mean()
            s = tr[f].std()
            if s == 0 or pd.isna(s): s = 1.0
            for d in [tr, va, te, df_b]:
                d[f'z_{f}'] = (d[f] - m) / s
                
        macro_z = ['z_' + f for f in macro_cols]
        structure_z = ['z_feat_price_band_spread_pct', 'z_feat_is_fixed_price_issue']
        scale_spread_z = ['z_nifty50_return_5s', 'z_india_vix_level_at_cutoff', 'z_recent5_positive_listing_rate', 'z_log_issue_price', 'z_feat_price_band_spread_pct']
        unified_z = ['z_nifty50_return_5s', 'z_india_vix_level_at_cutoff', 'z_recent5_positive_listing_rate', 'z_log_issue_price', 'z_feat_price_band_spread_pct', 'z_feat_is_fixed_price_issue']
        
        pos_feats = structure_z if board == 'Mainboard' else scale_spread_z
        loss_feats = unified_z
        
        clf_pos = LogisticRegression(C=1.0, solver='lbfgs', random_state=42).fit(tr[pos_feats], tr['target_positive_open'])
        clf_macro = LogisticRegression(C=1.0, solver='lbfgs', random_state=42).fit(tr[macro_z], tr['target_positive_open'])
        clf_loss = LogisticRegression(C=1.0, class_weight='balanced', solver='lbfgs', random_state=42).fit(tr[loss_feats], tr['target_severe_loss'])
        
        p_pos_va = clf_pos.predict_proba(va[pos_feats])[:, 1]
        p_macro_va = clf_macro.predict_proba(va[macro_z])[:, 1]
        p_loss_va = clf_loss.predict_proba(va[loss_feats])[:, 1]
        
        th_pos = float(np.percentile(p_pos_va, 60))
        th_macro = float(np.median(p_macro_va))
        th_loss = float(np.percentile(p_loss_va, 80))
        
        val_thresholds[board] = {
            'th_pos': th_pos,
            'th_macro': th_macro,
            'th_loss': th_loss,
            'val_sample': len(va),
            'val_macro_min': float(p_macro_va.min()),
            'val_macro_median': th_macro,
            'val_macro_max': float(p_macro_va.max())
        }
        
        p_pos_all = clf_pos.predict_proba(df_b[pos_feats])[:, 1]
        p_macro_all = clf_macro.predict_proba(df_b[macro_z])[:, 1]
        p_loss_all = clf_loss.predict_proba(df_b[loss_feats])[:, 1]
        
        for idx_k, (_, r) in enumerate(df_b.iterrows()):
            p_m = float(p_macro_all[idx_k])
            prob_predictions.append({
                'ipo_id': r['ipo_id'],
                'board_type': board,
                'p_positive_open': round(float(p_pos_all[idx_k]), 4),
                'p_macro': round(p_m, 4),
                'p_severe_loss': round(float(p_loss_all[idx_k]), 4)
            })
            
            if r['listing_year'] == 2026:
                macro_audit_records.append({
                    'ipo_id': r['ipo_id'],
                    'company_name': r['company_name'],
                    'board_type': board,
                    'issue_close_date': str(r['issue_close_date'])[:10],
                    'p_macro': round(p_m, 4),
                    'th_macro_raw': 0.50,
                    'th_macro_calibrated': round(th_macro, 4),
                    'passed_raw_050': bool(p_m >= 0.50),
                    'passed_calibrated': bool(p_m >= th_macro),
                    'actual_listing_return_pct': round(float(r['target_listing_open_return_pct']), 2),
                    'is_positive_open': bool(r['target_listing_open_return_pct'] > 0),
                    'is_severe_loss': bool(r['target_listing_open_return_pct'] <= -10.0)
                })
                
    df_probs = pd.DataFrame(prob_predictions)
    eligible = pd.merge(eligible, df_probs, on=['ipo_id', 'board_type'])
    
    df_macro_audit = pd.DataFrame(macro_audit_records)
    out_macro_audit = 'data/processed/step_8_1_macro_filter_audit.csv'
    df_macro_audit.to_csv(out_macro_audit, index=False)
    print(f"Saved Macro Filter Event Audit to {out_macro_audit} ({len(df_macro_audit)} IPOs)")

    # 3. Deterministic Shared-Ledger Simulation Engine
    def simulate_shared_portfolio(cohort_df, strategy_name, start_capital=500000.0,
                                  p_allotment=0.50, slippage_pct=1.0, roundtrip_cost_pct=0.35,
                                  scenario_seed=42):
        df_sim = cohort_df.sort_values('issue_close_dt').copy()
        
        available_cash = start_capital
        blocked_cash = 0.0
        peak_portfolio_val = start_capital
        max_drawdown_amt = 0.0
        max_drawdown_pct = 0.0
        
        active_blocks = []
        event_ledger = []
        
        all_dates = sorted(list(set(df_sim['issue_close_dt'].tolist() + df_sim['listing_dt'].tolist())))
        
        for curr_dt in all_dates:
            # A. Process listing unlocks occurring on curr_dt
            still_active = []
            for item in active_blocks:
                if item['release_dt'] <= curr_dt:
                    if item['is_allotted']:
                        returned_funds = item['application_amount'] + item['net_pnl']
                        available_cash += returned_funds
                        blocked_cash -= item['application_amount']
                        
                        event_ledger.append({
                            'date': str(curr_dt)[:10],
                            'ipo_id': item['ipo_id'],
                            'board_type': item['board_type'],
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
                        available_cash += item['application_amount']
                        blocked_cash -= item['application_amount']
                        
                        event_ledger.append({
                            'date': str(curr_dt)[:10],
                            'ipo_id': item['ipo_id'],
                            'board_type': item['board_type'],
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
            
            # Recalculate equity & drawdown after unblocks
            curr_equity = available_cash + blocked_cash
            if curr_equity > peak_portfolio_val:
                peak_portfolio_val = curr_equity
            dd_amt = peak_portfolio_val - curr_equity
            dd_pct = (dd_amt / peak_portfolio_val) * 100.0 if peak_portfolio_val > 0 else 0.0
            if dd_amt > max_drawdown_amt:
                max_drawdown_amt = dd_amt
            if dd_pct > max_drawdown_pct:
                max_drawdown_pct = dd_pct
                
            # B. Process new IPO applications closing on curr_dt
            closing_today = df_sim[df_sim['issue_close_dt'] == curr_dt]
            if closing_today.empty:
                continue
                
            for _, ipo in closing_today.iterrows():
                board = ipo['board_type']
                req_amt = 15000.0 if board == 'Mainboard' else 125000.0
                
                apply_decision = False
                reason = "REJECTED_BY_STRATEGY"
                
                if strategy_name == 'Strategy_A_Apply_All':
                    apply_decision = True
                    reason = "APPLY_ALL_RULE"
                    
                elif strategy_name == 'Strategy_B_Macro_Filter':
                    # Calibrated validation median threshold
                    th_m = val_thresholds[board]['th_macro']
                    if ipo['p_macro'] >= th_m:
                        apply_decision = True
                        reason = f"MACRO_CALIBRATED_PASS_{th_m:.2f}"
                    else:
                        reason = f"MACRO_CALIBRATED_FAIL_{th_m:.2f}"
                        
                elif strategy_name == 'Strategy_C_Positive_Ranking':
                    th_p = val_thresholds[board]['th_pos']
                    if ipo['p_positive_open'] >= th_p:
                        apply_decision = True
                        reason = f"POS_PROB_PASS_{th_p:.2f}"
                    else:
                        reason = f"POS_PROB_FAIL_{th_p:.2f}"
                        
                elif strategy_name == 'Strategy_D_Downside_Filter':
                    th_l = val_thresholds[board]['th_loss']
                    if ipo['p_severe_loss'] < th_l:
                        apply_decision = True
                        reason = f"RISK_PASS_SAFE_{th_l:.2f}"
                    else:
                        reason = f"RISK_REJECT_HAZARD_{th_l:.2f}"
                        
                elif strategy_name == 'Strategy_E_Combined':
                    th_p = val_thresholds[board]['th_pos']
                    th_l = val_thresholds[board]['th_loss']
                    if (ipo['p_positive_open'] >= th_p) and (ipo['p_severe_loss'] < th_l):
                        apply_decision = True
                        reason = "COMBINED_PASS"
                    else:
                        reason = "COMBINED_FAIL"
                        
                elif strategy_name == 'Strategy_F_No_Application':
                    apply_decision = False
                    reason = "CASH_BENCHMARK"
                    
                if not apply_decision:
                    continue
                    
                # Capital availability check
                if available_cash >= req_amt:
                    available_cash -= req_amt
                    blocked_cash += req_amt
                    
                    # Deterministic allotment draw
                    is_allotted = get_deterministic_allotment(ipo['ipo_id'], scenario_seed, p_allotment)
                    
                    gross_ret = float(ipo['target_listing_open_return_pct'])
                    net_ret = gross_ret - slippage_pct - roundtrip_cost_pct
                    net_pnl = req_amt * (net_ret / 100.0) if is_allotted else 0.0
                    
                    active_blocks.append({
                        'ipo_id': ipo['ipo_id'],
                        'board_type': board,
                        'application_amount': req_amt,
                        'release_dt': ipo['listing_dt'],
                        'is_allotted': is_allotted,
                        'gross_return_pct': gross_ret,
                        'net_return_pct': net_ret,
                        'net_pnl': net_pnl
                    })
                    
                    event_ledger.append({
                        'date': str(curr_dt)[:10],
                        'ipo_id': ipo['ipo_id'],
                        'board_type': board,
                        'event_type': 'APPLICATION_SUBMITTED',
                        'application_amount': req_amt,
                        'allotment_status': 'PENDING',
                        'gross_return_pct': np.nan,
                        'net_return_pct': np.nan,
                        'net_pnl_inr': 0.0,
                        'available_cash': round(available_cash, 2),
                        'blocked_cash': round(blocked_cash, 2),
                        'total_portfolio_val': round(available_cash + blocked_cash, 2)
                    })
                else:
                    event_ledger.append({
                        'date': str(curr_dt)[:10],
                        'ipo_id': ipo['ipo_id'],
                        'board_type': board,
                        'event_type': 'REJECTED_CAPITAL_EXHAUSTION',
                        'application_amount': req_amt,
                        'allotment_status': 'REJECTED',
                        'gross_return_pct': np.nan,
                        'net_return_pct': np.nan,
                        'net_pnl_inr': 0.0,
                        'available_cash': round(available_cash, 2),
                        'blocked_cash': round(blocked_cash, 2),
                        'total_portfolio_val': round(available_cash + blocked_cash, 2)
                    })
                    
        # Flush active blocks at end of cohort
        for item in active_blocks:
            if item['is_allotted']:
                available_cash += (item['application_amount'] + item['net_pnl'])
                event_ledger.append({
                    'date': str(item['release_dt'])[:10],
                    'ipo_id': item['ipo_id'],
                    'board_type': item['board_type'],
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
                available_cash += item['application_amount']
            blocked_cash -= item['application_amount']
            
        final_val = available_cash + blocked_cash
        net_profit = final_val - start_capital
        
        # Segment accounting strictly from the shared ledger
        df_ev = pd.DataFrame(event_ledger)
        if not df_ev.empty:
            listings = df_ev[df_ev['event_type'] == 'LISTING_AND_CAPITAL_RETURN']
            mb_listings = listings[listings['board_type'] == 'Mainboard']
            sme_listings = listings[listings['board_type'] == 'SME']
            
            mb_pnl = float(mb_listings['net_pnl_inr'].sum())
            sme_pnl = float(sme_listings['net_pnl_inr'].sum())
            
            mb_allotments = len(mb_listings)
            sme_allotments = len(sme_listings)
            
            mb_wins = (mb_listings['net_return_pct'] > 0).sum()
            sme_wins = (sme_listings['net_return_pct'] > 0).sum()
            
            mb_losses = (mb_listings['net_return_pct'] <= -10.0).sum()
            sme_losses = (sme_listings['net_return_pct'] <= -10.0).sum()
            
            apps_sub = len(df_ev[df_ev['event_type'] == 'APPLICATION_SUBMITTED'])
            apps_rej = len(df_ev[df_ev['event_type'] == 'REJECTED_CAPITAL_EXHAUSTION'])
            
            worst_loss = float(listings['net_return_pct'].min()) if len(listings) > 0 else 0.0
            mean_ret = float(listings['net_return_pct'].mean()) if len(listings) > 0 else 0.0
            tot_wins = (listings['net_return_pct'] > 0).sum()
            tot_allot = len(listings)
            win_rate = (tot_wins / tot_allot * 100.0) if tot_allot > 0 else 0.0
            tot_losses = (listings['net_return_pct'] <= -10.0).sum()
        else:
            mb_pnl, sme_pnl = 0.0, 0.0
            mb_allotments, sme_allotments = 0, 0
            mb_wins, sme_wins = 0, 0
            mb_losses, sme_losses = 0, 0
            apps_sub, apps_rej = 0, 0
            worst_loss, mean_ret, win_rate, tot_losses = 0.0, 0.0, 0.0, 0
            tot_allot = 0
            
        return {
            'strategy_name': strategy_name,
            'start_capital': start_capital,
            'final_portfolio_val': round(final_val, 2),
            'net_profit_total': round(net_profit, 2),
            'mainboard_pnl_contribution': round(mb_pnl, 2),
            'sme_pnl_contribution': round(sme_pnl, 2),
            'reconciliation_diff': round(net_profit - (mb_pnl + sme_pnl), 4),
            'roi_total_pct': round((net_profit / start_capital) * 100.0, 2),
            'max_drawdown_pct': round(max_drawdown_pct, 2),
            'applications_submitted': apps_sub,
            'applications_capital_rejected': apps_rej,
            'allotments_won_total': tot_allot,
            'allotments_won_mainboard': mb_allotments,
            'allotments_won_sme': sme_allotments,
            'allotment_win_rate_pct': round(win_rate, 2),
            'mean_allotment_return_pct': round(mean_ret, 2),
            'worst_single_loss_pct': round(worst_loss, 2),
            'severe_losses_incurred': tot_losses,
            'severe_losses_mainboard': mb_losses,
            'severe_losses_sme': sme_losses,
            'event_ledger': event_ledger
        }

    # 4. Execute 2026 Cohort Simulation
    test_2026 = eligible[eligible['listing_year'] == 2026].copy()
    print(f"\nRunning Audited Simulation on 2026 Diagnostic Cohort ({len(test_2026)} IPOs)...")
    
    strategies = [
        'Strategy_A_Apply_All',
        'Strategy_B_Macro_Filter',
        'Strategy_C_Positive_Ranking',
        'Strategy_D_Downside_Filter',
        'Strategy_E_Combined',
        'Strategy_F_No_Application'
    ]
    
    reconciled_perf_rows = []
    shared_ledgers = []
    
    for strat in strategies:
        sim_res = simulate_shared_portfolio(test_2026, strat, start_capital=500000.0, p_allotment=0.50, slippage_pct=1.0, roundtrip_cost_pct=0.35)
        
        reconciled_perf_rows.append({
            'strategy': sim_res['strategy_name'],
            'start_capital': sim_res['start_capital'],
            'final_portfolio_val': sim_res['final_portfolio_val'],
            'net_profit_total': sim_res['net_profit_total'],
            'mainboard_contribution': sim_res['mainboard_pnl_contribution'],
            'sme_contribution': sim_res['sme_pnl_contribution'],
            'reconciliation_diff': sim_res['reconciliation_diff'],
            'roi_pct': sim_res['roi_total_pct'],
            'max_drawdown_pct': sim_res['max_drawdown_pct'],
            'apps_submitted': sim_res['applications_submitted'],
            'apps_rejected_capital': sim_res['applications_capital_rejected'],
            'allotments_won': sim_res['allotments_won_total'],
            'allotments_mainboard': sim_res['allotments_won_mainboard'],
            'allotments_sme': sim_res['allotments_won_sme'],
            'allotment_win_rate_pct': sim_res['allotment_win_rate_pct'],
            'mean_return_per_allotment': sim_res['mean_allotment_return_pct'],
            'worst_single_loss_pct': sim_res['worst_single_loss_pct'],
            'severe_losses_total': sim_res['severe_losses_incurred'],
            'severe_losses_mainboard': sim_res['severe_losses_mainboard'],
            'severe_losses_sme': sim_res['severe_losses_sme']
        })
        
        for ev in sim_res['event_ledger']:
            ev['strategy'] = strat
            shared_ledgers.append(ev)
            
    df_reconciled = pd.DataFrame(reconciled_perf_rows)
    out_perf = 'data/processed/step_8_1_reconciled_strategy_performance.csv'
    df_reconciled.to_csv(out_perf, index=False)
    print(f"Saved Reconciled Strategy Performance Table to {out_perf} ({len(df_reconciled)} strategies)")
    
    df_shared_ledger = pd.DataFrame(shared_ledgers)
    out_ledger = 'data/processed/step_8_1_shared_capital_ledger.csv'
    df_shared_ledger.to_csv(out_ledger, index=False)
    print(f"Saved Shared Capital Ledger to {out_ledger} ({len(df_shared_ledger)} events)")

    # 4b. Execute Standalone Dedicated Portfolio Simulations (Dedicated INR 500,000 per board)
    standalone_perf_rows = []
    for board in ['Mainboard', 'SME']:
        cohort_b = test_2026[test_2026['board_type'] == board].copy()
        for strat in strategies:
            s_res = simulate_shared_portfolio(cohort_b, strat, start_capital=500000.0, p_allotment=0.50, slippage_pct=1.0, roundtrip_cost_pct=0.35)
            standalone_perf_rows.append({
                'market_segment': board,
                'strategy': strat,
                'dedicated_capital_inr': 500000.0,
                'final_portfolio_val': s_res['final_portfolio_val'],
                'net_profit_inr': s_res['net_profit_total'],
                'roi_pct': s_res['roi_total_pct'],
                'max_drawdown_pct': s_res['max_drawdown_pct'],
                'apps_submitted': s_res['applications_submitted'],
                'apps_rejected_capital': s_res['applications_capital_rejected'],
                'allotments_won': s_res['allotments_won_total'],
                'allotment_win_rate_pct': s_res['allotment_win_rate_pct'],
                'mean_return_per_allotment': s_res['mean_allotment_return_pct'],
                'worst_single_loss_pct': s_res['worst_single_loss_pct'],
                'severe_losses_incurred': s_res['severe_losses_incurred']
            })
    df_standalone = pd.DataFrame(standalone_perf_rows)
    out_standalone = 'data/processed/step_8_1_standalone_strategy_performance.csv'
    df_standalone.to_csv(out_standalone, index=False)
    print(f"Saved Standalone Strategy Performance Table to {out_standalone} ({len(df_standalone)} evaluations)")

    # 5. Reconciled Sensitivity Analysis
    print("\nRunning Reconciled Sensitivity Analysis across Allotment, Slippage, and Costs...")
    sens_rows = []
    for strat in ['Strategy_A_Apply_All', 'Strategy_B_Macro_Filter', 'Strategy_C_Positive_Ranking', 'Strategy_D_Downside_Filter', 'Strategy_E_Combined']:
        for p_allot in [0.20, 0.50, 0.80, 1.00]:
            for slip in [0.0, 1.0, 2.0]:
                for cost in [0.0, 0.35, 0.70]:
                    s_res = simulate_shared_portfolio(test_2026, strat, start_capital=500000.0,
                                                      p_allotment=p_allot, slippage_pct=slip, roundtrip_cost_pct=cost)
                    sens_rows.append({
                        'strategy': strat,
                        'allotment_prob': p_allot,
                        'slippage_pct': slip,
                        'roundtrip_cost_pct': cost,
                        'net_profit_total': s_res['net_profit_total'],
                        'mainboard_contribution': s_res['mainboard_pnl_contribution'],
                        'sme_contribution': s_res['sme_pnl_contribution'],
                        'reconciliation_diff': s_res['reconciliation_diff'],
                        'roi_pct': s_res['roi_total_pct'],
                        'max_drawdown_pct': s_res['max_drawdown_pct'],
                        'allotments_won': s_res['allotments_won_total'],
                        'mean_allotment_return_pct': s_res['mean_allotment_return_pct'],
                        'severe_losses_total': s_res['severe_losses_incurred']
                    })
    df_sens = pd.DataFrame(sens_rows)
    out_sens = 'data/processed/step_8_1_reconciled_sensitivity.csv'
    df_sens.to_csv(out_sens, index=False)
    print(f"Saved Reconciled Sensitivity Matrix to {out_sens} ({len(df_sens)} scenario evaluations)")
    
    print("\nStep 8.1 Audit and Simulation Engine Completed Successfully.")
    return df_reconciled, df_shared_ledger, df_sens

if __name__ == '__main__':
    run_step_8_1_audit()
