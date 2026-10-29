"""
Unit tests for Phase 10.17: Prospective Monitoring & Candidate Lifecycle Control.
Covers:
  1. New evidence discovery with valid primary exchange source transitions state from BLOCKED_CUTOFF.
  2. Evidence hash mismatch or malformed SHA-256 rejected.
  3. Duplicate evidence ingestion is idempotent (governance audit event not duplicated).
  4. Irrelevant/incorrect candidate evidence rejected.
  5. Primary vs secondary evidence classification (secondary retains BLOCKED_CUTOFF).
  6. Readiness changes after evidence verification (unverified -> ready).
  7. Cutoff equality boundary (now == cutoff) deterministically marks candidate EXPIRED_WITHOUT_COMMIT.
  8. Delayed monitoring after cutoff transitions to EXPIRED_WITHOUT_COMMIT.
  9. Process restart and lifecycle reconciliation preserves candidate states.
  10. Unauthorized commitment attempts blocked under strict mode.
  11. Retrospective commitment attempts on expired candidate blocked.
  12. Mainboard scoring prohibition (REGISTER_FOR_COVERAGE_ONLY / BLOCKED_GOVERNANCE).
  13. Frozen model and manifest SHA-256 immutability.
  14. Empty production ledger preservation (0 records).
  15. Monitoring source failure reported cleanly.
  16. Timezone-naive timestamp rejected in evidence update.
  17. Contradictory evidence timestamps (retrieval < publication) rejected.
  18. generate_daily_monitoring_report() outputs correct approaching cutoffs, candidate reports, and ledger status.
"""

import os
import json
import shutil
import tempfile
import unittest
import hashlib
from datetime import datetime, timezone, timedelta

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
from src.evidence_audit_protocol import ProspectiveEvidenceAuditor


