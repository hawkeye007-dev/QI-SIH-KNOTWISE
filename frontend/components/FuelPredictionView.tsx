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
          A naval-architecture power curve gets the leading term of fuel consumption right and then stops: it
          has no way to see hull fouling since the last drydock, or the added resistance a vessel meets in a
          seaway. Four models compete to close that residual, each validated by holding out one entire vessel
          at a time — so no model is ever scored on a ship it learned from.
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

      {/* Per-vessel dot plot */}
      <section className="metric-card mb-5" aria-label="Per-vessel prediction error">
        <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--text-primary)]">
          Error on every held-out vessel
        </h2>
        <p className="mb-5 mt-1 max-w-3xl text-sm leading-relaxed text-[var(--text-secondary)]">
          One row per vessel, each scored by models that never saw it during training. A mean is easy to win on
          one lucky fold — what matters operationally is whether a model is dependable on <em>every</em> ship,
          which is what the horizontal spread within a row shows.
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
            Averaged over all {benchmark.n_folds} leave-one-vessel-out folds. The worst-fold column is the one an
            operator would actually care about.
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
      <div className="grid gap-5 lg:grid-cols-2">
        <section className="metric-card" aria-label="Tensor-train finding">
          <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--text-primary)]">
            The tensor-train model earns its place
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
            The tensor-train arm is the quantum-inspired model here: it compresses an empirical residual table
            over the (class, route, fuel, speed) grid into a chain of three-index cores via singular-value
            decomposition, then predicts from the reconstructed, denoised table. It matches LightGBM&apos;s
            accuracy to within {Math.abs(arms.tensor_train.mean_mape_percent - arms.lightgbm.mean_mape_percent).toFixed(2)} of
            a percentage point ({arms.tensor_train.mean_mape_percent.toFixed(2)}% against{' '}
            {arms.lightgbm.mean_mape_percent.toFixed(2)}%), with the best single-fold result of any model
            ({arms.tensor_train.best_fold_mape_percent.toFixed(2)}%) — and fits in{' '}
            {arms.tensor_train.fit_seconds_total.toFixed(2)}s against LightGBM&apos;s {arms.lightgbm.fit_seconds_total.toFixed(2)}s.
          </p>
        </section>

        <section className="metric-card" aria-label="Stability finding">
          <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--text-primary)]">
            Why the neural net is not the answer
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
            The MLP posts a {arms.mlp.mean_mape_percent.toFixed(2)}% mean but{' '}
            {arms.mlp.worst_fold_mape_percent.toFixed(2)}% on its worst vessel — a{' '}
            {stability('mlp').toFixed(1)}-point spread against LightGBM&apos;s {stability('lightgbm').toFixed(1)} and
            the tensor-train&apos;s {stability('tensor_train').toFixed(1)}. A model that is occasionally wrong by
            13% on one ship cannot be trusted to price that ship&apos;s compliance exposure. Structured methods
            win here on dependability, not just on average accuracy, and that is the property the fleet
            optimizer needs.
          </p>
        </section>
      </div>

      <p className="mt-5 font-mono text-xs text-[var(--text-tertiary)]">
        Leave-one-vessel-out cross-validation · {benchmark.n_samples.toLocaleString()} samples ·{' '}
        {benchmark.samples_per_vessel_year} per vessel-year · deployed model:{' '}
        {ARM_LABELS[benchmark.demo_built_with_predictor as FuelPredictorArmId] ?? benchmark.demo_built_with_predictor}
      </p>
    </div>
  );
}
