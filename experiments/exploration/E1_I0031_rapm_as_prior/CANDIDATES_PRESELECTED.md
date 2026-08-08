# E1_I0031 -- PRESELECTED CANDIDATES (frozen before any candidate/outcome statistic)

Seed 20260808.  Exploration partition 2021-2024; RAPM emit seasons 2025 and 2026 dropped at the filter-point (579 of 1,177 rows).

## RAPM candidates (STEP 2 / STEP 3 / STEP 4)

| id | column | what it is |
|---|---|---|
| R01 | `net_100_lam2000_imp` | PRIMARY. Net RAPM at FIXED lambda=2000 -> comparable across emit seasons. Season-level, strictly prior. |
| R02 | `net_100_lam500_imp` | Net RAPM, weakest regularisation (most player-specific). |
| R03 | `net_100_lam1000_imp` | Net RAPM, lambda=1000. |
| R04 | `net_100_lam5000_imp` | Net RAPM, strongest fixed regularisation. |
| R05 | `z_net_100_imp` | Net RAPM at the artifact's own lambda_chosen, z-scored WITHIN emit season (lambda varies 50x across seasons -- see s00). |
| R06 | `z_orapm_100_imp` | OFFENSIVE RAPM, within-season z. |
| R07 | `z_drapm_100_imp` | DEFENSIVE RAPM, within-season z. |
| R08 | `log_total_poss_imp` | log(1+total possessions) behind the RAPM fit = its reliability. |
| R09 | `has_rapm_f` | Indicator that a RAPM value EXISTS. Its absence is itself information (a true rookie has no prior-season possessions). |
| R10 | `z_net_x_poss` | z_net_100 x log_total_poss: does RAPM matter more when better estimated? |

## Raw per-game plus-minus candidates (STEP 5 -- tested SEPARATELY, never pooled with RAPM)

| id | column | what it is |
|---|---|---|
| P01 | `pm_ewma5_imp` | EWMA (half-life 5) of the player's own prior SAME-SEASON per-game plus_minus. GAME-level -- can move within season. |
| P02 | `pm_ewma2_imp` | EWMA half-life 2 of prior same-season plus_minus (short memory). |
| P03 | `pm_run_mean_imp` | Expanding mean of prior same-season plus_minus. |
| P04 | `pm_per36_prior_imp` | sum(prior plus_minus)/sum(prior minutes) x 36, same season. |
| P05 | `pm_prev_season_imp` | The player's PREVIOUS-SEASON mean plus_minus (unadjusted season-level analogue of RAPM). |

## Controls

| id | column | what it is |
|---|---|---|
| N01 | `rapm_negcontrol` | NEGATIVE CONTROL. R01's values relabelled across player-seasons WITHIN emit season, fixed seed 20260808. Must show ~zero. |
| N02 | `rapm_noop_placebo` | NO-OP PLACEBO. R01 multiplied by 1.0 and re-derived through the same code path; VERIFIED to change no value (and therefore to reproduce the real statistic to machine precision). |
| N03 | `rapm_perturbed_placebo` | PERTURBED PLACEBO. R01 + 1e-6*sd; VERIFIED to actually change every value, so the placebo machinery is live. |

## Reference-component variants (STEP 3)

- **V0** -- D094 selected cell, UNCHANGED (shrink target as selected).  THE INCUMBENT.
- **V1** -- shrink target := RAPM-only map g_S(rapm), g fitted on seasons < S.
- **V2** -- shrink target := 0.5*prior_season_mean + 0.5*g_S(rapm)  (fixed weight, no fitting).
- **V3** -- shrink target := prior_season_mean where it exists, else g_S(rapm)  (coverage fill).
- **V4** -- shrink target := h_S(prior_season_mean, rapm), h an OLS fitted on seasons < S.
- **V5** -- shrink target := h_S(prior_season_mean) only -- V4 WITHOUT RAPM.  This is the DECOMPOSITION control: it isolates 'refit the map' from 'add RAPM'.

