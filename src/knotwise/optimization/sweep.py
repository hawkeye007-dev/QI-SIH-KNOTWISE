"""Carbon-price sweep + switching-point extraction (Task 2R component 4,
prototype version — implements PLAN.md §3.6).

The sweep clamps the **effective marginal carbon price** (the §3.6 axis, in
USD/tCO2e), not scenario identity: at each grid point we build a synthetic
resolved-regulations view where NZF's two-tier deficit structure collapses to
one uniform price, solve the fleet plan under it (warm-started from the
neighboring grid point's best genome — component 3's `solver.run_ga` already
supports this via `seed_genome`), and record where each vessel-year's optimal
decision changes as price rises. That set of changes is the switching-point
table; PLAN.md §3.6's scenario ticks (`scenario_axis_positions`) mark where
each of the K=5 live proposals — plus EU ETS's own real, always-on price —
actually sits on that same axis, so the gap between a tick and a switching
point is the demo's "bet distance."

Everything here consumes component 3's already-tested primitives
(`solver.run_ga`, `objective.vessel_year_facts`, `compliance_cost.nzf_gaps`,
`implied_price.fueleu_implied_price`) rather than re-deriving fuel/regime
logic — this module's own job is the grid loop, the switching-point diff, and
the scenario-axis bookkeeping around them.
"""

from __future__ import annotations

import copy
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from itertools import pairwise
from typing import Any

from knotwise.optimization import solver
from knotwise.optimization.compliance_cost import nzf_gaps
from knotwise.optimization.fuel_model import FuelModel, PhysicsFuelModel
from knotwise.optimization.genome import Genome
from knotwise.optimization.objective import vessel_year_facts
from knotwise.regulatory.implied_price import fueleu_implied_price
from knotwise.regulatory.loader import load_scenarios
from knotwise.regulatory.scenario_resolution import resolve_regulations_for_scenario

#: $0-600 in $25 steps — a demo-settings default, not a fixed contract;
#: callers may pass any grid via `run_sweep`'s `price_grid`.
DEFAULT_PRICE_GRID: tuple[float, ...] = tuple(range(0, 601, 25))

#: The six per-vessel-year decision fields switching points are extracted
#: over (`VesselYearGene`'s decision fields, minus `vessel_id`/`year`, which
#: identify the slot rather than decide anything).
DECISION_FIELDS: tuple[str, ...] = (
    "route_id",
    "speed_band_index",
    "fuel_id",
    "shore_power",
    "pool_opt_in",
    "borrow_election",
)


def _nzf_price_override(base_regulations: dict[str, Any], price: float) -> dict[str, Any]:
    """A synthetic resolved-regulations view: NZF's two-tier deficit price
    collapsed to one uniform `price` at both tiers.

    Surplus value scales 1:1 with `price` too, per
    `surplus_unit_value_usd_per_tco2e`'s own stated floor logic in
    regulations.json ("valued... at the Tier-1 remedial-unit price as a
    floor") — under a single uniform price, that floor *is* the price.
    Every other regime (CII, EU ETS, FuelEU) is left at `base_regulations`'s
    real, approved-text values: this sweep's axis is the NZF-style effective
    carbon price specifically (Task 2R component 4, item 2), not a rescaling
    of EU ETS's own genuinely posted price.
    """
    resolved = copy.deepcopy(base_regulations)
    nzf = resolved["regimes"]["nzf"]
    applicable_years = (nzf["tier_prices_usd_per_tco2e"] or {}).get("applicable_years", [2028, 2029, 2030])
    nzf["tier_prices_usd_per_tco2e"] = {
        "tier_1": price,
        "tier_2": price,
        "applicable_years": applicable_years,
    }
    nzf["surplus_unit_value_usd_per_tco2e"] = price
    return resolved


@dataclass(frozen=True)
class GridPointResult:
    price_usd_per_tco2e: float
    genome: Genome
    total_usd: float
    solve_seconds: float
    warm_started: bool
    generations_run: int


