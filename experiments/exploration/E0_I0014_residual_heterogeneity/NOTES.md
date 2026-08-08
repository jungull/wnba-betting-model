# E0_I0014 — Residual heterogeneity: what pre-game state predicts when the player model is wrong

**Tier E0 (discovery). Everything here is a LEAD, never a result.** No preregistration, no
bootstrap, no promotion threshold, no registry entry. Nothing in this directory may be cited as
evidence for anything.

Partition: **2021–2024 only**, screened on **2022–2024**. The 2025/26 holdout was never read,
joined, plotted, described or summarised.

---

## 1. The question, and why it is not the last six screens

Policy 13.5 changed the target. The last several sweeps hunted new *main effects* for player box
targets and that surface is mined out. This screen asks a different question: **where is the
existing model's error concentrated, what observable pre-game state predicts that, and can we
abstain elsewhere.** Heterogeneity in the residual is the object, not a new feature.

---

## 2. Step 1 — the residuals are genuinely point-in-time. No walk-forward had to be built.

**Verdict: POINT-IN-TIME, out-of-sample.**

A season-chronological walk-forward already exists at
`experiments/cbs_v15_player_oof_v5/attempt_001/`. The fold for season *S* is fitted on Tier-A rows
of seasons *< S* only:

| season | train_seasons | n_train | n_test | model_was_fitted | degenerate |
|---|---|---|---|---|---|
| 2021 | `[]` | 0 | 4997 | **false** | **true** |
| 2022 | `[2021]` | 4850 | 6333 | true | false |
| 2023 | `[2021, 2022]` | 10413 | 7418 | true | false |
| 2024 | `[2021, 2022, 2023]` | 16563 | 7866 | true | false |

**2021 is excluded.** Its fold reports `n_train_rows = 0`, `model_was_fitted = false`,
`cold_start_declared_constant_only = true`. Its residuals are the residuals of a declared
constant, not of the model, and characterising them would teach us nothing about forecasting.

Provenance evidence beyond the labels — I read the construction, not the label:

- Every fold receipt carries `fold_boundary` ok, `provenance_history` ok, and
  `own_outcome_never_informed_its_forecast: true`.
- Each row carries its own `forecast_cutoff` (prior-day 18:00 UTC) and `feature_asof`
  (prior-day 12:00 UTC).
- **Leak probe 1.** Rows flagged `is_cold_start` carry exactly **one distinct `pred_point` per
  season** for every target — a pooled prior, carrying zero player-specific information. A
  contaminated fit would have given each cold player their own number.
- **Leak probe 2.** Every forecast tracks the player's **prior**-game mean more tightly than the
  player's remaining-season mean: pts 0.947 vs 0.854, minutes 0.922 vs 0.830, fga 0.949 vs 0.879.
  An in-sample fit would not show that asymmetry.

Targets available from this arm: **points** (`player_scoring_distribution`), **minutes**
(`e_minutes_given_active`), **FGA** (`attempts_usage`). `p_active` is a declared constant 0.8 and
was not screened. **There is no rebound or assist forecast in this arm**, so the D051 residual
characterisation cannot be completed for those two targets without new generation. That is the
main gap this screen leaves open.

Caveat declared: the v15 artifacts are stamped `generation_only: true` / `scores_computed: false`.
Computing residuals from them for an E0 characterisation is not a scoring event and no metric here
is registered.

### The baseline nobody should skip past

Over 13,879 appeared player-games in 2022–2024, against a **point-in-time expanding
prior-appearance mean** built here as a reference:

| target | model MAE | reference MAE | skill | plain unweighted R² |
|---|---|---|---|---|
| points | 4.1909 | 4.1816 | **−0.22 %** | 0.4694 |
| minutes | 5.0797 | 5.2669 | **+3.55 %** | 0.6194 |
| FGA | 2.6376 | 2.6406 | **+0.12 %** | 0.5893 |

The champion player forecast is, pooled, indistinguishable from an expanding prior mean on points
and FGA. This is the number the abstention curves have to move, and it is why every curve reports
**skill** and not just MAE.

---

## 3. Manifest checks (values inspected, not text scanned)

