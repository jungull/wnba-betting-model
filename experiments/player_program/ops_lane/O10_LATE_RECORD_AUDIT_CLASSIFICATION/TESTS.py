"""TESTS.py — O10_LATE_RECORD_AUDIT_CLASSIFICATION.

Standalone (pytest is not installed). main() returns 1 on any failure.

    python experiments/player_program/ops_lane/O10_LATE_RECORD_AUDIT_CLASSIFICATION/TESTS.py

Sections
  A  reproduction against the frozen published coverage artifact (snapshot in evidence/)
  B  synthetic unit tests of the proposed served-evidence predicate
  C  invariants the fix must not break
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from late_record_evidence import (  # noqa: E402
    reclassify, served_at_timely, summarize, timely_buckets,
)

SNAP = HERE / "evidence" / "coverage_audit_snapshot.csv"
RECEIPT = HERE / "evidence" / "coverage_receipt_snapshot.json"

FAILURES: list[str] = []


def check(name, cond, detail=""):
    ok = bool(cond)
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        FAILURES.append(name)
    return ok


def _utc(t):
    if isinstance(t, str):
        t = datetime.fromisoformat(t.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


# ---------------------------------------------------------------- A
def section_a():
    print("\nA. reproduction against the frozen published artifact")
    if not SNAP.exists():
        check("A0 snapshot present", False, str(SNAP))
        return
    A = pd.read_csv(SNAP, dtype={"game_id": str})
    before = summarize(A)
    B = reclassify(A)
    after = summarize(B)

    check("A1 published artifact carries exactly 2 late_record rows",
          before["late_records"] == 2, f"late_records={before['late_records']}")
    check("A2 published artifact carries exactly 4 missing_data_unavailable rows",
          before["data_unavailable"] == 4, f"n={before['data_unavailable']}")
    check("A3 published operational_misses is 26",
          before["operational_misses"] == 26, f"n={before['operational_misses']}")

    # the specific obligation named in PROJECT_UPDATE_2026-08-04.md:558
    tgt = (A.game_date == "2026-08-03") & (A.home == "CHI") & (A.away == "PHX") \
        & (A.decision_time_label == "T-30m")
    check("A4 2026-08-03 PHX@CHI T-30m exists in the audit frame", int(tgt.sum()) == 1,
          f"rows={int(tgt.sum())}")
    if int(tgt.sum()) == 1:
        check("A5 ... and is published as missing_data_unavailable",
              A.loc[tgt, "classification"].iloc[0] == "missing_data_unavailable",
              A.loc[tgt, "classification"].iloc[0])
        bucket_all = A[(A.game_date == "2026-08-03")
                       & (A.decision_time_label == "T-30m")
                       & (A.n_base_records > 0)]
        check("A6 ... its only companion records at that (date,label) are 2, both late",
              len(bucket_all) == 2 and set(bucket_all.classification) == {"late_record"},
              f"n={len(bucket_all)} classes={sorted(set(bucket_all.classification))}")
        check("A7 DEFECT REPRODUCES: with the fix it becomes missing_job_did_not_run",
              B.loc[tgt, "classification"].iloc[0] == "missing_job_did_not_run",
              B.loc[tgt, "classification"].iloc[0])

    check("A8 operational misses move 26 -> 27",
          before["operational_misses"] == 26 and after["operational_misses"] == 27,
          f"{before['operational_misses']} -> {after['operational_misses']}")
    check("A9 data-unavailable moves 4 -> 3",
          before["data_unavailable"] == 4 and after["data_unavailable"] == 3,
          f"{before['data_unavailable']} -> {after['data_unavailable']}")
    check("A10 exactly one obligation is reclassified",
          int((A.classification.values != B.classification.values).sum()) == 1,
          str(int((A.classification.values != B.classification.values).sum())))
    check("A11 coverage_served is UNCHANGED by the fix",
          abs(before["coverage_served"] - after["coverage_served"]) < 1e-12,
          f"{before['coverage_served']:.10f} vs {after['coverage_served']:.10f}")
    check("A12 the surviving 3 data-unavailable rows each have a timely companion",
          all(len(timely_buckets(A).get((r.game_date, r.decision_time_label), set())) > 0
              for r in B[B.classification == "missing_data_unavailable"].itertuples()))
    check("A13 unexplained stays 0", after["unexplained"] == 0, str(after["unexplained"]))
    check("A14 late_record rows are themselves untouched",
          after["late_records"] == 2, str(after["late_records"]))

    if RECEIPT.exists():
        rec = json.loads(RECEIPT.read_text())
        check("A15 snapshot frame agrees with the published receipt",
              rec["operational_misses"] == before["operational_misses"]
              and rec["obligations_due"] == before["obligations_due"]
              and rec["served"] == before["served"],
              f"receipt misses={rec['operational_misses']} due={rec['obligations_due']}")


# ---------------------------------------------------------------- B
def _rec(gid, label, created):
    return {"game_id": gid, "decision_time_label": label, "logged_at_utc": created}


def section_b():
    print("\nB. synthetic unit tests of served_at_timely()")
    tip = _utc("2026-08-03T23:00:00Z")          # T-30m cutoff = 22:30Z
    gid_date = {"G1": "2026-08-03", "G2": "2026-08-03"}
    tip_by_gid = {"G1": tip, "G2": tip}
    prov = {"G1": "G1", "G2": "G2"}

    late = served_at_timely([_rec("G1", "T-30m", "2026-08-03T22:45:08Z")],
                            gid_date, tip_by_gid, prov, _utc)
    check("B1 a late record contributes NO served evidence", late == {}, str(late))

    timely = served_at_timely([_rec("G1", "T-30m", "2026-08-03T22:29:59Z")],
                              gid_date, tip_by_gid, prov, _utc)
    check("B2 a timely record contributes served evidence",
          timely == {("2026-08-03", "T-30m"): {"G1"}}, str(timely))

    exact = served_at_timely([_rec("G1", "T-30m", "2026-08-03T22:30:00Z")],
                             gid_date, tip_by_gid, prov, _utc)
    check("B3 exactly-at-cutoff counts as timely (same predicate as the late test, "
          "which is `created > cutoff`)",
          exact == {("2026-08-03", "T-30m"): {"G1"}}, str(exact))

    mixed = served_at_timely([_rec("G1", "T-30m", "2026-08-03T22:45:08Z"),
                              _rec("G2", "T-30m", "2026-08-03T22:00:00Z")],
                             gid_date, tip_by_gid, prov, _utc)
    check("B4 a mixed bucket keeps only the timely game",
          mixed == {("2026-08-03", "T-30m"): {"G2"}}, str(mixed))

    notip = served_at_timely([_rec("G3", "T-30m", "2026-08-03T22:00:00Z")],
                             {"G3": "2026-08-03"}, {}, {"G3": "G3"}, _utc)
    check("B5 fails closed when the tip is unknown", notip == {}, str(notip))

    badlab = served_at_timely([_rec("G1", "T-6h", "2026-08-03T12:00:00Z")],
                              gid_date, tip_by_gid, prov, _utc)
    check("B6 fails closed on an unknown decision-time label", badlab == {}, str(badlab))

    other = served_at_timely([_rec("G1", "T-8h", "2026-08-03T14:00:00Z")],
                             gid_date, tip_by_gid, prov, _utc)
    check("B7 evidence is keyed per label, not pooled across labels",
          other == {("2026-08-03", "T-8h"): {"G1"}}, str(other))


# ---------------------------------------------------------------- C
def _frame(rows):
    cols = ["game_date", "home", "away", "game_id", "decision_time_label",
            "n_base_records", "classification", "reason"]
    return pd.DataFrame(rows, columns=cols)


def section_c():
    print("\nC. invariants of reclassify()")
    # bucket where the only record is late -> the unserved obligation is an op miss
    f = _frame([
        ["2026-08-03", "A", "B", "G1", "T-30m", 1, "late_record", "created after cutoff"],
        ["2026-08-03", "C", "D", "G2", "T-30m", 0, "missing_data_unavailable",
         "job served 1 other game(s) on 2026-08-03 at T-30m"],
    ])
    r = reclassify(f)
    check("C1 late-only bucket promotes the gap to missing_job_did_not_run",
          list(r.classification) == ["late_record", "missing_job_did_not_run"],
          str(list(r.classification)))

    # bucket with a timely companion -> stands
    f2 = _frame([
        ["2026-08-03", "A", "B", "G1", "T-30m", 1, "forecast_logged", None],
        ["2026-08-03", "C", "D", "G2", "T-30m", 0, "missing_data_unavailable",
         "job served 1 other game(s) on 2026-08-03 at T-30m"],
    ])
    r2 = reclassify(f2)
    check("C2 a timely companion keeps missing_data_unavailable",
          list(r2.classification) == ["forecast_logged", "missing_data_unavailable"],
          str(list(r2.classification)))

    # an explicit decline is still evidence the job was alive
    f3 = _frame([
        ["2026-08-03", "A", "B", "G1", "T-30m", 1, "explicit_no_forecast", "no odds"],
        ["2026-08-03", "C", "D", "G2", "T-30m", 0, "missing_data_unavailable",
         "job served 1 other game(s) on 2026-08-03 at T-30m"],
    ])
    check("C3 explicit_no_forecast remains valid health evidence",
          list(reclassify(f3).classification)[1] == "missing_data_unavailable")

    # a mixed bucket (one late, one timely) stands
    f4 = _frame([
        ["2026-08-03", "A", "B", "G1", "T-30m", 1, "late_record", "created after cutoff"],
        ["2026-08-03", "E", "F", "G3", "T-30m", 1, "forecast_logged", None],
        ["2026-08-03", "C", "D", "G2", "T-30m", 0, "missing_data_unavailable",
         "job served 2 other game(s) on 2026-08-03 at T-30m"],
    ])
    check("C4 a mixed bucket keeps missing_data_unavailable",
          list(reclassify(f4).classification)[2] == "missing_data_unavailable")

    # evidence does not leak across dates or labels
    f5 = _frame([
        ["2026-08-02", "A", "B", "G1", "T-30m", 1, "forecast_logged", None],
        ["2026-08-03", "A", "B", "G1", "T-8h", 1, "forecast_logged", None],
        ["2026-08-03", "C", "D", "G2", "T-30m", 0, "missing_data_unavailable",
         "job served 1 other game(s) on 2026-08-03 at T-30m"],
    ])
    check("C5 health evidence does not leak across date or label",
          list(reclassify(f5).classification)[2] == "missing_job_did_not_run")

    # missing_job_did_not_run is never demoted
    f6 = _frame([
        ["2026-08-03", "A", "B", "G1", "T-30m", 1, "forecast_logged", None],
        ["2026-08-03", "C", "D", "G2", "T-30m", 0, "missing_job_did_not_run",
         "no base record for ANY game"],
    ])
    check("C6 the fix never turns an operational miss back into a data gap",
          list(reclassify(f6).classification)[1] == "missing_job_did_not_run")

    # idempotence
    r7 = reclassify(f)
    check("C7 reclassify is idempotent",
          list(reclassify(r7).classification) == list(r7.classification))

    # no row is dropped or added
    check("C8 row count and ordering are preserved",
          len(r) == len(f) and list(r.game_id) == list(f.game_id))


def main() -> int:
    print("=" * 78)
    print("O10_LATE_RECORD_AUDIT_CLASSIFICATION — TESTS")
    print("=" * 78)
    section_a()
    section_b()
    section_c()
    print("\n" + "=" * 78)
    if FAILURES:
        print("FAILED (%d): %s" % (len(FAILURES), "; ".join(FAILURES)))
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
