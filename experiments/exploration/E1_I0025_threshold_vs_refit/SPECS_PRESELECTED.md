# E1_I0025 -- PRESELECTED SPECIFICATIONS (THRESHOLD vs REFIT ARTEFACT)

**SHA-256 of the preregistered block:** `0daa5165d4469cab26db68ccace4cd4cf54af3ad117ed59815fc699fabe2dc4b`

Written by `c00_prereg.py` **before any statistic in this screen was computed**. Every later script re-hashes the live block, asserts equality against this file, and reports added/dropped specification counts.

## The question

Is the top-tercile opponent-defence gain a THRESHOLD (genuinely concentrated in high-volume players, non-linear in volume, representable by a pooled step) or a REFIT ARTEFACT (the top tercile simply has different baseline relationships, so re-estimating every coefficient there improves fit regardless of defence)?

D098's anchors, quoted here before anything was recomputed:

| anchor | value |
|---|---|
| `tier_refit_defence_maineffect_ppm_DECISION_T3` | 0.023862917871899772 |
| `tier_refit_defence_maineffect_points_DECISION_T3` | 0.018702810112816066 |
| `pooled_linear_interaction_ppm_DECISION_ALL` | 0.00020296622240270165 |
| `pooled_linear_interaction_points_DECISION_ALL` | 0.0010051448507570257 |
| `pooled_defence_maineffect_ppm_DECISION_ALL` | 0.005028055896625616 |
| `pooled_defence_maineffect_points_DECISION_ALL` | 0.0033354248642841694 |
| `n_scored_T3_DECISION` | 1687 |
| `ceiling_decision_stratum` | 0.01280821 |
| `largest_prior_ceiling_D089` | 0.002057 |

## Reproduction gate

|reproduced - published| < 1e-9 on BOTH of D098's anchors (+0.023862917871899772 ppm and +0.018702810112816066 points). IF THIS FAILS THE SCREEN STOPS AND REPORTS, because everything downstream is meaningless otherwise.

## The specification ladder

Every rung is scored on the **identical** walk-forward top-tercile rows, with SST taken on those rows -- D098's dR2 definition. Each rung's arm B is that rung's model with **every defence-carrying column removed**, so each rung's dR2 is the increment attributable to the defence family *at that rung*.

| rung | fit | arm B | arm A | why it is on the list |
|---|---|---|---|---|
| `L1_pooled_defence_main` | POOLED (all decision-stratum training rows, all tiers) | `[1, COMPLETE reference (5), prior usage]` | `arm_B + defence` | one pooled defence coefficient. The floor of the ladder. |
| `L2_pooled_linear_interaction` | POOLED | `[1, COMPLETE reference (5), prior usage]` | `arm_B + defence + (usage - u_bar) x (defence - d_bar)` | D098's interaction, scored as a FAMILY against a no-defence base so it is on the same footing as L3 and L4. A linear interaction cannot represent a step in volume. |
| `L3_pooled_tier_dummy_x_defence` | POOLED | `[1, COMPLETE reference (5), prior usage, tier dummies D2, D3]` | `arm_B + defence + D2 x (defence - d_bar) + D3 x (defence - d_bar)` | THE DECISIVE TEST. One model, all rows, a STEP FUNCTION in volume for the defence slope. This is exactly what the THRESHOLD reading claims exists and what D098 named and did not run. |
| `L4_tier_restricted_refit` | TIER-RESTRICTED (top-tercile training rows only) -- D098's construction | `[1, COMPLETE reference (5), prior usage]` | `arm_B + defence` | D098's +0.023863. Reproduced here as the anchor and as the top of the ladder. |

## Separating the refit from the signal

| id | what | why |
|---|---|---|
| `R_nodef_refit_only` | no-defence base fitted POOLED vs the SAME no-defence base fitted TIER-RESTRICTED, scored on the identical top-tercile rows. NO DEFENCE COLUMN IN EITHER ARM. | THE SINGLE CLEANEST MEASUREMENT OF THE ARTEFACT HYPOTHESIS. Whatever this recovers is the refit's own contribution, with the defence term absent by construction. |
| `TRANSPLANT_tier_frozen` | freeze the tier-restricted model's NON-DEFENCE coefficients, then fit only a defence coefficient on the frozen model's training residual (centred defence, no free intercept). | does the defence term still earn its keep when it may not re-shuffle the others? |
| `TRANSPLANT_pooled_frozen` | same, but the frozen non-defence coefficients come from the POOLED fit. | does defence earn its keep with NO tier refit anywhere? |

## Placebos and controls

