# Design Note: Pooling Locality in the Compliance Ledger

**Status: gating decision for tensor code. Nothing in Phase 3/4 is built until this is accepted or revised.**

---

## 1. The problem, stated precisely

§3.2 claims: *"The bond dimension is literally the ledger... An MPS is the canonical object for exactly this coupling topology."*

This is half true, and the half that's false matters.

**Banking is genuinely local.** A vessel's compliance balance in year Y depends only on its balance in year Y−1 (carry-forward) and Y+1 (borrowing against next year, capped at 2%). Under a **vessel-major** site ordering — (vessel 1: year 2026, 2027, …, 2030), (vessel 2: year 2026, …), … — a vessel's own years are adjacent sites. The bond between them is a genuine nearest-neighbor MPS bond, and the running per-vessel balance is exactly the kind of small, sequential state an MPS bond is built to carry. This part of §3.2 is correct.

**Pooling is not local under any 1D ordering.** A pool's balance is a sum over an arbitrary subset of vessels — up to all 24 — within the same year. Vessels in a pool are, in general, far apart on a vessel-major chain (up to `years × vessels_apart` sites away). This is not a defect of the vessel-major choice specifically; it is a structural fact. An MPS bond graph is a **path graph** — each site has exactly two neighbors. Pooling's natural graph is a **star or clique** over the pool's member vessels within a year — every member touches every other member simultaneously. No reordering of a 1D chain embeds a clique as nearest-neighbor unless the clique has size ≤ 2. §3.2's "non-separable in both directions simultaneously" line is accurate as a description of the difficulty; it is not, on its own, a solution.

So the choice is real: either the bond carries enough state to represent a running pool total (dimension blow-up, addressed in §2A below), or pooling is enforced somewhere other than the bond (§2B), or the site ordering is chosen to make pooling local at the cost of making banking long-range instead (§2C).

## 2. The three options, evaluated

### (A) Running pool sum on the bond, with L-level discretization

**Mechanism.** Keep vessel-major ordering. Extend the bond's carried state to include not just each vessel's own banking balance but a running tally of the pool's cumulative balance as the chain sweeps through pool members.

**Cost.** This is where the option fails on arithmetic, not principle. A pool's running sum, if each vessel's individual balance is discretized to L levels, needs a bond coordinate that can represent the sum of up to 24 such values — roughly `vessels × L` states just for the pool-sum coordinate, multiplied by whatever the banking-only bond dimension already needs (4–16, per §6.1's target). At a coarse L = 8, that is roughly 24 × 8 = 192 pool-sum states before multiplying by banking's own dimension; combined, a bond dimension in the low thousands. §6.1's stated target for the whole system is bond dimension 4–16. This option overshoots the stated compute budget by two to three orders of magnitude, on paper, before any code is written.

**What breaks at coarse L.** This is the more serious problem, and it is exactly the one the brief flagged: coarsening L to make the blow-up tractable does not degrade *accuracy*, it degrades *feasibility*. A pool-positivity constraint (`total pool balance ≥ 0`) is a hard threshold. If the discretization rounds a true balance of −0.3 to a bucket centered on 0, the model can represent a pool as compliant when it is not. **A hard regulatory constraint silently becoming approximate is not an acceptable failure mode** — it means the tool could tell an operator they're FuelEU-compliant when they are exposed to a real financial penalty. This is disqualifying on its own, independent of the dimension-count problem.

**Verdict: reject.** Both the compute cost and the feasibility-corruption risk are severe, and they get worse together — the only way to make L fine enough to avoid corrupting feasibility is to make the dimension blow-up worse, not better.

### (B) Hybrid — exact banking on the bond, exact pooling at the particle level

**Mechanism.** Keep vessel-major ordering, keep banking exactly on the bond at its natural small dimension (4–16), as in the uncontested half of §3.2. Do not attempt to represent the pool sum on the bond as a source of truth. Instead, enforce pooling where it is actually checkable exactly: **at the SMC particle level.**

This works because of a fact about how the optimizer is already structured (§5 Phase 3): each SMC particle, once fully sampled across all (vessel, year) sites, **is a complete fleet configuration**. Every vessel's fuel choice, speed, and banking state for every year is known for that particle. Pool membership and pool balance for any pool, in any year, can therefore be computed exactly — by summing the relevant vessels' known balances — as a deterministic function of the particle, not an approximation of it. The projection operators already planned for Phase 4 (hard masks for fuel availability, vessel-fuel compatibility, etc.) get one more member: a pool-positivity and no-worsening check, evaluated per particle, that either passes or the particle is rejected/reweighted to zero. This is exact, not discretized, because it operates on the particle's actual sampled values, not on a compressed bond coordinate.

**The cost, honestly stated.** Pooling can only be evaluated once all pool members' relevant year has been sampled — for a vessel-major chain, that means waiting until the last pool member's site for that year has been visited, which in the worst case is near the end of the sweep. This makes pooling a **delayed constraint** relative to banking's **immediate constraint** (checkable the moment a vessel's own consecutive sites are sampled). Delayed constraints in SMC mean particles can travel a long way down a path that is doomed to fail pooling before that failure is detectable, which wastes search effort — not correctness, effort.

