# Daily forecast — DRY RUN (scratch chain; NOT the regime-D log)

*Generated 2026-07-31T16:15:40.611703+00:00 by `daily_forecast.py` (v0). Slate date 2026-07-31 (ET); forecast cutoff 2026-07-31T16:15:38.411873+00:00. Model hash `9c267dcaf459d3ae…`; data snapshot hash `23955229845118f6…`; code `git:59d0249fc971`. Team model: promoted structural channels (chanreval_2026_structural_repaired/run1); player layer informational only — it does not modify the team forecast.*

**This file is engineering output. The records behind it were written ONLY to `experiments/forecast_dryrun/scratch_chain.jsonl`. The official regime-D clock starts with the first record of `forecasts/forecast_log.jsonl`, which this job refuses to touch.**

## Slate — model vs market

| Game (away @ home) | Tip (ET) | Label | Model H | Model A | Model margin (H−A) | Market home spread | Model total | Market total | Edge vs spread | Edge vs total |
|---|---|---|---|---|---|---|---|---|---|---|
| SEA @ ATL | 2026-07-31 19:30 | T-8h | 89.2 | 82.1 | +7.9 | -12.5 (11 bks) | 171.3 | 178.5 | -4.6 | -7.2 |
| DAL @ WAS | 2026-07-31 19:30 | T-8h | 83.3 | 86.3 | -4.2 | +3.0 (11 bks) | 169.5 | 167.0 | -1.2 | +2.5 |
| IND @ PDX | 2026-07-31 22:00 | T-8h | 87.5 | 94.7 | -9.8 | +8.5 (11 bks) | 182.2 | 188.0 | -1.3 | -5.8 |

*Market home spread is quoted book-style (negative = home favored); market-implied margin = −spread. Edge vs spread = model margin − market-implied margin. Both edges are informational — no betting layer ran (`not_applicable`, stake 0).*

## Player layer (informational — does not modify the team forecast)

- **SEA** — roster 13 (last 3 games through 2026-07-28), OUT 2 (vacated 16.2 EWMA min): Ezi Magbegor (12.3 min EWMA), Taina Mair (3.9 min EWMA). Other designations: {'Probable': 1}. Available min-EWMA sum 212.4.
- **ATL** — roster 13 (last 3 games through 2026-07-29), OUT 1 (vacated 7.4 EWMA min): Te-Hina Paopao (7.4 min EWMA). Other designations: none. Available min-EWMA sum 212.9; long-term absent (report-listed, outside recency roster): Indya Nivar (Out, last rostered 2026-07-11).
  - crew (SEA @ ATL): Toni Patillo (Crew Chief); Agon Abazi (Referee); Kelsey Reynolds (Umpire)
- **DAL** — roster 14 (last 3 games through 2026-07-29), OUT 0 (vacated 0.0 EWMA min): none. Other designations: none. Available min-EWMA sum 234.4; cold-start 1.
- **WAS** — roster 13 (last 3 games through 2026-07-28), OUT 1 (vacated 0.2 EWMA min): Darianna Littlepage-Buggs (0.2 min EWMA). Other designations: none. Available min-EWMA sum 212.4.
  - crew (DAL @ WAS): Isaac Barnett (Crew Chief); Gerda Gatling (Referee); Ken Jones (Umpire)
- **IND** — roster 12 (last 3 games through 2026-07-28), OUT 1 (vacated 7.8 EWMA min): Damiris Dantas (7.8 min EWMA). Other designations: {'Probable': 3}. Available min-EWMA sum 210.6; long-term absent (report-listed, outside recency roster): Bree Hall (Out, last rostered 2026-07-09).
- **PDX** — roster 13 (last 3 games through 2026-07-28), OUT 1 (vacated 20.7 EWMA min): Sarah Ashlee Barker (20.7 min EWMA). Other designations: none. Available min-EWMA sum 213.6; long-term absent (report-listed, outside recency roster): Sania Feagin (Out, last rostered 2026-07-16).
  - crew (IND @ PDX): Kevin Fahy (Crew Chief); Charles Watson (Referee); RJ Johnson (Umpire)

## Degradations & notes (no-imputation rule: explicit, never silent)

- **INFO** [player-layer] ATL: Indya Nivar (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-11) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] IND: Bree Hall (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-09) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] PDX: Sania Feagin (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-16) — long-term absentee, already excluded from the availability estimate

## Chain

- scratch chain verified (scratch_chain.jsonl): ok=True, n_records=15, tip_sha256=a98013bfd9d672210b54ed2d8c9652ca127d2a20bd1b66505fc3717cf3aaa7ea — record these two values out of band; tail truncation is only detectable against an external anchor
