"""Tests for the genome representation and operators (Task 2R component 3)."""

import random

import pytest

from knotwise.fleet.loader import load_fleet
from knotwise.fleet.model import option_menu_for
from knotwise.optimization.annual_service import annual_service_facts, route_demand_tonne_nm
from knotwise.optimization.constraints import MIN_SPEED_BAND_INDEX, feasible_speed_band_indices
from knotwise.optimization.genome import crossover_genomes, mutate_genome, random_genome


@pytest.fixture(scope="module")
def fleet():
    return load_fleet()


def _assert_gene_is_feasible(gene, fleet):
    vessel = next(v for v in fleet["vessels"] if v["vessel_id"] == gene.vessel_id)
    menu = option_menu_for(vessel, fleet, gene.year)
    assert gene.route_id in menu.routes
    assert gene.fuel_id in menu.fuels
    assert gene.speed_band_index in feasible_speed_band_indices(vessel, fleet, gene.year, gene.route_id)
    if gene.shore_power:
        assert menu.shore_power_available


def _assert_cargo_demand_is_met(genome, fleet):
    vessels = {v["vessel_id"]: v for v in fleet["vessels"]}
    for year in fleet["horizon_years"]:
        for route_id, route in fleet["routes"].items():
            assigned = sum(
                annual_service_facts(
                    vessels[g.vessel_id],
                    fleet,
                    route_id,
                    option_menu_for(vessels[g.vessel_id], fleet, g.year).speed_bands_knots[g.speed_band_index],
                ).annual_cargo_tonne_nm
                for g in genome
                if g.year == year and g.route_id == route_id
            )
            assert assigned >= route_demand_tonne_nm(fleet, route_id), (route_id, year, assigned)


def test_random_genome_has_one_gene_per_vessel_year(fleet):
    genome = random_genome(fleet, random.Random(0))
    assert len(genome) == len(fleet["vessels"]) * len(fleet["horizon_years"])


def test_random_genome_is_always_feasible(fleet):
    genome = random_genome(fleet, random.Random(1))
    for gene in genome:
        _assert_gene_is_feasible(gene, fleet)
    _assert_cargo_demand_is_met(genome, fleet)


def test_same_seed_gives_identical_genome(fleet):
    a = random_genome(fleet, random.Random(42))
    b = random_genome(fleet, random.Random(42))
    assert a == b


def test_mutation_stays_feasible(fleet):
    rng = random.Random(2)
    genome = random_genome(fleet, rng)
    mutated = mutate_genome(genome, fleet, rng, n_mutations=10)
    for gene in mutated:
        _assert_gene_is_feasible(gene, fleet)
    _assert_cargo_demand_is_met(mutated, fleet)


def test_crossover_children_stay_feasible(fleet):
    rng = random.Random(3)
    parent_a = random_genome(fleet, rng)
    parent_b = random_genome(fleet, rng)
    child_a, child_b = crossover_genomes(parent_a, parent_b, rng, fleet)
    for gene in child_a + child_b:
        _assert_gene_is_feasible(gene, fleet)
    _assert_cargo_demand_is_met(child_a, fleet)
    _assert_cargo_demand_is_met(child_b, fleet)


def test_crossover_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        crossover_genomes([], [1], random.Random(0))
