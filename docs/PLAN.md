# KnotWise

**Quantum-Inspired Fuel Prediction and Green Fleet Optimization Under Regulatory Uncertainty**

Problem Statement SIH26138 · Egreen Quanta · Software · Smart Vehicles

**Document version 1.2** — this is now the frozen internal build contract. After this patch, the only permitted changes to this document are (a) real experiment outputs replacing [TARGET] labels as they are produced, and (b) any §3.2 sentence marked for softening by the Stage 2 pooling-locality design note, once written.

**Post-freeze update:** Stage 2's design note (see `Stage2_Pooling_Locality_Design_Note.md`) is now written and accepted, and applies the one permitted category-(b) edit: §3.2's bond-dimension claim has been narrowed to cover banking only, with pooling explicitly moved to a particle-level hybrid enforcement. §5.4's decision-variable list has been extended with the minimal fleet-composition addition the note recommends in its §4, to honestly cover the PS's "optimal mix of vessel types, capacities" clause. No other document content changed in this update.

**Changelog from v1.1 — nine patches (second-review pass, gated for build), all content outside these points is unchanged:**
1. Regime count fixed from three to four throughout: §3.4 ("outside all three" → "all four"), §5.4 Band C ("None of the three" → "None of the four"), Phase 4 deliverable ("excluded from all three regimes" → "all four regimes," plus an added FuelEU/EU ETS stacking test), §2 mapping table (EU ETS added to the listed regimes). Grepped the full document for "three" co-occurring with "regime" — zero remaining instances.
2. §1.3: table row count fixed from "three operations" to "four" (it always had four rows; only the prose undercounted). Marginalisation row corrected to match §3.1's honest phrasing — marginalisation gives the marginal distribution, not a free argmin; the never-badly-wrong plan is the minimax-regret plan, extracted separately.
3. §3.6(b): the approved NZF text and Tuvalu's proposal are both two-tier structures, not flat prices, and are now placed on the switching-point axis identically — as tier-annotated ranges, with the fleet's expected operating point computed from the case study's own deficit distribution. EU ETS (a genuine single posted price) and Liberia (no posted price, qualitative marker) are unchanged. The §3.6 CFO illustration sentence updated to match.
4. Implied-price converter added as an explicit task: Phase 0 deliverable (design and document the CII/FuelEU-to-effective-carbon-price conversion) and a stated Phase 3 dependency (the sweep cannot be built until scenario 5 has an honest axis position). §3.6 now states plainly that any claim about whether the current regulatory stack crosses a switching point is provisional until this converter is run, and flags the existing CFO-sentence example as illustrative pending that computation.
5. §3.1 MI-exclusivity claim softened: "no GA/SA/MILP solver can produce this" replaced with the amortization-and-coherence framing already used for switching points in §3.6(a) — one trained state yields conditional plans, marginals, minimax-regret, the switching-point sweep, and the MI structure as views of a single object; a classical pipeline needs a separate run for each and shares no object between them. Explicitly ties back to §8.3(b)'s own classical MI estimate as the reason the stronger claim wasn't defensible. Checked §3.2, §9.3, and §10 for adjacent overclaim language — the "per-vessel-constrained optimizer structurally cannot find this" (§3.2) and "nobody else...with a number attached" (§9.3 demo script) claims are about constraint structure and a specific computed artifact respectively, not classical inexpressibility, and were left as-is.
6. New §5.5, **Delivery Table (Expected Deliverables)** — D1 through D11, one row per deliverable, each tied to exactly one phase from Track S and to acceptance evidence. Cross-checked against every phase deliverable stated under Track S (Phases 0–7): each phase deliverable maps to exactly one row and vice versa. A stray cross-reference to a nonexistent "§5.3" was caught during this check and corrected to point at the actual phase list.
7. §11 confirmed complete end-to-end on this side (31 references, §11.1–§11.7 all present) — no mid-citation cutoff found. EU ETS citation (Directive 2003/87/EC as amended for maritime) confirmed present as reference 8 with the same provenance/re-verification discipline as every other regulatory constant.
8. New §12, **Team** — scaffold table plus a worked explanation of what evidence counts as demonstrable prior work in each of the four skill areas the build actually needs (tensor-network/QC, SMC/sampling, OR/combinatorial optimization, maritime domain exposure), with an explicit instruction not to fabricate entries.
9. Phase 7 now names the trimmed-deck-plus-trimmed-document task explicitly as a future Phase 7 action item, not attempted in this patch, per instruction.

**Unresolved from this pass — flagged, not fixed:** §11.2's citations were renumbered (8→9 etc.) when EU ETS was added in v1.1, but §11.3 onward (items 15–31) still carry their original v1.0 numbers, leaving a numbering seam noted in-place at §11.2/§11.3. Not touched here; wasn't in Stage 1's scope and a full renumber risked introducing new errors under time pressure.

---

## The one-line thesis

Every competing solution will hand the operator a fleet plan. KnotWise hands them a fleet plan **plus the exact list of decisions that are secretly bets on the October 2026 IMO vote, priced in rupees.**

---

## A note on numbers in this document

Every quantitative figure below is one of three kinds, and is always labelled:

- **[VERIFIED]** — checked against a primary source, with the source named in §11.
- **[TARGET]** — a threshold we are building toward. Not a result. Never to be presented as one.
- **[ILLUSTRATIVE]** — a made-up number used only to explain a mechanism.

No number moves from TARGET to a headline claim until it comes out of the experiment battery in §5. This rule exists because a deck full of unearned percentages is the fastest way to lose a technically literate panel.

---

# 1. The Problem in Simpler Words

## 1.1 What a fleet operator actually decides

A shipping company running twenty-odd vessels makes a small number of decisions that consume almost all of its money and all of its carbon:

- **Which ship goes on which route**, and how much cargo it carries.
- **How fast it sails.** Fuel burn scales roughly with the cube of speed, so a 10% speed cut is close to a 27% power cut on that leg — but it costs you a day, and days cost charter money and schedule reliability.
- **What it burns.** Heavy fuel oil with a scrubber, low-sulphur fuel oil, marine gas oil, LNG, a biofuel blend, methanol, and eventually ammonia or hydrogen. Each has a different price, a different lifecycle carbon intensity, and different bunkering availability.
- **Whether it plugs into shore power at berth** instead of running auxiliary engines.
- **Whether and when to retrofit** a vessel to a dual-fuel engine — a capital decision in the tens of crores with a payback measured over a decade.

## 1.2 Why this is hard

Two reasons that are usually stated, and one that usually isn't.

**Stated reason one: prediction is hard.** Fuel burn is not a lookup table. It depends on speed, draft, payload, hull fouling, sea state, wind direction relative to heading, water temperature, and engine condition. The physics gives you the leading term; the rest is empirical and vessel-specific.

**Stated reason two: the search space is enormous.** Twenty vessels, five years, six fuel choices, eight speed bands, a shore-power flag and a retrofit-year choice per vessel gives a configuration count far beyond exhaustive search. Mixed-integer programming handles small instances exactly and then falls over, because the speed–power relationship is cubic and the fuel choice is discrete.

**The reason nobody states: the objective function does not exist yet.**

This is the part that matters. Adoption of the IMO Net-Zero Framework — the instrument that would put a global price on shipping carbon — was adjourned in October 2025 and reconvenes around **October 2026** [VERIFIED]. It is not a yes/no vote. As of the current negotiating round there are multiple live proposals with materially different economics: the approved text prices remedial units at USD 100 (Tier 1) and USD 380 (Tier 2) per tonne CO₂-equivalent for 2028–2030; Liberia proposes replacing the fund mechanism largely with transferable surplus units; Tuvalu proposes Tier 1 at USD 300 with a steeper trajectory; Brazil proposes a softened start at 3% reduction in 2029 [VERIFIED].

So an operator signing a methanol retrofit contract this quarter is placing a nine-figure bet on the outcome of a vote. Nobody is pricing that bet. That is the gap.

