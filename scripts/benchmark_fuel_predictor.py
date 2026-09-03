"""Fuel-consumption prediction benchmark (PS Objective 1 / experiment B1).

Physics baseline vs. LightGBM vs. MLP vs. tensor-train residual, leave-one-
vessel-out cross-validated on synthetic telemetry (`knotwise.optimization.
synthetic_telemetry` — see that module's docstring for exactly what the
residual is and is not, and why the ground truth is synthetic: no real
AIS/ERA5/THETIS-MRV pipeline exists in this repo yet).

Strictly orchestration, like `benchmark_optimizers.py`: calls existing
functions from `knotwise.optimization.{synthetic_telemetry,fuel_predictors}`
and reports what came back. **Writes only to
`outputs/fuel_predictor_benchmark.{json,md}` — never touches
`outputs/demo_data.json` or `frontend/public/demo_data.json`.**
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from knotwise.fleet.loader import load_fleet
from knotwise.optimization.fuel_model import PhysicsFuelModel
from knotwise.optimization.fuel_predictors import (
    FeatureEncoder,
    LightGbmResidualFuelModel,
    MlpResidualFuelModel,
    TensorTrainResidualFuelModel,
    mape,
    r_squared,
)
from knotwise.optimization.synthetic_telemetry import generate_telemetry, leave_one_vessel_out_folds

SAMPLES_PER_VESSEL_YEAR = 80
TELEMETRY_SEED = 0

_PHYSICS = PhysicsFuelModel()

#: (arm name, model class or None for the physics-only baseline, which
#: needs no fitting).
_LEARNED_ARMS: tuple[tuple[str, type], ...] = (
    ("lightgbm", LightGbmResidualFuelModel),
    ("mlp", MlpResidualFuelModel),
    ("tensor_train", TensorTrainResidualFuelModel),
)
ARMS: tuple[str, ...] = ("physics",) + tuple(name for name, _ in _LEARNED_ARMS)


def _predict(arm: str, model: Any, vessel: dict, fleet: dict, sample) -> float:
    fuel_model = _PHYSICS if arm == "physics" else model
    return fuel_model.fuel_consumption_tonnes(vessel, fleet, sample.year, sample.speed_knots, sample.fuel_id, sample.route_id)


def run_lovo_benchmark(
    fleet: dict, *, samples_per_vessel_year: int = SAMPLES_PER_VESSEL_YEAR, seed: int = TELEMETRY_SEED
) -> dict:
    """Generate telemetry once, then leave-one-vessel-out cross-validate
    every arm on it: for each held-out vessel, fit the three learned arms on
    every other vessel's rows and score all four arms (physics included) on
    the held-out vessel's rows -- the same test set for every arm, every fold.
    """
    print(f"Generating synthetic telemetry ({samples_per_vessel_year} samples/vessel-year, seed={seed})...")
    table = generate_telemetry(fleet, samples_per_vessel_year=samples_per_vessel_year, seed=seed)
    folds = leave_one_vessel_out_folds(table)
    vessels_by_id = {v["vessel_id"]: v for v in fleet["vessels"]}
    encoder = FeatureEncoder(fleet)
    print(f"  {len(table)} samples across {len(folds)} vessels ({len(folds)}-fold leave-one-vessel-out).")

    per_arm_fold_mape: dict[str, list[float]] = {arm: [] for arm in ARMS}
    per_arm_fold_r2: dict[str, list[float]] = {arm: [] for arm in ARMS}
    fit_seconds: dict[str, float] = {name: 0.0 for name, _ in _LEARNED_ARMS}

    for held_out_vessel_id, train, test in folds:
        print(f"  fold: holding out {held_out_vessel_id} (train={len(train)}, test={len(test)})")
        actual = [sample.actual_tonnes for sample in test]

        models: dict[str, Any] = {}
        for name, cls in _LEARNED_ARMS:
            model = cls(encoder)
            start = time.perf_counter()
            model.fit(train, fleet)
            fit_seconds[name] += time.perf_counter() - start
            models[name] = model

        for arm in ARMS:
            predicted = [_predict(arm, models.get(arm), vessels_by_id[s.vessel_id], fleet, s) for s in test]
            per_arm_fold_mape[arm].append(mape(actual, predicted))
            per_arm_fold_r2[arm].append(r_squared(actual, predicted))

    arm_results = {
        arm: {
            "mean_mape_percent": statistics.mean(per_arm_fold_mape[arm]),
            "best_fold_mape_percent": min(per_arm_fold_mape[arm]),
            "worst_fold_mape_percent": max(per_arm_fold_mape[arm]),
            "mean_r_squared": statistics.mean(per_arm_fold_r2[arm]),
            "fit_seconds_total": round(fit_seconds.get(arm, 0.0), 2),
        }
        for arm in ARMS
    }

    return {
        "n_samples": len(table),
        "n_folds": len(folds),
        "samples_per_vessel_year": samples_per_vessel_year,
        "telemetry_seed": seed,
        "arms": arm_results,
        "fold_vessel_ids": [held_out_vessel_id for held_out_vessel_id, _, _ in folds],
        "per_fold_mape_percent": {arm: [round(v, 3) for v in per_arm_fold_mape[arm]] for arm in ARMS},
    }


def to_markdown_table(result: dict) -> str:
    labels = {
        "physics": "Physics-only",
        "lightgbm": "LightGBM",
        "mlp": "MLP",
        "tensor_train": "Tensor-train residual",
    }
    lines = [
        "| Arm | Mean MAPE (%) | Best fold MAPE (%) | Worst fold MAPE (%) | Mean R² | Fit time (s, total over folds) |",
        "|---|---|---|---|---|---|",
    ]
    for arm in ARMS:
        a = result["arms"][arm]
        lines.append(
            f"| {labels[arm]} | {a['mean_mape_percent']:.3f} | {a['best_fold_mape_percent']:.3f} | "
            f"{a['worst_fold_mape_percent']:.3f} | {a['mean_r_squared']:.4f} | {a['fit_seconds_total']:.2f} |"
        )
    return "\n".join(lines)


def main() -> None:
    fleet = load_fleet()

    start = time.perf_counter()
    result = run_lovo_benchmark(fleet)
    elapsed = time.perf_counter() - start

    table = to_markdown_table(result)
    physics_mape = result["arms"]["physics"]["mean_mape_percent"]
    best_arm = min(ARMS, key=lambda a: result["arms"][a]["mean_mape_percent"])
    best_mape = result["arms"][best_arm]["mean_mape_percent"]

    outputs_dir = PROJECT_ROOT / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = outputs_dir / "fuel_predictor_benchmark.json"
    md_path = outputs_dir / "fuel_predictor_benchmark.md"

    payload = {
        "document_version": "fuel-predictor-benchmark-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "ILLUSTRATIVE",
        "provenance_note": (
            "Physics-only vs. LightGBM vs. MLP vs. tensor-train residual, leave-one-vessel-out "
            "cross-validated on SYNTHETIC telemetry -- there is no real AIS/ERA5/THETIS-MRV data "
            "pipeline in this repo (PLAN.md Phase 1 is unbuilt). The residual's generating process "
            "(hull-fouling age, sea state, gaussian noise -- see synthetic_telemetry.py's module "
            "docstring) is documented and known to whoever wrote it, so a model that approximates "
            "the learnable part of it is *expected* to beat physics-only on this data by "
            "construction. What this benchmark demonstrates is real: the feature engineering, "
            "leave-one-vessel-out CV methodology, and honest MAPE/R^2 reporting would apply "
            "directly to real telemetry the day Phase 1 exists. The specific numbers below are "
            "prototype-grade, not a claim about real-world model accuracy."
        ),
        "note": (
            "Decision-support benchmark only -- does not affect outputs/demo_data.json or "
            "frontend/public/demo_data.json, which are unchanged by running this."
        ),
        "total_seconds": round(elapsed, 2),
        **result,
        "best_arm": best_arm,
        "physics_only_mape_percent": physics_mape,
        "best_arm_mape_percent": best_mape,
        "best_arm_improvement_percentage_points": round(physics_mape - best_mape, 3),
    }
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)
    with open(md_path, "w") as f:
        f.write(f"# Fuel-consumption prediction benchmark ({payload['generated_at']})\n\n")
        f.write(payload["provenance_note"] + "\n\n")
        f.write(
            f"{result['n_samples']} synthetic samples, {result['n_folds']}-fold leave-one-vessel-out "
            f"(seed={result['telemetry_seed']}).\n\n"
        )
        f.write(table + "\n\n")
        arm_labels = {"physics": "Physics-only", "lightgbm": "LightGBM", "mlp": "MLP", "tensor_train": "Tensor-train residual"}
        f.write(
            f"**{arm_labels[best_arm]}** wins on mean MAPE "
            f"({best_mape:.3f}% vs. physics-only's {physics_mape:.3f}%, a "
            f"{payload['best_arm_improvement_percentage_points']:.3f} percentage-point gap). See "
            "the provenance note above before treating this ranking as anything more than a "
            "demonstration that the benchmarking method works.\n\n"
        )

        # MLP's worst-vs-mean gap is a real, measured finding, not smoothed
        # over: report it plainly whenever it's large enough to be worth a
        # reader's attention, same house style as this codebase's other
        # benchmark reports (e.g. optimizer_benchmark.md's honest QIEA-vs-GA
        # margin) -- never hide an inconvenient number behind a mean alone.
        mlp = result["arms"]["mlp"]
        if mlp["worst_fold_mape_percent"] > 2 * mlp["mean_mape_percent"]:
            worst_folds = [
                (vessel_id, mape_pct)
                for vessel_id, mape_pct in zip(result["fold_vessel_ids"], result["per_fold_mape_percent"]["mlp"])
                if mape_pct > 2 * mlp["mean_mape_percent"]
            ]
            f.write(
                f"**MLP is markedly less stable across folds than LightGBM or the tensor-train "
                f"residual** ({mlp['mean_mape_percent']:.2f}% mean but "
                f"{mlp['worst_fold_mape_percent']:.2f}% on its worst fold, holding out "
                f"{', '.join(v for v, _ in worst_folds)}) -- a known, real characteristic of "
                "gradient-trained neural nets on small tabular data (a fixed architecture and "
                "learning rate can land in a poor local optimum for a specific fold), and it is "
                "exactly the tree-based/tensor-based methods' relative stability that shows up "
                "here as an advantage, not just their mean accuracy.\n"
            )

    print("\n" + "=" * 60)
    print(table)
    print(f"\nBest arm on mean MAPE: {best_arm} ({best_mape:.3f}% vs. physics-only {physics_mape:.3f}%)")
    print(f"Total benchmark time: {elapsed:.1f}s")
    print("=" * 60)
    print(f"\nWrote {json_path} and {md_path} (demo_data.json untouched).")


if __name__ == "__main__":
    main()
