'use client';

import { PageHeader } from './PageHeader';
import React from 'react';
import Link from 'next/link';
import { DemoData, ScenarioAxisPosition } from '@/types/demo';
import { useAtlas } from '@/lib/AtlasContext';
import { deepestCut } from '@/lib/planAnalytics';
import { inrCrore, ktCO2e, pct } from '@/lib/format';

const SCENARIOS: { id: string; label: string; desc: string }[] = [
  { id: 'approved_text', label: 'Approved NZF text', desc: 'The baseline two-tier carbon pricing proposal.' },
  { id: 'tuvalu', label: 'Tuvalu proposal', desc: 'A higher flat levy, favoured by island states.' },
  { id: 'liberia', label: 'Liberia proposal', desc: 'Tradeable surplus units instead of a posted price.' },
  { id: 'brazil', label: 'Brazil transition', desc: 'A phased intensity-reduction schedule starting at 3%.' },
  { id: 'adoption_fails', label: 'Adoption fails again', desc: 'No NZF — the CII, FuelEU and EU ETS stack only.' },
];

const formatTick = (tick: ScenarioAxisPosition | undefined): string => {
  if (!tick || tick.operating_point_usd_per_tco2e == null) {
    if (tick?.kind === 'qualitative_marker') return 'no posted price';
    return 'not computed';
  }
  return `≈$${Math.round(tick.operating_point_usd_per_tco2e)}/tCO₂e`;
};

const Section: React.FC<{ n: number; title: string; children: React.ReactNode }> = ({ n, title, children }) => (
  <section className="metric-card">
    <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-[var(--text-primary)]">
      <span className="mr-2 text-[var(--text-tertiary)]">{n}</span>
      {title}
    </h2>
    <div className="space-y-2 text-sm leading-relaxed text-[var(--text-secondary)]">{children}</div>
  </section>
);

