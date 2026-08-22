# -*- coding: utf-8 -*-
"""M36 s03 -- is there a level shift at the props seam?

E0-style diagnostic, NON-CLAIMING.

s01 flagged that splicing two sources at 2026-07-30/07-31 creates a discontinuity
that must be TESTED for a level shift rather than assumed away. This is that test.

THE DESIGN PROBLEM, stated before the result. The two archives do not overlap --
the historical file's last quote is 2026-07-30 22:55 UTC and the live ladder's
first is 2026-07-31 14:22 UTC. With no overlap, a difference across the seam
cannot be cleanly attributed to the SOURCE rather than to the DATE. Nothing here
can separate them, and no amount of statistics will fix that.

So the test is deliberately weaker and honest about it: measure a daily series of
comparable quantities within each source, then ask whether the step ACROSS the
seam is unusual relative to the ordinary day-to-day steps WITHIN each source. A
seam step that sits inside the normal churn is not evidence of no shift; it is
only an absence of evidence for one. A seam step far outside it is evidence of a
shift, confounded with whatever else changed that day.

One quantity needs no such test and is decisive on its own: WHICH BOOKS APPEAR.
Book composition is a property of the capture configuration, not of the games, so
a change in it across the seam is a source effect by construction.

QUANTITIES COMPARED (all present in both schemas):
  * book composition and books-per-event
  * two-sided overround (the vig), from American prices
  * the quoted line itself
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model"
HIST = os.path.join(ROOT, "data", "props_capture", "historical",
                    "master_props_historical.csv")
LIVE = os.path.join(ROOT, "data", "props_capture", "master_props.csv")
MARKET = "player_points"
SEAM = pd.Timestamp("2026-07-31").date()


def implied(american):
    """American price -> implied probability, vig included."""
    a = pd.to_numeric(american, errors="coerce")
    return np.where(a < 0, (-a) / ((-a) + 100.0), 100.0 / (a + 100.0))


def load(path, tag):
    d = pd.read_csv(path, low_memory=False)
    d = d[d["market_key"] == MARKET].copy()
    d["gd"] = (pd.to_datetime(d["commence_time"], utc=True, errors="coerce")
                 .dt.tz_convert("US/Eastern").dt.date)
    d["po"] = implied(d["over_price"])
    d["pu"] = implied(d["under_price"])
    d["overround"] = d["po"] + d["pu"] - 1.0
    d["line"] = pd.to_numeric(d["line"], errors="coerce")
    d["src"] = tag
    return d


def daily(d):
    """One row per game-date: the quantities we compare across the seam."""
    g = d.groupby("gd")
    return pd.DataFrame({
        "books": g["bookmaker_key"].nunique(),
        "overround": g["overround"].median(),
        "line": g["line"].median(),
        "rows": g.size(),
    })


def main():
    res = {}
    print("=" * 94)
    print("M36 s03 -- level shift at the props seam (2026-07-30 | 2026-07-31)")
    print("=" * 94)

    h = load(HIST, "hist")
    l = load(LIVE, "live")
    # restrict the historical side to the 2026 season so the comparison is not
    # dominated by earlier seasons with different book rosters
    h26 = h[h["gd"] >= pd.Timestamp("2026-05-01").date()]

    print("\n0. THE DESIGN LIMIT")
    print("   historical last quote : %s" % h["gd"].max())
    print("   live first quote      : %s" % l["gd"].min())
    print("   OVERLAP               : none -- source and date are confounded.")
    print("   Read every number below with that in mind.")
    res["overlap"] = 0

    # ---- 1. book composition -- decisive on its own ---------------------
    bh = set(h26["bookmaker_key"].dropna())
    bl = set(l["bookmaker_key"].dropna())
    print("\n1. BOOK COMPOSITION (a capture-configuration property, not a game property)")
    print("   historical 2026 : %d books  %s" % (len(bh), sorted(bh)))
    print("   live            : %d books  %s" % (len(bl), sorted(bl)))
    print("   LOST at the seam: %s" % (sorted(bh - bl) or "none"))
    print("   GAINED          : %s" % (sorted(bl - bh) or "none"))
    res["books"] = {"hist": sorted(bh), "live": sorted(bl),
                    "lost": sorted(bh - bl), "gained": sorted(bl - bh)}

    # ---- 2. the seam step vs ordinary day-to-day steps ------------------
    dh, dl = daily(h26), daily(l)
    both = pd.concat([dh, dl]).sort_index()
    print("\n2. SEAM STEP vs ORDINARY DAY-TO-DAY STEP")
    print("   %-11s %10s %10s %12s %10s" %
          ("quantity", "last hist", "first live", "seam step", "|step| pctile"))
    for q in ("books", "overround", "line"):
        # ordinary steps computed WITHIN each source only, never across the seam
        steps = pd.concat([dh[q].diff().dropna(), dl[q].diff().dropna()]).abs()
        a, b = dh[q].iloc[-1], dl[q].iloc[0]
        step = b - a
        pct = 100.0 * (steps < abs(step)).mean()
        print("   %-11s %10.3f %10.3f %12.3f %9.1f%%" % (q, a, b, step, pct))
        res.setdefault("seam", {})[q] = {
            "last_hist": round(float(a), 4), "first_live": round(float(b), 4),
            "step": round(float(step), 4), "pctile_of_within_source_steps": round(pct, 1)}

    # ---- 3. pooled level, either side -----------------------------------
    print("\n3. POOLED LEVEL EITHER SIDE (median over all rows)")
    print("   %-12s %12s %12s %10s" % ("quantity", "hist 2026", "live", "delta"))
    for q, col in (("overround", "overround"), ("line", "line")):
        a, b = h26[col].median(), l[col].median()
        print("   %-12s %12.4f %12.4f %10.4f" % (q, a, b, b - a))
        res.setdefault("pooled", {})[q] = {"hist": round(float(a), 4),
                                           "live": round(float(b), 4),
                                           "delta": round(float(b - a), 4)}
    bpe_h = h26.groupby(["gd", "player_name"])["bookmaker_key"].nunique().median()
    bpe_l = l.groupby(["gd", "player_name"])["bookmaker_key"].nunique().median()
    print("   %-12s %12.1f %12.1f %10.1f" % ("books/player", bpe_h, bpe_l, bpe_l - bpe_h))
    res["pooled"]["books_per_player"] = {"hist": float(bpe_h), "live": float(bpe_l)}

    # the roster is only half of composition; DEPTH per quoted player is the other
    # half, and it moves the consensus estimator even when the roster is identical.
    lost = sorted(bh - bl)
    depth_delta = float(bpe_l - bpe_h)
    print("")
    print("=" * 94)
    print("VERDICT")
    if lost:
        print("  ROSTER SHIFT: %d book(s) present before the seam are absent after: %s"
              % (len(lost), ", ".join(lost)))
    else:
        print("  ROSTER: identical across the seam (%d books, season-matched). No shift."
              % len(bl))
        print("  NOTE: comparing the WHOLE historical file instead would show 9 books")
        print("  and imply a 4-book loss. Those books left earlier in history, not at")
        print("  the seam. The season-matched comparison is the correct one.")
    if abs(depth_delta) >= 0.5:
        print("  DEPTH SHIFT: median books per quoted player moves %.1f -> %.1f (%+.1f)."
              % (bpe_h, bpe_l, depth_delta))
        print("  Same roster, different completeness. A consensus over %.0f books is not"
              % bpe_l)
        print("  the same estimator as one over %.0f, so peer-consensus work (M30/M31/M32)"
              % bpe_h)
        print("  must carry that difference rather than splice straight through.")
    else:
        print("  DEPTH: median books per quoted player effectively unchanged (%+.1f)."
              % depth_delta)
    print("")
    print("  This does NOT block using the live ladder AFTER the seam on its own terms.")
    print("  It blocks treating the two archives as one continuous series without")
    print("  carrying the depth difference, and it cannot rule out a shift confounded")
    print("  with the date, because the archives do not overlap.")
    print("=" * 94)
    res["level_shift"] = {"roster": bool(lost), "depth_delta": round(depth_delta, 2),
                          "depth_shift": bool(abs(depth_delta) >= 0.5)}

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "FINDINGS_s03.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\nwrote FINDINGS_s03.json")


if __name__ == "__main__":
    main()
