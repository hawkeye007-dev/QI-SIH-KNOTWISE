'use client';

import React from 'react';
import dynamic from 'next/dynamic';
import { RoutesGeo, VesselYearGene, FleetVessel } from '@/types/demo';

const LeafletMap = dynamic(() => import('./LeafletMap'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full min-h-[420px] rounded-2xl glass-panel flex flex-col items-center justify-center text-slate-500">
      <div className="animate-spin w-8 h-8 border-2 border-sky-400 border-t-transparent rounded-full mb-3" />
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
