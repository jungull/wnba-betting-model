# -*- coding: utf-8 -*-
"""M43 s03 -- the totals market, and whether the favourite bias CONCENTRATES.

E0-style diagnostic, NON-CLAIMING. Nothing here fits, adopts or ships a model. S42 closed.

TWO HYPOTHESES, BOTH DECLARED BEFORE THE NUMBERS.

H1 -- TOTALS. s01 and s02 tested only spreads. Over/under is a separate market with its own
standing bias in the literature (recreational money leans OVER, so unders can be shaded).
Two tests: flat OVER, flat UNDER.

H2 -- CONCENTRATION. s02's blocker is arithmetic: at +3.46% and a per-game sd near 0.95, the
underdog bias needs ~2,878 games to resolve, which is about 14 WNBA seasons. THE ONLY WAY
OUT IS A LARGER EDGE PER BET, because the games needed fall with the SQUARE of the edge --
double the edge and you need a quarter of the games. The favourite-longshot literature makes
a specific prediction: the shading GROWS WITH THE SPREAD, because a big favourite attracts
the most one-sided recreational money. That prediction is stated here before it is tested,
and it is tested ONCE, on terciles of spread size. It is not a search for whichever cut
clears zero.

WHY THE DISTINCTION MATTERS. If the bias concentrates as predicted, that is evidence it is
a real mechanism rather than noise, AND it shrinks the sample needed. If it does not
concentrate -- or concentrates in the wrong place, at SMALL spreads -- that is evidence
against the mechanism and the candidate weakens rather than strengthens.

THE BURDEN, CARRIED NOT HIDDEN. s01 declared four tests and s02 added two. This adds five
more (two totals, three terciles), so ELEVEN comparisons now stand behind this programme's
search for a flat bias. At 95% confidence, roughly one in twenty tests clears zero by
chance alone; at eleven tests the chance of at least one false positive is about 43%. Any
single interval that excludes zero here must be read against that, and it is stated with
the result rather than after it.
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

ROOT = s01.ROOT
NAME2ABV = s01.NAME2ABV
ODDS = os.path.join(ROOT, "data", "odds_capture", "capture_log.csv")
MTEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")

N_PRIOR_TESTS = 6          # s01's four sides + s02's two follow-ups


def totals_frame():
    """Last pre-tip total per (game, book), joined to the realised game total."""
    d = pd.read_csv(ODDS, low_memory=False)
    d = d[d["market"] == "totals"].copy()
    d["snap"] = pd.to_datetime(d["snapshot_utc"], format="%Y%m%dT%H%M%SZ",
                               errors="coerce", utc=True)
    d["tip"] = pd.to_datetime(d["commence_time"], errors="coerce", utc=True)
    d["point"] = pd.to_numeric(d["point"], errors="coerce")
    d["price"] = pd.to_numeric(d["price"], errors="coerce")
    d = d.dropna(subset=["snap", "tip", "point", "price"])
    d = d[d["snap"] < d["tip"]]                 # strictly pre-tip, as in s01
    d["h"] = d["home_team"].map(NAME2ABV)
    d["a"] = d["away_team"].map(NAME2ABV)
    d["side"] = d["outcome"].astype(str).str.strip().str.title()
    d = d.dropna(subset=["h", "a"])
    d = d[d["side"].isin(["Over", "Under"])]
    d["gd"] = d["tip"].dt.tz_convert("UTC").dt.date
    d = (d.sort_values("snap")
           .groupby(["h", "a", "gd", "bookmaker", "side"], as_index=False).last())

    mt = pd.read_parquet(MTEAM, columns=["game_id", "game_date", "team_abbreviation",
                                         "is_home", "pts"])
    mt["game_id"] = mt["game_id"].astype(str)
    hm = mt[mt["is_home"] == 1][["game_id", "game_date", "team_abbreviation", "pts"]]
    hm = hm.rename(columns={"team_abbreviation": "h", "pts": "hp"})
    aw = mt[mt["is_home"] == 0][["game_id", "team_abbreviation", "pts"]]
    aw = aw.rename(columns={"team_abbreviation": "a", "pts": "ap"})
    g = hm.merge(aw, on="game_id", how="inner")
    g["game_total"] = g["hp"] + g["ap"]
    g["gd"] = pd.to_datetime(g["game_date"]).dt.date

    # the odds tip is UTC, so an evening ET game carries the NEXT UTC date. Try both.
    m = d.merge(g[["game_id", "h", "a", "gd", "game_total"]], on=["h", "a", "gd"], how="left")
    miss = m["game_id"].isna()
    if miss.any():
        alt = d[miss.to_numpy()].copy()
        alt["gd"] = alt["gd"] - pd.Timedelta(days=1)
        alt = alt.merge(g[["game_id", "h", "a", "gd", "game_total"]],
                        on=["h", "a", "gd"], how="left")
        m = pd.concat([m[~miss.to_numpy()], alt], ignore_index=True)
    m = m.dropna(subset=["game_id", "game_total"])

    diff = m["game_total"] - m["point"]
    m["won"] = np.where(m["side"] == "Over", diff > 0, diff < 0)
    m["push"] = diff == 0
    m["profit"] = s01.american_profit(m["price"].to_numpy(float),
                                      m["won"].to_numpy(), m["push"].to_numpy())
    return m


def main():
    res = {}
    print("=" * 94)
    print("M43 s03 -- totals bias, and whether the favourite bias concentrates")
    print("=" * 94)

    rng = np.random.default_rng(s01.SEED)

    # ---------------- H1: totals -------------------------------------------
    t = totals_frame()
    print("\nH1 -- TOTALS. settled pre-tip quotes: %d over %d games"
          % (len(t), t["game_id"].nunique()))
    tot = {}
    for side in ("Over", "Under"):
        sub = t[t["side"] == side]
        r = s01.clustered_ci(sub, rng)
        if r is None:
            continue
        flag = "  <-- CLEARS ZERO" if r["lo"] > 0 else ""
        print("   %-8s %4d games  hit %5.1f%%  ROI %+6.2f%%  [%+.2f%%, %+.2f%%]%s"
              % (side, r["n_games"], 100 * r["hit"], 100 * r["roi"],
                 100 * r["lo"], 100 * r["hi"], flag))
        tot[side] = r
    res["totals"] = tot

    # ---------------- H2: does the spread bias concentrate? ----------------
    d = s01.build()
    dog = d[~d["is_fav"]].copy()
    dog["absspread"] = dog["odds_spread"].abs()
    # terciles of spread size, cut on the GAME's median quoted line so a game sits in one bin
    per_game = dog.groupby("game_id")["absspread"].median()
    q1, q2 = per_game.quantile([1 / 3, 2 / 3])
    band = pd.cut(per_game, [-np.inf, q1, q2, np.inf],
                  labels=["small (<=%.1f)" % q1, "mid", "large (>%.1f)" % q2])
    dog["band"] = dog["game_id"].map(band)

    print("\nH2 -- DOES THE UNDERDOG EDGE GROW WITH THE SPREAD? (prediction: YES)")
    print("   tercile cuts at %.1f and %.1f points" % (q1, q2))
    conc = {}
    for lbl in band.cat.categories:
        sub = dog[dog["band"] == lbl]
        r = s01.clustered_ci(sub, rng)
        if r is None:
            continue
        flag = "  <-- CLEARS ZERO" if r["lo"] > 0 else ""
        print("   %-16s %4d games  hit %5.1f%%  ROI %+6.2f%%  [%+.2f%%, %+.2f%%]%s"
              % (lbl, r["n_games"], 100 * r["hit"], 100 * r["roi"],
                 100 * r["lo"], 100 * r["hi"], flag))
        conc[str(lbl)] = r
    res["concentration"] = conc

    # is the ordering the predicted one?
    rois = [conc[str(l)]["roi"] for l in band.cat.categories if str(l) in conc]
    predicted = len(rois) == 3 and rois[0] < rois[1] < rois[2]
    print("\n   monotonically increasing with spread size, as predicted? %s"
          % ("YES" if predicted else "NO"))
    res["monotonic_as_predicted"] = bool(predicted)

    n_tests = N_PRIOR_TESTS + len(tot) + len(conc)
    fp = 1 - 0.95 ** n_tests
    print("\n" + "=" * 94)
    print("MULTIPLE COMPARISONS: %d tests now stand behind this search for a flat bias."
          % n_tests)
    print("At 95%% confidence the chance of AT LEAST ONE false positive is about %.0f%%."
          % (100 * fp))
    print("Any interval above that excludes zero must be read against that number.")
    res["n_tests_cumulative"] = int(n_tests)
    res["p_at_least_one_false_positive"] = round(float(fp), 3)
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS_s03.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=float)
    print("\nwrote FINDINGS_s03.json")


if __name__ == "__main__":
    main()
