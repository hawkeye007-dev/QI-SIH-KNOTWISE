# KnotWise

Quantum-Inspired Fuel Prediction and Green Fleet Optimization Under Regulatory Uncertainty
(SIH26138 · Egreen Quanta).

The build contract lives in [`docs/PLAN.md`](docs/PLAN.md); the pooling-locality
architecture decision it depends on is [`docs/DESIGN_NOTE_POOLING.md`](docs/DESIGN_NOTE_POOLING.md).
Read those first — this README only covers running the code as it exists so far.

## Status

Phase 0 (regulatory ground truth) only. See `docs/PLAN.md` §5 Track S for the full
phase plan and `docs/scope_matrix.md` for the regime-applicability table.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Run tests

```bash
pytest
```
