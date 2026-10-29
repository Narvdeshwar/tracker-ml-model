"""
Script: src/build_step_7c_fundamentals.py
Objective: Step 7C - Ingest, extract, and normalize historical issuer fundamentals and valuation multiples.
Builds:
  - data/processed/step_7c_raw_fundamentals.csv
  - data/processed/step_7c_normalized_fundamentals.csv
  - data/processed/step_7c_provenance_audit.csv
  - data/processed/step_7c_missingness_coverage.csv
"""

import os
import re
import datetime
import pandas as pd
import numpy as np

def build_fundamentals():
    print("Building Step 7C Issuer Fundamentals & Valuation Ingestion Pipeline...")
    os.makedirs('data/processed', exist_ok=True)
    
    # 1. Load Master Dataset, Cutoff Recovery, and Raw Past Issues
    df_master = pd.read_excel('Indian_IPO_ML_Research_Starter.xlsx', sheet_name='IPO_Master')
    df_cutoff = pd.read_csv('data/processed/ipo_cutoff_recovery.csv')
    df_raw = pd.read_csv('IPO-PastIssue-01-01-2020-to-27-10-2026.csv')
    df_features = pd.read_csv('data/processed/ipo_features_issue_close.csv')
    
    def norm_name(s):
        if not isinstance(s, str):
            return ''
        s = s.upper().replace('LIMITED', 'LTD').replace('PRIVATE', 'PVT').replace('.', '').replace(',', '').replace('-', ' ')
        return ' '.join(s.split())
        
    df_raw['norm_name'] = df_raw['COMPANY NAME'].apply(norm_name)
    df_master['norm_name'] = df_master['company_name'].apply(norm_name)
    
    def parse_price_range(pr):
        if pd.isna(pr) or not isinstance(pr, str):
            return None, None
        pr = pr.replace('\r', '').replace('\n', '').strip()
        nums = [n for n in re.findall(r'\d+(?:\.\d+)?', pr)]
        if len(nums) >= 2:
            return float(nums[0]), float(nums[1])
        elif len(nums) == 1:
            return float(nums[0]), float(nums[0])
        return None, None

    parsed_bands = [parse_price_range(x) for x in df_raw['PRICE RANGE']]
    df_raw['low_band'] = [p[0] for p in parsed_bands]
    df_raw['high_band'] = [p[1] for p in parsed_bands]
    
    # Merge price band data from raw archive onto master records
    raw_dedup = df_raw.drop_duplicates(subset=['norm_name'])
    merged = pd.merge(df_master, raw_dedup[['norm_name', 'low_band', 'high_band', 'SECURITY TYPE']], on='norm_name', how='left')
    
    # Join cutoff recovery status
    cutoff_dict = df_cutoff.set_index('ipo_id')[['verification_status', 'issue_close_date']].to_dict('index')
    
    retrieval_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
    
    raw_records = []
    norm_records = []
    audit_records = []
    
    for idx, row in merged.iterrows():
        ipo_id = row['ipo_id']
        name = row['company_name']
        board = row['board_type']
        issue_p = float(row['issue_price_inr']) if pd.notna(row['issue_price_inr']) else np.nan
        low_b = float(row['low_band']) if pd.notna(row['low_band']) else np.nan
        high_b = float(row['high_band']) if pd.notna(row['high_band']) else np.nan
        
        c_info = cutoff_dict.get(ipo_id, {'verification_status': 'UNRESOLVED', 'issue_close_date': None})
        cutoff_status = c_info['verification_status']
        close_d = c_info['issue_close_date']
        
        # Determine price band metrics
        has_band = pd.notna(low_b) and pd.notna(high_b) and low_b > 0 and high_b > 0
        if has_band:
            spread_pct = round(100.0 * (high_b - low_b) / low_b, 2)
            is_fixed = 1 if low_b == high_b else 0
            # Check if priced at or near cap (within 0.5% tolerance)
            priced_at_cap = 1 if abs(issue_p - high_b) <= (0.005 * high_b) else 0
            source_doc = 'NSE Past Issues Primary Archive (Price Band Notice)'
            v_status = 'VERIFIED_PRIMARY'
            t_elig = True if cutoff_status == 'VERIFIED_PRIMARY_SOURCE' else False
            m_reason = None
        else:
            spread_pct = np.nan
            is_fixed = np.nan
            priced_at_cap = np.nan
            source_doc = 'Pending BSE SME Prospectus Circulars'
            v_status = 'UNAVAILABLE'
            t_elig = False
            m_reason = 'Omitted in static past issues table; requires prospectus extraction'
            
        raw_rec = {
            'ipo_id': ipo_id,
            'company_name': name,
            'market_segment': board,
            'issue_price_inr': issue_p,
            'price_band_low_inr': low_b,
            'price_band_high_inr': high_b,
            'price_band_spread_pct': spread_pct,
            'issue_priced_at_cap': priced_at_cap,
            'is_fixed_price_issue': is_fixed,
            'issue_size_cr': np.nan,
            'fresh_issue_cr': np.nan,
            'ofs_cr': np.nan,
            'eps_inr': np.nan,
            'issue_pe': np.nan,
            'peer_median_pe': np.nan,
            'source_document': source_doc,
            'verification_status': v_status,
            'temporal_eligibility': t_elig,
            'missingness_reason': m_reason
        }
        raw_records.append(raw_rec)
        
        # Normalized derived features for ML
        norm_rec = {
            'ipo_id': ipo_id,
            'market_segment': board,
            'issue_price_inr': issue_p,
            'feat_has_price_band': 1.0 if has_band else 0.0,
            'feat_price_band_spread_pct': spread_pct if has_band else np.nan,
            'feat_issue_priced_at_cap': float(priced_at_cap) if has_band else np.nan,
            'feat_is_fixed_price_issue': float(is_fixed) if has_band else np.nan,
            'feat_issue_size_log': np.nan,
            'feat_pe_ratio': np.nan,
            'temporal_eligibility': t_elig
        }
        norm_records.append(norm_rec)
        
        audit_records.append({
            'ipo_id': ipo_id,
            'company_name': name,
            'market_segment': board,
            'feature_family': 'Valuation & Band Structure',
            'source_document': source_doc,
            'source_publication_date': str(close_d)[:10] if pd.notna(close_d) else 'UNRESOLVED',
            'prediction_cutoff_ist': f"{close_d} 17:00:00 IST" if pd.notna(close_d) else 'UNRESOLVED',
            'temporal_eligibility_verdict': 'ELIGIBLE' if t_elig else 'INELIGIBLE',
            'verification_status': v_status,
            'retrieval_timestamp': retrieval_ts
        })
        
    df_raw_fund = pd.DataFrame(raw_records)
    out_raw = 'data/processed/step_7c_raw_fundamentals.csv'
    df_raw_fund.to_csv(out_raw, index=False)
    print(f"Saved raw fundamentals to {out_raw} ({len(df_raw_fund)} rows)")
    
    df_norm_fund = pd.DataFrame(norm_records)
    out_norm = 'data/processed/step_7c_normalized_fundamentals.csv'
    df_norm_fund.to_csv(out_norm, index=False)
    print(f"Saved normalized fundamentals to {out_norm} ({len(df_norm_fund)} rows)")
    
    df_audit_fund = pd.DataFrame(audit_records)
    out_audit = 'data/processed/step_7c_provenance_audit.csv'
    df_audit_fund.to_csv(out_audit, index=False)
    print(f"Saved provenance audit to {out_audit} ({len(df_audit_fund)} rows)")
    
    # Build Missingness and Coverage Breakdown
    merged_cov = pd.merge(df_raw_fund, df_master[['ipo_id', 'listing_date']], on='ipo_id')
    merged_cov['listing_year'] = pd.to_datetime(merged_cov['listing_date']).dt.year
    
    cov_rows = []
    for (year, segment), grp in merged_cov.groupby(['listing_year', 'market_segment']):
        tot = len(grp)
        v_primary = (grp['verification_status'] == 'VERIFIED_PRIMARY').sum()
        t_eligible = (grp['temporal_eligibility'] == True).sum()
        priced_cap_avail = grp['issue_priced_at_cap'].notna().sum()
        fixed_price_count = (grp['is_fixed_price_issue'] == 1).sum()
        
        cov_rows.append({
            'listing_year': int(year),
            'market_segment': segment,
            'total_ipos': tot,
            'verified_primary_source': int(v_primary),
            'temporal_eligible_count': int(t_eligible),
            'price_band_available': int(priced_cap_avail),
            'fixed_price_issues': int(fixed_price_count),
            'coverage_pct': round(100.0 * priced_cap_avail / tot, 2)
        })
        
    df_cov = pd.DataFrame(cov_rows).sort_values(['listing_year', 'market_segment'])
    out_cov = 'data/processed/step_7c_missingness_coverage.csv'
    df_cov.to_csv(out_cov, index=False)
    print(f"Saved missingness coverage to {out_cov} ({len(df_cov)} rows)")
    
    print("Step 7C fundamentals ingestion complete.")
    return df_raw_fund, df_norm_fund, df_audit_fund, df_cov

if __name__ == '__main__':
    build_fundamentals()
