# QIEA round 3 — improving the search itself

Rounds 1 and 2 both concluded that the coordinate-descent polish, not the
quantum-inspired search, was producing this solver's numbers. Round 3 attacked
the search directly. The finding is partly positive and partly a hard limit,
and the limit is the more important half.

## What was tried

**1. Mean-field initialization — KEPT (default on).** Registers started
uniform. They now start at the Boltzmann marginals of that vessel-year's own
*separable* cost table: `objective.slot_local_total_usd` enumerated over the
slot's route × speed-band × fuel × shore-power domain (96 combinations per
slot on this fleet, 50 slots), with the temperature set by the spread of those
costs — the same idiom `mps_exposure` already uses. Each individual draws its
own temperature scale, so the population starts informed *and* diverse.

`pool_opt_in` and `borrow_election` are deliberately left uniform: they enter
the objective only through FuelEU's cross-vessel pooling and multi-year ledger,
which has no per-slot value, so the prior has nothing honest to say about them.

This is the concrete answer to "what does the quantum-inspired representation
buy you?" — a *distribution* per decision can be seeded with the separable part
of the objective before any plan is evaluated. A population of point-valued
genomes cannot represent that. In tensor-network terms it is a mean-field
product state over the separable part of the cost, refined by search against
the coupled part no product state can express. It is a soft prior, not a greedy
argmin, precisely because the omitted coupled terms are real.

**2. Per-individual attractor (Han & Kim's `b_j`) — TRIED, REMOVED.** Rotating
each individual toward its own best-observed solution, with periodic global
migration from the elite archive, is the more faithful reading of the original
paper than the shared-archive-every-generation scheme in place. It measured
worse and was removed.

**3. Warm-start breadth — KEPT, NOT CLAIMED.** This module warm-started
1 individual in 40; `solver._seeded_population` warm-starts 11. The sweep is
almost entirely warm solves, so the asymmetry was pure loss — and plainly
unintended rather than tuned. Closing it costs nothing.

## Raw search quality (`polish=False`, pop 20 / gen 20, 8 seeds)

This isolates what the search itself finds, before the polish touches it.

| Configuration | mean | best | worst |
|---|---|---|---|
| baseline (uniform init) | $497,606,069 | $477,782,850 | $517,857,603 |
| **mean-field init** | **$441,947,561** | **$411,672,061** | **$453,804,580** |
| per-individual attractor | $513,760,315 | $456,184,149 | $541,156,817 |
| both | $459,872,640 | $427,846,083 | $487,224,594 |

**Mean-field initialization improves the raw search by 11.2%, and the ranges do
not overlap** — its worst seed ($453.8M) beats the baseline's best ($477.8M).
That is the largest effect any change has had on this solver's search. The
per-individual attractor is 3.2% *worse* than the baseline it was meant to
improve, and drags the combination down.

## End-to-end effect: none

Warm re-solve at price+100 from a fixed GA anchor, 5 anchors × 6 seeds =
30 solves per configuration, polish on (i.e. the real configuration).

| Configuration | mean total | median | worst | s/solve |
|---|---|---|---|---|
| warm 1-in-40 (old) | $371,217,788 | $370,318,927 | $373,806,276 | 1.23 |
| warm 25% | $371,070,509 | $370,358,520 | $372,872,992 | 1.25 |
| warm 25% + mean-field | $371,211,400 | $370,427,903 | $373,084,222 | 1.39 |
| warm 50% | $371,275,900 | $370,383,806 | $374,085,099 | 1.23 |

**Spread across all four: 0.06%.** Inside run-to-run noise. An 11.2%
improvement in what the search hands the polish produces no measurable change
in what comes out.

## A negative result worth recording

The sweep's `envelope_corrected` count — the metric that motivated this round
("QIEA loses 8 of 11 grid points, the GA loses none") — turns out to be too
noisy to tune against at this budget. The *same* configuration produced 8
corrections at seed 0 and 4 at seed 1. An apparent 8 → 4 improvement from the
warm-start fix at seed 0 did not replicate at seed 1 (4 → 7). Anything read
off a single-seed sweep at these settings is not a result. The n=30 warm-solve
comparison above replaced it for exactly this reason.

## Side effect worth knowing: mean-field largely substitutes for the warm start

Warm-started vs cold solve, same settings, 12 seeds each:

| Setting | init | warm mean | cold mean | warm wins |
|---|---|---|---|---|
| pop 6 / gen 1 | uniform | $374,313,471 | $374,500,991 | 9/12 |
| pop 6 / gen 1 | mean-field | $374,324,567 | $374,456,694 | 7/12 |
| pop 20 / gen 8 | uniform | $374,207,705 | $374,505,008 | 9/12 |
| pop 20 / gen 8 | mean-field | $374,353,620 | **$374,263,340** | 6/12 |

With uniform initialization the warm start is a clear win (9/12). With
mean-field initialization it is roughly a coin flip, and at sweep-like settings
the cold solve is marginally *ahead*. That is coherent rather than alarming:
both mechanisms do the same job — hand the search a good starting distribution
— so once one is in place the other has little left to add. The sweep's warm
start still earns its keep on *time* (8 generations instead of 20), just no
longer on quality.

This surfaced as a test failure (`test_seed_genome_biases_the_first_generation_
toward_it`, which asserted `min(warm) <= min(cold)` over five seeds). That
assertion was a weak proxy that now sits near chance. It was replaced by two
tests of the actual contract: a deterministic check that
`_warm_start_population` biases the intended share of registers, and a
behavioural check on *decision agreement* with the seed plan, which separates
cleanly (warm's worst 0.857 vs cold's best 0.757).

## Conclusion

Two things are true at once, both measured:

1. **The quantum-inspired representation does something a genetic population
   structurally cannot**, and it is worth 11.2% on the search — the mean-field
   prior is real, and it is the honest answer to what the physics contributes.
2. **On this problem, at these budgets, it does not matter.** The
   coordinate-descent polish is dominant enough to erase an 11% difference in
   its input. Round 1's and round 2's attribution stands, now confirmed a third
   time from the search side.

This is the reason not to present QIEA as beating the GA *because of* its
physics. It does return the cheaper plan — by 0.19%, within the same noise band
as everything else here — and the mechanism that gets it there is a classical
local search both solvers share.

## Benchmark after round 3

Unchanged end to end, exactly as the n=30 comparison predicted:

| Metric | GA | QIEA (round 2) | QIEA (round 3) |
|---|---|---|---|
| Total time (s) | 35.12 | 81.19 | 78.78 |
| Min cost across grid | $370,329,510 | $369,633,370 | $369,959,180 |
| Switching points | 27 | 52 | 55 |
| Envelope-corrected | 0 | 8 | 8 |

QIEA still returns the cheaper plan (0.10% under the GA here) and is still
~2.2x slower. The 8 envelope corrections did not move — which, given the
seed-to-seed variance documented above, is the expected outcome rather than a
failure of the change.

Where this would change: a problem whose objective is less separable-plus-polish
friendly, or a budget too tight to run coordinate descent to its fixed point.
Neither is this case.
