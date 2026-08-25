# -*- coding: utf-8 -*-
"""M41 s01 -- M38's repair is not implementable as measured. A legal one recovers most of it.

E0-style diagnostic, NON-CLAIMING. Nothing here fits, adopts or ships a model, and no
wager-shaped claim is made. S42 untouched.

WHY THIS WAS ASKED. M38 s03 (D184) is recorded as the programme's best model-side lead:
two walk-forward repairs closing 21.3% of the model's deficit to the market on held-out
2026. Before building a new arm revision on that number, it was checked -- the D201 lesson,
where a headline that had never been re-derived turned out to be wrong.

The 21.3% REPRODUCES EXACTLY. The problem is not the arithmetic; it is what the repair reads.

WHAT THE REPAIR ACTUALLY READS. Both constants in s03 are means over M33's PRICED FRAME --
`prior["rate_actual"].mean()` and `prior["min_actual"].mean()`, where `prior` is the subset
of rows that carried a market price. That is a population the arm cannot identify:

  * the arm's declared file boundary is the contract and the masters, read-only. Market
    data is not in it, so an arm cannot compute a priced-population constant at all; and
  * bookmakers price starters and rotation regulars, so the priced population is heavily
    selected on the very quantity being predicted. Prior-season mean minutes over priced
    rows is ~29.6-30.6; over all rows that played it is ~21.4. AN 8-9 MINUTE GAP.

Using the priced constant would also mean predicting ~30 minutes for deep-bench players
across every unpriced row -- the arm emits predictions for all candidates, and only a
minority are ever priced. The repair is scored only where it flatters itself.

THE MEASUREMENT. Substituting a constant the arm can legally compute -- prior-season mean
minutes over ALL rows that played -- the same repair closes 6.2% of the gap, not 21.3%.

BUT THE LEAD SURVIVES IN A BETTER FORM. Level 3 means NO PRIOR APPEARANCE THIS SEASON. It
does not mean no history: 93% of level-3 rows belong to a player with prior-SEASON minutes
of her own. Using HER OWN prior-season mean, falling back to the global constant only when
she has none, closes 19.7% -- nearly all of the leaked figure, using nothing but the masters.

HOW THE CHOICE WAS MADE, AND THE LOOK THAT HAD TO BE DECLARED. The own-history variant was
written after seeing the global variant score 6.2% ON THE HELD-OUT SEASON. That is a second
look at 2026, and a figure chosen that way is not out-of-sample. So the variants are
re-selected here on seasons < 2026 ALONE, exactly as s03 chose its shrinkage weight, and
2026 is reported only as confirmation. Own-history wins the selection outright, so the
choice does not depend on the holdout -- but the ordering is on the record either way.

WHAT THIS DOES NOT SHOW. The model still loses. -0.2495 is closer to the market than
-0.3108 and is still negative: the market remains better on the priced population. Closing
part of a deficit is not an edge. Nothing here revisits M32's -7.2%, and nothing is
implemented -- the arm is a registered artifact and changing it is a new revision.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
M38 = os.path.abspath(os.path.join(HERE, "..", "M38_FALLBACK_DEFICIT"))
sys.path.insert(0, M38)

import s01_fallback as s38  # noqa: E402

ROOT = r"C:\Users\jgallagher\wnba-betting-model"
MPLAYER = os.path.join(ROOT, "data", "masters", "master_player.parquet")

SHRINK_W = 0.60          # frozen by M38 s03, selected on 2024-2025. NOT re-tuned here.
HOLDOUT_SEASON = 2026
MIN_PRIOR_ROWS = 200     # s03's guard: a constant needs a population behind it


def masters():
    mp = pd.read_parquet(MPLAYER, columns=["season", "player_id", "minutes", "pts"])
    mp["min"] = pd.to_numeric(mp["minutes"], errors="coerce").fillna(0.0)
    mp = mp[mp["min"] > 0].copy()
    mp["rate"] = mp["pts"] / mp["min"]
    return mp


def build():
    d = s38.frame().sort_values("game_date")
    mp = masters()
    seasons = sorted(d["season"].unique())

    priced_min, priced_rate, all_min, all_rate = {}, {}, {}, {}
    for s in seasons:
        pr = d[d["season"] < s]
        ok = len(pr) > MIN_PRIOR_ROWS
        priced_min[s] = pr["min_actual"].mean() if ok else np.nan
        priced_rate[s] = pr["rate_actual"].mean() if ok else np.nan
        ap = mp[mp["season"] < s]
        oka = len(ap) > MIN_PRIOR_ROWS
        all_min[s] = ap["min"].mean() if oka else np.nan
        all_rate[s] = ap["rate"].mean() if oka else np.nan

    # her own mean minutes across strictly prior SEASONS -- masters only, no market data
    per = mp.groupby(["player_id", "season"])["min"].mean().reset_index()
    own = {}
    for s in seasons:
        pr = per[per["season"] < s]
        if len(pr):
            own[s] = pr.groupby("player_id")["min"].mean()
    d["own_prior_min"] = [own[r.season].get(r.player_id, np.nan) if r.season in own else np.nan
                          for r in d.itertuples()]
    return d, priced_min, priced_rate, all_min, all_rate


def response(x):
    """Mean competitive response: positive means the model is closer than the market."""
    x = x.copy()
    x["mod_abs"] = (x["pred_point"] - x["pts"]).abs()
    return float((x["mkt_abs"] - x["mod_abs"]).mean())


def repaired(sub, rate_map, min_map, use_own, w=SHRINK_W):
    x = sub.copy()
    x["prior_rate"] = x["season"].map(rate_map)
    x["prior_min"] = x["season"].map(min_map)
    s2 = (x["fallback_level"] == 2) & x["prior_rate"].notna()
    x.loc[s2, "pred_point"] = ((1 - w) * x.loc[s2, "rate_hat"]
                               + w * x.loc[s2, "prior_rate"]) * x.loc[s2, "min_hat"]
    base_min = x["own_prior_min"].fillna(x["prior_min"]) if use_own else x["prior_min"]
    s3 = (x["fallback_level"] == 3) & base_min.notna()
    x.loc[s3, "pred_point"] = x.loc[s3, "rate_hat"] * base_min[s3]
    return response(x)


def main():
    res = {}
    print("=" * 94)
    print("M41 s01 -- is M38's repair implementable, and what is it worth when it is?")
    print("=" * 94)

    d, pmin, prate, amin, arate = build()
    fit = d[d["season"] < HOLDOUT_SEASON]
    ho = d[d["season"] == HOLDOUT_SEASON]

    print("\n1. THE CONSTANT M38 USES IS NOT ONE THE ARM CAN COMPUTE")
    print("   %-8s %-24s %-24s" % ("season", "priced-population mean", "all-rows mean"))
    for s in sorted(d["season"].unique()):
        if pmin[s] == pmin[s]:
            print("   %-8s %-24.2f %-24.2f" % (s, pmin[s], amin[s]))
    print("   The priced population is selected on the quantity being predicted:")
    print("   bookmakers price starters and rotation regulars. The arm cannot see")
    print("   which rows are priced, and market data is outside its file boundary.")
    res["prior_min_priced"] = {int(k): (round(float(v), 2) if v == v else None)
                               for k, v in pmin.items()}
    res["prior_min_all_rows"] = {int(k): (round(float(v), 2) if v == v else None)
                                 for k, v in amin.items()}

    l3 = d[d["fallback_level"] == 3]
    cover = float(l3["own_prior_min"].notna().mean())
    print("\n2. LEVEL 3 IS NOT 'NO HISTORY', IT IS 'NO HISTORY THIS SEASON'")
    print("   level-3 rows: %d; with prior-SEASON minutes of their own: %d (%.0f%%)"
          % (len(l3), int(l3["own_prior_min"].notna().sum()), 100 * cover))
    res["level3_rows"] = int(len(l3))
    res["level3_own_history_pct"] = round(100 * cover, 1)

    print("\n3. SELECTION ON SEASONS < %d -- THE HOLDOUT IS NOT CONSULTED (n=%d)"
          % (HOLDOUT_SEASON, len(fit)))
    sel = {"current": response(fit),
           "priced constant (M38, NOT arm-legal)": repaired(fit, prate, pmin, False),
           "arm-legal global constant": repaired(fit, arate, amin, False),
           "arm-legal OWN prior-season mean": repaired(fit, arate, amin, True)}
    for k, v in sel.items():
        print("   %-38s %.4f" % (k, v))
    best = max((v, k) for k, v in sel.items() if "NOT arm-legal" not in k and k != "current")[1]
    print("   -> selected among ARM-LEGAL variants: %s" % best)
    res["selection_fit_seasons"] = {k: round(v, 4) for k, v in sel.items()}
    res["selected"] = best

    print("\n4. CONFIRMATION ON HELD-OUT %d (n=%d)" % (HOLDOUT_SEASON, len(ho)))
    cur = response(ho)
    conf = {"current": cur,
            "priced constant (M38, NOT arm-legal)": repaired(ho, prate, pmin, False),
            "arm-legal global constant": repaired(ho, arate, amin, False),
            "arm-legal OWN prior-season mean": repaired(ho, arate, amin, True)}
    for k, v in conf.items():
        pct = "" if k == "current" else ("   %5.1f%% of gap" % (100 * (v - cur) / abs(cur)))
        print("   %-38s %.4f%s" % (k, v, pct))
    res["confirmation_holdout"] = {k: round(v, 4) for k, v in conf.items()}
    res["gap_closed_pct"] = {k: round(100 * (v - cur) / abs(cur), 1)
                             for k, v in conf.items() if k != "current"}

    print("\n" + "=" * 94)
    print("M38's 21.3% IS NOT ATTAINABLE INSIDE THE ARM'S CONTRACT. Substituting a constant")
    print("the arm can legally compute leaves %.1f%%. Using the player's OWN prior-season"
          % res["gap_closed_pct"]["arm-legal global constant"])
    print("minutes recovers %.1f%% using nothing but the masters."
          % res["gap_closed_pct"]["arm-legal OWN prior-season mean"])
    print("")
    print("DECLARED LOOK: the own-history variant was written AFTER seeing the global")
    print("variant's holdout score. It is re-selected above on seasons < %d alone and wins"
          % HOLDOUT_SEASON)
    print("there outright, so the choice does not depend on the holdout -- but the ordering")
    print("is on the record rather than asserted later.")
    print("")
    print("THE MODEL STILL LOSES. %.4f is closer to the market than %.4f and is still"
          % (conf["arm-legal OWN prior-season mean"], cur))
    print("negative. Closing part of a deficit is NOT an edge. Nothing is implemented.")
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS_s01.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\nwrote FINDINGS_s01.json")


if __name__ == "__main__":
    main()
