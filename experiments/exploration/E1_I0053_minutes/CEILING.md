# CEILING — COMPUTED BEFORE ANY CANDIDATE WAS FITTED

Screen `E1_I0053_minutes` · `PREREG.md` sha256
`ac373cc884166e263ddfae43466932de430d0f046966c5d918dc3c3853a1168d` (20,518 bytes)
Evidence: `CEILING.csv`, `REFERENCE_TUNING.csv`, `REFERENCE_WORTH.csv`, `out/s03.txt`,
`scripts/_s03.json`. Written after `s03_ceiling.py` and **before `s04_primary.py` existed**.

---

## THE DENOMINATOR, STATED ONCE, FOR EVERYTHING ON THIS PAGE

| | **R1_min (PRIMARY)** | R2_smin (secondary) |
|---|---|---|
| **response** | `minutes` — the **LEVEL**, in minutes | `minutes / T_min(g)` — the **SHARE** |
| **row set** | `DECISION` (`n_prior ≥ 8` AND `prior5_minutes ≥ 24`) ∩ eval seasons 2023–2024, **n = 3,167** in **764 team-game blocks**, 113 players | identical rows |
| **SST basis** | `Σ(y − ȳ)²` over those 3,167 scored rows, about the **unweighted** mean (D069) = **132,506.769701 min²** | **3.163535** (dimensionless) |
| **weighting** | none | none |
| **base** | `X = [1, b]`, `b = B_TUNED` = shrunken EWMA of the player's own strictly earlier minutes, hyperparameters (h = 3, k = 1) selected by SSE on **decision-stratum rows from strictly earlier seasons only** | same, on shares |
| **fit kind** | **walk-forward**: eval 2023 trains on ≤ 2022, eval 2024 trains on ≤ 2023 | same |
| **statistic** | paired-forecast ΔR² with a **shared** SST, so it is exactly `(SSE_base − SSE_aug)/SST` | same |
| **base R² on those rows** | **RAW +0.229438** · **PROJ +0.224872** | PROJ +0.180691 |

`RAW` = the forecast is not required to be an allocation (the **primary** arm for a level).
`PROJ` = the forecast is rescaled inside the team-game to sum to the realised `T_min`. **PROJ is an
oracle** — it reads the realised team total and the realised roster — and no PROJ number on this
page is an achievable live increment.

---

## 1. THE FLOORS. NONE OF THE PROGRAMME'S PUBLISHED FLOORS APPLIES TO THIS RESPONSE.

Quoted from `E1_I0049_benchmark_constants/REFERENCE_CARD.md`, **not from memory**:

| constant | what it actually is | response | row set |
|---|---|---|---|
| `0.00102` | single-cell detection floor, drift-corrected, `t_crit(K=1) = 1.645` | **`y_ppm` — points per minute** | DECISION, **n = 5,673**, 2021–2024 |
| `0.00235` | same cell at `family_size_K = 132`, `t_crit = 6.974475` | **`y_ppm`** | identical |
| points-scale equivalents | **≈ 0.00072 / ≈ 0.00181** — and the **defensible output is the ratio 0.704 / 0.770**, not the absolute numbers | `y_pts` | n = 5,673 |
| `0.002057` | an **in-sample transported CEILING**, `c* = 1.359 → NOT A BOUND`. Never an effect. | `y_pts` | n = 5,673 |
| **`0.0023492`** | the programme's largest **live effect**: walk-forward paired ΔR² | `y_pts` | **n = 4,517**, seasons **2022–2024** |

**This screen's response is minutes, and its secondary response is a minutes share. Neither is
`y_ppm` and neither is points.** Under D101 every comparison between a number on this page and any
of the five constants above is **`NOT_COMPARABLE`**, and this screen does not make one. The floor
intervals (`0.00091–0.00336` at K=1, `0.00235–0.00974` at K=132) are likewise not transportable
here.

**This screen therefore computes its own floors, on its own response, row set, SST and null.** They
are in `POWER_FLOORS.csv` and in `VERDICT.md`: an analytic `2.80 × null_sd`, an
**injection-verified** 80 %-power floor from planting a component-wise effect into the **real**
response and rerunning the whole path, and a block bootstrap over the 764 scored team-game blocks.
**Where the three disagree, the verdict is taken against the injection-verified floor.**

The only comparison this page makes is to **its own matched noise controls**, which go through the
identical path on the identical rows:

| control | what it controls | `R1_min` RAW oracle | `R1_min` PROJ oracle | `R2_smin` PROJ oracle |
|---|---|---:|---:|---:|
| `G01_noise` | seeded row-level normal — the **within-team-game** family | **0.000032** | 0.000090 | 0.000090 |
| `G02_tg_noise` | seeded **team-game-constant** normal — the **team-game-constant** family | **0.000167** | 0.000415 | 0.000458 |

