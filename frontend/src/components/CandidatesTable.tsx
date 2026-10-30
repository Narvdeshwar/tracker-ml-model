import React, { useState } from 'react';
import { Layers, CheckCircle2, XCircle, Clock, ChevronDown, ChevronUp } from 'lucide-react';
import { CandidateReport } from '../types';

export function CandidatesTable({ candidates }: { candidates: CandidateReport[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  return (
    <section className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
      <div className="px-6 py-3 border-b border-slate-800 flex justify-between items-center text-xs">
        <div className="flex items-center gap-2 font-semibold text-white">
          <Layers className="w-4 h-4 text-indigo-400" /> Active IPO Trackers & Apply Ratings
        </div>
        <span className="text-slate-400">{candidates.length} Tracked Issues</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-950/60 text-slate-400 uppercase font-medium border-b border-slate-800">
            <tr>
              <th className="px-5 py-2.5">Company</th>
              <th className="px-4 py-2.5">Type</th>
              <th className="px-4 py-2.5">Cutoff</th>
              <th className="px-4 py-2.5">Official Notice</th>
              <th className="px-4 py-2.5">Action Status</th>
              <th className="px-4 py-2.5">Apply Rating</th>
              <th className="px-4 py-2.5 text-right">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {candidates.map((c) => {
              const isExp = expanded === c.ipo_id;
              const pct = c.predicted_probability ? (c.predicted_probability * 100).toFixed(0) : null;
              return (
                <React.Fragment key={c.ipo_id}>
                  <tr className="hover:bg-slate-800/40">
                    <td className="px-5 py-3 font-medium text-white">{c.company_name}</td>
                    <td className="px-4 py-3"><span className="px-2 py-0.5 rounded bg-slate-800 text-[11px]">{c.board_type}</span></td>
                    <td className="px-4 py-3 text-slate-300 font-mono text-[11px]">{c.asserted_cutoff_timestamp_ist}</td>
                    <td className="px-4 py-3">
                      {c.cutoff_verification_status === 'VERIFIED' ? <span className="text-emerald-400 font-medium flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5"/> Verified</span> :
                       c.cutoff_verification_status === 'EXPIRED' ? <span className="text-rose-400 font-medium flex items-center gap-1"><XCircle className="w-3.5 h-3.5"/> Closed</span> :
                       <span className="text-amber-400 font-medium flex items-center gap-1"><Clock className="w-3.5 h-3.5"/> Pending</span>}
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                        {c.current_lifecycle_state === 'EXPIRED_WITHOUT_COMMIT' ? 'MISSED / CLOSED' :
                         c.current_lifecycle_state === 'BLOCKED_CUTOFF' ? 'WAITING FOR CIRCULAR' : 'NOT ELIGIBLE (MAINBOARD)'}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono font-bold text-emerald-400">{pct ? `${pct}% Profit Chance` : 'N/A'}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => setExpanded(isExp ? null : c.ipo_id)} className="p-1 text-slate-400 hover:text-white">
                        {isExp ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                    </td>
                  </tr>
                  {isExp && (
                    <tr className="bg-slate-950/60 border-b border-slate-800 text-xs">
                      <td colSpan={7} className="px-6 py-3 space-y-1 text-slate-300">
                        <div className="font-semibold text-slate-400">Reason: {c.blocking_reasons[0] || 'All checks passed'}</div>
                        <div className="text-slate-400">Action: {c.next_required_action} | Commit: <span className="text-rose-400 font-bold">BLOCKED</span></div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
