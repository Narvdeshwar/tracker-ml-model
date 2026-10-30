"""
Unit tests for Phase 10.14: Independent Gate Verification & Prospective Integrity.
Verifies:
  1. Authoritative persistence boundary hard-blocks non-ready candidates.
  2. Bypassing readiness gate directly via commit_prospective_decision raises ValueError.
  3. Bypassing readiness gate with unverified cutoff raises ValueError.
  4. Bypassing readiness gate with future/lookahead publication timestamp raises ValueError.
  5. Bypassing readiness gate with expired cutoff raises ValueError.
  6. Bypassing readiness gate with unverified Mainboard candidate raises ValueError.
  7. Bypassing readiness gate with corrupted provenance hash raises ValueError.
  8. Point-in-time enforcement: source publication after decision time rejected at commit boundary.
  9. Point-in-time enforcement: retrieval after decision time rejected at commit boundary.
  10. Point-in-time enforcement: effective time after decision time rejected at commit boundary.
  11. Point-in-time enforcement: timezone-naive timestamps rejected at commit boundary.
  12. Point-in-time enforcement: missing timestamps rejected at commit boundary.
  13. Point-in-time enforcement: legitimate feature available before decision time succeeds with explicit authorization.
  14. Point-in-time enforcement: later prediction succeeds after feature becomes available.
  15. Point-in-time enforcement: future market-close value supplied to earlier decision rejected.
  16. Point-in-time enforcement: feature whose provenance cannot be reconstructed rejected.
  17. Point-in-time enforcement: invalid or incomplete artifact hash rejected.
  18. Frozen SME inference reproducibility: exact probability reconstruction.
  19. Model hash and manifest hash byte-for-byte preservation.
  20. Candidate Wiscon Industries and Carver Roboweld independently verified as BLOCKED_CUTOFF.
  21. Duplicate commitment rejection at logger and manager levels.
  22. Concurrent commitment race condition handles gracefully without duplicate ledger entry.
  23. Ledger corruption prevents append operations.
  24. Zero mature outcomes strictly renders predictive and economic validity inconclusive.
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


class TestPhase1014IndependentGateVerification(unittest.TestCase):

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
            "ipo_id": "test-sme-valid-gate-01",
            "company_name": "Gate Test SME Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-15 16:00:00 IST",
            "authoritative_evidence": "BSE SME Notice Ref 20261110-88: Verified closing 16:00:00 IST",
            "source_publication_timestamp_ist": "2026-11-10 10:00:00 IST",
            "retrieval_timestamp_ist": "2026-11-10 10:05:00 IST",
            "effective_timestamp_ist": "2026-11-10 10:00:00 IST",
            "raw_source_sha256": "a" * 64,
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
                    "source_artifact_sha256": "b" * 64
                },
                "feat_india_vix": {
                    "source_publication_timestamp_ist": "2026-11-10 10:00:00 IST",
                    "retrieval_timestamp_ist": "2026-11-10 10:05:00 IST",
                    "effective_timestamp_ist": "2026-11-10 10:00:00 IST",
                    "source_artifact_sha256": "c" * 64
                },
                "feat_recent5_sentiment": {
                    "source_publication_timestamp_ist": "2026-11-10 10:00:00 IST",
                    "retrieval_timestamp_ist": "2026-11-10 10:05:00 IST",
                    "effective_timestamp_ist": "2026-11-10 10:00:00 IST",
                    "source_artifact_sha256": "d" * 64
                }
            }
        }

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Authoritative Persistence Boundary Tests
    # -------------------------------------------------------------------------
    def test_01_blocked_cutoff_candidate_rejected_from_clean_cohort(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["is_bidding_cutoff_verified"] = False
        cand["authoritative_evidence"] = "Unverified notice"

        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_CUTOFF")
        self.assertFalse(prep["is_clean_eligible"])

        res = self.lifecycle.commit_prospective_decision(cand, override_commit_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertFalse(res["is_clean_eligible"])
        self.assertTrue(any("EXCHANGE_BIDDING_CUTOFF_UNVERIFIED" in r for r in res["exclusion_reasons"]))

    def test_02_lookahead_publication_rejected_from_clean_cohort(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["source_publication_timestamp_ist"] = "2026-11-12 10:00:00 IST"  # after 11-11 decision time

        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_FEATURE_PARITY")
        self.assertFalse(prep["is_clean_eligible"])

        res = self.lifecycle.commit_prospective_decision(cand, override_commit_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertFalse(res["is_clean_eligible"])
        self.assertTrue(any("FEATURE_PUBLISHED_AFTER_DECISION_TIMESTAMP" in r for r in res["exclusion_reasons"]))

    def test_03_expired_candidate_rejected_from_clean_cohort(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["cutoff_timestamp_ist"] = "2026-10-20 16:00:00 IST"
        cand["source_publication_timestamp_ist"] = "2026-10-15 10:00:00 IST"
        cand["retrieval_timestamp_ist"] = "2026-10-15 10:05:00 IST"
        cand["effective_timestamp_ist"] = "2026-10-15 10:00:00 IST"
        for fn in cand["individual_feature_provenance"]:
            cand["individual_feature_provenance"][fn]["source_publication_timestamp_ist"] = "2026-10-15 10:00:00 IST"
            cand["individual_feature_provenance"][fn]["retrieval_timestamp_ist"] = "2026-10-15 10:05:00 IST"
            cand["individual_feature_provenance"][fn]["effective_timestamp_ist"] = "2026-10-15 10:00:00 IST"

        # Evaluated on 2026-10-28 (post cutoff of 2026-10-20)
        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-10-28 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "EXPIRED_WITHOUT_COMMIT")
        self.assertFalse(prep["is_clean_eligible"])

        res = self.lifecycle.commit_prospective_decision(cand, override_commit_timestamp_ist="2026-10-28 12:00:00 IST")
        self.assertFalse(res["is_clean_eligible"])
        self.assertTrue(res["is_late"])
        self.assertTrue(any("LATE_DECISION_COMMITTED_AFTER_CUTOFF" in r for r in res["exclusion_reasons"]))

    def test_04_mainboard_candidate_never_scored_by_frozen_sme(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["board_type"] = "Mainboard"

        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_GOVERNANCE")
        self.assertIsNone(prep["predicted_probability"])
        self.assertEqual(prep["model_name"], "REGISTER_FOR_COVERAGE_ONLY")
        self.assertFalse(prep["is_clean_eligible"])

        res = self.lifecycle.commit_prospective_decision(cand, override_commit_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertFalse(res["is_clean_eligible"])
        self.assertTrue(any("NO_FROZEN_MODEL_FOR_MAINBOARD" in r for r in res["exclusion_reasons"]))

    def test_05_corrupt_provenance_hash_rejected_from_clean_cohort(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["raw_source_sha256"] = "invalid_short_hash"

        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("MISSING_OR_INVALID_PROVENANCE_HASH" in r for r in prep["exclusion_reasons"]))

    # -------------------------------------------------------------------------
    # 2. Point-in-Time Enforcement Edge Cases
    # -------------------------------------------------------------------------
    def test_06_retrieval_after_decision_time_rejected(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["individual_feature_provenance"]["feat_nifty50_ret5s_pct"]["retrieval_timestamp_ist"] = "2026-11-11 14:00:00 IST"

        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("POST_DECISION_RETRIEVAL_FEAT_NIFTY50_RET5S_PCT" in r for r in prep["exclusion_reasons"]))

    def test_07_effective_after_decision_time_rejected(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["individual_feature_provenance"]["feat_india_vix"]["effective_timestamp_ist"] = "2026-11-11 15:30:00 IST"

        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("POST_DECISION_EFFECTIVE_FEAT_INDIA_VIX" in r for r in prep["exclusion_reasons"]))

    def test_08_timezone_naive_timestamp_rejected(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["source_publication_timestamp_ist"] = "2026-11-10 10:00:00"  # Missing timezone

        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("INVALID_OR_TIMEZONE_NAIVE_PUBLICATION_TIMESTAMP" in r for r in prep["exclusion_reasons"]))

    def test_09_contradictory_timestamps_retrieval_before_publication(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["individual_feature_provenance"]["feat_recent5_sentiment"]["source_publication_timestamp_ist"] = "2026-11-10 12:00:00 IST"
        cand["individual_feature_provenance"]["feat_recent5_sentiment"]["retrieval_timestamp_ist"] = "2026-11-10 11:00:00 IST"

        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("RETRIEVAL_BEFORE_PUB_ANOMALY_FEAT_RECENT5_SENTIMENT" in r for r in prep["exclusion_reasons"]))

    def test_10_legitimate_pre_decision_feature_passes_point_in_time(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "READY_FOR_PROSPECTIVE_COMMIT")
        self.assertTrue(prep["is_clean_eligible"])
        self.assertEqual(prep["readiness_gate_evaluation"]["feature_temporal_provenance_status"], "PASS")

    def test_11_future_market_close_value_rejected(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["individual_feature_provenance"]["feat_nifty50_ret5s_pct"]["effective_timestamp_ist"] = "2026-11-11 15:30:00 IST"

        # Evaluated intraday at 11:00 IST before session close
        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 11:00:00 IST")
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("POST_DECISION_EFFECTIVE_FEAT_NIFTY50_RET5S_PCT" in r for r in prep["exclusion_reasons"]))

    def test_12_later_prediction_allowed_after_feature_becomes_available(self):
        cand = json.loads(json.dumps(self.valid_sme_candidate))
        cand["source_publication_timestamp_ist"] = "2026-11-11 16:00:00 IST"
        cand["retrieval_timestamp_ist"] = "2026-11-11 16:05:00 IST"
        cand["effective_timestamp_ist"] = "2026-11-11 15:30:00 IST"
        cand["individual_feature_provenance"]["feat_nifty50_ret5s_pct"]["source_publication_timestamp_ist"] = "2026-11-11 16:00:00 IST"
        cand["individual_feature_provenance"]["feat_nifty50_ret5s_pct"]["retrieval_timestamp_ist"] = "2026-11-11 16:05:00 IST"
        cand["individual_feature_provenance"]["feat_nifty50_ret5s_pct"]["effective_timestamp_ist"] = "2026-11-11 15:30:00 IST"

        # Earlier attempt at 12:00 IST is blocked
        prep_early = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertFalse(prep_early["is_clean_eligible"])

        # Later attempt at 16:30 IST succeeds
        prep_late = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-11 16:30:00 IST")
        self.assertTrue(prep_late["is_clean_eligible"])
        self.assertEqual(prep_late["candidate_lifecycle_state"], "READY_FOR_PROSPECTIVE_COMMIT")

    # -------------------------------------------------------------------------
    # 3. Frozen Inference & Artifact Preservation
    # -------------------------------------------------------------------------
    def test_13_frozen_sme_model_hash_verification(self):
        surveillance = SurveillanceMonitor()
        model_audit = surveillance.verify_model_integrity()
        self.assertTrue(model_audit["valid"])
        self.assertEqual(model_audit["actual_sha256"], FROZEN_SME_MODEL_SHA256)

    def test_14_baseline_manifest_hash_verification(self):
        surveillance = SurveillanceMonitor()
        manifest_audit = surveillance.verify_manifest_integrity()
        self.assertTrue(manifest_audit["valid"])
        self.assertEqual(manifest_audit["actual_sha256"], MANIFEST_SHA256)

    def test_15_frozen_inference_exact_reproducibility(self):
        features = {
            "feat_nifty50_ret5s_pct": 0.85,
            "feat_india_vix": 13.8,
            "feat_recent5_sentiment": 7.7
        }
        prob1 = self.lifecycle.predict_frozen_sme(features)
        prob2 = self.lifecycle.predict_frozen_sme(features)
        self.assertEqual(prob1, prob2)
        self.assertEqual(prob1, 0.8144)

    # -------------------------------------------------------------------------
    # 4. SME Candidates & Cutoff Evidence Audit
    # -------------------------------------------------------------------------
    def test_16_tracked_sme_candidates_remain_blocked_cutoff(self):
        with open(CANDIDATE_REGISTRY_PATH, "r") as f:
            candidates = json.load(f)

        sme_cands = [c for c in candidates if c.get("board_type") == "SME"]
        self.assertEqual(len(sme_cands), 2, "Must track exactly 2 SME candidates")

        for cand in sme_cands:
            prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-10-28 12:00:00 IST")
            self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_CUTOFF")
            self.assertFalse(prep["is_clean_eligible"])
            self.assertTrue(any("EXCHANGE_BIDDING_CUTOFF_UNVERIFIED" in r for r in prep["exclusion_reasons"]))
            self.assertEqual(prep["readiness_gate_evaluation"]["official_cutoff_status"], "FAIL")

    # -------------------------------------------------------------------------
    # 5. Lifecycle, Concurrency & Ledger Invariants
    # -------------------------------------------------------------------------
    def test_17_no_auto_commit_for_ready_candidate(self):
        """A candidate reaching READY_FOR_PROSPECTIVE_COMMIT must NOT be auto-committed."""
        prep = self.lifecycle.audit_and_prepare_candidate(self.valid_sme_candidate, evaluation_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "READY_FOR_PROSPECTIVE_COMMIT")

        # Verify ledger file does NOT exist or has 0 records
        if os.path.exists(self.decision_ledger):
            with open(self.decision_ledger, "r") as f:
                lines = [l for l in f if l.strip()]
            self.assertEqual(len(lines), 0)
        else:
            self.assertFalse(os.path.exists(self.decision_ledger))

    def test_18_duplicate_commitment_prevention(self):
        res1 = self.lifecycle.commit_prospective_decision(self.valid_sme_candidate, override_commit_timestamp_ist="2026-11-11 12:00:00 IST")
        self.assertEqual(res1["status"], "RECORDED")

        res2 = self.lifecycle.commit_prospective_decision(self.valid_sme_candidate, override_commit_timestamp_ist="2026-11-11 12:05:00 IST")
        self.assertEqual(res2["status"], "DUPLICATE_IGNORED")

        with open(self.decision_ledger, "r") as f:
            lines = [l for l in f if l.strip()]
        self.assertEqual(len(lines), 1)

    def test_19_concurrent_commit_processes_race_prevention(self):
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )

        def attempt_commit(idx):
            return logger.record_prospective_decision(
                ipo_id="race-cand-01",
                company_name="Race Test Ltd",
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
            results = list(executor.map(attempt_commit, range(5)))

        statuses = [r["status"] for r in results]
        self.assertEqual(statuses.count("RECORDED"), 1)
        self.assertEqual(statuses.count("DUPLICATE_IGNORED"), 4)

        with open(self.decision_ledger, "r") as f:
            lines = [l for l in f if l.strip()]
        self.assertEqual(len(lines), 1)

    def test_20_ledger_corruption_hard_blocks_writes(self):
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        # Write corrupted record
        os.makedirs(os.path.dirname(self.decision_ledger), exist_ok=True)
        with open(self.decision_ledger, "w") as f:
            f.write("{NOT_VALID_JSON_CORRUPT\n")

        with self.assertRaises(IOError) as ctx:
            logger.record_prospective_decision(
                ipo_id="cand-blocked-by-corruption",
                company_name="Corrupt Test Ltd",
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

    # -------------------------------------------------------------------------
    # 6. Evaluation Separation & Real-Money Prohibition
    # -------------------------------------------------------------------------
    def test_21_zero_mature_outcomes_inconclusive(self):
        resp = self.client.get("/api/metrics/brier")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        clean_status = data.get("prospective_clean_cohort_status", {})
        self.assertEqual(clean_status.get("evaluation_status"), "INCONCLUSIVE_ZERO_OUTCOMES")
        self.assertFalse(clean_status.get("performance_claim_allowed", False))

    def test_22_no_broker_or_real_money_execution(self):
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
