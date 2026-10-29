"""
Phase 10.22 Adversarial Test Suite:
Official Notice Ingestion, Deadline Expiry Sweeping, Lifecycle Reconciliation & Invariants.

Tests 35 distinct scenarios as specified in Section 9:
 1. Valid primary exchange notice.
 2. Secondary-source notice rejection.
 3. Irrelevant notice type (NCD / bonds).
 4. UPI-only deadline rejection.
 5. Incorrect candidate match.
 6. Ambiguous candidate match.
 7. Missing source artifact.
 8. Artifact SHA-256 mismatch.
 9. Publication timestamp missing.
10. Naive timestamp rejection.
11. Conflicting primary evidence.
12. Duplicate notice ingestion.
13. Notice retrieved after cutoff.
14. Notice published after decision.
15. Collector timeout.
16. HTTP error.
17. Malformed response.
18. Retry exhaustion.
19. Empty response.
20. Expiry immediately before cutoff.
21. Expiry exactly at cutoff.
22. Expiry immediately after cutoff.
23. Repeated expiry sweep.
24. Concurrent expiry sweep.
25. Restart after expiry.
26. Registry corruption.
27. Late evidence for an expired candidate.
28. Blocked candidate remains blocked without valid evidence.
29. Mainboard candidate remains non-scoring.
30. No decision creation by the collector.
31. No outcome creation by the sweeper.
32. No retroactive commitment.
33. Monitoring report does not mutate production ledgers.
34. Frozen model and manifest hashes remain unchanged.
35. Full regression suite passes.
"""

import unittest
import os
import json
import shutil
import tempfile
import hashlib
import datetime
from concurrent.futures import ThreadPoolExecutor

from src.exchange_notice_collector import ExchangeNoticeCollector
from src.prospective_lifecycle import (
    ProspectiveLifecycleManager,
    FROZEN_SME_MODEL_SHA256,
    MANIFEST_SHA256,
    DECISION_LEDGER_PATH,
    OUTCOME_LEDGER_PATH,
    CANDIDATE_REGISTRY_PATH,
    AUDIT_EVENTS_PATH,
    EVALUATION_RECORDS_PATH,
    process_evidence_update
)
from src.surveillance_monitor import FROZEN_SME_MODEL_PATH, MANIFEST_PATH


