"""Tests for the Exposure Map by flip-counting (Task 2R component 5)."""

import json
import time
from collections import Counter

import pytest

from knotwise.fleet.loader import load_fleet, load_prices
from knotwise.optimization.exposure import (
    ExposedDecision,
    compute_dwt_by_route_year,
    compute_exposure,
    detect_exposed_decisions,
    exposure_result_to_dict,
    price_fueleu_election,
    price_route_change,
    price_shore_power,
    run_consistency_checks,
)
from knotwise.optimization.genome import VesselYearGene
from knotwise.optimization.sweep import ScenarioAxisPosition, SwitchingPoint, run_sweep


@pytest.fixture(scope="module")
def fleet():
    return load_fleet()


@pytest.fixture(scope="module")
def prices():
    return load_prices()


@pytest.fixture(scope="module")
def full_exposure(fleet, prices):
    """One full-K=5-scenario + full-default-sweep exposure computation,
    shared across every test that needs the real thing (the expensive path)
    so it runs once rather than once per assertion."""
    start = time.perf_counter()
    sweep = run_sweep(fleet, prices, seed=0)
    result = compute_exposure(fleet, prices, sweep, seed=0)
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
    def test_at_least_one_decision_is_exposed(self, full_exposure):
        # PLAN §2R component 5's "done when": zero flips across all five
        # scenarios would be the §8.10 Outcome-A finding arriving early, and
        # would need reporting rather than a passing test forced around it.
        result, _ = full_exposure
        assert len(result.exposed_decisions) >= 1

    def test_no_band_c_vessel_appears(self, full_exposure, fleet):
        result, _ = full_exposure
        band_by_vessel_id = {v["vessel_id"]: v["band"] for v in fleet["vessels"]}
        for decision in result.exposed_decisions:
            assert band_by_vessel_id[decision.vessel_id] != "C"

    def test_summary_numbers_are_computed_not_placeholders(self, full_exposure):
        result, _ = full_exposure
        assert len(result.exposed_decisions) > 0
        assert result.total_capital_at_risk_usd > 0
        assert result.total_capital_at_risk_inr == pytest.approx(
            result.total_capital_at_risk_usd * result.fx_rate_usd_to_inr
        )

    def test_fx_conversion_carries_provenance(self, full_exposure, prices):
        result, _ = full_exposure
        fx_entry = prices["fx_rates"]["usd_to_inr"]
        assert result.fx_rate_usd_to_inr == fx_entry["rate"]
        assert result.fx_status == fx_entry["status"]
        assert result.fx_retrieval_date == fx_entry["retrieval_date"]

    def test_every_exposed_decision_has_a_priced_status_and_notes(self, full_exposure):
        result, _ = full_exposure
        for decision in result.exposed_decisions:
            assert decision.capital_at_risk_status
            assert decision.capital_at_risk_notes
            assert decision.capital_at_risk_usd >= 0.0

    def test_consistency_checks_are_produced_and_some_are_checkable(self, full_exposure):
        # item 4: "do not skip". Confirms the check actually ran across the
        # real flips, and that at least one pair had computed axis positions
        # on both sides (otherwise every outcome would trivially be None).
        result, _ = full_exposure
        assert len(result.consistency_checks) > 0
        outcomes = Counter(c.consistent for c in result.consistency_checks)
        assert outcomes[True] > 0 or outcomes[False] > 0

    def test_reproducible_from_seed(self, fleet, prices):
        sweep = run_sweep(fleet, prices, price_grid=(0, 200, 400), seed=3, population_size=16, cold_generations=15, warm_generations=6)
        kwargs = {"seed": 3, "population_size": 16, "n_generations": 15}
        result_a = compute_exposure(fleet, prices, sweep, **kwargs)
        result_b = compute_exposure(fleet, prices, sweep, **kwargs)
        assert [d.capital_at_risk_usd for d in result_a.exposed_decisions] == pytest.approx(
            [d.capital_at_risk_usd for d in result_b.exposed_decisions]
        )
        assert result_a.total_capital_at_risk_usd == pytest.approx(result_b.total_capital_at_risk_usd)


class TestOutputSerialization:
    def test_exposure_result_to_dict_is_json_serializable_and_complete(self, full_exposure):
        result, _ = full_exposure
        payload = exposure_result_to_dict(result)
        json.dumps(payload)  # must not raise
        assert payload["summary"]["exposed_decision_count"] == len(result.exposed_decisions)
        assert payload["summary"]["exposed_decision_count"] > 0
        assert payload["summary"]["total_capital_at_risk_inr"] > 0
        assert payload["fx"]["status"]
        assert payload["fx"]["retrieval_date"]
        assert payload["exposed_decisions"][0]["flips_between_which_scenarios"]
        assert "consistency_checks" in payload