| artifact | `asof_granularity` | verdict |
|---|---|---|
| `data/masters/master_player.parquet` | `row` | USED |
| `experiments/prediction_contract_v4/player_game.parquet` | `row` | USED (row_uid bridge + outcomes) |
| `cbs_v15_player_oof_v5/.../predictions__*__{2022,2023,2024}.parquet` | `artifact` | **USED — see below** |
| `data/w1_truth/player_game_availability.csv` | `artifact`, bound 2026 | **REFUSED, NEVER OPENED** |
| `data/w1_truth/roster_asof.csv` | `artifact`, bound 2026 | REFUSED, NEVER OPENED |
| `data/zone_maps/*` | artifact-granular | NOT TOUCHED |
| `experiments/minutes_baselines/test_predictions.csv` | **no sibling manifest** | NOT USED |

The availability file is exactly what an availability screen reaches for first. Its manifest was
read before any use. It is artifact-granular with `fit_through_season: 2026`, so filtering to
2021–2024 does not help. It was not opened, and every roster/availability candidate below was
rebuilt from `master_player` box membership instead.

**Why the artifact-granular OOF predictions are nevertheless usable.** The general rule — a
2021 row in an artifact-granular file may embed 2026 information, so filtering does not help — is
about *mixed-bound* files. These are per-season files and each carries its **own**
`fit_through_season` equal to its own season (2022 → 2022, 2023 → 2023, 2024 → 2024). The whole
artifact is bounded inside the exploration partition; no filtering is being relied on to rescue it.
I checked each file's manifest individually and refused anything bound past 2024. If a coordinator
disagrees with this reading, the screen collapses and would need the forecasts regenerated.

No regex or byte scan of file contents was used as a partition check anywhere. Partition
enforcement is a **value test** on the `season` column and on `max(game_date)`, at every load and
before every write (`rh_base.guard`, five call sites).

---

## 4. TIME-WINDOW TABLE — every constructed feature and exactly what window it reads

Construction rule for all of them: sort by `game_date` inside the group, then `.shift(1)` **before**
any `cumsum` or `rolling`. Nothing full-season, nothing leave-one-out, nothing leave-one-season-out.

| feature | group | window it reads | crosses seasons? |
|---|---|---|---|
| `pl_games_prior` | (season, player) | count of appearances in games strictly before this date | no |
| `pl_minutes_prior` | (season, player) | sum of minutes in games strictly before this date | no |
| `pl_career_games_prior` | (player) | appearances in all 2021→ games strictly before this date | yes, backwards only |
| `pl_prior_season_games` | (player) | `career_prior − season_prior` | yes, backwards only |
| `pl_is_rookie_window` | (player) | 1 if zero appearances in any earlier season in-window | yes, backwards only |
| `pl_min_mean5` / `pl_fga_mean5` / `pl_pts_mean5` / `pl_usg_mean5` | (season, player) | mean over the last ≤5 **prior appearances**, min 3 | no |
| `pl_min_sd5` / `pl_fga_sd5` / `pl_pts_sd5` / `pl_usg_sd5` | (season, player) | sd over the last ≤5 prior appearances, min 3 | no |
| `pl_min_cv5` | (season, player) | `pl_min_sd5 / pl_min_mean5` | no |
| `pl_min_rng5` | (season, player) | max−min of minutes over the last ≤5 prior appearances | no |
| `pl_min_trend5` / `pl_abs_min_trend5` | (season, player) | mean(prior 2) − mean(the 3 before those) | no |
| `pl_start_frac5` | (season, player) | mean `starter_flag` over the last ≤5 prior appearances | no |
| `pl_start_switch5` | (season, player) | count of starter-status changes among the last ≤5 prior appearances | no |
| `pl_rest_days` | (season, player) | days since the player's own last **appearance** (**as-played dates**) | no |
| `pl_teamgames_since_appear` | (season, player, team) | team-game index now − team-game index at the player's last appearance − 1 | no |
| `pl_dnp_frac5` | (season, player, team) | 1 − mean(appeared) over the team's last ≤5 prior games, min 3 | no |
| `tm_game_idx` | (season, team) | count of the team's games strictly before this one | no |
| `tm_rest_days`, `tm_b2b`, `tm_3in4`, `tm_games_prior7d` | (season, team) | gaps/counts over the team's strictly prior game dates (**as-played dates**) | no |
| `opp_rest_days`, `opp_game_idx` | (season, opponent) | same, joined by (game_id, opponent) | no |
| `tm_rest_diff` | — | `tm_rest_days − opp_rest_days` | no |
| `tm_poss_mean_prior`, `opp_poss_mean_prior` | (season, team) | mean team possessions over strictly prior games | no |
| `tm_roster_churn_prior` | (season, team) | 1 − Jaccard( roster of game *i−1*, roster of game *i−2* ) | no |
| `tm_newfaces_prior` | (season, team) | players in game *i−1*'s box who never appeared for the club in games 0…*i−2* | no |
| `tm_five_tenure_prior` | (season, team) | run length of the identical starting five ending at game *i−1* | no |
| `tm_five_changed_prior` | (season, team) | 1 if the starting five of game *i−1* ≠ that of game *i−2* | no |
| `tm_prior_meetings`, `tm_first_meeting` | (season, team, opponent) | count of same-season meetings strictly before this game | no |
| `tm_is_home` | — | contract field, known pre-game | — |
| `<target>__pred_point / pred_sd / pred_q* / pred_width / pred_iqr / pred_cv / is_fallback / fallback_level / is_cold_start / n_prior_games` | — | emitted by the v15 forecast itself; pre-game by construction | — |
| `ref_<target>` (reference forecast, not a candidate) | (season, player) | expanding mean of the player's **prior** appearances; cold rows fall back to the league mean over games strictly earlier in the season | no |

