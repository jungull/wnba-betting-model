"""Are the surviving leads distinct, or do they all collapse onto one axis?

Almost everything that survived -- thin player sample, debutants on the team, first meeting of the
season, early team-game index -- is elevated EARLY IN THE SEASON.  This script asks, for each lead,
whether it still moves |residual| once the others are held fixed."""
import os

import numpy as np
import pandas as pd

import rh_base as B

pd.set_option("display.width", 240); pd.set_option("display.max_columns", 40)

f = pd.read_parquet(os.path.join(B.OUT, "analysis_frame.parquet"))
B.guard(f, "conditioning input")
f = f.reset_index(drop=True)
seas = f["season"].to_numpy()
n = len(f)
f["pts__is_fallback"] = f["pts__is_fallback"].astype(float)
f["pts__pred_width"] = f["pts__pred_q95"] - f["pts__pred_q05"]

sc = np.asarray(pd.Categorical(seas).codes, dtype=np.int64)
NS = int(sc.max() + 1)
D = np.zeros((n, NS)); D[np.arange(n), sc] = 1.0


def fit(y, cols):
    X = np.column_stack([D] + [np.nan_to_num(pd.to_numeric(f[c], errors="coerce")
                                             .fillna(pd.to_numeric(f[c], errors="coerce").median())
                                             .to_numpy(float)) for c in cols])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b
    k = X.shape[1]
    s2 = float(r @ r) / (n - k)
    V = s2 * np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.maximum(np.diag(V), 0))
    return b, se, float(r @ r)


def r2_plain(y, sse):
    sst = float(((y - y.mean()) ** 2).sum())
    return 1 - sse / sst


CONTROLS = ["pl_games_prior", "tm_game_idx"]
LEADS = ["pl_games_prior", "tm_newfaces_prior", "tm_first_meeting", "tm_game_idx",
         "pl_minutes_prior", "pts__is_fallback", "tm_five_tenure_prior",
         "tm_prior_meetings", "pl_dnp_frac5", "pts__pred_width"]

for dep in ["absres_minutes", "absres_pts", "absres_fga"]:
    y = f[dep].to_numpy(float)
    B.hdr("DEPENDENT: %s   (R2 convention D069: plain unweighted, SST about the unweighted mean)"
          % dep)
    print("  %-24s %10s %10s | %10s %10s %10s" %
          ("lead", "t_alone", "dR2_alone", "t_|depth", "t_|depth+idx", "dR2_added"))
    _, _, sse0 = fit(y, [])
    for lead in LEADS:
        b1, s1, sse1 = fit(y, [lead])
        t_alone = b1[-1] / s1[-1]
        dr2_alone = r2_plain(y, sse1) - r2_plain(y, sse0)
        ctrl1 = [c for c in ["pl_games_prior"] if c != lead]
        b2, s2_, _ = fit(y, ctrl1 + [lead])
        t_depth = b2[-1] / s2_[-1]
        ctrl2 = [c for c in CONTROLS if c != lead]
        b3, s3, sse3 = fit(y, ctrl2 + [lead])
        _, _, sse_c = fit(y, ctrl2)
        t_both = b3[-1] / s3[-1]
        dr2_added = r2_plain(y, sse3) - r2_plain(y, sse_c)
        print("  %-24s %10.2f %10.5f | %10.2f %12.2f %10.5f"
              % (lead, t_alone, dr2_alone, t_depth, t_both, dr2_added))

B.hdr("CORRELATION AMONG THE LEADS (Pearson, pooled 2022-2024)")
M = f[LEADS].apply(pd.to_numeric, errors="coerce")
M = M.fillna(M.median())
print(M.corr().round(3).to_string())
M.corr().round(4).to_csv(os.path.join(B.OUT, "lead_correlations.csv"))

B.hdr("THE ONE-AXIS QUESTION, ANSWERED IN PLAIN NUMBERS")
q = pd.qcut(f["pl_games_prior"], 5, labels=False, duplicates="drop")
tab = f.assign(depth_quintile=q).groupby("depth_quintile").agg(
    n=("absres_minutes", "size"),
    median_prior_games=("pl_games_prior", "median"),
    mean_team_game_idx=("tm_game_idx", "mean"),
    mean_newfaces=("tm_newfaces_prior", "mean"),
    fallback_rate=("pts__is_fallback", "mean"),
    mae_minutes=("absres_minutes", "mean"),
    ref_mae_minutes=("refabs_minutes", "mean"),
    mae_pts=("absres_pts", "mean"),
    ref_mae_pts=("refabs_pts", "mean"))
tab["skill_minutes"] = 1 - tab["mae_minutes"] / tab["ref_mae_minutes"]
tab["skill_pts"] = 1 - tab["mae_pts"] / tab["ref_mae_pts"]
print(tab.to_string())
tab.to_csv(os.path.join(B.OUT, "depth_quintile_table.csv"))
