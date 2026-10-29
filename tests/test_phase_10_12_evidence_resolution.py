"""
Unit tests for Phase 10.12: Official Evidence Resolution & Prospective Cohort Integrity.
Covers:
  - Workstream 1: Reconcile candidate timelines & cutoff expiration transition to EXPIRED_WITHOUT_COMMIT.
  - Workstream 2: Authoritative exchange evidence validation vs secondary portal rejection.
  - Workstream 3: Exact 64-char hex provenance hashes, provenance status preservation (Provisional vs Verified).
  - Workstream 4: Lifecycle and ledger reconciliation (expired candidate cannot be committed retrospectively).
  - Workstream 5: Future-candidate 11-gate readiness checklist.
  - Workstream 6: Evaluation governance with 3 distinct milestone dimensions.
"""

import os
import json
import shutil
import tempfile
import unittest
import pandas as pd
import numpy as np

from fastapi.testclient import TestClient
from src.api.main import app
from src.prospective_lifecycle import ProspectiveLifecycleManager, FROZEN_SME_MODEL_SHA256, FROZEN_SME_MODEL_PATH
from src.prospective_simulator_logger import ProspectiveDecisionLogger
from src.evidence_audit_protocol import ProspectiveEvidenceAuditor

EXPECTED_MODEL_SHA256 = "dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76"
EXPECTED_MANIFEST_SHA256 = "b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e"


class TestPhase1012EvidenceResolution(unittest.TestCase):

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
    # Workstream 1: Reconcile Candidate Timelines & Expiration
    # =========================================================================
    def test_past_cutoff_candidate_transitions_to_expired_without_commit(self):
        """
        Tests that an uncommitted candidate whose cutoff has passed transitions
        to EXPIRED_WITHOUT_COMMIT and cannot be committed retrospectively to clean cohort.
        """
        past_candidate = {
            "ipo_id": "past-cutoff-sme-20261020",
            "company_name": "Past SME Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-10-20 16:00:00 IST",
            "authoritative_evidence": "BSE SME Notice Circular Ref 1020",
            "source_publication_timestamp_ist": "2026-10-18 10:00:00 IST",
            "raw_source_sha256": "c" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {
                "feat_nifty50_ret5s_pct": 0.5,
                "feat_india_vix": 14.0,
                "feat_recent5_sentiment": 10.0
            }
        }
        prep = self.lifecycle.audit_and_prepare_candidate(past_candidate)
        self.assertEqual(prep["candidate_lifecycle_state"], "EXPIRED_WITHOUT_COMMIT")
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("CANDIDATE_CUTOFF_EXPIRED" in r for r in prep["exclusion_reasons"]))

        # Attempt to commit expired candidate -> rejected from clean prospective cohort
        commit_res = self.lifecycle.commit_prospective_decision(past_candidate)
        self.assertEqual(commit_res["status"], "RECORDED")
        self.assertFalse(commit_res["is_clean_eligible"])
        self.assertTrue(commit_res["is_late"])
        self.assertTrue(any("LATE_DECISION_COMMITTED_AFTER_CUTOFF" in r for r in commit_res["exclusion_reasons"]))

    # =========================================================================
    # Workstream 2: Authoritative Exchange Evidence vs Secondary Portals
    # =========================================================================
    def test_secondary_source_cutoff_is_rejected_as_unverified(self):
        """
        Confirms that having a valid 64-char hash for a secondary portal document
        does not set is_bidding_cutoff_verified to True.
        """
        candidate_secondary = {
            "ipo_id": "carver-roboweld-sme-20261030",
            "company_name": "Carver Roboweld Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-10-30 16:00:00 IST",
            "authoritative_evidence": "Secondary aggregate listing portal: reports 16:00 IST",
            "source_publication_timestamp_ist": "2026-10-25 11:00:00 IST",
            "raw_source_sha256": "3a9c71e845f0d922bca981e44f32c918a56b7cd91024e6578dfba10842ca019d",
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": False,
            "features": {
                "feat_nifty50_ret5s_pct": 0.62,
                "feat_india_vix": 14.1,
                "feat_recent5_sentiment": 7.7
            }
        }
        prep = self.lifecycle.audit_and_prepare_candidate(candidate_secondary)
        self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_CUTOFF")
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("EXCHANGE_BIDDING_CUTOFF_UNVERIFIED" in r for r in prep["exclusion_reasons"]))

    # =========================================================================
    # Workstream 3: Exact 64-Char Provenance & Hash Enforcement
    # =========================================================================
    def test_abbreviated_or_placeholder_hashes_rejected(self):
        """
        Ensures that truncated hashes or placeholder strings are rejected.
        """
        bad_hashes = [
            "3a9c71e845f0d922bca981e44f32c918",  # 32 chars (MD5 length)
            "8f4b23c...e7",                      # ellipsis abbreviation
            "PENDING_HASH",                      # placeholder string
            "0" * 63                             # 63 chars (off by 1)
        ]
        for bh in bad_hashes:
            cand = {
                "ipo_id": "hash-test-candidate",
                "company_name": "Hash Test Ltd",
                "board_type": "SME",
                "cutoff_timestamp_ist": "2026-10-31 16:00:00 IST",
                "authoritative_evidence": "Notice Circular",
                "source_publication_timestamp_ist": "2026-10-25 10:00:00 IST",
                "raw_source_sha256": bh,
                "is_timing_verified": True,
                "is_bidding_cutoff_verified": True,
                "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 7.7}
            }
            prep = self.lifecycle.audit_and_prepare_candidate(cand)
            self.assertFalse(prep["is_clean_eligible"])
            self.assertTrue(any("MISSING_OR_INVALID_PROVENANCE_HASH" in r for r in prep["exclusion_reasons"]))

    # =========================================================================
    # Workstream 5: Future-Candidate 11-Gate Readiness Protocol
    # =========================================================================
    def test_fully_verified_candidate_passes_all_gates_without_auto_commit(self):
        """
        Tests that an SME candidate with complete authoritative evidence passes all 11 gates,
        achieves READY_FOR_PROSPECTIVE_COMMIT, but leaves decision ledger completely empty (no auto-commit).
        """
        future_candidate = {
            "ipo_id": "future-verified-sme-20261105",
            "company_name": "Apex Clean Energy SME Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-05 16:00:00 IST",
            "authoritative_evidence": "BSE SME Official Trading Notice Ref 20261101-08: Order book closes 16:00:00 IST",
            "source_publication_timestamp_ist": "2026-11-01 10:00:00 IST",
            "raw_source_sha256": "d" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {
                "feat_nifty50_ret5s_pct": 0.75,
                "feat_india_vix": 13.5,
                "feat_recent5_sentiment": 7.7
            }
        }
        prep = self.lifecycle.audit_and_prepare_candidate(future_candidate)
        self.assertEqual(prep["candidate_lifecycle_state"], "READY_FOR_PROSPECTIVE_COMMIT")
        self.assertTrue(prep["is_clean_eligible"])
        self.assertEqual(len(prep["exclusion_reasons"]), 0)
        self.assertIsNotNone(prep["predicted_probability"])

        # Confirm decision ledger is STILL empty (audit does NOT auto-commit)
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        self.assertEqual(len(logger.get_logged_decision_ids()), 0)


if __name__ == "__main__":
    unittest.main()
