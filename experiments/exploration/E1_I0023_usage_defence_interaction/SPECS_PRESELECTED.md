# E1_I0023 -- PRESELECTED SPECIFICATIONS

**SHA-256 of the preregistered block:** `b8777375c40e500d97e2e79a3516d663a7a7665127e5c11bb8030bd20cac69d4`

Written by `s00_prereg.py` **before any statistic in this screen was computed**. Every later script re-hashes the list it uses and asserts equality, and reports added/dropped counts against this file.

## What is being tested

D093 (E1_I0021) established a **structural** fact: per-player sensitivity to opponent defence rises with the player's own strictly-prior usage (Spearman +0.320, family-wise p 0.0035 under the cyclic-shift null, both negative controls null). This screen asks the **different** question of whether a pooled usage x defence **interaction term improves a forecast**.

## Partition

Seasons 2021-2024. **Every scored figure is on 2022-2024**; 2021 appears only as a training fold in the walk-forward, exactly as D089 used it. 2025 and 2026 are never read, joined, plotted or described.

## The COMPLETE reference (the base in both arms)

- `refB_ppm`
- `refB_spm`
- `refB_pps`
- `refB_mpg`
- `refB_own_usg_pg`

Plus the two **main effects** `O01_own_usg_pg` and the defence term, in BOTH arms. The contrast is strictly nested: the only difference between the arms is the interaction column.

`B_SINGLE` = `['refB_ppm']` is preregistered as a **contrast only**, so the reference-sensitivity of any result is measurable. It is never the headline.

## Defence terms (3)

| term | why it is on the list |
|---|---|
| `A10_opp_defrtg` | D093's decisive axis: Spearman +0.320, family-wise p 0.0035 |
| `A01_opp_efg_allowed` | same D085 opponent-allowance family; D093 r +0.167 |
| `A02_opp_ts_allowed` | same D085 opponent-allowance family; D093 r +0.198 |

## Negative controls (2)

| id | usage side | defence side | what it tests |
|---|---|---|---|
| `NC1_noise_x_defrtg` | `G01_noise` | `A10_opp_defrtg` | noise x the real defence term: does the machinery manufacture an increment? |
| `NC2_usage_x_noise` | `O01_own_usg_pg` | `G01_noise_tvframe` | the real usage term x noise: is the usage side alone enough to fake it? |

## Responses (3) and strata (2)

- `ppm` -- points per minute (rate fitted on `y_ppm`, scaled by a prior-only minutes estimate: False)
- `points` -- points per game (rate fitted on `y_ppm`, scaled by a prior-only minutes estimate: True)
- `attempts` -- true-shooting attempts per game (rate fitted on `y_spm`, scaled by a prior-only minutes estimate: True)

- `POOLED` -- all rows in the screen frame
- `DECISION` -- D081's decision-relevant stratum: n_prior >= 8 AND prior5_minutes >= 24 -- the players anyone would actually bet on

## Cell count

**18 real cells** (3 defence x 3 responses x 2 strata) and **12 control cells**. Family-wise correction is taken across the 18 real cells.

## PRIMARY cell, fixed a priori

`A10_opp_defrtg` x `points` x `DECISION`, base `B_COMPLETE`, `walk_forward`.

D093's decisive axis, on the bettable target, on the stratum D081 identified as decision-relevant, against the complete reference, with the coefficient fitted strictly on earlier seasons. Declared BEFORE any statistic was computed.

Co-primary (mechanism check): `A10_opp_defrtg` x `ppm` x `DECISION`.

## Inference

- Contrast form: NESTED. Arm B = [1, base, usage, defence]; Arm A = [1, base, usage, defence, usage x defence]. Identical rows, identical base, identical main effects. The only difference is the interaction column.
- Null: whole-cluster sign-flip at **['opp_team_id', 'season']** (2000 draws, seed 20260808). the defence term is constant within opponent-team-season, so rows sharing an opponent-season are not independent; the row-level null is anticonservative and is reported only as the contrast
- Fit windows: walk_forward (coefficients fitted on seasons < s, applied to season s) -- the HEADLINE; in_sample (whole partition) -- DIAGNOSTIC ONLY, reported as one
- Decision rule: The interaction is KEPT only if (a) the PRIMARY cell's walk-forward paired dR2 is positive at cluster-level p < 0.05, (b) it survives the max-statistic family-wise correction across the 18 real cells, (c) both negative controls fail, and (d) the arithmetic ceiling is not smaller than D084's 0.000129. Any one of these failing is a KILL or at most a lead.

## Arithmetic ceiling

D084/D089 form: ceiling dR2 <= (points moved by 1 sd of the centred interaction term / sd of the response)^2. The ORACLE variant (best rescaling chosen with hindsight) is a DIAGNOSTIC and is excluded from every headline.

Benchmarks quoted from the decision ledger **before** this screen's ceiling was computed: D079 shot-mix `0.001127`, D084 conversion `0.000129`, D089 teammate-volume (prior-only) `0.002057` -- the largest the programme has measured.

## Step-1 reproduction targets (D093, `structure_decisive.csv`)

