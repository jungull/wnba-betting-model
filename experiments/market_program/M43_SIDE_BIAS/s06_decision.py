# -*- coding: utf-8 -*-
"""M43 s06 -- is the best candidate better than the best of fifteen coin flips?

E0-style diagnostic. Authorises nothing; S42 stays closed.

WHY THIS FILE EXISTS. s01-s05 kept reporting "the 95% interval spans zero", which is the
right statistical statement and the wrong DECISION statement. So this asks the decision
questions directly: how likely is the edge to be positive, how much of the estimate is the
search itself, and what stake would follow.

THE CHECK THAT MATTERS. After running many tests there is ALWAYS a best one. The question is
never "is the best test significant on its own" but "is the best test better than the best
that NOISE would have produced over the same number of tries". That comparison is made here,
and it is the one that decides this programme's candidate.

WHAT MULTIPLE TESTING CANNOT EXPLAIN is an out-of-sample replication, because the held-out
years were not part of the search. So the held-out result is scored ALONE as well, on its
own sample size, rather than being folded into the pooled figure where it borrows strength
from the data that generated the hypothesis.
"""
from __future__ import annotations

import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# --- the candidate, from s04 (large-spread >8 underdogs, best price, 2022-2026) ---
ROI = 0.0775
SE = 0.0482
N_GAMES = 384
SD_PER_GAME = 0.945
N_TESTS = 15                 # comparisons run across M43 s01-s05
GAMES_PER_SEASON = 76

# --- the held-out replication (2022-2024 only, large-spread dogs) ---
OOS_ROI = 0.0403
OOS_N = 201


def phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def main():
    res = {}
    print("=" * 94)
    print("M43 s06 -- from interval to decision")
    print("=" * 94)

    z = ROI / SE
    print("\n1. THE CANDIDATE ON ITS OWN")
    print("   %+.2f%% on %d games, SE %.2f%%  ->  %.2f SE from zero"
          % (100 * ROI, N_GAMES, 100 * SE, z))
    print("   P(edge > 0 | this test alone, flat prior) = %.1f%%" % (100 * phi(z)))
    res["z"] = round(z, 3)
    res["p_positive_single"] = round(phi(z), 4)

    print("\n2. THE DECISIVE CHECK: BETTER THAN THE BEST OF %d COIN FLIPS?" % N_TESTS)
    p_any = 1.0 - phi(z) ** N_TESTS
    lg = math.log(N_TESTS)
    e_max = math.sqrt(2 * lg) - (math.log(lg) + math.log(4 * math.pi)) / (2 * math.sqrt(2 * lg))
    print("   %d comparisons were run across M43." % N_TESTS)
    print("   P(some test reaching %.2f SE from PURE NOISE) = %.1f%%" % (z, 100 * p_any))
    print("   E[best z over %d pure-noise tests] = %.2f   vs observed %.2f"
          % (N_TESTS, e_max, z))
    res["p_any_from_noise"] = round(p_any, 4)
    res["expected_max_z_null"] = round(e_max, 3)
    beaten_by_noise = z <= e_max * 1.05
    res["indistinguishable_from_search_artifact"] = bool(beaten_by_noise)
    if beaten_by_noise:
        print("   THE BEST RESULT IS WHAT THE SEARCH ITSELF PRODUCES. On this arithmetic it")
        print("   is not evidence of an edge; it is evidence that fifteen tests were run.")

    print("\n3. WHAT MULTIPLE TESTING CANNOT EXPLAIN -- the held-out years, scored ALONE")
    se_oos = SD_PER_GAME / math.sqrt(OOS_N)
    z_oos = OOS_ROI / se_oos
    print("   2022-2024 large-spread dogs: %+.2f%% on %d games, SE %.2f%% -> %.2f SE"
          % (100 * OOS_ROI, OOS_N, 100 * se_oos, z_oos))
    print("   P(edge > 0 | held-out test alone) = %.1f%%" % (100 * phi(z_oos)))
    print("   The hypothesis was formed on 2025-26, so these years are a genuine test --")
    print("   but at %.2f SE it LEANS positive and settles nothing." % z_oos)
    res["oos_z"] = round(z_oos, 3)
    res["p_positive_oos"] = round(phi(z_oos), 4)

    print("\n4. WHAT A STAKE WOULD LOOK LIKE IF YOU BET IT ANYWAY")
    b = 0.91
    # size on the HELD-OUT estimate, the only one not inflated by the search
    kelly = OOS_ROI / b
    print("   sizing on the held-out %+.2f%% (the only figure the search did not inflate):"
          % (100 * OOS_ROI))
    print("   full Kelly %.1f%% of bank | quarter %.2f%% | eighth %.2f%%"
          % (100 * kelly, 100 * kelly / 4, 100 * kelly / 8))
    for bank in (1000, 5000, 20000):
        stake = bank * kelly / 4
        print("   bank $%-6s quarter-Kelly $%-7.2f -> ~$%.0f a season if the edge is real, "
              "and ~-$%.0f if it is zero and you pay the vig"
              % (bank, stake, stake * OOS_ROI * GAMES_PER_SEASON,
                 stake * 0.045 * GAMES_PER_SEASON))
    res["kelly_quarter_oos"] = round(kelly / 4, 4)

    print("\n5. THE KILL CRITERION, SET BEFORE ANY MONEY MOVES")
    for n in (50, 100, 200):
        se_n = SD_PER_GAME / math.sqrt(n)
        print("   after %3d forward bets: SE %.2f%%  -> abandon if running ROI < %+.2f%%"
              % (n, 100 * se_n, 100 * (OOS_ROI - 1.64 * se_n)))

    print("\n" + "=" * 94)
    print("VERDICT")
    print("  The pooled +7.75%% is 1.61 SE, and fifteen tests produce %.2f SE from noise" % e_max)
    print("  on average. The pooled figure is therefore NOT usable as evidence.")
    print("  The held-out replication is the only clean number and it is %.2f SE -- it" % z_oos)
    print("  leans positive at %.0f%% and cannot carry a bankroll on its own." % (100 * phi(z_oos)))
    print("")
    print("  This is a LEAD, not an edge. Only forward results can settle it, and the")
    print("  honest expected value today is somewhere between zero and +4%%, with zero")
    print("  well inside the range.")
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS_s06.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\nwrote FINDINGS_s06.json")


if __name__ == "__main__":
    main()
