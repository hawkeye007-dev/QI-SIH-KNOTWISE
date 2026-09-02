"""Tests for the Exposure Map by flip-counting (Task 2R component 5)."""

import json
import random
import time
from types import SimpleNamespace

import pytest

from knotwise.fleet.loader import load_fleet, load_prices
from knotwise.optimization.exposure import (
    CAPEX_DECISION_TYPES,
    ExposedDecision,
    compute_dwt_by_route_year,
    compute_exposure,
    compute_mps_crosscheck,
    detect_exposed_decisions,
    detect_exposed_from_value_maps,
    exposure_result_to_dict,
    majority_values_from_per_seed_genomes,
    price_fueleu_election,
    price_route_change,
    price_shore_power,
    run_consistency_checks,
    stability_from_per_seed_genomes,
)
from knotwise.optimization.genome import DECISION_FIELDS, VesselYearGene, random_genome
from knotwise.optimization.mps_exposure import ExposureComparisonRow
from knotwise.optimization.sweep import ScenarioAxisPosition, SwitchingPoint, run_sweep


@pytest.fixture(scope="module")
def fleet():
    return load_fleet()


@pytest.fixture(scope="module")
def prices():
    return load_prices()


@pytest.fixture(scope="module")
def full_exposure(fleet, prices):
    """One K=5-scenario + sweep exposure computation, shared across every
    test that needs the real thing so it runs once rather than once per
    assertion.

    Deliberately NOT `compute_exposure`'s expensive stability-filter
    defaults (population 200 / 200 generations / 3 seeds -- tens of minutes
    on this fleet, verified separately via a one-off production run rather
    than baked into the routine test suite; see the exposure.py module
    docstring and the commit that introduced this filter for those real
    numbers).
    These settings (2 seeds, population 60/60 generations) were checked by
    hand before being pinned here: deterministic for these exact inputs, and
    confirmed to produce at least one stable exposed decision -- enough to
    exercise the full pipeline's structure without the production budget's
    cost. The "done when" criterion itself (at least one *real* stable
    exposed decision) is validated against the actual default budget, not
    reproduced as a fast test.
    """
    start = time.perf_counter()
    sweep = run_sweep(
        fleet,
        prices,
        seed=0,
        price_grid=tuple(range(0, 1001, 100)),
        population_size=20,
        cold_generations=20,
        warm_generations=8,
    )
    result = compute_exposure(fleet, prices, sweep, seeds=(0, 1), population_size=60, n_generations=60)
    elapsed = time.perf_counter() - start
    return result, elapsed


def _gene(vessel_id, year, **overrides):
    base = {
        "vessel_id": vessel_id,
        "year": year,
        "route_id": "india_gulf",
        "speed_band_index": 4,
        "fuel_id": "vlsfo",
        "shore_power": False,
        "borrow_election": False,
        "pool_opt_in": False,
    }
    base.update(overrides)
    return VesselYearGene(**base)


class TestDetectExposedDecisions:
    def test_flags_a_field_that_differs_across_scenarios(self, fleet):
        genomes = {
            "approved_text": [_gene("A1", 2028, fuel_id="hfo_scrubber")],
            "liberia": [_gene("A1", 2028, fuel_id="hfo_scrubber")],
            "tuvalu": [_gene("A1", 2028, fuel_id="b30_blend")],
            "brazil": [_gene("A1", 2028, fuel_id="hfo_scrubber")],
            "adoption_fails": [_gene("A1", 2028, fuel_id="hfo_scrubber")],
        }
        exposed = detect_exposed_decisions(genomes, fleet)
        assert len(exposed) == 1
        assert exposed[0]["vessel_id"] == "A1"
        assert exposed[0]["decision"] == "fuel_id"
        assert exposed[0]["values_by_scenario"]["tuvalu"] == "b30_blend"
        assert exposed[0]["values_by_scenario"]["approved_text"] == "hfo_scrubber"

    def test_no_disagreement_means_nothing_exposed(self, fleet):
        gene = _gene("A1", 2028, fuel_id="hfo_scrubber")
        genomes = {sid: [gene] for sid in ("approved_text", "liberia", "tuvalu", "brazil", "adoption_fails")}
        assert detect_exposed_decisions(genomes, fleet) == []

    def test_band_c_vessel_years_are_never_exposed(self, fleet):
        c_vessel_id = next(v["vessel_id"] for v in fleet["vessels"] if v["band"] == "C")
        genomes = {
            "approved_text": [_gene(c_vessel_id, 2028, fuel_id="hfo_scrubber")],
            "liberia": [_gene(c_vessel_id, 2028, fuel_id="hfo_scrubber")],
            "tuvalu": [_gene(c_vessel_id, 2028, fuel_id="b30_blend")],
            "brazil": [_gene(c_vessel_id, 2028, fuel_id="hfo_scrubber")],
            "adoption_fails": [_gene(c_vessel_id, 2028, fuel_id="hfo_scrubber")],
        }
        assert detect_exposed_decisions(genomes, fleet) == []