**`G02_tg_noise` is 5.2× `G01_noise` on the primary arm.** A team-game-constant column has far fewer
effective degrees of freedom (764 blocks, not 3,167 rows), so its ceiling statistic is noisier.
**Every team-game-constant candidate below is therefore read against `G02_tg_noise`, not against
`G01_noise`** — which is reference-card rule 5, applied per family rather than once.

---

## 2. THE CEILING, PRIMARY RESPONSE AND PRIMARY ARM: `R1_min` / `RAW`

`d` = candidate standardised to unit sd and residualised on the base design `[1, b]` on the scored
rows; `e` = the base's walk-forward eval residual; `SST` as above.

**Unconstrained oracle** `= (d·e)² / ((d·d)·SST)` — bounds the **UNFROZEN** arm.
**`c*` = (d·e)/(d·d)** — published for every row. **`|c*| < 1` is what makes a ceiling a bound.**
**`(d·d)/SST` is not a bound** (E1_I0043 D-02) and is in the CSV for continuity only.

| candidate | varies | ORACLE ΔR² (unconstrained) | ORACLE ΔR² (only `g` free) | `c*` | corr with base | × its own matched control |
|---|---|---:|---:|---:|---:|---:|
| **`C1_player_rest`** | **mixed** | **0.009455** | 0.009537 | **−0.6292** | −0.016 | **295×** `G01` |
| `C6_team_rest` | tg-constant | 0.000978 | 0.001008 | −0.2024 | +0.002 | **5.9×** `G02` |
| `C7_sched_density` | tg-constant | 0.000973 | 0.001035 | +0.2018 | +0.019 | **5.8×** `G02` |
| `C3_blowout_adj` | within-tg | 0.000752 | 0.000821 | +0.1848 | +0.279 | 23.5× `G01` |
| `C5_starter_delta` | within-tg | 0.000694 | 0.000403 | +0.1796 | −0.314 | 21.7× `G01` |
| `C4_min_volatility` | within-tg | 0.000387 | 0.000636 | −0.1386 | −0.397 | 12.1× `G01` |
| `C2_foul_rate` | within-tg | 0.000375 | 0.000177 | +0.1329 | −0.332 | 11.7× `G01` |
| `C8_opp_pace_prior` | tg-constant | 0.000187 | 0.000169 | +0.0886 | −0.056 | **1.1×** `G02` |
| `G01_noise` *(control)* | within-tg | 0.000032 | 0.000031 | +0.0364 | −0.002 | — |
| `G02_tg_noise` *(control)* | tg-constant | 0.000167 | 0.000158 | −0.0837 | +0.017 | — |
| **FAMILY (8 real, joint)** | — | **0.025832** | — | — | — | — |

**Every `|c*|` is below 1, so every ceiling on this page is a genuine bound on its own cell.**
The largest is `C1_player_rest` at 0.6292; the noise controls sit at 0.036 and 0.084.

**The gate opens.** The family ceiling is **0.025832**, and after the degrees-of-freedom cost of
eight free coefficients on 3,167 rows (`K/n = 0.002526`) it is **0.023306**. The channel cannot be
closed on arithmetic, and the preregistered gate releases the fit. **This is the expensive outcome
and it is recorded as such.**

**`C8_opp_pace_prior` is arithmetically dead before any fit** — 1.1× its own matched control, on the
arm where a team-game-constant candidate is *supposed* to be live. Opponent pace does not move
minutes, on the level, and no fit was needed to say so.

---

## 3. THE COMPONENT DECOMPOSITION — AND THE ONE RESULT THAT NEEDED NO FIT

`C1_player_rest` is **62.3 % between team-games and 37.7 % within** (measured in `s00`, before the
prereg). A null matched to one component is blind to the other, so it is split before it is tested:

| component | what it is | ORACLE ΔR², `R1_min`/RAW | its null |
|---|---|---:|---|
| `C1_player_rest__W` | player rest **minus** her team's rest that night | **0.004128** | `N_TGSWAP` + `N_PSWAP` |
| `C1_player_rest__B` | the team-game mean of player rest | **0.005489** | `N_TGBLOCK` |
| sum | | 0.009617 | |
| the undecomposed column | | 0.009455 | |

**Both halves carry room, and they carry roughly equal amounts.** A screen that tested only the raw
column under a within-team-game null would have left **58 %** of its ceiling untested by
construction, because `N_TGSWAP` preserves `__B` exactly. The other four within-tg candidates split
far less evenly (`C2` 0.000627/0.000173, `C3` 0.000311/0.000542, `C4` 0.000272/0.000084, `C5`
0.000455/0.000292) and the noise control splits as it must (`G01__W` 0.000044, `G01__B` 0.000005).

---

## 4. THE CONSTRAINT, MEASURED BEFORE ANY FIT — AND IT DOES NOT GO THE WAY THE POINTS SCREEN WENT

