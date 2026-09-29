'use client';

import { PageHeader } from './PageHeader';
import React from 'react';
import { CheckCircleIcon, MinusCircleIcon } from '@phosphor-icons/react';
import { DemoData } from '@/types/demo';
import { fuelCatalog, fuelEntryPrices, fuelMixByPrice, deepestCut } from '@/lib/planAnalytics';
import { FUEL_NOTES, fuelName } from '@/lib/labels';
import { FuelTransitionStages } from './FuelTransitionStages';
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

  return (
    <div className="page-shell">
      <PageHeader category="Fuels" title="The route to cleaner fuel.">
        <p className="mt-2 text-base leading-relaxed text-[var(--text-secondary)]">
          Eight fuels are open to every vessel-year. This page shows which ones the optimizer picks, and at
          what carbon price each becomes worth it.
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
            {cut ? `${pct(Math.abs(cut.deltaFraction))} below the $0/t plan, from fuel, speed, route and shore-power choices.` : ''}
          </p>
        </div>
        <div className="border-t border-[var(--success-soft-border)] p-4 sm:border-t-0">
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--text-secondary)]">First ammonia election</div>
          <div className="mt-1 font-mono text-2xl font-bold text-[var(--text-primary)]">
            {entry.ammonia != null ? `$${entry.ammonia}/t` : 'not elected'}
          </div>
          <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">
            Carbon price at which ammonia first pays off for a vessel.
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
            Intensity drives compliance cost, bunker price drives operating cost. The last column weighs both.
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

    </div>
  );
}