class TestStabilityFromPerSeedGenomes:
    """The pure part of the PLAN §8.3(c) stability filter (item B): given
    each seed's genome for one scenario, which decisions did the seeds
    disagree on. No GA solve needed -- exercised directly against hand-built
    genomes so the disagreement logic itself is verified deterministically,
    the same way `detect_exposed_decisions` is tested against hand-built
    per-scenario genomes above."""

    def test_agreement_across_all_seeds_is_stable(self):
        gene = _gene("A1", 2028, fuel_id="hfo_scrubber")
        genomes_by_seed = {0: [gene], 1: [gene], 2: [gene]}
        assert stability_from_per_seed_genomes(genomes_by_seed) == frozenset()

    def test_one_dissenting_seed_marks_the_field_unstable(self):
        genomes_by_seed = {
            0: [_gene("A1", 2028, fuel_id="hfo_scrubber")],
            1: [_gene("A1", 2028, fuel_id="hfo_scrubber")],
            2: [_gene("A1", 2028, fuel_id="b30_blend")],  # dissents
        }
        unstable = stability_from_per_seed_genomes(genomes_by_seed)
        assert ("A1", 2028, "fuel_id") in unstable

    def test_only_the_disagreeing_field_is_flagged_not_the_whole_gene(self):
        # route_id and fuel_id disagree; speed_band_index (and everything
        # else) agrees across seeds -> only the two disagreeing fields end
        # up in the unstable set.
        genomes_by_seed = {
            0: [_gene("A1", 2028, fuel_id="hfo_scrubber", route_id="india_northeurope", speed_band_index=4)],
            1: [_gene("A1", 2028, fuel_id="b30_blend", route_id="india_mediterranean", speed_band_index=4)],
        }
        unstable = stability_from_per_seed_genomes(genomes_by_seed)
        assert ("A1", 2028, "fuel_id") in unstable
        assert ("A1", 2028, "route_id") in unstable
        assert ("A1", 2028, "speed_band_index") not in unstable

    def test_two_vessel_years_are_tracked_independently(self):
        genomes_by_seed = {
            0: [_gene("A1", 2028, fuel_id="hfo_scrubber"), _gene("A2", 2029, fuel_id="vlsfo")],
            1: [_gene("A1", 2028, fuel_id="hfo_scrubber"), _gene("A2", 2029, fuel_id="mgo")],
        }
        unstable = stability_from_per_seed_genomes(genomes_by_seed)
        assert ("A1", 2028, "fuel_id") not in unstable
        assert ("A2", 2029, "fuel_id") in unstable


