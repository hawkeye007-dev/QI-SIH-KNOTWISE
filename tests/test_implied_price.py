"""Unit tests for the implied-price converter (PLAN.md §3.6(b), §5 Phase 0)."""

import pytest

from knotwise.regulatory.implied_price import (
    ImpliedPrice,
    cii_implied_price,
    fueleu_compliance_balance_gco2eq,
    fueleu_implied_price,
    fueleu_penalty_eur,
)


class TestCiiImpliedPrice:
    def test_returns_implied_price_with_assumptions(self):
        result = cii_implied_price(
            corrective_action_cost_usd=1_000_000,
            co2e_shortfall_addressed_tonnes=5_000,
        )
        assert isinstance(result, ImpliedPrice)
        assert result.value_usd_per_tco2e == pytest.approx(200.0)
        assert "cost_capitalization_years" in result.assumptions
        assert "caveat" in result.assumptions

    def test_capitalization_years_reduces_annual_price(self):
        one_year = cii_implied_price(1_000_000, 5_000, cost_capitalization_years=1)
        five_years = cii_implied_price(1_000_000, 5_000, cost_capitalization_years=5)
        assert five_years.value_usd_per_tco2e == pytest.approx(one_year.value_usd_per_tco2e / 5)

    def test_rejects_nonpositive_shortfall(self):
        with pytest.raises(ValueError):
            cii_implied_price(1_000_000, 0)

    def test_rejects_nonpositive_capitalization_years(self):
        with pytest.raises(ValueError):
            cii_implied_price(1_000_000, 5_000, cost_capitalization_years=0)


class TestFueleuComplianceBalance:
    def test_deficit_is_negative(self):
        cb = fueleu_compliance_balance_gco2eq(
            ghg_intensity_target_gco2e_per_mj=89.0,
            ghg_intensity_actual_gco2e_per_mj=91.0,
            energy_used_mj=1_000_000,
        )
        assert cb < 0

    def test_surplus_is_positive(self):
        cb = fueleu_compliance_balance_gco2eq(
            ghg_intensity_target_gco2e_per_mj=91.0,
            ghg_intensity_actual_gco2e_per_mj=89.0,
            energy_used_mj=1_000_000,
        )
        assert cb > 0


class TestFueleuPenalty:
    def test_no_penalty_on_surplus(self):
        assert fueleu_penalty_eur(compliance_balance_gco2eq=100.0, ghg_intensity_actual_gco2e_per_mj=90.0) == 0.0

    def test_penalty_positive_on_deficit(self):
        penalty = fueleu_penalty_eur(
            compliance_balance_gco2eq=-1_000_000.0,
            ghg_intensity_actual_gco2e_per_mj=91.0,
        )
        assert penalty > 0

    def test_consecutive_period_multiplier_increases_penalty(self):
        one_period = fueleu_penalty_eur(-1_000_000.0, 91.0, n_consecutive_deficit_periods=1)
        three_periods = fueleu_penalty_eur(-1_000_000.0, 91.0, n_consecutive_deficit_periods=3)
        assert three_periods == pytest.approx(one_period * 1.2)  # 1 + (3-1)/10

    def test_rejects_nonpositive_ghg_intensity(self):
        with pytest.raises(ValueError):
            fueleu_penalty_eur(-1_000_000.0, 0.0)

    def test_rejects_zero_consecutive_periods(self):
        with pytest.raises(ValueError):
            fueleu_penalty_eur(-1_000_000.0, 91.0, n_consecutive_deficit_periods=0)


class TestFueleuImpliedPrice:
    def test_returns_implied_price_with_assumptions(self):
        result = fueleu_implied_price(
            compliance_balance_gco2eq=-1_000_000.0,
            ghg_intensity_actual_gco2e_per_mj=91.0,
        )
        assert isinstance(result, ImpliedPrice)
        assert result.value_usd_per_tco2e > 0
        assert "caveat" in result.assumptions

    def test_rejects_surplus(self):
        with pytest.raises(ValueError):
            fueleu_implied_price(
                compliance_balance_gco2eq=100.0,
                ghg_intensity_actual_gco2e_per_mj=91.0,
            )

    def test_rejects_nonpositive_fx_rate(self):
        with pytest.raises(ValueError):
            fueleu_implied_price(-1_000_000.0, 91.0, eur_to_usd_rate=0)

    def test_price_is_independent_of_deficit_magnitude(self):
        # Documented structural consequence (see implied_price.py docstring): the
        # deficit's size cancels out algebraically under the gCO2eq->tonnes
        # conversion used here.
        small = fueleu_implied_price(-1_000.0, 91.0)
        large = fueleu_implied_price(-10_000_000.0, 91.0)
        assert small.value_usd_per_tco2e == pytest.approx(large.value_usd_per_tco2e)

    def test_price_scales_with_fx_rate(self):
        base = fueleu_implied_price(-1_000_000.0, 91.0, eur_to_usd_rate=1.0)
        scaled = fueleu_implied_price(-1_000_000.0, 91.0, eur_to_usd_rate=1.1)
        assert scaled.value_usd_per_tco2e == pytest.approx(base.value_usd_per_tco2e * 1.1)
