'use client';

import React from 'react';
import dynamic from 'next/dynamic';
import { RoutesGeo, VesselYearGene, FleetVessel } from '@/types/demo';

const LeafletMap = dynamic(() => import('./LeafletMap'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full min-h-[420px] rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)] flex flex-col items-center justify-center text-[var(--text-tertiary)]">
      <div className="animate-spin w-8 h-8 border-2 border-[var(--border-strong)] border-t-[var(--text-primary)] rounded-full mb-3" />
      <span className="text-xs font-mono">Loading Map…</span>
    </div>
  ),
});

interface Props {
  routesGeo: RoutesGeo;
  currentConfig: VesselYearGene[];
  baselineConfig: VesselYearGene[];
  vessels: FleetVessel[];
}

export const MapView: React.FC<Props> = (props) => <LeafletMap {...props} />;
