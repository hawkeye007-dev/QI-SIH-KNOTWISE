# Optimizer tuning, round 2 — shared-machinery pass

Round 1 (`qiea_tuning_ablation.md`) tuned the QIEA *search* and concluded that
the coordinate-descent polish, not the quantum-inspired redesign, closed the
gap to the GA. This round changed no search logic at all. It changed three
things underneath both solvers, and re-ran `scripts/benchmark_optimizers.py`
at identical settings.

## The three changes

**1. `objective.ObjectiveCache` — memoize the slot-local half of `evaluate`.**
Roughly two thirds of `evaluate`'s cost is per-vessel-year work that depends
only on that slot's own `(route, speed band, fuel, shore power)` — not on
`pool_opt_in`/`borrow_election`, and not on any other slot. The solvers'
hottest access pattern (`_local_search_refine` changes exactly one field per
call) hits that cache almost every time. Measured: **1.43 ms → 0.31 ms per
`evaluate` (4.6x)**, bit-identical output (max |cached − uncached| = 0.0 over
300 random genomes). The cache holds a strong reference to the four objects it
was bound against and clears itself when handed a different set, so reuse
across sweep grid points — whose `regulations` differ — yields a cold cache,
never a wrong number.

**2. QIEA qudit registers: numpy arrays → plain lists.** These vectors are 2–6
entries long and there are 300 of them per individual per generation, a regime
where numpy's per-call dispatch dominates its arithmetic. Measured before the
change: **58% of a QIEA generation's wall time was register bookkeeping**, not
`evaluate` — which is where essentially all of the GA-vs-QIEA time gap came
from. Solver output is unchanged, seed for seed.

**3. `solver._canonicalize_against` — a cost-tied tie-break.** Sweeping every
single-field change off a solved genome, the cost deltas fall into two disjoint
clusters: **89 of 585 candidates land below 1e-6 USD**, and every one of them is
a `pool_opt_in` or `borrow_election` bit on a vessel-year with no FuelEU
balance to pool or bank. The next cheapest candidate is over $1000 — nine
orders of magnitude of clear water. Left arbitrary, those ~89 free bits get
re-rolled by every independent solve, so adjacent sweep grid points disagree on
them for no economic reason, and `extract_switching_points` reports each
disagreement as a switching point. After the descent converges, any field that
can be set back to a reference plan's value **without changing total cost**
now is.

Strictly a tie-break (`abs(delta) <= tolerance`, not `<=`): accepting strictly
*better* reference values would also have worked, but it would quietly become a
second search biased toward the reference — exactly the bias
`exposure.solve_scenario_with_stability` must not have when it measures how much
independent seeds agree.

Enabled by (1): the descent's `max_sweeps` cap went 2 → 6, so it reaches its own
fixed point instead of being cut off mid-way.

## A/B evidence for the tie-break

6-point grid, `population_size=20`, identical seeds. The tie-break is toggled;
nothing else changes.

| | switching points | of those, degenerate-field | economic | cost @ $0/t |
|---|---|---|---|---|
| GA, tie-break off | 25 | 2 | 23 | $370,329,510 |
| GA, tie-break on | 25 | 2 | 23 | $370,329,510 |
| QIEA, tie-break off | 119 | 66 | 53 | $370,061,690 |
| QIEA, tie-break on | **61** | **8** | 53 | $370,061,690 |

| | unstable decisions (of 300) | best cost |
|---|---|---|
| exposure, tie-break off | 110 | $374,141,857 |
| exposure, tie-break on | **47** | $374,141,857 |

**Costs are identical to the cent in every row.** The economic switching-point
count is identical too (53 both ways for QIEA). The pass removes degenerate
flips and nothing else — verified, not asserted.

## Benchmark result

Same script, same settings, before vs after.

| Metric | GA before | GA after | QIEA before | QIEA after |
|---|---|---|---|---|
| Total time (s) | 94.06 | **35.04** | 176.97 | **81.19** |
| Total cost @ $0/t | $371,280,364 | **$370,329,510** | $373,446,856 | **$369,633,370** |
| Min cost across grid | $370,465,290 | $370,329,510 | $373,446,856 | **$369,633,370** |
| Switching points | 23 | 27 | 146 | **52** |
| Unstable decisions | 138 | **69** | 133 | **63** |
| Envelope-corrected points | 1 | **0** | 8 | 8 |

QIEA now returns the **cheapest plan of either solver** ($369.63M vs GA's
$370.33M, −0.19%), and both solvers are ~2.5x faster than before.

## What is still true, and still a caveat

- **QIEA's raw search is still the weaker of the two.** 8 of its 11 grid points
  still lose to a donor genome and trigger `_apply_monotonic_envelope` +
  a full independent cold re-solve; the GA now needs zero. QIEA's better final
  numbers come from the shared polish and envelope machinery working harder on
  a worse starting point, not from the quantum-inspired search finding more.
  Round 1's attribution stands.
- **QIEA is still ~2.3x slower than GA** (81s vs 35s), and for the same reason:
  those 8 re-solves, plus a polish that starts further away. The numpy fix
  removed the overhead half of the old gap; what remains is search quality.
- **52 switching points is not yet proven to be all signal.** It is now
  8-degenerate/44-economic rather than mostly degenerate, which is a real
  improvement, but `run_sweep`'s own warning still applies: an isolated flip at
  one grid step can be the search settling rather than the optimum moving.
- These are benchmark settings, deliberately between `--fast` and production.
  Re-run at production settings before treating the GA-vs-QIEA cost ordering,
  which is a 0.19% margin, as decided.

`outputs/demo_data.json` and `frontend/public/demo_data.json` are untouched by
this work.
