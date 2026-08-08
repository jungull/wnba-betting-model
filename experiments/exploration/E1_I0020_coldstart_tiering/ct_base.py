"""
E1_I0020 COLD-START TIERING -- shared loader / tier builder / placeholder builder.

QUESTION (direct user request).  "we should categorise players by ones we have sufficient data to
    model and ones that will have to be given a smart filler score maybe rookies get a placeholder
    based on their position on the team and draft position."

ANCHORS BEING REPRODUCED
    D076 (E0_I0014): the champion has NEGATIVE skill on the thinnest-experience quintile --
        minutes -15.1%, points -6.6% -- against a point-in-time prior-appearance-mean reference.
    D081 (E0_I0015): pooled points skill -0.22% is a near-cancellation; a crude splice of the
        running mean where prior appearances < 3 moves it to +1.36%, p = 0.0010.

PARTITION (GRAPH_POLICY 13.2).  Seasons 2021-2024 ONLY; the champion-forecast rows are 2022-2024
    because the 2021 fold is degenerate (n_train_rows=0, model_was_fitted=false).  2021 is used
    ONLY as a source of OBSERVED OUTCOMES to seed the walk-forward prior pool for the 2022 fold --
    never as a scored row.  Every load is value-checked with screenkit.assert_partition and an
    explicit max-date assertion.  2025/2026 rows are dropped at the FILTER-POINT in every loader
    and never enter any table, plot or description.

AUTHORISATION.  Model fitting is restricted in this program.  The coordinator scoped this work as
    distinct from that halt and the user requested it directly.  Accordingly:
      * SMALL PLACEHOLDER MODELS for the data-poor tier ARE fitted here (group means with
        shrinkage; one 3-parameter OLS on draft slot; one non-negative blend weight).
      * THE CHAMPION IS NEVER RETRAINED, MODIFIED OR REFITTED.  Its stored point forecasts
        (pts__pred_point, minutes__pred_point, fga__pred_point) are SCORED AS-IS, and its implied
        rate is the ratio of its own stored forecasts.

WALK-FORWARD RULE FOR EVERY PLACEHOLDER (trap 2 -- retrospective baselines, six instances).
    A placeholder for target season S is estimated on OBSERVED OUTCOMES FROM SEASONS < S ONLY,
    inside the 2021-2024 window:
        S = 2022 -> pool = {2021}
        S = 2023 -> pool = {2021, 2022}
        S = 2024 -> pool = {2021, 2022, 2023}
    Nothing in a placeholder for season S reads a single row of season S or later.  The
    within-season running mean (P1) is additionally .shift(1)-before-.expanding() inside
    (season, player_id), so it reads only the player's own STRICTLY PRIOR same-season games.
    The bios attributes used (draft_round, draft_number, position_raw) are fixed at or before a
    player's entry to the league and are knowable before their first game; the bios file is
    nevertheless filtered to season <= 2024 at load.

R2 CONVENTION (D069).  Plain unweighted R2, SST about the UNWEIGHTED mean.  Forecasts that already
    exist are scored with screenkit.r2_of_forecast (NOTHING refitted).  screenkit.r2_plain (which
    REFITS) is used only where a fitted model's R2 is genuinely wanted, and is labelled there.

INFERENCE.  screenkit.paired_forecast_comparison, clustered at (season, player_id).  The row-level
    null is reported alongside with its inflation factor, for contrast only.

HAZARDS honoured (inherited from D076/D081).  data/w1_truth/player_game_availability.csv and
    roster_asof.csv are asof_granularity "artifact" bound at 2026 -> UNUSABLE, NOT OPENED.
    Availability / roster membership is rebuilt from master_player box membership, as D076 did.
    master_player.pace / pace_per40 / estimated_pace are corrupt -> NOT READ.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, r"experiments\exploration\_screen_kit")
OUT = os.path.join(ROOT, r"experiments\exploration\E1_I0020_coldstart_tiering")
D076 = os.path.join(ROOT, r"experiments\exploration\E0_I0014_residual_heterogeneity")
D081 = os.path.join(ROOT, r"experiments\exploration\E0_I0015_points_skill_decomposition")
FRAME = os.path.join(D076, "analysis_frame.parquet")
DECOMP = os.path.join(D081, "decomp_frame.parquet")
MASTER = os.path.join(ROOT, r"data\masters\master_player.parquet")
BIOS = os.path.join(ROOT, r"data\reference\player_bios.csv")

if KIT not in sys.path:
    sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

SEED = 20260808
PARTITION = [2021, 2022, 2023, 2024]     # 2021 = prior-pool seed ONLY, never a scored row
SCREEN_SEASONS = [2022, 2023, 2024]      # rows the champion actually forecast
HOLDOUT = {2025, 2026}
N_DRAWS = 2000
SHRINK_K = 200.0                         # preregistered; sensitivity swept in s03
TARGETS = ["pts", "minutes", "ppm"]

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True
pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 80)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def guard(df, where, col="season"):
    """VALUE test.  Never a text/regex scan of file contents (trap 3, failed 4x in this program)."""
    s = set(int(x) for x in pd.unique(df[col]))
    bad = s & HOLDOUT
    if bad:
        raise SystemExit("PARTITION VIOLATION at %s: %s" % (where, sorted(bad)))
    print("  guard ok  %-52s n=%-7d seasons=%s" % (where, len(df), sorted(s)))


# --- KIT DEFECT K4 WORKAROUND.  See KIT_DEFECT_K4_REPRO.py and NOTES.md. --------------------
# `sk.assert_partition` raises PartitionViolation on clean 2021-2024 data whenever the frame carries
# a YEAR-VALUED PLAYER ATTRIBUTE such as `draft_year`, because a draft year legitimately PREDATES
# the partition.  The obvious workaround -- season_cols=["season"] -- is a FALSE-PASS DOOR: it also
# silences genuine 2026 leaks in columns the caller did not think to name (reproduction 4).
# So this screen keeps the guard ON and adjudicates its output instead, under an explicit rule:
#   * any flagged value >= min(HOLDOUT) is FATAL, in any column, always;
#   * a flagged column is tolerated ONLY if it is on ATTRIBUTE_YEAR_COLS *and* every flagged value
#     is strictly EARLIER than the partition;
#   * anything else is FATAL.
# The strict, unmodified kit check is ALSO run on the frame with the allowlisted columns dropped,
# so nothing else in the frame gets a weaker check than it would have had.
ATTRIBUTE_YEAR_COLS = {"draft_year"}     # adjudicated one at a time; never a blanket exemption


def assert_partition_adjudicated(df, where="", verbose=True):
    rep = sk.assert_partition(df, raise_on_violation=False, verbose=False)
    tolerated, fatal = [], []
    for c in ATTRIBUTE_YEAR_COLS & set(df.columns):
        v = pd.to_numeric(df[c], errors="coerce").dropna()
        vs = set(int(x) for x in v.unique())
        bad_future = sorted(x for x in vs if x >= min(HOLDOUT))
        if bad_future:
            fatal.append("%s holds HOLDOUT-SEASON values %s" % (c, bad_future))
        else:
            tolerated.append((c, sorted(vs)))
    strict = df.drop(columns=[c for c in ATTRIBUTE_YEAR_COLS if c in df.columns])
    strict_rep = sk.assert_partition(strict, raise_on_violation=False, verbose=False)
    if strict_rep["violations"]:
        fatal.extend(strict_rep["violations"])
    if fatal:
        raise SystemExit("PARTITION VIOLATION at %s: %s" % (where, fatal))
    if verbose:
        print("  assert_partition (adjudicated) at %-28s -> PASS  strict-on-remainder=PASS"
              % (where or "frame"))
        for c, vs in tolerated:
            print("     tolerated attribute-year column %-14s VALUES=%s..%s  (all strictly BEFORE "
                  "the partition; K4)" % (c, min(vs), max(vs)))
    return {"kit_report": rep, "strict_report_on_remainder": strict_rep,
            "tolerated_attribute_year_cols": {c: vs for c, vs in tolerated}}


def jdump(obj, name):
    p = os.path.join(OUT, name)
    with open(p, "w") as fh:
        json.dump(obj, fh, indent=2, default=_jsan)
    print("  wrote %s" % name)
    return p


def _jsan(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (pd.Timestamp,)):
        return str(o)
    return str(o)


def wcsv(df, name):
    if "season" in df.columns:
        guard(df, "write:" + name)
    df.to_csv(os.path.join(OUT, name), index=False)
    print("  wrote %s (%d rows)" % (name, len(df)))


# ============================================================================ loaders
def load_frame(verbose=True):
    """D076's FROZEN analysis frame.  READ ONLY.  13,879 appeared player-games, 2022-2024."""
    f = pd.read_parquet(FRAME)
    f = f.sort_values(["season", "player_id", "gdate"]).reset_index(drop=True)
    sk.assert_partition(f, verbose=verbose)
    assert set(int(x) for x in f["season"].unique()) <= set(SCREEN_SEASONS)
    assert f["gdate"].max() < pd.Timestamp("2025-01-01")
    assert (f["y_minutes"] > 0).all()
    if verbose:
        print("  analysis_frame  shape=%s  seasons=%s  max_date=%s"
              % (f.shape, sorted(f["season"].unique()), f["gdate"].max().date()))
    return f