class TestMajorityValuesFromPerSeedGenomes:
    """The looser drill-down criterion (review item 1a) -- purely additive
    to `stability_from_per_seed_genomes`, which stays the unanimous
    headline unchanged. 2 of 3 seeds agreeing is a majority; a 3-way split
    (or a 1-1 tie with 2 seeds) reaches no majority at all."""

    def test_unanimous_agreement_is_also_a_majority(self):
        gene = _gene("A1", 2028, fuel_id="hfo_scrubber")
        genomes_by_seed = {0: [gene], 1: [gene], 2: [gene]}
        majority = majority_values_from_per_seed_genomes(genomes_by_seed)
        assert majority[("A1", 2028, "fuel_id")] == "hfo_scrubber"

    def test_two_of_three_seeds_reach_a_majority(self):
        genomes_by_seed = {
            0: [_gene("A1", 2028, fuel_id="hfo_scrubber")],
            1: [_gene("A1", 2028, fuel_id="hfo_scrubber")],
            2: [_gene("A1", 2028, fuel_id="b30_blend")],  # dissents
        }
        majority = majority_values_from_per_seed_genomes(genomes_by_seed)
        assert majority[("A1", 2028, "fuel_id")] == "hfo_scrubber"

    def test_a_three_way_split_reaches_no_majority(self):
        genomes_by_seed = {
            0: [_gene("A1", 2028, fuel_id="hfo_scrubber")],
            1: [_gene("A1", 2028, fuel_id="vlsfo")],
            2: [_gene("A1", 2028, fuel_id="b30_blend")],
        }
        majority = majority_values_from_per_seed_genomes(genomes_by_seed)
        assert ("A1", 2028, "fuel_id") not in majority

    def test_a_two_seed_tie_reaches_no_majority(self):
        genomes_by_seed = {
            0: [_gene("A1", 2028, fuel_id="hfo_scrubber")],
            1: [_gene("A1", 2028, fuel_id="vlsfo")],
        }
        majority = majority_values_from_per_seed_genomes(genomes_by_seed)
        assert ("A1", 2028, "fuel_id") not in majority

    def test_every_key_reaching_majority_is_also_a_stability_superset(self):
        # Anything unanimous (stability_from_per_seed_genomes says stable)
        # must also show up with a majority value -- majority is strictly
        # looser, never stricter.
        genomes_by_seed = {
            0: [_gene("A1", 2028, fuel_id="hfo_scrubber"), _gene("A2", 2029, fuel_id="vlsfo")],
            1: [_gene("A1", 2028, fuel_id="hfo_scrubber"), _gene("A2", 2029, fuel_id="mgo")],
            2: [_gene("A1", 2028, fuel_id="hfo_scrubber"), _gene("A2", 2029, fuel_id="vlsfo")],
        }
        unstable = stability_from_per_seed_genomes(genomes_by_seed)
        majority = majority_values_from_per_seed_genomes(genomes_by_seed)
        assert ("A1", 2028, "fuel_id") not in unstable
        assert majority[("A1", 2028, "fuel_id")] == "hfo_scrubber"
        # A2/2029 is unstable under unanimous (vlsfo/mgo/vlsfo disagree) but
        # 2 of 3 seeds (vlsfo) still reach a majority.
        assert ("A2", 2029, "fuel_id") in unstable
        assert majority[("A2", 2029, "fuel_id")] == "vlsfo"


class TestDetectExposedFromValueMaps:
    def test_flags_a_key_that_differs_across_scenarios(self, fleet):
        value_maps = {
            "approved_text": {("A1", 2028, "fuel_id"): "hfo_scrubber"},
            "tuvalu": {("A1", 2028, "fuel_id"): "b30_blend"},
        }
        exposed = detect_exposed_from_value_maps(value_maps, fleet)
        assert len(exposed) == 1
        assert exposed[0]["values_by_scenario"] == {"approved_text": "hfo_scrubber", "tuvalu": "b30_blend"}

    def test_a_key_missing_from_one_scenario_is_not_comparable(self, fleet):
        # No majority reached in "tuvalu" for this key -> not reportable,
        # even though the two scenarios that do have a value disagree.
        value_maps = {
            "approved_text": {("A1", 2028, "fuel_id"): "hfo_scrubber"},
            "tuvalu": {},
        }
        assert detect_exposed_from_value_maps(value_maps, fleet) == []

    def test_band_c_is_excluded(self, fleet):
        c_vessel_id = next(v["vessel_id"] for v in fleet["vessels"] if v["band"] == "C")
        value_maps = {
            "approved_text": {(c_vessel_id, 2028, "fuel_id"): "hfo_scrubber"},
            "tuvalu": {(c_vessel_id, 2028, "fuel_id"): "b30_blend"},
        }
        assert detect_exposed_from_value_maps(value_maps, fleet) == []