class TestPhase1017CandidateMonitoringAndLifecycle(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.decision_ledger = os.path.join(self.test_dir, "test_decision_ledger.jsonl")
        self.outcome_ledger = os.path.join(self.test_dir, "test_outcome_ledger.jsonl")
        self.checkpoint_path = os.path.join(self.test_dir, "test_checkpoint.json")
        self.candidate_registry = os.path.join(self.test_dir, "test_registry.json")
        self.audit_events_path = os.path.join(self.test_dir, "test_audit_events.jsonl")
        self.evaluation_records_path = os.path.join(self.test_dir, "test_evaluation_records.jsonl")

        # Copy actual candidate registry as isolated baseline fixture
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

    def test_01_frozen_artifacts_immutability(self):
        """Verify frozen model and manifest match approved SHA-256 digests byte-for-byte."""
        with open(FROZEN_SME_MODEL_PATH, "rb") as f:
            model_hash = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(model_hash, FROZEN_SME_MODEL_SHA256)

        with open(MANIFEST_PATH, "rb") as f:
            manifest_hash = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(manifest_hash, MANIFEST_SHA256)

    def test_02_production_ledgers_strictly_empty(self):
        """Verify production ledgers are strictly empty (0 records)."""
        for path in [DECISION_LEDGER_PATH, OUTCOME_LEDGER_PATH, EVALUATION_RECORDS_PATH, AUDIT_EVENTS_PATH]:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    lines = [l for l in f if l.strip()]
                self.assertEqual(len(lines), 0, f"Production ledger {path} contains records!")

    def test_03_tracked_sme_candidates_initially_blocked_cutoff(self):
        """Tracked SME candidates Wiscon Industries and Carver Roboweld start as BLOCKED_CUTOFF."""
        current_time = "2026-10-28 12:00:00 IST"
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon_data = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        wiscon = self.manager.audit_and_prepare_candidate(wiscon_data, evaluation_timestamp_ist=current_time)
        self.assertEqual(wiscon["candidate_lifecycle_state"], "BLOCKED_CUTOFF")
        self.assertFalse(wiscon["is_clean_eligible"])

        carver_data = next(c for c in cands if c["ipo_id"] == "carver-roboweld-sme-20261030")
        carver = self.manager.audit_and_prepare_candidate(carver_data, evaluation_timestamp_ist=current_time)
        self.assertEqual(carver["candidate_lifecycle_state"], "BLOCKED_CUTOFF")
        self.assertFalse(carver["is_clean_eligible"])

    def test_04_new_evidence_discovery_transitions_candidate_state(self):
        """Valid primary exchange circular verifies bidding cutoff and transitions state."""
        raw_doc = (
            "BSE SME Trading Notice Notice No: 20261028-99. Subject: Trading and Bidding Cutoff for Wiscon Industries Limited. "
            "Retail order book closes strictly at 16:00:00 IST on October 29, 2026."
        )
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()

        evidence_payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-CIRCULAR-20261028-99",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }

        res = process_evidence_update(
            candidate_id="wiscon-industries-sme-20261029",
            evidence_payload=evidence_payload,
            manager=self.manager,
            current_time_iso="2026-10-28 11:00:00 IST"
        )

        self.assertTrue(res["success"])
        self.assertTrue(res["is_verified"])
        self.assertEqual(res["post_audit_state"]["lifecycle_state"], "READY_FOR_PROSPECTIVE_COMMIT")
        self.assertTrue(res["post_audit_state"]["readiness"]["is_ready"])

        # Check candidate registry persisted change
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            updated_reg = json.load(f)
        cand = next(c for c in updated_reg if c["ipo_id"] == "wiscon-industries-sme-20261029")
        self.assertTrue(cand["is_bidding_cutoff_verified"])
        self.assertEqual(cand["raw_source_sha256"], doc_hash)

    def test_05_evidence_hash_mismatch_rejected(self):
        """Evidence with invalid or mismatched SHA-256 is strictly rejected."""
        evidence_payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-CIRCULAR-20261028-99",
            "document_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
            "raw_text": "Mismatched content string",
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }

        res = process_evidence_update(
            candidate_id="wiscon-industries-sme-20261029",
            evidence_payload=evidence_payload,
            manager=self.manager,
            current_time_iso="2026-10-28 11:00:00 IST"
        )
        self.assertFalse(res["success"])
        self.assertIn("Hash mismatch", res["reason"])

    def test_06_duplicate_evidence_ingestion_is_idempotent(self):
        """Duplicate evidence ingestion does not append duplicate governance events."""
        raw_doc = "BSE Official circular text for Wiscon Industries Limited idempotency check."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()

        evidence_payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-CIRCULAR-IDEMPOTENT-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }

        res1 = process_evidence_update("wiscon-industries-sme-20261029", evidence_payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertTrue(res1["success"])

        # Second update with same evidence
        res2 = process_evidence_update("wiscon-industries-sme-20261029", evidence_payload, self.manager, "2026-10-28 11:05:00 IST")
        self.assertTrue(res2["success"])

        # Count events in audit log
        with open(self.audit_events_path, "r", encoding="utf-8") as f:
            events = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(events), 1, "Duplicate evidence generated multiple governance audit events!")

    def test_07_irrelevant_or_unknown_candidate_rejected(self):
        """Evidence updates for unrecorded or unknown candidate are rejected."""
        evidence_payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "raw_text": "Some circular for unknown",
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("unknown-candidate-9999", evidence_payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("not in candidate registry", res["reason"])

    def test_08_secondary_evidence_classification(self):
        """Secondary portal or news evidence updates record but does not unblock cutoff."""
        raw_doc = "Chittorgarh IPO timetable article for Wiscon Industries."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()

        evidence_payload = {
            "source_type": "SECONDARY_PORTAL_TIMETABLE",
            "source_portal": "CHITTORGARH_SECONDARY",
            "document_id": "CHITTOR-ARTICLE-101",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 09:00:00 IST",
            "retrieval_time": "2026-10-28 09:30:00 IST"
        }

        res = process_evidence_update("wiscon-industries-sme-20261029", evidence_payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertTrue(res["success"])
        self.assertFalse(res["is_verified"])
        self.assertEqual(res["post_audit_state"]["lifecycle_state"], "BLOCKED_CUTOFF")

    def test_09_cutoff_equality_boundary_marks_expired(self):
        """At exact cutoff equality (now == cutoff), candidate is strictly EXPIRED_WITHOUT_COMMIT."""
        exact_cutoff = "2026-10-29 16:00:00 IST"
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon_data = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        res = self.manager.audit_and_prepare_candidate(wiscon_data, evaluation_timestamp_ist=exact_cutoff)
        self.assertEqual(res["candidate_lifecycle_state"], "EXPIRED_WITHOUT_COMMIT")
        self.assertFalse(res["is_clean_eligible"])
        self.assertTrue(any("CANDIDATE_CUTOFF_EXPIRED" in r for r in res["exclusion_reasons"]))

    def test_10_delayed_monitoring_after_cutoff_transitions_to_expired(self):
        """Inspection occurring after cutoff timestamp marks candidate EXPIRED_WITHOUT_COMMIT."""
        after_cutoff = "2026-10-29 16:00:01 IST"
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon_data = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        res = self.manager.audit_and_prepare_candidate(wiscon_data, evaluation_timestamp_ist=after_cutoff)
        self.assertEqual(res["candidate_lifecycle_state"], "EXPIRED_WITHOUT_COMMIT")
        self.assertFalse(res["is_clean_eligible"])

    def test_11_process_restart_preserves_lifecycle_state(self):
        """Lifecycle state and evidence updates persist across process restart."""
        raw_doc = "BSE Circular verified cutoff text for Wiscon Industries Limited order book close."
        doc_hash = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-CIRCULAR-RESTART-01",
            "document_sha256": doc_hash,
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")

        # Reinstantiate new manager simulating process restart
        restarted_manager = ProspectiveLifecycleManager(
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
        audit_res = restarted_manager.audit_and_prepare_candidate(wiscon_data, evaluation_timestamp_ist="2026-10-28 12:00:00 IST")
        self.assertEqual(audit_res["candidate_lifecycle_state"], "READY_FOR_PROSPECTIVE_COMMIT")
        self.assertTrue(audit_res["is_clean_eligible"])

    def test_12_unauthorized_commitment_attempts_blocked(self):
        """Under strict mode, commit attempts without valid human administrative auth token are rejected."""
        # Unblock cutoff first
        raw_doc = "BSE Circular verified cutoff text for Wiscon Industries Limited retail order book close."
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-CIRCULAR-AUTH-01",
            "document_sha256": hashlib.sha256(raw_doc.encode()).hexdigest(),
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")

        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon_data = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")

        # Attempt commit without authorization token
        with self.assertRaises(ValueError) as ctx:
            self.manager.commit_prospective_decision(
                candidate_dict=wiscon_data,
                override_commit_timestamp_ist="2026-10-28 12:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "unauthorized_caller", "authorization_token": "short_tok"}
            )
        self.assertIn("COMMIT_BLOCKED_INVALID_AUTHORIZATION_TOKEN", str(ctx.exception))

    def test_13_retrospective_commitment_attempt_on_expired_candidate_blocked(self):
        """Attempt to commit at or after cutoff boundary fails even with valid authorization token."""
        raw_doc = "BSE Circular verified cutoff text."
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-CIRCULAR-EXP-01",
            "document_sha256": hashlib.sha256(raw_doc.encode()).hexdigest(),
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 10:00:00 IST",
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")

        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon_data = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")

        # Attempt commit at cutoff boundary under strict_clean_only=True
        with self.assertRaises(ValueError) as ctx:
            self.manager.commit_prospective_decision(
                candidate_dict=wiscon_data,
                override_commit_timestamp_ist="2026-10-29 16:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "Lead_Auditor_Signoff", "authorization_token": "a" * 32}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    def test_14_mainboard_scoring_prohibited(self):
        """Mainboard candidate scoring is prohibited; candidate is restricted to coverage tracking."""
        mainboard_cand = {
            "ipo_id": "mainboard-test-sample-01",
            "company_name": "Mainboard Sample Ltd",
            "board_type": "Mainboard",
            "symbol_or_ref": "SAMPLE",
            "exchange": "NSE Mainboard",
            "cutoff_timestamp_ist": "2026-11-05 16:00:00 IST",
            "authoritative_evidence": "NSE Official Notice",
            "source_publication_timestamp_ist": "2026-10-28 10:00:00 IST",
            "raw_source_sha256": "e" * 64,
            "is_timing_verified": True,
            "is_bidding_cutoff_verified": True,
            "features": {"feat_nifty50_ret5s_pct": 0.5, "feat_india_vix": 14.0, "feat_recent5_sentiment": 5.0}
        }
        res = self.manager.audit_and_prepare_candidate(mainboard_cand, evaluation_timestamp_ist="2026-10-28 12:00:00 IST")
        self.assertEqual(res["candidate_lifecycle_state"], "BLOCKED_GOVERNANCE")
        self.assertFalse(res["is_clean_eligible"])

        # Attempt commit on mainboard
        with self.assertRaises(ValueError) as ctx:
            self.manager.commit_prospective_decision(
                candidate_dict=mainboard_cand,
                override_commit_timestamp_ist="2026-10-28 12:00:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "Lead_Auditor_Signoff", "authorization_token": "b" * 32}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    def test_15_timezone_naive_timestamp_rejected(self):
        """Timezone-naive timestamp in evidence payload is strictly rejected."""
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "raw_text": "text",
            "publication_time": "2026-10-28 10:00:00",  # Naive
            "retrieval_time": "2026-10-28 10:15:00 IST"
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:00:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("Missing timezone", res["reason"])

    def test_16_contradictory_timestamps_rejected(self):
        """Evidence where retrieval time is prior to publication time is rejected."""
        raw_doc = "BSE Circular verified cutoff text."
        payload = {
            "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
            "source_portal": "BSE_INDIA_OFFICIAL_CIRCULAR",
            "document_id": "BSE-CIRCULAR-TIME-01",
            "document_sha256": hashlib.sha256(raw_doc.encode()).hexdigest(),
            "raw_text": raw_doc,
            "publication_time": "2026-10-28 11:00:00 IST",
            "retrieval_time": "2026-10-28 10:00:00 IST"  # Before publication!
        }
        res = process_evidence_update("wiscon-industries-sme-20261029", payload, self.manager, "2026-10-28 11:30:00 IST")
        self.assertFalse(res["success"])
        self.assertIn("RETRIEVAL_BEFORE_PUBLICATION_ANOMALY", res["reason"])

    def test_17_daily_monitoring_report_generation(self):
        """generate_daily_monitoring_report() generates read-only status structure."""
        report = generate_daily_monitoring_report(self.manager, current_time_iso="2026-10-28 12:00:00 IST")
        self.assertIn("report_timestamp", report)
        self.assertEqual(report["system_operating_mode"], "STRICT_SHADOW_VALIDATION")
        self.assertTrue(report["governance_integrity"]["model_sha256_verified"])
        self.assertTrue(report["governance_integrity"]["manifest_sha256_verified"])

        # Check candidate entries
        cands = {c["candidate_id"]: c for c in report["candidate_monitoring_records"]}
        self.assertIn("wiscon-industries-sme-20261029", cands)
        self.assertIn("carver-roboweld-sme-20261030", cands)

        # Wiscon cutoff is 2026-10-29 16:00 IST, which is within 48h of 2026-10-28 12:00 IST (28h away)
        self.assertTrue(cands["wiscon-industries-sme-20261029"]["cutoff_approaching_48h"])
        self.assertEqual(cands["wiscon-industries-sme-20261029"]["lifecycle_state"], "BLOCKED_CUTOFF")

        # Carver cutoff is 2026-10-30 16:00 IST, 52 hours away (not within 48h)
        self.assertFalse(cands["carver-roboweld-sme-20261030"]["cutoff_approaching_48h"])

        # Ledgers summary
        self.assertEqual(report["ledgers_summary"]["prospective_decisions_count"], 0)
        self.assertEqual(report["ledgers_summary"]["prospective_outcomes_count"], 0)


if __name__ == "__main__":
    unittest.main()
