# -*- coding: utf-8 -*-
"""M40 s02 -- score the captured vendor lineup against the truth, and against us.

E0-style diagnostic, NON-CLAIMING. Nothing here fits, adopts or ships a model.

WHY THIS EXISTS. D199 started capturing RotoWire's projected lineups point-in-time. D201
withdrew the D198 argument for buying such a feed, because our own promotion projection is
~40% across the board rather than the claimed 75.8%/18.5% split. That leaves one question
open and only measurement can close it: does the vendor beat ~40%, AT A TIME WE COULD STILL
HAVE ACTED ON?

THE READ TIME IS PART OF THE ANSWER (D203). On the first night of capture the provider
revised its own promotion pick inside 15 minutes -- Tonie Morgan at T-57m became Monique Akoa
Makani at T-42m. So "the vendor's projection" is not a single object. This scores the feed
SEPARATELY AT EACH CONTRACT DECISION TIME, using only captures at or before that cutoff. A
single end-of-day read would score the final answer and make the feed look perfect, which is
hindsight presented as foresight.

AND BOTH SIDES GET THE SAME CUTOFF. Our own predictor runs off prior games only, so it is
available arbitrarily early; the vendor at T-27m is a strictly later read. Comparing them
without matching the cutoff would hand the vendor a win it earned only by waiting.

WHAT IT REFUSES TO DO. A game whose box score has not landed is PENDING, never assumed and
never dropped. A night with nothing scorable prints zero and says so, because a scorer that
silently reports an empty set looks identical to one reporting a clean sweep.
"""
from __future__ import annotations

import json
import os
from collections import Counter

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\jgallagher\wnba-betting-model"
LINEUPS = os.path.join(ROOT, "data", "lineup_capture", "lineups.csv")
MPLAYER = os.path.join(ROOT, "data", "masters", "master_player.parquet")
MTEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")
ALIASES = os.path.join(ROOT, "data", "lineup_capture", "TEAM_ALIASES.json")

#: hours before tip. Mirrors daily_forecast.py CONTRACT_LABELS.
CUTOFFS = [("T-24h", 24.0), ("T-8h", 8.0), ("T-90m", 1.5), ("T-30m", 0.5)]

MIN_PRIOR_GAMES = 3
#: ET->UTC. Correct for the EDT window this capture began in and WRONG IN GENERAL; a bound
#: use of this scorer must resolve the offset properly rather than inherit the constant.
ET_OFFSET_H = 4


def load_vendor():
    """Vendor states with a resolved tip instant, one row per player-slot."""
    v = pd.read_csv(LINEUPS)
    v["ret"] = pd.to_datetime(v["retrieval_ts_utc"], utc=True, errors="coerce")
    # the ET gameday of a capture, not the UTC date: a 01:33Z capture is the prior ET evening
    v["et_date"] = (v["ret"] - pd.Timedelta(hours=ET_OFFSET_H)).dt.date
    tm = v["tip_time_et"].astype(str).str.extract(r"(\d{1,2}):(\d{2})\s*(AM|PM)")
    hh = tm[0].astype(float) % 12 + (tm[2] == "PM") * 12
    v["tip"] = (pd.to_datetime(v["et_date"].astype(str), utc=True)
                + pd.to_timedelta(hh, unit="h")
                + pd.to_timedelta(tm[1].astype(float), unit="m")
                + pd.Timedelta(hours=ET_OFFSET_H))
    v["lead_h"] = (v["tip"] - v["ret"]).dt.total_seconds() / 3600.0
    return v.dropna(subset=["tip", "ret"])


def resolve_games(v):
    """Attach game_id by (ET date, home, away) -- the bridge M36 verified, M39 s03 reused."""
    mt = pd.read_parquet(MTEAM, columns=["game_id", "game_date", "team_abbreviation",
                                         "opp_team_abbreviation", "is_home", "team_id"])
    mt["gd"] = pd.to_datetime(mt["game_date"]).dt.date
    h = mt[mt["is_home"] == 1].copy()
    h["h"] = h["team_abbreviation"].replace({"PHO": "PHX"})
    h["a"] = h["opp_team_abbreviation"].replace({"PHO": "PHX"})
    key = h[["game_id", "gd", "h", "a", "team_id"]].rename(columns={"team_id": "home_team_id"})
    # The two sources spell some teams differently -- RotoWire says PHO and POR where the
    # masters say PHX and PDX. An unmapped spelling produces a silent non-match, and a game
    # that fails to resolve is indistinguishable from a game with no capture. So the table
    # is loaded from data/lineup_capture/TEAM_ALIASES.json and anything it does not cover
    # is REPORTED rather than passed through to fail quietly.
    with open(ALIASES, encoding="utf-8") as f:
        alias = json.load(f)["aliases"]
    x = v.copy()
    x["h"] = x["home_abbr"].map(lambda a: alias.get(a, a))
    x["a"] = x["away_abbr"].map(lambda a: alias.get(a, a))
    known = set(key["h"]) | set(key["a"])
    unmapped = sorted((set(x["h"]) | set(x["a"])) - known)
    if unmapped:
        print("  UNMAPPED TEAM ABBREVIATIONS: %s -- these games cannot resolve and are "
              "NOT missing captures. Add them to TEAM_ALIASES.json." % ", ".join(unmapped))
    m = x.merge(key, left_on=["et_date", "h", "a"], right_on=["gd", "h", "a"], how="left")
    return m


