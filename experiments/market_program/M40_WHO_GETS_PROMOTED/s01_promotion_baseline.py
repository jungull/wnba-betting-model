# -*- coding: utf-8 -*-
"""M40 s01 -- when a starter sits, who gets promoted, and how well do WE predict it?

E0-style diagnostic, NON-CLAIMING. Nothing here fits, adopts or ships a model.

WHY THIS EXISTS. D198 recorded that our own promotion projection is 75.8% where the
absent player has a pair history on this team this season (58% of cases) and 18.5% where
she does not (42%). Those two numbers decide whether a third-party lineup feed is worth
anything -- a vendor can only pay us on the second group -- and THEY WERE NOT BACKED BY A
SCRIPT. A number in the ledger that nobody can re-run is a number nobody can check, so
this rebuilds them from the masters and then attacks the weak half.

WHAT AN EVENT IS. Within a team-season, compare consecutive games. A player who started
the previous game and does not play in this one is ABSENT; a player who starts this game
and did not start the previous one is PROMOTED. The clean case is EXACTLY ONE of each, so
the promotion is unambiguously attributable to that absence. Multi-absence games are
counted and dropped rather than guessed at.

EVERY PREDICTOR IS WALK-FORWARD. Each event is predicted using only games strictly before
it. The obvious trap here is the one M39 s01 fell into: choosing the answer after seeing
it. Naming the most common promotee across an entire team-season and then scoring it on
that same season would be circular and would flatter every method equally.

CHANCE IS NOT 1/ROSTER. The starting five is always 2F/2G/1C, so a promotion is not drawn
from the whole bench -- it is drawn from players who can fill the vacated slot. Chance is
therefore reported against the candidate pool actually used, and a position-restricted
predictor is scored against a position-restricted chance level, or it would look clever
merely for exploiting a constraint that every method could exploit.
"""
from __future__ import annotations

import json
import os
from collections import Counter

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\jgallagher\wnba-betting-model"
MPLAYER = os.path.join(ROOT, "data", "masters", "master_player.parquet")

MIN_PRIOR_GAMES = 3


def load():
    mp = pd.read_parquet(MPLAYER, columns=[
        "game_id", "season", "game_date", "team_id", "player_id", "player_name",
        "position", "starter_flag", "minutes"])
    mp["gd"] = pd.to_datetime(mp["game_date"])
    mp["min"] = pd.to_numeric(mp["minutes"], errors="coerce").fillna(0.0)
    mp["starter"] = mp["starter_flag"] == 1
    mp["played"] = mp["min"] > 0
    return mp.sort_values(["team_id", "season", "gd", "game_id"])


def build_events(mp):
    """One row per clean single-absence, single-promotion transition."""
    events, multi = [], 0
    for (tid, season), g in mp.groupby(["team_id", "season"], sort=False):
        games = list(g.groupby("game_id", sort=False))
        order = sorted(range(len(games)), key=lambda i: games[i][1]["gd"].iloc[0])
        for a, b in zip(order, order[1:]):
            prev, cur = games[a][1], games[b][1]
            prev_start = set(prev.loc[prev["starter"], "player_id"])
            cur_start = set(cur.loc[cur["starter"], "player_id"])
            played_now = set(cur.loc[cur["played"], "player_id"])
            absent = [p for p in prev_start if p not in played_now]
            promoted = list(cur_start - prev_start)
            if len(absent) != 1 or len(promoted) != 1:
                if absent:
                    multi += 1
                continue
            pos = prev.loc[prev["player_id"] == absent[0], "position"]
            newpos = cur.loc[cur["player_id"] == promoted[0], "position"]
            # candidates: everyone who played this game and was not already a starter
            cand = sorted(played_now - (prev_start - set(absent)))
            events.append({
                "game_id": games[b][0], "gd": cur["gd"].iloc[0], "season": season,
                "team_id": tid, "absent": absent[0], "promoted": promoted[0],
                "absent_pos": (pos.iloc[0] if len(pos) else ""),
                "promoted_pos": (newpos.iloc[0] if len(newpos) else ""),
                "candidates": cand, "n_cand": len(cand)})
    return pd.DataFrame(events).sort_values("gd").reset_index(drop=True), multi


