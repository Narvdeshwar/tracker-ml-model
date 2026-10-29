"""
Comprehensive automated tests for Phase 10.5:
  1. Operational health reporting separately from predictive performance.
  2. Input feature quality monitoring (feat_nifty50_ret5s_pct, feat_india_vix, feat_recent5_sentiment).
  3. Detection of missing values, NaN, and Infinity in feature inputs.
  4. Timezone-aware temporal checks (IST/+05:30) and publication timestamp vs cutoff validation.
  5. Statistical drift diagnostics against frozen training reference (SME 2020-2024, N=368).
  6. Sample size gating for drift: explicit INCONCLUSIVE_INSUFFICIENT_SAMPLE_SIZE when N < 15.
  7. Outcome lifecycle tracking across canonical 5 states.
  8. Append-only, SHA-256 chained governance audit events logging.
  9. Three-population accounting proof: Pop 1 = Pop 2 + Pop 3, with zero overlap.
  10. Read-only safety verification: frozen model and manifest hashes untouched.
"""

import os
import json
import tempfile
import shutil
import hashlib
import unittest
import numpy as np
from fastapi.testclient import TestClient

from src.surveillance_monitor import SurveillanceMonitor, FROZEN_TRAINING_FEATURE_REFERENCE
from src.api.main import app

