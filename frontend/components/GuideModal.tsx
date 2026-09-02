'use client';

import React from 'react';
import { DemoData, ScenarioAxisPosition } from '@/types/demo';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  data: DemoData;
}

const SCENARIOS: { id: string; label: string; desc: string }[] = [
  { id: 'approved_text', label: 'Approved NZF Text', desc: 'The standard baseline carbon pricing proposal.' },
  { id: 'tuvalu', label: 'Tuvalu Proposal', desc: 'Higher carbon levy favored by island nations.' },
  { id: 'liberia', label: 'Liberia Proposal', desc: 'Flexible surplus credit trading mechanism.' },
  { id: 'brazil', label: 'Brazil Transition', desc: 'Phased-in intensity reduction starting at 3%.' },
  { id: 'adoption_fails', label: 'Adoption Fails Again', desc: 'CII + FuelEU + EU ETS stack only, no NZF.' },
];

// Every price shown here is read live from data.sweep.scenario_ticks --
// never hardcoded -- so this copy can't drift out of sync with the real
// computed numbers the way an earlier version of this file did.
const formatTick = (tick: ScenarioAxisPosition | undefined): string => {
  if (!tick || tick.operating_point_usd_per_tco2e == null) {
    if (tick?.kind === 'qualitative_marker') return 'No posted price — market-design proposal';
    return 'Not yet computed';
  }
  return `~$${Math.round(tick.operating_point_usd_per_tco2e)}/tCO₂e`;
};