def main():
    res = {}
    print("=" * 94)
    print("M40 s01 -- who gets promoted when a starter sits, and can we call it?")
    print("=" * 94)

    mp = load()
    ev, multi = build_events(mp)
    print("\nclean single-absence promotions : %d" % len(ev))
    print("dropped (multi-absence/ambiguous): %d" % multi)
    print("candidate pool per event         : median %.0f" % ev["n_cand"].median())
    res["n_events"] = int(len(ev))
    res["n_dropped_multi"] = int(multi)

    same = (ev["absent_pos"] == ev["promoted_pos"]).mean()
    print("\n1. DOES THE PROMOTED PLAYER TAKE THE VACATED POSITION SLOT?")
    print("   same listed position: %.1f%% of events" % (100 * same))
    print("   (the starting five is always 2F/2G/1C, so this is close to structural --")
    print("    it constrains WHO can be promoted, and any predictor may use it.)")
    res["same_position_pct"] = round(float(100 * same), 1)

    # ---- trailing minutes, walk-forward -------------------------------------
    mp = mp.copy()
    mp["trail_min"] = (mp.groupby(["team_id", "season", "player_id"])["min"]
                         .transform(lambda s: s.shift(1).expanding(
                             min_periods=MIN_PRIOR_GAMES).mean()))
    trail = {(r.game_id, r.player_id): r.trail_min
             for r in mp.itertuples() if not pd.isna(r.trail_min)}

    # A player's usual position, learned ONLY from starts strictly before the event.
    # Recomputing this inside the loop would be O(n^2); instead walk the starts once
    # in date order and keep a running tally, which is the same information.
    starts = mp[mp["starter"] & (mp["position"].fillna("") != "")].sort_values("gd")
    start_rows = list(zip(starts["gd"], starts["player_id"], starts["position"]))

    hits = {k: [0, 0] for k in ("pair", "team_freq", "top_minutes",
                                "pos_top_minutes", "cross_season")}
    chance_open, chance_pos = [], []
    cover_open, cover_pos = [], []
    pair_hist, team_hist, cross_hist = {}, {}, {}
    pos_tally = {}
    si = 0
    rows = []
    for e in ev.itertuples():
        # advance the position tally to (but not including) this event's date
        while si < len(start_rows) and start_rows[si][0] < e.gd:
            _, pid, p = start_rows[si]
            pos_tally.setdefault(pid, Counter())[p] += 1
            si += 1

        key = (e.season, e.team_id, e.absent)
        xkey = (e.team_id, e.absent)
        cands = e.candidates
        if not cands:
            continue
        truth = e.promoted

        def usual(pid):
            c = pos_tally.get(pid)
            return c.most_common(1)[0][0] if c else ""

        # A candidate with NO prior start has no known position. Excluding her is the
        # bug this line exists to avoid: the promoted player is very often someone who
        # has never started before, so a filter built from prior starts throws away the
        # true answer and then looks precise on the small pool that remains. Unknown
        # position is therefore ELIGIBLE, and pool coverage is reported below so the
        # filter cannot flatter itself by shrinking the pool past the answer.
        pos_c = [c for c in cands if usual(c) in (e.absent_pos, "")] or cands

        preds = {}
        if key in pair_hist:
            preds["pair"] = Counter(pair_hist[key]).most_common(1)[0][0]
        if xkey in cross_hist:
            preds["cross_season"] = Counter(cross_hist[xkey]).most_common(1)[0][0]
        if (e.season, e.team_id) in team_hist:
            preds["team_freq"] = Counter(
                team_hist[(e.season, e.team_id)]).most_common(1)[0][0]
        preds["top_minutes"] = max(
            (trail.get((e.game_id, c), -1.0), c) for c in cands)[1]
        preds["pos_top_minutes"] = max(
            (trail.get((e.game_id, c), -1.0), c) for c in pos_c)[1]

        for k, p in preds.items():
            hits[k][0] += int(p == truth)
            hits[k][1] += 1
        # Chance = the accuracy a RANDOM PICK INSIDE THE POOL would actually score, which
        # is zero when the pool does not contain the answer. Scoring 1/len(pool)
        # unconditionally rewards a filter for shrinking the pool even when it shrinks
        # past the truth, and that is exactly how the first version of the
        # position-restricted predictor came to sit below its own chance level.
        chance_open.append(1.0 / len(cands) if truth in cands else 0.0)
        chance_pos.append(1.0 / len(pos_c) if truth in pos_c else 0.0)
        cover_open.append(int(truth in cands))
        cover_pos.append(int(truth in pos_c))
        rows.append({"gd": e.gd, "season": e.season, "has_pair": key in pair_hist,
                     "n_cand": len(cands), "n_pos_cand": len(pos_c),
                     **{("hit_" + k): int(v == truth) for k, v in preds.items()},
                     **{("had_" + k): 1 for k in preds}})

        pair_hist.setdefault(key, []).append(truth)
        team_hist.setdefault((e.season, e.team_id), []).append(truth)
        cross_hist.setdefault(xkey, []).append(truth)

    d = pd.DataFrame(rows)
    for c in d.columns:
        if c.startswith("had_") or c.startswith("hit_"):
            d[c] = d[c].fillna(0)
    res["chance_open"] = round(float(np.mean(chance_open)), 4)
    res["chance_pos_restricted"] = round(float(np.mean(chance_pos)), 4)
    res["pool_coverage_open_pct"] = round(float(100 * np.mean(cover_open)), 1)
    res["pool_coverage_pos_pct"] = round(float(100 * np.mean(cover_pos)), 1)
    print("\nPOOL COVERAGE -- is the answer even available to be picked?")
    print("   open candidate pool        : %.1f%% (true by construction)"
          % (100 * np.mean(cover_open)))
    print("   position-restricted pool   : %.1f%%  <- a filter cannot beat its coverage"
          % (100 * np.mean(cover_pos)))

    print("\n2. THE SPLIT D198 RESTS ON (rebuilt from the masters)")
    rep, first = d[d["has_pair"]], d[~d["has_pair"]]
    print("   events WITH a same-season pair history : %d (%.1f%%)"
          % (len(rep), 100 * len(rep) / len(d)))
    print("   events on a FIRST-TIME absence         : %d (%.1f%%)"
          % (len(first), 100 * len(first) / len(d)))
    pair_acc = rep["hit_pair"].mean() if len(rep) else float("nan")
    print("   pair-history predictor on the repeat half : %.1f%%" % (100 * pair_acc))

    # THE DECISIVE COMPARISON, and the one the ledger never made. Pair history is only
    # worth its complexity if it beats the dumbest available rule ON ITS OWN GROUND --
    # the repeat half, where it has the evidence it was built to exploit. Scoring it
    # only where it is available, against nothing, cannot show that.
    print("\n   HEAD TO HEAD on the same events (walk-forward):")
    print("      %-22s %-14s %-14s" % ("", "repeat half", "first-time half"))
    for k, lbl in (("pair", "pair history"), ("top_minutes", "top bench minutes"),
                   ("pos_top_minutes", "position-filtered")):
        a = (100 * rep["hit_" + k].mean()) if len(rep) else float("nan")
        b = (100 * first["hit_" + k].mean()) if len(first) else float("nan")
        avail = "" if k != "pair" else "   (undefined on first-time by definition)"
        print("      %-22s %11.1f%% %11.1f%%%s"
              % (lbl, a, b if k != "pair" else float("nan"), avail))
    res["repeat_half"] = {k: round(float(100 * rep["hit_" + k].mean()), 1)
                          for k in ("pair", "top_minutes", "pos_top_minutes")
                          if len(rep)}

    # n=86 is small enough that a 7-point gap may be noise. PAIRED bootstrap -- both
    # predictors are resampled on the SAME events, because they are correlated and
    # comparing two independent intervals would overstate the uncertainty of the gap.
    if len(rep) > 10:
        rng = np.random.default_rng(20260824)
        a = rep["hit_pair"].to_numpy(dtype=float)
        b = rep["hit_top_minutes"].to_numpy(dtype=float)
        idx = rng.integers(0, len(a), size=(4000, len(a)))
        diff = (a[idx].mean(axis=1) - b[idx].mean(axis=1)) * 100
        lo, hi = np.percentile(diff, [2.5, 97.5])
        share_pos = float((diff > 0).mean())
        print("\n   Is pair history really better than top-minutes on the repeat half?")
        print("      gap %+.1f pp, 95%% paired bootstrap [%+.1f, %+.1f], "
              "positive in %.0f%% of resamples (n=%d)"
              % (100 * (a.mean() - b.mean()), lo, hi, 100 * share_pos, len(a)))
        if lo <= 0 <= hi:
            print("      THE INTERVAL SPANS ZERO -- on this evidence the extra machinery")
            print("      is NOT demonstrably better than 'pick the busiest bench player'.")
        res["repeat_gap_pp"] = {"point": round(float(100 * (a.mean() - b.mean())), 1),
                                "lo": round(float(lo), 1), "hi": round(float(hi), 1),
                                "n": int(len(a))}
    res["share_with_pair_history"] = round(float(100 * len(rep) / len(d)), 1)
    res["pair_accuracy_repeat"] = round(float(100 * pair_acc), 1)

    print("\n3. WHAT CAN CARRY THE FIRST-TIME HALF? (%d events, chance %.1f%% open / "
          "%.1f%% position-restricted)"
          % (len(first), 100 * np.mean(chance_open), 100 * np.mean(chance_pos)))
    tbl = {}
    for k in ("team_freq", "cross_season", "top_minutes", "pos_top_minutes"):
        sub = first[first["had_" + k] == 1] if ("had_" + k) in first else first.iloc[:0]
        if not len(sub):
            continue
        acc = sub["hit_" + k].mean()
        print("   %-16s %5.1f%%   (available on %d of %d first-time events)"
              % (k, 100 * acc, len(sub), len(first)))
        tbl[k] = {"accuracy_pct": round(float(100 * acc), 1), "n": int(len(sub))}
    res["first_time_predictors"] = tbl

    print("\n4. PER SEASON (walk-forward; 2025/2026 are the confirmation holdout)")
    for s, g in d.groupby("season"):
        r, fh = g[g["has_pair"]], g[~g["has_pair"]]
        print("   %d  n=%-4d pair-half %5.1f%%   first-time pos_top_minutes %5.1f%%"
              % (s, len(g),
                 100 * r["hit_pair"].mean() if len(r) else float("nan"),
                 100 * fh["hit_pos_top_minutes"].mean() if len(fh) else float("nan")))

    with open(os.path.join(HERE, "FINDINGS_s01.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\nwrote FINDINGS_s01.json")


if __name__ == "__main__":
    main()
