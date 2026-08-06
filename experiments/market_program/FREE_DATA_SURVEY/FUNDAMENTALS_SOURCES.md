# FUNDAMENTALS_SOURCES — free basketball-fundamentals data for player-value translation and injury studies

**Lane:** market_intelligence · **Node type:** D028 free-data survey (basketball-fundamentals lens)
**Write scope used:** `experiments/market_program/FREE_DATA_SURVEY/FUNDAMENTALS_SOURCES.md` (this file only)

**Epistemic status:** SURVEY. This document catalogs candidate free data sources and, for the subset
that clears all four D028 graduation gates, a capture design + starter script. It admits no data
source into any predictive path and decides no signal's fate. It is not evidence and confers no
label under `MARKET_PROGRAM_CONTRACT.md` §3.

**Contract binding:** `MARKET_PROGRAM_CONTRACT.md` sha256 measured this session —

```
Get-FileHash -Algorithm SHA256 MARKET_PROGRAM_CONTRACT.md
1152DCD3BF74000F700844BC8BFC0DF25DE61A067F59534A714AC4F2F20265DE
```

— matches the task-supplied hash `1152dcd3...265de` exactly (case-insensitive), and matches the
value independently reported by M01, M02, M04, M05, M11, and M25. Verified before any source
was classified.

**D028 graduation gates (repeated from the mandate, applied per source below):**
1. Zero cost.
2. Lawful access — documented public API or explicitly permitted feed. No ToS-violating scraping,
   no fuzzy legality. RED-flag sources stay parked at survey stage.
3. Genuinely useful to a named downstream node: M04 (competitor projection archive), M06 (injury
   studies), M13 (player-value translation), or information-event capture generally.
4. A concrete plan: endpoints, cadence, quota limits, schema mapping, amendment-4 timestamp fields
   (`vendor_ts`, `vendor_ts_semantics`, `retrieval_ts`, `ingestion_ts`, etc., per §6.3) on anything
   that could feed a timing claim.

A source that fails any gate is recorded and parked, not silently dropped.

---

## 1. The public WNBA stats API surface already used by this repo

### 1.1 What the existing fetchers actually call (read from script headers, not assumed)

| Script | Import | Endpoint class | Confirmed live in repo |
|---|---|---|---|
| `scripts/01_acquisition/fetch_wnba_team_gamelog.py` | `nba_api.stats.endpoints.leaguegamelog` | `LeagueGameLog(league_id="10", season=..., season_type_all_star="Regular Season", player_or_team_abbreviation="T")` | Yes — team-level season log |
| `scripts/01_acquisition/fetch_wnba_boxscores.py` | `nba_api.stats.endpoints.leaguegamelog`, `boxscoretraditionalv2`, `boxscoremiscv2` | `LeagueGameLog` (player_or_team default → games list per season), `BoxScoreTraditionalV2(game_id=...)`, `BoxScoreMiscV2(game_id=...)`, merged on `GAME_ID`/`PLAYER_ID` | Yes — per-player traditional + misc box score |
| `scripts/01_acquisition/fetch_wnba_playbyplay.py` | `nba_api.stats.endpoints.playbyplayv2` | `PlayByPlayV2(game_id=...)`, driven by GAME_IDs harvested from the season gamelog parquet files already on disk | Yes — full play-by-play event stream |
| `scripts/01_acquisition/inspect_boxscoresummaryv2.py` | `nba_api.stats.endpoints.boxscoresummaryv2` | `BoxScoreSummaryV2(game_id=...)`, inspecting `resultSets` incl. arena/city fields | Yes — used as an inspection script, not yet a production fetcher |

All four hit the same underlying surface: `stats.wnba.com`/`stats.nba.com`'s JSON stats API, called
through the `nba_api` Python wrapper (`league_id="10"` selects WNBA). **Legal characterization,
stated honestly:** this is not a documented, contractually-offered public API — it is an
undocumented internal endpoint that the league's own stats site calls from the browser, with no
published ToS granting third-party programmatic use, and no API key or registration gate. `nba_api`
is a well-established, widely-used open-source wrapper (MIT-licensed) that has operated against this
surface for years, and this repo is already built on it for the possession/player lanes. Per D028's
"no fuzzy legality" instruction, this is recorded honestly as **UNDOCUMENTED-BUT-ESTABLISHED**, not
"documented public API" — it does not fully clear gate 2's "documented public API" phrasing, but it
is materially different from ToS-violating scraping of a rendered page: it is a JSON endpoint with no
robots.txt disallow, no login wall, and no rate-limit-evasion behavior required, already load-bearing
elsewhere in this repo's own possession lane. **Recommendation:** treat as the repo's existing
practice/precedent tier — continued use for the same purpose (fundamentals) is consistent with what
the possession lane already does, but any *new* endpoint on this surface should be verified live
before being wired into a schedule (see §1.3), and this survey does not certify the surface's legal
status beyond what the existing codebase has already assumed. If M00's stop-condition machinery
("accepting scraping or licensing risk") is read strictly, extending this surface to *new* endpoint
families is a judgment call this survey flags rather than resolves — see §5 HALT note.

