# E1_I0056 — MINUTES VARIANCE

**E1. Non-claiming. Nothing here is promoted, and nothing here may be cited as a result.**
Preregistration `PREREG.md`, sha256 `fda506c52352b33b8a5e5728a178bf407c938e23542a648521e513a55dd1e9d1`,
written and hashed before any statistic in s01–s06 was computed. No threshold, seed, arm or draw
count was revised after a result was seen.

Response: `absres_minutes`, the realised absolute error of the **shipped** minutes point forecast.
Stratum `A4_CLEAN_DEC` (2023–24, `pl_games_prior ≥ 8`, `pl_min_mean5 ≥ 24`): 3,549 rows, 174
player-seasons, 848 team-games; walk-forward, 138 folds, **2,945 scored rows**, SST 40,861.607444.
Plain unweighted R², shared SST for every increment (D069/D072).

---

## The three answers, in one paragraph each

**1. The season-constancy defect is real, and it is a scalar broadcast.** Confirmed on the shipped
prediction parquet bytes, not on the derived frame and not on a column name. `pred_sd` takes
**exactly one distinct value per season for all three targets in all three seasons** — minutes
6.710391 (2022), 5.934714 (2023), 6.037462 (2024), range exactly 0.0. `pred_q50` and `pred_q75` are
`pred_point` plus a single per-season offset; the only per-row variation anywhere in the emitted
quantiles is deterministic clipping at the `[0, 48]` support, which reproduces to ≤ 3.6e-15. The
emitting line is **`cbs_player_runner_v14.py:313`**, `pd.Series(sd_v, index=test.index)` — one
scalar `sd_v`, computed once per fold at `cbs_player_runner_v14.py:286` from
`cbs_v5.py:169-180 dispersion()`, broadcast to every test row. s00's label was accurate and this
screen widens it from the decision stratum to the whole file.

**2. Most of what D134 attributed to non-level signal is reference incompleteness, and the
remainder is not established.** The published reference — trailing level alone, a single column —
scores OOF R² **+0.018378** and a decile ratio of **1.3542**. A level-only ladder that a forecaster
could have built at the same moment scores **+0.034756** and **1.8407**. That is **1.89× the
published reference on R² and 89 % of the way from 1.35 to 1.91 on the decile ratio, using nothing
but levels.** Adding 36 non-level columns on top moves it to **+0.045434 / 1.9603**, an increment
of **+0.010678** over the best level rung (+0.012057 over the preregistered rung). That increment
is **not distinguishable from zero**: block bootstrap over the 174 player-seasons gives a 95 % CI of
**[−0.009571, +0.036266]** with 15.85 % of draws at or below zero. The level ladder's own gain, by
contrast, **is** established — dR²(`L4` over `L1`) = **+0.016378**, CI **[+0.003825, +0.029789]**,
0.30 % of draws at or below zero. (Every sign-flip p in this screen is uncalibrated; see D-9.)

**3. Even taken at face value it buys almost nothing.** Abstaining on the worst 30 % of rows by the
full model's predicted error cuts the shipped forecast's MAE by **9.48 %**; abstaining on the
level-only ranking cuts it by **9.26 %**. The non-level block is worth **0.22 percentage points** —
about **0.009 minutes of MAE** on the retained rows. At matched 80 % coverage the interval widths
are 13.388 min (shipped constant sd), 13.215 min (level-only), 13.382 min (full model): the
variance model is **0.04 % narrower than a constant** and **1.27 % WIDER than the level-only
model**. It does not convert into a better minutes forecast either — best of four conversion arms
**+0.00124 dR² at p = 0.69**, and the variance-weighted refit is catastrophic at **−2.78**.

**The qualification that keeps this from being a flat null.** The same 36 columns, same rows, same
folds, produce a **+0.028605** increment when the response is the error of a *trailing-mean*
forecast rather than the shipped one — 2.4× larger. The block does carry real information about
minutes dispersion, and it sits **+9.53 sd above its own noise placebo**. What is unestablished is
that it says anything about the **shipped** forecast's errors in particular, and the design is
underpowered there: an injected signal worth dR² 0.0074 is detected **5.0 %** of the time
(iid) and **2.5 %** (player-season-clustered), so the observed +0.012 sits inside the design's own
detection floor. **This is an underpowered null and must not be reported as an absence.**

