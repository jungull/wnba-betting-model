"""STEP 2a -- BUILD THE EFFICIENCY FRAME.  Every input strictly prior-games-only.

PREREGISTERED SPECIFICATIONS.  All three transfer specs below are fixed IN THIS FILE and ALL THREE
are reported in S03, so there is no room to pick the winner after the fact.  The adjustment is
always an additive shift to POINTS PER FIELD-GOAL ATTEMPT:

  SPEC A  (HEADLINE -- the faithful transfer of the D074 result that actually survived)
          adj_ppf = LAMBDA_D074 * w_RA * 2.0 * OC_RA
          The corrected D074 headline (+0.3731536) is a RESTRICTED-AREA conversion slope.  S01a3
          shows the other four zones are ~0 or negative.  So the honest transfer applies the
          surviving slope in the zone it was measured in, weighted by the share of the player's
          strictly-prior attempts that came from there, and valued at 2 points per made shot.

  SPEC B  (five-zone, one global slope -- a DIFFERENT and weaker hypothesis, stated as such)
          adj_ppf = LAMBDA_D074 * sum_z w_z * PV_z * OC_z

  SPEC C  (five-zone, per-zone FROZEN betas -- OPTIMISTIC, LABELLED, NOT A HEADLINE)
          adj_ppf = sum_z beta_z * w_z * PV_z * OC_z, beta_z from S01a3's frozen five-zone table.
          The beta_z were estimated on the SAME 2021-2024 partition, so this spec is in-sample in
          its coefficients and can only flatter the candidate.  It is reported to bound the
          channel from above, never as the verdict.

TIME WINDOW TABLE (also reproduced in NOTES.md):
  OC_z   opponent zone-conversion allowance : opponent's own games with game_date STRICTLY EARLIER
         in the same season (cumsum minus own row).  Gate >=20 prior zone attempts faced AND >=20
         prior pooled attempts faced.  Identical construction to D074's O2 -- verified in S01a2 at
         max|diff| = 0.
  w_z    player prior zone mix              : the player's own games with game_date STRICTLY
         EARLIER in the same season (cumsum minus own row).  Gate >=20 strictly-prior FGA.
  base   champion implied efficiency        : ratios of the champion's OWN point forecasts on this
         row.  Nothing refitted; the champion is not touched.
  ref    refA_*/refB_*                      : D081's strictly-prior expanding player references,
         .shift(1) BEFORE .expanding().  Carried in unchanged from the frozen decomp_frame.
  y      response                           : realised.  A RESPONSE, never an input.

NO `*_pregame` COLUMN FROM pressure_lib.py IS USED ANYWHERE IN THIS SCREEN (D080 subtlety: those
shrink toward the CURRENT season's league mean and are therefore not fully pregame for level
claims).  Nothing here touches pressure_lib.
"""
import json
import os

import numpy as np
import pandas as pd

import et_base as E
import screenkit as sk

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 80)

OUT = {}

# ------------------------------------------------------------------ frozen per-zone betas (SPEC C)
BETA_ZONE = {"Restricted Area": 0.4037, "In The Paint (Non-RA)": -0.1216,
             "Mid-Range": 0.0377, "Corner 3": -0.2558, "Above the Break 3": 0.0005}

E.hdr("S02 -- LOAD RAW SHOTS (2021-2024 only; 2025/2026 files exist and are never constructed)")
shots = E.load_shots(verbose=True)

E.hdr("S02a -- OPPONENT ZONE-CONVERSION ALLOWANCE OC_z (strictly prior games of the opponent)")
oc = pd.concat([E.opponent_zone_allowance(shots, z) for z in E.ZONES], ignore_index=True)
print("\n  %-24s %8s %8s %10s %10s" % ("zone", "rows", "usable", "mean OC", "sd OC"))
occov = {}
for z in E.ZONES:
    q = oc[oc["zone"] == z]
    occov[z] = dict(rows=int(len(q)), usable=int(q["OC"].notna().sum()),
                    mean=float(q["OC"].mean()), sd=float(q["OC"].std()))
    print("  %-24s %8d %8d %+10.5f %10.5f"
          % (z, len(q), q["OC"].notna().sum(), q["OC"].mean(), q["OC"].std()))
OUT["oc_coverage"] = occov

