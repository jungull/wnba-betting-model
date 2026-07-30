# WNBA Referee Assignments Capture

`ref_assignments_capture_daily.py` (repo root) snapshots the league's daily
referee assignments. This is W4's **point-in-time** feed: an assignment is
only usable by a forecast if it was public before that forecast's cutoff, so
the capture timestamp (`capture_utc`) IS the feature timestamp. First live
captures: 2026-07-30 (3-game slate MIN@TOR / CON@CHI / NYL@LVA, all three
crews verified name-for-name against the page).

## Primary source: officiating site JSON endpoint

```
https://official.nba.com/wp-json/api/v1/get-game-officials?date=YYYY-MM-DD
```

This is the endpoint behind the date picker on the NBA officiating group's
assignments page (found via `constants.restURL` + the theme's
`nba-official.min.js`, which calls `api/v1/get-game-officials`). One call
returns all three leagues — `{nba, gl, wnba} -> Table.rows[]` — and each row
carries, verbatim from the league:

- `game_id` (e.g. `1022600210`) — the league's standard 10-digit WNBA game
  id, same convention as `data/officials/officials_<gid>.parquet` from the
  historical W4 crawl, so the live feed **joins directly to the historical
  officials data on `game_id`**. Recorded as-is, never fabricated.
- `game_code` (`20260730/MINTOR`), team ids/names/tricodes,
- `official1..official4` with `official*_JNum` (jersey number) and
  `official*_code` (league person id — kept in the raw archive; useful for
  identity joins across seasons when names collide or change).

The site's own server-rendered table labels `official1..4` as **Crew Chief /
Referee / Umpire / Alternate** in that order; we record those labels in
`crew_role`. `official4` (Alternate) was null for all games on 2026-07-30 —
WNBA regular-season crews are 3 officials, alternate usually unassigned.

**Date-format quirk (important):** the endpoint answers HTTP 200 for several
date formats, but only `YYYY-MM-DD` returned rows in testing. The site's own
datepicker submits `July 30, 2026` — that format returned an *empty* result
set. If the server's date parsing ever changes, the failure mode is a valid
but empty response, which the script treats as "no assignments found" and
reports loudly (never a silent success), then tries the HTML fallback.

`official.nba.com` is a WordPress property on an Akamai CDN — it is **not**
stats.nba.com, so captures cannot interfere with stats.nba.com crawls. No
key, no JS, no bot wall observed with a plain browser UA.

## Fallback source: the server-rendered page

- <https://official.nba.com/referee-assignments/>

Today's assignments are **server-rendered plain HTML** (verified 2026-07-30:
raw fetch contains the full WNBA table, no JS needed). Structure per league:
an `entry-title` (`WNBA Referee Assignments`), an `entry-meta` date
(`July 30, 2026`), and a `<div class="wnba-refs-content">` table with header
`Game | Crew Chief | Referee | Umpire | Alternate` and rows like
`Minnesota @ Toronto | Maj Forsberg (#34) | ...`. The stdlib-`HTMLParser`
fallback reads the role labels straight from the table header (so a league
relabeling shows up immediately) and cross-checks the page's own date.
Limitations vs JSON: **today-only** (the date picker routes through the JSON
endpoint; there is no HTML for other dates) and **no `game_id`** (left blank
in the log — never fabricated).

Leagues with no slate that day simply have no section (G League was absent
on 2026-07-30; NBA section present but zero rows — offseason).

## Sources evaluated and rejected (2026-07-30)

- **wnba.com has no first-party assignments page**: `/referee-assignments`,
  `/officials`, `/official/referee-assignments`, `/news/referee-assignments`
  all 404. Search results confirm third-party trackers (refmetrics.com,
  covers.com, phillyref.com) are the only alternatives, and they are
  derivative of official.nba.com — not acceptable as a fallback of record.

## Posting cadence and point-in-time behavior (observed + stated)

- The page states: assignments are posted **~9:00am ET each game day**.
- Verified 2026-07-30 ~1pm ET: today's 3 games fully posted; querying
  **2026-07-31 returned zero rows** even though games are scheduled — i.e.
  the feed exposes nothing ahead of the posting day. No lookahead exists at
  the source, which is exactly the property W4 needs; the daily capture
  preserves it.
