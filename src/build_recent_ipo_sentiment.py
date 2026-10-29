"""
Script: src/build_recent_ipo_sentiment.py
Objective: Step 5C - Calculate rolling Recent IPO Sentiment strictly chronologically.
Only IPOs whose listing outcomes were observable before each target IPO's cutoff timestamp are used.
"""

import os
import pandas as pd
import numpy as np

def build_recent_ipo_sentiment():
    os.makedirs('data/processed', exist_ok=True)
    
    # 1. Load IPO Market Features dataset
    df_ipo = pd.read_csv('data/processed/ipo_market_features.csv')
    
    # We need: ipo_id, board_type, listing_date, target_listing_open_return_pct, target_listing_close_return_pct
    # For sentiment candidate outcomes:
    # A prior IPO i is observable at cutoff date D if prior_ipo.listing_date < D
    # Note: If prior IPO lists on date L, its outcome is observable after market close on L (or next day pre-open).
    # Therefore, strictly: prior_ipo.listing_date < target_ipo.prediction_cutoff_date
    
    # Filter candidates with valid listing_date and target returns
    candidates = df_ipo.dropna(subset=['listing_date', 'target_listing_open_return_pct']).copy()
    candidates['listing_date'] = pd.to_datetime(candidates['listing_date'])
    candidates = candidates.sort_values(['listing_date', 'ipo_id']).reset_index(drop=True)
    
    sentiment_records = []
    
    for _, row in df_ipo.iterrows():
        ipo_id = row['ipo_id']
        cutoff_status = row['cutoff_status']
        cutoff_date_str = row['prediction_cutoff_date']
        
        rec = {
            'ipo_id': ipo_id,
            'prediction_cutoff_date': cutoff_date_str,
            'cutoff_status': cutoff_status,
            'recent5_count': 0,
            'recent5_mean_listing_open_return_pct': None,
            'recent5_median_listing_open_return_pct': None,
            'recent5_positive_listing_rate': None,
            'recent10_count': 0,
            'recent10_mean_listing_open_return_pct': None,
            'recent10_median_listing_open_return_pct': None,
            'recent10_positive_listing_rate': None,
            'sentiment_missing_reason': None
        }
        
        if cutoff_status != 'verified' or pd.isnull(cutoff_date_str):
            rec['sentiment_missing_reason'] = 'Unresolved prediction cutoff date'
            sentiment_records.append(rec)
            continue
            
        cutoff_dt = pd.to_datetime(cutoff_date_str)
        
        # Eligible prior IPOs: listing_date strictly before cutoff_dt
        # (guarantees listing outcome was already published before bidding closed on cutoff_dt)
        prior_eligible = candidates[candidates['listing_date'] < cutoff_dt]
        
        if len(prior_eligible) < 5:
            rec['sentiment_missing_reason'] = f'Insufficient prior listing history (only {len(prior_eligible)} available)'
            rec['recent5_count'] = len(prior_eligible)
            rec['recent10_count'] = len(prior_eligible)
            sentiment_records.append(rec)
            continue
            
        # Select last 5 and last 10 prior eligible IPOs
        last5 = prior_eligible.tail(5)
        last10 = prior_eligible.tail(10)
        
        # Calculate recent 5 metrics
        rec['recent5_count'] = len(last5)
        rec['recent5_mean_listing_open_return_pct'] = round(float(last5['target_listing_open_return_pct'].mean()), 2)
        rec['recent5_median_listing_open_return_pct'] = round(float(last5['target_listing_open_return_pct'].median()), 2)
        rec['recent5_positive_listing_rate'] = round(float((last5['target_listing_open_return_pct'] > 0).mean()), 4)
        
        # Calculate recent 10 metrics
        rec['recent10_count'] = len(last10)
        rec['recent10_mean_listing_open_return_pct'] = round(float(last10['target_listing_open_return_pct'].mean()), 2)
        rec['recent10_median_listing_open_return_pct'] = round(float(last10['target_listing_open_return_pct'].median()), 2)
        rec['recent10_positive_listing_rate'] = round(float((last10['target_listing_open_return_pct'] > 0).mean()), 4)
        
        sentiment_records.append(rec)
        
    df_sent = pd.DataFrame(sentiment_records)
    out_csv = 'data/processed/ipo_sentiment_features.csv'
    df_sent.to_csv(out_csv, index=False)
    print(f"Generated {out_csv} with {len(df_sent)} records.")
    return df_sent

if __name__ == '__main__':
    build_recent_ipo_sentiment()
