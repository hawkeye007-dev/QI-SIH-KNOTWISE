"""Implied-price converter (PLAN.md §3.6(b), §5 Phase 0).

CII has no direct financial penalty; its consequence is a SEEMP Part III
corrective-action-plan obligation. FuelEU has a penalty formula but it is not a
posted per-tonne market price the way the NZF tiers or the EUA spot price are.
Scenario 5 ("adoption fails") and the "brazil" scenario in scenarios.json cannot be
placed on the same effective-marginal-carbon-price axis as the other scenarios
without converting their actual consequence into a $/tCO2e figure — under
*explicit, stated* assumptions, never a silently-invented flat price (PLAN.md
§3.6(b): "Any figure that looks like a single point for a tiered proposal is a
modelling choice, and the chart says so.").

Both public functions therefore return an :class:`ImpliedPrice`, which pairs the
number with the assumptions that produced it — never a bare float. Anything
downstream (the carbon-price sweep in Phase 3, the switching-point chart in the
demo) that drops the ``assumptions`` half is misrepresenting a modelling choice as
a market fact.

FuelEU penalty formula caveat: Annex IV Part B of Regulation (EU) 2023/1805 could
not be retrieved as primary-source text in this session (the EUR-Lex PDF did not
extract cleanly). The formula implemented here is reconstructed from secondary
summaries (see regulations.json's ``fuel_eu.penalty_formula.sources``) and must be
cross-checked against the primary regulation text before it gates any real
compliance-ledger number in Phase 4.
"""

from __future__ import annotations

from dataclasses import dataclass, field

FUELEU_PENALTY_RATE_EUR_PER_TONNE_VLSFOEQ = 2400.0
VLSFO_ENERGY_DENSITY_MJ_PER_TONNE = 41000.0


@dataclass(frozen=True)
class ImpliedPrice:
    """An effective marginal carbon price plus the assumptions that produced it.

    ``value_usd_per_tco2e`` is intentionally never returned on its own — per
    PLAN.md §3.6(b), a figure like this is a modelling choice, and every consumer
    of it must see the assumptions alongside the number.
    """

    value_usd_per_tco2e: float
    assumptions: dict = field(default_factory=dict)


def cii_implied_price(
    corrective_action_cost_usd: float,
    co2e_shortfall_addressed_tonnes: float,
    *,
    cost_capitalization_years: int = 1,
) -> ImpliedPrice:
    """Convert a CII corrective-action-plan cost into an effective $/tCO2e figure.

    CII carries no posted per-tonne price (PLAN.md §3.6(b)): its consequence is a
    SEEMP Part III corrective-action-plan obligation and reputational/charter-party
    risk. This capitalises a *stated* corrective-action cost over its
    capitalization horizon and divides by the tonnes of CO2e shortfall it is meant
    to address — the caller supplies both inputs; nothing here is looked up from a
    market.

    Args:
        corrective_action_cost_usd: the total cost of the corrective action (e.g.
            a SEEMP Part III retrofit or operational change), in USD.
        co2e_shortfall_addressed_tonnes: tonnes of CO2e shortfall the action
            addresses. Must be positive.
        cost_capitalization_years: number of years over which the cost is
            capitalised (straight-line). Defaults to 1 (treat the full cost as a
            single-year consequence) — an explicit, overridable assumption, not a
            hidden default that silently discounts the cost.

    Returns:
        An :class:`ImpliedPrice` carrying the figure and every assumption used to
        produce it.
    """
    if co2e_shortfall_addressed_tonnes <= 0:
        raise ValueError("co2e_shortfall_addressed_tonnes must be positive")
    if cost_capitalization_years <= 0:
        raise ValueError("cost_capitalization_years must be positive")

    annualized_cost_usd = corrective_action_cost_usd / cost_capitalization_years
    price = annualized_cost_usd / co2e_shortfall_addressed_tonnes

    return ImpliedPrice(
        value_usd_per_tco2e=price,
        assumptions={
            "method": (
                "capitalise the stated SEEMP Part III corrective-action cost "
                "straight-line over cost_capitalization_years, divide by the "
                "tonnes of CO2e shortfall it addresses"
            ),
            "cost_capitalization_years": cost_capitalization_years,
            "caveat": (
                "CII carries no posted per-tonne price (PLAN.md §3.6b); this "
                "is a modelling choice, not a market figure."
            ),
        },
    )


