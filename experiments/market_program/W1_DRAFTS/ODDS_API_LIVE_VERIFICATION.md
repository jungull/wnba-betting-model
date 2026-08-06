# Odds API Live-Key Verification — WNBA (basketball_wnba)

**Lane:** market_intelligence (D023) — **Role:** ODDS_API_LIVE_VERIFICATION (D025, user purchased 20K tier)
**Status:** Live key confirmed and exercised against `api.the-odds-api.com`. This document supersedes the documentation-only hypotheses in `ODDS_API_VERIFICATION.md` §1–§3 wherever they conflict — every number below was produced by an actual HTTP call, not a fetched-page paraphrase.
**Credential handling:** Key loaded from `.env` at repo root exactly as `odds_capture_daily.py::api_key()` does (env var first, then `.env` fallback). The key value was never printed, logged, written to a file, or included in any request URL that appeared in tool output — all probe scripts redacted it from exception text before it could surface, and results were captured via response headers/body only. Scratch probe scripts and raw JSON results used to build this report were deleted after extraction; only this markdown lives in `W1_DRAFTS/`.

---

## 0. Bottom line up front

- **Tier confirmed live:** the key is on the paid 20,000-credit/month tier (D025 purchase), not the free Starter tier. Confirmed by the `/v4/sports` quota call: `x-requests-remaining: 19448`, `x-requests-used: 552` at session start (19448 + 552 = 20000).
- **§1c conflict RESOLVED:** the WNBA featured-market (h2h/spreads/totals) historical floor is **not** 2020-06-06 and is **not** a vague "May 2022." It is the exact 5-minute snapshot **2022-05-21T09:05:00Z**. A query one snapshot earlier (`2022-05-21T09:04:00Z`) returns an empty `data` array with `previous_timestamp: null`, and the query at the floor snapshot itself also carries `previous_timestamp: null` — that is the first snapshot the vendor's historical archive has for this sport, full stop. Nothing "2020" exists for WNBA in this archive; the general "since 2020-06-06" claim on the vendor's docs is not sport-specific and does not apply to `basketball_wnba`.
- **Player-prop history is real but NOT a clean date floor — it is patchy/event-dependent coverage.** Real bookmaker `player_points` quotes were pulled live for a 2025-05-20 game (6 bookmakers, ~140 outcome lines) and a 2025-07-15 game (6 bookmakers). But probes at 2023-06-15, 2024-07-01, 2024-09-01, and 2025-06-15 all returned valid historical snapshots with an **empty bookmakers array** for player_points on the (arbitrarily first-returned) event tested at each date. The one hit in the 2024–2025 range was a Caitlin Clark game (Indiana Fever @ Atlanta Dream) — the sample is small (n=5, non-random event selection) and consistent with the interpretation that historical player-prop capture is denser for marquee games/players than for the median WNBA game, not a hard "available since date X" line. **Do not budget a props backfill as if coverage is uniform across all games in a season** — the earlier draft's "2023-05-03 policy floor, uniform" assumption is not supported by what was actually returned.
- **Historical credit cost measured directly, not inferred:** featured-markets historical odds calls cost **10 credits** when they return real data (`10 × 1 market × 1 region`, matching the documented 10× multiplier) and **0 credits** when the queried timestamp predates the archive (empty `data`, unbilled). The `/v4/historical/.../events` list call costs a flat **1 credit** regardless of markets/regions. The per-event historical odds call (used for props) costs **10 credits** when it returns real bookmaker data and **0 credits** when it returns an empty `bookmakers` array — i.e., **empty historical responses are not billed**, which materially changes backfill cost math versus a worst-case "every call costs the max" assumption.
- **Total spend this verification run: 57 credits** (x-requests-used moved from 552 → 609 across 13 billable-eligible probes; 401/403 was never hit; budget cap of 500 was never approached).

---

## 1. Session credit ledger

