"""
Module: src/phase_9b_preflight_runner.py
Objective: Run a comprehensive preflight validation for Phase 9B shadow logging candidates.
Verifies:
  1. Frozen Model and Manifest Integrity (Bit-for-bit SHA-256 match).
  2. Model Coverage Restriction (SME allowed for scoring; Mainboard tracked for coverage only).
  3. Authoritative Cutoff Evidence Contract (source URL, evidence text, timezone IST/+05:30).
  4. Feature Snapshot & Pre-Cutoff Timing Verification (source pub time <= cutoff time).
  5. Dry-run ledger append simulation (without modifying live ledgers).
  6. Three-Population Cohort Allocation (All eligible, Clean prospective, Excluded/Unverified).
"""

import os
import json
import hashlib
import datetime
import pandas as pd
import numpy as np
import joblib

from src.prospective_simulator_logger import ProspectiveDecisionLogger

MANIFEST_PATH = 'models/frozen/phase_9b_baseline_manifest.json'

def verify_manifest_and_models():
    """Verifies baseline manifest existence and frozen model hashes."""
    if not os.path.exists(MANIFEST_PATH):
        return {'status': 'FAIL', 'error': f'Manifest not found at {MANIFEST_PATH}'}
    
    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
        
    results = {'manifest_version': manifest.get('manifest_version'), 'models': {}}
    for model_name, model_info in manifest.get('frozen_baseline_models', {}).items():
        m_path = model_info.get('path')
        expected_sha = model_info.get('sha256')
        if not os.path.exists(m_path):
            results['models'][model_name] = {'status': 'FAIL', 'error': 'Artifact missing'}
            continue
        with open(m_path, 'rb') as f:
            actual_sha = hashlib.sha256(f.read()).hexdigest()
        match = (actual_sha == expected_sha)
        results['models'][model_name] = {
            'status': 'PASS' if match else 'FAIL',
            'path': m_path,
            'expected_sha': expected_sha,
            'actual_sha': actual_sha,
            'match': match
        }
    return results

def score_sme_candidate_dry_run(features_dict):
    """
    Dry-run scoring for an SME candidate using frozen Model_6B_SME_v1.0 pipeline artifact.
    Expects features:
      - 'feat_nifty50_ret5s_pct' (or 'nifty50_return_5s' which will be multiplied by 100)
      - 'feat_india_vix' (or 'india_vix_level_at_cutoff')
      - 'feat_recent5_sentiment' (or 'recent5_positive_listing_rate' / sentiment return)
    """
    model_path = 'models/frozen/model_6b_sme_v1.joblib'
    model = joblib.load(model_path)
    
    # Map input features flexibly to the pipeline's expected columns
    nifty5s = features_dict.get('feat_nifty50_ret5s_pct')
    if nifty5s is None and 'nifty50_return_5s' in features_dict:
        nifty5s = features_dict['nifty50_return_5s'] * 100.0
        
    vix = features_dict.get('feat_india_vix')
    if vix is None and 'india_vix_level_at_cutoff' in features_dict:
        vix = features_dict['india_vix_level_at_cutoff']
        
    sent = features_dict.get('feat_recent5_sentiment')
    if sent is None and 'recent5_positive_listing_rate' in features_dict:
        sent = features_dict['recent5_positive_listing_rate'] * 100.0
    elif sent is None and 'recent5_mean_listing_open_return_pct' in features_dict:
        sent = features_dict['recent5_mean_listing_open_return_pct']
        
    row = {
        'feat_nifty50_ret5s_pct': nifty5s,
        'feat_india_vix': vix,
        'feat_recent5_sentiment': sent
    }
    
    for k, v in row.items():
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            raise ValueError(f"Invalid feature value for {k}: {v}")
            
    df_in = pd.DataFrame([row])
    p_pos = float(model.predict_proba(df_in)[0, 1])
    return {
        'model_name': 'Model_6B_SME_v1.0',
        'p_positive_open': round(p_pos, 4),
        'p_macro': round(p_pos, 4)
    }

