"""STEP 3 -- THE EFFICIENCY CONTRAST, AND THE DECISIVE CUT.

HEADLINE TEST: screenkit.paired_forecast_comparison(y, candidate, baseline, groups).  This is a
forecast-vs-forecast contrast on the SAME rows with a WHOLE-CLUSTER SIGN-FLIP null, which is
exactly this question's shape.  `dr2_a_minus_b` is r2_of_forecast(cand) - r2_of_forecast(base)
to machine precision.

CLUSTER LEVEL.  s02 measured it rather than assuming it (constraint 6):
  * the CENTRED allowance RA_OCc is constant at `opponent_team_season_game` (1,466 groups) and
    68.2% of its variance is BETWEEN opponent-team-seasons (var_share_between = 0.6815);
  * the assembled signal S varies row by row, because the player mix w_z does.
So the headline p is taken at the COARSEST level the signal's variance actually lives at,
OPPONENT-TEAM-SEASON (36 clusters) -- the conservative choice.  Three finer levels and the naive
ROW-LEVEL null are reported beside it so the inflation factor is visible.  Cluster-robust SEs are
NOT used as a substitute anywhere.

SKILL, NOT MAE (D076).  Every row set is also scored as skill = 1 - MAE/MAE_ref against the
MATCHED point-in-time prior-mean reference refA (mean of the player's own prior per-game rates),
with refB (ratio of prior sums) reported beside it.  Raw MAE reduction is never a verdict.

THE DECISIVE CUT.  Everything is reported three ways: ALL scoreable rows, ON the decision-relevant
stratum (>=8 prior appearances AND trailing-5 minutes >=24), and OFF it.  D081 already showed a
free running-mean splice fixes cold-start rows, so an improvement concentrated OFF the stratum is
redundant with a cheaper remedy and is worth little.
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

pd.set_option("display.width", 300)
pd.set_option("display.max_columns", 80)
OUT = {}
N_DRAWS = 5000

f = pd.read_parquet(os.path.join(E.HERE, "eff_frame_v2.parquet"))
sk.assert_partition(f, verbose=True)

RESP = {
    "ppm_points_per_minute": dict(y="r_ppm", base="mdl_ppm", cand="ppm_cand_%s",
                                  refA="refA_ppm", refB="refB_ppm"),
    "ppf_points_per_FGA": dict(y="r_ppf", base="mdl_ppf", cand="ppf_cand_%s",
                               refA="refA_ppf", refB="refB_ppf"),
}
SPEC_ORDER = ["SPEC_RA", "SPEC_ALL5_GLOBAL", "SPEC_ALL5_PERZONE",
              "SPEC_RA_UNCENTRED", "SPEC_ALL5_GLOBAL_UNCENTRED", "SPEC_ALL5_PERZONE_UNCENTRED",
              "SPEC_RA_XSCENTRED", "SPEC_ALL5_GLOBAL_XSCENTRED", "SPEC_ALL5_PERZONE_XSCENTRED"]
PRIMARY = ("ppm_points_per_minute", "SPEC_RA")
STRATA = [("all", None), ("on_stratum", True), ("off_stratum", False)]
CLUSTERS = [("opponent_team_season", "opp_team_season"),
            ("opponent_team_season_game", "opp_team_season_game"),
            ("game", "gid"),
            ("player_season", "player_season")]

rows, paired_detail, draws_store = [], {}, {}

E.hdr("S03 -- EFFICIENCY CONTRAST (paired, clustered).  CENTRED specs are the only headlines.")
for rname, spec in RESP.items():
    for sp in SPEC_ORDER:
        ccol = spec["cand"] % sp
        for stag, sval in STRATA:
            m = np.isfinite(f[spec["y"]]) & np.isfinite(f[spec["base"]]) & np.isfinite(f[ccol]) \
                & np.isfinite(f[spec["refA"]]) & np.isfinite(f[spec["refB"]])
            if sval is not None:
                m = m & (f["stratum"] == sval)
            sub = f[m]
            if len(sub) < 100:
                continue
            y = sub[spec["y"]].to_numpy(float)
            b = sub[spec["base"]].to_numpy(float)
            c = sub[ccol].to_numpy(float)
            ra = sub[spec["refA"]].to_numpy(float)
            rb = sub[spec["refB"]].to_numpy(float)
            head = sk.paired_forecast_comparison(y, c, b, sub["opp_team_season"].to_numpy(),
                                                 n_draws=N_DRAWS, seed=E.SEED,
                                                 name_a="candidate", name_b="champion_baseline")
            rec = dict(response=rname, spec=sp, stratum=stag, n=int(head["n"]),
                       centred=("UNCENTRED" not in sp),
                       r2_baseline=float(head["r2_b"]), r2_candidate=float(head["r2_a"]),
                       dR2_cand_minus_base=float(head["dr2_a_minus_b"]),
                       p_cluster_opp_team_season=float(head["p"]),
                       n_clusters=int(head["n_groups"]),
                       p_row_level_NAIVE=float(head["p_row_level_NAIVE"]),
                       inflation_cluster_over_row=float(head["inflation"]),
                       skill_base_vs_refA=E.skill(y, b, ra)[0],
                       skill_cand_vs_refA=E.skill(y, c, ra)[0],
                       skill_base_vs_refB=E.skill(y, b, rb)[0],
                       skill_cand_vs_refB=E.skill(y, c, rb)[0],
                       mae_base=E.mae(y, b), mae_cand=E.mae(y, c), mae_refA=E.mae(y, ra))
            rec["d_skill_vs_refA"] = rec["skill_cand_vs_refA"] - rec["skill_base_vs_refA"]
            # all cluster levels
            for cname, ccol2 in CLUSTERS:
                h = sk.paired_forecast_comparison(y, c, b, sub[ccol2].to_numpy(),
                                                  n_draws=N_DRAWS, seed=E.SEED)
                rec["p_" + cname] = float(h["p"])
                rec["nclust_" + cname] = int(h["n_groups"])
            rows.append(rec)
            key = "%s|%s|%s" % (rname, sp, stag)
            paired_detail[key] = {k: v for k, v in head.items() if k != "draws"}
            if (rname, sp) == PRIMARY:
                draws_store[key] = head["draws"]

R = pd.DataFrame(rows)
R.to_csv(os.path.join(E.HERE, "efficiency_contrast.csv"), index=False)

E.hdr("S03.1 -- HEADLINE: per-minute efficiency, SPEC_RA (the D074 cell that actually survived)")
show = ["stratum", "n", "r2_baseline", "r2_candidate", "dR2_cand_minus_base",
        "p_cluster_opp_team_season", "n_clusters", "p_row_level_NAIVE",
        "inflation_cluster_over_row", "skill_base_vs_refA", "skill_cand_vs_refA",
        "d_skill_vs_refA"]
h = R[(R["response"] == PRIMARY[0]) & (R["spec"] == PRIMARY[1])]
print(h[show].to_string(index=False))

E.hdr("S03.2 -- the same contrast for points-per-FGA, SPEC_RA")
print(R[(R["response"] == "ppf_points_per_FGA") & (R["spec"] == "SPEC_RA")][show]
      .to_string(index=False))

E.hdr("S03.3 -- ALL specs x strata, dR2 and the cluster p (CENTRED rows are the only headlines)")
comp = ["response", "spec", "centred", "stratum", "n", "dR2_cand_minus_base",
        "p_cluster_opp_team_season", "d_skill_vs_refA"]
print(R[comp].to_string(index=False))

E.hdr("S03.4 -- p AT EVERY CLUSTER LEVEL, primary cell only (constraint 6: inflation visible)")
pc = ["stratum", "n", "dR2_cand_minus_base"] + \
     [c for c in R.columns if c.startswith("p_") or c.startswith("nclust_")]
print(h[pc].to_string(index=False))

# ------------------------------------------------------------------ noop placebo
E.hdr("S03.5 -- screenkit.noop_placebo (constraint 10): is the control vacuous?")
primary_spec = RESP[PRIMARY[0]]
ccol = primary_spec["cand"] % PRIMARY[1]
m = np.isfinite(f[primary_spec["y"]]) & np.isfinite(f[primary_spec["base"]]) \
    & np.isfinite(f[ccol]) & (f["stratum"])
sub = f[m].reset_index(drop=True)


def stat_dr2(d):
    return float(sk.r2_of_forecast(d["r_ppm"].to_numpy(float), d["_cand"].to_numpy(float))
                 - sk.r2_of_forecast(d["r_ppm"].to_numpy(float), d["mdl_ppm"].to_numpy(float)))


sub["_cand"] = sub[ccol]
placebo_identity = sk.noop_placebo(stat_dr2, sub, n_draws=200, transform=None, verbose=True)


def relabel_and_recompute(d, rng):
    """The CLASSIC DEFECTIVE placebo: permute the opponent key and rebuild the row's own signal
    from the permuted key.  Tested here explicitly to show it IS a no-op and was not used."""
    d2 = d.copy()
    perm = rng.permutation(d2["opp_team_season"].to_numpy())
    d2["opp_team_season"] = perm
    mu = d2.groupby("opp_team_season", sort=False)["S_SPEC_RA"].transform("mean")
    d2["_cand"] = d2["mdl_ppm"] + (d2["S_SPEC_RA"] - mu + mu) * d2["mdl_fpm"]
    return d2


placebo_relabel = sk.noop_placebo(stat_dr2, sub, n_draws=200, transform=relabel_and_recompute,
                                  verbose=True)
for tag, r in [("identity", placebo_identity), ("relabel_key_and_recompute", placebo_relabel)]:
    print("  noop_placebo[%s]: real=%.10e  observed sd=%.6e  n_distinct=%s  is_noop=%s"
          % (tag, r["real"], r["sd"], r.get("n_distinct"), r["is_noop"]))
OUT["noop_placebo"] = {
    "identity": {k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
                 for k, v in placebo_identity.items() if k != "draws"},
    "relabel_key_and_recompute": {k: (float(v) if isinstance(v, (int, float, np.floating))
                                      else str(v))
                                  for k, v in placebo_relabel.items() if k != "draws"}}

# ------------------------------------------------------------------ save draws
dd = pd.DataFrame({k: v for k, v in draws_store.items()})
dd.to_csv(os.path.join(E.HERE, "permutation_draws_paired_cluster.csv"), index=False)
print("\n  wrote permutation_draws_paired_cluster.csv  (%d draws x %d primary cells)" % dd.shape)

OUT["contrast_table"] = R.to_dict(orient="records")
OUT["paired_detail"] = paired_detail
OUT["n_draws"] = N_DRAWS
json.dump(OUT, open(os.path.join(E.HERE, "_s03.json"), "w"), indent=2, default=str)
print("DONE s03")
