/** Read-only views over data the Python optimizer already produced.
 *
 *  The rule this module keeps: it **selects, groups and differences** values
 *  that `build_demo_data.py` serialized, and never re-derives a physical or
 *  financial quantity the optimizer owns. Fuel burn, lifecycle emissions,
 *  compliance cost and feasibility are read as-is; what happens here is
 *  counting decisions, pairing runs by seed, and subtracting two numbers the
 *  optimizer emitted under the same assumptions.
 */

import { DemoData, GridPointResult, ComparableAlternative, ScalingBenchmark } from '@/types/demo';

/** GHG intensity (gCO₂e/MJ) at or above which a fuel is a conventional
 *  residual/distillate bunker. VLSFO sits at 91.2, MGO at 90.6, HFO at 91.6;
 *  the cleanest alternative above this line does not exist, and the dirtiest
 *  below it is LNG at 76.0 — so the boundary is a genuine gap in the fuel
 *  catalog, not a tuned threshold. */
const CONVENTIONAL_INTENSITY_FLOOR = 85;

export interface FuelFacts {
  fuelId: string;
  ghgIntensity: number;
  lcvMjPerTonne: number;
  priceUsdPerTonne: number | null;
  isLowCarbon: boolean;
}

export function fuelCatalog(data: DemoData): FuelFacts[] {
  const fuels = data.fleet.fuel_properties?.fuels ?? {};
  const prices = data.prices?.fuels ?? {};
  return Object.entries(fuels as Record<string, { ghg_intensity_gco2e_per_mj: number; lcv_mj_per_tonne: number }>)
    .map(([fuelId, props]) => ({
      fuelId,
      ghgIntensity: props.ghg_intensity_gco2e_per_mj,
      lcvMjPerTonne: props.lcv_mj_per_tonne,
      priceUsdPerTonne: (prices[fuelId] as { price_usd_per_tonne?: number } | undefined)?.price_usd_per_tonne ?? null,
      isLowCarbon: props.ghg_intensity_gco2e_per_mj < CONVENTIONAL_INTENSITY_FLOOR,
    }))
    .sort((a, b) => b.ghgIntensity - a.ghgIntensity);
}

/** Vessel-year counts per fuel at one swept carbon price. */
export interface FuelMixPoint {
  price: number;
  counts: Record<string, number>;
  totalSlots: number;
  lowCarbonSlots: number;
}

export function fuelMixByPrice(data: DemoData): FuelMixPoint[] {
  const lowCarbon = new Set(fuelCatalog(data).filter(f => f.isLowCarbon).map(f => f.fuelId));
  return data.sweep.grid_points.map(point => {
    const counts: Record<string, number> = {};
    point.configuration.forEach(gene => {
      counts[gene.fuel_id] = (counts[gene.fuel_id] ?? 0) + 1;
    });
    const lowCarbonSlots = point.configuration.filter(gene => lowCarbon.has(gene.fuel_id)).length;
    return { price: point.price_usd_per_tco2e, counts, totalSlots: point.configuration.length, lowCarbonSlots };
  });
}

/** Every fuel that wins at least one vessel-year somewhere in the sweep,
 *  ordered dirtiest-first so a stacked chart reads as "fossil at the bottom,
 *  alternatives rising above it". */
export function fuelsElectedInSweep(data: DemoData): string[] {
  const mix = fuelMixByPrice(data);
  const elected = new Set<string>();
  mix.forEach(point => Object.keys(point.counts).forEach(fuelId => elected.add(fuelId)));
  return fuelCatalog(data)
    .filter(fuel => elected.has(fuel.fuelId))
    .map(fuel => fuel.fuelId);
}

/** The lowest swept carbon price at which the optimizer first elects each
 *  fuel — the price that fuel has to "wait for" before it pays for itself
 *  anywhere in this fleet. `null` for a fuel already in the $0/t plan, and a
 *  fuel never elected is simply absent. */
