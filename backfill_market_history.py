#!/usr/bin/env python3
"""Historical odds backfill - user-authorized D028 (2026-08-06).

Phase 1: featured markets (h2h,spreads,totals), 2 snapshots/day, 2022-05-21 -> 2026-07-30.
Phase 2: player_points discovery per game day found in phase 1 (empty responses are free).

Discipline:
  - HARD STOP if x-requests-remaining < STOP_GUARD (protects live-capture headroom).
  - Resumable: state in data/market_snapshots/historical/_backfill_state.json.
  - Every row carries amendment-4 fields; provenance is T1_VENDOR_ASSERTED (the vendor's
    snapshot timestamps were never witnessed by our capture) per D027/D028.
  - Existing rows never rewritten: append-only JSONL, one file per phase.
  - Key loaded via the same dotenv mechanism as odds_capture_daily; never printed.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from odds_capture_daily import api_key  # noqa: E402  (dotenv loader, reused verbatim)

OUT = ROOT / "data" / "market_snapshots" / "historical"
OUT.mkdir(parents=True, exist_ok=True)
STATE_F = OUT / "_backfill_state.json"
FEAT_F = OUT / "featured_backfill.jsonl"
PROPS_F = OUT / "props_discovery.jsonl"
LOG_F = OUT / "_backfill_progress.log"

STOP_GUARD = 8000  # raised from 4000 at the D029 100K-tier bump: reserves a full month of worst-case ladder + daily-job burn
SNAP_TIMES = ("16:00:00Z", "23:30:00Z")
SEASONS = [
    ("2022-05-21", "2022-09-20"),
    ("2023-05-15", "2023-10-20"),
    ("2024-05-10", "2024-10-25"),
    ("2025-05-10", "2025-10-15"),
    ("2026-05-01", "2026-07-30"),
]
BASE = "https://api.the-odds-api.com/v4/historical/sports/basketball_wnba"


def log(msg: str) -> None:
    line = datetime.now(timezone.utc).isoformat(timespec="seconds") + " " + msg
    print(line, flush=True)
    with open(LOG_F, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def get(url_path: str, params: dict) -> tuple[object, dict]:
    params = dict(params)
    params["apiKey"] = api_key()
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
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")


def load_state() -> dict:
    if STATE_F.exists():
        return json.loads(STATE_F.read_text(encoding="utf-8"))
    return {"phase1_done": [], "phase1_game_days": [], "phase2_done": [], "credits_spent_est": 0}


def save_state(st: dict) -> None:
    tmp = STATE_F.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=0), encoding="utf-8")
    tmp.replace(STATE_F)


def day_range(a: str, b: str):
    d0, d1 = date.fromisoformat(a), date.fromisoformat(b)
    while d0 <= d1:
        yield d0.isoformat()
        d0 += timedelta(days=1)


def main() -> None:
    st = load_state()
    done = set(st["phase1_done"])
    game_days = set(st["phase1_game_days"])
    log(f"backfill start/resume: {len(done)} snapshots done, {len(game_days)} game days known")

    # ---- phase 1: featured markets ----
    for a, b in SEASONS:
        for day in day_range(a, b):
            for tsuf in SNAP_TIMES:
                key = day + "T" + tsuf
                if key in done:
                    continue
                data, hdrs = get("/odds", {
                    "date": key, "regions": "us",
                    "markets": "h2h,spreads,totals", "oddsFormat": "american",
                })
                retrieval_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
                if data and isinstance(data, dict) and data.get("data"):
                    snap_ts = data.get("timestamp")
                    payload = json.dumps(data["data"], separators=(",", ":"), sort_keys=True)
                    append_row(FEAT_F, {
                        "requested_ts": key, "vendor_snapshot_ts": snap_ts,
                        "vendor_prev_ts": data.get("previous_timestamp"),
                        "vendor_next_ts": data.get("next_timestamp"),
                        "retrieval_ts": retrieval_ts,
                        "vendor_ts_semantics": "vendor_asserted_unwitnessed",
                        "provenance_class": "T1_VENDOR_ASSERTED",
                        "n_events": len(data["data"]),
                        "payload_sha256": hashlib.sha256(payload.encode()).hexdigest(),
                        "payload": data["data"],
                    })
                    game_days.add(day)
                done.add(key)
                st["phase1_done"] = sorted(done)
                st["phase1_game_days"] = sorted(game_days)
                if len(done) % 50 == 0:
                    save_state(st)
                    log(f"phase1 progress: {len(done)} snapshots, {len(game_days)} game days, remaining={remaining(hdrs)}")
                guard(hdrs)
                time.sleep(0.7)
    save_state(st)
    log(f"phase 1 COMPLETE: {len(game_days)} game days with data")

    # ---- phase 2: props discovery on known game days ----
    p2done = set(st["phase2_done"])
    for day in sorted(game_days):
        if day in p2done:
            continue
        key = day + "T20:00:00Z"
        evs, hdrs = get("/events", {"date": key})
        events = (evs or {}).get("data") or []
        for ev in events[:2]:
            eid = ev.get("id")
            if not eid:
                continue
            pdata, hdrs = get(f"/events/{eid}/odds", {
                "date": key, "regions": "us", "markets": "player_points",
                "oddsFormat": "american",
            })
            retrieval_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
            body = (pdata or {}).get("data") or {}
            bms = body.get("bookmakers") or []
            append_row(PROPS_F, {
                "requested_ts": key, "event_id": eid, "day": day,
                "vendor_snapshot_ts": (pdata or {}).get("timestamp"),
                "retrieval_ts": retrieval_ts,
                "vendor_ts_semantics": "vendor_asserted_unwitnessed",
                "provenance_class": "T1_VENDOR_ASSERTED",
                "n_bookmakers": len(bms),
                "payload_sha256": hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() if bms else None,
                "payload": body if bms else None,
            })
            guard(hdrs)
            time.sleep(0.7)
        p2done.add(day)
        st["phase2_done"] = sorted(p2done)
        if len(p2done) % 20 == 0:
            save_state(st)
            log(f"phase2 progress: {len(p2done)}/{len(game_days)} game days, remaining={remaining(hdrs)}")
    save_state(st)
    log("phase 2 COMPLETE - backfill finished")


if __name__ == "__main__":
    main()
