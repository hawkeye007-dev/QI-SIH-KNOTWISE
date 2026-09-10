'use client';

/** Chart primitives, drawn as inline SVG against the theme's own tokens.
 *
 *  Shared rules these all keep, so every chart on the site reads as one
 *  system: one y-scale per plot (never a second axis), solid hairline grid,
 *  thin marks with a 2px surface gap between adjacent fills, a legend
 *  whenever there is more than one series, and a hover layer. Series colours
 *  come from `--series-N`, assigned to an entity once and never reassigned by
 *  rank.
 */

import React, { useId, useState } from 'react';

export const SERIES_TOKENS = [
  'var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)',
  'var(--series-5)', 'var(--series-6)', 'var(--series-7)', 'var(--series-8)',
] as const;

export const seriesColor = (index: number) => SERIES_TOKENS[index % SERIES_TOKENS.length];

/* ------------------------------------------------------------------ */
/* Shared chrome                                                       */
/* ------------------------------------------------------------------ */

export const Legend: React.FC<{ items: { label: string; color: string }[]; note?: string }> = ({ items, note }) => (
  <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-[var(--text-secondary)]">
    {items.map(item => (
      <span key={item.label} className="inline-flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-2.5 rounded-[2px]" style={{ background: item.color }} />
        {item.label}
      </span>
    ))}
    {note && <span className="text-[var(--text-tertiary)]">{note}</span>}
  </div>
);

const Tooltip: React.FC<{ x: number; y: number; children: React.ReactNode }> = ({ x, y, children }) => (
  <div
    className="pointer-events-none absolute z-10 min-w-[9rem] -translate-x-1/2 rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2 text-xs shadow-lg"
    style={{ left: `${x}%`, top: `${y}%` }}
  >
    {children}
  </div>
);

/** Wraps a plot so the tooltip can be positioned in percentages over it. */
const PlotFrame: React.FC<{ children: React.ReactNode; minWidth?: number }> = ({ children, minWidth }) => (
  <div className="relative w-full overflow-x-auto">
    <div className="relative" style={minWidth ? { minWidth } : undefined}>{children}</div>
  </div>
);

/* ------------------------------------------------------------------ */
/* Stacked area — composition over a continuous axis                   */
/* ------------------------------------------------------------------ */

export interface StackedAreaSeries {
  key: string;
  label: string;
  color: string;
  values: number[];
}

/** Composition across an ordered x-axis. Segments are separated by a 2px
 *  surface-coloured gap rather than a stroke, so the boundary reads without
 *  a border around every band. */
