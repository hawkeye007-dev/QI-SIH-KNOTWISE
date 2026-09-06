'use client';

import React, { useState } from 'react';
import { VesselYearGene, FleetVessel } from '@/types/demo';

interface CargoDemandRow {
  routeId: string;
  requiredDwt: number;
  minAssignedDwt: number;
  yearsShort: number[];
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  currentConfig: VesselYearGene[];
  baselineConfig: VesselYearGene[];
  unstableKeys: Set<string>;
  vessels: FleetVessel[];
  currentPrice: number;
  /** Per-route cargo demand coverage at the current price (PS hard
   *  constraint) -- optional so this modal still renders against an older
   *  caller that hasn't computed it yet. */
  cargoDemand?: CargoDemandRow[];
  /** fleet.fuel_properties.fuels from demo_data.json -- the real GHG
   *  intensity / LCV figures the optimizer already prices every fuel
   *  election against. Optional for the same reason as cargoDemand. */
  fuels?: Record<string, { ghg_intensity_gco2e_per_mj: number; lcv_mj_per_tonne: number; notes?: string }>;
}

/** Alternative fuels the PS names that this fleet's model does not yet
 *  price -- listed explicitly rather than silently omitted, so "are
 *  alternative fuels considered" has an honest answer instead of no
 *  answer at all. */
const UNMODELED_FUELS = ['Ammonia', 'Hydrogen'];

const FIELDS = [
  { key: 'fuel_id',          label: 'Fuel Option' },
  { key: 'speed_band_index', label: 'Speed Profile' },
  { key: 'route_id',         label: 'Assigned Trade Route' },
  { key: 'shore_power',      label: 'Shore Power (OPS)' },
  { key: 'pool_opt_in',      label: 'FuelEU Pooling' },
  { key: 'borrow_election',  label: 'Banking / Borrowing' },
];

const FUEL_NAMES: Record<string, string> = {
  hfo_scrubber: 'HFO + Scrubber',
  vlsfo: 'VLSFO Baseline',
  mgo: 'MGO Low-Sulfur',
  lng: 'LNG Dual-Fuel',
  b30_blend: 'B30 Biofuel',
  methanol: 'e-Methanol',
};

const ROUTE_NAMES: Record<string, string> = {
  india_northeurope: 'India ➔ N. Europe',
  india_mediterranean: 'India ➔ Mediterranean',
  india_gulf: 'India ➔ Arabian Gulf',
  india_seasia: 'India ➔ SE Asia',
  coastal_westcoast: 'India West Feeder',
  coastal_eastcoast: 'India East Feeder',
};

const VESSEL_REAL_NAMES: Record<string, { name: string; type: string; imo: string }> = {
  A1: { name: 'Knotwise Victory', type: 'Ultra Large Container', imo: 'IMO 9845120 (18,000 TEU)' },
  A2: { name: 'Knotwise Pioneer', type: 'Ultra Large Container', imo: 'IMO 9845132 (18,000 TEU)' },
  A3: { name: 'Knotwise Endeavour', type: 'Very Large Crude Carrier', imo: 'IMO 9732014 (300k DWT)' },
  A4: { name: 'Knotwise Horizon', type: 'Very Large Crude Carrier', imo: 'IMO 9732026 (300k DWT)' },
  B1: { name: 'Knotwise Explorer', type: 'Capesize Bulk Carrier', imo: 'IMO 9651048 (180k DWT)' },
  B2: { name: 'Knotwise Vanguard', type: 'Capesize Bulk Carrier', imo: 'IMO 9651050 (180k DWT)' },
  B3: { name: 'Knotwise Sentinel', type: 'Post-Panamax Container', imo: 'IMO 9541299 (8,000 TEU)' },
};

const fmt = (field: string, v: any): string => {
  if (v === undefined || v === null) return '—';
  if (field === 'fuel_id') return FUEL_NAMES[v] || v;
  if (field === 'route_id') return ROUTE_NAMES[v] || v;
  if (field === 'speed_band_index') return `Band ${v} (${14 + (5 - v) * 2} kts)`;
  if (typeof v === 'boolean') return v ? 'Elected' : 'Baseline';
  return String(v);
};

const YEARS = [2026, 2027, 2028, 2029, 2030];

