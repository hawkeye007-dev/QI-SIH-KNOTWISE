"""Shared loader for the regulatory JSON data files.

Single point of access so every consumer (tests, `knotwise.compliance`, later
phases) reads `regulations.json` / `scenarios.json` the same way, rather than
each caller reimplementing its own `importlib.resources` call.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


def _load_json(name: str) -> dict[str, Any]:
    return json.loads(resources.files("knotwise.regulatory").joinpath(name).read_text())


@lru_cache(maxsize=1)
def load_regulations() -> dict[str, Any]:
    """Load `regulations.json` (cached — the file is static package data)."""
    return _load_json("regulations.json")


@lru_cache(maxsize=1)
def load_scenarios() -> dict[str, Any]:
    """Load `scenarios.json` (cached — the file is static package data)."""
    return _load_json("scenarios.json")
