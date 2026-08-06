#!/usr/bin/env python3
"""M00 lane / Track A (DENSE_WINDOWS) — dense pregame odds-history puller.

DESIGN+BUILD ONLY. This script makes ZERO paid calls when imported/tested in
this session. Actual execution against api.the-odds-api.com is the
coordinator's job, after the running historical backfill (backfill_market_history.py)
completes and the coordinator explicitly runs `main()` / the CLI entrypoint.

What it does (when run for real):
  For the top-N ranked absence events (build_absence_events.py output), under
  a HARD_BUDGET_CAP credits ceiling:
    1. Resolve the exact event (id + commence_time) via the historical
       /events list endpoint for the absent game's date (1 credit/call).
    2. Pull featured-market (h2h,spreads,totals; us region) historical odds
       snapshots every 30 minutes from T-6h to tip (inclusive), 30 credits
       each per the measured cost model in W1_DRAFTS/ODDS_API_LIVE_VERIFICATION.md
       §4-5 (10 credits x 3 markets x 1 region).
    3. Append one JSONL row per snapshot, T1_VENDOR_ASSERTED, same row shape
       discipline as backfill_market_history.py (amendment-4 fields present
       on every row; append-only; existing rows never rewritten).

Cost model (measured, not estimated — see ODDS_API_LIVE_VERIFICATION.md):
    cost_per_snapshot_call = 10 * n_markets * n_regions = 10 * 3 * 1 = 30 credits
    n_snapshots_per_event  = T-6h to tip inclusive, every 30 min = 13
    cost_per_event = 1 (events-list call) + 13 * 30 = 391 credits

    N_events_under_cap(cap) = floor(cap / cost_per_event)
    at HARD_BUDGET_CAP=35000: N = floor(35000 / 391) = 89  (89*391=34,799 spent, 201 headroom)

Discipline carried over from backfill_market_history.py:
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

BASE = "https://api.the-odds-api.com/v4/historical/sports/basketball_wnba"

FEATURED_MARKETS = "h2h,spreads,totals"
REGION = "us"
N_MARKETS = 3  # h2h, spreads, totals
N_REGIONS = 1  # us
COST_PER_SNAPSHOT_CALL = 10 * N_MARKETS * N_REGIONS  # 30 credits, measured
COST_PER_EVENTS_CALL = 1  # flat, measured

WINDOW_HOURS_BEFORE_TIP = 6
SNAPSHOT_INTERVAL_MINUTES = 30
N_SNAPSHOTS_PER_EVENT = (WINDOW_HOURS_BEFORE_TIP * 60) // SNAPSHOT_INTERVAL_MINUTES + 1  # 13, inclusive of tip

COST_PER_EVENT = COST_PER_EVENTS_CALL + N_SNAPSHOTS_PER_EVENT * COST_PER_SNAPSHOT_CALL  # 391

STOP_GUARD = 8000  # same headroom reservation as backfill_market_history.py
HARD_BUDGET_CAP_DEFAULT = 35000


def n_events_under_cap(cap: int, cost_per_event: int = COST_PER_EVENT) -> int:
    return cap // cost_per_event


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
# Pure logic — event selection, snapshot scheduling, matching, row-building.
# These are the functions the fixture tests exercise directly.
# ---------------------------------------------------------------------------

def select_events(all_events: list[dict], hard_budget_cap: int) -> list[dict]:
    """Top-N ranked events (already rank-sorted by build_absence_events.py)
    that fit under hard_budget_cap at COST_PER_EVENT each."""
    n = n_events_under_cap(hard_budget_cap)
    return all_events[:n]


def snapshot_schedule(commence_time: datetime) -> list[datetime]:
    """T-6h to tip inclusive, every 30 minutes. Deterministic, testable."""
    start = commence_time - timedelta(hours=WINDOW_HOURS_BEFORE_TIP)
    out = []
    t = start
    while t <= commence_time:
        out.append(t)
        t += timedelta(minutes=SNAPSHOT_INTERVAL_MINUTES)
    return out


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
    retrieval_ts: str,
) -> dict:
    """Same amendment-4 row-shape discipline as backfill_market_history.py's
    append_row payloads, plus the event-linkage fields this track needs."""
    payload = vendor_payload.get("data") if vendor_payload else None
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True) if payload is not None else ""
    return {
        # event linkage (this track's addition over backfill_market_history.py)
        "absence_event_rank": absence_event.get("rank"),
        "player_id": absence_event.get("player_id"),
        "player_name": absence_event.get("player_name"),
        "absent_game_id": absence_event.get("absent_game_id"),
        "odds_api_event_id": event.get("id"),
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


def estimate_cost_report(all_events: list[dict], hard_budget_cap: int) -> dict:
    selected = select_events(all_events, hard_budget_cap)
    return {
        "cost_per_snapshot_call": COST_PER_SNAPSHOT_CALL,
        "n_snapshots_per_event": N_SNAPSHOTS_PER_EVENT,
        "cost_per_events_list_call": COST_PER_EVENTS_CALL,
        "cost_per_event": COST_PER_EVENT,
        "hard_budget_cap": hard_budget_cap,
        "n_events_available": len(all_events),
        "n_events_selected": len(selected),
        "estimated_total_credits": len(selected) * COST_PER_EVENT,
        "budget_headroom_credits": hard_budget_cap - len(selected) * COST_PER_EVENT,
    }


# ---------------------------------------------------------------------------
# Real execution entrypoint — coordinator-run only, after the historical
# backfill completes. Never called by tests or by importing this module.
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events-json", type=Path, default=TRACK_ROOT / "absence_events_ranked.json")
    ap.add_argument("--hard-budget-cap", type=int, default=HARD_BUDGET_CAP_DEFAULT)
    ap.add_argument("--execute", action="store_true",
                     help="Actually call the paid API. Without this flag, prints "
                          "the cost report and selected events only (still zero paid calls).")
    args = ap.parse_args()

    all_events = json.loads(args.events_json.read_text(encoding="utf-8"))["events"]
    report = estimate_cost_report(all_events, args.hard_budget_cap)
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
    selected = select_events(all_events, args.hard_budget_cap)
    log(f"dense window puller start/resume: {len(done)}/{len(selected)} events done")

    for ev in selected:
        key = f"{ev['absent_game_id']}::{ev['player_id']}"
        if key in done:
            continue
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

        # 2. dense snapshots, T-6h to tip, 30 min grid
        for snap_t in snapshot_schedule(commence):
            requested_ts = snap_t.isoformat(timespec="seconds").replace("+00:00", "Z")
            data, hdrs = get(f"/events/{matched['id']}/odds", {
                "date": requested_ts, "regions": REGION,
                "markets": FEATURED_MARKETS, "oddsFormat": "american",
            })
            retrieval_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
            row = build_snapshot_row(
                event=matched, absence_event=ev, requested_ts=requested_ts,
                vendor_payload=data, retrieval_ts=retrieval_ts,
            )
            append_row(SNAP_F, row)
            st["credits_spent_est"] = st.get("credits_spent_est", 0) + (
                COST_PER_SNAPSHOT_CALL if row["payload"] else 0
            )
            guard(hdrs)
            time.sleep(0.7)

        done.add(key)
        st["events_done"] = sorted(done)
        save_state(st)
        log(f"event {key} done ({len(done)}/{len(selected)}); credits_spent_est={st['credits_spent_est']}")

    log("dense window puller COMPLETE")


if __name__ == "__main__":
    main()
