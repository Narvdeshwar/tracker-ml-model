"""
Script: src/build_market_daily.py
Objective: Build standardized, anti-leakage Market_Daily dataset for Indian IPO research.
"""

import os
import pandas as pd
import numpy as np

def load_and_standardize_series(filepath, date_col='date', val_col='close', rename_val='close'):
    """Load a raw price series, sort chronologically, remove duplicates after consistency check."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Source file not found: {filepath}")
    
    df = pd.read_csv(filepath)
    df.columns = [c.strip().lower() for c in df.columns]
    
    # Standardize date to YYYY-MM-DD
    df['date'] = pd.to_datetime(df[date_col], errors='coerce').dt.strftime('%Y-%m-%d')
    df = df.dropna(subset=['date'])
    
    # Clean numeric value
    df[rename_val] = pd.to_numeric(df[val_col], errors='coerce')
    df = df.dropna(subset=[rename_val])
    
    # Deduplicate after checking consistency
    dups = df[df.duplicated(subset=['date'], keep=False)]
    if not dups.empty:
        # Verify if values match
        grp = dups.groupby('date')[rename_val].nunique()
        inconsistent = grp[grp > 1]
        if not inconsistent.empty:
            raise ValueError(f"Inconsistent duplicate dates found in {filepath}: {inconsistent.index.tolist()}")
        df = df.drop_duplicates(subset=['date'], keep='first')
        
    df = df[['date', rename_val]].sort_values('date').reset_index(drop=True)
    return df

def build_market_daily():
    os.makedirs('data/processed', exist_ok=True)
    
    # 1. Load constituent series
    df_nifty50 = load_and_standardize_series('data/inputs/indices/nifty50_price.csv', rename_val='nifty50_close')
    df_vix = load_and_standardize_series('data/inputs/indices/india_vix_price.csv', rename_val='india_vix_close')
    
    # For Nifty 500: use repo official file, spliced seamlessly with verified extension for post-Sept 28, 2026
    df_n500_base = load_and_standardize_series('data/inputs/indices/nifty500_price.csv', rename_val='nifty500_close')
    df_n500_ext = load_and_standardize_series('data/inputs/indices/nifty500_extended_price.csv', rename_val='nifty500_close')
    max_base_date = df_n500_base['date'].max()
    df_n500_post = df_n500_ext[df_n500_ext['date'] > max_base_date]
    df_nifty500 = pd.concat([df_n500_base, df_n500_post], ignore_index=True).sort_values('date').reset_index(drop=True)
    
    # SME series
    df_nifty_sme = load_and_standardize_series('data/inputs/indices/nifty_sme_emerge_price.csv', rename_val='nifty_sme_emerge_close')
    df_bse_sme = load_and_standardize_series('data/inputs/indices/bse_sme_ipo_price.csv', rename_val='bse_sme_ipo_close')
    
    # 2. Master trading calendar: derived from observed Nifty 50 sessions (the primary exchange calendar)
    master_dates = pd.DataFrame({'date': sorted(df_nifty50['date'].unique())})
    
    # Merge all series onto master trading dates (Left join to preserve verified trading sessions)
    m = master_dates.merge(df_nifty50, on='date', how='left')
    m = m.merge(df_nifty500, on='date', how='left')
    m = m.merge(df_vix, on='date', how='left')
    m = m.merge(df_nifty_sme, on='date', how='left')
    m = m.merge(df_bse_sme, on='date', how='left')
    
    # Sort chronologically
    m = m.sort_values('date').reset_index(drop=True)
    
    # 3. Calculate anti-leakage rolling trading session returns
    # Strictly session-based: t vs t-1, t vs t-5, t vs t-20
    for prefix in ['nifty50', 'nifty500', 'nifty_sme_emerge', 'bse_sme_ipo']:
        col = f'{prefix}_close'
        m[f'{prefix}_return_1d'] = (m[col] / m[col].shift(1) - 1).round(6)
        m[f'{prefix}_return_5s'] = (m[col] / m[col].shift(5) - 1).round(6)
        m[f'{prefix}_return_20s'] = (m[col] / m[col].shift(20) - 1).round(6)
        
    # 4. Calculate India VIX changes (absolute level delta and percentage changes)
    m['india_vix_change_5s'] = (m['india_vix_close'] - m['india_vix_close'].shift(5)).round(4)
    m['india_vix_change_20s'] = (m['india_vix_close'] - m['india_vix_close'].shift(20)).round(4)
    m['india_vix_pct_change_5s'] = (m['india_vix_close'] / m['india_vix_close'].shift(5) - 1).round(6)
    m['india_vix_pct_change_20s'] = (m['india_vix_close'] / m['india_vix_close'].shift(20) - 1).round(6)
    
    # Output path
    out_csv = 'data/processed/market_daily.csv'
    m.to_csv(out_csv, index=False)
    print(f"Successfully generated {out_csv}: {len(m)} trading sessions ({m['date'].min()} to {m['date'].max()})")
    return m

if __name__ == '__main__':
    build_market_daily()
