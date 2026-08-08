# Do the three improvements stack?

**Mostly no, and the reason is arithmetic rather than statistical.** Two of the three —
cold-start tiering and fallback routing — target **the same rows**: the cold-start set is a
**strict subset** of the fallback set (632 of 945), so combining them adds nothing and in fact
does slightly worse than using the better one alone. The third — minutes redistribution — shares
**48 and 63 rows** with them out of 9,022, which is near-empty by construction, so it simply adds
on top: the pair gains recover **98.1% and 98.4%** of the sum of their parts.

**The honest total, both numbers side by side, on one common row set of 9,022 player-games:**
all three together cut pooled minutes error by **+0.3817 MAE (+7.28%)** and pooled points error by
**+0.2089 MAE (+4.87%)** — but on the **decision stratum** (n = 3,158, the players you would
actually bet on) the same stack is worth **+0.0218 MAE on minutes (+0.50%, p 0.027)** and
**+0.0007 MAE on points (+0.013%, p 0.90 — nothing)**. That is a **17.5×** shrinkage on minutes
and a **367×** shrinkage on points on crossing into the betting population.

**And neither decision-stratum number clears its power floor.** Every one of the 20 decision-stratum
cells in this lattice returns **NOT ESTABLISHED**. The stack's minutes gain there is 0.0218 against
an injection-verified floor of 0.0340. **We cannot tell it from zero.**

---

## 1. The row overlap, which was run first and settled most of the question

`ROW_OVERLAP.csv`. Universe **U** = 9,022 scored, regular-season, appeared champion player-games,
2023–2024, across 960 team-games. Decision stratum = 3,158 (≥8 prior appearances **and** ≥24
trailing-5 minutes).

| set | n | % of U | in the decision stratum |
|---|---:|---:|---:|
| **A** cold-start tiering (`fallback_level == 2`) | 632 | 7.01% | **0** |
| **B** fallback routing (`is_fallback`) | 945 | 10.47% | **0** |
| **C** minutes redistribution (≥25 min freed) | 2,533 | 28.08% | **1,051** |
| **A ∩ B** | **632** | 7.01% | 0 |
| **A ∩ C** | **48** | 0.53% | 0 |
| **B ∩ C** | **63** | 0.70% | 0 |
| A ∩ B ∩ C | 48 | 0.53% | 0 |

Three things follow, and they are different from one another.

**A is a strict subset of B.** `A \ B` is empty. `B \ A` is 313 rows, all of them
`fallback_level == 3`. These are not two independent improvements; they are **two different
replacements proposed for overlapping rows**, so their composition was a *redundancy* question and
had to be measured empirically. It was, and the answer is below.

**A and C, and B and C, are near-disjoint — by construction, not by luck.** E1_I0034's remaining-
player set requires **at least 3 strictly-prior same-season appearances**; the champion's fallback
flag fires **below 3**. The two conditions are almost complementary as a matter of definition. For
these pairs the stacking question really is arithmetic, and the empirical work below is a *check on
that arithmetic* rather than a search for an interaction. The check passes.

**Zero cold-start rows and zero fallback rows are in the decision stratum.** Median prior
appearances is 2 for A and 1 for B; the stratum requires 8. This independently reproduces D109's
central sentence on a different window and with a differently-built row set.

---

## 2. The lattice

`STACK_LATTICE.csv`. One row set, one base (champion + walk-forward intercept, **intercept held in
both arms**), one SST per (response, stratum), paired sign-flip blocked at team-game, 20,000 draws.
**Minutes and points are never compared to each other** (D101). Every cell containing C is an
**ORACLE-ON-ABSENCE ceiling** — the absence indicator is realised, because both pre-game injury
sources are UNVERIFIABLE and may back no number.

### MINUTES — base MAE 5.2432 pooled, 4.3435 on the decision stratum

| arm | pooled ΔMAE | pooled % | decision ΔMAE | decision % | decision p |
|---|---:|---:|---:|---:|---:|
| A | +0.3541 | +6.75% | +0.0063 | +0.15% | 0.024 |
| **B** | **+0.3828** | **+7.30%** | +0.0103 | +0.24% | 0.028 |
| C | +0.0231 | +0.44% | +0.0150 | +0.35% | 0.218 |
| AB | +0.3660 | +6.98% | +0.0085 | +0.20% | 0.026 |
| AC | +0.3703 | +7.06% | +0.0197 | +0.45% | 0.061 |
| **BC** | **+0.3993** | **+7.62%** | **+0.0235** | **+0.54%** | 0.012 |
| ABC | +0.3817 | +7.28% | +0.0218 | +0.50% | 0.027 |

