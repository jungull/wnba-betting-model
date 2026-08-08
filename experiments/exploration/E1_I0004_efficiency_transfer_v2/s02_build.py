"""STEP 2 -- BUILD THE EFFICIENCY CONTRAST FRAME, WITH THE ALLOWANCE **CENTRED**.

WHAT IS BUILT, AND THE TIME WINDOW OF EACH PIECE (the full table is in NOTES.md):

  col            what                                        window read
  ------------   -----------------------------------------   ---------------------------------------
  mdl_ppf/ppm    champion's OWN implied efficiency, the       whatever the frozen walk-forward
                 ratio of its own point forecasts             champion saw; nothing refitted here
  OC_z           opponent zone conv. rate MINUS its pooled    opponent's own games STRICTLY EARLIER
                 rate                                         in the same season
  lg_gap_z       league zone-minus-pooled conversion gap      ALL league games on STRICTLY EARLIER
                 (THE CENTRING ANCHOR)                        calendar dates in the same season
  OCc_z          OC_z - lg_gap_z   <-- USED EVERYWHERE        (both of the above)
  w_z            player's prior share of FGA in zone z        player's own games STRICTLY EARLIER
                                                              in the same season
  opp_team_id    who the opponent is                          SCHEDULE (known pre-game)

  NOTHING realised about the game being forecast enters any candidate.  y_pts / y_fga / y_minutes
  appear ONLY as responses.

THE SIGNAL
  S = sum_z  w_z * PV_z * beta_z * OCc_z          [units: POINTS PER FIELD-GOAL ATTEMPT]
  PV_z is the zone's point value (2 or 3).  beta_z is the FROZEN D074 transfer slope; nothing is
  fitted.  Three specs:
    SPEC_RA        beta = +0.3731536 on the Restricted Area ONLY, 0 elsewhere.  *** PRIMARY ***
                   -- this is the cell that actually survived D074's five-way multiplicity.
    SPEC_ALL5_GLOBAL   the same single slope applied to all five zones.  A DIFFERENT, WEAKER
                   hypothesis than the one that survived; secondary.
    SPEC_ALL5_PERZONE  each zone's own published D074 beta (two of which are negative); secondary.

  ALSO BUILT, LABELLED, AND NEVER A HEADLINE: S_UNCENTRED, the defective form the predecessor
  warned about, so the size of the damage is visible rather than asserted.

CANDIDATES
  ppf: cand = mdl_ppf + S                       (S is already points per attempt)
  ppm: cand = mdl_ppm + S * mdl_fpm             (points per attempt x attempts per minute)
  Both reduce to the SAME points forecast, pts_cand = pts_pred + fga_pred * S, which is what
  step 4 propagates.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import etv2_base as E  # noqa: E402
import screenkit as sk  # noqa: E402

pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 80)
OUT = {}

# ------------------------------------------------------------------ 1. champion frame
E.hdr("S02.1 -- champion frame (D081's frozen decomp_frame; NOTHING refitted)")
f = pd.read_parquet(E.DECOMP_FRAME)
sk.assert_partition(f, verbose=True)
f["gid"] = f["game_id"].astype(str)
print("  rows=%d  seasons=%s" % (len(f), sorted(f["season"].unique())))

# ------------------------------------------------------------------ 2. raw shots, champion seasons
E.hdr("S02.2 -- raw shots for the champion seasons only (2022-2024)")
shots = E.load_shots(seasons=E.CHAMP_SEASONS, verbose=True)
oppmap = E.opponent_map(shots)
f["opp_team_id"] = [oppmap.get((g, t), np.nan) for g, t in zip(f["gid"], f["team_id"])]
assert f["opp_team_id"].notna().all()
f["opp_team_id"] = f["opp_team_id"].astype(np.int64)

# ------------------------------------------------------------------ 3. THE CENTRING
E.hdr("S02.3 -- *** THE CENTRING *** OCc_z = OC_z - league prior zone gap (both strictly prior)")
oc_parts, w_parts, centre_report = [], [], []
for z in E.ZONES:
    ocz = E.opponent_zone_allowance(shots, z)
    lgz = E.league_prior_zone_gap(shots, z)
    m = E.centred_allowance(ocz, lgz)
    m["OCc_xs"] = E.crosssectional_demean(m, "OC")          # ALT centring, robustness only
    v = m.dropna(subset=["OCc"])
    centre_report.append(dict(
        zone=z, n_opp_game_rows_with_OCc=int(len(v)),
        mean_OC=float(v["OC"].mean()), sd_OC=float(v["OC"].std(ddof=1)),
        mean_lg_gap=float(v["lg_prior_gap"].mean()),
        mean_OCc=float(v["OCc"].mean()), sd_OCc=float(v["OCc"].std(ddof=1)),
        corr_OC_OCc=float(v["OC"].corr(v["OCc"])),
        corr_OCc_OCcxs=float(v[["OCc", "OCc_xs"]].dropna().corr().iloc[0, 1])))
    oc_parts.append(m[["OPP_TEAM_ID", "season", "GAME_ID", "zone", "OC", "lg_prior_gap",
                       "OCc", "OCc_xs"]])
OC = pd.concat(oc_parts, ignore_index=True)
cr = pd.DataFrame(centre_report)
print(cr.to_string(index=False))
print("""
  WHAT WAS CENTRED, AND HOW.  OC_z is the opponent's prior zone conversion rate MINUS its own prior
  POOLED rate, so it inherits a large ZONE-SPECIFIC common level (RA about +0.18).  The centring
  subtracts the LEAGUE's own prior zone-minus-pooled gap on that calendar date in that season --
  a date-indexed scalar shared by every opponent, so the cross-sectional ORDERING of opponents is
  untouched while the additive LEVEL is removed.  `mean_OCc` is ~0 by construction; `sd_OCc` is
  essentially `sd_OC`, which is the point: the centring removes a level and keeps the signal.""")
OUT["centring"] = centre_report
cr.to_csv(os.path.join(E.HERE, "centring_report.csv"), index=False)

# ------------------------------------------------------------------ 4. player prior zone mix
E.hdr("S02.4 -- player prior zone mix w_z (player's own strictly prior same-season FGA shares)")
W = E.player_prior_zone_mix(shots)
wsum = (W.dropna(subset=["w"]).groupby(["PLAYER_ID", "season", "GAME_ID"])["w"].sum())
print("  w_z rows=%d   sum_z w_z over complete player-games: min=%.6f max=%.6f mean=%.6f"
      % (len(W), wsum.min(), wsum.max(), wsum.mean()))
print("  (sums to <=1; the residual is Backcourt attempts, which have no conversion transfer.)")
OUT["mix_sum_check"] = dict(min=float(wsum.min()), max=float(wsum.max()), mean=float(wsum.mean()))

# ------------------------------------------------------------------ 5. assemble the signal
E.hdr("S02.5 -- assemble S = sum_z w_z * PV_z * beta_z * OCc_z   (points per attempt)")
long = (f[["row_uid", "gid", "season", "player_id", "opp_team_id"]]
        .assign(_k=1).merge(pd.DataFrame({"zone": E.ZONES, "_k": 1}), on="_k").drop(columns="_k"))
long = long.merge(W.rename(columns={"PLAYER_ID": "player_id", "GAME_ID": "gid"})
                  [["player_id", "season", "gid", "zone", "w"]],
                  on=["player_id", "season", "gid", "zone"], how="left")
long = long.merge(OC.rename(columns={"OPP_TEAM_ID": "opp_team_id", "GAME_ID": "gid"}),
                  on=["opp_team_id", "season", "gid", "zone"], how="left")
long["PV"] = long["zone"].map(E.POINT_VALUE)

SPECS = {
    "SPEC_RA": {z: (E.LAMBDA_D074 if z == E.RA else 0.0) for z in E.ZONES},
    "SPEC_ALL5_GLOBAL": {z: E.LAMBDA_D074 for z in E.ZONES},
    "SPEC_ALL5_PERZONE": dict(E.BETA_BY_ZONE_D074),
}
for name, betas in SPECS.items():
    long["_b"] = long["zone"].map(betas)
    for tag, col in [("", "OCc"), ("_UNCENTRED", "OC"), ("_XSCENTRED", "OCc_xs")]:
        long["_t"] = long["w"] * long["PV"] * long["_b"] * long[col]
        # a row contributes 0 only where its beta is 0; otherwise a missing piece kills the row
        need = long["_b"] != 0.0
        bad = need & (~np.isfinite(long["_t"]))
        agg = long.assign(_t=long["_t"].where(~bad, np.nan), _bad=bad)
        s = agg.groupby("row_uid", sort=False).agg(v=("_t", "sum"), nbad=("_bad", "sum"))
        f["S_" + name + tag] = f["row_uid"].map(s["v"].where(s["nbad"] == 0)).astype(float)

# RA-only convenience columns for the grouping-level work
ra = long[long["zone"] == E.RA].set_index("row_uid")
for c in ["w", "OC", "OCc", "lg_prior_gap"]:
    f["RA_" + c] = f["row_uid"].map(ra[c]).astype(float)

sig_cols = [c for c in f.columns if c.startswith("S_")]
print("\n  %-34s %8s %12s %12s %12s" % ("signal column", "n_valid", "mean", "sd", "max|.|"))
sig_summary = {}
for c in sig_cols:
    v = f[c].dropna()
    sig_summary[c] = dict(n=int(len(v)), mean=float(v.mean()), sd=float(v.std(ddof=1)),
                          maxabs=float(v.abs().max()))
    print("  %-34s %8d %+12.6f %12.6f %12.6f"
          % (c, len(v), v.mean(), v.std(ddof=1), v.abs().max()))
print("""
  COMPARE THE `mean` COLUMN, CENTRED vs _UNCENTRED.  The uncentred signal has a mean that dwarfs
  its own sd -- it is a CONSTANT added to every forecast.  That is the defect the predecessor died
  reporting, and it is why every headline below uses the centred column.""")
OUT["signal_summary"] = sig_summary

# ------------------------------------------------------------------ 6. baselines and candidates
E.hdr("S02.6 -- baseline and candidate forecasts (NOTHING FITTED)")
f["mdl_ppf"] = np.where(f["fga__pred_point"] > 0,
                        f["pts__pred_point"] / f["fga__pred_point"].replace(0, np.nan), np.nan)
f["mdl_ppm"] = f["pts__pred_point"] / f["minutes__pred_point"]
f["mdl_fpm"] = f["fga__pred_point"] / f["minutes__pred_point"]
for c in sig_cols:
    tag = c[2:]
    f["ppf_cand_" + tag] = f["mdl_ppf"] + f[c]
    f["ppm_cand_" + tag] = f["mdl_ppm"] + f[c] * f["mdl_fpm"]
    f["pts_cand_" + tag] = f["pts__pred_point"] + f["fga__pred_point"] * f[c]
# identity check: ppm candidate x minutes forecast == points candidate
chk = (f["ppm_cand_SPEC_RA"] * f["minutes__pred_point"] - f["pts_cand_SPEC_RA"]).abs().max()
print("  identity check  max| ppm_cand * minutes_pred - pts_cand |  = %.3e" % chk)
assert chk < 1e-9
OUT["identity_check_ppm_x_minutes_equals_points"] = float(chk)

# ------------------------------------------------------------------ 7. coverage
E.hdr("S02.7 -- COVERAGE: which rows can be scored at all")
f["stratum"] = (f["pl_games_prior"] >= 8) & (f["pl_min_mean5"] >= 24)
cov = []
for name, m in [("all rows", np.ones(len(f), bool)),
                ("decision-relevant stratum", f["stratum"].to_numpy()),
                ("OFF stratum", ~f["stratum"].to_numpy())]:
    sub = f[m]
    cov.append(dict(
        stratum=name, n_rows=int(len(sub)),
        n_signal_RA=int(sub["S_SPEC_RA"].notna().sum()),
        n_signal_ALL5=int(sub["S_SPEC_ALL5_GLOBAL"].notna().sum()),
        n_ppf_scoreable=int((sub["S_SPEC_RA"].notna() & (sub["y_fga"] > 0)
                             & sub["mdl_ppf"].notna()).sum()),
        n_ppm_scoreable=int((sub["S_SPEC_RA"].notna() & sub["mdl_ppm"].notna()).sum())))
covt = pd.DataFrame(cov)
print(covt.to_string(index=False))
covt.to_csv(os.path.join(E.HERE, "coverage.csv"), index=False)
OUT["coverage"] = cov
print("""
  NOTE.  The RA spec needs only the RA zone's pieces; the ALL5 specs need all five and so cover
  slightly fewer rows.  Rows drop where the player has <20 strictly-prior same-season FGA or the
  opponent has faced <20 prior attempts in the zone -- i.e. EARLY-SEASON rows.  Coverage is
  therefore HIGHER on the decision-relevant stratum than off it, which is the right direction:
  the signal is available exactly where the champion fails.""")

# ------------------------------------------------------------------ 8. grouping level
E.hdr("S02.8 -- GROUPING LEVEL of the allowance (screenkit.detect_grouping_level; never assumed)")
f["opp_team_season"] = f["opp_team_id"].astype(str) + "_" + f["season"].astype(str)
f["opp_team_season_game"] = f["opp_team_season"] + "_" + f["gid"]
f["player_season"] = f["player_id"].astype(str) + "_" + f["season"].astype(str)
gl = {}
for col in ["RA_OCc", "S_SPEC_RA"]:
    r = sk.detect_grouping_level(
        f.dropna(subset=[col]).assign(
            game=lambda d: d["gid"], team_season=lambda d: d["opp_team_season"]),
        col,
        candidate_keys={"opponent_team_season": ["opp_team_season"],
                        "opponent_team_season_game": ["opp_team_season_game"],
                        "game": ["gid"],
                        "player_season": ["player_season"],
                        "season": ["season"],
                        "opponent_team": ["opp_team_id"]},
        verbose=True)
    gl[col] = {k: v for k, v in r.items() if k != "levels"}
    gl[col]["levels"] = r.get("levels")
OUT["grouping_levels"] = gl

vs = sk.var_share_between(f.dropna(subset=["RA_OCc"]), "RA_OCc", "opp_team_season")
print("\n  var_share_between(RA_OCc, opp_team_season) = %s" % vs)
OUT["var_share_between_opp_team_season"] = vs

# ------------------------------------------------------------------ 9. save
keep = ["row_uid", "gid", "season", "player_id", "team_id", "opp_team_id", "gdate",
        "opp_team_season", "opp_team_season_game", "player_season", "stratum",
        "pl_games_prior", "pl_min_mean5",
        "y_pts", "y_minutes", "y_fga", "r_ppm", "r_ppf",
        "pts__pred_point", "minutes__pred_point", "fga__pred_point",
        "mdl_ppf", "mdl_ppm", "mdl_fpm",
        "ref_pts", "refA_ppm", "refB_ppm", "refA_ppf", "refB_ppf", "ref_minutes",
        "RA_w", "RA_OC", "RA_OCc", "RA_lg_prior_gap"] + sig_cols \
    + [c for c in f.columns if c.startswith(("ppf_cand_", "ppm_cand_", "pts_cand_"))]
out = f[keep].copy()
sk.assert_partition(out, verbose=False)
out.to_parquet(os.path.join(E.HERE, "eff_frame_v2.parquet"), index=False)
print("\n  wrote eff_frame_v2.parquet  shape=%s" % (out.shape,))
json.dump(OUT, open(os.path.join(E.HERE, "_s02.json"), "w"), indent=2, default=str)
print("DONE s02")
