#!/usr/bin/env python3
"""
Event-driven burst-poll trigger: first-seen injury/news rows -> burst legs.

Per design (b): a lightweight watcher polls injury_log.csv / news_items.csv
(local CSV reads, not vendor API calls), diffs against a persisted cursor to
find newly appended rows since the last check, resolves the row's team to a
still-future game on the slate, and -- if it finds one -- schedules a short
burst (default 3 legs: immediate, +5min, +15min) of extra snapshots for that
game only.

REUSE, NOT DUPLICATION: team resolution and "is this game still capturable"
both come from data the caller injects (`team_lookup`, `slate`), so this
module can reuse `prospective_pair/coverage_audit.py`'s TEAMS dict and
build_slate() in production wiring (market_capture_run.py) without this
module importing coverage_audit.py itself -- that module pulls in
alt_model_log -> evalharness.forecast_log, a much heavier dependency chain
than a capture-layer trigger watcher needs, and dependency injection keeps
this module's own tests hermetic (fixture dicts, no filesystem coupling to
the forecast chain). This is a disclosed interpretation of "reuse the same
team-abbreviation join", not a byte-identical import, and is called out in
REPORT.md as a design deviation for the verifier to weigh.

CURSOR PERSISTENCE: a small JSON file records, per source CSV, the row
count already seen. This is a READ-ONLY relationship to injury_log.csv /
news_items.csv (this module never writes to them) and only ever grows
forward -- it does not rewind, matching every other append-only assumption
in this codebase.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

#: burst leg offsets from the trigger moment.
BURST_LEG_OFFSETS_MINUTES = [0, 5, 15]

#: default team-name aliasing recognized inside news teams_mentioned / injury
#: team columns is whatever `team_lookup` the caller passes maps -- this
#: module does no normalization of its own beyond exact-key lookup and a
#: semicolon split for news's multi-team column, by design (the join logic
#: itself is not re-derived here, see module docstring).


@dataclass
class Trigger:
    source: str                 # "injury" | "news"
    row_index: int               # 0-based row number within its CSV (post-header)
    capture_utc: str
    teams: list                  # resolved team name(s) mentioned in the row
    raw: dict


@dataclass
class BurstObligation:
    game_id: str
    trigger: Trigger
    leg_label: str                # "burst+0m" / "burst+5m" / "burst+15m"
    fire_at: datetime
    scope: str = "event"          # this design's odds pull stays slate-wide;
                                   # props pull is scoped to the game's event id


def _read_cursor(cursor_path: Path) -> dict:
    if not cursor_path.exists():
        return {}
    try:
        return json.loads(cursor_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_cursor(cursor_path: Path, cursor: dict) -> None:
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text(json.dumps(cursor, indent=1), encoding="utf-8")


def _csv_rows(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def scan_new_rows(csv_path: Path, cursor: dict, source_key: str) -> tuple:
    """New rows appended to csv_path since cursor[source_key]["last_row_count"].
    Returns (new_rows, updated_cursor). Coarser-but-safe against a rewritten
    file: if the file is now SHORTER than the cursor (should never happen
    under the append-only rule the writers themselves state, but is checked
    rather than assumed), that is reported as a NOTE-worthy anomaly and the
    cursor is reset to the current length rather than raising -- a burst
    trigger watcher must never crash the whole poller over an upstream file
    it does not own."""
    rows = _csv_rows(csv_path)
    prev = cursor.get(source_key, {}).get("last_row_count", 0)
    anomaly = None
    if len(rows) < prev:
        anomaly = (f"{csv_path.name} has fewer rows ({len(rows)}) than the "
                   f"last cursor position ({prev}); resetting cursor. This "
                   f"violates the append-only assumption and should be "
                   f"investigated.")
        prev = 0
    new_rows = rows[prev:]
    cursor = dict(cursor)
    cursor[source_key] = {"last_row_count": len(rows)}
    return new_rows, cursor, anomaly


def injury_triggers(rows: Iterable[dict], start_index: int = 0) -> list:
    out = []
    for i, r in enumerate(rows):
        team = (r.get("team") or "").strip()
        out.append(Trigger(source="injury", row_index=start_index + i,
                            capture_utc=r.get("capture_utc", ""),
                            teams=[team] if team else [], raw=dict(r)))
    return out


def news_triggers(rows: Iterable[dict], start_index: int = 0) -> list:
    out = []
    for i, r in enumerate(rows):
        raw_teams = (r.get("teams_mentioned") or "").strip()
        teams = [t.strip() for t in raw_teams.split(";") if t.strip()]
        out.append(Trigger(source="news", row_index=start_index + i,
                            capture_utc=r.get("capture_utc", ""),
                            teams=teams, raw=dict(r)))
    return out


def resolve_game_for_trigger(trig: Trigger, slate: list,
                              team_lookup: Optional[dict] = None,
                              now: Optional[datetime] = None) -> Optional[dict]:
    """Resolve a trigger's team(s) to a still-future game on the slate.
    `slate` is a list of dicts {"game_id","home","away","tip"}. `team_lookup`
    optionally normalizes raw team strings (e.g. full-name -> abbreviation)
    before matching against slate home/away -- pass the same mapping used to
    build the slate so identities agree; if omitted, raw team strings are
    matched directly against slate home/away.

    A trigger for a game whose tip has already passed fires nothing --
    matches should_run_base.py's own "cutoff already passed" refusal."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    norm = (lambda t: team_lookup.get(t, t)) if team_lookup else (lambda t: t)
    wanted = {norm(t) for t in trig.teams}
    if not wanted:
        return None
    for g in slate:
        tip = g["tip"]
        if tip.tzinfo is None:
            tip = tip.replace(tzinfo=timezone.utc)
        if tip <= now:
            continue
        if g.get("home") in wanted or g.get("away") in wanted:
            return g
    return None


