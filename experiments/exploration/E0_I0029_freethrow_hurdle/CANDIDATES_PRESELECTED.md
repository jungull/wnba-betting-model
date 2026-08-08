# E0_I0029 -- PRESELECTED CANDIDATES (preregistered before any statistic)

**PREREG SHA256 = `e1ef0849e5f79230e27a0baa8b63ce0e6a1f24cca0a3b261cbfa7ba67c69f757`**

- candidates: **21**
- bases: **5**
- targets: **6**
- cells (candidate x base x target): **280**
- cell RUNS (280 cells x 2 strata, POOLED and DECISION): **560**
- **added since hash: 0   dropped since hash: 0**

> **ONE DEPARTURE FROM THIS DOCUMENT, MADE AFTER THE HASH AND ON MEASURED POWER.** The
> verdict-carrying null for `player_season` candidates was preregistered below as `N_CYCLIC`
> (D093's within-player cyclic shift). An injection power check showed it is **degenerate** --
> handed a signal of exactly `dR2 = 0.002057` it returns `p = 1.0000`, in 0 of 15 configurations
> detected -- because a within-player rotation leaves each player's mean intact and an own-history
> trait varies almost entirely *between* players. It was replaced by **`N_PSWAP`** (whole
> player-season series reassigned within season), whose power was then measured on the same
> injections. `N_CYCLIC` is still computed and reported for every cell in `screen_results.csv`
> (`p_N_CYCLIC_EXCLUDED_no_power`) and is excluded from every verdict. **The candidate list, the
> bases, the targets and the strata below are unchanged, so the hash stands and the added/dropped
> counts remain 0/0.** See `DEFECTS.md` and `injection_power.csv`.

The list was fixed and hashed by `s01_prereg.py`, which **loads no data and computes no statistic**.
`s00_inspect.py` ran before it, but computes only descriptive quantities the ideation queue had
**already published** (FT share of points, the zero fraction, the two marginal correlations) --
no dR2, no null, nothing that could have been used to choose a candidate. Any later change is
reported as an added/dropped count against the hash above.

## Why this screen exists

Free throws are **17.37% of points** (re-derived on the exploration partition at **0.173663**,
`run_log_s00.txt`) and are the one substantial scoring channel this programme has never screened;
D084's ruling names the route explicitly untested. `fta == 0` on **46.4% of played rows**
(re-derived: **0.464035**), which makes free-throw production a **HURDLE PROCESS** rather than a
rate. Every screen in this programme has modelled rates, so a signal living in the hurdle would
have been invisible to all of them.

**The zero mass is not a low rate.** Mean `fta` is 1.9011; a Poisson with that mean puts
**0.1494** at zero against an observed **0.4640** -- an excess of **+0.3146**. And the hurdle alone
accounts for **45.74%** of Var(ftm) by the law of total variance.

## Targets -- the three stages, plus composites and an anchor

| target | stage | rowset | exposure | description |
|---|---|---|---|---|
| `y_any_fta` | A | FULL | minutes | `1{fta>0}` -- **THE HURDLE** |
| `y_fta_given` | B | CONDITIONAL | minutes | `fta \| fta>0` -- attempts given at least one |
| `y_ftm_given` | C | CONDITIONAL | **fta** | `ftm \| fta>0` -- conversion given attempts |
| `y_fta` | AB | FULL | minutes | attempts, unconditional (composed A x B) |
| `y_ftm` | ABC | FULL | minutes | **free-throw points** (composed A x B x C) |
| `y_pts` | ANCHOR | FULL | minutes | points -- **CALIBRATION ANCHOR ONLY**, no new claim |

`y_pts` is carried through the identical machinery so the new numbers sit on the same scale as
D081/D097 rather than being a fresh construction nobody can compare against.

## Bases

D087: **REFERENCE INCOMPLETENESS is the top-ranked source of false results in this programme** --
the same result has moved 6.5x, 4.6x and 8.12 points on reference choice alone. `B_COMPLETE` puts
**every** available strictly-prior measurement of the target in the base. A candidate is only
reported ALIVE if it survives `B_COMPLETE`.

- **B_SINGLE**: `ref_mean` -- reported to EXHIBIT reference incompleteness, never to carry a verdict
- **B_COMPLETE**: `ref_mean`, `ref_ewma`, `ref_trail5`, `ref_rate_x_min`, `ref_mean_minutes`,
  `ref_trail5_minutes`, `ref_pct`, `ref_mean_pace`, `n_prior`, `is_home`
- **B_COMPLETE_PLUS_M02**: B_COMPLETE + `M02_opp_allowed_fta_pg` -- the decomposition variant. An
  opponent candidate must survive a base that already contains the closest prior **opponent**
  measurement of the target.
- **B_MATCHUP**: B_COMPLETE + `F02_prior_fd_pm` + `M01_opp_pf_pg` -- **THE D085 GUARD**. Both main
  effects of `X01` are in the base **from the start**. X01's verdict is taken here and nowhere else.
- **B_MATCHUP2**: B_COMPLETE + `F01_prior_ftr` + `M04_opp_allowed_ft_rate` -- the same guard for `X02`.

## Candidates

| name | family | varies at (null level) | description |
|---|---|---|---|
| `F01_prior_ftr` | F | `player_season` | strictly-prior FTA / strictly-prior FGA -- the free-throw rate, a shooting-style trait |
| `F02_prior_fd_pm` | F | `player_season` | strictly-prior `fouls_drawn` per prior minute -- **the own-side main effect of the D085 interaction** |
| `F03_prior_ft_pct` | F | `player_season` | strictly-prior FTM / FTA -- conversion skill |
| `F04_prior_paint_share` | F | `player_season` | strictly-prior `points_paint` / prior points -- rim pressure draws fouls |
| `F05_prior_fga_pm` | F | `player_season` | strictly-prior FGA per prior minute -- shot volume |
| `F06_prior_fg3a_share` | F | `player_season` | strictly-prior FG3A / FGA -- a jump shooter draws fewer shooting fouls |
| `F07_prior_hurdle_rate` | F | `player_season` | strictly-prior **fraction of games with fta>0** -- the hurdle's own prior measurement. Identical to `ref_mean` on `y_any_fta` and therefore **not screened on that target** (already in the base) |
| `F08_prior_fta_given` | F | `player_season` | strictly-prior mean FTA over the player's prior **fta>0** games. Runs on a **separate, smaller, labelled row set** and is never compared with the others |
| `F09_prior_starter_rate` | F | `player_season` | strictly-prior fraction of games started. **`starter_flag` itself is a TIP-TIME observation and is never used as a contemporaneous feature** |
| `F10_prior_pf_pm` | F | `player_season` | strictly-prior personal fouls **committed** per minute -- foul trouble truncates minutes |
| `M01_opp_pf_pg` | M | `opp_team_season` | opponent's strictly-prior fouls **committed** per game -- **the opponent-side main effect of the D085 interaction** |
| `M02_opp_allowed_fta_pg` | M | `opp_team_season` | opponent's strictly-prior FTA **allowed** per game -- **the closest prior opponent measurement of the target**; also an extra base column in `B_COMPLETE_PLUS_M02` |
| `M03_opp_allowed_ftm_pg` | M | `opp_team_season` | opponent's strictly-prior FTM allowed per game |
| `M04_opp_allowed_ft_rate` | M | `opp_team_season` | opponent's strictly-prior FTA-allowed / FGA-allowed -- the rate form, free of the opponent's pace |
| `M05_opp_allowed_hurdle_rate` | M | `opp_team_season` | fraction of opposing player-games with `fta>0` the opponent has allowed -- **the closest prior opponent measurement of STAGE A's target** |
| `M06_opp_pace` | M | `opp_team_season` | opponent's strictly-prior mean pace |
| `X01_fd_x_oppfoul` | X | `opp_team_season` | (F02 centred) x (M01 centred) -- **the D085 candidate, rebuilt on free throws**. Verdict taken ONLY over `B_MATCHUP` |
| `X02_ftr_x_oppftrate` | X | `opp_team_season` | (F01 centred) x (M04 centred). Verdict ONLY over `B_MATCHUP2` |
| `G01_noise` | G | `row` | **NEGATIVE CONTROL**: iid gaussian, seed-fixed, independent of everything |
| `G02_placebo_noop` | G | `row` | **NO-OP PLACEBO**: affine copy of `ref_mean__y_ftm`. dR2 ~0 by collinearity; its observed null SD is published as this screen's **floor of resolution** |
| `G03_placebo_perturbed` | G | `row` | **PERTURBATION CHECK**: `ref_mean__y_ftm` with 30% of rows swapped pairwise. **Must move the statistic** -- a placebo that is a genuine no-op tests nothing about perturbation |

## What D085 did and did NOT test

D085 killed the **interaction** `own prior FT-draw rate x opp prior fouls conceded`: it cleared
family-wise on all three outcomes and then went to **exactly zero** (0.000000 / 0.000025 /
0.000001) once its own two main effects were in the base. **Its two main effects were the CONTROL,
never the candidate**, and its twelve opponent constructions were screened against points,
rebounds and assists -- **never against free-throw production itself**. So the Step 2 question is
genuinely untested, and this screen tests it with both main effects in the base from the start.

## Fixed analysis choices

- **partition**: seasons 2021-2024 only; **HEADLINE = 2022-2024** (matching D081/D097's
  reproduction rows); 2021 reported only as a labelled power sensitivity. **2025/2026 never read.**
- **rows**: appeared player-games only (`minutes > 0`), `data/masters/master_player.parquet`
- **decision_stratum**: `n_prior >= 8` AND trailing-5 mean minutes `>= 24` -- D081 s06's
  decision-relevant stratum, so figures are comparable with D081/D085/D089/D097. **n = 5111,
  identical to D097's decision stratum.**
- **history_minutes_floor_primary**: 10.0 (sensitivity 0/5/10/15/20)
- **floor_note**: the floor is applied to the **HISTORY ONLY** -- which prior games contribute to a
  per-exposure rate. It is **never** applied to the response (D091 ruling 3). The `fta>0`
  restriction on the conditional stages **is** a response condition; that is what "given attempts"
  means, and it is why those stages are reported on a labelled subset denominator and re-expressed
  on the common denominator before any stage is compared with any other.
- **ewma_halflife**: 5.0
- **r2_convention**: plain unweighted OLS R2, SST about the **unweighted** mean (D069)
- **n_draws**: 600  **seed**: 20260808
- **nulls**: `N_ROW` (naive, reported for **inflation only**, never a verdict); `N_CYCLIC`
  (within-player cyclic shift -- D093's autocorrelation trap; a plain shuffle is anticonservative
  for running-mean regressors) for `player_season` candidates; `N_ENTITY_SWAP` at
  opponent-team-season (whole entity series reassigned within season, preserving serial structure)
  for `opp_team_season` candidates. Interactions get **both**. `p_correct_level` = MAX over the
  applicable entity-level nulls. **Cluster-robust SEs are NOT used as a substitute**: they moved t
  the wrong way in two screens in this programme.
- **family_wise**: max-t across all cells sharing a `(stratum, rowset, target)` family,
  standardised by each cell's own null mean/sd; where a cell has two applicable nulls the **least
  favourable** t is used.
- **ceiling_form**: D084/D089 form: `CEILING_dR2 = (|beta| * sd_candidate / sd_y)^2`, the variance
  share reachable if 1 sd of the signal moves the target by `beta * sd`. Benchmarks: **0.002057**
  (D089, largest measured, **alive**), **0.001127** (D079, dead), **0.000129** (D084, dead). The
  base-residualised variant is reported alongside.
- **oracle_ladder**: D081/D097 shape, **per stage**. HONEST rungs REF / H1 EWMA / H2 trailing-5 /
  H3 prior rate(floored) x prior exposure / H4 walk-forward OLS on B_COMPLETE. ORACLE rungs O1
  season-mean target / O2 ACTUAL exposure x season-mean rate / O3 within-player-season OLS on
  ACTUAL exposure / O4 ACTUAL exposure x floored prior rate / O5 prior exposure x season-mean rate.
  **EXPOSURE is minutes for stages A, B and the composites, and REALISED FTA for stage C**, because
  conversion is a per-attempt rate and minutes are not its exposure. **That substitution is the
  only deviation from D097's ladder and is declared here.**
- **common_denominator (D099)**: stages B and C live on the `fta>0` subset. A dR2 on that subset's
  SST is **not** comparable to one on the full stratum's. The headline "which stage carries the
  predictability" question is answered **only** on `SST(ftm)` over the FULL stratum, by switching
  one stage at a time between LEAGUE / HONEST / ORACLE in a composed `ftm` forecast (`s04`).
  Per-stage R2 on each stage's own SST is reported alongside and never compared across stages.
- **champion**: **never loaded, never retrained, never refitted.** Whether the champion models free
  throws at all is answered by reading its code and artifact schemas, not by running it.
- **forbidden**: `data/w1_truth/player_game_availability.csv`, `data/w1_truth/roster_asof.csv`,
  `data/zone_maps/*` -- **not opened**. Availability is rebuilt from box membership (`minutes>0`),
  the D076 method.
- **tip_time_note**: `starter_flag`, `minutes`, `fta`, `ftm`, `fouls_drawn` and `pf` for the
  **current** game are post-game observations. They appear only as responses, as declared ORACLE
  rungs, or inside strictly-prior aggregations. **No contemporaneous value of any of them is ever
  a feature.**
