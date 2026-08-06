# Capture Upgrade Design — High-Frequency Live Capture, Event-to-Market Linkage, Competitor Projection Archiving

Lane: `market_intelligence` (D023, 2026-08-06) · Role: Capture Upgrade Designer · Status: **DESIGN ONLY — nothing here is implemented**

Scope note: this document is bound by the four user amendments to the market lane
(historical coverage verified not assumed; final-state archive's bounded uses
enumerated, not discarded; capture upgrade is the immediate critical path; every
reaction-time claim carries timestamp-uncertainty and vendor-latency terms). Sections
below cite the amendment they satisfy where relevant.

---

## (a) Current capture cadence and vendor quota cost, as the code exists today

Read directly from the live jobs on the data branch (`C:/Users/jgallagher/wnba-betting-model`,
read-only inputs for this design — not modified here).

| Job | Cadence (as coded/scheduled) | Endpoint | Cost formula (per run) | Stated/observed cost |
|---|---|---|---|---|
| `odds_capture_daily.py` | 2x/day (noon + 6:30pm local), Windows Task Scheduler task `WNBA_OddsCapture` | `/v4/sports/basketball_wnba/odds` (live, slate-wide — one call returns every upcoming game) | `1 credit × markets(3: spreads,totals,h2h) × regions(1: us)` | 3 credits/run → **6 credits/day** flat, independent of slate size |
| `props_capture_daily.py` | 3x/day fixed (10:05, 15:05, 19:35 ET), external scheduler (not created by this script) | `/v4/sports/basketball_wnba/events` (free) then per-event `/events/{id}/odds` | `4 markets × 1 region × N events` per snapshot, N = events inside a rolling 36h window | Script's own comment: "typical slate 2-4 events → 8-16 credits/snapshot, ~25-50/day at 3 snapshots" (verified against `x-requests-last` 2026-07-31) |
| `injury_capture_daily.py` | 2x/day (noon + 6:30pm local) | NBA CDN PDF (primary) / ESPN JSON (fallback) | not Odds-API-metered | n/a |
| `news_capture_daily.py` | 2-4x/day per its own docstring/UA string | ~19 RSS/JSON/HTML feeds + per-team Google News RSS | not Odds-API-metered | n/a |
| `ref_assignments_capture_daily.py` | daily (league posts once ~9am ET; re-runs same-day are idempotent snapshots) | official.nba.com JSON/HTML | not Odds-API-metered | n/a |
| `prospective_pair/run_pair.cmd` (Task Scheduler `WNBA prospective pair`, `task_definition.xml`) | every 15 min, gated by `should_run_base.py` so writes are capped to one per (game, registered decision time) | reads existing `data/odds_capture/live_*.json` — **does not call the vendor API itself** | 0 additional vendor credits | consumes odds captures, doesn't create them |

