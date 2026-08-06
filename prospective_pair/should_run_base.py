"""Gate: is a BASE forecast actually due right now?

WHY THIS EXISTS
    daily_forecast.py de-duplicates on the exact forecast_cutoff timestamp, which is
    "now" on every invocation. Two runs a minute apart therefore produce two records
    for the same (game, decision time) -- neither is a duplicate by its own test.
    Firing the wrapper every 15 minutes without this gate would append roughly 288
    near-identical records to the official chain per night. The chain is append-only,
    so that damage is not removable.

    Verified empirically 2026-08-03: a second wrapper invocation one minute after the
    first took the base chain from 16 to 19 records while the companion arm log
    correctly stayed at 3.

WHAT IT DOES
    Exits 0 (run the base job) only if at least one (game, registered cutoff)
    obligation is BOTH unserved AND inside its lead window. Exits 1 otherwise.

    Once the base job serves that obligation the gate closes for it, so each
    (game, decision time) is written at most once no matter how often the wrapper
    fires. The 15-minute cadence stays -- it is what makes the lead window reliable --
    but it no longer implies 15-minute writes.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from alt_model_log import read_official                      # noqa: E402
from coverage_audit import (                                 # noqa: E402
    CONTRACT_LABELS, _resolve_provisional, _utc, build_slate,
)

#: fire the base job at most this long before a nominal cutoff. Must exceed the
#: scheduler interval (15 min) or an obligation can fall between two firings.
LEAD = timedelta(minutes=20)


def current_label(hours_to_tip: float) -> str:
    """The label daily_forecast.py will assign RIGHT NOW: nearest registered
    decision time by hours-to-tip. The base job forecasts the whole slate in one
    pass and cannot be scoped to a single game (its only options are --slate-date,
    --cutoff, --live, --no-log), so every game on the slate gets whatever label its
    own hours-to-tip implies at the moment of firing."""
    return min(CONTRACT_LABELS, key=lambda lh: abs(hours_to_tip - lh[1]))[0]


def assess(now=None) -> dict:
    """Decide whether firing the base job right now would be CLEAN.

    Firing is clean only if every not-yet-tipped game on the slate maps to an
    UNSERVED (game, label) -- and at least one does. If any game currently sits on a
    label it has already been logged at, firing would append a duplicate for that
    game, because log_forecast()'s duplicate key is
    (game_id, forecast_cutoff, model_version_hash) and the cutoff is "now" on every
    invocation. Two firings a minute apart therefore never collide.

    Waiting costs a missed obligation. Firing anyway costs a permanent duplicate in
    an append-only chain, which is worse and is explicitly forbidden. So we wait, and
    the auditor records the miss with this exact reason rather than hiding it.
    """
    now = _utc(now or datetime.now(timezone.utc))
    slate = build_slate()
    if slate.empty:
        return {"fire": False, "reason": "no slate", "new": [], "would_duplicate": []}
    official = read_official()
    prov = _resolve_provisional(official, slate)
    served = {(prov.get(str(r["game_id"]), str(r["game_id"])), r["decision_time_label"])
              for r in official}

    new, dup, upcoming = [], [], []
    for g in slate.itertuples():
        gid = str(g.game_id) if pd.notna(g.game_id) else None
        if gid is None or g.tip <= now:
            continue                      # already tipped: cannot be forecast now
        hrs = (g.tip - now).total_seconds() / 3600.0
        label = current_label(hrs)
        cutoff = g.tip - timedelta(hours=dict(CONTRACT_LABELS)[label])
        item = {"game": f"{g.home} v {g.away}", "game_id": gid, "label": label,
                "cutoff": cutoff.isoformat(), "hours_to_tip": round(hrs, 2),
                "minutes_to_cutoff": round((cutoff - now).total_seconds() / 60, 1)}
        upcoming.append(item)
        (dup if (gid, label) in served else new).append(item)

    in_window = [i for i in new if -0.5 <= i["minutes_to_cutoff"] <= LEAD.total_seconds() / 60]
    fire = bool(in_window) and not dup
    if dup:
        reason = ("would duplicate %d already-served obligation(s); the base job cannot be "
                  "scoped to one game" % len(dup))
    elif not in_window:
        reason = "no unserved obligation inside its %d-minute lead window" % (LEAD.total_seconds() / 60)
    else:
        reason = "%d unserved obligation(s) in window, none would duplicate" % len(in_window)
    return {"fire": fire, "reason": reason, "new": new, "in_window": in_window,
            "would_duplicate": dup, "upcoming": upcoming, "now": now.isoformat()}


def due_obligations(now=None):
    """Back-compatible: the unserved obligations currently inside their lead window."""
    return assess(now)["in_window"]


def main() -> int:
    a = assess()
    print(f"[gate] {a['now']}  fire={a['fire']}  -- {a['reason']}")
    for i in a.get("upcoming", []):
        served = "SERVED" if i in a["would_duplicate"] else "unserved"
        win = "IN-WINDOW" if i in a.get("in_window", []) else ""
        print("       %-14s %-7s %-8s cutoff %s (%+.0f min) %s"
              % (i["game"], i["label"], served, i["cutoff"][:19],
                 i["minutes_to_cutoff"], win))
    if a["fire"]:
        print("[gate] BASE RUN DUE")
        return 0
    if a["would_duplicate"]:
        print("[gate] HOLDING: firing now would append %d permanent duplicate record(s) to an "
              "append-only chain. A missed obligation is recoverable; a duplicate is not."
              % len(a["would_duplicate"]))
    print("[gate] skipping the base job")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
