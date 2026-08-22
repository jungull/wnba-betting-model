# -*- coding: utf-8 -*-
"""M03 tests -- the node's validation_commands entry point.

These test the things that can actually go wrong, and several are written so they
FAIL if the property they check is removed. A test that cannot fail is worse than
the noisy check it replaced -- this programme has shipped two of those already
(D171), so each invariant here is exercised with a deliberate violation as well
as a conforming case.

Groups:
  A. schema additivity and required fields
  B. the fetch bracket (does it really bound retrieval?)
  C. no backdating / append-only
  D. quota arithmetic stays inside the tier
  E. the live archives still satisfy what we claim about them
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import capture_schema as cs  # noqa: E402

ROOT = r"C:\Users\jgallagher\wnba-betting-model"
ODDS_LOG = os.path.join(ROOT, "data", "odds_capture", "capture_log.csv")
PROPS_RAW = os.path.join(ROOT, "data", "props_capture", "raw")
HERE = os.path.dirname(os.path.abspath(__file__))

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %-4s %s%s" % ("ok" if cond else "FAIL", name,
                           ("  -- " + detail) if detail and not cond else ""))


# ---------------------------------------------------------------- A. schema
def test_schema():
    print("\nA. SCHEMA ADDITIVITY AND REQUIRED FIELDS")
    legacy = ["api_event_id", "player_name", "line", "snapshot_utc", "last_update"]
    up = cs.schema_for(legacy)
    check("every legacy column survives", all(c in up for c in legacy))
    check("legacy columns keep their positions", up[:len(legacy)] == legacy)
    check("all five required timing fields present",
          all(f in up for f in cs.REQUIRED_TIMING_FIELDS))
    check("upgrade is idempotent", cs.schema_for(up) == up)
    # negative: a schema missing a required field must be detectable
    broken = [c for c in up if c != "first_seen_utc"]
    check("a schema missing first_seen_utc is detected",
          not all(f in broken for f in cs.REQUIRED_TIMING_FIELDS))


# ------------------------------------------------------------ B. the bracket
def test_bracket():
    print("\nB. THE FETCH BRACKET BOUNDS RETRIEVAL")
    with cs.FetchWindow() as w:
        time.sleep(0.05)
    f = w.fields(vendor_reported_utc="2026-08-22T10:00:00Z")
    req, ret = cs.parse(f["fetch_requested_utc"]), cs.parse(f["fetch_returned_utc"])
    check("requested strictly precedes returned", req < ret)
    check("bracket covers the elapsed call", (ret - req).total_seconds() >= 0.05)
    check("vendor latency bound computed", isinstance(f["vendor_latency_bound_s"], float))
    check("vendor latency bound is positive for a past vendor stamp",
          f["vendor_latency_bound_s"] > 0)
    # the whole point: returned is a FAIL-CLOSED retrieval stamp, unlike a
    # cycle-start stamp which precedes the request entirely
    check("returned is at or after requested (fail-closed direction)", ret >= req)
    # negative: using the window before it closes must raise
    raised = False
    try:
        cs.FetchWindow().fields()
    except RuntimeError:
        raised = True
    check("unclosed window refuses to emit fields", raised)

    # a missing vendor stamp must degrade to blank, not to a wrong number
    f2 = w.fields(vendor_reported_utc=None)
    check("absent vendor stamp yields blank bound, not zero",
          f2["vendor_latency_bound_s"] == "")
    f3 = w.fields(vendor_reported_utc="not-a-timestamp")
    check("unparseable vendor stamp yields blank bound",
          f3["vendor_latency_bound_s"] == "")


# -------------------------------------------------------- C. no backdating
def test_no_backdating():
    print("\nC. NO BACKDATING / APPEND-ONLY")
    known = {}
    base = {"record_key": "evt1|dk|player_points|A. Player|12.5",
            "line": 12.5, "over_price": -110}

    r1 = dict(base, fetch_returned_utc="2026-08-22T10:00:00.000000Z")
    cs.apply_first_seen(r1, known)
    check("first observation sets first_seen",
          r1["first_seen_utc"] == "2026-08-22T10:00:00.000000Z")

    # same payload observed later -- first_seen must NOT move
    r2 = dict(base, fetch_returned_utc="2026-08-22T11:00:00.000000Z")
    cs.apply_first_seen(r2, known)
    check("re-observing an unchanged quote keeps the original first_seen",
          r2["first_seen_utc"] == "2026-08-22T10:00:00.000000Z")

    # and must not move BACKWARDS even if a stale response arrives late
    r3 = dict(base, fetch_returned_utc="2026-08-22T09:00:00.000000Z")
    cs.apply_first_seen(r3, known)
    check("an out-of-order observation cannot backdate first_seen",
          r3["first_seen_utc"] == "2026-08-22T10:00:00.000000Z")

    # a CHANGED payload is a new record, not an edit
    r4 = dict(base, over_price=-115,
              fetch_returned_utc="2026-08-22T12:00:00.000000Z")
    cs.apply_first_seen(r4, known)
    check("a changed price creates a new record with its own first_seen",
          r4["first_seen_utc"] == "2026-08-22T12:00:00.000000Z")
    check("the original record is untouched by the change",
          known[(base["record_key"], cs.payload_digest(r1))]
          == "2026-08-22T10:00:00.000000Z")

    # timing fields must not participate in the digest, or nothing would ever
    # be recognised as unchanged
    check("digest ignores timing fields",
          cs.payload_digest(r1) == cs.payload_digest(r2))
    check("digest reacts to an economic change",
          cs.payload_digest(r1) != cs.payload_digest(r4))


# ---------------------------------------------------------------- D. quota
def test_quota():
    print("\nD. QUOTA ARITHMETIC STAYS INSIDE THE TIER")
    mpath = os.path.join(HERE, "MEASUREMENTS.json")
    if not os.path.exists(mpath):
        check("MEASUREMENTS.json present (run s01_measure.py first)", False)
        return
    m = json.load(open(mpath, encoding="utf-8"))
    tier = 100_000
    check("observed usage is inside the tier", m["quota"]["per_30d"] < tier,
          "%d" % m["quota"]["per_30d"])
    check("observed usage is under 10% of tier", m["quota"]["pct_of_tier"] < 10.0)
    env = m["envelope"]
    rec = env["D: props 5-min in T-3h..tip"]
    check("recommended option fits on an expected day", rec["pct_expected"] < 100)
    check("recommended option fits on the WORST day", rec["pct_worst"] < 100,
          "%.1f%%" % rec["pct_worst"])
    check("recommended option leaves burst headroom (worst day under 75%)",
          rec["pct_worst"] < 75.0, "%.1f%%" % rec["pct_worst"])
    # the naive design must be shown to NOT fit -- if this ever passes, the
    # arithmetic has drifted and the recommendation is no longer motivated
    check("naive continuous polling does NOT fit (motivates targeting)",
          env["naive_continuous"]["pct_expected"] > 100,
          "%.1f%%" % env["naive_continuous"]["pct_expected"])
    check("games/day is measured, not the assumed 5.0",
          abs(m["quota"]["games_per_day_mean"] - 5.0) > 0.5)


# ------------------------------------------------------------ E. live claims
def test_live_archives():
    print("\nE. CLAIMS ABOUT THE LIVE ARCHIVES STILL HOLD")
    # the props cycle stamp really is one-per-cycle (the defect this node fixes)
    stamps = defaultdict(set)
    for f in glob.glob(os.path.join(PROPS_RAW, "props_*_*.json")):
        m = re.search(r"props_(.+?)_(\d{8}T\d{6}Z)\.json$", os.path.basename(f))
        if m:
            stamps[m.group(2)].add(m.group(1))
    check("props raw archive is readable", len(stamps) > 0)
    if stamps:
        multi = sum(1 for v in stamps.values() if len(v) > 1)
        check("cycles fetch several events under ONE stamp (the defect)", multi > 0,
              "%d cycles" % multi)

    check("odds capture log exists", os.path.exists(ODDS_LOG))
    if os.path.exists(ODDS_LOG):
        with open(ODDS_LOG, encoding="utf-8") as f:
            header = f.readline().strip().split(",")
        check("odds log lacks the required timing fields today",
              not all(x in header for x in cs.REQUIRED_TIMING_FIELDS))
        check("odds log retains snapshot_utc (what the upgrade must preserve)",
              "snapshot_utc" in header)


def main():
    print("=" * 78)
    print("M03_CAPTURE_UPGRADE -- tests")
    print("=" * 78)
    test_schema()
    test_bracket()
    test_no_backdating()
    test_quota()
    test_live_archives()
    print("\n" + "=" * 78)
    print("%d passed, %d failed" % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print("  FAILED: %s" % f)
        sys.exit(1)
    print("=" * 78)


if __name__ == "__main__":
    main()
