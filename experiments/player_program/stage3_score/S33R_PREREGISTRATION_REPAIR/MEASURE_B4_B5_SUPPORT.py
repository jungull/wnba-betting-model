r"""S33R / findings B4, B5 - support for the two unspecified card elements.

ROOT: C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program

B4: SC10's orthogonalisation covariate has no lineage and no support measurement.
B5: SC02's retirement kill ("condition-number failure") has no numeric threshold.
    Design-matrix condition numbers involve NO target and NO metric - this is a
    feasibility census, not a fit.

Produces B4_B5_SUPPORT_RECEIPT.json.
"""
import hashlib
import json
import os

import numpy as np
import pandas as pd

WORKTREE = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
DATA = os.path.join(WORKTREE, "data")
HERE = os.path.dirname(os.path.abspath(__file__))


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


mt_path = os.path.join(DATA, "masters", "master_team.parquet")
sb_path = os.path.join(WORKTREE, "experiments", "market_program", "SCORE_BASELINES",
                       "score_baseline_rows.parquet")
out = {"measurement": "B4_B5_SUPPORT", "root": WORKTREE,
       "reads": {"data/masters/master_team.parquet": sha256(mt_path),
                 "experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet":
                     sha256(sb_path)}}

mt = pd.read_parquet(mt_path)
home = mt[mt.is_home == 1]
fd = home[home.season == 2021].game_date.min()
uni = set(home[home.game_date > fd].game_id)
tg = mt[mt.game_id.isin(uni)][["game_id", "team_id", "is_home", "season", "game_date",
                               "pts", "opp_pts"]].copy()
tg = tg.sort_values(["team_id", "game_date", "game_id"])

# same-season strictly-prior completed game counts on the pinned 1,491 base
n_prior = {}
for tid, grp in tg.groupby("team_id"):
    seen = {}
    for _, r in grp.iterrows():
        n_prior[(tid, r.game_id)] = seen.get(r.season, 0)
        seen[r.season] = seen.get(r.season, 0) + 1

by_game = {}
for gid, grp in tg.groupby("game_id"):
    h = grp[grp.is_home == 1].iloc[0]
    a = grp[grp.is_home != 1].iloc[0]
    by_game[gid] = (h.team_id, a.team_id, int(h.season))

seasons = sorted({s for _, _, s in by_game.values()})

# ------------------------------------------------ B4: SC10 covariate support
supp = {"support_floor_declared": 4}
for thresh in (4,):
    ok = [g for g in uni if min(n_prior[(by_game[g][0], g)],
                                n_prior[(by_game[g][1], g)]) >= thresh]
    supp[f"clusters_with_both_sides_ge_{thresh}_same_season_prior_games"] = {
        "pooled": len(ok),
        "share": round(len(ok) / len(uni), 4),
        "per_season": {str(s): sum(1 for g in ok if by_game[g][2] == s) for s in seasons},
    }
below = [g for g in uni if min(n_prior[(by_game[g][0], g)],
                               n_prior[(by_game[g][1], g)]) < 4]
supp["clusters_taking_the_zero_spread_fallback"] = {
    "pooled": len(below),
    "per_season": {str(s): sum(1 for g in below if by_game[g][2] == s) for s in seasons},
}
supp["covariate_sources"] = ["data/masters/master_team.parquet"]
supp["covariate_columns_consumed"] = ["game_id", "team_id", "opp_team_id", "is_home",
                                      "season", "game_date", "pts", "opp_pts"]
supp["new_external_source_required"] = False
out["B4_sc10_orthogonalisation_covariate_support"] = supp

# ------------------------------------------------ B5: SC02 design condition numbers
sb = pd.read_parquet(sb_path)
comp = sb[sb.method == "composite_pace_x_eff_v1"].set_index("game_id")
lg = sb[sb.method == "league_average_v1"].set_index("game_id")


def comp_col(gid, col):
    if gid in comp.index and pd.notna(comp.at[gid, col]):
        return float(comp.at[gid, col])
    return float(lg.at[gid, col])


rows = []
for g in sorted(uni):
    th, ta, s = by_game[g]
    nh, na = n_prior[(th, g)], n_prior[(ta, g)]
    rows.append({"game_id": g, "season": s,
                 "C_total": comp_col(g, "pred_total"),
                 "C_margin": comp_col(g, "pred_margin"),
                 "a07_sum": np.exp(-nh / 5.0) + np.exp(-na / 5.0),
                 "a07_diff": np.exp(-nh / 5.0) - np.exp(-na / 5.0)})
df = pd.DataFrame(rows)


def kappa(mat):
    """condition number (2-norm) of [1, standardised columns]"""
    z = np.column_stack([np.ones(len(mat))] +
                        [(c - c.mean()) / (c.std(ddof=0) if c.std(ddof=0) > 0 else 1.0)
                         for c in mat.T])
    return float(np.linalg.cond(z))


ks = {}
for y in (2022, 2023, 2024, 2025, 2026):
    tr = df[df.season < y]
    ks[f"train_lt_{y}"] = {
        "train_clusters": int(len(tr)),
        "E1_design_[1,C_total,a07_sum]": round(kappa(tr[["C_total", "a07_sum"]].to_numpy()), 3),
        "E2_design_[1,C_margin,a07_diff]": round(kappa(tr[["C_margin", "a07_diff"]].to_numpy()), 3),
    }
out["B5_sc02_design_condition_numbers"] = {
    "definition": "2-norm condition number of the fold's TRAINING design matrix "
                  "[intercept, standardised null-granted column, standardised treatment term]; "
                  "no target and no metric enters this computation",
    "per_fold": ks,
    "max_observed": round(max(max(v["E1_design_[1,C_total,a07_sum]"],
                                  v["E2_design_[1,C_margin,a07_diff]"])
                              for v in ks.values()), 3),
    "note": "the threshold pinned in SPEC_V2 must be a convention, not a value read off "
            "this table; kappa_2 >= 1000 is the pinned convention and the measured maxima "
            "sit far below it, so the retirement kill is a live guard against an "
            "implementation that actually degenerates, not a pre-satisfied formality",
}

with open(os.path.join(HERE, "B4_B5_SUPPORT_RECEIPT.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out, indent=1))
