'use client';

import React from 'react';
import { GridPointResult } from '@/types/demo';

interface Props {
  gridPoints: GridPointResult[];
  currentPrice: number;
}

export const CostCurve: React.FC<Props> = ({ gridPoints, currentPrice }) => {
  if (gridPoints.length < 2) return null;

  const costs = gridPoints.map(gp => gp.total_usd);
  const minCost = Math.min(...costs);
  const maxCost = Math.max(...costs);
  const range = maxCost - minCost || 1;

  const W = 700;
  const H = 180;
  const PAD = { t: 16, b: 28, l: 56, r: 16 };
  const plotW = W - PAD.l - PAD.r;
  const plotH = H - PAD.t - PAD.b;

  const points = gridPoints.map((gp, i) => {
    const x = PAD.l + (gp.price_usd_per_tco2e / 1000) * plotW;
    const y = PAD.t + plotH - ((gp.total_usd - minCost) / range) * plotH;
    return { x, y, gp };
  });

  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');

  // Cursor position
  const closest = points.reduce((prev, cur) =>
    Math.abs(cur.gp.price_usd_per_tco2e - currentPrice) < Math.abs(prev.gp.price_usd_per_tco2e - currentPrice) ? cur : prev
  );

  return (
    <div className="glass-panel p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          Total Fleet Cost vs. Carbon Price
          <span className="badge badge-cyan">Sweep</span>
        </h3>
        <span className="text-[10px] font-mono text-slate-500">
          ${(closest.gp.total_usd / 1e6).toFixed(2)}M at ${closest.gp.price_usd_per_tco2e}/tCO₂e
        </span>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 200 }}>
        {/* Grid lines */}
        {[0, 250, 500, 750, 1000].map(v => {
          const x = PAD.l + (v / 1000) * plotW;
          return (
            <g key={v}>
              <line x1={x} y1={PAD.t} x2={x} y2={PAD.t + plotH} stroke="rgba(148,163,184,0.1)" strokeWidth={1} />
              <text x={x} y={H - 4} fill="#64748b" fontSize={8} fontFamily="monospace" textAnchor="middle">${v}</text>
            </g>
          );
        })}

        {/* Y-axis labels */}
        {[0, 0.5, 1].map(frac => {
          const y = PAD.t + plotH - frac * plotH;
          const val = minCost + frac * range;
          return (
            <g key={frac}>
              <line x1={PAD.l} y1={y} x2={PAD.l + plotW} y2={y} stroke="rgba(148,163,184,0.06)" strokeWidth={1} />
              <text x={PAD.l - 4} y={y + 3} fill="#64748b" fontSize={7} fontFamily="monospace" textAnchor="end">
                ${(val / 1e6).toFixed(1)}M
              </text>
            </g>
          );
        })}

        {/* Area fill */}
        <path
          d={`${pathD} L ${points[points.length - 1].x} ${PAD.t + plotH} L ${points[0].x} ${PAD.t + plotH} Z`}
          fill="url(#costGrad)" opacity={0.3}
        />

        {/* Line */}
        <path d={pathD} fill="none" stroke="#38bdf8" strokeWidth={2.5} strokeLinejoin="round" />

        {/* Dots */}
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={3} fill={p === closest ? '#fff' : '#38bdf8'}
            stroke={p === closest ? '#38bdf8' : 'none'} strokeWidth={2} />
        ))}

        {/* Cursor line */}
        <line x1={closest.x} y1={PAD.t} x2={closest.x} y2={PAD.t + plotH}
          stroke="#f43f5e" strokeWidth={1.5} strokeDasharray="4 3" opacity={0.7} />

        <defs>
          <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#38bdf8" stopOpacity="0" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
};
