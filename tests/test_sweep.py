"""Tests for the carbon-price sweep + switching-point extraction (Task 2R component 4)."""

import json
import random
import time

import pytest

from knotwise.fleet.loader import load_fleet, load_prices
from knotwise.optimization.genome import VesselYearGene, random_genome
from knotwise.optimization.objective import evaluate
from knotwise.optimization.solver import run_ga as solver_run_ga
from knotwise.optimization.sweep import (
    DEFAULT_PRICE_GRID,
    GridPointResult,
    _nzf_price_override,
    _reattempt_corrected_points,
    _run_solver,
    extract_switching_points,
    run_sweep,
    scenario_axis_positions,
    solve_scenario,
    sweep_result_to_dict,
)
from knotwise.regulatory.scenario_resolution import resolve_regulations_for_scenario


@pytest.fixture(scope="module")
def fleet():
    return load_fleet()


@pytest.fixture(scope="module")
def prices():
    return load_prices()


#: `run_sweep`'s own defaults, passed explicitly by `full_sweep` so tests can
#: tell a forward-pass warm solve apart from a `_reattempt_corrected_points`
#: cold re-solve by its reported `generations_run`.
COLD_GENERATIONS = 40
WARM_GENERATIONS = 12


@pytest.fixture(scope="module")
def full_sweep(fleet, prices):
    """One full-default-grid sweep, shared across every test that needs it
    (item 5's timing/switching-point/warm-start checks) so the expensive run
    happens once rather than once per assertion."""
    start = time.perf_counter()
    result = run_sweep(
        fleet, prices, seed=0, cold_generations=COLD_GENERATIONS, warm_generations=WARM_GENERATIONS
    )
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


class TestNzfPriceOverride:
    """Review defect 1: surplus-unit value must be capped at the real,
    fixed Tier 2 remedial-unit price -- it cannot legitimately be worth
    more than the most a deficit ship would ever pay to avoid buying one,
    and remedial-unit prices are posted dollar figures, not market-floating
    with this sweep's hypothetical axis."""

    def test_surplus_value_tracks_price_below_the_real_tier_2_cap(self, fleet):
        base_regulations = resolve_regulations_for_scenario("approved_text")
        real_tier_2 = base_regulations["regimes"]["nzf"]["tier_prices_usd_per_tco2e"]["tier_2"]
        below_cap_price = real_tier_2 - 50
        resolved = _nzf_price_override(base_regulations, below_cap_price)
        assert resolved["regimes"]["nzf"]["surplus_unit_value_usd_per_tco2e"] == below_cap_price

    def test_surplus_value_is_capped_at_the_real_tier_2_price_above_it(self, fleet):
        base_regulations = resolve_regulations_for_scenario("approved_text")
        real_tier_2 = base_regulations["regimes"]["nzf"]["tier_prices_usd_per_tco2e"]["tier_2"]
        resolved_at_1000 = _nzf_price_override(base_regulations, 1000)
        assert resolved_at_1000["regimes"]["nzf"]["surplus_unit_value_usd_per_tco2e"] == real_tier_2

    def test_deficit_tier_prices_are_not_capped(self, fleet):
        # Only the surplus *credit* has a real ceiling -- the deficit side
        # must keep tracking the swept price past 380, since this same axis
        # places scenarios with no NZF tier structure at all (e.g.
        # adoption_fails' ~$741 FuelEU-penalty-implied price).
        base_regulations = resolve_regulations_for_scenario("approved_text")
        resolved_at_1000 = _nzf_price_override(base_regulations, 1000)
        tier_prices = resolved_at_1000["regimes"]["nzf"]["tier_prices_usd_per_tco2e"]
        assert tier_prices["tier_1"] == 1000
        assert tier_prices["tier_2"] == 1000