| id | what | why |
|---|---|---|
| `PLACEBO_TIERS` | the identical L4 machinery on the MIDDLE and BOTTOM terciles | if a big gain appears there too, the gain is about refitting a subset. |
| `RANDOM_TIER_ROWSHUFFLE` | tier labels permuted among masked rows WITHIN SEASON, 500 draws, L4 statistic recomputed in full inside every draw | the null distribution for 'refitting any 1,687 rows'. |
| `RANDOM_TIER_PLAYERBLOCK` | tiers assigned to WHOLE PLAYER-SEASON BLOCKS at random, size-matched, 500 draws | a row shuffle breaks the player-block structure and could make the null too easy; this keeps whole player-seasons together. |
| `NEGATIVE_CONTROL_noise_defence` | the whole ladder and the whole decomposition with G01_noise in place of the defence column | does the machinery manufacture an increment from nothing? |
| `NOOP_PLACEBO_identity_swap` | the within-date opponent-swap null code path executed with the UNPERMUTED defence column; must return the observed dR2 to 0. | plumbing check. A vacuous control has bitten this programme twice, so the swap null is ALSO required to demonstrate that it actually perturbs: the mean fraction of team-game units whose defence value changes under a real draw, and corr(original, swapped), are both reported and the fraction must exceed 0.5. |

## Nulls

- **`within_date_opponent_swap`** -- permute the defence value among the team-games played on the SAME date; the whole walk-forward fit is redone inside every draw. 500 draws, seed 20260808. THE HEADLINE NULL. It is D098's, so the numbers are comparable, and it is the correct level for a between-opponent question: it preserves the date's marginal distribution of defence exactly and destroys only WHICH opponent was faced. It also holds the refit fixed while permuting the defence column, which is precisely the contrast this screen needs.
- **`whole_cluster_sign_flip_opponent_team_season`** -- flip the sign of every row's paired squared-error difference inside a whole opponent-team-season. 2000 draws. reported alongside, at the level the defence term varies at.
- **`row_level_sign_flip`** --  CONTRAST ONLY, known anticonservative (D098 measured a median width inflation of 1.611). Never a verdict.
- **`plain_within_player_shuffle`** --  NOT USED. Anticonservative for autocorrelated regressors; the cyclic variant is the honest one and is not needed here because no per-player slope is estimated.

## THE DECISION RULE, FIXED IN ADVANCE

Let **G_refit** = the L4 statistic on ppm / DECISION / top tercile (D098's +0.023863), **G_step** = the L3 statistic on the same scored rows, **F = G_step / G_refit**, **R_nodef** = the refit's own contribution with no defence column in either arm, and **Q95_rand** = the 95th percentile of the L4 statistic over size-matched random tiers (the worse of the two random-tier variants).

**THRESHOLD** requires ALL of:

- F = G_step / G_refit >= 0.60
- G_step > 0 at within-date opponent-swap p < 0.05
- R_nodef < 0.50 * G_refit
- Q95_rand < 0.50 * G_refit
- the negative control does not improve anything (one-sided p >= 0.05)
- max(|dR2_T1|, dR2_T2) < 0.50 * G_refit

**REFIT ARTEFACT** on ANY of:

- R_nodef >= G_refit  -- refitting with no defence column at all buys as much as the defence term is credited with
- Q95_rand >= 0.60 * G_refit  -- refitting a random equally sized subset reproduces it
- the random-tier one-sided p for the real top tercile is >= 0.05
- F <= 0.15 AND Q95_rand >= 0.30 * G_refit  -- the gain is not representable without the full tier refit, and refitting subsets is worth a material fraction of it
- the negative control reproduces >= 0.50 * G_refit

**UNRESOLVED** otherwise. state exactly which criterion failed and what would settle it. In particular F <= 0.15 with a clean random-tier null means the gain is REAL BUT NOT A STEP IN THE DEFENCE SLOPE -- it requires tier-specific baseline coefficients -- and that is reported as its own outcome, not silently folded into either verdict.

## Axis resolution rule

the axis is DECLARED SEPARABLE only if the defence gain is present on one axis's top tercile and absent (< 0.30 x) on another's, measured on the DISAGREEMENT rows where the two axes' top terciles differ. If the disagreement sets are too small or all axes carry it, the honest answer is COLLINEAR AND NOT SEPARABLE, and that is reported as the result rather than as a failure.

## Full specification list (15)

- `L1_pooled_defence_main`
- `L2_pooled_linear_interaction`
- `L3_pooled_tier_dummy_x_defence`
- `L4_tier_restricted_refit`
- `R_nodef_refit_only`
- `TRANSPLANT_tier_frozen`
- `TRANSPLANT_pooled_frozen`
- `PLACEBO_TIERS`
- `RANDOM_TIER_ROWSHUFFLE`
- `RANDOM_TIER_PLAYERBLOCK`
- `NEGATIVE_CONTROL_noise_defence`
- `NOOP_PLACEBO_identity_swap`
- `AXIS_O01_own_usg_pg`
- `AXIS_refB_mpg`
- `AXIS_refB_ppm`

## Scope

- experiments\exploration\E1_I0025_threshold_vs_refit only. D098's directory, the frozen frames and the ledgers are READ-ONLY; scripts run under python -B so not even a __pycache__ entry is created outside this directory.
- never loaded, scored, retrained or modified. Fitting comparison models is authorised by D091 ruling 1.
- Partition: 2021 is a TRAINING fold only. 2025/2026 never read, joined, plotted or described. Enforced on VALUES by D098's assert_partition inside every load.

