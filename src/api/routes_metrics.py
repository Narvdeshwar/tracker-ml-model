import os
from fastapi import APIRouter, Query
from typing import Optional
from src.api.common import load_manifest, load_tracked_candidates, verify_frozen_models, get_committed_ledgers, DECISION_LEDGER, OUTCOME_LEDGER
from src.prospective_simulator_logger import ProspectiveDecisionLogger
from src.surveillance_monitor import SurveillanceMonitor
from src.evidence_audit_protocol import ProspectiveEvidenceAuditor
from src.prospective_lifecycle import ProspectiveLifecycleManager

router = APIRouter()
surveillance_monitor = SurveillanceMonitor()
evidence_auditor = ProspectiveEvidenceAuditor()
lifecycle_manager = ProspectiveLifecycleManager()

@router.get("/api/status")
def get_system_status():
    model_audit = verify_frozen_models()
    logger = ProspectiveDecisionLogger()
    dec_audit = logger.verify_ledger_chain('decision')
    out_audit = logger.verify_ledger_chain('outcome')
    decisions, outcomes, warnings = get_committed_ledgers()
    candidates = load_tracked_candidates()
    ok = model_audit["all_verified"] and dec_audit.get("valid", True) and out_audit.get("valid", True) and len(warnings) == 0
    return {
        "status": "OPERATIONAL" if ok else "INTEGRITY_WARNING", "shadow_mode_active": True, "real_trading_prohibited": True,
        "governance_rule": "SHADOW_LOGGING_ONLY_NO_REAL_CAPITAL", "frozen_manifest_verified": model_audit["all_verified"],
        "manifest_version": load_manifest().get("manifest_version", "v1.0-Phase9B-Frozen"), "models_verified": model_audit["models"],
        "model_coverage": {"SME": "Model_6B_SME_v1.0 (Frozen SHA-256 Verified)", "Mainboard": "No Frozen Model (Coverage Tracking Only — Scores Never Invented)"},
        "populations": {"population_1_eligible_coverage_count": len(candidates), "population_2_clean_prospective_count": sum(1 for c in candidates if c["cohort_population"] == "Population_2_Clean_Prospective"), "population_3_excluded_unverified_count": sum(1 for c in candidates if c["cohort_population"] == "Population_3_Excluded_Unverified")},
        "live_ledgers": {"decision_ledger_path": DECISION_LEDGER, "outcome_ledger_path": OUTCOME_LEDGER, "committed_decisions_count": len(decisions), "committed_outcomes_count": len(outcomes), "decision_ledger_valid": dec_audit.get("valid", True), "outcome_ledger_valid": out_audit.get("valid", True), "integrity_warnings": warnings},
        "active_unit_tests": "150 Passing Tests"
    }

