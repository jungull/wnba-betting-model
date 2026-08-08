# Manifest remediation plan - the 68 unmanifested shared artifacts

**No manifest was written by this analysis.** This is a plan. Writing a manifest asserts a
provenance claim about someone else's artifact, and a wrong one is worse than a missing one
because it converts *unverifiable* into *falsely verified*.

Input: `experiments/exploration/AUDIT_baseline_provenance/MISSING_MANIFESTS.json`.
Classification method: producers located by scanning 762 `.py` files, then the build code was
**read** and the construction line quoted. Regex only ever located candidates; no text match
stands as a finding. Lineage was traced through inputs, so inherited granularity is captured.

## The headline

| | count |
|---|---|
| Artifacts in scope | 68 |
| **Live contamination** (artifact-granular AND embeds 2025/2026 AND live) | **6** |
| **Safe / honestly bounded - needs only a manifest** | **34** |
| **Undetermined - needs a human decision** | **15** |
| **Dead / unused - ignorable** | **13** |

Proposed granularity: **25 ROW**, **30 ARTIFACT**, **13 UNDETERMINED**.
Confidence: 36 HIGH, 19 MEDIUM, 13 NONE. 12 of the 68 are consumed by a PASSED graph node.

### The single most useful distinction in this document

Thirty of the 68 are artifact-granular, but they are **not all contaminated**. They split three ways:

- **6 embed holdout data** (`SPANS_HOLDOUT`). All six inherit from `cbs_v15_player_oof_v5`
  prediction files whose own manifests already declare `asof_granularity: "artifact"`. This is
  the real-contamination set.
- **10 pool across rows but only inside 2021-2024** (`PARTITION_ONLY_LOOKAHEAD`). Every one of
  these is an exploration frame whose build script hard-filters to the partition on **column**
  **values** before it pools anything. A 2021 row in these files cannot contain 2026 information.
  They are still not `row`-granular and must not be manifested as such - but they need no re-run.
- **25 are capture logs, static dimensions or realised-outcome targets** with no pooling at all.

**In short: the sweep found no new holdout contamination.** The six `SPANS_HOLDOUT` artifacts all
trace to one already-known and already-declared source. The rest of the artifact-granular set is
a paperwork problem, and a good deal of the paperwork can say `row` honestly.

## Priority ranking (consumers x liveness)

Liveness resolved two ways: from `PROGRAM_GRAPH.json` + `GRAPH_STATE.json` node status (86 PASSED
of 104 nodes), and - for the exploration lane, which no graph node names - from
`experiments/idea_log.jsonl` lead verdicts. Live leads: **I0004, I0009, I0011, I0014**.
Dead leads: **I0008, I0010, I0012, I0013**.

| # | consumers | liveness | granularity | conf | group | artifact |
|---|---|---|---|---|---|---|
| 1 | 11 | LIVE | ARTIFACT | HIGH | 2 | `experiments/exploration/E0_I0011_tendency_estimator/frame.parquet` |
| 2 | 11 | LIVE | ARTIFACT | HIGH | 2 | `experiments/exploration/E1_I0004_rim_finishing/_validate_sandbox/frame.parquet` |
| 3 | 11 | LIVE | ARTIFACT | HIGH | 2 | `experiments/exploration/E1_I0011_split_alpha/frame.parquet` |
| 4 | 9 | LIVE | ARTIFACT | HIGH | 2 | `experiments/exploration/E0_I0009_additive_pressure/player_game_analysis.csv` |
| 5 | 9 | LIVE | ARTIFACT | HIGH | 2 | `experiments/exploration/E1_I0009_additive_pressure/player_game_analysis.csv` |
| 6 | 8 | LIVE | ARTIFACT | HIGH | 2 | `experiments/exploration/E0_I0009_additive_pressure/team_game_defense.csv` |
| 7 | 8 | LIVE | ARTIFACT | HIGH | 2 | `experiments/exploration/E1_I0009_additive_pressure/team_game_defense.csv` |
| 8 | 7 | LIVE | ROW | HIGH | 2 | `experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet` |
| 9 | 6 | LIVE | ROW | HIGH | 2 | `data/reference/team_cities.csv` |
| 10 | 11 | DEAD | ARTIFACT | HIGH | 2 | `experiments/exploration/E1_I0008_height_mismatch/frame.parquet` |
| 11 | 7 | LIVE-ADJACENT | ROW | HIGH | 2 | `experiments/player_program/turnover_targets_v1/player_turnover_targets_v1.parquet` |
| 12 | 5 | LIVE | ROW | HIGH | 2 | `data/props_capture/historical/master_props_historical.csv` |
| 13 | 9 | DEAD | ARTIFACT | HIGH | 2 | `experiments/exploration/E0_I0005_turnover_interaction/player_game_analysis.csv` |
| 14 | 6 | LIVE-ADJACENT | ROW | HIGH | 2 | `experiments/player_program/turnover_targets_v1/team_turnover_reconciliation_v1.parquet` |
| 15 | 6 | LIVE-ADJACENT | ROW | HIGH | 2 | `experiments/prediction_contract_v5/player_game_enriched.parquet` |
| 16 | 4 | LIVE | ARTIFACT | HIGH | 2 | `experiments/exploration/E1_I0004_rim_finishing/_validate_sandbox/grid_metrics.parquet` |
| 17 | 5 | LIVE-ADJACENT | ROW | MEDIUM | 2 | `data/possessions/possessions.parquet` |
| 18 | 4 | LIVE-ADJACENT | ROW | MEDIUM | 2 | `data/reference/player_bios.csv` |
| 19 | 3 | LIVE | ROW | HIGH | 2 | `experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet` |
| 20 | 4 | LIVE-ADJACENT | ROW | HIGH | 2 | `experiments/player_program/possessions_v2/possessions_raw_v2.parquet` |

Note on the top of the table: the four 11-consumer `frame.parquet` files are only **three**
distinct artifacts. `E1_I0004_rim_finishing/_validate_sandbox/frame.parquet` is byte-identical
(sha256 `311BFDA2...`) to `E1_I0011_split_alpha/frame.parquet`; the same holds for the two
`grid_metrics.parquet` copies (`D6580165...`). 68 paths, 66 distinct contents.

## Group 1. LIVE CONTAMINATION - needs a re-run or a scope decision, not just paperwork

6 artifacts.

These are artifact-granular **and** embed 2025/2026 inputs **and** are consumed by
something in the live player-program lineage. They are the ones where a manifest alone is
not the whole answer.

All six share one root cause, which is the useful part: `build_projected_exposure.py`
globs **every** season of `experiments/cbs_v15_player_oof_v5/attempt_001/` -
`predictions__p_active__*.parquet` and `predictions__e_minutes_given_active__*.parquet`,
2021 through 2026 - and those files' own manifests already say
`"asof_granularity": "artifact"`. Everything downstream inherits it.

**The mitigating fact, which must not be lost when this is fixed:** each per-season
prediction file was fit only on *strictly prior* seasons. The 2024 file's manifest reads
`fit_seasons: [2021, 2022, 2023]`. So a 2021 row did **not** see 2026 - the chain is
walk-forward, not pooled. The binary `row`/`artifact` vocabulary simply cannot express
"bounded by the start of its own season", which is what these actually are. That is a
convention decision for a human (see group 3), and it determines whether these need a
re-run at all or just an honest manifest plus a note.

| artifact | cons | granularity | conf | holdout risk | remedy | cost |
|---|---|---|---|---|---|---|
| `experiments/player_program/projected_exposure_v1/projected_player_possessions_v1.parquet` | 4 | ARTIFACT | HIGH | SPANS_HOLDOUT | manifest-only | 15 min |
| `experiments/player_program/turnover_p1_v1/turnover_p1_predictions_intrinsic.parquet` | 3 | ARTIFACT | HIGH | SPANS_HOLDOUT | manifest-only | 10 min |
| `experiments/player_program/fits_v1/p3_coefficients_v1.parquet` | 2 | ARTIFACT | HIGH | SPANS_HOLDOUT | manifest-only | 15 min |
| `experiments/player_program/projected_exposure_v1/projected_team_rotations_v1.parquet` | 2 | ARTIFACT | HIGH | SPANS_HOLDOUT | manifest-only | 10 min |
| `experiments/player_program/turnover_p1_v1/turnover_p1_predictions_operational_corrected.parquet` | 1 | ARTIFACT | HIGH | SPANS_HOLDOUT | manifest-only | 10 min |
| `experiments/player_program/turnover_p2_v1/turnover_role_context_features_v1.parquet` | 1 | ARTIFACT | HIGH | SPANS_HOLDOUT | manifest-only | 10 min |

## Group 2. SAFE / HONESTLY-BOUNDED - needs only a manifest

34 artifacts.

Nothing here needs to be rebuilt. Each needs a sibling `<artifact>.manifest.json` stating
the granularity below. Note that **a good number of these are `ARTIFACT`** - that is the
correct, honest declaration, not a failure. An `ARTIFACT` label with
`holdout_risk: PARTITION_ONLY_LOOKAHEAD` tells a future screen exactly what it needs to know.

