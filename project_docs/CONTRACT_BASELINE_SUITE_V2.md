# `contract_baseline_suite_v2` — frozen executable specification (definition only)

*Registered 2026-08-01, before any output. **Nothing in this document has been computed.** No
prediction, fitted parameter, accuracy figure, coverage score or prediction file exists for this
suite, and none was inspected while writing it. The registry record is append-only and carries
`computed_nothing: true`.*

**Supersedes `contract_baseline_suite_v1`.** v1's registry record is **not mutated** — it stays
byte-identical, as an append-only registry requires. v1 was a genuine no-output freeze, but the
supervisory review of `db9f011` established that it was **frozen without being executable**: five
rules it referred to were named but never stated, so two engineers reading v1 could not produce
the same numbers. v2 states them. Where v2 changes a *decision* rather than filling a gap, the
change is a supervisory ruling and is marked **RULING**.

Everything in §1 is carried from v1 unchanged. §2 onward is where v2 differs.

---

## 0. What v2 fixes

| # | v1 defect | v2 |
|---|---|---|
| 1 | `p_active` "same model class as Stage A" — no feature vector, standardization, λ grid, tie-break, minimum-history or low-data rule | §3, fully enumerated |
| 2 | "a frozen deterministic constant declared here" — but no constant was declared | §9, complete numeric point/sd/quantile table |
| 3 | "training-fold residuals" — ambiguous between in-sample and out-of-sample | §8, **chronological inner-OOF (prequential) only**, with estimator, minimum sample, dof, interpolation, pooling level and fallback |
| 4 | promoted team centers reused with no fold-honest refitting rule | §7, refit per outer fold; the fixed 2021-2023 fit becomes a named legacy sensitivity |
| 5 | claimed points α = 0.30 "was tuned on 2021-2023" | §6 — **false**; corrected. That provenance belongs to *minutes*. `props_edge.py:203` declares `ALPHA = 0.30  # registered frozen family` |

And the three open questions v1 escalated are ruled on: §5 **RULING 1** (estimator family),
§5 **RULING 2** (α grid), §2 **RULING 3** (fold-honest α selection).

---

## 1. Common contract layer — carried from v1 unchanged

| element | frozen value | source |
|---|---|---|
| contract | `player_game_contract/2` | `experiments/prediction_contract_v2/contract.json` |
| rows — player | **35,615** candidates, 1,458 candidate games | `contract.json` `accounting` |
| rows — team | **2,990** team-games | `contract.json` `accounting` |
| roster lookback | 5 games, strictly prior | `contract.json` |
| folds | `fold_id = "season:<YYYY>"`, `train_boundary = "seasons < <YYYY>"` | `prediction_contract_v2.py:497-499, 506` |
| quantiles | 0.05, 0.25, 0.50, 0.75, 0.95 | `prediction_contract_v2.py:109` |
| clustering | `game_date` | `contract.json` |
| validator | `validate_predictions()` — fail-closed, per target, before anything is scored | `prediction_contract_v2.py:334-400` |

Cutoff classes, never merged: `exact_tip_T-90m` (407 games / 814 tg / 10,257 pg) and
`date_only_prior_day_cutoff` (1,088 games / 2,176 tg / 25,358 pg). Exact tips exist only in 2025
and 2026; **2021-2024 have zero certifiable exact tips.**

Fold sizes: 2021 4,850 pg / 418 tg · 2022 5,561 / 478 · 2023 6,145 / 520 · 2024 6,094 / 524 ·
2025 7,438 / 620 · 2026 5,527 / 430 — total 35,615 / 2,990.

Prediction obligation is 35,615 for every player target (2,990 for team) and is **never** combined
with the scoring mask (27,349 scoreable for the three conditional player targets). Every required
row is predicted or carries an explicit `exclusion_reason`; `prediction_coverage` and
`scoreable_coverage` are reported separately. The standing exclusion audit — cross-tabulate every
excluded row by `in_target_box` and `appeared`, and void the run if exclusion predicts
non-appearance — is carried forward unchanged.

Per-row provenance: `row_uid`, `target_key`, `arm_id`, `component_id`, `fold_id`,
`forecast_cutoff`, `pred_point`, `pred_sd`, `pred_q05..q95`, `is_fallback`, `is_cold_start`,
`fallback_level`, `n_prior_games`, `alpha_selected`, `lambda_selected`, `resid_pool_n`,
`feature_asof`, `model_hash`, `config_hash`, `data_snapshot_hash`, `exclusion_reason`.
`feature_asof < forecast_cutoff` **strictly**.

