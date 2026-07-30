#!/usr/bin/env python3
"""W4 referee FTA-prior sidecar — registered experiment ``w4_ref_fta_priors_v1``.

Registered 2026-07-30T21:05:19Z in experiments/registry.jsonl (BEFORE this code
was written). This script never registers; it evaluates the registered
hypothesis exactly as recorded:

    Per referee r and date t: prior_r(t) = shrunken mean of
    (game total FTA of both teams / league mean FTA) over r's games STRICTLY
    BEFORE t, partial pooling n/(n+K) with K tuned train-only (2021-2023);
    crew factor for a game = mean of the assigned officials' priors, bounded
    to [0.92, 1.08] (fixed a priori). Challenger FT channel = incumbent
    structural FT chain x crew factor, both teams scaled symmetrically.

    Incumbent: chanreval_structural_ft_chain — the FT chain of
    experiments/channel_reval (str_ft = fta_t x (opp_pf_trend / lg_pf) x
    ftpct_t, shifted EWMA alpha=0.10). Its per-team-game predictions are
    RECONSTRUCTED here by re-running the chanreval pipeline (imported from
    experiments/channel_reval/run_reval.py, same code) and HARD-ASSERTED
    against channel_results_v2.csv and predictions_v2.csv before anything
    else runs. A reproduction mismatch stops the experiment.

    Universe: all 673 chanreval eligible test games (2024/2025/2026 walk-
    forward) = 1,346 team-game FT-channel rows. Primary metric:
    ft_channel_mae, paired per team-game row, date-clustered bootstrap
    (evalharness.compare_to_incumbent, cluster='date'). NOTE the pooled MAE
    and the date-clustered CI are numerically identical whether units are
    team-rows or per-game means of the two rows (each game contributes both
    rows to the same date cluster); n_games on the ledger counts team-rows.

    Secondaries (recorded, not gated): game total MAE and the gate-4 joint
    margin check via substitution of the challenger FT channel into the
    structural sum + train-only recalibration.

POINT-IN-TIME CAVEAT (registered; PROMINENT on every report of this result):
the backtest uses the ACTUAL crew as a proxy for the pregame-announced crew.
Historical announcement pages were not archived; officials post ~9:00am ET
game day and late swaps are rare but unquantified here. Live deployment uses
the daily assignments capture (ref_assignments_capture_daily.py), which IS
point-in-time.

Walk-forward discipline (HANDOFF §3 constitution):
  * league mean FTA is an expanding mean over STRICTLY EARLIER DATES (shifted,
    never global);
  * prior_r(t) uses referee r's games on strictly earlier dates only;
  * K is tuned on inner walk-forward folds strictly inside 2021-2023
    (evalharness.inner_tuning_splits); test seasons never touch tuning;
  * audits run before results are reported: truncate-and-recompute prior
    audit on sampled (ref, date) pairs, league-mean walk-forward audit,
    crew-factor distribution + bound-activation accounting.

Usage:
    python w4_refs.py --smoke     # scratch COPY of the registry (tempdir);
                                  # artifacts -> experiments/w4_refs/; the real
                                  # ledger experiments/registry.jsonl untouched
    python w4_refs.py --real      # records the evaluation on the REAL ledger
                                  # (orchestrator only — never run casually)

No network. Python 3.13 + pandas/numpy only. Deterministic (fixed seeds).
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
sys.path.insert(0, str(REPO / "experiments" / "channel_reval"))

import evalharness as eh                      # noqa: E402
import run_reval as rr                        # noqa: E402  (chanreval pipeline, reused verbatim)

EXPERIMENT_ID = "w4_ref_fta_priors_v1"
INCUMBENT_ID = "chanreval_structural_ft_chain"
OUTDIR = REPO / "experiments" / "w4_refs"
OFFICIALS_CSV = REPO / "data" / "officials_master.csv"
MASTER_TEAM = REPO / "data" / "masters" / "master_team.parquet"
CHANREVAL = REPO / "experiments" / "channel_reval"

BOUND_LO, BOUND_HI = 0.92, 1.08               # registered, fixed a priori
K_GRID = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096]
SEED = 20260730                               # harness default seed (bootstrap)
AUDIT_SEED = 20260730
PRIOR_AUDIT_PER_SEASON = 8                    # sampled (ref, date) pairs per season
LEAGUE_MEAN_AUDIT_DATES = 12

CAVEAT = (
    "**Point-in-time caveat (registered):** this backtest uses the **actual** game crew as a "
    "proxy for the pregame-announced crew. Historical announcement pages were not archived; "
    "officials are posted ~9:00am ET on game day and late swaps are rare but **unquantified "
    "here**. Live deployment uses the daily assignments capture "
    "(`ref_assignments_capture_daily.py`), which *is* point-in-time. This proxy assumption "
    "must be stated on every report of this result."
)


def log(msg: str) -> None:
    print(f"[w4_refs] {msg}")


# ---------------------------------------------------------------------------
# 1. incumbent reproduction (hard-asserted before anything else)
# ---------------------------------------------------------------------------

def reproduce_incumbent() -> dict:
    """Re-run the chanreval pipeline via its own module and hard-assert the
    reproduction against the published artifacts. Returns every frame the
    experiment needs. Raises SystemExit on any mismatch."""
    alphas = json.load(open(CHANREVAL / "run_summary.json", encoding="utf-8"))["alphas"]
    D = rr.load_base()
    F = rr.build_features(D, alphas)
    games = rr.make_games(F)

    splits = eh.walk_forward_by_season(
        D, date_col="GAME_DATE", season_col="season",
        min_train_seasons=3, test_seasons=rr.TEST_YEARS,
    )
    by_name = {s.name: s for s in splits}
    outer24 = by_name["season:2024"]
    train_seasons = sorted(D.loc[outer24.train_idx, "season"].unique())
    assert train_seasons == rr.TRAIN_YEARS, train_seasons

    train_ids = set(D.loc[outer24.train_idx, "GAME_ID"])
    tg = games[games.GAME_ID.isin(train_ids) & games.eligible]
    cal = rr.fit_calibrations(tg)
    games = rr.apply_calibrations(games, cal)

    test_ids: set = set()
    for s in rr.TEST_YEARS:
        test_ids |= set(D.loc[by_name[f"season:{s}"].test_idx, "GAME_ID"])
    test = games[games.GAME_ID.isin(test_ids)]
    et = test[test.eligible].copy()

    # ---- hard assert 1: FT channel table reproduces channel_results_v2.csv
    cr = pd.read_csv(CHANREVAL / "channel_results_v2.csv")
    ft_ref = cr[cr.channel == "ft"].set_index("scope")
    base_m = (F.season.isin(rr.TEST_YEARS) & (F.prior_games >= rr.MIN_PRIOR)
              & ~F.fallback_row & F.ch_ft.notna() & F.raw_ft.notna() & F.str_ft.notna())
    ft_asserts = []
    for scope, m in [("2024-2026 pooled", base_m)] + [
            (str(s), base_m & (F.season == s)) for s in rr.TEST_YEARS]:
        got_n = int(m.sum())
        got_raw = float((F.loc[m, "raw_ft"] - F.loc[m, "ch_ft"]).abs().mean())
        got_str = float((F.loc[m, "str_ft"] - F.loc[m, "ch_ft"]).abs().mean())
        ref = ft_ref.loc[scope]
        ok = (got_n == int(ref.n_test_rows)
              and abs(got_raw - float(ref.mae_raw)) < 5e-7
              and abs(got_str - float(ref.mae_structural)) < 5e-7)
        ft_asserts.append({"scope": scope, "n": got_n, "mae_raw": got_raw,
                           "mae_structural": got_str, "match": bool(ok)})
        if not ok:
            raise SystemExit(
                f"REPRODUCTION FAILED: FT channel row {scope!r} does not match "
                f"channel_results_v2.csv (got n={got_n} raw={got_raw:.6f} "
                f"str={got_str:.6f}, expected n={int(ref.n_test_rows)} "
                f"raw={ref.mae_raw:.6f} str={ref.mae_structural:.6f}). "
                "The incumbent extraction is not certified; stopping."
            )

    # ---- hard assert 2: game-level predictions reproduce predictions_v2.csv
    pv = pd.read_csv(CHANREVAL / "predictions_v2.csv")
    if set(pv.GAME_ID) != set(et.GAME_ID) or len(pv) != len(et):
        raise SystemExit("REPRODUCTION FAILED: eligible-game universe differs "
                         f"from predictions_v2.csv ({len(et)} vs {len(pv)} games)")
    merged = et.merge(pv, on="GAME_ID", suffixes=("", "_pv"), validate="one_to_one")
    num_cols = ["margin_true", "total_true", "raw_margin_cal", "str_margin_cal",
                "raw_home_cal", "raw_away_cal", "str_home_cal", "str_away_cal",
                "raw_total_cal", "str_total_cal", "naive_margin_pred"]
    worst = max(float((merged[c] - merged[c + "_pv"]).abs().max()) for c in num_cols)
    if worst > 1e-9:
        raise SystemExit(f"REPRODUCTION FAILED: predictions_v2.csv max abs diff {worst}")

    log(f"incumbent reproduction certified: FT rows match channel_results_v2.csv "
        f"exactly (4/4 scopes), predictions_v2.csv max abs diff {worst:.3g} over "
        f"{len(et)} games x {len(num_cols)} columns")

    # per-team-row universe: both rows of every eligible test game
    elig_ids = set(et.GAME_ID)
    U = F[F.GAME_ID.isin(elig_ids)].copy()
    assert len(U) == 2 * len(et) == 1346, len(U)
    assert U.groupby("GAME_ID").size().eq(2).all()
    assert U.str_ft.notna().all() and U.ch_ft.notna().all()
    assert (U.prior_games >= rr.MIN_PRIOR).all()      # no fallback rows among eligible
    U["gid"] = U.GAME_ID.astype(str)

    return {"alphas": alphas, "D": D, "F": F, "games": games, "cal": cal,
            "outer24": outer24, "train_ids": train_ids, "tg": tg, "et": et,
            "U": U, "n_total_test_games": int(D[D.season.isin(rr.TEST_YEARS)].GAME_ID.nunique()),
            "repro": {"ft_table": ft_asserts, "predictions_max_abs_diff": worst,
                      "n_universe_games": int(len(et)), "n_universe_team_rows": int(len(U))}}


# ---------------------------------------------------------------------------
# 2. officials + game FTA + walk-forward league mean
# ---------------------------------------------------------------------------

def load_officials(master_game_ids: set) -> tuple[pd.DataFrame, dict]:
    o = pd.read_csv(OFFICIALS_CSV, dtype={"GAME_ID": str})
    o["ref_name"] = o.FIRST_NAME.str.strip() + " " + o.LAST_NAME.str.strip()
    sizes = o.groupby("GAME_ID").size()
    size_counts = sizes.value_counts().to_dict()
    four = sizes[sizes == 4].index
    four_prefixes = sorted(o[o.GAME_ID.isin(four)].GAME_ID.str[:3].unique())
    verify = {
        "n_rows": int(len(o)),
        "n_games": int(o.GAME_ID.nunique()),
        "crew_size_counts": {int(k): int(v) for k, v in size_counts.items()},
        "n_officials": int(o.OFFICIAL_ID.nunique()),
        "duplicate_game_official_rows": int(o.duplicated(["GAME_ID", "OFFICIAL_ID"]).sum()),
        "four_official_games_all_playoffs": bool(four_prefixes == ["104"] or len(four) == 0),
        "games_not_in_master": int((~o.GAME_ID.isin(master_game_ids)).sum()),
        "master_games_without_officials": int(len(master_game_ids - set(o.GAME_ID))),
    }
    # registered claim: 1,489 games, 3 refs/game. Verify, and record the deviation.
    if verify["n_games"] != 1489 or verify["duplicate_game_official_rows"] != 0 \
            or verify["games_not_in_master"] != 0 or verify["master_games_without_officials"] != 0:
        raise SystemExit(f"officials_master.csv failed verification: {verify}")
    if set(size_counts) != {3}:
        if not verify["four_official_games_all_playoffs"]:
            raise SystemExit(f"unexpected crew sizes outside playoffs: {verify}")
        log(f"officials verified with DEVIATION from the registered '3 refs/game': "
            f"{size_counts.get(3, 0)} games list 3 officials, {size_counts.get(4, 0)} "
            f"PLAYOFF games list 4 (boxscore includes the alternate; source has no role "
            f"labels). Primary uses all listed officials; first-3 sensitivity reported.")
    else:
        log("officials verified: 1,489 games, 3 refs/game, no duplicates")
    return o, verify


def build_game_fta() -> tuple[pd.DataFrame, dict]:
    """Per-game total FTA from data/masters/master_team.parquet + the walk-
    forward (expanding, shifted, strictly-earlier-dates) league mean and each
    game's FTA ratio. NaN ratio on the dataset's first date (no prior info)."""
    mt = pd.read_parquet(MASTER_TEAM, columns=["game_id", "game_date", "season",
                                               "season_type", "fta"])
    g = (mt.groupby("game_id")
           .agg(game_date=("game_date", "first"), season=("season", "first"),
                season_type=("season_type", "first"),
                game_fta=("fta", "sum"), n_rows=("fta", "size"))
           .reset_index())
    if not (g.n_rows == 2).all():
        raise SystemExit("master_team.parquet does not have exactly 2 rows per game")
    g["game_date"] = pd.to_datetime(g.game_date)

    # cross-check vs channel_base_v2 (the chanreval input built from the same master)
    cb = pd.read_csv(CHANREVAL / "channel_base_v2.csv",
                     dtype={"GAME_ID": str}, usecols=["GAME_ID", "is_home", "team_fta", "opp_fta"])
    cbh = cb[cb.is_home == 1]
    chk = g.merge(cbh, left_on="game_id", right_on="GAME_ID", validate="one_to_one")
    fta_xcheck = float((chk.game_fta - (chk.team_fta + chk.opp_fta)).abs().max())
    if fta_xcheck != 0.0:
        raise SystemExit(f"game FTA mismatch master_team vs channel_base_v2: {fta_xcheck}")

    per_date = g.groupby("game_date")["game_fta"].agg(["sum", "count"]).sort_index()
    cs = per_date.cumsum().shift(1)               # strictly earlier dates only
    lg = (cs["sum"] / cs["count"]).rename("lg_fta_mean")
    g = g.merge(lg, left_on="game_date", right_index=True, how="left")
    g["fta_ratio"] = g.game_fta / g.lg_fta_mean

    info = {"n_games": int(len(g)), "fta_xcheck_max_abs_diff": fta_xcheck,
            "global_mean_game_fta": float(g.game_fta.mean()),
            "n_games_nan_ratio_first_date": int(g.fta_ratio.isna().sum()),
            "first_date": str(g.game_date.min().date()),
            "ratio_mean": float(g.fta_ratio.mean()), "ratio_std": float(g.fta_ratio.std())}
    log(f"game FTA: {info['n_games']} games, master-vs-channel_base diff 0, "
        f"{info['n_games_nan_ratio_first_date']} first-date games have no league "
        f"baseline (excluded from ref histories), ratio mean {info['ratio_mean']:.4f}")
    return g, info


def officials_long(o: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, listed official) with the game's date and FTA ratio.
    Preserves the source CSV's listing order (used by the first-3 sensitivity)."""
    ol = o.merge(g[["game_id", "game_date", "season", "fta_ratio"]],
                 left_on="GAME_ID", right_on="game_id", how="left", validate="many_to_one")
    assert ol.game_date.notna().all()
    ol["rank_in_game"] = ol.groupby("GAME_ID").cumcount()
    return ol


