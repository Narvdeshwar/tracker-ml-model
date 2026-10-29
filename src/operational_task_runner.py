"""
CLI Runner for Scheduled Operations:
  - Exchange Notice Ingestion
  - Deadline Expiry Sweeping
  - Daily Monitoring Health Inspection

Provides:
  - Standard process exit codes (0 = Success, 1 = Error / Partial Failure)
  - Timezone-aware clock default (IST)
  - Inter-process locking preservation
  - Clean error surfacing
"""

import sys
import os
import json
import argparse
import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.exchange_notice_collector import ExchangeNoticeCollector
from src.prospective_lifecycle import ProspectiveLifecycleManager, parse_timezone_aware_ts


def run_notice_collection(exchanges=None):
    exchanges = exchanges or ["BSE", "NSE"]
    collector = ExchangeNoticeCollector()
    results = {}
    any_failure = False

    print(f"[{datetime.datetime.now().isoformat()}] Starting official exchange notice collection for {exchanges}...")
    for ex in exchanges:
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
            print(f"  [-] {ex}: {res.get('error_code')} - {res.get('error_message')}")
        else:
            print(f"  [+] {ex}: SUCCESS (SHA256: {res.get('artifact_sha256')[:8]}...)")

    return 0 if not any_failure else 1, results


def run_deadline_sweep(sweep_ts=None, candidate_registry_path=None, audit_events_path=None):
    manager = ProspectiveLifecycleManager(
        candidate_registry_path=candidate_registry_path or "data/registered/tracked_candidate_registry.json",
        audit_events_path=audit_events_path or "data/processed/governance_audit_events.jsonl"
    )
    ts = sweep_ts or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
    
    # Validate timezone awareness
    if parse_timezone_aware_ts(ts) is None:
        print(f"Error: Invalid or timezone-naive sweep timestamp '{ts}'", file=sys.stderr)
        return 1, {"error": "INVALID_TIMEZONE"}

    print(f"[{datetime.datetime.now().isoformat()}] Running deadline expiry sweep at {ts}...")
    try:
        report = manager.sweep_deadline_expiries(sweep_timestamp_ist=ts)
        print(f"  Examined: {report['total_candidates_examined']}")
        print(f"  Newly Expired: {report['newly_expired_candidates']}")
        print(f"  Already Expired: {report['already_expired_candidates']}")
        print(f"  Active Unexpired: {report['active_unexpired_candidates']}")
        if report['errors']:
            print(f"  Errors: {report['errors']}", file=sys.stderr)
            return 1, report
        return 0, report
    except Exception as e:
        print(f"Fatal sweep exception: {e}", file=sys.stderr)
        return 1, {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="IPO System Operational Scheduled Task Runner")
    parser.add_argument("--action", choices=["collect_notices", "sweep_expiries", "monitoring_report"], required=True)
    parser.add_argument("--exchanges", nargs="+", default=["BSE", "NSE"])
    parser.add_argument("--timestamp", help="Optional timezone-aware timestamp (e.g. '2026-10-29 16:00:00 IST')")
    parser.add_argument("--registry-path", help="Optional candidate registry file path")
    parser.add_argument("--audit-path", help="Optional governance audit events path")
    
    args = parser.parse_args()

    if args.action == "collect_notices":
        exit_code, res = run_notice_collection(args.exchanges)
        sys.exit(exit_code)
    elif args.action == "sweep_expiries":
        exit_code, res = run_deadline_sweep(args.timestamp, args.registry_path, args.audit_path)
        sys.exit(exit_code)
    elif args.action == "monitoring_report":
        mgr = ProspectiveLifecycleManager()
        ts = args.timestamp or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
        rep = mgr.generate_daily_monitoring_report(evaluation_timestamp_ist=ts)
        print(json.dumps(rep, indent=2))
        sys.exit(0)


if __name__ == "__main__":
    main()