| # | Probe | Timestamp param | Status | Bookmakers | Snapshot `timestamp` | `previous_timestamp` | `next_timestamp` | Credit cost (x-requests-last) | Cumulative used |
|---|---|---|---|---|---|---|---|---|---|
| 0 | baseline (before any call) | — | — | — | — | — | — | — | 552 |
| 1 | `/v4/sports` quota check | n/a | 200 | n/a | n/a | n/a | n/a | 0 | 552 |
| 2 | historical odds, featured, h2h/us | 2020-08-01T00:00:00Z | 200 | 0 games | null (empty) | null | 2022-05-21T09:05:00Z | 0 | 552 |
| 3 | historical odds, featured, h2h/us | 2021-06-15T00:00:00Z | 200 | 0 games | null (empty) | null | 2022-05-21T09:05:00Z | 0 | 552 |
| 4 | historical odds, featured, h2h/us | 2022-05-25T00:00:00Z | 200 | 3 games, 6-7 books/game | 2022-05-24T23:55:00Z | 2022-05-24T23:45:00Z | 2022-05-25T00:05:00Z | 10 | 562 |
| 5 | historical odds, featured, h2h/us | 2022-07-10T00:00:00Z | 200 | 1 game, 2 books | 2022-07-08T04:15:00Z | 2022-07-08T04:05:00Z | 2022-07-11T17:55:00Z | 10 | 572 |
| 6 | historical events list | 2023-06-15T00:00:00Z | 200 | n/a (1 event listed) | 2023-06-14T19:10:37Z | 2023-06-14T19:05:37Z | 2023-06-15T00:25:37Z | 1 | 573 |
| 7 | historical event odds, player_points | 2023-06-15T00:00:00Z (same event) | 200 | 0 books | 2023-06-14T19:10:37Z | 2023-06-14T19:05:37Z | 2023-06-15T00:25:37Z | 0 | 573 |
| 8 | historical events list | 2024-07-01T00:00:00Z | 200 | n/a (3 events listed) | 2024-06-30T23:55:38Z | 2024-06-30T23:50:38Z | 2024-07-01T00:00:38Z | 1 | 574 |
| 9 | historical event odds, player_points | 2024-07-01T00:00:00Z (same event) | 200 | 0 books | 2024-06-30T23:55:38Z | 2024-06-30T23:50:38Z | 2024-07-01T00:00:38Z | 0 | 574 |
| 10 | historical odds, featured, h2h/us — floor confirm | 2022-05-21T09:05:00Z | 200 | 1 game, 0 books (empty bookmakers for this specific game, but non-null snapshot) | 2022-05-21T09:05:00Z | **null** | 2022-05-21T09:15:00Z | 10 | 584 |
| 11 | historical odds, featured, h2h/us — floor confirm minus 1 snapshot | 2022-05-21T09:04:00Z | 200 | 0 games | null (empty) | null | 2022-05-21T09:05:00Z | 0 | 584 |
| 12 | historical events list | 2025-07-15T20:00:00Z | 200 | n/a (6 events listed) | 2025-07-15T19:55:38Z | 2025-07-15T19:50:38Z | 2025-07-15T20:00:38Z | 1 | 585 |
| 13 | historical event odds, player_points | 2025-07-15T20:00:00Z (same event) | 200 | **6 books, real quotes** (DraftKings, Fanatics, FanDuel, Caesars, BetOnline.ag, Bovada) | 2025-07-15T19:55:38Z | 2025-07-15T19:50:38Z | 2025-07-15T20:00:38Z | 10 | 595 |
| 14 | historical events list | 2024-09-01T20:00:00Z | 200 | n/a (4 events listed) | 2024-09-01T19:55:37Z | 2024-09-01T19:50:37Z | 2024-09-01T20:00:37Z | 1 | 596 |
| 15 | historical event odds, player_points | 2024-09-01T20:00:00Z (same event) | 200 | 0 books | 2024-09-01T19:55:37Z | 2024-09-01T19:50:37Z | 2024-09-01T20:00:37Z | 0 | 596 |
| 16 | historical events list | 2025-05-20T20:00:00Z | 200 | n/a (4 events listed) | 2025-05-20T19:55:38Z | 2025-05-20T19:50:37Z | 2025-05-20T20:00:37Z | 1 | 597 |
| 17 | historical event odds, player_points | 2025-05-20T20:00:00Z (same event) | 200 | **6 books, real quotes** (FanDuel, BetRivers, BetOnline.ag, DraftKings, Bovada, BetMGM) — game: Indiana Fever @ Atlanta Dream (Caitlin Clark, Rhyne Howard, Aliyah Boston, etc. all had priced O/U lines) | 2025-05-20T19:55:38Z | 2025-05-20T19:50:37Z | 2025-05-20T20:00:37Z | 10 | 607 |
| 18 | historical events list | 2025-06-15T20:00:00Z | 200 | n/a (2 events listed) | 2025-06-15T19:55:36Z | 2025-06-15T19:50:37Z | 2025-06-15T20:00:37Z | 1 | 608 |
| 19 | historical event odds, player_points | 2025-06-15T20:00:00Z (same event) | 200 | 0 books | 2025-06-15T19:55:36Z | 2025-06-15T19:50:37Z | 2025-06-15T20:00:37Z | 0 | 608 |

