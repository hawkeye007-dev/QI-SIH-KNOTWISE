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
from dataclasses import dataclass, replace
from typing import Any

from deap import base, creator, tools

from knotwise.fleet.model import OptionMenu, option_menu_for
from knotwise.optimization.constraints import allowed_speed_band_indices
from knotwise.optimization.genome import (
    DECISION_FIELDS,
    Genome,
    VesselYearGene,
    crossover_genomes,
    field_domains,
    mutate_genome,
    random_genome,
)
from knotwise.optimization.objective import ObjectiveCache, ObjectiveResult, evaluate

# `creator.create` registers a class in `deap.creator`'s module-level
# namespace exactly once per process; guard re-registration since this
# module (and therefore this file) can be imported more than once across a
# test session without erroring on the second import.
if not hasattr(creator, "KnotWiseFitnessMin"):
    creator.create("KnotWiseFitnessMin", base.Fitness, weights=(-1.0,))
if not hasattr(creator, "KnotWiseIndividual"):
    creator.create("KnotWiseIndividual", list, fitness=creator.KnotWiseFitnessMin)


#: Two plans whose totals differ by less than this are the *same* plan
#: priced twice, not a real economic difference. Calibrated against this
#: model, not guessed: sweeping every single-field change of a solved
#: genome, the cost deltas fall into two disjoint clusters -- 89 of 585
#: candidates land below 1e-6 USD (exactly cost-neutral, and every one of
#: them a `pool_opt_in` or `borrow_election` bit on a vessel-year with no
#: FuelEU balance to pool or bank), and the next cheapest is over $1000.
#: Nine orders of magnitude of clear water, so this threshold cannot
#: swallow a real switch.
DEGENERATE_COST_TOLERANCE_USD = 1e-6


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
    cache: ObjectiveCache,
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
        return (evaluate(list(ind), fleet, regulations, prices, cache=cache).total_usd,)

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


def _gene_field_candidates(gene: VesselYearGene, menu: OptionMenu) -> list[VesselYearGene]:
    """Every single-field variant of `gene` reachable within its own valid
    menu -- one field changed at a time, everything else held fixed. Used
    by `_local_search_refine`'s coordinate descent, not by the GA itself."""
    candidates: list[VesselYearGene] = []
    for fuel_id in menu.fuels:
        if fuel_id != gene.fuel_id:
            candidates.append(replace(gene, fuel_id=fuel_id))
    for index in allowed_speed_band_indices(len(menu.speed_bands_knots)):
        if index != gene.speed_band_index:
            candidates.append(replace(gene, speed_band_index=index))
    for route_id in menu.routes:
        if route_id != gene.route_id:
            candidates.append(replace(gene, route_id=route_id))
    if menu.shore_power_available:
        candidates.append(replace(gene, shore_power=not gene.shore_power))
    candidates.append(replace(gene, pool_opt_in=not gene.pool_opt_in))
    candidates.append(replace(gene, borrow_election=not gene.borrow_election))
    return candidates


def _local_search_refine(
    genome: Genome,
    fleet: dict[str, Any],
    regulations: dict[str, Any],
    prices: dict[str, Any],
    rng: random.Random,
    *,
    max_sweeps: int = 6,
    reference_genome: Genome | None = None,
    cache: ObjectiveCache | None = None,
) -> tuple[Genome, float]:
    """Coordinate-descent polish over the GA's output: visit every
    vessel-year slot (in a shuffled order, using the same seeded `rng` as
    everything else in this module) and try every single-field variant of
    it (`_gene_field_candidates`), holding every other slot fixed, keeping
    whichever variant strictly lowers total cost. Repeat until a full sweep
    makes no improvement, or `max_sweeps` is reached.

    `max_sweeps` is a safety cap, not the intended stopping rule -- the
    descent normally converges (a sweep with no improvement) well inside it.
    It was 2, chosen when a full sweep was expensive; `objective.ObjectiveCache`
    made `evaluate` ~4.6x cheaper for exactly this access pattern (one field
    changed at a time), so the cap is now high enough that the descent
    actually reaches its own fixed point instead of being cut off mid-way.

    Why this exists: on this fleet, a population/generation-bounded GA over
    a ~50-slot genome verifiably leaves individual slots at a locally
    suboptimal value even when the population's fitness looks converged --
    a vessel's own year-over-year fuel choice could reverse toward a
    dirtier fuel with no cost benefit, purely because the GA's crossover/
    mutation never happened to try the strictly-better single-slot swap for
    that one vessel-year. This is not a new search over the whole genome:
    it is an exhaustive check of "does any one-slot change help," applied
    slot by slot until none does. Cheap -- `evaluate()` calls only, no GA
    -- and every candidate comes from that slot's own `option_menu_for`
    menu, so it can never introduce an infeasible value.

    `reference_genome`, when given, adds a final **canonicalization** pass
    once the descent has converged: any field whose value could be set back
    to the reference plan's value without changing total cost by more than
    `DEGENERATE_COST_TOLERANCE_USD` is set back. This does not search and
    cannot make the plan worse -- it only picks, among plans this model
    prices *identically*, the one closest to a stated reference.

    Why that matters, concretely: on this fleet 89 of the 585 single-field
    changes off a solved genome are exactly cost-neutral, and they are
    entirely `pool_opt_in`/`borrow_election` bits on vessel-years with no
    FuelEU balance for them to act on. Left arbitrary, those ~89 free bits
    are re-rolled by every independent solve, so a sweep's adjacent grid
    points disagree on them for no economic reason at all -- and
    `sweep.extract_switching_points`, which diffs adjacent genomes, reports
    each disagreement as a switching point. That is the dominant source of
    the "is this real signal or search noise?" problem `run_sweep`'s own
    docstring already warns about. Canonicalizing against the neighbouring
    grid point's plan removes exactly that noise and nothing else: a field
    the price genuinely moved differs by far more than the tolerance and is
    left where the search put it.
    """
    vessels_by_id = {v["vessel_id"]: v for v in fleet["vessels"]}
    genome = list(genome)
    current_total = evaluate(genome, fleet, regulations, prices, cache=cache).total_usd

    slot_order = list(range(len(genome)))
    for _ in range(max_sweeps):
        improved_this_sweep = False
        rng.shuffle(slot_order)
        for i in slot_order:
            gene = genome[i]
            vessel = vessels_by_id[gene.vessel_id]
            menu = option_menu_for(vessel, fleet, gene.year)
            best_gene = gene
            best_total = current_total
            for candidate_gene in _gene_field_candidates(gene, menu):
                trial = genome[:i] + [candidate_gene] + genome[i + 1 :]
                total = evaluate(trial, fleet, regulations, prices, cache=cache).total_usd
                if total < best_total - 1e-6:
                    best_total = total
                    best_gene = candidate_gene
            if best_gene is not gene:
                genome[i] = best_gene
                current_total = best_total
                improved_this_sweep = True
        if not improved_this_sweep:
            break

    if reference_genome is not None:
        genome, current_total = _canonicalize_against(
            genome, reference_genome, current_total, fleet, regulations, prices, cache
        )
    return genome, current_total


