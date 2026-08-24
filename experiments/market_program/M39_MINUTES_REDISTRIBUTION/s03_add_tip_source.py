# -*- coding: utf-8 -*-
"""M39 s03 -- add the injury capture as a tip-time source and see whether games move to exact.

E0-style diagnostic, NON-CLAIMING. It regenerates no contract and modifies no frozen artifact.

WHAT WAS ASSUMED, AND WHAT TURNED OUT TO BE TRUE. The cutoff looked like a policy that needed
revising. It is not. `apply_cutoff_policy` already sets the cutoff to tip-90m wherever a tip
time is KNOWN, and falls back to the day before only where it is not. The 71.9% of rows on the
day-before policy are there because no qualifying tip observation exists -- not because a rule
forbids anything. `load_tip_observations` reads exactly two sources: the historical props
archive and the odds extension.

So the fix is additive: a THIRD source. The injury capture records `game_time_et` beside
`retrieval_ts_utc`, which is precisely the (tip, observed_at) pair the resolver wants.

THE MACHINERY IS IMPORTED, NOT REIMPLEMENTED. `resolve_tip_times` and `apply_cutoff_policy`
come from prediction_contract_v2 unchanged. If they were copied here, this would prove that a
copy behaves well and nothing about the real thing. The hard post-condition inside
`apply_cutoff_policy` -- every exact row must show its tip was observed strictly before its own
cutoff -- runs untouched and must still pass. The rule is not being relaxed; it is being fed.

WHAT THIS DOES NOT DO. It does not bind the source into the live contract. That is a v6 in the
established v2->v3->v4->v5 lineage, where each revision supersedes its predecessor, reads it,
and proves that the one thing that changed is the thing meant to change. This is the evidence
that such a revision is worth building.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, WT)
ROOT = r"C:\Users\jgallagher\wnba-betting-model"
INJ = os.path.join(ROOT, "data", "injury_official_live", "injury_snapshots.csv")
MTEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")

from prediction_contract_v2 import (          # noqa: E402  -- imported, never copied
    apply_cutoff_policy, load_tip_observations, resolve_tip_times)

NAME2ABV = {
    "Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
    "Dallas Wings": "DAL", "Golden State Valkyries": "GSV", "Indiana Fever": "IND",
    "Los Angeles Sparks": "LAS", "Las Vegas Aces": "LVA", "Minnesota Lynx": "MIN",
    "New York Liberty": "NYL", "Portland Fire": "PDX", "Phoenix Mercury": "PHX",
    "Seattle Storm": "SEA", "Toronto Tempo": "TOR", "Washington Mystics": "WAS",
}


def injury_tip_observations():
    """The new source, in exactly the shape the resolver already consumes.

    `game_time_et` is the tip as the provider reported it at that moment;
    `retrieval_ts_utc` is when we held it. Both are per-capture, so a revised tip appears
    as a later observation rather than overwriting an earlier one -- which is what makes the
    resolver's revision-awareness work.
    """
    inj = pd.read_csv(INJ, low_memory=False)
    hh = inj["game_time_et"].astype(str).str.extract(r"(\d{2}):(\d{2})")
    gd = pd.to_datetime(inj["game_date"], errors="coerce")
    # ET -> UTC, fixed -4. Correct for this August window and WRONG IN GENERAL; a bound
    # revision must resolve the offset properly rather than inherit this.
    tip = (pd.to_datetime(gd.dt.date.astype(str), utc=True, errors="coerce")
           + pd.to_timedelta(hh[0].astype(float) + 12, unit="h")
           + pd.to_timedelta(hh[1].astype(float), unit="m")
           + pd.Timedelta(hours=4))
    # The tape carries `matchup` as AWAY@HOME in ABBREVIATIONS already -- a cleaner
    # bridge than mapping club names. An earlier pass assumed home_team/away_team
    # columns that do not exist, silently produced zero observations, and reported
    # "no games moved" as though it were a finding rather than a broken join.
    mu = inj["matchup"].astype(str).str.strip().str.upper()
    obs = pd.DataFrame({
        "away": mu.str.split("@").str[0].str.strip(),
        "home": mu.str.split("@").str[-1].str.strip(),
        "gd": gd.dt.date, "tip": tip,
        "observed_at": pd.to_datetime(inj["retrieval_ts_utc"], utc=True, errors="coerce"),
        "source": "injury_capture"})
    return obs.dropna(subset=["tip", "observed_at", "gd"])


def resolve_game_ids(obs):
    """Attach game_id by (ET game-date, home, away) -- the same bridge M36 verified."""
    mt = pd.read_parquet(MTEAM)
    mt["gd"] = pd.to_datetime(mt["game_date"]).dt.date
    g = mt[mt["is_home"] == 1][["game_id", "gd", "team_abbreviation",
                                "opp_team_abbreviation"]].copy()
    g.columns = ["game_id", "gd", "h", "a"]
    g["h"] = g["h"].replace({"PHO": "PHX"})
    g["a"] = g["a"].replace({"PHO": "PHX"})
    o = obs.copy()
    o["h"] = o["home"].replace({"PHO": "PHX"})      # already abbreviations
    o["a"] = o["away"].replace({"PHO": "PHX"})
    o = o.dropna(subset=["h", "a"])
    m = o.merge(g, on=["gd", "h", "a"], how="inner")
    return m[["game_id", "tip", "observed_at", "source"]].assign(
        game_id=lambda d: d["game_id"].astype(str))


def main():
    res = {}
    print("=" * 94)
    print("M39 s03 -- add the injury capture as a tip source; do games move to exact?")
    print("=" * 94)

    existing = load_tip_observations()
    print("\nEXISTING tip observations: %d" % len(existing))
    print("  by source: %s" % existing["source"].value_counts().to_dict())

    new = resolve_game_ids(injury_tip_observations())
    print("\nNEW source (injury capture): %d observations over %d games"
          % (len(new), new["game_id"].nunique()))

    # games the resolver will be asked about: those the new source can speak to
    gids = sorted(set(new["game_id"]))
    games = pd.DataFrame({"game_id": gids})
    mt = pd.read_parquet(MTEAM)
    mt["game_id"] = mt["game_id"].astype(str)
    gd = mt.drop_duplicates("game_id").set_index("game_id")["game_date"]
    games["game_date"] = pd.to_datetime(games["game_id"].map(gd)).dt.date

    print("\nRunning the REAL resolver (imported from prediction_contract_v2, unmodified).")
    out = {}
    for label, obs in (("BEFORE -- existing sources only", existing),
                       ("AFTER  -- with the injury capture", pd.concat([existing, new],
                                                                       ignore_index=True))):
        sub = obs[obs["game_id"].astype(str).isin(gids)]
        tips, audit = resolve_tip_times(games.copy(), sub)
        g = apply_cutoff_policy(tips.merge(games, on="game_id", how="left"))
        n_exact = int(g["exact_cutoff_ok"].sum())
        out[label] = {"n_games": int(len(g)), "exact": n_exact,
                      "date_only": int(len(g) - n_exact),
                      "observations_used": int(len(sub)),
                      "post_condition_failures":
                          int(g.attrs.get("exact_rows_failing_observed_before_cutoff", -1))}
        print("\n  %s" % label)
        print("    observations available : %d" % len(sub))
        print("    games EXACT (T-90m)    : %d of %d" % (n_exact, len(g)))
        print("    games date-only        : %d" % (len(g) - n_exact))
        print("    hard post-condition failures: %d"
              % g.attrs.get("exact_rows_failing_observed_before_cutoff", -1))
    res["resolver"] = out

    b = out["BEFORE -- existing sources only"]
    a = out["AFTER  -- with the injury capture"]
    moved = a["exact"] - b["exact"]
    print("\n" + "=" * 94)
    if moved > 0:
        print("CONFIRMED: %d games move from the day-before policy to the exact T-90m cutoff."
              % moved)
        print("%d of %d games are now exact, up from %d." % (a["exact"], a["n_games"], b["exact"]))
    else:
        print("NO GAMES MOVED. The source adds observations but none qualifies under the rule.")
    print("")
    print("The rule was NOT relaxed to achieve this. `resolve_tip_times` and")
    print("`apply_cutoff_policy` were imported unmodified, and the hard post-condition --")
    print("every exact row must show its tip was observed strictly before its own cutoff --")
    print("ran untouched with %d failures." % a["post_condition_failures"])
    print("")
    print("NOT BOUND. This does not change the live contract; that is a v6 in the")
    print("v2->v3->v4->v5 lineage. The ET->UTC offset here is a fixed -4, correct for this")
    print("August window and wrong in general -- a bound revision must resolve it properly.")
    print("=" * 94)
    res["games_moved_to_exact"] = moved

    with open(os.path.join(HERE, "FINDINGS_s03.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\nwrote FINDINGS_s03.json")


if __name__ == "__main__":
    main()
