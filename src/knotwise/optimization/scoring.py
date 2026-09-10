"""Objective policies for choosing among already-feasible fleet plans.

The economic objective remains the source of all hard operational constraints:
``objective.evaluate`` returns an infinite total whenever annual service or
cargo throughput fails.  This module deliberately changes only how feasible
plans are ranked for a decision scenario; it does not duplicate feasibility
logic or make a frontend responsible for fleet physics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from knotwise.optimization.fuel_model import FuelModel, PhysicsFuelModel
from knotwise.optimization.genome import Genome
from knotwise.optimization.objective import ObjectiveResult, vessel_year_facts


ScoringKind = Literal["cost", "lifecycle_emissions", "cost_under_emissions_cap"]


def lifecycle_emissions_tco2e(
    genome: Genome,
    fleet: dict[str, Any],
    regulations: dict[str, Any],
    fuel_model: FuelModel | None = None,
) -> float:
    """Lifecycle GHG for a plan under its exact fuel model, in tCO2e.

    This is intentionally separate from cost.  A lower-emissions alternative
    is not assumed to be cheaper, and no weighted score conceals that tradeoff.
    """
    fuel_model = fuel_model or PhysicsFuelModel()
    vessels = {vessel["vessel_id"]: vessel for vessel in fleet["vessels"]}
    total = 0.0
    for gene in genome:
        facts = vessel_year_facts(gene, vessels[gene.vessel_id], fleet, regulations, fuel_model)
        total += facts.energy_mj * facts.actual_ghg_intensity_gco2e_per_mj / 1_000_000
    return total


@dataclass(frozen=True)
class PlanScorer:
    """One explicit way to rank feasible plans for one fixed scenario.

    ``cost_under_emissions_cap`` is the project's definition of *Balanced*:
    it is the cheapest plan whose lifecycle emissions do not exceed the stated
    cap.  Returning infinity outside that cap lets the solver retain its usual
    minimization semantics while making infeasible tradeoffs impossible to
    present as a recommendation.
    """

    kind: ScoringKind = "cost"
    emissions_cap_tco2e: float | None = None

    def score(
        self,
        genome: Genome,
        objective: ObjectiveResult,
        fleet: dict[str, Any],
        regulations: dict[str, Any],
        fuel_model: FuelModel | None = None,
    ) -> float:
        if objective.total_usd == float("inf"):
            return float("inf")
        if self.kind == "cost":
            return objective.total_usd

        emissions = lifecycle_emissions_tco2e(genome, fleet, regulations, fuel_model)
        if self.kind == "lifecycle_emissions":
            return emissions
        if self.emissions_cap_tco2e is None:
            raise ValueError("cost_under_emissions_cap requires emissions_cap_tco2e")
        return objective.total_usd if emissions <= self.emissions_cap_tco2e + 1e-6 else float("inf")