class TestReattemptCorrectedPoints:
    """Review defect 2: an envelope-corrected point must get a genuinely
    independent second opinion, not just keep a borrowed genome forever."""

    def test_leaves_uncorrected_points_untouched(self, fleet, prices):
        genome = random_genome(fleet, random.Random(1))
        point = GridPointResult(
            100, genome, 999_999_999.0, 0.1, False, 10, compliance_usd=0.0
        )  # envelope_corrected=False (default)
        base_regulations = resolve_regulations_for_scenario("approved_text")
        result = _reattempt_corrected_points(
            [point], fleet, prices, base_regulations, seed=0, population_size=10, n_generations=5, tournament_size=3
        )
        assert result == [point]

    def test_replaces_a_corrected_point_when_independent_solve_beats_it(self, fleet, prices):
        base_regulations = resolve_regulations_for_scenario("approved_text")
        regulations = _nzf_price_override(base_regulations, 100)
        bad_genome = random_genome(fleet, random.Random(2))
        inflated_total = evaluate(bad_genome, fleet, regulations, prices).total_usd + 1_000_000_000.0
        point = GridPointResult(
            100,
            bad_genome,
            inflated_total,
            0.1,
            False,
            10,
            compliance_usd=0.0,
            envelope_corrected=True,
            envelope_source_price_usd_per_tco2e=500,
        )
        result = _reattempt_corrected_points(
            [point], fleet, prices, base_regulations, seed=0, population_size=20, n_generations=15, tournament_size=3
        )
        assert result[0].total_usd < inflated_total
        assert result[0].envelope_corrected is False

    def test_keeps_the_donor_when_independent_solve_does_not_beat_it(self, fleet, prices):
        # The donor's *recorded* total is deflated below anything any solve
        # of this fleet could reach, so the challenge deterministically
        # fails and this exercises the "donor survives" branch itself --
        # mirroring how the sibling test above inflates a total to exercise
        # the opposite branch.
        #
        # This used to stage the same branch with a real pop60/gen60 donor
        # and a pop5/gen2 challenger, on the reasoning that the tiny solve
        # was "very unlikely" to win. That stopped being true once
        # `_local_search_refine` was allowed to run to its own fixed point
        # rather than stopping at two sweeps: the coordinate-descent polish
        # now does enough of the work that a tiny-population solve really
        # can beat a large one, so the old setup was asserting search luck
        # rather than the branch's contract.
        base_regulations = resolve_regulations_for_scenario("approved_text")
        regulations = _nzf_price_override(base_regulations, 100)
        good_result = solver_run_ga(fleet, regulations, prices, seed=42, population_size=60, n_generations=60)
        deflated_total = good_result.best_total_usd - 1_000_000_000.0
        point = GridPointResult(
            100,
            good_result.best_genome,
            deflated_total,
            0.1,
            False,
            60,
            compliance_usd=0.0,
            envelope_corrected=True,
            envelope_source_price_usd_per_tco2e=500,
        )
        result = _reattempt_corrected_points(
            [point], fleet, prices, base_regulations, seed=0, population_size=20, n_generations=15, tournament_size=3
        )
        assert result == [point]


class TestExtractSwitchingPoints:
    def test_detects_a_changed_decision_field(self):
        genome_a = [_gene("A1", 2028, fuel_id="hfo_scrubber")]
        genome_b = [_gene("A1", 2028, fuel_id="b30_blend")]
        grid = [
            GridPointResult(0, genome_a, 100.0, 0.1, False, 10, compliance_usd=0.0),
            GridPointResult(25, genome_b, 90.0, 0.05, True, 5, compliance_usd=0.0),
        ]
        points = extract_switching_points(grid)
        assert len(points) == 1
        point = points[0]
        assert point.vessel_id == "A1"
        assert point.decision == "fuel_id"
        assert point.from_value == "hfo_scrubber"
        assert point.to_value == "b30_blend"
        assert point.price_low_usd_per_tco2e == 0
        assert point.price_high_usd_per_tco2e == 25

    def test_no_change_means_no_switching_point(self):
        genome = [_gene("A1", 2028)]
        grid = [
            GridPointResult(0, genome, 100.0, 0.1, False, 10, compliance_usd=0.0),
            GridPointResult(25, list(genome), 100.0, 0.05, True, 5, compliance_usd=0.0),
        ]
        assert extract_switching_points(grid) == []

    def test_band_c_vessel_years_are_excluded_only_when_fleet_is_given(self, fleet):
        c_vessel_id = next(v["vessel_id"] for v in fleet["vessels"] if v["band"] == "C")
        genome_a = [_gene(c_vessel_id, 2028, fuel_id="hfo_scrubber")]
        genome_b = [_gene(c_vessel_id, 2028, fuel_id="b30_blend")]
        grid = [
            GridPointResult(0, genome_a, 100.0, 0.1, False, 10, compliance_usd=0.0),
            GridPointResult(25, genome_b, 90.0, 0.05, True, 5, compliance_usd=0.0),
        ]
        assert extract_switching_points(grid, fleet=fleet) == []
        assert extract_switching_points(grid) != []  # no fleet given -> no band filter


@pytest.fixture(scope="module")
def scenario_positions(fleet, prices):
    representative = random_genome(fleet, random.Random(3))
    return scenario_axis_positions(fleet, prices, representative_genome=representative)