| artifact | cons | granularity | conf | holdout risk | remedy | cost |
|---|---|---|---|---|---|---|
| `experiments/exploration/E0_I0011_tendency_estimator/frame.parquet` | 11 | ARTIFACT | HIGH | PARTITION_ONLY_LOOKAHEAD | manifest-only | 5 min |
| `experiments/exploration/E1_I0004_rim_finishing/_validate_sandbox/frame.parquet` | 11 | ARTIFACT | HIGH | PARTITION_ONLY_LOOKAHEAD | manifest-only | 2 min |
| `experiments/exploration/E1_I0011_split_alpha/frame.parquet` | 11 | ARTIFACT | HIGH | PARTITION_ONLY_LOOKAHEAD | manifest-only | 5 min |
| `experiments/exploration/E1_I0008_height_mismatch/frame.parquet` | 11 | ARTIFACT | HIGH | PARTITION_ONLY_LOOKAHEAD | manifest-only | 5 min |
| `experiments/exploration/E0_I0009_additive_pressure/player_game_analysis.csv` | 9 | ARTIFACT | HIGH | PARTITION_ONLY_LOOKAHEAD | manifest-only | 10 min |
| `experiments/exploration/E1_I0009_additive_pressure/player_game_analysis.csv` | 9 | ARTIFACT | HIGH | PARTITION_ONLY_LOOKAHEAD | manifest-only | 10 min |
| `experiments/exploration/E0_I0005_turnover_interaction/player_game_analysis.csv` | 9 | ARTIFACT | HIGH | PARTITION_ONLY_LOOKAHEAD | manifest-only | 10 min |
| `experiments/exploration/E0_I0009_additive_pressure/team_game_defense.csv` | 8 | ARTIFACT | HIGH | PARTITION_ONLY_LOOKAHEAD | manifest-only | 10 min |
| `experiments/exploration/E1_I0009_additive_pressure/team_game_defense.csv` | 8 | ARTIFACT | HIGH | PARTITION_ONLY_LOOKAHEAD | manifest-only | 10 min |
| `experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet` | 7 | ROW | HIGH | NONE | manifest-only | 5 min |
| `experiments/player_program/turnover_targets_v1/player_turnover_targets_v1.parquet` | 7 | ROW | HIGH | NONE | manifest-only | 5 min |
| `data/reference/team_cities.csv` | 6 | ROW | HIGH | NONE | manifest-only | 5 min |
| `experiments/player_program/turnover_targets_v1/team_turnover_reconciliation_v1.parquet` | 6 | ROW | HIGH | NONE | manifest-only | 5 min |
| `experiments/prediction_contract_v5/player_game_enriched.parquet` | 6 | ROW | HIGH | NONE | manifest-only | 5 min |
| `data/props_capture/historical/master_props_historical.csv` | 5 | ROW | HIGH | NONE | manifest-only | 5 min |
| `data/possessions/possessions.parquet` | 5 | ROW | MEDIUM | NONE | manifest-only | 5 min |
| `experiments/exploration/E1_I0004_rim_finishing/_validate_sandbox/grid_metrics.parquet` | 4 | ARTIFACT | HIGH | PARTITION_ONLY_LOOKAHEAD | manifest-only | 5 min |
| `data/reference/player_bios.csv` | 4 | ROW | MEDIUM | NONE | manifest-only | 15 min |
| `experiments/player_program/possessions_v2/possessions_raw_v2.parquet` | 4 | ROW | HIGH | NONE | manifest-only | 5 min |
| `experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet` | 3 | ROW | HIGH | NONE | manifest-only | 5 min |
| `experiments/market_program/INJURY_OFFICIAL/live/capture_log.csv` | 2 | ROW | HIGH | NONE | manifest-only | 5 min |
| `experiments/player_program/event_contract_v1/canonical_player_events_v1.parquet` | 2 | ROW | HIGH | NONE | manifest-only | 5 min |
| `data/injury_capture/injury_log.csv` | 1 | ROW | HIGH | NONE | manifest-only | 5 min |
| `data/injury_history/injury_history.csv` | 1 | ROW | HIGH | NONE | manifest-only | 5 min |
| `data/ref_assignments/assignments_log.csv` | 1 | ROW | HIGH | NONE | manifest-only | 5 min |
| `experiments/market_program/INJURY_OFFICIAL/live/injury_snapshots.csv` | 1 | ROW | HIGH | NONE | manifest-only | 5 min |
| `experiments/market_program/INJURY_OFFICIAL/live/status_transitions.csv` | 1 | ROW | HIGH | NONE | manifest-only | 5 min |
| `data/masters/master_player.csv` | 1 | ROW | HIGH | NONE | manifest-only | 5 min |
| `data/props_capture/master_props.csv` | 1 | ROW | HIGH | NONE | manifest-only | 5 min |
| `data/reference/tip_times.csv` | 1 | ROW | HIGH | NONE | manifest-only | 5 min |
| `experiments/market_program/SCORE_BASELINES/market_paired_rows.parquet` | 1 | ROW | MEDIUM | NONE | manifest-only | 10 min |
| `experiments/player_program/possessions_v1/possessions_raw_v1.parquet` | 1 | ROW | MEDIUM | NONE | manifest-only | 5 min |
| `experiments/prediction_contract_v5/candidacy_exclusions.parquet` | 1 | ROW | HIGH | NONE | manifest-only | 5 min |
| `experiments/prediction_contract_v5/player_game.parquet` | 1 | ROW | HIGH | NONE | manifest-only | 5 min |

## Group 3. UNDETERMINED - needs a human decision

15 artifacts.

Do not guess these. Two different kinds of unknown are mixed here and they need different
things from a human:

**(a) A vocabulary decision, affecting several artifacts at once.** GRAPH_POLICY defines
`row` as *bounded by the row's own date*. Several artifacts are bounded by the row's own
**season** instead - `team_season_coverage_v1.csv` (one row per team-season), and the
whole walk-forward prediction chain (bounded by the start of its own season). For all of
them, filtering by season **is** sufficient, so the policy's actual purpose is met - but
`row` would be literally false and `artifact` is needlessly disqualifying. One ruling on
whether a season-bounded row counts as `row`, or whether a third value is needed, settles
a large fraction of this backlog at once. **This is the highest-leverage decision in the
document.**

**(b) Genuinely not traced.** 13 legacy game-and-betting-program outputs whose producers
were located but whose build code was not read. No granularity is proposed for them
because none was established. The prior leans ARTIFACT - the H1 hazard already lists two
siblings of this family as contaminated - but a prior is not evidence, and this program
has already paid once for confident guesses.

| artifact | cons | granularity | conf | holdout risk | remedy | cost |
|---|---|---|---|---|---|---|
| `experiments/props_edge/bet_universe_best_line.csv` | 3 | UNDETERMINED | NONE | UNKNOWN | human-decision | 20-40 min each |
| `experiments/props_edge/bet_universe_per_book.csv` | 3 | UNDETERMINED | NONE | UNKNOWN | human-decision | 20-40 min each |
| `experiments/player_program/data_lane/D12_COACHING_HISTORY/team_season_coverage_v1.csv` | 2 | ROW | MEDIUM | NONE | human-decision | 10 min |
| `experiments/channel_reval/channel_base_v2.csv` | 2 | UNDETERMINED | NONE | UNKNOWN | human-decision | 20-40 min each |
| `experiments/channel_reval/channel_results_v2.csv` | 2 | UNDETERMINED | NONE | UNKNOWN | human-decision | 20-40 min each |
| `experiments/clv_transfer/bet_log.csv` | 2 | UNDETERMINED | NONE | UNKNOWN | human-decision | 20-40 min each |
| `experiments/clv_transfer/flat_stake_sim.csv` | 2 | UNDETERMINED | NONE | UNKNOWN | human-decision | 20-40 min each |
| `experiments/totals_groundwork/bookie_totals_per_game.csv` | 2 | UNDETERMINED | NONE | UNKNOWN | human-decision | 20-40 min each |
| `experiments/market_program/M13_PLAYER_VALUE_TRANSLATION/translation_rows.parquet` | 1 | ARTIFACT | MEDIUM | UNKNOWN | human-decision | already in flight |
| `experiments/dist_margin_cover/game_level_dist.csv` | 1 | UNDETERMINED | NONE | UNKNOWN | human-decision | 20-40 min each |
| `experiments/minutes_twostage/test_predictions_m1.csv` | 1 | UNDETERMINED | NONE | UNKNOWN | human-decision | 20-40 min each |
| `experiments/minutes_twostage/test_predictions_m2.csv` | 1 | UNDETERMINED | NONE | UNKNOWN | human-decision | 20-40 min each |
| `experiments/oracle_bracket/game_level_margins.csv` | 1 | UNDETERMINED | NONE | UNKNOWN | human-decision | 20-40 min each |
| `experiments/totals_groundwork/exploratory_bias_fix_per_game.csv` | 1 | UNDETERMINED | NONE | UNKNOWN | human-decision | 20-40 min each |
| `experiments/w2_integration/game_level_predictions.csv` | 1 | UNDETERMINED | NONE | UNKNOWN | human-decision | 20-40 min each |

## Group 4. DEAD or UNUSED - ignorable

13 artifacts.

Housekeeping only. No player-program graph node and no live exploration lead reads these.

| artifact | cons | granularity | conf | holdout risk | remedy | cost |
|---|---|---|---|---|---|---|
| `experiments/exploration/E0_I0014_residual_heterogeneity/screen_results.csv` | 2 | ARTIFACT | MEDIUM | UNKNOWN | manifest-only | 5 min each |
| `experiments/feature_archetypes/survivor_summary.csv` | 2 | ARTIFACT | MEDIUM | UNKNOWN | manifest-only | 5 min each |
| `experiments/feature_interactions/survivor_summary.csv` | 2 | ARTIFACT | MEDIUM | UNKNOWN | manifest-only | 5 min each |
| `experiments/feature_screen/screen_results.csv` | 2 | ARTIFACT | MEDIUM | UNKNOWN | manifest-only | 5 min each |
| `experiments/feature_screen/survivor_summary.csv` | 2 | ARTIFACT | MEDIUM | UNKNOWN | manifest-only | 5 min each |
| `experiments/feature_screen_crossseason/screen_results.csv` | 2 | ARTIFACT | MEDIUM | UNKNOWN | manifest-only | 5 min each |
| `experiments/feature_screen_crossseason/survivor_summary.csv` | 2 | ARTIFACT | MEDIUM | UNKNOWN | manifest-only | 5 min each |
| `experiments/feature_screen_rebaselined/screen_results.csv` | 2 | ARTIFACT | MEDIUM | UNKNOWN | manifest-only | 5 min each |
| `experiments/feature_screen_rebaselined/survivor_summary.csv` | 2 | ARTIFACT | MEDIUM | UNKNOWN | manifest-only | 5 min each |
| `experiments/feature_screen_run2/screen_results.csv` | 2 | ARTIFACT | MEDIUM | UNKNOWN | manifest-only | 5 min each |
| `experiments/feature_screen_run2/survivor_summary.csv` | 2 | ARTIFACT | MEDIUM | UNKNOWN | manifest-only | 5 min each |
| `experiments/volume_heterogeneity/screen_results.csv` | 2 | ARTIFACT | MEDIUM | UNKNOWN | manifest-only | 5 min each |
| `experiments/volume_heterogeneity/survivor_summary.csv` | 2 | ARTIFACT | MEDIUM | UNKNOWN | manifest-only | 5 min each |

## Evidence, per artifact

Every classification below is backed by a line that was read. A classification without a quoted
line is not evidence, so entries with no quote are reported as UNDETERMINED.

### 1. `experiments/exploration/E0_I0011_tendency_estimator/frame.parquet`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk PARTITION_ONLY_LOOKAHEAD)
- Consumers: 11. LIVE: feeds exploration lead I0011 -- LIVE (keep-as-lead x3)
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

Pooled HOME_MULT/MEAN_POSS/fallback means are estimated on the SELECTION seasons 2021-2022 and frozen. That is a genuine pooled step, so the file is NOT row-granular. It is also filtered to the partition BEFORE any pooling, so no 2025/2026 value can reach a row. The prior-season merge at line 152-154 uses the season+1 offset and is legitimate.

