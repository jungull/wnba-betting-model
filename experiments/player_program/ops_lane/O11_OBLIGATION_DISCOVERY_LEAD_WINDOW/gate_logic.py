"""O11 — the base-forecast gate's obligation-discovery logic, isolated.

This module contains TWO pure functions over an already-built slate:

  * `classify_original`  — the current behaviour of
    `prospective_pair/should_run_base.py::assess` (lines 78-102), transcribed
    verbatim in its decision structure so the defect can be reproduced without
    executing the live scheduler.
  * `classify_fixed`     — the candidate fix.

Nothing here imports or mutates the live scheduler. The live file is NOT edited
by this node; the intended change is recorded as `PROPOSED_PATCH.diff`.

THE DEFECT (D-b in experiments/player_program/PROJECT_UPDATE_2026-08-04.md:200)

    should_run_base.py:80-82

        gid = str(g.game_id) if pd.notna(g.game_id) else None
        if gid is None or g.tip <= now:
            continue

    A slate row with no official `game_id` is dropped before any window test, so
    it never reaches `upcoming`, `new` or `in_window`. The gate then falls to

        elif not in_window:
            reason = "no unserved obligation inside its %d-minute lead window"

    which names the lead window as the cause of a decline the lead window did not
    cause. Nothing is printed for the dropped game, so the decline is silent.

    The gate's identity rule is STRICTER than that of the job it guards.
    `daily_forecast.py:561-563` mints `PROV-{slate_date}-{away}@{home}` and sets
    `game_id_provisional` when the ref-assignment id is absent, and
    `coverage_audit.py:148-168` resolves those provisional ids back to the real
    id retroactively. The gate is the only component that requires the official
    id up front.

THE FIX

    Give the gate the same identity rule as the job: fall back to the provisional
    id rather than skipping the row, and report unresolved rows explicitly so a
    decline can never be silent. `current_label` is deliberately NOT changed --
    it mirrors the label `daily_forecast.py` will actually assign, and decoupling
    them would create a different, worse defect. The `fire = ... and not dup`
    conjunction is deliberately NOT changed either: that is defect D-c, node
    O12_PER_GAME_EXECUTION_SCOPE.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

#: coverage_audit.py:47
CONTRACT_LABELS = [("T-24h", 24.0), ("T-8h", 8.0), ("T-90m", 1.5), ("T-30m", 0.5)]

#: should_run_base.py:43
LEAD = timedelta(minutes=20)


def current_label(hours_to_tip: float, labels=CONTRACT_LABELS) -> str:
    """should_run_base.py:46-52, unchanged."""
    return min(labels, key=lambda lh: abs(hours_to_tip - lh[1]))[0]


def provisional_game_id(game_date: str, home: str, away: str) -> str:
    """daily_forecast.py:562 — `PROV-{slate_date}-{away}@{home}`.

    Parsed back by coverage_audit.py:161-165, which splits on '-' with maxsplit 4
    and rejoins parts[1:4] as the date, so the date must stay ISO and the team
    codes must not contain '-'.
    """
    return f"PROV-{game_date}-{away}@{home}"


def _item(g: dict, gid: str, now: datetime, labels) -> dict:
    hrs = (g["tip"] - now).total_seconds() / 3600.0
    label = current_label(hrs, labels)
    cutoff = g["tip"] - timedelta(hours=dict(labels)[label])
    return {"game": f"{g['home']} v {g['away']}", "game_id": gid, "label": label,
            "cutoff": cutoff.isoformat(), "hours_to_tip": round(hrs, 2),
            "minutes_to_cutoff": round((cutoff - now).total_seconds() / 60, 1)}


def _finish(new, dup, upcoming, unresolved, now, lead, labels):
    lead_min = lead.total_seconds() / 60
    in_window = [i for i in new if -0.5 <= i["minutes_to_cutoff"] <= lead_min]
    fire = bool(in_window) and not dup
    return {"fire": fire, "new": new, "in_window": in_window,
            "would_duplicate": dup, "upcoming": upcoming,
            "unresolved": unresolved, "now": now.isoformat(),
            "_lead_min": lead_min}


def classify_original(slate, served, now, lead=LEAD, labels=CONTRACT_LABELS) -> dict:
    """Current behaviour. `slate` rows: dict(game_id, tip, home, away, game_date)."""
    new, dup, upcoming = [], [], []
    for g in slate:
        gid = str(g["game_id"]) if g.get("game_id") else None
        if gid is None or g["tip"] <= now:
            continue
        item = _item(g, gid, now, labels)
        upcoming.append(item)
        (dup if (gid, item["label"]) in served else new).append(item)
    a = _finish(new, dup, upcoming, [], now, lead, labels)
    if dup:
        a["reason"] = ("would duplicate %d already-served obligation(s); the base job cannot be "
                       "scoped to one game" % len(dup))
    elif not a["in_window"]:
        a["reason"] = ("no unserved obligation inside its %d-minute lead window"
                       % a["_lead_min"])
    else:
        a["reason"] = ("%d unserved obligation(s) in window, none would duplicate"
                       % len(a["in_window"]))
    return a


def classify_fixed(slate, served, now, lead=LEAD, labels=CONTRACT_LABELS) -> dict:
    """Candidate fix: provisional identity + non-silent decline."""
    new, dup, upcoming, unresolved = [], [], [], []
    for g in slate:
        if g["tip"] <= now:
            continue
        gid = str(g["game_id"]) if g.get("game_id") else None
        provisional = gid is None
        if provisional:
            gid = provisional_game_id(g["game_date"], g["home"], g["away"])
            unresolved.append(f"{g['home']} v {g['away']} ({g['game_date']}) -> {gid}")
        item = _item(g, gid, now, labels)
        item["game_id_provisional"] = provisional
        upcoming.append(item)
        (dup if (gid, item["label"]) in served else new).append(item)
    a = _finish(new, dup, upcoming, unresolved, now, lead, labels)
    note = ("; %d slate game(s) have no official game_id and were served under a "
            "provisional id: %s" % (len(unresolved), ", ".join(unresolved))) if unresolved else ""
    if dup:
        a["reason"] = ("would duplicate %d already-served obligation(s); the base job cannot be "
                       "scoped to one game%s" % (len(dup), note))
    elif not a["in_window"]:
        a["reason"] = ("no unserved obligation inside its %d-minute lead window (%d upcoming "
                       "game(s) examined)%s" % (a["_lead_min"], len(upcoming), note))
    else:
        a["reason"] = ("%d unserved obligation(s) in window, none would duplicate%s"
                       % (len(a["in_window"]), note))
    return a


def utc(s: str) -> datetime:
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