export function GuideView({ data }: { data: DemoData }) {
  const { scaleSummary } = useAtlas();
  const tickById = new Map(data.sweep.scenario_ticks.map(tick => [tick.scenario_id, tick]));
  const spread = data.exposure.plan_spread;
  const cut = deepestCut(data);
  const benchmark = data.optimizer_benchmark;
  const predictor = data.fuel_predictor_benchmark;

  return (
    <div className="page-shell guide-page">
      <PageHeader category="Guide" title="The fleet decision, explained.">
        <p className="mt-2 text-base leading-relaxed text-[var(--text-secondary)]">
          Plain English, no maritime background assumed — what the problem is, what the software does about it,
          and what each page is showing you.
        </p>
      </PageHeader>

      <div className="space-y-5">
        <Section n={1} title="The problem">
          <p>
            The IMO — the UN body that regulates shipping — is due to reconvene on{' '}
            <strong className="text-[var(--text-primary)]">4 December 2026</strong> to decide on a global carbon
            price for merchant ships. A shipping company has to plan five years ahead: which vessel runs which
            route, how fast it sails, what fuel it burns, whether it plugs into shore power in port. Those
            decisions are locked in long before the vote lands, and they are worth very different amounts
            depending on how it goes.
          </p>
          <p>
            KnotWise solves the whole fleet plan for <em>every</em> possible outcome, then shows which decisions
            are genuinely safe and which are bets — priced, in rupees.
          </p>
        </Section>

        <Section n={2} title="What the optimizer decides">
          <p>
            For each of the {data.fleet.vessels.length} vessels, in each of the five years 2026–2030, it picks six
            things at once: the trade route, the cruising speed band, the fuel, whether to take shore power, and
            two FuelEU flexibility elections (pooling and borrowing). That is {data.fleet.vessels.length * 5}{' '}
            coupled decisions, each affecting the others through the fleet-wide cargo requirement and the
            compliance pool.
          </p>
          <p>
            Every plan it returns has already been checked twice: the fleet carries the cargo each route demands,
            and no vessel is asked to spend more days at sea than it physically has available.
          </p>
        </Section>

        <Section n={3} title="Four regulations, priced together">
          <p>
            Most tools model one regime. This one prices four simultaneously — the IMO&apos;s{' '}
            <strong className="text-[var(--text-primary)]">CII</strong> and{' '}
            <strong className="text-[var(--text-primary)]">Net-Zero Framework</strong>, plus{' '}
            <strong className="text-[var(--text-primary)]">FuelEU Maritime</strong> and the{' '}
            <strong className="text-[var(--text-primary)]">EU Emissions Trading System</strong> — including the
            rule that European regimes only apply to half of a voyage that starts outside Europe, and all of one
            that stays inside it. A vessel can owe under all four, some, or none, depending on its size and where
            it trades.
          </p>
        </Section>

        <Section n={4} title="The carbon price slider">
          <p>
            Drag it on the Overview, Fleet or Sensitivity pages, or jump straight to a real proposal on the
            table. Each figure below is computed from this fleet&apos;s own compliance position, not typed in:
          </p>
          <ul className="mt-2 space-y-1.5">
            {SCENARIOS.map(scenario => (
              <li key={scenario.id}>
                <strong className="font-mono text-[var(--text-primary)]">
                  {scenario.label} ({formatTick(tickById.get(scenario.id))}):
                </strong>{' '}
                {scenario.desc}
              </li>
            ))}
          </ul>
          <p className="mt-2">
            Two of them show no price on purpose. Liberia&apos;s proposal is a market design with no posted
            per-tonne figure, and Brazil&apos;s is a percentage schedule rather than a price — so neither is
            given an invented number.
          </p>
        </Section>

        <Section n={5} title="What “quantum-inspired” means here">
          <p>
            Nothing runs on a quantum computer. The idea borrowed from quantum computing is the{' '}
            <em>representation</em>: instead of carrying a population of concrete candidate plans the way a
            genetic algorithm does, the solver carries a probability distribution over every single decision —
            the classical analogue of a superposition — and reshapes those distributions as it learns.
          </p>
          <p>
            That buys something a population of fixed plans structurally cannot have: each decision can be
            started off already knowing what the cost model implies about it, before any complete plan has been
            scored.{' '}
            {scaleSummary && (
              <>
                Measured against a classical genetic algorithm at an identical compute budget, it delivers{' '}
                <strong className="text-[var(--success)]">
                  {pct(scaleSummary.minGainFraction)}–{pct(scaleSummary.maxGainFraction)} lower fleet cost
                </strong>
                , winning {scaleSummary.totalWins} of {scaleSummary.totalRuns} paired runs, with the margin
                widening from {scaleSummary.smallestFleet} to {scaleSummary.largestFleet} vessels.
              </>
            )}{' '}
            On a problem small enough to solve exactly by brute force, both solvers return the provable optimum —
            so the comparison is between two correct methods, not a correct one and a lucky one.
          </p>
          <p>
            The same family of mathematics shows up twice more: a tensor-train decomposition predicts fuel burn
            on the <Link href="/prediction" className="font-medium text-[var(--accent)] hover:underline">Prediction</Link> page,
            and a tensor-network mutual-information calculation ranks decision confidence on the{' '}
            <Link href="/exposure" className="font-medium text-[var(--accent)] hover:underline">Exposure</Link> page.
          </p>
        </Section>

        <Section n={6} title="Where to find each answer">
          <ul className="space-y-2">
            <li>
              <Link href="/plans" className="font-semibold text-[var(--accent)] hover:underline">Plans</Link> — the
              cost-versus-carbon trade-off, three optimized plans on one curve, with the marginal cost of each
              tonne abated. Re-solve it live on your own inputs.
            </li>
            <li>
              <Link href="/fleet-matrix" className="font-semibold text-[var(--accent)] hover:underline">Fleet</Link> —
              the actual year-by-year decision for every vessel, with anything that changed from the $0/t plan
              highlighted.
            </li>
            <li>
              <Link href="/fuels" className="font-semibold text-[var(--accent)] hover:underline">Fuels</Link> — which
              of the eight bunker options win, and the carbon price each one has to wait for.
              {cut && <> The deepest cut available is {ktCO2e(Math.abs(cut.deltaTco2e))}, or {pct(Math.abs(cut.deltaFraction))}.</>}
            </li>
            <li>
              <Link href="/sensitivity" className="font-semibold text-[var(--accent)] hover:underline">Sensitivity</Link> —
              cost, compliance, emissions and bunker mass across the full price axis.
            </li>
            <li>
              <Link href="/exposure" className="font-semibold text-[var(--accent)] hover:underline">Exposure</Link> — the{' '}
              {inrCrore(spread.spread_inr)} of fleet cost that depends on how the vote lands, and which decisions
              carry it.
            </li>
            <li>
              <Link href="/engine" className="font-semibold text-[var(--accent)] hover:underline">Engine</Link> and{' '}
              <Link href="/prediction" className="font-semibold text-[var(--accent)] hover:underline">Prediction</Link> —
              the benchmarks behind the two algorithms.
            </li>
          </ul>
        </Section>

        <Section n={7} title="Provenance">
          <p>
            The fleet is a documented ten-vessel case study built on published vessel-class figures; regulatory
            constants are transcribed from the regulation texts with retrieval dates, and bunker prices from
            dated market quotes. Every cost the optimizer reports carries a confidence label internally, and an
            aggregate is never reported as more confident than its weakest component.
          </p>
          <p>
            {benchmark.available && <>Solver benchmarks were generated {benchmark.generated_at.slice(0, 10)}. </>}
            {predictor.available && <>Prediction benchmarks were generated {predictor.generated_at.slice(0, 10)}, cross-validated by holding out one vessel at a time. </>}
            Figures on this site are prototype outputs for evaluation, not sailing instructions.
          </p>
        </Section>
      </div>
    </div>
  );
}
