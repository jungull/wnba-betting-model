"""O10 — late-record evidence test for the forecast-coverage auditor.

ISOLATED. Nothing here is imported by, or patched into, any shared file. The shared
auditor (`prospective_pair/coverage_audit.py`, team-thread owned) is NOT edited by this
node; the proposed source change is carried as text in PROPOSED_PATCH.diff and as
`served_at_timely()` below, which is the drop-in replacement for the `served_at`
construction at coverage_audit.py:189-194.

THE DEFECT (documented as D-a in
experiments/player_program/PROJECT_UPDATE_2026-08-04.md:199)

    coverage_audit.py builds `served_at[(slate_date, label)]` from EVERY base record,
    with no timeliness test:

        for r in official:                                   # :190
            rgid = prov.get(str(r["game_id"]), str(r["game_id"]))
            d = gid_date.get(rgid)
            if d is not None:
                served_at.setdefault((d, r["decision_time_label"]), set()).add(rgid)

    That same record, viewed as its own obligation, may be classified `late_record`
    at :227-228 because it was created after its own cutoff. So a record the auditor
    itself refuses to count as SERVED (`SERVED` at :253 is forecast_logged /
    explicit_no_forecast only) is still admitted as proof that the job was healthy at
    that (date, label) — which downgrades an unserved obligation from
    `missing_job_did_not_run` (an operational miss) to `missing_data_unavailable`
    (a benign game-specific gap) at :242-248.

THE FIX

    A record is evidence the job was alive at a label only if it was created at or
    before that label's cutoff. Same predicate as the `late_record` test at :227, so
    the two tests cannot disagree. Anything whose timeliness cannot be established
    (no tip, unknown label) is excluded — fail closed, in the direction that reports
    the miss rather than hides it.

WHAT THE FIX DOES NOT DO

    It does not change how an obligation that HAS a record is classified: a late
    record still classifies its own obligation as `late_record`. It does not change
    `coverage_served`, because `missing_job_did_not_run` and `missing_data_unavailable`
    are both in DUE (:255) and both outside SERVED (:253). It only moves obligations
    between two non-served classes, and therefore only moves `operational_misses`.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

# label -> hours before tip, mirroring coverage_audit.CONTRACT_LABELS (:47)
LABEL_HOURS = {"T-24h": 24.0, "T-8h": 8.0, "T-90m": 1.5, "T-30m": 0.5}

SERVED = ("forecast_logged", "explicit_no_forecast")
EXCLUDED = ("not_yet_due", "before_period_start", "postponed_or_tip_changed")
DUE = SERVED + ("missing_job_did_not_run", "missing_data_unavailable", "late_record")


# --------------------------------------------------------------------------
# 1. The proposed source change, in the form it would take inside audit().
# --------------------------------------------------------------------------
def served_at_timely(official, gid_date, tip_by_gid, prov, utc):
    """Drop-in replacement for coverage_audit.py:189-194.

    Parameters mirror the local names already present in `audit()`:
      official   list of base records (read_official())
      gid_date   {game_id -> slate ET date}
      tip_by_gid {game_id -> tip datetime}   (NEW: built from the same slate frame)
      prov       provisional-id resolution map (_resolve_provisional)
      utc        coverage_audit._utc

    Returns {(slate_date, label) -> set(game_id)} containing only records created at
    or before their own cutoff.
    """
    served_at: dict[tuple, set] = {}
    for r in official:
        rgid = prov.get(str(r["game_id"]), str(r["game_id"]))
        d = gid_date.get(rgid)
        if d is None:
            continue
        label = r["decision_time_label"]
        hrs = LABEL_HOURS.get(label)
        tip = tip_by_gid.get(rgid)
        if hrs is None or tip is None:
            # timeliness not establishable -> not evidence of health. Fail closed.
            continue
        if utc(r["logged_at_utc"]) > tip - timedelta(hours=hrs):
            # a late record is not evidence the job was alive at this label
            continue
        served_at.setdefault((d, label), set()).add(rgid)
    return served_at


# --------------------------------------------------------------------------
# 2. The same rule applied to an already-produced audit frame, so the effect can
#    be measured against the frozen published artifact without re-running (and
#    without the auditor's side effects, which write into the repo-root worktree).
# --------------------------------------------------------------------------
def timely_buckets(A: pd.DataFrame) -> dict:
    """{(game_date, label) -> set(game_id)} of games with a TIMELY base record.

    Derived from the audit frame: a row carries a base record iff n_base_records > 0,
    and that record is late iff the row is classified `late_record`. This relies on
    the auditor's own stated invariant that `recs` is in chain (creation) order and
    recs[0] is the original (coverage_audit.py:216-218) — so if recs[0] is late, no
    later record for that obligation can be timely.
    """
    out: dict[tuple, set] = {}
    for r in A.itertuples():
        if int(r.n_base_records) <= 0:
            continue
        if r.classification == "late_record":
            continue
        out.setdefault((r.game_date, r.decision_time_label), set()).add(str(r.game_id))
    return out


def reclassify(A: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of the audit frame with D-a corrected.

    Only `missing_data_unavailable` rows can move, and only to
    `missing_job_did_not_run`. Every other classification is left byte-identical.
    """
    B = A.copy()
    buckets = timely_buckets(A)
    new_cls, new_reason = [], []
    for r in B.itertuples():
        cls, why = r.classification, r.reason
        if cls == "missing_data_unavailable":
            b = buckets.get((r.game_date, r.decision_time_label), set())
            if not b:
                cls = "missing_job_did_not_run"
                why = ("no TIMELY base record for ANY game on %s at %s"
                       % (r.game_date, r.decision_time_label))
            else:
                why = ("job served %d other game(s) timely on %s at %s"
                       % (len(b), r.game_date, r.decision_time_label))
        new_cls.append(cls)
        new_reason.append(why)
    B["classification"] = new_cls
    B["reason"] = new_reason
    return B


def summarize(A: pd.DataFrame) -> dict:
    """coverage_audit.summarize (:258-280), reimplemented so the corrected frame can
    be summarized without importing the shared module."""
    due = A[A.classification.isin(DUE)]
    served = due[due.classification.isin(SERVED)]
    misses = int((A.classification == "missing_job_did_not_run").sum())
    unexplained = int(due[~due.classification.isin(SERVED) & due.reason.isna()].shape[0])
    cov = (len(served) / len(due)) if len(due) else None
    return {
        "obligations_total": int(len(A)),
        "obligations_due": int(len(due)),
        "served": int(len(served)),
        "coverage_served": cov,
        "not_yet_due": int((A.classification == "not_yet_due").sum()),
        "data_unavailable": int((A.classification == "missing_data_unavailable").sum()),
        "late_records": int((A.classification == "late_record").sum()),
        "operational_misses": misses,
        "unexplained": unexplained,
    }
