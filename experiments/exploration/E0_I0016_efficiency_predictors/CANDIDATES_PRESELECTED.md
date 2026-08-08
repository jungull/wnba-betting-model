# E0_I0016 — candidate list, PRESELECTED

**This file was written before any statistic was computed.** It is the whole candidate list.
Nothing was added after seeing a result; anything dropped is recorded in `NOTES.md` with the reason.

E0 has no preregistration requirement. This is voluntary, because the prompt correctly notes that
"preselecting and saying so is worth a great deal" when the deliverable is a breadth screen whose
main failure mode is a lottery ticket dressed as a finding.

## Outcomes (efficiency measures), 3, all defined on appeared rows

| id | definition | note |
|---|---|---|
| `y_ppm` | `pts / minutes` | PRIMARY. D081's decomposition axis: `points = minutes x ppm`. |
| `y_ts` | `pts / (2*(fga + 0.44*fta))` | true shooting; needs `fga + 0.44*fta > 0` |
| `y_efg` | `(fgm + 0.5*fg3m) / fga` | effective FG%; needs `fga > 0` |

`y_ppf = pts/fga` is deliberately NOT screened: it is near-collinear with `y_ts` and `y_efg` and
would inflate the family with a duplicate.

## Reference (the thing every candidate must beat)

REF-B, **ratio of prior sums** inside `(season, player_id)`, `.shift(1)` before `.expanding()`,
with a same-season strictly-earlier league-mean cold fallback. REF-A (mean of prior per-game
ratios) is built too and reported as a robustness check for survivors only.

## Candidates — 44, in 7 declared families

Entity column = the level the candidate's novel information lives at. Each candidate is screened
as TWO components:
`__between` = the entity-season mean of the feature (constant within entity-season)
`__within`  = feature minus that mean (mean-free within entity-season)
so that each component has a *valid* permutation scheme. 44 x 2 x 3 outcomes = **264 cells**.

### A — OPPONENT DEFENSIVE MATCHUP QUALITY (entity: opponent-team-season) — 12
Built from the OPPONENT's own strictly-prior same-season team games in `master_team`, where the
`opp_*` columns are what that team ALLOWED.

| id | construction |
|---|---|
| `A01_opp_efg_allowed` | `sum(opp_fgm + 0.5*opp_fg3m) / sum(opp_fga)` |
| `A02_opp_ts_allowed` | `sum(opp_pts) / (2*sum(opp_fga + 0.44*opp_fta))` |
| `A03_opp_paintpts_allowed` | `mean(opp_points_paint)` — interior allowance |
| `A04_opp_blk` | `mean(blk)` — rim protection / shot contest |
| `A05_opp_fg3pct_allowed` | `sum(opp_fg3m)/sum(opp_fg3a)` — perimeter defence |
| `A06_opp_fg3a_share_allowed` | `sum(opp_fg3a)/sum(opp_fga)` — shot-LOCATION allowance |
| `A07_opp_ftrate_allowed` | `sum(opp_fta)/sum(opp_fga)` — FT allowance |
| `A08_opp_pf` | `mean(pf)` — fouls committed |
| `A09_opp_stl` | `mean(stl)` — perimeter disruption |
| `A10_opp_defrtg` | `100*sum(opp_pts)/sum(opp_poss)` with `poss = fga - oreb + tov + 0.44*fta` |
| `A11_opp_fastbreak_allowed` | `mean(opp_points_fast_break)` |
| `A12_opp_2ndchance_allowed` | `mean(opp_points_second_chance)` |

`A06` is declared ADJACENT to the already-alive opponent zone-ATTEMPT allowance channel and to the
concurrent agent's zone-CONVERSION work. It is a box-score shadow of them, not a duplicate, and is
reported as adjacent rather than novel.

### B — FOUL-DRAW AND FREE-THROW CHANNEL (entity: player-season, except B4/B5) — 6
| id | construction |
|---|---|
| `B01_pl_ftrate` | player prior `sum(fta)/sum(fga)` |
| `B02_pl_ftpct` | player prior `sum(ftm)/sum(fta)` |
| `B03_pl_fouls_drawn_per36` | player prior `36*sum(fouls_drawn)/sum(minutes)` |
| `B04_matchup_ftrate` | `B01 x A07` — INTERACTION (entity: opponent-team-season) |
| `B05_matchup_fouldraw` | `B03 x A08` — INTERACTION (entity: opponent-team-season) |
| `B06_pl_ftpts_per36` | player prior `36*sum(ftm)/sum(minutes)` |

### C — TEAMMATE CONTEXT (entity: team-season) — 8
Availability is rebuilt from `master_player` box membership exactly as D076 did.
`data/w1_truth/player_game_availability.csv` and `roster_asof.csv` are artifact-granular / 2026 and
are NOT OPENED.

