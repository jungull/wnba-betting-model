"""STEP 2b/3/4 -- THE FORECAST CONTRAST, THE DECISIVE STRATUM CUT, AND THE POINTS CEILING.

HEADLINE TEST is screenkit.paired_forecast_comparison: candidate vs baseline on the SAME rows,
paired squared-loss difference, null by sign-flipping WHOLE CLUSTERS.  The clustering level is
chosen by screenkit.detect_grouping_level rather than assumed, and the naive row-level null is
reported beside it so the inflation factor is visible (seven confirmations in this program that
the row-level null is anticonservative; cluster-robust SEs are NOT a substitute -- three
confirmations -- and none is reported here as one).

SKILL is always 1 - MAE_model/MAE_reference with the reference facing THE SAME ROWS (D076: one
prior candidate cut MAE 9.9% while moving skill by +0.00007).  Raw MAE reduction is never a verdict.

R2 convention D069: plain unweighted, SST about the unweighted mean.  Forecasts already in hand are
scored with screenkit.r2_of_forecast, NOT r2_plain (which refits and would flatter both sides).
"""
import json
import os

import numpy as np
import pandas as pd

import et_base as E
import screenkit as sk

pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 80)

OUT = {}
NDRAWS = 5000

f = pd.read_parquet(os.path.join(E.HERE, "efficiency_frame.parquet"))
sk.assert_partition(f, verbose=True)
f["opp_team_season"] = f["OPP_TEAM_ID"].astype(str) + "_" + f["season"].astype(str)
f["player_season"] = f["player_id"].astype(str) + "_" + f["season"].astype(str)
f["player_game"] = f["player_id"].astype(str) + "_" + f["game_id"].astype(str)

gp = f["pl_games_prior"].to_numpy(float)
m5 = f["pl_min_mean5"].to_numpy(float)
M_DEC = (gp >= 8) & (m5 >= 24)
M_OFF = ~M_DEC
STRATA = [("DECISION-RELEVANT (>=8 prior, trail5 min >=24)", M_DEC),
          ("OFF-STRATUM (everything else)", M_OFF),
          ("POOLED", np.ones(len(f), bool))]
print("\n  strata sizes: decision-relevant=%d (%.1f%%)  off=%d  pooled=%d"
      % (M_DEC.sum(), 100 * M_DEC.mean(), M_OFF.sum(), len(f)))

SPECS = [("A", "HEADLINE  RA-only, frozen D074 slope, league-centred"),
         ("B", "sensitivity  five zones, one global slope"),
         ("C", "sensitivity  five zones, per-zone frozen betas (OPTIMISTIC, in-sample coefs)"),
         ("U", "sensitivity  RA-only UNCENTRED (carries the league zone level -- mis-calibrated)")]

# ================================================================ 1. THE GROUPING LEVEL ==========
E.hdr("S03.1 -- WHICH LEVEL IS THE NULL AT?  (detect_grouping_level, not an assumption)")
KEYS = {"row": None, "player_game": ["player_id", "game_id"], "game": ["game_id"],
        "opp_team_season": ["OPP_TEAM_ID", "season"], "team_season": ["team_id", "season"],
        "player_season": ["player_id", "season"], "season": ["season"]}
lvl_info = {}
for col in ["OC__Restricted Area", "adjA_ppf"]:
    lv = sk.detect_grouping_level(f, col, candidate_keys=KEYS, verbose=True)
    lvl_info[col] = {k: v for k, v in lv.items() if k != "levels"}
    lvl_info[col]["levels"] = {k: {kk: (float(vv) if isinstance(vv, (int, float, np.floating))
                                        else vv) for kk, vv in v.items()}
                               for k, v in lv["levels"].items()}
    print("    status=%s  recommended=%s" % (lv["status"], lv["recommended_permutation_level"]))
vsb = {k: float(sk.var_share_between(f, "adjA_ppf", k))
       for k in ["opp_team_season", "game_id", "player_season"]}
