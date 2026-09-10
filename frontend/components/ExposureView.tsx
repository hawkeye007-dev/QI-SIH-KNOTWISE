'use client';

import { PageHeader } from './PageHeader';
import React from 'react';
import { DemoData } from '@/types/demo';

export function ExposureView({ data }: { data: DemoData }) {
  const exposure = data.exposure;
  const ps = exposure.plan_spread;
  const capex = exposure.capex_exposure;
  const majorityCapex = exposure.majority_capex_exposure ?? { total_usd: 0, total_inr: 0, decisions: [], description: '' };
  const summary = exposure.summary;
  const fx = exposure.fx;
  const hasCapexSignal = majorityCapex.total_inr > 0 || capex.total_inr > 0;

  return (
    <div className="page-shell">
      <PageHeader category="Exposure" title="Put a price on regulatory uncertainty.">
        <p>See how fleet costs change across regulatory scenarios, then separate consistent decisions from uncertain ones before committing capital.</p>
      </PageHeader>

      {/* Hero Financial Summary */}
      <div className={`grid grid-cols-1 ${hasCapexSignal ? 'md:grid-cols-2' : ''} gap-5 mb-6`}>
        <div className="metric-card report-evidence">
          <div className="text-xs uppercase tracking-wide text-[var(--text-tertiary)] mb-1">
            Regulatory Uncertainty Spread
          </div>
          <div className="text-2xl font-bold font-mono text-[var(--text-primary)] mb-1">
            ₹{(ps.spread_inr / 1e7).toFixed(2)} Crore
          </div>
          <div className="text-sm font-mono text-[var(--text-secondary)]">
            ${(ps.spread_usd / 1e6).toFixed(2)}M USD Plan Cost Variance
          </div>
          <p className="text-sm text-[var(--text-secondary)] mt-2 leading-relaxed">
            {hasCapexSignal
              ? `Non-overlapping financial spread across scenario limits (${ps.max_scenario_id} vs ${ps.min_scenario_id}).`
              : 'Plan-cost spread across regulatory scenarios; see the Fleet Decision Matrix for which decisions drive it.'}
          </p>
        </div>

        {hasCapexSignal && (
          <div className="metric-card">
            <div className="text-xs uppercase tracking-wide text-[var(--text-tertiary)] mb-1">
              Capital at Risk (Capex Exposure)
            </div>
            <div className="text-2xl font-bold font-mono text-[var(--text-primary)] mb-1">
              ₹{(majorityCapex.total_inr / 1e7).toFixed(2)} Crore
            </div>
            <div className="text-sm font-mono text-[var(--text-secondary)]">
              ${(majorityCapex.total_usd / 1e6).toFixed(2)}M USD Capital Reallocation
            </div>
            <p className="text-sm text-[var(--text-secondary)] mt-2 leading-relaxed">
              Majority-confidence capital commitment estimate (2-of-3+ seeds agree). The strict unanimous filter
              is ₹0 by definition — see the table below for why.
            </p>
          </div>
        )}
      </div>

      {/* Exposure Tiers Table */}
      <div className="border border-[var(--border)] rounded-xl overflow-x-auto mb-6 shadow-sm">
        <table className="decision-table">
          <thead>
            <tr>
              <th>Confidence Tier</th>
              <th className="text-center">Decision Count</th>
              <th className="text-right">Financial Exposure</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <div className="font-semibold text-[var(--text-secondary)]">Unanimous Confidence Filter</div>
                <div className="text-xs text-[var(--text-tertiary)] mt-0.5">
                  Strict agreement across all stability seeds — ₹0 by construction: a decision that&apos;s
                  unanimous across every regulatory scenario has, by definition, no exposure to the vote.
                </div>
              </td>
              <td className="text-center font-mono text-[var(--text-secondary)]">{summary.stable_exposed_decision_count}</td>
              <td className="text-right font-mono text-[var(--text-tertiary)]">
                {summary.capex_exposure_inr > 0 ? `₹${(summary.capex_exposure_inr / 1e7).toFixed(2)} Cr` : 'None flagged'}
              </td>
            </tr>
            <tr>
              <td>
                <div className="font-semibold text-[var(--text-primary)]">Majority Confidence Band</div>
                <div className="text-xs text-[var(--text-tertiary)] mt-0.5">High-probability drill-down elections</div>
              </td>
              <td className="text-center font-mono font-bold text-[var(--text-primary)]">
                {summary.majority_band_decision_count > 0 ? summary.majority_band_decision_count : 'None this run'}
              </td>
              <td className="text-right font-mono text-[var(--text-primary)]">
                {majorityCapex.total_inr > 0 ? `₹${(majorityCapex.total_inr / 1e7).toFixed(2)} Cr` : 'No capex flagged'}
              </td>
            </tr>
            <tr>
              <td>
                <div className="font-semibold text-[var(--text-secondary)]">High-Variance Decisions</div>
                <div className="text-xs text-[var(--text-tertiary)] mt-0.5">Excluded near-tied optimization regions</div>
              </td>
              <td className="text-center font-mono text-[var(--text-secondary)]">{summary.unstable_decision_count}</td>
              <td className="text-right font-mono text-[var(--text-tertiary)]">Excluded</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Tensor-network confidence crosscheck */}
      {exposure.mps_crosscheck && exposure.mps_crosscheck.rows.length > 0 && (
        <div className="border border-[var(--border)] rounded-xl overflow-x-auto mb-6 shadow-sm">
          <div className="px-4 py-3 bg-[var(--surface-sunken)] border-b border-[var(--border)]">
            <div className="text-sm font-semibold uppercase text-[var(--text-secondary)]">
              Tensor-Network Decision Confidence
            </div>
            <p className="text-sm text-[var(--text-secondary)] mt-1 leading-relaxed">
              Mutual information (bits) for the fleet&apos;s highest-signal decisions, computed directly from the
              quantum-inspired tensor-network model. This is an unbounded information measure, not a 0-1
              confidence score — read it as a ranking within this table, not against a fixed scale.
              <span className="block mt-1">
                Status is computed independently, by classical seed voting across scenario re-solves (the same
                method behind the tiers table above) — it is not derived from the score beside it, so the two
                columns can and do disagree on ordering.
              </span>
            </p>
          </div>
          <table className="decision-table">
            <thead>
              <tr>
                <th>Vessel / Year</th>
                <th>Decision</th>
                <th className="text-right">Tensor MI (bits)</th>
                <th className="text-center">Classical Status</th>
              </tr>
            </thead>
            <tbody>
              {exposure.mps_crosscheck.rows.slice(0, 20).map((row, i) => {
                const statusLabel =
                  row.classical_status === 'exposed' ? 'Exposed' : row.classical_status === 'unstable' ? 'High Variance' : 'Stable';
                const statusClass =
                  row.classical_status === 'exposed'
                    ? 'font-mono text-sm text-[var(--text-primary)]'
                    : row.classical_status === 'unstable'
                    ? 'font-mono text-sm text-[var(--text-tertiary)]'
                    : 'font-mono text-sm text-[var(--success)] font-bold';
                return (
                  <tr key={`${row.vessel_id}-${row.year}-${row.decision}-${i}`}>
                    <td className="font-mono text-[var(--text-secondary)]">{row.vessel_id} / {row.year}</td>
                    <td className="font-mono text-[var(--text-tertiary)]">{row.decision}</td>
                    <td className="text-right font-mono text-[var(--accent)] font-bold">{row.mutual_information_bits.toFixed(4)}</td>
                    <td className="text-center">
                      <span className={statusClass}>{statusLabel}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* FX Metadata */}
      <div className="p-3 bg-[var(--surface-sunken)] rounded-lg border border-[var(--border)] text-sm font-mono text-[var(--text-secondary)] flex flex-wrap items-center justify-between gap-2">
        <span>USD to INR Exchange Benchmark: ₹{fx.usd_to_inr_rate}</span>
        <span>Status: Verified Regulatory Benchmark ({fx.retrieval_date})</span>
      </div>
    </div>
  );
}
