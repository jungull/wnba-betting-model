# Track C — Free Stats Surface Expansion: Live Verification Report

**Lane:** market_intelligence · **Node:** Track C (FREE STATS SURFACE EXPANSION)
**Write scope:** `experiments/market_program/FREE_DATA_SURVEY/stats_surface/` (this directory only)
**Date:** 2026-08-06

**Contract binding:** `MARKET_PROGRAM_CONTRACT.md` sha256 verified this session —
`1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de` (matches task-supplied hash,
case-insensitive).

**Scope:** live-verify the endpoint candidates named in `FUNDAMENTALS_SOURCES.md` §1.2
(lineups, hustle stats, shot charts, officials/referee assignments, advanced box scores) against
real WNBA 2025 game_ids already on disk (`data/wnba_gamelog_2025.parquet`), then build capture
scripts for whatever verifies real. Free/keyless `stats.nba.com` surface only — **no calls made to
`api.the-odds-api.com`** (paid, reserved for the coordinator's historical backfill currently
running).

**Etiquette actually used:** 9 total live requests against `stats.nba.com`, spaced >=0.8s apart
(most >=2s), using `nba_api`'s default production headers (Host: stats.nba.com, browser
User-Agent, `Referer: https://www.nba.com/`) — the same headers/host already load-bearing in
`scripts/01_acquisition/*.py`. Within the "<=10 total requests" ceiling given for this track.

Sample game_ids used (WNBA, 2025 season, pulled from the repo's own gamelog data):
- `1022500001` — ATL (1611661330) vs WAS (1611661322)
- `1022500002` — MIN (1611661324) vs DAL (1611661321)

Raw machine-readable output of the primary 7-call script run: `endpoint_coverage_report.json`
(same directory).

---

## Verdict per endpoint

| Endpoint | Verdict | Evidence | Season depth | Capture script |
|---|---|---|---|---|
| `boxscoresummaryv2` → `Officials` resultSet | **REAL, GRADUATED** | 3 officials/game, both sample game_ids, full headers (OFFICIAL_ID, FIRST_NAME, LAST_NAME, JERSEY_NUM) | Confirmed 2025; endpoint itself already proven live 2021-2025 by existing `inspect_boxscoresummaryv2.py` usage — Officials resultSet specifically only checked for 2025 here | `fetch_wnba_officials.py` |
| `boxscoreadvancedv2` | **REAL, GRADUATED** | 23 PlayerStats rows + 2 TeamStats rows, fully populated (OFF_RATING, DEF_RATING, USG_PCT, PACE, PIE, etc. all non-null in the returned headers/shape) for game `1022500001` | Confirmed 2025 only (1 game checked); same call shape as production `boxscoretraditionalv2`/`boxscoremiscv2`, low-risk to extend to full historical range | `fetch_wnba_boxscore_advanced.py` |
| `leaguedashlineups` | **REAL, GRADUATED (after param fix)** | `league_id_nullable="10"` (not `league_id` — that kwarg name doesn't exist on the current `nba_api` signature and raises `TypeError`), `season="2025-26"` returned 2000 lineup rows for WNBA | Confirmed 2025-26 only; season string format for this endpoint is `"YYYY-YY"`, unlike `leaguegamelog`'s plain `"2025"` — historical seasons untested but same param pattern expected to work | `fetch_wnba_lineups.py` |
| `boxscorehustlev2` | **LIKELY DEAD FOR WNBA** | Errored both sample game_ids (`AttributeError: 'NoneType' object has no attribute 'get'` inside `nba_api`'s own response parser — consistent with an empty or non-JSON response body from the server, not a client-side param bug: the endpoint's only required arg is `game_id`, which was supplied correctly) | Untested beyond 2025; not scheduled further | **No capture script built.** Do not treat as populated. |
| `shotchartdetail` | **UNRESOLVED — endpoint responds, but our query returned empty** | HTTP-level call succeeded (`Shot_Chart_Detail` resultSet present with correct headers, `LeagueAverages` resultSet populated with 20 rows), but `Shot_Chart_Detail` itself was 0 rows for `player_id=0` (the "all players on team" sentinel does not appear to aggregate — this endpoint typically requires a specific individual `player_id`, not a team-wide roll-up) | Not determined — the empty result is a query-shape problem in this probe, not evidence the data doesn't exist | **No capture script built.** Needs one more live check with a real individual `player_id` before it can be graduated or killed. |

---

## What this means for the four D028 gates (per endpoint, additive to `FUNDAMENTALS_SOURCES.md` §1.2)

All three graduated endpoints (Officials, advanced box score, lineups) inherit the same gate-1/
gate-2 posture already recorded for the base `stats.nba.com`/`nba_api` surface in
`FUNDAMENTALS_SOURCES.md` §1.1: zero cost, no key, **UNDOCUMENTED-BUT-ESTABLISHED** (not a
formally documented public API, but the same JSON surface already load-bearing for this repo's
possession lane, with no robots.txt disallow or login wall). This report does not re-litigate that
judgment call — it is flagged there as a HALT-worth judgment for the user, not resolved here, and
that flag still applies to extending the surface to these new endpoint families.

- **Officials → M06/M25-adjacent (officials/referee assignment record).** Gate 3: useful for any
  node modeling foul-rate or pace effects tied to specific officiating crews. Gate 4: concrete —
  see `fetch_wnba_officials.py`.
- **Advanced box score → M13 (player-value translation).** Gate 3: directly useful — usage%, PIE,
  on-court ratings are exactly the "activity beyond box score" signal `FUNDAMENTALS_SOURCES.md`
  flagged as wanted. Gate 4: concrete — see `fetch_wnba_boxscore_advanced.py`.
- **Lineups → M13.** Gate 3: 5-man on/off splits are directly useful for player marginal-value
  estimation. Gate 4: concrete — see `fetch_wnba_lineups.py`.
- **Hustle stats:** does not clear gate 4 (no working capture plan — the endpoint itself appears
  non-functional for WNBA game_ids tested). Recorded as parked, not silently dropped.
- **Shot charts:** does not yet clear gate 4 — plan is incomplete pending one more live check with
  a real `player_id`. Parked pending that check, not graduated, not killed.

## Amendment-4 timestamp discipline

All three capture scripts stamp every row with `retrieval_ts` (our own capture-time fact, UTC
ISO8601), `vendor_ts_semantics` (set to `"not_a_timing_claim"` — these are stat-snapshot captures,
not injury/market timing claims, so this is deliberately not `unknown_unverified`; it's an
explicit statement that no timing semantics are being asserted), and `provenance_class`
(`"witnessed_direct_api_capture"` — we made the HTTP call ourselves, this is not
vendor-republished or third-party-scraped data).

## What was NOT done here (explicitly, so nothing is silently assumed)

- No calls to `api.the-odds-api.com` (paid host, reserved for the coordinator's running backfill).
- No capture script was **run** against a full historical range — `fetch_wnba_officials.py`,
  `fetch_wnba_boxscore_advanced.py`, and `fetch_wnba_lineups.py` are built and verified against
  single-game/single-season spot checks only. A full-season or full-history run is a materially
  larger pull (hundreds of requests) and is left for the coordinator to schedule per the
  "NOT SCHEDULED — the coordinator schedules" instruction.
- No scripts were added to cron/CI/any scheduler.
- Hustle stats and shot charts were left un-graduated rather than forced through — an errored or
  empty probe was not reinterpreted as success.