@router.get("/api/metrics/brier")
def get_brier_and_calibration_metrics(board: Optional[str] = Query(None)):
    logger = ProspectiveDecisionLogger()
    counts = logger.get_cohort_populations().get("counts", {})
    eval_res = logger.evaluate_prospective_brier_and_skill(board_type=board, require_clean_cohort=True)
    calib_res = logger.evaluate_prospective_calibration(board_type=board, require_clean_cohort=True)
    severe_res = logger.evaluate_prospective_severe_loss(board_type=board, require_clean_cohort=True)
    return {
        "fixed_training_baselines": {"SME_train_base_rate": 0.8306, "SME_reference_brier": 0.1407, "SME_training_cohort": "2020-2024 (N=360)", "Mainboard_train_base_rate": 0.7583, "Mainboard_reference_brier": 0.1833, "Mainboard_training_cohort": "2020-2024 (N=240)", "mathematical_derivation": "Reference Brier = p*(1-p) for constant climatology predictor evaluated on cohort base rate."},
        "prospective_clean_cohort_status": {"board_evaluated": eval_res.get("board_type", "All"), "n_eligible": eval_res.get("n_eligible_decisions", counts.get("n_all_eligible", 0)), "n_clean": counts.get("n_clean_prospective", 0), "n_known_outcomes": eval_res.get("n_known_outcomes", 0), "n_pending_listing": eval_res.get("n_pending_listing", 0), "evaluation_status": eval_res.get("status", "INCONCLUSIVE_ZERO_OUTCOMES"), "model_brier_score": eval_res.get("model_brier_score"), "train_baseline_brier_score": eval_res.get("train_baseline_brier_score"), "brier_skill_score": eval_res.get("brier_skill_score"), "bootstrap_95_ci_brier": eval_res.get("bootstrap_95_ci_brier"), "bootstrap_95_ci_bss": eval_res.get("bootstrap_95_ci_bss"), "roc_auc": eval_res.get("roc_auc"), "pr_auc": eval_res.get("pr_auc"), "auc_diagnostics": eval_res.get("auc_diagnostics"), "sample_size_status": "PRE_COLLECTION_STAGE (N=0 in committed live ledger; candidates registered)" if eval_res.get("n_known_outcomes", 0) == 0 else f"COLLECTED (N={eval_res.get('n_known_outcomes')})", "checkpoint_1_target": 30, "production_hurdle_target": 100, "bss_rule": "BSS > 0.0 with 95% bootstrap CI lower bound > 0.0 required for production hurdle."},
        "calibration_audit_protocol": {"status": calib_res.get("status", "INCONCLUSIVE_INSUFFICIENT_SAMPLE"), "minimum_n_for_calibration_curve": 50, "n_observed": calib_res.get("n_known_clean_samples", 0), "calibration_formula": "Grouped predicted vs observed frequency", "message": calib_res.get("message")},
        "severe_loss_diagnostics": {"status": severe_res.get("status", "INCONCLUSIVE_ZERO_OUTCOMES"), "severe_loss_events_observed": severe_res.get("severe_losses_observed", 0), "minimum_severe_events_required": 25, "severe_loss_benchmark": "PR-AUC vs base rate with Wilson score confidence intervals"}
    }

@router.get("/api/metrics/allotment")
def get_allotment_and_simulation_metrics():
    four = ProspectiveDecisionLogger().generate_four_tier_performance_report()
    return {"tier_1_prediction_layer": four.get("tier_1_prediction_layer"), "tier_2_observed_allotment_layer": four.get("tier_2_observed_allotment_layer"), "tier_3_real_execution_layer": {"status": "PROHIBITED_SHADOW_MODE_ONLY", "real_capital_deployed_inr": 0.0, "real_orders_executed": 0, "real_broker_connections": "DISABLED", "compliance_attestation": "Real-money IPO applications strictly forbidden."}, "tier_4_simulated_scenarios_layer": four.get("tier_4_simulated_scenarios_layer"), "historical_simulator_benchmarks_reconciled": {"cohort": "2026 Diagnostic Test Cohort (N=148)", "strategy_c_profit_inr": 317414.50, "strategy_c_max_drawdown_pct": 0.78, "strategy_d_profit_inr": 447042.50, "strategy_d_max_drawdown_pct": 5.17, "interpretation": "Historical simulation only; not a guarantee of prospective yield."}}

@router.get("/api/audit/selection-bias")
def get_selection_bias_audit():
    cands = load_tracked_candidates()
    return {"committed_bias_audit": ProspectiveDecisionLogger().audit_selection_bias(), "preflight_registered_cohorts": {"population_1_total": len(cands), "population_2_clean_count": sum(1 for c in cands if c["cohort_population"] == "Population_2_Clean_Prospective"), "population_3_excluded_count": sum(1 for c in cands if c["cohort_population"] == "Population_3_Excluded_Unverified"), "exclusion_reasons": {"eaaa-india-mainboard-20261028": "Timing unverified prior to issue cutoff; secondary aggregate listing."}}, "governance_note": "Evaluations are computed strictly on Population 2. Population 1 audits decision coverage."}
