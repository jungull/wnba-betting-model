# Does the +1.73% replicate?

**Its sign does; its size does not; and the operational rule attached to it is wrong.** On the one
clean window the partition allows, the published decision-stratum minutes gain reproduces to the
last digit and then **survives a genuine frozen intercept, growing from +1.69% to +1.774%
(ΔMAE +0.0796, p 0.0030, n 1,051)** — so unlike cold-start tiering and fallback routing, component
C is not a recalibration artefact. **But it is 0.55× its own injection-verified power floor
(0.0796 against 0.1435), empirical power at the observed effect size is 0.482, and of the two
disjoint folds only 2024 rejects on its own (+2.47%, p 0.00085); 2023 returns +1.29% at p 0.145.**

**The frozen-intercept number is +0.0796 minutes MAE = +1.774%.** It sits beside the published
shared-intercept +0.0776 = +1.729%, which this screen reproduced at |Δ| = 0.000e+00.

**Decision-stratum n = 1,051 rows in 264 team-game blocks** (2023: 613 in 151; 2024: 438 in 113) —
42.5% of the 2,475 rows C treats, out of a common scored row set of 9,022.

---

## 0. The decision-stratum intersection, before any effect size

Standing programme requirement, and it leads this document.

| scope | rows | team-games | decision stratum | C-treated | **C-treated ∩ decision** | blocks |
|---|---:|---:|---:|---:|---:|---:|
| pooled window 2023–2024 | 9,022 | 960 | 3,158 (35.0%) | 2,475 | **1,051** | 264 |
| fold 2023 | 4,520 | 480 | 1,591 | 1,452 | **613** | 151 |
| fold 2024 | 4,502 | 480 | 1,567 | 1,023 | **438** | 113 |

Every number below lives on the **C-treated ∩ decision** column unless it says otherwise. Every
cell is an **ORACLE-ON-ABSENCE CEILING** — the absence is realised, not forecast, because both
pre-game injury sources are UNVERIFIABLE. **Nothing here is an achievable live increment.**

---

## 1. The headline, both intercept regimes, all three windows

`PRIMARY_CELLS.csv`, `HEADLINE_WITH_FLOORS.csv`. Minutes. Paired sign-flip blocked at team-game,
20,000 draws.

| window | arm | n | blocks | ΔMAE | % | p | analytic floor | **injection floor** | effect / injection floor |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pooled | C, shared intercept | 1,051 | 264 | +0.0760 | +1.694% | 0.0063 | 0.0796 | 0.1494 | 0.51 |
| **pooled** | **C, FROZEN intercept** | **1,051** | **264** | **+0.0796** | **+1.774%** | **0.0030** | 0.0765 | **0.1435** | **0.55** |
| pooled | ABC, shared *(the published +1.73%)* | 1,051 | 264 | +0.0776 | +1.729% | 0.0044 | 0.0779 | 0.1461 | 0.53 |
| split 2023 | C, FROZEN | 613 | 151 | +0.0590 | +1.295% | **0.145** | 0.1122 | 0.2105 | 0.28 |
| split 2024 | C, FROZEN | 438 | 113 | +0.1084 | +2.470% | 0.00085 | 0.0916 | 0.1718 | 0.63 |

**Not one cell clears the injection-verified floor.** Under the analytic rule alone, three of them
would read decided. Under this screen's own measured floor, none do.

---

## 2. The frozen intercept, and why E1_I0039's freeze was not one

E1_I0039's `intercept_frozen_attribution.csv` set the arm equal to the base **off** the treated
rows and to the full shared-intercept arm **on** them. That removes off-row movement, but on the
treated rows themselves — which is exactly where the headline is measured — the number is still the
unfrozen one.

This screen's frozen arm holds the base's walk-forward intercept `b(S)` and lets the candidate
contribute **only its slopes**, fitted with **no intercept term** on the residual about that frozen
base. Three construction guards, all exact:

* **G1** frozen base == shared intercept-only base, max |Δ| = **0.000e+00**
* **G2** frozen arm == base on every untreated row, max |Δ| = **0.000e+00**
* **G4** ungated frozen arm == base wherever `u == 0`, max |Δ| = **0.000e+00**

and the comparison is not vacuous — the **shared** arm moves untreated rows by up to **0.4228
minutes** (0.2090 points). That movement is the recalibration channel.

**Result: C does not collapse. It grows.** `RECALIBRATION_SHARE.csv`: on the commercial cell the
shared intercept is worth **−0.0036**, i.e. **−4.7%** — the global recalibration was working
*against* C, not for it. This is the opposite of A and B, whose decision-stratum effect E1_I0039
showed going to exactly zero when frozen.

