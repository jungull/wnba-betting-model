"""E1_I0022 STEP 2 -- PREREGISTER AND HASH THE ESTIMATOR GRID.

Run BEFORE any skill number is computed.  Writes ESTIMATOR_GRID.md, hashes the enumerated grid and
the specification text, and records added/dropped counts against the declared design.  s03 refuses
to run unless the hash it recomputes matches the one written here.
"""
import json
import os
from datetime import datetime

import ose_base as B

rows = B.grid_rows()
ghash, n = B.grid_hash()

spec = """# E1_I0022 -- PREREGISTERED ESTIMATOR GRID

**Preregistered %s, BEFORE any skill number for any grid cell was computed.**
The only numbers computed before this file was written are the STEP 1 reproduction of D081's
frozen per-component skill table (which is a reproduction of someone else's published result, not a
result of this screen) and row/column counts.

## What is being built

A grid of **strictly prior-games-only** estimators. Every cell is the same object:

    est(row i) = shrink( SUM_j w_j * num_j / SUM_j w_j * den_j , n_eff , T , k )

where j ranges over the games of the SAME (season, player_id) that are **strictly earlier in date
order** than row i and whose **realised minutes >= FLOOR**; `w_j` is the MEMORY weight; `(num,den)`
is the FORM; `T` is the SHRINKAGE target; `k` is the shrinkage strength in units of prior games;
and `n_eff = SUM_j w_j` is the decayed count of admissible prior games.

    shrink(raw, n_eff, T, k) = (n_eff * raw + k * T) / (n_eff + k)

k = 0 is exactly the unshrunk estimator. With no admissible history, the estimator returns T.

## The five dimensions

### 1. TARGET (4)
`pts`, `minutes`, `fga`, `ppm` (= points per minute, y = pts/minutes).

### 2. FORM / aggregation MODE (9 target-mode pairs)
| target | modes |
|---|---|
| `pts` | `equal` (num=pts, den=1); `minutes_weighted` (num=pts*min, den=min); `composite` (= the `minutes/equal` estimate of the SAME cell times the `ppm/ratio_of_prior_sums` estimate of the SAME cell) |
| `minutes` | `equal`; `minutes_weighted` |
| `fga` | `equal`; `minutes_weighted` |
| `ppm` | `ratio_of_prior_sums` (num=pts, den=minutes); `mean_of_prior_ratios` (num=pts/minutes, den=1) |

**Ratio-of-prior-sums vs mean-of-prior-ratios is a DIMENSION, not a choice** (D093: which one wins
flips under a minutes floor). For the rate target it is the `den` column; for the level targets the
same axis appears as `equal` vs `minutes_weighted`.

### 3. MEMORY (19)
- `expanding` (all admissible prior games, weight 1)
- `sma`, window w in {1, 2, 3, 5, 8, 10, 15, 20, 30} (last w admissible prior games, weight 1)
- `ewma`, half-life h in {0.5, 1, 2, 3, 5, 8, 12, 20, 40} admissible prior games
  (w_j = 0.5^(age/h), age 0 = most recent admissible prior game)

Deliberately spans from **1 game** (pure last-game) to **effectively infinite** (expanding /
half-life 40, longer than any player's season).

### 4. SHRINKAGE (22)
- `none` (k = 0)
- toward `league`, k in {0.5, 1, 2, 4, 8, 16, 32}
- toward `prior_season` (the player's OWN previous-season value), k in the same set
- toward `role` (same-season expanding value within the player's previous-season minutes-per-game
  tercile), k in the same set

Prior-only chains, all documented in NOTES.md TIME-WINDOW TABLE:
- `league` = same-season expanding value over **strictly earlier DATES** -> previous season's
  league value -> GRAND (whole-frame value; fires only on opening-date rows of 2022, counted).
- `prior_season` = player's previous-season value -> `league` chain.
- `role` = same-season expanding value within (season, prior-season MPG tercile) over strictly
  earlier dates -> `league` chain. Tercile cutpoints come from the PREVIOUS season only.

### 5. REALISED-MINUTES FLOOR ON THE HISTORY (4)
FLOOR in {0, 5, 10, 15} minutes. A prior game with realised minutes below FLOOR is **removed from
the history entirely** (it contributes to no sum and to no count). The floor is **never** applied to
the row being scored, so every cell is scored on the identical row set.
D093 measured that such a floor removes 39.3%% of per-minute variance.

### 6. DEPTH ADAPTATION (not a grid axis -- a second SELECTION protocol)
The grid is swept once. Hyperparameters are then selected in two ways and both are reported:
- **GLOBAL**: one cell for all rows.
- **DEPTH-ADAPTIVE**: an independent cell per prior-appearance tier
  (`pl_games_prior` in 0, 1-2, 3-7, 8-14, 15-24, 25+), each selected on the tuning rows of that
  tier only. D092 found the champion emits a constant below 3 appearances and that skill is
  NON-MONOTONE in depth (worst at 2 priors, not 0), so a single setting is TESTED, not assumed.

## Grid size

4 targets -> 9 target-mode pairs x 19 memory x 22 shrinkage x 4 floors = **%d cells**.

## Tuning protocol (fixed here, before any number)

Walk-forward by season. The 2021 fold is degenerate (n_train_rows = 0) and absent from the frame.

| split | hyperparameters selected on | scored on |
|---|---|---|
| A | season 2022 | season 2023 |
| B | seasons 2022 + 2023 | season 2024 |

**WALK-FORWARD EVALUATION ROWS = 2023 union 2024** (the union of the two `scored on` columns).
Selection criterion = **lowest MAE on the tuning rows**, computed by the identical code path used on
the evaluation rows. No evaluation number is consulted by any selection.

The IN-SAMPLE counterfactual (cell chosen by lowest MAE on the evaluation rows themselves, then
scored on those same rows) is computed and reported **only** as the optimism gap. D093 found
in-sample R2 of +0.04 to +0.18 whose walk-forward R2 was NEGATIVE, so the gap is reported for every
target.

## Decisive comparison (fixed here)

`champion_skill_vs_best_simple = 1 - MAE_champion / MAE_best_simple`, both on the SAME walk-forward
evaluation rows, for each of pts / minutes / fga / ppm, reported: pooled; on D081's decision stratum
(`pl_games_prior >= 8` AND `pl_min_mean5 >= 24`); and by prior-appearance tier.
Paired inference by (season, player_id) BLOCK SIGN-FLIP. Any null over the estimator's own series
uses a WITHIN-PLAYER CYCLIC SHIFT, never a plain shuffle (D093: the plain shuffle gave p = 0.0015
where the honest null gave p = 0.39), and the control is verified to actually perturb the statistic
(D093: a player-key relabel was a literal no-op at sd 5.2e-17).

## Nothing is fitted on the champion

The champion's stored forecasts (`pts__pred_point`, `minutes__pred_point`, `fga__pred_point`, and
`mdl_ppm = pts__pred_point / minutes__pred_point`) are **scored only**. D091 authorises fitting
simple estimators; nothing here refits, recalibrates or reweights the champion.

## Grid hash

    sha256 over the sorted enumeration of (target, mode, memory_kind, memory_param,
                                           shrink_target, shrink_k, floor), one per line, "|"-joined

    GRID_SHA256 = %s
    N_CELLS     = %d
    ADDED after preregistration   = 0
    DROPPED after preregistration = 0
""" % (datetime.now().strftime("%Y-%m-%d %H:%M"), n, ghash, n)

