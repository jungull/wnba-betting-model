# Daily forecast — DRY RUN (scratch chain; NOT the regime-D log)

*Generated 2026-07-30T21:27:04.990313+00:00 by `daily_forecast.py` (v0). Slate date 2026-07-30 (ET); forecast cutoff 2026-07-30T21:27:03.490703+00:00. Model hash `1fd0b74945a9b9e1…`; data snapshot hash `8e513a75d4225a66…`; code `git:ba2ea129f7d3`. Team model: promoted structural channels (chanreval_2026_structural_repaired/run1); player layer informational only — it does not modify the team forecast.*

**This file is engineering output. The records behind it were written ONLY to `experiments/forecast_dryrun/scratch_chain.jsonl`. The official regime-D clock starts with the first record of `forecasts/forecast_log.jsonl`, which this job refuses to touch.**

## Slate — model vs market

| Game (away @ home) | Tip (ET) | Label | Model H | Model A | Model margin (H−A) | Market home spread | Model total | Market total | Edge vs spread | Edge vs total |
|---|---|---|---|---|---|---|---|---|---|---|
| CON @ CHI | 2026-07-30 20:10 | T-90m | 86.8 | 83.1 | +3.7 | -5.5 (11 bks) | 169.9 | 175.5 | -1.8 | -5.6 |
| MIN @ TOR | 2026-07-30 20:10 | T-90m | 85.6 | 92.9 | -9.8 | +12.5 (11 bks) | 178.5 | 186.0 | +2.7 | -7.5 |
| NYL @ LVA | 2026-07-30 22:10 | T-90m | 91.8 | 85.1 | +7.1 | -4.5 (11 bks) | 176.9 | 181.5 | +2.6 | -4.6 |

*Market home spread is quoted book-style (negative = home favored); market-implied margin = −spread. Edge vs spread = model margin − market-implied margin. Both edges are informational — no betting layer ran (`not_applicable`, stake 0).*

## Player layer (informational — does not modify the team forecast)

- **CON** — roster 14 (last 3 games through 2026-07-28), OUT 4 (vacated 61.9 EWMA min): Aaliyah Edwards (16.6 min EWMA), Ashlon Jackson (8.2 min EWMA), Brittney Griner (27.8 min EWMA), Hailey Van Lith (9.2 min EWMA). Other designations: none. Available min-EWMA sum 194.1.
- **CHI** — roster 13 (last 3 games through 2026-07-22), OUT 3 (vacated 67.9 EWMA min): Azura Stevens (29.8 min EWMA), Chloe Bibby (9.3 min EWMA), Skylar Diggins (28.8 min EWMA). Other designations: {'Questionable': 1}. Available min-EWMA sum 170.0; cold-start 1; long-term absent (report-listed, outside recency roster): Maddy Westbeld (Out, last rostered 2026-07-12); Rickea Jackson (Out, last rostered 2026-06-26).
  - crew (CON @ CHI): Isaac Barnett (Crew Chief); Tiara Cruse (Referee); Gerda Gatling (Umpire)
- **MIN** — roster 12 (last 3 games through 2026-07-28), OUT 1 (vacated 16.3 EWMA min): Emma Cechova (16.3 min EWMA). Other designations: {'Questionable': 1}. Available min-EWMA sum 221.3.
- **TOR** — roster 14 (last 3 games through 2026-07-28), OUT 1 (vacated 29.4 EWMA min): Brittney Sykes (29.4 min EWMA). Other designations: {'Questionable': 1, 'Probable': 1}. Available min-EWMA sum 258.2.
  - crew (MIN @ TOR): Maj Forsberg (Crew Chief); Marcy Williams (Referee); Genesis Perrymond (Umpire)
- **NYL** — roster 11 (last 3 games through 2026-07-28), OUT 0 (vacated 0.0 EWMA min): none. Other designations: none. Available min-EWMA sum 220.4; long-term absent (report-listed, outside recency roster): Satou Sabally (Out, last rostered 2026-07-18); Marine Johannes (Available, last rostered 2026-07-18); Leonie Fiebich (Out, last rostered 2026-07-18).
- **LVA** — roster 13 (last 3 games through 2026-07-28), OUT 1 (vacated 10.0 EWMA min): Cheyenne Parker-Tyus (10.0 min EWMA). Other designations: {'Doubtful': 1, 'Questionable': 1}. Available min-EWMA sum 223.8; long-term absent (report-listed, outside recency roster): Janiah Barker (Out, last rostered 2026-07-09).
  - crew (NYL @ LVA): Randy Richardson (Crew Chief); Angelica Suffren (Referee); Angel Kent (Umpire)

## Degradations & notes (no-imputation rule: explicit, never silent)

- **INFO** [player-layer] CHI: Maddy Westbeld (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-12) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] CHI: Rickea Jackson (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-06-26) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] LVA: Janiah Barker (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-09) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] NYL: Satou Sabally (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-18) — long-term absentee, already excluded from the availability estimate
- **WARN** [player-layer] NYL: Marine Johannes (Available) is outside the 3-game recency roster (last rostered 2026-07-18) but NOT Out — a possible RETURN the recency roster cannot see; the availability estimate may understate tonight's rotation
- **INFO** [player-layer] NYL: Leonie Fiebich (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-18) — long-term absentee, already excluded from the availability estimate
- **INFO** [trend-staleness] CHI last played 2026-07-22 (8 days before the slate) — trend features are that old (schedule gap, not a data failure: masters are current through yesterday)

## Chain

- scratch chain verified: ok=True, n_records=12, tip_sha256=41deb92c05ae6c840924fd9c0b4bce805dac0fcbe257a370b43ed400d505adee — record these two values out of band; tail truncation is only detectable against an external anchor
