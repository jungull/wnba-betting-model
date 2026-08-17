#!/usr/bin/env python3
"""E1_I0045 s04 -- THE COVERAGE COST, BY NAME, and the downstream exposure shape.

Pruning rows loses coverage.  E1_I0035's Xc lost 5.23% of appeared player-games and reported it
as a share; a share is not inspectable.  Every false removal here is named -- player, club, date,
what she actually scored -- so the trade-off can be argued about rather than accepted.

The exposure-shape metric reproduces E1_I0035's producer model (fixed 200 team-minutes allocated
in proportion to w x e_minutes) and its published X0 value of 8.912455 minutes is used as a fifth
anchor.  It omits the real producer's 40-minute cap and water-filling loop, exactly as E1_I0035's
did, and therefore transfers no better than its did.
"""
from __future__ import annotations
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rc_base as rb  # noqa: E402

pd.set_option("display.width", 250)
F = {}

PF = pd.read_parquet(os.path.join(rb.OUT, "_PF_arms.parquet"))
TF2 = pd.read_parquet(os.path.join(rb.OUT, "_TF_arms.parquet"))
RULES = [c[5:] for c in PF.columns if c.startswith("drop_")]
ARMS = [c[2:] for c in PF.columns if c.startswith("w_")]
print("  rules: %s" % RULES)
print("  arms : %s" % ARMS)

# =========================================================================================
rb.hdr("1. COVERAGE COST -- EVERY FALSE REMOVAL, NAMED")
tmn = rb.load_team_master()[["game_id", "team_id", "game_date", "opp_team_id"]].drop_duplicates()
rows = []
for r in RULES:
    m = PF["drop_" + r].to_numpy(bool) & (PF["appeared"] == 1).to_numpy()
    sub = PF[m].copy()
    sub["rule"] = r
    rows.append(sub)
FALSE = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
FALSE = FALSE.merge(tmn[["game_id", "team_id", "opp_team_id"]], on=["game_id", "team_id"],
                    how="left")
COLS = ("rule", "season", "game_date", "game_id", "team_id", "opp_team_id", "player_id",
        "player_name", "tier_A", "rec_S2", "departed", "seasons_since_club",
        "days_since_club", "p_active_hat", "pts_hat", "minutes", "pts", "starter_flag",
        "n_prior_app_season", "trail5_min", "in_decision_stratum")
FALSE = rb.pick(FALSE, COLS, "false removals")
FALSE = FALSE.sort_values(["rule", "season", "game_date"], kind="stable")
FALSE.to_csv(os.path.join(rb.OUT, "COVERAGE_COST.csv"), index=False)
print("  wrote COVERAGE_COST.csv with %d named false removals across %d rules"
      % (len(FALSE), len(RULES)))
for r in RULES:
    s = FALSE[FALSE["rule"] == r]
    napp = int((PF["appeared"] == 1).sum())
    print("\n  --- %s : %d false removals of %d appeared player-games (%.3f%%)"
          % (r, len(s), napp, 100.0 * len(s) / napp))
    if len(s):
        print(s[["season", "game_date", "player_name", "team_id", "minutes", "pts",
                 "p_active_hat", "seasons_since_club", "departed",
                 "in_decision_stratum"]].to_string(index=False))
F["false_removals"] = {r: int((FALSE["rule"] == r).sum()) for r in RULES}
F["n_appeared_rows"] = int((PF["appeared"] == 1).sum())

print("\n  For comparison, E1_I0035's Xc (prune by p_active threshold) lost 684 appeared")
print("  player-games, 5.23%% of all of them.  The worst currency rule here loses %d (%.3f%%)."
      % (max(F["false_removals"].values()),
         100.0 * max(F["false_removals"].values()) / F["n_appeared_rows"]))

# who is removed, correctly, in bulk -- the other side of the ledger
print("\n  THE OTHER SIDE: correct removals (dropped, did not appear)")
cr = []
for r in RULES:
    m = PF["drop_" + r].to_numpy(bool)
    cr.append({"rule": r, "n_dropped": int(m.sum()),
               "n_correct": int((m & (PF["appeared"] == 0).to_numpy()).sum()),
               "n_false": int((m & (PF["appeared"] == 1).to_numpy()).sum()),
               "precision_of_removal": float((m & (PF["appeared"] == 0).to_numpy()).sum()
                                             / max(m.sum(), 1))})
CR = pd.DataFrame(cr)
print(CR.to_string(index=False))
CR.to_csv(os.path.join(rb.OUT, "removal_precision.csv"), index=False)
F["removal_precision"] = CR.to_dict("records")

# the biggest contributors removed, by player -- the "established starters held against clubs
# they have left" population E1_I0035 named
big = (PF[PF["drop_R3_union_S2"]].groupby("player_name")
       .agg(rows_removed=("p_active_hat", "size"), mean_p_active=("p_active_hat", "mean"),
            appearances=("appeared", "sum"),
            p_active_mass=("p_active_hat", "sum")).reset_index()
       .sort_values("p_active_mass", ascending=False).head(20))