def fueleu_compliance_balance_gco2eq(
    ghg_intensity_target_gco2e_per_mj: float,
    ghg_intensity_actual_gco2e_per_mj: float,
    energy_used_mj: float,
) -> float:
    """FuelEU compliance balance, in gCO2eq (positive = surplus, negative = deficit).

    Formula (secondary-sourced — see module docstring):
        (target - actual) [gCO2eq/MJ] * energy_used [MJ]
    """
    return (ghg_intensity_target_gco2e_per_mj - ghg_intensity_actual_gco2e_per_mj) * energy_used_mj


def fueleu_penalty_eur(
    compliance_balance_gco2eq: float,
    ghg_intensity_actual_gco2e_per_mj: float,
    *,
    n_consecutive_deficit_periods: int = 1,
) -> float:
    """FuelEU Annex IV Part B penalty, in EUR, for a single ship and period.

    Returns 0.0 when ``compliance_balance_gco2eq`` is non-negative (no deficit).
    Formula (secondary-sourced — see module docstring):
        abs(CB) / (ghg_actual * 41000) * 2400 * (1 + (n - 1) / 10)
    """
    if ghg_intensity_actual_gco2e_per_mj <= 0:
        raise ValueError("ghg_intensity_actual_gco2e_per_mj must be positive")
    if n_consecutive_deficit_periods < 1:
        raise ValueError("n_consecutive_deficit_periods must be >= 1")
    if compliance_balance_gco2eq >= 0:
        return 0.0

    base_penalty = (
        abs(compliance_balance_gco2eq)
        / (ghg_intensity_actual_gco2e_per_mj * VLSFO_ENERGY_DENSITY_MJ_PER_TONNE)
        * FUELEU_PENALTY_RATE_EUR_PER_TONNE_VLSFOEQ
    )
    multiplier = 1 + (n_consecutive_deficit_periods - 1) / 10
    return base_penalty * multiplier


def fueleu_implied_price(
    compliance_balance_gco2eq: float,
    ghg_intensity_actual_gco2e_per_mj: float,
    *,
    n_consecutive_deficit_periods: int = 1,
    eur_to_usd_rate: float = 1.0,
) -> ImpliedPrice:
    """Convert a FuelEU deficit into an effective $/tCO2e figure.

    Converts the deficit's compliance-balance units (gCO2eq, a GHG-intensity-
    weighted regulatory unit) into tonnes by dividing by 1e6 and treating that as
    a literal tonnes-of-CO2e-equivalent figure — an explicit assumption stated
    here, not hidden, because compliance-balance gCO2eq is not literally the same
    thing as physically emitted CO2e mass.

    Note: under that assumption, the deficit magnitude cancels out of the
    resulting $/tCO2e figure algebraically — the implied price depends only on
    the ship's actual GHG intensity, the consecutive-deficit multiplier, and the
    FX rate, not on how large the deficit is. That is a real structural
    consequence of the assumption above, not a bug, and is worth knowing before
    trusting this number: it means this converter answers "what is the marginal
    price of a unit of FuelEU deficit for this ship", not "what would this
    specific ship's total penalty imply about the market".

    Requires ``compliance_balance_gco2eq < 0`` (only a deficit has a price to
    convert).
    """
    if compliance_balance_gco2eq >= 0:
        raise ValueError(
            "fueleu_implied_price is only defined for a deficit "
            "(compliance_balance_gco2eq < 0); a surplus has no penalty to convert"
        )
    if eur_to_usd_rate <= 0:
        raise ValueError("eur_to_usd_rate must be positive")

    penalty_eur = fueleu_penalty_eur(
        compliance_balance_gco2eq,
        ghg_intensity_actual_gco2e_per_mj,
        n_consecutive_deficit_periods=n_consecutive_deficit_periods,
    )
    penalty_usd = penalty_eur * eur_to_usd_rate
    co2e_shortfall_tonnes = abs(compliance_balance_gco2eq) / 1e6
    price = penalty_usd / co2e_shortfall_tonnes

    return ImpliedPrice(
        value_usd_per_tco2e=price,
        assumptions={
            "method": (
                "compute the Annex IV Part B penalty for the given deficit, "
                "convert compliance-balance gCO2eq to tonnes by dividing by 1e6 "
                "(treating regulatory gCO2eq units as literal CO2e mass), divide "
                "penalty by that tonnage"
            ),
            "n_consecutive_deficit_periods": n_consecutive_deficit_periods,
            "eur_to_usd_rate": eur_to_usd_rate,
            "caveat": (
                "Result is algebraically independent of the deficit's magnitude "
                "under this conversion (see docstring); it depends only on "
                "ghg_intensity_actual, the consecutive-deficit multiplier, and "
                "the FX rate. Penalty formula itself is secondary-sourced — see "
                "module docstring — and needs primary-source cross-check before "
                "gating a real compliance-ledger number."
            ),
        },
    )
