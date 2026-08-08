# E0_I0017 — SHOT QUALITY vs SCORING EFFICIENCY — PRESELECTED CANDIDATE LIST

**This file is written and hashed BEFORE any statistic is computed.** The hash is reported in
`FINDINGS.json` and `NOTES.md`. Its purpose is to convert "we screened N things" from a claim into
a checkable fact (D085 practice, recommended by the coordinator as standard E0 practice).

**Frozen at:** before `s01_build_frame.py` was first executed.
**Count: 39 candidates.** Screened against **3 efficiency outcomes** = **117 cells**.

Any candidate added or dropped after this point is reported explicitly with a reason.

---

## Outcomes (3) — identical definitions to D085 so results are directly comparable

| id | definition |
|---|---|
| `y_ppm` | `pts / minutes` — **the per-minute efficiency step D081 localised the points failure to** |
| `y_ts`  | `pts / (2*(fga + 0.44*fta))` — true shooting |
| `y_efg` | `(fgm + 0.5*fg3m) / fga` — effective field goal % |

## Reference (the thing skill is measured AGAINST)

`refB_<rt>` = **ratio of strictly-prior sums** within `(season, player_id)`, i.e.
`sum(prior numerator) / sum(prior denominator)`, `.shift(1)` applied **before** `.expanding()`,
with an expanding **same-season strictly-earlier league** mean as cold-start fallback.
`refA_<rt>` = mean of prior ratios, kept as the leakage probe's clean comparator.

**The reference IS the player's own prior efficiency.** Therefore *every* dR2 in this screen
already answers the brief's question "does prior shot quality predict efficiency **beyond** the
player's own prior efficiency?" — there is no separate test needed, and a candidate that dies here
is by construction a slower-moving proxy for the reference.

---

## FAMILY A — the player's own prior SHOT PROFILE (12)

All built from `data/shotcharts/shots_{2021..2024}_{regular,playoffs}.parquet`, aggregated to
player-game, then `.shift(1).expanding()` within `(season, player_id)` ordered by `game_date`.
Ratio-of-prior-sums, never mean-of-prior-ratios.

| id | definition |
|---|---|
| `A01_dist_mean` | prior mean `SHOT_DISTANCE` (feet) |
| `A02_share_lt5ft` | prior share of attempts with `SHOT_DISTANCE < 5` |
| `A03_share_restricted` | prior share in `SHOT_ZONE_BASIC == "Restricted Area"` |
| `A04_share_paint` | prior share in `Restricted Area` or `In The Paint (Non-RA)` |
| `A05_share_midrange` | prior share in `Mid-Range` |
| `A06_share_corner3` | prior share in `Left Corner 3` or `Right Corner 3` |
| `A07_share_abovebreak3` | prior share in `Above the Break 3` |
| `A08_share_3pa` | prior share with `SHOT_TYPE == "3PT Field Goal"` |
| `A09_share_catch_action` | prior share of `ACTION_TYPE` in the **catch//finish** set: `Cutting*`, `Alley Oop*`, `Putback*`, `Tip*`, `Dunk*`, plain `Layup Shot`, plain `Jump Shot` |
| `A10_share_selfcreate_action` | prior share of `ACTION_TYPE` in the **self-creation** set: `Pullup*`, `Step Back*`, `Driving*`, `Turnaround*`, `Fadeaway*`, `Running*`, `Floating*` |
| `A11_share_layup_action` | prior share of `ACTION_TYPE` containing `Layup`/`Dunk`/`Finger Roll` |
| `A12_share_plain_jumpshot` | prior share of `ACTION_TYPE == "Jump Shot"` exactly (the canonical catch-and-shoot label) |

## FAMILY B — RECENT FORM and TREND in shot profile (6)

Trailing-5 = the player's 5 most recent **strictly prior** appearances. Trend = trailing-5 minus
the expanding prior, so a positive value means the profile has recently moved in that direction.

| id | definition |
|---|---|
| `B01_dist_t5` | trailing-5 mean shot distance |
| `B02_lt5ft_t5` | trailing-5 share `< 5` ft |
| `B03_restricted_t5` | trailing-5 restricted-area share |
| `B04_dist_trend` | `B01 − A01` |
| `B05_lt5ft_trend` | `B02 − A02` |
| `B06_3pa_trend` | trailing-5 3PA share − `A08` |

## FAMILY C — ASSISTED SHARE (5) — the family D085 explicitly could not screen

