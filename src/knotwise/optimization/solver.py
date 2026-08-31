"""The GA solver (Task 2R component 3, item 5) — wires the DEAP-independent
genome/objective/constraint modules (items 1-4) into a DEAP toolbox and runs
the evolutionary loop that turns them into an actual fleet plan.

DEAP owns exactly what it's good at here: the `Fitness`/`Individual`
bookkeeping and `HallOfFame` tracking. Selection, crossover, and mutation stay
on `genome.py`'s own explicit-`random.Random` operators rather than DEAP's
global-`random`-module equivalents (`tools.selTournament`,
`algorithms.eaSimple`'s `varAnd`) — `genome.py` was built "DEAP-independent by
design" specifically so every source of randomness in a run is threaded
through one seeded `random.Random` instance, and mixing in DEAP's
global-state operators here would quietly break that guarantee.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from deap import base, creator, tools

from knotwise.optimization.genome import Genome, crossover_genomes, mutate_genome, random_genome
from knotwise.optimization.objective import ObjectiveResult, evaluate

# `creator.create` registers a class in `deap.creator`'s module-level
# namespace exactly once per process; guard re-registration since this
# module (and therefore this file) can be imported more than once across a
# test session without erroring on the second import.
if not hasattr(creator, "KnotWiseFitnessMin"):
    creator.create("KnotWiseFitnessMin", base.Fitness, weights=(-1.0,))
if not hasattr(creator, "KnotWiseIndividual"):
    creator.create("KnotWiseIndividual", list, fitness=creator.KnotWiseFitnessMin)


@dataclass(frozen=True)
class SolverResult:
    best_genome: Genome
    best_total_usd: float
    best_breakdown: ObjectiveResult
    generations_run: int


def _clone(individual: creator.KnotWiseIndividual) -> creator.KnotWiseIndividual:
    """A fresh individual with the same genes and a fresh (invalid) fitness.

    `VesselYearGene` is frozen and neither `crossover_genomes` nor
    `mutate_genome` ever mutates a gene in place, so copying the list
    shallowly (rather than `copy.deepcopy`) is sufficient and cheap.
    """
    return creator.KnotWiseIndividual(individual)


def _tournament_select(
    population: list, n: int, tournament_size: int, rng: random.Random
) -> list:
    """Pick `n` individuals, each the best of `tournament_size` random draws.

    Hand-rolled rather than `deap.tools.selTournament` so selection draws
    from the same seeded `rng` as every other operator in this module (see
    the module docstring) instead of the global `random` module.
    """
    return [
        min(rng.sample(population, tournament_size), key=lambda ind: ind.fitness.values[0])
        for _ in range(n)
    ]


def _build_toolbox(
    fleet: dict[str, Any],
    regulations: dict[str, Any],
    prices: dict[str, Any],
    rng: random.Random,
    tournament_size: int,
) -> base.Toolbox:
    toolbox = base.Toolbox()

    def make_individual() -> creator.KnotWiseIndividual:
        return creator.KnotWiseIndividual(random_genome(fleet, rng))

    def mate(ind1, ind2):
        child_a, child_b = crossover_genomes(list(ind1), list(ind2), rng)
        ind1[:] = child_a
        ind2[:] = child_b
        return ind1, ind2

    def mutate(ind):
        ind[:] = mutate_genome(list(ind), fleet, rng)
        return (ind,)

    def fitness_of(ind) -> tuple[float]:
        return (evaluate(list(ind), fleet, regulations, prices).total_usd,)

    toolbox.register("individual", make_individual)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("clone", _clone)
    toolbox.register("mate", mate)
    toolbox.register("mutate", mutate)
    toolbox.register("select", _tournament_select, tournament_size=tournament_size, rng=rng)
    toolbox.register("evaluate", fitness_of)
    return toolbox


def _seeded_population(
    toolbox: base.Toolbox,
    fleet: dict[str, Any],
    seed_genome: Genome,
    population_size: int,
    rng: random.Random,
) -> list:
    """A warm-started initial population: `seed_genome` itself, a handful of
    its near neighbors (small mutations), and the rest freshly random — a
    genuine head start without collapsing all diversity onto one point (Task
    2R component 4, item 2: "warm-start each solve from the neighboring grid
    point's best genome")."""
    n_neighbors = min(population_size // 4, 10)
    population = [creator.KnotWiseIndividual(seed_genome)]
    population += [
        creator.KnotWiseIndividual(mutate_genome(seed_genome, fleet, rng, n_mutations=3))
        for _ in range(n_neighbors)
    ]
    population += [toolbox.individual() for _ in range(population_size - len(population))]
    return population


def run_ga(
    fleet: dict[str, Any],
    regulations: dict[str, Any],
    prices: dict[str, Any],
    *,
    seed: int = 0,
    population_size: int = 40,
    n_generations: int = 30,
    crossover_prob: float = 0.6,
    mutation_prob: float = 0.3,
    tournament_size: int = 3,
    seed_genome: Genome | None = None,
) -> SolverResult:
    """Evolve a population of genomes to (approximately) minimize total fleet cost.

    Deterministic for a fixed `seed`: every random draw in this run — initial
    population, tournament selection, crossover point, mutation slot/value —
    comes from one `random.Random(seed)` instance, so two calls with the same
    seed (and the same `fleet`/`regulations`/`prices`/`seed_genome`) return an
    identical `SolverResult`.

    Generational replacement (no elitism in the population itself), with a
    `HallOfFame` tracking the best individual seen across every generation —
    the standard way to avoid losing a good solution to an unlucky
    generation's crossover/mutation without also needing to hand-tune which
    individuals survive a generation.

    `seed_genome`, when given, warm-starts the initial population around it
    instead of drawing every individual fresh — pair this with a smaller
    `n_generations` for a cheap re-solve after a small change to the inputs
    (e.g. the next grid point in a carbon-price sweep) rather than a cold
    solve from scratch.
    """
    rng = random.Random(seed)
    toolbox = _build_toolbox(fleet, regulations, prices, rng, tournament_size)

    if seed_genome is not None:
        population = _seeded_population(toolbox, fleet, seed_genome, population_size, rng)
    else:
        population = toolbox.population(n=population_size)
    for individual in population:
        individual.fitness.values = toolbox.evaluate(individual)

    hall_of_fame = tools.HallOfFame(1)
    hall_of_fame.update(population)

    for _ in range(n_generations):
        offspring = [toolbox.clone(ind) for ind in toolbox.select(population, len(population))]

        for child_a, child_b in zip(offspring[::2], offspring[1::2]):
            if rng.random() < crossover_prob:
                toolbox.mate(child_a, child_b)
                del child_a.fitness.values
                del child_b.fitness.values

        for mutant in offspring:
            if rng.random() < mutation_prob:
                toolbox.mutate(mutant)
                del mutant.fitness.values

        for individual in offspring:
            if not individual.fitness.valid:
                individual.fitness.values = toolbox.evaluate(individual)

        population[:] = offspring
        hall_of_fame.update(population)

    best = hall_of_fame[0]
    best_genome = list(best)
    breakdown = evaluate(best_genome, fleet, regulations, prices)
    return SolverResult(
        best_genome=best_genome,
        best_total_usd=breakdown.total_usd,
        best_breakdown=breakdown,
        generations_run=n_generations,
    )
