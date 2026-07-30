#!/usr/bin/env python3
"""
Phase-1 channel re-validation under the evaluation harness.

Registered experiment: chanreval_2026_structural_repaired (regime A,
primary metric margin_mae, incumbent raw_trend_channel_sum) -- registered
2026-07-30 in experiments/registry.jsonl BEFORE this run. This script never
registers; it evaluates.

Faithful re-implementation of the July 2026 channel experiment
(experiments/channels/run_experiment.py) on channel_base_v2.csv (rebuilt
masters, repaired 2023 paint), with these preregistered/documented deltas:

  1. Paint & np2 channels now TRAIN ON 2021-2023 (July excluded 2023: corrupted
     paint). Retesting the provisional paint call is the point of this rerun.
  2. Alpha tuning goes through evalharness.inner_tuning_splits (3 inner
     walk-forward folds strictly inside the 2021-2023 outer-train window)
     instead of July's pooled train-window MAE. Never touches test.
  3. League running means use STRICTLY EARLIER DATES from the start (July's
     final certified variant: "strict league-mean rebuild", 9.51 -> 9.54).
  4. Test seasons 2024 / 2025 / 2026, split via evalharness.walk_forward_by_season.
     All fitted parameters (alphas, calibrations) come from the season-2024
     split's train window == 2021-2023 ONLY and are applied unchanged to all
     three test seasons (stricter than the expanding-window option).
  5. Expansion teams (GSV-2025, TOR-2026, PDX-2026 first seasons): league-prior
     fallback until the team has >= 5 prior same-season games (constitution
     rule 2 stays in force for every other team: games with a short-history
     non-expansion team are excluded, as in July). Fallback rows are counted,
     reported, and excluded from the per-channel table (they carry no team
     signal); game-level results are also reported excluding them as a
     sensitivity line.

Leakage audits (constitution rule 1) run inside this script before results are
reported: a removal audit (current game's rows blanked -> identical features)
and a perturbation probe (current game's stats distorted -> identical
predictions), plus the harness's own split validation.

Shifted EWMA everywhere: .shift(1) before use; trends reset per (team, season).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

import evalharness as eh
from evalharness.baselines import load_frozen_baselines, frozen_baseline_value

EXPERIMENT_ID = "chanreval_2026_structural_repaired"
TRAIN_YEARS = [2021, 2022, 2023]
TEST_YEARS = [2024, 2025, 2026]
MIN_PRIOR = 5
ALPHAS = [0.05, 0.08, 0.10, 0.15, 0.20, 0.30]
CHANNELS = ["ft", "3pt", "paint", "np2"]
CH_ACTUAL = {"ft": "ch_ft", "3pt": "ch_3pt", "paint": "ch_paint", "np2": "ch_np2"}
EXPANSION = {(2025, "GSV"), (2026, "TOR"), (2026, "PDX")}  # first-season teams only
SEED_CHANNEL_BOOT = 7          # July's channel-level bootstrap seed
N_BOOT_CHANNEL = 2000
AUDIT_SEED = 20260730
AUDIT_GAMES_PER_SEASON = 20

# every raw input column the feature pipeline is allowed to read; the audits
# blank/distort exactly these on the audited game's two rows
STAT_COLS = [
    "team_pf", "team_pfd", "team_fta", "team_ftm", "team_ft_pct", "team_fg3a", "team_fg3m",
    "team_fga", "team_fgm", "team_pts_paint", "team_pts",
    "ch_ft", "ch_3pt", "ch_paint", "ch_np2", "pts_2s",
    "opp_pf", "opp_fta", "opp_fg3a", "opp_fg3m", "opp_ftm",
    "opp_ch_3pt", "opp_ch_paint", "opp_ch_np2", "opp_ch_ft", "opp_pts",
]


# ---------------------------------------------------------------------------
# data + shared machinery
# ---------------------------------------------------------------------------

def load_base() -> pd.DataFrame:
    D = pd.read_csv(HERE / "channel_base_v2.csv", parse_dates=["GAME_DATE"])
    D = D.sort_values(["TEAM_ID", "GAME_DATE", "GAME_ID"]).reset_index(drop=True)
    D[STAT_COLS] = D[STAT_COLS].astype(float)   # audits assign NaN/floats into these
    D["season"] = D["year"]
    D["prior_games"] = D.groupby(["TEAM_ID", "season"]).cumcount()
    is_exp = [(s, a) in EXPANSION for s, a in zip(D.season, D.TEAM_ABBREVIATION)]
    D["is_expansion_season"] = np.array(is_exp, dtype=bool)
    D["fallback_row"] = D.is_expansion_season & (D.prior_games < MIN_PRIOR)
    return D


def ewma_shifted(s: pd.Series, alpha: float) -> pd.Series:
    """EWMA of strictly prior observations only (constitution rule 1)."""
    return s.ewm(alpha=alpha, adjust=True).mean().shift(1)


def add_trend(df: pd.DataFrame, col: str, alpha: float, out: str) -> None:
    df[out] = df.groupby(["TEAM_ID", "season"], sort=False)[col].transform(
        lambda s: ewma_shifted(s, alpha)
    )


def league_running_strict(df: pd.DataFrame, col: str) -> pd.Series:
    """Per-season league mean of `col` over all team-game rows on STRICTLY
    EARLIER dates (no same-date, no same-game information). NaN on each
    season's first date -- no prior information exists, none is invented."""
    g = df.groupby(["season", "GAME_DATE"])[col].agg(["sum", "count"]).sort_index()
    cs = g.groupby(level="season")[["sum", "count"]].cumsum()
    cs = cs.groupby(level="season").shift(1)  # strictly earlier dates only
    lg = cs["sum"] / cs["count"]
    key = pd.MultiIndex.from_arrays([df["season"], df["GAME_DATE"]])
    return pd.Series(lg.reindex(key).to_numpy(), index=df.index)


