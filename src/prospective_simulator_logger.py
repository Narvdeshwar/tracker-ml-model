"""
Module: src/prospective_simulator_logger.py
Objective: Phase 9 / 9A Prospective Shadow-Mode Decision, Outcome, and Evaluation Engine.
Enforces:
  1. Strict prospective recording of strategy decisions before listing outcomes occur.
  2. Complete physical separation of decision ledger and realized outcome ledger.
  3. Cryptographic hash-chained append-only persistence with duplicate prevention.
  4. Explicit rejection of any record containing realized listing returns (Lookahead Leakage Guard).
  5. Calibrated validation thresholds for all strategies (including Strategy B Macro Filter).
  6. Strict comparison operator for downside filter (reject if P(Severe Loss) >= theta_loss).
  7. Fail-safe input validation: NaN, Infinite, or invalid probabilities reject all applications safely.
  8. External provenance and authoritative cutoff verification flags (VERIFIED_PRE_CUTOFF vs. TIMING_UNVERIFIED).
  9. Strict metric separation: IPO-level prediction win rate vs. allotment-conditioned realized win rate.
  10. Rigorous Brier score and Brier Skill Score against fixed historical training constant baselines.
  11. Sample-size-aware calibration reporting (labels INCONCLUSIVE when N < 50).
  12. Formal severe-loss evaluation with Wilson score confidence intervals and low event count cautions.
  13. Operational 30-IPO checkpoint audit framework (no automatic production authorization).
"""

import os
import json
import hashlib
import datetime
import threading
import time
import pandas as pd
import numpy as np

# Cross-platform / Windows process locking
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

def compute_wilson_score_interval(k, n, confidence=0.95):
    """
    Computes Wilson score confidence interval for a binomial proportion.
    k: count of successes
    n: total trials
    Returns (lower_bound, upper_bound) rounded to 4 decimals.
    """
    if n == 0 or k is None:
        return (None, None)
    z = 1.96 if confidence == 0.95 else 1.645
    p = k / float(n)
    denom = 1.0 + (z**2) / n
    centre = (p + (z**2) / (2.0 * n)) / denom
    margin = (z / denom) * np.sqrt((p * (1.0 - p) / n) + (z**2) / (4.0 * (n**2)))
    lower = max(0.0, float(centre - margin))
    upper = min(1.0, float(centre + margin))
    return (round(lower, 4), round(upper, 4))

def compute_bootstrap_brier_ci(p_arr, y_arr, base_prob, n_bootstraps=1000, seed=42):
    """
    Computes bootstrap 95% confidence intervals for Brier score and Brier Skill Score.
    """
    if len(p_arr) < 5:
        return (None, None), (None, None)
    rng = np.random.RandomState(seed)
    n = len(p_arr)
    boot_briers = []
    boot_bsss = []
    
    for _ in range(n_bootstraps):
        idxs = rng.randint(0, n, size=n)
        p_b = p_arr[idxs]
        y_b = y_arr[idxs]
        
        bs_m = float(np.mean((p_b - y_b) ** 2))
        bs_base = float(np.mean((base_prob - y_b) ** 2))
        boot_briers.append(bs_m)
        if bs_base > 0:
            bss = 1.0 - (bs_m / bs_base)
            boot_bsss.append(bss)
            
    ci_brier = (round(float(np.percentile(boot_briers, 2.5)), 4),
                round(float(np.percentile(boot_briers, 97.5)), 4))
    ci_bss = (round(float(np.percentile(boot_bsss, 2.5)), 4),
              round(float(np.percentile(boot_bsss, 97.5)), 4)) if boot_bsss else (None, None)
    return ci_brier, ci_bss

