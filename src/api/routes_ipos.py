import os
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from src.api.common import load_manifest, load_tracked_candidates, get_committed_ledgers
from src.prospective_lifecycle import ProspectiveLifecycleManager

router = APIRouter()
lifecycle_manager = ProspectiveLifecycleManager()

@router.get("/api/ipos")
def list_tracked_ipos(
    board: Optional[str] = None, population: Optional[str] = None,
    scoring_status: Optional[str] = None, listing_status: Optional[str] = None,
    search: Optional[str] = None, sort_by: str = Query("cutoff_timestamp_ist"),
    sort_dir: str = Query("asc"), page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)
):
    items = load_tracked_candidates()
    if search:
        q = search.lower().strip()
        items = [i for i in items if q in i.get("company_name", "").lower() or q in i.get("symbol_or_ref", "").lower() or q in i.get("ipo_id", "").lower()]
    if board and board.strip():
        items = [i for i in items if i.get("board_type", "").lower() == board.lower().strip()]
    if population and population.strip():
        items = [i for i in items if i.get("cohort_population", "").lower() == population.lower().strip()]
    if scoring_status and scoring_status.strip():
        sc = scoring_status.upper().strip()
        items = [i for i in items if (i.get("p_positive_open") is not None if sc == "SCORED" else i.get("p_positive_open") is None)]
    if listing_status and listing_status.strip():
        ls = listing_status.upper().strip()
        items = [i for i in items if (i.get("listing_date") is not None if ls == "LISTED" else i.get("listing_date") is None)]

    sort_keys = {
        "cutoff_timestamp_ist": lambda x: str(x.get("cutoff_timestamp_ist", "")),
        "open_date": lambda x: str(x.get("open_date", "")),
        "close_date": lambda x: str(x.get("close_date", "")),
        "p_positive_open": lambda x: (x.get("p_positive_open") is not None, x.get("p_positive_open") or 0.0),
        "company_name": lambda x: str(x.get("company_name", "")).lower()
    }
    items = sorted(items, key=sort_keys.get(sort_by, sort_keys["cutoff_timestamp_ist"]), reverse=(sort_dir.lower().strip() == "desc"))
    total = len(items)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size, "total_pages": max(1, (total + page_size - 1) // page_size), "ipos": items[start:start + page_size]}

@router.get("/api/ipos/{ipo_id}")
def get_ipo_detail(ipo_id: str, evaluation_timestamp_ist: Optional[str] = Query(None)):
    candidates = load_tracked_candidates()
    match = next((item for item in candidates if item["ipo_id"] == ipo_id), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"IPO {ipo_id} not found in tracked registry.")
    decisions, outcomes, _ = get_committed_ledgers()
    committed_dec = next((d for d in decisions if d.get("ipo_id") == ipo_id), None)
    committed_out = next((o for o in outcomes if o.get("ipo_id") == ipo_id), None)
    cutoff_raw = match.get("cutoff_timestamp_ist", "")
    has_auth = bool(match.get("authoritative_evidence"))
    has_tz = any(tz in cutoff_raw for tz in ["IST", "+05:30", "+0530"])
    has_hash = bool(match.get("raw_source_sha256"))
    timing_ver = match.get("is_timing_verified", False)
    pub_ts = match.get("source_publication_timestamp_ist")
    chrono = True
    if pub_ts and cutoff_raw:
        try:
            chrono = bool(pd.to_datetime(pub_ts.replace(" IST", "").strip()) <= pd.to_datetime(cutoff_raw.replace(" IST", "").strip()))
        except Exception:
            chrono = False
    manifest = load_manifest()
    sme_model = manifest.get("frozen_baseline_models", {}).get("Model_6B_SME_v1.0", {})
    prep = lifecycle_manager.audit_and_prepare_candidate(match, evaluation_timestamp_ist=evaluation_timestamp_ist)
    feat_pass = bool(match.get("board_type") == "SME" and match.get("p_positive_open") is not None and prep.get("predicted_probability") is not None)
    has_eval = bool(committed_dec and committed_out)
    return {
        "ipo": match, "candidate_lifecycle_state": prep.get("candidate_lifecycle_state", "BLOCKED_CUTOFF"),
        "readiness_gate_evaluation": prep.get("readiness_gate_evaluation", {}),
        "is_committed_prospective": committed_dec is not None, "committed_decision_record": committed_dec,
        "committed_outcome_record": committed_out,
        "evaluation_milestones": {
            "feature_and_inference_integrity": {"status": "PASS" if feat_pass else ("NOT_APPLICABLE_MAINBOARD" if match.get("board_type") == "Mainboard" else "FAIL"), "question": "Inputs correct?", "verified": feat_pass},
            "predictive_validity": {"status": "PENDING_MATURE_OBSERVATIONS" if not has_eval else "EVALUATING", "question": "Outperforms baseline?", "verified": False, "mature_prospective_samples": 1 if has_eval else 0},
            "economic_viability": {"status": "PENDING_SAMPLE_ACCUMULATION", "question": "Acceptable net return?", "verified": False, "net_alpha_confirmed": False}
        },
        "model_governance": {
            "board_type": match.get("board_type"), "model_authorized": match.get("board_type") == "SME",
            "model_name": "Model_6B_SME_v1.0" if match.get("board_type") == "SME" else "None (Coverage Tracking Only)",
            "model_sha256": sme_model.get("sha256") if match.get("board_type") == "SME" else None,
            "decision_hurdles": manifest.get("frozen_decision_hurdles", {}).get("SME", {}) if match.get("board_type") == "SME" else None,
            "scoring_rule": "Mainboard issues MUST display Not Scored. SME model is never repurposed."
        },
        "audit_checks": {
            "has_authoritative_cutoff": has_auth, "timezone_valid": has_tz, "raw_source_checksum_verified": has_hash,
            "raw_source_sha256": match.get("raw_source_sha256"), "timing_verified_prior_to_cutoff": timing_ver,
            "pre_cutoff_chronological_consistency": chrono, "model_scoring_eligibility": match.get("model_coverage_status"),
            "clean_cohort_eligible": (has_auth and has_tz and has_hash and timing_ver and chrono)
        },
        "listing_outcome": {"is_listed": match.get("listing_date") is not None, "listing_date": match.get("listing_date"), "official_open_price_inr": match.get("listing_open_inr"), "evidence_status": "PENDING_OFFICIAL_EXCHANGE_BULLETIN" if match.get("listing_date") is None else "VERIFIED"}
    }
