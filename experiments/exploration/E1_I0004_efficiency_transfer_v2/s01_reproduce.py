"""STEP 1 -- REPRODUCE BOTH ANCHORS BEFORE CHANGING ANYTHING.

(a) D074 / I0004's CORRECTED conversion headline, slope +0.3731536 (never the killed E0 +0.0392).
    Three levels of reproduction, weakest to strongest:
      a1  the STATISTIC, recomputed from E1_I0004_shot_selection's frozen repro_ra_common.parquet
      a2  the CONSTRUCTION of the opponent side, rebuilt here from the RAW per-shot files and
          compared value-by-value with the frozen O2 column (this is the piece THIS screen reuses)
      a3  the FIVE-ZONE conversion family betas, recomputed from the frozen conversion_frame
(b) D081 / E0_I0015's DECISION-RELEVANT-STRATUM points skill, -0.36% at p=0.27 on n=5,107,
    recomputed from its frozen decomp_frame.parquet with its own psd_base machinery.

If either fails to reproduce this screen STOPS.  Recent screens reproduced at 0.000e+00 and
4.9e-05; that is the standard.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import etv2_base as E  # noqa: E402
import psd_base as B  # noqa: E402
import screenkit as sk  # noqa: E402

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 60)

OUT = {}
FAIL = []

E.hdr("S01 -- INPUT PROVENANCE (screenkit.check_manifest; missing manifest is UNVERIFIABLE)")
prov = {}
for tag, p in [("decomp_frame (D081)", E.DECOMP_FRAME),
               ("repro_ra_common (D074)", os.path.join(E.SEL, "repro_ra_common.parquet")),
               ("conversion_frame (D074)", os.path.join(E.SEL, "conversion_frame.parquet")),
               ("raw shots 2022 regular",
                os.path.join(E.ROOT, r"data\shotcharts\shots_2022_regular.parquet")),
               ("raw shots 2023 regular",
                os.path.join(E.ROOT, r"data\shotcharts\shots_2023_regular.parquet")),
               ("raw shots 2024 regular",
                os.path.join(E.ROOT, r"data\shotcharts\shots_2024_regular.parquet"))]:
    r = sk.check_manifest(p)
    prov[tag] = {k: r[k] for k in ("manifest_present", "asof_granularity", "status",
                                   "usable_at_e0_e1", "filtering_helps")}
    print("  %-26s manifest=%-5s status=%s" % (tag, r["manifest_present"], r["status"]))
print("""
  Every input is 'UNVERIFIABLE' (no sibling manifest), which is NOT a pass and travels with the
  verdict.  This screen proceeds on them because it is a REPRODUCTION-AND-CONTRAST screen: the
  anchor parquets are frozen outputs of committed screens whose own partition was value-checked,
  and the raw per-season shot files carry the season IN THE FILENAME and are re-checked here on
  COLUMN VALUES via assert_partition.  data/zone_maps/* (asof_granularity 'artifact') are NOT
  READ ANYWHERE.  Nothing here is a deployable result.""")
OUT["input_provenance"] = prov

# ============================================================ (a1) THE STATISTIC, FROZEN FRAME ====
E.hdr("S01a1 -- D074 conversion headline, statistic recomputed from the frozen COMMON frame")
common = pd.read_parquet(os.path.join(E.SEL, "repro_ra_common.parquet"))
sk.assert_partition(common, verbose=True)
g = common[["resid_B1", "O2", "OPP_TEAM_ID", "season"]].dropna()
st = E.e0_stat(g, "resid_B1", "O2")
st.update(E.ols_cluster(g["resid_B1"], g["O2"],
                        (g["OPP_TEAM_ID"].astype(str) + "_" + g["season"].astype(str)).tolist()))
d = {k: float(st[k] - E.D074_TARGET[k]) for k in ("corr", "diff", "beta")}
d["n"] = int(st["n"] - E.D074_TARGET["n"])
print("\n  reproduced : n=%d  corr=%+.8f  diff=%+.8f  beta=%+.8f"
      % (st["n"], st["corr"], st["diff"], st["beta"]))
print("  D074 target: n=%d  corr=%+.8f  diff=%+.8f  beta=%+.8f"
      % (E.D074_TARGET["n"], E.D074_TARGET["corr"], E.D074_TARGET["diff"], E.D074_TARGET["beta"]))
print("  ABSOLUTE DELTA: dn=%d  |dcorr|=%.3e  |ddiff|=%.3e  |dbeta|=%.3e"
      % (d["n"], abs(d["corr"]), abs(d["diff"]), abs(d["beta"])))
ok_a1 = (d["n"] == 0) and abs(d["beta"]) < 1e-12
print("  VERDICT: %s" % ("EXACT" if ok_a1 else "*** NOT EXACT ***"))
if not ok_a1:
    FAIL.append("a1 D074 statistic")
OUT["a1_d074_statistic"] = dict(reproduced=st, target=E.D074_TARGET, delta=d, exact=bool(ok_a1))

# ================================== (a2) THE CONSTRUCTION -- rebuild O2 from the RAW shot files ===
E.hdr("S01a2 -- D074 opponent side REBUILT FROM RAW SHOTS and compared value-by-value with O2")
print("""  This is the piece this screen actually reuses, so reproducing the STATISTIC is not enough:
  the opponent zone-conversion allowance is rebuilt from data/shotcharts/shots_{2021..2024}_*.parquet
  by etv2_base.opponent_zone_allowance and matched against the frozen O2 column row by row.""")
shots_all = E.load_shots(verbose=True)                      # 2021-2024, as D074 built it
oc_ra_all = E.opponent_zone_allowance(shots_all, E.RA)
chk = common.merge(oc_ra_all[["OPP_TEAM_ID", "season", "GAME_ID", "OC"]],
                   on=["OPP_TEAM_ID", "season", "GAME_ID"], how="left")
both = chk[["O2", "OC"]].dropna()
maxdiff = float((chk["O2"] - chk["OC"]).abs().max())
n_miss = int(chk["OC"].isna().sum())
print("\n  rows matched = %d / %d   rows where my rebuild is NaN but O2 is not = %d"
      % (len(both), len(chk), n_miss))
print("  max |O2_frozen - OC_rebuilt| = %.3e     corr = %.12f"
      % (maxdiff, float(both["O2"].corr(both["OC"]))))
ok_a2 = (maxdiff < 1e-12) and n_miss == 0
print("  VERDICT: %s" % ("EXACT -- the construction, not just the number" if ok_a2
                         else "*** NOT EXACT ***"))
if not ok_a2:
    FAIL.append("a2 D074 construction")
OUT["a2_d074_construction"] = dict(n_matched=int(len(both)), n_rebuild_nan=n_miss,
                                   max_abs_diff=maxdiff, exact=bool(ok_a2))

# ================================================ (a3) FIVE-ZONE FAMILY from the frozen frame =====
E.hdr("S01a3 -- D074's five-zone conversion family, recomputed from the frozen conversion_frame")
CONV = pd.read_parquet(os.path.join(E.SEL, "conversion_frame.parquet"))
sk.assert_partition(CONV, verbose=False)
PUB = {"Restricted Area": (33273, 0.0313, 0.0191, 0.4037),
       "In The Paint (Non-RA)": (23798, -0.0078, 0.0017, -0.1216),
       "Mid-Range": (21100, 0.0025, 0.0094, 0.0377),
       "Corner 3": (3150, -0.0312, -0.0326, -0.2558),
       "Above the Break 3": (33833, 0.0000, -0.0034, 0.0005)}
fam = {}
print("\n  %-24s%8s%10s%10s%10s   %s"
      % ("zone", "n", "corr", "diff", "beta", "published (n,corr,diff,beta)"))
ok_a3 = True
for z in E.ZONES:
    q = CONV[CONV["zone_name"] == z][["resid", "OC", "OPP_TEAM_ID", "season"]].dropna()
    s = E.e0_stat(q, "resid", "OC")
    s.update(E.ols_cluster(q["resid"], q["OC"],
                           (q["OPP_TEAM_ID"].astype(str) + "_" + q["season"].astype(str)).tolist()))
    p = PUB[z]
    m = (s["n"] == p[0] and abs(s["corr"] - p[1]) < 5e-5 and abs(s["diff"] - p[2]) < 5e-5
         and abs(s["beta"] - p[3]) < 5e-5)
    ok_a3 &= m
    fam[z] = dict(reproduced=s, published=dict(n=p[0], corr=p[1], diff=p[2], beta=p[3]),
                  max_abs_delta=float(max(abs(s["corr"] - p[1]), abs(s["diff"] - p[2]),
                                          abs(s["beta"] - p[3]))), match=bool(m))
    print("  %-24s%8d%+10.4f%+10.4f%+10.4f   (%d, %+.4f, %+.4f, %+.4f)  %s"
          % (z, s["n"], s["corr"], s["diff"], s["beta"], p[0], p[1], p[2], p[3],
             "MATCH" if m else "MISMATCH"))
print("""
  READ THIS TABLE BEFORE READING ANY LATER RESULT.  D074's surviving conversion effect is
  essentially a RESTRICTED-AREA effect (+0.4037).  Of the other four zones two are NEGATIVE
  (paint -0.1216, corner 3 -0.2558) and two are ~0.  The family-wise p 0.0124 is a max-t statement
  about the RA cell surviving five-way multiplicity, NOT a statement that all five zones carry the
  effect.  This screen's PRIMARY transfer spec is therefore RA-ONLY.  A spec that spreads one
  global slope over all five zones is a DIFFERENT and weaker hypothesis and is reported as
  secondary.""")
if not ok_a3:
    FAIL.append("a3 five-zone family")
OUT["a3_five_zone_family"] = fam

# ================================== *** THE CENTRING, MEASURED ON THE ANCHOR ITSELF *** ===========
E.hdr("S01a4 -- THE INHERITED DEFECT, QUANTIFIED: how big is the level the centring removes?")
print("""  The predecessor died reporting that the UNCENTRED allowance is a level shift, not a
  cross-sectional signal.  Here is the size of that level, per zone, on the frozen O2/OC values.""")
lg_rows = []
for z in E.ZONES:
    ocz = E.opponent_zone_allowance(shots_all, z)
    lgz = E.league_prior_zone_gap(shots_all, z)
    m = E.centred_allowance(ocz, lgz)
    v = m.dropna(subset=["OCc"])
    lg_rows.append(dict(zone=z, n=int(len(v)),
                        mean_OC_uncentred=float(v["OC"].mean()),
                        sd_OC_uncentred=float(v["OC"].std(ddof=1)),
                        mean_OCc_centred=float(v["OCc"].mean()),
                        sd_OCc_centred=float(v["OCc"].std(ddof=1)),
                        mean_over_sd_uncentred=float(abs(v["OC"].mean()) / v["OC"].std(ddof=1)),
                        corr_OC_OCc=float(v["OC"].corr(v["OCc"]))))
lgt = pd.DataFrame(lg_rows)
print(lgt.to_string(index=False))
print("""
  READ THE `mean_over_sd_uncentred` COLUMN.  For the Restricted Area the UNCENTRED allowance has a
  mean many times its own cross-sectional sd: used additively it is overwhelmingly a CONSTANT
  ADDED TO EVERY ROW.  Centring removes exactly that constant (per point in time) and leaves the
  opponent's deviation.  `corr_OC_OCc` < 1 shows the centring is not the identity.""")
lgt.to_csv(os.path.join(E.HERE, "centring_level_table.csv"), index=False)
OUT["a4_centring_level"] = lg_rows

# ======================================================= (b) D081 DECISION-RELEVANT STRATUM =======
E.hdr("S01b -- D081 decision-relevant-stratum points skill, recomputed from the frozen decomp_frame")
f = pd.read_parquet(E.DECOMP_FRAME)
sk.assert_partition(f, verbose=True)
y = f["y_pts"].to_numpy(float)
ref_pts = f["ref_pts"].to_numpy(float)
champ = f["pts__pred_point"].to_numpy(float)
blocks = B.block_codes_player_season(f)
gp = f["pl_games_prior"].to_numpy(float)
m5 = f["pl_min_mean5"].to_numpy(float)
m = (gp >= 8) & (m5 >= 24)
dd = np.abs(y[m] - champ[m]) - np.abs(y[m] - ref_pts[m])
bt = B.block_signflip_test(dd, blocks[m], n_draws=2000)          # same seed default as D081
rep = dict(n=int(m.sum()), points_skill=B.skill(y[m], champ[m], ref_pts[m])[0],
           champion_points_mae=B.mae(y[m], champ[m]),
           reference_points_mae=B.mae(y[m], ref_pts[m]),
           p_two_sided_block_signflip=bt["p_two_sided_blockflip"],
           minutes_skill=B.skill(f["y_minutes"].to_numpy(float)[m],
                                 f["minutes__pred_point"].to_numpy(float)[m],
                                 f["ref_minutes"].to_numpy(float)[m])[0],
           rate_ppm_skill=B.skill(f["r_ppm"].to_numpy(float)[m], f["mdl_ppm"].to_numpy(float)[m],
                                  f["refA_ppm"].to_numpy(float)[m])[0])
db = {k: float(rep[k] - E.D081_TARGET[k]) for k in E.D081_TARGET}
print("\n  %-32s %18s %18s %12s" % ("quantity", "reproduced", "D081 target", "|delta|"))
for k in ["n", "points_skill", "champion_points_mae", "reference_points_mae",
          "p_two_sided_block_signflip", "minutes_skill", "rate_ppm_skill"]:
    print("  %-32s %18.10f %18.10f %12.3e" % (k, rep[k], E.D081_TARGET[k], abs(db[k])))
ok_b = (db["n"] == 0 and abs(db["points_skill"]) < 1e-12
        and abs(db["p_two_sided_block_signflip"]) < 1e-12)
print("  VERDICT: %s" % ("EXACT" if ok_b else "*** NOT EXACT ***"))
if not ok_b:
    FAIL.append("b D081 stratum")
OUT["b_d081_stratum"] = dict(rule=E.STRATUM_RULE, reproduced=rep, target=E.D081_TARGET, delta=db,
                             exact=bool(ok_b))

# ---- the response sd the ceiling in s04 is measured against -------------------------------------
OUT["response_sd"] = dict(
    points_sd_all=float(np.std(y, ddof=1)), points_sd_stratum=float(np.std(y[m], ddof=1)),
    note="D079's ceiling statement is against the points response sd; both are recorded.")
print("\n  points response sd: all rows %.4f   decision-relevant stratum %.4f"
      % (OUT["response_sd"]["points_sd_all"], OUT["response_sd"]["points_sd_stratum"]))

E.hdr("S01 SUMMARY")
print("  a1 D074 statistic        : |dbeta| = %.3e" % abs(d["beta"]))
print("  a2 D074 construction     : max|O2 - OC_rebuilt| = %.3e" % maxdiff)
print("  a3 five-zone family      : max |delta| over 5 zones x 3 stats = %.3e"
      % max(v["max_abs_delta"] for v in fam.values()))
print("  b  D081 stratum skill    : |dskill| = %.3e   |dp| = %.3e"
      % (abs(db["points_skill"]), abs(db["p_two_sided_block_signflip"])))
print("\n  FAILURES: %s" % (FAIL if FAIL else "NONE -- both anchors reproduce; proceeding."))
OUT["failures"] = FAIL
json.dump(OUT, open(os.path.join(E.HERE, "_s01.json"), "w"), indent=2, default=str)
if FAIL:
    raise SystemExit("STOP: anchor reproduction failed -- %s" % FAIL)
print("DONE s01")
