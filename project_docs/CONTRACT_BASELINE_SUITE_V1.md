# `contract_baseline_suite_v1` — frozen specification (definition only)

> ## SUPERSEDED 2026-08-01 by `contract_baseline_suite_v2`
>
> See **`project_docs/CONTRACT_BASELINE_SUITE_V2.md`**. Supervisory review of `db9f011` found
> this specification **frozen but not executable**: five rules it named were never stated (the
> `p_active` feature vector/standardization/λ grid/tie-break/low-data rule; the `season:2021`
> numeric constants; whether "training-fold residuals" are in-sample or out-of-sample; a
> fold-honest refitting rule for the team centers), and **§2.4's claim that points α = 0.30 was
> "tuned on 2021-2023" is false** — that provenance belongs to *minutes*;
> `props_edge.py:203` declares points α = 0.30 a frozen family. The three open questions of §6
> are ruled on in v2 §5.1, §5.2 and §2.
>
> **This document is retained unchanged as the historical record**, and the v1 **registry record
> is not mutated** — the registry is append-only. Nothing here was ever generated from: v1
> produced no prediction, fitted parameter or score. Read v2 for the executable specification.

*Registered 2026-08-01, before any output. **Nothing in this document has been computed.** No
prediction, fitted parameter, accuracy figure, coverage score or prediction file exists for this
suite, and none was inspected while writing it. The registry record is append-only and carries
`computed_nothing: true`.*

This replaces the inaccurate phrase *"the current EWMA/ridge player layer, unchanged"* used when
`experiments/arm_incumbent` was attempted at `ac2e2f0`. There is no such unchanged layer: the
incumbent mapping audit establishes **zero exact full-contract controls across all five targets**
(`project_docs/INCUMBENT_MAPPING_AUDIT.md`). This is therefore a **registered baseline suite**,
newly specified — **not** a previously promoted incumbent arm, and not a promotion candidate.

Its purpose is to be the reference every later council member must beat under identical rows,
cutoffs, folds, obligations and scoring masks.

---

## 1. Common contract layer (identical for all five targets)

| element | frozen value | source |
|---|---|---|
| contract | `player_game_contract/2` | `experiments/prediction_contract_v2/contract.json` |
| rows — player | **35,615** candidates (`pg_`), 1,458 candidate games | `contract.json` `accounting` |
| rows — team | **2,990** team-games (`tg_`) | `contract.json` `accounting` |
| roster lookback | 5 games, strictly prior | `contract.json` |
| central invariant | deleting every target-game player row must not change the candidate set | `contract.json` |
| folds | `fold_id = "season:<YYYY>"`, `train_boundary = "seasons < <YYYY>"` | `prediction_contract_v2.py:497-499, 506` |
| quantiles | 0.05, 0.25, 0.50, 0.75, 0.95 | `prediction_contract_v2.py:109` |
| clustering | `game_date` | `contract.json` |
| validator | `validate_predictions()` — **fail-closed, run per target before anything is scored** | `prediction_contract_v2.py:334-400` |

### Cutoff classes — two, never merged

- `exact_tip_T-90m` — `scheduled_tip_time - 90m`. **407 games / 814 tg / 10,257 pg.**
- `date_only_prior_day_cutoff` — 18:00 UTC the day before. **1,088 games / 2,176 tg / 25,358 pg.**

Reported **separately**, always. A date-only row is never described as T-90m. Exact-tip rows
exist only in 2025 (197/310) and 2026 (210/215); **2021-2024 have zero certifiable exact tips**,
so any exact-cutoff comparison is confined to the last two seasons.

### Fold sizes (from the committed contract parquets)

| fold | train boundary | pg rows | tg rows |
|---|---|---|---|
| `season:2021` | `seasons < 2021` | 4,850 | 418 |
| `season:2022` | `seasons < 2022` | 5,561 | 478 |
| `season:2023` | `seasons < 2023` | 6,145 | 520 |
| `season:2024` | `seasons < 2024` | 6,094 | 524 |
| `season:2025` | `seasons < 2025` | 7,438 | 620 |
| `season:2026` | `seasons < 2026` | 5,527 | 430 |
| **total** | | **35,615** | **2,990** |

**`season:2021` has an empty training set.** It is frozen here as a fold in which *every* row
takes the deterministic fallback path of §4 and is flagged `is_cold_start = True`. It is
reported, never hidden, and **never pooled into a headline score without being shown
separately**.

### Prediction obligation vs scoring mask — independent, never combined

| target | `prediction_required` | `outcome_scoreable` |
|---|---|---|
| `p_active` | 35,615 | 35,615 |
| `e_minutes_given_active` | 35,615 | 27,349 |
| `attempts_usage` | 35,615 | 27,349 |
| `player_scoring_distribution` | 35,615 | 27,349 |
| `team_game_distribution` | 2,990 | 2,990 (resolved finals) |

