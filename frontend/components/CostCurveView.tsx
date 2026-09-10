'use client';

import { PageHeader } from './PageHeader';
import React from 'react';
import { TrendDownIcon, TrendUpIcon } from '@phosphor-icons/react';
import { DemoData, GridPointResult } from '@/types/demo';
import { useAtlas } from '@/lib/AtlasContext';
import { PriceControl } from '@/components/PriceControl';
import { LineChart, seriesColor } from '@/components/Charts';
import { ktCO2e, kTonnes, pct, usdM } from '@/lib/format';

/** One panel of the small-multiple stack: a single measure against carbon
 *  price, on its own y-scale.
 *
 *  These are deliberately four separate plots sharing an x-axis rather than
 *  one plot with two y-axes. Overlaying cost and emissions on a shared frame
 *  would let the arbitrary alignment of two scales imply a relationship that
 *  is not in the data.
 */
const MeasurePanel: React.FC<{
  title: string;
  caption: string;
  points: GridPointResult[];
  value: (point: GridPointResult) => number;
  format: (value: number) => string;
  color: string;
  price: number;
  shadeFromX?: number | null;
  shadeLabel?: string;
}> = ({ title, caption, points, value, format, color, price, shadeFromX, shadeLabel }) => {
  const x = points.map(point => point.price_usd_per_tco2e);
  const y = points.map(value);
  const nearest = points.reduce((a, b) =>
    Math.abs(b.price_usd_per_tco2e - price) < Math.abs(a.price_usd_per_tco2e - price) ? b : a
  );
  const first = value(points[0]);
  const selected = value(nearest);
  const delta = selected - first;

  return (
    <section className="metric-card" aria-label={title}>
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--text-primary)]">{title}</h2>
        <span className="font-mono text-sm font-semibold text-[var(--text-primary)]">
          {format(selected)}
          <span className={`ml-2 text-xs ${delta <= 0 ? 'text-[var(--success)]' : 'text-[var(--text-tertiary)]'}`}>
            {delta === 0 ? 'unchanged' : `${delta < 0 ? '−' : '+'}${format(Math.abs(delta))} vs $0/t`}
          </span>
        </span>
      </div>
      <p className="mb-3 max-w-3xl text-sm leading-relaxed text-[var(--text-secondary)]">{caption}</p>
      <LineChart
        x={x}
        y={y}
        color={color}
        xLabel="Carbon price ($/tCO₂e)"
        yLabel={title}
        formatX={value => `$${Math.round(value)}`}
        formatY={format}
        markerX={nearest.price_usd_per_tco2e}
        shadeFromX={shadeFromX}
        shadeLabel={shadeLabel}
        height={210}
      />
    </section>
  );
};

