"""Resolve one regulatory view per scenario (Task 2R component 2).

`scenarios.json` carries a partial `regulatory_overrides` object per scenario —
just the fields that scenario changes relative to the base `regulations.json`
(which already represents the "approved_text" position). This module merges
the two into one concrete, `regulations.json`-shaped view per scenario, so
downstream consumers (component 3's solver, and `scope_gating.applicable_regimes`)
read a single resolved dict and never need an `if scenario_id == ...` branch.
"""

from __future__ import annotations

import copy
from typing import Any

from knotwise.regulatory.loader import load_regulations, load_scenarios


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge `overrides` onto `base`, in place, and return it.

    A dict value merges key-by-key (recursing); any other value (including
    `null`/`None`, which several overrides use deliberately — e.g. "no posted
    tier price under this proposal") replaces the base value outright.
    """
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def resolve_regulations_for_scenario(
    scenario_id: str,
    regulations: dict[str, Any] | None = None,
    scenarios: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a `regulations.json`-shaped dict with `scenario_id`'s overrides applied.

    Never mutates the cached `load_regulations()`/`load_scenarios()` results —
    always deep-copies before merging.
    """
    if regulations is None:
        regulations = load_regulations()
    if scenarios is None:
        scenarios = load_scenarios()

    matches = [s for s in scenarios["scenarios"] if s["id"] == scenario_id]
    if not matches:
        known = sorted(s["id"] for s in scenarios["scenarios"])
        raise ValueError(f"unknown scenario_id {scenario_id!r}; known scenarios: {known}")
    scenario = matches[0]

    resolved = copy.deepcopy(regulations)
    for regime_name, regime_overrides in scenario["regulatory_overrides"].items():
        _deep_merge(resolved["regimes"][regime_name], regime_overrides)
    return resolved
