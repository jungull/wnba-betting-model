# E1_I0056 — MINUTES VARIANCE: PREREGISTRATION

**Written 2026-08-17, BEFORE any statistic in stages s01–s05 was computed.**
Hashed to `PREREG.sha256`. Nothing below may be revised after a result is seen. If a prediction
fails, the failure is recorded in `FINDINGS.json` and `NOTES.md` and the threshold stands.

Evidence level: **E1**. Non-claiming. Nothing here may be cited as a result, promoted, or used to
change production. Screen count disclosure: this is one screen; it re-opens a single thread left by
D134 ruling 4.

---

## 0. What ran before this preregistration, and why that is allowed

`scripts/s00_probe.py` ran on 2026-08-09 and is **structural only**: row counts, join coverage,
column degeneracy, within-season constancy, the `pred_cv` reciprocal identity, and rest-day
bucketing. It computes **no candidate-to-response statistic**. Its log ends `DONE s00` with an empty
stderr file. It is treated as trustworthy input to this preregistration and is not re-run.

**D100 DISCLOSURE — hindsight-informed choices, declared in advance.**

1. `s00`'s season-constancy table told me **where to look** (question 1). No number from `s00`
   produces a decision here; question 1 is re-settled independently on the shipped prediction
   parquet bytes and on the emitting source line.
2. Before writing this file I read `E1_I0054_absres_to_skill/CALIBRATION.csv`, which contains the
   published anchors `VLEV oof_r2 = 0.018378`, `VSIG oof_r2 = 0.042870`, `VALL oof_r2 = 0.041420`
   and `VSD oof_r2 = -0.004810` for minutes/WF. **Predictions P4 and P5 are reproduction targets and
   are therefore informed by construction.** Predictions **P6, P8a and P8b are thresholds set while
   knowing those four numbers** but **not** knowing any value of the L2–L5 level ladder, of the
   unselected non-level block, or of any increment — which are the new measurements. This is
   disclosed rather than hidden; it is the reason P6/P8 are stated as thresholds with real failure
   risk rather than as ranges around a known answer.
3. I read D131, D133 and D134 before writing this. Their content shapes the arms and the
   robustness checks. No number of theirs is reused as a floor (see §7).

---

## 1. Partition guard

Seasons **2021–2024 only**. 2025 and 2026 are the sealed confirmation holdout and are never read,
joined, plotted or described. Asserted on `season` and on the parsed date column of every source
read, and re-asserted after every filter. Sources:

| source | role | granularity |
|---|---|---|
| `E0_I0014_residual_heterogeneity/analysis_frame.parquet` | frame + response | derived, all inputs row- or season-bounded |
| `experiments/cbs_v15_player_oof_v5/attempt_001/predictions__*__{2022,2023,2024}.parquet` | question 1, on bytes | `asof_granularity: artifact`, `fit_through_season` 2022/2023/2024 — each file bounded at its own season, inside the partition |
| `E1_I0053_minutes/scripts/_frame.parquet` | robustness candidates only | inside partition |
| `E1_I0054_absres_to_skill/CALIBRATION.csv` | anchors only | published table |

The OOF prediction files are artifact-granular. Under GRAPH_POLICY 13.2.2 that normally forbids
use — but each file's `fit_through_season` is its own season and ≤ 2024, so the whole artifact sits
inside the exploration partition and no 2025/26 value can reach a 2021–2024 row. This is the same
resolution `E0_I0014` and `E1_I0054` used; it is recorded here rather than assumed.

---

## 2. Response, stratum, folds, convention

- **Response (primary):** `absres_minutes` = |realised minutes − `minutes__pred_point`|, the
  realised absolute error of the **shipped** minutes point forecast. This is a variance response,
  not a level response, and it is **not comparable to any published points, points-per-minute or
  minutes-level floor** (D101).
- **Response (replication):** `refabs_minutes` = |realised minutes − `ref_minutes`|, where
  `ref_minutes` is the strictly-prior within-season expanding mean of the player's own minutes. Used
  to check that any increment is a property of minutes, not of the shipped model's idiosyncrasies.
- **Stratum (primary):** `A4_CLEAN_DEC` = seasons ≥ 2023 **and** `pl_games_prior ≥ 8` **and**
  `pl_min_mean5 ≥ 24`. n = 3,549 rows, 174 player-seasons, 848 team-games, 169 dates.