export function CostCurveView({ data }: { data: DemoData }) {
  const { gridPoints, price, closest } = useAtlas();

  if (gridPoints.length < 2) {
    return (
      <div className="page-shell">
        <h1 className="mb-2 text-2xl font-bold text-[var(--text-primary)]">Carbon price sensitivity</h1>
        <p className="text-[var(--text-secondary)]">Not enough swept grid points to draw a curve yet.</p>
      </div>
    );
  }

  const withMetrics = gridPoints.filter(point => point.metrics);
  const hasClimate = withMetrics.length === gridPoints.length;
  const first = gridPoints[0];
  const last = gridPoints[gridPoints.length - 1];

  // Where the plan stops responding: the longest run of grid points at the
  // end of the sweep whose total cost is within a dollar of the last one.
  let plateauIndex = gridPoints.length - 1;
  for (let i = gridPoints.length - 2; i >= 0; i--) {
    if (Math.abs(gridPoints[i].total_usd - last.total_usd) <= 1) plateauIndex = i;
    else break;
  }
  const hasPlateau = gridPoints.length - 1 - plateauIndex >= 3;
  const plateauPrice = hasPlateau ? gridPoints[plateauIndex].price_usd_per_tco2e : null;

  const peak = gridPoints.reduce((a, b) => (b.total_usd > a.total_usd ? b : a), gridPoints[0]);
  const fallFromPeak = peak.total_usd - last.total_usd;
  const tier2Price = data.sweep.scenario_ticks.find(tick => tick.scenario_id === 'approved_text')?.high_usd_per_tco2e ?? null;

  const baselineEmissions = withMetrics[0]?.metrics?.lifecycle_emissions_tco2e;
  const selectedEmissions = closest?.metrics?.lifecycle_emissions_tco2e;
  const emissionsFalling = baselineEmissions != null && selectedEmissions != null && selectedEmissions < baselineEmissions;

  return (
    <div className="page-shell">
      <PageHeader category="Sensitivity" title="Follow the price. Understand the response." detail={hasPlateau ? `Plan locked in above $${plateauPrice}/t` : undefined}>
        <p className="text-base leading-relaxed text-[var(--text-secondary)]">
          {gridPoints.length} independently optimized five-year plans, one for every carbon price on the
          $0–$1,000/tCO₂e axis. Each measure below gets its own panel and its own scale — cost and carbon are
          different quantities and are never overlaid on a shared frame.
        </p>
      </PageHeader>

      <PriceControl />

      {fallFromPeak > 0 && (
        <div className="report-insight mb-5">
          <p className="text-sm leading-relaxed text-[var(--text-primary)]">
            Total cost climbs to {usdM(peak.total_usd)} around ${peak.price_usd_per_tco2e}/t, then retreats{' '}
            {usdM(fallFromPeak)} as fuel switching starts paying for itself
            {hasPlateau && <> and goes flat above ${plateauPrice}/t</>}.
            {hasPlateau && tier2Price != null && (
              <> The ceiling is real, not numerical: surplus credit under the approved text is capped at the
              Tier 2 remedial-unit price of ${tier2Price}/tCO₂e, so over-compliance stops paying beyond that
              point.</>
            )}
          </p>
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <MeasurePanel
          title="Total fleet cost"
          caption="Everything the fleet spends over five years — bunkers, fixed operating cost, time cost and the compliance bill."
          points={gridPoints}
          value={point => point.total_usd}
          format={value => usdM(value, 1)}
          color={seriesColor(0)}
          price={price}
          shadeFromX={plateauPrice}
          shadeLabel="PLAN LOCKED IN →"
        />

        <MeasurePanel
          title="Compliance bill"
          caption="The CII, NZF, FuelEU Maritime and EU ETS slice alone. It turns negative once the fleet over-complies and starts earning surplus credit."
          points={gridPoints}
          value={point => point.compliance_usd}
          format={value => usdM(value, 1)}
          color={seriesColor(1)}
          price={price}
        />

        {hasClimate && (
          <>
            <MeasurePanel
              title="Lifecycle GHG"
              caption="Well-to-wake emissions of the whole plan. This is the quantity the regulations actually price, and the one the fleet is being asked to cut."
              points={withMetrics}
              value={point => point.metrics!.lifecycle_emissions_tco2e}
              format={value => ktCO2e(value, 0)}
              color={seriesColor(2)}
              price={price}
            />

            <MeasurePanel
              title="Bunker mass"
              caption="Total tonnes loaded. It moves against emissions once ammonia enters the mix — low-carbon fuels carry less energy per tonne, so a cleaner plan is a heavier one."
              points={withMetrics}
              value={point => point.metrics!.fuel_tonnes}
              format={value => kTonnes(value, 0)}
              color={seriesColor(3)}
              price={price}
            />
          </>
        )}
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)] p-4 font-mono text-sm">
        <span className="text-[var(--text-secondary)]">
          Selected: <strong className="text-[var(--text-primary)]">${closest?.price_usd_per_tco2e ?? price}/tCO₂e</strong>
        </span>
        <span className="text-[var(--text-secondary)]">
          Cost: <strong className="text-[var(--text-primary)]">{usdM(closest?.total_usd ?? first.total_usd)}</strong>
        </span>
        {selectedEmissions != null && (
          <span className="flex items-center gap-1.5 text-[var(--text-secondary)]">
            Lifecycle GHG:{' '}
            <strong className={emissionsFalling ? 'font-bold text-[var(--success)]' : 'text-[var(--text-primary)]'}>
              {ktCO2e(selectedEmissions)}
            </strong>
            {baselineEmissions != null && (
              <span className={emissionsFalling ? 'text-[var(--success)]' : 'text-[var(--text-tertiary)]'}>
                {emissionsFalling ? <TrendDownIcon size={14} weight="bold" className="inline" /> : <TrendUpIcon size={14} weight="bold" className="inline" />}{' '}
                {pct(Math.abs(selectedEmissions - baselineEmissions) / baselineEmissions, 1)}
              </span>
            )}
          </span>
        )}
      </div>
    </div>
  );
}
