'use client';

import React, { useState } from 'react';
import { DemoData } from '@/types/demo';
import { fuelMixByPrice, fuelsElectedInSweep } from '@/lib/planAnalytics';
import { fuelName } from '@/lib/labels';
import { Legend, StackedAreaChart, seriesColor } from '@/components/Charts';

/** Fuel composition of the optimized plan across the swept carbon price.
 *
 *  Two of the four series sit below 3:1 contrast on the light surface, so
 *  this ships the table view alongside the plot rather than relying on hue
 *  alone (the relief rule).
 */
export const FuelAdoptionChart: React.FC<{ data: DemoData; showTableByDefault?: boolean }> = ({
  data,
  showTableByDefault = false,
}) => {
  const [showTable, setShowTable] = useState(showTableByDefault);
  const mix = fuelMixByPrice(data);
  const elected = fuelsElectedInSweep(data);
  const prices = mix.map(point => point.price);

  // A fuel's colour is fixed by its position in the catalog's own
  // dirtiest-first order, so it never changes when another fuel enters.
  const series = elected.map((fuelId, index) => ({
    key: fuelId,
    label: fuelName(fuelId),
    color: seriesColor(index),
    values: mix.map(point => point.counts[fuelId] ?? 0),
  }));

  // Only prices where the mix actually changes are worth a table row.
  const changeRows = mix.filter((point, index) => {
    if (index === 0) return true;
    return elected.some(fuelId => (point.counts[fuelId] ?? 0) !== (mix[index - 1].counts[fuelId] ?? 0));
  });

  return (
    <div>
      <StackedAreaChart
        x={prices}
        series={series}
        xLabel="Carbon price ($/tCO₂e)"
        yLabel="Vessel-years"
        formatX={value => `$${Math.round(value)}`}
        formatValue={value => `${value} vessel-years`}
      />
      <Legend items={series.map(s => ({ label: s.label, color: s.color }))} note={`${mix[0]?.totalSlots ?? 0} vessel-years in total`} />

      <button
        type="button"
        onClick={() => setShowTable(value => !value)}
        className="mt-3 text-xs font-semibold text-[var(--accent)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        aria-expanded={showTable}
      >
        {showTable ? 'Hide the numbers' : 'Show the numbers'}
      </button>

      {showTable && (
        <div className="mt-3 overflow-x-auto">
          <table className="decision-table">
            <caption className="sr-only">Vessel-years by fuel at each carbon price where the fleet plan changes</caption>
            <thead>
              <tr>
                <th scope="col">Carbon price</th>
                {elected.map(fuelId => <th key={fuelId} scope="col" className="text-right">{fuelName(fuelId)}</th>)}
              </tr>
            </thead>
            <tbody>
              {changeRows.map(row => (
                <tr key={row.price}>
                  <th scope="row" className="font-mono text-sm font-semibold text-[var(--text-primary)]">${row.price}/t</th>
                  {elected.map(fuelId => (
                    <td key={fuelId} className="text-right font-mono">
                      {row.counts[fuelId] ?? 0}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