- **Folds (primary):** walk-forward by date, `MIN_TRAIN = 600`, 138 folds, **2,945 scored rows**.
- **Folds (secondary):** grouped 5-fold by `player_id`, 3,549 scored rows. Reported, never the
  headline.
- **Convention:** plain **unweighted** R², unweighted in fit, SSE and SST (D069, D072 ruling 2).
  `SST = Σ(y − ȳ)²` over the scored rows, about the **unweighted** mean, **shared across all arms**
  so every `dR2 = (SSE_ref − SSE_cand)/SST` exactly.
- **Estimator:** ridge with an unpenalised intercept, standardised, zero-variance columns forced to
  zero coefficient. λ tuned on the last 25 % of each training window over `10^{-3..3}` when the arm
  has more than 3 columns, λ = 0 otherwise. This is `E1_I0054`'s exact rule, kept unchanged for
  comparability.

**Imputation — T1 (retrospective baseline).** The inherited `_common.py` fills missing candidate
values with the **season median over all rows in that season, including rows after the target
date**. That reads the future. Measured exposure on the stratum: 385 of 3,549 rows (10.85 %) for
every `x53_*` column, 3 rows for `pl_dnp_frac5`, zero elsewhere.

- **Primary arms use a strictly-prior imputation**: the expanding median over rows at strictly
  earlier dates within the same season, 0.0 if no prior row exists. Every imputed cell is counted
  and reported.
- The season-median version is run as a **declared robustness arm only**, and is used for the
  reproduction anchors P4/P5 because the sibling's number was produced with it.
- `x53_*` columns are excluded from the primary non-level block entirely (10.85 % join failure) and
  appear only in a robustness arm.

---

## 3. Column classification — settled on CONSTRUCTION and VALUES, never on names (D086)

Every list below is literal. **No substring match anywhere in this screen selects a column.** A name
may nominate; only a value test convicts.

**CONSTANT — carries zero per-row information on the stratum, ineligible for any arm.**
`minutes__pred_sd`, `pts__pred_sd`, `fga__pred_sd`, `minutes__pred_iqr`, `minutes__is_fallback`,
`minutes__fallback_level`, `minutes__is_cold_start`, `pts__is_fallback`, `pts__fallback_level`,
`pts__is_cold_start`. Evidence: `_SEASON_CONSTANCY.csv`, one distinct value within every season, and
(question 1) re-confirmed on the shipped parquet bytes.

**LEVEL-SPANNED — an exact monotone function of a predicted level, ineligible for a "non-level"
claim.** `pts__pred_cv`, `minutes__pred_cv`, `fga__pred_cv` (identity residual ≤ 8.9e-16 against
`pred_sd / pred_point`; within-season correlation with `1/pred_point` = 1.000000, `s00`);
`pts__pred_width`, `minutes__pred_width`, `fga__pred_width`, `fga__pred_iqr` (a fixed per-season
offset added to `pred_point` and then clipped to the support — verified on bytes in s01).

**CONTEMPORANEOUS — outcome-side, never in a forecasting feature set.**
`x53_starter_flag`, `x53_blowout`.

**LEVEL LADDER (the reference ladder — T4 requires more than one reference).**

| id | columns |
|---|---|
| `L0` | intercept only |
| `L1` | `pl_min_mean5` — **the D134 reference, "trailing level alone"** |
| `L2` | `L1` + `pl_min_mean5²` + `pl_min_mean5³` |
| `L3` | `L2` + `minutes__pred_point` + `minutes__pred_point²` + `inv_min_pred_point` |
| `L4` | `pl_min_mean5`, `pl_pts_mean5`, `pl_fga_mean5`, `pl_usg_mean5`, `pl_start_frac5`, `minutes__pred_point`, `pts__pred_point`, `fga__pred_point` |
| `L5` | `L4` + `pl_min_mean5²`, `pl_min_mean5³`, `minutes__pred_point²`, `pts__pred_point²`, `inv_pl_min_mean5`, `inv_min_pred_point`, `inv_pts_pred_point` |

`L5` is designed to span everything a level-only forecaster could use, **including the reciprocals**,
because `pred_cv` is exactly a season constant times `1/pred_point` and would otherwise re-enter a
"non-level" arm as smuggled level.

