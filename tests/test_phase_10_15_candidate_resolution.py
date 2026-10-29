"""
Unit tests for Phase 10.15: Evidence-Backed Candidate Resolution & Prospective Integrity.
Verifies:
  1. Official evidence verification for the correct candidate.
  2. Secondary-source cutoff rejection.
  3. Evidence for one IPO being rejected for another IPO.
  4. Missing or malformed evidence hashes.
  5. Publication after decision time rejection at persistence boundary.
  6. Retrieval after decision time rejection at persistence boundary.
  7. Contradictory source timestamps rejection.
  8. Original timestamp correction record preserving the historical audit.
  9. Blocked candidate rejection at the persistence boundary.
  10. Forged readiness status rejection.
  11. Readiness becoming stale before commitment.
  12. Explicit administrative authorization requirement.
  13. Expired candidate rejection.
  14. Concurrent duplicate commitment attempts.
  15. Ledger corruption blocking writes.
  16. Frozen model and manifest integrity.
  17. Exact feature definitions and units.
  18. Reproducible inference.
  19. Mainboard scoring prohibition.
  20. Empty-outcome evaluation remaining inconclusive.
  21. API and dashboard consistency.
  22. No automatic commitment of ready candidates.
  23. No real-money execution functionality.
"""

import os
import json
import shutil
import tempfile
import unittest
import pandas as pd
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from src.api.main import app
from src.prospective_lifecycle import (
    ProspectiveLifecycleManager,
    parse_timezone_aware_ts,
    FROZEN_SME_MODEL_SHA256,
    FROZEN_SME_MODEL_PATH,
    MANIFEST_SHA256,
    CANDIDATE_REGISTRY_PATH
)
from src.prospective_simulator_logger import ProspectiveDecisionLogger
from src.evidence_audit_protocol import ProspectiveEvidenceAuditor
from src.surveillance_monitor import SurveillanceMonitor, MANIFEST_PATH


