#!/usr/bin/env python3
"""
bottomup_3pt_channel_v1 -- player-level bottom-up 3pt channel vs the incumbent
team-level structural 3pt chain. The first true test of the V4 bottom-up thesis.

Registered 2026-07-30T21:05:19Z in experiments/registry.jsonl (regime B,
primary metric threep_channel_mae, incumbent chanreval_structural_3pt_chain,
thresholds: min_improvement 0.10 / harm_ci_bound 0.05 / per_season_tolerance
0.15 / coverage_tolerance 0.0). This script never registers; it evaluates.
Every construction below follows the registration record verbatim.

THE CHALLENGER (per registration)
  team 3pt points =
      [ 3.0 * SUM over covered players( rate3pa_asof * pct3_shrunk * exp_min )
        + (200 - SUM covered exp_min) * team_3pt_pts_per_min_trend ]
      * (opp_fg3a_allow / lg_fg3a)          <- the incumbent chain's structural
                                               opponent-allowed factor, unchanged,
                                               applied ONCE at team level
  where, all strictly shifted within (player, season) / (team, season):
    rate3pa_asof   EWMA of per-minute 3PA rate on played rows, alpha tuned on
                   2021-2023 only via evalharness.inner_tuning_splits
    pct3_shrunk    empirical-Bayes 3P%: player cum makes/attempts shrunk toward
                   the team-season prior, itself shrunk toward the league prior
                   (strictly-earlier-dates running ratio); single count K tuned
                   on 2021-2023 only
    exp_min        p_plays * min_ewma(alpha=0.30 frozen), both consumed from the
                   committed Stage-A artifact
                   experiments/minutes_twostage/test_predictions_m2.csv
    team trend     shifted EWMA of (ch_3pt / actual team minutes), alpha tuned
                   on 2021-2023 only

UNIVERSE  regular-season chanreval test team-games only: season in {2024,2025,
2026}, season_type == Regular Season, prior_games >= 5, not an expansion-team
fallback row, incumbent raw/str 3pt predictions defined (the chanreval
channel-table mask intersected with Regular Season).

INCUMBENT RECONCILIATION  predictions_v2.csv is game-level only (no per-channel
columns), so the incumbent 3pt chain is REBUILT here exactly per
experiments/channel_reval/run_reval.py with the recorded alphas, then verified:
  * 3pt channel raw+structural MAEs and row counts must reproduce
    channel_results_v2.csv (pooled and per season) to 1e-6  -- hard assert;
  * game-level str/raw margin calibrated predictions must reproduce
    predictions_v2.csv to 1e-6 on all 673 rows              -- hard assert;
  * calibration constants must reproduce run_summary.json    -- hard assert.

GATE 4 (joint)  challenger 3pt substituted into the 4-channel structural sum,
margin recalibrated under the train-years-only protocol. The challenger cannot
be constructed on 2021-2023 (its exp_min consumes committed Stage-A artifacts
that exist for test seasons only), so the train-only protocol here = the
incumbent's train-years margin calibration (a, b), fit on 2021-2023 games and
applied unchanged to the substituted margin. No test-year information enters
any fitted constant. The uncalibrated comparison is reported as sensitivity.

MODES
  python bottomup_3pt.py --smoke [--outdir DIR]   scratch registry copy in a
        tempdir (the real ledger is never touched) + scratch outdir
        (tempdir/out unless --outdir given)
  python bottomup_3pt.py [--outdir DIR]           real mode: records the
        evaluation on experiments/registry.jsonl via compare_to_incumbent,
        writes to experiments/bottomup_3pt/
Only compare_to_incumbent records; this script never calls registry.register/
evaluate/record_evaluation and never renders leaderboards.

Constitution: walk-forward always; every trend shifted within (player, season)
or (team, season); tuning strictly inside 2021-2023 via inner walk-forward
folds; audits before believing (shift-truncation recompute on sampled rows).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

import evalharness as eh
from evalharness.baselines import load_frozen_baselines

EXPERIMENT_ID = "bottomup_3pt_channel_v1"
CHANREVAL = REPO / "experiments" / "channel_reval"
M2_PATH = REPO / "experiments" / "minutes_twostage" / "test_predictions_m2.csv"
MASTER_PLAYER = REPO / "data" / "masters" / "master_player.parquet"
DEFAULT_OUTDIR = REPO / "experiments" / "bottomup_3pt"

TRAIN_YEARS = [2021, 2022, 2023]
TEST_YEARS = [2024, 2025, 2026]
MIN_PRIOR = 5
EXPANSION = {(2025, "GSV"), (2026, "TOR"), (2026, "PDX")}
CHANNELS = ["ft", "3pt", "paint", "np2"]
CH_ACTUAL = {"ft": "ch_ft", "3pt": "ch_3pt", "paint": "ch_paint", "np2": "ch_np2"}

RATE_ALPHAS = [0.05, 0.08, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50]
TEAM_TREND_ALPHAS = [0.05, 0.08, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50]
# K grid runs to an effectively-infinite sentinel (player identity ignored,
# pure team-season prior) so the train-only curve can bracket its optimum or
# demonstrate a monotone asymptote instead of clipping at an arbitrary edge.
K_GRID = [2.0, 5.0, 10.0, 20.0, 40.0, 80.0, 160.0, 320.0, 640.0, 1280.0,
          2560.0, 5120.0, 1.0e9]
MIN_EWMA_ALPHA = 0.30            # frozen per registration; consumed, not refit

AUDIT_SEED = 20260730
AUDIT_TEAMROWS_PER_SEASON = 20
AUDIT_PLAYERS_PER_ROW = 3
SAMPLE_SEED = 20260730
REG_MINUTES = 200.0

STAT_COLS = [  # verbatim from run_reval.py -- the raw inputs its pipeline reads
    "team_pf", "team_pfd", "team_fta", "team_ftm", "team_ft_pct", "team_fg3a", "team_fg3m",
    "team_fga", "team_fgm", "team_pts_paint", "team_pts",
    "ch_ft", "ch_3pt", "ch_paint", "ch_np2", "pts_2s",
    "opp_pf", "opp_fta", "opp_fg3a", "opp_fg3m", "opp_ftm",
    "opp_ch_3pt", "opp_ch_paint", "opp_ch_np2", "opp_ch_ft", "opp_pts",
]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# incumbent pipeline -- faithful replica of experiments/channel_reval/run_reval.py
# ---------------------------------------------------------------------------

def load_base() -> pd.DataFrame:
    D = pd.read_csv(CHANREVAL / "channel_base_v2.csv", parse_dates=["GAME_DATE"])
    D = D.sort_values(["TEAM_ID", "GAME_DATE", "GAME_ID"]).reset_index(drop=True)
    D[STAT_COLS] = D[STAT_COLS].astype(float)
    D["season"] = D["year"]
    D["prior_games"] = D.groupby(["TEAM_ID", "season"]).cumcount()
    is_exp = [(s, a) in EXPANSION for s, a in zip(D.season, D.TEAM_ABBREVIATION)]
    D["is_expansion_season"] = np.array(is_exp, dtype=bool)
    D["fallback_row"] = D.is_expansion_season & (D.prior_games < MIN_PRIOR)
    return D


def ewma_shifted(s: pd.Series, alpha: float) -> pd.Series:
    return s.ewm(alpha=alpha, adjust=True).mean().shift(1)


def add_trend(df: pd.DataFrame, col: str, alpha: float, out: str) -> None:
    df[out] = df.groupby(["TEAM_ID", "season"], sort=False)[col].transform(
        lambda s: ewma_shifted(s, alpha)
    )


def league_running_strict(df: pd.DataFrame, col: str) -> pd.Series:
    g = df.groupby(["season", "GAME_DATE"])[col].agg(["sum", "count"]).sort_index()
    cs = g.groupby(level="season")[["sum", "count"]].cumsum()
    cs = cs.groupby(level="season").shift(1)
    lg = cs["sum"] / cs["count"]
    key = pd.MultiIndex.from_arrays([df["season"], df["GAME_DATE"]])
    return pd.Series(lg.reindex(key).to_numpy(), index=df.index)


def league_running_ratio_strict(df: pd.DataFrame, num_col: str, den_col: str) -> pd.Series:
    """Per-season league ratio sum(num)/sum(den) over STRICTLY EARLIER dates
    (ratio of sums -- the natural league 3P% prior). NaN on each season's
    first date."""
    g = df.groupby(["season", "GAME_DATE"])[[num_col, den_col]].sum().sort_index()
    cs = g.groupby(level="season").cumsum().groupby(level="season").shift(1)
    ratio = cs[num_col] / cs[den_col]
    key = pd.MultiIndex.from_arrays([df["season"], df["GAME_DATE"]])
    return pd.Series(ratio.reindex(key).to_numpy(), index=df.index)


def build_features(D0: pd.DataFrame, alphas: dict, fallback: bool = True) -> pd.DataFrame:
    """Verbatim replica of run_reval.build_features (incumbent chains)."""
    D = D0.copy()
    a_ft, a_3pt, a_paint, a_np2 = (alphas[c] for c in CHANNELS)

    add_trend(D, "ch_ft", a_ft, "raw_ft")
    add_trend(D, "ch_3pt", a_3pt, "raw_3pt")
    add_trend(D, "ch_paint", a_paint, "raw_paint")
    add_trend(D, "ch_np2", a_np2, "raw_np2")

    for col, out in [
        ("team_pf", "lg_pf"), ("team_fta", "lg_fta"), ("team_ft_pct", "lg_ftpct"),
        ("team_fg3a", "lg_fg3a"), ("team_fg3m", "lg_fg3m"),
        ("ch_ft", "lg_ft"), ("ch_3pt", "lg_3pt"), ("ch_paint", "lg_paint"), ("ch_np2", "lg_np2"),
    ]:
        D[out] = league_running_strict(D, col)

    add_trend(D, "team_fta", a_ft, "fta_t")
    add_trend(D, "team_ft_pct", a_ft, "ftpct_t")
    add_trend(D, "team_pf", a_ft, "pf_t")
    add_trend(D, "team_fg3a", a_3pt, "fg3a_t")
    add_trend(D, "team_fg3m", a_3pt, "fg3m_t")
    add_trend(D, "opp_fg3a", a_3pt, "fg3a_allow_t")
    add_trend(D, "opp_ch_paint", a_paint, "paint_allow_t")
    add_trend(D, "opp_ch_np2", a_np2, "np2_allow_t")

    if fallback:
        fb = D["fallback_row"].to_numpy()
        for feat, lg in [
            ("raw_ft", "lg_ft"), ("raw_3pt", "lg_3pt"), ("raw_paint", "lg_paint"), ("raw_np2", "lg_np2"),
            ("fta_t", "lg_fta"), ("ftpct_t", "lg_ftpct"), ("pf_t", "lg_pf"),
            ("fg3a_t", "lg_fg3a"), ("fg3m_t", "lg_fg3m"),
            ("fg3a_allow_t", "lg_fg3a"), ("paint_allow_t", "lg_paint"), ("np2_allow_t", "lg_np2"),
        ]:
            D.loc[fb, feat] = D.loc[fb, lg]

    for src, out in [
        ("pf_t", "opp_pf_trend"), ("fg3a_allow_t", "opp_fg3a_allow"),
        ("paint_allow_t", "opp_paint_allow"), ("np2_allow_t", "opp_np2_allow"),
    ]:
        mp = D[["GAME_ID", "TEAM_ID", src]].rename(columns={"TEAM_ID": "OPP_TEAM_ID", src: out})
        D = D.merge(mp, on=["GAME_ID", "OPP_TEAM_ID"], how="left")

    D["fg3pct_t"] = D["fg3m_t"] / D["fg3a_t"]
    D["str_ft"] = D["fta_t"] * (D["opp_pf_trend"] / D["lg_pf"]) * D["ftpct_t"]
    D["str_3pt"] = D["fg3a_t"] * (D["opp_fg3a_allow"] / D["lg_fg3a"]) * D["fg3pct_t"] * 3.0
    D["str_paint"] = D["raw_paint"] * (D["opp_paint_allow"] / D["lg_paint"])
    D["str_np2"] = D["raw_np2"] * (D["opp_np2_allow"] / D["lg_np2"])

    if not (D.index == D0.index).all():
        raise RuntimeError("feature pipeline broke row alignment")
    return D


def make_games(F: pd.DataFrame) -> pd.DataFrame:
    """Verbatim replica of run_reval.make_games."""
    F = F.copy()
    F["row_ok"] = (F.prior_games >= MIN_PRIOR) | F.fallback_row
    for p in ("raw", "str"):
        cols = [f"{p}_{c}" for c in CHANNELS]
        F[f"{p}_ok"] = F[cols].notna().all(axis=1)
        F[f"{p}_sum"] = F[cols].sum(axis=1)
    keep = (["GAME_ID", "TEAM_ID", "TEAM_ABBREVIATION", "GAME_DATE", "season", "season_type",
             "is_home", "team_pts", "prior_games", "fallback_row", "row_ok", "raw_ok", "str_ok",
             "raw_sum", "str_sum"]
            + [f"{p}_{c}" for p in ("raw", "str") for c in CHANNELS] + [CH_ACTUAL[c] for c in CHANNELS])
    home = F.loc[F.is_home == 1, keep].add_suffix("_h").rename(columns={"GAME_ID_h": "GAME_ID"})
    away = F.loc[F.is_home == 0, keep].add_suffix("_a").rename(columns={"GAME_ID_a": "GAME_ID"})
    g = home.merge(away, on="GAME_ID", validate="one_to_one")
    g["eligible"] = (g.row_ok_h & g.row_ok_a & g.raw_ok_h & g.raw_ok_a & g.str_ok_h & g.str_ok_a)
    g["any_fallback"] = g.fallback_row_h | g.fallback_row_a
    g["margin_true"] = g.team_pts_h - g.team_pts_a
    g["total_true"] = g.team_pts_h + g.team_pts_a
    for p in ("raw", "str"):
        g[f"{p}_margin_uncal"] = g[f"{p}_sum_h"] - g[f"{p}_sum_a"]
    return g


def linfit(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    slope, intercept = np.polyfit(np.asarray(x, float), np.asarray(y, float), 1)
    return float(intercept), float(slope)


def mae(err: pd.Series) -> float:
    return float(err.abs().mean())


def channel_mask_3pt(F: pd.DataFrame) -> pd.Series:
    """The chanreval channel-table row mask for the 3pt channel (verbatim:
    test seasons, >=5 prior team games, no fallback rows, predictions and
    actuals defined; playoffs INCLUDED -- this mask exists to reproduce the
    recorded numbers)."""
    return (F.season.isin(TEST_YEARS) & (F.prior_games >= MIN_PRIOR) & ~F.fallback_row
            & F["ch_3pt"].notna() & F["raw_3pt"].notna() & F["str_3pt"].notna())


def reconcile_incumbent(F: pd.DataFrame, games_cal: pd.DataFrame, cal: dict) -> dict:
    """Hard asserts: rebuilt incumbent must reproduce the recorded artifacts."""
    rec = {"checked_at": utcnow_iso()}

    # --- channel_results_v2.csv, 3pt rows, pooled + per season -------------
    C = pd.read_csv(CHANREVAL / "channel_results_v2.csv")
    C3 = C[C.channel == "3pt"].set_index("scope")
    m_all = channel_mask_3pt(F)
    scopes = {"2024-2026 pooled": m_all}
    for s in TEST_YEARS:
        scopes[str(s)] = m_all & (F.season == s)
    ch_rows = []
    for scope, m in scopes.items():
        err_r = (F.loc[m, "raw_3pt"] - F.loc[m, "ch_3pt"]).abs()
        err_s = (F.loc[m, "str_3pt"] - F.loc[m, "ch_3pt"]).abs()
        ours = {"n": int(m.sum()), "mae_raw": float(err_r.mean()),
                "mae_structural": float(err_s.mean())}
        theirs = C3.loc[scope]
        assert ours["n"] == int(theirs.n_test_rows), \
            f"3pt {scope}: n {ours['n']} != recorded {int(theirs.n_test_rows)}"
        assert abs(ours["mae_raw"] - theirs.mae_raw) < 1e-6, \
            f"3pt {scope}: raw MAE {ours['mae_raw']:.8f} != recorded {theirs.mae_raw:.8f}"
        assert abs(ours["mae_structural"] - theirs.mae_structural) < 1e-6, \
            f"3pt {scope}: str MAE {ours['mae_structural']:.8f} != recorded {theirs.mae_structural:.8f}"
        ch_rows.append({"scope": scope, **ours,
                        "recorded_mae_structural": float(theirs.mae_structural)})
    rec["channel_table_3pt"] = ch_rows

    # --- run_summary.json calibration constants ----------------------------
    S = json.load(open(CHANREVAL / "run_summary.json", encoding="utf-8"))
    for key in ("raw_margin", "str_margin"):
        a_rec, b_rec = S["calibration"][key]
        a_our, b_our = cal[key]
        assert abs(a_our - a_rec) < 1e-9 and abs(b_our - b_rec) < 1e-9, \
            f"calibration {key}: ours ({a_our}, {b_our}) != recorded ({a_rec}, {b_rec})"
    rec["calibration"] = {k: list(cal[k]) for k in ("raw_margin", "str_margin")}
    rec["recorded_alphas"] = dict(S["alphas"])

    # --- predictions_v2.csv game-level reproduction ------------------------
    P = pd.read_csv(CHANREVAL / "predictions_v2.csv")
    ours = games_cal[["GAME_ID", "str_margin_cal", "raw_margin_cal",
                      "str_home_cal", "str_away_cal"]]
    j = P.merge(ours, on="GAME_ID", how="left", suffixes=("_rec", "_our"))
    assert len(j) == len(P) and j.str_margin_cal_our.notna().all(), \
        "rebuilt games frame does not cover every recorded prediction row"
    for col in ("str_margin_cal", "raw_margin_cal", "str_home_cal", "str_away_cal"):
        d = (j[f"{col}_rec"] - j[f"{col}_our"]).abs().max()
        assert d < 1e-6, f"predictions_v2 {col}: max |recorded - rebuilt| = {d}"
    rec["predictions_v2_rows_matched"] = int(len(j))
    rec["predictions_v2_max_abs_diff"] = float(max(
        (j[f"{c}_rec"] - j[f"{c}_our"]).abs().max()
        for c in ("str_margin_cal", "raw_margin_cal", "str_home_cal", "str_away_cal")))
    return rec


# ---------------------------------------------------------------------------
# player-level machinery
# ---------------------------------------------------------------------------

def load_master_player() -> pd.DataFrame:
    mp = pd.read_parquet(MASTER_PLAYER, columns=[
        "game_id", "season", "season_type", "game_date", "team_id",
        "team_abbreviation", "opp_team_id", "player_id", "player_name",
        "minutes", "fg3a", "fg3m"])
    mp["game_id"] = mp.game_id.astype("int64")
    mp["team_id"] = mp.team_id.astype("int64")
    mp["player_id"] = mp.player_id.astype("int64")
    mp["game_date"] = pd.to_datetime(mp.game_date)
    assert not mp.duplicated(["game_id", "player_id"]).any()
    return mp


def build_played_frame(mp: pd.DataFrame) -> pd.DataFrame:
    """Played regular-season rows with per-minute 3PA rate; sorted for
    group-wise shifted transforms. minutes==0 rows (rounded-down sub-minute
    stints, 4 rows) are dropped: a per-minute rate is undefined at 0 minutes."""
    P = mp[(mp.season_type == "Regular Season") & mp.minutes.notna() & (mp.minutes > 0)].copy()
    P = P.sort_values(["player_id", "season", "game_date"]).reset_index(drop=True)
    assert not P.duplicated(["player_id", "season", "game_date"]).any()
    P["rate3pa"] = P.fg3a / P.minutes
    return P


def add_player_shifted(P: pd.DataFrame, alpha: float) -> pd.DataFrame:
    """Shifted-at-row player features on played rows (for train-year tuning):
    EWMA of per-minute 3PA rate and cumulative 3PA/3PM, all strictly prior,
    within (player, season)."""
    P = P.copy()
    g = P.groupby(["player_id", "season"], sort=False)
    P["rate_shift"] = g["rate3pa"].transform(lambda s: ewma_shifted(s, alpha))
    P["cum3pa_shift"] = g["fg3a"].cumsum() - P["fg3a"]
    P["cum3pm_shift"] = g["fg3m"].cumsum() - P["fg3m"]
    return P


def add_player_post(P: pd.DataFrame, alpha: float) -> pd.DataFrame:
    """POST values (including the row's own game) on played rows; consumed
    as-of (strictly before the target date) by merge_asof."""
    P = P.copy()
    g = P.groupby(["player_id", "season"], sort=False)
    P["post_rate_ewma"] = g["rate3pa"].transform(
        lambda s: s.ewm(alpha=alpha, adjust=True).mean())
    P["post_cum3pa"] = g["fg3a"].cumsum()
    P["post_cum3pm"] = g["fg3m"].cumsum()
    return P


def asof_player_features(target: pd.DataFrame, P_post: pd.DataFrame) -> pd.DataFrame:
    """As-of merge: for each target (player, season, date) row take the
    player's most recent PLAYED game strictly before the target date."""
    right = P_post[["player_id", "season", "game_date",
                    "post_rate_ewma", "post_cum3pa", "post_cum3pm"]].sort_values("game_date")
    left = target.sort_values("game_date").copy()
    out = pd.merge_asof(
        left, right, on="game_date", by=["player_id", "season"],
        allow_exact_matches=False, direction="backward",
    )
    return out.rename(columns={
        "post_rate_ewma": "rate3pa_asof",
        "post_cum3pa": "cum3pa_asof", "post_cum3pm": "cum3pm_asof"})


def add_team_percent_priors(F: pd.DataFrame) -> pd.DataFrame:
    """Shifted team-season cumulative 3PA/3PM and the strictly-earlier league
    3P% ratio, at every channel_base row."""
    F = F.copy()
    g = F.groupby(["TEAM_ID", "season"], sort=False)
    F["tcum3pa_shift"] = g["team_fg3a"].cumsum() - F["team_fg3a"]
    F["tcum3pm_shift"] = g["team_fg3m"].cumsum() - F["team_fg3m"]
    F["lg_3ppct_prior"] = league_running_ratio_strict(F, "team_fg3m", "team_fg3a")
    return F


def shrunk_pct(cum3pm, cum3pa, tcum3pm, tcum3pa, lg_pct, K: float):
    """Two-level empirical-Bayes 3P%: team-season prior = team counts shrunk
    toward the league prior with count K; player = player counts shrunk toward
    the team prior with the same K. Players/teams with no prior counts land on
    the level above. NaN player cums (no prior played game) are treated as
    zero counts -> pure team prior."""
    cum3pm = np.nan_to_num(np.asarray(cum3pm, float), nan=0.0)
    cum3pa = np.nan_to_num(np.asarray(cum3pa, float), nan=0.0)
    tcum3pm = np.nan_to_num(np.asarray(tcum3pm, float), nan=0.0)
    tcum3pa = np.nan_to_num(np.asarray(tcum3pa, float), nan=0.0)
    lg = np.asarray(lg_pct, float)
    team_prior = (tcum3pm + K * lg) / (tcum3pa + K)
    player = (cum3pm + K * team_prior) / (cum3pa + K)
    return player, team_prior


def add_team_trend(F: pd.DataFrame, team_minutes: pd.DataFrame, alpha: float,
                   out: str = "team_3ppm_trend") -> pd.DataFrame:
    """Shifted EWMA of team 3pt points per actual team minute, within
    (team, season). team_minutes: [game_id, team_id, team_min]."""
    F = F.copy()
    F = F.merge(team_minutes, left_on=["GAME_ID", "TEAM_ID"],
                right_on=["game_id", "team_id"], how="left").drop(columns=["game_id", "team_id"])
    assert F.team_min.notna().all(), "missing team minutes for some team-game"
    F["ch3_per_min"] = F["ch_3pt"] / F["team_min"]
    F[out] = F.groupby(["TEAM_ID", "season"], sort=False)["ch3_per_min"].transform(
        lambda s: ewma_shifted(s, alpha))
    return F


# ---------------------------------------------------------------------------
# train-only tuning (inner walk-forward folds strictly inside 2021-2023)
# ---------------------------------------------------------------------------

def outer24_and_inner(frame: pd.DataFrame, date_col: str) -> tuple:
    splits = eh.walk_forward_by_season(
        frame, date_col=date_col, season_col="season",
        min_train_seasons=3, test_seasons=[2024])
    outer24 = splits[0]
    train_seasons = sorted(frame.loc[outer24.train_idx, "season"].unique())
    assert train_seasons == TRAIN_YEARS, train_seasons
    inner = eh.inner_tuning_splits(frame, outer24, date_col=date_col, n_folds=3)
    return outer24, inner


def tune_rate_alpha(P: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    """alpha for the per-minute 3PA-rate EWMA. Objective on inner val folds:
    MAE of predicted attempts given realized minutes (rate_shift * minutes vs
    fg3a) on played rows with a defined rate -- isolates rate quality from the
    minutes model exactly as the rate is consumed (rate x minutes)."""
    _, inner = outer24_and_inner(P, "game_date")
    rows = []
    for a in RATE_ALPHAS:
        Pa = add_player_shifted(P, a)
        fold_maes = []
        for f in inner:
            val = Pa.loc[f.val_idx]
            m = val.rate_shift.notna()
            fold_maes.append(float(
                (val.loc[m, "rate_shift"] * val.loc[m, "minutes"] - val.loc[m, "fg3a"]).abs().mean()))
        rows.append({"alpha": a, "inner_mae_mean": float(np.mean(fold_maes)),
                     "inner_mae_fold1": fold_maes[0], "inner_mae_fold2": fold_maes[1],
                     "inner_mae_fold3": fold_maes[2]})
    curve = pd.DataFrame(rows)
    best = curve.loc[curve.inner_mae_mean.idxmin(), "alpha"]
    return float(best), curve


def tune_shrinkage_k(P: pd.DataFrame, F_pri: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    """K (EB counts) for the two-level 3P% shrinkage. Objective on inner val
    folds: MAE of predicted makes given realized attempts (pct * fg3a vs fg3m)
    on played rows with fg3a >= 1 and a defined league prior."""
    _, inner = outer24_and_inner(P, "game_date")
    Pk = add_player_shifted(P, 0.10)  # alpha irrelevant here; cums are alpha-free
    pri = F_pri[["GAME_ID", "TEAM_ID", "tcum3pa_shift", "tcum3pm_shift", "lg_3ppct_prior"]]
    Pk = Pk.merge(pri, left_on=["game_id", "team_id"],
                  right_on=["GAME_ID", "TEAM_ID"], how="left")
    assert len(Pk) == len(P)
    rows = []
    for K in K_GRID:
        pct, _ = shrunk_pct(Pk.cum3pm_shift, Pk.cum3pa_shift,
                            Pk.tcum3pm_shift, Pk.tcum3pa_shift, Pk.lg_3ppct_prior, K)
        Pk["pct_k"] = pct
        fold_maes = []
        for f in inner:
            val = Pk.loc[f.val_idx]
            m = (val.fg3a >= 1) & val.pct_k.notna()
            fold_maes.append(float(
                (val.loc[m, "pct_k"] * val.loc[m, "fg3a"] - val.loc[m, "fg3m"]).abs().mean()))
        rows.append({"K": K, "inner_mae_mean": float(np.mean(fold_maes)),
                     "inner_mae_fold1": fold_maes[0], "inner_mae_fold2": fold_maes[1],
                     "inner_mae_fold3": fold_maes[2]})
    curve = pd.DataFrame(rows)
    best = curve.loc[curve.inner_mae_mean.idxmin(), "K"]
    return float(best), curve


def tune_team_trend_alpha(F_rs: pd.DataFrame, team_minutes: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    """alpha for the team 3pt-points-per-minute trend (uncovered-minutes
    correction). Objective on inner val folds: MAE of trend * actual team
    minutes vs actual ch_3pt, on rows with >= MIN_PRIOR prior team games."""
    F_rs = F_rs.reset_index(drop=True)
    _, inner = outer24_and_inner(F_rs, "GAME_DATE")
    rows = []
    for a in TEAM_TREND_ALPHAS:
        Fa = add_team_trend(F_rs, team_minutes, a)
        fold_maes = []
        for f in inner:
            val = Fa.loc[f.val_idx]
            m = val.team_3ppm_trend.notna() & (val.prior_games >= MIN_PRIOR)
            fold_maes.append(float(
                (val.loc[m, "team_3ppm_trend"] * val.loc[m, "team_min"] - val.loc[m, "ch_3pt"]).abs().mean()))
        rows.append({"alpha": a, "inner_mae_mean": float(np.mean(fold_maes)),
                     "inner_mae_fold1": fold_maes[0], "inner_mae_fold2": fold_maes[1],
                     "inner_mae_fold3": fold_maes[2]})
    curve = pd.DataFrame(rows)
    best = curve.loc[curve.inner_mae_mean.idxmin(), "alpha"]
    return float(best), curve


# ---------------------------------------------------------------------------
# audits
# ---------------------------------------------------------------------------

def shift_audit(univ: pd.DataFrame, cov: pd.DataFrame, P: pd.DataFrame,
                F_full: pd.DataFrame, a_rate: float, K: float, a_team: float,
                a_3pt_inc: float) -> pd.DataFrame:
    """Truncate-and-recompute audit (constitution rule 1). For sampled universe
    team-rows: rebuild every challenger ingredient from INDEPENDENT loops over
    rows with game_date STRICTLY BEFORE the target game, and compare to the
    pipeline values. Covers: player rate EWMA, player cum 3PA/3PM, team-season
    3P% prior counts, league 3P% prior, team 3pt-per-minute trend, and the
    incumbent opponent-allowed factor ingredients (opp_fg3a_allow, lg_fg3a).
    ``F_full`` is the full channel frame carrying ch3_per_min and fallback_row."""
    rng = np.random.default_rng(AUDIT_SEED)
    sample_rows = []
    for s in TEST_YEARS:
        pool = univ.index[univ.season == s].to_numpy()
        take = min(AUDIT_TEAMROWS_PER_SEASON, len(pool))
        sample_rows.extend(rng.choice(pool, size=take, replace=False).tolist())

    P_idx = P.set_index(["player_id", "season"]).sort_index()
    F_team = F_full.set_index(["TEAM_ID", "season"]).sort_index()
    out = []

    def ew_last(vals: list[float], alpha: float) -> float:
        if not vals:
            return np.nan
        return float(pd.Series(vals, dtype=float).ewm(alpha=alpha, adjust=True).mean().iloc[-1])

    for ridx in sample_rows:
        row = univ.loc[ridx]
        t, season, team, gid = row.GAME_DATE, int(row.season), int(row.TEAM_ID), int(row.GAME_ID)

        # -- team trend, recomputed from strictly-prior rows of (team, season)
        th = F_team.loc[[(team, season)]]
        th = th[th.GAME_DATE < t].sort_values("GAME_DATE")
        trend_re = ew_last(list(th.ch3_per_min), a_team)
        out.append({"row": ridx, "check": "team_3ppm_trend", "game_id": gid,
                    "pipeline": row.team_3ppm_trend, "recomputed": trend_re,
                    "abs_diff": abs(row.team_3ppm_trend - trend_re)})

        # -- team-season 3P% prior counts + league prior
        out.append({"row": ridx, "check": "tcum3pa_shift", "game_id": gid,
                    "pipeline": row.tcum3pa_shift, "recomputed": float(th.team_fg3a.sum()),
                    "abs_diff": abs(row.tcum3pa_shift - float(th.team_fg3a.sum()))})
        lg_rows = F_full[(F_full.season == season) & (F_full.GAME_DATE < t)]
        lg_re = float(lg_rows.team_fg3m.sum()) / float(lg_rows.team_fg3a.sum())
        out.append({"row": ridx, "check": "lg_3ppct_prior", "game_id": gid,
                    "pipeline": row.lg_3ppct_prior, "recomputed": lg_re,
                    "abs_diff": abs(row.lg_3ppct_prior - lg_re)})

        # -- incumbent opponent factor ingredients. The pipeline takes
        # opp_fg3a_allow from the OPPONENT's row of this game (after the
        # expansion fallback substituted the league mean on fallback rows).
        opp = int(row.OPP_TEAM_ID)
        orow = F_full[(F_full.GAME_ID == gid) & (F_full.TEAM_ID == opp)].iloc[0]
        lg_fg3a_re = float(lg_rows.team_fg3a.mean())   # strictly-earlier team-rows
        if bool(orow.fallback_row):
            allow_re = lg_fg3a_re                      # fallback exports the league mean
        else:
            oh = F_team.loc[[(opp, season)]]
            oh = oh[oh.GAME_DATE < t].sort_values("GAME_DATE")
            allow_re = ew_last(list(oh.opp_fg3a), a_3pt_inc)
        out.append({"row": ridx, "check": "opp_fg3a_allow", "game_id": gid,
                    "pipeline": row.opp_fg3a_allow, "recomputed": allow_re,
                    "abs_diff": abs(row.opp_fg3a_allow - allow_re)})
        out.append({"row": ridx, "check": "lg_fg3a", "game_id": gid,
                    "pipeline": row.lg_fg3a, "recomputed": lg_fg3a_re,
                    "abs_diff": abs(row.lg_fg3a - lg_fg3a_re)})

        # -- player-rate features for up to AUDIT_PLAYERS_PER_ROW covered players
        crows = cov[(cov.game_id == gid) & (cov.team_id == team) & cov.rate3pa_asof.notna()]
        crows = crows.sort_values("exp_min", ascending=False).head(AUDIT_PLAYERS_PER_ROW)
        for _, pr in crows.iterrows():
            key = (int(pr.player_id), season)
            hist = P_idx.loc[[key]] if key in P_idx.index else P_idx.iloc[0:0]
            hist = hist[hist.game_date < t].sort_values("game_date")
            rate_re = ew_last(list(hist.rate3pa), a_rate)
            out.append({"row": ridx, "check": "rate3pa_asof", "game_id": gid,
                        "player_id": int(pr.player_id),
                        "pipeline": pr.rate3pa_asof, "recomputed": rate_re,
                        "abs_diff": abs(pr.rate3pa_asof - rate_re)})
            for col, src in (("cum3pa_asof", "fg3a"), ("cum3pm_asof", "fg3m")):
                v_re = float(hist[src].sum())
                v_pipe = pr[col] if pd.notna(pr[col]) else 0.0
                out.append({"row": ridx, "check": col, "game_id": gid,
                            "player_id": int(pr.player_id),
                            "pipeline": v_pipe, "recomputed": v_re,
                            "abs_diff": abs(v_pipe - v_re)})
    audit = pd.DataFrame(out)
    audit["ok"] = audit.abs_diff < 1e-9
    return audit


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="scratch registry copy + scratch outdir; the real ledger is never touched")
    ap.add_argument("--outdir", type=Path, default=None)
    args = ap.parse_args()

    registry_path = None
    outdir = args.outdir or DEFAULT_OUTDIR
    if args.smoke:
        scratch = Path(tempfile.mkdtemp(prefix="bottomup_3pt_smoke_"))
        registry_path = scratch / "registry_scratch.jsonl"
        shutil.copyfile(REPO / "experiments" / "registry.jsonl", registry_path)
        outdir = args.outdir or (scratch / "out")
    outdir.mkdir(parents=True, exist_ok=True)
    mode = "SMOKE" if args.smoke else "REAL"
    print(f"[bottomup3pt] {mode} run at {utcnow_iso()} -> {outdir}")
    if args.smoke:
        print(f"[bottomup3pt] scratch registry: {registry_path}")

    load_frozen_baselines()   # tamper check; raises on drift
    reg = eh.get_registration(EXPERIMENT_ID, registry_path=registry_path)
    print(f"[bottomup3pt] registration OK: {EXPERIMENT_ID} "
          f"(registered {reg['registered_at']}, incumbent {reg['incumbent_id']}, "
          f"regime {reg['regime']}, primary {reg['primary_metric']})")
    th = reg["thresholds"]

    # ---------------- incumbent rebuild + reconciliation gate ----------------
    D = load_base()
    S = json.load(open(CHANREVAL / "run_summary.json", encoding="utf-8"))
    alphas_inc = {k: float(v) for k, v in S["alphas"].items()}
    a_3pt_inc = alphas_inc["3pt"]
    F = build_features(D, alphas_inc)
    games = make_games(F)

    splits = eh.walk_forward_by_season(D, date_col="GAME_DATE", season_col="season",
                                       min_train_seasons=3, test_seasons=TEST_YEARS)
    by_name = {s.name: s for s in splits}
    train_ids = set(D.loc[by_name["season:2024"].train_idx, "GAME_ID"])
    tg = games[games.GAME_ID.isin(train_ids) & games.eligible]
    cal = {}
    for p in ("raw", "str"):
        cal[f"{p}_margin"] = linfit(tg[f"{p}_margin_uncal"], tg.margin_true)
        cal[f"{p}_home"] = linfit(tg[f"{p}_sum_h"], tg.team_pts_h)
        cal[f"{p}_away"] = linfit(tg[f"{p}_sum_a"], tg.team_pts_a)
    games_cal = games.copy()
    for p in ("raw", "str"):
        a, b = cal[f"{p}_margin"]
        games_cal[f"{p}_margin_cal"] = a + b * games_cal[f"{p}_margin_uncal"]
        ah, bh = cal[f"{p}_home"]
        games_cal[f"{p}_home_cal"] = ah + bh * games_cal[f"{p}_sum_h"]
        aa, ba = cal[f"{p}_away"]
        games_cal[f"{p}_away_cal"] = aa + ba * games_cal[f"{p}_sum_a"]
    test_ids = set()
    for s in TEST_YEARS:
        test_ids |= set(D.loc[by_name[f"season:{s}"].test_idx, "GAME_ID"])
    games_cal = games_cal[games_cal.GAME_ID.isin(test_ids) & games_cal.eligible].copy()

    recon = reconcile_incumbent(F, games_cal, cal)
    print(f"[bottomup3pt] incumbent reconciliation PASS: 3pt channel table "
          f"(pooled str MAE {recon['channel_table_3pt'][0]['mae_structural']:.6f}) and "
          f"{recon['predictions_v2_rows_matched']} game rows reproduced "
          f"(max |diff| {recon['predictions_v2_max_abs_diff']:.2e})")

    # ---------------- universe: RS chanreval test team-rows ------------------
    F = add_team_percent_priors(F)
    m_univ = channel_mask_3pt(F) & (F.season_type == "Regular Season")
    univ = F[m_univ].copy()
    print(f"[bottomup3pt] universe: {len(univ)} regular-season test team-rows "
          f"({univ.groupby('season').size().to_dict()})")

    # ---------------- player data + train-only tuning ------------------------
    mp = load_master_player()
    P = build_played_frame(mp)
    team_minutes = (mp[mp.minutes.notna()]
                    .groupby(["game_id", "team_id"], as_index=False).minutes.sum()
                    .rename(columns={"minutes": "team_min"}))

    a_rate, curve_rate = tune_rate_alpha(P)
    K, curve_k = tune_shrinkage_k(P, F)
    F_rs = F[F.season_type == "Regular Season"].copy()
    a_team, curve_team = tune_team_trend_alpha(F_rs, team_minutes)
    print(f"[bottomup3pt] train-only tuning: rate alpha={a_rate}, shrinkage K={K}, "
          f"team-trend alpha={a_team}")
    curve_rate.to_csv(outdir / "alpha_curve_player_rate.csv", index=False)
    curve_k.to_csv(outdir / "k_curve_shrinkage.csv", index=False)
    curve_team.to_csv(outdir / "alpha_curve_team_trend.csv", index=False)

    # ---------------- covered-player construction (test rows) ----------------
    m2 = pd.read_csv(M2_PATH, parse_dates=["game_date"])
    assert (m2.game_id.astype(str).str[:3] == "102").all(), "m2 artifact contains non-RS games"
    assert not m2.duplicated(["game_id", "player_id"]).any()
    key_mp = mp[["game_id", "player_id", "team_id"]]
    m2 = m2.merge(key_mp, on=["game_id", "player_id"], how="left", validate="one_to_one")
    assert m2.team_id.notna().all(), "m2 rows failed to join master_player"
    m2["team_id"] = m2.team_id.astype("int64")
    m2["exp_min"] = m2.p_plays * m2.min_ewma

    P_post = add_player_post(P, a_rate)
    covA = asof_player_features(
        m2[["game_id", "game_date", "season", "player_id", "player_name",
            "team_abbreviation", "team_id", "p_plays", "min_ewma", "exp_min",
            "played_flag", "minutes"]], P_post)

    pri_cols = F[["GAME_ID", "TEAM_ID", "tcum3pa_shift", "tcum3pm_shift", "lg_3ppct_prior"]]
    cov = covA.merge(pri_cols, left_on=["game_id", "team_id"],
                     right_on=["GAME_ID", "TEAM_ID"], how="left")
    pct, team_prior = shrunk_pct(cov.cum3pm_asof, cov.cum3pa_asof,
                                 cov.tcum3pm_shift, cov.tcum3pa_shift,
                                 cov.lg_3ppct_prior, K)
    cov["team_prior_pct"] = team_prior
    cov["pct3_shrunk"] = pct
    cov["is_covered"] = cov.rate3pa_asof.notna() & cov.pct3_shrunk.notna() & cov.exp_min.notna()
    cov["pred_makes"] = np.where(cov.is_covered,
                                 cov.rate3pa_asof * cov.pct3_shrunk * cov.exp_min, 0.0)
    cov["pred_attempts"] = np.where(cov.is_covered, cov.rate3pa_asof * cov.exp_min, 0.0)
    cov["exp_min_eff"] = np.where(cov.is_covered, cov.exp_min, 0.0)
    n_rate_gap = int(((~cov.rate3pa_asof.notna()) & (cov.exp_min > 0)).sum())

    # independent cross-check of the as-of path: at played m2 rows the as-of rate
    # must equal the groupby-shift rate at the same master row (two code paths)
    Pchk = add_player_shifted(P, a_rate)[["game_id", "player_id", "rate_shift",
                                          "cum3pa_shift", "cum3pm_shift"]]
    chk = cov.merge(Pchk, on=["game_id", "player_id"], how="inner")
    both = chk.rate3pa_asof.notna() & chk.rate_shift.notna()
    max_dev = float((chk.loc[both, "rate3pa_asof"] - chk.loc[both, "rate_shift"]).abs().max())
    one_side = int((chk.rate3pa_asof.notna() != chk.rate_shift.notna()).sum())
    assert max_dev < 1e-9 and one_side == 0, \
        f"as-of vs shifted rate mismatch: max dev {max_dev}, one-sided {one_side}"
    for c_asof, c_shift in (("cum3pa_asof", "cum3pa_shift"), ("cum3pm_asof", "cum3pm_shift")):
        b2 = chk[c_asof].notna() & chk[c_shift].notna()
        dv = float((chk.loc[b2, c_asof] - chk.loc[b2, c_shift]).abs().max())
        assert dv < 1e-9, f"{c_asof} mismatch vs groupby-shift: {dv}"
    print(f"[bottomup3pt] as-of feature cross-check PASS "
          f"({int(both.sum())} played rows, max dev {max_dev:.2e})")

    # ---------------- team-game aggregation ----------------------------------
    agg = (cov.groupby(["game_id", "team_id"])
           .agg(covered_exp_min_sum=("exp_min_eff", "sum"),
                covered_makes_sum=("pred_makes", "sum"),
                covered_attempts_sum=("pred_attempts", "sum"),
                n_m2_rows=("player_id", "size"),
                n_covered=("is_covered", "sum"))
           .reset_index())

    F_full = add_team_trend(F, team_minutes, a_team)          # full frame, then slice
    univ = F_full[m_univ.to_numpy()].copy()
    univ = univ.merge(agg, left_on=["GAME_ID", "TEAM_ID"],
                      right_on=["game_id", "team_id"], how="left").drop(
                          columns=["game_id", "team_id"])
    assert univ.covered_exp_min_sum.notna().all(), "universe team-row without m2 coverage"
    assert univ.team_3ppm_trend.notna().all()
    univ["opp_factor"] = univ.opp_fg3a_allow / univ.lg_fg3a
    assert univ.opp_factor.notna().all()

    univ["corr_minutes"] = REG_MINUTES - univ.covered_exp_min_sum
    univ["corr_points_prefactor"] = univ.corr_minutes * univ.team_3ppm_trend
    univ["covered_points_prefactor"] = 3.0 * univ.covered_makes_sum
    univ["challenger_prefactor"] = univ.covered_points_prefactor + univ.corr_points_prefactor
    univ["challenger_pred"] = univ.challenger_prefactor * univ.opp_factor
    univ["correction_share"] = univ.corr_points_prefactor / univ.challenger_prefactor
    assert univ.challenger_pred.notna().all()

    # uncovered actual players: played the game but absent from the m2 universe
    played_keys = mp[mp.minutes.notna()][["game_id", "team_id", "player_id"]]
    m2_keys = m2[["game_id", "team_id", "player_id"]].assign(in_m2=True)
    pk = played_keys.merge(m2_keys, on=["game_id", "team_id", "player_id"], how="left")
    n_not_m2 = (pk[pk.in_m2.isna()].groupby(["game_id", "team_id"]).size()
                .rename("n_played_not_in_m2").reset_index())
    univ = univ.merge(n_not_m2, left_on=["GAME_ID", "TEAM_ID"],
                      right_on=["game_id", "team_id"], how="left").drop(
                          columns=["game_id", "team_id"])
    univ["n_played_not_in_m2"] = univ.n_played_not_in_m2.fillna(0).astype(int)
    univ = univ.reset_index(drop=True)

    # ---------------- audits before believing --------------------------------
    audit = shift_audit(univ, cov, P, F_full, a_rate, K, a_team, a_3pt_inc)
    audit.to_csv(outdir / "shift_audit.csv", index=False)
    n_bad = int((~audit.ok).sum())
    print(f"[bottomup3pt] shift audit: {len(audit)} truncation recomputes, "
          f"{n_bad} mismatches, max |diff| {audit.abs_diff.max():.3e} -> "
          f"{'PASS' if n_bad == 0 else 'FAIL'}")
    if n_bad:
        raise SystemExit("shift audit FAILED -- results are not evidence; stopping")

    # ---------------- primary comparison (recorded via the harness) ----------
    univ["row_key"] = univ.GAME_ID.astype(str) + "_" + univ.TEAM_ID.astype(str)
    ch_frame = pd.DataFrame({
        "game_id": univ.row_key, "game_date": univ.GAME_DATE, "season": univ.season,
        "y_true": univ.ch_3pt, "y_pred": univ.challenger_pred, "own_team": univ.TEAM_ID})
    inc_frame = pd.DataFrame({
        "game_id": univ.row_key, "y_true": univ.ch_3pt, "y_pred": univ.str_3pt})
    n_univ = len(univ)
    coverage = (float(univ.challenger_pred.notna().sum()) / n_univ,
                float(univ.str_3pt.notna().sum()) / n_univ)

    # gate 4: substitute challenger 3pt into the structural sum, margin
    # recalibrated under the train-only protocol (see module docstring)
    side = univ[["GAME_ID", "TEAM_ID", "challenger_pred"]]
    g4 = games_cal[games_cal.season_type_h == "Regular Season"].merge(
        side.rename(columns={"TEAM_ID": "TEAM_ID_h", "challenger_pred": "ch3_h"}),
        on=["GAME_ID", "TEAM_ID_h"], how="inner").merge(
        side.rename(columns={"TEAM_ID": "TEAM_ID_a", "challenger_pred": "ch3_a"}),
        on=["GAME_ID", "TEAM_ID_a"], how="inner")
    a_str, b_str = cal["str_margin"]
    g4["sub_sum_h"] = g4.str_sum_h - g4.str_3pt_h + g4.ch3_h
    g4["sub_sum_a"] = g4.str_sum_a - g4.str_3pt_a + g4.ch3_a
    g4["sub_margin_uncal"] = g4.sub_sum_h - g4.sub_sum_a
    g4["sub_margin_cal"] = a_str + b_str * g4.sub_margin_uncal
    m_sub = mae(g4.sub_margin_cal - g4.margin_true)
    m_inc = mae(g4.str_margin_cal - g4.margin_true)
    m_sub_unc = mae(g4.sub_margin_uncal - g4.margin_true)
    m_inc_unc = mae(g4.str_margin_uncal - g4.margin_true)
    # margin-error decomposition: var(e_margin) = var(e_h) + var(e_a) - 2 cov(e_h, e_a)
    # -- positive home/away error correlation cancels in the margin; measure how much
    # cancellation each model gets (uncalibrated sums vs actual points).
    decomp = {}
    for tag, ch_h, ch_a in (("challenger_sub", g4.sub_sum_h, g4.sub_sum_a),
                            ("incumbent", g4.str_sum_h, g4.str_sum_a)):
        e_h = (ch_h - g4.team_pts_h).to_numpy(float)
        e_a = (ch_a - g4.team_pts_a).to_numpy(float)
        decomp[tag] = {
            "corr_eh_ea": float(np.corrcoef(e_h, e_a)[0, 1]),
            "var_eh": float(np.var(e_h)), "var_ea": float(np.var(e_a)),
            "cov_eh_ea": float(np.cov(e_h, e_a)[0, 1]),
            "var_margin_err": float(np.var(e_h - e_a)),
        }
    joint_detail = {
        "n_games": int(len(g4)),
        "margin_mae_challenger_sub": round(m_sub, 4),
        "margin_mae_incumbent": round(m_inc, 4),
        "delta_degradation": round(m_sub - m_inc, 4),
        "tolerance": float(th["harm_ci_bound"]),
        "uncal_sensitivity": {"challenger_sub": round(m_sub_unc, 4),
                              "incumbent": round(m_inc_unc, 4)},
        "margin_error_decomposition": decomp,
        "calibration_protocol": ("incumbent train-years-only str_margin (a,b) applied "
                                 "unchanged to the substituted margin; challenger is "
                                 "unconstructible on 2021-2023 (Stage-A artifacts are "
                                 "test-years only), so no refit is possible without "
                                 "touching test data"),
    }

    def joint_check():
        ok = m_sub <= m_inc + float(th["harm_ci_bound"])
        return ok, joint_detail

    result = eh.compare_to_incumbent(
        ch_frame, inc_frame, experiment_id=EXPERIMENT_ID,
        registry_path=registry_path, loss="absolute", cluster="date",
        team_col="own_team", joint_check=joint_check, coverage=coverage)
    print(f"[bottomup3pt] VERDICT: {result.verdict} (promote={result.promote}); "
          f"challenger MAE {result.metric_challenger:.4f} vs incumbent "
          f"{result.metric_incumbent:.4f}; pooled improvement "
          f"{result.pooled_improvement:+.4f} [90% CI {result.ci_low:+.4f}, "
          f"{result.ci_high:+.4f}]; failed gates: {result.failed_gates}")

    # ---------------- outputs ------------------------------------------------
    tg_out = univ[["GAME_ID", "TEAM_ABBREVIATION", "TEAM_ID", "GAME_DATE", "season",
                   "is_home", "ch_3pt", "str_3pt", "raw_3pt", "challenger_pred",
                   "covered_exp_min_sum", "corr_minutes", "correction_share",
                   "covered_points_prefactor", "corr_points_prefactor", "opp_factor",
                   "team_3ppm_trend", "covered_attempts_sum", "team_fg3a",
                   "n_covered", "n_m2_rows", "n_played_not_in_m2"]].copy()
    tg_out = tg_out.rename(columns={
        "GAME_ID": "game_id", "TEAM_ABBREVIATION": "team", "TEAM_ID": "team_id",
        "GAME_DATE": "date", "ch_3pt": "actual_3pt_points",
        "str_3pt": "incumbent_pred", "raw_3pt": "incumbent_raw_trend"})
    tg_out["abs_err_challenger"] = (tg_out.challenger_pred - tg_out.actual_3pt_points).abs()
    tg_out["abs_err_incumbent"] = (tg_out.incumbent_pred - tg_out.actual_3pt_points).abs()
    tg_out.to_csv(outdir / "teamgame_level_predictions.csv", index=False)

    rng = np.random.default_rng(SAMPLE_SEED)
    cov_ok = cov[cov.is_covered].copy()
    take = min(300, len(cov_ok))
    samp = cov_ok.iloc[np.sort(rng.choice(len(cov_ok), size=take, replace=False))]
    samp_cols = ["game_id", "game_date", "season", "team_abbreviation", "team_id",
                 "player_id", "player_name", "p_plays", "min_ewma", "exp_min",
                 "rate3pa_asof", "cum3pa_asof", "cum3pm_asof", "tcum3pa_shift",
                 "tcum3pm_shift", "lg_3ppct_prior", "team_prior_pct", "pct3_shrunk",
                 "pred_makes", "played_flag", "minutes"]
    samp[samp_cols].to_csv(outdir / "player_level_sample.csv", index=False)

    acct = pd.DataFrame([{
        "n_universe_team_rows": n_univ,
        "n_m2_rows_in_universe_games": int(univ.n_m2_rows.sum()),
        "n_covered_player_rows": int(univ.n_covered.sum()),
        "n_exp_min_pos_but_rate_nan": n_rate_gap,
        "mean_covered_exp_min_sum": float(univ.covered_exp_min_sum.mean()),
        "p10_covered_exp_min_sum": float(univ.covered_exp_min_sum.quantile(0.10)),
        "p90_covered_exp_min_sum": float(univ.covered_exp_min_sum.quantile(0.90)),
        "n_rows_negative_correction": int((univ.corr_minutes < 0).sum()),
        "mean_correction_share": float(univ.correction_share.mean()),
        "median_correction_share": float(univ.correction_share.median()),
        "pooled_correction_share": float(univ.corr_points_prefactor.sum()
                                         / univ.challenger_prefactor.sum()),
        "mean_n_played_not_in_m2": float(univ.n_played_not_in_m2.mean()),
        "rows_with_any_played_not_in_m2": int((univ.n_played_not_in_m2 > 0).sum()),
        "mean_bias_challenger": float((univ.challenger_pred - univ.ch_3pt).mean()),
        "mean_bias_incumbent": float((univ.str_3pt - univ.ch_3pt).mean()),
        "min_challenger_pred": float(univ.challenger_pred.min()),
        "max_challenger_pred": float(univ.challenger_pred.max()),
        # bias attribution: attempts volume vs conversion (covered part, opp-adjusted)
        "mean_pred_attempts_oppadj": float((univ.covered_attempts_sum * univ.opp_factor).mean()),
        "mean_actual_attempts": float(univ.team_fg3a.mean()),
        "implied_pred_3ppct": float(univ.covered_makes_sum.sum() / univ.covered_attempts_sum.sum()),
        "actual_3ppct": float(univ.team_fg3m.sum() / univ.team_fg3a.sum()),
    }])
    acct.to_csv(outdir / "uncovered_accounting.csv", index=False)

    # diagnostics: does the correction hurt? MAE by correction-share tercile
    bins = pd.qcut(univ.correction_share, 3, labels=["low", "mid", "high"],
                   duplicates="drop")
    terc_rows = []
    for lab in bins.cat.categories:
        d = univ[bins == lab]
        terc_rows.append({
            "share_bin": str(lab), "n": int(len(d)),
            "mean_correction_share": float(d.correction_share.mean()),
            "mae_challenger": float((d.challenger_pred - d.ch_3pt).abs().mean()),
            "mae_incumbent": float((d.str_3pt - d.ch_3pt).abs().mean())})
    terc_tbl = pd.DataFrame(terc_rows)

    # diagnostics: residual covariance with the rest of the structural sum
    # (ROADMAP Phase 1: a channel that improves alone but breaks error
    # cancellation in the sum is rejected by gate 4 -- quantify exactly that)
    e3_ch = univ.challenger_pred - univ.ch_3pt
    e3_inc = univ.str_3pt - univ.ch_3pt
    e_rest = ((univ.str_ft + univ.str_paint + univ.str_np2)
              - (univ.ch_ft + univ.ch_paint + univ.ch_np2))
    cov_diag = {
        "corr_e3_erest_challenger": float(np.corrcoef(e3_ch, e_rest)[0, 1]),
        "corr_e3_erest_incumbent": float(np.corrcoef(e3_inc, e_rest)[0, 1]),
        "var_e3_challenger": float(e3_ch.var()),
        "var_e3_incumbent": float(e3_inc.var()),
        "var_team_total_err_challenger": float((e3_ch + e_rest).var()),
        "var_team_total_err_incumbent": float((e3_inc + e_rest).var()),
        "mae_team_total_challenger": float((e3_ch + e_rest).abs().mean()),
        "mae_team_total_incumbent": float((e3_inc + e_rest).abs().mean()),
    }

    # diagnosis slice (reported, never gated): are the losses concentrated in
    # expansion-team rows (thin team-season priors under heavy shrinkage)?
    exp_rows = []
    for s in TEST_YEARS:
        for is_exp in (False, True):
            d = univ[(univ.season == s) & (univ.is_expansion_season == is_exp)]
            if not len(d):
                continue
            exp_rows.append({
                "season": s, "expansion_team_row": is_exp, "n": int(len(d)),
                "mae_challenger": float((d.challenger_pred - d.ch_3pt).abs().mean()),
                "mae_incumbent": float((d.str_3pt - d.ch_3pt).abs().mean())})
    exp_tbl = pd.DataFrame(exp_rows)
    exp_tbl["delta"] = exp_tbl.mae_incumbent - exp_tbl.mae_challenger

    verdict_payload = {
        "experiment_id": EXPERIMENT_ID, "mode": mode,
        "registry": str(registry_path) if registry_path else "experiments/registry.jsonl",
        "run_number": result.run_number, "eval_time": result.eval_time,
        "tuned": {"rate_alpha": a_rate, "shrinkage_K": K, "team_trend_alpha": a_team,
                  "min_ewma_alpha_frozen": MIN_EWMA_ALPHA,
                  "incumbent_alphas_used": alphas_inc},
        "reconciliation": recon,
        "comparison": result.to_dict(),
        "joint_gate4": joint_detail,
        "accounting": acct.iloc[0].to_dict(),
        "correction_terciles": terc_tbl.to_dict(orient="records"),
        "residual_covariance_diag": cov_diag,
        "expansion_split": exp_tbl.to_dict(orient="records"),
        "audit": {"n_recomputes": int(len(audit)), "n_mismatches": n_bad,
                  "max_abs_diff": float(audit.abs_diff.max())},
    }
    with open(outdir / "gate_verdict.json", "w", encoding="utf-8") as fh:
        json.dump(verdict_payload, fh, indent=2, default=str)

    write_report(outdir, mode, reg, result, joint_detail, recon, acct.iloc[0],
                 terc_tbl, a_rate, K, a_team, curve_rate, curve_k, curve_team,
                 univ, audit, cov_diag, exp_tbl)
    print(f"[bottomup3pt] wrote REPORT.md, teamgame_level_predictions.csv, "
          f"player_level_sample.csv, tuning curves, shift_audit.csv, "
          f"uncovered_accounting.csv, gate_verdict.json -> {outdir}")


def write_report(outdir, mode, reg, result, joint, recon, acct, terc_tbl,
                 a_rate, K, a_team, curve_rate, curve_k, curve_team, univ, audit,
                 cov_diag, exp_tbl):
    per_season = pd.DataFrame(result.per_season)
    lines = []
    a = lines.append
    a(f"# Bottom-up 3pt channel (`{EXPERIMENT_ID}`)")
    a("")
    a(f"*Generated by `bottomup_3pt.py` on {utcnow_iso()} -- {mode} run"
      + (" (scratch registry; the real ledger was not touched; the orchestrator's "
         "real-mode run re-records and overwrites this file)" if mode == "SMOKE" else "")
      + f". Run {result.run_number} against the ledger used. Regime {reg['regime']}. "
      f"Registered {reg['registered_at']}; incumbent `{reg['incumbent_id']}`.*")
    a("")
    a("## Verdict -- per-team-game 3pt points MAE (primary, gated)")
    a("")
    a(f"- **{result.verdict}** (promote={result.promote}); failed gates: {result.failed_gates}.")
    a(f"- Pooled 3pt MAE: **challenger {result.metric_challenger:.4f}** vs "
      f"**incumbent {result.metric_incumbent:.4f}** -> improvement "
      f"**{result.pooled_improvement:+.4f}** (gate 1 needs >= "
      f"+{result.thresholds['min_improvement']}).")
    a(f"- 90% date-cluster bootstrap CI for the improvement: "
      f"[{result.ci_low:+.4f}, {result.ci_high:+.4f}] over {result.n_clusters} date "
      f"clusters (gate 2 low must be >= -{result.thresholds['harm_ci_bound']}); "
      f"team-cluster sensitivity: {result.ci_sensitivity_team}.")
    a(f"- Universe: {result.n_games} regular-season chanreval test team-games "
      f"(availability system is RS-only), coverage challenger/incumbent = "
      f"{result.gate_details['gate5_coverage']['coverage_challenger']:.4f}/"
      f"{result.gate_details['gate5_coverage']['coverage_incumbent']:.4f}.")
    a("")
    a("| season | n | challenger MAE | incumbent MAE | delta (+ = challenger better) |")
    a("|---|---|---|---|---|")
    for _, r in per_season.iterrows():
        a(f"| {r.season} | {r.n} | {r.metric_challenger:.4f} | "
          f"{r.metric_incumbent:.4f} | {r.delta:+.4f} |")
    a("")
    a("## Gate 4 -- joint margin forecast (challenger 3pt substituted into the 4-channel sum)")
    a("")
    ok4 = result.gates.get("gate4_joint_forecast")
    a(f"- Margin MAE on {joint['n_games']} RS games: substituted "
      f"**{joint['margin_mae_challenger_sub']:.4f}** vs incumbent "
      f"**{joint['margin_mae_incumbent']:.4f}** (degradation "
      f"{joint['delta_degradation']:+.4f}; tolerance {joint['tolerance']}) -> "
      f"{'PASS' if ok4 else 'FAIL'}.")
    a(f"- Uncalibrated sensitivity: {joint['uncal_sensitivity']['challenger_sub']:.4f} "
      f"vs {joint['uncal_sensitivity']['incumbent']:.4f} (degradation "
      f"{joint['uncal_sensitivity']['challenger_sub'] - joint['uncal_sensitivity']['incumbent']:+.4f} "
      f"before any calibration is applied).")
    a(f"- Calibration protocol: {joint['calibration_protocol']}.")
    a("")
    a("### Where the margin result comes from (error-cancellation decomposition)")
    a("")
    d_ch = joint["margin_error_decomposition"]["challenger_sub"]
    d_in = joint["margin_error_decomposition"]["incumbent"]
    team_better = (cov_diag["mae_team_total_challenger"]
                   <= cov_diag["mae_team_total_incumbent"])
    a(f"- Within a team-row, substituting the challenger "
      f"{'does not hurt' if team_better else 'hurts'} the 4-channel sum: "
      f"corr(e_3pt, e_other_channels) = {cov_diag['corr_e3_erest_challenger']:+.4f} "
      f"(challenger) vs {cov_diag['corr_e3_erest_incumbent']:+.4f} (incumbent); "
      f"team-TOTAL points error MAE {cov_diag['mae_team_total_challenger']:.4f} vs "
      f"{cov_diag['mae_team_total_incumbent']:.4f}, variance "
      f"{cov_diag['var_team_total_err_challenger']:.2f} vs "
      f"{cov_diag['var_team_total_err_incumbent']:.2f}.")
    a(f"- Cross-side cancellation: var(e_margin) = var(e_h) + var(e_a) "
      f"- 2 cov(e_h, e_a). Incumbent home/away sum errors correlate "
      f"{d_in['corr_eh_ea']:+.4f} (cov {d_in['cov_eh_ea']:+.2f}); substituted "
      f"{d_ch['corr_eh_ea']:+.4f} (cov {d_ch['cov_eh_ea']:+.2f}). Margin error "
      f"variance {d_ch['var_margin_err']:.2f} (substituted) vs "
      f"{d_in['var_margin_err']:.2f} (incumbent).")
    if team_better and d_ch["corr_eh_ea"] < d_in["corr_eh_ea"]:
        a("- Reading: the structural chains on both sides of a game share "
          "opponent/league scaling terms, so their errors co-move and subtract "
          "out of the margin. The bottom-up channel is more accurate per team "
          "but its errors are less correlated across the two sides of the same "
          "game, so less cancels -- ROADMAP Phase 1's joint-coherence rule "
          "('structural sum means a coherent joint forecast, not an arithmetic "
          "sum of independently optimized parts') in action.")
    a("")
    a("## The challenger, as built (registration verbatim)")
    a("")
    a("```")
    a("team_3pt = [ 3 * SUM_covered( rate3pa_ewma * pct3_shrunk * p_plays*min_ewma )")
    a("             + (200 - SUM_covered exp_min) * team_3pt_per_min_trend ]")
    a("           * (opp_fg3a_allow / lg_fg3a)     # incumbent factor, team level")
    a("```")
    a("")
    a(f"- Tuned on 2021-2023 only (3 inner walk-forward folds via "
      f"`evalharness.inner_tuning_splits`): rate EWMA alpha = **{a_rate}** "
      f"(curve: `alpha_curve_player_rate.csv`), EB shrinkage K = **{K:g}** "
      f"(`k_curve_shrinkage.csv`), team-trend alpha = **{a_team}** "
      f"(`alpha_curve_team_trend.csv`). min_ewma alpha 0.30 frozen per registration; "
      f"p_plays and min_ewma consumed from the committed Stage-A artifact "
      f"`experiments/minutes_twostage/test_predictions_m2.csv`.")
    a(f"- Tuning objectives: attempts given realized minutes (alpha); makes given "
      f"realized attempts (K, rows with >=1 attempt); team 3pt points given realized "
      f"team minutes (team alpha). All rows strictly inside 2021-2023.")
    a(f"- 3P% shrinkage: player counts -> team-season prior -> league strictly-earlier "
      f"running ratio, single K at both levels. The K grid runs to an "
      f"effectively-infinite sentinel (1e9 = player identity ignored, pure "
      f"team-season prior) after a first pass showed the curve still falling at "
      f"the original 320 edge -- a train-curve-only observation; the grid "
      f"extension never consulted test data.")
    if K >= 1e8:
        a(f"- **The K sentinel won**: on 2021-2023 the tuner prefers ignoring player "
          f"3P% identity entirely (pure team-season prior conversion). Under this "
          f"construction the challenger's player level carries the ATTEMPTS profile "
          f"(who shoots, how often, for how many expected minutes) but no "
          f"player-specific conversion skill -- a core V4 finding on its own.")
    else:
        a(f"- K = {K:g} is interior to the grid; player 3P% identity retains "
          f"weight n_attempts/(n_attempts+{K:g}) -- e.g. a 150-attempt shooter "
          f"keeps {150 / (150 + K):.0%} of her own observed rate.")
    a(f"- Grid-boundary note (train curves): the rate and team-trend alpha curves "
      f"are monotone decreasing into the conventional 0.05 floor -- the same "
      f"floor, and the same winning value, as the incumbent chanreval 3pt alpha. "
      f"Slower-than-0.05 trends are a v2 lead, recorded in the curves.")
    a("- Opponent adjustment: the incumbent chain's structural factor "
      "`opp_fg3a_allow / lg_fg3a` (run_reval.py str_3pt definition), applied once "
      "to the whole team-level sum (covered + uncovered correction).")
    a("")
    a("## Incumbent reconciliation (hard-asserted before anything else ran)")
    a("")
    a("`predictions_v2.csv` is game-level only, so the incumbent 3pt chain was rebuilt "
      "per `run_reval.py` with the recorded alphas "
      f"({recon['recorded_alphas']}) and verified:")
    a("")
    a("| scope | n rows | rebuilt str MAE | recorded str MAE |")
    a("|---|---|---|---|")
    for r in recon["channel_table_3pt"]:
        a(f"| {r['scope']} | {r['n']} | {r['mae_structural']:.6f} | "
          f"{r['recorded_mae_structural']:.6f} |")
    a("")
    a(f"Game-level: all {recon['predictions_v2_rows_matched']} recorded prediction rows "
      f"reproduced, max |diff| {recon['predictions_v2_max_abs_diff']:.2e}; calibration "
      f"constants reproduced to 1e-9. (Numbers above include playoffs because the "
      f"recorded table does; the experiment universe below is RS-only.)")
    a("")
    a("## Cold-start / uncovered accounting")
    a("")
    a(f"- Covered expected minutes per team-game: mean "
      f"{acct['mean_covered_exp_min_sum']:.1f} of 200 (p10 "
      f"{acct['p10_covered_exp_min_sum']:.1f} / p90 {acct['p90_covered_exp_min_sum']:.1f}); "
      f"{acct['n_rows_negative_correction']} of {acct['n_universe_team_rows']} team-rows "
      f"overshoot 200 (negative correction, kept unclamped per the registered formula).")
    a(f"- Correction share of predicted 3pt points: mean "
      f"{acct['mean_correction_share']:.3f}, median {acct['median_correction_share']:.3f}, "
      f"pooled {acct['pooled_correction_share']:.3f}.")
    a(f"- Players who played but sit outside the minutes universe: "
      f"{acct['rows_with_any_played_not_in_m2']} team-rows have at least one "
      f"(mean {acct['mean_n_played_not_in_m2']:.2f}/team-game); their minutes are "
      f"exactly what the correction term absorbs. Dressed rows with exp_min > 0 but "
      f"no prior played game (rate undefined): {acct['n_exp_min_pos_but_rate_nan']}.")
    a(f"- Level bias (pred - actual): challenger {acct['mean_bias_challenger']:+.3f}, "
      f"incumbent {acct['mean_bias_incumbent']:+.3f} points. Attribution: "
      f"opponent-adjusted covered attempts predict "
      f"{acct['mean_pred_attempts_oppadj']:.2f}/game vs {acct['mean_actual_attempts']:.2f} "
      f"actual; implied covered 3P% {acct['implied_pred_3ppct']:.4f} vs actual "
      f"{acct['actual_3ppct']:.4f}.")
    a("")
    a("| correction-share tercile | n | mean share | challenger MAE | incumbent MAE |")
    a("|---|---|---|---|---|")
    for _, r in terc_tbl.iterrows():
        a(f"| {r.share_bin} | {int(r.n)} | {r.mean_correction_share:.3f} | "
          f"{r.mae_challenger:.4f} | {r.mae_incumbent:.4f} |")
    a("")
    a("## Diagnosis slices (reported, never gated)")
    a("")
    a("Expansion-team rows (first-season TOR/PDX/GSV beyond their 5-game floor) "
      "vs legacy teams -- thin team-season priors are where heavy EB shrinkage "
      "should misbehave first:")
    a("")
    a("| season | rows | n | challenger MAE | incumbent MAE | delta (+ = challenger better) |")
    a("|---|---|---|---|---|---|")
    for _, r in exp_tbl.iterrows():
        lab = "expansion" if r.expansion_team_row else "legacy"
        a(f"| {int(r.season)} | {lab} | {int(r.n)} | {r.mae_challenger:.4f} | "
          f"{r.mae_incumbent:.4f} | {r.delta:+.4f} |")
    a("")
    k_tail = curve_k[curve_k.K >= 320.0].inner_mae_mean
    a(f"K identification caveat: the train-only K curve is nearly flat across its "
      f"upper range (inner-MAE spread over K >= 320 is "
      f"{float(k_tail.max() - k_tail.min()):.6f} on a ~{float(k_tail.mean()):.3f} "
      f"base) -- K is weakly identified on 2021-2023; per-season test deltas are "
      f"sensitive to choices the tuner cannot distinguish, which is itself part "
      f"of the finding.")
    a("")
    a("## Audits")
    a("")
    a(f"- Shift-truncation recompute (constitution rule 1): {len(audit)} independent "
      f"recomputations over sampled universe rows -- player rate EWMA, player cum "
      f"3PA/3PM, team-season prior counts, league 3P% prior, team per-minute trend, "
      f"and the incumbent opponent factor ingredients -- all rebuilt from strictly "
      f"prior-dated rows only: {int((~audit.ok).sum())} mismatches, max |diff| "
      f"{audit.abs_diff.max():.3e}. PASS. (`shift_audit.csv`)")
    a("- As-of merge cross-check: at every played dressed row the merge_asof rate/cum "
      "values equal the independent groupby-shift values (two code paths, max dev "
      "< 1e-9). PASS.")
    a("- Stage-A inputs (p_plays, min_ewma) are consumed from the committed artifact; "
      "their own shift audit (875 recomputes, 0 mismatches) is recorded in "
      "`experiments/minutes_twostage/REPORT.md`.")
    a("")
    a("## Files")
    a("")
    a("`gate_verdict.json`, `teamgame_level_predictions.csv`, `player_level_sample.csv`, "
      "`alpha_curve_player_rate.csv`, `k_curve_shrinkage.csv`, `alpha_curve_team_trend.csv`, "
      "`shift_audit.csv`, `uncovered_accounting.csv`.")
    (outdir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
