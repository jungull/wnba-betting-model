"""E0_I0029 s00 -- MANIFEST CHECK, PARTITION ASSERT, and verification of the feasibility numbers
that the ideation queue used to rank this idea.

THE FEASIBILITY NUMBERS WERE QUOTED OVER SIX SEASONS.  This screen may only read 2021-2024.  Every
number is therefore RE-DERIVED ON THE EXPLORATION PARTITION and the difference is reported rather
than hidden.  A quoted number I cannot reproduce inside the partition is flagged, not adopted.

NOTHING IS FITTED HERE.  s00 runs before the preregistration hash is computed, and computes only
descriptive quantities that were ALREADY PUBLISHED in the ideation queue.  It does not compute any
dR2, any null, or any statistic that could be used to choose a candidate.  That ordering is stated
so the prereg cannot be accused of being informed by this screen's own statistics.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ft_base import (FORBIDDEN, MP_PATH, MT_PATH, OUT, SEASONS, assert_partition, hdr, jsonable,
                     manifest_status)

rep = {}

hdr("0. FORBIDDEN ARTIFACTS -- declared and NOT opened")
for f in FORBIDDEN:
    print("  NOT OPENED: %s" % f)
rep["forbidden_not_opened"] = FORBIDDEN

hdr("1. MANIFEST CHECK -- read from bytes this session, never cited from NOTES")
mans = {}
for p in [MP_PATH, MT_PATH]:
    m = manifest_status(p)
    mans[os.path.basename(p)] = m
    print("  %-28s %s  granularity=%s fit_through=%s"
          % (os.path.basename(p), m["status"], m["asof_granularity"], m["fit_through_season"]))
    if m["status"] == "UNUSABLE":
        sys.exit("13.2.2 FAIL: %s is artifact-granular beyond the partition." % p)
rep["manifests"] = mans

hdr("2. LOAD + PARTITION ASSERT ON VALUES")
mp = pd.read_parquet(MP_PATH)
print("  raw master_player %s" % (mp.shape,))
mp["game_date"] = pd.to_datetime(mp["game_date"], errors="coerce")
mp = mp[mp["season"].isin(SEASONS)].copy()                      # FILTER-POINT
assert_partition(mp)
print("  after partition filter %s" % (mp.shape,))

for c in ["minutes", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb", "ast",
          "tov", "pf", "pts", "fouls_drawn", "possessions", "pace"]:
    mp[c] = pd.to_numeric(mp[c], errors="coerce").astype(float)

app = mp[mp["minutes"] > 0].copy()                              # FILTER-POINT: appeared only
assert_partition(app)
print("  appeared player-games (minutes>0): %d" % len(app))
rep["n_rows"] = dict(raw_partition=int(len(mp)), appeared=int(len(app)))

hdr("3. RE-DERIVING THE FEASIBILITY NUMBERS ON THE EXPLORATION PARTITION")
tot_pts = float(app["pts"].sum())
tot_ftm = float(app["ftm"].sum())
ft_share = tot_ftm / tot_pts
print("  FT share of points          = %.6f   (ideation quoted 0.1737 over SIX seasons)"
      % ft_share)

# per-season, so the reader can see whether the six-season figure is an average of stable numbers
per_season = []
for s in sorted(app["season"].unique()):
    d = app[app["season"] == s]
    per_season.append(dict(season=int(s), n=int(len(d)),
                           ft_share_of_points=float(d["ftm"].sum() / d["pts"].sum()),
                           frac_fta_zero=float((d["fta"] == 0).mean()),
                           mean_fta=float(d["fta"].mean()), mean_ftm=float(d["ftm"].mean()),
                           corr_ftm_pts=float(np.corrcoef(d["ftm"], d["pts"])[0, 1]),
                           corr_fd_pts=float(np.corrcoef(d["fouls_drawn"].fillna(0), d["pts"])[0, 1]),
                           fouls_drawn_null_frac=float(d["fouls_drawn"].isna().mean())))
PS = pd.DataFrame(per_season)
print(PS.to_string(index=False))
rep["per_season"] = per_season

frac0 = float((app["fta"] == 0).mean())
c_ftm = float(np.corrcoef(app["ftm"], app["pts"])[0, 1])
fd = app["fouls_drawn"]
fd_ok = fd.notna()
c_fd = float(np.corrcoef(app.loc[fd_ok, "fouls_drawn"], app.loc[fd_ok, "pts"])[0, 1])
print("\n  frac fta==0                 = %.6f   (ideation quoted 0.4640)" % frac0)
print("  corr(ftm, pts)              = %+.6f  (ideation quoted +0.6595)  -> bound R2 %.6f"
      % (c_ftm, c_ftm ** 2))
print("  corr(fouls_drawn, pts)      = %+.6f  (ideation quoted +0.6749)  -> bound R2 %.6f"
      % (c_fd, c_fd ** 2))
print("  fouls_drawn NULL fraction   = %.6f  <-- COVERAGE IS NOT 100%% INSIDE THE PARTITION IF >0"
      % float(fd.isna().mean()))
print("  ftm/fta NULL fraction       = %.6f / %.6f"
      % (float(app["ftm"].isna().mean()), float(app["fta"].isna().mean())))

rep["feasibility_reproduction"] = dict(
    ft_share_of_points=ft_share, quoted_ft_share=0.1737,
    frac_fta_zero=frac0, quoted_frac_fta_zero=0.4640,
    corr_ftm_pts=c_ftm, quoted_corr_ftm_pts=0.6595, bound_r2_ftm=c_ftm ** 2,
    corr_fouls_drawn_pts=c_fd, quoted_corr_fd_pts=0.6749, bound_r2_fd=c_fd ** 2,
    fouls_drawn_null_frac=float(fd.isna().mean()),
    ftm_null_frac=float(app["ftm"].isna().mean()), fta_null_frac=float(app["fta"].isna().mean()),
    note=("Quoted figures were computed over SIX seasons including 2025/2026, which this screen "
          "may not read.  These are the 2021-2024 values.  Differences are partition differences, "
          "not errors, and the quoted values are NOT adopted anywhere in this screen."))

hdr("4. THE HURDLE, DESCRIBED")
print("  This is the number the whole screen turns on.  If free-throw production were a rate,")
print("  the zero mass would follow from a low rate.  It does not: the zero mass is far larger")
print("  than a Poisson with the observed mean would produce.")
lam = float(app["fta"].mean())
pois0 = float(np.exp(-lam))
print("  mean fta = %.4f  ->  Poisson P(0) = %.4f   OBSERVED P(0) = %.4f   EXCESS = %+.4f"
      % (lam, pois0, frac0, frac0 - pois0))
rep["hurdle_excess_zero"] = dict(mean_fta=lam, poisson_p0=pois0, observed_p0=frac0,
                                 excess=frac0 - pois0)

pos = app[app["fta"] > 0]
print("\n  GIVEN fta>0 (n=%d, %.1f%% of rows):" % (len(pos), 100 * len(pos) / len(app)))
print("    fta   mean %.4f  sd %.4f  median %.1f  max %.0f"
      % (pos["fta"].mean(), pos["fta"].std(), pos["fta"].median(), pos["fta"].max()))
print("    ftm   mean %.4f  sd %.4f" % (pos["ftm"].mean(), pos["ftm"].std()))
print("    ft%%   mean %.4f  sd %.4f" % ((pos["ftm"] / pos["fta"]).mean(),
                                         (pos["ftm"] / pos["fta"]).std()))
print("\n  fta value counts (top 12):")
print(app["fta"].value_counts().sort_index().head(12).to_string())
rep["conditional_moments"] = dict(
    n_pos=int(len(pos)), frac_pos=float(len(pos) / len(app)),
    fta_mean=float(pos["fta"].mean()), fta_sd=float(pos["fta"].std()),
    fta_max=float(pos["fta"].max()),
    ftm_mean=float(pos["ftm"].mean()), ftm_sd=float(pos["ftm"].std()),
    ftpct_mean=float((pos["ftm"] / pos["fta"]).mean()),
    ftpct_sd=float((pos["ftm"] / pos["fta"]).std()))

hdr("5. VARIANCE DECOMPOSITION OF ftm ACROSS THE HURDLE -- LAW OF TOTAL VARIANCE")
print("  Var(ftm) = E[Var(ftm|A)] + Var(E[ftm|A]) where A = 1{fta>0}.")
print("  The SECOND term is the share of free-throw-point variance that is EXPLAINED BY THE")
print("  HURDLE ALONE -- i.e. by knowing only whether the player got to the line.")
y = app["ftm"].to_numpy(float)
a = (app["fta"].to_numpy(float) > 0).astype(float)
mu = y.mean()
grp = {0.0: y[a == 0], 1.0: y[a == 1]}
within = sum(len(v) * v.var() for v in grp.values()) / len(y)
between = sum(len(v) * (v.mean() - mu) ** 2 for v in grp.values()) / len(y)
print("  Var(ftm) = %.6f    within = %.6f (%.2f%%)   BETWEEN (hurdle) = %.6f (%.2f%%)"
      % (y.var(), within, 100 * within / y.var(), between, 100 * between / y.var()))
rep["total_variance_law"] = dict(var_ftm=float(y.var()), within=float(within),
                                 between_hurdle=float(between),
                                 hurdle_share_of_ftm_variance=float(between / y.var()))

hdr("6. IS ftm A MEANINGFUL SHARE OF POINTS VARIANCE, NOT JUST OF POINTS LEVEL?")
print("  17.37%% of the POINTS TOTAL is a level statement.  What matters for a forecast is the")
print("  VARIANCE share and the covariance, so both are computed here.")
p = app["pts"].to_numpy(float)
f = app["ftm"].to_numpy(float)
nf = p - f
cov = float(np.cov(np.vstack([f, nf]))[0, 1])
print("  Var(pts) = %.4f = Var(ftm) %.4f + Var(non-ft pts) %.4f + 2*Cov %.4f"
      % (p.var(), f.var(), nf.var(), 2 * cov))
print("  ftm share of Var(pts)                = %.4f" % (f.var() / p.var()))
print("  ftm TOTAL contribution (Var+Cov)/Var = %.4f" % ((f.var() + cov) / p.var()))
rep["points_variance_share"] = dict(var_pts=float(p.var()), var_ftm=float(f.var()),
                                    var_nonft=float(nf.var()), cov=cov,
                                    ftm_var_share=float(f.var() / p.var()),
                                    ftm_total_contribution=float((f.var() + cov) / p.var()))

json.dump(jsonable(rep), open(os.path.join(OUT, "_s00.json"), "w"), indent=2)
print("\n  WROTE _s00.json")
