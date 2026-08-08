# E0_I0015 — Points skill decomposition: where does the champion lose its points skill?

**Tier E0 (discovery). Everything here is a LEAD, never a result.** No preregistration, no
bootstrap, no promotion threshold, no registry entry. Nothing in this directory may be cited as
evidence for anything.

Partition: **2021–2024 only**, screened on **2022–2024** (D076 established the 2021 fold is
degenerate: `n_train_rows = 0`, `model_was_fitted = false`). The 2025/26 holdout was never read,
joined, plotted, described or summarised.

---

## 1. The question

D076 (`E0_I0014_residual_heterogeneity`) measured the champion player model's SKILL against a
point-in-time expanding prior-appearance-mean reference, on the pre-existing season-chronological
walk-forward `experiments/cbs_v15_player_oof_v5/attempt_001/`, 13,879 appeared player-games:

| target | skill vs prior-mean reference |
|---|---|
| minutes | **+3.55 %** |
| FGA | +0.12 % |
| points | **−0.22 %** |

Points is the headline betting target. Since `POINTS = MINUTES × POINTS-PER-MINUTE`, the skill must
be leaking somewhere along that chain. This screen finds where.

---

## 2. Step 1 — the three numbers reproduce

| target | model MAE | ref MAE | skill here | D076 published | \|Δ skill\| |
|---|---|---|---|---|---|
| points | 4.1909 | 4.1816 | −0.002222 | −0.0022 | 2.2e−05 |
| minutes | 5.0797 | 5.2669 | +0.035549 | +0.0355 | 4.9e−05 |
| FGA | 2.6376 | 2.6406 | +0.001152 | +0.0012 | 4.8e−05 |

D076 published skill to two decimal places in percent, so an exact match is only possible to ~5e−05
on the fraction. All three land inside that. **REPRODUCED.**

The reference was also rebuilt from scratch in this screen's own code path
(`psd_base.build_references`) without reading D076's `ref_` columns: `max |refX − D076 ref| = 0.0`
for all three targets.

**A minor defect in D076's reference, disclosed.** Its fallback chain ends in
`.fillna(f["y_t"].mean())` — the **whole-sample** mean, which is retrospective. It binds on exactly
**3 of 13,879 rows** (the first games of the earliest season, where the player has no prior
appearance *and* no earlier same-season game exists). Immaterial to every number anywhere, but it is
a retrospective element sitting inside a baseline labelled "prior mean", and this program's rule is
to read the construction rather than the label, so it is reported rather than left implicit.

---

## 3. The answer, in the order it was actually found

### 3.1 Every component has POSITIVE skill. Nothing "goes to zero".

