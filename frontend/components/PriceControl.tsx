'use client';

import React from 'react';
import { ScenarioAxisPosition } from '@/types/demo';
import { useAtlas } from '@/lib/AtlasContext';

// Why Liberia and Brazil show "N/A" -- real, current reasons, not a
// placeholder. Both are honest "not computed," never a silently-assumed
// zero (see sweep.py's scenario_axis_positions).
const NO_PRICE_REASONS: Record<string, string> = {
  liberia:
    "Liberia's proposal replaces the fund with transferable surplus units — a market design, not a posted " +
    'per-tonne price, so there is no $/t figure to place on this axis.',
  brazil:
    "Brazil's proposal is a phased reduction-percentage schedule, not a per-tonne price. Converting it to one " +
    "(the same way adoption_fails' implied price is computed) isn't built in this pass.",
};

const SCENARIOS = [
  { id: 'approved_text', label: 'Approved Text', desc: 'Baseline Proposal' },
  { id: 'liberia', label: 'Liberia Proposal', desc: 'Surplus Credits' },
  { id: 'tuvalu', label: 'Tuvalu Levy', desc: '$300/t Carbon Levy' },
  { id: 'brazil', label: 'Brazil Transition', desc: 'Phase-in 3% → 4%' },
  { id: 'adoption_fails', label: 'FuelEU Baseline', desc: 'EU Equivalent Penalty' },
];

/** The carbon-price slider, shared across every page whose content depends
 *  on it (Home, Fleet Matrix, Cost Curve). Reads/writes state from
 *  AtlasContext so the price picked here is the price every other page
 *  sees, without prop-drilling. */
export const PriceControl: React.FC = () => {
  const { data, price, setPrice, scenarioId, setScenarioId, showNotification } = useAtlas();
  const ticks: ScenarioAxisPosition[] = data?.sweep.scenario_ticks ?? [];

  const tickMap = React.useMemo(() => {
    const m: Record<string, ScenarioAxisPosition> = {};
    ticks.forEach(t => { m[t.scenario_id] = t; });
    return m;
  }, [ticks]);

  const closestScenarioId = React.useMemo(() => {
    let closestId: string | null = null;
    let closestDistance = Infinity;
    for (const [id, tick] of Object.entries(tickMap)) {
      const point = tick.operating_point_usd_per_tco2e;
      if (point == null) continue;
      const distance = Math.abs(point - price);
      if (distance < closestDistance) {
        closestDistance = distance;
        closestId = id;
      }
    }
    return closestId;
  }, [tickMap, price]);

  return (
    <div className="metric-card mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
            IMO Carbon Tax Price Slider
            <span className="tag">Interactive Axis</span>
          </h2>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Click a regulatory proposal button below or drag the slider to test carbon tax rates.
          </p>
        </div>
        <div className="flex items-center gap-2 bg-[var(--surface-sunken)] border border-[var(--border)] px-4 py-2 rounded-lg shrink-0">
          <span className="text-xs font-mono uppercase text-[var(--text-secondary)]">Carbon Price:</span>
          <span className="text-xl font-mono font-bold text-[var(--text-primary)]">${price}</span>
          <span className="text-xs font-mono text-[var(--text-secondary)]">/ ton CO₂</span>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 mb-5">
        {SCENARIOS.map(sc => {
          const tick = tickMap[sc.id];
          const tickPrice = tick?.operating_point_usd_per_tco2e;
          const active = closestScenarioId === sc.id;
          return (
            <button
              key={sc.id}
              onClick={() => {
                setScenarioId(sc.id);
                if (tickPrice != null) {
                  setPrice(Math.round(tickPrice));
                } else {
                  showNotification(`${sc.label} has no price on this axis: ${NO_PRICE_REASONS[sc.id] ?? 'No price is computed for this proposal.'}`, 6000);
                }
              }}
              className={`p-3 rounded-lg text-left transition-colors border focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:outline-none ${
                active
                  ? 'bg-[var(--action-bg)] text-[var(--action-text)] border-[var(--action-bg)] shadow-md'
                  : 'bg-[var(--surface-elevated)] text-[var(--text-secondary)] border-[var(--border)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-hover)]'
              }`}
            >
              <div className={`text-[11px] uppercase tracking-wider mb-0.5 ${active ? 'opacity-60' : 'text-[var(--text-tertiary)]'}`}>
                {sc.label}
              </div>
              <div className={`text-xs truncate mb-1 ${active ? 'opacity-60' : 'text-[var(--text-tertiary)]'}`}>{sc.desc}</div>
              <div className="text-sm font-mono font-bold">
                {tickPrice != null ? `$${Math.round(tickPrice)}/tCO₂` : 'N/A'}
              </div>
            </button>
          );
        })}
      </div>

      <div className="relative px-1 pt-2 pb-1">
        <input
          type="range" min={0} max={1000} step={25}
          value={price}
          onChange={e => setPrice(Number(e.target.value))}
          aria-label="Carbon tax price in USD per ton of CO2 equivalent"
        />
        <div className="flex justify-between text-xs font-mono text-[var(--text-secondary)] mt-1 font-medium">
          <span>$0/t</span>
          <span>$250/t</span>
          <span>$500/t</span>
          <span>$750/t</span>
          <span>$1000/tCO₂</span>
        </div>
      </div>

      <p className="text-xs text-[var(--text-tertiary)] mt-2">
        Scenario: <span className="font-medium text-[var(--text-secondary)]">{scenarioId}</span>
      </p>
    </div>
  );
};
