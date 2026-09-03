"""Tests for the synthetic fuel-consumption telemetry generator (PS
Objective 1 / experiment B1's data substitute — see synthetic_telemetry.py's
module docstring for why the ground truth is synthetic)."""

from __future__ import annotations

import statistics

import pytest

from knotwise.fleet.loader import load_fleet
from knotwise.fleet.model import speed_bands_knots
from knotwise.optimization.constraints import MIN_SPEED_BAND_INDEX
from knotwise.optimization.fuel_model import PhysicsFuelModel
from knotwise.optimization.synthetic_telemetry import generate_telemetry, leave_one_vessel_out_folds


@pytest.fixture(scope="module")
def fleet():
    return load_fleet()


@pytest.fixture(scope="module")
def table(fleet):
    return generate_telemetry(fleet, samples_per_vessel_year=30, seed=0)


class TestDeterminism:
    def test_same_seed_gives_identical_output(self, fleet):
        a = generate_telemetry(fleet, samples_per_vessel_year=10, seed=7)
        b = generate_telemetry(fleet, samples_per_vessel_year=10, seed=7)
        assert a == b

    def test_different_seed_gives_different_output(self, fleet):
        a = generate_telemetry(fleet, samples_per_vessel_year=10, seed=7)
        b = generate_telemetry(fleet, samples_per_vessel_year=10, seed=8)
        assert a != b


class TestSampleCount:
    def test_matches_vessels_times_years_times_samples_per_vessel_year(self, fleet):
        table = generate_telemetry(fleet, samples_per_vessel_year=5, seed=0)
        expected = len(fleet["vessels"]) * len(fleet["horizon_years"]) * 5
        assert len(table) == expected


class TestPhysicsGroundTruthMatchesPhysicsFuelModel:
    def test_every_sample_physics_tonnes_matches_direct_call(self, table, fleet):
        physics = PhysicsFuelModel()
        vessels_by_id = {v["vessel_id"]: v for v in fleet["vessels"]}
        for sample in table:
            vessel = vessels_by_id[sample.vessel_id]
            expected = physics.fuel_consumption_tonnes(
                vessel, fleet, sample.year, sample.speed_knots, sample.fuel_id, sample.route_id
            )
            assert sample.physics_tonnes == pytest.approx(expected, rel=1e-9)


class TestSampledFieldsAreFeasible:
    def test_route_matches_vessel_band(self, table, fleet):
        for sample in table:
            assert fleet["routes"][sample.route_id]["band"] == sample.band

    def test_fuel_is_engine_compatible(self, table, fleet):
        vessels_by_id = {v["vessel_id"]: v for v in fleet["vessels"]}
        for sample in table:
            vessel = vessels_by_id[sample.vessel_id]
            compatible = fleet["engine_fuel_compatibility"]["matrix"][vessel["engine_type"]]
            assert sample.fuel_id in compatible

    def test_speed_within_the_solver_reachable_range(self, table, fleet):
        # Same lower bound the solver itself is restricted to
        # (constraints.MIN_SPEED_BAND_INDEX), through full design speed.
        for sample in table:
            design_speed = fleet["vessel_class_defaults"][sample.band]["design_speed_knots"]
            bands = speed_bands_knots(design_speed)
            lo, hi = bands[MIN_SPEED_BAND_INDEX], bands[-1]
            assert lo - 1e-6 <= sample.speed_knots <= hi + 1e-6

    def test_hull_fouling_age_and_sea_state_are_bounded(self, table):
        for sample in table:
            assert 0.0 <= sample.hull_fouling_age_days <= 730.0
            assert 0.0 <= sample.sea_state_index <= 1.0


class TestResidualIsBoundedAndStructured:
    def test_actual_tonnes_stays_positive_and_close_to_physics(self, table):
        # The documented residual terms (max +8% fouling, +-5% sea state
        # amplified up to 1.5x, +-2% noise std) bound the total swing well
        # inside +-20% -- if this ever fires, the residual model changed in
        # a way that could produce a non-physical (e.g. negative) fuel figure.
        for sample in table:
            ratio = sample.actual_tonnes / sample.physics_tonnes
            assert 0.7 <= ratio <= 1.3

    def test_band_a_has_higher_mean_residual_than_band_c(self, table):
        # Band A's mean synthetic fouling age is set higher than Band C's
        # (module docstring) -- a real, directional, statistically safe
        # assertion given thousands of samples per band at a fixed seed.
        by_band: dict[str, list[float]] = {}
        for sample in table:
            residual = (sample.actual_tonnes - sample.physics_tonnes) / sample.physics_tonnes
            by_band.setdefault(sample.band, []).append(residual)
        mean_a = statistics.mean(by_band["A"])
        mean_c = statistics.mean(by_band["C"])
        assert mean_a > mean_c


class TestLeaveOneVesselOutFolds:
    def test_one_fold_per_vessel(self, table, fleet):
        folds = leave_one_vessel_out_folds(table)
        assert len(folds) == len(fleet["vessels"])

    def test_every_fold_partitions_the_table_by_vessel(self, table, fleet):
        folds = leave_one_vessel_out_folds(table)
        for held_out_vessel_id, train, test in folds:
            assert all(s.vessel_id == held_out_vessel_id for s in test)
            assert all(s.vessel_id != held_out_vessel_id for s in train)
            assert len(train) + len(test) == len(table)

    def test_held_out_vessel_ids_cover_every_vessel_exactly_once(self, table, fleet):
        folds = leave_one_vessel_out_folds(table)
        held_out_ids = {held_out_vessel_id for held_out_vessel_id, _, _ in folds}
        assert held_out_ids == {v["vessel_id"] for v in fleet["vessels"]}
