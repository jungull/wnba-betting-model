# -*- coding: utf-8 -*-
"""M39 -- when a WNBA rotation regular sits, where do her minutes actually go?

E0-style diagnostic, NON-CLAIMING. Nothing here fits, adopts or ships a model.

WHY. The minutes model forecasts each player from her own history alone -- the EWMA is grouped
by (player_id, season) and no teammate term exists anywhere in it. So when a starter is ruled
out, the model predicts every teammate exactly as if nothing had happened. Team minutes are a
hard constraint (200 per team-game; 95.6% of team-games are within one minute of exactly 200),
so those minutes MUST go somewhere.

John asked the right question before any modelling: does an absence move everyone's minutes a
little, does one designated substitute absorb them, or is it a rotation? The architecture
depends entirely on the answer, and it is measurable.

METHOD. Each player's baseline is her trailing mean minutes within team-season, using prior
games only. A "rotation regular" averages 15+ minutes. The clean case is a team-game where
EXACTLY ONE regular is absent and at least seven teammates played -- isolating one absence
rather than trying to untangle several at once.

THE TRAP THIS FILE EXISTS TO AVOID. "The top absorber" is chosen AFTER seeing the result, so
asking "was it the same player again?" over the same events is circular: with two events, the
most common absorber is at minimum 50% by construction. That inflated version returns 64%. The
honest test is PREDICTIVE -- for each absence after the first, predict the absorber from PRIOR
absences only and score it -- and it returns 36%. Both are reported so the difference is
visible.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\jgallagher\wnba-betting-model"
MPLAYER = os.path.join(ROOT, "data", "masters", "master_player.parquet")

REGULAR_MIN = 15.0        # a rotation regular averages this many minutes
MIN_PRESENT = 7           # a plausible rotation, not a decimated roster
MIN_PRIOR = 3             # games needed before a baseline means anything


def events():
    mp = pd.read_parquet(MPLAYER)
    mp["gd"] = pd.to_datetime(mp["game_date"])
    mp["min"] = pd.to_numeric(mp["minutes"], errors="coerce").fillna(0.0)
    mp = mp.sort_values(["team_id", "season", "gd", "game_id"])
    mp["base"] = (mp.groupby(["team_id", "season", "player_id"])["min"]
                    .transform(lambda s: s.shift(1).expanding(min_periods=MIN_PRIOR).mean()))
    mp["played"] = mp["min"] > 0
    d = mp.dropna(subset=["base"]).copy()
    d["regular"] = d["base"] >= REGULAR_MIN

    out = []
    for (gid, tid), s in d.groupby(["game_id", "team_id"]):
        ab = s[s["regular"] & ~s["played"]]
        if len(ab) != 1:                       # isolate the single-absence case
            continue
        a = ab.iloc[0]
        pr = s[s["played"]].copy()
        if len(pr) < MIN_PRESENT:
            continue
        pr["delta"] = pr["min"] - pr["base"]
        top = pr.loc[pr["delta"].idxmax()]
        out.append({"gd": a["gd"], "season": int(a["season"]), "team_id": tid,
                    "absent": a["player_id"], "lost": float(a["base"]),
                    "absorber": top["player_id"], "n_cand": int(len(pr)),
                    "top1": float(pr["delta"].max()),
                    "top2": float(pr["delta"].nlargest(2).sum()),
                    "top3": float(pr["delta"].nlargest(3).sum()),
                    "n_gained": int((pr["delta"] > 0).sum())})
    return pd.DataFrame(out).sort_values("gd")


def main():
    res = {}
    print("=" * 94)
    print("M39 -- where do an absent regular's minutes go?")
    print("=" * 94)

    r = events()
    print("\nclean single-absence team-games: %d" % len(r))
    print("the absent regular normally plays %.1f minutes" % r["lost"].mean())

    print("\n1. HOW CONCENTRATED IS THE ABSORPTION?")
    for k, lbl in (("top1", "the single biggest gainer"),
                   ("top2", "the top two gainers"),
                   ("top3", "the top three gainers")):
        pct = 100 * (r[k] / r["lost"]).median()
        print("   %-26s absorb %3.0f%% of the lost minutes (median)" % (lbl, pct))
        res[k + "_pct"] = round(float(pct), 0)
    print("   teammates gaining ANY minutes: median %.0f of %.0f who played"
          % (r["n_gained"].median(), r["n_cand"].median()))
    print("\n   => neither 'one designated substitute' nor 'everyone shifts a little'.")
    print("      One player takes the bulk, a second takes most of the rest, and a")
    print("      broad group picks up small change.")
    res["n_gained_median"] = float(r["n_gained"].median())
    res["n_events"] = int(len(r))
    res["lost_mean"] = round(float(r["lost"].mean()), 1)

    # ---- who: the circular version, then the honest one ------------------
    rep = r.groupby(["season", "team_id", "absent"]).filter(lambda x: len(x) >= 2)
    same = (rep.groupby(["season", "team_id", "absent"])["absorber"]
               .apply(lambda s: s.value_counts().iloc[0] / len(s)))
    print("\n2. IS THE ABSORBER THE SAME PERSON EACH TIME?")
    print("   CIRCULAR version (most common absorber scored on the same events):")
    print("     mean %.0f%%, median %.0f%% -- INFLATED BY CONSTRUCTION. With two events the"
          % (100 * same.mean(), 100 * same.median()))
    print("     most common absorber is at minimum 50%. Do not quote this.")

    hit = miss = 0
    chance = []
    for _, g in r.groupby(["season", "team_id", "absent"]):
        seen = []
        for _, row in g.sort_values("gd").iterrows():
            if seen:
                pred = pd.Series(seen).value_counts().idxmax()
                hit += int(pred == row["absorber"])
                miss += int(pred != row["absorber"])
                chance.append(1.0 / row["n_cand"])
            seen.append(row["absorber"])
    n = hit + miss
    acc = hit / n
    ch = float(np.mean(chance))
    print("\n   PREDICTIVE version (predict from PRIOR absences only) -- quote this one:")
    print("     %d events scored, %d correct = %.0f%%" % (n, hit, 100 * acc))
    print("     chance level given the candidate pool: %.0f%%" % (100 * ch))
    print("     lift over chance: %.1fx" % (acc / ch))
    res["predictive"] = {"n": n, "accuracy": round(acc, 3), "chance": round(ch, 3),
                         "lift": round(acc / ch, 2)}
    res["circular_inflated"] = round(float(same.mean()), 3)

    print("\n" + "=" * 94)
    print("WHAT THIS MEANS FOR THE MODEL")
    print("  A hard depth-chart successor -- 'player X always covers player Y' -- would be")
    print("  WRONG ABOUT TWO TIMES IN THREE. But the absorber is far from random: 3.3x chance")
    print("  is a real, learnable signal.")
    print("  So the right shape is a PROBABILISTIC SHARE REALLOCATION: when a player is out,")
    print("  her freed minutes are distributed across teammates by a learned propensity, with")
    print("  most of the mass on one or two, rather than handed to a single designated heir.")
    print("  And it can only run at all if we know WHO IS OUT before tip -- which is the")
    print("  forecast-cutoff question, not a modelling question.")
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\nwrote FINDINGS.json")


if __name__ == "__main__":
    main()
