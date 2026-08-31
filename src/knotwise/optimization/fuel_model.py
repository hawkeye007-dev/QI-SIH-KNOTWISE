"""Pluggable fuel-consumption model (Task 2R component 3).

`FuelModel` is the mandatory interface: Phase 2's learned predictor and the
tensor core's particle evaluator (later phases) call through this exact
signature, so it is fixed now rather than grown ad hoc. `PhysicsFuelModel` is
the physics-only implementation for this component, derived from the
Admiralty relation (power ∝ Δ^(2/3)·V³), calibrated per vessel band via
`fleet.json`'s `anchor_daily_energy_mj_at_design_speed`.

Two distinct, both-intentional scaling laws (see `docs/PLAN.md` §1.1 and the
Task 2R component 3 plan's correction 2 for why this distinction matters —
an earlier draft of this model had it inverted):

- `daily_energy_mj` — **V³** (the Admiralty power law itself).
- `fuel_consumption_tonnes` (the full annual figure, at a route's fixed
  `distance_nm`) — **V²**: covering a fixed distance faster means fewer sea
  days, which partially offsets the V³ daily rate
  (`daily_energy(V) * (distance/(24V))` = `... * V**2`). Monotonically
  increasing in speed either way — it's `objective.py`'s per-sea-day charter
  premium (decreasing in speed) that turns this into a genuine trade-off with
  an interior optimum, not this module's job.

`fuel_id` is accepted and *used*, not just threaded through for a future
model's benefit: the energy required to move the ship at a given speed is
fuel-independent (physics), but the **mass** needed to deliver that energy
depends on the chosen fuel's own energy content (LCV) — methanol's LCV is
roughly half VLSFO's, so it takes roughly twice the mass for the same energy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


def sea_days(fleet: dict[str, Any], route_id: str, speed_knots: float) -> float:
    """Days at sea to cover `route_id`'s fixed annual distance at `speed_knots`.

    Shared by `PhysicsFuelModel.annual_energy_mj` and `objective.py`'s
    per-sea-day charter-premium term (Task 2R component 3 correction 2) —
    one formula, not duplicated across the two.
    """
    return fleet["routes"][route_id]["distance_nm"] / (24 * speed_knots)


class FuelModel(Protocol):
    """Mandatory interface — any fuel model (physics, learned, hybrid) implements this."""

    def fuel_consumption_tonnes(
        self,
        vessel: dict[str, Any],
        fleet: dict[str, Any],
        year: int,
        speed_knots: float,
        fuel_id: str,
        route_id: str,
    ) -> float: ...


@dataclass(frozen=True)
class PhysicsFuelModel:
    """Admiralty-derived fuel model, calibrated per vessel band via fleet.json's anchor.

    `year` is accepted (part of the `FuelModel` interface) but unused here —
    the physics doesn't vary by year in this prototype; a learned model
    implementing the same interface may use it (e.g. hull-fouling drift).
    """

    def daily_energy_mj(self, vessel: dict[str, Any], fleet: dict[str, Any], speed_knots: float) -> float:
        """Admiralty power law: energy demand per day at sea, at `speed_knots`."""
        defaults = fleet["vessel_class_defaults"][vessel["band"]]
        design_speed = defaults["design_speed_knots"]
        anchor = defaults["anchor_daily_energy_mj_at_design_speed"]
        return anchor * (speed_knots / design_speed) ** 3

    def annual_energy_mj(
        self, vessel: dict[str, Any], fleet: dict[str, Any], speed_knots: float, route_id: str
    ) -> float:
        """Total annual energy demand for `vessel` on `route_id` at `speed_knots`.

        Fuel-independent — this is what `compliance_cost.py` uses directly for
        `energy_used_mj`, since compliance formulas care about energy consumed,
        not fuel mass burned.
        """
        return self.daily_energy_mj(vessel, fleet, speed_knots) * sea_days(fleet, route_id, speed_knots)

    def fuel_consumption_tonnes(
        self,
        vessel: dict[str, Any],
        fleet: dict[str, Any],
        year: int,
        speed_knots: float,
        fuel_id: str,
        route_id: str,
    ) -> float:
        energy_mj = self.annual_energy_mj(vessel, fleet, speed_knots, route_id)
        lcv = fleet["fuel_properties"]["fuels"][fuel_id]["lcv_mj_per_tonne"]
        return energy_mj / lcv