---

## 2. The fold-honesty rule that governs every hyperparameter — **RULING 3**

> Every hyperparameter that is **selected** rather than **declared** must be selected inside the
> outer fold's own training window, by chronological inner validation, using only outcomes that
> precede the validation segment. No hyperparameter may be carried in from a tuning run whose
> validation outcomes lie in a season this suite predicts.

**Inner split construction — frozen.** `evalharness.splits.inner_tuning_splits(df, outer,
date_col="game_date", n_folds=3)`. The outer training window's unique game dates are cut into
**4 contiguous chronological segments**; inner fold *i* trains on segments `[0..i]` and validates
on segment `i+1` (expanding walk-forward, 3 inner folds). The function raises `LeakageError` if
any candidate row falls outside the outer training window, so tuning on test dates is
unrepresentable rather than merely discouraged.

**Selection loss.** Brier for `p_active`; MAE for every conditional-mean target. Mean over usable
inner folds.

**Tie-break — frozen now, before any curve is seen.** The grid is evaluated in **ascending**
order and the **first** minimum wins, i.e. **ties go to the smallest λ / smallest α** (the more
regularised, more heavily smoothed choice). This is `DataFrame.idxmin()`'s first-occurrence
semantics made explicit rather than incidental.

**Low-data rule — frozen.** An inner validation segment is *usable* if it has **>= 200 rows**
(**>= 30 team-games** for team targets) and, for `p_active`, **both classes present**. If fewer
than **2** usable inner folds exist — including the case where the outer training window has
fewer than 4 distinct game dates, so the splits cannot be built at all — **no tuning occurs** and
the declared defaults are used: **λ = 1.0**, **α = 0.10**. Both are grid interior points declared
here a priori, not chosen from any curve. Rows so predicted carry `alpha_selected` /
`lambda_selected` set to the default and are flagged in the run report.

**Legacy sensitivities.** Fixed-hyperparameter variants of the components are retained as named
comparators (§4, §6, §7) because they are what the committed artifacts actually did. They are
**reported, never promoted**, and are **ineligible for meta-weight or council-weight fitting on
any fold whose predicted season's outcomes influenced their selection**. The per-component
contamination windows are stated where each legacy variant is defined.

---

## 3. `p_active` — `cbs2_pactive_logistic_histonly`

Predicted for **all 35,615** candidate rows. There is **no minimum-history requirement**; see the
zero-history defaults below.

### 3.1 Feature vector — exactly 14, history-only

Regime **A**. This is `minutes_twostage.py:122-130`'s `STAGE_A_FEATURES` **minus the five
regime-B features that read the injury-history archive**:

```
 1  p_plays_prior                  9  prev_dnp_inj
 2  min_ewma                      10  prev_dnp_nwt
 3  started_last                  11  returning_flag
 4  start_share_l5                12  player_gp_season
 5  played_last_team_game         13  team_gp_season
 6  played_share_l10_team_games   14  prev_dnp_cd
 7  days_since_last_appearance
 8  games_missed_streak
```

**Excluded (regime B, archive-dependent):** `miss_inj_l21`, `miss_other_l21`, `roster_move_l14`,
`suspension_l30`, `waived_since_last_game`. **No W1 news input.** Adding either changes the regime
label and requires a new registration.

Caps carried from the source module: `days_since_last_appearance` capped at **45.0**
(`DAYS_CAP`), `games_missed_streak` capped at **20.0** (`MISS_CAP`).

All history features are shifted strictly prior and computed within `(player_id, season)`.

### 3.2 Zero-history defaults — declared, not imputed from the predicted season

A candidate with no prior same-season appearance at the cutoff gets:

| feature | value |
|---|---|
| `p_plays_prior` | the **training-fold** base rate of `played_flag` over training candidate rows |
| `min_ewma` | 0.0 |
| `started_last`, `played_last_team_game`, `returning_flag`, `prev_dnp_cd`, `prev_dnp_inj`, `prev_dnp_nwt` | 0 |
| `start_share_l5`, `played_share_l10_team_games` | 0.0 |
| `days_since_last_appearance` | 45.0 (`DAYS_CAP`) |
| `games_missed_streak` | 0.0 |
| `player_gp_season` | 0 |
| `team_gp_season` | the true team games played (known pregame) |

