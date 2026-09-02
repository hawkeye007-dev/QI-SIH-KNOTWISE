# KnotWise — The Complete Plain-English Explainer

**Who this is for:** someone who needs to understand and present this project but has no software background. Every technical term is explained the first time it shows up. Nothing here is aspirational or rounded up — this describes exactly what exists and runs today, including the rough edges. If a number here doesn't match what you see on screen, the screen is right (we rebuild the data periodically) — but the *mechanism* described here doesn't change.

**Don't skip section 9 ("Questions a judge will ask, and the honest answer").** That's the part that actually gets you through a pitch.

---

## 1. The problem, in one paragraph

Shipping companies burn fuel, and fuel makes CO₂. International regulators (the IMO — International Maritime Organization, the UN body that regulates shipping) are trying to agree on a global carbon tax for ships. They *tried* to pass one in October 2025 and failed to reach agreement. The vote has been rescheduled to **4 December 2026**. Nobody knows what the final price will be, or if it'll pass at all — there are five realistic outcomes on the table, from "the strict version passes" to "nothing passes and only the existing weaker rules apply."

Here's the part that matters commercially: a shipping company deciding *today* whether to spend tens of millions of dollars converting a ship's engine to burn a cleaner fuel is making a bet on how that vote goes. If the strict version passes, that investment pays off. If it fails, they've spent money they didn't need to. **Nobody is telling them how big that bet is, or which of their decisions actually depend on it.** That's the gap KnotWise fills.

---

## 2. What KnotWise actually does (the one-sentence pitch)

**KnotWise takes a shipping company's fleet, works out the cheapest way to run it under any possible carbon-tax price from $0 to $1,000 per tonne of CO₂, and then tells the operator exactly which of their decisions change depending on how the vote goes — priced in rupees.**

Two outputs matter:
1. **A fleet plan** — for any assumed carbon price, which ship should use which fuel, sail at what speed, on which route, in which year.
2. **An exposure report** — of all those decisions, which ones are "safe" (same answer no matter what the vote does) and which ones are "bets" (the answer flips depending on the outcome) — and how much money is riding on each bet.

---

## 3. The two halves of the project, and why they're separate

Think of this project as having a **brain** and a **face**.

