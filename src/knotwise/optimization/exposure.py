"""Exposure by flip-counting, priced in rupees (Task 2R component 5,
prototype version — implements PLAN.md §3.1's Exposure Map via §8.3(b)'s
classical validation method: "retraining per scenario and counting how often
each decision flips").

A decision is **exposed** if its optimal value differs across the K=5
scenario-optimal fleet plans (`solve_scenario`, component 4). Two integrity
requirements shape this module beyond the basic flip-count, both added after
review of the first version's numbers:

**Stability first (PLAN §8.3(c)'s principle, applied to GA seed variance).**
Every scenario is independently re-solved under `DEFAULT_STABILITY_SEEDS`
before anything is called "exposed" — at this component's original default
budget (population 40, 30 generations), roughly half of all decisions
disagreed between two runs of the *same* scenario differing only in random
seed, which would have made most of the original "113 exposed decisions"
uninterpretable GA noise rather than a real reading of the vote's economics.
A decision is reported only when every seed agrees on its value within each
scenario it's evaluated under; where seeds disagree, it's reported as
*unstable* and excluded from the exposed count instead of silently kept in
or silently dropped. Raising the GA's population/generation budget alone
does not make this go away past a point — even at population 300 (vs. the
default 200), the per-scenario two-seed disagreement rate on this fleet
plateaus around 38% rather than reaching zero, because a real fraction of
decisions sit in genuinely near-tied cost regions where multiple choices
cost almost the same; the stability filter is reporting that honestly
rather than an under-convergence artifact to be brute-forced away.

Requiring *unanimous* agreement across all `len(DEFAULT_STABILITY_SEEDS)`
seeds, independently in *every one* of the K=5 scenarios, compounds that
per-scenario rate into a much stricter bar than it looks at first: a
one-off production run at the full defaults (population 200, 200
generations, 3 seeds) on this fleet found only **2 of ~200 candidate
decisions stable enough to report as exposed** — the other 198 disagreed
across seeds somewhere in at least one scenario. That is not a bug in the
filter; it is the filter doing its job. It also means the "N stable exposed
decisions" count should be read as a lower bound produced by a strict,
honest criterion, not as "how many decisions the vote could plausibly
move" — a softer criterion (e.g. majority-of-seeds agreement) would surface
more decisions at the cost of weaker confidence in each one; this version
takes the stricter reading deliberately.

**Three outputs, not one summed total.** Per-decision capital-at-risk
figures are independent marginal deltas — each computed against the same
baseline plan with only *that one* decision swapped — and are not mutually
exclusive costs, so summing them across decision types double-counts
overlapping risk and mixes one-time capex with recurring opex-shaped deltas
(this module's first version did exactly that, and the resulting total
exceeded the entire fleet's five-year operating cost, which was the tell).
This version instead reports:

1. `plan_spread` — PLAN §3.1's actual headline "cost of regulatory
   uncertainty" number: max minus min of the K=5 scenarios' own
   *scenario-optimal total plan costs*. A single, non-overlapping figure.
2. `capex_exposure` — PLAN §3.1/§9.3's "X crore of capex is contingent on
   the vote" figure: capital-commitment decisions only. This prototype's
   genome models exactly one such decision (shore-power election); there is
   no `retrofit_year` variable yet (PLAN.md §5.4/Track F), so retrofit-type
   capex isn't represented here and the note says so.
3. `per_decision_deltas` — every stable exposed decision, all types, for
   drill-down tables only, carrying an explicit "do not sum" note.

Component 4's carbon-price sweep gives a free cross-check: since every
scenario in scenarios.json differs from the others only in its NZF
treatment, a decision that flips between two scenarios ought to have a
matching switching point somewhere between those scenarios' axis positions
in the sweep. Where it doesn't, that's a finding (a GA-convergence gap, or
an axis position built from a mechanism the uniform-price sweep doesn't
capture) reported rather than hidden.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from itertools import combinations
from typing import Any

from knotwise.fleet.model import option_menu_for
from knotwise.optimization.constraints import demand_shortfall_penalty
from knotwise.optimization.fuel_model import FuelModel, PhysicsFuelModel, sea_days
from knotwise.optimization.genome import Genome
from knotwise.optimization.objective import evaluate
from knotwise.optimization.sweep import (
    DECISION_FIELDS,
    ScenarioAxisPosition,
    SweepResult,
    solve_scenario,
)
from knotwise.regulatory.loader import load_scenarios
from knotwise.regulatory.scenario_resolution import resolve_regulations_for_scenario

#: The scenario whose solved plan supplies "everything else held fixed" when
#: pricing one decision's flip — the currently-approved regulatory text, i.e.
#: today's expected plan, not an arbitrary or averaged one.
BASELINE_SCENARIO_ID = "approved_text"

#: Stability-filter defaults (PLAN §8.3(c)'s principle): each scenario is
#: solved under every one of these seeds independently before a decision's
#: value is trusted. Expensive at these settings (see `solve_scenario_with_
#: stability`'s docstring) — meant for an offline run, not routine test use;
#: tests pass smaller values explicitly.
DEFAULT_STABILITY_SEEDS: tuple[int, ...] = (0, 1, 2)
DEFAULT_STABILITY_POPULATION_SIZE = 200
DEFAULT_STABILITY_GENERATIONS = 200


@dataclass(frozen=True)
class ExposedDecision:
    vessel_id: str
    year: int
    decision: str
    values_by_scenario: dict[str, Any]
    capital_at_risk_usd: float
    capital_at_risk_status: str
    capital_at_risk_notes: str


@dataclass(frozen=True)
class ConsistencyCheck:
    """One scenario-pair cross-check of an exposed decision's flip against
    component 4's sweep (Task 2R component 5, item 4 — "PLAN §8.3(b)'s
    validation logic in miniature").

    `consistent` is `None` when the check isn't possible at all (one or both
    scenarios has no computed axis position) — distinct from `False`, which
    means the check *was* run and the sweep didn't corroborate the flip.
    """

    vessel_id: str
    year: int
    decision: str
    scenario_low: str
    scenario_high: str
    axis_low_usd_per_tco2e: float | None
    axis_high_usd_per_tco2e: float | None
    consistent: bool | None
    notes: str


@dataclass(frozen=True)
class UnstableDecision:
    """A vessel-year decision where `DEFAULT_STABILITY_SEEDS` (or whatever
    `seeds` was passed) disagreed on the optimal value *within* at least one
    scenario -- not a finding about the vote, a finding about the search
    not having converged to a single answer at this GA budget."""

    vessel_id: str
    year: int
    decision: str


@dataclass(frozen=True)
class PlanSpread:
    """PLAN §3.1's headline "cost of regulatory uncertainty" figure: the
    spread between the most and least expensive of the K=5 scenario-optimal
    total plan costs. A single, non-overlapping number -- not a sum of
    per-decision deltas."""

    scenario_totals_usd: dict[str, float]
    max_scenario_id: str
    min_scenario_id: str
    spread_usd: float
    spread_inr: float


@dataclass(frozen=True)
class CapexExposure:
    """PLAN §3.1/§9.3's "X crore of capex is contingent on the vote" figure:
    capital-commitment decisions only, summed (unlike `per_decision_deltas`,
    these genuinely are mutually exclusive per-vessel-year elections, so
    summing them is legitimate)."""

    decisions: list[ExposedDecision]
    total_usd: float
    total_inr: float


@dataclass(frozen=True)
class ExposureResult:
    scenario_ids: list[str]
    stability_seeds: tuple[int, ...]
    ga_population_size: int
    ga_generations: int
    plan_spread: PlanSpread
    capex_exposure: CapexExposure
    per_decision_deltas: list[ExposedDecision]
    unstable_decisions: list[UnstableDecision]
    majority_band_decisions: list[ExposedDecision]
    majority_unstable_decisions: list[UnstableDecision]
    fx_rate_usd_to_inr: float
    fx_status: str
    fx_retrieval_date: str
    fx_notes: str
    consistency_checks: list[ConsistencyCheck]
    majority_band_consistency_checks: list[ConsistencyCheck]


@dataclass(frozen=True)
class ScenarioStabilitySolve:
    """One scenario's result across every stability seed: the best (lowest-
    cost) seed's genome/cost stand in as "the" scenario-optimal plan (same
    role `solve_scenario`'s single result played before), plus which
    vessel-year decisions the seeds didn't all agree on (`unstable_keys`,
    the unanimous/headline criterion) and, separately, the value at least a
    majority of seeds agreed on where one exists (`majority_values`, the
    looser drill-down criterion — PLAN §8.3(c)'s stability flag reported at
    two thresholds rather than loosened outright, per review)."""

    scenario_id: str
    best_genome: Genome
    best_total_usd: float
    per_seed_total_usd: dict[int, float]
    unstable_keys: frozenset[tuple[str, int, str]]
    majority_values: dict[tuple[str, int, str], Any]


def stability_from_per_seed_genomes(genomes_by_seed: dict[int, Genome]) -> frozenset[tuple[str, int, str]]:
    """The pure part of the stability filter: given each seed's genome for
    one scenario, which (vessel_id, year, decision) keys do the seeds
    disagree on. Factored out from `solve_scenario_with_stability` so it's
    directly unit-testable against hand-built genomes, without paying for a
    real GA solve just to exercise the disagreement logic."""
    seeds = list(genomes_by_seed)
    genes_by_seed_by_key = {
        seed: {(gene.vessel_id, gene.year): gene for gene in genome} for seed, genome in genomes_by_seed.items()
    }
    keys = list(genes_by_seed_by_key[seeds[0]])

    unstable_keys: set[tuple[str, int, str]] = set()
    for vessel_id, year in keys:
        for field_name in DECISION_FIELDS:
            values = {getattr(genes_by_seed_by_key[seed][(vessel_id, year)], field_name) for seed in seeds}
            if len(values) > 1:
                unstable_keys.add((vessel_id, year, field_name))
    return frozenset(unstable_keys)


def majority_values_from_per_seed_genomes(genomes_by_seed: dict[int, Genome]) -> dict[tuple[str, int, str], Any]:
    """The looser drill-down criterion (review item 1a): for each
    (vessel_id, year, decision) key, the value at least a strict majority
    of seeds agree on -- present in the returned dict only where such a
    majority exists (e.g. 2 of 3 seeds, not a 3-way split). A superset of
    what `stability_from_per_seed_genomes` would call stable (unanimous
    agreement is also a majority), so `len(majority_values) >=
    total_keys - len(stability_from_per_seed_genomes(...))`.

    Deliberately a *separate* function from the unanimous one rather than a
    parameterized generalization of it: the unanimous path stays exactly as
    reviewed and tested (item 1's "do NOT loosen the filter" — it remains
    the headline), and this is purely additive.
    """
    seeds = list(genomes_by_seed)
    majority_threshold = len(seeds) // 2 + 1
    genes_by_seed_by_key = {
        seed: {(gene.vessel_id, gene.year): gene for gene in genome} for seed, genome in genomes_by_seed.items()
    }
    keys = list(genes_by_seed_by_key[seeds[0]])

    majority_values: dict[tuple[str, int, str], Any] = {}
    for vessel_id, year in keys:
        for field_name in DECISION_FIELDS:
            values = [getattr(genes_by_seed_by_key[seed][(vessel_id, year)], field_name) for seed in seeds]
            value, count = Counter(values).most_common(1)[0]
            if count >= majority_threshold:
                majority_values[(vessel_id, year, field_name)] = value
    return majority_values


def solve_scenario_with_stability(
    fleet: dict[str, Any],
    prices: dict[str, Any],
    scenario_id: str,
    *,
    seeds: tuple[int, ...] = DEFAULT_STABILITY_SEEDS,
    population_size: int = DEFAULT_STABILITY_POPULATION_SIZE,
    n_generations: int = DEFAULT_STABILITY_GENERATIONS,
) -> ScenarioStabilitySolve:
    """Re-solve `scenario_id` under every seed in `seeds` independently and
    report which vessel-year decisions they don't agree on (PLAN §8.3(c)'s
    stability-flag principle, applied to this classical GA's own
    seed-to-seed variance -- the analog available before the tensor/SMC
    optimizer's own bond-dimension sweep exists).

    Expensive at the defaults (`len(seeds)` full solves at population 200 /
    200 generations each -- multiple minutes on this fleet): intended for an
    offline run producing `exposure.json`, not for interactive or routine
    test use. Pass smaller `seeds`/`population_size`/`n_generations` for
    fast structural tests; see `solve_scenario` for the cheap single-seed
    primitive this wraps.
    """
    results_by_seed = {
        seed: solve_scenario(
            fleet, prices, scenario_id, seed=seed, population_size=population_size, n_generations=n_generations
        )
        for seed in seeds
    }
    best_seed = min(results_by_seed, key=lambda s: results_by_seed[s].best_total_usd)
    best_result = results_by_seed[best_seed]
    genomes_by_seed = {seed: r.best_genome for seed, r in results_by_seed.items()}
    unstable_keys = stability_from_per_seed_genomes(genomes_by_seed)
    majority_values = majority_values_from_per_seed_genomes(genomes_by_seed)

    return ScenarioStabilitySolve(
        scenario_id=scenario_id,
        best_genome=best_result.best_genome,
        best_total_usd=best_result.best_total_usd,
        per_seed_total_usd={seed: r.best_total_usd for seed, r in results_by_seed.items()},
        unstable_keys=unstable_keys,
        majority_values=majority_values,
    )


def solve_all_scenarios_with_stability(
    fleet: dict[str, Any],
    prices: dict[str, Any],
    *,
    seeds: tuple[int, ...] = DEFAULT_STABILITY_SEEDS,
    population_size: int = DEFAULT_STABILITY_POPULATION_SIZE,
    n_generations: int = DEFAULT_STABILITY_GENERATIONS,
) -> dict[str, ScenarioStabilitySolve]:
    return {
        scenario["id"]: solve_scenario_with_stability(
            fleet, prices, scenario["id"], seeds=seeds, population_size=population_size, n_generations=n_generations
        )
        for scenario in load_scenarios()["scenarios"]
    }


def detect_exposed_decisions(
    genomes_by_scenario: dict[str, Genome], fleet: dict[str, Any]
) -> list[dict[str, Any]]:
    """A decision is exposed when its value differs across at least two of
    the K=5 scenario-optimal genomes. Band C is excluded — same rationale as
    component 4's switching-point extraction: it falls under none of the
    four regimes, so it's provably invariant to which NZF-outcome scenario
    is realized, and any apparent flip there is GA search noise."""
    band_by_vessel_id = {v["vessel_id"]: v["band"] for v in fleet["vessels"]}
    scenario_ids = list(genomes_by_scenario)
    genes_by_key_by_scenario = {
        scenario_id: {(gene.vessel_id, gene.year): gene for gene in genome}
        for scenario_id, genome in genomes_by_scenario.items()
    }
    keys = list(genes_by_key_by_scenario[scenario_ids[0]])

    exposed: list[dict[str, Any]] = []
    for vessel_id, year in keys:
        if band_by_vessel_id.get(vessel_id) == "C":
            continue
        for field_name in DECISION_FIELDS:
            values_by_scenario = {
                scenario_id: getattr(genes_by_key_by_scenario[scenario_id][(vessel_id, year)], field_name)
                for scenario_id in scenario_ids
            }
            if len(set(values_by_scenario.values())) > 1:
                exposed.append(
                    {
                        "vessel_id": vessel_id,
                        "year": year,
                        "decision": field_name,
                        "values_by_scenario": values_by_scenario,
                    }
                )
    return exposed


def detect_exposed_from_value_maps(
    values_by_scenario_by_key: dict[str, dict[tuple[str, int, str], Any]], fleet: dict[str, Any]
) -> list[dict[str, Any]]:
    """Like `detect_exposed_decisions`, generalized to any per-scenario
    (vessel_id, year, decision) -> value mapping rather than full genomes —
    used for the majority-agreement drill-down band (review item 1a), where
    a scenario may have no value at all for a key (no majority reached
    among its seeds). A key is only comparable, and therefore only
    reportable, where *every* scenario has a value for it; Band C is
    excluded for the same reason as `detect_exposed_decisions`.
    """
    band_by_vessel_id = {v["vessel_id"]: v["band"] for v in fleet["vessels"]}
    scenario_ids = list(values_by_scenario_by_key)
    all_keys: set[tuple[str, int, str]] = set()
    for value_map in values_by_scenario_by_key.values():
        all_keys |= set(value_map)

    exposed: list[dict[str, Any]] = []
    for vessel_id, year, field_name in sorted(all_keys):
        if band_by_vessel_id.get(vessel_id) == "C":
            continue
        key = (vessel_id, year, field_name)
        if not all(key in values_by_scenario_by_key[sid] for sid in scenario_ids):
            continue  # no majority reached in at least one scenario -- not comparable
        values_by_scenario = {sid: values_by_scenario_by_key[sid][key] for sid in scenario_ids}
        if len(set(values_by_scenario.values())) > 1:
            exposed.append(
                {"vessel_id": vessel_id, "year": year, "decision": field_name, "values_by_scenario": values_by_scenario}
            )
    return exposed


def price_fuel_switch(
    decision: dict[str, Any], baseline_gene, vessel: dict[str, Any], fleet: dict[str, Any], prices: dict[str, Any], fuel_model: FuelModel
) -> tuple[float, str, str]:
    distinct_fuels = sorted(set(decision["values_by_scenario"].values()))
    menu = option_menu_for(vessel, fleet, decision["year"])
    speed_knots = menu.speed_bands_knots[baseline_gene.speed_band_index]
    costs = {
        fuel_id: fuel_model.fuel_consumption_tonnes(vessel, fleet, decision["year"], speed_knots, fuel_id, baseline_gene.route_id)
        * prices["fuels"][fuel_id]["price_usd_per_tonne"]
        for fuel_id in distinct_fuels
    }
    capital_at_risk = max(costs.values()) - min(costs.values())
    notes = (
        f"Annual fuel-contract value delta across {distinct_fuels} at the {BASELINE_SCENARIO_ID}-solved "
        f"plan's route/speed ({baseline_gene.route_id}, band {baseline_gene.speed_band_index})."
    )
    return capital_at_risk, "SECONDARY_SOURCE", notes


def price_speed_band(
    decision: dict[str, Any], baseline_gene, vessel: dict[str, Any], fleet: dict[str, Any], prices: dict[str, Any], fuel_model: FuelModel
) -> tuple[float, str, str]:
    distinct_bands = sorted(set(decision["values_by_scenario"].values()))
    menu = option_menu_for(vessel, fleet, decision["year"])
    band_defaults = fleet["vessel_class_defaults"][vessel["band"]]
    fuel_price = prices["fuels"][baseline_gene.fuel_id]["price_usd_per_tonne"]
    costs = {}
    for index in distinct_bands:
        speed_knots = menu.speed_bands_knots[index]
        tonnes = fuel_model.fuel_consumption_tonnes(vessel, fleet, decision["year"], speed_knots, baseline_gene.fuel_id, baseline_gene.route_id)
        time_cost = band_defaults["charter_premium_usd_per_sea_day"] * sea_days(fleet, baseline_gene.route_id, speed_knots)
        costs[index] = tonnes * fuel_price + time_cost
    capital_at_risk = max(costs.values()) - min(costs.values())
    notes = (
        f"Annual fuel+time cost delta across speed bands {distinct_bands} at the {BASELINE_SCENARIO_ID}-solved "
        f"plan's fuel/route ({baseline_gene.fuel_id}, {baseline_gene.route_id})."
    )
    return capital_at_risk, "ILLUSTRATIVE", notes


def compute_dwt_by_route_year(genome: Genome, fleet: dict[str, Any]) -> dict[tuple[str, int], float]:
    vessels_by_id = {v["vessel_id"]: v for v in fleet["vessels"]}
    totals: dict[tuple[str, int], float] = defaultdict(float)
    for gene in genome:
        band = vessels_by_id[gene.vessel_id]["band"]
        totals[(gene.route_id, gene.year)] += fleet["vessel_class_defaults"][band]["dwt_tonnes"]
    return totals


def price_route_change(
    decision: dict[str, Any],
    baseline_gene,
    vessel: dict[str, Any],
    fleet: dict[str, Any],
    dwt_by_route_year: dict[tuple[str, int], float],
) -> tuple[float, str, str]:
    """Capacity coverage delta: `constraints.demand_shortfall_penalty`
    recomputed for the one or two routes actually affected by moving *this*
    vessel's DWT off its baseline route and onto each candidate route, on
    top of the rest of the baseline plan's real assignments.

    Deliberately *not* `vessel_dwt * DEMAND_PENALTY_USD_PER_DWT_SHORTFALL`
    applied flat: that per-DWT rate is calibrated in constraints.py to be
    prohibitively large ("large enough that the GA never prefers... any
    realistic combination of the other cost terms") precisely so the GA
    never chooses it — using it as a literal price would swamp every other
    decision type by two orders of magnitude and misrepresent what's really
    at stake. What's actually at stake is whether the *other* vessels
    already covering each route leave any slack above its demand floor —
    often none, sometimes plenty — which is what this recomputes.
    """
    distinct_routes = sorted(set(decision["values_by_scenario"].values()))
    year = decision["year"]
    vessel_dwt = fleet["vessel_class_defaults"][vessel["band"]]["dwt_tonnes"]
    baseline_route = baseline_gene.route_id

    def total_shortfall_penalty_usd(candidate_route: str) -> float:
        affected_routes = {baseline_route, candidate_route}
        total = 0.0
        for route_id in affected_routes:
            assigned = dwt_by_route_year.get((route_id, year), 0.0)
            if route_id == baseline_route and route_id != candidate_route:
                assigned -= vessel_dwt
            if route_id == candidate_route and route_id != baseline_route:
                assigned += vessel_dwt
            total += demand_shortfall_penalty(fleet, route_id, assigned).amount_usd
        return total

    costs = {route_id: total_shortfall_penalty_usd(route_id) for route_id in distinct_routes}
    capital_at_risk = max(costs.values()) - min(costs.values())
    notes = (
        f"Capacity-coverage delta: demand_shortfall_penalty recomputed for the routes this vessel could "
        f"occupy ({sorted({baseline_route, *distinct_routes})}), moving only this vessel's {vessel_dwt:.0f} "
        f"DWT between {distinct_routes} on top of the {BASELINE_SCENARIO_ID}-solved plan's other "
        f"assignments. Zero when the other vessels already covering both routes leave enough slack above "
        "each route's demand floor either way."
    )
    return capital_at_risk, "ILLUSTRATIVE", notes


def price_shore_power(fleet: dict[str, Any]) -> tuple[float, str, str]:
    capital_at_risk = fleet["shore_power_model"]["cost_usd_per_vessel_year_when_elected"]
    notes = "Fixed shore-power election cost from fleet.json's shore_power_model (already a priced figure -- not re-derived)."
    return capital_at_risk, "ILLUSTRATIVE", notes


def price_fueleu_election(
    decision: dict[str, Any],
    baseline_genome: Genome,
    fleet: dict[str, Any],
    prices: dict[str, Any],
    base_regulations: dict[str, Any],
) -> tuple[float, str, str]:
    """pool_opt_in / borrow_election: the only two decisions whose cost isn't
    a local, closed-form function of one vessel-year -- pooling depends on
    which *other* vessels opted in that year, and borrowing depends on the
    FuelEU ledger's banked-surplus state carried from prior years. Priced by
    full-fleet counterfactual re-evaluation instead of a formula: swap this
    one gene's field, hold everything else at the baseline plan, and read off
    the FuelEU compliance-cost delta -- the model's own number, not an
    approximation of it."""
    field_name = decision["decision"]
    key = (decision["vessel_id"], decision["year"])
    distinct_values = sorted(set(decision["values_by_scenario"].values()), key=str)

    costs = {}
    for value in distinct_values:
        counterfactual_genome = [
            replace(gene, **{field_name: value}) if (gene.vessel_id, gene.year) == key else gene
            for gene in baseline_genome
        ]
        result = evaluate(counterfactual_genome, fleet, base_regulations, prices)
        costs[value] = result.compliance_costs["fuel_eu"].amount_usd

    capital_at_risk = max(costs.values()) - min(costs.values())
    notes = (
        f"FuelEU compliance-cost delta between {field_name}={distinct_values}, full-fleet counterfactual "
        f"re-evaluation holding everything else at the {BASELINE_SCENARIO_ID}-solved plan "
        f"(regulations: {BASELINE_SCENARIO_ID}, since FuelEU is identical across every K=5 scenario)."
    )
    return capital_at_risk, "SECONDARY_SOURCE", notes


def price_exposed_decision(
    decision: dict[str, Any],
    baseline_genome: Genome,
    baseline_by_key: dict[tuple[str, int], Any],
    vessels_by_id: dict[str, Any],
    fleet: dict[str, Any],
    prices: dict[str, Any],
    base_regulations: dict[str, Any],
    fuel_model: FuelModel,
    dwt_by_route_year: dict[tuple[str, int], float],
) -> ExposedDecision:
    key = (decision["vessel_id"], decision["year"])
    baseline_gene = baseline_by_key[key]
    vessel = vessels_by_id[decision["vessel_id"]]
    field_name = decision["decision"]

    if field_name == "fuel_id":
        capital_at_risk, status, notes = price_fuel_switch(decision, baseline_gene, vessel, fleet, prices, fuel_model)
    elif field_name == "speed_band_index":
        capital_at_risk, status, notes = price_speed_band(decision, baseline_gene, vessel, fleet, prices, fuel_model)
    elif field_name == "route_id":
        capital_at_risk, status, notes = price_route_change(decision, baseline_gene, vessel, fleet, dwt_by_route_year)
    elif field_name == "shore_power":
        capital_at_risk, status, notes = price_shore_power(fleet)
    elif field_name in ("pool_opt_in", "borrow_election"):
        capital_at_risk, status, notes = price_fueleu_election(decision, baseline_genome, fleet, prices, base_regulations)
    else:  # pragma: no cover — DECISION_FIELDS is a closed, tested set
        raise ValueError(f"unknown decision field {field_name!r}")

    return ExposedDecision(
        vessel_id=decision["vessel_id"],
        year=decision["year"],
        decision=field_name,
        values_by_scenario=decision["values_by_scenario"],
        capital_at_risk_usd=capital_at_risk,
        capital_at_risk_status=status,
        capital_at_risk_notes=notes,
    )


def run_consistency_checks(
    priced_decisions: list[ExposedDecision],
    ticks_by_scenario: dict[str, ScenarioAxisPosition],
    switching_points_by_key: dict[tuple[str, int, str], list],
) -> list[ConsistencyCheck]:
    checks: list[ConsistencyCheck] = []
    for decision in priced_decisions:
        key = (decision.vessel_id, decision.year, decision.decision)
        for (scenario_a, value_a), (scenario_b, value_b) in combinations(decision.values_by_scenario.items(), 2):
            if value_a == value_b:
                continue

            tick_a = ticks_by_scenario.get(scenario_a)
            tick_b = ticks_by_scenario.get(scenario_b)
            if (
                tick_a is None
                or tick_b is None
                or tick_a.operating_point_usd_per_tco2e is None
                or tick_b.operating_point_usd_per_tco2e is None
            ):
                checks.append(
                    ConsistencyCheck(
                        vessel_id=decision.vessel_id,
                        year=decision.year,
                        decision=decision.decision,
                        scenario_low=scenario_a,
                        scenario_high=scenario_b,
                        axis_low_usd_per_tco2e=None,
                        axis_high_usd_per_tco2e=None,
                        consistent=None,
                        notes=f"Not checkable: no computed axis position for one or both of {scenario_a!r}/{scenario_b!r}.",
                    )
                )
                continue

            point_a, point_b = tick_a.operating_point_usd_per_tco2e, tick_b.operating_point_usd_per_tco2e
            scenario_low, scenario_high = (scenario_a, scenario_b) if point_a <= point_b else (scenario_b, scenario_a)
            price_low, price_high = min(point_a, point_b), max(point_a, point_b)

            candidates = switching_points_by_key.get(key, [])
            overlapping = [
                sp
                for sp in candidates
                if sp.price_high_usd_per_tco2e >= price_low and sp.price_low_usd_per_tco2e <= price_high
            ]
            if overlapping:
                consistent = True
                notes = (
                    f"Sweep switching point(s) {[(sp.price_low_usd_per_tco2e, sp.price_high_usd_per_tco2e) for sp in overlapping]} "
                    f"overlap [{price_low}, {price_high}] ({scenario_low} -> {scenario_high})."
                )
            elif candidates:
                consistent = False
                notes = (
                    f"Sweep found switching point(s) for this decision at "
                    f"{[(sp.price_low_usd_per_tco2e, sp.price_high_usd_per_tco2e) for sp in candidates]}, none overlapping "
                    f"[{price_low}, {price_high}] ({scenario_low} -> {scenario_high}) -- "
                    "either a GA-convergence gap in one of the two solves, or the axis positions are off."
                )
            else:
                consistent = False
                notes = (
                    f"Scenarios {scenario_low}/{scenario_high} disagree on this decision but the sweep found no "
                    "switching point for it anywhere on the grid -- likely a GA-convergence gap in the sweep "
                    "(or in one of the two scenario solves), not a real absence of a switching price."
                )

            checks.append(
                ConsistencyCheck(
                    vessel_id=decision.vessel_id,
                    year=decision.year,
                    decision=decision.decision,
                    scenario_low=scenario_low,
                    scenario_high=scenario_high,
                    axis_low_usd_per_tco2e=price_low,
                    axis_high_usd_per_tco2e=price_high,
                    consistent=consistent,
                    notes=notes,
                )
            )
    return checks


#: The one decision type that's a genuine capital commitment in this
#: prototype's genome. No `retrofit_year` variable exists yet (PLAN.md
#: §5.4/Track F), so this is the whole capex-shaped decision set for now.
CAPEX_DECISION_TYPES = frozenset({"shore_power"})


def compute_exposure(
    fleet: dict[str, Any],
    prices: dict[str, Any],
    sweep_result: SweepResult,
    *,
    seeds: tuple[int, ...] = DEFAULT_STABILITY_SEEDS,
    population_size: int = DEFAULT_STABILITY_POPULATION_SIZE,
    n_generations: int = DEFAULT_STABILITY_GENERATIONS,
    fuel_model: FuelModel | None = None,
) -> ExposureResult:
    """The Exposure Map by flip-counting (Task 2R component 5): solve every
    K=5 scenario under every stability seed, keep only the decisions every
    seed agreed on within its scenario, price each one that still differs
    across scenarios, and cross-check the flips against `sweep_result`
    (component 4's carbon-price sweep -- pass one from `sweep.run_sweep`;
    not run here automatically, since it's the more expensive of the two
    computations and the caller may already have one).

    Returns three non-overlapping figures rather than one summed total --
    see the module docstring for why summing `per_decision_deltas` would be
    wrong. `seeds`/`population_size`/`n_generations` default to the
    (expensive) stability-filter settings; pass smaller values for fast
    structural tests.
    """
    fuel_model = fuel_model or PhysicsFuelModel()
    vessels_by_id = {v["vessel_id"]: v for v in fleet["vessels"]}
    band_by_vessel_id = {v["vessel_id"]: v["band"] for v in fleet["vessels"]}
    scenario_ids = [s["id"] for s in load_scenarios()["scenarios"]]
    fx = prices["fx_rates"]["usd_to_inr"]

    solves_by_scenario = solve_all_scenarios_with_stability(
        fleet, prices, seeds=seeds, population_size=population_size, n_generations=n_generations
    )
    genomes_by_scenario = {sid: solve.best_genome for sid, solve in solves_by_scenario.items()}
    global_unstable_keys: set[tuple[str, int, str]] = set()
    for solve in solves_by_scenario.values():
        global_unstable_keys |= solve.unstable_keys

    baseline_solve = solves_by_scenario[BASELINE_SCENARIO_ID]
    baseline_genome = baseline_solve.best_genome
    baseline_by_key = {(gene.vessel_id, gene.year): gene for gene in baseline_genome}
    base_regulations = resolve_regulations_for_scenario(BASELINE_SCENARIO_ID)
    dwt_by_route_year = compute_dwt_by_route_year(baseline_genome, fleet)

    # `detect_exposed_decisions` already excludes Band C; for any key not in
    # global_unstable_keys, every scenario's own 3-seed solve agreed, so its
    # best-seed genome value *is* that scenario's stable value -- no need to
    # re-derive it from a separate "stable-values" structure.
    candidate_exposed = detect_exposed_decisions(genomes_by_scenario, fleet)
    stable_exposed = [
        d for d in candidate_exposed if (d["vessel_id"], d["year"], d["decision"]) not in global_unstable_keys
    ]
    unstable_decisions = [
        UnstableDecision(vessel_id=vessel_id, year=year, decision=decision)
        for vessel_id, year, decision in sorted(global_unstable_keys)
        if band_by_vessel_id.get(vessel_id) != "C"
    ]

    priced_decisions = [
        price_exposed_decision(
            decision,
            baseline_genome,
            baseline_by_key,
            vessels_by_id,
            fleet,
            prices,
            base_regulations,
            fuel_model,
            dwt_by_route_year,
        )
        for decision in stable_exposed
    ]

    # --- Majority band (review item 1a): "do NOT loosen the filter" -- the
    # unanimous computation above is untouched and stays the headline. This
    # is a purely additive, looser drill-down tier: a key needs only a
    # strict majority of seeds to agree, in every scenario, to be
    # comparable. Deduplicated against the headline set so nothing is
    # double-reported across the two tiers.
    all_possible_keys = {
        (gene.vessel_id, gene.year, field_name) for gene in baseline_genome for field_name in DECISION_FIELDS
    }
    majority_values_by_scenario = {sid: solve.majority_values for sid, solve in solves_by_scenario.items()}
    majority_candidate_exposed = detect_exposed_from_value_maps(majority_values_by_scenario, fleet)
    headline_keys = {(d["vessel_id"], d["year"], d["decision"]) for d in stable_exposed}
    majority_band = [
        d for d in majority_candidate_exposed if (d["vessel_id"], d["year"], d["decision"]) not in headline_keys
    ]
    priced_majority_band = [
        price_exposed_decision(
            decision,
            baseline_genome,
            baseline_by_key,
            vessels_by_id,
            fleet,
            prices,
            base_regulations,
            fuel_model,
            dwt_by_route_year,
        )
        for decision in majority_band
    ]
    global_majority_unstable_keys = {
        key for key in all_possible_keys if any(key not in solve.majority_values for solve in solves_by_scenario.values())
    }
    majority_unstable_decisions = [
        UnstableDecision(vessel_id=vessel_id, year=year, decision=decision)
        for vessel_id, year, decision in sorted(global_majority_unstable_keys)
        if band_by_vessel_id.get(vessel_id) != "C"
    ]

    # --- (1) Plan spread: PLAN §3.1's actual headline number. ---
    scenario_totals_usd = {sid: solve.best_total_usd for sid, solve in solves_by_scenario.items()}
    max_scenario_id = max(scenario_totals_usd, key=scenario_totals_usd.get)
    min_scenario_id = min(scenario_totals_usd, key=scenario_totals_usd.get)
    spread_usd = scenario_totals_usd[max_scenario_id] - scenario_totals_usd[min_scenario_id]
    plan_spread = PlanSpread(
        scenario_totals_usd=scenario_totals_usd,
        max_scenario_id=max_scenario_id,
        min_scenario_id=min_scenario_id,
        spread_usd=spread_usd,
        spread_inr=spread_usd * fx["rate"],
    )

    # --- (2) Capex exposure: the PLAN §9.3 CFO-sentence figure. ---
    capex_decisions = [d for d in priced_decisions if d.decision in CAPEX_DECISION_TYPES]
    capex_total_usd = sum(d.capital_at_risk_usd for d in capex_decisions)
    capex_exposure = CapexExposure(
        decisions=capex_decisions, total_usd=capex_total_usd, total_inr=capex_total_usd * fx["rate"]
    )

    # --- (3) Consistency checks, on the stable (seed-converged) decisions. ---
    ticks_by_scenario = {tick.scenario_id: tick for tick in sweep_result.scenario_ticks}
    switching_points_by_key: dict[tuple[str, int, str], list] = defaultdict(list)
    for switching_point in sweep_result.switching_points:
        switching_points_by_key[(switching_point.vessel_id, switching_point.year, switching_point.decision)].append(
            switching_point
        )
    consistency_checks = run_consistency_checks(priced_decisions, ticks_by_scenario, switching_points_by_key)
    majority_band_consistency_checks = run_consistency_checks(
        priced_majority_band, ticks_by_scenario, switching_points_by_key
    )

    return ExposureResult(
        scenario_ids=scenario_ids,
        stability_seeds=tuple(seeds),
        ga_population_size=population_size,
        ga_generations=n_generations,
        plan_spread=plan_spread,
        capex_exposure=capex_exposure,
        per_decision_deltas=priced_decisions,
        unstable_decisions=unstable_decisions,
        majority_band_decisions=priced_majority_band,
        majority_unstable_decisions=majority_unstable_decisions,
        fx_rate_usd_to_inr=fx["rate"],
        fx_status=fx["status"],
        fx_retrieval_date=fx["retrieval_date"],
        fx_notes=fx.get("notes", ""),
        consistency_checks=consistency_checks,
        majority_band_consistency_checks=majority_band_consistency_checks,
    )


def _exposed_decision_to_dict(d: ExposedDecision) -> dict[str, Any]:
    return {
        "vessel_id": d.vessel_id,
        "year": d.year,
        "decision": d.decision,
        "flips_between_which_scenarios": d.values_by_scenario,
        "capital_at_risk": {
            "amount_usd": d.capital_at_risk_usd,
            "status": d.capital_at_risk_status,
            "notes": d.capital_at_risk_notes,
        },
    }


def exposure_result_to_dict(result: ExposureResult) -> dict[str, Any]:
    """A fully JSON-serializable view of `result` for `exposure.json` —
    plan_spread / capex_exposure / per_decision_deltas kept as three
    separate, clearly-labeled figures (never re-merged into one summed
    total), plus unstable_decisions and the sweep cross-check, every figure
    carrying the status/notes discipline established by components 3 and 4.
    """
    return {
        "document_version": "task2r-component5-v2",
        "provenance_note": (
            "Exposure Map by flip-counting (Task 2R component 5, prototype version, PLAN.md §3.1 via "
            "§8.3b's classical method). A decision is exposed if its stable (seed-converged) value "
            "differs across the K=5 scenario-optimal solves; Band C vessel-years are excluded (provably "
            "invariant -- see sweep.py's own note). plan_spread, capex_exposure, and per_decision_deltas "
            "are three DISTINCT figures, not one broken into parts -- see the 'methodology' and each "
            "section's own 'description' for why they must not be summed together or with each other."
        ),
        "scenario_ids": result.scenario_ids,
        "methodology": {
            "stability_seeds": list(result.stability_seeds),
            "ga_population_size": result.ga_population_size,
            "ga_generations": result.ga_generations,
            "note": (
                "PLAN §8.3(c)'s stability-flag principle, applied to this classical GA's own seed-to-seed "
                "variance (the analog available before the tensor/SMC optimizer's bond-dimension sweep "
                "exists): each scenario is solved under every seed in stability_seeds independently; a "
                "decision is reported (as exposed or not) only when every seed agrees on its value within "
                "that scenario. See unstable_decisions for what didn't converge."
            ),
        },
        "summary": {
            "stable_exposed_decision_count": len(result.per_decision_deltas),
            "unstable_decision_count": len(result.unstable_decisions),
            "majority_band_decision_count": len(result.majority_band_decisions),
            "majority_unstable_decision_count": len(result.majority_unstable_decisions),
            "plan_spread_usd": result.plan_spread.spread_usd,
            "plan_spread_inr": result.plan_spread.spread_inr,
            "capex_exposure_usd": result.capex_exposure.total_usd,
            "capex_exposure_inr": result.capex_exposure.total_inr,
        },
        "plan_spread": {
            "description": (
                "PLAN §3.1's headline 'cost of regulatory uncertainty' figure: max minus min of the five "
                "scenario-optimal total plan costs. A single, non-overlapping number, not a sum."
            ),
            "scenario_totals_usd": result.plan_spread.scenario_totals_usd,
            "max_scenario_id": result.plan_spread.max_scenario_id,
            "min_scenario_id": result.plan_spread.min_scenario_id,
            "spread_usd": result.plan_spread.spread_usd,
            "spread_inr": result.plan_spread.spread_inr,
        },
        "capex_exposure": {
            "description": (
                "PLAN §3.1/§9.3's 'X crore of capex is contingent on the vote' figure: capital-commitment "
                "decisions only. This prototype's genome models exactly one such decision (shore-power "
                "election) -- there is no retrofit_year variable yet (PLAN.md §5.4/Track F), so "
                "retrofit-type capex is not represented here."
            ),
            "total_usd": result.capex_exposure.total_usd,
            "total_inr": result.capex_exposure.total_inr,
            "decisions": [_exposed_decision_to_dict(d) for d in result.capex_exposure.decisions],
        },
        "per_decision_deltas": {
            "description": (
                "Every stable exposed decision (all types), for drill-down only. These are independent "
                "marginal deltas, each computed against the same baseline plan with only that one "
                "decision swapped -- they are NOT mutually exclusive costs and MUST NOT be summed into a "
                "single 'total exposure' figure: doing so double-counts overlapping risk and mixes "
                "one-time capex with recurring opex-shaped deltas. Use plan_spread for the headline number "
                "and capex_exposure for the capex-specific figure."
            ),
            "decisions": [_exposed_decision_to_dict(d) for d in result.per_decision_deltas],
        },
        "unstable_decisions": {
            "count": len(result.unstable_decisions),
            "description": (
                "Decisions where the stability_seeds disagreed on the optimal value within at least one "
                "scenario -- excluded from every headline count above (PLAN §8.3(c)): a decision the "
                "search itself can't reproduce isn't a finding about the vote, it's GA noise."
            ),
            "decisions": [asdict(d) for d in result.unstable_decisions],
        },
        "majority_band": {
            "description": (
                "Review item 1a: the unanimous criterion above stays the headline (NOT loosened). This is "
                "a separate, additive, looser drill-down tier -- a key needs only a strict majority of "
                "stability_seeds to agree (e.g. 2 of 3), independently in every scenario, to be reported "
                "here. Deduplicated against per_decision_deltas: nothing appears in both. Read alongside "
                "majority_band_consistency_checks and treat with correspondingly less confidence than the "
                "headline tier -- a majority is a real signal, not the same bar as unanimous agreement."
            ),
            "decisions": [_exposed_decision_to_dict(d) for d in result.majority_band_decisions],
            "unstable_decisions": {
                "count": len(result.majority_unstable_decisions),
                "description": "Decisions where not even a majority of stability_seeds agreed, in at least one scenario.",
                "decisions": [asdict(d) for d in result.majority_unstable_decisions],
            },
        },
        "fx": {
            "usd_to_inr_rate": result.fx_rate_usd_to_inr,
            "status": result.fx_status,
            "retrieval_date": result.fx_retrieval_date,
            "notes": result.fx_notes,
        },
        "consistency_checks": [asdict(c) for c in result.consistency_checks],
        "majority_band_consistency_checks": [asdict(c) for c in result.majority_band_consistency_checks],
    }


def write_exposure_results(path: str, result: ExposureResult) -> None:
    """Write `exposure_result_to_dict(result)` to `path` as `exposure.json`."""
    import json

    with open(path, "w") as f:
        json.dump(exposure_result_to_dict(result), f, indent=2)


if __name__ == "__main__":
    from knotwise.fleet.loader import load_fleet, load_prices
    from knotwise.optimization.sweep import run_sweep

    _fleet = load_fleet()
    _prices = load_prices()
    _sweep = run_sweep(_fleet, _prices)
    _result = compute_exposure(_fleet, _prices, _sweep)
    write_exposure_results("exposure.json", _result)
    print(
        f"wrote exposure.json: {len(_result.per_decision_deltas)} stable exposed decisions "
        f"({len(_result.unstable_decisions)} unstable), "
        f"{len(_result.majority_band_decisions)} majority-band decisions "
        f"({len(_result.majority_unstable_decisions)} majority-unstable), "
        f"plan_spread=₹{_result.plan_spread.spread_inr:,.0f}, "
        f"capex_exposure=₹{_result.capex_exposure.total_inr:,.0f}"
    )
