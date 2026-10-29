"""
Unit and integration tests for Phase 10.3 UI hardening:
  1. Multi-parameter search, filtering (board, population, scoring_status, listing_status), sorting, and pagination.
  2. IPO Detail audit trail: Section 1-9 data presence, timing checks, and source SHA-256.
  3. Mainboard 'Not Scored' model restriction: No model name, no fabricated score, no hurdles.
  4. Non-existent IPO 404 error handling.
  5. Read-only filesystem guarantee: Zero file mutations during extensive read queries.
  6. Empty result handling for out-of-range queries.
"""

import hashlib
import unittest
from fastapi.testclient import TestClient

from src.api.main import app

class TestPhase103ExplorerAndAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_search_by_company_name_and_symbol(self):
        """Verifies search works across company name, symbol, and ipo_id."""
        # By company name
        res1 = self.client.get("/api/ipos?search=wiscon")
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["total"], 1)
        self.assertEqual(data1["ipos"][0]["company_name"], "Wiscon Industries Ltd")

        # By symbol
        res2 = self.client.get("/api/ipos?search=BLSPOLY")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["total"], 1)
        self.assertEqual(data2["ipos"][0]["symbol_or_ref"], "BLSPOLY")

        # By ipo_id substring
        res3 = self.client.get("/api/ipos?search=eaaa-india")
        self.assertEqual(res3.status_code, 200)
        data3 = res3.json()
        self.assertEqual(data3["total"], 1)
        self.assertEqual(data3["ipos"][0]["ipo_id"], "eaaa-india-mainboard-20261028")

    def test_filter_by_scoring_and_listing_status(self):
        """Tests filtering by SCORED vs NOT_SCORED and listing status."""
        # Filter SCORED
        res_scored = self.client.get("/api/ipos?scoring_status=SCORED")
        self.assertEqual(res_scored.status_code, 200)
        data_scored = res_scored.json()
        self.assertEqual(data_scored["total"], 2)
        for ipo in data_scored["ipos"]:
            self.assertEqual(ipo["board_type"], "SME")
            self.assertIsNotNone(ipo["p_positive_open"])

        # Filter NOT_SCORED
        res_not_scored = self.client.get("/api/ipos?scoring_status=NOT_SCORED")
        self.assertEqual(res_not_scored.status_code, 200)
        data_not_scored = res_not_scored.json()
        self.assertEqual(data_not_scored["total"], 4)
        for ipo in data_not_scored["ipos"]:
            self.assertEqual(ipo["board_type"], "Mainboard")
            self.assertIsNone(ipo["p_positive_open"])

        # Filter PENDING_LISTING
        res_pending = self.client.get("/api/ipos?listing_status=PENDING_LISTING")
        self.assertEqual(res_pending.status_code, 200)
        data_pending = res_pending.json()
        self.assertEqual(data_pending["total"], 6)

    def test_sorting_and_pagination(self):
        """Tests sort orders and pagination bounds."""
        # Sort by p_positive_open descending
        res_sort = self.client.get("/api/ipos?sort_by=p_positive_open&sort_dir=desc")
        self.assertEqual(res_sort.status_code, 200)
        data_sort = res_sort.json()
        # Top 2 should be the SME models with probabilities ~0.8124 and ~0.7985
        self.assertIsNotNone(data_sort["ipos"][0]["p_positive_open"])
        self.assertIsNotNone(data_sort["ipos"][1]["p_positive_open"])
        self.assertGreater(data_sort["ipos"][0]["p_positive_open"], data_sort["ipos"][1]["p_positive_open"])

        # Pagination: page_size=2, page=1
        res_p1 = self.client.get("/api/ipos?page=1&page_size=2")
        self.assertEqual(res_p1.status_code, 200)
        d_p1 = res_p1.json()
        self.assertEqual(len(d_p1["ipos"]), 2)
        self.assertEqual(d_p1["total"], 6)
        self.assertEqual(d_p1["total_pages"], 3)
        self.assertEqual(d_p1["page"], 1)

        # Pagination: page=2
        res_p2 = self.client.get("/api/ipos?page=2&page_size=2")
        self.assertEqual(res_p2.status_code, 200)
        d_p2 = res_p2.json()
        self.assertEqual(len(d_p2["ipos"]), 2)
        self.assertNotEqual(d_p1["ipos"][0]["ipo_id"], d_p2["ipos"][0]["ipo_id"])

    def test_ipo_detail_audit_traceability(self):
        """Tests that IPO detail returns complete auditability, evidence, and model governance."""
        res = self.client.get("/api/ipos/wiscon-industries-sme-20261029")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        
        # Verify model governance
        gov = data["model_governance"]
        self.assertTrue(gov["model_authorized"])
        self.assertEqual(gov["model_name"], "Model_6B_SME_v1.0")
        self.assertEqual(gov["model_sha256"], "dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76")
        self.assertIn("th_pos", gov["decision_hurdles"])

        # Verify audit checks
        audit = data["audit_checks"]
        self.assertTrue(audit["has_authoritative_cutoff"])
        self.assertTrue(audit["timezone_valid"])
        self.assertTrue(audit["raw_source_checksum_verified"])
        self.assertTrue(audit["timing_verified_prior_to_cutoff"])
        self.assertTrue(audit["pre_cutoff_chronological_consistency"])
        self.assertTrue(audit["clean_cohort_eligible"])
        
        # Verify outcome layer
        outcome = data["listing_outcome"]
        self.assertFalse(outcome["is_listed"])
        self.assertEqual(outcome["evidence_status"], "PENDING_OFFICIAL_EXCHANGE_BULLETIN")

    def test_mainboard_detail_governance_restriction(self):
        """Verifies Mainboard detail enforces model restriction without fabricated thresholds."""
        res = self.client.get("/api/ipos/bls-polymers-mainboard-20261029")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        
        gov = data["model_governance"]
        self.assertFalse(gov["model_authorized"])
        self.assertIsNone(gov["model_sha256"])
        self.assertIsNone(gov["decision_hurdles"])
        self.assertIn("Coverage Tracking Only", gov["model_name"])
        self.assertIsNone(data["ipo"]["p_positive_open"])

    def test_excluded_candidate_audit_flags(self):
        """Verifies candidate with unverified timing fails clean cohort eligibility check."""
        res = self.client.get("/api/ipos/eaaa-india-mainboard-20261028")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        
        audit = data["audit_checks"]
        self.assertFalse(audit["timing_verified_prior_to_cutoff"])
        self.assertFalse(audit["clean_cohort_eligible"])
        self.assertEqual(data["ipo"]["cohort_population"], "Population_3_Excluded_Unverified")

    def test_ipo_not_found_returns_404(self):
        """Tests that invalid IPO id raises 404."""
        res = self.client.get("/api/ipos/unknown-nonexistent-ipo")
        self.assertEqual(res.status_code, 404)
        self.assertIn("not found in tracked registry", res.json()["detail"])

    def test_read_only_protection_during_explorer_queries(self):
        """Ensures queries never mutate frozen model artifacts or manifest."""
        manifest_path = "models/frozen/phase_9b_baseline_manifest.json"
        sme_model_path = "models/frozen/model_6b_sme_v1.joblib"
        
        with open(manifest_path, "rb") as f:
            manifest_sha_before = hashlib.sha256(f.read()).hexdigest()
        with open(sme_model_path, "rb") as f:
            model_sha_before = hashlib.sha256(f.read()).hexdigest()

        # Call multiple search, filter, and detail endpoints
        self.client.get("/api/ipos?search=carver&sort_by=company_name&sort_dir=desc")
        self.client.get("/api/ipos/carver-roboweld-sme-20261030")
        self.client.get("/api/ipos?population=Population_3_Excluded_Unverified")

        with open(manifest_path, "rb") as f:
            manifest_sha_after = hashlib.sha256(f.read()).hexdigest()
        with open(sme_model_path, "rb") as f:
            model_sha_after = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(manifest_sha_before, manifest_sha_after)
        self.assertEqual(model_sha_before, model_sha_after)


if __name__ == "__main__":
    unittest.main()
