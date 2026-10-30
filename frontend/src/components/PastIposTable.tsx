import React from 'react';
import { Calendar, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { PastIPO } from '../types';

export function PastIposTable({ pastIpos }: { pastIpos: PastIPO[] }) {
  return (
    <section className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
      <div className="px-6 py-3 border-b border-slate-800 flex justify-between items-center text-xs">
        <div className="flex items-center gap-2 font-semibold text-white">
          <Calendar className="w-4 h-4 text-cyan-400" /> Past Month IPO Results & Model Accuracy
        </div>
        <span className="text-slate-400">Actual Market Open vs AI Prediction</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-950/60 text-slate-400 uppercase font-medium border-b border-slate-800">
            <tr>
              <th className="px-5 py-2.5">Company</th>
              <th className="px-4 py-2.5">Date</th>
              <th className="px-4 py-2.5">Issue</th>
              <th className="px-4 py-2.5">Open</th>
              <th className="px-4 py-2.5">AI Rating</th>
              <th className="px-4 py-2.5">Gain</th>
              <th className="px-4 py-2.5">Result</th>
              <th className="px-4 py-2.5">Accuracy</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {pastIpos.map((p, idx) => {
              const isProfit = p.gain_percentage >= 0;
              return (
                <tr key={idx} className="hover:bg-slate-800/40">
                  <td className="px-5 py-3 font-medium text-white">{p.company_name}</td>
                  <td className="px-4 py-3 text-slate-400 font-mono text-[11px]">{p.listing_date}</td>
                  <td className="px-4 py-3 text-slate-300 font-mono">₹{p.issue_price.toFixed(0)}</td>
                  <td className="px-4 py-3 text-white font-mono font-medium">₹{p.listing_open.toFixed(0)}</td>
                  <td className="px-4 py-3 font-mono text-cyan-400 font-bold">{p.model_prediction_label}</td>
                  <td className="px-4 py-3 font-mono font-bold">
                    <span className={`inline-flex items-center gap-0.5 ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {isProfit ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                      {isProfit ? `+${p.gain_percentage.toFixed(1)}%` : `${p.gain_percentage.toFixed(1)}%`}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${isProfit ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                      {p.actual_outcome}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      p.model_accuracy === 'CORRECT' ? 'bg-emerald-500/10 text-emerald-400' :
                      p.model_accuracy === 'WRONG' ? 'bg-rose-500/10 text-rose-400' : 'bg-slate-800 text-slate-400'
                    }`}>
                      {p.model_accuracy}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