## 1.3 What "quantum-inspired" means here, without hand-waving

We do not use quantum hardware, and §7 explains with arithmetic why nobody can for this problem yet.

We use the **mathematics of quantum many-body systems on classical hardware.** Specifically, a Matrix Product State — the same object physicists use to represent an entangled many-particle wavefunction — is used to represent a probability distribution over entire fleet configurations. Instead of holding one candidate plan and mutating it, we hold a *distribution over all plans* and reshape it.

This buys four operations that a population-based search cannot perform:

| Operation | What it means physically | What it gives the operator |
|---|---|---|
| Contraction | Compute an amplitude | Predicted fuel and cost for a specific plan |
| Conditioning (clamping a leg) | Fix one subsystem's state | "Show me the plan if Tuvalu's proposal passes" — the conditional *distribution* comes from the clamp itself; the optimal plan under it comes from one warm-started conditional re-anneal, seconds, not a cold re-solve |
| Marginalisation | Trace out a subsystem | The marginal distribution over configurations, averaged across vote outcomes — the never-badly-wrong single plan is not this marginal but the **minimax-regret plan** (§3.1), extracted separately by comparing per-scenario conditional plans |
| Mutual information between legs | Measure entanglement | **Which decisions depend on the vote, and by how much** |

That last row is the product.

---

# 2. How This Addresses the Problem Statement

SIH26138 lists five objectives. Mapping is direct and each row names the section that delivers it.

| PS Objective | KnotWise component | Where |
|---|---|---|
| Accurate quantum-inspired models for fuel consumption prediction across vessel types and conditions | Admiralty physics baseline + tensor-train residual regressor, trained distributionally (quantiles, not point estimates) | §3.2, §5 Phase 2 |
| Quantum metaheuristic optimization for optimal mix of vessel types, capacities, cruising speeds | Born-machine decision state + annealed Sequential Monte Carlo over the joint configuration space | §3.3, §5 Phase 3 |
| Minimise fuel consumption, operational cost, and lifecycle GHG | Three-objective Pareto optimisation on Well-to-Wake CO₂-equivalent, OPEX, and fuel mass, with a marginal abatement cost curve as output | §3.5 |
| Operational reliability, cargo demand satisfaction, emission-regulation compliance | Algebraic projection operators for hard constraints; compliance ledger carried in the tensor bond; CII, FuelEU, EU ETS, and NZF regimes modelled separately with correct scope | §3.4, §5 Phase 4 |
| Benchmark against conventional prediction and optimization on accuracy, convergence, solution quality, scalability | Six-experiment battery B1–B6 against GA, SA, CEM, PSO, Han–Kim QIEA, exact MILP, LightGBM, and physics-only baselines, 30 seeds, Wilcoxon with Holm correction | §5 Phase 5 |

The PS also asks for scenario analysis for alternative fuels. Our scenario module goes further than fuel-price scenarios: it treats the **regulatory outcome itself** as a scenario axis, which is the axis that actually dominates alternative-fuel economics.

---

# 3. Innovation and Uniqueness

Five things here. The first three are the ones that will not appear in any other submission.

## 3.1 The regulatory outcome is a leg of the tensor, not a for-loop around the solver

**The obvious approach.** You have K possible regulatory futures. Run the optimizer K times. Get K plans. Squint at the differences. This costs K× the compute and produces K answers, which is not an answer.

**Our approach.** Add an index `r` of dimension K as an explicit physical leg of the network, entangled with every decision leg. One trained state. Then:

- **Clamp `r = Tuvalu`** → this fixes the conditional *distribution* over configurations, by contraction, which is free. The optimal plan under that distribution is then extracted by **one warm-started conditional re-anneal** — a short SMC run initialised from the unconditioned state's particles, a few hundred temperature steps rather than a cold re-solve from scratch. Seconds, not free, and we say so.
- **Minimise maximum regret over `r`** → a single plan that is never badly wrong under any outcome. **No prior over vote outcomes is required.** This is the headline plan.
- **Compute mutual information `I(r ; x_i)`** between the regulatory leg and each decision variable → a per-decision number for how much that decision depends on the vote.

That third quantity is the **Exposure Map**, and it is the deliverable.

A decision with `I(r ; x_i) ≈ 0` should be executed today regardless of politics — it is robust. A decision with high mutual information is a *bet*, and the operator deserves to be told so before signing. Convert it to money by multiplying by the capital at risk and you get a sentence a CFO acts on: *"₹47 crore of your 2027 capex is contingent on the October vote, concentrated in three decisions."* [ILLUSTRATIVE]

**This is not a classically inexpressible quantity, and we do not claim it is.** §8.3(b) validates the Exposure Map by doing exactly what a classical pipeline would do — retraining per scenario and counting how often each decision flips — so a determined classical approach can estimate the same thing. The honest claim, the same one we make for switching points in §3.6(a), is **amortization and coherence**: one trained state yields the conditional plans (§3.1), the marginal (§1.3), the minimax-regret plan, the switching-point sweep (§3.6), and the mutual-information coupling structure, all as views of a single object. A classical pipeline needs a separate run — and often a separate piece of code — for each of these, and produces no shared object connecting them. Mutual information stays the tensor-native view of the coupling; we simply stop implying no classical method could ever approximate it.

**Why the entanglement framing is honest and not decorative:** mutual information between two subsystems of a quantum state is a standard, well-defined, computable quantity, obtained here from the singular value spectrum at the relevant bond. We are not borrowing a word. We are computing the thing the word denotes.

## 3.2 The decision variable is a multi-year compliance balance sheet, not a fleet plan

Every other team will apply carbon regulation as a per-vessel hard constraint: *make each ship compliant.* This is wrong, and wrong in a way maritime professionals recognise immediately.

FuelEU Maritime provides three flexibility mechanisms with real combinatorial teeth [VERIFIED]:

- **Pooling.** Compliance balances of multiple ships may be combined, within a fleet or between fleets by contract. Constraints: total pool balance must be positive; ships entering with a surplus must not end in deficit; ships entering with a deficit must not have it worsened; all pool members must agree on a single verifier.
- **Banking.** Surplus carries forward, and a banked surplus does not expire.
- **Borrowing.** A deficit ship may borrow an advance compliance surplus from the following period, capped at 2% of the limit multiplied by the ship's energy consumption, repaid at 1.1× — all-or-nothing, not permitted in two consecutive periods, and **not permitted simultaneously with pooling.**

The IMO NZF has a parallel structure: ships below the direct compliance target earn surplus units, transferable **once** through the GFI Registry and bankable for two years; ships in deficit acquire remedial units at the tier prices [VERIFIED].

**Consequence, and this is the slide that makes a panel lean forward: the optimal strategy is frequently to run one vessel deliberately dirty.** A single LNG dual-fuel ship over-complying can lift an entire pool above the line for less money than dragging five ships to marginal individual compliance. A per-vessel-constrained optimizer structurally cannot find this. It is not a smarter search of the same space — it is a different space.

**And this is why a Matrix Product State is the correct primitive for banking specifically, though not for pooling.** Order the tensor sites vessel-major: (vessel × year). Between a vessel's own consecutive-year sites, the bond is a genuine nearest-neighbor structure and carries the running banking/borrowing balance exactly, at small dimension. **For banking, the bond is the ledger.** Pooling is a different shape of constraint — a sum across an arbitrary subset of vessels within a year, which is a clique, not a chain — and no 1D bond ordering makes it local; see the Stage 2 design note for the full argument. It is enforced exactly at the SMC particle level instead, where a fully sampled configuration makes every pool member's balance directly computable, with only a coarse, lossy guidance signal on the inter-vessel bonds to steer search — never to gate feasibility. We can defend the banking half of this on a whiteboard without qualification; the pooling half is a hybrid design, and we say so rather than overclaiming a clean bond-native solution we don't have.

