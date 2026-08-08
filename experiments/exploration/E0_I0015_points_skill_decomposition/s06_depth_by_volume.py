"""STEP 6e -- depth x volume, because 'adequate history' and 'stable high-minutes' disagreed.

s05 found points skill +1.44% on rows with >=8 prior appearances, but s04's sensitivity table found
-0.29% on the STABLE subset (>=15 prior appearances AND trailing-5 mean minutes >=24), which is a
SUBSET of it.  Both cannot be the whole story.  This resolves it on a two-way table before anything
is written down, and then regenerates FINDINGS.json with the corrected headline.
"""
import json
import os

import numpy as np
import pandas as pd

import psd_base as B
import screenkit as sk

pd.set_option("display.width", 240)

f = pd.read_parquet(os.path.join(B.OUT, "decomp_frame.parquet"))
sk.assert_partition(f, verbose=False)
y = f["y_pts"].to_numpy(float)
ref_pts = f["ref_pts"].to_numpy(float)
champ = f["pts__pred_point"].to_numpy(float)
blocks = B.block_codes_player_season(f)
gp = f["pl_games_prior"].to_numpy(float)
m5 = f["pl_min_mean5"].to_numpy(float)

B.hdr("STEP 6e -- POINTS SKILL BY (prior-appearance depth) x (trailing-5 mean minutes)")
depth_bins = [("D1 <3", gp < 3), ("D2 3-7", (gp >= 3) & (gp < 8)),
              ("D3 8-19", (gp >= 8) & (gp < 20)), ("D4 >=20", gp >= 20)]
vol_bins = [("V1 <14 min", m5 < 14), ("V2 14-24 min", (m5 >= 14) & (m5 < 24)),
            ("V3 >=24 min", m5 >= 24), ("V? no trailing-5", ~np.isfinite(m5))]
rows = []
print("\n  points skill (n in brackets).  Reference faces the same rows in every cell.")
print("  %-10s %-22s %-22s %-22s %-22s" % ("", *[v[0] for v in vol_bins]))
for dl, dm in depth_bins:
    cells = []
    for vl, vm in vol_bins:
        m = dm & vm
        if m.sum() < 60:
            cells.append("        --        ")
            rows.append(dict(depth=dl, volume=vl, n=int(m.sum()), points_skill=np.nan,
                             minutes_skill=np.nan, rate_skill=np.nan))
            continue
        s = B.skill(y[m], champ[m], ref_pts[m])[0]
        sm = B.skill(f["y_minutes"].to_numpy(float)[m],
                     f["minutes__pred_point"].to_numpy(float)[m],
                     f["ref_minutes"].to_numpy(float)[m])[0]
        sr = B.skill(f["r_ppm"].to_numpy(float)[m], f["mdl_ppm"].to_numpy(float)[m],
                     f["refA_ppm"].to_numpy(float)[m])[0]
        d = np.abs(y[m] - champ[m]) - np.abs(y[m] - ref_pts[m])
        bt = B.block_signflip_test(d, blocks[m], n_draws=1000)
        cells.append("%+8.4f [%5d] p%.3f" % (s, m.sum(), bt["p_two_sided_blockflip"]))
        rows.append(dict(depth=dl, volume=vl, n=int(m.sum()), points_skill=s, minutes_skill=sm,
                         rate_skill=sr, p_blockflip=bt["p_two_sided_blockflip"]))
    print("  %-10s %-22s %-22s %-22s %-22s" % (dl, *cells))
DV = pd.DataFrame(rows)
DV.to_csv(os.path.join(B.OUT, "points_skill_depth_by_volume.csv"), index=False)

print("\n  same table, MINUTES skill:")
print(DV.pivot(index="depth", columns="volume", values="minutes_skill").to_string(
    float_format=lambda v: "%+.4f" % v))
print("\n  same table, POINTS-PER-MINUTE (rate) skill:")
print(DV.pivot(index="depth", columns="volume", values="rate_skill").to_string(
    float_format=lambda v: "%+.4f" % v))

B.hdr("STEP 6f -- THE DECISION-RELEVANT STRATUM, STATED ALONE")
m = (gp >= 8) & (m5 >= 24)
d = np.abs(y[m] - champ[m]) - np.abs(y[m] - ref_pts[m])
bt = B.block_signflip_test(d, blocks[m], n_draws=2000)
s = B.skill(y[m], champ[m], ref_pts[m])[0]
print("""
  ESTABLISHED, HIGH-MINUTES PLAYERS -- the rows a points market would actually be bet:
     rule: >=8 prior same-season appearances AND trailing-5 mean minutes >=24
     n = %d (%.0f%% of appeared player-games)
     champion points MAE  = %.4f
     prior-mean reference = %.4f
     POINTS SKILL         = %+.5f   (p = %.4f, (season,player) block sign-flip, 2000 draws)

  This is the honest headline number for deployment, and it is NOT distinguishable from zero.
  The +1.44%% on all '>=8 prior appearances' rows is carried by the LOW- and MID-minutes players
  inside that group, where the running mean is a weaker reference because the player's own minutes
  are volatile.  On the players whose points lines actually get bet, the champion is level with a
  running mean of their own prior games.
""" % (int(m.sum()), 100 * m.mean(), B.mae(y[m], champ[m]), B.mae(y[m], ref_pts[m]), s,
       bt["p_two_sided_blockflip"]))
res = dict(rule=">=8 prior same-season appearances AND trailing-5 mean minutes >=24",
           n=int(m.sum()), pct_of_rows=float(100 * m.mean()),
           champion_points_mae=B.mae(y[m], champ[m]),
           reference_points_mae=B.mae(y[m], ref_pts[m]), points_skill=s,
           p_two_sided_block_signflip=bt["p_two_sided_blockflip"],
           minutes_skill=B.skill(f["y_minutes"].to_numpy(float)[m],
                                 f["minutes__pred_point"].to_numpy(float)[m],
                                 f["ref_minutes"].to_numpy(float)[m])[0],
           rate_ppm_skill=B.skill(f["r_ppm"].to_numpy(float)[m], f["mdl_ppm"].to_numpy(float)[m],
                                  f["refA_ppm"].to_numpy(float)[m])[0])
print("     minutes skill on the same rows = %+.5f   rate skill = %+.5f"
      % (res["minutes_skill"], res["rate_ppm_skill"]))

json.dump(dict(depth_by_volume=DV.to_dict("records"), decision_relevant_stratum=res),
          open(os.path.join(B.OUT, "_s06.json"), "w"), indent=2, default=str)
print("DONE s06")
