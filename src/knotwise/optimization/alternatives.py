"""Build directly comparable fleet alternatives for a single scenario.

This is intentionally not a price sweep.  Each plan is evaluated with the
same fleet, regulations, prices and fuel model; only the stated ranking rule
changes.  That is the minimum honest contract for a judge-facing choice.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from knotwise.optimization import qiea_solver, solver
from knotwise.optimization.fuel_model import FuelModel
from knotwise.optimization.genome import DECISION_FIELDS
from knotwise.optimization.plan_metrics import plan_metrics
from knotwise.optimization.scoring import PlanScorer


OptimizerName = Literal["ga", "qiea"]
BALANCED_EMISSIONS_GAP_FRACTION = 0.5


def _run(
    optimizer: OptimizerName,
    fleet: dict[str, Any],
    regulations: dict[str, Any],
    prices: dict[str, Any],
    *,
    seed: int,
    population_size: int,
    n_generations: int,
    fuel_model: FuelModel | None,
    scorer: PlanScorer,
    seed_genome=None,
) -> solver.SolverResult:
    kwargs = dict(
        seed=seed,
        population_size=population_size,
        n_generations=n_generations,
        fuel_model=fuel_model,
        scorer=scorer,
        seed_genome=seed_genome,
    )
    if optimizer == "ga":
        return solver.run_ga(fleet, regulations, prices, **kwargs)
    # The normal QIEA mean-field prior is a separable *cost* estimate.  It is
    # useful for Cheapest, but would bias Greenest/Balanced before their real
    # objective is evaluated, so those calls begin uninformatively.
    return qiea_solver.run_qiea(
        fleet,
        regulations,
        prices,
        **kwargs,
        mean_field_init=scorer.kind == "cost",
    )


def _serialized_plan(
    definition: str,
    result: solver.SolverResult,
    fleet: dict[str, Any],
    regulations: dict[str, Any],
    prices: dict[str, Any],
    fuel_model: FuelModel | None,
    *,
    emissions_cap_tco2e: float | None = None,
) -> dict[str, Any]:
    metrics = plan_metrics(result.best_genome, fleet, regulations, prices, fuel_model)
    if not metrics["annual_service"]["passed"] or not metrics["cargo"]["passed"]:
        raise ValueError(f"{definition} solver result violates a hard operational constraint")
    return {
        "id": definition.lower(),
        "definition": definition,
        "configuration": [asdict(gene) for gene in result.best_genome],
        "metrics": metrics,
        "emissions_cap_tco2e": emissions_cap_tco2e,
    }


def _change_summary(reference_genome, candidate_genome) -> dict[str, Any]:
    """A compact, serializable explanation of how a plan differs from Cheapest."""
    reference = {(gene.vessel_id, gene.year): gene for gene in reference_genome}
    changed_slots = 0
    changed_fields: dict[str, int] = {field: 0 for field in DECISION_FIELDS}
    examples: list[dict[str, Any]] = []
    for candidate in candidate_genome:
        baseline = reference[(candidate.vessel_id, candidate.year)]
        changed = {
            field: {"from": getattr(baseline, field), "to": getattr(candidate, field)}
            for field in DECISION_FIELDS
            if getattr(baseline, field) != getattr(candidate, field)
        }
        if not changed:
            continue
        changed_slots += 1
        for field in changed:
            changed_fields[field] += 1
        if len(examples) < 3:
            examples.append({"vessel_id": candidate.vessel_id, "year": candidate.year, "changes": changed})
    return {
        "changed_vessel_years": changed_slots,
        "changed_fields": {field: count for field, count in changed_fields.items() if count},
        "examples": examples,
    }


def build_comparable_alternatives(
    fleet: dict[str, Any],
    regulations: dict[str, Any],
    prices: dict[str, Any],
    *,
    fuel_model: FuelModel | None = None,
    optimizer: OptimizerName = "qiea",
    seed: int = 0,
    population_size: int = 40,
    n_generations: int = 30,
) -> dict[str, Any]:
    """Return Cheapest, Balanced and Greenest for one identical scenario.

    Balanced is not a weighted score.  Its emission cap is the midpoint of
    the achievable emissions interval between the independently solved
    Cheapest and Greenest plans, then it minimizes cost within that cap.
    Consequently the serialized cap is a concrete, inspectable decision
    rule rather than a hidden preference weight.
    """
    cheapest_result = _run(
        optimizer, fleet, regulations, prices, seed=seed, population_size=population_size,
        n_generations=n_generations, fuel_model=fuel_model, scorer=PlanScorer("cost"),
    )
    cheapest = _serialized_plan("Cheapest", cheapest_result, fleet, regulations, prices, fuel_model)

    greenest_result = _run(
        optimizer, fleet, regulations, prices, seed=seed + 1, population_size=population_size,
        n_generations=n_generations, fuel_model=fuel_model, scorer=PlanScorer("lifecycle_emissions"),
    )
    greenest = _serialized_plan("Greenest", greenest_result, fleet, regulations, prices, fuel_model)

    cheap_emissions = cheapest["metrics"]["lifecycle_emissions_tco2e"]
    green_emissions = greenest["metrics"]["lifecycle_emissions_tco2e"]
    if green_emissions > cheap_emissions + 1e-6:
        # Stochastic search has not found the known feasible cost plan.  Do
        # not label a worse result "Greenest"; use that proven candidate.
        greenest_result = cheapest_result
        greenest = _serialized_plan("Greenest", greenest_result, fleet, regulations, prices, fuel_model)
        green_emissions = cheap_emissions
    emissions_cap = cheap_emissions - BALANCED_EMISSIONS_GAP_FRACTION * (cheap_emissions - green_emissions)

    balanced_result = _run(
        optimizer, fleet, regulations, prices, seed=seed + 2, population_size=population_size,
        n_generations=n_generations, fuel_model=fuel_model,
        scorer=PlanScorer("cost_under_emissions_cap", emissions_cap),
        seed_genome=greenest_result.best_genome,
    )
    balanced = _serialized_plan(
        "Balanced", balanced_result, fleet, regulations, prices, fuel_model,
        emissions_cap_tco2e=emissions_cap,
    )
    if balanced["metrics"]["lifecycle_emissions_tco2e"] > emissions_cap + 1e-6:
        raise ValueError("Balanced solver result exceeds its declared lifecycle-emissions cap")

    cheapest["change_summary"] = _change_summary(cheapest_result.best_genome, cheapest_result.best_genome)
    balanced["change_summary"] = _change_summary(cheapest_result.best_genome, balanced_result.best_genome)
    greenest["change_summary"] = _change_summary(cheapest_result.best_genome, greenest_result.best_genome)

    return {
        "status": "SYNTHETIC_COMPARABLE_ALTERNATIVES",
        "optimizer": optimizer,
        "balanced_definition": (
            "Lowest-cost feasible plan whose lifecycle emissions are at or below the midpoint "
            "between the independently solved Cheapest and Greenest plans."
        ),
        "balanced_emissions_gap_fraction": BALANCED_EMISSIONS_GAP_FRACTION,
        "alternatives": [cheapest, balanced, greenest],
    }
