"""Hard and soft constraints (Task 2R component 3, item 2).

Compatibility masks (fuel/engine-type) are already enforced by
`knotwise.fleet.model.option_menu_for` (component 2) — not re-implemented
here. This module covers the two constraints component 3 adds:

- **Schedule reliability (speed floor)**: a true hard mask, applied in
  `genome.py`'s sampling (never generating the two slowest of 8 bands) rather
  than by shrinking `option_menu_for`'s own output, which stays 8 bands to
  preserve component 2's already-committed contract and tests.
- **Demand constraint**: a softer, explicitly-ILLUSTRATIVE constraint (per
  the task's own framing) — a large penalty rather than outright rejection,
  since under-serving a route-year is a modelling simplification's failure
  mode, not a regulatory hard invariant.
"""

from __future__ import annotations

from typing import Any

from knotwise.optimization.costs import CostBreakdown

#: Skip the 2 slowest of the 8 speed bands `fleet.model.speed_bands_knots`
#: produces — "so plans stay operable" (Task 2R component 3, item 2).
MIN_SPEED_BAND_INDEX = 2

#: ILLUSTRATIVE — large enough that the GA never prefers leaving a route
#: under-served over any realistic combination of the other cost terms.
DEMAND_PENALTY_USD_PER_DWT_SHORTFALL = 10_000


def allowed_speed_band_indices(n_bands: int) -> range:
    """Indices into `option_menu_for(...).speed_bands_knots` the solver may pick from."""
    return range(MIN_SPEED_BAND_INDEX, n_bands)


def demand_shortfall_penalty(fleet: dict[str, Any], route_id: str, assigned_dwt_total: float) -> CostBreakdown:
    """ILLUSTRATIVE penalty when a route-year's assigned capacity falls short of the demand floor."""
    required = fleet["routes"][route_id]["min_capacity_dwt_required"]
    shortfall = max(required - assigned_dwt_total, 0.0)
    if shortfall <= 0:
        return CostBreakdown(0.0, "ILLUSTRATIVE", f"{route_id}: demand met.")
    return CostBreakdown(
        shortfall * DEMAND_PENALTY_USD_PER_DWT_SHORTFALL,
        "ILLUSTRATIVE",
        f"{route_id}: under-served by {shortfall:.0f} DWT.",
    )