Every such row is flagged `is_cold_start = True`. **No feature is left NaN and no row is dropped**
— that is the defect that sank `arm_incumbent`.

### 3.3 Standardization — frozen

`minutes_twostage.Standardizer`: column mean and standard deviation with **`ddof = 0`**, computed
**on the fitting rows only**; columns with `std <= 1e-12` are **dropped** (recorded in
`dropped_features`); the identical mean/std are applied to validation and test rows. The
standardizer is **refit at every fit** — once per inner fold during tuning, once per outer fold at
final fit. Never fit on pooled train+test.

### 3.4 Model — frozen

L2 logistic regression by IRLS (`minutes_twostage.logistic_fit`):

- intercept column prepended and **left unpenalised** (`pen[0,0] = 0`);
- intercept initialised to `log(ȳ / (1 - ȳ))` on the training rows, with `ȳ` clipped to `>= 1e-6`;
- `max_iter = 100`; convergence when `max |step| < 1e-9`;
- linear predictor clipped to `[-30, 30]` before the logistic transform, at fit and at predict.

### 3.5 λ selection

Grid — `[round(x, 6) for x in np.logspace(-2, 4, 13)]`, i.e. exactly:

```
0.01, 0.031623, 0.1, 0.316228, 1.0, 3.162278, 10.0,
31.622777, 100.0, 316.227766, 1000.0, 3162.27766, 10000.0
```

Selected **per outer fold** by mean **Brier** score over usable inner folds (§2). Ties → smallest
λ. Low-data → λ = 1.0.

### 3.6 Uncertainty and the comparator

`pred_sd = null` by contract — for a probability the point estimate *is* the distribution.
Calibration is scored; §8's residual machinery does not apply.

The deterministic latest-designation-Out exclusion rule is registered separately as
**`cbs2_pactive_rulegate_comparator`**. It is a binary rule with no uncertainty, reported
alongside and **never relabelled as a probability**, never averaged with one.

---

## 4. `e_minutes_given_active` — `cbs2_eminutes_ewma_tuned`

Center: shifted within-`(player, season)` EWMA of minutes —
`features.common.sew(P, minutes, α)` = `groupby(player, season).ewm(alpha=α, adjust=True).mean()`
then `.shift(1)`. `adjust=True` is the house convention and is part of the freeze.

**α is selected per outer fold** from the §5.2 grid by inner-fold MAE (§2). Ties → smallest α.

**Legacy sensitivity — `cbs2_eminutes_ewma_a030_legacy`.** α = 0.30 fixed, the promoted value from
`minutes_ewma_vs_carryforward_v1` (`verdict: PASS`, `promote: true`; `alpha_tuning_curve.csv`
argmin `mean_val_mae` 4.755807 at 0.30), live in production as `MINUTES_ALPHA`
(`daily_forecast.py:112`). That tuning validated on **2021-2023** outcomes. **Contamination
window: folds `season:2021`, `season:2022`, `season:2023`.** On those folds the legacy variant is
reported as a sensitivity only and is ineligible for any weight fit. On `season:2024` onward it is
fold-honest.

---

## 5. `attempts_usage` — `cbs2_attempts_ratio_ewma_x_minutes` — **NEW COMPOSITION**

### 5.1 Estimator family — **RULING 1**

v1 froze the *instructed* form (shifted EWMA of the FGA/36 rate) and flagged that the artifact it
cited had actually selected a different estimator. The ruling adopts **the artifact's own
selection**:

```
ratio_ewma(α) = shift_ps( EWMA(FGA, α) / EWMA(minutes, α) ) * 36
```

`features.common.sratio_ew(P, fga, minutes, α) * 36.0` — a **shifted ratio-of-EWMAs**, not an EWMA
of a ratio. A zero EWMA denominator becomes NaN and routes the row to the §10 cold-start level,
never to a silent zero. This is what `volume_heterogeneity` selected for shot attempts / 36
(`REPORT.md:30`: form `ratio_ewma`, α 0.05).

Raw conditional attempts are then

```
pred_attempts = ratio_ewma(α) * (conditional minutes / 36)
```

**This composition is new.** No committed artifact forecasts raw conditional FGA; the rate leg was
never gated multiplied by a minutes forecast. It is registered as new and must never be described
as a promoted incumbent.

### 5.2 α grid — **RULING 2**

