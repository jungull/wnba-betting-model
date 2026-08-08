# CANDIDATES PRESELECTED -- E0_I0019 availability forecast (`p_active`)

Written and hashed BEFORE any statistic was computed (constraint 7). The hash covers
the family -> candidate mapping exactly as serialised in `s02_build_candidates.py`.

**CANDIDATE LIST SHA256 = `aecb93baa9c7bb02e85fe6753562f2b86bbb56bd93a39ed0a7bda37b778c2048`**

**DEPENDENT LIST SHA256 = `8279f0c9089fb253113d9ea4528b5df160fc2f954cef2b0bd0bb5d41ab991bcc`**

53 candidates x 6 dependents = **318 cells**.

## Dependents

- `signed_err` --- y - p          (SIGNED calibration error; sign = direction of miscalibration)
- `brier` --- (y - p)^2      (ERROR, NOT an edge -- D076: predicting error != predicting skill)
- `skill_vs_R1` --- (y-R1)^2 - (y-p)^2   differential skill vs the per-player prior rate
- `skill_vs_R2` --- (y-R2)^2 - (y-p)^2   differential skill vs the Beta-shrunk career prior rate
- `skill_vs_R3` --- (y-R3)^2 - (y-p)^2   differential skill vs the RICH walk-forward lookup
- `llskill_vs_R3` --- logloss(R3) - logloss(p)   the same contrast on the log-loss scale

## Candidates by family

### A_depth_experience (10)

- `pl_opps_prior`
- `pl_games_prior`
- `pl_prior_rate_inseason`
- `pl_career_opps_prior`
- `pl_career_games_prior`
- `pl_prior_rate_career`
- `pl_prior_season_games`
- `pl_is_rookie_window`
- `pl_minutes_prior`
- `pl_min_per_opp_prior`

### B_absence_return (7)

- `pl_missed_last`
- `pl_missed_any_last3`
- `pl_dnp_frac5`
- `pl_dnp_frac10`
- `pl_consec_absences`
- `pl_absence_spells`
- `pl_days_since_appear`

### C_boundary_intermittency (6)

- `pl_boundary_score`
- `pl_boundary_score_career`
- `pl_switches`
- `pl_switch_rate`
- `pl_switches5`
- `pl_run_length`

### D_role_volume (6)

- `pl_min_mean5`
- `pl_min_sd5`
- `pl_min_cv5`
- `pl_start_mean5`
- `pl_usg_mean5`
- `pl_min_trend5`

### E_roster_churn (5)

- `tm_roster_churn_prior`
- `tm_newfaces_prior`
- `tm_roster_size_prior`
- `tm_five_tenure_prior`
- `tm_five_changed_prior`

### F_schedule (5)

- `tm_rest_days`
- `tm_b2b`
- `tm_3in4`
- `tm_games_prior7d`
- `tm_is_home`

### G_season_phase_contention (5)

- `tm_game_idx`
- `tm_season_progress`
- `tm_win_pct_prior`
- `tm_win_pct_vs_league`
- `tm_late_out_of_contention`

### H_model_own_state (7)

- `mdl_is_fallback`
- `mdl_fallback_level`
- `mdl_is_cold_start`
- `mdl_n_prior_games`
- `mdl_pred_point`
- `mdl_pred_entropy`
- `mdl_pred_dist_from_half`

### Z_negative_control (2)

- `neg_ctrl_row_noise`
- `neg_ctrl_player_noise`

## Added / dropped versus the pre-registration

This is the FIRST and ONLY candidate list for this screen. Added since hashing: **0**.
Dropped since hashing: **0**. Any later change would require a new hash and would be
recorded here with both hashes.

## Notes on specific choices

- `F_schedule` is included **knowing the family is dead for points and rates** (D081:
  0 of 330 rate cells; D085: 0 of 12; D076: 18 cells, best |t| 7.46, all decile ratios
  0.94-1.25). Availability is a different target and rest decisions plausibly respond
  to back-to-backs, so it is tested rather than assumed. If it dies again the screen
  says so plainly.
- `H_model_own_state` conditions on the model's OWN declared state. `mdl_pred_point`
  and `mdl_pred_entropy` are the model's own uncertainty; a well-behaved forecast
  should NOT have differential skill against its own probability level.
- `Z_negative_control` carries two controls, one varying by ROW and one constant
  WITHIN a player-season. The second exists to show the block permutation null is
  doing work: a player-season-constant noise column must die under the player-level
  null even when it survives the row-level one.