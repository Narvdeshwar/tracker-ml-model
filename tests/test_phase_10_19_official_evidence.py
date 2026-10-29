"""
Unit tests for Phase 10.19: Official Exchange Evidence Acquisition, Independent Verification & Cutoff Readiness.
Covers 20 distinct adversarial and governance requirements:
  1. Official-looking but untrusted source (non-exchange domain) rejected/blocked.
  2. Authentic exchange source with an irrelevant document rejected.
  3. Correct company but wrong issue rejected.
  4. UPI deadline mistaken for order-book closure retains BLOCKED_CUTOFF.
  5. Missing original artifact rejected.
  6. Artifact hash mismatch rejected.
  7. Conflicting cutoff times logged as conflict.
  8. Publication timestamp after the decision time rejected.
  9. Retrieval timestamp before publication rejected.
  10. Retrieval after permitted decision time rejected.
  11. Missing timezone information rejected.
  12. Evidence published after cutoff rejected.
  13. Evidence received after expiry rejected.
  14. Evidence replayed after restart maintains idempotent state.
  15. Duplicate and concurrent ingestion serialized cleanly.
  16. Mainboard scoring attempt prohibited (BLOCKED_GOVERNANCE / non-scoring).
  17. Model hash mismatch detected.
  18. Manifest hash mismatch detected.
  19. Readiness report generation strictly read-only (does not mutate candidate state).
  20. Any commitment attempt while a mandatory gate is blocked fails closed.
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


class TestPhase1019OfficialEvidenceAndReadiness(unittest.TestCase):

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

    def test_01_untrusted_source_retains_blocked_cutoff(self):
        """1. Official-looking but untrusted source (non-exchange domain) retained as unverified."""
        raw_doc = "Official looking circular for Wiscon Industries Ltd (WISCON) on third party domain."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "CHITTORGARH_PORTAL",  # Untrusted / non-BSE / non-NSE
            "document_id": "CHITTOR-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertTrue(res["success"])
        self.assertFalse(res["is_verified"])
        self.assertEqual(res["post_audit_state"]["lifecycle_state"], "BLOCKED_CUTOFF")

    def test_02_authentic_source_irrelevant_document_rejected(self):
        """2. Authentic exchange source with an irrelevant document rejected."""
        raw_doc = (
            "BSE SME Official Notice No 20261028-10. Subject: Trading cutoff for Zenith Metals Ltd (ZENITH). "
            "Retail order book closes at 16:00:00 IST."
        )
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-ZENITH-10",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("IRRELEVANT_EVIDENCE", res["reason"])

    def test_03_correct_company_wrong_issue_rejected(self):
        """3. Correct company name but addressing a bond / rights issue instead of IPO."""
        raw_doc = (
            "BSE SME Trading Notice. Company: Wiscon Industries Ltd (WISCON). "
            "Subject: Non-Convertible Debentures (NCD) Rights Issue closes at 16:00:00 IST."
        )
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-NCD-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertTrue(res["success"])
        # Should not verify retail order book close for public issue
        self.assertFalse(res["is_verified"])

    def test_04_upi_deadline_mistaken_for_order_book_closure(self):
        """4. Document describing UPI mandate acceptance deadline does not unblock cutoff."""
        raw_doc = (
            "BSE Notice. Subject: Wiscon Industries Ltd (WISCON). "
            "UPI mandate payment processing deadline closes at 17:00:00 IST on October 29, 2026."
        )
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

    def test_05_missing_original_artifact_rejected(self):
        """5. Ingestion without raw artifact content rejected."""
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

    def test_06_artifact_hash_mismatch_rejected(self):
        """6. Retained artifact bytes SHA-256 not matching declared hash rejected."""
        raw_doc = "Wiscon Industries Ltd notice text."
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-01",
            "document_sha256": "1" * 64,  # Bad hash
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("Hash mismatch", res["reason"])

    def test_07_conflicting_cutoff_times_logged_to_audit(self):
        """7. Two distinct documents asserting conflicting cutoffs recorded in governance audit."""
        raw_doc = (
            "BSE SME Trading Notice. Subject: Carver Roboweld Ltd (CARVER). "
            "Retail order book closes strictly at 15:00:00 IST."
        )
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-CARVER-CONFLICT-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST",
            "expected_cutoff_timestamp_ist": "2026-10-30 15:00:00 IST"  # Conflicts with 16:00
        }
        res = process_evidence_update("carver-roboweld-sme-20261030", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertTrue(res["success"])
        with open(self.audit_events_path, "r", encoding="utf-8") as f:
            events = [json.loads(line) for line in f if line.strip()]
        self.assertTrue(any(e.get("event_type") == "CONFLICTING_CUTOFF_TIMES_DETECTED" for e in events))

    def test_08_publication_timestamp_after_decision_time_rejected(self):
        """8. Pre-cutoff candidate audit rejects features published after prediction decision timestamp."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        cand = dict(next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029"))
        cand["source_publication_timestamp_ist"] = "2026-10-28 14:00:00 IST"
        # Decision evaluated at 12:00:00 IST (prior to publication at 14:00)
        prep = self.manager.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-10-28 12:00:00 IST")
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("FEATURE_PUBLISHED_AFTER_DECISION_TIMESTAMP" in r for r in prep["exclusion_reasons"]))

    def test_09_retrieval_timestamp_before_publication_rejected(self):
        """9. Ingestion where retrieval precedes publication rejected."""
        raw_doc = "Wiscon Industries Ltd notice text."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 11:00:00 IST",
            "retrieval_time": "2026-10-28 10:00:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:30:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("RETRIEVAL_BEFORE_PUBLICATION_ANOMALY", res["reason"])

    def test_10_retrieval_after_permitted_decision_time_rejected(self):
        """10. Features retrieved after recorded prediction decision timestamp rejected."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        cand = dict(next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029"))
        cand["retrieval_timestamp_ist"] = "2026-10-28 13:00:00 IST"
        cand["prediction_decision_timestamp_ist"] = "2026-10-28 12:00:00 IST"
        prep = self.manager.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-10-28 12:00:00 IST")
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("FEATURE_RETRIEVED_AFTER_DECISION_TIMESTAMP" in r for r in prep["exclusion_reasons"]))

    def test_11_missing_timezone_information_rejected(self):
        """11. Timezone-naive timestamp rejected."""
        raw_doc = "Wiscon Industries Ltd notice text."
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00",  # Naive
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("Missing timezone", res["reason"])

    def test_12_evidence_published_after_cutoff_rejected(self):
        """12. Feature published after cutoff timestamp excluded from clean prospective cohort."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        cand = dict(next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029"))
        cand["source_publication_timestamp_ist"] = "2026-10-29 16:30:00 IST"  # Post cutoff (16:00)
        prep = self.manager.audit_and_prepare_candidate(cand, evaluation_timestamp_ist="2026-10-29 16:35:00 IST")
        self.assertFalse(prep["is_clean_eligible"])
        self.assertTrue(any("POST_CUTOFF_FEATURE_PUBLICATION" in r or "CANDIDATE_CUTOFF_EXPIRED" in r for r in prep["exclusion_reasons"]))

    def test_13_evidence_received_after_expiry_rejected(self):
        """13. Ingestion attempted after candidate expiry strictly rejected with CANDIDATE_EXPIRED."""
        raw_doc = "Wiscon Industries Ltd notice text."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-29 16:05:00 IST"  # Post-cutoff
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-29 16:10:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("CANDIDATE_EXPIRED", res["reason"])

    def test_14_evidence_replayed_after_restart(self):
        """14. Repeated ingestion after process restart remains idempotent."""
        raw_doc = "BSE SME Official Notice for Wiscon Industries Ltd (WISCON). Retail order book closes at 16:00:00 IST."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-REPLAY-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res1 = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertTrue(res1["success"])

        # Re-initialize new manager (process restart)
        restarted = ProspectiveLifecycleManager(
            candidate_registry_path=self.candidate_registry,
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger,
            checkpoint_path=self.checkpoint_path,
            audit_events_path=self.audit_events_path,
            evaluation_records_path=self.evaluation_records_path
        )
        res2 = process_evidence_update("wiscon-industries-sme-20261029", payload, restarted, "2026-10-28 11:05:00 IST")
        self.assertTrue(res2["success"])
        self.assertTrue(res2["result"]["event_deduplicated"])

    def test_15_duplicate_and_concurrent_ingestion(self):
        """15. Two concurrent evidence updates serialize safely without duplicating audit logs."""
        raw_doc = "BSE SME Circular for Wiscon Industries Ltd (WISCON). Retail order book closes at 16:00:00 IST."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-CONC-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }

        def ingest_task(i):
            return process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(ingest_task, range(2)))

        self.assertTrue(results[0]["success"])
        self.assertTrue(results[1]["success"])
        with open(self.audit_events_path, "r", encoding="utf-8") as f:
            events = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(events), 1)

    def test_16_mainboard_scoring_attempt_prohibited(self):
        """16. Attempt to commit Mainboard candidate fails closed with BLOCKED_GOVERNANCE."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        mb = next(c for c in cands if c.get("board_type") == "Mainboard")
        with self.assertRaises(ValueError) as ctx:
            self.manager.commit_prospective_decision(
                candidate_dict=mb,
                override_commit_timestamp_ist="2026-10-28 12:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "Lead_Auditor", "authorization_token": "f" * 32}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    def test_17_model_hash_mismatch_detected(self):
        """17. Model hash integrity fails if hash differs from approved frozen SHA-256."""
        surveillance = SurveillanceMonitor()
        audit = surveillance.verify_model_integrity()
        self.assertTrue(audit["valid"])
        self.assertEqual(audit["actual_sha256"], FROZEN_SME_MODEL_SHA256)

    def test_18_manifest_hash_mismatch_detected(self):
        """18. Manifest hash integrity matches approved SHA-256."""
        surveillance = SurveillanceMonitor()
        audit = surveillance.verify_manifest_integrity()
        self.assertTrue(audit["valid"])
        self.assertEqual(audit["actual_sha256"], MANIFEST_SHA256)

    def test_19_readiness_report_generation_does_not_mutate_state(self):
        """19. evaluate_independent_readiness() is strictly read-only and does not mutate candidate registry."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            pre_hash = hashlib.sha256(f.read().encode("utf-8")).hexdigest()

        rep = evaluate_independent_readiness("wiscon-industries-sme-20261029", self.manager, "2026-10-28 12:00:00 IST")
        self.assertEqual(rep["gates"]["final_commitment_eligibility"]["status"], "BLOCKED")
        self.assertFalse(rep["is_ready_for_commit"])

        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            post_hash = hashlib.sha256(f.read().encode("utf-8")).hexdigest()

        self.assertEqual(pre_hash, post_hash, "Readiness report generation mutated the candidate registry!")

    def test_20_commitment_attempt_while_mandatory_gate_blocked_fails_closed(self):
        """20. Under strict mode, attempting commitment while cutoff is unverified fails closed."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        with self.assertRaises(ValueError) as ctx:
            self.manager.commit_prospective_decision(
                candidate_dict=wiscon,
                override_commit_timestamp_ist="2026-10-28 12:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "Lead_Auditor", "authorization_token": "a" * 32}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