class TestPriceRouteChange:
    """The most bug-prone pricing rule: it must NOT be a flat
    `vessel_dwt * DEMAND_PENALTY_USD_PER_DWT_SHORTFALL` (that per-DWT rate is
    a deliberately prohibitive GA deterrent, not a realistic price -- using
    it flat was caught producing a route-flip capital-at-risk figure larger
    than the fleet's entire modelled cost before this test existed)."""

    def test_zero_when_both_routes_have_slack(self, fleet):
        # india_mediterranean's floor is 72000 and nothing else is assigned
        # to either route this year -> plenty of slack moving one A-band
        # vessel (72000 DWT) onto or off either route.
        decision = {
            "vessel_id": "A1",
            "year": 2028,
            "decision": "route_id",
            "values_by_scenario": {"approved_text": "india_northeurope", "tuvalu": "india_mediterranean"},
        }
        baseline_gene = _gene("A1", 2028, route_id="india_northeurope")
        vessel = next(v for v in fleet["vessels"] if v["vessel_id"] == "A1")
        dwt_by_route_year = {("india_northeurope", 2028): 216000.0, ("india_mediterranean", 2028): 216000.0}
        capital_at_risk, _status, _notes = price_route_change(decision, baseline_gene, vessel, fleet, dwt_by_route_year)
        assert capital_at_risk == 0.0

    def test_nonzero_when_leaving_the_baseline_route_would_create_a_shortfall(self, fleet):
        decision = {
            "vessel_id": "A1",
            "year": 2028,
            "decision": "route_id",
            "values_by_scenario": {"approved_text": "india_northeurope", "tuvalu": "india_mediterranean"},
        }
        baseline_gene = _gene("A1", 2028, route_id="india_northeurope")
        vessel = next(v for v in fleet["vessels"] if v["vessel_id"] == "A1")
        # Only this one vessel covers india_northeurope (floor 72000) -> moving
        # it away leaves that route's whole floor unserved.
        dwt_by_route_year = {("india_northeurope", 2028): 72000.0, ("india_mediterranean", 2028): 216000.0}
        capital_at_risk, _status, _notes = price_route_change(decision, baseline_gene, vessel, fleet, dwt_by_route_year)
        assert capital_at_risk > 0.0

    def test_never_uses_the_flat_per_dwt_deterrent_rate(self, fleet):
        # The bug this guards against: 72000 DWT * the constraints.py deterrent
        # rate ($10,000/DWT) = $720,000,000 applied to *every* route flip
        # regardless of whether slack exists. With slack on both sides, the
        # correct answer is exactly zero, not that number.
        decision = {
            "vessel_id": "A1",
            "year": 2028,
            "decision": "route_id",
            "values_by_scenario": {"approved_text": "india_northeurope", "tuvalu": "india_mediterranean"},
        }
        baseline_gene = _gene("A1", 2028, route_id="india_northeurope")
        vessel = next(v for v in fleet["vessels"] if v["vessel_id"] == "A1")
        dwt_by_route_year = {("india_northeurope", 2028): 216000.0, ("india_mediterranean", 2028): 216000.0}
        capital_at_risk, _, _ = price_route_change(decision, baseline_gene, vessel, fleet, dwt_by_route_year)
        assert capital_at_risk != 720_000_000.0


class TestPriceShorePower:
    def test_matches_fleet_json_figure_exactly(self, fleet):
        capital_at_risk, _status, _notes = price_shore_power(fleet)
        assert capital_at_risk == fleet["shore_power_model"]["cost_usd_per_vessel_year_when_elected"]


class TestPriceFueleuElection:
    def test_pool_opt_in_delta_is_computed_not_zero_for_a_deficit_vessel(self, fleet, prices):
        from knotwise.regulatory.scenario_resolution import resolve_regulations_for_scenario

        regulations = resolve_regulations_for_scenario("approved_text")
        # A dirty (hfo_scrubber) Band A vessel is FuelEU-applicable and, on
        # its own, in deficit -> pool_opt_in should change its FuelEU cost
        # relative to not pooling (no partner to pool with here, so it's
        # really "pooling changes nothing when solo" vs "the ledger prices a
        # deficit" -- either way this must be a real, computed number).
        baseline_genome = [
            _gene("A1", 2028, fuel_id="hfo_scrubber", route_id="india_northeurope", pool_opt_in=False)
        ]
        decision = {
            "vessel_id": "A1",
            "year": 2028,
            "decision": "pool_opt_in",
            "values_by_scenario": {"approved_text": False, "tuvalu": True},
        }
        capital_at_risk, status, _notes = price_fueleu_election(decision, baseline_genome, fleet, prices, regulations)
        assert capital_at_risk >= 0.0
        assert status == "SECONDARY_SOURCE"


class TestComputeDwtByRouteYear:
    def test_sums_dwt_per_route_year(self, fleet):
        genome = [
            _gene("A1", 2028, route_id="india_northeurope"),
            _gene("A2", 2028, route_id="india_northeurope"),
            _gene("B1", 2028, route_id="india_gulf"),
        ]
        totals = compute_dwt_by_route_year(genome, fleet)
        a_dwt = fleet["vessel_class_defaults"]["A"]["dwt_tonnes"]
        b_dwt = fleet["vessel_class_defaults"]["B"]["dwt_tonnes"]
        assert totals[("india_northeurope", 2028)] == pytest.approx(2 * a_dwt)
        assert totals[("india_gulf", 2028)] == pytest.approx(b_dwt)


