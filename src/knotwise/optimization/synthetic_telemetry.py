"""Synthetic fuel-consumption telemetry generator (PS Objective 1 / PLAN.md
§5 Phase 2's data pipeline).

**No real telemetry exists in this repo.** PLAN.md's Phase 1 (THETIS-MRV /
AIS / ERA5 ingestion) is unbuilt — `fleet.json` carries only class-level
static anchor figures (one illustrative daily-energy number per vessel band),
never a per-voyage or per-timestamp record. This module generates a
*documented* synthetic ground truth instead, so the prediction-benchmark
machinery (feature engineering, leave-one-vessel-out CV, honest MAPE/R²
reporting, the residual-model construction in `fuel_predictors.py`) is real
and runnable now, and would apply directly to real telemetry the day Phase 1
exists — the numeric *results* this produces are prototype-grade, not a
claim about real-world model accuracy, exactly as this codebase already
labels every other synthetic figure (`fleet.json`'s own `"ILLUSTRATIVE"`
anchor-energy fields, `docs/PLAN.md` §6.2).

**Each sample is a synthetic annual fuel-consumption observation**, not a
literal daily log entry: `knotwise.optimization.fuel_model.PhysicsFuelModel.
fuel_consumption_tonnes` already computes an *annual* total for a fixed
(route, speed, fuel, year) — the same units the `FuelModel` protocol's
consumers (`objective.py`, `sweep.py`, `exposure.py`) already expect. Rather
than inventing a separate "daily" concept those consumers don't use, each
sample here is one plausible annual outcome for a vessel-year under one
sampled (speed, fuel, route, hull-fouling age, sea-state) combination — an
ensemble of "what a full year at this operating point would have burned",
not a time series. This keeps `TelemetrySample.physics_tonnes` in exactly
the units `fuel_predictors.py`'s `FuelModel`-conformant residual predictors
need to correct.

**The residual has structured, learnable signal on purpose** — two
documented drift terms physics doesn't capture, plus bounded gaussian noise:

- **Hull-fouling age** (`hull_fouling_age_days`, 0 to `MAX_FOULING_AGE_DAYS`
  since a synthetic last drydock): drag — and therefore fuel burn — rises
  roughly linearly with fouling age; `hull_fouling_fraction` implements that
  as a fraction of `physics_tonnes`, capped at `MAX_FOULING_RESIDUAL_FRACTION`.
  Its *mean* is band-conditional (`_BAND_MEAN_FOULING_AGE_DAYS`) — deep-sea
  Band A vessels are given a longer typical drydock interval than Band C
  coastal feeders, an illustrative but directionally realistic maintenance-
  cadence difference — so vessel band carries real signal for this term.
- **Sea state** (`sea_state_index`, 0-1): a weather/current proxy. Its mean
  is nudged upward for longer, more open-ocean routes (derived from
  `fleet.json`'s own `distance_nm` — not a new hardcoded per-route table).
  Its *effect* on fuel burn is additionally scaled up at higher speed
  (`_speed_amplification`) — added resistance in a seaway grows faster than
  linearly with speed, a real hydrodynamic effect — so there is a genuine
  route x speed interaction here, not just a per-route additive offset.
- Gaussian measurement/engine-condition noise, `NOISE_STD_FRACTION` of
  `physics_tonnes`, irreducible by any model (the honest error floor).

**What a model can and cannot learn from this, stated plainly.** The
`FuelModel` protocol's `fuel_consumption_tonnes(vessel, fleet, year,
speed_knots, fuel_id, route_id)` signature has no slot for hull-fouling age
or sea state — the live solver has no such decision variable, and this
module's residual predictors (`fuel_predictors.py`) must stay conformant to
that exact signature to remain drop-in-compatible with `objective.evaluate`
and everything downstream of it. So a predictor is trained *and evaluated*
using only what that signature actually provides (band, route, fuel, speed,
year) — it can learn the band- and route-conditional *mean* of the fouling
and sea-state terms (real, systematic, learnable), and the speed-conditional
amplification of the sea-state term (real, nonlinear, learnable), but it
cannot and should not be expected to predict the zero-mean noise within
those terms or the explicit gaussian term — that part is the honest error
floor, the same way a real deployment averaging over unmeasured weather on
a given day would face it too.

A model that can approximate the *learnable* part of this generating
process will beat physics-only on this data — the residual is synthetic and
its structure is known to whoever wrote it. That is not a hidden weakness:
it is stated here, in the benchmark report
(`scripts/benchmark_fuel_predictor.py`), and in every consumer of this
module's output, exactly once, plainly.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from knotwise.fleet.model import speed_bands_knots
from knotwise.optimization.constraints import MIN_SPEED_BAND_INDEX
from knotwise.optimization.fuel_model import PhysicsFuelModel

#: Documented, ILLUSTRATIVE synthetic-residual parameters — see module
#: docstring. Not fitted to anything; chosen so physics-only prediction has
#: a real, non-trivial, non-overwhelming error to close (order 5-10% MAPE),
#: leaving room for a model to genuinely improve on it without the whole
#: benchmark being a coin flip against pure noise.
MAX_FOULING_AGE_DAYS = 730.0
MAX_FOULING_RESIDUAL_FRACTION = 0.08
SEA_STATE_RESIDUAL_SCALE = 0.05
NOISE_STD_FRACTION = 0.02

#: Mean days since a synthetic last drydock, by band -- deep-sea vessels get
#: a longer typical interval than coastal feeders (illustrative, directional).
_BAND_MEAN_FOULING_AGE_DAYS = {"A": 450.0, "B": 350.0, "C": 200.0}
_FOULING_AGE_RELATIVE_STDDEV = 0.4

DEFAULT_SAMPLES_PER_VESSEL_YEAR = 80

_PHYSICS = PhysicsFuelModel()


@dataclass(frozen=True)
class TelemetrySample:
    """One synthetic annual fuel-consumption observation. `physics_tonnes`
    is what `PhysicsFuelModel` alone predicts for this exact (vessel, year,
    speed, fuel, route); `actual_tonnes` additionally carries the two
    documented drift terms plus noise (module docstring)."""

    vessel_id: str
    band: str
    year: int
    route_id: str
    fuel_id: str
    speed_knots: float
    hull_fouling_age_days: float
    sea_state_index: float
    physics_tonnes: float
    actual_tonnes: float


def hull_fouling_fraction(hull_fouling_age_days: float) -> float:
    """Fraction of `physics_tonnes` added by hull-fouling drag, linear in
    age up to `MAX_FOULING_AGE_DAYS` (clamped beyond it — a vessel overdue
    for drydock doesn't keep fouling in this simplified model)."""
    age_fraction = min(max(hull_fouling_age_days, 0.0), MAX_FOULING_AGE_DAYS) / MAX_FOULING_AGE_DAYS
    return age_fraction * MAX_FOULING_RESIDUAL_FRACTION


def _speed_amplification(speed_knots: float, design_speed_knots: float) -> float:
    """Added resistance in a seaway grows faster than linearly with speed --
    a real hydrodynamic effect, not a modelling convenience. Scales the
    sea-state term from 0.5x at the slowest realistic speed up to 1.5x at
    full design speed, so the same sea state costs more fuel the faster the
    vessel is pushed through it."""
    fraction_of_design = speed_knots / design_speed_knots
    return 0.5 + fraction_of_design


def sea_state_fraction(sea_state_index: float, speed_knots: float, design_speed_knots: float) -> float:
    """Fraction of `physics_tonnes` added or removed by sea state, linear in
    `sea_state_index` (0-1) around its midpoint (+-`SEA_STATE_RESIDUAL_SCALE`
    at the extremes, 0 at `sea_state_index == 0.5`), scaled by how fast the
    vessel is moving through it (`_speed_amplification`)."""
    base = (sea_state_index - 0.5) * 2 * SEA_STATE_RESIDUAL_SCALE
    return base * _speed_amplification(speed_knots, design_speed_knots)


def _route_sea_state_bias(fleet: dict[str, Any], route_id: str) -> float:
    """Longer routes cross more open ocean -- a modest, documented proxy for
    a higher average sea state, derived from fleet.json's own `distance_nm`
    rather than a new hardcoded per-route table. 0-1, relative to this
    fleet's longest route."""
    distance_nm = fleet["routes"][route_id]["distance_nm"]
    max_distance = max(r["distance_nm"] for r in fleet["routes"].values())
    return distance_nm / max_distance if max_distance > 0 else 0.0


def _speed_range_knots(vessel: dict[str, Any], fleet: dict[str, Any]) -> tuple[float, float]:
    """The operationally-realistic continuous speed range for `vessel`:
    the same lower bound the solver itself is restricted to
    (`constraints.MIN_SPEED_BAND_INDEX`) through full design speed --
    reused from `fleet.model.speed_bands_knots` rather than re-deriving the
    0.30-1.00 fractions here."""
    design_speed = fleet["vessel_class_defaults"][vessel["band"]]["design_speed_knots"]
    bands = speed_bands_knots(design_speed)
    return bands[MIN_SPEED_BAND_INDEX], bands[-1]


def _vessel_routes(vessel: dict[str, Any], fleet: dict[str, Any]) -> list[str]:
    return [route_id for route_id, route in fleet["routes"].items() if route["band"] == vessel["band"]]


def _vessel_fuels(vessel: dict[str, Any], fleet: dict[str, Any]) -> list[str]:
    return list(fleet["engine_fuel_compatibility"]["matrix"][vessel["engine_type"]])


def _generate_sample(vessel: dict[str, Any], fleet: dict[str, Any], year: int, rng: random.Random) -> TelemetrySample:
    routes = _vessel_routes(vessel, fleet)
    fuels = _vessel_fuels(vessel, fleet)
    route_id = rng.choice(routes)
    fuel_id = rng.choice(fuels)

    design_speed_knots = fleet["vessel_class_defaults"][vessel["band"]]["design_speed_knots"]
    speed_lo, speed_hi = _speed_range_knots(vessel, fleet)
    speed_mode = speed_lo + 0.6 * (speed_hi - speed_lo)
    speed_knots = rng.triangular(speed_lo, speed_hi, speed_mode)

    fouling_mean = _BAND_MEAN_FOULING_AGE_DAYS[vessel["band"]]
    hull_fouling_age_days = min(
        max(rng.gauss(fouling_mean, fouling_mean * _FOULING_AGE_RELATIVE_STDDEV), 0.0), MAX_FOULING_AGE_DAYS
    )
    sea_state_bias = _route_sea_state_bias(fleet, route_id)
    sea_state_index = min(max(rng.gauss(0.3 + 0.3 * sea_state_bias, 0.15), 0.0), 1.0)

    physics_tonnes = _PHYSICS.fuel_consumption_tonnes(vessel, fleet, year, speed_knots, fuel_id, route_id)

    residual_fraction = (
        hull_fouling_fraction(hull_fouling_age_days)
        + sea_state_fraction(sea_state_index, speed_knots, design_speed_knots)
        + rng.gauss(0.0, NOISE_STD_FRACTION)
    )
    actual_tonnes = physics_tonnes * (1.0 + residual_fraction)

    return TelemetrySample(
        vessel_id=vessel["vessel_id"],
        band=vessel["band"],
        year=year,
        route_id=route_id,
        fuel_id=fuel_id,
        speed_knots=speed_knots,
        hull_fouling_age_days=hull_fouling_age_days,
        sea_state_index=sea_state_index,
        physics_tonnes=physics_tonnes,
        actual_tonnes=actual_tonnes,
    )


def generate_telemetry(
    fleet: dict[str, Any],
    *,
    samples_per_vessel_year: int = DEFAULT_SAMPLES_PER_VESSEL_YEAR,
    seed: int = 0,
) -> list[TelemetrySample]:
    """Generate `samples_per_vessel_year` synthetic annual observations for
    every (vessel, year) in `fleet`, deterministic for a fixed `seed` (one
    `random.Random(seed)` instance threads every draw, matching this
    codebase's RNG discipline elsewhere -- never the global `random` module).
    """
    rng = random.Random(seed)
    samples: list[TelemetrySample] = []
    for vessel in fleet["vessels"]:
        for year in fleet["horizon_years"]:
            for _ in range(samples_per_vessel_year):
                samples.append(_generate_sample(vessel, fleet, year, rng))
    return samples


def leave_one_vessel_out_folds(
    table: list[TelemetrySample],
) -> list[tuple[str, list[TelemetrySample], list[TelemetrySample]]]:
    """Split `table` into one fold per distinct `vessel_id`: that vessel's
    rows held out as the test set, every other vessel's rows as training.

    Returns `[(held_out_vessel_id, train, test), ...]`, one entry per vessel,
    in the order vessels first appear in `table`.
    """
    vessel_ids = list(dict.fromkeys(sample.vessel_id for sample in table))
    folds = []
    for held_out in vessel_ids:
        train = [s for s in table if s.vessel_id != held_out]
        test = [s for s in table if s.vessel_id == held_out]
        folds.append((held_out, train, test))
    return folds