α = 0.05 is **not** an identified optimum. The sweep that produced it used
`feature_lab.ALPHA_GRID = [round(a,2) for a in np.arange(0.05, 0.501, 0.05)]` — floor **0.05** —
and the FGA/36 curve was monotonically increasing across it, so the minimiser lies **at or below
the floor** and is unidentified. The predeclared grid extends below that floor:

```
0.01, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50
```

Selected **inside each outer training fold** by chronological inner validation only, MAE loss,
ties → smallest α. **This grid is final.** If the minimum lands on 0.01, that value is retained
and **reported as a boundary solution**; the grid is **not** extended after seeing results. Doing
so would be exactly the post-hoc specification change the charter forbids.

The same 11-point grid is used for the minutes (§4) and points (§6) rate estimators, so that no
target gets a silently wider search than another.

---

## 6. `player_scoring_distribution` — `cbs2_points_pts36_x_minutes` — **NEW COMPOSITION**

Center: shifted within-`(player, season)` EWMA of the **points/36 rate**, multiplied by
conditional minutes / 36. This is the `per36_pts_ewma` family of `props_edge.py:14`, evaluated on
the contract universe rather than on prop-line rows.

**α selected per outer fold** from the §5.2 grid, inner-fold MAE, ties → smallest α.

### Provenance correction — v1 was wrong here

v1 stated that α = 0.30 for points "was tuned on 2021-2023 inner folds". **It was not.**
`props_edge.py:203` reads:

```python
ALPHA = 0.30                      # registered frozen family
```

It is a **declared** constant, not the argmin of any points curve. The 2021-2023 tuning provenance
belongs to **minutes** (`minutes_ewma_vs_carryforward_v1`), and v1 transplanted it.

This has a consequence that runs in the suite's favour and must be stated rather than quietly
enjoyed: because the points α was **declared** and not selected against outcomes, the legacy
fixed-0.30 variant **`cbs2_points_a030_legacy`** is **not outcome-contaminated on any fold**. It
is fold-honest throughout and eligible for weight fitting — unlike the minutes legacy variant of
§4. The asymmetry is real and is recorded so no later reader assumes the two legacies carry the
same status.

This composition (rate × forecast minutes, on the full contract universe, with no prop-line
restriction, no >= 3-prior-appearance restriction, and no inherited ~T-69m line vintage) is
**new**.

---

## 7. `team_game_distribution` — `cbs2_teampoints_structural_cal`

Center: the **structural** home/away point channels of `chanreval_2026_structural_repaired`
(`promote: true`, `verdict: PASS`), summed per team and passed through a **two-parameter linear
calibration map**

```
calibrated = a + b * uncalibrated          # experiments/channel_reval/run_reval.py:234-256
```

where `linfit` returns `(intercept, slope)` from `np.polyfit(x, y, 1)`.

### Fold-honest refitting — **required, and the committed artifact does not satisfy it**

The committed run fit **everything once on `TRAIN_YEARS = [2021, 2022, 2023]`** (`run_reval.py:57`;
`run_summary.json`: `calibration.n_train_games = 610`, channel `alphas = {ft: 0.1, 3pt: 0.05,
paint: 0.05, np2: 0.05}`, `str_home = (27.492229236454957, 0.6765323839944605)`,
`str_away = (30.293072204555740, 0.6234734548537014)`) and applied them forward. For an experiment
whose test seasons were 2024+ that was honest. **For this suite, which predicts 2021-2026, it is
not** — those parameters saw the outcomes of three seasons the suite must forecast.

Therefore, **within each outer training fold**:

1. re-select the four channel EWMA alphas (`ft`, `3pt`, `paint`, `np2`) by chronological inner
   validation on that fold's training games only, from the §5.2 grid, ties → smallest α;
2. **refit** the `str_home` and `str_away` linear calibration maps by ordinary least squares on
   that fold's training games only;
3. record both in the per-row provenance.

**Legacy sensitivity — `cbs2_teampoints_frozen2123_legacy`**: the committed fixed 2021-2023
alphas and calibration maps. **Contamination window: folds `season:2021`, `season:2022`,
`season:2023`** — reported there as a sensitivity only, ineligible for weight fitting; fold-honest
from `season:2024`.

### Dispersion and the margin comparator

These are **point centers with no dispersion of their own**. The per-team predictive sd comes from
§8 and is **new** — no committed artifact emits a per-team points sd.

The frozen live Gaussian **margin** sigma `SIGMA_V0 = 12.9022` is **not** a team-points sd and is
never used as one. Where a margin distribution is reported it is named
**`cbs2_margin_gaussian_comparator`** and kept distinct. A margin sd is a property of a
*difference*; per-team sds additionally require the residual correlation between the two teams,
which no committed artifact provides.