class TestPhase105Surveillance(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.client = TestClient(app)
        self.audit_events_path = os.path.join(self.temp_dir, "test_audit_events.jsonl")
        self.monitor = SurveillanceMonitor(
            audit_events_path=self.audit_events_path
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_operational_health_separates_health_from_predictive_performance(self):
        """Verifies operational health is HEALTHY while predictive performance is INCONCLUSIVE_ZERO_MATURE_OUTCOMES."""
        rep = self.monitor.get_operational_health_report()
        self.assertEqual(rep["operational_status"], "HEALTHY")
        self.assertTrue(rep["real_trading_prohibited"])
        self.assertEqual(rep["predictive_performance_status"], "INCONCLUSIVE_ZERO_MATURE_OUTCOMES")
        self.assertTrue(rep["manifest_integrity"]["valid"])
        self.assertTrue(rep["model_integrity"]["valid"])

    def test_feature_quality_monitoring_detects_nan_and_missing(self):
        """Verifies audit_feature_quality detects missing values, NaNs, and infinities."""
        # Create a temp candidate registry with synthetic defects
        temp_candidates_path = os.path.join(self.temp_dir, "test_candidates.json")
        bad_candidates = [
            {
                "ipo_id": "test-defect-1",
                "cutoff_timestamp_ist": "2026-11-05 17:00:00 IST",
                "source_publication_timestamp_ist": "2026-11-04 12:00:00 IST",
                "features": {
                    "feat_nifty50_ret5s_pct": np.nan,  # NaN
                    "feat_india_vix": float('inf'),    # Infinity
                    "feat_recent5_sentiment": None      # Missing
                }
            },
            {
                "ipo_id": "test-valid-1",
                "cutoff_timestamp_ist": "2026-11-05 17:00:00 IST",
                "source_publication_timestamp_ist": "2026-11-04 12:00:00 IST",
                "features": {
                    "feat_nifty50_ret5s_pct": 0.50,
                    "feat_india_vix": 14.5,
                    "feat_recent5_sentiment": 45.0
                }
            }
        ]
        with open(temp_candidates_path, "w", encoding="utf-8") as f:
            json.dump(bad_candidates, f)

        temp_monitor = SurveillanceMonitor(candidate_registry_path=temp_candidates_path)
        res = temp_monitor.audit_feature_quality()
        
        sums = res["feature_summaries"]
        self.assertEqual(sums["feat_nifty50_ret5s_pct"]["invalid_count"], 1)
        self.assertEqual(sums["feat_india_vix"]["invalid_count"], 1)
        self.assertEqual(sums["feat_recent5_sentiment"]["missing_count"], 1)
        self.assertEqual(sums["feat_nifty50_ret5s_pct"]["valid_count"], 1)

    def test_feature_quality_temporal_compliance_late_published_warning(self):
        """Verifies that feature publication after cutoff triggers late_published_count and warning."""
        temp_candidates_path = os.path.join(self.temp_dir, "test_candidates_late.json")
        candidates = [
            {
                "ipo_id": "test-late-feat",
                "cutoff_timestamp_ist": "2026-11-05 17:00:00 IST",
                "source_publication_timestamp_ist": "2026-11-05 18:00:00 IST",  # 1 hour late
                "features": {"feat_nifty50_ret5s_pct": 0.5}
            }
        ]
        with open(temp_candidates_path, "w", encoding="utf-8") as f:
            json.dump(candidates, f)

        temp_monitor = SurveillanceMonitor(candidate_registry_path=temp_candidates_path)
        res = temp_monitor.audit_feature_quality()
        self.assertEqual(res["status"], "WARNING_TEMPORAL_ANOMALY")
        self.assertEqual(res["temporal_compliance"]["late_published_count"], 1)

    def test_drift_surveillance_sample_size_gating(self):
        """Verifies drift surveillance returns INCONCLUSIVE when N < 15."""
        res = self.monitor.audit_drift_surveillance(min_sample_size=15)
        self.assertEqual(res["status"], "INCONCLUSIVE_INSUFFICIENT_SAMPLE_SIZE")
        self.assertEqual(res["sample_size_observed"], 2)  # Only 2 scored in registry
        self.assertIn("minimum_required_sample_size", res)

    def test_drift_surveillance_on_synthetic_fixture(self):
        """Tests deterministic drift calculation when sample size hurdle is met."""
        temp_candidates_path = os.path.join(self.temp_dir, "test_candidates_drift.json")
        # Generate 20 synthetic candidates with elevated VIX (mean ~25 vs ref 14.82)
        candidates = []
        for i in range(20):
            candidates.append({
                "ipo_id": f"synth-ipo-{i}",
                "p_positive_open": 0.70,
                "features": {
                    "feat_nifty50_ret5s_pct": 0.40,
                    "feat_india_vix": 25.0,  # Elevated VIX
                    "feat_recent5_sentiment": 40.0
                }
            })
        with open(temp_candidates_path, "w", encoding="utf-8") as f:
            json.dump(candidates, f)

        temp_monitor = SurveillanceMonitor(candidate_registry_path=temp_candidates_path)
        res = temp_monitor.audit_drift_surveillance(min_sample_size=15)
        
        self.assertEqual(res["status"], "EVALUATED")
        self.assertEqual(res["sample_size_observed"], 20)
        vix_drift = res["feature_drift"]["feat_india_vix"]
        self.assertEqual(vix_drift["status"], "SIGNIFICANT_DRIFT")
        self.assertGreater(vix_drift["mean_shift_in_ref_std"], 2.0)

    def test_outcome_lifecycle_distribution(self):
        """Verifies outcome lifecycle correctly maps tracked candidates."""
        res = self.monitor.audit_outcome_lifecycle()
        self.assertIn("state_distribution", res)
        self.assertIn("tracked_candidates_lifecycle", res)
        self.assertEqual(len(res["tracked_candidates_lifecycle"]), 6)

    def test_governance_audit_trail_logging_and_hash_chain(self):
        """Verifies immutable audit event appending and SHA-256 hash chaining."""
        evt1 = self.monitor.log_governance_event(
            event_type="MODEL_HASH_CHECK",
            affected_entity="Model_6B_SME_v1.0",
            severity="INFO",
            reason_code="PERIODIC_SHA256_AUDIT",
            description="Bit-for-bit SHA256 verified against manifest."
        )
        self.assertEqual(evt1["prev_event_sha256"], "GENESIS_AUDIT_EVENT")
        self.assertIsNotNone(evt1["event_sha256"])

        # Second event must chain from evt1
        evt2 = self.monitor.log_governance_event(
            event_type="DATA_QUALITY_ALERT",
            affected_entity="Wiscon Industries",
            severity="WARNING",
            reason_code="FEATURE_CHECK_PASS",
            description="Features verified pre-cutoff."
        )
        self.assertEqual(evt2["prev_event_sha256"], evt1["event_sha256"])
        
        # Read back trail
        trail = self.monitor.get_governance_audit_trail()
        self.assertEqual(len(trail), 2)
        self.assertEqual(trail[0]["event_id"], evt1["event_id"])
        self.assertEqual(trail[1]["event_id"], evt2["event_id"])

    def test_three_population_reconciliation_exact_mutual_exclusion(self):
        """
        Mathematically verifies 3-population accounting:
        Total Tracked (Pop 1) = Pop 2 (Clean) + Pop 3 (Excluded/Unverified), with overlap = 0.
        """
        res = self.monitor.audit_population_reconciliation()
        self.assertEqual(res["accounting_status"], "EXACT_MUTUAL_EXCLUSION_VERIFIED")
        self.assertEqual(res["overlap_count"], 0)
        self.assertTrue(res["is_mutually_exclusive"])
        self.assertEqual(res["population_1_eligible_coverage_total"], 6)
        self.assertEqual(
            res["population_1_eligible_coverage_total"],
            res["population_2_clean_prospective_count"] + res["population_3_excluded_unverified_count"]
        )

    def test_fastapi_monitoring_endpoints(self):
        """Verifies all Phase 10.5 monitoring endpoints respond with HTTP 200 and expected schemas."""
        res_health = self.client.get("/api/monitoring/operational-health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json()["operational_status"], "HEALTHY")

        res_feat = self.client.get("/api/monitoring/feature-quality")
        self.assertEqual(res_feat.status_code, 200)
        self.assertIn("feature_summaries", res_feat.json())

        res_drift = self.client.get("/api/monitoring/drift")
        self.assertEqual(res_drift.status_code, 200)
        self.assertEqual(res_drift.json()["status"], "INCONCLUSIVE_INSUFFICIENT_SAMPLE_SIZE")

        res_life = self.client.get("/api/monitoring/outcome-lifecycle")
        self.assertEqual(res_life.status_code, 200)
        self.assertIn("state_distribution", res_life.json())

        res_audit = self.client.get("/api/monitoring/governance-audit-trail")
        self.assertEqual(res_audit.status_code, 200)
        self.assertIn("events", res_audit.json())

        res_pop = self.client.get("/api/monitoring/population-reconciliation")
        self.assertEqual(res_pop.status_code, 200)
        self.assertEqual(res_pop.json()["accounting_status"], "EXACT_MUTUAL_EXCLUSION_VERIFIED")

    def test_read_only_protection_during_monitoring(self):
        """Ensures monitoring requests never alter frozen model or manifest files."""
        manifest_path = "models/frozen/phase_9b_baseline_manifest.json"
        sme_model_path = "models/frozen/model_6b_sme_v1.joblib"
        
        with open(manifest_path, "rb") as f:
            manifest_sha_before = hashlib.sha256(f.read()).hexdigest()
        with open(sme_model_path, "rb") as f:
            model_sha_before = hashlib.sha256(f.read()).hexdigest()

        # Execute monitoring calls
        self.client.get("/api/monitoring/operational-health")
        self.client.get("/api/monitoring/feature-quality")
        self.client.get("/api/monitoring/drift")
        self.client.get("/api/monitoring/outcome-lifecycle")
        self.client.get("/api/monitoring/population-reconciliation")

        with open(manifest_path, "rb") as f:
            manifest_sha_after = hashlib.sha256(f.read()).hexdigest()
        with open(sme_model_path, "rb") as f:
            model_sha_after = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(manifest_sha_before, manifest_sha_after)
        self.assertEqual(model_sha_before, model_sha_after)


if __name__ == "__main__":
    unittest.main()