**NON-LEVEL BLOCK `N` (36 columns) — the thing being tested.**
Volatility (10): `pl_min_sd5`, `pl_min_cv5`, `pl_min_rng5`, `pl_min_trend5`, `pl_abs_min_trend5`,
`pl_start_switch5`, `pl_dnp_frac5`, `pl_pts_sd5`, `pl_fga_sd5`, `pl_usg_sd5`.
Experience/depth (9): `pl_games_prior`, `pl_minutes_prior`, `pl_career_games_prior`,
`pl_prior_season_games`, `pl_is_rookie_window`, `pl_rest_days`, `pl_teamgames_since_appear`,
`minutes__n_prior_games`, `pts__n_prior_games`.
Team/schedule (17): `tm_rest_days`, `tm_b2b`, `tm_3in4`, `tm_games_prior7d`, `opp_rest_days`,
`tm_rest_diff`, `tm_roster_churn_prior`, `tm_newfaces_prior`, `tm_five_tenure_prior`,
`tm_five_changed_prior`, `tm_prior_meetings`, `tm_first_meeting`, `tm_is_home`, `tm_game_idx`,
`opp_game_idx`, `tm_poss_mean_prior`, `opp_poss_mean_prior`.

**NON-LEVEL BLOCK `N2` (robustness only)** = `N` + the 11 `x53_*` non-contemporaneous columns +
`x53_absence8`.

---

## 4. Arms

| arm | columns | purpose |
|---|---|---|
| `A_L0` … `A_L5` | the ladder | reference decomposition (T4/D087) |
| `A_C1` | `L1 + N` | increment over the D134 reference |
| `A_C5` | `L5 + N` | **PRIMARY** — increment over the strongest level reference |
| `A_NONLY` | `N` | non-level alone |
| `A_VSIG` | `pl_abs_min_trend5, pl_dnp_frac5, pl_min_rng5, pl_min_sd5, pl_start_switch5, pts__pred_cv, pts__pred_width` | D134 reproduction. **Selection-carrying** (chosen from the 16 surviving E0_I0014 cells on this same partition) and reported for comparability only, never as a headline |
| `A_VSD` | `minutes__pred_sd` | the incumbent shipped column |
| `A_C5X` | `L5 + N2` | robustness |

**Primary statistic:** `dR2_primary = (SSE(A_L5) − SSE(A_C5)) / SST` on the 2,945 WF-scored rows.
**Secondary:** `dR2 over L1`; top-decile ÷ bottom-decile mean realised `absres_minutes` for every
arm; calibration slope; Spearman.

---

## 5. Nulls, controls and CI — fixed now

| id | scheme | draws | seed |
|---|---|---|---|
| `N1` | **within-player-season CYCLIC SHIFT** of the whole block `N` (one offset per block, applied to every column of the block together, preserving serial structure and cross-column alignment); re-run the full OOF; recompute `dR2` against the unchanged `A_L5` | **R = 1000** | 20260817 |
| `N1b` | within-player-season plain SHUFFLE, identical otherwise — run **only** to measure the D093 anticonservatism gap | R = 1000 | 20260817 |
| `N2` | paired **cluster sign-flip** on per-row squared-error differences `d_i = (y−ŷ_L5)² − (y−ŷ_C5)²`, clustered at **player-season** (174) and, separately, **team-game** | R = 5000 | 20260817 |
| `N3` | **noise control**: block `N` replaced by 36 iid N(0,1) columns | R = 200 | 20260817 |
| `V` | **vacuity proof**: cyclic shift with offset forced to 0, 50 draws; must reproduce the observed `dR2` with sd < 1e-15 and exactly 1 distinct draw value | 50 | 20260817 |
| `CI` | block bootstrap over the 174 player-season blocks, recomputing `dR2` from stored OOF predictions | R = 2000 | 20260817 |

**Grouping level.** Every column in `N` varies within a player-season, so no coarser constant level
exists; the correct scheme is a within-player-season permutation, and per D093 it must be the
**cyclic** variant because these are `.shift(1).rolling()` constructions. I will report
`within_group_acf1` for every column in `N` (screen kit) as the evidence for that choice.

**Proof the control is not vacuous (T6/D093/K7).** `N1`'s draws must have sd > 1e-6 and more than
100 distinct values; `V`'s draws must have sd < 1e-15. Both are reported as numbers, not verdicts.

**Power (mandatory whether or not the result is a null).** Injection: append one standardised iid
N(0,1) column `u` to block `N` and set `y_inj = y + c·u` for
`c ∈ {0.00, 0.10, 0.15, 0.20, 0.30, 0.40, 0.60, 0.90}` (units of the response scale), 40 replicates
per `c` with fresh `u` (seeds 20260901+k). Detection = paired sign-flip `p < 0.05` at
player-season clustering. Report the detection rate and the realised `dR2` per `c`, and the
**minimum detectable dR2 at 80 % power**.