### 1.2 Additional free endpoints on the same surface — candidates, not yet used here

`nba_api.stats.endpoints` exposes many endpoint classes beyond what this repo currently calls. The
ones matching the requested lens (lineups, tracking, hustle, shot charts, referee assignments),
recorded from package documentation/knowledge, **NOT yet independently verified against a live WNBA
`league_id=10` response in this session** (flagged `REQUIRES_LIVE_VERIFICATION` per source):

| Endpoint class | What it would give us | WNBA coverage status |
|---|---|---|
| `boxscoresummaryv2` → `Officials` resultSet | **Referee assignments** — the existing inspection script already pulls this endpoint; the `Officials` resultSet (official name/ID per game) was not the field the script's inspection loop printed (it filtered for arena/city), but the resultSet is present in the endpoint's schema. `REQUIRES_LIVE_VERIFICATION`: confirm the `Officials` resultSet is non-empty for WNBA game IDs (NBA-only stats products sometimes ship empty resultSets for WNBA). | Endpoint already proven reachable for WNBA (repo uses it); specific resultSet population unverified. |
| `boxscorehustlev2` / `leaguehustlestatsplayer` / `leaguehustlestatsteam` | **Hustle stats** — deflections, loose balls recovered, charges drawn, contested shots, screen assists. Directly useful to M13 (player-value translation needs activity/effort signal beyond box score) and M06 (workload/exposure context for injury studies). | `REQUIRES_LIVE_VERIFICATION` — hustle tracking historically launched later and with uneven WNBA backfill; must confirm season coverage before relying on it. |
| `boxscoreadvancedv2` | **Advanced box score** (offensive/defensive rating, usage%, pace, PIE) per player per game | `REQUIRES_LIVE_VERIFICATION`, but same call shape as `boxscoretraditionalv2`/`boxscoremiscv2` already proven live — low-risk extension. |
| `shotchartdetail` | **Shot charts** — shot location (x/y), shot type, make/miss, per player/team/season | `REQUIRES_LIVE_VERIFICATION` — shot x/y tracking coverage for WNBA has historically been inconsistent across seasons; must confirm before treating as complete. |
| `boxscoreplayertrackv2` / player-tracking (SportVU-derived) endpoints | **Player tracking** (speed, distance, touches) | `LIKELY_UNAVAILABLE` — optical tracking infrastructure has been an NBA-arena investment; WNBA arena coverage is materially incomplete or absent for most of the historical window. Flagged low-confidence, do not build a fetcher until verified empty-vs-populated on a real call. |
| `leaguedashlineups` / lineup endpoints | **Lineup data** — 5-man unit on/off splits | `REQUIRES_LIVE_VERIFICATION` — same `league_id=10` parameter pattern as the already-working `leaguegamelog` call; structurally likely to work, not yet tested. |

**Gate-4 plan for graduating any row in this table:** a single verification script
(`starter_scripts/verify_wnba_endpoint_coverage.py`, §1.3 below) that calls each candidate endpoint
for a small fixed sample of already-known WNBA game IDs (drawn from `data/wnba_gamelog_2024.parquet`,
already on disk) and records row counts / non-null coverage per resultSet. No endpoint in this table
graduates past "candidate" until that script has run and its output is reviewed — this survey does
not claim any of them work; it claims they are worth the one cheap check.

### 1.3 Starter script — endpoint coverage verification only (not a scheduled fetcher)

Zero cost, zero key, uses the same `nba_api` package and call pattern already live in this repo. This
script performs **read-only, single-game-ID spot checks** against `boxscoresummaryv2` (Officials
resultSet), `boxscorehustlev2`, `boxscoreadvancedv2`, `shotchartdetail`, and `leaguedashlineups` — at
most 5 endpoint calls total against 1 known game ID, well inside the "1-2 documentation-verification
calls" spirit extended slightly because there are 5 distinct endpoint *families* to characterize, not
5 calls to the same one. It is not scheduled and must not be added to cron/CI as-is.

