'use client';

import React from 'react';
import { FuelPredictorArmId, FuelPredictorArmResult, FuelPredictorBenchmark } from '@/types/demo';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  benchmark: FuelPredictorBenchmark;
}

const ARM_LABELS: Record<FuelPredictorArmId, string> = {
  physics: 'Physics-only',
  lightgbm: 'LightGBM',
  mlp: 'MLP',
  tensor_train: 'Tensor-Train',
};
const ARM_ORDER: FuelPredictorArmId[] = ['physics', 'lightgbm', 'mlp', 'tensor_train'];

export const PredictorModal: React.FC<Props> = ({ isOpen, onClose, benchmark }) => {
  if (!isOpen) return null;

  const header = (
    <div className="flex items-start justify-between border-b border-neutral-800 pb-4 mb-5 gap-4">
      <div>
        <h2 className="text-base font-semibold text-white uppercase tracking-wider font-mono">
          Fuel Consumption Prediction
        </h2>
        <p className="text-xs text-neutral-400 mt-1 font-sans">
          How accurately each model predicts real fuel burn, validated across the fleet.
        </p>
      </div>
      <button
        onClick={onClose}
        className="w-8 h-8 shrink-0 rounded-full border border-neutral-800 flex items-center justify-center text-neutral-400 hover:text-white hover:border-neutral-600 font-mono text-sm transition-all"
      >
        ✕
      </button>
    </div>
  );

  if (!benchmark.available) {
    return (
      <div className="overlay-backdrop" onClick={onClose}>
        <div className="overlay-panel w-full max-w-4xl p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
          {header}
          <div className="p-4 rounded-lg bg-neutral-950 border border-neutral-800">
            <p className="text-xs text-neutral-400 font-sans">Prediction benchmark not generated yet.</p>
          </div>
        </div>
      </div>
    );
  }

  const { arms, best_arm: bestArm } = benchmark;
  const relativeImprovementPct =
    benchmark.physics_only_mape_percent > 0
      ? ((benchmark.physics_only_mape_percent - benchmark.best_arm_mape_percent) / benchmark.physics_only_mape_percent) * 100
      : 0;

  // `get` always returns the value in "higher is better" space, so a plain
  // Math.max over it picks the right arm -- mean_mape_percent itself is the
  // opposite (lower is better), so it's inverted to an accuracy figure here
  // rather than formatted-but-still-inverted at display time.
  const metrics: { label: string; get: (r: FuelPredictorArmResult) => number; fmt: (v: number) => string }[] = [
    { label: 'Accuracy (Avg. Error)', get: r => 100 - r.mean_mape_percent, fmt: v => `${v.toFixed(1)}%` },
    { label: 'Accuracy Score (R²)', get: r => r.mean_r_squared, fmt: v => v.toFixed(3) },
  ];

  return (
    <div className="overlay-backdrop" onClick={onClose}>
      <div
        className="overlay-panel w-full max-w-5xl p-6 shadow-2xl max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {header}

        <div className="space-y-5">
          {/* Hero result */}
          <div className="p-5 rounded-lg bg-neutral-950 border border-emerald-900/60 flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-[10px] font-mono uppercase text-neutral-400 tracking-wider mb-1">
                Best Model: {ARM_LABELS[bestArm]}
              </div>
              <div className="text-3xl font-mono font-bold text-emerald-400">
                {relativeImprovementPct.toFixed(0)}% More Accurate
              </div>
              <div className="text-[11px] font-mono text-neutral-500 mt-1">than physics-only estimation</div>
            </div>
            <div className="flex gap-6">
              <div>
                <div className="text-[10px] font-mono uppercase text-neutral-500 tracking-wider mb-1">Validated On</div>
                <div className="text-lg font-mono font-bold text-white">{benchmark.n_samples.toLocaleString()}</div>
                <div className="text-[10px] font-mono text-neutral-500">fuel-burn samples</div>
              </div>
              <div>
                <div className="text-[10px] font-mono uppercase text-neutral-500 tracking-wider mb-1">Fleet Coverage</div>
                <div className="text-lg font-mono font-bold text-white">{benchmark.n_folds}</div>
                <div className="text-[10px] font-mono text-neutral-500">vessels cross-checked</div>
              </div>
            </div>
          </div>

          {/* Head-to-head, four arms */}
          <div className="p-4 rounded-lg bg-neutral-950 border border-neutral-800">
            <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider mb-3">
              Model Comparison
            </h3>
            <div className="overflow-x-auto">
              <table className="decision-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    {ARM_ORDER.map(arm => (
                      <th key={arm} className={arm === bestArm ? 'text-emerald-400' : ''}>{ARM_LABELS[arm]}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {metrics.map(m => {
                    const values = ARM_ORDER.map(arm => m.get(arms[arm]));
                    const best = Math.max(...values);
                    return (
                      <tr key={m.label}>
                        <td className="text-neutral-400">{m.label}</td>
                        {ARM_ORDER.map((arm, i) => (
                          <td
                            key={arm}
                            className={`font-mono ${values[i] === best ? 'text-emerald-400 font-bold' : 'text-neutral-300'}`}
                          >
                            {m.fmt(values[i])}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="mt-6 pt-4 border-t border-neutral-800 flex items-center justify-between">
          <span className="text-[10px] font-mono text-neutral-600">Updated {benchmark.generated_at.slice(0, 10)}</span>
          <button
            onClick={onClose}
            className="px-5 py-2 bg-white text-black font-semibold text-xs rounded hover:bg-neutral-200 transition-all font-mono"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
