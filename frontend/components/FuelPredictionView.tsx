'use client';

import { PageHeader } from './PageHeader';
import React from 'react';
import { DemoData, FuelPredictorArmId } from '@/types/demo';
import { DotPlot, Legend, seriesColor } from '@/components/Charts';
import { pct } from '@/lib/format';

const ARM_LABELS: Record<FuelPredictorArmId, string> = {
  physics: 'Physics only',
  lightgbm: 'LightGBM',
  mlp: 'Neural net (MLP)',
  tensor_train: 'Tensor-train',
};

/** Fixed order, and therefore fixed colour per model — a model keeps its hue
 *  on every chart on this page regardless of how it ranks. */
const ARM_ORDER: FuelPredictorArmId[] = ['physics', 'lightgbm', 'mlp', 'tensor_train'];
const ARM_COLORS: Record<FuelPredictorArmId, string> = {
  physics: seriesColor(0),
  lightgbm: seriesColor(1),
  mlp: seriesColor(2),
  tensor_train: seriesColor(3),
};

/** What each model sees. Speed, vessel type and route/fuel are direct inputs;
 *  weather and hull condition vary in the training telemetry but are not
 *  observable at planning time, so the models learn their average effect. */
const INPUT_FEATURES = [
  { name: 'Speed', source: 'model input', role: 'Cruising speed in knots; fuel burn rises roughly with its cube.' },
  { name: 'Vessel type', source: 'model input', role: 'Class (containership, bulk carrier, feeder): hull, engine and DWT.' },
  { name: 'Load', source: 'via route', role: 'Fixed per route by its payload utilisation and laden share; enters through the route input.' },
  { name: 'Route, fuel, year', source: 'model input', role: 'Distance, fuel energy content and the year of operation.' },
  { name: 'Weather', source: 'in telemetry', role: 'Sea-state index in the telemetry; unknown years ahead, so learned as an average.' },
  { name: 'Hull fouling', source: 'in telemetry', role: 'Days since drydock in the telemetry; learned as an average effect.' },
];