print("\n  var_share_between(adjA_ppf, .) : %s" % {k: round(v, 4) for k, v in vsb.items()})
print("""
  READING.  The OPPONENT ALLOWANCE OC is constant within (opponent-team, game) and varies slowly
  within an opponent-team-season.  The ADJUSTMENT adjA_ppf multiplies it by a PLAYER-specific
  prior mix, so it varies row by row and no coarser level is exactly constant -- detect_grouping_
  level therefore returns None for it, which is the kit refusing to endorse the row null (P2).
  The correct clustering for the PAIRED test comes from the OUTCOME side, which detect_grouping_
  level explicitly does not inspect: the candidate-minus-baseline loss difference is driven by one
  opponent-team-season allowance series shared by every player who faced that team, so
  OPPONENT-TEAM-SEASON is the coarsest defensible level and is the headline.  Game and
  player-season are reported beside it, and the row-level null is reported ONLY as the
  anticonservative contrast with its inflation factor.""")
OUT["grouping_levels"] = lvl_info
OUT["var_share_between_adjA"] = vsb

# ================================================================ 2. THE EFFICIENCY CONTRAST =====
E.hdr("S03.2 -- EFFICIENCY CONTRAST.  Candidate vs the champion's own implied efficiency.")


def contrast(mask, target, tag, cluster_col="opp_team_season", n_draws=NDRAWS, ref="refA"):
    """One candidate-vs-baseline comparison on one row set, scored every way that matters."""
    ycol = {"ppf": "y_ppf", "ppm": "y_ppm", "pts": "y_pts"}[target]
    bcol = {"ppf": "base_ppf", "ppm": "base_ppm", "pts": "pts__pred_point"}[target]
    rcol = {"ppf": ref + "_ppf", "ppm": ref + "_ppm", "pts": "ref_pts"}[target]
    ccol = "cand%s_%s" % (tag, target)
    d = f.loc[mask, [ycol, bcol, ccol, rcol, cluster_col]].dropna()
    y = d[ycol].to_numpy(float)
    b = d[bcol].to_numpy(float)
    c = d[ccol].to_numpy(float)
    r = d[rcol].to_numpy(float)
    pc = sk.paired_forecast_comparison(y, c, b, groups=d[cluster_col].to_numpy(),
                                       n_draws=n_draws, seed=E.SEED,
                                       name_a="candidate_" + tag, name_b="champion_baseline")
    s_b, mae_b, mae_r = E.skill(y, b, r)
    s_c = E.skill(y, c, r)[0]
    return dict(target=target, spec=tag, n=int(len(d)), cluster=cluster_col, reference=rcol,
                r2_baseline=float(sk.r2_of_forecast(y, b)),
                r2_candidate=float(sk.r2_of_forecast(y, c)),
                dr2_candidate_minus_baseline=float(pc["dr2_a_minus_b"]),
                mae_baseline=mae_b, mae_candidate=E.mae(y, c), mae_reference=mae_r,
                skill_baseline=s_b, skill_candidate=s_c, d_skill=float(s_c - s_b),
                p_two_sided_cluster=float(pc["p"]), n_clusters=int(pc["n_groups"]),
                null_sd_cluster=float(pc["sd"]),
                p_row_level_NAIVE=float(pc["p_row_level_NAIVE"]),
                inflation_cluster_over_row=float(pc["inflation"]),
                _draws=pc["draws"])


rows = []
draws_store = {}
for target in ["ppf", "ppm"]:
    print("\n  ================ TARGET: %s  (%s) ================"
          % (target, {"ppf": "points per field-goal attempt",
                      "ppm": "points per minute"}[target]))
    print("  %-46s %-4s %6s %11s %11s %11s %11s %9s %9s %8s"
          % ("stratum", "spec", "n", "R2 base", "R2 cand", "dR2", "d skill", "p clus", "p row",
             "infl"))
    for lbl, m in STRATA:
        for tag, _desc in SPECS:
            r = contrast(m, target, tag)
            r["stratum"] = lbl
            draws_store[(target, lbl, tag)] = r.pop("_draws")
            rows.append(r)
            print("  %-46s %-4s %6d %11.6f %11.6f %+11.3e %+11.3e %9.4f %9.4f %8.2f"
                  % (lbl, tag, r["n"], r["r2_baseline"], r["r2_candidate"],
                     r["dr2_candidate_minus_baseline"], r["d_skill"], r["p_two_sided_cluster"],
                     r["p_row_level_NAIVE"], r["inflation_cluster_over_row"]))
