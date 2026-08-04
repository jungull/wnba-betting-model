# ws3_team_total_plus_allocation — DISCOVERY, development folds only

**Verdict: NULL. The hypothesis is not supported, and its motivating observation does not survive
a leakage audit.**

Nothing here may replace Arm D. Nothing was appended to `arm_registry.jsonl`. No canonical
artifact was modified.

## What was built

A two-stage model over all **35,629** Tier A candidate obligations (including the 8,278
non-appearers, realised target 0), **2,914** team-games, walk-forward by season, training-fold
statistics only.

- **Stage 1** — Poisson team-total model, offset `log(projected_team_off_possessions)`, target
  `player_attributed`. Features: personnel baseline rate, team EWMA turnover rate, shrunk
  season-to-date team rate, roster continuity (minutes and Jaccard), displaced creation
  responsibility, top-5 concentration, candidate count, cold-start fraction.
- **Stage 2** — conditional multinomial (softmax shares with ridge shrinkage), offset
  `log(pred_D_i)` so `gamma = 0` reproduces the D-proportional allocation exactly. Features:
  offensive involvement, projected role, prior turnover share, role change, responsibility
  transfer.
- **The constraint holds exactly**: max absolute deviation of the allocated player expectations
  from the stage-1 team total is `1.07e-14` across every arm; shares sum to 1 within every
  team-game to `6.7e-16`. Asserted in code.

## Result

| stage 1 (team total) | MAE | vs D aggregate (90% CI) |
|---|---|---|
| D aggregate (frozen incumbent) | 2.96745 | — |
| D aggregate, level-recalibrated | 2.96368 | +0.00377 [-0.00006, +0.00765] |
| K0 intercept-only control | 3.00586 | -0.03841 [-0.06368, -0.01377] |
| **S1 team-total model** | **3.00926** | **-0.04181 [-0.07115, -0.01324]** |

S1 vs K0: **-0.00340 [-0.03975, +0.03398]** — the nine stage-1 features add nothing over a fitted
intercept on projected possessions. S1 wins 2023-2025 and loses catastrophically in 2022
(3.4319 vs 3.0745) where it trains on 406 team-games.

| stage 2 (player allocation, 35,629 rows) | deviance | MAE | vs D (90% CI) |
|---|---|---|---|
| D frozen, unconstrained | 1.22854 | 0.84787 | — |
| S1 total x D shares | 1.23126 | 0.85263 | -0.00476 [-0.00586, -0.00377] |
| **D total x S2 shares** | **1.24366** | **0.85089** | **-0.00302 [-0.00498, -0.00104]** |
| S1 total x S2 shares | 1.24638 | 0.85597 | -0.00810 [-0.01040, -0.00583] |
| ORACLE total x D shares | 1.14043 | 0.80652 | +0.04135 [+0.03865, +0.04417] |
| ORACLE total x S2 shares | 1.15555 | 0.81039 | +0.03748 [+0.03399, +0.04096] |

Share calibration: S2 shares are *better calibrated* (slope 0.9703 vs 1.0293, mean absolute decile
gap 0.0025 vs 0.0031) yet have *worse* multinomial log loss (2.27674 vs 2.26964). Calibration
improved while discrimination degraded.

## The joint question

`D_total_x_S2_shares` answers it directly: the team total is held **exactly** at the frozen D
aggregate, so team MAE is identical to the incumbent by construction and every player-level
movement is pure allocation. On that arm the allocation makes player identity **worse** —
deviance +0.01512, MAE -0.00302 with a CI excluding zero.

Mechanism: the learned allocation shifts mass toward high-`p_active` candidates. That helps the
8,278 non-appearers (deviance 1.0046 vs 1.0348) and hurts the 27,351 appearers (1.3160 vs
1.2872). Net negative.

**Allocation is not the binding constraint; the team total is.** Holding the D shares fixed and
supplying the true candidate total is worth +0.04135 player MAE — an order of magnitude more than
anything the allocation layer moves. The D-proportional allocation is already close to the best
available given the features; the error lives in the total.

## The motivating observation does not survive

ws3 was commissioned because P2 arm G improved operational player deviance 1.22854 -> 1.22717
while worsening team MAE 2.96745 -> 2.97251. `turnover_role_context_features_v1.parquet` columns
`offensive_involvement_proxy`, `trailing_minutes_share` and `role_change` are non-null on exactly
27,351 rows and null on exactly 8,278 — **zero off-diagonal against `did_appear`**. The
missingness is an exact post-cutoff appearance oracle.

Refitting the same one-feature arm through an identical pipeline on the canonical column and on
the ws3 rebuilt column, the leaking column is worth **0.02180** deviance over the clean one —
**15.9x** the entire published arm-G gain of 0.00137.

## Defects found (all preserved)

1. **Post-cutoff missingness in a shared input** (above). Rebuilt under ws3; canonical artifact
   untouched. The ws3 rebuild is non-null on 34,860 rows; its 769 nulls mean "no prior appearance
   for that team", are cutoff-knowable, and cross `did_appear` in both directions.
2. **The permanent gate must run per training fold.** The 2021 projected-exposure regime assigns
   every Tier A candidate on a team an identical projected possession share and an identical
   `p_active`. The 2022 training fold's within-team design therefore had std `7.8e-9` and
   `5.1e-17` while the *pooled* design looked healthy. Scaling by that std drove `|X.gamma|` to
   `6.9e4` and saturated the softmax to exact 0.0 and 1.0 shares. `feature_gate.audit` catches it
   immediately — but only when run on the fold actually being fitted.
3. **Pairwise auditing misses multi-way dependency.** `proj_off_poss_share == proj_minutes_share`
   exactly and `role_change == proj_minutes_share - trailing_minutes_share`, so three declared
   features span two dimensions. A supplementary SVD rank check is included here.
4. **Compositional links are not additive links.** P2's EWMA decayed player state only on days the
   player appeared while team state decayed every team game, so the "share" reached 1.617. A
   Poisson with a log offset absorbs that; a within-team softmax saturated (deviance 8.2465).
   Corrected by decaying every tracked player on every team game, keyed by (team, player).

In every failure the optimiser **converged** — stage 2 in five Newton iterations in every fold.

## Files

- `run_ws3_two_stage.py` — the experiment, self-contained.
- `WS3_RESULTS.json` — full results, per-fold coefficients, per-fold gate, constraint proof.
- `WS3_FEATURE_GATE.json` — prefit gate audits, rank checks, leakage audit.
- `ws3_player_features_v1.parquet`, `ws3_team_features_v1.parquet` — features, nulls preserved.
- `ws3_player_predictions_v1.parquet`, `ws3_team_predictions_v1.parquet` — all arms.
- `LEDGER_UPDATE_ws3.json` — fields to merge into the shared hypothesis ledger. The shared
  ledger was deliberately **not** edited: seven other workstreams are running in parallel
  worktrees against the same file.
