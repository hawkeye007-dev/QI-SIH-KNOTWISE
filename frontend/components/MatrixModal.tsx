'use client';

import React, { useState } from 'react';
import { VesselYearGene, FleetVessel } from '@/types/demo';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  currentConfig: VesselYearGene[];
  baselineConfig: VesselYearGene[];
  unstableKeys: Set<string>;
  vessels: FleetVessel[];
  currentPrice: number;
}

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
  isOpen, onClose, currentConfig, baselineConfig, unstableKeys, vessels, currentPrice
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
