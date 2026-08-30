"""Tests for the scenario-override merge mechanism (Task 2R component 2).

Proves scenarios.json's `regulatory_overrides` resolve correctly and that the
result feeds straight into scope_gating.applicable_regimes with zero
scenario-aware branching anywhere in Python.
"""

import pytest

from knotwise.compliance.scope_gating import VesselSpec, VoyagePattern, applicable_regimes
from knotwise.regulatory.loader import load_regulations
from knotwise.regulatory.scenario_resolution import resolve_regulations_for_scenario

# A vessel/voyage that would qualify for NZF under the base (approved) rules,
# used throughout to isolate "does NZF apply" to the scenario override alone.
_QUALIFYING_VESSEL = VesselSpec(gross_tonnage=55_000)
_QUALIFYING_VOYAGE = VoyagePattern(is_international=True)


def test_approved_text_matches_base_regulations():
    resolved = resolve_regulations_for_scenario("approved_text")
    base = load_regulations()
    assert resolved == base


def test_brazil_pushes_nzf_start_year_to_2029():
    resolved = resolve_regulations_for_scenario("brazil")
    nzf = resolved["regimes"]["nzf"]
    assert nzf["start_year"] == 2029
    assert nzf["tier_prices_usd_per_tco2e"] is None
    assert nzf["reduction_target_percent"] == {"2029": 3, "2030": 4}


def test_adoption_fails_disables_nzf():
    resolved = resolve_regulations_for_scenario("adoption_fails")
    assert resolved["regimes"]["nzf"]["enabled"] is False


def test_liberia_clears_tier_prices():
    resolved = resolve_regulations_for_scenario("liberia")
    assert resolved["regimes"]["nzf"]["tier_prices_usd_per_tco2e"] is None


def test_tuvalu_overrides_tier_one_only():
    resolved = resolve_regulations_for_scenario("tuvalu")
    tiers = resolved["regimes"]["nzf"]["tier_prices_usd_per_tco2e"]
    # Deep-merge, not wholesale replace: tier_1/tier_2 come from the override,
    # applicable_years is untouched because Tuvalu's proposal doesn't restate it.
    assert tiers["tier_1"] == 300
    assert tiers["tier_2"] is None
    assert tiers["applicable_years"] == [2028, 2029, 2030]


@pytest.mark.parametrize("scenario_id", ["approved_text", "liberia", "tuvalu", "brazil", "adoption_fails"])
def test_non_overridden_regimes_are_untouched(scenario_id):
    # None of the five scenarios override anything outside `nzf` — cii and
    # eu_ets must come through byte-for-byte identical to the base.
    resolved = resolve_regulations_for_scenario(scenario_id)
    base = load_regulations()
    assert resolved["regimes"]["cii"] == base["regimes"]["cii"]
    assert resolved["regimes"]["eu_ets"] == base["regimes"]["eu_ets"]
    assert resolved["regimes"]["fuel_eu"] == base["regimes"]["fuel_eu"]


def test_unknown_scenario_id_raises():
    with pytest.raises(ValueError):
        resolve_regulations_for_scenario("not-a-real-scenario")


def test_resolving_does_not_mutate_the_cached_base_regulations():
    resolve_regulations_for_scenario("adoption_fails")
    # load_regulations() is lru_cache'd — a real bug here would leak across scenarios.
    assert load_regulations()["regimes"]["nzf"]["enabled"] is True


class TestEndToEndWithScopeGating:
    """The point of this whole mechanism: component 3 (and anything else) reads
    a resolved view and passes it straight to applicable_regimes — no branch."""

    def test_nzf_applies_under_approved_text(self):
        resolved = resolve_regulations_for_scenario("approved_text")
        result = applicable_regimes(_QUALIFYING_VESSEL, _QUALIFYING_VOYAGE, year=2029, regulations=resolved)
        assert result["nzf"].applies is True

    def test_nzf_does_not_apply_under_adoption_fails(self):
        resolved = resolve_regulations_for_scenario("adoption_fails")
        result = applicable_regimes(_QUALIFYING_VESSEL, _QUALIFYING_VOYAGE, year=2029, regulations=resolved)
        assert result["nzf"].applies is False

    def test_nzf_start_year_shifts_under_brazil(self):
        resolved = resolve_regulations_for_scenario("brazil")
        result_2028 = applicable_regimes(_QUALIFYING_VESSEL, _QUALIFYING_VOYAGE, year=2028, regulations=resolved)
        result_2029 = applicable_regimes(_QUALIFYING_VESSEL, _QUALIFYING_VOYAGE, year=2029, regulations=resolved)
        assert result_2028["nzf"].applies is False  # approved text would have said True at 2028
        assert result_2029["nzf"].applies is True
