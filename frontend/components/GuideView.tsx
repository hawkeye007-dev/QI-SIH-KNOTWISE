'use client';

import { PageHeader } from './PageHeader';
import React from 'react';
import { DemoData } from '@/types/demo';

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
  const benchmark = data.optimizer_benchmark;
  const predictor = data.fuel_predictor_benchmark;

  return (
    <div className="page-shell guide-page">
      <PageHeader category="Guide" title="The fleet decision, explained.">
        <p className="mt-2 text-base leading-relaxed text-[var(--text-secondary)]">
          Plain English, no maritime background assumed.
        </p>
      </PageHeader>

      <div className="space-y-5">
        <Section n={1} title="The problem">
          <p>
            The IMO, the UN body that regulates shipping, reconvenes on{' '}
            <strong className="text-[var(--text-primary)]">4 December 2026</strong> to decide a global carbon price
            for ships. Operators must lock in routes, speeds, fuels and shore power years before that vote, and
            those choices are worth very different amounts depending on the outcome.
          </p>
          <p>
            KnotWise solves the whole fleet plan for <em>every</em> possible outcome, then shows which decisions
            are genuinely safe and which are bets — priced, in rupees.
          </p>
        </Section>

        <Section n={2} title="What the optimizer decides">
          <p>
            For each of the {data.fleet.vessels.length} vessels in each year 2026–2030, it picks the route, speed
            band, fuel, shore power, and two FuelEU elections (pooling and borrowing):{' '}
            {data.fleet.vessels.length * 5 * 6} coupled decisions linked by fleet-wide cargo demand and the
            compliance pool. Every plan carries each route&apos;s cargo without exceeding any vessel&apos;s available
            sea days.
          </p>
        </Section>

        <Section n={3} title="Four regulations, priced together">
          <p>
            Four regimes priced together: the IMO&apos;s{' '}
            <strong className="text-[var(--text-primary)]">CII</strong> and{' '}
            <strong className="text-[var(--text-primary)]">Net-Zero Framework</strong>, plus{' '}
            <strong className="text-[var(--text-primary)]">FuelEU Maritime</strong> and the{' '}
            <strong className="text-[var(--text-primary)]">EU Emissions Trading System</strong>. EU regimes cover
            half of a voyage into or out of Europe and all of one inside it.
          </p>
        </Section>

        <Section n={4} title="Implementation guide">
          <p>
            <strong className="text-[var(--text-primary)]">Architecture.</strong> Next.js web app → Python REST API →
            optimizer (QIEA, with a GA baseline) + fuel-consumption model + four-regime compliance engine. Precomputed
            results ship as one JSON file; the live API re-solves on demand.
          </p>
          <pre className="overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--surface-sunken)] p-3 font-mono text-xs leading-relaxed text-[var(--text-primary)]">{`# 1. Backend (Python 3.11+)
pip install -e ".[dev]"
python -m knotwise.api.server          # http://127.0.0.1:8000

# 2. Rebuild precomputed results (optional)
python scripts/build_demo_data.py

# 3. Frontend
cd frontend && npm install
NEXT_PUBLIC_LIVE_API_BASE_URL=http://127.0.0.1:8000 npm run dev`}</pre>
          <p><strong className="text-[var(--text-primary)]">API.</strong> One endpoint re-solves the three comparable plans:</p>
          <pre className="overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--surface-sunken)] p-3 font-mono text-xs leading-relaxed text-[var(--text-primary)]">{`POST /api/recommendations
{ "carbon_price_usd_per_tco2e": 175,   // 0 – 1000
  "cargo_demand_multiplier": 1.0 }     // 0.1 – 10

→ 200 { "status": "SYNTHETIC_COMPARABLE_ALTERNATIVES", "alternatives": [...] }
→ 422 { "status": "INFEASIBLE", "reasons": [{ "message": "..." }] }
→ 400 { "status": "INVALID_REQUEST", "message": "..." }
GET /health → { "status": "ok" }`}</pre>
          <p>
            <strong className="text-[var(--text-primary)]">Your own fleet.</strong> Vessels, classes, routes, cargo demand and
            fuel properties live in <code className="font-mono">src/knotwise/fleet/fleet.json</code>, bunker prices in{' '}
            <code className="font-mono">prices.json</code>, each validated against its JSON schema. Replace them and rebuild.
          </p>
        </Section>

        <Section n={5} title="Provenance">
          <p>
            The fleet is a ten-vessel case study built on published vessel-class figures. Regulatory constants
            come from the regulation texts and bunker prices from dated market quotes, each with a retrieval date.
            The fuel-prediction benchmark uses synthetic telemetry.
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
