# Daily forecast — DRY RUN (scratch chain; NOT the regime-D log)

*Generated 2026-08-07T01:15:15.688043+00:00 by `daily_forecast.py` (v0). Slate date 2026-08-06 (ET); forecast cutoff 2026-08-07T01:15:14.053464+00:00. Model hash `b0eee0392e745559…`; data snapshot hash `14431fce62dd07b4…`; code `git:55d84f1edd11`. Team model: promoted structural channels (chanreval_2026_structural_repaired/run1); player layer informational only — it does not modify the team forecast.*

**This file is engineering output. The records behind it were written ONLY to `experiments/forecast_dryrun/scratch_chain.jsonl`. The official regime-D clock starts with the first record of `forecasts/forecast_log.jsonl`, which this job refuses to touch.**

## Slate — model vs market

| Game (away @ home) | Tip (ET) | Label | Model H | Model A | Model margin (H−A) | Market home spread | Model total | Market total | Edge vs spread | Edge vs total |
|---|---|---|---|---|---|---|---|---|---|---|
| LVA @ IND | 2026-08-06 19:06 | T-30m | — | — | — | +1.5 | — | 152.5 | — | — | (no forecast: tip already passed at the cutoff — a post-tip 'forecast' violates the prediction contract) |
| LAS @ MIN | 2026-08-06 21:05 | T-30m | — | — | — | -16.5 | — | 187.5 | — | — | (no forecast: tip already passed at the cutoff — a post-tip 'forecast' violates the prediction contract) |
| TOR @ PDX | 2026-08-06 22:00 | T-30m | 91.6 | 86.2 | +5.4 | -2.5 (11 bks) | 177.8 | 187.5 | +2.9 | -9.7 |

*Market home spread is quoted book-style (negative = home favored); market-implied margin = −spread. Edge vs spread = model margin − market-implied margin. Both edges are informational — no betting layer ran (`not_applicable`, stake 0).*

## Player layer (informational — does not modify the team forecast)

- **LVA** — roster 13 (last 3 games through 2026-08-03), OUT 1 (vacated 10.0 EWMA min): Cheyenne Parker-Tyus (10.0 min EWMA). Other designations: {'Available': 3}. Available min-EWMA sum 216.7; long-term absent (report-listed, outside recency roster): Janiah Barker (Out, last rostered 2026-07-09).
- **IND** — roster 12 (last 3 games through 2026-08-02), OUT 3 (vacated 7.8 EWMA min): Damiris Dantas (7.8 min EWMA), Ugonne Onyiah (no played games), Michelle Onyiah (no played games). Other designations: {'Available': 3}. Available min-EWMA sum 208.8; long-term absent (report-listed, outside recency roster): Bree Hall (Out, last rostered 2026-07-09); UNMATCHED report rows: ['Ugonne Onyiah (Out)', 'Michelle Onyiah (Out)'].
  - crew (LVA @ IND): Roy Gulbeyan (Crew Chief); Toni Patillo (Referee); RJ Johnson (Umpire)
- **LAS** — roster 12 (last 3 games through 2026-08-05), OUT 1 (vacated 0.0 EWMA min): Tonie Morgan (no played games). Other designations: {'Available': 1}. Available min-EWMA sum 227.4; long-term absent (report-listed, outside recency roster): Alissa Pili (Out, last rostered 2026-07-13); UNMATCHED report rows: ['Tonie Morgan (Out)'].
- **MIN** — roster 13 (last 3 games through 2026-08-02), OUT 2 (vacated 29.1 EWMA min): Chloe Bibby (12.8 min EWMA), Emma Cechova (16.3 min EWMA). Other designations: {'Available': 1}. Available min-EWMA sum 215.9; long-term absent (report-listed, outside recency roster): Liatu King (Out, last rostered 2026-07-15).
  - crew (LAS @ MIN): Randy Richardson (Crew Chief); Teresa Stuck (Referee); Genesis Perrymond (Umpire)
