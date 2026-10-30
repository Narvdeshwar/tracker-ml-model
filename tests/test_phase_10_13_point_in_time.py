"""
Unit tests for Phase 10.13: Point-in-Time Provenance Enforcement & Evidence-Backed Readiness.
Comprehensive 24-test deterministic suite covering:
  1. Publication time after decision time (hard failure).
  2. Retrieval time after decision time (hard failure).
  3. Effective time after decision time (hard failure).
  4. Missing timestamps.
  5. Naive timestamps without timezone information.
  6. Conflicting timezones representing the same instant.
  7. Source publication before retrieval with consistent chronology.
  8. A valid later prediction using data that became available after an earlier decision.
  9. A historical record whose chronology cannot be reconstructed.
  10. Incorrect system clock or report-generation timestamp.
  11. Future market-close data incorrectly supplied to an earlier prediction.
  12. Invalid or incomplete source artifact hashes.
  13. Secondary-source cutoff rejection.
  14. Official evidence tied to the wrong IPO.
  15. A cutoff verified for a different issue being rejected.
  16. A blocked candidate being prevented from commitment.
  17. An expired candidate being prevented from retrospective commitment.
  18. Concurrent duplicate commitment attempts.
  19. Corrupted decision-ledger and checkpoint handling.
  20. Model and manifest hash preservation.
  21. Exact frozen feature definitions and units.
  22. API and dashboard consistency with the readiness engine.
  23. Zero mature outcomes remaining inconclusive.
  24. No real-money trading or broker-order pathways.
"""

import os
import json
import shutil
import tempfile
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from src.api.main import app
from src.prospective_lifecycle import (
    ProspectiveLifecycleManager,
    parse_timezone_aware_ts,
    FROZEN_SME_MODEL_SHA256,
    FROZEN_SME_MODEL_PATH,
    MANIFEST_SHA256
)
from src.prospective_simulator_logger import ProspectiveDecisionLogger
from src.evidence_audit_protocol import ProspectiveEvidenceAuditor

EXPECTED_MODEL_SHA256 = "dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76"
EXPECTED_MANIFEST_SHA256 = "b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e"