**Date provenance, stated plainly.** Every rest / back-to-back / third-in-four / games-in-7-days
field above is computed from **AS-PLAYED game dates**. No scheduled-date artifact exists in this
repo — `prediction_contract_v4.scheduled_tip_time` is `NaT` with `tip_time_quality = "none"`
throughout the screened seasons. These are as-played fields and are not described as scheduled
anywhere in `FINDINGS.json`.

---

## 5. Nulls

Classical *t* is computed but never trusted on its own. Two permutation nulls are built, plus the
naive row-level one for contrast. All permute the **assignment of an already-computed value**;
nothing is recomputed inside a draw. 1000 draws, seed 20260807, shared across every candidate and
every dependent so the max-|t| family-wise statistic is valid.

- **BETWEEN-block** — whole (season, player_id) or (season, team_id) blocks are reassigned to other
  blocks inside the same season, cycling when lengths differ. 475 player-season blocks, 36
  team-season blocks.
- **WITHIN-block** — values are shuffled inside each block, so the block's *level* survives and only
  the game-to-game alignment dies.
- **ROW (naive)** — reported only to show how much too narrow it is.

**Choosing between them is not optional and it is not a matter of taste.** Applying the wrong one
is not a null at all: a candidate that varies mostly *within* a player-season keeps almost its
entire effect under between-block reassignment, and vice versa. So each candidate is assigned the
null matching where its variance actually lives (`var_share_between_blocks > 0.5` → between-block,
else within-block; 23 candidates went one way, 35 the other). Both p-values are printed for every
cell so the mismatched-null p ≈ 1 columns are visible rather than hidden.

**Inflation factor (correct-level null sd ÷ naive row-level null sd):** median **1.40**, 5th–95th
percentile **0.95–2.36**, full range **0.58–2.89**, and it exceeds 1 in **84 %** of cells. Split by
level, the between-block null runs 1.00–2.89 (median 1.99) and the within-block null 0.58–2.18
(median 1.13). That reproduces the program's known 1.00–3.82× finding for block-level state, and it
also shows the honest tail: for a handful of within-block candidates the correct null is *narrower*
than the naive one, so the naive null is not uniformly anticonservative — it is simply the wrong
null, in whichever direction. Cluster-robust sandwich SEs were **not** used as a substitute; this
program has already found them unreliable in both directions.

**Family-wise.** 6 dependents × 58 candidates = 348 cells. Observed max |t| = 41.61 against a
correct-level max-|t| null whose own maximum over 1000 draws is 30.32 → family-wise p = 0.0000. The
screen as a whole survives. Restricted to the three |residual| dependents: observed max |t| = 39.35,
family-wise p = 0.0000. Per-cell family-wise p is in `screen_results.csv`; most cells do **not**
clear it, which is the honest picture.