**76 team-games have zero candidates** (season openers; the lookback resets at each season
boundary). They stay **visible** in the output, flagged, never dropped and never silently imputed.

---

## 8. Uncertainty — chronological inner-OOF residuals only

This section replaces v1's ambiguous phrase "residuals computed strictly within the training
folds", which did not distinguish in-sample from out-of-sample and therefore permitted an
optimistic reading.

### 8.1 Residual source — frozen

For outer fold **F**, the residual pool is built **only** from the **same 3 inner walk-forward
folds** used for hyperparameter selection (§2). For inner fold *i*: fit the center on segments
`[0..i]`, predict segment `i+1`, and keep the residuals **on segment `i+1`**. Pool the three
validation segments.

Explicitly **excluded**:

- in-sample residuals of any kind;
- residuals from the final full-training-window fit that produces F's deployed center (same fit
  that produced the center → forbidden);
- any residual from the predicted season;
- any pooled all-season residual.

The α / λ used to generate residuals is **the one selected for F**, so the dispersion describes the
estimator actually deployed.

### 8.2 Point dispersion

`pred_sd` = sample standard deviation of the pooled inner-OOF residuals with **`ddof = 1`**.

**Minimum residual count:** **200** rows for player targets, **30** games for team targets. Below
that the §8.4 ladder escalates. `pred_sd > 0` strictly; a computed sd of 0 or non-finite escalates
the same way.

### 8.3 Quantiles

Empirical quantiles of the **same** pooled inner-OOF residual pool, added to the point center:

- estimator: `numpy.quantile(..., method="linear")` — the NumPy default, Hyndman-Fan **type 7**;
- levels: the contract's 0.05, 0.25, 0.50, 0.75, 0.95;
- **minimum sample for empirical quantiles: 200** residuals. Below that, quantiles are Gaussian:
  `pred_point + z_p * pred_sd` with **z frozen here**:

  | p | 0.05 | 0.25 | 0.50 | 0.75 | 0.95 |
  |---|---|---|---|---|---|
  | z | -1.6448536269514722 | -0.6744897501960817 | 0.0 | 0.6744897501960817 | 1.6448536269514722 |

- **truncation, then monotone sort, in that order**: truncate to the target's support, then sort
  the five values ascending so `q05 <= q25 <= q50 <= q75 <= q95`. The truncation applied is
  recorded per row, never applied silently.

Support: minutes `[0, 48]` (48 is a deliberately loose cap — WNBA regulation is 40 minutes and the
cap must admit overtime); attempts `>= 0`; player points `>= 0`; team points `> 0`.

### 8.4 Pooling level — frozen

**Fold-global.** All candidate rows of the target in fold F share one residual pool. There is
**no per-player and no heteroscedastic dispersion in v2.**

This is a deliberate baseline simplification, declared before results: per-player residual counts
are small enough that per-player sds would mostly estimate noise, and a baseline's job is to be a
hard-to-game reference, not the best available model. Minutes dispersion certainly varies with
expected minutes; a council member that models that should beat this suite on interval score, and
**that is the intended way to demonstrate it**. Heteroscedastic dispersion is deferred to a later
registered version and may not be retrofitted into v2 after seeing v2's results.

Escalation ladder when the pool is too small: fold-global pool → (if still `< 200` / `< 30`, which
can only happen in a degenerate fold) the §9 declared constants, flagged `is_fallback = True`.

---

## 9. `season:2021` — the declared constants, in full

`season:2021` has `train_boundary = "seasons < 2021"`, which selects **no rows at all**. Nothing
may be estimated for it. v1 promised "a frozen deterministic constant declared here" and then
declared none. Here they are.

These are **declared a priori from structural basketball arithmetic, not estimated from any
season**: 5 players on court × 40 regulation minutes = **200 team-minutes**; a declared 10-player
rotation → **20.0** minutes per rotation player; declared league-typical **82** team points and
**70** team field-goal attempts per game. No WNBA season's outcomes were consulted, and in
particular 2021's were not.

