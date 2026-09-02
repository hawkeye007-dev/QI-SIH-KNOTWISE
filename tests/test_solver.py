"""Tests for the GA solver (Task 2R component 3, item 5)."""

import random
import time
from dataclasses import replace

import pytest

from knotwise.fleet.loader import load_fleet, load_prices
from knotwise.fleet.model import option_menu_for
from knotwise.optimization.genome import random_genome
from knotwise.optimization.objective import evaluate
from knotwise.optimization.solver import _local_search_refine, run_ga
from knotwise.regulatory.loader import load_scenarios
from knotwise.regulatory.scenario_resolution import resolve_regulations_for_scenario


@pytest.fixture(scope="module")
def fleet():
    return load_fleet()


@pytest.fixture(scope="module")
def prices():
    return load_prices()


@pytest.fixture(scope="module")
def regulations():
    return resolve_regulations_for_scenario("approved_text")


class TestReproducibility:
    def test_same_seed_gives_identical_result(self, fleet, regulations, prices):
        kwargs = {"population_size": 12, "n_generations": 5}
        result_a = run_ga(fleet, regulations, prices, seed=11, **kwargs)
        result_b = run_ga(fleet, regulations, prices, seed=11, **kwargs)
        assert result_a.best_genome == result_b.best_genome
        assert result_a.best_total_usd == pytest.approx(result_b.best_total_usd)

    def test_different_seeds_can_diverge(self, fleet, regulations, prices):
        # Not a strict correctness requirement — this guards against a solver
        # that's secretly ignoring `seed` (e.g. a global-RNG leak), which
        # `test_same_seed_gives_identical_result` alone couldn't catch.
        kwargs = {"population_size": 12, "n_generations": 5}
        result_a = run_ga(fleet, regulations, prices, seed=1, **kwargs)
        result_b = run_ga(fleet, regulations, prices, seed=2, **kwargs)
        assert result_a.best_genome != result_b.best_genome


class TestResultIntegrity:
    def test_best_breakdown_matches_reevaluating_best_genome(self, fleet, regulations, prices):
        result = run_ga(fleet, regulations, prices, seed=5, population_size=10, n_generations=4)
        reevaluated = evaluate(result.best_genome, fleet, regulations, prices)
        assert result.best_total_usd == pytest.approx(reevaluated.total_usd)
        assert result.best_breakdown.total_usd == pytest.approx(reevaluated.total_usd)

    def test_best_genome_has_one_gene_per_vessel_year(self, fleet, regulations, prices):
        result = run_ga(fleet, regulations, prices, seed=5, population_size=10, n_generations=4)
        assert len(result.best_genome) == len(fleet["vessels"]) * len(fleet["horizon_years"])


class TestSearchQuality:
    def test_ga_beats_the_mean_of_random_genomes(self, fleet, regulations, prices):
        # Sanity check that the GA is actually searching rather than just
        # returning an arbitrary genome: its best-found cost should beat the
        # average of several independent random genomes by a real margin.
        rng = random.Random(99)
        random_totals = [
            evaluate(random_genome(fleet, rng), fleet, regulations, prices).total_usd for _ in range(8)
        ]
        mean_random_total = sum(random_totals) / len(random_totals)

        result = run_ga(fleet, regulations, prices, seed=99, population_size=30, n_generations=20)
        assert result.best_total_usd < mean_random_total


class TestLocalSearchRefine:
    """Task 2R review follow-up: a bounded GA can leave individual
    vessel-year slots at a locally suboptimal value even when the
    population looks converged -- verified on this fleet as year-over-year
    fuel trajectories that get *dirtier* with no cost benefit. This is the
    coordinate-descent polish that closes exactly that gap."""

    def test_fixes_a_deliberately_suboptimal_slot(self, fleet, regulations, prices):
        rng = random.Random(3)
        genome = random_genome(fleet, rng)

        # Force one vessel-year onto its single most expensive fuel option
        # -- an obviously locally-suboptimal slot the refiner should be
        # able to fix without any GA search at all.
        vessel = fleet["vessels"][0]
        target_year = fleet["horizon_years"][0]
        menu = option_menu_for(vessel, fleet, target_year)
        index = next(
            i for i, g in enumerate(genome) if g.vessel_id == vessel["vessel_id"] and g.year == target_year
        )
        worst_fuel = max(menu.fuels, key=lambda f: prices["fuels"][f]["price_usd_per_tonne"])
        genome[index] = replace(genome[index], fuel_id=worst_fuel)
        degraded_total = evaluate(genome, fleet, regulations, prices).total_usd

        refined_genome, refined_total = _local_search_refine(genome, fleet, regulations, prices, random.Random(0))
        assert refined_total <= degraded_total
        assert refined_total == pytest.approx(evaluate(refined_genome, fleet, regulations, prices).total_usd)

    def test_never_returns_a_higher_cost_than_the_input(self, fleet, regulations, prices):
        rng = random.Random(4)
        genome = random_genome(fleet, rng)
        input_total = evaluate(genome, fleet, regulations, prices).total_usd
        _, refined_total = _local_search_refine(genome, fleet, regulations, prices, random.Random(1))
        assert refined_total <= input_total + 1e-6

    def test_every_candidate_stays_within_its_own_menu(self, fleet, regulations, prices):
        # Feasibility-closure is what lets the refiner skip a repair step
        # (see genome.py's own docstring on the same guarantee for
        # crossover/mutation) -- confirm it actually holds here too.
        rng = random.Random(6)
        genome = random_genome(fleet, rng)
        refined_genome, _ = _local_search_refine(genome, fleet, regulations, prices, random.Random(2))
        vessels_by_id = {v["vessel_id"]: v for v in fleet["vessels"]}
        for gene in refined_genome:
            menu = option_menu_for(vessels_by_id[gene.vessel_id], fleet, gene.year)
            assert gene.fuel_id in menu.fuels
            assert gene.route_id in menu.routes
            assert gene.speed_band_index in range(len(menu.speed_bands_knots))
            assert menu.shore_power_available or not gene.shore_power


class TestFiveScenariosUnderSixtySeconds:
    """PLAN.md §6.1's target ("[TARGET: sub-60s for N=24 at demo settings]")
    applied as a sanity check on this component's own fleet, across every
    regulatory scenario in scenarios.json's K=5 leg — the solver must stay
    usable for every one of the live regulatory outcomes, not just the base
    case."""

    def test_each_scenario_solves_within_budget(self, fleet, prices):
        scenario_ids = [s["id"] for s in load_scenarios()["scenarios"]]
        assert len(scenario_ids) == 5

        for scenario_id in scenario_ids:
            scenario_regulations = resolve_regulations_for_scenario(scenario_id)
            start = time.perf_counter()
            result = run_ga(
                fleet, scenario_regulations, prices, seed=7, population_size=40, n_generations=30
            )
            elapsed = time.perf_counter() - start
            assert elapsed < 60.0, f"{scenario_id} took {elapsed:.1f}s, over the 60s budget"
            assert result.best_total_usd > 0
