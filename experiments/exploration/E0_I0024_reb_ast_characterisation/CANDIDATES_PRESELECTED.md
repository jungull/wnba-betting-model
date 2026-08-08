# E0_I0024 -- PRESELECTED CANDIDATES (preregistered before any statistic)

**PREREG SHA256 = `ab220cd18ae33a4c0c03a3a408a6c498145d6493e06e9201a8461e5587d13736`**

- candidates: **17**
- cells (target x base x candidate): **125**
- cell RUNS (125 cells x 2 strata, POOLED and DECISION): **250**
- **added since hash: 4   dropped since hash: 0**

**The 4 post-hoc additions**, declared in `s05_mechanism.py` and counted here:
`A01_c04_prevgame` and `A04_teammate_prior_fgm_pg` on target `y_pts`, on both strata. They are the
decisive specificity test — if the surviving teammate channel is general opportunity rather than a
playmaking channel, it must fire on points too. It does, roughly three times as hard as on assists.
**The addition made the conclusion more negative, not less.**

This list was fixed and hashed by `s01_prereg.py`, which loads no data and computes no statistic. Any later change is reported as an added/dropped count against the hash above.

## Targets

- `y_oreb` -- offensive rebounds, player-game count
- `y_dreb` -- defensive rebounds, player-game count
- `y_reb` -- total rebounds, player-game count (oreb+dreb; identity asserted against box `reb`)
- `y_ast` -- assists, player-game count
- `y_pts` -- points -- CALIBRATION ANCHOR ONLY.  Already characterised by D081.  Carried through the identical ladder/ceiling machinery so the rebound and assist numbers are compared to points ON THIS FRAME rather than across frames.  No new claim is made about points.

## Bases

D087 REFERENCE INCOMPLETENESS is the top-ranked explanation for this programme's nulls.  B_COMPLETE puts EVERY available strictly-prior measurement of the target in the base.  A candidate is only reported as alive if it survives B_COMPLETE.

- **B_SINGLE**: `ref_mean`
- **B_COMPLETE**: `ref_mean`, `ref_ewma`, `ref_trail5`, `ref_rate_x_min`, `ref_mean_minutes`, `ref_trail5_minutes`, `ref_pct`, `ref_mean_pace`, `n_prior`, `is_home`
- **B_COMPLETE_PLUS_R10**: B_COMPLETE + `R10_opp_allowed_oreb_pg` -- the decomposition variant. A rebound candidate must survive against a base that already contains the closest prior *opponent* measurement of the target.


## Candidates

| name | family | varies at (null level) | description |
|---|---|---|---|
| `R01_opp_allowed_miss_pg` | R | `opp_team_season` | opp team's strictly-prior mean MISSED field goals allowed per game (box) |
| `R02_opp_allowed_ra_share` | R | `opp_team_season` | opp team's strictly-prior share of ALLOWED attempts from Restricted Area |
| `R03_opp_allowed_atb3_share` | R | `opp_team_season` | opp team's strictly-prior share of ALLOWED attempts Above the Break 3 |
| `R04_opp_allowed_mid_share` | R | `opp_team_season` | opp team's strictly-prior share of ALLOWED attempts Mid-Range |
| `R05_opp_allowed_long_miss_pg` | R | `opp_team_season` | opp team's strictly-prior MISSED 3PA allowed per game (long rebounds) |
| `R06_own_atb3_share` | R | `team_season` | own team's strictly-prior share of OWN attempts Above the Break 3 |
| `R07_own_miss_pg` | R | `team_season` | own team's strictly-prior mean MISSED field goals per game |
| `R08_player_ra_share` | R | `player_season` | player's OWN strictly-prior share of own attempts from Restricted Area |
| `R09_opp_allowed_paint_share` | R | `opp_team_season` | opp team's strictly-prior share of ALLOWED attempts in the paint (RA + non-RA) |
| `R10_opp_allowed_oreb_pg` | R | `opp_team_season` | opp team's strictly-prior mean OFFENSIVE rebounds ALLOWED per game (box) -- the closest prior opponent measurement of the target; also used as an EXTRA base column in the decomposition variant B_COMPLETE_PLUS_R10 |
| `A01_c04_prevgame` | A | `team_season` | sum of strictly-prior per-game USAGE of the OTHER players who appeared in the team's PREVIOUS game box.  Construction credited to D089 E1_I0018_teammate_volume_channel/s01_build_frame.py (P01_c04_prevgame), reproduced here, READ-ONLY.  The TIP-TIME variant T01 is a POST-GAME observation and is NEVER BUILT. |
| `A02_n_present_prevgame` | A | `team_season` | count of players in the team's PREVIOUS game box (D089 P05) |
| `A03_absent_usg_prevgame` | A | `team_season` | strictly-prior usage of players ABSENT from the previous game box (D089 P04) |
| `A04_teammate_prior_fgm_pg` | A | `team_season` | sum of strictly-prior per-game FGM of the OTHER players in the previous game box -- an assist requires a teammate to MAKE a shot, so this is the mechanism-specific form of A01 |
| `A05_teammate_prior_fgpct` | A | `team_season` | usage-weighted strictly-prior FG% of the OTHER players in the previous game box |
| `G01_noise` | G | `row` | NEGATIVE CONTROL: iid gaussian, seed-fixed, independent of everything |
| `G02_placebo_noop` | G | `row` | NO-OP PLACEBO: an exact affine copy of the base's first column.  Its dR2 must be ~0 by construction; its OBSERVED SD across draws is reported as the floor of resolution of this screen. |

