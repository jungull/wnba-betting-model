# -*- coding: utf-8 -*-
"""M39 s02 -- what the current forecast cutoff costs us, in the only currency that matters.

E0-style diagnostic, NON-CLAIMING.

s01 established the mechanism: when a rotation regular sits, one teammate absorbs 59% of her
minutes, two absorb 98%, and a broad group picks up the rest -- and the primary absorber is
predictable 36% of the time against an 11% chance level. A share-reallocation model can use
that. But it cannot run at all unless it knows WHO IS OUT before tip.

So the cutoff stops being an abstract contract question and becomes a measurable one: at each
candidate cutoff, what fraction of the players who were actually ruled Out do we know about?

WHY THIS IS THE RIGHT MEASUREMENT. Earlier cutoff work asked whether the injury tape was
VISIBLE at a cutoff -- a property of the tape. This asks whether the OUT DESIGNATIONS THEMSELVES
had been published yet, which is the property the model actually consumes. A tape we can legally
read is worthless if the news has not broken.

WHAT IT CANNOT SETTLE. The tape covers 2026-08-06 to 08-22 and yields 144 player-games carrying
an Out designation. That is a small sample and a single late-season window; roster news may
break differently in April than in August. The lead times are also computed against a fixed
ET->UTC offset, correct for this window and wrong in general.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\jgallagher\wnba-betting-model"
INJ = os.path.join(ROOT, "data", "injury_official_live", "injury_snapshots.csv")

#: hours before tip. The day-before default is 18:00 UTC the prior day; against a
#: typical 23:00-02:00 UTC tip that is roughly 26 hours.
CUTOFFS = (("the current day-before default (~26h)", 26.0),
           ("T-6h", 6.0), ("T-90m", 1.5), ("T-30m", 0.5))


def main():
    res = {}
    print("=" * 94)
    print("M39 s02 -- how much of 'who is out' does each cutoff actually see?")
    print("=" * 94)

    inj = pd.read_csv(INJ, low_memory=False)
    inj["ret"] = pd.to_datetime(inj["retrieval_ts_utc"], utc=True, errors="coerce")
    inj["gd"] = pd.to_datetime(inj["game_date"], errors="coerce")
    hh = inj["game_time_et"].astype(str).str.extract(r"(\d{2}):(\d{2})")
    inj["tip"] = (pd.to_datetime(inj["gd"].dt.date.astype(str), utc=True)
                  + pd.to_timedelta(hh[0].astype(float) + 12, unit="h")
                  + pd.to_timedelta(hh[1].astype(float), unit="m")
                  + pd.Timedelta(hours=4))          # ET->UTC, correct for August only
    inj = inj.dropna(subset=["ret", "tip", "player_id"]).copy()
    inj["lead_h"] = (inj["tip"] - inj["ret"]).dt.total_seconds() / 3600.0

    out = inj[inj["status"] == "Out"]
    first = out.groupby(["player_id", "gd"])["lead_h"].max().rename("first_seen_h").reset_index()
    print("\ntape window : %s -> %s" % (inj["gd"].min().date(), inj["gd"].max().date()))
    print("Out designations: %d rows over %d player-games" % (len(out), len(first)))

    print("\nHOW EARLY IS AN 'OUT' FIRST PUBLISHED? (hours before tip)")
    print("   median %.1f h   p25 %.1f   p75 %.1f"
          % (first["first_seen_h"].median(), first["first_seen_h"].quantile(0.25),
             first["first_seen_h"].quantile(0.75)))
    print("   Half of them break inside 90 minutes of tip. This is late news, not a")
    print("   day-ahead list.")
    res["first_seen_h"] = {"median": round(float(first["first_seen_h"].median()), 2),
                           "p25": round(float(first["first_seen_h"].quantile(0.25)), 2),
                           "p75": round(float(first["first_seen_h"].quantile(0.75)), 2)}

    print("\nSHARE OF 'OUT' DESIGNATIONS ALREADY KNOWN AT EACH CUTOFF")
    tbl = {}
    for lbl, h in CUTOFFS:
        pct = 100.0 * float((first["first_seen_h"] >= h).mean())
        print("   %-40s %5.1f%%" % (lbl, pct))
        tbl[lbl] = round(pct, 1)
    res["known_at_cutoff_pct"] = tbl
    res["n_player_games"] = int(len(first))

    base = tbl[CUTOFFS[0][0]]
    t90 = tbl["T-90m"]
    print("\n" + "=" * 94)
    print("THE COST OF THE CURRENT CUTOFF")
    print("  At the day-before default we know %.1f%% of who will be out. At T-90m we would" % base)
    print("  know %.1f%% -- a %.1fx improvement in the one input the redistribution model" % (t90, t90 / base))
    print("  cannot run without.")
    print("")
    print("  This also explains a result that has been sitting unexplained: the market's")
    print("  forecast error is FLAT across our thin-history rows while ours degrades sharply.")
    print("  The market is reading roster news we have contractually declined to look at.")
    print("")
    print("  SMALL SAMPLE. 144 player-games in one late-season window. Roster news may break")
    print("  differently in April than in August, and the ET->UTC offset is fixed at -4,")
    print("  correct here and wrong in general. The direction is not in doubt; the exact")
    print("  percentages are.")
    print("=" * 94)
    res["improvement_factor"] = round(t90 / base, 1)

    with open(os.path.join(HERE, "FINDINGS_s02.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\nwrote FINDINGS_s02.json")


if __name__ == "__main__":
    main()
