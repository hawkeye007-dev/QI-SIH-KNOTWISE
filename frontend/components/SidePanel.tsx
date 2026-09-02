'use client';

import React from 'react';
import { ExposureData, SwitchingPoint } from '@/types/demo';

interface Props {
  exposure: ExposureData;
  currentPrice: number;
  switchingPoints: SwitchingPoint[];
}

export const SidePanel: React.FC<Props> = ({ exposure, currentPrice, switchingPoints }) => {
  const ps = exposure.plan_spread;
  const capex = exposure.capex_exposure;
  const summary = exposure.summary;
  const fx = exposure.fx;

  const activeFlips = React.useMemo(() => {
    return switchingPoints.filter(
      sp => currentPrice >= sp.price_low_usd_per_tco2e && currentPrice <= sp.price_high_usd_per_tco2e
    );
  }, [switchingPoints, currentPrice]);

  return (
    <div className="space-y-4">
      {/* Plan Spread – Hero Card */}
      <div className="glass-panel p-5 relative overflow-hidden border-sky-500/20">
        <div className="absolute -top-4 -right-4 text-[80px] font-black text-sky-400/[0.06] select-none leading-none">₹</div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
            Cost of Regulatory Uncertainty
          </span>
          <span className="badge badge-cyan">§3.1</span>
        </div>
        <div className="text-3xl font-black text-white mb-0.5 tracking-tight">
          ₹{(ps.spread_inr / 1e7).toFixed(1)} <span className="text-lg text-slate-400 font-normal">Crore</span>
        </div>
        <div className="text-xs font-mono text-sky-400/80 mb-3">
          ${(ps.spread_usd / 1e6).toFixed(2)}M USD
        </div>
        <div className="text-[10px] text-slate-500 leading-relaxed">
          Max <span className="text-amber-400 font-semibold">{ps.max_scenario_id}</span> vs
          min <span className="text-emerald-400 font-semibold">{ps.min_scenario_id}</span> —
          single non-overlapping figure (not a sum).
        </div>
      </div>

      {/* Exposure Tiers */}
      <div className="glass-panel p-5 space-y-3">
        <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-800/80 pb-2">
          Exposure Tiers
        </h4>

        {/* Unanimous */}
        <div className="bg-slate-900/50 p-3 rounded-xl border border-slate-800/60">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">Unanimous (3 Seeds)</span>
            <span className="badge badge-emerald">Strict</span>
          </div>
          <div className="text-xl font-bold text-white">{summary.stable_exposed_decision_count}</div>
          <div className="text-[10px] text-slate-400">
            exposed decision{summary.stable_exposed_decision_count !== 1 ? 's' : ''} ·
            Capex ₹{(summary.capex_exposure_inr / 1e7).toFixed(2)} Cr
          </div>
        </div>

        {/* Majority */}
        <div className="bg-slate-900/50 p-3 rounded-xl border border-slate-800/60">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-bold text-purple-400 uppercase tracking-wider">Majority Confidence</span>
            <span className="badge badge-purple">Drill-Down</span>
          </div>
          <div className="text-xl font-bold text-white">{summary.majority_band_decision_count}</div>
          <div className="text-[10px] text-slate-400">additional decisions</div>
        </div>

        {/* Unstable */}
        <div className="bg-slate-900/50 p-3 rounded-xl border border-amber-500/20">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider">Unstable (Excluded)</span>
            <span className="badge badge-amber">⚠️</span>
          </div>
          <div className="text-xl font-bold text-white">{summary.unstable_decision_count}</div>
          <div className="text-[10px] text-slate-400">decisions where GA seeds disagree</div>
        </div>
      </div>

      {/* Live Switching Readout */}
      <div className="glass-panel p-5 space-y-2">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
            Flips at ${currentPrice}/tCO₂e
          </span>
          <span className={`badge ${activeFlips.length > 0 ? 'badge-rose' : 'badge-slate'}`}>
            {activeFlips.length}
          </span>
        </div>

        {activeFlips.length === 0 ? (
          <p className="text-[11px] text-slate-500 italic py-1">
            Fleet plan is flat at this price — no vessel-year decision changes.
          </p>
        ) : (
          <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
            {activeFlips.slice(0, 15).map((f, i) => (
              <div key={i} className="bg-slate-900/70 p-2 rounded-lg border border-slate-800/60 text-[11px]">
                <div className="flex justify-between font-mono font-bold mb-0.5">
                  <span className="text-sky-400">{f.vessel_id} · {f.year}</span>
                  <span className="text-rose-400">{f.decision}</span>
                </div>
                <div className="text-slate-300 flex items-center gap-1.5">
                  <span className="line-through text-slate-500">{String(f.from_value)}</span>
                  <span className="text-slate-600">→</span>
                  <span className="text-emerald-400 font-semibold">{String(f.to_value)}</span>
                </div>
              </div>
            ))}
            {activeFlips.length > 15 && (
              <p className="text-[10px] text-slate-500 text-center">+{activeFlips.length - 15} more</p>
            )}
          </div>
        )}
      </div>

      {/* FX Footer */}
      <div className="text-[10px] text-slate-500 font-mono flex items-center justify-between px-1">
        <span>FX: $1 = ₹{fx.usd_to_inr_rate}</span>
        <span className="badge badge-slate">{fx.status}</span>
      </div>
    </div>
  );
};
