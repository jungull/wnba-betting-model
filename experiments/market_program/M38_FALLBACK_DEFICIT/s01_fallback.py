# -*- coding: utf-8 -*-
"""M38 -- 8.8% of priced rows carry 42% of the model's deficit to the market.

E0-style diagnostic, NON-CLAIMING. Not a graph node; same shape as M33-M37. Nothing here
fits, adopts or ships a model, and no wager-shaped claim is made. S42 untouched.

WHY THIS WAS ASKED. M33 established the model-market gap is entirely MINUTES, and that closing
it needs roughly a 40% cut in minutes error -- about five times anything the programme has
achieved on that target. D150 had already found 7.4% of rows carrying 56% of the deficit, and
the cause turned out to be ONE hardcoded constant, worth more than 58 screens of feature
search. D169 then measured the repair and found it moved the competitive verdict by a net ONE
call, "because the repair helps where the market does not compete" -- the cold-start rows it
fixed are largely unpriced.

So the question here is the same one, asked about the PRICED population: is the remaining
minutes error a LIMIT, or another DEFECT?

HOW THE ROWS ARE IDENTIFIED. Not by a heuristic. A first pass grouped predictions by repeated
value and found three near-identical constants around 21.51 -- suggestive, but a guess. The
arm's own prediction files carry `is_fallback`, `fallback_level`, `is_cold_start` and
`n_prior_games`, so the rows are identified by the model's own flags instead. That matters:
the heuristic found 168 rows and the flags find 519, so the heuristic would have understated
the finding by two thirds.

WHAT IS READ. attempt_002 -- the REPAIRED rev-9 arm, checked rather than assumed. Diagnosing a
defect on a superseded attempt would be worthless.

THE COUNTERFACTUAL IS A CEILING, NOT A PLAN. "If fallback rows scored like non-fallback rows"
assumes a repair reaches full parity. Nothing here shows that is achievable -- these players
genuinely have 0-2 prior games. It bounds the prize; it does not claim it.
"""
from __future__ import annotations

import glob
import json
import os
import random
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
M33 = os.path.abspath(os.path.join(HERE, "..", "M33_WHERE_THE_GAP_IS"))
sys.path.insert(0, M33)

import diagnose as dg  # noqa: E402

SEED = 20260824
DRAWS = 2000


def frame():
    """M33's priced frame, plus the arm's own fallback flags."""
    d = dg.build()
    flags = [pd.read_parquet(p)[["row_uid", "is_fallback", "fallback_level",
                                 "is_cold_start", "n_prior_games", "component_id"]]
             for p in sorted(glob.glob(str(dg.ARM / "predictions__e_minutes_given_active__*.parquet")))]
    d = d.merge(pd.concat(flags, ignore_index=True), on="row_uid", how="left")
    d["mkt_abs"] = (d["mkt_mean"] - d["pts"]).abs()
    d["mod_abs"] = (d["pred_point"] - d["pts"]).abs()
    d["resp"] = d["mkt_abs"] - d["mod_abs"]          # positive => model closer
    d["min_err"] = d["min_hat"] - d["min_actual"]
    d["min_abs"] = d["min_err"].abs()
    d["fb"] = d["is_fallback"] == True               # noqa: E712
    return d


