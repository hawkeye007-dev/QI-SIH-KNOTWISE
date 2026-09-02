'use client';

import React from 'react';
import { AblationArm, OptimizerBenchmark, OptimizerRun } from '@/types/demo';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  benchmark: OptimizerBenchmark;
}

const usdM = (v: number) => `$${(v / 1e6).toFixed(2)}M`;
const pct = (frac: number) => `${(frac * 100).toFixed(2)}%`;

/** Paired horizontal range bars for one ablation stage. Both arms share a
 *  single scale so "disjoint" vs "overlapping" is read off the geometry
 *  rather than asserted in prose -- that contrast IS the finding. */
const AblationStage: React.FC<{
  title: string;
  caption: string;
  arms: { uniform_init: AblationArm; mean_field_init: AblationArm };
  improvementFraction: number;
}> = ({ title, caption, arms, improvementFraction }) => {
  const all = [arms.uniform_init, arms.mean_field_init];
  const lo = Math.min(...all.map(a => a.best_total_usd));
  const hi = Math.max(...all.map(a => a.worst_total_usd));
  const span = hi - lo || 1;
  // 6% headroom each side so an endpoint label never clips the track edge.
  const x = (v: number) => 6 + ((v - lo) / span) * 88;

  const rows: { label: string; arm: AblationArm; accent: string }[] = [
    { label: 'Uniform init', arm: arms.uniform_init, accent: '#737373' },
    { label: 'Mean-field init', arm: arms.mean_field_init, accent: '#34d399' },
  ];

  return (
    <div className="p-4 rounded-lg bg-neutral-950 border border-neutral-800">
      <div className="flex items-baseline justify-between mb-1 gap-3">
        <h4 className="text-xs font-mono font-bold text-white uppercase tracking-wider">{title}</h4>
        <span
          className={`text-xs font-mono font-bold ${
            improvementFraction > 0.01 ? 'text-emerald-400' : 'text-neutral-500'
          }`}
        >
          {improvementFraction > 0 ? '−' : '+'}
          {pct(Math.abs(improvementFraction))} cost
        </span>
      </div>
      <p className="text-[11px] text-neutral-400 font-sans mb-4">{caption}</p>

      <div className="space-y-4">
        {rows.map(({ label, arm, accent }) => (
          <div key={label}>
            <div className="flex items-baseline justify-between mb-1.5">
              <span className="text-[11px] font-mono" style={{ color: accent }}>
                {label}
              </span>
              <span className="text-[10px] font-mono text-neutral-500">
                n={arm.n_runs} · mean {usdM(arm.mean_total_usd)}
              </span>
            </div>
            <div className="relative h-7">
              {/* track */}
              <div className="absolute top-3 left-0 right-0 h-px bg-neutral-800" />
              {/* best..worst range */}
              <div
                className="absolute top-[9px] h-1.5 rounded-full"
                style={{
                  left: `${x(arm.best_total_usd)}%`,
                  width: `${x(arm.worst_total_usd) - x(arm.best_total_usd)}%`,
                  backgroundColor: accent,
                  opacity: 0.35,
                }}
              />
              {/* mean marker */}
              <div
                className="absolute top-1.5 w-0.5 h-3.5 rounded"
                style={{ left: `${x(arm.mean_total_usd)}%`, backgroundColor: accent }}
              />
              <span
                className="absolute top-[18px] text-[9px] font-mono text-neutral-500 -translate-x-1/2"
                style={{ left: `${x(arm.best_total_usd)}%` }}
              >
                {usdM(arm.best_total_usd)}
              </span>
              <span
                className="absolute top-[18px] text-[9px] font-mono text-neutral-500 -translate-x-1/2"
                style={{ left: `${x(arm.worst_total_usd)}%` }}
              >
                {usdM(arm.worst_total_usd)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export const QuantumModal: React.FC<Props> = ({ isOpen, onClose, benchmark }) => {
  if (!isOpen) return null;

  const header = (
    <div className="flex items-start justify-between border-b border-neutral-800 pb-4 mb-5 gap-4">
      <div>
        <h2 className="text-base font-semibold text-white uppercase tracking-wider font-mono">
          Quantum-Inspired Optimizer · What It Actually Buys
        </h2>
        <p className="text-xs text-neutral-400 mt-1 font-sans">
          A measured GA-vs-QIEA comparison, and an ablation isolating the contribution of the
          quantum-inspired representation itself.
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

  // `build_demo_data.py` gives the un-run case a defined shape on purpose, so
  // say so plainly rather than rendering an empty table of zeroes.
  if (!benchmark.available) {
    return (
      <div className="overlay-backdrop" onClick={onClose}>
        <div className="overlay-panel w-full max-w-4xl p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
          {header}
          <div className="p-4 rounded-lg bg-neutral-950 border border-neutral-800">
            <div className="text-xs font-mono text-amber-400 mb-2">BENCHMARK NOT AVAILABLE</div>
            <p className="text-xs text-neutral-400 font-sans">{benchmark.notes}</p>
            <p className="text-[11px] text-neutral-500 font-mono mt-3">
              This demo&apos;s plans were solved with &apos;{benchmark.demo_built_with_optimizer}&apos;.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const { ga, qiea, search_attribution: sa } = benchmark;
  const shipped = benchmark.demo_built_with_optimizer;

  const metrics: { label: string; get: (r: OptimizerRun) => string; lowerIsBetter: boolean; note?: string }[] = [
    { label: 'Min plan cost across grid', get: r => usdM(r.min_total_usd_across_grid), lowerIsBetter: true },
    { label: 'Wall-clock (sweep + exposure)', get: r => `${r.total_seconds.toFixed(1)}s`, lowerIsBetter: true },
    { label: 'Switching points found', get: r => `${r.n_switching_points}`, lowerIsBetter: false },
    { label: 'Unstable decisions', get: r => `${r.n_unanimous_unstable}`, lowerIsBetter: true },
    { label: 'Plan spread', get: r => `₹${r.plan_spread_inr_crore.toFixed(1)} Cr`, lowerIsBetter: false },
    {
      label: 'Envelope corrections',
      get: r => `${r.n_envelope_corrected}`,
      lowerIsBetter: true,
      note: 'noisy across seeds — not tuned against',
    },
  ];

  const costWinner = qiea.min_total_usd_across_grid < ga.min_total_usd_across_grid ? 'qiea' : 'ga';
  const costMarginFrac =
    Math.abs(qiea.min_total_usd_across_grid - ga.min_total_usd_across_grid) / ga.min_total_usd_across_grid;

  return (
    <div className="overlay-backdrop" onClick={onClose}>
      <div
        className="overlay-panel w-full max-w-4xl p-6 shadow-2xl max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {header}

        <div className="space-y-5">
          {/* Head-to-head */}
          <div className="p-4 rounded-lg bg-neutral-950 border border-neutral-800">
            <div className="flex items-baseline justify-between mb-3 gap-3">
              <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                Head-to-head · matched settings
              </h3>
              <span className="text-[10px] font-mono text-neutral-500">
                pop {benchmark.sweep_kwargs.population_size} · {benchmark.price_grid.length} grid points
              </span>
            </div>
            <table className="decision-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>GA (classical)</th>
                  <th>QIEA (quantum-inspired)</th>
                </tr>
              </thead>
              <tbody>
                {metrics.map(m => {
                  const g = m.get(ga);
                  const q = m.get(qiea);
                  const qBetter =
                    m.lowerIsBetter &&
                    parseFloat(q.replace(/[^0-9.]/g, '')) < parseFloat(g.replace(/[^0-9.]/g, ''));
                  return (
                    <tr key={m.label}>
                      <td className="text-neutral-400">
                        {m.label}
                        {m.note && <span className="block text-[10px] text-neutral-600">{m.note}</span>}
                      </td>
                      <td className="font-mono text-neutral-300">{g}</td>
                      <td className={`font-mono ${qBetter ? 'text-emerald-400 font-semibold' : 'text-neutral-300'}`}>
                        {q}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="text-[11px] text-neutral-400 font-sans mt-3">
              QIEA returns the cheaper plan, by {pct(costMarginFrac)} — a margin small enough that the
              ordering should be re-confirmed at production settings before being relied on. The plans shown
              everywhere else on this site were solved with{' '}
              <strong className="text-white font-mono">{shipped.toUpperCase()}</strong>.
              {costWinner === 'qiea' && ' The cheaper solver is not the one shipped.'}
            </p>
          </div>

          {/* Mechanism */}
          <div className="p-4 rounded-lg bg-neutral-950 border border-neutral-800">
            <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider mb-2">
              The mechanism
            </h3>
            <p className="text-xs text-neutral-400 font-sans leading-relaxed">{sa.mechanism}</p>
          </div>

          {/* Ablation */}
          <AblationStage
            title="1 · Raw search (polish disabled)"
            caption="What the quantum-inspired representation contributes on its own. The two distributions do not overlap: the mean-field prior's worst run beats the uniform prior's best."
            arms={sa.raw_search_polish_disabled}
            improvementFraction={sa.raw_search_improvement_fraction}
          />
          <AblationStage
            title="2 · Delivered answer (polish enabled)"
            caption="The same comparison with the coordinate-descent polish both solvers share. The distributions now sit on top of each other — the polish absorbs the entire difference in what the search hands it."
            arms={sa.end_to_end_polish_enabled}
            improvementFraction={sa.end_to_end_improvement_fraction}
          />

          {/* Finding */}
          <div className="p-4 rounded-lg bg-neutral-950 border border-neutral-700">
            <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider mb-2">
              What this means
            </h3>
            <p className="text-xs text-neutral-300 font-sans leading-relaxed">{sa.finding}</p>
          </div>

          {/* Provenance */}
          <div className="p-4 rounded-lg bg-neutral-950 border border-neutral-800">
            <div className="flex items-center gap-2 mb-2">
              <span className="tag font-mono">{benchmark.status}</span>
              <span className="text-[10px] font-mono text-neutral-500">
                benchmarked {benchmark.generated_at}
              </span>
            </div>
            <p className="text-[11px] text-neutral-500 font-sans leading-relaxed">{benchmark.provenance_note}</p>
            <p className="text-[11px] text-neutral-500 font-sans leading-relaxed mt-2">{benchmark.freshness_note}</p>
          </div>
        </div>

        <div className="mt-6 pt-4 border-t border-neutral-800 flex justify-end">
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
