"""Tests for per-regime compliance-cost formulas (Task 2R component 3).

Hand-computed fixtures throughout — every expected value is worked out from
the same formulas already documented in regulations.json / implied_price.py,
written out explicitly here rather than re-invoking the implementation.
"""

import pytest

from knotwise.compliance.scope_gating import RegimeApplicability
from knotwise.optimization.compliance_cost import (
    FuelEuYearInput,
    cii_cost,
    compute_fueleu_ledger,
    eu_ets_cost,
    fueleu_target_intensity,
    nzf_cost,
)

EUR_TO_USD = 1.1591  # same rate used for prices.json's carbon_allowances.eu_ets_eua

NZF_REGIME = {
    "reference_intensity_gco2e_per_mj": 93.3,
    "base_target_reduction_percent": {"2028": 4, "2029": 6, "2030": 8},
    "direct_compliance_target_reduction_percent": {"2028": 17, "2029": 19, "2030": 21},
    "tier_prices_usd_per_tco2e": {"tier_1": 100, "tier_2": 380},
    "surplus_unit_value_usd_per_tco2e": 100,
}

FUEL_EU_REGIME = {
    "ghg_intensity_baseline_gco2e_per_mj": 91.16,
    "reduction_schedule_percent": {"2025": 2, "2030": 6, "2035": 14.5, "2040": 31, "2045": 62, "2050": 80},
}

_APPLIES_FULL = RegimeApplicability(
    applies=True, voyage_share=1.0, phase_in_fraction=1.0, effective_obligation_fraction=1.0, notes=""
)
_NOT_APPLIES = RegimeApplicability(
    applies=False, voyage_share=0.0, phase_in_fraction=0.0, effective_obligation_fraction=0.0, notes=""
)


def test_fueleu_target_intensity_step_schedule():
    # 2026-2029 sit in the -2% block (target 89.34); 2030 steps to -6% (85.69)
    assert fueleu_target_intensity(FUEL_EU_REGIME, 2026) == pytest.approx(91.16 * 0.98)
    assert fueleu_target_intensity(FUEL_EU_REGIME, 2029) == pytest.approx(91.16 * 0.98)
    assert fueleu_target_intensity(FUEL_EU_REGIME, 2030) == pytest.approx(91.16 * 0.94)


class TestCiiCost:
    def test_cii_never_costs_anything(self):
        result = cii_cost(_APPLIES_FULL)
        assert result.amount_usd == 0.0
        assert result.status == "NOT_APPLICABLE_NO_DIRECT_PENALTY"


class TestEuEtsCost:
    def test_hand_computed_cost(self):
        # 91.16 gCO2e/MJ (vlsfo) x 1,000,000 MJ / 1e6 = 91.16 tonnes actually emitted;
        # x 0.5 voyage-share/phase-in x $97.6/t EUA = 4448.608
        applicability = RegimeApplicability(
            applies=True, voyage_share=0.5, phase_in_fraction=1.0, effective_obligation_fraction=0.5, notes=""
        )
        eua_price_entry = {"price_usd_per_tco2e": 97.6, "status": "PROXY"}
        result = eu_ets_cost(
            applicability,
            actual_ghg_intensity_gco2e_per_mj=91.16,
            energy_used_mj=1_000_000,
            eua_price_entry=eua_price_entry,
        )
        expected = 91.16 * 1_000_000 / 1e6 * 0.5 * 97.6
        assert result.amount_usd == pytest.approx(expected)
        assert result.status == "PROXY"

    def test_zero_when_not_applicable(self):
        eua_price_entry = {"price_usd_per_tco2e": 97.6, "status": "PROXY"}
        result = eu_ets_cost(_NOT_APPLIES, 91.16, 1_000_000, eua_price_entry)
        assert result.amount_usd == 0.0


_NZF_BASE_TARGET_2028 = 93.3 * (1 - 4 / 100)  # 89.568
_NZF_COMPLIANCE_TARGET_2028 = 93.3 * (1 - 17 / 100)  # 77.439


