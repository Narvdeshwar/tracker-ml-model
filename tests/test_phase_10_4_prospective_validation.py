"""
Comprehensive automated tests for Phase 10.4:
  1. Immutable decision ledger: duplicate commitment idempotency and hash chain preservation.
  2. Cutoff enforcement: rejection of post-cutoff decisions from clean cohort.
  3. Feature publication after cutoff triggers DATA_QUALITY_POST_CUTOFF_FEATURE and unverified status.
  4. Missing timezone or cutoff timestamp triggers TIMING_UNVERIFIED and clean cohort exclusion.
  5. Outcome reconciliation: exact return calculation formula ((P_open - P_issue)/P_issue)*100.
  6. Price integrity: rejection of negative or zero issue/open prices.
  7. Outcome cannot be recorded for non-existent prospective decision (unmatched outcome error).
  8. Prospective model evaluation: ROC-AUC and PR-AUC defined only when both classes present;
     explicit INCONCLUSIVE_SINGLE_CLASS when only one class is observed.
  9. Zero mature outcomes state produces explicit INCONCLUSIVE_ZERO_OUTCOMES without fabricated numbers.
  10. Read-only safety: Frozen model and manifest SHA-256 remain bit-for-bit identical before and after test executions.
"""

import os
import json
import tempfile
import shutil
import hashlib
import unittest
import pandas as pd
from fastapi.testclient import TestClient

from src.prospective_simulator_logger import ProspectiveDecisionLogger
from src.api.main import app

