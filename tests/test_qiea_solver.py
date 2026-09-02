"""Tests for the QIEA solver (`knotwise.optimization.qiea_solver`) —
mirrors `test_solver.py`'s structure so the two solvers are held to the
same bar."""

from __future__ import annotations

import random

import pytest

from knotwise.fleet.loader import load_fleet, load_prices
from knotwise.fleet.model import option_menu_for
from knotwise.optimization.genome import DECISION_FIELDS, VesselYearGene, random_genome
from knotwise.optimization.objective import evaluate
from knotwise.optimization.qiea_solver import (
    _annealed_learning_rate,
    _EliteArchive,
    _mean_field_individual,
    _new_individual,
    _slot_cost_tables,
    _warm_start_population,
    run_qiea,
)
from knotwise.regulatory.scenario_resolution import resolve_regulations_for_scenario


@pytest.fixture(scope="module")
def fleet():
    return load_fleet()


@pytest.fixture(scope="module")
def prices():
    return load_prices()


@pytest.fixture(scope="module")
def regulations():
    return resolve_regulations_for_scenario("approved_text")


class TestReproducibility:
    def test_same_seed_gives_identical_result(self, fleet, regulations, prices):
        kwargs = {"population_size": 10, "n_generations": 5}
        result_a = run_qiea(fleet, regulations, prices, seed=11, **kwargs)
        result_b = run_qiea(fleet, regulations, prices, seed=11, **kwargs)
        assert result_a.best_genome == result_b.best_genome
        assert result_a.best_total_usd == pytest.approx(result_b.best_total_usd)

    def test_different_seeds_can_diverge(self, fleet, regulations, prices):
        kwargs = {"population_size": 10, "n_generations": 5}
        result_a = run_qiea(fleet, regulations, prices, seed=1, **kwargs)
        result_b = run_qiea(fleet, regulations, prices, seed=2, **kwargs)
        assert result_a.best_genome != result_b.best_genome


class TestResultIntegrity:
    def test_best_breakdown_matches_reevaluating_best_genome(self, fleet, regulations, prices):
        result = run_qiea(fleet, regulations, prices, seed=5, population_size=10, n_generations=4)
        reevaluated = evaluate(result.best_genome, fleet, regulations, prices)
        assert result.best_total_usd == pytest.approx(reevaluated.total_usd)
        assert result.best_breakdown.total_usd == pytest.approx(reevaluated.total_usd)

    def test_best_genome_has_one_gene_per_vessel_year(self, fleet, regulations, prices):
        result = run_qiea(fleet, regulations, prices, seed=5, population_size=10, n_generations=4)
        assert len(result.best_genome) == len(fleet["vessels"]) * len(fleet["horizon_years"])


class TestFeasibility:
    """The central invariant of the qubit->qudit generalization: every
    observed value must come from that slot's own `option_menu_for` menu,
    exactly like the GA's genome operators (see `genome.py`'s own
    feasibility-closure docstring)."""

    def test_every_gene_stays_within_its_own_menu(self, fleet, regulations, prices):
        result = run_qiea(fleet, regulations, prices, seed=8, population_size=12, n_generations=8)
        vessels_by_id = {v["vessel_id"]: v for v in fleet["vessels"]}
        for gene in result.best_genome:
            menu = option_menu_for(vessels_by_id[gene.vessel_id], fleet, gene.year)
            assert gene.route_id in menu.routes
            assert gene.fuel_id in menu.fuels
            assert gene.speed_band_index in range(len(menu.speed_bands_knots))
            assert menu.shore_power_available or not gene.shore_power


class TestSearchQuality:
    def test_qiea_beats_the_mean_of_random_genomes(self, fleet, regulations, prices):
        rng = random.Random(99)
        random_totals = [
            evaluate(random_genome(fleet, rng), fleet, regulations, prices).total_usd for _ in range(8)
        ]
        mean_random_total = sum(random_totals) / len(random_totals)

        result = run_qiea(fleet, regulations, prices, seed=99, population_size=24, n_generations=25)
        assert result.best_total_usd < mean_random_total