def build_features(D0: pd.DataFrame, alphas: dict, fallback: bool = True) -> pd.DataFrame:
    """The full feature pipeline: raw trends, structural chains, league means,
    expansion-team league-prior fallback. Row order/index preserved."""
    D = D0.copy()
    a_ft, a_3pt, a_paint, a_np2 = (alphas[c] for c in CHANNELS)

    # raw channel trends (the incumbent's features; also chain ingredients)
    add_trend(D, "ch_ft", a_ft, "raw_ft")
    add_trend(D, "ch_3pt", a_3pt, "raw_3pt")
    add_trend(D, "ch_paint", a_paint, "raw_paint")
    add_trend(D, "ch_np2", a_np2, "raw_np2")

    # league running means, strictly earlier dates
    for col, out in [
        ("team_pf", "lg_pf"), ("team_fta", "lg_fta"), ("team_ft_pct", "lg_ftpct"),
        ("team_fg3a", "lg_fg3a"), ("team_fg3m", "lg_fg3m"),
        ("ch_ft", "lg_ft"), ("ch_3pt", "lg_3pt"), ("ch_paint", "lg_paint"), ("ch_np2", "lg_np2"),
    ]:
        D[out] = league_running_strict(D, col)

    # structural ingredients -- own side
    add_trend(D, "team_fta", a_ft, "fta_t")
    add_trend(D, "team_ft_pct", a_ft, "ftpct_t")
    add_trend(D, "team_pf", a_ft, "pf_t")          # own fouls committed (feeds opponent's FT chain)
    add_trend(D, "team_fg3a", a_3pt, "fg3a_t")
    add_trend(D, "team_fg3m", a_3pt, "fg3m_t")
    # structural ingredients -- allowed side (what this team gives up)
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

    # opponent-side maps (merged AFTER fallback so expansion rows export league priors)
    for src, out in [
        ("pf_t", "opp_pf_trend"), ("fg3a_allow_t", "opp_fg3a_allow"),
        ("paint_allow_t", "opp_paint_allow"), ("np2_allow_t", "opp_np2_allow"),
    ]:
        mp = D[["GAME_ID", "TEAM_ID", src]].rename(columns={"TEAM_ID": "OPP_TEAM_ID", src: out})
        D = D.merge(mp, on=["GAME_ID", "OPP_TEAM_ID"], how="left")

    # structural chains (July definitions, verbatim)
    D["fg3pct_t"] = D["fg3m_t"] / D["fg3a_t"]
    D["str_ft"] = D["fta_t"] * (D["opp_pf_trend"] / D["lg_pf"]) * D["ftpct_t"]
    D["str_3pt"] = D["fg3a_t"] * (D["opp_fg3a_allow"] / D["lg_fg3a"]) * D["fg3pct_t"] * 3.0
    D["str_paint"] = D["raw_paint"] * (D["opp_paint_allow"] / D["lg_paint"])
    D["str_np2"] = D["raw_np2"] * (D["opp_np2_allow"] / D["lg_np2"])

    if not (D.index == D0.index).all():
        raise RuntimeError("feature pipeline broke row alignment")
    return D