def run_candidate_preflight(candidate_dict, dry_run_ledger_path='data/processed/dry_run_preflight_ledger.jsonl'):
    """
    Executes a formal preflight check for a candidate issue.
    """
    report = {
        'ipo_id': candidate_dict['ipo_id'],
        'company_name': candidate_dict['company_name'],
        'board_type': candidate_dict['board_type'],
        'checks': {},
        'cohort_allocation': None,
        'scoring_status': None
    }
    
    # 1. Manifest and Model Check
    manifest_audit = verify_manifest_and_models()
    report['checks']['manifest_verification'] = manifest_audit
    
    # 2. Model Coverage Restriction Check
    board = candidate_dict['board_type']
    if board == 'Mainboard':
        report['scoring_status'] = 'NO_FROZEN_MODEL_REGISTER_FOR_COVERAGE_ONLY'
        report['checks']['model_coverage_restriction'] = {
            'status': 'RESTRICTED',
            'detail': 'Phase 9B manifest has no frozen Mainboard model artifact. Model scores MUST NOT be invented.'
        }
    elif board == 'SME':
        report['scoring_status'] = 'ELIGIBLE_FOR_FROZEN_SME_MODEL'
        report['checks']['model_coverage_restriction'] = {
            'status': 'PASS',
            'detail': 'SME issue eligible for frozen Model_6B_SME_v1.0 evaluation.'
        }
    else:
        report['scoring_status'] = 'INVALID_BOARD_TYPE'
        report['checks']['model_coverage_restriction'] = {'status': 'FAIL', 'detail': f'Unknown board: {board}'}
        
    # 3. Cutoff & Timezone Verification
    cutoff_ts = candidate_dict.get('cutoff_timestamp_ist')
    prov = candidate_dict.get('feature_provenance', {})
    
    has_tz = False
    if cutoff_ts and isinstance(cutoff_ts, str):
        has_tz = any(tz in cutoff_ts for tz in ['IST', '+05:30', '+0530'])
        
    has_evidence = bool(prov.get('cutoff_source_evidence') or prov.get('source_url_or_doc'))
    has_raw_hash = bool(prov.get('raw_source_sha256'))
    is_timing_ver = bool(prov.get('is_timing_verified', False))
    
    report['checks']['cutoff_timezone_present'] = {'status': 'PASS' if has_tz else 'FAIL', 'cutoff_ts': cutoff_ts}
    report['checks']['authoritative_evidence_present'] = {'status': 'PASS' if has_evidence else 'FAIL', 'evidence': prov.get('cutoff_source_evidence')}
    report['checks']['raw_checksum_present'] = {'status': 'PASS' if has_raw_hash else 'FAIL', 'hash': prov.get('raw_source_sha256')}
    report['checks']['timing_verified_flag'] = {'status': 'PASS' if is_timing_ver else 'FAIL', 'value': is_timing_ver}
    
    # Check publication timestamp vs cutoff
    pub_ts = prov.get('source_publication_timestamp_ist')
    chrono_pass = True
    if pub_ts and cutoff_ts:
        try:
            clean_pub = pub_ts.replace(' IST', '').replace('+05:30', '').replace('+0530', '').strip()
            clean_cut = cutoff_ts.replace(' IST', '').replace('+05:30', '').replace('+0530', '').strip()
            chrono_pass = pd.to_datetime(clean_pub) <= pd.to_datetime(clean_cut)
        except Exception:
            chrono_pass = False
    report['checks']['pre_cutoff_chronological_consistency'] = {'status': 'PASS' if chrono_pass else 'FAIL', 'pub_ts': pub_ts, 'cutoff_ts': cutoff_ts}
    
    # Determine Population Cohort
    all_checks_passed = (has_tz and has_evidence and has_raw_hash and is_timing_ver and chrono_pass)
    if all_checks_passed:
        report['cohort_allocation'] = 'Population_2_Clean_Prospective'
    else:
        report['cohort_allocation'] = 'Population_3_Excluded_Unverified'
        
    # 4. Feature Contract & Scoring (if SME)
    if board == 'SME' and all_checks_passed:
        try:
            scores = score_sme_candidate_dry_run(candidate_dict.get('features', {}))
            report['dry_run_scores'] = scores
            report['checks']['feature_contract'] = {'status': 'PASS'}
        except Exception as e:
            report['checks']['feature_contract'] = {'status': 'FAIL', 'error': str(e)}
            report['cohort_allocation'] = 'Population_3_Excluded_Unverified'
    else:
        report['dry_run_scores'] = None
        
    # 5. Dry-run ledger append simulation (isolated temporary ledger)
    logger = ProspectiveDecisionLogger(
        decision_ledger_path=dry_run_ledger_path,
        outcome_ledger_path='data/processed/dry_run_preflight_out_tmp.jsonl'
    )
    
    p_pos = report.get('dry_run_scores', {}).get('p_positive_open') if report.get('dry_run_scores') else 0.50
    p_mac = report.get('dry_run_scores', {}).get('p_macro') if report.get('dry_run_scores') else 0.50
    p_loss = 0.05
    
    dry_append = logger.record_prospective_decision(
        ipo_id=candidate_dict['ipo_id'],
        company_name=candidate_dict['company_name'],
        board_type=board,
        cutoff_timestamp_ist=cutoff_ts,
        features_dict=candidate_dict.get('features', {}),
        p_positive_open=p_pos if board == 'SME' else 0.50, # Marker if non-scored
        p_macro=p_mac if board == 'SME' else 0.50,
        p_severe_loss=p_loss,
        model_name='Model_6B_SME_v1.0' if board == 'SME' else 'REGISTER_FOR_COVERAGE_ONLY',
        model_sha256='dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76' if board == 'SME' else 'NO_FROZEN_MODEL',
        feature_provenance=candidate_dict.get('feature_provenance'),
        data_quality_warnings=['MAINBOARD_COVERAGE_TRACKING_ONLY_NO_FROZEN_MODEL'] if board == 'Mainboard' else []
    )
    report['checks']['dry_run_ledger_append'] = dry_append
    
    # Clean up dry-run files
    if os.path.exists(dry_run_ledger_path):
        os.remove(dry_run_ledger_path)
    if os.path.exists('data/processed/dry_run_preflight_out_tmp.jsonl'):
        os.remove('data/processed/dry_run_preflight_out_tmp.jsonl')
        
    return report
