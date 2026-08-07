r"""S33R / findings A3, B2, B3 - strata, row bases, SC12 clip incidence.

ROOT: C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program
(the worktree's data/masters/master_team.parquet matches the S33 pin ad79ce5c...8528;
the main working tree's copy has drifted and is NOT admissible.)

Produces A3_B_STRATA_RECEIPT.json.  Census counts only - no fit, no performance number.
"""
import hashlib
import json
import os

import pandas as pd

WORKTREE = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
DATA = os.path.join(WORKTREE, "data")
HERE = os.path.dirname(os.path.abspath(__file__))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


mt_path = os.path.join(DATA, "masters", "master_team.parquet")
mt = pd.read_parquet(mt_path)
out = {"measurement": "A3_B_STRATA", "root": WORKTREE,
       "reads": {"data/masters/master_team.parquet": sha256(mt_path)}}

home = mt[mt.is_home == 1]
first_date = home[home.season == 2021].game_date.min()
uni_ids = set(home[home.game_date > first_date].game_id)
full_ids = set(home.game_id)

TEST_SEASONS = [2022, 2023, 2024, 2025, 2026]


def prior_counts(row_base_ids, same_season=True):
    """n(team, game) = count of that team's completed games in row_base_ids that are
    strictly earlier by (game_date, game_id) - same season only when same_season."""
    base = mt[mt.game_id.isin(row_base_ids)][
        ["game_id", "team_id", "season", "game_date"]].copy()
    base = base.sort_values(["team_id", "game_date", "game_id"])
    n = {}
    for tid, grp in base.groupby("team_id"):
        seen_all, seen_season = 0, {}
        for _, r in grp.iterrows():
            if same_season:
                n[(tid, r.game_id)] = seen_season.get(r.season, 0)
                seen_season[r.season] = seen_season.get(r.season, 0) + 1
            else:
                n[(tid, r.game_id)] = seen_all
                seen_all += 1
    return n


games = mt[mt.game_id.isin(full_ids)][
    ["game_id", "team_id", "is_home", "season", "game_date"]]
by_game = {}
for gid, grp in games.groupby("game_id"):
    h = grp[grp.is_home == 1].iloc[0]
    a = grp[grp.is_home != 1].iloc[0]
    by_game[gid] = (h.team_id, a.team_id, int(h.season))


def stratum(n_map, ids, reducer, thresh, strict=False):
    hit = []
    for g in ids:
        th, ta, _s = by_game[g]
        v = reducer(n_map[(th, g)], n_map[(ta, g)])
        if (v < thresh) if strict else (v <= thresh):
            hit.append(g)
    return hit


def census(ids):
    return {"pooled": len(ids),
            "per_test_season": {str(s): sum(1 for g in ids if by_game[g][2] == s)
                                for s in TEST_SEASONS},
            "in_2021_training_only": sum(1 for g in ids if by_game[g][2] == 2021)}


# ------------------------------------------------- A3: the SC01 stratum, both readings
n_uni = prior_counts(uni_ids)          # strictly-prior base = the 1,491 universe
n_full = prior_counts(full_ids)        # strictly-prior base = the 1,495 full schedule

res = {}
for base_name, nmap in (("universe_1491", n_uni), ("full_schedule_1495", n_full)):
    res[base_name] = {
        "SC01_max_le_12_BOTH_TEAMS_EARLY": census(
            stratum(nmap, uni_ids, max, 12)),
        "SC01_min_le_12_AT_LEAST_ONE_TEAM_EARLY": census(
            stratum(nmap, uni_ids, min, 12)),
        "SC02_min_le_5": census(stratum(nmap, uni_ids, min, 5)),
        "SC02_max_le_5": census(stratum(nmap, uni_ids, max, 5)),
        "SC03_min_lt_10": census(stratum(nmap, uni_ids, min, 10, strict=True)),
        "SC03_max_lt_10": census(stratum(nmap, uni_ids, max, 10, strict=True)),
    }
out["A3_strata"] = res
out["A3_note"] = ("'BOTH teams <= 12' is max(n_H, n_A) <= 12. The S33 card's predicate text "
                  "says BOTH; its number (516) is the min reading, which means AT LEAST ONE "
                  "team early. J12's reconciliation ('each team <= 12 is exactly min <= 12') "
                  "is false.")