Each component is scored against its own matched point-in-time prior-mean reference. Two reference
variants are reported for every rate, because picking one after seeing the answer would be a place
to cheat: **REF-A** = expanding mean of the player's own prior per-game rate values (the exact
structural analogue of D076's level reference); **REF-B** = `sum(prior numerator)/sum(prior
denominator)`, a better estimator and therefore a **harder** reference.

| component | kind | n | model MAE | ref MAE | skill | p (block) |
|---|---|---|---|---|---|---|
| minutes | level | 13879 | 5.07967 | 5.26691 | **+3.555 %** | 0.0005 |
| FGA | level | 13879 | 2.63757 | 2.64061 | +0.115 % | 0.80 |
| points | level | 13879 | 4.19092 | 4.18163 | **−0.222 %** | 0.55 |
| FGA per minute | rate | 13879 | 0.11034 | 0.11184 (A) | +1.345 % | 0.0005 |
| | | | | 0.11111 (B) | +0.695 % | 0.0075 |
| points per FGA | rate | 12976 | 0.50658 | 0.51759 (A) | +2.127 % | 0.0005 |
| | | | | 0.51182 (B) | +1.024 % | 0.0005 |
| points per minute | rate | 13879 | 0.18174 | 0.18276 (A) | +0.559 % | 0.059 |
| | | | | 0.18350 (B) | +0.959 % | 0.0050 |

Candidate explanation **(a)** "the rate components are genuinely unpredictable" is **partly
rejected** — the model beats a prior-mean rate reference on all three rates. Candidate **(b)** "the
model forecasts rates worse than a naive prior mean" is **rejected outright** — it forecasts every
rate better.

Note also that the champion's −0.22 % points skill is **not distinguishable from zero**: mean paired
|error| difference +0.0093 points, p = 0.55 at the (season, player) block level. The honest phrasing
is "no measurable points skill", not "negative points skill".

### 3.2 The pooled 2×2 — and why its headline reading is WITHDRAWN

`H1 = model minutes × model rate` (identically the champion: `max|H1 − pts__pred_point| = 3.6e−15`),
`H2 = model minutes × naive rate`, `H3 = naive minutes × model rate`, `H4 = naive × naive`. All
scored in points, skill against D076's `ref_pts` on the same rows.

**Pooled (variant A):**

| | model rate | naive rate |
|---|---|---|
| **model minutes** | H1 4.1909 → **−0.222 %** | H2 4.1739 → +0.184 % |
| **naive minutes** | H3 4.1479 → **+0.806 %** | H4 4.1710 → +0.254 % |

`H3 > H1` with p = 0.0005, in every season separately and under both reference variants. I first
read that as *"the model's minutes forecast destroys points value"*.

**That pooled claim is withdrawn.** Stratifying by prior-appearance depth reverses it:

| stratum | n | H1 | H2 | H3 | H4 | H3 − H1 |
|---|---|---|---|---|---|---|
| THIN (<8 prior appearances) | 3213 | **−5.589 %** | −3.961 % | +2.344 % | +0.682 % | +7.93 pts |
| ADEQUATE (≥8) | 10666 | **+1.443 %** | +1.470 % | +0.329 % | +0.121 % | **−1.11 pts** |
| fallback rows only | 1061 | **−18.626 %** | −10.776 % | +2.167 % | +1.960 % | +20.79 pts |
| non-fallback rows | 12818 | **+1.675 %** | +1.314 % | +0.666 % | +0.078 % | **−1.01 pts** |
| POOLED | 13879 | −0.222 % | +0.184 % | +0.806 % | +0.254 % | +1.03 pts |

On 77 % of rows the champion's *own* minutes forecast is what delivers its points skill
(`H1 > H3`, p = 0.0005). The pooled ordering is produced entirely by the 1,061 fallback rows.
**A pooled statement that flips sign on 77 % of its own rows is an aggregation artifact, not a
finding**, and I am recording that I nearly published it.

### 3.3 The single most informative table: depth × volume

Points skill, with n and the block sign-flip p:

| | <14 min | 14–24 min | **≥24 min** |
|---|---|---|---|
| **<3 prior appearances** | — | — | −17.91 % [999, p 0.001] |
| **3–7** | −2.02 % [742, p 0.39] | +4.58 % [590, p 0.003] | +1.91 % [882, p 0.085] |
| **8–19** | +2.80 % [1347, p 0.003] | +2.20 % [1342, p 0.003] | **−0.11 % [2020, p 0.79]** |
| **≥20** | **+7.64 %** [1225, p 0.001] | +3.69 % [1645, p 0.001] | **−0.53 % [3087, p 0.30]** |

Minutes skill on the same cells runs +13.87 % / +12.74 % / **+7.69 %** across the ≥20-appearance
row. Points-per-minute skill on that row runs −0.01 % / −0.51 % / **−0.51 %**.

**This is the answer.** For an established, high-minutes player the model forecasts minutes well
(+7.7 %) and forecasts efficiency slightly *worse* than a running mean (−0.5 %), and the points
forecast lands at −0.5 %. The minutes skill buys nothing because **points error is dominated ~3:1 by
efficiency error**: giving the champion perfect knowledge of the rate while keeping its own minutes
cuts points MAE by **58.5 %**, whereas giving it perfect minutes while keeping its own rate cuts it
by only **18.4 %**.

The champion's points skill is strongly positive exactly where a points market does not care
(low-minutes bench players with deep history, where a running mean is a weak reference because their
minutes are volatile) and zero where it does.

### 3.4 The decision-relevant number, stated alone

Rows with ≥8 prior same-season appearances **and** trailing-5 mean minutes ≥24 — the players whose
points lines actually get bet:

* n = 5,107 (37 % of appeared player-games)
* champion points MAE 5.0098, prior-mean reference 4.9919
* **points skill −0.36 %, p = 0.27** — indistinguishable from zero
* minutes skill on the same rows **+6.14 %**, rate skill **−0.20 %**

### 3.5 The cold-start defect, and D076's own follow-up question answered

D076 asked, verbatim: *"replace the cold-start path with the running mean and see whether Q1 skill
goes to 0 or to +."* It is cheap, so it was answered.

| splice where prior games < | n spliced | % | pooled points MAE | pooled skill | skill on UN-spliced rows | p vs champion |
|---|---|---|---|---|---|---|
| 0 (champion) | 0 | 0.0 | 4.1909 | −0.222 % | −0.222 % | 1.000 |
| **3** | 999 | 7.2 | 4.1248 | **+1.360 %** | +1.492 % | 0.0010 |
| 5 | 1899 | 13.7 | 4.1294 | +1.249 % | +1.470 % | 0.0010 |
| 8 | 3213 | 23.2 | 4.1356 | +1.101 % | +1.443 % | 0.0010 |
| 15 | 6060 | 43.7 | 4.1378 | +1.048 % | +1.853 % | 0.0010 |

**It is a MODEL effect, not a data effect.** The estimator's cold-start path is worse than the
trivial fallback it is meant to improve on. Refusing to use it below ~3 prior appearances — touching
7.2 % of rows and adding *no information whatsoever* — moves pooled points skill from −0.22 % to
+1.36 %.

**Caveat, stated in the run log and repeated here:** splicing the reference into the model on a row
set makes the spliced forecast *equal* to the reference there, so skill on those rows is 0 **by
construction**. The evidence is the pooled movement and the untouched rows, not the spliced ones.

### 3.6 Is the ceiling intrinsic? Partly — and it is low, but it is not the whole story.

Oracle ladder (the oracles **deliberately read the future**; they are never used as a skill
reference and exist only to bound what is forecastable at all). On all 13,879 rows:

| forecast | kind | MAE | R² as-is |
|---|---|---|---|
| prior-mean reference | honest | 4.1816 | 0.4740 |
| **champion** | honest | 4.1909 | 0.4694 |
| model minutes × SEASON-MEAN rate | ORACLE | 3.9603 | 0.5323 |
| SEASON-MEAN points | ORACLE | 3.8478 | 0.5561 |
| ACTUAL minutes × model rate | ORACLE | 3.4180 | 0.6223 |
| ACTUAL minutes × SEASON-MEAN rate | ORACLE | 3.1681 | 0.6770 |
| within-player-season OLS on ACTUAL minutes | ORACLE | 3.0960 | 0.6897 |

On the STABLE subset (a **pre-game** rule: ≥15 prior appearances and trailing-5 mean minutes ≥24,
n = 3903), plain unweighted R² (D069):

| quantity | R² |
|---|---|
| oracle: player-season fixed effects alone | 0.3844 |
| oracle-on-player **+ honest model minutes forecast** | 0.3844 |
| oracle-on-player + ACTUAL minutes played (unreachable) | 0.4868 |
| honest: champion as-is | 0.3085 |
| honest: prior-mean reference as-is | 0.3021 |

**Verdict: the ceiling is low but it is not the explanation.** 51.3 % of points variance is
irreducible even to an oracle that knows the player's season-long identity *and* the actual minutes
played. But a **pre-game-reachable** oracle — one that knows each player's true season scoring level
while forecasting minutes exactly as well as the champion already does — reaches R² 0.3844 where the
champion sits at 0.3085. So there is ≈ **0.076 R² (≈ 5.5 % of MAE pooled) of genuinely reachable
points headroom, and the champion has captured none of it relative to a running mean.**

Both halves are true, and "points is mostly unforecastable" alone would be too generous to the
model. The honest statement is: *points is mostly noise, and separately the model is not near the
reachable part of the floor.*

**Method assumptions, stated plainly.** (i) A player's true scoring rate is roughly constant within
a season, so a season-mean rate stands in for perfect knowledge of the player. (ii) The
minutes-to-points relationship is roughly linear within a player-season. (iii) The STABLE subset is
selected from pre-game observables only, so the ceiling quoted on it is one a forecaster could
actually target. Violations of (i)/(ii) make the oracle **weaker**, so the estimated ceiling is
conservative — the true ceiling is at least this good. **This is an estimate, not a theorem.**

### 3.7 Mechanism checks that did NOT pan out, reported anyway

* **The blowout / garbage-time story is wrong in sign.** The realised within-player-season
  correlation between minutes and points-per-minute is **positive** (+0.150 within, +0.351 pooled).
  Within a player-season, the games she plays more are the games she scores at a higher rate.
  Candidate explanation (d) as originally worded is rejected in sign.
* **Over-dispersion is not the diagnosis.** sd(champion) = 5.772, sd(reference) = 5.794,
  sd(outcome) = 7.580. The champion is *less* dispersed than the reference it fails to beat.
* **Shrinking the champion toward the reference does help** (λ = 0.5 → skill +1.14 %), but that is
  an **ensemble** gain, not a dispersion fix: the two forecasts' errors are only 0.941 correlated,
  so averaging two partly-independent forecasts beats either. The champion's information is real; it
  is simply not incremental to a running mean as a point forecast.

### 3.8 Step 5 — does abstention help the RATE components? No.

55 pre-game candidates × 5 dependents × 2 directions = **550 cells**, skill gain at 75 % coverage,
400 permutation draws shared across every cell so the max-stat family-wise correction is valid.

| dependent | cells clearing family-wise p < 0.05 |
|---|---|
| minutes level | **13 / 110** |
| points level | **0 / 110** |
| points-per-minute (ref A) | **0 / 110** |
| points-per-minute (ref B) | **0 / 110** |
| points-per-FGA (ref A) | **0 / 110** |

Observed max skill gain across the whole screen +0.0552 (`pl_minutes_prior` → minutes) against a
correct-level max-stat null whose own maximum over 400 draws is +0.0246. The best *rate* cell is
+0.0081 — family-wise p = 1.00.

**D076's asymmetry is confirmed and extended.** Abstention works on minutes because minutes is
predictable; it fails on points *and on every rate component* because nothing observable pre-game
predicts differential skill on efficiency. This was worth establishing rather than assuming.

`pl_games_prior → points-per-FGA` looks tempting in isolation (skill +2.13 % → +2.94 % at 75 %
coverage → +10.71 % at 10 %) but does not clear the family and is reported as not clearing it.

---

## 4. TIME-WINDOW TABLE — every constructed quantity and exactly what window it reads

Construction rule for every reference: the frame is sorted `(season, player_id, game_date)`, then
`.shift(1)` is applied **before** any `expanding()` or `cumsum()`. Nothing full-season, nothing
leave-one-out, nothing leave-one-season-out.

| quantity | group | window it reads | pre-game? |
|---|---|---|---|
| `r_ppm`, `r_fpm`, `r_ppf` | — | the target game's own box score. **OUTCOMES, not features** — they are what the rate references and rate forecasts are scored against | no, by design |
| `mdl_ppm`, `mdl_fpm`, `mdl_ppf` | — | ratios of the champion's own already-emitted point forecasts for this game; pre-game by construction | **yes** |
| `refX_pts` / `refX_minutes` / `refX_fga` | (season, player) | expanding mean of the player's own appearances **strictly before** this date; independent rebuild of D076's `ref_*` | **yes** |
| `refA_ppm` / `refA_fpm` / `refA_ppf` | (season, player) | expanding mean of the player's own **prior** per-game rate values | **yes** |
| `refB_ppm` / `refB_fpm` / `refB_ppf` | (season, player) | `sum(prior numerator) / sum(prior denominator)` over strictly prior appearances | **yes** |
| cold fallback for all of the above | (season) | expanding league mean over games **strictly earlier in the same season** | **yes** |
| final fallback (3 rows only) | — | whole-sample mean — **RETROSPECTIVE**, inherited from D076, binds on 3 of 13,879 rows | **no** — disclosed in §2 |
| `pts__pred_width`, `minutes__pred_width`, `fga__pred_width`, `pts__pred_iqr` | — | `q95 − q05` (and `q75 − q25`) of the model's own emitted quantiles for this game | **yes** |
| `rate_pred_width`, `rate_pred_cv` | — | ratios of the model's own emitted quantities for this game | **yes** |
| all 40 `pl_*` / `tm_*` / `opp_*` candidates | various | inherited unchanged from D076's frame; see D076's own TIME-WINDOW TABLE, which was read and not re-derived | **yes** |
| `_o_pts_mean`, `_o_ppm_mean`, `_o_ols_min` (ORACLES) | (season, player) | the player's **whole season, including this game** | **NO — deliberately retrospective.** Used ONLY as a ceiling bound in §3.6. Never a skill reference, never a candidate, never a feature. |
| `_loo_pts` (leak-probe control) | (season, player) | the player's whole season | **NO — deliberately retrospective.** Exists only to confirm the leak probe fires. |
| STABLE subset selector (`pl_games_prior`, `pl_min_mean5`) | (season, player) | strictly prior appearances only | **yes** — so the ceiling quoted on that subset is targetable |

**Leak probe run on the reference, because names lie.** `screenkit.future_leakage_probe` flagged the
deliberately-retrospective full-season mean (corr with the player's own strictly-after-date future
+0.9480 vs the prior mean's +0.8453, ΔR² 0.1954 in predicting that future) and did **not** flag the
prior-mean reference in the reverse contrast (ΔR² 0.0112). The rate references A and B were probed
against each other; neither flagged (ΔR² 0.0027 and 0.0002). The probe is a positive detector, not a
certificate, so the construction is stated above as well.

---

## 5. Nulls

* **Paired contrasts** (H1–H4, champion vs reference, every stratified contrast): **(season,
  player_id) block sign-flip** permutation, 2000 draws, seed 20260807, two-sided. The paired
  difference `d_i = |e_A,i| − |e_B,i|` has its sign flipped for a *whole player-season block* at a
  time. Flipping per row would treat 13,879 correlated rows as independent — exactly the
  anticonservative row-level null this program has found wrong six times.
* **Abstention screen**: block permutation of **already-computed** candidate values, 400 draws,
  seed 20260807, shared across every cell so the max-stat family-wise correction is valid. Scheme
  chosen per candidate by where its variance actually lives (`var_share_between_player_season > 0.5`
  → BETWEEN-block reassignment, 18 candidates; else WITHIN-block shuffle, 37 candidates), mirroring
  D076. Nothing is recomputed inside a draw.
* **Inflation factor, per cell:** median 0.95, 5th–95th pct 0.69–1.32, range 0.26–2.06, above 1 in
  only 32 % of cells. Read honestly: the naive row-level null is **not uniformly narrower** here — it
  is simply the *wrong* null, in whichever direction. Same honest tail D076 reported.
* **Inflation factor, family-wise — this is the one that matters:** the correct-level max-stat null
  reaches **+0.0246** while the naive row-level max-stat null reaches only **+0.0113**, i.e. **2.2×
  too narrow at the family level.** Judged against the naive null, every rate cell in the top 15
  would have "passed". Sixth-plus confirmation in this program.
* **Cluster-robust SEs were NOT used.** This program has found them unreliable in both directions
  three separate times; they are not a substitute.

### No-op placebo (`screenkit.noop_placebo`), observed sd reported honestly

Statistic: points skill vs the D076 prior-mean reference. 200 draws each.

| control | observed sd | max\|draw − real\| | distinct draws | verdict |
|---|---|---|---|---|
| literal identity | **0.000e+00** | 0.000e+00 | 1 | CONFIRMED NO-OP (as intended) |
| **defective**: permute the block key, then compute a statistic that never consults the shuffled label | **0.000e+00** | 0.000e+00 | 1 | **CONFIRMED NO-OP** — the known signature, run on purpose |
| genuine: shuffle which row receives which already-computed forecast, within season | **8.867e−03** | 8.103e−01 | 200 | NOT a no-op — the transform really moves the statistic |

Both no-op cases came back at exactly 0.0, not the ~7e−18 the kit's docstring warns is possible.
Reported as measured.

### R² convention (D069) — and a name collision worth flagging

Plain unweighted OLS R², SST about the **unweighted** mean. No weighting anywhere in this screen.
The defective `sst = sum((sqrt(w)*y − mean(sqrt(w)*y))**2)` form does not appear.

**But `r2_plain` means two different things in this repo.** `screenkit.r2_plain(y, X)` treats its
second argument as **regressors** and fits an intercept and slope by OLS. D076's
`rh_base.r2_plain(y, yhat)` is `1 − SSE/SST` with SSE about the **supplied forecast**. Same name,
different semantics. Measured on the same frame:

| target | forecast as-is (D076's semantics) | `screenkit.r2_plain` (refits) | D076 published |
|---|---|---|---|
| points | **0.4694** | 0.4747 | 0.4694 |
| minutes | **0.6194** | 0.6218 | 0.6194 |
| FGA | **0.5893** | 0.5915 | 0.5893 |

Both are reported in `FINDINGS.json`, labelled. The kit's version is *documented* correctly — its
signature says "regressors" — but a screen reproducing a frozen published R² with it will silently
get the higher number. See §7.

---

## 6. Partition and manifest enforcement

Partition is enforced by `screenkit.assert_partition`, a **value test** on parsed dates and
season-valued columns. **No regex or byte scan of file contents was used as a partition check
anywhere in this screen.** It passed, with `season` values `[2022, 2023, 2024]` and `gdate` years
`[2022, 2023, 2024]`, and correctly **skipped** two columns whose *names* look season-like but whose
*values* are not seasons (`pl_prior_season_games`, values 0–132; `tm_season_progress`, values
0.025–1.275) — the trap-3 regression behaving as designed.

Manifests, checked with `screenkit.check_manifest` at call time:

| artifact | `asof_granularity` | verdict |
|---|---|---|
| `data/masters/master_player.parquet` | `row` | USABLE_IF_FILTERED |
| `experiments/prediction_contract_v4/player_game.parquet` | `row` | USABLE_IF_FILTERED |
| `cbs_v15_player_oof_v5/.../predictions__*__{2022,2023,2024}.parquet` (9 files) | `artifact` | **USED — see below** |
| `data/w1_truth/player_game_availability.csv` | `artifact`, bound 2026 | **NOT OPENED** |
| `data/w1_truth/roster_asof.csv` | `artifact`, bound 2026 | **NOT OPENED** |
| `experiments/minutes_baselines/test_predictions.csv` | **no sibling manifest** | **UNVERIFIABLE → NOT OPENED** |

**The artifact-granular OOF reading is inherited from D076 and re-verified file by file.** The
general rule is that an `artifact`-granular file is unusable and filtering does not help, because a
2021 row may embed 2026 information. That rule is about *mixed-bound* files. These are per-season
files, and each one's own `fit_through_season` equals its own season (2022→2022, 2023→2023,
2024→2024), so the whole artifact sits inside the exploration partition and no filtering is being
relied on. Every one of the nine was checked individually and anything bound past 2024 would have
aborted the run. **If a coordinator rejects that reading, D076 collapses and this screen collapses
with it.**

---

## 7. My experience using `_screen_kit` — I am its first real user

I ran `python TESTS.py` first: **49/49 assertions pass, exit code 0**, ~2.5 min, in this environment.

The kit did real work. `assert_partition` correctly skipped two name-only season columns without my
having to think about it. `check_manifest` gave the right verdict on all fourteen artifacts
including the missing-manifest UNVERIFIABLE case. `future_leakage_probe` fired on my deliberately
retrospective control and stayed quiet on the clean one. `noop_placebo` correctly identified both
no-ops and correctly cleared the genuine shuffle. The README's four-trap framing is the most useful
part of the whole thing and I would not change it.

Four problems, in descending order of how much they would cost the next user.

### 7.1 **DEFECT — `detect_grouping_level` crashes on any boolean feature.** Reproduced in `KIT_BUG_REPRO.py`.

```
TypeError: numpy boolean subtract, the `-` operator, is not supported ...
```

In `_constant_within` (screenkit.py ~line 302), `pd.api.types.is_numeric_dtype(s)` returns **True**
for `bool`, so the numeric branch runs `g.transform("max") - g.transform("min")` on numpy bools,
which raises. `permutation_null` inherits the same failure through the same helper whenever it is
given a boolean feature at a non-row level.

This matters more than it sounds. Binary pre-game flags are among the most common candidates in this
program, and **two of D076's four surviving leads were the boolean `is_fallback` and
`fallback_level`.** A new screen following the kit's own documented quick-start order —
`check_manifest`, `assert_partition`, `detect_grouping_level`, `permutation_null` — crashes on the
third call the moment a boolean candidate is reached. My run died on
`pts__is_fallback`, `pts__is_cold_start`, `minutes__is_fallback`, `fga__is_fallback`.

`TESTS.py` passes 49/49 because **it never exercises a boolean feature.** A shared library that is
subtly wrong is worse than copy-paste, and this is the cheap version of that: not wrong, just
absent, and the test suite does not know it.

*Suggested fix, NOT applied* (the kit is outside this screen's write scope and was not touched):
branch on `pd.api.types.is_bool_dtype(s)` **before** the numeric branch, or cast
`s = s.astype(float)` when the dtype is bool; then add a boolean case to `TESTS.py`. My workaround
was caller-side casting.

### 7.2 **GAP — the kit has no WITHIN-block permutation scheme, and `detect_grouping_level` will happily recommend the anticonservative null for a row-varying feature.**

For a candidate that varies row by row (34 of my 55 did), `detect_grouping_level` recommends `row` —
correct as to *where the feature varies*, but `row` is precisely the null this program has found
wrong six times, because **the OUTCOME is clustered by player-season even when the feature is not.**
The kit's own docstring admits it ("If your outcome is clustered at a coarser level than the
feature, that is a separate (and also real) problem this does not detect"), but the function returns
a field literally named `recommended_permutation_level`, and a first-time user who trusts the
recommendation gets the wrong null with the kit's authority behind it. The docstring caveat is doing
a lot of load-bearing work that the return value's name undoes.

D076 solved this by adding a **within-block** null (shuffle values inside each `(season, player)`
block so the block's *level* survives and only the game-to-game alignment dies) and choosing between
the two schemes by `var_share_between_blocks`. **The kit has neither the within-block scheme nor the
variance-share helper**, so I reimplemented both from `rh_base` — exactly the duplication the kit
exists to prevent. `_permute_group_values` is a *between*-block scheme that reassigns one
representative value per group; with `allow_nonconstant=True` it would have silently discarded all
within-group variation on 37 of my candidates.

Concretely I would suggest: a `within_block_null`, a `var_share_between` helper, and making
`detect_grouping_level` return something like `outcome_clustering_not_checked: True` alongside the
recommendation.

### 7.3 **NAME COLLISION — `r2_plain` means one thing in the kit and a different thing in the frozen screens.**

`screenkit.r2_plain(y, X)` fits an OLS of `y` on `X`. D076's `rh_base.r2_plain(y, yhat)` is
`1 − SSE/SST` about the supplied forecast. I passed a forecast to the kit's version, got 0.4747, and
spent time wondering why D076's published 0.4694 had "not reproduced" — it had; I had computed a
different quantity. The kit's provenance table says `r2_plain` was adapted from
`E1_I0013/e1_lib.py::r2()`, which invites exactly this substitution.

A screen scoring a *forecast* rather than *regressors* is the common case in this program, and the
kit has no function for it. I added `psd_base.r2_forecast` locally. A kit-level
`r2_of_forecast(y, yhat)` with a docstring pointing at the difference would have saved me the
detour, and would stop the next person publishing a silently inflated R².

### 7.4 **GAP — no paired-comparison machinery.**

The decisive statistic in this screen is a *paired* contrast of two forecasts' absolute errors on
the same rows. That is not a feature-permutation problem and the kit does not cover it. I wrote a
`(season, player)` block sign-flip test (`psd_base.block_signflip_test`) and have flagged it
throughout as **not** a kit function. Forecast-vs-forecast comparison seems common enough in this
program to belong in a shared kit, with the same "refuses to guess the level" discipline
`permutation_null` already has.

### 7.5 Smaller notes

* `SCREEN_TEMPLATE.py` is genuinely useful — running the trap-1 demo on synthetic data before
  touching real data is the right order and I copied its structure.
* `noop_placebo` returning the observed sd rather than a boolean is the right call, and both my
  no-op cases came back at exactly 0.0 rather than the ~7e−18 the docstring warns about.
* `permutation_null` refusing to default to rows is good design and I would keep it even though
  §7.2 means the recommendation feeding it can still be wrong.

---

## 8. Where I could have cheated — and whether I chose before or after seeing the result

Chosen **before** seeing any result, and written into `psd_base.py`'s module docstring before the
first number was computed:

* The rate definitions (`ppm = pts/min`, `fpm = fga/min`, `ppf = pts/fga`), and that the model's
  implied rate is the **ratio of its own already-emitted point forecasts** — nothing refitted, the
  champion never retrained.
* **Both** reference variants (REF-A mean-of-prior-ratios, REF-B ratio-of-prior-sums), specifically
  so that I could not pick the flattering one afterwards. Every rate result reports both.
* The skill metric (`1 − MAE_model/MAE_ref`, reference facing the same rows), the seed (20260807,
  D076's, for comparability), the coverage grid, the 75 % headline coverage, and the draw counts.
* The 55-candidate list for Step 5, fixed before the first abstention curve ran. No candidate was
  added or dropped after seeing its effect.
* The STABLE subset rule, defined from **pre-game observables only** precisely so the ceiling quoted
  on it would be targetable rather than an oracle selection.
* Excluding 2021 (inherited from D076's fold receipts).

Chosen **after** seeing results — declared, because each is a place I could have flattered the
screen:

* **The whole of §3.2's withdrawal.** I computed the pooled 2×2, got a clean, dramatic, "H3 beats
  H1, p = 0.0005, every season, both variants" result, and drafted it as the headline. Only the
  subset sensitivity check — which I had written into `s04` before seeing the 2×2, but which ran
  after — reversed it. I then wrote `s05` and `s06`, which were **not** planned, to resolve it. The
  earlier reading is preserved in `FINDINGS.json` under
  `step3_hybrid_2x2.pooled_verdict_WITHDRAWN` rather than deleted. **This is the single most
  important disclosure in this file**: the dramatic pooled finding was wrong, and it was wrong in
  the direction that would have made the best return to the coordinator.
* **The depth × volume table** (§3.3) was built after the stratification surprised me. It is the
  most informative table here and it is entirely post-hoc.
* **The cold-start splice thresholds** (0/3/5/8/10/15/20) were swept, and `<3` is the best cell. I
  am reporting the whole sweep rather than only the winner, and the winner is only 0.26 points of
  skill above the `<8` cell, so it is not a knife-edge — but it is a swept maximum and should be
  read as one.
* **The blend weight** in §3.7 (λ = 0.55 optimal) was swept **in-sample** after seeing the skill
  numbers. The round λ = 0.50 gives +1.141 % against the optimum's +1.149 %, so it is not
  knife-edged, but no blend weight here is out-of-sample validated and none should be deployed on
  this evidence.
* **Reframing (d) as "rejected in sign".** I expected the blowout/garbage-time story and went
  looking for a negative minutes–efficiency correlation. It came out positive. I am reporting the
  rejection rather than quietly dropping the hypothesis, and I have left the original wording of the
  candidate in `FINDINGS.json` next to its verdict.

Places I could have cheated and consciously did not:

* I did not open `player_game_availability.csv` or `roster_asof.csv` (artifact-granular, bound 2026)
  or `minutes_baselines/test_predictions.csv` (no manifest at all). An availability file is the
  single easiest way to make a minutes/points screen look good.
* I did not use any oracle quantity as a skill reference. Every oracle is labelled `ORACLE` in the
  ladder, in `FINDINGS.json`, and in the time-window table, and each appears only inside the ceiling
  estimate.
* I did not report raw MAE reduction as evidence anywhere. D076's `pts__pred_point` lesson — a 9.9 %
  MAE cut worth +0.00007 of skill — is why every number here is skill against a reference facing the
  same rows, including inside the abstention screen where the reference is recomputed at every
  coverage.
* I did not report only per-candidate p-values in Step 5. Judged per-cell, dozens of rate cells
  "pass"; judged family-wise, **zero** do, and that is the number in the table.
* I did not quietly work around the screen-kit boolean crash. It is reproduced in
  `KIT_BUG_REPRO.py`, described in §7.1, and the workaround is labelled as a caller-side patch
  rather than a fix. The kit was **not modified**.
* I did not touch `E1_I0004_fga_forecast/`, `MEASURE_F1_m13_fitpool/` or `MANIFEST_REMEDIATION/`,
  and I did not write anything to `registry.jsonl`, `DECISION_LEDGER.jsonl`, `GRAPH_EVENTS.jsonl` or
  `idea_log.jsonl`. `E0_I0014_residual_heterogeneity/` was read and never written to.

**One further caveat on the whole screen.** Every number here rests on D076's reading that the
per-season `artifact`-granular OOF files are usable because each is bound at its own season. That
reading is restated in §6 rather than assumed. If it is wrong, this screen is void, not merely
weakened.

---

## 9. What a follow-up should ask

1. **Fix the cold-start path.** The largest correctable defect found: 999 rows at −17.9 % points
   skill and 1,061 fallback rows at −18.6 % points / −34.1 % minutes. The model emits the flag
   itself, so gating on it costs nothing. Confirm out-of-sample before anything ships.
2. **The efficiency ceiling on established players is the real question for points betting.** On the
   5,107 decision-relevant rows the champion is at −0.36 % (p = 0.27) with +6.1 % minutes skill and
   −0.2 % rate skill. Either find a pre-game efficiency signal — this screen found none among 55
   candidates, family-wise — or accept the ceiling and redirect to the conditional-edge and
   abstention work that *is* paying off on minutes.
3. **Does the +7.6 % points skill on deep-history LOW-minutes players survive out of sample?** It is
   the largest honest positive in the screen and it is in the least commercially interesting corner.
   Worth knowing whether it is real or a weak-reference artifact.
4. **Is the ensemble gain real?** The champion's and the reference's errors are only 0.941
   correlated. If that survives out-of-sample, a blend is nearly free — but every weight here is
   in-sample.
5. **The rebound and assist gap remains open**, exactly as D076 left it. The v15 arm emits no
   forecast for either.
