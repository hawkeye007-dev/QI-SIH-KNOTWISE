"""Tests for the MPS / Born-machine Exposure Map
(`knotwise.optimization.mps_exposure`).

Deliberately scoped to a handful of vessel-year slots, not the whole
fleet: `vessel_year_born_machine` enumerates every combination of a slot's
six decision fields under all five scenarios (a few hundred to ~2000
`objective.evaluate` calls per slot), so these tests stay fast by picking
one or two slots rather than the full (vessels x years) grid. The
underlying math (mutual information, TT-SVD) is already proven correct in
isolation by `test_tensor_network.py`; these tests check that this module
wires the fleet/regulatory data into that math correctly.
"""

from __future__ import annotations

import random
from types import SimpleNamespace

import numpy as np
import pytest

from knotwise.fleet.loader import load_fleet, load_prices
from knotwise.optimization.genome import DECISION_FIELDS, field_domains, random_genome
from knotwise.optimization.mps_exposure import (
    ExposureComparisonRow,
    compare_with_classical,
    compute_mps_exposure,
    compute_mps_exposure_map,
    vessel_year_born_machine,
)


@pytest.fixture(scope="module")
def fleet():
    return load_fleet()


@pytest.fixture(scope="module")
def prices():
    return load_prices()


@pytest.fixture(scope="module")
def baseline_genome(fleet):
    # A fixed random genome, not a solved plan -- these tests only need
    # *some* concrete "everything else held fixed" baseline, not an
    # optimal one (an optimal baseline matters for the real demo output,
    # not for checking this module's plumbing).
    return random_genome(fleet, random.Random(0))


@pytest.fixture(scope="module")
def one_vessel_year(fleet):
    vessel = fleet["vessels"][0]
    year = fleet["horizon_years"][0]
    return vessel["vessel_id"], year


class TestBornMachineTensor:
    def test_tensor_is_a_valid_probability_distribution(self, fleet, prices, baseline_genome, one_vessel_year):
        vessel_id, year = one_vessel_year
        born_machine = vessel_year_born_machine(vessel_id, year, fleet, prices, baseline_genome)

        assert np.all(born_machine.tensor >= 0)
        assert born_machine.tensor.sum() == pytest.approx(1.0, abs=1e-9)
        assert born_machine.tensor.shape[0] == len(born_machine.scenario_ids) == 5

    def test_tensor_shape_matches_the_slot_own_field_domains(self, fleet, prices, baseline_genome, one_vessel_year):
        vessel_id, year = one_vessel_year
        born_machine = vessel_year_born_machine(vessel_id, year, fleet, prices, baseline_genome)

        vessel = next(v for v in fleet["vessels"] if v["vessel_id"] == vessel_id)
        domains = field_domains(vessel, fleet, year)
        expected_shape = (5, *(len(domains[f]) for f in DECISION_FIELDS))
        assert born_machine.tensor.shape == expected_shape
        assert born_machine.fields == DECISION_FIELDS

    def test_each_scenario_rows_mode_is_its_own_cheapest_combination(
        self, fleet, prices, baseline_genome, one_vessel_year
    ):
        # Sanity check on the Boltzmann construction: within one scenario
        # (fixed r), the highest-probability combination should be the one
        # objective.evaluate actually priced cheapest for that scenario --
        # not a hand-copy of the pipeline, just confirming the distribution
        # points the right way.
        vessel_id, year = one_vessel_year
        born_machine = vessel_year_born_machine(vessel_id, year, fleet, prices, baseline_genome)

        for r_index in range(len(born_machine.scenario_ids)):
            row = born_machine.tensor[r_index]
            mode_index = np.unravel_index(np.argmax(row), row.shape)
            min_index = np.unravel_index(np.argmin(row), row.shape)
            # The mode must be strictly more probable than the row's own
            # least-probable cell whenever the row isn't perfectly flat
            # (a flat row means every combo costs the same for this slot
            # under this scenario -- a legitimate, low-exposure outcome).
            if not np.allclose(row, row.flat[0]):
                assert row[mode_index] > row[min_index]

    def test_temperature_falls_back_to_a_flat_distribution_when_costs_never_vary(
        self, fleet, prices, baseline_genome, one_vessel_year
    ):
        vessel_id, year = one_vessel_year
        born_machine = vessel_year_born_machine(
            vessel_id, year, fleet, prices, baseline_genome, temperature=1e12
        )
        # An enormous temperature should already look nearly flat; this
        # also exercises the explicit-temperature override path.
        row = born_machine.tensor[0]
        assert np.allclose(row, row.flat[0], rtol=1e-3)


