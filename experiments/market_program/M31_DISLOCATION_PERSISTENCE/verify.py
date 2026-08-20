"""verify.py -- M31 integrity check. Runs whether or not the sample gate is open.

The point of this node is that it REFUSES to answer until it has enough data. That refusal
is the thing most worth protecting, because it is the thing a future run would be tempted to
remove. These checks fail if the gate is weakened, if the preregistration is edited, or if
censored episodes stop being censored.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys

import s01_persistence as s01

PASS = FAIL = 0


def check(label, ok, why=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  PASS  %s" % label)
    else:
        FAIL += 1
        print("  FAIL  %s" % label + (("\n          " + why) if why else ""))


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("=" * 84)
    print("M31 DISLOCATION PERSISTENCE -- verification")
    print("=" * 84)

    print("\n1. The preregistration is intact")
    got = hashlib.sha256(io.open("PREREG.md", "rb").read()).hexdigest()
    want = io.open("PREREG.sha256").read().split()[0]
    check("PREREG.md matches its frozen sha256", got == want,
          "frozen %s\n          actual %s\n          Restore the bytes; do not re-hash." % (want, got))

    print("\n2. The sample gate is where the preregistration put it")
    check("gate thresholds are unchanged",
          (s01.GATE_GAMES, s01.GATE_EPISODES, s01.GATE_STRONG) == (30, 150, 40),
          "PREREG.md fixes these at 30 games / 150 episodes / 40 strong. Lowering them to "
          "reach an answer sooner is optional stopping with extra steps.")
    check("the fast era starts at the cadence change",
          s01.FAST_ERA_FROM == "2026-08-19T14:00:00Z",
          "the hourly tape cannot see a phenomenon lasting minutes and is excluded")
    check("an episode straddling a capture gap is discarded, not guessed",
          s01.MAX_GAP_MIN == 12.0)
    check("STRONG means what M30/D157 measured", s01.STRONG_PP == 0.030)

    print("\n3. The gate is actually enforced")
    eps, diag = s01.build_episodes()
    games = len({e["game"] for e in eps})
    strong = [e for e in eps if e["strong"]]
    open_ = (games >= s01.GATE_GAMES and len(eps) >= s01.GATE_EPISODES
             and len(strong) >= s01.GATE_STRONG)
    d = json.load(open("FINDINGS.json", encoding="utf-8")) if os.path.exists("FINDINGS.json") else {}
    check("FINDINGS.json records the prereg hash", d.get("prereg_sha256") == want)
    check("the published gate state matches the data",
          d.get("gate", {}).get("open") == open_)
    check("no primary is published while the gate is closed",
          open_ or d.get("primary") is None,
          "a closed gate that still emits a number is not a gate")

    print("\n4. Censoring is handled, not dropped")
    check("censored episodes are retained",
          all("censored" in e for e in eps))
    check("every censored episode still carries a lifetime",
          all(e["minutes"] >= 0 for e in eps if e["censored"]),
          "dropping them would bias every lifetime downward, which flatters 'act fast'")
    if eps:
        curve, med = s01.kaplan_meier(eps)
        check("survival is monotone non-increasing",
              all(curve[i][1] >= curve[i + 1][1] for i in range(len(curve) - 1)),
              "a survival function that rises is a bug in the estimator")
        check("survival starts at or below 1", (not curve) or curve[0][1] <= 1.0)

    print("\n5. The partition claim is visible in the file that does the work")
    src = io.open("s01_persistence.py", encoding="utf-8").read()
    check("s01 declares it reads no outcome", "NO GAME OUTCOME IS READ" in src)

    print("\n" + "=" * 84)
    print("%s -- %d/%d checks" % ("VERIFIED" if not FAIL else "FAILED", PASS, PASS + FAIL))
    print("  sample gate: %s (%d/%d games, %d/%d episodes, %d/%d strong)"
          % ("OPEN" if open_ else "CLOSED", games, s01.GATE_GAMES, len(eps),
             s01.GATE_EPISODES, len(strong), s01.GATE_STRONG))
    print("=" * 84)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