# ---------------------------------------------------------------------------
# alpha tuning -- inner walk-forward folds strictly inside 2021-2023
# ---------------------------------------------------------------------------

def tune_alphas(D: pd.DataFrame, outer24: "eh.OuterSplit") -> tuple[dict, list]:
    inner = eh.inner_tuning_splits(D, outer24, date_col="GAME_DATE", n_folds=3)
    alphas, detail = {}, []
    for ch in CHANNELS:
        col = CH_ACTUAL[ch]
        rows = []
        for a in ALPHAS:
            t = D[["TEAM_ID", "season", "GAME_DATE", "prior_games", col]].copy()
            add_trend(t, col, a, "p")
            fold_maes = []
            for f in inner:
                val = t.loc[f.val_idx]
                m = val["p"].notna() & val[col].notna() & (val.prior_games >= MIN_PRIOR)
                fold_maes.append(float((val.loc[m, "p"] - val.loc[m, col]).abs().mean()))
            rows.append({"channel": ch, "alpha": a,
                         "inner_mae_mean": float(np.mean(fold_maes)),
                         "inner_mae_by_fold": fold_maes})
        best = min(rows, key=lambda r: r["inner_mae_mean"])
        alphas[ch] = best["alpha"]
        detail.extend(rows)
    return alphas, detail


# ---------------------------------------------------------------------------
# game table, calibration, scoring
# ---------------------------------------------------------------------------

def make_games(F: pd.DataFrame) -> pd.DataFrame:
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


def fit_calibrations(train_games: pd.DataFrame) -> dict:
    """Train-years-only linear calibrations: margin, home score, away score,
    per model; plus the naive home-advantage intercept (train mean margin)."""
    cal = {"naive_home_margin": float(train_games.margin_true.mean()),
           "n_train_games": int(len(train_games))}
    for p in ("raw", "str"):
        a, b = linfit(train_games[f"{p}_margin_uncal"], train_games.margin_true)
        cal[f"{p}_margin"] = (a, b)
        a, b = linfit(train_games[f"{p}_sum_h"], train_games.team_pts_h)
        cal[f"{p}_home"] = (a, b)
        a, b = linfit(train_games[f"{p}_sum_a"], train_games.team_pts_a)
        cal[f"{p}_away"] = (a, b)
    return cal


def apply_calibrations(g: pd.DataFrame, cal: dict) -> pd.DataFrame:
    g = g.copy()
    for p in ("raw", "str"):
        a, b = cal[f"{p}_margin"]
        g[f"{p}_margin_cal"] = a + b * g[f"{p}_margin_uncal"]
        ah, bh = cal[f"{p}_home"]
        g[f"{p}_home_cal"] = ah + bh * g[f"{p}_sum_h"]
        aa, ba = cal[f"{p}_away"]
        g[f"{p}_away_cal"] = aa + ba * g[f"{p}_sum_a"]
        g[f"{p}_total_cal"] = g[f"{p}_home_cal"] + g[f"{p}_away_cal"]
    g["naive_margin_pred"] = cal["naive_home_margin"]
    return g