**Defective no-op placebo — run on purpose, as a positive diagnostic.** The defective control
permutes the block key and then looks the value up by the *original* key, so the shuffled label is
never consulted. On the probe cell `pl_games_prior → |resid_minutes|` (real *t* = −15.270403) it
reproduced the real number on all 200 draws with max deviation **exactly 0.000e+00** and sd
**exactly 0.000000** — the known signature. The live block control on the same cell moved to mean
*t* = −11.23 with sd 1.046. The real permutation genuinely shuffles.

**R² convention (D069).** Plain unweighted OLS R² = 1 − SSE/SST with SST about the **unweighted**
mean. No weighting anywhere in this screen. The defective form
`sst = sum((sqrt(w)*y − mean(sqrt(w)*y))**2)` does not appear.

---

## 6. What the screen found

### The volume confound, before anything else

|residual| on a counting stat scales with the player's volume. **Any** rule that abstains on
high-volume player-games cuts pooled MAE while carrying zero information. `pts__pred_point` is the
proof: abstaining on its worst quartile cuts points MAE by **9.9 %** and moves skill by **+0.00007**.
Raw MAE reduction is not evidence of a conditional edge. Every abstention curve here is reported in
skill against the point-in-time prior-mean reference, which absorbs the confound. Two candidates
with large |t| — `pl_min_sd5` and `pl_min_cv5` — are caught by this: they have *negative* skill gain
at every coverage in every season. They are volume proxies wearing a volatility label.

### The single most useful table in the screen

Player-games in quintiles of prior same-season appearances:

| depth quintile | n | median prior games | fallback rate | minutes MAE | ref MAE | **minutes skill** | **points skill** |
|---|---|---|---|---|---|---|---|
| Q1 (thinnest) | 2778 | 3 | 38.2 % | 6.573 | 5.711 | **−15.1 %** | **−6.6 %** |
| Q2 | 2894 | 10 | 0 % | 4.735 | 4.882 | +3.0 % | +0.4 % |
| Q3 | 2961 | 17 | 0 % | 4.696 | 5.216 | +10.0 % | +1.6 % |
| Q4 | 2552 | 25 | 0 % | 4.622 | 5.195 | +11.0 % | +2.3 % |
| Q5 (deepest) | 2694 | 35 | 0 % | 4.765 | 5.347 | +10.9 % | +1.6 % |

The pooled +3.6 % minutes skill is an average over one quintile where the model is **worse than a
naive prior mean** and four where it is worth about +10 %. That is policy 13.5's claim in this
repo's own numbers.

### Abstention: error versus coverage

Ranked by usable skill gain, not by *t*.

**1. Abstain on thin prior same-season history** (`pl_games_prior`, minutes). Threshold at 75 %
coverage is "≥ 8 prior appearances".

| coverage | n kept | minutes MAE | ref MAE | skill | MAE cut |
|---|---|---|---|---|---|
| 1.00 | 13879 | 5.080 | 5.267 | +3.55 % | — |
| 0.90 | 12491 | 4.700 | 5.107 | +7.97 % | 7.5 % |
| **0.75** | 10409 | 4.720 | 5.185 | **+8.97 %** | 7.1 % |
| 0.60 | 8327 | 4.698 | 5.250 | +10.51 % | 7.5 % |
| 0.50 | 6940 | 4.706 | 5.272 | +10.73 % | 7.3 % |
| 0.25 | 3470 | 4.682 | 5.238 | +10.62 % | 7.8 % |

Per-season skill gain at 75 % coverage: **+4.24 pts (2022), +5.15 (2023), +6.75 (2024)** — positive
and monotone in every season separately. Note the curve **saturates around 60 % coverage**; there is
no reason to abstain harder than that.

**2. Abstain when the model fell back off its primary estimator** (`is_fallback`, minutes). Free —
the model already emits the flag. Minutes error doubles on those rows (worst decile 8.657 vs best
4.318). At 90 % coverage skill goes +3.55 % → +7.84 %. Per-season gain +3.14 / +4.02 / +4.03.
**But it is nested inside lead 1**: fallback rate is 29.1 % in the bottom `games_prior` quartile and
**exactly 0 %** in the other three, so the composite "fallback OR thin" rule is numerically
identical to `games_prior` alone. The depth gradient nevertheless **survives inside the non-fallback
rows** (skill 7.99 % → 9.66 % at 75 % → 10.69 % at 60 %), so it is not merely a restatement of the
flag.