Every required row is predicted or carries an explicit `exclusion_reason`. **A silently missing
row is a violation.** Coverage is reported as `prediction_coverage` and `scoreable_coverage`
**separately and never combined** — the loophole that sank `arm_incumbent` at `ac2e2f0`, where
outcome-selecting exclusions produced a `scoreable_coverage` of 1.0.

**Standing exclusion-audit obligation.** Because the validator accepts any *declared*
exclusion, this suite additionally commits — before generation — to cross-tabulating every
excluded row by `in_target_box` and by `appeared`. If exclusion predicts non-appearance, that is
an outcome-selection alarm and the run is void, not a success.

### Provenance emitted per row

`row_uid`, `target_key`, `arm_id`, `fold_id`, `forecast_cutoff`, `pred_point`, `pred_sd`,
`pred_q05..q95`, `is_fallback`, `is_cold_start`, `n_prior_games`, `feature_asof`, `model_hash`,
`config_hash`, `data_snapshot_hash`, `exclusion_reason`.

`feature_asof < forecast_cutoff` **strictly** (equality is leakage and is rejected).

---

## 2. Target components — frozen before any output

`arm_id` = `contract_baseline_suite_v1`. Each target carries its own component id.

### 2.1 `p_active` — `cbs1_pactive_logistic_histonly`

- **History-only chronological Stage-A logistic.** Same model class as
  `minutes_twostage_availability_v1` Stage A (L2 logistic via IRLS, intercept unpenalised),
  but **history-only**: no injury-history archive and no W1 news input, so this suite is
  **regime A**.
- **Refit within each training fold** on the contract candidate universe — not fit once and
  frozen. λ selected by inner chronological folds **strictly inside the training seasons of the
  fold being predicted**, never on the predicted season.
- Uncertainty: for `p_active` the probability **is** the uncertainty; `pred_sd` is null by
  contract. Calibration is scored.
- **The deterministic Out gate is a separately named comparator**,
  `cbs1_pactive_rulegate_comparator`, reported alongside and **never relabelled as a
  probability**. It is a binary exclusion rule with no uncertainty.

### 2.2 `e_minutes_given_active` — `cbs1_eminutes_ewma_a030`

- Shifted per-player minutes EWMA, **α = 0.30** — the promoted value from
  `minutes_ewma_vs_carryforward_v1` (`verdict: PASS`, `promote: true`), live as
  `MINUTES_ALPHA`.
- Reused as a **point-estimator ingredient only.** The registered artifact predicts only
  regular-season played rows with >= 1 prior same-season played appearance and emits no sd; this
  suite wraps it to meet the every-candidate obligation and adds uncertainty per §3.
- **α is inherited, not re-tuned.** It was tuned on 2021-2023 inner folds; because that window
  overlaps folds this suite predicts, α is frozen as a **fixed constant of the baseline**, and
  the suite is labelled accordingly. It is not presented as a fold-honest tuned hyperparameter.

### 2.3 `attempts_usage` — `cbs1_attempts_fga36_x_minutes` — **NEW COMPOSITION**

- Shifted per-player **FGA/36 EWMA, α = 0.05**, multiplied by conditional minutes / 36 to
  produce **raw conditional attempts** on the contract's support.
- **Registered explicitly as a new composition.** Neither leg has ever been gated in this form,
  and no registered component forecasts raw conditional FGA.
- **Two open questions are frozen with it, for supervisory ruling before generation** — see §6.

### 2.4 `player_scoring_distribution` — `cbs1_points_pts36_x_minutes` — **NEW COMPOSITION**

- Shifted per-player **points/36 EWMA, α = 0.30**, multiplied by conditional minutes / 36 for
  the player-points center.
- Same functional form as `props_edge_v1`'s projection, but **not** that artifact: this suite is
  not restricted to prop-line rows, not restricted to >= 3 prior appearances, and does not
  inherit its ~T-69m line vintage. It is a **new composition** on the contract universe.
- Requires sd **and** the five named quantiles per §3.

### 2.5 `team_game_distribution` — `cbs1_teampoints_structural_cal`

- **Promoted calibrated structural home/away point centers** — `str_home_cal` / `str_away_cal`
  from `chanreval_2026_structural_repaired` (`promote: true`, `verdict: PASS`, all five gates
  true), two-parameter linear mean maps.
- These are **point centers with no dispersion**. The per-team predictive sd required by the
  contract comes from §3 and is **new** — no committed artifact emits a per-team points sd.
- The frozen live Gaussian **margin** sigma (`SIGMA_V0 = 12.9022`) is **not** a team-points sd
  and is not used as one. Where a margin distribution is reported it is named
  `cbs1_margin_gaussian_comparator` and kept distinct.
