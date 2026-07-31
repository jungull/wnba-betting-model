"""joint_differential.py — R2 joint differential margin system (regime A).

Preregistered experiment: ``joint_differential_v1`` (experiments/registry.jsonl,
registered 2026-07-31T14:59:26Z, regime A, primary metric margin_mae, incumbent
``chanreval_structural_calibrated``). This is the R2 program from
experiments/coherence_study/REPORT.md: margins are affine in the channel
DIFFERENTIALS only (margin err var = 4*var(u)); recombining existing predictions
is dead (in-sample ceiling +0.087); only new differential information can move
the margin. This experiment predicts each channel's home-minus-away differential
directly, with differential features plus the minutes-EWMA-weighted RAPM lineup
differential as the new information.

Design (the registration's features_desc is binding):

  Per channel ch in {ft, 3pt, paint, np2} and game g:
    target  = true channel differential  (ch_actual_h - ch_actual_a)
    features (all walk-forward, all home-minus-away differentials):
      d_own_ch    own-tendency trend differential      (chain ingredient 1)
      d_allow_ch  opponent-allowed trend differential  (chain ingredient 2)
      d_conv_ch   conversion trend differential        (ft/3pt only: the paint
                  and np2 chains have no conversion ingredient in
                  channel_base_v2 — differentials come from the SAME shifted
                  inputs the incumbent chains use, nothing invented)
      d_rest      rest-day differential (master_team dates; strictly-prior
                  game dates + own tip date, i.e. schedule information)
      d_rapm      RAPM lineup differential: minutes-EWMA-weighted mean of
                  rapm_v0 net_100 over each side's played-history roster
                  (weights = shifted minutes EWMA, alpha 0.30 — the frozen
                  minutes-system constant, the oracle bracket's w1 pattern —
                  over strictly-prior played games; roster = players whose
                  most recent prior played game this season was for the team;
                  unrated players at the committed p25 replacement -0.890).
                  Regime-A clean: no availability system, no dressed-roster
                  dependence.
    Model: ridge per channel (house pattern: standardized features,
    unpenalized intercept), fit on the 610 eligible 2021-2023 train games only;
    lambda per channel from evalharness.inner_tuning_splits (3 walk-forward
    folds strictly inside 2021-2023), frozen for 2024/2025/2026.
    margin_uncal = sum of the four predicted channel differentials;
    margin_cal   = house train-years-only linear calibration (fit on the SAME
    610 train games the incumbent's calibration used — run_reval protocol).

  The per-side score and total heads are NOT touched: this model emits a margin
  only (gate 4 asserts no side/total columns exist).

Audits (all must pass before results are believed):
  0. incumbent reproduction: rebuilt chains + committed calibration reproduce
     predictions_v2.csv per game (<=1e-9, expected ~1e-14 scale) and the
     ledgered pooled 10.0860 within 1e-3;
  1. shift audit on EVERY differential feature: truncate-and-recompute on >= 15
     sampled test games (all rows at/after the game's date blanked/dropped;
     features on the game must be identical);
  2. RAPM-diff walk-forward audit: independent hand-loop recompute of sampled
     team strengths from strictly-prior played games only;
  3. permutation probe: train channel targets shuffled within season, refit at
     frozen lambdas -> the test margin must collapse to the no-skill level.

Secondary (recorded to files, not gated): per-channel differential MAE vs the
incumbent's implied channel differentials; the coherence-study section-3b
own-variance vs cross-covariance attribution; the preregistered ablation
WITHOUT d_rapm (does the new information or the reframing carry the gain?);
error-variance c/u split vs the coherence study's var(u).

Run:  python joint_differential.py --real     # orchestrator only (records on the ledger)
      python joint_differential.py --smoke [--outdir DIR]   # scratch registry copy
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import evalharness as eh  # noqa: E402

# --- the incumbent's committed machinery, imported from the registered script -
_spec = importlib.util.spec_from_file_location(
    "run_reval", REPO / "experiments" / "channel_reval" / "run_reval.py")
rr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr)

EXPERIMENT_ID = "joint_differential_v1"
CHANNELS = list(rr.CHANNELS)                      # ["ft", "3pt", "paint", "np2"]
TRAIN_YEARS = list(rr.TRAIN_YEARS)                # [2021, 2022, 2023]
TEST_YEARS = list(rr.TEST_YEARS)                  # [2024, 2025, 2026]

CHAN_SUMMARY = REPO / "experiments" / "channel_reval" / "run_summary.json"
CHAN_PRED = REPO / "experiments" / "channel_reval" / "predictions_v2.csv"
W2_PRED = REPO / "experiments" / "w2_integration" / "game_level_predictions.csv"
COHERENCE_SUMMARY = REPO / "experiments" / "coherence_study" / "analysis_summary.json"
MASTER_PLAYER = REPO / "data" / "masters" / "master_player.parquet"
MASTER_TEAM = REPO / "data" / "masters" / "master_team.parquet"
RAPM = REPO / "data" / "rapm" / "rapm_v0.csv"
DEFAULT_OUTDIR = REPO / "experiments" / "joint_differential"

ALPHAS_COMMITTED = {"ft": 0.10, "3pt": 0.05, "paint": 0.05, "np2": 0.05}
EWMA_ALPHA_MIN = 0.30            # frozen minutes-system constant (mts EWMA_ALPHA)
REPLACEMENT_COMMITTED = -0.890   # committed p25 of rapm_v0 net_100
INC_POOLED_LEDGER = 10.0860      # ledgered incumbent pooled margin MAE (673 games)
N_TRAIN_LEDGER = 610             # ledgered incumbent calibration train games

LAMBDAS = [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0]
AUDIT_SEED = 20260731
SHIFT_AUDIT_PER_SEASON = 6       # 18 games total (>= 15 required)
RAPM_AUDIT_GAMES = 10            # x2 sides = 20 independent recomputes
PERM_K = 5
PERM_NEAR_NAIVE_TOL = 0.35       # permuted MAE must sit within this of naive
PERM_MIN_GAP = 0.50              # ... and at least this worse than the real model
REPRO_TOL_PER_GAME = 1e-9
ATOL = 1e-9

# chain ingredients per channel: (own tendency, opponent allowed, conversion)
ING = {
    "ft":    ("fta_t",     "opp_pf_trend",   "ftpct_t"),
    "3pt":   ("fg3a_t",    "opp_fg3a_allow", "fg3pct_t"),
    "paint": ("raw_paint", "opp_paint_allow", None),
    "np2":   ("raw_np2",   "opp_np2_allow",   None),
}
FEATSETS = {
    ch: [f"d_own_{ch}", f"d_allow_{ch}"]
        + ([f"d_conv_{ch}"] if ING[ch][2] else [])
        + ["d_rest", "d_rapm"]
    for ch in CHANNELS
}
FEATSETS_ABL = {ch: [f for f in FEATSETS[ch] if f != "d_rapm"] for ch in CHANNELS}
ALL_DIFF_FEATURES = sorted({f for fs in FEATSETS.values() for f in fs})


# ---------------------------------------------------------------------------
# house ridge pattern (minutes_twostage conventions, hand-rolled)
# ---------------------------------------------------------------------------

class Standardizer:
    def __init__(self, X: pd.DataFrame):
        self.mean = X.mean(axis=0)
        self.std = X.std(axis=0, ddof=0)
        self.keep = self.std[self.std > 1e-12].index.tolist()
        self.dropped = [c for c in X.columns if c not in self.keep]

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        Z = (X[self.keep] - self.mean[self.keep]) / self.std[self.keep]
        return Z.to_numpy(dtype=float)


def ridge_fit(Z: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
    n, p = Z.shape
    X1 = np.hstack([np.ones((n, 1)), Z])
    pen = lam * np.eye(p + 1)
    pen[0, 0] = 0.0
    return np.linalg.solve(X1.T @ X1 + pen, X1.T @ y)


def ridge_predict(Z: np.ndarray, beta: np.ndarray) -> np.ndarray:
    return np.hstack([np.ones((Z.shape[0], 1)), Z]) @ beta


def mae(err) -> float:
    return float(np.abs(np.asarray(err, dtype=float)).mean())


def fmt_table(df: pd.DataFrame, floatfmt: str = "{:.4f}") -> str:
    d = df.copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: floatfmt.format(v) if pd.notna(v) else "")
    header = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "|" + "|".join("---" for _ in d.columns) + "|"
    body = "\n".join("| " + " | ".join(map(str, row)) + " |"
                     for row in d.itertuples(index=False))
    return "\n".join([header, sep, body])


# ---------------------------------------------------------------------------
# rest days (master_team dates, walk-forward: strictly-prior dates + own date)
# ---------------------------------------------------------------------------

def team_rest(mt: pd.DataFrame) -> pd.DataFrame:
    """Per (game_id, team_id): days since the team's previous game this season
    (any season_type — RS -> playoffs rest is real rest). NaN on each team's
    season opener; the eligibility rule (>= 5 prior games) keeps openers out of
    every fitted/evaluated row, so nothing is invented for them."""
    t = mt[["game_id", "team_id", "season", "game_date"]].copy()
    t["game_date"] = pd.to_datetime(t["game_date"])
    t["team_id"] = t["team_id"].astype("int64")
    t = t.sort_values(["team_id", "season", "game_date", "game_id"],
                      kind="mergesort").reset_index(drop=True)
    t["rest_days"] = t.groupby(["team_id", "season"], sort=False)["game_date"] \
        .diff().dt.days.astype(float)
    return t[["game_id", "team_id", "rest_days"]]


# ---------------------------------------------------------------------------
# RAPM lineup differential (regime-A clean: played history only)
# ---------------------------------------------------------------------------

def load_played_minutes() -> pd.DataFrame:
    mp = pd.read_parquet(MASTER_PLAYER)
    mp = mp[mp["minutes"].notna() & (mp["minutes"] > 0)
            & mp["player_id"].notna() & mp["team_id"].notna()].copy()
    mp["game_date"] = pd.to_datetime(mp["game_date"])
    mp["player_id"] = mp["player_id"].astype("int64")
    mp["team_id"] = mp["team_id"].astype("int64")
    mp["minutes"] = mp["minutes"].astype(float)
    P = mp[["player_id", "season", "game_id", "game_date", "team_id", "minutes"]] \
        .sort_values(["player_id", "season", "game_date", "game_id"],
                     kind="mergesort").reset_index(drop=True)
    # POST-value minutes EWMA per (player, season) — the mts/oracle-w1 pattern;
    # as-of use below is strictly-prior via allow_exact_matches=False.
    P["post_ewma"] = P.groupby(["player_id", "season"], sort=False)["minutes"] \
        .transform(lambda s: s.ewm(alpha=EWMA_ALPHA_MIN, adjust=True).mean())
    return P


def rapm_strengths(P: pd.DataFrame, queries: pd.DataFrame,
                   val_map: dict, replacement: float) -> pd.DataFrame:
    """Team lineup values for every (season, game_date, team_id) reachable from
    ``queries`` [season, game_date]: for each player the last played row
    STRICTLY BEFORE the query date (merge_asof, allow_exact_matches=False);
    roster membership = that row's team; weight = its post-EWMA minutes (the
    shifted, prior-games-only value); value = rapm_v0 net_100 or replacement."""
    players = P[["season", "player_id"]].drop_duplicates()
    Q = queries.drop_duplicates().merge(players, on="season", how="inner")
    Q = Q.sort_values("game_date", kind="mergesort").reset_index(drop=True)
    Pp = P[["season", "player_id", "game_date", "team_id", "post_ewma"]] \
        .sort_values("game_date", kind="mergesort").reset_index(drop=True)
    A = pd.merge_asof(Q, Pp, on="game_date", by=["season", "player_id"],
                      direction="backward", allow_exact_matches=False)
    A = A[A["post_ewma"].notna()].copy()
    A["w"] = A["post_ewma"].clip(lower=0)
    vals = A["player_id"].map(val_map)
    A["rated"] = vals.notna()
    A["val"] = vals.fillna(replacement)
    A["wv"] = A["w"] * A["val"]
    A["w_repl"] = A["w"] * (~A["rated"]).astype(float)
    G = A.groupby(["season", "game_date", "team_id"], as_index=False).agg(
        wsum=("w", "sum"), wvsum=("wv", "sum"),
        n_roster=("w", "size"), w_repl=("w_repl", "sum"))
    G["strength"] = np.where(G["wsum"] > 0, G["wvsum"] / G["wsum"], np.nan)
    G["repl_wshare"] = np.where(G["wsum"] > 0, G["w_repl"] / G["wsum"], np.nan)
    return G[["season", "game_date", "team_id", "strength", "n_roster", "repl_wshare"]]


def ewma_manual(x: np.ndarray, alpha: float) -> float:
    w = (1.0 - alpha) ** np.arange(len(x) - 1, -1, -1)
    return float((w * x).sum() / w.sum())


def manual_strength(P: pd.DataFrame, season: int, date: pd.Timestamp,
                    team_id: int, val_map: dict, replacement: float) -> tuple:
    """Independent hand-loop recompute from STRICTLY-PRIOR played games only."""
    sub = P[(P["season"] == season) & (P["game_date"] < date)]
    last = sub.sort_values(["game_date", "game_id"], kind="mergesort") \
        .groupby("player_id").tail(1)
    roster = last.loc[last["team_id"] == team_id, "player_id"].tolist()
    wsum = wvsum = 0.0
    for p in roster:
        x = sub.loc[sub["player_id"] == p].sort_values(
            ["game_date", "game_id"], kind="mergesort")["minutes"].to_numpy(float)
        w = max(ewma_manual(x, EWMA_ALPHA_MIN), 0.0)
        v = val_map.get(p, replacement)
        wsum += w
        wvsum += w * v
    return (wvsum / wsum if wsum > 0 else np.nan), len(roster)


# ---------------------------------------------------------------------------
# game-level frame: incumbent rebuild + differential features
# ---------------------------------------------------------------------------

def trend_diffs_from_F(F: pd.DataFrame, gid) -> dict:
    rows = F[F["GAME_ID"] == gid]
    h = rows[rows["is_home"] == 1].iloc[0]
    a = rows[rows["is_home"] == 0].iloc[0]
    out = {}
    for ch, (own, allow, conv) in ING.items():
        out[f"d_own_{ch}"] = h[own] - a[own]
        out[f"d_allow_{ch}"] = h[allow] - a[allow]
        if conv:
            out[f"d_conv_{ch}"] = h[conv] - a[conv]
    return out


def build_game_frame(D: pd.DataFrame, F: pd.DataFrame, games: pd.DataFrame,
                     rest: pd.DataFrame, S: pd.DataFrame) -> pd.DataFrame:
    """games (run_reval.make_games output) + chain-ingredient differentials +
    rest differential + RAPM lineup differential. One row per game."""
    ing_cols = sorted({c for tpl in ING.values() for c in tpl if c})
    keep = ["GAME_ID"] + ing_cols
    h = F.loc[F["is_home"] == 1, keep].add_suffix("_h") \
        .rename(columns={"GAME_ID_h": "GAME_ID"})
    a = F.loc[F["is_home"] == 0, keep].add_suffix("_a") \
        .rename(columns={"GAME_ID_a": "GAME_ID"})
    g = games.merge(h, on="GAME_ID", validate="one_to_one") \
             .merge(a, on="GAME_ID", validate="one_to_one")

    for ch, (own, allow, conv) in ING.items():
        g[f"d_own_{ch}"] = g[f"{own}_h"] - g[f"{own}_a"]
        g[f"d_allow_{ch}"] = g[f"{allow}_h"] - g[f"{allow}_a"]
        if conv:
            g[f"d_conv_{ch}"] = g[f"{conv}_h"] - g[f"{conv}_a"]
        # targets + incumbent-implied channel differentials
        act = rr.CH_ACTUAL[ch]
        g[f"t_d_{ch}"] = g[f"{act}_h"] - g[f"{act}_a"]
        g[f"inc_d_{ch}"] = g[f"str_{ch}_h"] - g[f"str_{ch}_a"]

    # rest differential (join by game+team)
    g["GID_STR"] = g["GAME_ID"].astype(str)
    for side, tid in (("h", "TEAM_ID_h"), ("a", "TEAM_ID_a")):
        r = rest.rename(columns={"game_id": "GID_STR", "team_id": tid,
                                 "rest_days": f"rest_{side}"})
        g = g.merge(r, on=["GID_STR", tid], how="left", validate="one_to_one")
    g["d_rest"] = g["rest_h"] - g["rest_a"]

    # RAPM lineup differential (join by season+date+team)
    g["GDATE"] = pd.to_datetime(g["GAME_DATE_h"]).dt.normalize()
    for side, tid in (("h", "TEAM_ID_h"), ("a", "TEAM_ID_a")):
        s = S.rename(columns={"season": "season_h", "game_date": "GDATE",
                              "team_id": tid, "strength": f"rapm_{side}",
                              "n_roster": f"roster_n_{side}",
                              "repl_wshare": f"repl_wshare_{side}"})
        g = g.merge(s, on=["season_h", "GDATE", tid], how="left",
                    validate="one_to_one")
    g["d_rapm"] = g["rapm_h"] - g["rapm_a"]

    # box identity: the four true channel differentials sum to the margin
    ok = g[[f"t_d_{c}" for c in CHANNELS]].notna().all(axis=1)
    ident = (g.loc[ok, [f"t_d_{c}" for c in CHANNELS]].sum(axis=1)
             - g.loc[ok, "margin_true"]).abs().max()
    assert ident <= 1e-9, f"channel differentials do not sum to margin: {ident}"
    return g.reset_index(drop=True)


# ---------------------------------------------------------------------------
# tuning + fitting
# ---------------------------------------------------------------------------

def tune_lambdas(g2: pd.DataFrame, folds, featset_map: dict,
                 model_ok: pd.Series, variant: str) -> tuple[dict, list]:
    chosen, rows = {}, []
    for ch in CHANNELS:
        feats, ycol = featset_map[ch], f"t_d_{ch}"
        per_lam = []
        for lam in LAMBDAS:
            fold_maes = []
            for f in folds:
                tr_lab = f.train_idx[model_ok.loc[f.train_idx].to_numpy()]
                va_lab = f.val_idx[model_ok.loc[f.val_idx].to_numpy()]
                tr, va = g2.loc[tr_lab], g2.loc[va_lab]
                if len(tr) < 30 or len(va) < 10:
                    raise RuntimeError(
                        f"inner fold {f.name} too thin ({len(tr)}/{len(va)})")
                std = Standardizer(tr[feats])
                beta = ridge_fit(std.transform(tr[feats]),
                                 tr[ycol].to_numpy(float), lam)
                pred = ridge_predict(std.transform(va[feats]), beta)
                fold_maes.append(mae(pred - va[ycol].to_numpy(float)))
            per_lam.append((lam, fold_maes, float(np.mean(fold_maes))))
        best = min(per_lam, key=lambda t: (t[2], t[0]))
        chosen[ch] = best[0]
        for lam, fm, m in per_lam:
            rows.append({"variant": variant, "channel": ch, "lambda": lam,
                         **{f"mae_fold{i+1}": v for i, v in enumerate(fm)},
                         "mae_mean": m, "chosen": lam == best[0]})
    return chosen, rows


def fit_channels(g2: pd.DataFrame, train_lab, featset_map: dict,
                 lambdas: dict) -> dict:
    models = {}
    tr = g2.loc[train_lab]
    for ch in CHANNELS:
        feats = featset_map[ch]
        std = Standardizer(tr[feats])
        assert not std.dropped, f"zero-variance feature in {ch}: {std.dropped}"
        beta = ridge_fit(std.transform(tr[feats]),
                         tr[f"t_d_{ch}"].to_numpy(float), lambdas[ch])
        models[ch] = (std, beta, feats)
    return models


def predict_channels(g2: pd.DataFrame, models: dict, prefix: str) -> None:
    for ch, (std, beta, feats) in models.items():
        ok = g2[feats].notna().all(axis=1)
        g2.loc[ok, f"{prefix}_d_{ch}"] = ridge_predict(
            std.transform(g2.loc[ok, feats]), beta)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true",
                      help="scratch registry copy + scratch outdir (unless --outdir)")
    mode.add_argument("--real", action="store_true",
                      help="orchestrator only: records on the real ledger")
    ap.add_argument("--outdir", type=Path, default=None)
    args = ap.parse_args(argv)

    registry_path = None
    outdir = args.outdir or DEFAULT_OUTDIR
    if args.smoke:
        import tempfile
        scratch = Path(tempfile.mkdtemp(prefix="joint_differential_smoke_"))
        registry_path = scratch / "registry_scratch.jsonl"
        shutil.copyfile(REPO / "experiments" / "registry.jsonl", registry_path)
        outdir = args.outdir or (scratch / "out")
    outdir.mkdir(parents=True, exist_ok=True)
    run_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mode_s = "SMOKE" if args.smoke else "REAL"
    print(f"[jd] {mode_s} run at {run_time} -> {outdir}")

    reg = eh.get_registration(EXPERIMENT_ID, registry_path)
    print(f"[jd] registration OK: {EXPERIMENT_ID} (registered {reg['registered_at']}, "
          f"incumbent {reg['incumbent_id']}, regime {reg['regime']}, "
          f"primary {reg['primary_metric']})")

    # -- 0. committed constants ---------------------------------------------
    summ = json.loads(CHAN_SUMMARY.read_text(encoding="utf-8"))
    alphas = {k: float(v) for k, v in summ["alphas"].items()}
    assert alphas == ALPHAS_COMMITTED, f"committed alphas changed: {alphas}"
    cal_committed = summ["calibration"]["str_margin"]
    assert int(summ["calibration"]["n_train_games"]) == N_TRAIN_LEDGER

    rapm = pd.read_csv(RAPM)
    replacement = float(rapm["net_100"].quantile(0.25))
    assert abs(replacement - REPLACEMENT_COMMITTED) < 5e-4, replacement
    val_map = dict(zip(rapm["player_id"].astype("int64"), rapm["net_100"].astype(float)))

    # -- 1. rebuild the incumbent pipeline (committed alphas) ----------------
    D = rr.load_base()
    F = rr.build_features(D, alphas)
    games = rr.make_games(F)

    splits = eh.walk_forward_by_season(
        D, date_col="GAME_DATE", season_col="season",
        min_train_seasons=3, test_seasons=TEST_YEARS)
    by_name = {s.name: s for s in splits}
    outer24_D = by_name["season:2024"]
    train_ids = set(D.loc[outer24_D.train_idx, "GAME_ID"])
    assert sorted(D.loc[outer24_D.train_idx, "season"].unique()) == TRAIN_YEARS

    tg_mask = games["GAME_ID"].isin(train_ids) & games["eligible"]
    a_m, b_m = rr.linfit(games.loc[tg_mask, "str_margin_uncal"],
                         games.loc[tg_mask, "margin_true"])
    assert int(tg_mask.sum()) == N_TRAIN_LEDGER, int(tg_mask.sum())
    assert abs(a_m - cal_committed[0]) < 1e-9 and abs(b_m - cal_committed[1]) < 1e-9, \
        f"calibration reproduction failed: {(a_m, b_m)} vs {cal_committed}"
    games["inc_margin_cal"] = a_m + b_m * games["str_margin_uncal"]

    test_ids = {s: set(D.loc[by_name[f"season:{s}"].test_idx, "GAME_ID"])
                for s in TEST_YEARS}
    et_mask = games["eligible"] & games["GAME_ID"].isin(set().union(*test_ids.values()))
    n_total_test_games = int(D[D["season"].isin(TEST_YEARS)]["GAME_ID"].nunique())

    # -- AUDIT 0: incumbent reproduction (hard assert BEFORE anything else) --
    committed = pd.read_csv(CHAN_PRED)
    j = games.loc[et_mask, ["GAME_ID", "margin_true", "inc_margin_cal"]].merge(
        committed[["GAME_ID", "margin_true", "str_margin_cal", "naive_margin_pred"]],
        on="GAME_ID", validate="one_to_one", suffixes=("", "_c"))
    assert len(j) == len(committed) == int(et_mask.sum()), \
        (len(j), len(committed), int(et_mask.sum()))
    assert float((j["margin_true"] - j["margin_true_c"]).abs().max()) == 0.0
    repro_dev = float((j["inc_margin_cal"] - j["str_margin_cal"]).abs().max())
    inc_pooled = mae(j["str_margin_cal"] - j["margin_true"])
    naive_mae = mae(j["naive_margin_pred"] - j["margin_true"])
    assert repro_dev <= REPRO_TOL_PER_GAME, f"per-game reproduction dev {repro_dev}"
    assert abs(inc_pooled - INC_POOLED_LEDGER) <= 1e-3, inc_pooled
    print(f"[audit0] incumbent reproduced: per-game max|dev| = {repro_dev:.2e} "
          f"over {len(j)} games; pooled {inc_pooled:.6f} (ledger {INC_POOLED_LEDGER}); "
          f"naive {naive_mae:.4f}")

    # cross-check rebuilt chains against the committed w2 per-channel columns
    w2 = pd.read_csv(W2_PRED)
    w2j = games.loc[et_mask].merge(w2, left_on="GAME_ID", right_on="game_id",
                                   validate="one_to_one", suffixes=("", "_w2"))
    w2_dev = 0.0
    for ch in CHANNELS:
        for side in ("h", "a"):
            col = f"str_{ch}_{side}"
            w2_dev = max(w2_dev, float(
                (w2j[col] - w2j[f"{col}_w2"]).abs().max()))
    assert w2_dev <= 1e-6, f"w2 chain cross-check dev {w2_dev}"
    print(f"[audit0] w2 per-channel chain cross-check: max|dev| = {w2_dev:.2e}")

    # -- 2. walk-forward features: rest + RAPM lineup differential ----------
    mt = pd.read_parquet(MASTER_TEAM)
    rest = team_rest(mt)
    P = load_played_minutes()
    queries = pd.DataFrame({
        "season": games["season_h"].astype("int64"),
        "game_date": pd.to_datetime(games["GAME_DATE_h"]).dt.normalize(),
    })
    S = rapm_strengths(P, queries, val_map, replacement)
    n_repl_players = int(pd.Series(sorted(P["player_id"].unique()))
                         .map(lambda p: p not in val_map).sum())
    g2 = build_game_frame(D, F, games, rest, S)
    print(f"[feat] rapm replacement (p25 net_100) = {replacement:.3f}; "
          f"{n_repl_players} of {P['player_id'].nunique()} played players unrated")

    # -- 3. model universe + coverage ----------------------------------------
    feat_ok = g2[ALL_DIFF_FEATURES].notna().all(axis=1)
    model_ok = g2["eligible"] & feat_ok
    tg2 = g2["GAME_ID"].isin(train_ids) & g2["eligible"]
    et2 = g2["eligible"] & g2["GAME_ID"].isin(set().union(*test_ids.values()))
    n_train_gap = int((tg2 & ~feat_ok).sum())
    n_test_gap = int((et2 & ~feat_ok).sum())
    print(f"[cover] train eligible {int(tg2.sum())} (feature gaps {n_train_gap}); "
          f"test eligible {int(et2.sum())} (feature gaps {n_test_gap}); "
          f"mean roster {g2.loc[et2, ['roster_n_h', 'roster_n_a']].to_numpy().mean():.1f}; "
          f"mean replacement weight share "
          f"{g2.loc[et2, ['repl_wshare_h', 'repl_wshare_a']].to_numpy().mean():.3f}")
    assert int(tg2.sum()) == N_TRAIN_LEDGER
    if n_test_gap or n_train_gap:
        print(f"[cover] WARNING: coverage gaps (train {n_train_gap}, test {n_test_gap}) "
              "- the registration expected full coverage; gates will see it.")

    # -- 4. lambda tuning: inner walk-forward folds strictly inside 2021-2023
    splits_g = eh.walk_forward_by_season(
        g2, date_col="GAME_DATE_h", season_col="season_h",
        min_train_seasons=3, test_seasons=TEST_YEARS)
    outer24_g = {s.name: s for s in splits_g}["season:2024"]
    assert sorted(g2.loc[outer24_g.train_idx, "season_h"].unique()) == TRAIN_YEARS
    folds = eh.inner_tuning_splits(g2, outer24_g, date_col="GAME_DATE_h", n_folds=3)

    lambdas, curve_rows = tune_lambdas(g2, folds, FEATSETS, model_ok, "full")
    lambdas_abl, curve_rows_abl = tune_lambdas(g2, folds, FEATSETS_ABL, model_ok,
                                               "ablation_no_rapm")
    curves = pd.DataFrame(curve_rows + curve_rows_abl)
    print(f"[tune] lambdas (inner-fold winners): {lambdas}; "
          f"ablation: {lambdas_abl}")

    # -- 5. final fits on the 610 train games, frozen ------------------------
    train_lab = g2.index[tg2 & model_ok].to_numpy()
    test_lab = g2.index[et2 & model_ok].to_numpy()
    models = fit_channels(g2, train_lab, FEATSETS, lambdas)
    predict_channels(g2, models, "jd")
    models_abl = fit_channels(g2, train_lab, FEATSETS_ABL, lambdas_abl)
    predict_channels(g2, models_abl, "abl")

    for pref in ("jd", "abl"):
        g2[f"{pref}_margin_uncal"] = g2[[f"{pref}_d_{c}" for c in CHANNELS]].sum(
            axis=1, skipna=False)
    a_j, b_j = rr.linfit(g2.loc[train_lab, "jd_margin_uncal"],
                         g2.loc[train_lab, "margin_true"])
    g2["jd_margin_cal"] = a_j + b_j * g2["jd_margin_uncal"]
    a_a, b_a = rr.linfit(g2.loc[train_lab, "abl_margin_uncal"],
                         g2.loc[train_lab, "margin_true"])
    g2["abl_margin_cal"] = a_a + b_a * g2["abl_margin_uncal"]
    print(f"[fit] calibration (train 2021-2023, n={len(train_lab)}): "
          f"full a={a_j:.4f} b={b_j:.4f}; ablation a={a_a:.4f} b={b_a:.4f}; "
          f"incumbent a={a_m:.4f} b={b_m:.4f}")
    assert not g2.loc[test_lab, "jd_margin_cal"].isna().any()

    # feature importances (standardized coefficients)
    imp_rows = []
    for variant, mdl in (("full", models), ("ablation_no_rapm", models_abl)):
        for ch, (std, beta, feats) in mdl.items():
            imp_rows.append({"variant": variant, "channel": ch, "term": "intercept",
                             "coef_std": float(beta[0])})
            for f_name, b in zip(std.keep, beta[1:]):
                imp_rows.append({"variant": variant, "channel": ch,
                                 "term": f_name, "coef_std": float(b)})
    importances = pd.DataFrame(imp_rows)

    # =======================================================================
    # AUDITS (before results are believed)
    # =======================================================================
    rng = np.random.default_rng(AUDIT_SEED)
    et_games = g2[et2]
    sample_gids = []
    for s in TEST_YEARS:
        pool = et_games.loc[et_games["season_h"] == s, "GAME_ID"].to_numpy()
        sample_gids.extend(rng.choice(pool, size=min(SHIFT_AUDIT_PER_SEASON,
                                                     len(pool)), replace=False).tolist())

    # -- AUDIT 1: truncate-and-recompute shift audit on EVERY differential --
    audit1 = {"n_games": len(sample_gids), "mismatches": 0, "max_abs_dev": 0.0,
              "per_feature_max_dev": {f: 0.0 for f in ALL_DIFF_FEATURES}}
    gi = g2.set_index("GAME_ID")
    for gid in sample_gids:
        row = gi.loc[gid]
        d = pd.Timestamp(row["GDATE"])
        season = int(row["season_h"])
        # (a) trend differentials: blank every stat at/after d, rebuild
        Dm = D.copy()
        Dm.loc[pd.to_datetime(Dm["GAME_DATE"]) >= d, rr.STAT_COLS] = np.nan
        Fm = rr.build_features(Dm, alphas)
        got = trend_diffs_from_F(Fm, gid)
        # (b) rest differential from a date-truncated master_team
        rest_m = team_rest(mt[pd.to_datetime(mt["game_date"]) <= d])
        rm = rest_m.set_index(["game_id", "team_id"])["rest_days"]
        got["d_rest"] = (rm.loc[(str(gid), int(row["TEAM_ID_h"]))]
                         - rm.loc[(str(gid), int(row["TEAM_ID_a"]))])
        # (c) RAPM differential from strictly-prior played rows only
        Pm = P[P["game_date"] < d]
        Sm = rapm_strengths(Pm, pd.DataFrame({"season": [season], "game_date": [d]}),
                            val_map, replacement)
        smi = Sm.set_index("team_id")["strength"]
        got["d_rapm"] = (smi.get(int(row["TEAM_ID_h"]), np.nan)
                         - smi.get(int(row["TEAM_ID_a"]), np.nan))
        for f_name in ALL_DIFF_FEATURES:
            want, have = float(row[f_name]), float(got[f_name])
            dev = abs(want - have) if np.isfinite(want) and np.isfinite(have) else (
                0.0 if (np.isnan(want) and np.isnan(have)) else np.inf)
            audit1["per_feature_max_dev"][f_name] = max(
                audit1["per_feature_max_dev"][f_name], dev)
            audit1["max_abs_dev"] = max(audit1["max_abs_dev"], dev)
            if not dev <= ATOL:
                audit1["mismatches"] += 1
    audit1["passed"] = audit1["mismatches"] == 0
    print(f"[audit1] shift audit (truncate+recompute, {audit1['n_games']} games x "
          f"{len(ALL_DIFF_FEATURES)} differential features): "
          f"mismatches={audit1['mismatches']}, max|dev|={audit1['max_abs_dev']:.2e} "
          f"-> {'PASS' if audit1['passed'] else 'FAIL'}")

    # -- AUDIT 2: RAPM walk-forward, independent hand-loop recompute ---------
    rapm_gids = rng.choice(et_games["GAME_ID"].to_numpy(),
                           size=RAPM_AUDIT_GAMES, replace=False).tolist()
    audit2 = {"n_recomputes": 0, "mismatches": 0, "max_abs_dev": 0.0}
    for gid in rapm_gids:
        row = gi.loc[gid]
        d, season = pd.Timestamp(row["GDATE"]), int(row["season_h"])
        for side in ("h", "a"):
            want = float(row[f"rapm_{side}"])
            have, n_roster = manual_strength(P, season, d,
                                             int(row[f"TEAM_ID_{side}"]),
                                             val_map, replacement)
            dev = abs(want - have)
            audit2["n_recomputes"] += 1
            audit2["max_abs_dev"] = max(audit2["max_abs_dev"], dev)
            if not (dev <= ATOL and n_roster == int(row[f"roster_n_{side}"])):
                audit2["mismatches"] += 1
    audit2["passed"] = audit2["mismatches"] == 0
    print(f"[audit2] RAPM walk-forward recompute ({audit2['n_recomputes']} team-games, "
          f"weights from strictly-prior games only): mismatches={audit2['mismatches']}, "
          f"max|dev|={audit2['max_abs_dev']:.2e} -> "
          f"{'PASS' if audit2['passed'] else 'FAIL'}")

    # -- AUDIT 3: permutation probe (shuffled train targets must collapse) ---
    perm_maes = []
    ycols = [f"t_d_{c}" for c in CHANNELS]
    tr_frame = g2.loc[train_lab]
    for k in range(PERM_K):
        prng = np.random.default_rng(AUDIT_SEED + 1 + k)
        Yperm = tr_frame[ycols].copy()
        for s in TRAIN_YEARS:
            m = (tr_frame["season_h"] == s).to_numpy()
            idx = np.flatnonzero(m)
            Yperm.iloc[idx] = Yperm.iloc[prng.permutation(idx)].to_numpy()
        pred_sum_tr = np.zeros(len(tr_frame))
        pred_sum_te = np.zeros(len(test_lab))
        for ch in CHANNELS:
            std, _, feats = models[ch]
            beta_p = ridge_fit(std.transform(tr_frame[feats]),
                               Yperm[f"t_d_{ch}"].to_numpy(float), lambdas[ch])
            pred_sum_tr += ridge_predict(std.transform(tr_frame[feats]), beta_p)
            pred_sum_te += ridge_predict(std.transform(g2.loc[test_lab, feats]), beta_p)
        a_p, b_p = rr.linfit(pred_sum_tr, tr_frame["margin_true"].to_numpy(float))
        perm_maes.append(mae(a_p + b_p * pred_sum_te
                             - g2.loc[test_lab, "margin_true"].to_numpy(float)))
    jd_pooled = mae(g2.loc[test_lab, "jd_margin_cal"]
                    - g2.loc[test_lab, "margin_true"])
    audit3 = {
        "n_permutations": PERM_K, "perm_maes": [round(v, 4) for v in perm_maes],
        "naive_mae": naive_mae, "real_mae": jd_pooled,
        "near_naive_tol": PERM_NEAR_NAIVE_TOL, "min_gap": PERM_MIN_GAP,
        "passed": all(abs(v - naive_mae) <= PERM_NEAR_NAIVE_TOL
                      and v - jd_pooled >= PERM_MIN_GAP for v in perm_maes),
    }
    print(f"[audit3] permutation probe: perm MAEs {audit3['perm_maes']} "
          f"(naive {naive_mae:.4f}, real {jd_pooled:.4f}) -> "
          f"{'PASS (collapsed)' if audit3['passed'] else 'FAIL'}")

    audits = {"audit0_incumbent_reproduction": {
                  "per_game_max_dev": repro_dev, "pooled": inc_pooled,
                  "ledger": INC_POOLED_LEDGER, "w2_chain_max_dev": w2_dev,
                  "passed": True},
              "audit1_shift_truncate_recompute": audit1,
              "audit2_rapm_walk_forward": audit2,
              "audit3_permutation_probe": audit3}
    if not (audit1["passed"] and audit2["passed"] and audit3["passed"]):
        (outdir / "audit_results.json").write_text(
            json.dumps(audits, indent=2, default=str), encoding="utf-8")
        raise SystemExit("AUDIT FAILED - results are not evidence; stopping "
                         f"(see {outdir / 'audit_results.json'})")

    # =======================================================================
    # results
    # =======================================================================
    te = g2.loc[test_lab]
    err_jd = te["jd_margin_cal"] - te["margin_true"]
    err_abl = te["abl_margin_cal"] - te["margin_true"]
    err_inc = te["inc_margin_cal"] - te["margin_true"]

    season_rows = []
    for s in TEST_YEARS + ["pooled"]:
        m = slice(None) if s == "pooled" else (te["season_h"] == s).to_numpy()
        sub_jd, sub_abl, sub_inc = err_jd[m], err_abl[m], err_inc[m]
        season_rows.append({
            "season": s, "n": int(len(sub_jd)),
            "incumbent_mae": mae(sub_inc), "challenger_mae": mae(sub_jd),
            "delta": mae(sub_inc) - mae(sub_jd),
            "ablation_mae": mae(sub_abl),
            "abl_delta": mae(sub_inc) - mae(sub_abl)})
    season_tbl = pd.DataFrame(season_rows)
    print(fmt_table(season_tbl))

    # error-variance split (margin error = 2u; var(c) untouched by design)
    coh = json.loads(COHERENCE_SUMMARY.read_text(encoding="utf-8"))
    var_u_study = float(coh["incumbent_673"]["var_u"])
    var_c_study = float(coh["incumbent_673"]["var_c"])
    var_jd = float(err_jd.var(ddof=1))
    var_abl = float(err_abl.var(ddof=1))
    var_inc_head = float(err_inc.var(ddof=1))
    varu = {
        "margin_err_var_challenger": var_jd,
        "margin_err_var_ablation": var_abl,
        "margin_err_var_incumbent_head": var_inc_head,
        "implied_var_u_challenger": var_jd / 4.0,
        "implied_var_u_ablation": var_abl / 4.0,
        "implied_var_u_incumbent_head": var_inc_head / 4.0,
        "coherence_study_var_u_sideheads": var_u_study,
        "coherence_study_var_c_untouched": var_c_study,
        "beat_incumbent_head_var_u": bool(var_jd < var_inc_head),
        "beat_study_var_u": bool(var_jd / 4.0 < var_u_study),
    }

    # section-3b diagnostic: own-variance vs cross-covariance attribution
    E_jd = pd.DataFrame({ch: te[f"jd_d_{ch}"] - te[f"t_d_{ch}"] for ch in CHANNELS})
    E_inc = pd.DataFrame({ch: te[f"inc_d_{ch}"] - te[f"t_d_{ch}"] for ch in CHANNELS})
    def var_split(E):
        tot = float(E.sum(axis=1).var(ddof=1))
        own = float(sum(E[c].var(ddof=1) for c in E.columns))
        return tot, own, tot - own
    tot_jd, own_jd, cross_jd = var_split(E_jd)
    tot_inc, own_inc, cross_inc = var_split(E_inc)
    attribution = {
        "uncal_margin_err_var": {"challenger": tot_jd, "incumbent": tot_inc,
                                 "delta": tot_jd - tot_inc},
        "own_variance_term": {"challenger": own_jd, "incumbent": own_inc,
                              "delta": own_jd - own_inc},
        "cross_covariance_term": {"challenger": cross_jd, "incumbent": cross_inc,
                                  "delta": cross_jd - cross_inc},
        "corr_channel_vs_rest": {
            ch: {"challenger": float(np.corrcoef(
                     E_jd[ch], E_jd.drop(columns=[ch]).sum(axis=1))[0, 1]),
                 "incumbent": float(np.corrcoef(
                     E_inc[ch], E_inc.drop(columns=[ch]).sum(axis=1))[0, 1])}
            for ch in CHANNELS},
    }

    # per-channel differential MAE (secondary, uncalibrated on both sides)
    chan_rows = []
    for ch in CHANNELS:
        m_jd = mae(te[f"jd_d_{ch}"] - te[f"t_d_{ch}"])
        m_in = mae(te[f"inc_d_{ch}"] - te[f"t_d_{ch}"])
        chan_rows.append({"channel": ch, "n": len(te),
                          "incumbent_diff_mae": m_in, "challenger_diff_mae": m_jd,
                          "delta": m_in - m_jd, "lambda": lambdas[ch]})
    chan_tbl = pd.DataFrame(chan_rows)
    print(fmt_table(chan_tbl))

    # -- the registered comparison ------------------------------------------
    cov = len(te) / n_total_test_games
    ch_frame = pd.DataFrame({
        "game_id": te["GAME_ID"], "game_date": te["GAME_DATE_h"],
        "season": te["season_h"], "y_true": te["margin_true"].astype(float),
        "y_pred": te["jd_margin_cal"].astype(float),
        "home_team": te["TEAM_ID_h"]})
    inc_frame = j[["GAME_ID", "margin_true", "str_margin_cal"]].rename(columns={
        "GAME_ID": "game_id", "margin_true": "y_true", "str_margin_cal": "y_pred"})

    joint_tol = float(reg["thresholds"]["harm_ci_bound"])
    def joint_check():
        m_ch, m_inc = mae(err_jd), mae(err_inc)
        emitted = [c for c in ("jd_home_cal", "jd_away_cal", "jd_total_cal")
                   if c in g2.columns]
        comps = {
            "home_score": {"status": "untouched (incumbent artifact deployed)",
                           "delta_improvement": 0.0},
            "away_score": {"status": "untouched (incumbent artifact deployed)",
                           "delta_improvement": 0.0},
            "total": {"status": "untouched (incumbent artifact deployed)",
                      "delta_improvement": 0.0},
            "margin": {"challenger_mae": round(m_ch, 4),
                       "incumbent_mae": round(m_inc, 4),
                       "delta_improvement": round(m_inc - m_ch, 4)},
        }
        ok = (not emitted) and (m_ch <= m_inc + joint_tol)
        return ok, {"tolerance": joint_tol, "components": comps,
                    "side_or_total_columns_emitted": emitted,
                    "error_variance_split": varu}
    assert not any(c in g2.columns for c in
                   ("jd_home_cal", "jd_away_cal", "jd_total_cal"))

    result = eh.compare_to_incumbent(
        ch_frame, inc_frame, experiment_id=EXPERIMENT_ID,
        registry_path=registry_path, loss="absolute", cluster="date",
        team_col="home_team", joint_check=joint_check, coverage=(cov, cov))
    print(f"[gate] VERDICT: {result.verdict} (promote={result.promote}); "
          f"pooled {result.metric_challenger:.4f} vs {result.metric_incumbent:.4f}, "
          f"improvement {result.pooled_improvement:+.4f} "
          f"[90% CI {result.ci_low:+.4f}, {result.ci_high:+.4f}], "
          f"failed: {result.failed_gates or 'none'}")

    # ablation + RAPM-increment deltas (secondary; date-clustered CIs, no registry)
    dates = pd.to_datetime(te["GAME_DATE_h"]).dt.normalize().to_numpy()
    d_abl = (np.abs(err_inc.to_numpy()) - np.abs(err_abl.to_numpy()))
    d_incr = (np.abs(err_abl.to_numpy()) - np.abs(err_jd.to_numpy()))
    ci_abl = eh.cluster_bootstrap_ci(d_abl, dates)
    ci_incr = eh.cluster_bootstrap_ci(d_incr, dates)
    ablation = {
        "ablation_vs_incumbent_delta": float(d_abl.mean()),
        "ablation_ci90": [ci_abl["low"], ci_abl["high"]],
        "rapm_increment_delta_full_vs_ablation": float(d_incr.mean()),
        "rapm_increment_ci90": [ci_incr["low"], ci_incr["high"]],
        "lambdas_full": lambdas, "lambdas_ablation": lambdas_abl,
        "per_season": season_tbl.to_dict("records"),
    }
    print(f"[abl] ablation (no d_rapm) vs incumbent: {d_abl.mean():+.4f} "
          f"[{ci_abl['low']:+.4f}, {ci_abl['high']:+.4f}]; RAPM increment "
          f"(full vs ablation): {d_incr.mean():+.4f} "
          f"[{ci_incr['low']:+.4f}, {ci_incr['high']:+.4f}]")

    # -- artifacts -----------------------------------------------------------
    out_cols = (["GAME_ID", "GAME_DATE_h", "season_h", "season_type_h",
                 "TEAM_ABBREVIATION_h", "TEAM_ABBREVIATION_a", "margin_true",
                 "inc_margin_cal", "jd_margin_uncal", "jd_margin_cal",
                 "abl_margin_cal"]
                + [f"jd_d_{c}" for c in CHANNELS]
                + [f"inc_d_{c}" for c in CHANNELS]
                + [f"t_d_{c}" for c in CHANNELS]
                + ["d_rapm", "d_rest", "rapm_h", "rapm_a",
                   "roster_n_h", "roster_n_a", "repl_wshare_h", "repl_wshare_a"])
    te[out_cols].rename(columns={
        "GAME_DATE_h": "game_date", "season_h": "season",
        "season_type_h": "season_type", "GAME_ID": "game_id",
        "inc_margin_cal": "incumbent_margin_cal",
        "jd_margin_uncal": "challenger_margin_uncal",
        "jd_margin_cal": "challenger_margin_cal",
        "abl_margin_cal": "ablation_margin_cal",
    }).to_csv(outdir / "game_level_predictions.csv", index=False)
    curves.to_csv(outdir / "lambda_curves.csv", index=False)
    importances.to_csv(outdir / "feature_importance.csv", index=False)
    season_tbl.to_csv(outdir / "ablation_results.csv", index=False)
    (outdir / "gate_verdict.json").write_text(
        json.dumps(result.to_dict(), indent=2, default=str), encoding="utf-8")
    (outdir / "audit_results.json").write_text(
        json.dumps(audits, indent=2, default=str), encoding="utf-8")
    secondary = {
        "record_type": "joint_differential_secondary",
        "run_mode": mode_s, "run_time": run_time,
        "per_channel_differential_mae": chan_tbl.to_dict("records"),
        "section3b_attribution": attribution,
        "error_variance_split": varu,
        "ablation": ablation,
        "coverage": {"n_test_games": int(len(te)),
                     "n_total_test_games": n_total_test_games,
                     "coverage": cov, "train_feature_gaps": n_train_gap,
                     "test_feature_gaps": n_test_gap,
                     "mean_roster_size": float(
                         te[["roster_n_h", "roster_n_a"]].to_numpy().mean()),
                     "mean_replacement_weight_share": float(
                         te[["repl_wshare_h", "repl_wshare_a"]].to_numpy().mean())},
        "constants": {"alphas": alphas, "ewma_alpha_minutes": EWMA_ALPHA_MIN,
                      "replacement": replacement, "lambdas": lambdas,
                      "calibration_full": [a_j, b_j],
                      "calibration_ablation": [a_a, b_a],
                      "calibration_incumbent": [a_m, b_m]},
    }
    (outdir / "secondary_results.json").write_text(
        json.dumps(secondary, indent=2, default=str), encoding="utf-8")

    # -- REPORT.md -----------------------------------------------------------
    verdict_line = ("BEAT" if varu["beat_incumbent_head_var_u"] else "did NOT beat")
    rapm_carries = ablation["rapm_increment_delta_full_vs_ablation"]
    md = f"""# Joint differential margin system (`{EXPERIMENT_ID}`)

