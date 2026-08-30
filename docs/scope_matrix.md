# Scope Matrix — Regulatory Regime Applicability by Vessel Class

**Deliverable D2** (PLAN.md §5.5). Transcribed to match PLAN.md §3.4 (regime scope
text) and §5.4 (Bharat Line case-study bands) exactly — if this table and either of
those sections ever disagree, this file is wrong and gets fixed to match them, not
the other way round.

## By regulatory regime (PLAN.md §3.4)

| Regime | Applies to | Voyage-share basis |
|---|---|---|
| CII (MARPOL Annex VI, Reg. 28) | Ships ≥5,000 GT, international voyages | Not fractional — applies to the full voyage |
| NZF | Ships ≥5,000 GT, international voyages | Not fractional — applies to the full voyage |
| FuelEU Maritime | Ships ≥5,000 GT (PLAN.md §3.4 states EU ETS shares "the same ≥5,000 GT threshold" as FuelEU, implying this figure for FuelEU itself; confirm directly against Reg. (EU) 2023/1805 Article 2(1) before this line gates code — it is inferred, not separately restated with its own number in PLAN.md) | 100% intra-EU/EEA voyages and at EU/EEA berth; 50% EU/EEA ↔ third-country voyages |
| EU ETS (Directive 2003/87/EC as amended) | Cargo/passenger ships ≥5,000 GT, regardless of flag, since 1 Jan 2024 | Same 50%/100% split as FuelEU |

Indian domestic coastal voyages sit outside all four regimes (PLAN.md §3.4).

## By Bharat Line case-study band (PLAN.md §5.4)

| Band | Vessels | Regimes that apply | Notes |
|---|---|---|---|
| A — Europe liner | 10 deep-sea ≥5,000 GT, India–North Europe / Mediterranean | CII + NZF + FuelEU + EU ETS | FuelEU and EU ETS both fractional: 50% on the India–EU legs, 100% at EU berth — separate instruments, both owed, not netted against each other |
| B — Non-EU deep-sea | 6 deep-sea ≥5,000 GT, India–Gulf / Southeast Asia | CII + NZF only | No EU/EEA port calls → FuelEU and EU ETS voyage-share basis never triggers |
| C — Coastal feeder | 8 vessels, Indian coastal routes | None of the four | Below GT threshold and/or domestic-only voyages |

## Acceptance evidence

Per D2 (PLAN.md §5.5): this table must match §3.4 and §5.4 exactly, and be reviewed
against the regulation text. The FuelEU GT-threshold line above is flagged rather
than asserted — it is the one cell not explicitly restated with a GT figure in
PLAN.md's §3.4 prose, and should be confirmed against Regulation (EU) 2023/1805
Article 2(1) directly (not assumed from EU ETS's threshold) before Phase 4's
scope-gating unit tests are written.
