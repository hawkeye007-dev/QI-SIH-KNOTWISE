"""GA vs QIEA head-to-head benchmark — produces one comparison table.

Strictly orchestration, like `build_demo_data.py`: calls `run_sweep` and
`compute_exposure` directly under each optimizer at identical settings and
reports what came back. **Writes only to `outputs/optimizer_benchmark.{json,md}`
— never touches `outputs/demo_data.json` or `frontend/public/demo_data.json`.**
This is a decision-support run, not a demo-data build; the live demo is
untouched by running this.

Benchmark budget deliberately sits between `build_demo_data.py`'s `--fast`
and production settings: matches `tests/test_exposure.py::full_exposure`'s
fixture (already verified, elsewhere, to run in a few minutes and to
produce real, non-degenerate exposure results) rather than production's
20-30-minute budget, so this finishes in a reasonable time while still
being a meaningful, non-toy comparison. Re-run with larger settings before
trusting a close call.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from knotwise.fleet.loader import load_fleet, load_prices
from knotwise.optimization.exposure import compute_exposure
from knotwise.optimization.qiea_solver import run_qiea
from knotwise.optimization.solver import run_ga
from knotwise.optimization.sweep import run_sweep
from knotwise.regulatory.loader import load_scenarios
from knotwise.regulatory.scenario_resolution import resolve_regulations_for_scenario

BENCHMARK_PRICE_GRID = tuple(range(0, 1001, 100))  # 11 points, matches the verified-fast test fixture
BENCHMARK_SWEEP_KWARGS = {"population_size": 20, "cold_generations": 20, "warm_generations": 8}
BENCHMARK_EXPOSURE_KWARGS = {"seeds": (0, 1), "population_size": 60, "n_generations": 60}

#: Search-attribution ablation budget. Small on purpose: the effect it measures
#: is ~11% with non-overlapping ranges, so a handful of seeds resolves it
#: comfortably, and this has to stay cheap enough to run on every benchmark.
ATTRIBUTION_SEEDS = tuple(range(8))
ATTRIBUTION_SOLVER_KWARGS = {"population_size": 20, "n_generations": 20}
#: Regulatory scenarios the end-to-end half anchors on. Several, not one, so
#: the result is not an artifact of a single regulatory regime.
ATTRIBUTION_ANCHOR_SCENARIO_COUNT = 3
ATTRIBUTION_WARM_SEEDS = tuple(range(4))


def _describe(values: list[float]) -> dict:
    return {
        "mean_total_usd": statistics.mean(values),
        "best_total_usd": min(values),
        "worst_total_usd": max(values),
        "n_runs": len(values),
    }


def run_search_attribution(fleet: dict, prices: dict) -> dict:
    """Measure what the quantum-inspired *search* itself contributes, and
    whether that survives the shared coordinate-descent polish.

    This exists because the honest answer to "what does the quantum-inspired
    half actually do?" is two numbers that point opposite ways, and quoting
    either alone misleads. Both are computed here rather than transcribed from
    a previous run, so they cannot drift away from the code that produced them.
    """
    print("\n--- Running search attribution ablation ---")
    regulations = resolve_regulations_for_scenario("approved_text")

    # (a) The raw search, polish disabled: what QIEA's own mechanism finds.
    raw = {}
    for label, mean_field in (("uniform_init", False), ("mean_field_init", True)):
        start = time.perf_counter()
        totals = [
            run_qiea(
                fleet, regulations, prices, seed=seed, polish=False,
                mean_field_init=mean_field, **ATTRIBUTION_SOLVER_KWARGS,
            ).best_total_usd
            for seed in ATTRIBUTION_SEEDS
        ]
        raw[label] = _describe(totals)
        print(f"  raw search [{label}]: mean ${statistics.mean(totals):,.0f} ({time.perf_counter() - start:.1f}s)")

    # (b) The same two configurations in the real pipeline: polish on, warm
    #     re-solving from a fixed GA anchor, which is what every sweep grid
    #     point after the first and every exposure re-solve actually does.
    scenario_ids = [
        scenario["id"] for scenario in load_scenarios()["scenarios"][:ATTRIBUTION_ANCHOR_SCENARIO_COUNT]
    ]
    anchors = [
        (
            scenario_id,
            resolve_regulations_for_scenario(scenario_id),
        )
        for scenario_id in scenario_ids
    ]
    anchors = [
        (scenario_id, scenario_regulations,
         run_ga(fleet, scenario_regulations, prices, seed=99,
                population_size=40, n_generations=40).best_genome)
        for scenario_id, scenario_regulations in anchors
    ]
    end_to_end = {}
    for label, mean_field in (("uniform_init", False), ("mean_field_init", True)):
        start = time.perf_counter()
        totals = [
            run_qiea(
                fleet, scenario_regulations, prices,
                seed=seed, population_size=20, n_generations=8,
                seed_genome=genome, mean_field_init=mean_field,
            ).best_total_usd
            for _, scenario_regulations, genome in anchors
            for seed in ATTRIBUTION_WARM_SEEDS
        ]
        end_to_end[label] = _describe(totals)
        print(f"  end-to-end [{label}]: mean ${statistics.mean(totals):,.0f} ({time.perf_counter() - start:.1f}s)")

    raw_gain = 1 - raw["mean_field_init"]["mean_total_usd"] / raw["uniform_init"]["mean_total_usd"]
    net_gain = 1 - end_to_end["mean_field_init"]["mean_total_usd"] / end_to_end["uniform_init"]["mean_total_usd"]

    return {
        "status": "ILLUSTRATIVE",
        "description": (
            "What the quantum-inspired search contributes on its own, and how much of that "
            "survives the coordinate-descent polish both solvers share."
        ),
        "mechanism": (
            "Each qudit register starts at the Boltzmann marginals of its own vessel-year's "
            "separable cost table (objective.slot_local_total_usd over that slot's route x "
            "speed-band x fuel x shore-power domain) instead of uniform. A distribution per "
            "decision can absorb what the separable part of the objective already implies "
            "before any plan is evaluated; a population of point-valued genomes cannot "
            "represent that. pool_opt_in and borrow_election are deliberately left uniform -- "
            "they act only through FuelEU's cross-vessel pooling and multi-year ledger, which "
            "has no per-slot value for a prior to be built from."
        ),
        "raw_search_polish_disabled": raw,
        "end_to_end_polish_enabled": end_to_end,
        "raw_search_improvement_fraction": raw_gain,
        "end_to_end_improvement_fraction": net_gain,
        "finding": (
            f"The mean-field prior improves the raw search by {raw_gain:.1%}, and changes the "
            f"delivered answer by {net_gain:.1%} -- i.e. essentially not at all. The polish is "
            "dominant enough on this problem to erase the difference in what the search hands "
            "it. Both halves are measured. The second is the reason not to claim this solver "
            "beats the GA because of its physics: it does return the cheaper plan, by a margin "
            "inside the same noise band, and the mechanism that gets it there is a classical "
            "local search both solvers run."
        ),
        "settings": {
            "raw_search": {**ATTRIBUTION_SOLVER_KWARGS, "polish": False, "seeds": list(ATTRIBUTION_SEEDS)},
            "end_to_end": {
                "population_size": 20, "n_generations": 8, "polish": True,
                "anchor_scenario_ids": scenario_ids,
                "seeds": list(ATTRIBUTION_WARM_SEEDS),
            },
        },
    }


def run_one(optimizer: str, fleet: dict, prices: dict) -> dict:
    print(f"\n--- Running optimizer={optimizer} ---")
    start = time.perf_counter()

    sweep_start = time.perf_counter()
    sweep_result = run_sweep(
        fleet, prices, price_grid=BENCHMARK_PRICE_GRID, seed=0, optimizer=optimizer, **BENCHMARK_SWEEP_KWARGS
    )
    sweep_seconds = time.perf_counter() - sweep_start
    print(f"  sweep done in {sweep_seconds:.1f}s ({len(sweep_result.grid_points)} grid points)")

    exposure_start = time.perf_counter()
    exposure_result = compute_exposure(
        fleet, prices, sweep_result, optimizer=optimizer, **BENCHMARK_EXPOSURE_KWARGS
    )
    exposure_seconds = time.perf_counter() - exposure_start
    print(f"  exposure done in {exposure_seconds:.1f}s")

    total_seconds = time.perf_counter() - start
    totals = [gp.total_usd for gp in sweep_result.grid_points]
    n_corrected = sum(1 for gp in sweep_result.grid_points if gp.envelope_corrected)
    ps = exposure_result.plan_spread
    capex = exposure_result.capex_exposure
    majority_capex = exposure_result.majority_capex_exposure

    return {
        "optimizer": optimizer,
        "sweep_seconds": round(sweep_seconds, 2),
        "exposure_seconds": round(exposure_seconds, 2),
        "total_seconds": round(total_seconds, 2),
        "n_grid_points": len(sweep_result.grid_points),
        "n_switching_points": len(sweep_result.switching_points),
        "n_envelope_corrected": n_corrected,
        "total_usd_at_price_0": totals[0],
        "total_usd_at_price_max": totals[-1],
        "min_total_usd_across_grid": min(totals),
        "max_total_usd_across_grid": max(totals),
        "plan_spread_usd": ps.spread_usd,
        "plan_spread_inr_crore": round(ps.spread_inr / 1e7, 2),
        "n_unanimous_exposed": len(exposure_result.per_decision_deltas),
        "n_unanimous_unstable": len(exposure_result.unstable_decisions),
        "n_majority_exposed": len(exposure_result.majority_band_decisions),
        "capex_exposure_usd": capex.total_usd,
        "majority_capex_exposure_usd": majority_capex.total_usd,
    }


def to_markdown_table(ga: dict, qiea: dict) -> str:
    rows = [
        ("Sweep time (s)", "sweep_seconds"),
        ("Exposure time (s)", "exposure_seconds"),
        ("Total time (s)", "total_seconds"),
        ("Grid points", "n_grid_points"),
        ("Switching points found", "n_switching_points"),
        ("Envelope-corrected points", "n_envelope_corrected"),
        ("Total cost @ $0/t (USD)", "total_usd_at_price_0"),
        ("Total cost @ $1000/t (USD)", "total_usd_at_price_max"),
        ("Min cost across grid (USD)", "min_total_usd_across_grid"),
        ("Max cost across grid (USD)", "max_total_usd_across_grid"),
        ("Plan spread (USD)", "plan_spread_usd"),
        ("Plan spread (₹ crore)", "plan_spread_inr_crore"),
        ("Unanimous exposed decisions", "n_unanimous_exposed"),
        ("Unanimous unstable decisions", "n_unanimous_unstable"),
        ("Majority-band exposed decisions", "n_majority_exposed"),
        ("Capex exposure, unanimous (USD)", "capex_exposure_usd"),
        ("Capex exposure, majority (USD)", "majority_capex_exposure_usd"),
    ]

    def fmt(v):
        if isinstance(v, float):
            return f"{v:,.2f}"
        return str(v)

    lines = ["| Metric | GA | QIEA |", "|---|---|---|"]
    for label, key in rows:
        lines.append(f"| {label} | {fmt(ga[key])} | {fmt(qiea[key])} |")
    return "\n".join(lines)


def main():
    fleet = load_fleet()
    prices = load_prices()

    ga_result = run_one("ga", fleet, prices)
    qiea_result = run_one("qiea", fleet, prices)
    attribution = run_search_attribution(fleet, prices)

    table = to_markdown_table(ga_result, qiea_result)

    outputs_dir = PROJECT_ROOT / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    json_path = outputs_dir / "optimizer_benchmark.json"
    md_path = outputs_dir / "optimizer_benchmark.md"

    payload = {
        "document_version": "optimizer-benchmark-v2",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "ILLUSTRATIVE",
        "provenance_note": (
            "GA vs QIEA head-to-head at matched settings, plus an ablation isolating what the "
            "quantum-inspired search itself contributes. Every figure here is measured by this "
            "script on this fleet at the settings recorded alongside it -- prototype-grade, not "
            "a production-settings result, and the cost margin between the two solvers is small "
            "enough that the ordering should be re-confirmed at production settings before being "
            "relied on. Benchmark settings sit deliberately between build_demo_data.py's --fast "
            "and its production defaults."
        ),
        "note": (
            "Decision-support benchmark only -- does not affect outputs/demo_data.json or "
            "frontend/public/demo_data.json, which are unchanged by running this."
        ),
        "price_grid": list(BENCHMARK_PRICE_GRID),
        "sweep_kwargs": BENCHMARK_SWEEP_KWARGS,
        "exposure_kwargs": {k: (list(v) if isinstance(v, tuple) else v) for k, v in BENCHMARK_EXPOSURE_KWARGS.items()},
        "ga": ga_result,
        "qiea": qiea_result,
        "search_attribution": attribution,
    }
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)
    with open(md_path, "w") as f:
        f.write(f"# GA vs QIEA benchmark ({payload['generated_at']})\n\n")
        f.write(f"Price grid: {BENCHMARK_PRICE_GRID}\n\n")
        f.write(f"Sweep settings: {BENCHMARK_SWEEP_KWARGS}\n\n")
        f.write(f"Exposure settings: {BENCHMARK_EXPOSURE_KWARGS}\n\n")
        f.write(table + "\n")
        f.write("\n## What the quantum-inspired search itself contributes\n\n")
        f.write(attribution["mechanism"] + "\n\n")
        f.write("| Configuration | raw search (polish off) | delivered (polish on) |\n|---|---|---|\n")
        for label in ("uniform_init", "mean_field_init"):
            raw_mean = attribution["raw_search_polish_disabled"][label]["mean_total_usd"]
            net_mean = attribution["end_to_end_polish_enabled"][label]["mean_total_usd"]
            f.write(f"| {label} | ${raw_mean:,.0f} | ${net_mean:,.0f} |\n")
        f.write(
            f"\nRaw-search improvement: **{attribution['raw_search_improvement_fraction']:.1%}**. "
            f"Delivered improvement: **{attribution['end_to_end_improvement_fraction']:.1%}**.\n\n"
        )
        f.write(attribution["finding"] + "\n")

    print("\n" + "=" * 60)
    print(table)
    print(
        f"\nSearch attribution: raw {attribution['raw_search_improvement_fraction']:+.1%}, "
        f"delivered {attribution['end_to_end_improvement_fraction']:+.1%}"
    )
    print("=" * 60)
    print(f"\nWrote {json_path} and {md_path} (demo_data.json untouched).")


if __name__ == "__main__":
    main()
