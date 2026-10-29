"""
Unit tests for FastAPI research and audit endpoints in src/api/main.py.
Verifies:
  1. System status and shadow mode governance flag.
  2. Model coverage restriction: Mainboard must never have invented scores (p_positive_open is None).
  3. SME candidates have valid model coverage and preflight dry-run scores.
  4. 4-tier separation: Tier 3 real execution status is explicitly PROHIBITED_SHADOW_MODE_ONLY.
  5. 3-population tracking in selection bias audit.
  6. Endpoint retrieval by specific IPO ID.
"""

import unittest
from fastapi.testclient import TestClient
from src.api.main import app

class TestFastAPIRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_status_endpoint(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "OPERATIONAL")
        self.assertTrue(data["shadow_mode_active"])
        self.assertTrue(data["real_trading_prohibited"])
        self.assertTrue(data["frozen_manifest_verified"])
        self.assertIn("Model_6B_SME_v1.0", data["models_verified"])
        self.assertEqual(data["models_verified"]["Model_6B_SME_v1.0"]["status"], "VERIFIED")

    def test_list_tracked_ipos_coverage_restriction(self):
        response = self.client.get("/api/ipos")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 6)
        
        # Verify Mainboard candidates have NO invented scores
        mainboard_ipos = [i for i in data["ipos"] if i["board_type"] == "Mainboard"]
        self.assertGreaterEqual(len(mainboard_ipos), 3)
        for mb in mainboard_ipos:
            self.assertIsNone(mb["p_positive_open"], f"Mainboard issue {mb['ipo_id']} must have None score")
            self.assertIn("Not Scored", mb["model_coverage_status"])

        # Verify SME candidates have Model_6B_SME_v1.0 scoring
        sme_ipos = [i for i in data["ipos"] if i["board_type"] == "SME"]
        self.assertEqual(len(sme_ipos), 2)
        for sme in sme_ipos:
            self.assertIsNotNone(sme["p_positive_open"])
            self.assertGreater(sme["p_positive_open"], 0.70)
            self.assertIn("Model_6B_SME_v1.0", sme["model_coverage_status"])

    def test_ipo_detail_lookup(self):
        response = self.client.get("/api/ipos/wiscon-industries-sme-20261029")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ipo"]["company_name"], "Wiscon Industries Ltd")
        self.assertTrue(data["audit_checks"]["has_authoritative_cutoff"])
        self.assertTrue(data["audit_checks"]["timing_verified_prior_to_cutoff"])

        # Test non-existent IPO
        err_res = self.client.get("/api/ipos/non-existent-ipo")
        self.assertEqual(err_res.status_code, 404)

    def test_metrics_brier_fixed_baselines(self):
        response = self.client.get("/api/metrics/brier")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        baselines = data["fixed_training_baselines"]
        self.assertAlmostEqual(baselines["SME_train_base_rate"], 0.8306, places=4)
        self.assertAlmostEqual(baselines["Mainboard_train_base_rate"], 0.7583, places=4)
        self.assertEqual(data["prospective_clean_cohort_status"]["checkpoint_1_target"], 30)
        self.assertEqual(data["prospective_clean_cohort_status"]["production_hurdle_target"], 100)

    def test_four_tier_separation_metrics(self):
        response = self.client.get("/api/metrics/allotment")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("tier_1_prediction_layer", data)
        self.assertIn("tier_2_observed_allotment_layer", data)
        self.assertIn("tier_3_real_execution_layer", data)
        self.assertIn("tier_4_simulated_scenarios_layer", data)
        
        tier_3 = data["tier_3_real_execution_layer"]
        self.assertEqual(tier_3["status"], "PROHIBITED_SHADOW_MODE_ONLY")
        self.assertEqual(tier_3["real_capital_deployed_inr"], 0.0)

    def test_selection_bias_audit_populations(self):
        response = self.client.get("/api/audit/selection-bias")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        preflight = data["preflight_registered_cohorts"]
        self.assertEqual(preflight["population_1_total"], 6)
        self.assertEqual(preflight["population_2_clean_count"], 2)
        self.assertEqual(preflight["population_3_excluded_count"], 1)
        self.assertIn("eaaa-india-mainboard-20261028", preflight["exclusion_reasons"])


if __name__ == "__main__":
    unittest.main()