def load_master(verbose=True):
    """master_player, FILTERED to 2021-2024 at the filter-point.  Manifest is asof_granularity=row.

    Used for (a) 2021 observed outcomes to seed the 2022 prior pool, (b) box membership -> roster,
    from which the point-in-time depth chart is rebuilt (D076's approach; the w1_truth roster
    artifacts are artifact-granular at 2026 and are NOT opened).
    """
    m = sk.check_manifest(MASTER, verbose=verbose)
    if m.get("status") not in ("ROW_LEVEL_USABLE_IF_FILTERED", "USABLE_IF_FILTERED", "row"):
        print("  check_manifest status: %s" % m.get("status"))
    mp = pd.read_parquet(MASTER)
    mp = mp[mp["season"].isin(PARTITION)].copy()                        # FILTER-POINT
    mp["gdate"] = pd.to_datetime(mp["game_date"])
    assert mp["gdate"].max() < pd.Timestamp("2025-01-01"), "date bound violated"
    mp["minutes"] = pd.to_numeric(mp["minutes"], errors="coerce").fillna(0.0)
    mp["pts"] = pd.to_numeric(mp["pts"], errors="coerce")
    mp["fga"] = pd.to_numeric(mp["fga"], errors="coerce")
    mp["appeared"] = mp["minutes"] > 0
    guard(mp, "master_player after load")
    return mp