export function fuelEntryPrices(data: DemoData): Record<string, number | null> {
  const mix = fuelMixByPrice(data);
  const entry: Record<string, number | null> = {};
  mix.forEach(point => {
    Object.keys(point.counts).forEach(fuelId => {
      if (!(fuelId in entry)) entry[fuelId] = point.price === 0 ? null : point.price;
    });
  });
  return entry;
}

/** Emissions and fuel outcome of one swept plan against the $0/t plan.
 *  Both sides come from the optimizer's own `metrics`, so this is a
 *  subtraction, not a re-scoring. */
export interface ClimateDelta {
  emissionsTco2e: number;
  emissionsDeltaTco2e: number;
  emissionsDeltaFraction: number;
  fuelTonnes: number;
  fuelDeltaTonnes: number;
  fuelDeltaFraction: number;
  lowCarbonShare: number;
  baselineLowCarbonShare: number;
}

export function climateDelta(data: DemoData, point: GridPointResult | null): ClimateDelta | null {
  const baseline = data.sweep.grid_points.find(p => p.price_usd_per_tco2e === 0) ?? data.sweep.grid_points[0];
  if (!point?.metrics || !baseline?.metrics) return null;
  const mix = fuelMixByPrice(data);
  const shareAt = (price: number) => {
    const found = mix.find(m => m.price === price);
    return found && found.totalSlots > 0 ? found.lowCarbonSlots / found.totalSlots : 0;
  };
  const emissionsDelta = point.metrics.lifecycle_emissions_tco2e - baseline.metrics.lifecycle_emissions_tco2e;
  const fuelDelta = point.metrics.fuel_tonnes - baseline.metrics.fuel_tonnes;
  return {
    emissionsTco2e: point.metrics.lifecycle_emissions_tco2e,
    emissionsDeltaTco2e: emissionsDelta,
    emissionsDeltaFraction: emissionsDelta / baseline.metrics.lifecycle_emissions_tco2e,
    fuelTonnes: point.metrics.fuel_tonnes,
    fuelDeltaTonnes: fuelDelta,
    fuelDeltaFraction: fuelDelta / baseline.metrics.fuel_tonnes,
    lowCarbonShare: shareAt(point.price_usd_per_tco2e),
    baselineLowCarbonShare: shareAt(baseline.price_usd_per_tco2e),
  };
}

/** The deepest lifecycle-GHG cut anywhere in the sweep, against the $0/t
 *  plan. Price-independent: emissions are a property of the plan, not of the
 *  carbon price it was selected under. */
export function deepestCut(data: DemoData): { point: GridPointResult; deltaFraction: number; deltaTco2e: number } | null {
  const points = data.sweep.grid_points.filter(p => p.metrics);
  const baseline = points.find(p => p.price_usd_per_tco2e === 0) ?? points[0];
  if (!baseline?.metrics || points.length === 0) return null;
  const best = points.reduce((a, b) =>
    (b.metrics?.lifecycle_emissions_tco2e ?? Infinity) < (a.metrics?.lifecycle_emissions_tco2e ?? Infinity) ? b : a
  );
  if (!best.metrics) return null;
  const delta = best.metrics.lifecycle_emissions_tco2e - baseline.metrics.lifecycle_emissions_tco2e;
  return { point: best, deltaTco2e: delta, deltaFraction: delta / baseline.metrics.lifecycle_emissions_tco2e };
}

/** Marginal abatement cost between consecutive alternatives, ordered
 *  dirtiest-first. Both plans in each pair were solved and scored under the
 *  *same* carbon price and demand, which is what makes the ratio meaningful.
 */
export interface AbatementStep {
  from: ComparableAlternative;
  to: ComparableAlternative;
  deltaCostUsd: number;
  deltaEmissionsTco2e: number;
  usdPerTonneAbated: number;
}