E.hdr("S02a2 -- CENTRE OC_z ON THE STRICTLY-PRIOR LEAGUE ZONE GAP  (OCc = OC - lg_prior_gap)")
print("""  Mandatory, and NOT a free choice.  OC_RA above has a league-wide MEAN of about +0.18: an RA
  shot simply converts better than the pooled average.  D074 measured its slope in a regression
  WITH AN INTERCEPT, which absorbs that common level.  An additive forecast adjustment does not,
  so the uncentred form would inject a systematic positive bias into every row and would be
  testing a mis-calibrated level rather than the cross-sectional signal.  The centred form
  OCc_z = OC_z - (league zone-minus-pooled gap over games STRICTLY BEFORE this date this season)
  is the opponent's DEVIATION from the league, which is what the surviving slope describes.

  DISCLOSURE: this centring was added after inspecting the MEAN and SD of OC_z printed above and
  BEFORE any contrast, skill number or p-value in this screen was computed.  The uncentred variant
  is carried through as a labelled sensitivity so the reader can see both.""")
lg = pd.concat([E.league_prior_zone_gap(shots, z) for z in E.ZONES], ignore_index=True)
oc = oc.merge(lg, on=["season", "game_date", "zone"], how="left")
oc["OCc"] = oc["OC"] - oc["lg_prior_gap"]
print("\n  %-24s %12s %12s %12s %12s %10s" % ("zone", "mean OC", "mean lg gap", "mean OCc",
                                              "sd OCc", "usable"))
occ = {}
for z in E.ZONES:
    q = oc[oc["zone"] == z]
    occ[z] = dict(mean_OC=float(q["OC"].mean()), mean_lg_gap=float(q["lg_prior_gap"].mean()),
                  mean_OCc=float(q["OCc"].mean()), sd_OCc=float(q["OCc"].std()),
                  usable=int(q["OCc"].notna().sum()))
    print("  %-24s %+12.5f %+12.5f %+12.5f %12.5f %10d"
          % (z, q["OC"].mean(), q["lg_prior_gap"].mean(), q["OCc"].mean(), q["OCc"].std(),
             q["OCc"].notna().sum()))
OUT["oc_centred"] = occ

E.hdr("S02b -- PLAYER PRIOR ZONE MIX w_z (strictly prior games of the player)")
mix = E.player_prior_zone_mix(shots)
print("\n  %-24s %8s %10s %10s" % ("zone", "usable", "mean w", "sd w"))
mixcov = {}
for z in E.ZONES:
    q = mix[mix["zone"] == z]
    mixcov[z] = dict(usable=int(q["w"].notna().sum()), mean=float(q["w"].mean()),
                     sd=float(q["w"].std()))
    print("  %-24s %8d %10.5f %10.5f" % (z, q["w"].notna().sum(), q["w"].mean(), q["w"].std()))
w_sum = (mix.dropna(subset=["w"]).groupby(["PLAYER_ID", "season", "GAME_ID"])["w"].sum())
print("\n  identity check  sum_z w_z == 1 on rows with a defined mix: max|sum-1| = %.3e"
      % float((w_sum - 1.0).abs().max()))
assert float((w_sum - 1.0).abs().max()) < 1e-12
OUT["mix_coverage"] = mixcov

E.hdr("S02c -- LEAKAGE PROBE: does the prior-only OC read the opponent's future?  (kit guard)")
print("""  screenkit.future_leakage_probe is run with the KNOWN OFFENDER as the suspect baseline:
  D074's E0-form O1, a leave-one-GAME-out FULL-SEASON opponent zone rate, which reads the
  opponent's LATER games.  The clean comparator is this screen's strictly-prior OC.  The probe
  must FLAG the retrospective one; if it flagged the prior-only one instead, this screen stops.""")
retro = E.opponent_zone_allowance_LOO_RETROSPECTIVE(shots, E.RA)
probe_in = (oc[oc["zone"] == E.RA][["OPP_TEAM_ID", "season", "GAME_ID", "game_date", "OC"]]
            .merge(retro, on=["OPP_TEAM_ID", "season", "GAME_ID"], how="inner"))
# outcome = what the opponent ACTUALLY allowed in this game in RA (realised -- this is the probe's
# outcome column, which is exactly what a leakage probe is supposed to look at).  LABELLED
# DIAGNOSTIC; it is never an input to any forecast.
realised = (shots[shots["zone"] == E.RA]
            .groupby(["OPP_TEAM_ID", "season", "GAME_ID"])["made"].mean()
            .rename("DIAG_realised_ra_allowed").reset_index())
probe_in = probe_in.merge(realised, on=["OPP_TEAM_ID", "season", "GAME_ID"], how="left")
probe_in["entity"] = (probe_in["OPP_TEAM_ID"].astype(str) + "_" + probe_in["season"].astype(str))
probe_in = probe_in.dropna(subset=["OC", "OC_LOO_RETRO", "DIAG_realised_ra_allowed"])
pr = sk.future_leakage_probe(probe_in, baseline_col="OC_LOO_RETRO", clean_col="OC",
                             entity_col="entity", date_col="game_date",
                             outcome_col="DIAG_realised_ra_allowed", verbose=True)
