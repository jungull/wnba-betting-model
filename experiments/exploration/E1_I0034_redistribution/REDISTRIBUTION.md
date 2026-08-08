# Where the minutes go when a starter sits — and whether you can bet on it

**E1_I0034_redistribution.** Preregistration hash
`8963b3464f8b6b930940ddf42fe4cbe5f37776ee82bec0d1af79163bc0741b70`, 18,575 bytes, 14 cells fixed
before anything was measured. **0 dropped. 1 added after the hash** (a null audit, forced by a
coordinator correction; it made the headline *weaker*, and the direction is stated in §7).

Regular season, **2023–2024**, 8,118 remaining-player-games in 888 team-games, walk-forward,
strictly prior-only. 2021 and 2022 are training data only. **2025 and 2026 were never opened.**

---

## The short answer

E1_I0033 established that when a starter sits, the team scores the same number of points, and
suggested the interesting question was where those points go instead. **They mostly go nowhere,
because for most absences there is nothing to redistribute.**

Three things, in order of how much they matter:

1. **The redistribution is real but it has a threshold.** A team's remaining players' own recent
   minutes *already* account for the whole 200-minute budget until the absence gets large. Below
   about 30 minutes of absent playing time there is no slack and nothing moves. Above it, roughly
   9–16 minutes of genuine slack opens up and gets shared out.
2. **When it does happen, nobody can tell you who gets it.** Every pre-game predictor we tried —
   how big the player is, how big she is relative to her teammates, whether she plays the
   absentee's position — explains **at most 1.5%** of the within-team variation in who actually
   benefits. The allocation is **diffuse**.
3. **It reaches minutes, and it does not reach points.** Knowing the absence improves a minutes
   forecast. On the same rows, with the same machinery, it makes the **points** forecast **worse**.
   Points is the prop market.

---

## 1. The mechanism, which is the actual finding

Team-games grouped by how much playing time the absent established players represent
(`accounting_where_minutes_go.csv`, `baseline_sum_diagnostic.csv`, 888 team-games, 2023–2024):

| absent playing time | team-games | remaining players' own recent minutes sum to | slack against the 200-minute budget | what the remaining players actually gain | minutes played by call-ups |
|---|---:|---:|---:|---:|---:|
| none | 261 | 198.96 | **+1.0** | −3.24 | 4.14 |
| 0–15 min | 220 | 201.08 | **−1.1** | −2.59 | 2.48 |
| 15–30 min | 171 | 201.50 | **−1.5** | −3.01 | 2.33 |
| 30–45 min | 124 | 191.44 | **+8.6** | **+6.36** | 3.30 |
| 45+ min | 112 | 184.02 | **+16.0** | **+15.47** | 1.92 |

Read the third and fifth columns together. **Until the absence passes roughly 30 minutes, the
players who are left were already, on their own recent form, playing all 200 minutes between them.
There is no room.** Past that point the remaining roster genuinely cannot cover the game, real
slack appears, and the gain column tracks it almost one-for-one (+8.6 → +6.36, +16.0 → +15.47).

*(The gain and slack columns differ by the call-up minutes in the last column — `gain = slack −
call-up minutes`, up to overtime. The three columns are one identity, not three measurements.)*

This is why the naive estimator fails. "The absent player's 24 minutes go to her teammates" sounds
like arithmetic, but a team's trailing-form minutes do not sum to 200 — they sum to 199 when
everyone is healthy and to **250** when three rotation players are out, because a player's recent
average is computed over games she *played*, which are her higher-minute games. The freed volume is
an overstatement of what is available, and by the most in exactly the games the question is about.

**And it does not leak out of the roster.** P01 asked whether the freed volume goes to call-ups
with no established role. Slope on minutes **θ = −0.030** (p 0.082), attempts **−0.033** (p 0.057),
points **−0.039** (p 0.034). Full leakage, θ = 1, sits **59.6 null standard deviations away** and
the null is verified able to see it — planting θ = 1.0 recovers 0.970 at p = 0.001. Call-up minutes
are flat at 2–4 per game across every absence bucket. **The volume stays inside the established
rotation.**

---

## 2. Who benefits — and the answer is nobody predictably

Not measured from the after-the-fact spread of who gained, which is dominated by noise and would
read as "concentrated" even under a perfectly even split. Measured as **predictable** concentration:
how much of the within-team-game variation in who gained is explained by a pre-game predictor
(`concentration_predictable.csv`, rows where an absence is actually present).

| predictor | minutes | attempts | points |
|---|---:|---:|---:|
| the player's own recent level | −0.091 | −0.083 | −0.138 |
| her level relative to her teammates | −0.083 | −0.074 | −0.124 |
| that, interacted with the freed volume | **−0.122** | −0.061 | −0.088 |
| **position match with the absentee** | **+0.045** | +0.048 | +0.029 |
| *(the actual spread of the gain, sd)* | *6.11 min* | *3.20 att* | *5.44 pts* |

The best of these correlations is −0.122, which is **1.5% of the variation**. Against an actual
spread of ±6 minutes per player.

