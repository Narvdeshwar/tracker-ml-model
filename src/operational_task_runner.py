"""
CLI Runner for Scheduled Operations:
  - Exchange Notice Ingestion
  - Deadline Expiry Sweeping
  - Daily Monitoring Health Inspection

Provides:
  - Standard process exit codes (0 = Success, 1 = Error / Partial Failure)
  - Timezone-aware clock default (IST)
  - Inter-process locking preservation
  - Operational run telemetry logging (isolated from decision & outcome ledgers)
  - Clean error surfacing
"""

import sys
import os
import json
import time
import argparse
import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.exchange_notice_collector import ExchangeNoticeCollector
from src.prospective_lifecycle import ProspectiveLifecycleManager, parse_timezone_aware_ts
from src.operational_run_ledger import OperationalRunLogger


def run_notice_collection(exchanges=None, operational_ledger_path=None, artifact_storage_dir=None):
    exchanges = exchanges or ["BSE", "NSE"]
    collector = ExchangeNoticeCollector(artifact_storage_dir=artifact_storage_dir)
    op_logger = OperationalRunLogger(ledger_path=operational_ledger_path)
    
    start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
    t0 = time.time()
    results = {}
    any_failure = False
    sanitized_errors = []

    retrieval_attempts = 0
    successful_retrievals = 0
    failed_retrievals = 0
    raw_artifacts_acquired = 0
    verified_primary = 0
    unverified = 0
    rejected = 0

    print(f"[{datetime.datetime.now().isoformat()}] Starting official exchange notice collection for {exchanges}...")
    for ex in exchanges:
        retrieval_attempts += 1
        res = collector.fetch_exchange_notices(ex)
        results[ex] = {
            "success": res.get("success"),
            "verification_status": res.get("verification_status"),
            "status_code": res.get("status_code"),
            "artifact_sha256": res.get("artifact_sha256"),
            "error_code": res.get("error_code"),
            "error_message": res.get("error_message")
        }
        if not res.get("success"):
            any_failure = True
            failed_retrievals += 1
            err_msg = f"{ex}: {res.get('error_code')} - {res.get('error_message')}"
            sanitized_errors.append(err_msg)
            print(f"  [-] {err_msg}")
            if res.get("verification_status") == "LIVE_SOURCE_UNAVAILABLE":
                unverified += 1
            else:
                rejected += 1
        else:
            successful_retrievals += 1
            raw_artifacts_acquired += 1
            verified_primary += 1
            print(f"  [+] {ex}: SUCCESS (SHA256: {res.get('artifact_sha256')[:8]}...)")

    duration_sec = time.time() - t0
    end_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
    exit_code = 1 if any_failure else 0
    overall_result = "SUCCESS" if exit_code == 0 else "PARTIAL_FAILURE_OR_UNAVAILABLE"

    # Log operational telemetry
    try:
        op_logger.log_run(
            action="collect_notices",
            start_time_ist=start_time,
            end_time_ist=end_time,
            duration_sec=duration_sec,
            overall_result=overall_result,
            exit_code=exit_code,
            source_identifier=",".join(exchanges),
            retrieval_attempts=retrieval_attempts,
            successful_retrievals=successful_retrievals,
            failed_retrievals=failed_retrievals,
            raw_artifacts_acquired=raw_artifacts_acquired,
            artifacts_accepted_validation=raw_artifacts_acquired,
            verified_primary_notices=verified_primary,
            unverified_notices=unverified,
            rejected_notices=rejected,
            cutoff_conflicts=0,
            candidate_transitions=0,
            sanitized_errors=sanitized_errors
        )
    except Exception as e:
        print(f"Warning: Failed to persist operational telemetry: {e}", file=sys.stderr)

    return exit_code, results


def run_deadline_sweep(sweep_ts=None, candidate_registry_path=None, audit_events_path=None, operational_ledger_path=None):
    manager = ProspectiveLifecycleManager(
        candidate_registry_path=candidate_registry_path or "data/registered/tracked_candidate_registry.json",
        audit_events_path=audit_events_path or "data/processed/governance_audit_events.jsonl"
    )
    op_logger = OperationalRunLogger(ledger_path=operational_ledger_path)
    ts = sweep_ts or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
    
    # Validate timezone awareness
    if parse_timezone_aware_ts(ts) is None:
        print(f"Error: Invalid or timezone-naive sweep timestamp '{ts}'", file=sys.stderr)
        return 1, {"error": "INVALID_TIMEZONE"}

    start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
    t0 = time.time()
    print(f"[{datetime.datetime.now().isoformat()}] Running deadline expiry sweep at {ts}...")
    try:
        report = manager.sweep_deadline_expiries(sweep_timestamp_ist=ts)
        print(f"  Examined: {report['total_candidates_examined']}")
        print(f"  Newly Expired: {report['newly_expired_candidates']}")
        print(f"  Already Expired: {report['already_expired_candidates']}")
        print(f"  Active Unexpired: {report['active_unexpired_candidates']}")
        
        has_errors = bool(report['errors'])
        exit_code = 1 if has_errors else 0
        overall_result = "SUCCESS" if exit_code == 0 else "SWEEP_ERRORS_DETECTED"
        sanitized_errors = [str(e) for e in report.get('errors', [])]

        if has_errors:
            print(f"  Errors: {report['errors']}", file=sys.stderr)

        # Log operational run
        duration_sec = time.time() - t0
        end_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
        op_logger.log_run(
            action="sweep_expiries",
            start_time_ist=start_time,
            end_time_ist=end_time,
            duration_sec=duration_sec,
            overall_result=overall_result,
            exit_code=exit_code,
            source_identifier="CANDIDATE_REGISTRY",
            candidate_transitions=len(report['newly_expired_candidates']),
            sanitized_errors=sanitized_errors
        )

        return exit_code, report
    except Exception as e:
        print(f"Fatal sweep exception: {e}", file=sys.stderr)
        try:
            op_logger.log_run(
                action="sweep_expiries",
                start_time_ist=start_time,
                end_time_ist=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST'),
                duration_sec=time.time() - t0,
                overall_result="FATAL_EXCEPTION",
                exit_code=1,
                source_identifier="CANDIDATE_REGISTRY",
                sanitized_errors=[str(e)]
            )
        except Exception:
            pass
        return 1, {"error": str(e)}