**3. Abstain on wide predictive intervals for points** (`pts__pred_width` = q95−q05). The only
pre-game state that turns the points model from negative to positive skill: −0.22 % → +1.28 % at
75 %, +3.17 % at 50 %, +5.06 % at 25 %. Positive in all three seasons (+1.64 / +1.06 / +2.42).
Small, but it is the only thing that works on points at all. Note that `pred_sd` does **not** work
(skill gain ≈ 0 at every coverage) while the quantile **width** does — that is itself a finding
about the v15 uncertainty head.

**4. A debutant played for the team in its last prior game** (`tm_newfaces_prior`, minutes).
Worst-vs-best decile 6.913 vs 4.478 minutes (ratio 1.54), *t* = +19.27, and it **survives**
conditioning on both `pl_games_prior` and `tm_game_idx` (*t* = +16.35, ΔR² +0.0186) so it is not an
early-season artefact. But its abstention skill gain at 75 % coverage is only **+0.008**: the naive
reference is hurt there almost as much as the model is. **It predicts error without predicting
differential skill.** Worth a look as a variance feature; useless as an abstention rule. This
distinction is the most transferable methodological point in the screen.

### What died

- **Schedule state** — rest days, back-to-back, third-in-four, games-in-prior-7-days, opponent rest,
  rest differential. Eighteen cells; the largest |t| is 7.46 and decile ratios sit in 0.94–1.25
  with no consistent sign across targets. `tm_b2b` and `tm_3in4` are flatly null on points and FGA
  (p 0.34–0.94 at the correct level). Nothing here.
- **Opponent unfamiliarity** — first meeting vs later meetings, prior-meeting count. Loses
  essentially all of its effect once depth and team-game index are held fixed (ΔR² added ≤ 0.0006).
  It was an early-season proxy.
- **Roster churn / starting-five stability** — Jaccard churn |t| ≤ 2.24, five-tenure |t| ≤ 8.63 and
  pointing the *wrong* way for a stability story, five-changed |t| ≤ 3.30. Only `tm_newfaces_prior`
  survives, and only as a variance signal.
- **Home/away** — null on all three targets (p 0.19–0.83).
- **Role volatility as a standalone edge** — see the volume confound above.
- **Player rest / games-since-return / DNP fraction** — small and inconsistent in sign across
  targets; `pl_dnp_frac5` is the best of them and its abstention skill gain is +0.003 to +0.013.

**The attrition, counted honestly.** Of the 174 candidate × |residual| cells, **115 clear p < 0.05
at the correct level** — which sounds like a lot until you apply the family. Only **20 cells across
14 candidates** clear the family-wise max-|t| correction on the |residual| family, and of those 14,
ten are volume proxies (`pred_point`, `pl_*_mean5`, `pl_start_frac5`). **Three** survive both the
family and the volume test: `is_fallback` / `fallback_level` (minutes) and `pts__pred_width`
(points). Add `pl_games_prior`, which fails family-wise (|t| = 15.3 against a family max of 41.6)
but carries by far the largest *skill* gain, and the usable leads from a 58-candidate screen number
**four**. That is the expected E0 yield.

---

## 7. Where I could have cheated — and whether I chose before or after seeing the result

Chosen **before** seeing any result:

- Dependent quantities (|residual| and residual²), the three targets, the 2021–2024 partition, the
  permutation-draw count (1000) and the seed (20260807).
- Excluding 2021: decided from `fold_receipt__2021.json` (`n_train_rows = 0`,
  `model_was_fitted = false`) before any residual was computed.
- Restricting to rows where the player appeared and all three targets are outcome-scoreable.
- The candidate list. It was written out in full before the first regression ran and **no candidate
  was added or dropped after seeing its effect**. `tm_newfaces_prior` initially came out constant
  because of a genuine off-by-one in the `seen`-set update; that was a bug fix, not a
  post-hoc addition, and the fix is visible in `rh_base.build_team_pregame`.
- The abstention coverage grid (1.00 / 0.90 / 0.80 / 0.75 / 0.60 / 0.50 / 0.40 / 0.25 / 0.10).
- Using within-season median imputation with complete-case robustness reported alongside.

