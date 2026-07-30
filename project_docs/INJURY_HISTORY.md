# WNBA Injury / Absence / Transaction History (2021 – present)

Recovered 2026-07-30 to give the minutes/availability model training history.
Live capture starts 2026-07-30; this dataset covers the past.

- Script: `scrape_injury_history.py` (repo root)
- Output: `data/injury_history/injury_history.csv` (UTF-8)
- Raw pages: `data/injury_history/raw/` (every HTTP payload; parsing is
  re-runnable offline; `manifest.jsonl` records url/status/time per fetch)

## Sources

Two complementary sources were used:

| # | Source | What it provides | Requests |
|---|--------|-----------------|----------|
| 1 | ESPN game summaries (`site.api.espn.com/.../wnba/summary?event=`) | Per-game **did-not-play entries with reasons** ("RIGHT KNEE INJURY", "COACH'S DECISION", "HEALTH & SAFETY PROTOCOLS") for every completed regular-season + playoff game 2021 → today. This is the per-game injury/absence signal. | 1,495 JSON files, one per game |
| 2 | Basketball-Reference WNBA transaction pages (`/wnba/years/<YYYY>_transactions.html`) | The **league transaction wire**: signings, waivers, waiver claims, trades, drafts, contract suspensions, activations, retirements, front-office moves. | 6 HTML files, one per year |

Season scoreboard JSONs (`espn_scoreboard_<yr>.json`) enumerate the games and
carry each game's Eastern date, teams, season type and Commissioner's Cup
final flag.

### Why not prosportstransactions.com (the original first choice)

