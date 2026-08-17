# Is the allocation of a team's scoring across its roster forecastable at all?

**E1_I0046_allocation.** `PREREG.md` sha256
`b6dd2e6b141295b8accd92c9fb8920ef5d05a9901f35bf74410fb9c1ba331322`, 21,729 bytes, every cell fixed
before anything was measured. **0 dropped. 3 added after the hash**, all listed in `NOTES.md` with
their direction; **two of the three weaken the headline** and the third is a control.

Regular season, **2023–2024 (the one clean window)**, walk-forward, strictly prior-only, **3,167
decision-stratum player-games** in 764 team-games out of 16,717 appeared player-games in 1,776
team-games. 2021 and 2022 are training data; 2022 is reported as a disclosed contrast and is never a
headline. **2025 and 2026 were never opened.**

---

## THE DECISION-STRATUM RESULT, FROZEN AND UNFROZEN

**On the decision stratum in the clean window, the allocation of a team's points across its roster is
strongly forecastable — a tuned trailing-share allocator scores R² +0.3366 where an equal split
across the same roster scores −0.4110 — and of five preregistered candidates tested on top of that
allocator, exactly one moves the number: the player's own prior ATTEMPTS share, at ΔR²
+0.005487 UNFROZEN (p 0.0005, family-wise p 0.0005, 21.3 null sd) and −0.004696 FROZEN (p 1.0000,
−17.4 null sd).** Frozen it is the largest negative in the table and unfrozen the largest positive,
and the two together say something sharper than either alone: **the attempts channel does not ADD to
the trailing points share, it partly REPLACES it** — freezing the base weight is exactly what a
substitute cannot survive. **Everything else on points is null**: prior minutes share −0.000879
(p 0.9865), prior start rate +0.000304 (p 0.0420 but 0.42× its own power floor), the generalised
absence channel +0.000573 (p 0.0060) against its own 80 %-power floor of 0.000703, and an opponent
term at −0.000005 that is **arithmetically incapable** of moving an allocation at all.

---

## THE FIVE THINGS THAT MATTER, IN ORDER

### 1. Allocation is emphatically forecastable, and the simplest possible estimator does it

`Q1_ALLOCATION_FORECASTABLE.csv`, decision stratum, clean window, n = 3,167, 764 team-game blocks:

| response | tuned trailing-share allocator | naive trailing-5 | equal split 1/n | tuned − uniform | tuned − naive |
|---|---:|---:|---:|---:|---:|
| **points share** | **+0.3366** | +0.3211 | −0.4110 | **+0.7476** (z +20.1, p 0.0005) | **+0.0156** (z +4.49, p 0.0010) |
| minutes share | +0.2617 | +0.2233 | −1.5982 | +1.8599 (z +22.5) | +0.0384 (z +5.70, p 0.0005) |
| attempts share | +0.4892 | +0.4834 | −0.5605 | +1.0497 (z +22.2) | +0.0058 (z +2.54, p 0.0140) |

**Q1 is not in doubt. The answer nobody had asked for is yes, and by a wide margin.** A shrunken
EWMA of a player's own earlier shares (halflife 13, shrinkage k = 1, selected on strictly earlier
seasons) explains a third of the variation in who scores a team's points.

**And the tuning is not decoration.** Tuned beats naive by +0.0156 on points and +0.0384 on
minutes — **15× and 38× the single-cell detection floor.** Anything measured against the naive
allocator instead would have been measuring the halflife. On minutes the naive-versus-tuned gap is
larger than the entire family ceiling for every candidate combined.

### 2. THE COMPOSITIONAL CONSTRAINT IS THE LARGEST EFFECT IN THIS SCREEN

D111's rule — *allocations of a shared fixed budget do not survive being modelled separately* — is
usually quoted. Here it is measured twice, on the primary response, decision stratum, unfrozen:

| candidate | modelled **separately** (RAW) | forced to remain an **allocation** (PROJ) | |
|---|---:|---:|---|
| A1_min_share_prior | **+0.003989** | **−0.000879** | **sign flips** |
| A2_fga_share_prior | +0.008518 | +0.005487 | −36 % |
| A3_starter_rate_prior | **+0.002680** | +0.000304 | −89 % |
| A4_vac_x_own | **+0.000803** | **−0.000251** | **sign flips** |

**Three of the four candidates flip sign.** A screen that modelled these shares independently — the
default thing to do — would have reported **three survivors on the primary response.** Requiring the
forecast to be an actual allocation of the team's points leaves **one**. The same thing is visible
*before any fit* in `CEILING.md`: between **87 % and 98 %** of the arithmetic ceiling for the most
promising candidate on each response exists only if the forecast is permitted to break the budget.

**This is the single most transferable finding here and it is not about basketball.**

### 3. Any candidate that is constant within the team-game cannot forecast an allocation — arithmetically

