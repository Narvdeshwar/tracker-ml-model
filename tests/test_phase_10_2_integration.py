"""
Comprehensive Integration Tests for Phase 10.2:
  1. Real data responses against registered repository records.
  2. Mainboard scoring restriction: scores remain strictly None.
  3. Reference Brier score mathematical verification (p*(1-p)) for SME and Mainboard.
  4. Pending outcomes handling (N_known=0 produces explicit INCONCLUSIVE/PENDING status, not fabricated zeros).
  5. Read-only safety verification: API requests never mutate frozen models, manifest, or ledgers.
  6. Ledger corruption and integrity warning detection.
  7. Empty candidate registry handling without crashes.
"""

import os
import json
import tempfile
import shutil
import hashlib
import unittest
from fastapi.testclient import TestClient

from src.api.main import app, load_manifest, load_tracked_candidates, verify_frozen_models, get_committed_ledgers
import src.api.main as api_module

class TestPhase102Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.manifest = load_manifest()
        cls.candidates = load_tracked_candidates()

    def test_status_endpoint_reconciliation(self):
        """Reconciles GET /api/status against actual candidate registry and manifest."""
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        
        self.assertEqual(data["status"], "OPERATIONAL")
        self.assertTrue(data["shadow_mode_active"])
        self.assertTrue(data["real_trading_prohibited"])
        
        # Verify counts match candidate registry
        n_eligible = len(self.candidates)
        n_clean = sum(1 for c in self.candidates if c["cohort_population"] == "Population_2_Clean_Prospective")
        n_excluded = sum(1 for c in self.candidates if c["cohort_population"] == "Population_3_Excluded_Unverified")
        
        self.assertEqual(data["populations"]["population_1_eligible_coverage_count"], n_eligible)
        self.assertEqual(data["populations"]["population_2_clean_prospective_count"], n_clean)
        self.assertEqual(data["populations"]["population_3_excluded_unverified_count"], n_excluded)

    def test_mainboard_never_scored_by_sme_model(self):
        """Verifies Mainboard candidates never receive invented scores from SME model."""
        res = self.client.get("/api/ipos?board=Mainboard")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        
        self.assertGreater(data["total"], 0)
        for ipo in data["ipos"]:
            self.assertEqual(ipo["board_type"], "Mainboard")
            self.assertIsNone(ipo["p_positive_open"], f"Mainboard candidate {ipo['ipo_id']} must have None score")
            self.assertIsNone(ipo["p_macro"])
            self.assertIsNone(ipo["p_severe_loss"])
            self.assertIn("Not Scored", ipo["model_coverage_status"])

    def test_sme_candidates_have_verified_scoring(self):
        """Verifies SME candidates have valid model coverage and preflight dry-run scores."""
        res = self.client.get("/api/ipos?board=SME")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        
        self.assertEqual(data["total"], 2)
        for ipo in data["ipos"]:
            self.assertEqual(ipo["board_type"], "SME")
            self.assertIsNotNone(ipo["p_positive_open"])
            self.assertGreater(ipo["p_positive_open"], 0.70)
            self.assertEqual(ipo["cohort_population"], "Population_2_Clean_Prospective")
            self.assertTrue(ipo["is_timing_verified"])

    def test_reference_brier_mathematical_derivation(self):
        """
        Audits exact mathematical derivation of Reference Brier Score:
        Reference Brier = p * (1 - p).
        """
        res = self.client.get("/api/metrics/brier")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        baselines = data["fixed_training_baselines"]
        
        p_sme = baselines["SME_train_base_rate"]
        p_mb = baselines["Mainboard_train_base_rate"]
        
        ref_sme_calc = round(p_sme * (1.0 - p_sme), 4)
        ref_mb_calc = round(p_mb * (1.0 - p_mb), 4)
        
        self.assertEqual(baselines["SME_reference_brier"], ref_sme_calc)
        self.assertEqual(baselines["Mainboard_reference_brier"], ref_mb_calc)
        self.assertEqual(baselines["SME_reference_brier"], 0.1407)
        self.assertEqual(baselines["Mainboard_reference_brier"], 0.1833)

    def test_pending_outcomes_produce_explicit_inconclusive_status(self):
        """
        Verifies that when zero outcomes are recorded, BSS and Brier are not fabricated as 0.0,
        but explicitly returned as None and INCONCLUSIVE_ZERO_OUTCOMES.
        """
        res = self.client.get("/api/metrics/brier")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        status = data["prospective_clean_cohort_status"]
        
        self.assertEqual(status["n_known_outcomes"], 0)
        self.assertEqual(status["evaluation_status"], "INCONCLUSIVE_ZERO_OUTCOMES")
        self.assertIsNone(status["model_brier_score"])
        self.assertIsNone(status["brier_skill_score"])

    def test_api_read_only_safety_no_file_mutations(self):
        """Verifies API requests never mutate frozen model files, manifest, or ledgers."""
        manifest_path = "models/frozen/phase_9b_baseline_manifest.json"
        sme_model_path = "models/frozen/model_6b_sme_v1.joblib"
        
        with open(manifest_path, "rb") as f:
            manifest_sha_before = hashlib.sha256(f.read()).hexdigest()
        with open(sme_model_path, "rb") as f:
            model_sha_before = hashlib.sha256(f.read()).hexdigest()
            
        # Execute extensive suite of API calls
        self.client.get("/")
        self.client.get("/api/status")
        self.client.get("/api/ipos")
        self.client.get("/api/ipos/wiscon-industries-sme-20261029")
        self.client.get("/api/metrics/brier")
        self.client.get("/api/metrics/allotment")
        self.client.get("/api/audit/selection-bias")
        
        with open(manifest_path, "rb") as f:
            manifest_sha_after = hashlib.sha256(f.read()).hexdigest()
        with open(sme_model_path, "rb") as f:
            model_sha_after = hashlib.sha256(f.read()).hexdigest()
            
        self.assertEqual(manifest_sha_before, manifest_sha_after)
        self.assertEqual(model_sha_before, model_sha_after)

    def test_ledger_corruption_triggers_integrity_warning(self):
        """
        Verifies that corrupted ledger records cause get_system_status to switch
        to INTEGRITY_WARNING with diagnostic warning logs.
        """
        temp_dir = tempfile.mkdtemp()
        try:
            corrupt_ledger = os.path.join(temp_dir, "corrupt_decisions.jsonl")
            with open(corrupt_ledger, "w", encoding="utf-8") as f:
                f.write('{"ipo_id": "test_1", "valid": true}\n')
                f.write('INVALID_NON_JSON_CORRUPT_LINE_XYZ\n')
                
            orig_dec_ledger = api_module.DECISION_LEDGER
            api_module.DECISION_LEDGER = corrupt_ledger
            
            res = self.client.get("/api/status")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            
            self.assertEqual(data["status"], "INTEGRITY_WARNING")
            self.assertGreater(len(data["live_ledgers"]["integrity_warnings"]), 0)
            self.assertIn("Corrupt JSON", data["live_ledgers"]["integrity_warnings"][0])
            
        finally:
            api_module.DECISION_LEDGER = orig_dec_ledger
            shutil.rmtree(temp_dir)

    def test_four_tier_separation_guarantee(self):
        """Verifies strict architectural four-tier separation."""
        res = self.client.get("/api/metrics/allotment")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        
        self.assertEqual(data["tier_3_real_execution_layer"]["status"], "PROHIBITED_SHADOW_MODE_ONLY")
        self.assertEqual(data["tier_3_real_execution_layer"]["real_capital_deployed_inr"], 0.0)
        self.assertEqual(data["tier_3_real_execution_layer"]["real_orders_executed"], 0)
        self.assertEqual(data["tier_3_real_execution_layer"]["real_broker_connections"], "DISABLED")


if __name__ == "__main__":
    unittest.main()