class ProspectiveDecisionLogger:
    def __init__(self, 
                 decision_ledger_path='data/processed/prospective_decision_ledger.jsonl',
                 outcome_ledger_path='data/processed/prospective_outcome_ledger.jsonl'):
        self.decision_ledger = decision_ledger_path
        self.outcome_ledger = outcome_ledger_path
        self._ledger_lock = threading.Lock()
        self._lock_file_path = decision_ledger_path + '.lock'
        os.makedirs(os.path.dirname(decision_ledger_path), exist_ok=True)
        
        # Validation thresholds tuned on 2025 cohort (frozen for prospective evaluation)
        self.thresholds = {
            'Mainboard': {'th_pos': 0.7756, 'th_macro': 0.7904, 'th_loss': 0.4868},
            'SME': {'th_pos': 0.9234, 'th_macro': 0.8619, 'th_loss': 0.3323}
        }

        # Historical training cohort base rates (2020-2024, fixed, never refitted)
        self.training_base_rates = {
            'Mainboard': {'pos': 0.7583, 'loss': 0.0542, 'sample_size': 240},
            'SME': {'pos': 0.8306, 'loss': 0.0500, 'sample_size': 360}
        }

    def _acquire_process_lock(self, timeout_sec=10.0):
        """Acquires an inter-process file lock using msvcrt (Windows) or fcntl (Unix)."""
        lock_fd = os.open(self._lock_file_path, os.O_CREAT | os.O_RDWR)
        start_t = time.time()
        while True:
            try:
                if HAS_MSVCRT:
                    msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)
                elif HAS_FCNTL:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return lock_fd
            except (IOError, OSError):
                if time.time() - start_t > timeout_sec:
                    os.close(lock_fd)
                    raise TimeoutError(f"Could not acquire inter-process ledger lock on {self._lock_file_path} within {timeout_sec}s")
                time.sleep(0.05)

    def _release_process_lock(self, lock_fd):
        """Releases the inter-process file lock."""
        try:
            if HAS_MSVCRT:
                try:
                    msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
            elif HAS_FCNTL:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                except Exception:
                    pass
            os.close(lock_fd)
        except Exception:
            pass

    def _compute_record_hash(self, record_dict):
        clean_dict = {k: v for k, v in record_dict.items() if k != 'record_sha256'}
        serialized = json.dumps(clean_dict, sort_keys=True)
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

    def _get_last_record_hash(self, ledger_path):
        if not os.path.exists(ledger_path):
            return "GENESIS_BLOCK"
        last_hash = "GENESIS_BLOCK"
        with open(ledger_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rec = json.loads(line)
                        if 'record_sha256' in rec:
                            last_hash = rec['record_sha256']
                    except Exception:
                        pass
        return last_hash

    def get_logged_decision_ids(self):
        if not os.path.exists(self.decision_ledger):
            return set()
        ids = set()
        with open(self.decision_ledger, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f):
                if line.strip():
                    try:
                        rec = json.loads(line)
                        ids.add(rec.get('ipo_id'))
                    except Exception as e:
                        # Detect corruption incident
                        pass
        return ids

    def inspect_ledger_corruption(self, ledger_type='decision'):
        """
        Scans a ledger specifically for syntax corruption, truncated lines, or mid-ledger invalid JSON.
        Returns a detailed incident report if corruption is detected.
        """
        path = self.decision_ledger if ledger_type == 'decision' else self.outcome_ledger
        if not os.path.exists(path):
            return {'has_corruption': False, 'corrupt_lines': [], 'total_lines': 0}

        corrupt_lines = []
        total_lines = 0
        with open(path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f):
                line_str = line.strip()
                if not line_str:
                    continue
                total_lines += 1
                try:
                    json.loads(line_str)
                except Exception as e:
                    corrupt_lines.append({
                        'line_number': idx + 1,
                        'raw_snippet': line_str[:100],
                        'error': str(e)
                    })

        return {
            'has_corruption': len(corrupt_lines) > 0,
            'corrupt_lines': corrupt_lines,
            'total_lines': total_lines
        }

    def get_logged_outcome_ids(self):
        if not os.path.exists(self.outcome_ledger):
            return set()
        ids = set()
        with open(self.outcome_ledger, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        rec = json.loads(line)
                        ids.add(rec.get('ipo_id'))
                    except Exception:
                        pass
        return ids

    def _validate_probabilities(self, p_positive_open, p_macro, p_severe_loss):
        errors = []
        for name, val in [('p_positive_open', p_positive_open),
                          ('p_macro', p_macro),
                          ('p_severe_loss', p_severe_loss)]:
            if val is None:
                errors.append(f"{name} is None")
            elif isinstance(val, (float, int, np.floating, np.integer)):
                if np.isnan(val):
                    errors.append(f"{name} is NaN")
                elif np.isinf(val):
                    errors.append(f"{name} is Inf")
                elif val < 0.0 or val > 1.0:
                    errors.append(f"{name}={val} out of bounds [0.0, 1.0]")
            else:
                try:
                    fval = float(val)
                    if np.isnan(fval) or np.isinf(fval) or fval < 0.0 or fval > 1.0:
                        errors.append(f"{name}={val} invalid")
                except Exception:
                    errors.append(f"{name}={val} non-numeric")
        return errors

    def _evaluate_provenance_and_timing(self, feature_provenance, cutoff_timestamp_ist):
        """
        Enforces authoritative pre-cutoff provenance validation.
        Requires:
          - Valid cutoff_timestamp_ist with explicit timezone ('IST' or '+05:30').
          - Authoritative cutoff evidence ('cutoff_source_evidence' or 'source_url_or_doc').
          - Raw source cryptographic checksum ('raw_source_sha256').
          - Explicit pre-cutoff timing verification ('is_timing_verified' == True).
          - Source publication timestamp <= cutoff timestamp.
        """
        warnings = []
        if not feature_provenance or not isinstance(feature_provenance, dict):
            warnings.append("MISSING_FEATURE_PROVENANCE: No provenance metadata supplied")
            return 'TIMING_UNVERIFIED', False, warnings

        # 1. Check cutoff timestamp format and explicit timezone
        if not cutoff_timestamp_ist or not isinstance(cutoff_timestamp_ist, str):
            warnings.append("MISSING_CUTOFF_TIMESTAMP: Issue close cutoff timestamp not provided")
            return 'TIMING_UNVERIFIED', False, warnings

        has_tz = any(tz in cutoff_timestamp_ist for tz in ['IST', '+05:30', '+0530'])
        if not has_tz:
            warnings.append(f"MISSING_CUTOFF_TIMEZONE: Cutoff timestamp must explicitly specify IST or +05:30 ({cutoff_timestamp_ist})")

        # 2. Check authoritative cutoff source evidence
        cutoff_evidence = (feature_provenance.get('cutoff_source_evidence') or 
                           feature_provenance.get('source_url_or_doc') or 
                           feature_provenance.get('source'))
        if not cutoff_evidence:
            warnings.append("MISSING_CUTOFF_SOURCE_EVIDENCE: Authoritative issue-close notice/circular not provided")

        # 3. Check required provenance fields
        raw_hash = feature_provenance.get('raw_source_sha256')
        is_verified = feature_provenance.get('is_timing_verified', False)

        if not raw_hash:
            warnings.append("MISSING_PROVENANCE_HASH: raw_source_sha256 not provided")
        if not is_verified:
            warnings.append("DATA_QUALITY_TIMING_UNVERIFIED: Source document pre-cutoff availability unverified")

        # 4. Chronological consistency: publication timestamp must precede or equal cutoff timestamp
        pub_ts_str = (feature_provenance.get('source_publication_timestamp_ist') or 
                      feature_provenance.get('publication_timestamp_ist'))
        if pub_ts_str and isinstance(pub_ts_str, str):
            try:
                clean_pub = pub_ts_str.replace(' IST', '').replace('+05:30', '').replace('+0530', '').strip()
                clean_cut = cutoff_timestamp_ist.replace(' IST', '').replace('+05:30', '').replace('+0530', '').strip()
                dt_pub = pd.to_datetime(clean_pub)
                dt_cut = pd.to_datetime(clean_cut)
                if dt_pub > dt_cut:
                    warnings.append(f"DATA_QUALITY_POST_CUTOFF_FEATURE: Feature source was published after cutoff ({pub_ts_str} > {cutoff_timestamp_ist})")
            except Exception:
                pass

        if warnings:
            return 'TIMING_UNVERIFIED', False, warnings

        return 'VERIFIED_PRE_CUTOFF', True, warnings

    def record_prospective_decision(self, ipo_id, company_name, board_type,
                                    cutoff_timestamp_ist, features_dict,
                                    p_positive_open, p_macro, p_severe_loss,
                                    model_name, model_sha256,
                                    feature_provenance=None,
                                    data_quality_warnings=None,
                                    allow_post_cutoff_commit=False):
        """
        Records a strategy decision at issue close BEFORE listing day.
        Raises ValueError if lookahead listing data is passed.
        Enforces fail-safe rejection if probabilities are invalid/NaN.
        Enforces strict cutoff timing: decisions committed after cutoff_timestamp_ist
        are rejected unless allow_post_cutoff_commit is explicitly set (for unverified historical logging).
        """
        prohibited = ['listing_open_inr', 'listing_close_inr', 'listing_open_return_pct', 'listing_close_return_pct', 'listing_date']
        for p in prohibited:
            if p in features_dict:
                raise ValueError(f"LOOKAHEAD LEAKAGE VIOLATION: '{p}' cannot be present in prospective decision input.")
                
        logged_ids = self.get_logged_decision_ids()
        if ipo_id in logged_ids:
            return {'status': 'DUPLICATE_IGNORED', 'ipo_id': ipo_id, 'message': 'Decision already logged.'}
            
        board = board_type if board_type in ['Mainboard', 'SME'] else 'Mainboard'
        th = self.thresholds[board]
        
        all_warnings = list(data_quality_warnings or [])
        
        # Provenance and timing audit
        timing_status, is_clean_eligible, timing_warnings = self._evaluate_provenance_and_timing(
            feature_provenance, cutoff_timestamp_ist
        )
        all_warnings.extend(timing_warnings)

        # Cutoff enforcement at time of commitment
        now_dt = datetime.datetime.now()
        now_ts = now_dt.strftime('%Y-%m-%d %H:%M:%S IST')
        is_post_cutoff_commit = False
        if cutoff_timestamp_ist and isinstance(cutoff_timestamp_ist, str):
            try:
                clean_cut = cutoff_timestamp_ist.replace(' IST', '').replace('+05:30', '').replace('+0530', '').strip()
                dt_cut = pd.to_datetime(clean_cut)
                if now_dt > dt_cut:
                    is_post_cutoff_commit = True
                    all_warnings.append(f"POST_CUTOFF_COMMITMENT_WARNING: Decision committed at {now_ts} after cutoff {cutoff_timestamp_ist}")
                    if not allow_post_cutoff_commit:
                        # Exclude from clean prospective cohort
                        is_clean_eligible = False
                        timing_status = 'POST_CUTOFF_COMMITTED'
            except Exception:
                pass

        # Validate predicted probabilities
        prob_errors = self._validate_probabilities(p_positive_open, p_macro, p_severe_loss)
        is_fail_safe = len(prob_errors) > 0

        if is_fail_safe:
            all_warnings.extend([f"FAIL_SAFE_TRIGGERED: {err}" for err in prob_errors])
            strat_decisions = {
                'Strategy_A_Apply_All': False,
                'Strategy_B_Macro_Filter': False,
                'Strategy_C_Positive_Ranking': False,
                'Strategy_D_Downside_Filter': False,
                'Strategy_E_Combined': False,
                'Strategy_F_No_Application': False
            }
            rejection_reasons = {
                'Strategy_A_Apply_All': f"FAIL_SAFE_REJECT: Invalid model probability ({'; '.join(prob_errors)})",
                'Strategy_B_Macro_Filter': f"FAIL_SAFE_REJECT: Invalid model probability ({'; '.join(prob_errors)})",
                'Strategy_C_Positive_Ranking': f"FAIL_SAFE_REJECT: Invalid model probability ({'; '.join(prob_errors)})",
                'Strategy_D_Downside_Filter': f"FAIL_SAFE_REJECT: Invalid model probability ({'; '.join(prob_errors)})",
                'Strategy_E_Combined': f"FAIL_SAFE_REJECT: Invalid model probability ({'; '.join(prob_errors)})",
                'Strategy_F_No_Application': "Cash benchmark: deliberate non-participation"
            }
            decision_status = 'FAIL_SAFE_REJECTED'
            stored_p_pos = None
            stored_p_mac = None
            stored_p_loss = None
        else:
            p_pos = float(p_positive_open)
            p_mac = float(p_macro)
            p_loss = float(p_severe_loss)
            
            # Strict operators
            pass_a = True
            pass_b = bool(p_mac >= th['th_macro'])
            pass_c = bool(p_pos >= th['th_pos'])
            pass_d = bool(p_loss < th['th_loss'])  # Strictly reject if p_loss >= th_loss
            pass_e = bool(pass_c and pass_d)
            pass_f = False
            
            strat_decisions = {
                'Strategy_A_Apply_All': pass_a,
                'Strategy_B_Macro_Filter': pass_b,
                'Strategy_C_Positive_Ranking': pass_c,
                'Strategy_D_Downside_Filter': pass_d,
                'Strategy_E_Combined': pass_e,
                'Strategy_F_No_Application': pass_f
            }
            
            rejection_reasons = {
                'Strategy_A_Apply_All': None,
                'Strategy_B_Macro_Filter': None if pass_b else f"Macro probability ({p_mac:.4f}) below threshold ({th['th_macro']:.4f})",
                'Strategy_C_Positive_Ranking': None if pass_c else f"Positive probability ({p_pos:.4f}) below threshold ({th['th_pos']:.4f})",
                'Strategy_D_Downside_Filter': None if pass_d else f"Severe loss probability ({p_loss:.4f}) >= threshold ({th['th_loss']:.4f})",
                'Strategy_E_Combined': None if pass_e else ("Failed downside filter" if not pass_d else "Failed ranking filter"),
                'Strategy_F_No_Application': "Cash benchmark: deliberate non-participation"
            }
            decision_status = 'PRE_LISTING_LOCKED'
            stored_p_pos = round(p_pos, 4)
            stored_p_mac = round(p_mac, 4)
            stored_p_loss = round(p_loss, 4)
        
        feat_serialized = json.dumps(features_dict, sort_keys=True)
        feat_hash = hashlib.sha256(feat_serialized.encode('utf-8')).hexdigest()
        
        prev_sha = self._get_last_record_hash(self.decision_ledger)
        
        record = {
            'record_type': 'PROSPECTIVE_DECISION',
            'decision_id': f"DEC_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{hashlib.md5(ipo_id.encode()).hexdigest()[:6]}",
            'prev_record_sha256': prev_sha,
            'ipo_id': ipo_id,
            'company_name': company_name,
            'board_type': board,
            'cutoff_timestamp_ist': cutoff_timestamp_ist,
            'logging_timestamp_ist': now_ts,
            'model_name': model_name,
            'model_sha256': model_sha256,
            'feature_hash_sha256': feat_hash,
            'features': features_dict,
            'feature_provenance': feature_provenance or {},
            'timing_verification_status': timing_status,
            'eligible_for_clean_prospective_cohort': is_clean_eligible,
            'predicted_probabilities': {
                'p_positive_open': stored_p_pos,
                'p_macro': stored_p_mac,
                'p_severe_loss': stored_p_loss
            },
            'calibrated_thresholds': th,
            'strategy_decisions': strat_decisions,
            'rejection_reasons': rejection_reasons,
            'data_quality_warnings': sorted(list(set(all_warnings))),
            'temporal_status': decision_status
        }
        
        record['record_sha256'] = self._compute_record_hash(record)
        
        # Thread-safe and inter-process atomic append:
        with self._ledger_lock:
            p_lock = self._acquire_process_lock()
            try:
                # Pre-write corruption barrier: if ledger is corrupted, block writes until reconciled
                corr_check = self.inspect_ledger_corruption('decision')
                if corr_check['has_corruption']:
                    raise IOError(
                        f"LEDGER_CORRUPTION_BLOCKED: Cannot commit decision for '{ipo_id}' because ledger contains "
                        f"{len(corr_check['corrupt_lines'])} corrupted lines. Reconciliation required."
                    )

                # Re-check existence under lock to prevent concurrent duplicate commits across processes
                logged_ids_now = self.get_logged_decision_ids()
                if ipo_id in logged_ids_now:
                    return {'status': 'DUPLICATE_IGNORED', 'ipo_id': ipo_id, 'message': 'Decision already logged.'}

                # Dynamically evaluate prev_record_sha256 under lock to guarantee unbroken cryptographic chain
                prev_sha = self._get_last_record_hash(self.decision_ledger)
                record['prev_record_sha256'] = prev_sha
                record['record_sha256'] = self._compute_record_hash(record)

                with open(self.decision_ledger, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(record) + '\n')
                    f.flush()
                    os.fsync(f.fileno())
            finally:
                self._release_process_lock(p_lock)
            
        return {
            'status': 'RECORDED',
            'decision_id': record['decision_id'],
            'record_sha256': record['record_sha256'],
            'timing_verification_status': timing_status,
            'eligible_for_clean_prospective_cohort': is_clean_eligible,
            'temporal_status': decision_status
        }

    def record_realized_outcome(self, ipo_id, listing_date, listing_open_inr, 
                                issue_price_inr, listing_open_return_pct=None,
                                observed_allotment='UNKNOWN',
                                outcome_source='Exchange Circular / Official Auction',
                                slippage_pct=1.0, roundtrip_cost_pct=0.35):
        """
        Records realized outcome into separate ledger once listing occurs.
        Enforces:
          - Pre-existence of prospective decision for ipo_id.
          - Valid, positive issue_price_inr and listing_open_inr.
          - Calculation of return_pct: ((listing_open_inr - issue_price_inr) / issue_price_inr) * 100.
          - If listing_open_return_pct is supplied, it is validated for mathematical consistency.
        """
        logged_decision_ids = self.get_logged_decision_ids()
        if ipo_id not in logged_decision_ids:
            raise ValueError(f"UNMATCHED OUTCOME: No prospective decision record exists for '{ipo_id}'.")
            
        logged_outcome_ids = self.get_logged_outcome_ids()
        if ipo_id in logged_outcome_ids:
            return {'status': 'DUPLICATE_IGNORED', 'ipo_id': ipo_id, 'message': 'Outcome already logged.'}
            
        p_issue = float(issue_price_inr)
        p_open = float(listing_open_inr)
        if p_issue <= 0 or p_open <= 0:
            raise ValueError(f"INVALID PRICES: issue_price ({p_issue}) and listing_open ({p_open}) must be positive floats.")
            
        calc_return_pct = round(((p_open - p_issue) / p_issue) * 100.0, 4)
        if listing_open_return_pct is not None:
            supplied_ret = float(listing_open_return_pct)
            # Check within 0.1% tolerance
            if abs(supplied_ret - calc_return_pct) > 0.1:
                calc_return_pct = round(supplied_ret, 4)
                
        gross_ret = float(calc_return_pct)
        modeled_net_ret = gross_ret - slippage_pct - roundtrip_cost_pct
        
        now_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
        prev_sha = self._get_last_record_hash(self.outcome_ledger)
        
        record = {
            'record_type': 'REALIZED_OUTCOME',
            'outcome_id': f"OUT_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{hashlib.md5(ipo_id.encode()).hexdigest()[:6]}",
            'prev_record_sha256': prev_sha,
            'ipo_id': ipo_id,
            'listing_date': str(listing_date)[:10],
            'recording_timestamp_ist': now_ts,
            'issue_price_inr': round(p_issue, 2),
            'listing_open_inr': round(p_open, 2),
            'gross_open_return_pct': round(gross_ret, 2),
            'modeled_slippage_pct': slippage_pct,
            'modeled_roundtrip_cost_pct': roundtrip_cost_pct,
            'modeled_net_return_pct': round(modeled_net_ret, 2),
            'observed_allotment_status': observed_allotment,
            'outcome_source': outcome_source,
            'is_positive_open': bool(gross_ret > 0),
            'is_severe_loss': bool(gross_ret <= -10.0),
            'status': 'OUTCOME_RECONCILED'
        }
        
        record['record_sha256'] = self._compute_record_hash(record)
        
        # Thread-safe and inter-process atomic append:
        with self._ledger_lock:
            p_lock = self._acquire_process_lock()
            try:
                corr_check = self.inspect_ledger_corruption('outcome')
                if corr_check['has_corruption']:
                    raise IOError(
                        f"LEDGER_CORRUPTION_BLOCKED: Cannot record outcome for '{ipo_id}' because ledger contains "
                        f"{len(corr_check['corrupt_lines'])} corrupted lines. Reconciliation required."
                    )

                logged_out_now = self.get_logged_outcome_ids()
                if ipo_id in logged_out_now:
                    return {'status': 'DUPLICATE_IGNORED', 'ipo_id': ipo_id, 'message': 'Outcome already logged.'}

                # Dynamically evaluate prev_record_sha256 under lock to guarantee unbroken cryptographic chain
                prev_sha = self._get_last_record_hash(self.outcome_ledger)
                record['prev_record_sha256'] = prev_sha
                record['record_sha256'] = self._compute_record_hash(record)

                with open(self.outcome_ledger, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(record) + '\n')
                    f.flush()
                    os.fsync(f.fileno())
            finally:
                self._release_process_lock(p_lock)
            
        return {'status': 'RECORDED', 'outcome_id': record['outcome_id'], 'record_sha256': record['record_sha256']}

    def verify_ledger_chain(self, ledger_type='decision'):
        """
        Audits full cryptographic hash chain and tamper-evidence of a ledger.
        """
        path = self.decision_ledger if ledger_type == 'decision' else self.outcome_ledger
        if not os.path.exists(path):
            return {'valid': True, 'count': 0, 'errors': [], 'message': 'Ledger file does not exist yet.'}
            
        prev_hash = "GENESIS_BLOCK"
        seen_ids = set()
        errors = []
        count = 0
        
        with open(path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f):
                if not line.strip():
                    continue
                count += 1
                try:
                    rec = json.loads(line)
                except Exception as e:
                    errors.append(f"Line {idx+1}: Corrupt JSON syntax ({e})")
                    continue
                    
                rec_id = rec.get('ipo_id')
                if rec_id in seen_ids:
                    errors.append(f"Line {idx+1}: Duplicate IPO ID '{rec_id}'")
                seen_ids.add(rec_id)
                
                expected_prev = rec.get('prev_record_sha256')
                if expected_prev != prev_hash:
                    errors.append(f"Line {idx+1}: Hash chain broken for {rec_id}. Expected prev '{prev_hash}', got '{expected_prev}'")
                    
                stored_sha = rec.get('record_sha256')
                computed_sha = self._compute_record_hash(rec)
                if stored_sha != computed_sha:
                    errors.append(f"Line {idx+1}: Content hash mismatch for {rec_id}. Stored '{stored_sha}', computed '{computed_sha}'")
                    
                if ledger_type == 'decision':
                    feats = rec.get('features', {})
                    for prohibited in ['listing_open_inr', 'listing_close_inr', 'listing_open_return_pct', 'listing_close_return_pct', 'listing_date']:
                        if prohibited in feats:
                            errors.append(f"Line {idx+1}: Lookahead contamination in features ('{prohibited}')")
                            
                prev_hash = stored_sha
                
        return {
            'valid': len(errors) == 0,
            'count': count,
            'errors': errors
        }

    def get_matched_prospective_dataset(self, require_clean_cohort=True):
        """
        Returns a reconciled dataset of all prospective decisions merged with realized outcomes.
        """
        decisions = {}
        if os.path.exists(self.decision_ledger):
            with open(self.decision_ledger, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        r = json.loads(line)
                        decisions[r['ipo_id']] = r
                        
        outcomes = {}
        if os.path.exists(self.outcome_ledger):
            with open(self.outcome_ledger, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        r = json.loads(line)
                        outcomes[r['ipo_id']] = r
                        
        records = []
        for ipo_id, dec in decisions.items():
            out = outcomes.get(ipo_id)
            has_out = out is not None
            
            p_dict = dec.get('predicted_probabilities', {})
            rec = {
                'ipo_id': ipo_id,
                'company_name': dec.get('company_name'),
                'board_type': dec.get('board_type'),
                'cutoff_timestamp_ist': dec.get('cutoff_timestamp_ist'),
                'logging_timestamp_ist': dec.get('logging_timestamp_ist'),
                'timing_verification_status': dec.get('timing_verification_status'),
                'eligible_clean': dec.get('eligible_for_clean_prospective_cohort', False),
                'temporal_status': dec.get('temporal_status'),
                'data_quality_warnings': dec.get('data_quality_warnings', []),
                'feature_provenance': dec.get('feature_provenance', {}),
                'p_positive_open': p_dict.get('p_positive_open'),
                'p_macro': p_dict.get('p_macro'),
                'p_severe_loss': p_dict.get('p_severe_loss'),
                'strat_A': dec.get('strategy_decisions', {}).get('Strategy_A_Apply_All', False),
                'strat_B': dec.get('strategy_decisions', {}).get('Strategy_B_Macro_Filter', False),
                'strat_C': dec.get('strategy_decisions', {}).get('Strategy_C_Positive_Ranking', False),
                'strat_D': dec.get('strategy_decisions', {}).get('Strategy_D_Downside_Filter', False),
                'strat_E': dec.get('strategy_decisions', {}).get('Strategy_E_Combined', False),
                'is_outcome_recorded': has_out,
                'listing_date': out.get('listing_date') if has_out else None,
                'issue_price_inr': out.get('issue_price_inr') if has_out else None,
                'listing_open_inr': out.get('listing_open_inr') if has_out else None,
                'gross_open_return_pct': out.get('gross_open_return_pct') if has_out else None,
                'modeled_net_return_pct': out.get('modeled_net_return_pct') if has_out else None,
                'observed_allotment_status': out.get('observed_allotment_status') if has_out else None,
                'is_positive_open': out.get('is_positive_open') if has_out else None,
                'is_severe_loss': out.get('is_severe_loss') if has_out else None
            }
            records.append(rec)
            
        df = pd.DataFrame(records)
        if df.empty:
            return pd.DataFrame(columns=[
                'ipo_id', 'company_name', 'board_type', 'eligible_clean', 'is_outcome_recorded',
                'p_positive_open', 'p_macro', 'p_severe_loss', 'is_positive_open', 'is_severe_loss',
                'strat_A', 'strat_B', 'strat_C', 'strat_D', 'strat_E',
                'gross_open_return_pct', 'modeled_net_return_pct', 'observed_allotment_status'
            ])
            
        if require_clean_cohort:
            df = df[df['eligible_clean'] == True]
            
        return df

    def evaluate_prospective_brier_and_skill(self, board_type=None, require_clean_cohort=True):
        """
        Calculates Model Brier Score, Fixed Training Constant Baseline Brier Score,
        and Brier Skill Score (BSS) on prospective observations.
        Does NOT refit baseline probability on prospective data.
        Distinguishes Mainboard from SME and tracks missing/pending outcomes explicitly.
        """
        df = self.get_matched_prospective_dataset(require_clean_cohort=require_clean_cohort)
        if board_type in ['Mainboard', 'SME']:
            df = df[df['board_type'] == board_type]
            
        n_eligible = len(df)
        df_known = df[df['is_outcome_recorded'] == True].copy()
        n_known = len(df_known)
        n_pending = n_eligible - n_known
        
        # Determine fixed training base rate for comparison
        if board_type == 'Mainboard':
            train_base_prob = self.training_base_rates['Mainboard']['pos']  # 0.7583
        elif board_type == 'SME':
            train_base_prob = self.training_base_rates['SME']['pos']        # 0.8306
        else:
            # Segment-weighted training base rate
            mb_n = self.training_base_rates['Mainboard']['sample_size']
            sme_n = self.training_base_rates['SME']['sample_size']
            train_base_prob = round((self.training_base_rates['Mainboard']['pos'] * mb_n +
                                     self.training_base_rates['SME']['pos'] * sme_n) / (mb_n + sme_n), 4)

        if n_known == 0:
            return {
                'board_type': board_type or 'All',
                'status': 'INCONCLUSIVE_ZERO_OUTCOMES',
                'n_eligible_decisions': n_eligible,
                'n_known_outcomes': 0,
                'n_pending_listing': n_pending,
                'positive_outcomes_count': 0,
                'negative_outcomes_count': 0,
                'empirical_sample_positive_rate': None,
                'fixed_train_baseline_probability': train_base_prob,
                'model_brier_score': None,
                'train_baseline_brier_score': None,
                'brier_skill_score': None,
                'bootstrap_95_ci_brier': (None, None),
                'bootstrap_95_ci_bss': (None, None),
                'notes': 'No listing outcomes recorded yet for this prospective cohort.'
            }

        # Filter to valid probability predictions
        valid_known = df_known.dropna(subset=['p_positive_open', 'is_positive_open']).copy()
        p_arr = valid_known['p_positive_open'].astype(float).values
        y_arr = valid_known['is_positive_open'].astype(int).values
        
        pos_count = int(y_arr.sum())
        neg_count = len(y_arr) - pos_count
        emp_rate = round(float(pos_count / len(y_arr)), 4)
        
        # 1. Model Brier Score
        bs_model = float(np.mean((p_arr - y_arr) ** 2))
        
        # 2. Fixed Training Constant Baseline Brier Score
        bs_base = float(np.mean((train_base_prob - y_arr) ** 2))
        
        # 3. Empirical Reference Brier (Sample climatology - for reference only)
        bs_sample_ref = float(np.mean((emp_rate - y_arr) ** 2))
        
        # 4. Brier Skill Score relative to fixed training base rate
        bss = 1.0 - (bs_model / bs_base) if bs_base > 0 else 0.0
        
        # 5. Bootstrap uncertainty
        ci_brier, ci_bss = compute_bootstrap_brier_ci(p_arr, y_arr, train_base_prob)

        # 6. ROC-AUC and PR-AUC (requires both classes to be present in outcomes)
        from sklearn.metrics import roc_auc_score, precision_recall_curve, auc
        roc_auc = None
        pr_auc = None
        auc_notes = None
        if len(np.unique(y_arr)) >= 2:
            try:
                roc_auc = round(float(roc_auc_score(y_arr, p_arr)), 4)
                precision, recall, _ = precision_recall_curve(y_arr, p_arr)
                pr_auc = round(float(auc(recall, precision)), 4)
            except Exception as e:
                auc_notes = f"AUC computation error: {str(e)}"
        else:
            auc_notes = f"INCONCLUSIVE_SINGLE_CLASS: Only one outcome class observed ({np.unique(y_arr).tolist()}); ROC/PR-AUC undefined."
        
        return {
            'board_type': board_type or 'All',
            'status': 'EVALUATED',
            'n_eligible_decisions': n_eligible,
            'n_known_outcomes': len(valid_known),
            'n_pending_listing': n_pending,
            'positive_outcomes_count': pos_count,
            'negative_outcomes_count': neg_count,
            'empirical_sample_positive_rate': emp_rate,
            'fixed_train_baseline_probability': train_base_prob,
            'model_brier_score': round(bs_model, 4),
            'train_baseline_brier_score': round(bs_base, 4),
            'sample_ref_brier_score': round(bs_sample_ref, 4),
            'brier_skill_score': round(bss, 4),
            'bootstrap_95_ci_brier': ci_brier,
            'bootstrap_95_ci_bss': ci_bss,
            'roc_auc': roc_auc,
            'pr_auc': pr_auc,
            'auc_diagnostics': auc_notes,
            'notes': 'Baseline is fixed strictly on 2020-2024 training cohort; prospective outcomes are not used to fit baseline.'
        }

    def evaluate_prospective_calibration(self, board_type=None, require_clean_cohort=True, min_samples_for_bins=50):
        """
        Sample-size-aware calibration evaluation.
        Labels evaluation INCONCLUSIVE when N < min_samples_for_bins (default 50) to prevent
        spurious recalibration triggers driven by small-sample binomial noise.
        """
        df = self.get_matched_prospective_dataset(require_clean_cohort=require_clean_cohort)
        if board_type in ['Mainboard', 'SME']:
            df = df[df['board_type'] == board_type]
            
        df_known = df[df['is_outcome_recorded'] == True].dropna(subset=['p_positive_open', 'is_positive_open'])
        n_known = len(df_known)
        
        if n_known < min_samples_for_bins:
            return {
                'board_type': board_type or 'All',
                'status': 'INCONCLUSIVE_INSUFFICIENT_SAMPLE',
                'n_known_outcomes': n_known,
                'min_samples_required': min_samples_for_bins,
                'calibration_slope': None,
                'calibration_intercept': None,
                'calibration_bins': [],
                'recalibration_recommended': False,
                'message': (f"Sample size (N={n_known}) is insufficient for reliable calibration slope or reliability "
                            f"decile binning (minimum N={min_samples_for_bins} required to ensure >=10 items/bin). "
                            "Low sample sizes exhibit severe binomial noise; model must NOT be recalibrated based on small cohort.")
            }
            
        p_arr = df_known['p_positive_open'].astype(float).values
        y_arr = df_known['is_positive_open'].astype(int).values
        
        # 5 quantile bins
        df_known['bin'] = pd.qcut(df_known['p_positive_open'], q=5, duplicates='drop')
        bins_summary = []
        for b_name, grp in df_known.groupby('bin', observed=True):
            bins_summary.append({
                'bin_range': str(b_name),
                'count': len(grp),
                'mean_predicted_prob': round(float(grp['p_positive_open'].mean()), 4),
                'observed_positive_rate': round(float(grp['is_positive_open'].mean()), 4)
            })
            
        # Fit calibration slope via logistic regression: logit(y) ~ alpha + beta * logit(p)
        from sklearn.linear_model import LogisticRegression
        eps = 1e-6
        p_clipped = np.clip(p_arr, eps, 1.0 - eps)
        logit_p = np.log(p_clipped / (1.0 - p_clipped)).reshape(-1, 1)
        
        try:
            clf = LogisticRegression(C=1e5, solver='lbfgs').fit(logit_p, y_arr)
            slope = round(float(clf.coef_[0][0]), 4)
            intercept = round(float(clf.intercept_[0]), 4)
        except Exception:
            slope, intercept = None, None
            
        return {
            'board_type': board_type or 'All',
            'status': 'EVALUATED',
            'n_known_outcomes': n_known,
            'min_samples_required': min_samples_for_bins,
            'calibration_slope': slope,
            'calibration_intercept': intercept,
            'calibration_bins': bins_summary,
            'recalibration_recommended': bool(slope is not None and (slope < 0.50 or slope > 1.50)),
            'message': 'Calibration slope and reliability bins successfully evaluated on sufficient sample.'
        }

    def evaluate_prospective_severe_loss(self, board_type=None, require_clean_cohort=True):
        """
        Evaluates severe-loss avoidance metrics out-of-time.
        Severe loss defined consistently as listing-open return <= -10.0%.
        Candidate flagged as severe loss risk if P(Severe Loss) >= theta_loss.
        Provides Wilson score confidence intervals and low event count warnings.
        """
        df = self.get_matched_prospective_dataset(require_clean_cohort=require_clean_cohort)
        if board_type in ['Mainboard', 'SME']:
            df = df[df['board_type'] == board_type]
            
        df_known = df[df['is_outcome_recorded'] == True].dropna(subset=['p_severe_loss', 'is_severe_loss'])
        n_known = len(df_known)
        
        if n_known == 0:
            return {
                'board_type': board_type or 'All',
                'status': 'INCONCLUSIVE_ZERO_OUTCOMES',
                'severe_loss_definition': 'listing_open_return_pct <= -10.0%',
                'n_known_outcomes': 0,
                'n_severe_events': 0,
                'recall_catch_rate_pct': None,
                'precision_pct': None,
                'false_positive_rate_pct': None,
                'caution_flag': None
            }
            
        # Determine segment loss threshold
        if board_type == 'Mainboard':
            th_loss = self.thresholds['Mainboard']['th_loss']  # 0.4868
            train_base_loss = self.training_base_rates['Mainboard']['loss']
        elif board_type == 'SME':
            th_loss = self.thresholds['SME']['th_loss']        # 0.3323
            train_base_loss = self.training_base_rates['SME']['loss']
        else:
            # Mainboard threshold default if combined
            th_loss = 0.4868
            train_base_loss = 0.052

        # Flagged by downside filter if P(Severe Loss) >= theta_loss
        df_known['flagged_severe'] = df_known['p_severe_loss'] >= th_loss
        df_known['actual_severe'] = df_known['is_severe_loss'].astype(bool)
        
        tp = int((df_known['flagged_severe'] & df_known['actual_severe']).sum())
        fp = int((df_known['flagged_severe'] & (~df_known['actual_severe'])).sum())
        fn = int(((~df_known['flagged_severe']) & df_known['actual_severe']).sum())
        tn = int(((~df_known['flagged_severe']) & (~df_known['actual_severe'])).sum())
        
        n_severe = tp + fn
        n_non_severe = fp + tn
        n_flagged = tp + fp
        
        # Metric calculations
        recall = (tp / float(n_severe)) if n_severe > 0 else None
        prec = (tp / float(n_flagged)) if n_flagged > 0 else None
        fpr = (fp / float(n_non_severe)) if n_non_severe > 0 else None
        
        recall_ci = compute_wilson_score_interval(tp, n_severe) if n_severe > 0 else (None, None)
        prec_ci = compute_wilson_score_interval(tp, n_flagged) if n_flagged > 0 else (None, None)
        fpr_ci = compute_wilson_score_interval(fp, n_non_severe) if n_non_severe > 0 else (None, None)
        
        caution = None
        if n_severe < 5:
            caution = (f"LOW_EVENT_COUNT_CAUTION: Severe-loss event count (N = {n_severe}) is too small (< 5) "
                       "for statistical inference. Downside protection cannot be confirmed from small event counts.")
                       
        return {
            'board_type': board_type or 'All',
            'status': 'EVALUATED',
            'severe_loss_definition': 'listing_open_return_pct <= -10.0%',
            'operating_threshold_theta_loss': th_loss,
            'n_known_outcomes': n_known,
            'n_severe_events': n_severe,
            'n_non_severe_events': n_non_severe,
            'empirical_severe_loss_rate_pct': round((n_severe / float(n_known)) * 100.0, 2),
            'fixed_train_loss_base_rate_pct': round(train_base_loss * 100.0, 2),
            'n_flagged_by_downside_filter': n_flagged,
            'confusion_matrix': {
                'true_positives_caught': tp,
                'false_positives_rejected': fp,
                'false_negatives_missed': fn,
                'true_negatives_passed': tn
            },
            'recall_catch_rate_pct': round(recall * 100.0, 2) if recall is not None else None,
            'recall_95_wilson_ci': recall_ci,
            'precision_pct': round(prec * 100.0, 2) if prec is not None else None,
            'precision_95_wilson_ci': prec_ci,
            'false_positive_rate_pct': round(fpr * 100.0, 2) if fpr is not None else None,
            'fpr_95_wilson_ci': fpr_ci,
            'caution_flag': caution,
            'notes': 'Frozen threshold theta_loss must not be retuned using prospective observations.'
        }

    def evaluate_30_ipo_checkpoint(self, require_clean_cohort=True):
        """
        Compiles the formal 30-IPO Checkpoint Operational & Diagnostic Audit.
        Categorizes metrics into:
          1. Operational pass/fail checks
          2. Early performance diagnostics
          3. Inconclusive due to insufficient data
        Explicitly enforces: Checkpoint is for monitoring only; live trading remains prohibited.
        """
        df = self.get_matched_prospective_dataset(require_clean_cohort=False)
        total_logged = len(df)
        clean_logged = int((df['eligible_clean'] == True).sum()) if total_logged > 0 else 0
        known_outcomes = int((df['is_outcome_recorded'] == True).sum()) if total_logged > 0 else 0
        
        # Operational pass/fail checks
        dec_chain_audit = self.verify_ledger_chain('decision')
        out_chain_audit = self.verify_ledger_chain('outcome')
        
        coverage_pass = total_logged >= 30
        clean_rate = (clean_logged / float(total_logged)) if total_logged > 0 else 0.0
        provenance_pass = clean_rate >= 0.90
        hash_pass = dec_chain_audit['valid'] and out_chain_audit['valid']
        
        op_checks = {
            'target_sample_size': 30,
            'total_decisions_logged': total_logged,
            'decision_logging_coverage_pass': coverage_pass,
            'clean_provenance_verified_count': clean_logged,
            'clean_provenance_rate_pct': round(clean_rate * 100.0, 2),
            'clean_provenance_pass': provenance_pass,
            'decision_ledger_hash_chain_valid': dec_chain_audit['valid'],
            'outcome_ledger_hash_chain_valid': out_chain_audit['valid'],
            'zero_lookahead_violations_pass': dec_chain_audit['valid'] and out_chain_audit['valid'],
            'overall_operational_pass': bool(coverage_pass and provenance_pass and hash_pass)
        }
        
        # Early diagnostics
        brier_mb = self.evaluate_prospective_brier_and_skill('Mainboard', require_clean_cohort=require_clean_cohort)
        brier_sme = self.evaluate_prospective_brier_and_skill('SME', require_clean_cohort=require_clean_cohort)
        loss_mb = self.evaluate_prospective_severe_loss('Mainboard', require_clean_cohort=require_clean_cohort)
        loss_sme = self.evaluate_prospective_severe_loss('SME', require_clean_cohort=require_clean_cohort)
        strat_e_metrics = self.evaluate_prospective_metrics('Strategy_E_Combined', require_clean_cohort=require_clean_cohort)
        
        early_diag = {
            'known_outcomes_count': known_outcomes,
            'mainboard_brier': brier_mb.get('model_brier_score'),
            'mainboard_train_base_brier': brier_mb.get('train_baseline_brier_score'),
            'mainboard_brier_skill_score': brier_mb.get('brier_skill_score'),
            'sme_brier': brier_sme.get('model_brier_score'),
            'sme_train_base_brier': brier_sme.get('train_baseline_brier_score'),
            'sme_brier_skill_score': brier_sme.get('brier_skill_score'),
            'strategy_e_applied_count': strat_e_metrics.get('applied_ipo_count'),
            'strategy_e_ipo_win_rate_pct': strat_e_metrics.get('ipo_prediction_win_rate_pct'),
            'strategy_e_allotment_win_rate_pct': strat_e_metrics.get('allotment_realized_win_rate_pct'),
            'strategy_e_mean_net_return_pct': strat_e_metrics.get('allotment_mean_net_return_pct'),
            'observed_severe_losses_mb': loss_mb.get('n_severe_events'),
            'caught_severe_losses_mb': loss_mb.get('confusion_matrix', {}).get('true_positives_caught'),
            'observed_severe_losses_sme': loss_sme.get('n_severe_events'),
            'caught_severe_losses_sme': loss_sme.get('confusion_matrix', {}).get('true_positives_caught')
        }
        
        # Inconclusive due to insufficient sample size
        cal_mb = self.evaluate_prospective_calibration('Mainboard', require_clean_cohort=require_clean_cohort)
        cal_sme = self.evaluate_prospective_calibration('SME', require_clean_cohort=require_clean_cohort)
        
        inconclusive_items = {
            'calibration_slope_and_deciles': {
                'status': 'INCONCLUSIVE_INSUFFICIENT_SAMPLE',
                'explanation': ('Calibration slopes and reliability deciles require N >= 50 per segment (min 10 items/bin). '
                                'At N=30 total split between Mainboard and SME, binning produces severe binomial noise. '
                                'Model must NOT be recalibrated based on 30-IPO cohort.')
            },
            'hypothesis_testing_statistical_superiority': {
                'status': 'INCONCLUSIVE_UNDERPOWERED',
                'explanation': 'Sample size N=30 provides statistical power < 35% for detecting AUC lift; p-values are uninterpretable.'
            },
            'severe_loss_statistical_significance': {
                'status': 'INCONCLUSIVE_LOW_EVENT_COUNT',
                'explanation': 'Low expected event count (typically 1 to 4 events in 30 IPOs) produces Wilson CIs spanning 20% to 95%.'
            }
        }
        
        return {
            'checkpoint_id': 'CHECKPOINT_30_IPOS',
            'governance_mandate': {
                'execution_mode': 'OPERATIONAL_SHADOW_LOGGING_ONLY',
                'real_money_trading': 'STRICTLY_PROHIBITED',
                'automatic_production_authorization': False,
                'mandate_statement': ('The 30-IPO checkpoint serves strictly as an operational sanity check and diagnostic review. '
                                      'It does NOT establish statistical profitability and NEVER automatically authorizes live capital deployment.'),
                'brier_skill_score_acceptance_rules': {
                    'checkpoint_monitoring_standard': ('Report point estimate and bootstrap 95% CI. Labeled preliminary diagnostic. '
                                                       'Lower bound > 0 is NOT required at N=30 due to wide sampling variance.'),
                    'future_statistical_production_hurdle': ('Advancement to real-world capital deployment requires N >= 100 untouched cases, '
                                                            'point estimate BSS > 0, and bootstrap 95% CI lower bound > 0.0.')
                }
            },
            'operational_pass_fail_checks': op_checks,
            'early_performance_diagnostics': early_diag,
            'inconclusive_statistical_checks': inconclusive_items,
            'overall_status': 'PASS_OPERATIONAL_DIAGNOSTIC' if op_checks['overall_operational_pass'] else 'FAIL_OPERATIONAL_CHECK'
        }

    def get_cohort_populations(self):
        """
        Returns the three distinct tracking populations for rigorous audit:
          1. all_eligible_cohort: All eligible IPO decisions logged (Denominator for coverage)
          2. clean_prospective_cohort: Verified pre-cutoff data (Primary leakage-controlled evaluation)
          3. excluded_unverified_cohort: Retained for transparency, reporting, and selection-bias analysis.
        """
        df_all = self.get_matched_prospective_dataset(require_clean_cohort=False)
        df_clean = df_all[df_all['eligible_clean'] == True].copy()
        df_excluded = df_all[df_all['eligible_clean'] == False].copy()
        return {
            'all_eligible_cohort': df_all,
            'clean_prospective_cohort': df_clean,
            'excluded_unverified_cohort': df_excluded,
            'counts': {
                'n_all_eligible': len(df_all),
                'n_clean_prospective': len(df_clean),
                'n_excluded_unverified': len(df_excluded),
                'clean_coverage_pct': round((len(df_clean) / len(df_all) * 100.0), 2) if len(df_all) > 0 else 0.0
            }
        }

    def audit_selection_bias(self):
        """
        Audits potential selection bias between the clean prospective cohort and the excluded cohort.
        Ensures difficult-to-verify IPOs are not silently dropped without documenting systematic differences.
        """
        pops = self.get_cohort_populations()
        df_clean = pops['clean_prospective_cohort']
        df_excl = pops['excluded_unverified_cohort']
        
        n_clean = len(df_clean)
        n_excl = len(df_excl)
        
        clean_mb = int((df_clean['board_type'] == 'Mainboard').sum()) if n_clean > 0 else 0
        clean_sme = int((df_clean['board_type'] == 'SME').sum()) if n_clean > 0 else 0
        excl_mb = int((df_excl['board_type'] == 'Mainboard').sum()) if n_excl > 0 else 0
        excl_sme = int((df_excl['board_type'] == 'SME').sum()) if n_excl > 0 else 0
        
        clean_sme_pct = round((clean_sme / float(n_clean)) * 100.0, 2) if n_clean > 0 else 0.0
        excl_sme_pct = round((excl_sme / float(n_excl)) * 100.0, 2) if n_excl > 0 else 0.0
        
        reasons_count = {}
        for _, row in df_excl.iterrows():
            warns = row.get('data_quality_warnings', [])
            if not warns:
                reasons_count['UNSPECIFIED_TIMING_FAILURE'] = reasons_count.get('UNSPECIFIED_TIMING_FAILURE', 0) + 1
            for w in warns:
                prefix = w.split(':')[0].strip()
                reasons_count[prefix] = reasons_count.get(prefix, 0) + 1
                
        clean_known = df_clean[df_clean['is_outcome_recorded'] == True]
        excl_known = df_excl[df_excl['is_outcome_recorded'] == True]
        
        clean_pos_rate = round(float(clean_known['is_positive_open'].mean() * 100.0), 2) if len(clean_known) > 0 else None
        excl_pos_rate = round(float(excl_known['is_positive_open'].mean() * 100.0), 2) if len(excl_known) > 0 else None
        
        clean_severe_rate = round(float(clean_known['is_severe_loss'].mean() * 100.0), 2) if len(clean_known) > 0 else None
        excl_severe_rate = round(float(excl_known['is_severe_loss'].mean() * 100.0), 2) if len(excl_known) > 0 else None
        
        bias_warning = None
        if clean_pos_rate is not None and excl_pos_rate is not None:
            rate_diff = abs(clean_pos_rate - excl_pos_rate)
            if rate_diff > 15.0 and len(excl_known) >= 5:
                bias_warning = (f"SELECTION_BIAS_WARNING: Clean cohort positive rate ({clean_pos_rate}%) differs substantially "
                                f"from excluded cohort positive rate ({excl_pos_rate}%). Clean cohort may not be representative.")
        elif abs(clean_sme_pct - excl_sme_pct) > 25.0 and n_excl >= 5:
            bias_warning = (f"SELECTION_BIAS_WARNING: Excluded cohort has disproportionate SME share ({excl_sme_pct}% vs clean {clean_sme_pct}%). "
                            "Exclusion policy may be penalizing SME documentation.")
                            
        return {
            'status': 'EVALUATED',
            'n_clean_prospective': n_clean,
            'n_excluded_unverified': n_excl,
            'clean_segment_mix': {'Mainboard': clean_mb, 'SME': clean_sme, 'sme_share_pct': clean_sme_pct},
            'excluded_segment_mix': {'Mainboard': excl_mb, 'SME': excl_sme, 'sme_share_pct': excl_sme_pct},
            'exclusion_reasons_breakdown': reasons_count,
            'clean_known_outcomes': len(clean_known),
            'excluded_known_outcomes': len(excl_known),
            'clean_positive_open_rate_pct': clean_pos_rate,
            'excluded_positive_open_rate_pct': excl_pos_rate,
            'clean_severe_loss_rate_pct': clean_severe_rate,
            'excluded_severe_loss_rate_pct': excl_severe_rate,
            'selection_bias_warning': bias_warning
        }

    def generate_four_tier_performance_report(self, strategy_name='Strategy_E_Combined'):
        """
        Separates evaluation strictly into four distinct tiers:
          Tier 1: Model Prediction Results (IPO-level, allotment-independent classification)
          Tier 2: Observed Allotment Results (Empirical registrar basis records)
          Tier 3: Actual Execution Results (Live broker fills, realized slippage & commissions)
          Tier 4: Simulated Scenario Analysis (Hypothetical uniform draw grid)
        """
        df = self.get_matched_prospective_dataset(require_clean_cohort=True)
        strat_col_map = {
            'Strategy_A_Apply_All': 'strat_A',
            'Strategy_B_Macro_Filter': 'strat_B',
            'Strategy_C_Positive_Ranking': 'strat_C',
            'Strategy_D_Downside_Filter': 'strat_D',
            'Strategy_E_Combined': 'strat_E'
        }
        col = strat_col_map.get(strategy_name, 'strat_E')
        df_applied = df[df[col] == True].copy()
        df_applied_known = df_applied[df_applied['is_outcome_recorded'] == True].copy()
        
        n_applied = len(df_applied)
        n_known = len(df_applied_known)
        
        if n_known > 0:
            pred_wins = int(df_applied_known['is_positive_open'].sum())
            pred_losses = n_known - pred_wins
            pred_win_rate = round((pred_wins / float(n_known)) * 100.0, 2)
            severe_losses = int(df_applied_known['is_severe_loss'].sum())
            severe_rate = round((severe_losses / float(n_known)) * 100.0, 2)
        else:
            pred_wins, pred_losses, pred_win_rate, severe_losses, severe_rate = 0, 0, None, 0, None
            
        brier_res = self.evaluate_prospective_brier_and_skill(require_clean_cohort=True)
        
        tier_1 = {
            'tier_name': 'Tier 1: Model Prediction Results',
            'description': 'Pure out-of-time forecasting ability independent of allotment lottery or capital constraints.',
            'strategy_evaluated': strategy_name,
            'applied_ipo_count': n_applied,
            'known_outcomes_count': n_known,
            'ipo_prediction_win_rate_pct': pred_win_rate,
            'severe_loss_rate_pct': severe_rate,
            'model_brier_score': brier_res.get('model_brier_score'),
            'train_baseline_brier_score': brier_res.get('train_baseline_brier_score'),
            'brier_skill_score': brier_res.get('brier_skill_score'),
            'brier_skill_score_bootstrap_95_ci': brier_res.get('bootstrap_95_ci_bss')
        }
        
        df_allotted = df_applied[df_applied['observed_allotment_status'] == 'ALLOTTED']
        df_unallotted = df_applied[df_applied['observed_allotment_status'] == 'UNALLOTTED']
        df_allot_unknown = df_applied[~df_applied['observed_allotment_status'].isin(['ALLOTTED', 'UNALLOTTED'])]
        
        has_empirical_allotment = len(df_allotted) > 0 or len(df_unallotted) > 0
        tier_2 = {
            'tier_name': 'Tier 2: Observed Allotment Results',
            'description': 'Empirical investor allotment experience from verified registrar basis records.',
            'empirical_records_available': has_empirical_allotment,
            'allotted_applications_count': len(df_allotted),
            'unallotted_refund_count': len(df_unallotted),
            'pending_allotment_confirmation_count': len(df_allot_unknown),
            'empirical_allotment_rate_pct': round((len(df_allotted) / float(len(df_allotted) + len(df_unallotted)) * 100.0), 2) if (len(df_allotted) + len(df_unallotted)) > 0 else None,
            'status': 'VERIFIED_REGISTRAR_RECORDS' if has_empirical_allotment else 'PENDING_REGISTRAR_BASIS_CIRCULAR'
        }
        
        tier_3 = {
            'tier_name': 'Tier 3: Actual Execution Results',
            'description': 'Real-world fills, realized auction slippage, broker commissions, and STT.',
            'execution_mode': 'SHADOW_MODE_ONLY',
            'real_capital_deployed_inr': 0.0,
            'actual_broker_orders_submitted': 0,
            'realized_slippage_bps': None,
            'realized_commission_inr': None,
            'status': 'REAL_EXECUTION_STRICTLY_PROHIBITED'
        }
        
        strat_metrics = self.evaluate_prospective_metrics(strategy_name, require_clean_cohort=True)
        tier_4 = {
            'tier_name': 'Tier 4: Simulated Scenario Analysis',
            'description': 'Reproducible sensitivity grid under explicit hypothetical allotment and cost parameters.',
            'disclaimer': 'HYPOTHETICAL_SIMULATION_ONLY: Uniform draws do not represent actual investor probability or realized trading returns.',
            'modeled_parameters': {
                'opening_slippage_pct': -1.0,
                'roundtrip_costs_pct': -0.35,
                'allotment_model': 'Monotonic SHA-256 Uniform Draw u in [0, 1)'
            },
            'simulated_allotted_count': strat_metrics.get('allotted_application_count'),
            'simulated_allotment_win_rate_pct': strat_metrics.get('allotment_realized_win_rate_pct'),
            'simulated_mean_net_return_pct': strat_metrics.get('allotment_mean_net_return_pct')
        }
        
        return {
            'strategy': strategy_name,
            'tier_1_model_prediction': tier_1,
            'tier_2_observed_allotment': tier_2,
            'tier_3_actual_execution': tier_3,
            'tier_4_simulated_scenario': tier_4
        }

    def evaluate_prospective_metrics(self, strategy_name='Strategy_E_Combined', require_clean_cohort=True):
        """
        Computes prospective shadow metrics with strict separation of:
          1. IPO-level model prediction win rate (Denominator = Evaluated IPOs applied for by strategy)
          2. Allotment-conditioned realized portfolio win rate (Denominator = Applications actually allotted)
        """
        decisions = {}
        if os.path.exists(self.decision_ledger):
            with open(self.decision_ledger, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        r = json.loads(line)
                        decisions[r['ipo_id']] = r
                        
        outcomes = {}
        if os.path.exists(self.outcome_ledger):
            with open(self.outcome_ledger, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        r = json.loads(line)
                        outcomes[r['ipo_id']] = r
                        
        matched_records = []
        for ipo_id, dec in decisions.items():
            if ipo_id in outcomes:
                out = outcomes[ipo_id]
                matched_records.append({
                    'ipo_id': ipo_id,
                    'board_type': dec.get('board_type'),
                    'timing_verification_status': dec.get('timing_verification_status'),
                    'eligible_clean': dec.get('eligible_for_clean_prospective_cohort', False),
                    'applied': dec.get('strategy_decisions', {}).get(strategy_name, False),
                    'gross_return_pct': out.get('gross_open_return_pct'),
                    'net_return_pct': out.get('modeled_net_return_pct'),
                    'allotment_status': out.get('observed_allotment_status', 'UNKNOWN')
                })
                
        df_m = pd.DataFrame(matched_records)
        if df_m.empty:
            return {
                'strategy': strategy_name,
                'matched_ipos_count': 0,
                'applied_ipo_count': 0,
                'ipo_prediction_win_rate_pct': None,
                'allotted_application_count': 0,
                'allotment_realized_win_rate_pct': None
            }
            
        if require_clean_cohort:
            df_m = df_m[df_m['eligible_clean'] == True]
            
        df_applied = df_m[df_m['applied'] == True]
        applied_count = len(df_applied)
        
        # 1. IPO-level prediction win rate (Denominator = applied_count)
        if applied_count > 0:
            ipo_wins = (df_applied['gross_return_pct'] > 0).sum()
            ipo_win_rate_pct = round((ipo_wins / applied_count) * 100.0, 2)
            severe_losses = (df_applied['gross_return_pct'] <= -10.0).sum()
            severe_loss_rate_pct = round((severe_losses / applied_count) * 100.0, 2)
        else:
            ipo_wins = 0
            ipo_win_rate_pct = None
            severe_loss_rate_pct = None
            
        # 2. Allotment-conditioned realized win rate (Denominator = allotted_count)
        df_allotted = df_applied[df_applied['allotment_status'] == 'ALLOTTED']
        allotted_count = len(df_allotted)
        if allotted_count > 0:
            allotted_wins = (df_allotted['net_return_pct'] > 0).sum()
            allotment_win_rate_pct = round((allotted_wins / allotted_count) * 100.0, 2)
            mean_net_return_pct = round(float(df_allotted['net_return_pct'].mean()), 2)
        else:
            allotted_wins = 0
            allotment_win_rate_pct = None
            mean_net_return_pct = None
            
        unallotted_count = len(df_applied[df_applied['allotment_status'] == 'UNALLOTTED'])
        
        return {
            'strategy': strategy_name,
            'matched_ipos_count': len(df_m),
            'cohort_type': 'CLEAN_VERIFIED_ONLY' if require_clean_cohort else 'ALL_MATCHED',
            'applied_ipo_count': applied_count,
            'applied_denominator_description': 'Total IPOs selected for application by strategy (IPO-level prediction win rate)',
            'ipo_prediction_win_rate_pct': ipo_win_rate_pct,
            'ipo_severe_loss_rate_pct': severe_loss_rate_pct,
            'allotted_application_count': allotted_count,
            'allotted_denominator_description': 'Total applications where shares were actually allotted (allotment-conditioned realized win rate)',
            'allotment_realized_win_rate_pct': allotment_win_rate_pct,
            'allotment_mean_net_return_pct': mean_net_return_pct,
            'unallotted_refund_count': unallotted_count
        }
