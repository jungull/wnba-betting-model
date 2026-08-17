"""S02b -- MECHANISM.  What IS `pts__pred_cv` on the decision stratum?

POST-HOC.  This measurement was not named in the PREREG; it was forced by a singular matrix
in s03 and is reported as a mechanism probe, not as a preregistered test.  It belongs to
PART V ("how much of the signal is just this player scores more"), which WAS preregistered.

`<target>__pred_cv = <target>__pred_sd / <target>__pred_point` by construction.  If
`pred_sd` is constant on the arm then `pred_cv` is EXACTLY a reciprocal of the forecast level,
and any association it has with |residual| is a statement about scoring level and nothing else.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *  # noqa

rows = []
for arm, mask in ARM_MASKS.items():
    ss = seas[mask]
    for tgt in ("pts", "minutes", "fga"):
        for suff in ("pred_sd", "pred_point", "pred_cv", "pred_width", "pred_iqr"):
            nm = "%s__%s" % (tgt, suff)
            if nm not in NAME_IX:
                continue
            v = X[mask, NAME_IX[nm]]
            per = {int(s): int(len(np.unique(v[ss == s]))) for s in np.unique(ss)}
            rows.append(dict(arm=arm, column=nm, n=int(mask.sum()),
                             n_distinct_on_arm=int(len(np.unique(v))),
                             n_distinct_by_season=json.dumps(per),
                             sd_on_arm=float(v.std()),
                             largest_value_share=float(pd.Series(v).value_counts(
                                 normalize=True).iloc[0])))
D = pd.DataFrame(rows)
D.to_csv(os.path.join(HERE, "_PRED_COLUMN_DEGENERACY.csv"), index=False)
pd.set_option("display.width", 250)
print(D.to_string(index=False))

print("\n=== is pred_cv just 1 / pred_level on the decision stratum? ===")
mech = []
for arm, mask in ARM_MASKS.items():
    ss = seas[mask]
    for tgt in ("pts", "minutes", "fga"):
        cv = X[mask, NAME_IX["%s__pred_cv" % tgt]]
        pt = X[mask, NAME_IX["%s__pred_point" % tgt]]
        sd = X[mask, NAME_IX["%s__pred_sd" % tgt]]
        inv = np.where(pt != 0, 1.0 / np.where(pt == 0, np.nan, pt), np.nan)
        ok = np.isfinite(inv) & np.isfinite(cv)
        r_inv = float(np.corrcoef(cv[ok], inv[ok])[0, 1])
        # within-season correlation (the screen z-scores within season)
        ws = []
        for s in np.unique(ss):
            mm = ok & (ss == s)
            if mm.sum() > 20 and np.std(inv[mm]) > 0:
                ws.append(float(np.corrcoef(cv[mm], inv[mm])[0, 1]))
        ident = float(np.nanmax(np.abs(cv[ok] * pt[ok] - sd[ok])))
        mech.append(dict(arm=arm, target=tgt,
                         corr_pred_cv_vs_reciprocal_pred_point=r_inv,
                         within_season_corr_min=min(ws) if ws else np.nan,
                         within_season_corr_max=max(ws) if ws else np.nan,
                         max_abs_identity_residual_cv_times_point_minus_sd=ident,
                         corr_pred_cv_vs_pred_point=float(np.corrcoef(cv[ok], pt[ok])[0, 1])))
M = pd.DataFrame(mech)
M.to_csv(os.path.join(HERE, "_PRED_CV_MECHANISM.csv"), index=False)
print(M.round(6).to_string(index=False))

# --- substitute 1/pred_point for pred_cv in the two largest cells and re-measure
print("\n=== substituting 1 / pts__pred_point for pts__pred_cv (A4_CLEAN_DEC, base B0) ===")
ARM = "A4_CLEAN_DEC"
mask = ARM_MASKS[ARM]
ctx = arm_context(mask)
pt = X[mask, NAME_IX["pts__pred_point"]]
inv = 1.0 / np.where(pt == 0, np.nan, pt)
inv_z = np.nan_to_num(zwithin(inv, ctx["ss"]))
sub_rows = []
for dep in ("pts_absres", "pts_sqres", "fga_absres", "fga_sqres", "minutes_sqres"):
    yt = ctx["Yt"][dep]
    sst = ctx["SST"][dep]
    for tag, col in (("pts__pred_cv", ctx["Xza"][:, NAME_IX["pts__pred_cv"]]),
                     ("ONE_OVER_pts__pred_point", inv_z)):
        xt = ctx["dm"](col.reshape(-1, 1))[:, 0]
        b, t, d = t_and_dr2(yt, xt.reshape(-1, 1), ctx["df"], sst)
        sub_rows.append(dict(arm=ARM, base="B0", dependent=dep, carrier=tag,
                             signed_t=float(t[0]), dr2=float(d[0])))
SB = pd.DataFrame(sub_rows)
SB.to_csv(os.path.join(HERE, "_PRED_CV_SUBSTITUTION.csv"), index=False)
print(SB.round(6).to_string(index=False))
print("\nDONE s02b")
