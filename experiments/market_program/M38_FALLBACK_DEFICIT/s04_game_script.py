# -*- coding: utf-8 -*-
"""M38 s04 -- level-0 minutes error tracks game script, and the obvious fix is CONTRACT-BLOCKED.

E0-style diagnostic, NON-CLAIMING.

Level 0 is 91% of the priced population and s03 showed oracle minutes there takes the model
from -0.196 to +0.408 -- correct minutes and it BEATS the market. So what drives level-0
minutes error?

THE MECHANISM IS GAME SCRIPT, and it is clean. Minutes error correlates 0.2975 with the final
margin, and the bias gradient is monotonic across margin buckets: the model UNDER-forecasts
minutes by 1.18 in close games, where starters stay on, and OVER-forecasts by 3.58 in blowouts,
where they sit. The model does not anticipate how competitive a game will be.

THE CEILING, MEASURED LEGITIMATELY. Removing the margin-conditional bias entirely takes level-0
minutes MAE from 4.0651 to 3.8249 and the competitive response from -0.1957 to -0.1502 -- about
23% of level-0's deficit. This uses the FINAL MARGIN and is therefore pure oracle: it bounds
what perfect game-script anticipation would be worth. It is not achievable and is not a plan.
The margin comes from the outcome masters, NOT from any odds archive.

THE OBVIOUS TEST IS PROHIBITED, AND THIS FILE HALTS RATHER THAN STRETCHING THE ENUMERATION.
The natural next step is to ask whether the PRE-GAME SPREAD anticipates the margin well enough
to fix this. It cannot be run:

  * `data/drive_masters/master_odds.csv` carries `odds_spread` and covers the right seasons,
    but M00's final-state archive ruling enumerates six permitted uses and M00-U4 states the
    archive is for coarse descriptive context "never a feature, never a benchmark". Using its
    spread as a minutes feature is outside the enumeration, and this node's stop condition is
    explicit: HALT and raise, do not stretch it.
  * The cutoff-valid alternative, `data/odds_capture`, begins 2026-07-30 -- the day the priced
    frame ENDS. There is no legal pre-game spread for this window at all.

AND A POINT THAT OUTLIVES THE BLOCK. Even with permission, closing the gap by feeding the
model the market's own spread would import market information. It would move the model TOWARD
the market asymptotically, not past it. This route can narrow the deficit; it cannot produce
edge, and it should never be sold as a path to one.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = r"C:\Users\jgallagher\wnba-betting-model"
MTEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")

import s01_fallback as s01  # noqa: E402

BUCKETS = [0, 5, 10, 15, 20, 100]


def main():
    out = {}
    print("=" * 94)
    print("M38 s04 -- game script drives level-0 minutes error; the fix is contract-blocked")
    print("=" * 94)

    d = s01.frame()
    d = d[d["fallback_level"] == 0].copy()
    mt = pd.read_parquet(MTEAM)
    mt = mt[mt["is_home"] == 1][["game_id", "pts", "opp_pts"]].copy()
    mt["margin"] = (mt["pts"] - mt["opp_pts"]).abs()
    mt["game_id"] = mt["game_id"].astype(str)
    d["game_id"] = d["game_id"].astype(str)
    d = d.merge(mt[["game_id", "margin"]], on="game_id", how="left")
    d = d[d["margin"].notna()].copy()
    d["min_err"] = d["min_hat"] - d["min_actual"]

    print("\n1. MINUTES ERROR BY FINAL MARGIN (n=%d level-0 rows)" % len(d))
    print("   %-8s %6s %13s %9s %12s %11s"
          % ("margin", "n", "minutes bias", "min MAE", "model pts", "market pts"))
    d["bucket"] = pd.cut(d["margin"], BUCKETS,
                         labels=["0-5", "6-10", "11-15", "16-20", "21+"])
    rows = {}
    for b, s in d.groupby("bucket", observed=True):
        print("   %-8s %6d %+13.3f %9.3f %12.3f %11.3f"
              % (b, len(s), s["min_err"].mean(), s["min_err"].abs().mean(),
                 (s["pred_point"] - s["pts"]).abs().mean(),
                 (s["mkt_mean"] - s["pts"]).abs().mean()))
        rows[str(b)] = {"n": int(len(s)), "min_bias": round(float(s["min_err"].mean()), 3)}
    corr = float(d[["min_err", "margin"]].corr().iloc[0, 1])
    print("\n   correlation of minutes error with final margin: %.4f" % corr)
    print("   the model does not anticipate how competitive a game will be.")
    out["by_margin"] = rows
    out["corr_err_margin"] = round(corr, 4)

    # ---- oracle ceiling, from OUTCOMES not from any odds archive --------
    adj = d.groupby("bucket", observed=True)["min_err"].transform("mean")
    d["min_hat_adj"] = d["min_hat"] - adj
    mkt = (d["mkt_mean"] - d["pts"]).abs()
    base_mae = d["min_err"].abs().mean()
    adj_mae = (d["min_hat_adj"] - d["min_actual"]).abs().mean()
    base_r = (mkt - (d["pred_point"] - d["pts"]).abs()).mean()
    adj_r = (mkt - (d["rate_hat"] * d["min_hat_adj"] - d["pts"]).abs()).mean()

    print("\n2. CEILING -- remove the margin-conditional bias entirely")
    print("   level-0 minutes MAE      %.4f -> %.4f" % (base_mae, adj_mae))
    print("   level-0 response         %+.4f -> %+.4f  (%.0f%% of level-0's deficit)"
          % (base_r, adj_r, 100 * (adj_r - base_r) / abs(base_r)))
    print("   ORACLE: this uses the FINAL MARGIN, unknowable pre-game. It bounds the prize.")
    out["ceiling"] = {"min_mae": [round(float(base_mae), 4), round(float(adj_mae), 4)],
                      "response": [round(float(base_r), 4), round(float(adj_r), 4)]}

    print("\n3. HALT -- the pre-game-spread test cannot be run")
    print("   M00's final-state archive ruling enumerates six permitted uses. M00-U4 covers")
    print("   coarse descriptive context and says the archive is NEVER A FEATURE, NEVER A")
    print("   BENCHMARK. Using master_odds.csv's spread as a minutes feature is outside the")
    print("   enumeration, and this lane's stop condition says HALT and raise rather than")
    print("   stretch it. The cutoff-valid source, data/odds_capture, begins 2026-07-30 --")
    print("   the day the priced frame ends. There is no legal pre-game spread for this window.")
    out["halt"] = {"blocked_use": "master_odds.csv odds_spread as a model feature",
                   "rule": "M00-U4: never a feature, never a benchmark",
                   "alternative": "data/odds_capture starts 2026-07-30, after the frame ends"}

    print("\n" + "=" * 94)
    print("AND A POINT THAT OUTLIVES THE BLOCK. Even with permission, closing the gap by")
    print("feeding the model the market's own spread imports market information. It moves the")
    print("model TOWARD the market, not past it. This route can narrow the deficit; it cannot")
    print("produce edge, and must never be sold as a path to one.")
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS_s04.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("\nwrote FINDINGS_s04.json")


if __name__ == "__main__":
    main()
