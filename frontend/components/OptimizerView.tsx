'use client';

import { PageHeader } from './PageHeader';
import React from 'react';
import { AtomIcon, CheckCircleIcon, TargetIcon } from '@phosphor-icons/react';
import { AblationArm, DemoData } from '@/types/demo';
import { useAtlas } from '@/lib/AtlasContext';
import { GainBarChart, Legend, seriesColor } from '@/components/Charts';
import { pairedScaleResults, scaleAdvantageSummary } from '@/lib/planAnalytics';
import { pct, usdM } from '@/lib/format';

const QIEA_COLOR = seriesColor(0);

/** Paired range bars for one ablation stage. Both arms share a single scale,
 *  so "these two distributions do not overlap" is read off the geometry
 *  rather than asserted in prose — that contrast is the finding. */
const AblationStage: React.FC<{
  title: string;
  caption: string;
  arms: { uniform_init: AblationArm; mean_field_init: AblationArm };
  improvementFraction: number;
}> = ({ title, caption, arms, improvementFraction }) => {
  const all = [arms.uniform_init, arms.mean_field_init];
  const lo = Math.min(...all.map(arm => arm.best_total_usd));
  const hi = Math.max(...all.map(arm => arm.worst_total_usd));
  const span = hi - lo || 1;
  const position = (value: number) => 6 + ((value - lo) / span) * 88;

  const rows = [
    { label: 'Uniform start', arm: arms.uniform_init, accent: 'var(--text-tertiary)' },
    { label: 'Mean-field start', arm: arms.mean_field_init, accent: QIEA_COLOR },
  ];

  return (
    <div className="metric-card">
      <div className="mb-1 flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-bold uppercase tracking-wide text-[var(--text-primary)]">{title}</h3>
        <span className={`font-mono text-sm font-bold ${improvementFraction > 0.01 ? 'text-[var(--success)]' : 'text-[var(--text-tertiary)]'}`}>
          {improvementFraction > 0 ? '−' : '+'}{pct(Math.abs(improvementFraction), 2)} cost
        </span>
      </div>
      <p className="mb-5 text-sm leading-relaxed text-[var(--text-secondary)]">{caption}</p>
      <div className="space-y-6">
        {rows.map(({ label, arm, accent }) => (
          <div key={label}>
            <div className="mb-2 flex items-baseline justify-between">
              <span className="font-mono text-sm font-semibold" style={{ color: accent }}>{label}</span>
              <span className="font-mono text-xs text-[var(--text-tertiary)]">
                {arm.n_runs} runs · mean {usdM(arm.mean_total_usd)}
              </span>
            </div>
            <div className="relative h-8">
              <div className="absolute inset-x-0 top-3.5 h-px bg-[var(--border)]" />
              <div
                className="absolute top-3 h-2 rounded-full"
                style={{
                  left: `${position(arm.best_total_usd)}%`,
                  width: `${position(arm.worst_total_usd) - position(arm.best_total_usd)}%`,
                  backgroundColor: accent,
                  opacity: 0.32,
                }}
              />
              <div
                className="absolute top-2 h-4 w-0.5 rounded"
                style={{ left: `${position(arm.mean_total_usd)}%`, backgroundColor: accent }}
              />
              <span className="absolute top-[22px] -translate-x-1/2 font-mono text-xs text-[var(--text-tertiary)]" style={{ left: `${position(arm.best_total_usd)}%` }}>
                {usdM(arm.best_total_usd)}
              </span>
              <span className="absolute top-[22px] -translate-x-1/2 font-mono text-xs text-[var(--text-tertiary)]" style={{ left: `${position(arm.worst_total_usd)}%` }}>
                {usdM(arm.worst_total_usd)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export function OptimizerView({ data }: { data: DemoData }) {
  const { scaling, fairStartScaling, phase6, scaleRows, scaleSummary } = useAtlas();
  const benchmark = data.optimizer_benchmark;
  const fairRows = fairStartScaling ? pairedScaleResults(fairStartScaling) : [];
  const fairSummary = fairRows.length > 0 ? scaleAdvantageSummary(fairRows) : null;
  const largest = scaleRows[scaleRows.length - 1];

  return (
    <div className="page-shell">
      <PageHeader category="Engine" title="The advantage behind the algorithm.">
        <p className="mt-2 text-base leading-relaxed text-[var(--text-secondary)]">
          A classical genetic algorithm carries a population of concrete candidate plans. The quantum-inspired
          evolutionary algorithm carries a <em>probability distribution</em> over every decision instead — a
          qudit register per vessel-year field, rotated toward the best plans found so far. Both solvers run on
          ordinary hardware, over the same genome, constraints and objective, so the comparison below changes
          exactly one thing.
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
                lower total fleet cost than the classical genetic algorithm, at an identical compute budget —
                same population ({scaling.protocol.population_size}), same generations ({scaling.protocol.generations}),
                same final polish ({scaling.protocol.polish_max_sweeps} sweep), same random seed within every pair.
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
            Median cost advantage per fleet size, paired seed by seed. This is the property that matters for a
            real operator: the harder the search problem gets, the more the distributional representation is
            worth. At {largest?.vesselCount} vessels it is also no slower — {largest?.medianQieaSeconds.toFixed(0)}s
            against the genetic algorithm&apos;s {largest?.medianGaSeconds.toFixed(0)}s.
          </p>

          <GainBarChart
            rows={scaleRows.map(row => ({
              label: `${row.vesselCount} vessels`,
              sublabel: `${row.decisionSlots.toLocaleString()} slots`,
              value: -row.medianQieaMinusGaFraction,
            }))}
            formatValue={value => pct(value, 2)}
            color={QIEA_COLOR}
            ariaLabel="Median QIEA cost advantage over GA by fleet size"
          />
          <Legend
            items={[{ label: 'QIEA advantage over GA (median of paired runs)', color: QIEA_COLOR }]}
            note={`${scaling.protocol.seeds.length} seeds per fleet size`}
          />

          <div className="mt-5 overflow-x-auto">
            <table className="decision-table">
              <caption className="sr-only">Paired solver results by fleet size</caption>
              <thead>
                <tr>
                  <th scope="col">Fleet</th>
                  <th scope="col" className="text-right">Decision slots</th>
                  <th scope="col" className="text-right">GA median time</th>
                  <th scope="col" className="text-right">QIEA median time</th>
                  <th scope="col" className="text-right">Median cost gap</th>
                  <th scope="col" className="text-right">QIEA lower</th>
                  <th scope="col">All feasible</th>
                </tr>
              </thead>
              <tbody>
                {scaleRows.map(row => {
                  const summaryRows = scaling.summary.filter(entry => entry.vessel_count === row.vesselCount);
                  const feasible = summaryRows.every(entry => entry.all_runs_feasible);
                  return (
                    <tr key={row.vesselCount}>
                      <th scope="row" className="font-mono text-sm font-semibold text-[var(--text-primary)]">{row.vesselCount}</th>
                      <td className="text-right font-mono">{row.decisionSlots.toLocaleString()}</td>
                      <td className="text-right font-mono">{row.medianGaSeconds.toFixed(1)}s</td>
                      <td className="text-right font-mono">{row.medianQieaSeconds.toFixed(1)}s</td>
                      <td className="text-right font-mono font-semibold text-[var(--success)]">
                        −{pct(Math.abs(row.medianQieaMinusGaFraction), 2)}
                      </td>
                      <td className="text-right font-mono">{row.qieaLowerRuns}/{row.pairedRuns}</td>
                      <td className="font-mono text-[var(--success)]">
                        {feasible ? (
                          <span className="inline-flex items-center gap-1.5"><CheckCircleIcon size={14} weight="bold" /> Yes</span>
                        ) : 'No'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* ---------- Mechanism ---------- */}
      {benchmark.available && (
        <section className="metric-card mb-5" aria-label="Mechanism">
          <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--text-primary)]">
            Where the advantage comes from
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-[var(--text-secondary)]">
            The cost model already knows a great deal about each individual decision before any complete plan
            exists — what a given route costs a given vessel at a given speed on a given fuel. A population of
            fixed candidate plans has nowhere to put that knowledge and has to rediscover it by trial. A
            distribution per decision can absorb it directly, as a starting bias, and spend the whole search
            budget on the part that genuinely requires search: the couplings between vessels.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-3">
              <div className="text-xs uppercase tracking-wide text-[var(--text-tertiary)]">The object</div>
              <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-secondary)]">
                One probability vector per decision — route, speed band, fuel, shore power, pooling, borrowing —
                rather than one fixed value. A population of concrete plans cannot represent this.
              </p>
            </div>
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-3">
              <div className="text-xs uppercase tracking-wide text-[var(--text-tertiary)]">The prior</div>
              <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-secondary)]">
                Each register starts at the Boltzmann marginals of that vessel-year&apos;s own separable cost
                table — a mean-field product state seeded with everything the cost model already implies before
                a single plan is scored.
              </p>
            </div>
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-3">
              <div className="text-xs uppercase tracking-wide text-[var(--text-tertiary)]">The refinement</div>
              <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-secondary)]">
                The search then works against the coupled part no product state can express — FuelEU pooling and
                the fleet-wide cargo constraint — rotating registers toward an archive of the best plans found.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* ---------- Isolating the mechanism ---------- */}
      {benchmark.available && (
        <>
          <div className="mb-3 mt-7">
            <h2 className="text-lg font-bold text-[var(--text-primary)]">Isolating the mechanism</h2>
            <p className="mt-1 max-w-3xl text-sm leading-relaxed text-[var(--text-secondary)]">
              Turning the distributional prior off and everything else on measures what that one idea
              contributes on its own, at the {data.fleet.vessels.length}-vessel scale.
            </p>
          </div>
          <div className="grid gap-5 lg:grid-cols-2">
            <AblationStage
              title="Raw search, prior on vs. off"
              caption="The two cost distributions do not overlap: with the mean-field prior, the worst run beats the uniform prior's best run."
              arms={benchmark.search_attribution.raw_search_polish_disabled}
              improvementFraction={benchmark.search_attribution.raw_search_improvement_fraction}
            />
            {fairSummary && fairRows.length > 0 && (
              <div className="metric-card">
                <h3 className="text-sm font-bold uppercase tracking-wide text-[var(--text-primary)]">
                  Attribution check at fleet scale
                </h3>
                <p className="mt-1 text-sm leading-relaxed text-[var(--text-secondary)]">
                  Give both solvers the same informed starting point and switch the mean-field prior off, and the
                  two converge to a tie. That is the precise, defensible reading of the headline: the gain is
                  bought by the quantum-inspired initialization, not by a generic post-start search advantage.
                </p>
                <div className="mt-4 space-y-3">
                  {fairRows.map(row => (
                    <div key={row.vesselCount} className="flex items-baseline justify-between gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] px-3 py-2.5">
                      <span className="font-mono text-sm text-[var(--text-secondary)]">{row.vesselCount} vessels</span>
                      <span className="font-mono text-sm font-semibold text-[var(--text-primary)]">
                        {row.medianQieaMinusGaFraction < 0 ? '−' : '+'}{pct(Math.abs(row.medianQieaMinusGaFraction), 2)}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="mt-3 text-xs leading-relaxed text-[var(--text-tertiary)]">
                  Median paired difference with a shared coordinate-descent anchor before each run.
                </p>
              </div>
            )}
          </div>
        </>
      )}

      {/* ---------- Correctness ---------- */}
      {phase6 && (
        <section className="metric-card mt-5" aria-label="Correctness reference">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-[260px] flex-1">
              <div className="flex items-center gap-2 text-[var(--text-tertiary)]">
                <TargetIcon size={15} weight="bold" />
                <span className="text-xs font-semibold uppercase tracking-wide">Exact reference</span>
              </div>
              <h2 className="mt-2 text-sm font-bold text-[var(--text-primary)]">
                Both solvers hit the provable optimum
              </h2>
              <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-[var(--text-secondary)]">
                On a {phase6.exact_reference.decision_slots}-slot instance small enough to enumerate exhaustively, the
                true optimum is {usdM(phase6.exact_reference.exhaustive_optimum_usd, 3)}. Both the genetic algorithm and
                the quantum-inspired solver return it exactly — a correctness floor under everything above, not a
                heuristic that merely looks good on large instances nobody can check.
              </p>
            </div>
            <div className="flex gap-8">
              <div>
                <div className="text-xs uppercase tracking-wide text-[var(--text-tertiary)]">GA gap</div>
                <div className="mt-1 font-mono text-2xl font-bold text-[var(--success)]">${phase6.exact_reference.ga_gap_usd.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-[var(--text-tertiary)]">QIEA gap</div>
                <div className="mt-1 font-mono text-2xl font-bold text-[var(--success)]">${phase6.exact_reference.qiea_gap_usd.toFixed(2)}</div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ---------- Provenance ---------- */}
      {benchmark.available && (
        <section className="metric-card mt-5" aria-label="Protocol and provenance">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="tag font-mono">Protocol</span>
            {scaling && (
              <span className="font-mono text-xs text-[var(--text-tertiary)]">
                {scaling.protocol.seeds.length} seeds · population {scaling.protocol.population_size} ·{' '}
                {scaling.protocol.generations} generations · scenario {scaling.protocol.scenario ?? 'approved_text'}
              </span>
            )}
          </div>
          <p className="text-sm leading-relaxed text-[var(--text-secondary)]">
            Every plan shown elsewhere on this site was solved with{' '}
            <strong className="font-mono text-[var(--text-primary)]">{benchmark.demo_built_with_optimizer.toUpperCase()}</strong>,
            recorded in the generated data rather than inferred from this page. Fleet sizes above{' '}
            {data.fleet.vessels.length} vessels repeat the documented class mix with cargo demand scaled in
            proportion, so the constraint structure stays identical as the search space grows. Cost gaps are
            measured within matched seed pairs; timings are medians on one machine.
          </p>
        </section>
      )}
    </div>
  );
}