export const GuideModal: React.FC<Props> = ({ isOpen, onClose, data }) => {
  if (!isOpen) return null;

  const tickById = new Map(data.sweep.scenario_ticks.map(t => [t.scenario_id, t]));
  const ps = data.exposure.plan_spread;
  const deepSeaCount = data.fleet.vessels.filter(v => v.band !== 'C').length;
  const bench = data.optimizer_benchmark;

  return (
    <div className="overlay-backdrop" onClick={onClose}>
      <div className="overlay-panel w-full max-w-3xl p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-neutral-800 pb-4 mb-5">
          <div>
            <h2 className="text-base font-semibold text-white uppercase tracking-wider font-mono">
              Platform Guide & How to Read This Atlas
            </h2>
            <p className="text-xs text-neutral-400 mt-1 font-sans">
              A plain-English guide to understanding vessel fleet compliance under IMO carbon regulations.
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full border border-neutral-800 flex items-center justify-center text-neutral-400 hover:text-white hover:border-neutral-600 font-mono text-sm transition-all"
          >
            ✕
          </button>
        </div>

        {/* Content sections */}
        <div className="space-y-6 text-sm text-neutral-300 font-sans leading-relaxed">
          {/* Section 1 */}
          <div className="p-4 rounded-lg bg-neutral-950 border border-neutral-800">
            <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider mb-2">
              1. What is this website showing?
            </h3>
            <p className="text-xs text-neutral-400">
              The IMO's Second Extraordinary MEPC Session is set to reconvene on <strong>4 December 2026</strong> to
              decide on a global carbon-pricing framework for merchant ships (subject to confirmation by MEPC 85,
              30 Nov–3 Dec 2026).
              Ship owners must plan 5 years ahead (2026–2030) on what fuel to burn, what speed to run, and which
              trade routes to assign.
              This platform maps out the optimal fleet plan for any carbon tax price between <strong>$0 and $1,000 per ton of CO₂</strong>.
            </p>
          </div>

          {/* Section 2 */}
          <div className="p-4 rounded-lg bg-neutral-950 border border-neutral-800">
            <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider mb-2">
              2. How do I use the Carbon Price Slider?
            </h3>
            <p className="text-xs text-neutral-400 mb-2">
              Drag the white slider bar at the top or click any of the proposal buttons — each price below is
              computed live from the current fleet plan, not a fixed figure:
            </p>
            <ul className="list-disc list-inside text-xs text-neutral-400 space-y-1 font-mono">
              {SCENARIOS.map(sc => (
                <li key={sc.id}>
                  <strong className="text-white">{sc.label} ({formatTick(tickById.get(sc.id))}):</strong> {sc.desc}
                </li>
              ))}
            </ul>
          </div>

          {/* Section 3 */}
          <div className="p-4 rounded-lg bg-neutral-950 border border-neutral-800">
            <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider mb-2">
              3. What does "Strategy Reallocation" mean?
            </h3>
            <p className="text-xs text-neutral-400">
              When the carbon tax goes up, it becomes cheaper to switch a vessel from traditional VLSFO fuel to
              Biofuel (B30) or e-Methanol, or reduce sailing speed.
              Whenever moving the slider changes a ship's optimal decision, a notification will pop up showing
              which ships modified their operational strategy!
            </p>
          </div>

          {/* Section 4 */}
          <div className="p-4 rounded-lg bg-neutral-950 border border-neutral-800">
            <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider mb-2">
              4. Interactive Controls & Overlay Buttons
            </h3>
            <p className="text-xs text-neutral-400 mb-2">
              Click any of the three panel buttons on the right side:
            </p>
            <ul className="list-disc list-inside text-xs text-neutral-400 space-y-1 font-mono">
              <li>
                <strong className="text-white">View Exposure & Risk Atlas:</strong> See the financial risk
                (₹{(ps.spread_inr / 1e7).toFixed(1)} Crore variance) across all regulatory proposals.
              </li>
              <li>
                <strong className="text-white">Open Fleet Decision Matrix:</strong> View the exact 2026–2030
                fuel/route matrix for all {deepSeaCount} deep-sea vessels.
              </li>
              <li>
                <strong className="text-white">Open Sensitivity Curve:</strong> See total fleet cost as a function
                of carbon tax. Cost rises to a peak, retreats as fuel-switching becomes worthwhile, then goes
                <em> flat</em> — NZF's surplus credit for over-complying is capped at the real, fixed Tier 2
                remedial-unit price, so there's a hard ceiling on how much decarbonization can offset the tax.
                Open the curve for the exact numbers.
              </li>
            </ul>
          </div>

          {/* Section 5 -- every number read live from optimizer_benchmark, same
              discipline as formatTick above: no computed figure hardcoded. */}
          {bench.available && (
            <div className="p-4 rounded-lg bg-neutral-950 border border-neutral-800">
              <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider mb-2">
                5. What&apos;s the &quot;quantum-inspired&quot; part?
              </h3>
              <p className="text-xs text-neutral-400 mb-2">
                Finding the cheapest 5-year plan for a whole fleet is a huge search problem — every vessel,
                every year, a choice of route, speed, fuel and shore power. Two solvers were built for it: a
                classical <strong className="text-white">Genetic Algorithm</strong>, which carries a population
                of concrete candidate plans, and a{' '}
                <strong className="text-white">Quantum-Inspired Evolutionary Algorithm</strong>, which instead
                carries a <em>probability distribution</em> over each decision — the borrowed idea from quantum
                computing, run entirely on ordinary hardware.
              </p>
              <p className="text-xs text-neutral-400 mb-2">
                That representation lets each decision start out already knowing what the cost model implies
                about it, before a single full plan is scored. It measurably works: it makes the raw search{' '}
                <strong className="text-emerald-400">
                  {(bench.search_attribution.raw_search_improvement_fraction * 100).toFixed(1)}% cheaper
                </strong>
                .
              </p>
              <p className="text-xs text-neutral-400">
                But both solvers finish with the same classical local-search polish, and that polish is strong
                enough to erase the head start — end to end the difference is{' '}
                <strong className="text-white">
                  {Math.abs(bench.search_attribution.end_to_end_improvement_fraction * 100).toFixed(2)}%
                </strong>
                , i.e. nothing. So the honest claim is <em>not</em> &quot;quantum beats classical here&quot;.
                Open the <strong className="text-white">Solver Benchmark</strong> from the header for the full
                head-to-head and the measured ablation behind both numbers.
              </p>
            </div>
          )}
        </div>

        {/* Footer button */}
        <div className="mt-6 pt-4 border-t border-neutral-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 bg-white text-black font-semibold text-xs rounded hover:bg-neutral-200 transition-all font-mono"
          >
            Got It • Explore Atlas
          </button>
        </div>
      </div>
    </div>
  );
};
