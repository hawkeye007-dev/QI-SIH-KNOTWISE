"""Tests for the fleet model (Task 2R component 2)."""

import json
from importlib import resources

import jsonschema
import pytest

from knotwise.compliance.scope_gating import applicable_regimes
from knotwise.fleet.loader import load_fleet, load_prices
from knotwise.fleet.model import (
    option_menu_for,
    speed_bands_knots,
    vessel_spec,
    vessel_voyage_pattern,
)

# All four regimes are in force at this year for every regime that ever
# applies in this fleet's horizon (NZF's start_year is 2028 under the base
# "approved_text" regulations that these tests deliberately use).
_YEAR_ALL_REGIMES_IN_FORCE = 2028


def _load_schema(name: str) -> dict:
    return json.loads(resources.files("knotwise.fleet").joinpath(name).read_text())


@pytest.fixture(scope="module")
def fleet() -> dict:
    return load_fleet()


@pytest.fixture(scope="module")
def prices() -> dict:
    return load_prices()


def test_fleet_validates_against_schema(fleet):
    jsonschema.validate(instance=fleet, schema=_load_schema("fleet.schema.json"))


def test_prices_validates_against_schema(prices):
    jsonschema.validate(instance=prices, schema=_load_schema("prices.schema.json"))


def test_fleet_has_exactly_ten_vessels_in_the_right_bands(fleet):
    bands = [v["band"] for v in fleet["vessels"]]
    assert len(bands) == 10
    assert bands.count("A") == 4
    assert bands.count("B") == 3
    assert bands.count("C") == 3


class TestBandConsistencyWithScopeGating:
    """Component 2 must agree with component 1 (Task 2) — no vessel's band
    should imply a regime-applicability pattern scope_gating disagrees with."""

    def test_band_a_can_produce_fueleu_and_eu_ets(self, fleet):
        band_a_vessels = [v for v in fleet["vessels"] if v["band"] == "A"]
        results = [
            applicable_regimes(
                vessel_spec(v, fleet), vessel_voyage_pattern(v, fleet), year=_YEAR_ALL_REGIMES_IN_FORCE
            )
            for v in band_a_vessels
        ]
        assert any(r["fuel_eu"].applies for r in results)
        assert any(r["eu_ets"].applies for r in results)
        assert all(r["cii"].applies and r["nzf"].applies for r in results)

    def test_band_b_never_produces_fueleu_or_eu_ets(self, fleet):
        band_b_vessels = [v for v in fleet["vessels"] if v["band"] == "B"]
        for v in band_b_vessels:
            result = applicable_regimes(
                vessel_spec(v, fleet), vessel_voyage_pattern(v, fleet), year=_YEAR_ALL_REGIMES_IN_FORCE
            )
            assert result["cii"].applies is True
            assert result["nzf"].applies is True
            assert result["fuel_eu"].applies is False
            assert result["eu_ets"].applies is False

    def test_band_c_cannot_produce_any_applicable_regime(self, fleet):
        band_c_vessels = [v for v in fleet["vessels"] if v["band"] == "C"]
        for v in band_c_vessels:
            result = applicable_regimes(
                vessel_spec(v, fleet), vessel_voyage_pattern(v, fleet), year=_YEAR_ALL_REGIMES_IN_FORCE
            )
            assert all(not r.applies for r in result.values())


class TestOptionMenus:
    def test_every_vessel_every_year_has_a_non_empty_menu(self, fleet):
        for vessel in fleet["vessels"]:
            for year in fleet["horizon_years"]:
                menu = option_menu_for(vessel, fleet, year)
                assert menu.routes
                assert menu.speed_bands_knots
                assert menu.fuels

    def test_menu_has_eight_speed_bands(self, fleet):
        vessel = fleet["vessels"][0]
        menu = option_menu_for(vessel, fleet, fleet["horizon_years"][0])
        assert len(menu.speed_bands_knots) == 8

    def test_routes_in_menu_match_vessels_band(self, fleet):
        for vessel in fleet["vessels"]:
            menu = option_menu_for(vessel, fleet, fleet["horizon_years"][0])
            for route_id in menu.routes:
                assert fleet["routes"][route_id]["band"] == vessel["band"]

    def test_year_outside_horizon_raises(self, fleet):
        vessel = fleet["vessels"][0]
        with pytest.raises(ValueError):
            option_menu_for(vessel, fleet, 1999)