**A fourth instrument sits alongside these three, and it is priced today rather than pending a vote.** The EU Emissions Trading System was extended to shipping from 1 January 2024, applying to cargo and passenger ships ≥5,000 GT regardless of flag, on the same voyage-share logic as FuelEU — 100% of emissions on intra-EU/EEA voyages and at EU/EEA berth, 50% on voyages to or from a non-EU port [VERIFIED]. It phased in by *surrender* year: 40% of 2024 emissions (surrendered 2025), 70% of 2025 emissions (surrendered 2026), 100% of 2026 emissions onward (surrendered 2027) [VERIFIED]. EU Allowances are tradeable on the open carbon market and may be banked for future surrender — a simpler, single-tier version of the same banking primitive already in our ledger. **This is why we built the ledger as a general compliance-balance object rather than hard-coding FuelEU's specific rules:** EU ETS is one more row in the same bond, priced in EUAs rather than compliance-intensity units, and it costs us a schema entry rather than a new subsystem. FuelEU and EU ETS are separate instruments that stack — a Band A vessel calling at Rotterdam owes both, independently, on overlapping but not identical voyage-share definitions, and our compliance ledger keeps them as separate line items rather than netting them.

## 3.3 We optimise against a distribution trained on decision regret, not against a point forecast

Optimising against a point forecast is systematically wrong, and the failure has a name: the **optimizer's curse**. The optimizer actively hunts for the corners of the configuration space where your model is optimistically biased, because that is where the objective looks best. Higher prediction accuracy on average does not fix this — the error that matters is the error at the argmin, not the error on the mean.

The fix is decision-focused learning: train the predictor on **downstream decision regret** rather than on mean squared error (Elmachtoub & Grigas's SPO+ framework, Donti et al.'s task-based learning). Because our decision state is differentiable, this is available to us and is not available to a pipeline that hands a frozen regressor to a black-box metaheuristic.

**This lets us pre-empt the question that would otherwise sink us.** Every panel will ask: *why not just use XGBoost?* Our answer is a slide, not a defence:

> LightGBM beats our tensor-train residual on MAPE by roughly 0.4 points. Its fleet plans cost more. Here is the plot. [TARGET — must come from experiment B2]

Two honest supporting points we state openly rather than hide:

1. **On raw prediction accuracy, gradient boosting is competitive with a tensor-train regressor on tabular fuel data.** We do not claim otherwise, and B1 will show it.
2. **We use the tensor network anyway for a structural reason:** it is *contractible with the decision state*. It can be conditioned and marginalised as part of the same network. A boosted tree cannot be conditioned on a regulatory leg, cannot be marginalised, and cannot yield mutual information with a decision variable. The prediction model and the optimizer are the same object, which is what removes the seam where error compounds.

## 3.4 The compliance perimeter is itself a decision variable

This is the piece that makes the Indian case study interesting rather than decorative, and it comes from taking the regulatory scope text seriously.

FuelEU counts **100%** of energy on voyages between EU/EEA ports, **50%** on voyages between an EU/EEA port and a third-country port, and **100%** at berth in EU/EEA ports [VERIFIED]. CII and the NZF apply to ships ≥5,000 GT on **international voyages** [VERIFIED]. EU ETS applies on the same voyage-share basis as FuelEU, to the same ≥5,000 GT threshold [VERIFIED]. Indian domestic coastal voyages sit outside all four regimes.

So for a mixed Indian fleet, *the routing structure determines the regulatory exposure*. Whether a box moves India→Rotterdam direct or India→Colombo→Rotterdam changes how much energy falls inside the FuelEU perimeter. Whether a leg is served by a ≥5,000 GT deep-sea vessel or a smaller coastal feeder changes whether it is regulated at all.

An unconstrained optimizer will find this and exploit it. **We let it, and then we report it.**

Every rupee of saving in KnotWise output is split into two columns:

- **Abatement** — savings accompanied by a genuine reduction in Well-to-Wake CO₂-equivalent.
- **Perimeter** — savings arising from regulatory scope boundaries, with no emissions benefit or a negative one.

The default operator view shows both. A **Policy Mode** lets a regulator run the model in reverse to find where leakage is largest across a fleet archetype. This turns what would be an awkward finding into a governance contribution, and it means we can present the loophole from the stage without the panel thinking we built an evasion tool. Quantified carbon leakage from an Indian operator's balance sheet is a result worth having.

## 3.5 The output is a price, not a plan

We emit a **marginal abatement cost curve** for the fleet: rupees per tonne of CO₂-equivalent avoided, as a function of how much abatement you demand. This is the derivative of the Pareto front, so it costs almost nothing extra once the multi-objective solve exists, and it is the single artefact a CFO can act on directly. Compare it against the tier prices in the live NZF proposals and the retrofit decision answers itself.

## 3.6 Switching points — the price at which a decision flips

The Exposure Map (§3.1) answers *whether* a decision depends on the vote. It does not tell an operator *how far away* the danger is. Switching points answer that.

**The construction.** Sweep a single scalar — an assumed effective marginal carbon price — across a range. At each price, run one warm-started conditional re-anneal (the same mechanism as §3.1, clamped on price rather than on a named proposal) and record the optimal configuration. For each major decision (a retrofit, a fuel switch, a shore-power connection), the **switching point** is the price at which that decision's optimal value changes. Below it, do X. Above it, do Y. The number is a single rupee-per-tonne figure, and it requires no forecast, no scenario probability, and no belief about which proposal wins.

**Why this is the number a CFO wants.** Combine it with §3.1's exposure figure and you get a complete statement: *bet size* (capital at risk on the decision, from the Exposure Map) × *bet distance* (how far the switching point sits from the cheapest live proposal, in dollars per tonne). *"Your methanol retrofit flips at USD 185/tCO₂e. The approved NZF text's tier range (USD 100–380) straddles that line — whether it crosses depends on how deep the fleet sits into deficit. Tuvalu's range (USD 300 and up) sits above the line and crosses outright. The current CII/FuelEU/EU ETS stack alone does not."* [ILLUSTRATIVE numbers; the sweep in Phase 3 produces the real ones.]

**Two constraints on how we present this, stated here so they cannot drift in later drafts:**

**(a) This is not a tensor-exclusive capability, and we do not claim it is.** A classical optimizer run in a loop across a grid of carbon prices would eventually find the same switching points. The honest claim is narrower and still real: our network **amortizes** the sweep, because each price point is a warm-started conditional re-anneal off the same trained state rather than an independent cold solve, and the **same state** that produces the switching-point sweep also produces the mutual-information coupling structure in §3.1 — one object, two views, rather than two separate pipelines. We say this plainly in the deck rather than letting a judge catch us implying otherwise.

**(b) The sweep axis is an "effective marginal carbon price under stated assumptions," not a single posted number that every proposal maps onto.** Both the approved NZF text (Tier 1 USD 100 / Tier 2 USD 380) and Tuvalu's proposal (Tier 1 USD 300 at a steeper trajectory) are **two-tier structures, not flat prices** — a ship's effective marginal price depends on how far into deficit it sits, which tier it's paying into. Both are therefore placed on the axis identically: as a **tier-annotated range** bounded by Tier 1 and Tier 2, with the fleet's expected operating point within that range computed from the case study's own deficit distribution rather than assumed. EU ETS, by contrast, has a genuine single posted price (the EUA spot price) and converts onto the axis as a point, with the usual re-verification flag on that price. Liberia's transferable surplus-unit mechanism has no posted price at all — it is a market design, not a tariff — and is annotated as a **qualitative marker** with the assumption used to place it stated explicitly next to the tick mark, not silently baked into a number. Any figure that looks like a single point for a tiered proposal is a modelling choice, and the chart says so.

