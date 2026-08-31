"""Genome representation and operators (Task 2R component 3, item 3).

A flat list of per-(vessel, year) genes, each drawn only from that
vessel-year's own `option_menu_for` output (component 2) — structurally
infeasible values cannot be constructed, so mutation and crossover never
need a repair step (feasibility is closed under both operators: crossover
only ever recombines already-valid slot values, and mutation only ever
resamples a slot from its own valid menu).

DEAP-independent by design — these are plain functions over plain data, so
they're directly unit-testable without pulling in DEAP's machinery.
`solver.py` wraps them into a DEAP toolbox.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from knotwise.fleet.model import option_menu_for
from knotwise.optimization.constraints import allowed_speed_band_indices


@dataclass(frozen=True)
class VesselYearGene:
    vessel_id: str
    year: int
    route_id: str
    speed_band_index: int
    fuel_id: str
    shore_power: bool
    borrow_election: bool
    pool_opt_in: bool  # only meaningful for a vessel-year FuelEU actually applies to; harmless otherwise


Genome = list[VesselYearGene]


def random_gene(vessel: dict[str, Any], fleet: dict[str, Any], year: int, rng: random.Random) -> VesselYearGene:
    menu = option_menu_for(vessel, fleet, year)
    speed_index = rng.choice(list(allowed_speed_band_indices(len(menu.speed_bands_knots))))
    return VesselYearGene(
        vessel_id=vessel["vessel_id"],
        year=year,
        route_id=rng.choice(menu.routes),
        speed_band_index=speed_index,
        fuel_id=rng.choice(menu.fuels),
        shore_power=menu.shore_power_available and rng.random() < 0.5,
        borrow_election=rng.random() < 0.5,
        pool_opt_in=rng.random() < 0.5,
    )


def random_genome(fleet: dict[str, Any], rng: random.Random) -> Genome:
    genome: Genome = []
    for vessel in fleet["vessels"]:
        for year in fleet["horizon_years"]:
            genome.append(random_gene(vessel, fleet, year, rng))
    return genome


def mutate_genome(genome: Genome, fleet: dict[str, Any], rng: random.Random, n_mutations: int = 3) -> Genome:
    """Resample `n_mutations` random slots from their own valid menu — never an invalid value."""
    vessels_by_id = {v["vessel_id"]: v for v in fleet["vessels"]}
    mutated = list(genome)
    for _ in range(n_mutations):
        index = rng.randrange(len(mutated))
        gene = mutated[index]
        vessel = vessels_by_id[gene.vessel_id]
        mutated[index] = random_gene(vessel, fleet, gene.year, rng)
    return mutated


def crossover_genomes(parent_a: Genome, parent_b: Genome, rng: random.Random) -> tuple[Genome, Genome]:
    """Single-point crossover over the flat gene list.

    Safe without a repair step: each slot's value is independently valid
    regardless of its position (it was drawn from that same slot's own
    menu in one parent or the other), so any recombination is still feasible.
    """
    if len(parent_a) != len(parent_b):
        raise ValueError("genomes must have the same length to cross over")
    point = rng.randrange(1, len(parent_a))
    child_a = parent_a[:point] + parent_b[point:]
    child_b = parent_b[:point] + parent_a[point:]
    return child_a, child_b