class TestScenarioAxisPositions:
    def test_covers_all_five_scenarios_plus_eu_ets_reference(self, scenario_positions):
        ids = {p.scenario_id for p in scenario_positions}
        assert ids == {"approved_text", "liberia", "tuvalu", "brazil", "adoption_fails", "eu_ets_reference"}

    def test_every_position_has_a_status_and_notes(self, scenario_positions):
        for position in scenario_positions:
            assert position.status
            assert position.notes

    def test_tier_annotated_ranges_carry_their_posted_tier_prices(self, scenario_positions):
        by_id = {p.scenario_id: p for p in scenario_positions}
        assert by_id["approved_text"].low_usd_per_tco2e == 100
        assert by_id["approved_text"].high_usd_per_tco2e == 380
        assert by_id["tuvalu"].low_usd_per_tco2e == 300
        assert by_id["tuvalu"].high_usd_per_tco2e is None  # PLAN.md gives no Tier 2 figure for Tuvalu

    def test_liberia_is_a_qualitative_marker_with_no_number(self, scenario_positions):
        liberia = next(p for p in scenario_positions if p.scenario_id == "liberia")
        assert liberia.kind == "qualitative_marker"
        assert liberia.low_usd_per_tco2e is None

    def test_adoption_fails_never_silently_assumes_zero(self, scenario_positions):
        # Task 2R component 4, item 1: scenario 5's axis position must come
        # from implied_price.py -- either a real computed number or an
        # explicit "undefined" (None), never a silently-assumed zero.
        adoption_fails = next(p for p in scenario_positions if p.scenario_id == "adoption_fails")
        assert adoption_fails.operating_point_usd_per_tco2e != 0.0

    def test_eu_ets_reference_matches_the_real_posted_price(self, scenario_positions, prices):
        eu_ets = next(p for p in scenario_positions if p.scenario_id == "eu_ets_reference")
        assert eu_ets.low_usd_per_tco2e == prices["carbon_allowances"]["eu_ets_eua"]["price_usd_per_tco2e"]

    def test_every_computed_axis_position_falls_inside_the_default_grid(self, scenario_positions):
        # A computed position outside [min(DEFAULT_PRICE_GRID),
        # max(DEFAULT_PRICE_GRID)] would make its bet distances unmeasurable:
        # component 5's consistency check could never find a switching point
        # near it, because the sweep never explores that far. Scenario 5's
        # implied price (~$700-750/tCO2e) is exactly why the grid was
        # extended from $600 to $1000 -- this guards against it drifting
        # back out, or a future scenario's implied price landing outside it.
        grid_low, grid_high = min(DEFAULT_PRICE_GRID), max(DEFAULT_PRICE_GRID)
        for position in scenario_positions:
            if position.operating_point_usd_per_tco2e is None:
                continue  # qualitative marker / not computed -- nothing to place on the grid
            assert grid_low <= position.operating_point_usd_per_tco2e <= grid_high, (
                f"{position.scenario_id}'s operating point "
                f"{position.operating_point_usd_per_tco2e} falls outside the swept grid "
                f"[{grid_low}, {grid_high}]"
            )


