# Props capture setup — WNBA player props on The Odds API

**Date:** 2026-07-31 | **Status:** LIVE — first real snapshot captured 20260731T142341Z.
Props have no backfill on our plan; forward accumulation started today. Every day not
captured is gone.

## What exists (verified, not assumed)

Discovery = one free `/events` call + one 1-credit single-event `player_points` probe,
then the first real capture (raw evidence: `discovery_events_*.json`,
`discovery_probe_*.json` here; per-event raws in `data/props_capture/raw/`).

- **All four target markets are live for WNBA**: `player_points`, `player_rebounds`,
  `player_assists`, `player_threes`. No 422s, none suspended on a 5-event slate.
- **5 US books quote WNBA props**: fanduel, draftkings, betrivers, williamhill_us
  (Caesars), betonlineag. **Day-of games get all 5; day-ahead games get 3** — props post
  thin the afternoon before and fill in on game day (so the morning snapshot's day-ahead
  rows are early-line gold, but coverage counts below are day-of).
- **Players per game per market (day-of):** points ~10-11, rebounds ~9, assists 5-9,
  threes 6-9. Stars are quoted everywhere; role players mostly points/rebounds only.
- **78% of lines have both over+under priced.** The gap is almost entirely **betrivers
  alternate lines** (only book posting them; 27 player-market combos with 2+ points,
  often over-only). Flattener keys on (player, **point**) so alternates are separate rows.
- **Books genuinely disagree**: e.g. A'ja Wilson points 27.5 (FD) vs 26.5 (DK, BOL) same
  snapshot — cross-book line shopping is real in this market, which is exactly the
  "can we consistently beat a prop type" question's raw material.

## Cost (measured, credit headers)

`/events` = 0 credits. Per-event odds call = **markets x regions = 4 x 1 = 4 credits**
(header `x-requests-last: 4`, confirmed on all 5 events). Failed requests cost 0.

Spent today: 1 (probe) + 20 (first snapshot, 5 events) = **21 credits. 11,180 remaining.**

### Per-day credit cost (4 markets, us, 36h look-ahead window)

The 36h window catches today's AND most of tomorrow's games at each snapshot, so
events-in-window ~= games today + games tomorrow (~1.5-2x the daily slate).

| Slate (events in window) | 1 snap/day | 2 snaps | 3 snaps |
|---|---|---|---|
| Light (2) | 8 | 16 | 24 |
| Modest (3) | 12 | 24 | 36 |
| **Typical (5 — today's actual)** | **20** | **40** | **60** |
| Heavy (8) | 32 | 64 | 96 |

Monthly at 3 snaps/day, typical slates: **~1,200-1,800 credits/month.** Trivial on the
paid tier (20K) even alongside the existing game-line capture (~72/day).

### Free-tier feasibility (feeds the ~Aug 30 tier decision)

**This cadence does NOT fit 500/month.** Even 1 snapshot/day on typical slates is
~600/month before a single game-line credit. The only free-tier shape is 1 snap/day,
24h window (~10-12/day ~= 330/month) — which forfeits line movement, early-vs-closing
comparison, and leaves ~170/month for everything else. **If props matter, the paid tier
is required.** That is the concrete input for John's decision.

## Settlement (grading is free)

Actuals for all four markets — points, rebounds, assists, made threes — are already in
our player gamelog masters. Grading = join `master_props.csv` on (player_name, game
date from `commence_time` in ET) to the gamelogs; no API credits involved. One known
chore: name normalization (API uses full display names, e.g. "A'ja Wilson"). Closing
line ~= last snapshot before commence_time.

## Recommended snapshot schedule

**3/day at 10:05, 15:05, 19:35 ET** (script is capture-once; orchestrator schedules).
- 10:05 — first look at tonight + earliest lines on tomorrow (3-book early market).
- 15:05 — mid-day move; day-of books have filled in to 5.
- 19:35 — near-closing for the 7-7:30pm ET tips that dominate the slate.
Known limit: 9-10pm ET West-coast tips close well after 19:35; if closing-line fidelity
there starts to matter, add a 4th snap ~21:35 ET (+~1/3 daily cost) later.

## Artifacts

- `props_capture_daily.py` (repo root) — the capture script. Idempotent per (event,
  book, market, player, line, snapshot); explicit counts on empty slates and missing
  markets; credit headers logged every call; 422 market-drop retry; no scheduler inside.
- `data/props_capture/raw/props_<eventid>_<UTCstamp>.json` — raw archive, one per event
  per snapshot (5 files today).
- `data/props_capture/master_props.csv` — flattened master, 597 rows from snapshot 1.
  Columns: api_event_id, home_team, away_team, commence_time, bookmaker_key, market_key,
  player_name, line, over_price, under_price, snapshot_utc, last_update.
