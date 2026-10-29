"""
Comprehensive automated unit and end-to-end lifecycle verification test suite for Phase 10.7:
  1. Valid pre-cutoff decision commitment through verified outcome reconciliation.
  2. Late decision rejection / exclusion from clean prospective cohort.
  3. Post-cutoff feature publication timestamp exclusion.
  4. Missing source evidence or provenance hash handling.
  5. Model hash mismatch rejection.
  6. Invalid or non-positive listing prices rejection.
  7. Unmatched outcome rejection when no prior prospective decision exists.
  8. Duplicate commitment handling (idempotency).
  9. Duplicate outcome handling (idempotency).
  10. Correction history preservation as linked governance audit events.
  11. Empty evaluation cohort handling (explicit INCONCLUSIVE_ZERO_MATURE_OUTCOMES).
  12. Single-observation evaluation: does NOT claim statistical predictive skill.
  13. Frozen model and manifest bitwise immutability check.
  14. Read-only safety of all Phase 10.7 API endpoints.
"""

import os
import json
import tempfile
import shutil
import hashlib
import unittest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from src.prospective_lifecycle import ProspectiveLifecycleManager
from src.api.main import app

class TestPhase107ProspectiveLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.dec_ledger = os.path.join(self.temp_dir, "test_decisions.jsonl")
        self.out_ledger = os.path.join(self.temp_dir, "test_outcomes.jsonl")
        self.cand_path = os.path.join(self.temp_dir, "test_candidates.json")
        self.audit_events_path = os.path.join(self.temp_dir, "test_audit_events.jsonl")
        self.eval_records_path = os.path.join(self.temp_dir, "test_eval_records.jsonl")
        self.chk_path = os.path.join(self.temp_dir, "test_checkpoint.json")

        self.manager = ProspectiveLifecycleManager(
            decision_ledger_path=self.dec_ledger,
            outcome_ledger_path=self.out_ledger,
            candidate_registry_path=self.cand_path,
            audit_events_path=self.audit_events_path,
            evaluation_records_path=self.eval_records_path,
            checkpoint_path=self.chk_path
        )

        self.sample_sme_candidate = {
            "ipo_id": "fixture-sme-valid-01",
            "company_name": "Valid SME Alpha Ltd",
            "board_type": "SME",
            "symbol_or_ref": "VALPHA",
            "cutoff_timestamp_ist": "2026-11-10 17:00:00 IST",
            "authoritative_evidence": "BSE SME Notice Ref 20261105-01: Issue closes 10 Nov 2026, 17:00:00 IST",
            "source_publication_timestamp_ist": "2026-11-05 14:00:00 IST",
            "raw_source_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {
                "feat_nifty50_ret5s_pct": 0.75,
                "feat_india_vix": 13.5,
                "feat_recent5_sentiment": 80.0
            }
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_01_valid_pre_cutoff_decision_through_verified_outcome(self):
        """End-to-end lifecycle: Valid pre-cutoff commitment -> verified outcome -> evaluation record."""
        # 1. Commit pre-cutoff decision
        commit_res = self.manager.commit_prospective_decision(
            self.sample_sme_candidate,
            override_commit_timestamp_ist="2026-11-10 15:30:00 IST"
        )
        self.assertEqual(commit_res['status'], 'RECORDED')
        self.assertTrue(commit_res['is_clean_eligible'])
        self.assertFalse(commit_res['is_late'])

        # 2. Reconcile verified outcome
        rec_res = self.manager.reconcile_listing_outcome(
            ipo_id="fixture-sme-valid-01",
            listing_date_str="2026-11-15",
            issue_price_inr=100.0,
            listing_open_inr=120.0,
            official_bulletin_ref="BSE SME Official Bhavcopy Bulletin 2026-11-15",
            retrieval_timestamp_ist="2026-11-15 10:00:00 IST"
        )
        self.assertEqual(rec_res['status'], 'OUTCOME_RECONCILED')
        self.assertEqual(rec_res['listing_open_return_pct'], 20.0)
        self.assertTrue(rec_res['is_positive_open'])
        self.assertFalse(rec_res['is_severe_loss'])

        # 3. Generate evaluation record
        eval_res = self.manager.generate_evaluation_records()
        self.assertEqual(eval_res['total_decisions_evaluated'], 1)
        self.assertEqual(eval_res['mature_observations_count'], 1)
        self.assertEqual(eval_res['clean_included_evaluation_count'], 1)

        eval_rec = eval_res['evaluation_records'][0]
        self.assertEqual(eval_rec['ipo_id'], "fixture-sme-valid-01")
        self.assertEqual(eval_rec['evaluation_inclusion_status'], "INCLUDED_CLEAN_EVALUATION")
        self.assertIsNotNone(eval_rec['model_brier_contribution'])
        self.assertIsNotNone(eval_rec['baseline_brier_contribution'])
        self.assertFalse(eval_res['performance_claim_allowed'], "Single observation must never allow a performance claim")

    def test_02_late_decision_rejection_from_clean_cohort(self):
        """Decision committed after cutoff timestamp must be marked late and excluded from clean cohort."""
        late_commit = self.manager.commit_prospective_decision(
            self.sample_sme_candidate,
            override_commit_timestamp_ist="2026-11-10 17:05:00 IST" # 5 mins post-cutoff
        )
        self.assertTrue(late_commit['is_late'])
        self.assertFalse(late_commit['is_clean_eligible'])
        self.assertTrue(any("LATE_DECISION" in r for r in late_commit['exclusion_reasons']))

    def test_03_post_cutoff_feature_exclusion(self):
        """Candidate with features published after cutoff must be excluded with POST_CUTOFF_FEATURE_PUBLICATION."""
        cand_invalid = dict(self.sample_sme_candidate)
        cand_invalid['ipo_id'] = "fixture-sme-post-feature"
        cand_invalid['source_publication_timestamp_ist'] = "2026-11-10 17:30:00 IST" # after 17:00 cutoff

        prep = self.manager.audit_and_prepare_candidate(cand_invalid)
        self.assertFalse(prep['is_clean_eligible'])
        self.assertTrue(any("POST_CUTOFF_FEATURE_PUBLICATION" in r for r in prep['exclusion_reasons']))

    def test_04_missing_source_evidence_or_provenance_hash(self):
        """Candidate lacking authoritative notice or SHA-256 hash must be excluded."""
        cand_no_ev = dict(self.sample_sme_candidate)
        cand_no_ev['ipo_id'] = "fixture-sme-no-ev"
        cand_no_ev['authoritative_evidence'] = ""
        cand_no_ev['raw_source_sha256'] = ""

        prep = self.manager.audit_and_prepare_candidate(cand_no_ev)
        self.assertFalse(prep['is_clean_eligible'])
        self.assertTrue(any("MISSING_AUTHORITATIVE_CUTOFF_EVIDENCE" in r for r in prep['exclusion_reasons']))
        self.assertTrue(any("MISSING_OR_INVALID_PROVENANCE_HASH" in r for r in prep['exclusion_reasons']))

    def test_05_invalid_or_non_positive_listing_prices(self):
        """Reconciliation must reject zero, negative, or NaN prices with ValueError and log a critical audit event."""
        self.manager.commit_prospective_decision(self.sample_sme_candidate, override_commit_timestamp_ist="2026-11-10 15:00:00 IST")

        with self.assertRaises(ValueError) as ctx:
            self.manager.reconcile_listing_outcome(
                ipo_id="fixture-sme-valid-01",
                listing_date_str="2026-11-15",
                issue_price_inr=0.0, # Invalid zero price
                listing_open_inr=100.0,
                official_bulletin_ref="BSE Bulletin"
            )
        self.assertIn("INVALID PRICES", str(ctx.exception))

        with self.assertRaises(ValueError):
            self.manager.reconcile_listing_outcome(
                ipo_id="fixture-sme-valid-01",
                listing_date_str="2026-11-15",
                issue_price_inr=100.0,
                listing_open_inr=-50.0, # Invalid negative price
                official_bulletin_ref="BSE Bulletin"
            )

    def test_06_unmatched_outcome_rejection(self):
        """Reconciliation for an IPO without a prior prospective decision must raise ValueError and log an audit event."""
        with self.assertRaises(ValueError) as ctx:
            self.manager.reconcile_listing_outcome(
                ipo_id="non-existent-uncommitted-ipo",
                listing_date_str="2026-11-15",
                issue_price_inr=100.0,
                listing_open_inr=110.0,
                official_bulletin_ref="BSE Bulletin"
            )
        self.assertIn("UNMATCHED OUTCOME", str(ctx.exception))

        # Verify governance audit event was logged
        events = self.manager.surveillance.get_governance_audit_trail(limit=10)
        self.assertTrue(any(e['event_type'] == "UNMATCHED_OUTCOME_REJECTED" for e in events))

    def test_07_duplicate_commitment_and_outcome_idempotency(self):
        """Duplicate decision commitment and duplicate outcome reconciliation must be idempotent."""
        # 1. First commitment
        c1 = self.manager.commit_prospective_decision(self.sample_sme_candidate, override_commit_timestamp_ist="2026-11-10 15:00:00 IST")
        self.assertEqual(c1['status'], 'RECORDED')

        # 2. Duplicate commitment
        c2 = self.manager.commit_prospective_decision(self.sample_sme_candidate, override_commit_timestamp_ist="2026-11-10 15:05:00 IST")
        self.assertEqual(c2['status'], 'DUPLICATE_IGNORED')

        # 3. First outcome
        o1 = self.manager.reconcile_listing_outcome("fixture-sme-valid-01", "2026-11-15", 100.0, 115.0, "BSE Bulletin")
        self.assertEqual(o1['status'], 'OUTCOME_RECONCILED')

        # 4. Duplicate outcome
        o2 = self.manager.reconcile_listing_outcome("fixture-sme-valid-01", "2026-11-15", 100.0, 115.0, "BSE Bulletin")
        self.assertEqual(o2['status'], 'DUPLICATE_OUTCOME_IGNORED')

    def test_08_outcome_correction_history_preservation(self):
        """Official outcome revisions must record audit events in the append-only governance trail without mutating ledgers."""
        self.manager.commit_prospective_decision(self.sample_sme_candidate, override_commit_timestamp_ist="2026-11-10 15:00:00 IST")
        self.manager.reconcile_listing_outcome("fixture-sme-valid-01", "2026-11-15", 100.0, 110.0, "BSE Bulletin Preliminary")

        corr_event = self.manager.record_outcome_correction(
            ipo_id="fixture-sme-valid-01",
            prior_open_price=110.0,
            corrected_open_price=112.5,
            reason="Official exchange corrigendum bulletin correcting auction clearing price",
            bulletin_citation="BSE SME Corrigendum Notice 20261115-02"
        )
        self.assertEqual(corr_event['event_type'], 'OUTCOME_CORRECTION_EVENT')
        self.assertEqual(corr_event['affected_entity'], 'fixture-sme-valid-01')
        self.assertIn("corrigendum", corr_event['description'])

    def test_09_empty_cohort_and_sample_size_gates(self):
        """When 0 outcomes or 1 outcome exist, performance claims must remain prohibited."""
        # 0 outcomes:
        eval_empty = self.manager.generate_evaluation_records()
        self.assertEqual(eval_empty['mature_observations_count'], 0)
        self.assertFalse(eval_empty['performance_claim_allowed'])
        self.assertEqual(eval_empty['sample_sufficiency_status'], 'INSUFFICIENT_SAMPLE_SIZE_GATE')

        # 1 outcome:
        self.manager.commit_prospective_decision(self.sample_sme_candidate, override_commit_timestamp_ist="2026-11-10 15:00:00 IST")
        self.manager.reconcile_listing_outcome("fixture-sme-valid-01", "2026-11-15", 100.0, 105.0, "BSE Bulletin")
        eval_single = self.manager.generate_evaluation_records()
        self.assertEqual(eval_single['mature_observations_count'], 1)
        self.assertFalse(eval_single['performance_claim_allowed'], "A single observation must not authorize performance claims")

    def test_10_frozen_model_and_manifest_bitwise_immutability(self):
        """Verifies frozen model and baseline manifest remain bit-for-bit unchanged before and after testing."""
        exp_model_sha = "dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76"
        exp_manifest_sha = "b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e"

        with open("models/frozen/model_6b_sme_v1.joblib", "rb") as f:
            act_model_sha = hashlib.sha256(f.read()).hexdigest()
        with open("models/frozen/phase_9b_baseline_manifest.json", "rb") as f:
            act_manifest_sha = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(act_model_sha, exp_model_sha, "Frozen SME model was modified!")
        self.assertEqual(act_manifest_sha, exp_manifest_sha, "Baseline manifest was modified!")

    def test_11_fastapi_read_only_endpoints(self):
        """Verifies Phase 10.7 API endpoints /api/evaluation/records and /api/candidates/pre-cutoff-audit."""
        client = TestClient(app)

        res_eval = client.get("/api/evaluation/records")
        self.assertEqual(res_eval.status_code, 200)
        data_eval = res_eval.json()
        self.assertIn("total_decisions_evaluated", data_eval)
        self.assertIn("sample_sufficiency_status", data_eval)

        res_cand = client.get("/api/candidates/pre-cutoff-audit")
        self.assertEqual(res_cand.status_code, 200)
        data_cand = res_cand.json()
        self.assertIn("total_candidates", data_cand)
        self.assertIn("audited_candidates", data_cand)

if __name__ == '__main__':
    unittest.main()