*Generated by `joint_differential.py` on {run_time} ({mode_s} run{"; gate verdict
recorded on a scratch registry copy - the ledger was NOT touched; the --real run
is the orchestrator's" if args.smoke else ""}). Regime A. Incumbent:
`{reg["incumbent_id"]}` (pooled margin MAE {inc_pooled:.4f} on the identical
{len(te)} games, reproduced per game to {repro_dev:.1e} before comparison).*

## The registered question

{reg["hypothesis"]}

Honest expectation, from the registration: the additive RAPM adjustment captured
+0.02 in the oracle bracket; this differential-chain reframing with fitted
per-channel weights tests whether structure unlocks more. A FAIL maps the R2
route's ceiling with current player values.

## Result: {result.verdict}

| scope | n | incumbent MAE | challenger MAE | delta | ablation (no RAPM) | abl delta |
|---|---|---|---|---|---|---|
""" + "\n".join(
        f"| {r['season']} | {r['n']} | {r['incumbent_mae']:.4f} | "
        f"{r['challenger_mae']:.4f} | {r['delta']:+.4f} | "
        f"{r['ablation_mae']:.4f} | {r['abl_delta']:+.4f} |"
        for r in season_rows) + f"""

- **Gate verdict: {result.verdict}** (pooled improvement
  {result.pooled_improvement:+.4f} vs the registered min_improvement
  {reg["thresholds"]["min_improvement"]}; 90% date-clustered CI
  [{result.ci_low:+.4f}, {result.ci_high:+.4f}], {result.n_clusters} clusters;
  failed gates: {result.failed_gates or "none"}; team-clustered sensitivity CI
  {result.ci_sensitivity_team}).
- Coverage {cov:.4f} for both models ({len(te)}/{n_total_test_games} test-season
  games; feature gaps: train {n_train_gap}, test {n_test_gap}).
- Gate 4: the model replaces ONLY the margin head - no side-score or total
  columns are emitted (asserted); home/away/total remain the incumbent's
  committed artifacts, deltas identically 0.

## Does the RAPM lineup differential carry the gain? (preregistered ablation)

| variant | pooled MAE | delta vs incumbent |
|---|---|---|
| incumbent | {mae(err_inc):.4f} | - |
| ablation (differential reframing only, no d_rapm) | {mae(err_abl):.4f} | {d_abl.mean():+.4f} [{ci_abl["low"]:+.4f}, {ci_abl["high"]:+.4f}] |
| full challenger (reframing + d_rapm) | {mae(err_jd):.4f} | {result.pooled_improvement:+.4f} [{result.ci_low:+.4f}, {result.ci_high:+.4f}] |

RAPM increment (full minus ablation, paired per game): **{rapm_carries:+.4f}**
[{ci_incr["low"]:+.4f}, {ci_incr["high"]:+.4f}].

## Error-variance split (what the coherence study said to watch)

Margin error = 2u; the common shock c never touches the margin and is untouched
here by construction (var(c) stays {var_c_study:.2f}).

| quantity | incumbent (study, side-heads) | incumbent margin head | challenger | ablation |
|---|---|---|---|---|
| margin error variance | {4 * var_u_study:.2f} | {var_inc_head:.2f} | {var_jd:.2f} | {var_abl:.2f} |
| implied var(u) | {var_u_study:.2f} | {var_inc_head / 4:.2f} | {var_jd / 4:.2f} | {var_abl / 4:.2f} |

The challenger {verdict_line} the incumbent margin head's error variance
(and {"beat" if varu["beat_study_var_u"] else "did not beat"} the study's
side-head var(u) = {var_u_study:.2f}).

## Per-channel differential MAE (secondary, uncalibrated both sides)

{fmt_table(chan_tbl)}

## Section-3b attribution (own variance vs cross-channel covariance, uncal)

| term | incumbent | challenger | delta |
|---|---|---|---|
| var(sum of channel diff errors) | {tot_inc:.2f} | {tot_jd:.2f} | {tot_jd - tot_inc:+.2f} |
| own-variance term | {own_inc:.2f} | {own_jd:.2f} | {own_jd - own_inc:+.2f} |
| cross-covariance term | {cross_inc:.2f} | {cross_jd:.2f} | {cross_jd - cross_inc:+.2f} |

## Model

- Features per channel (all home-minus-away differentials, all walk-forward):
  chain-ingredient differentials from the committed channel_base_v2 trends
  (own tendency, opponent allowed, conversion for ft/3pt - the paint/np2 chains
  carry no conversion ingredient, so none is invented), rest-day differential
  (master_team dates), RAPM lineup differential (minutes-EWMA alpha
  {EWMA_ALPHA_MIN} weights over strictly-prior played games, most-recent-team
  roster, rapm_v0 net_100, replacement {replacement:.3f} for unrated players -
  regime-A clean, no availability system).
- Ridge per channel (standardized, unpenalized intercept), fit on the
  {len(train_lab)} eligible 2021-2023 games; lambda per channel from
  evalharness.inner_tuning_splits (3 walk-forward folds inside 2021-2023),
  frozen: {lambdas} (ablation: {lambdas_abl}).
- margin = sum of the four predicted channel differentials, then the house
  train-years-only linear calibration on the same {len(train_lab)} games:
  a={a_j:.4f}, b={b_j:.4f} (incumbent: a={a_m:.4f}, b={b_m:.4f}).
- Mean roster size {secondary["coverage"]["mean_roster_size"]:.1f}; mean
  replacement weight share {secondary["coverage"]["mean_replacement_weight_share"]:.3f}.

## Audits (all passed before results were read)

- **Incumbent reproduction:** rebuilt chains + committed calibration reproduce
  `predictions_v2.csv` per game to {repro_dev:.1e}; pooled {inc_pooled:.4f}
  (ledger {INC_POOLED_LEDGER}); w2 per-channel chain cross-check {w2_dev:.1e}.
- **Shift audit (truncate + recompute):** {audit1["n_games"]} sampled test games,
  every stat at/after each game's date blanked (trends), master_team truncated
  (rest), played rows truncated (RAPM); all {len(ALL_DIFF_FEATURES)} differential
  features identical (max|dev| {audit1["max_abs_dev"]:.1e}).
- **RAPM walk-forward audit:** {audit2["n_recomputes"]} team-strengths recomputed
  by an independent hand-loop from strictly-prior played games; max|dev|
  {audit2["max_abs_dev"]:.1e}.
- **Permutation probe:** train channel targets shuffled within season, refit at
  frozen lambdas x{PERM_K}: test MAEs {audit3["perm_maes"]} vs naive
  {naive_mae:.4f} - the model collapses to no-skill; the fitted signal is not
  leakage plumbing.

## Files

`game_level_predictions.csv`, `lambda_curves.csv`, `feature_importance.csv`,
`ablation_results.csv`, `gate_verdict.json`, `audit_results.json`,
`secondary_results.json`.
"""
    (outdir / "REPORT.md").write_text(md, encoding="utf-8")
    print(f"[done] artifacts in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
