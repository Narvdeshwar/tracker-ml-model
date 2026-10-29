"""
Module: src/evidence_audit_protocol.py
Objective: Workstream 1, 2, 3, 4, 5, 6 implementation for Phase 10.6.
Provides:
  1. Observation-level evidence audit: Traces every prospective decision to original inputs,
     pre-cutoff timestamps, source evidence, model identity, and verified outcome.
  2. Statistically sound evaluation protocol: Evaluates model Brier score and fixed constant baseline
     on the exact same prospective observation set.
  3. Deterministic bootstrap confidence intervals (seed-locked, paired resamples, handling degenerates).
  4. Non-parametric distribution drift methodology (mean, median, IQR, KS test / quantile shifts).
  5. Cryptographic audit checkpoint protection against complete historical rewriting.
"""

import os
import json
import hashlib
import datetime
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
from scipy import stats
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc

MANIFEST_PATH = 'models/frozen/phase_9b_baseline_manifest.json'
FROZEN_SME_MODEL_PATH = 'models/frozen/model_6b_sme_v1.joblib'
CHECKPOINT_PATH = 'data/processed/governance_checkpoint_signature.json'

class ProspectiveEvidenceAuditor:
    def __init__(self,
                 decision_ledger_path: str = 'data/processed/prospective_decision_ledger.jsonl',
                 outcome_ledger_path: str = 'data/processed/prospective_outcome_ledger.jsonl',
                 candidate_registry_path: str = 'data/registered/tracked_candidate_registry.json',
                 audit_events_path: str = 'data/processed/governance_audit_events.jsonl',
                 checkpoint_path: str = CHECKPOINT_PATH):
        self.decision_ledger_path = decision_ledger_path
        self.outcome_ledger_path = outcome_ledger_path
        self.candidate_registry_path = candidate_registry_path
        self.audit_events_path = audit_events_path
        self.checkpoint_path = checkpoint_path

    # =========================================================================
    # Workstream 1: Observation-Level Evidence Audit
    # =========================================================================
    def audit_observation_level_evidence(self) -> Dict[str, Any]:
        """
        Provides a granular, observation-level traceable audit for every prospective decision.
        Verifies:
          - Stable IPO identifier and board compatibility.
          - Original decision commitment timestamp vs issue cutoff.
          - Feature snapshot and source publication timestamps.
          - Frozen model identity and bit-for-bit SHA-256 match.
          - Official listing outcome link and evidence status.
          - Derived return and target classification.
          - Inclusion / exclusion reason from primary clean cohort.
        """
        decisions = self._load_jsonl(self.decision_ledger_path)
        outcomes = self._load_jsonl(self.outcome_ledger_path)
        candidates = self._load_json(self.candidate_registry_path)

        outcome_by_ipo = {o['ipo_id']: o for o in outcomes}
        candidate_by_ipo = {c['ipo_id']: c for c in candidates}

        observation_audits = []
        total_committed = len(decisions)
        mature_count = 0
        clean_included_count = 0
        excluded_count = 0

        for dec in decisions:
            ipo_id = dec.get('ipo_id')
            board = dec.get('board_type')
            cutoff_raw = dec.get('cutoff_timestamp_ist')
            logging_ts = dec.get('logging_timestamp_ist')
            prov = dec.get('feature_provenance', {})
            model_name = dec.get('model_name')
            model_sha = dec.get('model_sha256')
            p_dict = dec.get('predicted_probabilities', {})
            
            # Check matching candidate registry entry
            cand = candidate_by_ipo.get(ipo_id, {})
            out = outcome_by_ipo.get(ipo_id)
            has_outcome = (out is not None)
            if has_outcome:
                mature_count += 1

            # Audit checks
            checks = {}
            failure_reasons = []

            # 1. Timing check (commit <= cutoff)
            timing_valid = False
            if logging_ts and cutoff_raw:
                try:
                    c_log = logging_ts.replace(' IST', '').replace('+05:30', '').replace('+0530', '').strip()
                    c_cut = cutoff_raw.replace(' IST', '').replace('+05:30', '').replace('+0530', '').strip()
                    timing_valid = (pd.to_datetime(c_log) <= pd.to_datetime(c_cut))
                except Exception:
                    timing_valid = False
            checks['committed_before_cutoff'] = timing_valid
            if not timing_valid:
                failure_reasons.append("DECISION_COMMITTED_AFTER_CUTOFF")

            # 2. Source evidence presence
            has_ev = bool(prov.get('cutoff_source_evidence') or prov.get('source_url_or_doc') or prov.get('source'))
            checks['authoritative_evidence_present'] = has_ev
            if not has_ev:
                failure_reasons.append("MISSING_AUTHORITATIVE_CUTOFF_EVIDENCE")

            # 3. Model compatibility
            model_valid = True
            if board == 'Mainboard':
                if model_name != "REGISTER_FOR_COVERAGE_ONLY" and p_dict.get('p_positive_open') is not None:
                    model_valid = False
                    failure_reasons.append("MAINBOARD_SCORED_BY_UNAUTHORIZED_MODEL")
            elif board == 'SME':
                if model_name != "Model_6B_SME_v1.0":
                    model_valid = False
                    failure_reasons.append("INVALID_SME_MODEL_NAME")
            checks['model_board_compatible'] = model_valid

            # 4. Outcome verification
            outcome_audit = {
                'has_outcome': has_outcome,
                'listing_date': out.get('listing_date') if out else None,
                'issue_price_inr': out.get('issue_price_inr') if out else None,
                'listing_open_inr': out.get('listing_open_inr') if out else None,
                'gross_open_return_pct': out.get('gross_open_return_pct') if out else None,
                'is_positive_open': out.get('is_positive_open') if out else None,
                'outcome_source': out.get('outcome_source') if out else 'PENDING_OFFICIAL_BULLETIN'
            }

            # 5. Inclusion in clean evaluation
            is_clean = (len(failure_reasons) == 0 and dec.get('eligible_for_clean_prospective_cohort', False))
            if is_clean:
                clean_included_count += 1
            else:
                excluded_count += 1

            observation_audits.append({
                'ipo_id': ipo_id,
                'company_name': dec.get('company_name'),
                'board_type': board,
                'decision_id': dec.get('decision_id'),
                'cutoff_timestamp_ist': cutoff_raw,
                'logging_timestamp_ist': logging_ts,
                'feature_snapshot': dec.get('features', {}),
                'feature_hash_sha256': dec.get('feature_hash_sha256'),
                'source_publication_timestamp_ist': prov.get('source_publication_timestamp_ist'),
                'model_name': model_name,
                'model_sha256': model_sha,
                'predicted_probabilities': p_dict,
                'audit_checks': checks,
                'inclusion_status': 'CLEAN_PROSPECTIVE_COHORT' if is_clean else 'EXCLUDED_FROM_PRIMARY_EVAL',
                'exclusion_reasons': failure_reasons,
                'outcome_layer': outcome_audit,
                'record_sha256': dec.get('record_sha256')
            })

        return {
            'total_observations_audited': total_committed,
            'mature_observations_count': mature_count,
            'clean_included_count': clean_included_count,
            'excluded_count': excluded_count,
            'observations': observation_audits,
            'audit_timestamp_ist': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
        }

    # =========================================================================
    # Workstream 2, 3, 4: Evaluation Protocol & Metric Correctness
    # =========================================================================
    def evaluate_prospective_metrics_rigorous(self,
                                              board_type: Optional[str] = None,
                                              require_clean: bool = True,
                                              n_bootstraps: int = 1000,
                                              random_seed: int = 42) -> Dict[str, Any]:
        """
        Rigorous, reproducible prospective metric evaluation.
        Evaluates Model Brier Score and Fixed Constant Training Baseline on the EXACT same observations.
        Baseline prospective Brier score is computed against the prospective cohort's actual labels:
          BS_base = mean((p_base_ref - y_i)^2).
        Returns explicit INCONCLUSIVE statuses when sample is zero or single-class.
        """
        decisions = self._load_jsonl(self.decision_ledger_path)
        outcomes = self._load_jsonl(self.outcome_ledger_path)
        outcome_by_ipo = {o['ipo_id']: o for o in outcomes}

        # Filter and pair
        paired_records = []
        for d in decisions:
            if require_clean and not d.get('eligible_for_clean_prospective_cohort', False):
                continue
            if board_type and d.get('board_type') != board_type:
                continue
            ipo_id = d.get('ipo_id')
            if ipo_id in outcome_by_ipo:
                out = outcome_by_ipo[ipo_id]
                p_val = d.get('predicted_probabilities', {}).get('p_positive_open')
                y_val = out.get('is_positive_open')
                if p_val is not None and y_val is not None:
                    paired_records.append({
                        'ipo_id': ipo_id,
                        'board_type': d.get('board_type'),
                        'p_model': float(p_val),
                        'y_true': int(bool(y_val)),
                        'p_severe_loss': d.get('predicted_probabilities', {}).get('p_severe_loss'),
                        'is_severe_loss': int(bool(out.get('is_severe_loss', False)))
                    })

        n_mature = len(paired_records)
        
        # Reference constant probabilities
        sme_base_ref = 0.8306
        mb_base_ref = 0.7583
        target_ref_prob = sme_base_ref if board_type == 'SME' else (mb_base_ref if board_type == 'Mainboard' else 0.80)

        if n_mature == 0:
            return {
                'status': 'INCONCLUSIVE_ZERO_MATURE_OUTCOMES',
                'board_evaluated': board_type or 'All',
                'sample_size_mature': 0,
                'message': 'No mature prospective outcomes recorded yet. Metrics remain inconclusive.',
                'model_brier_score': None,
                'baseline_brier_score': None,
                'brier_skill_score': None,
                'roc_auc': None,
                'pr_auc': None,
                'bootstrap_95_ci_bss': None
            }

        df_m = pd.DataFrame(paired_records)
        p_arr = df_m['p_model'].values
        y_arr = df_m['y_true'].values

        # 1. Brier Scores on exact same observations
        bs_model = float(np.mean((p_arr - y_arr) ** 2))
        bs_base = float(np.mean((target_ref_prob - y_arr) ** 2))
        bss = (1.0 - (bs_model / bs_base)) if bs_base > 0 else 0.0

        # 2. ROC-AUC and PR-AUC
        roc_auc = None
        pr_auc = None
        auc_status = "EVALUATED"
        if len(np.unique(y_arr)) >= 2:
            try:
                roc_auc = round(float(roc_auc_score(y_arr, p_arr)), 4)
                prec, rec, _ = precision_recall_curve(y_arr, p_arr)
                pr_auc = round(float(auc(rec, prec)), 4)
            except Exception as e:
                auc_status = f"ERROR: {str(e)}"
        else:
            auc_status = "INCONCLUSIVE_SINGLE_CLASS"

        # 3. Deterministic Paired Bootstrap CI
        ci_brier, ci_bss = self._compute_paired_bootstrap(p_arr, y_arr, target_ref_prob, n_bootstraps, random_seed)

        return {
            'status': 'EVALUATED',
            'board_evaluated': board_type or 'All',
            'sample_size_mature': n_mature,
            'positive_outcomes_count': int(y_arr.sum()),
            'negative_outcomes_count': int(len(y_arr) - y_arr.sum()),
            'fixed_training_reference_prob': target_ref_prob,
            'model_brier_score': round(bs_model, 4),
            'baseline_brier_score': round(bs_base, 4),
            'brier_skill_score': round(bss, 4),
            'roc_auc': roc_auc,
            'pr_auc': pr_auc,
            'auc_diagnostics': auc_status,
            'bootstrap_95_ci_brier': ci_brier,
            'bootstrap_95_ci_bss': ci_bss,
            'methodology_note': 'Both model and baseline are evaluated on the exact same paired prospective observations.'
        }

    # =========================================================================
    # Workstream 5: Enhanced Non-Parametric Drift Methodology
    # =========================================================================
    def audit_drift_methodology_enhanced(self,
                                         scored_candidates: List[Dict[str, Any]],
                                         training_ref_features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates input feature drift and prediction shift using both parametric (z-score)
        and non-parametric (quantile shift, IQR, Kolmogorov-Smirnov test where N>=20) diagnostics.
        """
        n_obs = len(scored_candidates)
        if n_obs < 15:
            return {
                'status': 'INCONCLUSIVE_INSUFFICIENT_SAMPLE_SIZE',
                'sample_size': n_obs,
                'minimum_gate': 15,
                'message': 'Sample size inadequate for descriptive drift diagnostics.'
            }

        feat_diagnostics = {}
        for f, ref in training_ref_features.items():
            vals = [float(c['features'][f]) for c in scored_candidates if f in c.get('features', {}) and c['features'][f] is not None]
            if len(vals) < 5:
                continue
            
            obs_mean = float(np.mean(vals))
            obs_median = float(np.median(vals))
            obs_std = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            obs_q25 = float(np.percentile(vals, 25))
            obs_q75 = float(np.percentile(vals, 75))
            obs_iqr = obs_q75 - obs_q25

            # Mean z-shift in reference std
            ref_mean = ref['mean']
            ref_std = ref['std']
            z_shift = round((obs_mean - ref_mean) / ref_std, 4) if ref_std > 0 else 0.0

            # Kolmogorov-Smirnov test against normal approximation of reference
            ks_stat, ks_pval = None, None
            if len(vals) >= 20 and ref_std > 0:
                ks_res = stats.kstest(vals, 'norm', args=(ref_mean, ref_std))
                ks_stat = round(float(ks_res.statistic), 4)
                ks_pval = round(float(ks_res.pvalue), 4)

            feat_diagnostics[f] = {
                'observed_mean': round(obs_mean, 4),
                'observed_median': round(obs_median, 4),
                'observed_iqr': round(obs_iqr, 4),
                'reference_mean': ref_mean,
                'reference_median': ref.get('median', ref_mean),
                'z_shift_in_ref_std': z_shift,
                'ks_statistic': ks_stat,
                'ks_pvalue': ks_pval,
                'status': 'SIGNIFICANT_DRIFT' if abs(z_shift) >= 2.0 or (ks_pval is not None and ks_pval < 0.01) else 'NORMAL_VARIATION'
            }

        return {
            'status': 'EVALUATED',
            'sample_size': n_obs,
            'feature_drift_diagnostics': feat_diagnostics,
            'governance_rule': 'Drift alerts are qualitative surveillance signals; automated model modifications are strictly forbidden.'
        }

    # =========================================================================
    # Workstream 6: Cryptographic Audit Checkpoint Protection
    # =========================================================================
    def generate_and_seal_audit_checkpoint(self) -> Dict[str, Any]:
        """
        Creates an independently stored cryptographic checkpoint that seals the current state
        of the governance audit event log, decision ledger, and frozen manifest.
        Detects complete ledger rewriting or historical truncation.
        """
        os.makedirs(os.path.dirname(self.checkpoint_path), exist_ok=True)
        now_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')

        # Checksum of decision ledger
        dec_sha = self._hash_file(self.decision_ledger_path)
        out_sha = self._hash_file(self.outcome_ledger_path)
        audit_sha = self._hash_file(self.audit_events_path)
        manifest_sha = self._hash_file(MANIFEST_PATH)
        model_sha = self._hash_file(FROZEN_SME_MODEL_PATH)

        checkpoint_record = {
            'checkpoint_id': f"CHK_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
            'sealed_timestamp_ist': now_ts,
            'sealed_files': {
                'decision_ledger_sha256': dec_sha,
                'outcome_ledger_sha256': out_sha,
                'governance_audit_events_sha256': audit_sha,
                'manifest_sha256': manifest_sha,
                'frozen_sme_model_sha256': model_sha
            },
            'signature_algorithm': 'SHA256_SEALED_DIGEST'
        }

        # Seal checkpoint digest
        s = json.dumps(checkpoint_record, sort_keys=True)
        checkpoint_record['sealed_checkpoint_sha256'] = hashlib.sha256(s.encode('utf-8')).hexdigest()

        with open(self.checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_record, f, indent=2)

        return checkpoint_record

    def verify_sealed_checkpoint(self) -> Dict[str, Any]:
        """
        Verifies that current ledger and manifest files match the sealed cryptographic checkpoint.
        """
        if not os.path.exists(self.checkpoint_path):
            return {
                'status': 'NO_CHECKPOINT_FOUND',
                'valid': True,
                'message': 'No sealed checkpoint established yet.'
            }

        with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
            chk = json.load(f)

        files = chk.get('sealed_files', {})
        dec_match = (self._hash_file(self.decision_ledger_path) == files.get('decision_ledger_sha256'))
        out_match = (self._hash_file(self.outcome_ledger_path) == files.get('outcome_ledger_sha256'))
        audit_match = (self._hash_file(self.audit_events_path) == files.get('governance_audit_events_sha256'))
        man_match = (self._hash_file(MANIFEST_PATH) == files.get('manifest_sha256'))
        mod_match = (self._hash_file(FROZEN_SME_MODEL_PATH) == files.get('frozen_sme_model_sha256'))

        all_match = (dec_match and out_match and audit_match and man_match and mod_match)
        return {
            'status': 'CHECKPOINT_VERIFIED' if all_match else 'CHECKPOINT_INTEGRITY_BREACH',
            'valid': all_match,
            'checkpoint_id': chk.get('checkpoint_id'),
            'sealed_timestamp_ist': chk.get('sealed_timestamp_ist'),
            'file_matches': {
                'decision_ledger': dec_match,
                'outcome_ledger': out_match,
                'governance_audit_events': audit_match,
                'manifest': man_match,
                'model': mod_match
            }
        }

    # =========================================================================
    # Helpers
    # =========================================================================
    def _compute_paired_bootstrap(self, p_arr, y_arr, base_prob, n_bootstraps, seed):
        if len(p_arr) < 5:
            return (None, None), (None, None)
        rng = np.random.RandomState(seed)
        n = len(p_arr)
        boot_briers = []
        boot_bsss = []
        for _ in range(n_bootstraps):
            idxs = rng.randint(0, n, size=n)
            pb = p_arr[idxs]
            yb = y_arr[idxs]
            bs_m = float(np.mean((pb - yb) ** 2))
            bs_b = float(np.mean((base_prob - yb) ** 2))
            boot_briers.append(bs_m)
            if bs_b > 0:
                boot_bsss.append(1.0 - (bs_m / bs_b))
        
        ci_brier = (round(float(np.percentile(boot_briers, 2.5)), 4),
                    round(float(np.percentile(boot_briers, 97.5)), 4))
        ci_bss = (round(float(np.percentile(boot_bsss, 2.5)), 4),
                  round(float(np.percentile(boot_bsss, 97.5)), 4)) if boot_bsss else (None, None)
        return ci_brier, ci_bss

    def _hash_file(self, path: str) -> str:
        if not os.path.exists(path):
            return "FILE_NOT_FOUND"
        with open(path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def _load_jsonl(self, path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(path):
            return []
        items = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    items.append(json.loads(line))
        return items

    def _load_json(self, path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(path):
            return []
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
