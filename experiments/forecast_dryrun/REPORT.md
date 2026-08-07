# Daily forecast — DRY RUN (scratch chain; NOT the regime-D log)

*Generated 2026-08-07T14:20:05.713465+00:00 by `daily_forecast.py` (v0). Slate date 2026-08-07 (ET); forecast cutoff 2026-08-07T14:20:03.529881+00:00. Model hash `0fa225211ddb21db…`; data snapshot hash `9481457096ee177d…`; code `git:9cfe22e61d77`. Team model: promoted structural channels (chanreval_2026_structural_repaired/run1); player layer informational only — it does not modify the team forecast.*

**This file is engineering output. The records behind it were written ONLY to `experiments/forecast_dryrun/scratch_chain.jsonl`. The official regime-D clock starts with the first record of `forecasts/forecast_log.jsonl`, which this job refuses to touch.**

## Slate — model vs market

| Game (away @ home) | Tip (ET) | Label | Model H | Model A | Model margin (H−A) | Market home spread | Model total | Market total | Edge vs spread | Edge vs total |
|---|---|---|---|---|---|---|---|---|---|---|
| PHX @ CON | 2026-08-07 19:30 | T-8h | 80.3 | 83.3 | -3.9 | +6.5 (11 bks) | 163.5 | 174.5 | +2.6 | -11.0 |
| ATL @ WAS | 2026-08-07 19:30 | T-8h | 83.1 | 83.9 | -1.4 | +6.5 (11 bks) | 167.1 | 170.5 | +5.1 | -3.4 |
| GSV @ DAL | 2026-08-07 21:30 | T-8h | 80.5 | 80.7 | -0.4 | -1.0 (11 bks) | 161.2 | 161.5 | -1.4 | -0.3 |

*Market home spread is quoted book-style (negative = home favored); market-implied margin = −spread. Edge vs spread = model margin − market-implied margin. Both edges are informational — no betting layer ran (`not_applicable`, stake 0).*

## Player layer (informational — does not modify the team forecast)

- **PHX** — roster 11 (last 3 games through 2026-08-05), OUT 1 (vacated 0.0 EWMA min): Kara Dunn (no played games). Other designations: {'Available': 2}. Available min-EWMA sum 228.0; long-term absent (report-listed, outside recency roster): Jovana Nogic (Out, last rostered 2026-06-17); Shay Ciezki (Out, last rostered 2026-07-09); UNMATCHED report rows: ['Kara Dunn (Out)'].
- **CON** — roster 14 (last 3 games through 2026-08-02), OUT 4 (vacated 47.7 EWMA min): Aaliyah Edwards (16.6 min EWMA), Hailey Van Lith (9.2 min EWMA), Ashlon Jackson (9.2 min EWMA), Raegan Beers (12.6 min EWMA). Other designations: {'Questionable': 1}. Available min-EWMA sum 196.9.
  - crew (PHX @ CON): Isaac Barnett (Crew Chief); Ashley Gloss (Referee); Kelsey Reynolds (Umpire)
- **ATL** — roster 13 (last 3 games through 2026-08-05), OUT 1 (vacated 7.4 EWMA min): Te-Hina Paopao (7.4 min EWMA). Other designations: none. Available min-EWMA sum 207.8; long-term absent (report-listed, outside recency roster): Indya Nivar (Out, last rostered 2026-07-11).
- **WAS** — roster 13 (last 3 games through 2026-08-05), OUT 1 (vacated 0.2 EWMA min): Darianna Littlepage-Buggs (0.2 min EWMA). Other designations: none. Available min-EWMA sum 213.6.
  - crew (ATL @ WAS): Kevin Fahy (Crew Chief); Charles Watson (Referee); RJ Johnson (Umpire)
- **GSV** — roster 13 (last 3 games through 2026-08-04), OUT 1 (vacated 4.8 EWMA min): Ashten Prechtel (4.8 min EWMA). Other designations: {'Available': 1}. Available min-EWMA sum 210.6; long-term absent (report-listed, outside recency roster): Miela Sowah (Out, last rostered 2026-07-10).
- **DAL** — roster 14 (last 3 games through 2026-08-05), OUT 2 (vacated 17.9 EWMA min): Haley Jones (12.1 min EWMA), Costanza Verona (5.8 min EWMA). Other designations: {'Questionable': 1}. Available min-EWMA sum 219.3.
  - crew (GSV @ DAL): Randy Richardson (Crew Chief); Marcy Williams (Referee); Jason Alabanza (Umpire)

## Degradations & notes (no-imputation rule: explicit, never silent)

- **BLOCK** [entity-resolution] Indiana Fever: designation 'Out' for 'Ugonne Onyiah' resolves to NO player identity in any season — cold start or unlisted alias. FAIL-CLOSED: the availability estimate for this team is not trustworthy until an alias or a cold-start object is supplied.
- **BLOCK** [entity-resolution] Phoenix Mercury: designation 'Out' for 'Kara Dunn' resolves to NO player identity in any season — cold start or unlisted alias. FAIL-CLOSED: the availability estimate for this team is not trustworthy until an alias or a cold-start object is supplied.
- **BLOCK** [entity-resolution] Los Angeles Sparks: designation 'Out' for 'Tonie Morgan' resolves to NO player identity in any season — cold start or unlisted alias. FAIL-CLOSED: the availability estimate for this team is not trustworthy until an alias or a cold-start object is supplied.
- **BLOCK** [entity-resolution] Indiana Fever: designation 'Out' for 'Michelle Onyiah' resolves to NO player identity in any season — cold start or unlisted alias. FAIL-CLOSED: the availability estimate for this team is not trustworthy until an alias or a cold-start object is supplied.
- **INFO** [player-layer] ATL: Indya Nivar (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-11) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] GSV: Miela Sowah (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-10) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] PHX: Jovana Nogic (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-06-17) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] PHX: Shay Ciezki (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-09) — long-term absentee, already excluded from the availability estimate
- **INFO** [trend-staleness] CON last played 2026-08-02 (5 days before the slate) — trend features are that old (schedule gap, not a data failure: masters are current through yesterday)

## Chain

- OFFICIAL chain verified (forecast_log.jsonl): ok=True, n_records=48, tip_sha256=63c24bdf7918155f56377ef11cb72b282c1cfab56437c7284e4e2f8449503af3 — record these two values out of band; tail truncation is only detectable against an external anchor