The preregistered test agrees. **P02**, the allocation tilt, with the mean-reversion main effect
already in the base:

| channel | tilt γ | p | 80%-power floor | verdict |
|---|---:|---:|---:|---|
| minutes | −0.0349 | 0.673 | 0.083 | **DIFFUSE — tilt not established** |
| attempts | +0.0577 | 0.069 | 0.131 | **DIFFUSE — tilt not established** |
| points | +0.0426 | 0.198 | 0.181 | **DIFFUSE — tilt not established** |

**P05**, position match, on top of that tilt: δ = +0.099, p = 0.044, 80%-power floor **0.153**.
Significant and *underpowered* — the exact pattern D103 exists to catch. Not established.

The sign is worth a sentence anyway, because it is the opposite of the intuition: the minutes tilt
is **negative**, i.e. the freed time drifts toward the *smaller* rotation players, not the stars.
Probe 3 showed most of that is mean reversion in a noisy trailing average (the same correlation is
−0.111 in team-games with no absence at all, against −0.186 with one), which is why the base
carries it and the incremental tilt does not survive.

---

## 3. Does knowing the absence improve a forecast? Minutes yes, points no

All cells below are an **ORACLE CEILING**: the absence indicator is realised, because both pre-game
injury sources in this repo return `manifest_present: false` from `check_manifest` and
UNVERIFIABLE is not a pass. Nothing here is an achievable live increment. Identical rows, identical
response, identical weighting on both sides of every comparison (D101).

**Against a tuned trailing-5 base (P03) and against the champion arm (P04), pooled over all 8,118
rows:**

| | minutes | attempts | points |
|---|---:|---:|---:|
| P03 ΔMAE vs trailing-5 | **+0.0295** (p 0.0012) | +0.0074 (p 0.024) | +0.0023 (p 0.479) |
| P04 ΔMAE vs champion | +0.0169 (p 0.063) | +0.0071 (p 0.048) | **−0.0034** (p 0.490) |

**And on the 2,475 rows in the 282 team-games where the absence is actually large (≥25 minutes
freed) — a stratification of the same cells, not a new one:**

| | minutes | attempts | points |
|---|---:|---:|---:|
| P03 vs trailing-5 | **+0.1228 = 2.34% of MAE** (p 0.00005) | −0.0039 (p 0.682) | **−0.0366 = −0.84%** (p 0.00015) |
| P04 vs champion | **+0.0927 = 1.82% of MAE** (p 0.0003) | −0.0001 (p 0.993) | **−0.0485 = −1.17%** (p 0.0008) |

**That is the whole result.** Where the treatment is strong, absence knowledge is worth about 2% of
minutes-forecast error against the champion, and it makes the points forecast **worse by about 1%**.

The negative control passes: pseudo-absences constructed on a **disjoint** row set — team-games
where nobody sat — return ΔMAE −0.00067, p 0.8175, against a floor of 0.00796. The machinery does
not manufacture signal from roster arithmetic.

---

## 4. THE COUNTERWEIGHT — stated here, not in a footnote

Four things weaken the headline, and the fourth weakens it most.

**(a) The pooled minutes cell sits ON its power boundary, not past it.** The analytic
`MDE80 = 2.80 × null_sd` rule says 0.0295 > 0.0253 and the cell is decided. A simulated power curve
— planted effect × block bootstrap × the full null, 60 replicates per level — puts the **empirical
power at the observed effect size at 0.783**, not 0.80, and the injection-verified floor at
**0.0308** rather than 0.0253. The honest statement is *at the boundary*. Rescaled to that floor
(3.41 null sds for minutes), the ≥25-minute stratum survives at **4.68** null sds for P03 and
**3.44** — barely over — for P04. The commercial number in §5 is the marginal one.

**(b) The attempts result is an artefact and I caught it by stratifying.** P03_fga's pooled
+0.0074 (p 0.024) is produced **entirely on the rows where the treatment is switched off**
(+0.0158, p 0.00055 on FREED = 0) and reverses sign where it is strongest (−0.0039). It is
coefficient refitting, not attempt redistribution. D111 predicted attempts would be where a
shared-budget constraint bites hardest, because attempts pay the largest bottom-up penalty
(49.6%). **They are not.** Reported as NOT ESTABLISHED. See DEFECTS.md D-3.

**(c) One null partially absorbs its own effect.** The coordinator's tell fires on exactly one of
fourteen cells: `P02_TILT_minutes` has null mean −0.0232 against an observed −0.0349 — same sign,
**67% of the observed statistic**. A null that absorbs part of the effect inflates its p. That
cell's "diffuse" reading is therefore weaker evidence than its p = 0.673 suggests, and it is
carried as NOT ESTABLISHED rather than as evidence of a uniform allocation. No cell has a null mean
*exceeding* its observed statistic.

