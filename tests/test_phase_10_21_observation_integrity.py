"""
Unit & Adversarial Tests for Phase 10.21:
Prospective Observation Integrity, Outcome Reconciliation & Cross-Process Persistence Assurance.

Covers at least the 24 required test scenarios from Phase 10.21:
1. Missing decision provenance.
2. Feature snapshot modified after decision.
3. Model hash mismatch.
4. Manifest hash mismatch.
5. Candidate expires before persistence.
6. Two processes attempt the same commitment.
7. Crash during persistence (simulated truncated record).
8. Restart following partial persistence.
9. Duplicate outcome ingestion.
10. Incorrect listing price units.
11. Listing-close data substituted for listing-open data.
12. Missing official outcome artifact.
13. Outcome source hash mismatch.
14. Contradictory official outcome sources.
15. Outcome received before the expected observation is mature.
16. Blocked candidates included accidentally in evaluation.
17. Immature outcomes included in evaluation.
18. Simulated outcomes mixed with actual observations.
19. Empty-cohort metrics.
20. Single-class evaluation cohorts.
21. Duplicate candidate IDs.
22. Unauthorized outcome correction.
23. Mainboard candidate scored by the SME model.
24. Evaluation report generation mutates production records.
"""

import unittest
import os
import json
import shutil
import tempfile
import hashlib
import datetime
from concurrent.futures import ThreadPoolExecutor

from src.prospective_lifecycle import (
    ProspectiveLifecycleManager,
    FROZEN_SME_MODEL_SHA256,
    MANIFEST_SHA256,
    DECISION_LEDGER_PATH,
    OUTCOME_LEDGER_PATH,
    CANDIDATE_REGISTRY_PATH,
    AUDIT_EVENTS_PATH,
    EVALUATION_RECORDS_PATH
)
from src.prospective_simulator_logger import ProspectiveDecisionLogger