**Scenario 5 needs the same treatment, and it is the least obvious of the five.** "Adoption fails again" does not mean zero carbon price — it means the CII/FuelEU/EU ETS stack alone, none of which post a single unified per-tonne CO₂e figure the way the NZF tiers do. CII has no direct financial penalty at all; its consequence is a corrective-action-plan obligation and reputational/charter-party risk. FuelEU's penalty is a formula (a deficit-based charge per unit of missed GHG-intensity target, distinct from the NZF's remedial-unit price). Placing scenario 5 on the same axis as the other four therefore requires an explicit **implied-price converter**: a documented method for translating CII's non-compliance consequences and FuelEU's penalty formula into an effective marginal carbon price, under stated assumptions (e.g. capitalising a SEEMP Part III corrective-action cost, or converting FuelEU's penalty rate at the prevailing GHG-intensity gap). Until that converter exists and is run, **any claim in this document about whether the current regulatory stack crosses or does not cross a given switching point is provisional**, and is labelled as such everywhere it appears — including the CFO sentence just above, where "the current CII/FuelEU/EU ETS stack alone does not" cross is an illustrative placeholder, not a computed result.

---

# 4. Technologies Used

| Domain | Choice | Why this and not the alternative |
|---|---|---|
| Language and numerics | Python 3.11, NumPy, Polars | Polars over Pandas for AIS trajectory volumes — lazy evaluation and multi-threaded joins matter at tens of millions of position reports |
| Tensor core | PyTorch, custom Tensor-Train / MPS routines | Autograd is required for decision-regret training. Off-the-shelf libraries (TeNPy, quimb) are physics-oriented and do not expose the gradient path we need; we borrow their canonical-form and SVD-truncation logic rather than their solvers |
| Prediction baselines | LightGBM, scikit-learn, statsmodels | LightGBM is the honest strong baseline. Including it is a credibility move, not a formality |
| Optimizer | Custom annealed Sequential Monte Carlo sampler with systematic resampling | Del Moral–Doucet–Jasra SMC samplers give principled tempering with effective-sample-size control; a plain GA gives neither calibrated marginals nor a temperature schedule |
| Classical baselines | DEAP (GA), SciPy (SA, PSO), custom CEM, custom Han–Kim QIEA, PuLP + CBC (exact MILP for N≤8) | The exact MILP anchors optimality gap on small instances so our claims are grounded, not relative |
| Multi-objective | pymoo | Hypervolume and IGD implementations that reviewers recognise |
| Weather and ocean | ERA5 reanalysis (Copernicus/ECMWF) | Open, hourly, global, well-documented; the standard choice in the literature |
| AIS | Danish Maritime Authority open AIS archive, plus any accessible Indian coastal AIS | DMA AIS is genuinely open, large, and clean enough to learn realistic operating-profile priors from |
| Regulatory data | EMSA THETIS-MRV verified annual reports | The anchor to reality — see §6.2 |
| Backend | FastAPI + Redis queue, WebSockets for streaming anneal telemetry | Tempering runs are long; the UI needs to stream, not block |
| Storage | PostgreSQL + PostGIS | Route graphs, port coordinates, ECA polygons |
| Frontend | React + Vite, deck.gl for the fleet map, Plotly for the Pareto and MACC | **Deliberately not Streamlit.** Roughly half the finalists will present a Streamlit app and the panel will have decision fatigue by mid-afternoon. The vote slider (§9.3) has to feel like a product |
| Reproducibility | Docker, Make, GitHub Actions, fixed seeds | `make demo` must run offline with pre-seeded data. Live network dependency during a demo is an unforced error |

Deliberately **not** used: any quantum SDK submitting toy circuits. See §7.4.

---

# 5. Process of Implementation

## 5.1 Two tracks

The stated PS deadline is **20 September 2026**. Assuming that is the idea-submission gate and the grand finale follows later, the plan splits:

- **Track S (Days 1–21):** everything needed for submission — a working thin slice end-to-end plus the deck. Nothing here is optional.
- **Track F (post-submission):** depth, scale, and polish for the finale.

If the 20 September date is in fact a full-build deadline, Track S alone is a complete and defensible submission; Track F items degrade gracefully.

## Track S

### Phase 0 — Regulatory ground truth and scenario schema (Days 1–2)

Lock the numbers. CII Z-factors: 5% / 7% / 9% / 11% for 2023–2026, then 13.625% / 16.25% / 18.875% / 21.5% for 2027–2030 per MEPC.400(83) [VERIFIED]. FuelEU GHG-intensity baseline 91.16 gCO₂e/MJ with its reduction schedule. NZF tier prices USD 100 / USD 380 for 2028–2030. **EU ETS: phase-in 40% (2024 emissions) / 70% (2025 emissions) / 100% (2026 emissions onward), same 50%/100% voyage-share split as FuelEU, ≥5,000 GT cargo/passenger ships regardless of flag [VERIFIED — re-verify EUA spot price and phase-in percentages before submission, as both are the least stable numbers in the document].** Design and document the **implied-price converter** (§3.6): the method for expressing CII's corrective-action consequences and FuelEU's penalty formula as an effective marginal carbon price under stated assumptions, so that scenario 5 ("adoption fails") has an honest, non-zero position on the switching-point axis rather than being silently dropped or set to zero. Encode the five regulatory scenarios (§5.4) as JSON schemas. Record the source and retrieval date for every constant in a single `regulations.json` with a provenance field.

**Deliverable:** `regulations.json` with provenance, now carrying four regimes (CII, FuelEU, NZF, EU ETS); the implied-price converter as a documented, testable function, not a footnote; a one-page scope matrix showing precisely which vessel classes fall under which regime, with EU ETS as its own column.

### Phase 1 — Data pipeline (Days 2–5)

Ingest THETIS-MRV verified annual records. Ingest DMA AIS and derive operating-profile distributions (speed histograms, port-time fractions, laden/ballast ratios) by vessel class. Join ERA5 to AIS tracks for sea state and wind-relative-to-heading. Build the synthetic-telemetry generator described in §6.2.

**Deliverable:** reproducible ingestion scripts; a validated feature table; a data card documenting every source, its licence, and its known limitations.

### Phase 2 — Prediction (Days 4–8)

Calibrate the Admiralty baseline (P ∝ Δ^(2/3)·V³) per vessel class. Train the tensor-train residual, bond dimension 4–8, on quantile loss so the output is a distribution rather than a point. Train LightGBM and a plain MLP on identical folds. Run leave-one-vessel-out cross-validation.

**Deliverable:** calibrated predictor; **experiment B1 results**, including the honest LightGBM comparison.

### Phase 3 — Decision state and optimizer (Days 7–12)

Build the Born-machine decision state over (vessel × year) sites with the regulatory leg `r`. Implement chain-rule sampling, annealed SMC with effective-sample-size-triggered systematic resampling, and three-objective Pareto tracking. Implement minimax-regret extraction over `r`. Implement the warm-started conditional re-anneal used both to extract a plan under a clamped `r` (§3.1) and to run the carbon-price sweep (§3.6). **Depends on Phase 0's implied-price converter** — scenario 5 has no honest position on the price axis without it, and the sweep cannot be built until every scenario, including "adoption fails," converts to a point or range on the same axis. Implement switching-point extraction as post-processing over that sweep: for each major decision, locate the price at which the optimal value changes, at a resolution set by the sweep step size.

**Deliverable:** optimizer producing ranked Pareto fronts and a minimax-regret plan on the case-study instance; a carbon-price sweep with per-decision switching points; the warm-started conditional re-anneal benchmarked against a cold re-solve to confirm the "seconds, not free" claim in §3.1 with an actual number.

### Phase 4 — Compliance ledger (Days 10–14)

Projection operators for hard masks: fuel availability by port, vessel–fuel compatibility, shore-power capability, cargo demand balance. Compliance ledger on the bond: banking, borrowing with the 2% cap, 1.1× repayment, consecutive-period prohibition, and mutual exclusion with pooling; pooling with positive-total and no-worsening constraints. CII rating computation with correct scope gating. Abatement/Perimeter attribution.

**Deliverable:** compliance engine; scope-gating unit tests that assert a coastal feeder is correctly excluded from all four regimes, and that a Band A vessel is correctly assessed under FuelEU and EU ETS as two separate, stacking obligations rather than one.

### Phase 5 — Benchmarking battery (Days 12–17)

Six experiments, 30 seeds each, Wilcoxon signed-rank with Holm–Bonferroni correction, effect sizes reported alongside p-values.

| ID | Question | Comparators | Metrics |
|---|---|---|---|
| B1 | Is the prediction competitive? | Physics-only, LightGBM, MLP, TT-residual | MAPE, R², CRPS (distributional), LOVO CV |
| B2 | **Does decision-regret training beat MSE training?** | Same optimizer, two predictors | Realised cost regret vs. ground-truth simulator |
| B3 | Is the optimizer competitive? | GA, SA, CEM, PSO, Han–Kim QIEA, exact MILP (N≤8) | Hypervolume, IGD, feasibility rate, evaluations-to-target, optimality gap |
| B4 | Does it scale? | Same set | Runtime and quality at N = 5, 10, 20, 50, 100 vessels × 5 years |
| B5 | Is minimax-regret worth it? | Per-scenario optima, expected-value plan | Worst-case regret; prior-robustness sweep over the simplex |
| B6 | Which components earn their place? | Ablations: no regulatory leg, no pooling, no projection operators | Δ cost, Δ feasibility, Δ exposure-map fidelity |

**Deliverable:** benchmark report with convergence curves, scaling plots, and every significance test. B2 and B6 are the intellectually load-bearing ones.

### Phase 6 — Case study and interface (Days 15–19)

Run the segmented Indian fleet (§5.4). Build the React interface: fleet map, Pareto explorer, MACC, Exposure Map, and the vote slider.

**Deliverable:** working demo; case-study results with Abatement/Perimeter split.

### Phase 7 — Quantum resource estimate, packaging, deck (Days 18–21)

Produce the honest resource estimate (§7.4). Write the deck money-first. Record a two-minute screencast. Freeze `make demo`. **Also produce a trimmed submission document** — this full document is the internal build contract; the version submitted to SIH should be a shorter document plus deck derived from it, not this file verbatim. Noted here as a Phase 7 task so it is not lost; not attempted in this patch.

**Deliverable:** submission package.

## Track F (post-submission)

Multi-stage stochastic retrofit timing as a genuine real-option valuation; hull-fouling as an evolving state making the problem sequential rather than static; port berth-window coupling (just-in-time arrival, which is where a large share of real-world savings actually live); higher bond dimension with DMRG-style sweeps; a validated third-party fleet dataset if a partner is available.

**Also Track F, deferred deliberately rather than omitted by oversight:**

- **A second uncertainty leg for fuel-price spread**, alongside the regulatory leg `r`, with mutual information `I(r ; q)` computed between the two — a sentence like *"your methanol bet is three times more sensitive to fuel-price spread than to the vote"* is cheap once the first leg exists, but it is one more axis to validate under the same stability protocol as §8.3, and it does not belong in a three-week build.
- **"The India Brief"** — a named one-page output from Policy Mode: what each of the five live proposals costs the Indian fleet archetype, specifically. This lands directly on the PS's national-relevance dimension and is a natural finale-week item **if shortlisted** — it costs roughly a day once Policy Mode exists, and a day is worth spending only once there is a finale to spend it on.

## 5.4 The case study, specified

**"Bharat Line"** — a synthetic but realistic Indian operator. 24 vessels, planning horizon 2026–2030. Synthetic because no real operator will hand us their bunker data in three weeks; realistic because every parameter is drawn from public vessel particulars, THETIS-MRV distributions, and AIS-derived operating profiles.

Three compliance bands, which is the entire point:

| Band | Vessels | Regimes that apply |
|---|---|---|
| A — Europe liner | 10 deep-sea ≥5,000 GT, India–North Europe / Mediterranean | CII + NZF + FuelEU + **EU ETS** (FuelEU and EU ETS both fractional: 50% on the India–EU legs, 100% at EU berth — separate instruments, both owed) |
| B — Non-EU deep-sea | 6 deep-sea ≥5,000 GT, India–Gulf / Southeast Asia | CII + NZF only |
| C — Coastal feeder | 8 vessels on Indian coastal routes | **None of the four** |

Decision variables per vessel-year: route assignment, cruising speed (8 bands), fuel (HFO+scrubber, VLSFO, MGO, LNG, B30 blend, methanol), shore-power flag, retrofit year. Fleet-level: pool membership, bank/borrow election. **Fleet-composition, per year** (added per the Stage 2 design note §4, to honestly cover the PS's "optimal mix of vessel types, capacities" clause rather than only optimizing deployment of a fixed fleet): a small discrete menu — charter-in a feeder-class slot, charter-in a deep-sea-class slot, retire a vessel, trigger a newbuild-class placeholder, no change. This is a year-indexed, fleet-wide site (5 sites added to the existing 120), not a per-vessel multiplier, and does not materially change the compute profile in §6.1.

**Regulatory leg, K = 5**, grounded in actual live positions [VERIFIED as live proposals]:

1. NZF adopted as approved — Tier 1 USD 100, Tier 2 USD 380
2. Liberia-style — transferable surplus units largely replacing the fund mechanism
3. Tuvalu-style — Tier 1 USD 300, steeper GFI trajectory
4. Brazil-style — softened start, 3% in 2029, 4% in 2030
5. Adoption fails again — CII, FuelEU, and EU ETS only, no NZF

These are not invented scenarios. They are the proposals on the table.

## 5.5 Delivery Table (Expected Deliverables)

The SIH template asks for this as a named table. It is reconciled against the per-phase deliverables stated inline under **Track S, Phases 0–7** above — every row below is produced by exactly one phase named there, and every phase deliverable above appears in exactly one row below. If the two ever disagree, this table is wrong and gets fixed to match the phase deliverables, not the other way round, since the phase list is where the actual build order and acceptance criteria live.

| ID | Deliverable | Description | Produced by | Acceptance evidence |
|---|---|---|---|---|
| D1 | `regulations.json` + implied-price converter | All regulatory constants (CII, FuelEU, NZF, EU ETS) with source and retrieval-date provenance; documented function converting CII/FuelEU consequences to an effective marginal carbon price | Phase 0 | `verify_regulations.py` passes against primary sources; converter output reproducible and unit-tested |
| D2 | Scope matrix | One-page table of which vessel classes fall under which of the four regimes, and on what voyage-share basis | Phase 0 | Matches §3.4 and §5.4's Band A/B/C table exactly; reviewed against regulation text |
| D3 | Ingested and validated feature table | THETIS-MRV, DMA AIS, ERA5 joined and cleaned; synthetic-telemetry generator | Phase 1 | Data card complete; feature table passes schema validation; synthetic generator runs deterministically under a fixed seed |
| D4 | Calibrated fuel-consumption predictor | Admiralty baseline + tensor-train residual (quantile loss) + LightGBM and MLP comparators | Phase 2 | Experiment B1 results produced; leave-one-vessel-out CV complete; closure test (§6.2) run against THETIS-MRV |
| D5 | Optimizer core | Born-machine decision state, chain-rule sampler, annealed SMC, Pareto tracking, minimax-regret extraction, warm-started conditional re-anneal | Phase 3 | Runs on the case-study instance; warm-start vs. cold-solve timing measured and reported, not asserted |
| D6 | Carbon-price sweep and switching points | Parametric sweep over effective marginal carbon price; per-decision switching-point extraction | Phase 3 | Sweep resolution documented; switching points reproducible across seeds within a stated tolerance |
| D7 | Compliance ledger | Banking, borrowing, pooling (FuelEU), NZF surplus/remedial units, EU ETS allowance tracking, CII rating, Abatement/Perimeter attribution | Phase 4 | Scope-gating tests pass (D2); hard-constraint feasibility enforced per Stage 2's chosen design, never approximated by tensor truncation |
| D8 | Benchmark report | Experiments B1–B6 against GA, SA, CEM, PSO, Han–Kim QIEA, exact MILP, LightGBM, physics-only | Phase 5 | 30 seeds per experiment; Wilcoxon signed-rank with Holm–Bonferroni correction; every figure labelled [VERIFIED] once produced |
| D9 | Case study and interface | "Bharat Line" 24-vessel run; React frontend — fleet map, Pareto explorer, MACC, Exposure Map, vote/carbon-price slider | Phase 6 | `make demo` runs fully offline; protected-core elements (§8.1) function live; Abatement/Perimeter split visible on every output |
| D10 | Quantum resource estimate | QUBO mapping, logical-qubit and T-gate count, surface-code overhead, hardware-readiness year estimate | Phase 7 | Arithmetic shown, not asserted; sources for overhead figures cited in §11 |
| D11 | Submission package | Trimmed deck, trimmed document (see Phase 7), two-minute screencast, frozen `make demo` | Phase 7 | Deck and document consistent with each other; demo rehearsed end-to-end five times per §8.8 |

---

# 6. Feasibility Analysis

## 6.1 Computational

The MPS has (24 vessels × 5 years) = 120 sites plus one regulatory leg, local dimension around 200 for the combined per-site decision, bond dimension 4–16. Parameter count is on the order of 10⁵–10⁶ — small. Annealed SMC with a few thousand particles across a few hundred temperature steps is a matter of minutes on a single consumer GPU and is tractable on CPU. **[TARGET: sub-60s for N=24 at demo settings.]** There is no compute risk here; this fits on a laptop.

## 6.2 Data — the real constraint, stated honestly

High-frequency fuel telemetry from commercial fleets is commercially sensitive and not reliably available as open data. We do not pretend otherwise. Our position:

1. **Search first.** Any accessible open vessel-performance dataset gets used and named. If one lands, it replaces the synthetic track for condition modelling.
2. **Synthetic where necessary, clearly labelled.** A physics simulator (Admiralty baseline plus published added-resistance formulations) generates high-frequency telemetry, driven by *real* AIS operating profiles and *real* ERA5 weather, with realistic sensor noise and drift.
3. **Anchor to reality with the closure test.** This is the load-bearing validation. Integrate the condition-level model over a vessel's real annual AIS operating profile and compare the result against its **verified** THETIS-MRV annual fuel total. Verified means audited by an accredited third party. If the model closes annual energy to within a few percent against independently audited totals, the condition model is not fantasy. **[TARGET: ≤5% closure error.]**

This is a stronger validation story than most teams will have, precisely because we are upfront about the synthetic component and then show a hard external check on it.

## 6.3 Scope

Team of four to six over three weeks. The optimizer core is a few thousand lines. The largest risk is not difficulty but breadth — see §7.1.

## 6.4 Regulatory modelling

All constants are public and now pinned. The flexibility-mechanism rules are precisely specified in the regulation text and translate directly into constraint code. The scope-gating logic is the fiddly part and is why it gets dedicated unit tests in Phase 4.

---

# 7. Potential Challenges and Risks

## 7.1 Scope creep — the highest-probability failure

Five novel components in three weeks is how projects die. This is the risk that actually materialises.

## 7.2 The tensor-train predictor may not beat gradient boosting

It probably won't, on raw MAPE. We have already conceded this in §3.3 rather than being caught by it.

## 7.3 Mutual-information estimates from a truncated tensor may be unstable

Low bond dimension truncates correlations. If the truncation is aggressive, `I(r ; x_i)` could be biased and the Exposure Map — our headline — would be unreliable.

## 7.4 A panel from a quantum company may test whether "quantum-inspired" is real

They should. This is a fair test and we should want it.

## 7.5 The perimeter finding may read as an evasion tool

"We found the loophole" can land badly if framed carelessly.

## 7.6 Regulatory ground shifting

The NZF vote is roughly three weeks after the submission deadline. CII Phase 2 runs from spring 2026 to spring 2028 and is actively examining the CII metric itself, including exclusion of idle and port-waiting fuel [VERIFIED].

## 7.7 A panel unfamiliar with FuelEU may miss the entire point

Most of the value in §3.2 and §3.4 requires knowing what pooling is.

## 7.8 Demo failure

Live failure in front of judges.

## 7.9 The vote may resolve before the finale

If the extraordinary session in October 2026 actually adopts a text, "your plan is a bet on the vote" stops being true for the NZF axis specifically — though CII Phase 2 (open until spring 2028) and EU ETS's own post-2026 price path remain live uncertainty. A pitch built entirely around an unresolved vote is fragile to the vote resolving.

## 7.10 The demo choreography is asserted, not guaranteed

"The plan barely moves except three decisions" is the outcome we expect, not one we have observed on real numbers yet. If the sweep instead shows most of the plan moving, that is a different but still tellable story, and we should not be caught flat-footed by it.

---

# 8. Strategies for Overcoming Them

**8.1 Scope.** A hard cut-list, agreed on day one and written down: real-options retrofit timing, hull-fouling dynamics, port berth-window coupling, and DMRG sweeps are **all Track F**. Nothing moves from F to S. Phase 4 and Phase 5 are the two phases that must not be compressed, because the compliance ledger is the technical claim and the benchmark battery is an explicit PS requirement.

If time is lost, it comes out of interface polish in a specific order, not a general one — because the vote slider *is* the product, not decoration around it. **Protected core, never cut:** the vote/carbon-price slider and its exposure/switching-point readout (§3.1, §3.6, §9.3). This is the fifteen-second moment and it must work live. **Degradable, in this order:** first the fleet map (a static screenshot with a caption is an acceptable fallback), then the Pareto explorer (a pre-rendered plot is acceptable). If time is still short after that, the honest fallback is a smaller case study (N=12) with the full method rather than a large one with a partial method.

**8.2 Prediction parity.** Already converted from weakness to punchline in §3.3. The commitment is that we run B1 fairly, report LightGBM's win if it wins, and let B2 carry the argument. Contingency: if B2 shows *no* decision-quality advantage from regret training, we report that too, and the Exposure Map remains the differentiator on its own. Our submission does not depend on any single experiment coming out our way.

**8.3 MI stability.** Three mitigations. (a) Bond-dimension sweep: compute the Exposure Map at D = 4, 8, 16 and report the values only where the ranking is stable across all three. (b) Cross-check against a model-free estimate — retrain per-scenario, measure how much each decision actually flips, and confirm the tensor MI ranks decisions the same way. (c) Report the Exposure Map as an **ordinal ranking with a stability flag**, not as spurious three-decimal numbers. If a decision's exposure is not stable across bond dimensions, it is shown as "unstable," which is itself honest information.

**8.4 Passing the quantum test — attack, don't defend.** We drop the toy-circuit hardware receipt entirely. In its place: an explicit resource estimate. Map the fleet problem to a QUBO, count logical qubits, estimate T-gate depth for QAOA at a useful depth, apply a published surface-code overhead figure, and state the physical-qubit requirement and the year at which projected hardware roadmaps might reach it. The slide reads: *"No quantum computer can solve this problem before roughly the mid-2030s. Here is the arithmetic. That is why the quantum-inspired route is the correct engineering answer today."* Telling a quantum company that hardware can't do this yet, with numbers, reads as maturity. A five-qubit demo reads as decoration and invites exactly the scrutiny you don't want.

**8.5 Framing the perimeter finding.** Three moves. Every output carries the Abatement/Perimeter split by default, so we never present a headline saving that quietly includes leakage. Policy Mode is presented as a *regulator's* tool. And the framing sentence is fixed in advance: *"Our optimizer found the boundary. We are showing it to you because a regulator needs to know it exists, and because our own savings number is honest only if we separate the two."* This converts an ethical liability into a policy contribution.

**8.5a Grounding the pooling-vs-per-vessel headline.** Whether "run one vessel deliberately dirty" (§3.2) actually emerges as the dominant strategy is a function of the fuel-price and retrofit-cost assumptions fed into the case study — it is a finding, not a guarantee, and we do not assert it before we have it. Fuel prices and retrofit capex are seeded from published bunker-price indices and published newbuild/retrofit cost estimates, not invented, and the full pooling-economics run is executed **before** the finale, not live. If the pre-run shows only a modest gap between pooled and per-vessel compliance, the fallback headline — written now, not improvised then — is: *"Per-vessel compliance leaves ₹X crore on the table."* [TARGET — X from the pre-run] Less dramatic, still true, still something no per-vessel-constrained competitor can say. From the stage, pooling is framed throughout as *compliance portfolio optimization the regulation explicitly permits*, never as "dirty" — that word stays inside this document and out of the deck.

**8.6 Regulatory drift.** All constants live in one `regulations.json` with provenance and retrieval dates; nothing is hard-coded in solver logic. A `verify_regulations.py` script re-checks every value against source and is run in the final week. And structurally, the entire point of the architecture is that regulatory change is a parameter, not a rebuild — if the NZF text shifts, we clamp a different leg. **A submission whose thesis is regulatory uncertainty is the one submission that gains rather than loses when the regulation moves.** We should say that out loud.

**8.7 Legibility.** The vote slider (§9.3) makes the point in fifteen seconds with no regulatory knowledge required. The deck leads with rupees. Tensor notation does not appear before slide six, and never in the headline. The first sentence of the pitch is about money and a vote, not about Matrix Product States.

**8.8 Demo reliability.** `make demo` runs fully offline against pre-seeded, cached data with fixed seeds. No live API, no network dependency, no model training at demo time. A recorded screencast is the fallback. The demo path is rehearsed end-to-end at least five times on the actual presentation machine.

**8.9 Two scripts for the post-vote world.** Prepared now, not written under pressure at the finale.

- **Script A — the session adopts a text.** *"In October, the IMO adopted [text]. Our minimax-regret plan already accounted for this as one of five live outcomes — here is what changes and what doesn't. The uncertainty hasn't disappeared, it's moved: CII's Phase 2 review runs to spring 2028 and is re-examining the metric itself, and the EU ETS price path beyond 2026 is still open market. Same tool, same architecture, next axis."*
- **Script B — the session adjourns again.** *"The vote didn't resolve. Everything in this document still holds, and the Exposure Map gets more valuable, not less, because the uncertainty just got longer."*

The line underneath both: **regulatory change is a parameter in this architecture, not a rebuild.** If the NZF text shifts, we clamp a different leg on the same trained state. That sentence is true regardless of which script we deliver, and it is worth saying explicitly rather than leaving it implied.

**8.10 Two scripts for the demo itself.** The slider drag in §9.3 has two plausible outcomes on real numbers, and we script both rather than betting the pitch on one.

- **Outcome A — most of the plan is stable, a few decisions flip.** *"Notice how little moved. That's the point — most of your fleet plan is robust to politics. These three decisions are the ones riding on October, and here's what each one is worth."*
- **Outcome B — much of the plan moves with the slider.** *"Your entire 2027 plan is a bet on this vote. That's not a flaw in the tool — that's the finding. Nobody else in this room can tell you that with a number attached."*

Both are legitimate results and both are tellable live; the only failure mode is being visibly surprised by whichever one the real sweep produces.

---

# 9. Potential Impact on the Target Audience

## 9.1 The fleet operator

Today, retrofit and fuel-procurement decisions are made on a spreadsheet with a single assumed carbon price. KnotWise changes the conversation from *"what should we do"* to *"what should we do now, what should we defer until October, and what does deferring cost."* The Exposure Map converts an unquantified political risk into a line item with a rupee value. For an operator with even a modest retrofit programme, correctly deferring one wrong bet pays for the entire tool.

## 9.2 The regulator and the policy analyst

Policy Mode quantifies leakage: how much emissions activity migrates from the regulated perimeter to the unregulated one, per fleet archetype, under each proposal. For India specifically — a country with a large coastal fleet, a growing deep-sea fleet, and an active negotiating position at the IMO — being able to model *"what does each proposal on the table cost the Indian fleet, and where does it push activity"* is directly useful to DG Shipping and to the Ministry of Ports, Shipping and Waterways ahead of the vote. This is the part with genuine national relevance, and it is not a stretch.

## 9.3 The evaluator, in fifteen seconds

The demo moment is designed and rehearsed:

> One slider, labelled **"October 2026 IMO vote."** Five notches, matching the K=5 regulatory scenarios in §5.4: Approved text, Liberia, Tuvalu, Brazil, **Adoption fails again**. Drag it. The fleet plan barely moves — except three decisions, which flip and light up red. A number updates: **₹47 crore of planned capex is exposed to this vote.** [ILLUSTRATIVE]
>
> A second, continuous control sits beside it: the **effective carbon price** axis from §3.6. Rather than jumping between five named points, drag along the price line and watch each decision's **switching point** pass underneath the cursor — the exact price at which that decision flips, independent of which proposal gets there. The five vote notches are simply marked as ticks on this same axis, each annotated with its assumption. This is the artefact that outlives the vote: whichever way October goes, the switching points are still the answer.

Legible to a non-technical judge. Technically deep for a quantum-literate one. Fifteen seconds. No other submission will have it, because it requires knowing the vote is happening, that the proposals differ, and that a decision can be reduced to the price at which it flips.

---

# 10. Benefits of the Solution

**Economic.** Direct fuel and OPEX reduction from joint speed, routing, and fuel optimisation, with the compliance-portfolio effect — pooling and banking correctly exploited — adding savings that per-vessel optimisation cannot reach. **[TARGET: 10–15% OPEX reduction against a fixed-speed, single-fuel baseline; to be established by B3, not asserted.]** Separately and probably larger: avoided capital misallocation. A single deferred-or-accelerated retrofit decision on a mid-size vessel is a tens-of-crores swing, and that is what the Exposure Map addresses.

**Environmental.** Well-to-Wake lifecycle CO₂-equivalent is a first-class objective, not a reporting afterthought — which matters, because CII is a tank-to-wake measure while FuelEU and the NZF are well-to-wake [VERIFIED], and optimising the wrong one produces fuel choices that look good on paper and are worse in atmosphere. Shore-power utilisation is optimised jointly rather than treated as a berth-side afterthought, which also cuts NOx, SOx, and particulates in port cities. **[TARGET: 12–20% WtW CO₂e reduction — to be established, not asserted.]** And the leakage quantification is an environmental contribution in its own right: unmeasured leakage is unaddressed leakage.

**Social.** Port-adjacent communities in Indian coastal cities carry the health burden of at-berth auxiliary-engine emissions; shore-power optimisation is directly a public-health intervention. More broadly, the tool lowers the analytical barrier for smaller Indian operators who cannot afford the consultancies that currently do this work for the major lines.

**Policy and strategic.** A domestically built capability to model IMO proposals against the Indian fleet, ahead of a vote India participates in, is a small but real piece of negotiating infrastructure. It aligns with the direction of Maritime Amrit Kaal Vision 2047, the Harit Sagar green-port guidelines, and India's coastal shipping expansion agenda.

**Methodological.** Decision-focused learning applied to maritime operations, and mutual information with a policy leg as an exposure metric, are contributions that generalise beyond shipping — to aviation under CORSIA, to power-sector dispatch under carbon-price uncertainty, to any capital-allocation problem where the objective function is awaiting a vote.

---

# 11. References and Research Work

## 11.1 Primary regulatory sources — verified

1. **Regulation (EU) 2023/1805 (FuelEU Maritime).** Article 2(1) scope; Articles 20–21 banking, borrowing, pooling. https://eur-lex.europa.eu/eli/reg/2023/1805/oj/eng
2. **MARPOL Annex VI, Regulation 28** — CII requirement; Regulation 27 — IMO Data Collection System. Scope: ships ≥5,000 GT on international voyages.
3. **Resolution MEPC.338(76)** — 2021 Guidelines on operational carbon intensity reduction factors (G3). Z-factors 2023–2026. https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MEPCDocuments/MEPC.338(76).pdf
4. **Resolution MEPC.400(83)** — amendments to G3 setting Z-factors for 2027–2030 (13.625%, 16.25%, 18.875%, 21.5%). MEPC 83/17/Add.1 Annex 4.
5. **IMO Net-Zero Framework — official FAQ.** Surplus units, remedial units, two-tier pricing. https://www.imo.org/en/mediacentre/hottopics/pages/faqs-the-imo-net-zero-framework.aspx
6. **Resolution MEPC.376(80)** — 2023 Guidelines on lifecycle GHG intensity of marine fuels (LCA Guidelines). *Confirm resolution number against the IMO index before submission.*
7. **EMSA THETIS-MRV** — verified annual emissions reports database.
8. **Directive 2003/87/EC as amended for maritime (EU ETS)** — scope (≥5,000 GT, regardless of flag, from 2024), phase-in schedule (40%/70%/100% by surrender year 2025/2026/2027 for emissions years 2024/2025/2026+), voyage-share rules matching FuelEU's 50/100 split. *EUA spot price and any post-2026 phase-in adjustments are the most volatile numbers in this document — re-verify immediately before submission.*

## 11.2 Regulatory analysis and current status — verified

*(Numbering continues at 9 following the addition of EU ETS as item 8 above; items 9–14 below are unchanged from v1.0 and correspond to the same sources.)*

9. Global Maritime Forum, *A guide to the IMO's Net-Zero Framework* — adjournment and October 2026 reconvening. https://globalmaritimeforum.org/news/a-guide-to-the-imos-net-zero-framework/
10. Vinson & Elkins, *IMO Postpones Adoption of Net Zero Framework* — procedural detail on the October 2025 adjournment.
11. Climate Action Tracker, *Rescuing shipping's Net Zero Framework*, April 2026 — flexibility mechanisms and their effect on delivered abatement.
12. Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping, *IMO Net-Zero Framework* — tier-price analysis and surplus-unit mechanics.
13. DNV, *FuelEU Maritime — flexibility mechanisms and pool verification* — operational detail on the 2% borrowing cap and 1.1× repayment.
14. Lloyd's Register, *Flexibility compliance mechanisms* — pooling validity conditions.
15. Coverage of the current negotiating round and the Liberia, Tuvalu, Brazil, and Australia/Canada/South Africa/UK proposals. *Re-check immediately before submission; this is the fastest-moving item in the document.*
16. DNV / Sofar Ocean / European Commission Climate Action, *EU ETS maritime scope and phase-in* — cross-checked across three independent summaries against the phase-in schedule cited in item 8.

## 11.3 Method — tensor networks and quantum-inspired optimization

15. Oseledets, I. (2011). Tensor-Train Decomposition. *SIAM Journal on Scientific Computing* 33(5).
16. Stoudenmire, E.M. & Schwab, D. (2016). Supervised Learning with Tensor Networks. *NeurIPS*.
17. Han, Z-Y., Wang, J., Fan, H., Wang, L. & Zhang, P. (2018). Unsupervised Generative Modeling Using Matrix Product States. *Physical Review X* 8, 031012. — the Born machine.
18. Han, K-H. & Kim, J-H. (2002). Quantum-Inspired Evolutionary Algorithm for a Class of Combinatorial Optimization. *IEEE Transactions on Evolutionary Computation* 6(6). — the baseline we must beat.
19. Del Moral, P., Doucet, A. & Jasra, A. (2006). Sequential Monte Carlo Samplers. *JRSS Series B* 68(3).
20. Schollwöck, U. (2011). The density-matrix renormalization group in the age of matrix product states. *Annals of Physics* 326(1). — canonical forms, bond entropy, truncation.

## 11.4 Method — decision-focused learning

21. Elmachtoub, A. & Grigas, P. (2022). Smart "Predict, then Optimize". *Management Science* 68(1). — the SPO+ loss and the formal statement of why MSE is the wrong training objective.
22. Donti, P., Amos, B. & Kolter, J.Z. (2017). Task-based End-to-end Model Learning in Stochastic Optimization. *NeurIPS*.
23. Smith, J.E. & Winkler, R.L. (2006). The Optimizer's Curse. *Management Science* 52(3).
24. Savage, L.J. (1951). The Theory of Statistical Decision. — minimax regret.

## 11.5 Maritime operations research

25. Psaraftis, H. & Kontovas, C. (2013). Speed models for energy-efficient maritime transportation: a taxonomy and survey. *Transportation Research Part C* 26.
26. Psaraftis, H. & Kontovas, C. (2014). Ship speed optimization: concepts, models and combined speed-routing scenarios. *Transportation Research Part C* 44.
27. Meng, Q., Wang, S., Andersson, H. & Thun, K. (2014). Containership Routing and Scheduling in Liner Shipping: Overview and Future Research Directions. *Transportation Science* 48(2). — the MILP formulations we benchmark against.
28. Literature on hull fouling and added resistance in waves for the physics baseline (ITTC recommended procedures; Kwon's method for added resistance). *Specific formulations to be fixed in Phase 2.*

## 11.6 Data sources

29. Hersbach, H. et al. (2020). The ERA5 global reanalysis. *Quarterly Journal of the Royal Meteorological Society* 146(730).
30. Danish Maritime Authority — open AIS archive.
31. GEBCO bathymetry; IMO ECA boundary definitions.

## 11.7 Verification note

The IMO regulatory position is live and moving. The NZF adoption session reconvenes around October 2026 and the CII Phase 2 review runs to spring 2028. **Every constant in `regulations.json` must be re-verified against primary source in the final week before submission**, and the retrieval date recorded. A submission whose thesis is regulatory uncertainty cannot afford to be stale about the regulation.

---

# 12. Team

*Scaffold only — I cannot write this content. Below is the structure and, for each member, exactly what evidence needs to be gathered and attached before this section is real.*

| Member | Role on this project | Prior relevant work | Evidence to attach |
|---|---|---|---|
| [Name] | [e.g. tensor-network / optimizer lead] | [placeholder] | [placeholder] |
| [Name] | [e.g. prediction / data pipeline lead] | [placeholder] | [placeholder] |
| [Name] | [e.g. compliance ledger / regulatory research lead] | [placeholder] | [placeholder] |
| [Name] | [e.g. frontend / demo lead] | [placeholder] | [placeholder] |
| [Name] | [e.g. benchmarking / evaluation lead] | [placeholder] | [placeholder] |
| [Name] | [e.g. team lead / integration] | [placeholder] | [placeholder] |

**What "evidence" means here, concretely, per the four skill areas this build actually needs:**

- **Prior tensor-network or quantum-inspired-computing work.** A repo, coursework project, or paper touching MPS/tensor-train methods, DMRG, tensor decomposition, or (failing that) any hands-on quantum-computing coursework. If nobody on the team has this, say so plainly rather than implying otherwise — it's a real gap and the panel may test it directly (§7.4).
- **SMC, sampling, or Monte Carlo methods.** A repo or coursework project using particle filters, MCMC, simulated annealing, or any sampling-based optimizer — this is the more learnable half of the optimizer core and is worth having even if the tensor experience is thin.
- **Operations research / combinatorial optimization.** Any MILP, GA, or metaheuristic implementation — course project, Kaggle-style competition, or internship work. This directly supports the classical-baseline benchmarking in §5 Phase 5 and Stage 2's fallback design.
- **Maritime, logistics, or regulatory-compliance domain exposure.** Not required, but if anyone has it — shipping internship, logistics coursework, or even close reading of the regulation texts already done for this document — it should be named, since panels weight domain grounding highly for an applied PS like this one.

Fill in names, roles, and evidence, then this section is complete. Do not fabricate prior work that doesn't exist — an honest "this is our stretch area, here's our mitigation" (pointing back to Stage 3's BUILD_ORDER de-risking week) is more credible to a panel than an inflated credentials list, and inconsistent with the document's own labelling discipline if overstated.
