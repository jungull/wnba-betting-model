# -*- coding: utf-8 -*-
"""M43 s02 -- the underdog side, followed up honestly. It is SUGGESTIVE, not established.

E0-style diagnostic, NON-CLAIMING. Nothing here fits, adopts or ships a model. S42 closed.

WHAT s01 FOUND. Betting every favourite loses -11.46% with an interval excluding zero;
betting every underdog returns +2.49% with an interval that does NOT. Those are the same
finding twice -- complementary bets whose ROIs differ by about twice the vig -- and the
honest statement is that the market shades favourites, but not by enough to clear the vig
reliably on this sample.

THE MULTIPLE-COMPARISON BURDEN, STATED NOT DISCOVERED. s01 declared four tests. This file
adds two more -- time stability and best-price shopping -- so six comparisons now stand
behind a single positive point estimate. That is stated here, with the result, because a
burden mentioned only when it is convenient is not a burden.

WHY NO SLICING. The obvious next move is to cut by spread size, book, month or league
phase until something clears zero. That is a search, and on 406 games it would certainly
succeed at finding a subgroup. This file does not slice, and any later file that does must
treat what it finds as a hypothesis rather than a result.

WHAT WOULD SETTLE IT, AND WHY THIS DATA CANNOT. The spread of per-game returns puts the
standard error near 4.7% at n=406. A true edge of +3% is therefore INSIDE THE NOISE by
construction -- this sample cannot distinguish it from zero however it is analysed. Only
more games can, and the only clean ones are the games not yet played.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import s01_flat_side_bias as s01  # noqa: E402

BREAK_EVEN_110 = 0.5238


def main():
    res = {}
    print("=" * 94)
    print("M43 s02 -- the underdog side: stability, shopping, and what it would take")
    print("=" * 94)

    d = s01.build()
    rng = np.random.default_rng(s01.SEED)
    dog = d[~d["is_fav"]].copy()
    dog["gd"] = pd.to_datetime(dog["game_date"])
    cut = dog["gd"].median()

    print("\n1. TIME STABILITY (flat bet, every book)")
    halves = {}
    for lbl, sub in (("first half", dog[dog["gd"] <= cut]),
                     ("second half", dog[dog["gd"] > cut])):
        r = s01.clustered_ci(sub, rng)
        halves[lbl] = r
        print("   %-12s %4d games  hit %5.1f%%  ROI %+6.2f%%  [%+.2f%%, %+.2f%%]"
              % (lbl, r["n_games"], 100 * r["hit"], 100 * r["roi"],
                 100 * r["lo"], 100 * r["hi"]))
    res["halves_flat"] = halves

    print("\n2. BEST AVAILABLE PRICE, one bet per game (shop all books)")
    best = (dog.sort_values(["odds_spread", "odds_price"], ascending=[False, False])
               .groupby("game_id", as_index=False).first())
    r_all = s01.clustered_ci(best, rng)
    print("   %-12s %4d games  hit %5.1f%%  ROI %+6.2f%%  [%+.2f%%, %+.2f%%]"
          % ("all games", r_all["n_games"], 100 * r_all["hit"], 100 * r_all["roi"],
             100 * r_all["lo"], 100 * r_all["hi"]))
    res["best_price"] = r_all

    print("\n3. HOW BIG A SAMPLE WOULD SETTLE IT?")
    per_game = best.groupby("game_id")["profit"].mean()
    sd = float(per_game.std())
    roi = float(per_game.mean())
    se = sd / np.sqrt(len(per_game))
    print("   per-game return: mean %+.4f, sd %.4f  ->  standard error %.4f (%.2f%%)"
          % (roi, sd, se, 100 * se))
    print("   the observed %+.2f%% sits %.2f standard errors from zero"
          % (100 * roi, roi / se if se else float("nan")))
    if roi > 0:
        need = int(np.ceil((1.96 * sd / roi) ** 2))
        print("   games needed for a 95%% interval to exclude zero AT THIS ROI: ~%d" % need)
        print("   (that is roughly %.1f full WNBA seasons of ~200 games)" % (need / 200.0))
        res["games_needed"] = need
    res["per_game"] = {"roi": round(roi, 5), "sd": round(sd, 5), "se": round(se, 5),
                       "n": int(len(per_game))}

    print("\n" + "=" * 94)
    print("VERDICT: SUGGESTIVE, NOT ESTABLISHED.")
    print("  * positive in both halves and above the %.1f%% break-even in most splits;"
          % (100 * BREAK_EVEN_110))
    print("  * every interval spans zero;")
    print("  * six comparisons now stand behind one positive point estimate;")
    print("  * and the sample is too small BY CONSTRUCTION to resolve an edge this size.")
    print("")
    print("This is NOT a profitable strategy that has been found. It is a candidate with a")
    print("known mechanism -- favourites are shaded in small markets -- that this data")
    print("cannot confirm or refute. Betting it now would be acting on noise that happens")
    print("to point the right way.")
    print("")
    print("The only clean test is PROSPECTIVE: record the underdog side before tip, at the")
    print("best available price, and score it forward. That costs nothing and settles it.")
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS_s02.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=float)
    print("\nwrote FINDINGS_s02.json")


if __name__ == "__main__":
    main()