Adding `g·x_g` to every member of a composition and renormalising divides through by the same shift.
`A5_opp_defrtg` was preregistered to demonstrate it, and does, at ΔR² **−0.000005** (p 0.9540 under
a date-blocked null) against a pure-noise control at −0.000069.

**Opponent, venue, pace, rest, travel and referee assignment are all team-game-constant.** The whole
family is disposed of without a fit. Whatever they do to a *level*, they cannot move a *share*.

The same cell also produced the cleanest control-that-cannot-fail this screen ran: the
within-team-game swap is the **literal identity** for a team-game-constant column, and it duly
returned a null sd of **8.5 × 10⁻²²**, and **exactly 0.0** in two of six cells.

### 4. SHARE IS NOT MORE STABLE THAN LEVEL — the mechanism the brief hoped for is not there

`STABILITY.csv`, identical rows, identical order, within player-season:

| population | channel | acf1 **share** | acf1 **level** | gap | ICC share | ICC level |
|---|---|---:|---:|---:|---:|---:|
| **DECISION, clean window** | **points** | **+0.3826** | **+0.3850** | **−0.0023** | 0.3933 | 0.3923 |
| DECISION, clean window | minutes | +0.3794 | +0.3707 | +0.0087 | 0.3371 | 0.3271 |
| DECISION, clean window | attempts | +0.5318 | +0.5272 | +0.0046 | 0.5265 | 0.5184 |
| DECISION, all seasons | points | +0.3629 | +0.3595 | +0.0034 | 0.3801 | 0.3778 |
| all appeared rows | points | +0.5742 | +0.5696 | +0.0046 | 0.5476 | 0.5456 |

**Conditioning on the team total buys between −0.002 and +0.012 of autocorrelation, and on the
primary response in the clean window it is negative.** Lags 2–5 and the within-player-centred
variants are in the CSV and say the same.

**And there is a mechanism for why, computed in the same file.** Dividing by the team total can only
remove the variance the team total contributes, and the team total barely varies:
`sd(log team points) = 0.1359` against `sd(log player points) = 0.6499`, so the total accounts for
**4.4 %** of the level's log-variance on points, **2.6 %** on attempts and **0.8 %** on minutes.
**There was never more than about 4 % available to strip out, and the measured gap is consistent
with that ceiling.** A player's share and a player's level are, for persistence purposes, the same
quantity.

*(This is the one cross-response comparison this screen makes, and it is made only on
autocorrelation and ICC — unitless quantities on identical rows in identical order. No ΔR², MAE or
variance share is ever set beside a differently-scaled one.)*

### 5. THE ONE SURVIVOR, AND WHY IT IS WEAKER THAN ITS p-VALUE

`R1_s_pts / A2_fga_share_prior / UNFROZEN / PROJ`, decision stratum, clean window, n = 3,167:

| | value |
|---|---:|
| ΔR² over the tuned points-share allocator | **+0.005487** |
| as a share of the base R² (0.33491) | 1.64 % |
| **translated:** rms movement of the forecast | 0.66 percentage points of the team total = **0.545 points per player-game** |
| against a points-level response sd of | 7.7415 points |
| N_TGSWAP null | mean −0.000065, sd 0.000261, **z +21.29, p 0.0005** (2,000 draws; p is at its floor) |
| N_PSWAP null (serial structure preserved) | mean −0.000069, sd 0.000238, **z +23.39, p 0.0017** (600 draws; p is at its floor) |
| family-wise, max-z over 4 real between-player candidates | **p 0.0005** |
| analytic 80 %-power floor `2.80 × null_sd` | 0.000731 → observed is **7.5×** it |
| **injection-verified 80 %-power floor** (recovered units) | **0.000926** → observed is **5.9×** it |
| non-circular type-I of the null | **0.040** at α = 0.05, sd(z) **0.927**, max z over 100 synthetic candidates **+3.07** |
| eval 2023 / eval 2024 / disclosed 2022 | **+0.005472 / +0.005503 / +0.008590** |

The mechanism is not mysterious and it is the one E1_I0033 predicted. **Points = attempts ×
efficiency, and efficiency is mostly noise; the attempts share is a cleaner measurement of the same
underlying role than the points share is.** E1_I0033 found attempts the most allocation-like of the
six quantities it measured (the largest bottom-up penalty, 49.6 %). This is the same fact seen from
the other side.

**And here is what most weakens it, stated in the same place.**

