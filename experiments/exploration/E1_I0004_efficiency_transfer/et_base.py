"""E1_I0004_efficiency_transfer -- shared loader and construction module.

QUESTION.  D081 located the champion player model's failure at the PER-MINUTE EFFICIENCY step:
    on the decision-relevant stratum (>=8 prior same-season appearances AND trailing-5 mean minutes
    >=24; n=5,107) points skill is -0.36% at p=0.27, minutes skill is +7.7% and buys nothing,
    because points error is dominated ~3:1 by efficiency.  D081 also screened 550 cells of GENERIC
    pre-game state and cleared 0 of 330 rate cells family-wise.  D074 left ONE live basketball-
    specific EFFICIENCY signal untested against the champion: I0004's CONVERSION channel (a player
    converts better against opponents that have historically conceded conversion in that zone),
    slope +0.373, family-wise p 0.0124 one-sided / 0.0220 two-sided across the five-zone family.
    D079 killed the SHOT-MIX channel on an arithmetic ceiling (dR2 <= 0.00113) but that ceiling is
    a statement about REALLOCATING attempts at constant volume and does NOT apply to conversion.

PARTITION (GRAPH_POLICY 13.2).  2021-2024 only; the champion-forecast work is 2022-2024 because
    D076 established the 2021 fold is degenerate (n_train_rows=0, model_was_fitted=false).  The
    files data/shotcharts/shots_2025_*.parquet and shots_2026_regular.parquet EXIST and are NEVER
    OPENED -- the loader whitelists 2021..2024 by filename and then re-asserts on COLUMN VALUES
    via screenkit.assert_partition.  No byte/regex scan is used as a partition check anywhere.

NO REALISED-GAME INFORMATION.  Every constructed input reads STRICTLY PRIOR games only:
    * opponent zone-conversion allowance OC_z  -- the opponent's own strictly prior games in season
    * player prior zone mix w_z                -- the player's own strictly prior games in season
    Realised FGA / minutes / conversion appear ONLY as the response y, and in two clearly labelled
    DIAGNOSTIC quantities that are excluded from every headline.

ZONE MAPS FORBIDDEN.  data/zone_maps/* are asof_granularity "artifact"; filtering does not help.
    Zones are derived from the raw per-shot SHOT_ZONE_BASIC label, which is a property of the shot.

R2 CONVENTION (D069): plain unweighted, SST about the UNWEIGHTED mean.  Forecasts already in hand
    are scored with screenkit.r2_of_forecast (NOT r2_plain, which refits).

NO MODEL FITTING.  Nothing is trained here.  The transfer coefficient LAMBDA is the FROZEN D074
    slope +0.3731535713274873, carried in from E1_I0004_rim_finishing / E1_I0004_shot_selection.
    It is not re-estimated on this frame.
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, r"experiments\exploration\_screen_kit")
HERE = os.path.join(ROOT, r"experiments\exploration\E1_I0004_efficiency_transfer")
PSD = os.path.join(ROOT, r"experiments\exploration\E0_I0015_points_skill_decomposition")
SEL = os.path.join(ROOT, r"experiments\exploration\E1_I0004_shot_selection")
RIM = os.path.join(ROOT, r"experiments\exploration\E1_I0004_rim_finishing")
BASELINE_DIR = os.path.join(ROOT, r"experiments\exploration\E1_I0011_split_alpha\baseline")

for p in (KIT, PSD, BASELINE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)
import screenkit as sk  # noqa: E402

sys.dont_write_bytecode = True

DECOMP_FRAME = os.path.join(PSD, "decomp_frame.parquet")

# --------------------------------------------------------------------------- frozen constants
SEED = 20260807
PARTITION = [2021, 2022, 2023, 2024]        # files whitelisted by name; 2025/2026 never opened
CHAMP_SEASONS = [2022, 2023, 2024]          # D076: the 2021 fold is degenerate
TYPES = ["regular", "playoffs"]
RA = "Restricted Area"
ZONES = [RA, "In The Paint (Non-RA)", "Mid-Range", "Corner 3", "Above the Break 3"]
POINT_VALUE = {RA: 2.0, "In The Paint (Non-RA)": 2.0, "Mid-Range": 2.0,
               "Corner 3": 3.0, "Above the Break 3": 3.0}

MIN_PRE = 20                # D074's opponent gate: >=20 prior zone attempts faced AND >=20 pooled
MIN_PRIOR_ATT = 20          # player must have >=20 strictly-prior FGA in season to have a mix

# THE TRANSFER COEFFICIENT -- FROZEN, NOT FITTED HERE.
# E1_I0004_rim_finishing/measure_results.json, cell B1_own_rate_v2_split_alpha | O2_pregame:
#   n = 30764   corr = +0.02881718   diff = +0.01757440   beta = +0.37315357
LAMBDA_D074 = 0.3731535713274873

# D081's decision-relevant stratum
STRATUM_RULE = ">=8 prior same-season appearances AND trailing-5 mean minutes >=24"

D074_TARGET = dict(n=30764, corr=0.02881718165669519, diff=0.01757439922911997,
                   beta=0.3731535713274873)
D081_TARGET = dict(n=5107, points_skill=-0.0035882639143178796,
                   champion_points_mae=5.0097913607053295,
                   reference_points_mae=4.991879180776316,
                   p_two_sided_block_signflip=0.26636681659170414,
                   minutes_skill=0.061432671098414104,
                   rate_ppm_skill=-0.001972131916302633)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


# --------------------------------------------------------------------------- raw shots
def load_shots(seasons=None, verbose=True):
    """Raw per-shot records for the EXPLORATION PARTITION ONLY.

    The 2025 and 2026 shot files exist in data/shotcharts/ and are NEVER constructed as a path.
    Zone comes from the per-shot SHOT_ZONE_BASIC label; data/zone_maps/* are not read (they are
    asof_granularity "artifact" -- verified by reading the manifest COLUMN VALUE, not by text).
    """
    seasons = seasons or PARTITION
    assert set(seasons) <= set(PARTITION), "PARTITION VIOLATION: %s" % seasons
    dfs = []
    for ssn in seasons:
        for t in TYPES:
            f = os.path.join(ROOT, "data", "shotcharts", "shots_%d_%s.parquet" % (ssn, t))
            d = pd.read_parquet(f)
            d["season"] = ssn
            d = d[d["season"].isin(seasons)]          # FILTER-POINT 1
            if verbose:
                print("  %-52s rows=%7d  seasons=%s"
                      % (os.path.basename(f), len(d), sorted(d["season"].unique())))
            dfs.append(d)
    shots = pd.concat(dfs, ignore_index=True)
    shots = shots[shots["season"].isin(seasons)].copy()    # FILTER-POINT 2
    shots["game_date"] = pd.to_datetime(shots["GAME_DATE"], format="%Y%m%d")
    shots["zone"] = shots["SHOT_ZONE_BASIC"].map(
        lambda z: "Corner 3" if z in ("Left Corner 3", "Right Corner 3") else z)
    shots["made"] = shots["SHOT_MADE_FLAG"].astype(int)

    game_teams = shots.groupby("GAME_ID")["TEAM_ID"].unique()
    opp = {}
    for gid, teams in game_teams.items():
        if len(teams) == 2:
            opp[(gid, teams[0])] = teams[1]
            opp[(gid, teams[1])] = teams[0]
    shots["OPP_TEAM_ID"] = [opp.get((g, t), np.nan)
                            for g, t in zip(shots["GAME_ID"], shots["TEAM_ID"])]
    shots = shots[shots["OPP_TEAM_ID"].notna()].copy()
    shots["OPP_TEAM_ID"] = shots["OPP_TEAM_ID"].astype(shots["TEAM_ID"].dtype)
    sk.assert_partition(shots.rename(columns={"game_date": "gdate"}), verbose=verbose)
    assert shots["game_date"].dt.year.max() <= 2024, "PARTITION VIOLATION (date)"
    if verbose:
        print("  shots with resolved opponent = %d over %d games; seasons=%s"
              % (len(shots), shots["GAME_ID"].nunique(), sorted(shots["season"].unique())))
    return shots


# ------------------------------------------------- opponent zone-conversion allowance (PRIOR ONLY)
def opponent_zone_allowance(shots, zone, min_pre=MIN_PRE):
    """OC_z for every (opponent-team, season, game): the conversion rate the opponent allowed IN
    ZONE z over its STRICTLY PRIOR games this season, minus the POOLED rate it allowed over the
    same strictly prior games.

    TIME WINDOW: the opponent's own games with game_date strictly earlier in the same season
    (cumsum MINUS the current game's own contribution -- the current game never enters).
    This is D074's corrected O2 construction, extended to all five zones exactly as
    E1_I0004_shot_selection/build_frames.py section 2 did.  It reads NO realised quantity of the
    game being forecast.
    """
    zsh = shots[shots["zone"] == zone]
    o = (shots.groupby(["OPP_TEAM_ID", "season", "GAME_ID", "game_date"])
         .agg(pool_att=("made", "size"), pool_mk=("made", "sum")).reset_index())
    oz = (zsh.groupby(["OPP_TEAM_ID", "season", "GAME_ID"])
          .agg(z_att=("made", "size"), z_mk=("made", "sum")).reset_index())
    o = o.merge(oz, on=["OPP_TEAM_ID", "season", "GAME_ID"], how="left")
    o[["z_att", "z_mk"]] = o[["z_att", "z_mk"]].fillna(0.0)
    o = o.sort_values(["OPP_TEAM_ID", "season", "game_date", "GAME_ID"],
                      kind="stable").reset_index(drop=True)
    k = [o["OPP_TEAM_ID"], o["season"]]
    for c in ["pool_att", "pool_mk", "z_att", "z_mk"]:
        o["pre_" + c] = o.groupby(k, sort=False)[c].cumsum() - o[c]
    o["OC"] = o["pre_z_mk"] / o["pre_z_att"] - o["pre_pool_mk"] / o["pre_pool_att"]
    o.loc[~((o["pre_z_att"] >= min_pre) & (o["pre_pool_att"] >= min_pre)), "OC"] = np.nan
    o["zone"] = zone
    return o[["OPP_TEAM_ID", "season", "GAME_ID", "game_date", "zone", "OC",
              "pre_z_att", "pre_pool_att"]]


def league_prior_zone_gap(shots, zone):
    """The LEAGUE-wide zone-minus-pooled conversion gap over all games played STRICTLY BEFORE the
    current calendar date in the same season.

    WHY THIS EXISTS.  OC_z as D074 defined it is (opponent's prior zone rate) - (opponent's prior
    POOLED rate).  Restricted-area shots convert far better than the pooled average, so OC_RA has a
    LEAGUE-WIDE MEAN of about +0.18 that is a property of the zone, not of the opponent.  In a
    REGRESSION WITH AN INTERCEPT -- which is how D074 measured it -- that common level is absorbed
    and irrelevant.  In an additive FORECAST ADJUSTMENT it is not: adding LAMBDA * w * PV * OC_RA
    would add a systematic positive bias to every row and would be testing a mis-calibrated level
    rather than the cross-sectional signal that survived.  Subtracting this league prior gap leaves
    exactly the opponent's DEVIATION from the league, which is the quantity D074's slope describes.

    TIME WINDOW: all league games with game_date STRICTLY EARLIER in the same season.  NaN before
    any prior game exists; NOT back-filled (back-filling the first dates from later ones would read
    forward, which is the trap-2 signature).  This is the same shape as the frozen
    E1_I0004_shot_selection `lg_share_prior` anchor, minus its bfill.

    D080 NOTE: this anchor is a SEASON-LEVEL SCALAR shared by every team on a given date, so it
    cannot manufacture cross-sectional differences between opponents.  Unlike the `*_pregame`
    columns in pressure_lib.py it is built only from games strictly before the date, so it is also
    legitimate for the LEVEL claim being made here.
    """
    z = shots[shots["zone"] == zone]
    zd = (z.groupby(["season", "game_date"]).agg(z_att=("made", "size"), z_mk=("made", "sum"))
          .reset_index())
    pd_ = (shots.groupby(["season", "game_date"])
           .agg(p_att=("made", "size"), p_mk=("made", "sum")).reset_index())
    d = pd_.merge(zd, on=["season", "game_date"], how="left")
    d[["z_att", "z_mk"]] = d[["z_att", "z_mk"]].fillna(0.0)
    d = d.sort_values(["season", "game_date"], kind="stable").reset_index(drop=True)
    for c in ["z_att", "z_mk", "p_att", "p_mk"]:
        d["cum_" + c] = d.groupby("season", sort=False)[c].cumsum() - d[c]
    gap = (d["cum_z_mk"] / d["cum_z_att"].replace(0, np.nan)
           - d["cum_p_mk"] / d["cum_p_att"].replace(0, np.nan))
    d["lg_prior_gap"] = gap
    d["zone"] = zone
    return d[["season", "game_date", "zone", "lg_prior_gap"]]


def opponent_zone_allowance_LOO_RETROSPECTIVE(shots, zone, min_loo=MIN_PRE):
    """*** DIAGNOSTIC ONLY -- READS THE FUTURE.  NEVER AN INPUT TO ANY FORECAST HERE. ***

    D074's E0 form O1: leave-one-GAME-out FULL-SEASON opponent zone rate.  TIME WINDOW: the
    opponent's WHOLE SEASON minus the current game, i.e. it reads the opponent's LATER games.
    Built here for exactly one purpose: to be the `baseline_col` in screenkit.future_leakage_probe
    so that the probe is shown to FLAG the known offender and NOT to flag the prior-only OC.
    """
    s = shots.copy()
    st = (s.groupby(["OPP_TEAM_ID", "season", "zone"])
          .agg(season_att=("made", "size"), season_mk=("made", "sum")).reset_index())
    sp = (s.groupby(["OPP_TEAM_ID", "season"])
          .agg(pool_att=("made", "size"), pool_mk=("made", "sum")).reset_index())
    gz = (s.groupby(["OPP_TEAM_ID", "season", "GAME_ID", "zone"])
          .agg(game_att=("made", "size"), game_mk=("made", "sum")).reset_index())
    gp = (s.groupby(["OPP_TEAM_ID", "season", "GAME_ID"])
          .agg(gpool_att=("made", "size"), gpool_mk=("made", "sum")).reset_index())
    z = gz[gz["zone"] == zone].merge(st[st["zone"] == zone].drop(columns="zone"),
                                     on=["OPP_TEAM_ID", "season"], how="left")
    z = z.merge(gp, on=["OPP_TEAM_ID", "season", "GAME_ID"], how="left")
    z = z.merge(sp, on=["OPP_TEAM_ID", "season"], how="left")
    z["loo_att"] = z["season_att"] - z["game_att"]
    z["loo_mk"] = z["season_mk"] - z["game_mk"]
    z["loo_pool_att"] = z["pool_att"] - z["gpool_att"]
    z["loo_pool_mk"] = z["pool_mk"] - z["gpool_mk"]
    z["OC_LOO_RETRO"] = (z["loo_mk"] / z["loo_att"] - z["loo_pool_mk"] / z["loo_pool_att"])
    z.loc[~((z["loo_att"] >= min_loo) & (z["loo_pool_att"] >= min_loo)), "OC_LOO_RETRO"] = np.nan
    return z[["OPP_TEAM_ID", "season", "GAME_ID", "OC_LOO_RETRO"]]


# ------------------------------------------------------ player prior zone mix (STRICTLY PRIOR ONLY)
def player_prior_zone_mix(shots, zones=None, min_prior_att=MIN_PRIOR_ATT):
    """w_z for every (player, season, game): the share of the player's own STRICTLY PRIOR
    same-season field-goal attempts that were taken in zone z.

    TIME WINDOW: the player's own games with game_date strictly earlier in the same season
    (cumsum MINUS the current game).  The current game's realised attempts NEVER enter -- this is
    the whole point, because the realised mix is a realised-game quantity and is forbidden.
    Rows with fewer than `min_prior_att` strictly-prior attempts get NaN and drop out.
    """
    zones = zones or ZONES
    z5 = shots[shots["zone"].isin(zones)]
    pgz = (z5.groupby(["PLAYER_ID", "season", "GAME_ID", "game_date", "zone"])
           .size().rename("z_att").reset_index())
    pg = (z5.groupby(["PLAYER_ID", "season", "GAME_ID", "game_date"])
          .size().rename("fga").reset_index())
    grid = (pg.assign(_k=1).merge(pd.DataFrame({"zone": zones, "_k": 1}), on="_k")
            .drop(columns="_k"))
    grid = grid.merge(pgz, on=["PLAYER_ID", "season", "GAME_ID", "game_date", "zone"], how="left")
    grid["z_att"] = grid["z_att"].fillna(0.0)
    grid = grid.sort_values(["zone", "PLAYER_ID", "season", "game_date", "GAME_ID"],
                            kind="stable").reset_index(drop=True)
    k = [grid["zone"], grid["PLAYER_ID"], grid["season"]]
    grid["pre_z_att"] = grid.groupby(k, sort=False)["z_att"].cumsum() - grid["z_att"]
    grid["pre_fga"] = grid.groupby(k, sort=False)["fga"].cumsum() - grid["fga"]
    grid["w"] = np.where(grid["pre_fga"] >= min_prior_att,
                         grid["pre_z_att"] / grid["pre_fga"].replace(0, np.nan), np.nan)
    return grid[["PLAYER_ID", "season", "GAME_ID", "game_date", "zone", "w",
                 "pre_z_att", "pre_fga"]]


# --------------------------------------------------------------------------- scoring helpers
def mae(y, yhat):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    return float(np.mean(np.abs(y - yhat)))


def skill(y, yhat_model, yhat_ref):
    """1 - MAE_model/MAE_ref, BOTH on the SAME rows (D076: predicting error is not skill)."""
    mm, mr = mae(y, yhat_model), mae(y, yhat_ref)
    return float(1.0 - mm / mr), mm, mr


def ols_cluster(y, x, cluster):
    """Plain unweighted OLS y ~ 1 + x, R2 = 1 - SSE/SST about the UNWEIGHTED mean (D069).
    CR0 cluster-robust SE reported ONLY for comparability with D074's published table -- it is
    NEVER used here as a substitute for a permutation null (three confirmations in this program).
    Verbatim in form from E1_I0004_shot_selection/build_frames.py :: ols_cluster.
    """
    y = np.asarray(y, float)
    X = np.column_stack([np.ones(len(y)), np.asarray(x, float)])
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ (X.T @ y)
    e = y - X @ b
    sse = float(e @ e)
    sst = float(((y - y.mean()) ** 2).sum())
    n, kp = X.shape
    cl = pd.Series(list(cluster), dtype=object)
    meat = np.zeros((kp, kp))
    for _, idx in cl.groupby(cl.values, sort=False).indices.items():
        u = X[idx].T @ e[idx]
        meat += np.outer(u, u)
    G = cl.nunique()
    adj = (G / max(G - 1, 1)) * ((n - 1) / (n - kp))
    V = XtX_inv @ (adj * meat) @ XtX_inv
    return dict(beta=float(b[1]), se_naive=float(np.sqrt(sse / (n - kp) * XtX_inv[1, 1])),
                se_cluster=float(np.sqrt(V[1, 1])), n_clusters=int(G),
                r2_unweighted_about_unweighted_mean=float(1 - sse / sst), n=int(n))


def e0_stat(g, ycol, xcol):
    """D074's published cell statistic: corr, and the high-vs-low-median difference in y."""
    corr = g[ycol].corr(g[xcol])
    med = g[xcol].median()
    hi = g[xcol] > med
    v = g[ycol].var()
    return dict(n=int(len(g)), corr=float(corr),
                diff=float(g.loc[hi, ycol].mean() - g.loc[~hi, ycol].mean()),
                se_diff=float(np.sqrt(v / hi.sum() + v / (~hi).sum())))
