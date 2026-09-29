'use client';

import { PageHeader } from './PageHeader';
import React, { FormEvent, useState } from 'react';
import { CheckCircleIcon, DownloadSimpleIcon, InfoIcon } from '@phosphor-icons/react';
import { DataGate } from '@/components/DataGate';
import { ComparableAlternative, ComparableRecommendations, DemoData } from '@/types/demo';
import { abatementLadder } from '@/lib/planAnalytics';
import { FrontierChart, Legend, seriesColor } from '@/components/Charts';
import { ktCO2e, kTonnes, pct, usdM } from '@/lib/format';
import { downloadFile, plansCsv, plansReportHtml } from '@/lib/report';

const PLAN_COLORS: Record<ComparableAlternative['id'], string> = {
  cheapest: seriesColor(0),
  balanced: seriesColor(3),
  greenest: seriesColor(2),
};

const PLAN_BLURB: Record<ComparableAlternative['id'], string> = {
  cheapest: 'Lowest five-year cost that still clears every cargo and service constraint.',
  balanced: 'Lowest cost achievable under the stated lifecycle-GHG cap.',
  greenest: 'Lowest lifecycle GHG the fleet can reach at all.',
};

const signedMoney = (value: number) =>
  value < 0 ? `${usdM(Math.abs(value))} credit` : `${usdM(value)} cost`;

