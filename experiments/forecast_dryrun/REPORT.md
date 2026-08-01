# Daily forecast — DRY RUN (scratch chain; NOT the regime-D log)

*Generated 2026-08-01T14:20:06.320033+00:00 by `daily_forecast.py` (v0). Slate date 2026-08-01 (ET); forecast cutoff 2026-08-01T14:20:03.643889+00:00. Model hash `adab1085988faa3c…`; data snapshot hash `33f2556097832cde…`; code `git:b3026fc590e8`. Team model: promoted structural channels (chanreval_2026_structural_repaired/run1); player layer informational only — it does not modify the team forecast.*

**This file is engineering output. The records behind it were written ONLY to `experiments/forecast_dryrun/scratch_chain.jsonl`. The official regime-D clock starts with the first record of `forecasts/forecast_log.jsonl`, which this job refuses to touch.**

## Slate — model vs market

| Game (away @ home) | Tip (ET) | Label | Model H | Model A | Model margin (H−A) | Market home spread | Model total | Market total | Edge vs spread | Edge vs total |
|---|---|---|---|---|---|---|---|---|---|---|
| LVA @ CHI | 2026-08-01 13:00 | T-90m | 86.5 | 90.7 | -6.0 | +6.5 (11 bks) | 177.2 | 183.5 | +0.5 | -6.3 |
| NYL @ PHX | 2026-08-01 15:00 | T-90m | 84.4 | 85.6 | -2.1 | +3.0 (11 bks) | 170.0 | 177.0 | +0.9 | -7.0 |

*Market home spread is quoted book-style (negative = home favored); market-implied margin = −spread. Edge vs spread = model margin − market-implied margin. Both edges are informational — no betting layer ran (`not_applicable`, stake 0).*

## Player layer (informational — does not modify the team forecast)

- **LVA** — roster 13 (last 3 games through 2026-07-30), OUT 1 (vacated 10.0 EWMA min): Cheyenne Parker-Tyus (10.0 min EWMA). Other designations: {'Questionable': 1, 'Available': 1}. Available min-EWMA sum 225.8; long-term absent (report-listed, outside recency roster): Janiah Barker (Out, last rostered 2026-07-09).
- **CHI** — roster 13 (last 3 games through 2026-07-30), OUT 3 (vacated 71.4 EWMA min): Azura Stevens (29.8 min EWMA), Chloe Bibby (12.8 min EWMA), Skylar Diggins (28.8 min EWMA). Other designations: {'Available': 1}. Available min-EWMA sum 187.1; long-term absent (report-listed, outside recency roster): Rickea Jackson (Out, last rostered 2026-06-26); Maddy Westbeld (Out, last rostered 2026-07-12).
  - crew (LVA @ CHI): Fatou Cissoko-Stephens (Crew Chief); Sarah Williams (Referee); Tyler Mirkovich (Umpire)
- **NYL** — roster 12 (last 3 games through 2026-07-30), OUT 1 (vacated 12.1 EWMA min): Anneli Maley (12.1 min EWMA). Other designations: {'Available': 1}. Available min-EWMA sum 225.0; long-term absent (report-listed, outside recency roster): Leonie Fiebich (Out, last rostered 2026-07-18); Satou Sabally (Out, last rostered 2026-07-18).
- **PHX** — roster 11 (last 3 games through 2026-07-29), OUT 0 (vacated 0.0 EWMA min): none. Other designations: none. Available min-EWMA sum 226.9; long-term absent (report-listed, outside recency roster): Shay Ciezki (Out, last rostered 2026-07-09); Jovana Nogic (Out, last rostered 2026-06-17); UNMATCHED report rows: ['Kara Dunn (Out)'].
  - crew (NYL @ PHX): Roy Gulbeyan (Crew Chief); Amy Bonner (Referee); Ryan Sassano (Umpire)

## Degradations & notes (no-imputation rule: explicit, never silent)

- **INFO** [player-layer] CHI: Rickea Jackson (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-06-26) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] CHI: Maddy Westbeld (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-12) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] LVA: Janiah Barker (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-09) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] NYL: Leonie Fiebich (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-18) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] NYL: Satou Sabally (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-18) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] PHX: Shay Ciezki (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-09) — long-term absentee, already excluded from the availability estimate
- **WARN** [player-layer] PHX: injury-report player 'Kara Dunn' (Out) matches NO ONE in the team's season history — new signing or name mismatch; if the status is Out and the player is rostered under another spelling, the gate did NOT fire
- **INFO** [player-layer] PHX: Jovana Nogic (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-06-17) — long-term absentee, already excluded from the availability estimate

## Chain

- OFFICIAL chain verified (forecast_log.jsonl): ok=True, n_records=8, tip_sha256=6747f986a9e06fe112eaa867444a3b2e38e42cdc80a1a0342cc39c5737ca47db — record these two values out of band; tail truncation is only detectable against an external anchor
