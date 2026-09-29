import { seriesColor } from './Charts';

/** Illustrative register contents: real field domains, example probabilities.
 *  The update panel applies the solver's exact rotation rule to these numbers. */
const REGISTERS: { field: string; outcomes: string[]; probs: number[]; observed: number }[] = [
  { field: 'Route', outcomes: ['N. Europe', 'Med', 'Gulf'], probs: [0.5, 0.3, 0.2], observed: 0 },
  { field: 'Speed band', outcomes: ['3', '4', '5'], probs: [0.25, 0.5, 0.25], observed: 1 },
  { field: 'Fuel', outcomes: ['VLSFO', 'B30', 'NH₃'], probs: [0.4, 0.35, 0.25], observed: 1 },
  { field: 'Shore power', outcomes: ['No', 'Yes'], probs: [0.7, 0.3], observed: 0 },
  { field: 'FuelEU pool', outcomes: ['No', 'Yes'], probs: [0.45, 0.55], observed: 1 },
  { field: 'Borrowing', outcomes: ['No', 'Yes'], probs: [0.8, 0.2], observed: 0 },
];

const LEARNING_RATE = 0.3;

/** `qiea_solver._rotate_toward`: shrink every outcome by (1 − η), then pull
 *  the target up by η of its remaining gap. The result stays normalized. */
const rotate = (probs: number[], target: number, eta: number) =>
  probs.map((p, i) => (i === target ? p + eta * (1 - p) : p * (1 - eta)));

const Bars = ({ outcomes, probs, highlight, color }: { outcomes: string[]; probs: number[]; highlight?: number; color: string }) => (
  <div className="space-y-1">
    {outcomes.map((label, i) => (
      <div key={label} className="flex items-center gap-2 text-xs">
        <span className={`w-16 shrink-0 truncate ${i === highlight ? 'font-semibold text-[var(--text-primary)]' : 'text-[var(--text-tertiary)]'}`}>{label}</span>
        <span className="h-2 flex-1 rounded-sm bg-[var(--surface-sunken)]">
          <span className="block h-2 rounded-sm" style={{ width: `${probs[i] * 100}%`, background: color, opacity: i === highlight ? 1 : 0.45 }} />
        </span>
        <span className="w-9 text-right font-mono text-[var(--text-secondary)]">{probs[i].toFixed(2)}</span>
      </div>
    ))}
  </div>
);

export function QuantumEncodingDiagram() {
  const color = seriesColor(0);
  const fuel = REGISTERS[2];
  const target = 1;
  const after = rotate(fuel.probs, target, LEARNING_RATE);

  return (
    <div className="mt-5 grid gap-5 lg:grid-cols-[1.6fr_1fr]">
      <figure className="rounded-lg border border-[var(--border)] p-4">
        <figcaption className="mb-3 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
          Encoding: one vessel-year (A1 · 2028) = six qudit registers
        </figcaption>
        <div className="grid gap-4 sm:grid-cols-3">
          {REGISTERS.map(reg => (
            <div key={reg.field}>
              <div className="mb-1.5 text-xs font-semibold text-[var(--text-primary)]">{reg.field}</div>
              <Bars outcomes={reg.outcomes} probs={reg.probs} highlight={reg.observed} color={color} />
            </div>
          ))}
        </div>
        <div className="mt-4 border-t border-[var(--border)] pt-3 text-xs leading-relaxed text-[var(--text-secondary)]">
          <strong className="text-[var(--text-primary)]">Observe →</strong> sample each register once to get a concrete plan slot:{' '}
          <span className="font-mono text-[var(--text-primary)]">
            ({REGISTERS.map(reg => reg.outcomes[reg.observed]).join(', ')})
          </span>
          . A full fleet plan is {`10 vessels × 5 years`} of these, scored by the cost model.
        </div>
      </figure>

      <figure className="rounded-lg border border-[var(--border)] p-4">
        <figcaption className="mb-3 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
          Quantum update: rotate toward an elite plan
        </figcaption>
        <div className="mb-1 text-xs text-[var(--text-secondary)]">Fuel register before (elite plan chose B30)</div>
        <Bars outcomes={fuel.outcomes} probs={fuel.probs} highlight={target} color={color} />
        <div className="my-2 text-center font-mono text-xs text-[var(--text-tertiary)]">↓ rotation, η = {LEARNING_RATE}</div>
        <Bars outcomes={fuel.outcomes} probs={after} highlight={target} color={color} />
        <div className="mt-3 rounded-md bg-[var(--surface-sunken)] px-3 py-2 font-mono text-xs leading-relaxed text-[var(--text-primary)]">
          p<sub>t</sub> ← p<sub>t</sub> + η(1 − p<sub>t</sub>)
          <br />p<sub>k</sub> ← (1 − η) p<sub>k</sub>, k ≠ t
        </div>
        <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">
          The quantum-inspired start sets p ∝ exp(−cost / T) from each slot&apos;s own cost table. η anneals upward and a
          probability floor keeps every option reachable.
        </p>
      </figure>
    </div>
  );
}