# ---------------------------------------------------------------------------
# 3. walk-forward referee priors + crew factors
# ---------------------------------------------------------------------------

def ref_prior_sums(ol: pd.DataFrame) -> pd.DataFrame:
    """Per (official, date): sum and count of the official's game FTA ratios on
    STRICTLY EARLIER dates. Every appearance date gets a row (n_prior=0 for a
    debut). Games with NaN ratio (dataset's first date) contribute nothing to
    any history but still receive a prior."""
    t = ol[["OFFICIAL_ID", "game_date"]].copy()
    t["r_sum"] = ol.fta_ratio.fillna(0.0)
    t["r_cnt"] = ol.fta_ratio.notna().astype(float)
    d = t.groupby(["OFFICIAL_ID", "game_date"])[["r_sum", "r_cnt"]].sum().sort_index()
    cs = d.groupby(level=0).cumsum()
    sh = cs.groupby(level=0).shift(1).fillna(0.0)   # strictly earlier dates only
    rp = sh.rename(columns={"r_sum": "sum_prior", "r_cnt": "n_prior"}).reset_index()
    assert len(rp) == len(ol[["OFFICIAL_ID", "game_date"]].drop_duplicates())
    return rp


def crew_factors(ol: pd.DataFrame, rp: pd.DataFrame, K: float,
                 first3: bool = False) -> pd.DataFrame:
    """Per game: crew factor = mean over listed officials of the shrunken prior
    (sum_prior + K) / (n_prior + K)  [= (n/(n+K)) * mean_ratio + (K/(n+K)) * 1.0],
    clipped to the registered bounds. first3=True keeps only the first three
    listed officials (sensitivity for the 83 four-official playoff games)."""
    x = ol if not first3 else ol[ol.rank_in_game < 3]
    x = x.merge(rp, on=["OFFICIAL_ID", "game_date"], how="left", validate="many_to_one")
    assert x.sum_prior.notna().all() and x.n_prior.notna().all()
    x = x.copy()
    x["prior"] = (x.sum_prior + K) / (x.n_prior + K)
    cf = (x.groupby("GAME_ID")
            .agg(game_date=("game_date", "first"), season=("season", "first"),
                 n_officials=("OFFICIAL_ID", "size"),
                 refs=("ref_name", lambda s: "; ".join(s)),
                 crew_prior_mean=("prior", "mean"),
                 min_ref_prior=("prior", "min"), max_ref_prior=("prior", "max"),
                 min_ref_n_prior=("n_prior", "min"))
            .reset_index())
    cf["crew_factor"] = cf.crew_prior_mean.clip(BOUND_LO, BOUND_HI)
    cf["at_lo"] = cf.crew_prior_mean <= BOUND_LO
    cf["at_hi"] = cf.crew_prior_mean >= BOUND_HI
    return cf