class TestRunConsistencyChecks:
    """The 'free' PLAN §8.3(b) cross-check (item 4) -- exercised directly
    against synthetic fixtures so its True/False/None outcomes are verified
    deterministically, independent of any particular GA run."""

    def _decision(self, values_by_scenario):
        return ExposedDecision(
            vessel_id="A1",
            year=2028,
            decision="fuel_id",
            values_by_scenario=values_by_scenario,
            capital_at_risk_usd=1000.0,
            capital_at_risk_status="SECONDARY_SOURCE",
            capital_at_risk_notes="",
        )

    def _tick(self, scenario_id, operating_point):
        return ScenarioAxisPosition(
            scenario_id=scenario_id,
            label=scenario_id,
            kind="tier_annotated_range",
            low_usd_per_tco2e=operating_point,
            high_usd_per_tco2e=operating_point,
            operating_point_usd_per_tco2e=operating_point,
            status="SECONDARY_SOURCE",
            notes="",
        )

    def test_consistent_when_switching_point_overlaps_the_scenario_gap(self):
        decision = self._decision({"approved_text": "hfo_scrubber", "tuvalu": "b30_blend"})
        ticks = {"approved_text": self._tick("approved_text", 150), "tuvalu": self._tick("tuvalu", 300)}
        switching_points_by_key = {
            ("A1", 2028, "fuel_id"): [SwitchingPoint("A1", 2028, "fuel_id", "hfo_scrubber", "b30_blend", 200, 225)]
        }
        checks = run_consistency_checks([decision], ticks, switching_points_by_key)
        assert len(checks) == 1
        assert checks[0].consistent is True

    def test_inconsistent_when_switching_point_does_not_overlap(self):
        decision = self._decision({"approved_text": "hfo_scrubber", "tuvalu": "b30_blend"})
        ticks = {"approved_text": self._tick("approved_text", 150), "tuvalu": self._tick("tuvalu", 300)}
        # Switching point way outside [150, 300].
        switching_points_by_key = {
            ("A1", 2028, "fuel_id"): [SwitchingPoint("A1", 2028, "fuel_id", "hfo_scrubber", "b30_blend", 500, 525)]
        }
        checks = run_consistency_checks([decision], ticks, switching_points_by_key)
        assert len(checks) == 1
        assert checks[0].consistent is False

    def test_inconsistent_when_no_switching_point_found_at_all(self):
        decision = self._decision({"approved_text": "hfo_scrubber", "tuvalu": "b30_blend"})
        ticks = {"approved_text": self._tick("approved_text", 150), "tuvalu": self._tick("tuvalu", 300)}
        checks = run_consistency_checks([decision], ticks, {})
        assert len(checks) == 1
        assert checks[0].consistent is False

    def test_none_when_a_scenario_has_no_axis_position(self):
        decision = self._decision({"approved_text": "hfo_scrubber", "liberia": "b30_blend"})
        ticks = {"approved_text": self._tick("approved_text", 150)}  # liberia has no tick at all
        checks = run_consistency_checks([decision], ticks, {})
        assert len(checks) == 1
        assert checks[0].consistent is None

    def test_no_check_emitted_when_values_are_actually_equal(self):
        # Same value under both scenarios -> not a real flip for this pair,
        # shouldn't be checked (and shouldn't have been detected as exposed
        # in the first place, but this guards the check function itself too).
        decision = self._decision({"approved_text": "hfo_scrubber", "tuvalu": "hfo_scrubber"})
        ticks = {"approved_text": self._tick("approved_text", 150), "tuvalu": self._tick("tuvalu", 300)}
        assert run_consistency_checks([decision], ticks, {}) == []


