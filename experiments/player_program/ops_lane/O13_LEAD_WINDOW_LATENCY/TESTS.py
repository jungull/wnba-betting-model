"""O13_LEAD_WINDOW_LATENCY -- tests for the proposed fix. Standalone; no pytest.

    python TESTS.py                 # synthetic tests only
    python TESTS.py <live-repo>     # synthetic tests + replay against the real chain

Returns 1 on any failure. Writes nothing anywhere.
"""
from __future__ import annotations

import glob
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from late_write_guard import (  # noqa: E402
    asof_cutoff, classify_write, cutoff_for, refuse_late,
)

UTC = timezone.utc
FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  PASS  " if cond else "  FAIL  ") + name + (("  -- " + detail) if detail else ""))
    if not cond:
        FAILURES.append(name)


def T(*a) -> datetime:
    return datetime(*a, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# 1. synthetic: cutoff arithmetic
# --------------------------------------------------------------------------- #
def test_cutoff_arithmetic() -> None:
    print("\n[1] cutoff arithmetic")
    tip = T(2026, 8, 3, 23, 4)
    check("T-30m", cutoff_for(tip, "T-30m") == T(2026, 8, 3, 22, 34))
    check("T-90m", cutoff_for(tip, "T-90m") == T(2026, 8, 3, 21, 34))
    check("T-8h", cutoff_for(tip, "T-8h") == T(2026, 8, 3, 15, 4))
    check("T-24h", cutoff_for(tip, "T-24h") == T(2026, 8, 2, 23, 4))
    try:
        cutoff_for(tip, "T-45m")
        check("unregistered label rejected", False, "no exception raised")
    except ValueError:
        check("unregistered label rejected", True)


# --------------------------------------------------------------------------- #
# 2. synthetic: G1 write guard
# --------------------------------------------------------------------------- #
def test_refuse_late() -> None:
    print("\n[2] G1 refuse_late")
    cut = T(2026, 8, 3, 22, 34)
    ok, _ = refuse_late(cut - timedelta(seconds=1), cut)
    check("one second before cutoff is allowed", ok)
    ok, why = refuse_late(cut, cut)
    check("exactly on the cutoff is refused", not ok, "boundary closed against the write")
    ok, why = refuse_late(cut + timedelta(minutes=11, seconds=9), cut)
    check("11.15 min late is refused", not ok)
    check("refusal carries a reason", bool(why) and "after its own cutoff" in why)
    # naive datetimes must be coerced, not crash
    ok, _ = refuse_late(datetime(2026, 8, 3, 22, 33), cut)
    check("naive datetime coerced to UTC", ok)


# --------------------------------------------------------------------------- #
# 3. synthetic: G2 as-of cutoff
# --------------------------------------------------------------------------- #
def test_asof_cutoff() -> None:
    print("\n[3] G2 asof_cutoff")
    hist = [(T(2026, 8, 2, 0, 0), T(2026, 8, 3, 23, 30)),      # believed at write time
            (T(2026, 8, 3, 23, 0), T(2026, 8, 3, 23, 0)),      # revised AFTER the write
            (T(2026, 8, 4, 0, 0), T(2026, 8, 3, 23, 14))]
    at = T(2026, 8, 3, 22, 45)
    check("uses newest capture at or before `at`",
          asof_cutoff(hist, "T-30m", at) == T(2026, 8, 3, 23, 0))
    check("later captures are invisible to an earlier `at`",
          asof_cutoff(hist, "T-30m", at) != cutoff_for(T(2026, 8, 3, 23, 14), "T-30m"))
    check("no capture predates `at` -> None",
          asof_cutoff(hist, "T-30m", T(2026, 8, 1, 0, 0)) is None,
          "unknowable cutoff must not silently fall back to the latest tip")
    check("empty history -> None", asof_cutoff([], "T-30m", at) is None)


# --------------------------------------------------------------------------- #
# 4. synthetic: the retroactive-relabel case, the whole point of G2
# --------------------------------------------------------------------------- #
def test_retroactive_relabel() -> None:
    print("\n[4] retroactive relabelling is detected and separated")
    hist = [(T(2026, 8, 2, 0, 0), T(2026, 8, 3, 23, 30)),
            (T(2026, 8, 4, 0, 0), T(2026, 8, 3, 23, 14))]
    v = classify_write(T(2026, 8, 3, 22, 45, 8), hist, "T-30m")
    check("late against the LATEST tip", v["latest_late"] is True, f"{v['latest_minutes']} min")
    check("on time against the tip KNOWN then", v["asof_late"] is False, f"{v['asof_minutes']} min")
    check("flagged retroactively_relabelled", v["retroactively_relabelled"] is True)
    check("G1 would have ALLOWED this write", v["guard_allows_write"] is True,
          "the writer did nothing wrong; the tip moved afterwards")

    # a genuinely late record: late on both clocks, and the guard refuses it
    hist2 = [(T(2026, 8, 2, 0, 0), T(2026, 8, 3, 23, 0)),
             (T(2026, 8, 4, 0, 0), T(2026, 8, 3, 23, 4))]
    v2 = classify_write(T(2026, 8, 3, 22, 45, 8), hist2, "T-30m")
    check("genuinely late on both clocks",
          v2["latest_late"] is True and v2["asof_late"] is True)
    check("not flagged as retroactive", v2["retroactively_relabelled"] is False)
    check("G1 REFUSES the genuinely late write", v2["guard_allows_write"] is False)


# --------------------------------------------------------------------------- #
# 5. synthetic: the guard is schedule-independent
# --------------------------------------------------------------------------- #
def test_schedule_independence() -> None:
    print("\n[5] G1 holds for a writer that never consulted the discovery gate")
    # A fixed-wall-clock task firing at 18:45 ET (22:45Z) every night, against a
    # slate whose cutoffs move nightly. The guard needs no knowledge of the
    # schedule, the gate, or the lead window.
    fire = T(2026, 8, 3, 22, 45, 1)
    refused = allowed = 0
    for tip_minute in range(0, 121, 5):                 # tips 22:45Z .. 00:45Z
        tip = T(2026, 8, 3, 22, 45) + timedelta(minutes=tip_minute)
        ok, _ = refuse_late(fire, cutoff_for(tip, "T-30m"))
        refused += (not ok)
        allowed += ok
    check("refuses every write whose cutoff has passed", refused == 7, f"refused={refused}")
    check("allows every write still inside its cutoff", allowed == 18, f"allowed={allowed}")


# --------------------------------------------------------------------------- #
# 6. replay against the real chain (optional)
# --------------------------------------------------------------------------- #
TEAMS_OF_INTEREST = {("New York Liberty", "Seattle Storm"),
                     ("Atlanta Dream", "Las Vegas Aces")}


def _tip_history(repo: Path) -> dict:
    hist: dict = {}
    for f in sorted(glob.glob(str(repo / "data" / "odds_capture" / "live_*.json"))):
        cap = datetime.strptime(Path(f).stem.replace("live_", ""), "%Y%m%dT%H%M%SZ") \
            .replace(tzinfo=UTC)
        try:
            games = json.load(open(f, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for g in games:
            key = (g.get("home_team"), g.get("away_team"))
            if key not in TEAMS_OF_INTEREST:
                continue
            tip = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
            if tip.date().isoformat() != "2026-08-03":
                continue
            hist.setdefault(key, []).append((cap, tip))
    return hist


def test_replay(repo: Path) -> None:
    print("\n[6] replay against the live chain  (%s)" % repo)
    log = repo / "forecasts" / "forecast_log.jsonl"
    if not log.exists():
        print("  SKIP  live chain not present at %s" % log)
        return
    recs = [json.loads(l) for l in open(log, encoding="utf-8") if l.strip()]
    hist = _tip_history(repo)
    check("tip history recovered for both games", len(hist) == 2, str(list(hist)))
    if len(hist) != 2:
        return

    # the two records the project update calls D-d
    by_gid = {"1022600223": ("New York Liberty", "Seattle Storm"),
              "1022600222": ("Atlanta Dream", "Las Vegas Aces")}
    targets = [r for r in recs
               if str(r["game_id"]) in by_gid and r["decision_time_label"] == "T-30m"
               and str(r["logged_at_utc"]).startswith("2026-08-03T22:45")]
    check("exactly the two D-d records are present", len(targets) == 2,
          "found %d" % len(targets))

    verdicts = {}
    for r in targets:
        gid = str(r["game_id"])
        v = classify_write(r["logged_at_utc"], hist[by_gid[gid]], "T-30m")
        verdicts[gid] = v
        print("      %s %-34s latest %+7.2f min  as-of %+7.2f min  guard_allows=%s"
              % (gid, "%s v %s" % by_gid[gid], v["latest_minutes"], v["asof_minutes"],
                 v["guard_allows_write"]))

    a = verdicts.get("1022600223", {})
    b = verdicts.get("1022600222", {})
    check("NYL v SEA is late on BOTH clocks",
          a.get("latest_late") is True and a.get("asof_late") is True)
    check("NYL v SEA would have been refused by G1", a.get("guard_allows_write") is False)
    check("ATL v LVA is late on the LATEST clock only",
          b.get("latest_late") is True and b.get("asof_late") is False)
    check("ATL v LVA is flagged retroactively_relabelled",
          b.get("retroactively_relabelled") is True)
    check("ATL v LVA would have been ALLOWED by G1", b.get("guard_allows_write") is True)


def main() -> int:
    test_cutoff_arithmetic()
    test_refuse_late()
    test_asof_cutoff()
    test_retroactive_relabel()
    test_schedule_independence()
    if len(sys.argv) > 1:
        test_replay(Path(sys.argv[1]).resolve())
    else:
        print("\n[6] replay SKIPPED (no live repo path given)")
    print("\n%d failure(s)" % len(FAILURES))
    for f in FAILURES:
        print("  FAILED: " + f)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