class TestNzfCost:
    def test_tier_1_only_deficit(self):
        # actual = 80 -> between compliance_target (77.439) and base_target (89.568)
        # -> gap_tier1 = 80 - 77.439, gap_tier2 = 0
        result = nzf_cost(NZF_REGIME, _APPLIES_FULL, year=2028, actual_ghg_intensity_gco2e_per_mj=80, energy_used_mj=1_000_000)
        gap_tier1 = 80 - _NZF_COMPLIANCE_TARGET_2028
        expected = gap_tier1 * 100
        assert result.amount_usd == pytest.approx(expected)
        assert result.status == "SECONDARY_SOURCE"

    def test_tier_1_and_tier_2_deficit(self):
        # actual = 95 -> worse than base_target (89.568)
        # gap_tier1 = base_target - compliance_target; gap_tier2 = actual - base_target
        result = nzf_cost(NZF_REGIME, _APPLIES_FULL, year=2028, actual_ghg_intensity_gco2e_per_mj=95, energy_used_mj=1_000_000)
        gap_tier1 = _NZF_BASE_TARGET_2028 - _NZF_COMPLIANCE_TARGET_2028
        gap_tier2 = 95 - _NZF_BASE_TARGET_2028
        expected = gap_tier1 * 100 + gap_tier2 * 380
        assert result.amount_usd == pytest.approx(expected)

    def test_surplus_earns_negative_cost(self):
        # actual = 70 -> better than compliance_target (77.439) -> gap_surplus = compliance_target - actual
        result = nzf_cost(NZF_REGIME, _APPLIES_FULL, year=2028, actual_ghg_intensity_gco2e_per_mj=70, energy_used_mj=1_000_000)
        gap_surplus = _NZF_COMPLIANCE_TARGET_2028 - 70
        expected = -(gap_surplus * 100)
        assert result.amount_usd == pytest.approx(expected)

    def test_not_applicable_when_regime_does_not_apply(self):
        result = nzf_cost(NZF_REGIME, _NOT_APPLIES, year=2028, actual_ghg_intensity_gco2e_per_mj=95, energy_used_mj=1_000_000)
        assert result.amount_usd == 0.0
        assert result.status == "NOT_APPLICABLE"

    def test_null_tier_prices_gives_zero_deficit_cost(self):
        regime = dict(NZF_REGIME, tier_prices_usd_per_tco2e=None)
        result = nzf_cost(regime, _APPLIES_FULL, year=2028, actual_ghg_intensity_gco2e_per_mj=95, energy_used_mj=1_000_000)
        assert result.amount_usd == 0.0

    def test_null_surplus_value_gives_zero_surplus_credit(self):
        regime = dict(NZF_REGIME, surplus_unit_value_usd_per_tco2e=None)
        result = nzf_cost(regime, _APPLIES_FULL, year=2028, actual_ghg_intensity_gco2e_per_mj=70, energy_used_mj=1_000_000)
        assert result.amount_usd == 0.0


class TestScenarioNzfDistinctness:
    """The concrete regression test for the degeneracy correction 3 was fixing.

    A deficit and a surplus fixture each exercise a different half of the
    degeneracy: deficit-side tier prices differ across approved/tuvalu/
    liberia/brazil; surplus-side value is what actually separates `liberia`
    from `adoption_fails` (both zero deficit cost, but only one values surplus).
    """

    def _cost(self, overrides: dict | None, *, actual: float, applies: bool = True):
        regime = dict(NZF_REGIME, **(overrides or {}))
        applicability = _APPLIES_FULL if applies else _NOT_APPLIES
        return nzf_cost(regime, applicability, year=2028, actual_ghg_intensity_gco2e_per_mj=actual, energy_used_mj=1_000_000)

    def test_liberia_differs_from_adoption_fails_in_a_surplus_scenario(self):
        # actual = 70 -> a surplus vessel. Liberia keeps surplus_unit_value_usd_per_tco2e
        # (untouched at 100) even though its deficit-side tier_prices is nulled;
        # adoption_fails disables NZF outright (applies=False). These must differ.
        liberia = self._cost({"tier_prices_usd_per_tco2e": None}, actual=70)
        adoption_fails = self._cost(None, actual=70, applies=False)
        assert liberia.amount_usd < 0  # a real credited value
        assert adoption_fails.amount_usd == 0.0
        assert liberia.amount_usd != adoption_fails.amount_usd

    def test_brazil_and_adoption_fails_both_zero_but_for_different_reasons(self):
        # Brazil: NZF applies, but both prices are null (deferred to the implied-price
        # converter). Adoption-fails: NZF disabled outright. Same number, different status/notes.
        brazil = self._cost({"tier_prices_usd_per_tco2e": None, "surplus_unit_value_usd_per_tco2e": None}, actual=95)
        adoption_fails = self._cost(None, actual=95, applies=False)
        assert brazil.amount_usd == adoption_fails.amount_usd == 0.0
        assert brazil.status != adoption_fails.status

    def test_approved_tuvalu_and_liberia_give_three_different_deficit_costs(self):
        approved = self._cost(None, actual=95)
        tuvalu = self._cost({"tier_prices_usd_per_tco2e": {"tier_1": 300, "tier_2": None}}, actual=95)
        liberia = self._cost({"tier_prices_usd_per_tco2e": None}, actual=95)
        values = {approved.amount_usd, tuvalu.amount_usd, liberia.amount_usd}
        assert len(values) == 3