**The bond's remaining role.** This is where "a coarse pool summary on the bond for search guidance" earns its place, and it is the piece that makes this option efficient rather than merely correct. A coarse, lossy running estimate of each pool's partial balance *can* live on the bond — not as the accept/reject authority (that stays exact, at the particle level, per the paragraph above), but as an importance-sampling signal that lets the SMC resampling step downweight particles heading toward likely pool infeasibility *before* the exact check is even reachable. Because this coarse value never gates a final decision — it only influences which particles get more computational attention — its lossiness is confined to search efficiency. If the coarse estimate is wrong, the optimizer wastes some particles or spends slightly longer converging. It cannot, even in principle, report an infeasible pool as compliant, because the exact particle-level check is still what runs before any result is reported.

**Verdict: recommended.** This is the only option of the three that satisfies the standing rule stated in the brief — truncation may degrade search quality, never feasibility — as a structural property rather than a hope. It also preserves the genuinely correct half of §3.2 (banking is a real MPS bond primitive) without asking the bond to do something it structurally cannot do cheaply.

### (C) Reordering (e.g., year-major)

**Mechanism.** Reorder sites as (year 2026: vessel 1…24), (year 2027: vessel 1…24), … so that all vessels in a pool, within a given year, are adjacent.

**What this actually buys.** Pooling becomes local within a year-block. But banking — a vessel's year Y balance depending on its own year Y−1 — now requires reaching across an entire year-block (24 sites) to find the same vessel's previous-year site. Banking becomes exactly as long-range as pooling was under vessel-major ordering. This is not a fix; it is a swap. The underlying fact from §1 holds regardless of ordering: an MPS's path-graph bond structure cannot simultaneously localize a chain-structured constraint (years, inherently sequential) and a clique-structured constraint (pool membership, inherently fleet-wide within a year) unless the clique has at most two members. No ordering escapes this, because it is a statement about the topology of the constraint graph versus the topology of the MPS bond graph, not about which axis is listed first.

**The only real escape** from this trade-off would be a bond structure that isn't a 1D path — a tree tensor network or PEPS with genuine 2D or hierarchical connectivity could in principle localize both simultaneously. That is a materially different and substantially harder architecture to implement correctly in three weeks, and belongs in Track F, not this decision.

**Verdict: reject for Track S.** Confirmed as a non-solution for a 1D MPS; noted as a legitimate Track F direction if there is appetite to move to a tree tensor network later.

## 3. Recommendation

**Adopt (B).**