---

## Question 1 — the defect, settled on bytes

`SHIPPED_UNCERTAINTY.csv`, `scripts/run_log_s01.txt`.

| target | season | n | `pred_sd` distinct | value | `q75−point` distinct | `q50−point` distinct |
|---|---|---|---|---|---|---|
| minutes | 2022 | 6,333 | **1** | 6.710391139367 | **1** | **1** |
| minutes | 2023 | 7,418 | **1** | 5.934714400560 | **1** | **1** |
| minutes | 2024 | 7,866 | **1** | 6.037461772357 | **1** | **1** |
| pts | 2022–24 | — | **1** each | 5.455/5.258/5.412 | **1** each | 42/58/76 |
| fga | 2022–24 | — | **1** each | 3.349/3.205/3.265 | **1** each | 6/17/7 |

`pred_q05` shows 523–710 distinct offsets and `pred_q95` shows 4–36, and **all** of that variation
is clipping: `pred_q05 == max(pred_point + off05, 0)` reproduces every row to a maximum absolute
deviation of **3.553e-15**, and `pred_q95 == min(pred_point + off95, 48)` to **7.105e-15**. On the
decision stratum the 90 % interval width takes 37 distinct values across 3,549 rows with an sd of
**0.224 minutes** — i.e. it is a constant plus edge effects.

The dispersion method was decided on values, not on the name: a Gaussian construction would give
`off_q75 = 0.6744897501960817 × sd` exactly and `off_q50 = 0`. Measured, `off_q75 − z75·sd` is
+0.045019, −0.143580 and −0.224021 across the three seasons and `off_q50` is +0.457048, −0.009895
and +0.106481 — so `dispersion()` took its `empirical` branch (`cbs_v5.py:179`), which returns the
empirical quantiles of the fold's residual pool. Empirical or Gaussian, the branch is irrelevant to
the finding: **both branches return one number per fold.**

**Code path.** `run_player_oof_v15.py` → `cbs_player_runner_v15` (forks `cbs_v14._run` at exactly
one identity line) → `cbs_player_runner_v14.run_player_fold`, unforked. Inside it:

- `cbs_player_runner_v14.py:286` — `sd_v, off, method = dispersion(residuals(...), min_resid=...)`
  returns a **float**, one per (fold, target).
- `cbs_player_runner_v14.py:313` — `pd.Series(sd_v, index=test.index)` — **the line.** The same
  construction appears at `cbs_v8.py:965`, `cbs_v8.py:1134`, `cbs_v7.py:1428`, `cbs_v7.py:1603`.

**This is a capability gap presented as a capability, not an arithmetic mistake.** `dispersion()`
does what its docstring says. The column is named `pred_sd`, sits in a per-row prediction table
next to `pred_point`, and is therefore read downstream as per-row uncertainty. It is not. Its
measured OOF R² on this response is **−0.004813** — an intercept with extra steps, which is exactly
D134's "negative out-of-fold R²" and now has a file and a line.

Reported, not worked around. **No file outside this screen was modified.**

---

## Question 2 — the increment over trailing level

`REFERENCE_LADDER.csv`, `NULL_LEVEL.csv`, `raw/s02_nulls.npz`, `scripts/run_log_s02.txt`.

### The reference ladder — this is the finding