def load_bios(verbose=True):
    """player_bios, FILTERED to season <= 2024 at the filter-point.

    NOTE, reported honestly: this file has NO sibling manifest -> screenkit.check_manifest returns
    UNVERIFIABLE, which is NEVER a pass.  The structural argument for using it anyway is made and
    tested in s02 on COLUMN VALUES (age advances by +1 per season for 78% of consecutive
    player-season pairs, height/weight vary within player across seasons), which is inconsistent
    with a replicated current-state pull.  draft_round / draft_number / draft_year are constant
    within player, as immutable facts must be.
    """
    b = pd.read_csv(BIOS)
    b = b[b["season"].isin(PARTITION)].copy()                           # FILTER-POINT
    guard(b, "player_bios after load")
    b["position_raw"] = b["position_raw"].fillna("UNKNOWN")
    b["pos_group"] = b["position_raw"].str.split("-").str[0].str.upper().str[0]  # G / F / C / U
    b["pos_full"] = b["position_raw"].str.upper()
    b["undrafted"] = b["draft_number"].isna().astype(float)
    b["draft_pick"] = b["draft_number"]
    if verbose:
        print("  player_bios  shape=%s  seasons=%s" % (b.shape, sorted(b["season"].unique())))
    return b


# ============================================================================ derived, point-in-time
def build_depth_chart(mp, verbose=True):
    """POINT-IN-TIME depth-chart rank inside the player's own roster, from PRIOR games only.

    Construction, per (season, team_id), in date order:
      minutes_prior_mean = expanding mean of the player's own STRICTLY PRIOR same-season appearance
                           minutes  (.shift(1) BEFORE .expanding(), appearances only);
      depth_rank         = dense rank (1 = most prior minutes) of that quantity among the players
                           IN THAT TEAM'S BOX FOR THAT GAME who have >=1 prior appearance;
      players with ZERO prior same-season appearances are UNRANKED and take depth_bucket 0.
    depth_bucket = 0 for unranked, else min(depth_rank, 11).

    Reads: the player's own prior same-season games, and prior same-season games of teammates on
    the same roster.  Reads NOTHING from the current game or any later game.  Box membership is
    used only as the roster list -- who was in uniform is knowable at tip-off.
    """
    d = mp.sort_values(["season", "player_id", "gdate", "game_id"]).copy()
    d["_ap"] = d["appeared"].astype(float)
    d["_apmin"] = d["_ap"] * d["minutes"]
    g = d.groupby(["season", "player_id"], sort=False)
    n_prior = g["_ap"].transform(lambda x: x.shift(1).cumsum()).fillna(0.0)
    m_prior = g["_apmin"].transform(lambda x: x.shift(1).cumsum()).fillna(0.0)
    d["mp_prior_games"] = n_prior
    d["mp_prior_minutes"] = m_prior
    d["mp_prior_min_mean"] = np.where(n_prior > 0, m_prior / n_prior.replace(0, np.nan), np.nan)

    # career (inside the 2021-2024 window) prior appearances
    d = d.sort_values(["player_id", "gdate", "game_id"])
    d["mp_career_prior_games"] = d.groupby("player_id", sort=False)["_ap"].transform(
        lambda x: x.shift(1).cumsum()).fillna(0.0)
    d["mp_career_prior_minutes"] = d.groupby("player_id", sort=False)["_apmin"].transform(
        lambda x: x.shift(1).cumsum()).fillna(0.0)

    # rank inside (game_id, team_id) among players with prior appearances
    d["depth_rank"] = d.groupby(["game_id", "team_id"], sort=False)["mp_prior_min_mean"].rank(
        ascending=False, method="dense")
    d["depth_bucket"] = np.where(d["depth_rank"].notna(),
                                 np.minimum(d["depth_rank"].fillna(99), 11.0), 0.0)
    d["roster_size"] = d.groupby(["game_id", "team_id"], sort=False)["player_id"].transform("size")
    if verbose:
        print("  depth chart built: depth_bucket distribution (all master rows 2021-2024)")
        print(d["depth_bucket"].value_counts().sort_index().to_string())
    return d[["game_id", "team_id", "player_id", "season", "gdate", "appeared", "minutes",
              "pts", "fga", "mp_prior_games", "mp_prior_minutes", "mp_prior_min_mean",
              "mp_career_prior_games", "mp_career_prior_minutes", "depth_rank", "depth_bucket",
              "roster_size"]].copy()


