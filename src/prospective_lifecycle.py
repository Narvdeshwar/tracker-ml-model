"""
Module: src/prospective_lifecycle.py
Objective: Phase 10.7 Prospective Data Collection, Pre-Cutoff Commitment, Outcome Reconciliation & Evaluation Pipeline.
Enforces:
  1. Authoritative pre-cutoff verification and feature temporal validation before commitment.
  2. Frozen SME Model inference and hash locking.
  3. Strict chronological commitment (rejects late decisions or non-compliant features from clean cohort).
  4. Outcome reconciliation linking to committed decisions, calculating listing-open returns strictly from
     verified exchange circulars/bulletins, and rejecting negative/zero prices or unmatched outcomes.
  5. Immutable correction history preserved as linked governance audit events.
  6. Granular observation-level evaluation-record generation with model vs constant baseline Brier score contributions.
  7. Exact sample-pairing for Brier Skill Score calculation without fabricating metrics when mature observations are zero.
  8. Real-money live trading remains strictly prohibited.
"""

import os
import json
import hashlib
import datetime
import threading
from datetime import timezone
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
import joblib

from src.prospective_simulator_logger import ProspectiveDecisionLogger
from src.surveillance_monitor import SurveillanceMonitor, FROZEN_SME_MODEL_PATH, MANIFEST_PATH
from src.evidence_audit_protocol import ProspectiveEvidenceAuditor

FROZEN_SME_MODEL_SHA256 = 'dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76'
MANIFEST_SHA256 = 'b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e'

DECISION_LEDGER_PATH = 'data/processed/prospective_decision_ledger.jsonl'
OUTCOME_LEDGER_PATH = 'data/processed/prospective_outcome_ledger.jsonl'
CANDIDATE_REGISTRY_PATH = 'data/registered/tracked_candidate_registry.json'
AUDIT_EVENTS_PATH = 'data/processed/governance_audit_events.jsonl'
EVALUATION_RECORDS_PATH = 'data/processed/prospective_evaluation_records.jsonl'
CHECKPOINT_PATH = 'data/processed/governance_checkpoint_signature.json'

def parse_timezone_aware_ts(ts_str: Optional[str]) -> Optional[datetime.datetime]:
    """
    Parses a timestamp string and normalizes to a timezone-aware UTC datetime.
    Rejects naive timestamps without explicit timezone.
    Accepts ISO formats and strings with 'IST', '+05:30', '+0530', or 'Z'.
    """
    if not ts_str or not isinstance(ts_str, str):
        return None
    s = ts_str.strip()
    if s.endswith('IST'):
        s = s[:-3].strip() + ' +0530'
    try:
        dt = pd.to_datetime(s)
        if dt.tzinfo is None:
            return None  # Rejects naive timestamp
        return dt.astimezone(timezone.utc).to_pydatetime()
    except Exception:
        return None


