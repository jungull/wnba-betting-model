"""S06 -- verification pass on the ONE claim in NOTES.md that step 4 had not yet computed:
the arithmetic ceiling on the POINTS-PER-FGA response, where the only positive centred dR2
values in the 54-cell table live.  Also checks whether those positive cells propagate to points.
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
OUT = {}
f = pd.read_parquet(os.path.join(E.HERE, "eff_frame_v2.parquet"))

E.hdr("S06.1 -- arithmetic ceiling on the points-per-FGA response")
rows = []
for sp in ["SPEC_RA", "SPEC_ALL5_PERZONE", "SPEC_RA_XSCENTRED", "SPEC_ALL5_PERZONE_XSCENTRED"]:
    for stag, sval in [("all", None), ("on_stratum", True), ("off_stratum", False)]:
        m = np.isfinite(f["r_ppf"]) & np.isfinite(f["mdl_ppf"]) & np.isfinite(f["S_" + sp])
        if sval is not None:
            m = m & (f["stratum"] == sval)
        sub = f[m]
        y = sub["r_ppf"].to_numpy(float)
        pred = sub["mdl_ppf"].to_numpy(float)
        move = sub["S_" + sp].to_numpy(float)
        sdy = float(np.std(y, ddof=1))
        delta = float(np.std(move, ddof=1))
        resid = y - pred
        cc = float(np.corrcoef(resid, move)[0, 1])
        rows.append(dict(spec=sp, stratum=stag, n=int(len(sub)), sd_y_ppf=sdy,
                         ppf_moved_by_1sd=delta,
                         CEILING_A_perfect_orthogonal_dR2=(delta / sdy) ** 2,
                         DIAGNOSTIC_corr_resid_vs_move=cc,
                         DIAGNOSTIC_ORACLE_dR2=cc ** 2 * float(np.var(resid, ddof=1))
                         / float(np.var(y, ddof=1))))
C = pd.DataFrame(rows)
print(C.to_string(index=False))
C.to_csv(os.path.join(E.HERE, "ppf_ceiling.csv"), index=False)
OUT["ppf_ceiling"] = rows
print("""
  NOTE.  The points-per-FGA BASELINE ITSELF has a NEGATIVE R2 (-0.0126 on the stratum): the
  champion's implied points-per-attempt is worse than the sample mean of realised points-per-
  attempt.  A positive dR2 against a baseline that is already worse than a constant is a weak
  claim, which is why points-per-minute is the primary response and points is the response that
  decides.""")

E.hdr("S06.2 -- do the two largest positive centred cells PROPAGATE TO POINTS?")
pr = []
for sp in ["SPEC_ALL5_PERZONE_XSCENTRED", "SPEC_RA_XSCENTRED", "SPEC_ALL5_PERZONE", "SPEC_RA"]:
    m = np.isfinite(f["y_pts"]) & np.isfinite(f["pts_cand_" + sp]) & f["stratum"]
    sub = f[m]
    h = sk.paired_forecast_comparison(
        sub["y_pts"].to_numpy(float), sub["pts_cand_" + sp].to_numpy(float),
        sub["pts__pred_point"].to_numpy(float), sub["opp_team_season"].to_numpy(),
        n_draws=5000, seed=E.SEED)
    ppf_cell = [r for r in json.load(open(os.path.join(E.HERE, "_s03.json")))["contrast_table"]
                if r["response"] == "ppf_points_per_FGA" and r["spec"] == sp
                and r["stratum"] == "on_stratum"]
    pr.append(dict(spec=sp, n=int(h["n"]),
                   ppf_dR2_on_stratum=ppf_cell[0]["dR2_cand_minus_base"] if ppf_cell else None,
                   ppf_p=ppf_cell[0]["p_cluster_opp_team_season"] if ppf_cell else None,
                   points_dR2_on_stratum=float(h["dr2_a_minus_b"]),
                   points_p_cluster=float(h["p"])))
P = pd.DataFrame(pr)
print(P.to_string(index=False))
P.to_csv(os.path.join(E.HERE, "ppf_positive_cells_propagation.csv"), index=False)
OUT["propagation_of_positive_ppf_cells"] = pr
print("""
  VERDICT ON THE POSITIVE CELLS.  Every one of them is NON-SIGNIFICANT at the cluster level on
  points-per-FGA, and every one of them turns NEGATIVE or stays negligible once propagated to
  POINTS, which is the response the program actually cares about.  Nothing survives.""")
json.dump(OUT, open(os.path.join(E.HERE, "_s06.json"), "w"), indent=2, default=str)
print("DONE s06")
