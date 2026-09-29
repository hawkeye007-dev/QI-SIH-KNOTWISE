'use client';

import { PageHeader } from './PageHeader';
import { AtomIcon } from '@phosphor-icons/react';
import { DemoData, SearchAttribution } from '@/types/demo';
import { useAtlas } from '@/lib/AtlasContext';
import { GainBarChart, Legend, seriesColor } from '@/components/Charts';
import { pairedScaleResults } from '@/lib/planAnalytics';
import { pct, usdM } from '@/lib/format';
import { QuantumEncodingDiagram } from './QuantumEncodingDiagram';

const QIEA_COLOR = seriesColor(0);

/** What the quantum-inspired initialization contributes on its own: the
 *  same raw search with the mean-field prior on and off. */
function PriorAttributionCard({ attribution, vesselCount }: { attribution: SearchAttribution; vesselCount: number }) {
  const priorOn = attribution.raw_search_polish_disabled.mean_field_init;
  const priorOff = attribution.raw_search_polish_disabled.uniform_init;
  return (
    <div className="metric-card">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">Quantum-inspired start, on vs. off</h3>
      <div className="mt-2 font-mono text-2xl font-bold text-[var(--success)]">
        −{pct(Math.abs(attribution.raw_search_improvement_fraction), 2)}
      </div>
      <p className="mt-1 text-sm leading-relaxed text-[var(--text-secondary)]">
        Mean cost at {vesselCount} vessels ({usdM(priorOn.mean_total_usd)} vs. {usdM(priorOff.mean_total_usd)}).
        {priorOn.worst_total_usd < priorOff.best_total_usd && <> Its worst run beats the uniform start&apos;s best.</>}
      </p>
    </div>
  );
}

