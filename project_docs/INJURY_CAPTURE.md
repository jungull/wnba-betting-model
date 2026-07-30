# WNBA Injury/Availability Capture

`injury_capture_daily.py` (repo root) snapshots the league injury report twice
daily (same Task Scheduler cadence as `odds_capture_daily.py`: noon + 6:30pm
local works well — the 6:30pm run catches the near-final designations for that
night's games). First live captures: 2026-07-30.

## Primary source: official WNBA injury report (PDF)

- Landing page: <https://www.wnba.com/wnba-injury-report>
- Actual data:  `https://ak-static.cms.nba.com/referee/wnba_injury/Injury-Report_{YYYY-MM-DD}_{HH_MM}{AM|PM}.pdf`
  (US/Eastern timestamps, e.g. `Injury-Report_2026-07-30_11_45AM.pdf`)

Why this one: it is the league's own report, so it is the only source with
true per-game designations (**Out / Doubtful / Questionable / Probable /
Available**), the game date, matchup, and the team-submitted reason string
(`Injury/Illness - Right Knee; Right Knee`, `Concussion Protocol`,
`Personal Reasons`, ...). Every betting-relevant availability decision keys
off these designations, so designation fidelity beat format convenience.

Notes from source research (2026-07-30):

- The wnba.com landing page is a Next.js app; the injury table is rendered
  client-side, so the HTML contains **no data**. Its `/api/injury-reports`
  route just enumerates candidate PDF links for the day in 15-minute slots —
  the PDFs on the Akamai CDN are the real payload. There is no JSON feed of
  the parsed report.
- PDFs publish roughly **hourly, around :00 +7s ET**, with occasional
  off-hour extras (an 11:45 AM report existed on 2026-07-30). Each report
  covers today's and (from mid-day on) tomorrow's games; teams that have not
  filed yet show `NOT YET SUBMITTED`.
- The CDN host `ak-static.cms.nba.com` is a static Akamai property — it is
  **not** stats.nba.com, so capture runs cannot interfere with (or be rate
  limited alongside) stats.nba.com collection jobs.
- The script finds the newest report by walking back from "now" (ET) in
  15-minute steps (HEAD requests, max 48h) until a PDF exists. No scraping of
  the landing page is involved.

### PDF parsing approach (and format-change risks)

The PDF is text-based (same generator as the NBA injury report, in use since
2023). `pypdf` extracts words with x/y coordinates; the parser:

1. clusters words into rows by y (2pt tolerance),
2. reads the column x-positions off the per-page header row
   (`Game Date | Game Time | Matchup | Team | Player Name | Current Status | Reason`),
3. derives reading order per page (the generator emits text bottom-up, so
   order is verified by requiring the header row to precede data rows),
4. carries game date/time/matchup/team forward through blank cells, including
   across page breaks (continuation pages have no header but keep the same
   column x-positions), and
5. flips `Last, First` to `First Last` and normalizes team names.

Known risks, in rough likelihood order:

- **Column set changes** (e.g. a new column): the parser hard-fails with
  `injury PDF header changed`, which routes the run to the fallback. Fix by
  updating `_column_starts()`.
- **Report becomes image-based or moves hosts**: primary would fail, fallback
  keeps the log alive; re-point `PDF_BASE`.
- **New status word** (e.g. mid-season rule change): row is still captured,
  with a stderr warning.
- **Expansion/rename**: unknown team names are kept raw (never dropped) with
  a stderr warning; add to `CANON_TEAMS`/aliases.

Because the raw PDF of every capture is kept (see below), any parser bug or
format change can be re-parsed retroactively — never lose a day.

## Fallback source: ESPN injuries API (JSON)

- `https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/injuries`

Plain JSON, no key, no JS, updates continuously, and exists in the off-season.
Caveats: it is a **running injury list**, not a per-game report — statuses are
coarser (`Out` / `Day-To-Day`), there is no `game_date`, and the reason is
reconstructed from `details` (side/type/detail, e.g. `Left Foot (Surgery)`)
or the news `shortComment`. Team names arrive as full names already.

Fallback triggers when the primary (a) throws — network failure, no PDF found
within 48h, parse error — or (b) parses to **zero player rows** (e.g. every
team `NOT YET SUBMITTED`; also the off-season case, where no PDF is published
at all and ESPN still answers). The `source` column records which parser
produced each row: `wnba_official` or `espn`. Exit code is nonzero only when
**both** sources fail; a structurally valid but empty report is success.

Sources evaluated and rejected (2026-07-30): ESPN's HTML injuries *page*
returns HTTP 202 with an empty body to non-browser clients (bot detection);
Rotowire `wnba/injury-report.php` and CBS Sports `wnba/injuries/` both ship
zero table rows in the raw HTML (tables are JS-rendered). None are parseable
from raw HTTP, which was a hard requirement.

## Outputs

Raw payload is **always saved before parsing**:

```
data/injury_capture/raw/wnba_official_<UTCstamp>.pdf
data/injury_capture/raw/espn_<UTCstamp>.json          (only when ESPN is hit)
```

Normalized rows append to `data/injury_capture/injury_log.csv` (UTF-8, header
auto-created, one row per player-designation):

| column      | example                                   | notes                                        |
|-------------|-------------------------------------------|----------------------------------------------|
| capture_utc | `20260730T154950Z`                        | run stamp; matches raw filename               |
| report_date | `2026-07-30`                              | date in the PDF title / ESPN feed timestamp   |
| game_date   | `2026-07-30`                              | official source only; empty for espn          |
| team        | `Las Vegas Aces`                          | normalized to the 15 canonical full names     |
| player      | `Cheyenne Parker-Tyus`                    | `First Last`                                  |
| status      | `Questionable`                            | official: Out/Doubtful/Questionable/Probable/Available; espn: Out/Day-To-Day |
| reason      | `Injury/Illness - Right Leg; R. Leg`      | team-submitted string (official) / details (espn) |
| source      | `wnba_official`                           | or `espn`                                     |

The log is **append-only snapshots**: every run appends the full current
report, so the same player appears once per capture (and once per listed game
— the report covers today *and* tomorrow). Dedupe downstream on
`(report_date, game_date, team, player)` taking the latest `capture_utc`,
which also gives you designation *progression* (Questionable at noon → Out at
6:30pm) for free. A run that fails writes nothing (no partial appends).

Rows with `NOT YET SUBMITTED` team-slots are not emitted as player rows; the
count is printed in the run summary and the raw PDF retains them.

## Operational notes

- Dependencies: `requests`, `pypdf` (`pip install --user pypdf`). No pandas
  required at capture time; stdlib `csv` keeps the append atomic and simple.
- Scheduling: mirror the `WNBA_OddsCapture` task; working directory does not
  matter (paths are derived from the script location).
- Manual override for testing/debugging: `--force-source official` or
  `--force-source espn`.
- Off-season behavior: no PDFs are published → primary reports "no official
  PDF found in last 48h" → ESPN fallback captures (possibly zero rows) and
  the run still exits 0. The task can run year-round unattended.