R = pd.DataFrame(rows)
R.to_csv(os.path.join(E.HERE, "efficiency_contrast.csv"), index=False)
OUT["efficiency_contrast"] = R.to_dict("records")

E.hdr("S03.2b -- THE HEADLINE LINE, STATED ALONE")
h = R[(R["target"] == "ppf") & (R["spec"] == "A")
      & (R["stratum"] == STRATA[0][0])].iloc[0].to_dict()
h_ppm = R[(R["target"] == "ppm") & (R["spec"] == "A")
          & (R["stratum"] == STRATA[0][0])].iloc[0].to_dict()
print("""
  DECISION-RELEVANT STRATUM (>=8 prior same-season appearances AND trailing-5 mean minutes >=24)
  SPEC A -- the faithful transfer of the D074 slope that actually survived multiplicity.

    POINTS PER FGA        n = %d   clusters = %d (opponent-team-season)
      R2 champion baseline      = %+.6f
      R2 candidate              = %+.6f
      dR2 candidate - baseline  = %+.3e
      skill vs prior-mean ref   : baseline %+.5f -> candidate %+.5f   (delta %+.3e)
      p (cluster sign-flip, %d draws) = %.4f      p (row-level, ANTICONSERVATIVE) = %.4f
      null sd inflation cluster/row   = %.2fx

    POINTS PER MINUTE     n = %d
      dR2 candidate - baseline  = %+.3e     p (cluster) = %.4f
""" % (h["n"], h["n_clusters"], h["r2_baseline"], h["r2_candidate"],
       h["dr2_candidate_minus_baseline"], h["skill_baseline"], h["skill_candidate"], h["d_skill"],
       NDRAWS, h["p_two_sided_cluster"], h["p_row_level_NAIVE"],
       h["inflation_cluster_over_row"], h_ppm["n"], h_ppm["dr2_candidate_minus_baseline"],
       h_ppm["p_two_sided_cluster"]))
OUT["headline_ppf_decision_stratum"] = h
OUT["headline_ppm_decision_stratum"] = h_ppm

E.hdr("S03.2c -- ALTERNATIVE CLUSTERING LEVELS FOR THE HEADLINE (robustness of the null, not of "
      "the effect)")
alt = []
print("  %-18s %8s %11s %9s %9s" % ("cluster", "clusters", "dR2", "p", "null sd"))
for cl in ["opp_team_season", "game_id", "player_season", "player_game", sk.ROW_LEVEL]:
    if cl == sk.ROW_LEVEL:
        d = f.loc[M_DEC, ["y_ppf", "base_ppf", "candA_ppf"]].dropna()
        pc = sk.paired_forecast_comparison(d["y_ppf"], d["candA_ppf"], d["base_ppf"],
                                           groups=sk.ROW_LEVEL, n_draws=NDRAWS, seed=E.SEED)
    else:
        d = f.loc[M_DEC, ["y_ppf", "base_ppf", "candA_ppf", cl]].dropna()
        pc = sk.paired_forecast_comparison(d["y_ppf"], d["candA_ppf"], d["base_ppf"],
                                           groups=d[cl].to_numpy(), n_draws=NDRAWS, seed=E.SEED)
    alt.append(dict(cluster=str(cl), n_clusters=int(pc["n_groups"]),
                    dr2=float(pc["dr2_a_minus_b"]), p=float(pc["p"]), null_sd=float(pc["sd"])))
    print("  %-18s %8d %+11.3e %9.4f %9.3e"
          % (cl, pc["n_groups"], pc["dr2_a_minus_b"], pc["p"], pc["sd"]))
OUT["alternative_clusterings_headline"] = alt

E.hdr("S03.2d -- SAME CONTRAST AGAINST REF-B (ratio of prior sums, a HARDER reference)")
refb = []
for lbl, m in STRATA:
    r = contrast(m, "ppf", "A", ref="refB")
    r.pop("_draws")
    r["stratum"] = lbl
    refb.append(r)
    print("  %-46s n=%5d  skill base %+.5f -> cand %+.5f  (d %+.3e)  p=%.4f"
          % (lbl, r["n"], r["skill_baseline"], r["skill_candidate"], r["d_skill"],
             r["p_two_sided_cluster"]))
