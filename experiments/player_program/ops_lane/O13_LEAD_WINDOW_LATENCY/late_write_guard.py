"""O13_LEAD_WINDOW_LATENCY -- proposed fix, implemented in isolation.

NOT WIRED INTO ANYTHING. This module is a self-contained design, tested by
TESTS.py in the same directory. It touches no shared file, no scheduler, and no
frozen artifact. Adoption is a decision for the operations owner, not this node.

WHAT THE MEASUREMENT SHOWED (see REPORT.md for the citations)

    The two records the project update calls "lead-window execution latency"
    (D-d) were NOT produced by the gated 15-minute path. `should_run_base.py`
    evaluated 2.4 s earlier and declined. They were produced by a SECOND,
    independent scheduled task that fires at a fixed wall-clock time and never
    calls the gate. So the documented remediation target -- an amendment to
    `should_run_base.py` -- cannot fix them: the writer never reads it.

    Enforcement therefore has to sit at the WRITE, not at the discovery gate.
    That is exactly the rule the companion arm log already enforces
    (alt_model_log.py "NEVER LATE"); the official chain has no equivalent.

TWO INDEPENDENT RULES

    G1  refuse_late(created, cutoff)
        A base record whose creation instant is at or after its own cutoff
        carries information the cutoff excludes. Refuse the write. This is a
        write-site guard, correct no matter which process is writing and no
        matter what schedule invoked it.

    G2  asof_cutoff(tip_history, at)
        Lateness must be judged against the cutoff implied by the tip that was
        KNOWN when the record was written, not the latest tip. Judging against
        the latest tip lets a later upstream tip revision retroactively convert
        an on-time record into a late one -- which is what happened to one of
        the two D-d records. G2 is only the *arithmetic*; adopting it changes
        the auditor's classification contract and is therefore PROPOSED, never
        merged, from this lane.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Sequence, Tuple

#: the four registered decision times, hours before tip. Mirrored here rather
#: than imported so this module has no dependency on a shared file.
CONTRACT_LABELS = (("T-24h", 24.0), ("T-8h", 8.0), ("T-90m", 1.5), ("T-30m", 0.5))
LABEL_HOURS = dict(CONTRACT_LABELS)


def _utc(t) -> datetime:
    if isinstance(t, str):
        t = datetime.fromisoformat(t.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


def cutoff_for(tip, label: str) -> datetime:
    """The nominal cutoff for one (tip, registered label)."""
    if label not in LABEL_HOURS:
        raise ValueError(f"unregistered decision time {label!r}")
    return _utc(tip) - timedelta(hours=LABEL_HOURS[label])


def refuse_late(created, cutoff) -> Tuple[bool, Optional[str]]:
    """G1. Returns (allowed, refusal_reason).

    Strictly at-or-after the cutoff is refused. A record written exactly ON the
    cutoff instant already saw the cutoff instant, so it is refused too; the
    boundary is closed against the write, which is the conservative side.
    """
    created, cutoff = _utc(created), _utc(cutoff)
    if created >= cutoff:
        late_min = (created - cutoff).total_seconds() / 60.0
        return False, (f"created {created.isoformat()} is {late_min:.2f} min at or after "
                       f"its own cutoff {cutoff.isoformat()}; a forecast made after its "
                       f"cutoff carries information the cutoff excludes")
    return True, None


def asof_cutoff(tip_history: Sequence[Tuple[datetime, datetime]], label: str, at) -> Optional[datetime]:
    """G2. Cutoff implied by the newest tip observed AT OR BEFORE `at`.

    `tip_history` is [(capture_time, tip), ...] in any order. Returns None if no
    capture predates `at` -- meaning no cutoff was knowable then, which is itself
    a reportable state and must not be silently replaced by the latest tip.
    """
    at = _utc(at)
    seen = [(_utc(c), _utc(t)) for c, t in tip_history if _utc(c) <= at]
    if not seen:
        return None
    return cutoff_for(max(seen, key=lambda ct: ct[0])[1], label)


def classify_write(created, tip_history: Sequence[Tuple[datetime, datetime]],
                   label: str, latest_tip=None) -> dict:
    """Full verdict for one candidate or existing base record.

    `asof_late`   -- was it late against what was KNOWN at write time?  (honest)
    `latest_late` -- is it late against the newest tip?                 (auditor today)
    A record with latest_late and not asof_late was made late by an upstream tip
    revision, not by the writer. That distinction is the whole point of G2.
    """
    created = _utc(created)
    a_cut = asof_cutoff(tip_history, label, created)
    l_tip = latest_tip if latest_tip is not None else (
        max(tip_history, key=lambda ct: _utc(ct[0]))[1] if tip_history else None)
    l_cut = cutoff_for(l_tip, label) if l_tip is not None else None
    allowed, why = (True, None) if a_cut is None else refuse_late(created, a_cut)
    return {
        "created_utc": created.isoformat(),
        "asof_cutoff_utc": a_cut.isoformat() if a_cut else None,
        "latest_cutoff_utc": l_cut.isoformat() if l_cut else None,
        "asof_late": (None if a_cut is None else created >= a_cut),
        "latest_late": (None if l_cut is None else created >= l_cut),
        "asof_minutes": (None if a_cut is None
                         else round((created - a_cut).total_seconds() / 60, 2)),
        "latest_minutes": (None if l_cut is None
                           else round((created - l_cut).total_seconds() / 60, 2)),
        "guard_allows_write": allowed,
        "guard_refusal_reason": why,
        "retroactively_relabelled": bool(
            a_cut is not None and l_cut is not None
            and (created >= l_cut) and not (created >= a_cut)),
    }