---

## 3. The kill: E1_I0039's "below the threshold the treatment is actively harmful" is 100% recalibration

E1_I0039 §4 reports, and the brief for this screen repeats as claim 3, that below the threshold the
minutes treatment is **actively harmful, −0.0230 at p 0.0003**. This screen reproduced that number
at **|Δ| = 0.000e+00** and then froze the intercept.

| stratum | rows | shared intercept | **frozen intercept** |
|---|---:|---:|---:|
| `freed = 0` | 3,300 | −0.0046 (p 0.40) | **exactly 0.0000** |
| `0 < freed < 25` | 3,189 | **−0.0230 (p 0.00005)** | **exactly 0.0000** |
| `freed = 0`, points | 3,300 | +0.0187 (p 0.00005) | **exactly 0.0000** |
| `0 < freed < 25`, points | 3,189 | +0.0224 (p 0.00005) | **exactly 0.0000** |

The published C arm gates its own regressors at `freed ≥ 25`, so on every one of those 6,489 rows
`u` is **identically zero** and the arm can differ from the base only through the shared intercept.
**The below-threshold harm is not a treatment effect. It is the vacuous-control trap E1_I0034
documented, firing on a number E1_I0039 promoted to a headline.** The preregistration predicted
exactly 0.0000 before the number existed.

---

## 4. A worse instance of the same trap, and it clears its floor

On the **1,051 commercial rows, cold-start tiering and fallback routing substitute ZERO rows** —
E1_I0039's own row overlap says so and this screen confirms it. Yet swapping them in is worth

**+0.0287 minutes MAE, p 0.00005, against an analytic floor of 0.0175 and a carried floor of
0.0213 — ABOVE BOTH.**

That is **36% of C's entire frozen effect, generated on rows the arm does not touch, purely by
moving the shared walk-forward intercept.** A reader applying the programme's own floor rule to
that cell would call it decided. **Every shared-intercept lattice in this programme is exposed to
this, and the exposure is large enough to manufacture a decided result out of nothing.**

---

## 5. Claim 1 — the threshold. The mechanism is real; the forecasting rule is not

**The mechanism reproduces exactly.** All **20** published figures of E1_I0034's accounting table
come back on the clean window: remaining players' trailing-5 sums of **198.96 / 201.08 / 201.50 /
191.44 / 184.02**, realised gains **−3.24 / −2.59 / −3.01 / +6.36 / +15.47**, call-up minutes
**4.14 / 2.48 / 2.33 / 3.30 / 1.92**, team-game counts **261 / 220 / 171 / 124 / 112**. Slack really
does open at about 30 minutes of absence.

**The forecasting threshold does not exist.** `THRESHOLD.csv`, ungated frozen arm, decision stratum:

* ΔMAE on rows with `freed ≥ τ` is **positive at every τ from 0 to 60**. It never changes sign.
* The preregistered crossing estimator returns **τ̂ = 0.0 minutes**. Block bootstrap over 764
  team-games, 2,000 replicates: **every replicate that crossed at all returned 0.0**; **471 of
  2,000 (23.6%) found no crossing anywhere on the grid.** There is no location to estimate — what
  varies with freed minutes is the effect's **magnitude**, not its **sign**.
* ΔMAE on rows *below* τ is **positive at every τ too** (+0.0088 at τ = 25, +0.0081 at τ = 30).

**And the gate costs money.** `GATE_SWEEP.csv` — one fixed row set (n = 2,321, 559 blocks), D101
clean, only the arm's gate varies:

