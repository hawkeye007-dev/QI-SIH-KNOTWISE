"""Fleet-model access helpers (Task 2R component 2).

Builds `knotwise.compliance.scope_gating` types directly from `fleet.json`
records rather than redefining a parallel vessel/voyage representation, and
exposes the per-vessel-year decision-variable option menu that component 3's
solver searches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from knotwise.compliance.scope_gating import VesselSpec, VoyagePattern

_SPEED_BAND_FRACTIONS_OF_DESIGN_SPEED = (0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00)
_SHORE_POWER_AVAILABLE_BANDS = {"A", "B"}  # deep-sea vessels calling major ports; ILLUSTRATIVE


@dataclass(frozen=True)
class OptionMenu:
    routes: list[str]
    speed_bands_knots: list[float]
    fuels: list[str]
    shore_power_available: bool


def vessel_spec(vessel: dict[str, Any], fleet: dict[str, Any]) -> VesselSpec:
    """Build a `VesselSpec` from the vessel's band's class defaults."""
    defaults = fleet["vessel_class_defaults"][vessel["band"]]
    return VesselSpec(gross_tonnage=defaults["gross_tonnage"])


def vessel_voyage_pattern(vessel: dict[str, Any], fleet: dict[str, Any]) -> VoyagePattern:
    """Build a `VoyagePattern` from the vessel's default route."""
    route = fleet["routes"][vessel["default_route"]]
    return VoyagePattern(**route["voyage_pattern"])


def speed_bands_knots(design_speed_knots: float) -> list[float]:
    """8 speed bands from 65% to 100% of design speed, in 5% steps.

    ILLUSTRATIVE: PLAN.md §5.4 specifies "8 speed bands" but gives no exact
    values; this is a representative slow-steaming-to-design-speed range
    derived from each vessel's own design speed, not a fixed absolute figure.
    """
    return [round(design_speed_knots * fraction, 2) for fraction in _SPEED_BAND_FRACTIONS_OF_DESIGN_SPEED]


def option_menu_for(vessel: dict[str, Any], fleet: dict[str, Any], year: int) -> OptionMenu:
    """The decision-variable option menu for `vessel` in `year`.

    Same menu for every year in `fleet["horizon_years"]` — no retrofit
    modelling in this pass (a vessel's engine type, and therefore its fuel
    menu, does not change over its own horizon here; see Task 2R component 2
    plan's non-goals). `year` is accepted for forward compatibility with a
    future retrofit-aware menu and to keep this a per-vessel-year lookup, as
    the option-menu concept is specified.
    """
    if year not in fleet["horizon_years"]:
        raise ValueError(f"year {year} is outside this fleet's horizon {fleet['horizon_years']}")

    routes = [route_id for route_id, route in fleet["routes"].items() if route["band"] == vessel["band"]]
    defaults = fleet["vessel_class_defaults"][vessel["band"]]
    fuels = fleet["engine_fuel_compatibility"]["matrix"][vessel["engine_type"]]

    return OptionMenu(
        routes=routes,
        speed_bands_knots=speed_bands_knots(defaults["design_speed_knots"]),
        fuels=list(fuels),
        shore_power_available=vessel["band"] in _SHORE_POWER_AVAILABLE_BANDS,
    )
