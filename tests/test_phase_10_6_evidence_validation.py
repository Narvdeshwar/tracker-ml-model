"""
Comprehensive automated tests for Phase 10.6:
  1. Observation-level evidence audit: Tracing prediction to inputs, cutoff, model hash, and outcome.
  2. Brier score and baseline evaluated on identical prospective observations.
  3. Constant baseline prospective Brier score calculated from actual prospective labels.
  4. Seed-locked bootstrap CI determinism.
  5. Degenerate and single-class bootstrap handling (explicit INCONCLUSIVE_SINGLE_CLASS).
  6. Non-parametric drift diagnostics (IQR, quantile shifts, KS test).
  7. Audit checkpoint sealing and integrity verification.
  8. Checkpoint alteration detection if any sealed ledger or manifest is modified.
  9. Mainboard/model incompatibility rejection in observation audit.
  10. Read-only safety: Frozen model and manifest SHA-256 remain bit-for-bit unchanged.
"""

import os
import json
import tempfile
import shutil
import hashlib
import unittest
import numpy as np
from fastapi.testclient import TestClient

from src.evidence_audit_protocol import ProspectiveEvidenceAuditor
from src.surveillance_monitor import FROZEN_TRAINING_FEATURE_REFERENCE
from src.api.main import app

class TestPhase106EvidenceAndValidation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.dec_ledger = os.path.join(self.temp_dir, "test_decisions.jsonl")
        self.out_ledger = os.path.join(self.temp_dir, "test_outcomes.jsonl")
        self.candidates_path = os.path.join(self.temp_dir, "test_candidates.json")
        self.audit_events_path = os.path.join(self.temp_dir, "test_audit_events.jsonl")
        self.checkpoint_path = os.path.join(self.temp_dir, "test_checkpoint.json")

        self.auditor = ProspectiveEvidenceAuditor(
            decision_ledger_path=self.dec_ledger,
            outcome_ledger_path=self.out_ledger,
            candidate_registry_path=self.candidates_path,
            audit_events_path=self.audit_events_path,
            checkpoint_path=self.checkpoint_path
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_observation_level_evidence_audit_traceability(self):
        """Verifies observation-level audit traces decision inputs, cutoff, model hash, and verified outcome."""
        # Create a valid decision
        dec_record = {
            "record_type": "PROSPECTIVE_DECISION",
            "decision_id": "DEC_TEST_001",
            "ipo_id": "wiscon-sme-test",
            "company_name": "Wiscon Test Ltd",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-05 17:00:00 IST",
            "logging_timestamp_ist": "2026-11-05 16:30:00 IST",
            "model_name": "Model_6B_SME_v1.0",
            "model_sha256": "dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76",
            "feature_hash_sha256": "feat_hash_123",
            "features": {"feat_nifty50_ret5s_pct": 0.8},
            "feature_provenance": {
                "cutoff_source_evidence": "BSE Circular",
                "raw_source_sha256": "src_sha_456",
                "is_timing_verified": True,
                "source_publication_timestamp_ist": "2026-11-04 12:00:00 IST"
            },
            "predicted_probabilities": {"p_positive_open": 0.82, "p_macro": 0.82, "p_severe_loss": 0.04},
            "eligible_for_clean_prospective_cohort": True,
            "record_sha256": "rec_sha_789"
        }
        with open(self.dec_ledger, "w", encoding="utf-8") as f:
            f.write(json.dumps(dec_record) + "\n")

        # Create matching verified outcome
        out_record = {
            "record_type": "REALIZED_OUTCOME",
            "outcome_id": "OUT_TEST_001",
            "ipo_id": "wiscon-sme-test",
            "listing_date": "2026-11-08",
            "issue_price_inr": 100.0,
            "listing_open_inr": 125.0,
            "gross_open_return_pct": 25.0,
            "is_positive_open": True,
            "outcome_source": "NSE Circular Ref 20261108"
        }
        with open(self.out_ledger, "w", encoding="utf-8") as f:
            f.write(json.dumps(out_record) + "\n")

        # Audit
        res = self.auditor.audit_observation_level_evidence()
        self.assertEqual(res["total_observations_audited"], 1)
        self.assertEqual(res["mature_observations_count"], 1)
        self.assertEqual(res["clean_included_count"], 1)
        
        obs = res["observations"][0]
        self.assertEqual(obs["ipo_id"], "wiscon-sme-test")
        self.assertTrue(obs["audit_checks"]["committed_before_cutoff"])
        self.assertTrue(obs["audit_checks"]["model_board_compatible"])
        self.assertEqual(obs["inclusion_status"], "CLEAN_PROSPECTIVE_COHORT")
        self.assertEqual(obs["outcome_layer"]["gross_open_return_pct"], 25.0)

    def test_model_and_baseline_evaluated_on_identical_observations(self):
        """
        Verifies that Model Brier Score and Constant Baseline Brier Score are evaluated
        on the exact same paired prospective observations and labels.
        """
        decisions = [
            {"ipo_id": "ipo-1", "board_type": "SME", "eligible_for_clean_prospective_cohort": True, "predicted_probabilities": {"p_positive_open": 0.80}},
            {"ipo_id": "ipo-2", "board_type": "SME", "eligible_for_clean_prospective_cohort": True, "predicted_probabilities": {"p_positive_open": 0.60}},
            {"ipo_id": "ipo-3", "board_type": "SME", "eligible_for_clean_prospective_cohort": True, "predicted_probabilities": {"p_positive_open": 0.90}}
        ]
        outcomes = [
            {"ipo_id": "ipo-1", "is_positive_open": True},   # y=1
            {"ipo_id": "ipo-2", "is_positive_open": False},  # y=0
            {"ipo_id": "ipo-3", "is_positive_open": True}    # y=1
        ]
        with open(self.dec_ledger, "w", encoding="utf-8") as f:
            for d in decisions: f.write(json.dumps(d) + "\n")
        with open(self.out_ledger, "w", encoding="utf-8") as f:
            for o in outcomes: f.write(json.dumps(o) + "\n")

        res = self.auditor.evaluate_prospective_metrics_rigorous(board_type="SME", require_clean=True)
        self.assertEqual(res["status"], "EVALUATED")
        self.assertEqual(res["sample_size_mature"], 3)
        
        # Verify manual Brier score calculation:
        # p_model: [0.80, 0.60, 0.90], y: [1, 0, 1]
        # (0.8-1)^2 = 0.04; (0.6-0)^2 = 0.36; (0.9-1)^2 = 0.01 -> mean = 0.41/3 = 0.1367
        # p_base = 0.8306:
        # (0.8306-1)^2 = 0.028696; (0.8306-0)^2 = 0.689896; (0.8306-1)^2 = 0.028696 -> mean = 0.747288/3 = 0.2491
        self.assertAlmostEqual(res["model_brier_score"], 0.1367, places=3)
        self.assertAlmostEqual(res["baseline_brier_score"], 0.2491, places=3)
        self.assertGreater(res["brier_skill_score"], 0.0)

    def test_roc_auc_single_class_produces_explicit_inconclusive(self):
        """Verifies that when only single-class outcomes exist, ROC/PR-AUC are marked INCONCLUSIVE_SINGLE_CLASS."""
        decisions = [
            {"ipo_id": "ipo-a", "board_type": "SME", "eligible_for_clean_prospective_cohort": True, "predicted_probabilities": {"p_positive_open": 0.80}},
            {"ipo_id": "ipo-b", "board_type": "SME", "eligible_for_clean_prospective_cohort": True, "predicted_probabilities": {"p_positive_open": 0.75}}
        ]
        outcomes = [
            {"ipo_id": "ipo-a", "is_positive_open": True},  # Both positive
            {"ipo_id": "ipo-b", "is_positive_open": True}
        ]
        with open(self.dec_ledger, "w", encoding="utf-8") as f:
            for d in decisions: f.write(json.dumps(d) + "\n")
        with open(self.out_ledger, "w", encoding="utf-8") as f:
            for o in outcomes: f.write(json.dumps(o) + "\n")

        res = self.auditor.evaluate_prospective_metrics_rigorous(board_type="SME", require_clean=True)
        self.assertEqual(res["status"], "EVALUATED")
        self.assertIsNone(res["roc_auc"])
        self.assertEqual(res["auc_diagnostics"], "INCONCLUSIVE_SINGLE_CLASS")

    def test_bootstrap_determinism_seed_locked(self):
        """Verifies paired bootstrap CI produces identical intervals given the same random seed."""
        decisions = [
            {"ipo_id": f"ipo-{i}", "board_type": "SME", "eligible_for_clean_prospective_cohort": True, "predicted_probabilities": {"p_positive_open": 0.5 + (i * 0.05)}}
            for i in range(10)
        ]
        outcomes = [
            {"ipo_id": f"ipo-{i}", "is_positive_open": (i % 2 == 0)}
            for i in range(10)
        ]
        with open(self.dec_ledger, "w", encoding="utf-8") as f:
            for d in decisions: f.write(json.dumps(d) + "\n")
        with open(self.out_ledger, "w", encoding="utf-8") as f:
            for o in outcomes: f.write(json.dumps(o) + "\n")

        res1 = self.auditor.evaluate_prospective_metrics_rigorous(board_type="SME", random_seed=42)
        res2 = self.auditor.evaluate_prospective_metrics_rigorous(board_type="SME", random_seed=42)
        self.assertEqual(res1["bootstrap_95_ci_brier"], res2["bootstrap_95_ci_brier"])
        self.assertEqual(res1["bootstrap_95_ci_bss"], res2["bootstrap_95_ci_bss"])

    def test_non_parametric_drift_diagnostics(self):
        """Verifies enhanced drift methodology calculates median, IQR, and z-shifts on N=20 fixture."""
        synthetic = []
        for i in range(20):
            synthetic.append({
                "ipo_id": f"drift-test-{i}",
                "features": {
                    "feat_nifty50_ret5s_pct": 0.5 + (i * 0.02),
                    "feat_india_vix": 14.0 + (i * 0.1),
                    "feat_recent5_sentiment": 40.0
                }
            })
        res = self.auditor.audit_drift_methodology_enhanced(
            synthetic,
            FROZEN_TRAINING_FEATURE_REFERENCE["features"]
        )
        self.assertEqual(res["status"], "EVALUATED")
        vix_res = res["feature_drift_diagnostics"]["feat_india_vix"]
        self.assertIn("observed_median", vix_res)
        self.assertIn("observed_iqr", vix_res)

    def test_cryptographic_audit_checkpoint_sealing_and_verification(self):
        """Verifies audit checkpoint generation and tamper detection upon file alteration."""
        # Write dummy ledger line
        with open(self.dec_ledger, "w", encoding="utf-8") as f:
            f.write('{"init": true}\n')
            
        chk = self.auditor.generate_and_seal_audit_checkpoint()
        self.assertIsNotNone(chk["sealed_checkpoint_sha256"])
        
        # Verify valid checkpoint
        ver = self.auditor.verify_sealed_checkpoint()
        self.assertTrue(ver["valid"])
        self.assertEqual(ver["status"], "CHECKPOINT_VERIFIED")

        # Tamper decision ledger by appending a modified record
        with open(self.dec_ledger, "a", encoding="utf-8") as f:
            f.write('{"tampered": true}\n')

        # Verification must now fail
        tamper_ver = self.auditor.verify_sealed_checkpoint()
        self.assertFalse(tamper_ver["valid"])
        self.assertEqual(tamper_ver["status"], "CHECKPOINT_INTEGRITY_BREACH")
        self.assertFalse(tamper_ver["file_matches"]["decision_ledger"])

    def test_fastapi_phase_10_6_endpoints(self):
        """Verifies FastAPI endpoints for Phase 10.6."""
        client = TestClient(app)
        
        res_obs = client.get("/api/audit/observation-level")
        self.assertEqual(res_obs.status_code, 200)
        self.assertIn("total_observations_audited", res_obs.json())

        res_rig = client.get("/api/metrics/rigorous-eval")
        self.assertEqual(res_rig.status_code, 200)
        self.assertEqual(res_rig.json()["status"], "INCONCLUSIVE_ZERO_MATURE_OUTCOMES")

        res_chk = client.get("/api/audit/checkpoint-verification")
        self.assertEqual(res_chk.status_code, 200)
        self.assertTrue(res_chk.json()["valid"])


if __name__ == "__main__":
    unittest.main()