export function abatementLadder(alternatives: ComparableAlternative[]): {
  ordered: ComparableAlternative[];
  steps: AbatementStep[];
} {
  const ordered = [...alternatives].sort(
    (a, b) => b.metrics.lifecycle_emissions_tco2e - a.metrics.lifecycle_emissions_tco2e
  );
  const steps: AbatementStep[] = [];
  for (let i = 0; i < ordered.length - 1; i++) {
    const from = ordered[i];
    const to = ordered[i + 1];
    const deltaCostUsd = to.metrics.total_usd - from.metrics.total_usd;
    const deltaEmissionsTco2e = from.metrics.lifecycle_emissions_tco2e - to.metrics.lifecycle_emissions_tco2e;
    steps.push({
      from,
      to,
      deltaCostUsd,
      deltaEmissionsTco2e,
      usdPerTonneAbated: deltaEmissionsTco2e > 0 ? deltaCostUsd / deltaEmissionsTco2e : 0,
    });
  }
  return { ordered, steps };
}

/** GA and QIEA paired by (fleet size, seed) — the only comparison the
 *  scaling records support, since the two solvers share a seed within a pair
 *  and nothing else. Reported as a median over seeds so one lucky run cannot
 *  carry a fleet size. */
export interface PairedScaleResult {
  vesselCount: number;
  decisionSlots: number;
  pairedRuns: number;
  qieaLowerRuns: number;
  medianQieaMinusGaFraction: number;
  medianGaSeconds: number;
  medianQieaSeconds: number;
}

const median = (values: number[]) => {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
};

export function pairedScaleResults(benchmark: ScalingBenchmark): PairedScaleResult[] {
  const bySize = new Map<number, Map<number, { ga?: number; qiea?: number; gaSec?: number; qieaSec?: number; slots: number }>>();
  benchmark.records.forEach(record => {
    if (!bySize.has(record.vessel_count)) bySize.set(record.vessel_count, new Map());
    const seeds = bySize.get(record.vessel_count)!;
    const entry = seeds.get(record.seed) ?? { slots: record.decision_slots };
    if (record.solver === 'ga') {
      entry.ga = record.total_usd;
      entry.gaSec = record.seconds;
    } else {
      entry.qiea = record.total_usd;
      entry.qieaSec = record.seconds;
    }
    seeds.set(record.seed, entry);
  });

  return [...bySize.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([vesselCount, seeds]) => {
      const pairs = [...seeds.values()].filter(entry => entry.ga != null && entry.qiea != null);
      const deltas = pairs.map(entry => (entry.qiea! - entry.ga!) / entry.ga!);
      return {
        vesselCount,
        decisionSlots: pairs[0]?.slots ?? 0,
        pairedRuns: deltas.length,
        qieaLowerRuns: deltas.filter(delta => delta < 0).length,
        medianQieaMinusGaFraction: median(deltas),
        medianGaSeconds: median(pairs.map(entry => entry.gaSec ?? 0)),
        medianQieaSeconds: median(pairs.map(entry => entry.qieaSec ?? 0)),
      };
    });
}

/** Headline across every fleet size: the narrowest and widest median paired
 *  advantage, and whether it held on every single run. */
export function scaleAdvantageSummary(rows: PairedScaleResult[]) {
  const gains = rows.map(row => -row.medianQieaMinusGaFraction);
  const totalRuns = rows.reduce((sum, row) => sum + row.pairedRuns, 0);
  const totalWins = rows.reduce((sum, row) => sum + row.qieaLowerRuns, 0);
  return {
    minGainFraction: Math.min(...gains),
    maxGainFraction: Math.max(...gains),
    smallestFleet: rows[0]?.vesselCount ?? 0,
    largestFleet: rows[rows.length - 1]?.vesselCount ?? 0,
    largestSlots: rows[rows.length - 1]?.decisionSlots ?? 0,
    totalRuns,
    totalWins,
    sweptEveryRun: totalRuns > 0 && totalWins === totalRuns,
  };
}
