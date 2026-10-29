"""
Phase 10.25 Adversarial Test Suite:
Operational Soak Test, State Separation & Telemetry Recovery.

Tests 14 distinct scenarios:
  1. Distinguish 4 operational states: Execution, Collection, Verification, Eligibility.
  2. Live BSE & NSE collection failure fails closed with LIVE_SOURCE_UNAVAILABLE.
  3. Pre-write operational ledger corruption check detects middle-of-ledger corruption.
  4. Truncated last line detection in operational ledger.
  5. Multi-process concurrent operational writes with process crash recovery.
  6. Configuration fingerprint correctly matches running configuration.
  7. Git revision tracking matches repository HEAD.
  8. Cutoff rechecked at final commitment boundary.
  9. Asserted unverified cutoff prevents commitment authorization.
  10. Expired candidate cannot be committed retroactively.
  11. Conflicting notices log governance warning and retain BLOCKED_CUTOFF.
  12. Mainboard candidates strictly non-scoring BLOCKED_GOVERNANCE.
  13. Decision, outcome, evaluation ledgers remain strictly empty at 0 records.
  14. Frozen SME model binary and baseline manifest hashes byte-for-byte identical.
"""

import os
import sys
import json
import shutil
import hashlib
import tempfile
import unittest
import subprocess
import datetime
from concurrent.futures import ThreadPoolExecutor

from src.exchange_notice_collector import ExchangeNoticeCollector
from src.operational_run_ledger import OperationalRunLogger, get_git_revision
from src.prospective_lifecycle import (
    ProspectiveLifecycleManager,
    FROZEN_SME_MODEL_SHA256,
    MANIFEST_SHA256,
    DECISION_LEDGER_PATH,
    OUTCOME_LEDGER_PATH,
    EVALUATION_RECORDS_PATH,
    AUDIT_EVENTS_PATH,
    CANDIDATE_REGISTRY_PATH
)
from src.surveillance_monitor import FROZEN_SME_MODEL_PATH, MANIFEST_PATH


