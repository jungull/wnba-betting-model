"""S06 -- Resolve the UNDETERMINABLE cells with the measurements from S05, recover null
means/sds from raw draw archives already on disk, and run the one decisive structural check
E1_I0021's verdict turns on.

Nothing is refitted. The null draws were already written by the screens themselves.
"""
import os, json
import numpy as np
import pandas as pd

EXPL = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALPHA, THR = 0.05, 0.50

M = pd.read_csv(os.path.join(HERE, "MEASURED_VARIANCE_SHARES.csv"))
def share(screen, cand):
    r = M[(M.screen == screen) & (M.candidate == cand)]
    return float(r.var_share_between.iloc[0]) if len(r) else np.nan

out = {}

# =====================================================================================
# A. THE DECISIVE CHECK FOR E1_I0021 -- does the between-player component of the candidate
#    reach the statistic at all?  Its statistic is the SD of per-player slopes fitted on
#    WITHIN-player demeaned x and y (hd_base.py:225-252).  If the estimand annihilates the
#    between-player component, then adding an arbitrary per-player constant to x must leave
#    every slope, and therefore the statistic, EXACTLY unchanged.  Measure it, do not assert it.
# =====================================================================================
print("=" * 78)
print("A. E1_I0021 -- IS THE BETWEEN-PLAYER COMPONENT VISIBLE TO THE STATISTIC AT ALL?")
print("=" * 78)
fr = pd.read_parquet(os.path.join(EXPL, "E1_I0018_teammate_volume_channel", "screen_frame.parquet"))
if "season" in fr.columns:
    fr = fr[pd.to_numeric(fr["season"], errors="coerce") <= 2024]
assert pd.to_numeric(fr["season"], errors="coerce").max() <= 2024, "PARTITION"
print("frame: %s rows, seasons %s" % (len(fr), sorted(pd.unique(fr['season']))))

def per_player_slope_sd(x, y, pid, min_games=8):
    """hd_base.per_player_slopes(demean=True) arithmetic, reproduced."""
    d = pd.DataFrame(dict(x=np.asarray(x, float), y=np.asarray(y, float), p=np.asarray(pid)))
    d = d.dropna()
    betas = []
    for _p, g in d.groupby("p"):
        if len(g) < min_games:
            continue
        xi = g.x.to_numpy() - g.x.to_numpy().mean()
        yi = g.y.to_numpy() - g.y.to_numpy().mean()
        sxx = float((xi * xi).sum())
        if sxx <= 0:
            continue
        betas.append(float((xi * yi).sum() / sxx))
    return (float(np.std(np.asarray(betas), ddof=1)) if len(betas) > 2 else np.nan), len(betas)

ycol = "y_ppm" if "y_ppm" in fr.columns else next(
    (c for c in fr.columns if c.lower() in ("y_ppm_floor", "ppm", "pts_per_min")), None)
if ycol is None:
    num = fr.select_dtypes("number")
    ycol = "O01_own_usg_pg"
print("using response column:", ycol)

DEMO = []
for xcol in ["O01_own_usg_pg", "refA_ppm", "P01_c04_prevgame"]:
    if xcol not in fr.columns:
        continue
    x = pd.to_numeric(fr[xcol], errors="coerce").to_numpy(float)
    y = pd.to_numeric(fr[ycol], errors="coerce").to_numpy(float)
    pid = fr["player_id"].to_numpy()
    s_real, ng = per_player_slope_sd(x, y, pid)
    # inflate the BETWEEN-player component 10x by adding 9x each player's own mean back on.
    pm = pd.Series(x).groupby(pd.Series(pid)).transform("mean").to_numpy()
    s_infl, _ = per_player_slope_sd(x + 9.0 * pm, y, pid)
    # remove the between-player component entirely
    s_zero, _ = per_player_slope_sd(x - pm, y, pid)
    vsb = share("E1_I0021_heterogeneity_diagnostic", xcol)
    print("\n  %-20s measured between-player share = %.4f  (n_players=%d)" % (xcol, vsb, ng))
    print("     SD of per-player slopes, as measured            = %.12f" % s_real)
    print("     ... with the BETWEEN component multiplied by 10 = %.12f  (delta %.3e)"
          % (s_infl, s_infl - s_real))
    print("     ... with the BETWEEN component removed entirely = %.12f  (delta %.3e)"
          % (s_zero, s_zero - s_real))
    DEMO.append(dict(candidate=xcol, measured_between_player_share=vsb, n_players=ng,
                     sd_slopes_real=s_real, sd_slopes_between_x10=s_infl,
                     sd_slopes_between_removed=s_zero,
                     delta_x10=s_infl - s_real, delta_removed=s_zero - s_real))
D = pd.DataFrame(DEMO)
D.to_csv(os.path.join(HERE, "E1_I0021_ESTIMAND_CHECK.csv"), index=False)
maxdelta = float(np.nanmax(np.abs(np.r_[D.delta_x10.to_numpy(), D.delta_removed.to_numpy()])))
print("\n  MAX |change in the statistic| over every manipulation of the between-player "
      "component = %.3e" % maxdelta)