| target | `pred_point` | `pred_sd` | q05 | q25 | q50 | q75 | q95 |
|---|---|---|---|---|---|---|---|
| `p_active` | **0.800** | null | — | — | — | — | — |
| `e_minutes_given_active` | **20.0** | **9.0** | 5.196 | 13.930 | 20.000 | 26.070 | 34.804 |
| `attempts_usage` | **7.0** | **4.0** | 0.421 | 4.302 | 7.000 | 9.698 | 13.579 |
| `player_scoring_distribution` | **8.2** | **5.0** | 0.000 | 4.828 | 8.200 | 11.572 | 16.424 |
| `team_game_distribution` | **82.0** | **10.0** | 65.551 | 75.255 | 82.000 | 88.745 | 98.449 |

Derivation of the centers: minutes 200/10 = 20.0; attempts 70 × (20/200) = 7.0; player points
82 × (20/200) = 8.2; team points 82.0. Quantiles are `point + z_p × sd` with §8.3's z, then
truncated to support and sorted — which is why `player_scoring_distribution` q05 is **0.000**
(the untruncated value is negative) and why `attempts_usage` q05 is 0.421 rather than negative.
The sds are declared round numbers, not estimates.

**`season:2021` is its own stratum.** Every 2021 row carries `is_fallback = True` **and**
`is_cold_start = True`. It is reported separately and is **excluded from every pooled headline
score and from every council or meta-weight fit.** It exists so that the obligation count is
honest — 4,850 player rows and 418 team-games are predicted rather than quietly dropped — not so
that it can flatter an average. If these constants turn out to be poor, that is a **finding to
report, not a licence to retune them**; retuning after seeing 2021 outcomes would convert a
declared prior into a fitted parameter.

---

## 10. Fallback ladder — deterministic, training-only, visible

Fires in this fixed order; `fallback_level` is recorded per row.

| level | condition | estimate | flags |
|---|---|---|---|
| **1** | `n_prior_games >= 3` in the same season | the §3-§7 component | — |
| **2** | `1 <= n_prior_games <= 2` | the same estimator on the shorter history | `is_fallback = True` |
| **3** | `n_prior_games == 0`, or a NaN center (e.g. §5's zero EWMA denominator) | the **training-fold** mean of the target over training candidate rows, with the fold's §8 dispersion | `is_cold_start = True` |
| **4** | no training fold exists at all (`season:2021`) | §9's declared constants | `is_fallback = True` **and** `is_cold_start = True` |

`p_active` never uses levels 3-4 for its *features* — §3.2's declared defaults keep it at level 1-2
mechanically — but a zero-history row is still flagged `is_cold_start = True` so the strata are
comparable across targets.

Fallback rows are **never** dropped from the obligation count. Every headline score is reported
with the fallback strata broken out.

---

## 11. Identity and hashes

| field | how it is fixed |
|---|---|
| `arm_id` | `contract_baseline_suite_v2` |
| component ids | `cbs2_pactive_logistic_histonly`, `cbs2_eminutes_ewma_tuned`, `cbs2_attempts_ratio_ewma_x_minutes`, `cbs2_points_pts36_x_minutes`, `cbs2_teampoints_structural_cal` |
| named comparators | `cbs2_pactive_rulegate_comparator`, `cbs2_margin_gaussian_comparator` |
| legacy sensitivities | `cbs2_eminutes_ewma_a030_legacy`, `cbs2_points_a030_legacy`, `cbs2_teampoints_frozen2123_legacy` |
| `config_hash` | **`7ad8c09742bcbe89e469c7647d5026f5444ec85660ee713f0a921c3c9abeadb9`** — SHA-256 over the canonical (`sort_keys=True`, compact separators) JSON of `extra.frozen_config` **with `hashes.config_hash_value` removed**, the same self-referential convention v1 used and the supervisor verified |
| `model_hash` | per fold **and** per target, from the fitted parameters at generation time — necessarily absent today, because nothing is fitted |
| `data_snapshot_hash` | hash of the contract parquet snapshot consumed |

---

## 12. What this registration is not

- It is **not** a promotion candidate. Its registry thresholds are **sentinels**.
- It is **not** a previously promoted incumbent arm. Three of its five components are new
  compositions or newly refit; the audit at `db9f011` established **zero exact full-contract
  controls**.
- It is **not** evidence. It is a specification frozen before results exist.
- `arm_incumbent` remains **rejected and unconsumed**.
- The dynamic hierarchical arm is **not** begun.

**No chronological OOF prediction has been generated.** The three v1 open questions are now ruled
on, so the block that v1 recorded is lifted by this document — but generation itself remains
outside this cycle's authorisation and awaits the supervisory review of this registration.