# --------------------------------------------- B2: do the two row bases differ at all?
diff_games, diff_detail = [], []
for g in uni_ids:
    th, ta, s = by_game[g]
    if n_uni[(th, g)] != n_full[(th, g)] or n_uni[(ta, g)] != n_full[(ta, g)]:
        diff_games.append(g)
        diff_detail.append({"game_id": g, "season": s,
                            "home_n_universe": n_uni[(th, g)], "home_n_full": n_full[(th, g)],
                            "away_n_universe": n_uni[(ta, g)], "away_n_full": n_full[(ta, g)]})
out["B2_row_base_divergence"] = {
    "excluded_from_universe": sorted(full_ids - uni_ids),
    "universe_clusters_whose_same_season_prior_counts_DIFFER_between_bases":
        census(diff_games),
    "n_affected": len(diff_games),
    "sample_detail": sorted(diff_detail, key=lambda r: r["game_id"])[:12],
}
# does the base choice move any carded stratum count?
out["B2_effect_on_carded_strata"] = {
    k: {"universe_1491": res["universe_1491"][k]["pooled"],
        "full_schedule_1495": res["full_schedule_1495"][k]["pooled"]}
    for k in res["universe_1491"]}

# ------------------------------------------------------- B3: SC12 clip incidence
# The kill reads "< 8% of prior-game inputs actually clipped at the frozen +/-15 cap".
# The inputs to SC12's EWMA are each side's strictly-prior own settled margins, any
# season.  Incidence = share of those inputs with |margin| > 15.
tm = mt[mt.game_id.isin(uni_ids)].copy()
tm["own_margin"] = tm.pts - tm.opp_pts
clipped_rows = int((tm.own_margin.abs() > 15).sum())
out["B3_sc12_clip_incidence"] = {
    "definition": "share of team-game margin observations (the EWMA inputs) with |margin| > 15",
    "team_game_rows_in_universe": int(tm.shape[0]),
    "rows_exceeding_cap": clipped_rows,
    "share": round(clipped_rows / tm.shape[0], 6),
    "game_level_share_cited_by_S33": {
        "games_with_abs_settled_margin_gt_15": int(
            (tm[tm.is_home == 1].own_margin.abs() > 15).sum()),
        "universe_clusters": len(uni_ids)},
    "per_season_share": {str(s): round(float((grp.own_margin.abs() > 15).mean()), 6)
                         for s, grp in tm.groupby("season")},
    "kill_as_carded": "< 8% clipped => inert => kill",
    "can_the_kill_fire": bool(clipped_rows / tm.shape[0] < 0.08),
    "minimum_per_season_share": round(float(min(
        (grp.own_margin.abs() > 15).mean() for _s, grp in tm.groupby("season"))), 6),
}

# --------- B3b: what a non-vacuous inertness kill would have to measure instead ------
# The transform's actual bite is the size of w = EWMA(clipped) - EWMA(raw), not the
# clip incidence.  Measure the realised |w_H - w_A| distribution the card can pin against.
tm = tm.sort_values(["team_id", "game_date", "game_id"])
alpha = 2.0 / 11.0
w_by = {}
for tid, grp in tm.groupby("team_id"):
    e_raw = e_win = None
    for _, r in grp.iterrows():
        w_by[(tid, r.game_id)] = (0.0 if e_raw is None else e_win - e_raw)
        m = float(r.own_margin)
        mc = max(-15.0, min(15.0, m))
        e_raw = m if e_raw is None else alpha * m + (1 - alpha) * e_raw
        e_win = mc if e_win is None else alpha * mc + (1 - alpha) * e_win
diffs = []
for g in uni_ids:
    th, ta, _s = by_game[g]
    diffs.append(abs(w_by[(th, g)] - w_by[(ta, g)]))
diffs.sort()
out["B3b_realised_transform_bite"] = {
    "statistic": "|w_H - w_A| where w = EWMA(clip(margin,+/-15)) - EWMA(margin), span 10",
    "n_clusters": len(diffs),
    "median": round(diffs[len(diffs) // 2], 4),
    "p90": round(diffs[int(0.9 * len(diffs))], 4),
    "p99": round(diffs[int(0.99 * len(diffs))], 4),
    "max": round(diffs[-1], 4),
    "share_below_0_25_points": round(sum(1 for d in diffs if d < 0.25) / len(diffs), 4),
    "share_below_0_50_points": round(sum(1 for d in diffs if d < 0.50) / len(diffs), 4),
}

with open(os.path.join(HERE, "A3_B_STRATA_RECEIPT.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out, indent=1))