export const StackedAreaChart: React.FC<{
  x: number[];
  series: StackedAreaSeries[];
  xLabel: string;
  yLabel: string;
  formatX: (value: number) => string;
  formatValue: (value: number, seriesLabel: string) => string;
  height?: number;
}> = ({ x, series, xLabel, yLabel, formatX, formatValue, height = 260 }) => {
  const [hover, setHover] = useState<number | null>(null);
  const W = 720;
  const H = height;
  const PAD = { top: 14, right: 16, bottom: 40, left: 46 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  const totals = x.map((_, i) => series.reduce((sum, s) => sum + s.values[i], 0));
  const yMax = Math.max(...totals, 1);
  const xMin = x[0];
  const xMax = x[x.length - 1];
  const xFor = (value: number) => PAD.left + ((value - xMin) / (xMax - xMin || 1)) * plotW;
  const yFor = (value: number) => PAD.top + plotH - (value / yMax) * plotH;

  // Running baseline so each band sits on the one below it.
  const baselines = x.map(() => 0);
  const bands = series.map(s => {
    const lower = [...baselines];
    s.values.forEach((value, i) => { baselines[i] += value; });
    const upper = [...baselines];
    const top = x.map((xv, i) => `${i === 0 ? 'M' : 'L'} ${xFor(xv)} ${yFor(upper[i])}`).join(' ');
    const bottom = [...x].reverse().map((xv, i) => {
      const index = x.length - 1 - i;
      return `L ${xFor(xv)} ${yFor(lower[index])}`;
    }).join(' ');
    return { series: s, d: `${top} ${bottom} Z` };
  });

  const ticks = [0, 0.25, 0.5, 0.75, 1].map(f => Math.round(f * yMax));
  const hoverIndex = hover;

  return (
    <PlotFrame minWidth={560}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label={`${yLabel} by ${xLabel}`}
        onMouseLeave={() => setHover(null)}
        onMouseMove={event => {
          const rect = event.currentTarget.getBoundingClientRect();
          const ratio = (event.clientX - rect.left) / rect.width;
          const svgX = ratio * W;
          const value = xMin + ((svgX - PAD.left) / plotW) * (xMax - xMin);
          let nearest = 0;
          x.forEach((xv, i) => { if (Math.abs(xv - value) < Math.abs(x[nearest] - value)) nearest = i; });
          setHover(nearest);
        }}
      >
        {ticks.map(tick => (
          <g key={tick}>
            <line x1={PAD.left} x2={W - PAD.right} y1={yFor(tick)} y2={yFor(tick)} stroke="var(--chart-grid)" strokeWidth={1} />
            <text x={PAD.left - 8} y={yFor(tick) + 4} textAnchor="end" fontSize={11} fill="var(--chart-axis-text)">{tick}</text>
          </g>
        ))}
        {bands.map(band => (
          <path
            key={band.series.key}
            d={band.d}
            fill={band.series.color}
            stroke="var(--surface-elevated)"
            strokeWidth={2}
            strokeLinejoin="round"
            opacity={0.92}
          />
        ))}
        {[xMin, (xMin + xMax) / 2, xMax].map(value => (
          <text key={value} x={xFor(value)} y={H - 14} textAnchor="middle" fontSize={11} fill="var(--chart-axis-text)">
            {formatX(value)}
          </text>
        ))}
        <text x={PAD.left + plotW / 2} y={H - 1} textAnchor="middle" fontSize={11} fill="var(--chart-axis-text)">{xLabel}</text>
        {hoverIndex != null && (
          <line
            x1={xFor(x[hoverIndex])} x2={xFor(x[hoverIndex])} y1={PAD.top} y2={PAD.top + plotH}
            stroke="var(--chart-crosshair)" strokeWidth={1}
          />
        )}
      </svg>
      {hoverIndex != null && (
        <Tooltip x={((xFor(x[hoverIndex]) / W) * 100)} y={4}>
          <div className="mb-1 font-mono font-semibold text-[var(--text-primary)]">{formatX(x[hoverIndex])}</div>
          {[...series].reverse().filter(s => s.values[hoverIndex] > 0).map(s => (
            <div key={s.key} className="flex items-center justify-between gap-3">
              <span className="inline-flex items-center gap-1.5 text-[var(--text-secondary)]">
                <span className="inline-block h-2 w-2 rounded-[2px]" style={{ background: s.color }} />
                {s.label}
              </span>
              <span className="font-mono text-[var(--text-primary)]">{formatValue(s.values[hoverIndex], s.label)}</span>
            </div>
          ))}
        </Tooltip>
      )}
    </PlotFrame>
  );
};

/* ------------------------------------------------------------------ */
/* Horizontal gain bars — one measure across ordered categories        */
/* ------------------------------------------------------------------ */

export interface GainBarRow {
  label: string;
  sublabel?: string;
  value: number;
  caption?: string;
}

/** One measure across ordered categories, drawn from a zero baseline with
 *  4px rounded data-ends. Single series, so no legend: the title names it. */
export const GainBarChart: React.FC<{
  rows: GainBarRow[];
  formatValue: (value: number) => string;
  color?: string;
  ariaLabel: string;
}> = ({ rows, formatValue, color = 'var(--series-1)', ariaLabel }) => {
  const max = Math.max(...rows.map(row => Math.abs(row.value)), 1e-9);
  return (
    <div className="space-y-3" role="img" aria-label={ariaLabel}>
      {rows.map(row => (
        <div key={row.label} className="grid grid-cols-[7.5rem_1fr_5rem] items-center gap-3">
          <div className="text-xs">
            <div className="font-mono font-semibold text-[var(--text-primary)]">{row.label}</div>
            {row.sublabel && <div className="text-[var(--text-tertiary)]">{row.sublabel}</div>}
          </div>
          <div className="relative h-5 rounded bg-[var(--surface-sunken)]">
            <div
              className="absolute inset-y-0 left-0 rounded"
              style={{ width: `${(Math.abs(row.value) / max) * 100}%`, background: color }}
            />
          </div>
          <div className="text-right font-mono text-sm font-semibold text-[var(--text-primary)]">{formatValue(row.value)}</div>
          {row.caption && <div className="col-span-3 -mt-2 pl-[8.25rem] text-xs text-[var(--text-tertiary)]">{row.caption}</div>}
        </div>
      ))}
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* Dot plot — several series compared across categories                */
/* ------------------------------------------------------------------ */

export interface DotPlotSeries {
  key: string;
  label: string;
  color: string;
  values: number[];
}

/** Several series on one shared measure axis, one row per category. Chosen
 *  over grouped bars because the story is *spread between models*, which
 *  reads directly as horizontal distance here. Markers are 9px with a 2px
 *  surface ring so overlaps stay separable. */
export const DotPlot: React.FC<{
  categories: string[];
  series: DotPlotSeries[];
  xLabel: string;
  formatValue: (value: number) => string;
}> = ({ categories, series, xLabel, formatValue }) => {
  const [hover, setHover] = useState<{ row: number; series: number } | null>(null);
  const all = series.flatMap(s => s.values);
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  const pad = (hi - lo) * 0.12 || 1;
  const min = Math.max(0, lo - pad);
  const max = hi + pad;
  // Inset the usable track: a marker is centred on its position, so mapping
  // straight to 0-100% pushes half of the extreme markers outside the row.
  const INSET = 3;
  const position = (value: number) => INSET + ((value - min) / (max - min)) * (100 - INSET * 2);
  const ticks = [min, (min + max) / 2, max];

  // Two models can land on nearly the same error for the same vessel. Stacked
  // on one baseline their surface rings cut each other into crescents, so each
  // series gets a fixed vertical lane within the row. Only x carries meaning;
  // the lane is purely so coincident markers stay countable.
  const laneCount = Math.max(series.length, 1);
  const dodgeTop = (seriesIndex: number) =>
    laneCount === 1 ? 50 : 26 + (seriesIndex / (laneCount - 1)) * 48;

  return (
    <div>
      <div className="space-y-1">
        {categories.map((category, rowIndex) => (
          <div key={category} className="grid grid-cols-[3.5rem_1fr] items-center gap-3">
            <span className="font-mono text-xs font-semibold text-[var(--text-primary)]">{category}</span>
            <div className="relative h-9">
              <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-[var(--chart-grid)]" />
              {series.map((s, seriesIndex) => (
                <button
                  key={s.key}
                  type="button"
                  aria-label={`${category} ${s.label} ${formatValue(s.values[rowIndex])}`}
                  onMouseEnter={() => setHover({ row: rowIndex, series: seriesIndex })}
                  onMouseLeave={() => setHover(null)}
                  onFocus={() => setHover({ row: rowIndex, series: seriesIndex })}
                  onBlur={() => setHover(null)}
                  className="absolute h-[14px] w-[14px] -translate-x-1/2 -translate-y-1/2 rounded-full focus-visible:outline-none"
                  style={{ left: `${position(s.values[rowIndex])}%`, top: `${dodgeTop(seriesIndex)}%` }}
                >
                  <span
                    className="absolute left-1/2 top-1/2 block h-[9px] w-[9px] -translate-x-1/2 -translate-y-1/2 rounded-full"
                    style={{ background: s.color, boxShadow: '0 0 0 1.5px var(--surface-elevated)' }}
                  />
                </button>
              ))}
              {hover?.row === rowIndex && (
                <Tooltip x={position(series[hover.series].values[rowIndex])} y={-140}>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[var(--text-secondary)]">{series[hover.series].label}</span>
                    <span className="font-mono font-semibold text-[var(--text-primary)]">
                      {formatValue(series[hover.series].values[rowIndex])}
                    </span>
                  </div>
                </Tooltip>
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-1 grid grid-cols-[3.5rem_1fr] gap-3">
        <span />
        <div className="flex justify-between font-mono text-[11px] text-[var(--chart-axis-text)]">
          {ticks.map((tick, index) => <span key={index}>{formatValue(tick)}</span>)}
        </div>
      </div>
      <div className="mt-1 grid grid-cols-[3.5rem_1fr] gap-3">
        <span />
        <div className="text-center text-[11px] text-[var(--chart-axis-text)]">{xLabel}</div>
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* Trade-off frontier — two measures, one point per plan               */
/* ------------------------------------------------------------------ */

export interface FrontierPoint {
  id: string;
  label: string;
  x: number;
  y: number;
  color: string;
}

/** Cost against emissions, one marker per plan, connected in emissions
 *  order so the shape of the trade-off is visible. Two measures on two
 *  axes is a scatter, not a dual-axis time series: each point is one
 *  object with both properties, which is the legitimate case. */
export const FrontierChart: React.FC<{
  points: FrontierPoint[];
  xLabel: string;
  yLabel: string;
  formatX: (value: number) => string;
  formatY: (value: number) => string;
  annotations?: { fromId: string; toId: string; text: string }[];
}> = ({ points, xLabel, yLabel, formatX, formatY, annotations = [] }) => {
  const gradientId = useId();
  const W = 720;
  const H = 320;
  const PAD = { top: 24, right: 96, bottom: 52, left: 104 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const xs = points.map(point => point.x);
  const ys = points.map(point => point.y);
  const xMin = Math.min(...xs) - (Math.max(...xs) - Math.min(...xs)) * 0.15;
  const xMax = Math.max(...xs) + (Math.max(...xs) - Math.min(...xs)) * 0.15;
  const yMin = Math.min(...ys) - (Math.max(...ys) - Math.min(...ys)) * 0.18;
  const yMax = Math.max(...ys) + (Math.max(...ys) - Math.min(...ys)) * 0.18;
  const xFor = (value: number) => PAD.left + ((value - xMin) / (xMax - xMin || 1)) * plotW;
  const yFor = (value: number) => PAD.top + plotH - ((value - yMin) / (yMax - yMin || 1)) * plotH;
  const ordered = [...points].sort((a, b) => b.y - a.y);
  const pathD = ordered.map((point, index) => `${index === 0 ? 'M' : 'L'} ${xFor(point.x)} ${yFor(point.y)}`).join(' ');

  return (
    <PlotFrame minWidth={620}>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={`${yLabel} against ${xLabel}`}>
        <defs>
          <linearGradient id={gradientId} x1="0" x2="1">
            <stop offset="0%" stopColor="var(--series-1)" />
            <stop offset="100%" stopColor="var(--series-3)" />
          </linearGradient>
        </defs>
        {[0, 0.5, 1].map(fraction => {
          const y = PAD.top + plotH - fraction * plotH;
          return (
            <g key={`y${fraction}`}>
              <line x1={PAD.left} x2={PAD.left + plotW} y1={y} y2={y} stroke="var(--chart-grid)" strokeWidth={1} />
              <text x={PAD.left - 10} y={y + 4} textAnchor="end" fontSize={11} fill="var(--chart-axis-text)">
                {formatY(yMin + fraction * (yMax - yMin))}
              </text>
            </g>
          );
        })}
        {[0, 0.5, 1].map(fraction => {
          const x = PAD.left + fraction * plotW;
          return (
            <text key={`x${fraction}`} x={x} y={H - 26} textAnchor="middle" fontSize={11} fill="var(--chart-axis-text)">
              {formatX(xMin + fraction * (xMax - xMin))}
            </text>
          );
        })}
        <path d={pathD} fill="none" stroke={`url(#${gradientId})`} strokeWidth={2} strokeLinecap="round" />
        {annotations.map(annotation => {
          const from = points.find(point => point.id === annotation.fromId);
          const to = points.find(point => point.id === annotation.toId);
          if (!from || !to) return null;
          return (
            <text
              key={`${annotation.fromId}-${annotation.toId}`}
              x={(xFor(from.x) + xFor(to.x)) / 2}
              y={(yFor(from.y) + yFor(to.y)) / 2 - 12}
              textAnchor="middle"
              fontSize={11}
              fontWeight={600}
              fill="var(--text-secondary)"
            >
              {annotation.text}
            </text>
          );
        })}
        {points.map(point => (
          <g key={point.id}>
            <circle cx={xFor(point.x)} cy={yFor(point.y)} r={7} fill={point.color} stroke="var(--surface-elevated)" strokeWidth={2} />
            <text
              x={xFor(point.x) + 13}
              y={yFor(point.y) + 4}
              fontSize={12}
              fontWeight={700}
              fill="var(--text-primary)"
            >
              {point.label}
            </text>
          </g>
        ))}
        <text x={PAD.left + plotW / 2} y={H - 6} textAnchor="middle" fontSize={11} fill="var(--chart-axis-text)">{xLabel}</text>
        <text x={16} y={PAD.top + plotH / 2} fontSize={11} fill="var(--chart-axis-text)" transform={`rotate(-90 16 ${PAD.top + plotH / 2})`} textAnchor="middle">{yLabel}</text>
      </svg>
    </PlotFrame>
  );
};

/* ------------------------------------------------------------------ */
/* Single-measure line — one series over a continuous axis             */
/* ------------------------------------------------------------------ */

export const LineChart: React.FC<{
  x: number[];
  y: number[];
  color?: string;
  xLabel: string;
  yLabel: string;
  formatX: (value: number) => string;
  formatY: (value: number) => string;
  markerX?: number | null;
  shadeFromX?: number | null;
  shadeLabel?: string;
  height?: number;
}> = ({ x, y, color = 'var(--series-1)', xLabel, yLabel, formatX, formatY, markerX, shadeFromX, shadeLabel, height = 250 }) => {
  const [hover, setHover] = useState<number | null>(null);
  const W = 720;
  const H = height;
  const PAD = { top: 18, right: 20, bottom: 46, left: 78 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const xMin = x[0];
  const xMax = x[x.length - 1];
  const lo = Math.min(...y);
  const hi = Math.max(...y);
  const pad = (hi - lo) * 0.12 || Math.abs(hi) * 0.05 || 1;
  const yMin = lo - pad;
  const yMax = hi + pad;
  const xFor = (value: number) => PAD.left + ((value - xMin) / (xMax - xMin || 1)) * plotW;
  const yFor = (value: number) => PAD.top + plotH - ((value - yMin) / (yMax - yMin || 1)) * plotH;
  const pathD = x.map((xv, i) => `${i === 0 ? 'M' : 'L'} ${xFor(xv)} ${yFor(y[i])}`).join(' ');

  return (
    <PlotFrame minWidth={560}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label={`${yLabel} by ${xLabel}`}
        onMouseLeave={() => setHover(null)}
        onMouseMove={event => {
          const rect = event.currentTarget.getBoundingClientRect();
          const ratio = (event.clientX - rect.left) / rect.width;
          const value = xMin + (((ratio * W) - PAD.left) / plotW) * (xMax - xMin);
          let nearest = 0;
          x.forEach((xv, i) => { if (Math.abs(xv - value) < Math.abs(x[nearest] - value)) nearest = i; });
          setHover(nearest);
        }}
      >
        {shadeFromX != null && (
          <>
            <rect
              x={xFor(shadeFromX)} y={PAD.top}
              width={PAD.left + plotW - xFor(shadeFromX)} height={plotH}
              fill="var(--success-soft)"
            />
            {shadeLabel && (
              <text x={xFor(shadeFromX) + 8} y={PAD.top + 14} fontSize={11} fontWeight={700} fill="var(--success)">
                {shadeLabel}
              </text>
            )}
          </>
        )}
        {[0, 0.25, 0.5, 0.75, 1].map(fraction => {
          const yy = PAD.top + plotH - fraction * plotH;
          return (
            <g key={fraction}>
              <line x1={PAD.left} x2={PAD.left + plotW} y1={yy} y2={yy} stroke="var(--chart-grid)" strokeWidth={1} />
              <text x={PAD.left - 10} y={yy + 4} textAnchor="end" fontSize={11} fill="var(--chart-axis-text)">
                {formatY(yMin + fraction * (yMax - yMin))}
              </text>
            </g>
          );
        })}
        {[xMin, (xMin + xMax) / 2, xMax].map(value => (
          <text key={value} x={xFor(value)} y={H - 22} textAnchor="middle" fontSize={11} fill="var(--chart-axis-text)">
            {formatX(value)}
          </text>
        ))}
        <path d={pathD} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {markerX != null && (
          <circle cx={xFor(markerX)} cy={yFor(y[x.indexOf(markerX)] ?? y[0])} r={6} fill={color} stroke="var(--surface-elevated)" strokeWidth={2} />
        )}
        {hover != null && (
          <>
            <line x1={xFor(x[hover])} x2={xFor(x[hover])} y1={PAD.top} y2={PAD.top + plotH} stroke="var(--chart-crosshair)" strokeWidth={1} />
            <circle cx={xFor(x[hover])} cy={yFor(y[hover])} r={5} fill={color} stroke="var(--surface-elevated)" strokeWidth={2} />
          </>
        )}
        <text x={PAD.left + plotW / 2} y={H - 4} textAnchor="middle" fontSize={11} fill="var(--chart-axis-text)">{xLabel}</text>
      </svg>
      {hover != null && (
        <Tooltip x={(xFor(x[hover]) / W) * 100} y={2}>
          <div className="font-mono font-semibold text-[var(--text-primary)]">{formatX(x[hover])}</div>
          <div className="mt-0.5 flex items-center justify-between gap-3">
            <span className="text-[var(--text-secondary)]">{yLabel}</span>
            <span className="font-mono text-[var(--text-primary)]">{formatY(y[hover])}</span>
          </div>
        </Tooltip>
      )}
    </PlotFrame>
  );
};
