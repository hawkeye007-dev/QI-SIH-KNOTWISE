'use client';

import katex from 'katex';
import 'katex/dist/katex.min.css';
import { ReactNode } from 'react';
import { PageHeader } from './PageHeader';
import { DemoData } from '@/types/demo';
import { FUEL_NAMES, ROUTE_NAMES, VESSEL_CLASS_NAMES } from '@/lib/labels';

/** Typeset one LaTeX expression. Every expression on this page is a constant
 *  written here, never user input. */
const Tex = ({ math }: { math: string }) => (
  <span dangerouslySetInnerHTML={{ __html: katex.renderToString(math, { throwOnError: false }) }} />
);

/** A labelled display equation: name on the left, formula on the right. */
const Equation = ({ label, math, note }: { label: string; math: string; note?: string }) => (
  <div className="grid gap-1 border-t border-[var(--border)] py-3 first:border-t-0 sm:grid-cols-[170px_1fr] sm:items-center sm:gap-6">
    <div>
      <div className="text-sm font-semibold text-[var(--text-primary)]">{label}</div>
      {note && <div className="text-xs text-[var(--text-tertiary)]">{note}</div>}
    </div>
    <div className="overflow-x-auto py-1 text-[1.05rem] text-[var(--text-primary)]">
      <Tex math={`\\displaystyle ${math}`} />
    </div>
  </div>
);

const Block = ({ n, title, children }: { n: number; title: string; children: ReactNode }) => (
  <section className="metric-card">
    <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-[var(--text-primary)]">
      <span className="mr-2 text-[var(--text-tertiary)]">{n}</span>
      {title}
    </h2>
    <div className="text-sm leading-relaxed text-[var(--text-secondary)]">{children}</div>
  </section>
);

const SYMBOLS: [string, string][] = [
  ['m_{vy}', 'fuel burned (t), from the prediction model'],
  ['\\mathrm{LCV}_f,\\ \\mathrm{WtW}_f', 'fuel energy content (MJ/t) and well-to-wake intensity (tCO₂e/MJ)'],
  ['\\lambda', 'carbon price ($/tCO₂e)'],
  ['\\varepsilon', 'lifecycle-GHG cap'],
  ['\\mathrm{DWT}_v', 'vessel deadweight (t)'],
  ['u_r,\\ \\ell_r', 'route payload utilisation and laden share'],
  ['d_r,\\ D_r', 'annual route distance (nm) and cargo demand (t·nm)'],
  ['k', 'cargo-demand multiplier (1.0 in the plans shown)'],
  ['\\sigma_s', 'speed of band s (knots)'],
  ['A_v', 'service days available per year'],
];