| rung | columns | OOF R² | decile ratio | calib slope |
|---|---|---|---|---|
| `L0` intercept | 0 | −0.002107 | 0.9305 | −1.63 |
| **`L1` trailing level alone (the D134 reference)** | 1 | **+0.018378** | **1.3542** | +0.84 |
| `L2` + square, cube | 3 | +0.018379 | 1.3458 | +0.84 |
| `L3` + predicted level, its square, its reciprocal | 6 | +0.027334 | 1.6629 | +0.92 |
| **`L4` eight level columns, linear — STRONGEST** | 8 | **+0.034756** | **1.8407** | +0.92 |
| `L5` `L4` + squares, cubes, reciprocals (preregistered primary rung) | 15 | +0.033377 | 1.7980 | +0.89 |
| | | | | |
| `C1` = `L1` + block N | 37 | +0.041046 | 1.8837 | +0.83 |
| **`C5` = `L5` + block N (PRIMARY)** | 51 | **+0.045434** | **1.9603** | +0.82 |
| `NONLY` block N alone | 36 | +0.041048 | 1.8441 | +0.85 |
| `C5X` = `L5` + block N + the `x53_*` block | 63 | +0.035814 | 1.8284 | +0.74 |
| `VSIG` (D134's arm, selection-carrying) | 7 | +0.042866 | 1.9089 | +1.01 |
| `VSD` the shipped column | 1 | −0.004813 | 0.9488 | −0.51 |

**The level-only reference spread is 0.016378 in R², i.e. a factor of 1.89 (L1 → L4).** T4 says only
decomposition catches reference incompleteness, and here it caught most of the effect: D134 reported
1.91 against 1.35 and concluded that minutes carries genuine non-level signal, but **a level-only
ladder reaches 1.8407**. The gap the non-level block actually has to explain is 1.8407 → 1.9603, not
1.3542 → 1.9089.

Two smaller readings from the same table. `C1` (+0.041046) and `NONLY` (+0.041048) agree to five
decimal places, so **once the 36 non-level columns are present the single trailing-level column adds
nothing** — the block already carries the level information. And `C5X` (+0.035814) is *worse* than
`C5` (+0.045434): adding the `x53_*` block, 10.85 % of whose rows are imputed, costs 0.0096.

### Increments and their nulls

| statistic | value |
|---|---|
| **dR²(C5 over L5)** — preregistered primary | **+0.012057** |
| dR²(C5 over L4) — over the strongest level rung | **+0.010678** |
| dR²(C1 over L1) — over the D134 reference | +0.022668 |
| block bootstrap, 174 player-season blocks, R = 2000 | **95 % CI [−0.009571, +0.036266]**, frac ≤ 0 = **0.1585** |
| (over `L1`) block bootstrap | CI [−0.003140, +0.050815], frac ≤ 0 = 0.0490 |
| N1 cyclic within-player-season, R = 1000 | centre **+0.011500**, sd 0.005430, **p = 0.426573** |
| N1b plain shuffle, R = 1000 | centre +0.011013, sd 0.004302, p = 0.387612 |
| N3 noise control (36 iid columns), R = 200 | centre **−0.006882**, sd 0.001988, all 200 draws negative |
| paired cluster sign-flip, player-season / team-game, R = 5000 | p = 0.342132 / 0.362328 — **UNCALIBRATED, see below** |

### The three nulls do not conflict; each destroys something different

Read them as a decomposition rather than as competing verdicts:

| what the null destroys | centre of the statistic |
|---|---|
| everything — 36 iid columns of the same dimension (N3) | **−0.006882** |
| only the within-player-season timing; cross-sectional identity kept (N1 cyclic) | **+0.011500** |
| nothing — the real block | **+0.012057** |

**Essentially all of the increment is cross-sectional and essentially none of it is temporal.**
The real block sits **+9.5 sd above its own noise placebo** (a random block of 36 columns *costs*
0.0069 of out-of-fold R², so the block is doing something a random block does not do) and
**+0.10 sd above the cyclic null** (scrambling when each volatility reading occurred inside a
player's season changes nothing). What it is telling you is *which player-season this row belongs
to* — chronically erratic players have larger minutes errors — not *when in that season you are*.

### Why the sign-flip p is not usable, and what stands in its place

**P11 FAILED and the failure is the point.** The noise control's `dR²` is centred at
**−0.006882**, not at zero — adding 36 uninformative columns to an out-of-fold ridge reliably
*costs* R², so the paired loss difference has a systematic sign under H0. The consequence is
measured: **the cluster sign-flip rejects at 0.420 against a nominal 0.05 on pure noise.** A test
with a 42 % false-positive rate cannot be quoted, in either direction, and **the p = 0.342 above
must not be read as "p = 0.34".** This is `E1_I0054`'s D-3 defect reproduced on a different response
and a different arm set, and considerably larger.

What stands in its place is the **block bootstrap over player-seasons**, which resamples the
entities the effect is attached to and needs no null centring: **95 % CI [−0.009571, +0.036266],
frac ≤ 0 = 0.1585.** That is the basis for "not established". It is a statement about whether the
increment would survive to a fresh set of player-seasons, and it does not.

### Which permutation scheme is correct

`detect_grouping_level` returns `NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE` — the kit's
K2 case. The median within-player-season lag-1 autocorrelation across block N is **0.5654** (P16
held; `pl_minutes_prior` 0.902, `pl_min_sd5` 0.594, `tm_rest_days` −0.099), so a plain shuffle is
excluded by D093 and the cyclic variant is required. **D093's direction is confirmed on this
screen's own numbers:** the shuffle null is **21 % narrower** than the cyclic one
(sd ratio 0.7922) and returns the smaller p (0.3876 vs 0.4266) — anticonservative, exactly as K6
predicts, on a block whose median acf1 is 0.57.

**The cyclic null answers a narrower question than the headline**, because it preserves everything
between player-seasons. The kit's own answer to the between-entity question is `entity_swap_null`;
it was **not preregistered and was not run** (DEFECTS D-6). A future screen wanting a permutation
verdict on the cross-sectional component should run it.

---

## Question 3 — what the increment is worth

### Abstention, in minutes (`ABSTENTION.csv`)

Full sample: n = 2,945, MAE **4.2777 min**, RMSE 5.6722 min.

| drop worst … | rank by `L1` | rank by `L4` (level-only) | rank by `C5` (full) |
|---|---|---|---|
| 10 % | 2.16 % | 3.72 % | 3.90 % |
| 20 % | 4.54 % | 5.93 % | 7.42 % |
| **30 %** | 6.76 % | **9.26 %** | **9.48 %** |
| 40 % | 9.73 % | 11.26 % | 14.16 % |
| 50 % | 10.59 % | 13.31 % | 15.19 % |

P12 held on its own terms (9.48 % ≥ 8 %), **and it is a level effect**. Against the level-only
ranking the non-level block is worth **0.22 percentage points of MAE reduction — 0.009 minutes**.
This is the same shape `E1_I0054` found on points ("abstention's MSE gain is a level effect"),
reproduced independently on minutes with a stronger level reference.

### Intervals (`INTERVALS.csv`)

Predicted mean absolute error is converted to a Gaussian sd by ×√(π/2) and an 80 % interval is
`pred_point ± 0.8416·sd`.

| model | coverage at nominal 80 % | mean width | **mean width at matched 80 % coverage** | sd of the per-row sd |
|---|---|---|---|---|
| shipped constant sd | 0.6849 | 10.094 min | **13.388 min** | 0.0503 |
| `L1` | 0.6312 | 8.967 min | 13.016 min | 0.7738 |
| `L4` level-only | 0.6275 | 8.966 min | **13.215 min** | 0.9489 |
| `C5` full | 0.5986 | 8.573 min | **13.382 min** | 1.2793 |

Every arm **under-covers at nominal 80 %**, including the shipped one at 0.685 — the ×√(π/2)
conversion assumes a Gaussian residual and these residuals are heavier-tailed, so nominal coverage
is not the comparison to read. The comparison to read is matched-coverage width, and there the
answer is blunt: **the full variance model is 0.04 % narrower than a per-season constant and 1.27 %
wider than a level-only model.** Making the per-row sd more variable (sd 0.05 → 1.28) does not make
the interval that has to contain 80 % of the outcomes any smaller.

*Disclosed:* the matched-coverage scale is an oracle — it is the 80th percentile of
`|residual| / sd` on the scored rows. It is applied identically to every arm and supports only a
width-at-equal-coverage comparison, never a coverage claim (DEFECTS D-4).

### It does not convert into a better minutes forecast (`CONVERSION.csv`)

Response `y_minutes`, same folds, reference a tuned ridge on the level columns
(OOF R² **+0.250786**, which itself beats the shipped forecast's **+0.241269** — the fourth
independent sighting of D133's "the tuning beats every candidate").

| conversion arm | OOF R² | dR² over the level reference | sign-flip p |
|---|---|---|---|
| variance-weighted refit (weights 1/v̂²) | −2.531780 | **−2.782565** | 0.0002 |
| adaptive blend of shipped vs level, weights linear in v̂ | +0.245541 | −0.005244 | 0.1282 |
| mean augmentation (v̂ as a feature) | +0.252026 | **+0.001240** | 0.6879 |
| v̂ × trailing level interaction | +0.250426 | −0.000359 | 0.9154 |

**P13 held: there is no conversion.** The best arm is +0.00124 at p = 0.69. The
variance-weighted refit is not merely unhelpful, it is catastrophic and significantly so — because
v̂ is a *predicted mean absolute error*, and 1/v̂² is a wildly heavy-tailed weight on 2,945 rows.
That arm is reported at full size rather than dropped.

### It does replicate on a second response, and there it IS significant (`REPLICATION.csv`)

| scheme | response | `L1` | `L4` | `L5` | `C5` | dR² over `L5` | sign-flip p |
|---|---|---|---|---|---|---|---|
| WF | `absres_minutes` (shipped forecast's error) | +0.018378 | +0.034756 | +0.033377 | +0.045434 | **+0.012057** | **0.3421** |
| WF | `refabs_minutes` (trailing-mean forecast's error) | +0.023893 | +0.063260 | +0.062831 | +0.091436 | **+0.028605** | **0.0194** |
| GKF | `absres_minutes` | +0.018578 | +0.033978 | +0.034278 | +0.055691 | +0.021412 | — |

**This is the most important qualification in the screen and it cuts against a flat null.** The same
36 non-level columns, on the same rows and the same folds, give an increment **2.4× larger and
significant at p = 0.019** when the response is the error of a *trailing-mean* forecast instead of
the error of the *shipped* forecast. So the block does carry real information about how dispersed a
player's minutes will be. What is not established is that it carries information about the
**shipped forecast's** errors specifically, on this stratum, at this sample size. The reference
incompleteness result holds on both responses and is if anything larger on the second (`L1`
+0.023893 → `L4` +0.063260, a factor of 2.65).

The GKF row scores all 3,549 rows but its folds contain future games; it is reported and never
differenced against the WF row.

---

## D131 — the 200-minute budget

The primary response is a per-row dispersion and does not sum, so the projection requirement does
not bind it. Reported anyway because the brief requires it of any minutes work, and **as dispersion,
never as a mean** (`A1_FULL`, 13,879 rows, 1,486 team-games):

| per-team-game sum | MAE vs 200 | RMSE vs 200 | within ±5 | exactly 200 |
|---|---|---|---|---|
| realised minutes | 1.9940 | 7.3210 | 91.25 % | 76.31 % |
| shipped forecast | **13.1698** | 17.6185 | **27.79 %** | 0.00 % |

This independently reproduces D131's 13.09 MAE and D133's correction that exact equality is ~81 %
rather than ~95 % (76.31 % here on the appeared-row sum over 1,486 team-games, against D133's
81.02 % on its own row set — the same order, measured on a different universe).

---

## Power — and this null is only partly powered

`POWER_INJECTION.csv` (preregistered, iid injection) and
`POWER_INJECTION_CLUSTERED_POSTHOC.csv` (post-hoc, player-season-constant injection). Both inject
`y + c·sd(y)·u` with `u` appended to block N, 40 replicates per `c`, detection = paired sign-flip
`p < 0.05`. The `c = 0` row is **not** a Type-I row (block N is still present); it is the detection
rate of the *real* observed increment, and it is **0.000** in both curves.

| c | implied dR² | realised dR² (iid) | detection (iid) | realised dR² (clustered) | detection (clustered) |
|---|---|---|---|---|---|
| 0.00 | 0.000 | +0.011742 | **0.000** | +0.011883 | **0.000** |
| 0.10 | 0.0099 | +0.018376 | **0.050** | +0.019254 | **0.025** |
| 0.15 | 0.0220 | +0.027918 | 0.900 | +0.027650 | 0.650 |
| 0.20 | 0.0385 | +0.041509 | 1.000 | +0.039136 | 0.925 |
| 0.30 | 0.0826 | +0.076151 | 1.000 | +0.074530 | 1.000 |
| 0.40 | 0.1379 | +0.122789 | 1.000 | +0.119979 | 1.000 |
| 0.60 | 0.2647 | +0.253862 | 1.000 | +0.238768 | 1.000 |
| 0.90 | 0.4475 | +0.422749 | 1.000 | +0.422749 | 1.000 |

**MDE at 80 % power: total realised dR² +0.027918 (iid) and +0.039136 (player-season-clustered).**
Subtracting the +0.0118 that block N already supplies, the *added* signal a fresh column must carry
to be detected is roughly **+0.016 (iid)** and **+0.027 (clustered)**.

**P15 FAILED, and it is the most consequential failure in the screen.** The observed increment is
+0.012057. The design detects an added iid signal of dR² 0.0074 five per cent of the time and an
added clustered one two-and-a-half per cent of the time. **The observed effect is well inside the
design's own detection floor, and block N's information is measured to be cross-sectional — the
clustered case, the worse of the two.** So this is a null that is *not powered against an effect of
the size actually seen*, and it must not be reported as "the increment is absent". It is reported
as **not established, and not resolvable on this stratum**.

The honest boundary: 174 player-seasons on 2,945 rows is not enough to settle a dR² of 0.01 on this
response with a cluster-honest procedure. What *is* settled on this stratum is the reference
incompleteness (bootstrap CI excludes zero) and the decision value (below).

---

## The preregistered predictions: 14 held, 3 failed, nothing revised

| id | prediction | outcome |
|---|---|---|
| P1 | `pred_sd` 1 distinct value per season on the shipped parquet | **HELD** |
| P2 | `q75`/`q50` offsets 1 distinct value per season | **HELD** |
| P3 | all `q05` row-variation is clipping (max dev < 1e-9) | **HELD** (3.553e-15) |
| P4 | `VLEV` anchor reproduces to 1e-6 | **HELD** (9.7e-17) |
| P5 | `VSIG` anchor reproduces | **HELD** (2.9e-16; ratio 0.0) |
| P6 | strongest level-only rung reaches OOF R² ≥ 0.030 | **HELD** (`L5` +0.033377) |
| P7 | dR²(C5 over L5) > 0 | **HELD** (+0.012057) |
| P8a | dR²(C1 over L1) ≥ 0.015 | **HELD** (+0.022668) |
| P8b | dR²(C5 over L5) ≥ 0.010 | **HELD** (+0.012057) |
| **P9** | **cyclic null p < 0.05** | **FAILED** (p = 0.426573) |
| P10 | p(shuffle) ≤ p(cyclic) — D093 direction | **HELD** (0.3876 ≤ 0.4266; width ratio 0.7922) |
| **P11** | **noise control \|mean\| < 0.002 and Type-I ≤ 0.10** | **FAILED** (mean −0.006882, Type-I 0.420) |
| P12 | abstention drop-30 % MAE reduction ≥ 8 % | **HELD** (9.48 %) — but see the level-only column |
| P13 | no conversion to a better minutes level forecast | **HELD** (best +0.001240, p 0.6879) |
| P14 | increment > 0 on `refabs_minutes` | **HELD** (+0.028605, p 0.0194) |
| **P15** | **detection ≥ 0.80 at an injected dR² of ~0.010** | **FAILED** (0.050 iid, 0.025 clustered) |
| P16 | median within-player-season acf1 of block N ≥ 0.20 | **HELD** (0.5654) |

No threshold, seed, arm, draw count or tolerance was revised after a result was seen. Two of the
three failures (P11, P15) are the ones that changed the verdict, which is what preregistering them
was for.

---

## Post-hoc, and labelled as such

Two things were added after seeing the ladder. Neither changes a preregistered threshold.

1. **A clustered power curve** (above), because the preregistered iid injection overstates power
   against a block whose information is cross-sectional (DEFECTS D-2).
2. **A null for the reference-incompleteness claim itself** — dR²(`L4` over `L1`) = **+0.016378**,
   block bootstrap **95 % CI [+0.003825, +0.029789], frac ≤ 0 = 0.0030**. (Its sign-flip p of
   0.0124 is quoted in the artifact but carries the same calibration problem as every other
   sign-flip here and should not be used.) **The reference-incompleteness finding is established on
   this stratum; the non-level increment is not.** That contrast is the screen's result.

---

## What I could not do

- **`entity_swap_null` was not run.** The kit's K2 answer to "does which player-season this row
  belongs to matter" is the swap of whole entity-season series, and since the increment turns out to
  be almost entirely cross-sectional, that is the permutation test this question actually wanted. It
  was not preregistered, so it was not run. It is the single highest-value follow-up.
- **A calibrated null for a many-column dR².** Every sign-flip p in this screen is uncalibrated
  (42 % Type-I on noise). The fix is to score against the noise placebo's own distribution rather
  than against a sign-flip, as `E1_I0054` D-3 concluded; I report the +9.53 sd figure but did not
  build a properly centred test.
- **A second stratum.** Everything here is `A4_CLEAN_DEC`. Whether the reference-incompleteness gap
  survives off-stratum is untested.
- **Anything on 2025/26.** Sealed.

## What I would want checked next

1. Run `entity_swap_null` on block N against `absres_minutes` — the cross-sectional question, with
   the kit's own tool.
2. Re-examine **every other screen in this programme that used a single trailing-level column as its
   reference.** This one lost 89 % of its apparent effect to a level ladder a forecaster could have
   built. D134's ruling 4 rested on the single-column version.
3. Decide whether the `pred_sd` scalar broadcast at `cbs_player_runner_v14.py:313` is worth
   replacing with a per-row dispersion model at all. **This screen's answer is that it is not**:
   even a 51-column variance model produces an interval that is 0.04 % narrower than a per-season
   constant at matched coverage. The gap is real, and closing it appears to be worth nothing.
4. The `refabs_minutes` result (+0.028605, p 0.0194) is the one live thread. It says minutes
   dispersion *is* partly forecastable; it does not say the shipped forecast's errors are.

---

## Discipline and disclosures

- **T1 retrospective baseline.** `_common._impute_by_season` fills from the whole-season median,
  future included. Exposure: 385 of 3,549 rows (10.85 %) on every `x53_*` column, 3 on
  `pl_dnp_frac5`. Primary arms use a strictly-prior expanding median; the maximum absolute
  difference between the two rules over every candidate cell is **0.000000**, because the 385
  unjoined rows are exactly the **postseason** (2023-09-13→10-18, 2024-09-22→10-20) and fall
  strictly after every joined row. Verified on dates, not assumed. **10.85 % of the decision
  stratum is postseason.**
- **T5 / D086.** No substring match selects any column anywhere in this screen. Every block is a
  literal list fixed in the preregistration, and every classification (`pred_sd` constant,
  `pred_cv` level-spanned) is settled on values.
- **T6 vacuous controls.** The permutation machinery was proved to be the identity at offset 0
  (sd exactly 0.0, one distinct value, reproducing the observed statistic to 0.000e+00) and proved
  to move under the real scheme (see the null table above).
- **T8.** Every decision-facing number is stated against a reference facing the same rows, and the
  conversion arms measure skill on the minutes level, not on the error.
- **D100 hindsight.** `s00` decided where to look; its structural claims were re-derived from bytes.
  The P4/P5 anchors and the P6/P8 thresholds were set knowing `E1_I0054`'s published VLEV/VSIG/VALL
  /VSD numbers. Declared in `PREREG.md` §0 before measuring.
- **Anchors.** `VLEV` reproduces the published +0.018378185 to **9.7e-17**; `VSIG` reproduces
  +0.042865714 to **2.9e-16** and its decile ratio 1.908944 to **0.0**; `VSD` reproduces −0.004813.
- **Own defects: nine, in `DEFECTS.md`,** including one that runs in my own favour (my
  preregistered primary rung was not the strongest level rung, so my headline increment is 0.0014
  too large) and one crash whose stderr is preserved rather than overwritten.
