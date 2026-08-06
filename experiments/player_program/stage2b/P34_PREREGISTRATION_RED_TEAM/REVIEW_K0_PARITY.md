# P34 adversarial review — dimension: K0 PARITY

ADVERSARIAL REVIEW. Reviewers are independent of the preregistration author. A clean review does not make an arm true; it makes it fittable.

**Reviewer dimension:** per-arm K0_MATCHED completeness and fairness for all 26 arms — does any treatment carry an information advantage its declared null lacks (the S4 lesson), and the four mandated probes (A04 post-kernel-strike null; A02/A15 accounting; D1 null fairness; enumeration-grid K0 sharing).

**Verdict: ACCEPT_WITH_REQUIRED_CHANGES.**

## STOP-CONDITION NOTICE (stated first, per node rules)

Two findings below (K1, K2) cannot be closed without a decision about a K0 construction — which null A11 actually has, and what intercept structure the calibration arms and nulls carry. Under this node's stop conditions ("a finding would change ... the K0 structure ... HALT and raise, do not resolve it inside the node") I raise both and resolve neither. My reading of which resolution the frozen precedence rules already force is recorded, but the decision belongs to the coordinator/P35, not to a reviewer. Nothing I found changes the primary target, folds, clustering, resampling, universe, cutoff-valid set, or leakage status.

## Blindness attestation

I did not author the P33 preregistration or any input to it. I did not read any other reviewer's file: I listed the P34 directory's filenames once, solely to confirm my own output filename does not collide, and opened none of them. I read nothing under `SEALED_RESULTS` (and did not look for it). I fitted nothing; no target value entered any statistic I computed; no comparative performance of any challenger was inspected.

## 1. Hash verification (before any other read)

`Get-FileHash -Algorithm SHA256` over raw bytes — all four match the task-pinned values exactly:

| file | expected (pinned) | match |
|---|---|---|
| `stage2b/P33_PREREGISTRATION_DRAFT/SPEC.json` | `066b2a04...d347d093` | YES |
| `stage2b/P33_PREREGISTRATION_DRAFT/REPORT.md` | `6d945b86...1681248ab` | YES |
| `stage2b/P32_CANDIDATE_SYNTHESIS/SPEC.json` | `1dc25981...9198c2138c` | YES |
| `stage2b/P30_EVIDENCE_PACKET_V3/EVIDENCE_PACKET_V3.json` | `95d2412c...950875e75` | YES |

## 2. What I measured, and how

All numbers below come from two scripts I ran against the live artifacts (scratchpad
`p34_k0_parity_measurements.py`, `p34_n_contract.py`; full JSON output retained in the run log).
Both are feature/schedule-only: the target column is dropped immediately after
`possession_features.load_universe()` and never enters any statistic; nothing is fitted (least
squares over feature columns only, for R2/condition diagnostics); no performance number exists
anywhere in the output. Universe re-derived live: 2,982 rows / 1,491 clusters; the five D006 folds
with train rows 410/888/1408/1932/2552 and train clusters exactly rows/2 — matches the draft.

Headline measurements (per training fold, `train_lt_2022 .. train_lt_2026` order):

