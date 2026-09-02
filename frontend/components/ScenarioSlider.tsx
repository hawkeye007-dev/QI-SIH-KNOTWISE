'use client';

import React from 'react';
import { ScenarioAxisPosition, SwitchingPoint } from '@/types/demo';

interface Props {
  currentPrice: number;
  onPriceChange: (price: number) => void;
  activeScenarioId: string;
  onScenarioSelect: (id: string) => void;
  ticks: ScenarioAxisPosition[];
  switchingPoints: SwitchingPoint[];
  onNoPriceClick: (label: string, reason: string) => void;
}

// Why Liberia and Brazil show "N/A" -- real, current reasons, not a
// placeholder. Both are honest "not computed," never a silently-assumed
// zero (see sweep.py's scenario_axis_positions). If Brazil's implied-price
// converter is ever built, its entry here should be revisited.
const NO_PRICE_REASONS: Record<string, string> = {
  liberia:
    "Liberia's proposal replaces the fund with transferable surplus units — a market design, not a posted " +
    'per-tonne price, so there is no $/t figure to place on this axis.',
  brazil:
    "Brazil's proposal is a phased reduction-percentage schedule, not a per-tonne price. Converting it to one " +
    "(the same way adoption_fails' implied price is computed) isn't built in this pass.",
};

export const ScenarioSlider: React.FC<Props> = ({
  currentPrice, onPriceChange, activeScenarioId, onScenarioSelect, ticks, switchingPoints, onNoPriceClick,
}) => {
  const tickMap = React.useMemo(() => {
    const m: Record<string, ScenarioAxisPosition> = {};
    ticks.forEach(t => { m[t.scenario_id] = t; });
    return m;
  }, [ticks]);

  // Which proposal card is highlighted must track the actual slider price,
  // not just the last-clicked button -- otherwise dragging away from a
  // clicked proposal leaves its card looking selected at a price nowhere
  // near it. Whichever proposal's own price sits closest to currentPrice
  // wins; a proposal with no computed price (Liberia, Brazil) can't win.
  const closestScenarioId = React.useMemo(() => {
    let closestId: string | null = null;
    let closestDistance = Infinity;
    for (const [id, tick] of Object.entries(tickMap)) {
      const point = tick.operating_point_usd_per_tco2e;
      if (point == null) continue;
      const distance = Math.abs(point - currentPrice);
      if (distance < closestDistance) {
        closestDistance = distance;
        closestId = id;
      }
    }
    return closestId;
  }, [tickMap, currentPrice]);

  const scenarios = [
    { id: 'approved_text', label: 'Approved Text', desc: 'Baseline Proposal' },
    { id: 'liberia',       label: 'Liberia Proposal', desc: 'Surplus Credits' },
    { id: 'tuvalu',        label: 'Tuvalu Levy', desc: '$300/t Carbon Levy' },
    { id: 'brazil',        label: 'Brazil Transition', desc: 'Phase-in 3% ➔ 4%' },
    { id: 'adoption_fails',label: 'FuelEU Baseline', desc: 'EU Equivalent Penalty' },
  ];

  return (
    <div className="bg-neutral-950 border border-neutral-800 rounded-xl p-4 mb-2">
      {/* Top Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
        <div>
          <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-white flex items-center gap-2">
            IMO Carbon Tax Price Slider
            <span className="tag">Interactive Axis</span>
          </h2>
          <p className="text-[11px] text-neutral-400 mt-0.5">
            Click a regulatory proposal button below or drag the slider bar to test carbon tax rates.
          </p>
        </div>
        <div className="flex items-center gap-2 bg-neutral-900 border border-neutral-700 px-4 py-2 rounded-lg shrink-0">
          <span className="text-[10px] font-mono uppercase text-neutral-400">Carbon Price:</span>
          <span className="text-lg font-mono font-bold text-white">${currentPrice}</span>
          <span className="text-[10px] font-mono text-neutral-400">/ ton CO₂</span>
        </div>
      </div>

      {/* Regulatory Proposal Buttons */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 mb-4">
        {scenarios.map(sc => {
          const tick = tickMap[sc.id];
          const price = tick?.operating_point_usd_per_tco2e;
          const active = closestScenarioId === sc.id;
          return (
            <button
              key={sc.id}
              onClick={() => {
                onScenarioSelect(sc.id);
                if (price != null) {
                  onPriceChange(Math.round(price));
                } else {
                  onNoPriceClick(sc.label, NO_PRICE_REASONS[sc.id] ?? 'No price is computed for this proposal.');
                }
              }}
              className={`p-2.5 rounded-lg text-left transition-all border ${
                active
                  ? 'bg-white text-black border-white font-bold shadow-md'
                  : 'bg-neutral-900 text-neutral-300 border-neutral-800 hover:border-neutral-700 hover:bg-neutral-850'
              }`}
            >
              <div className="text-[10px] font-mono uppercase tracking-wider opacity-80 mb-0.5">
                {sc.label}
              </div>
              <div className="text-[11px] truncate mb-1 text-neutral-400">{sc.desc}</div>
              <div className="text-xs font-mono font-bold">
                {price != null ? `$${Math.round(price)}/tCO₂` : 'N/A'}
              </div>
            </button>
          );
        })}
      </div>

      {/* Continuous Axis Slider Track */}
      <div className="relative px-1 pt-2 pb-1">
        <input
          type="range" min={0} max={1000} step={25}
          value={currentPrice}
          onChange={e => onPriceChange(Number(e.target.value))}
        />

        {/* Axis tick markers */}
        <div className="flex justify-between text-[10px] font-mono text-neutral-400 mt-1 font-medium">
          <span>$0/t</span>
          <span>$250/t</span>
          <span>$500/t</span>
          <span>$750/t</span>
          <span>$1000/tCO₂</span>
        </div>
      </div>
    </div>
  );
};
