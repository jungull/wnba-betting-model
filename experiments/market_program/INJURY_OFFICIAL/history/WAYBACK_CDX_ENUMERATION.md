# Layer 1 — Wayback CDX API enumeration

**Endpoint used:** `http://web.archive.org/cdx/search/cdx` (documented, free, no key — the Internet
Archive's own indexing API; this is the lawful archive route named by D032, not a scrape of
`wnba.com` itself).

**Politeness:** every request below carried `User-Agent: WNBA-Research-Bot/1.0 (contact:
jgallagher@sasscpas.com; academic research, polite 1rps)` and was spaced ≥1 second from the
previous request (`Start-Sleep -Seconds 1` before each call). No parallel requests were issued.
9 CDX index queries total this session; each is metadata (URL/timestamp/mimetype list), not a
page fetch, and none returned a non-200 status or any sign of rate-limiting.

**Note on tool access:** `WebFetch` returned "unable to fetch from web.archive.org" for this
environment's built-in fetch tool — this is an environment allowlist restriction, not a target-side
block. `Invoke-WebRequest` from PowerShell reached `web.archive.org` cleanly on the first attempt,
so all Wayback work in this session went through that path instead.

## §0. Query log (verbatim, in order)

1. `url=wnba.com/wnba-injury-report&matchType=prefix&from=2022&to=2026&output=json&collapse=urlkey&limit=50`
2. `url=wnba.com&matchType=domain&filter=urlkey:.*injury.*&from=2018&to=2026&output=json&collapse=urlkey&limit=200`
3. `url=mystics.wnba.com&matchType=domain&filter=urlkey:.*injury.*&from=2018&to=2026&output=json&collapse=urlkey&limit=100`
4. `url=liberty.wnba.com/news/category/injury-report&output=json&limit=20`
5. `url=aces.wnba.com/news/category/injury-report&output=json&limit=20`
6. `url=sparks.wnba.com/news/category/injury-report&output=json&limit=20`
7. `url=sky.wnba.com/news/category/injury-report&output=json&limit=20`
8. `url=liberty.wnba.com&matchType=domain&filter=urlkey:.*(injury-report|category.injury).*&from=2018&to=2026&output=json&collapse=urlkey&limit=40` (and same for aces, sparks — all `[]`)
9. `url=liberty.wnba.com&matchType=domain&filter=urlkey:.*injury.*...` / `url=aces.wnba.com...` / `url=sparks.wnba.com...` (broadened filter; see `TEAM_SITE_PROBE.md`)

Plus 3 document-content fetches (2 HTML article pages, 1 PNG banner image) via direct
`https://web.archive.org/web/<timestamp>/<url>` replay — logged in `catalog_sample.csv` /
this session's summary, counted against the ≤200-document cap (3 of 200 used).

## §1. `wnba.com` — the official league site

### `wnba.com/wnba-injury-report` (the human-readable official report page)

**Exactly one capture in the entire CDX index, 2022-2026:** `20260509202958`
(`2026-05-09T20:29:58Z`), status 200, `text/html`, 48,836 bytes. No captures found in 2022, 2023,
2024, or 2025.

### `wnba.com/api/injury-reports` (the backing JSON — discovered incidentally via the domain-wide
injury filter, not something the prior survey had located)

**Exactly one capture:** `20260509203000` (2 seconds after the HTML page above — almost certainly
the same crawl visit fetching both), status 200, `application/json`, 2,740 bytes. This is a live
endpoint worth flagging to whichever node owns live capture design (M03/ladder) — a JSON injury
feed with no key requirement is a materially better live-capture target than scraping the HTML
page — but it has **zero historical depth** in Wayback and cannot contribute to this track's
retrospective mandate.

### Everything else matching `*injury*` on `wnba.com` (domain-wide, ~68 rows after de-noise)