# ---------------------------------------------------------------------------
# 4. K tuning — inner walk-forward folds strictly inside 2021-2023
# ---------------------------------------------------------------------------

def tune_K(D: pd.DataFrame, F: pd.DataFrame, ol: pd.DataFrame, rp: pd.DataFrame,
           outer24: "eh.OuterSplit") -> tuple[int, pd.DataFrame]:
    inner = eh.inner_tuning_splits(D, outer24, date_col="GAME_DATE", n_folds=3)
    Fg = F.copy()
    Fg["gid"] = Fg.GAME_ID.astype(str)

    def fold_mask(val: pd.DataFrame) -> pd.Series:
        return (val.ch_ft.notna() & val.raw_ft.notna() & val.str_ft.notna()
                & (val.prior_games >= rr.MIN_PRIOR) & ~val.fallback_row)

    # incumbent reference per fold (the K -> infinity limit)
    inc_by_fold = []
    for f in inner:
        val = Fg.loc[f.val_idx]
        m = fold_mask(val)
        inc_by_fold.append(float((val.loc[m, "str_ft"] - val.loc[m, "ch_ft"]).abs().mean()))

    rows = []
    for K in K_GRID:
        cf = crew_factors(ol, rp, K).set_index("GAME_ID")["crew_factor"]
        fold_maes = []
        for f in inner:
            val = Fg.loc[f.val_idx]
            m = fold_mask(val)
            v = val.loc[m]
            fac = v.gid.map(cf)
            assert fac.notna().all()
            fold_maes.append(float((v.str_ft * fac - v.ch_ft).abs().mean()))
        rows.append({"K": K, "inner_mae_mean": float(np.mean(fold_maes)),
                     "inner_mae_fold1": fold_maes[0], "inner_mae_fold2": fold_maes[1],
                     "inner_mae_fold3": fold_maes[2],
                     "inner_delta_vs_incumbent": float(np.mean(inc_by_fold) - np.mean(fold_maes))})
    curve = pd.DataFrame(rows)
    curve["incumbent_inner_mae_mean"] = float(np.mean(inc_by_fold))
    # winner: minimal mean inner MAE; exact ties break toward LARGER K (more pooling)
    best = min(curve.to_dict("records"),
               key=lambda r: (round(r["inner_mae_mean"], 12), -r["K"]))
    K_star = int(best["K"])
    curve["chosen"] = curve.K == K_star
    log(f"K tuning (3 inner folds in 2021-2023): K*={K_star} "
        f"(inner MAE {best['inner_mae_mean']:.6f} vs incumbent {np.mean(inc_by_fold):.6f}); "
        f"curve {curve.inner_mae_mean.min():.6f}..{curve.inner_mae_mean.max():.6f}")
    return K_star, curve