```python
"""
verify_wnba_endpoint_coverage.py
D028 FREE_DATA_SURVEY starter script — coverage verification ONLY.
Not a production fetcher. Not scheduled. Run manually, at most once per
candidate-endpoint review cycle, against a tiny fixed game-ID sample.

Zero cost: uses nba_api (MIT-licensed wrapper) against the same
stats.wnba.com JSON surface already load-bearing in scripts/01_acquisition/.
No API key. No login. No write to any frozen artifact.
"""
import json
from datetime import datetime, timezone

from nba_api.stats.endpoints import (
    boxscoresummaryv2,
    boxscorehustlev2,
    boxscoreadvancedv2,
    shotchartdetail,
    leaguedashlineups,
)

# One known-good WNBA game ID from data already on disk in this repo
# (data/wnba_gamelog_2024.parquet). Replace/extend only for manual re-checks.
SAMPLE_GAME_ID = "1022400001"
WNBA_LEAGUE_ID = "10"
WNBA_TEAM_ID_SAMPLE = "1611661313"  # placeholder — fill from roster data before running

CHECKS = {}


def record(name, fn):
    """Run one endpoint call, record row counts per resultSet, never raise past this point."""
    retrieval_ts = datetime.now(timezone.utc).isoformat()
    try:
        resp = fn()
        data = resp.get_json() if hasattr(resp, "get_json") else None
        parsed = json.loads(data) if isinstance(data, str) else data
        result_sets = parsed.get("resultSets") or parsed.get("resultSet") or []
        if isinstance(result_sets, dict):
            result_sets = [result_sets]
        summary = [
            {"name": rs.get("name"), "row_count": len(rs.get("rowSet", []))}
            for rs in result_sets
        ]
        CHECKS[name] = {
            "status": "OK",
            "retrieval_ts": retrieval_ts,
            "result_sets": summary,
        }
    except Exception as e:  # noqa: BLE001 — this is a diagnostic probe, not production code
        CHECKS[name] = {
            "status": "ERROR",
            "retrieval_ts": retrieval_ts,
            "error": f"{type(e).__name__}: {e}",
        }


if __name__ == "__main__":
    record(
        "boxscoresummaryv2.Officials",
        lambda: boxscoresummaryv2.BoxScoreSummaryV2(game_id=SAMPLE_GAME_ID),
    )
    record(
        "boxscorehustlev2",
        lambda: boxscorehustlev2.BoxScoreHustleV2(game_id=SAMPLE_GAME_ID),
    )
    record(
        "boxscoreadvancedv2",
        lambda: boxscoreadvancedv2.BoxScoreAdvancedV2(game_id=SAMPLE_GAME_ID),
    )
    record(
        "shotchartdetail",
        lambda: shotchartdetail.ShotChartDetail(
            team_id=WNBA_TEAM_ID_SAMPLE,
            player_id=0,
            game_id_nullable=SAMPLE_GAME_ID,
            context_measure_simple="FGA",
        ),
    )
    record(
        "leaguedashlineups",
        lambda: leaguedashlineups.LeagueDashLineups(
            league_id=WNBA_LEAGUE_ID, season="2024", season_type_all_star="Regular Season"
        ),
    )

    print(json.dumps(CHECKS, indent=2))
    # Human review step: for each "OK" entry, confirm result_sets row_count > 0
    # before treating the endpoint as WNBA-populated. An OK status with all
    # row_count == 0 means the endpoint exists but is empty for WNBA — do not
    # graduate it.
```

**This script is NOT graduated to a scheduled capture pipeline.** Its sole purpose is to answer
"does this resultSet come back non-empty for WNBA" so a *future* node can decide whether to build a
real fetcher. Running it is the single permitted live check under the D028 mandate's execution
ceiling for this survey.

---

## 2. Basketball-Reference WNBA pages

**Object:** `basketball-reference.com` / `sports-reference.com` family — includes WNBA player/team
season pages, game logs, splits, on/off, shooting data.

**ToS/robots posture — checked, not assumed:**

* `basketball-reference.com/robots.txt` (fetched this session) blocks automated access to
  `/basketball/`, `/blazers/`, `/dump/`, `/fc/`, `/my/`, `/7103`, multiple play-index paths, and —
  materially for this survey — **gamelogs, splits, on-off data, lineups, and shooting-stat paths
  specifically**, plus a 3-second crawl-delay directive on `/req/`, `/short/`, `/nocdn/`. AhrefsBot
  and GPTBot are fully disallowed; unnamed/generic bots are subject to the path-level blocks above.