| gate τ | 0 | 10 | 20 | **25 (published)** | **30 (D116's rule)** | 40 | 50 |
|---|---:|---:|---:|---:|---:|---:|---:|
| ΔMAE | **+0.0414** | +0.0345 | +0.0357 | +0.0360 | +0.0363 | +0.0220 | +0.0185 |

**The ungated arm is the best of eleven gates.** "Under ~30 minutes of absence, do nothing" — the
part E1_I0034 called "the operationally useful fact" and "the part of the result with the largest
effect size" — is not merely unsupported. On this window it **throws away 13% of the gain.**

**Reported as a measured quantity, as required: the threshold is 0.0 minutes freed, 90% interval
[0.0, 0.0] among crossing replicates, with 23.6% of replicates showing no crossing at all. "~30
minutes" is an artefact of a five-bin stratification of a monotone magnitude.**

---

## 6. Claim 2 — allocate evenly. Upheld, and more strongly than published

`ALLOCATION.csv`. Identical rows (1,051 / 264 blocks), identical response, identical base, frozen
intercept; only the shape of the allocation changes.

| allocation | ΔMAE | % | p | null sd | analytic floor |
|---|---:|---:|---:|---:|---:|
| **EVEN** `u = freed / n_rem` | **+0.1220** | +2.72% | 0.0155 | 0.0504 | 0.1412 |
| TILTED `u + u·z` *(published)* | +0.0796 | +1.77% | 0.0030 | 0.0273 | 0.0765 |
| PROPORTIONAL to `base5` | +0.0882 | +1.97% | 0.0560 | 0.0465 | 0.1301 |
| PROPORTIONAL + tilt | +0.0446 | +0.99% | 0.1109 | 0.0281 | 0.0786 |

**Nothing beats EVEN by more than EVEN's own floor: claim 2 is upheld.** And the published
specification's tilt term is a **drag** — dropping `u·z` raises the effect by **+0.0424**, 53% of
the headline.

**The counterweight, in the same section.** EVEN's larger effect comes with a null sd of 0.0504
against TILTED's 0.0273, so EVEN does **not** clear its own analytic floor while TILTED does. The
honest reading is that even allocation is not beaten, **not** that it is demonstrated superior.

---

## 7. Claim 3 — minutes yes, points no. Holds, and hardens

D101: each response is compared only to its own base; the minutes and points numbers are never
compared to each other.

| points cell, frozen intercept | n | ΔMAE | % | p |
|---|---:|---:|---:|---:|
| commercial cell, pooled | 1,051 | **−0.0187** | −0.372% | 0.214 |
| commercial cell, 2023 | 613 | −0.0157 | −0.315% | 0.440 |
| commercial cell, 2024 | 438 | −0.0230 | −0.449% | 0.310 |
| all C-treated rows | 2,475 | **−0.0588** | −1.42% | — |

**Every points cell that carries a treatment is negative, and freezing the intercept makes them
more negative.** E1_I0039's apparently positive pooled points figure for C (+0.0012) is entirely
vacuous: frozen, it is **−0.0161**. The stage boundary is the most robust thing in this screen.
**Redistribution must not be applied to the points stage.**

---

## 8. Order and specification — C alone IS sensitive, contrary to expectation

The brief predicted C alone should be insensitive to order. It is not.

| variant | ΔMAE | % of headline |
|---|---:|---:|
| C on the raw champion | +0.0796 | 100% |
| C on the A/B-substituted forecast | +0.0507 | 64% |

**Order spread 0.0289 = 36.3% of the effect** — larger than the 19–22% E1_I0039 measured for the
whole stack. And the frame matters too: rebuilt on E1_I0034's own remaining-player frame the same
cell gives **+0.0482 (61% of the headline)**.

`SPEC_LATTICE.csv` — fifteen variants across allocation, order, frame, intercept regime and window.
**Spread 0.0774 against a headline of 0.0796 = 97% of the headline.** By the preregistered rule
(spread > headline ⇒ specification-dependent) it scrapes through by two thousandths of a minute,
which is not a distinction worth defending. **The one thing that is robust: all fifteen variants
have the same sign.**

---

## 9. Power, nulls and controls

* **Null**: paired sign-flip blocked at **team-game**, matching the level the redistribution term
  varies at (D115). 20,000 draws. Saved in `nulls/`.
* **The `null_mean` diagnostic is structurally vacuous here and is not quoted as clearing
  anything.** The draws are ± fixed block sums, so `E[draws] = 0` exactly.
* **Six-block hard floor**: minimum `n_blocks` across all **180** primary cells is **113**; the
  smallest cell anywhere in the screen is a threshold bucket at **11 blocks** (`freed` 45–50).
  **Every cell in the screen passes the six-block floor**, and `n_blocks` together with
  `p_min = 2^(1−nb)` is reported for every one of them.
* **`t_crit` vs `√nb`, computed before any correction**: Bonferroni over 180 cells gives
  α = 2.778e-04; the attainable `p_min = 2^(1−nb)` is below it everywhere and the sign-flip
  resolution 1/(N+1) = 5.0e-05 is below it too, so a correction is arithmetically achievable and
  makes no cell undetectable. **It is not applied to the headline** (which is the single
  preregistered primary cell) — and the arithmetic is published because **at Bonferroni the
  commercial cell's p of 0.0030 would not clear.**
* **Type-I**: **0.0575** over 400 synthetic no-effect datasets against a target of 0.05.
* **Injection is component-wise**, planted through the candidate's own functional form
  (`y = y_null + κ·u`) into a **true null response** and recovered through the identical path.
  Not shuffled residuals (E1_I0034 measured that attenuating). Not constant loss subtraction
  (E1_I0039 DEF-3).
* **The floor this screen measured**: MDE80 = **0.1435**, which is **1.88× the analytic rule** —
  independently confirming D113's suspicion and **exceeding D116's carried 1.22×**. Empirical
  power at the observed effect size: **0.482**.
* **No-op placebo**: ΔMAE **exactly 0.000e+00**, one distinct draw value, transform asserted
  elementwise to be the identity.
* **Random-target control**: the treatment reassigned to random team-games, 30 replicates —
  real/|random| ratio **14.77**, and **0 of 30** random draws reach the real effect.
* **43 anchors reproduced from prior screens before any new statistic**, **40 at exactly
  0.000e+00** and three at machine precision (5.1e-16, 7.6e-16, 5.6e-16), **zero mismatches**.
  Two of them caught real errors in my own first drafts (DEFECTS DEF-2, DEF-3).

---

## 10. The results that most weaken this document's own conclusion

**(a) The single most important number here is that the effect is 0.55× its floor at 48% power.**
Everything positive said above — survives the freeze, same sign on both folds, same sign across
fifteen specifications — is said about an effect the instrument cannot reliably detect. A result at
48% power that keeps its sign twice is not strong evidence; it is what a real-but-small effect and
a moderate-sized artefact look like alike.

**(b) The split is not a replication and I will not dress it up as one.** 2024's overlay trains on
2023. The folds are disjoint in evaluation, nested in fitting. And the weaker fold (2023, p 0.145)
is precisely the one whose overlay trains on the single season whose champion came from the
degenerate 2021 fold. **The programme has one window. It does not have a replication.**

**(c) My own two instruments were broken first, and I found it, but only because Type-I read
1.0000.** DEF-4 planted the injection on top of the real response, so κ = 0 returned power 0.700
and would have produced a floor of 0.116 — comfortably *below* the observed effect, i.e. it would
have licensed the opposite verdict. DEF-5 synthesised a response only on the scored seasons and let
the walk-forward learn a real slope, giving a rejection rate of 1.0000. **Had the second defect not
been loud, the first would have passed silently and this document would have read DECIDED.**

**(d) I killed a published claim using a construction I introduced.** The frozen intercept is not
what E1_I0034 or E1_I0039 ran. It is defensible — G1/G2/G4 are exact — but §3's kill and §4's
finding both depend on my choosing a stricter definition of "freeze" than the prior screens used.
A reader who prefers the shared-intercept construction gets E1_I0039's numbers back exactly, and
this screen reproduced them to prove it.

**(e) The strongest single result in this screen argues against the programme's own prescription,
not for it.** The best-performing arm in the whole lattice is the one that ignores the threshold
entirely (ungated, even allocation) — and neither of those two facts was preregistered as the
headline.

---

## 11. Verdict, in the preregistered grammar

| claim | verdict |
|---|---|
| clean windows | **EXACTLY ONE**, and no second was manufactured |
| the +1.73%, pooled | **PARTIALLY REPLICATED** — reproduces exactly, survives the freeze at +1.77%, **NOT ESTABLISHED** (0.55× floor, power 0.482) |
| the +1.73%, on the split | **PARTIALLY REPLICATED** — same sign both folds, only 2024 rejects |
| claim 1, threshold mechanism | **REPLICATED**, 20/20 figures exact |
| claim 1, threshold as a forecasting rule | **KILLED** — no crossing exists; the ungated arm beats all eleven gates |
| claim 1, "below the threshold it is harmful" | **KILLED** — exactly 0.0000 when frozen; 100% recalibration |
| claim 2, allocate evenly | **UPHELD**, not beaten; the published tilt term is a drag |
| claim 3, minutes yes / points no | **UPHELD AND HARDENED** |
| order-insensitivity of C alone | **FALSIFIED** — 36.3% spread |

## 12. What this does not say

Nothing here has touched 2025 or 2026; both sealed fold receipts were listed and skipped by name.
Nothing has been tested against a market. Every cell is an oracle-on-absence ceiling that assumes
you know pre-game who is sitting, which **no verifiable source in this repo can supply** — so the
live value of this term is bounded above by a number that is itself not established.
**No production change is proposed and none is enacted. Component C remains unauthorised.**
