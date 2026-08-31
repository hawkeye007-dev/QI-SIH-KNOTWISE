"""Shared cost-breakdown type (Task 2R component 3, item 4 — output labeling).

A tiny standalone module rather than living in `objective.py`: both
`compliance_cost.py` and `objective.py` need `CostBreakdown`, and
`objective.py` composes `compliance_cost.py`'s output, so the type has to
live somewhere neither depends on the other to reach.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Every CostBreakdown.status must be one of these — enforced by
#: knotwise.optimization.objective, not by the dataclass itself (dataclasses
#: don't validate field values on construction without extra machinery, and
#: a hard-coded Literal type would make this list harder to see in one place).
VALID_STATUSES = (
    "ILLUSTRATIVE",
    "PROXY",
    "SECONDARY_SOURCE",
    "MARKET_QUOTE",
    "VERIFIED_PER_DOCUMENT",
    "NOT_APPLICABLE",
    "NOT_APPLICABLE_NO_DIRECT_PENALTY",
    "NOT_APPLICABLE_NO_PRICE_BASIS",
)


@dataclass(frozen=True)
class CostBreakdown:
    """A cost figure that never travels without the confidence label it needs.

    Per Task 2R component 3 item 4: "every rupee/dollar figure in outputs
    programmatically carries the model status" — this is the type that makes
    that mechanically true rather than a convention someone can forget.
    """

    amount_usd: float
    status: str
    notes: str = field(default="")
