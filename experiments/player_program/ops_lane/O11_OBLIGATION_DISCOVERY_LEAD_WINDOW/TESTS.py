"""O11 tests — reproduce defect D-b and verify the candidate fix.

Standalone (pytest is not installed). `python TESTS.py`; main() returns 1 on any
failure. The fixture is the real 2026-08-04 GSV v TOR case named in
experiments/player_program/PROJECT_UPDATE_2026-08-04.md:200, with the tip time,
cutoffs and firing instants taken from measured data (see REPORT.md §2).

Section 9 additionally re-measures against the live capture data if it is
present; it SKIPS (does not fail) when it is not, because that data lives in a
different worktree and this node may not depend on its presence.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from gate_logic import (  # noqa: E402
    CONTRACT_LABELS, LEAD, classify_fixed, classify_original, current_label,
    provisional_game_id, utc,
)

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  PASS  " if cond else "  FAIL  ") + name + (("  -- " + detail) if detail else ""))
    if not cond:
        FAILURES.append(name)


# ---------------------------------------------------------------- fixture ----
# tip and cutoffs: measured, DISCOVERY_LAG.csv rows 60-63.
TIP = utc("2026-08-05T02:00:00Z")
GSV_TOR_NO_ID = {"game_id": None, "tip": TIP, "home": "GSV", "away": "TOR",
                 "game_date": "2026-08-04"}
GSV_TOR_WITH_ID = {**GSV_TOR_NO_ID, "game_id": "1022600225"}

# firing instants: forecasts/runner_logs/pair_20260803.log:1996, 2093, 2190.
T0130 = utc("2026-08-04T01:30:05.128408Z")
T0145 = utc("2026-08-04T01:45:04.560181Z")
T0200 = utc("2026-08-04T02:00:05.384686Z")


def main() -> int:
    print("O11_OBLIGATION_DISCOVERY_LEAD_WINDOW -- TESTS")

    print("\n1. the T-24h obligation really was inside the lead window at 01:45")
    a = classify_fixed([GSV_TOR_WITH_ID], set(), T0145)
    it = a["upcoming"][0]
    check("label is T-24h", it["label"] == "T-24h", it["label"])
    check("cutoff is 2026-08-04T02:00:00", it["cutoff"].startswith("2026-08-04T02:00:00"),
          it["cutoff"])
    check("minutes_to_cutoff == 14.9 (the figure PROJECT_UPDATE:200 quotes)",
          it["minutes_to_cutoff"] == 14.9, str(it["minutes_to_cutoff"]))
    check("14.9 < 20-minute lead window", it["minutes_to_cutoff"] < LEAD.total_seconds() / 60)

    print("\n2. DEFECT REPRODUCES: with no official game_id the current gate declines")
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

    print("\n4. FIX: provisional identity restores the obligation")
    f = classify_fixed([GSV_TOR_NO_ID], set(), T0145)
    check("01:45 fires", f["fire"] is True, f["reason"])
    check("exactly one obligation in window", len(f["in_window"]) == 1)
    check("it is the T-24h obligation at 14.9 min",
          f["in_window"][0]["label"] == "T-24h"
          and f["in_window"][0]["minutes_to_cutoff"] == 14.9)
    check("it is flagged provisional", f["in_window"][0]["game_id_provisional"] is True)

    print("\n5. FIX: 01:30 still correctly declines, and now the reason is TRUE")
    f = classify_fixed([GSV_TOR_NO_ID], set(), T0130)
    check("01:30 does not fire", f["fire"] is False)
    check("the game is now visible in upcoming", len(f["upcoming"]) == 1)
    check("29.9 min out", f["upcoming"][0]["minutes_to_cutoff"] == 29.9,
          str(f["upcoming"][0]["minutes_to_cutoff"]))
    check("reason names the unresolved id rather than hiding it",
          "provisional id" in f["reason"], f["reason"])

    print("\n6. FIX: once served at 01:45, 02:00 does not write a second record")
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

    print("\n8. NO REGRESSION when every game already has an official id")
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

    print("\n9. live capture data (SKIPPED if absent -- different worktree)")
    repo = Path("C:/Users/jgallagher/wnba-betting-model")
    if not (repo / "data" / "odds_capture").exists():
        print("  SKIP  no data/odds_capture at %s" % repo)
    else:
        r = subprocess.run([sys.executable, str(HERE / "measure_discovery_lag.py"),
                            "--repo", str(repo)], capture_output=True, text=True)
        ok = r.returncode == 0
        check("measure_discovery_lag.py runs", ok, r.stderr[-300:])
        if ok:
            import json as _json
            s = _json.loads(r.stdout[:r.stdout.index("\nPER-GAME")])
            check("no T-24h obligation was discoverable before its cutoff",
                  s["by_label"]["T-24h"]["discoverable_before_cutoff"] == 0,
                  str(s["by_label"]["T-24h"]))
            check("the T-24h failure is total, not sporadic",
                  s["by_label"]["T-24h"]["not_discoverable"] == s["by_label"]["T-24h"]["n"],
                  str(s["by_label"]["T-24h"]))

    print("\n%d check(s) failed" % len(FAILURES))
    for f_ in FAILURES:
        print("   - " + f_)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