def mae(err: pd.Series) -> float:
    return float(err.abs().mean())


# ---------------------------------------------------------------------------
# leakage audits (constitution rule 1: audit before believing)
# ---------------------------------------------------------------------------

def _rows_of(F: pd.DataFrame, gid) -> pd.Index:
    return F.index[F.GAME_ID == gid]


def run_audits(D: pd.DataFrame, alphas: dict, games: pd.DataFrame) -> dict:
    """1) Removal audit: blank the audited game's two rows' stat columns (the
    game 'has not happened'); every feature/prediction ON those rows must be
    IDENTICAL -- proves no same-game information enters any feature series.
    2) Perturbation probe: distort the same columns (x3 + 11); predictions on
    those rows must not move. Both run on the REAL pipeline (same code path)."""
    F0 = build_features(D, alphas)
    rng = np.random.default_rng(AUDIT_SEED)
    elig = games[games.eligible & games.season_h.isin(TEST_YEARS)]
    sample = []
    for s in TEST_YEARS:
        pool = elig.loc[elig.season_h == s, "GAME_ID"].to_numpy()
        take = min(AUDIT_GAMES_PER_SEASON, len(pool))
        sample.extend(rng.choice(pool, size=take, replace=False).tolist())
    # force fallback games into the sample so the fallback path is audited too --
    # regardless of eligibility (2025/2026 schedules produced no ELIGIBLE fallback
    # game: every expansion team's first 5 opponents were themselves under the
    # 5-game floor; the substitution path still runs on those rows and must be clean)
    fb_pool = games.loc[games.any_fallback & games.season_h.isin(TEST_YEARS), "GAME_ID"].to_numpy()
    fb_added = [g for g in fb_pool if g not in sample]
    sample.extend(fb_added)

    feat_cols = [f"{p}_{c}" for p in ("raw", "str") for c in CHANNELS] + ["fg3pct_t", "fta_t", "pf_t"]
    out = {"n_games_audited": len(sample), "n_fallback_games_audited": int(
        games.set_index("GAME_ID").loc[sample, "any_fallback"].sum()),
        "removal_mismatch_rows": 0, "perturbation_mismatch_rows": 0,
        "removal_max_abs_diff": 0.0, "perturbation_max_abs_diff": 0.0}

    def compare(Fm: pd.DataFrame, idx: pd.Index) -> tuple[int, float]:
        bad, worst = 0, 0.0
        for colname in feat_cols:
            x0 = F0.loc[idx, colname].to_numpy(float)
            x1 = Fm.loc[idx, colname].to_numpy(float)
            same = np.isclose(x0, x1, rtol=1e-12, atol=1e-9) | (np.isnan(x0) & np.isnan(x1))
            bad += int((~same).sum())
            diffs = np.abs(x0 - x1)
            if np.isfinite(diffs).any():
                worst = max(worst, float(np.nanmax(diffs)))
        return bad, worst

    for gid in sample:
        idx = _rows_of(D, gid)
        # removal: the game's stats do not exist
        Dm = D.copy()
        Dm.loc[idx, STAT_COLS] = np.nan
        b, w = compare(build_features(Dm, alphas), idx)
        out["removal_mismatch_rows"] += b
        out["removal_max_abs_diff"] = max(out["removal_max_abs_diff"], w)
        # perturbation: the game's stats are grossly wrong
        Dp = D.copy()
        Dp.loc[idx, STAT_COLS] = Dp.loc[idx, STAT_COLS].to_numpy(float) * 3.0 + 11.0
        b, w = compare(build_features(Dp, alphas), idx)
        out["perturbation_mismatch_rows"] += b
        out["perturbation_max_abs_diff"] = max(out["perturbation_max_abs_diff"], w)

    out["passed"] = (out["removal_mismatch_rows"] == 0 and out["perturbation_mismatch_rows"] == 0)
    return out


# ---------------------------------------------------------------------------
# channel-level table (July's table, on the new data)
# ---------------------------------------------------------------------------