def attach_bios(df, bios):
    """Season-level join, with a STRICTLY-EARLIER-SEASON fallback (never a later season)."""
    cols = ["player_id", "season", "pos_group", "pos_full", "draft_round", "draft_pick",
            "undrafted", "draft_year"]
    out = df.merge(bios[cols], on=["player_id", "season"], how="left")
    miss = out["pos_group"].isna()
    if miss.any():
        # fallback: that player's most recent STRICTLY EARLIER bios season
        b = bios[cols].sort_values(["player_id", "season"])
        recs = []
        for pid, grp in b.groupby("player_id", sort=False):
            recs.append(grp)
        fill = out.loc[miss, ["player_id", "season"]].copy()
        fill["_i"] = fill.index
        merged = fill.merge(b, on="player_id", how="left", suffixes=("", "_b"))
        merged = merged[merged["season_b"] < merged["season"]] if "season_b" in merged else merged
        if len(merged):
            merged = merged.sort_values(["_i", "season_b"]).groupby("_i").tail(1).set_index("_i")
            for c in ["pos_group", "pos_full", "draft_round", "draft_pick", "undrafted",
                      "draft_year"]:
                out.loc[merged.index, c] = merged[c]
    out["pos_group"] = out["pos_group"].fillna("U")
    out["pos_full"] = out["pos_full"].fillna("UNKNOWN")
    out["undrafted"] = out["undrafted"].fillna(1.0)
    return out


