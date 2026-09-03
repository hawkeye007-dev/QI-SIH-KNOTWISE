'use client';

import React, { useEffect, useState, useMemo, useRef } from 'react';
import { DemoData, VesselYearGene } from '@/types/demo';
import { ScenarioSlider } from '@/components/ScenarioSlider';
import { MapView } from '@/components/MapView';
import { MatrixModal } from '@/components/MatrixModal';
import { ExposureModal } from '@/components/ExposureModal';
import { CostCurveModal } from '@/components/CostCurveModal';
import { GuideModal } from '@/components/GuideModal';
import { QuantumModal } from '@/components/QuantumModal';
import { PredictorModal } from '@/components/PredictorModal';

export default function Home() {
  const [data, setData] = useState<DemoData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scenarioId, setScenarioId] = useState('approved_text');
  const [price, setPrice] = useState(175);

  // Modal Overlay States
  const [isMatrixOpen, setIsMatrixOpen] = useState(false);
  const [isExposureOpen, setIsExposureOpen] = useState(false);
  const [isCostCurveOpen, setIsCostCurveOpen] = useState(false);
  const [isGuideOpen, setIsGuideOpen] = useState(false);
  const [isQuantumOpen, setIsQuantumOpen] = useState(false);
  const [isPredictorOpen, setIsPredictorOpen] = useState(false);

  // Reallocation Notification Toast State
  const [notification, setNotification] = useState<string | null>(null);
  const prevPriceRef = useRef(price);
  const notificationTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Shared by the price-change toast and any manually-triggered one (e.g.
  // clicking a proposal with no computed price) so a new notification
  // always resets the dismiss timer instead of racing a previous one.
  const showNotification = (text: string, durationMs = 3500) => {
    if (notificationTimerRef.current) clearTimeout(notificationTimerRef.current);
    setNotification(text);
    notificationTimerRef.current = setTimeout(() => setNotification(null), durationMs);
  };

  useEffect(() => {
    fetch('/demo_data.json')
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d: DemoData) => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

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
  }, [gridPoints, price]);

  // What re-planning is worth at this price: the $0/t plan re-costed here
  // without ever being revised, minus this price's re-optimized plan
  // (sweep.compute_baseline_counterfactual). This is the comparison that
  // carries a direction -- bigger is better, always. Total cost against the
  // $0/t *baseline* does not: a carbon price costs money however well the
  // fleet is planned, so that difference measures the regulation, not the
  // optimizer, and colouring it good/bad was misleading.
  const counterfactual = useMemo(() => {
    const points = data?.sweep.baseline_counterfactual?.points ?? [];
    if (points.length === 0) return null;
    return points.reduce((p, c) =>
      Math.abs(c.price_usd_per_tco2e - price) < Math.abs(p.price_usd_per_tco2e - price) ? c : p
    );
  }, [data, price]);

  const currentConfig: VesselYearGene[] = closest?.configuration ?? [];
  const baselineConfig: VesselYearGene[] = gridPoints.length > 0 ? gridPoints[0].configuration : [];

  // Active flips count at current price
  const activeFlips = useMemo(() => {
    if (!data) return [];
    return data.sweep.switching_points.filter(
      sp => price >= sp.price_low_usd_per_tco2e && price <= sp.price_high_usd_per_tco2e
    );
  }, [data, price]);

  // Distinct vessels among those active flips (real, price-dependent -- not
  // a static count: this is 0 at $0/t when nothing has flipped yet, and 0
  // again above the highest price any switching point was found at, once
  // the plan has settled into its final configuration).
  const flippedVesselCount = useMemo(() => new Set(activeFlips.map(f => f.vessel_id)).size, [activeFlips]);
  const highestSwitchingPrice = useMemo(() => {
    const points = data?.sweep.switching_points ?? [];
    return points.length > 0 ? Math.max(...points.map(sp => sp.price_high_usd_per_tco2e)) : null;
  }, [data]);
  const planHasStabilized = highestSwitchingPrice !== null && price > highestSwitchingPrice;

  // Monitor price changes and trigger notification toast
  useEffect(() => {
    if (!data) return;
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

  if (loading) return (
    <div className="h-screen w-screen bg-black flex flex-col items-center justify-center text-neutral-400 font-mono text-xs">
      <div className="w-6 h-6 border border-white border-t-transparent rounded-full animate-spin mb-3" />
      <span>LOADING KNOTWISE COMPLIANCE ATLAS...</span>
    </div>
  );

  if (error || !data) return (
    <div className="h-screen w-screen bg-black flex items-center justify-center p-6">
      <div className="bg-neutral-950 border border-neutral-800 p-6 rounded-xl max-w-sm text-center">
        <div className="text-sm font-mono text-red-400 mb-2">DATA FILE NOT FOUND</div>
        <p className="text-xs text-neutral-400 mb-4 font-sans">
          Could not load demo_data.json.
        </p>
        <button onClick={() => location.reload()} className="px-4 py-1.5 bg-white text-black font-semibold text-xs rounded">
          Retry Connection
        </button>
      </div>
    </div>
  );

  const ps = data.exposure.plan_spread;
  const totalCostUsd = closest ? closest.total_usd : 0;
  const usdM = (v: number) => `$${(v / 1e6).toFixed(2)}M`;
  const predictorBenchmark = data.fuel_predictor_benchmark;
  const predictorImprovementPct =
    predictorBenchmark.available && predictorBenchmark.physics_only_mape_percent > 0
      ? ((predictorBenchmark.physics_only_mape_percent - predictorBenchmark.best_arm_mape_percent) /
          predictorBenchmark.physics_only_mape_percent) *
        100
      : 0;
  // Real, measured dollar gap between the quantum-inspired search and a
  // naive (uniform-prior) search at the same budget, before either is
  // refined -- the money version of the "Search Advantage" percentage
  // above, not a separate/different comparison.
  const optimizerBenchmark = data.optimizer_benchmark;
  const optimizerMoneySavedInr = optimizerBenchmark.available
    ? (optimizerBenchmark.search_attribution.raw_search_polish_disabled.uniform_init.mean_total_usd -
        optimizerBenchmark.search_attribution.raw_search_polish_disabled.mean_field_init.mean_total_usd) *
      data.exposure.fx.usd_to_inr_rate
    : 0;


  return (
    <div className="min-h-screen bg-black text-neutral-200 flex flex-col font-sans relative">
      {/* Notification Toast -- strategy reallocations on price change, or a
          "why is this N/A" explanation when a no-price proposal is clicked */}
      {notification && (
        <div className="fixed bottom-6 right-6 z-[1000] max-w-sm bg-neutral-900 border border-neutral-700 px-4 py-3 rounded-lg shadow-2xl flex items-start gap-3 animate-bounce">
          <span className="w-2 h-2 mt-1 rounded-full bg-white animate-ping shrink-0" />
          <span className="text-xs font-mono text-white font-medium leading-relaxed">{notification}</span>
        </div>
      )}

      {/* Top Header */}
      <header className="border-b border-neutral-800 bg-neutral-950 px-6 py-3 flex flex-wrap items-center justify-between gap-3 sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <span className="font-mono font-bold text-sm tracking-widest text-white">KNOTWISE</span>
          <span className="text-neutral-700">|</span>
          <span className="text-xs font-mono text-neutral-400">Fleet Regulatory Risk Atlas</span>
        </div>

        <div className="flex items-center gap-3">
          {/* Docs / Guide Button */}
          <button
            onClick={() => setIsGuideOpen(true)}
            className="px-3 py-1.5 bg-neutral-900 hover:bg-neutral-800 border border-neutral-700 hover:border-neutral-500 text-xs font-mono text-white rounded transition-all flex items-center gap-1.5"
          >
            <span>📖</span>
            <span>Docs / Platform Guide</span>
          </button>
          <button
            onClick={() => setIsQuantumOpen(true)}
            title="How the plan was solved — GA vs quantum-inspired QIEA"
            className="px-3 py-1.5 bg-neutral-900 hover:bg-neutral-800 border border-neutral-700 hover:border-emerald-700 text-xs font-mono text-white rounded transition-all flex items-center gap-1.5"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span>Solver: {data.metadata.optimizer.toUpperCase()}</span>
          </button>
          <button
            onClick={() => setIsPredictorOpen(true)}
            title="Fuel-consumption prediction accuracy"
            className="px-3 py-1.5 bg-neutral-900 hover:bg-neutral-800 border border-neutral-700 hover:border-emerald-700 text-xs font-mono text-white rounded transition-all flex items-center gap-1.5"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />
            <span>Fuel Prediction</span>
          </button>
          <span className="tag">IMO 4 Dec 2026 Vote</span>
        </div>
      </header>

      {/* Main Dashboard Content */}
      <main className="flex-1 p-4 sm:p-6 max-w-[1600px] w-full mx-auto space-y-4">
        {/* Scenario Slider */}
        <ScenarioSlider
          currentPrice={price}
          onPriceChange={setPrice}
          activeScenarioId={scenarioId}
          onScenarioSelect={setScenarioId}
          ticks={data.sweep.scenario_ticks}
          switchingPoints={data.sweep.switching_points}
          onNoPriceClick={(label, reason) => showNotification(`${label} has no price on this axis: ${reason}`, 6000)}
        />

        {/* Dashboard Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
          {/* Left Column: Interactive Leaflet Map */}
          <div className="lg:col-span-2">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-xs font-mono font-semibold uppercase text-white">
                Global Trade Lanes & Active Vessels
              </span>
              <span className="text-[11px] font-mono text-neutral-400">
                Interactive Map • Scroll/Buttons to Zoom
              </span>
            </div>
            <MapView
              routesGeo={data.routes_geo}
              currentConfig={currentConfig}
              baselineConfig={baselineConfig}
              vessels={data.fleet.vessels}
            />
          </div>

          {/* Right Column: Key Metrics & Modal Overlay Buttons */}
          <div className="lg:col-span-1 space-y-4">
            {/* Card 1: Regulatory Risk Spread */}
            <div className="metric-card">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-mono uppercase text-neutral-400 tracking-wider">
                  Cost Variance Across Regulations
                </span>
                <span className="tag font-mono">Financial Risk</span>
              </div>
              <div className="text-2xl font-mono font-bold text-white mt-1">
                ₹{(ps.spread_inr / 1e7).toFixed(1)} Crore
              </div>
              <div className="text-xs font-mono text-neutral-400 mt-0.5">
                ${(ps.spread_usd / 1e6).toFixed(2)}M USD Plan Cost Variance
              </div>
              <p className="text-[11px] text-neutral-400 mt-2 font-sans">
                ₹{(ps.spread_inr / 1e7).toFixed(1)} Cr of fleet cost rides on how the Dec 4 IMO vote lands
                ({ps.min_scenario_id} vs {ps.max_scenario_id}) — see exactly which decisions carry that bet.
              </p>
              <button
                onClick={() => setIsExposureOpen(true)}
                className="mt-3 w-full py-2 bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 hover:border-neutral-700 text-xs font-mono text-white rounded transition-all flex items-center justify-between px-3"
              >
                <span>View Exposure & Risk Atlas</span>
                <span>➔</span>
              </button>
            </div>

            {/* Card 2: Strategy Reallocations */}
            <div className="metric-card">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-mono uppercase text-neutral-400 tracking-wider">
                  Vessels Modifying Strategy
                </span>
                <span className="tag font-mono">{activeFlips.length} Reallocations</span>
              </div>
              <div className="text-2xl font-mono font-bold text-white mt-1">
                {flippedVesselCount} Vessel{flippedVesselCount === 1 ? '' : 's'} • at ${price}/t
              </div>
              <div className="text-xs text-neutral-400 mt-0.5 font-sans">
                {planHasStabilized
                  ? `Plan has fully stabilized above $${highestSwitchingPrice}/t — no further fuel, speed, route, or shore-power switch is worth making beyond this price.`
                  : 'Changes in fuel, speed, assigned routes, and shore power.'}
              </div>
              <button
                onClick={() => setIsMatrixOpen(true)}
                className="mt-3 w-full py-2 bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 hover:border-neutral-700 text-xs font-mono text-white rounded transition-all flex items-center justify-between px-3"
              >
                <span>Open Fleet Decision Matrix</span>
                <span>➔</span>
              </button>
            </div>

            {/* Card 3: Total Fleet Expenditure */}
            <div className="metric-card">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-mono uppercase text-neutral-400 tracking-wider">
                  Total Fleet Expenditure
                </span>
                <span className="tag font-mono">Current Carbon Price</span>
              </div>
              <div className="text-2xl font-mono font-bold text-white mt-1">
                ${(totalCostUsd / 1e6).toFixed(2)}M USD
              </div>
              {counterfactual && counterfactual.saving_usd > 0 ? (
                <div className="text-xs font-mono font-semibold mt-0.5 text-emerald-400">
                  ▼ {usdM(counterfactual.saving_usd)} saved by re-planning
                </div>
              ) : (
                <div className="text-xs font-mono font-semibold mt-0.5 text-neutral-500">
                  — no re-planning gain yet at this price
                </div>
              )}
              <div className="text-xs text-neutral-400 mt-0.5 font-sans">
                {counterfactual && counterfactual.saving_usd > 0
                  ? `Keeping the $0/t plan and simply paying the carbon price would cost ${usdM(
                      counterfactual.frozen_total_usd
                    )} at $${price}/t. Re-optimizing fuel, speed, routes and shore power brings it down to ${usdM(
                      counterfactual.optimized_total_usd
                    )}.`
                  : `At $${price}/t the carbon price is still too low to make any fuel, speed, route or shore-power switch pay for itself — the optimal plan is the same one you'd run at $0/t.`}
              </div>
              <button
                onClick={() => setIsCostCurveOpen(true)}
                className="mt-3 w-full py-2 bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 hover:border-neutral-700 text-xs font-mono text-white rounded transition-all flex items-center justify-between px-3"
              >
                <span>Open Sensitivity Curve</span>
                <span>➔</span>
              </button>
            </div>
          </div>
        </div>

        {/* Optimizer band -- the one place on this site that talks about how the
            plan was solved. Full-width rather than a 4th right-column card: the
            three cards already match the map's height. Every figure reads live
            from optimizer_benchmark, which build_demo_data.py embeds from
            scripts/benchmark_optimizers.py. */}
        {data.optimizer_benchmark.available && (
          <div className="metric-card">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex-1 min-w-[240px]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] font-mono uppercase text-neutral-400 tracking-wider">
                    Quantum-Inspired Optimizer
                  </span>
                  <span className="tag font-mono">{data.optimizer_benchmark.status}</span>
                </div>
                <p className="text-[11px] text-neutral-400 font-sans max-w-2xl leading-relaxed">
                  Each qudit register is seeded from the Boltzmann marginals of its own vessel-year cost table
                  instead of uniform — a distribution per decision, which a population of point-valued genomes
                  cannot represent. Measured below: what that buys in raw search, and how much of it survives
                  the classical polish.
                </p>
              </div>

              <div className="flex flex-wrap items-stretch gap-6">
                <div>
                  <div className="text-[10px] font-mono uppercase text-neutral-500 tracking-wider mb-1">
                    Raw search
                  </div>
                  <div className="text-xl font-mono font-bold text-emerald-400">
                    {data.optimizer_benchmark.search_attribution.raw_search_improvement_fraction > 0 ? '−' : '+'}
                    {Math.abs(
                      data.optimizer_benchmark.search_attribution.raw_search_improvement_fraction * 100
                    ).toFixed(1)}
                    %
                  </div>
                  <div className="text-[10px] font-mono text-neutral-500">cost, polish off</div>
                </div>
                <div>
                  <div className="text-[10px] font-mono uppercase text-neutral-500 tracking-wider mb-1">
                    Delivered
                  </div>
                  <div className="text-xl font-mono font-bold text-neutral-400">
                    {data.optimizer_benchmark.search_attribution.end_to_end_improvement_fraction > 0 ? '−' : '+'}
                    {Math.abs(
                      data.optimizer_benchmark.search_attribution.end_to_end_improvement_fraction * 100
                    ).toFixed(2)}
                    %
                  </div>
                  <div className="text-[10px] font-mono text-neutral-500">cost, polish on</div>
                </div>
                <div>
                  <div className="text-[10px] font-mono uppercase text-neutral-500 tracking-wider mb-1">
                    Shipped plan
                  </div>
                  <div className="text-xl font-mono font-bold text-white">
                    {data.optimizer_benchmark.demo_built_with_optimizer.toUpperCase()}
                  </div>
                  <div className="text-[10px] font-mono text-neutral-500">
                    QIEA {usdM(data.optimizer_benchmark.qiea.min_total_usd_across_grid)} vs GA{' '}
                    {usdM(data.optimizer_benchmark.ga.min_total_usd_across_grid)}
                  </div>
                </div>
                <button
                  onClick={() => setIsQuantumOpen(true)}
                  className="self-center px-4 py-2 bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 hover:border-neutral-700 text-xs font-mono text-white rounded transition-all flex items-center gap-2 whitespace-nowrap"
                >
                  <span>Open Solver Benchmark</span>
                  <span>➔</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Fuel-predictor band -- the one place on this site that talks about
            fuel-consumption PREDICTION (PS Objective 1) as distinct from
            fleet OPTIMIZATION. Every figure reads live from
            fuel_predictor_benchmark, which build_demo_data.py embeds from
            scripts/benchmark_fuel_predictor.py. */}
        {data.fuel_predictor_benchmark.available && (
          <div className="metric-card">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex-1 min-w-[240px]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] font-mono uppercase text-neutral-400 tracking-wider">
                    Fuel Consumption Prediction
                  </span>
                </div>
                <p className="text-[11px] text-neutral-400 font-sans max-w-2xl leading-relaxed">
                  Machine-learning and tensor-inspired models predict fuel burn more accurately than
                  physics-only estimation, validated across every vessel in the fleet.
                </p>
              </div>

              <div className="flex flex-wrap items-stretch gap-6">
                <div>
                  <div className="text-[10px] font-mono uppercase text-neutral-500 tracking-wider mb-1">
                    Accuracy Gain
                  </div>
                  <div className="text-xl font-mono font-bold text-emerald-400">
                    +{predictorImprovementPct.toFixed(0)}%
                  </div>
                  <div className="text-[10px] font-mono text-neutral-500">vs. physics-only</div>
                </div>
                <div>
                  <div className="text-[10px] font-mono uppercase text-neutral-500 tracking-wider mb-1">
                    Best Model
                  </div>
                  <div className="text-xl font-mono font-bold text-white">
                    {predictorBenchmark.available ? predictorBenchmark.best_arm.replace('_', '-').toUpperCase() : ''}
                  </div>
                  <div className="text-[10px] font-mono text-emerald-400 font-semibold">
                    {predictorBenchmark.available ? (100 - predictorBenchmark.best_arm_mape_percent).toFixed(1) : ''}% accurate
                  </div>
                </div>
                <button
                  onClick={() => setIsPredictorOpen(true)}
                  className="self-center px-4 py-2 bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 hover:border-neutral-700 text-xs font-mono text-white rounded transition-all flex items-center gap-2 whitespace-nowrap"
                >
                  <span>Open Prediction Benchmark</span>
                  <span>➔</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-neutral-900 bg-neutral-950 px-6 py-3 flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono text-neutral-500 mt-auto">
        <div>KNOTWISE REGULATORY ATLAS • GLOBAL MERCHANT FLEET</div>
        <div>PRECOMPUTED DETERMINISTIC DECISION TREE</div>
      </footer>

      {/* Modal Popup Overlays */}
      <MatrixModal
        isOpen={isMatrixOpen}
        onClose={() => setIsMatrixOpen(false)}
        currentConfig={currentConfig}
        baselineConfig={baselineConfig}
        unstableKeys={unstableKeys}
        vessels={data.fleet.vessels}
        currentPrice={price}
      />

      <ExposureModal
        isOpen={isExposureOpen}
        onClose={() => setIsExposureOpen(false)}
        exposure={data.exposure}
      />

      <CostCurveModal
        isOpen={isCostCurveOpen}
        onClose={() => setIsCostCurveOpen(false)}
        gridPoints={gridPoints}
        currentPrice={price}
        tier2PriceUsdPerTco2e={
          data.sweep.scenario_ticks.find(t => t.scenario_id === 'approved_text')?.high_usd_per_tco2e ?? null
        }
      />

      <QuantumModal
        isOpen={isQuantumOpen}
        onClose={() => setIsQuantumOpen(false)}
        benchmark={data.optimizer_benchmark}
      />

      <PredictorModal
        isOpen={isPredictorOpen}
        onClose={() => setIsPredictorOpen(false)}
        benchmark={data.fuel_predictor_benchmark}
      />

      <GuideModal
        isOpen={isGuideOpen}
        onClose={() => setIsGuideOpen(false)}
        data={data}
      />
    </div>
  );
}