def channel_table(F: pd.DataFrame, alphas: dict) -> pd.DataFrame:
    rows = []
    rng_seed = SEED_CHANNEL_BOOT
    for ch in CHANNELS:
        act = CH_ACTUAL[ch]
        base_m = (F.season.isin(TEST_YEARS) & (F.prior_games >= MIN_PRIOR) & ~F.fallback_row
                  & F[act].notna() & F[f"raw_{ch}"].notna() & F[f"str_{ch}"].notna())
        for scope, m in [("2024-2026 pooled", base_m)] + [
                (str(s), base_m & (F.season == s)) for s in TEST_YEARS]:
            err_r = (F.loc[m, f"raw_{ch}"] - F.loc[m, act]).abs()
            err_s = (F.loc[m, f"str_{ch}"] - F.loc[m, act]).abs()
            diffs = (err_s - err_r).to_numpy()
            rng = np.random.default_rng(rng_seed)
            boots = np.array([diffs[rng.integers(0, len(diffs), len(diffs))].mean()
                              for _ in range(N_BOOT_CHANNEL)])
            rows.append({
                "channel": ch, "scope": scope, "alpha": alphas[ch], "n_test_rows": int(m.sum()),
                "mae_raw": float(err_r.mean()), "mae_structural": float(err_s.mean()),
                "delta": float(err_s.mean() - err_r.mean()),
                "prob_structural_better": float((boots < 0).mean()),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    frozen = load_frozen_baselines()   # tamper check runs here; raises on drift
    reg = eh.get_registration(EXPERIMENT_ID)
    print(f"registration OK: {EXPERIMENT_ID} (registered {reg['registered_at']}, "
          f"incumbent {reg['incumbent_id']}, regime {reg['regime']})")

    D = load_base()

    # outer splits via the harness (validates season ordering + disjointness)
    splits = eh.walk_forward_by_season(
        D, date_col="GAME_DATE", season_col="season",
        min_train_seasons=3, test_seasons=TEST_YEARS,
    )
    by_name = {s.name: s for s in splits}
    outer24 = by_name["season:2024"]
    train_seasons_24 = sorted(D.loc[outer24.train_idx, "season"].unique())
    assert train_seasons_24 == TRAIN_YEARS, train_seasons_24
    print(f"outer splits: {[s.name for s in splits]}; params fit on {train_seasons_24} only")

    # alphas -- inner walk-forward folds strictly inside 2021-2023
    alphas, alpha_detail = tune_alphas(D, outer24)
    print(f"alphas (inner-fold winners): {alphas}")

    # features + games
    F = build_features(D, alphas)
    games = make_games(F)

    # calibrations: train games = eligible games inside the 2021-2023 window
    train_ids = set(D.loc[outer24.train_idx, "GAME_ID"])
    tg = games[games.GAME_ID.isin(train_ids) & games.eligible]
    assert sorted(tg.season_h.unique()) == TRAIN_YEARS
    cal = fit_calibrations(tg)
    games = apply_calibrations(games, cal)
    print(f"calibration (train 2021-2023, n={cal['n_train_games']} games): "
          + ", ".join(f"{p}_margin a={cal[f'{p}_margin'][0]:.3f} b={cal[f'{p}_margin'][1]:.3f}"
                      for p in ("raw", "str"))
          + f", naive home margin {cal['naive_home_margin']:.3f}")

    # test games strictly via the harness's test indices
    test_frames = {}
    for s in TEST_YEARS:
        split = by_name[f"season:{s}"]
        ids = set(D.loc[split.test_idx, "GAME_ID"])
        sel = games[games.GAME_ID.isin(ids)].copy()
        assert (sel.season_h == s).all()
        test_frames[s] = sel
    test = pd.concat(test_frames.values(), ignore_index=True)
    et = test[test.eligible].copy()

    # fallback accounting
    fb_rows = D[D.fallback_row]
    fb_used = et[et.any_fallback]
    fallback = {
        "fallback_team_rows_by_team": {
            f"{int(s)}-{a}": int(n) for (s, a), n in
            fb_rows.groupby(["season", "TEAM_ABBREVIATION"]).size().items()},
        "eligible_test_games_using_fallback": int(len(fb_used)),
        "fallback_games_by_season": {int(k): int(v) for k, v in
                                     fb_used.groupby("season_h").size().items()},
        "fallback_games_by_team": {},
        "fallback_games_excluded_anyway": 0,
    }
    fb_team_counts: dict = {}
    for _, r in fb_used.iterrows():
        for side in ("h", "a"):
            if r[f"fallback_row_{side}"]:
                key = f"{int(r.season_h)}-{r[f'TEAM_ABBREVIATION_{side}']}"
                fb_team_counts[key] = fb_team_counts.get(key, 0) + 1
    fallback["fallback_games_by_team"] = fb_team_counts
    fallback["fallback_games_excluded_anyway"] = int(
        (test.any_fallback & ~test.eligible).sum())

    # audits BEFORE believing anything
    audits = run_audits(D, alphas, games)
    print(f"audits: removal mismatches={audits['removal_mismatch_rows']}, "
          f"perturbation mismatches={audits['perturbation_mismatch_rows']} "
          f"over {audits['n_games_audited']} games "
          f"({audits['n_fallback_games_audited']} fallback) -> "
          f"{'PASS' if audits['passed'] else 'FAIL'}")
    if not audits["passed"]:
        raise SystemExit("leakage audit FAILED -- results are not evidence; stopping")

    # -------- per-season game-level table --------
    def season_rows(frame, label):
        rows = []
        for s in TEST_YEARS:
            sub = frame[frame.season_h == s]
            if not len(sub):
                continue
            rows.append({
                "scope": label, "season": s, "n_games": int(len(sub)),
                "mae_structural": mae(sub.str_margin_cal - sub.margin_true),
                "mae_raw": mae(sub.raw_margin_cal - sub.margin_true),
                "mae_naive_home": mae(sub.naive_margin_pred - sub.margin_true),
            })
        rows.append({
            "scope": label, "season": "pooled", "n_games": int(len(frame)),
            "mae_structural": mae(frame.str_margin_cal - frame.margin_true),
            "mae_raw": mae(frame.raw_margin_cal - frame.margin_true),
            "mae_naive_home": mae(frame.naive_margin_pred - frame.margin_true),
        })
        return rows

    season_table = pd.DataFrame(
        season_rows(et, "all eligible") + season_rows(et[~et.any_fallback], "excl fallback games"))
    print(season_table.round(3).to_string(index=False))

    # -------- channel-level table + residual covariance --------
    ch_table = channel_table(F, alphas)
    print(ch_table[ch_table.scope == "2024-2026 pooled"].round(3).to_string(index=False))

    resid = {}
    for p in ("raw", "str"):
        errs = pd.DataFrame({
            c: pd.concat([et[f"{p}_{c}_h"] - et[f"{CH_ACTUAL[c]}_h"],
                          et[f"{p}_{c}_a"] - et[f"{CH_ACTUAL[c]}_a"]], ignore_index=True)
            for c in CHANNELS})
        resid[p] = errs.cov().round(3)

    # -------- gate 4 joint check: home / away / margin / total must not degrade
    joint_tol = float(reg["thresholds"]["harm_ci_bound"])  # preregistered degradation bound

    def joint_check():
        comps = {}
        for name, t_col, c_col, i_col in [
            ("home_score", "team_pts_h", "str_home_cal", "raw_home_cal"),
            ("away_score", "team_pts_a", "str_away_cal", "raw_away_cal"),
            ("margin", "margin_true", "str_margin_cal", "raw_margin_cal"),
            ("total", "total_true", "str_total_cal", "raw_total_cal"),
        ]:
            m_ch = mae(et[c_col] - et[t_col])
            m_inc = mae(et[i_col] - et[t_col])
            comps[name] = {"challenger_mae": round(m_ch, 4), "incumbent_mae": round(m_inc, 4),
                           "delta_improvement": round(m_inc - m_ch, 4)}
        ok = all(c["challenger_mae"] <= c["incumbent_mae"] + joint_tol for c in comps.values())
        return ok, {"tolerance": joint_tol, "components": comps}

    # -------- coverage: eligible predicted games / all test-season games ------
    n_total_test_games = int(D[D.season.isin(TEST_YEARS)].GAME_ID.nunique())
    cov = len(et) / n_total_test_games          # identical rule for both models

    # -------- the registered comparison --------
    # home_team = franchise TEAM_ID (stable across the 2025 PHO->PHX rename) so
    # the team-clustered sensitivity CI clusters franchises, not abbreviations.
    # (Run 1 on the ledger used abbreviations: 16 clusters, Phoenix split across
    # eras; sensitivity-only, primary date clustering unaffected -- see REPORT.md.)
    ch_frame = et[["GAME_ID", "GAME_DATE_h", "season_h", "margin_true", "str_margin_cal",
                   "TEAM_ID_h"]].rename(columns={
        "GAME_ID": "game_id", "GAME_DATE_h": "game_date", "season_h": "season",
        "margin_true": "y_true", "str_margin_cal": "y_pred", "TEAM_ID_h": "home_team"})
    inc_frame = et[["GAME_ID", "margin_true", "raw_margin_cal"]].rename(columns={
        "GAME_ID": "game_id", "margin_true": "y_true", "raw_margin_cal": "y_pred"})
    result = eh.compare_to_incumbent(
        ch_frame, inc_frame,
        experiment_id=EXPERIMENT_ID,
        joint_check=joint_check,
        coverage=(cov, cov),
    )
    print(f"VERDICT: {result.verdict} (promote={result.promote}); "
          f"pooled improvement {result.pooled_improvement:.3f} "
          f"[90% CI {result.ci_low:.3f}, {result.ci_high:.3f}], "
          f"failed gates: {result.failed_gates}")

    # -------- outputs --------
    ch_table.to_csv(HERE / "channel_results_v2.csv", index=False)
    season_table.to_csv(HERE / "game_level_results_v2.csv", index=False)
    pred_cols = ["GAME_ID", "GAME_DATE_h", "season_h", "season_type_h",
                 "TEAM_ABBREVIATION_h", "TEAM_ABBREVIATION_a", "any_fallback",
                 "fallback_row_h", "fallback_row_a", "margin_true", "total_true",
                 "team_pts_h", "team_pts_a",
                 "raw_margin_uncal", "raw_margin_cal", "str_margin_uncal", "str_margin_cal",
                 "raw_home_cal", "raw_away_cal", "str_home_cal", "str_away_cal",
                 "raw_total_cal", "str_total_cal", "naive_margin_pred"]
    et[pred_cols].to_csv(HERE / "predictions_v2.csv", index=False)

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "run_number": result.run_number,
        "eval_time": result.eval_time,
        "alphas": alphas,
        "alpha_detail": alpha_detail,
        "calibration": {k: v for k, v in cal.items()},
        "n_total_test_games": n_total_test_games,
        "n_eligible_test_games": int(len(et)),
        "coverage": cov,
        "per_season_table": season_table.to_dict(orient="records"),
        "channel_table": ch_table.to_dict(orient="records"),
        "residual_covariance_structural": resid["str"].to_dict(),
        "residual_covariance_raw": resid["raw"].to_dict(),
        "fallback": fallback,
        "audits": audits,
        "joint_check": joint_check()[1],
        "gate_verdict": result.to_dict(),
        "frozen_references": {
            "incumbent_structural_chains_2024_25": frozen_baseline_value("incumbent_structural_chains"),
            "raw_trend_channel_sum_2024_25": frozen_baseline_value("raw_trend_channel_sum"),
            "home_advantage_only_2024_25": frozen_baseline_value("home_advantage_only"),
        },
        "n_frozen_baseline_rows_verified": int(len(frozen)),
    }
    with open(HERE / "run_summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)
    print(f"wrote channel_results_v2.csv, game_level_results_v2.csv, predictions_v2.csv, run_summary.json")


if __name__ == "__main__":
    main()
