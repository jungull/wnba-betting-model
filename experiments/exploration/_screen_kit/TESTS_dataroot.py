"""TESTS_dataroot.py -- the D138 repoint.

Kept separate from the kit's own TESTS.py so the statistics suite and the environment suite
fail independently: a machine with no data root should not make the null-machinery tests red.

Run: python TESTS_dataroot.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import dataroot as dr

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS  " if cond else "  FAIL  ") + name + ("   " + detail if detail and not cond else ""))


print("--- 1. the inventory of what a worktree cannot see " + "-" * 28)
check("six sources are catalogued", len(dr.WORKTREE_INVISIBLE) == 6,
      str(len(dr.WORKTREE_INVISIBLE)))
for expected in ("odds_capture", "injury_official_live", "market_snapshots",
                 "drive_masters", "entity_resolution", "sxbet_capture"):
    check(f"catalogue names {expected}", expected in dr.WORKTREE_INVISIBLE)
check("every catalogued source carries a description",
      all(isinstance(v, str) and v for v in dr.WORKTREE_INVISIBLE.values()))

print("\n--- 2. resolution reaches the sources, not merely a data directory " + "-" * 12)
inv = dr.inventory()
check("a naive <repo>/data root is found at all", bool(inv["naive_root"]))
check("the report distinguishes the naive root from what is reachable",
      "naive_root_is_blind" in inv and "reachable_via_require" in inv)
if inv["naive_root_is_blind"]:
    check("inside a worktree the naive root is correctly diagnosed as blind",
          len(inv["naive_root_would_be_blind_to"]) > 0,
          "this is the D138 defect, detected rather than suffered")
check("require() reaches every catalogued source",
      not inv["unreachable"], f"unreachable: {inv['unreachable']}")
check("the warning text matches the blindness state",
      ("CANNOT REACH" in inv["warning"]) == bool(inv["unreachable"]))

print("\n--- 3. the failure mode is LOUD, which is the entire point " + "-" * 20)
try:
    dr.require("definitely_not_a_real_source_xyz")
    check("a missing source raises rather than returning None", False, "no exception")
except FileNotFoundError as e:
    msg = str(e)
    check("a missing source raises rather than returning None", True)
    check("the error lists every path that was tried", "Tried, in order:" in msg)
    check("the error names the environment override", "WNBA_DATA_ROOT" in msg)

try:
    dr.resolve(must_contain="definitely_not_a_real_source_xyz")
    check("resolve() with an unmet must_contain raises", False, "no exception")
except FileNotFoundError as e:
    check("resolve() with an unmet must_contain raises", True)
    check("that error refuses to call an environmental absence a repository fact",
          "ENVIRONMENTAL absence" in str(e))

# A catalogued source that is genuinely absent must say WHICH of the six it is.
with tempfile.TemporaryDirectory() as td:
    empty = Path(td) / "data"
    empty.mkdir()
    try:
        dr.require("odds_capture", explicit=empty)
        check("an explicitly empty root still raises for a catalogued source", False)
    except FileNotFoundError as e:
        check("an explicitly empty root still raises for a catalogued source", True)
        # explicit= is tried FIRST but resolution falls through to the real roots, so the
        # message may report success elsewhere; what must never happen is a silent None.
        check("the raise names the source", "odds_capture" in str(e))

print("\n--- 4. available() is the non-raising probe, and is honest " + "-" * 20)
check("available() is True for a reachable source", dr.available("odds_capture") is True)
check("available() is False for a fictional source",
      dr.available("definitely_not_a_real_source_xyz") is False)
check("available() and require() agree",
      dr.available("injury_official_live") == ("injury_official_live" in inv["reachable_via_require"]))

print("\n--- 5. the sources actually contain what the catalogue claims " + "-" * 17)
if not inv["unreachable"]:
    odds = dr.require("odds_capture")
    check("odds_capture holds live snapshots", any(odds.glob("live_*.json")))
    check("odds_capture holds a capture log", (odds / "capture_log.csv").exists())

    inj = dr.require("injury_official_live")
    check("injury capture holds status transitions",
          (inj / "status_transitions.csv").exists())
    check("injury capture holds provenance-tracked snapshots",
          (inj / "injury_snapshots.csv").exists())
    check("injury capture holds the raw source documents", (inj / "raw").is_dir())

    ms = dr.require("market_snapshots")
    check("market_snapshots holds the credit poll log", (ms / "poll_log.csv").exists())

print("\n--- 6. the module does not mutate anything " + "-" * 36)
src = Path(dr.__file__).read_text(encoding="utf-8")
for forbidden in ("shutil.rmtree", "os.remove", "unlink(", "write_text(", "mkdir("):
    check(f"dataroot never calls {forbidden}", forbidden not in src)

print("\n" + "=" * 78)
if FAIL:
    print(f"DATAROOT TESTS FAILED -- {len(FAIL)} of {len(PASS) + len(FAIL)}")
    for f in FAIL:
        print("   *", f)
    sys.exit(1)
print(f"DATAROOT TESTS PASSED -- {len(PASS)}/{len(PASS)} checks")
print("=" * 78)
