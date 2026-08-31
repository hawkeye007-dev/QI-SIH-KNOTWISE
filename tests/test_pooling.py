"""Tests for FuelEU pooling economics (Task 2R component 3) — the headline fixture.

Written before knotwise.optimization.pooling exists.
"""

import pytest

from knotwise.regulatory.implied_price import fueleu_penalty_eur


def _import():
    from knotwise.optimization.pooling import VesselPoolBalance, resolve_pool

    return VesselPoolBalance, resolve_pool


class TestPoolAccepted:
    def test_two_vessels_positive_total_is_accepted_and_beats_per_vessel_compliance(self):
        VesselPoolBalance, resolve_pool = _import()

        surplus_vessel = VesselPoolBalance(vessel_id="A1", balance_gco2eq=3_000_000)
        deficit_vessel = VesselPoolBalance(vessel_id="A2", balance_gco2eq=-1_000_000)

        result = resolve_pool([surplus_vessel, deficit_vessel])

        assert result.accepted is True
        assert result.total_balance_gco2eq == pytest.approx(2_000_000)

        members = {m.vessel_id: m for m in result.members}
        # No-worsening / no-flip-to-deficit invariants, checked exactly:
        assert members["A2"].balance_after_pool_gco2eq == pytest.approx(0.0)  # deficit fully absorbed, never worsened
        assert members["A1"].balance_after_pool_gco2eq >= 0  # surplus entrant must not end in deficit
        assert members["A1"].balance_after_pool_gco2eq == pytest.approx(3_000_000 - 1_000_000)

        # The headline claim: pooling costs nothing here, but the deficit
        # vessel alone would have paid a real penalty (hand-computed via the
        # same Annex-IV-derived formula already in implied_price.py).
        pooled_total_cost = sum(m.cost.amount_usd for m in result.members)
        standalone_penalty_eur = fueleu_penalty_eur(
            compliance_balance_gco2eq=-1_000_000, ghg_intensity_actual_gco2e_per_mj=91.16
        )
        assert pooled_total_cost == 0.0
        assert standalone_penalty_eur > 0
        assert pooled_total_cost < standalone_penalty_eur

    def test_exact_zero_total_is_accepted(self):
        VesselPoolBalance, resolve_pool = _import()
        result = resolve_pool(
            [VesselPoolBalance("A1", 1_000_000), VesselPoolBalance("A2", -1_000_000)]
        )
        assert result.accepted is True
        assert result.total_balance_gco2eq == pytest.approx(0.0)


class TestPoolRejected:
    def test_negative_total_is_rejected_never_approximated(self):
        VesselPoolBalance, resolve_pool = _import()
        result = resolve_pool(
            [VesselPoolBalance("A1", 500_000), VesselPoolBalance("A2", -1_000_000)]
        )
        assert result.accepted is False
        assert result.total_balance_gco2eq == pytest.approx(-500_000)
        assert result.members == []  # no partial/approximate pooling — caller falls back per-vessel


class TestPoolInvariantsGeneral:
    def test_no_surplus_entrant_ever_flips_to_deficit(self):
        VesselPoolBalance, resolve_pool = _import()
        result = resolve_pool(
            [
                VesselPoolBalance("A1", 100_000),
                VesselPoolBalance("A2", 50_000),
                VesselPoolBalance("A3", -140_000),
            ]
        )
        assert result.accepted is True
        for member in result.members:
            original = next(
                v.balance_gco2eq
                for v in [VesselPoolBalance("A1", 100_000), VesselPoolBalance("A2", 50_000), VesselPoolBalance("A3", -140_000)]
                if v.vessel_id == member.vessel_id
            )
            if original > 0:
                assert member.balance_after_pool_gco2eq >= 0
            else:
                assert member.balance_after_pool_gco2eq >= original  # never worsened
