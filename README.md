# KnotWise

KnotWise explores lower-emission fleet plans by optimizing vessel fuel, speed, route, and shore-power choices across regulatory scenarios. It combines a Python optimization engine with a Next.js decision dashboard.


## Quick start

Requirements: Python 3.11+ and Node.js.

```bash
# Terminal 1 — Python engine and API
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m knotwise.api.server

# Terminal 2 — dashboard
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The dashboard works from bundled demo data; the API is only needed for live recommendations on **Plans**.

## What’s inside

- **Dashboard:** overview, plan comparison, fleet matrix, fuel analysis, sensitivity, regulatory exposure, solver, prediction, and guide pages.
- **Optimizer:** genetic algorithm and quantum-inspired search over fleet decisions, with regulatory costs and operational constraints.
- **Live API:** `POST http://127.0.0.1:8000/api/recommendations` accepts `carbon_price_usd_per_tco2e` (0–1000) and `cargo_demand_multiplier` (0.1–10).
- **Demo data:** precomputed fleet plans and benchmarks in `outputs/` and `frontend/public/`.

## Checks

```bash
# From the repository root
pytest

# Frontend production build
cd frontend && npm run build
```

## Project layout

| Path | Purpose |
|---|---|
| `src/knotwise/` | Fleet and regulatory data, compliance, optimization, and API |
| `frontend/` | Next.js dashboard |
| `outputs/` | Generated demo results and benchmark reports |
| `tests/` | Python behavior and data-contract tests |
