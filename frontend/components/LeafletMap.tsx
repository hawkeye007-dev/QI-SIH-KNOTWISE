'use client';

import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { RoutesGeo, VesselYearGene, FleetVessel } from '@/types/demo';

const vesselIcon = (id: string, flipped: boolean) => {
  return L.divIcon({
    html: `<div style="
      width:30px;height:30px;background:${flipped ? '#ffffff' : '#121212'};
      border:${flipped ? '2px solid #ffffff' : '1.5px solid #666666'};
      border-radius:50%;display:flex;align-items:center;justify-content:center;
      color:${flipped ? '#000000' : '#ffffff'};font-family:monospace;font-weight:700;font-size:11px;
      box-shadow: ${flipped ? '0 0 10px rgba(255,255,255,0.7)' : '0 2px 6px rgba(0,0,0,0.8)'};
      transition: all 0.2s ease;
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
    <div className="relative w-full h-[460px] border border-neutral-800 rounded-xl overflow-hidden bg-neutral-950 shadow-inner">
      <MapContainer center={[18, 60]} zoom={3} style={{ width: '100%', height: '100%' }} zoomControl={true}>
        {/* Standard OpenStreetMap tiles, no API key -- inverted via CSS
            (.leaflet-tile in globals.css) to match the dark theme. */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {Object.entries(routesGeo.routes).map(([id, r]) => (
          <Polyline key={id} positions={r.waypoints} pathOptions={{
            color: '#666666', weight: 2, opacity: 0.7, dashArray: '5, 5',
          }} />
        ))}
        {vessels.map(v => {
          const { pos, route, flipped } = getPos(v.vessel_id);
          const gene = curMap.get(`${v.vessel_id}:2028`);
          return (
            <Marker key={v.vessel_id} position={pos} icon={vesselIcon(v.vessel_id, flipped)}>
              <Popup>
                <div style={{ fontSize: 11, fontFamily: 'monospace', padding: '4px 6px', color: '#e5e5e5' }}>
                  <div style={{ fontWeight: 'bold', fontSize: 12, borderBottom: '1px solid #333', paddingBottom: 2, marginBottom: 4 }}>
                    Vessel {v.vessel_id} <span style={{ opacity: 0.6 }}>({v.band})</span>
                    {flipped && <span style={{ background: '#fff', color: '#000', padding: '1px 4px', borderRadius: 3, marginLeft: 6, fontSize: 9 }}>REALLOCATED</span>}
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
