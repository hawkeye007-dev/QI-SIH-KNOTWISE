"""Per-regime compliance-cost formulas (Task 2R component 3).

Reuses `knotwise.compliance.scope_gating.RegimeApplicability` (for
`applies`/`effective_obligation_fraction` — never recomputed here) and
`knotwise.regulatory.implied_price.{fueleu_compliance_balance_gco2eq,
fueleu_penalty_eur}` (the Annex-IV-derived FuelEU formula — not
reimplemented). Every function takes a **resolved** regime dict (i.e. the
output of `scenario_resolution.resolve_regulations_for_scenario`, or a
hand-built one in tests) — nothing here ever branches on scenario_id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knotwise.compliance.scope_gating import RegimeApplicability
from knotwise.optimization.costs import CostBreakdown
from knotwise.regulatory.implied_price import fueleu_compliance_balance_gco2eq, fueleu_penalty_eur

#: Borrowing-cap base (Task 2R component 3 "minor correction" — this
#: operationalization is flagged in regulations.json's
#: fuel_eu.flexibility_mechanisms.borrowing.cap_base_status as sharing the
#: same Annex-IV-needs-primary-source-check scope as the penalty formula):
#: "2% of the limit" is interpreted as 2% of (target intensity x energy
#: consumed), i.e. 2% of the gCO2e a fully-compliant ship would be allowed,
#: not 2% of raw MJ (which would be dimensionally wrong against a gCO2e balance).
BORROW_CAP_FRACTION = 0.02
BORROW_REPAYMENT_MULTIPLIER = 1.1


def fueleu_target_intensity(fuel_eu_regime: dict[str, Any], year: int) -> float:
    """FuelEU's target GHG intensity for `year`, from its step-function reduction schedule.

    The schedule is flat within each 5-year block (e.g. 2025-2029 is all -2%),
    not interpolated — see regulations.json's fuel_eu.reduction_schedule_status.
    """
    baseline = fuel_eu_regime["ghg_intensity_baseline_gco2e_per_mj"]
    schedule = fuel_eu_regime["reduction_schedule_percent"]
    applicable_threshold_years = sorted(int(y) for y in schedule)
    percent = 0.0
    for threshold_year in applicable_threshold_years:
        if year >= threshold_year:
            percent = schedule[str(threshold_year)]
    return baseline * (1 - percent / 100)


def cii_cost(applicability: RegimeApplicability) -> CostBreakdown:  # applicability kept for a uniform per-regime call signature
    """CII has no direct financial penalty (PLAN.md §3.6) — always $0.

    See `knotwise.regulatory.implied_price.cii_implied_price` for the optional
    corrective-action-cost proxy route, not wired in here per the task's own
    framing ("flag... implied price available if needed later"). CII rating
    computation (A-E bands) is out of scope this pass — see Task 2R component
    3's plan, non-goals: it needs MEPC.338(76) reference-curve boundary
    constants not sourced this session.
    """
    return CostBreakdown(
        amount_usd=0.0,
        status="NOT_APPLICABLE_NO_DIRECT_PENALTY",
        notes="CII has no direct financial penalty. Rating computation not built this pass.",
    )


def eu_ets_cost(
    applicability: RegimeApplicability,
    actual_ghg_intensity_gco2e_per_mj: float,
    energy_used_mj: float,
    eua_price_entry: dict[str, Any],
) -> CostBreakdown:
    """EU ETS: pay for what's actually emitted, scaled by voyage-share x phase-in.

    Real cap-and-trade mechanic — not a deficit-from-target formula like
    FuelEU/NZF. `eua_price_entry` is `prices.json`'s
    `carbon_allowances.eu_ets_eua` (or an equivalent dict with
    `price_usd_per_tco2e` and `status`), passed in rather than loaded here so
    this function stays pure and testable without touching disk.
    """
    if not applicability.applies:
        return CostBreakdown(0.0, "NOT_APPLICABLE", "EU ETS does not apply.")

    allowances_tonnes = actual_ghg_intensity_gco2e_per_mj * energy_used_mj / 1e6
    amount = allowances_tonnes * applicability.effective_obligation_fraction * eua_price_entry["price_usd_per_tco2e"]
    return CostBreakdown(
        amount_usd=amount,
        status=eua_price_entry["status"],
        notes="allowances (tonnes actually emitted) x voyage-share x phase-in x EUA price.",
    )


@dataclass(frozen=True)
class NzfGaps:
    """The two-tier gap decomposition `nzf_cost` prices — factored out so a
    consumer that needs the gaps themselves (Task 2R component 4's
    switching-point sweep computes each scenario's fleet-wide operating point
    from these) doesn't re-derive the base/compliance-target arithmetic."""

    gap_tier1_gco2e_per_mj: float
    gap_tier2_gco2e_per_mj: float
    gap_surplus_gco2e_per_mj: float
    base_target_gco2e_per_mj: float
    compliance_target_gco2e_per_mj: float