export const MatrixModal: React.FC<Props> = ({
  isOpen, onClose, currentConfig, baselineConfig, unstableKeys, vessels, currentPrice, cargoDemand, fuels
}) => {
  const [field, setField] = useState('fuel_id');

  if (!isOpen) return null;

  const curMap = new Map<string, VesselYearGene>();
  currentConfig.forEach(g => curMap.set(`${g.vessel_id}:${g.year}`, g));

  const baseMap = new Map<string, VesselYearGene>();
  baselineConfig.forEach(g => baseMap.set(`${g.vessel_id}:${g.year}`, g));

  const deepSeaVessels = vessels.filter(v => v.band !== 'C');

  let flipCount = 0;
  deepSeaVessels.forEach(v => {
    YEARS.forEach(y => {
      const k = `${v.vessel_id}:${y}`;
      const cur = curMap.get(k);
      const base = baseMap.get(k);
      if (cur && base && (cur as any)[field] !== (base as any)[field]) flipCount++;
    });
  });

  return (
    <div className="overlay-backdrop" onClick={onClose}>
      <div className="overlay-panel w-full max-w-5xl p-6 shadow-2xl border border-neutral-800" onClick={e => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-neutral-800 pb-4 mb-5">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                Fleet Operating Strategy Matrix (2026–2030)
              </h2>
              <span className="tag font-mono text-white">Carbon Tax: ${currentPrice}/t</span>
              {flipCount > 0 && (
                <span className="tag bg-white text-black font-semibold border-white font-mono">
                  {flipCount} Reallocations
                </span>
              )}
            </div>
            <p className="text-xs text-neutral-400 mt-1 font-sans">
              Year-by-year operational decisions across 7 deep-sea vessels under current carbon pricing.
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg border border-neutral-800 flex items-center justify-center text-neutral-400 hover:text-white hover:border-neutral-600 font-mono text-sm transition-all"
          >
            ✕
          </button>
        </div>

        {/* Dimension Selection Buttons */}
        <div className="flex flex-wrap items-center gap-2 mb-5 bg-neutral-950 p-2 rounded-lg border border-neutral-900">
          <span className="text-xs text-neutral-400 font-mono px-2 uppercase">Select Strategy View:</span>
          {FIELDS.map(f => (
            <button
              key={f.key}
              onClick={() => setField(f.key)}
              className={`px-3 py-1.5 rounded-md text-xs font-mono transition-all ${
                field === f.key
                  ? 'bg-white text-black font-bold shadow-sm'
                  : 'text-neutral-400 hover:text-white hover:bg-neutral-900 border border-transparent'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Enhanced Matrix Table */}
        <div className="overflow-x-auto border border-neutral-800 rounded-lg shadow-sm">
          <table className="decision-table">
            <thead>
              <tr>
                <th className="w-2/5">Vessel Name & Class</th>
                {YEARS.map(y => (
                  <th key={y} className="text-center font-mono">{y}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {deepSeaVessels.map(v => {
                const meta = VESSEL_REAL_NAMES[v.vessel_id] || {
                  name: `Vessel ${v.vessel_id}`,
                  type: `Band ${v.band} Vessel`,
                  imo: 'IMO Registered'
                };

                return (
                  <tr key={v.vessel_id}>
                    <td>
                      <div className="font-mono text-xs font-bold text-white flex items-center gap-2">
                        <span>{meta.name}</span>
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-neutral-900 text-neutral-400 border border-neutral-800">
                          {v.vessel_id}
                        </span>
                      </div>
                      <div className="text-[11px] text-neutral-400 font-sans mt-0.5">
                        {meta.type} • <span className="font-mono text-[10px] text-neutral-500">{meta.imo}</span>
                      </div>
                    </td>
                    {YEARS.map(year => {
                      const k = `${v.vessel_id}:${year}`;
                      const cur = curMap.get(k);
                      const base = baseMap.get(k);
                      const curVal = cur ? (cur as any)[field] : undefined;
                      const baseVal = base ? (base as any)[field] : undefined;
                      const flipped = base != null && cur != null && curVal !== baseVal;
                      const unstable = unstableKeys.has(`${v.vessel_id}:${year}:${field}`);

                      return (
                        <td key={year} className="text-center">
                          <div className={`p-2.5 rounded-md text-xs transition-all ${
                            flipped
                              ? 'cell-flip'
                              : 'text-neutral-300 bg-neutral-950 border border-neutral-900'
                          }`}>
                            <div className="font-medium">{fmt(field, curVal)}</div>
                            {flipped && (
                              <div className="text-[10px] text-neutral-400 line-through mt-0.5 font-mono">
                                {fmt(field, baseVal)}
                              </div>
                            )}
                            {unstable && (
                              <div className="text-[9px] text-neutral-500 font-mono mt-0.5">⚠️ Variance</div>
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

        {/* Cargo Demand Coverage -- the PS's "cargo demand satisfaction" hard
            constraint, read off the same route_id assignments and
            min_capacity_dwt_required figures the objective's
            demand_shortfall_penalty already enforces during optimization,
            not a separate re-derivation. */}
        {cargoDemand && cargoDemand.length > 0 && (
          <div className="mt-4 border border-neutral-800 rounded-lg overflow-hidden">
            <div className="px-4 py-2.5 bg-neutral-950 border-b border-neutral-800">
              <div className="text-xs font-mono font-semibold uppercase text-white">Cargo Demand Coverage</div>
              <p className="text-[11px] text-neutral-500 mt-0.5 font-sans">
                Assigned deadweight vs. each route&apos;s minimum capacity requirement, every year 2026–2030, at
                the current plan.
              </p>
            </div>
            <table className="decision-table">
              <thead>
                <tr>
                  <th>Route</th>
                  <th className="text-right">Required (DWT)</th>
                  <th className="text-right">Worst-Year Assigned (DWT)</th>
                  <th className="text-center">Status</th>
                </tr>
              </thead>
              <tbody>
                {cargoDemand.map(row => (
                  <tr key={row.routeId}>
                    <td className="font-mono text-neutral-300">{ROUTE_NAMES[row.routeId] || row.routeId}</td>
                    <td className="text-right font-mono text-neutral-400">{row.requiredDwt.toLocaleString()}</td>
                    <td className="text-right font-mono text-neutral-400">{row.minAssignedDwt.toLocaleString()}</td>
                    <td className="text-center">
                      {row.yearsShort.length === 0 ? (
                        <span className="font-mono text-[11px] text-emerald-400 font-bold">✓ Fully Served</span>
                      ) : (
                        <span className="font-mono text-[11px] text-white">
                          ⚠ Under-served {row.yearsShort.length}/5 yrs
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Fuel Options & GHG Intensity -- the real fuel_properties every
            election above is priced against, including the fuels this
            fleet's economics never happen to elect. */}
        {fuels && Object.keys(fuels).length > 0 && (
          <div className="mt-4 border border-neutral-800 rounded-lg overflow-hidden">
            <div className="px-4 py-2.5 bg-neutral-950 border-b border-neutral-800">
              <div className="text-xs font-mono font-semibold uppercase text-white">
                Fuel Options &amp; Lifecycle GHG Intensity
              </div>
              <p className="text-[11px] text-neutral-500 mt-0.5 font-sans">
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
                {Object.entries(fuels).map(([fuelId, props]) => (
                  <tr key={fuelId}>
                    <td className="font-mono text-neutral-300">{FUEL_NAMES[fuelId] || fuelId}</td>
                    <td className="text-right font-mono text-neutral-400">
                      {props.ghg_intensity_gco2e_per_mj.toFixed(1)}
                    </td>
                    <td className="text-right font-mono text-neutral-400">
                      {props.lcv_mj_per_tonne.toLocaleString()}
                    </td>
                  </tr>
                ))}
                {UNMODELED_FUELS.map(name => (
                  <tr key={name}>
                    <td className="font-mono text-neutral-500">{name}</td>
                    <td className="text-right font-mono text-neutral-600" colSpan={2}>
                      Not yet modeled — no cost or engine-compatibility data in this fleet
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Footer Info */}
        <div className="mt-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-neutral-400 font-mono">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-white" />
            <span>Highlighted cells indicate strategic operational shift from $0/t baseline.</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-neutral-900 text-white rounded border border-neutral-700 hover:bg-neutral-800 text-xs font-mono transition-all"
          >
            Close Panel
          </button>
        </div>
      </div>
    </div>
  );
};
