# `contract_baseline_suite_v3` — frozen, pipeline-honest, executable

*Registered 2026-08-01, before any output. **Nothing in this document has been computed.** No
prediction, fitted parameter, accuracy figure, coverage score or prediction file exists for this
suite. The registry record is append-only and carries `computed_nothing: true`.*

**Supersedes `contract_baseline_suite_v2`.** Neither v1 nor v2 is mutated — both registry records
stay byte-identical and both specification documents are retained unchanged as the historical
record. `CONTRACT_BASELINE_SUITE_V1.md` was restored **byte-for-byte** to its `db9f011` content
after an earlier revision wrongly edited a frozen document while claiming it was "retained
unchanged"; supersession notices live here and in the ledger, never inside a frozen spec.

v3 exists because v2, though executable, was **not pipeline-honest**: it let the same outcomes
both select the estimator and calibrate its uncertainty.

---

## 0. What v3 changes

| # | v2 defect | v3 |
|---|---|---|
| 1 | dispersion came from the same 3 inner validation segments that selected α and λ — the residual spread was conditioned on outcomes already used to pick the estimator, so intervals would be optimistically narrow | §1 **disjoint chronological calibration tail**, never used for any selection |
| 2 | tuning/fallback masks unstated per target | §2 target-specific masks frozen |
| 3 | play history built on prior *appearances*, conflating "0 of 4 obligations" with "no evidence" | §3 history over **candidate obligations**, the two counts recorded separately |
| 4 | document feature order did not match the hashed registry order | §4 one canonical order, used in both |
| 5 | tuning order unstated — attempts/points could float against an unselected minutes leg | §5 explicit order and objectives |
| 6 | points α = 0.30 called fold-honest and weight-eligible | §6 provenance **unknown**, sensitivity-only on **all** folds |
| 7 | team-points support written as "> 0" | §7 floor frozen numerically at **`1e-6`** |

**Carried from v2 unchanged:** the common contract layer (35,615 pg / 2,990 tg, two cutoff classes
never merged, `season:<YYYY>` folds, obligation-vs-scoring split, fail-closed
`validate_predictions()`, per-row provenance, `feature_asof < forecast_cutoff` strictly); the
`p_active` model class, standardisation and λ grid; the `ratio_ewma` attempts estimator and the
11-point α grid with its boundary-reporting rule; the fallback ladder; the `season:2021` declared
constants; the exclusion cross-tab obligation; the named comparators; and the 76 visible
zero-candidate team-games.

**Executable core:** `cbs_builders.py`, exercised on synthetic data by
`tests/test_cbs_builders.py` (54 assertions), wired into the repository gate. Nothing in either
file reads contract data or emits a forecast.

---

## 1. Disjoint selection and calibration — the core correction

> **No outcome may serve both selection and uncertainty calibration.**

v2 said dispersion came from "chronological inner-OOF residuals", which sounds out-of-sample and
is — with respect to the *fit*. But those same three validation segments chose α and λ. The
selected pipeline is the one that looked best on exactly those rows, so its residuals there are
biased small. Prediction intervals built from them would be too narrow, and the bias would be
invisible in any single-arm check.

### 1.1 Player targets — two disjoint segments

Each outer fold's training window is cut **on distinct game dates**, so no date straddles the
boundary and a heavy slate cannot appear on both sides:

| segment | share of distinct training dates | used for | never used for |
|---|---|---|---|
| **tuning prefix** | first **75 %** | feature/family choice, α, λ, base rates, fallback means | dispersion |
| **calibration tail** | last **25 %** | residual sd and quantiles | any selection |

- Fraction frozen: `CALIBRATION_TAIL_FRACTION = 0.25`, tail size `floor(n_dates * 0.25)`.
- Minimums frozen: **8** distinct tuning dates and **4** distinct calibration dates.
- Construction: `cbs_builders.split_tuning_calibration`, which asserts disjointness on both rows
  and dates and raises `SelectionLeakage` otherwise.
- The selected pipeline is refit on the **tuning prefix only**, then predicts the untouched
  calibration tail; those out-of-sample residuals are the dispersion pool.

**Low-data fallback, frozen.** If the window cannot satisfy both minimums the split is reported
`degenerate`, **no calibration rows are produced**, and the fold takes the §9-of-v2 declared
constants for dispersion. It must **not** fall back to reusing tuning residuals — that is the
exact defect being corrected, and the builder makes it unrepresentable by returning an empty
calibration index.

