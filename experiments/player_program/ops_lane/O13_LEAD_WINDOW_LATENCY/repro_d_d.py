"""O13_LEAD_WINDOW_LATENCY -- reproduction probe for defect D-d.

READ-ONLY. Imports prospective_pair.coverage_audit and calls audit() in memory.
It NEVER calls coverage_audit.main(), because main() writes
forecasts/coverage_audit.csv and forecasts/coverage_receipt.json into the live
repository, which is outside this node's write scope.

D-d as documented (experiments/player_program/PROJECT_UPDATE_2026-08-04.md:202):
    "Lead-window execution latency. Two records created 22:45:08Z against
     22:34 / 22:44 cutoffs. Distinct from D-b: discovery worked, execution was late."

Usage:  python repro_d_d.py <path-to-live-repo-root>
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main() -> int:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "prospective_pair"))
    import coverage_audit as CA  # noqa: E402
    from alt_model_log import read_official  # noqa: E402

    fail = 0

    # ---- 1. raw evidence: every official record vs its own nominal cutoff -------
    official = read_official()
    print("official chain records: %d" % len(official))
    labels = dict(CA.CONTRACT_LABELS)
    slate = CA.build_slate()
    prov = CA._resolve_provisional(official, slate)
    tip_by_gid = {str(g.game_id): g.tip for g in slate.itertuples()
                  if str(g.game_id) != "nan"}

    print("\nper-record latency (created_at - nominal cutoff), positive = LATE")
    late = []
    for i, r in enumerate(official):
        gid = prov.get(str(r["game_id"]), str(r["game_id"]))
        lab = r["decision_time_label"]
        tip = tip_by_gid.get(gid)
        if tip is None or lab not in labels:
            print("  idx %-3d %-12s %-12s tip/label not resolvable on slate" % (i, gid, lab))
            continue
        cutoff = tip - timedelta(hours=labels[lab])
        created = CA._utc(r["logged_at_utc"])
        delta_min = (created - cutoff).total_seconds() / 60.0
        flag = "LATE" if delta_min > 0 else ""
        print("  idx %-3d %-12s %-8s cutoff %s created %s  %+8.2f min %s"
              % (i, gid, lab, cutoff.isoformat(), created.isoformat(), delta_min, flag))
        if delta_min > 0:
            late.append({"record_idx": i, "game_id": gid, "label": lab,
                         "cutoff_utc": cutoff.isoformat(),
                         "created_utc": created.isoformat(),
                         "latency_minutes": round(delta_min, 2)})

    print("\nrecords created after their own nominal cutoff: %d" % len(late))
    print(json.dumps(late, indent=2))

    # ---- 2. auditor's own classification ---------------------------------------
    A = CA.audit()
    lr = A[A.classification == "late_record"]
    print("\nauditor late_record obligations: %d" % len(lr))
    for r in lr.itertuples():
        print("  %s %s v %s %-7s  %s" % (r.game_date, r.home, r.away,
                                         r.decision_time_label, r.reason))

    # ---- 3. the gate's own window arithmetic -----------------------------------
    # should_run_base.assess() admits an obligation when
    #     -0.5 <= minutes_to_cutoff <= LEAD (20)
    # so the gate can only FIRE up to 0.5 min after a cutoff. Any larger positive
    # latency in the chain must have accrued AFTER the gate said fire, i.e. inside
    # daily_forecast.py's own execution, not inside discovery.
    import should_run_base as SRB  # noqa: E402
    print("\nSRB.LEAD = %s ; admits minutes_to_cutoff in [-0.5, %.1f]"
          % (SRB.LEAD, SRB.LEAD.total_seconds() / 60))
    max_gate_lateness = 0.5
    beyond = [x for x in late if x["latency_minutes"] > max_gate_lateness]
    print("records later than the gate could possibly admit (%.1f min): %d"
          % (max_gate_lateness, len(beyond)))

    # ---- 4. assertions ---------------------------------------------------------
    if not late:
        print("\nRESULT: NO late records found -- D-d did NOT reproduce on this chain.")
        fail = 1
    else:
        print("\nRESULT: %d late record(s) found; %d exceed the gate's admissible "
              "lateness -- execution latency, not discovery." % (len(late), len(beyond)))
    return fail


if __name__ == "__main__":
    raise SystemExit(main())
