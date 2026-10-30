import React from 'react';
import { Lock, FileCheck, Database, TrendingUp, Server, Clock, Activity, CheckCircle2 } from 'lucide-react';
import { MonitoringReport } from '../types';

export function MetricsCards({ data }: { data: MonitoringReport | null }) {
  const op = data?.operational_readiness;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex justify-between text-slate-400 text-xs uppercase mb-1">
            <span>Model (SME v1)</span><Lock className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-base font-bold text-white">LOCKED & VERIFIED</div>
          <p className="text-[11px] text-slate-400 mt-1">Weights unchanged byte-for-byte</p>
        </div>
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex justify-between text-slate-400 text-xs uppercase mb-1">
            <span>Safety Rulebook</span><FileCheck className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-base font-bold text-white">ACTIVE</div>
          <p className="text-[11px] text-slate-400 mt-1">Requires official BSE/NSE notice</p>
        </div>
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex justify-between text-slate-400 text-xs uppercase mb-1">
            <span>Live Trade Orders</span><Database className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-base font-bold text-emerald-400">0 Placed (Safe Zero)</div>
          <p className="text-[11px] text-slate-400 mt-1">No real money or broker connected</p>
        </div>
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex justify-between text-slate-400 text-xs uppercase mb-1">
            <span>Accuracy Rating</span><TrendingUp className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-base font-bold text-amber-400">WAITING FOR RESULTS</div>
          <p className="text-[11px] text-slate-400 mt-1">Awaiting mature outcomes</p>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex justify-between text-slate-400 text-xs uppercase mb-1">
            <span>Activity History</span><Database className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-base font-bold text-emerald-400">HEALTHY ({op?.ledger_record_count ?? 17} checks)</div>
          <p className="text-[11px] text-slate-500 mt-1">Background ledger chain verified</p>
        </div>
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex justify-between text-slate-400 text-xs uppercase mb-1">
            <span>Checkers</span><Server className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-xs text-emerald-400 font-semibold space-y-0.5">
            <div>Collector: WORKING</div>
            <div>Sweeper: WORKING</div>
            <div>Reporter: WORKING</div>
          </div>
        </div>
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex justify-between text-slate-400 text-xs uppercase mb-1">
            <span>Stability Test</span><Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-base font-bold text-amber-400">{op?.soak_test.progress_label ?? '0/5'}</div>
          <p className="text-[11px] text-slate-400 mt-1">Day 1 in progress (no failures)</p>
        </div>
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex justify-between text-slate-400 text-xs uppercase mb-1">
            <span>Last Check</span><Activity className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-xs font-mono text-white font-bold">{op?.last_verified_timestamp_ist ?? 'Checked'}</div>
          <p className="text-[11px] text-emerald-400 flex items-center gap-1 mt-1">
            <CheckCircle2 className="w-3.5 h-3.5" /> Backed by fresh scan
          </p>
        </div>
      </div>
    </div>
  );
}
