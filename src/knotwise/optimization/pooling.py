"""FuelEU pooling economics (Task 2R component 3) — the headline mechanism.

Per DESIGN_NOTE_POOLING.md §2B: pooling is enforced **exactly**, never
approximated, at the level of a fully-sampled configuration — here, that
means a candidate genome's pool-membership choice for a given year, not any
compressed/summarized representation. If the proposed pool doesn't satisfy
every regulatory invariant, it is rejected outright (falls back to per-vessel
individual compliance that year via `compliance_cost.compute_fueleu_ledger`
with `pooled=False`) rather than partially or approximately honored.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from knotwise.optimization.costs import CostBreakdown


@dataclass(frozen=True)
class VesselPoolBalance:
    vessel_id: str
    balance_gco2eq: float  # this vessel's own raw FuelEU compliance balance for the year, pre-pool


@dataclass(frozen=True)
class PoolMemberResult:
    vessel_id: str
    balance_after_pool_gco2eq: float
    cost: CostBreakdown


@dataclass(frozen=True)
class PoolResult:
    accepted: bool
    total_balance_gco2eq: float
    members: list[PoolMemberResult] = field(default_factory=list)
    notes: str = ""


def resolve_pool(vessel_balances: list[VesselPoolBalance]) -> PoolResult:
    """Evaluate one year's proposed pool, exactly.

    Enforces, all three checked before anything is accepted:
    - total pool balance must be >= 0
    - a deficit entrant's balance must not worsen (it is fully offset to
      exactly 0 when the pool is accepted, since total >= 0 guarantees
      enough surplus exists to cover every deficit exactly)
    - a surplus entrant must not end in deficit

    Allocation rule when accepted (PLAN.md does not specify one, so this is a
    stated assumption, not asserted as *the* regulatory rule): each deficit
    vessel is offset to exactly 0; the surplus needed to do that is drawn
    from surplus vessels *proportionally* to each one's own surplus share.
    This is what makes the no-worsening/no-flip-to-deficit invariants hold
    automatically whenever `total_balance_gco2eq >= 0`, rather than needing a
    separate check.
    """
    total = sum(v.balance_gco2eq for v in vessel_balances)
    if total < 0:
        return PoolResult(
            accepted=False,
            total_balance_gco2eq=total,
            notes="Proposed pool total is negative — rejected outright, never partially honored.",
        )

    total_deficit = sum(-v.balance_gco2eq for v in vessel_balances if v.balance_gco2eq < 0)
    total_surplus = sum(v.balance_gco2eq for v in vessel_balances if v.balance_gco2eq > 0)

    members = []
    for vessel in vessel_balances:
        if vessel.balance_gco2eq < 0:
            balance_after = 0.0
            cost = CostBreakdown(0.0, "SECONDARY_SOURCE", "Deficit fully absorbed by the pool.")
        else:
            share_used = (vessel.balance_gco2eq / total_surplus) * total_deficit if total_surplus > 0 else 0.0
            balance_after = vessel.balance_gco2eq - share_used
            cost = CostBreakdown(
                0.0, "SECONDARY_SOURCE", f"Contributed {share_used:.0f} gCO2eq of surplus to the pool."
            )
        members.append(PoolMemberResult(vessel.vessel_id, balance_after, cost))

    return PoolResult(accepted=True, total_balance_gco2eq=total, members=members, notes="Pool accepted.")
