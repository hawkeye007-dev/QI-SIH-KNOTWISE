'use client';

import Link from 'next/link';
import { ArrowRightIcon, ArrowDownRightIcon } from '@phosphor-icons/react';
import { DataGate } from '@/components/DataGate';
import { PriceControl } from '@/components/PriceControl';
import { MapView } from '@/components/MapView';
import { OverviewFuelMix } from '@/components/OverviewFuelMix';
import { useAtlas } from '@/lib/AtlasContext';
import { DemoData } from '@/types/demo';
import { climateDelta, deepestCut, fuelMixByPrice } from '@/lib/planAnalytics';
import { inrCrore, ktCO2e, kTonnes, pct, signedPct, usdM } from '@/lib/format';
import styles from './overview.module.css';

function HomeContent({ data }: { data: DemoData }) {
  const { price, currentConfig, baselineConfig, closest, counterfactual, scaleSummary } = useAtlas();
  const cut = deepestCut(data);
  const baseline = data.sweep.grid_points.find(point => point.price_usd_per_tco2e === 0);
  const mix = fuelMixByPrice(data);
  const baselineMix = mix.find(point => point.price === 0);
  const deepestMix = cut ? mix.find(point => point.price === cut.point.price_usd_per_tco2e) : null;
  const delta = climateDelta(data, closest);
  const predictor = data.fuel_predictor_benchmark;

  return (
    <main className={styles.overview}>
      <div className={styles.masthead}><span>Fleet intelligence / Overview</span><span>SIH26138 · Egreen Quanta</span></div>
      <section className={styles.hero} aria-labelledby="overview-title">
        <header className={styles.intro}>
          <p className={styles.eyebrow}>Quantum-inspired green fleet optimization</p>
          <h1 id="overview-title">A cleaner fleet.<br />A calculated decision.</h1>
          <p className={styles.lead}>Choose the fuel, speed, route and shore power that move your fleet forward. Understand the cost of cutting emissions before committing to a plan.</p>
          <div className={styles.actions}>
            <Link href="/plans" className={styles.primary}>Compare fleet plans <ArrowRightIcon size={18} /></Link>
            <a href="#explore" className={styles.textLink}>Explore the results <ArrowDownRightIcon size={18} /></a>
          </div>
          <dl className={styles.scope}>
            <div><dt>Fleet</dt><dd>{data.fleet.vessels.length} vessels</dd></div>
            <div><dt>Planning horizon</dt><dd>2026–2030</dd></div>
            <div><dt>Regulatory coverage</dt><dd>4 regimes</dd></div>
          </dl>
        </header>
        <aside className={styles.result} aria-label="Best emissions result in the carbon-price sweep">
          <div className={styles.resultHeading}><span>Measured fleet outcome</span><span>Five-year total</span></div>
          {cut && baseline?.metrics && cut.point.metrics ? <>
            <div className={styles.resultNumber}>{signedPct(cut.deltaFraction)}<ArrowDownRightIcon size={38} weight="light" /></div>
            <h2>Lifecycle greenhouse gas emissions</h2>
            <p>{ktCO2e(Math.abs(cut.deltaTco2e))} less than the fleet plan at $0/t.</p>
            <div className={styles.comparison}>
              <div className={styles.barLabel}><span>Baseline / $0 per tonne</span><strong>{ktCO2e(baseline.metrics.lifecycle_emissions_tco2e)}</strong></div>
              <div className={styles.barTrack}><span style={{width: '100%'}} /></div>
              <div className={styles.barLabel}><span>Lowest emissions / ${cut.point.price_usd_per_tco2e} per tonne</span><strong>{ktCO2e(cut.point.metrics.lifecycle_emissions_tco2e)}</strong></div>
              <div className={styles.barTrack}><span className={styles.cleanBar} style={{width: `${cut.point.metrics.lifecycle_emissions_tco2e / baseline.metrics.lifecycle_emissions_tco2e * 100}%`}} /></div>
            </div>
            <Link href="/sensitivity" className={styles.resultLink}>Inspect the carbon-price sweep <ArrowRightIcon size={17} /></Link>
          </> : <p>Emissions comparison is unavailable in this dataset.</p>}
        </aside>
      </section>

      <section className={styles.proofStrip} aria-label="Supporting results">
        <Link href="/fuels"><span className={styles.eyebrow}>Fuel transition</span><strong>{baselineMix && deepestMix && baselineMix.totalSlots > 0 && deepestMix.totalSlots > 0 ? `${pct(baselineMix.lowCarbonSlots / baselineMix.totalSlots, 0)} → ${pct(deepestMix.lowCarbonSlots / deepestMix.totalSlots, 0)}` : 'Unavailable'}</strong><span>Low-carbon vessel-years, baseline to lowest-emissions plan <ArrowRightIcon size={16} /></span></Link>
        <Link href="/engine"><span className={styles.eyebrow}>Solver advantage</span><strong>{scaleSummary ? `${pct(scaleSummary.minGainFraction)}–${pct(scaleSummary.maxGainFraction)}` : 'Unavailable'}</strong><span>Lower cost than a classical genetic algorithm at matched compute <ArrowRightIcon size={16} /></span></Link>
        <Link href="/exposure"><span className={styles.eyebrow}>Regulatory exposure</span><strong>{inrCrore(data.exposure.plan_spread.spread_inr)}</strong><span>Fleet cost spread across regulatory scenarios <ArrowRightIcon size={16} /></span></Link>
      </section>

      <section id="explore" className={styles.explore} aria-labelledby="explore-title">
        <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>The decision in motion</p><h2 id="explore-title">What changes when carbon has a price?</h2></div><p>Explore {data.sweep.grid_points.length} precomputed fleet plans. Each price point reconsiders fuel, speed, routes and shore power.</p></div>
        <div className={styles.controls}><PriceControl /></div>
        <div className={styles.analysis}>
          <div className={styles.fuelChart}><div className={styles.chartHeading}><h3>The fleet’s fuel mix</h3><Link href="/fuels" className={styles.textLink}>Fuel analysis <ArrowRightIcon size={16} /></Link></div><p>Fuel choices at the selected price, compared with the $0 baseline.</p><OverviewFuelMix data={data} /></div>
          <aside className={styles.selected} aria-label="Selected plan outcome">
            <p className={styles.eyebrow}>Selected plan / ${closest?.price_usd_per_tco2e ?? price} per tCO₂e</p>
            {delta && closest ? <><h3>{ktCO2e(delta.emissionsTco2e)}</h3><p className={styles.delta}>{signedPct(delta.emissionsDeltaFraction)} emissions vs. the $0/t plan</p><dl><div><dt>Five-year fleet cost</dt><dd>{usdM(closest.total_usd)}</dd></div><div><dt>Low-carbon vessel-years</dt><dd>{pct(delta.lowCarbonShare, 0)}</dd></div><div><dt>Bunker mass</dt><dd>{kTonnes(delta.fuelTonnes)}</dd></div></dl>{delta.fuelDeltaFraction > 0.01 && <p className={styles.note}>Cleaner fuels can require more tonnes because their energy density is lower. Lifecycle emissions measure the climate outcome.</p>}</> : <p>Plan metrics are unavailable.</p>}
            {counterfactual && <div className={styles.saving}><span>Value of re-planning</span><strong>{usdM(Math.max(0, counterfactual.saving_usd))}</strong><p>Saved against keeping the $0/t plan and paying the carbon bill at ${counterfactual.price_usd_per_tco2e}/t.</p></div>}
            <Link href="/fleet-matrix" className={styles.textLink}>Inspect vessel decisions <ArrowRightIcon size={16} /></Link>
          </aside>
        </div>
      </section>

      <section className={styles.network} aria-labelledby="network-title">
        <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>From fleet to vessel</p><h2 id="network-title">Every decision has a route.</h2></div><p>Explore 2028 route assignments. Highlighted vessels have a different strategy from the $0/t plan. Positions are illustrative.</p></div>
        <MapView routesGeo={data.routes_geo} currentConfig={currentConfig} baselineConfig={baselineConfig} vessels={data.fleet.vessels} />
      </section>

      <section className={styles.method} aria-labelledby="method-title">
        <div className={styles.methodIntro}><p className={styles.eyebrow}>Behind the decisions</p><h2 id="method-title">Engineering you can interrogate.</h2><p>Predict fuel consumption. Search fleet-wide decisions. Evaluate each plan against IMO NZF, CII, FuelEU Maritime and EU ETS.</p><Link href="/guide" className={styles.textLink}>How to read the platform <ArrowRightIcon size={16} /></Link></div>
        <div className={styles.evidenceList}>
          <Link href="/prediction"><div><span className={styles.eyebrow}>Fuel consumption prediction</span><h3>{predictor.available ? `${predictor.best_arm_mape_percent.toFixed(2)}% mean prediction error` : 'Explore the prediction models'}</h3><p>Four models evaluated by holding out an entire vessel at a time. Each test ship is unseen during training.</p></div><ArrowRightIcon size={22} /></Link>
          <Link href="/engine"><div><span className={styles.eyebrow}>Quantum-inspired optimization</span><h3>{scaleSummary ? `Lower cost in ${scaleSummary.totalWins} of ${scaleSummary.totalRuns} paired runs` : 'Explore the solver benchmark'}</h3><p>{scaleSummary ? `Benchmarked on ${scaleSummary.smallestFleet}–${scaleSummary.largestFleet} vessels with matched population, generations and polish budget.` : 'Compare the quantum-inspired search with a classical genetic algorithm.'}</p></div><ArrowRightIcon size={22} /></Link>
        </div>
      </section>
      <div className={styles.closing}><p>See the trade-off. Choose the plan.</p><Link href="/plans" className={styles.primary}>Compare the three fleet plans <ArrowRightIcon size={18} /></Link></div>
    </main>
  );
}

export default function Home() {
  return <DataGate>{data => <HomeContent data={data} />}</DataGate>;
}