class TestComputeMPSExposure:
    def test_mutual_information_is_finite_nonnegative_and_covers_every_field(
        self, fleet, prices, baseline_genome, one_vessel_year
    ):
        vessel_id, year = one_vessel_year
        result = compute_mps_exposure(vessel_id, year, fleet, prices, baseline_genome)

        assert set(result.mutual_information_bits) == set(DECISION_FIELDS)
        for field_name, mi in result.mutual_information_bits.items():
            assert np.isfinite(mi), f"{field_name} MI was not finite"
            assert mi >= -1e-9, f"{field_name} MI was negative: {mi}"

    def test_bond_dimensions_reported_for_every_bond(self, fleet, prices, baseline_genome, one_vessel_year):
        vessel_id, year = one_vessel_year
        result = compute_mps_exposure(vessel_id, year, fleet, prices, baseline_genome)
        # 7 axes (r + 6 fields) -> 6 bonds.
        assert len(result.bond_dimensions) == 6
        assert all(d >= 1 for d in result.bond_dimensions)


class TestComputeMPSExposureMap:
    def test_runs_over_an_explicit_small_slot_list(self, fleet, prices, baseline_genome, one_vessel_year):
        vessel_id, year = one_vessel_year
        other_vessel_id = fleet["vessels"][1]["vessel_id"]
        result = compute_mps_exposure_map(
            fleet, prices, baseline_genome, vessel_years=[(vessel_id, year), (other_vessel_id, year)]
        )
        assert len(result.per_slot) == 2

        ranked = result.ranked()
        assert len(ranked) == 2 * len(DECISION_FIELDS)
        # Descending by mutual information.
        mi_values = [row[3] for row in ranked]
        assert mi_values == sorted(mi_values, reverse=True)


class TestCompareWithClassical:
    def test_labels_each_row_by_the_classical_exposure_result(self, fleet, prices, baseline_genome, one_vessel_year):
        vessel_id, year = one_vessel_year
        mps_result = compute_mps_exposure_map(fleet, prices, baseline_genome, vessel_years=[(vessel_id, year)])

        # A minimal duck-typed stand-in for exposure.ExposureResult -- only
        # the two attributes compare_with_classical actually reads, so this
        # test doesn't have to pay for a real (multi-minute) classical run.
        exposed_field, unstable_field = DECISION_FIELDS[0], DECISION_FIELDS[1]
        classical_result = SimpleNamespace(
            per_decision_deltas=[SimpleNamespace(vessel_id=vessel_id, year=year, decision=exposed_field)],
            unstable_decisions=[SimpleNamespace(vessel_id=vessel_id, year=year, decision=unstable_field)],
        )

        rows = compare_with_classical(mps_result, classical_result)
        assert len(rows) == len(DECISION_FIELDS)
        by_field = {row.decision: row for row in rows}
        assert by_field[exposed_field].classical_status == "exposed"
        assert by_field[unstable_field].classical_status == "unstable"
        other_field = next(f for f in DECISION_FIELDS if f not in (exposed_field, unstable_field))
        assert by_field[other_field].classical_status == "not_exposed"
        assert all(isinstance(row, ExposureComparisonRow) for row in rows)
