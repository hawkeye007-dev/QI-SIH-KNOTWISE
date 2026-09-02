'use client';

import React from 'react';
import { ExposureData } from '@/types/demo';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  exposure: ExposureData;
}

export const ExposureModal: React.FC<Props> = ({ isOpen, onClose, exposure }) => {
  if (!isOpen) return null;

  const ps = exposure.plan_spread;
  const capex = exposure.capex_exposure;
  // Falls back safely if an older/stale demo_data.json (predating the
  // majority_capex_exposure backend field) is being served -- e.g. while a
  // rebuild is still in flight -- rather than crashing the whole modal.
  const majorityCapex = exposure.majority_capex_exposure ?? { total_usd: 0, total_inr: 0, decisions: [], description: '' };
  const summary = exposure.summary;
  const fx = exposure.fx;
  // shore-power is the only capex-typed decision this prototype's genome
  // models (no retrofit variable yet) -- on a given run it can genuinely
  // land at ₹0 in both confidence tiers if no shore-power election happens
  // to be exposed. Rather than headline a scary ₹0.00 Cr, fall back to the
  // always-real plan_spread figure and say plainly why.
  const hasCapexSignal = majorityCapex.total_inr > 0 || capex.total_inr > 0;

  return (
    <div className="overlay-backdrop" onClick={onClose}>
      <div className="overlay-panel w-full max-w-4xl p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-neutral-800 pb-4 mb-5">
          <div>
            <h2 className="text-base font-semibold text-white uppercase tracking-wider font-mono">
              Regulatory Exposure & Capital Risk Breakdown
            </h2>
            <p className="text-xs text-neutral-400 mt-1 font-sans">
              Financial Variance & Unanimous vs. Majority Decision Confidence Analysis.
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full border border-neutral-800 flex items-center justify-center text-neutral-400 hover:text-white hover:border-neutral-600 font-mono text-sm transition-all"
          >
            ✕
          </button>
        </div>

        {/* Hero Financial Summary — one card when there's only one real
            number to show (never two boxes echoing the same figure under
            different labels), two when capex exposure is genuinely its
            own, distinct figure. */}
        <div className={`grid grid-cols-1 ${hasCapexSignal ? 'md:grid-cols-2' : ''} gap-4 mb-6`}>
          <div className="p-4 rounded-lg bg-neutral-950 border border-neutral-800">
            <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 mb-1">
              Regulatory Uncertainty Spread
            </div>
            <div className="text-2xl font-bold font-mono text-white mb-1">
              ₹{(ps.spread_inr / 1e7).toFixed(2)} Crore
            </div>
            <div className="text-xs font-mono text-neutral-400">
              ${(ps.spread_usd / 1e6).toFixed(2)}M USD Plan Cost Variance
            </div>
            <p className="text-[11px] text-neutral-500 mt-2 leading-relaxed font-sans">
              {hasCapexSignal
                ? `Non-overlapping financial spread across scenario limits (${ps.max_scenario_id} vs ${ps.min_scenario_id}).`
                : 'Plan-cost spread across regulatory scenarios; see the Fleet Decision Matrix for which decisions drive it.'}
            </p>
          </div>

          {hasCapexSignal && (
            <div className="p-4 rounded-lg bg-neutral-950 border border-neutral-800">
              <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 mb-1">
                Capital at Risk (Capex Exposure)
              </div>
              <div className="text-2xl font-bold font-mono text-white mb-1">
                ₹{(majorityCapex.total_inr / 1e7).toFixed(2)} Crore
              </div>
              <div className="text-xs font-mono text-neutral-400">
                ${(majorityCapex.total_usd / 1e6).toFixed(2)}M USD Capital Reallocation
              </div>
              <p className="text-[11px] text-neutral-500 mt-2 leading-relaxed font-sans">
                Majority-confidence capital commitment estimate (2-of-3+ seeds agree). The strict
                unanimous filter is ₹0 by definition — see the table below for why.
              </p>
            </div>
          )}
        </div>

        {/* Exposure Tiers Table */}
        <div className="border border-neutral-800 rounded-lg overflow-hidden mb-6">
          <table className="decision-table">
            <thead>
              <tr className="bg-neutral-950">
                <th>Confidence Tier</th>
                <th className="text-center">Decision Count</th>
                <th className="text-right">Financial Exposure</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <div className="font-semibold text-neutral-400">Unanimous Confidence Filter</div>
                  <div className="text-[11px] text-neutral-500">
                    Strict agreement across all stability seeds — ₹0 by construction: a decision that's
                    unanimous across every regulatory scenario has, by definition, no exposure to the vote.
                  </div>
                </td>
                <td className="text-center font-mono text-neutral-400">{summary.stable_exposed_decision_count}</td>
                <td className="text-right font-mono text-neutral-500">₹{(summary.capex_exposure_inr / 1e7).toFixed(2)} Cr</td>
              </tr>
              <tr>
                <td>
                  <div className="font-semibold text-white">Majority Confidence Band</div>
                  <div className="text-[11px] text-neutral-500">
                    High-probability drill-down elections
                    {hasCapexSignal ? ' — the headline figure above' : ' — ₹0 capex-typed this run; see the Regulatory Uncertainty Spread above instead'}
                  </div>
                </td>
                <td className="text-center font-mono font-bold text-white">{summary.majority_band_decision_count}</td>
                <td className="text-right font-mono text-white">
                  ₹{(majorityCapex.total_inr / 1e7).toFixed(2)} Cr
                </td>
              </tr>
              <tr>
                <td>
                  <div className="font-semibold text-neutral-400">High-Variance Decisions</div>
                  <div className="text-[11px] text-neutral-500">Excluded near-tied optimization regions</div>
                </td>
                <td className="text-center font-mono text-neutral-400">{summary.unstable_decision_count}</td>
                <td className="text-right font-mono text-neutral-500">Excluded</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* FX Metadata */}
        <div className="p-3 bg-neutral-950 rounded border border-neutral-900 text-xs font-mono text-neutral-500 flex items-center justify-between">
          <span>USD to INR Exchange Benchmark: ₹{fx.usd_to_inr_rate}</span>
          <span>Status: Verified Regulatory Benchmark ({fx.retrieval_date})</span>
        </div>
      </div>
    </div>
  );
};
