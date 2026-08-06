#!/usr/bin/env python3
"""
Snapshot ladder scheduler: T-24h..final-pregame, per game, per design (b).

Mirrors `prospective_pair/should_run_base.py`'s gate shape deliberately (same
"registered obligation + lead window + at-most-once" discipline) rather than
reinventing it, per the node's instruction to reuse the existing gate /
idempotency patterns. It does NOT import that module: the ladder here is a
capture-layer obligation (games x ladder rungs), not a forecast-layer one
(games x CONTRACT_LABELS), and the two must stay independently testable
without pulling in `evalharness`/`alt_model_log`'s heavier import chain for
what is pure scheduling arithmetic.

INPUT CONTRACT (dependency injection, not file reads):
    Callers pass in a `games` list of dicts with at minimum
    {"game_id": str, "tip": timezone-aware datetime}. Production wiring
    (market_capture_run.py) builds that list from
    prospective_pair.coverage_audit.build_slate(); tests pass fixtures
    directly. This keeps the scheduling arithmetic hermetic and fast.

ASSUMPTION FLAGGED EXPLICITLY (report this, do not silently bake it in):
    The design's ladder is "T-24h T-8h T-4h T-2h T-60m T-30m T-15m
    final-pregame" and defines "final pregame" only as "the last scheduled
    ladder rung before tip, distinct from any capture made after tip" -- it
    does not give final-pregame a numeric offset. This module treats
    final-pregame as T-5m (0.0833h before tip), one rung tighter than T-15m,
    so it is a genuinely distinct rung rather than a renamed duplicate of
    T-15m. This is an interpretation, not a measurement; a different offset
    is a one-line change to LADDER_RUNGS.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

#: (label, hours_before_tip). Order matters only for display.
LADDER_RUNGS = [
    ("T-24h", 24.0),
    ("T-8h", 8.0),
    ("T-4h", 4.0),
    ("T-2h", 2.0),
    ("T-60m", 1.0),
    ("T-30m", 0.5),
    ("T-15m", 0.25),
    ("final_pregame", 5.0 / 60.0),
]

#: how many minutes BEFORE a rung's cutoff the poller is allowed to fire for
#: it (mirrors should_run_base.LEAD). Coarse rungs get a wide lead because
#: they are typically hours apart and a missed poll is expensive (unrecoverable,
#: append-only); the two tightest rungs get a narrow lead so "T-15m" and
#: "final_pregame" (5 min apart) cannot fire for each other's obligation.
LEAD_MINUTES = {
    "T-24h": 30, "T-8h": 20, "T-4h": 15, "T-2h": 10,
    "T-60m": 8, "T-30m": 4, "T-15m": 3, "final_pregame": 2,
}
#: how late after a cutoff the poller may still fire and count it as "on
#: time" rather than a miss the auditor should flag -- mirrors
#: should_run_base's `-0.5 <= minutes_to_cutoff` tolerance for firing, kept
#: separate from the auditor's own (wider) grace period in
#: capture_coverage_audit.py.
FIRE_GRACE_MINUTES = 1.0


def _utc(t: datetime) -> datetime:
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


def rung_cutoff(tip: datetime, label: str) -> datetime:
    hours = dict(LADDER_RUNGS)[label]
    return _utc(tip) - timedelta(hours=hours)


def _rung_poll_intervals() -> dict:
    """seconds between this rung and the previous (coarser) one -- the
    `poll_interval_at_capture` / `max_staleness_bound` value written for a
    row captured at this rung (design (d): "required because the ladder's
    own interval changes ... so a fixed global constant would misstate the
    bound at every rung except the one it was tuned for"). The first rung
    (T-24h) has no earlier rung to measure from; its own offset (24h) is
    used as a conservative bound -- documented assumption, not a
    measurement, since nothing was polled before it."""
    out = {}
    prev_hours = None
    for label, hours in LADDER_RUNGS:
        gap_hours = hours if prev_hours is None else (prev_hours - hours)
        out[label] = gap_hours * 3600.0
        prev_hours = hours
    return out


RUNG_POLL_INTERVAL_SECONDS = _rung_poll_intervals()

#: burst-leg spacing per design (b): "propose 3 legs: immediate, +5min, +15min"
BURST_LEG_INTERVAL_SECONDS = 5 * 60.0


def due_rungs(game: dict, now: Optional[datetime] = None,
              served_labels: Iterable[str] = ()) -> dict:
    """Which ladder rungs for one game are due right now.

    Returns {"game_id":..., "due": [rung_item...], "upcoming": [...],
    "already_tipped": bool}. A rung is due if it is unserved AND now sits in
    [cutoff - LEAD, cutoff + FIRE_GRACE]. Mirrors should_run_base.assess():
    waiting past the lead window without firing costs a missed obligation
    (recoverable via capture_coverage_audit.py's classification, never
    silently hidden); firing for an already-served label would be a
    duplicate poll (wasted quota, not a correctness bug, since this schema
    is append-only and a repeat poll is just another true observation -- but
    it is still gated out here to avoid needlessly burning vendor credits).
    """
    now = _utc(now or datetime.now(timezone.utc))
    tip = _utc(game["tip"])
    served = set(served_labels)
    if tip <= now:
        return {"game_id": game["game_id"], "due": [], "upcoming": [],
                "already_tipped": True}

    due, upcoming = [], []
    for label, _hours in LADDER_RUNGS:
        cutoff = rung_cutoff(tip, label)
        minutes_to_cutoff = (cutoff - now).total_seconds() / 60.0
        lead = LEAD_MINUTES[label]
        item = {"game_id": game["game_id"], "label": label,
                "cutoff_utc": cutoff.isoformat(),
                "minutes_to_cutoff": round(minutes_to_cutoff, 2),
                "served": label in served}
        upcoming.append(item)
        if label in served:
            continue
        if -FIRE_GRACE_MINUTES <= minutes_to_cutoff <= lead:
            due.append(item)
    return {"game_id": game["game_id"], "due": due, "upcoming": upcoming,
            "already_tipped": False}


def ladder_obligations(games: list, now: Optional[datetime] = None,
                        served_by_game: Optional[dict] = None) -> list:
    """due_rungs() applied across a slate. `served_by_game` maps
    game_id -> set/iterable of already-served labels; defaults to none
    served for any game not present."""
    served_by_game = served_by_game or {}
    now = _utc(now or datetime.now(timezone.utc))
    return [due_rungs(g, now, served_by_game.get(g["game_id"], ()))
            for g in games]