def schedule_burst(trig: Trigger, game: dict, now: Optional[datetime] = None,
                    offsets_minutes: Iterable[int] = BURST_LEG_OFFSETS_MINUTES
                    ) -> list:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return [BurstObligation(game_id=game["game_id"], trigger=trig,
                            leg_label=f"burst+{m}m",
                            fire_at=now + timedelta(minutes=m))
            for m in offsets_minutes]


def dedupe_against_ladder(bursts: list, pending_ladder_cutoffs: dict,
                           window_minutes: float = 5.0) -> list:
    """Drop a burst leg if a scheduled ladder rung for the SAME game already
    falls inside the leg's firing window -- the ladder rung already captures
    it, per design (b) step 5 ("idempotent, at-most-once obligation").
    `pending_ladder_cutoffs` maps game_id -> iterable of rung cutoff
    datetimes still ahead of now."""
    kept = []
    for b in bursts:
        cutoffs = pending_ladder_cutoffs.get(b.game_id, [])
        collide = any(abs((c - b.fire_at).total_seconds()) <= window_minutes * 60
                     for c in cutoffs)
        if not collide:
            kept.append(b)
    return kept


def run_watch(injury_csv: Path, news_csv: Path, cursor_path: Path,
              slate: list, team_lookup: Optional[dict] = None,
              now: Optional[datetime] = None,
              pending_ladder_cutoffs: Optional[dict] = None) -> dict:
    """One watcher tick: diff both source CSVs, resolve triggers to games,
    schedule (deduped) bursts, persist the cursor. Pure/testable: pass fixture
    CSV paths and an in-memory slate; production wiring supplies the real
    injury_log.csv / news_items.csv paths and coverage_audit.build_slate()'s
    output (converted to the {"game_id","home","away","tip"} shape)."""
    now = now or datetime.now(timezone.utc)
    cursor = _read_cursor(cursor_path)
    anomalies = []

    inj_new, cursor, a1 = scan_new_rows(injury_csv, cursor, "injury")
    if a1:
        anomalies.append(a1)
    news_new, cursor, a2 = scan_new_rows(news_csv, cursor, "news")
    if a2:
        anomalies.append(a2)

    triggers = (injury_triggers(inj_new) + news_triggers(news_new))
    scheduled, unresolved = [], []
    for trig in triggers:
        game = resolve_game_for_trigger(trig, slate, team_lookup, now)
        if game is None:
            unresolved.append(trig)
            continue
        legs = schedule_burst(trig, game, now)
        scheduled.extend(legs)

    if pending_ladder_cutoffs:
        scheduled = dedupe_against_ladder(scheduled, pending_ladder_cutoffs)

    _write_cursor(cursor_path, cursor)
    return {"triggers_seen": len(triggers), "bursts_scheduled": scheduled,
            "unresolved_triggers": unresolved, "anomalies": anomalies,
            "now": now.isoformat()}