export function FuelPredictionView({ data }: { data: DemoData }) {
  const benchmark = data.fuel_predictor_benchmark;

  if (!benchmark.available) {
    return (
      <div className="page-shell">
        <h1 className="mb-4 text-2xl font-bold text-[var(--text-primary)] sm:text-3xl">Fuel consumption prediction</h1>
        <div className="metric-card">
          <p className="text-sm text-[var(--text-secondary)]">Prediction benchmark not generated yet.</p>
        </div>
      </div>
    );
  }

  const { arms, best_arm: bestArm, per_fold_mape_percent: perFold, fold_vessel_ids: vessels } = benchmark;
  const improvement =
    (benchmark.physics_only_mape_percent - benchmark.best_arm_mape_percent) / benchmark.physics_only_mape_percent;

  const stability = (arm: FuelPredictorArmId) => arms[arm].worst_fold_mape_percent - arms[arm].best_fold_mape_percent;

  return (
    <div className="page-shell">
      <PageHeader category="Prediction" title="Better fuel estimates. Tested vessel by vessel.">
        <p className="mt-2 text-base leading-relaxed text-[var(--text-secondary)]">
          A physics power curve gets fuel burn mostly right but misses hull fouling and sea state. Four models
          learn that residual, each tested on a vessel it never saw in training.
        </p>
      </PageHeader>

      {/* Hero */}
      <section className="metric-card mb-5 border-[var(--success-soft-border)] bg-[var(--success-soft)] report-evidence" aria-label="Headline accuracy">
        <div className="flex flex-wrap items-center justify-between gap-6">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--text-secondary)]">
              Best model — {ARM_LABELS[bestArm]}
            </div>
            <div className="mt-2 font-mono text-4xl font-bold text-[var(--success)]">{pct(improvement, 0)}</div>
            <div className="mt-1 text-sm text-[var(--text-secondary)]">
              lower mean prediction error than physics-only estimation
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-4">
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--text-secondary)]">Mean error</dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--text-primary)]">
                {arms[bestArm].mean_mape_percent.toFixed(2)}%
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--text-secondary)]">Variance explained</dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--text-primary)]">
                {arms[bestArm].mean_r_squared.toFixed(3)}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--text-secondary)]">Samples</dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--text-primary)]">
                {benchmark.n_samples.toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--text-secondary)]">Held-out folds</dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--text-primary)]">{benchmark.n_folds}</dd>
            </div>
          </dl>
        </div>
      </section>

      {/* Input features */}
      <section className="metric-card mb-5" aria-label="Input features">
        <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--text-primary)]">Input features</h2>
        <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          {INPUT_FEATURES.map(feature => (
            <div key={feature.name} className="rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-3">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-semibold text-[var(--text-primary)]">{feature.name}</span>
                <span className={`text-xs ${feature.source === 'model input' ? 'text-[var(--success)]' : 'text-[var(--text-tertiary)]'}`}>
                  {feature.source}
                </span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">{feature.role}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Per-vessel dot plot */}
      <section className="metric-card mb-5" aria-label="Per-vessel prediction error">
        <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--text-primary)]">
          Error on every held-out vessel
        </h2>
        <p className="mb-5 mt-1 max-w-3xl text-sm leading-relaxed text-[var(--text-secondary)]">
          One row per held-out vessel. A dependable model stays low on <em>every</em> ship, not just on average.
        </p>
        <DotPlot
          categories={vessels}
          series={ARM_ORDER.map(arm => ({
            key: arm,
            label: ARM_LABELS[arm],
            color: ARM_COLORS[arm],
            values: perFold[arm],
          }))}
          xLabel="Mean absolute percentage error on the held-out vessel (lower is better)"
          formatValue={value => `${value.toFixed(2)}%`}
        />
        <Legend items={ARM_ORDER.map(arm => ({ label: ARM_LABELS[arm], color: ARM_COLORS[arm] }))} />
      </section>

      {/* Comparison table */}
      <section className="mb-5 overflow-hidden rounded-xl border border-[var(--border)] shadow-sm" aria-label="Model comparison">
        <div className="border-b border-[var(--border)] bg-[var(--surface-sunken)] px-4 py-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--text-secondary)]">Model comparison</h2>
          <p className="mt-1 text-sm leading-relaxed text-[var(--text-secondary)]">
            Averaged over {benchmark.n_folds} leave-one-vessel-out folds. Worst fold matters most to an operator.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="decision-table">
            <thead>
              <tr>
                <th scope="col">Model</th>
                <th scope="col" className="text-right">Mean error</th>
                <th scope="col" className="text-right">Best fold</th>
                <th scope="col" className="text-right">Worst fold</th>
                <th scope="col" className="text-right">Spread</th>
                <th scope="col" className="text-right">R²</th>
                <th scope="col" className="text-right">Fit time</th>
              </tr>
            </thead>
            <tbody>
              {ARM_ORDER.map(arm => {
                const result = arms[arm];
                const isBest = arm === bestArm;
                return (
                  <tr key={arm}>
                    <th scope="row" className="text-left">
                      <span className="inline-flex items-center gap-2">
                        <span className="inline-block h-2.5 w-2.5 rounded-[2px]" style={{ background: ARM_COLORS[arm] }} />
                        <span className={isBest ? 'font-semibold text-[var(--text-primary)]' : 'text-[var(--text-secondary)]'}>
                          {ARM_LABELS[arm]}
                        </span>
                      </span>
                    </th>
                    <td className={`text-right font-mono ${isBest ? 'font-bold text-[var(--success)]' : ''}`}>
                      {result.mean_mape_percent.toFixed(2)}%
                    </td>
                    <td className="text-right font-mono">{result.best_fold_mape_percent.toFixed(2)}%</td>
                    <td className="text-right font-mono">{result.worst_fold_mape_percent.toFixed(2)}%</td>
                    <td className="text-right font-mono">{stability(arm).toFixed(2)} pp</td>
                    <td className="text-right font-mono">{result.mean_r_squared.toFixed(3)}</td>
                    <td className="text-right font-mono">{result.fit_seconds_total.toFixed(2)}s</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Findings */}
      <ul className="metric-card space-y-2 text-sm leading-relaxed text-[var(--text-secondary)]" aria-label="Findings">
        <li>
          <strong className="text-[var(--text-primary)]">Tensor-train (quantum-inspired):</strong> compresses the
          residual table over class, route, fuel and speed via SVD. {arms.tensor_train.mean_mape_percent.toFixed(2)}% error
          against LightGBM&apos;s {arms.lightgbm.mean_mape_percent.toFixed(2)}%, best single fold
          ({arms.tensor_train.best_fold_mape_percent.toFixed(2)}%), fits in {arms.tensor_train.fit_seconds_total.toFixed(2)}s.
        </li>
        <li>
          <strong className="text-[var(--text-primary)]">Neural net rejected:</strong> {arms.mlp.mean_mape_percent.toFixed(2)}% mean
          but {arms.mlp.worst_fold_mape_percent.toFixed(2)}% on its worst vessel, too unreliable to price one ship&apos;s
          compliance.
        </li>
      </ul>

      <p className="mt-5 font-mono text-xs text-[var(--text-tertiary)]">
        Leave-one-vessel-out cross-validation · {benchmark.n_samples.toLocaleString()} samples ·{' '}
        {benchmark.samples_per_vessel_year} per vessel-year · deployed model:{' '}
        {ARM_LABELS[benchmark.demo_built_with_predictor as FuelPredictorArmId] ?? benchmark.demo_built_with_predictor} ·
        trained and tested on synthetic telemetry
      </p>
    </div>
  );
}