**(d) The secondary window disagrees about the sign of the tilt, and the disagreement is
significant.** Adding 2022 back (11,721 rows) moves the attempts tilt from +0.058 to **+0.109
(p 0.007)** and the points tilt from +0.043 to **+0.161 (p 0.007)** — both now *positive*, i.e.
concentrated on the *bigger* players, the opposite of the minutes story. Both remain below their
own 80%-power floors (0.149, 0.203) and so remain NOT ESTABLISHED, but **"diffuse" is a
not-established verdict on an unstable statistic, not a demonstration that the allocation is
even.** Anyone who wants the *shape* of the allocation rather than its unforecastability needs more
data than 2021–2024 contains.

---

## 5. The one number that is genuinely new, and the one that closes a door

**New.** For team-games where at least 25 minutes of established playing time is absent —
**282 of 888, about a third** — a redistribution term worth **1.82% of the champion's minutes MAE**
exists and is decided. Nothing in this programme had measured it.

**Closed.** On those same rows, the same term applied to **points** is decided *negative* under the
analytic floor (−1.17% against the champion, p 0.0008; −4.01 and −3.28 null sds). Applying the
injection-verified correction from §7 to the points response — **3.40×**, an extrapolation, so an
upper bound on the floor rather than a measurement of it — those verdicts soften to NOT
ESTABLISHED. But the direction is negative in **all four** points cells that carry a treatment,
across two independent bases and two strata, and **not one of them is positive**. **A
redistribution model does not improve points props.** D111's closing sentence — that the
redistribution "is the entire content of a player-props market" — is, on this evidence, **not
supported for points.** It holds for minutes.

---

## 6. What follows

* **A minutes model is where absence knowledge pays.** Not a points model. If a player-props stack
  is built, absence should enter through the **minutes** stage and be allowed to propagate, not be
  applied to points directly, where it is measurably harmful.
* **Do not model who benefits.** Every pre-game beneficiary signal we could construct explains ≤1.5%
  of the variation. A model that allocates the freed volume *evenly across the remaining rotation*
  is not a simplification — on this evidence it is the best available answer.
* **The threshold is the operationally useful fact.** Under ~30 minutes of absence, do nothing:
  the remaining players were already covering the budget. This is cheap to implement and it is the
  part of the result with the largest effect size.
* **Fix the trailing-form arithmetic before anything else.** A team's established players' recent
  minutes sum to 250 against a 200-minute budget in heavy-absence games. This is the same class of
  defect as D111 ruling 3 — a per-player-calibrated quantity that nobody has ever summed — and it
  is the reason the naive estimator is wrong by roughly 4×.

---

## 7. Discipline record

* **Anchors reproduced on bytes before any new statistic**, and the run halts if any fails: D104's
  home advantage **+0.965090 on 888 games** (exact), D076's **13,879** appeared player-games
  (exact), and **six** figures of E1_I0033's own absence construction — 1,392 team-games, 4,176
  pre-game top-3 rows, appearance rate 0.9411, mean forecast points 14.3408, 183 absence
  team-games, 15.8151 naive points lost (all exact).
* **Arithmetic ceiling computed before any fitting**: ΔR² on the level response of 0.00470
  (minutes), 0.00258 (attempts), 0.00146 (points), against D103's 0.00102 single-cell floor. Points
  was flagged in the preregistration as sitting *below* the programme's largest live effect
  (0.002057), and it duly returned nothing.
* **Nulls matched to the level the candidate varies at**, measured rather than asserted: the P02/P05
  candidates are **95–96% within-team-game between-player**, and their null is a within-team-game
  player swap. The P03/P04 term is **100% team-game** and its null blocks at team-game.
* **The degenerate null demonstrated blind on this screen's own candidate.** A between-player effect
  of 4 null sds planted into the minutes tilt: the within-team-game player swap detects it at
  **p = 0.0017**; the within-player cyclic shift returns **p = 0.8087**. D108's ruling and
  E1_I0036's correction reproduced here directly, not cited.
* **Injection is component-wise** — the planted effect is added to the *real* response and the whole
  path is rerun — and the shuffled-residual construction E1_I0036 found defective is run beside it
  for comparison (`injection_style_comparison.csv`). It systematically **attenuates** the recovered
  effect (e.g. 0.024 → −0.001 on minutes at 2 null sds).
* **Type-I calibration**: 400 synthetic no-effect datasets per N2 cell → rejection rates 0.0575,
  0.0525, 0.0400. N1 at 60 replicates → 0.033, 0.067, 0.050.
* **No-op placebo** reproduces the real statistic with deviation **exactly 0.0** on all three
  channels, and the transform is asserted to be the identity permutation so the check is not vacuous.
* **Bootstrap vs analytic variance**: ratio 0.963–1.013 over six cells. **D113's ~6.6×
  anti-conservatism is NOT reproduced in the variance estimate** — but the *power rule* is
  anti-conservative by **1.22×** (minutes), **1.61×** (attempts) and **3.40×** (points, and that
  one is an extrapolation because the simulated curve tops out at power 0.467). Every verdict above
  says which floor backs it. `power_simulated_curve.csv`, `power_bootstrap_floors.csv`.
* **Eight defects self-reported** in DEFECTS.md, three of which change a headline, including one
  that killed a preregistered cell's apparent positive result and one that downgraded my own
  headline from decided to boundary.
* **No production change is proposed and no champion model was fitted.**
