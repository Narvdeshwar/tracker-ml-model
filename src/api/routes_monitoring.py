import os
import pandas as pd
from fastapi import APIRouter, Query
from typing import Optional
from src.api.common import load_tracked_candidates
from src.surveillance_monitor import SurveillanceMonitor
from src.evidence_audit_protocol import ProspectiveEvidenceAuditor
from src.prospective_lifecycle import ProspectiveLifecycleManager
from src.operational_run_ledger import OperationalRunLogger

router = APIRouter()
surveillance_monitor = SurveillanceMonitor()
evidence_auditor = ProspectiveEvidenceAuditor()
lifecycle_manager = ProspectiveLifecycleManager()

def _load_past_ipos_preview():
    past_ipos = []
    past_csv, pred_csv = os.path.join("data_verified", "ipo_cohort_verified.csv"), os.path.join("data", "processed", "step_6a_predictions.csv")
    if not os.path.exists(past_csv): return past_ipos
    try:
        df = pd.read_csv(past_csv)
        df['dt'] = pd.to_datetime(df['listing_date'], errors='coerce')
        pred_map = {}
        if os.path.exists(pred_csv):
            pdf = pd.read_csv(pred_csv)
            for _, pr in pdf[pdf['model_id'] == 'Model_6B_Logistic_PositiveOpen'].iterrows():
                if pd.notna(pr.get('predicted_probability')):
                    pred_map[str(pr.get('company_name')).strip().lower()] = float(pr.get('predicted_probability'))
        for _, r in df.dropna(subset=['dt']).sort_values('dt', ascending=False).head(8).iterrows():
            hp = pred_map.get(str(r.get("company_name")).strip().lower())
            pct = round(hp * 100, 0) if hp is not None else None
            ret = float(r.get("return_pct", 0))
            past_ipos.append({
                "company_name": r.get("company_name"), "board_type": "SME" if "sme" in str(r.get("board_type")).lower() else "Mainboard",
                "listing_date": str(r.get("listing_date")), "issue_price": float(r.get("issue_price_inr", 0)),
                "listing_open": float(r.get("listing_open_inr", 0)), "gain_percentage": ret, "model_predicted_pct": pct,
                "model_prediction_label": f"{int(pct)}% Chance" if pct is not None else "70% Baseline",
                "model_recommendation": "APPLY (PROFIT LIKELY)" if (hp and hp >= 0.6) else ("AVOID (RISK)" if (hp and hp < 0.6) else "NEUTRAL"),
                "actual_outcome": "PROFIT" if ret > 0 else "LOSS",
                "model_accuracy": "CORRECT" if ((hp and hp >= 0.5 and ret > 0) or (hp and hp < 0.5 and ret <= 0)) else ("WRONG" if hp else "N/A")
            })
    except Exception: pass
    return past_ipos

@router.get("/api/monitoring/status")
def get_monitoring_status():
    rep = lifecycle_manager.generate_daily_monitoring_report()
    op_logger = OperationalRunLogger()
    chain = op_logger.verify_ledger_chain()
    def _t(runs):
        if not runs: return {"status": "UNVERIFIED", "last_run_ist": None, "exit_code": None}
        r = runs[0]
        return {"status": "PASS" if r.get("overall_result") == "SUCCESS" else "FAIL", "last_run_ist": r.get("start_time_ist"), "exit_code": r.get("exit_code"), "duration_seconds": r.get("duration_seconds")}
    rep["past_ipos_preview"] = _load_past_ipos_preview()
    rep["operational_readiness"] = {
        "ledger_integrity": "VALID" if chain.get("valid") else "INVALID", "ledger_record_count": chain.get("count", 0), "last_hash": chain.get("last_hash"),
        "tasks": {"notice_collector": _t(op_logger.get_latest_runs(1, action="collect_notices")), "deadline_sweeper": _t(op_logger.get_latest_runs(1, action="sweep_expiries")), "monitoring_report": _t(op_logger.get_latest_runs(1, action="monitoring_report"))},
        "soak_test": {"completed_sessions": 0, "required_sessions": 5, "progress_label": "0/5 qualifying sessions", "current_session_date": "2026-10-30", "current_session_status": "IN_PROGRESS", "acceptance_criteria": "Minimum 5 consecutive qualifying market sessions"},
        "frozen_model_sha256": rep.get("frozen_artifacts_integrity", {}).get("model_sha256"), "last_verified_timestamp_ist": rep.get("report_timestamp_ist")
    }
    return rep

@router.get("/api/monitoring/operational-health")
def get_monitoring_operational_health(): return surveillance_monitor.get_operational_health_report()
@router.get("/api/monitoring/feature-quality")
def get_monitoring_feature_quality(): return surveillance_monitor.audit_feature_quality()
@router.get("/api/monitoring/drift")
def get_monitoring_drift_surveillance(min_sample_size: int = Query(15, ge=5, le=100)): return surveillance_monitor.audit_drift_surveillance(min_sample_size=min_sample_size)
@router.get("/api/monitoring/outcome-lifecycle")
def get_monitoring_outcome_lifecycle(): return surveillance_monitor.audit_outcome_lifecycle()
@router.get("/api/monitoring/governance-audit-trail")
def get_monitoring_governance_audit_trail(limit: int = Query(50, ge=1, le=200)):
    ev = surveillance_monitor.get_governance_audit_trail(limit=limit)
    return {"total_events": len(ev), "events": ev}
@router.get("/api/monitoring/population-reconciliation")
def get_monitoring_population_reconciliation(): return surveillance_monitor.audit_population_reconciliation()
@router.get("/api/audit/observation-level")
def get_audit_observation_level(): return evidence_auditor.audit_observation_level_evidence()
@router.get("/api/metrics/rigorous-eval")
def get_metrics_rigorous_eval(board: Optional[str] = Query(None), require_clean: bool = Query(True)):
    return evidence_auditor.evaluate_prospective_metrics_rigorous(board_type=board, require_clean=require_clean)
@router.get("/api/audit/checkpoint-verification")
def get_audit_checkpoint_verification(): return evidence_auditor.verify_sealed_checkpoint()
@router.get("/api/evaluation/records")
def get_evaluation_records(): return lifecycle_manager.generate_evaluation_records()
@router.get("/api/candidates/pre-cutoff-audit")
def get_candidates_pre_cutoff_audit():
    cands = load_tracked_candidates()
    return {"total_candidates": len(cands), "audited_candidates": [lifecycle_manager.audit_and_prepare_candidate(c) for c in cands]}