# ============================================================================ placeholder estimation
def _shrunk_group_mean(pool, keycols, valcol, mu, k=SHRINK_K):
    """Empirical-Bayes-flavoured group mean shrunk toward the pool mean `mu`.

    mean_g = (sum_g + k*mu) / (n_g + k).  k is in units of player-games.  k=0 is the raw mean.
    Fitted on `pool` ONLY -- and `pool` is always strictly-prior seasons.
    """
    g = pool.groupby(keycols, dropna=False)[valcol].agg(["sum", "count"])
    g["est"] = (g["sum"] + k * mu) / (g["count"] + k)
    return g["est"], g["count"]


def _ols(X, y):
    """Plain OLS with intercept, lstsq.  Returns coefficient vector [b0, b1, ...]."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    A = np.column_stack([np.ones(len(X)), X]) if X.ndim > 1 else np.column_stack(
        [np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    return beta


def _apply_ols(beta, X):
    X = np.asarray(X, float)
    A = np.column_stack([np.ones(len(X)), X])
    return A @ beta


def fit_priors_for_season(pool, season, k=SHRINK_K, verbose=False):
    """Estimate every structural placeholder for target `season` on `pool` (seasons < season).

    `pool` must already be restricted to appeared player-games of STRICTLY EARLIER seasons and must
    already carry pos_group / pos_full / draft_round / draft_pick / undrafted / depth_bucket.

    Returns a dict of lookup objects; nothing here reads `season` or later.
    """
    assert len(pool) and int(pool["season"].max()) < int(season), \
        "prior pool for %s contains season >= %s" % (season, season)
    P = {}
    P["season"] = int(season)
    P["pool_seasons"] = sorted(int(s) for s in pool["season"].unique())
    P["pool_rows"] = int(len(pool))
    for t in TARGETS:
        v = pool["t_" + t]
        mu = float(v.mean())
        P[t] = {"league_mean": mu}
        # ---- P2 position prior (pos_group and full listed position) ----
        est, cnt = _shrunk_group_mean(pool, ["pos_group"], "t_" + t, mu, k)
        P[t]["pos_group"] = est.to_dict()
        P[t]["pos_group_n"] = cnt.to_dict()
        est, cnt = _shrunk_group_mean(pool, ["pos_full"], "t_" + t, mu, k)
        P[t]["pos_full"] = est.to_dict()
        # ---- P3 draft prior: binned (round x pick bucket) and a 3-parameter OLS on log pick ----
        est, cnt = _shrunk_group_mean(pool, ["draft_bucket"], "t_" + t, mu, k)
        P[t]["draft_bucket"] = est.to_dict()
        P[t]["draft_bucket_n"] = cnt.to_dict()
        dr = pool[pool["undrafted"] < 0.5]
        if len(dr) > 30:
            X = np.column_stack([np.log(dr["draft_pick"].to_numpy(float)),
                                 (dr["draft_round"].to_numpy(float) >= 2).astype(float)])
            P[t]["draft_ols_beta"] = _ols(X, dr["t_" + t].to_numpy(float)).tolist()
        else:
            P[t]["draft_ols_beta"] = None
        P[t]["undrafted_mean"] = float(pool.loc[pool["undrafted"] >= 0.5, "t_" + t].mean()) \
            if (pool["undrafted"] >= 0.5).any() else mu
        # ---- P4 team-role / depth-chart prior ----
        est, cnt = _shrunk_group_mean(pool, ["depth_bucket"], "t_" + t, mu, k)
        P[t]["depth_bucket"] = est.to_dict()
        P[t]["depth_bucket_n"] = cnt.to_dict()
        # ---- P5 combination: OLS of target on the three priors, fitted IN the pool ----
        #      (the pool rows' own priors are themselves estimated on the pool -- see NOTES.md
        #       "in-pool prior estimation" for why this is a level-only risk, and the leave-one-
        #       season-out variant that bounds it.)
    if verbose:
        print("    priors for %s from pool seasons %s (%d rows)"
              % (season, P["pool_seasons"], P["pool_rows"]))
    return P


DRAFT_BUCKET_EDGES = [0.5, 4.5, 8.5, 12.5, 20.5, 40.5]
DRAFT_BUCKET_LABELS = ["p01_04", "p05_08", "p09_12", "p13_20", "p21_plus"]


def add_draft_bucket(df):
    b = pd.cut(df["draft_pick"], bins=DRAFT_BUCKET_EDGES, labels=DRAFT_BUCKET_LABELS)
    df = df.copy()
    df["draft_bucket"] = b.astype(object).where(df["undrafted"] < 0.5, "undrafted")
    df["draft_bucket"] = df["draft_bucket"].fillna("undrafted")
    return df


def apply_priors(rows, P, t):
    """Map each row to its structural placeholder values under the priors `P` for target `t`."""
    d = P[t]
    mu = d["league_mean"]
    out = {}
    out["league"] = np.full(len(rows), mu, float)
    out["pos"] = rows["pos_group"].map(d["pos_group"]).astype(float).fillna(mu).to_numpy()
    out["pos_full"] = rows["pos_full"].map(d["pos_full"]).astype(float).fillna(mu).to_numpy()
    out["draft_bin"] = rows["draft_bucket"].map(d["draft_bucket"]).astype(float).fillna(mu).to_numpy()
    out["depth"] = rows["depth_bucket"].map(d["depth_bucket"]).astype(float).fillna(mu).to_numpy()
    beta = d["draft_ols_beta"]
    if beta is not None:
        pick = rows["draft_pick"].to_numpy(float)
        rnd2 = (rows["draft_round"].to_numpy(float) >= 2).astype(float)
        safe = np.where(np.isfinite(pick) & (pick > 0), pick, 1.0)
        v = _apply_ols(np.array(beta, float),
                       np.column_stack([np.log(safe), np.nan_to_num(rnd2)]))
        v = np.where(rows["undrafted"].to_numpy(float) >= 0.5, d["undrafted_mean"], v)
        out["draft_ols"] = v
    else:
        out["draft_ols"] = out["draft_bin"]
    return out


# ============================================================================ scoring
def mae(y, yhat):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yhat)
    return float(np.mean(np.abs(y[m] - yhat[m])))


def skill_mae(y, yhat_model, yhat_ref):
    """1 - MAE_model/MAE_ref, both on the SAME rows.  D076's convention, kept for continuity."""
    mm, mr = mae(y, yhat_model), mae(y, yhat_ref)
    return float(1.0 - mm / mr), mm, mr


def r2f(y, yhat):
    """screenkit.r2_of_forecast -- scores a GIVEN forecast, fits nothing (D069 denominator)."""
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yhat)
    return float(sk.r2_of_forecast(y[m], yhat[m]))


def block_codes(f, cols=("season", "player_id")):
    return sk._group_codes(f, list(cols))


def paired(y, a, b, groups, name_a="A", name_b="B", n_draws=N_DRAWS, seed=SEED):
    """Kit paired cluster sign-flip, plus the row-level contrast the kit reports alongside."""
    r = sk.paired_forecast_comparison(np.asarray(y, float), np.asarray(a, float),
                                      np.asarray(b, float), groups=groups,
                                      n_draws=n_draws, seed=seed, name_a=name_a, name_b=name_b)
    return {kk: vv for kk, vv in r.items() if kk != "draws"}, r.get("draws")
