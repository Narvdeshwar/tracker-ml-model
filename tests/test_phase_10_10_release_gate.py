"""
Unit tests for Phase 10.10: Independent Feature Parity and First-Decision Release Gate.
Covers:
  - Workstream 1: Exact feature parity between historical training feature builder and production lifecycle builder.
  - Workstream 2: Frozen SME inference deterministic regression and manifest SHA-256 verification.
  - Workstream 3 & 4: Candidate evidence verification and release gate integrity.
  - Workstream 5: Persistence, crash recovery, corruption detection, idempotency, and concurrent commit simulation.
  - Workstream 6: Sealed cryptographic checkpoint verification and tampering detection.
"""

import os
import json
import shutil
import tempfile
import unittest
import threading
import pandas as pd
import numpy as np
import joblib

from src.prospective_lifecycle import ProspectiveLifecycleManager, FROZEN_SME_MODEL_SHA256, FROZEN_SME_MODEL_PATH
from src.prospective_simulator_logger import ProspectiveDecisionLogger
from src.evidence_audit_protocol import ProspectiveEvidenceAuditor

EXPECTED_MODEL_SHA256 = "dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76"
EXPECTED_MANIFEST_SHA256 = "b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e"


class TestPhase1010ReleaseGate(unittest.TestCase):

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

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # Workstream 1: Feature Parity
    # =========================================================================
    def test_feature_parity_with_training_implementation(self):
        """
        Tests that calculate_trailing_5_sentiment exactly matches the training-time
        historical features across historical observation cutoffs.
        """
        df_sent = pd.read_csv("data/processed/ipo_sentiment_features.csv")
        valid = df_sent.dropna(subset=["prediction_cutoff_date", "recent5_mean_listing_open_return_pct"])
        sample = valid.sample(25, random_state=42)

        for _, row in sample.iterrows():
            c_date = row["prediction_cutoff_date"]
            expected = float(row["recent5_mean_listing_open_return_pct"])
            res = self.lifecycle.calculate_trailing_5_sentiment(c_date)
            self.assertEqual(res["status"], "VERIFIED_CALCULATED")
            self.assertAlmostEqual(res["mean_return_pct"], expected, places=2)

    def test_trailing_5_deterministic_selection_october_2026(self):
        """
        Verifies the exact trailing 5 issues and mean return for Wiscon & Carver pre-cutoff dates.
        Trailing mean open return must be exactly +7.70%, NOT positive opening rate (80.0).
        """
        res = self.lifecycle.calculate_trailing_5_sentiment("2026-10-29")
        self.assertEqual(res["status"], "VERIFIED_CALCULATED")
        self.assertEqual(res["count"], 5)
        self.assertEqual(res["mean_return_pct"], 7.7)

        prior_ids = [item["ipo_id"] for item in res["prior_issues"]]
        expected_ids = [
            "ipo-2026-10-06-ine029n01014",
            "ipo-2026-10-06-ine0rnf01016",
            "ipo-2026-10-06-ine18cu01023",
            "ipo-2026-10-06-ine1kul01020",
            "ipo-2026-10-06-ine307k01028"
        ]
        self.assertEqual(prior_ids, expected_ids)

    # =========================================================================
    # Workstream 2: Frozen Inference Verification
    # =========================================================================
    def test_frozen_sme_inference_exact_reproducibility(self):
        """
        Runs the actual frozen model artifact and confirms exact predictions for Wiscon and Carver.
        """
        # Wiscon inputs
        wiscon_feat = {
            "feat_nifty50_ret5s_pct": 0.85,
            "feat_india_vix": 13.8,
            "feat_recent5_sentiment": 7.7
        }
        p_wiscon = self.lifecycle.predict_frozen_sme(wiscon_feat)
        self.assertEqual(p_wiscon, 0.8144)

        # Carver inputs
        carver_feat = {
            "feat_nifty50_ret5s_pct": 0.62,
            "feat_india_vix": 14.1,
            "feat_recent5_sentiment": 7.7
        }
        p_carver = self.lifecycle.predict_frozen_sme(carver_feat)
        self.assertEqual(p_carver, 0.8100)

    def test_model_and_manifest_hash_integrity(self):
        """Verifies bitwise integrity of the frozen model and baseline manifest."""
        auditor = ProspectiveEvidenceAuditor()
        model_hash = auditor._hash_file(FROZEN_SME_MODEL_PATH)
        manifest_hash = auditor._hash_file("models/frozen/phase_9b_baseline_manifest.json")
        self.assertEqual(model_hash, EXPECTED_MODEL_SHA256)
        self.assertEqual(manifest_hash, EXPECTED_MANIFEST_SHA256)

    # =========================================================================
    # Workstream 3 & 4: Candidate Evidence & Cutoff Gates
    # =========================================================================
    def test_unverified_bidding_cutoff_blocks_commitment(self):
        """
        Verifies that candidates without independently verified exchange bidding cutoff
        are strictly blocked from commitment with an explicit reason code.
        """
        candidate = {
            "ipo_id": "wiscon-industries-sme-20261029",
            "company_name": "Wiscon Industries Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-10-29 16:00:00 IST",
            "authoritative_evidence": "BSE SME Notice Ref 20261024-01: Pending independent order book circular verification",
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
        prep = self.lifecycle.audit_and_prepare_candidate(candidate)
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("EXCHANGE_BIDDING_CUTOFF_UNVERIFIED" in r for r in prep["exclusion_reasons"]))

    # =========================================================================
    # Workstream 5: Persistence, Crash Recovery & Concurrency
    # =========================================================================
    def test_concurrent_commit_prevention(self):
        """
        Tests that concurrent threads attempting to commit the same candidate cannot create
        duplicate entries or race conditions.
        """
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )

        results = []

        def worker():
            res = logger.record_prospective_decision(
                ipo_id="concurrent-test-ipo",
                company_name="Concurrent Test Ltd",
                board_type="SME",
                cutoff_timestamp_ist="2026-10-31 16:00:00 IST",
                features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 10.0},
                p_positive_open=0.82,
                p_macro=0.82,
                p_severe_loss=0.04,
                model_name="Model_6B_SME_v1.0",
                model_sha256=EXPECTED_MODEL_SHA256,
                feature_provenance={
                    "cutoff_source_evidence": "Notice Circular",
                    "raw_source_sha256": "a" * 64,
                    "is_timing_verified": True,
                    "source_publication_timestamp_ist": "2026-10-25 10:00:00 IST"
                }
            )
            results.append(res["status"])

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 1 RECORDED, and 9 DUPLICATE_IGNORED
        self.assertEqual(results.count("RECORDED"), 1)
        self.assertEqual(results.count("DUPLICATE_IGNORED"), 9)

        # Confirm ledger physically contains exactly 1 line
        with open(self.decision_ledger, "r", encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        self.assertEqual(len(lines), 1)

    def test_corrupted_trailing_lines_recovery(self):
        """
        Verifies that corrupted, truncated, or half-written trailing JSONL lines do not crash
        the ledger reader and prior valid records are preserved.
        """
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )

        # Write valid decision
        res1 = logger.record_prospective_decision(
            ipo_id="valid-ipo-1",
            company_name="Valid 1 Ltd",
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

        # Simulate crash/power-loss writing half a line
        with open(self.decision_ledger, "a", encoding="utf-8") as f:
            f.write('{"record_type": "PROSPECTIVE_DECISION", "ipo_id": "corrupt-ip\n')

        # Read back logged IDs
        logged_ids = logger.get_logged_decision_ids()
        self.assertIn("valid-ipo-1", logged_ids)
        self.assertNotIn("corrupt-ip", logged_ids)

    # =========================================================================
    # Workstream 6: Sealed Checkpoint Verification
    # =========================================================================
    def test_sealed_checkpoint_integrity_check(self):
        """
        Tests that ProspectiveEvidenceAuditor correctly validates sealed files against
        SHA256_SEALED_DIGEST and detects any tampering.
        """
        auditor = ProspectiveEvidenceAuditor(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger,
            audit_events_path=self.audit_events,
            checkpoint_path=self.checkpoint
        )

        # Create valid mock checkpoint
        chk_data = {
            "checkpoint_id": "CHK_TEST_1010",
            "sealed_timestamp_ist": "2026-10-28 09:40:00 IST",
            "sealed_files": {
                "decision_ledger_sha256": "FILE_NOT_FOUND",
                "outcome_ledger_sha256": "FILE_NOT_FOUND",
                "governance_audit_events_sha256": "FILE_NOT_FOUND",
                "manifest_sha256": EXPECTED_MANIFEST_SHA256,
                "frozen_sme_model_sha256": EXPECTED_MODEL_SHA256
            },
            "signature_algorithm": "SHA256_SEALED_DIGEST",
            "sealed_checkpoint_sha256": "mock_hash"
        }
        with open(self.checkpoint, "w", encoding="utf-8") as f:
            json.dump(chk_data, f)

        res = auditor.verify_sealed_checkpoint()
        self.assertTrue(res["valid"])
        self.assertEqual(res["status"], "CHECKPOINT_VERIFIED")

        # Tamper with model hash in checkpoint
        chk_data["sealed_files"]["frozen_sme_model_sha256"] = "f" * 64
        with open(self.checkpoint, "w", encoding="utf-8") as f:
            json.dump(chk_data, f)

        res_tampered = auditor.verify_sealed_checkpoint()
        self.assertFalse(res_tampered["valid"])
        self.assertEqual(res_tampered["status"], "CHECKPOINT_INTEGRITY_BREACH")


if __name__ == "__main__":
    unittest.main()