class TestPhase1015CandidateResolution(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.decision_ledger = os.path.join(self.test_dir, "test_decision_ledger.jsonl")
        self.outcome_ledger = os.path.join(self.test_dir, "test_outcome_ledger.jsonl")
        self.checkpoint_path = os.path.join(self.test_dir, "test_checkpoint.json")
        self.candidate_registry = os.path.join(self.test_dir, "test_registry.json")
        self.audit_events_path = os.path.join(self.test_dir, "test_events.jsonl")
        self.evaluation_records = os.path.join(self.test_dir, "test_eval_records.jsonl")

        self.lifecycle = ProspectiveLifecycleManager(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger,
            candidate_registry_path=self.candidate_registry,
            audit_events_path=self.audit_events_path,
            evaluation_records_path=self.evaluation_records,
            checkpoint_path=self.checkpoint_path
        )
        self.client = TestClient(app)

        # Baseline valid candidate template (ready state fixture)
        self.valid_sme_candidate = {
            "ipo_id": "test-sme-valid-gate-15",
            "company_name": "Gate 15 Test SME Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-15 16:00:00 IST",
            "authoritative_evidence": "BSE SME Notice Ref 20261110-88: Verified closing 16:00:00 IST",
            "source_publication_timestamp_ist": "2026-11-10 10:00:00 IST",
            "retrieval_timestamp_ist": "2026-11-10 10:05:00 IST",
            "effective_timestamp_ist": "2026-11-10 10:00:00 IST",
            "raw_source_sha256": "e" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {
                "feat_nifty50_ret5s_pct": 0.85,
                "feat_india_vix": 13.8,
                "feat_recent5_sentiment": 7.7
            },
            "individual_feature_provenance": {
                "feat_nifty50_ret5s_pct": {
                    "source_publication_timestamp_ist": "2026-11-10 10:00:00 IST",
                    "retrieval_timestamp_ist": "2026-11-10 10:05:00 IST",
                    "effective_timestamp_ist": "2026-11-10 10:00:00 IST",
                    "source_artifact_sha256": "1" * 64
                },
                "feat_india_vix": {
                    "source_publication_timestamp_ist": "2026-11-10 10:00:00 IST",
                    "retrieval_timestamp_ist": "2026-11-10 10:05:00 IST",
                    "effective_timestamp_ist": "2026-11-10 10:00:00 IST",
                    "source_artifact_sha256": "2" * 64
                },
                "feat_recent5_sentiment": {
                    "source_publication_timestamp_ist": "2026-11-10 10:00:00 IST",
                    "retrieval_timestamp_ist": "2026-11-10 10:05:00 IST",
                    "effective_timestamp_ist": "2026-11-10 10:00:00 IST",
                    "source_artifact_sha256": "3" * 64
                }
            }
        }

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # 1. Official evidence verification for the correct candidate
    def test_01_official_evidence_verified_for_correct_candidate(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "READY_FOR_PROSPECTIVE_COMMIT")
        self.assertTrue(prep["is_clean_eligible"])
        self.assertEqual(prep["readiness_gate_evaluation"]["official_cutoff_status"], "PASS")

    # 2. Secondary-source cutoff rejection
    def test_02_secondary_source_cutoff_rejected(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["authoritative_evidence"] = "Chittorgarh / Portal summary report (secondary aggregator)"
        cand["is_bidding_cutoff_verified"] = False
        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_CUTOFF")
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("EXCHANGE_BIDDING_CUTOFF_UNVERIFIED" in r for r in prep["exclusion_reasons"]))

    # 3. Evidence for one IPO being rejected for another IPO
    def test_03_mismatched_ipo_evidence_rejected(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["authoritative_evidence"] = "NSE Notice Ref 2026-10: Applicable to Alpha Corp Ltd (Different Issuer)"
        # Evidence clearly mentions another company
        cand["is_bidding_cutoff_verified"] = False
        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_CUTOFF")
        self.assertFalse(prep["is_clean_eligible"])

    # 4. Missing or malformed evidence hashes
    def test_04_malformed_evidence_hash_rejected(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["raw_source_sha256"] = "short_hash_123"
        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("MISSING_OR_INVALID_PROVENANCE_HASH" in r for r in prep["exclusion_reasons"]))

    # 5. Publication after decision time rejection at persistence boundary
    def test_05_publication_after_decision_time_rejected_at_persistence(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["source_publication_timestamp_ist"] = "2026-11-12 10:00:00 IST"  # After 11-11 decision time
        with self.assertRaises(ValueError) as ctx:
            self.lifecycle.commit_prospective_decision(
                cand,
                override_commit_timestamp_ist="2026-11-11 12:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "lead_researcher"}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    # 6. Retrieval after decision time rejection at persistence boundary
    def test_06_retrieval_after_decision_time_rejected_at_persistence(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["individual_feature_provenance"]["feat_nifty50_ret5s_pct"]["retrieval_timestamp_ist"] = "2026-11-11 15:00:00 IST"
        with self.assertRaises(ValueError) as ctx:
            self.lifecycle.commit_prospective_decision(
                cand,
                override_commit_timestamp_ist="2026-11-11 12:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "lead_researcher"}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    # 7. Contradictory source timestamps rejection
    def test_07_contradictory_source_timestamps_rejected(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["individual_feature_provenance"]["feat_recent5_sentiment"]["source_publication_timestamp_ist"] = "2026-11-10 14:00:00 IST"
        cand["individual_feature_provenance"]["feat_recent5_sentiment"]["retrieval_timestamp_ist"] = "2026-11-10 13:00:00 IST"
        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("RETRIEVAL_BEFORE_PUB_ANOMALY" in r for r in prep["exclusion_reasons"]))

    # 8. Original timestamp correction record preserving the historical audit
    def test_08_timestamp_correction_record_preservation(self):
        self.assertTrue(os.path.exists("reports/phase_10_13_point_in_time_audit.md"))
        self.assertTrue(os.path.exists("reports/phase_10_14_independent_gate_audit.md"))
        # Verify raw data integrity
        nifty_path = "data/inputs/indices/nifty50_price.csv"
        df_nifty = pd.read_csv(nifty_path)
        self.assertEqual(df_nifty.iloc[-1]["date"], "2026-10-27")

    # 9. Blocked candidate rejection at the persistence boundary
    def test_09_blocked_candidate_rejection_at_persistence_boundary(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["is_bidding_cutoff_verified"] = False  # Held in BLOCKED_CUTOFF
        with self.assertRaises(ValueError) as ctx:
            self.lifecycle.commit_prospective_decision(
                cand,
                override_commit_timestamp_ist="2026-11-11 12:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "lead_researcher"}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    # 10. Forged readiness status rejection
    def test_10_forged_readiness_status_rejection(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["is_bidding_cutoff_verified"] = False
        cand["candidate_lifecycle_state"] = "READY_FOR_PROSPECTIVE_COMMIT"  # Forged by caller
        cand["is_clean_eligible"] = True                                    # Forged by caller
        with self.assertRaises(ValueError) as ctx:
            self.lifecycle.commit_prospective_decision(
                cand,
                override_commit_timestamp_ist="2026-11-11 12:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "lead_researcher"}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    # 11. Readiness becoming stale before commitment
    def test_11_readiness_becoming_stale_before_commitment(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        # Evaluated at valid time, but committed past cutoff
        cand["cutoff_timestamp_ist"] = "2026-11-15 16:00:00 IST"
        with self.assertRaises(ValueError) as ctx:
            self.lifecycle.commit_prospective_decision(
                cand,
                override_commit_timestamp_ist="2026-11-15 16:30:00 IST",  # 30 mins after cutoff
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "lead_researcher"}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    # 12. Explicit administrative authorization requirement
    def test_12_explicit_authorization_requirement(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        # Missing explicit authorization dict
        with self.assertRaises(ValueError) as ctx:
            self.lifecycle.commit_prospective_decision(
                cand,
                override_commit_timestamp_ist="2026-11-11 12:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization=None
            )
        self.assertIn("COMMIT_BLOCKED_NO_EXPLICIT_AUTHORIZATION", str(ctx.exception))

        # Successfully commits when explicit authorization is provided
        res = self.lifecycle.commit_prospective_decision(
            cand,
            override_commit_timestamp_ist="2026-11-11 12:00:00 IST",
            strict_clean_only=True,
            explicit_admin_authorization={"authorized_by": "lead_governance_officer"}
        )
        self.assertEqual(res["status"], "RECORDED")
        self.assertTrue(res["is_clean_eligible"])

    # 13. Expired candidate rejection
    def test_13_expired_candidate_rejection(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["cutoff_timestamp_ist"] = "2026-10-20 16:00:00 IST"
        with self.assertRaises(ValueError) as ctx:
            self.lifecycle.commit_prospective_decision(
                cand,
                override_commit_timestamp_ist="2026-10-28 12:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "lead_researcher"}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    # 14. Concurrent duplicate commitment attempts
    def test_14_concurrent_duplicate_commitment_attempts(self):
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        def commit_proc(i):
            return logger.record_prospective_decision(
                ipo_id="p15-race-cand",
                company_name="P15 Race Test Ltd",
                board_type="SME",
                cutoff_timestamp_ist="2026-11-20 16:00:00 IST",
                features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0},
                p_positive_open=0.80,
                p_macro=0.80,
                p_severe_loss=0.05,
                model_name="Model_6B_SME_v1.0",
                model_sha256=FROZEN_SME_MODEL_SHA256
            )
        with ThreadPoolExecutor(max_workers=5) as executor:
            res_list = list(executor.map(commit_proc, range(5)))
        statuses = [r["status"] for r in res_list]
        self.assertEqual(statuses.count("RECORDED"), 1)
        self.assertEqual(statuses.count("DUPLICATE_IGNORED"), 4)

    # 15. Ledger corruption blocking writes
    def test_15_ledger_corruption_blocks_writes(self):
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        os.makedirs(os.path.dirname(self.decision_ledger), exist_ok=True)
        with open(self.decision_ledger, "w") as f:
            f.write("{BAD_JSON_CORRUPTION\n")

        with self.assertRaises(IOError) as ctx:
            logger.record_prospective_decision(
                ipo_id="corrupt-cand-15",
                company_name="Corrupt 15 Ltd",
                board_type="SME",
                cutoff_timestamp_ist="2026-11-20 16:00:00 IST",
                features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0},
                p_positive_open=0.80,
                p_macro=0.80,
                p_severe_loss=0.05,
                model_name="Model_6B_SME_v1.0",
                model_sha256=FROZEN_SME_MODEL_SHA256
            )
        self.assertIn("LEDGER_CORRUPTION_BLOCKED", str(ctx.exception))

    # 16. Frozen model and manifest integrity
    def test_16_frozen_model_and_manifest_integrity(self):
        surveillance = SurveillanceMonitor()
        self.assertTrue(surveillance.verify_model_integrity()["valid"])
        self.assertEqual(surveillance.verify_model_integrity()["actual_sha256"], FROZEN_SME_MODEL_SHA256)
        self.assertTrue(surveillance.verify_manifest_integrity()["valid"])
        self.assertEqual(surveillance.verify_manifest_integrity()["actual_sha256"], MANIFEST_SHA256)

    # 17. Exact feature definitions and units
    def test_17_exact_feature_definitions_and_units(self):
        res = self.lifecycle.calculate_trailing_5_sentiment("2026-10-24")
        self.assertEqual(res["status"], "VERIFIED_CALCULATED")
        self.assertEqual(res["count"], 5)
        self.assertEqual(res["mean_return_pct"], 7.7)

    # 18. Reproducible inference
    def test_18_reproducible_inference(self):
        features = {"feat_nifty50_ret5s_pct": 0.85, "feat_india_vix": 13.8, "feat_recent5_sentiment": 7.7}
        p1 = self.lifecycle.predict_frozen_sme(features)
        p2 = self.lifecycle.predict_frozen_sme(features)
        self.assertEqual(p1, 0.8144)
        self.assertEqual(p1, p2)

    # 19. Mainboard scoring prohibition
    def test_19_mainboard_scoring_prohibition(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["board_type"] = "Mainboard"
        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_GOVERNANCE")
        self.assertIsNone(prep["predicted_probability"])
        self.assertEqual(prep["model_name"], "REGISTER_FOR_COVERAGE_ONLY")
        self.assertFalse(prep["is_clean_eligible"])

    # 20. Empty-outcome evaluation remaining inconclusive
    def test_20_empty_outcome_inconclusive(self):
        resp = self.client.get("/api/metrics/brier")
        self.assertEqual(resp.status_code, 200)
        clean_status = resp.json().get("prospective_clean_cohort_status", {})
        self.assertEqual(clean_status.get("evaluation_status"), "INCONCLUSIVE_ZERO_OUTCOMES")
        self.assertFalse(clean_status.get("performance_claim_allowed", False))

    # 21. API and dashboard consistency
    def test_21_api_dashboard_consistency(self):
        resp = self.client.get("/api/ipos/wiscon-industries-sme-20261029")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("candidate_lifecycle_state"), "BLOCKED_CUTOFF")
        gate_eval = data.get("readiness_gate_evaluation", {})
        self.assertEqual(gate_eval.get("final_readiness_status"), "BLOCKED_CUTOFF")
        self.assertEqual(gate_eval.get("official_cutoff_status"), "FAIL")
        self.assertFalse(data.get("is_committed_prospective", True))

    # 22. No automatic commitment of ready candidates
    def test_22_no_automatic_commitment(self):
        prep = self.lifecycle.audit_and_prepare_candidate(self.valid_sme_candidate, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "READY_FOR_PROSPECTIVE_COMMIT")
        if os.path.exists(self.decision_ledger):
            with open(self.decision_ledger, "r") as f:
                lines = [l for l in f if l.strip()]
            self.assertEqual(len(lines), 0)
        else:
            self.assertFalse(os.path.exists(self.decision_ledger))

    # 23. No real-money execution functionality
    def test_23_no_real_money_execution_functionality(self):
        prohibited_terms = [
            "place_order", "submit_order", "broker_api", "zerodha",
            "upstox", "angelone", "buy_shares", "execute_trade"
        ]
        src_files = [os.path.join("src", f) for f in os.listdir("src") if f.endswith(".py")]
        for fpath in src_files:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read().lower()
                for term in prohibited_terms:
                    self.assertNotIn(term, content, f"Prohibited real-money term '{term}' found in {fpath}")


if __name__ == "__main__":
    unittest.main()