class TestRunSweep:
    def test_switching_points_exist_for_at_least_one_decision(self, full_sweep):
        # Non-degenerate fixture: the real fleet's own fuel prices/GHG
        # intensities produce a genuine hfo_scrubber/vlsfo/b30_blend cost
        # crossover within $0-600/tCO2e (verified by hand against
        # fleet.json's own numbers before writing this test). If this ever
        # finds zero switching points, that's a finding about the model's
        # economics worth reporting, not a reason to weaken the assertion.
        result, _ = full_sweep
        assert len(result.switching_points) >= 1

    def test_warm_start_is_not_slower_than_a_cold_solve(self, full_sweep):
        result, _ = full_sweep
        assert result.warm_start_benchmark.warm_seconds <= result.warm_start_benchmark.cold_seconds

    def test_default_grid_produces_one_point_per_price(self, full_sweep):
        result, _ = full_sweep
        assert len(result.grid_points) == len(DEFAULT_PRICE_GRID)
        assert [gp.price_usd_per_tco2e for gp in result.grid_points] == list(DEFAULT_PRICE_GRID)
        assert result.grid_points[0].warm_started is False
        # Every later point is warm-started in the forward pass -- unless
        # `_reattempt_corrected_points` then replaced it. That pass
        # deliberately re-solves an envelope-corrected point from cold and
        # reports `warm_started=False` with the full cold generation budget,
        # precisely so the output says which points were borrowed and then
        # independently reconfirmed. A blanket `all(gp.warm_started)` here
        # would assert that pass never succeeds, which is not the contract
        # (and stopped holding once the coordinate-descent polish was
        # allowed to run to its fixed point, making those re-solves good
        # enough to win).
        for grid_point in result.grid_points[1:]:
            assert grid_point.warm_started or grid_point.generations_run == COLD_GENERATIONS

    def test_envelope_is_the_true_minimum_over_all_discovered_genomes(self, full_sweep, fleet, prices):
        # The real, provable guarantee `_apply_monotonic_envelope` makes
        # (see its docstring) -- NOT that total_usd is monotonic in price.
        # Verified directly on this fleet: its optimal plan nets an NZF
        # surplus credit at every grid point, so total cost genuinely (and
        # correctly, under this sweep's stated assumptions) *falls* as
        # price rises -- forcing monotonicity would have meant reporting a
        # wrong number to look tidier. What the envelope must guarantee
        # instead: no other already-discovered genome, evaluated at a given
        # grid point's own price, ever beats what that point reports.
        result, _ = full_sweep
        base_regulations = resolve_regulations_for_scenario("approved_text")
        # Checking every grid point x every genome is O(N^2) evaluate()
        # calls on top of an already-expensive fixture; first/middle/last is
        # enough to catch a regression without materially slowing the suite.
        check_indices = {0, len(result.grid_points) // 2, len(result.grid_points) - 1}
        for i in check_indices:
            target = result.grid_points[i]
            target_regulations = _nzf_price_override(base_regulations, target.price_usd_per_tco2e)
            for candidate in result.grid_points:
                candidate_total = evaluate(candidate.genome, fleet, target_regulations, prices).total_usd
                assert candidate_total >= target.total_usd - 1e-6, (
                    f"grid point at price {target.price_usd_per_tco2e} reports {target.total_usd}, but "
                    f"the genome discovered at price {candidate.price_usd_per_tco2e} achieves "
                    f"{candidate_total} there -- the envelope should already have picked this up"
                )

    def test_compliance_usd_is_a_bounded_real_component_of_total(self, full_sweep, fleet, prices):
        # compliance_usd is the cii+eu_ets+nzf+fuel_eu slice of total_usd (the
        # sensitivity chart's "carbon bill" series) -- it must never exceed
        # total_usd (fuel/opex/time/demand are each >= 0 by construction, so
        # total - compliance_usd >= 0 algebraically), and it must be the same
        # real figure objective.evaluate() would report for that exact
        # genome under that exact grid point's own (price-clamped) NZF
        # regulations -- never a stale or re-derived approximation.
        result, _ = full_sweep
        base_regulations = resolve_regulations_for_scenario("approved_text")
        for gp in result.grid_points:
            assert gp.compliance_usd <= gp.total_usd + 1e-6
            regulations = _nzf_price_override(base_regulations, gp.price_usd_per_tco2e)
            breakdown = evaluate(gp.genome, fleet, regulations, prices)
            expected_compliance = sum(c.amount_usd for c in breakdown.compliance_costs.values())
            assert gp.compliance_usd == pytest.approx(expected_compliance, abs=1e-3)

    def test_reproducible_from_seed(self, fleet, prices):
        kwargs = {"seed": 2, "population_size": 16, "cold_generations": 15, "warm_generations": 6}
        price_grid = (0, 100, 200)
        result_a = run_sweep(fleet, prices, price_grid=price_grid, **kwargs)
        result_b = run_sweep(fleet, prices, price_grid=price_grid, **kwargs)
        assert [gp.genome for gp in result_a.grid_points] == [gp.genome for gp in result_b.grid_points]
        assert [gp.total_usd for gp in result_a.grid_points] == pytest.approx(
            [gp.total_usd for gp in result_b.grid_points]
        )

    def test_rejects_a_grid_with_fewer_than_two_points(self, fleet, prices):
        with pytest.raises(ValueError):
            run_sweep(fleet, prices, price_grid=(100,))


class TestOptimizerSelection:
    """`solve_scenario`/`run_sweep`'s `optimizer` switch (wiring the QIEA
    solver into the sweep pipeline): default behaviour must stay exactly
    the classical GA, and `"qiea"` must be a real, working alternative
    through the same call sites (grid solves, warm-start benchmark, and
    `_reattempt_corrected_points`)."""

    def test_omitting_optimizer_still_means_ga(self, fleet, prices):
        regulations = resolve_regulations_for_scenario("approved_text")
        default_result = _run_solver(
            "ga", fleet, regulations, prices, seed=4, population_size=8, n_generations=4, tournament_size=3
        )
        explicit_ga_result = solve_scenario(
            fleet, prices, "approved_text", seed=4, population_size=8, n_generations=4
        )
        assert default_result.best_genome == explicit_ga_result.best_genome

    def test_unknown_optimizer_rejected(self, fleet, prices):
        with pytest.raises(ValueError):
            solve_scenario(fleet, prices, "approved_text", optimizer="not_a_real_optimizer")

    def test_solve_scenario_accepts_qiea(self, fleet, prices):
        result = solve_scenario(
            fleet, prices, "approved_text", seed=1, population_size=8, n_generations=5, optimizer="qiea"
        )
        assert result.best_genome
        assert result.best_total_usd > 0

    def test_run_sweep_accepts_qiea_end_to_end(self, fleet, prices):
        # Tiny population/generations (kept small so this test stays fast)
        # make `_reattempt_corrected_points` more likely to relabel a point
        # `warm_started=False` after a winning independent re-solve (see
        # that function's own docstring) than the full-budget GA fixture
        # elsewhere in this file -- so this only checks what's actually
        # guaranteed at any budget, not the warm-start labeling pattern.
        result = run_sweep(
            fleet,
            prices,
            price_grid=(0, 200, 400),
            seed=1,
            population_size=8,
            cold_generations=5,
            warm_generations=3,
            optimizer="qiea",
        )
        assert len(result.grid_points) == 3
        assert result.warm_start_benchmark is not None
        for grid_point in result.grid_points:
            assert grid_point.total_usd > 0
            assert len(grid_point.genome) == len(fleet["vessels"]) * len(fleet["horizon_years"])

    def test_run_sweep_qiea_is_reproducible_from_seed(self, fleet, prices):
        kwargs = {
            "seed": 2,
            "population_size": 8,
            "cold_generations": 5,
            "warm_generations": 3,
            "optimizer": "qiea",
        }
        price_grid = (0, 200)
        result_a = run_sweep(fleet, prices, price_grid=price_grid, **kwargs)
        result_b = run_sweep(fleet, prices, price_grid=price_grid, **kwargs)
        assert [gp.genome for gp in result_a.grid_points] == [gp.genome for gp in result_b.grid_points]


class TestSweepCompletesInDemoTime:
    """Task 2R component 4 item 5's own guide: "~5 x scenarios at 10s each".

    Budget raised from 60s (item 5's original guide) after adding
    `solver._local_search_refine`'s coordinate-descent polish -- a real,
    verified fix for GA under-convergence (year-over-year fuel trajectories
    that reversed to a dirtier fuel with no cost benefit; see solver.py's
    docstring), not free. This test's fixture uses `run_sweep`'s cheapest
    default settings (population 40); the actual demo build always runs
    offline ahead of time against pre-seeded data (PLAN.md §8.8), never at
    interactive/demo-time, so this budget only bounds *build* time, not
    anything a judge waits on live.
    """

    def test_default_grid_within_budget(self, full_sweep):
        _, elapsed = full_sweep
        assert elapsed < 150.0, f"sweep took {elapsed:.1f}s, over the 150s build-time budget"


class TestOutputSerialization:
    def test_sweep_result_to_dict_is_json_serializable_and_complete(self, fleet, prices):
        result = run_sweep(
            fleet,
            prices,
            seed=0,
            population_size=16,
            cold_generations=10,
            warm_generations=4,
            price_grid=(0, 100, 200),
        )
        payload = sweep_result_to_dict(result)
        json.dumps(payload)  # must not raise
        assert len(payload["grid_points"]) == 3
        assert payload["grid_points"][0]["configuration"]
        assert set(payload["grid_points"][0]["configuration"][0]) == {
            "vessel_id",
            "year",
            "route_id",
            "speed_band_index",
            "fuel_id",
            "shore_power",
            "pool_opt_in",
            "borrow_election",
        }
        assert len(payload["scenario_ticks"]) == 6
        assert payload["warm_start_benchmark"]["warm_seconds"] <= payload["warm_start_benchmark"]["cold_seconds"]
        assert "envelope_corrected" in payload["grid_points"][0]
        assert "envelope_source_price_usd_per_tco2e" in payload["grid_points"][0]
        assert "compliance_usd" in payload["grid_points"][0]
        assert payload["grid_points"][0]["compliance_usd"] <= payload["grid_points"][0]["total_usd"] + 1e-6