## Fixed analysis choices

- **partition**: seasons 2021-2024 only; HEADLINE = 2022-2024 (matching D081's reproduction rows); 2021 reported only as a labelled power sensitivity.  2025/2026 never read.
- **rows**: appeared player-games only (minutes > 0), master_player.parquet
- **decision_stratum**: n_prior >= 8 AND trailing-5 mean minutes >= 24 -- D081 s06's decision-relevant stratum, so figures are comparable with D081/D085/D089
- **history_minutes_floor_primary**: 10.0
- **history_minutes_floor_sensitivity**: [0.0, 5.0, 10.0, 15.0, 20.0]
- **floor_note**: THE FLOOR IS APPLIED TO THE HISTORY ONLY -- which prior games contribute to a per-minute rate estimate.  It is NEVER applied to the response, because filtering the response conditions on an outcome (D091 ruling 3).  D093 measured a response floor removing 39.3% of per-minute variance; that is a measurement result, not a licence to filter the response here.
- **ewma_halflife**: 5.0
- **r2_convention**: plain unweighted OLS R2, SST about the UNWEIGHTED mean (D069)
- **n_draws**: 600
- **seed**: 20260808
- **nulls**: N_ROW (naive, reported for INFLATION ONLY, never a verdict); N_ENTITY_SWAP at the candidate's declared level (whole entity time-series reassigned within season, preserving serial structure); N_CYCLIC (within-player cyclic shift, D093's autocorrelation trap -- a plain shuffle is anticonservative, p 0.0015 vs an honest 0.39, implementation credited to E1_I0021_heterogeneity_diagnostic/hd_base.py, READ-ONLY).  p_correct_level = MAX over the applicable entity-level nulls.
- **family_wise**: max-t across all cells sharing a target family, standardised by each cell's own null mean/sd
- **ceiling_form**: D084/D089 form: CEILING_dr2 = (|beta| * sd_candidate / sd_y)^2, i.e. the variance share reachable if 1 sd of the signal moves the target by beta*sd.  Benchmarks: 0.002057 (D089, largest measured, alive), 0.001127 (dead), 0.000129 (dead).  The base-residualised variant is reported alongside.
- **oracle_ladder**: REF/H honest rungs (strictly prior only) vs O1 season-mean target, O2 ACTUAL minutes x season-mean rate, O3 within-player-season OLS on ACTUAL minutes, O4 ACTUAL minutes x honest prior rate, O5 honest prior minutes x season-mean rate.  D081's ladder shape, with the champion rungs omitted BECAUSE NO CHAMPION REBOUND OR ASSIST FORECAST EXISTS (D088).
- **champion**: NEVER loaded, never retrained, never refitted.  D088 established the champion carries no rebound and no assist forecast, which is why this screen exists.
- **forbidden**: ['data/w1_truth/player_game_availability.csv', 'data/w1_truth/roster_asof.csv', 'data/zone_maps/*']
- **forbidden_note**: NOT OPENED.  Availability is rebuilt from box membership (minutes>0), the D076 method.  Zones are derived from raw per-shot SHOT_ZONE_BASIC in data/shotcharts/, which carries NO MANIFEST and is therefore reported as UNVERIFIABLE; row-granularity value evidence was reproduced in s00b at 1.000000 of 132,558 rows and is a MITIGATION, not a manifest.