export function OptimizerView({ data }: { data: DemoData }) {
  const { scaling, fairStartScaling, phase6, scaleRows, scaleSummary } = useAtlas();
  const benchmark = data.optimizer_benchmark;
  const fairRows = fairStartScaling ? pairedScaleResults(fairStartScaling) : [];
  const attribution = benchmark.available ? benchmark.search_attribution : null;
  const largest = scaleRows[scaleRows.length - 1];
  const allFeasible = scaling?.summary.every(entry => entry.all_runs_feasible) ?? false;

  return (
    <div className="page-shell">
      <PageHeader category="Engine" title="The advantage behind the algorithm.">
        <p className="mt-2 text-base leading-relaxed text-[var(--text-secondary)]">
          A genetic algorithm keeps a population of fixed candidate plans. The quantum-inspired evolutionary
          algorithm (QIEA) keeps a <em>probability distribution</em> over every decision instead. Both run on
          ordinary hardware with the same constraints and objective.
        </p>
      </PageHeader>

      {/* ---------- Headline: scaling advantage ---------- */}
      {scaleSummary && scaling && (
        <section className="metric-card mb-5 border-[var(--border-strong)] report-evidence" aria-label="Scaling advantage">
          <div className="flex flex-wrap items-start justify-between gap-5">
            <div className="min-w-[260px] flex-1">
              <div className="flex items-center gap-2 text-[var(--text-tertiary)]">
                <AtomIcon size={15} weight="bold" />
                <span className="text-xs font-semibold uppercase tracking-wide">Headline result</span>
              </div>
              <div className="mt-3 font-mono text-4xl font-bold text-[var(--success)]">
                {pct(scaleSummary.minGainFraction)}–{pct(scaleSummary.maxGainFraction)}
              </div>
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-[var(--text-secondary)]">
                lower total fleet cost than a classical genetic algorithm at identical compute: same population,
                generations, polish and random seed in every pair.
              </p>
            </div>
            <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-3">
              <div>
                <dt className="text-xs uppercase tracking-wide text-[var(--text-tertiary)]">Paired runs won</dt>
                <dd className="mt-1 font-mono text-2xl font-bold text-[var(--success)]">
                  {scaleSummary.totalWins}/{scaleSummary.totalRuns}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-[var(--text-tertiary)]">Fleet range</dt>
                <dd className="mt-1 font-mono text-2xl font-bold text-[var(--text-primary)]">
                  {scaleSummary.smallestFleet}–{scaleSummary.largestFleet}
                </dd>
                <dd className="text-xs text-[var(--text-tertiary)]">vessels</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-[var(--text-tertiary)]">Largest search</dt>
                <dd className="mt-1 font-mono text-2xl font-bold text-[var(--text-primary)]">
                  {scaleSummary.largestSlots.toLocaleString()}
                </dd>
                <dd className="text-xs text-[var(--text-tertiary)]">decision slots</dd>
              </div>
            </dl>
          </div>
        </section>
      )}

      {/* ---------- The advantage grows with fleet size ---------- */}
      {scaleRows.length > 0 && scaling && (
        <section className="metric-card mb-5" aria-label="Advantage by fleet size">
          <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--text-primary)]">
            The margin widens as the fleet grows
          </h2>
          <p className="mb-5 mt-1 max-w-3xl text-sm leading-relaxed text-[var(--text-secondary)]">
            Median paired cost advantage. The harder the search, the larger the gain — and at{' '}
            {largest?.vesselCount} vessels QIEA takes {largest?.medianQieaSeconds.toFixed(0)}s against the genetic
            algorithm&apos;s {largest?.medianGaSeconds.toFixed(0)}s.
          </p>

          <GainBarChart
            rows={scaleRows.map(row => ({
              label: `${row.vesselCount} vessels`,
              sublabel: `${row.decisionSlots.toLocaleString()} slots · ${row.qieaLowerRuns}/${row.pairedRuns} won`,
              value: -row.medianQieaMinusGaFraction,
            }))}
            formatValue={value => pct(value, 2)}
            color={QIEA_COLOR}
            ariaLabel="Median QIEA cost advantage over GA by fleet size"
          />
          <Legend
            items={[{ label: 'QIEA advantage over GA (median of paired runs)', color: QIEA_COLOR }]}
            note={`${scaling.protocol.seeds.length} seeds per fleet size · ${allFeasible ? 'every run feasible' : 'some runs infeasible'}`}
          />

        </section>
      )}

      {/* ---------- Mechanism ---------- */}
      {benchmark.available && (
        <section className="metric-card mb-5" aria-label="Mechanism">
          <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--text-primary)]">
            Encoding and quantum update
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-[var(--text-secondary)]">
            Each vessel-year holds one probability register per decision: route, speed band, fuel, shore power,
            pooling and borrowing. Registers start from what the cost model already implies about each decision,
            then rotate toward the best plans found, so the search budget goes to the couplings between vessels:
            fleet-wide cargo demand and FuelEU pooling.
          </p>
          <QuantumEncodingDiagram />
        </section>
      )}

      {/* ---------- Validation ---------- */}
      <section className="mt-5" aria-label="Validation">
        <h2 className="mb-3 text-lg font-bold text-[var(--text-primary)]">Validation</h2>
        <div className="grid gap-5 lg:grid-cols-3">
          {attribution && <PriorAttributionCard attribution={attribution} vesselCount={data.fleet.vessels.length} />}
          {fairRows.length > 0 && (
            <div className="metric-card">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">Same start for both solvers</h3>
              <div className="mt-2 font-mono text-2xl font-bold text-[var(--text-primary)]">
                {fairRows.map(row => `${row.medianQieaMinusGaFraction < 0 ? '−' : '+'}${pct(Math.abs(row.medianQieaMinusGaFraction), 2)}`).join(' / ')}
              </div>
              <p className="mt-1 text-sm leading-relaxed text-[var(--text-secondary)]">
                At {fairRows.map(row => row.vesselCount).join(' and ')} vessels the two tie, so the gain comes from the
                quantum-inspired initialization.
              </p>
            </div>
          )}
          {phase6 && (
            <div className="metric-card">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">Exact optimum check</h3>
              <div className="mt-2 font-mono text-2xl font-bold text-[var(--success)]">
                ${phase6.exact_reference.ga_gap_usd.toFixed(2)} / ${phase6.exact_reference.qiea_gap_usd.toFixed(2)}
              </div>
              <p className="mt-1 text-sm leading-relaxed text-[var(--text-secondary)]">
                GA / QIEA gap to the brute-force optimum ({usdM(phase6.exact_reference.exhaustive_optimum_usd, 3)}) on a{' '}
                {phase6.exact_reference.decision_slots}-slot instance.
              </p>
            </div>
          )}
        </div>
      </section>

      {benchmark.available && scaling && (
        <p className="mt-5 font-mono text-xs text-[var(--text-tertiary)]">
          {scaling.protocol.seeds.length} seeds · population {scaling.protocol.population_size} ·{' '}
          {scaling.protocol.generations} generations · every plan on this site solved with{' '}
          {benchmark.demo_built_with_optimizer.toUpperCase()} · larger fleets repeat the {data.fleet.vessels.length}-vessel
          class mix with cargo scaled in proportion · timings are medians on one machine
        </p>
      )}
    </div>
  );
}