- **The brain** (folder: `src/knotwise/`) is a Python program. It does all the actual math: it knows the regulations, knows the ships, and runs a search algorithm to find good fleet plans. It has no visuals — it just crunches numbers and writes them to a file.
- **The face** (folder: `frontend/`) is a website built with Next.js (a popular web-app framework built on React — you don't need to know more than "it's what makes the interactive website"). It has no math in it at all. It just reads a file the brain already produced and draws charts, maps, and tables from it.

**Why keep them separate?** Two reasons, and both matter for the demo:

1. **Speed and reliability.** The brain's calculations are slow — a full run takes roughly 20–30 minutes of computer time (explained in section 6). You cannot make a judge sit and wait 20 minutes while dragging a slider. So the brain runs *once, ahead of time*, and saves everything it found into one big file — `demo_data.json`. The website only ever reads that file. Dragging the slider during a live demo is instant because it's just looking up an already-computed answer, not solving anything live.
2. **No internet dependency.** Because the website only reads a local file, the demo works with the venue wifi turned off. This is deliberate — a live network dependency during a demo is a classic way to fail on stage.

There's even an automated check (`tests/test_demo_frontend.py`) that fails the build if anyone accidentally makes the website import Python code directly — the separation is enforced, not just a suggestion.

---

## 4. The file that connects them: `demo_data.json`

Everything the website shows comes from one file: `frontend/public/demo_data.json`. It's produced by running one script:

```
python scripts/build_demo_data.py
```

This script is pure orchestration — it doesn't do any math itself, it just calls the brain's functions in order and glues their results together into one JSON file (JSON = a text format for structured data; think of it as a big nested list of labelled numbers and facts). The file contains, roughly:

- `fleet` — the ships, their routes, their fuel options.
- `sweep` — the fleet-plan answer at 41 different carbon-tax prices ($0, $25, $50, ... up to $1,000).
- `exposure` — which decisions are "safe" vs. "bets," and how much money is on the bets.
- `routes_geo` — made-up but realistic-looking shipping-lane coordinates, for the map.
- `metadata` — a timestamp and an honest label: `"SYNTHETIC FLEET, PROTOTYPE-GRADE FIGURES"`. We do not hide that the fleet is invented (see section 8).

If you ever need to "restart everything from scratch," this one script is the entire pipeline. It currently takes about 20–30 minutes to run because it's doing a lot of search (again, section 6).

---

## 5. The fleet — what's actually being optimized

The prototype fleet has **10 ships**, split into three "bands" based on what regulations apply to them:

| Band | Ships | What they do | Which regulations apply |
|---|---|---|---|
| A | A1–A4 (4 ships) | Deep-sea, Europe-bound routes | All four: CII, FuelEU, NZF, EU ETS |
| B | B1–B3 (3 ships) | Deep-sea, non-EU routes (Gulf, SE Asia) | CII and NZF only |
| C | C1–C3 (3 ships) | Indian coastal feeder routes | **None** — they're outside all four regimes |

Band C existing at all is a deliberate finding, not an oversight: coastal shipping inside India is *invisible* to every one of these international carbon rules. That's a real, defensible insight about how regulation perimeters work, and the model reports it rather than hiding it.

Each ship also has an **engine type** that limits which fuels it can burn:
- `conventional_hfo_scrubber` — can burn HFO+scrubber, VLSFO, MGO, or a biofuel blend (B30). Cannot burn LNG or methanol — the engine physically isn't built for it.
- `dual_fuel_lng` — can burn VLSFO, MGO, B30, or LNG.
- `dual_fuel_methanol` — can burn VLSFO, MGO, B30, or methanol.

(Fuel names, if you need them for a slide: **HFO** = Heavy Fuel Oil, the cheapest, dirtiest option, usually paired with a "scrubber" that removes sulfur but does nothing for CO₂. **VLSFO/MGO** = cleaner refined fuel oils. **B30** = a 30% biofuel blend. **LNG** = liquefied natural gas. **Methanol** = the cleanest option modelled, burnable only in a methanol-capable engine.)

For every ship, for every year from 2026 to 2030, the model has to decide:
- Which **route** to sail
- What **speed** to sail at (8 speed bands, from crawl to full design speed — slower burns much less fuel but takes longer, which costs charter money)
- Which **fuel** to burn (from that ship's own allowed list)
- Whether to plug into **shore power** at berth instead of running engines (only possible for Bands A/B, costs $150,000/ship/year when used)
- Whether to **pool** its compliance balance with other ships that year (explained in section 6)
- Whether to **borrow** against next year's compliance allowance (also section 6)

That's roughly 50 "slots" to fill in (10 ships × 5 years), each with up to ~20 valid choices. The total number of possible fleet plans is astronomically large — far too many to check one by one. That's why we need a search algorithm (section 6).

**Important scoping note:** the original plan document (`KnotWise_Project_Document`) describes a 24-vessel case study. What's actually built is the smaller 10-vessel version above. This was a deliberate scale-down to keep build times reasonable, not an oversight — but if your junior colleague reads the plan document and then looks at the code, this is the discrepancy they'll notice, so it's worth saying out loud rather than letting them find it mid-question.

---

## 6. The four regulations, in plain English

This is the part that makes the model realistic instead of a toy. Four separate carbon rules can apply to the same ship at the same time, and they don't work the same way.

### CII (Carbon Intensity Indicator)
A rating system (like an efficiency label) for how much CO₂ a ship emits per unit of cargo carried. **It has no direct fine.** If you get a bad rating, you have to write a corrective-action plan and it can hurt your reputation/charter rates — but there's no dollar penalty in the model, and none in reality either.

### FuelEU Maritime
An EU rule. Every ship has a target for how "clean" its fuel mix must be on average, and the target **tightens every year**. If you're above target, you pay a penalty formula (in euros). If you're below target (cleaner than required), you're in **surplus**, and you can do useful things with that surplus:
- **Bank it** — carry it forward to next year, no expiry.
- **Borrow** — if you're short this year, you can borrow up to 2% of your allowance from *next* year's balance, but you have to pay it back at 1.1× (a 10% "interest" charge), and you can't borrow two years running.
- **Pool** — combine your compliance balance with other ships (in your fleet or under contract with someone else's) so the *pool's total* just needs to be positive. This means **one very clean ship can let several dirtier ships stay technically non-compliant on paper** — the model actually finds this trick, and it's flagged as a real, permitted strategy, not a bug.

### NZF (Net-Zero Framework) — the one being voted on
The rule at the center of the whole project. It works in **two tiers**:
- **Tier 1**: the gap between a lenient "base target" and a stricter "compliance target." Priced at $100/tonne CO₂ (this is the *approved, real* number).
- **Tier 2**: anything worse than the base target. Priced at $380/tonne CO₂ (also the real, approved number).
- **Surplus**: if a ship beats the compliance target, it earns a tradeable "surplus unit" — like a credit you can sell.

Both tier prices only kick in from **2028 onward** — 2026 and 2027 have no NZF cost at all, regardless of what fuel you burn. That's a real, important detail: it means a ship staying on cheap dirty fuel in 2026–2027 isn't being lazy, it's correctly noticing there's nothing to gain yet.

### EU ETS (EU Emissions Trading System)
The one regulation that's **already real and already priced today** — no vote needed. Ships pay for a percentage of what they actually emit, phased in: 40% of 2024 emissions, 70% of 2025, 100% from 2026 onward. It stacks on top of whatever NZF outcome happens — they're separate bills, not netted against each other.

### Who owes what, by route
All four regulations only count emissions on certain kinds of voyages:
- 100% counted on EU-to-EU voyages and at EU berths.
- 50% counted on voyages between an EU port and a non-EU port.
- 0% for Band C's pure-domestic Indian coastal routes.

This is why the routing decision matters just as much as the fuel decision — moving cargo via a different port can change how much of a voyage even falls under these rules.

---

## 7. The search algorithm — how the model actually finds a good plan

This is the "brain" doing its main job. Here's the plain-English version, no math.

### The genetic algorithm (GA)
Imagine you have a population of, say, 200 random fleet plans. Each one is complete nonsense — random fuels, random speeds, random routes. You measure how expensive each one is. Then you do what evolution does:
1. **Selection** — the cheaper (better) plans are more likely to "survive" into the next generation.
2. **Crossover** — take two decent plans and mix them (like a child inheriting some traits from each parent) to make a new plan.
3. **Mutation** — randomly tweak a few decisions in a plan, in case a better option was never tried.
4. Repeat this for many "generations" (typically 200), and the population gradually gets cheaper and cheaper.

This is called a **Genetic Algorithm**, and it's a well-established, decades-old optimization technique — nothing exotic. It's implemented using an open-source library called **DEAP**.

### Why not just try every combination?
Because there are more possible fleet plans than atoms in the observable universe, roughly speaking. A GA doesn't guarantee the perfect answer, but it reliably finds a *very good* one in a reasonable amount of time, without checking everything.

### The "polish" step (a fix we added)
Here's something we found and fixed: even after 200 generations, the GA sometimes leaves a *few* individual decisions slightly wrong — not because the wrong choice is cheaper, but simply because the random breeding/mutation process never happened to try the correct swap for that one slot. We added a cheap clean-up step that runs after the GA finishes: for every single decision slot, try every possible value for *just that slot* (holding everything else fixed), and keep whichever is cheapest. This is called **coordinate-descent local search** — a standard technique, and it's very cheap to run because it doesn't need to search, just check.

This mattered a lot in practice: before this fix, some ships showed fuel choices that got *dirtier* in later years for no economic reason — clearly a search mistake, not a real answer. After the fix, every ship's fuel trajectory only ever moves in a direction that makes sense.

### Warm-starting (making the sweep fast)
We don't just solve the fleet plan once — we solve it **41 times**, once for every $25 step in carbon price from $0 to $1,000 (this whole exercise is called **the sweep**). Solving from scratch 41 times would be slow. Instead, each price point (except the very first) starts its search from the *previous* price point's answer, since the answer probably only needs small adjustments. This is called **warm-starting**, and it's much faster than 41 independent cold solves.

### The "envelope correction" (another fix we added)
Even with warm-starting, the GA doesn't always find the true best answer at every single price point — sometimes the answer found at price $500 turns out to be cheaper even at price $475 than what the GA found when it was actually asked to solve for $475. We added a cheap check after the whole sweep: for every price point, look at *every other already-computed plan* and see if any of them would actually be cheaper at this price. If so, borrow that plan. This can never make anything worse (it's just picking the best of what's already been found), and it fixed a real problem where the very first price point ($0, which has no "previous" point to warm-start from) was landing on a noticeably worse answer than it should have.

We then added one more layer: if a price point's plan got borrowed from very far away, we make it *prove itself* — run one more fresh, independent solve at that exact price, with no bias toward the borrowed answer, and see if it holds up. This caught a real issue: in an earlier version, four consecutive price points ($900, $925, $950, $975) had all silently borrowed the exact same plan from $1000, meaning the app's claim of "the plan is stable up here" was actually "we only found one good plan in this whole range." The independent re-check exists specifically so we don't ship a finding that's actually a search accident.

### A second search option we added: QIEA (Quantum-Inspired Evolutionary Algorithm)

Everything above describes the Genetic Algorithm — the search method that actually produces the fleet plans you see in the live demo today. We've since built and fully tested a second, genuinely different search method: a **Quantum-Inspired Evolutionary Algorithm**, or **QIEA**.

The idea, in plain English: instead of holding a population of complete, fixed guesses the way the GA does, each individual decision — "what fuel does Ship A1 burn in 2028?" — is held as a *spread of possibilities* rather than one fixed answer, similar to how a **qubit** (the basic building block of a real quantum computer) can hold a mix of two states at once until it's measured. Every round, we "measure" (collapse) each of these spreads into one concrete fleet plan, check its cost the normal way, and then nudge every spread a little further toward whatever the best plan found so far actually chose. Over many rounds, the spreads sharpen into confident answers. This nudging step is called a **rotation gate**, a real technique from the published quantum-computing literature (Han & Kim, 2002) — this isn't the GA wearing a different label, the underlying mechanism is genuinely different.

This is a real, working alternative to the GA today: it reliably beats a random baseline, gives the same answer every time for the same starting point, and never picks an option a ship isn't actually allowed to use — confirmed by 7 dedicated automated tests. **It exists as a callable option in the code, a drop-in swap for the GA anywhere in the pipeline, but it is not yet what the live demo runs** — `scripts/build_demo_data.py`, the script that actually builds the website's data file, still calls the classical GA. Pointing the demo at QIEA instead is a small, deliberate next step, not a rebuild.

---

## 8. What's real, what's synthetic, what's "quantum-inspired" (be very honest about this)

**The fleet is invented.** There is no real company called "Bharat Line" or "KnotWise." The ship names in the UI (Knotwise Victory, Pioneer, Endeavour, Horizon, Explorer, Vanguard, Sentinel) and their IMO registration numbers are made up for flavor. The routes are realistic (Mumbai–Rotterdam via Suez, Chennai–Singapore via Malacca, etc.) but the waypoints are hand-drawn approximations, not real AIS ship-tracking data. This is stated plainly in the data file itself (`"status": "ILLUSTRATIVE"` on the routes, `"SYNTHETIC FLEET, PROTOTYPE-GRADE FIGURES"` in the metadata) — nothing here is presented as real-world measured data.

**The regulations are real.** The CII Z-factors, FuelEU's baseline and reduction schedule, NZF's Tier 1/Tier 2 prices ($100/$380), and the EU ETS phase-in percentages are all sourced from the actual regulation texts and cross-checked against multiple independent sources (see `regulations.json`'s own provenance notes — every number records where it came from and when it was checked).

**"Quantum-inspired" is now partially real — and it matters to be precise about exactly which part.** The original plan describes using *Matrix Product States* (MPS) — a mathematical tool borrowed from quantum physics for representing many interacting variables at once — plus a "Born machine" sampler, to compute "how much does decision X depend on the vote" as one precise number, called *mutual information*, instead of estimating it. **That math now exists for real, and is tested** — for a deliberately bounded slice of the problem, not the whole fleet at once.

Here's exactly what's built. For one ship-year at a time (say, "Ship A1 in 2028"), holding the rest of the fleet fixed, the code builds an actual probability cloud — a real quantum state, using the same "Born machine" idea the plan describes (named after physicist Max Born) — spanning that ship-year's six decisions and the five regulatory scenarios, and reads a genuine mutual-information number straight off it, using the same singular-value-spectrum math a physicist would use on an actual entangled quantum system. This isn't an approximation wearing quantum language — it's checked against hand-worked examples, including a subtlety we caught mid-build and now test for explicitly: a simplified two-variable version of this calculation gives a different number than everyday statistics would, for a well-understood mathematical reason (a technical aside worth having ready if a physicist in the room asks, but not one to lead with). We also built the QIEA search algorithm described above — the "quantum metaheuristic" half of the original ambition.

**What's still not built:** running this calculation for the *entire* 10-ship fleet at once, fully linked together (the fleet-wide entangled state the original plan describes) — that's a substantially bigger mathematical and engineering undertaking, and remains future work. **And critically: none of this is wired into the live demo yet.** `scripts/build_demo_data.py` — the script that actually produces what the website shows — still uses only the classical Genetic Algorithm and the classical way of computing exposure (nicknamed "flip-counting": solve the fleet plan separately under each of the five scenarios, then see which decisions come out different — this is what produces the exposure report described in section 2). We did add one cheap, real bridge between the two: a function (`compute_mps_crosscheck`) that takes whatever flip-counting already flagged as exposed and re-checks it with the real tensor-network number, side by side — but it isn't called by `scripts/build_demo_data.py` either, so it doesn't reach the website yet. The website's footer still accurately reads **"PRECOMPUTED DETERMINISTIC DECISION TREE."**

If a judge asks "is this really quantum," the honest answer is now more interesting than a flat no: *"Yes, for real — we built and tested a genuine quantum-inspired search algorithm and a genuine tensor-network mutual-information calculation, 32 new automated tests between them, 236 passing in total across the project. What's on screen right now still runs on the classical version, because we haven't wired the new pieces into the live demo yet — that's the next step, not a discovery that the harder version doesn't work."* That's a stronger, more specific answer than before — and it's still exactly true. Don't round it up further than that: no real quantum hardware is used anywhere, and the fleet-wide (not just per-ship-year) version of the tensor calculation still doesn't exist.

**Everything downstream of the GA (the exposure numbers, the switching points, the sweep) is real math on real (if synthetic) inputs** — it's not decoration. The GA producing the fleet plans is the one piece that's simpler than the original ambition.

---

## 9. Questions a judge will ask, and the honest answer

Prepare these. They come directly from problems we found and fixed (or explicitly chose not to fix yet) while building this.

**"Why does the cost curve rise, then dip, then go flat?"**
Because of how the NZF surplus credit works. As the carbon price rises, ships have more incentive to run cleaner, which briefly makes the fleet's own costs go up (cleaner fuel costs more to buy) before the savings kick in — hence the small rise. Past a point, switching pays for itself and cost retreats. Then, because a surplus credit can never be worth more than the real, fixed Tier 2 price ($380/tonne — that's a genuine regulatory ceiling, not something we invented), there's nothing left to gain once the fleet has captured all the value available below that ceiling — so the curve goes flat. This is a real finding: **there's a hard ceiling on how much a fleet can hedge its way out of a rising carbon tax through decarbonization alone.**

**"Why is 'Capital at Risk' sometimes ₹0.00?"**
Because right now, the only decision in the model that counts as genuine *capital* spending is the shore-power connection (a real $150,000/ship/year cost). Fuel and speed choices are recurring operating costs, not capex. On some runs, no shore-power decision happens to land in the "exposed" (vote-dependent) category, so the capex-specific number is honestly zero — not a bug, just a narrow definition. The bigger, real fix (not yet built) is adding an actual ship-retrofit decision to the model, which is where the real tens-of-millions-of-dollars bets live in reality.

**"Why do the exposure numbers change between runs?"**
Because the search algorithm has some randomness in it, and a meaningful fraction of decisions are genuinely close calls — two options cost almost exactly the same, so which one "wins" can flip between runs. We only count a decision as "confidently exposed" if multiple independent search runs (called *seeds*) agree on it; the rest are honestly labeled "unstable" rather than pretended to be certain. This is a known, documented limitation of using a Genetic Algorithm here rather than something more precise — it's part of why the original plan wanted the "quantum-inspired" approach eventually, since it would give exact numbers instead of noisy estimates.

**"Is this the real IMO vote date?"**
Yes — 4 December 2026, confirmed against the IMO's own public announcements (their Second Extraordinary MEPC Session), subject to confirmation by MEPC 85 (30 Nov–3 Dec 2026). This is checked and current as of the last data refresh.

**"Why do Liberia and Brazil show 'N/A' on the price slider?"**
Liberia's proposal isn't a price at all — it's a market mechanism (tradeable surplus units) with no posted per-tonne figure, so there's honestly nothing to put on a dollar axis. Brazil's proposal is a percentage-reduction schedule, not a price, and we haven't built the conversion formula for it yet (we did build one for the "adoption fails" scenario, using the FuelEU penalty formula as a stand-in — Brazil would need its own). Clicking either button now pops up a message explaining exactly this, live, instead of doing nothing.

**"Is the map real ship tracking data?"**
No — it's OpenStreetMap (a free, open-licence map, like Wikipedia but for maps) with hand-drawn approximate shipping lanes and a simple animation looping the ship icons along them. It's honestly labeled `ILLUSTRATIVE` in the data.

**"Why a Genetic Algorithm and not the tensor-network approach from the plan?"**
Originally: time. We built the classical GA first because it's well-understood and gave us a working foundation fast. **That's since changed, partially.** We've now built and tested a real quantum-inspired search algorithm (QIEA) and a real tensor-network mutual-information calculation for the Exposure Map (both described in sections 7–8), adding 32 new automated tests on top of the original 204. What hasn't changed yet is the live demo: it still runs on the classical GA and classical flip-counting, because the new pieces haven't been wired into `scripts/build_demo_data.py` — the script that builds the website's data file — yet. So the honest answer today is: *the harder version is real, tested, and working; it's just not yet what's plugged into the website you're looking at.*

---

## 10. Website walkthrough — every screen, in order

**Header (top bar):** the KnotWise name, and a small tag showing "IMO 4 Dec 2026 Vote" — the real vote date, always visible.

**The Guide button:** opens a plain-English explainer built right into the app (similar spirit to this document, but shorter and written for a first-time visitor rather than a presenter). Every number in it is pulled live from the same data file — nothing in it is hand-typed, so it can never drift out of sync with what the charts show.

**The Scenario Slider (top of the dashboard):** the centerpiece. Five buttons, one per live regulatory proposal (Approved Text, Liberia, Tuvalu, Brazil, "Adoption Fails Again"), each showing its own price if one exists — clicking jumps the slider there. Below the buttons, a continuous drag-slider from $0 to $1,000/tonne lets you test *any* price, not just the five named ones. Whichever proposal's price is currently closest to the slider gets visually highlighted — this updates live as you drag, it doesn't just freeze on the last button you clicked.

**The map (left side):** an OpenStreetMap-based dark map showing the fleet's routes as dashed lines, with small circular icons for each ship animating along their assigned route. A ship glows white and gets a "REALLOCATED" badge if its plan at the current price differs from the plan at $0/tonne — a quick visual signal of "this ship's strategy just changed."

**The three metric cards (right side):**
1. **Cost Variance Across Regulations** — the single biggest, most defensible number: the gap in total cost between the cheapest and most expensive of the five regulatory outcomes. This is the real "how much money rides on this vote" headline.
2. **Vessels Modifying Strategy** — how many ships have a decision that's currently "active" (i.e., the current price sits inside a bracket where that ship's choice changes). Can genuinely read zero at very low or very high prices — and if so, the card now says plainly that the plan has stabilized, rather than leaving a bare, confusing zero.
3. **Total Fleet Expenditure** — the total 5-year cost at the current price, plus a live comparison against the $0/tonne baseline.

**Three pop-up panels, opened from buttons on the cards:**
- **Exposure & Risk Atlas** — the detailed breakdown of which decisions are "safe" vs. "bets," split into confidence tiers (explained below).
- **Fleet Decision Matrix** — a full table, ship by ship and year by year, of exactly what's chosen (fuel/speed/route/etc.), with a toggle to switch which decision type you're viewing, and highlighting for anything that changed from the baseline or is flagged unstable.
- **Sensitivity Curve** — the full $0–$1,000 cost-vs-price chart, with a live-computed one-line explanation of its actual shape (see section 9's first answer).

**The confidence tiers, explained simply:** we don't just say "here are the exposed decisions" — we grade our own confidence.
- **Unanimous** — every independent search run agreed on this decision, across every regulatory scenario. The strictest bar. By definition, if it's unanimous *and* the value differs across scenarios, it's a genuine exposed bet — but this bar is so strict that very few decisions clear it.
- **Majority** — at least 2 of 3 independent runs agreed. A looser, second-tier bar that catches far more real signal, clearly labeled as lower-confidence than "unanimous."
- **Unstable / High-Variance** — the runs disagreed entirely. Honestly excluded from the headline numbers rather than reported as if certain.

**Footer:** fleet name, and the honest label "PRECOMPUTED DETERMINISTIC DECISION TREE" (see section 8 — have your one-sentence answer ready).

---

## 11. Glossary (every acronym used above, in one place)

| Term | Plain-English meaning |
|---|---|
| IMO | International Maritime Organization — the UN body regulating international shipping |
| MEPC | Marine Environment Protection Committee — the IMO group that votes on this |
| CII | Carbon Intensity Indicator — an efficiency rating, no direct fine |
| FuelEU (Maritime) | EU rule requiring a cleaner average fuel mix each year, with a real financial penalty |
| NZF | Net-Zero Framework — the specific rule being voted on 4 Dec 2026, with real dollar-per-tonne prices |
| EU ETS | EU Emissions Trading System — already real and priced today, no vote needed |
| GHG | Greenhouse Gas |
| tCO₂e | Tonne of CO₂-equivalent — the standard unit carbon prices are quoted in |
| GT | Gross Tonnage — a measure of a ship's overall internal size |
| DWT | Deadweight Tonnage — how much cargo weight a ship can carry |
| GA | Genetic Algorithm — the evolution-inspired search method used to find fleet plans |
| QIEA | Quantum-Inspired Evolutionary Algorithm — a real alternative to the GA where each decision starts as a "maybe-this, maybe-that" spread (like a qubit) and sharpens over many rounds, instead of guessing complete plans outright. Tested; not yet used by the live demo |
| Qubit | The basic unit of a real quantum computer — can hold a mix of two states at once until "measured." QIEA borrows this idea in ordinary software, with no real quantum hardware involved |
| Genome | In this project, one complete candidate fleet plan (all ships, all years, all decisions) |
| Warm start | Starting a new search from a previous, similar answer instead of from scratch |
| Envelope correction | Checking whether any other already-found plan is secretly cheaper at a given price |
| Local search / polish | A cheap clean-up pass that fixes obviously-wrong individual decisions after the main search |
| Switching point | The exact carbon price at which a specific decision flips from one answer to another |
| Exposure Map | The report of which decisions are vote-dependent, and how much money is on each |
| Matrix Product State (MPS) | A structure, borrowed from quantum physics, for representing a probability cloud over many linked variables at once instead of one at a time. Real, tested, per-ship-year today; fleet-wide is future work |
| Born machine | The specific way of reading real probabilities out of an MPS, named after physicist Max Born |
| Mutual information | A precise, computed number for how much one thing (e.g. a fuel choice) depends on another (e.g. the vote outcome), instead of an estimate |
| Surplus unit | A tradeable credit a ship earns for beating its NZF compliance target |
| Pooling | Combining several ships' compliance balances so only the group total needs to be positive |
| AIS | Automatic Identification System — real ship-tracking data (not used here; our routes are hand-drawn) |
| JSON | A text format for structured data — the file format `demo_data.json` is written in |

---

## 12. If you remember nothing else

1. There's a **brain** (Python, does the math, runs ahead of time) and a **face** (the website, only ever reads a file the brain already wrote).
2. The brain's live demo runs on a **Genetic Algorithm** (evolution-style search) — say this plainly if asked. A genuinely different alternative, a **Quantum-Inspired Evolutionary Algorithm (QIEA)**, and a real (per-ship-year, not yet fleet-wide) **tensor-network mutual-information calculation** for the Exposure Map both now exist and are fully tested — but neither is wired into the live demo yet. Real quantum *hardware* is never used anywhere in this project.
3. The headline number — **₹X crore riding on the December 4 vote** — comes from `plan_spread`, the gap between the cheapest and most expensive of five real regulatory outcomes. It's the most robust number in the app.
4. The curve rising-then-flattening is a **real finding**, not a glitch: NZF's surplus credit is capped at the real $380/tonne Tier 2 price, so decarbonization can only offset so much of a rising tax.
5. Everything is honestly labeled: synthetic fleet, illustrative map, precomputed decision tree. Nothing here claims to be more than it is — and that's a feature, not a weakness, in front of a technically literate panel.
