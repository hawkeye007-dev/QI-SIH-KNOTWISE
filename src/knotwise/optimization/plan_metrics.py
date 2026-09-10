"""Authoritative, serializable metrics for a solved fleet plan.

The optimizer is the sole owner of plan fuel, lifecycle emissions, cargo and
annual-service figures.  Frontends consume this result rather than restating
physics or feasibility calculations in JavaScript.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from knotwise.optimization.annual_service import annual_service_facts, route_demand_tonne_nm
from knotwise.optimization.constraints import annual_service_penalty, cargo_shortfall_penalty
from knotwise.optimization.fuel_model import FuelModel, PhysicsFuelModel
from knotwise.optimization.genome import Genome
from knotwise.optimization.objective import evaluate, vessel_year_facts
from knotwise.optimization.scoring import lifecycle_emissions_tco2e


def plan_metrics(
    genome: Genome,
    fleet: dict[str, Any],
    regulations: dict[str, Any],
    prices: dict[str, Any],
    fuel_model: FuelModel | None = None,
) -> dict[str, Any]:
    """Return all judge-facing metrics for one exact plan and scenario."""
    fuel_model = fuel_model or PhysicsFuelModel()
    objective = evaluate(genome, fleet, regulations, prices, fuel_model)
    vessels = {vessel["vessel_id"]: vessel for vessel in fleet["vessels"]}
    cargo_by_route_year: dict[tuple[str, int], float] = defaultdict(float)
    fuel_tonnes = 0.0
    emissions_tco2e = lifecycle_emissions_tco2e(genome, fleet, regulations, fuel_model)
    service_rows: list[dict[str, Any]] = []

    for gene in genome:
        vessel = vessels[gene.vessel_id]
        facts = vessel_year_facts(gene, vessel, fleet, regulations, fuel_model)
        service = annual_service_facts(vessel, fleet, gene.route_id, facts.speed_knots)
        fuel_tonnes += facts.tonnes
        cargo_by_route_year[(gene.route_id, gene.year)] += service.annual_cargo_tonne_nm
        service_check = annual_service_penalty(vessel, fleet, gene.year, gene.route_id, gene.speed_band_index)
        service_rows.append(
            {
                "vessel_id": gene.vessel_id,
                "year": gene.year,
                "route_id": gene.route_id,
                "speed_knots": facts.speed_knots,
                "sea_days": service.sea_days,
                "port_service_days": service.port_service_days,
                "total_service_days": service.total_service_days,
                "available_days": service.available_days,
                "status": service_check.status,
            }
        )

    cargo_rows: list[dict[str, Any]] = []
    for year in fleet["horizon_years"]:
        for route_id in fleet["routes"]:
            assigned = cargo_by_route_year[(route_id, year)]
            required = route_demand_tonne_nm(fleet, route_id)
            check = cargo_shortfall_penalty(fleet, route_id, assigned)
            cargo_rows.append(
                {
                    "route_id": route_id,
                    "year": year,
                    "required_tonne_nm": required,
                    "assigned_tonne_nm": assigned,
                    "status": check.status,
                }
            )

    return {
        "total_usd": objective.total_usd,
        "compliance_usd": sum(cost.amount_usd for cost in objective.compliance_costs.values()),
        "fuel_tonnes": fuel_tonnes,
        "lifecycle_emissions_tco2e": emissions_tco2e,
        "annual_service": {
            "passed": all(row["status"] == "FEASIBLE" for row in service_rows),
            "rows": service_rows,
        },
        "cargo": {
            "passed": all(row["status"] == "FEASIBLE" for row in cargo_rows),
            "rows": cargo_rows,
        },
    }
