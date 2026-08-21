# Daily forecast — DRY RUN (scratch chain; NOT the regime-D log)

*Generated 2026-08-19T14:20:05.176617+00:00 by `daily_forecast.py` (v0). Slate date 2026-08-19 (ET); forecast cutoff 2026-08-19T14:20:03.477556+00:00. Model hash `3a7ef1866347ec72…`; data snapshot hash `e41e6ee406679e36…`; code `git:5943846f4d01`. Team model: promoted structural channels (chanreval_2026_structural_repaired/run1); player layer informational only — it does not modify the team forecast.*

**This file is engineering output. The records behind it were written ONLY to `experiments/forecast_dryrun/scratch_chain.jsonl`. The official regime-D clock starts with the first record of `forecasts/forecast_log.jsonl`, which this job refuses to touch.**

## Slate — model vs market

| Game (away @ home) | Tip (ET) | Label | Model H | Model A | Model margin (H−A) | Market home spread | Model total | Market total | Edge vs spread | Edge vs total |
|---|---|---|---|---|---|---|---|---|---|---|
| TOR @ WAS | 2026-08-19 19:30 | T-8h | 85.8 | 81.8 | +4.4 | -11.0 (11 bks) | 167.6 | 170.5 | -6.6 | -2.9 |
| MIN @ GSV | 2026-08-19 22:10 | T-8h | 84.1 | 81.8 | +2.3 | +2.0 (11 bks) | 165.9 | 164.0 | +4.3 | +1.9 |

*Market home spread is quoted book-style (negative = home favored); market-implied margin = −spread. Edge vs spread = model margin − market-implied margin. Both edges are informational — no betting layer ran (`not_applicable`, stake 0).*

## Player layer (informational — does not modify the team forecast)

- **TOR** — roster 13 (last 3 games through 2026-08-18), OUT 5 (vacated 111.2 EWMA min): Isabelle Harrison (20.8 min EWMA), Julie Allemand (29.4 min EWMA), Maria Conde (29.4 min EWMA), Nyara Sabally (23.1 min EWMA), Ornella Bankole (8.5 min EWMA). Other designations: {'Available': 3}. Available min-EWMA sum 163.1.
- **WAS** — roster 12 (last 3 games through 2026-08-15), OUT 0 (vacated 0.0 EWMA min): none. Other designations: none. Available min-EWMA sum 212.6; long-term absent (report-listed, outside recency roster): Darianna Littlepage-Buggs (Out, last rostered 2026-08-09).
  - crew (TOR @ WAS): Isaac Barnett (Crew Chief); Jason Alabanza (Referee); Ken Jones (Umpire)
- **MIN** — roster 12 (last 3 games through 2026-08-15), OUT 2 (vacated 12.8 EWMA min): Chloe Bibby (12.8 min EWMA), Elena Buenavida (no played games). Other designations: {'Available': 1}. Available min-EWMA sum 215.0; long-term absent (report-listed, outside recency roster): Emma Cechova (Out, last rostered 2026-07-30); Liatu King (Out, last rostered 2026-07-15); UNMATCHED report rows: ['Elena Buenavida (Out)'].
- **GSV** — roster 13 (last 3 games through 2026-08-17), OUT 1 (vacated 12.7 EWMA min): Ashten Prechtel (12.7 min EWMA). Other designations: {'Questionable': 1, 'Available': 2}. Available min-EWMA sum 211.5; long-term absent (report-listed, outside recency roster): Miela Sowah (Out, last rostered 2026-07-10).
  - crew (MIN @ GSV): Maj Forsberg (Crew Chief); Randy Richardson (Referee); Angel Kent (Umpire)

## Degradations & notes (no-imputation rule: explicit, never silent)

- **WARN** [injuries] latest injury capture is 16.3 h before the cutoff (game-day cadence is hourly) — stale
- **BLOCK** [entity-resolution] Indiana Fever: designation 'Out' for 'Ugonne Onyiah' resolves to NO player identity in any season — cold start or unlisted alias. FAIL-CLOSED: the availability estimate for this team is not trustworthy until an alias or a cold-start object is supplied.
- **BLOCK** [entity-resolution] Minnesota Lynx: designation 'Out' for 'Elena Buenavida' resolves to NO player identity in any season — cold start or unlisted alias. FAIL-CLOSED: the availability estimate for this team is not trustworthy until an alias or a cold-start object is supplied.
- **BLOCK** [entity-resolution] Indiana Fever: designation 'Out' for 'Michelle Onyiah' resolves to NO player identity in any season — cold start or unlisted alias. FAIL-CLOSED: the availability estimate for this team is not trustworthy until an alias or a cold-start object is supplied.
- **INFO** [player-layer] GSV: Miela Sowah (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-10) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] MIN: Emma Cechova (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-30) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] MIN: Liatu King (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-15) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] WAS: Darianna Littlepage-Buggs (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-08-09) — long-term absentee, already excluded from the availability estimate

## Chain

- OFFICIAL chain verified (forecast_log.jsonl): ok=True, n_records=94, tip_sha256=ae79a738aaed8c466ef0d8b195fdf1f0f47f923b8c17ebc696c7e5b8b2b95d51 — record these two values out of band; tail truncation is only detectable against an external anchor