### 1.2 Team points — three disjoint segments

Team points need one more, because the calibration *map* is itself fitted:

| segment | share of training team-games | used for |
|---|---|---|
| **T1** | first **50 %** | channel α selection |
| **T2** | next **25 %** | fitting the `str_home` / `str_away` linear calibration maps |
| **T3** | last **25 %** | dispersion residuals |

Fitting the map and measuring its residual spread on the same games would understate dispersion
for the same reason. Minimum **30 team-games per segment**; below that the fold is degenerate and
takes the declared constants.

---

## 2. Target-specific masks — frozen

| target | tuning loss / base rate / fallback mean computed over |
|---|---|
| `p_active` | **all candidate obligations** in the segment — the estimand is defined on every candidate, so restricting to active rows would estimate the wrong thing |
| `e_minutes_given_active` | **active, outcome-scoreable** training rows only |
| `attempts_usage` | **active, outcome-scoreable** training rows only |
| `player_scoring_distribution` | **active, outcome-scoreable** training rows only |
| `team_game_distribution` | **resolved** team-games only |

The three conditional targets are conditional *on activity*; including inactive rows would drag
their centers toward zero and silently redefine the estimand. `p_active` is the opposite case.

---

## 3. History over candidate obligations, not appearances

Stage-A history is built on **strictly prior contract candidate obligations**, including prior
candidacies where the player was absent or not in the box score.

Two counts are recorded separately per row:

- **`n_prior_candidate_games`** — prior obligations;
- **`n_prior_appearances`** — of those, the ones played.

`p_plays_prior = n_prior_appearances / n_prior_candidate_games` whenever
`n_prior_candidate_games > 0`.

The distinction that v2 lost: a player with **0 appearances across `k > 0` obligations** has
history **`0/k`** — strong evidence of non-play. A player with **zero prior obligations** has *no
evidence at all*. **The training-fold base-rate default is reserved exclusively for the second
case.** Applying it to the first would overwrite real evidence with a league average and
systematically over-predict availability for exactly the players least likely to play.

Enforced by `cbs_builders.prior_candidate_history` (which returns `NaN`, not a fill, for the
no-obligation case) and `apply_base_rate_default` (which fills only where
`has_prior_obligation` is false).

---

## 4. Canonical `p_active` feature order

**This exact order, positionally, is what the registry hashes and what coefficient and model
hashes are computed over.** v2's document rendered the same 14 features in a two-column layout
that did not match the registry order; the list below is authoritative.

```
 1  p_plays_prior                    8  games_missed_streak
 2  min_ewma                         9  prev_dnp_cd
 3  started_last                    10  prev_dnp_inj
 4  start_share_l5                  11  prev_dnp_nwt
 5  played_last_team_game           12  returning_flag
 6  played_share_l10_team_games     13  player_gp_season
 7  days_since_last_appearance      14  team_gp_season
```

Read **down each column in index order** — 1-7 then 8-14. Regime A: the five regime-B archive
features (`miss_inj_l21`, `miss_other_l21`, `roster_move_l14`, `suspension_l30`,
`waived_since_last_game`) are excluded, and there is no W1 news input. Caps carried unchanged:
`days_since_last_appearance` at 45.0, `games_missed_streak` at 20.0.

---

## 5. Tuning order and objectives — frozen

The legs are **not** independent: attempts and points are compositions over the minutes leg, so a
rate α selected against a floating minutes leg would silently absorb minutes error.

1. **Minutes α** — selected first, by **conditional-minutes MAE on active validation rows**.
2. **Attempts-rate α** — with the minutes leg **held fixed** at the α from step 1, selected by
   **raw conditional-FGA MAE after composition** on active validation rows.
3. **Points-rate α** — with the **same** fixed minutes leg, selected by **conditional-points MAE
   after composition** on active validation rows.
4. **Team channel α** — each of `ft`, `3pt`, `paint`, `np2` selected **independently by its own
   channel-specific MAE**, matching the registered `run_reval.tune_alphas` family (per-channel
   inner-fold MAE, masked to non-null predictions and `prior_games >= MIN_PRIOR`, first minimum
   in ascending-α order). Then the `str_home` / `str_away` calibration maps are fitted **only on
   segment T2** of §1.2.

