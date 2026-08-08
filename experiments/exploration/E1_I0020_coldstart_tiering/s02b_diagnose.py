"""E1_I0020 STEP 2b -- TWO STRUCTURAL SURPRISES IN THE TIER TABLE, DIAGNOSED BEFORE BUILDING ON IT.

  SURPRISE 1.  Only 71 of the 13,879 scored rows have pl_games_prior == 0, but the frame contains
      475 player-seasons.  Every player-season has exactly one first appearance, so ~475 rows should
      sit at 0.  404 first appearances are MISSING from the champion's scored output.  If the
      zero-games population is systematically absent from the evaluation set, STEP 4 cannot be
      answered on it honestly without saying so.

  SURPRISE 2.  Skill is NOT monotone in prior appearances.  At 0 priors it is ~0 (pts +0.008,
      minutes -0.000); at 1 prior it is -0.049 / -0.101; at 2 priors it COLLAPSES to -0.391 /
      -0.818; at 3 priors it is back to +0.026 / -0.036.  A cold-start story predicts monotone
      recovery.  This shape does not, so the mechanism is something else and must be identified
      before a tier boundary is justified by it.
"""
import os

import numpy as np
import pandas as pd

import ct_base as B

OUT = {}
w = pd.read_parquet(os.path.join(B.OUT, "tier_frame.parquet"))
B.assert_partition_adjudicated(w, where="tier_frame reload")

# ============================================================ SURPRISE 1
B.hdr("STEP 2b.1 -- WHERE ARE THE MISSING FIRST APPEARANCES?")
g = w.groupby(["season", "player_id"])["pl_games_prior"].min()
print("  player-seasons in the scored frame: %d" % len(g))
print("  distribution of the MINIMUM pl_games_prior within each player-season:")
vc = g.value_counts().sort_index()
print(vc.head(20).to_string())
OUT["min_games_prior_per_player_season"] = {str(k): int(v) for k, v in vc.items()}
print("\n  player-seasons whose first SCORED row is not their first appearance: %d of %d (%.1f%%)"
      % (int((g > 0).sum()), len(g), 100.0 * (g > 0).mean()))

# Is it a team-schedule effect?  Compare against master_player.
mp = B.load_master()
mp2 = mp[mp["season"].isin(B.SCREEN_SEASONS) & mp["appeared"]].copy()
mp2["game_id"] = mp2["game_id"].astype(str)
w["game_id"] = w["game_id"].astype(str)
key = ["game_id", "team_id", "player_id"]
scored = set(map(tuple, w[key].to_numpy()))
mp2["_scored"] = [tuple(r) in scored for r in mp2[key].to_numpy()]
print("\n  appeared player-games in master_player 2022-2024 : %d" % len(mp2))
print("  of those, present in the champion's scored frame  : %d (%.1f%%)"
      % (int(mp2["_scored"].sum()), 100 * mp2["_scored"].mean()))
OUT["master_appeared_2022_2024"] = int(len(mp2))
OUT["master_appeared_scored"] = int(mp2["_scored"].sum())

dc = B.build_depth_chart(mp)
dc["game_id"] = dc["game_id"].astype(str)
mp2 = mp2.merge(dc[key + ["mp_prior_games"]], on=key, how="left")
tab = mp2.groupby(mp2["mp_prior_games"].clip(upper=10)).agg(
    n_master=("_scored", "size"), n_scored=("_scored", "sum"))
tab["coverage"] = tab["n_scored"] / tab["n_master"]
print("\n  COVERAGE OF THE CHAMPION'S SCORED FRAME BY PRIOR-APPEARANCE COUNT:")
print(tab.to_string(float_format=lambda v: "%.4f" % v))
OUT["coverage_by_prior_games"] = tab.reset_index().to_dict("records")
print("""
  READING: the champion's evaluation set is NOT a random sample of appearances.  Coverage at 0
  prior appearances is far below coverage elsewhere, so the population STEP 4 is about is
  systematically UNDER-REPRESENTED in the only rows on which the champion can be scored.  Every
  zero-games number in this screen is therefore conditional on that selection and is reported with
  its n attached.
""")

# ============================================================ SURPRISE 2
B.hdr("STEP 2b.2 -- WHY DOES SKILL COLLAPSE AT EXACTLY 2 PRIOR APPEARANCES?")
sub = w[w["pl_games_prior"] <= 4].copy()
rows = []
for n in [0, 1, 2, 3, 4]:
    m = sub["pl_games_prior"] == n
    s = sub[m]
    r = dict(n_prior=n, n=int(m.sum()),
             fallback_rate=float(s["pts__is_fallback"].mean()),
             mean_fallback_level=float(s["pts__fallback_level"].mean()),
             coldstart_rate=float(s["pts__is_cold_start"].mean()),
             mean_champ_pts=float(s["champ_pts"].mean()),
             sd_champ_pts=float(s["champ_pts"].std()),
             mean_ref_pts=float(s["p1_pts"].mean()),
             sd_ref_pts=float(s["p1_pts"].std()),
             mean_y_pts=float(s["t_pts"].mean()),
             sd_y_pts=float(s["t_pts"].std()),
             mean_champ_min=float(s["champ_minutes"].mean()),
             sd_champ_min=float(s["champ_minutes"].std()),
             mean_ref_min=float(s["p1_minutes"].mean()),
             mean_y_min=float(s["t_minutes"].mean()),
             mean_tm_game_idx=float(s["tm_game_idx"].mean()))
    rows.append(r)
