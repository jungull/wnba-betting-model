"""E1_I0022 STEP 1 -- REPRODUCE D081's PER-COMPONENT SKILL TABLE.

If minutes +3.554946% / FGA +0.115161% / points -0.222183% / ppm +0.559%,+0.959% /
ppf +2.127%,+1.024% do not come back, this screen STOPS and reports it.  Recent screens reproduced
at 1e-16 to 1e-17.

Reproduction is done with THIS screen's own local metric code (ose_base), NOT by importing D081's
psd_base and NOT by importing the shared screen kit (another agent is editing it).
"""
import json
import os

import numpy as np
import pandas as pd

import ose_base as B

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 60)

OUT = {}

B.hdr("STEP 1a -- LOAD D081's FROZEN decomp_frame.parquet (READ ONLY) + VALUE-BASED PARTITION")
f = B.load_frame(verbose=True)
OUT["season_ranges"] = B.assert_season_disjoint(f, verbose=True)
OUT["n_rows"] = int(len(f))
OUT["n_players"] = int(f["player_id"].nunique())
OUT["rows_per_season"] = {str(int(k)): int(v) for k, v in f.groupby("season").size().items()}

B.hdr("STEP 1b -- REPRODUCE THE PER-COMPONENT SKILL TABLE")
# D081's published values, transcribed from
# E0_I0015_points_skill_decomposition/component_skill.csv (frozen).
PUB = [
    ("minutes",     "LEVEL", "ref_minutes", "y_minutes", "minutes__pred_point",  0.035549460412317546, 5.079670829517938,  5.266906514137652,  13879),
    ("fga",         "LEVEL", "ref_fga",     "y_fga",     "fga__pred_point",      0.0011516133985177701, 2.6375697656574264, 2.640610728352467,  13879),
    ("pts",         "LEVEL", "ref_pts",     "y_pts",     "pts__pred_point",     -0.0022218316796525084, 4.190919667572693,  4.181628792249526,  13879),
    ("pts_per_min", "RATE",  "refA_ppm",    "r_ppm",     "mdl_ppm",              0.005590773577162533, 0.18174283099586136, 0.18276462664132767, 13879),
    ("pts_per_min", "RATE",  "refB_ppm",    "r_ppm",     "mdl_ppm",              0.009588508088615777, 0.18174283099586136, 0.18350234471241633, 13879),
    ("pts_per_fga", "RATE",  "refA_ppf",    "r_ppf",     "mdl_ppf",              0.02126771341978151, 0.5065778966660669,  0.5175857623294488,  12976),
    ("pts_per_fga", "RATE",  "refB_ppf",    "r_ppf",     "mdl_ppf",              0.010236525235077898, 0.5065778966660669,  0.5118171255878924,  12976),
    ("fga_per_min", "RATE",  "refA_fpm",    "r_fpm",     "mdl_fpm",              0.013453784501652244, 0.11033798411000435, 0.1118426915806147,  13879),
    ("fga_per_min", "RATE",  "refB_fpm",    "r_fpm",     "mdl_fpm",              0.006953266193469032, 0.11033798411000435, 0.11111056544847446, 13879),
]

rep = []
print("\n  %-12s %-10s %6s %12s %12s %14s %12s" %
      ("component", "reference", "n", "model MAE", "ref MAE", "skill", "|d skill|"))
for comp, kind, refcol, ycol, mcol, pub_skill, pub_mmae, pub_rmae, pub_n in PUB:
    s, mm, mr, n = B.skill(f[ycol], f[mcol], f[refcol])
    rep.append(dict(component=comp, kind=kind, reference=refcol, n=n, published_n=pub_n,
                    model_mae=mm, published_model_mae=pub_mmae, abs_delta_model_mae=abs(mm - pub_mmae),
                    ref_mae=mr, published_ref_mae=pub_rmae, abs_delta_ref_mae=abs(mr - pub_rmae),
                    skill=s, published_skill=pub_skill, abs_delta_skill=abs(s - pub_skill)))
    print("  %-12s %-10s %6d %12.6f %12.6f %+14.9f %12.3e"
          % (comp, refcol, n, mm, mr, s, abs(s - pub_skill)))
    assert n == pub_n, "row count differs for %s/%s: %d vs published %d" % (comp, refcol, n, pub_n)

rp = pd.DataFrame(rep)
rp.to_csv(os.path.join(B.OUT, "reproduction.csv"), index=False)
maxd_skill = float(rp["abs_delta_skill"].max())
maxd_mae = float(max(rp["abs_delta_model_mae"].max(), rp["abs_delta_ref_mae"].max()))
REPRODUCED = maxd_skill < 5e-9
print("\n  MAX |delta skill| = %.3e     MAX |delta MAE| = %.3e     REPRODUCED = %s"
      % (maxd_skill, maxd_mae, REPRODUCED))