Chosen **after** seeing results — declared, because each of these is a place I could have flattered
the screen:

- **The skill-against-reference metric.** I built the point-in-time prior-mean reference in the same
  script as the frame, before running the screen, but I *promoted it to the headline metric* after
  seeing that `pts__pred_point` produced a 9.9 % MAE cut with no information in it. That promotion
  makes the results look **worse**, not better, and it killed two of my own candidates
  (`pl_min_sd5`, `pl_min_cv5`). Declared anyway.
- **The WITHIN-block null.** My first pass used only between-block reassignment, in line with the
  house `perm_block` helper. I added the within-block null after seeing that the between-block
  max-|t| null had a mean of 21.7, which is not a null for a within-block-varying candidate. This
  change made the correct-level nulls **wider** for 35 of 58 candidates and raised several
  p-values. Also declared.
- **The rank-ordering of the abstention rules.** I ordered the leads by skill gain, not by |t|,
  after seeing that the |t| ordering was dominated by volume. If ordered by |t| the headline would
  have been `pts__pred_point`, which is worthless.
- **`tm_newfaces_prior` as a "variance not skill" finding.** I only framed it that way after seeing
  its abstention curve. Its earlier framing in my own notes was "roster stability died", which was
  wrong and is corrected in `FINDINGS.json`.

Places I could have cheated and consciously did not:

- I did not open `player_game_availability.csv`, which is the single easiest way to make an
  availability screen look good, and which is contaminated.
- I did not use the `minutes_baselines` test predictions, which would have given me a second
  residual set for minutes, because that CSV has **no sibling manifest** and its test seasons run
  into the holdout.
- I did not screen any candidate computed from the target game's own box score. Several tempting
  ones — "how many rotation players are out tonight" — are only reconstructible from the target box
  in this repo, which is a retrospective baseline dressed as a pre-game state. They are absent.
- I did not report only per-candidate p-values. A 58-candidate screen that reports only those is a
  lottery ticket.
- Deciles are taken on within-season ranks with `method='first'`, which splits binaries cleanly but
  breaks ties by row order. For binaries the decile means are therefore "all-zero rows vs all-one
  rows", not a true decile. Stated here because it flatters binary candidates' apparent spread.

---

## 8. Files

| file | what |
|---|---|
| `FINDINGS.json` | all 348 cells, nulls, family-wise, spreads, abstention curves, R² convention, manifest checks |
| `NOTES.md` | this file |
| `rh_base.py` | loaders, guards, feature builders, null machinery |
| `s03_build_frame.py` → `analysis_frame.parquet`, `step1_provenance.json` | provenance + frame |
| `s04_screen.py` → `screen_results.csv`, `familywise_summary.json`, `maxt_null_draws*.csv`, `permutation_nulls.npz` | the screen |
| `s05_abstention.py` → `abstention_curves.csv`, `abstention_per_season.csv`, `abstention_composite_minutes.csv`, `abstention_games_prior_within_nonfallback.csv`, `noop_placebo*.{json,csv}`, `complete_case_robustness.csv` | step 3 + placebo |
| `s06_findings.py` | assembles `FINDINGS.json` |
| `s07_family_table.py` → `family_summary.csv` | per-family verdicts |
| `s08_conditioning.py` → `lead_correlations.csv`, `depth_quintile_table.csv` | do the leads collapse onto one axis |
| `run_log*.txt` | full console output of every step |

---

## 9. What a follow-up should ask

1. **The rebound and assist gap.** The v15 arm emits no forecast for them. D051's residual
   characterisation is incomplete until it does.
2. **Is the depth effect a data effect or a model effect?** The model has *negative* skill in the
   thinnest quintile. Either the estimator's cold-start path is actively harmful, or ~8 prior
   appearances is simply the point where any estimator beats a running mean. A cheap discriminator:
   replace the cold-start path with the running mean and see whether Q1 skill goes to 0 or to +.
3. **Why does `pred_width` work on points when `pred_sd` does not?** That is a question about the
   v15 uncertainty head, and it is the only lever this screen found on the points target.
4. **`tm_newfaces_prior` as a variance feature**, not an abstention rule.
