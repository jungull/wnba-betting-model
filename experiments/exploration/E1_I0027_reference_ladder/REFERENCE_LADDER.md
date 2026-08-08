# The canonical reference ladder

**SHA-256 of the definition below: `8079f632ea1bc159bdb993e1e1efdf49d6f73c11e5ade1b5398bdffb8dac24db`**

Frozen by `s03_prereg.py` before any re-priced figure was computed. Implementation: `refladder.py`. Reproduce the hash with `refladder.ladder_hash()` after loading `_prereg.json`'s `canon` block.

## Why this exists

Every skill figure in this programme is a statement about a **pair** — a forecast and a reference — and the programme has been reporting them as statements about the forecast. Four instances are on the record: D090 (+46.4% vs +7.1% for one availability forecast), D093 (+0.22% vs +4.24%), D094 (minutes +3.71% vs −4.41%, an 8.12-point swing that forced a withdrawal), D099 (a headline inflated ~4x by a subset's SST). D069 ruled that such numbers cannot be rescaled and must be **re-run**. A re-run needs one fixed thing to run against. This is it.

## The rungs

| rung | what it is | prior-only construction |
|---|---|---|
| `R0_LEAGUE` | a league / base-rate constant | same-season league value over strictly earlier **dates** → previous season's league value → GRAND (named, counted, never in an evaluation set) |
| `R1_PLAYER_EXPAND` | the player's own expanding prior mean | **this is the programme's incumbent reference** — the one D094 showed is beatable by 1.3–7.8%. It is on the ladder so every legacy figure has a named rung to sit on |
| `R2_EWMA_TUNED` | a tuned EWMA of the player's own prior games | form, half-life and shrinkage **imported from D094's 15,048-cell grid**, not re-searched |
| `R3_RATE_X_MINUTES` | a rate × minutes composite | EWMA(target per minute) × EWMA(minutes, half-life 2). **Degenerate for `minutes`** and returned as NaN there rather than silently duplicating R2 |
| `R4_RICH_LOOKUP` | the player's own prior measurements of the target **and its components**, blended | walk-forward OLS on `{R0, R1, R2, R3, prior-minutes EWMA, prior-rate EWMA, prior-season player mean, log1p(n_prior)}`, coefficients fitted on seasons **strictly earlier** than the season being scored |

**The canonical rung for re-pricing is `R4_RICH_LOOKUP`.**

## Per-target settings

| target | mode | EWMA half-life | shrink toward | k | history minutes-floor | source |
|---|---|---|---|---|---|---|
| `pts` | composite | 8.0 | prior_season | 0.5 | 0.0 | D094 idx 3044 |
| `minutes` | equal | 2.0 | none | 0.0 | 0.0 | D094 idx 2379 |
| `fga` | equal | 5.0 | prior_season | 0.5 | 0.0 | D094 idx 2849 |
| `ppm` | mean_of_prior_ratios | 40.0 | prior_season | 2.0 | 0.0 | D094 idx 3662 |
| `reb` | equal | 5.0 | prior_season | 0.5 | 0.0 | selected in E1_I0027 on train seasons [2021, 2022] only, D094's grid, mode/shrinkage adopted from D094 unchanged |
| `ast` | equal | 8.0 | prior_season | 0.5 | 0.0 | selected in E1_I0027 on train seasons [2021, 2022] only, D094's grid, mode/shrinkage adopted from D094 unchanged |

Three of D094's findings are adopted wholesale rather than re-tested: EWMA beats SMA beats expanding on every measured target; shrinkage is weak and **never toward the league** — always toward the player's own prior season; and a realised-minutes floor on the history hurts monotonically, so the floor is fixed at 0 everywhere. The half-lives differ by a factor of 20 across targets (minutes 2, attempts 5, points 8, points-per-minute 40), which is itself the reason a single 'average to date' reference is wrong for all of them at once.

## The denominator rule

- Two dR2 figures are comparable only if ALL of the following hold.
- D1 SAME RESPONSE: the same variable in the same units.  No rescaling makes a dR2 on turnover-rate comparable to a dR2 on points (D072 ruling 4).
- D2 SAME SCORED ROWS: the identical row set, not merely the same n.
- D3 SAME DENOMINATOR: SST computed on that full scored row set about ITS OWN unweighted mean.  A subset's SST is never a valid denominator for a figure that will be compared to a stratum-wide figure (D099: a ~4x inflation).
- D4 SAME WEIGHTING in all three of the fit, the SSE and the SST (D072 ruling 2).
- D5 SAME BASE: both increments measured over the same reference model (D090, D094).
- If D2 fails but D1/D4/D5 hold, the figures become comparable after BOTH are re-expressed on a common denominator: dR2_common = SSE_reduction / SST_common, SST_common being the SST of the common scored row set.  If D1 fails, they are NOT comparable and no denominator fixes it.

## Time-window table (rungs **and** inference)

| stage | ingredient | window consumed | verdict |
|---|---|---|---|
| R0_LEAGUE | same-season league value | all games in the same season on STRICTLY EARLIER DATES (date-blocked, so same-day games are excluded) | prior-only |
| R0_LEAGUE | previous-season league value (chain step 2) | the whole previous season; seasons are calendar-disjoint, asserted by assert_season_disjoint | prior-only |
| R0_LEAGUE | GRAND (chain step 3) | the whole frame; FIRES ONLY on rows with neither an earlier same-season game nor a previous season in the frame; counted and reported as grand_fallback_rows | NOT prior-only -- named, counted, and never in an evaluation set |
| R1_PLAYER_EXPAND | player's expanding prior mean | the player's own same-season games at an EARLIER position in the date-sorted group; prefix arrays indexed at h, never h+1 | prior-only |
| R2_EWMA_TUNED | tuned EWMA of the player's prior games | as R1 | prior-only |
| R2_EWMA_TUNED | half-life / mode / shrinkage (pts, minutes, fga, ppm) | D094's grid, selected on 2022-2023 and evaluated on 2023-2024; imported, not re-searched | prior-only by D094's construction |
| R2_EWMA_TUNED | half-life (reb, ast) | selected inside this screen on TRAIN SEASONS ONLY, frozen and hashed before any re-priced figure | prior-only |
| R2/R3/R4 | shrinkage target `prior_season` | the player's own PREVIOUS season, whole; calendar-disjoint | prior-only |
| R3_RATE_X_MINUTES | EWMA(rate) x EWMA(minutes) | as R1, both factors | prior-only |
| R4_RICH_LOOKUP | the feature columns | each is a rung or a prior-only aggregate above | prior-only |
| R4_RICH_LOOKUP | THE BLEND COEFFICIENTS (inference step) | OLS fitted on seasons STRICTLY EARLIER than the season being scored; the earliest season is unscored | prior-only |
| re-price | lead coefficients (inference step) | refitted on seasons strictly earlier than the scored season, matching D089/D098's walk-forward protocol | prior-only |
| re-price | the denominator SST | computed on the realised response of the FULL scored row set; uses the response only, never a forecast, and is identical across every arm of a comparison | uses realised y of the scored set -- as every R2 denominator must; identical across arms |

## How to reuse this

```python
import refladder as RL
rungs, meta = RL.ladder(my_frame, 'points')      # any of pts/minutes/fga/ppm/reb/ast
ref = rungs[RL.CANONICAL_RUNG].to_numpy()        # align on meta['frame'], not on the
y   = RL.target_series(meta['frame'], 'points')  # caller's original index
sst = float(((y[m] - y[m].mean())**2).sum())     # ONE denominator, fixed for every arm
```

The frame must carry `season`, `player_id`, a datetime column, `minutes`, and the target. Nothing else is required. `RL.assert_partition` and `RL.assert_season_disjoint` run inside `ladder()` and will raise rather than let a previous-season aggregate be used where seasons overlap in calendar time.
