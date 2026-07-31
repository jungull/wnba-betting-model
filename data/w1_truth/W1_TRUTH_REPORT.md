# W1 truth set and as-of resolution — build report

Infrastructure for `w1_extraction_quality_audit_v1` (W1-A, W1-B). Makes no predictive claim and promotes nothing.

## W1-A — availability truth set

master_player rows: 33,636 over 1,492 games, seasons 2021-2026

| availability | n | share | mean minutes |
|---|---:|---:|---:|
| dressed_dnp_coach | 2,852 | 8.5% | 0.0 |
| dressed_unused | 6 | 0.0% | 0.0 |
| played | 28,263 | 84.0% | 21.2 |
| unavailable | 2,508 | 7.5% | 0.0 |
| unavailable_other | 7 | 0.0% | 0.0 |

available (played / dressed / coach's DNP): 31,121 (92.5%)

team-games: 2,984; players listed per team-game median 11, min 8, max 16
team-games listing fewer than (team-season median - 1): 241 (8.1%) — these are where an unavailable player is most likely to be INVISIBLE rather than listed, so recall computed here is recall AMONG LISTED PLAYERS only.

injury_log rows: 396 (2026-07-30 .. 2026-07-31), 0 with an unmappable team name
designations joined onto 13 player-games; 30 designation rows existed, so 17 did not match a box-score row (a player designated Out who never appears on the box score is exactly the invisible case above).

### designation versus what happened

| designation | n | played | mean minutes | available |
|---|---:|---:|---:|---:|
| Available | 5 | 100% | 15.9 | 100% |
| Out | 8 | 0% | 0.0 | 12% |

These are BASE RATES, not errors. A Questionable player who plays is the report behaving normally; W1-C compares news extractions against this table, so the table has to show what the official signal is worth before the news signal is judged against it.

### corroboration from the transaction history

transaction history: 8,340 rows, 2021-01-07 .. 2026-07-29; 114 unmappable teams
missed-game records: 5,332; matched to a box-score row for 5,278 player-games

**Agreement on the hard fact is exact: 0 of 5,278 rows flagged as a missed game by the transaction log show any minutes in the box score.** Two independently sourced records of who sat, over 2021-2026, with no conflict.

The categories carry the REASON, and there the correspondence is strong but not exact:

| history category | n | box score: unavailable | box score: coach's DNP |
|---|---:|---:|---:|
| missed_game_injury | 2,223 | 98.9% | 1.1% |
| missed_game_other | 3,055 | 9.4% | 90.6% |

Read this carefully, because a naive reading of `was_available` manufactures a disagreement that does not exist. `missed_game_other` is overwhelmingly COACH'S DECISION and NOT WITH TEAM, and this truth set deliberately classifies a coach's DNP as AVAILABLE — the player could have played. So a row can be simultaneously a 'missed game' in the transaction log and 'available' here without either source being wrong. The two columns answer different questions:

  - `availability` / `was_available` — COULD the player have played?
  - `history_missed_game` — DID the player play, and was the reason injury or something else?

The residual is the genuinely interesting part: 25 injury-categorised rows are recorded as a coach's decision in the box score, and 287 other-categorised rows are recorded as an injury. That is the reason-attribution error rate between two independent sources, and it bounds how precisely W1-C can score a news extraction's stated reason.

The box score is authoritative here and is NOT overwritten — `history_missed_game` is an extra column, so W1-C can require agreement, prefer one source, or report both, and the choice is visible rather than baked in.

## W1-B — as-of roster index

roster index: 762 (team, player) spans, 386 players, 191 players with more than one team span (trades, 7-day contracts, re-signings)
surnames shared by more than one player: 29 (e.g. allen, barker, brown, carter, charles, clark) — a surname-only mention in a headline cannot be resolved to a player at all, and is counted as AMBIGUOUS rather than guessed

## W1-B — extraction resolution

extractions: 354

| resolution | n | share |
|---|---:|---:|
| ambiguous_surname_only | 1 | 0.3% |
| no_player_named | 8 | 2.3% |
| resolved_full_name | 339 | 95.8% |
| resolved_surname_only | 5 | 1.4% |
| unresolved_no_such_player | 1 | 0.3% |

**resolution rate: 97.2%** (344/354)
**ambiguity rate: 0.3%** — a name that maps to more than one player who had already appeared by publication time. Guessing here would convert a measurable gap into an unmeasurable error.
**wrong-team rate: 8.2%** (24/293 resolved rows whose extracted team disagrees with the player's as-of team). This is the trade / 7-day-contract hazard, and it is measured against the roster AS IT WAS, not as it is today.

diagnosis — of 215 resolved rows captured from a TEAM-SPECIFIC feed, the extracted team equals the FEED'S team in 59% of cases. Among the wrong-team rows from such feeds, 50% name the feed's team rather than the player's.

That points at the pipeline, not the model: the extractor is being handed a headline that names two teams and no roster, so the team field is behaving like feed provenance rather than a player attribute. Recommendation for W1-C/W1-D, recorded here and NOT acted on: treat the extracted team as UNRELIABLE and derive team from the resolved player's as-of roster instead. That is a design change and belongs in the audit's findings, not in this build.

wrong-team examples:
  - Aaliyah Edwards extracted as Washington Mystics, as-of CON (last appearance 2026-07-28, published 2026-07-29)
  - Angel Reese extracted as Chicago Sky, as-of ATL (last appearance 2026-07-19, published 2026-07-28)
  - Angel Reese extracted as Chicago Sky, as-of ATL (last appearance 2026-07-19, published 2026-07-20)
  - Angel Reese extracted as Chicago Sky, as-of ATL (last appearance 2026-07-19, published 2026-07-28)
  - Sarah Ashlee Barker extracted as Toronto Tempo, as-of PDX (last appearance 2026-07-22, published 2026-07-28)
  - DiJonai Carrington extracted as Las Vegas Aces, as-of CHI (last appearance 2026-07-17, published 2026-07-29)
  - Brittney Sykes extracted as Minnesota Lynx, as-of TOR (last appearance 2026-07-28, published 2026-07-28)
  - Aaliyah Edwards extracted as Washington Mystics, as-of CON (last appearance 2026-07-28, published 2026-07-28)

## Limitations, stated so W1-C cannot forget them

1. **The official injury-report arm is two days deep.** `data/injury_capture/` began 2026-07-30, so it overlaps played games on essentially one date and cannot support precision or recall against official designations this season. That arm accrues FORWARD ONLY. The transaction history (2021-2026) is the retrospective substitute, and it is a different kind of evidence — scraped transaction text, not a pre-game report — so W1-C must not silently treat the two as one source.
2. **Recall is bounded by the box score.** A player absent from it is indistinguishable from a player not on the roster. Report recall as *recall among box-score-listed players*.
3. **The designation join is name-based.** Normalisation is exact after accent/punctuation/suffix stripping; no fuzzy matching, so a near-miss shows up as an unmatched row rather than as a wrong match.
4. **The roster index is appearance-based.** A signed player who has not yet played is invisible to it — which is precisely the population news is most likely to discuss, and it will show as `unresolved_not_yet_seen`.
5. **Nothing here is tuned.** No threshold in this file was chosen by looking at a result.

