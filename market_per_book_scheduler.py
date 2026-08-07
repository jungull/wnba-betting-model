#!/usr/bin/env python3
"""
M27_PER_BOOK_POLLING scheduling arithmetic: which games are due for a
per-book poll cycle right now, and a persisted cursor so repeated runs of
market_capture_run.py know when the declared interval has elapsed.

Mirrors market_burst_trigger.py's cursor-file pattern deliberately (same
"persist last-fired instant per game, compare against now" discipline)
rather than reinventing it. Kept as its own module, not folded into
market_ladder_scheduler.py, because the per-book layer has a different
obligation shape: the ladder fires each rung AT MOST ONCE per game
(`due_rungs`'s `served` set), while per-book polling fires REPEATEDLY at a
fixed interval for as long as `now` sits inside the declared pre-tip window
-- a "served once" model does not fit it.

Every number this module consumes (window width, interval) is imported from
market_capture_config.py, not hardcoded here, so the scope declaration lives
in exactly one place.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from market_capture_config import (
    PER_BOOK_POLL_INTERVAL_SECONDS,
    PER_BOOK_PRE_TIP_WINDOW_MINUTES,
)

PER_BOOK_CURSOR_JSON = "_per_book_cursor.json"


def _utc(t: datetime) -> datetime:
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


def in_pre_tip_window(tip: datetime, now: datetime) -> bool:
    """True iff now sits in [tip - PER_BOOK_PRE_TIP_WINDOW_MINUTES, tip).
    Never fires at or after tip (in-play exclusion, M00 contract Section
    4.4) and never fires before the declared window starts (the bounded-
    scope hard stop: "never raise cadence beyond the scoped window")."""
    tip = _utc(tip)
    now = _utc(now)
    window_start = tip - timedelta(minutes=PER_BOOK_PRE_TIP_WINDOW_MINUTES)
    return window_start <= now < tip


def due_per_book(game: dict, now: datetime, last_polled: Optional[datetime]) -> bool:
    """A game is due for a per-book poll cycle right now iff (a) now is
    inside its declared pre-tip window, and (b) either no per-book cycle has
    ever fired for this game, or at least PER_BOOK_POLL_INTERVAL_SECONDS
    have elapsed since the last one."""
    tip = game.get("tip")
    if tip is None:
        return False
    now = _utc(now)
    if not in_pre_tip_window(tip, now):
        return False
    if last_polled is None:
        return True
    elapsed = (now - _utc(last_polled)).total_seconds()
    return elapsed >= PER_BOOK_POLL_INTERVAL_SECONDS


class PerBookCursor:
    """Persisted map of game_id -> ISO timestamp of the last per-book poll
    cycle fired for that game. Same load/save discipline as
    market_snapshot_writer.ChainIndex/RosterIndex (best-effort JSON load,
    corrupt/missing file treated as empty, never raises)."""

    def __init__(self, path: Path):
        self.path = path
        self._data = {}
        if path.exists():
            try:
                self._data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def last_polled(self, game_id: str) -> Optional[datetime]:
        v = self._data.get(game_id)
        if not v:
            return None
        try:
            dt = datetime.fromisoformat(v)
        except ValueError:
            return None
        return _utc(dt)

    def mark_polled(self, game_id: str, when: datetime) -> None:
        self._data[game_id] = _utc(when).isoformat()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=1), encoding="utf-8")