Evidence:

- `experiments/exploration/E0_I0011_tendency_estimator/build_frame.py:109`
  ```
  h = sel.loc[sel["is_home"] == 1, s].mean()   # HOME_MULT pooled over ALL of 2021-2022
  ```
- `experiments/exploration/E0_I0011_tendency_estimator/build_frame.py:115`
  ```
  MEAN_POSS = float(sel["game_poss"].mean())   # single pooled constant
  ```
- `experiments/exploration/E0_I0011_tendency_estimator/build_frame.py:161`
  ```
  df["prior_" + s] = df["prior_" + s].fillna(float(sel[s].mean()))  # pooled fallback
  ```
- `experiments/exploration/E0_I0011_tendency_estimator/build_frame.py:154`
  ```
  prior["season"] = prior["season"] + 1   # LEGITIMATE season offset: full-season mean of S applied to S+1
  ```
- `experiments/exploration/E0_I0011_tendency_estimator/build_frame.py:33`
  ```
  tm = tm[tm["season"].isin(PARTITION)].copy()   # FILTER-POINT before any pooling
  ```

### 2. `experiments/exploration/E1_I0004_rim_finishing/_validate_sandbox/frame.parquet`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk PARTITION_ONLY_LOOKAHEAD)
- Consumers: 11. LIVE: feeds exploration lead I0004 -- LIVE (SCREENED_LEAD_REFRAMED)
- Remedy: **manifest-only**, estimated cost 2 min. Group 2.

Not an independently built artifact: a byte-identical copy of the E1_I0011 frame placed in the rim-finishing baseline-validation sandbox. Inherits that file's classification exactly.

Evidence:

- `(sha256 comparison)`
  ```
  BYTE-IDENTICAL to E1_I0011_split_alpha/frame.parquet, sha256 311BFDA27F6D97EF...
  ```

### 3. `experiments/exploration/E1_I0011_split_alpha/frame.parquet`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk PARTITION_ONLY_LOOKAHEAD)
- Consumers: 11. LIVE: feeds exploration lead I0011 -- LIVE (keep-as-lead x3)
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

Every predictor column is strictly-prior (shift(1)+expanding, cumcount). The ONLY pooled step is the `half` column: a within-season game_date median over the whole season. That is a within-partition look-ahead, not holdout contamination -- the file is filtered to 2021-2024 at line 55 before the median is taken. Declaring 'row' would be false because of `half`.

Evidence:

- `experiments/exploration/E1_I0011_split_alpha/build_frame.py:83`
  ```
  med = mp.groupby("season")["game_date"].transform("median")  # season-pooled split point
  ```
- `experiments/exploration/E1_I0011_split_alpha/build_frame.py:55`
  ```
  mp = mp[mp["season"].isin(PARTITION)].copy()   # FILTER-POINT (immediately after load)
  ```
- `experiments/exploration/E1_I0011_split_alpha/build_frame.py:76`
  ```
  mp["std_minutes"] = (g["minutes"].shift(1)... expanding(1).mean())  # strictly prior, clean
  ```

### 4. `experiments/exploration/E0_I0009_additive_pressure/player_game_analysis.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk PARTITION_ONLY_LOOKAHEAD)
- Consumers: 9. LIVE: feeds exploration lead I0009 -- LIVE (SCREENED_LEAD_MAGNITUDE_CORRECTED; strongest surviving lead)
- Remedy: **manifest-only**, estimated cost 10 min. Group 2.

TWO independent season-pooling steps. (1) The `*_loo` columns are whole-season-minus-this-game leave-one-out -- they read LATER games in the same season; the script labels them 'hindsight; NOT pregame-observable'. (2) The `*_pregame` columns, despite the name, are shrunk toward an anchor that is the CURRENT season's full-season league mean whenever no prior season exists, and ALWAYS for defrtg. Both are confined to 2021-2024 by hard column-value asserts, so this is within-partition look-ahead, not holdout contamination. The file must not be manifested 'row'.

Evidence:

- `experiments/exploration/E0_I0009_additive_pressure/build_data.py:163`
  ```
  # 4a. E0-comparable LOO tendency (hindsight; NOT pregame-observable)
  ```
- `experiments/exploration/E0_I0009_additive_pressure/build_data.py:167`
  ```
  tov["loo_poss"] = tov["season_poss"] - tov["realised_off_possessions"]
  ```
- `experiments/exploration/E0_I0009_additive_pressure/build_data.py:116`
  ```
  tot = (team_game.groupby(["team_id","season"]).agg(s_poss=("def_poss","sum"), ...))
  ```
- `experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py:39`
  ```
  lg = team_game.groupby("season").agg(p=("def_poss","sum"), t=("def_tov","sum"), ...)
  ```
- `experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py:55`
  ```
  self.anchor[(team, season)] = self.league_mean[season]   # CURRENT season full-season mean
  ```
- `experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py:97`
  ```
  anchor = self.league_pts_mean[season]   # defrtg always shrunk to the current season league mean
  ```

### 5. `experiments/exploration/E1_I0009_additive_pressure/player_game_analysis.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk PARTITION_ONLY_LOOKAHEAD)
- Consumers: 9. LIVE: feeds exploration lead I0009 -- LIVE (SCREENED_LEAD_MAGNITUDE_CORRECTED; strongest surviving lead)
- Remedy: **manifest-only**, estimated cost 10 min. Group 2.

TWO independent season-pooling steps. (1) The `*_loo` columns are whole-season-minus-this-game leave-one-out -- they read LATER games in the same season; the script labels them 'hindsight; NOT pregame-observable'. (2) The `*_pregame` columns, despite the name, are shrunk toward an anchor that is the CURRENT season's full-season league mean whenever no prior season exists, and ALWAYS for defrtg. Both are confined to 2021-2024 by hard column-value asserts, so this is within-partition look-ahead, not holdout contamination. The file must not be manifested 'row'.

Evidence:

- `experiments/exploration/E1_I0009_additive_pressure/build_data.py:163`
  ```
  # 4a. E0-comparable LOO tendency (hindsight; NOT pregame-observable)
  ```
- `experiments/exploration/E1_I0009_additive_pressure/build_data.py:167`
  ```
  tov["loo_poss"] = tov["season_poss"] - tov["realised_off_possessions"]
  ```
- `experiments/exploration/E1_I0009_additive_pressure/build_data.py:116`
  ```
  tot = (team_game.groupby(["team_id","season"]).agg(s_poss=("def_poss","sum"), ...))
  ```
- `experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py:39`
  ```
  lg = team_game.groupby("season").agg(p=("def_poss","sum"), t=("def_tov","sum"), ...)
  ```
- `experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py:55`
  ```
  self.anchor[(team, season)] = self.league_mean[season]   # CURRENT season full-season mean
  ```
- `experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py:97`
  ```
  anchor = self.league_pts_mean[season]   # defrtg always shrunk to the current season league mean
  ```

### 6. `experiments/exploration/E0_I0009_additive_pressure/team_game_defense.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk PARTITION_ONLY_LOOKAHEAD)
- Consumers: 8. LIVE: feeds exploration lead I0009 -- LIVE (SCREENED_LEAD_MAGNITUDE_CORRECTED; strongest surviving lead)
- Remedy: **manifest-only**, estimated cost 10 min. Group 2.

Same two pooling steps as its player-level sibling: season LOO columns plus a current-season full-season league anchor in the shrinkage. Partition-asserted on column values.

Evidence:

- `experiments/exploration/E0_I0009_additive_pressure/build_data.py:116`
  ```
  tot = (team_game.groupby(["team_id","season"]).agg(s_poss=("def_poss","sum"), ...))
  ```
- `experiments/exploration/E0_I0009_additive_pressure/build_data.py:120`
  ```
  loo_poss = team_game["s_poss"] - team_game["def_poss"]
  ```
- `experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py:97`
  ```
  anchor = self.league_pts_mean[season]
  ```
- `experiments/exploration/E0_I0009_additive_pressure/build_data.py:109`
  ```
  assert set(team_game["season"].unique()).issubset(set(EXPLORATION_SEASONS))
  ```

### 7. `experiments/exploration/E1_I0009_additive_pressure/team_game_defense.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk PARTITION_ONLY_LOOKAHEAD)
- Consumers: 8. LIVE: feeds exploration lead I0009 -- LIVE (SCREENED_LEAD_MAGNITUDE_CORRECTED; strongest surviving lead)
- Remedy: **manifest-only**, estimated cost 10 min. Group 2.

Same two pooling steps as its player-level sibling: season LOO columns plus a current-season full-season league anchor in the shrinkage. Partition-asserted on column values.

Evidence:

- `experiments/exploration/E1_I0009_additive_pressure/build_data.py:116`
  ```
  tot = (team_game.groupby(["team_id","season"]).agg(s_poss=("def_poss","sum"), ...))
  ```
- `experiments/exploration/E1_I0009_additive_pressure/build_data.py:120`
  ```
  loo_poss = team_game["s_poss"] - team_game["def_poss"]
  ```
- `experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py:97`
  ```
  anchor = self.league_pts_mean[season]
  ```
- `experiments/exploration/E1_I0009_additive_pressure/build_data.py:109`
  ```
  assert set(team_game["season"].unique()).issubset(set(EXPLORATION_SEASONS))
  ```

### 8. `experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 7. LIVE: consumed by PASSED graph node(s) P24_INJURY_REGIME_LEDGER, R14_D10_COACHING_CORRECTION, S36_IMPLEMENT_ARMS
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

CLEAN. Every pace estimate uses a strict d < r.game_date cutoff; the league fallback is a cumsum().shift(1) by date. Crucially it does NOT inherit the cbs_v15 prediction contamination: build_pace() takes only game_id/team_id/game_date/season from `base`, never a predicted value. Its other input, possessions_raw_v2, is per-game derived. This is the highest-priority item in the sweep (3 PASSED nodes) and it is safe.

Evidence:

- `experiments/player_program/build_projected_exposure.py:296`
  ```
  same = [v for (d, s, v) in h if d < r.game_date and s == r.season]
  ```
- `experiments/player_program/build_projected_exposure.py:297`
  ```
  prev = [v for (d, s, v) in h if d < r.game_date and s == r.season - 1]
  ```
- `experiments/player_program/build_projected_exposure.py:280`
  ```
  league_prior_mean = (by_date["sum"].cumsum().shift(1) / by_date["count"].cumsum().shift(1))
  ```
