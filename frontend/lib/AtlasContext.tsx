'use client';

import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { DemoData, VesselYearGene, GridPointResult, BaselineCounterfactualPoint, SwitchingPoint, ScalingBenchmark, Phase6Benchmark } from '@/types/demo';
import { PairedScaleResult, pairedScaleResults, scaleAdvantageSummary } from '@/lib/planAnalytics';

export interface CargoDemandRow {
  routeId: string;
  requiredTonneNm: number;
  minAssignedTonneNm: number;
  yearsShort: number[];
}

interface AtlasState {
  data: DemoData | null;
  loading: boolean;
  error: string | null;

  /** Solver benchmarks live beside demo_data.json rather than inside it, so
   *  they are fetched once here and shared: the Overview headline and the
   *  Engine page must never quote two different numbers for the same run. */
  scaling: ScalingBenchmark | null;
  fairStartScaling: ScalingBenchmark | null;
  phase6: Phase6Benchmark | null;
  scaleRows: PairedScaleResult[];
  scaleSummary: ReturnType<typeof scaleAdvantageSummary> | null;

  price: number;
  setPrice: (p: number) => void;
  scenarioId: string;
  setScenarioId: (id: string) => void;

  notification: string | null;
  showNotification: (text: string, durationMs?: number) => void;

  // Derived, price-dependent plan state -- computed once here so every page
  // reads the same numbers instead of re-deriving them.
  gridPoints: GridPointResult[];
  closest: GridPointResult | null;
  counterfactual: BaselineCounterfactualPoint | null;
  currentConfig: VesselYearGene[];
  baselineConfig: VesselYearGene[];
  cargoDemand: CargoDemandRow[];
  unstableKeys: Set<string>;
  activeFlips: SwitchingPoint[];
  flippedVesselCount: number;
  highestSwitchingPrice: number | null;
  planHasStabilized: boolean;
}

const AtlasContext = createContext<AtlasState | null>(null);

const PRICE_STORAGE_KEY = 'knotwise:price';
const SCENARIO_STORAGE_KEY = 'knotwise:scenarioId';