### POINTS — base MAE 4.2906 pooled, 5.0622 on the decision stratum

| arm | pooled ΔMAE | pooled % | decision ΔMAE | decision % | decision p |
|---|---:|---:|---:|---:|---:|
| A | +0.1589 | +3.70% | −0.0059 | −0.12% | 0.00005 |
| **B** | **+0.2140** | **+4.99%** | −0.0064 | −0.13% | 0.00005 |
| C | +0.0012 | +0.03% | +0.0080 | +0.16% | 0.152 |
| AB | +0.2106 | +4.91% | −0.0070 | −0.14% | 0.00005 |
| AC | +0.1572 | +3.66% | +0.0018 | +0.04% | 0.739 |
| BC | +0.2135 | +4.98% | +0.0015 | +0.03% | 0.787 |
| ABC | +0.2089 | +4.87% | +0.0007 | +0.01% | 0.901 |

**The whole stack does not beat its best single part on either pooled response.** ABC minutes
(+0.3817) is *below* B alone (+0.3828). ABC points (+0.2089) is *below* B alone (+0.2140).

---

## 3. Additive, sub-additive, or interfering — the answer is all three, depending on the pair

`additivity.csv`, sum-of-parts over the whole, pooled minutes:

| pair | sum of parts | whole | ratio | reading |
|---|---:|---:|---:|---|
| **A + B** | 0.7369 | 0.3660 | **2.013** | **massively sub-additive — and AB is worse than B alone** |
| A + C | 0.3772 | 0.3703 | 1.019 | **additive to within 1.9%** |
| B + C | 0.4059 | 0.3993 | 1.016 | **additive to within 1.6%** |
| A + B + C | 0.7600 | 0.3817 | 1.991 | dominated entirely by the A/B redundancy |

The pattern is exactly what the row overlap predicted. **Where the row sets overlap, the gains do
not add. Where they do not overlap, the gains add almost perfectly.** No pair interferes — no
combination is below either of its parts — but A+B is redundant to the point of costing 0.0168
minutes MAE against simply dropping A and keeping B.

---

## 4. The stage boundary held, and D116's threshold reproduced

D116 was explicit that redistribution helps at the **minutes** stage and is **harmful** at the
**points** stage. That is exactly what happened, measured here on a different row set with
different machinery (`negative_and_threshold_strata.csv`, `vacuous_split.csv`):

