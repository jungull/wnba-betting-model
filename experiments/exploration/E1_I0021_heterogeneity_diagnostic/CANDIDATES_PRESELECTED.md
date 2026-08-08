# E1_I0021 -- PRESELECTED RELATIONSHIPS AND FLOOR GRID

**SHA-256 of the preregistered block:** `8d7c8af4fce21746ce4e1ec3b58dc346a8ea696075b5149c05b9ad4817a96cbb`

Written by `s00_prereg.py` BEFORE any statistic in this screen was computed. Every later script re-hashes the list it actually uses and asserts equality, and reports added/dropped counts against this file.

## Partition

Seasons 2022-2024 only (the 2021 fold is degenerate: n_train_rows=0). 2025 and 2026 are never read, joined, plotted or described.

## Minutes-floor grid (realised minutes of the game being scored)

`[0, 10, 15, 20, 25, 30]`  -- headline floor for the pooling diagnostic: **20 minutes**, fixed a priori as 'a rotation player played a real game', not chosen by evidence.

**CONDITIONING LABEL.** A realised-minutes floor conditions on an OUTCOME. Every figure under a floor answers the measurement question 'given a player got meaningful minutes, is their rate predictable?' and is NOT a live forecasting increment, because a real forecast must predict minutes first.

## Preregistered relationships (6)

| id | frame | x | y | expected sign | why it is on the list |
|---|---|---|---|---|---|
| `R01_prior_efficiency_persistence` | D085_eff | `refA_ppm_floor` | `y_ppm_floor` | positive | D081 (E0_I0015) -- points-per-minute vs the player's own strictly-prior expanding mean rate; the persistence term the whole program leans on |
| `R02_opp_efg_allowed` | D085_eff | `A01_opp_efg_allowed` | `y_ppm_floor` | positive | D085 (E0_I0016) opponent-allowance family, cell A01 |
| `R03_opp_ts_allowed` | D085_eff | `A02_opp_ts_allowed` | `y_ppm_floor` | positive | D085 (E0_I0016) opponent-allowance family, cell A02 |
| `R04_opp_defrtg` | D085_eff | `A10_opp_defrtg` | `y_ppm_floor` | positive | D085 (E0_I0016) opponent-allowance family, cell A10 |
| `R05_teammate_volume_pregame` | D089_tv | `P01_c04_prevgame` | `y_ppm_floor` | negative | D089 (E1_I0018) teammate-volume channel, STRICTLY PRE-GAME variant. The tip-time variant T01 is deliberately EXCLUDED: D089 ruling 2 forbids quoting it as a result because it is computed from a post-game observation |
| `R06_own_usage` | D089_tv | `O01_own_usg_pg` | `y_ppm_floor` | positive | D089 (E1_I0018) own-usage term, the player-side half of the volume channel |

## Negative controls (2)

| id | frame | x | y | what it is |
|---|---|---|---|---|
| `NC1_noise_eff_frame` | D085_eff | `G01_noise` | `y_ppm_floor` | pure noise column frozen into D085's screen frame |
| `NC2_noise_tv_frame` | D089_tv | `G01_noise` | `y_ppm_floor` | pure noise column frozen into D089's screen frame |

## Step-1 components (D081 reproduction targets, 9 cells)

| component | kind | y | model forecast | frozen reference | floor-refit reference |
|---|---|---|---|---|---|
| minutes | LEVEL | `y_minutes` | `minutes__pred_point` | `ref_minutes` | `refF_minutes` |
| fga | LEVEL | `y_fga` | `fga__pred_point` | `ref_fga` | `refF_fga` |
| pts | LEVEL | `y_pts` | `pts__pred_point` | `ref_pts` | `refF_pts` |
| pts_per_min | RATE | `r_ppm` | `mdl_ppm` | `refA_ppm` | `refFA_ppm` |
| pts_per_min | RATE | `r_ppm` | `mdl_ppm` | `refB_ppm` | `refFB_ppm` |
| fga_per_min | RATE | `r_fpm` | `mdl_fpm` | `refA_fpm` | `refFA_fpm` |
| fga_per_min | RATE | `r_fpm` | `mdl_fpm` | `refB_fpm` | `refFB_fpm` |
| pts_per_fga | RATE | `r_ppf` | `mdl_ppf` | `refA_ppf` | `refFA_ppf` |
| pts_per_fga | RATE | `r_ppf` | `mdl_ppf` | `refB_ppf` | `refFB_ppf` |

## Step-3 structure covariates (used ONLY if step 2 is positive, 6)

- `usage_tier_prior`
- `minutes_tier_prior`
- `role_stability_prior`
- `team_pace_prior`
- `experience_prior`
- `n_games_retained`

## Inference

- Null scheme: WITHIN-PLAYER permutation: each player's own games are shuffled, which preserves that player's sample size and their marginal distribution of x and destroys ONLY the within-player alignment of x to y. The statistic is the SD of per-player slopes, computed by the identical code path on the real frame and on every draw.
- Statistic: sd of per-player OLS slopes (both precision-weighted and unweighted), players with >= min_games rows after the floor
- Draws: 2000, seed 20260808, min games per player 8
- Decision rule: A relationship is called HETEROGENEOUS only if the observed spread exceeds the within-player null at p < 0.05 AND survives the max-statistic family-wise null across the 6 preregistered relationships at the headline floor AND its negative control does not.