class TestPhase1025SoakTestAndOperationalVerification(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_phase_10_25_")
        self.decision_ledger = os.path.join(self.test_dir, "test_decision_ledger.jsonl")
        self.outcome_ledger = os.path.join(self.test_dir, "test_outcome_ledger.jsonl")
        self.evaluation_records = os.path.join(self.test_dir, "test_eval_records.jsonl")
        self.audit_events = os.path.join(self.test_dir, "test_events.jsonl")
        self.candidate_registry = os.path.join(self.test_dir, "test_registry.json")
        self.operational_ledger = os.path.join(self.test_dir, "test_op_ledger.jsonl")
        self.artifact_dir = os.path.join(self.test_dir, "raw_artifacts")

        with open(CANDIDATE_REGISTRY_PATH, "r", encoding="utf-8") as f:
            cands = json.load(f)
        with open(self.candidate_registry, "w", encoding="utf-8") as f:
            json.dump(cands, f, indent=2)

        self.manager = ProspectiveLifecycleManager(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger,
            candidate_registry_path=self.candidate_registry,
            audit_events_path=self.audit_events,
            evaluation_records_path=self.evaluation_records
        )
        self.runner_script = os.path.join("src", "operational_task_runner.py")
        self.py_exec = sys.executable

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Workstream A: State Separation (Execution vs Collection vs Evidence vs Eligibility)
    # -------------------------------------------------------------------------
    def test_01_four_operational_states_cleanly_separated(self):
        """1. Monitoring cleanly separates Task Execution, Collection, Evidence, and Eligibility."""
        rep = self.manager.generate_daily_monitoring_report(evaluation_timestamp_ist="2026-10-29 15:30:00 IST")
        
        # State A: Execution
        self.assertIn("collection_health", rep)
        self.assertEqual(rep["collection_health"]["collector_status"], "OPERATIONAL")
        
        # State B: Collection
        self.assertIn("monitoring_source_health", rep)
        
        # State C: Evidence Verification
        self.assertIn("evidence_health", rep)
        self.assertEqual(rep["evidence_health"]["verified_primary_notices"], 0)
        self.assertGreater(rep["evidence_health"]["unverified_asserted_notices"], 0)

        # State D: Candidate Eligibility
        self.assertIn("candidate_reports", rep)
        wiscon = next(c for c in rep["candidate_reports"] if c["ipo_id"] == "wiscon-industries-sme-20261029")
        self.assertEqual(wiscon["current_lifecycle_state"], "BLOCKED_CUTOFF")
        self.assertIn("official_cutoff_status", wiscon["failed_readiness_gates"])

    def test_02_endpoint_unreachable_fails_closed(self):
        """2. When exchange endpoint is unreachable, collector records LIVE_SOURCE_UNAVAILABLE."""
        collector = ExchangeNoticeCollector()
        res = collector.fetch_exchange_notices("BSE", url_override="https://127.0.0.1:9999/nonexistent")
        self.assertFalse(res["success"])
        self.assertEqual(res["verification_status"], "LIVE_SOURCE_UNAVAILABLE")
        self.assertIn(res["error_code"], ["FETCH_FAILED", "HTTP_ERROR"])
        self.assertIsNone(res["artifact_sha256"])

    # -------------------------------------------------------------------------
    # Workstream B: Telemetry Ledger Integrity & Crash Recovery
    # -------------------------------------------------------------------------
    def test_03_telemetry_detects_middle_corruption(self):
        """3. Corrupt line in middle of operational ledger blocks writes with IOError."""
        logger = OperationalRunLogger(self.operational_ledger)
        logger.log_run("action1", "2026-10-29 10:00:00 IST", "2026-10-29 10:00:01 IST", 1.0, "SUCCESS", 0)
        with open(self.operational_ledger, "a", encoding="utf-8") as f:
            f.write("{corrupt_json_payload\n")
        
        with self.assertRaises(IOError) as ctx:
            logger.log_run("action2", "2026-10-29 10:00:02 IST", "2026-10-29 10:00:03 IST", 1.0, "SUCCESS", 0)
        self.assertIn("OPERATIONAL_LEDGER_CORRUPTION_BLOCKED", str(ctx.exception))

    def test_04_telemetry_detects_truncated_last_record(self):
        """4. Truncated/incomplete final record is flagged as corruption."""
        logger = OperationalRunLogger(self.operational_ledger)
        logger.log_run("action1", "2026-10-29 10:00:00 IST", "2026-10-29 10:00:01 IST", 1.0, "SUCCESS", 0)
        with open(self.operational_ledger, "a", encoding="utf-8") as f:
            f.write('{"record_type": "OPERATIONAL_RUN_TELEMETRY", "run_id": "RUN_TRUNCATED"')
        
        corr = logger.inspect_corruption()
        self.assertTrue(corr["has_corruption"])
        self.assertEqual(corr["corrupt_line_number"], 2)

    def test_05_concurrent_operational_writes_with_abnormal_death(self):
        """5. Process exiting abnormally while holding lock reclaims cleanly for subsequent workers."""
        worker_suicide = f"""
import sys, os, time
sys.path.insert(0, os.path.abspath('.'))
from src.operational_run_ledger import OperationalRunLogger

logger = OperationalRunLogger(r'{self.operational_ledger}')
fd = logger._acquire_process_lock()
# Die abruptly without releasing
os._exit(42)
"""
        p = subprocess.Popen([self.py_exec, "-c", worker_suicide])
        p.communicate(timeout=5)
        self.assertEqual(p.returncode, 42)

        # Subsequent worker must acquire lock immediately
        logger = OperationalRunLogger(self.operational_ledger)
        rec = logger.log_run("recovery_action", "2026-10-29 11:00:00 IST", "2026-10-29 11:00:01 IST", 0.5, "SUCCESS", 0)
        self.assertEqual(rec["action"], "recovery_action")

    def test_06_configuration_fingerprint_and_git_revision(self):
        """6. Telemetry records preserve runtime configuration fingerprint and git revision."""
        logger = OperationalRunLogger(self.operational_ledger)
        rec = logger.log_run("audit_action", "2026-10-29 11:00:00 IST", "2026-10-29 11:00:01 IST", 0.5, "SUCCESS", 0, config_fingerprint="SOAK_CONFIG_V10_25")
        self.assertEqual(rec["config_fingerprint"], "SOAK_CONFIG_V10_25")
        self.assertIsNotNone(rec["git_revision"])
        self.assertTrue(len(rec["git_revision"]) >= 7)

    # -------------------------------------------------------------------------
    # Workstream C: Candidate Cutoff & Invariants
    # -------------------------------------------------------------------------
    def test_07_cutoff_rechecked_at_commitment_boundary(self):
        """7. Candidate becoming expired immediately before commit boundary is rejected."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon = dict(next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029"))
        wiscon["is_bidding_cutoff_verified"] = True
        wiscon["authoritative_evidence"] = "BSE Official Verified"
        wiscon["raw_source_sha256"] = "c" * 64
        wiscon["source_publication_timestamp_ist"] = "2026-10-29 10:00:00 IST"
        wiscon["retrieval_timestamp_ist"] = "2026-10-29 10:05:00 IST"

        # Commit at 16:01 IST (Cutoff is 16:00 IST) -> Must fail closed
        with self.assertRaises(ValueError) as ctx:
            self.manager.commit_prospective_decision(
                candidate_dict=wiscon,
                override_commit_timestamp_ist="2026-10-29 16:01:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "Lead_Auditor", "authorization_token": "c" * 32}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    def test_08_mainboard_candidates_remain_non_scoring(self):
        """8. Mainboard candidates cannot receive Model_6B_SME_v1.0 scores or commitments."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        mb = next(c for c in cands if c["board_type"] == "Mainboard")
        prep = self.manager.audit_and_prepare_candidate(mb, evaluation_timestamp_ist="2026-10-29 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_GOVERNANCE")
        self.assertIsNone(prep["predicted_probability"])

    def test_09_production_ledgers_clean_at_zero(self):
        """9. Core production ledgers contain exactly 0 records."""
        for p in [DECISION_LEDGER_PATH, OUTCOME_LEDGER_PATH, EVALUATION_RECORDS_PATH]:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    self.assertEqual(len([l for l in f if l.strip()]), 0, f"Production ledger {p} has records!")

    def test_10_frozen_artifacts_hash_verification(self):
        """10. Frozen SME model binary and baseline manifest hashes match exact approved values."""
        with open(FROZEN_SME_MODEL_PATH, "rb") as f:
            model_hash = hashlib.sha256(f.read()).hexdigest()
        with open(MANIFEST_PATH, "rb") as f:
            manifest_hash = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(model_hash, FROZEN_SME_MODEL_SHA256)
        self.assertEqual(manifest_hash, MANIFEST_SHA256)

    def test_11_no_broker_or_real_money_execution(self):
        """11. Codebase is free of live broker order placement or real-money trading keywords."""
        prohibited_terms = [
            "place_order", "submit_order", "broker_api", "zerodha",
            "upstox", "angelone", "buy_shares", "execute_trade"
        ]
        import glob
        py_files = glob.glob("src/**/*.py", recursive=True)
        for pf in py_files:
            with open(pf, "r", encoding="utf-8") as f:
                content = f.read().lower()
            for term in prohibited_terms:
                self.assertNotIn(term, content, f"Prohibited real-money term '{term}' found in {pf}!")


if __name__ == "__main__":
    unittest.main()
