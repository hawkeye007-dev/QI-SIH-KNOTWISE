export interface RouteWaypoint {
  name: string;
  band: string;
  waypoints: [number, number][];
}

export interface RoutesGeo {
  status: string;
  provenance_note: string;
  routes: Record<string, RouteWaypoint>;
}

export interface FleetVessel {
  vessel_id: string;
  band: string;
  engine_type: string;
  default_route: string;
}

export interface VesselYearGene {
  vessel_id: string;
  year: number;
  route_id: string;
  speed_band_index: number;
  fuel_id: string;
  shore_power: boolean;
  pool_opt_in: boolean;
  borrow_election: boolean;
}

export interface GridPointResult {
  price_usd_per_tco2e: number;
  total_usd: number;
  solve_seconds: number;
  warm_started: boolean;
  generations_run: number;
  configuration: VesselYearGene[];
}

export interface SwitchingPoint {
  vessel_id: string;
  year: number;
  decision: string;
  from_value: any;
  to_value: any;
  price_low_usd_per_tco2e: number;
  price_high_usd_per_tco2e: number;
}

export interface ScenarioAxisPosition {
  scenario_id: string;
  label: string;
  kind: string;
  low_usd_per_tco2e: number | null;
  high_usd_per_tco2e: number | null;
  operating_point_usd_per_tco2e: number | null;
  status: string;
  notes: string;
}

export interface BaselineCounterfactualPoint {
  price_usd_per_tco2e: number;
  /** The $0/t plan re-costed at this price, never revised. */
  frozen_total_usd: number;
  optimized_total_usd: number;
  /** frozen − optimized: what re-planning is worth at this price. */
  saving_usd: number;
}

export interface SweepData {
  baseline_counterfactual?: {
    description: string;
    points: BaselineCounterfactualPoint[];
  };
  price_grid: number[];
  resolution_usd_per_tco2e: number;
  grid_points: GridPointResult[];
  switching_points: SwitchingPoint[];
  scenario_ticks: ScenarioAxisPosition[];
  warm_start_benchmark: any;
  flip_activity_by_bracket: any[];
}

export interface ExposureData {
  plan_spread: {
    description: string;
    max_scenario_id: string;
    min_scenario_id: string;
    spread_usd: number;
    spread_inr: number;
    scenario_totals_usd: Record<string, number>;
  };
  capex_exposure: {
    description: string;
    total_usd: number;
    total_inr: number;
    decisions: any[];
  };
  majority_capex_exposure: {
    description: string;
    total_usd: number;
    total_inr: number;
    decisions: any[];
  };
  per_decision_deltas: {
    description: string;
    decisions: any[];
  };
  unstable_decisions: {
    count: number;
    description: string;
    decisions: Array<{ vessel_id: string; year: number; decision: string }>;
  };
  /** PLAN.md §8.3(b)'s crosscheck: real tensor-network mutual information
   *  (mps_exposure.py) against this run's own classical flip-counting
   *  result, for the same (vessel_id, year) slots this run already flagged.
   *  Optional -- absent on a demo_data.json built before this was wired in. */
  mps_crosscheck?: {
    description: string;
    rows: Array<{
      vessel_id: string;
      year: number;
      decision: string;
      mutual_information_bits: number;
      classical_status: 'exposed' | 'unstable' | 'not_exposed';
    }>;
  };
  majority_band: {
    description: string;
    decisions: any[];
    unstable_decisions: { count: number; decisions: any[] };
  };
  summary: {
    stable_exposed_decision_count: number;
    unstable_decision_count: number;
    majority_band_decision_count: number;
    majority_unstable_decision_count: number;
    plan_spread_usd: number;
    plan_spread_inr: number;
    capex_exposure_usd: number;
    capex_exposure_inr: number;
    majority_capex_exposure_usd: number;
    majority_capex_exposure_inr: number;
  };
  fx: {
    usd_to_inr_rate: number;
    status: string;
    retrieval_date: string;
    notes: string;
  };
  consistency_checks: any[];
}

export interface DemoData {
  metadata: {
    generated_at: string;
    total_build_seconds: number;
    status_disclaimer: string;
    provenance: string;
    /** Which solver produced every plan in this file: 'ga' or 'qiea'. */
    optimizer: string;
  };
  routes_geo: RoutesGeo;
  fleet: {
    vessels: FleetVessel[];
    vessel_class_defaults: Record<string, any>;
    routes: Record<string, any>;
    [key: string]: any;
  };
  prices: any;
  sweep: SweepData;
  exposure: ExposureData;
  optimizer_benchmark: OptimizerBenchmark;
}

/** One arm of the initialization ablation: N independent runs of the QIEA
 *  search at fixed settings, summarized by their total-cost distribution. */
export interface AblationArm {
  mean_total_usd: number;
  best_total_usd: number;
  worst_total_usd: number;
  n_runs: number;
}

/** Per-solver results from a GA-vs-QIEA head-to-head at matched settings. */
export interface OptimizerRun {
  optimizer: string;
  sweep_seconds: number;
  exposure_seconds: number;
  total_seconds: number;
  n_grid_points: number;
  n_switching_points: number;
  n_envelope_corrected: number;
  min_total_usd_across_grid: number;
  max_total_usd_across_grid: number;
  plan_spread_usd: number;
  plan_spread_inr_crore: number;
  n_unanimous_exposed: number;
  n_unanimous_unstable: number;
}

export interface SearchAttribution {
  description: string;
  mechanism: string;
  finding: string;
  raw_search_polish_disabled: { uniform_init: AblationArm; mean_field_init: AblationArm };
  end_to_end_polish_enabled: { uniform_init: AblationArm; mean_field_init: AblationArm };
  raw_search_improvement_fraction: number;
  end_to_end_improvement_fraction: number;
  settings: Record<string, any>;
}

/** `build_demo_data.py` deliberately gives "benchmark was never run" a defined
 *  shape rather than omitting the key, so a consumer never has to tell absent
 *  from zero. Modelled as a union on `available` so the UI must handle both. */
export type OptimizerBenchmark =
  | {
      available: false;
      status: 'NOT_AVAILABLE';
      demo_built_with_optimizer: string;
      notes: string;
    }
  | {
      available: true;
      status: string;
      generated_at: string;
      provenance_note: string;
      note: string;
      demo_built_with_optimizer: string;
      freshness_note: string;
      price_grid: number[];
      sweep_kwargs: Record<string, number>;
      exposure_kwargs: Record<string, any>;
      ga: OptimizerRun;
      qiea: OptimizerRun;
      search_attribution: SearchAttribution;
    };