All remaining matches are **news-article slugs that happen to contain the word "injury"**
("elena-delle-donne-injury-update", "diana-taurasi-to-miss-time-due-to-injury", etc.) or
**gameday-preview article titles that mention "injury report" as one of several bullet topics**
("how-to-watch-...-tv-channel-radio-game-time-injury-report-jerseys"). These are `GENERAL_NEWS` /
rank-5 sources at best if pursued, not the official report — noted for completeness, not pursued
further this session, since they require per-article prose parsing with a much lower per-document
information yield than the team-report series found below.

**Verdict on layer 1 against `wnba.com` itself: the primary source has no retrospective archive
depth this program can reach.** This is not a failure of method — the CDX index was queried
correctly and returned real, if sparse, data — it is a fact about what the Internet Archive
happened to crawl. The official report is new enough, or obscure enough, that it was essentially
never crawled before mid-2026.

## §2. `mystics.wnba.com` — the team-site injury report series

Domain-wide `*injury*` filter, 2018-2026, returned **~90 rows** (collapsed to one entry per unique
URL). After removing tracking-pixel/API-noise sub-URLs (the WordPress theme emits
`/API/`, `/gtm.js`, `/privacy.cookies_enabled` etc. as sibling "pages" that Wayback also indexed —
these are not content), the substantive set is:

- **2 standing category/index pages:** `/news/category/injury` (first seen 2024-08-15) and
  `/news/category/injury-report` (first seen 2025-05-02) — these would be the entry point for a
  fuller category-listing crawl (each likely paginates to the full post history; not fetched this
  session, flagged for the runbook).
- **~35 distinct dated "Injury Report" article posts**, spanning three naming conventions the
  team used over time:
  - `mystics-injury-report-<month>-<day>-2022` (May-Aug 2022 — the earliest is
    `mystics-injury-report-may-6-2022`, first Wayback capture `20220510171015`)
  - `injury-report-<month>-<day>-2022` / `-2023` (Jun 2022 - Sep 2023, the bulk of the series,
    roughly biweekly-to-weekly during each season, e.g. 8+ distinct June 2023 dates alone)
  - `injury-update-<month>-<day>-2023` (a handful, mid-2023, same content pattern under a
    different slug)
- **No posts found after `injury-report-september-18-2023`** in this filter/window. This could
  mean the team stopped the series, changed URL convention again (untested), or simply that
  Wayback's crawl coverage of `mystics.wnba.com` thinned after that date — **not distinguished in
  this session**; the runbook flags this as the first thing a fuller pull must resolve.

**Confirms D032's claim exactly:** "Mystics demonstrates 2022-depth feasibility" is not merely
relayed here — it is reproduced independently from the CDX bytes, with the earliest capture dated
2022-05-10 (for a report about the May 6 game) and dense coverage through at least September 2023.

## §3. Document-content sample (2 of the ≤200-document budget)

Two article pages were fetched via Wayback replay and parsed:

1. `mystics-injury-report-may-6-2022` (Wayback capture `20220628213334`) — one player listed:
   Alysha Clark, Right Foot, OUT. Published `2022-05-05T18:11:14-04:00` per the page's own
   `datePublished` meta.
2. `injury-report-aug-12-2022` (Wayback capture `20220828014447`) — one player listed: Myisha
   Hines-Allen, Health and Safety Protocols, OUT. Published `2022-08-11T15:55:42-04:00`.

Both are now `catalog_sample.csv` rows. **Content structure confirmed:** a decorative banner image
(text-free, just says "WASHINGTON MYSTICS INJURY REPORT" — visually confirmed, not OCR'd) followed
by plain prose: one fixed opening sentence naming the opponent/tip-time, then one line per listed
player in the exact format `<Name> – <Reason> – <Designation>`. **This is directly regex-parseable
text**, correcting what would otherwise have been a reasonable assumption (that a team's injury
graphic is an image table requiring OCR) before a parser got built against the wrong assumption.
