"""
Script: src/build_step_7b_subscription_pipeline.py
Objective: Step 7B - Historical IPO Subscription Data Ingestion & Snapshot Framework.
Builds:
  - data/processed/ipo_subscription_observations.csv
  - data/processed/ipo_subscription_features.csv
  - data/processed/step_7b_subscription_coverage.csv
  - data/processed/step_7b_subscription_conflicts.csv
  - data/processed/step_7b_subscription_unresolved.csv
"""

import os
import datetime
import pandas as pd
import numpy as np

def build_subscription_pipeline():
    print("Building Step 7B Subscription Observation & Snapshot Framework...")
    os.makedirs('data/processed', exist_ok=True)
    
    # 1. Load Master Dataset and Cutoff Recovery Data
    df_master = pd.read_excel('Indian_IPO_ML_Research_Starter.xlsx', sheet_name='IPO_Master')
    df_cutoff = pd.read_csv('data/processed/ipo_cutoff_recovery.csv')
    df_features = pd.read_csv('data/processed/ipo_features_issue_close.csv')
    
    # 2. Schema Definition for Canonical Subscription Observations
    # We inspect existing subscription sources across exchanges.
    # Currently, primary exchange subscription tables provide verified day-by-day bidding updates.
    # In the starter workbook, the Subscription_History sheet was initialized as an empty schema.
    # We populate the canonical schema with verified records where available, and queue remaining IPOs.
    
    retrieval_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
    
    obs_cols = [
        'ipo_id', 'issuer_name', 'market_segment', 'issue_open_date', 'issue_close_date',
        'subscription_category', 'subscription_multiple', 'observation_date',
        'observation_timestamp', 'publication_timestamp', 'retrieval_timestamp',
        'source_name', 'source_url_or_document_reference', 'source_type',
        'verification_status', 'reported_value', 'normalized_value',
        'normalization_method', 'missingness_reason', 'notes'
    ]
    
    # Check if any observations exist in raw/processed sources
    # Currently 0 rows exist in Subscription_History. We build the auditable canonical dataset.
    observations = []
    conflicts = []
    unresolved_sources = []
    
    for idx, row in df_cutoff.iterrows():
        ipo_id = row['ipo_id']
        issuer = row['issuer_name']
        segment = row['market_segment']
        open_d = row['issue_open_date']
        close_d = row['issue_close_date']
        v_status = row['verification_status']
        
        # If cutoff is verified, subscription data can be mapped to bidding schedule
        if v_status == 'VERIFIED_PRIMARY_SOURCE' and pd.notna(close_d):
            # Record queued status for subscription data extraction from exchange bidding archives
            unresolved_sources.append({
                'ipo_id': ipo_id,
                'issuer_name': issuer,
                'market_segment': segment,
                'issue_open_date': open_d,
                'issue_close_date': close_d,
                'bidding_schedule_status': 'CUTOFF_VERIFIED',
                'target_categories': 'QIB,NII,RETAIL,TOTAL',
                'required_snapshots': 'DAY1_SNAPSHOT,DAY2_SNAPSHOT,DAY3_SNAPSHOT,FINAL_SNAPSHOT',
                'primary_source_target': 'NSE/BSE Daily Bidding Details Circulars',
                'status': 'AWAITING_EXCHANGE_BID_ARCHIVE_INGESTION',
                'notes': 'Cutoff verified; daily bid logs require raw exchange bidding log extraction.'
            })
        else:
            # Cutoff unresolved or conflicted
            unresolved_sources.append({
                'ipo_id': ipo_id,
                'issuer_name': issuer,
                'market_segment': segment,
                'issue_open_date': open_d,
                'issue_close_date': close_d,
                'bidding_schedule_status': 'CUTOFF_UNRESOLVED_OR_CONFLICT',
                'target_categories': 'QIB,NII,RETAIL,TOTAL',
                'required_snapshots': 'BLOCKED_PENDING_CUTOFF_RECOVERY',
                'primary_source_target': 'BSE SME Public Circulars / Prospectus',
                'status': 'BLOCKED_BY_MISSING_CUTOFF',
                'notes': 'Cannot construct day-by-day subscription snapshots without verified bidding opening/closing dates.'
            })
            
    df_obs = pd.DataFrame(observations, columns=obs_cols)
    out_obs = 'data/processed/ipo_subscription_observations.csv'
    df_obs.to_csv(out_obs, index=False)
    print(f"Saved canonical subscription observations to {out_obs} ({len(df_obs)} rows)")
    
    df_conflicts = pd.DataFrame(conflicts, columns=obs_cols + ['conflict_reason'])
    out_conflicts = 'data/processed/step_7b_subscription_conflicts.csv'
    df_conflicts.to_csv(out_conflicts, index=False)
    print(f"Saved subscription conflicts to {out_conflicts} ({len(df_conflicts)} rows)")
    
    df_unres = pd.DataFrame(unresolved_sources)
    out_unres = 'data/processed/step_7b_subscription_unresolved.csv'
    df_unres.to_csv(out_unres, index=False)
    print(f"Saved subscription unresolved queue to {out_unres} ({len(df_unres)} rows)")
    
    # 3. Build Subscription Features Dataset (Snapshot Schema)
    # Defines the 4 snapshot cutoffs per IPO: DAY1, DAY2, DAY3, FINAL
    feat_cols = [
        'ipo_id', 'issuer_name', 'market_segment', 'snapshot_type',
        'intended_prediction_timestamp', 'actual_cutoff_timestamp',
        'qib_subscription_multiple', 'nii_subscription_multiple',
        'retail_subscription_multiple', 'total_subscription_multiple',
        'demand_change_vs_prior_snapshot', 'retail_to_qib_ratio',
        'latest_observation_publication_timestamp',
        'timing_validity_status', 'rejection_reason'
    ]
    
    feature_rows = []
    # Build skeleton snapshots for research framework
    for idx, row in df_cutoff.iterrows():
        ipo_id = row['ipo_id']
        issuer = row['issuer_name']
        segment = row['market_segment']
        close_d = row['issue_close_date']
        v_status = row['verification_status']
        
        for snap in ['DAY1_SNAPSHOT', 'DAY2_SNAPSHOT', 'DAY3_SNAPSHOT', 'FINAL_SNAPSHOT']:
            if v_status != 'VERIFIED_PRIMARY_SOURCE' or pd.isna(close_d):
                t_valid = 'TIMING_UNVERIFIED'
                rej_reason = 'Unresolved issue cutoff date'
            else:
                t_valid = 'DATA_PENDING_EXTRACTION'
                rej_reason = 'Subscription observation pending primary exchange bid log parsing'
                
            feature_rows.append({
                'ipo_id': ipo_id,
                'issuer_name': issuer,
                'market_segment': segment,
                'snapshot_type': snap,
                'intended_prediction_timestamp': f"{close_d} 17:00:00 IST" if pd.notna(close_d) else None,
                'actual_cutoff_timestamp': f"{close_d} 17:00:00 IST" if pd.notna(close_d) else None,
                'qib_subscription_multiple': np.nan,
                'nii_subscription_multiple': np.nan,
                'retail_subscription_multiple': np.nan,
                'total_subscription_multiple': np.nan,
                'demand_change_vs_prior_snapshot': np.nan,
                'retail_to_qib_ratio': np.nan,
                'latest_observation_publication_timestamp': None,
                'timing_validity_status': t_valid,
                'rejection_reason': rej_reason
            })
            
    df_feats = pd.DataFrame(feature_rows, columns=feat_cols)
    out_feats = 'data/processed/ipo_subscription_features.csv'
    df_feats.to_csv(out_feats, index=False)
    print(f"Saved subscription feature snapshots to {out_feats} ({len(df_feats)} rows)")
    
    # 4. Coverage Report Summary
    cov_summary = []
    df_cutoff['listing_year'] = pd.to_datetime(df_master['listing_date']).dt.year
    for (year, segment), grp in df_cutoff.groupby(['listing_year', 'market_segment']):
        tot = len(grp)
        v_cutoffs = (grp['verification_status'] == 'VERIFIED_PRIMARY_SOURCE').sum()
        
        cov_summary.append({
            'listing_year': int(year),
            'market_segment': segment,
            'total_ipos': tot,
            'cutoff_verified_ipos': int(v_cutoffs),
            'qib_verified_count': 0,
            'nii_verified_count': 0,
            'retail_verified_count': 0,
            'total_sub_verified_count': 0,
            'day1_snapshot_available': 0,
            'day2_snapshot_available': 0,
            'day3_snapshot_available': 0,
            'final_snapshot_available': 0,
            'timestamped_subscription_coverage_pct': 0.0,
            'timing_unverified_count': tot
        })
        
    df_cov = pd.DataFrame(cov_summary).sort_values(['listing_year', 'market_segment'])
    out_cov = 'data/processed/step_7b_subscription_coverage.csv'
    df_cov.to_csv(out_cov, index=False)
    print(f"Saved subscription coverage report to {out_cov} ({len(df_cov)} rows)")
    
    print("Step 7B subscription pipeline build complete.")
    return df_obs, df_feats, df_cov, df_conflicts, df_unres

if __name__ == '__main__':
    build_subscription_pipeline()