def _canonicalize_against(
    genome: Genome,
    reference_genome: Genome,
    current_total: float,
    fleet: dict[str, Any],
    regulations: dict[str, Any],
    prices: dict[str, Any],
    cache: ObjectiveCache | None,
) -> tuple[Genome, float]:
    """Revert every cost-neutral difference from `reference_genome` (see
    `_local_search_refine`'s docstring for why). Field by field rather than
    whole-gene, so a slot that differs in one decisive field and one
    degenerate one keeps the decisive value and canonicalizes the other.

    Values are checked against the slot's own `field_domains` before being
    adopted, so a reference genome built for a different fleet can never
    introduce an infeasible value here.
    """
    vessels_by_id = {v["vessel_id"]: v for v in fleet["vessels"]}
    reference_by_slot = {(gene.vessel_id, gene.year): gene for gene in reference_genome}
    genome = list(genome)

    for i, gene in enumerate(genome):
        reference_gene = reference_by_slot.get((gene.vessel_id, gene.year))
        if reference_gene is None or reference_gene == gene:
            continue
        domains = field_domains(vessels_by_id[gene.vessel_id], fleet, gene.year)
        # `current` accumulates this slot's accepted reverts across fields --
        # deliberately not `gene`, which goes stale the moment the first field
        # is accepted. Reverting each field off `gene` instead would silently
        # discard every earlier revert at the same slot.
        current = gene
        for field_name in DECISION_FIELDS:
            reference_value = getattr(reference_gene, field_name)
            if getattr(current, field_name) == reference_value:
                continue
            if reference_value not in domains[field_name]:
                continue
            candidate = replace(current, **{field_name: reference_value})
            trial = genome[:i] + [candidate] + genome[i + 1 :]
            total = evaluate(trial, fleet, regulations, prices, cache=cache).total_usd
            # Strictly a tie-break: `abs`, not `<=`. Accepting a strictly
            # *better* reference value here would work -- the coordinate
            # descent above stops at `max_sweeps` and does leave some on the
            # table -- but it would quietly turn this into a second search
            # that pulls toward the reference plan, which is exactly the bias
            # `exposure.solve_scenario_with_stability` must not have when it
            # measures how much independent seeds agree. Improvements are the
            # descent's job; this pass only chooses among plans this model
            # prices the same.
            if abs(total - current_total) <= DEGENERATE_COST_TOLERANCE_USD:
                current = candidate
                genome[i] = candidate
    return genome, current_total


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
    reference_genome: Genome | None = None,
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
    cache = ObjectiveCache()
    toolbox = _build_toolbox(fleet, regulations, prices, rng, tournament_size, cache)

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
    breakdown = evaluate(best_genome, fleet, regulations, prices, cache=cache)

    # Coordinate-descent polish (see _local_search_refine's docstring):
    # closes real single-slot convergence gaps the GA's finite population/
    # generations can leave behind, cheaply (evaluate() calls only), then
    # canonicalizes cost-neutral decisions against the reference plan.
    polished_genome, polished_total = _local_search_refine(
        best_genome,
        fleet,
        regulations,
        prices,
        rng,
        reference_genome=reference_genome if reference_genome is not None else seed_genome,
        cache=cache,
    )
    # `<=` (not `<`): the canonicalization pass deliberately returns an
    # equal-cost plan, and that plan is the one worth keeping.
    if polished_total <= breakdown.total_usd + DEGENERATE_COST_TOLERANCE_USD:
        best_genome = polished_genome
        breakdown = evaluate(best_genome, fleet, regulations, prices, cache=cache)

    return SolverResult(
        best_genome=best_genome,
        best_total_usd=breakdown.total_usd,
        best_breakdown=breakdown,
        generations_run=n_generations,
    )