OUT["refB_contrast_ppf"] = refb

# ============================================================ 3. SIGNAL-ONLY ROWS ================
E.hdr("S03.3 -- RESTRICTED TO ROWS THAT ACTUALLY CARRY A SIGNAL (candidate != champion)")
print("""  2,598 of 13,879 rows have no usable RA signal, so the candidate IS the champion there and
  those rows can only dilute.  The contrast is repeated on rows where the adjustment is nonzero.""")
sig = f["has_signal"].to_numpy(bool)
sigrows = []
for lbl, m in [("DECISION-RELEVANT & has_signal", M_DEC & sig),
               ("OFF-STRATUM & has_signal", M_OFF & sig),
               ("POOLED & has_signal", sig)]:
    r = contrast(m, "ppf", "A")
    r.pop("_draws")
    r["stratum"] = lbl
    sigrows.append(r)
    print("  %-34s n=%5d  dR2=%+.3e  d skill=%+.3e  p=%.4f (clusters %d)"
          % (lbl, r["n"], r["dr2_candidate_minus_baseline"], r["d_skill"],
             r["p_two_sided_cluster"], r["n_clusters"]))
OUT["signal_rows_only"] = sigrows

# ============================================================ 4. NOOP PLACEBO =====================
E.hdr("S03.4 -- NOOP PLACEBO (kit guard: is the control secretly the identity?)")


def stat_dr2(d):
    y = d["y_ppf"].to_numpy(float)
    return float(sk.r2_of_forecast(y, d["candA_ppf"].to_numpy(float))
                 - sk.r2_of_forecast(y, d["base_ppf"].to_numpy(float)))


dec = f.loc[M_DEC, ["y_ppf", "base_ppf", "candA_ppf", "adjA_ppf", "opp_team_season"]].dropna()
np_id = sk.noop_placebo(stat_dr2, dec, 200, transform=None, verbose=True)
print("  identity placebo   : observed sd = %.3e   distinct draw values = %d   is_noop = %s"
      % (np_id["sd"], np_id["n_distinct_draw_values"], np_id["is_noop"]))


def relabel_cluster_and_recompute(d, rng):
    """The classic DEFECTIVE placebo: permute the cluster key and recompute.  The statistic does
    not read the key at all, so this must come back as a confirmed no-op."""
    d2 = d.copy()
    d2["opp_team_season"] = rng.permutation(d2["opp_team_season"].to_numpy())
    return d2


np_relabel = sk.noop_placebo(stat_dr2, dec, 200, transform=relabel_cluster_and_recompute)
print("  relabel-key placebo: observed sd = %.3e   is_noop = %s  <- confirmed vacuous, as expected"
      % (np_relabel["sd"], np_relabel["is_noop"]))


def real_shuffle(d, rng):
    """A GENUINE control: reassign the adjustment across rows and rebuild the candidate."""
    d2 = d.copy()
    d2["candA_ppf"] = d2["base_ppf"] + rng.permutation(d2["adjA_ppf"].to_numpy())
    return d2


np_real = sk.noop_placebo(stat_dr2, dec, 200, transform=real_shuffle)
print("  genuine shuffle    : observed sd = %.3e   is_noop = %s  <- correctly NOT flagged"
      % (np_real["sd"], np_real["is_noop"]))
OUT["noop_placebo"] = dict(
    identity=dict(sd=float(np_id["sd"]), is_noop=bool(np_id["is_noop"]),
                  n_distinct=int(np_id["n_distinct_draw_values"]), real=float(np_id["real"])),
    relabel_key=dict(sd=float(np_relabel["sd"]), is_noop=bool(np_relabel["is_noop"])),
    genuine_shuffle=dict(sd=float(np_real["sd"]), is_noop=bool(np_real["is_noop"])))