@dataclass(frozen=True)
class SwitchingPoint:
    """A decision that changed between two adjacent grid points.

    Resolution is the grid step: the true switching price lies somewhere in
    `(price_low_usd_per_tco2e, price_high_usd_per_tco2e]`, not at a specific
    point within it (Task 2R component 4, item 3).
    """

    vessel_id: str
    year: int
    decision: str
    from_value: Any
    to_value: Any
    price_low_usd_per_tco2e: float
    price_high_usd_per_tco2e: float


@dataclass(frozen=True)
class WarmStartBenchmark:
    """The measured warm-start-vs-cold-solve timing at one grid point —
    "retires the classical half of the 'seconds, not free' claim" (item 2):
    an actual number, not an assumption."""

    price_usd_per_tco2e: float
    cold_seconds: float
    warm_seconds: float
    cold_generations: int
    warm_generations: int


@dataclass(frozen=True)
class ScenarioAxisPosition:
    """Where one scenario sits on the effective-marginal-carbon-price axis
    (PLAN.md §3.6b). `kind` is scenarios.json's own `price_axis_treatment`
    field, so this module never re-decides how a scenario should be
    classified. Never a bare number — `notes` always states the assumption
    behind it, per §3.6(b)'s own rule."""

    scenario_id: str
    label: str
    kind: str
    low_usd_per_tco2e: float | None
    high_usd_per_tco2e: float | None
    operating_point_usd_per_tco2e: float | None
    status: str
    notes: str


def extract_switching_points(
    grid_points: list[GridPointResult], fleet: dict[str, Any] | None = None
) -> list[SwitchingPoint]:
    """Diff each pair of adjacent grid points' genomes, decision field by
    decision field, for every vessel-year.

    When `fleet` is given, vessel-years belonging to a vessel in Band C are
    excluded: Band C falls under none of the four regimes
    (`docs/scope_matrix.md`), so its objective terms are provably invariant
    to the NZF price this sweep varies — any "switching" observed there is
    GA search noise (an equally-good alternative the search happened to
    land on), not a real economic response, and would just dilute the
    signal from the vessel-years where the sweep's content actually lives.
    `fleet=None` (the default) skips this filter, e.g. for unit tests that
    construct grid points directly without a full fleet fixture.
    """
    band_by_vessel_id: dict[str, str] | None = None
    if fleet is not None:
        band_by_vessel_id = {v["vessel_id"]: v["band"] for v in fleet["vessels"]}

    switching_points: list[SwitchingPoint] = []
    for previous, current in pairwise(grid_points):
        current_by_key = {(gene.vessel_id, gene.year): gene for gene in current.genome}
        for previous_gene in previous.genome:
            if band_by_vessel_id is not None and band_by_vessel_id.get(previous_gene.vessel_id) == "C":
                continue
            current_gene = current_by_key.get((previous_gene.vessel_id, previous_gene.year))
            if current_gene is None:
                continue
            for field_name in DECISION_FIELDS:
                old_value = getattr(previous_gene, field_name)
                new_value = getattr(current_gene, field_name)
                if old_value != new_value:
                    switching_points.append(
                        SwitchingPoint(
                            vessel_id=previous_gene.vessel_id,
                            year=previous_gene.year,
                            decision=field_name,
                            from_value=old_value,
                            to_value=new_value,
                            price_low_usd_per_tco2e=previous.price_usd_per_tco2e,
                            price_high_usd_per_tco2e=current.price_usd_per_tco2e,
                        )
                    )
    return switching_points


