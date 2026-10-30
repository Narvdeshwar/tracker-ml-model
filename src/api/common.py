import os
import json
import hashlib
from typing import Dict, List, Optional, Any

MANIFEST_PATH = 'models/frozen/phase_9b_baseline_manifest.json'
DECISION_LEDGER = 'data/processed/prospective_decision_ledger.jsonl'
OUTCOME_LEDGER = 'data/processed/prospective_outcome_ledger.jsonl'
REGISTRY_PATH = 'data/registered/tracked_candidate_registry.json'

def load_manifest() -> Dict[str, Any]:
    if not os.path.exists(MANIFEST_PATH):
        return {}
    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_tracked_candidates() -> List[Dict[str, Any]]:
    if not os.path.exists(REGISTRY_PATH):
        return []
    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def verify_frozen_models() -> Dict[str, Any]:
    manifest = load_manifest()
    results = {}
    all_match = True
    for model_name, info in manifest.get('frozen_baseline_models', {}).items():
        m_path = info.get('path')
        exp_sha = info.get('sha256')
        if not os.path.exists(m_path):
            results[model_name] = {'status': 'MISSING', 'path': m_path, 'match': False}
            all_match = False
            continue
        with open(m_path, 'rb') as f:
            act_sha = hashlib.sha256(f.read()).hexdigest()
        m = (act_sha == exp_sha)
        if not m:
            all_match = False
        results[model_name] = {
            'status': 'VERIFIED' if m else 'CORRUPT',
            'path': m_path,
            'expected_sha256': exp_sha,
            'actual_sha256': act_sha,
            'match': m
        }
    return {
        'all_verified': all_match,
        'manifest_version': manifest.get('manifest_version'),
        'governance': manifest.get('governance'),
        'models': results
    }

def get_committed_ledgers():
    decisions = []
    outcomes = []
    warnings = []
    for path, target in [(DECISION_LEDGER, decisions), (OUTCOME_LEDGER, outcomes)]:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for idx, line in enumerate(f):
                        if line.strip():
                            try:
                                target.append(json.loads(line.strip()))
                            except Exception as e:
                                warnings.append(f"Corrupt JSON at {path} line {idx+1}: {e}")
            except Exception as e:
                warnings.append(f"Failed to read {path}: {e}")
    return decisions, outcomes, warnings
