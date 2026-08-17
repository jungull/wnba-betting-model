# Does anything forecast a player's MINUTES beyond a tuned trailing-minutes estimator?

**E1_I0053_minutes.** `PREREG.md` sha256
`ac373cc884166e263ddfae43466932de430d0f046966c5d918dc3c3853a1168d`, 20,518 bytes, every cell,
candidate, null and decision rule fixed before any candidate-to-response statistic existed.
**0 dropped. 3 grids added after the hash** (`s06` budget decomposition at the coordinator's
request, `s07` robustness, `s08` floors) — all three listed in `NOTES.md`, and **`s07` is the one
that overturned this screen's own headline.**

Regular season, **2023–2024 (the one clean window)**, walk-forward, strictly prior-only, **3,167
decision-stratum player-games in 764 team-game blocks** out of 16,717 appeared player-games in
1,776 team-games. 2021 and 2022 are training data; 2022 is a disclosed contrast and never a
headline. **2025 and 2026 were never opened.**

---

## THE DECISION-STRATUM RESULT, FROZEN AND UNFROZEN

**On the decision stratum in the clean window, seven of eight preregistered minutes candidates are
null in both arms, and the eighth — `C1_player_rest` — clears every preregistered bar at ΔR²
+0.006644 FROZEN and +0.006661 UNFROZEN, a 0.26 % difference: the freeze changes nothing, so this
is an addition to the tuned reference and not a substitute for it.** But **removing the 120 rows
(3.79 % of the stratum) where a player had been away more than seven days takes that cell from
+0.006644 to −0.000408 (p 0.9920), and clipping rest at four days leaves +0.000053 (p 0.1129) — so
it is not a schedule-rest effect at all, it is a return-from-absence effect on 3.79 % of the rows,
and ordinary rest is null.** **And the tuned reference is worth 2.5× to 7.6× more than the whole
of it**: tuning is worth +0.016456 over an untuned EWMA and +0.050624 over the literal trailing-5
mean, against a best candidate of +0.006644.

---

## THE FULL PRIMARY TABLE — `R1_min` (LEVEL) / RAW / DECISION / 2023–24, n = 3,167

Response `minutes`; SST `Σ(y − ȳ)²` about the unweighted mean = **132,506.769701 min²**; no
weighting; base `[1, B_TUNED]` refit walk-forward; statistic paired-forecast ΔR² with shared SST.
**The 200-minute constraint is UNENFORCED in this arm and that is declared, not hidden.**

| candidate | varies | ΔR² FROZEN | ΔR² UNFROZEN | matched null p (F) | 2nd null p (F) | family-wise | eval 2023 / 2024 |
|---|---|---:|---:|---:|---:|---:|---|
| **`C1_player_rest`** | mixed | **+0.006644** | **+0.006661** | **0.0005** | **0.0017** | **0.0010** | +0.00321 / +0.00998 |
| `C7_sched_density` | tg-const | +0.000810 | +0.000859 | 0.2074 | *identity* | 0.4518 | −0.00012 / +0.00171 |
| `C3_blowout_adj` | within-tg | +0.000731 | −0.000050 | 0.0255 | 0.0100 | 0.1524 | +0.00171 / −0.00022 |
| `C4_min_volatility` | within-tg | +0.000533 | +0.000373 | 0.0235 | 0.0300 | 0.1724 | +0.00047 / +0.00060 |
| `C5_starter_delta` | within-tg | +0.000208 | +0.000364 | 0.1214 | 0.1298 | 0.5122 | −0.00032 / +0.00072 |
| `C2_foul_rate` | within-tg | +0.000087 | +0.000232 | 0.1884 | 0.1897 | 0.7091 | −0.00031 / +0.00047 |
| `C6_team_rest` | tg-const | −0.000237 | −0.000236 | 0.5182 | *identity* | 0.8586 | −0.00005 / −0.00041 |
| `C8_opp_pace_prior` | tg-const | −0.001882 | −0.001953 | 0.9855 | *identity* | 1.0000 | −0.00096 / −0.00278 |
| `G01_noise` *(control)* | within-tg | −0.000403 | −0.000405 | 0.7311 | 0.7188 | — | — |
| `G02_tg_noise` *(control)* | tg-const | −0.000154 | −0.000155 | 0.4268 | *identity* | — | — |