_FUELEU_TARGET_2026_2029 = 91.16 * (1 - 2 / 100)  # 89.3368, the -2% step (2025-2029)


class TestFuelEuLedger:
    def test_surplus_banks_then_offsets_a_later_deficit(self):
        # Year 1 (2026): target 89.3368, actual 85 -> surplus, banks the balance
        # Year 2 (2027): target 89.3368, actual 95 -> raw deficit, offset by the
        #   Year-1 banked surplus -> a smaller remaining deficit
        target = _FUELEU_TARGET_2026_2029
        year1_surplus = (target - 85) * 1_000_000
        year2_raw_deficit = (95 - target) * 1_000_000

        year_inputs = [
            FuelEuYearInput(year=2026, actual_ghg_intensity_gco2e_per_mj=85, energy_used_mj=1_000_000),
            FuelEuYearInput(year=2027, actual_ghg_intensity_gco2e_per_mj=95, energy_used_mj=1_000_000),
        ]
        results = compute_fueleu_ledger(FUEL_EU_REGIME, year_inputs, eur_to_usd_rate=EUR_TO_USD)

        assert results[0].raw_balance_gco2eq == pytest.approx(year1_surplus)
        assert results[0].banked_surplus_after_gco2eq == pytest.approx(year1_surplus)
        assert results[0].cost.amount_usd == 0.0

        remaining_deficit = year2_raw_deficit - year1_surplus
        expected_penalty_eur = remaining_deficit / (95 * 41000) * 2400
        assert results[1].banked_surplus_after_gco2eq == pytest.approx(0.0, abs=1e-6)
        assert results[1].cost.amount_usd == pytest.approx(expected_penalty_eur * EUR_TO_USD, rel=1e-6)

    def test_borrow_then_forced_no_consecutive_borrow(self):
        # Year 1 (2026): deficit = (91 - target) * energy; cap = 2% * target * energy
        #   -> deficit <= cap here -> fully borrowed, no cost this year, repayment due
        #   next year = borrowed_amount * 1.1
        # Year 2 (2027): the same raw deficit recurs, PLUS the Year-1 repayment now
        #   due -> a larger effective deficit; borrow_election is True again but
        #   borrowing is forced off (borrowed last period) -> the full effective
        #   deficit is penalised, none of it borrowed away
        target = _FUELEU_TARGET_2026_2029
        energy = 1_000_000
        year1_deficit = (91 - target) * energy
        cap = 0.02 * target * energy
        assert year1_deficit <= cap, "fixture assumption: fully borrowable in year 1"
        repayment_due = year1_deficit * 1.1

        year_inputs = [
            FuelEuYearInput(year=2026, actual_ghg_intensity_gco2e_per_mj=91, energy_used_mj=energy, borrow_election=True),
            FuelEuYearInput(year=2027, actual_ghg_intensity_gco2e_per_mj=91, energy_used_mj=energy, borrow_election=True),
        ]
        results = compute_fueleu_ledger(FUEL_EU_REGIME, year_inputs, eur_to_usd_rate=EUR_TO_USD)

        assert results[0].borrowed is True
        assert results[0].cost.amount_usd == pytest.approx(0.0, abs=1e-6)

        assert results[1].borrowed is False  # forced off — consecutive borrowing not permitted
        effective_deficit = year1_deficit + repayment_due
        expected_penalty_eur = effective_deficit / (91 * 41000) * 2400
        assert results[1].cost.amount_usd == pytest.approx(expected_penalty_eur * EUR_TO_USD, rel=1e-6)

    def test_pooled_year_is_skipped_by_the_individual_ledger(self):
        year_inputs = [
            FuelEuYearInput(year=2026, actual_ghg_intensity_gco2e_per_mj=95, energy_used_mj=1_000_000, pooled=True),
        ]
        results = compute_fueleu_ledger(FUEL_EU_REGIME, year_inputs, eur_to_usd_rate=EUR_TO_USD)
        assert results[0].cost.amount_usd == 0.0
        assert results[0].cost.status == "NOT_APPLICABLE"
