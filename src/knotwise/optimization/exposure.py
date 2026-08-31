"""Exposure by flip-counting, priced in rupees (Task 2R component 5,
prototype version — implements PLAN.md §3.1's Exposure Map via §8.3(b)'s
classical validation method: "retraining per scenario and counting how often
each decision flips").

A decision is **exposed** if its optimal value differs across the K=5
scenario-optimal fleet plans (`solve_scenario`, component 4). Each exposed
decision is priced in capital-at-risk USD from the model's own numbers —
never an invented lump sum — summed and converted to INR. Component 4's
carbon-price sweep gives a free cross-check for free: since every scenario
in scenarios.json differs from the others only in its NZF treatment, a
decision that flips between two scenarios ought to have a matching switching
point somewhere between those scenarios' axis positions in the sweep. Where
it doesn't, that's a finding (a GA-convergence gap, or an axis position built
from a mechanism the uniform-price sweep doesn't capture) reported rather
than hidden.
"""

from __future__ import annotations

from collections import defaultdict
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
class ExposureResult:
    scenario_ids: list[str]
    exposed_decisions: list[ExposedDecision]
    total_capital_at_risk_usd: float
    total_capital_at_risk_inr: float
    fx_rate_usd_to_inr: float
    fx_status: str
    fx_retrieval_date: str
    fx_notes: str
    consistency_checks: list[ConsistencyCheck]


def solve_all_scenarios(
    fleet: dict[str, Any],
    prices: dict[str, Any],
    *,
    seed: int,
    population_size: int,
    n_generations: int,
) -> dict[str, Genome]:
    return {
        scenario["id"]: solve_scenario(
            fleet,
            prices,
            scenario["id"],
            seed=seed,
            population_size=population_size,
            n_generations=n_generations,
        ).best_genome
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


def compute_exposure(
    fleet: dict[str, Any],
    prices: dict[str, Any],
    sweep_result: SweepResult,
    *,
    seed: int = 0,
    population_size: int = 40,
    n_generations: int = 30,
    fuel_model: FuelModel | None = None,
) -> ExposureResult:
    """The Exposure Map by flip-counting (Task 2R component 5): solve every
    K=5 scenario, diff the results, price each exposed decision from the
    model's own numbers, and cross-check the flips against `sweep_result`
    (component 4's carbon-price sweep -- pass one from `sweep.run_sweep`;
    not run here automatically, since it's the more expensive of the two
    computations and the caller may already have one).
    """
    fuel_model = fuel_model or PhysicsFuelModel()
    vessels_by_id = {v["vessel_id"]: v for v in fleet["vessels"]}
    scenario_ids = [s["id"] for s in load_scenarios()["scenarios"]]

    genomes_by_scenario = solve_all_scenarios(
        fleet, prices, seed=seed, population_size=population_size, n_generations=n_generations
    )
    baseline_genome = genomes_by_scenario[BASELINE_SCENARIO_ID]
    baseline_by_key = {(gene.vessel_id, gene.year): gene for gene in baseline_genome}
    base_regulations = resolve_regulations_for_scenario(BASELINE_SCENARIO_ID)
    dwt_by_route_year = compute_dwt_by_route_year(baseline_genome, fleet)

    exposed = detect_exposed_decisions(genomes_by_scenario, fleet)
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
        for decision in exposed
    ]

    total_usd = sum(d.capital_at_risk_usd for d in priced_decisions)
    fx = prices["fx_rates"]["usd_to_inr"]
    total_inr = total_usd * fx["rate"]

    ticks_by_scenario = {tick.scenario_id: tick for tick in sweep_result.scenario_ticks}
    switching_points_by_key: dict[tuple[str, int, str], list] = defaultdict(list)
    for switching_point in sweep_result.switching_points:
        switching_points_by_key[(switching_point.vessel_id, switching_point.year, switching_point.decision)].append(
            switching_point
        )
    consistency_checks = run_consistency_checks(priced_decisions, ticks_by_scenario, switching_points_by_key)

    return ExposureResult(
        scenario_ids=scenario_ids,
        exposed_decisions=priced_decisions,
        total_capital_at_risk_usd=total_usd,
        total_capital_at_risk_inr=total_inr,
        fx_rate_usd_to_inr=fx["rate"],
        fx_status=fx["status"],
        fx_retrieval_date=fx["retrieval_date"],
        fx_notes=fx.get("notes", ""),
        consistency_checks=consistency_checks,
    )


def exposure_result_to_dict(result: ExposureResult) -> dict[str, Any]:
    """A fully JSON-serializable view of `result` for `exposure.json` —
    exposed_decisions -> capital_at_risk/flips_between_which_scenarios ->
    totals -> consistency checks, every figure carrying the status/notes
    discipline established by components 3 and 4."""
    return {
        "document_version": "task2r-component5-v1",
        "provenance_note": (
            "Exposure Map by flip-counting (Task 2R component 5, prototype version, PLAN.md §3.1 via "
            "§8.3b's classical method). A decision is exposed if its GA-optimal value differs across the "
            "K=5 scenario-optimal solves. Band C vessel-years are excluded (provably invariant -- see "
            "sweep.py's own note). capital_at_risk figures are computed from this model's fuel/compliance/"
            "demand-penalty numbers, never invented lump sums; each carries its own confidence status. "
            "consistency_checks cross-validate every flip against component 4's carbon-price sweep -- "
            "'consistent: null' means not checkable (no computed axis position for one of the two "
            "scenarios), not a pass or a fail."
        ),
        "scenario_ids": result.scenario_ids,
        "summary": {
            "exposed_decision_count": len(result.exposed_decisions),
            "total_capital_at_risk_usd": result.total_capital_at_risk_usd,
            "total_capital_at_risk_inr": result.total_capital_at_risk_inr,
        },
        "fx": {
            "usd_to_inr_rate": result.fx_rate_usd_to_inr,
            "status": result.fx_status,
            "retrieval_date": result.fx_retrieval_date,
            "notes": result.fx_notes,
        },
        "exposed_decisions": [
            {
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
            for d in result.exposed_decisions
        ],
        "consistency_checks": [asdict(c) for c in result.consistency_checks],
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
        f"wrote exposure.json: {len(_result.exposed_decisions)} exposed decisions, "
        f"₹{_result.total_capital_at_risk_inr:,.0f} total capital at risk"
    )