**Nothing on this table except `C1_player_rest` clears its own family-wise bar, and nothing except
`C1_player_rest` clears its own 80 %-power floor.** Both controls behaved.

**`C6_team_rest` — days since the team's last game, the canonical minutes story — is flat null at
−0.000237 (p 0.5182) with a pre-fit ceiling of 0.000978.** Schedule rest does not move minutes on
the rows that are bet on. **`C8_opp_pace_prior` is negative in both arms** and was already dead on
arithmetic at 1.1× its own matched control.

---

## THE FIVE THINGS THAT MATTER, IN ORDER

### 1. THE ONLY SURVIVOR IS 120 ROWS, AND IT IS NOT WHAT IT WAS PREREGISTERED AS

`ROBUSTNESS.csv`, every line a **different cell with its own null**, not a reweighting:

| variant of `C1_player_rest` | n | ΔR² FROZEN | `N_TGSWAP` p | `N_PSWAP` p |
|---|---:|---:|---:|---:|
| **V0 published (clipped at 21 days)** | 3,167 | **+0.006644** | **0.0005** | **0.0017** |
| V1 clipped at 7 days | 3,167 | +0.001572 | 0.0095 | 0.0017 |
| **V2 clipped at 4 days** | 3,167 | **+0.000053** | **0.1129** | **0.3677** |
| V3 log1p | 3,167 | +0.003401 | 0.0015 | 0.0017 |
| V4 binary, rest ≥ 4 days | 3,167 | +0.000299 | 0.1249 | 0.1364 |
| **V5 binary, rest ≥ 8 days** | 3,167 | **+0.007107** | 0.0015 | 0.0017 |
| **V6 drop the rows with rest > 7 days** | **3,047** | **−0.000408** | **0.9920** | 0.7953 |
| V7 drop the rows with rest > 4 days | 2,807 | −0.000214 | 0.9975 | 0.6955 |

**A bare binary flag for "eight or more days since this player last appeared" reproduces the entire
effect (+0.007107 against +0.006644), and deleting those rows destroys it (−0.000408).**

`REST_SHAPE.csv` — mean base residual, in minutes, by rest bucket — says the same thing, and it is
a cliff rather than a gradient:

| rest, days | [0,2) | [2,3) | [3,4) | [4,6) | [6,8) | **[8,12)** | **[12,22)** |
|---|---:|---:|---:|---:|---:|---:|---:|
| n | 107 | 1,620 | 792 | 425 | 103 | **44** | **76** |
| mean base residual (min) | +0.29 | −0.03 | +0.44 | +0.37 | +0.29 | **−2.16** | **−4.15** |
| se | 0.48 | 0.14 | 0.19 | 0.27 | 0.53 | 0.93 | 0.84 |

**Everything from one to seven days of rest — 96.21 % of the decision stratum — is flat.** The
signal is that a player returning after eight or more days out plays about **four minutes fewer**
than a trailing-minutes estimator expects, because the estimator's last five appearances predate
the absence and cannot know about it.

**V5 is a diagnostic, not a new survivor.** It was chosen after seeing V0's result, its p-value is
uncorrected for the eight variants tried, and it is reported here to say *where the preregistered
cell's effect lives*, never as a candidate in its own right.

**The commercial scope, stated plainly**: `CONCENTRATION.csv` — 120 rows, in **54 team-game
blocks**, 77 players, 37 dates, split **51 in 2023 and 69 in 2024**. That is about 60 bettable
player-games per season. And `TRANSLATION.csv` puts the whole cell at an rms forecast movement of
**0.306 minutes** (max 1.92) against a response sd of 6.469 minutes, and **ΔMAE = +0.0144 minutes =
0.33 % of MAE**.

### 2. THE TUNING IS WORTH MORE THAN EVERYTHING THIS SCREEN TESTED, COMBINED

`REFERENCE.md`, established before any candidate was measured, identical rows and null:

