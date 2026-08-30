"""Tests for the scope-gating engine (Task 2; PLAN.md §3.4, §5.4, Phase 4).

Written before knotwise.compliance.scope_gating exists — see that module for
the implementation these tests drive.
"""

import pytest

from knotwise.compliance.scope_gating import VesselSpec, VoyagePattern, applicable_regimes

ALL_REGIMES = {"cii", "nzf", "fuel_eu", "eu_ets"}


def test_coastal_feeder_excluded_from_all_four_regimes():
    vessel = VesselSpec(gross_tonnage=3000)
    voyage = VoyagePattern(is_international=False)

    result = applicable_regimes(vessel, voyage, year=2027)

    assert set(result.keys()) == ALL_REGIMES
    for regime, applicability in result.items():
        assert applicability.applies is False, f"{regime} should not apply to a coastal feeder"


def test_band_a_vessel_owes_fueleu_and_eu_ets_as_separate_stacking_obligations():
    # 10 deep-sea >=5000 GT, India-EU liner (PLAN.md §5.4 Band A): 50% on the
    # India-EU legs (third-country voyage weight), 100% at EU berth.
    vessel = VesselSpec(gross_tonnage=55_000)
    voyage = VoyagePattern(
        is_international=True,
        eu_eea_third_country_voyage_fraction=0.9,
        eu_eea_berth_fraction=0.1,
    )

    result = applicable_regimes(vessel, voyage, year=2028)

    assert result["cii"].applies is True
    assert result["nzf"].applies is True
    assert result["fuel_eu"].applies is True
    assert result["eu_ets"].applies is True
    # Separate instruments: each carries its own obligation fraction, never netted
    # against the other, even though both read the same voyage-share formula.
    assert result["fuel_eu"].effective_obligation_fraction == pytest.approx(0.9 * 0.5 + 0.1 * 1.0)
    assert result["eu_ets"].effective_obligation_fraction == pytest.approx(0.9 * 0.5 + 0.1 * 1.0)


def test_band_b_vessel_owes_only_cii_and_nzf():
    # 6 deep-sea >=5000 GT, India-Gulf / Southeast Asia (PLAN.md §5.4 Band B):
    # no EU/EEA port calls at all.
    vessel = VesselSpec(gross_tonnage=25_000)
    voyage = VoyagePattern(is_international=True)

    result = applicable_regimes(vessel, voyage, year=2028)

    assert result["cii"].applies is True
    assert result["nzf"].applies is True
    assert result["fuel_eu"].applies is False
    assert result["eu_ets"].applies is False


class TestGtThresholdBoundary:
    def test_5000_gt_exactly_meets_the_threshold(self):
        vessel = VesselSpec(gross_tonnage=5000)
        voyage = VoyagePattern(is_international=True)

        result = applicable_regimes(vessel, voyage, year=2028)

        assert result["cii"].applies is True
        assert result["nzf"].applies is True

    def test_just_under_5000_gt_does_not_meet_the_threshold(self):
        vessel = VesselSpec(gross_tonnage=4999.999)
        voyage = VoyagePattern(is_international=True)

        result = applicable_regimes(vessel, voyage, year=2028)

        assert result["cii"].applies is False
        assert result["nzf"].applies is False


class TestEuEtsPhaseIn:
    _vessel = VesselSpec(gross_tonnage=55_000)
    _voyage = VoyagePattern(
        is_international=True,
        eu_eea_third_country_voyage_fraction=0.9,
        eu_eea_berth_fraction=0.1,
    )

    @pytest.mark.parametrize(
        ("emissions_year", "expected_phase_in_fraction"),
        [(2024, 0.40), (2025, 0.70), (2026, 1.00), (2030, 1.00)],  # 2030 via the "2026 onward" fallback
    )
    def test_phase_in_fraction_by_emissions_year(self, emissions_year, expected_phase_in_fraction):
        result = applicable_regimes(self._vessel, self._voyage, year=emissions_year)
        assert result["eu_ets"].phase_in_fraction == pytest.approx(expected_phase_in_fraction)

    def test_voyage_share_is_constant_across_phase_in_years(self):
        shares = {
            year: applicable_regimes(self._vessel, self._voyage, year=year)["eu_ets"].voyage_share
            for year in (2024, 2025, 2026, 2030)
        }
        assert len(set(shares.values())) == 1

    def test_effective_obligation_fraction_scales_with_phase_in(self):
        r2024 = applicable_regimes(self._vessel, self._voyage, year=2024)["eu_ets"]
        r2027 = applicable_regimes(self._vessel, self._voyage, year=2027)["eu_ets"]
        assert r2027.effective_obligation_fraction > r2024.effective_obligation_fraction
        assert r2027.effective_obligation_fraction == pytest.approx(
            r2024.effective_obligation_fraction * (1.00 / 0.40)
        )


class TestNzfStartYear:
    def test_nzf_does_not_apply_before_2028(self):
        vessel = VesselSpec(gross_tonnage=55_000)
        voyage = VoyagePattern(is_international=True)

        result = applicable_regimes(vessel, voyage, year=2027)

        assert result["nzf"].applies is False

    def test_nzf_applies_from_2028(self):
        vessel = VesselSpec(gross_tonnage=55_000)
        voyage = VoyagePattern(is_international=True)

        result = applicable_regimes(vessel, voyage, year=2028)

        assert result["nzf"].applies is True


class TestMatchesScopeMatrixExactly:
    """One fixture per named Bharat Line band (PLAN.md §5.4 / docs/scope_matrix.md),
    checked cell-for-cell against the scope-matrix table."""

    YEAR = 2028  # within the case-study horizon, at/after every regime's start_year

    def test_band_a_europe_liner(self):
        vessel = VesselSpec(gross_tonnage=55_000)
        voyage = VoyagePattern(
            is_international=True,
            eu_eea_third_country_voyage_fraction=0.9,
            eu_eea_berth_fraction=0.1,
        )
        result = applicable_regimes(vessel, voyage, year=self.YEAR)
        assert {k: v.applies for k, v in result.items()} == {
            "cii": True, "nzf": True, "fuel_eu": True, "eu_ets": True,
        }

    def test_band_b_non_eu_deep_sea(self):
        vessel = VesselSpec(gross_tonnage=25_000)
        voyage = VoyagePattern(is_international=True)
        result = applicable_regimes(vessel, voyage, year=self.YEAR)
        assert {k: v.applies for k, v in result.items()} == {
            "cii": True, "nzf": True, "fuel_eu": False, "eu_ets": False,
        }

    def test_band_c_coastal_feeder(self):
        vessel = VesselSpec(gross_tonnage=2500)
        voyage = VoyagePattern(is_international=False)
        result = applicable_regimes(vessel, voyage, year=self.YEAR)
        assert {k: v.applies for k, v in result.items()} == {
            "cii": False, "nzf": False, "fuel_eu": False, "eu_ets": False,
        }


class TestVoyagePatternValidation:
    def test_rejects_fractions_summing_above_one(self):
        with pytest.raises(ValueError):
            VoyagePattern(
                is_international=True,
                intra_eu_eea_voyage_fraction=0.6,
                eu_eea_berth_fraction=0.6,
            )

    def test_rejects_out_of_range_fraction(self):
        with pytest.raises(ValueError):
            VoyagePattern(is_international=True, eu_eea_berth_fraction=1.5)