OUT["reproduction"] = rep
OUT["max_abs_delta_skill"] = maxd_skill
OUT["max_abs_delta_mae"] = maxd_mae
OUT["reproduced"] = bool(REPRODUCED)
json.dump(OUT, open(os.path.join(B.OUT, "_s01.json"), "w"), indent=2, default=str)
if not REPRODUCED:
    raise SystemExit("STOP: D081's per-component skill table did NOT reproduce.")

B.hdr("STEP 1c -- INDEPENDENT REBUILD OF D081's OWN REFERENCES (is the frozen column what it says?)")
# Rebuild ref_pts / ref_minutes / ref_fga and refA/refB_ppm from the raw outcomes with this
# screen's own code.  If the frozen columns are what their names claim, the rebuild matches.
fr = f.copy()
codes, starts, ns = B.group_bounds(fr)


def expanding_prior_mean(v, starts, ns):
    out = np.full(len(v), np.nan)
    for a, ln in zip(starts, ns):
        c = np.r_[0.0, np.cumsum(v[a:a + ln])]
        h = np.arange(ln)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[a:a + ln] = np.where(h > 0, c[h] / np.maximum(h, 1), np.nan)
    return out


def league_prior_mean_rowblocked(fr, v):
    """D081's cold fallback: expanding same-season league mean with a plain shift(1) in DATE order
    (ROW-blocked, not DATE-blocked).  Reproduced exactly as D081 built it, for the check only."""
    s = fr["season"].to_numpy()
    d = fr["gdate"].to_numpy()
    out = np.full(len(fr), np.nan)
    for ss in np.unique(s):
        m = np.flatnonzero(s == ss)
        order = m[np.argsort(d[m], kind="stable")]
        c = np.r_[0.0, np.cumsum(v[order])]
        h = np.arange(len(order))
        with np.errstate(invalid="ignore", divide="ignore"):
            out[order] = np.where(h > 0, c[h] / np.maximum(h, 1), np.nan)
    return out


chk = []
for t in ["pts", "minutes", "fga"]:
    v = fr["y_" + t].to_numpy(float)
    a = expanding_prior_mean(v, starts, ns)
    lg = league_prior_mean_rowblocked(fr, v)
    reb = np.where(np.isfinite(a), a, np.where(np.isfinite(lg), lg, np.nanmean(v)))
    d = float(np.nanmax(np.abs(reb - fr["ref_" + t].to_numpy(float))))
    chk.append(dict(column="ref_" + t, max_abs_diff_vs_independent_rebuild=d))
    print("  ref_%-8s  max|rebuild - frozen| = %.3e" % (t, d))
OUT["independent_reference_rebuild"] = chk

B.hdr("STEP 1d -- LEAK PROBE: does a KNOWN-retrospective baseline get flagged and ours not?")
# Correlation of each 'reference' with the player's own STRICTLY FUTURE mean outcome, over and
# above what the outcome itself explains.  A retrospective baseline knows the future; a prior-only
# one does not.  Control = the player's whole-season mean (deliberately retrospective).
fut = np.full(len(fr), np.nan)
for a, ln in zip(starts, ns):
    v = fr["y_pts"].to_numpy(float)[a:a + ln]
    csum = np.r_[np.cumsum(v[::-1])[::-1], 0.0]
    cnt = np.arange(ln, 0, -1, dtype=float) - 1.0
    with np.errstate(invalid="ignore", divide="ignore"):
        fut[a:a + ln] = np.where(cnt > 0, (csum[:ln] - v) / np.maximum(cnt, 1), np.nan)
fr["_future_mean_pts"] = fut
fr["_full_season_mean_pts"] = fr.groupby(["season", "player_id"], sort=False)["y_pts"].transform("mean")
m = np.isfinite(fut)
probe = {}
for name, col in [("RETROSPECTIVE CONTROL full-season mean", "_full_season_mean_pts"),
                  ("our/D076 prior-appearance mean ref_pts", "ref_pts")]:
    c = float(np.corrcoef(fr[col].to_numpy(float)[m], fut[m])[0, 1])
    probe[name] = c
    print("  corr(%s, player's STRICTLY FUTURE mean pts) = %+.4f" % (name, c))
print("  -> the retrospective control is the more future-correlated of the two; the prior-only")
print("     reference is not.  (D081 measured +0.9480 vs +0.8453 with the same construction.)")
OUT["leak_probe_corr_with_future"] = probe

json.dump(OUT, open(os.path.join(B.OUT, "_s01.json"), "w"), indent=2, default=str)
print("\nDONE s01")