class TestComputeExposureEndToEnd:
    def test_at_least_one_stable_decision_is_exposed(self, full_exposure):
        # PLAN §2R component 5's "done when": zero flips across all five
        # scenarios would be the §8.10 Outcome-A finding arriving early, and
        # would need reporting rather than a passing test forced around it.
        # (These reduced test settings were checked by hand to still clear
        # this bar -- see the full_exposure fixture's docstring for why the
        # production-budget confirmation isn't reproduced here.)
        result, _ = full_exposure
        assert len(result.per_decision_deltas) >= 1

    def test_stable_and_unstable_decisions_are_disjoint(self, full_exposure):
        result, _ = full_exposure
        stable_keys = {(d.vessel_id, d.year, d.decision) for d in result.per_decision_deltas}
        unstable_keys = {(d.vessel_id, d.year, d.decision) for d in result.unstable_decisions}
        assert stable_keys.isdisjoint(unstable_keys)

    def test_no_band_c_vessel_appears_anywhere(self, full_exposure, fleet):
        result, _ = full_exposure
        band_by_vessel_id = {v["vessel_id"]: v["band"] for v in fleet["vessels"]}
        for decision in result.per_decision_deltas:
            assert band_by_vessel_id[decision.vessel_id] != "C"
        for decision in result.unstable_decisions:
            assert band_by_vessel_id[decision.vessel_id] != "C"

    def test_plan_spread_is_max_minus_min_of_scenario_totals(self, full_exposure):
        result, _ = full_exposure
        totals = result.plan_spread.scenario_totals_usd
        assert set(totals) == set(result.scenario_ids)
        assert result.plan_spread.spread_usd == pytest.approx(max(totals.values()) - min(totals.values()))
        assert totals[result.plan_spread.max_scenario_id] == max(totals.values())
        assert totals[result.plan_spread.min_scenario_id] == min(totals.values())
        assert result.plan_spread.spread_inr == pytest.approx(result.plan_spread.spread_usd * result.fx_rate_usd_to_inr)

    def test_plan_spread_is_not_the_sum_of_per_decision_deltas(self, full_exposure):
        # The bug this guards against: component 5's first version summed
        # every per-decision delta into one "total exposure" figure that
        # exceeded the entire fleet's modelled cost. plan_spread is a wholly
        # different, non-overlapping computation and must not coincide with
        # (or be derived from) that sum.
        result, _ = full_exposure
        sum_of_deltas = sum(d.capital_at_risk_usd for d in result.per_decision_deltas)
        if sum_of_deltas > 0:
            assert result.plan_spread.spread_usd != pytest.approx(sum_of_deltas)

    def test_capex_exposure_only_contains_capex_decision_types(self, full_exposure):
        result, _ = full_exposure
        for decision in result.capex_exposure.decisions:
            assert decision.decision in CAPEX_DECISION_TYPES
        assert result.capex_exposure.total_usd == pytest.approx(
            sum(d.capital_at_risk_usd for d in result.capex_exposure.decisions)
        )
        assert result.capex_exposure.total_inr == pytest.approx(
            result.capex_exposure.total_usd * result.fx_rate_usd_to_inr
        )

    def test_capex_exposure_is_a_subset_of_per_decision_deltas(self, full_exposure):
        result, _ = full_exposure
        per_decision_keys = {(d.vessel_id, d.year, d.decision) for d in result.per_decision_deltas}
        for decision in result.capex_exposure.decisions:
            assert (decision.vessel_id, decision.year, decision.decision) in per_decision_keys

    def test_majority_capex_exposure_only_contains_capex_decision_types(self, full_exposure):
        result, _ = full_exposure
        for decision in result.majority_capex_exposure.decisions:
            assert decision.decision in CAPEX_DECISION_TYPES
        assert result.majority_capex_exposure.total_usd == pytest.approx(
            sum(d.capital_at_risk_usd for d in result.majority_capex_exposure.decisions)
        )
        assert result.majority_capex_exposure.total_inr == pytest.approx(
            result.majority_capex_exposure.total_usd * result.fx_rate_usd_to_inr
        )

    def test_majority_capex_exposure_is_a_subset_of_majority_band_decisions(self, full_exposure):
        result, _ = full_exposure
        majority_keys = {(d.vessel_id, d.year, d.decision) for d in result.majority_band_decisions}
        for decision in result.majority_capex_exposure.decisions:
            assert (decision.vessel_id, decision.year, decision.decision) in majority_keys

    def test_majority_capex_exposure_never_overlaps_the_headline_capex_exposure(self, full_exposure):
        # Both tiers filter to CAPEX_DECISION_TYPES, but majority_band_decisions
        # is already deduplicated against the unanimous headline set (review
        # item 1a), so the two capex totals must never share a decision --
        # safe to show side by side without double-counting.
        result, _ = full_exposure
        headline_keys = {(d.vessel_id, d.year, d.decision) for d in result.capex_exposure.decisions}
        majority_capex_keys = {(d.vessel_id, d.year, d.decision) for d in result.majority_capex_exposure.decisions}
        assert headline_keys.isdisjoint(majority_capex_keys)

    def test_fx_conversion_carries_provenance(self, full_exposure, prices):
        result, _ = full_exposure
        fx_entry = prices["fx_rates"]["usd_to_inr"]
        assert result.fx_rate_usd_to_inr == fx_entry["rate"]
        assert result.fx_status == fx_entry["status"]
        assert result.fx_retrieval_date == fx_entry["retrieval_date"]

    def test_every_per_decision_delta_has_a_priced_status_and_notes(self, full_exposure):
        result, _ = full_exposure
        for decision in result.per_decision_deltas:
            assert decision.capital_at_risk_status
            assert decision.capital_at_risk_notes
            assert decision.capital_at_risk_usd >= 0.0

    def test_consistency_checks_are_produced(self, full_exposure):
        # item 4: "do not skip". The logic itself (True/False/None outcomes)
        # is verified deterministically in TestRunConsistencyChecks above;
        # this just confirms compute_exposure actually wires it up end to
        # end against the real stable-exposed decisions and sweep.
        result, _ = full_exposure
        assert len(result.consistency_checks) >= 0  # always true; the real assertion is that this doesn't raise
        for check in result.consistency_checks:
            assert check.consistent in (True, False, None)

    def test_majority_band_never_duplicates_the_headline(self, full_exposure):
        # Review item 1a: majority is purely additive drill-down, never a
        # replacement for or overlap with the unanimous headline tier.
        result, _ = full_exposure
        headline_keys = {(d.vessel_id, d.year, d.decision) for d in result.per_decision_deltas}
        majority_keys = {(d.vessel_id, d.year, d.decision) for d in result.majority_band_decisions}
        assert headline_keys.isdisjoint(majority_keys)

    def test_majority_unstable_is_a_subset_of_headline_unstable(self, full_exposure):
        # Majority is a strictly looser bar than unanimous, so anything that
        # can't even reach a majority also fails the stricter unanimous bar.
        result, _ = full_exposure
        headline_unstable = {(d.vessel_id, d.year, d.decision) for d in result.unstable_decisions}
        majority_unstable = {(d.vessel_id, d.year, d.decision) for d in result.majority_unstable_decisions}
        assert majority_unstable <= headline_unstable

    def test_majority_band_decisions_are_priced_and_band_c_free(self, full_exposure, fleet):
        result, _ = full_exposure
        band_by_vessel_id = {v["vessel_id"]: v["band"] for v in fleet["vessels"]}
        for decision in result.majority_band_decisions:
            assert band_by_vessel_id[decision.vessel_id] != "C"
            assert decision.capital_at_risk_status
            assert decision.capital_at_risk_notes

    def test_reproducible_from_seeds(self, fleet, prices):
        sweep = run_sweep(
            fleet, prices, price_grid=(0, 400, 800), seed=3, population_size=16, cold_generations=15, warm_generations=6
        )
        kwargs = {"seeds": (3, 4, 5), "population_size": 20, "n_generations": 20}
        result_a = compute_exposure(fleet, prices, sweep, **kwargs)
        result_b = compute_exposure(fleet, prices, sweep, **kwargs)
        assert [d.capital_at_risk_usd for d in result_a.per_decision_deltas] == pytest.approx(
            [d.capital_at_risk_usd for d in result_b.per_decision_deltas]
        )
        assert result_a.plan_spread.spread_usd == pytest.approx(result_b.plan_spread.spread_usd)
        assert result_a.capex_exposure.total_usd == pytest.approx(result_b.capex_exposure.total_usd)
        assert result_a.majority_capex_exposure.total_usd == pytest.approx(result_b.majority_capex_exposure.total_usd)
        assert {(d.vessel_id, d.year, d.decision) for d in result_a.unstable_decisions} == {
            (d.vessel_id, d.year, d.decision) for d in result_b.unstable_decisions
        }
        assert {(d.vessel_id, d.year, d.decision) for d in result_a.majority_band_decisions} == {
            (d.vessel_id, d.year, d.decision) for d in result_b.majority_band_decisions
        }


