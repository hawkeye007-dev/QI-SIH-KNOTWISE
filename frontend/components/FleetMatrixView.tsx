'use client';

import { PageHeader } from './PageHeader';
import React, { useState } from 'react';
import { WarningIcon, CheckCircleIcon } from '@phosphor-icons/react';
import { VesselYearGene, DemoData } from '@/types/demo';
import { useAtlas } from '@/lib/AtlasContext';
import { FUEL_NAMES, ROUTE_NAMES, VESSEL_CLASS_NAMES } from '@/lib/labels';
import { PriceControl } from '@/components/PriceControl';

const FIELDS = [
  { key: 'fuel_id',          label: 'Fuel Option' },
  { key: 'speed_band_index', label: 'Speed Profile' },
  { key: 'route_id',         label: 'Assigned Trade Route' },
  { key: 'shore_power',      label: 'Shore Power (OPS)' },
  { key: 'pool_opt_in',      label: 'FuelEU Pooling' },
  { key: 'borrow_election',  label: 'Banking / Borrowing' },
] as const;
type StrategyField = (typeof FIELDS)[number]['key'];
type FuelProps = { ghg_intensity_gco2e_per_mj: number; lcv_mj_per_tonne: number };

const SPEED_FRACTIONS = [0.05, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 1];

const fmt = (field: StrategyField, v: unknown, designSpeedKnots?: number): string => {
  if (v === undefined || v === null) return '—';
  if (field === 'fuel_id') return FUEL_NAMES[String(v)] || String(v);
  if (field === 'route_id') return ROUTE_NAMES[String(v)] || String(v);
  if (field === 'speed_band_index') {
    const speed = designSpeedKnots == null ? undefined : designSpeedKnots * SPEED_FRACTIONS[Number(v)];
    return speed == null ? `Band ${v}` : `Band ${v} (${speed.toFixed(1)} kn)`;
  }
  if (typeof v === 'boolean') return v ? 'Elected' : 'Not elected';
  return String(v);
};

const YEARS = [2026, 2027, 2028, 2029, 2030];

