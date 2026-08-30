"""Shared loader for the fleet JSON data files — mirrors `knotwise.regulatory.loader`."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


def _load_json(name: str) -> dict[str, Any]:
    return json.loads(resources.files("knotwise.fleet").joinpath(name).read_text())


@lru_cache(maxsize=1)
def load_fleet() -> dict[str, Any]:
    """Load `fleet.json` (cached — the file is static package data)."""
    return _load_json("fleet.json")


@lru_cache(maxsize=1)
def load_prices() -> dict[str, Any]:
    """Load `prices.json` (cached — the file is static package data)."""
    return _load_json("prices.json")