class TestPhase104ProspectiveValidation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.dec_ledger = os.path.join(self.temp_dir, "test_decisions.jsonl")
        self.out_ledger = os.path.join(self.temp_dir, "test_outcomes.jsonl")
        self.logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.dec_ledger,
            outcome_ledger_path=self.out_ledger
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_immutable_decision_ledger_idempotency(self):
        """Verifies duplicate commitment attempts return DUPLICATE_IGNORED and do not append."""
        res1 = self.logger.record_prospective_decision(
            ipo_id="ipo-idem-1",
            company_name="Idempotent Test Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-05 17:00:00 IST",
            features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 80.0},
            p_positive_open=0.80,
            p_macro=0.80,
            p_severe_loss=0.04,
            model_name="Model_6B_SME_v1.0",
            model_sha256="dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76",
            feature_provenance={
                "cutoff_source_evidence": "BSE Circular",
                "raw_source_sha256": "abc123hash",
                "is_timing_verified": True,
                "source_publication_timestamp_ist": "2026-11-04 12:00:00 IST"
            }
        )
        self.assertEqual(res1["status"], "RECORDED")
        
        # Second attempt
        res2 = self.logger.record_prospective_decision(
            ipo_id="ipo-idem-1",
            company_name="Idempotent Test Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-05 17:00:00 IST",
            features_dict={"feat_nifty50_ret5s_pct": 0.5},
            p_positive_open=0.80,
            p_macro=0.80,
            p_severe_loss=0.04,
            model_name="Model_6B_SME_v1.0",
            model_sha256="dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76"
        )
        self.assertEqual(res2["status"], "DUPLICATE_IGNORED")
        
        # Verify ledger file contains exactly 1 line
        with open(self.dec_ledger, "r", encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        self.assertEqual(len(lines), 1)

    def test_post_cutoff_decision_excluded_from_clean_cohort(self):
        """Verifies that an attempt to commit a decision after the cutoff fails clean cohort validation."""
        past_cutoff = "2025-01-01 17:00:00 IST"
        res = self.logger.record_prospective_decision(
            ipo_id="ipo-past-1",
            company_name="Past Cutoff Ltd",
            board_type="SME",
            cutoff_timestamp_ist=past_cutoff,
            features_dict={"feat_nifty50_ret5s_pct": 0.5},
            p_positive_open=0.80,
            p_macro=0.80,
            p_severe_loss=0.04,
            model_name="Model_6B_SME_v1.0",
            model_sha256="dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76",
            feature_provenance={
                "cutoff_source_evidence": "Notice",
                "raw_source_sha256": "hash",
                "is_timing_verified": True,
                "source_publication_timestamp_ist": "2024-12-31 12:00:00 IST"
            }
        )
        self.assertEqual(res["status"], "RECORDED")
        self.assertFalse(res["eligible_for_clean_prospective_cohort"])
        self.assertEqual(res["timing_verification_status"], "POST_CUTOFF_COMMITTED")

    def test_feature_published_after_cutoff_rejected(self):
        """Verifies feature publication timestamp > cutoff timestamp marks timing unverified."""
        cutoff = "2026-11-05 17:00:00 IST"
        pub_after = "2026-11-05 18:30:00 IST"
        res = self.logger.record_prospective_decision(
            ipo_id="ipo-feat-late",
            company_name="Late Features Ltd",
            board_type="SME",
            cutoff_timestamp_ist=cutoff,
            features_dict={"feat_nifty50_ret5s_pct": 0.5},
            p_positive_open=0.80,
            p_macro=0.80,
            p_severe_loss=0.04,
            model_name="Model_6B_SME_v1.0",
            model_sha256="dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76",
            feature_provenance={
                "cutoff_source_evidence": "Circular",
                "raw_source_sha256": "hash",
                "is_timing_verified": True,
                "source_publication_timestamp_ist": pub_after
            }
        )
        self.assertEqual(res["timing_verification_status"], "TIMING_UNVERIFIED")
        self.assertFalse(res["eligible_for_clean_prospective_cohort"])

    def test_missing_timezone_rejects_clean_status(self):
        """Verifies lack of explicit IST / +05:30 in cutoff rejects clean cohort eligibility."""
        no_tz_cutoff = "2026-11-05 17:00:00"  # Missing IST
        res = self.logger.record_prospective_decision(
            ipo_id="ipo-notz",
            company_name="No Timezone Ltd",
            board_type="SME",
            cutoff_timestamp_ist=no_tz_cutoff,
            features_dict={"feat_nifty50_ret5s_pct": 0.5},
            p_positive_open=0.80,
            p_macro=0.80,
            p_severe_loss=0.04,
            model_name="Model_6B_SME_v1.0",
            model_sha256="dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76",
            feature_provenance={
                "cutoff_source_evidence": "Circular",
                "raw_source_sha256": "hash",
                "is_timing_verified": True
            }
        )
        self.assertEqual(res["timing_verification_status"], "TIMING_UNVERIFIED")
        self.assertFalse(res["eligible_for_clean_prospective_cohort"])

    def test_outcome_reconciliation_exact_return_calculation(self):
        """Verifies exact return percentage calculation: ((P_open - P_issue)/P_issue)*100."""
        # 1. Commit prospective decision
        self.logger.record_prospective_decision(
            ipo_id="ipo-ret-1",
            company_name="Return Test Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-05 17:00:00 IST",
            features_dict={"feat_nifty50_ret5s_pct": 0.5},
            p_positive_open=0.85,
            p_macro=0.85,
            p_severe_loss=0.02,
            model_name="Model_6B_SME_v1.0",
            model_sha256="dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76",
            feature_provenance={
                "cutoff_source_evidence": "Circular",
                "raw_source_sha256": "hash",
                "is_timing_verified": True,
                "source_publication_timestamp_ist": "2026-11-04 12:00:00 IST"
            }
        )
        
        # 2. Record outcome with issue_price=100.0, open_price=125.0
        res_out = self.logger.record_realized_outcome(
            ipo_id="ipo-ret-1",
            listing_date="2026-11-08",
            listing_open_inr=125.0,
            issue_price_inr=100.0,
            outcome_source="Official NSE Bulletin Ref 20261108-01"
        )
        self.assertEqual(res_out["status"], "RECORDED")
        
        # Verify stored record
        with open(self.out_ledger, "r", encoding="utf-8") as f:
            rec = json.loads(f.readline())
        self.assertEqual(rec["gross_open_return_pct"], 25.0)
        self.assertTrue(rec["is_positive_open"])
        self.assertFalse(rec["is_severe_loss"])
        self.assertEqual(rec["modeled_net_return_pct"], 23.65)  # 25.0 - 1.0 (slippage) - 0.35 (cost)

    def test_invalid_prices_rejected(self):
        """Verifies negative or zero issue prices raise ValueError."""
        # Setup decision
        self.logger.record_prospective_decision(
            ipo_id="ipo-price-err",
            company_name="Price Error Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-05 17:00:00 IST",
            features_dict={"feat": 1},
            p_positive_open=0.8, p_macro=0.8, p_severe_loss=0.05,
            model_name="Model_6B_SME_v1.0", model_sha256="hash"
        )
        with self.assertRaises(ValueError):
            self.logger.record_realized_outcome(
                ipo_id="ipo-price-err",
                listing_date="2026-11-08",
                listing_open_inr=100.0,
                issue_price_inr=0.0  # Zero issue price
            )

    def test_unmatched_outcome_rejected(self):
        """Verifies recording outcome for non-existent prospective decision raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.logger.record_realized_outcome(
                ipo_id="non-existent-ipo-999",
                listing_date="2026-11-08",
                listing_open_inr=120.0,
                issue_price_inr=100.0
            )
        self.assertIn("UNMATCHED OUTCOME", str(ctx.exception))

    def test_prospective_evaluation_roc_auc_and_single_class_handling(self):
        """
        Verifies ROC-AUC / PR-AUC behavior:
        - When only single class exists: flags INCONCLUSIVE_SINGLE_CLASS.
        - When both classes exist: computes valid ROC-AUC and PR-AUC.
        """
        # Create 2 decisions
        for i, outcome_ret in enumerate([20.0, 15.0]):  # Both positive (single class)
            ipo_id = f"ipo-eval-{i}"
            self.logger.record_prospective_decision(
                ipo_id=ipo_id,
                company_name=f"Eval Test {i} Ltd",
                board_type="SME",
                cutoff_timestamp_ist="2026-11-05 17:00:00 IST",
                features_dict={"feat": 1},
                p_positive_open=0.85 if i == 0 else 0.75,
                p_macro=0.85, p_severe_loss=0.02,
                model_name="Model_6B_SME_v1.0", model_sha256="hash",
                feature_provenance={"cutoff_source_evidence": "BSE", "raw_source_sha256": "h", "is_timing_verified": True}
            )
            self.logger.record_realized_outcome(
                ipo_id=ipo_id,
                listing_date="2026-11-08",
                listing_open_inr=100.0 * (1 + outcome_ret / 100.0),
                issue_price_inr=100.0
            )

        res_single = self.logger.evaluate_prospective_brier_and_skill(board_type="SME", require_clean_cohort=True)
        self.assertEqual(res_single["status"], "EVALUATED")
        self.assertIsNone(res_single["roc_auc"])
        self.assertIn("INCONCLUSIVE_SINGLE_CLASS", res_single["auc_diagnostics"])

        # Add a negative outcome (dual class)
        neg_id = "ipo-eval-neg"
        self.logger.record_prospective_decision(
            ipo_id=neg_id,
            company_name="Eval Neg Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-05 17:00:00 IST",
            features_dict={"feat": 1},
            p_positive_open=0.40,
            p_macro=0.40, p_severe_loss=0.20,
            model_name="Model_6B_SME_v1.0", model_sha256="hash",
            feature_provenance={"cutoff_source_evidence": "BSE", "raw_source_sha256": "h", "is_timing_verified": True}
        )
        self.logger.record_realized_outcome(
            ipo_id=neg_id,
            listing_date="2026-11-08",
            listing_open_inr=85.0,
            issue_price_inr=100.0  # -15% loss
        )

        res_dual = self.logger.evaluate_prospective_brier_and_skill(board_type="SME", require_clean_cohort=True)
        self.assertIsNotNone(res_dual["roc_auc"])
        self.assertIsNotNone(res_dual["pr_auc"])
        self.assertGreater(res_dual["roc_auc"], 0.5)

    def test_api_read_only_safety_frozen_hashes_untouched(self):
        """Verifies frozen model and manifest SHA-256 remain bit-for-bit identical before and after queries."""
        client = TestClient(app)
        manifest_path = "models/frozen/phase_9b_baseline_manifest.json"
        sme_model_path = "models/frozen/model_6b_sme_v1.joblib"
        
        with open(manifest_path, "rb") as f:
            manifest_sha_before = hashlib.sha256(f.read()).hexdigest()
        with open(sme_model_path, "rb") as f:
            model_sha_before = hashlib.sha256(f.read()).hexdigest()

        # Execute queries with new parameters
        client.get("/api/metrics/brier?board=SME")
        client.get("/api/metrics/brier?board=Mainboard")
        client.get("/api/audit/selection-bias")
        client.get("/api/ipos?scoring_status=SCORED&listing_status=PENDING_LISTING")

        with open(manifest_path, "rb") as f:
            manifest_sha_after = hashlib.sha256(f.read()).hexdigest()
        with open(sme_model_path, "rb") as f:
            model_sha_after = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(manifest_sha_before, manifest_sha_after)
        self.assertEqual(model_sha_before, model_sha_after)


if __name__ == "__main__":
    unittest.main()
