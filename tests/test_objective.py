"""Tests for the composed objective function (Task 2R component 3)."""

import random
from collections import defaultdict

import pytest

from knotwise.fleet.loader import load_fleet, load_prices
from knotwise.fleet.model import speed_bands_knots
from knotwise.optimization.fuel_model import PhysicsFuelModel, sea_days
from knotwise.optimization.genome import random_genome
from knotwise.optimization.objective import evaluate
from knotwise.regulatory.loader import load_regulations


@pytest.fixture(scope="module")
def fleet():
    return load_fleet()


@pytest.fixture(scope="module")
def regulations():
    return load_regulations()


@pytest.fixture(scope="module")
def prices():
    return load_prices()


@pytest.fixture()
def genome(fleet):
    return random_genome(fleet, random.Random(7))


class TestBreakdownIntegrity:
    def test_total_equals_the_sum_of_every_leaf(self, genome, fleet, regulations, prices):
        result = evaluate(genome, fleet, regulations, prices)
        leaf_sum = (
            result.fuel_cost.amount_usd
            + result.opex_cost.amount_usd
            + result.time_cost.amount_usd
            + result.demand_penalty.amount_usd
            + sum(c.amount_usd for c in result.compliance_costs.values())
        )
        assert result.total_usd == pytest.approx(leaf_sum)

    def test_every_leaf_has_a_non_empty_status(self, genome, fleet, regulations, prices):
        result = evaluate(genome, fleet, regulations, prices)
        leaves = [result.fuel_cost, result.opex_cost, result.time_cost, result.demand_penalty, *result.compliance_costs.values()]
        for leaf in leaves:
            assert leaf.status, f"a cost leaf has no status: {leaf}"

    def test_compliance_costs_cover_all_four_regimes(self, genome, fleet, regulations, prices):
        result = evaluate(genome, fleet, regulations, prices)
        assert set(result.compliance_costs.keys()) == {"cii", "eu_ets", "nzf", "fuel_eu"}


class TestDemandConstraint:
    def test_penalty_is_positive_when_a_route_is_unserved(self, fleet, regulations, prices):
        from knotwise.optimization.genome import VesselYearGene

        # Every vessel assigned to a route OTHER than "india_gulf" -> that
        # route-year has zero assigned capacity -> should be penalised.
        genome = []
        for vessel in fleet["vessels"]:
            menu_routes = [r for r, route in fleet["routes"].items() if route["band"] == vessel["band"]]
            chosen_route = next((r for r in menu_routes if r != "india_gulf"), menu_routes[0])
            for year in fleet["horizon_years"]:
                genome.append(
                    VesselYearGene(
                        vessel_id=vessel["vessel_id"],
                        year=year,
                        route_id=chosen_route,
                        speed_band_index=4,
                        fuel_id="vlsfo" if "vlsfo" in fleet["engine_fuel_compatibility"]["matrix"][vessel["engine_type"]] else fleet["engine_fuel_compatibility"]["matrix"][vessel["engine_type"]][0],
                        shore_power=False,
                        borrow_election=False,
                        pool_opt_in=False,
                    )
                )
        result = evaluate(genome, fleet, regulations, prices)
        assert result.demand_penalty.amount_usd > 0

    def test_penalty_is_zero_when_min_capacity_is_met(self, fleet, regulations, prices):
        from knotwise.optimization.genome import VesselYearGene

        # Every route needs at least one vessel-worth of DWT assigned to it,
        # every year, to clear its demand floor (fleet.json's
        # min_capacity_dwt_required is set to exactly one vessel-worth per
        # route). Round-robin each band's vessels across that band's routes
        # so every route gets covered rather than funnelling the whole band
        # onto a single route and starving the rest of it.
        genome = []
        band_vessel_counters: dict[str, int] = defaultdict(int)
        for vessel in fleet["vessels"]:
            band_routes = [r for r, route in fleet["routes"].items() if route["band"] == vessel["band"]]
            route_id = band_routes[band_vessel_counters[vessel["band"]] % len(band_routes)]
            band_vessel_counters[vessel["band"]] += 1
            for year in fleet["horizon_years"]:
                genome.append(
                    VesselYearGene(
                        vessel_id=vessel["vessel_id"],
                        year=year,
                        route_id=route_id,
                        speed_band_index=4,
                        fuel_id=fleet["engine_fuel_compatibility"]["matrix"][vessel["engine_type"]][0],
                        shore_power=False,
                        borrow_election=False,
                        pool_opt_in=False,
                    )
                )
        result = evaluate(genome, fleet, regulations, prices)
        assert result.demand_penalty.amount_usd == pytest.approx(0.0)


class TestSpeedTradeOff:
    def test_total_cost_has_an_interior_optimum_not_a_monotonic_edge(self, fleet, prices):
        # The actual point of Task 2R component 3 correction 2: fuel cost (V²,
        # increasing in speed) and time cost (charter premium x sea_days,
        # decreasing in speed) must trade off to a genuine interior minimum —
        # not park at either extreme, which is what the earlier (degenerate)
        # fixed-sea-days model would have done.
        model = PhysicsFuelModel()
        vessel = next(v for v in fleet["vessels"] if v["band"] == "A")
        route_id = vessel["default_route"]
        defaults = fleet["vessel_class_defaults"]["A"]
        fuel_price = prices["fuels"]["vlsfo"]["price_usd_per_tonne"]

        speeds = speed_bands_knots(defaults["design_speed_knots"])
        totals = []
        for speed in speeds:
            tonnes = model.fuel_consumption_tonnes(vessel, fleet, 2028, speed, "vlsfo", route_id)
            days = sea_days(fleet, route_id, speed)
            totals.append(tonnes * fuel_price + days * defaults["charter_premium_usd_per_sea_day"])

        cheapest_index = totals.index(min(totals))
        assert 0 < cheapest_index < len(totals) - 1, (
            f"expected an interior optimum, got cheapest at index {cheapest_index} of {len(totals)}: {totals}"
        )