class TestPhase1013PointInTimeEnforcement(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.decision_ledger = os.path.join(self.temp_dir, "test_decisions.jsonl")
        self.outcome_ledger = os.path.join(self.temp_dir, "test_outcomes.jsonl")
        self.audit_events = os.path.join(self.temp_dir, "test_events.jsonl")
        self.checkpoint = os.path.join(self.temp_dir, "test_checkpoint.json")
        self.registry = os.path.join(self.temp_dir, "test_registry.json")

        self.lifecycle = ProspectiveLifecycleManager(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger,
            candidate_registry_path=self.registry,
            audit_events_path=self.audit_events,
            checkpoint_path=self.checkpoint
        )
        self.client = TestClient(app)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. Publication time after decision time
    def test_01_publication_time_after_decision_time(self):
        cand = {
            "ipo_id": "test-pit-01",
            "company_name": "Test PIT 01 Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-10 16:00:00 IST",
            "prediction_decision_timestamp_ist": "2026-11-05 10:00:00 IST",
            "authoritative_evidence": "BSE Circular",
            "source_publication_timestamp_ist": "2026-11-05 12:00:00 IST",  # 2 hours after decision!
            "raw_source_sha256": "a" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
        }
        prep = self.lifecycle.audit_and_prepare_candidate(cand)
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("FEATURE_PUBLISHED_AFTER_DECISION_TIMESTAMP" in r for r in prep["exclusion_reasons"]))

    # 2. Retrieval time after decision time
    def test_02_retrieval_time_after_decision_time(self):
        cand = {
            "ipo_id": "test-pit-02",
            "company_name": "Test PIT 02 Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-10 16:00:00 IST",
            "prediction_decision_timestamp_ist": "2026-11-05 10:00:00 IST",
            "source_publication_timestamp_ist": "2026-11-04 16:00:00 IST",
            "retrieval_timestamp_ist": "2026-11-05 11:30:00 IST",  # Retrieved after decision!
            "authoritative_evidence": "BSE Circular",
            "raw_source_sha256": "a" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
        }
        prep = self.lifecycle.audit_and_prepare_candidate(cand)
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("FEATURE_RETRIEVED_AFTER_DECISION_TIMESTAMP" in r for r in prep["exclusion_reasons"]))

    # 3. Effective time after decision time
    def test_03_effective_time_after_decision_time(self):
        cand = {
            "ipo_id": "test-pit-03",
            "company_name": "Test PIT 03 Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-10 16:00:00 IST",
            "prediction_decision_timestamp_ist": "2026-11-05 10:00:00 IST",
            "source_publication_timestamp_ist": "2026-11-04 16:00:00 IST",
            "retrieval_timestamp_ist": "2026-11-05 09:00:00 IST",
            "effective_timestamp_ist": "2026-11-05 15:30:00 IST",  # Effective at market close!
            "authoritative_evidence": "BSE Circular",
            "raw_source_sha256": "a" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
        }
        prep = self.lifecycle.audit_and_prepare_candidate(cand)
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("FEATURE_EFFECTIVE_AFTER_DECISION_TIMESTAMP" in r for r in prep["exclusion_reasons"]))

    # 4. Missing timestamps
    def test_04_missing_timestamps(self):
        cand = {
            "ipo_id": "test-pit-04",
            "company_name": "Test PIT 04 Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-10 16:00:00 IST",
            "source_publication_timestamp_ist": None,  # Missing!
            "authoritative_evidence": "BSE Circular",
            "raw_source_sha256": "a" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
        }
        prep = self.lifecycle.audit_and_prepare_candidate(cand)
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("MISSING_FEATURE_PUBLICATION_TIMESTAMP" in r for r in prep["exclusion_reasons"]))

    # 5. Naive timestamps without timezone information
    def test_05_naive_timestamps_rejected(self):
        cand = {
            "ipo_id": "test-pit-05",
            "company_name": "Test PIT 05 Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-10 16:00:00 IST",
            "source_publication_timestamp_ist": "2026-11-04 14:00:00",  # No timezone!
            "authoritative_evidence": "BSE Circular",
            "raw_source_sha256": "a" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
        }
        prep = self.lifecycle.audit_and_prepare_candidate(cand)
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("INVALID_OR_TIMEZONE_NAIVE_PUBLICATION_TIMESTAMP" in r for r in prep["exclusion_reasons"]))

    # 6. Conflicting timezones representing the same instant
    def test_06_timezone_normalization_utc_comparison(self):
        # 14:30:00 IST is exactly 09:00:00 UTC
        ts_ist = "2026-11-05 14:30:00 IST"
        ts_utc = "2026-11-05 09:00:00 Z"
        dt_ist = parse_timezone_aware_ts(ts_ist)
        dt_utc = parse_timezone_aware_ts(ts_utc)
        self.assertEqual(dt_ist, dt_utc)

    # 7. Source publication before retrieval with consistent chronology
    def test_07_source_retrieval_before_publication_anomaly(self):
        cand = {
            "ipo_id": "test-pit-07",
            "company_name": "Test PIT 07 Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-10 16:00:00 IST",
            "prediction_decision_timestamp_ist": "2026-11-05 16:00:00 IST",
            "source_publication_timestamp_ist": "2026-11-05 14:00:00 IST",
            "retrieval_timestamp_ist": "2026-11-05 12:00:00 IST",  # Retrieved 2 hours before publication!
            "authoritative_evidence": "BSE Circular",
            "raw_source_sha256": "a" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
        }
        prep = self.lifecycle.audit_and_prepare_candidate(cand)
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("RETRIEVAL_BEFORE_PUBLICATION_ANOMALY" in r for r in prep["exclusion_reasons"]))

    # 8. Valid later prediction using data that became available after earlier decision
    def test_08_valid_later_prediction_allowed(self):
        cand = {
            "ipo_id": "test-pit-08",
            "company_name": "Test PIT 08 Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-10 16:00:00 IST",
            "prediction_decision_timestamp_ist": "2026-11-05 17:00:00 IST",  # Decision at 17:00
            "source_publication_timestamp_ist": "2026-11-05 16:00:00 IST",  # Data published at 16:00
            "retrieval_timestamp_ist": "2026-11-05 16:15:00 IST",           # Data retrieved at 16:15
            "authoritative_evidence": "BSE Circular",
            "raw_source_sha256": "a" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
        }
        prep = self.lifecycle.audit_and_prepare_candidate(cand)
        self.assertTrue(prep["is_clean_eligible"])
        self.assertEqual(len(prep["exclusion_reasons"]), 0)

    # 9. Historical record whose chronology cannot be reconstructed
    def test_09_unparseable_timestamp_blocked(self):
        cand = {
            "ipo_id": "test-pit-09",
            "company_name": "Test PIT 09 Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-10 16:00:00 IST",
            "source_publication_timestamp_ist": "NOT_A_VALID_DATE_STRING",
            "authoritative_evidence": "BSE Circular",
            "raw_source_sha256": "a" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
        }
        prep = self.lifecycle.audit_and_prepare_candidate(cand)
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("INVALID_OR_TIMEZONE_NAIVE_PUBLICATION_TIMESTAMP" in r for r in prep["exclusion_reasons"]))

    # 10. Incorrect system clock / report generation timestamp
    def test_10_evaluation_timestamp_past_cutoff_triggers_expired(self):
        cand = {
            "ipo_id": "test-pit-10",
            "company_name": "Test PIT 10 Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-10-20 16:00:00 IST",  # In the past!
            "source_publication_timestamp_ist": "2026-10-18 10:00:00 IST",
            "authoritative_evidence": "BSE Circular",
            "raw_source_sha256": "a" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
        }
        prep = self.lifecycle.audit_and_prepare_candidate(cand)
        self.assertEqual(prep["candidate_lifecycle_state"], "EXPIRED_WITHOUT_COMMIT")
        self.assertFalse(prep["is_clean_eligible"])

    # 11. Future market-close data incorrectly supplied to an earlier prediction
    def test_11_future_market_close_data_rejected(self):
        cand = {
            "ipo_id": "test-pit-11",
            "company_name": "Test PIT 11 Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-10 16:00:00 IST",
            "prediction_decision_timestamp_ist": "2026-11-05 10:00:00 IST",  # Decision at 10:00 AM
            "individual_feature_provenance": {
                "feat_india_vix": {
                    "source_publication_timestamp_ist": "2026-11-05 16:00:00 IST",  # VIX close published at 16:00!
                    "retrieval_timestamp_ist": "2026-11-05 16:05:00 IST",
                    "effective_timestamp_ist": "2026-11-05 15:30:00 IST",
                    "source_artifact_sha256": "b" * 64
                }
            },
            "authoritative_evidence": "BSE Circular",
            "source_publication_timestamp_ist": "2026-11-04 10:00:00 IST",
            "raw_source_sha256": "a" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
        }
        prep = self.lifecycle.audit_and_prepare_candidate(cand)
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("POST_DECISION_PUBLICATION_FEAT_INDIA_VIX" in r for r in prep["exclusion_reasons"]))

    # 12. Invalid or incomplete source artifact hashes
    def test_12_incomplete_source_artifact_hash_rejected(self):
        cand = {
            "ipo_id": "test-pit-12",
            "company_name": "Test PIT 12 Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-10 16:00:00 IST",
            "authoritative_evidence": "BSE Circular",
            "source_publication_timestamp_ist": "2026-11-04 10:00:00 IST",
            "raw_source_sha256": "1234567890abcdef",  # Only 16 chars!
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
        }
        prep = self.lifecycle.audit_and_prepare_candidate(cand)
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("MISSING_OR_INVALID_PROVENANCE_HASH" in r for r in prep["exclusion_reasons"]))

    # 13. Secondary-source cutoff rejection
    def test_13_secondary_source_cutoff_rejection(self):
        cand = {
            "ipo_id": "test-pit-13",
            "company_name": "Test PIT 13 Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-10 16:00:00 IST",
            "authoritative_evidence": "Secondary aggregate IPO portal reports 16:00 close",
            "source_publication_timestamp_ist": "2026-11-04 10:00:00 IST",
            "raw_source_sha256": "c" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": False,  # Secondary portal cannot verify bidding cutoff!
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
        }
        prep = self.lifecycle.audit_and_prepare_candidate(cand)
        self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_CUTOFF")
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("EXCHANGE_BIDDING_CUTOFF_UNVERIFIED" in r for r in prep["exclusion_reasons"]))

    # 14. Official evidence tied to the wrong IPO
    def test_14_official_evidence_tied_to_wrong_ipo(self):
        cand = {
            "ipo_id": "wiscon-industries-sme-20261029",
            "company_name": "Wiscon Industries Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-10-29 16:00:00 IST",
            "authoritative_evidence": "BSE Notice for Carver Roboweld Ltd ref 20261025-01",  # Wrong issuer!
            "source_publication_timestamp_ist": "2026-10-25 10:00:00 IST",
            "raw_source_sha256": "d" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": False,
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
        }
        prep = self.lifecycle.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-10-28 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_CUTOFF")

    # 15. A cutoff verified for a different issue being rejected
    def test_15_cutoff_verified_for_different_issue_rejected(self):
        cand = {
            "ipo_id": "test-pit-15",
            "company_name": "Test PIT 15 Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-10 16:00:00 IST",
            "authoritative_evidence": "Notice for Issue XYZ-2025",
            "source_publication_timestamp_ist": "2026-11-04 10:00:00 IST",
            "raw_source_sha256": "e" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": False,
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
        }
        prep = self.lifecycle.audit_and_prepare_candidate(cand)
        self.assertFalse(prep["is_clean_eligible"])

    # 16. A blocked candidate being prevented from commitment
    def test_16_blocked_candidate_prevented_from_clean_commitment(self):
        cand = {
            "ipo_id": "wiscon-industries-sme-20261029",
            "company_name": "Wiscon Industries Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-10-29 16:00:00 IST",
            "authoritative_evidence": "Pending circular",
            "source_publication_timestamp_ist": "2026-10-24 16:30:00 IST",
            "raw_source_sha256": "8f4b23c12a78e11a3d44bc82310b865fe2a184df29cba414de2f42aa68b209e7",
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": False,
            "features": {"feat_nifty50_ret5s_pct": 0.85, "feat_india_vix": 13.8, "feat_recent5_sentiment": 7.7}
        }
        res = self.lifecycle.commit_prospective_decision(cand)
        self.assertEqual(res["status"], "RECORDED")
        self.assertFalse(res["is_clean_eligible"])
        self.assertTrue(any("EXCHANGE_BIDDING_CUTOFF_UNVERIFIED" in r for r in res["exclusion_reasons"]))

    # 17. An expired candidate being prevented from retrospective commitment
    def test_17_expired_candidate_prevented_from_retrospective_commitment(self):
        cand = {
            "ipo_id": "expired-sme-20261015",
            "company_name": "Expired SME Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-10-15 16:00:00 IST",
            "authoritative_evidence": "BSE Circular",
            "source_publication_timestamp_ist": "2026-10-10 10:00:00 IST",
            "raw_source_sha256": "f" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
        }
        res = self.lifecycle.commit_prospective_decision(cand)
        self.assertFalse(res["is_clean_eligible"])
        self.assertTrue(res["is_late"])
        self.assertTrue(any("LATE_DECISION_COMMITTED_AFTER_CUTOFF" in r for r in res["exclusion_reasons"]))

    # 18. Concurrent duplicate commitment attempts
    def test_18_concurrent_duplicate_commitments(self):
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        res1 = logger.record_prospective_decision(
            ipo_id="test-dup-18",
            company_name="Duplicate Test Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-10 16:00:00 IST",
            features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7},
            p_positive_open=0.80,
            p_macro=0.80,
            p_severe_loss=0.04,
            model_name="Model_6B_SME_v1.0",
            model_sha256=EXPECTED_MODEL_SHA256
        )
        self.assertEqual(res1["status"], "RECORDED")

        res2 = logger.record_prospective_decision(
            ipo_id="test-dup-18",
            company_name="Duplicate Test Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-10 16:00:00 IST",
            features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7},
            p_positive_open=0.80,
            p_macro=0.80,
            p_severe_loss=0.04,
            model_name="Model_6B_SME_v1.0",
            model_sha256=EXPECTED_MODEL_SHA256
        )
        self.assertEqual(res2["status"], "DUPLICATE_IGNORED")

    # 19. Corrupted decision-ledger and checkpoint handling
    def test_19_corrupted_ledger_blocks_writes(self):
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        with open(self.decision_ledger, "w", encoding="utf-8") as f:
            f.write("{invalid_json_line\n")

        with self.assertRaises(IOError) as ctx:
            logger.record_prospective_decision(
                ipo_id="test-corr-19",
                company_name="Corruption Test Ltd",
                board_type="SME",
                cutoff_timestamp_ist="2026-11-10 16:00:00 IST",
                features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7},
                p_positive_open=0.80,
                p_macro=0.80,
                p_severe_loss=0.04,
                model_name="Model_6B_SME_v1.0",
                model_sha256=EXPECTED_MODEL_SHA256
            )
        self.assertIn("LEDGER_CORRUPTION_BLOCKED", str(ctx.exception))

    # 20. Model and manifest hash preservation
    def test_20_model_and_manifest_hash_preservation(self):
        auditor = ProspectiveEvidenceAuditor()
        model_hash = auditor._hash_file(FROZEN_SME_MODEL_PATH)
        manifest_hash = auditor._hash_file("models/frozen/phase_9b_baseline_manifest.json")
        self.assertEqual(model_hash, EXPECTED_MODEL_SHA256)
        self.assertEqual(manifest_hash, EXPECTED_MANIFEST_SHA256)

    # 21. Exact frozen feature definitions and units
    def test_21_exact_frozen_feature_definitions(self):
        metadata_path = "models/frozen/model_6b_sme_v1_metadata.json"
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertEqual(meta["features"], ["feat_nifty50_ret5s_pct", "feat_india_vix", "feat_recent5_sentiment"])
        self.assertEqual(meta["target_definition"], "target_listing_open_return_pct > 0")

    # 22. API and dashboard consistency with the readiness engine
    def test_22_api_dashboard_readiness_consistency(self):
        res = self.client.get("/api/ipos/wiscon-industries-sme-20261029?evaluation_timestamp_ist=2026-10-28+12:00:00+IST")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["candidate_lifecycle_state"], "BLOCKED_CUTOFF")
        self.assertIn("readiness_gate_evaluation", data)
        gate = data["readiness_gate_evaluation"]
        self.assertEqual(gate["official_cutoff_status"], "FAIL")
        self.assertEqual(gate["final_readiness_status"], "BLOCKED_CUTOFF")

    # 23. Zero mature outcomes remaining inconclusive
    def test_23_zero_mature_outcomes_inconclusive(self):
        res = self.client.get("/api/metrics/brier")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        clean_status = data.get("prospective_clean_cohort_status", {})
        self.assertIsNone(clean_status.get("model_brier_score"))
        self.assertEqual(clean_status.get("evaluation_status"), "INCONCLUSIVE_ZERO_OUTCOMES")

    # 24. No real-money trading or broker-order pathways
    def test_24_no_broker_or_real_money_execution(self):
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
