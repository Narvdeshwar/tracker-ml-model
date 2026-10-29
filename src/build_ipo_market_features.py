"""
Script: src/build_ipo_market_features.py
Objective: Step 5B - Join market features to IPO master data strictly backward-only as of prediction cutoff.
"""

import os
import pandas as pd
import numpy as np
import openpyxl

def build_ipo_market_features(cutoff_policy='issue_close_date_after_required_data_available'):
    """
    Builds the IPO Market Features dataset using backward-only alignment to avoid lookahead bias.
    Policies supported:
      - 'issue_close_date_after_required_data_available' (Primary)
      - 'listing_eve' (Exploratory / Optional comparison)
    """
    os.makedirs('data/processed', exist_ok=True)
    
    # 1. Load IPO Master data from Excel starter workbook
    wb = openpyxl.load_workbook('Indian_IPO_ML_Research_Starter.xlsx', data_only=True)
    ws_master = wb['IPO_Master']
    headers = [c.value for c in ws_master[1]]
    rows = list(ws_master.iter_rows(min_row=2, values_only=True))
    df_ipo = pd.DataFrame(rows, columns=headers)
    
    # Also load Listing_Outcomes to get target metrics without mixing them as predictors
    ws_outcomes = wb['Listing_Outcomes']
    outcome_headers = [c.value for c in ws_outcomes[1]]
    outcome_rows = list(ws_outcomes.iter_rows(min_row=2, values_only=True))
    df_outcomes = pd.DataFrame(outcome_rows, columns=outcome_headers)
    
    # Merge listing outcome metadata for reference
    df_ipo = df_ipo.merge(
        df_outcomes[['ipo_id', 'listing_open_return_pct', 'listing_close_return_pct', 'verification_status']],
        on='ipo_id',
        how='left',
        suffixes=('', '_outcome')
    )
    
    # 2. Load Market_Daily
    market_daily_path = 'data/processed/market_daily.csv'
    if not os.path.exists(market_daily_path):
        raise FileNotFoundError(f"Missing processed market data: {market_daily_path}")
    df_market = pd.read_csv(market_daily_path)
    df_market['date'] = pd.to_datetime(df_market['date']).dt.strftime('%Y-%m-%d')
    df_market = df_market.sort_values('date').reset_index(drop=True)
    market_dates = df_market['date'].tolist()
    date_to_idx = {d: i for i, d in enumerate(market_dates)}
    
    # 3. Establish Cutoff Date per IPO
    # Supported policy: 'issue_close_date_after_required_data_available'
    records = []
    
    for _, row in df_ipo.iterrows():
        ipo_id = str(row['ipo_id']).strip()
        cname = row['company_name']
        board = row['board_type']
        nse_sym = row['nse_symbol']
        bse_code = row['bse_code']
        isin = row['isin']
        raw_close = row['issue_close_date']
        listing_dt = str(row['listing_date']).strip()
        
        # Standardize dates
        parsed_close = None
        if raw_close is not None and str(raw_close).strip() not in ['', 'None', 'nan', '-']:
            try:
                # Handle potential formats: '23-OCT-2026', '2026-10-23'
                parsed_close = pd.to_datetime(raw_close).strftime('%Y-%m-%d')
            except Exception:
                parsed_close = None

        parsed_listing = None
        if listing_dt not in ['', 'None', 'nan', '-']:
            try:
                parsed_listing = pd.to_datetime(listing_dt).strftime('%Y-%m-%d')
            except Exception:
                parsed_listing = None

        # Determine cutoff based on policy
        if cutoff_policy == 'issue_close_date_after_required_data_available':
            if parsed_close:
                cutoff_date = parsed_close
                cutoff_status = 'verified'
                cutoff_notes = 'Issue close date verified from official exchange issue records'
                cutoff_source = 'Exchange Past Issues Master'
            else:
                cutoff_date = None
                cutoff_status = 'unresolved'
                cutoff_notes = 'Missing issue close date; preserved without synthetic inference'
                cutoff_source = 'Pending Exchange Circular Verification'
        elif cutoff_policy == 'listing_eve':
            # Listing-eve: previous calendar day before listing
            if parsed_listing:
                cutoff_date = (pd.to_datetime(parsed_listing) - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
                cutoff_status = 'listing_eve_derived'
                cutoff_notes = 'Derived strictly as listing_date minus 1 calendar day'
                cutoff_source = 'Derived from Listing Date'
            else:
                cutoff_date = None
                cutoff_status = 'unresolved'
                cutoff_notes = 'Missing listing date'
                cutoff_source = 'Unknown'
        else:
            raise ValueError(f"Unknown cutoff_policy: {cutoff_policy}")

        rec = {
            'ipo_id': ipo_id,
            'company_name': cname,
            'board_type': board,
            'nse_symbol': nse_sym,
            'bse_code': bse_code,
            'isin': isin,
            'issue_price_inr': row['issue_price_inr'],
            'listing_date': parsed_listing,
            'issue_close_date': parsed_close,
            'prediction_cutoff_policy': cutoff_policy,
            'prediction_cutoff_date': cutoff_date,
            'cutoff_status': cutoff_status,
            'cutoff_date_source': cutoff_source,
            'cutoff_validation_notes': cutoff_notes
        }

        # 4. Backward-Only Join for Market Indicators
        if cutoff_status == 'verified' and cutoff_date:
            # Find eligible market observations: date <= cutoff_date
            eligible = df_market[df_market['date'] <= cutoff_date]
            if not eligible.empty:
                latest_obs = eligible.iloc[-1]
                obs_date = latest_obs['date']
                
                # Calculate ages
                cal_age = (pd.to_datetime(cutoff_date) - pd.to_datetime(obs_date)).days
                
                # Session age
                # Find index of obs_date in master market_dates
                obs_idx = date_to_idx.get(obs_date)
                # If cutoff_date is also an observed market date, session age = cutoff_idx - obs_idx
                # Otherwise, it's 0 sessions from the latest completed session
                if cutoff_date in date_to_idx:
                    sess_age = date_to_idx[cutoff_date] - obs_idx
                else:
                    sess_age = 0  # Latest completed session before holiday/weekend cutoff

                rec['source_observation_date'] = obs_date
                rec['observation_age_sessions'] = sess_age
                rec['observation_age_calendar_days'] = cal_age
                rec['feature_available_at_cutoff'] = True
                rec['feature_missing_reason'] = None
                
                # Broad-Market Features
                rec['nifty50_close_at_cutoff'] = latest_obs['nifty50_close']
                rec['nifty50_return_1d'] = latest_obs['nifty50_return_1d']
                rec['nifty50_return_5s'] = latest_obs['nifty50_return_5s']
                rec['nifty50_return_20s'] = latest_obs['nifty50_return_20s']

                rec['nifty500_close_at_cutoff'] = latest_obs['nifty500_close']
                rec['nifty500_return_1d'] = latest_obs['nifty500_return_1d']
                rec['nifty500_return_5s'] = latest_obs['nifty500_return_5s']
                rec['nifty500_return_20s'] = latest_obs['nifty500_return_20s']

                rec['india_vix_level_at_cutoff'] = latest_obs['india_vix_close']
                rec['india_vix_change_5s'] = latest_obs['india_vix_change_5s']
                rec['india_vix_change_20s'] = latest_obs['india_vix_change_20s']
                rec['india_vix_pct_change_5s'] = latest_obs['india_vix_pct_change_5s']
                rec['india_vix_pct_change_20s'] = latest_obs['india_vix_pct_change_20s']

                # Segment-Specific Features
                # Keep separate: do NOT substitute broad market for SME or vice versa
                rec['nifty_sme_emerge_return_1d'] = latest_obs['nifty_sme_emerge_return_1d']
                rec['nifty_sme_emerge_return_5s'] = latest_obs['nifty_sme_emerge_return_5s']
                rec['nifty_sme_emerge_return_20s'] = latest_obs['nifty_sme_emerge_return_20s']

                rec['bse_sme_ipo_return_1d'] = latest_obs['bse_sme_ipo_return_1d']
                rec['bse_sme_ipo_return_5s'] = latest_obs['bse_sme_ipo_return_5s']
                rec['bse_sme_ipo_return_20s'] = latest_obs['bse_sme_ipo_return_20s']
            else:
                rec['source_observation_date'] = None
                rec['observation_age_sessions'] = None
                rec['observation_age_calendar_days'] = None
                rec['feature_available_at_cutoff'] = False
                rec['feature_missing_reason'] = 'Cutoff precedes market history coverage'
                for col in [
                    'nifty50_close_at_cutoff', 'nifty50_return_1d', 'nifty50_return_5s', 'nifty50_return_20s',
                    'nifty500_close_at_cutoff', 'nifty500_return_1d', 'nifty500_return_5s', 'nifty500_return_20s',
                    'india_vix_level_at_cutoff', 'india_vix_change_5s', 'india_vix_change_20s', 'india_vix_pct_change_5s', 'india_vix_pct_change_20s',
                    'nifty_sme_emerge_return_1d', 'nifty_sme_emerge_return_5s', 'nifty_sme_emerge_return_20s',
                    'bse_sme_ipo_return_1d', 'bse_sme_ipo_return_5s', 'bse_sme_ipo_return_20s'
                ]:
                    rec[col] = None
        else:
            rec['source_observation_date'] = None
            rec['observation_age_sessions'] = None
            rec['observation_age_calendar_days'] = None
            rec['feature_available_at_cutoff'] = False
            rec['feature_missing_reason'] = 'Unresolved prediction cutoff date'
            for col in [
                'nifty50_close_at_cutoff', 'nifty50_return_1d', 'nifty50_return_5s', 'nifty50_return_20s',
                'nifty500_close_at_cutoff', 'nifty500_return_1d', 'nifty500_return_5s', 'nifty500_return_20s',
                'india_vix_level_at_cutoff', 'india_vix_change_5s', 'india_vix_change_20s', 'india_vix_pct_change_5s', 'india_vix_pct_change_20s',
                'nifty_sme_emerge_return_1d', 'nifty_sme_emerge_return_5s', 'nifty_sme_emerge_return_20s',
                'bse_sme_ipo_return_1d', 'bse_sme_ipo_return_5s', 'bse_sme_ipo_return_20s'
            ]:
                rec[col] = None

        # Targets kept separate from predictor columns
        rec['target_listing_open_return_pct'] = row.get('listing_open_return_pct')
        rec['target_listing_close_return_pct'] = row.get('listing_close_return_pct')

        records.append(rec)

    df_out = pd.DataFrame(records)
    
    # Save processed CSV
    out_csv = 'data/processed/ipo_market_features.csv'
    df_out.to_csv(out_csv, index=False)
    print(f"Generated {out_csv} with {len(df_out)} IPO records.")
    return df_out

if __name__ == '__main__':
    build_ipo_market_features()