export const AtlasProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [data, setData] = useState<DemoData | null>(null);
  const [scaling, setScaling] = useState<ScalingBenchmark | null>(null);
  const [fairStartScaling, setFairStartScaling] = useState<ScalingBenchmark | null>(null);
  const [phase6, setPhase6] = useState<Phase6Benchmark | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [price, setPrice] = useState(175);
  const [scenarioId, setScenarioId] = useState('approved_text');

  const [notification, setNotification] = useState<string | null>(null);
  const prevPriceRef = useRef(price);
  const notificationTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hydratedRef = useRef(false);

  const showNotification = (text: string, durationMs = 3500) => {
    if (notificationTimerRef.current) clearTimeout(notificationTimerRef.current);
    setNotification(text);
    notificationTimerRef.current = setTimeout(() => setNotification(null), durationMs);
  };

  // Restore price/scenario from a previous visit (localStorage) so a
  // navigation-across-pages OR a hard reload keeps the same selection.
  useEffect(() => {
    try {
      const storedPrice = window.localStorage.getItem(PRICE_STORAGE_KEY);
      const storedScenario = window.localStorage.getItem(SCENARIO_STORAGE_KEY);
      if (storedPrice != null && !Number.isNaN(Number(storedPrice))) {
        setPrice(Number(storedPrice));
        prevPriceRef.current = Number(storedPrice);
      }
      if (storedScenario) setScenarioId(storedScenario);
    } catch {
      // localStorage unavailable (private mode, etc.) -- fall back silently.
    }
    hydratedRef.current = true;
  }, []);

  useEffect(() => {
    if (!hydratedRef.current) return;
    try {
      window.localStorage.setItem(PRICE_STORAGE_KEY, String(price));
      window.localStorage.setItem(SCENARIO_STORAGE_KEY, scenarioId);
    } catch {
      // ignore
    }
  }, [price, scenarioId]);

  useEffect(() => {
    fetch('/demo_data.json')
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d: DemoData) => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  // Benchmark artifacts are optional: a build without them renders every
  // page except the solver panels, rather than failing the whole app.
  useEffect(() => {
    const load = <T,>(path: string, set: (value: T | null) => void) =>
      fetch(path)
        .then(response => (response.ok ? response.json() : null))
        .then((value: T | null) => set(value))
        .catch(() => set(null));
    load<ScalingBenchmark>('/optimizer_scaling_benchmark.json', setScaling);
    load<ScalingBenchmark>('/optimizer_scaling_fair_start.json', setFairStartScaling);
    load<Phase6Benchmark>('/optimizer_phase6_benchmark.json', setPhase6);
  }, []);

  const scaleRows = useMemo(() => (scaling ? pairedScaleResults(scaling) : []), [scaling]);
  const scaleSummary = useMemo(() => (scaleRows.length > 0 ? scaleAdvantageSummary(scaleRows) : null), [scaleRows]);

  const unstableKeys = useMemo(() => {
    const s = new Set<string>();
    if (data) {
      data.exposure.unstable_decisions?.decisions?.forEach(d => {
        s.add(`${d.vessel_id}:${d.year}:${d.decision}`);
      });
    }
    return s;
  }, [data]);

  const gridPoints = data?.sweep.grid_points ?? [];

  const closest = useMemo(() => {
    if (gridPoints.length === 0) return null;
    return gridPoints.reduce((p, c) =>
      Math.abs(c.price_usd_per_tco2e - price) < Math.abs(p.price_usd_per_tco2e - price) ? c : p
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, price]);

  // What re-planning is worth at this price: the $0/t plan re-costed here
  // without ever being revised, minus this price's re-optimized plan.
  const counterfactual = useMemo(() => {
    const points = data?.sweep.baseline_counterfactual?.points ?? [];
    if (points.length === 0) return null;
    return points.reduce((p, c) =>
      Math.abs(c.price_usd_per_tco2e - price) < Math.abs(p.price_usd_per_tco2e - price) ? c : p
    );
  }, [data, price]);

  const currentConfig: VesselYearGene[] = closest?.configuration ?? [];
  const baselineConfig: VesselYearGene[] = gridPoints.length > 0 ? gridPoints[0].configuration : [];

  // The Python optimizer is the sole owner of cargo throughput. Do not
  // reconstruct it here from vessel DWT: payload utilization and annual
  // transit distance are part of the operating model.
  const cargoDemand = useMemo(() => {
    const rows = closest?.metrics?.cargo.rows;
    if (!rows) return [];
    const byRoute = new Map<string, typeof rows>();
    rows.forEach(row => byRoute.set(row.route_id, [...(byRoute.get(row.route_id) ?? []), row]));
    return [...byRoute.entries()].map(([routeId, routeRows]) => ({
      routeId,
      requiredTonneNm: routeRows[0].required_tonne_nm,
      minAssignedTonneNm: Math.min(...routeRows.map(row => row.assigned_tonne_nm)),
      yearsShort: routeRows.filter(row => row.status !== 'FEASIBLE').map(row => row.year),
    }));
  }, [closest]);

  const activeFlips = useMemo(() => {
    if (!data) return [];
    return data.sweep.switching_points.filter(
      sp => price >= sp.price_low_usd_per_tco2e && price <= sp.price_high_usd_per_tco2e
    );
  }, [data, price]);

  const flippedVesselCount = useMemo(() => new Set(activeFlips.map(f => f.vessel_id)).size, [activeFlips]);

  const highestSwitchingPrice = useMemo(() => {
    const points = data?.sweep.switching_points ?? [];
    return points.length > 0 ? Math.max(...points.map(sp => sp.price_high_usd_per_tco2e)) : null;
  }, [data]);

  const planHasStabilized = highestSwitchingPrice !== null && price > highestSwitchingPrice;

  // Price-change toast, mirrored from the original single-page app.
  useEffect(() => {
    if (!data || !hydratedRef.current) return;
    if (prevPriceRef.current !== price) {
      prevPriceRef.current = price;
      if (activeFlips.length > 0) {
        showNotification(`Strategy Reallocation: ${activeFlips.length} vessel elections updated at $${price}/tCO₂e`);
      } else {
        showNotification(`Strategy Baseline: Fleet plans stable at $${price}/tCO₂e`);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [price, data, activeFlips]);

  const value: AtlasState = {
    data, loading, error,
    scaling, fairStartScaling, phase6, scaleRows, scaleSummary,
    price, setPrice, scenarioId, setScenarioId,
    notification, showNotification,
    gridPoints, closest, counterfactual,
    currentConfig, baselineConfig, cargoDemand,
    unstableKeys, activeFlips, flippedVesselCount,
    highestSwitchingPrice, planHasStabilized,
  };

  return <AtlasContext.Provider value={value}>{children}</AtlasContext.Provider>;
};

export function useAtlas(): AtlasState {
  const ctx = useContext(AtlasContext);
  if (!ctx) throw new Error('useAtlas must be used within an AtlasProvider');
  return ctx;
}