Adding `g·x_g` to every member of a team-game and renormalising divides through by the same shift.
`E1_I0046` used that to dispose of the whole team-game-constant family **on a share response**, and
measured `A5_opp_defrtg` at ΔR² −0.000005. **The same arithmetic, run here on both responses:**

| candidate | `R1_min` **RAW** (level, constraint unenforced) | `R1_min` **PROJ** (constraint enforced) | `R2_smin` **PROJ** (share) | matched control on that arm |
|---|---:|---:|---:|---:|
| `C6_team_rest` | **0.000978** (5.9× control) | 0.000101 | 0.000117 | `G02` 0.000167 / 0.000415 / 0.000458 |
| `C7_sched_density` | **0.000973** (5.8× control) | 0.000098 | 0.000108 | same |
| `C8_opp_pace_prior` | 0.000187 (1.1×) | 0.000520 | 0.000550 | same |

**On the unconstrained oracle, forcing the forecast to remain an allocation destroys 90 % of
`C6_team_rest`'s ceiling and 90 % of `C7_sched_density`'s, and drops both to *below* their own
matched noise control.** That is the arithmetic in the brief, confirmed on minutes and stated in the
direction that matters: **rest and schedule density are live on a minutes LEVEL and dead on a
minutes SHARE.** A screen that had chosen the share response would have closed this entire family
without ever learning that it moves the level.

**This is why the primary response here is the level, and it is also the reason the primary result
below is not a commercially usable one:** the level arm does not enforce the 200-minute budget, and
the arm that does enforce it is an oracle.

### 4.1 A ceiling on the PROJ arm that is NOT usable as headroom

The `ORACLE_projected` column for the PROJ arms runs far above the linear oracle — `C3_blowout_adj`
at 0.032978 against an unconstrained 0.002388. **This is not a bug and it is not headroom.** The
projection is **nonlinear**: adding `g·d` and renormalising *redistributes* minutes inside the
team-game, which is a far more expressive operation than an additive shift, so the one-parameter
hindsight search is not bounded by the linear oracle. The non-negativity clip is **not** the cause —
`clip_frac_at_gstar` is 0.0000 for all but two component cells (max 0.0025) — but the number is a
hindsight fit of one parameter through a nonlinear map on the eval rows and it is **not corrected
for that**. `CEILING.csv` carries a companion column, `ORACLE_projected_g_within_2g0`, restricting
`g` to twice its linear value; it removes 18–55 % of the excess. **No verdict in this screen uses
the projected oracle.** Recorded as **D-02** in `DEFECTS.md`.

---

## 5. THE SAME-CHANNEL CHECK, RUN BEFORE THE FIT

`E1_I0046`'s largest single number was excluded as same-channel — the candidate *was* the base's own
channel at a different halflife, so it measured smoothing, not information. The check here is
`corr(candidate, base)` on the scored rows, in the table above. **The largest magnitude is
`C4_min_volatility` at −0.397 and `C2_foul_rate` at −0.332; nothing approaches the ≥ 0.9 that would
make a cell same-channel.** `C3_blowout_adj` is +0.279 — it is a *correction to* the trailing mean,
a difference of two prior means, not the trailing mean at another halflife, and its correlation
confirms that.

---

## 6. WHAT ON THIS PAGE MOST WEAKENS IT

* **The family ceiling is a hindsight fit of eight columns to 3,167 residuals.** The stated
  df-corrected figure (0.023306) subtracts only the expected null R² of eight free coefficients; it
  does not correct the per-candidate ceilings at all, and the measured pure-noise single-candidate
  value (0.000032) sits **below** the `1/3167 = 0.000316` a single free coefficient would predict,
  so the noise floor is if anything flattering to the candidates.
* **`C1_player_rest`'s ceiling is 9.7× the next largest, and that should raise suspicion, not
  excitement.** Days since a player's own last appearance is very close to "this player just missed
  games", and a player returning from an absence is exactly the population whose minutes are
  restricted. The ceiling being large is consistent with a real and well-known effect; it is equally
  consistent with the candidate being a proxy for a state the *reference* already partly knows
  about. **The frozen arm is the check that separates those two, and it is reported beside the
  unfrozen one for every cell.**
* **A ceiling is not an effect.** `0.009455` is the most a hindsight-optimal linear coefficient
  could extract in-sample from this column over this base. `E1_I0049` documents a cell where the
  realised value exceeded the published ceiling by 61 % and another where the ceiling overstated the
  true bound by 3.34×. **Nothing on this page is a result.**
* **2023's overlay is one step removed from the degenerate 2021 fold.** Eval 2023 trains on
  2021–2022, and 2021 is degenerate (all forecasts at fallback level 4). Half of the clean window
  therefore inherits a training set that is partly built on a fold with no usable residual. Eval
  2024 does not, and the two seasons are reported separately everywhere.