def _fleet_nzf_operating_point(
    representative_genome: Genome,
    fleet: dict[str, Any],
    scenario_regulations: dict[str, Any],
    fuel_model: FuelModel,
) -> float | None:
    """The fleet's own tonnage-weighted average $/tCO2e under
    `scenario_regulations`'s tier prices, applied to `representative_genome`'s
    NZF deficit distribution (PLAN.md §3.6b: "the fleet's expected operating
    point... computed from the case study's own deficit distribution").

    `None` when nothing in the representative plan is NZF-priced (no
    applicable deficit, or the scenario has no tier prices at all) — an
    honest "undefined", never a guessed number.
    """
    vessels_by_id = {v["vessel_id"]: v for v in fleet["vessels"]}
    nzf_regime = scenario_regulations["regimes"]["nzf"]
    tier_prices = nzf_regime["tier_prices_usd_per_tco2e"]
    if tier_prices is None:
        return None

    weighted_dollars = 0.0
    priced_tonnes = 0.0
    for gene in representative_genome:
        vessel = vessels_by_id[gene.vessel_id]
        facts = vessel_year_facts(gene, vessel, fleet, scenario_regulations, fuel_model)
        if not facts.applicability["nzf"].applies:
            continue
        gaps = nzf_gaps(nzf_regime, gene.year, facts.actual_ghg_intensity_gco2e_per_mj)
        if gaps is None:
            continue
        tonnes = facts.energy_mj / 1e6
        if tier_prices.get("tier_1") is not None:
            weighted_dollars += gaps.gap_tier1_gco2e_per_mj * tonnes * tier_prices["tier_1"]
            priced_tonnes += gaps.gap_tier1_gco2e_per_mj * tonnes
        if tier_prices.get("tier_2") is not None:
            weighted_dollars += gaps.gap_tier2_gco2e_per_mj * tonnes * tier_prices["tier_2"]
            priced_tonnes += gaps.gap_tier2_gco2e_per_mj * tonnes

    if priced_tonnes <= 0:
        return None
    return weighted_dollars / priced_tonnes


def _adoption_fails_axis_position(
    scenario: dict[str, Any],
    fleet: dict[str, Any],
    prices: dict[str, Any],
    representative_genome: Genome,
    fuel_model: FuelModel,
) -> ScenarioAxisPosition:
    """Scenario 5's position, via `implied_price.fueleu_implied_price` — never
    assumed zero (Task 2R component 4, item 1). Tonnage-weighted across the
    representative plan's FuelEU-deficit vessel-years (only Band A is ever
    FuelEU-applicable — see `docs/scope_matrix.md`).

    CII's corrective-action second marker (PLAN.md §3.6b, item 1's "optional
    second marker") is *not* computed here: `implied_price.cii_implied_price`
    needs a stated corrective-action cost and the tonnage it addresses, and
    no such figure exists anywhere in fleet.json to supply it honestly —
    inventing one just to populate an optional field would be a worse choice
    than reporting it as not computed this pass, matching `compliance_cost
    .cii_cost`'s own documented deferral of the same route.
    """
    resolved = resolve_regulations_for_scenario(scenario["id"])
    vessels_by_id = {v["vessel_id"]: v for v in fleet["vessels"]}
    eur_to_usd_rate = prices["carbon_allowances"]["eu_ets_eua"]["eur_to_usd_rate"]

    weighted_sum = 0.0
    weight_total = 0.0
    for gene in representative_genome:
        vessel = vessels_by_id[gene.vessel_id]
        facts = vessel_year_facts(gene, vessel, fleet, resolved, fuel_model)
        if not facts.applicability["fuel_eu"].applies or facts.raw_fuel_eu_balance_gco2eq >= 0:
            continue
        implied = fueleu_implied_price(
            facts.raw_fuel_eu_balance_gco2eq,
            facts.actual_ghg_intensity_gco2e_per_mj,
            eur_to_usd_rate=eur_to_usd_rate,
        )
        weight = abs(facts.raw_fuel_eu_balance_gco2eq) / 1e6
        weighted_sum += implied.value_usd_per_tco2e * weight
        weight_total += weight

    cii_caveat = (
        "CII's corrective-action second marker (§3.6b) is not computed this pass: no "
        "corrective-action-cost figure exists in fleet.json to feed cii_implied_price honestly."
    )
    if weight_total <= 0:
        return ScenarioAxisPosition(
            scenario_id=scenario["id"],
            label=scenario["label"],
            kind=scenario["price_axis_treatment"],
            low_usd_per_tco2e=None,
            high_usd_per_tco2e=None,
            operating_point_usd_per_tco2e=None,
            status="NOT_APPLICABLE_NO_PRICE_BASIS",
            notes=f"{scenario['notes']} No FuelEU deficit in the representative plan -- implied price undefined. {cii_caveat}",
        )

    point = weighted_sum / weight_total
    return ScenarioAxisPosition(
        scenario_id=scenario["id"],
        label=scenario["label"],
        kind=scenario["price_axis_treatment"],
        low_usd_per_tco2e=point,
        high_usd_per_tco2e=point,
        operating_point_usd_per_tco2e=point,
        status="SECONDARY_SOURCE",
        notes=(
            f"{scenario['notes']} Computed via implied_price.fueleu_implied_price, tonnage-weighted "
            f"across the representative plan's FuelEU-deficit vessel-years. {cii_caveat}"
        ),
    )