## Cold-start variants (STEP 4)

- **C0** -- D092 P5d_blend_k2: lambda(n)*own_running_mean + (1-lambda)*(league+depth+draft), lambda(n)=n/(n+2).  THE INCUMBENT, read from E1_I0020 (READ ONLY, credited).
- **C1** -- C0 with the structural prior REPLACED by g_S(rapm).
- **C2** -- C0 with the structural prior AUGMENTED by g_S(rapm) (equal-weight average).
- **C3** -- C0's structural prior + a RAPM term fitted walk-forward on seasons < S.
- **C4** -- structural prior = g_S(rapm) ONLY, no depth, no draft.  Isolates RAPM's own content.

## COMPLETE base reference per target (STEP 2)

Every prior measurement of the target already present in D081's frame, plus D094's tuned best simple estimator, which is the strongest prior-only forecast known to this programme.  A reference missing any of these would make a RAPM 'survivor' a reference-incompleteness artefact -- the top-ranked source of false results here.

- **pts** (11): `est_pts`, `ref_pts`, `pl_pts_mean5`, `pl_pts_sd5`, `prevseason_pts`, `lgexp_pts`, `role_pts`, `pl_games_prior`, `pl_minutes_prior`, `pl_career_games_prior`, `pl_prior_season_games`
- **minutes** (11): `est_minutes`, `ref_minutes`, `pl_min_mean5`, `pl_min_sd5`, `prevseason_minutes`, `lgexp_minutes`, `role_minutes`, `pl_games_prior`, `pl_minutes_prior`, `pl_career_games_prior`, `pl_prior_season_games`
- **fga** (11): `est_fga`, `ref_fga`, `pl_fga_mean5`, `pl_fga_sd5`, `prevseason_fga`, `lgexp_fga`, `role_fga`, `pl_games_prior`, `pl_minutes_prior`, `pl_career_games_prior`, `pl_prior_season_games`
- **ppm** (10): `est_ppm`, `ref_ppm`, `refA_ppm`, `prevseason_ppm`, `lgexp_ppm`, `role_ppm`, `pl_games_prior`, `pl_minutes_prior`, `pl_career_games_prior`, `pl_prior_season_games`

## Evaluation strata (fixed here, not chosen later)

- `wf_eval`  : seasons 2023+2024 (9517 rows).  D094's walk-forward evaluation rows; 2022 is a tuning season and is EXCLUDED from the headline.
- `decision_stratum` : `pl_games_prior >= 8 AND pl_min_mean5 >= 24` (D081), intersected with `wf_eval` (3549 rows).
- `data_poor` : `pl_games_prior < 3` (D092's tier), 999 rows total, 657 in wf_eval.

## Denominator rule (D099)

Every dR2 reported for a SUBSET is additionally reported on the FULL stratum's SST so the two are comparable; the column `sst_basis` names which is which.

## Null construction (constraint 4)

RAPM is CONSTANT within (season, player_id) -- verified on values in this script. The null therefore RELABELS WHOLE PLAYER-SEASONS.  A within-player shuffle would be anticonservative and the kit refuses it; where a within-group null is needed for a game-level series (the plus-minus candidates) the CYCLIC SHIFT variant is used (credit: E1_I0021/hd_base.py, D093).  Cluster-robust SEs are NOT used as a substitute anywhere.

---

**CANDIDATE LIST SHA256 (canonical form, sorted-stable):** `79331a724bbde189d17a887400e36587ee53d8cf242411b2baeec765cda7c026`

- RAPM candidates: 10
- plus-minus candidates: 5
- controls: 3
- reference variants: 6
- cold-start variants: 5
- base columns: 43 across 4 targets

**ADDED after preregistration: 0.  DROPPED after preregistration: 0.**  (Re-asserted by every downstream step against this hash; a mismatch aborts the step.)