class TestCompatibilityMasking:
    def test_conventional_engine_never_offers_lng_or_methanol(self, fleet):
        for vessel in fleet["vessels"]:
            if vessel["engine_type"] == "conventional_hfo_scrubber":
                menu = option_menu_for(vessel, fleet, fleet["horizon_years"][0])
                assert "lng" not in menu.fuels
                assert "methanol" not in menu.fuels

    def test_dual_fuel_lng_never_offers_methanol_or_hfo_scrubber(self, fleet):
        for vessel in fleet["vessels"]:
            if vessel["engine_type"] == "dual_fuel_lng":
                menu = option_menu_for(vessel, fleet, fleet["horizon_years"][0])
                assert "methanol" not in menu.fuels
                assert "hfo_scrubber" not in menu.fuels
                assert "lng" in menu.fuels

    def test_dual_fuel_methanol_never_offers_lng_or_hfo_scrubber(self, fleet):
        for vessel in fleet["vessels"]:
            if vessel["engine_type"] == "dual_fuel_methanol":
                menu = option_menu_for(vessel, fleet, fleet["horizon_years"][0])
                assert "lng" not in menu.fuels
                assert "hfo_scrubber" not in menu.fuels
                assert "methanol" in menu.fuels

    def test_every_menu_fuel_has_a_price_entry(self, fleet, prices):
        known_fuels = set(prices["fuels"].keys())
        for vessel in fleet["vessels"]:
            menu = option_menu_for(vessel, fleet, fleet["horizon_years"][0])
            for fuel in menu.fuels:
                assert fuel in known_fuels, f"{fuel} has no prices.json entry"

    def test_every_menu_fuel_has_a_fuel_properties_entry(self, fleet):
        # Task 2R component 3 — fuel_model.py needs lcv_mj_per_tonne/ghg_intensity
        # for every fuel a vessel can actually be assigned.
        known_fuels = set(fleet["fuel_properties"]["fuels"].keys())
        for vessel in fleet["vessels"]:
            menu = option_menu_for(vessel, fleet, fleet["horizon_years"][0])
            for fuel in menu.fuels:
                assert fuel in known_fuels, f"{fuel} has no fleet.json fuel_properties entry"


class TestPhysicalAndEconomicData:
    """Task 2R component 3 additions — the data fuel_model.py/objective.py need."""

    def test_every_band_has_physics_and_economics_fields(self, fleet):
        for band, defaults in fleet["vessel_class_defaults"].items():
            assert defaults["anchor_daily_energy_mj_at_design_speed"] > 0, band
            assert defaults["fixed_opex_usd_per_year"] > 0, band
            assert defaults["charter_premium_usd_per_sea_day"] > 0, band

    def test_every_route_has_distance_and_demand_floor(self, fleet):
        for route_id, route in fleet["routes"].items():
            assert route["distance_nm"] > 0, route_id
            assert route["min_capacity_dwt_required"] > 0, route_id

    def test_fuel_properties_cover_all_six_canonical_fuels(self, fleet):
        expected = {"hfo_scrubber", "vlsfo", "mgo", "lng", "b30_blend", "methanol"}
        assert set(fleet["fuel_properties"]["fuels"].keys()) == expected
        for fuel_id, props in fleet["fuel_properties"]["fuels"].items():
            assert props["ghg_intensity_gco2e_per_mj"] > 0, fuel_id
            assert props["lcv_mj_per_tonne"] > 0, fuel_id

    def test_shore_power_model_present(self, fleet):
        model = fleet["shore_power_model"]
        assert 0 < model["berth_fuel_reduction_fraction"] <= 1
        assert model["cost_usd_per_vessel_year_when_elected"] > 0


def test_speed_bands_knots_scales_with_design_speed():
    slow_vessel_bands = speed_bands_knots(12)
    fast_vessel_bands = speed_bands_knots(22)
    assert len(slow_vessel_bands) == len(fast_vessel_bands) == 8
    assert max(slow_vessel_bands) == pytest.approx(12)
    assert max(fast_vessel_bands) == pytest.approx(22)
    assert min(slow_vessel_bands) == pytest.approx(12 * 0.05)
