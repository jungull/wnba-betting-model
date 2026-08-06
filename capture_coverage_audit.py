#!/usr/bin/env python3
"""
Capture-layer auditor: missed-poll, silent-overwrite, identifier-change and
stale-job detection (design section (e)).

Applies `prospective_pair/coverage_audit.py`'s own obligation-vs-actual
auditing pattern to the capture layer, as the design instructs, without
importing that module (see market_burst_trigger.py's docstring for why:
this keeps the capture-layer auditor independently testable without pulling
in the forecast chain's evalharness dependency). `SERVED`/`DUE`-style
classification naming is intentionally kept the same as coverage_audit.py's
so a reader who knows that module recognizes the pattern immediately.

All four functions take already-loaded data (rows/DataFrames/dicts as
plain Python), not file paths, so tests are fixture-driven with no I/O.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

# ------------------------------------------------------- missed-poll ------
def missed_poll_audit(games: list, ladder_rungs, snapshot_rows: list,
                       now: Optional[datetime] = None,
                       tip_move_tolerance_minutes: float = 30.0) -> list:
    """One row per (game, ladder rung) obligation, classified the same way
    coverage_audit.audit() classifies forecast obligations.

    `games`: [{"game_id","tip","first_tip"(optional),"tip_moved"(optional)}]
    `ladder_rungs`: [(label, hours_before_tip), ...] (market_ladder_scheduler.LADDER_RUNGS)
    `snapshot_rows`: [{"game_id","retrieval_ts"}, ...] (from snapshots.csv)

    CLASSES (mirrors coverage_audit.py's naming):
        served                 a snapshot row exists with retrieval_ts on/after
                                the rung's cutoff (never before -- amendment 4's
                                no-backdating rule means a row retrieved before
                                a cutoff cannot retroactively satisfy it)
        not_yet_due             cutoff is in the future
        postponed_or_tip_changed  tip moved since the rung's cutoff was computed
        missing_poll_did_not_run  cutoff passed, no row for this game at all
                                 in the window -- an operational miss
    """
    now = _utc(now or datetime.now(timezone.utc))
    served_ts = {}
    for r in snapshot_rows:
        served_ts.setdefault(r["game_id"], []).append(_utc_str(r["retrieval_ts"]))

    out = []
    for g in games:
        tip = _utc(g["tip"])
        tip_moved = bool(g.get("tip_moved"))
        gid = g["game_id"]
        rows_for_game = sorted(served_ts.get(gid, []))
        for label, hours in ladder_rungs:
            cutoff = tip - timedelta(hours=hours)
            # next rung's cutoff bounds the acceptable window on the late side
            # (a row retrieved well past this rung, inside the NEXT rung's
            # window, belongs to that rung, not this one)
            later_cutoffs = sorted(
                (tip - timedelta(hours=h) for lbl, h in ladder_rungs
                 if (tip - timedelta(hours=h)) > cutoff),
                reverse=False)
            window_end = later_cutoffs[0] if later_cutoffs else (cutoff + timedelta(hours=hours))
            matches = [t for t in rows_for_game if cutoff <= t < window_end]
            if matches:
                cls, why = "served", None
            elif cutoff > now:
                cls, why = "not_yet_due", None
            elif tip_moved:
                cls, why = "postponed_or_tip_changed", "tip moved since this cutoff was set"
            else:
                cls, why = "missing_poll_did_not_run", \
                    f"no snapshot row for {gid} in [{cutoff.isoformat()}, {window_end.isoformat()})"
            out.append({"game_id": gid, "label": label, "cutoff_utc": cutoff.isoformat(),
                       "classification": cls, "reason": why})
    return out


def summarize_missed_poll(audit_rows: list) -> dict:
    due = [r for r in audit_rows if r["classification"] != "not_yet_due"]
    served = [r for r in due if r["classification"] == "served"]
    misses = [r for r in due if r["classification"] == "missing_poll_did_not_run"]
    cov = (len(served) / len(due)) if due else None
    return {"obligations_total": len(audit_rows), "due": len(due),
            "served": len(served), "operational_misses": len(misses),
            "coverage_served": cov}


# --------------------------------------------------- silent-overwrite -----
def silent_overwrite_check(snapshot_rows: list) -> list:
    """Walk the prev_snapshot_ref chain per (game_id, book, market, outcome)
    key, ordered by retrieval_ts, and flag any row whose prev_snapshot_ref
    does not equal the snapshot_id of the row that actually preceded it.
    Structurally this should be impossible if the writer only ever appends
    (design (e)) -- a broken chain link means something wrote out of
    process, or the file was hand-edited. Returns a list of break dicts,
    empty if the chain is intact."""
    by_key: dict = {}
    for r in snapshot_rows:
        k = (r["game_id"], r.get("book"), r.get("market"), r.get("outcome"))
        by_key.setdefault(k, []).append(r)
    breaks = []
    for k, rows in by_key.items():
        rows_sorted = sorted(rows, key=lambda r: r["retrieval_ts"])
        prev_id = None
        for r in rows_sorted:
            expected = prev_id
            actual = r.get("prev_snapshot_ref") or None
            if actual != expected:
                breaks.append({"key": k, "snapshot_id": r.get("snapshot_id"),
                              "expected_prev": expected, "actual_prev": actual,
                              "retrieval_ts": r["retrieval_ts"]})
            prev_id = r.get("snapshot_id")
    return breaks


# --------------------------------------------------- identifier-change ----
def identifier_change_check(snapshot_rows: list, known_books: set,
                             known_markets: set) -> dict:
    """Compare books/markets seen in snapshot_rows against an allow-list
    (seeded from odds_capture_daily.MARKETS / props_capture_daily.MARKETS +
    whatever books have been seen before). Anything new is a NOTE, matching
    the existing WARNING-style convention -- never silently absorbed, never
    fatal (an unannounced vendor rename must not take the poller down)."""
    seen_books = {r.get("book") for r in snapshot_rows if r.get("book")}
    seen_markets = {r.get("market") for r in snapshot_rows if r.get("market")}
    new_books = sorted(seen_books - known_books)
    new_markets = sorted(seen_markets - known_markets)
    notes = []
    if new_books:
        notes.append(f"NOTE: new bookmaker key(s) not in allow-list: {new_books}")
    if new_markets:
        notes.append(f"NOTE: new market key(s) not in allow-list: {new_markets}")
    return {"new_books": new_books, "new_markets": new_markets, "notes": notes}


# -------------------------------------------------------- stale-job -------
def stale_job_check(last_row_retrieval_ts: Optional[str],
                     now: Optional[datetime] = None,
                     max_expected_gap_hours: float = 24.0 + 2.0) -> dict:
    """A capture job that has not written ANY row in longer than its own
    maximum expected gap (coarsest ladder rung, 24h, + a 2h safety margin)
    is stale. `last_row_retrieval_ts` is None when no row has EVER been
    written (also stale -- there is no grace period for a job that never
    started)."""
    now = _utc(now or datetime.now(timezone.utc))
    if last_row_retrieval_ts is None:
        return {"stale": True, "reason": "no snapshot row has ever been written",
                "last_row_utc": None, "gap_hours": None}
    last = _utc_str(last_row_retrieval_ts)
    gap_hours = (now - last).total_seconds() / 3600.0
    stale = gap_hours > max_expected_gap_hours
    return {"stale": stale, "last_row_utc": last.isoformat(),
            "gap_hours": round(gap_hours, 2),
            "max_expected_gap_hours": max_expected_gap_hours,
            "reason": (None if not stale else
                      f"last row {gap_hours:.1f}h ago exceeds max expected gap "
                      f"{max_expected_gap_hours}h")}


# ------------------------------------------------------------- helpers ----
def _utc(t) -> datetime:
    if isinstance(t, str):
        t = _utc_str(t)
        return t
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


def _utc_str(s: str) -> datetime:
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)