| contrast | ΔR² | p | its own MDE80 | × floor |
|---|---:|---:|---:|---:|
| `B_TUNED` − `B_NAIVE` (untuned h = 5 EWMA) | **+0.016456** | 0.0010 | 0.013684 | 1.20× |
| `B_TUNED` − `B_TRAIL5` (literal trailing-5 mean) | **+0.050624** | 0.0005 | 0.025308 | 2.00× |
| best candidate anywhere in this screen | +0.006644 | 0.0005 | 0.004760 | 1.40× |

**Two hyperparameters — halflife 3 instead of 5, shrinkage weight 1 instead of 0 — are worth 2.5×
the best candidate. Against the trailing-5 mean, which is the decision stratum's own gate variable,
they are worth 7.6×.** This is the programme's recurring result found for a fourth time, on the
response it had never been tested on.

**And it weakens itself**: the tuned-over-naive gap does **not** replicate in the disclosed 2022
window (+0.009862, p 0.4408) and does **not** survive off the decision stratum (+0.003743,
p 0.1089). Only the gap over `B_TRAIL5` survives both. The robust statement is about the *shape* of
the estimator, not the particular halflife.

### 3. THE PROJECTION GAIN E1_I0051 FOUND IS AN OVERTIME ORACLE, NOT A BUDGET EFFECT

`E1_I0051` measured that projecting a minutes forecast onto the 200-minute budget is worth
ΔR² +0.020020 pooled and asked whether the pre-game-available portion could be isolated. **It can,
and it is zero.** The projection has exactly two ingredients — the total it renormalises *to*, and
the roster it sums *over*. `BUDGET_DECOMPOSITION.csv`, identical base, identical rows, identical
SST, decision stratum, clean window:

| contrast | what it isolates | ΔR², all 764 blocks | p | ΔR², **737 regulation-only blocks** | p |
|---|---|---:|---:|---:|---:|
| `A2_PROJ200` − `A0_RAW` | renormalise to the **rulebook 200** over the realised roster | **−0.006357** | 0.7041 | **−0.000097** | 0.9950 |
| `A3_PROJT` − `A2_PROJ200` | replace 200 with the **realised** `T_min` | **+0.034620** | 0.0005 | **+0.000036** | 0.0005 |
| `A3_PROJT` − `A0_RAW` | the whole projection | +0.028263 | 0.1044 | **−0.000061** | 0.9970 |

**Every bit of the projection gain comes from knowing the realised team total, and the realised
team total differs from 200 only when the game goes to overtime.** Restricted to the 96.43 % of
scored rows in regulation-time team-games, projecting is worth **−0.000061 at p 0.9970**.
Renormalising onto the rulebook 200 — the half that *is* known before tip-off — is worth nothing on
its own, because rescaling to a known constant is informative only relative to the roster you sum
over, and that roster is not known before tip-off either.

**The budget is real; the gain from asserting it is not.** On this screen's own frame the team
minutes total lands within 0.066667 of a multiple of 25 in **1,776 of 1,776 team-games**, mean
201.2695, sd 5.8573 — confirming `E1_I0051`'s item 1. One correction: summed from the player box,
the total is **exactly** 200.000000 in **81.02 %** of team-games and **within 0.07 of 200 in
95.27 %**; the 95.27 % figure is the tolerance band, not exact equality.

### 4. TEAM-GAME-CONSTANT CANDIDATES ARE LIVE ON A LEVEL AND DEAD ON A SHARE — MEASURED BOTH WAYS

The arithmetic is that adding `g·x_g` to every member of a team-game and renormalising divides
through by the same shift. `E1_I0046` used it to dispose of the family on a *points share*. Here it
is measured on **both** responses, which is what the choice of response was for:

| candidate | ceiling, `R1_min` RAW (level) | realised, `R1_min` RAW | ceiling, `R2_smin` (share) | realised, `R2_smin` UNFROZEN |
|---|---:|---:|---:|---:|
| `C6_team_rest` | 0.000978 (5.9× control) | −0.000237 (p 0.52) | 0.000117 | +0.000771 (p 0.8051) |
| `C7_sched_density` | 0.000973 (5.8× control) | +0.000810 (p 0.21) | 0.000108 | −0.000390 (p 0.7051) |
| `C8_opp_pace_prior` | 0.000187 (1.1× control) | −0.001882 (p 0.99) | 0.000550 | −0.001161 (p 0.9870) |

