"""E1_I0004_efficiency_transfer_v2 -- shared loader and construction module.

RETRY.  The first attempt (`E1_I0004_efficiency_transfer/`) was killed mid-run by an API error
    (GRAPH_POLICY 12: infrastructure event, not a finding).  Its `et_base.py` and s00-s04 scripts
    are read here AS SCAFFOLDING ONLY.  No number, contrast, p-value or verdict from that directory
    is reused; every contrast is rebuilt.  See its ABANDONED.md.

THE INHERITED DEFECT, WHICH IS THIS SCREEN'S FIRST DESIGN REQUIREMENT.
    The opponent zone-conversion allowance OC_z used UNCENTRED shifts every prediction by roughly
    the same amount instead of discriminating between opponents -- a LEVEL SHIFT, not a
    cross-sectional signal.  OC_z as D074 defined it is (opponent's prior zone conversion rate)
    MINUS (opponent's prior POOLED conversion rate), so for the Restricted Area it carries a
    league-wide mean of roughly +0.18 that is a property of the ZONE, not of the OPPONENT.  In
    D074's REGRESSION WITH AN INTERCEPT that common level is absorbed and irrelevant.  In an
    additive FORECAST ADJUSTMENT it is not: it would add a systematic positive bias to every row.
    EVERY contrast in this screen therefore uses a CENTRED allowance, `OCc_z`, built by
    `centred_allowance` below.  Same distinction as D080 (a season-level scalar shared by all teams
    is harmless cross-sectionally, not harmless for a level claim).

QUESTION.  D081 located the champion's failure at the PER-MINUTE EFFICIENCY step: on the
    DECISION-RELEVANT STRATUM (>=8 prior same-season appearances AND trailing-5 mean minutes >=24;
    n=5,107) points skill is -0.36% at p=0.27; minutes skill is +7.7% and buys nothing because
    points error is dominated ~3:1 by efficiency.  D081 also cleared 0 of 330 generic pre-game rate
    cells family-wise.  D074 left ONE live basketball-specific EFFICIENCY signal untested against
    the champion: I0004's CONVERSION channel, slope +0.373, family-wise p 0.0124 one-sided /
    0.0220 two-sided across the five-zone family.  D079 killed the SHOT-MIX channel on an
    ARITHMETIC CEILING (dR2 <= 0.00113), but that ceiling is a statement about REALLOCATING attempts
    at constant volume and does NOT apply to CONVERSION.

PARTITION (GRAPH_POLICY 13.2).  2021-2024 only; champion-forecast work is 2022-2024 because D076
    established the 2021 fold is degenerate (n_train_rows=0, model_was_fitted=false).  The files
    data/shotcharts/shots_2025_*.parquet and shots_2026_regular.parquet EXIST and are NEVER OPENED
    -- the loader whitelists seasons by filename and then re-asserts on COLUMN VALUES via
    screenkit.assert_partition.  No byte/regex scan is used as a partition check anywhere.

NO REALISED-GAME INFORMATION.  Every constructed input reads STRICTLY PRIOR games only:
    * opponent zone-conversion allowance OC_z -- the opponent's own strictly prior games in season
    * league prior zone gap (the CENTRING anchor) -- all league games strictly earlier in season
    * player prior zone mix w_z -- the player's own strictly prior games in season
    Realised FGA / minutes / conversion appear ONLY as the response y, and in clearly labelled
    DIAGNOSTIC quantities excluded from every headline.
    The OPPONENT IDENTITY is resolved from the two team ids appearing in a game.  That is a
    SCHEDULE fact, known pre-game; no realised per-player quantity of that game is read.

ZONE MAPS FORBIDDEN.  data/zone_maps/* are asof_granularity "artifact"; filtering does not help.
    Zones come from the raw per-shot SHOT_ZONE_BASIC label, a property of the shot.

R2 CONVENTION (D069): plain unweighted, SST about the UNWEIGHTED mean.  Forecasts already in hand
    are scored with screenkit.r2_of_forecast (NOT r2_plain, which REFITS).

NO MODEL FITTING IS AUTHORISED.  Nothing is trained.  The transfer coefficient LAMBDA is the FROZEN
    D074 slope +0.3731535713274873, carried in from E1_I0004_rim_finishing / _shot_selection.  It is
    not re-estimated on this frame.
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, r"experiments\exploration\_screen_kit")
HERE = os.path.join(ROOT, r"experiments\exploration\E1_I0004_efficiency_transfer_v2")
PSD = os.path.join(ROOT, r"experiments\exploration\E0_I0015_points_skill_decomposition")
SEL = os.path.join(ROOT, r"experiments\exploration\E1_I0004_shot_selection")
RIM = os.path.join(ROOT, r"experiments\exploration\E1_I0004_rim_finishing")

for p in (KIT, PSD):
    if p not in sys.path:
        sys.path.insert(0, p)
import screenkit as sk  # noqa: E402

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

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

# D074's PUBLISHED five-zone conversion betas (E1_I0004_shot_selection).  Used only for the
# secondary per-zone spec; the primary spec is RA-only, which is the cell that survived.
BETA_BY_ZONE_D074 = {"Restricted Area": 0.4037, "In The Paint (Non-RA)": -0.1216,
                     "Mid-Range": 0.0377, "Corner 3": -0.2558, "Above the Break 3": 0.0005}

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
    asof_granularity "artifact").
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
    assert shots["game_date"].dt.year.max() <= max(seasons), "PARTITION VIOLATION (date)"
    if verbose:
        print("  shots with resolved opponent = %d over %d games; seasons=%s"
              % (len(shots), shots["GAME_ID"].nunique(), sorted(shots["season"].unique())))
    return shots


def opponent_map(shots):
    """(GAME_ID as str, TEAM_ID) -> OPP_TEAM_ID.  SCHEDULE fact, known pre-game."""
    m = (shots[["GAME_ID", "TEAM_ID", "OPP_TEAM_ID"]].drop_duplicates())
    return {(str(g), t): o for g, t, o in
            zip(m["GAME_ID"], m["TEAM_ID"], m["OPP_TEAM_ID"])}


# ------------------------------------------------- opponent zone-conversion allowance (PRIOR ONLY)
def opponent_zone_allowance(shots, zone, min_pre=MIN_PRE):
    """OC_z for every (opponent-team, season, game): the conversion rate the opponent allowed IN
    ZONE z over its STRICTLY PRIOR games this season, minus the POOLED rate it allowed over the
    same strictly prior games.

    TIME WINDOW: the opponent's own games with game_date strictly earlier in the same season
    (cumsum MINUS the current game's own contribution -- the current game never enters).
    This is D074's corrected O2 construction extended to all five zones exactly as
    E1_I0004_shot_selection/build_frames.py did.  It reads NO realised quantity of the game being
    forecast.
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


# =================================================================== *** THE CENTRING *** =========
def league_prior_zone_gap(shots, zone):
    """THE CENTRING ANCHOR.  League-wide (zone conversion rate MINUS pooled conversion rate) over
    all league games played STRICTLY EARLIER in the same season, on a calendar-date grid.

    WHY.  See the module docstring: OC_z carries a large zone-specific common level (~+0.18 for the
    Restricted Area) that is a property of the ZONE, not the OPPONENT.  `OCc_z = OC_z -
    lg_prior_gap_z` is exactly the opponent's DEVIATION from the league at that point in time,
    which is the quantity D074's slope +0.373 describes and the only part that discriminates
    between opponents.

    TIME WINDOW: strictly earlier calendar dates in the same season (cumsum MINUS the current
    date's own contribution).  NaN before any prior game exists and NOT back-filled -- back-filling
    the first dates from later ones would read forward, the trap-2 signature.

    D080 NOTE.  This anchor is a SEASON-LEVEL, DATE-INDEXED SCALAR shared by every team on a given
    date, so it CANNOT manufacture cross-sectional differences between opponents; the cross-
    sectional ranking of OCc_z within a date is identical to that of OC_z.  Unlike the `*_pregame`
    columns in pressure_lib.py (which shrink toward the CURRENT season's league mean, i.e. read
    forward), it is built only from games strictly before the date, so it is legitimate for the
    LEVEL claim as well.
    """
    z = shots[shots["zone"] == zone]
    zd = (z.groupby(["season", "game_date"]).agg(z_att=("made", "size"), z_mk=("made", "sum"))
          .reset_index())
    pdd = (shots.groupby(["season", "game_date"])
           .agg(p_att=("made", "size"), p_mk=("made", "sum")).reset_index())
    d = pdd.merge(zd, on=["season", "game_date"], how="left")
    d[["z_att", "z_mk"]] = d[["z_att", "z_mk"]].fillna(0.0)
    d = d.sort_values(["season", "game_date"], kind="stable").reset_index(drop=True)
    for c in ["z_att", "z_mk", "p_att", "p_mk"]:
        d["cum_" + c] = d.groupby("season", sort=False)[c].cumsum() - d[c]
    d["lg_prior_gap"] = (d["cum_z_mk"] / d["cum_z_att"].replace(0, np.nan)
                         - d["cum_p_mk"] / d["cum_p_att"].replace(0, np.nan))
    d["zone"] = zone
    return d[["season", "game_date", "zone", "lg_prior_gap"]]


def centred_allowance(oc_df, lg_df):
    """OCc = OC - lg_prior_gap, merged on (season, game_date, zone).  THE headline construction."""
    m = oc_df.merge(lg_df, on=["season", "game_date", "zone"], how="left")
    m["OCc"] = m["OC"] - m["lg_prior_gap"]
    return m


def crosssectional_demean(df, valcol, keys=("season", "game_date", "zone"), min_n=4):
    """ALTERNATIVE CENTRING (robustness only).  Subtract the mean of `valcol` over the OPPONENTS
    that actually appear on that (season, date, zone).  Uses only values that are themselves
    strictly prior-only, so it reads no future game; but it is a within-slate demean and therefore
    depends on WHO ELSE played that night, which is why it is secondary, not headline.
    """
    g = df.groupby(list(keys), sort=False)[valcol]
    mu = g.transform("mean")
    n = g.transform("size")
    return np.where(n >= min_n, df[valcol] - mu, np.nan)


# ------------------------------------------------------ player prior zone mix (STRICTLY PRIOR ONLY)
def player_prior_zone_mix(shots, zones=None, min_prior_att=MIN_PRIOR_ATT):
    """w_z for every (player, season, game): the share of the player's own STRICTLY PRIOR
    same-season field-goal attempts that were taken in zone z.

    TIME WINDOW: the player's own games with game_date strictly earlier in the same season
    (cumsum MINUS the current game).  The current game's realised attempts NEVER enter -- the
    realised mix is a realised-game quantity and is forbidden.  Rows with fewer than
    `min_prior_att` strictly-prior attempts get NaN and drop out.
    """
    zones = list(zones or ZONES)
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
