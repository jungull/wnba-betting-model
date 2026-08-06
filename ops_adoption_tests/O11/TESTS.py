"""O11 adoption tests -- ported from the research worktree's TESTS.py, now
pointed at the REAL patched module.

Source: experiments/player_program/ops_lane/O11_OBLIGATION_DISCOVERY_LEAD_WINDOW/TESTS.py

ADOPTION STATUS: APPLIED. prospective_pair/should_run_base.py now exists in
this adoption worktree (committed by the coordinator as a pre-patch
baseline) and PROPOSED_PATCH.diff has been applied to it verbatim. See
ADOPTION_NOTES.md in this directory for sha256 before/after and the full
record.

ADJUSTMENTS FROM THE ORIGINAL:
  * Sections 1-8 are the original design-verification checks against the
    pure-function reproduction in `./gate_logic.py` (`classify_original` /
    `classify_fixed`). These are kept unchanged -- they verify the *shape*
    of the fix independent of any live wiring.
  * A new Section 9 (replacing the old live-capture re-measurement, which
    depended on data only present in the live main worktree) drives the
    REAL `prospective_pair/should_run_base.py::assess()` -- imported
    directly from that file, not copied -- through the same fixture,
    by monkeypatching its `build_slate` / `read_official` dependencies
    (the only I/O boundary `assess()` has). This is the part that proves
    the patch landed correctly in the live module, not just in the
    isolated reproduction.
  * The old section 9 (live-capture re-measurement against
    C:/Users/jgallagher/wnba-betting-model) is still REMOVED. That path is
    the live main worktree, which this node must never touch, and
    measure_discovery_lag.py is not in this node's ownership set to port.
  * Everything else (fixture data, checks, structure) is unchanged.

Standalone (pytest is not installed). `python TESTS.py`; main() returns 1 on
any failure.
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from gate_logic import (  # noqa: E402
    CONTRACT_LABELS, LEAD, classify_fixed, classify_original, current_label,
    provisional_game_id, utc,
)

# --- wire up the REAL module under test -------------------------------------
REPO_ROOT = HERE.parent.parent          # .../o16-adoption
PP_DIR = REPO_ROOT / "prospective_pair"
sys.path.insert(0, str(PP_DIR))
sys.path.insert(0, str(REPO_ROOT))

import should_run_base as srb  # noqa: E402  -- the real, patched module

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  PASS  " if cond else "  FAIL  ") + name + (("  -- " + detail) if detail else ""))
    if not cond:
        FAILURES.append(name)


# ---------------------------------------------------------------- fixture ----
# tip and cutoffs: measured, DISCOVERY_LAG.csv rows 60-63 (research worktree).
TIP = utc("2026-08-05T02:00:00Z")
GSV_TOR_NO_ID = {"game_id": None, "tip": TIP, "home": "GSV", "away": "TOR",
                 "game_date": "2026-08-04"}
GSV_TOR_WITH_ID = {**GSV_TOR_NO_ID, "game_id": "1022600225"}

# firing instants: forecasts/runner_logs/pair_20260803.log:1996, 2093, 2190.
T0130 = utc("2026-08-04T01:30:05.128408Z")
T0145 = utc("2026-08-04T01:45:04.560181Z")
T0200 = utc("2026-08-04T02:00:05.384686Z")


def real_assess(slate_rows: list[dict], official: list[dict], now):
    """Call the REAL should_run_base.assess(), with its two I/O calls
    (build_slate, read_official) monkeypatched to the fixture. Everything
    downstream -- current_label, the window/dup logic, the reason string,
    the provisional-id fallback from the applied patch -- runs as the live
    module actually wrote it."""
    slate_df = pd.DataFrame(slate_rows)
    orig_build_slate, orig_read_official = srb.build_slate, srb.read_official
    srb.build_slate = lambda: slate_df
    srb.read_official = lambda: official
    try:
        return srb.assess(now)
    finally:
        srb.build_slate = orig_build_slate
        srb.read_official = orig_read_official


def main() -> int:
    print("O11_OBLIGATION_DISCOVERY_LEAD_WINDOW -- ADOPTION TESTS (ported, real module)")

    print("\n1. the T-24h obligation really was inside the lead window at 01:45")
    a = classify_fixed([GSV_TOR_WITH_ID], set(), T0145)
    it = a["upcoming"][0]
    check("label is T-24h", it["label"] == "T-24h", it["label"])
    check("cutoff is 2026-08-04T02:00:00", it["cutoff"].startswith("2026-08-04T02:00:00"),
          it["cutoff"])
    check("minutes_to_cutoff == 14.9 (the figure PROJECT_UPDATE:200 quotes)",
          it["minutes_to_cutoff"] == 14.9, str(it["minutes_to_cutoff"]))
    check("14.9 < 20-minute lead window", it["minutes_to_cutoff"] < LEAD.total_seconds() / 60)

    print("\n2. DEFECT REPRODUCES (pure repro): with no official game_id the "
          "unpatched shape declines silently")
    for nm, now in (("01:30", T0130), ("01:45", T0145), ("02:00", T0200)):
        o = classify_original([GSV_TOR_NO_ID], set(), now)
        check(f"{nm} fire is False", o["fire"] is False)
        check(f"{nm} reason blames the lead window",
              o["reason"].startswith("no unserved obligation inside its 20-minute lead window"))
        check(f"{nm} decline is SILENT: nothing printed for the game",
              o["upcoming"] == [] and o["new"] == [] and o["would_duplicate"] == [])

    print("\n3. the cause is identity, not timing: same instants, id present")
    check("01:30 still holds (29.9 min out, genuinely outside the window)",
          classify_original([GSV_TOR_WITH_ID], set(), T0130)["fire"] is False)
    check("01:45 WOULD have fired had the id existed",
          classify_original([GSV_TOR_WITH_ID], set(), T0145)["fire"] is True)
    check("02:00 WOULD have fired had the id existed",
          classify_original([GSV_TOR_WITH_ID], set(), T0200)["fire"] is True)

    print("\n4. FIX (pure repro): provisional identity restores the obligation")
    f = classify_fixed([GSV_TOR_NO_ID], set(), T0145)
    check("01:45 fires", f["fire"] is True, f["reason"])
    check("exactly one obligation in window", len(f["in_window"]) == 1)
    check("it is the T-24h obligation at 14.9 min",
          f["in_window"][0]["label"] == "T-24h"
          and f["in_window"][0]["minutes_to_cutoff"] == 14.9)
    check("it is flagged provisional", f["in_window"][0]["game_id_provisional"] is True)

    print("\n5. FIX (pure repro): 01:30 still correctly declines, and now the reason is TRUE")
    f = classify_fixed([GSV_TOR_NO_ID], set(), T0130)
    check("01:30 does not fire", f["fire"] is False)
    check("the game is now visible in upcoming", len(f["upcoming"]) == 1)
    check("29.9 min out", f["upcoming"][0]["minutes_to_cutoff"] == 29.9,
          str(f["upcoming"][0]["minutes_to_cutoff"]))
    check("reason names the unresolved id rather than hiding it",
          "provisional id" in f["reason"], f["reason"])

    print("\n6. FIX (pure repro): once served at 01:45, 02:00 does not write a second record")
    gid = provisional_game_id("2026-08-04", "GSV", "TOR")
    f = classify_fixed([GSV_TOR_NO_ID], {(gid, "T-24h")}, T0200)
    check("02:00 does not fire", f["fire"] is False)
    check("it is recognised as already served", len(f["would_duplicate"]) == 1)
    check("no duplicate would be appended", f["in_window"] == [])

    print("\n7. the provisional id round-trips through coverage_audit's parser")
    parts = gid.split("-", 4)
    check("format is PROV-<date>-<away>@<home>", gid == "PROV-2026-08-04-TOR@GSV", gid)
    check("coverage_audit.py:162-163 recovers the date",
          "-".join(parts[1:4]) == "2026-08-04")
    check("id is stable across firings",
          provisional_game_id("2026-08-04", "GSV", "TOR") == gid)

    print("\n8. NO REGRESSION (pure repro) when every game already has an official id")
    slate = [GSV_TOR_WITH_ID,
             {"game_id": "1022600226", "tip": utc("2026-08-04T23:00:00Z"),
              "home": "ATL", "away": "PHX", "game_date": "2026-08-04"}]
    for nm, now in (("01:30", T0130), ("01:45", T0145), ("02:00", T0200)):
        o = classify_original(slate, set(), now)
        f = classify_fixed(slate, set(), now)
        check(f"{nm} fire identical", o["fire"] == f["fire"])
        check(f"{nm} in_window identical",
              [i["game_id"] for i in o["in_window"]] == [i["game_id"] for i in f["in_window"]])
        check(f"{nm} no game reported unresolved", f["unresolved"] == [])
    check("current_label is untouched", current_label(24.25) == "T-24h"
          and current_label(12.0) == "T-8h" and current_label(0.4) == "T-30m")
    check("CONTRACT_LABELS unchanged",
          CONTRACT_LABELS == [("T-24h", 24.0), ("T-8h", 8.0), ("T-90m", 1.5), ("T-30m", 0.5)])
    check("LEAD unchanged", LEAD == timedelta(minutes=20))

    print("\n9. REAL MODULE: prospective_pair/should_run_base.py itself, patched")

    print("\n9a. real module: defect is FIXED -- no official id no longer declines silently")
    for nm, now in (("01:30", T0130), ("01:45", T0145), ("02:00", T0200)):
        r = real_assess([GSV_TOR_NO_ID], [], now)
        check(f"9a.{nm} real module reports the game in upcoming (not dropped)",
              len(r["upcoming"]) == 1, r["reason"])
        check(f"9a.{nm} real module flags it provisional",
              r["upcoming"][0]["game_id_provisional"] is True)

    print("\n9b. real module: 01:45 fires with the provisional id")
    r = real_assess([GSV_TOR_NO_ID], [], T0145)
    check("9b fire is True", r["fire"] is True, r["reason"])
    check("9b exactly one obligation in window", len(r["in_window"]) == 1)
    check("9b it is the T-24h obligation at 14.9 min",
          r["in_window"][0]["label"] == "T-24h"
          and r["in_window"][0]["minutes_to_cutoff"] == 14.9)
    check("9b provisional id matches the documented format",
          r["in_window"][0]["game_id"] == "PROV-2026-08-04-TOR@GSV",
          r["in_window"][0]["game_id"])

    print("\n9c. real module: 01:30 declines, but the reason is now TRUE (not the lead window)")
    r = real_assess([GSV_TOR_NO_ID], [], T0130)
    check("9c does not fire", r["fire"] is False)
    check("9c game is visible in upcoming (not silently dropped)", len(r["upcoming"]) == 1)
    check("9c reason names the unresolved provisional id",
          "provisional id" in r["reason"], r["reason"])
    check("9c reason names the game count examined",
          "1 upcoming game(s) examined" in r["reason"], r["reason"])

    print("\n9d. real module: DECLINE-REASON MASKING DEFECT is fixed for the "
          "duplicate-vs-lead-window case -- the duplicate reason must not silently "
          "outrank a true lead-window reason for a DIFFERENT game")
    # GSV v TOR already served (official record uses the provisional id, matching
    # what daily_forecast.py would have logged); ATL v PHX has an official id but
    # is genuinely outside the lead window. The overall decline must be reported
    # as a duplicate (correct: duplicate-of-existing-obligation info is real and
    # present), but the game outside the window must still be visible/explained,
    # not erased the way the pre-patch module erased provisional-id games.
    official_served = [{
        "game_id": "PROV-2026-08-04-TOR@GSV",
        "decision_time_label": "T-24h",
        "core_only_prediction": {"home_team": "GSV", "away_team": "TOR"},
    }]
    slate_mixed = [GSV_TOR_NO_ID,
                   {"game_id": "1022600226", "tip": utc("2026-08-04T23:00:00Z"),
                    "home": "ATL", "away": "PHX", "game_date": "2026-08-04"}]
    r = real_assess(slate_mixed, official_served, T0145)
    check("9d GSV v TOR recognised as already served (no duplicate write)",
          len(r["would_duplicate"]) == 1 and r["would_duplicate"][0]["game_id"]
          == "PROV-2026-08-04-TOR@GSV")
    check("9d ATL v PHX is visible in upcoming even though it's a different game",
          any(i["game"] == "ATL v PHX" for i in r["upcoming"]))
    check("9d does not fire (would duplicate the served obligation)", r["fire"] is False)

    print("\n9e. real module: NO REGRESSION when every game already has an official id")
    slate_ids = [GSV_TOR_WITH_ID,
                 {"game_id": "1022600226", "tip": utc("2026-08-04T23:00:00Z"),
                  "home": "ATL", "away": "PHX", "game_date": "2026-08-04"}]
    for nm, now in (("01:30", T0130), ("01:45", T0145), ("02:00", T0200)):
        r = real_assess(slate_ids, [], now)
        check(f"9e.{nm} no game reported unresolved", r["unresolved"] == [])
        check(f"9e.{nm} neither game flagged provisional",
              all(i["game_id_provisional"] is False for i in r["upcoming"]))

    print("\n9f. real module: LEAD / CONTRACT_LABELS / current_label untouched by the patch")
    check("9f LEAD unchanged", srb.LEAD == timedelta(minutes=20))
    check("9f current_label(24.25) == T-24h", srb.current_label(24.25) == "T-24h")
    check("9f current_label(12.0) == T-8h", srb.current_label(12.0) == "T-8h")
    check("9f current_label(0.4) == T-30m", srb.current_label(0.4) == "T-30m")

    print("\n%d check(s) failed" % len(FAILURES))
    for f_ in FAILURES:
        print("   - " + f_)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