**Forcing the forecast to remain an allocation destroys ~90 % of the arithmetic room for rest and
schedule density before any fit.** So the choice of a level response was necessary to give this
family a fair test — **and given a fair test, on the rows that are bet on, they still do nothing.**
That is a stronger statement than the arithmetic one, and it is the one this screen contributes.

The vacuous control worked exactly as intended: `N_TGSWAP` is the **literal identity** for a
team-game-constant column, and its observed null sd on those cells is **5.4e-20, 2.2e-19, 2.2e-19
and exactly 0.000000e+00** — published rather than rounded, with the `z` suppressed because it is
meaningless at that sd.

### 5. THE COMPONENT DECOMPOSITION SPLITS THE SURVIVOR IN HALF AND NEITHER HALF STANDS ALONE

`C1_player_rest` is 62.3 % between team-games and 37.7 % within (measured in `s00`, before the
prereg), so it was preregistered to be tested component-wise:

| component | ΔR² FROZEN | matched null | p | family-wise | **block-bootstrap t** | eval 2023 / 2024 / *2022* |
|---|---:|---|---:|---:|---:|---|
| `C1_player_rest__B` (team-game mean) | +0.003766 | `N_TGBLOCK`, 335 blocks | 0.0015 | 0.0020 | **2.43 — FAILS** | +0.00106 / +0.00639 / *+0.00122* |
| `C1_player_rest__W` (within team-game) | +0.002392 | `N_TGSWAP`, 1,776 blocks | 0.0005 | 0.0020 | **1.25 — FAILS** | +0.00192 / +0.00285 / *−0.00208* |
| the undecomposed column | +0.006644 | `N_TGSWAP` | 0.0005 | 0.0010 | 2.85 — clears by 1.02× | +0.00321 / +0.00998 / *+0.00161* |

**Both halves are individually significant under their matched nulls and neither survives the block
bootstrap. The whole column survives it by 1.02×.** A screen that had tested only the raw column
under a within-team-game null would have left **58 %** of its ceiling untested, because `N_TGSWAP`
preserves the between component exactly.

**And the between component is not team rest.** `C1_player_rest__B` is the team-game mean of *player*
rest, which is +0.003766 at p 0.0015, while `C6_team_rest` — the team's actual schedule rest — is
−0.000237 at p 0.5182. The difference between those two columns is entirely the absence load on the
roster. **This is `E1_I0034`/D116's absence channel arriving from a different direction, and it
localises it: the channel is absence, not schedule.**

---

## AGAINST THE PREREGISTERED DECISION RULE (PREREG § 9)

| # | requirement | `C1_player_rest` |
|---|---|---|
| 1 | p < 0.05 under **every** matched null | **PASS** — `N_TGSWAP` 0.0005, `N_PSWAP` 0.0017 |
| 2 | exceeds its **injection-verified** 80 %-power floor | **PASS, by 1.40×** — 0.006644 against a conservative 0.004760 (θ80 = 0.6684); the linear-interpolation reading of the same curve gives 0.001863 and 3.57×, and **the conservative one is used** |
| 3 | clears the **family-wise** bar in its null family | **PASS** — 0.0010, coupled max-z, K = 5 |
| 4 | survives the **block bootstrap** | **PASS, by 1.02×** — 0.006644 against 0.006534, bootstrap sd 2.54× the permutation sd |
| 5 | stable in sign across eval 2023 and 2024 | **PASS in sign, FAIL in magnitude** — +0.003210 vs +0.009978, a 3.1× spread; `CONCENTRATION.csv` shows why: 10 of the 76 longest-absence rows are in 2023 and 66 in 2024 |
| 6 | both arms reported; sign disagreement ⇒ substitute | **PASS** — +0.006644 / +0.006661, an addition |

**It passes all six, two of them by 1.02× and 1.40×.** And then §1 above shows that what passed is
not the thing that was preregistered. **The verdict is: ESTABLISHED AS A RETURN-FROM-ABSENCE
EFFECT ON 3.79 % OF THE DECISION STRATUM, NOT ESTABLISHED AS A REST OR SCHEDULE EFFECT, AND NOT
RECOMMENDED FOR PRODUCTION.**