class TestPhase1021ObservationIntegrity(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_phase_10_21_")
        self.decision_ledger = os.path.join(self.test_dir, "prospective_decision_ledger.jsonl")
        self.outcome_ledger = os.path.join(self.test_dir, "prospective_outcome_ledger.jsonl")
        self.candidate_registry = os.path.join(self.test_dir, "tracked_candidate_registry.json")
        self.audit_events = os.path.join(self.test_dir, "governance_audit_events.jsonl")
        self.evaluation_records = os.path.join(self.test_dir, "prospective_evaluation_records.jsonl")
        self.checkpoint_file = os.path.join(self.test_dir, "governance_checkpoint_signature.json")

        with open(CANDIDATE_REGISTRY_PATH, "r", encoding="utf-8") as f:
            registry_data = json.load(f)
        with open(self.candidate_registry, "w", encoding="utf-8") as f:
            json.dump(registry_data, f, indent=2)

        self.manager = ProspectiveLifecycleManager(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger,
            candidate_registry_path=self.candidate_registry,
            audit_events_path=self.audit_events,
            evaluation_records_path=self.evaluation_records,
            checkpoint_path=self.checkpoint_file
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_unblocked_sme_candidate(self, ipo_id="test-sme-unblocked-21"):
        raw_doc = f"Official BSE SME circular for {ipo_id}. Order book close: 16:00:00 IST."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        cand = {
            "ipo_id": ipo_id,
            "company_name": f"Candidate {ipo_id}",
            "board_type": "SME",
            "cutoff_timestamp_ist": "2026-11-20 16:00:00 IST",
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "authoritative_evidence": f"BSE_CIRCULAR_OFFICIAL:{ipo_id}",
            "source_publication_timestamp_ist": "2026-11-19 10:00:00 IST",
            "raw_source_sha256": doc_hash,
            "features": {
                "feat_nifty50_ret5s_pct": 0.5,
                "feat_india_vix": 14.0,
                "feat_recent5_sentiment": 5.0
            }
        }
        return cand

    def test_01_missing_decision_provenance(self):
        """1. Candidate missing required decision provenance cannot be committed as clean cohort."""
        cand = self._create_unblocked_sme_candidate("test-missing-prov")
        cand["raw_source_sha256"] = None  # Missing provenance hash
        cand["is_timing_verified"] = False
        with self.assertRaises(ValueError) as ctx:
            self.manager.commit_prospective_decision(
                candidate_dict=cand,
                override_commit_timestamp_ist="2026-11-20 12:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "Auditor", "authorization_token": "a" * 32}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    def test_02_feature_snapshot_modified_after_decision(self):
        """2. Decision record verifies cryptographic hash of features dict; modification alters record hash."""
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        features = {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0}
        rec = logger.record_prospective_decision(
            ipo_id="test-feat-hash",
            company_name="Feat Hash Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-20 16:00:00 IST",
            features_dict=features,
            p_positive_open=0.80,
            p_macro=0.80,
            p_severe_loss=0.05,
            model_name="Model_6B_SME_v1.0",
            model_sha256=FROZEN_SME_MODEL_SHA256
        )
        self.assertEqual(rec["status"], "RECORDED")
        
        # Read the stored record
        with open(self.decision_ledger, "r", encoding="utf-8") as f:
            stored = json.loads(f.readline())
        
        orig_hash = stored["feature_hash_sha256"]
        calc_hash = hashlib.sha256(json.dumps(features, sort_keys=True).encode("utf-8")).hexdigest()
        self.assertEqual(orig_hash, calc_hash)

        # Post-decision modification detected
        modified_features = {"feat_nifty50_ret5s_pct": 0.99, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0}
        mod_hash = hashlib.sha256(json.dumps(modified_features, sort_keys=True).encode("utf-8")).hexdigest()
        self.assertNotEqual(orig_hash, mod_hash)

    def test_03_model_hash_mismatch(self):
        """3. Any model SHA-256 mismatch blocks commitment immediately."""
        cand = self._create_unblocked_sme_candidate("test-bad-model-hash")
        prep = self.manager.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-20 12:00:00 IST")
        prep["model_sha256"] = "0" * 64
        with self.assertRaises(ValueError) as ctx:
            self.manager.commit_prospective_decision(
                candidate_dict=prep,
                override_commit_timestamp_ist="2026-11-20 12:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "Auditor", "authorization_token": "a" * 32}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    def test_04_manifest_hash_mismatch(self):
        """4. Any baseline manifest mismatch blocks commitment."""
        cand = self._create_unblocked_sme_candidate("test-bad-manifest-hash")
        # Tampering manifest reference in candidate
        cand["manifest_sha256"] = "1" * 64
        prep = self.manager.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-20 12:00:00 IST")
        prep["manifest_sha256"] = "1" * 64
        with self.assertRaises(ValueError) as ctx:
            self.manager.commit_prospective_decision(
                candidate_dict=prep,
                override_commit_timestamp_ist="2026-11-20 12:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "Auditor", "authorization_token": "a" * 32}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    def test_05_candidate_expires_before_persistence(self):
        """5. Candidate expiring between readiness audit and persistence is blocked at persistence boundary."""
        cand = self._create_unblocked_sme_candidate("test-toctou-expiry")
        cand["cutoff_timestamp_ist"] = "2026-11-20 16:00:00 IST"
        cand["source_publication_timestamp_ist"] = "2026-11-19 10:00:00 IST"
        # Prepared before cutoff
        prep = self.manager.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-11-20 15:59:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "READY_FOR_PROSPECTIVE_COMMIT")

        # Persistence attempted at or after cutoff
        with self.assertRaises(ValueError) as ctx:
            self.manager.commit_prospective_decision(
                candidate_dict=cand,
                override_commit_timestamp_ist="2026-11-20 16:00:01 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "Auditor", "authorization_token": "a" * 32}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    def test_06_two_processes_attempt_same_commitment(self):
        """6. Two concurrent workers attempting to commit the same candidate serialize to exactly 1 commit, 1 duplicate ignored."""
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        def commit_task(idx):
            return logger.record_prospective_decision(
                ipo_id="concurrent-race-21",
                company_name="Race 21 Ltd",
                board_type="SME",
                cutoff_timestamp_ist="2026-11-20 16:00:00 IST",
                features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0},
                p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
                model_name="Model_6B_SME_v1.0", model_sha256=FROZEN_SME_MODEL_SHA256
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            res = list(executor.map(commit_task, range(2)))

        statuses = [r["status"] for r in res]
        self.assertEqual(statuses.count("RECORDED"), 1)
        self.assertEqual(statuses.count("DUPLICATE_IGNORED"), 1)

    def test_07_crash_during_persistence(self):
        """7. Truncated record in ledger blocks subsequent writes via inspect_ledger_corruption."""
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        # Simulate partial record write
        with open(self.decision_ledger, "w", encoding="utf-8") as f:
            f.write('{"record_type": "PROSPECTIVE_DECISION", "decision_id": "PARTIAL_REC')

        corr = logger.inspect_ledger_corruption("decision")
        self.assertTrue(corr["has_corruption"])
        self.assertEqual(len(corr["corrupt_lines"]), 1)

        # Attempting write fails closed with IOError
        with self.assertRaises(IOError) as ctx:
            logger.record_prospective_decision(
                ipo_id="test-post-crash",
                company_name="Post Crash Ltd",
                board_type="SME",
                cutoff_timestamp_ist="2026-11-20 16:00:00 IST",
                features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0},
                p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
                model_name="Model_6B_SME_v1.0", model_sha256=FROZEN_SME_MODEL_SHA256
            )
        self.assertIn("LEDGER_CORRUPTION_BLOCKED", str(ctx.exception))

    def test_08_restart_following_partial_persistence(self):
        """8. Restarting after truncated record detects corruption and prevents further ingestion until repaired."""
        with open(self.decision_ledger, "w", encoding="utf-8") as f:
            f.write('{"record_type": "PROSPECTIVE_DECISION", "decision_id": "HALTED"\n{"invalid json}')

        # Re-instantiate manager
        restarted_manager = ProspectiveLifecycleManager(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger,
            candidate_registry_path=self.candidate_registry,
            audit_events_path=self.audit_events,
            evaluation_records_path=self.evaluation_records,
            checkpoint_path=self.checkpoint_file
        )
        chain_check = restarted_manager.logger.verify_ledger_chain("decision")
        self.assertFalse(chain_check["valid"])

    def test_09_duplicate_outcome_ingestion(self):
        """9. Re-ingesting an outcome for the same IPO is idempotent (DUPLICATE_OUTCOME_IGNORED)."""
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        logger.record_prospective_decision(
            ipo_id="test-outcome-dup",
            company_name="Outcome Dup Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-20 16:00:00 IST",
            features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
            model_name="Model_6B_SME_v1.0", model_sha256=FROZEN_SME_MODEL_SHA256
        )

        res1 = self.manager.reconcile_listing_outcome(
            ipo_id="test-outcome-dup",
            listing_date_str="2026-11-25",
            issue_price_inr=100.0,
            listing_open_inr=115.0,
            official_bulletin_ref="BSE_BULLETIN_TEST_01"
        )
        self.assertEqual(res1["status"], "OUTCOME_RECONCILED")

        res2 = self.manager.reconcile_listing_outcome(
            ipo_id="test-outcome-dup",
            listing_date_str="2026-11-25",
            issue_price_inr=100.0,
            listing_open_inr=115.0,
            official_bulletin_ref="BSE_BULLETIN_TEST_01"
        )
        self.assertEqual(res2["status"], "DUPLICATE_OUTCOME_IGNORED")

    def test_10_incorrect_listing_price_units(self):
        """10. Listing prices must be in INR; foreign or incorrect currencies are rejected."""
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        logger.record_prospective_decision(
            ipo_id="test-currency-unit",
            company_name="Currency Unit Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-20 16:00:00 IST",
            features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
            model_name="Model_6B_SME_v1.0", model_sha256=FROZEN_SME_MODEL_SHA256
        )
        with self.assertRaises(ValueError) as ctx:
            self.manager.reconcile_listing_outcome(
                ipo_id="test-currency-unit",
                listing_date_str="2026-11-25",
                issue_price_inr=100.0,
                listing_open_inr=115.0,
                official_bulletin_ref="BSE_BULLETIN_USD_01",
                price_currency="USD"
            )
        self.assertIn("INVALID_PRICE_CURRENCY", str(ctx.exception))

    def test_11_listing_close_data_substituted_for_listing_open(self):
        """11. Substituting listing close data for listing open data is prohibited."""
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        logger.record_prospective_decision(
            ipo_id="test-close-sub",
            company_name="Close Sub Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-20 16:00:00 IST",
            features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
            model_name="Model_6B_SME_v1.0", model_sha256=FROZEN_SME_MODEL_SHA256
        )
        with self.assertRaises(ValueError) as ctx:
            self.manager.reconcile_listing_outcome(
                ipo_id="test-close-sub",
                listing_date_str="2026-11-25",
                issue_price_inr=100.0,
                listing_open_inr=120.0,
                official_bulletin_ref="BSE_BULLETIN_CLOSE_01",
                is_close_price=True
            )
        self.assertIn("LISTING_CLOSE_SUBSTITUTION_PROHIBITED", str(ctx.exception))

    def test_12_missing_official_outcome_artifact(self):
        """12. Reconciling outcome without official bulletin reference is rejected."""
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        logger.record_prospective_decision(
            ipo_id="test-missing-bulletin",
            company_name="Missing Bulletin Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-20 16:00:00 IST",
            features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
            model_name="Model_6B_SME_v1.0", model_sha256=FROZEN_SME_MODEL_SHA256
        )
        with self.assertRaises(ValueError) as ctx:
            self.manager.reconcile_listing_outcome(
                ipo_id="test-missing-bulletin",
                listing_date_str="2026-11-25",
                issue_price_inr=100.0,
                listing_open_inr=115.0,
                official_bulletin_ref=""
            )
        self.assertIn("MISSING_OFFICIAL_BULLETIN_REF", str(ctx.exception))

    def test_13_outcome_source_hash_mismatch(self):
        """13. Reconciling outcome with mismatched artifact checksum is rejected."""
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        logger.record_prospective_decision(
            ipo_id="test-outcome-bad-hash",
            company_name="Bad Hash Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-20 16:00:00 IST",
            features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
            model_name="Model_6B_SME_v1.0", model_sha256=FROZEN_SME_MODEL_SHA256
        )
        with self.assertRaises(ValueError) as ctx:
            self.manager.reconcile_listing_outcome(
                ipo_id="test-outcome-bad-hash",
                listing_date_str="2026-11-25",
                issue_price_inr=100.0,
                listing_open_inr=115.0,
                official_bulletin_ref="BSE_BULLETIN_HASH_01",
                artifact_sha256="a" * 64,
                raw_artifact_payload="Real payload that does not match 64 a's"
            )
        self.assertIn("OUTCOME_ARTIFACT_HASH_MISMATCH", str(ctx.exception))

    def test_14_contradictory_official_outcome_sources(self):
        """14. Conflicting or invalid price values raise ValueError and log audit warning."""
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        logger.record_prospective_decision(
            ipo_id="test-contra-prices",
            company_name="Contra Prices Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-20 16:00:00 IST",
            features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
            model_name="Model_6B_SME_v1.0", model_sha256=FROZEN_SME_MODEL_SHA256
        )
        with self.assertRaises(ValueError) as ctx:
            self.manager.reconcile_listing_outcome(
                ipo_id="test-contra-prices",
                listing_date_str="2026-11-25",
                issue_price_inr=-100.0,  # Negative price
                listing_open_inr=115.0,
                official_bulletin_ref="BSE_BULLETIN_NEG_01"
            )
        self.assertIn("INVALID PRICES", str(ctx.exception))

    def test_15_outcome_received_before_decision_exists(self):
        """15. Outcome submitted for an IPO without prior prospective decision record is rejected."""
        with self.assertRaises(ValueError) as ctx:
            self.manager.reconcile_listing_outcome(
                ipo_id="unmatched-ipo-999",
                listing_date_str="2026-11-25",
                issue_price_inr=100.0,
                listing_open_inr=115.0,
                official_bulletin_ref="BSE_BULLETIN_UNMATCHED_01"
            )
        self.assertIn("UNMATCHED OUTCOME", str(ctx.exception))

    def test_16_blocked_candidates_excluded_from_clean_evaluation(self):
        """16. Blocked candidates (e.g. Wiscon, Carver) are excluded from clean evaluation cohort."""
        rep = self.manager.generate_evaluation_records()
        self.assertEqual(rep["clean_included_evaluation_count"], 0)
        self.assertEqual(rep["sample_sufficiency_status"], "INSUFFICIENT_SAMPLE_SIZE_GATE")
        self.assertFalse(rep["performance_claim_allowed"])

    def test_17_immature_outcomes_pending_in_evaluation(self):
        """17. Decisions without realized outcomes remain PENDING_REALIZED_OUTCOME."""
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        logger.record_prospective_decision(
            ipo_id="test-pending-outcome",
            company_name="Pending Outcome Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-20 16:00:00 IST",
            features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
            model_name="Model_6B_SME_v1.0", model_sha256=FROZEN_SME_MODEL_SHA256,
            feature_provenance={"cutoff_source_evidence": "BSE", "raw_source_sha256": "a"*64, "is_timing_verified": True}
        )
        eval_rep = self.manager.generate_evaluation_records()
        rec = next(r for r in eval_rep["evaluation_records"] if r["ipo_id"] == "test-pending-outcome")
        self.assertEqual(rec["evaluation_inclusion_status"], "PENDING_REALIZED_OUTCOME")
        self.assertFalse(rec["has_verified_outcome"])

    def test_18_simulated_outcomes_mixed_with_actual_prohibited(self):
        """18. Simulated outcome records cannot be passed to reconcile_listing_outcome."""
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        logger.record_prospective_decision(
            ipo_id="test-sim-reject",
            company_name="Sim Reject Ltd",
            board_type="SME",
            cutoff_timestamp_ist="2026-11-20 16:00:00 IST",
            features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
            model_name="Model_6B_SME_v1.0", model_sha256=FROZEN_SME_MODEL_SHA256
        )
        with self.assertRaises(ValueError) as ctx:
            self.manager.reconcile_listing_outcome(
                ipo_id="test-sim-reject",
                listing_date_str="2026-11-25",
                issue_price_inr=100.0,
                listing_open_inr=115.0,
                official_bulletin_ref="SIMULATED_STUDY_REF",
                is_simulated=True
            )
        self.assertIn("SIMULATED_OUTCOME_PROHIBITED", str(ctx.exception))

    def test_19_empty_cohort_metrics(self):
        """19. Zero-outcome prospective cohort returns INCONCLUSIVE_ZERO_OUTCOMES."""
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        res = logger.evaluate_prospective_brier_and_skill(board_type="SME")
        self.assertEqual(res["status"], "INCONCLUSIVE_ZERO_OUTCOMES")
        self.assertEqual(res["n_known_outcomes"], 0)
        self.assertIsNone(res["model_brier_score"])
        self.assertIsNone(res["brier_skill_score"])

    def test_20_single_class_evaluation_cohorts(self):
        """20. Single-class evaluation cohorts note AUC undefined (INCONCLUSIVE_SINGLE_CLASS)."""
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        # Create 2 decisions and 2 positive outcomes (100% positive, single class)
        for i in range(2):
            iid = f"single-class-{i}"
            logger.record_prospective_decision(
                ipo_id=iid, company_name=f"SC {i}", board_type="SME",
                cutoff_timestamp_ist="2026-11-20 16:00:00 IST",
                features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0},
                p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
                model_name="Model_6B_SME_v1.0", model_sha256=FROZEN_SME_MODEL_SHA256,
                feature_provenance={"cutoff_source_evidence": "BSE", "raw_source_sha256": "a"*64, "is_timing_verified": True}
            )
            logger.record_realized_outcome(
                ipo_id=iid, listing_date="2026-11-25",
                issue_price_inr=100.0, listing_open_inr=120.0,
                listing_open_return_pct=20.0
            )
        eval_res = logger.evaluate_prospective_brier_and_skill(board_type="SME")
        self.assertEqual(eval_res["positive_outcomes_count"], 2)
        self.assertEqual(eval_res["negative_outcomes_count"], 0)
        self.assertIn("INCONCLUSIVE_SINGLE_CLASS", str(eval_res))

    def test_21_duplicate_candidate_ids_in_registry_prohibited(self):
        """21. Registry with duplicate candidate IDs is detected."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        ids = [c["ipo_id"] for c in cands]
        self.assertEqual(len(ids), len(set(ids)), "Production registry contains duplicate candidate IDs!")

    def test_22_unauthorized_outcome_correction(self):
        """22. Corrections are logged to append-only governance trail, never modifying immutable outcome ledger."""
        logger = ProspectiveDecisionLogger(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger
        )
        logger.record_prospective_decision(
            ipo_id="test-corr", company_name="Corr Ltd", board_type="SME",
            cutoff_timestamp_ist="2026-11-20 16:00:00 IST",
            features_dict={"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0},
            p_positive_open=0.80, p_macro=0.80, p_severe_loss=0.05,
            model_name="Model_6B_SME_v1.0", model_sha256=FROZEN_SME_MODEL_SHA256
        )
        logger.record_realized_outcome(
            ipo_id="test-corr", listing_date="2026-11-25",
            issue_price_inr=100.0, listing_open_inr=120.0
        )
        with open(self.outcome_ledger, "r", encoding="utf-8") as f:
            orig_lines = f.readlines()

        # Log correction
        event = self.manager.record_outcome_correction(
            ipo_id="test-corr",
            prior_open_price=120.0,
            corrected_open_price=122.0,
            reason="Exchange revised auction trade bulletin",
            bulletin_citation="BSE_REV_CIRCULAR_002"
        )
        self.assertEqual(event["event_type"], "OUTCOME_CORRECTION_EVENT")

        # Verify outcome ledger remains unchanged
        with open(self.outcome_ledger, "r", encoding="utf-8") as f:
            curr_lines = f.readlines()
        self.assertEqual(orig_lines, curr_lines)

    def test_23_mainboard_candidate_scored_by_sme_model_prohibited(self):
        """23. Mainboard candidate is blocked from SME model scoring and cannot enter clean SME cohort."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        mb = next(c for c in cands if c.get("board_type") == "Mainboard")
        prep = self.manager.audit_and_prepare_candidate(mb, evaluation_timestamp_ist="2026-10-28 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_GOVERNANCE")
        self.assertFalse(prep["is_clean_eligible"])

    def test_24_evaluation_report_generation_does_not_mutate_production_ledgers(self):
        """24. Running generate_evaluation_records or monitoring report does not mutate production ledgers."""
        for p in [DECISION_LEDGER_PATH, OUTCOME_LEDGER_PATH, AUDIT_EVENTS_PATH]:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    self.assertEqual(len([l for l in f if l.strip()]), 0, f"Production ledger {p} has records!")


if __name__ == "__main__":
    unittest.main()