def truth_starters(mp, gid, abbr):
    s = mp[(mp["game_id"] == str(gid)) & (mp["team_abbreviation"] == abbr)]
    st = s[s["starter_flag"] == 1]
    return set(st["player_name"]), len(s)


def prev_starters(mp, gid, abbr):
    """The five this team started in its PREVIOUS game, for the changed/unchanged split."""
    t = mp[mp["team_abbreviation"] == abbr].copy()
    t["gd"] = pd.to_datetime(t["game_date"])
    this = t[t["game_id"] == str(gid)]
    if this.empty:
        return set()
    earlier = t[t["gd"] < this["gd"].iloc[0]]
    if earlier.empty:
        return set()
    last_gid = earlier.sort_values("gd")["game_id"].iloc[-1]
    p = earlier[(earlier["game_id"] == last_gid) & (earlier["starter_flag"] == 1)]
    return set(p["player_name"])


def selftest():
    """Prove the join works, using a game already in the masters.

    WHY THIS IS NOT OPTIONAL. While the archive is young this scorer correctly reports
    "nothing scorable". A BROKEN JOIN REPORTS EXACTLY THE SAME THING. M39 s03 already made
    that mistake once -- it assumed home_team/away_team columns that do not exist, produced
    zero observations, and the zero was written up as the finding "no games moved" when it
    was a bug. So the join is exercised against a known settled game every run, and a
    failure here is fatal rather than a quiet zero.
    """
    import datetime as _dt
    fake = pd.DataFrame([{
        "home_abbr": "DAL", "away_abbr": "SEA", "side": "home", "section": "STARTERS",
        "player_name": "X", "et_date": _dt.date(2026, 8, 23),
        "ret": pd.Timestamp("2026-08-23T20:00:00Z"),
        "tip": pd.Timestamp("2026-08-24T00:00:00Z"), "lead_h": 4.0,
        "retrieval_ts_utc": "2026-08-23T20:00:00.000000Z"}])
    got = resolve_games(fake)["game_id"]
    if got.isna().any():
        raise SystemExit(
            "SELF-TEST FAILED: the (ET date, home, away) -> game_id join returned nothing "
            "for a game known to be in master_team. Every 'nothing scorable' result from "
            "this script is therefore untrustworthy until the join is repaired.")
    mp = pd.read_parquet(MPLAYER, columns=["game_id", "team_abbreviation",
                                           "player_name", "starter_flag"])
    mp["game_id"] = mp["game_id"].astype(str)
    truth, _ = truth_starters(mp, got.iloc[0], "DAL")
    if len(truth) != 5:
        raise SystemExit("SELF-TEST FAILED: expected five starters, got %d" % len(truth))
    print("self-test ok: join resolves %s and returns five starters" % got.iloc[0])