**(a) The block bootstrap disagrees with the permutation null by 8.07×, and under the bootstrap the
cell is NOT ESTABLISHED.** Resampling the 764 team-game blocks gives a sampling sd of **0.002106**
against the permutation null's **0.000261**. On the bootstrap the statistic is **t = 2.61** and the
80 %-power threshold is **0.005897**, which the observed **0.005487** does not clear. E1_I0034
measured this same ratio at **0.963–1.013**; here it is 8.07. The two answer different questions —
the permutation tests whether the assignment carries information, the bootstrap asks whether the
*number* would replicate — but the honest statement is that **one of the two preregistered variance
estimates does not decide this cell.** The direct evidence on replication is the season split above:
+0.005472, +0.005503, +0.008590 across three independent evaluation seasons, which is far tighter
than a sd of 0.0021 predicts.

**(b) The implementable version does NOT survive on the decision stratum.** The regression cell adds
a coefficient to a column. The thing you would actually build is an allocator. `SUBSTITUTE_TEST.csv`:

| contrast, decision stratum, clean window | R² | ΔR² | p | 80 % floor |
|---|---:|---:|---:|---:|
| attempts-share allocator **alone** vs points-share allocator | +0.33155 vs +0.33665 | **−0.005101** | 0.3168 | — |
| **50/50 blend** vs points-share allocator | +0.34130 vs +0.33665 | **+0.004647** | **0.0870** | 0.00743 |
| *(50/50 blend, pooled over all 9,056 appeared rows)* | *+0.52518 vs +0.51785* | *+0.007334* | *0.0005* | *0.00397* |

**On the rows that matter, the blend gains what the regression said it should and does not reach
significance, let alone its power floor.** It establishes only when pooled over rows that are not
bettable — which is the exact failure mode the decision stratum exists to catch, and it is why the
pooled row is in italics. **A2 is established as a signal and is NOT established as an allocator.**

**(c) The frozen arm is not a technicality.** −0.004696 frozen against +0.005487 unfrozen means the
gain is entirely in re-weighting, and the frozen sign **flips positive (+0.005224) in the disclosed
2022 window** while the unfrozen value stays stable. The channel is a substitute, and a substitute's
value depends on how much you were relying on what it substitutes for.

**(d) Both figures are oracle ceilings.** The response needs the realised team total and the
projection needs the realised roster (`DEFECTS.md` D-07). Neither is available before tip-off; the
programme's own availability forecast sums to 10.34 players where 9.40 play. **No number here is an
achievable live increment.**

---

## THE OTHER TWO RESPONSES, IN ONE PARAGRAPH EACH

**Minutes share.** The generalised absence channel `A4_vac_x_own` is the only thing that moves:
**+0.002640 frozen** (z +5.07 under N_TGSWAP, z +7.58 under N_PSWAP, both p at their floor), which
clears both its analytic floor (0.001686) and its bootstrap floor (0.001994). **But it collapses
unfrozen to +0.000175 (p 0.1664) and to +0.000578 in the disclosed 2022 window**, and its injection
curve is not resolved (`DEFECTS.md` D-06). Reported as **arm-dependent and window-unstable, not
established**. It is nonetheless the same sign and the same channel E1_I0034 found real for minutes
and harmful for points, and this screen reproduces both halves of that: A4 on **points** is +0.000573
against a 0.000703 floor — **not established** — and A4 on minutes is the largest frozen effect in
the screen.

**Attempts share.** Nothing. Every candidate p ≥ 0.1248 under N_PSWAP; the largest frozen value is
+0.000160 and the largest honest unfrozen value +0.000112. The single biggest number anywhere in
`PRIMARY_CELLS.csv` — `R3_s_fga / A2 / UNFROZEN = +0.013228` — is **excluded as same-channel**
(`DEFECTS.md` D-02): there the candidate *is* the base's own channel at a different halflife, so it
measures smoothing, not information.

---

## THE DEMONSTRATION THIS SCREEN RAN ON ITSELF RATHER THAN CITING

A within-player cyclic-shift null, applied to a between-player candidate, on this screen's own
primary cell (`BLIND_NULL_DEMO.csv`):

| candidate, `R1_s_pts` FROZEN | observed | null mean | p |
|---|---:|---:|---:|
| A1_min_share_prior, **correct** within-team-game null | −0.004252 | −0.000063 | **1.0000** |
| A1_min_share_prior, **blind** within-player null | −0.004252 | **−0.009759** | **0.0020** |
| A2_fga_share_prior, **correct** null | −0.004696 | −0.000071 | **1.0000** |
| A2_fga_share_prior, **blind** null | −0.004696 | **−0.013774** | **0.0020** |

**The blind null does not merely lose power. It manufactures a significant survivor out of a
candidate that is strongly HARMFUL**, because its own mean sits three times further negative than
the observed statistic. Two cells, both at p = 0.0020, both with the sign reversed. D108's ruling
and E1_I0036's correction, reproduced here directly rather than cited.

---

## WHAT FOLLOWS