---

## WHAT MOST WEAKENS THIS WHOLE SCREEN

* **The injection recovery curve is not monotone and the floor it produces is a range, not a
  number.** `INJECTION_POWER.csv`: planting θ = 0.20, 0.35 and 0.50 into the real minutes returns
  mean recovered ΔR² of **−0.000604, −0.001196 and −0.000528** — negative recoveries from positive
  plants — before turning positive at θ = 0.70. Power itself is monotone (0.000, 0.050, 0.400,
  0.875, 1.000), so θ80 = 0.6684 is trustworthy and the *recovered-units* conversion is not: the
  floor is anywhere from **0.001863 to 0.004760** and the verdict above uses the conservative end.
  This is `E1_I0046`'s D-06 recurring.
* **The statistic is biased upward for this candidate under a genuinely null draw.** At θ = 0 the
  injection returns a mean recovered ΔR² of **+0.002140**, not 0, because the frozen arm's `g·d`
  term also acts as an accidental intercept correction when the candidate's eval-season mean differs
  from its training mean. **The null is centred at +0.002190 and therefore prices it correctly**
  (null-centre ratio **+1.0232**, type-I 0.060 against a nominal 0.05), but a reader comparing
  +0.006644 to zero rather than to +0.002190 will overstate the effect by 3×.
* **The block bootstrap disagrees with the permutation null by 2.54×** and the cell clears the
  bootstrap floor by **1.02×**. One of the two preregistered variance estimates barely decides this
  cell. `E1_I0046` reported the same disagreement at 8.07× and `E1_I0034` at 0.96–1.01×.
* **Eval 2023 trains on 2021–2022 and 2021 is degenerate** (all forecasts at fallback level 4, no
  usable residual). Half of the clean window is one step removed from that fold, and the two eval
  seasons are reported separately everywhere. The disclosed 2022 window puts the survivor at
  +0.001610 — same sign, one quarter the size — and puts its **within** component at **−0.002080**.
* **The PROJ arms are oracles twice over** and their FROZEN and UNFROZEN values are not comparable
  to each other, because that arm fits on the unprojected response and scores the projected
  forecast (`DEFECTS.md` D-04). The largest number anywhere in `PRIMARY_CELLS.csv` —
  `R2_smin / C3_blowout_adj / FROZEN = +0.019254` — is that artefact and is quoted nowhere else.
* **The brief that commissioned this screen overstates its own strongest pointer.**
  `E1_I0042/HEADLINE_WITH_FLOORS.csv` records the frozen-intercept minutes result at +1.774 % of MAE
  with `verdict_vs_carried = BELOW_FLOOR_NOT_ESTABLISHED` and `effect_over_injection_floor = 0.5547`.
  It survives the freeze; it is **not established** by its own screen. This screen's finding is
  consistent with it and is also small.
* **A powered honest null is what most of this screen found, and that was the expected outcome.**
  Seven of eight candidates null in both arms, both controls behaved, the nulls verified valid by
  injection and non-circular type-I, and the tuned reference worth more than any of them.

---

## WHAT FOLLOWS

1. **Do not build a rest or schedule feature for minutes.** Team rest, schedule density and
   opponent pace are null on the decision stratum, on the response where the arithmetic allows them
   to be live. `C6_team_rest` is −0.000237 at p 0.5182 against a pre-fit ceiling of 0.000978.
2. **The absence channel is the one that exists, and it is a step function, not a gradient.** If
   anything is built, it is a flag for a player returning after eight or more days out, worth about
   four minutes of downward adjustment on roughly 60 bettable player-games per season. **This screen
   does not recommend building it** — it is 3.79 % of the stratum, it clears its bootstrap floor by
   1.02×, and its magnitude is unstable across the two eval seasons.
3. **Stop quoting the 200-minute projection as free headroom.** Its entire measured value is the
   realised team total, which is overtime, which is not knowable before tip-off. On regulation
   games it is worth −0.000061 at p 0.9970.