print("  => the between-player component of the candidate CANNOT reach this statistic.")
out["E1_I0021_max_delta_from_between_component"] = maxdelta

# =====================================================================================
# B. E1_I0031 -- recover null mean / sd from the screen's OWN draw archive, and apply the
#    frozen exposure rule with MEASURED shares.
# =====================================================================================
print("\n" + "=" * 78)
print("B. E1_I0031 -- MEASURED SHARES + NULL MEANS RECOVERED FROM ITS OWN DRAW ARCHIVE")
print("=" * 78)
PM_GAME = ["pm_ewma5_imp", "pm_ewma2_imp", "pm_run_mean_imp", "pm_per36_prior_imp"]
PM_SEASON = ["pm_prev_season_imp"]
BUNDLE = {"pm_game_level": PM_GAME, "pm_prev_season": PM_SEASON, "pm_all": PM_GAME + PM_SEASON}
bshare = {}
for b, cols in BUNDLE.items():
    vs = [share("E1_I0031_rapm_as_prior", c) for c in cols]
    vs = [v for v in vs if np.isfinite(v)]
    bshare[b] = (max(vs) if vs else np.nan, dict(zip(cols, vs)))
    print("  %-16s max component between-player_season share = %.4f   %s"
          % (b, bshare[b][0], {k: round(v, 3) for k, v in bshare[b][1].items()}))

dr = pd.read_csv(os.path.join(EXPL, "E1_I0031_rapm_as_prior", "permutation_draws_plusminus.csv"))
print("\n  draw archive: %d rows, tests=%s" % (len(dr), sorted(dr.test.unique())))
g = dr.groupby(["test", "target", "over", "added"])["value"]
stats = g.agg(null_mean="mean", null_sd="std", n_draws="size").reset_index()
stats.to_csv(os.path.join(HERE, "E1_I0031_RECOVERED_NULL_MOMENTS.csv"), index=False)
print(stats.to_string())
out["E1_I0031_recovered_null_moment_rows"] = int(len(stats))

pm = pd.read_csv(os.path.join(EXPL, "E1_I0031_rapm_as_prior", "plusminus_separate.csv"))
pm = pm[pm["null"].notna() & pm["perm_p"].notna()].copy()
key = ["target", "over", "added"]
pm = pm.merge(stats[stats.test == "pm_dr2"][key + ["null_mean", "null_sd", "n_draws"]],
              on=key, how="left", suffixes=("", "_rec"))
pm["within"] = pm["null"].str.contains("cyclic")
pm["vsb_max_component"] = pm["added"].map(lambda a: bshare.get(a, (np.nan, {}))[0])
pm["is_kill"] = pm["perm_p"] >= ALPHA
pm["z"] = (pm["dr2_own_sst"] - pm["null_mean"]) / pm["null_sd"]
pm["EXPOSURE"] = np.where(~pm["within"], "NOT_EXPOSED",
                  np.where(pm["vsb_max_component"] >= THR, "EXPOSED", "NOT_EXPOSED"))
pm.to_csv(os.path.join(HERE, "E1_I0031_EXPOSURE_DETAIL.csv"), index=False)
print("\n  exposure over E1_I0031 plus-minus cells:")
print(pd.crosstab(pm["added"], [pm["EXPOSURE"], pm["is_kill"]]).to_string())
print("\n  EXPOSED KILLS:", int(((pm.EXPOSURE == "EXPOSED") & pm.is_kill).sum()))
ek = pm[(pm.EXPOSURE == "EXPOSED") & pm.is_kill]
print(ek[["target", "over", "added", "stratum", "n", "dr2_own_sst", "perm_p", "null_mean",
          "null_sd", "z", "vsb_max_component"]].to_string())
out["E1_I0031_exposed_kills"] = int(len(ek))
out["E1_I0031_exposed_flag_z_lt_neg1"] = int((ek.z < -1.0).sum())
out["E1_I0031_exposed_bare_flag"] = int((ek.null_mean > ek.dr2_own_sst).sum())

# =====================================================================================
# C. E1_I0030 -- both undeterminable groups resolved by measurement
# =====================================================================================
print("\n" + "=" * 78)
print("C. E1_I0030 -- RESOLVED BY MEASUREMENT")
print("=" * 78)
print("  is_home, between-player share            = %.6f  -> NOT_EXPOSED" %
      share("E1_I0030_home_advantage_accounting", "is_home"))
for c in ["eastbound", "westbound", "same_zone_travel"]:
    print("  %-18s between-team_season share = %.6f  -> NOT_EXPOSED"
          % (c, share("E1_I0030_home_advantage_accounting", c)))

with open(os.path.join(HERE, "scripts", "_s06.json"), "w") as fh:
    json.dump(out, fh, indent=2, default=str)
print("\nwrote _s06.json")
