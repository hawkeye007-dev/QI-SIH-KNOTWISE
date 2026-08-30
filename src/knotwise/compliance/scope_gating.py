"""Scope-gating engine (Task 2; PLAN.md §3.4, §5.4, Phase 4 pulled forward).

Given a vessel, its voyage pattern, and a year, decides which of the four
regimes (CII, NZF, FuelEU, EU ETS) apply and at what voyage share — pure logic,
no ML, no data dependency beyond `regulations.json`. Every threshold (GT
boundary, regime start year, voyage-share weights, EU ETS phase-in) is read
from `regulations.json`, never inlined here, so a regulatory constant only
ever needs updating in one place.

No band-specific branching exists in this module: PLAN.md §5.4's Band A/B/C
outcomes (see docs/scope_matrix.md) fall out of the general formula below —
e.g. Band B's "CII+NZF only" is a consequence of its voyage having zero EU/EEA
exposure, not a special case coded for that band.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knotwise.regulatory.loader import load_regulations

_FRACTIONAL_FIELDS = (
    "intra_eu_eea_voyage_fraction",
    "eu_eea_berth_fraction",
    "eu_eea_third_country_voyage_fraction",
)


@dataclass(frozen=True)
class VesselSpec:
    gross_tonnage: float


@dataclass(frozen=True)
class VoyagePattern:
    """Shares of a vessel's annual energy, by regulatory voyage category.

    `is_international` gates CII/NZF (which are not fractional: "international
    voyages" is a yes/no condition, not a share). The three EU/EEA fractions
    gate FuelEU/EU ETS and may leave a remainder implicitly outside EU/EEA
    scope (e.g. domestic Indian legs, or non-EU international legs such as
    India-Gulf) — that remainder is 0%-weighted and does not need its own field.
    """

    is_international: bool
    intra_eu_eea_voyage_fraction: float = 0.0
    eu_eea_berth_fraction: float = 0.0
    eu_eea_third_country_voyage_fraction: float = 0.0

    def __post_init__(self) -> None:
        total = 0.0
        for name in _FRACTIONAL_FIELDS:
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {value}")
            total += value
        if total > 1.0 + 1e-9:
            raise ValueError(f"voyage fractions must sum to <= 1.0, got {total}")


@dataclass(frozen=True)
class RegimeApplicability:
    applies: bool
    voyage_share: float
    phase_in_fraction: float
    effective_obligation_fraction: float
    notes: str = field(default="")


def eu_ets_phase_in_fraction(emissions_year: int, regulations: dict[str, Any]) -> float:
    """EU ETS phase-in fraction for a given emissions year (0.0-1.0).

    Inverts `phase_in_by_surrender_year` (keyed by surrender year, each entry
    naming the emissions year it corresponds to) into an emissions-year lookup,
    falling back to `phase_in_2026_onward_percent` for any year past the table
    — both fields already exist in regulations.json; nothing is duplicated here.
    """
    eu_ets = regulations["regimes"]["eu_ets"]
    by_emissions_year = {
        entry["emissions_year"]: entry["percent_of_emissions_surrendered"] / 100
        for entry in eu_ets["phase_in_by_surrender_year"].values()
    }
    if emissions_year in by_emissions_year:
        return by_emissions_year[emissions_year]
    if emissions_year > max(by_emissions_year):
        return eu_ets["phase_in_2026_onward_percent"] / 100
    raise ValueError(f"no EU ETS phase-in data for emissions_year={emissions_year}")


def _whole_voyage_regime(vessel: VesselSpec, voyage: VoyagePattern, year: int, regime: dict[str, Any]) -> RegimeApplicability:
    """CII / NZF: not fractional — applies wholly to a qualifying international voyage, or not at all."""
    applies = (
        regime.get("enabled", True)
        and vessel.gross_tonnage >= regime["gt_threshold"]
        and voyage.is_international
        and year >= regime["start_year"]
    )
    share = 1.0 if applies else 0.0
    return RegimeApplicability(
        applies=applies,
        voyage_share=share,
        phase_in_fraction=1.0,
        effective_obligation_fraction=share,
        notes=f"gt_threshold={regime['gt_threshold']}, start_year={regime['start_year']}",
    )


def _fractional_regime(
    vessel: VesselSpec,
    voyage: VoyagePattern,
    year: int,
    regime: dict[str, Any],
    phase_in_fraction: float,
) -> RegimeApplicability:
    """FuelEU / EU ETS: geographic voyage-share fraction, gated by GT and start year."""
    weights = regime["voyage_share_percent"]
    weight_100 = weights["intra_eu_eea_or_at_berth"] / 100
    weight_50 = weights["eu_eea_to_third_country"] / 100
    voyage_share = (
        (voyage.intra_eu_eea_voyage_fraction + voyage.eu_eea_berth_fraction) * weight_100
        + voyage.eu_eea_third_country_voyage_fraction * weight_50
    )
    applies = (
        regime.get("enabled", True)
        and vessel.gross_tonnage >= regime["gt_threshold"]
        and year >= regime["start_year"]
        and voyage_share > 0
    )
    effective = voyage_share * phase_in_fraction if applies else 0.0
    return RegimeApplicability(
        applies=applies,
        voyage_share=voyage_share,
        phase_in_fraction=phase_in_fraction,
        effective_obligation_fraction=effective,
        notes=f"gt_threshold={regime['gt_threshold']}, start_year={regime['start_year']}",
    )


def applicable_regimes(
    vessel: VesselSpec,
    voyage: VoyagePattern,
    year: int,
    regulations: dict[str, Any] | None = None,
) -> dict[str, RegimeApplicability]:
    """Which of the four regimes apply to `vessel` under `voyage` in `year`, and at what share.

    Returns one :class:`RegimeApplicability` per regime, keyed "cii", "nzf",
    "fuel_eu", "eu_ets" — FuelEU and EU ETS are always reported separately,
    never netted against each other, even when both apply to the same vessel
    (PLAN.md §3.2: they stack).
    """
    if regulations is None:
        regulations = load_regulations()
    regimes = regulations["regimes"]

    eu_ets_regime = regimes["eu_ets"]
    eu_ets_phase_in = (
        eu_ets_phase_in_fraction(year, regulations) if year >= eu_ets_regime["start_year"] else 0.0
    )

    return {
        "cii": _whole_voyage_regime(vessel, voyage, year, regimes["cii"]),
        "nzf": _whole_voyage_regime(vessel, voyage, year, regimes["nzf"]),
        "fuel_eu": _fractional_regime(vessel, voyage, year, regimes["fuel_eu"], phase_in_fraction=1.0),
        "eu_ets": _fractional_regime(vessel, voyage, year, eu_ets_regime, phase_in_fraction=eu_ets_phase_in),
    }