- **76 team-games have zero candidates** (season openers; the lookback resets at each season
  boundary). They remain **visible** in the output, flagged, never dropped and never silently
  imputed.

---

## 3. Uncertainty — strictly training-fold residuals

For every target requiring uncertainty (`e_minutes_given_active`, `attempts_usage`,
`player_scoring_distribution`, `team_game_distribution`):

- `pred_sd` and the quantiles are derived from **residuals computed strictly within the training
  folds of the fold being predicted** (`seasons < fold season`). **No residual from the
  predicted season, and no pooled all-season residual, may enter.**
- Quantiles are the training-fold empirical residual quantiles applied around the point center,
  then **sorted to enforce monotone non-decreasing** q05 <= q25 <= q50 <= q75 <= q95 — the
  validator rejects non-monotone quantiles.
- **Support and truncation, frozen:**
  - minutes: truncated at 0, capped at 48; `pred_sd > 0` strictly.
  - attempts: truncated at 0; `pred_sd > 0` strictly.
  - player points: truncated at 0; `pred_sd > 0` strictly.
  - team points: strictly positive; `pred_sd > 0` strictly.
  - Truncation is applied to the **emitted quantiles and point**, and the truncation rule is
    recorded per row rather than applied silently.
- `p_active` emits `pred_sd = null` by contract.
- **`season:2021` has no training fold**, so it has no training residual. Its sd/quantiles come
  from the §4 fallback and every row is flagged `is_fallback = True` and `is_cold_start = True`.

---

## 4. Fallbacks — deterministic, training-only, and visible

Every required row is predicted. Fallbacks fire in this fixed order, and each is **estimated
only from training-fold data**:

1. **Player has sufficient prior same-season history** → the target component of §2.
2. **Player has some prior history below the component's threshold** → the same estimator on the
   shorter history, flagged `is_fallback = True`, with `n_prior_games` recorded.
3. **Player has zero prior history at this cutoff (cold start)** → the **training-fold
   positional/league prior**: the training-fold mean of the target over all candidate rows,
   flagged `is_cold_start = True`.
4. **No training fold exists at all (`season:2021`)** → a frozen deterministic constant declared
   here rather than learned, flagged `is_fallback = True` **and** `is_cold_start = True`, and
   reported as its own stratum.

Fallback rows are **never** dropped from the obligation count, and headline scores are always
reported with the fallback stratum broken out.

---

## 5. Hashes and identity

| field | how it is fixed |
|---|---|
| `arm_id` | `contract_baseline_suite_v1` |
| component ids | the five `cbs1_*` ids in §2, plus the two named comparators |
| `config_hash` | SHA-256 of the frozen configuration block stored in the registry record's `extra.frozen_config` |
| `model_hash` | per fold **and per target**, computed from the fitted parameters at generation time — necessarily absent today, because nothing is fitted |
| `data_snapshot_hash` | hash of the contract parquet snapshot consumed |

`config_hash` is a hash of **text frozen before any output**, not of a result.

---

## 6. Open questions frozen with the registration — supervisory ruling requested

These are recorded **before** generation so that whatever is decided cannot be chosen after
seeing an outcome.

1. **`attempts_usage` estimator family.** The supervisory instruction specifies *"shifted FGA/36
   EWMA alpha 0.05"*. The artifact it points to selected **`ratio_ewma`** — the shifted
   **ratio-of-EWMAs** of (fga, minutes) × 36 — which is a *different* estimator from the shifted
   EWMA of the FGA/36 rate. This registration freezes the **instructed** form (shifted EWMA of
   the FGA/36 rate) and flags the divergence rather than substituting its own judgment.
2. **α = 0.05 is a grid-boundary corner.** The swept grid starts at 0.05 and the FGA/36 curve is
   monotonically increasing across all ten points, so the minimising α is **unidentified** and
   lies at or below the floor. Freezing 0.05 freezes a corner solution. Whether to (a) keep
   0.05, (b) extend the grid downward inside training folds only, or (c) re-tune per fold, is a
   **specification decision for the supervisor**, not for the engineer.
3. **Inherited α values (0.30 for minutes and points/36)** were tuned on 2021-2023, which
   overlaps folds this suite predicts. They are frozen as fixed constants and the suite is
   labelled accordingly; they must not be described as fold-honest tuned hyperparameters.

Until these are ruled on, **no chronological OOF prediction is generated.**

---

## 7. What this registration is not

- It is **not** a promotion candidate. Its registry thresholds are **sentinels**; it defines a
  reference, it does not claim to beat anything.
- It is **not** the previously promoted incumbent arm, and must never be described as such.
- It is **not** evidence. It is a specification frozen before results exist.
- The dynamic hierarchical arm is **not** begun.
