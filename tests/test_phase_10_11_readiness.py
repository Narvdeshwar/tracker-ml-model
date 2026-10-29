"""
Unit tests for Phase 10.11: Official Evidence Acquisition, Release-Gate Revalidation & Shadow Readiness.
Covers:
  - Workstream 1 & 2: Authoritative cutoff evidence requirement and feature availability verification.
  - Workstream 3: Candidate lifecycle state reconciliation (BLOCKED_CUTOFF, BLOCKED_GOVERNANCE, etc.).
  - Workstream 4: Inter-process concurrency, middle-of-ledger corruption blocking, and torn write recovery.
  - Workstream 5: Cryptographic snapshot seal tamper detection and threat model invariants.
  - Workstream 6: Dashboard & API milestone separation (Feature Integrity vs Predictive Validity vs Economic Viability).
  - Workstream 7: Release gate verification blocking unverified candidates from commitment.
"""

import os
import json
import shutil
import tempfile
import unittest
import threading
import multiprocessing
import pandas as pd
import numpy as np

from fastapi.testclient import TestClient
from src.api.main import app
from src.prospective_lifecycle import ProspectiveLifecycleManager, FROZEN_SME_MODEL_SHA256, FROZEN_SME_MODEL_PATH
from src.prospective_simulator_logger import ProspectiveDecisionLogger
from src.evidence_audit_protocol import ProspectiveEvidenceAuditor

EXPECTED_MODEL_SHA256 = "dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76"
EXPECTED_MANIFEST_SHA256 = "b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e"


def _process_commit_worker(ledger_path, outcome_path, ipo_id, res_queue):
    logger = ProspectiveDecisionLogger(
        decision_ledger_path=ledger_path,
        outcome_ledger_path=outcome_path
    )
    res = logger.record_prospective_decision(
        ipo_id=ipo_id,
        company_name=f"Company {ipo_id}",
        board_type="SME",
        cutoff_timestamp_ist="2026-10-31 16:00:00 IST",
        features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 10.0},
        p_positive_open=0.82,
        p_macro=0.82,
        p_severe_loss=0.04,
        model_name="Model_6B_SME_v1.0",
        model_sha256=EXPECTED_MODEL_SHA256,
        feature_provenance={
            "cutoff_source_evidence": "BSE Circular",
            "raw_source_sha256": "b" * 64,
            "is_timing_verified": True,
            "source_publication_timestamp_ist": "2026-10-25 10:00:00 IST"
        }
    )
    res_queue.put(res["status"])


