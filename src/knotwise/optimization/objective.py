"""The objective function (Task 2R component 3, item 1) — composes fuel cost,
OPEX, time cost, and all four regimes' compliance costs into one total, with
a mandatory per-category status label on every leaf (item 4).

This is the module that turns a genome (a full fleet-configuration candidate)
into a single number the solver optimizes — and the structured breakdown the
demo's Abatement/Perimeter split (a later component) will read from.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from knotwise.compliance.scope_gating import RegimeApplicability, VoyagePattern, applicable_regimes
from knotwise.fleet.model import OptionMenu, option_menu_for, vessel_spec
from knotwise.optimization.compliance_cost import (
    FuelEuYearInput,
    cii_cost,
    compute_fueleu_ledger,
    eu_ets_cost,
    fueleu_target_intensity,
    nzf_cost,
)
from knotwise.optimization.constraints import demand_shortfall_penalty
from knotwise.optimization.costs import CostBreakdown
from knotwise.optimization.fuel_model import FuelModel, PhysicsFuelModel, sea_days
from knotwise.optimization.genome import Genome
from knotwise.optimization.pooling import VesselPoolBalance, resolve_pool
from knotwise.regulatory.implied_price import fueleu_compliance_balance_gco2eq

#: Confidence ranking for combining many CostBreakdowns into one aggregate —
#: the aggregate is only ever as confident as its least-confident contributor
#: (never overstates confidence by averaging it away).
_CONFIDENCE_RANK = {
    "MARKET_QUOTE": 0,
    "VERIFIED_PER_DOCUMENT": 0,
    "PROXY": 1,
    "SECONDARY_SOURCE": 2,
    "ESTIMATE": 2,
    "ILLUSTRATIVE": 3,
    "NOT_APPLICABLE": 4,
    "NOT_APPLICABLE_NO_DIRECT_PENALTY": 4,
    "NOT_APPLICABLE_NO_PRICE_BASIS": 4,
}


def _combine(costs: list[CostBreakdown], label: str) -> CostBreakdown:
    if not costs:
        return CostBreakdown(0.0, "NOT_APPLICABLE", f"{label}: nothing to aggregate.")
    total = sum(c.amount_usd for c in costs)
    weakest = max(costs, key=lambda c: _CONFIDENCE_RANK.get(c.status, 99))
    return CostBreakdown(
        total,
        weakest.status,
        f"{label}: aggregated over {len(costs)} vessel-years; least-confident component status shown.",
    )


@dataclass(frozen=True)
class VesselYearFacts:
    """The regulation- and physics-facing facts for one vessel-year.

    Factored out of `evaluate()`'s own first pass (rather than left inline)
    so a second consumer can reuse the menu/shore-power/applicability
    derivation without re-deriving it: Task 2R component 4's carbon-price
    sweep needs exactly these facts — actual GHG intensity, the regulated
    energy each regime sees, and each regime's applicability — to compute a
    scenario's fleet-wide operating point (PLAN.md §3.6b), and would
    otherwise have had to duplicate this logic rather than call it.
    """

    menu: OptionMenu
    speed_knots: float
    tonnes: float
    energy_mj: float
    shore_power_elected: bool
    shore_power_extra_cost_usd: float
    applicability: dict[str, RegimeApplicability]
    actual_ghg_intensity_gco2e_per_mj: float
    regulated_energy_mj: float
    raw_fuel_eu_balance_gco2eq: float


def vessel_year_facts(
    gene: Any,
    vessel: dict[str, Any],
    fleet: dict[str, Any],
    regulations: dict[str, Any],
    fuel_model: FuelModel,
) -> VesselYearFacts:
    """Derive one vessel-year's physics and regulatory-applicability facts.

    Pure function of its arguments — no cost/price lookups here, so it's
    usable by anything that needs the regulation-facing numbers without also
    needing `prices.json` (e.g. the sweep's scenario-axis-position code,
    which prices nothing itself).
    """
    menu = option_menu_for(vessel, fleet, gene.year)
    route = fleet["routes"][gene.route_id]
    speed_knots = menu.speed_bands_knots[gene.speed_band_index]

    raw_tonnes = fuel_model.fuel_consumption_tonnes(vessel, fleet, gene.year, speed_knots, gene.fuel_id, gene.route_id)
    raw_energy_mj = fuel_model.annual_energy_mj(vessel, fleet, speed_knots, gene.route_id)

    shore_power_elected = gene.shore_power and menu.shore_power_available
    if shore_power_elected:
        berth_fraction = route["voyage_pattern"].get("eu_eea_berth_fraction", 0.0)
        reduction = fleet["shore_power_model"]["berth_fuel_reduction_fraction"]
        factor = 1 - berth_fraction * reduction
        tonnes = raw_tonnes * factor
        energy_mj = raw_energy_mj * factor
        shore_power_extra_cost = fleet["shore_power_model"]["cost_usd_per_vessel_year_when_elected"]
    else:
        tonnes = raw_tonnes
        energy_mj = raw_energy_mj
        shore_power_extra_cost = 0.0

    voyage_pattern = VoyagePattern(**route["voyage_pattern"])
    applicability = applicable_regimes(vessel_spec(vessel, fleet), voyage_pattern, gene.year, regulations)

    actual_intensity = fleet["fuel_properties"]["fuels"][gene.fuel_id]["ghg_intensity_gco2e_per_mj"]
    regulated_energy_mj = energy_mj * applicability["fuel_eu"].effective_obligation_fraction
    target = fueleu_target_intensity(regulations["regimes"]["fuel_eu"], gene.year)
    raw_balance = fueleu_compliance_balance_gco2eq(target, actual_intensity, regulated_energy_mj)

    return VesselYearFacts(
        menu=menu,
        speed_knots=speed_knots,
        tonnes=tonnes,
        energy_mj=energy_mj,
        shore_power_elected=shore_power_elected,
        shore_power_extra_cost_usd=shore_power_extra_cost,
        applicability=applicability,
        actual_ghg_intensity_gco2e_per_mj=actual_intensity,
        regulated_energy_mj=regulated_energy_mj,
        raw_fuel_eu_balance_gco2eq=raw_balance,
    )


@dataclass(frozen=True)
class ObjectiveResult:
    total_usd: float
    fuel_cost: CostBreakdown
    opex_cost: CostBreakdown
    time_cost: CostBreakdown
    compliance_costs: dict[str, CostBreakdown] = field(default_factory=dict)
    demand_penalty: CostBreakdown = field(default_factory=lambda: CostBreakdown(0.0, "ILLUSTRATIVE"))


def evaluate(
    genome: Genome,
    fleet: dict[str, Any],
    regulations: dict[str, Any],
    prices: dict[str, Any],
    fuel_model: FuelModel | None = None,
) -> ObjectiveResult:
    fuel_model = fuel_model or PhysicsFuelModel()
    vessels_by_id = {v["vessel_id"]: v for v in fleet["vessels"]}

    genes_by_vessel: dict[str, list] = defaultdict(list)
    for gene in genome:
        genes_by_vessel[gene.vessel_id].append(gene)
    for genes in genes_by_vessel.values():
        genes.sort(key=lambda g: g.year)

    fuel_costs: list[CostBreakdown] = []
    opex_costs: list[CostBreakdown] = []
    time_costs: list[CostBreakdown] = []
    cii_costs: list[CostBreakdown] = []
    eu_ets_costs: list[CostBreakdown] = []
    nzf_costs: list[CostBreakdown] = []

    # First pass: per-vessel-year physical/economic figures and every
    # single-year regime cost (CII, EU ETS, NZF). FuelEU is handled in a
    # second pass because it needs cross-vessel pooling resolved per year
    # before each vessel's multi-year ledger can be folded.
    context: dict[tuple[str, int], dict[str, Any]] = {}
    dwt_by_route_year: dict[tuple[str, int], float] = defaultdict(float)

    for vessel_id, genes in genes_by_vessel.items():
        vessel = vessels_by_id[vessel_id]
        band_defaults = fleet["vessel_class_defaults"][vessel["band"]]
        for gene in genes:
            facts = vessel_year_facts(gene, vessel, fleet, regulations, fuel_model)

            fuel_price_entry = prices["fuels"][gene.fuel_id]
            fuel_costs.append(
                CostBreakdown(
                    facts.tonnes * fuel_price_entry["price_usd_per_tonne"],
                    fuel_price_entry["status"],
                    f"{vessel_id}/{gene.year} fuel={gene.fuel_id}",
                )
            )
            opex_costs.append(
                CostBreakdown(
                    band_defaults["fixed_opex_usd_per_year"] + facts.shore_power_extra_cost_usd,
                    "ILLUSTRATIVE",
                    f"{vessel_id}/{gene.year}",
                )
            )
            time_costs.append(
                CostBreakdown(
                    band_defaults["charter_premium_usd_per_sea_day"]
                    * sea_days(fleet, gene.route_id, facts.speed_knots),
                    "ILLUSTRATIVE",
                    f"{vessel_id}/{gene.year}",
                )
            )
            cii_costs.append(cii_cost(facts.applicability["cii"]))
            eu_ets_costs.append(
                eu_ets_cost(
                    facts.applicability["eu_ets"],
                    facts.actual_ghg_intensity_gco2e_per_mj,
                    facts.energy_mj,
                    prices["carbon_allowances"]["eu_ets_eua"],
                )
            )
            nzf_costs.append(
                nzf_cost(
                    regulations["regimes"]["nzf"],
                    facts.applicability["nzf"],
                    gene.year,
                    facts.actual_ghg_intensity_gco2e_per_mj,
                    facts.energy_mj,
                )
            )

            context[(vessel_id, gene.year)] = {
                "gene": gene,
                "fuel_eu_applicability": facts.applicability["fuel_eu"],
                "raw_balance": facts.raw_fuel_eu_balance_gco2eq,
                "actual_intensity": facts.actual_ghg_intensity_gco2e_per_mj,
                "regulated_energy_mj": facts.regulated_energy_mj,
            }
            dwt_by_route_year[(gene.route_id, gene.year)] += band_defaults["dwt_tonnes"]

    # Pooling: resolved once per year, across every FuelEU-eligible vessel
    # that opted in that year (component 3's headline mechanism).
    pooled_vessel_years: set[tuple[str, int]] = set()
    pool_cost_by_vessel_year: dict[tuple[str, int], CostBreakdown] = {}
    for year in fleet["horizon_years"]:
        candidates = [
            (vessel_id, ctx)
            for (vessel_id, y), ctx in context.items()
            if y == year and ctx["fuel_eu_applicability"].applies and ctx["gene"].pool_opt_in
        ]
        if len(candidates) >= 2:
            balances = [VesselPoolBalance(vessel_id, ctx["raw_balance"]) for vessel_id, ctx in candidates]
            pool_result = resolve_pool(balances)
            if pool_result.accepted:
                for member in pool_result.members:
                    pooled_vessel_years.add((member.vessel_id, year))
                    pool_cost_by_vessel_year[(member.vessel_id, year)] = member.cost

    # FuelEU ledger: sequential per vessel across its full horizon, deferring
    # to the resolved pool's cost for any year that vessel ended up pooled in.
    fuel_eu_costs: list[CostBreakdown] = []
    eur_to_usd_rate = prices["carbon_allowances"]["eu_ets_eua"]["eur_to_usd_rate"]
    for vessel_id, genes in genes_by_vessel.items():
        year_inputs = [
            FuelEuYearInput(
                year=gene.year,
                actual_ghg_intensity_gco2e_per_mj=context[(vessel_id, gene.year)]["actual_intensity"],
                energy_used_mj=context[(vessel_id, gene.year)]["regulated_energy_mj"],
                borrow_election=gene.borrow_election,
                pooled=(vessel_id, gene.year) in pooled_vessel_years,
            )
            for gene in genes
        ]
        ledger_results = compute_fueleu_ledger(regulations["regimes"]["fuel_eu"], year_inputs, eur_to_usd_rate)
        for result in ledger_results:
            key = (vessel_id, result.year)
            fuel_eu_costs.append(pool_cost_by_vessel_year.get(key, result.cost))

    demand_costs = [
        demand_shortfall_penalty(fleet, route_id, dwt_by_route_year.get((route_id, year), 0.0))
        for year in fleet["horizon_years"]
        for route_id in fleet["routes"]
    ]

    compliance_costs = {
        "cii": _combine(cii_costs, "cii"),
        "eu_ets": _combine(eu_ets_costs, "eu_ets"),
        "nzf": _combine(nzf_costs, "nzf"),
        "fuel_eu": _combine(fuel_eu_costs, "fuel_eu"),
    }
    fuel_agg = _combine(fuel_costs, "fuel")
    opex_agg = _combine(opex_costs, "opex")
    time_agg = _combine(time_costs, "time")
    demand_agg = _combine(demand_costs, "demand")

    total = (
        fuel_agg.amount_usd
        + opex_agg.amount_usd
        + time_agg.amount_usd
        + demand_agg.amount_usd
        + sum(c.amount_usd for c in compliance_costs.values())
    )

    return ObjectiveResult(
        total_usd=total,
        fuel_cost=fuel_agg,
        opex_cost=opex_agg,
        time_cost=time_agg,
        compliance_costs=compliance_costs,
        demand_penalty=demand_agg,
    )
