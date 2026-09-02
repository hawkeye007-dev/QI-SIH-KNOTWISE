'use client';

import React, { useState } from 'react';
import { VesselYearGene, FleetVessel } from '@/types/demo';

interface Props {
  currentConfig: VesselYearGene[];
  baselineConfig: VesselYearGene[];
  unstableKeys: Set<string>;
  vessels: FleetVessel[];
}

const FIELDS = [
  { key: 'fuel_id',          label: 'Fuel' },
  { key: 'speed_band_index', label: 'Speed' },
  { key: 'route_id',         label: 'Route' },
  { key: 'shore_power',      label: 'Shore Pwr' },
  { key: 'pool_opt_in',      label: 'Pool' },
  { key: 'borrow_election',  label: 'Borrow' },
];

const FUEL: Record<string, string> = {
  hfo_scrubber: 'HFO+Scrub', vlsfo: 'VLSFO', mgo: 'MGO',
  lng: 'LNG', b30_blend: 'B30', methanol: 'Methanol',
};

const ROUTE_SHORT: Record<string, string> = {
  india_northeurope: 'N.Eur', india_mediterranean: 'Med',
  india_gulf: 'Gulf', india_seasia: 'SEAsia',
  coastal_westcoast: 'WCoast', coastal_eastcoast: 'ECoast',
};

const fmt = (field: string, v: any): string => {
  if (v === undefined || v === null) return '—';
  if (field === 'fuel_id') return FUEL[v] || v;
  if (field === 'route_id') return ROUTE_SHORT[v] || v;
  if (field === 'speed_band_index') return `Spd ${v}`;
  if (typeof v === 'boolean') return v ? '✓' : '✗';
  return String(v);
};

const YEARS = [2026, 2027, 2028, 2029, 2030];

export const DecisionGrid: React.FC<Props> = ({ currentConfig, baselineConfig, unstableKeys, vessels }) => {
  const [field, setField] = useState('fuel_id');

  const curMap = React.useMemo(() => {
    const m = new Map<string, VesselYearGene>();
    currentConfig.forEach(g => m.set(`${g.vessel_id}:${g.year}`, g));
    return m;
  }, [currentConfig]);

  const baseMap = React.useMemo(() => {
    const m = new Map<string, VesselYearGene>();
    baselineConfig.forEach(g => m.set(`${g.vessel_id}:${g.year}`, g));
    return m;
  }, [baselineConfig]);

  const deepSeaVessels = vessels.filter(v => v.band !== 'C');

  // Count total flips for current field
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
    <div className="glass-panel p-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            Fleet Decision Matrix
            {flipCount > 0 && (
              <span className="badge badge-rose">{flipCount} Flip{flipCount > 1 ? 's' : ''}</span>
            )}
          </h3>
          <p className="text-[11px] text-slate-400 mt-0.5">
            {deepSeaVessels.length} deep-sea vessels × {YEARS.length} years · Red = flipped vs. baseline · ⚠️ = unstable (GA seed variance)
          </p>
        </div>

        {/* Field selector */}
        <div className="flex gap-1 bg-slate-900/70 p-1 rounded-lg border border-slate-800">
          {FIELDS.map(f => (
            <button
              key={f.key}
              onClick={() => setField(f.key)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all ${
                field === f.key
                  ? 'bg-sky-500 text-white shadow-sm shadow-sky-500/30'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto -mx-2">
        <table className="w-full text-left border-collapse min-w-[550px]">
          <thead>
            <tr className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
              <th className="py-2 px-3 border-b border-slate-800">Vessel</th>
              {YEARS.map(y => (
                <th key={y} className="py-2 px-2 text-center border-b border-slate-800">{y}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {deepSeaVessels.map(vessel => (
              <tr key={vessel.vessel_id} className="group hover:bg-white/[0.02] transition-colors">
                <td className="py-2 px-3 border-b border-slate-800/50">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono font-bold text-sm text-sky-400">{vessel.vessel_id}</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-400 font-semibold">
                      {vessel.band}
                    </span>
                  </div>
                </td>
                {YEARS.map(year => {
                  const k = `${vessel.vessel_id}:${year}`;
                  const cur = curMap.get(k);
                  const base = baseMap.get(k);
                  const curVal = cur ? (cur as any)[field] : undefined;
                  const baseVal = base ? (base as any)[field] : undefined;
                  const flipped = base != null && cur != null && curVal !== baseVal;
                  const unstable = unstableKeys.has(`${vessel.vessel_id}:${year}:${field}`);

                  return (
                    <td key={year} className="py-1.5 px-1.5 border-b border-slate-800/50 text-center">
                      <div
                        className={`relative py-1.5 px-2 rounded-lg text-[11px] font-medium transition-all ${
                          unstable ? 'cell-unstable' :
                          flipped  ? 'cell-flipped' :
                          'bg-slate-900/50 border border-slate-800/60 text-slate-300'
                        }`}
                      >
                        <div className={flipped ? 'text-rose-300 font-bold' : ''}>{fmt(field, curVal)}</div>
                        {flipped && (
                          <div className="text-[9px] text-slate-500 line-through">{fmt(field, baseVal)}</div>
                        )}
                        {unstable && (
                          <span className="absolute top-0.5 right-0.5 text-[8px] text-amber-400" title="Unstable: GA seeds disagree">⚠️</span>
                        )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