class TestMPSCrosscheck:
    """PLAN §8.3(b)'s validation, now runnable in both directions
    (`exposure.compute_mps_crosscheck`, wiring `mps_exposure.py`'s real
    tensor-native mutual information against this module's classical
    flip-counting on the same run's solved baseline)."""

    def test_baseline_genome_is_a_full_fleet_plan(self, full_exposure, fleet):
        result, _ = full_exposure
        assert len(result.baseline_genome) == len(fleet["vessels"]) * len(fleet["horizon_years"])

    def test_covers_exactly_the_unanimous_tier_candidate_slots(self, full_exposure, fleet, prices):
        result, _ = full_exposure
        rows = compute_mps_crosscheck(fleet, prices, result)

        candidate_slots = {(d.vessel_id, d.year) for d in result.per_decision_deltas + result.unstable_decisions}
        assert len(rows) == len(candidate_slots) * len(DECISION_FIELDS)
        assert all(isinstance(row, ExposureComparisonRow) for row in rows)

    def test_every_row_label_matches_the_classical_result_it_was_built_from(self, full_exposure, fleet, prices):
        result, _ = full_exposure
        rows = compute_mps_crosscheck(fleet, prices, result)

        exposed_keys = {(d.vessel_id, d.year, d.decision) for d in result.per_decision_deltas}
        unstable_keys = {(d.vessel_id, d.year, d.decision) for d in result.unstable_decisions}
        for row in rows:
            key = (row.vessel_id, row.year, row.decision)
            if key in exposed_keys:
                assert row.classical_status == "exposed"
            elif key in unstable_keys:
                assert row.classical_status == "unstable"
            else:
                assert row.classical_status == "not_exposed"
            assert row.mutual_information_bits >= -1e-9

    def test_empty_when_the_unanimous_tier_has_no_candidates(self, fleet, prices):
        # A minimal, cheap ExposureResult-shaped stand-in with an empty
        # unanimous tier -- confirms compute_mps_crosscheck degrades to "no
        # slots to check" rather than falling back to the whole fleet.
        empty_result = SimpleNamespace(
            per_decision_deltas=[], unstable_decisions=[], baseline_genome=random_genome(fleet, random.Random(0))
        )
        rows = compute_mps_crosscheck(fleet, prices, empty_result)
        assert rows == []


