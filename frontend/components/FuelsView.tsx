'use client';

import { PageHeader } from './PageHeader';
import React from 'react';
import { CheckCircleIcon, MinusCircleIcon } from '@phosphor-icons/react';
import { DemoData } from '@/types/demo';
import { fuelCatalog, fuelEntryPrices, fuelMixByPrice, deepestCut } from '@/lib/planAnalytics';
import { FUEL_NOTES, fuelName } from '@/lib/labels';
import { FuelTransitionStages } from './FuelTransitionStages';
import { GainBarChart } from '@/components/Charts';
import { ktCO2e, pct } from '@/lib/format';

export function FuelsView({ data }: { data: DemoData }) {
  const catalog = fuelCatalog(data);
  const entry = fuelEntryPrices(data);
  const mix = fuelMixByPrice(data);
  const cut = deepestCut(data);
  const baselineMix = mix.find(point => point.price === 0) ?? mix[0];
  const finalMix = mix[mix.length - 1];
  const elected = new Set(mix.flatMap(point => Object.keys(point.counts)));

  const vlsfo = catalog.find(fuel => fuel.fuelId === 'vlsfo');
  // One measure, one series, one colour: bar length already encodes the
  // magnitude, so a per-bar hue would spend the colour channel on nothing.
  const intensityRows = catalog.map(fuel => ({
    label: fuelName(fuel.fuelId),
    sublabel: elected.has(fuel.fuelId) ? 'elected in plan' : 'available, not elected',
    value: fuel.ghgIntensity,
  }));

  return (
    <div className="page-shell">
      <PageHeader category="Fuels" title="The route to cleaner fuel.">
        <p className="mt-2 text-base leading-relaxed text-[var(--text-secondary)]">
          Eight bunker options are open to this fleet, from heavy fuel oil to green hydrogen. The optimizer is
          free to elect any of them for any vessel-year. This page shows which ones it actually chooses, at
          what carbon price each becomes worth paying for, and what that does to lifecycle emissions.
        </p>
      </PageHeader>

      {/* Headline shift */}
      <section aria-label="Fuel transition summary" className="report-stat-strip mb-6 grid sm:grid-cols-3">
        <div className="p-4 sm:border-r sm:border-[var(--success-soft-border)]">
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--text-secondary)]">Low-carbon vessel-years</div>
          <div className="mt-1 font-mono text-2xl font-bold text-[var(--text-primary)]">
            {baselineMix.lowCarbonSlots} → {finalMix.lowCarbonSlots}
          </div>
          <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">
            of {finalMix.totalSlots} vessel-years, moving from {pct(baselineMix.lowCarbonSlots / baselineMix.totalSlots, 0)} to{' '}
            {pct(finalMix.lowCarbonSlots / finalMix.totalSlots, 0)} across the price range.
          </p>
        </div>
        <div className="border-t border-[var(--success-soft-border)] p-4 sm:border-t-0 sm:border-r">
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--text-secondary)]">Lifecycle GHG removed</div>
          <div className="mt-1 font-mono text-2xl font-bold text-[var(--success)]">
            {cut ? ktCO2e(Math.abs(cut.deltaTco2e)) : '—'}
          </div>
          <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">
            {cut ? `${pct(Math.abs(cut.deltaFraction))} below the $0/t plan, achieved entirely through fuel, speed, route and shore-power choices.` : ''}
          </p>
        </div>
        <div className="border-t border-[var(--success-soft-border)] p-4 sm:border-t-0">
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--text-secondary)]">First ammonia election</div>
          <div className="mt-1 font-mono text-2xl font-bold text-[var(--text-primary)]">
            {entry.ammonia != null ? `$${entry.ammonia}/t` : 'not elected'}
          </div>
          <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">
            The carbon price at which zero-carbon ammonia first pays for itself somewhere in this fleet.
          </p>
        </div>
      </section>

      <section className="report-section" aria-label="Fuel adoption by carbon price">
        <FuelTransitionStages data={data} />
      </section>

      {/* Break-even table */}
      <section className="mb-6 overflow-hidden rounded-xl border border-[var(--border)] shadow-sm" aria-label="Fuel catalog">
        <div className="border-b border-[var(--border)] bg-[var(--surface-sunken)] px-4 py-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--text-secondary)]">
            Fuel catalog and switching thresholds
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-[var(--text-secondary)]">
            Well-to-wake intensity and energy content drive the compliance calculation; the bunker price drives
            the operating cost. The last column is the answer the optimizer gives when both are weighed together.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="decision-table">
            <thead>
              <tr>
                <th scope="col">Fuel</th>
                <th scope="col" className="text-right">Well-to-wake GHG</th>
                <th scope="col" className="text-right">vs. VLSFO</th>
                <th scope="col" className="text-right">Energy content</th>
                <th scope="col" className="text-right">Bunker price</th>
                <th scope="col">Elected from</th>
              </tr>
            </thead>
            <tbody>
              {catalog.map(fuel => {
                const isElected = elected.has(fuel.fuelId);
                const entryPrice = entry[fuel.fuelId];
                const relative = vlsfo ? fuel.ghgIntensity / vlsfo.ghgIntensity - 1 : 0;
                return (
                  <tr key={fuel.fuelId}>
                    <th scope="row" className="text-left">
                      <div className="font-semibold text-[var(--text-primary)]">{fuelName(fuel.fuelId)}</div>
                      <div className="mt-0.5 max-w-md text-xs font-normal leading-relaxed text-[var(--text-tertiary)]">
                        {FUEL_NOTES[fuel.fuelId] ?? ''}
                      </div>
                    </th>
                    <td className="text-right font-mono">{fuel.ghgIntensity.toFixed(1)} g/MJ</td>
                    <td className={`text-right font-mono ${relative < -0.05 ? 'text-[var(--success)] font-semibold' : ''}`}>
                      {relative < 0 ? '−' : '+'}{Math.abs(relative * 100).toFixed(0)}%
                    </td>
                    <td className="text-right font-mono">{(fuel.lcvMjPerTonne / 1000).toLocaleString()} GJ/t</td>
                    <td className="text-right font-mono">
                      {fuel.priceUsdPerTonne != null ? `$${fuel.priceUsdPerTonne.toLocaleString()}/t` : '—'}
                    </td>
                    <td>
                      {!isElected ? (
                        <span className="inline-flex items-center gap-1.5 font-mono text-sm text-[var(--text-tertiary)]">
                          <MinusCircleIcon size={14} weight="bold" /> Not elected
                        </span>
                      ) : entryPrice == null ? (
                        <span className="inline-flex items-center gap-1.5 font-mono text-sm text-[var(--text-secondary)]">
                          <CheckCircleIcon size={14} weight="bold" /> $0/t — already optimal
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 font-mono text-sm font-semibold text-[var(--success)]">
                          <CheckCircleIcon size={14} weight="bold" /> ${entryPrice}/tCO₂e
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Intensity ladder */}
      <section className="metric-card" aria-label="Fuel intensity comparison">
        <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--text-primary)]">
          Why the ordering is what it is
        </h2>
        <p className="mb-5 mt-1 text-sm leading-relaxed text-[var(--text-secondary)]">
          Well-to-wake GHG intensity, the quantity every one of the four regimes ultimately prices. The three
          conventional bunkers sit within a percent of each other near 91 g/MJ — switching between them buys
          almost nothing. The gap to LNG and below is where the compliance saving actually lives.
        </p>
        <GainBarChart
          rows={intensityRows}
          formatValue={value => `${value.toFixed(1)} g/MJ`}
          ariaLabel="Well-to-wake GHG intensity by fuel"
        />
      </section>
    </div>
  );
}
