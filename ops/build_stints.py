# -*- coding: utf-8 -*-
"""Reconstruct five-player stints from play-by-play -- CURRENTLY FAILS ON 994 OF 996 GAMES.

READ THIS FIRST. As written, this reconstructs only 2 of 996 games and discards the rest. That
is NOT a bug in the walk: SUBSTITUTIONS AT PERIOD BOUNDARIES ARE NOT RECORDED AS SUB EVENTS in
this play-by-play. Player 1630446 is flagged a starter in the box score, yet her first
play-by-play appearance is ENTERING in period 2 -- she left the floor between quarters with no
event to say so. Any walk that assumes every lineup change emits an event will desynchronise
within a quarter or two.

The file is kept because the failure is worth inheriting: a successor reaching for stints will
otherwise rebuild this and hit the same wall. Making it work requires inferring each PERIOD'S
STARTING LINEUP separately -- commonly from which players record events early in that period --
and that was not attempted.

WHAT IT DOES GET RIGHT is refusing. Games whose lineup ever leaves five players are DISCARDED
AND COUNTED rather than repaired, because a drifted lineup produces co-play numbers that look
perfectly usable and are wrong. If you fix the period-boundary problem, keep that guard.

The question this was built to answer -- who plays when she does not -- was answered WITHOUT
stints in the end, from game-level minutes correlation (D195: 24.7%, 2.23x chance). So nothing
downstream is blocked on repairing this.


WHY. D194 tested the obvious rotation hypothesis -- that a player's usual in-game substitute
absorbs her minutes when she misses a whole game -- and it failed at 1.23x chance, because her
absorber is typically her FOURTH most common substitute, not her first. Who spells you for a
shift is not who replaces you for a game.

That leaves one construction this data still supports, and it asks a different question:
not "who comes in for her" but "WHO PLAYS WHEN SHE DOES NOT". Two players who alternate --
rarely on the floor together, each covering the same slot -- are substitutes for one another in
a structural sense that a single sub event does not capture. That is COMPLEMENTARITY, and it
needs stints rather than sub events.

HOW A STINT IS BUILT, and where it can go wrong:
  * the five starters come from the box score's starter flag, not from the play-by-play;
  * events are walked in game order, and each substitution swaps one player for another;
  * elapsed seconds between events are attributed to whoever is on the floor.

THE VALIDATION MATTERS MORE THAN THE RECONSTRUCTION. A lineup that drifts off five players
means the walk has desynchronised, and every downstream number would be quietly wrong. So the
lineup size is asserted at every event and games that ever break are DISCARDED AND COUNTED
rather than repaired -- a partially-correct stint is worse than a missing one, because it looks
usable.
"""
from __future__ import annotations

import glob
import json
import os
import re

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PBP = os.path.join(ROOT, "data", "playbyplay")
MPLAYER = os.path.join(ROOT, "data", "masters", "master_player.parquet")
OUT = os.path.join(ROOT, "data", "derived", "coplay.parquet")

SUB = 8                      # EVENTMSGTYPE for a substitution
PERIOD_SECONDS = 600         # WNBA quarters are 10 minutes


def clock_to_elapsed(period, pcstring):
    """Seconds elapsed in the GAME at this event."""
    try:
        m, s = str(pcstring).split(":")
        remaining = int(m) * 60 + int(s)
    except (ValueError, AttributeError):
        return np.nan
    p = int(period)
    if p <= 4:
        return (p - 1) * PERIOD_SECONDS + (PERIOD_SECONDS - remaining)
    ot = p - 4                                  # overtimes are 5 minutes
    return 4 * PERIOD_SECONDS + (ot - 1) * 300 + (300 - remaining)


def game_coplay(pbp, starters_by_team):
    """Seconds each PAIR of teammates spent on the floor together, for one game.

    Returns None if the lineup ever leaves five players -- see the module docstring.
    """
    pbp = pbp.copy()
    pbp["t"] = [clock_to_elapsed(p, c) for p, c in zip(pbp["PERIOD"], pbp["PCTIMESTRING"])]
    pbp = pbp.dropna(subset=["t"]).sort_values(["t", "EVENTNUM"])

    on = {tid: set(s) for tid, s in starters_by_team.items()}
    if any(len(v) != 5 for v in on.values()):
        return None                                   # box score did not give five starters
    last_t = 0.0
    pair = {}
    for _, e in pbp.iterrows():
        t = float(e["t"])
        if t > last_t:
            for tid, lineup in on.items():
                players = sorted(lineup)
                for i in range(len(players)):
                    for j in range(i + 1, len(players)):
                        k = (players[i], players[j])
                        pair[k] = pair.get(k, 0.0) + (t - last_t)
            last_t = t
        if int(e["EVENTMSGTYPE"]) != SUB:
            continue
        tid = e["PLAYER1_TEAM_ID"]
        out_p, in_p = e["PLAYER1_ID"], e["PLAYER2_ID"]
        if pd.isna(tid) or pd.isna(out_p) or pd.isna(in_p):
            continue
        tid, out_p, in_p = int(tid), int(out_p), int(in_p)
        if tid not in on or out_p not in on[tid]:
            return None                               # desynchronised: refuse the game
        on[tid].discard(out_p)
        on[tid].add(in_p)
        if len(on[tid]) != 5:
            return None
    return pair


def main():
    mp = pd.read_parquet(MPLAYER)
    mp["game_id"] = mp["game_id"].astype(str)
    st = mp[mp["starter_flag"] == 1]
    starters = {g: {int(t): grp["player_id"].astype(int).tolist()
                    for t, grp in s.groupby("team_id")}
                for g, s in st.groupby("game_id")}
    played = {(str(g), int(p)) for g, p in zip(mp["game_id"], mp["player_id"])}

    files = sorted(glob.glob(os.path.join(PBP, "pbp_*.parquet")))
    rows, ok, bad = [], 0, 0
    for f in files:
        gid = re.search(r"pbp_(\d+)\.parquet", os.path.basename(f))
        if not gid:
            continue
        gid = gid.group(1)
        if gid not in starters:
            bad += 1
            continue
        try:
            d = pd.read_parquet(f, columns=["EVENTNUM", "EVENTMSGTYPE", "PERIOD",
                                            "PCTIMESTRING", "PLAYER1_ID", "PLAYER2_ID",
                                            "PLAYER1_TEAM_ID"])
        except Exception:                              # noqa: BLE001
            bad += 1
            continue
        pair = game_coplay(d, starters[gid])
        if pair is None:
            bad += 1
            continue
        ok += 1
        for (a, b), sec in pair.items():
            rows.append((gid, a, b, sec))

    print("games reconstructed : %d" % ok)
    print("games DISCARDED     : %d (lineup left five players, or no starters recorded)" % bad)
    if not ok:
        raise SystemExit("no games reconstructed; refusing to write an empty co-play table")

    cp = pd.DataFrame(rows, columns=["game_id", "a", "b", "seconds"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cp.to_parquet(OUT, index=False)
    print("pair-game rows      : %d" % len(cp))
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