def nzf_gaps(nzf_regime: dict[str, Any], year: int, actual_ghg_intensity_gco2e_per_mj: float) -> NzfGaps | None:
    """The NZF two-tier gap decomposition for one vessel-year, or `None` when
    `year` has no two-tier trajectory data for this regime.

    - Tier 1: the gap between the direct compliance target and the (less
      strict) base target.
    - Tier 2: any further gap beyond the base target.
    - Surplus: over-performance beyond the direct compliance target.
    """
    year_key = str(year)
    if year_key not in nzf_regime["base_target_reduction_percent"]:
        return None

    reference = nzf_regime["reference_intensity_gco2e_per_mj"]
    base_target = reference * (1 - nzf_regime["base_target_reduction_percent"][year_key] / 100)
    compliance_target = reference * (1 - nzf_regime["direct_compliance_target_reduction_percent"][year_key] / 100)

    return NzfGaps(
        gap_tier1_gco2e_per_mj=max(min(actual_ghg_intensity_gco2e_per_mj, base_target) - compliance_target, 0.0),
        gap_tier2_gco2e_per_mj=max(actual_ghg_intensity_gco2e_per_mj - base_target, 0.0),
        gap_surplus_gco2e_per_mj=max(compliance_target - actual_ghg_intensity_gco2e_per_mj, 0.0),
        base_target_gco2e_per_mj=base_target,
        compliance_target_gco2e_per_mj=compliance_target,
    )


def nzf_cost(
    nzf_regime: dict[str, Any],
    applicability: RegimeApplicability,
    year: int,
    actual_ghg_intensity_gco2e_per_mj: float,
    energy_used_mj: float,
) -> CostBreakdown:
    """NZF's two-tier GFI structure: deficit priced at Tier 1/Tier 2, surplus valued
    at its own decoupled price (Task 2R component 3 correction 3).

    Surplus is valued via `surplus_unit_value_usd_per_tco2e` — a field
    deliberately decoupled from `tier_prices_usd_per_tco2e` (see that field's
    own note in regulations.json/scenarios.json for why: tying them together
    left the `liberia` scenario indistinguishable from `adoption_fails`).

    Either side is $0 when its resolved-scenario price is `null` (e.g.
    Brazil's deficit side, explicitly deferred to the not-built-this-pass
    implied-price converter) rather than silently treated as compliant.
    """
    if not applicability.applies:
        return CostBreakdown(0.0, "NOT_APPLICABLE", "NZF does not apply (disabled, or year is before its start_year).")

    gaps = nzf_gaps(nzf_regime, year, actual_ghg_intensity_gco2e_per_mj)
    if gaps is None:
        return CostBreakdown(0.0, "NOT_APPLICABLE", f"No NZF two-tier trajectory data for {year}.")

    tonnes = energy_used_mj / 1e6

    tier_prices = nzf_regime["tier_prices_usd_per_tco2e"]
    deficit_cost = 0.0
    if tier_prices is not None:
        # Each tier priced independently — a proposal may state only Tier 1
        # (e.g. Tuvalu, whose tier_2 is null rather than guessed): that tier's
        # gap then contributes $0, not a crash, and not a silently-assumed price.
        if tier_prices.get("tier_1") is not None:
            deficit_cost += gaps.gap_tier1_gco2e_per_mj * tier_prices["tier_1"]
        if tier_prices.get("tier_2") is not None:
            deficit_cost += gaps.gap_tier2_gco2e_per_mj * tier_prices["tier_2"]
        deficit_cost *= tonnes

    surplus_price = nzf_regime["surplus_unit_value_usd_per_tco2e"]
    surplus_value = 0.0
    if surplus_price is not None:
        surplus_value = gaps.gap_surplus_gco2e_per_mj * tonnes * surplus_price

    net = deficit_cost - surplus_value
    status = (
        "SECONDARY_SOURCE"
        if (tier_prices is not None or surplus_price is not None)
        # Regime *applies* here (unlike the early-return above) — this scenario
        # just has no price basis for either side (e.g. Brazil, deferred to the
        # not-built-this-pass implied-price converter). Distinct from
        # "NOT_APPLICABLE" (the regime itself doesn't apply this vessel-year)
        # precisely so this doesn't collapse to the same status as adoption_fails.
        else "NOT_APPLICABLE_NO_PRICE_BASIS"
    )
    return CostBreakdown(
        amount_usd=net,
        status=status,
        notes=(
            f"deficit_cost={deficit_cost:.2f}, surplus_value={surplus_value:.2f} "
            f"(base_target={gaps.base_target_gco2e_per_mj:.3f}, "
            f"compliance_target={gaps.compliance_target_gco2e_per_mj:.3f} gCO2e/MJ)"
        ),
    )