- The JSON endpoint does serve **past** dates (2026-07-29 → 2 games;
  2025-09-10 → 1 game), so a coarse backfill is possible — but a past-date
  pull reflects the source's *current* state, not what was public before any
  historical cutoff. Backfilled rows must never be treated as point-in-time.
  (`--date YYYY-MM-DD` exists for exactly this, JSON source only.)
- Officials do get scratched/substituted after the morning post; re-runs
  append fresh snapshots, so an afternoon run captures crew changes as a new
  `capture_utc` (progression visible downstream, same as the injury log).

## Outputs

Raw response is **always saved before parsing** (every run, even ones that
parse to zero rows):

```
data/ref_assignments/raw/official_nba_json_<UTCstamp>.json
data/ref_assignments/raw/official_nba_html_<UTCstamp>.html   (fallback runs)
```

Normalized rows append to `data/ref_assignments/assignments_log.csv`
(UTF-8, header auto-created, one row per game-official):

| column        | example            | notes                                        |
|---------------|--------------------|----------------------------------------------|
| capture_utc   | `20260730T170806Z` | run stamp; matches raw filename; **the feature timestamp** |
| game_date     | `2026-07-30`       | from the source row (JSON) / page date (HTML) |
| game_id       | `1022600210`       | source's own id; blank for HTML rows          |
| away_team     | `Minnesota Lynx`   | normalized to the 15 canonical full names     |
| home_team     | `Toronto Tempo`    | normalized to the 15 canonical full names     |
| official_name | `Maj Forsberg`     | as published                                  |
| official_num  | `34`               | jersey number, disambiguates similar names    |
| crew_role     | `Crew Chief`       | Crew Chief / Referee / Umpire / Alternate, as the source labels them |
| source        | `official_nba_json`| or `official_nba_html`                        |

The log is **append-only snapshots**: every run appends the full current
slate. Dedupe downstream on `(capture date, game, official)` taking the
latest `capture_utc` — verified live: 3 snapshots (27 rows) collapse to
exactly 9 game-official rows. A failed run appends nothing.

## Format-change risks (rough likelihood order)

- **Server date parsing changes** → valid-but-empty JSON. Caught: empty
  results are reported per-source with full diagnostics and the HTML
  fallback is tried; a game-day empty run is your alarm.
- **Endpoint path/shape changes** (WordPress theme update): primary throws
  or parses empty → HTML fallback keeps the log alive; re-derive the
  endpoint from `constants.restURL` in the page source + the theme JS.
- **Crew structure/labels change** (e.g. 4-official crews): JSON mapping
  assumes official1..4 = Crew Chief/Referee/Umpire/Alternate. The HTML
  parser reads labels from the header, so run `--force-source html` once to
  see the source's current labeling; update `ROLE_LABELS` if it drifts.
- **Table header changes** (HTML): parser hard-fails with
  `assignments table header changed` rather than mis-bucketing roles.
- **Expansion/rename**: unknown team names are kept raw (never dropped)
  with a stderr warning; extend `CANON_TEAMS`/aliases.

Raw archives make every capture re-parseable retroactively — never lose a
day to a parser bug.

## Recommended capture schedule

Assignments post once daily ~9:00am ET; officials occasionally change later
in the day. Two runs, mirroring the existing capture tasks:

1. **10:00am ET** — primary capture, ~1h after the posting window, so the
   crew feature is available well before any forecast cutoff or line move.
2. **6:30pm ET** — revision/scratch sweep near first tip, piggybacking on
   the existing `WNBA_OddsCapture`/injury 6:30pm task slot; a changed crew
   shows up as a fresh snapshot.

Each run is two cheap HTTP calls at most; if W4 later wants finer revision
granularity, an additional ~4:00pm ET run (or hourly 9am–7pm ET) is safe.
Runs before ~9am ET or on off-days exit 0 with an explicit "no assignments
posted" diagnostic, so the task can run year-round unattended (off-season:
JSON `wnba` comes back empty/null, HTML section disappears — both handled).

## Operational notes

- Dependencies: `requests` only (stdlib `csv`/`html.parser` otherwise).
- Scheduling: mirror the `WNBA_OddsCapture` task; working directory does
  not matter (paths derive from the script location). Game "day" is
  US/Eastern (zoneinfo with a manual DST fallback, same as injury capture).
- Manual overrides: `--force-source json|html` (test one path),
  `--date YYYY-MM-DD` (historical pull via JSON; **not** point-in-time).
- Do NOT join tonight's crews to forecasts via anything but `capture_utc`
  gating: use rows whose `capture_utc` precedes the forecast cutoff.