with open(os.path.join(B.OUT, "ESTIMATOR_GRID.md"), "w", encoding="utf-8") as fh:
    fh.write(spec)

spec_hash = B.sha256_text(spec)
meta = {"grid_sha256": ghash, "n_cells": n, "spec_sha256": spec_hash,
        "targets": B.TARGETS, "modes": B.MODES,
        "memories": [list(m) for m in B.MEMORIES],
        "shrinks": [list(s) for s in B.SHRINKS], "floors": B.FLOORS,
        "added_after_prereg": 0, "dropped_after_prereg": 0,
        "prereg_time": datetime.now().isoformat(timespec="seconds")}
json.dump(meta, open(os.path.join(B.OUT, "_prereg.json"), "w"), indent=2)

B.hdr("PREREGISTRATION WRITTEN")
print("  ESTIMATOR_GRID.md   spec sha256 = %s" % spec_hash)
print("  GRID_SHA256         = %s" % ghash)
print("  N_CELLS             = %d" % n)
print("  target-mode pairs   = %d" % sum(len(v) for v in B.MODES.values()))
print("  memory settings     = %d" % len(B.MEMORIES))
print("  shrinkage settings  = %d" % len(B.SHRINKS))
print("  floors              = %d" % len(B.FLOORS))
print("  added=0 dropped=0")
print("DONE s02")
