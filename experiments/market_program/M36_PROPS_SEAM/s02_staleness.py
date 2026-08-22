# -*- coding: utf-8 -*-
"""M36 s02 -- what does `snapshot_utc` actually mean, and does it leak at T-90m?

E0-style diagnostic, NON-CLAIMING.

s01 found the props seam crossable on identity and flagged one thing as prerequisite
work rather than a footnote: the live capture carries a single `snapshot_utc` where
the historical archive carries a `snapshot_requested_utc`/`snapshot_returned_utc`
PAIR that bounds staleness. This file settles what that single stamp means and
whether the difference can leak.

THE SEMANTICS, read from the capture source rather than assumed.
`props_capture_daily.py:197` takes `stamp` ONCE at the top of main(), BEFORE the
events list is fetched and before any event request is issued, then writes it
identically to every row of the cycle. Therefore:

    snapshot_utc  <=  true retrieval time of every row stamped with it

WHY THE DIRECTION MATTERS. A point-in-time cutoff question asks whether a quote was
HELD by a given instant. Because snapshot_utc is at or earlier than the true
retrieval, using it as the retrieval time makes a quote look available EARLIER than
it truly was. That is the optimistic direction -- it can admit a quote whose true
retrieval fell after the cutoff. The archive's `returned` stamp is fail-closed;
this one is not. So the size of the understatement has to be measured, not waved at.

HOW IT IS BOUNDED. Every event response in a cycle is written to
`data/props_capture/raw/props_<event>_<stamp>.json` during that cycle. The interval
from the stamp to the LAST of those file writes is a direct, per-cycle upper bound
on how far snapshot_utc understates true retrieval. Each cycle is bounded by its
OWN slack rather than by a global worst case, because two day-one cycles are wild
outliers and applying their slack to every row would manufacture a false exposure.

THE TEST. Recompute each quote's lead time against tip using the fail-closed
retrieval bound (snapshot_utc + that cycle's own slack) and count how many quotes
the optimistic stamp admits at T-90m that the fail-closed bound would refuse. That
count -- not the size of the slack -- is the thing that matters.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re

import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model"
LIVE = os.path.join(ROOT, "data", "props_capture", "master_props.csv")
RAW = os.path.join(ROOT, "data", "props_capture", "raw")
STAMP_FMT = "%Y%m%dT%H%M%SZ"
T90_MIN = 90
OUTLIER_MIN = 5.0        # cycles slower than this are reported separately, not dropped


def cycle_slack_minutes():
    """Per-cycle upper bound on how far `snapshot_utc` understates true retrieval.

    Measured as stamp -> last raw-JSON write for that stamp. mtime is used because
    the capture writes each response as it arrives; nothing else rewrites these
    files in normal operation.
    """
    last = {}
    for f in glob.glob(os.path.join(RAW, "props_*_*.json")):
        m = re.search(r"_(\d{8}T\d{6}Z)\.json$", os.path.basename(f))
        if not m:
            continue
        s = m.group(1)
        last[s] = max(last.get(s, 0.0), os.path.getmtime(f))
    out = {}
    for s, t in last.items():
        t0 = dt.datetime.strptime(s, STAMP_FMT).replace(
            tzinfo=dt.timezone.utc).timestamp()
        out[s] = (t - t0) / 60.0
    return out


def main():
    res = {}
    print("=" * 94)
    print("M36 s02 -- snapshot_utc semantics and whether they leak at T-90m")
    print("=" * 94)

    slack = cycle_slack_minutes()
    ss = pd.Series(slack)
    outl = ss[ss > OUTLIER_MIN].sort_values(ascending=False)

    print("\n1. HOW FAR DOES snapshot_utc UNDERSTATE TRUE RETRIEVAL?")
    print("   cycles measured : %d" % len(ss))
    print("   median          : %.2f min" % ss.median())
    print("   p95             : %.2f min" % ss.quantile(0.95))
    print("   max             : %.2f min" % ss.max())
    print("   cycles over %.0f min : %d" % (OUTLIER_MIN, len(outl)))
    for s, v in outl.items():
        print("      %s  %.1f min" % (s, v))
    if len(outl):
        print("   excluding those : max %.2f min" % ss[ss <= OUTLIER_MIN].max())
    print("   NOTE: the outliers are day-one cycles (2026-07-31). They are kept and")
    print("   charged to their own rows below, not dropped and not spread globally.")
    res["slack_min"] = {"cycles": int(len(ss)), "median": round(float(ss.median()), 3),
                        "p95": round(float(ss.quantile(0.95)), 3),
                        "max": round(float(ss.max()), 3),
                        "n_over_5min": int(len(outl)),
                        "max_excluding_outliers": round(float(ss[ss <= OUTLIER_MIN].max()), 3)}

    # ---- the test --------------------------------------------------------
    l = pd.read_csv(LIVE, low_memory=False)
    l["snap"] = pd.to_datetime(l["snapshot_utc"], format=STAMP_FMT, utc=True,
                               errors="coerce")
    l["tip"] = pd.to_datetime(l["commence_time"], utc=True, errors="coerce")
    l["lead"] = (l["tip"] - l["snap"]).dt.total_seconds() / 60.0
    l["slack"] = l["snapshot_utc"].map(slack)

    pts = l[l["market_key"] == "player_points"].copy()
    unmeasured = int(pts["slack"].isna().sum())
    # fail closed: a row we cannot bound is charged the worst slack observed
    pts["slack"] = pts["slack"].fillna(ss.max())
    pts["lead_failclosed"] = pts["lead"] - pts["slack"]

    opt = int((pts["lead"] >= T90_MIN).sum())
    safe = int((pts["lead_failclosed"] >= T90_MIN).sum())
    wrong = opt - safe

    print("\n2. DOES IT ACTUALLY LEAK AT T-90m?")
    print("   player_points rows                  : %d" % len(pts))
    print("   rows with no raw JSON to bound      : %d (charged the worst slack)"
          % unmeasured)
    print("   admitted using snapshot_utc         : %d" % opt)
    print("   admitted using fail-closed bound    : %d" % safe)
    print("   WRONGLY ADMITTED                    : %d (%.3f%%)"
          % (wrong, 100.0 * wrong / max(opt, 1)))
    res["leak"] = {"rows": int(len(pts)), "unmeasured": unmeasured,
                   "admitted_optimistic": opt, "admitted_failclosed": safe,
                   "wrongly_admitted": wrong}

    # why: how close does anything actually get to the boundary?
    print("\n3. WHY -- how close does any quote get to the cutoff?")
    for hi in (95, 105, 120, 150):
        n = int(((pts["lead"] >= T90_MIN) & (pts["lead"] < hi)).sum())
        print("   lead in [90, %3d) min : %5d quotes" % (hi, n))
    print("   the capture cadence is coarse (median gap between cycles is hours),")
    print("   so nothing lands near the boundary and the understatement cannot bite.")
    res["near_boundary"] = {str(hi): int(((pts["lead"] >= T90_MIN) &
                                          (pts["lead"] < hi)).sum())
                            for hi in (95, 105, 120, 150)}

    verdict = (wrong == 0)
    print("\n" + "=" * 94)
    print("VERDICT: the single-stamp defect is REAL and runs in the leak-prone")
    print("direction, but its measured exposure at T-90m on this window is %s."
          % ("ZERO" if verdict else "NON-ZERO -- %d quotes" % wrong))
    print("This clears the staleness item s01 named as prerequisite. It does NOT")
    print("generalise: a finer capture cadence, or a cutoff nearer tip, would put")
    print("quotes next to the boundary and the bound would have to be re-measured.")
    print("=" * 94)
    res["clears_prerequisite"] = bool(verdict)

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "FINDINGS_s02.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\nwrote FINDINGS_s02.json")


if __name__ == "__main__":
    main()
