"""Orchestration script to compute and build demo_data.json for KnotWise Next.js demo.

Strictly orchestration ONLY: calls existing functions from knotwise.fleet,
knotwise.optimization.sweep, and knotwise.optimization.exposure. Zero
reimplemented logic.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Ensure src is in python path if running standalone
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from knotwise.fleet.loader import load_fleet, load_prices
from knotwise.optimization.exposure import compute_exposure, exposure_result_to_dict
from knotwise.optimization.sweep import DEFAULT_PRICE_GRID, run_sweep, sweep_result_to_dict

ROUTES_GEO = {
    "status": "ILLUSTRATIVE",
    "provenance_note": (
        "Approximate waypoint polylines (lat/lon) derived from public shipping-lane "
        "knowledge and major port coordinates (Suez Canal, Strait of Hormuz, Malacca Strait, "
        "and Indian West/East coastal fairways). Illustrative only, not live AIS or actual ECDIS tracks."
    ),
    "routes": {
        "india_northeurope": {
            "name": "India to North Europe (via Suez)",
            "band": "A",
            "waypoints": [
                [18.95, 72.85],  # Nhava Sheva / Mumbai
                [14.50, 65.00],  # Arabian Sea
                [12.60, 43.30],  # Bab-el-Mandeb Strait
                [20.00, 38.50],  # Red Sea
                [29.90, 32.50],  # Suez Canal
                [34.00, 24.00],  # Central Mediterranean
                [35.90, -5.30],  # Strait of Gibraltar
                [48.50, -5.00],  # Ushant / Celtic Sea entrance
                [50.00, -1.00],  # English Channel
                [51.95, 4.00],   # Rotterdam
            ]
        },
        "india_mediterranean": {
            "name": "India to Mediterranean (via Suez)",
            "band": "A",
            "waypoints": [
                [18.95, 72.85],  # Nhava Sheva / Mumbai
                [14.50, 65.00],  # Arabian Sea
                [12.60, 43.30],  # Bab-el-Mandeb Strait
                [20.00, 38.50],  # Red Sea
                [29.90, 32.50],  # Suez Canal
                [35.50, 18.00],  # Central Med
                [43.20, 5.30],   # Marseille / Genoa approach
            ]
        },
        "india_gulf": {
            "name": "India to Persian Gulf (via Hormuz)",
            "band": "B",
            "waypoints": [
                [18.95, 72.85],  # Nhava Sheva / Mumbai
                [22.50, 64.00],  # Northern Arabian Sea
                [24.50, 58.50],  # Gulf of Oman
                [26.50, 56.40],  # Strait of Hormuz
                [25.00, 55.00],  # Jebel Ali / Dubai
            ]
        },
        "india_seasia": {
            "name": "India to Southeast Asia (via Malacca)",
            "band": "B",
            "waypoints": [
                [13.10, 80.30],  # Chennai
                [10.00, 88.00],  # Bay of Bengal
                [6.00, 95.00],   # Andaman Sea / Strait entrance
                [4.00, 99.50],   # Strait of Malacca
                [1.25, 103.80],  # Singapore
            ]
        },
        "coastal_westcoast": {
            "name": "Indian West Coast Feeder",
            "band": "C",
            "waypoints": [
                [23.00, 70.20],  # Deendayal / Kandla
                [21.00, 72.00],  # Gulf of Khambhat
                [18.95, 72.85],  # Mumbai / JNPT
                [15.40, 73.80],  # Mormugao (Goa)
                [12.90, 74.80],  # New Mangalore
                [9.96, 76.24],   # Cochin
            ]
        },
        "coastal_eastcoast": {
            "name": "Indian East Coast Feeder",
            "band": "C",
            "waypoints": [
                [22.00, 88.10],  # Syama Prasad Mookerjee / Haldia (Kolkata)
                [20.30, 86.70],  # Paradip
                [17.70, 83.30],  # Visakhapatnam
                [13.10, 80.30],  # Chennai
                [8.75, 78.18],   # V.O. Chidambaranar / Tuticorin
            ]
        }
    }
}


#: Production settings: expensive, thorough, the default. `--fast` overrides
#: these to a much cheaper budget for local iteration (verifying a code
#: change doesn't need production-quality convergence, just a fast round
#: trip); `demo_data.json` intended for actual submission/demo use should
#: always be built at these defaults, never at --fast settings.
PRODUCTION_SWEEP_KWARGS = dict(population_size=200, cold_generations=200, warm_generations=12)
PRODUCTION_EXPOSURE_KWARGS = dict(seeds=(0, 1, 2), population_size=200, n_generations=200)
FAST_SWEEP_KWARGS = dict(population_size=20, cold_generations=15, warm_generations=6)
FAST_EXPOSURE_KWARGS = dict(seeds=(0, 1), population_size=30, n_generations=30)

#: Where `scripts/benchmark_optimizers.py` leaves its GA-vs-QIEA comparison.
#: Read, never written, by this script.
BENCHMARK_PATH = PROJECT_ROOT / "outputs" / "optimizer_benchmark.json"


def load_optimizer_benchmark(demo_optimizer: str) -> dict:
    """Embed `benchmark_optimizers.py`'s comparison, if it has been run.

    Read rather than recomputed on purpose: the benchmark runs *both* solvers
    through a full sweep and exposure, so computing it here would more than
    double an already 20-30 minute production build, to answer a question that
    does not change between builds. It is a separate decision-support artifact
    with its own lifecycle, and this only carries it through to the demo.

    Because the two artifacts are produced independently, the block records
    what it is honest about: which optimizer *this* demo was actually built
    with, whether the benchmark predates this build, and -- when the benchmark
    has not been run at all -- that fact explicitly, with a defined shape, so a
    consumer never has to distinguish "absent" from "zero".
    """
    if not BENCHMARK_PATH.exists():
        return {
            "status": "NOT_AVAILABLE",
            "available": False,
            "demo_built_with_optimizer": demo_optimizer,
            "notes": (
                f"No optimizer benchmark found at {BENCHMARK_PATH.name}. Run "
                "scripts/benchmark_optimizers.py to produce one; it writes only its own "
                "outputs and does not affect this file."
            ),
        }

    with open(BENCHMARK_PATH) as handle:
        benchmark = json.load(handle)

    benchmark["available"] = True
    benchmark["demo_built_with_optimizer"] = demo_optimizer
    benchmark["freshness_note"] = (
        "This comparison was produced by a separate run of scripts/benchmark_optimizers.py "
        f"at {benchmark.get('generated_at', 'an unrecorded time')}, at that script's own "
        "benchmark settings -- not at the settings used to build this demo, and not "
        "necessarily from the same revision. It describes how the two solvers compare to "
        f"each other; the plans shown elsewhere in this file were solved with '{demo_optimizer}'."
    )
    return benchmark


def build_demo_data(*, fast: bool = False, optimizer: str = "ga") -> dict:
    print("=" * 60)
    print(f"KnotWise: Building demo_data.json{' [--fast dev mode]' if fast else ''} [optimizer={optimizer}]")
    print("=" * 60)
    start_time = time.perf_counter()

    sweep_kwargs = FAST_SWEEP_KWARGS if fast else PRODUCTION_SWEEP_KWARGS
    exposure_kwargs = FAST_EXPOSURE_KWARGS if fast else PRODUCTION_EXPOSURE_KWARGS

    # 1. Load Fleet and Price configurations
    print("[1/5] Loading fleet and prices specifications...")
    fleet = load_fleet()
    prices = load_prices()

    # 2. Run carbon-price sweep ($0–$1000 step $25, warm-started)
    print(f"[2/5] Running carbon-price sweep ($0–$1000, step $25, warm-started) with {sweep_kwargs}...")
    sweep_start = time.perf_counter()
    sweep_result = run_sweep(
        fleet,
        prices,
        price_grid=DEFAULT_PRICE_GRID,
        seed=0,
        optimizer=optimizer,
        **sweep_kwargs,
    )
    sweep_elapsed = time.perf_counter() - sweep_start
    print(f"      Sweep completed in {sweep_elapsed:.1f}s across {len(sweep_result.grid_points)} grid points.")
    print(f"      Extracted {len(sweep_result.switching_points)} decision switching points.")
    n_envelope_corrected = sum(1 for gp in sweep_result.grid_points if gp.envelope_corrected)
    print(f"      Monotonic envelope replaced {n_envelope_corrected}/{len(sweep_result.grid_points)} grid points'"
          " own GA solve with a cheaper genome found at another price.")

    # Validate grid boundaries for computed scenario axis ticks
    print("[3/5] Validating scenario axis positions against price grid...")
    grid_min = min(DEFAULT_PRICE_GRID)
    grid_max = max(DEFAULT_PRICE_GRID)
    for tick in sweep_result.scenario_ticks:
        if tick.operating_point_usd_per_tco2e is not None:
            pos = tick.operating_point_usd_per_tco2e
            print(f"      Tick '{tick.scenario_id}' ({tick.label}): ${pos:.2f}/tCO2e")
            assert grid_min <= pos <= grid_max, f"Position {pos} for {tick.scenario_id} is outside grid [{grid_min}, {grid_max}]"

    # 3. Run cross-scenario exposure analysis
    print(f"[4/5] Computing multi-scenario exposure map with {exposure_kwargs}...")
    exp_start = time.perf_counter()
    exposure_result = compute_exposure(
        fleet,
        prices,
        sweep_result,
        optimizer=optimizer,
        **exposure_kwargs,
    )
    exp_elapsed = time.perf_counter() - exp_start
    print(f"      Exposure analysis completed in {exp_elapsed:.1f}s.")

    # 4. Serialize dict structures and assemble payload
    print("[5/5] Assembling final demo_data.json payload...")
    sweep_dict = sweep_result_to_dict(sweep_result)
    exposure_dict = exposure_result_to_dict(exposure_result)

    demo_data = {
        "metadata": {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_build_seconds": round(time.perf_counter() - start_time, 2),
            "status_disclaimer": "SYNTHETIC FLEET, PROTOTYPE-GRADE FIGURES",
            "provenance": "Generated by scripts/build_demo_data.py calling knotwise optimizer & compliance core",
            "optimizer": optimizer,
        },
        "routes_geo": ROUTES_GEO,
        "fleet": fleet,
        "prices": prices,
        "sweep": sweep_dict,
        "exposure": exposure_dict,
        "optimizer_benchmark": load_optimizer_benchmark(optimizer),
    }

    # Print summary highlights
    ps = exposure_result.plan_spread
    capex = exposure_result.capex_exposure
    majority_capex = exposure_result.majority_capex_exposure
    totals = [gp.total_usd for gp in sweep_result.grid_points]
    n_corrected = sum(1 for gp in sweep_result.grid_points if gp.envelope_corrected)
    total_delta_usd = totals[-1] - totals[0]
    # NOT a universal "must be non-decreasing" check -- see sweep.py's
    # _apply_monotonic_envelope docstring. A fleet whose optimal plan nets
    # an NZF surplus credit legitimately gets cheaper as price rises; this
    # just reports which direction it actually went, honestly, rather than
    # asserting a claim that can be false for a well-optimized fleet.
    print("\n" + "=" * 60)
    print("SUMMARY HIGHLIGHTS:")
    print(f"  - Plan Spread: ${ps.spread_usd:,.2f} USD / ₹{ps.spread_inr/1e7:,.2f} Crore")
    print(f"  - Unanimous Headline Exposed Decisions: {len(exposure_result.per_decision_deltas)}")
    print(f"  - Majority Band Exposed Decisions: {len(exposure_result.majority_band_decisions)}")
    print(f"  - Capex Exposure (Unanimous): ${capex.total_usd:,.2f} USD / ₹{capex.total_inr/1e7:,.2f} Crore")
    print(f"  - Capex Exposure (Majority Band): ${majority_capex.total_usd:,.2f} USD / "
          f"₹{majority_capex.total_inr/1e7:,.2f} Crore")
    print(f"  - Total Grid Points Swept: {len(sweep_result.grid_points)}")
    print(f"  - Total Switching Points Extracted: {len(sweep_result.switching_points)}")
    print(f"  - Envelope-corrected grid points: {n_corrected}/{len(sweep_result.grid_points)}")
    benchmark = demo_data["optimizer_benchmark"]
    if benchmark.get("available"):
        attribution = benchmark.get("search_attribution", {})
        print(f"  - Optimizer benchmark embedded (generated {benchmark.get('generated_at')}); "
              f"search attribution raw {attribution.get('raw_search_improvement_fraction', 0):+.1%} / "
              f"delivered {attribution.get('end_to_end_improvement_fraction', 0):+.1%}")
    else:
        print("  - Optimizer benchmark: NOT AVAILABLE (run scripts/benchmark_optimizers.py)")
    print(f"  - Total fleet cost {'falls' if total_delta_usd < 0 else 'rises'} "
          f"${abs(total_delta_usd)/1e6:,.1f}M from $0/t to $1000/t "
          f"({'this fleet nets an NZF surplus credit at every price -- see sweep.py docstring for why that is correct, not a bug' if total_delta_usd < 0 else 'net NZF deficit dominates this fleet'})")
    print("=" * 60 + "\n")

    return demo_data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Cheap population/generation budget for local iteration (verifying a code change round-trips). "
        "Not for the demo_data.json that actually ships -- use production defaults (no flag) for that.",
    )
    parser.add_argument(
        "--optimizer",
        choices=("ga", "qiea"),
        default="ga",
        help="Solver used for every sweep grid point and every exposure stability seed: the classical "
        "Genetic Algorithm (default, what demo_data.json has always shipped with) or the Quantum-Inspired "
        "Evolutionary Algorithm (qiea_solver.py). Both write the same demo_data.json shape.",
    )
    args = parser.parse_args()

    outputs_dir = PROJECT_ROOT / "outputs"
    frontend_public_dir = PROJECT_ROOT / "frontend" / "public"

    outputs_dir.mkdir(parents=True, exist_ok=True)
    frontend_public_dir.mkdir(parents=True, exist_ok=True)

    demo_data = build_demo_data(fast=args.fast, optimizer=args.optimizer)

    output_path = outputs_dir / "demo_data.json"
    frontend_path = frontend_public_dir / "demo_data.json"

    print(f"Writing {output_path}...")
    with open(output_path, "w") as f:
        json.dump(demo_data, f, indent=2)

    print(f"Copying to {frontend_path}...")
    with open(frontend_path, "w") as f:
        json.dump(demo_data, f, indent=2)

    print("Successfully completed build_demo_data.py!")


if __name__ == "__main__":
    main()
