"""Hard operating constraints for fleet-plan feasibility.

Fuel compatibility remains owned by ``fleet.model.option_menu_for``.  This
module owns the constraints that depend on a complete annual assignment:

- a route-specific annual-service envelope (sea transit + port service <=
  post-maintenance availability); and
- annual cargo demand measured in tonne-nautical-miles, not a DWT proxy.

Both return an infinite cost at the objective boundary, while genome operators
construct and repair plans to stay inside the same feasible region.
"""

from __future__ import annotations

from typing import Any

from knotwise.fleet.model import option_menu_for
from knotwise.optimization.annual_service import annual_service_facts, route_demand_tonne_nm
from knotwise.optimization.costs import CostBreakdown

#: The two physically implausible lowest bands remain unavailable even before
#: route-specific annual-service availability is applied.
MIN_SPEED_BAND_INDEX = 2


def allowed_speed_band_indices(n_bands: int) -> range:
    """The global speed-floor domain, independent of one route assignment."""
    return range(MIN_SPEED_BAND_INDEX, n_bands)


def feasible_speed_band_indices(vessel: dict[str, Any], fleet: dict[str, Any], year: int, route_id: str) -> list[int]:
    """Speed bands that satisfy both the global floor and annual service time."""
    menu = option_menu_for(vessel, fleet, year)
    if route_id not in menu.routes:
        raise ValueError(f"{route_id} is not a valid route for {vessel['vessel_id']}")
    return [
        index
        for index in allowed_speed_band_indices(len(menu.speed_bands_knots))
        if annual_service_facts(vessel, fleet, route_id, menu.speed_bands_knots[index]).feasible
    ]


def annual_service_penalty(
    vessel: dict[str, Any], fleet: dict[str, Any], year: int, route_id: str, speed_band_index: int
) -> CostBreakdown:
    """Return infeasible when a vessel cannot complete its annual service."""
    menu = option_menu_for(vessel, fleet, year)
    if speed_band_index not in allowed_speed_band_indices(len(menu.speed_bands_knots)):
        return CostBreakdown(float("inf"), "INFEASIBLE", "speed band is below the operational floor")
    facts = annual_service_facts(vessel, fleet, route_id, menu.speed_bands_knots[speed_band_index])
    if facts.feasible:
        return CostBreakdown(0.0, "FEASIBLE", f"annual service {facts.total_service_days:.1f}/{facts.available_days:.0f} days")
    return CostBreakdown(
        float("inf"),
        "INFEASIBLE",
        f"annual service requires {facts.total_service_days:.1f} days; {facts.available_days:.0f} are available",
    )


def cargo_shortfall_penalty(
    fleet: dict[str, Any], route_id: str, assigned_cargo_tonne_nm: float, demand_multiplier: float = 1.0
) -> CostBreakdown:
    """Return infeasible when annual cargo demand exceeds allocated capacity."""
    required = route_demand_tonne_nm(fleet, route_id, demand_multiplier)
    shortfall = max(required - assigned_cargo_tonne_nm, 0.0)
    if shortfall <= 0:
        return CostBreakdown(0.0, "FEASIBLE", f"{route_id}: annual cargo demand met.")
    return CostBreakdown(
        float("inf"),
        "INFEASIBLE",
        f"{route_id}: annual cargo shortfall {shortfall:.0f} tonne-nm; rejected as infeasible.",
    )
