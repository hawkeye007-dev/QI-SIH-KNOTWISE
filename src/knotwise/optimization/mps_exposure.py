"""The Exposure Map, computed for real from an actual Matrix Product State —
PLAN.md §3.1's own definition, not `exposure.py`'s classical flip-counting
proxy (which PLAN §8.3(b) describes as *this* method's validation check,
built first because the tensor method didn't exist yet).

**Scope of this iteration.** PLAN/DESIGN_NOTE_POOLING.md describe a single
fleet-wide MPS: 125 sites (24 vessels x 5 years, plus the regulatory leg),
genuinely entangled end to end. Building and *training* that object is a
Track F-scale effort (bond-dimension sweeps, DMRG-style optimization,
likely gradient-based amplitude fitting). This module instead builds one
**small, exact Born machine per vessel-year slot**: the regulatory leg `r`
(K=5) entangled with that one slot's own six `genome.DECISION_FIELDS`,
holding every other vessel-year fixed at an already-solved baseline plan —
the same "everything else held fixed" pattern `exposure.py`'s
`capex_exposure` already uses for its per-decision deltas. This is small
enough (a few hundred to a few thousand joint outcomes) to enumerate
*exactly* via `objective.evaluate` rather than search or train, and the
resulting joint tensor's mutual information is computed by
`tensor_network.py` with no approximation at this scale — a real answer to
a smaller question, not an approximate answer to the full one. Extending
this to a genuinely multi-vessel entangled chain (where bond-dimension
truncation starts to matter) is Track F.

**Where the probabilities come from.** For one vessel-year slot and one
scenario `r`, every combination of that slot's six decision fields is
enumerated, substituted into the baseline plan, and priced with
`objective.evaluate` (unchanged, pure). Costs become a **Boltzmann
distribution** `P(config | r) proportional-to exp(-(cost - min_cost) / T)`
— lower cost, higher probability, the standard way to turn an objective
function into a proper distribution over its own configuration space
without any training data. `P(r)` is uniform across the K=5 scenarios: an
explicit, documented assumption ("no prior over vote outcomes required",
PLAN §1.3), not a fitted or asserted belief about which proposal wins.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

from knotwise.optimization import tensor_network
from knotwise.optimization.genome import DECISION_FIELDS, Genome, field_domains
from knotwise.optimization.objective import ObjectiveCache, evaluate
from knotwise.regulatory.loader import load_scenarios
from knotwise.regulatory.scenario_resolution import resolve_regulations_for_scenario


@dataclass(frozen=True)
class BornMachineTensor:
    """The joint probability tensor `P(r, field_1, ..., field_6)` for one
    vessel-year slot: axis 0 is the K=5 regulatory scenario leg, axes 1-6
    are `fields` in order (matching `genome.DECISION_FIELDS`)."""

    vessel_id: str
    year: int
    tensor: np.ndarray
    fields: tuple[str, ...]
    domains: dict[str, list[Any]]
    scenario_ids: list[str]
    temperature_used: float


def vessel_year_born_machine(
    vessel_id: str,
    year: int,
    fleet: dict[str, Any],
    prices: dict[str, Any],
    baseline_genome: Genome,
    *,
    temperature: float | None = None,
) -> BornMachineTensor:
    """Build `vessel_id`/`year`'s Born-machine tensor by enumerating every
    combination of its own six decision fields under every K=5 scenario,
    pricing each with `objective.evaluate` against `baseline_genome` (every
    other vessel-year held fixed), and converting to a Boltzmann
    distribution per scenario row.

    `temperature`, if not given, defaults to the standard deviation of this
    slot's own enumerated costs (across every scenario and combination) —
    avoids both degenerate argmin-collapse (T too small: only the cheapest
    config gets any probability) and a flat, uninformative distribution (T
    too large). This is an explicit, ILLUSTRATIVE modelling choice, in the
    same spirit as `CostBreakdown.status` labelling elsewhere in this
    codebase — not a fitted or verified parameter.

    Perf note: within one scenario's inner loop, every enumerated combo
    shares the *same* baseline value for the other ~32 vessel-year slots in
    `baseline_genome` -- only this one slot's trial gene changes. An
    `ObjectiveCache`, re-bound automatically every time `regulations`'
    identity changes (i.e. every scenario switch -- the standard "re-bound
    per iteration" idiom `sweep._apply_monotonic_envelope` already uses),
    turns those ~32 other slots' cost computations from "recomputed on every
    combo" into "computed once per scenario, reused for the rest". Measured
    on the case-study fleet's actual unanimous-tier candidate slots (33
    slots at `--fast` settings): `exposure.compute_mps_crosscheck` went from
    94.1s to 22.7s end to end (~2.85s/slot to ~0.69s/slot) once this cache
    was added -- not assumed, timed before and after.
    """
    vessels_by_id = {v["vessel_id"]: v for v in fleet["vessels"]}
    vessel = vessels_by_id[vessel_id]
    domains = field_domains(vessel, fleet, year)
    fields = DECISION_FIELDS
    domain_lists = [domains[f] for f in fields]
    combos = list(itertools.product(*domain_lists))

    slot_index = next(
        i for i, g in enumerate(baseline_genome) if g.vessel_id == vessel_id and g.year == year
    )

    scenario_ids = [s["id"] for s in load_scenarios()["scenarios"]]
    costs = np.empty((len(scenario_ids), len(combos)))
    cache = ObjectiveCache()  # re-bound per scenario (regulations identity changes each r_index); see ObjectiveCache
    for r_index, scenario_id in enumerate(scenario_ids):
        regulations = resolve_regulations_for_scenario(scenario_id)
        for c_index, combo in enumerate(combos):
            trial_gene = replace(baseline_genome[slot_index], **dict(zip(fields, combo)))
            trial_genome = baseline_genome[:slot_index] + [trial_gene] + baseline_genome[slot_index + 1 :]
            costs[r_index, c_index] = evaluate(trial_genome, fleet, regulations, prices, cache=cache).total_usd

    if temperature is None:
        temperature = float(np.std(costs))
        if temperature <= 0.0:
            # Every enumerated config costs the same for this slot -- no
            # information to weight by; fall back to a flat distribution
            # rather than dividing by zero (a scenario-invariant slot is a
            # legitimate, low-exposure outcome, not an error).
            temperature = 1.0

    per_scenario_probs = np.empty_like(costs)
    for r_index in range(len(scenario_ids)):
        row = costs[r_index]
        weights = np.exp(-(row - row.min()) / temperature)
        per_scenario_probs[r_index] = weights / weights.sum()

    joint = per_scenario_probs / len(scenario_ids)  # uniform P(r) = 1/K
    tensor = joint.reshape((len(scenario_ids), *(len(d) for d in domain_lists)))

    return BornMachineTensor(
        vessel_id=vessel_id,
        year=year,
        tensor=tensor,
        fields=fields,
        domains=domains,
        scenario_ids=scenario_ids,
        temperature_used=temperature,
    )


@dataclass(frozen=True)
class MPSVesselYearExposure:
    """One vessel-year slot's real tensor-native exposure: `I(r; field)` in
    bits for each of its six decision fields, plus the tensor's realized
    bond dimensions (reported for transparency — nothing is truncated at
    this scale, see module docstring)."""

    vessel_id: str
    year: int
    mutual_information_bits: dict[str, float]
    bond_dimensions: list[int]
    temperature_used: float


def compute_mps_exposure(
    vessel_id: str,
    year: int,
    fleet: dict[str, Any],
    prices: dict[str, Any],
    baseline_genome: Genome,
    *,
    temperature: float | None = None,
) -> MPSVesselYearExposure:
    """Build the Born machine for one vessel-year slot and read off real
    mutual information between the regulatory leg (axis 0) and each of its
    six decision fields (axes 1-6) — `tensor_network.mutual_information`,
    not a flip-count."""
    born_machine = vessel_year_born_machine(
        vessel_id, year, fleet, prices, baseline_genome, temperature=temperature
    )
    mutual_information_bits = {
        field_name: tensor_network.mutual_information(born_machine.tensor, axis_a=0, axis_b=axis_index)
        for axis_index, field_name in enumerate(born_machine.fields, start=1)
    }
    _, bond_singular_values = tensor_network.tt_svd(born_machine.tensor, max_bond=None)
    bond_dimensions = [len(s) for s in bond_singular_values]

    return MPSVesselYearExposure(
        vessel_id=vessel_id,
        year=year,
        mutual_information_bits=mutual_information_bits,
        bond_dimensions=bond_dimensions,
        temperature_used=born_machine.temperature_used,
    )


@dataclass(frozen=True)
class MPSExposureResult:
    per_slot: list[MPSVesselYearExposure] = field(default_factory=list)

    def ranked(self) -> list[tuple[str, int, str, float]]:
        """Every (vessel_id, year, field, mutual_information_bits) row,
        highest exposure first — the tensor-native counterpart of
        `exposure.py`'s `per_decision_deltas` drill-down list."""
        rows = [
            (slot.vessel_id, slot.year, field_name, mi)
            for slot in self.per_slot
            for field_name, mi in slot.mutual_information_bits.items()
        ]
        return sorted(rows, key=lambda row: row[3], reverse=True)