---

## 6. Predictions — 16, with numeric thresholds, fixed now

**Question 1 — the defect.**
- **P1** `pred_sd` in `predictions__e_minutes_given_active__{2022,2023,2024}.parquet` has exactly
  **1 distinct value per season** across the whole file (not merely the decision stratum).
- **P2** `pred_q75 − pred_point` and `pred_q50 − pred_point` each have exactly **1 distinct value
  per season** for minutes.
- **P3** All per-row variation in `pred_q05` is deterministic clipping at the support bound:
  `pred_q05 == max(pred_point + off05, 0)` for every row, `max |deviation| < 1e-9`, where
  `off05 = min_rows(pred_q05 − pred_point)` in that season.

**Reproduction anchors.**
- **P4** `A_VLEV` (= `A_L1`) OOF R² on `absres_minutes`, WF, `A4_CLEAN_DEC`, season-median
  imputation = **0.018378 ± 1e-6** against `E1_I0054/CALIBRATION.csv`.
- **P5** `A_VSIG` OOF R² = **0.042870 ± 1e-4** and top/bottom decile ratio = **1.9089 ± 0.002**.

**Question 2 — the increment.**
- **P6** The strongest level-only reference `A_L5` reaches OOF R² **≥ 0.030** (against `A_L1`'s
  0.0184). *This is the reference-incompleteness test: I predict the published single-column
  reference is materially weaker than an available level-only reference.*
- **P7** `dR2(A_C5 over A_L5) > 0`.
- **P8a** `dR2(A_C1 over A_L1) ≥ 0.015`.
- **P8b** `dR2(A_C5 over A_L5) ≥ 0.010`.
- **P9** `N1` cyclic p **< 0.05** for `dR2(A_C5 over A_L5)`.
- **P10** `p(N1b plain shuffle) ≤ p(N1 cyclic)` — the D093 anticonservative direction.
- **P11** `N3` noise control: `|mean dR2| < 0.002` **and** Type-I rate at nominal 0.05 is **≤ 0.10**.
- **P16** Median `within_group_acf1` across the 36 columns of `N` is **≥ 0.20**, justifying the
  cyclic scheme over a plain shuffle.

**Question 3 — is it worth anything.**
- **P12** Abstaining on the top **30 %** of rows by `A_C5`'s predicted error reduces MAE of the
  shipped minutes forecast on the retained 70 % by **≥ 8 %** relative to the full-sample MAE.
- **P13** *(I predict this PASSES, i.e. no conversion.)* None of four point-forecast conversion arms
  (variance-weighted refit, variance-proportional shrinkage toward trailing level, mean augmentation,
  two-stage) improves the **minutes level** forecast: best `dR2` on `y_minutes` over a tuned `L5`
  reference is **≤ +0.002** with sign-flip **p ≥ 0.05**.
- **P14** Replication on the second response: `dR2(A_C5 over A_L5)` on `refabs_minutes` is **> 0**.
- **P15** Power: detection rate **≥ 0.80** at an injected realised `dR2` of **0.010**.

---

## 7. Floors and comparability (D101)

**No programme floor is imported.** The published points-scale floor 0.00072, the 0.002057 ceiling
and every points or points-per-minute number in the ledger are **NOT COMPARABLE** to a
`absres_minutes` response on this row set. This screen measures its **own** floor by injection
(§5) and its own block-bootstrap CI, and reports both. D133 established this as the norm.

## 8. D131 — the 200-minute budget

The primary response is a **per-row dispersion** forecast; it does not sum, so the budget projection
requirement does not bind it. Two things are nonetheless required and preregistered:

1. The P13 conversion arms **do** produce a summing minutes level forecast. They are defined only on
   a 3,549-row stratum, so a team-game sum is not computable there; I will therefore report **no
   team-aggregate mean** for them and make **no team-level claim**.
2. As a disclosure, I will report on `A1_FULL` (13,879 rows, 1,486 team-games) the **dispersion** of
   the shipped minutes forecast's per-team-game sum against 200 — MAE, RMSE, and the fraction within
   ±5 — and **never its mean**.

## 9. Deliverables

`PREREG.md` (this file) + `PREREG.sha256`, `FINDINGS.json`, `NOTES.md`, `DEFECTS.md`,
`run_log_s01..s05.txt`, raw null draws under `raw/`, and `scripts/s06_verify.py` asserting that every
headline number re-derives from the stored artifacts.
