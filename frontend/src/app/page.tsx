'use client';

import React, { useState, useEffect } from 'react';
import { ShieldCheck, Activity, RefreshCw, XCircle } from 'lucide-react';
import { MonitoringReport } from '../types';
import { MetricsCards } from '../components/MetricsCards';
import { CandidatesTable } from '../components/CandidatesTable';
import { PastIposTable } from '../components/PastIposTable';

export default function ProspectiveDashboard() {
  const [data, setData] = useState<MonitoringReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMonitoringData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/monitoring/status');
      if (!res.ok) throw new Error(`API responded with HTTP ${res.status}`);
      setData(await res.json());
    } catch (err: any) {
      setError(err.message || 'Failed to connect to backend surveillance service');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMonitoringData();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <header className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-800 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
              <ShieldCheck className="w-6 h-6" />
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              IPO Research & Prediction Dashboard
            </h1>
          </div>
          <p className="mt-1 text-sm text-slate-400">
            Automated check system, simple apply ratings, and official exchange validation
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Activity className="w-3.5 h-3.5" />
            RESEARCH & TEST MODE ONLY (NO REAL TRADING)
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

      {error && (
        <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <MetricsCards data={data} />
      <CandidatesTable candidates={data?.candidate_reports || []} />
      <PastIposTable pastIpos={data?.past_ipos_preview || []} />

      <footer className="p-4 rounded-lg bg-slate-900/60 border border-slate-800 text-xs text-slate-400">
        Strict Research Mode: Apply Rating is an automated model calculation. No live trade or real-money execution occurs.
      </footer>
    </div>
  );
}