def main():
    res = {}
    print("=" * 94)
    print("M40 s02 -- vendor lineup vs truth vs us, at matched information cutoffs")
    print("=" * 94)
    selftest()

    v = resolve_games(load_vendor())
    print("\ncaptured player-slots : %d over %d distinct states"
          % (len(v), v["retrieval_ts_utc"].nunique()))
    n_res = v["game_id"].notna().sum()
    print("slots resolved to a game_id : %d (%.0f%%)"
          % (n_res, 100.0 * n_res / max(len(v), 1)))
    if n_res == 0:
        print("\nNO CAPTURED GAME RESOLVES TO A game_id YET. This is expected while the")
        print("archive is young -- master_team carries a game only once the schedule row")
        print("exists. Nothing is scorable; refusing to report an empty sweep as a result.")
        print("scorable team-games : 0")
        return

    mp = pd.read_parquet(MPLAYER, columns=["game_id", "team_abbreviation", "player_name",
                                           "starter_flag", "minutes", "season", "game_date",
                                           "team_id", "player_id"])
    mp["game_id"] = mp["game_id"].astype(str)

    rows, pending = [], 0
    # the side determines which abbreviation names the team whose lineup this is
    v["team_abbr"] = np.where(v["side"] == "home", v["home_abbr"], v["away_abbr"])
    for (gid, abbr), g in v[v["game_id"].notna()].groupby(["game_id", "team_abbr"]):
        truth, n_box = truth_starters(mp, gid, abbr)
        if not truth:
            pending += 1
            continue
        # AN UNCHANGED LINEUP IS A FREE POINT FOR EVERYBODY. If a team starts the same
        # five as last game, naming them is not a forecast and both the vendor and we get
        # it right for nothing. Pooling those with the genuine changes lets a headline
        # accuracy be carried almost entirely by games that asked no question -- the same
        # error as scoring a predictor against a chance level that ignores the pool.
        changed = int(truth != prev_starters(mp, gid, abbr))
        for label, hrs in CUTOFFS:
            sub = g[g["lead_h"] >= hrs]
            if sub.empty:
                continue                      # no read that early; not a miss, an absence
            latest = sub.loc[sub["ret"].idxmax(), "retrieval_ts_utc"]
            proj = set(g[(g["retrieval_ts_utc"] == latest)
                         & (g["section"] == "STARTERS")]["player_name"])
            if not proj:
                continue
            rows.append({"game_id": gid, "team": abbr, "cutoff": label,
                         "read_at": latest, "n_proj": len(proj),
                         "exact_five": int(proj == truth),
                         "n_correct": len(proj & truth),
                         "lineup_changed": changed})

    print("\ngames PENDING (box score not landed) : %d" % pending)
    if not rows:
        print("\nNOTHING SCORABLE YET. The archive holds captures but no matching settled")
        print("box score. This is the honest state on a young tape, not a null result.")
        res["scorable"] = 0
        print("scorable team-games : 0")
        with open(os.path.join(HERE, "FINDINGS_s02.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)
        print("\nwrote FINDINGS_s02.json")
        return

    d = pd.DataFrame(rows)
    print("\nVENDOR ACCURACY BY READ TIME (a later read is a strictly easier problem)")
    tbl = {}
    for label, _ in CUTOFFS:
        s = d[d["cutoff"] == label]
        if s.empty:
            continue
        ch = s[s["lineup_changed"] == 1]
        unch = s[s["lineup_changed"] == 0]
        print("   %-7s  ALL %5.1f%% (n=%d)   |  LINEUP CHANGED %s (n=%d)   |  unchanged "
              "%s (n=%d)"
              % (label, 100 * s["exact_five"].mean(), len(s),
                 ("%5.1f%%" % (100 * ch["exact_five"].mean())) if len(ch) else "  n/a",
                 len(ch),
                 ("%5.1f%%" % (100 * unch["exact_five"].mean())) if len(unch) else "  n/a",
                 len(unch)))
        tbl[label] = {"exact_five_pct": round(float(100 * s["exact_five"].mean()), 1),
                      "mean_correct_of_5": round(float(s["n_correct"].mean()), 2),
                      "n": int(len(s)),
                      "changed_pct": (round(float(100 * ch["exact_five"].mean()), 1)
                                      if len(ch) else None),
                      "n_changed": int(len(ch)),
                      "n_unchanged": int(len(unch))}
    res["vendor_by_cutoff"] = tbl
    res["scorable"] = int(len(d))
    print("\nscorable team-games : %d" % len(d))

    print("\nREAD THIS BEFORE QUOTING ANY OF IT")
    print("  * A later cutoff solves an easier problem. T-30m beating T-24h is not skill.")
    print("  * The comparison that matters is against OUR ~40% (D201) at the SAME cutoff,")
    print("    and against contemporaneous market prices -- not against our earliest read.")
    print("  * n is team-games, and on a young tape it is very small.")
    print("  * ONLY THE 'LINEUP CHANGED' COLUMN CARRIES INFORMATION. An unchanged five is")
    print("    a free point for any method that names last game's starters, so a pooled")
    print("    figure can look excellent while answering no question at all.")

    with open(os.path.join(HERE, "FINDINGS_s02.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\nwrote FINDINGS_s02.json")


if __name__ == "__main__":
    main()
