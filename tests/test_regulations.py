"""Schema validation and spot-checks for regulations.json and scenarios.json.

Covers D1's acceptance evidence (PLAN.md §5.5): "verify_regulations.py passes
against primary sources" is a later, fuller task (§8.6) — these tests check
structure and that the constants match what PLAN.md itself states, which is the
part of D1 buildable in Phase 0 without a live re-verification pass.
"""

import json
from importlib import resources

import jsonschema
import pytest


def _load(name: str) -> dict:
    return json.loads(resources.files("knotwise.regulatory").joinpath(name).read_text())


@pytest.fixture(scope="module")
def regulations() -> dict:
    return _load("regulations.json")


@pytest.fixture(scope="module")
def schema() -> dict:
    return _load("regulations.schema.json")


@pytest.fixture(scope="module")
def scenarios() -> dict:
    return _load("scenarios.json")


def test_regulations_validates_against_schema(regulations, schema):
    jsonschema.validate(instance=regulations, schema=schema)


def test_all_four_regimes_present(regulations):
    assert set(regulations["regimes"].keys()) == {"cii", "fuel_eu", "nzf", "eu_ets"}


def test_every_regime_has_provenance(regulations):
    for name, regime in regulations["regimes"].items():
        assert regime["source"]["citations"], f"{name} has no citations"
        assert regime["retrieval_date"], f"{name} has no retrieval_date"
        assert regime["status"], f"{name} has no status"


def test_cii_z_factors_match_plan(regulations):
    # PLAN.md §5 Phase 0 / MEPC.338(76) + MEPC.400(83)
    expected = {
        "2023": 5, "2024": 7, "2025": 9, "2026": 11,
        "2027": 13.625, "2028": 16.25, "2029": 18.875, "2030": 21.5,
    }
    assert regulations["regimes"]["cii"]["z_factors_percent"] == expected


def test_fueleu_baseline_matches_plan(regulations):
    assert regulations["regimes"]["fuel_eu"]["ghg_intensity_baseline_gco2e_per_mj"] == 91.16


def test_nzf_tier_prices_match_plan(regulations):
    tiers = regulations["regimes"]["nzf"]["tier_prices_usd_per_tco2e"]
    assert tiers["tier_1"] == 100
    assert tiers["tier_2"] == 380


def test_eu_ets_phase_in_matches_plan(regulations):
    phase_in = regulations["regimes"]["eu_ets"]["phase_in_by_surrender_year"]
    assert phase_in["2025"]["percent_of_emissions_surrendered"] == 40
    assert phase_in["2026"]["percent_of_emissions_surrendered"] == 70
    assert phase_in["2027"]["percent_of_emissions_surrendered"] == 100


def test_eua_spot_price_is_not_fabricated(regulations):
    # PLAN.md flags this as unverified/volatile — it must stay null, not a guessed number.
    assert regulations["regimes"]["eu_ets"]["eua_spot_price_usd_per_tco2e"] is None


def test_scenarios_has_five_entries_matching_plan_5_4(scenarios):
    assert scenarios["k"] == 5
    ids = {s["id"] for s in scenarios["scenarios"]}
    assert ids == {"approved_text", "liberia", "tuvalu", "brazil", "adoption_fails"}


def test_every_scenario_declares_a_price_axis_treatment(scenarios):
    allowed = {"tier_annotated_range", "qualitative_marker", "requires_implied_price_converter"}
    for s in scenarios["scenarios"]:
        assert s["price_axis_treatment"] in allowed