def _eu_ets_reference_tick(prices: dict[str, Any]) -> ScenarioAxisPosition:
    """EU ETS's real, currently-posted price as a fixed reference tick —
    not one of the K=5 vote outcomes, but PLAN.md §3.6(b) places it on the
    same axis as a point ("a genuine single posted price") since it stacks
    with whichever NZF outcome is realized."""
    eua = prices["carbon_allowances"]["eu_ets_eua"]
    price = eua["price_usd_per_tco2e"]
    return ScenarioAxisPosition(
        scenario_id="eu_ets_reference",
        label="EU ETS (current EUA spot)",
        kind="point",
        low_usd_per_tco2e=price,
        high_usd_per_tco2e=price,
        operating_point_usd_per_tco2e=price,
        status=eua["status"],
        notes=(
            "Not one of scenarios.json's K=5 regulatory-vote outcomes -- EU ETS is already priced "
            "today and stacks with whichever NZF outcome is realized (PLAN.md §3.6b)."
        ),
    )


def scenario_axis_positions(
    fleet: dict[str, Any],
    prices: dict[str, Any],
    *,
    representative_genome: Genome | None = None,
    representative_seed: int = 0,
    fuel_model: FuelModel | None = None,
) -> list[ScenarioAxisPosition]:
    """Every K=5 scenario's position on the effective-marginal-carbon-price
    axis, plus the EU ETS reference tick (Task 2R component 4, item 4).

    `representative_genome` stands in for "the case study's own deficit
    distribution" (PLAN.md §3.6b): if not supplied, one is produced by a
    small solve under the real (non-swept) approved-text economics — the
    fleet's realistic operating configuration, not a random one, and not one
    optimized under the extreme end of the sweep grid.
    """
    fuel_model = fuel_model or PhysicsFuelModel()
    if representative_genome is None:
        representative_genome = solver.run_ga(
            fleet,
            resolve_regulations_for_scenario("approved_text"),
            prices,
            seed=representative_seed,
            population_size=30,
            n_generations=15,
        ).best_genome

    positions: list[ScenarioAxisPosition] = []
    for scenario in load_scenarios()["scenarios"]:
        kind = scenario["price_axis_treatment"]
        resolved = resolve_regulations_for_scenario(scenario["id"])
        base_note = scenario.get("notes", scenario["description"])

        if kind == "tier_annotated_range":
            tier_prices = resolved["regimes"]["nzf"]["tier_prices_usd_per_tco2e"]
            operating_point = _fleet_nzf_operating_point(representative_genome, fleet, resolved, fuel_model)
            positions.append(
                ScenarioAxisPosition(
                    scenario_id=scenario["id"],
                    label=scenario["label"],
                    kind=kind,
                    low_usd_per_tco2e=tier_prices["tier_1"],
                    high_usd_per_tco2e=tier_prices.get("tier_2"),
                    operating_point_usd_per_tco2e=operating_point,
                    status="SECONDARY_SOURCE",
                    notes=(
                        f"{base_note} Operating point computed from a representative solved fleet "
                        "plan's own NZF deficit distribution (PLAN.md §3.6b), not assumed."
                        if operating_point is not None
                        else f"{base_note} No NZF deficit in the representative plan -- operating point undefined."
                    ),
                )
            )
        elif kind == "qualitative_marker":
            positions.append(
                ScenarioAxisPosition(
                    scenario_id=scenario["id"],
                    label=scenario["label"],
                    kind=kind,
                    low_usd_per_tco2e=None,
                    high_usd_per_tco2e=None,
                    operating_point_usd_per_tco2e=None,
                    status="NOT_APPLICABLE_NO_PRICE_BASIS",
                    notes=base_note,
                )
            )
        elif scenario["id"] == "adoption_fails":
            positions.append(
                _adoption_fails_axis_position(scenario, fleet, prices, representative_genome, fuel_model)
            )
        else:
            # brazil: scenarios.json flags the same "requires_implied_price_converter"
            # treatment, but its conversion (a reduction-percentage schedule, not a
            # penalty formula) has no implied_price.py function to call — item 1
            # scopes the implied-price requirement to scenario 5 only, so this is
            # reported as not computed rather than guessed at.
            positions.append(
                ScenarioAxisPosition(
                    scenario_id=scenario["id"],
                    label=scenario["label"],
                    kind=kind,
                    low_usd_per_tco2e=None,
                    high_usd_per_tco2e=None,
                    operating_point_usd_per_tco2e=None,
                    status="NOT_APPLICABLE_NO_PRICE_BASIS",
                    notes=(
                        f"{base_note} Not computed this pass -- Task 2R component 4 scopes the "
                        "implied-price requirement to scenario 5 (adoption_fails) only."
                    ),
                )
            )

    positions.append(_eu_ets_reference_tick(prices))
    return positions