4. **Tune the reference before measuring anything against it, on every response.** Four for four
   now. On minutes the tuning is worth 2.5× to 7.6× the best candidate.
5. **No production change is proposed, no champion model was fitted, and nothing here should be
   promoted to the ledger without the 2025/26 holdout, which was never opened.**

---

## DISCIPLINE RECORD

* **39 anchors reproduced before any new statistic, 38 of them at exactly `0.000e+00`**, run halting
  on failure (`ANCHORS.csv`): D104's home advantage **+0.96509009** on **888** games; the appeared
  universe at **16,717 / 1,776 / 265**; `E1_I0043`'s decision stratum at **5,673** rows, **149**
  players, **708** games and **3,167** rows in 2023–24; `E1_I0046`'s **764** clean blocks and
  **2,506** training rows; the composition closing against `master_team` with **zero** nonzero
  differences on points and attempts over all 1,776 team-games; and — the load-bearing ones —
  **`E1_I0046`'s published tuned, naive and uniform minutes-share R² for eval 2022, 2023 and 2024,
  together with its selected halflife, shrinkage, training SSE and row counts, all reproduced
  bit-exactly (|Δ| = 0) by an independent reimplementation.**
* **The ceiling was computed and gated before any fit**, with `c*` on every row (all |c*| < 1, so
  every ceiling is a genuine bound), a matched control per **family** rather than one shared one,
  and the family ceiling's degrees-of-freedom cost stated. It opened at 0.025832 (0.023306
  df-corrected). That is the expensive outcome and `CEILING.md` records it as such.
* **Programme floors were not used.** `0.00102` and `0.00235` are `y_ppm`; `0.002057` is a ceiling
  with `c*` = 1.359 and is not an effect; `0.0023492` is on points, n = 4,517. This screen's
  response is minutes, so all of them are `NOT_COMPARABLE` under D101 and **own floors were
  measured** — analytic, injection-verified and block-bootstrap, all three published per cell.
* **Nulls matched to the level, two per candidate, and verified rather than asserted.** Null-centre
  ratios **+1.0232 / +0.9602 / +1.1091** for the three injected candidates against **−0.1103** for
  the blind arm — reproducing `E1_I0043`'s +1.030 vs −0.040 separation on this screen's own data.
  Non-circular type-I **0.060** at α = 0.05 with **sd(z) = 0.935** and max z **+1.87** over 100
  synthetic candidates carrying a real player's whole series but belonging to a player on another
  team-season. A too-narrow null would show sd(z) ≫ 1; it does not.
* **The blind null is demonstrated, not cited.** `N_WITHIN_PLAYER` on this screen's own live cell
  inflates z from **+4.70 to +12.02**. Unlike `E1_I0046`, where it reversed a sign, here it merely
  inflates — **reported as the weaker version of that demonstration**, because that is what was
  measured.
* **Block counts published in every cell**: 1,776 (`N_TGSWAP`), 335 (`N_TGBLOCK`), 48 team-seasons
  over 634 series (`N_PSWAP`), 764 scored blocks. All far above the six below which a two-sided
  sign-flip cannot reject.
* **No-op placebo: observed sd `8.899e-19`, 1 distinct draw value**, with the transform asserted to
  be the identity so the check is not vacuous. **Response placebo** (permute the response inside the
  team-game and rerun the whole path, 200 draws): mean −0.000156, sd 0.000360, **max +0.000744**
  against an observed +0.006644.
* **Future-leakage probe on all ten candidates plus the base.** The survivor sits at **−0.0697**
  against the base's **+0.5816**; nothing exceeds 0.271 in magnitude. No flags.
* **Signed statistics and raw unstandardised draws stored** with full stratum keys in both filename
  and payload, for every cell, every null, every bootstrap and every robustness variant.
* **Eight defects self-reported** in `DEFECTS.md`, two of which would have changed a published
  number: a global-rescale arm that summed the forecast over decision rows only and scored
  R² = −10.34, caught because the number was impossible; and a first ceiling implementation whose
  unanchored `g`-grid returned clip-driven projected oracles up to 0.0330.
* **Pooled numbers are reported second, always.** The decision stratum is 18.94 % of the frame.
* **No production change is proposed and no champion model was fitted.**