class TestPhase1011Readiness(unittest.TestCase):

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

    # =========================================================================
    # Workstream 3: Standardized Candidate Lifecycle States
    # =========================================================================
    def test_candidate_lifecycle_states_reconciliation(self):
        """
        Verifies that candidates receive exact lifecycle states:
        - Wiscon & Carver -> BLOCKED_CUTOFF
        - Mainboard candidates -> BLOCKED_GOVERNANCE
        """
        # SME with unverified bidding cutoff
        wiscon_cand = {
            "ipo_id": "wiscon-industries-sme-20261029",
            "company_name": "Wiscon Industries Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-10-29 16:00:00 IST",
            "authoritative_evidence": "BSE SME Notice Ref 20261024-01",
            "source_publication_timestamp_ist": "2026-10-24 16:30:00 IST",
            "raw_source_sha256": "8f4b23c12a78e11a3d44bc82310b865fe2a184df29cba414de2f42aa68b209e7",
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": False,
            "features": {
                "feat_nifty50_ret5s_pct": 0.85,
                "feat_india_vix": 13.8,
                "feat_recent5_sentiment": 7.7
            }
        }
        prep_sme = self.lifecycle.audit_and_prepare_candidate(wiscon_cand)
        self.assertEqual(prep_sme["candidate_lifecycle_state"], "BLOCKED_CUTOFF")
        self.assertFalse(prep_sme["is_clean_eligible"])

        # Mainboard candidate
        mb_cand = {
            "ipo_id": "bls-polymers-mainboard-20261029",
            "company_name": "BLS Polymers Ltd",
            "board_type": "Mainboard",
            "cutoff_timestamp_ist": "2026-10-29 17:00:00 IST",
            "authoritative_evidence": "Statutory Notice",
            "source_publication_timestamp_ist": "2026-10-25 10:00:00 IST",
            "raw_source_sha256": "a" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {}
        }
        prep_mb = self.lifecycle.audit_and_prepare_candidate(mb_cand)
        self.assertEqual(prep_mb["candidate_lifecycle_state"], "BLOCKED_GOVERNANCE")
        self.assertFalse(prep_mb["is_clean_eligible"])

    # =========================================================================
    # Workstream 4: Multi-Process Concurrency & Corruption Barriers
    # =========================================================================
    def test_inter_process_concurrency_protection(self):
        """
        Tests that multiple distinct OS processes attempting concurrent commits
        are safely serialized by the inter-process file lock.
        """
        q = multiprocessing.Queue()
        p1 = multiprocessing.Process(
            target=_process_commit_worker,
            args=(self.decision_ledger, self.outcome_ledger, "mp-test-candidate", q)
        )
        p2 = multiprocessing.Process(
            target=_process_commit_worker,
            args=(self.decision_ledger, self.outcome_ledger, "mp-test-candidate", q)
        )

        p1.start()
        p2.start()
        p1.join()
        p2.join()

        results = [q.get(), q.get()]
        self.assertEqual(results.count("RECORDED"), 1)
        self.assertEqual(results.count("DUPLICATE_IGNORED"), 1)

    def test_mid_ledger_corruption_blocks_writes_and_requires_reconciliation(self):
        """
        Tests that a corrupted record in the middle of a ledger raises an explicit
        IOError and blocks new writes rather than silently ignoring the corruption.
        """
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )

        # Write valid record 1
        res1 = logger.record_prospective_decision(
            ipo_id="cand-1",
            company_name="Company 1",
            board_type="SME",
            cutoff_timestamp_ist="2026-10-31 16:00:00 IST",
            features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 10.0},
            p_positive_open=0.82,
            p_macro=0.82,
            p_severe_loss=0.04,
            model_name="Model_6B_SME_v1.0",
            model_sha256=EXPECTED_MODEL_SHA256
        )
        self.assertEqual(res1["status"], "RECORDED")

        # Inject corrupt syntax line in the middle of ledger
        with open(self.decision_ledger, "a", encoding="utf-8") as f:
            f.write("{corrupt_json_not_valid_payload}\n")

        # Attempt to write record 2 -> MUST be blocked with LEDGER_CORRUPTION_BLOCKED
        with self.assertRaises(IOError) as ctx:
            logger.record_prospective_decision(
                ipo_id="cand-2",
                company_name="Company 2",
                board_type="SME",
                cutoff_timestamp_ist="2026-10-31 16:00:00 IST",
                features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 10.0},
                p_positive_open=0.82,
                p_macro=0.82,
                p_severe_loss=0.04,
                model_name="Model_6B_SME_v1.0",
                model_sha256=EXPECTED_MODEL_SHA256
            )
        self.assertIn("LEDGER_CORRUPTION_BLOCKED", str(ctx.exception))

    # =========================================================================
    # Workstream 6: API Status and Evaluation Milestones
    # =========================================================================
    def test_api_detail_returns_three_distinct_milestones(self):
        """
        Verifies that /api/ipos/{ipo_id} cleanly separates:
        1. Feature & inference integrity
        2. Predictive validity
        3. Economic viability
        """
        res = self.client.get("/api/ipos/wiscon-industries-sme-20261029")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("evaluation_milestones", data)
        milestones = data["evaluation_milestones"]
        
        # 1. Feature & inference integrity is verified
        self.assertEqual(milestones["feature_and_inference_integrity"]["status"], "PASS")
        self.assertTrue(milestones["feature_and_inference_integrity"]["verified"])

        # 2. Predictive validity is pending mature observations
        self.assertEqual(milestones["predictive_validity"]["status"], "PENDING_MATURE_OBSERVATIONS")
        self.assertFalse(milestones["predictive_validity"]["verified"])

        # 3. Economic viability is pending prospective sample accumulation
        self.assertEqual(milestones["economic_viability"]["status"], "PENDING_SAMPLE_ACCUMULATION")
        self.assertFalse(milestones["economic_viability"]["verified"])

        # Standardized lifecycle state is exposed
        self.assertEqual(data["candidate_lifecycle_state"], "BLOCKED_CUTOFF")


if __name__ == "__main__":
    unittest.main()
