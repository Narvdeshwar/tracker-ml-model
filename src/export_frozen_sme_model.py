"""
Script: src/export_frozen_sme_model.py
Objective: Train and serialize the exact Model_6B_SME_v1.0 pipeline on Training (2020-2024).
Compute and export cryptographic SHA-256 hash for absolute immutability.
"""

import os
import hashlib
import json
import joblib
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

def export_frozen_model():
    os.makedirs('models/frozen', exist_ok=True)
    
    # 1. Load Step 6A Training Data
    df_ipo = pd.read_csv('data/processed/ipo_features_issue_close.csv')
    df_ipo['listing_year'] = pd.to_datetime(df_ipo['listing_date']).dt.year
    
    # Filter strictly to SME Training (2020-2024)
    df_sme_train = df_ipo[
        (df_ipo['board_type'] == 'SME') &
        (df_ipo['cutoff_status'] == 'verified') &
        (df_ipo['target_listing_open_return_pct'].notnull()) &
        (df_ipo['listing_year'] >= 2020) &
        (df_ipo['listing_year'] <= 2024)
    ].copy()
    
    df_sme_train['feat_nifty50_ret5s_pct'] = df_sme_train['nifty50_return_5s'] * 100.0
    df_sme_train['feat_india_vix'] = df_sme_train['india_vix_level_at_cutoff']
    df_sme_train['feat_recent5_sentiment'] = df_sme_train['recent5_mean_listing_open_return_pct']
    
    feature_cols = ['feat_nifty50_ret5s_pct', 'feat_india_vix', 'feat_recent5_sentiment']
    X_train = df_sme_train[feature_cols]
    y_train = (df_sme_train['target_listing_open_return_pct'] > 0).astype(int).values
    
    # 2. Build and Fit Full End-to-End Pipeline
    # Preprocessor (median imputer + standard scaler) + LogisticRegression(C=1.0, random_state=42)
    pipeline = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler()),
        ('classifier', LogisticRegression(C=1.0, random_state=42))
    ])
    pipeline.fit(X_train, y_train)
    
    # 3. Export Artifact
    model_path = 'models/frozen/model_6b_sme_v1.joblib'
    joblib.dump(pipeline, model_path)
    print(f"Serialized model saved to {model_path}")
    
    # 4. Compute Cryptographic SHA-256
    with open(model_path, 'rb') as f:
        model_bytes = f.read()
        sha256_hash = hashlib.sha256(model_bytes).hexdigest()
        
    metadata = {
        'model_version': 'Model_6B_SME_v1.0',
        'model_name': 'SME Positive-Opening Logistic Classifier',
        'target_definition': 'target_listing_open_return_pct > 0',
        'features': feature_cols,
        'feature_schema_version': 'v1.0',
        'training_cohort': 'SME_2020_2024_Verified_Cutoffs',
        'training_sample_size': len(df_sme_train),
        'training_positive_rate': float(y_train.mean()),
        'sha256_hash': sha256_hash,
        'operating_threshold': 0.50,
        'rank_tier_boundaries': {
            'tier_1_max_prob': 0.8018,
            'tier_2_max_prob': 0.8385
        },
        'status': 'FROZEN_FOR_PROSPECTIVE_EVALUATION'
    }
    
    meta_path = 'models/frozen/model_6b_sme_v1_metadata.json'
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"Model metadata saved to {meta_path} with SHA256: {sha256_hash}")
    return metadata

if __name__ == '__main__':
    export_frozen_model()