class TestWarmStart:
    def test_warm_start_biases_a_share_of_the_population_toward_the_seed(self, fleet, regulations, prices):
        """`_warm_start_population`'s actual contract, checked directly and
        deterministically: one individual pulled hard onto the seed plan, a
        quarter of the rest pulled partway, the remainder untouched."""
        seed_genome = run_qiea(
            fleet, regulations, prices, seed=3, population_size=6, n_generations=15
        ).best_genome
        by_slot = {(gene.vessel_id, gene.year): gene for gene in seed_genome}

        def mean_mass_on_seed_values(individual):
            masses = []
            for slot_key, registers in individual.items():
                gene = by_slot[slot_key]
                for field_name, register in registers.items():
                    value = getattr(gene, field_name)
                    masses.append(
                        register.probs[register.domain.index(value)] if value in register.domain else 0.0
                    )
            return sum(masses) / len(masses)

        population = [_new_individual(fleet) for _ in range(20)]
        untouched = mean_mass_on_seed_values(population[0])
        _warm_start_population(population, seed_genome, random.Random(0))

        # int(20 * 0.25) + 1 = 6 biased, so indices 6.. are left alone.
        assert mean_mass_on_seed_values(population[0]) > 0.85  # pulled hard
        assert untouched < mean_mass_on_seed_values(population[5]) < 0.85  # pulled partway
        assert mean_mass_on_seed_values(population[6]) == pytest.approx(untouched)
        assert mean_mass_on_seed_values(population[19]) == pytest.approx(untouched)

    def test_seed_genome_biases_the_solved_plan_toward_it(self, fleet, regulations, prices):
        """The behavioural half: a warm-started run's plan should *agree*
        with the seed plan on more decisions than a cold run's does.

        Agreement, not total cost. An earlier version compared
        `min(warm_totals) <= min(cold_totals)` over five seeds, which stopped
        separating the two once `mean_field_init` gave cold starts an informed
        prior of their own: measured over twelve seeds the warm runs are still
        ahead on the mean, but by a margin a five-seed `min` reads as noise.
        Decision agreement is what "biases toward it" actually means and it
        separates cleanly -- the warm runs' *worst* agreement beats the cold
        runs' *best*.
        """
        seed_genome = run_qiea(
            fleet, regulations, prices, seed=3, population_size=6, n_generations=15
        ).best_genome
        by_slot = {(gene.vessel_id, gene.year): gene for gene in seed_genome}

        def agreement(genome):
            matches = sum(
                getattr(gene, field_name) == getattr(by_slot[(gene.vessel_id, gene.year)], field_name)
                for gene in genome
                for field_name in DECISION_FIELDS
            )
            return matches / (len(genome) * len(DECISION_FIELDS))

        warm = [
            agreement(
                run_qiea(
                    fleet, regulations, prices, seed=s, population_size=6, n_generations=1, seed_genome=seed_genome
                ).best_genome
            )
            for s in range(5)
        ]
        cold = [
            agreement(
                run_qiea(fleet, regulations, prices, seed=s, population_size=6, n_generations=1).best_genome
            )
            for s in range(5)
        ]
        assert min(warm) > max(cold)


class TestMeanFieldInitialization:
    def test_mean_field_init_beats_uniform_init_on_the_raw_search(self, fleet, regulations, prices):
        """The one measured improvement to the *search itself* (round 3).

        Checked with `polish=False`, deliberately: with the coordinate-descent
        polish on, this difference does not survive to the output at all (see
        `outputs/qiea_search_round3.md`), so asserting it end to end would be
        asserting noise. What is real, and what this guards, is that seeding
        each register from its slot's own separable cost table finds a
        markedly better plan than starting uniform.

        The margin is wide enough to assert on the aggregate without being
        flaky: measured over eight seeds the two ranges do not overlap
        (uniform $477.8M-$517.9M, mean-field $411.7M-$453.8M), so a 5%
        threshold on the mean has very large headroom over the ~11% effect.
        """
        settings = {"population_size": 20, "n_generations": 20, "polish": False}
        uniform = [
            run_qiea(fleet, regulations, prices, seed=s, mean_field_init=False, **settings).best_total_usd
            for s in range(4)
        ]
        mean_field = [
            run_qiea(fleet, regulations, prices, seed=s, mean_field_init=True, **settings).best_total_usd
            for s in range(4)
        ]
        uniform_mean = sum(uniform) / len(uniform)
        assert sum(mean_field) / len(mean_field) < uniform_mean * 0.95

    def test_registers_stay_valid_probability_vectors(self, fleet, regulations, prices):
        """A mean-field register is still a genuine distribution over that
        slot's own menu -- the property `_observe` relies on for feasibility."""
        tables = _slot_cost_tables(fleet, regulations, prices, None)
        individual = _mean_field_individual(fleet, tables, temperature_scale=1.0)
        for registers in individual.values():
            for register in registers.values():
                assert len(register.probs) == len(register.domain)
                assert all(probability >= 0.0 for probability in register.probs)
                assert sum(register.probs) == pytest.approx(1.0)