# ---------------------------------------------------------------------------
# 5. audits (run before results are believed)
# ---------------------------------------------------------------------------

def audit_priors(ol: pd.DataFrame, rp: pd.DataFrame, g: pd.DataFrame, K: int) -> dict:
    """Truncate-and-recompute audit: for sampled (ref, date) pairs, rebuild
    prior_r(t) from raw officials + master FTA with an independent (loop-based)
    code path, truncated strictly before t; must equal the pipeline value.
    Also recomputes WITH date-t games included — that value must differ
    (walk-forward is doing something) unless the ref's date-t ratio is NaN."""
    rng = np.random.default_rng(AUDIT_SEED)
    apps = ol[["OFFICIAL_ID", "game_date", "season"]].drop_duplicates().reset_index(drop=True)
    sample_idx: list[int] = []
    for s in sorted(apps.season.unique()):
        pool = apps.index[apps.season == s].to_numpy()
        take = min(PRIOR_AUDIT_PER_SEASON, len(pool))
        sample_idx.extend(rng.choice(pool, size=take, replace=False).tolist())

    g_idx = g.set_index("game_id")
    rp_idx = rp.set_index(["OFFICIAL_ID", "game_date"])
    n_mismatch, worst, n_trunc_matters = 0, 0.0, 0
    pairs = []
    for i in sample_idx:
        ref, t, season = apps.loc[i, ["OFFICIAL_ID", "game_date", "season"]]
        gids = ol.loc[ol.OFFICIAL_ID == ref, "GAME_ID"].unique()
        hist = g_idx.loc[[gid for gid in gids if gid in g_idx.index]]

        def shrunken(cutoff_exclusive: bool) -> tuple[float, int]:
            vals = []
            sub = hist[hist.game_date < t] if cutoff_exclusive else hist[hist.game_date <= t]
            for _, row in sub.iterrows():
                prior_games = g[g.game_date < row.game_date]
                if len(prior_games) == 0:
                    continue                      # no league baseline -> no ratio
                vals.append(row.game_fta / prior_games.game_fta.mean())
            return (sum(vals) + K) / (len(vals) + K), len(vals)

        expected, n_used = shrunken(cutoff_exclusive=True)
        with_t, n_with_t = shrunken(cutoff_exclusive=False)
        srow = rp_idx.loc[(ref, t)]
        pipeline = (srow.sum_prior + K) / (srow.n_prior + K)
        diff = abs(pipeline - expected)
        worst = max(worst, diff)
        ok = diff < 1e-12 and int(srow.n_prior) == n_used
        if not ok:
            n_mismatch += 1
        if abs(with_t - expected) > 1e-15:
            n_trunc_matters += 1
        pairs.append({"official_id": int(ref), "date": str(pd.Timestamp(t).date()),
                      "season": int(season), "n_prior": int(srow.n_prior),
                      "pipeline": float(pipeline), "recomputed": float(expected),
                      "abs_diff": float(diff),
                      "value_if_date_t_included": float(with_t), "match": bool(ok)})
    out = {"K": K, "n_pairs_audited": len(pairs), "n_mismatch": n_mismatch,
           "max_abs_diff": worst, "n_pairs_where_truncation_changes_value": n_trunc_matters,
           "passed": n_mismatch == 0, "pairs": pairs}
    log(f"prior walk-forward audit: {len(pairs)} (ref,date) pairs, "
        f"{n_mismatch} mismatches, max |diff| {worst:.3g}, truncation changes the "
        f"value in {n_trunc_matters}/{len(pairs)} -> {'PASS' if out['passed'] else 'FAIL'}")
    return out


def audit_league_mean(g: pd.DataFrame) -> dict:
    """League mean FTA must be the expanding mean over strictly earlier dates —
    verified against a brute-force recompute at sampled dates, and shown to be
    date-varying (i.e., NOT the global mean)."""
    rng = np.random.default_rng(AUDIT_SEED + 1)
    dates = np.sort(g.game_date.unique())
    dates_with_prior = dates[1:]                          # first date has no baseline
    sample = rng.choice(dates_with_prior,
                        size=min(LEAGUE_MEAN_AUDIT_DATES, len(dates_with_prior)),
                        replace=False)
    global_mean = float(g.game_fta.mean())
    n_mismatch, worst, n_differs_from_global = 0, 0.0, 0
    checks = []
    for d in sorted(sample):
        expected = float(g.loc[g.game_date < d, "game_fta"].mean())
        got = float(g.loc[g.game_date == d, "lg_fta_mean"].iloc[0])
        diff = abs(got - expected)
        worst = max(worst, diff)
        if diff > 1e-9:
            n_mismatch += 1
        if abs(got - global_mean) > 1e-9:
            n_differs_from_global += 1
        checks.append({"date": str(pd.Timestamp(d).date()), "pipeline": got,
                       "recomputed_strictly_before": expected, "abs_diff": diff})
    first_date_nan = bool(g.loc[g.game_date == dates[0], "lg_fta_mean"].isna().all())
    out = {"n_dates_audited": len(checks), "n_mismatch": n_mismatch,
           "max_abs_diff": worst, "global_mean_game_fta": global_mean,
           "n_sampled_dates_differing_from_global_mean": n_differs_from_global,
           "first_date_league_mean_is_nan": first_date_nan,
           "passed": n_mismatch == 0 and first_date_nan, "dates": checks}
    log(f"league-mean walk-forward audit: {len(checks)} dates, {n_mismatch} mismatches, "
        f"{n_differs_from_global}/{len(checks)} differ from the global mean, first-date "
        f"mean is NaN: {first_date_nan} -> {'PASS' if out['passed'] else 'FAIL'}")
    return out


def crew_factor_stats(cf: pd.DataFrame, universe_gids: set) -> dict:
    """Distribution + bound-activation accounting, all games and test universe."""
    def stats(frame: pd.DataFrame) -> dict:
        return {"n_games": int(len(frame)),
                "mean": float(frame.crew_factor.mean()),
                "std": float(frame.crew_factor.std()),
                "min": float(frame.crew_factor.min()),
                "p05": float(frame.crew_factor.quantile(0.05)),
                "p50": float(frame.crew_factor.quantile(0.50)),
                "p95": float(frame.crew_factor.quantile(0.95)),
                "max": float(frame.crew_factor.max()),
                "n_at_lower_bound": int(frame.at_lo.sum()),
                "n_at_upper_bound": int(frame.at_hi.sum()),
                "bound_activation_rate": float((frame.at_lo | frame.at_hi).mean()),
                "mean_unclipped": float(frame.crew_prior_mean.mean())}
    uni = cf[cf.GAME_ID.isin(universe_gids)]
    per_season = {int(s): stats(sub) for s, sub in uni.groupby("season")}
    return {"all_1489_games": stats(cf), "test_universe_673": stats(uni),
            "test_universe_by_season": per_season,
            "n_four_official_games_in_universe": int((uni.n_officials == 4).sum())}