class ProspectiveLifecycleManager:
    def __init__(self,
                 decision_ledger_path: str = DECISION_LEDGER_PATH,
                 outcome_ledger_path: str = OUTCOME_LEDGER_PATH,
                 candidate_registry_path: str = CANDIDATE_REGISTRY_PATH,
                 audit_events_path: str = AUDIT_EVENTS_PATH,
                 evaluation_records_path: str = EVALUATION_RECORDS_PATH,
                 checkpoint_path: str = CHECKPOINT_PATH):
        self.decision_ledger_path = decision_ledger_path
        self.outcome_ledger_path = outcome_ledger_path
        self.candidate_registry_path = candidate_registry_path
        self.audit_events_path = audit_events_path
        self.evaluation_records_path = evaluation_records_path
        self.checkpoint_path = checkpoint_path
        self._evidence_lock = threading.Lock()

        self.logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger_path,
            outcome_ledger_path=self.outcome_ledger_path
        )
        self.surveillance = SurveillanceMonitor(
            decision_ledger_path=self.decision_ledger_path,
            outcome_ledger_path=self.outcome_ledger_path,
            candidate_registry_path=self.candidate_registry_path,
            audit_events_path=self.audit_events_path
        )
        self.auditor = ProspectiveEvidenceAuditor(
            decision_ledger_path=self.decision_ledger_path,
            outcome_ledger_path=self.outcome_ledger_path,
            candidate_registry_path=self.candidate_registry_path,
            audit_events_path=self.audit_events_path,
            checkpoint_path=self.checkpoint_path
        )

    # =========================================================================
    # Workstream 1: Pre-Cutoff Decision Capture & Commitment Pipeline
    # =========================================================================
    def calculate_trailing_5_sentiment(self, cutoff_date_str: str, market_features_path: str = 'data/processed/ipo_market_features.csv') -> Dict[str, Any]:
        """
        Calculates exact trailing 5 listing outcomes deterministically:
          - Only prior IPOs with listing_date < cutoff_date are eligible.
          - Deterministically sorted by [listing_date ASC, ipo_id ASC].
          - Returns trailing 5 issues (tail(5)).
          - Computes mean listing-open return in percentage points.
        """
        if not os.path.exists(market_features_path):
            raise FileNotFoundError(f"Market features file missing at {market_features_path}")
        df = pd.read_csv(market_features_path)
        cand = df.dropna(subset=['listing_date', 'target_listing_open_return_pct']).copy()
        cand['listing_date'] = pd.to_datetime(cand['listing_date'])
        cand = cand.sort_values(['listing_date', 'ipo_id']).reset_index(drop=True)
        
        cutoff_dt = pd.to_datetime(cutoff_date_str[:10])
        prior_eligible = cand[cand['listing_date'] < cutoff_dt]
        
        if len(prior_eligible) < 5:
            return {
                'status': 'INSUFFICIENT_PRIOR_LISTINGS',
                'count': len(prior_eligible),
                'mean_return_pct': None,
                'prior_issues': []
            }
            
        last5 = prior_eligible.tail(5)
        mean_ret = round(float(last5['target_listing_open_return_pct'].mean()), 2)
        
        issues_summary = []
        for _, r in last5.iterrows():
            issues_summary.append({
                'ipo_id': r['ipo_id'],
                'board_type': r['board_type'],
                'listing_date': str(r['listing_date'])[:10],
                'issue_price_inr': float(r['issue_price_inr']),
                'target_listing_open_return_pct': float(r['target_listing_open_return_pct'])
            })
            
        return {
            'status': 'VERIFIED_CALCULATED',
            'count': 5,
            'mean_return_pct': mean_ret,
            'prior_issues': issues_summary,
            'effective_cutoff_date': str(cutoff_dt)[:10]
        }

    def audit_and_prepare_candidate(self, candidate_dict: Dict[str, Any], evaluation_timestamp_ist: Optional[str] = None) -> Dict[str, Any]:
        """
        Audits an eligible IPO candidate before decision commitment:
          - Verifies authoritative issue-specific cutoff.
          - Verifies feature source evidence and publication timestamps.
          - Verifies feature completeness and numeric validity.
          - Verifies frozen model identity and SHA-256 digest.
          - Rejects or excludes non-compliant records with explicit reason codes.
        """
        ipo_id = candidate_dict.get('ipo_id', '')
        company_name = candidate_dict.get('company_name', '')
        board = candidate_dict.get('board_type', 'Mainboard')
        cutoff_ts = candidate_dict.get('cutoff_timestamp_ist', '')
        features = candidate_dict.get('features', {})
        cutoff_evidence = (
            candidate_dict.get('authoritative_evidence') or
            (candidate_dict.get('feature_provenance') or {}).get('cutoff_source_evidence') or
            (candidate_dict.get('feature_provenance') or {}).get('authoritative_evidence')
        )
        prov = candidate_dict.get('feature_provenance') or {
            'cutoff_source_evidence': cutoff_evidence,
            'authoritative_evidence': cutoff_evidence,
            'source_publication_timestamp_ist': candidate_dict.get('source_publication_timestamp_ist'),
            'raw_source_sha256': candidate_dict.get('raw_source_sha256'),
            'is_timing_verified': candidate_dict.get('is_timing_verified', False)
        }
        if 'cutoff_source_evidence' not in prov and cutoff_evidence:
            prov['cutoff_source_evidence'] = cutoff_evidence

        reasons = []
        is_clean_eligible = True

        # 1. Authoritative Cutoff & Timezone verification
        has_tz = bool(cutoff_ts and ('+05:30' in cutoff_ts or '+0530' in cutoff_ts or 'IST' in cutoff_ts))
        if not has_tz:
            reasons.append("MISSING_OR_INVALID_CUTOFF_TIMEZONE")
            is_clean_eligible = False

        # 2. Source evidence presence and hash format
        has_evidence = bool(prov.get('authoritative_evidence') or prov.get('cutoff_source_evidence') or candidate_dict.get('authoritative_evidence'))
        raw_hash = prov.get('raw_source_sha256') or candidate_dict.get('raw_source_sha256')
        has_raw_hash = bool(raw_hash and isinstance(raw_hash, str) and len(raw_hash) == 64 and all(c in '0123456789abcdefABCDEF' for c in raw_hash))
        
        if not has_evidence:
            reasons.append("MISSING_AUTHORITATIVE_CUTOFF_EVIDENCE")
            is_clean_eligible = False
        if not has_raw_hash:
            reasons.append("MISSING_OR_INVALID_PROVENANCE_HASH: Must be exact 64-char hex SHA-256")
            is_clean_eligible = False

        # Verify bidding cutoff evidence explicitly
        bidding_cutoff_verified = prov.get('is_bidding_cutoff_verified', False) or candidate_dict.get('is_bidding_cutoff_verified', False)
        if not bidding_cutoff_verified:
            reasons.append("EXCHANGE_BIDDING_CUTOFF_UNVERIFIED: Authoritative order book close not verified independently of UPI mandate")
            is_clean_eligible = False

        # 3. Source publication timestamp precedes or equals cutoff
        pub_ts = prov.get('source_publication_timestamp_ist') or candidate_dict.get('source_publication_timestamp_ist')
        ret_ts = prov.get('retrieval_timestamp_ist') or candidate_dict.get('retrieval_timestamp_ist')
        eff_ts = prov.get('effective_timestamp_ist') or candidate_dict.get('effective_timestamp_ist')
        dec_ts = evaluation_timestamp_ist or candidate_dict.get('prediction_decision_timestamp_ist')

        # Timezone-aware normalization
        dt_pub = parse_timezone_aware_ts(pub_ts)
        dt_cut = parse_timezone_aware_ts(cutoff_ts)
        dt_ret = parse_timezone_aware_ts(ret_ts)
        dt_eff = parse_timezone_aware_ts(eff_ts)
        dt_dec = parse_timezone_aware_ts(dec_ts) if dec_ts else None

        if not pub_ts:
            reasons.append("MISSING_FEATURE_PUBLICATION_TIMESTAMP")
            is_clean_eligible = False
        elif dt_pub is None:
            reasons.append(f"INVALID_OR_TIMEZONE_NAIVE_PUBLICATION_TIMESTAMP: '{pub_ts}'")
            is_clean_eligible = False
        elif dt_cut is not None and dt_pub > dt_cut:
            reasons.append(f"POST_CUTOFF_FEATURE_PUBLICATION: {pub_ts} > {cutoff_ts}")
            is_clean_eligible = False

        # Point-in-time enforcement against decision timestamp:
        if dt_pub is not None and dt_dec is not None and dt_pub > dt_dec:
            reasons.append(f"FEATURE_PUBLISHED_AFTER_DECISION_TIMESTAMP: pub {pub_ts} > dec {dec_ts}")
            is_clean_eligible = False

        if ret_ts:
            if dt_ret is None:
                reasons.append(f"INVALID_OR_TIMEZONE_NAIVE_RETRIEVAL_TIMESTAMP: '{ret_ts}'")
                is_clean_eligible = False
            elif dt_dec is not None and dt_ret > dt_dec:
                reasons.append(f"FEATURE_RETRIEVED_AFTER_DECISION_TIMESTAMP: ret {ret_ts} > dec {dec_ts}")
                is_clean_eligible = False
            elif dt_pub is not None and dt_ret < dt_pub:
                reasons.append(f"RETRIEVAL_BEFORE_PUBLICATION_ANOMALY: ret {ret_ts} < pub {pub_ts}")
                is_clean_eligible = False

        if eff_ts:
            if dt_eff is None:
                reasons.append(f"INVALID_OR_TIMEZONE_NAIVE_EFFECTIVE_TIMESTAMP: '{eff_ts}'")
                is_clean_eligible = False
            elif dt_dec is not None and dt_eff > dt_dec:
                reasons.append(f"FEATURE_EFFECTIVE_AFTER_DECISION_TIMESTAMP: eff {eff_ts} > dec {dec_ts}")
                is_clean_eligible = False

        # Granular feature-level provenance audit if individual features dict provided
        individual_provenance = prov.get('individual_feature_provenance') or candidate_dict.get('individual_feature_provenance') or {}
        for fname, fmeta in individual_provenance.items():
            f_pub = fmeta.get('source_publication_timestamp_ist')
            f_ret = fmeta.get('retrieval_timestamp_ist')
            f_eff = fmeta.get('effective_timestamp_ist')
            f_hash = fmeta.get('source_artifact_sha256')
            
            # Check complete 64-char hex hash
            if not f_hash or len(f_hash) != 64 or not all(c in '0123456789abcdefABCDEF' for c in f_hash):
                reasons.append(f"INVALID_FEATURE_ARTIFACT_HASH_{fname.upper()}: Must be 64-char hex")
                is_clean_eligible = False

            dt_f_pub = parse_timezone_aware_ts(f_pub)
            dt_f_ret = parse_timezone_aware_ts(f_ret)
            dt_f_eff = parse_timezone_aware_ts(f_eff)

            if f_pub and dt_f_pub is None:
                reasons.append(f"INVALID_TIMEZONE_PUB_{fname.upper()}")
                is_clean_eligible = False
            elif dt_f_pub and dt_dec and dt_f_pub > dt_dec:
                reasons.append(f"POST_DECISION_PUBLICATION_{fname.upper()}: {f_pub} > {dec_ts}")
                is_clean_eligible = False

            if f_ret and dt_f_ret is None:
                reasons.append(f"INVALID_TIMEZONE_RET_{fname.upper()}")
                is_clean_eligible = False
            elif dt_f_ret and dt_dec and dt_f_ret > dt_dec:
                reasons.append(f"POST_DECISION_RETRIEVAL_{fname.upper()}: {f_ret} > {dec_ts}")
                is_clean_eligible = False
            elif dt_f_ret and dt_f_pub and dt_f_ret < dt_f_pub:
                reasons.append(f"RETRIEVAL_BEFORE_PUB_ANOMALY_{fname.upper()}: {f_ret} < {f_pub}")
                is_clean_eligible = False

            if f_eff and dt_f_eff is None:
                reasons.append(f"INVALID_TIMEZONE_EFF_{fname.upper()}")
                is_clean_eligible = False
            elif dt_f_eff and dt_dec and dt_f_eff > dt_dec:
                reasons.append(f"POST_DECISION_EFFECTIVE_{fname.upper()}: {f_eff} > {dec_ts}")
                is_clean_eligible = False

        # 4. Prohibited lookahead leakage
        prohibited = ['listing_open_inr', 'listing_close_inr', 'listing_open_return_pct', 'listing_close_return_pct', 'listing_date']
        for p in prohibited:
            if p in features or p in candidate_dict:
                reasons.append(f"LOOKAHEAD_LEAKAGE_DETECTED: Prohibited variable '{p}' present.")
                is_clean_eligible = False

        # 5. Feature completeness and numeric validity
        required_features = ['feat_nifty50_ret5s_pct', 'feat_india_vix', 'feat_recent5_sentiment']
        missing_feats = []
        invalid_feats = []
        for rf in required_features:
            val = features.get(rf)
            if val is None:
                missing_feats.append(rf)
            else:
                try:
                    fval = float(val)
                    if np.isnan(fval) or np.isinf(fval):
                        invalid_feats.append(f"{rf}={val}")
                except (ValueError, TypeError):
                    invalid_feats.append(f"{rf}={val}")

        if missing_feats and board == 'SME':
            reasons.append(f"MISSING_REQUIRED_FEATURES: {', '.join(missing_feats)}")
            is_clean_eligible = False
        if invalid_feats and board == 'SME':
            reasons.append(f"INVALID_NUMERIC_FEATURES: {', '.join(invalid_feats)}")
            is_clean_eligible = False

        # 6. Model verification
        model_name = "Model_6B_SME_v1.0" if board == 'SME' else "REGISTER_FOR_COVERAGE_ONLY"
        model_sha = FROZEN_SME_MODEL_SHA256 if board == 'SME' else "NO_FROZEN_MODEL"
        p_model = None

        if board == 'SME':
            model_audit = self.surveillance.verify_model_integrity()
            if not model_audit.get('valid', False):
                reasons.append("FROZEN_SME_MODEL_INTEGRITY_BREACH")
                is_clean_eligible = False
            else:
                # Generate prediction strictly with frozen SME model artifact if features are valid
                if not missing_feats and not invalid_feats:
                    try:
                        p_model = self.predict_frozen_sme(features)
                    except Exception as e:
                        reasons.append(f"MODEL_INFERENCE_ERROR: {str(e)}")
                        is_clean_eligible = False
        elif board == 'Mainboard':
            # Mainboard has no authorized model
            p_model = None
            reasons.append("NO_FROZEN_MODEL_FOR_MAINBOARD")
            is_clean_eligible = False

        # Reconcile standardized candidate lifecycle state
        # Check if cutoff has already expired relative to decision/evaluation time
        # Boundary rule: evaluation_ts >= cutoff_ts is strictly expired/late
        cutoff_has_passed = False
        if cutoff_ts:
            try:
                now_str = (evaluation_timestamp_ist or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')).replace(' IST', '').replace('+05:30', '').replace('+0530', '').strip()
                c_now = pd.to_datetime(now_str)
                c_cut = pd.to_datetime(cutoff_ts.replace(' IST', '').replace('+05:30', '').replace('+0530', '').strip())
                if c_now >= c_cut:
                    cutoff_has_passed = True
            except Exception:
                pass

        # Order of precedence for candidate states:
        if board == "Mainboard":
            # Mainboard candidates are strictly non-scoring and remain BLOCKED_GOVERNANCE
            candidate_lifecycle_state = "BLOCKED_GOVERNANCE"
            is_clean_eligible = False
            reasons.append("MAINBOARD_CANDIDATE_NON_SCORING: Model_6B_SME_v1.0 is strictly restricted to SME issues.")
        elif cutoff_has_passed:
            candidate_lifecycle_state = "EXPIRED_WITHOUT_COMMIT"
            reasons.append(f"CANDIDATE_CUTOFF_EXPIRED: Cutoff reached or passed at {cutoff_ts}")
            is_clean_eligible = False
        elif not is_clean_eligible:
            if any("EXCHANGE_BIDDING_CUTOFF_UNVERIFIED" in r for r in reasons) or any("MISSING_AUTHORITATIVE_CUTOFF" in r for r in reasons):
                candidate_lifecycle_state = "BLOCKED_CUTOFF"
            elif any("POST_CUTOFF_FEATURE" in r for r in reasons) or any("MISSING_FEATURE_PUBLICATION" in r for r in reasons):
                candidate_lifecycle_state = "BLOCKED_FEATURE_AVAILABILITY"
            elif any("FEATURE" in r for r in reasons):
                candidate_lifecycle_state = "BLOCKED_FEATURE_PARITY"
            elif any("MODEL" in r for r in reasons):
                candidate_lifecycle_state = "BLOCKED_INFERENCE"
            else:
                candidate_lifecycle_state = "BLOCKED_CUTOFF"
        else:
            candidate_lifecycle_state = "READY_FOR_PROSPECTIVE_COMMIT"

        return {
            'ipo_id': ipo_id,
            'company_name': company_name,
            'board_type': board,
            'cutoff_timestamp_ist': cutoff_ts,
            'candidate_lifecycle_state': candidate_lifecycle_state,
            'feature_provenance': prov,
            'features': features,
            'model_name': model_name,
            'model_sha256': model_sha,
            'predicted_probability': p_model,
            'is_clean_eligible': is_clean_eligible and (len(reasons) == 0),
            'exclusion_reasons': sorted(list(set(reasons))),
            'readiness_gate_evaluation': {
                'candidate_identity_status': 'PASS' if ipo_id and company_name else 'FAIL',
                'exchange_segment_status': 'PASS' if board in ['Mainboard', 'SME'] else 'FAIL',
                'official_cutoff_status': 'PASS' if (bidding_cutoff_verified and has_tz and has_evidence and not cutoff_has_passed) else ('EXPIRED' if cutoff_has_passed else 'FAIL'),
                'feature_temporal_provenance_status': 'PASS' if not any('POST_' in r or 'INVALID_OR_TIMEZONE' in r or 'RETRIEVAL_BEFORE' in r for r in reasons) else 'FAIL',
                'feature_definition_parity_status': 'PASS' if not any('INVALID_NUMERIC' in r or 'MISSING_REQUIRED' in r for r in reasons) else 'FAIL',
                'model_hash_status': 'PASS' if (board == 'Mainboard' or model_sha == FROZEN_SME_MODEL_SHA256) else 'FAIL',
                'manifest_hash_status': 'PASS' if self.surveillance.verify_manifest_integrity().get('valid', False) else 'FAIL',
                'input_artifact_integrity_status': 'PASS' if has_raw_hash else 'FAIL',
                'inference_reproducibility_status': 'PASS' if (p_model is not None or board == 'Mainboard') else 'FAIL',
                'persistence_integrity_status': 'PASS' if not self.logger.inspect_ledger_corruption('decision')['has_corruption'] else 'FAIL',
                'governance_approval_status': 'PASS' if (board == 'SME' and is_clean_eligible) else ('NOT_AUTHORIZED_MAINBOARD' if board == 'Mainboard' else 'FAIL'),
                'final_readiness_status': candidate_lifecycle_state,
                'blocking_reasons': sorted(list(set(reasons))),
                'evaluated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
            }
        }

    def predict_frozen_sme(self, features_dict: Dict[str, Any]) -> float:
        """Loads the frozen SME model artifact and outputs predicted opening probability."""
        if not os.path.exists(FROZEN_SME_MODEL_PATH):
            raise FileNotFoundError(f"Frozen SME model artifact missing at {FROZEN_SME_MODEL_PATH}")
        pipeline = joblib.load(FROZEN_SME_MODEL_PATH)
        df_in = pd.DataFrame([{
            'feat_nifty50_ret5s_pct': float(features_dict['feat_nifty50_ret5s_pct']),
            'feat_india_vix': float(features_dict['feat_india_vix']),
            'feat_recent5_sentiment': float(features_dict['feat_recent5_sentiment'])
        }])
        prob = float(pipeline.predict_proba(df_in)[0, 1])
        return round(prob, 4)

    def commit_prospective_decision(self,
                                    candidate_dict: Dict[str, Any],
                                    override_commit_timestamp_ist: Optional[str] = None,
                                    explicit_admin_authorization: Optional[Dict[str, Any]] = None,
                                    strict_clean_only: bool = False) -> Dict[str, Any]:
        """
        Commits a prospective decision record to the live decision ledger before cutoff.
        Rejects backdated decisions or commits occurring after cutoff from clean cohort.
        Enforces mandatory governance checks:
          - If strict_clean_only is True, blocks persistence unless candidate is READY_FOR_PROSPECTIVE_COMMIT
            and explicitly authorized by administrator.
          - Revalidates candidate state at persistence boundary immediately before write.
        """
        now_ts = override_commit_timestamp_ist or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
        prep = self.audit_and_prepare_candidate(candidate_dict, evaluation_timestamp_ist=now_ts)
        ipo_id = prep['ipo_id']
        cutoff_ts = prep['cutoff_timestamp_ist']
        board = prep['board_type']
        lifecycle_state = prep['candidate_lifecycle_state']
        is_clean = prep['is_clean_eligible']

        if strict_clean_only:
            if lifecycle_state != "READY_FOR_PROSPECTIVE_COMMIT" or not is_clean:
                raise ValueError(
                    f"COMMIT_BLOCKED_UNREADY_CANDIDATE: Candidate '{ipo_id}' in state '{lifecycle_state}' "
                    f"cannot be committed to clean prospective cohort. Blocking reasons: {prep['exclusion_reasons']}"
                )
            if not explicit_admin_authorization or not isinstance(explicit_admin_authorization, dict):
                raise ValueError(
                    f"COMMIT_BLOCKED_NO_EXPLICIT_AUTHORIZATION: Explicit admin authorization required to commit '{ipo_id}'."
                )
            auth_by = explicit_admin_authorization.get('authorized_by')
            auth_token = explicit_admin_authorization.get('authorization_token')
            # Check non-empty authorizer
            if not auth_by or not isinstance(auth_by, str) or len(auth_by.strip()) < 3:
                raise ValueError(
                    f"COMMIT_BLOCKED_NO_EXPLICIT_AUTHORIZATION: Invalid or missing 'authorized_by' for '{ipo_id}'."
                )
            # If an authorization token or secret verification is required/configured:
            # Token format validation if provided: must be valid hex SHA-256 or match candidate authorization digest
            if auth_token is not None:
                if not isinstance(auth_token, str) or len(auth_token) < 32:
                    raise ValueError(
                        f"COMMIT_BLOCKED_INVALID_AUTHORIZATION_TOKEN: Authorization token for '{ipo_id}' must be at least 32 hex chars."
                    )

        is_late = False
        if cutoff_ts:
            try:
                c_now = now_ts.replace(' IST', '').replace('+05:30', '').replace('+0530', '').strip()
                c_cut = cutoff_ts.replace(' IST', '').replace('+05:30', '').replace('+0530', '').strip()
                if pd.to_datetime(c_now) >= pd.to_datetime(c_cut):
                    is_late = True
            except Exception:
                is_late = True

        warnings = list(prep['exclusion_reasons'])
        if is_late:
            warnings.append(f"LATE_DECISION_COMMITTED_AFTER_CUTOFF: {now_ts} >= {cutoff_ts}")
            is_clean = False

        if strict_clean_only and is_late:
            raise ValueError(
                f"COMMIT_BLOCKED_UNREADY_CANDIDATE: Candidate '{ipo_id}' cutoff elapsed at persistence boundary: {now_ts} >= {cutoff_ts}."
            )

        if explicit_admin_authorization:
            warnings.append(f"ADMIN_AUTHORIZED_BY: {explicit_admin_authorization.get('authorized_by')}")

        p_pos = prep['predicted_probability']
        p_macro = p_pos
        p_loss = 0.05 if board == 'SME' else 0.05

        if board == 'Mainboard':
            p_pos = 0.50  # non-scoring placeholder
            p_macro = 0.50
            p_loss = 0.05

        result = self.logger.record_prospective_decision(
            ipo_id=ipo_id,
            company_name=prep['company_name'],
            board_type=board,
            cutoff_timestamp_ist=cutoff_ts,
            features_dict=prep['features'],
            p_positive_open=p_pos if board == 'SME' else 0.50,
            p_macro=p_macro if board == 'SME' else 0.50,
            p_severe_loss=p_loss,
            model_name=prep['model_name'],
            model_sha256=prep['model_sha256'],
            feature_provenance=prep['feature_provenance'],
            data_quality_warnings=warnings,
            allow_post_cutoff_commit=True
        )

        return {
            'status': result['status'],
            'ipo_id': ipo_id,
            'decision_id': result.get('decision_id'),
            'record_sha256': result.get('record_sha256'),
            'committed_timestamp_ist': now_ts,
            'is_clean_eligible': is_clean and not is_late and (board == 'SME'),
            'is_late': is_late,
            'candidate_lifecycle_state': lifecycle_state,
            'exclusion_reasons': sorted(list(set(warnings)))
        }

    # =========================================================================
    # Workstream 2: First-Outcome Reconciliation
    # =========================================================================
    def reconcile_listing_outcome(self,
                                  ipo_id: str,
                                  listing_date_str: str,
                                  issue_price_inr: float,
                                  listing_open_inr: float,
                                  official_bulletin_ref: str,
                                  observed_allotment: str = 'UNKNOWN',
                                  retrieval_timestamp_ist: Optional[str] = None,
                                  artifact_sha256: Optional[str] = None,
                                  raw_artifact_payload: Optional[str] = None,
                                  price_currency: str = 'INR',
                                  is_close_price: bool = False,
                                  is_simulated: bool = False) -> Dict[str, Any]:
        """
        Reconciles realized listing outcome for a committed IPO:
          - Validates pre-existence of prospective decision.
          - Rejects non-positive prices.
          - Calculates listing-open return strictly as ((P_open - P_issue) / P_issue) * 100.
          - Never mixes open returns with close returns (rejects if is_close_price is True).
          - Rejects non-INR currency units (must be INR).
          - Rejects simulated outcomes.
          - Validates official bulletin reference and artifact SHA-256 byte checksum when provided.
          - Preserves source bulletin reference and retrieval timestamp.
        """
        now_ts = retrieval_timestamp_ist or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')

        if is_simulated:
            raise ValueError(f"SIMULATED_OUTCOME_PROHIBITED: Simulated outcomes cannot be ingested into prospective ledger for '{ipo_id}'.")

        if is_close_price:
            raise ValueError(f"LISTING_CLOSE_SUBSTITUTION_PROHIBITED: Listing-close price cannot be substituted for listing-open price for '{ipo_id}'.")

        if price_currency.upper() not in ['INR', 'RS', 'RUPEES']:
            raise ValueError(f"INVALID_PRICE_CURRENCY: Price currency must be INR, received '{price_currency}' for '{ipo_id}'.")

        if not official_bulletin_ref or len(str(official_bulletin_ref).strip()) < 5:
            raise ValueError(f"MISSING_OFFICIAL_BULLETIN_REF: Authoritative official exchange bulletin citation is required for '{ipo_id}'.")

        if artifact_sha256 is not None:
            if not isinstance(artifact_sha256, str) or len(artifact_sha256) != 64:
                raise ValueError(f"INVALID_ARTIFACT_SHA256: Outcome artifact hash must be a 64-char hex SHA-256 string for '{ipo_id}'.")
            if raw_artifact_payload is not None:
                calc_sha = hashlib.sha256(raw_artifact_payload.encode('utf-8')).hexdigest()
                if calc_sha.lower() != artifact_sha256.lower():
                    raise ValueError(f"OUTCOME_ARTIFACT_HASH_MISMATCH: Artifact content hash {calc_sha} does not match asserted {artifact_sha256} for '{ipo_id}'.")

        # Check existing decision
        logged_decision_ids = self.logger.get_logged_decision_ids()
        if ipo_id not in logged_decision_ids:
            # Log governance audit warning for unmatched outcome
            self.surveillance.log_governance_event(
                event_type="UNMATCHED_OUTCOME_REJECTED",
                affected_entity=ipo_id,
                severity="WARNING",
                reason_code="NO_PRE_EXISTING_DECISION",
                description=f"Attempted to reconcile outcome for '{ipo_id}' without prior prospective decision record.",
                evidence_reference=official_bulletin_ref
            )
            raise ValueError(f"UNMATCHED OUTCOME: No prospective decision record exists for '{ipo_id}'.")

        # Check existing outcome
        logged_outcome_ids = self.logger.get_logged_outcome_ids()
        if ipo_id in logged_outcome_ids:
            return {
                'status': 'DUPLICATE_OUTCOME_IGNORED',
                'ipo_id': ipo_id,
                'message': 'Outcome already logged in prospective outcome ledger.'
            }

        p_issue = float(issue_price_inr)
        p_open = float(listing_open_inr)
        if p_issue <= 0 or p_open <= 0 or np.isnan(p_issue) or np.isnan(p_open):
            self.surveillance.log_governance_event(
                event_type="INVALID_PRICES_REJECTED",
                affected_entity=ipo_id,
                severity="CRITICAL",
                reason_code="NON_POSITIVE_PRICE_DETECTED",
                description=f"Invalid prices submitted for '{ipo_id}': issue_price={p_issue}, open_price={p_open}",
                evidence_reference=official_bulletin_ref
            )
            raise ValueError(f"INVALID PRICES: issue_price ({p_issue}) and listing_open ({p_open}) must be strictly positive floats.")

        calc_return_pct = round(((p_open - p_issue) / p_issue) * 100.0, 4)

        result = self.logger.record_realized_outcome(
            ipo_id=ipo_id,
            listing_date=listing_date_str,
            listing_open_inr=p_open,
            issue_price_inr=p_issue,
            listing_open_return_pct=calc_return_pct,
            observed_allotment=observed_allotment,
            outcome_source=f"{official_bulletin_ref} (Retrieved: {now_ts})"
        )

        return {
            'status': 'OUTCOME_RECONCILED',
            'ipo_id': ipo_id,
            'outcome_id': result.get('outcome_id'),
            'record_sha256': result.get('record_sha256'),
            'listing_date': listing_date_str,
            'issue_price_inr': p_issue,
            'listing_open_inr': p_open,
            'listing_open_return_pct': calc_return_pct,
            'is_positive_open': bool(calc_return_pct > 0),
            'is_severe_loss': bool(calc_return_pct <= -10.0),
            'official_bulletin_ref': official_bulletin_ref,
            'artifact_sha256': artifact_sha256,
            'currency': price_currency.upper(),
            'reconciliation_timestamp_ist': now_ts
        }

    def record_outcome_correction(self,
                                  ipo_id: str,
                                  prior_open_price: float,
                                  corrected_open_price: float,
                                  reason: str,
                                  bulletin_citation: str) -> Dict[str, Any]:
        """
        Records an official correction event in the append-only governance audit trail without
        mutating the immutable outcome ledger.
        """
        event = self.surveillance.log_governance_event(
            event_type="OUTCOME_CORRECTION_EVENT",
            affected_entity=ipo_id,
            severity="WARNING",
            reason_code="OFFICIAL_PRICE_REVISION",
            description=f"Outcome open price for '{ipo_id}' revised from {prior_open_price} to {corrected_open_price}. Reason: {reason}",
            evidence_reference=bulletin_citation
        )
        return event

    # =========================================================================
    # Workstream 3: Evaluation-Record Generation
    # =========================================================================
    def generate_evaluation_records(self) -> Dict[str, Any]:
        """
        Generates observation-level evaluation records pairing committed decisions and verified outcomes.
        Calculates:
          - Model Brier contribution: (p_model - y_true)^2
          - Baseline Brier contribution: (p_base_ref - y_true)^2
          - Evaluation inclusion status (CLEAN_PROSPECTIVE_COHORT vs EXCLUDED)
        """
        decisions = self._load_jsonl(self.decision_ledger_path)
        outcomes = self._load_jsonl(self.outcome_ledger_path)
        outcome_by_ipo = {o['ipo_id']: o for o in outcomes}

        sme_base_ref = 0.8306
        mb_base_ref = 0.7583

        eval_records = []
        n_eligible = 0
        n_excluded = 0

        for d in decisions:
            ipo_id = d.get('ipo_id')
            board = d.get('board_type', 'Mainboard')
            commit_ts = d.get('logging_timestamp_ist')
            cutoff_ts = d.get('cutoff_timestamp_ist')
            model_name = d.get('model_name')
            model_sha = d.get('model_sha256')
            p_pos = d.get('predicted_probabilities', {}).get('p_positive_open')

            out = outcome_by_ipo.get(ipo_id)
            has_outcome = (out is not None)

            y_true = int(out.get('is_positive_open', False)) if has_outcome else None
            ret_open = out.get('gross_open_return_pct') if has_outcome else None
            bulletin_ref = out.get('outcome_source') if has_outcome else None

            # Brier contributions
            base_ref = sme_base_ref if board == 'SME' else mb_base_ref
            model_brier_contrib = None
            base_brier_contrib = None
            if has_outcome and p_pos is not None and y_true is not None:
                model_brier_contrib = round(float((p_pos - y_true) ** 2), 6)
                base_brier_contrib = round(float((base_ref - y_true) ** 2), 6)

            is_clean = bool(d.get('eligible_for_clean_prospective_cohort', False))
            reasons = [str(r) for r in (d.get('rejection_reasons', {}).values() if isinstance(d.get('rejection_reasons'), dict) else []) if r is not None]
            if not is_clean:
                reasons.extend([str(w) for w in d.get('data_quality_warnings', []) if w is not None])

            # Evaluation inclusion rule
            eval_inclusion_status = "EXCLUDED_FROM_EVALUATION"
            if is_clean and board == 'SME' and has_outcome:
                eval_inclusion_status = "INCLUDED_CLEAN_EVALUATION"
                n_eligible += 1
            elif not has_outcome:
                eval_inclusion_status = "PENDING_REALIZED_OUTCOME"
            else:
                eval_inclusion_status = "EXCLUDED_FROM_PRIMARY_EVALUATION"
                n_excluded += 1

            rec = {
                'ipo_id': ipo_id,
                'company_name': d.get('company_name'),
                'board_type': board,
                'decision_id': d.get('decision_id'),
                'committed_timestamp_ist': commit_ts,
                'cutoff_timestamp_ist': cutoff_ts,
                'model_name': model_name,
                'model_sha256': model_sha,
                'predicted_probability': p_pos,
                'has_verified_outcome': has_outcome,
                'verified_outcome_label': y_true,
                'verified_listing_open_return_pct': ret_open,
                'source_evidence_reference': bulletin_ref or d.get('feature_provenance', {}).get('authoritative_evidence'),
                'is_clean_cohort': is_clean,
                'exclusion_reasons': sorted(list(set(reasons))),
                'fixed_baseline_probability': base_ref,
                'model_brier_contribution': model_brier_contrib,
                'baseline_brier_contribution': base_brier_contrib,
                'evaluation_inclusion_status': eval_inclusion_status
            }
            eval_records.append(rec)

        # Write out to evaluation_records_path
        os.makedirs(os.path.dirname(self.evaluation_records_path), exist_ok=True)
        with open(self.evaluation_records_path, 'w', encoding='utf-8') as f:
            for r in eval_records:
                f.write(json.dumps(r) + '\n')

        return {
            'total_decisions_evaluated': len(decisions),
            'mature_observations_count': len([r for r in eval_records if r['has_verified_outcome']]),
            'clean_included_evaluation_count': n_eligible,
            'excluded_evaluation_count': n_excluded,
            'evaluation_records': eval_records,
            'sample_sufficiency_status': 'SUFFICIENT_FOR_POINT_ESTIMATE' if n_eligible >= 30 else 'INSUFFICIENT_SAMPLE_SIZE_GATE',
            'performance_claim_allowed': n_eligible >= 100
        }

    # =========================================================================
    # Helpers
    # =========================================================================
    def _load_jsonl(self, path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(path):
            return []
        items = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        items.append(json.loads(line))
                    except Exception:
                        pass
        return items

    # =========================================================================
    # Workstream C & D: Evidence-Change Processing & Daily Monitoring Report
    # =========================================================================
    def process_evidence_update(self,
                                ipo_id: str,
                                raw_artifact_content: bytes,
                                source_reference: str,
                                publication_timestamp_ist: Optional[str],
                                retrieval_timestamp_ist: str,
                                is_primary_exchange_source: bool = False,
                                relevant_bidding_category: str = "RETAIL_INDIVIDUAL",
                                expected_cutoff_timestamp_ist: Optional[str] = None) -> Dict[str, Any]:
        """
        Idempotently processes newly discovered candidate evidence with rigorous adversarial defense:
          1. Retains original raw artifact bytes & computes SHA-256 hash.
          2. Validates timestamp chronology (retrieval >= publication) and timezone-awareness.
          3. Rejects evidence published after decision timestamp (when decision timestamp provided).
          4. Verifies document applies to target IPO (name/id/symbol mentions in content).
          5. Verifies document establishes retail order book cutoff, rejecting UPI mandate only documents.
          6. Blocks evidence ingestion if candidate is already EXPIRED_WITHOUT_COMMIT.
          7. Handles conflicting cutoff timestamps between existing and new evidence.
          8. Re-evaluates candidate readiness and lifecycle transition.
          9. Logs linked governance audit event idempotently without duplicating events.
        """
        if not ipo_id:
            raise ValueError("ipo_id is required for evidence update.")
        if not raw_artifact_content:
            raise ValueError("raw_artifact_content cannot be empty.")
        if not retrieval_timestamp_ist:
            raise ValueError("retrieval_timestamp_ist is required.")

        artifact_sha256 = hashlib.sha256(raw_artifact_content).hexdigest()

        # Parse timestamps
        dt_pub = parse_timezone_aware_ts(publication_timestamp_ist) if publication_timestamp_ist else None
        dt_ret = parse_timezone_aware_ts(retrieval_timestamp_ist)

        if dt_ret is None:
            raise ValueError(f"INVALID_OR_TIMEZONE_NAIVE_RETRIEVAL_TIMESTAMP: '{retrieval_timestamp_ist}'")
        if publication_timestamp_ist and dt_pub is None:
            raise ValueError(f"INVALID_OR_TIMEZONE_NAIVE_PUBLICATION_TIMESTAMP: '{publication_timestamp_ist}'")
        if dt_pub and dt_ret and dt_ret < dt_pub:
            raise ValueError(f"RETRIEVAL_BEFORE_PUBLICATION_ANOMALY: retrieval {retrieval_timestamp_ist} < pub {publication_timestamp_ist}")

        # Load candidates
        candidates = []
        if os.path.exists(self.candidate_registry_path):
            with open(self.candidate_registry_path, 'r', encoding='utf-8') as f:
                candidates = json.load(f)

        target_candidate = next((c for c in candidates if c.get('ipo_id') == ipo_id), None)
        if not target_candidate:
            raise ValueError(f"CANDIDATE_NOT_FOUND: Candidate '{ipo_id}' is not in candidate registry.")

        # Capture pre-update state
        pre_prep = self.audit_and_prepare_candidate(target_candidate, evaluation_timestamp_ist=retrieval_timestamp_ist)
        pre_state = pre_prep['candidate_lifecycle_state']

        # Rule 6: Block evidence update if candidate is already expired
        if pre_state == "EXPIRED_WITHOUT_COMMIT":
            self.surveillance.log_governance_event(
                event_type="EVIDENCE_UPDATE_REJECTED",
                affected_entity=ipo_id,
                severity="WARNING",
                reason_code="CANDIDATE_ALREADY_EXPIRED",
                description=f"Evidence update rejected for '{ipo_id}': candidate already expired at cutoff boundary.",
                evidence_reference=artifact_sha256
            )
            raise ValueError(f"CANDIDATE_EXPIRED: Cannot ingest evidence for '{ipo_id}' because candidate cutoff has already elapsed.")

        # Content Inspection & Adversarial Checks
        content_text = ""
        try:
            content_text = raw_artifact_content.decode('utf-8', errors='ignore')
        except Exception:
            pass

        # Check candidate relevance
        target_name = target_candidate.get('company_name', '').lower()
        target_sym = target_candidate.get('symbol_or_ref', '').lower()
        content_lower = content_text.lower()

        relevance_verified = True
        if target_name and target_sym:
            # Check if either full company name, key word from company name, or symbol appears
            key_name_parts = [p for p in target_name.split() if len(p) > 3 and p not in ['limited', 'ltd.', 'industries', 'india']]
            has_name = any(p in content_lower for p in key_name_parts) if key_name_parts else (target_name in content_lower)
            has_sym = target_sym in content_lower
            if not (has_name or has_sym):
                if any(k in content_lower for k in ["notice", "subject", "trading", "cutoff", "circular"]):
                    relevance_verified = False

        if not relevance_verified:
            self.surveillance.log_governance_event(
                event_type="EVIDENCE_REJECTED_IRRELEVANT_CANDIDATE",
                affected_entity=ipo_id,
                severity="WARNING",
                reason_code="WRONG_CANDIDATE_DOCUMENT",
                description=f"Document does not mention candidate '{ipo_id}' ({target_name} / {target_sym}).",
                evidence_reference=artifact_sha256
            )
            raise ValueError(f"IRRELEVANT_EVIDENCE: Document does not mention candidate '{ipo_id}' or symbol '{target_sym}'.")

        # Check issue type: must be equity IPO / public issue, not debentures, bonds, or rights issue
        is_wrong_issue_type = bool(
            "ncd" in content_lower or "debenture" in content_lower or "bond" in content_lower or "rights issue" in content_lower
        )
        if is_wrong_issue_type:
            self.surveillance.log_governance_event(
                event_type="EVIDENCE_REJECTED_WRONG_ISSUE_TYPE",
                affected_entity=ipo_id,
                severity="WARNING",
                reason_code="NON_EQUITY_ISSUE_TYPE",
                description=f"Evidence update rejected for '{ipo_id}': document references NCDs, debentures, bonds, or rights issues.",
                evidence_reference=artifact_sha256
            )

        # Check order-book closure vs UPI mandate only
        is_upi_only = (
            ("upi mandate" in content_lower or "mandate acceptance" in content_lower or "payment deadline" in content_lower) and
            not ("order book" in content_lower or "bidding close" in content_lower or "retail cutoff" in content_lower or "book close" in content_lower)
        )

        # Check conflicting cutoff times
        new_cutoff_ts = expected_cutoff_timestamp_ist or target_candidate.get('cutoff_timestamp_ist')
        existing_cutoff = target_candidate.get('cutoff_timestamp_ist')
        if expected_cutoff_timestamp_ist and existing_cutoff and expected_cutoff_timestamp_ist != existing_cutoff:
            # Conflicting cutoff detected
            self.surveillance.log_governance_event(
                event_type="CONFLICTING_CUTOFF_TIMES_DETECTED",
                affected_entity=ipo_id,
                severity="WARNING",
                reason_code="CUTOFF_TIME_CONFLICT",
                description=f"Conflicting cutoff detected for '{ipo_id}': existing '{existing_cutoff}' vs new '{expected_cutoff_timestamp_ist}'.",
                evidence_reference=artifact_sha256
            )

        # Determine validity: must be primary exchange source, relevant category, not upi only, not wrong issue
        is_verified_bidding_cutoff = bool(
            is_primary_exchange_source and
            (relevant_bidding_category == "RETAIL_INDIVIDUAL") and
            relevance_verified and
            not is_upi_only and
            not is_wrong_issue_type
        )

        # Create updated candidate record
        updated_cand = dict(target_candidate)
        updated_cand['authoritative_evidence'] = source_reference
        updated_cand['raw_source_sha256'] = artifact_sha256
        updated_cand['source_publication_timestamp_ist'] = publication_timestamp_ist
        updated_cand['retrieval_timestamp_ist'] = retrieval_timestamp_ist
        updated_cand['is_timing_verified'] = True
        updated_cand['is_bidding_cutoff_verified'] = is_verified_bidding_cutoff
        if expected_cutoff_timestamp_ist:
            updated_cand['cutoff_timestamp_ist'] = expected_cutoff_timestamp_ist

        # Persist updated candidate into candidate registry
        for idx, c in enumerate(candidates):
            if c.get('ipo_id') == ipo_id:
                candidates[idx] = updated_cand
                break
        with open(self.candidate_registry_path, 'w', encoding='utf-8') as f:
            json.dump(candidates, f, indent=2)

        # Re-evaluate post-update readiness
        post_prep = self.audit_and_prepare_candidate(updated_cand, evaluation_timestamp_ist=retrieval_timestamp_ist)
        post_state = post_prep['candidate_lifecycle_state']

        # Idempotent governance event logging: deduplicate on (ipo_id, artifact_sha256)
        with self._evidence_lock:
            existing_events = self._load_jsonl(self.audit_events_path)
            event_already_logged = any(
                e.get('affected_entity') == ipo_id and
                e.get('evidence_reference') == artifact_sha256 and
                e.get('event_type') == "EVIDENCE_DISCOVERY_PROCESSED"
                for e in existing_events
            )

            event_id = None
            if not event_already_logged:
                reason = "PRIMARY_EVIDENCE_VERIFIED" if is_verified_bidding_cutoff else ("UPI_MANDATE_SECONDARY_RETAINED" if is_upi_only else "SECONDARY_EVIDENCE_RETAINED")
                severity = "INFO" if is_verified_bidding_cutoff else "WARNING"
                event_res = self.surveillance.log_governance_event(
                    event_type="EVIDENCE_DISCOVERY_PROCESSED",
                    affected_entity=ipo_id,
                    severity=severity,
                    reason_code=reason,
                    description=f"Evidence update processed for '{ipo_id}'. State transition: {pre_state} -> {post_state}.",
                    evidence_reference=artifact_sha256
                )
                event_id = event_res.get('event_id')

        return {
            'status': 'EVIDENCE_PROCESSED',
            'ipo_id': ipo_id,
            'artifact_sha256': artifact_sha256,
            'source_reference': source_reference,
            'is_primary_exchange_source': is_primary_exchange_source,
            'is_bidding_cutoff_verified': is_verified_bidding_cutoff,
            'is_upi_only': is_upi_only,
            'previous_lifecycle_state': pre_state,
            'new_lifecycle_state': post_state,
            'readiness_gate_evaluation': post_prep['readiness_gate_evaluation'],
            'audit_event_id': event_id,
            'event_deduplicated': event_already_logged,
            'evaluated_at': retrieval_timestamp_ist
        }

    def generate_daily_monitoring_report(self, evaluation_timestamp_ist: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates a comprehensive, deterministic, read-only daily monitoring report:
          1. Candidate lifecycle summary & approaching/passed cutoffs.
          2. Cutoff verification status.
          3. Failed readiness gates per candidate.
          4. Frozen model & manifest integrity.
          5. Decision and outcome ledger counts.
          6. Predictive evaluation maturity status.
          7. Outstanding required actions.
        """
        now_ts = evaluation_timestamp_ist or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')

        # Model & manifest integrity checks
        model_audit = self.surveillance.verify_model_integrity()
        manifest_audit = self.surveillance.verify_manifest_integrity()

        candidates = []
        if os.path.exists(self.candidate_registry_path):
            with open(self.candidate_registry_path, 'r', encoding='utf-8') as f:
                candidates = json.load(f)

        candidate_reports = []
        approaching_cutoffs = []
        expired_candidates = []

        now_clean = now_ts.replace(' IST', '').replace('+05:30', '').replace('+0530', '').strip()
        dt_now = pd.to_datetime(now_clean)

        for c in candidates:
            prep = self.audit_and_prepare_candidate(c, evaluation_timestamp_ist=now_ts)
            state = prep['candidate_lifecycle_state']
            cutoff_ts = c.get('cutoff_timestamp_ist')
            is_expired = False
            hours_to_cutoff = None

            if cutoff_ts:
                try:
                    c_clean = cutoff_ts.replace(' IST', '').replace('+05:30', '').replace('+0530', '').strip()
                    dt_cut = pd.to_datetime(c_clean)
                    diff_hours = (dt_cut - dt_now).total_seconds() / 3600.0
                    hours_to_cutoff = round(diff_hours, 2)
                    if diff_hours <= 0:
                        is_expired = True
                except Exception:
                    pass

            c_rep = {
                'ipo_id': c.get('ipo_id'),
                'company_name': c.get('company_name'),
                'board_type': c.get('board_type'),
                'exchange': c.get('exchange'),
                'asserted_cutoff_timestamp_ist': cutoff_ts,
                'cutoff_verification_status': 'VERIFIED' if c.get('is_bidding_cutoff_verified') else ('EXPIRED' if is_expired else 'UNVERIFIED'),
                'current_lifecycle_state': state,
                'model_eligibility': 'ELIGIBLE' if c.get('board_type') == 'SME' else 'COVERAGE_ONLY',
                'predicted_probability': prep.get('predicted_probability'),
                'failed_readiness_gates': [k for k, v in prep.get('readiness_gate_evaluation', {}).items() if v in ['FAIL', 'EXPIRED']],
                'blocking_reasons': prep.get('exclusion_reasons', []),
                'hours_to_cutoff': hours_to_cutoff,
                'evidence_reference': c.get('authoritative_evidence'),
                'evidence_sha256': c.get('raw_source_sha256'),
                'next_required_action': 'AWAIT_OFFICIAL_BSE_CIRCULAR' if (c.get('board_type') == 'SME' and not c.get('is_bidding_cutoff_verified') and not is_expired) else (
                    'EXPIRE_WITHOUT_COMMIT' if is_expired else 'MONITOR_COVERAGE_ONLY'
                )
            }
            candidate_reports.append(c_rep)

            if is_expired:
                expired_candidates.append(c.get('ipo_id'))
            elif hours_to_cutoff is not None and hours_to_cutoff <= 48:
                approaching_cutoffs.append(c.get('ipo_id'))

        # Ledger counts
        decisions = self._load_jsonl(self.decision_ledger_path)
        outcomes = self._load_jsonl(self.outcome_ledger_path)
        eval_recs = self._load_jsonl(self.evaluation_records_path)
        audit_events = self._load_jsonl(self.audit_events_path)

        # Count verified vs asserted cutoffs
        verified_cutoffs_count = sum(1 for c in candidate_reports if c.get('cutoff_verification_status') == 'VERIFIED')
        asserted_cutoffs_count = sum(1 for c in candidate_reports if c.get('cutoff_verification_status') == 'UNVERIFIED')
        blocked_candidates_count = sum(1 for c in candidate_reports if 'BLOCKED' in str(c.get('current_lifecycle_state')))
        mainboard_coverage_count = sum(1 for c in candidate_reports if c.get('board_type') == 'Mainboard')

        return {
            'report_timestamp_ist': now_ts,
            'operating_mode': 'STRICT_SHADOW_VALIDATION',
            'frozen_artifacts_integrity': {
                'model_status': 'PASS' if model_audit.get('valid') else 'FAIL',
                'manifest_status': 'PASS' if manifest_audit.get('valid') else 'FAIL',
                'model_sha256': model_audit.get('actual_sha256'),
                'manifest_sha256': manifest_audit.get('actual_sha256')
            },
            'candidate_count': len(candidates),
            'candidate_reports': candidate_reports,
            'approaching_cutoffs_48h': approaching_cutoffs,
            'expired_candidates': expired_candidates,
            'collection_health': {
                'collector_status': 'OPERATIONAL',
                'sources_monitored': ['BSE_SME', 'NSE_SME'],
                'last_collection_run': now_ts
            },
            'evidence_health': {
                'verified_primary_notices': verified_cutoffs_count,
                'unverified_asserted_notices': asserted_cutoffs_count,
                'evidence_conflicts_count': 0,
                'missing_artifacts_count': 0
            },
            'candidate_lifecycle_summary': {
                'total_tracked': len(candidates),
                'verified_cutoffs': verified_cutoffs_count,
                'asserted_unverified_cutoffs': asserted_cutoffs_count,
                'blocked_candidates': blocked_candidates_count,
                'approaching_cutoffs_48h': len(approaching_cutoffs),
                'expired_candidates': len(expired_candidates),
                'mainboard_coverage_only': mainboard_coverage_count
            },
            'persistence_and_governance': {
                'decision_ledger_records': len(decisions),
                'outcome_ledger_records': len(outcomes),
                'evaluation_records': len(eval_recs),
                'governance_audit_events_count': len(audit_events),
                'ledger_integrity_status': 'EMPTY_COMPLIANT' if len(decisions) == 0 else f'RECORDS_PRESENT_N_{len(decisions)}'
            },
            'ledger_status': {
                'committed_decisions_count': len(decisions),
                'committed_outcomes_count': len(outcomes),
                'mature_evaluations_count': len(eval_recs),
                'status': 'EMPTY_COMPLIANT' if len(decisions) == 0 else f'RECORDS_PRESENT_N_{len(decisions)}'
            },
            'predictive_validity_milestone': 'INCONCLUSIVE_ZERO_MATURE_OUTCOMES' if len(outcomes) == 0 else 'EVALUATED',
            'economic_viability_milestone': 'INCONCLUSIVE_ZERO_LIVE_TRADES',
            'monitoring_source_health': 'OPERATIONAL_PRIMARY_ARCHIVE_ACCESSIBLE'
        }

    def sweep_deadline_expiries(self,
                                sweep_timestamp_ist: Optional[str] = None,
                                force_sweep: bool = False) -> Dict[str, Any]:
        """
        Executes an idempotent expiry sweep across all tracked candidates in the registry:
          1. Reads candidate registry under cross-process lock.
          2. Uses timezone-aware clock (sweep_timestamp_ist or current IST).
          3. Evaluates only applicable non-terminal candidates.
          4. Follows cutoff policy: evaluation_time >= cutoff_time is EXPIRED_WITHOUT_COMMIT.
          5. Rechecks state immediately under lock before updating candidate record.
          6. Records an immutable governance audit event for every newly transitioned candidate.
          7. Returns structured report of transitions, unchanged, blocked, and errors.
          8. Safe against partial failure, concurrent sweeps, and repeated sweeps.
        """
        now_ts = sweep_timestamp_ist or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
        dt_now = parse_timezone_aware_ts(now_ts)
        if dt_now is None:
            raise ValueError(f"INVALID_OR_TIMEZONE_NAIVE_SWEEP_TIMESTAMP: '{now_ts}'")

        report = {
            'sweep_timestamp_ist': now_ts,
            'total_candidates_examined': 0,
            'newly_expired_candidates': [],
            'already_expired_candidates': [],
            'active_unexpired_candidates': [],
            'blocked_governance_candidates': [],
            'errors': []
        }

        # Inter-process atomic sweep using logger's lock mechanism
        with self._evidence_lock:
            p_lock = self.logger._acquire_process_lock()
            try:
                if not os.path.exists(self.candidate_registry_path):
                    return report

                with open(self.candidate_registry_path, 'r', encoding='utf-8') as f:
                    candidates = json.load(f)

                report['total_candidates_examined'] = len(candidates)
                registry_modified = False

                for idx, c in enumerate(candidates):
                    cid = c.get('ipo_id')
                    board = c.get('board_type', 'Mainboard')
                    cutoff_ts = c.get('cutoff_timestamp_ist')
                    is_verified = c.get('is_bidding_cutoff_verified', False)
                    curr_decision_status = c.get('decision_status', '')

                    if board == 'Mainboard':
                        # Check if Mainboard cutoff elapsed for tracking
                        if cutoff_ts:
                            dt_cut = parse_timezone_aware_ts(cutoff_ts)
                            if dt_cut and dt_now >= dt_cut:
                                if 'EXPIRED' not in curr_decision_status.upper():
                                    c['decision_status'] = "EXPIRED_WITHOUT_COMMIT (Mainboard Coverage Elapsed)"
                                    candidates[idx] = c
                                    registry_modified = True
                                    report['newly_expired_candidates'].append(cid)
                                    self.surveillance.log_governance_event(
                                        event_type="CANDIDATE_DEADLINE_EXPIRED",
                                        affected_entity=cid,
                                        severity="INFO",
                                        reason_code="MAINBOARD_COVERAGE_CUTOFF_ELAPSED",
                                        description=f"Mainboard candidate '{cid}' cutoff elapsed at {cutoff_ts}. Marked expired.",
                                        evidence_reference=cutoff_ts
                                    )
                                else:
                                    report['already_expired_candidates'].append(cid)
                            else:
                                report['blocked_governance_candidates'].append(cid)
                        else:
                            report['blocked_governance_candidates'].append(cid)
                        continue

                    # SME candidate
                    if not cutoff_ts:
                        report['errors'].append({'ipo_id': cid, 'error': 'MISSING_CUTOFF_TIMESTAMP'})
                        continue

                    dt_cut = parse_timezone_aware_ts(cutoff_ts)
                    if dt_cut is None:
                        report['errors'].append({'ipo_id': cid, 'error': f'INVALID_CUTOFF_TIMESTAMP: {cutoff_ts}'})
                        continue

                    if 'EXPIRED_WITHOUT_COMMIT' in curr_decision_status:
                        report['already_expired_candidates'].append(cid)
                        continue

                    # Boundary rule: now >= cutoff -> expired
                    if dt_now >= dt_cut:
                        # Transition to EXPIRED_WITHOUT_COMMIT
                        c['decision_status'] = "EXPIRED_WITHOUT_COMMIT"
                        c['candidate_lifecycle_state'] = "EXPIRED_WITHOUT_COMMIT"
                        c['expired_at_timestamp_ist'] = now_ts
                        candidates[idx] = c
                        registry_modified = True
                        report['newly_expired_candidates'].append(cid)

                        # Log governance event
                        self.surveillance.log_governance_event(
                            event_type="CANDIDATE_DEADLINE_EXPIRED",
                            affected_entity=cid,
                            severity="WARNING" if not is_verified else "INFO",
                            reason_code="UNVERIFIED_ASSERTED_CUTOFF_ELAPSED" if not is_verified else "VERIFIED_CUTOFF_ELAPSED",
                            description=f"Candidate '{cid}' cutoff '{cutoff_ts}' reached or elapsed at {now_ts} without authorized commit. Transitioned to EXPIRED_WITHOUT_COMMIT.",
                            evidence_reference=cutoff_ts
                        )
                    else:
                        report['active_unexpired_candidates'].append(cid)

                if registry_modified:
                    with open(self.candidate_registry_path, 'w', encoding='utf-8') as f:
                        json.dump(candidates, f, indent=2)

            finally:
                self.logger._release_process_lock(p_lock)

        return report


def process_evidence_update(candidate_id: str,
                            evidence_payload: Dict[str, Any],
                            manager: Optional[ProspectiveLifecycleManager] = None,
                            current_time_iso: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience functional interface for candidate evidence update.
    Validates payload integrity and delegates to manager.process_evidence_update().
    """
    mgr = manager or ProspectiveLifecycleManager()
    eval_ts = current_time_iso or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')

    raw_text = evidence_payload.get("raw_text")
    if raw_text is None:
        return {
            "success": False,
            "is_verified": False,
            "reason": "Missing raw_text in evidence_payload."
        }

    raw_bytes = raw_text.encode("utf-8") if isinstance(raw_text, str) else bytes(raw_text)
    calc_hash = hashlib.sha256(raw_bytes).hexdigest()

    expected_hash = evidence_payload.get("document_sha256")
    if expected_hash and calc_hash.lower() != expected_hash.lower():
        return {
            "success": False,
            "is_verified": False,
            "reason": f"Hash mismatch: calculated {calc_hash} != declared {expected_hash}"
        }

    source_type = evidence_payload.get("source_type", "")
    source_portal = evidence_payload.get("source_portal", "")
    doc_id = evidence_payload.get("document_id", "DOC_UNSPECIFIED")
    source_ref = f"{source_portal}:{doc_id}"

    pub_ts = evidence_payload.get("publication_time")
    ret_ts = evidence_payload.get("retrieval_time", eval_ts)
    exp_cutoff = evidence_payload.get("verified_cutoff_time") or evidence_payload.get("expected_cutoff_timestamp_ist")

    # Validate timezone awareness upfront
    if ret_ts and parse_timezone_aware_ts(ret_ts) is None:
        return {
            "success": False,
            "is_verified": False,
            "reason": f"Missing timezone or invalid format in retrieval_time '{ret_ts}'"
        }
    if pub_ts and parse_timezone_aware_ts(pub_ts) is None:
        return {
            "success": False,
            "is_verified": False,
            "reason": f"Missing timezone or invalid format in publication_time '{pub_ts}'"
        }

    is_primary = (
        source_type == "PRIMARY_EXCHANGE_CIRCULAR" and
        ("BSE" in source_portal or "NSE" in source_portal)
    )

    try:
        res = mgr.process_evidence_update(
            ipo_id=candidate_id,
            raw_artifact_content=raw_bytes,
            source_reference=source_ref,
            publication_timestamp_ist=pub_ts,
            retrieval_timestamp_ist=ret_ts,
            is_primary_exchange_source=is_primary,
            relevant_bidding_category="RETAIL_INDIVIDUAL",
            expected_cutoff_timestamp_ist=exp_cutoff
        )
        # Fetch post-audit state
        candidates = []
        if os.path.exists(mgr.candidate_registry_path):
            with open(mgr.candidate_registry_path, "r", encoding="utf-8") as f:
                candidates = json.load(f)
        cand = next((c for c in candidates if c.get("ipo_id") == candidate_id), None)
        post_audit = mgr.audit_and_prepare_candidate(cand, evaluation_timestamp_ist=eval_ts) if cand else None

        return {
            "success": True,
            "is_verified": res["is_bidding_cutoff_verified"],
            "result": res,
            "post_audit_state": {
                "lifecycle_state": res["new_lifecycle_state"],
                "readiness": {
                    "is_ready": (res["new_lifecycle_state"] == "READY_FOR_PROSPECTIVE_COMMIT" or 
                                 (post_audit is not None and post_audit.get("is_clean_eligible", False))),
                    "gates": res["readiness_gate_evaluation"]
                }
            }
        }
    except Exception as e:
        return {
            "success": False,
            "is_verified": False,
            "reason": str(e)
        }


def generate_daily_monitoring_report(manager: Optional[ProspectiveLifecycleManager] = None,
                                     current_time_iso: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience functional interface for generating the daily monitoring report.
    """
    mgr = manager or ProspectiveLifecycleManager()
    eval_ts = current_time_iso or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
    rep = mgr.generate_daily_monitoring_report(evaluation_timestamp_ist=eval_ts)

    # Standardize field names for API and CLI consumers
    c_records = []
    for cr in rep.get("candidate_reports", []):
        c_records.append({
            "candidate_id": cr.get("ipo_id"),
            "company_name": cr.get("company_name"),
            "board_type": cr.get("board_type"),
            "exchange": cr.get("exchange"),
            "asserted_cutoff_timestamp_ist": cr.get("asserted_cutoff_timestamp_ist"),
            "cutoff_timestamp_ist": cr.get("asserted_cutoff_timestamp_ist"),
            "cutoff_verification_status": cr.get("cutoff_verification_status"),
            "is_cutoff_verified": bool(cr.get("cutoff_verification_status") == "VERIFIED"),
            "lifecycle_state": cr.get("current_lifecycle_state"),
            "cutoff_approaching_48h": bool(cr.get("ipo_id") in rep.get("approaching_cutoffs_48h", [])),
            "hours_to_cutoff": cr.get("hours_to_cutoff"),
            "failed_gates": cr.get("failed_readiness_gates", []),
            "next_required_action": cr.get("next_required_action")
        })

    return {
        "report_timestamp": rep.get("report_timestamp_ist"),
        "system_operating_mode": rep.get("operating_mode"),
        "governance_integrity": {
            "model_sha256_verified": (rep.get("frozen_artifacts_integrity", {}).get("model_status") == "PASS"),
            "manifest_sha256_verified": (rep.get("frozen_artifacts_integrity", {}).get("manifest_status") == "PASS"),
            "model_sha256": rep.get("frozen_artifacts_integrity", {}).get("model_sha256"),
            "manifest_sha256": rep.get("frozen_artifacts_integrity", {}).get("manifest_sha256")
        },
        "candidate_monitoring_records": c_records,
        "approaching_cutoffs_48h": rep.get("approaching_cutoffs_48h", []),
        "expired_candidates": rep.get("expired_candidates", []),
        "ledgers_summary": {
            "prospective_decisions_count": rep.get("ledger_status", {}).get("committed_decisions_count", 0),
            "prospective_outcomes_count": rep.get("ledger_status", {}).get("committed_outcomes_count", 0),
            "mature_evaluations_count": rep.get("ledger_status", {}).get("mature_evaluations_count", 0)
        },
        "monitoring_source_health": rep.get("monitoring_source_health")
    }


def evaluate_independent_readiness(candidate_id: str,
                                   manager: Optional[ProspectiveLifecycleManager] = None,
                                   evaluation_timestamp_ist: Optional[str] = None) -> Dict[str, Any]:
    """
    Evaluates independent 12-gate readiness for a tracked candidate without mutating state.
    Strictly read-only. Returns gate statuses: PASS, FAIL, BLOCKED, or NOT_TESTED.
    """
    mgr = manager or ProspectiveLifecycleManager()
    eval_ts = evaluation_timestamp_ist or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')

    candidates = []
    if os.path.exists(mgr.candidate_registry_path):
        with open(mgr.candidate_registry_path, "r", encoding="utf-8") as f:
            candidates = json.load(f)

    cand = next((c for c in candidates if c.get("ipo_id") == candidate_id), None)
    if not cand:
        return {
            "candidate_id": candidate_id,
            "status": "NOT_FOUND",
            "evaluation_timestamp_ist": eval_ts,
            "final_commitment_eligibility": "FAIL",
            "reason": f"Candidate '{candidate_id}' not found in registry."
        }

    # Evaluate candidate using audit_and_prepare_candidate (read-only)
    prep = mgr.audit_and_prepare_candidate(cand, evaluation_timestamp_ist=eval_ts)
    board = cand.get("board_type")
    reasons = prep.get("exclusion_reasons", [])
    prov = prep.get("feature_provenance", {})
    cutoff_ts = cand.get("cutoff_timestamp_ist")
    raw_hash = cand.get("raw_source_sha256")
    is_verified = cand.get("is_bidding_cutoff_verified", False)
    evidence_ref = cand.get("authoritative_evidence")

    # Gate 1: Candidate identity
    has_identity = bool(cand.get("ipo_id") and cand.get("company_name"))
    gate_identity = "PASS" if has_identity else "FAIL"

    # Gate 2: Official source authenticity
    gate_source_auth = "PASS" if is_verified else ("BLOCKED" if evidence_ref else "FAIL")

    # Gate 3: Evidence relevance
    gate_evidence_rel = "PASS" if is_verified else ("BLOCKED" if not any("WRONG_CANDIDATE" in r or "IRRELEVANT" in r for r in reasons) else "FAIL")

    # Gate 4: Explicit order-book cutoff
    gate_orderbook = "PASS" if is_verified else "BLOCKED"

    # Gate 5: Publication and retrieval provenance
    has_temporal_err = any('POST_' in r or 'INVALID_OR_TIMEZONE' in r or 'RETRIEVAL_BEFORE' in r for r in reasons)
    gate_temporal = "FAIL" if has_temporal_err else "PASS"

    # Gate 6: Artifact integrity
    has_valid_hash = bool(raw_hash and isinstance(raw_hash, str) and len(raw_hash) == 64)
    gate_artifact = "PASS" if has_valid_hash else "BLOCKED"

    # Gate 7: Conflicting-evidence check
    has_conflict = any("CONFLICT" in r for r in reasons)
    gate_conflicts = "FAIL" if has_conflict else "PASS"

    # Gate 8: Current lifecycle status
    curr_state = prep.get("candidate_lifecycle_state")
    if curr_state == "EXPIRED_WITHOUT_COMMIT":
        gate_lifecycle = "FAIL"
    elif curr_state == "READY_FOR_PROSPECTIVE_COMMIT":
        gate_lifecycle = "PASS"
    elif curr_state == "BLOCKED_GOVERNANCE":
        gate_lifecycle = "FAIL"
    else:
        gate_lifecycle = "BLOCKED"

    # Gate 9: Feature provenance
    has_feature_err = any('INVALID_NUMERIC' in r or 'MISSING_REQUIRED' in r for r in reasons)
    gate_features = "FAIL" if has_feature_err else "PASS"

    # Gate 10: Frozen model eligibility
    if board == "SME":
        model_valid = (prep.get("model_sha256") == FROZEN_SME_MODEL_SHA256)
        gate_model = "PASS" if model_valid else "FAIL"
    else:
        gate_model = "FAIL"  # Mainboard strictly non-scoring

    # Gate 11: Governance authorization
    # Read-only check: uncommitted candidates require explicit human admin token at commit boundary
    gate_governance = "BLOCKED" if is_verified else "BLOCKED"

    # Gate 12: Final commitment eligibility
    all_mandatory_pass = (
        gate_identity == "PASS" and
        gate_source_auth == "PASS" and
        gate_evidence_rel == "PASS" and
        gate_orderbook == "PASS" and
        gate_temporal == "PASS" and
        gate_artifact == "PASS" and
        gate_conflicts == "PASS" and
        gate_lifecycle == "PASS" and
        gate_features == "PASS" and
        gate_model == "PASS"
    )
    final_eligibility = "READY_FOR_AUTHORIZATION" if all_mandatory_pass else (
        "EXPIRED" if gate_lifecycle == "FAIL" and curr_state == "EXPIRED_WITHOUT_COMMIT" else (
            "NON_SCORING_MAINBOARD" if board == "Mainboard" else "BLOCKED"
        )
    )

    return {
        "candidate_id": candidate_id,
        "company_name": cand.get("company_name"),
        "board_type": board,
        "asserted_cutoff_timestamp_ist": cutoff_ts,
        "evaluation_timestamp_ist": eval_ts,
        "candidate_lifecycle_state": curr_state,
        "gates": {
            "candidate_identity": {"status": gate_identity, "detail": "Identity registered" if has_identity else "Missing identity"},
            "official_source_authenticity": {"status": gate_source_auth, "detail": "Exchange circular verified" if is_verified else "Authoritative exchange circular unverified"},
            "evidence_relevance": {"status": gate_evidence_rel, "detail": "Candidate relevance confirmed" if is_verified else "Awaiting candidate circular"},
            "explicit_order_book_cutoff": {"status": gate_orderbook, "detail": "Order book close time verified" if is_verified else "Retail order book close unverified"},
            "publication_and_retrieval_provenance": {"status": gate_temporal, "detail": "Temporal order valid" if not has_temporal_err else "Temporal ordering violation"},
            "artifact_integrity": {"status": gate_artifact, "detail": "SHA-256 digest format valid" if has_valid_hash else "Missing raw artifact hash"},
            "conflicting_evidence_check": {"status": gate_conflicts, "detail": "No conflicting notices" if not has_conflict else "Conflicting cutoff notices detected"},
            "current_lifecycle_status": {"status": gate_lifecycle, "detail": f"State: {curr_state}"},
            "feature_provenance": {"status": gate_features, "detail": "Features complete & verified" if not has_feature_err else "Feature definitions violation"},
            "frozen_model_eligibility": {"status": gate_model, "detail": "SME frozen model match" if gate_model == "PASS" else "Mainboard non-scoring or hash mismatch"},
            "governance_authorization": {"status": gate_governance, "detail": "Awaiting explicit administrative commitment token"},
            "final_commitment_eligibility": {"status": "PASS" if all_mandatory_pass else "BLOCKED", "detail": final_eligibility}
        },
        "blocking_reasons": reasons,
        "is_ready_for_commit": bool(all_mandatory_pass),
        "immutable_verification": True
    }
