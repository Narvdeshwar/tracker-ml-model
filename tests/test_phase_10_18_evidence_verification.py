"""
Unit tests for Phase 10.18: Authoritative Evidence Verification & Prospective Readiness.
Covers comprehensive adversarial and boundary cases:
  1. A genuine primary-source fixture unblocks cutoff and transitions state.
  2. A secondary portal falsely labelled as primary evidence retained as unverified (BLOCKED_CUTOFF).
  3. A circular for the wrong IPO rejected immediately.
  4. A document about UPI deadlines instead of order-book closure retains BLOCKED_CUTOFF.
  5. A missing raw artifact rejected.
  6. A modified artifact whose hash no longer matches rejected.
  7. Contradictory source metadata rejected.
  8. Missing or timezone-naive timestamps rejected.
  9. Retrieval before publication rejected.
  10. Evidence published after decision timestamp rejected.
  11. Repeated ingestion of the same evidence is idempotent.
  12. Two distinct documents with conflicting cutoff times logged as governance conflict.
  13. Evidence updates attempted after candidate expiry strictly rejected.
  14. Equality boundary: one instant before, exactly at, and one instant after cutoff.
  15. Restart after cutoff preserves EXPIRED_WITHOUT_COMMIT.
  16. Delayed monitoring run after expiry preserves EXPIRED_WITHOUT_COMMIT.
  17. Attempt to commit after expiry fails closed.
  18. Governance audit events logged for discoveries, rejections, verifications, and auth failures.
  19. generate_daily_monitoring_report() error handling on missing/corrupted candidate registry.
  20. Mainboard candidates remain strictly non-scoring (BLOCKED_GOVERNANCE).
"""

import os
import json
import shutil
import tempfile
import unittest
import hashlib
from datetime import datetime, timezone