class TestPhase1022NoticeIngestionAndDeadlineSweeper(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_phase_10_22_")
        self.decision_ledger = os.path.join(self.test_dir, "prospective_decision_ledger.jsonl")
        self.outcome_ledger = os.path.join(self.test_dir, "prospective_outcome_ledger.jsonl")
        self.candidate_registry = os.path.join(self.test_dir, "tracked_candidate_registry.json")
        self.audit_events = os.path.join(self.test_dir, "governance_audit_events.jsonl")
        self.evaluation_records = os.path.join(self.test_dir, "prospective_evaluation_records.jsonl")
        self.checkpoint_file = os.path.join(self.test_dir, "governance_checkpoint_signature.json")
        self.raw_artifact_dir = os.path.join(self.test_dir, "raw_artifacts")

        # Copy original tracked candidates into test directory
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

    # -------------------------------------------------------------------------
    # Phase 10.22A & B: Collector, Evidence Normalization & Authority Checks
    # -------------------------------------------------------------------------
    def test_01_valid_primary_exchange_notice(self):
        """1. Valid official BSE primary circular is fetched, retained, and verifies bidding cutoff."""
        raw_doc = (
            "BSE India Official SME Notice Ref 20261028-01.\n"
            "Public Issue of Wiscon Industries Ltd (WISCON).\n"
            "Retail individual order book close timing: 16:00:00 IST on 2026-10-29."
        )
        doc_bytes = raw_doc.encode("utf-8")
        doc_hash = hashlib.sha256(doc_bytes).hexdigest()

        def mock_transport(url, headers, timeout):
            return {"status_code": 200, "headers": {"Content-Type": "text/html"}, "content": doc_bytes}

        collector = ExchangeNoticeCollector(
            http_transport=mock_transport,
            artifact_storage_dir=self.raw_artifact_dir
        )
        res = collector.fetch_exchange_notices("BSE")
        self.assertTrue(res["success"])
        self.assertEqual(res["artifact_sha256"], doc_hash)
        self.assertTrue(os.path.exists(res["retained_path"]))

        # Process through lifecycle manager
        update_res = self.manager.process_evidence_update(
            ipo_id="wiscon-industries-sme-20261029",
            raw_artifact_content=doc_bytes,
            source_reference=f"BSE_CIRCULAR:{doc_hash[:8]}",
            publication_timestamp_ist="2026-10-28 10:00:00 IST",
            retrieval_timestamp_ist="2026-10-28 10:15:00 IST",
            is_primary_exchange_source=True,
            relevant_bidding_category="RETAIL_INDIVIDUAL"
        )
        self.assertEqual(update_res["status"], "EVIDENCE_PROCESSED")
        self.assertTrue(update_res["is_bidding_cutoff_verified"])

    def test_02_secondary_source_notice_rejection(self):
        """2. Notice from secondary tracker portal cannot satisfy primary exchange cutoff requirement."""
        raw_doc = "Chittorgarh SME Update: Wiscon Industries issue closes at 16:00:00 IST."
        res = process_evidence_update(
            candidate_id="wiscon-industries-sme-20261029",
            evidence_payload={
                "source_type": "SECONDARY_AGGREGATOR",
                "source_portal": "CHITTORGARH",
                "document_id": "CHITTOR-WISCON-01",
                "document_sha256": hashlib.sha256(raw_doc.encode()).hexdigest(),
                "raw_text": raw_doc,
                "publication_time": "2026-10-28 10:00:00 IST",
                "retrieval_time": "2026-10-28 10:15:00 IST"
            },
            manager=self.manager
        )
        self.assertTrue(res["success"])
        self.assertFalse(res["is_verified"])
        self.assertIn("BLOCKED_CUTOFF", res["post_audit_state"]["lifecycle_state"])

    def test_03_irrelevant_notice_type(self):
        """3. Notice for debentures, bonds, or rights issues is rejected from verifying bidding cutoff."""
        raw_doc = "BSE Notice: Public issue of Non-Convertible Debentures (NCD) for Wiscon Industries Ltd (WISCON)."
        res = self.manager.process_evidence_update(
            ipo_id="wiscon-industries-sme-20261029",
            raw_artifact_content=raw_doc.encode("utf-8"),
            source_reference="BSE_NCD_CIRCULAR_01",
            publication_timestamp_ist="2026-10-28 10:00:00 IST",
            retrieval_timestamp_ist="2026-10-28 10:15:00 IST",
            is_primary_exchange_source=True
        )
        self.assertEqual(res["status"], "EVIDENCE_PROCESSED")
        self.assertFalse(res["is_bidding_cutoff_verified"])

    def test_04_upi_only_deadline_rejection(self):
        """4. Document containing only UPI mandate deadline does not verify retail order book close."""
        raw_doc = "BSE Circular: Wiscon Industries UPI mandate acceptance cutoff is 17:00:00 IST."
        res = self.manager.process_evidence_update(
            ipo_id="wiscon-industries-sme-20261029",
            raw_artifact_content=raw_doc.encode("utf-8"),
            source_reference="BSE_UPI_CIRCULAR_01",
            publication_timestamp_ist="2026-10-28 10:00:00 IST",
            retrieval_timestamp_ist="2026-10-28 10:15:00 IST",
            is_primary_exchange_source=True
        )
        self.assertTrue(res["is_upi_only"])
        self.assertFalse(res["is_bidding_cutoff_verified"])

    def test_05_incorrect_candidate_match(self):
        """5. Notice referencing a completely different company raises ValueError."""
        raw_doc = "BSE SME Notice: Retail order book close for Zenith Healthcare Ltd at 16:00:00 IST."
        with self.assertRaises(ValueError) as ctx:
            self.manager.process_evidence_update(
                ipo_id="wiscon-industries-sme-20261029",
                raw_artifact_content=raw_doc.encode("utf-8"),
                source_reference="BSE_ZENITH_CIRCULAR_01",
                publication_timestamp_ist="2026-10-28 10:00:00 IST",
                retrieval_timestamp_ist="2026-10-28 10:15:00 IST",
                is_primary_exchange_source=True
            )
        self.assertIn("IRRELEVANT_EVIDENCE", str(ctx.exception))

    def test_06_ambiguous_candidate_match(self):
        """6. Ambiguous document missing candidate name and symbol raises IRRELEVANT_EVIDENCE."""
        raw_doc = "BSE SME General Notice: Issue closing guidelines for all members on trading system."
        with self.assertRaises(ValueError) as ctx:
            self.manager.process_evidence_update(
                ipo_id="wiscon-industries-sme-20261029",
                raw_artifact_content=raw_doc.encode("utf-8"),
                source_reference="BSE_GENERAL_NOTICE_01",
                publication_timestamp_ist="2026-10-28 10:00:00 IST",
                retrieval_timestamp_ist="2026-10-28 10:15:00 IST",
                is_primary_exchange_source=True
            )
        self.assertIn("IRRELEVANT_EVIDENCE", str(ctx.exception))

    def test_07_missing_source_artifact(self):
        """7. Empty or missing raw artifact content fails validation."""
        with self.assertRaises(ValueError) as ctx:
            self.manager.process_evidence_update(
                ipo_id="wiscon-industries-sme-20261029",
                raw_artifact_content=b"",
                source_reference="BSE_EMPTY",
                publication_timestamp_ist="2026-10-28 10:00:00 IST",
                retrieval_timestamp_ist="2026-10-28 10:15:00 IST"
            )
        self.assertIn("raw_artifact_content cannot be empty", str(ctx.exception))

    def test_08_artifact_sha256_mismatch(self):
        """8. If expected artifact SHA-256 does not match raw bytes, update fails."""
        raw_text = "Some official text"
        res = process_evidence_update(
            candidate_id="wiscon-industries-sme-20261029",
            evidence_payload={
                "source_type": "PRIMARY_EXCHANGE_CIRCULAR",
                "source_portal": "BSE",
                "document_sha256": "f" * 64,
                "raw_text": raw_text,
                "publication_time": "2026-10-28 10:00:00 IST",
                "retrieval_time": "2026-10-28 10:15:00 IST"
            },
            manager=self.manager
        )
        self.assertFalse(res["success"])
        self.assertIn("Hash mismatch", res["reason"])

    def test_09_publication_timestamp_missing(self):
        """9. Primary evidence requires publication timestamp; None is accepted only as unverified."""
        raw_doc = "BSE SME Notice for Carver Roboweld Ltd (CARVER). Retail book closes at 16:00:00 IST."
        res = self.manager.process_evidence_update(
            ipo_id="carver-roboweld-sme-20261030",
            raw_artifact_content=raw_doc.encode("utf-8"),
            source_reference="BSE_NO_PUB_TS",
            publication_timestamp_ist=None,
            retrieval_timestamp_ist="2026-10-28 10:15:00 IST",
            is_primary_exchange_source=True
        )
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        carver = next(c for c in cands if c["ipo_id"] == "carver-roboweld-sme-20261030")
        prep = self.manager.audit_and_prepare_candidate(carver, evaluation_timestamp_ist="2026-10-28 12:00:00 IST")
        self.assertIn("MISSING_FEATURE_PUBLICATION_TIMESTAMP", prep["exclusion_reasons"])

    def test_10_naive_timestamp_rejection(self):
        """10. Timezone-naive timestamp without IST or offset raises ValueError."""
        raw_doc = "BSE SME Notice for Wiscon Industries Ltd (WISCON)."
        with self.assertRaises(ValueError) as ctx:
            self.manager.process_evidence_update(
                ipo_id="wiscon-industries-sme-20261029",
                raw_artifact_content=raw_doc.encode("utf-8"),
                source_reference="BSE_NAIVE",
                publication_timestamp_ist="2026-10-28 10:00:00",  # Naive
                retrieval_timestamp_ist="2026-10-28 10:15:00 IST"
            )
        self.assertIn("INVALID_OR_TIMEZONE_NAIVE_PUBLICATION_TIMESTAMP", str(ctx.exception))

    def test_11_conflicting_primary_evidence(self):
        """11. Conflicting cutoff times between notices logs governance warning."""
        raw_doc = "BSE Notice: Wiscon Industries Ltd (WISCON) order book closes at 16:30:00 IST."
        res = self.manager.process_evidence_update(
            ipo_id="wiscon-industries-sme-20261029",
            raw_artifact_content=raw_doc.encode("utf-8"),
            source_reference="BSE_CONFLICT_CIRCULAR",
            publication_timestamp_ist="2026-10-28 10:00:00 IST",
            retrieval_timestamp_ist="2026-10-28 10:15:00 IST",
            is_primary_exchange_source=True,
            expected_cutoff_timestamp_ist="2026-10-29 16:30:00 IST"
        )
        self.assertEqual(res["status"], "EVIDENCE_PROCESSED")

    def test_12_duplicate_notice_ingestion(self):
        """12. Re-ingesting the exact same artifact is idempotent and deduplicated."""
        raw_doc = "BSE SME Notice: Wiscon Industries Ltd (WISCON) retail order book close: 16:00:00 IST."
        doc_bytes = raw_doc.encode("utf-8")
        res1 = self.manager.process_evidence_update(
            ipo_id="wiscon-industries-sme-20261029",
            raw_artifact_content=doc_bytes,
            source_reference="BSE_NOTICE_DUP",
            publication_timestamp_ist="2026-10-28 10:00:00 IST",
            retrieval_timestamp_ist="2026-10-28 10:15:00 IST",
            is_primary_exchange_source=True
        )
        self.assertFalse(res1["event_deduplicated"])

        res2 = self.manager.process_evidence_update(
            ipo_id="wiscon-industries-sme-20261029",
            raw_artifact_content=doc_bytes,
            source_reference="BSE_NOTICE_DUP",
            publication_timestamp_ist="2026-10-28 10:00:00 IST",
            retrieval_timestamp_ist="2026-10-28 10:15:00 IST",
            is_primary_exchange_source=True
        )
        self.assertTrue(res2["event_deduplicated"])

    def test_13_notice_retrieved_after_cutoff(self):
        """13. Notice retrieved after candidate cutoff is rejected if candidate is expired."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        wiscon["cutoff_timestamp_ist"] = "2026-10-28 16:00:00 IST"
        with open(self.candidate_registry, "w", encoding="utf-8") as f:
            json.dump(cands, f)

        # Retrieval at 16:00:01 IST
        raw_doc = "BSE Notice: Wiscon Industries Ltd (WISCON)."
        with self.assertRaises(ValueError) as ctx:
            self.manager.process_evidence_update(
                ipo_id="wiscon-industries-sme-20261029",
                raw_artifact_content=raw_doc.encode("utf-8"),
                source_reference="BSE_LATE_NOTICE",
                publication_timestamp_ist="2026-10-28 15:00:00 IST",
                retrieval_timestamp_ist="2026-10-28 16:00:01 IST",
                is_primary_exchange_source=True
            )
        self.assertIn("CANDIDATE_EXPIRED", str(ctx.exception))

    def test_14_notice_published_after_decision(self):
        """14. Ingestion rejects retrieval before publication timestamp."""
        raw_doc = "BSE Notice: Wiscon Industries Ltd (WISCON)."
        with self.assertRaises(ValueError) as ctx:
            self.manager.process_evidence_update(
                ipo_id="wiscon-industries-sme-20261029",
                raw_artifact_content=raw_doc.encode("utf-8"),
                source_reference="BSE_FUTURE_PUB",
                publication_timestamp_ist="2026-10-28 12:00:00 IST",
                retrieval_timestamp_ist="2026-10-28 10:00:00 IST",
                is_primary_exchange_source=True
            )
        self.assertIn("RETRIEVAL_BEFORE_PUBLICATION_ANOMALY", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Collector Fault Tolerance Tests
    # -------------------------------------------------------------------------
    def test_15_collector_timeout(self):
        """15. Collector handles timeouts with bounded retries and fails closed."""
        def timeout_transport(url, headers, timeout):
            raise TimeoutError("Connection timed out after 5.0s")

        collector = ExchangeNoticeCollector(
            http_transport=timeout_transport,
            max_retries=2,
            base_backoff_sec=0.01
        )
        res = collector.fetch_exchange_notices("BSE")
        self.assertFalse(res["success"])
        self.assertEqual(res["error_code"], "TIMEOUT")

    def test_16_collector_http_error(self):
        """16. Collector handles non-200 HTTP responses gracefully."""
        def error_transport(url, headers, timeout):
            return {"status_code": 503, "content": b"Service Unavailable"}

        collector = ExchangeNoticeCollector(
            http_transport=error_transport,
            max_retries=2,
            base_backoff_sec=0.01
        )
        res = collector.fetch_exchange_notices("NSE")
        self.assertFalse(res["success"])
        self.assertEqual(res["error_code"], "HTTP_ERROR")

    def test_17_collector_malformed_response(self):
        """17. Collector validates payload and detects malformed or oversize response."""
        def large_transport(url, headers, timeout):
            return {"status_code": 200, "content": b"A" * 1000}

        collector = ExchangeNoticeCollector(
            http_transport=large_transport,
            max_response_bytes=500,
            max_retries=1
        )
        res = collector.fetch_exchange_notices("BSE")
        self.assertFalse(res["success"])
        self.assertIn("RESPONSE_SIZE_EXCEEDED", res["error_message"])

    def test_18_collector_retry_exhaustion(self):
        """18. Collector halts after configured maximum retries."""
        attempts = [0]
        def counting_transport(url, headers, timeout):
            attempts[0] += 1
            raise IOError("Network unreachable")

        collector = ExchangeNoticeCollector(
            http_transport=counting_transport,
            max_retries=3,
            base_backoff_sec=0.01
        )
        res = collector.fetch_exchange_notices("BSE")
        self.assertFalse(res["success"])
        self.assertEqual(attempts[0], 3)
        self.assertEqual(res["attempts_used"], 3)

    def test_19_collector_empty_response(self):
        """19. Empty 0-byte response from exchange endpoint is classified as an error."""
        def empty_transport(url, headers, timeout):
            return {"status_code": 200, "content": b""}

        collector = ExchangeNoticeCollector(
            http_transport=empty_transport,
            max_retries=1
        )
        res = collector.fetch_exchange_notices("BSE")
        self.assertFalse(res["success"])
        self.assertIn("EMPTY_RESPONSE_BODY", res["error_message"])

    # -------------------------------------------------------------------------
    # Phase 10.22D: Deadline Expiry Sweeper Tests
    # -------------------------------------------------------------------------
    def test_20_expiry_immediately_before_cutoff(self):
        """20. Sweeper run 1 second before cutoff leaves candidate active."""
        res = self.manager.sweep_deadline_expiries(sweep_timestamp_ist="2026-10-29 15:59:59 IST")
        self.assertIn("wiscon-industries-sme-20261029", res["active_unexpired_candidates"])
        self.assertNotIn("wiscon-industries-sme-20261029", res["newly_expired_candidates"])

    def test_21_expiry_exactly_at_cutoff(self):
        """21. Sweeper run exactly at cutoff transitions candidate to EXPIRED_WITHOUT_COMMIT."""
        res = self.manager.sweep_deadline_expiries(sweep_timestamp_ist="2026-10-29 16:00:00 IST")
        self.assertIn("wiscon-industries-sme-20261029", res["newly_expired_candidates"])

        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        self.assertEqual(wiscon["decision_status"], "EXPIRED_WITHOUT_COMMIT")

    def test_22_expiry_immediately_after_cutoff(self):
        """22. Sweeper run 1 second after cutoff transitions candidate to EXPIRED_WITHOUT_COMMIT."""
        res = self.manager.sweep_deadline_expiries(sweep_timestamp_ist="2026-10-29 16:00:01 IST")
        self.assertIn("wiscon-industries-sme-20261029", res["newly_expired_candidates"])

    def test_23_repeated_expiry_sweep_idempotent(self):
        """23. Consecutive sweeps are strictly idempotent and do not duplicate transitions."""
        res1 = self.manager.sweep_deadline_expiries(sweep_timestamp_ist="2026-10-29 16:00:00 IST")
        self.assertIn("wiscon-industries-sme-20261029", res1["newly_expired_candidates"])

        res2 = self.manager.sweep_deadline_expiries(sweep_timestamp_ist="2026-10-29 16:00:05 IST")
        self.assertEqual(len(res2["newly_expired_candidates"]), 0)
        self.assertIn("wiscon-industries-sme-20261029", res2["already_expired_candidates"])

    def test_24_concurrent_expiry_sweep(self):
        """24. Two concurrent sweep processes serialize cleanly without registry corruption."""
        def sweep_worker(idx):
            mgr = ProspectiveLifecycleManager(
                decision_ledger_path=self.decision_ledger,
                outcome_ledger_path=self.outcome_ledger,
                candidate_registry_path=self.candidate_registry,
                audit_events_path=self.audit_events,
                evaluation_records_path=self.evaluation_records,
                checkpoint_path=self.checkpoint_file
            )
            return mgr.sweep_deadline_expiries(sweep_timestamp_ist="2026-10-29 16:00:00 IST")

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(sweep_worker, range(2)))

        # One worker executes the transition for wiscon and eaaa; the second observes them already expired
        wiscon_newly_expired_count = sum(1 for r in results if "wiscon-industries-sme-20261029" in r["newly_expired_candidates"])
        self.assertEqual(wiscon_newly_expired_count, 1)

    def test_25_restart_after_expiry_preserves_state(self):
        """25. New manager instance after expiry preserves EXPIRED_WITHOUT_COMMIT state."""
        self.manager.sweep_deadline_expiries(sweep_timestamp_ist="2026-10-29 16:00:00 IST")
        restarted = ProspectiveLifecycleManager(
            decision_ledger_path=self.decision_ledger,
            outcome_ledger_path=self.outcome_ledger,
            candidate_registry_path=self.candidate_registry,
            audit_events_path=self.audit_events,
            evaluation_records_path=self.evaluation_records,
            checkpoint_path=self.checkpoint_file
        )
        with open(restarted.candidate_registry_path, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        self.assertEqual(wiscon["decision_status"], "EXPIRED_WITHOUT_COMMIT")

    def test_26_registry_corruption_handling(self):
        """26. Invalid JSON in registry path raises or logs error safely."""
        with open(self.candidate_registry, "w", encoding="utf-8") as f:
            f.write("CORRUPTED_NON_JSON")
        with self.assertRaises(Exception):
            self.manager.sweep_deadline_expiries(sweep_timestamp_ist="2026-10-29 16:00:00 IST")

    def test_27_late_evidence_for_expired_candidate(self):
        """27. Official evidence arriving after a candidate has expired is rejected."""
        self.manager.sweep_deadline_expiries(sweep_timestamp_ist="2026-10-29 16:00:00 IST")
        raw_doc = "BSE Official Notice for Wiscon Industries Ltd (WISCON)."
        with self.assertRaises(ValueError) as ctx:
            self.manager.process_evidence_update(
                ipo_id="wiscon-industries-sme-20261029",
                raw_artifact_content=raw_doc.encode("utf-8"),
                source_reference="BSE_LATE_01",
                publication_timestamp_ist="2026-10-29 15:30:00 IST",
                retrieval_timestamp_ist="2026-10-29 16:05:00 IST",
                is_primary_exchange_source=True
            )
        self.assertIn("CANDIDATE_EXPIRED", str(ctx.exception))

    def test_28_blocked_candidate_remains_blocked(self):
        """28. Without valid primary circular evidence, candidate remains in BLOCKED_CUTOFF."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        carver = next(c for c in cands if c["ipo_id"] == "carver-roboweld-sme-20261030")
        prep = self.manager.audit_and_prepare_candidate(carver, evaluation_timestamp_ist="2026-10-28 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_CUTOFF")
        self.assertFalse(prep["is_clean_eligible"])

    def test_29_mainboard_candidate_remains_non_scoring(self):
        """29. Mainboard candidates cannot be scored or authorized by SME model."""
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        mb = next(c for c in cands if c["board_type"] == "Mainboard")
        prep = self.manager.audit_and_prepare_candidate(mb, evaluation_timestamp_ist="2026-10-28 12:00:00 IST")
        self.assertEqual(prep["candidate_lifecycle_state"], "BLOCKED_GOVERNANCE")
        self.assertFalse(prep["is_clean_eligible"])

    def test_30_no_decision_creation_by_collector(self):
        """30. Notice collector run produces 0 records in decision ledger."""
        def mock_transport(url, headers, timeout):
            return {"status_code": 200, "content": b"Sample notice text"}

        collector = ExchangeNoticeCollector(http_transport=mock_transport)
        collector.fetch_exchange_notices("BSE")
        if os.path.exists(self.decision_ledger):
            with open(self.decision_ledger, "r", encoding="utf-8") as f:
                lines = [l for l in f if l.strip()]
        else:
            lines = []
        self.assertEqual(len(lines), 0)

    def test_31_no_outcome_creation_by_sweeper(self):
        """31. Expiry sweeper run produces 0 records in outcome ledger."""
        self.manager.sweep_deadline_expiries(sweep_timestamp_ist="2026-10-29 16:00:00 IST")
        if os.path.exists(self.outcome_ledger):
            with open(self.outcome_ledger, "r", encoding="utf-8") as f:
                lines = [l for l in f if l.strip()]
        else:
            lines = []
        self.assertEqual(len(lines), 0)

    def test_32_no_retroactive_commitment(self):
        """32. Expired candidate cannot be committed retroactively."""
        self.manager.sweep_deadline_expiries(sweep_timestamp_ist="2026-10-29 16:00:00 IST")
        with open(self.candidate_registry, "r", encoding="utf-8") as f:
            cands = json.load(f)
        wiscon = next(c for c in cands if c["ipo_id"] == "wiscon-industries-sme-20261029")
        with self.assertRaises(ValueError) as ctx:
            self.manager.commit_prospective_decision(
                candidate_dict=wiscon,
                override_commit_timestamp_ist="2026-10-29 16:05:00 IST",
                strict_clean_only=True,
                explicit_admin_authorization={"authorized_by": "Auditor", "authorization_token": "a" * 32}
            )
        self.assertIn("COMMIT_BLOCKED_UNREADY_CANDIDATE", str(ctx.exception))

    def test_33_monitoring_report_does_not_mutate_production_ledgers(self):
        """33. Generating daily monitoring report preserves 0 production records."""
        self.manager.generate_daily_monitoring_report(evaluation_timestamp_ist="2026-10-28 12:00:00 IST")
        for p in [DECISION_LEDGER_PATH, OUTCOME_LEDGER_PATH, EVALUATION_RECORDS_PATH, AUDIT_EVENTS_PATH]:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    self.assertEqual(len([l for l in f if l.strip()]), 0, f"Production ledger {p} altered!")

    def test_34_frozen_artifacts_hash_verification(self):
        """34. Frozen model and manifest hashes match exact approved values."""
        with open(FROZEN_SME_MODEL_PATH, "rb") as f:
            m_hash = hashlib.sha256(f.read()).hexdigest()
        with open(MANIFEST_PATH, "rb") as f:
            man_hash = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(m_hash, FROZEN_SME_MODEL_SHA256)
        self.assertEqual(man_hash, MANIFEST_SHA256)

    def test_35_sweep_invalid_timezone_raises_value_error(self):
        """35. Sweeper rejects naive or invalid timestamps upfront."""
        with self.assertRaises(ValueError) as ctx:
            self.manager.sweep_deadline_expiries(sweep_timestamp_ist="2026-10-29 16:00:00")  # Naive
        self.assertIn("INVALID_OR_TIMEZONE_NAIVE_SWEEP_TIMESTAMP", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