**Measured monthly reality (from the props script's own docstring):** at 3 snapshots/day,
2-4 events/snapshot, 4 markets, the job already runs ~25-50 credits/day → **~750-1,500
credits/month**, which the script explicitly says "does NOT fit the 500/month free tier;
fine on the paid month." **The free tier is already exceeded by the current cadence,
before any of this design's changes.** That is the correct baseline for the quota math
in (c) — this design is not the thing that first requires a paid plan.

`data/odds_capture/` currently holds 92 `live_*.json` snapshots; `data/props_capture/raw/`
holds 95 event JSONs (counts only, files not read beyond that — per the read-only-headers
constraint on this lane).

---

## (b) Target snapshot ladder + event-driven burst polling

### Fixed ladder (per game, anchored to that game's own tip time — not a global slate time)

```
T-24h  T-8h  T-4h  T-2h  T-60m  T-30m  T-15m  final-pregame
```

"final pregame" = the last scheduled ladder rung before tip, distinct from any capture
made after tip (in-game odds are out of scope for this design — this ladder is a
*pregame* market-timing instrument, matching the possession-lane critical path's own
decision times T-24h/T-8h/T-90m/T-30m in `coverage_audit.py`, extended with three closer
rungs since amendment 3 calls out high-frequency capture specifically).

Each ladder rung is a **per-game** obligation, not a per-slate-run: a slate with games at
7:00pm and 10:00pm ET produces two independent sets of 8 rungs, at different clock times.
This mirrors the existing `should_run_base.py` gate design (game-anchored cutoffs, not
wall-clock cron ticks) rather than reinventing it.

### Event-driven burst polling

Trigger source: `injury_capture_daily.py` and `news_capture_daily.py` already write
first-seen timestamps — `capture_utc` is the row's first appearance in `injury_log.csv`
/ `news_items.csv` (both dedupe on identity: injury log has no explicit dedupe key today,
news log dedupes on `(source, url)`). This design does not change those writers; it reads
their output.

**Wiring (polling-based trigger, not push/webhook — matches the rest of this codebase,
which has no event bus):**

1. A new lightweight watcher (`market_burst_trigger.py`, to be built if this design is
   approved — not part of this deliverable) polls `injury_log.csv` and `news_items.csv`
   every N minutes (propose N=2, cheap since these reads are local CSV, not API calls).
2. It diffs against a persisted "last seen row count" cursor for each file (or
   last-seen `capture_utc`, whichever is coarser at trigger volume) to find newly
   appended rows since its last check.
3. For each new row, resolve `team` (injury) or `teams_mentioned` (news) to that team's
   game on the current slate (via the same team-abbreviation join `coverage_audit.py`
   already does against `data/ref_assignments/assignments_log.csv` +
   `data/masters/master_team.parquet`).
4. If that game's tip is still in the future (a trigger for an already-tipped or
   postponed game fires nothing — matches `should_run_base.py`'s own "cutoff already
   passed" refusal logic), a **burst** is scheduled: a short run of extra ladder-style
   snapshots (propose 3 legs: immediate, +5min, +15min) for *that game only* — odds
   endpoint pulled slate-wide as always (it's not scopeable to one game) but props
   pulled scoped to that game's single event id.
5. Burst legs are deduplicated against the regular ladder: if a scheduled ladder rung
   falls inside a pending burst's window, the burst leg is skipped (the ladder rung
   already captures it) — same "idempotent, at-most-once obligation" discipline as
   `should_run_base.py` / `run_prospective.py` use for the base and arm forecast chains.
6. A burst is a *reason*, not a schedule: this design does not propose a permanently
   running burst poller as a new standalone service unless approved — it can be folded
   into the same wrapper cadence that already exists (`run_pair.cmd`'s 15-minute
   Task Scheduler firing), with the watcher step added as a cheap local-file check that
   only spends vendor credits when it actually finds a new trigger.

**What is explicitly NOT designed here:** true push-based webhooks from injury/news
sources (none of the current sources offer them — RSS/PDF/JSON polling is what's
available, per `news_capture_daily.py`'s own source list), and in-game (post-tip)
capture (out of scope — see "final pregame" above).

---

## (c) Quota math against The Odds API tiers, for a full WNBA slate week

**Tier verification (live-fetched from the-odds-api.com, not assumed — amendment 1's
"verify, don't assume" standard applied here even though historical-endpoint coverage
itself is a different lane's deliverable):**

| Plan | Monthly credits | Price |
|---|---|---|
| Starter | 500 | Free |
| 20K | 20,000 | $30/mo |
| 100K | 100,000 | $59/mo |
| 5M | 5,000,000 | $119/mo |
| 15M | 15,000,000 | $249/mo |

All tiers include the same endpoints/markets/historical access; higher tiers only buy
quota and full bookmaker coverage (Starter is "most," paid is "all"). This design's ladder
and burst polling use **only the live `/odds` and per-event `/events/{id}/odds`
endpoints** — never the historical endpoint, which The Odds API prices at **10 credits
per region per market** (10x live) for anything before "now." Enumerating historical's
bounded legitimate uses (amendment 2) and verifying its point-in-time coverage
(amendment 1) are separate lane deliverables; this design deliberately keeps the capture
upgrade off that 10x-cost endpoint so its quota math stays independent of that
verification's outcome.

### Cost model (formulas, not single numbers — inputs vary day to day; measure after burn-in, don't assume)

- **Odds ladder** (slate-wide, doesn't scale with event count): `8 rungs × 3 markets × 1
  region = 24 credits per game-day`, flat.
- **Props ladder**: `8 rungs × 4 markets × 1 region × E`, where `E` = events inside the
  rolling props window at each rung. The existing script's own observed range is E=2-4
  events/snapshot on a typical slate; using that range: **64-128 credits/game-day**
  (low-to-mid case), up to **224 credits/game-day** at a high-volume E=7 slate (WNBA now
  has 15 teams post-expansion per the team lists in the capture scripts, so a 7-8 game
  day is plausible in a compressed schedule).
- **Burst polling**: `burst_legs(3) × (3 odds-markets + 4 props-markets × events_in_trigger(≈1))
  = 21 credits per burst`. Estimate 1-4 triggering injury/news first-seen events per
  game-day (this is a genuine unknown pending real trigger-volume data — flagged as an
  open input, not assumed): **21-84 credits/game-day**.

### Weekly roll-up (assuming 4-5 game days/week, typical WNBA slate cadence)

| Scenario | Game-days/wk | Odds ladder | Props ladder | Bursts | Weekly total | **Monthly (×4.3)** |
|---|---|---|---|---|---|---|
| Low | 4 | 96 | 256 | 84 | 436 | **~1,875** |
| Mid | 4 | 96 | 512 | 168 | 776 | **~3,340** |
| High | 5 | 120 | 1,120 | 420 | 1,660 | **~7,140** |

### Break-even

- **Free tier (500/mo) is already broken by the current, pre-upgrade cadence** (per (a)
  above — a paid plan is not a consequence of this design, it's already a fact on the
  ground).
- **20K plan ($30/mo) comfortably covers every modeled scenario above**, including the
  high case, with 3-11x headroom. This is the plan this design recommends targeting.
- **100K plan ($59/mo) break-even** would require sustained usage over ~20,000
  credits/month — roughly **2.8x the high-case estimate here**. That would need either
  (i) burst volume far above the 1-4/game-day estimate above, (ii) E consistently above
  7 events/snapshot, or (iii) a design change this document doesn't propose (e.g.
  polling more than 8 rungs, or scoping props snapshots wider than the 36h window).
  **This is a USER GATE**: if real telemetry after a 1-2 week burn-in on the 20K plan
  shows sustained usage above ~15,000/month (75% of quota, leaving headroom for
  slate-volume spikes), that is the trigger to move to 100K — not a decision to make
  from these estimates alone.

**Verification obligation before committing spend:** these are model estimates from
code-as-written cost formulas, not measured production totals — every capture script
already prints `x-requests-used` / `x-requests-remaining` / `x-requests-last` per call
(see `log_credits()` in `props_capture_daily.py`, and the `r.headers.get(...)` line in
`odds_capture_daily.py`). The migration plan in (f) proposes logging those headers into
the new snapshot table specifically so the estimates above get replaced by measured
numbers within the first week of running the ladder, before any tier upgrade decision.

---

## (d) Append-only market-snapshot schema

One row per `(snapshot_id, book, market, outcome)` — i.e. the same outcome-row grain the
existing `capture_log.csv` / `master_props.csv` already use, so downstream readers of the
*new* table can reuse the join logic `coverage_audit.py` and `run_prospective.py` already
have for team/game resolution. This is a **new, additive** table — see (f) for why it does
not touch the existing CSVs.

| Column | Type | Notes |
|---|---|---|
| `snapshot_id` | string (uuid or `sha256(payload)` short-hash) | primary identity of this poll event; stable across retries of the same poll |
| `game_id` | string | official league game_id where known, else the same `PROV-<date>-<away>@<home>` provisional scheme `daily_forecast.py`/`coverage_audit.py` already use — do not invent a second provisional-id convention |
| `book` | string | bookmaker key, as returned by the vendor (`bookmaker_key` today) |
| `market` | string | market key (`spreads`/`totals`/`h2h`/`player_points`/...) |
| `outcome` | string | outcome name/description (team name or player name + Over/Under) |
| `line` | float, nullable | the point/line |
| `price_over` / `price_under` or `price` | int (American odds) | keep the existing over/under-pair shape from `flatten()` in `props_capture_daily.py` for props; single `price` for two-way game markets, matching `odds_capture_daily.py`'s row shape — **do not force both shapes into one column layout**, that's exactly the kind of schema-forcing that produced the "ragged CSV" hazard the v1→v2 migration scripts (`migrate_o14_capture_player_id.py`) already had to work around once |
| `implied_prob` | float | computed at write time from American odds, no vig removal |
| `novig_prob` | float, nullable | computed only when both sides of a two-way market (or the full over/under pair) are present in the *same* snapshot; null otherwise — never interpolated across snapshots |
| `market_status` | enum: `active`/`suspended`/`missing` | `missing` = market absent from this book's response this poll (distinct from `suspended`, which the vendor sometimes marks explicitly — `props_capture_daily.py`'s existing 422-handling and "MISSING/suspended" log line is the precedent to extend, not replace) |
| **Timestamp-uncertainty fields (amendment 4, mandatory on every row):** | | |
| `vendor_ts` | ISO8601 UTC | the vendor's own `last_update` field, verbatim |
| `vendor_ts_semantics` | enum: `book_last_change` / `vendor_ingest_time` / `unknown_unverified` | **must be set to `unknown_unverified` until the vendor's own documentation or support channel confirms which** — do not assume `last_update` means "when the book moved the line"; that assumption is exactly the kind of unverified timing claim D016/P2B ruled the final-state archive out for, and this design will not repeat it on the new table |
| `retrieval_ts` | ISO8601 UTC | this poller's `datetime.now(timezone.utc)` at the moment the HTTP response was received — the one timestamp this design fully controls and can trust |
| `ingestion_ts` | ISO8601 UTC | when the row was written to the snapshot table (may lag `retrieval_ts` under load; usually equal) |
| `max_staleness_bound` | duration (seconds) | upper bound on how old `vendor_ts` could be relative to `retrieval_ts` given the poll_interval at capture — see next field; this is a *bound*, not a point estimate |
| `poll_interval_at_capture` | duration (seconds) | the actual interval this poller was running at when this row was captured (ladder rung spacing, or burst-leg spacing) — required because the ladder's own interval changes (24h down to 15m) so a fixed global constant would misstate the bound at every rung except the one it was tuned for |
| `vendor_latency_note` | free text, nullable | any known/reported vendor-side lag (e.g. rate-limit backoff, retry) affecting this specific row's confidence — populated by the burst/ladder poller when it had to retry, empty otherwise |
| **Chain-integrity fields:** | | |
| `payload_hash` | sha256 of raw response bytes for this event | detects silent overwrites (e) |
| `prev_snapshot_ref` | `snapshot_id` of the immediately preceding snapshot for this same `(game_id, book, market, outcome)` key, or null on first occurrence | makes the table walkable as a chain per amendment-style provenance, same spirit as `alt_model_log.py`'s `base_record_hash` chaining that `run_prospective.py` already relies on |

**Never rewrites existing rows** — same LIVE-DATA RULE the existing capture scripts state
explicitly (`props_capture_daily.py`, `injury_capture_daily.py` docstrings): append-only,
full stop. A correction is a new row with a new `snapshot_id` and `prev_snapshot_ref`
pointing at what it corrects — never an UPDATE.

---

## (e) Missed-poll / silent-overwrite / identifier-change / stale-job detection

All four reuse the existing codebase's own idioms rather than inventing new machinery —
`coverage_audit.py` already does obligation-vs-actual auditing for the forecast chain;
this is the same pattern applied to the capture layer.

**Missed-poll detection**
- Every ladder rung and burst leg is a *registered obligation* the same way
  `CONTRACT_LABELS` register forecast decision times in `coverage_audit.py`. A companion
  `capture_coverage_audit.py` (not built here — a natural extension of the existing
  auditor, following its own `SERVED`/`DUE`/classification pattern) walks the slate the
  same way `build_slate()` does, and for each `(game_id, ladder_rung)` checks whether a
  snapshot row with matching `game_id` and a `retrieval_ts` inside that rung's expected
  window exists. Missing → `missing_job_did_not_run` (operational miss) vs. explained
  absence (game postponed/tip moved, using the existing `tip_moved` /
  `TIP_MOVE_TOLERANCE` logic already in `coverage_audit.py` — do not re-derive that) —
  same honest-decline-vs-operational-miss distinction the forecast auditor already
  enforces.

**Silent-overwrite detection**
- Structurally prevented by (d)'s append-only rule plus `payload_hash`: any writer path
  that would UPDATE instead of INSERT is a bug, not a possible outcome, if the writer is
  built the same way `append_master()` / `append_log()` in the existing capture scripts
  are (open in `"a"` append mode, never `"w"`). As a second layer, a periodic integrity
  check re-hashes each `(game_id, book, market, outcome)` key's most recent row and
  compares to a maintained `prev_snapshot_ref` chain — a broken chain (a row whose
  `prev_snapshot_ref` doesn't match what's actually before it) means something wrote out
  of process and should hard-fail the next scheduled run rather than silently continuing.

**Identifier-change detection**
- Vendor event/game ids, bookmaker keys, and market keys are not guaranteed stable
  (props_capture_daily.py already handles one instance of this — a market key rejected
  with HTTP 422 gets dropped and retried, logged loudly, never silently). Extend that
  precedent: maintain a small allow-list of known `book` and `market` values (seeded from
  current `MARKETS` constants in `odds_capture_daily.py` /`props_capture_daily.py`); any
  new value seen in a response is logged as a `NOTE:` (matching the existing WARNING-style
  stderr convention in every capture script) rather than silently absorbed, so an
  unannounced vendor rename doesn't quietly split one book/market's history into two
  identities inside the snapshot table.
- Game-id stability specifically reuses the provisional-id resolution
  `coverage_audit.py._resolve_provisional()` already implements for the forecast chain —
  the same PROV-id → real-id backfill applies here rather than a second bespoke scheme.

**Stale-job surfacing**
- A capture job that hasn't written *any* row (ladder or burst) in longer than its own
  maximum expected gap (the coarsest ladder rung, 24h, plus a safety margin) is stale.
  This is the same shape as `should_run_base.py`'s reasoning about the 15-minute
  Task Scheduler cadence never having more than a bounded gap between checks — a stale-job
  check is one more auditor query: "when was the last row written for game X's active
  ladder, and is now past `last_row.retrieval_ts + max_expected_gap`?" Surfaced the same
  way the existing scripts surface failure: non-zero exit + explicit stderr line, never a
  silent no-op (matching every existing script's "exit nonzero only when everything
  failed, always print a summary line" convention).

---

## (f) Migration / coexistence with the current daily jobs — never break the running capture

**Principle: additive, not replacing.** The running Task Scheduler jobs
(`WNBA_OddsCapture`, the props/injury/news/ref cadences, and the 15-minute
`WNBA prospective pair` task) keep running exactly as they are. Nothing in this design
proposes deleting, pausing, or rewriting `odds_capture_daily.py`, `props_capture_daily.py`,
`injury_capture_daily.py`, `news_capture_daily.py`, `ref_assignments_capture_daily.py`, or
`prospective_pair/*` — those are explicitly out of ownership for this lane and this role
(read-only inputs per the task charter), and `prospective_pair/` in particular sits on the
possession-lane critical path, which this lane must not touch.

**Coexistence mechanics:**
1. The new ladder/burst poller is a **separate process** with its own Task Scheduler
   entry, following the exact pattern `prospective_pair/task_definition.xml` +
   `run_pair.cmd` already establish (calendar trigger + repetition interval, working
   directory at repo root, non-zero exit on failure, per-run log file under a `runner_logs`-
   style directory). It does not modify or wrap the existing `WNBA_OddsCapture` task.
2. It writes to a **new** table/directory (proposed: `data/market_snapshots/`, schema per
   (d)) — it never touches `data/odds_capture/capture_log.csv` or
   `data/props_capture/master_props.csv`. Those existing artifacts, and everything that
   reads them today (`coverage_audit.py`'s `build_slate()`, `run_prospective.py`'s
   `latest_tips()`), keep working unmodified, unaware the new table exists.
3. It **reuses, not reimplements**, the existing `api_key()` credential loader from
   `odds_capture_daily.py` (already designed to be imported — `props_capture_daily.py`
   already does `from odds_capture_daily import api_key`) — same ODDS_API_KEY env var /
   `.env` file, same credit pool. This means the quota math in (c) must be read as
   *additive* to the existing jobs' usage, which the weekly roll-up already accounts for
   (it doesn't subtract the current 2x/3x-daily cadence — it's a from-scratch model of
   the target-state ladder+burst load, and the existing 2x/3x jobs would logically be
   **retired** once the ladder supersedes their coverage — see step 4).
4. **Cutover, not parallel-forever**: once the ladder+burst poller is verified stable
   (proposed: 1-2 week burn-in per the (c) verification obligation), the existing
   `odds_capture_daily.py` (2x/day) and `props_capture_daily.py` (3x/day fixed times)
   Task Scheduler entries can be disabled — their coverage is a strict subset of the
   8-rung ladder. This is a **user decision**, not something this design executes: until
   that switch is flipped, both run, and the small double-spend (the old jobs' 6-50
   credits/day layered on top of the ladder's cost) is trivial next to the 20K/mo budget
   headroom in (c).
5. `injury_capture_daily.py`, `news_capture_daily.py`, and `ref_assignments_capture_daily.py`
   are **not superseded by anything in this design** — they remain the burst trigger
   *source*, unmodified, forever (or until a separate lane deliverable changes them).

**Rollback:** because the new poller only ever writes to `data/market_snapshots/` and
only ever reads (never writes) `injury_log.csv` / `news_items.csv` / the existing
odds/props outputs, disabling its Task Scheduler entry is a complete, side-effect-free
rollback — no other job's state, schema, or cadence is coupled to it.

---

## Open items for the user (not decidable from this design alone)

1. **Tier commitment**: recommend starting the 20K/$30-mo plan given the mid/high-case
   modeling in (c); confirm actual measured usage via the headers every script already
   logs before considering 100K.
2. **`vendor_ts_semantics` verification**: this design flags it `unknown_unverified` by
   default per amendment 4 — resolving it (vendor docs/support ticket) is prerequisite
   work before any reaction-time claim is built on `vendor_ts`, but is not itself part of
   this capture-upgrade design.
3. **Burst trigger volume**: the 1-4 triggers/game-day estimate in (c) is a placeholder
   pending real measurement from `injury_log.csv`/`news_items.csv` history — this lane's
   read-only access to those logs means the estimate could be tightened before burn-in if
   wanted; flagged here rather than silently presented as firm.
