"""Tests for the carbon-price sweep + switching-point extraction (Task 2R component 4)."""

import json
import random
import time

import pytest

from knotwise.fleet.loader import load_fleet, load_prices
from knotwise.optimization.genome import VesselYearGene, random_genome
from knotwise.optimization.sweep import (
    DEFAULT_PRICE_GRID,
    GridPointResult,
    extract_switching_points,
    run_sweep,
    scenario_axis_positions,
    sweep_result_to_dict,
)


@pytest.fixture(scope="module")
def fleet():
    return load_fleet()


@pytest.fixture(scope="module")
def prices():
    return load_prices()


@pytest.fixture(scope="module")
def full_sweep(fleet, prices):
    """One full-default-grid sweep, shared across every test that needs it
    (item 5's timing/switching-point/warm-start checks) so the expensive run
    happens once rather than once per assertion."""
    start = time.perf_counter()
    result = run_sweep(fleet, prices, seed=0)
    elapsed = time.perf_counter() - start
    return result, elapsed


def _gene(vessel_id, year, **overrides):
    base = {
        "vessel_id": vessel_id,
        "year": year,
        "route_id": "india_gulf",
        "speed_band_index": 4,
        "fuel_id": "vlsfo",
        "shore_power": False,
        "borrow_election": False,
        "pool_opt_in": False,
    }
    base.update(overrides)
    return VesselYearGene(**base)


class TestExtractSwitchingPoints:
    def test_detects_a_changed_decision_field(self):
        genome_a = [_gene("A1", 2028, fuel_id="hfo_scrubber")]
        genome_b = [_gene("A1", 2028, fuel_id="b30_blend")]
        grid = [
            GridPointResult(0, genome_a, 100.0, 0.1, False, 10),
            GridPointResult(25, genome_b, 90.0, 0.05, True, 5),
        ]
        points = extract_switching_points(grid)
        assert len(points) == 1
        point = points[0]
        assert point.vessel_id == "A1"
        assert point.decision == "fuel_id"
        assert point.from_value == "hfo_scrubber"
        assert point.to_value == "b30_blend"
        assert point.price_low_usd_per_tco2e == 0
        assert point.price_high_usd_per_tco2e == 25

    def test_no_change_means_no_switching_point(self):
        genome = [_gene("A1", 2028)]
        grid = [
            GridPointResult(0, genome, 100.0, 0.1, False, 10),
            GridPointResult(25, list(genome), 100.0, 0.05, True, 5),
        ]
        assert extract_switching_points(grid) == []

    def test_band_c_vessel_years_are_excluded_only_when_fleet_is_given(self, fleet):
        c_vessel_id = next(v["vessel_id"] for v in fleet["vessels"] if v["band"] == "C")
        genome_a = [_gene(c_vessel_id, 2028, fuel_id="hfo_scrubber")]
        genome_b = [_gene(c_vessel_id, 2028, fuel_id="b30_blend")]
        grid = [
            GridPointResult(0, genome_a, 100.0, 0.1, False, 10),
            GridPointResult(25, genome_b, 90.0, 0.05, True, 5),
        ]
        assert extract_switching_points(grid, fleet=fleet) == []
        assert extract_switching_points(grid) != []  # no fleet given -> no band filter


@pytest.fixture(scope="module")
def scenario_positions(fleet, prices):
    representative = random_genome(fleet, random.Random(3))
    return scenario_axis_positions(fleet, prices, representative_genome=representative)