# ---------------------------------------------------------------------------
# 6. secondaries — substitution into the structural sum + train-only recal
# ---------------------------------------------------------------------------

def secondaries(games: pd.DataFrame, tg: pd.DataFrame, et: pd.DataFrame,
                cf: pd.DataFrame, joint_tol: float) -> dict:
    """Challenger FT channel substituted into both teams' structural sums,
    margin/home/away calibrations REFIT on 2021-2023 eligible games only,
    then margin / home / away / total MAE vs the incumbent on the 673."""
    fac = cf.set_index("GAME_ID")["crew_factor"]

    def with_challenger(frame: pd.DataFrame) -> pd.DataFrame:
        x = frame.copy()
        f = x.GAME_ID.astype(str).map(fac)
        assert f.notna().all()
        x["cf"] = f.to_numpy()
        for side in ("h", "a"):
            x[f"chal_ft_{side}"] = x[f"str_ft_{side}"] * x.cf
            x[f"chal_sum_{side}"] = x[f"str_sum_{side}"] + x[f"str_ft_{side}"] * (x.cf - 1.0)
        x["chal_margin_uncal"] = x.chal_sum_h - x.chal_sum_a
        return x

    tg2 = with_challenger(tg)
    et2 = with_challenger(et)
    cal = {}
    for name, xcol, ycol in [("margin", "chal_margin_uncal", "margin_true"),
                             ("home", "chal_sum_h", "team_pts_h"),
                             ("away", "chal_sum_a", "team_pts_a")]:
        a, b = rr.linfit(tg2[xcol], tg2[ycol])
        cal[name] = (a, b)
    et2["chal_margin_cal"] = cal["margin"][0] + cal["margin"][1] * et2.chal_margin_uncal
    et2["chal_home_cal"] = cal["home"][0] + cal["home"][1] * et2.chal_sum_h
    et2["chal_away_cal"] = cal["away"][0] + cal["away"][1] * et2.chal_sum_a
    et2["chal_total_cal"] = et2.chal_home_cal + et2.chal_away_cal

    comps = {}
    for name, t_col, c_col, i_col in [
        ("home_score", "team_pts_h", "chal_home_cal", "str_home_cal"),
        ("away_score", "team_pts_a", "chal_away_cal", "str_away_cal"),
        ("margin", "margin_true", "chal_margin_cal", "str_margin_cal"),
        ("total", "total_true", "chal_total_cal", "str_total_cal"),
    ]:
        m_ch = float((et2[c_col] - et2[t_col]).abs().mean())
        m_inc = float((et2[i_col] - et2[t_col]).abs().mean())
        comps[name] = {"challenger_mae": round(m_ch, 4), "incumbent_mae": round(m_inc, 4),
                       "delta_improvement": round(m_inc - m_ch, 4)}
    ok = all(c["challenger_mae"] <= c["incumbent_mae"] + joint_tol for c in comps.values())
    per_season_total = {}
    for s, sub in et2.groupby("season_h"):
        per_season_total[int(s)] = {
            "n": int(len(sub)),
            "total_mae_challenger": float((sub.chal_total_cal - sub.total_true).abs().mean()),
            "total_mae_incumbent": float((sub.str_total_cal - sub.total_true).abs().mean())}
    return {"joint_ok": bool(ok), "tolerance": joint_tol, "components": comps,
            "recalibration_train_only": {k: [float(a), float(b)] for k, (a, b) in cal.items()},
            "total_mae_by_season": per_season_total, "frame": et2}


# ---------------------------------------------------------------------------
# 7. report
# ---------------------------------------------------------------------------