OUT["leakage_probe_retro_vs_prior"] = {k: v for k, v in pr.items()
                                       if not isinstance(v, (np.ndarray, list))}
pr_rev = sk.future_leakage_probe(probe_in, baseline_col="OC", clean_col="OC_LOO_RETRO",
                                 entity_col="entity", date_col="game_date",
                                 outcome_col="DIAG_realised_ra_allowed", verbose=True)
OUT["leakage_probe_reverse"] = {k: v for k, v in pr_rev.items()
                                if not isinstance(v, (np.ndarray, list))}

E.hdr("S02d -- ATTACH TO THE CHAMPION FRAME (D081's frozen decomp_frame, 2022-2024)")
f = pd.read_parquet(E.DECOMP_FRAME)
sk.assert_partition(f, verbose=True)
assert set(f["season"].unique()) <= set(E.CHAMP_SEASONS)

# opponent identity from the shot files: per GAME_ID the two TEAM_IDs.
gt = shots.groupby("GAME_ID")["TEAM_ID"].unique()
opp_map = {}
for gid, teams in gt.items():
    if len(teams) == 2:
        opp_map[(gid, teams[0])] = teams[1]
        opp_map[(gid, teams[1])] = teams[0]
f["OPP_TEAM_ID"] = [opp_map.get((g, t), np.nan) for g, t in zip(f["game_id"], f["team_id"])]
n_no_opp = int(f["OPP_TEAM_ID"].isna().sum())
print("  champion rows = %d ; rows whose opponent could not be resolved from the shot files = %d "
      "(%.2f%%)" % (len(f), n_no_opp, 100.0 * n_no_opp / len(f)))

wide_oc = (oc.pivot_table(index=["OPP_TEAM_ID", "season", "GAME_ID"], columns="zone",
                          values="OCc").reset_index()
           .rename(columns={z: "OC__" + z for z in E.ZONES}))
wide_ocu = (oc.pivot_table(index=["OPP_TEAM_ID", "season", "GAME_ID"], columns="zone",
                           values="OC").reset_index()
            .rename(columns={z: "OCU__" + z for z in E.ZONES}))
wide_w = (mix.pivot_table(index=["PLAYER_ID", "season", "GAME_ID"], columns="zone",
                          values="w").reset_index()
          .rename(columns={z: "W__" + z for z in E.ZONES}))
f = f.merge(wide_oc.rename(columns={"GAME_ID": "game_id"}),
            on=["OPP_TEAM_ID", "season", "game_id"], how="left")
f = f.merge(wide_ocu.rename(columns={"GAME_ID": "game_id"}),
            on=["OPP_TEAM_ID", "season", "game_id"], how="left")
f = f.merge(wide_w.rename(columns={"PLAYER_ID": "player_id", "GAME_ID": "game_id"}),
            on=["player_id", "season", "game_id"], how="left")

cov = {}
for z in E.ZONES:
    cov[z] = dict(oc_present=int(f["OC__" + z].notna().sum()),
                  w_present=int(f["W__" + z].notna().sum()),
                  both=int((f["OC__" + z].notna() & f["W__" + z].notna()).sum()))
print("\n  %-24s %10s %10s %10s" % ("zone", "OC present", "w present", "both"))
for z in E.ZONES:
    print("  %-24s %10d %10d %10d" % (z, cov[z]["oc_present"], cov[z]["w_present"], cov[z]["both"]))
OUT["join_coverage"] = cov
OUT["n_rows_champion_frame"] = int(len(f))
OUT["n_rows_opponent_unresolved"] = n_no_opp

E.hdr("S02e -- BUILD THE THREE PREREGISTERED ADJUSTMENTS (points per attempt)")
for z in E.ZONES:
    f["term__" + z] = (f["W__" + z].fillna(0.0) * E.POINT_VALUE[z] * f["OC__" + z].fillna(0.0))
    f["termU__" + z] = (f["W__" + z].fillna(0.0) * E.POINT_VALUE[z] * f["OCU__" + z].fillna(0.0))
f["adjA_ppf"] = E.LAMBDA_D074 * f["term__" + E.RA]
f["adjB_ppf"] = E.LAMBDA_D074 * sum(f["term__" + z] for z in E.ZONES)
f["adjC_ppf"] = sum(BETA_ZONE[z] * f["term__" + z] for z in E.ZONES)
# UNCENTRED sensitivity -- carries the league-wide zone level, reported but never a headline.
f["adjU_ppf"] = E.LAMBDA_D074 * f["termU__" + E.RA]
f["has_signal"] = (f["OC__" + E.RA].notna() & f["W__" + E.RA].notna())
print("\n  rows with a usable RA signal (OC and w both present) = %d / %d (%.1f%%)"
      % (int(f["has_signal"].sum()), len(f), 100.0 * f["has_signal"].mean()))