* **A02 identities**: `(own−opp)−pace_gap`, `(own+opp)−2·proj`, `offset−log(proj)` all max-abs **0.0**; corr(pace_gap, log_exposure) = **−7.5e−19**; R2 ≈ 0 and condition number 1.000 in all five training folds. New structural result: **offset max within-cluster range = 0.0** (the offset is cluster-constant) and **pace_gap max |within-cluster sum| = 0.0** (exactly antisymmetric) — so the orthogonality is by construction, not sample luck.
* **A15**: corr(pace_gap, pace_gap·asym) per training fold ≤ **2.7e−18** (structural: gap flips sign across the two rows of a game, asym flips sign, so the product is cluster-symmetric while gap is cluster-antisymmetric). R2 of the treatment `gap·asym` on A15's full null `[offset | gap | depth | opp_depth | asym]`: **0.039 / 0.022 / 0.021 / 0.021 / 0.021**. R2(asym ~ depth, opp_depth): 0.816–0.860. Null-design condition numbers 10.2–17.9 (fold 1 worst), full-arm design nearly identical.
* **A04**: R2 of the interaction `1[SHALLOW]·(off−m̄)` on its null columns `[1[SHALLOW], (off−m̄)]`: **0.823 / 0.623 / 0.549 / 0.552 / 0.534**; sd of the offset within the shallow tier **0.017–0.024** (log scale) on **40/52/64/76/92** shallow training rows.
* **A03 tier support** (t=3): shallow training clusters **24/36/46/57/69** — matches the draft exactly. Depth histogram {0:37, 3..9:76 each, 10:2413} — matches.
* **A05**: training playoff clusters **17/40/60/82/106**; fold-2026 test playoff rows **0** — matches.
* **A14**: expansion training clusters **0/0/0/0/46**; expansion teams {1611661331:2025, 1611661327:2026, 1611661332:2026}; PHO/PHX first season 2021 — matches.
* **A03/A07 collapse re-check and the n_i clock (finding K6)**: with n_i counted over **universe rows**, I get R2 = 0.7061/0.3674/0.2643/0.2148/0.1949 — **not** the draft's 0.7134/0.3321/0.2359/0.1923/0.1770. With n_i counted over the **2,990-row prior artifact** (the contract schedule, including the four D010-excluded 2021 opening-day games), I reproduce the draft's numbers **exactly to 4 decimals in every fold**. Verdict unchanged either way (nothing near 0.998001 / 0.999; no collapse), but see K6.
* **A07 absorption**: R2(exp(−n/5) ~ depth) = 0.956/0.540/0.417/0.358/0.335 under the universe clock (draft reports 0.958/0.494/0.379/0.327/0.310 under the contract clock) — same conclusion (elevated fold 1, below blocking threshold), different bytes; K6 pins the clock.
* **D1 factual basis re-verified against bytes**: `projected_exposure_v1/PROJECTED_EXPOSURE_RECEIPT.json` `source_counts` = team_window_same_season 2762 / prior_season 183 / league_prior_all 37 / unresolved 8 — the incumbent switches tiers and never blends, exactly as the draft's D1 resolution states.
* **Incumbent structure re-verified against bytes**: `possession_features.py` — `incumbent_input` docstring: "The incumbent has no fitted feature — its prediction IS projected_team_off_possessions"; module docstring lines 50–67: pace_gap "is the part that does not" enter the offset. Load-bearing for K5.

## 3. Findings

### K1 (Severity A) — A11's K0 block is self-contradictory in the frozen bytes; one reading invalidates the arm, and one kill condition can never fire

Three clauses of the same frozen record disagree about what A11's null IS:

1. **Formula**: "null fixes rho == 1" → null = identical machinery with the single blended column `dblend_t(1)` and free β. This is also what the frozen P26 contract's `hierarchical_pooling` kind prescribes ("pooling strength fixed at its null" — `validate_k0_matched.py`, `KINDS_REQUIRING_FIXED_PARAMETER`).
2. **k0_matched.null**: "`[log_exposure | dcur_t | dprev_t]` with rho fixed at 1 — BOTH lower-order main effects in K0". Everywhere else in this document, `[A | B | C]` notation denotes free design columns. Two free mains are **not** `dblend(1)`: the blend's weights `n_cur/(n_cur+m_prev)` vary by row, so `dblend(1)` is not in span{dcur, dprev}, and no (b1,b2) reproduces it. Under this reading the null (2 free df) is a model the arm (offset + β·dblend(ρ), 1 df per grid element) **cannot reproduce and does not nest** — the null holds a flexibility advantage over the arm (the mirror image of S4), "rho fixed at 1" is false of it, and the declared inference structure ("every null is term_removal or parameter_fixed_at_null") is violated.
3. **kill_conditions**: "rho interval includes 1 (null value) in every evaluable fold under family correction". rho is not a GLM coefficient. Each enumerated element **fixes** rho ∈ {0.25, 0.5, 0.75}; the only frozen interval machinery is the training-cluster bootstrap over fitted coefficients (which for A11 is β alone). No procedure frozen anywhere in this record can produce a "rho interval", and any bootstrap-over-grid distribution is bounded above by 0.75 < 1 — **this kill condition can never fire as written**. The arm's declared falsifiability is weaker than the record makes it look.

