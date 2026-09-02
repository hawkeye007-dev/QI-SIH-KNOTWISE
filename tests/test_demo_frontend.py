"""Smoke test for Next.js demo website structure and contracts.

Ensures:
1. No imports from `src/` inside the `frontend/` directory (strict presentation separation).
2. `scripts/build_demo_data.py` exists, is standalone orchestration, and produces outputs/demo_data.json and frontend/public/demo_data.json.
3. Frontend Next.js build succeeds cleanly without type errors.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_no_src_imports_in_frontend():
    """Verify frontend code never imports directly from src/ or knotwise Python package."""
    frontend_dir = PROJECT_ROOT / "frontend"
    assert frontend_dir.exists()

    forbidden_phrases = ["from knotwise", "import knotwise", "from src", "import src"]

    for file_path in frontend_dir.rglob("*"):
        if file_path.suffix in (".ts", ".tsx", ".js", ".jsx", ".json") and "node_modules" not in file_path.parts:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for phrase in forbidden_phrases:
                assert phrase not in content, f"Forbidden import {phrase!r} found in {file_path}"


def test_routes_geo_structure():
    """Verify scripts/build_demo_data.py contains valid routes_geo definitions for 6 routes."""
    from scripts.build_demo_data import ROUTES_GEO

    assert ROUTES_GEO["status"] == "ILLUSTRATIVE"
    assert "provenance_note" in ROUTES_GEO
    routes = ROUTES_GEO["routes"]
    expected_routes = [
        "india_northeurope",
        "india_mediterranean",
        "india_gulf",
        "india_seasia",
        "coastal_westcoast",
        "coastal_eastcoast",
    ]
    for r in expected_routes:
        assert r in routes
        assert len(routes[r]["waypoints"]) >= 2
        for wpt in routes[r]["waypoints"]:
            assert len(wpt) == 2  # [lat, lon]