function PlanCard({
  plan,
  reference,
}: {
  plan: ComparableAlternative;
  reference: ComparableAlternative;
}) {
  const { metrics } = plan;
  const costDelta = metrics.total_usd - reference.metrics.total_usd;
  const emissionsDelta = metrics.lifecycle_emissions_tco2e - reference.metrics.lifecycle_emissions_tco2e;
  const isReference = plan.id === reference.id;

  return (
    <article className="metric-card plan-option relative flex flex-col overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-1" style={{ background: PLAN_COLORS[plan.id] }} />
      <div className="pt-1">
        <h3 className="text-xl font-bold capitalize text-[var(--text-primary)]">{plan.definition}</h3>
        <p className="mt-1 min-h-10 text-sm leading-relaxed text-[var(--text-secondary)]">{PLAN_BLURB[plan.id]}</p>
      </div>

      <div className="my-5 grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-[var(--text-tertiary)]">Five-year cost</div>
          <div className="mt-1 font-mono text-2xl font-bold text-[var(--text-primary)]">{usdM(metrics.total_usd, 1)}</div>
          {!isReference && (
            <div className="mt-0.5 font-mono text-xs text-[var(--warning)]">
              +{pct(costDelta / reference.metrics.total_usd, 1)}
            </div>
          )}
        </div>
        <div>
          <div className="text-xs text-[var(--text-tertiary)]">Lifecycle GHG</div>
          <div className="mt-1 font-mono text-2xl font-bold text-[var(--text-primary)]">
            {ktCO2e(metrics.lifecycle_emissions_tco2e, 0)}
          </div>
          {!isReference && (
            <div className="mt-0.5 font-mono text-xs font-semibold text-[var(--success)]">
              −{pct(Math.abs(emissionsDelta) / reference.metrics.lifecycle_emissions_tco2e, 1)}
            </div>
          )}
        </div>
      </div>

      <dl className="space-y-2.5 border-y border-[var(--border)] py-4 text-sm">
        <div className="flex justify-between gap-3">
          <dt className="text-[var(--text-secondary)]">Bunker mass</dt>
          <dd className="font-mono text-[var(--text-primary)]">{kTonnes(metrics.fuel_tonnes)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-[var(--text-secondary)]">Compliance position</dt>
          <dd className={`font-mono ${metrics.compliance_usd < 0 ? 'text-[var(--success)] font-semibold' : 'text-[var(--text-primary)]'}`}>
            {signedMoney(metrics.compliance_usd)}
          </dd>
        </div>
        {plan.emissions_cap_tco2e !== null && (
          <div className="flex justify-between gap-3">
            <dt className="text-[var(--text-secondary)]">GHG cap applied</dt>
            <dd className="font-mono text-[var(--text-primary)]">{ktCO2e(plan.emissions_cap_tco2e, 0)}</dd>
          </div>
        )}
      </dl>

      <div className="mt-4 grid grid-cols-2 gap-2 text-xs font-medium">
        <span className="rounded-md bg-[var(--success-soft)] px-2.5 py-2 text-[var(--success)]">
          <CheckCircleIcon className="mr-1 inline" size={14} weight="bold" />Cargo demand met
        </span>
        <span className="rounded-md bg-[var(--success-soft)] px-2.5 py-2 text-[var(--success)]">
          <CheckCircleIcon className="mr-1 inline" size={14} weight="bold" />Service days met
        </span>
      </div>

      <p className="mt-3 text-xs leading-relaxed text-[var(--text-secondary)]">
        {isReference
          ? 'Reference plan for this comparison.'
          : `${plan.change_summary.changed_vessel_years} vessel-year decisions differ from Cheapest.`}
      </p>
    </article>
  );
}

function StaleDataNotice() {
  return (
    <div className="page-shell">
      <div className="max-w-2xl rounded-xl border border-[var(--warning)] bg-[var(--surface-sunken)] p-6">
        <InfoIcon size={24} className="text-[var(--warning)]" weight="fill" />
        <h1 className="mt-4 text-2xl font-bold text-[var(--text-primary)]">This build has no comparable alternatives</h1>
        <p className="mt-2 leading-relaxed text-[var(--text-secondary)]">
          Comparable plans are calculated by the optimizer under one shared operating scenario. This page will
          not reconstruct them in the browser from sweep points, because plans solved under different
          assumptions are not comparable.
        </p>
      </div>
    </div>
  );
}

function TradeOffDeck({ recommendations, metadata }: { recommendations: ComparableRecommendations; metadata: DemoData['metadata'] }) {
  const scenario = recommendations.scenario;
  const provenance = recommendations.provenance ?? {
    optimizer: metadata.optimizer,
    fuel_model: metadata.fuel_model ?? 'physics',
    fuel_model_fallback_reason: metadata.fuel_model_fallback_reason ?? null,
  };
  const { ordered, steps } = abatementLadder(recommendations.alternatives);
  const reference = ordered[0];

  return (
    <div className="page-shell pt-6">
      <PageHeader category="Plans" title="Choose your balance of cost and carbon.">
        <p className="mt-2 text-base leading-relaxed text-[var(--text-secondary)]">
          Three independently optimized plans, scored under one scenario:{' '}
          ${scenario.effective_carbon_price_usd_per_tco2e}/tCO₂e carbon price and{' '}
          {(scenario.cargo_demand_multiplier ?? 1).toFixed(1)}× annual cargo demand.
        </p>
      </PageHeader>

      <h2 className="mb-5">Three plans. The same operating assumptions.</h2>
      <div className="plan-comparison">
        {ordered.map(plan => <PlanCard key={plan.id} plan={plan} reference={reference} />)}
      </div>

      {/* Frontier */}
      <section className="metric-card mb-6" aria-label="Cost against lifecycle emissions">
        <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--text-primary)]">
          The abatement curve for this fleet
        </h2>
        <p className="mb-4 mt-1 max-w-3xl text-sm leading-relaxed text-[var(--text-secondary)]">
          Each marker is a complete five-year plan. Labels show what each extra tonne of CO₂e costs to remove.
        </p>
        <FrontierChart
          points={ordered.map(plan => ({
            id: plan.id,
            label: plan.definition,
            x: plan.metrics.total_usd,
            y: plan.metrics.lifecycle_emissions_tco2e,
            color: PLAN_COLORS[plan.id],
          }))}
          xLabel="Five-year fleet cost"
          yLabel="Lifecycle GHG"
          formatX={value => usdM(value, 0)}
          formatY={value => ktCO2e(value, 0)}
          annotations={steps.map(step => ({
            fromId: step.from.id,
            toId: step.to.id,
            text: `$${Math.round(step.usdPerTonneAbated)}/tCO₂e abated`,
          }))}
        />
        <Legend items={ordered.map(plan => ({ label: plan.definition, color: PLAN_COLORS[plan.id] }))} />
      </section>

      <p className="mb-6 text-xs leading-relaxed text-[var(--text-tertiary)]">
        Solved with {provenance.optimizer.toUpperCase()} and the {provenance.fuel_model.toUpperCase()} fuel estimator.
        Every plan meets annual cargo and service-day requirements on every route and year.{' '}
        <strong className="font-medium text-[var(--text-secondary)]">Balanced:</strong> {recommendations.balanced_definition}
      </p>
    </div>
  );
}

/** Hidden for now; set to true to show the live re-solve form again. */
const SHOW_LIVE_RESOLVE = false;

const liveApiBaseUrl = (process.env.NEXT_PUBLIC_LIVE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '');

