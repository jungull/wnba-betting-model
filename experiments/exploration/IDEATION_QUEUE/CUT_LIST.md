# CUT LIST — ideas generated and killed before queueing, with reasons

**101 generated, 57 cut, 44 queued.** This file exists so nobody re-proposes these. A cut is not
always permanent: where a cut would be reversed by a specific new fact, that fact is named.

Cut reason codes:
- `DEAD` — the surface is closed in `CLOSED_SURFACES.md`; this is a re-proposal.
- `CEILING` — cannot plausibly clear ~0.001 dR2 on points (T7).
- `LIVE` — currently being screened by another agent; would duplicate.
- `NO_DATA` — required data does not exist in this repository.
- `UNCONFIRMABLE` — constructible in exploration, not constructible in the 2025/26 holdout (T/Q33).
- `TRAP` — the construction cannot be made honest.
- `GATED` — requires model fitting or a user decision that is not available.
- `SUBSUMED` — a queued entry already covers it.

---

## Cut as re-proposals of closed surfaces (`DEAD`)

| # | Idea | Why cut |
|---|---|---|
| C01 | Opponent defensive rating x player usage → points | `DEAD` D085, 12 constructions / 36 cells. Also `LIVE` — the surviving usage x defence interaction is `E1_I0023`. |
| C02 | Opponent 3P% allowed → player 3PM | `DEAD` D087, part of the 39 shot-quality candidates, 0 of 39. |
| C03 | Back-to-back fatigue → efficiency | `DEAD` D076/D090, schedule family closed on four screens. |
| C04 | Travel distance / timezone shift → minutes | `DEAD` D076. Tier-1 receipts issued for timezone fields (D065/D066) and the family still died. |
| C05 | Days rest x age interaction | `DEAD` schedule family + no new mechanism (D090 ruling 5). |
| C06 | Team pace → player points | `DEAD` D073, all 27 possession-volume constructions. |
| C07 | Expected possessions → player attempts | `DEAD` D073. Same family; `ABSORBED` by team fixed effects. |
| C08 | Opponent forced-turnover rate → player TOV | `DEAD` — this is I0009, already screened and re-priced down to 0.000413 (D072). |
| C09 | Assisted-share of made FG → efficiency | `DEAD` D087. |
| C10 | Average shot distance → efficiency | `DEAD` D087. |
| C11 | Early-clock share → efficiency | `DEAD` D087. |
| C12 | Height differential → rebound secure rate | `DEAD` D064 / I0008 family. |
| C13 | Lineup size mismatch → rebound opportunity | `DEAD` same family; I0003 also carried a ~72% lineup-attribution defect. |
| C14 | Per-player coefficients for the six tested relationships | `DEAD` D093 under the cyclic null (p 0.625–0.460, nothing clears anywhere). |
| C15 | Per-cluster (k-means on player style) model fitting | `DEAD` D093 — the single-player ceiling bounds every per-player and per-cluster scheme. |
| C16 | Realised-minutes floor to recover points-per-minute skill | `DEAD` D093, flat across six floors against the strongest reference. |
| C17 | Opponent shot-quality-conceded → player efficiency | `DEAD` D087. |
| C18 | Roster churn / new faces → skill | `DEAD` D076; and `tm_newfaces_prior` is the canonical T8 example. |
| C19 | Starting-five stability → minutes | `DEAD` D076. |
| C20 | `p_active` as an abstention conditioner | `DEAD` D090 ruling 4 — adds nothing over depth; explicitly do not combine. |
| C21 | Rebuild `p_active` | `DEAD` D090 ruling 1 — AUC 0.90, should not be rebuilt. |
| C22 | Home/away advantage → player production | `DEAD` D076. |
| C23 | Opponent unfamiliarity (first meeting of the season) | `DEAD` D076, dR2 <= 0.0006 after conditioning. |
| C24 | Rim-finishing specificity | `DEAD` D074. |
| C25 | Role/volume concentration → shot selection | `DEAD` D074. |
| C26 | Shot mix → points | `DEAD` D079 on a ceiling of 0.001127. |
| C27 | Conversion channel → points | `DEAD` D084 on a ceiling of 0.000129. |
| C28 | Foul-draw **matchup** (opponent-conditioned) | `DEAD` D085 — a repackaged main effect. (The player's own foul-draw **main effect** is queued as Q5; the distinction is stated there.) |

## Cut on arithmetic ceiling (`CEILING`)

| # | Idea | Why cut |
|---|---|---|
| C29 | Blocks (`blk`) as a target | `CEILING` — var 0.646, **70.9% zeros**, perfect-forecast bound on points negligible. Nothing bettable. |
| C30 | Steals (`stl`) as a target | `CEILING` — var 1.022, 51.8% zeros, corr with points 0.28 equivalent. |
| C31 | Offensive rebounds → **points** | `CEILING` — perfect-`oreb` bound on points is **0.0763**, and the forecastable fraction of `oreb` is small. (Kept as a **rebound** target in Q23.) |
| C32 | Plus-minus as a player target | `CEILING` + `TRAP` — plus-minus is a lineup quantity attributed to an individual; the attribution defect is the same ~72% class that damaged I0003. |
| C33 | `pie` / composite ratings as targets | `CEILING` — composites are not bettable quantities; no market exists for them. |
| C34 | Second-chance points as a standalone target | `CEILING` — a thin slice; queued instead as one of four channels inside Q24. |
| C35 | Personal fouls as a target | `CEILING` for betting; kept only as an **exposure moderator** in Q39. |
| C36 | Predicting the game total from player forecasts (bottom-up) | `CEILING` + `DEAD` — this is P3 layer 4, status VIABLE_BUT_UNVALIDATED, and D061's guard forbids rerunning it without a materially improved exposure artifact. |

## Cut as duplicating live work (`LIVE`)

| # | Idea | Why cut |
|---|---|---|
| C37 | Tune the EWMA span / shrinkage of the prior-history estimator | `LIVE` — `E1_I0022_optimal_simple_estimator` is running exactly this. |
| C38 | Does the champion beat a well-tuned prior-history baseline? | `LIVE` — same screen. |
| C39 | Usage x opponent defence interaction (D093's one positive) | `LIVE` — `E1_I0023_usage_defence_interaction`. |
| C40 | Characterise rebound and assist residuals | `LIVE` — `E0_I0024_reb_ast_characterisation`. |
| C41 | Fix `SCHEME_WITHIN` to add a cyclic variant | `LIVE` — the kit repair is in flight; `_screen_kit` is off-limits. |

## Cut for missing data (`NO_DATA`)

| # | Idea | Why cut |
|---|---|---|
| C42 | Vertical jump / reach / wingspan → rebounding | `NO_DATA` — D064: "VERTICAL JUMP AND REACH ARE NOT COLLECTED ANYWHERE". **Reversible by acquisition.** |
| C43 | Market-implied player totals as a reference | `NO_DATA` on the exploration partition — D071/D073: zero in-partition rows in `bookie_totals_per_game.csv`; `bookie_consensus_total` 100% NULL on the 229 rows dated 2024. **Reversible by acquisition** (flagged in Q42). |
| C44 | Closing-line value / market movement | `NO_DATA` in-partition; also belongs to S-MKT under the frozen four-system separation (D061). |
| C45 | Pre-game injury report / official inactives | `NO_DATA` — this is the acquisition itself. Priced in Q42; the recoverable-by-construction part is Q7. |
| C46 | Coaching identity / scheme change → rotation | Partly available — `injury_history.csv` has **49 `front_office` rows** with dated coaching changes (D008 confirmed this against a manufactured negative). But 49 events across 76 team-seasons is far too thin to screen. `CEILING` on sample size. |
| C47 | Practice participation / load management reports | `NO_DATA`. |
| C48 | Player tracking (speed, distance, touches) | `NO_DATA` — not collected. **Reversible by acquisition**, and would be expensive. |

## Cut as unconfirmable in the holdout (`UNCONFIRMABLE`)

| # | Idea | Why cut |
|---|---|---|
| C49 | Referee crew → foul rate → FT volume | `UNCONFIRMABLE` — `data/officials/` holds 996 files: 2021–2024 covered, **2025 = 108/310, 2026 = 0/215**. Discoverable, never confirmable. Genuinely plausible mechanism; **reversible by backfilling officials for 2025–2026.** |
| C50 | Any feature requiring raw play-by-play event sequences | `UNCONFIRMABLE` — raw pbp is 0/215 in 2026 (Q33). Note this does **not** apply to `possessions.parquet` or `data/shotcharts/`, which are all-season. |
| C51 | Shot-clock-state features (time remaining when shot taken) | `UNCONFIRMABLE` via raw pbp; **partly reversible** via the shotchart clock fields, which are all-season — but D087 already killed early-clock share. |

## Cut as traps that cannot be made honest (`TRAP`)

| # | Idea | Why cut |
|---|---|---|
| C52 | Season-long lineup effectiveness from `data/lineups/*.parquet` | `TRAP` — these are **season-aggregate totals retrieved 2026-08-06** (`GROUP_SET='Lineups'`, `vendor_ts_semantics='not_a_timing_claim'`). Any exploration-season use reads the future of every row. Trap T1 in its purest form. |
| C53 | Anything using `data/w1_truth/player_game_availability.csv` or `roster_asof.csv` | `TRAP` + forbidden — artifact-granular, `fit_through_season 2026`. Explicitly off-limits at E0/E1. |
| C54 | Tonight's `dnp_reason` / tonight's `starter_flag` as features | `TRAP` — post-game and post-lineup respectively. Prior-game versions are queued (Q25, Q36). |
| C55 | Using realised minutes as a regressor for points | `TRAP` — D091 ruling 3: legitimate for a measurement question, **never** presentable as a forecasting increment. Any screen doing this must carry the conditioning in every statement. |
| C56 | Per-player residual correction learned on the same rows it scores | `TRAP` — this is F1 (D075/D078), already measured and downgraded to MINOR but user-gated; repeating the construction would re-introduce it. |
| C57 | Reporting a raw-MAE reduction as a conditional edge | `TRAP` — T8. `pts__pred_point` cut points MAE 9.9% while moving skill +0.00007. Listed as a cut because it was generated as an idea ("find where MAE is lowest and bet there") and is exactly the error D076 named. |

---

## Notes on borderline cuts a successor may wish to revisit

- **C46 (coaching identity)** is cut on sample size, not on mechanism. If the `front_office` records
  were extended backwards or supplemented, the mechanism (rotation philosophy changes minutes
  allocation) is one of the more plausible unscreened ideas in basketball.
- **C49 (referees)** is cut only on holdout coverage. It is the single cut most likely to be worth
  reversing, and the reversal is cheap: backfill `data/officials/` for 2025–2026.
- **C42/C48** are acquisition-reversible and should be mentioned if the user revisits data purchases.
- **Q44** in the queue is the weakest surviving entry and is a legitimate candidate for demotion to
  this list; it is queued only because it is cheap and completes the bios surface.