- **TOR** — roster 13 (last 3 games through 2026-08-04), OUT 2 (vacated 46.6 EWMA min): Isabelle Harrison (17.2 min EWMA), Brittney Sykes (29.4 min EWMA). Other designations: {'Available': 3}. Available min-EWMA sum 236.8; long-term absent (report-listed, outside recency roster): Ornella Bankole (Out, last rostered 2026-07-28).
- **PDX** — roster 12 (last 3 games through 2026-08-02), OUT 2 (vacated 32.8 EWMA min): Sarah Ashlee Barker (20.7 min EWMA), Teja Oblak (12.1 min EWMA). Other designations: {'Available': 1}. Available min-EWMA sum 194.8; long-term absent (report-listed, outside recency roster): Jordan Harrison (Out, last rostered 2026-07-18); Sania Feagin (Out, last rostered 2026-07-16).
  - crew (TOR @ PDX): Clare Simmons (Crew Chief); Agon Abazi (Referee); Sarah Williams (Umpire)

## Degradations & notes (no-imputation rule: explicit, never silent)

- **BLOCK** [entity-resolution] Indiana Fever: designation 'Out' for 'Ugonne Onyiah' resolves to NO player identity in any season — cold start or unlisted alias. FAIL-CLOSED: the availability estimate for this team is not trustworthy until an alias or a cold-start object is supplied.
- **BLOCK** [entity-resolution] Phoenix Mercury: designation 'Out' for 'Kara Dunn' resolves to NO player identity in any season — cold start or unlisted alias. FAIL-CLOSED: the availability estimate for this team is not trustworthy until an alias or a cold-start object is supplied.
- **BLOCK** [entity-resolution] Los Angeles Sparks: designation 'Out' for 'Tonie Morgan' resolves to NO player identity in any season — cold start or unlisted alias. FAIL-CLOSED: the availability estimate for this team is not trustworthy until an alias or a cold-start object is supplied.
- **BLOCK** [entity-resolution] Indiana Fever: designation 'Out' for 'Michelle Onyiah' resolves to NO player identity in any season — cold start or unlisted alias. FAIL-CLOSED: the availability estimate for this team is not trustworthy until an alias or a cold-start object is supplied.
- **INFO** [player-layer] IND: Bree Hall (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-09) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] LAS: Alissa Pili (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-13) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] LVA: Janiah Barker (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-09) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] MIN: Liatu King (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-15) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] PDX: Jordan Harrison (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-18) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] PDX: Sania Feagin (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-16) — long-term absentee, already excluded from the availability estimate
- **INFO** [player-layer] TOR: Ornella Bankole (Out) is on the injury report but outside the 3-game recency roster (last rostered 2026-07-28) — long-term absentee, already excluded from the availability estimate
- **WARN** [forecast] LVA @ IND: tip already passed at the cutoff — a post-tip 'forecast' violates the prediction contract
- **WARN** [forecast] LAS @ MIN: tip already passed at the cutoff — a post-tip 'forecast' violates the prediction contract
- **INFO** [chain] LVA @ IND: obligation (game 1022600230, T-30m, this model version) already served — refused by the obligation guard (D-c: dedup no longer keys on the wall-clock cutoff); a second serving is the same decision re-timestamped, not a new prediction
- **INFO** [chain] LAS @ MIN: logged as NO_FORECAST (tip already passed at the cutoff — a post-tip 'forecast' violates the prediction contract)
- **WARN** [chain] LAS @ MIN: chain write failed (ForecastValidationError: market_source is required when any market field is recorded — a market line whose provenance cannot be established is not a benchmark (prediction-contract provenance rule).) — game isolated; remaining slate continues (D-c per-game execution scope)

## Chain

- OFFICIAL chain verified (forecast_log.jsonl): ok=True, n_records=45, tip_sha256=2d2f5e2e5dae005ce70e3bb701088de2c1c06ce8892c65fed123169168f3fcbc — record these two values out of band; tail truncation is only detectable against an external anchor
