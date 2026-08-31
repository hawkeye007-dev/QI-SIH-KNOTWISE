"""Tests for the pluggable fuel-consumption model (Task 2R component 3).

Written before knotwise.optimization.fuel_model exists.
"""

import pytest

from knotwise.fleet.loader import load_fleet
from knotwise.optimization.fuel_model import PhysicsFuelModel


@pytest.fixture(scope="module")
def fleet():
    return load_fleet()


@pytest.fixture(scope="module")
def model():
    return PhysicsFuelModel()


def _band_a_vessel(fleet):
    return next(v for v in fleet["vessels"] if v["band"] == "A")


class TestDailyEnergyV3Law:
    def test_doubling_speed_gives_eight_times_daily_energy(self, model, fleet):
        vessel = _band_a_vessel(fleet)
        design_speed = fleet["vessel_class_defaults"]["A"]["design_speed_knots"]
        at_design = model.daily_energy_mj(vessel, fleet, design_speed)
        at_double = model.daily_energy_mj(vessel, fleet, design_speed * 2)
        assert at_double == pytest.approx(at_design * 8, rel=1e-9)

    def test_daily_energy_at_design_speed_equals_the_anchor(self, model, fleet):
        vessel = _band_a_vessel(fleet)
        design_speed = fleet["vessel_class_defaults"]["A"]["design_speed_knots"]
        anchor = fleet["vessel_class_defaults"]["A"]["anchor_daily_energy_mj_at_design_speed"]
        assert model.daily_energy_mj(vessel, fleet, design_speed) == pytest.approx(anchor)


class TestAnnualFuelConsumptionV2Law:
    def test_doubling_speed_gives_four_times_annual_energy_at_fixed_distance(self, model, fleet):
        vessel = _band_a_vessel(fleet)
        route_id = vessel["default_route"]
        design_speed = fleet["vessel_class_defaults"]["A"]["design_speed_knots"]
        low = model.annual_energy_mj(vessel, fleet, design_speed, route_id)
        high = model.annual_energy_mj(vessel, fleet, design_speed * 2, route_id)
        assert high == pytest.approx(low * 4, rel=1e-9)

    def test_monotonically_increasing_in_speed(self, model, fleet):
        vessel = _band_a_vessel(fleet)
        route_id = vessel["default_route"]
        speeds = [10, 14, 18, 22, 26]
        consumptions = [
            model.fuel_consumption_tonnes(vessel, fleet, 2028, s, "vlsfo", route_id) for s in speeds
        ]
        assert consumptions == sorted(consumptions)
        assert consumptions[0] < consumptions[-1]


class TestFuelIdAffectsMass:
    def test_lower_lcv_fuel_needs_more_mass_for_same_energy(self, model, fleet):
        vessel = _band_a_vessel(fleet)
        route_id = vessel["default_route"]
        speed = fleet["vessel_class_defaults"]["A"]["design_speed_knots"]
        vlsfo_tonnes = model.fuel_consumption_tonnes(vessel, fleet, 2028, speed, "vlsfo", route_id)
        methanol_tonnes = model.fuel_consumption_tonnes(vessel, fleet, 2028, speed, "methanol", route_id)
        # methanol's LCV (~19,900) is roughly half VLSFO's (~41,000) -> roughly double the mass
        assert methanol_tonnes > vlsfo_tonnes
        vlsfo_lcv = fleet["fuel_properties"]["fuels"]["vlsfo"]["lcv_mj_per_tonne"]
        methanol_lcv = fleet["fuel_properties"]["fuels"]["methanol"]["lcv_mj_per_tonne"]
        assert methanol_tonnes / vlsfo_tonnes == pytest.approx(vlsfo_lcv / methanol_lcv, rel=1e-9)

    def test_same_fuel_same_speed_same_route_gives_same_energy_regardless_of_fuel_choice(self, model, fleet):
        # The energy demand itself (before mass conversion) must not depend on fuel_id.
        vessel = _band_a_vessel(fleet)
        route_id = vessel["default_route"]
        speed = fleet["vessel_class_defaults"]["A"]["design_speed_knots"]
        energy = model.annual_energy_mj(vessel, fleet, speed, route_id)
        vlsfo_tonnes = model.fuel_consumption_tonnes(vessel, fleet, 2028, speed, "vlsfo", route_id)
        vlsfo_lcv = fleet["fuel_properties"]["fuels"]["vlsfo"]["lcv_mj_per_tonne"]
        assert vlsfo_tonnes * vlsfo_lcv == pytest.approx(energy, rel=1e-9)


class TestPerBandCalibration:
    def test_band_a_anchor_exceeds_band_b_exceeds_band_c(self, fleet):
        defaults = fleet["vessel_class_defaults"]
        a = defaults["A"]["anchor_daily_energy_mj_at_design_speed"]
        b = defaults["B"]["anchor_daily_energy_mj_at_design_speed"]
        c = defaults["C"]["anchor_daily_energy_mj_at_design_speed"]
        assert a > b > c