@dataclass(frozen=True)
class FuelEuYearInput:
    year: int
    actual_ghg_intensity_gco2e_per_mj: float
    energy_used_mj: float
    borrow_election: bool = False
    pooled: bool = False


@dataclass(frozen=True)
class FuelEuYearResult:
    year: int
    raw_balance_gco2eq: float
    banked_surplus_after_gco2eq: float
    borrowed: bool
    cost: CostBreakdown = field(default_factory=lambda: CostBreakdown(0.0, "NOT_APPLICABLE"))


def compute_fueleu_ledger(
    fuel_eu_regime: dict[str, Any],
    year_inputs: list[FuelEuYearInput],
    eur_to_usd_rate: float,
) -> list[FuelEuYearResult]:
    """FuelEU's banking/borrowing state machine, folded sequentially over one vessel's horizon.

    - A pooled year is skipped entirely by this ledger (banked surplus carries
      through unchanged, no new borrowing/penalty computed here) — the pool
      computation in `pooling.py` is authoritative for that vessel-year, per
      DESIGN_NOTE_POOLING.md §2B.
    - Otherwise: banked surplus offsets a deficit first; if a deficit remains
      and the caller elected to borrow *and* the vessel didn't borrow last
      period (hard override — not left to the GA to learn), borrow up to
      `BORROW_CAP_FRACTION` of (target intensity x energy consumed); any
      still-unresolved deficit is priced via `fueleu_penalty_eur`; the
      borrowed amount is rolled into *next* period's effective balance at
      `BORROW_REPAYMENT_MULTIPLIER` (repayment).
    - A surplus (no deficit) banks forward unconditionally (never expires).
    """
    results: list[FuelEuYearResult] = []
    banked_surplus = 0.0
    borrowed_last_period = False
    pending_repayment = 0.0

    for year_input in year_inputs:
        target = fueleu_target_intensity(fuel_eu_regime, year_input.year)
        raw_balance = fueleu_compliance_balance_gco2eq(
            target, year_input.actual_ghg_intensity_gco2e_per_mj, year_input.energy_used_mj
        )

        if year_input.pooled:
            results.append(
                FuelEuYearResult(
                    year=year_input.year,
                    raw_balance_gco2eq=raw_balance,
                    banked_surplus_after_gco2eq=banked_surplus,
                    borrowed=False,
                    cost=CostBreakdown(
                        0.0, "NOT_APPLICABLE", "Pooled this year — see pooling.resolve_pool for the authoritative cost."
                    ),
                )
            )
            continue

        balance = raw_balance - pending_repayment
        pending_repayment = 0.0
        borrowed_this_period = False

        if balance >= 0:
            banked_surplus += balance
            cost = CostBreakdown(0.0, "SECONDARY_SOURCE", "Surplus — banked forward, no penalty.")
        else:
            deficit = -balance
            offset = min(banked_surplus, deficit)
            banked_surplus -= offset
            deficit -= offset

            if deficit > 0 and year_input.borrow_election and not borrowed_last_period:
                cap = BORROW_CAP_FRACTION * target * year_input.energy_used_mj
                borrow_amount = min(deficit, cap)
                deficit -= borrow_amount
                pending_repayment = borrow_amount * BORROW_REPAYMENT_MULTIPLIER
                borrowed_this_period = True

            if deficit > 0:
                penalty_eur = fueleu_penalty_eur(-deficit, year_input.actual_ghg_intensity_gco2e_per_mj)
                cost = CostBreakdown(
                    penalty_eur * eur_to_usd_rate,
                    "SECONDARY_SOURCE",
                    "Unresolved deficit after banking/borrowing.",
                )
            else:
                cost = CostBreakdown(0.0, "SECONDARY_SOURCE", "Deficit fully offset by banking/borrowing.")

        borrowed_last_period = borrowed_this_period
        results.append(
            FuelEuYearResult(
                year=year_input.year,
                raw_balance_gco2eq=raw_balance,
                banked_surplus_after_gco2eq=banked_surplus,
                borrowed=borrowed_this_period,
                cost=cost,
            )
        )

    return results