1. **Model the allocation, not the players.** Requiring a forecast to be a genuine allocation of the
   team's total is not a refinement — it is what separates one survivor from three false ones. Any
   player-props stack that forecasts players independently and normalises afterwards, or not at all,
   is inheriting a ceiling roughly **7.6×** larger than the one it can actually reach.
2. **Stop looking at team-game-level features for props allocation.** Opponent, venue, pace and rest
   cannot move a share. They can move a total, which the team model already owns.
3. **The trailing share is the answer, and the tuning of it is worth more than any candidate.**
   Tuned-over-naive is +0.0156 on points; the best surviving candidate is +0.0055. **The
   hyperparameter is worth 2.8× the feature.**
4. **The attempts channel is the one place worth another look** — as a *blend* with the points
   channel, not as a replacement, and with the explicit knowledge that the blend does not reach
   significance on the decision stratum and that the whole result is an oracle ceiling.
5. **Do not build a share model hoping shares are more persistent than levels.** They are not, by
   about 0.3 percentage points of autocorrelation, and there was only ~4 % of variance available to
   remove in the first place.
6. **No production change is proposed and no champion model was fitted.**

---

## DISCIPLINE RECORD

* **20 anchors reproduced before any new statistic, 17 of them at exactly `0.000e+00`**, and the run
  halts if any fails (`ANCHORS.csv`): D104's home advantage **+0.965090 on 888 games** (exact);
  `E0_I0016` and `E1_I0018` screen frames at **14,852** and their merge at **14,852** (exact);
  E1_I0043's decision stratum at **5,673** rows / **149** players / **708** games and **3,167** rows
  in 2023–24 (all exact, and reproduced from `master_player` rather than from its frames); D085's
  `A10_opp_defrtg → y_ppm` ΔR² **recomputed** to `0.0014430974149689` against a published
  `0.0014430974149688` (|d| 6.9e-17) and over `refA` to |d| 7.6e-17; this screen's from-scratch
  `n_prior` matching `E1_I0018`'s on **all 14,852** shared rows with **zero** disagreements and
  `prior5_minutes` to 1.4e-14; and the composition closing against `master_team` on **all 1,776
  team-games with max |diff| exactly 0** for both points and attempts.
* **The response is asserted to lie on the simplex** — every share sums to 1 within its team-game to
  < 1e-12 — on the real data and on **every synthetic response at every θ in every replicate**.
* **The arithmetic ceiling was computed and gated before any fit.** It opened, on all three
  responses (5.88× / 22.47× / 5.21× the single-cell floor). That is the expensive outcome and it is
  recorded as such in `CEILING.md`.
* **Nulls matched to the level, and two of them.** `N_TGSWAP` (within-composition player swap, 1,776
  blocks) and `N_PSWAP` (whole player-season series reassigned inside the team-season, 48 blocks,
  634 series) — the second added after the hash precisely because the first destroys serial
  structure as well as assignment, which is the K6 hazard one level over. **Every verdict requires
  both.** Family-wise max-z is computed from the **same draw stream**, so cross-candidate correlation
  is preserved (D120).
* **Type-I verified non-circularly**: 100 synthetic candidates carrying a real player's whole series
  but belonging to a player on another team-season — realistic level and autocorrelation, zero true
  relation. Rejection **0.040 / 0.010 / 0.020** against a nominal 0.05, sd(z) **0.927 / 0.847 /
  0.852**. A too-narrow null would show sd(z) ≫ 1. It does not.
* **Injection is component-wise, planted into the REAL response in the model's own functional form,
  and the whole path is rerun.** Type-I at θ = 0: 0.000, 0.033, 0.033, 0.000, 0.000.
* **No-op placebo: deviation exactly `0.000e+00` on all 12 cells**, with the transform asserted to be
  the identity so the check is not vacuous.
* **Response placebo**: permuting the response inside the team-game gives mean ΔR² −0.001101 (max
  +0.002019) against an observed +0.005487.
* **Future-leakage probe fired on A2 (+0.8309 against the base's +0.8248) and is read as kit K1
  requires** — a screening flag, equally consistent with a better estimator of a persistent
  quantity. Both columns are `.shift(1)` constructions and cannot read the future; and A2 tracking a
  player's own future share *better than the base does* **is the claimed mechanism**, not evidence
  against it. `A5_opp_defrtg` and `G01_noise` sit at −0.008 and −0.010, as they must.
* **Ten defects self-reported** in `DEFECTS.md`, four of which would have changed a published number:
  a retrospective-baseline projection caught only because it produced an impossible ΔR² of 2.43; two
  same-channel cells that would have made the screen's largest number quotable; a first injection DGP
  that recovered **negative** effects from positive plants; and a ceiling page that implied one bound
  covered both arms.
* **Pooled numbers are reported second in every file.** The decision stratum is 18.94 % of the frame
  and 4.15 rows per team-game against a 9.41-player roster.
* **No production change is proposed and no champion model was fitted.**