@dataclass(frozen=True)
class SweepResult:
    price_grid: tuple[float, ...]
    resolution_usd_per_tco2e: float
    grid_points: list[GridPointResult]
    switching_points: list[SwitchingPoint]
    warm_start_benchmark: WarmStartBenchmark
    scenario_ticks: list[ScenarioAxisPosition]


def run_sweep(
    fleet: dict[str, Any],
    prices: dict[str, Any],
    *,
    price_grid: Sequence[float] = DEFAULT_PRICE_GRID,
    seed: int = 0,
    population_size: int = 40,
    cold_generations: int = 40,
    warm_generations: int = 12,
    tournament_size: int = 3,
) -> SweepResult:
    """Solve the fleet plan at every grid point, warm-started from the
    previous point's best genome, and extract switching points + scenario
    ticks from the result (Task 2R component 4).

    Deterministic for a fixed `seed`: each grid point's solve uses
    `seed + its index`, so two calls with the same `seed`/`fleet`/`prices`
    return an identical `SweepResult` (item 5's reproducibility requirement).

    Caveat inherent to a GA-based sweep, not hidden here: a switching point
    is a genuine economic response only when its consequences persist as
    price moves further in the same direction; an isolated flip at one grid
    step (especially the first one, off a single cold solve) can instead be
    the search still settling rather than the true optimum changing. Band C
    vessel-years are filtered out for exactly this reason (see
    `extract_switching_points`); the remaining ones are the best a
    finite-population, finite-generation search can report at this grid's
    resolution, not an exhaustive guarantee.
    """
    if len(price_grid) < 2:
        raise ValueError("price_grid needs at least two points to extract switching points")
    resolution = price_grid[1] - price_grid[0]

    base_regulations = resolve_regulations_for_scenario("approved_text")
    grid_points: list[GridPointResult] = []
    warm_start_benchmark: WarmStartBenchmark | None = None
    previous_genome: Genome | None = None

    for index, price in enumerate(price_grid):
        regulations = _nzf_price_override(base_regulations, price)
        grid_seed = seed + index  # distinct-but-deterministic per grid point

        if previous_genome is None:
            start = time.perf_counter()
            result = solver.run_ga(
                fleet,
                regulations,
                prices,
                seed=grid_seed,
                population_size=population_size,
                n_generations=cold_generations,
                tournament_size=tournament_size,
            )
            elapsed = time.perf_counter() - start
            grid_points.append(
                GridPointResult(price, result.best_genome, result.best_total_usd, elapsed, False, cold_generations)
            )
        else:
            start = time.perf_counter()
            result = solver.run_ga(
                fleet,
                regulations,
                prices,
                seed=grid_seed,
                population_size=population_size,
                n_generations=warm_generations,
                tournament_size=tournament_size,
                seed_genome=previous_genome,
            )
            warm_elapsed = time.perf_counter() - start
            grid_points.append(
                GridPointResult(price, result.best_genome, result.best_total_usd, warm_elapsed, True, warm_generations)
            )

            if warm_start_benchmark is None:
                # Measure the "seconds, not free" number once, at this same
                # price point: an actual cold-solve time to compare against,
                # not an assumed one (item 2).
                cold_start = time.perf_counter()
                solver.run_ga(
                    fleet,
                    regulations,
                    prices,
                    seed=grid_seed,
                    population_size=population_size,
                    n_generations=cold_generations,
                    tournament_size=tournament_size,
                )
                cold_elapsed = time.perf_counter() - cold_start
                warm_start_benchmark = WarmStartBenchmark(
                    price, cold_elapsed, warm_elapsed, cold_generations, warm_generations
                )

        previous_genome = result.best_genome

    switching_points = extract_switching_points(grid_points, fleet=fleet)
    scenario_ticks = scenario_axis_positions(fleet, prices, representative_seed=seed)

    assert warm_start_benchmark is not None  # guaranteed: price_grid has >= 2 points
    return SweepResult(
        price_grid=tuple(price_grid),
        resolution_usd_per_tco2e=resolution,
        grid_points=grid_points,
        switching_points=switching_points,
        warm_start_benchmark=warm_start_benchmark,
        scenario_ticks=scenario_ticks,
    )