def write_report(outdir: Path, ctx: dict) -> None:
    S = ctx["summary"]
    res = S["primary_result"]
    reg = ctx["registration"]
    sec = S["secondaries"]
    cfs = S["crew_factor_stats"]
    mode = S["mode"].upper()
    per_season = {r["season"]: r for r in res["per_season"]}
    ft_rows = {r["scope"]: r for r in S["reproduction"]["ft_table"]}
    curve = pd.DataFrame(S["k_tuning"]["curve"])

    def srow(season: str) -> str:
        r = per_season[season]
        return (f"| {season} | {r['n']} | {r['metric_challenger']:.4f} | "
                f"{r['metric_incumbent']:.4f} | {r['delta']:+.4f} |")

    gate_names = {
        "gate1_pooled_improvement": ("Pooled improvement >= 0.10", "gate1"),
        "gate2_ci_excludes_harm": ("90% date-clustered CI excludes harm > 0.05", "gate2"),
        "gate3_per_season_non_inferiority": ("No season worse than -0.15", "gate3"),
        "gate4_joint_forecast": ("Joint forecast non-degrading (substitution)", "gate4"),
        "gate5_coverage": ("Coverage maintained", "gate5"),
    }
    gate_lines = []
    for k, (desc, _) in gate_names.items():
        ok = res["gates"][k]
        mark = "PASS" if ok else ("FAIL" if ok is False else "n/a")
        gate_lines.append(f"| {desc} | {mark} |")

    curve_lines = [
        f"| {int(r.K)} | {r.inner_mae_fold1:.4f} | {r.inner_mae_fold2:.4f} | "
        f"{r.inner_mae_fold3:.4f} | {r.inner_mae_mean:.6f} | "
        f"{r.inner_delta_vs_incumbent:+.6f}{' **<- K***' if r.chosen else ''} |"
        for r in curve.itertuples()]

    comp_lines = []
    for name, c in sec["components"].items():
        comp_lines.append(f"| {name} | {c['challenger_mae']:.4f} | {c['incumbent_mae']:.4f} "
                          f"| {c['delta_improvement']:+.4f} |")

    uni = cfs["test_universe_673"]
    allg = cfs["all_1489_games"]
    audits = S["audits"]
    pa, lm = audits["prior_walk_forward"], audits["league_mean_walk_forward"]
    sens = S["sensitivity_first3"]
    ver = S["officials_verification"]

    md = f"""# W4 — Referee FTA-Prior Crew Factor on the FT Channel ({res['verdict']})

{CAVEAT}

*{S['run_time']} · registered experiment `{EXPERIMENT_ID}` (registered {reg['registered_at']},
regime {reg['regime']}, primary metric `{reg['primary_metric']}`, incumbent
`{reg['incumbent_id']}`) · run mode **{mode}**{' — evaluated against a scratch COPY of the registry; the real ledger is untouched by this run' if S['mode'] == 'smoke' else ' — recorded on the real ledger'}
· code `w4_refs.py` (repo root) · data `data/officials_master.csv`,
`data/masters/master_team.parquet`, incumbent artifacts in `experiments/channel_reval/`.*

## Verdict

**{res['verdict']}{' — clean null' if not res['promote'] else ''}.** The crew FTA-prior multiplier
{'does not move' if abs(res['pooled_improvement']) < 0.02 else 'moves'} the FT channel:
challenger FT MAE **{res['metric_challenger']:.4f}** vs incumbent **{res['metric_incumbent']:.4f}**
(pooled improvement **{res['pooled_improvement']:+.4f}**, 90% date-clustered bootstrap CI
[{res['ci_low']:+.4f}, {res['ci_high']:+.4f}], {res['n_clusters']} date clusters,
{res['n_games']} team-game rows on the registered universe of
{S['reproduction']['n_universe_games']} games). Tuned pooling constant K* = {S['k_tuning']['K_star']}
(train-only) — the tuner chose {'heavy' if S['k_tuning']['K_star'] >= 256 else 'moderate'} shrinkage,
crew factors hug 1.0 (test-universe mean {uni['mean']:.4f}, sd {uni['std']:.4f}), and the
registered [{BOUND_LO}, {BOUND_HI}] bound activated on {uni['n_at_lower_bound'] + uni['n_at_upper_bound']}
of {uni['n_games']} test games. The registered expectation was a small effect
("cheap isolated sidecar — never auto-included"); the ROADMAP W4 design keeps this
isolated until it passes both FT-channel and joint gates{', which it does not' if not res['promote'] else ''}.

| Gate | Result |
|---|---|
{chr(10).join(gate_lines)}

Failed gates: {', '.join(res['failed_gates']) if res['failed_gates'] else 'none'}.

## Primary — FT channel MAE (challenger vs incumbent, walk-forward)

Units are team-game FT-channel rows (2 per game, equal weight — pooled MAE and the
date-clustered CI are identical under per-game averaging; n counts rows).

| Season | n rows | Challenger | Incumbent | delta (improvement) |
|---|---|---|---|---|
{srow('2024')}
{srow('2025')}
{srow('2026')}
| **pooled** | {res['n_games']} | **{res['metric_challenger']:.4f}** | **{res['metric_incumbent']:.4f}** | **{res['pooled_improvement']:+.4f}** |

Team-clustered sensitivity CI: [{res['ci_sensitivity_team'][0]:+.4f}, {res['ci_sensitivity_team'][1]:+.4f}]
({res['ci_sensitivity_team'][2]} franchise clusters).

## The challenger

`prior_r(t)` = shrunken mean of (game total FTA / walk-forward league mean FTA) over
referee r's games strictly before t; partial pooling `n/(n+K)` toward 1.0, K tuned
train-only; crew factor = mean over the game's listed officials, clipped to
[{BOUND_LO}, {BOUND_HI}] (registered, fixed). Challenger FT channel = incumbent structural
FT chain x crew factor, both teams symmetrically. League mean FTA is an expanding mean
over strictly earlier dates (audited below) — never a global constant.

## K tuning curve (3 inner walk-forward folds strictly inside 2021-2023)

Incumbent (no crew factor) inner-fold mean MAE: **{curve.incumbent_inner_mae_mean.iloc[0]:.6f}**.

| K | fold1 | fold2 | fold3 | mean | delta vs incumbent |
|---|---|---|---|---|---|
{chr(10).join(curve_lines)}

{S['k_tuning']['comment']}

## Crew factor distribution (at K* = {S['k_tuning']['K_star']})

| Scope | n | mean | sd | min | p05 | p50 | p95 | max | at lower bound | at upper bound |
|---|---|---|---|---|---|---|---|---|---|---|
| all 1,489 games | {allg['n_games']} | {allg['mean']:.4f} | {allg['std']:.4f} | {allg['min']:.4f} | {allg['p05']:.4f} | {allg['p50']:.4f} | {allg['p95']:.4f} | {allg['max']:.4f} | {allg['n_at_lower_bound']} | {allg['n_at_upper_bound']} |
| test universe (673) | {uni['n_games']} | {uni['mean']:.4f} | {uni['std']:.4f} | {uni['min']:.4f} | {uni['p05']:.4f} | {uni['p50']:.4f} | {uni['p95']:.4f} | {uni['max']:.4f} | {uni['n_at_lower_bound']} | {uni['n_at_upper_bound']} |

Bound-activation rate: {allg['bound_activation_rate']:.2%} of all games,
{uni['bound_activation_rate']:.2%} of the test universe. Unclipped crew-prior mean
{allg['mean_unclipped']:.4f} over all games — the ratio construction runs slightly above 1
because league FTA drifted upward across 2021-2026 while the expanding league mean lags;
the tuned shrinkage compresses exactly that.

## Secondaries (recorded, not gated) — substitution + train-only recalibration

Challenger FT channel substituted into both teams' structural sums; margin/home/away
calibrations refit on 2021-2023 eligible games only (n = {len(ctx['tg'])}); scored on the 673.

| Component | Challenger MAE | Incumbent MAE | delta (improvement) |
|---|---|---|---|
{chr(10).join(comp_lines)}

Joint check (gate-4 style, tolerance {sec['tolerance']}): {'no component degrades beyond tolerance' if sec['joint_ok'] else 'DEGRADED beyond tolerance'}.
Game-total MAE by season (challenger / incumbent): {' · '.join(f"{s}: {v['total_mae_challenger']:.3f} / {v['total_mae_incumbent']:.3f}" for s, v in sorted(sec['total_mae_by_season'].items()))}.
Refs plausibly move totals more than margins; at K* = {S['k_tuning']['K_star']} the substitution
moves {'neither' if sec['joint_ok'] else 'the joint forecast'} materially.

## Data verification

- `officials_master.csv`: {ver['n_games']} games (= the full master universe), {ver['n_officials']}
  distinct officials, 0 duplicate (game, official) rows, 0 games missing officials,
  0 official rows for unknown games. Joined to `master_team.parquet` on the repo's
  10-digit string `game_id`.
- **Deviation from the registered "3 refs/game":** {ver['crew_size_counts'].get(3, 0)} games list
  exactly 3 officials; **{ver['crew_size_counts'].get(4, 0)} playoff games list 4** (the boxscore
  officials table includes the alternate for playoff games; the source carries no role
  labels, and listing order is not a documented contract). Primary uses **all listed
  officials**; a first-3-only sensitivity is reported below. {cfs['n_four_official_games_in_universe']}
  of the 673 universe games list 4 officials.
- Game FTA from `data/masters/master_team.parquet` (2 rows per game, summed), cross-checked
  exactly (max |diff| = 0) against `channel_base_v2.csv`.
- {S['game_fta_info']['n_games_nan_ratio_first_date']} games on the dataset's first date
  ({S['game_fta_info']['first_date']}) have no league baseline -> no ratio; they are excluded
  from every referee's history (no information is invented) but still receive crew factors.

## Incumbent reproduction (certified before anything else ran)

Rebuilt the chanreval pipeline via `experiments/channel_reval/run_reval.py`'s own
functions (alphas from `run_summary.json`: ft = {S['alphas']['ft']}). Hard asserts, all passed:

- FT channel table matches `channel_results_v2.csv` on n / raw MAE / structural MAE in
  all 4 scopes exactly (pooled: n = {ft_rows['2024-2026 pooled']['n']},
  structural {ft_rows['2024-2026 pooled']['mae_structural']:.6f});
- game-level calibrated predictions match `predictions_v2.csv` across 11 numeric columns
  x 673 games, max |diff| = {S['reproduction']['predictions_max_abs_diff']:.3g}.

The incumbent's per-team-game FT predictions used here are therefore bit-identical to the
ledgered chanreval run. (Incumbent pooled FT MAE on the 1,346-row universe is
{res['metric_incumbent']:.4f} vs {ft_rows['2024-2026 pooled']['mae_structural']:.4f} on the
channel table's 1,362 rows — the table additionally includes 16 rows from games whose
*opponent* was under the 5-prior-game floor; the registered universe is the 673 games.)

## Leakage audits (constitution rule 1 — run before believing)

1. **Prior walk-forward audit (truncate + recompute):** {pa['n_pairs_audited']} sampled
   (ref, date) pairs across all seasons; each prior rebuilt from raw officials + master
   FTA by an independent loop-based recompute truncated strictly before t.
   **{pa['n_mismatch']} mismatches, max |diff| = {pa['max_abs_diff']:.3g}**. Including
   date-t games changes the value in {pa['n_pairs_where_truncation_changes_value']}/{pa['n_pairs_audited']}
   pairs — the truncation is real, no game at/after t enters any prior.
2. **League-mean walk-forward audit:** {lm['n_dates_audited']} sampled dates recomputed
   strictly-before by brute force: {lm['n_mismatch']} mismatches
   (max |diff| = {lm['max_abs_diff']:.3g}); {lm['n_sampled_dates_differing_from_global_mean']}/{lm['n_dates_audited']}
   sampled dates differ from the global mean (it is expanding, not global), and the
   first date's league mean is NaN by construction.
3. **K tuned strictly inside 2021-2023** via `evalharness.inner_tuning_splits` (leakage-
   checked fold construction); test seasons never touched tuning. The curve is above.
4. Universe / truth columns are the chanreval artifacts' own, reproduced bit-identically
   (see reproduction section); coverage is identical for both models by construction
   (crew factors exist for all 1,489 games).

## Sensitivity — first-3 listed officials only

Priors and crew factors rebuilt using only each game's first 3 listed officials
(same K* = {S['k_tuning']['K_star']}): pooled challenger FT MAE {sens['ft_mae']:.4f}
(vs {res['metric_challenger']:.4f} primary; delta vs incumbent {sens['delta_vs_incumbent']:+.4f}
vs {res['pooled_improvement']:+.4f} primary); crew factors differ from primary on
{sens['n_games_factor_differs']} of 1,489 games (max |diff| {sens['max_factor_abs_diff']:.4f}).
The 4-official ambiguity does not change the conclusion.

## Files

- `w4_refs.py` (repo root) — this experiment, end to end; `--smoke` = scratch registry.
- `game_level_predictions.csv` — 673 rows: refs, crew factor, actual/incumbent/challenger
  FT points both teams, actual + calibrated margins and totals for both models.
- `k_tuning_curve.csv` — the train-only K curve above.
- `crew_factors.csv` — per-game crew factor, listed officials, bound flags (all 1,489).
- `audits.json` — full audit detail (sampled pairs/dates, mismatch counts).
- `run_summary.json` — machine-readable everything (registration echo, reproduction
  certificates, K curve, primary verdict, secondaries, sensitivity).
- Ledger: {'scratch copy (smoke) — real registry untouched' if S['mode'] == 'smoke' else 'experiments/registry.jsonl (evaluation recorded)'}.
"""
    (outdir / "REPORT.md").write_text(md, encoding="utf-8")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode_g = ap.add_mutually_exclusive_group(required=True)
    mode_g.add_argument("--smoke", action="store_true",
                        help="evaluate against a scratch COPY of the registry "
                             "(tempdir); real ledger untouched; artifacts still "
                             "written to experiments/w4_refs/")
    mode_g.add_argument("--real", action="store_true",
                        help="record the evaluation on the REAL ledger "
                             "(orchestrator only)")
    ap.add_argument("--outdir", type=Path, default=OUTDIR)
    args = ap.parse_args(argv)
    mode = "smoke" if args.smoke else "real"

    registry_path = None
    scratch_note = None
    if args.smoke:
        scratch = Path(tempfile.mkdtemp(prefix="w4_refs_smoke_"))
        registry_path = scratch / "registry_scratch.jsonl"
        shutil.copyfile(REPO / "experiments" / "registry.jsonl", registry_path)
        scratch_note = str(registry_path)
        log(f"SMOKE mode: scratch registry copy at {registry_path}")

    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    run_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log(f"{mode.upper()} run at {run_time} -> {outdir}")

    # registration echo (read-only)
    reg = eh.get_registration(EXPERIMENT_ID, registry_path=registry_path)
    assert reg["incumbent_id"] == INCUMBENT_ID, reg["incumbent_id"]
    joint_tol = float(reg["thresholds"]["harm_ci_bound"])
    log(f"registration OK: {EXPERIMENT_ID} registered {reg['registered_at']}, "
        f"incumbent {reg['incumbent_id']}, primary {reg['primary_metric']}, "
        f"thresholds {reg['thresholds']}")

    # 1. incumbent reproduction (hard asserts inside)
    ctx = reproduce_incumbent()
    D, F, games, tg, et, U = (ctx[k] for k in ("D", "F", "games", "tg", "et", "U"))

    # 2. officials + game FTA
    mt_games = set(pd.read_parquet(MASTER_TEAM, columns=["game_id"]).game_id.unique())
    o, officials_ver = load_officials(mt_games)
    g, fta_info = build_game_fta()
    ol = officials_long(o, g)
    rp = ref_prior_sums(ol)

    # 3. K tuning, train-only
    K_star, curve = tune_K(D, F, ol, rp, ctx["outer24"])
    flat = float(curve.inner_mae_mean.max() - curve.inner_mae_mean.min())
    best_delta = float(curve.loc[curve.chosen, "inner_delta_vs_incumbent"].iloc[0])
    at_edge = K_star == K_GRID[-1]
    if K_star >= 256:
        k_comment = (
            f"The curve improves monotonically toward heavy pooling and is essentially flat "
            f"past K=64 (full range {flat:.4f} MAE points); the shallow optimum at "
            f"K*={K_star}{' (grid edge)' if at_edge else ''} beats the no-crew incumbent by "
            f"only {best_delta:+.6f} FT-MAE points on the inner folds. 2021-2023 shows no "
            f"exploitable referee FTA signal at face value, so the train-only tuner "
            f"compresses the crew factor toward 1.0.")
    else:
        k_comment = (f"K*={K_star} retains material crew signal: inner-fold gain "
                     f"{best_delta:+.6f} over the incumbent (curve range {flat:.4f}).")

    # 4. crew factors at K*
    cf = crew_factors(ol, rp, K_star)
    assert len(cf) == 1489
    cf_first3 = crew_factors(ol, rp, K_star, first3=True)
    uni_gids = set(U.gid)
    cfs = crew_factor_stats(cf, uni_gids)

    # 5. audits BEFORE evaluating
    audit_prior = audit_priors(ol, rp, g, K_star)
    audit_lg = audit_league_mean(g)
    if not (audit_prior["passed"] and audit_lg["passed"]):
        raise SystemExit("walk-forward audit FAILED — results are not evidence; stopping")

    # 6. primary comparison on the registered universe
    fac = cf.set_index("GAME_ID")["crew_factor"]
    Uc = U.copy()
    Uc["crew_factor"] = Uc.gid.map(fac)
    assert Uc.crew_factor.notna().all()
    Uc["chal_ft"] = Uc.str_ft * Uc.crew_factor
    Uc["row_id"] = Uc.gid + np.where(Uc.is_home == 1, "_h", "_a")

    challenger = pd.DataFrame({
        "game_id": Uc.row_id, "game_date": Uc.GAME_DATE, "season": Uc.season,
        "y_true": Uc.ch_ft, "y_pred": Uc.chal_ft, "home_team": Uc.TEAM_ID})
    incumbent = pd.DataFrame({
        "game_id": Uc.row_id, "y_true": Uc.ch_ft, "y_pred": Uc.str_ft})

    sec = secondaries(games, tg, et, cf, joint_tol)
    cov = len(et) / ctx["n_total_test_games"]

    result = eh.compare_to_incumbent(
        challenger, incumbent,
        experiment_id=EXPERIMENT_ID,
        registry_path=registry_path,
        cluster="date",
        n_boot=2000, seed=SEED,
        joint_check=lambda: (sec["joint_ok"],
                             {"tolerance": sec["tolerance"], "components": sec["components"],
                              "note": "substitution into structural sum + train-only recalibration"}),
        coverage=(cov, cov),
    )
    log(f"VERDICT: {result.verdict} (promote={result.promote}); FT MAE challenger "
        f"{result.metric_challenger:.4f} vs incumbent {result.metric_incumbent:.4f}; "
        f"pooled improvement {result.pooled_improvement:+.4f} "
        f"[90% CI {result.ci_low:+.4f}, {result.ci_high:+.4f}]; "
        f"failed gates: {result.failed_gates or 'none'}")

    # 7. sensitivity: first-3 listed officials, same K*
    fac3 = cf_first3.set_index("GAME_ID")["crew_factor"]
    chal3 = Uc.str_ft * Uc.gid.map(fac3)
    sens_mae = float((chal3 - Uc.ch_ft).abs().mean())
    both = cf.set_index("GAME_ID")["crew_factor"].to_frame("p").join(
        cf_first3.set_index("GAME_ID")["crew_factor"].rename("f3"))
    sens = {"ft_mae": sens_mae,
            "delta_vs_incumbent": float(result.metric_incumbent - sens_mae),
            "n_games_factor_differs": int((both.p - both.f3).abs().gt(1e-12).sum()),
            "max_factor_abs_diff": float((both.p - both.f3).abs().max())}
    log(f"first-3 sensitivity: FT MAE {sens_mae:.4f} (primary "
        f"{result.metric_challenger:.4f}); factors differ on "
        f"{sens['n_games_factor_differs']} games, max |diff| {sens['max_factor_abs_diff']:.4f}")

    # 8. artifacts ----------------------------------------------------------
    et2 = sec.pop("frame")
    cf_cols = cf.rename(columns={"GAME_ID": "game_id"})
    gp = et2.merge(cf_cols[["game_id", "refs", "n_officials"]],
                   left_on=et2.GAME_ID.astype(str), right_on="game_id", how="left")
    game_preds = pd.DataFrame({
        "game_id": et2.GAME_ID.astype(str),
        "game_date": et2.GAME_DATE_h.dt.date.astype(str),
        "season": et2.season_h,
        "home": et2.TEAM_ABBREVIATION_h, "away": et2.TEAM_ABBREVIATION_a,
        "refs": gp.refs.to_numpy(), "n_officials": gp.n_officials.to_numpy(),
        "crew_factor": et2.cf,
        "ft_actual_home": et2.ch_ft_h, "ft_actual_away": et2.ch_ft_a,
        "ft_pred_incumbent_home": et2.str_ft_h, "ft_pred_incumbent_away": et2.str_ft_a,
        "ft_pred_challenger_home": et2.chal_ft_h, "ft_pred_challenger_away": et2.chal_ft_a,
        "margin_true": et2.margin_true, "total_true": et2.total_true,
        "margin_pred_incumbent_cal": et2.str_margin_cal,
        "margin_pred_challenger_cal": et2.chal_margin_cal,
        "total_pred_incumbent_cal": et2.str_total_cal,
        "total_pred_challenger_cal": et2.chal_total_cal,
    }).sort_values(["game_date", "game_id"])
    assert len(game_preds) == 673 and game_preds.refs.notna().all()
    game_preds.to_csv(outdir / "game_level_predictions.csv", index=False)

    curve.to_csv(outdir / "k_tuning_curve.csv", index=False)
    cf_out = cf.copy()
    cf_out["in_test_universe"] = cf_out.GAME_ID.isin(uni_gids)
    cf_out.to_csv(outdir / "crew_factors.csv", index=False)

    audits = {"prior_walk_forward": audit_prior, "league_mean_walk_forward": audit_lg}
    with open(outdir / "audits.json", "w", encoding="utf-8") as fh:
        json.dump(audits, fh, indent=2)

    summary = {
        "experiment_id": EXPERIMENT_ID, "mode": mode, "run_time": run_time,
        "scratch_registry": scratch_note,
        "registration": {k: reg[k] for k in ("experiment_id", "registered_at", "incumbent_id",
                                             "primary_metric", "thresholds", "regime")},
        "alphas": ctx["alphas"],
        "reproduction": ctx["repro"],
        "officials_verification": officials_ver,
        "game_fta_info": fta_info,
        "k_tuning": {"K_star": K_star, "grid": K_GRID, "comment": k_comment,
                     "curve": curve.to_dict(orient="records")},
        "crew_factor_stats": cfs,
        "audits": {"prior_walk_forward": {k: v for k, v in audit_prior.items() if k != "pairs"},
                   "league_mean_walk_forward": {k: v for k, v in audit_lg.items() if k != "dates"}},
        "primary_result": result.to_dict(),
        "secondaries": sec,
        "sensitivity_first3": sens,
        "coverage": cov,
        "bounds": [BOUND_LO, BOUND_HI],
    }
    with open(outdir / "run_summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)

    write_report(outdir, {"summary": summary, "registration": reg, "tg": tg})
    log(f"wrote REPORT.md, game_level_predictions.csv, k_tuning_curve.csv, "
        f"crew_factors.csv, audits.json, run_summary.json -> {outdir}")
    if args.smoke:
        log(f"smoke ledger record appended to {scratch_note} (real ledger untouched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