class TestScenarioAxisPositions:
    def test_covers_all_five_scenarios_plus_eu_ets_reference(self, scenario_positions):
        ids = {p.scenario_id for p in scenario_positions}
        assert ids == {"approved_text", "liberia", "tuvalu", "brazil", "adoption_fails", "eu_ets_reference"}

    def test_every_position_has_a_status_and_notes(self, scenario_positions):
        for position in scenario_positions:
            assert position.status
            assert position.notes

    def test_tier_annotated_ranges_carry_their_posted_tier_prices(self, scenario_positions):
        by_id = {p.scenario_id: p for p in scenario_positions}
        assert by_id["approved_text"].low_usd_per_tco2e == 100
        assert by_id["approved_text"].high_usd_per_tco2e == 380
        assert by_id["tuvalu"].low_usd_per_tco2e == 300
        assert by_id["tuvalu"].high_usd_per_tco2e is None  # PLAN.md gives no Tier 2 figure for Tuvalu

    def test_liberia_is_a_qualitative_marker_with_no_number(self, scenario_positions):
        liberia = next(p for p in scenario_positions if p.scenario_id == "liberia")
        assert liberia.kind == "qualitative_marker"
        assert liberia.low_usd_per_tco2e is None

    def test_adoption_fails_never_silently_assumes_zero(self, scenario_positions):
        # Task 2R component 4, item 1: scenario 5's axis position must come
        # from implied_price.py -- either a real computed number or an
        # explicit "undefined" (None), never a silently-assumed zero.
        adoption_fails = next(p for p in scenario_positions if p.scenario_id == "adoption_fails")
        assert adoption_fails.operating_point_usd_per_tco2e != 0.0

    def test_eu_ets_reference_matches_the_real_posted_price(self, scenario_positions, prices):
        eu_ets = next(p for p in scenario_positions if p.scenario_id == "eu_ets_reference")
        assert eu_ets.low_usd_per_tco2e == prices["carbon_allowances"]["eu_ets_eua"]["price_usd_per_tco2e"]


class TestRunSweep:
    def test_switching_points_exist_for_at_least_one_decision(self, full_sweep):
        # Non-degenerate fixture: the real fleet's own fuel prices/GHG
        # intensities produce a genuine hfo_scrubber/vlsfo/b30_blend cost
        # crossover within $0-600/tCO2e (verified by hand against
        # fleet.json's own numbers before writing this test). If this ever
        # finds zero switching points, that's a finding about the model's
        # economics worth reporting, not a reason to weaken the assertion.
        result, _ = full_sweep
        assert len(result.switching_points) >= 1

    def test_warm_start_is_not_slower_than_a_cold_solve(self, full_sweep):
        result, _ = full_sweep
        assert result.warm_start_benchmark.warm_seconds <= result.warm_start_benchmark.cold_seconds

    def test_default_grid_produces_one_point_per_price(self, full_sweep):
        result, _ = full_sweep
        assert len(result.grid_points) == len(DEFAULT_PRICE_GRID)
        assert [gp.price_usd_per_tco2e for gp in result.grid_points] == list(DEFAULT_PRICE_GRID)
        assert result.grid_points[0].warm_started is False
        assert all(gp.warm_started for gp in result.grid_points[1:])

    def test_reproducible_from_seed(self, fleet, prices):
        kwargs = {"seed": 2, "population_size": 16, "cold_generations": 15, "warm_generations": 6}
        price_grid = (0, 100, 200)
        result_a = run_sweep(fleet, prices, price_grid=price_grid, **kwargs)
        result_b = run_sweep(fleet, prices, price_grid=price_grid, **kwargs)
        assert [gp.genome for gp in result_a.grid_points] == [gp.genome for gp in result_b.grid_points]
        assert [gp.total_usd for gp in result_a.grid_points] == pytest.approx(
            [gp.total_usd for gp in result_b.grid_points]
        )

    def test_rejects_a_grid_with_fewer_than_two_points(self, fleet, prices):
        with pytest.raises(ValueError):
            run_sweep(fleet, prices, price_grid=(100,))


class TestSweepCompletesInDemoTime:
    """Task 2R component 4 item 5's own guide: "~5 x scenarios at 10s each"."""

    def test_default_grid_within_budget(self, full_sweep):
        _, elapsed = full_sweep
        assert elapsed < 60.0, f"sweep took {elapsed:.1f}s, over the ~50s guide budget"


class TestOutputSerialization:
    def test_sweep_result_to_dict_is_json_serializable_and_complete(self, fleet, prices):
        result = run_sweep(
            fleet,
            prices,
            seed=0,
            population_size=16,
            cold_generations=10,
            warm_generations=4,
            price_grid=(0, 100, 200),
        )
        payload = sweep_result_to_dict(result)
        json.dumps(payload)  # must not raise
        assert len(payload["grid_points"]) == 3
        assert payload["grid_points"][0]["configuration"]
        assert set(payload["grid_points"][0]["configuration"][0]) == {
            "vessel_id",
            "year",
            "route_id",
            "speed_band_index",
            "fuel_id",
            "shore_power",
            "pool_opt_in",
            "borrow_election",
        }
        assert len(payload["scenario_ticks"]) == 6
        assert payload["warm_start_benchmark"]["warm_seconds"] <= payload["warm_start_benchmark"]["cold_seconds"]