Reading (1) is coherent on every other clause, including the stated rationale (under rho=1 the null carries prior-season information, so the treatment cannot take credit for merely having it). My assessment is that frozen precedence (the arm's own formula, plus the frozen P26 kind) already forces reading (1) — but per the standing rules I report the contradiction rather than reconcile it. **Close by**: pinning the null to reading (1) in the frozen record, striking the two-free-mains gloss, and replacing the rho-interval kill with a decidable per-element criterion (the per-element β interval plus the existing thin-stratum-concentration and sign kills) — or withdrawing the arm. Raised as stop-condition-adjacent (K0 structure); not resolved here.

### K2 (Severity B) — "the preregistered intercept structure" is never preregistered, and its worst-case default recreates S4

A01's null: "[log_exposure] with slope fixed at 1 and **the preregistered intercept structure**"; A03/A06: "with incumbent intercept structure". The phrase originates in the packet's `k0_matched.core_rules` and the P26 contract ("the preregistered lower-order intercept structure"), and every upstream document defers to "the preregistered" one — but **P33 is the preregistration and nowhere defines it**. The formulas of A01–A06 carry no global intercept term, which supports a no-free-intercept reading (under which A01/A02/A05/A16's nulls have zero fitted parameters and equal the frozen incumbent exactly — coherent, and "delta = 0 recovers the incumbent exactly" is then literally true). But P26's own report calls the intercept structure something the null *carries*, and its validator blocks calibration K0s lacking declared lower-order structural terms ("without it the null is a straw").

Why this is a K0-parity finding and not pedantry: the choice is currently left to the P36 implementer, and **standard GLM/IRLS implementations add an intercept silently by default**. If any arm design picks up a default intercept while its null is coded as bare offset (per the literal "[log_exposure]" glosses), that arm gains a free recalibration intercept its null lacks — the exact P2/S4 defect this program has paid for twice, reintroduced by an undefined term at precisely the point the S4 lesson lives. **Close by**: stating per arm (at minimum A01–A06; ideally all 26) whether a global intercept exists, identically in arm and null, and adding an explicit invariant that no implementation-default intercept may enter any design. Raised as stop-condition-adjacent (K0 structure); not resolved here.

### K3 (Severity B) — the P33 K0 declarations cannot pass, or even be consumed by, the frozen P26 K0-contract validator

The frozen `P26_ARM_SPECIFIC_K0_CONTRACT/validate_k0_matched.py` is the only executable enforcement of the per-arm K0 contract, and:

* **Schema**: P33's `k0_matched` blocks lack every structured field the validator reads (`invariants.lower_order_structural_terms`, `null_construction`, `claimed_signal_axes`, structured `fold_local_fallback` with `registered_before_results`/numeric trigger). As frozen, the validator cannot run against the preregistration at all.
* **Substance, where translatable**: R8 requires a calibration_only arm to name a role-"slope" parameter with null_value **exactly 1.0**. A01 and A04 declare role "slope" with null_value **0** (the deviation-from-1 parameterization delta/delta_S — mathematically equivalent, byte-level non-compliant). A02, A03, A05 and A06 are calibration_only with **no slope-role parameter at all** (blend-weight, intercept, intercept and drift calibrations respectively) → R8's `tested_parameter_missing, missing_role=slope` fires on each. The P26 rule was written for slope recalibration only.
* The P33 inference block's guard chain (P22/P23/P25/P27 per GATE_INVOCATION_CONTRACT sections 1–6) **does not include the P26 K0 validation** — I searched GATE_INVOCATION_CONTRACT.md for it: zero matches. So nothing currently frozen says who enforces the K0 contract at fit time, on what record format.

**Close by** (at P35): emit per-arm P26-schema K0 records with the slope-parameterization equivalence (delta = 0 ⟺ slope = 1) adjudicated on the record, and either extend the calibration_only rule to intercept/blend-weight calibrations or record the interpretation; name the node/call site at which `validate_k0_matched` runs. If instead P26 validation is considered superseded, say so in a frozen record — silent non-enforcement of the K0 contract for exactly the calibration family is the S4 lesson unlearned.

### K4 (Severity B) — A08's d_t centering constant is unpinned across the K grid, so whether the two elements share one K0 is undecidable from the frozen bytes

A08's null is `[log_exposure | d_t]` and its treatment L_t uses the trailing-K league mean with K ∈ {20, 80}, each element charged. But d_t's own definition ("strictly-lagged mean of prior-game realized regulation-equivalent pace **minus lagged league mean**") does not say which window that inner league mean uses. If it is all-prior (the D6 note "A08/A09/A10/A11 all-prior/EWMA-on-grid" suggests this), d_t is K-free, the two grid elements share one null, and A08's null is the same object as A09/A10's — fair and clean. If an implementer builds it with the trailing-K mean, the two elements carry **different nulls** `[offset | d_t(20)]` vs `[offset | d_t(80)]`, the "identical machinery" claims across A08/A09/A10 silently break, and the frozen A04/A09 collapse test (defined on "A09's rebuilt lagged deviation") no longer speaks for A08's columns. **Close by**: one sentence at P35 pinning d_t's league-mean window as K-free and shared across A08/A09/A10 (or, if per-K is intended, declaring per-element nulls explicitly).

### K5 (Severity C) — "incumbent structural terms" is a misnomer for gap/depth/opp_depth in the A07/A12/A14 nulls; the grant is fair but the label invites a wrong claim

A07/A12/A14 grant their nulls free coefficients on `gap, depth, opp_depth`, labeled "incumbent structural terms" / "the full incumbent structure". The frozen producer's own bytes contradict the label: the incumbent "has no fitted feature — its prediction IS projected_team_off_possessions" (`incumbent_input`, lines 399–406), and pace_gap is explicitly the part of the prior information that does **not** enter the projection (lines 50–67). These nulls are therefore strictly *stronger* than the incumbent (up to 4–5 fitted df), which is the deliberate and correct S6-direction-1 choice — and it is symmetric, since each arm's design carries the same terms, so **no unfairness exists**. Record so that (a) P36 never asserts these nulls "recover the incumbent" at their fitted coefficients, and (b) no one reads MAE(K0[A07]) as an incumbent benchmark. Suggested relabel: "receipted incumbent-path features granted to the null (S6 direction 1)".

### K6 (Severity C) — the n_i clock is the contract schedule including the D010-excluded games; the frozen text supports it but never says it, and I could only discover it by failing to reproduce the draft's numbers

The draft's A03/A07 collapse numbers reproduce exactly (4 decimals, every fold) **only** when n_i counts strictly-earlier same-season rows of the 2,990-row prior artifact — i.e. the 2021 opening-day games that the universe excludes DO count toward n_i. The universe-row clock gives materially different bytes (fold-2 R2 0.3674 vs 0.3321). "Completed same-season contract games" (A07's frozen wording) supports the contract reading, and it is the right one — but nothing in the record states that D010-excluded games count. Since w(n)/decay machinery is shared arm-and-null in A07/A12/A13/A14, parity is automatic once the clock is pinned; if left unpinned, an implementer using the universe clock would build a *different preregistered feature* while believing themselves compliant. **Close by**: one sentence at P35 — "n_i / n counts are computed on the contract schedule (2,990 team-game rows of team_possession_prior_v1), including universe-excluded games."

### K7 (Severity C) — no frozen rule for bootstrap draws or IRLS fits that degenerate asymmetrically between arm and null

The train_refit stream (B = 2,000, cluster resample with refit) can draw training sets in which a tier/indicator treatment column is constant — a state that breaks the ARM's fit while leaving the null (which lacks the column) intact. Measured, the probability of a fully-empty draw is negligible everywhere (worst case A03 fold 1: 24 shallow clusters of 205; P(zero in a 205-draw resample) ≈ e^(−25.5) ≈ 8e−12; A05 fold 1 ≈ 4e−8), but *near*-degenerate draws (1–2 indicator clusters) will occur and produce wild arm-side coefficients with no null-side counterpart. Similarly, no rule exists for an IRLS non-convergence (100-iteration cap) that hits one side of a pair. Both asymmetries only widen arm-side intervals — i.e. they push toward kills, the conservative direction — so this is a C: declare one symmetric rule at P35 (e.g. a draw in which the treatment column is constant, or either member of a pair fails to converge, is recorded NA for BOTH members of the pair), so the behavior is preregistered rather than implementation-defined.

### K8 (Severity C) — A23's two bundles have per-bundle nulls with potentially different evaluable sets, inside one Holm family

bundle_AI's opener rule is an S7 fold-level fallback (can change fold evaluability, arm-and-null identically); bundle_OM's opener rule is a deterministic cap assignment (cannot). The two charged elements may therefore be tested on different evaluable fold/row sets while competing in `schedule_context_family` with A25. Each element's null matches its own machinery — fair per element, and declared. Record only so the family-level Holm is never read as comparing like-for-like row sets.

## 4. The four mandated probes — answers

**A04 post-kernel-strike null: COHERENT.** The null `[log_exposure | 1[SHALLOW] | (log_exposure − m̄)]` contains exactly the interaction's lower-order terms (tier main + global slope; the struck kernel basis left no orphaned lower-order structure), the arm design nests it, and the S4 confound pattern is preregistered as a kill, not a find. Measured: the interaction retains identifiable residual variation in every fold (R2 on null columns 0.53–0.82, never near a blocking threshold), resting on offset sd of only 0.017–0.024 within the 40–92 shallow training rows — which quantifies, and confirms, the arm's own declared "rank-4 power starvation" death. One note: m̄ is the global training mean, so the interaction has a nonzero shallow-tier mean; the tier main in the null absorbs exactly that component, which is the correct accounting. Subject to K2 (does this design carry a global intercept?), no defect.

**A02 == pace_gap: NOT a null-vs-null tautology.** "Already-adjudicated" is a statement about cutoff adjudication of the feature, not about the incumbent's model content. Measured structurally: the offset is cluster-constant (within-cluster range 0.0) and the gap exactly antisymmetric (within-cluster sum 0.0), so the treatment column is by construction orthogonal to everything the incumbent predicts — it is precisely the half of the prior information the incumbent's (own+opp)/2 average discards (the producer's docstring says so in words). K0[A02] = the incumbent; the arm tests genuinely new information; corr, R2 and condition numbers re-measured clean in all five folds. **A15 interaction-only accounting: SEPARABLE, and more strongly than the draft claims.** gap·asym is cluster-symmetric while gap is cluster-antisymmetric, so A02's term and A15's term are *structurally* orthogonal (measured corr ≤ 2.7e−18 every fold), and A15's treatment has R2 ≤ 0.039 on its own full null. Neither arm can claim or leak the other's credit even numerically. No double counting is possible.

**D1 resolution (incumbent switches, never blends): both retained readings get fair distinct nulls — SUBJECT TO K1.** The receipt bytes (2762/183/37/8) verify the switch; the corrected glosses are right; A12's no-carryover null (which owns every depth-indexed level df but no dev_prev in any form — S6 both directions) is clean and nested, and A12/A13's fixed-sequence null-stacking (A13's K0 = A12's full arm design + cont main) is coherent. A11's null, however, is currently three inconsistent descriptions (K1); until it is pinned, "fair distinct nulls for both readings" is true of A12 and undecidable-from-bytes for A11.

**Enumeration elements and shared K0s.** A09 (kappa grid): the null `[offset | d_t]` IS the kappa=0 member with β free, shared by all three elements — fair; note the per-element comparisons are parameter-fixed and non-nested (arm at kappa=10 cannot reproduce kappa=0), which biases delta_MAE *against* the arm when the null is true: conservative, acceptable, and worth one clarifying sentence at P35 since A09's formula omits the flat term that its own treatment_terms gloss ("minus the flat term") presupposes — for A09, unlike A11, both readings give the identical null, so this is C-level drafting, not a defect. A10 (lambda grid): null lambda-free and shared — fair. A11 (rho grid): shared null subject to K1. A08 (K grid): shared null only if K4 is closed. A06 (2 conditional elements): shared `[offset]` null — fair. A23: per-bundle nulls, K8. Every element I checked is charged to its declared family budget; I found no uncharged element and no element borrowing a null that grants its treatment an information advantage.

**The self-frozen response family (quasi-Poisson IRLS), through the K0-parity lens only:** the freeze binds family, link, offset and convergence tolerance *identically on arm and null*, the fit is deterministic, and the gate metric (MAE, paired cluster resamples, shared seed streams) is family-agnostic — so the choice, receipted or not, cannot asymmetrically favor any treatment over its null. The one parity-relevant residue is the unhandled pairwise non-convergence case, folded into K7. I raise no K0-parity objection to the freeze itself; its legitimacy as an unreceipted convention is another reviewer's dimension.

## 5. What I could NOT establish

* Whether A11's intended null is reading (1) or (2) of K1 — the bytes genuinely conflict; I did not resolve it.
* Whether any calibration design is intended to carry a global intercept (K2) — undefined in every frozen document I read; `p33_measurements.py` itself was reproduced only as logic embedded in the SPEC, and it fits nothing, so it cannot answer this either.
* The A04/A09 and A08-side d_t questions empirically: d_t construction is P36 scope by design; my K4 finding is about the *definition*, which is checkable now, not the numbers, which are not.
* Whether the P26 validator is intended to run at P35/P36 at all (K3): no frozen document names its call site; GATE_INVOCATION_CONTRACT.md does not mention it (measured: zero grep matches for `P26|validate_k0|K0_MATCHED` in that file).

## 6. Contradictions found (document vs document / document vs bytes)

1. A11 `formula` + P26 contract vs A11 `k0_matched.null` gloss vs A11 `kill_conditions` — K1 (within one frozen artifact).
2. P33 calibration `tested_parameters` (slope role, null 0; or no slope role) vs frozen P26 R8 (slope role, null exactly 1.0, mandatory) — K3.
3. "incumbent structural terms" (P33 A07/A12/A14) vs `possession_features.py` incumbent-has-no-fitted-feature bytes — K5.
4. P33's A03/A07 and A07-vs-depth measurements vs the record's own feature definitions as readable: reproducible only under the contract-schedule n_i clock, which no frozen sentence states — K6.

## 7. Required changes (summary)

1. **K1 (A)**: pin A11's null to one construction, strike the contradicting gloss, replace the never-fireable rho-interval kill with a decidable per-element criterion — or withdraw A11. (Stop-condition-adjacent: raised, not resolved.)
2. **K2 (B)**: preregister the intercept structure per arm, identically in arm and null; prohibit implementation-default intercepts. (Stop-condition-adjacent: raised, not resolved.)
3. **K3 (B)**: make the P26 K0 contract enforceable on the P35 task cards (schema + slope-parameterization equivalence + calibration-kind scope), or supersede it on the record and name the replacement enforcement.
4. **K4 (B)**: pin d_t's league-mean window across A08's K grid (shared-null vs per-element-null).
5. **K5–K8 (C)**: relabel "incumbent structural terms"; pin the contract-schedule n_i clock in a frozen sentence; clarify A09's formula to match its treatment_terms; declare a symmetric degenerate-draw/non-convergence rule; note A23's per-bundle evaluable sets.

No Severity A finding of *treatment-side* information advantage was found in any of the 26 arms: every treatment I could check is either nested above its null with complete lower-order structure, or a contract-sanctioned parameter-fixed comparison against a null sharing all machinery. The two A-class hazards found (K1's two-mains reading; K2's default-intercept channel) are both *ambiguities that would create* an asymmetry if resolved wrong at P36 — which is exactly what a preregistration exists to make impossible, and why they must be closed before the P35 freeze.