def compute_mps_exposure_map(
    fleet: dict[str, Any],
    prices: dict[str, Any],
    baseline_genome: Genome,
    *,
    vessel_years: list[tuple[str, int]] | None = None,
) -> MPSExposureResult:
    """Run `compute_mps_exposure` over `vessel_years` (every vessel-year
    slot in `fleet` by default). Cost is linear in the number of slots —
    each slot's own enumeration is independent of every other slot's — so
    `vessel_years` lets a caller price a handful of candidates (e.g. the
    ones `exposure.py`'s flip-counting already flagged) instead of the
    whole fleet, when only a cross-check is needed rather than the full map.
    """
    if vessel_years is None:
        vessel_years = [(v["vessel_id"], y) for v in fleet["vessels"] for y in fleet["horizon_years"]]
    per_slot = [
        compute_mps_exposure(vessel_id, year, fleet, prices, baseline_genome)
        for vessel_id, year in vessel_years
    ]
    return MPSExposureResult(per_slot=per_slot)


@dataclass(frozen=True)
class ExposureComparisonRow:
    """One (vessel_id, year, field) slot's tensor-native reading next to
    `exposure.py`'s classical flip-counting label — PLAN §8.3(b)'s
    cross-check, now runnable in both directions instead of only the
    classical side existing."""

    vessel_id: str
    year: int
    decision: str
    mutual_information_bits: float
    classical_status: str  # "exposed" | "unstable" | "not_exposed"


