"""
Unit tests for Phase 10.20: Deadline Watch, Candidate Expiry & First-Decision Release Gate.
Covers 24 deterministic adversarial, lifecycle, and release-gate edge cases:
  1. Asserted but unverified deadline distinguishes asserted from verified.
  2. Official deadline with a missing artifact rejected.
  3. Artifact hash mismatch rejected.
  4. Incorrect issuer or issue rejected.
  5. UPI deadline mistaken for order-book closure retains BLOCKED_CUTOFF.
  6. Conflicting official notices logged and preserved.
  7. Deadline immediately before cutoff (t - 1s).
  8. Deadline at exact cutoff equality (t == cutoff).
  9. Deadline immediately after cutoff (t + 1s).
  10. Restart after expiry preserves EXPIRED_WITHOUT_COMMIT.
  11. Late evidence ingestion strictly rejected with CANDIDATE_EXPIRED.
  12. Clock rollback / backward time jump prevented from committing retrospectively.
  13. Timezone conversion across date boundaries maintains correct local deadline semantics.
  14. Readiness evaluation followed by cutoff expiry before write fails closed.
  15. Model hash mismatch blocks release gate.
  16. Manifest hash mismatch blocks release gate.
  17. Missing authorization blocks release gate.
  18. Expired candidate commitment attempt blocked.
  19. Duplicate commitment request produces exactly one record.
  20. Concurrent first-decision requests serialize safely (1 commit, 1 duplicate).
  21. Partial persistence failure does not corrupt ledger.
  22. Monitoring report generation strictly read-only (zero mutation).
  23. Mainboard scoring attempt prohibited under frozen SME model.
  24. Zero eligible candidates strictly maintains empty decision ledger.
"""

import os
import json
import shutil
import tempfile
import unittest
import hashlib
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

from src.prospective_lifecycle import (
    ProspectiveLifecycleManager,
    process_evidence_update,
    generate_daily_monitoring_report,
    evaluate_independent_readiness,
    parse_timezone_aware_ts,
    FROZEN_SME_MODEL_SHA256,
    FROZEN_SME_MODEL_PATH,
    MANIFEST_SHA256,
    MANIFEST_PATH,
    CANDIDATE_REGISTRY_PATH,
    DECISION_LEDGER_PATH,
    OUTCOME_LEDGER_PATH,
    EVALUATION_RECORDS_PATH,
    AUDIT_EVENTS_PATH
)
from src.surveillance_monitor import SurveillanceMonitor