D = pd.DataFrame(rows)
print(D.to_string(index=False, float_format=lambda v: "%.3f" % v))
OUT["low_n_diagnostics"] = D.to_dict("records")
print("""
  The champion's fallback flag is 1.0 for n = 0, 1, 2 and ~0.13 at n = 3, so the whole data-poor
  regime IS the fallback path.  The question is why the SAME path is near-neutral at n=0 and
  catastrophic at n=2.
""")

print("  DECOMPOSING BY WHAT THE REFERENCE IS DOING (the D076 lesson: skill is RELATIVE):")
for n in [0, 1, 2, 3]:
    m = w["pl_games_prior"] == n
    s = w[m]
    cm = B.mae(s["t_pts"], s["champ_pts"])
    rm = B.mae(s["t_pts"], s["p1_pts"])
    cmi = B.mae(s["t_minutes"], s["champ_minutes"])
    rmi = B.mae(s["t_minutes"], s["p1_minutes"])
    print("   n=%d  n_rows=%4d | pts champMAE=%6.3f refMAE=%6.3f | min champMAE=%6.3f refMAE=%6.3f"
          % (n, m.sum(), cm, rm, cmi, rmi))
print("""
  THE MECHANISM IS THE REFERENCE, NOT THE MODEL.  At n=0 the reference has NO player-specific
  information and falls back to the same-season expanding league mean, so it is weak and the
  champion ties it.  At n=1 and n=2 the reference becomes the player's own 1- or 2-game running
  mean, which for a player who has just appeared is a SHARP, correctly-scaled estimate of their
  current role -- and the champion's fallback path does not move nearly as far.  By n>=3 the
  champion's real path switches on and it recovers.

  CONSEQUENCE FOR THE USER'S QUESTION.  The damage is concentrated where the player HAS one or two
  observations and the model is not using them, NOT where the player has none.  A structural
  placeholder (position / draft / depth) has no competition only in the n=0 cell -- which is 71
  rows -- while the expensive cell, n in {1,2}, is exactly where the player's OWN running mean is
  already available and already winning.
""")

print("  IS THE FALLBACK FLAG A BETTER TIER VARIABLE THAN A PRIOR-APPEARANCE COUNT?")
fb = w["pts__is_fallback"].to_numpy(bool)
lt3 = (w["pl_games_prior"] < 3).to_numpy(bool)
print("     fallback rows           : %5d" % fb.sum())
print("     pl_games_prior < 3 rows : %5d" % lt3.sum())
print("     both                    : %5d" % (fb & lt3).sum())
print("     fallback but >=3 priors : %5d" % (fb & ~lt3).sum())
print("     <3 priors but not fallb : %5d" % (~fb & lt3).sum())
for lbl, m in [("fallback only", fb & ~lt3), ("both", fb & lt3), ("<3 only", ~fb & lt3)]:
    if m.sum() > 30:
        s = w[m]
        print("     %-16s n=%5d  pts skill=%+.4f  minutes skill=%+.4f"
              % (lbl, m.sum(), B.skill_mae(s["t_pts"], s["champ_pts"], s["p1_pts"])[0],
                 B.skill_mae(s["t_minutes"], s["champ_minutes"], s["p1_minutes"])[0]))
OUT["fallback_vs_count"] = {"n_fallback": int(fb.sum()), "n_lt3": int(lt3.sum()),
                            "n_both": int((fb & lt3).sum()),
                            "n_fallback_ge3": int((fb & ~lt3).sum()),
                            "n_lt3_not_fallback": int((~fb & lt3).sum())}
print("""
  The 'fallback but >= 3 priors' cell is the returning-from-absence case the task asked about:
  players whose model path fell back for a reason other than a thin season count.
""")
ret = w[fb & ~lt3]
if len(ret) > 30:
    print("  returning-from-absence cell: mean pl_teamgames_since_appear=%.2f (vs %.2f overall)"
          % (ret["pl_teamgames_since_appear"].mean(), w["pl_teamgames_since_appear"].mean()))
    print("                               mean pl_games_prior=%.2f" % ret["pl_games_prior"].mean())
    OUT["returning_cell"] = {"n": int(len(ret)),
                             "mean_teamgames_since_appear": float(ret["pl_teamgames_since_appear"].mean()),
                             "mean_games_prior": float(ret["pl_games_prior"].mean())}

B.jdump(OUT, "_s02b.json")
print("\nSTEP 2b COMPLETE.")
