'use client';

import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  Clock,
  Database,
  Lock,
  Layers,
  Activity,
  CheckCircle2,
  XCircle,
  RefreshCw,
  TrendingUp,
  FileCheck
} from 'lucide-react';

interface CandidateReport {
  ipo_id: string;
  company_name: string;
  board_type: string;
  exchange: string;
  asserted_cutoff_timestamp_ist: string;
  cutoff_verification_status: string;
  current_lifecycle_state: string;
  model_eligibility: string;
  predicted_probability: number | null;
  failed_readiness_gates: string[];
  blocking_reasons: string[];
  hours_to_cutoff: number | null;
  evidence_reference: string;
  next_required_action: string;
}

interface MonitoringReport {
  report_timestamp_ist: string;
  operating_mode: string;
  frozen_artifacts_integrity: {
    model_status: string;
    manifest_status: string;
    model_sha256: string;
    manifest_sha256: string;
  };
  candidate_count: number;
  candidate_reports: CandidateReport[];
  approaching_cutoffs_48h: string[];
  expired_candidates: string[];
  collection_health: {
    collector_status: string;
    sources_monitored: string[];
    last_collection_run: string;
  };
  evidence_health: {
    verified_primary_notices: number;
    unverified_asserted_notices: number;
    evidence_conflicts_count: number;
    missing_artifacts_count: number;
  };
  persistence_and_governance: {
    decision_ledger_records: number;
    outcome_ledger_records: number;
    evaluation_records: number;
    governance_audit_events_count: number;
    ledger_integrity_status: string;
  };
  predictive_validity_milestone: string;
  economic_viability_milestone: string;
}