def sweep_result_to_dict(result: SweepResult) -> dict[str, Any]:
    """A fully JSON-serializable view of `result` for `sweep_results.json` —
    grid -> configurations -> switching points -> scenario ticks, every
    figure carrying the status/notes discipline component 3 established for
    cost figures, extended here to axis positions."""
    return {
        "document_version": "task2r-component4-v1",
        "provenance_note": (
            "Carbon-price sweep + switching-point extraction (Task 2R component 4, "
            "prototype version, PLAN.md §3.6). Grid solves are warm-started from the "
            "previous point's best genome; see warm_start_benchmark for the measured "
            "warm-vs-cold timing. Switching points are resolved only to the grid step "
            "(price_low, price_high]. Band C vessel-years are excluded from switching "
            "points: they fall under none of the four regimes, so they're provably "
            "invariant to this axis, and any apparent flip there is GA search noise."
        ),
        "price_grid": list(result.price_grid),
        "resolution_usd_per_tco2e": result.resolution_usd_per_tco2e,
        "warm_start_benchmark": asdict(result.warm_start_benchmark),
        "grid_points": [
            {
                "price_usd_per_tco2e": gp.price_usd_per_tco2e,
                "total_usd": gp.total_usd,
                "solve_seconds": gp.solve_seconds,
                "warm_started": gp.warm_started,
                "generations_run": gp.generations_run,
                "configuration": [
                    {
                        "vessel_id": gene.vessel_id,
                        "year": gene.year,
                        "route_id": gene.route_id,
                        "speed_band_index": gene.speed_band_index,
                        "fuel_id": gene.fuel_id,
                        "shore_power": gene.shore_power,
                        "pool_opt_in": gene.pool_opt_in,
                        "borrow_election": gene.borrow_election,
                    }
                    for gene in gp.genome
                ],
            }
            for gp in result.grid_points
        ],
        "switching_points": [asdict(sp) for sp in result.switching_points],
        "scenario_ticks": [asdict(tick) for tick in result.scenario_ticks],
    }


def write_sweep_results(path: str, result: SweepResult) -> None:
    """Write `sweep_result_to_dict(result)` to `path` as `sweep_results.json`."""
    import json

    with open(path, "w") as f:
        json.dump(sweep_result_to_dict(result), f, indent=2)


if __name__ == "__main__":
    from knotwise.fleet.loader import load_fleet, load_prices

    _fleet = load_fleet()
    _prices = load_prices()
    _result = run_sweep(_fleet, _prices)
    write_sweep_results("sweep_results.json", _result)
    print(f"wrote sweep_results.json: {len(_result.grid_points)} grid points, {len(_result.switching_points)} switching points")