export function FormulationView({ data }: { data: DemoData }) {
  const vessels = data.fleet.vessels;
  const years = data.fleet.horizon_years as number[];
  const classes = Object.entries(data.fleet.vessel_class_defaults) as [string, { dwt_tonnes: number }][];
  const routes = Object.keys(data.fleet.routes);
  const fuels = Object.keys(data.fleet.fuel_properties.fuels);
  const slots = vessels.length * years.length;

  const sets: [string, string][] = [
    ['v \\in V', `${vessels.length} vessels: ${classes.map(([id, c]) => `${VESSEL_CLASS_NAMES[id] ?? id} (${c.dwt_tonnes.toLocaleString()} DWT)`).join(', ')}`],
    ['y \\in Y', `years ${years[0]}–${years[years.length - 1]}`],
    ['r \\in R', `${routes.length} routes: ${routes.map(r => ROUTE_NAMES[r] ?? r).join(', ')}`],
    ['f \\in F', `${fuels.length} fuels: ${fuels.map(f => FUEL_NAMES[f] ?? f).join(', ')}`],
    ['s \\in S', 'cruising-speed bands, as fractions of design speed'],
  ];

  return (
    <div className="page-shell">
      <PageHeader category="Formulation" title="The optimization model, written down.">
        <p className="mt-2 text-base leading-relaxed text-[var(--text-secondary)]">
          A multi-objective, mixed-categorical program over {slots} vessel-years and {slots * 6} coupled decisions.
          Every plan on this site is a solution of this model.
        </p>
      </PageHeader>

      <div className="space-y-5">
        <Block n={1} title="Sets">
          <dl className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
            {sets.map(([symbol, meaning]) => (
              <div key={symbol} className="flex gap-3">
                <dt className="w-16 shrink-0 text-[var(--text-primary)]"><Tex math={symbol} /></dt>
                <dd>{meaning}</dd>
              </div>
            ))}
          </dl>
        </Block>

        <Block n={2} title="Decision variables">
          <Equation
            label="Per vessel-year"
            note="route, speed, fuel, shore power, FuelEU pool, borrow"
            math="x_{vy} = \big(r_{vy},\ s_{vy},\ f_{vy},\ o_{vy},\ p_{vy},\ b_{vy}\big) \in R \times S \times F \times \{0,1\}^3"
          />
          <p className="mt-2">
            Assigning each vessel, and so its capacity, to a route is how the model allocates fleet capacity across trades.
          </p>
        </Block>

        <Block n={3} title="Objectives">
          <Equation
            label="Total cost"
            note="bunkers, OPEX, time + four regimes"
            math="\min_x\ C(x) = \sum_{v,y}\big(c^{\mathrm{fuel}}_{vy} + c^{\mathrm{opex}}_{vy} + c^{\mathrm{time}}_{vy}\big) + \sum_{y}\big(\mathrm{CII}_y + \mathrm{NZF}_y(\lambda) + \mathrm{FuelEU}_y + \mathrm{ETS}_y\big)"
          />
          <Equation
            label="Fuel consumption"
            note="tonnes"
            math="\min_x\ M(x) = \sum_{v,y} m_{vy}\big(s_{vy}, f_{vy}, r_{vy}\big)"
          />
          <Equation
            label="Lifecycle GHG"
            note="tCO₂e, well-to-wake"
            math="\min_x\ E(x) = \sum_{v,y} m_{vy}\,\mathrm{LCV}_{f_{vy}}\,\mathrm{WtW}_{f_{vy}}"
          />
          <Equation
            label="Trade-off"
            note="price sweep and ε-constraint"
            math="\min_x\ C_\lambda(x),\ \ \lambda \in \{0, 25, \dots, 1000\} \qquad\text{and}\qquad \min_x\ C(x)\ \ \text{s.t.}\ \ E(x) \le \varepsilon"
          />
          <p className="mt-2">
            The {data.sweep.grid_points.length}-price sweep on Sensitivity varies λ; the ε-cap produces the Balanced and
            Greenest plans on Plans. Fuel mass enters cost through the bunker bill.
          </p>
        </Block>

        <Block n={4} title="Constraints">
          <Equation
            label="Cargo demand"
            note="every route, every year"
            math="\sum_{v\,:\,r_{vy}=r} \mathrm{DWT}_v\,u_r\,\ell_r\,d_r \;\ge\; k\,D_r \qquad \forall\, r, y"
          />
          <Equation
            label="Schedule"
            note="sea + port days"
            math="\frac{d_{r_{vy}}}{24\,\sigma_{s_{vy}}} + \mathrm{port}_{r_{vy}} \;\le\; A_v \qquad \forall\, v, y"
          />
          <Equation
            label="Compatibility"
            math="f_{vy} \in F(\mathrm{engine}_v), \qquad s_{vy} \in S(v, r_{vy}, y)"
          />
          <Equation
            label="Emission limit"
            note="Balanced / Greenest"
            math="E(x) \le \varepsilon"
          />
          <Equation
            label="Regulation"
            note="per vessel, year, voyage"
            math="\mathrm{CII},\ \mathrm{NZF},\ \mathrm{FuelEU},\ \mathrm{ETS}\ \text{scope and rating rules}"
          />
          <p className="mt-2">Plans that break cargo or schedule constraints are rejected, never returned.</p>
        </Block>

        <Block n={5} title="Symbols">
          <dl className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
            {SYMBOLS.map(([symbol, meaning]) => (
              <div key={symbol} className="flex gap-3">
                <dt className="w-28 shrink-0 text-[var(--text-primary)]"><Tex math={symbol} /></dt>
                <dd>{meaning}</dd>
              </div>
            ))}
          </dl>
        </Block>

        <Block n={6} title="Scope and next extension">
          <p>
            The fleet itself is fixed at {vessels.length} vessels. Choosing how many vessels of each class and capacity to
            own or charter (fleet composition) is the next extension: one more categorical variable per vessel-year,
            costed by the fixed-OPEX and charter-premium terms the model already carries.
          </p>
        </Block>
      </div>
    </div>
  );
}
