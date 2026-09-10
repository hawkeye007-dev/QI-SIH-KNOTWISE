'use client';

import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { RoutesGeo, VesselYearGene, FleetVessel } from '@/types/demo';

// Marker colors stay fixed regardless of site theme -- the map tiles
// underneath are standard light OSM raster tiles in both themes (a themed
// tile set needs a keyed provider), so pins are tuned to read clearly
// against that light basemap either way.
const vesselIcon = (id: string, flipped: boolean) => {
  return L.divIcon({
    html: `<div style="
      width:30px;height:30px;background:${flipped ? '#4f46e5' : '#111827'};
      border:2px solid #ffffff;
      border-radius:50%;display:flex;align-items:center;justify-content:center;
      color:#ffffff;font-family:var(--font-sans);font-weight:700;font-size:11px;
      box-shadow: ${flipped ? '0 0 0 3px rgba(79,70,229,0.25)' : '0 2px 6px rgba(16,24,40,0.35)'};
      transition: transform 0.2s ease;
    ">${id}</div>`,
    className: '',
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });
};

interface Props {
  routesGeo: RoutesGeo;
  currentConfig: VesselYearGene[];
  baselineConfig: VesselYearGene[];
  vessels: FleetVessel[];
}

const LeafletMap: React.FC<Props> = ({ routesGeo, currentConfig, baselineConfig, vessels }) => {
  const [day, setDay] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setDay(d => (d + 1) % 360), 800);
    return () => clearInterval(t);
  }, []);

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

  const getPos = (vid: string): { pos: [number, number]; route: string; flipped: boolean } => {
    const k = `${vid}:2028`;
    const cur = curMap.get(k);
    const base = baseMap.get(k);
    const routeId = cur?.route_id || 'india_northeurope';
    const wps = routesGeo.routes[routeId]?.waypoints || [[18.95, 72.85]];
    const flipped = !!(cur && base && (
      cur.fuel_id !== base.fuel_id || cur.route_id !== base.route_id ||
      cur.speed_band_index !== base.speed_band_index || cur.shore_power !== base.shore_power
    ));
    if (wps.length < 2) return { pos: wps[0] as [number, number], route: routeId, flipped };
    const seg = wps.length - 1;
    const prog = (day % 30) / 30;
    const idx = Math.min(Math.floor(prog * seg), seg - 1);
    const t = prog * seg - idx;
    return {
      pos: [wps[idx][0] + (wps[idx+1][0] - wps[idx][0]) * t, wps[idx][1] + (wps[idx+1][1] - wps[idx][1]) * t],
      route: routesGeo.routes[routeId]?.name || routeId,
      flipped,
    };
  };

  return (
    <div className="relative w-full h-full min-h-[420px] border border-[var(--border)] rounded-xl overflow-hidden bg-[var(--surface-sunken)] shadow-sm">
      {/* Fill this (position:relative) root by insets rather than height:100%.
          A percentage height only resolves against a parent with a *definite*
          height; when an ancestor sets min-height alone the percentage
          collapses to zero and Leaflet initialises into a 0px box. */}
      <MapContainer center={[18, 60]} zoom={3} style={{ position: 'absolute', inset: 0 }} zoomControl={true}>
        {/* Standard OpenStreetMap tiles, no API key -- the map's own UI
            chrome (popups/controls) themes via globals.css, tile imagery
            stays the standard light basemap in both site themes. */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {Object.entries(routesGeo.routes).map(([id, r]) => (
          <Polyline key={id} positions={r.waypoints} pathOptions={{
            color: '#9ca3af', weight: 2, opacity: 0.8, dashArray: '5, 5',
          }} />
        ))}
        {vessels.map(v => {
          const { pos, route, flipped } = getPos(v.vessel_id);
          const gene = curMap.get(`${v.vessel_id}:2028`);
          return (
            <Marker key={v.vessel_id} position={pos} icon={vesselIcon(v.vessel_id, flipped)}>
              <Popup>
                <div className="text-xs font-mono px-1.5 py-1 text-[var(--text-primary)]">
                  <div className="font-bold text-[13px] border-b border-[var(--border)] pb-1 mb-1 flex items-center">
                    Vessel {v.vessel_id} <span className="opacity-60 ml-1">({v.band})</span>
                    {flipped && <span className="bg-[var(--accent)] text-white px-1.5 py-0.5 rounded ml-1.5 text-[10px]">REALLOCATED</span>}
                  </div>
                  <div>Assigned Route: <strong>{route}</strong></div>
                  <div>Fuel Choice: <strong>{gene?.fuel_id || '—'}</strong></div>
                  <div>Speed Profile: <strong>Band {gene?.speed_band_index ?? '—'}</strong></div>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
};

export default LeafletMap;
