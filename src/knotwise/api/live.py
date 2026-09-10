"""Validated live decision requests, independent of the HTTP transport."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from knotwise.fleet.loader import load_fleet, load_prices
from knotwise.fleet.model import option_menu_for
from knotwise.optimization.alternatives import build_comparable_alternatives
from knotwise.optimization.annual_service import annual_service_facts, route_demand_tonne_nm
from knotwise.optimization.constraints import feasible_speed_band_indices
from knotwise.optimization.fuel_model import FuelModel, PhysicsFuelModel
from knotwise.optimization.sweep import regulations_for_carbon_price
from knotwise.regulatory.scenario_resolution import resolve_regulations_for_scenario

MIN_CARBON_PRICE_USD_PER_TCO2E = 0.0
MAX_CARBON_PRICE_USD_PER_TCO2E = 1_000.0
MIN_DEMAND_MULTIPLIER = 0.1
MAX_DEMAND_MULTIPLIER = 10.0


@dataclass(frozen=True)
class LiveScenario:
    carbon_price_usd_per_tco2e: float
    cargo_demand_multiplier: float


def parse_live_scenario(payload: dict[str, Any]) -> LiveScenario:
    """Validate the only two supported live inputs with useful error text."""
    try:
        price = float(payload["carbon_price_usd_per_tco2e"])
        demand = float(payload["cargo_demand_multiplier"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("carbon_price_usd_per_tco2e and cargo_demand_multiplier must be numbers") from error
    if not MIN_CARBON_PRICE_USD_PER_TCO2E <= price <= MAX_CARBON_PRICE_USD_PER_TCO2E:
        raise ValueError(f"carbon price must be between {MIN_CARBON_PRICE_USD_PER_TCO2E:g} and {MAX_CARBON_PRICE_USD_PER_TCO2E:g}")
    if not MIN_DEMAND_MULTIPLIER <= demand <= MAX_DEMAND_MULTIPLIER:
        raise ValueError(f"cargo demand multiplier must be between {MIN_DEMAND_MULTIPLIER:g} and {MAX_DEMAND_MULTIPLIER:g}")
    return LiveScenario(price, demand)


def fleet_with_demand_multiplier(fleet: dict[str, Any], multiplier: float) -> dict[str, Any]:
    """Return an isolated fleet view so one live request cannot mutate another."""
    adjusted = copy.deepcopy(fleet)
    for route in adjusted["routes"].values():
        route["annual_cargo_demand_tonne_nm"] *= multiplier
    return adjusted


@lru_cache(maxsize=1)
def live_fuel_model() -> tuple[FuelModel, str, str | None]:
    """Use the validated predictor once per API process, with explicit fallback."""
    try:
        from knotwise.optimization.fuel_predictors import (
            VALIDATED_DEPLOYMENT_PREDICTOR_ID,
            fit_validated_deployment_predictor,
        )

        return fit_validated_deployment_predictor(load_fleet()), VALIDATED_DEPLOYMENT_PREDICTOR_ID, None
    except Exception as error:
        return PhysicsFuelModel(), "physics", f"{type(error).__name__}: {error}"


def impossible_route_reasons(fleet: dict[str, Any]) -> list[dict[str, Any]]:
    """Prove obvious route-level cargo impossibility before running a search.

    The bound generously assigns every vessel to a route, so exceeding it is a
    definitive infeasibility result. Passing it is not presented as a proof of
    fleet-wide feasibility; the optimizer still enforces all coupled cargo and
    annual-service constraints.
    """
    reasons: list[dict[str, Any]] = []
    for route_id in fleet["routes"]:
        required = route_demand_tonne_nm(fleet, route_id)
        capacity = 0.0
        for vessel in fleet["vessels"]:
            for year in fleet["horizon_years"]:
                menu = option_menu_for(vessel, fleet, year)
                if route_id not in menu.routes:
                    continue
                speeds = feasible_speed_band_indices(vessel, fleet, year, route_id)
                if speeds:
                    capacity += annual_service_facts(
                        vessel, fleet, route_id, menu.speed_bands_knots[speeds[0]]
                    ).annual_cargo_tonne_nm
                    break
        if required > capacity + 1e-6:
            reasons.append({
                "route_id": route_id,
                "required_tonne_nm_per_year": required,
                "maximum_possible_tonne_nm_per_year": capacity,
                "message": "Demand exceeds the annual cargo throughput of every eligible vessel combined.",
            })
    return reasons


def solve_live_scenario(
    scenario: LiveScenario,
    *,
    fuel_model: FuelModel | None = None,
    optimizer: str = "qiea",
    population_size: int = 20,
    n_generations: int = 15,
) -> dict[str, Any]:
    """Return authoritative alternatives or a structured infeasibility result."""
    fleet = fleet_with_demand_multiplier(load_fleet(), scenario.cargo_demand_multiplier)
    reasons = impossible_route_reasons(fleet)
    if reasons:
        return {"status": "INFEASIBLE", "reasons": reasons}

    regulations = regulations_for_carbon_price(
        resolve_regulations_for_scenario("approved_text"), scenario.carbon_price_usd_per_tco2e
    )
    model, model_id, fallback_reason = (fuel_model, "caller_supplied", None) if fuel_model else live_fuel_model()
    try:
        result = build_comparable_alternatives(
            fleet,
            regulations,
            load_prices(),
            fuel_model=model,
            optimizer=optimizer,  # type: ignore[arg-type]
            population_size=population_size,
            n_generations=n_generations,
        )
    except ValueError as error:
        return {
            "status": "INFEASIBLE",
            "reasons": [{
                "message": str(error),
                "kind": "coupled_fleet_constraint",
            }],
        }
    result["scenario"] = {
        "scenario_id": "approved_text",
        "effective_carbon_price_usd_per_tco2e": scenario.carbon_price_usd_per_tco2e,
        "cargo_demand_multiplier": scenario.cargo_demand_multiplier,
        "note": "Live synthetic scenario; all alternatives use these identical inputs.",
    }
    result["provenance"] = {
        "optimizer": optimizer,
        "fuel_model": model_id,
        "fuel_model_fallback_reason": fallback_reason,
    }
    return result
