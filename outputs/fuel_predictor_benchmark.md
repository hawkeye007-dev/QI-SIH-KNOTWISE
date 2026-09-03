# Fuel-consumption prediction benchmark (2026-09-03T02:11:16Z)

Physics-only vs. LightGBM vs. MLP vs. tensor-train residual, leave-one-vessel-out cross-validated on SYNTHETIC telemetry -- there is no real AIS/ERA5/THETIS-MRV data pipeline in this repo (PLAN.md Phase 1 is unbuilt). The residual's generating process (hull-fouling age, sea state, gaussian noise -- see synthetic_telemetry.py's module docstring) is documented and known to whoever wrote it, so a model that approximates the learnable part of it is *expected* to beat physics-only on this data by construction. What this benchmark demonstrates is real: the feature engineering, leave-one-vessel-out CV methodology, and honest MAPE/R^2 reporting would apply directly to real telemetry the day Phase 1 exists. The specific numbers below are prototype-grade, not a claim about real-world model accuracy.

4000 synthetic samples, 10-fold leave-one-vessel-out (seed=0).

| Arm | Mean MAPE (%) | Best fold MAPE (%) | Worst fold MAPE (%) | Mean R² | Fit time (s, total over folds) |
|---|---|---|---|---|---|
| Physics-only | 3.993 | 2.139 | 5.596 | 0.9834 | 0.00 |
| LightGBM | 2.436 | 2.109 | 2.652 | 0.9935 | 0.26 |
| MLP | 4.224 | 2.261 | 13.617 | 0.9597 | 6.16 |
| Tensor-train residual | 2.470 | 2.062 | 2.864 | 0.9934 | 0.05 |

**LightGBM** wins on mean MAPE (2.436% vs. physics-only's 3.993%, a 1.558 percentage-point gap). See the provenance note above before treating this ranking as anything more than a demonstration that the benchmarking method works.

**MLP is markedly less stable across folds than LightGBM or the tensor-train residual** (4.22% mean but 13.62% on its worst fold, holding out A3) -- a known, real characteristic of gradient-trained neural nets on small tabular data (a fixed architecture and learning rate can land in a poor local optimum for a specific fold), and it is exactly the tree-based/tensor-based methods' relative stability that shows up here as an advantage, not just their mean accuracy.