All selection is on the tuning prefix (T1 for team channels). Ties go to the **smallest α**,
evaluated in ascending grid order. Boundary solutions are **retained and reported**, never fixed
by widening the grid after the fact. The α held fixed for steps 2-3 is emitted as provenance.

Implemented by `cbs_builders.select_alpha_ordered`; the fixed-minutes-leg property is asserted in
`tests/test_cbs_builders.py`.

---

## 6. Points α = 0.30 — provenance **unknown**, sensitivity only

v2 concluded that because `props_edge.py:203` declares `ALPHA = 0.30  # registered frozen family`
and no points-target tuning curve exists, the constant must be outcome-independent, and therefore
fold-honest and eligible for weight fitting on every fold.

**That inference is withdrawn.** The absence of a demonstrated tuning curve is not evidence of
outcome-independence. It does not establish that 0.30 was chosen without looking at points
outcomes, nor that it was available before every retrospective fold this suite predicts. Absence
of a record is absence of a record.

Therefore:

- provenance and contamination window are labelled **UNKNOWN**;
- `cbs3_points_a030_legacy` is **sensitivity-only on all folds**;
- it is **not** described as fold-honest and is **not** eligible for meta-weight or council-weight
  fitting on any fold.

The same caution applies to the minutes legacy α = 0.30, whose contamination window on
`season:2021-2023` is *documented* rather than unknown. Neither legacy is weight-eligible.

---

## 7. Support and floors

| target | support | floor |
|---|---|---|
| `e_minutes_given_active` | `[0, 48]` | 0 (48 is deliberately loose — WNBA regulation is 40 minutes; the cap must admit overtime) |
| `attempts_usage` | `>= 0` | 0 |
| `player_scoring_distribution` | `>= 0` | 0 |
| `team_game_distribution` | strictly positive | **`1e-6`**, frozen numerically (`cbs_builders.TEAM_POINTS_FLOOR`) |

Quantiles are **truncated to support first, then monotone-sorted** — that order, because sorting
before truncating can reintroduce a non-monotone sequence the validator rejects.
`pred_sd > 0` strictly. Dispersion estimator unchanged from v2: sample sd with `ddof = 1`;
empirical quantiles via `numpy.quantile(method="linear")` (Hyndman-Fan type 7) at **>= 200**
player residuals / **>= 30** team residuals, Gaussian `z * sd` below that with the frozen z
values — now computed on the §1 calibration segments rather than the tuning segments.

---

## 8. Identity

| field | value |
|---|---|
| `arm_id` | `contract_baseline_suite_v3` |
| components | `cbs3_pactive_logistic_histonly`, `cbs3_eminutes_ewma_tuned`, `cbs3_attempts_ratio_ewma_x_minutes`, `cbs3_points_pts36_x_minutes`, `cbs3_teampoints_structural_cal` |
| comparators | `cbs3_pactive_rulegate_comparator`, `cbs3_margin_gaussian_comparator` |
| legacy sensitivities (none weight-eligible) | `cbs3_eminutes_ewma_a030_legacy` (contaminated 2021-2023), `cbs3_points_a030_legacy` (provenance unknown), `cbs3_teampoints_frozen2123_legacy` (contaminated 2021-2023) |
| `config_hash` | **`b8d22ec8c3d4584a3bba97f9cc47ba64d369e0f91f29f0e38560b33da595733e`** — SHA-256 over the canonical (`sort_keys=True`, compact separators) JSON of `extra.frozen_config` with `hashes.config_hash_value` removed, the same self-referential convention as v1/v2 |

The §4 feature order, the α and λ grids, the calibration-tail fraction, the minimum residual
counts and the `1e-6` floor are all asserted **equal between this document, the registry record
and `cbs_builders.py`** by `tests/test_cbs_builders.py`, which runs in the repository gate. A doc
that drifts from the hashed record now fails the gate rather than going unnoticed.

---

## 9. What this registration is not

- **Not** a promotion candidate — thresholds are sentinels.
- **Not** evidence. It is a specification frozen before results exist.
- **Not** a previously promoted incumbent arm.
- `arm_incumbent` remains **rejected and unconsumed**.
- The dynamic hierarchical arm is **not** begun.

**No historical OOF, fitted suite artifact, accuracy or coverage result has been generated.**
Generation into a new v3 artifact directory awaits supervisory review of this registration, and
validation, provenance, obligation coverage and the exclusion cross-tabs must all pass **before
any accuracy metric is inspected**.