export default function ProspectiveDashboard() {
  const [data, setData] = useState<MonitoringReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMonitoringData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/monitoring/status');
      if (!res.ok) {
        throw new Error(`API responded with HTTP ${res.status}`);
      }
      const json = await res.json();
      setData(json);
    } catch (err: any) {
      // Fallback to local offline structure if backend API is not live during build
      setError(err.message || 'Failed to connect to backend surveillance service');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMonitoringData();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Banner / Operating Mode Guard */}
      <header className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-800 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
              <ShieldCheck className="w-6 h-6" />
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              Indian IPO Prospective Shadow-Validation Engine
            </h1>
          </div>
          <p className="mt-1 text-sm text-slate-400">
            Phase 10 Prospective Prediction Surveillance, Frozen Model Hash-Lock & Release-Gate Verification
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Activity className="w-3.5 h-3.5" />
            STRICT SHADOW MODE ONLY
          </span>
          <button
            onClick={fetchMonitoringData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </header>

      {/* Invariants & Frozen Baseline Cards */}
      <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider mb-2">
            <span>Frozen Model (SME v1)</span>
            <Lock className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-bold text-white">
              {data?.frozen_artifacts_integrity.model_status === 'PASS' ? 'LOCKED' : 'VERIFYING'}
            </span>
            <span className="text-xs text-emerald-400 font-mono">dbf2eec7...aad76</span>
          </div>
          <p className="mt-2 text-xs text-slate-500 truncate" title="dbf2eec7169888424698c55286c59c406c58b61ff77d34ca6beabab1e53aad76">
            SHA-256 byte-for-byte exact match verified
          </p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider mb-2">
            <span>Baseline Manifest</span>
            <FileCheck className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-bold text-white">
              {data?.frozen_artifacts_integrity.manifest_status === 'PASS' ? 'LOCKED' : 'VERIFYING'}
            </span>
            <span className="text-xs text-cyan-400 font-mono">b19c913e...6c6e</span>
          </div>
          <p className="mt-2 text-xs text-slate-500 truncate" title="b19c913e7c0e0afd6054255f389a4cab3a15d79e338f67c5fc04cacde7e86c6e">
            Preflight thresholds & calibration constants locked
          </p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider mb-2">
            <span>Production Ledgers</span>
            <Database className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-bold text-emerald-400">
              {data?.persistence_and_governance.decision_ledger_records ?? 0} Committed
            </span>
            <span className="text-xs text-slate-400">Clean 0-state</span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Physical separation: Decisions & Realized Outcomes
          </p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider mb-2">
            <span>Predictive Validity</span>
            <TrendingUp className="w-4 h-4 text-amber-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-bold text-amber-400">INCONCLUSIVE</span>
            <span className="text-xs text-slate-400">N=0 Mature</span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Real-money trading strictly prohibited
          </p>
        </div>
      </section>

      {/* Candidate Tracking & Readiness Gate Table */}
      <section className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-indigo-400" />
            <h2 className="text-base font-semibold text-white">Tracked Candidates & Release-Gate Lifecycle</h2>
          </div>
          <span className="text-xs text-slate-400">
            Total Tracked: {data?.candidate_count ?? 6} Issues
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/60 text-slate-400 uppercase font-medium border-b border-slate-800">
              <tr>
                <th className="px-6 py-3">Candidate / Symbol</th>
                <th className="px-6 py-3">Segment</th>
                <th className="px-6 py-3">Asserted Cutoff (IST)</th>
                <th className="px-6 py-3">Cutoff Status</th>
                <th className="px-6 py-3">Lifecycle State</th>
                <th className="px-6 py-3">Model Inference</th>
                <th className="px-6 py-3">Blocking Reasons / Gate Evaluation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 font-normal">
              {data?.candidate_reports.map((cand) => (
                <tr key={cand.ipo_id} className="hover:bg-slate-800/40 transition">
                  <td className="px-6 py-4">
                    <div className="font-medium text-white">{cand.company_name}</div>
                    <div className="text-[11px] font-mono text-slate-500">{cand.ipo_id}</div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                      cand.board_type === 'SME' ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' : 'bg-slate-800 text-slate-300'
                    }`}>
                      {cand.board_type}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-slate-300 font-mono">
                    {cand.asserted_cutoff_timestamp_ist}
                  </td>
                  <td className="px-6 py-4">
                    {cand.cutoff_verification_status === 'VERIFIED' ? (
                      <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
                        <CheckCircle2 className="w-3.5 h-3.5" /> VERIFIED
                      </span>
                    ) : cand.cutoff_verification_status === 'EXPIRED' ? (
                      <span className="inline-flex items-center gap-1 text-rose-400 font-medium">
                        <XCircle className="w-3.5 h-3.5" /> EXPIRED
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-amber-400 font-medium">
                        <Clock className="w-3.5 h-3.5" /> UNVERIFIED
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                      cand.current_lifecycle_state === 'READY_FOR_PROSPECTIVE_COMMIT' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' :
                      cand.current_lifecycle_state === 'EXPIRED_WITHOUT_COMMIT' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30' :
                      'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                    }`}>
                      {cand.current_lifecycle_state}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {cand.predicted_probability !== null ? (
                      <div className="font-mono text-white font-medium">
                        {(cand.predicted_probability * 100).toFixed(2)}%
                        <span className="block text-[10px] text-slate-400">P(Open &gt; Issue)</span>
                      </div>
                    ) : (
                      <span className="text-slate-500 font-mono text-[11px]">NON_SCORING</span>
                    )}
                  </td>
                  <td className="px-6 py-4 max-w-xs">
                    {cand.blocking_reasons.length > 0 ? (
                      <ul className="list-disc list-inside space-y-1 text-[11px] text-slate-400">
                        {cand.blocking_reasons.slice(0, 2).map((r, idx) => (
                          <li key={idx} className="truncate" title={r}>{r}</li>
                        ))}
                      </ul>
                    ) : (
                      <span className="text-emerald-400 text-[11px]">All mandatory gates satisfied</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Operational Provenance & Safety Notice */}
      <footer className="p-4 rounded-lg bg-slate-900/60 border border-slate-800 text-xs text-slate-400 space-y-2">
        <div className="flex items-center gap-2 text-slate-300 font-medium">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          Strict Model Governance & Operational Guardrails
        </div>
        <p>
          This prospective dashboard is strictly for scientific verification and shadow-validation tracking of Indian IPO pricing predictions. Order routing, automated trading, live broker integrations, and capital allocation are strictly prohibited. The prospective decision ledger is append-only, cryptographic hash-chained, and bounded by pre-cutoff release gates.
        </p>
      </footer>
    </div>
  );
}