def compare_with_classical(mps_result: MPSExposureResult, classical_result: Any) -> list[ExposureComparisonRow]:
    """Label each MPS row with what `exposure.py`'s independently-computed,
    already-expensive `ExposureResult` (`exposure.compute_exposure`'s
    return value) says about that same (vessel_id, year, field) slot.
    Additive only: neither this function nor `compute_mps_exposure_map`
    requires `classical_result` to run — call this only when a classical
    run is already available and a cross-check is wanted.
    """
    exposed_keys = {(d.vessel_id, d.year, d.decision) for d in classical_result.per_decision_deltas}
    unstable_keys = {(d.vessel_id, d.year, d.decision) for d in classical_result.unstable_decisions}

    rows = []
    for slot in mps_result.per_slot:
        for field_name, mi in slot.mutual_information_bits.items():
            key = (slot.vessel_id, slot.year, field_name)
            if key in exposed_keys:
                status = "exposed"
            elif key in unstable_keys:
                status = "unstable"
            else:
                status = "not_exposed"
            rows.append(ExposureComparisonRow(slot.vessel_id, slot.year, field_name, mi, status))
    return sorted(rows, key=lambda row: row.mutual_information_bits, reverse=True)


def comparison_rows_to_dicts(rows: list[ExposureComparisonRow]) -> list[dict[str, Any]]:
    """A JSON-serializable view of `compare_with_classical`'s output —
    the module that owns `ExposureComparisonRow` owns its serialization,
    mirroring `exposure.py`'s own `_exposed_decision_to_dict` pattern
    rather than leaving a caller (`scripts/build_demo_data.py`) to reach
    into the dataclass's fields itself."""
    return [
        {
            "vessel_id": row.vessel_id,
            "year": row.year,
            "decision": row.decision,
            "mutual_information_bits": row.mutual_information_bits,
            "classical_status": row.classical_status,
        }
        for row in rows
    ]
