"""Annual-service feasibility and cargo-throughput calculations.

This module owns the operational terms that were previously conflated as a
route ``distance_nm`` and a DWT demand floor.  It deliberately models an
annual service envelope, not a voyage timetable: annual transit time plus
annual port-service time must fit after the vessel class's maintenance/off-hire
allowance.  It therefore supports defensible annual feasibility without
claiming arrival reliability or individual port-call scheduling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnnualServiceFacts:
    """One vessel's contribution when assigned to one route for one year."""

    sea_days: float
    port_service_days: float
    total_service_days: float
    available_days: float
    annual_cargo_tonne_nm: float

    @property
    def feasible(self) -> bool:
        return self.total_service_days <= self.available_days


def annual_service_facts(vessel: dict[str, Any], fleet: dict[str, Any], route_id: str, speed_knots: float) -> AnnualServiceFacts:
    """Return annual time and cargo capacity for one vessel-route assignment.

    Cargo is measured in tonne-nautical-miles: vessel DWT × stated payload
    utilisation × laden share of the route's annual transit distance.  This is
    compatible with an annual route distance and avoids pretending that DWT is
    annual cargo mass.
    """
    route = fleet["routes"][route_id]
    defaults = fleet["vessel_class_defaults"][vessel["band"]]
    sea_days = route["annual_transit_distance_nm"] / (24 * speed_knots)
    port_days = route["annual_port_service_days"]
    annual_cargo_tonne_nm = (
        defaults["dwt_tonnes"]
        * route["payload_utilization_fraction"]
        * route["laden_distance_fraction"]
        * route["annual_transit_distance_nm"]
    )
    return AnnualServiceFacts(
        sea_days=sea_days,
        port_service_days=port_days,
        total_service_days=sea_days + port_days,
        available_days=defaults["annual_service_available_days"],
        annual_cargo_tonne_nm=annual_cargo_tonne_nm,
    )


def route_demand_tonne_nm(fleet: dict[str, Any], route_id: str, demand_multiplier: float = 1.0) -> float:
    """The selected scenario's annual cargo demand for a route.

    ``demand_multiplier`` is the API/UI scenario input.  It is intentionally
    validated at this boundary so an impossible request is reported as
    infeasible rather than silently transformed into an unrelated plan.
    """
    if demand_multiplier < 0:
        raise ValueError("demand_multiplier must be non-negative")
    return fleet["routes"][route_id]["annual_cargo_demand_tonne_nm"] * demand_multiplier