| id | construction | window |
|---|---|---|
| `C01_tm_usage_hhi` | HHI of teammates' prior season-to-date usage shares | strictly prior |
| `C02_tm_ast_per_game` | team prior mean `ast` | strictly prior |
| `C03_tm_ast_rate` | team prior `sum(ast)/sum(fgm)` | strictly prior |
| `C04_teammate_usg_present` | sum of prior usage of OTHER players in TODAY's box | **TIP-TIME** |
| `C05_top_usg_teammate_out` | top prior-usage other player absent from TODAY's box (0/1) | **TIP-TIME** |
| `C06_top_usg_teammate_out_lastgame` | same, measured on the team's PREVIOUS game | strictly prior |
| `C07_pl_usage_rank` | player's rank among teammates by prior usage (1 = primary option) | strictly prior |
| `C08_vacated_usg` | prior usage of prior-active players NOT in today's box | **TIP-TIME** |

**TIP-TIME is not strictly prior-games-only.** It is known roughly 30 minutes before tip, not the
day before. It is flagged everywhere it appears and never counted as a strictly-pregame lead.

### D — PACE / TRANSITION-EFFICIENCY (entity: team-season, D02 opponent-team-season) — 6
| id | construction |
|---|---|
| `D01_tm_poss_per40` | team prior `poss` per 40 team-minutes |
| `D02_opp_poss_per40` | opponent prior `poss` per 40 |
| `D03_pace_sum` | `D01 + D02` |
| `D04_pl_fastbreak_share` | player prior `sum(points_fast_break)/sum(pts)` |
| `D05_transition_x_pace` | `D04 x D03` — INTERACTION |
| `D06_tm_fastbreak_pts` | team prior mean `points_fast_break` |

Declared adjacency: all 27 possession-VOLUME constructions and possessions-per-minute as an
exposure channel are already dead. These are pace against **efficiency**, which is a different
outcome, but D01/D02/D03 are the same underlying quantity and are reported as adjacent.

### E — SHOT-MIX / SHOT-QUALITY PROXIES (entity: player-season, E04/E05 opponent-team-season) — 7
Box-derived only. `data/zone_maps/*` is forbidden and `data/shotcharts/*` carries **no manifest at
all** -> UNVERIFIABLE -> not used. That is a real limitation of this screen, recorded in NOTES.md.

| id | construction |
|---|---|
| `E01_pl_fg3a_share` | player prior `sum(fg3a)/sum(fga)` |
| `E02_pl_paintpts_share` | player prior `sum(points_paint)/sum(pts)` |
| `E03_pl_blocked_rate` | player prior `sum(blocks_against)/sum(fga)` — rim difficulty proxy |
| `E04_3pt_vs_opp_perim` | `E01 x A05` — INTERACTION |
| `E05_paint_vs_opp_rim` | `E02 x A04` — INTERACTION |
| `E06_pl_efg_prior` | player prior eFG — **SANITY ANCHOR**, expected ~0 because the reference already contains it |
| `E07_pl_2ndchance_share` | player prior `sum(points_second_chance)/sum(pts)` |

### F — REST / TRAVEL, INTERACTIONS ONLY (entity: player-season) — 4
The generic schedule-state main effects are DEAD (D081, 0/330 rate cells). Only mechanisms that
could plausibly act on SHOOTING specifically are screened, and F03 is included precisely so the
screen can say honestly whether this family is just the dead one wearing a hat.

| id | construction |
|---|---|
| `F01_b2b_x_fg3a_share` | back-to-back flag x `E01` |
| `F02_b2b_x_ftrate` | back-to-back flag x `B01` |
| `F03_minutes_load_7d` | player minutes played in the trailing 7 days (accumulated load, NOT rest-days) |
| `F04_load_x_fg3a_share` | `F03 x E01` |

### G — NEGATIVE CONTROL (entity: player-season) — 1
| id | construction |
|---|---|
| `G01_noise` | deterministic pseudo-random value per player-game from a fixed seed; carries no information by construction |

## What is NOT screened, and why

Everything D081 already killed: roster stability, prior-appearance depth, role volatility,
schedule state as a main effect, opponent unfamiliarity, home/away, minutes variance. Also
possessions-per-minute as exposure, the layer-2 offensive-rebound main effect, supply-side pace
instruments, the height/size family, the 27 possession-volume constructions, T2 layer-3 personnel
matching at player level. And the opponent zone-CONVERSION channel, which a concurrent agent in
`E1_I0004_efficiency_transfer` is testing directly — that directory is neither read nor written.