- `experiments/player_program/build_projected_exposure.py:268`
  ```
  sched = base[["game_id","team_id","game_date","season"]]  # identity columns ONLY from base
  ```

### 9. `data/reference/team_cities.csv`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 6. LIVE: consumed by PASSED graph node(s) P24_INJURY_REGIME_LEDGER, S36_IMPLEMENT_ARMS
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

A 16-row static geography dimension (city, arena, lat/lon, elevation, timezone) built from a hardcoded literal. No time-varying value, no fit, no data-derived field. The master is read only to VERIFY that every key joins. Highest consumer count among the reference files (6, two PASSED nodes) and completely inert.

Evidence:

- `data/reference/collect_bios.py:203`
  ```
  df = pd.DataFrame(CITY_ROWS, columns=[...])   # a hardcoded offline constant
  ```
- `data/reference/collect_bios.py:213`
  ```
  chk = master_keys.merge(df, ...)   # join-VERIFY only; no value is derived from the master
  ```

### 10. `experiments/exploration/E1_I0008_height_mismatch/frame.parquet`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk PARTITION_ONLY_LOOKAHEAD)
- Consumers: 11. DEAD: lead I0008 -- DEAD (KILL at Stage-1 noise-floor gate)
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

Opponent roster/rotation height aggregates use full-season minutes weights and a top-8 rank on total season minutes -- both read later games in the same season. The script documents this itself at line 114-118. Lead I0008 is KILLED, so this is housekeeping.

Evidence:

- `experiments/exploration/E1_I0008_height_mismatch/build_frame.py:117`
  ```
  What DOES apply: the minutes WEIGHTS are full-season, so the aggregate is not strictly pregame-observable at game t.   [the script says so itself]
  ```
- `experiments/exploration/E1_I0008_height_mismatch/build_frame.py:133`
  ```
  season_minutes.groupby(["team_id","season"])["minutes"].rank(...)  # top-8 by TOTAL SEASON minutes
  ```
- `experiments/exploration/E1_I0008_height_mismatch/build_frame.py:90`
  ```
  mp = mp[mp["season"].isin(EXPLORATION_SEASONS)].copy()  # FILTER-POINT
  ```

### 11. `experiments/player_program/turnover_targets_v1/player_turnover_targets_v1.parquet`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 7. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

CLEAN. A realised-OUTCOME target artifact. EVERY aggregation is keyed on game_id -- there is no cross-game, cross-season or population-level step anywhere in the file. Each row's value is that player-game's own realised turnovers over its own realised possessions, bounded by its own date.

Evidence:

- `experiments/player_program/build_turnover_targets.py:108`
  ```
  expo = long.groupby(["game_id","offense_team_id","player_id"]).size()  # keyed on game_id
  ```
- `experiments/player_program/build_turnover_targets.py:128`
  ```
  tot = pa.groupby(["game_id","turnover_team_id","attributed_player_id"]).size()
  ```
- `experiments/player_program/build_turnover_targets.py:150`
  ```
  players["turnovers_per_100_off_poss"] = 100.0 * turnovers / realised_off_possessions
  ```

### 12. `data/props_capture/historical/master_props_historical.csv`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 5. LIVE: consumed by PASSED graph node(s) M13_PLAYER_VALUE_TRANSLATION, M14_MODEL_MARKET_RESIDUAL
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

An append-only CAPTURE or per-game record. Every row carries its own observation/capture timestamp, so each row is bounded by its own as-of time by construction. Nothing is fitted and nothing is aggregated across rows. Consumed by: M13 + M14 PASSED

Evidence:

- `experiments/exploration/MANIFEST_REMEDIATION/s10_capture_headers.py`
  ```
  header inspection: per-row as-of columns present -> snapshot_requested_utc, snapshot_returned_utc, last_update
  ```

### 13. `experiments/exploration/E0_I0005_turnover_interaction/player_game_analysis.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk PARTITION_ONLY_LOOKAHEAD)
- Consumers: 9. DEAD: lead I0005 -- superseded by I0009
- Remedy: **manifest-only**, estimated cost 10 min. Group 2.

TWO independent season-pooling steps. (1) The `*_loo` columns are whole-season-minus-this-game leave-one-out -- they read LATER games in the same season; the script labels them 'hindsight; NOT pregame-observable'. (2) The `*_pregame` columns, despite the name, are shrunk toward an anchor that is the CURRENT season's full-season league mean whenever no prior season exists, and ALWAYS for defrtg. Both are confined to 2021-2024 by hard column-value asserts, so this is within-partition look-ahead, not holdout contamination. The file must not be manifested 'row'.

Evidence:

- `experiments/exploration/E0_I0005_turnover_interaction/build_data.py:163`
  ```
  # 4a. E0-comparable LOO tendency (hindsight; NOT pregame-observable)
  ```
- `experiments/exploration/E0_I0005_turnover_interaction/build_data.py:167`
  ```
  tov["loo_poss"] = tov["season_poss"] - tov["realised_off_possessions"]
  ```
- `experiments/exploration/E0_I0005_turnover_interaction/build_data.py:116`
  ```
  tot = (team_game.groupby(["team_id","season"]).agg(s_poss=("def_poss","sum"), ...))
  ```
- `experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py:39`
  ```
  lg = team_game.groupby("season").agg(p=("def_poss","sum"), t=("def_tov","sum"), ...)
  ```
- `experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py:55`
  ```
  self.anchor[(team, season)] = self.league_mean[season]   # CURRENT season full-season mean
  ```
- `experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py:97`
  ```
  anchor = self.league_pts_mean[season]   # defrtg always shrunk to the current season league mean
  ```

### 14. `experiments/player_program/turnover_targets_v1/team_turnover_reconciliation_v1.parquet`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 6. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

CLEAN, same reasoning: strictly game-keyed reconciliation of realised team turnovers.

Evidence:

- `experiments/player_program/build_turnover_targets.py:162`
  ```
  team_tot = T_team.groupby(["game_id","turnover_team_id"]).size()
  ```
- `experiments/player_program/build_turnover_targets.py:189`
  ```
  players.groupby(["game_id","team_id"])["turnovers"].sum()
  ```

### 15. `experiments/prediction_contract_v5/player_game_enriched.parquet`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 6. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

The v5 contract adds per-row outcome LABELS and obligation declarations to a frozen per-row candidate universe. No fit, no pooled statistic, no cross-row aggregation -- the module's whole discipline is that each row's cutoff bounds its own evidence. Independently corroborated by the H1 correction record, which already names prediction_contract_v* as row-granular.

Evidence:

- `prediction_contract_v5_enrich.py:13`
  ```
  1. pre-cutoff CANDIDATE and FEATURE information  -- Stage 1 frozen output
  ```
- `prediction_contract_v5_enrich.py:15`
  ```
  3. PREDICTION OBLIGATIONS -- derived from tier, never from outcomes
  ```
- `experiments/idea_log.jsonl`
  ```
  H1 correction record, notable_row_granular_and_therefore_SAFE: "experiments/prediction_contract_v*/**.parquet"
  ```

### 16. `experiments/exploration/E1_I0004_rim_finishing/_validate_sandbox/grid_metrics.parquet`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk PARTITION_ONLY_LOOKAHEAD)
- Consumers: 4. LIVE: feeds exploration lead I0011 -- LIVE (keep-as-lead x3)
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

A grid of evaluation METRICS, each computed by pooling over the whole evaluation set. Artifact-granular by construction as well as by inheritance. The two paths are byte-identical (sha256 D6580165...).

Evidence:

- `experiments/exploration/E1_I0011_split_alpha/grid.py:157`
  ```
  met.to_parquet(HERE + r"\grid_metrics.parquet", index=False)
  ```
- `(lineage)`
  ```
  built from E1_I0011 frame.parquet, which is artifact-granular; grid metrics are themselves aggregates over the whole evaluation set
  ```

### 17. `data/possessions/possessions.parquet`

- **Proposed `asof_granularity`: ROW** (confidence MEDIUM, holdout risk NONE)
- Consumers: 5. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

The repo-level possession store, same per-game non-fitted construction. MEDIUM: producer identified and its no-fit contract read, full body not traced.

Evidence:

- `experiments/player_program/possession_artifact_v1.py:4`
  ```
  **NOTHING IS FITTED.** ...  [same producer family as possessions_raw_v1]
  ```

### 18. `data/reference/player_bios.csv`

- **Proposed `asof_granularity`: ROW** (confidence MEDIUM, holdout risk NONE)
- Consumers: 4. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 15 min. Group 2.

Biographical attributes keyed (player_id, season). The probe settles the question the brief would otherwise leave open: the values are NOT one current-state pull replicated across a player's seasons -- age and weight genuinely vary season to season, so each row is a per-season fact. position_raw/college/country are constant because they are genuinely time-invariant. MEDIUM not HIGH for one reason: spot-checking `age` against `birthdate` suggests it may be off by about a year (Taurasi shows 40 in 2021). That is a DATA-QUALITY question, not a granularity one, but it deserves a five-minute check before the manifest is written.

Evidence:

- `data/reference/collect_bios.py:438`
  ```
  out = REF / "player_bios.csv"   # keyed (player_id, season)
  ```
- `experiments/exploration/MANIFEST_REMEDIATION/s11_bios_probe.py`
  ```
  probe on 2021-2024 rows only: age varies across seasons for 182/184 multi-season players; weight_lbs for 44/184; position_raw/college/country for 0/184
  ```

### 19. `experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 3. LIVE: consumed by PASSED graph node(s) S36_IMPLEMENT_ARMS
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

CLEAN. Three independent as-of constructions and no pooled one: strictly-lagged league expanding means by date, team season-to-date with an explicit d < date filter, and a win-probability logistic calibrated walk-forward on strictly prior seasons. The `ridge=1e-9` in fit_logistic_1d is numerical conditioning, not shrinkage toward a population prior.

Evidence:

- `experiments/market_program/SCORE_BASELINES/build_score_baselines.py:348`
  ```
  cum_n = by_date["n"].cumsum().shift(1)
  ```
- `experiments/market_program/SCORE_BASELINES/build_score_baselines.py:386`
  ```
  h = [(p, o) for (d, p, o) in hist.get((team_id, season), []) if d < date]
  ```
- `experiments/market_program/SCORE_BASELINES/build_score_baselines.py:425`
  ```
  train = d[d["season"] < s]   # walk-forward calibration, strictly prior seasons only
  ```

### 20. `experiments/player_program/possessions_v2/possessions_raw_v2.parquet`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 4. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