def main():
    out = {}
    print("=" * 94)
    print("M38 -- where the priced minutes error actually lives")
    print("=" * 94)
    print("arm read: %s" % dg.ARM.name)
    if dg.ARM.name != "attempt_002":
        print("  WARNING: this is not the repaired rev-9 attempt.")

    d = frame()
    print("\npriced rows %d over %d games, seasons %s"
          % (len(d), d["game_id"].nunique(), sorted(int(s) for s in d["season"].unique())))
    print("fallback rows: %d (%.1f%%)  -- all component %s"
          % (d["fb"].sum(), 100 * d["fb"].mean(),
             d.loc[d["fb"], "component_id"].unique().tolist()))
    print("their prior-game counts: median %.0f, max %.0f"
          % (d.loc[d["fb"], "n_prior_games"].median(), d.loc[d["fb"], "n_prior_games"].max()))

    print("\nBY FALLBACK LEVEL (the model's own flag, not a heuristic)")
    print("  %-6s %6s %9s %10s %10s %11s %10s"
          % ("level", "n", "min MAE", "min bias", "model MAE", "market MAE", "response"))
    lv_rows = {}
    for lv, s in d.groupby(d["fallback_level"].fillna(-1)):
        print("  %-6d %6d %9.3f %+10.3f %10.3f %11.3f %+10.4f"
              % (int(lv), len(s), s["min_abs"].mean(), s["min_err"].mean(),
                 s["mod_abs"].mean(), s["mkt_abs"].mean(), s["resp"].mean()))
        lv_rows[int(lv)] = {"n": int(len(s)), "min_mae": round(float(s["min_abs"].mean()), 3),
                            "min_bias": round(float(s["min_err"].mean()), 3),
                            "model_mae": round(float(s["mod_abs"].mean()), 3),
                            "market_mae": round(float(s["mkt_abs"].mean()), 3),
                            "response": round(float(s["resp"].mean()), 4)}
    out["by_level"] = lv_rows

    print("\n  THE MARKET DOES NOT DEGRADE ON THESE ROWS. Its MAE is flat across every level,")
    print("  so this is not an intrinsically unpredictable population -- it is our defect.")

    # ---- concentration, game-clustered ----------------------------------
    share = 100.0 * d.loc[d["fb"], "resp"].sum() / d["resp"].sum()
    gain = (d["fb"].sum() * (d.loc[d["fb"], "mod_abs"].mean()
                             - d.loc[~d["fb"], "mod_abs"].mean())) / len(d)
    gap = d["mod_abs"].mean() - d["mkt_abs"].mean()

    rnd = random.Random(SEED)
    byg = {g: s for g, s in d.groupby("game_id")}
    keys = list(byg)
    shares, gains = [], []
    for _ in range(DRAWS):
        samp = pd.concat([byg[rnd.choice(keys)] for _ in keys], ignore_index=True)
        tot = samp["resp"].sum()
        if tot == 0:
            continue
        shares.append(100.0 * samp.loc[samp["fb"], "resp"].sum() / tot)
        gains.append((samp["fb"].sum() * (samp.loc[samp["fb"], "mod_abs"].mean()
                                          - samp.loc[~samp["fb"], "mod_abs"].mean())) / len(samp))
    shares.sort(); gains.sort()
    lo_s, hi_s = shares[int(0.025 * len(shares))], shares[int(0.975 * len(shares))]
    lo_g, hi_g = gains[int(0.025 * len(gains))], gains[int(0.975 * len(gains))]

    print("\nCONCENTRATION (game-clustered bootstrap, %d draws, seed %d)" % (DRAWS, SEED))
    print("  fallback rows are %.1f%% of the priced population" % (100 * d["fb"].mean()))
    print("  they carry %.1f%% of the competitive deficit   95%% CI [%.1f, %.1f]"
          % (share, lo_s, hi_s))
    print("\nCEILING IF THEY REACHED PARITY (a bound, not a plan)")
    print("  points MAE would improve %.4f   95%% CI [%.4f, %.4f]" % (gain, lo_g, hi_g))
    print("  current gap to market    %.4f" % gap)
    print("  => closes %.0f%% of the model-vs-market gap" % (100 * gain / gap))
    out["concentration"] = {"pct_of_rows": round(100 * float(d["fb"].mean()), 1),
                            "pct_of_deficit": round(float(share), 1),
                            "ci95": [round(lo_s, 1), round(hi_s, 1)]}
    out["ceiling"] = {"points_mae_gain": round(float(gain), 4),
                      "ci95": [round(lo_g, 4), round(hi_g, 4)],
                      "current_gap": round(float(gap), 4),
                      "pct_of_gap_closed": round(100 * float(gain) / float(gap), 0)}

    print("\n" + "=" * 94)
    print("A DEFECT, NOT A LIMIT -- on the population the market actually prices.")
    print("D169 found the earlier cold-start repair moved the verdict by one call because it")
    print("helped where the market does not compete. These rows ARE priced, so a repair here")
    print("lands where it counts. This does NOT say how to fix it, and the parity assumption")
    print("is a ceiling: these players genuinely have 0-2 prior games.")
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("\nwrote FINDINGS.json")


if __name__ == "__main__":
    main()
