'use client';

import React from 'react';
import { GridPointResult } from '@/types/demo';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  gridPoints: GridPointResult[];
  currentPrice: number;
  tier2PriceUsdPerTco2e: number | null;
}

export const CostCurveModal: React.FC<Props> = ({ isOpen, onClose, gridPoints, currentPrice, tier2PriceUsdPerTco2e }) => {
  if (!isOpen || gridPoints.length < 2) return null;

  const costs = gridPoints.map(gp => gp.total_usd);
  const minCost = Math.min(...costs);
  const maxCost = Math.max(...costs);
  const range = maxCost - minCost || 1;

  const W = 800;
  const H = 320;
  const PAD = { t: 20, b: 40, l: 70, r: 20 };
  const plotW = W - PAD.l - PAD.r;
  const plotH = H - PAD.t - PAD.b;

  const points = gridPoints.map((gp) => {
    const x = PAD.l + (gp.price_usd_per_tco2e / 1000) * plotW;
    const y = PAD.t + plotH - ((gp.total_usd - minCost) / range) * plotH;
    return { x, y, gp };
  });

  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');

  const closest = points.reduce((prev, cur) =>
    Math.abs(cur.gp.price_usd_per_tco2e - currentPrice) < Math.abs(prev.gp.price_usd_per_tco2e - currentPrice) ? cur : prev
  );

  // Real, computed finding (not asserted, and not assumed to be a simple
  // straight line or an uncapped runaway): find where the curve actually
  // peaks, whether it flattens into a plateau at the end, and how the
  // final value compares to the $0/t baseline -- described from whatever
  // the swept data shows this rebuild, never a fixed shape.
  const firstPoint = gridPoints[0];
  const lastPoint = gridPoints[gridPoints.length - 1];
  const peakPoint = gridPoints.reduce((a, b) => (b.total_usd > a.total_usd ? b : a), gridPoints[0]);
  const risesFirst = peakPoint.price_usd_per_tco2e > firstPoint.price_usd_per_tco2e;
  const fallFromPeakUsd = peakPoint.total_usd - lastPoint.total_usd;
  const endsAboveBaselineUsd = lastPoint.total_usd - firstPoint.total_usd;

  // Walk back from the last point to find where the curve settles into a
  // flat plateau (NZF's surplus credit is capped at the real Tier 2 price,
  // so past that point further price increases change nothing -- see
  // sweep.py's _nzf_price_override). Requires at least 3 consecutive grid
  // steps of an exact match to count as a real plateau, not incidental.
  let plateauStartIndex = gridPoints.length - 1;
  for (let i = gridPoints.length - 2; i >= 0; i--) {
    if (Math.abs(gridPoints[i].total_usd - lastPoint.total_usd) <= 1) {
      plateauStartIndex = i;
    } else {
      break;
    }
  }
  const hasPlateau = gridPoints.length - 1 - plateauStartIndex >= 3;
  const plateauStartPrice = hasPlateau ? gridPoints[plateauStartIndex].price_usd_per_tco2e : null;

  return (
    <div className="overlay-backdrop" onClick={onClose}>
      <div className="overlay-panel w-full max-w-5xl p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-neutral-800 pb-4 mb-5">
          <div>
            <h2 className="text-base font-semibold text-white uppercase tracking-wider font-mono">
              Carbon Price Sensitivity & Fleet Cost Trajectory
            </h2>
            <p className="text-xs text-neutral-400 mt-1 font-sans">
              Total Fleet Compliance & Expenditure Curve across $0–$1000/tCO₂e.
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full border border-neutral-800 flex items-center justify-center text-neutral-400 hover:text-white hover:border-neutral-600 font-mono text-sm transition-all"
          >
            ✕
          </button>
        </div>

        {/* Headline finding, computed live from the actual swept data --
            describes the curve's real shape (a rise to a peak, a partial
            retreat, and — since NZF's surplus credit is capped at the real
            Tier 2 price — a hard plateau), never a blanket "always rises"
            or "always falls" claim. */}
        {fallFromPeakUsd > 0 && (
          <div className="mb-4 p-3 rounded-lg border border-emerald-900 bg-emerald-950/30">
            <span className="text-xs font-mono text-emerald-300">
              {risesFirst && (
                <>Cost rises to a peak of ${(peakPoint.total_usd / 1e6).toFixed(1)}M around ${peakPoint.price_usd_per_tco2e}/t, then </>
              )}
              retreats ${(fallFromPeakUsd / 1e6).toFixed(1)}M
              {hasPlateau && <> and goes flat above ${plateauStartPrice}/t</>} —{' '}
              {endsAboveBaselineUsd > 0
                ? <>but never drops below the ${(firstPoint.total_usd / 1e6).toFixed(1)}M baseline at $0/t.</>
                : <>settling ${(Math.abs(endsAboveBaselineUsd) / 1e6).toFixed(1)}M below the $0/t baseline.</>}
              {hasPlateau && tier2PriceUsdPerTco2e != null && (
                <> NZF's surplus credit is capped at the real Tier 2 remedial-unit price (${tier2PriceUsdPerTco2e}/tCO₂e)
                — over-compliance stops paying beyond that, so there's a hard ceiling on how much decarbonization
                can offset the tax.</>
              )}
            </span>
          </div>
        )}

        {/* SVG Chart */}
        <div className="bg-neutral-950 p-4 rounded-lg border border-neutral-800 mb-4">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
            {/* Grid lines */}
            {[0, 200, 400, 600, 800, 1000].map(v => {
              const x = PAD.l + (v / 1000) * plotW;
              return (
                <g key={v}>
                  <line x1={x} y1={PAD.t} x2={x} y2={PAD.t + plotH} stroke="#1a1a1a" strokeWidth={1} />
                  <text x={x} y={H - 12} fill="#555" fontSize={9} fontFamily="monospace" textAnchor="middle">${v}</text>
                </g>
              );
            })}

            {/* Y-axis ticks */}
            {[0, 0.25, 0.5, 0.75, 1].map(frac => {
              const y = PAD.t + plotH - frac * plotH;
              const val = minCost + frac * range;
              return (
                <g key={frac}>
                  <line x1={PAD.l} y1={y} x2={PAD.l + plotW} y2={y} stroke="#1a1a1a" strokeWidth={1} />
                  <text x={PAD.l - 8} y={y + 3} fill="#555" fontSize={9} fontFamily="monospace" textAnchor="end">
                    ${(val / 1e6).toFixed(1)}M
                  </text>
                </g>
              );
            })}

            {/* Trajectory Line */}
            <path d={pathD} fill="none" stroke="#ffffff" strokeWidth={2} strokeLinejoin="round" />

            {/* Points */}
            {points.map((p, i) => (
              <circle
                key={i}
                cx={p.x}
                cy={p.y}
                r={p === closest ? 5 : 2.5}
                fill={p === closest ? '#ffffff' : '#444444'}
                stroke={p === closest ? '#000000' : 'none'}
                strokeWidth={1.5}
              />
            ))}

            {/* Selected Price Cursor */}
            <line x1={closest.x} y1={PAD.t} x2={closest.x} y2={PAD.t + plotH} stroke="#888888" strokeWidth={1} strokeDasharray="3 3" />
          </svg>
        </div>

        {/* Selected Point Status Bar */}
        <div className="p-3 bg-neutral-950 rounded border border-neutral-900 flex items-center justify-between text-xs font-mono">
          <span className="text-neutral-400">Selected Carbon Price: <strong className="text-white">${closest.gp.price_usd_per_tco2e}/tCO₂e</strong></span>
          <span className="text-neutral-400">Total Fleet Cost: <strong className="text-white">${(closest.gp.total_usd / 1e6).toFixed(2)}M USD</strong></span>
        </div>
      </div>
    </div>
  );
};