Built by joining each shot event to its play-by-play event on `(GAME_ID, GAME_EVENT_ID == EVENTNUM)`
and reading `PLAYER2_ID != 0` on `EVENTMSGTYPE == 1` (made field goal) as "assisted". Play-by-play
covers **regular season only**; playoff appearances contribute no assist denominator but a playoff
row still carries its regular-season prior.

| id | definition |
|---|---|
| `C01_assisted_share` | prior assisted share of the player's **made** field goals |
| `C02_assisted_share_3pt` | prior assisted share of made 3PT field goals |
| `C03_assisted_share_2pt` | prior assisted share of made 2PT field goals |
| `C04_assisted_share_t5` | trailing-5 assisted share of made FG |
| `C05_assisted_trend` | `C04 − C01` |

## FAMILY D — SHOT-QUALITY INDEX (4) — the profile priced at league rates

The canonical shot-quality construct: how good is this player's **shot mix**, valued at what the
league converts those shots at. **The league zone rates are themselves strictly prior** — expanding
over shots from games strictly earlier in the same season (see TIME-WINDOW TABLE).

| id | definition |
|---|---|
| `D01_xefg_zone` | `sum_z (player prior share of zone z) * (league prior eFG in zone z)` |
| `D02_xpps_zone` | same mix priced in **points per shot** rather than eFG |
| `D03_xefg_action` | same construction over the 42 `ACTION_TYPE` labels instead of zones |
| `D04_xefg_minus_own` | `D01 − refB_efg` — does the player's shot **mix** look better than the player's own conversion? A positive value is "good shots, poor finishing" |

## FAMILY E — OPPONENT SHOT QUALITY **CONCEDED** (6) — the genuinely new matchup story

D084 killed opponent zone **CONVERSION** allowance and D085 killed twelve constructions of
opponent **outcome-based** defence. Neither touched the **shape of shots a defence concedes**.
All are `.shift(1).expanding()` within `(season, opp_team_id)` over the opponent's prior games.

| id | definition |
|---|---|
| `E01_opp_dist_conceded` | opponent's prior mean shot distance allowed |
| `E02_opp_lt5ft_conceded` | opponent's prior share of allowed shots `< 5` ft |
| `E03_opp_restricted_conceded` | opponent's prior restricted-area share allowed |
| `E04_opp_xefg_conceded` | `D01`-style shot-quality index of the shots the opponent allows |
| `E05_opp_3pa_conceded` | opponent's prior allowed 3PA share |
| `E06_opp_assisted_conceded` | opponent's prior allowed assisted share of made FG |

## FAMILY F — PLAYER PROFILE × OPPONENT CONCESSION (4)

The interaction the brief names as the one new matchup story. **D085's lesson is applied: each
interaction is screened with its own two main effects already in the base**, because the foul-draw
interaction in D085 cleared family-wise and then went to exactly zero once its own main effects
were controlled. Both forms are reported.

| id | definition |
|---|---|
| `F01_dist_x_oppdist` | `A01 * E01` |
| `F02_lt5ft_x_opplt5ft` | `A02 * E02` |
| `F03_xefg_x_oppxefg` | `D01 * E04` |
| `F04_3pa_x_opp3pa` | `A08 * E05` |

## FAMILY G — CONTROLS (2)

| id | definition |
|---|---|
| `G01_noise` | **negative control.** Seeded `standard_normal`, no relation to anything. Must die. |
| `G02_ref_echo` | **vacuous positive control.** The reference itself re-entered as a candidate. Its dR2 over a base that already contains the reference must be ~0; a non-zero value would indicate a bug in `BaseFit`. |

---

### Deliberately NOT screened, and why

| named in brief | status |
|---|---|
| early-clock (first 8 seconds) share | **IMPOSSIBLE.** `data/shotcharts/*` carries `PERIOD`, `MINUTES_REMAINING`, `SECONDS_REMAINING` — the **game** clock, not the shot clock. Play-by-play carries `PCTIMESTRING`, also the game clock. There is no shot-clock field in any input. A "time since the previous event" proxy was considered and rejected as a different construct. |
| defender-proximity share | **IMPOSSIBLE.** No tracking data in this repo; no defender-distance column exists in any input. |
| `data/zone_maps/*` | **FORBIDDEN.** `asof_granularity = "artifact"`, pooled 2021–2026, so a 2021 row has seen the holdout. Filtering does not help. Never opened. |
| `league_avg_*.parquet` in `data/shotcharts/` | **NOT OPENED.** League-average aggregates; the league rates in family D are rebuilt strictly-prior from the raw shot rows instead. |
