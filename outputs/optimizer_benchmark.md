# GA vs QIEA benchmark (2026-09-02T11:58:23Z)

Price grid: (0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000)

Sweep settings: {'population_size': 20, 'cold_generations': 20, 'warm_generations': 8}

Exposure settings: {'seeds': (0, 1), 'population_size': 60, 'n_generations': 60}

| Metric | GA | QIEA |
|---|---|---|
| Sweep time (s) | 9.20 | 30.95 |
| Exposure time (s) | 25.86 | 52.79 |
| Total time (s) | 35.05 | 83.74 |
| Grid points | 11 | 11 |
| Switching points found | 27 | 55 |
| Envelope-corrected points | 0 | 8 |
| Total cost @ $0/t (USD) | 370,329,510.18 | 370,498,981.31 |
| Total cost @ $1000/t (USD) | 370,465,290.25 | 369,959,179.90 |
| Min cost across grid (USD) | 370,329,510.18 | 369,959,179.90 |
| Max cost across grid (USD) | 374,105,128.40 | 374,418,499.50 |
| Plan spread (USD) | 4,614,311.88 | 5,148,707.92 |
| Plan spread (₹ crore) | 44.11 | 49.22 |
| Unanimous exposed decisions | 41 | 45 |
| Unanimous unstable decisions | 69 | 70 |
| Majority-band exposed decisions | 0 | 0 |
| Capex exposure, unanimous (USD) | 0 | 0 |
| Capex exposure, majority (USD) | 0 | 0 |

## What the quantum-inspired search itself contributes

Each qudit register starts at the Boltzmann marginals of its own vessel-year's separable cost table (objective.slot_local_total_usd over that slot's route x speed-band x fuel x shore-power domain) instead of uniform. A distribution per decision can absorb what the separable part of the objective already implies before any plan is evaluated; a population of point-valued genomes cannot represent that. pool_opt_in and borrow_election are deliberately left uniform -- they act only through FuelEU's cross-vessel pooling and multi-year ledger, which has no per-slot value for a prior to be built from.

| Configuration | raw search (polish off) | delivered (polish on) |
|---|---|---|
| uniform_init | $497,606,069 | $371,842,320 |
| mean_field_init | $441,947,561 | $372,113,531 |

Raw-search improvement: **11.2%**. Delivered improvement: **-0.1%**.

The mean-field prior improves the raw search by 11.2%, and changes the delivered answer by -0.1% -- i.e. essentially not at all. The polish is dominant enough on this problem to erase the difference in what the search hands it. Both halves are measured. The second is the reason not to claim this solver beats the GA because of its physics: it does return the cheaper plan, by a margin inside the same noise band, and the mechanism that gets it there is a classical local search both solvers run.