print("\n  TOP 20 NAMES BY REMOVED p_active MASS under R3_union_S2:")
print(big.to_string(index=False))
big.to_csv(os.path.join(rb.OUT, "top_removed_players_R3.csv"), index=False)
F["top_removed_R3"] = big.to_dict("records")

# =========================================================================================
rb.hdr("2. DOWNSTREAM EXPOSURE SHAPE  (E1_I0035's producer model; ANCHOR X0 = 8.912455)")
print("  The only site in the repository that multiplies by p_active allocates a fixed 200")
print("  team-minutes in proportion to w x e_minutes_given_active.  A per-team-game UNIFORM")
print("  rescaling of w cancels exactly in that normalisation, which is why E1_I0035's Xb")
print("  changed the team sum and nothing downstream.  What survives is the SHAPE.")
mh = PF["min_hat"].to_numpy(float)
tb = (~PF["tier_A"]).to_numpy(float)
real_min = PF["minutes"].to_numpy(float)
g = PF.groupby(["game_id", "team_id"]).ngroup().to_numpy()
ng = g.max() + 1
real_B = np.bincount(g, weights=tb * real_min, minlength=ng)
er = []
for a in ARMS:
    w = PF["w_" + a].to_numpy(float)
    num = w * mh
    den = np.bincount(g, weights=num, minlength=ng)
    alloc_B = 200.0 * np.bincount(g, weights=num * tb, minlength=ng) / np.maximum(den, 1e-12)
    er.append({"arm": a, "mean_minutes_allocated_to_tier_B": float(alloc_B.mean()),
               "mean_minutes_actually_played_by_tier_B": float(real_B.mean()),
               "misallocation_minutes_per_team_game": float((alloc_B - real_B).mean())})
ER = pd.DataFrame(er)
print(ER.to_string(index=False))
x0 = float(ER.loc[ER["arm"] == "X0", "misallocation_minutes_per_team_game"].iloc[0])
print("\n  ANCHOR: X0 misallocation = %.6f   E1_I0035 published 8.912455   abs diff %.6f  %s"
      % (x0, abs(x0 - 8.912455), "CONFIRMED" if abs(x0 - 8.912455) < 5e-4 else "*** DIFFERS ***"))
F["exposure_anchor"] = {"mine": x0, "published": 8.912455, "confirmed":
                        bool(abs(x0 - 8.912455) < 5e-4)}
ER.to_csv(os.path.join(rb.OUT, "exposure_shape.csv"), index=False)
F["exposure_shape"] = ER.to_dict("records")

# =========================================================================================
rb.hdr("3. TEAM-LEVEL INJECTION FLOOR, RESOLVED  (the verdict-carrying floor)")
blk_t = (TF2["season"].astype(str) + "_" + TF2["team_id"].astype(str)).to_numpy()
noise = (np.abs(TF2["pts"] - TF2["c_Z_R3_union_S2"]).to_numpy(float)
         - np.abs(TF2["pts"] - TF2["c_Xa"]).to_numpy(float))
print("  Noise = the REAL Z_R3-vs-Xa per-row loss difference, centred (36 team-season blocks).")
pw = {}
for eff in (0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0):
    pw[eff] = rb.injection_power(noise, blk_t, eff, 2000, rb.SEED, n_reps=200)
    print("    planted %.2f MAE -> detection rate %.3f" % (eff, pw[eff]))
F["team_injection_floor_Z_R3_vs_Xa"] = pw
floor = min([e for e, v in pw.items() if v >= 0.80], default=None)
print("  => injection-verified 80%% power floor is at or below %s MAE" % floor)
F["team_injection_80pct_floor"] = floor

print("\n  PLAYER (all rows, player-season blocks): the floor for the pooled Brier comparison.")
y = PF["appeared"].to_numpy(float)
blk_p = (PF["season"].astype(str) + "_" + PF["player_id"].astype(str)).to_numpy()
np_noise = ((np.clip(PF["w_Z_R3_union_S2"].to_numpy(float), 0, 1) - y) ** 2
            - (np.clip(PF["w_Xa"].to_numpy(float), 0, 1) - y) ** 2)
pw2 = {}
for eff in (0.0002, 0.0005, 0.001, 0.002, 0.004):
    pw2[eff] = rb.injection_power(np_noise, blk_p, eff, 2000, rb.SEED + 7, n_reps=200)
    print("    planted %.4f Brier -> detection rate %.3f" % (eff, pw2[eff]))
F["player_injection_floor_all_Z_R3_vs_Xa"] = pw2

rb.dump(F, "_s04.json")
print("\nDONE s04")