function Recommendations({ data }: { data: DemoData }) {
  const [recommendations, setRecommendations] = useState<ComparableRecommendations | null>(
    data.comparable_recommendations ?? null
  );
  const [carbonPrice, setCarbonPrice] = useState('175');
  const [demandMultiplier, setDemandMultiplier] = useState('1');
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const requestLiveScenario = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPending(true);
    setMessage(null);
    try {
      const response = await fetch(`${liveApiBaseUrl}/api/recommendations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          carbon_price_usd_per_tco2e: Number(carbonPrice),
          cargo_demand_multiplier: Number(demandMultiplier),
        }),
      });
      const payload = (await response.json()) as
        | ComparableRecommendations
        | { status: string; message?: string; reasons?: Array<{ message: string }> };
      if (response.ok && payload.status === 'SYNTHETIC_COMPARABLE_ALTERNATIVES') {
        setRecommendations(payload as ComparableRecommendations);
        setMessage('Solved. The curve and cards below now reflect your inputs.');
      } else if (payload.status === 'INFEASIBLE') {
        const errorPayload = payload as { reasons?: Array<{ message: string }> };
        const reasons = errorPayload.reasons ?? [];
        setMessage(
          reasons.length
            ? `No feasible plan exists on ${reasons.length} route${reasons.length === 1 ? '' : 's'}: ${reasons[0].message}`
            : 'No feasible plan exists for the requested scenario.'
        );
      } else {
        setMessage((payload as { message?: string }).message ?? 'The request could not be completed.');
      }
    } catch {
      setMessage('Solver service unreachable. Start the Python API, then try again.');
    } finally {
      setPending(false);
    }
  };

  if (!recommendations) return <StaleDataNotice />;

  return (
    <>
      <TradeOffDeck recommendations={recommendations} metadata={data.metadata} />
      <div className="page-shell pb-0 pt-0">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border)] p-4">
          <div>
            <h2 className="font-semibold text-[var(--text-primary)]">Export this comparison</h2>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Printable report with every vessel-year decision, or the raw decisions as CSV.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => downloadFile('knotwise-plan-report.html', plansReportHtml(recommendations, new Date()), 'text/html')}
              className="inline-flex items-center gap-1.5 rounded-md bg-[var(--action-bg)] px-4 py-2 text-sm font-semibold text-[var(--action-text)] transition-colors hover:bg-[var(--action-bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
            >
              <DownloadSimpleIcon size={16} weight="bold" /> Download report
            </button>
            <button
              type="button"
              onClick={() => downloadFile('knotwise-plan-decisions.csv', plansCsv(recommendations), 'text/csv')}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-4 py-2 text-sm font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
            >
              CSV
            </button>
          </div>
        </div>
      </div>
      {SHOW_LIVE_RESOLVE && <div className="page-shell pb-0 pt-6">
        <form onSubmit={requestLiveScenario} className="rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)] p-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="font-semibold text-[var(--text-primary)]">Re-solve the fleet on your own scenario</h2>
              <p className="mt-1 text-sm leading-relaxed text-[var(--text-secondary)]">
                Change the carbon price or annual cargo demand and the optimizer runs for real. If no feasible
                plan exists, it says which route makes it impossible rather than returning a plausible-looking
                answer.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <label className="text-xs font-medium text-[var(--text-secondary)]">
                Carbon price ($/tCO₂e)
                <input
                  aria-label="Carbon price"
                  value={carbonPrice}
                  onChange={event => setCarbonPrice(event.target.value)}
                  inputMode="decimal"
                  className="mt-1 block w-full rounded-md border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2 font-mono text-sm text-[var(--text-primary)]"
                />
              </label>
              <label className="text-xs font-medium text-[var(--text-secondary)]">
                Cargo-demand multiplier
                <input
                  aria-label="Cargo-demand multiplier"
                  value={demandMultiplier}
                  onChange={event => setDemandMultiplier(event.target.value)}
                  inputMode="decimal"
                  className="mt-1 block w-full rounded-md border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2 font-mono text-sm text-[var(--text-primary)]"
                />
              </label>
              <button
                disabled={pending}
                className="rounded-md bg-[var(--action-bg)] px-4 py-2 text-sm font-semibold text-[var(--action-text)] transition-colors hover:bg-[var(--action-bg-hover)] disabled:cursor-wait disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
              >
                {pending ? 'Solving…' : 'Solve scenario'}
              </button>
            </div>
          </div>
          {message && (
            <p className="mt-3 text-sm text-[var(--text-secondary)]" role="status">
              {message}
            </p>
          )}
        </form>
      </div>}
    </>
  );
}

export function RecommendationView() {
  return <DataGate>{data => <Recommendations data={data} />}</DataGate>;
}
