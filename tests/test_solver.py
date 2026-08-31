"""Tests for the GA solver (Task 2R component 3, item 5)."""

import random
import time

import pytest

from knotwise.fleet.loader import load_fleet, load_prices
from knotwise.optimization.genome import random_genome
from knotwise.optimization.objective import evaluate
from knotwise.optimization.solver import run_ga
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