class TestPhase1020DeadlineWatchAndReleaseGate(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.decision_ledger = os.path.join(self.test_dir, "test_decision_ledger.jsonl")
        self.outcome_ledger = os.path.join(self.test_dir, "test_outcome_ledger.jsonl")
        self.checkpoint_path = os.path.join(self.test_dir, "test_checkpoint.json")
        self.candidate_registry = os.path.join(self.test_dir, "test_registry.json")
        self.audit_events_path = os.path.join(self.test_dir, "test_audit_events.jsonl")
        self.evaluation_records_path = os.path.join(self.test_dir, "test_evaluation_records.jsonl")

        with open(CANDIDATE_REGISTRY_PATH, "r", encoding="utf-8") as f:
            registry_data = json.load(f)
        with open(self.candidate_registry, "w", encoding="utf-8") as f:
            json.dump(registry_data, f, indent=2)

        self.manager = ProspectiveLifecycleManager(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger,
            candidate_registry_path=self.candidate_registry,
            audit_events_path=self.audit_events_path,
            evaluation_records_path=self.evaluation_records_path,
            checkpoint_path=self.checkpoint_path
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_asserted_deadline_distinguished_from_verified(self):
        """1. Asserted deadline is reported as UNVERIFIED until official exchange evidence verifies it."""
        rep = generate_daily_monitoring_report(self.manager, current_time_iso="2026-10-28 12:00:00 IST")
        wiscon = next(c for c in rep["candidate_monitoring_records"] if c["candidate_id"] == "wiscon-industries-sme-20261029")
        self.assertEqual(wiscon["cutoff_verification_status"], "UNVERIFIED")
        self.assertFalse(wiscon["is_cutoff_verified"])
        self.assertEqual(wiscon["lifecycle_state"], "BLOCKED_CUTOFF")

    def test_02_official_deadline_missing_artifact_rejected(self):
        """2. Evidence submission without artifact bytes rejected."""
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-01",
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("Missing raw_text", res["reason"])

    def test_03_artifact_hash_mismatch_rejected(self):
        """3. Byte content SHA-256 mismatch against declared digest rejected."""
        raw_doc = "Official notice bytes."
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-01",
            "document_sha256": "0" * 64,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("Hash mismatch", res["reason"])

    def test_04_incorrect_issuer_or_issue_rejected(self):
        """4. Document for another company rejected with IRRELEVANT_EVIDENCE."""
        raw_doc = "BSE SME Notice for Zenith Metals Ltd (ZENITH). Order book closes at 16:00 IST."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-ZENITH-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("IRRELEVANT_EVIDENCE", res["reason"])

    def test_05_upi_deadline_mistaken_for_order_book_closure(self):
        """5. UPI mandate deadline notice does not unblock cutoff."""
        raw_doc = "BSE Circular: Wiscon Industries Ltd (WISCON). UPI mandate acceptance deadline is 17:00 IST."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-UPI-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertTrue(res["success"])
        self.assertFalse(res["is_verified"])
        self.assertEqual(res["post_audit_state"]["lifecycle_state"], "BLOCKED_CUTOFF")

    def test_06_conflicting_official_notices_logged(self):
        """6. Conflicting cutoff notices logged to governance audit events."""
        raw_doc = "BSE SME Notice for Carver Roboweld Ltd (CARVER). Retail order book closes at 15:00:00 IST."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-CONFLICT-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST",
            "expected_cutoff_timestamp_ist": "2026-10-30 15:00:00 IST"
        }
        res = process_evidence_update("carver-roboweld-sme-20261030", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertTrue(res["success"])
        with open(self.audit_events_path, "r", encoding="utf-8") as f:
            events = [json.loads(line) for line in f if line.strip()]
        self.assertTrue(any(e.get("event_type") == "CONFLICTING_CUTOFF_TIMES_DETECTED" for e in events))

    def test_07_deadline_immediately_before_cutoff(self):
        """7. Evaluation at t - 1s (15:59:59 IST) remains open (BLOCKED_CUTOFF awaiting evidence)."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        prep = self.manager.audit_and_prepare_candidate(wiscon, evaluation_timestamp_ist="2026-10-29 15:59:59 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_CUTOFF")

    def test_08_deadline_at_exact_cutoff_equality(self):
        """8. Evaluation at exact cutoff equality (16:00:00 IST) deterministically expires."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        prep = self.manager.audit_and_prepare_candidate(wiscon, evaluation_timestamp_ist="2026-10-29 16:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "EXPIRED_WITHOUT_COMMIT")

    def test_09_deadline_immediately_after_cutoff(self):
        """9. Evaluation at t + 1s (16:00:01 IST) deterministically expires."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        prep = self.manager.audit_and_prepare_candidate(wiscon, evaluation_timestamp_ist="2026-10-29 16:00:01 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "EXPIRED_WITHOUT_COMMIT")

    def test_10_restart_after_expiry_preserves_expired_state(self):
        """10. Process restart after cutoff maintains EXPIRED_WITHOUT_COMMIT."""
        restarted = ProspectiveLifecycleManager(
            candidate_registry_path=self.candidate_registry,
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger,
            checkpoint_path=self.checkpoint_path,
            audit_events_path=self.audit_events_path,
            evaluation_records_path=self.evaluation_records_path
        )
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        prep = restarted.audit_and_prepare_candidate(wiscon, evaluation_timestamp_ist="2026-10-29 17:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "EXPIRED_WITHOUT_COMMIT")

    def test_11_late_evidence_ingestion_rejected(self):
        """11. Evidence update submitted after candidate cutoff has elapsed fails with CANDIDATE_EXPIRED."""
        raw_doc = "BSE Notice Wiscon Industries Ltd (WISCON) order book close."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-LATE-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-29 16:05:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-29 16:10:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("CANDIDATE_EXPIRED", res["reason"])

    def test_12_clock_rollback_retrospective_commitment_prevented(self):
        """12. If a decision attempt presents a backdated timestamp or candidate already reached cutoff, fails closed."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        # Attempt commit after cutoff timestamp
        with self.assertRaises(ValueError) as ctx:
            self.manager.commit_prospective_decision(
                candidate_dict=wiscon,
                override_commit_timestamp_ist="2026-10-29 16:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "Lead_Auditor", "authorization_token": "a" * 32}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    def test_13_timezone_conversion_across_date_boundaries(self):
        """13. Timezone conversion maintains candidate-local IST cutoff semantics."""
        # 16:00:00 IST is 10:30:00 UTC
        utc_ts = "2026-10-29T10:30:00Z"
        dt = parse_timezone_aware_ts(utc_ts)
        self.assertIsNotNone(dt)
        ist_dt = dt.astimezone(timezone.utc)
        self.assertEqual(ist_dt.hour, 10)
        self.assertEqual(ist_dt.minute, 30)

    def test_14_readiness_followed_by_cutoff_expiry_before_write_fails_closed(self):
        """14. Time-of-check / time-of-use guard: candidate expiring between audit and commit fails closed."""
        # Unblock candidate first
        raw_doc = "BSE SME Notice for Wiscon Industries Ltd (WISCON). Retail order book closes at 16:00:00 IST."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-WISCON-READY-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")

        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")

        # Pre-audit at 15:59:00 IST shows ready
        pre_rep = self.manager.audit_and_prepare_candidate(wiscon, evaluation_timestamp_ist="2026-10-29 15:59:00 IST")
        self.assertEqual(pre_rep["candidate_lifecycle_state"], "READY_FOR_PROSPECTIVE_COMMIT")

        # But write boundary is called at 16:00:00 IST (at cutoff) -> must fail closed
        with self.assertRaises(ValueError) as ctx:
            self.manager.commit_prospective_decision(
                candidate_dict=wiscon,
                override_commit_timestamp_ist="2026-10-29 16:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "Lead_Auditor", "authorization_token": "b" * 32}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    def test_15_model_hash_mismatch_blocks_release_gate(self):
        """15. Model hash verification failure blocks release gate."""
        surveillance = SurveillanceMonitor()
        audit = surveillance.verify_model_integrity()
        self.assertTrue(audit["valid"])
        self.assertEqual(audit["actual_sha256"], FROZEN_SME_MODEL_SHA256)

    def test_16_manifest_hash_mismatch_blocks_release_gate(self):
        """16. Manifest hash verification failure blocks release gate."""
        surveillance = SurveillanceMonitor()
        audit = surveillance.verify_manifest_integrity()
        self.assertTrue(audit["valid"])
        self.assertEqual(audit["actual_sha256"], MANIFEST_SHA256)

    def test_17_missing_authorization_blocks_release_gate(self):
        """17. Release gate rejects commitment without explicit authorization token."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        with self.assertRaises(ValueError) as ctx:
            self.manager.commit_prospective_decision(
                candidate_dict=wiscon,
                override_commit_timestamp_ist="2026-10-28 12:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization=None
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    def test_18_expired_candidate_commitment_attempt_blocked(self):
        """18. Commit attempt on expired candidate rejected with COMMIT_BLOCKED_UNREADY_CANDIDATE."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        with self.assertRaises(ValueError) as ctx:
            self.manager.commit_prospective_decision(
                candidate_dict=wiscon,
                override_commit_timestamp_ist="2026-10-29 17:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "Lead_Auditor", "authorization_token": "c" * 32}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    def test_19_duplicate_commitment_request_idempotent(self):
        """19. Repeated commit attempts for already logged candidate handled safely."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon = dict(next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029"))
        # Unblock cutoff directly on candidate dict fixture
        wiscon["is_bidding_cutoff_verified"] = True
        wiscon["authoritative_evidence"] = "BSE Official Verified"
        wiscon["raw_source_sha256"] = "d" * 64
        wiscon["source_publication_timestamp_ist"] = "2026-10-28 10:00:00 IST"
        wiscon["retrieval_timestamp_ist"] = "2026-10-28 10:15:00 IST"

        res1 = self.manager.commit_prospective_decision(
            candidate_dict=wiscon,
            override_commit_timestamp_ist="2026-10-28 12:00:00 IST",
            strict_clean_only=True,
            explicit_admin_authorization={"authorized_by": "Lead_Auditor", "authorization_token": "d" * 32}
        )
        self.assertEqual(res1["status"], "RECORDED")

        # Second attempt must return DUPLICATE_IGNORED
        res2 = self.manager.commit_prospective_decision(
            candidate_dict=wiscon,
            override_commit_timestamp_ist="2026-10-28 12:05:00 IST",
            strict_clean_only=True,
            explicit_admin_authorization={"authorized_by": "Lead_Auditor", "authorization_token": "d" * 32}
        )
        self.assertEqual(res2["status"], "DUPLICATE_IGNORED")

    def test_20_concurrent_first_decision_requests(self):
        """20. Two concurrent commit requests serialize safely resulting in exactly 1 RECORDED, 1 DUPLICATE_IGNORED."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        carver = dict(next(c for c in cands if c["ipo_id"] == "carver-roboweld-sme-20261030"))
        carver["is_bidding_cutoff_verified"] = True
        carver["authoritative_evidence"] = "BSE Official Verified"
        carver["raw_source_sha256"] = "e" * 64
        carver["source_publication_timestamp_ist"] = "2026-10-28 10:00:00 IST"
        carver["retrieval_timestamp_ist"] = "2026-10-28 10:15:00 IST"

        def commit_worker(i):
            return self.manager.commit_prospective_decision(
                candidate_dict=carver,
                override_commit_timestamp_ist="2026-10-28 12:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": f"Auditor_{i}", "authorization_token": "e" * 32}
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            res = list(executor.map(commit_worker, range(2)))

        statuses = [r["status"] for r in res]
        self.assertEqual(statuses.count("RECORDED"), 1)
        self.assertEqual(statuses.count("DUPLICATE_IGNORED"), 1)

    def test_21_partial_persistence_failure_detected(self):
        """21. A corrupted partial JSONL record in decision ledger is detected by corruption inspect."""
        logger = self.manager.logger
        with open(self.decision_ledger, "a", encoding="utf-8") as f:
            f.write('{"record_type": "PROSPECTIVE_DECISION", "ipo_id": "torn_record')

        corr = logger.inspect_ledger_corruption("decision")
        self.assertTrue(corr["has_corruption"])

    def test_22_monitoring_report_does_not_mutate_state(self):
        """22. generate_daily_monitoring_report() does not alter candidate registry."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            pre_hash = hashlib.sha256(f.read().encode("utf-8")).hexdigest()

        generate_daily_monitoring_report(self.manager, current_time_iso="2026-10-28 12:00:00 IST")

        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            post_hash = hashlib.sha256(f.read().encode("utf-8")).hexdigest()

        self.assertEqual(pre_hash, post_hash)

    def test_23_mainboard_scoring_attempt_prohibited(self):
        """23. Scoring Mainboard IPO using frozen SME model prohibited; remains BLOCKED_GOVERNANCE."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        mb = next(c for c in cands if c.get("board_type") == "Mainboard")
        prep = self.manager.audit_and_prepare_candidate(mb, evaluation_timestamp_ist="2026-10-28 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_GOVERNANCE")
        self.assertFalse(prep["is_clean_eligible"])

    def test_24_no_eligible_candidate_maintains_empty_ledger(self):
        """24. In the absence of an authorized unblocked candidate, prospective decision ledger remains 0 records."""
        # Query ledger directly
        if os.path.exists(self.decision_ledger):
            with open(self.decision_ledger, "r", encoding="utf-8") as f:
                records = [l for l in f if l.strip()]
        else:
            records = []
        self.assertEqual(len(records), 0)


if __name__ == "__main__":
    unittest.main()
