# QIEA tuning ablation

Baseline scenario (`approved_text`), `population_size=20, n_generations=20`, GA at the same settings for reference. Total cost in USD, lower is better.

| Variant | seed=0 | seed=1 | seed=2 |
|---|---|---|---|
| GA (reference) | 379,285,950 | 380,251,984 | 380,498,042 |
| QIEA baseline (flat lr=0.08, archive=1, no polish) | 521,722,970 | 525,526,932 | 526,370,434 |
| QIEA + polish only | 378,220,996 | — | — |
| QIEA + elite archive only (size=5) | 558,346,015 | — | — |
| QIEA + annealed rate only (0.05 → 0.45) | 461,496,289 | — | — |
| QIEA + annealed rate + elite archive, no polish | 480,767,602 | 495,479,234 | 517,857,603 |
| QIEA all three (new defaults) | 378,186,302 | 380,682,018 | 379,831,729 |

## Reading

- **The coordinate-descent polish step, alone, closes essentially the entire gap** (378.2M vs GA's 379.3M at seed 0) — reusing `solver._local_search_refine`, the exact mechanism `run_ga` already uses to fix single-slot convergence gaps.
- **The elite-archive redesign, alone, is mildly *worse* than the single-global-best baseline it replaced** (558.3M vs 521.7M) — diluting rotation across 5 targets without ever committing hard seems to hurt more than a single (even premature) attractor helps, at this budget.
- **The annealed rotation rate, alone, helps but not decisively** (461.5M vs 521.7M baseline — real improvement, still ~20% off GA).
- **Archive + annealing together, without polish, land between the two** (~481–518M across seeds) — still meaningfully worse than GA, confirming the search-side redesign is not, on its own, what closes the gap.
- All three combined match GA almost exactly and don't measurably underperform polish-alone, so all three ship as defaults — but the honest attribution is: **the polish step did the work.**