A derived EVENT artifact: possessions reconstructed per game from the play-by-play. The only ordering operation is a within-game shift(1). Nothing is fitted (the module header says so and the code bears it out). Each possession row is bounded by its own game's date.

Evidence:

- `experiments/player_program/possession_artifact_v2.py:4`
  ```
  **NOTHING IS FITTED.** No RAPM, no rate model, no ridge penalty, no player ranking ...
  ```
- `experiments/player_program/possession_artifact_v2.py:116`
  ```
  prev_end = pos.groupby("game_id")["end_sec"].shift(1)   # within-game only
  ```

### 21. `experiments/player_program/projected_exposure_v1/projected_player_possessions_v1.parquet`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk SPANS_HOLDOUT)
- Consumers: 4. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 15 min. Group 1.

INHERITANCE. Every allocated minute is a function of raw_expected_minutes = p_active x e_minutes_given_active, both read from cbs_v15_player_oof_v5 prediction files whose OWN manifests declare asof_granularity='artifact'. The glob concatenates all seasons 2021-2026 into one file. Weakest-link rule: this artifact is artifact-granular. MITIGATING (do not lose this): each per-season prediction file was fit only on STRICTLY PRIOR seasons (the 2024 file's manifest says fit_seasons [2021,2022,2023]), so a 2021 row did not see 2026. The binary row/artifact vocabulary cannot express that; see the convention decision in group 3.

Evidence:

- `experiments/player_program/build_projected_exposure.py:190`
  ```
  for f in sorted(PRED_DIR.glob("predictions__p_active__*.parquet"))  # ALL seasons incl. 2025/2026
  ```
- `experiments/player_program/build_projected_exposure.py:238`
  ```
  base["raw_expected_minutes"] = base["p_active"] * base["e_minutes_given_active"]
  ```
- `experiments/cbs_v15_player_oof_v5/attempt_001/predictions__p_active__2021.parquet.manifest.json:4`
  ```
  "asof_granularity": "artifact"   [the INPUT declares artifact granularity]
  ```

### 22. `experiments/player_program/turnover_p1_v1/turnover_p1_predictions_intrinsic.parquet`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk SPANS_HOLDOUT)
- Consumers: 3. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 10 min. Group 1.

MIXED, and the mix is the finding. The four rate arms A-D are genuinely row-clean: a strict day-by-day chronological pass that advances history only AFTER predicting the whole day, with a preregistered (not learned) EB_PRIOR_K. BUT line 108 merges projected_off_possessions from the artifact-granular projected exposure artifact, and that column is still present in the written 'intrinsic' frame. Weakest link makes the FILE artifact-granular even though its headline estimator is clean. Worth stating on the manifest so the clean part is not lost.

Evidence:

- `experiments/player_program/run_turnover_p1.py:77`
  ```
  # advance history AFTER predicting the whole day   [arms A-D are strictly prior: CLEAN]
  ```
- `experiments/player_program/run_turnover_p1.py:71`
  ```
  out["B_career_shrunk"] = (cx + EB_PRIOR_K * r_lg) / (cn + EB_PRIOR_K)  # r_lg = running prior-day league mean
  ```
- `experiments/player_program/run_turnover_p1.py:108`
  ```
  R = R.merge(PX, on=["game_id","team_id","player_id"], how="left")  # <-- PX = projected_player_possessions_v1
  ```
- `experiments/player_program/run_turnover_p1.py:113`
  ```
  df = R if name == "intrinsic" else both   # the intrinsic frame STILL carries the merged projected column
  ```

### 23. `experiments/market_program/INJURY_OFFICIAL/live/capture_log.csv`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 2. LIVE: consumed by PASSED graph node(s) M06_INJURY_REACTION_STUDY, P2B_MARKET_ODDS_ELIGIBILITY
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

An append-only CAPTURE or per-game record. Every row carries its own observation/capture timestamp, so each row is bounded by its own as-of time by construction. Nothing is fitted and nothing is aggregated across rows. Consumed by: M06 + P2B PASSED

Evidence:

- `experiments/exploration/MANIFEST_REMEDIATION/s10_capture_headers.py`
  ```
  header inspection: per-row as-of columns present -> attempted_ts_utc, retrieval_ts_utc
  ```

### 24. `experiments/player_program/data_lane/D12_COACHING_HISTORY/team_season_coverage_v1.csv`

- **Proposed `asof_granularity`: ROW** (confidence MEDIUM, holdout risk NONE)
- Consumers: 2. LIVE: consumed by PASSED graph node(s) D12_COACHING_HISTORY, R14_D10_COACHING_CORRECTION
- Remedy: **human-decision**, estimated cost 10 min. Group 3.

76 rows, one per team-season. Each row's fields are computed from its OWN season plus carried-forward PRIOR seasons -- never a later one. So filtering by season IS sufficient and the policy's purpose is met. The reason this needs a human is a VOCABULARY question, not a safety one: 'row' is defined as bounded by the row's own DATE, and this row's bound is its own SEASON. See the convention decision in group 3.

Evidence:

- `experiments/player_program/data_lane/D12_COACHING_HISTORY/build_coaching_history.py:466`
  ```
  season_open = ts.groupby("season")["first_game_date"].min().to_dict()
  ```
- `experiments/exploration/MANIFEST_REMEDIATION/s10_capture_headers.py`
  ```
  header: season, team_id, franchise, first_game_date, ... seasons_carried_forward, cutoff_status
  ```

### 25. `experiments/player_program/event_contract_v1/canonical_player_events_v1.parquet`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 2. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

A schema-normalisation artifact built one game at a time from two raw play-by-play stores. 'Normalise' here means schema harmonisation, not statistical normalisation -- this is exactly the kind of regex false-positive the brief warns about, and reading the function confirms it is per-game. Each event row is bounded by its own game.

Evidence:

- `experiments/player_program/build_canonical_events.py:295`
  ```
  """Normalise ONE game and apply keying, ordering and provenance.
  ```
- `experiments/player_program/build_canonical_events.py:300`
  ```
  df = normalise_legacy(game_id, path) if source == "legacy" else normalise_cdn(game_id, path)
  ```

### 26. `experiments/player_program/fits_v1/p3_coefficients_v1.parquet`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk SPANS_HOLDOUT)
- Consumers: 2. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 15 min. Group 1.

A FIT artifact, and the most interesting case in the sweep. Granularity is unambiguously ARTIFACT: a coefficient is one number pooled over every possession in its training window, with empirical-Bayes shrinkage toward a league prior. But the fit is WALK-FORWARD (train strictly earlier seasons) and -- unusually -- EVERY ROW CARRIES ITS OWN `training_cutoff_season`. So the file is self-describing: rows with cutoff <= 2024 saw only exploration-partition data, and rows with cutoff 2025 did not. Because TEST_SEASONS runs to 2026, the file DOES contain rows fit through 2025, so the file as a whole spans the holdout -- but a consumer can filter on `training_cutoff_season` and know exactly what it has. That column is the strongest existing argument for the convention decision in group 3.

Evidence:

- `experiments/player_program/fit_rate_and_p3.py:391`
  ```
  "model": "pooled empirical-Bayes shrinkage; player effect shrunk toward the league ..."
  ```
- `experiments/player_program/fit_rate_and_p3.py:164`
  ```
  beta = ridge_solve(D, lo, ld)   # a single global ridge fit over the whole training window
  ```
- `experiments/player_program/fit_rate_and_p3.py:144`
  ```
  tr = d[d["season"] < test_s]   # WALK-FORWARD: train strictly earlier seasons
  ```
- `experiments/player_program/fit_rate_and_p3.py:182`
  ```
  "training_cutoff_season": int(test_s) - 1, "player_id": int(p),   # per-ROW declared cutoff
  ```
- `experiments/player_program/fit_rate_and_p3.py:35`
  ```
  TEST_SEASONS = (2022, 2023, 2024, 2025, 2026)   # so rows exist whose training window includes 2025
  ```

### 27. `experiments/player_program/projected_exposure_v1/projected_team_rotations_v1.parquet`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk SPANS_HOLDOUT)
- Consumers: 2. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 10 min. Group 1.

Team-level roll-up of the same allocation; identical inheritance from the cbs_v15 predictions.

Evidence:

- `experiments/player_program/build_projected_exposure.py:627`
  ```
  teams.to_parquet(OUT / "projected_team_rotations_v1.parquet", index=False)
  ```
- `experiments/player_program/build_projected_exposure.py:238`
  ```
  base["raw_expected_minutes"] = base["p_active"] * base["e_minutes_given_active"]
  ```

### 28. `data/injury_capture/injury_log.csv`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 1. LIVE: consumed by PASSED graph node(s) O14_OPS_ENTITY_RESOLUTION
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

An append-only CAPTURE or per-game record. Every row carries its own observation/capture timestamp, so each row is bounded by its own as-of time by construction. Nothing is fitted and nothing is aggregated across rows. Consumed by: O14 PASSED

Evidence:

- `experiments/exploration/MANIFEST_REMEDIATION/s10_capture_headers.py`
  ```
  header inspection: per-row as-of columns present -> capture_utc, report_date, game_date
  ```

### 29. `data/injury_history/injury_history.csv`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 1. LIVE: consumed by PASSED graph node(s) P24_INJURY_REGIME_LEDGER
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

An append-only CAPTURE or per-game record. Every row carries its own observation/capture timestamp, so each row is bounded by its own as-of time by construction. Nothing is fitted and nothing is aggregated across rows. Consumed by: P24 PASSED

Evidence:

- `experiments/exploration/MANIFEST_REMEDIATION/s10_capture_headers.py`
  ```
  header inspection: per-row as-of columns present -> date
  ```

### 30. `data/ref_assignments/assignments_log.csv`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 1. LIVE: consumed by PASSED graph node(s) O11_OBLIGATION_DISCOVERY_LEAD_WINDOW
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

An append-only CAPTURE or per-game record. Every row carries its own observation/capture timestamp, so each row is bounded by its own as-of time by construction. Nothing is fitted and nothing is aggregated across rows. Consumed by: O11 PASSED

Evidence:

- `experiments/exploration/MANIFEST_REMEDIATION/s10_capture_headers.py`
  ```
  header inspection: per-row as-of columns present -> capture_utc, game_date
  ```

### 31. `experiments/market_program/INJURY_OFFICIAL/live/injury_snapshots.csv`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 1. LIVE: consumed by PASSED graph node(s) M06_INJURY_REACTION_STUDY
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

An append-only CAPTURE or per-game record. Every row carries its own observation/capture timestamp, so each row is bounded by its own as-of time by construction. Nothing is fitted and nothing is aggregated across rows. Consumed by: M06 PASSED

Evidence:

- `experiments/exploration/MANIFEST_REMEDIATION/s10_capture_headers.py`
  ```
  header inspection: per-row as-of columns present -> retrieval_ts_utc, ingestion_ts_utc, provider_publication_ts_*, url_slot_ts_*
  ```

### 32. `experiments/market_program/INJURY_OFFICIAL/live/status_transitions.csv`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 1. LIVE: consumed by PASSED graph node(s) M06_INJURY_REACTION_STUDY
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

An append-only CAPTURE or per-game record. Every row carries its own observation/capture timestamp, so each row is bounded by its own as-of time by construction. Nothing is fitted and nothing is aggregated across rows. Consumed by: M06 PASSED

Evidence:

- `experiments/exploration/MANIFEST_REMEDIATION/s10_capture_headers.py`
  ```
  header inspection: per-row as-of columns present -> t_lower_utc_bound, t_upper_utc_bound
  ```

### 33. `experiments/market_program/M13_PLAYER_VALUE_TRANSLATION/translation_rows.parquet`

- **Proposed `asof_granularity`: ARTIFACT** (confidence MEDIUM, holdout risk UNKNOWN)
- Consumers: 1. LIVE: consumed by PASSED graph node(s) M13_PLAYER_VALUE_TRANSLATION, M14_MODEL_MARKET_RESIDUAL
- Remedy: **human-decision**, estimated cost already in flight. Group 3.

Full-population qcut deciles, full-population ranks and a closed-form OLS variance model -- all pooled steps. DO NOT ACT ON THIS ONE HERE: a concurrent agent (MEASURE_F1_m13_fitpool) is measuring exactly this fit pool, and D075 records the M13 finding as HALT-AND-RAISED and USER_REQUIRED because it touches PASSED nodes. Listed for completeness only.

Evidence:

- `experiments/market_program/M13_PLAYER_VALUE_TRANSLATION/build_translation.py:390`
  ```
  q = pd.qcut(fp["pred_point"], 10, duplicates="drop")   # deciles over the WHOLE population
  ```
- `experiments/market_program/M13_PLAYER_VALUE_TRANSLATION/build_translation.py:401`
  ```
  r_pred = pd.Series(fp["pred_point"]).rank().to_numpy()   # full-population rank
  ```
- `experiments/market_program/M13_PLAYER_VALUE_TRANSLATION/build_translation.py:405`
  ```
  # heteroscedastic normal: |residual| ~ a + b*pred_point (closed-form OLS)
  ```

### 34. `data/masters/master_player.csv`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 1. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

An append-only CAPTURE or per-game record. Every row carries its own observation/capture timestamp, so each row is bounded by its own as-of time by construction. Nothing is fitted and nothing is aggregated across rows. Consumed by: -

Evidence:

- `experiments/exploration/MANIFEST_REMEDIATION/s10_capture_headers.py`
  ```
  header inspection: per-row as-of columns present -> game_date, observed_time
  ```

### 35. `data/props_capture/master_props.csv`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 1. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

An append-only CAPTURE or per-game record. Every row carries its own observation/capture timestamp, so each row is bounded by its own as-of time by construction. Nothing is fitted and nothing is aggregated across rows. Consumed by: -

Evidence:

- `experiments/exploration/MANIFEST_REMEDIATION/s10_capture_headers.py`
  ```
  header inspection: per-row as-of columns present -> snapshot_utc, last_update
  ```

### 36. `data/reference/tip_times.csv`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 1. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

An append-only CAPTURE or per-game record. Every row carries its own observation/capture timestamp, so each row is bounded by its own as-of time by construction. Nothing is fitted and nothing is aggregated across rows. Consumed by: -

Evidence:

- `experiments/exploration/MANIFEST_REMEDIATION/s10_capture_headers.py`
  ```
  header inspection: per-row as-of columns present -> game_date, tip_utc
  ```

### 37. `experiments/market_program/SCORE_BASELINES/market_paired_rows.parquet`

- **Proposed `asof_granularity`: ROW** (confidence MEDIUM, holdout risk NONE)
- Consumers: 1. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 10 min. Group 2.

Same producer as score_baseline_rows; pairs baseline rows against captured market lines, each carrying its own snapshot timestamp. MEDIUM: the pairing block itself was not read line by line.

Evidence:

- `experiments/market_program/SCORE_BASELINES/build_score_baselines.py:804`
  ```
  paired_rows.to_parquet(OUT_DIR / "market_paired_rows.parquet", index=False)
  ```
- `experiments/market_program/SCORE_BASELINES/build_score_baselines.py:348`
  ```
  cum_n = by_date["n"].cumsum().shift(1)   [same producer, same as-of discipline]
  ```

### 38. `experiments/player_program/possessions_v1/possessions_raw_v1.parquet`

- **Proposed `asof_granularity`: ROW** (confidence MEDIUM, holdout risk NONE)
- Consumers: 1. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

Superseded v1 of the possession artifact; same non-fitting per-game construction as v2. MEDIUM rather than HIGH because only the module contract header was read, not the full body.

Evidence:

- `experiments/player_program/possession_artifact_v1.py:4`
  ```
  **NOTHING IS FITTED.** No RAPM, no rate model, no ridge penalty, no player ranking, no offensive ...
  ```

### 39. `experiments/player_program/turnover_p1_v1/turnover_p1_predictions_operational_corrected.parquet`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk SPANS_HOLDOUT)
- Consumers: 1. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 10 min. Group 1.

The operational track multiplies each rate by projected_off_possessions, so it inherits the cbs_v15 chain directly and unambiguously.

Evidence:

- `experiments/player_program/run_turnover_p1_universe_fix.py:291`
  ```
  O.to_parquet(OUT / "turnover_p1_predictions_operational_corrected.parquet", index=False)
  ```
- `experiments/player_program/run_turnover_p1.py:112`
  ```
  ("operational", "projected_off_possessions")  # exposure IS the projected artifact
  ```

### 40. `experiments/player_program/turnover_p2_v1/turnover_role_context_features_v1.parquet`

- **Proposed `asof_granularity`: ARTIFACT** (confidence HIGH, holdout risk SPANS_HOLDOUT)
- Consumers: 1. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 10 min. Group 1.

Feature group 1 (proj_minutes_share, proj_off_poss_share, proj_rotation_rank, proj_top5_concentration) is derived from projected_player_possessions_v1 and inherits its artifact granularity. Feature groups 2-3 (trailing EWMA) are strictly prior and clean -- the day loop snapshots state BEFORE applying the day's updates. Mixed file, artifact-granular overall.

Evidence:

- `experiments/player_program/run_turnover_p2.py:113`
  ```
  F["proj_minutes_share"] = F["projected_minutes"] / g["projected_minutes"].transform("sum")
  ```
- `experiments/player_program/run_turnover_p2.py:100`
  ```
  columns=[... "projected_minutes", "projected_off_possessions", "p_active"]  # from projected_exposure_v1
  ```
- `experiments/player_program/run_turnover_p2.py:126`
  ```
  snap_min = dict(ewm_min); snap_fga = dict(ewm_fga)   # trailing features ARE strictly prior: clean
  ```

### 41. `experiments/prediction_contract_v5/candidacy_exclusions.parquet`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 1. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

The v5 contract adds per-row outcome LABELS and obligation declarations to a frozen per-row candidate universe. No fit, no pooled statistic, no cross-row aggregation -- the module's whole discipline is that each row's cutoff bounds its own evidence. Independently corroborated by the H1 correction record, which already names prediction_contract_v* as row-granular.

Evidence:

- `prediction_contract_v5_enrich.py:13`
  ```
  1. pre-cutoff CANDIDATE and FEATURE information  -- Stage 1 frozen output
  ```
- `prediction_contract_v5_enrich.py:15`
  ```
  3. PREDICTION OBLIGATIONS -- derived from tier, never from outcomes
  ```
- `experiments/idea_log.jsonl`
  ```
  H1 correction record, notable_row_granular_and_therefore_SAFE: "experiments/prediction_contract_v*/**.parquet"
  ```

### 42. `experiments/prediction_contract_v5/player_game.parquet`

- **Proposed `asof_granularity`: ROW** (confidence HIGH, holdout risk NONE)
- Consumers: 1. LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it
- Remedy: **manifest-only**, estimated cost 5 min. Group 2.

The v5 contract adds per-row outcome LABELS and obligation declarations to a frozen per-row candidate universe. No fit, no pooled statistic, no cross-row aggregation -- the module's whole discipline is that each row's cutoff bounds its own evidence. Independently corroborated by the H1 correction record, which already names prediction_contract_v* as row-granular.

Evidence:

- `prediction_contract_v5.py:13`
  ```
  1. pre-cutoff CANDIDATE and FEATURE information  -- Stage 1 frozen output
  ```
- `prediction_contract_v5.py:15`
  ```
  3. PREDICTION OBLIGATIONS -- derived from tier, never from outcomes
  ```
- `experiments/idea_log.jsonl`
  ```
  H1 correction record, notable_row_granular_and_therefore_SAFE: "experiments/prediction_contract_v*/**.parquet"
  ```

### 43. `experiments/props_edge/bet_universe_best_line.csv`

- **Proposed `asof_granularity`: UNDETERMINED** (confidence NONE, holdout risk UNKNOWN)
- Consumers: 3. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **human-decision**, estimated cost 20-40 min each. Group 3.

NOT CLASSIFIED. The producer script was located (see producer_candidates.json) but its build code was not read, so no granularity is proposed. Stating UNDETERMINED rather than guessing: these are model/backtest outputs from the game-and-betting program, where a train/test split fit through 2026 is the norm -- the H1 hazard already lists two siblings of this family (channel_reval/predictions_v2.csv, w2_integration/calibration_params.json) as contaminated, so the prior leans ARTIFACT, but a prior is not evidence. None of these is read by any player-program graph node or any live exploration lead.

Evidence:

- `(not traced)`
  ```
  producer located but build code NOT read in this sweep
  ```

### 44. `experiments/props_edge/bet_universe_per_book.csv`

- **Proposed `asof_granularity`: UNDETERMINED** (confidence NONE, holdout risk UNKNOWN)
- Consumers: 3. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **human-decision**, estimated cost 20-40 min each. Group 3.

NOT CLASSIFIED. The producer script was located (see producer_candidates.json) but its build code was not read, so no granularity is proposed. Stating UNDETERMINED rather than guessing: these are model/backtest outputs from the game-and-betting program, where a train/test split fit through 2026 is the norm -- the H1 hazard already lists two siblings of this family (channel_reval/predictions_v2.csv, w2_integration/calibration_params.json) as contaminated, so the prior leans ARTIFACT, but a prior is not evidence. None of these is read by any player-program graph node or any live exploration lead.

Evidence:

- `(not traced)`
  ```
  producer located but build code NOT read in this sweep
  ```

### 45. `experiments/channel_reval/channel_base_v2.csv`

- **Proposed `asof_granularity`: UNDETERMINED** (confidence NONE, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **human-decision**, estimated cost 20-40 min each. Group 3.

NOT CLASSIFIED. The producer script was located (see producer_candidates.json) but its build code was not read, so no granularity is proposed. Stating UNDETERMINED rather than guessing: these are model/backtest outputs from the game-and-betting program, where a train/test split fit through 2026 is the norm -- the H1 hazard already lists two siblings of this family (channel_reval/predictions_v2.csv, w2_integration/calibration_params.json) as contaminated, so the prior leans ARTIFACT, but a prior is not evidence. None of these is read by any player-program graph node or any live exploration lead.

Evidence:

- `(not traced)`
  ```
  producer located but build code NOT read in this sweep
  ```

### 46. `experiments/channel_reval/channel_results_v2.csv`

- **Proposed `asof_granularity`: UNDETERMINED** (confidence NONE, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **human-decision**, estimated cost 20-40 min each. Group 3.

NOT CLASSIFIED. The producer script was located (see producer_candidates.json) but its build code was not read, so no granularity is proposed. Stating UNDETERMINED rather than guessing: these are model/backtest outputs from the game-and-betting program, where a train/test split fit through 2026 is the norm -- the H1 hazard already lists two siblings of this family (channel_reval/predictions_v2.csv, w2_integration/calibration_params.json) as contaminated, so the prior leans ARTIFACT, but a prior is not evidence. None of these is read by any player-program graph node or any live exploration lead.

Evidence:

- `(not traced)`
  ```
  producer located but build code NOT read in this sweep
  ```

### 47. `experiments/clv_transfer/bet_log.csv`

- **Proposed `asof_granularity`: UNDETERMINED** (confidence NONE, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **human-decision**, estimated cost 20-40 min each. Group 3.

NOT CLASSIFIED. The producer script was located (see producer_candidates.json) but its build code was not read, so no granularity is proposed. Stating UNDETERMINED rather than guessing: these are model/backtest outputs from the game-and-betting program, where a train/test split fit through 2026 is the norm -- the H1 hazard already lists two siblings of this family (channel_reval/predictions_v2.csv, w2_integration/calibration_params.json) as contaminated, so the prior leans ARTIFACT, but a prior is not evidence. None of these is read by any player-program graph node or any live exploration lead.

Evidence:

- `(not traced)`
  ```
  producer located but build code NOT read in this sweep
  ```

### 48. `experiments/clv_transfer/flat_stake_sim.csv`

- **Proposed `asof_granularity`: UNDETERMINED** (confidence NONE, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **human-decision**, estimated cost 20-40 min each. Group 3.

NOT CLASSIFIED. The producer script was located (see producer_candidates.json) but its build code was not read, so no granularity is proposed. Stating UNDETERMINED rather than guessing: these are model/backtest outputs from the game-and-betting program, where a train/test split fit through 2026 is the norm -- the H1 hazard already lists two siblings of this family (channel_reval/predictions_v2.csv, w2_integration/calibration_params.json) as contaminated, so the prior leans ARTIFACT, but a prior is not evidence. None of these is read by any player-program graph node or any live exploration lead.

Evidence:

- `(not traced)`
  ```
  producer located but build code NOT read in this sweep
  ```

### 49. `experiments/exploration/E0_I0014_residual_heterogeneity/screen_results.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence MEDIUM, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **manifest-only**, estimated cost 5 min each. Group 4.

A SCREEN RESULT table, not a feature table. Every cell is a statistic computed over the whole screened population, so there is no per-row date bound that could exist. Artifact-granular by construction. MEDIUM because the classification is structural (from the artifact's shape and its consumers) rather than from reading each of the six screen producers line by line. These feed only interactions_lab.py / volume_heterogeneity.py, both legacy game-model screens; AUDIT_SCREEN_INTEGRITY already covers this family.

Evidence:

- `(structural)`
  ```
  one row per screened FEATURE, not per game: columns are dR2 / p-value / survivor flags, each of which is a statistic pooled over the whole screened population
  ```

### 50. `experiments/feature_archetypes/survivor_summary.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence MEDIUM, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **manifest-only**, estimated cost 5 min each. Group 4.

A SCREEN RESULT table, not a feature table. Every cell is a statistic computed over the whole screened population, so there is no per-row date bound that could exist. Artifact-granular by construction. MEDIUM because the classification is structural (from the artifact's shape and its consumers) rather than from reading each of the six screen producers line by line. These feed only interactions_lab.py / volume_heterogeneity.py, both legacy game-model screens; AUDIT_SCREEN_INTEGRITY already covers this family.

Evidence:

- `(structural)`
  ```
  one row per screened FEATURE, not per game: columns are dR2 / p-value / survivor flags, each of which is a statistic pooled over the whole screened population
  ```

### 51. `experiments/feature_interactions/survivor_summary.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence MEDIUM, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **manifest-only**, estimated cost 5 min each. Group 4.

A SCREEN RESULT table, not a feature table. Every cell is a statistic computed over the whole screened population, so there is no per-row date bound that could exist. Artifact-granular by construction. MEDIUM because the classification is structural (from the artifact's shape and its consumers) rather than from reading each of the six screen producers line by line. These feed only interactions_lab.py / volume_heterogeneity.py, both legacy game-model screens; AUDIT_SCREEN_INTEGRITY already covers this family.

Evidence:

- `(structural)`
  ```
  one row per screened FEATURE, not per game: columns are dR2 / p-value / survivor flags, each of which is a statistic pooled over the whole screened population
  ```

### 52. `experiments/feature_screen/screen_results.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence MEDIUM, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **manifest-only**, estimated cost 5 min each. Group 4.

A SCREEN RESULT table, not a feature table. Every cell is a statistic computed over the whole screened population, so there is no per-row date bound that could exist. Artifact-granular by construction. MEDIUM because the classification is structural (from the artifact's shape and its consumers) rather than from reading each of the six screen producers line by line. These feed only interactions_lab.py / volume_heterogeneity.py, both legacy game-model screens; AUDIT_SCREEN_INTEGRITY already covers this family.

Evidence:

- `(structural)`
  ```
  one row per screened FEATURE, not per game: columns are dR2 / p-value / survivor flags, each of which is a statistic pooled over the whole screened population
  ```

### 53. `experiments/feature_screen/survivor_summary.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence MEDIUM, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **manifest-only**, estimated cost 5 min each. Group 4.

A SCREEN RESULT table, not a feature table. Every cell is a statistic computed over the whole screened population, so there is no per-row date bound that could exist. Artifact-granular by construction. MEDIUM because the classification is structural (from the artifact's shape and its consumers) rather than from reading each of the six screen producers line by line. These feed only interactions_lab.py / volume_heterogeneity.py, both legacy game-model screens; AUDIT_SCREEN_INTEGRITY already covers this family.

Evidence:

- `(structural)`
  ```
  one row per screened FEATURE, not per game: columns are dR2 / p-value / survivor flags, each of which is a statistic pooled over the whole screened population
  ```

### 54. `experiments/feature_screen_crossseason/screen_results.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence MEDIUM, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **manifest-only**, estimated cost 5 min each. Group 4.

A SCREEN RESULT table, not a feature table. Every cell is a statistic computed over the whole screened population, so there is no per-row date bound that could exist. Artifact-granular by construction. MEDIUM because the classification is structural (from the artifact's shape and its consumers) rather than from reading each of the six screen producers line by line. These feed only interactions_lab.py / volume_heterogeneity.py, both legacy game-model screens; AUDIT_SCREEN_INTEGRITY already covers this family.

Evidence:

- `(structural)`
  ```
  one row per screened FEATURE, not per game: columns are dR2 / p-value / survivor flags, each of which is a statistic pooled over the whole screened population
  ```

### 55. `experiments/feature_screen_crossseason/survivor_summary.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence MEDIUM, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **manifest-only**, estimated cost 5 min each. Group 4.

A SCREEN RESULT table, not a feature table. Every cell is a statistic computed over the whole screened population, so there is no per-row date bound that could exist. Artifact-granular by construction. MEDIUM because the classification is structural (from the artifact's shape and its consumers) rather than from reading each of the six screen producers line by line. These feed only interactions_lab.py / volume_heterogeneity.py, both legacy game-model screens; AUDIT_SCREEN_INTEGRITY already covers this family.

Evidence:

- `(structural)`
  ```
  one row per screened FEATURE, not per game: columns are dR2 / p-value / survivor flags, each of which is a statistic pooled over the whole screened population
  ```

### 56. `experiments/feature_screen_rebaselined/screen_results.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence MEDIUM, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **manifest-only**, estimated cost 5 min each. Group 4.

A SCREEN RESULT table, not a feature table. Every cell is a statistic computed over the whole screened population, so there is no per-row date bound that could exist. Artifact-granular by construction. MEDIUM because the classification is structural (from the artifact's shape and its consumers) rather than from reading each of the six screen producers line by line. These feed only interactions_lab.py / volume_heterogeneity.py, both legacy game-model screens; AUDIT_SCREEN_INTEGRITY already covers this family.

Evidence:

- `(structural)`
  ```
  one row per screened FEATURE, not per game: columns are dR2 / p-value / survivor flags, each of which is a statistic pooled over the whole screened population
  ```

### 57. `experiments/feature_screen_rebaselined/survivor_summary.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence MEDIUM, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **manifest-only**, estimated cost 5 min each. Group 4.

A SCREEN RESULT table, not a feature table. Every cell is a statistic computed over the whole screened population, so there is no per-row date bound that could exist. Artifact-granular by construction. MEDIUM because the classification is structural (from the artifact's shape and its consumers) rather than from reading each of the six screen producers line by line. These feed only interactions_lab.py / volume_heterogeneity.py, both legacy game-model screens; AUDIT_SCREEN_INTEGRITY already covers this family.

Evidence:

- `(structural)`
  ```
  one row per screened FEATURE, not per game: columns are dR2 / p-value / survivor flags, each of which is a statistic pooled over the whole screened population
  ```

### 58. `experiments/feature_screen_run2/screen_results.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence MEDIUM, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **manifest-only**, estimated cost 5 min each. Group 4.

A SCREEN RESULT table, not a feature table. Every cell is a statistic computed over the whole screened population, so there is no per-row date bound that could exist. Artifact-granular by construction. MEDIUM because the classification is structural (from the artifact's shape and its consumers) rather than from reading each of the six screen producers line by line. These feed only interactions_lab.py / volume_heterogeneity.py, both legacy game-model screens; AUDIT_SCREEN_INTEGRITY already covers this family.

Evidence:

- `(structural)`
  ```
  one row per screened FEATURE, not per game: columns are dR2 / p-value / survivor flags, each of which is a statistic pooled over the whole screened population
  ```

### 59. `experiments/feature_screen_run2/survivor_summary.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence MEDIUM, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **manifest-only**, estimated cost 5 min each. Group 4.

A SCREEN RESULT table, not a feature table. Every cell is a statistic computed over the whole screened population, so there is no per-row date bound that could exist. Artifact-granular by construction. MEDIUM because the classification is structural (from the artifact's shape and its consumers) rather than from reading each of the six screen producers line by line. These feed only interactions_lab.py / volume_heterogeneity.py, both legacy game-model screens; AUDIT_SCREEN_INTEGRITY already covers this family.

Evidence:

- `(structural)`
  ```
  one row per screened FEATURE, not per game: columns are dR2 / p-value / survivor flags, each of which is a statistic pooled over the whole screened population
  ```

### 60. `experiments/totals_groundwork/bookie_totals_per_game.csv`

- **Proposed `asof_granularity`: UNDETERMINED** (confidence NONE, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **human-decision**, estimated cost 20-40 min each. Group 3.

NOT CLASSIFIED. The producer script was located (see producer_candidates.json) but its build code was not read, so no granularity is proposed. Stating UNDETERMINED rather than guessing: these are model/backtest outputs from the game-and-betting program, where a train/test split fit through 2026 is the norm -- the H1 hazard already lists two siblings of this family (channel_reval/predictions_v2.csv, w2_integration/calibration_params.json) as contaminated, so the prior leans ARTIFACT, but a prior is not evidence. None of these is read by any player-program graph node or any live exploration lead.

Evidence:

- `(not traced)`
  ```
  producer located but build code NOT read in this sweep
  ```

### 61. `experiments/volume_heterogeneity/screen_results.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence MEDIUM, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **manifest-only**, estimated cost 5 min each. Group 4.

A SCREEN RESULT table, not a feature table. Every cell is a statistic computed over the whole screened population, so there is no per-row date bound that could exist. Artifact-granular by construction. MEDIUM because the classification is structural (from the artifact's shape and its consumers) rather than from reading each of the six screen producers line by line. These feed only interactions_lab.py / volume_heterogeneity.py, both legacy game-model screens; AUDIT_SCREEN_INTEGRITY already covers this family.

Evidence:

- `(structural)`
  ```
  one row per screened FEATURE, not per game: columns are dR2 / p-value / survivor flags, each of which is a statistic pooled over the whole screened population
  ```

### 62. `experiments/volume_heterogeneity/survivor_summary.csv`

- **Proposed `asof_granularity`: ARTIFACT** (confidence MEDIUM, holdout risk UNKNOWN)
- Consumers: 2. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **manifest-only**, estimated cost 5 min each. Group 4.

A SCREEN RESULT table, not a feature table. Every cell is a statistic computed over the whole screened population, so there is no per-row date bound that could exist. Artifact-granular by construction. MEDIUM because the classification is structural (from the artifact's shape and its consumers) rather than from reading each of the six screen producers line by line. These feed only interactions_lab.py / volume_heterogeneity.py, both legacy game-model screens; AUDIT_SCREEN_INTEGRITY already covers this family.

Evidence:

- `(structural)`
  ```
  one row per screened FEATURE, not per game: columns are dR2 / p-value / survivor flags, each of which is a statistic pooled over the whole screened population
  ```

### 63. `experiments/dist_margin_cover/game_level_dist.csv`

- **Proposed `asof_granularity`: UNDETERMINED** (confidence NONE, holdout risk UNKNOWN)
- Consumers: 1. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **human-decision**, estimated cost 20-40 min each. Group 3.

NOT CLASSIFIED. The producer script was located (see producer_candidates.json) but its build code was not read, so no granularity is proposed. Stating UNDETERMINED rather than guessing: these are model/backtest outputs from the game-and-betting program, where a train/test split fit through 2026 is the norm -- the H1 hazard already lists two siblings of this family (channel_reval/predictions_v2.csv, w2_integration/calibration_params.json) as contaminated, so the prior leans ARTIFACT, but a prior is not evidence. None of these is read by any player-program graph node or any live exploration lead.

Evidence:

- `(not traced)`
  ```
  producer located but build code NOT read in this sweep
  ```

### 64. `experiments/minutes_twostage/test_predictions_m1.csv`

- **Proposed `asof_granularity`: UNDETERMINED** (confidence NONE, holdout risk UNKNOWN)
- Consumers: 1. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **human-decision**, estimated cost 20-40 min each. Group 3.

NOT CLASSIFIED. The producer script was located (see producer_candidates.json) but its build code was not read, so no granularity is proposed. Stating UNDETERMINED rather than guessing: these are model/backtest outputs from the game-and-betting program, where a train/test split fit through 2026 is the norm -- the H1 hazard already lists two siblings of this family (channel_reval/predictions_v2.csv, w2_integration/calibration_params.json) as contaminated, so the prior leans ARTIFACT, but a prior is not evidence. None of these is read by any player-program graph node or any live exploration lead.

Evidence:

- `(not traced)`
  ```
  producer located but build code NOT read in this sweep
  ```

### 65. `experiments/minutes_twostage/test_predictions_m2.csv`

- **Proposed `asof_granularity`: UNDETERMINED** (confidence NONE, holdout risk UNKNOWN)
- Consumers: 1. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **human-decision**, estimated cost 20-40 min each. Group 3.

NOT CLASSIFIED. The producer script was located (see producer_candidates.json) but its build code was not read, so no granularity is proposed. Stating UNDETERMINED rather than guessing: these are model/backtest outputs from the game-and-betting program, where a train/test split fit through 2026 is the norm -- the H1 hazard already lists two siblings of this family (channel_reval/predictions_v2.csv, w2_integration/calibration_params.json) as contaminated, so the prior leans ARTIFACT, but a prior is not evidence. None of these is read by any player-program graph node or any live exploration lead.

Evidence:

- `(not traced)`
  ```
  producer located but build code NOT read in this sweep
  ```

### 66. `experiments/oracle_bracket/game_level_margins.csv`

- **Proposed `asof_granularity`: UNDETERMINED** (confidence NONE, holdout risk UNKNOWN)
- Consumers: 1. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **human-decision**, estimated cost 20-40 min each. Group 3.

NOT CLASSIFIED. The producer script was located (see producer_candidates.json) but its build code was not read, so no granularity is proposed. Stating UNDETERMINED rather than guessing: these are model/backtest outputs from the game-and-betting program, where a train/test split fit through 2026 is the norm -- the H1 hazard already lists two siblings of this family (channel_reval/predictions_v2.csv, w2_integration/calibration_params.json) as contaminated, so the prior leans ARTIFACT, but a prior is not evidence. None of these is read by any player-program graph node or any live exploration lead.

Evidence:

- `(not traced)`
  ```
  producer located but build code NOT read in this sweep
  ```

### 67. `experiments/totals_groundwork/exploratory_bias_fix_per_game.csv`

- **Proposed `asof_granularity`: UNDETERMINED** (confidence NONE, holdout risk UNKNOWN)
- Consumers: 1. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **human-decision**, estimated cost 20-40 min each. Group 3.

NOT CLASSIFIED. The producer script was located (see producer_candidates.json) but its build code was not read, so no granularity is proposed. Stating UNDETERMINED rather than guessing: these are model/backtest outputs from the game-and-betting program, where a train/test split fit through 2026 is the norm -- the H1 hazard already lists two siblings of this family (channel_reval/predictions_v2.csv, w2_integration/calibration_params.json) as contaminated, so the prior leans ARTIFACT, but a prior is not evidence. None of these is read by any player-program graph node or any live exploration lead.

Evidence:

- `(not traced)`
  ```
  producer located but build code NOT read in this sweep
  ```

### 68. `experiments/w2_integration/game_level_predictions.csv`

- **Proposed `asof_granularity`: UNDETERMINED** (confidence NONE, holdout risk UNKNOWN)
- Consumers: 1. DEAD/LEGACY: game-and-betting program only; no player-program consumer
- Remedy: **human-decision**, estimated cost 20-40 min each. Group 3.

NOT CLASSIFIED. The producer script was located (see producer_candidates.json) but its build code was not read, so no granularity is proposed. Stating UNDETERMINED rather than guessing: these are model/backtest outputs from the game-and-betting program, where a train/test split fit through 2026 is the norm -- the H1 hazard already lists two siblings of this family (channel_reval/predictions_v2.csv, w2_integration/calibration_params.json) as contaminated, so the prior leans ARTIFACT, but a prior is not evidence. None of these is read by any player-program graph node or any live exploration lead.

Evidence:

- `(not traced)`
  ```
  producer located but build code NOT read in this sweep
  ```

## What this sweep did NOT cover

Stated plainly so this does not read as complete when it is not:

- **13 legacy game-and-betting artifacts were not code-traced** (group 3b). Producers are
  recorded in `producer_candidates.json`; the build code was not read.
- The **24 screen-local intermediates** and **21 unresolved references** in the audit's other
  buckets were out of scope and were not classified.
- `experiments/market_program/M13_PLAYER_VALUE_TRANSLATION/translation_rows.parquet` was
  classified but deliberately **not pursued**: a concurrent agent (`MEASURE_F1_m13_fitpool`) is
  measuring that exact fit pool, and D075 records the M13 finding as HALT-AND-RAISED and
  USER_REQUIRED because it touches PASSED nodes.
- Three directories were excluded from every scan as required:
  `E1_I0004_fga_forecast`, `MEASURE_F1_m13_fitpool`, `_screen_kit`.
- Of the seven directories the audit flagged as having zero manifests, six were reached
  (`turnover_p1_v1`, `turnover_p2_v1`, `turnover_targets_v1`, `projected_exposure_v1`,
  `fits_v1`, plus the possession stores). **`possession_features_v1` and `validation_v1` have
  no artifact in the 68-item list**, so nothing in them was classified.

## Partition compliance

One numerical probe was run (`s11_bios_probe.py`, on `player_bios.csv`). It filters to
`season in [2021,2022,2023,2024]` on column values immediately after load and before any
comparison. No 2025/2026 data was loaded into any analysis. Source code referencing later
seasons was read, which the brief permits.