- **Final site ordering:** vessel-major — (vessel 1: year 2026…2030), (vessel 2: year 2026…2030), …, (vessel 24: year 2026…2030), with the regulatory leg `r` as an additional site entangled globally (not part of the vessel-year chain's locality structure, and not affected by this decision).
- **What each bond carries:** between a vessel's own consecutive-year sites, the exact banking/borrowing balance, small discrete state, target dimension 4–16 as already stated in §6.1. Between different vessels (i.e., every other bond in the chain), a coarse, lossy pool-balance-progress estimate for search guidance only — dimension to be tuned empirically in Phase 3, expected small (single digits to low tens), since it never needs to be exact.
- **Discretization scheme and granularity:** exact integer compliance units for banking (no discretization loss — compliance balances are naturally quantized to reporting-period units already). The coarse pool-guidance value on inter-vessel bonds may be discretized freely, including quite coarsely, precisely because it is advisory.
- **Where the hard feasibility guarantee lives, per constraint class:**
  - **Banking caps (2% borrowing limit, 1.1× repayment, no consecutive-period borrowing):** on the bond, exact. This is the one class of constraint the bond was always suited to carry, and nothing here changes that.
  - **Pool positivity, no-worsening:** at the particle level, exact, evaluated as a projection operator once a particle's relevant year is fully sampled across all pool members. Never on the bond as source of truth.
  - **NZF surplus/remedial units, EU ETS allowances:** these follow the banking pattern (per-vessel, with limited transferability — NZF surplus units transfer once; EU ETS allowances trade on an open market but are tracked per-company in this model) rather than the pooling pattern, and belong on the bond alongside banking, at the same small dimension. They do not introduce a new locality problem.

**§3.2 sentences that survive verbatim:** the claim that banking is genuinely local and that the bond is the correct primitive for it; the description of FuelEU's three mechanisms and their combinatorial constraints; the "run one vessel deliberately dirty" pooling-strategy argument itself (this is a claim about what the *optimizer* finds, not about *where* the constraint is enforced, and holds regardless of which of (A)/(B)/(C) is chosen).

**§3.2 sentences that must be softened:** *"The bond dimension is literally the ledger... Banking couples years; pooling couples vessels; the problem is non-separable in both directions simultaneously... An MPS is the canonical object for exactly this coupling topology."* This overstates what the bond does. The corrected version should say something close to: *the bond is the exact ledger for banking, which is genuinely local; pooling is enforced exactly at the particle level, with the bond providing only a lossy search-efficiency signal, not the feasibility guarantee, for that constraint.* This is a real, defensible, still-interesting architectural claim — it is just a narrower one than the current sentence makes, and the narrower one is the one that survives a hard question from a judge who knows what an MPS bond actually is.

## 4. Folding in fleet composition

The PS asks for "optimal mix of vessel types, capacities" — the case study as specified fixes the 24-vessel fleet and optimizes deployment only (route, speed, fuel, shore-power, retrofit timing per existing vessel). This under-covers that clause of the PS.

**Cost of adding it properly.** A full newbuild/capacity design search — continuous vessel size, engine design, capital structure — is out of scope for three weeks and arguably out of scope for the PS's intent, which reads as being about deployment mix more than shipyard design.

**The minimal honest version, and its cost.** Add a small **fleet-composition site per year** — not per vessel — carrying a discrete decision from a small menu (e.g., charter-in a feeder-class slot, charter-in a deep-sea-class slot, retire a vessel, trigger a newbuild-class placeholder, no change). This is a *year-indexed*, fleet-level site, not a per-vessel one: it adds 5 new sites (one per year of the 2026–2030 horizon) to the existing 120 (vessel × year) sites — a 4% growth in site count — with a small local dimension (order 6, the size of the composition menu) compared to the roughly 200-state local dimension already carried by each vessel-year site. This is tractable to add within Track S without materially changing the compute profile assessed in §6.1.

**Recommendation:** add this minimal composition layer to Phase 3's build scope, not as a stretch item. It is the difference between honestly covering the PS's "optimal mix of vessel types, capacities" clause and merely asserting we do. Do not attempt a continuous or capital-design-level composition search; that is Track F, alongside the real-options retrofit-timing work already deferred there.

## 5. What this note does not resolve

The exact bond dimension for the coarse pool-guidance signal (§3, second bullet) is left to be tuned empirically once the walking skeleton exists — this note fixes the *architecture*, not every hyperparameter. The interaction between the composition site (§4) and the pooling mechanism (§2B) — i.e., whether a newly chartered-in vessel can join an existing pool mid-year — is a modeling detail for Phase 4, not an architectural one, and does not change the recommendation above.
