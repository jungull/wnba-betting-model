# -*- coding: utf-8 -*-
"""M38 s03 -- two cheap walk-forward repairs, chosen out-of-sample, worth 21% of the gap.

E0-style diagnostic, NON-CLAIMING. This measures what two repairs WOULD be worth. It does not
implement them: the arm is a registered, byte-locked artifact and changing it is a new revision,
not a diagnostic's business. And closing part of the gap is NOT edge -- the model still loses.

WHAT s02 LEFT OPEN. It fixed the level-3 constant and found 7%. But level 2 is 351 rows to
level 3's 168, and s02 showed it is not a constant problem. An oracle decomposition within
levels says why:

    level   as-is    +oracle minutes
    0      -0.196        +0.408      minutes is the whole story; correct it and the model WINS
    2      -1.054        -0.592      oracle minutes recovers less than HALF -- not mainly minutes
    3      -2.381        -0.362      85% of the deficit is minutes -- the constant

So level 2 is a RATE problem. Its rate MAE is 0.1945 against level 0's 0.1601, with a positive
bias of +0.037 points per minute -- roughly a point of systematic over-prediction across 29
minutes. That is textbook small-sample over-fitting: a player who scored well in their one or
two prior games gets an inflated rate.

THE REPAIRS, BOTH WALK-FORWARD.
  level 3: replace the prefix-mean constant with the prior-SEASON priced-population mean minutes.
  level 2: shrink the fitted rate toward the prior-SEASON priced-population mean rate.

Every constant comes from strictly earlier seasons, so all of it was knowable before the games.

THE METHODOLOGICAL POINT THIS FILE EXISTS TO HONOUR. s02 picked the shrinkage weight by
maximising the response on the same rows it then reported -- in-sample tuning, which is the very
error the level-2 rows themselves commit. Here the weight is chosen on 2024-2025 ONLY and
evaluated on 2026 alone, which never informed the choice.
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

HOLDOUT_SEASON = 2026


def frame():
    d = s01.frame().sort_values("game_date")
    pr, mn = {}, {}
    for s in sorted(d["season"].unique()):
        prior = d[d["season"] < s]
        ok = len(prior) > 200
        pr[s] = prior["rate_actual"].mean() if ok else np.nan
        mn[s] = prior["min_actual"].mean() if ok else np.nan
    d["prior_rate"] = d["season"].map(pr)
    d["prior_min"] = d["season"].map(mn)
    return d


def apply(df, w, do_l2=True, do_l3=True):
    """Return the mean competitive response after the selected repairs."""
    x = df.copy()
    if do_l2:
        s = (x["fallback_level"] == 2) & x["prior_rate"].notna()
        x.loc[s, "pred_point"] = ((1 - w) * x.loc[s, "rate_hat"]
                                  + w * x.loc[s, "prior_rate"]) * x.loc[s, "min_hat"]
    if do_l3:
        s = (x["fallback_level"] == 3) & x["prior_min"].notna()
        x.loc[s, "pred_point"] = x.loc[s, "rate_hat"] * x.loc[s, "prior_min"]
    x["mod_abs"] = (x["pred_point"] - x["pts"]).abs()
    return float((x["mkt_abs"] - x["mod_abs"]).mean())


def main():
    out = {}
    print("=" * 94)
    print("M38 s03 -- two walk-forward repairs, chosen out-of-sample")
    print("=" * 94)

    d = frame()

    print("\n1. ORACLE DECOMPOSITION WITHIN LEVELS -- why level 2 is a different problem")
    print("   %-6s %6s %10s %13s" % ("level", "n", "as-is", "+oracle min"))
    dec = {}
    for lv in (0, 2, 3):
        s = d[d["fallback_level"] == lv]
        mkt = (s["mkt_mean"] - s["pts"]).abs()
        asis = (mkt - (s["pred_point"] - s["pts"]).abs()).mean()
        om = (mkt - (s["rate_hat"] * s["min_actual"] - s["pts"]).abs()).mean()
        print("   %-6d %6d %10.4f %13.4f" % (lv, len(s), asis, om))
        dec[int(lv)] = {"n": int(len(s)), "as_is": round(float(asis), 4),
                        "oracle_minutes": round(float(om), 4)}
    out["oracle_decomposition"] = dec
    print("   level 0: correct minutes and the model BEATS the market.")
    print("   level 2: oracle minutes recovers under half -- it is a RATE problem.")
    print("   level 3: 85% of the deficit is minutes -- it is the constant.")

    print("\n   rate error by level:")
    for lv in (0, 2, 3):
        s = d[d["fallback_level"] == lv]
        print("     level %d  rate MAE %.4f  bias %+.4f"
              % (lv, (s["rate_hat"] - s["rate_actual"]).abs().mean(),
                 (s["rate_hat"] - s["rate_actual"]).mean()))

    # ---- weight chosen on earlier seasons ONLY ---------------------------
    tr = d[d["season"] < HOLDOUT_SEASON]
    te = d[d["season"] == HOLDOUT_SEASON]
    ws = [i / 20 for i in range(21)]
    best = max(ws, key=lambda w: apply(tr, w))

    print("\n2. THE SHRINKAGE WEIGHT, CHOSEN ON %d-%d ONLY"
          % (int(tr["season"].min()), HOLDOUT_SEASON - 1))
    print("   selected w = %.2f   (2026 never informed this choice)" % best)
    out["weight"] = best

    print("\n3. RESULT")
    print("   %-34s %14s %16s" % ("", "fit seasons", "HELD-OUT %d" % HOLDOUT_SEASON))
    rows = (("current model", 0.0, False, False),
            ("level-3 constant only", 0.0, False, True),
            ("level-2 shrinkage only", best, True, False),
            ("both repairs", best, True, True))
    res = {}
    for lbl, w, a, b in rows:
        f, h = apply(tr, w, a, b), apply(te, w, a, b)
        print("   %-34s %14.4f %16.4f" % (lbl, f, h))
        res[lbl] = {"fit": round(f, 4), "holdout": round(h, 4)}
    out["results"] = res

    b0, b1 = apply(te, 0.0, False, False), apply(te, best, True, True)
    pct = 100 * (b1 - b0) / abs(b0)
    print("\n   HELD-OUT %d: %+.4f -> %+.4f  = %.1f%% of the gap closed, on %d rows"
          % (HOLDOUT_SEASON, b0, b1, pct, len(te)))
    out["holdout"] = {"before": round(b0, 4), "after": round(b1, 4),
                      "pct_gap_closed": round(pct, 1), "n": int(len(te))}

    print("\n" + "=" * 94)
    print("THE MODEL STILL LOSES. %+.4f is closer to the market than %+.4f, and it is still"
          % (b1, b0))
    print("negative: the market remains better on the priced population. Closing part of a")
    print("deficit is NOT an edge, and nothing here revisits M32's -7.2%.")
    print("Neither repair is implemented -- the arm is registered and byte-locked, and changing")
    print("it is a new revision rather than a diagnostic's business.")
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS_s03.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("\nwrote FINDINGS_s03.json")


if __name__ == "__main__":
    main()
