"""Genome representation and feasibility-preserving operators."""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Any

from knotwise.fleet.model import option_menu_for
from knotwise.optimization.annual_service import annual_service_facts, route_demand_tonne_nm
from knotwise.optimization.constraints import feasible_speed_band_indices


@dataclass(frozen=True)
class VesselYearGene:
    vessel_id: str
    year: int
    route_id: str
    speed_band_index: int
    fuel_id: str
    shore_power: bool
    borrow_election: bool
    pool_opt_in: bool


Genome = list[VesselYearGene]

DECISION_FIELDS: tuple[str, ...] = (
    "route_id", "speed_band_index", "fuel_id", "shore_power", "pool_opt_in", "borrow_election",
)


def field_domains(vessel: dict[str, Any], fleet: dict[str, Any], year: int) -> dict[str, list[Any]]:
    """Legal per-field domains for QIEA/MPS registers.

    Route and speed are coupled by annual-service feasibility.  The separate
    registers therefore expose the union of route-valid speeds; observation is
    repaired through :func:`repair_capacity_coverage` before evaluation.
    """
    menu = option_menu_for(vessel, fleet, year)
    speed_domain = sorted({
        index for route_id in menu.routes for index in feasible_speed_band_indices(vessel, fleet, year, route_id)
    })
    if not speed_domain:
        raise ValueError(f"{vessel['vessel_id']} has no annual-service-feasible speed")
    return {
        "route_id": list(menu.routes),
        "speed_band_index": speed_domain,
        "fuel_id": list(menu.fuels),
        "shore_power": [False, True] if menu.shore_power_available else [False],
        "pool_opt_in": [False, True],
        "borrow_election": [False, True],
    }


def random_gene(vessel: dict[str, Any], fleet: dict[str, Any], year: int, rng: random.Random) -> VesselYearGene:
    """Sample one locally feasible annual vessel-route assignment."""
    menu = option_menu_for(vessel, fleet, year)
    route_id = rng.choice(menu.routes)
    speeds = feasible_speed_band_indices(vessel, fleet, year, route_id)
    if not speeds:
        raise ValueError(f"{vessel['vessel_id']} cannot serve {route_id} within annual availability")
    return VesselYearGene(
        vessel_id=vessel["vessel_id"],
        year=year,
        route_id=route_id,
        speed_band_index=rng.choice(speeds),
        fuel_id=rng.choice(menu.fuels),
        shore_power=menu.shore_power_available and rng.random() < 0.5,
        borrow_election=rng.random() < 0.5,
        pool_opt_in=rng.random() < 0.5,
    )


def _cargo_capacity(gene: VesselYearGene, vessel: dict[str, Any], fleet: dict[str, Any]) -> float:
    menu = option_menu_for(vessel, fleet, gene.year)
    speed = menu.speed_bands_knots[gene.speed_band_index]
    return annual_service_facts(vessel, fleet, gene.route_id, speed).annual_cargo_tonne_nm


def _repair_speed(gene: VesselYearGene, vessel: dict[str, Any], fleet: dict[str, Any]) -> VesselYearGene:
    speeds = feasible_speed_band_indices(vessel, fleet, gene.year, gene.route_id)
    if not speeds:
        raise ValueError(f"{gene.vessel_id} cannot serve {gene.route_id} within annual availability")
    return gene if gene.speed_band_index in speeds else replace(gene, speed_band_index=speeds[0])


def random_genome(fleet: dict[str, Any], rng: random.Random) -> Genome:
    return repair_capacity_coverage(
        [random_gene(vessel, fleet, year, rng) for vessel in fleet["vessels"] for year in fleet["horizon_years"]],
        fleet,
    )


def repair_capacity_coverage(genome: Genome, fleet: dict[str, Any]) -> Genome:
    """Repair annual-service and cargo-demand feasibility constructively.

    The historical function name is retained because callers already use it,
    but coverage now means cargo tonne-nautical-mile demand—not assigned DWT.
    A move only takes a donor from a route that stays served afterwards, and
    reselects a feasible speed if the new route needs one.
    """
    vessels_by_id = {vessel["vessel_id"]: vessel for vessel in fleet["vessels"]}
    repaired = [_repair_speed(gene, vessels_by_id[gene.vessel_id], fleet) for gene in genome]

    for year in fleet["horizon_years"]:
        indices_by_route: dict[str, list[int]] = defaultdict(list)
        assigned: dict[str, float] = defaultdict(float)
        for index, gene in enumerate(repaired):
            if gene.year == year:
                indices_by_route[gene.route_id].append(index)
                assigned[gene.route_id] += _cargo_capacity(gene, vessels_by_id[gene.vessel_id], fleet)

        for route_id, route in fleet["routes"].items():
            required = route_demand_tonne_nm(fleet, route_id)
            while assigned[route_id] < required:
                donor_index = next(
                    (
                        index
                        for source_route, indices in indices_by_route.items()
                        if source_route != route_id
                        for index in indices
                        if vessels_by_id[repaired[index].vessel_id]["band"] == route["band"]
                        and assigned[source_route] - _cargo_capacity(
                            repaired[index], vessels_by_id[repaired[index].vessel_id], fleet
                        ) >= route_demand_tonne_nm(fleet, source_route)
                    ),
                    None,
                )
                if donor_index is None:
                    shortfall = required - assigned[route_id]
                    raise ValueError(
                        f"fleet cannot meet {route_id} annual cargo demand in {year}: {shortfall:.0f} tonne-nm uncovered"
                    )

                donor = repaired[donor_index]
                vessel = vessels_by_id[donor.vessel_id]
                source_route = donor.route_id
                destination_speeds = feasible_speed_band_indices(vessel, fleet, donor.year, route_id)
                if not destination_speeds:
                    raise ValueError(f"{donor.vessel_id} cannot serve {route_id} within annual availability")
                moved = replace(
                    donor,
                    route_id=route_id,
                    speed_band_index=donor.speed_band_index if donor.speed_band_index in destination_speeds else destination_speeds[0],
                )
                assigned[source_route] -= _cargo_capacity(donor, vessel, fleet)
                assigned[route_id] += _cargo_capacity(moved, vessel, fleet)
                repaired[donor_index] = moved
                indices_by_route[source_route].remove(donor_index)
                indices_by_route[route_id].append(donor_index)

    return repaired


def mutate_genome(genome: Genome, fleet: dict[str, Any], rng: random.Random, n_mutations: int = 3) -> Genome:
    vessels_by_id = {vessel["vessel_id"]: vessel for vessel in fleet["vessels"]}
    mutated = list(genome)
    for _ in range(n_mutations):
        index = rng.randrange(len(mutated))
        gene = mutated[index]
        mutated[index] = random_gene(vessels_by_id[gene.vessel_id], fleet, gene.year, rng)
    return repair_capacity_coverage(mutated, fleet)


def crossover_genomes(
    parent_a: Genome, parent_b: Genome, rng: random.Random, fleet: dict[str, Any] | None = None
) -> tuple[Genome, Genome]:
    if len(parent_a) != len(parent_b):
        raise ValueError("genomes must have the same length to cross over")
    point = rng.randrange(1, len(parent_a))
    child_a = parent_a[:point] + parent_b[point:]
    child_b = parent_b[:point] + parent_a[point:]
    if fleet is None:
        return child_a, child_b
    return repair_capacity_coverage(child_a, fleet), repair_capacity_coverage(child_b, fleet)