| C, on its own treated rows | minutes | points |
|---|---:|---:|
| freed = 0 (nothing to redistribute) | −0.0046, p 0.398 — **null, as required** | +0.0187, p 0.0003 — **see §6** |
| 0 < freed < 25 (below D116's threshold) | **−0.0230, p 0.0003 — HARMFUL** | +0.0224, p 0.0003 |
| freed ≥ 25 | **+0.1171, +2.22%** | **−0.0482, −1.15%, p 0.0025** |
| freed ≥ 30 | **+0.1443, +2.69%** | −0.0466, −1.11%, p 0.010 |

**D116's ~30-minute threshold reproduces independently.** Below the threshold the treatment is
*measurably harmful* on minutes; above it the gain grows as the threshold rises. And the points
harm reproduces at **−1.15%** against D116's published **−1.17%**, on a row set built from a
different frame.

**A naive stack that pushed C through to points would have destroyed value, and this lattice shows
by how much.** On C's own treated rows the points response is −1.27%.

---

## 5. The decision-stratum total — the number that actually matters

On the 1,051 decision-stratum rows that C actually treats (`C_on_own_rows.csv`):

| arm | response | n | ΔMAE | % | p | analytic floor |
|---|---|---:|---:|---:|---:|---:|
| C | minutes | 1,051 | +0.0760 | **+1.69%** | 0.008 | 0.0798 |
| **ABC** | **minutes** | **1,051** | **+0.0776** | **+1.73%** | **0.006** | **0.0781** |
| C | points | 1,051 | −0.0131 | −0.26% | 0.395 | 0.0434 |
| ABC | points | 1,051 | −0.0163 | −0.32% | 0.298 | 0.0443 |

**ABC beats C by +0.0016 MAE on those rows. That is what A and B are worth to the betting
population: 2% of C's effect, on a population where they treat literally zero rows.**

Spread over the whole decision stratum (n = 3,158), with the shared recalibration frozen out
(`intercept_frozen_attribution.csv`), the stack is **+0.0258 minutes MAE (+0.59%)** and
**−0.0054 points MAE (−0.11%)**.

**All of it is C. None of it is established.**

---

## 6. The result that most weakens this conclusion, in the same document as the conclusion

Four of them.

**(a) Every component moves rows it does not touch, and on the decision stratum that is the whole
of A's and B's apparent effect.** All arms share a walk-forward intercept refit, so changing what
the model emits on 632 cold-start rows shifts the global calibration and therefore every other
row's forecast. Freeze the base's intercept and re-measure on rows each component actually treats
(`recalibration_share.csv`): **A and B on the decision stratum go to EXACTLY ZERO** — their
+0.0063 / +0.0103 minutes gains and their −0.0059 / −0.0064 points losses there are **100%
recalibration**. Likewise C's *points* number: +0.0187 on `freed = 0` rows, where C's term is
identically zero, is the vacuous-control trap firing, and once frozen C's decision-stratum points
effect is **−0.0044**, not +0.0080. This is not a coding error — it is a real consequence of
composing components under a shared recalibration — but **it means the pooled numbers are not
attributable to the components' own rows**, and any reader who treats them that way is misreading
them.

**(b) The secondary window reverses C.** The declared W1 secondary cannot be run under the primary
training rule at all (with training starting in 2022, the 2022 season has no valid training
season). Forced through by training on 2021 — the fold the champion's own receipt declares
`degenerate: true` — sign agreement with the primary drops to **0.64 of 28 cells** and **C goes
to −12.56% on decision-stratum minutes**. The alternative window is known-bad, so this does not
overturn the primary reading; it does mean **the C result has never been checked against a second
clean window and the only available second window destroys it**.

**(c) The order in which C is applied moves the answer by as much as the entire decision-stratum
effect.** Applying C to the raw champion instead of to the A/B-substituted forecast changes ABC's
pooled MAE by 0.0048 on minutes and 0.0044 on points (`order_sensitivity.csv`) — negligible against
a 0.38 pooled gain, but **19–22% of the 0.0218 decision-stratum number**.

**(d) This screen did not succeed in deriving its own injection-verified power floor.** Three
constructions were tried and all three failed in disclosed ways (`DEFECTS.md` DEF-3, DEF-5,
DEF-6). Every verdict here therefore leans on **D116's carried anti-conservatism factors**
(minutes 1.22×, points 3.40×), which were measured on a different cell, and that is a **weaker
evidential position than preregistered**. Under the analytic floor alone, eight pooled points cells
would read DECIDED-POSITIVE instead of NOT ESTABLISHED, and four decision-stratum points cells
would read DECIDED-NEGATIVE. **The choice of floor changes twelve of forty verdicts.**

---

## 7. What passed

* **No-op placebo**: ΔMAE exactly 0.000e+00, one distinct draw value, both responses.
* **Random-target control**: reassigning each component's treatment to a same-size random row set
  gives real/random ratios of **18.0** (A minutes), **9.1** (B minutes), **12.2** (C minutes),
  **23.4** (A points), **10.2** (B points). The targeting is doing the work, not the machinery.
* **Negative stratum**: C on `freed = 0` minutes returns −0.0046 at p 0.398 — null, as required.
* **Absorption tell (D114)**: `|null_mean| > |observed|` on **zero of the 40 cells**. No null
  absorbed its effect.
* **Type-I**: 0.0275–0.0500 over 400 synthetic datasets per cell against a target of 0.05.
* **Seventeen anchors reproduced before any new statistic was generated**, sixteen at
  |Δ| = 0.000e+00, including D092's 1,061 fallback rows at skill −0.1863, D102's 947 routed rows,
  D109's zero-routed-rows-in-the-decision-stratum, D116's 2,475 rows, and — the strongest of them —
  **E1_I0034's published P04 minutes cell reproduced to 5.1e-16** (ΔMAE 0.09269264623364977 vs
  0.09269264623364926), which is what licenses this screen's C machinery.

---

## 8. What this does not say

Nothing here has touched 2025 or 2026. Nothing has been tested against a market. Every C cell is an
**oracle-on-absence ceiling** — it assumes you know pre-game who is sitting, which no verifiable
source in this repo can supply. **No production change is enacted and none is requested**; all
three components remain unauthorised.

And the pooled headline — "the stack cuts minutes error by 7.3%" — should never be quoted on its
own. It is carried by 945 rows where the champion emits a constant, the same rows D076's abstention
rule says a forecaster should decline to forecast at all, and it is worth **0.50%, not
established**, on the players anyone would bet on.