class TestAnnealedLearningRate:
    def test_flat_when_end_is_none(self):
        for generation in (0, 5, 9):
            assert _annealed_learning_rate(0.1, None, generation, 10) == 0.1

    def test_flat_when_only_one_generation(self):
        # Nothing to ramp across -- must not divide by zero.
        assert _annealed_learning_rate(0.1, 0.5, 0, 1) == 0.1

    def test_starts_at_start_and_ends_at_end(self):
        assert _annealed_learning_rate(0.05, 0.45, 0, 10) == pytest.approx(0.05)
        assert _annealed_learning_rate(0.05, 0.45, 9, 10) == pytest.approx(0.45)

    def test_ramps_monotonically_between(self):
        rates = [_annealed_learning_rate(0.05, 0.45, g, 10) for g in range(10)]
        assert rates == sorted(rates)


class TestEliteArchive:
    def _gene(self, vessel_id="A1", year=2026, **overrides):
        base = {
            "vessel_id": vessel_id,
            "year": year,
            "route_id": "r",
            "speed_band_index": 4,
            "fuel_id": "vlsfo",
            "shore_power": False,
            "borrow_election": False,
            "pool_opt_in": False,
        }
        base.update(overrides)
        return VesselYearGene(**base)

    def test_keeps_only_up_to_max_size_entries(self):
        archive = _EliteArchive(max_size=2)
        genomes = [[self._gene(fuel_id=f)] for f in ("vlsfo", "mgo", "lng")]
        archive.offer(genomes, [300.0, 100.0, 200.0])
        assert len(archive.entries) == 2
        assert [total for total, _ in archive.entries] == [100.0, 200.0]

    def test_deduplicates_identical_genomes(self):
        archive = _EliteArchive(max_size=5)
        same_genome = [self._gene(fuel_id="vlsfo")]
        archive.offer([same_genome, list(same_genome)], [100.0, 100.0])
        assert len(archive.entries) == 1

    def test_pick_favors_the_best_ranked_entry_statistically(self):
        archive = _EliteArchive(max_size=3)
        genomes = [[self._gene(fuel_id=f)] for f in ("vlsfo", "mgo", "lng")]
        archive.offer(genomes, [10.0, 20.0, 30.0])  # rank 0 = vlsfo (cheapest)

        rng = random.Random(0)
        picks = [archive.pick(rng) for _ in range(500)]
        vlsfo_count = sum(1 for g in picks if g[0].fuel_id == "vlsfo")
        lng_count = sum(1 for g in picks if g[0].fuel_id == "lng")
        assert vlsfo_count > lng_count  # rank 0 (weight 1) picked more than rank 2 (weight 1/3)

    def test_pick_can_return_any_entry_not_only_the_best(self):
        archive = _EliteArchive(max_size=3)
        genomes = [[self._gene(fuel_id=f)] for f in ("vlsfo", "mgo", "lng")]
        archive.offer(genomes, [10.0, 20.0, 30.0])

        rng = random.Random(1)
        picks = {archive.pick(rng)[0].fuel_id for _ in range(200)}
        assert picks == {"vlsfo", "mgo", "lng"}


class TestPolish:
    def test_polish_true_never_worse_than_polish_false(self, fleet, regulations, prices):
        kwargs = {"seed": 7, "population_size": 10, "n_generations": 8}
        polished = run_qiea(fleet, regulations, prices, polish=True, **kwargs)
        unpolished = run_qiea(fleet, regulations, prices, polish=False, **kwargs)
        assert polished.best_total_usd <= unpolished.best_total_usd + 1e-6

    def test_polish_false_is_respected(self, fleet, regulations, prices):
        # Same seed, same search trajectory either way (polish runs after
        # the search loop and doesn't consume any extra rng draws the
        # search itself depends on) -- only the final genome should differ
        # when polish finds an improvement to make.
        kwargs = {"seed": 2, "population_size": 8, "n_generations": 6}
        polished = run_qiea(fleet, regulations, prices, polish=True, **kwargs)
        unpolished = run_qiea(fleet, regulations, prices, polish=False, **kwargs)
        assert unpolished.best_total_usd >= polished.best_total_usd