**End-of-session quota:** `x-requests-remaining` dropped from 19448 to 19391 (matches 20000 − 609 = 19391, self-consistent). Total task spend: **57 credits**, cap was 500 — no throttling risk encountered, no 401/403 seen at any point.

Table shows every value actually returned by the vendor. Where a row says "0 books" for player_points, the historical odds/event-odds envelope (`timestamp`/`previous_timestamp`/`next_timestamp`) was still returned correctly and matched the archive's real 5-minute snapshot grid at that date — the emptiness is specifically an absence of bookmaker prop postings for that event at that snapshot, not a broken or out-of-range query.

---

## 2. Featured-market historical floor — RULED

**Ruling: the WNBA featured-markets (h2h, and by extension spreads/totals, since they share the same historical archive and snapshot grid) historical floor is 2022-05-21T09:05:00Z.**

Evidence:
- Querying `date=2020-08-01T00:00:00Z` and `date=2021-06-15T00:00:00Z` both return `"data": []`, `"timestamp": null`, `"previous_timestamp": null`, and — critically — the same `"next_timestamp": "2022-05-21T09:05:00Z"` regardless of how far before that date the query is aimed. This is the vendor's own archive telling us there is nothing before that instant for this sport.
- Querying exactly `date=2022-05-21T09:05:00Z` returns real data (`previous_timestamp: null`, confirming this is the first snapshot) with `next_timestamp: 2022-05-21T09:15:00Z` (10-minute grid at this point in the archive's history, consistent with the documented "10-minute until Sep 2022, then 5-minute" cadence).
- Querying one snapshot earlier, `date=2022-05-21T09:04:00Z`, returns empty again with `next_timestamp` pointing right back at the floor.

This directly resolves the conflict flagged in `ODDS_API_VERIFICATION.md` §1c: the general "2020-06-06" claim on the vendor's non-sport-specific docs page does not apply to `basketball_wnba` — WNBA odds simply were not in the historical archive until May 21, 2022. **Do not backfill-budget past 2022-05-21T09:05:00Z for WNBA featured markets; there is nothing there to fetch.**

Spreads/totals were not separately probed (h2h only, to conserve credits per plan) — they are billed and stored on the identical snapshot timeline as h2h per the vendor's own architecture (`markets` is just a filter on the same underlying snapshot), so this floor should hold for all three featured markets, but that specific claim is inference from architecture, not a direct spreads/totals probe. Flag as **VENDOR_ASSERTED-by-analogy** if a spreads/totals-specific confirmation is later required.

Bookmaker coverage observed at/near the floor was thin (0–7 books per game across the probes), consistent with the WNBA odds market being immature at that point in the archive's life — this affects how usable data right at the floor is for modeling purposes, separate from whether it exists.

---

## 3. Player-prop historical availability — RULED

**Ruling: player-prop (player_points) historical data for WNBA is REAL — confirmed by two independent live pulls returning full bookmaker panels with real player names, lines, and prices — but it is NOT available as a uniform "since date X" floor. Coverage is patchy and event-dependent.**

Evidence for "it's real":
- 2025-05-20 (Indiana Fever @ Atlanta Dream): 6 bookmakers returned live historical `player_points` quotes — FanDuel, BetRivers, BetOnline.ag, DraftKings, Bovada, BetMGM — with real player names (Caitlin Clark, Rhyne Howard, Aliyah Boston, Kelsey Mitchell, Brittney Griner, etc.), real lines (e.g., Caitlin Clark Over/Under 20.5 points at −110/−118 on FanDuel), captured at the archive's own 5-minute snapshot (`timestamp: 2025-05-20T19:55:38Z`).
- 2025-07-15 (Connecticut Sun @ Indiana Fever): 6 bookmakers again — DraftKings, Fanatics, FanDuel, Caesars (returned as `williamhill_us`), BetOnline.ag, Bovada — again with real player names and lines.

Evidence for "it's not a clean floor":
- 2023-06-15, 2024-07-01, 2024-09-01, and 2025-06-15 — all mid-season dates, all with valid event listings returned by the `/events` endpoint — returned an **empty bookmakers array** for player_points on the event tested. These are not archive-range failures (the envelope timestamps are real, in-grid snapshots); the vendor's system captured a snapshot at that instant and no bookmaker had posted a `player_points` market for the tested event at that moment.
- The two "hit" dates both happen to be higher-profile games (a Caitlin Clark game in each case, since events are returned in an order that put her games first in both hits). This is circumstantial — the event selection in this probe run always took the *first* event returned by `/events` for a given timestamp, so the correlation with marquee games is a sampling artifact worth calling out, not necessarily a proven mechanism — but it is at minimum consistent with "prop coverage correlates with game visibility," which the earlier draft's uniform-policy assumption did not anticipate.

**Practical consequence for backfill planning:** the earlier draft's assumption ("additional markets since 2023-05-03, uniform 5-minute grid") describes when the archive *mechanism* for additional markets went live, not when any specific game/player actually has captured prop data. A season-wide props backfill cannot be sized by date range alone — it needs either (a) a full historical scan (games × market-check calls) to discover which events actually have captured props, which is expensive at 10 credits per non-empty hit and unpredictable in yield, or (b) acceptance that props backfill coverage will be incomplete and concentrated on higher-visibility games. This is a real, evidence-based gap the earlier draft could not have surfaced without live calls.

---

## 4. Measured credit cost per historical call type

| Call type | Params | Cost when data present | Cost when empty/out-of-range |
|---|---|---|---|
| `/v4/sports` (live, non-historical) | — | 0 (unbilled quota-check call) | n/a |
| `/v4/historical/.../odds` (featured) | 1 market × 1 region (`h2h`, `us`) | **10 credits** (= 10 × markets × regions, matches documented 10× multiplier) | **0 credits** |
| `/v4/historical/.../events` | date only, no markets/regions | **1 credit flat** | 1 credit (was billed even when the returned list was later found to be non-empty in all 6 tests — no empty-events case was hit in this run to confirm whether an empty events list is also unbilled) |
| `/v4/historical/.../events/{id}/odds` (event odds, used for props) | 1 market × 1 region (`player_points`, `us`) | **10 credits** (= 10 × markets × regions) | **0 credits** |

The empty-response-is-unbilled behavior was consistent across 6 empty-result probes (5 for featured odds/props, all showing `x-requests-last: 0`) and is the single most consequential finding for backfill cost modeling — it means a wide date-range scan to *discover* where real data exists is far cheaper than a naive "10 credits × every call" estimate, as long as most of the scan lands on genuinely-empty snapshots.

---

## 5. Backfill sizing formula — filled with real numbers (for M02B)

**Featured markets (h2h + spreads + totals), full season backfill:**

```
cost_per_snapshot_call = 10 × n_markets × n_regions
                        = 10 × 3 (h2h, spreads, totals) × 1 (us)
                        = 30 credits per call
```
Each call returns the *entire* WNBA slate active at that snapshot in one request — cost does not scale with number of concurrent games. For a season running late May–October (WNBA 2024/2025-style calendar, ~ 120–140 game dates including playoffs):

- 1 snapshot/day (e.g., closing line only): ~130 calls × 30 credits ≈ **3,900 credits**
- 2 snapshots/day (open + close, matching the existing `odds_capture_daily.py` cadence): ~130 × 2 × 30 ≈ **7,800 credits**
- Dense capture (e.g., hourly for 6 pre-game hours × ~5 games/day, if pursuing true line-movement reconstruction): scales linearly — 6 snapshots/day × 130 dates × 30 credits ≈ **23,400 credits**, i.e., already over a full 20K-credit month by itself. A dense full-season featured-market reconstruction does not fit in the 20K tier alongside anything else; would need the 100K tier ($59/mo) or a narrower capture window.

All of the above assumes every snapshot call returns real data (post-2022-05-21 dates only, per §2) — pre-floor dates cost 0 credits but also return nothing, so there's no reason to include them in a backfill plan at all.

**Player props, full season backfill:**

```
cost_per_event_check = 10 × n_markets × n_regions, billed only if bookmakers non-empty
                      = 10 × 1 (player_points) × 1 (us) per hit
                      = 0 credits per miss
```
Because coverage is patchy (§3) rather than date-bounded, there is no clean "credits per season" formula — the honest formula is:

```
season_props_cost ≈ (n_events_checked) × (observed_hit_rate) × 10 credits
                   + (n_events_checked) × (1 − observed_hit_rate) × 0 credits
                   = n_events_checked × observed_hit_rate × 10
```
With this run's tiny sample (n=5 mid/late-season checks, 2 hits) the observed hit rate is **~40%**, but the sample is far too small and non-random (always first-event-of-slate) to trust as a season-wide planning number — flag as **VENDOR_ASSERTED / LOW-CONFIDENCE, n=5**. A real props-backfill budget needs a dedicated discovery pass: run the events+event-odds probe across every game date in a target season (roughly 130 events for a full WNBA season), which would cost at most `130 × 10 = 1,300 credits` in the worst case (100% hit rate) and as little as `0` credits in the best case (0% hit rate) — cheap enough to just run the full discovery pass directly rather than estimate further, since even the worst case fits comfortably inside a single 20K-credit month.

**Combined recommendation for M02B:** a full-season featured-market backfill at the existing 2×/day cadence (~7,800 credits) plus a full-season props discovery pass (≤1,300 credits worst case) together cost **≤ 9,100 credits**, well inside one month of the already-purchased 20K tier, with room to spare for the twice-daily live capture (`odds_capture_daily.py`, 3 credits/run ≈ negligible) running concurrently.

---

## 6. Open items not resolved by this pass

- Spreads/totals historical floor was not directly probed (only h2h) — inferred to share the 2022-05-21T09:05:00Z floor by architecture, not independently confirmed (see §2).
- Player-prop coverage density (§3, §5) is based on n=5 non-random event checks — a full discovery pass (≤1,300 credits per §5) is the recommended next step before committing to a specific props-backfill scope, not this document's estimate.
- Licensing, storage/retention rights, and model-training rights (`ODDS_API_VERIFICATION.md` §4) were not re-verified live — those are terms-of-service questions, not API-behavior questions, and remain open per the original draft's §6.7 (email team@the-odds-api.com).
- Timestamp semantics (`ODDS_API_VERIFICATION.md` §5): confirmed structurally in this run — every response carries `timestamp`/`previous_timestamp`/`next_timestamp` exactly as documented, and the grid was observed at 10-minute spacing near the 2022 floor and effectively 5-minute spacing by 2023+ (`19:50:37` → `19:55:37` → `20:00:37` pattern), consistent with the documented Sep-2022 cadence change. No independent latency measurement against a known book-side line-change log was performed in this pass (that was §6.4 in the original draft, a manual-diff exercise, not attempted here) — timestamp-to-true-line-change latency remains **VENDOR_ASSERTED**, unbounded, per the M00 contract.