- `R04_opp_defrtg_spearman` = `0.3200431235648813`
- `R06_own_usage_spearman` = `0.2805225231952508`
- `family_wise_p` = `0.0035`
- `NC1_p` = `0.20439780109945027`
- `NC2_p` = `0.9385307346326837`
- `prereg_sha256_of_D093` = `8d7c8af4fce21746ce4e1ec3b58dc346a8ea696075b5149c05b9ad4817a96cbb`
- `floor` = `20`
- `min_games_per_player` = `8`

## Full cell list (30)

| cell_id | kind | usage | defence | response | stratum |
|---|---|---|---|---|---|
| `A10_opp_defrtg|ppm|POOLED` | REAL | `O01_own_usg_pg` | `A10_opp_defrtg` | ppm | POOLED |
| `A10_opp_defrtg|ppm|DECISION` | REAL | `O01_own_usg_pg` | `A10_opp_defrtg` | ppm | DECISION |
| `A10_opp_defrtg|points|POOLED` | REAL | `O01_own_usg_pg` | `A10_opp_defrtg` | points | POOLED |
| `A10_opp_defrtg|points|DECISION` | REAL | `O01_own_usg_pg` | `A10_opp_defrtg` | points | DECISION |
| `A10_opp_defrtg|attempts|POOLED` | REAL | `O01_own_usg_pg` | `A10_opp_defrtg` | attempts | POOLED |
| `A10_opp_defrtg|attempts|DECISION` | REAL | `O01_own_usg_pg` | `A10_opp_defrtg` | attempts | DECISION |
| `A01_opp_efg_allowed|ppm|POOLED` | REAL | `O01_own_usg_pg` | `A01_opp_efg_allowed` | ppm | POOLED |
| `A01_opp_efg_allowed|ppm|DECISION` | REAL | `O01_own_usg_pg` | `A01_opp_efg_allowed` | ppm | DECISION |
| `A01_opp_efg_allowed|points|POOLED` | REAL | `O01_own_usg_pg` | `A01_opp_efg_allowed` | points | POOLED |
| `A01_opp_efg_allowed|points|DECISION` | REAL | `O01_own_usg_pg` | `A01_opp_efg_allowed` | points | DECISION |
| `A01_opp_efg_allowed|attempts|POOLED` | REAL | `O01_own_usg_pg` | `A01_opp_efg_allowed` | attempts | POOLED |
| `A01_opp_efg_allowed|attempts|DECISION` | REAL | `O01_own_usg_pg` | `A01_opp_efg_allowed` | attempts | DECISION |
| `A02_opp_ts_allowed|ppm|POOLED` | REAL | `O01_own_usg_pg` | `A02_opp_ts_allowed` | ppm | POOLED |
| `A02_opp_ts_allowed|ppm|DECISION` | REAL | `O01_own_usg_pg` | `A02_opp_ts_allowed` | ppm | DECISION |
| `A02_opp_ts_allowed|points|POOLED` | REAL | `O01_own_usg_pg` | `A02_opp_ts_allowed` | points | POOLED |
| `A02_opp_ts_allowed|points|DECISION` | REAL | `O01_own_usg_pg` | `A02_opp_ts_allowed` | points | DECISION |
| `A02_opp_ts_allowed|attempts|POOLED` | REAL | `O01_own_usg_pg` | `A02_opp_ts_allowed` | attempts | POOLED |
| `A02_opp_ts_allowed|attempts|DECISION` | REAL | `O01_own_usg_pg` | `A02_opp_ts_allowed` | attempts | DECISION |
| `NC1_noise_x_defrtg|ppm|POOLED` | CONTROL | `G01_noise` | `A10_opp_defrtg` | ppm | POOLED |
| `NC1_noise_x_defrtg|ppm|DECISION` | CONTROL | `G01_noise` | `A10_opp_defrtg` | ppm | DECISION |
| `NC1_noise_x_defrtg|points|POOLED` | CONTROL | `G01_noise` | `A10_opp_defrtg` | points | POOLED |
| `NC1_noise_x_defrtg|points|DECISION` | CONTROL | `G01_noise` | `A10_opp_defrtg` | points | DECISION |
| `NC1_noise_x_defrtg|attempts|POOLED` | CONTROL | `G01_noise` | `A10_opp_defrtg` | attempts | POOLED |
| `NC1_noise_x_defrtg|attempts|DECISION` | CONTROL | `G01_noise` | `A10_opp_defrtg` | attempts | DECISION |
| `NC2_usage_x_noise|ppm|POOLED` | CONTROL | `O01_own_usg_pg` | `G01_noise_tvframe` | ppm | POOLED |
| `NC2_usage_x_noise|ppm|DECISION` | CONTROL | `O01_own_usg_pg` | `G01_noise_tvframe` | ppm | DECISION |
| `NC2_usage_x_noise|points|POOLED` | CONTROL | `O01_own_usg_pg` | `G01_noise_tvframe` | points | POOLED |
| `NC2_usage_x_noise|points|DECISION` | CONTROL | `O01_own_usg_pg` | `G01_noise_tvframe` | points | DECISION |
| `NC2_usage_x_noise|attempts|POOLED` | CONTROL | `O01_own_usg_pg` | `G01_noise_tvframe` | attempts | POOLED |
| `NC2_usage_x_noise|attempts|DECISION` | CONTROL | `O01_own_usg_pg` | `G01_noise_tvframe` | attempts | DECISION |