print("  rows where every adjustment is exactly 0 (no signal -> candidate == champion) = %d"
      % int((f[["adjA_ppf", "adjB_ppf", "adjC_ppf"]].abs().sum(axis=1) == 0).sum()))
print("\n  %-10s %12s %12s %12s %12s" % ("adjustment", "mean", "sd", "min", "max"))
adjstats = {}
for a in ["adjA_ppf", "adjB_ppf", "adjC_ppf", "adjU_ppf"]:
    adjstats[a] = dict(mean=float(f[a].mean()), sd=float(f[a].std()),
                       min=float(f[a].min()), max=float(f[a].max()))
    print("  %-10s %+12.6f %12.6f %+12.6f %+12.6f"
          % (a, f[a].mean(), f[a].std(), f[a].min(), f[a].max()))
OUT["adjustment_stats"] = adjstats

# ------------------------------------------------------------------ responses and forecasts
f["y_ppf"] = np.where(f["y_fga"] > 0, f["y_pts"] / f["y_fga"].replace(0, np.nan), np.nan)
f["y_ppm"] = f["y_pts"] / f["y_minutes"]
f["base_ppf"] = f["mdl_ppf"]
f["base_ppm"] = f["mdl_ppm"]
for tag in ["A", "B", "C", "U"]:
    f["cand%s_ppf" % tag] = f["base_ppf"] + f["adj%s_ppf" % tag]
    f["cand%s_ppm" % tag] = f["base_ppm"] + f["adj%s_ppf" % tag] * f["mdl_fpm"]
    f["cand%s_pts" % tag] = f["pts__pred_point"] + f["adj%s_ppf" % tag] * f["fga__pred_point"]

# ------------------------------------------------------------------ DIAGNOSTIC: FT dilution
fgpts = (shots[shots["zone"].isin(E.ZONES)]
         .assign(v=lambda d: d["made"] * d["zone"].map(E.POINT_VALUE))
         .groupby(["PLAYER_ID", "season", "GAME_ID"])["v"].sum()
         .rename("DIAG_fg_points").reset_index()
         .rename(columns={"PLAYER_ID": "player_id", "GAME_ID": "game_id"}))
f = f.merge(fgpts, on=["player_id", "season", "game_id"], how="left")
f["DIAG_fg_points"] = f["DIAG_fg_points"].fillna(0.0)
share = float(f["DIAG_fg_points"].sum() / f["y_pts"].sum())
print("""
  *** DIAGNOSTIC, USES REALISED QUANTITIES, EXCLUDED FROM EVERY HEADLINE ***
  Field-goal points are %.1f%% of the total points in this frame; the remaining %.1f%% are free
  throws, which the conversion channel cannot touch.  The response y_pts is TOTAL points because
  that is what the champion forecasts, so the channel is diluted by roughly that factor.  This is
  reported so the ceiling in S04 is read against the right denominator.""" % (100 * share, 100 * (1 - share)))
OUT["DIAG_fg_point_share_of_total_points"] = share

E.hdr("S02f -- WRITE")
keep = ([c for c in ["season", "player_id", "game_id", "team_id", "OPP_TEAM_ID", "gdate",
                     "y_pts", "y_fga", "y_minutes", "y_ppf", "y_ppm", "r_ppm", "r_ppf", "r_fpm",
                     "pts__pred_point", "fga__pred_point", "minutes__pred_point",
                     "mdl_ppf", "mdl_ppm", "mdl_fpm", "base_ppf", "base_ppm",
                     "refA_ppf", "refA_ppm", "refB_ppf", "refB_ppm", "ref_pts", "ref_minutes",
                     "ref_fga", "pl_games_prior", "pl_min_mean5", "pts__is_fallback",
                     "has_signal", "adjA_ppf", "adjB_ppf", "adjC_ppf", "adjU_ppf",
                     "DIAG_fg_points"]]
        + ["OC__" + z for z in E.ZONES] + ["OCU__" + z for z in E.ZONES]
        + ["W__" + z for z in E.ZONES]
        + ["cand%s_%s" % (t, k) for t in "ABCU" for k in ("ppf", "ppm", "pts")])
g = f[keep].copy()
sk.assert_partition(g, verbose=True)
g.to_parquet(os.path.join(E.HERE, "efficiency_frame.parquet"), index=False)
print("  wrote efficiency_frame.parquet  shape=%s  seasons=%s"
      % (g.shape, sorted(g["season"].unique())))
OUT["efficiency_frame_shape"] = list(g.shape)
json.dump(OUT, open(os.path.join(E.HERE, "_s02.json"), "w"), indent=2, default=str)
print("DONE s02")
