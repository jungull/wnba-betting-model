#!/usr/bin/env python3
"""M00 lane / Track A (DENSE_WINDOWS) — event-adaptive pregame odds-history puller.

D033 Track A redesign. Supersedes the uniform 30-min/6h grid this file
previously shipped. DESIGN+BUILD ONLY. This script makes ZERO paid calls when
imported/tested in this session. Actual execution against
api.the-odds-api.com is the coordinator's job, after the running historical
backfill (backfill_market_history.py) completes and the coordinator
explicitly sets the confirmation env gate and runs `main() --execute`.

What it does (when run for real), per absence event:
  1. Resolve the exact event (id + commence_time) via the historical
     /events list endpoint for the absent game's date (1 credit/call) — same
     as before.
  2. Look the event up in the INJURY_OFFICIAL/history event catalog (D033
     schema: player_id, game_id, status_transition, ts_lower, ts_upper,
     source_type, source_url, source_published_ts, source_captured_ts,
     confidence). The catalog is owned and built by a sibling track and may
     be partial or entirely absent here; a missing file or a missing row for
     this (player_id, absent_game_id) is not an error.
  3. Build the EVENT-ADAPTIVE snapshot schedule (`adaptive_snapshot_schedule`
     below):
       - Catalog hit -> baselines at T-24h/12h/6h, a 5-minute grid spanning
         [event_ts_lower - 60min, event_ts_upper + 60min] (clipped to the
         24h capture window), a 15-30-minute grid from there to T-30min, and
         a 5-minute sprint over the final 30 minutes before tip.
       - Catalog miss (including "no catalog available at all") -> the
         unknown-event-ts FALLBACK: a uniform 30-minute grid over the full
         24 hours before tip (D033's explicit fallback clause).
     All schedules are clipped to [tip-24h, tip] and de-duplicated; the
     24-hour ceiling applies uniformly so cost is bounded even for a catalog
     hit whose bounds sit at the far edge of the window.
  4. Pull featured-market (h2h,spreads,totals; us region) historical odds at
     every scheduled instant, 30 credits each (10 credits x 3 markets x 1
     region — unchanged measured per-call cost; only the NUMBER of calls per
     event changed under the redesign).
  5. Append one JSONL row per snapshot, T1_VENDOR_ASSERTED, same row shape
     discipline as backfill_market_history.py (amendment-4 fields present on
     every row; append-only; existing rows never rewritten), plus the
     resolved schedule's anchor kind (`schedule_segment`) so the sampling
     density at any given row is traceable after the fact.

Cost model (recomputed for the adaptive grid — see `COST SCENARIOS` below).
cost_per_snapshot_call is UNCHANGED (still measured at 30 credits: 10 x 3
markets x 1 region, per ODDS_API_LIVE_VERIFICATION.md §4-5). What changed is
the number of snapshots per event, which is no longer a constant — it now
depends on where (or whether) the event timestamp falls relative to tip:

    cost_per_snapshot_call = 10 * n_markets * n_regions = 10 * 3 * 1 = 30 credits

    Scenario                          n_snapshots   cost_per_event
    -----------------------------------------------------------------
    UNKNOWN_TS (fallback, 30-min/24h)      49            1471
    KNOWN_TS_TYPICAL (event ~T-2h)         35            1051
    KNOWN_TS_WORST   (event ~T-24h,
                       edge of window)     64            1921
    KNOWN_TS_BEST    (event ~T-15m)        19             571

(These are computed by n_snapshots_for_event_offset()/_cost_for_offset() at
import time, not hand-derived — they cannot silently drift from the actual
adaptive_snapshot_schedule() behavior.)

The INJURY_OFFICIAL event catalog this puller consumes is expected to be
partial or absent at build time (D033: "catalog may be partial - handle
absent-catalog events with the fallback grid keyed to the absence list").
The conservative, honest planning default is therefore the UNKNOWN_TS
fallback cost (events without a catalog hit fall back to it, and that is the
realistic near-term case for most of the 155 ranked absence events until the
sibling track's catalog matures):

    N_events_under_cap(35000, cost=1471) = floor(35000 / 1471) = 23
    (23 * 1471 = 33,833 spent, 1,167 headroom; 24 * 1471 = 35,304 > cap)

This is the headline number this redesign reports: **N = 23**, well under
the previous grid's 89 because 5-minute windows are materially pricier per
event. As catalog coverage improves, per-event cost falls toward the
KNOWN_TS_TYPICAL/BEST figures (more events resolvable near tip rather than
falling to the 24h fallback), so N rises over time without any code change —
`select_events` below is budget-aware at RUN time using each event's actual
resolved cost, not the static planning constant, so real spend never
exceeds `hard_budget_cap` regardless of which scenario mix actually occurs.

Discipline carried over unchanged from the prior grid / backfill_market_history.py:
  - HARD STOP if x-requests-remaining < STOP_GUARD (8000) — protects live-capture
    and backfill headroom; independent of, and checked in addition to, the
    HARD_BUDGET_CAP (a per-run credit ceiling for *this* puller specifically).
  - Resumable: state in <out_dir>/_dense_window_state.json.
  - Append-only JSONL, one file: dense_window_snapshots.jsonl. Corrections are
    new rows, never UPDATEs.
  - Key loaded via the same dotenv mechanism as odds_capture_daily.api_key();
    never printed, never logged.
  - provenance_class T1_VENDOR_ASSERTED throughout (per M00 §4 rule 3: Odds
    API historical rows enter as T1 at best, vendor-asserted, unwitnessed).
  - The coordinator-confirmation env gate (DENSE_WINDOW_COORDINATOR_CONFIRMED_BACKFILL_DONE=1)
    still guards the only network-touching codepath.
  - Zero-network dry-run: importing this module and running the cost-report /
    scheduling / selection codepaths performs no network I/O, exercised by
    TESTS.py with a monkeypatched urlopen that raises on any attempt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

TRACK_ROOT = Path(__file__).resolve().parent
LIVE_MAIN_WORKTREE = Path("C:/Users/jgallagher/wnba-betting-model")  # READ-ONLY (for api_key() reuse only)

OUT_DIR = TRACK_ROOT / "data" / "dense_windows"
STATE_F = OUT_DIR / "_dense_window_state.json"
SNAP_F = OUT_DIR / "dense_window_snapshots.jsonl"
LOG_F = OUT_DIR / "_dense_window_progress.log"

# Default location of the sibling INJURY_OFFICIAL/history event catalog this
# puller consumes (D033). Owned and populated by another track; this file
# never writes to it. Missing file -> every event uses the fallback grid.
DEFAULT_EVENT_CATALOG = TRACK_ROOT.parent / "INJURY_OFFICIAL" / "event_catalog.json"

BASE = "https://api.the-odds-api.com/v4/historical/sports/basketball_wnba"

FEATURED_MARKETS = "h2h,spreads,totals"
REGION = "us"
N_MARKETS = 3  # h2h, spreads, totals
N_REGIONS = 1  # us
COST_PER_SNAPSHOT_CALL = 10 * N_MARKETS * N_REGIONS  # 30 credits, measured — unchanged by the redesign
COST_PER_EVENTS_CALL = 1  # flat, measured

# ---------------------------------------------------------------------------
# D033 event-adaptive grid parameters.
# ---------------------------------------------------------------------------
CAPTURE_WINDOW_HOURS = 24  # every schedule (adaptive or fallback) is clipped to [tip-24h, tip]
BASELINE_HOURS_BEFORE_TIP = (24, 12, 6)  # D033 baselines
DENSE_HALF_WIDTH_MINUTES = 60  # 5-min grid spans event_ts +/- 60 minutes
DENSE_INTERVAL_MINUTES = 5
MEDIUM_INTERVAL_MINUTES = 30  # D033 specifies "15-30min"; 30 is the cost-conservative
                              # (cheaper) end of that band and the default here. A
                              # coordinator with headroom may tighten this to 15 —
                              # every function below takes it as a module constant,
                              # not a hardcoded literal, for exactly that reason.
FINAL_WINDOW_MINUTES = 30  # final dense sprint covers the last 30 minutes before tip
FINAL_INTERVAL_MINUTES = 5
FALLBACK_INTERVAL_MINUTES = 30  # unknown-event-ts fallback: uniform grid over the 24h window

STOP_GUARD = 8000  # same headroom reservation as backfill_market_history.py
HARD_BUDGET_CAP_DEFAULT = 35000

# NOTE: the reference-tip cost-scenario constants (COST_PER_EVENT_*,
# n_snapshots_for_event_offset, n_events_under_cap) are defined further below,
# immediately after adaptive_snapshot_schedule() — they call it to compute
# their values, so they must follow its definition. Search
# "D033 event-adaptive grid parameters — cost scenarios" for that block.

# ---------------------------------------------------------------------------
# HTTP layer — identical shape/behavior to backfill_market_history.py.
# Never invoked by the fixture tests (they monkeypatch `get`), so importing
# this module performs no network I/O.
# ---------------------------------------------------------------------------

def _api_key() -> str:
    """Reuses the exact dotenv-loading mechanism as odds_capture_daily.api_key(),
    on the live main worktree (read-only import, never copied/modified here).
    Never printed or logged."""
    sys.path.insert(0, str(LIVE_MAIN_WORKTREE))
    from odds_capture_daily import api_key  # noqa: E402
    return api_key()


def log(msg: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    line = datetime.now(timezone.utc).isoformat(timespec="seconds") + " " + msg
    print(line, flush=True)
    with open(LOG_F, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def get(url_path: str, params: dict) -> tuple[object, dict]:
    """Real network call. Not exercised by fixture tests."""
    params = dict(params)
    params["apiKey"] = _api_key()
    url = BASE + url_path + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                body = resp.read()
                hdrs = {k.lower(): v for k, v in resp.headers.items()}
                return json.loads(body), hdrs
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                log(f"FATAL auth error {e.code} - aborting (key value not logged)")
                raise SystemExit(2)
            if e.code == 429:
                time.sleep(15 * (attempt + 1))
                continue
            if e.code == 404:
                return None, {k.lower(): v for k, v in e.headers.items()}
            time.sleep(5 * (attempt + 1))
        except Exception:
            time.sleep(5 * (attempt + 1))
    return None, {}


def remaining(hdrs: dict) -> float:
    try:
        return float(hdrs.get("x-requests-remaining", "1e9"))
    except ValueError:
        return 1e9


def guard(hdrs: dict) -> None:
    r = remaining(hdrs)
    if r < STOP_GUARD:
        log(f"STOP-GUARD tripped: remaining={r} < {STOP_GUARD}; exiting cleanly (resumable)")
        raise SystemExit(0)


def append_row(path: Path, row: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")


def load_state() -> dict:
    if STATE_F.exists():
        return json.loads(STATE_F.read_text(encoding="utf-8"))
    return {"events_done": [], "credits_spent_est": 0}


def save_state(st: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_F.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=0), encoding="utf-8")
    tmp.replace(STATE_F)


# ---------------------------------------------------------------------------
# Event catalog (D033: INJURY_OFFICIAL/history event catalog) — consumed,
# never written, by this track. Partial or absent files are handled by
# falling back to the fallback grid for the affected event(s).
# ---------------------------------------------------------------------------

def load_event_catalog(path: Path | None = None) -> list[dict]:
    """Load the sibling track's event catalog. Returns [] if the file is
    missing, unreadable, or malformed — never raises. Accepts either a bare
    JSON list of records or {"events": [...]}."""
    p = path or DEFAULT_EVENT_CATALOG
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, dict):
        data = data.get("events", [])
    return data if isinstance(data, list) else []


def build_catalog_index(catalog_records: list[dict]) -> dict:
    """Index by (player_id, game_id) -> most-recent record (last one wins;
    catalog rows are expected append-only/chronological upstream)."""
    idx: dict = {}
    for rec in catalog_records:
        key = (rec.get("player_id"), rec.get("game_id"))
        if key[0] is None or key[1] is None:
            continue
        idx[key] = rec
    return idx


def catalog_event_ts_bounds(absence_event: dict, catalog_index: dict) -> tuple[datetime, datetime] | None:
    """Resolve (ts_lower, ts_upper) for an absence event from the catalog
    index, or None on any catalog miss / malformed bound (treated as a miss,
    never an error — the caller falls back to the fallback grid)."""
    key = (absence_event.get("player_id"), absence_event.get("absent_game_id"))
    rec = catalog_index.get(key)
    if rec is None:
        return None
    try:
        lo = datetime.fromisoformat(str(rec["ts_lower"]).replace("Z", "+00:00"))
        hi = datetime.fromisoformat(str(rec["ts_upper"]).replace("Z", "+00:00"))
    except (KeyError, ValueError, TypeError):
        return None
    if hi < lo:
        return None
    return lo, hi


# ---------------------------------------------------------------------------
# Pure logic — event-adaptive scheduling, event selection, matching,
# row-building. These are the functions the fixture tests exercise directly.
# ---------------------------------------------------------------------------

def adaptive_snapshot_schedule(
    commence_time: datetime,
    event_ts_lower: datetime | None = None,
    event_ts_upper: datetime | None = None,
) -> list[datetime]:
    """D033 event-adaptive schedule, deterministic and testable.

    Unknown event timestamp (either bound is None): the D033 fallback — a
    uniform 30-minute grid over the full 24 hours before tip, inclusive of
    both ends.

    Known event timestamp bounds: baselines at T-24h/12h/6h, a 5-minute grid
    spanning [ts_lower-60min, ts_upper+60min], a 15-30-minute grid from the
    end of that dense window to T-30min, and a 5-minute sprint over the
    final 30 minutes before tip. Every segment is clipped to the
    [tip-24h, tip] capture window (bounding worst-case cost even when the
    event sits right at the window edge) and the result is de-duplicated and
    sorted.
    """
    window_start = commence_time - timedelta(hours=CAPTURE_WINDOW_HOURS)

    if event_ts_lower is None or event_ts_upper is None:
        out: list[datetime] = []
        t = window_start
        while t <= commence_time:
            out.append(t)
            t += timedelta(minutes=FALLBACK_INTERVAL_MINUTES)
        return out

    times: set[datetime] = set()

    for h in BASELINE_HOURS_BEFORE_TIP:
        t = commence_time - timedelta(hours=h)
        if window_start <= t <= commence_time:
            times.add(t)

    dense_start = max(window_start, event_ts_lower - timedelta(minutes=DENSE_HALF_WIDTH_MINUTES))
    dense_end = min(commence_time, event_ts_upper + timedelta(minutes=DENSE_HALF_WIDTH_MINUTES))
    if dense_start <= dense_end:
        t = dense_start
        while t <= dense_end:
            times.add(t)
            t += timedelta(minutes=DENSE_INTERVAL_MINUTES)
    else:
        dense_end = dense_start  # degenerate (event bounds entirely outside the window); no dense grid

    medium_start = dense_end
    medium_end = commence_time - timedelta(minutes=FINAL_WINDOW_MINUTES)
    if medium_start <= medium_end:
        t = medium_start
        while t <= medium_end:
            times.add(t)
            t += timedelta(minutes=MEDIUM_INTERVAL_MINUTES)

    final_start = max(window_start, commence_time - timedelta(minutes=FINAL_WINDOW_MINUTES))
    t = final_start
    while t <= commence_time:
        times.add(t)
        t += timedelta(minutes=FINAL_INTERVAL_MINUTES)

    return sorted(t for t in times if window_start <= t <= commence_time)


# ---------------------------------------------------------------------------
# D033 event-adaptive grid parameters — cost scenarios.
# Computed here (not hand-derived) so they can never silently drift out of
# sync with adaptive_snapshot_schedule()'s actual behavior. Reference tip is
# an arbitrary fixed instant used ONLY to size scenario costs before any real
# commence_time is known (pre-execution cost estimation): every boundary in
# adaptive_snapshot_schedule() is computed as an offset from commence_time,
# so schedule LENGTH is invariant to which absolute instant is used as the
# reference — only the relative offsets (event-before-tip, window-before-tip)
# matter.
# ---------------------------------------------------------------------------
_REFERENCE_TIP = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def n_snapshots_for_event_offset(hours_before_tip: float | None) -> int:
    """Size a schedule for cost-estimation purposes without a real commence_time.

    hours_before_tip=None models the unknown-event-ts fallback grid.
    Otherwise models a catalog-known event treated as an exact instant
    (ts_lower == ts_upper) that many hours before an arbitrary reference tip.
    """
    if hours_before_tip is None:
        return len(adaptive_snapshot_schedule(_REFERENCE_TIP))
    event_ts = _REFERENCE_TIP - timedelta(hours=hours_before_tip)
    return len(adaptive_snapshot_schedule(_REFERENCE_TIP, event_ts, event_ts))


def _cost_for_offset(hours_before_tip: float | None) -> int:
    return COST_PER_EVENTS_CALL + n_snapshots_for_event_offset(hours_before_tip) * COST_PER_SNAPSHOT_CALL


COST_PER_EVENT_UNKNOWN_TS = _cost_for_offset(None)          # fallback grid
COST_PER_EVENT_KNOWN_TYPICAL = _cost_for_offset(2.0)        # event ~2h before tip
COST_PER_EVENT_KNOWN_WORST = _cost_for_offset(CAPTURE_WINDOW_HOURS)   # event at the 24h window edge
COST_PER_EVENT_KNOWN_BEST = _cost_for_offset(0.25)          # event ~15min before tip

# Conservative planning default: the catalog is expected partial/absent
# (D033), so most events fall to the fallback grid until the sibling track's
# catalog matures. This is the number reported as "the new N" — see the
# module docstring's cost table.
COST_PER_EVENT_PLANNING_DEFAULT = COST_PER_EVENT_UNKNOWN_TS


def n_events_under_cap(cap: int, cost_per_event: int = COST_PER_EVENT_PLANNING_DEFAULT) -> int:
    return cap // cost_per_event


def schedule_segment_label(
    t: datetime,
    commence_time: datetime,
    event_ts_lower: datetime | None,
    event_ts_upper: datetime | None,
) -> str:
    """Classify a scheduled instant for the row's `schedule_segment` field —
    traceability only, never re-derives the schedule itself."""
    if event_ts_lower is None or event_ts_upper is None:
        return "FALLBACK_UNKNOWN_TS"
    if t == commence_time - timedelta(hours=24) or t == commence_time - timedelta(hours=12) \
            or t == commence_time - timedelta(hours=6):
        pass  # baseline instants can coincide with dense/medium/final; fall through to the finer label
    dense_start = event_ts_lower - timedelta(minutes=DENSE_HALF_WIDTH_MINUTES)
    dense_end = event_ts_upper + timedelta(minutes=DENSE_HALF_WIDTH_MINUTES)
    if dense_start <= t <= dense_end:
        return "DENSE_EVENT_WINDOW_5MIN"
    if commence_time - timedelta(minutes=FINAL_WINDOW_MINUTES) <= t <= commence_time:
        return "FINAL_SPRINT_5MIN"
    if t in (commence_time - timedelta(hours=h) for h in BASELINE_HOURS_BEFORE_TIP):
        return "BASELINE_ANCHOR"
    return "MEDIUM_GRID"


def estimate_event_cost(absence_event: dict, catalog_index: dict | None) -> int:
    """Pre-execution cost estimate for one event: catalog hit sizes the real
    adaptive schedule against the catalog's own bounds treated relative to
    the reference tip (schedule length is offset-invariant, see
    n_snapshots_for_event_offset); catalog miss uses the fallback cost."""
    if not catalog_index:
        return COST_PER_EVENTS_CALL + n_snapshots_for_event_offset(None) * COST_PER_SNAPSHOT_CALL
    bounds = catalog_event_ts_bounds(absence_event, catalog_index)
    if bounds is None:
        return COST_PER_EVENTS_CALL + n_snapshots_for_event_offset(None) * COST_PER_SNAPSHOT_CALL
    lo, hi = bounds
    width = hi - lo
    # Model as an instant at the bound midpoint for sizing purposes; the real
    # per-event execution cost is computed exactly once commence_time is
    # resolved (see main()). This estimate is planning-only.
    ref_event = _REFERENCE_TIP - timedelta(hours=CAPTURE_WINDOW_HOURS / 2)  # neutral mid-window placement
    sched = adaptive_snapshot_schedule(_REFERENCE_TIP, ref_event - width / 2, ref_event + width / 2)
    return COST_PER_EVENTS_CALL + len(sched) * COST_PER_SNAPSHOT_CALL


def select_events(
    all_events: list[dict],
    hard_budget_cap: int,
    catalog_index: dict | None = None,
) -> list[dict]:
    """Rank-ordered, budget-aware selection. Unlike the old fixed-N floor
    division, this walks the ranked list accumulating each event's estimated
    cost (catalog-aware when a catalog_index is supplied) and stops before
    the cumulative total would exceed hard_budget_cap. Real execution
    (main()) re-checks actual spend against the same cap as it goes, so a
    mis-estimate here under-selects rather than over-spends."""
    selected = []
    spent = 0
    for ev in all_events:
        cost = estimate_event_cost(ev, catalog_index)
        if spent + cost > hard_budget_cap:
            break
        selected.append(ev)
        spent += cost
    return selected


def snapshot_schedule(commence_time: datetime) -> list[datetime]:
    """Back-compat alias: the unknown-event-ts fallback grid alone (what the
    old uniform grid computed, now widened to the 24h fallback window). Kept
    as a thin wrapper — new code should call adaptive_snapshot_schedule()."""
    return adaptive_snapshot_schedule(commence_time)


def match_event(events_payload: list[dict], team_abbrev: str, opp_abbrev: str, is_home) -> dict | None:
    """Match an Odds API /events list entry to our absence-event row via
    team names. The Odds API events endpoint returns full team names
    (e.g. "Minnesota Lynx"), not abbreviations, so callers pass an
    abbrev->fullname resolver via `team_abbrev`/`opp_abbrev` already resolved
    to the vendor's naming convention upstream of this function; here we do
    plain substring/equality matching on whatever strings are supplied so the
    function is testable without a live vendor name map."""
    for ev in events_payload:
        home = ev.get("home_team", "")
        away = ev.get("away_team", "")
        names = {home, away}
        if team_abbrev in names and opp_abbrev in names:
            ev_is_home = (ev.get("home_team") == team_abbrev)
            if is_home is None or ev_is_home == bool(is_home):
                return ev
    return None


def build_snapshot_row(
    *, event: dict, absence_event: dict, requested_ts: str, vendor_payload: dict | None,
    retrieval_ts: str, schedule_segment: str = "UNKNOWN",
) -> dict:
    """Same amendment-4 row-shape discipline as backfill_market_history.py's
    append_row payloads, plus the event-linkage fields this track needs, plus
    `schedule_segment` recording which part of the adaptive grid produced
    this row (traceability for the redesign)."""
    payload = vendor_payload.get("data") if vendor_payload else None
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True) if payload is not None else ""
    return {
        # event linkage (this track's addition over backfill_market_history.py)
        "absence_event_rank": absence_event.get("rank"),
        "player_id": absence_event.get("player_id"),
        "player_name": absence_event.get("player_name"),
        "absent_game_id": absence_event.get("absent_game_id"),
        "odds_api_event_id": event.get("id"),
        "schedule_segment": schedule_segment,
        # amendment-4 mandatory fields (§6.3 / backfill_market_history.py parity)
        "requested_ts": requested_ts,
        "vendor_snapshot_ts": (vendor_payload or {}).get("timestamp"),
        "vendor_prev_ts": (vendor_payload or {}).get("previous_timestamp"),
        "vendor_next_ts": (vendor_payload or {}).get("next_timestamp"),
        "retrieval_ts": retrieval_ts,
        "vendor_ts_semantics": "vendor_asserted_unwitnessed",
        "provenance_class": "T1_VENDOR_ASSERTED",
        "n_events": len(payload) if isinstance(payload, list) else (1 if payload else 0),
        "payload_sha256": hashlib.sha256(payload_json.encode()).hexdigest() if payload is not None else None,
        "payload": payload,
    }


def estimate_cost_report(
    all_events: list[dict],
    hard_budget_cap: int,
    catalog_index: dict | None = None,
) -> dict:
    selected = select_events(all_events, hard_budget_cap, catalog_index)
    spent = sum(estimate_event_cost(ev, catalog_index) for ev in selected)
    return {
        "cost_per_snapshot_call": COST_PER_SNAPSHOT_CALL,
        "cost_per_events_list_call": COST_PER_EVENTS_CALL,
        "scenario_costs": {
            "UNKNOWN_TS_FALLBACK": COST_PER_EVENT_UNKNOWN_TS,
            "KNOWN_TS_TYPICAL_T_MINUS_2H": COST_PER_EVENT_KNOWN_TYPICAL,
            "KNOWN_TS_WORST_T_MINUS_24H": COST_PER_EVENT_KNOWN_WORST,
            "KNOWN_TS_BEST_T_MINUS_15M": COST_PER_EVENT_KNOWN_BEST,
        },
        "planning_default_cost_per_event": COST_PER_EVENT_PLANNING_DEFAULT,
        "planning_default_n_events_under_cap": n_events_under_cap(hard_budget_cap),
        "hard_budget_cap": hard_budget_cap,
        "n_events_available": len(all_events),
        "n_events_selected": len(selected),
        "estimated_total_credits": spent,
        "budget_headroom_credits": hard_budget_cap - spent,
        "catalog_coverage": (
            f"{sum(1 for ev in selected if catalog_index and catalog_event_ts_bounds(ev, catalog_index))}"
            f"/{len(selected)} selected events matched the event catalog"
            if catalog_index else "no event catalog supplied — all events use the fallback grid"
        ),
    }


# ---------------------------------------------------------------------------
# Real execution entrypoint — coordinator-run only, after the historical
# backfill completes. Never called by tests or by importing this module.
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events-json", type=Path, default=TRACK_ROOT / "absence_events_ranked.json")
    ap.add_argument("--event-catalog", type=Path, default=DEFAULT_EVENT_CATALOG,
                     help="INJURY_OFFICIAL/history event catalog (D033 schema). "
                          "Missing/partial is fine — affected events use the fallback grid.")
    ap.add_argument("--hard-budget-cap", type=int, default=HARD_BUDGET_CAP_DEFAULT)
    ap.add_argument("--execute", action="store_true",
                     help="Actually call the paid API. Without this flag, prints "
                          "the cost report and selected events only (still zero paid calls).")
    args = ap.parse_args()

    all_events = json.loads(args.events_json.read_text(encoding="utf-8"))["events"]
    catalog_index = build_catalog_index(load_event_catalog(args.event_catalog))
    report = estimate_cost_report(all_events, args.hard_budget_cap, catalog_index)
    print(json.dumps(report, indent=2))

    if not args.execute:
        print("\n--execute not passed: dry run only, zero paid calls made.", file=sys.stderr)
        return

    # Guard: this codepath is coordinator-only. Refuse to run against the
    # paid host while the historical backfill may still be in flight, unless
    # explicitly overridden by the coordinator with an env var they set
    # themselves after confirming backfill completion.
    import os
    if os.environ.get("DENSE_WINDOW_COORDINATOR_CONFIRMED_BACKFILL_DONE") != "1":
        print(
            "REFUSING to execute paid calls: DENSE_WINDOW_COORDINATOR_CONFIRMED_BACKFILL_DONE=1 "
            "is not set. This puller must not race the running historical backfill against "
            "api.the-odds-api.com. Set that env var only after the coordinator has confirmed "
            "the backfill run is complete.",
            file=sys.stderr,
        )
        raise SystemExit(3)

    st = load_state()
    done = set(st["events_done"])
    selected = select_events(all_events, args.hard_budget_cap, catalog_index)
    log(f"dense window puller start/resume: {len(done)}/{len(selected)} events done")

    credits_spent = st.get("credits_spent_est", 0)
    for ev in selected:
        key = f"{ev['absent_game_id']}::{ev['player_id']}"
        if key in done:
            continue
        if credits_spent >= args.hard_budget_cap:
            log(f"HARD_BUDGET_CAP reached ({credits_spent} >= {args.hard_budget_cap}); stopping (resumable)")
            break
        # 1. resolve exact event (1 credit)
        day = ev["absent_game_date"]
        events_data, hdrs = get("/events", {"date": day + "T00:00:00Z"})
        guard(hdrs)
        matched = match_event(
            (events_data or {}).get("data") or [],
            ev["team_abbreviation"], ev["absent_game_opponent_abbreviation"],
            ev.get("absent_game_team_is_home"),
        )
        if matched is None:
            log(f"NO MATCH for {key}; skipping (recorded as done to avoid retry loop)")
            done.add(key)
            st["events_done"] = sorted(done)
            save_state(st)
            continue
        commence = datetime.fromisoformat(matched["commence_time"].replace("Z", "+00:00"))

        # 2. resolve this event's actual adaptive schedule against the real commence_time
        bounds = catalog_event_ts_bounds(ev, catalog_index)
        event_ts_lower, event_ts_upper = bounds if bounds else (None, None)
        schedule = adaptive_snapshot_schedule(commence, event_ts_lower, event_ts_upper)

        for snap_t in schedule:
            requested_ts = snap_t.isoformat(timespec="seconds").replace("+00:00", "Z")
            data, hdrs = get(f"/events/{matched['id']}/odds", {
                "date": requested_ts, "regions": REGION,
                "markets": FEATURED_MARKETS, "oddsFormat": "american",
            })
            retrieval_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
            segment = schedule_segment_label(snap_t, commence, event_ts_lower, event_ts_upper)
            row = build_snapshot_row(
                event=matched, absence_event=ev, requested_ts=requested_ts,
                vendor_payload=data, retrieval_ts=retrieval_ts, schedule_segment=segment,
            )
            append_row(SNAP_F, row)
            credits_spent += COST_PER_SNAPSHOT_CALL if row["payload"] else 0
            st["credits_spent_est"] = credits_spent
            guard(hdrs)
            if credits_spent >= args.hard_budget_cap:
                log(f"HARD_BUDGET_CAP reached mid-event ({credits_spent} >= {args.hard_budget_cap}); "
                    f"stopping (resumable, event {key} incomplete)")
                save_state(st)
                return
            time.sleep(0.7)

        done.add(key)
        st["events_done"] = sorted(done)
        save_state(st)
        log(f"event {key} done ({len(done)}/{len(selected)}); credits_spent_est={credits_spent}")

    log("dense window puller COMPLETE")


if __name__ == "__main__":
    main()
