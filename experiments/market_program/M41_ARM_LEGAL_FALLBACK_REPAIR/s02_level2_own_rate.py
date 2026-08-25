# -*- coding: utf-8 -*-
"""M41 s02 -- does per-player history help LEVEL 2 too, as it did level 3?

E0-style diagnostic, NON-CLAIMING. Nothing here fits, adopts or ships a model. S42 untouched.

WHY. s01 found that level 3's repair works far better when it uses the player's OWN prior-season
mean minutes than any population constant -- 19.7% of the gap against 6.2%. Level 2 is the other
half of M38's repair and it still shrinks the fitted rate toward a GLOBAL prior-season rate. The
same question has not been asked of it, and s01 listed it as the obvious next step.

WHAT LEVEL 2 IS. A player with 1..PLAYER_SHORT_HISTORY_MAX prior appearances THIS SEASON -- an
EWMA over one or two observations, which cbs_v7 calls "a fallback wearing a model's clothes".
Exactly as with level 3, "short history this season" does not mean "no history": she may have a
full prior season behind her.

THE WEIGHT STAYS FROZEN. w = 0.60 was selected by M38 s03 on 2024-2025. It is NOT re-tuned here.
Re-tuning the weight beside a changed shrinkage TARGET would select two things against one
holdout, which is the error s03 itself was careful to avoid.

SELECT THEN CONFIRM. Variants are chosen on seasons < 2026 alone and 2026 is reported only as
confirmation. s01 had to declare a look at the holdout; this file is written before its own
numbers are computed, so no look is being declared -- but if the level-2 result contradicts the
level-3 one, that is a finding to report, not a reason to search for a third variant.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import s01_arm_legal as s01  # noqa: E402

HOLDOUT_SEASON = s01.HOLDOUT_SEASON
SHRINK_W = s01.SHRINK_W          # frozen at 0.60 -- see the module docstring


def build():
    """s01's frame plus each row's OWN prior-season points-per-minute rate."""
    d, pmin, prate, amin, arate = s01.build()
    mp = s01.masters()
    # her own rate across strictly prior seasons: prior points / prior minutes, a ratio of
    # sums rather than a mean of per-game ratios -- a 2-minute game must not count as much
    # as a 35-minute one.
    per = mp.groupby(["player_id", "season"]).agg(pts=("pts", "sum"), mn=("min", "sum"))
    per = per.reset_index()
    own = {}
    for s in sorted(d["season"].unique()):
        pr = per[per["season"] < s]
        if len(pr):
            g = pr.groupby("player_id").agg(pts=("pts", "sum"), mn=("mn", "sum"))
            own[s] = (g["pts"] / g["mn"]).replace([np.inf, -np.inf], np.nan)
    d["own_prior_rate"] = [own[r.season].get(r.player_id, np.nan) if r.season in own else np.nan
                           for r in d.itertuples()]
    return d, amin, arate


def repaired(sub, amin, arate, use_own_rate, w=SHRINK_W):
    """Level 3 fixed at s01's selected rule; only the LEVEL 2 target varies."""
    x = sub.copy()
    x["prior_rate"] = x["season"].map(arate)
    x["prior_min"] = x["season"].map(amin)
    tgt = (x["own_prior_rate"].fillna(x["prior_rate"]) if use_own_rate else x["prior_rate"])
    s2 = (x["fallback_level"] == 2) & tgt.notna()
    x.loc[s2, "pred_point"] = ((1 - w) * x.loc[s2, "rate_hat"]
                               + w * tgt[s2]) * x.loc[s2, "min_hat"]
    base_min = x["own_prior_min"].fillna(x["prior_min"])      # s01's selected level-3 rule
    s3 = (x["fallback_level"] == 3) & base_min.notna()
    x.loc[s3, "pred_point"] = x.loc[s3, "rate_hat"] * base_min[s3]
    return s01.response(x)