prosportstransactions.com has the ideal dedicated archive ("missed games due
to injury/illness" + movement categories), but as of 2026-07-30 the whole
site — including `robots.txt` — sits behind a Cloudflare managed challenge
that returns 403 "Just a moment…" to every scripted client (tested: plain
honest UA, `Mozilla/5.0 (compatible; …)` UA, full Chrome UA string, and
Anthropic's server-side fetcher). Getting past it would require TLS-
fingerprint spoofing / clearance-cookie transplants, i.e. deliberate
bot-detection bypass. **It was not scraped.** If the operator ever drops the
challenge, its "Injuries" category would be a good cross-check source.

### Other alternates evaluated (2026-07-30)

- **RealGM WNBA transactions** — also Cloudflare-403 to scripted clients.
- **Spotrac WNBA** — 403 to scripted clients (incl. robots.txt).
- **ESPN transactions API** (`/wnba/transactions`) — works, but only holds a
  rolling ~6-week window; useless for history, fine for live capture.
- **Wikipedia "List of 20XX WNBA season transactions"** — curated movement
  only, no injury/absence; superseded by Basketball-Reference.
- **Across the Timeline** (acrossthetimeline.com) — has a WNBA transactions
  database (static Next.js app, data embedded in JS chunks) but no
  per-game injury/absence dataset surfaced; not needed.
- **stats.nba.com boxscore `COMMENT` field** — the richest DNP-reason source,
  but off-limits for this task (collection run in progress on that host).
  Worth a backfill pass later; it would give the same rows as source #1 with
  official phrasing.

## Politeness / compliance record

- basketball-reference.com `robots.txt`: `/wnba/` is allowed for `User-agent: *`;
  `Crawl-delay: 3` honored (3.5 s between requests).
- site.api.espn.com serves no robots.txt (plain 403 on the file). Per
  RFC 9309 a 4xx robots response does not forbid crawling. 1.6 s between
  requests, sequential, honest User-Agent
  (`wnba-injury-history-research/1.0 …`).
- Fully resumable: existing files in `raw/` are never re-fetched (the current
  season's scoreboard/transaction page is refreshed when >20 h old).

## CSV schema

`date, team, player_acquired, player_relinquished, notes, category, source_page`

- `date` — US-Eastern game date (ESPN rows) or league transaction date (BBRef rows), ISO `YYYY-MM-DD`.
- `team` — canonical stats.nba.com-style abbreviation (see team-mapping notes below).
- `player_acquired` — player arriving / returning (signings, claims, trade-in, draft, activation, contract conversion).
- `player_relinquished` — player out / leaving (missed game, waiver, trade-out, contract suspension, retirement).
- `notes` — raw reason / original sentence; `[playoffs]` and
  `[commissioners-cup-final]` tags mark games outside the RS gamelog files.
- `category` — see table.
- `source_page` — file in `data/injury_history/raw/` the row was parsed from.

| category | source | meaning |
|----------|--------|---------|
| `missed_game_injury` | ESPN | rostered player did not play; reason looks medical (injury/illness/body part/protocols) |
| `missed_game_other` | ESPN | did not play; non-medical reason (COACH'S DECISION, REST, PERSONAL, OVERSEAS, NOT WITH TEAM, …) |
| `missed_game_unspecified` | ESPN | did not play; no reason string |
| `signing` | BBRef | signed (training-camp / rest-of-season / 7-day / hardship contracts) |
| `waiver` | BBRef | waived / released |
| `waiver_claim` | BBRef | claimed off waivers (acquisition) |
| `trade` | BBRef | player moved between teams (draft-pick-only annotations excluded) |
| `draft` | BBRef | drafted (incl. expansion drafts) |
| `contract_suspension` | BBRef | team suspended the player's contract (overseas commitment, personal, pregnancy, full-season absence, …) |
| `activation` | BBRef | activated / suspension lifted |
| `contract_conversion` | BBRef | development → standard contract (2026 CBA) |
| `retirement` | BBRef | retired |
| `front_office` | BBRef | coach/GM moves (no player fields) |
| `other` | BBRef | unclassified sentence (kept verbatim in notes) |

## Coverage

Parsed 2026-07-30 from 1,507 raw files (1,495 game summaries + 6 season
scoreboards + 6 transaction pages). **8,340 rows total**; every ESPN DNP row
carries a reason string (zero `missed_game_unspecified`). Games covered:
2021: 210 (193 RS incl. Cup final + 17 playoff), 2022: 240, 2023: 261,
2024: 263, 2025: 311, 2026: 210 (season in progress). ~3.6 DNP rows/game.

| season | total | missed_game_injury | missed_game_other | transaction wire (BBRef) |
|--------|------:|-------------------:|------------------:|-------------------------:|
| 2021 | 1,151 | 321 | 370 | 460 |
| 2022 | 1,261 | 293 | 455 | 513 |
| 2023 | 1,299 | 398 | 454 | 447 |
| 2024 | 1,383 | 340 | 631 | 412 |
| 2025 | 1,785 | 528 | 693 | 564 |
| 2026 (thru 07-30) | 1,461 | 362 | 528 | 571 |

Wire detail (all seasons): signing 1,455 · waiver 795 · trade 252 ·
draft 260 · contract_suspension 111 · waiver_claim 18 · retirement 21 ·
front_office 49 · contract_conversion 6.

## Validation (2026-07-30)

**Date→GAME_ID alignment method** (needed because player gamelogs have no
date column): per-team ordinal alignment of ESPN regular-season dates vs
sorted GAME_IDs scored **480/480 exact** against
`wnba_team_gamelog_2024.parquet` `GAME_DATE` ground truth.

**Sampled `missed_game_injury` cross-check — 10/10 hits.** Ten rows sampled
(seed 42, 2/season 2021–2025); in every case the named player has *no
boxscore row* in her team's game on the event date, while matching (by
normalized name) real rows elsewhere in the season — ruling out
name-mismatch false positives:

| date | team | player | reason | season apps | corroboration |
|------|------|--------|--------|------------:|---------------|
| 2021-05-30 | CHI | Allie Quigley | HAMSTRING | 26 | back 06-03 |
| 2021-05-16 | PHO | Bria Hartley | RIGHT KNEE INJURY | 6 | knee injury ended season |
| 2022-06-28 | DAL | Satou Sabally | KNEE INJURY | 11 | back 07-01 |
| 2022-06-19 | NYL | Betnijah Laney-Hamilton | RIGHT KNEE INJURY | 9 | June knee surgery |
| 2023-06-29 | PHO | Shey Peddy | ACHILLES | 18 | played 06-18, back 07-01 |
| 2023-06-15 | ATL | Danielle Robinson | LEFT KNEE | 32 | back 06-18 |
| 2024-06-04 | SEA | Nneka Ogwumike | EYE INJURY | 37 | played 05-30, back 06-07 |
| 2024-09-13 | CHI | Diamond DeShields | ANKLE INJURY | 32 | last app 09-08 |
| 2025-05-22 | CHI | Moriah Jefferson | LEG INJURY | 2 | 2 apps before injury |
| 2025-06-21 | PHO | Megan McConnell | RIGHT KNEE INJURY | 1 | 1 app before injury |

**`contract_suspension` spot-checks — 5/5 consistent** (player has zero
gamelog appearances for that team after the suspension date, no intervening
activation): Skylar Diggins-Smith PHO 2022-08-10, Julie Allemand IND
2021-04-28 & 2021-05-13, Bernadett Hatar IND 2023-05-18, Cecilia
Zandalasini GSV 2025-06-08.

Caveats: 2025 checks are limited to the partial local gamelog (league games
1–108); 2026 rows cannot be cross-checked locally yet (no 2026 parquet);
playoff/Cup-final rows are excluded from checks (RS-only gamelogs).

## How this joins to the gamelogs

The player gamelog parquets (`data/wnba_gamelog_<yr>.parquet`) contain only
players who appeared (no DNP rows, `COMMENT` empty, no `GAME_DATE` column),
so joining needs two bridges:

1. **Game-date → GAME_ID.** Regular-season GAME_IDs (`102<yy>xxxxx`) are
   assigned in schedule order, so for each (season, team) the sorted list of
   ESPN regular-season dates (Commissioner's Cup final excluded) zips 1:1
   onto the team's sorted GAME_IDs. This alignment was verified against
   `wnba_team_gamelog_2024.parquet` (`GAME_DATE`): **480/480 exact**. The
   scoreboard JSONs in `raw/` provide the dates; convert ESPN's UTC
   timestamps to US-Eastern first (the scraper's `eastern_date()` does this —
   late tipoffs otherwise land on the next calendar day).
2. **Name key.** Join on accent-folded, lower-cased, alpha-only names
   (NFKD → ASCII, strip non-letters): handles Juhász/Juhasz, Koné/Kone,
   Johannès/Johannes. Residual hazards: name changes across seasons
   (e.g. Betnijah Laney → Laney-Hamilton), Jr./suffix variants, and
   provider-specific spellings — treat unmatched names as suspect rather
   than assuming absence.

Team-abbreviation mapping (CSV is canonical-stats style):

- ESPN → canonical: `NY→NYL, LV→LVA, LA→LAS, PHX→PHO, WSH→WAS, CONN→CON, GS→GSV`
  (identity: ATL CHI CON DAL IND MIN SEA; 2026 expansion: TOR, POR).
- **stats.nba.com renamed Phoenix `PHO`→`PHX` starting 2025**; the CSV uses
  `PHO` for all seasons — map `PHX→PHO` when joining 2025+ gamelogs.

Movement rows apply from `date` forward: a `contract_suspension` holds until
the next `activation`/`signing` row for the same player+team; a `waiver`
ends that player's team association until a new `signing`/`waiver_claim`.

## Known limitations

- **Granularity vs the modern injury-report taxonomy.** ESPN rows are
  *game-day final* absences with a reason — there is no historical
  Out/Questionable/Doubtful/Probable pregame signal here, and no
  "played hurt" designations. The live capture starting 2026-07-30 should
  collect the official injury report to get prospective statuses going
  forward.
- **Roster scope.** A player only appears as a DNP if she was on the game-day
  roster: season-long absences (suspended contracts, pregnancy, overseas)
  never show up as `missed_game_*` rows — they are visible instead as
  `contract_suspension` (+ missing gamelog rows). The two sources are
  complementary; use both.
- **Reason noise.** `COACH'S DECISION` sometimes masks minor injuries or
  planned rest; `HEALTH & SAFETY PROTOCOLS` (COVID era) is bucketed as
  injury/illness; a small share of DNPs have no reason
  (`missed_game_unspecified`). The injury/other split is a keyword heuristic
  over free text — the raw string is always preserved in `notes`.
- **Event-date semantics.** For ESPN rows, `date` is the game missed (the
  first missed game usually lags the actual injury, which typically happened
  in the *previous* game). BBRef dates are league-office announcement dates,
  which can trail the real-world event.
- **Playoffs / Cup final.** Absences there are tagged in `notes`; the local
  gamelog parquets are regular-season only, so those rows have no local
  join target (kept because they are real availability history).
- **Trades.** Multi-team (3+) trades record only the actor team's side;
  pick-only trades yield rows with empty player fields (full sentence in
  `notes`). "(X later selected)" draft-pick annotations are excluded from
  trade player extraction on purpose.
- **2025 local gamelog is partial** (league games 1–108; Phoenix missing due
  to the PHX rename) — that limits local cross-checks, not the scraped data.
- **Preseason excluded** (no gamelogs, rosters unsettled). All-Star and
  USA-vs-All-Stars exhibitions excluded.
- **No 2026 cross-check yet** — no local 2026 gamelog parquet exists to
  validate against; validation below covers 2021–2025.

## Refresh

`python scrape_injury_history.py` re-fetches only what is missing (plus the
current season's scoreboard/transaction page when stale), then re-parses
everything from `raw/`. `--parse-only` rebuilds the CSV fully offline.