* Sports Reference's public data-use policy (`sports-reference.com/data_use.html`) — attempted fetch
  this session returned HTTP 403, so its exact current text is **not independently confirmed in this
  session**; this is recorded as a gap, not papered over. Sports Reference has a long-standing,
  widely-documented public position (stated on their own site historically and referenced across the
  sports-analytics community) that bulk/automated scraping of their stat pages without a commercial
  data license is prohibited, and that their paid Stathead/CSV-export tooling is the sanctioned route
  for programmatic access.

**Classification: PROHIBITED for automated capture.** Even setting aside the unconfirmed data-use
page, the robots.txt block on exactly the page families this survey's lens asked about (gamelogs,
splits, lineups, shooting data) is sufficient on its own under D028 gate 2 ("no ToS-violating
scraping, no fuzzy legality"). This source **does not graduate**. It stays parked. If a licensed
route (Stathead subscription, or a written data-license) is ever wanted, that is a spend decision —
routes to the M02B vendor-purchase gate, never resolved inside this survey.

**Gate 3 relevance (if this were ever unblocked by license):** would be genuinely useful to M13
(historical shooting splits, advanced per-100 rates for player-value translation) and M06 (games-
played/minutes-load history as injury-adjacent workload context). Recorded so the case exists if the
user later wants to route a Stathead subscription to M02B — not built further here.

---

## 3. Public play-by-play datasets (GitHub / academic)

### 3.1 `sportsdataverse` / `wehoop` WNBA data pipeline — **candidate for graduation**

Checked live this session:

* `github.com/sportsdataverse/wehoop-wnba-raw` — confirmed to exist; described as the raw-scraping
  layer that extracts WNBA schedules and play-by-play **from ESPN's public endpoints** (script named
  `espn_wnba_02_pbp_scrape.py` in the repo's own pipeline), feeding a downstream processing repo.
  853 commits, actively maintained per the fetch.
* `github.com/sportsdataverse/wehoop-wnba-data` — confirmed to exist; publishes **processed datasets
  as GitHub Releases**: ESPN WNBA schedules, play-by-play, team box scores, and player box scores
  (each presumably as a downloadable file per release, standard GitHub Releases mechanism). License
  files (`LICENSE`, `LICENSE.md`) are present in the repo; **exact license terms were not readable
  from the fetched page content in this session** — this is a genuine gap, flagged rather than
  assumed permissive.

**What this actually is, stated precisely:** `sportsdataverse` runs the ESPN-scraping burden
themselves and republishes the *result* as static files attached to GitHub Releases. Our consumption
of those release files is a **GitHub download**, not scraping ESPN ourselves — this is the load-
bearing distinction for gate 2. We would not be the ones hitting ESPN's undocumented endpoints; we
would be downloading files a third party already published under an open-source repo, the same way
one would depend on any other open dataset release. This is a materially different legal posture
from basketball-reference (§2), which blocks the paths directly.

**Gate assessment:**
1. Zero cost — yes, public GitHub Releases, no auth. **CLEAR.**
2. Lawful access — CONDITIONAL. The repo carries LICENSE/LICENSE.md files but this session could not
   read their exact terms (fetch returned only a page summary, not raw file content). **Before this
   graduates further than "candidate," the actual LICENSE text must be read from the raw file** (e.g.
   `raw.githubusercontent.com/sportsdataverse/wehoop-wnba-data/main/LICENSE`) — not assumed permissive
   because the repo is public. Recorded as `REQUIRES_LICENSE_TEXT_VERIFICATION`, not cleared.
3. Genuinely useful — yes, unambiguously, to M06 and M13: cleaned, structured, historical WNBA
   play-by-play at zero cost duplicates and cross-validates this repo's own `nba_api`-sourced
   play-by-play (§1), giving an independent-source check on a data path this repo already depends on
   for the possession lane — valuable for corroboration, gap-filling seasons where the stats.wnba.com
   surface has holes, and as a fallback if that surface's availability ever degrades.
4. Concrete plan — see below.

**Status: NOT YET GRADUATED — one verification step short.** The plan below is written so that once
the LICENSE text is confirmed permissive (e.g., MIT/CC-BY/ODbL-class), the same design activates
without further design work; if the license turns out to require attribution-only, non-commercial,
or share-alike terms, that changes gate 2's answer and this survey would re-classify accordingly
rather than silently building against it.

**Capture design (pending license confirmation):**

* **Endpoints:** GitHub Releases API, `GET
  https://api.github.com/repos/sportsdataverse/wehoop-wnba-data/releases` (unauthenticated, GitHub's
  public API; 60 requests/hour unauthenticated rate limit — trivial for a periodic pull) to enumerate
  release assets, then direct `https://github.com/.../releases/download/<tag>/<asset>` file downloads.
* **Cadence:** these are batch-published historical datasets, not live feeds — a weekly or
  post-season-completion pull is more than sufficient; no case for anything higher-frequency.
* **Quota limits:** GitHub unauthenticated REST API: 60 req/hour per IP. A release-listing pull uses
  1 request; asset downloads are plain file GETs, not API-rate-limited the same way. Comfortably
  inside budget for even daily checks.
* **Schema mapping:** ESPN's WNBA play-by-play schema (event type, clock, score, participants) is
  materially different from `nba_api`'s `PlayByPlayV2` schema already used in
  `fetch_wnba_playbyplay.py` — this would land as a **separate, clearly-labeled second source table**
  (e.g. `data/playbyplay_espn_wehoop/`), never merged into the existing `stats.wnba.com`-sourced PBP
  table without an explicit reconciliation/crosswalk step, per the same discipline `MARKET_PROGRAM_CONTRACT.md`
  §4.5 applies to market data ("exclusion, never patching" — the analogous fundamentals-side discipline
  is: never silently blend two vendors' event streams into one series).
* **Amendment-4-style timestamp fields:** even though this is fundamentals data (not a market
  reaction-time claim under §6), the same discipline is applied by design so any future timing
  question about "when did we learn this" is answerable: `source_repo`, `source_release_tag`,
  `source_asset_name`, `retrieval_ts` (when we downloaded it), `espn_event_ts` (as published in the
  payload, labeled `VENDOR_ASSERTED` — ESPN's own event timestamps are not independently witnessed by
  us), `ingestion_ts`, `payload_hash`. No field here is claimed as witnessed; all are vendor-asserted
  or our own retrieval-time facts.

### 3.2 Academic public play-by-play datasets

No specific academic (e.g. university-hosted, Kaggle-permanent, or journal-supplementary) WNBA
play-by-play dataset was identified and independently verified in this session. General knowledge
suggests occasional Kaggle WNBA datasets exist, but Kaggle dataset licenses vary per-uploader and
per-dataset (some CC0, some all-rights-reserved-with-permission, some scraped-and-reposted with
unclear original-source rights) — **none is named here as a candidate** because gate 2 cannot be
cleared without checking a specific dataset's specific license, and doing that honestly requires
naming and checking one, not gesturing at "Kaggle has WNBA data somewhhere." Recorded as
`NOT_SURVEYED_INSUFFICIENT_SPECIFICITY` rather than a false negative or a manufactured candidate.

---

## 4. Official league press-release feeds for transactions/injuries

**Object:** WNBA.com and/or team official sites' transaction wire, injury report postings, press
releases.

**Status: NOT YET GRADUATED — no specific feed endpoint verified this session.** This survey did not
spend a live-verification call confirming whether WNBA.com exposes a structured feed (RSS/JSON) for
transactions or injury reports versus only rendered HTML press-release pages. This is a real gap, not
a negative finding — recorded as `REQUIRES_LIVE_VERIFICATION`, distinct from basketball-reference's
confirmed-PROHIBITED status.

**What would make this genuinely useful (gate 3, stated so a future check knows what it's looking
for):** M06 (injury studies) needs a **point-in-time-honest** injury-report capture — the moment a
player is listed OUT/QUESTIONABLE/PROBABLE, not a reconstructed injury history. An official league
feed, if it exists in machine-readable form (RSS is the most likely legitimate zero-cost shape — RSS
is explicitly designed for automated, permitted consumption, unlike scraping a rendered page), would
be the cleanest possible source for exactly the `vendor_ts_semantics` discipline `MARKET_PROGRAM_CONTRACT.md`
§6.3 requires: an RSS `pubDate` is a vendor-published timestamp we can label
`vendor_ts_semantics = vendor_ingest_time` with real confidence, rather than `unknown_unverified`.

**Recommended next step (not performed here, stays inside this survey's execution ceiling):** one
future documentation-verification call to check `wnba.com` for an RSS/Atom feed URL (commonly at a
path like `/feed` or discoverable via a `<link rel="alternate" type="application/rss+xml">` tag on
the news/transactions page) and to check individual WNBA team sites for the same. If found, this
graduates on the same logic as §3.1's GitHub-Releases case: a feed format's entire design purpose is
permitted automated polling, which clears gate 2 far more cleanly than scraping HTML would. If no
feed exists and only rendered HTML press releases are available, this stays parked exactly like
basketball-reference — HALT rather than build a scraper.

---

## 5. Sources parked (not graduated) and why

| Source | Gate failed | Disposition |
|---|---|---|
| Basketball-Reference / Sports-Reference family (§2) | Gate 2 — robots.txt explicitly blocks gamelogs/splits/lineups/shooting paths; data-use policy text unconfirmed but historically restrictive | PARKED — RED flag, consistent with the RotoWire-class discipline named in the mandate. Route a Stathead license to M02B if ever wanted; do not scrape. |
| Player-tracking / SportVU-derived endpoints on the `nba_api` surface (§1.2) | Gate 4 — plan incomplete; WNBA arena optical-tracking coverage is likely materially incomplete and unverified | PARKED as `LIKELY_UNAVAILABLE`, revisit only after the §1.3 verification script is actually run |
| Kaggle / generic academic WNBA PBP datasets (§3.2) | Gate 2 — no specific dataset+license identified to check | NOT_SURVEYED, not parked-as-failed; needs a named candidate before it can be gated at all |
| WNBA.com official transactions/injury feed (§4) | Gate 4 — no endpoint verified live this session | NOT_YET_GRADUATED, single next step identified |
| `sportsdataverse`/`wehoop` WNBA data (§3.1) | Gate 2 — license text not read, only repo presence confirmed | ONE STEP FROM GRADUATION — read the LICENSE file raw content before building the real fetcher |

**Stop-condition note (HALT, not resolved here):** §1.1's characterization of the existing
`stats.wnba.com`/`nba_api` surface as "undocumented-but-established" rather than "documented public
API" sits close to the mandate's gate 2 language. This survey does not silently wave that through —
it is flagged here as a judgment call worth a second opinion, since M00 §9.7 reserves "legal/risk
acceptance... ToS interpretation" as a USER_REQUIRED matter, and this repo's own possession lane has
already built four production fetchers on this exact surface. Extending it to new endpoint families
(§1.2) is treated here as continuous with existing practice rather than a new risk decision, but
that reasoning is surfaced explicitly rather than assumed, per the mandate's "NO fuzzy legality"
instruction.

---

## 6. Summary table

| # | Source | Cost | Legal posture | Gate 3 target(s) | Gate 4 plan status | Graduated? |
|---|---|---|---|---|---|---|
| 1 | `nba_api`/`stats.wnba.com` — endpoints already in use | Free | Undocumented-but-established, precedent in this repo | M13, M06 (existing possession-lane data) | Complete (already running) | Already in production use (pre-existing) |
| 1.2 | Same surface — hustle/advanced/shotchart/lineups/officials | Free | Same posture, extension of #1 | M13 (activity signal), M06 (workload), event capture (officials) | Verification script written, NOT run | NOT GRADUATED — pending live verification |
| 2 | Basketball-Reference / Sports-Reference | Free (page views) / Paid (Stathead) | robots.txt PROHIBITS the relevant paths | M13, M06 | N/A | PARKED — RED, route license to M02B if wanted |
| 3.1 | `sportsdataverse`/`wehoop` WNBA GitHub Releases | Free | Repo confirmed; license text unread | M06, M13 (independent PBP cross-check) | Design complete, pending license read | NOT GRADUATED — one check short |
| 3.2 | Academic/Kaggle WNBA PBP | Unknown | No candidate named | M06, M13 | N/A | NOT SURVEYED |
| 4 | WNBA.com official transactions/injury feed | Free (if RSS exists) | Unverified — feed existence unchecked | M06 (injury point-in-time capture) | Next step identified, not executed | NOT GRADUATED — no endpoint confirmed |

**Nothing in this survey was scheduled or executed against a live endpoint beyond the documentation-
verification fetches logged above** (`basketball-reference.com/robots.txt`,
`sports-reference.com/data_use.html` [403, unreadable], `github.com/sportsdataverse/wehoop-wnba-raw`,
`github.com/sportsdataverse/wehoop-wnba-data`) and the §1.3 script is provided but was **not run**
against the live `stats.wnba.com` surface in this session — it is delivered as a starter script for a
future node to run, not as an executed capture.