def main():
    res = {}
    print("=" * 94)
    print("M41 s02 -- does the player's OWN prior-season RATE improve the level-2 repair?")
    print("=" * 94)

    d, amin, arate = build()
    fit = d[d["season"] < HOLDOUT_SEASON]
    ho = d[d["season"] == HOLDOUT_SEASON]

    l2 = d[d["fallback_level"] == 2]
    cover = float(l2["own_prior_rate"].notna().mean())
    print("\nlevel-2 rows: %d; with a prior-SEASON rate of their own: %d (%.0f%%)"
          % (len(l2), int(l2["own_prior_rate"].notna().sum()), 100 * cover))
    res["level2_rows"] = int(len(l2))
    res["level2_own_history_pct"] = round(100 * cover, 1)
    print("shrinkage weight w = %.2f, FROZEN from M38 s03 -- not re-tuned here" % SHRINK_W)

    print("\n1. SELECTION ON SEASONS < %d (holdout not consulted, n=%d)"
          % (HOLDOUT_SEASON, len(fit)))
    sel = {"level-2 toward GLOBAL prior rate (s01's rule)": repaired(fit, amin, arate, False),
           "level-2 toward HER OWN prior rate": repaired(fit, amin, arate, True)}
    for k, v in sel.items():
        print("   %-46s %.4f" % (k, v))
    best = max((v, k) for k, v in sel.items())[1]
    print("   -> selected: %s" % best)
    res["selection_fit"] = {k: round(v, 4) for k, v in sel.items()}
    res["selected"] = best

    print("\n2. CONFIRMATION ON HELD-OUT %d (n=%d)" % (HOLDOUT_SEASON, len(ho)))
    cur = s01.response(ho)
    conf = {"current model": cur,
            "level-2 toward GLOBAL prior rate (s01's rule)": repaired(ho, amin, arate, False),
            "level-2 toward HER OWN prior rate": repaired(ho, amin, arate, True)}
    for k, v in conf.items():
        pct = "" if k == "current model" else ("   %5.1f%% of gap" % (100 * (v - cur) / abs(cur)))
        print("   %-46s %.4f%s" % (k, v, pct))
    res["confirmation_holdout"] = {k: round(v, 4) for k, v in conf.items()}
    res["gap_closed_pct"] = {k: round(100 * (v - cur) / abs(cur), 1)
                             for k, v in conf.items() if k != "current model"}

    g = res["gap_closed_pct"]["level-2 toward GLOBAL prior rate (s01's rule)"]
    o = res["gap_closed_pct"]["level-2 toward HER OWN prior rate"]
    print("\n" + "=" * 94)
    if o > g:
        print("PER-PLAYER HISTORY HELPS LEVEL 2 AS WELL: %.1f%% against %.1f%%." % (o, g))
    elif abs(o - g) < 0.05:
        print("NO MATERIAL DIFFERENCE: %.1f%% against %.1f%%. Level 2 does not behave like" % (o, g))
        print("level 3, and the simpler global target should be kept -- a change that buys")
        print("nothing is still a change that must be maintained and can break.")
    else:
        print("PER-PLAYER HISTORY IS WORSE AT LEVEL 2: %.1f%% against %.1f%%. Reported as a"
              % (o, g))
        print("negative result and NOT searched past -- hunting a third variant on the same")
        print("holdout is how a tuned number acquires an out-of-sample costume.")
    print("")
    # THIS EXPLANATION WAS PRE-WRITTEN FOR A NULL RESULT AND PRINTED REGARDLESS, which
    # made it a rationalisation rather than a reading -- it argued the shrinkage target
    # "matters less" at level 2 while the numbers showed it mattering MORE. Kept only on
    # the branch it actually describes.
    if o <= g:
        print("A level-2 row HAS current-season evidence, so its fitted rate is already")
        print("partly informative and the shrinkage target matters less. Level 3 had")
        print("nothing, so its constant was everything.")
    else:
        print("Note this did NOT have to happen: a level-2 row already carries some")
        print("current-season evidence, so the shrinkage target could have mattered less")
        print("here than at level 3, not more. It matters more. The reading is that one or")
        print("two games of current-season EWMA is a WORSE estimate of a player's scoring")
        print("rate than her whole previous season -- which is what calling it a fallback")
        print("wearing a model's clothes already implied, now measured.")
    print("")
    print("THE MODEL STILL LOSES on every line above. Nothing is implemented.")
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS_s02.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\nwrote FINDINGS_s02.json")


if __name__ == "__main__":
    main()