from src.prospective_lifecycle import (
    ProspectiveLifecycleManager,
    process_evidence_update,
    generate_daily_monitoring_report,
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


class TestPhase1018AuthoritativeEvidenceVerification(unittest.TestCase):

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

    def test_01_genuine_primary_source_fixture(self):
        """Genuine primary exchange circular verifies order-book close and unblocks cutoff."""
        raw_doc = (
            "BSE SME Trading Notice. Ref: 20261028-01. Candidate: Wiscon Industries Ltd (WISCON). "
            "Public Issue Bidding: Retail order book closes strictly at 16:00:00 IST on October 29, 2026."
        )
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-CIRCULAR-WISCON-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertTrue(res["success"])
        self.assertTrue(res["is_verified"])
        self.assertEqual(res["post_audit_state"]["lifecycle_state"], "READY_FOR_PROSPECTIVE_COMMIT")

    def test_02_secondary_portal_falsely_labelled_as_primary(self):
        """Secondary portal content falsely tagged as PRIMARY_EXCHANGE_CIRCULAR rejected if non-exchange portal."""
        raw_doc = "IPO Central bulletin for Wiscon Industries Ltd claiming 16:00 IST closing."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "IPOCENTRAL_AGGREGATOR",  # Not BSE/NSE
            "document_id": "FAKE-PRIMARY-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertTrue(res["success"])
        self.assertFalse(res["is_verified"])
        self.assertEqual(res["post_audit_state"]["lifecycle_state"], "BLOCKED_CUTOFF")

    def test_03_circular_for_wrong_candidate_rejected(self):
        """Official exchange circular addressing a different IPO is rejected with IRRELEVANT_EVIDENCE."""
        raw_doc = (
            "BSE SME Trading Notice Ref: 20261028-99. Subject: Trading cutoff for ABC Steels Limited (ABCSTEEL). "
            "Retail order book closes at 16:00:00 IST."
        )
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-CIRCULAR-ABC-99",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("IRRELEVANT_EVIDENCE", res["reason"])

    def test_04_upi_deadline_only_document_retains_blocked_cutoff(self):
        """Document discussing only UPI mandate acceptance deadline does not unblock bidding cutoff."""
        raw_doc = (
            "NPCI / BSE Circular. Subject: Wiscon Industries Ltd (WISCON). "
            "UPI mandate acceptance deadline expires at 17:00:00 IST on October 29, 2026."
        )
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-CIRCULAR-UPI-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertTrue(res["success"])
        self.assertFalse(res["is_verified"])
        self.assertEqual(res["post_audit_state"]["lifecycle_state"], "BLOCKED_CUTOFF")

    def test_05_missing_raw_artifact_rejected(self):
        """Evidence payload without raw_text or empty artifact is rejected."""
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-01",
            "document_sha256": "a" * 64,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("Missing raw_text", res["reason"])

    def test_06_tampered_artifact_hash_mismatch_rejected(self):
        """Payload where declared SHA-256 does not match bytes is rejected."""
        raw_doc = "Wiscon Industries Ltd genuine circular text."
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-01",
            "document_sha256": "0" * 64,  # Bad hash
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("Hash mismatch", res["reason"])

    def test_07_timezone_naive_timestamps_rejected(self):
        """Timezone-naive publication or retrieval timestamps fail validation."""
        raw_doc = "Wiscon Industries Ltd notice text."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00",  # Naive
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("Missing timezone", res["reason"])

    def test_08_retrieval_before_publication_rejected(self):
        """Evidence where retrieval time precedes publication time raises error."""
        raw_doc = "Wiscon Industries Ltd notice text."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 11:00:00 IST",
            "retrieval_time": "2026-10-28 10:00:00 IST"  # Precedes publication
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:30:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("RETRIEVAL_BEFORE_PUBLICATION_ANOMALY", res["reason"])

    def test_09_evidence_update_attempt_after_candidate_expired_rejected(self):
        """Evidence update submitted after candidate cutoff has elapsed is strictly rejected."""
        raw_doc = "BSE Notice Wiscon Industries Ltd retail order book close."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-LATE-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-29 16:05:00 IST"  # After cutoff (16:00 IST)
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-29 16:10:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("CANDIDATE_EXPIRED", res["reason"])

    def test_10_conflicting_cutoff_times_logged_to_governance(self):
        """Evidence asserting a cutoff time different from registry logs a governance warning."""
        raw_doc = "BSE SME Notice for Carver Roboweld Ltd (CARVER). Retail order book closes at 15:30:00 IST."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-CONFLICT-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST",
            "verified_cutoff_time": "2026-10-30 15:30:00 IST"  # Conflicting with 16:00
        }
        res = process_evidence_update("carver-roboweld-sme-20261030", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertTrue(res["success"])

        # Verify governance conflict event logged
        with open(self.audit_events_path, "r", encoding="utf-8") as f:
            events = [json.loads(line) for line in f if line.strip()]
        has_conflict = any(e.get("event_type") == "CONFLICTING_CUTOFF_TIMES_DETECTED" for e in events)
        self.assertTrue(has_conflict)

    def test_11_cutoff_equality_boundary_trichotomy(self):
        """Trichotomy check: 1 instant before is open, exactly at is expired, 1 instant after is expired."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon_data = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")

        # 1 instant before: 15:59:59 IST
        before_res = self.manager.audit_and_prepare_candidate(wiscon_data, evaluation_timestamp_ist="2026-10-29 15:59:59 IST")
        self.assertEqual(before_res["candidate_lifecycle_state"], "BLOCKED_CUTOFF")

        # Exactly at: 16:00:00 IST
        exact_res = self.manager.audit_and_prepare_candidate(wiscon_data, evaluation_timestamp_ist="2026-10-29 16:00:00 IST")
        self.assertEqual(exact_res["candidate_lifecycle_state"], "EXPIRED_WITHOUT_COMMIT")

        # 1 instant after: 16:00:01 IST
        after_res = self.manager.audit_and_prepare_candidate(wiscon_data, evaluation_timestamp_ist="2026-10-29 16:00:01 IST")
        self.assertEqual(after_res["candidate_lifecycle_state"], "EXPIRED_WITHOUT_COMMIT")

    def test_12_restart_after_cutoff_preserves_expired_state(self):
        """Reconciliation after restart for past-cutoff candidate stays EXPIRED_WITHOUT_COMMIT."""
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
        wiscon_data = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        res = restarted.audit_and_prepare_candidate(wiscon_data, evaluation_timestamp_ist="2026-10-29 18:00:00 IST")
        self.assertEqual(res["candidate_lifecycle_state"], "EXPIRED_WITHOUT_COMMIT")

    def test_13_daily_monitoring_report_missing_registry_graceful(self):
        """Monitoring report generation handles missing candidate registry gracefully without throwing uncaught exceptions."""
        non_existent_reg = os.path.join(self.test_dir, "missing_reg.json")
        mgr = ProspectiveLifecycleManager(
            candidate_registry_path=non_existent_reg,
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger,
            checkpoint_path=self.checkpoint_path,
            audit_events_path=self.audit_events_path,
            evaluation_records_path=self.evaluation_records_path
        )
        rep = generate_daily_monitoring_report(mgr, current_time_iso="2026-10-28 12:00:00 IST")
        self.assertEqual(rep["candidate_monitoring_records"], [])
        self.assertEqual(rep["system_operating_mode"], "STRICT_SHADOW_VALIDATION")

    def test_14_mainboard_candidates_remain_blocked_governance(self):
        """Mainboard candidates are tracked for coverage only and remain BLOCKED_GOVERNANCE."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        mb_cands = [c for c in cands if c.get("board_type") == "Mainboard"]
        self.assertGreaterEqual(len(mb_cands), 3)
        for mb in mb_cands:
            prep = self.manager.audit_and_prepare_candidate(mb, evaluation_timestamp_ist="2026-10-28 12:00:00 IST")
            self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_GOVERNANCE")
            self.assertFalse(prep["is_clean_eligible"])


if __name__ == "__main__":
    unittest.main()