export function FleetMatrixView({ data }: { data: DemoData }) {
  const { currentConfig, baselineConfig, unstableKeys, price, cargoDemand, closest, gridPoints } = useAtlas();
  const [field, setField] = useState<StrategyField>('fuel_id');
  const vessels = data.fleet.vessels;
  const fuels = data.fleet.fuel_properties.fuels;

  const curMap = new Map<string, VesselYearGene>();
  currentConfig.forEach(g => curMap.set(`${g.vessel_id}:${g.year}`, g));

  const baseMap = new Map<string, VesselYearGene>();
  baselineConfig.forEach(g => baseMap.set(`${g.vessel_id}:${g.year}`, g));

  const deepSeaVessels = vessels.filter(v => v.band !== 'C');
  const baselineMetrics = (gridPoints.find(point => point.price_usd_per_tco2e === 0) ?? gridPoints[0])?.metrics;
  const emissionsDelta = closest?.metrics && baselineMetrics
    ? closest.metrics.lifecycle_emissions_tco2e - baselineMetrics.lifecycle_emissions_tco2e
    : null;

  let flipCount = 0;
  deepSeaVessels.forEach(v => {
    YEARS.forEach(y => {
      const k = `${v.vessel_id}:${y}`;
      const cur = curMap.get(k);
      const base = baseMap.get(k);
      if (cur && base && cur[field] !== base[field]) flipCount++;
    });
  });

  return (
    <div className="page-shell">
      <PageHeader category="Fleet" title="One fleet. Every operating decision." detail={<><span>Carbon price: ${price}/t</span><span>{flipCount} changes from baseline</span></>}>
        <p>Inspect fuel, speed, routes and shore power for {deepSeaVessels.length} deep-sea vessels across 2026–2030. Highlighted cells differ from the $0/t plan. Select a strategy below to inspect its decisions.</p>
      </PageHeader>

      <PriceControl />

      {closest?.metrics && baselineMetrics && emissionsDelta !== null && (
        <section aria-label="Selected plan climate result" className="report-stat-strip mb-5 grid sm:grid-cols-3">
          <div className="p-4 sm:border-r sm:border-[var(--success-soft-border)]">
            <div className="text-sm font-semibold text-[var(--text-primary)]">Selected plan climate result</div>
            <p className="mt-1 text-sm leading-relaxed text-[var(--text-secondary)]">These fleet decisions carry a five-year lifecycle-GHG and fuel outcome, not only a cost result.</p>
          </div>
          <div className="border-t border-[var(--success-soft-border)] p-4 sm:border-t-0 sm:border-r">
            <div className="text-xs text-[var(--text-secondary)]">Lifecycle GHG</div>
            <div className="mt-1 font-mono text-xl font-bold text-[var(--text-primary)]">{(closest.metrics.lifecycle_emissions_tco2e / 1000).toFixed(0)}k tCO₂e</div>
          </div>
          <div className="border-t border-[var(--success-soft-border)] p-4 sm:border-t-0">
            <div className="text-xs text-[var(--text-secondary)]">Change vs. $0/t plan</div>
            <div className={`mt-1 font-mono text-xl font-bold ${emissionsDelta <= 0 ? 'text-[var(--success)]' : 'text-[var(--warning)]'}`}>{emissionsDelta <= 0 ? '↓' : '↑'} {Math.abs(emissionsDelta / 1000).toFixed(0)}k tCO₂e</div>
          </div>
        </section>
      )}

      {/* Dimension Selection */}
      <div className="flex flex-wrap items-center gap-2 mb-5 bg-[var(--surface-sunken)] p-2 rounded-xl border border-[var(--border)]">
        <span className="text-sm text-[var(--text-secondary)] px-2 uppercase tracking-wide">Select Strategy View:</span>
        {FIELDS.map(f => (
          <button
            key={f.key}
            onClick={() => setField(f.key)}
            aria-pressed={field === f.key}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:outline-none ${
              field === f.key
                ? 'bg-[var(--action-bg)] text-[var(--action-text)] font-semibold'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-elevated)] border border-transparent'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Matrix Table */}
      <div className="overflow-x-auto border border-[var(--border)] rounded-xl shadow-sm mb-6">
        <table className="decision-table">
          <thead>
            <tr>
              <th className="w-2/5">Vessel Name &amp; Class</th>
              {YEARS.map(y => (
                <th key={y} className="text-center font-mono">{y}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {deepSeaVessels.map(v => {
              const defaults = data.fleet.vessel_class_defaults[v.band] as { dwt_tonnes: number; design_speed_knots: number };
              const meta = {
                name: `Fleet vessel ${v.vessel_id}`,
                type: VESSEL_CLASS_NAMES[v.band] || `Band ${v.band} vessel`,
              };
              return (
                <tr key={v.vessel_id}>
                  <td>
                    <div className="font-mono text-sm font-bold text-[var(--text-primary)] flex items-center gap-2">
                      <span>{meta.name}</span>
                      <span className="text-[11px] px-1.5 py-0.5 rounded bg-[var(--surface-sunken)] text-[var(--text-tertiary)] border border-[var(--border)]">
                        {v.vessel_id}
                      </span>
                    </div>
                    <div className="text-xs text-[var(--text-tertiary)] mt-0.5">
                      {meta.type} · <span className="font-mono text-[11px]">{defaults.dwt_tonnes.toLocaleString()} DWT</span>
                    </div>
                  </td>
                  {YEARS.map(year => {
                    const k = `${v.vessel_id}:${year}`;
                    const cur = curMap.get(k);
                    const base = baseMap.get(k);
                    const curVal = cur?.[field];
                    const baseVal = base?.[field];
                    const flipped = base != null && cur != null && curVal !== baseVal;
                    const unstable = unstableKeys.has(`${v.vessel_id}:${year}:${field}`);
                    return (
                      <td key={year} className="text-center">
                        <div className={`p-2.5 rounded-lg text-sm transition-colors ${
                          flipped ? 'cell-flip' : 'text-[var(--text-secondary)] bg-[var(--surface-elevated)] border border-[var(--border)]'
                        }`}>
                          <div className="font-medium">{fmt(field, curVal, defaults.design_speed_knots)}</div>
                          {flipped && (
                            <div className="text-xs text-[var(--text-tertiary)] line-through mt-0.5 font-mono">
                              {fmt(field, baseVal, defaults.design_speed_knots)}
                            </div>
                          )}
                          {unstable && (
                            <div className="text-[11px] text-[var(--text-tertiary)] font-mono mt-0.5 flex items-center justify-center gap-1">
                              <WarningIcon size={11} weight="bold" /> Variance
                            </div>
                          )}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Cargo Demand Coverage */}
      {cargoDemand.length > 0 && (
        <div className="border border-[var(--border)] rounded-xl overflow-hidden mb-6 shadow-sm">
          <div className="px-4 py-3 bg-[var(--surface-sunken)] border-b border-[var(--border)]">
            <div className="text-sm font-semibold uppercase text-[var(--text-secondary)]">Annual cargo throughput</div>
            <p className="text-sm text-[var(--text-secondary)] mt-0.5">
              Required and assigned cargo throughput are calculated by the optimizer using each route&apos;s annual
              transit distance and payload-utilization assumption.
            </p>
          </div>
          <table className="decision-table">
            <thead>
              <tr>
                <th>Route</th>
                <th className="text-right">Required (tonne-nm/year)</th>
                <th className="text-right">Lowest Assigned (tonne-nm/year)</th>
                <th className="text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {cargoDemand.map(row => (
                <tr key={row.routeId}>
                  <td className="font-mono text-[var(--text-secondary)]">{ROUTE_NAMES[row.routeId] || row.routeId}</td>
                  <td className="text-right font-mono text-[var(--text-tertiary)]">{row.requiredTonneNm.toLocaleString()}</td>
                  <td className="text-right font-mono text-[var(--text-tertiary)]">{row.minAssignedTonneNm.toLocaleString()}</td>
                  <td className="text-center">
                    {row.yearsShort.length === 0 ? (
                      <span className="font-mono text-sm text-[var(--success)] font-bold inline-flex items-center gap-1">
                        <CheckCircleIcon size={14} weight="bold" /> Fully Served
                      </span>
                    ) : (
                      <span className="font-mono text-sm text-[var(--text-primary)] inline-flex items-center gap-1">
                        <WarningIcon size={14} weight="bold" /> Under-served {row.yearsShort.length}/5 yrs
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Fuel Options & GHG Intensity */}
      {fuels && Object.keys(fuels).length > 0 && (
        <div className="border border-[var(--border)] rounded-xl overflow-hidden mb-6 shadow-sm">
          <div className="px-4 py-3 bg-[var(--surface-sunken)] border-b border-[var(--border)]">
            <div className="text-sm font-semibold uppercase text-[var(--text-secondary)]">
              Fuel Options &amp; Lifecycle GHG Intensity
            </div>
            <p className="text-sm text-[var(--text-secondary)] mt-0.5">
              Every fuel the optimizer can elect for this fleet, priced on its well-to-wake GHG intensity and
              energy content. Not every fuel wins a slot in every plan — the matrix above shows which ones do.
            </p>
          </div>
          <table className="decision-table">
            <thead>
              <tr>
                <th>Fuel</th>
                <th className="text-right">GHG Intensity (gCO₂e/MJ)</th>
                <th className="text-right">Energy Content (MJ/tonne)</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(fuels as Record<string, FuelProps>).map(([fuelId, props]) => (
                <tr key={fuelId}>
                  <td className="font-mono text-[var(--text-secondary)]">{FUEL_NAMES[fuelId] || fuelId}</td>
                  <td className="text-right font-mono text-[var(--text-tertiary)]">
                    {props.ghg_intensity_gco2e_per_mj.toFixed(1)}
                  </td>
                  <td className="text-right font-mono text-[var(--text-tertiary)]">
                    {props.lcv_mj_per_tonne.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
        <span className="w-2 h-2 rounded-full bg-[var(--accent)]" />
        <span>Highlighted cells indicate a strategic operational shift from the $0/t baseline.</span>
      </div>
    </div>
  );
}