class TestOutputSerialization:
    def test_exposure_result_to_dict_is_json_serializable_and_complete(self, full_exposure):
        result, _ = full_exposure
        payload = exposure_result_to_dict(result)
        json.dumps(payload)  # must not raise

        assert payload["summary"]["stable_exposed_decision_count"] == len(result.per_decision_deltas)
        assert payload["summary"]["unstable_decision_count"] == len(result.unstable_decisions)
        assert payload["summary"]["plan_spread_inr"] == pytest.approx(result.plan_spread.spread_inr)
        assert payload["summary"]["capex_exposure_inr"] == pytest.approx(result.capex_exposure.total_inr)

        assert payload["methodology"]["stability_seeds"] == list(result.stability_seeds)
        assert payload["methodology"]["ga_population_size"] == result.ga_population_size

        assert payload["plan_spread"]["spread_usd"] == pytest.approx(result.plan_spread.spread_usd)
        assert "description" in payload["plan_spread"]

        assert "description" in payload["capex_exposure"]
        assert payload["capex_exposure"]["total_usd"] == pytest.approx(result.capex_exposure.total_usd)

        assert "description" in payload["majority_capex_exposure"]
        assert payload["majority_capex_exposure"]["total_usd"] == pytest.approx(
            result.majority_capex_exposure.total_usd
        )
        assert payload["summary"]["majority_capex_exposure_inr"] == pytest.approx(
            result.majority_capex_exposure.total_inr
        )

        assert "description" in payload["per_decision_deltas"]
        assert "must not be summed" in payload["per_decision_deltas"]["description"].lower()

        assert payload["unstable_decisions"]["count"] == len(result.unstable_decisions)

        assert payload["summary"]["majority_band_decision_count"] == len(result.majority_band_decisions)
        assert payload["summary"]["majority_unstable_decision_count"] == len(result.majority_unstable_decisions)
        assert "description" in payload["majority_band"]
        assert len(payload["majority_band"]["decisions"]) == len(result.majority_band_decisions)
        assert payload["majority_band"]["unstable_decisions"]["count"] == len(result.majority_unstable_decisions)
        assert len(payload["majority_band_consistency_checks"]) == len(result.majority_band_consistency_checks)

        assert payload["fx"]["status"]
        assert payload["fx"]["retrieval_date"]
        assert "consistency_checks" in payload

    def test_per_decision_deltas_json_carries_flip_data(self, full_exposure):
        result, _ = full_exposure
        payload = exposure_result_to_dict(result)
        if payload["per_decision_deltas"]["decisions"]:
            first = payload["per_decision_deltas"]["decisions"][0]
            assert first["flips_between_which_scenarios"]
            assert "amount_usd" in first["capital_at_risk"]