def run_monitoring_report(timestamp=None, candidate_registry_path=None, operational_ledger_path=None):
    op_logger = OperationalRunLogger(ledger_path=operational_ledger_path)
    start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
    t0 = time.time()

    ts = timestamp or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
    if parse_timezone_aware_ts(ts) is None:
        print(f"Error: Invalid or timezone-naive evaluation timestamp '{ts}'", file=sys.stderr)
        return 1, {"error": "INVALID_TIMEZONE"}

    try:
        mgr = ProspectiveLifecycleManager(
            candidate_registry_path=candidate_registry_path or "data/registered/tracked_candidate_registry.json"
        )
        rep = mgr.generate_daily_monitoring_report(evaluation_timestamp_ist=ts)

        # Attach operational telemetry from dedicated run ledger
        latest_runs = op_logger.get_latest_runs(limit=5)
        rep["operational_telemetry"] = {
            "recent_scheduled_runs_count": len(latest_runs),
            "latest_run": latest_runs[-1] if latest_runs else None,
            "operational_ledger_verified": op_logger.verify_ledger_chain().get("valid", False)
        }

        # Check source health status based on collection
        last_collect = op_logger.get_latest_runs(limit=1, action="collect_notices")
        if last_collect:
            rec = last_collect[0]
            if rec.get("overall_result") == "SUCCESS":
                rep["collection_health"]["source_availability_state"] = "OPERATIONAL"
            else:
                rep["collection_health"]["source_availability_state"] = "UNAVAILABLE"
        else:
            rep["collection_health"]["source_availability_state"] = "INSUFFICIENT_EVIDENCE"

        duration_sec = time.time() - t0
        end_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
        op_logger.log_run(
            action="monitoring_report",
            start_time_ist=start_time,
            end_time_ist=end_time,
            duration_sec=duration_sec,
            overall_result="SUCCESS",
            exit_code=0,
            source_identifier="MONITORING_ENGINE"
        )
        return 0, rep
    except Exception as e:
        print(f"Error generating monitoring report: {e}", file=sys.stderr)
        try:
            op_logger.log_run(
                action="monitoring_report",
                start_time_ist=start_time,
                end_time_ist=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST'),
                duration_sec=time.time() - t0,
                overall_result="MONITORING_FAILED",
                exit_code=1,
                source_identifier="MONITORING_ENGINE",
                sanitized_errors=[str(e)]
            )
        except Exception:
            pass
        return 1, {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="IPO System Operational Scheduled Task Runner (Phase 10.24)")
    parser.add_argument("--action", choices=["collect_notices", "sweep_expiries", "monitoring_report"], required=True)
    parser.add_argument("--exchanges", nargs="+", default=["BSE", "NSE"])
    parser.add_argument("--timestamp", help="Optional timezone-aware timestamp (e.g. '2026-10-29 16:00:00 IST')")
    parser.add_argument("--registry-path", help="Optional candidate registry file path")
    parser.add_argument("--audit-path", help="Optional governance audit events path")
    parser.add_argument("--operational-ledger", help="Optional operational run ledger path")
    parser.add_argument("--artifact-dir", help="Optional raw artifact storage directory")
    
    args = parser.parse_args()

    if args.action == "collect_notices":
        exit_code, res = run_notice_collection(
            exchanges=args.exchanges,
            operational_ledger_path=args.operational_ledger,
            artifact_storage_dir=args.artifact_dir
        )
        sys.exit(exit_code)
    elif args.action == "sweep_expiries":
        exit_code, res = run_deadline_sweep(
            sweep_ts=args.timestamp,
            candidate_registry_path=args.registry_path,
            audit_events_path=args.audit_path,
            operational_ledger_path=args.operational_ledger
        )
        sys.exit(exit_code)
    elif args.action == "monitoring_report":
        exit_code, rep = run_monitoring_report(
            timestamp=args.timestamp,
            candidate_registry_path=args.registry_path,
            operational_ledger_path=args.operational_ledger
        )
        if exit_code == 0:
            print(json.dumps(rep, indent=2))
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
