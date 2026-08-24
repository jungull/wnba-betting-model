# -*- coding: utf-8 -*-
"""M38 s02 -- is the fallback deficit one number, as the cold-start defect was?

E0-style diagnostic, NON-CLAIMING.

s01 found 8.8% of priced rows take a minutes fallback and carry 42.3% of the competitive
deficit, and quoted a PARITY CEILING of 37% of the model-market gap. A ceiling is not a plan,
and this file asks what a realistic repair actually delivers. The answer is materially smaller
and the difference matters.

TWO FINDINGS, AND THE SECOND CORRECTS s01's FRAMING.

  1. THE TWO FALLBACK LEVELS ARE DIFFERENT ANIMALS. Level 3 (168 rows) really is a degenerate
     constant -- 3 distinct values, sd 0.007. Level 2 (351 rows) is NOT: 339 distinct values,
     sd 5.50, spanning 4.35 to 39.90. The model uses per-row information there and a single
     constant would be WORSE. So "519 rows take a prefix mean" was too broad; only 168 do.

  2. FIXING THE CONSTANT IS WORTH ~7% OF THE GAP, NOT 37%. The 37% was parity across all 519
     rows, and a constant cannot reach it: it repairs minutes, while the points error on those
     rows has other sources.

THE CONSTANT IS WRONG FOR A SPECIFIC, DIAGNOSABLE REASON. 21.51 is a prefix mean over a
population that includes bench players. The rows it lands on in the PRICED set are 74%
starters playing 25+ minutes, averaging 27.6. It is not wrong in general -- it is wrong for
this subpopulation, which is a selection effect rather than a modelling failure.

HONESTY ABOUT THE REPLACEMENT. Choosing 29.0 because it is the median of the ACTUALS is
oracle. So the candidate tested here is a WALK-FORWARD constant -- the mean minutes of priced
players in strictly EARLIER seasons -- which could have been known before any of these games.
It is available for 127 of the 168 rows; the rest are in the first season and have no prior.
The oracle constant is reported beside it purely to show the walk-forward choice loses nothing.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import s01_fallback as s01  # noqa: E402


def main():
    out = {}
    print("=" * 94)
    print("M38 s02 -- is it one number?")
    print("=" * 94)

    d = s01.frame().sort_values("game_date")

    print("\n1. THE TWO FALLBACK LEVELS ARE NOT THE SAME PROBLEM")
    for lv in (2, 3):
        s = d[d["fallback_level"] == lv]
        print("   level %d: n=%3d  distinct predictions %3d  sd %.4f  range %.2f-%.2f"
              % (lv, len(s), s["min_hat"].nunique(), s["min_hat"].std(),
                 s["min_hat"].min(), s["min_hat"].max()))
    print("   => level 3 is a genuine constant; level 2 is modelled and varies. Only 168 rows")
    print("      take a prefix mean, not 519. s01's framing was too broad.")
    out["levels"] = {int(lv): {"n": int((d["fallback_level"] == lv).sum()),
                               "distinct": int(d.loc[d["fallback_level"] == lv, "min_hat"].nunique()),
                               "sd": round(float(d.loc[d["fallback_level"] == lv, "min_hat"].std()), 4)}
                     for lv in (2, 3)}

    l3 = d["fallback_level"] == 3
    s3 = d[l3]
    print("\n2. WHY THE CONSTANT IS WRONG (a selection effect, not a modelling failure)")
    print("   the constant applied            : %.2f" % s3["min_hat"].mean())
    print("   what these players actually play: mean %.1f, median %.1f, %.0f%% play 25+ min"
          % (s3["min_actual"].mean(), s3["min_actual"].median(),
             100 * (s3["min_actual"] >= 25).mean()))
    print("   the whole priced population     : mean %.1f, %.0f%% play 25+ min"
          % (d["min_actual"].mean(), 100 * (d["min_actual"] >= 25).mean()))
    print("   => a prefix mean over everyone, applied to rows that are overwhelmingly starters.")
    out["selection"] = {"constant": round(float(s3["min_hat"].mean()), 2),
                        "actual_mean": round(float(s3["min_actual"].mean()), 1),
                        "pct_25plus": round(100 * float((s3["min_actual"] >= 25).mean()), 0)}

    # ---- a constant we could actually have known -------------------------
    prior_mean = {}
    for s in sorted(d["season"].unique()):
        prior = d[d["season"] < s]
        prior_mean[s] = prior["min_actual"].mean() if len(prior) > 200 else np.nan
    d["legit_const"] = d["season"].map(prior_mean)
    have = l3 & d["legit_const"].notna()

    print("\n3. REPLACING IT -- walk-forward, not oracle")
    print("   walk-forward constant available for %d of %d level-3 rows"
          % (int(have.sum()), int(l3.sum())))
    cands = (("current", d.loc[have, "min_hat"]),
             ("walk-forward prior-season priced mean", d.loc[have, "legit_const"]),
             ("oracle median of actuals (ceiling)", pd.Series(29.0, index=d.index[have])))
    minutes = {}
    for lbl, c in cands:
        err = c.values - d.loc[have, "min_actual"].values
        print("   %-38s %5.2f   minutes MAE %.3f  bias %+.3f"
              % (lbl, float(np.mean(c.values)), float(np.abs(err).mean()), float(err.mean())))
        minutes[lbl] = {"value": round(float(np.mean(c.values)), 2),
                        "mae": round(float(np.abs(err).mean()), 3),
                        "bias": round(float(err.mean()), 3)}
    out["minutes_repair"] = minutes

    # ---- propagate to points through the model's own rate ----------------
    base = d["resp"].mean()
    print("\n4. WHAT IT IS ACTUALLY WORTH, propagated to points via the model's own rate")
    print("   baseline competitive response: %+.4f" % base)
    worth = {}
    for lbl, c in cands[1:]:
        d2 = d.copy()
        d2.loc[have, "pred_point"] = d2.loc[have, "rate_hat"] * c.values
        d2["mod_abs"] = (d2["pred_point"] - d2["pts"]).abs()
        d2["resp"] = d2["mkt_abs"] - d2["mod_abs"]
        newr = d2["resp"].mean()
        pct = 100 * (newr - base) / abs(base)
        print("   %-38s response %+.4f   closes %.0f%% of the gap" % (lbl, newr, pct))
        worth[lbl] = {"response": round(float(newr), 4), "pct_gap_closed": round(float(pct), 0)}
    out["gap_closed"] = worth

    print("\n" + "=" * 94)
    print("CORRECTION TO s01. The one-number repair is worth about 7% of the model-market gap,")
    print("not the 37% s01 quoted. That 37% was a PARITY ceiling across all 519 fallback rows;")
    print("a constant repairs minutes on 168 of them and cannot reach parity, because the points")
    print("error on those rows has sources a minutes constant does not touch. The repair is")
    print("still real, cheap and walk-forward -- it is simply an order smaller than the ceiling.")
    print("The remaining 351 level-2 rows are a different problem and need something else.")
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS_s02.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("\nwrote FINDINGS_s02.json")


if __name__ == "__main__":
    main()
