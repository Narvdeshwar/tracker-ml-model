export interface CandidateReport {
  ipo_id: string;
  company_name: string;
  board_type: string;
  exchange: string;
  asserted_cutoff_timestamp_ist: string;
  cutoff_verification_status: string;
  current_lifecycle_state: string;
  model_eligibility: string;
  predicted_probability: number | null;
  failed_readiness_gates: string[];
  blocking_reasons: string[];
  hours_to_cutoff: number | null;
  evidence_reference: string;
  evidence_sha256: string | null;
  next_required_action: string;
}

export interface PastIPO {
  company_name: string;
  board_type: string;
  listing_date: string;
  issue_price: number;
  listing_open: number;
  gain_percentage: number;
  model_predicted_pct: number | null;
  model_prediction_label: string;
  model_recommendation: string;
  actual_outcome: 'PROFIT' | 'LOSS';
  model_accuracy: 'CORRECT' | 'WRONG' | 'N/A';
}

export interface TaskExecutionState {
  status: string;
  last_run_ist: string | null;
  exit_code: number | null;
  duration_seconds?: number;
}

export interface OperationalReadiness {
  ledger_integrity: string;
  ledger_record_count: number;
  last_hash: string;
  tasks: {
    notice_collector: TaskExecutionState;
    deadline_sweeper: TaskExecutionState;
    monitoring_report: TaskExecutionState;
  };
  soak_test: {
    completed_sessions: number;
    required_sessions: number;
    progress_label: string;
    current_session_date: string;
    current_session_status: string;
    acceptance_criteria: string;
  };
  frozen_model_sha256: string;
  last_verified_timestamp_ist: string;
}

export interface MonitoringReport {
  report_timestamp_ist: string;
  operating_mode: string;
  frozen_artifacts_integrity: {
    model_status: string;
    manifest_status: string;
    model_sha256: string;
    manifest_sha256: string;
  };
  candidate_count: number;
  candidate_reports: CandidateReport[];
  approaching_cutoffs_48h: string[];
  expired_candidates: string[];
  persistence_and_governance: {
    decision_ledger_records: number;
    outcome_ledger_records: number;
    evaluation_records: number;
    governance_audit_events_count: number;
    ledger_integrity_status: string;
  };
  operational_readiness?: OperationalReadiness;
  past_ipos_preview?: PastIPO[];
}