# ============================================================ 5. POINTS PROPAGATION ==============
E.hdr("S03.5 -- PROPAGATE TO POINTS: efficiency x the champion's OWN minutes forecast")
print("""  points_candidate = (base_ppm + adj_ppf * mdl_fpm) * minutes_pred
                   = pts_pred + adj_ppf * fga_pred        (exactly -- the champion's own minutes
  and attempts forecasts are reused unchanged; nothing is refitted and the champion is not touched).""")
pts_rows = []
print("\n  %-46s %-4s %6s %11s %11s %11s %9s %9s"
      % ("stratum", "spec", "n", "R2 base", "R2 cand", "dR2", "d skill", "p clus"))
for lbl, m in STRATA:
    for tag, _ in SPECS:
        r = contrast(m, "pts", tag)
        r.pop("_draws")
        r["stratum"] = lbl
        pts_rows.append(r)
        print("  %-46s %-4s %6d %11.6f %11.6f %+11.3e %+11.3e %9.4f"
              % (lbl, tag, r["n"], r["r2_baseline"], r["r2_candidate"],
                 r["dr2_candidate_minus_baseline"], r["d_skill"], r["p_two_sided_cluster"]))
P = pd.DataFrame(pts_rows)
P.to_csv(os.path.join(E.HERE, "points_contrast.csv"), index=False)
OUT["points_contrast"] = P.to_dict("records")

E.hdr("S03.6 -- THE ARITHMETIC CEILING FOR THIS CHANNEL (D079's convention)")
print("""  D079 killed the SHOT-MIX channel by showing that even a PERFECT mix term could buy at most
  dR2 = 0.00113, because reallocating attempts at constant volume cannot move enough points.  That
  ceiling does NOT apply to conversion -- converting better is not reallocating -- so the ceiling
  has to be recomputed from scratch for this channel.  Same convention as D079:
      dR2 <= (sd of the points adjustment / sd of the points response)^2
  i.e. the ceiling if the adjustment term were a PERFECT predictor of the residual and orthogonal
  to the champion's own forecast.""")
ceil = []
for lbl, m in STRATA:
    d = f.loc[m, ["y_pts", "adjA_ppf", "adjB_ppf", "adjC_ppf", "fga__pred_point",
                  "pts__pred_point"]].dropna()
    sd_y = float(d["y_pts"].std())
    row = dict(stratum=lbl, n=int(len(d)), sd_points_response=sd_y)
    for tag in ["A", "B", "C"]:
        dpts = (d["adj%s_ppf" % tag] * d["fga__pred_point"]).to_numpy(float)
        sd_t = float(np.std(dpts, ddof=1))
        row["sd_points_adjustment_" + tag] = sd_t
        row["one_sd_signal_moves_points_" + tag] = sd_t
        row["ceiling_dR2_" + tag] = float((sd_t / sd_y) ** 2)
    ceil.append(row)
    print("\n  %s  (n=%d, sd(points)=%.4f)" % (lbl, len(d), sd_y))
    for tag in ["A", "B", "C"]:
        print("    spec %s : 1 sd of the signal moves the points forecast by %.4f points ; "
              "ceiling dR2 <= %.3e"
              % (tag, row["sd_points_adjustment_" + tag], row["ceiling_dR2_" + tag]))
C = pd.DataFrame(ceil)
C.to_csv(os.path.join(E.HERE, "arithmetic_ceiling.csv"), index=False)
OUT["arithmetic_ceiling"] = ceil

# ============================================================ 6. DRAWS ============================
E.hdr("S03.7 -- WRITE PERMUTATION DRAWS")
dr = []
for (target, lbl, tag), v in draws_store.items():
    dr.append(pd.DataFrame({"target": target, "stratum": lbl, "spec": tag,
                            "draw_index": np.arange(len(v)), "value": v}))
DR = pd.concat(dr, ignore_index=True)
DR.to_csv(os.path.join(E.HERE, "permutation_draws_paired_cluster.csv"), index=False)
print("  wrote permutation_draws_paired_cluster.csv  (%d rows, %d contrasts x %d draws)"
      % (len(DR), len(draws_store), NDRAWS))

json.dump(OUT, open(os.path.join(E.HERE, "_s03.json"), "w"), indent=2, default=str)
print("DONE s03")
