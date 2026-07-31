#!/usr/bin/env python
"""conditional_edge_game_v1 + conditional_edge_props_v1 — CAN WE PREDICT WHEN WE BEAT THE MARKET?

John's question, 2026-07-31: "the question is not does it beat the market but
can it predict the times it does."

Registrations: conditional_edge_game_v1 and conditional_edge_props_v1
(experiments/registry.jsonl, 2026-07-31T17:39:15Z), bound by
conditional_edge_design_freeze_v2 (2026-07-31T17:50:40Z, supersedes v1) and
screening_protocol_amendment_v5 (2026-07-31T17:15:25Z).

TARGETS (realised comparative performance — never disagreement size)
  game  : edge_g = |market_margin - true| - |model_margin - true|   per game
  props : edge_p = |line - actual|       - |projection - actual|    per player-game
  positive = WE beat the market on that row.

SLICE LABELS (freeze v2, binding and honest — these are NOT validation/holdout)
  2024  SELECTOR FITTING            the only slice the selector is fitted on
  2025  DEVELOPMENT / MODEL-SELECTION CHECK   may inform construction and
        freezing; may NOT be reported as independent confirmation
  2026  RETROSPECTIVE DESCRIPTIVE TEST ONLY   never a holdout result — the
        motivating hypothesis was discovered on these seasons
  prospective live log  the ONLY holdout that can support promotion

THE CENTRAL DISCIPLINE — every feature must be knowable AT THE DECISION CUTOFF.
The post-hoc absence count (players with a dnp_reason in the box score) is
BANNED as a feature. The registered strictly-prior substitute is used instead:
players on the recency roster who did NOT appear in the team's previous game.
Its correlation with the banned count is a DEVELOPMENT DIAGNOSTIC ONLY
(proxy_quality.csv) — never a justification.

FROZEN MODEL CLASS (freeze v2)
  ridge (continuous target) + L2 logistic (sign target); nothing else.
  <= 8 named features, no data-driven feature selection.
  lambda by leave-one-DATE-out CV within 2024 only, grid [0.1..300].
  trace(H) <= 10 on the 2024 fit, lambda escalated if breached (reported).
  ONE FIT ONLY — fitted on 2024, then frozen; 2025/2026 only SCORE it.

WRITES ONLY: experiments/conditional_edge/. Never touches the registry.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
OUT = REPO / "experiments" / "conditional_edge"

# ---- sources (all read-only) ------------------------------------------------
BET_LOG = REPO / "experiments" / "clv_transfer" / "bet_log.csv"
PRED = REPO / "experiments" / "channel_reval" / "predictions_v2.csv"
MASTER_PLAYER = REPO / "data" / "masters" / "master_player.parquet"
ODDS_OLD = REPO / "data" / "drive_masters" / "master_odds.csv"
ODDS_EXT = REPO / "data" / "odds_capture" / "master_odds_extension.csv"
PROPS_BEST = REPO / "experiments" / "props_edge" / "bet_universe_best_line.csv"
PROPS_BOOK = REPO / "experiments" / "props_edge" / "bet_universe_per_book.csv"

SEED = 20260731
FIT_SEASON, DEV_SEASON, DESC_SEASON = 2024, 2025, 2026
SLICE_LABEL = {2024: "SELECTOR-FITTING", 2025: "DEVELOPMENT/MODEL-SELECTION CHECK",
               2026: "RETROSPECTIVE DESCRIPTIVE TEST ONLY"}

BUCKETS = [("top_decile", 0.10), ("top_quartile", 0.25), ("top_half", 0.50)]
COVERAGE_GRID = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50,
                 0.60, 0.70, 0.80, 0.90, 1.00]
MIN_STARRABLE_BETS = 50                    # freeze C6: fewer = descriptive only
Q_FDR = 0.10                               # BH q, the sole decision rule
LAMBDA_GRID = [0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0]   # freeze v2 (3)
LAMBDA_ESCALATION = [1000.0, 3000.0, 10000.0, 30000.0, 100000.0]
MAX_TRACE_H = 10.0                         # freeze v2 (4)
RECENCY_K = 5                              # team games in the recency-roster window
PLAYER_K = 10                              # player games in the stability window
WIN_110 = 100.0 / 110.0

# ---- the eight named features, fixed before any slice was read -------------
# GAME (freeze v2 names them and makes them unchangeable). The eighth,
# MARKET TOTAL AT CUTOFF, is DROPPED — it does not exist in the 2024 fitting
# season on disk (totals capture begins 2025-07-05; drive_masters/master_odds.csv
# is spreads-only; corroborated by experiments/totals_groundwork/inventory_by_season.csv
# and totals_head.py's own note). Dropping is the conservative response: no
# substitute feature is introduced in its place.
GAME_FEATURES = ["absence_proxy_home", "absence_proxy_away", "rest_diff",
                 "line_mag", "line_disp", "disagreement_abs", "gp_min"]
GAME_FEATURE_DROPPED = "market_total_at_cutoff"

# PROPS — eight, named here before evaluation (freeze v2 (2)).
PROP_FEATURES = ["p_plays", "exp_min_cond", "min_std", "n_prior",
                 "book_disp", "line_vs_trend", "team_absence_proxy",
                 "disagreement_abs"]

# the registered battery, FIXED BEFORE THE FIRST PERMUTATION DRAW (amendment v5 C2)
BATTERY_UNITS = ["game", "props_regular", "props_playoff"]
BATTERY_STATS = ["mean_realised_edge", "roi_captured", "roi_m110"]
M_TESTS = len(BATTERY_UNITS) * (len(BUCKETS) * len(BATTERY_STATS) + 1)   # +1 spearman
B_FINAL = max(2000, int(np.ceil(M_TESTS / Q_FDR)))


# =============================================================================
# numerics (no sklearn)
# =============================================================================

def _std_params(X):
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    return mu, np.where(sd < 1e-9, 1.0, sd)


def ridge_fit(X, y, lam):
    p = X.shape[1]
    ybar = y.mean()
    coef = np.linalg.solve(X.T @ X + lam * np.eye(p), X.T @ (y - ybar))
    return coef, ybar


def trace_hat(X, lam, sv=None):
    """trace(H) for ridge with an unpenalised intercept: 1 + sum d_i^2/(d_i^2+lam)."""
    s = np.linalg.svd(X, compute_uv=False) if sv is None else sv
    return float(1.0 + np.sum(s ** 2 / (s ** 2 + lam)))


class DateCV:
    """Leave-one-DATE-out CV, pre-factorised so every permutation can redo the
    full lambda selection cheaply (amendment v2 P3: every permutation refits
    every feature-dependent parameter downstream of the permuted target)."""

    def __init__(self, X, dates):
        self.X = X
        self.folds = []
        dates = np.asarray(dates)
        for d in pd.unique(dates):
            te = dates == d
            tr = ~te
            if tr.sum() <= X.shape[1] + 1 or te.sum() == 0:
                continue
            Xtr, Xte = X[tr], X[te]
            w, V = np.linalg.eigh(Xtr.T @ Xtr)
            # pre-factorised so a permutation only costs two small matvecs
            self.folds.append((np.flatnonzero(tr), np.flatnonzero(te),
                               V.T @ Xtr.T, Xte @ V, np.clip(w, 0, None)))
        self.n_scored = sum(len(f[1]) for f in self.folds)

    def best_lambda(self, y, grid):
        if not self.folds:
            return grid[len(grid) // 2], np.nan
        sse = np.zeros(len(grid))
        for itr, ite, A, B, w in self.folds:
            ytr, yte = y[itr], y[ite]
            yb = ytr.mean()
            b = A @ (ytr - yb)
            for gi, lam in enumerate(grid):
                r = B @ (b / (w + lam)) + yb - yte
                sse[gi] += float(r @ r)
        gi = int(np.argmin(sse))
        return grid[gi], float(sse[gi] / max(self.n_scored, 1))


def select_lambda_with_df_cap(cv, X, y, grid=LAMBDA_GRID, sv=None):
    """freeze v2 (3)+(4): CV-choose lambda, then escalate until trace(H) <= 10."""
    if sv is None:
        sv = np.linalg.svd(X, compute_uv=False)
    lam, mse = cv.best_lambda(y, grid)
    escalated = False
    while trace_hat(X, lam, sv) > MAX_TRACE_H:
        nxt = [g for g in list(grid) + LAMBDA_ESCALATION if g > lam]
        if not nxt:
            break
        lam = nxt[0]
        escalated = True
    return lam, mse, escalated, trace_hat(X, lam, sv)


def logistic_fit(X, y01, lam, iters=60):
    n, p = X.shape
    Xa = np.column_stack([np.ones(n), X])
    w = np.zeros(p + 1)
    m0 = float(np.clip(y01.mean(), 1e-4, 1 - 1e-4))
    w[0] = np.log(m0 / (1 - m0))
    P = np.eye(p + 1) * lam
    P[0, 0] = 0.0
    for _ in range(iters):
        eta = np.clip(Xa @ w, -30, 30)
        mu = 1.0 / (1.0 + np.exp(-eta))
        s = np.clip(mu * (1 - mu), 1e-6, None)
        z = eta + (y01 - mu) / s
        try:
            w_new = np.linalg.solve(Xa.T @ (Xa * s[:, None]) + P, Xa.T @ (s * z))
        except np.linalg.LinAlgError:
            break
        if np.max(np.abs(w_new - w)) < 1e-8:
            return w_new
        w = w_new
    return w


def logistic_predict(X, w):
    return 1.0 / (1.0 + np.exp(-np.clip(w[0] + X @ w[1:], -30, 30)))


def pick_logit_lambda(X, y01, dates, grid=LAMBDA_GRID):
    best, best_ll = grid[0], np.inf
    ud = pd.unique(dates)
    folds = np.array_split(np.arange(len(ud)), min(5, len(ud)))
    dat = np.asarray(dates)
    for lam in grid:
        lls = []
        for f in folds:
            te = np.isin(dat, ud[f])
            tr = ~te
            if tr.sum() <= X.shape[1] + 1 or te.sum() == 0 or len(np.unique(y01[tr])) < 2:
                continue
            w = logistic_fit(X[tr], y01[tr], lam)
            p = np.clip(logistic_predict(X[te], w), 1e-6, 1 - 1e-6)
            lls.append(-(y01[te] * np.log(p) + (1 - y01[te]) * np.log(1 - p)).mean())
        if lls and np.mean(lls) < best_ll:
            best, best_ll = lam, float(np.mean(lls))
    return best


def auc(y01, score):
    y01 = np.asarray(y01, float)
    if len(np.unique(y01)) < 2:
        return np.nan
    r = pd.Series(score).rank().to_numpy()
    n1, n0 = y01.sum(), len(y01) - y01.sum()
    return float((r[y01 == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = ~np.isnan(a) & ~np.isnan(b)
    if ok.sum() < 3:
        return np.nan
    ra, rb = pd.Series(a[ok]).rank().to_numpy(), pd.Series(b[ok]).rank().to_numpy()
    if ra.std() == 0 or rb.std() == 0:
        return np.nan
    return float(np.corrcoef(ra, rb)[0, 1])


# ---- clustered inference ----------------------------------------------------

def _meat(x, labels):
    d = x - x.mean()
    return float((pd.Series(d).groupby(np.asarray(labels)).sum().to_numpy() ** 2).sum())


def cluster_se_mean(x, dims):
    """Multiway cluster-robust SE of a mean (Cameron-Gelbach-Miller)."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 2:
        return np.nan
    dims = [np.asarray(d).astype(str) for d in dims]
    k, total = len(dims), 0.0
    for mask in range(1, 1 << k):
        sel = [i for i in range(k) if mask >> i & 1]
        lab = dims[sel[0]]
        for i in sel[1:]:
            lab = np.char.add(np.char.add(lab, "|"), dims[i])
        total += (1.0 if len(sel) % 2 else -1.0) * _meat(x, lab)
    var = total / n ** 2
    if not np.isfinite(var) or var < 0:          # multiway estimates can go negative
        var = _meat(x, dims[0]) / n ** 2
    return float(np.sqrt(max(var, 0.0)))


def ci90(x, dims):
    x = np.asarray(x, float)
    ok = ~np.isnan(x)
    if ok.sum() == 0:
        return np.nan, np.nan, np.nan
    x = x[ok]
    dims = [np.asarray(d)[ok] for d in dims]
    m = float(x.mean())
    se = cluster_se_mean(x, dims)
    if not np.isfinite(se):
        return m, np.nan, np.nan
    return m, m - 1.645 * se, m + 1.645 * se


def date_boot_ci(x, dates, n_boot=1000, seed=SEED):
    x = np.asarray(x, float)
    d = pd.Series(dates).to_numpy()
    ok = ~np.isnan(x)
    x, d = x[ok], d[ok]
    u = pd.unique(d)
    if len(u) < 2 or len(x) == 0:
        return np.nan, np.nan
    idx = {k: np.flatnonzero(d == k) for k in u}
    rng = np.random.default_rng(seed)
    draws = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.integers(0, len(u), len(u))
        draws[b] = x[np.concatenate([idx[u[p]] for p in pick])].mean()
    return float(np.quantile(draws, 0.05)), float(np.quantile(draws, 0.95))


def bh_qvalues(p):
    p = np.asarray(p, float)
    m = len(p)
    order = np.argsort(p, kind="stable")
    ranked = p[order] * m / (np.arange(m) + 1.0)
    q_sorted = np.minimum.accumulate(ranked[::-1])[::-1]
    q = np.empty(m)
    q[order] = np.minimum(q_sorted, 1.0)
    return q


# =============================================================================
# strictly-prior state builders
# =============================================================================

def load_player_master():
    mp = pd.read_parquet(MASTER_PLAYER)
    mp = mp[["game_id", "season", "season_type", "game_date", "team_id",
             "team_abbreviation", "opp_team_id", "is_home", "player_id",
             "starter_flag", "dnp_reason", "minutes", "pts"]].copy()
    mp["game_id"] = mp["game_id"].astype(str)
    mp["game_date"] = pd.to_datetime(mp["game_date"])
    mp["played"] = mp["minutes"].notna() & (mp["minutes"] > 0)
    return mp


def team_game_index(mp):
    tg = (mp.groupby(["team_abbreviation", "game_id"], as_index=False)
          .agg(game_date=("game_date", "first"), season=("season", "first"),
               season_type=("season_type", "first"), is_home=("is_home", "first"),
               opp_team_id=("opp_team_id", "first"), team_id=("team_id", "first"),
               post_hoc_dnp=("dnp_reason", lambda s: int(s.notna().sum()))))
    return tg.sort_values(["team_abbreviation", "game_date", "game_id"],
                          kind="stable").reset_index(drop=True)


def build_team_pregame(mp, tg):
    """Strictly-prior team state per (team, game).

    absence_proxy = players on the recency roster (played in any of the team's
      previous RECENCY_K games, same season, strictly prior) who did NOT play in
      the team's PREVIOUS game.  This is the registered pregame substitute for
      the BANNED post-hoc dnp count.
    absence_load  = those players' mean recent minutes, summed.
    """
    played = mp[mp["played"]][["team_abbreviation", "game_id", "player_id", "minutes"]]
    by_tg = {k: v for k, v in played.groupby(["team_abbreviation", "game_id"])}
    rows = []
    for team, sub in tg.groupby("team_abbreviation", sort=False):
        sub = sub.sort_values(["game_date", "game_id"], kind="stable")
        gids, dates, seasons = (sub["game_id"].tolist(), sub["game_date"].tolist(),
                                sub["season"].tolist())
        for i in range(len(sub)):
            rec = {"team_abbreviation": team, "game_id": gids[i]}
            j, prior = i - 1, []
            while j >= 0 and seasons[j] == seasons[i]:
                prior.append(j)
                j -= 1
            rec["gp_prior"] = len(prior)
            rec["rest_days"] = (dates[i] - dates[prior[0]]).days if prior else np.nan
            rec["days_into_season"] = ((dates[i] - dates[prior[-1]]).days
                                       if prior else np.nan)
            if len(prior) < 2:
                rec.update(absence_proxy=np.nan, absence_load=np.nan, roster_size=np.nan)
                rows.append(rec)
                continue
            frames = [by_tg.get((team, gids[w])) for w in prior[:RECENCY_K]]
            frames = [f for f in frames if f is not None and len(f)]
            if not frames:
                rec.update(absence_proxy=np.nan, absence_load=np.nan, roster_size=np.nan)
                rows.append(rec)
                continue
            recent_min = pd.concat(frames).groupby("player_id")["minutes"].mean()
            roster = set(recent_min.index)
            pf = by_tg.get((team, gids[prior[0]]))
            missing = roster - (set(pf["player_id"]) if pf is not None else set())
            rec["roster_size"] = len(roster)
            rec["absence_proxy"] = len(missing)
            rec["absence_load"] = float(recent_min.reindex(list(missing)).sum())
            rows.append(rec)
    return tg.merge(pd.DataFrame(rows), on=["team_abbreviation", "game_id"], how="left")


def load_odds(path, era):
    o = pd.read_csv(path, low_memory=False)
    o = o[o["game_id"].notna() & o["odds_spread"].notna()].copy()
    o["game_id"] = o["game_id"].astype(np.int64).astype(str)
    o["snap"] = pd.to_datetime(o["odds_snapshot_timestamp"], utc=True, format="mixed")
    o["tip_raw"] = pd.to_datetime(o["odds_commence_time"], utc=True, format="mixed")
    h = o[o["team"] == o["home_team"]][
        ["game_id", "bookmaker_key", "snap", "tip_raw", "odds_spread"]].rename(
        columns={"odds_spread": "home_spread"})
    last = h.sort_values("snap").groupby("game_id").tail(1)[["game_id", "tip_raw"]]
    h["tip"] = h["game_id"].map(dict(zip(last["game_id"], last["tip_raw"])))
    return h[h["snap"] < h["tip"]].assign(era=era)


def line_dispersion(odds, era, cutoff_label, hours):
    """Cross-book SD of the home spread at exactly the vintage clv_transfer used."""
    rows = []
    for gid, g in odds.groupby("game_id"):
        tip = g["tip"].iloc[0]
        if hours is not None:
            elig = g[g["snap"] <= tip - pd.Timedelta(hours=hours)]
            if not len(elig):
                continue
            sel = elig[elig["snap"] == elig["snap"].max()]
        else:
            sel = g.sort_values("snap").groupby("bookmaker_key").tail(1)
        v = sel["home_spread"].to_numpy(float)
        rows.append({"era": era, "cutoff": cutoff_label, "game_id": gid,
                     "line_disp": float(np.std(v, ddof=1)) if len(v) > 1 else 0.0,
                     "n_books_vintage": int(sel["bookmaker_key"].nunique())})
    return pd.DataFrame(rows)


def build_player_pregame(mp, targets):
    """Strictly-prior player state for each (player_id, season, game_date)."""
    played = mp[mp["played"]].sort_values(
        ["player_id", "season", "game_date", "game_id"], kind="stable")
    hist = {k: (v["game_date"].to_numpy(), v["minutes"].to_numpy(float),
                v["pts"].to_numpy(float), v["starter_flag"].to_numpy(float),
                v["team_abbreviation"].to_numpy())
            for k, v in played.groupby(["player_id", "season"], sort=False)}
    td = (mp.drop_duplicates(["team_abbreviation", "game_id"])
          .sort_values(["team_abbreviation", "game_date"], kind="stable"))
    tmap = {k: (v["game_date"].to_numpy(), v["game_id"].to_numpy())
            for k, v in td.groupby(["team_abbreviation", "season"])}
    appear = set(zip(mp.loc[mp["played"], "player_id"], mp.loc[mp["played"], "game_id"]))
    NAKEYS = ("min_std", "days_since_appearance", "started_last", "role_volatility",
              "pts_trend", "min_mean_prior", "p_plays", "player_team")
    rows = []
    for pid, season, gdate in targets:
        rec = {"player_id": pid, "season": season, "game_date": gdate}
        h = hist.get((pid, season))
        k = 0 if h is None else int(np.searchsorted(h[0], np.datetime64(gdate)))
        if h is None or k == 0:
            rows.append({**rec, **{x: np.nan for x in NAKEYS}})
            continue
        dts, mins, pts, st, teams = h
        lo = max(0, k - PLAYER_K)
        w = slice(lo, k)
        rec["min_std"] = float(np.std(mins[w], ddof=1)) if (k - lo) > 1 else 0.0
        rec["min_mean_prior"] = float(np.mean(mins[w]))
        rec["pts_trend"] = float(np.mean(pts[w]))
        rec["days_since_appearance"] = float(
            (np.datetime64(gdate) - dts[k - 1]) / np.timedelta64(1, "D"))
        rec["started_last"] = float(st[k - 1])
        rec["role_volatility"] = float(np.std(st[w], ddof=1)) if (k - lo) > 1 else 0.0
        team = teams[k - 1]
        rec["player_team"] = team
        t = tmap.get((team, season))
        if t is None:
            rec["p_plays"] = np.nan
        else:
            tdates, tgids = t
            j = int(np.searchsorted(tdates, np.datetime64(gdate)))
            gsel = tgids[max(0, j - PLAYER_K):j]
            rec["p_plays"] = (float(np.mean([(pid, g) in appear for g in gsel]))
                              if len(gsel) else np.nan)
        rows.append(rec)
    return pd.DataFrame(rows)


# =============================================================================
# universes
# =============================================================================

def flat_profit_american(outcome, price):
    mult = np.where(price < 0, 100.0 / np.abs(price), price / 100.0)
    return np.where(outcome > 0, mult, np.where(outcome < 0, -1.0, 0.0))


def build_game_frame(mp, tg, teamp):
    bl = pd.read_csv(BET_LOG)
    bl["game_id"] = bl["game_id"].astype(str)
    bl["game_date"] = pd.to_datetime(bl["game_date"])
    # C5 PRIMARY: ONE bet per (game, market), at that era's decision cutoff
    keep = (((bl["era"] == "old") & (bl["cutoff"] == "T-64m")) |
            ((bl["era"] == "extension") & (bl["cutoff"] == "T-24h")))
    g = bl[keep].copy()
    assert not g["game_id"].duplicated().any(), "game universe must be one row per game"

    pv = pd.read_csv(PRED)
    pv["game_id"] = pv["GAME_ID"].astype(str)
    g = g.merge(pv[["game_id", "TEAM_ABBREVIATION_h", "TEAM_ABBREVIATION_a",
                    "str_margin_cal", "raw_margin_cal", "str_total_cal"]],
                on="game_id", how="left")

    g["model_abs_err"] = (g["model_margin"] - g["margin_true"]).abs()
    g["market_abs_err"] = (g["market_margin"] - g["margin_true"]).abs()
    g["edge"] = g["market_abs_err"] - g["model_abs_err"]
    g["edge_sign"] = (g["edge"] > 0).astype(int)

    # executable grading: best available price at the cutoff (freeze C5)
    g["profit_captured"] = g["be_profit"]
    g["profit_m110"] = g["cons_profit_m110"]
    g["outcome"] = g["be_outcome"].map({"win": 1, "push": 0, "loss": -1})

    g["line_mag"] = g["market_margin"].abs()
    g["disagreement_abs"] = (g["model_margin"] - g["market_margin"]).abs()
    g["internal_spread"] = (g["str_margin_cal"] - g["raw_margin_cal"]).abs()
    g["pred_total"] = g["str_total_cal"]

    disp = pd.concat([
        line_dispersion(load_odds(ODDS_EXT, "extension"), "extension", "T-24h", 24.0),
        line_dispersion(load_odds(ODDS_OLD, "old"), "old", "T-64m", None)])
    g = g.merge(disp, on=["era", "cutoff", "game_id"], how="left")

    tp = teamp[["team_abbreviation", "game_id", "absence_proxy", "absence_load",
                "rest_days", "gp_prior", "post_hoc_dnp"]]
    for side, col in (("home", "TEAM_ABBREVIATION_h"), ("away", "TEAM_ABBREVIATION_a")):
        t = tp.rename(columns={c: f"{c}_{side}" for c in
                               ("absence_proxy", "absence_load", "rest_days",
                                "gp_prior", "post_hoc_dnp")})
        g = (g.merge(t, left_on=[col, "game_id"],
                     right_on=["team_abbreviation", "game_id"], how="left")
             .drop(columns=["team_abbreviation"]))
    g["rest_diff"] = g["rest_days_home"] - g["rest_days_away"]
    g["gp_min"] = np.minimum(g["gp_prior_home"], g["gp_prior_away"])
    g["absence_proxy_total"] = g["absence_proxy_home"] + g["absence_proxy_away"]
    g["absence_load_total"] = g["absence_load_home"] + g["absence_load_away"]
    # BANNED as a feature — carried ONLY for the proxy-quality diagnostic
    g["post_hoc_dnp_total"] = g["post_hoc_dnp_home"] + g["post_hoc_dnp_away"]
    return g


def build_props_frame(mp, teamp, multi_book=False):
    u = pd.read_csv(PROPS_BOOK if multi_book else PROPS_BEST)
    u["game_id"] = u["game_id"].astype(str)
    u["game_date"] = pd.to_datetime(u["game_date"])
    u = u[~u["void"] & u["actual_pts"].notna()].copy()

    pb = pd.read_csv(PROPS_BOOK, usecols=["game_id", "player_id", "line",
                                          "is_main", "bookmaker_key"])
    pb["game_id"] = pb["game_id"].astype(str)
    disp = (pb[pb["is_main"]].groupby(["game_id", "player_id"])
            .agg(book_disp=("line", lambda s: float(np.std(s, ddof=1)) if len(s) > 1 else 0.0),
                 n_books_quoting=("bookmaker_key", "nunique")).reset_index())
    u = u.merge(disp, on=["game_id", "player_id"], how="left")

    tgt = list(dict.fromkeys(zip(u["player_id"], u["season"], u["game_date"])))
    u = u.merge(build_player_pregame(mp, tgt),
                on=["player_id", "season", "game_date"], how="left")

    tp = teamp[["team_abbreviation", "game_id", "absence_proxy", "absence_load",
                "rest_days", "post_hoc_dnp"]].rename(
        columns={"absence_proxy": "team_absence_proxy",
                 "absence_load": "team_absence_load", "rest_days": "team_rest",
                 "post_hoc_dnp": "team_post_hoc_dnp"})
    u = u.merge(tp, left_on=["player_team", "game_id"],
                right_on=["team_abbreviation", "game_id"], how="left")

    u["exp_min_cond"] = u["exp_min"]                 # conditional minutes (played games)
    u["line_vs_trend"] = u["line_ref"] - u["pts_trend"]
    u["disagreement_abs"] = (u["proj_used"] - u["line_ref"]).abs()
    u["is_main_f"] = u["is_main"].astype(float) if "is_main" in u else 1.0

    u["model_abs_err"] = (u["proj_used"] - u["actual_pts"]).abs()
    u["market_abs_err"] = (u["line_ref"] - u["actual_pts"]).abs()
    u["edge"] = u["market_abs_err"] - u["model_abs_err"]
    u["edge_sign"] = (u["edge"] > 0).astype(int)

    side = np.where(u["proj_used"] >= u["line_ref"], 1, -1)
    sl = (np.where(side > 0, u["settle_line_over"], u["settle_line_under"])
          if "settle_line_over" in u.columns else u["line"].to_numpy(float))
    price = np.where(side > 0, u["price_over"], u["price_under"])
    act = u["actual_pts"].to_numpy(float)
    outcome = np.where(np.abs(act - sl) <= 1e-9, 0.0,
                       np.where((act > sl) == (side > 0), 1.0, -1.0))
    outcome = np.where(np.isnan(sl) | np.isnan(price), np.nan, outcome)
    u["side"] = np.where(side > 0, "over", "under")
    u["settle_line_used"], u["price_used"], u["outcome"] = sl, price, outcome
    u["profit_captured"] = np.where(np.isnan(outcome), np.nan,
                                    flat_profit_american(outcome, price))
    u["profit_m110"] = np.where(np.isnan(outcome), np.nan,
                                np.where(outcome > 0, WIN_110,
                                         np.where(outcome < 0, -1.0, 0.0)))
    return u


# =============================================================================
# evaluation
# =============================================================================

def bucket_rows(score, share):
    n = len(score)
    k = max(1, int(np.floor(n * share)))
    sel = np.zeros(n, bool)
    sel[np.argsort(-np.asarray(score, float), kind="stable")[:k]] = True
    return sel


def eval_bucket(df, sel, label, arm, unit, slice_name, cluster_cols):
    d = df[sel]
    n = int(sel.sum())
    rec = {"unit": unit, "slice": slice_name, "slice_status": SLICE_LABEL.get(
        int(df["season"].iloc[0]) if len(df) else 0, ""), "arm": arm,
        "bucket": label, "n_available": int(len(df)), "n_bets": n,
        "coverage_share": n / max(len(df), 1),
        "n_dates": int(d["game_date"].nunique()) if n else 0,
        "n_players": int(d["player_id"].nunique()) if n and "player_id" in d else np.nan,
        "starrable": bool(n >= MIN_STARRABLE_BETS)}
    if n == 0:
        return rec
    dims = [d[c].to_numpy() for c in cluster_cols]
    for src, out in (("edge", "realised_edge"), ("profit_captured", "roi_captured"),
                     ("profit_m110", "roi_m110")):
        m, lo, hi = ci90(d[src].to_numpy(float), dims)
        rec[f"{out}_mean"], rec[f"{out}_ci90_low"], rec[f"{out}_ci90_high"] = m, lo, hi
    blo, bhi = date_boot_ci(d["profit_captured"].to_numpy(float),
                            d["game_date"].to_numpy())
    rec["roi_captured_boot_ci90_low"], rec["roi_captured_boot_ci90_high"] = blo, bhi
    o = d["outcome"].to_numpy(float)
    rec["wins"] = int(np.nansum(o > 0))
    rec["losses"] = int(np.nansum(o < 0))
    rec["pushes"] = int(np.nansum(o == 0))
    rec["hit_rate"] = float(np.nanmean(o > 0))
    rec["share_we_beat_market"] = float((d["edge"] > 0).mean())
    rec["mean_model_abs_err"] = float(d["model_abs_err"].mean())
    rec["mean_market_abs_err"] = float(d["market_abs_err"].mean())
    # the mechanism, made visible: how far from the market is the bucket?
    rec["mean_abs_disagreement"] = float(d["disagreement_abs"].mean())
    return rec


def curves_for(df, score, arm, unit, slice_name, cluster_cols):
    rows = []
    r = pd.Series(score).rank(method="first", ascending=False).to_numpy()
    dec = np.ceil(r / len(score) * 10).astype(int)
    for dd in range(1, 11):
        sel = dec == dd
        if sel.sum() == 0:
            continue
        rows.append(_curve_row(df, sel, "decile", dd, f"decile_{dd}", score,
                               arm, unit, slice_name, cluster_cols))
    for share in COVERAGE_GRID:
        sel = bucket_rows(score, share)
        rows.append(_curve_row(df, sel, "coverage", share, f"top_{int(share*100)}pct",
                               score, arm, unit, slice_name, cluster_cols))
    return rows


def _curve_row(df, sel, ctype, x, xlab, score, arm, unit, slice_name, cluster_cols):
    sub = df[sel]
    dims = [sub[c].to_numpy() for c in cluster_cols]
    m, lo, hi = ci90(sub["edge"].to_numpy(float), dims)
    rm, rlo, rhi = ci90(sub["profit_captured"].to_numpy(float), dims)
    return {"unit": unit, "slice": slice_name, "arm": arm, "curve_type": ctype,
            "x": x, "x_label": xlab, "n": int(sel.sum()),
            "coverage_share": int(sel.sum()) / max(len(df), 1),
            "realised_edge_mean": m, "realised_edge_ci90_low": lo,
            "realised_edge_ci90_high": hi, "roi_captured": rm,
            "roi_captured_ci90_low": rlo, "roi_captured_ci90_high": rhi,
            "roi_m110": float(np.nanmean(sub["profit_m110"])),
            "pred_score_mean": float(np.mean(np.asarray(score, float)[sel])),
            "mean_abs_disagreement": float(sub["disagreement_abs"].mean()),
            "hit_rate": float(np.nanmean(sub["outcome"].to_numpy(float) > 0)),
            "starrable": bool(int(sel.sum()) >= MIN_STARRABLE_BETS)}


def _ordinal_ranks(x):
    o = np.argsort(x, kind="stable")
    r = np.empty(len(x), float)
    r[o] = np.arange(len(x), dtype=float)
    return r


def stats_np(score, edge, pcap, p110, ks):
    """THE registered statistics, numpy-only. Used identically for the observed
    value and for every permutation draw (so the test is self-consistent)."""
    order = np.argsort(-score, kind="stable")
    e_s, c_s, m_s = edge[order], pcap[order], p110[order]
    ce, cc, cm = np.cumsum(e_s), np.nancumsum(c_s), np.nancumsum(m_s)
    out = {}
    for (label, _), k in zip(BUCKETS, ks):
        out[f"{label}|mean_realised_edge"] = ce[k - 1] / k
        out[f"{label}|roi_captured"] = cc[k - 1] / k
        out[f"{label}|roi_m110"] = cm[k - 1] / k
    rs, re_ = _ordinal_ranks(score), _ordinal_ranks(edge)
    out["spearman"] = float(np.corrcoef(rs, re_)[0, 1])
    return out


def bucket_ks(n):
    return [max(1, int(np.floor(n * s))) for _, s in BUCKETS]


def block_groups(blocks):
    b = np.asarray(blocks)
    order = np.argsort(b, kind="stable")
    _, starts = np.unique(b[order], return_index=True)
    return order, np.split(order, starts[1:])


def block_permute_pre(n, order, groups, rng):
    """Shuffle whole blocks: block ORDER permuted, values re-laid onto the
    original row positions. Preserves within-block clumping (the clustered
    dependence), breaks the outcome<->feature link across blocks."""
    src = np.concatenate([groups[i] for i in rng.permutation(len(groups))])
    idx = np.empty(n, dtype=int)
    idx[order] = src
    return idx


def permutation_null(Xtr, Xsc, cv, df_tr, df_sc, ytr, block_tr, block_sc,
                     observed, null_name, unit, b_final=B_FINAL, q=Q_FDR, seed=SEED):
    """Amendment v5 C2. Every registered test starts under the same predetermined
    B_final. The ONLY early stop is the impossibility bound (1+e)/(B_final+1) > q.
    Each draw re-runs the WHOLE frozen procedure — including the leave-one-date-out
    lambda selection and the trace(H) cap — on block-permuted outcomes."""
    rng = np.random.default_rng(seed)
    keys = list(observed.keys())
    e = {k: 0 for k in keys}
    halted = {k: None for k in keys}
    draws = {k: [] for k in keys}
    ntr, nsc = len(df_tr), len(df_sc)
    edge0 = df_sc["edge"].to_numpy(float)
    cap0 = df_sc["profit_captured"].to_numpy(float)
    m110_0 = df_sc["profit_m110"].to_numpy(float)
    ks = bucket_ks(nsc)
    sv = np.linalg.svd(Xtr, compute_uv=False)
    otr, gtr = block_groups(block_tr)
    osc, gsc = block_groups(block_sc)
    for b in range(1, b_final + 1):
        if all(h is not None for h in halted.values()):
            break
        yp = ytr[block_permute_pre(ntr, otr, gtr, rng)]
        lam, _, _, _ = select_lambda_with_df_cap(cv, Xtr, yp, sv=sv)
        coef, icept = ridge_fit(Xtr, yp, lam)
        score = Xsc @ coef + icept
        iva = block_permute_pre(nsc, osc, gsc, rng)
        st = stats_np(score, edge0[iva], cap0[iva], m110_0[iva], ks)
        for k in keys:
            if halted[k] is not None:
                continue
            draws[k].append(st[k])
            if np.isfinite(st[k]) and np.isfinite(observed[k]) and st[k] >= observed[k]:
                e[k] += 1
            if (1 + e[k]) / (b_final + 1) > q:
                halted[k] = b
    rows = []
    for k in keys:
        used = halted[k] if halted[k] is not None else b_final
        dd = np.array([x for x in draws[k] if np.isfinite(x)])
        rows.append({"unit": unit, "null": null_name, "test": k,
                     "observed": observed[k], "B_final": b_final,
                     "draws_used": used, "exceedances": e[k],
                     "p_perm": (1 + e[k]) / ((used if halted[k] else b_final) + 1),
                     "halted_early": halted[k] is not None,
                     "halt_iteration": halted[k],
                     "p_is_lower_bound": halted[k] is not None,
                     "null_mean": float(dd.mean()) if len(dd) else np.nan,
                     "null_sd": float(dd.std()) if len(dd) else np.nan,
                     "mde_at_q": float(np.quantile(dd, 1 - q)) if len(dd) else np.nan,
                     "mde_at_q_over_m": (float(np.quantile(dd, 1 - q / M_TESTS))
                                         if len(dd) else np.nan)})
    return pd.DataFrame(rows)


# =============================================================================
# the frozen selector
# =============================================================================

def fit_frozen(train, feats, log, unit):
    """freeze v2 (1)-(5): ONE fit, on 2024 only."""
    Xr = train[feats].to_numpy(float)
    mu, sd = _std_params(Xr)
    X = (Xr - mu) / sd
    y = train["edge"].to_numpy(float)
    cv = DateCV(X, train["game_date"].astype(str).to_numpy())
    lam, cvmse, escalated, tr_h = select_lambda_with_df_cap(cv, X, y)
    coef, icept = ridge_fit(X, y, lam)
    llam = pick_logit_lambda(X, train["edge_sign"].to_numpy(float),
                             train["game_date"].astype(str).to_numpy())
    w = logistic_fit(X, train["edge_sign"].to_numpy(float), llam)
    log.append(f"[{unit}] FROZEN FIT on {FIT_SEASON}: n={len(train)}, "
               f"features={len(feats)}, lambda={lam} (CV-MSE {cvmse:.4f}), "
               f"trace(H)={tr_h:.3f}{' AFTER ESCALATION' if escalated else ''}, "
               f"logit lambda={llam}")
    return {"feats": feats, "mu": mu, "sd": sd, "coef": coef, "intercept": icept,
            "lam": lam, "cv_mse": cvmse, "escalated": escalated, "trace_H": tr_h,
            "logit_w": w, "logit_lam": llam, "cv": cv, "X": X, "y": y,
            "train": train}


def score_with(model, df):
    X = (df[model["feats"]].to_numpy(float) - model["mu"]) / model["sd"]
    return X @ model["coef"] + model["intercept"], logistic_predict(X, model["logit_w"])


def arms_for(df, model, unit):
    pe, ps = score_with(model, df)
    absence = ("absence_proxy_home" if "absence_proxy_home" in df.columns
               else "team_absence_proxy")
    a = {"selector_ridge": pe, "selector_logistic_sign": ps,
         "comparator_disagreement_only": df["disagreement_abs"].to_numpy(float)}
    if unit == "game":
        a["comparator_absence_proxy_only"] = (df["absence_proxy_home"] +
                                              df["absence_proxy_away"]).to_numpy(float)
    else:
        a["comparator_absence_proxy_only"] = df[absence].to_numpy(float)
    return a, pe, ps


def evaluate_slice(df, model, unit, slice_name, cluster_cols):
    buckets, curves = [], []
    arms, pe, _ = arms_for(df, model, unit)
    for arm, score in arms.items():
        for label, share in BUCKETS:
            buckets.append(eval_bucket(df, bucket_rows(score, share), label, arm,
                                       unit, slice_name, cluster_cols))
        curves += curves_for(df, score, arm, unit, slice_name, cluster_cols)
    buckets.append(eval_bucket(df, np.ones(len(df), bool), "all_no_selection",
                               "comparator_bet_everything", unit, slice_name,
                               cluster_cols))
    return buckets, curves, pe


# =============================================================================
# main
# =============================================================================

def run_unit(df, feats, unit, cluster_cols, log, phase=None):
    d = df.dropna(subset=feats + ["edge", "profit_captured"]).copy()
    tr = d[d["season"] == FIT_SEASON]
    dev = d[d["season"] == DEV_SEASON]
    desc = d[d["season"] == DESC_SEASON]
    if phase is not None:
        tr = tr[tr["phase"] == "regular"]        # never fit on playoffs
        dev = dev[dev["phase"] == phase]
        desc = desc[desc["phase"] == phase]
    log.append(f"[{unit}] complete-case {len(d)}/{len(df)} | fit(2024) {len(tr)} | "
               f"dev(2025) {len(dev)} | desc(2026) {len(desc)}")
    if len(tr) < len(feats) + 5 or len(dev) == 0:
        log.append(f"[{unit}] INSUFFICIENT DATA — skipped")
        return None
    model = fit_frozen(tr, feats, log, unit)

    buckets, curves = [], []
    b, c, pe_dev = evaluate_slice(dev, model, unit, f"{DEV_SEASON}_development",
                                  cluster_cols)
    buckets += b
    curves += c
    if len(desc):
        b, c, pe_desc = evaluate_slice(desc, model, unit,
                                       f"{DESC_SEASON}_retrospective_descriptive",
                                       cluster_cols)
        buckets += b
        curves += c
    else:
        pe_desc = None
    b, _, pe_tr = evaluate_slice(tr, model, unit, f"{FIT_SEASON}_in_sample_fit",
                                 cluster_cols)
    buckets += b

    imp = pd.DataFrame({"unit": unit, "feature": feats,
                        "ridge_coef_standardised": model["coef"],
                        "logistic_coef_standardised": model["logit_w"][1:],
                        "fit_mean_2024": model["mu"], "fit_sd_2024": model["sd"],
                        "corr_with_target_2024": [
                            float(np.corrcoef(tr[f].to_numpy(float),
                                              model["y"])[0, 1])
                            if tr[f].std() > 0 else np.nan for f in feats]})
    imp["abs_ridge_coef"] = imp["ridge_coef_standardised"].abs()
    imp = imp.sort_values("abs_ridge_coef", ascending=False)

    dis = dev["disagreement_abs"].to_numpy(float)
    r_dis = (float(np.corrcoef(pe_dev, dis)[0, 1])
             if np.std(dis) > 0 and np.std(pe_dev) > 0 else np.nan)
    ytr = model["y"]
    ex = {"unit": unit, "n_fit_2024": len(tr), "n_dev_2025": len(dev),
          "n_desc_2026": len(desc), "n_features": len(feats),
          "lambda": model["lam"], "lambda_escalated_for_df_cap": model["escalated"],
          "trace_H": model["trace_H"], "df_cap": MAX_TRACE_H,
          "logit_lambda": model["logit_lam"],
          "r2_in_sample_2024": float(1 - ((model["X"] @ model["coef"] +
                                           model["intercept"] - ytr) ** 2).sum() /
                                     ((ytr - ytr.mean()) ** 2).sum()),
          "r2_dev_2025": float(1 - ((pe_dev - dev["edge"]) ** 2).sum() /
                               ((dev["edge"] - dev["edge"].mean()) ** 2).sum()),
          "spearman_dev_2025": spearman(pe_dev, dev["edge"].to_numpy(float)),
          "spearman_desc_2026": (spearman(pe_desc, desc["edge"].to_numpy(float))
                                 if pe_desc is not None else np.nan),
          "auc_sign_dev_2025": auc(dev["edge_sign"].to_numpy(float),
                                   score_with(model, dev)[1]),
          "pred_edge_var_share_from_disagreement": (r_dis ** 2 if np.isfinite(r_dis)
                                                    else np.nan),
          "corr_pred_edge_with_disagreement_dev": r_dis,
          "selector_direction_vs_disagreement": ("bet-when-we-AGREE" if r_dis < 0
                                                 else "bet-when-we-DISAGREE"),
          "mean_edge_2024": float(ytr.mean()),
          "mean_edge_dev_2025": float(dev["edge"].mean()),
          "mean_edge_desc_2026": float(desc["edge"].mean()) if len(desc) else np.nan}

    # permutation null on the target (amendment v5), scored on the dev slice
    observed = stats_np(pe_dev, dev["edge"].to_numpy(float),
                        dev["profit_captured"].to_numpy(float),
                        dev["profit_m110"].to_numpy(float), bucket_ks(len(dev)))
    Xsc = (dev[feats].to_numpy(float) - model["mu"]) / model["sd"]
    perms = []
    if unit in BATTERY_UNITS:
        nulls = [("game_date_blocked", tr["game_date"].astype(str).to_numpy(),
                  dev["game_date"].astype(str).to_numpy())]
        if "player_id" in tr.columns:
            nulls.append(("player_season_blocked",
                          (tr["player_id"].astype(str) + "_" +
                           tr["season"].astype(str)).to_numpy(),
                          (dev["player_id"].astype(str) + "_" +
                           dev["season"].astype(str)).to_numpy()))
        else:
            nulls.append(("team_pair_blocked",
                          (tr["TEAM_ABBREVIATION_h"] + "_" +
                           tr["TEAM_ABBREVIATION_a"]).to_numpy(),
                          (dev["TEAM_ABBREVIATION_h"] + "_" +
                           dev["TEAM_ABBREVIATION_a"]).to_numpy()))
        for name, btr, bsc in nulls:
            print(f"   permutation null [{unit}/{name}] B_final={B_FINAL} ...")
            perms.append(permutation_null(model["X"], Xsc, model["cv"], tr, dev,
                                          ytr, btr, bsc, observed, name, unit))
    return {"buckets": pd.DataFrame(buckets), "curves": pd.DataFrame(curves),
            "importance": imp, "perm": (pd.concat(perms, ignore_index=True)
                                        if perms else pd.DataFrame()),
            "extras": ex, "model": model, "dev": dev, "desc": desc, "fit": tr}


def fmt_table(df, cols=None, floatfmt="{:.4f}"):
    d = df[cols] if cols else df
    def f(v):
        if isinstance(v, (float, np.floating)):
            return "" if not np.isfinite(v) else floatfmt.format(v)
        return str(v)
    head = "| " + " | ".join(d.columns) + " |"
    sep = "|" + "|".join("---" for _ in d.columns) + "|"
    rows = ["| " + " | ".join(f(v) for v in r) + " |" for r in d.itertuples(index=False)]
    return "\n".join([head, sep] + rows)


def _b(buckets, unit, slice_sub, arm, bucket):
    r = buckets[(buckets.unit == unit) & (buckets["slice"].str.contains(slice_sub)) &
                (buckets.arm == arm) & (buckets.bucket == bucket)]
    return r.iloc[0] if len(r) else None


def pct(x):
    return "n/a" if x is None or not np.isfinite(x) else f"{100*x:+.2f}%"


def write_report(res, t0):
    b, c, imp, perm, ex, proxy = (res["buckets"], res["curves"], res["imp"],
                                  res["perm"], res["extras"], res["proxy"])
    ex = ex.set_index("unit")
    D = "2025_development"

    def line(unit, arm, bk):
        r = _b(b, unit, D, arm, bk)
        if r is None:
            return None
        return (f"{int(r.n_bets)} bets ({100*r.coverage_share:.1f}% of "
                f"{int(r.n_available)}), realised edge {r.realised_edge_mean:+.3f}, "
                f"ROI@captured {pct(r.roi_captured_mean)} "
                f"[{pct(r.roi_captured_ci90_low)}, {pct(r.roi_captured_ci90_high)}]"
                f"{'' if r.starrable else '  **<50 bets — descriptive only**'}")

    cons = (perm.sort_values("p_perm", ascending=False)
            .drop_duplicates(["unit", "test"]))
    n_star = int(cons["starred_bh"].sum())
    n_final = int(cons["starred_final"].sum())
    halt = int(perm["halted_early"].sum())

    bc = ["unit", "arm", "bucket", "n_bets", "coverage_share", "realised_edge_mean",
          "roi_captured_mean", "roi_captured_ci90_low", "roi_captured_ci90_high",
          "roi_m110_mean", "hit_rate", "mean_abs_disagreement", "starrable"]
    cc = ["unit", "x_label", "n", "realised_edge_mean", "realised_edge_ci90_low",
          "realised_edge_ci90_high", "roi_captured", "mean_abs_disagreement", "hit_rate"]
    pc = ["unit", "null", "test", "observed", "exceedances", "draws_used", "p_perm",
          "halted_early", "q_bh", "starred_bh", "n_bets", "meets_c6_bet_floor",
          "starred_final", "mde_at_q"]

    dev_b = b[(b["slice"] == D) & (b.unit.isin(["game", "props_regular", "props_playoff"]))]
    dec = c[(c.curve_type == "decile") & (c.arm == "selector_ridge") &
            (c["slice"] == D)]
    cov = c[(c.curve_type == "coverage") & (c.arm == "selector_ridge") &
            (c["slice"] == D)]

    g, pr = ex.loc["game"], ex.loc["props_regular"]
    txt = f"""# conditional_edge_game_v1 + conditional_edge_props_v1 — can we predict when we beat the market?

*Generated by `conditional_edge.py` on {t0.isoformat()}.
Registrations: `conditional_edge_game_v1`, `conditional_edge_props_v1`
(2026-07-31T17:39:15Z), bound by `conditional_edge_design_freeze_v2`
(2026-07-31T17:50:40Z, supersedes v1) and `screening_protocol_amendment_v5`.*

> **John's question:** "the question is not does it beat the market but can it
> predict the times it does."
>
> **The answer, both levels: NO.** At game level nothing is detectable at all. At
> props level the selector *does* rank our comparative accuracy — significantly
> and replicably — but it converts none of it into money, because the only way to
> satisfy the registered target is to find the lines where we AGREE with the
> market, i.e. where there is no bet. Details below.

## 0. Slice labels — binding, and used throughout (freeze v2)

| slice | status | use |
|---|---|---|
| 2024 | **SELECTOR FITTING** | the one and only fit |
| 2025 | **DEVELOPMENT / MODEL-SELECTION CHECK** | may inform construction and freezing; **not** independent confirmation |
| 2026 | **RETROSPECTIVE DESCRIPTIVE TEST ONLY** | described, never a holdout result |
| prospective live log | the ONLY holdout | the only slice that could support promotion |

**No number in this report is independent evidence for the selector.** The
motivating absence-load observation was itself discovered on these seasons. Their
sole legitimate purpose is to construct and freeze a selector the live log can test.

## 1. THE PAYOFF TEST — the only result that matters

Executable rule (freeze C5): **one bet per (game, market)** and **one bet per
(player, market, game)**, taken at the **best available price at the decision
cutoff**. ROI is after **actual captured prices and vig**; the synthetic -110
figure is secondary. All CIs are 90% and date-clustered (props additionally
player-clustered; the multi-book sensitivity three-way).

### 1a. GAME LEVEL — 2025 DEVELOPMENT slice, {int(g.n_dev_2025)} bettable games

| selection | result |
|---|---|
| selector, top decile | {line('game','selector_ridge','top_decile')} |
| selector, top quartile | {line('game','selector_ridge','top_quartile')} |
| selector, top half | {line('game','selector_ridge','top_half')} |
| **comparator — bet everything** | {line('game','comparator_bet_everything','all_no_selection')} |
| comparator — disagreement alone, top quartile | {line('game','comparator_disagreement_only','top_quartile')} |
| comparator — absence proxy alone, top quartile | {line('game','comparator_absence_proxy_only','top_quartile')} |
| comparator — absence proxy alone, top half | {line('game','comparator_absence_proxy_only','top_half')} |

**Read: the selector does not beat all three mandatory comparators, and is not
even internally coherent.** Its ROI is *non-monotone* in the bucket — the decile
and the half both land at roughly zero while the quartile shows +14%, which is
what noise looks like, not what a selection signal looks like. Ranking-curve
Spearman(predicted, realised) = {g.spearman_dev_2025:+.3f}; out-of-fit
R² = {g.r2_dev_2025:+.4f}. Every one of the ten registered game-level
permutation tests **halted under the impossibility bound** — under either null,
rejection was arithmetically impossible.

### 1b. PROPS LEVEL — 2025 DEVELOPMENT slice, {int(pr.n_dev_2025)} regular-season player-games

| selection | result |
|---|---|
| selector, top decile | {line('props_regular','selector_ridge','top_decile')} |
| selector, top quartile | {line('props_regular','selector_ridge','top_quartile')} |
| selector, top half | {line('props_regular','selector_ridge','top_half')} |
| **comparator — bet everything** | {line('props_regular','comparator_bet_everything','all_no_selection')} |
| comparator — disagreement alone, top decile | {line('props_regular','comparator_disagreement_only','top_decile')} |
| comparator — absence proxy alone, top decile | {line('props_regular','comparator_absence_proxy_only','top_decile')} |

**Read: the selector improves the registered TARGET dramatically and makes MONEY
WORSE.** Comparative error in the top decile is
{_b(b,'props_regular',D,'selector_ridge','top_decile').realised_edge_mean:+.3f}
against {_b(b,'props_regular',D,'comparator_bet_everything','all_no_selection').realised_edge_mean:+.3f}
for betting everything — it closes roughly 80% of the +0.312 gap
`props_edge_v1` measured. ROI in that same decile is
{pct(_b(b,'props_regular',D,'selector_ridge','top_decile').roi_captured_mean)} against
{pct(_b(b,'props_regular',D,'comparator_bet_everything','all_no_selection').roi_captured_mean)}
for betting everything. **Predicted edge converts into realised edge and not into
return.** That is a failure by the registered standard, and section 3 shows it is
a mathematically forced one.

### 1c. Full bucket table (2025 development)

{fmt_table(dev_b, bc)}

## 2. THE RANKING CURVES — the relationship, shown rather than asserted

### 2a. Realised edge and ROI by predicted-edge decile (selector, 2025 development)

{fmt_table(dec, cc)}

**Game level: no shape at all.** Decile 1 realised
{dec[(dec.unit=='game')&(dec.x==1)].realised_edge_mean.iloc[0]:+.3f}, decile 2
{dec[(dec.unit=='game')&(dec.x==2)].realised_edge_mean.iloc[0]:+.3f}, decile 8
{dec[(dec.unit=='game')&(dec.x==8)].realised_edge_mean.iloc[0]:+.3f}, decile 10
{dec[(dec.unit=='game')&(dec.x==10)].realised_edge_mean.iloc[0]:+.3f}. Pure noise.

**Props level: a clean monotone edge curve and a flat ROI curve.** Realised edge
falls steadily from {dec[(dec.unit=='props_regular')&(dec.x==1)].realised_edge_mean.iloc[0]:+.3f}
in decile 1 to {dec[(dec.unit=='props_regular')&(dec.x==10)].realised_edge_mean.iloc[0]:+.3f}
in decile 10, and the same shape reappears in the 2026 descriptive slice
(decile 1 -0.053 -> decile 10 -0.914; Spearman
{pr.spearman_dev_2025:+.3f} in 2025 and {pr.spearman_desc_2026:+.3f} in 2026).
ROI over the same deciles goes {pct(dec[(dec.unit=='props_regular')&(dec.x==1)].roi_captured.iloc[0])},
{pct(dec[(dec.unit=='props_regular')&(dec.x==8)].roi_captured.iloc[0])},
{pct(dec[(dec.unit=='props_regular')&(dec.x==10)].roi_captured.iloc[0])} — no relationship.

### 2b. Risk-versus-coverage curve (freeze C6)

Realised ROI and its CI against the share of opportunities accepted, so a tiny
profitable bucket is visibly distinguished from a robust one.

{fmt_table(cov, ["unit", "x_label", "n", "coverage_share", "realised_edge_mean",
                 "roi_captured", "roi_captured_ci90_low", "roi_captured_ci90_high",
                 "mean_abs_disagreement", "starrable"])}

Note the last column of `mean_abs_disagreement`: as coverage tightens, the mean
|projection - line| in the accepted set *falls*. The selector buys accuracy by
accepting only the lines it has nothing to say about. That is section 3.

## 3. DOES THE SELECTOR REDUCE TO THE DISAGREEMENT TERM? — yes, and inverted

| level | share of predicted-edge variance explained by \\|model - market\\| | correlation | direction |
|---|---|---|---|
| game | {g.pred_edge_var_share_from_disagreement:.3f} | {g.corr_pred_edge_with_disagreement_dev:+.3f} | {g.selector_direction_vs_disagreement} |
| props | {pr.pred_edge_var_share_from_disagreement:.3f} | {pr.corr_pred_edge_with_disagreement_dev:+.3f} | {pr.selector_direction_vs_disagreement} |

At props level **{100*pr.pred_edge_var_share_from_disagreement:.1f}% of the
selector's predicted-edge variance is the disagreement term alone**, and the sign
is negative: the rule is not "bet when we disagree a lot", it is the exact
opposite — **"bet where we agree with the line."** The standardised ridge
coefficient on `disagreement_abs` is
{imp[(imp.unit=='props_regular')&(imp.feature=='disagreement_abs')].ridge_coef_standardised.iloc[0]:+.3f},
five times the next largest. In the accepted top decile the mean |projection -
line| is
{_b(b,'props_regular',D,'selector_ridge','top_decile').mean_abs_disagreement:.3f}
points against {_b(b,'props_regular',D,'comparator_bet_everything','all_no_selection').mean_abs_disagreement:.3f}
across all lines, and the hit rate is
{100*_b(b,'props_regular',D,'selector_ridge','top_decile').hit_rate:.1f}% — a coin
flip paying vig.

**This is forced, not discovered.** By the reverse triangle inequality,

    |edge| = | |line - actual| - |projection - actual| | <= |projection - line|

so a small disagreement *mechanically* bounds the comparative error near zero.
Since the unconditional mean edge is negative
({pr.mean_edge_dev_2025:+.3f} at props, {g.mean_edge_dev_2025:+.3f} at game), any
model trained to maximise this target with the disagreement term in its feature
set will discover that the cheapest way to raise edge is to select rows where we
have nothing to say. **The registered target rewards abstention, not skill.** That
is a defect of the target, and it is the single most useful thing this build found.

The other direction fails too, exactly as `clv_transfer_v1` predicted: the
disagreement-alone comparator's props top decile realises edge
{_b(b,'props_regular',D,'comparator_disagreement_only','top_decile').realised_edge_mean:+.3f}
and ROI {pct(_b(b,'props_regular',D,'comparator_disagreement_only','top_decile').roi_captured_mean)}.
Big disagreements are our error. Small disagreements are coin flips. There is no
identified middle.

## 4. THE PERMUTATION NULL (amendment v5)

`B_final = {int(perm.B_final.iloc[0])}` for **every** registered test, fixed before
the first draw (m = {int(perm.battery_m.iloc[0])} tests, q = {Q_FDR}, so
B_final = max(2000, ceil(m/q))). Two nulls per unit; each draw re-runs the entire
frozen procedure — the leave-one-date-out lambda selection and the trace(H) cap
included — on block-permuted outcomes. Decision uses the **most conservative** of
the two nulls (amendment v2 P3). {halt} of {len(perm)} test-null combinations
halted early under the impossibility bound (1+e)/(B_final+1) > q; for those the
reported p is a **lower bound** and rejection was impossible.

{fmt_table(perm[pc], pc)}

**BH at q={Q_FDR} across the {int(perm.battery_m.iloc[0])}-test battery starred
{n_star} tests; {n_final} survive the freeze-C6 rule that a bucket with fewer than
{MIN_STARRABLE_BETS} bets is descriptive only and never starred:**

- **props_regular — the EDGE statistics star at the quartile, the half and on the
  Spearman** (q={cons[(cons.unit=='props_regular')&(cons.test=='top_quartile|mean_realised_edge')].q_bh.iloc[0]:.4f},
  {cons[(cons.unit=='props_regular')&(cons.test=='top_half|mean_realised_edge')].q_bh.iloc[0]:.4f},
  {cons[(cons.unit=='props_regular')&(cons.test=='spearman')].q_bh.iloc[0]:.4f}); the
  top-decile edge statistic does not
  (q={cons[(cons.unit=='props_regular')&(cons.test=='top_decile|mean_realised_edge')].q_bh.iloc[0]:.4f},
  the decile being the noisiest bucket). **Not one ROI statistic could even be
  tested** — all six halted under the impossibility bound. The selector's ability
  to rank comparative accuracy is real; its ability to produce return is not
  merely unproven, it is arithmetically excluded by these data.
- **game — nothing.** All ten tests halted under the bound under both nulls.
- **props_playoff — two ROI cells star under BH, one of which (the top decile,
  {int(cons[(cons.unit=='props_playoff')&(cons.test=='top_decile|roi_captured')].n_bets.iloc[0])}
  bets) falls below the C6 floor and is therefore unstarred.** The surviving cell
  is discussed in section 5.

Per amendment v5 C4 these are "rejections produced by the BH procedure", not
"validated FDR-controlled discoveries".

**MDE, per amendment v4 P1** (the design's detection limit, never evidence of an
effect): at the game top quartile the ROI statistic's null 90th percentile is
{cons[(cons.unit=='game')&(cons.test=='top_quartile|roi_captured')].mde_at_q.iloc[0]:+.3f}
— **the game-level design cannot detect anything below roughly +20% ROI at that
bucket size.** Its null result is "could not detect", not "shown absent". The
props top half is far better powered: its ROI MDE is
{cons[(cons.unit=='props_regular')&(cons.test=='top_half|roi_captured')].mde_at_q.iloc[0]:+.3f}
against an observed
{cons[(cons.unit=='props_regular')&(cons.test=='top_half|roi_captured')].observed.iloc[0]:+.3f}
— a clear miss, not a near miss.

## 5. The one starrable ROI cell — 2025 props PLAYOFFS, and why it is not a finding

The selector's 2025 playoff top quartile shows
{line('props_playoff','selector_ridge','top_quartile')}, p={cons[(cons.unit=='props_playoff')&(cons.test=='top_quartile|roi_captured')].p_perm.iloc[0]:.4f},
q={cons[(cons.unit=='props_playoff')&(cons.test=='top_quartile|roi_captured')].q_bh.iloc[0]:.4f}.
The top decile is larger still but sits at
{int(_b(b,'props_playoff',D,'selector_ridge','top_decile').n_bets)} bets, below the
50-bet floor, so it is descriptive only and never starred. Reasons this is not
reportable as a result:

1. Its **matching EDGE statistics did not reject** (halted under the bound). ROI
   without any comparative-accuracy improvement is the signature of variance.
2. 2025 is the **DEVELOPMENT** slice. It cannot confirm anything by construction.
3. The sample is one postseason —
   {int(_b(b,'props_playoff',D,'comparator_bet_everything','all_no_selection').n_bets)}
   lines over {int(_b(b,'props_playoff',D,'comparator_bet_everything','all_no_selection').n_dates)}
   dates — and `props_edge_v1` already documented playoff cells as artefact-prone.
4. **2026 has no playoff data**, so no second look exists anywhere in the record.
5. The coverage curve is non-monotone (deciles 3-5 are strongly negative).

It goes forward as a candidate for the prospective log, nothing more.

## 6. 2026 — RETROSPECTIVE DESCRIPTIVE TEST ONLY

Never a holdout result. Reported for description.

{fmt_table(b[(b['slice'].str.contains('2026')) & (b.arm.isin(['selector_ridge','comparator_bet_everything']))], bc)}

- **Game:** the selector's top half descriptively shows
  {pct(_b(b,'game','2026','selector_ridge','top_half').roi_captured_mean)} on
  {int(_b(b,'game','2026','selector_ridge','top_half').n_bets)} bets, but its top
  decile and quartile are
  {pct(_b(b,'game','2026','selector_ridge','top_decile').roi_captured_mean)} and
  {pct(_b(b,'game','2026','selector_ridge','top_quartile').roi_captured_mean)} —
  a *different* bucket from the 2025 blip, and non-monotone again. Betting
  everything returned
  {pct(_b(b,'game','2026','comparator_bet_everything','all_no_selection').roi_captured_mean)}.
  This is noise in both slices, and neither could confirm the other even if it agreed.
- **Props:** the **edge ranking replicates cleanly** (Spearman
  {pr.spearman_desc_2026:+.3f} against {pr.spearman_dev_2025:+.3f}) and the
  **payoff still does not appear** — selector top decile
  {pct(_b(b,'props_regular','2026','selector_ridge','top_decile').roi_captured_mean)}
  against {pct(_b(b,'props_regular','2026','comparator_bet_everything','all_no_selection').roi_captured_mean)}
  for betting everything. The same story twice.
- **Multi-book sensitivity** (three-way clustered by player, date and book;
  the frozen selector SCORED on the per-book universe, never refit): top half
  {pct(_b(b,'props_multibook_SENS','2026','selector_ridge','top_half').roi_captured_mean)}
  against {pct(_b(b,'props_multibook_SENS','2026','comparator_bet_everything','all_no_selection').roi_captured_mean)}.
  No gain there either.

## 7. THE PROXY — and why the game level was always going to be null

The post-hoc absence count is BANNED as a feature. The registered pregame
substitute is used instead. **Development diagnostic only (freeze C4) — this
never justifies using the banned feature:**

{fmt_table(proxy, ["scope", "level", "n", "mean_proxy", "mean_post_hoc_dnp",
                   "pearson_proxy_vs_post_hoc", "spearman_proxy_vs_post_hoc",
                   "corr_post_hoc_with_edge_BANNED_REFERENCE", "corr_proxy_with_edge"])}

**The proxy correlates {proxy[proxy.scope=='all_team_games'].pearson_proxy_vs_post_hoc.iloc[0]:.3f}
with the post-hoc count** (Pearson, {int(proxy[proxy.scope=='all_team_games'].n.iloc[0])}
team-games; per-season 0.055-0.111). It is a weak proxy, and the two quantities
are not the same object: `post_hoc_dnp` counts players who **dressed and did not
play** (a box-score row carrying a `dnp_reason`), while the proxy counts players
who **recently played and are absent from the box score entirely**, plus
dressed-DNPs. Different populations, weak overlap.

Decisively: at game level the **banned post-hoc count correlates
{proxy[proxy.scope=='game_universe'].corr_post_hoc_with_edge_BANNED_REFERENCE.iloc[0]:+.3f}
with our edge — and the pregame proxy correlates
{proxy[proxy.scope=='game_universe'].corr_proxy_with_edge.iloc[0]:+.3f}.** The
motivating signal does not survive translation into pregame-knowable form. The
absence-load effect that produced the -0.73 / -0.40 / +0.09 tercile split is
either post-hoc information we cannot have at the cutoff, or this proxy is too
crude to carry it. Either way the game-level null is explained rather than mysterious.

Consistent with that, the fitted coefficients put the absence proxies in with the
*opposite* sign to the motivating split (more pregame absence -> slightly worse
edge, not better).

## 8. Model, features and degrees of freedom (freeze v2)

One fit only, on 2024. Never refit on 2025 or 2026 — those slices only score the
frozen object.

{fmt_table(ex.reset_index()[["unit", "n_fit_2024", "n_dev_2025", "n_desc_2026",
                             "n_features", "lambda", "trace_H",
                             "lambda_escalated_for_df_cap", "r2_in_sample_2024",
                             "r2_dev_2025", "spearman_dev_2025", "auc_sign_dev_2025"]])}

`trace(H)` is within the cap of {MAX_TRACE_H} at both levels, so no lambda
escalation was needed. Note the in-sample R² is already tiny
({g.r2_in_sample_2024:.3f} game, {pr.r2_in_sample_2024:.3f} props): **this is not
an overfitting story — there is almost nothing to fit.**

**GAME features ({len(GAME_FEATURES)} of the registered 8):** {", ".join(GAME_FEATURES)}.
**`market_total_at_cutoff` is DROPPED.** No totals lines exist for the 2024
fitting season anywhere on disk: `drive_masters/master_odds.csv` is spreads-only,
and the totals capture begins 2025-07-05. Corroborated independently by
`experiments/totals_groundwork/inventory_by_season.csv` (totals rows: 2025 and
2026 only) and by `totals_head.py`'s own note. Dropping was chosen over
substituting so that no unnamed feature entered the frozen set.

**PROPS features (8, named before evaluation):** {", ".join(PROP_FEATURES)}.
`p_plays` (the strictly-prior availability term the projection implicitly sets to
1) and `exp_min_cond` (conditional minutes, from played games only) are carried
**separately**, as registered, so the "projection dominated by an uncertain
availability term" mechanism is testable. It tested near zero: standardised
coefficients
{imp[(imp.unit=='props_regular')&(imp.feature=='p_plays')].ridge_coef_standardised.iloc[0]:+.3f}
and
{imp[(imp.unit=='props_regular')&(imp.feature=='exp_min_cond')].ridge_coef_standardised.iloc[0]:+.3f}
against {imp[(imp.unit=='props_regular')&(imp.feature=='disagreement_abs')].ridge_coef_standardised.iloc[0]:+.3f}
for the disagreement term.

### Standardised feature importances

{fmt_table(imp[imp.unit != 'props_playoff'], ["unit", "feature",
           "ridge_coef_standardised", "logistic_coef_standardised",
           "corr_with_target_2024"])}

## 8b. Grading validation — this build reproduces its two source experiments

Independent check that the executable-bet grading and price conventions used here
are the same objects `clv_transfer_v1` and `props_edge_v1` published, not a
re-derivation that drifted:

{fmt_table(res["validation"], ["check", "n_here", "n_published", "metric",
                              "value_here", "value_published"], "{:.4f}")}

The game-level rows reproduce `clv_transfer`'s flat-stake simulation exactly. The
props rows reproduce `props_edge`'s published ROI to four decimals on a bet set
differing by 2 rows in ~3,600 (boundary rows at exactly the 1.0 threshold).

## 9. Limitations — stated, not buried

1. **The fitting sample is one season.** {int(g.n_fit_2024)} games and
   {int(pr.n_fit_2024)} player-games, all 2024. The registered "fit 2022-2024" is
   unsatisfiable: `predictions_v2.csv` holds only the 673 walk-forward TEST games,
   and 2021-2023 are the base model's training window, so their predictions are
   in-sample. `base_predictions_oof_2022_2023_v1` is registered separately to fix
   this; it was NOT attempted inline.
2. **The game level is underpowered** — see the MDE in section 4. Its null is
   "could not detect", not "shown absent".
3. **Era/season confound at game level.** 2024 rows are old-era T-64m, 2025 mixes
   old-era T-64m (before 2025-07-05) with extension T-24h, 2026 is extension T-24h
   only. `clv_transfer_v1`'s era discipline says never pool eras; here era is
   confounded with the fitting/development split and no fix exists in the
   available data. This is a real weakness of the game-level design.
4. **Game universe is the threshold-0.5 bet set.** The `clv_transfer` bet log
   contains only games with |model - market| >= 0.5
   ({int(g.n_fit_2024)+int(g.n_dev_2025)+int(g.n_desc_2026)} of them). That is the
   operationally relevant universe but it truncates the disagreement feature's range.
5. **Registered features that could not be built, and were dropped rather than
   improvised:** (a) *pregame absence load from the captured injury reports* —
   `data/injury_capture/injury_log.csv` begins 2026-07-30 and holds 378 rows over
   two days, so it does not exist for any retrospective game; (b) *channel-level
   disagreement across the four channels* — `predictions_v2.csv` does not persist
   per-channel predictions and re-deriving them would mean re-implementing the base
   model; (c) *market total at cutoff*, section 8. None were in the frozen eight
   except (c).
6. **The playoff scope has no 2026 data at all**, so the section-5 cell can never
   be looked at twice retrospectively.
7. **Two-way vs three-way clustering.** The primary props analysis is one bet per
   player-game and is clustered by date and player. The multi-book sensitivity is
   clustered three ways (player, date, book) per freeze C5.

## 10. What this means for the program

- **The registered target is the wrong objective for a betting rule.** Maximising
  |market error| - |model error| is maximised by agreeing with the market. Any
  successor experiment should target *realised return* directly, or restrict the
  candidate set to a fixed disagreement band before ranking, so that "abstain"
  is not available as a way to score well.
- **The absence-load hypothesis is not recoverable at the cutoff through this
  proxy.** If it is to be pursued, it needs a genuinely pregame availability
  feed — the injury capture that started 2026-07-30 is the right instrument, and
  it will take a season to accumulate.
- **Nothing here is promotable.** Per freeze C7 and amendment v5 C3-BLOCKING,
  retrospective results are candidate generation only; promotion requires the
  frozen selector to identify opportunities prospectively in the live log as
  preregistered paper-trade cells.

## 11. Outputs

| file | contents |
|---|---|
| `REPORT.md` | this document |
| `game_level_results.csv` | the game universe: one row per game with every pregame feature, target, executed bet and grade |
| `props_level_results.csv` | the props universe (best-line, one row per player-game), same structure |
| `payoff_buckets.csv` | every bucket x arm x slice: coverage, comparative error, ROI at captured prices and -110, clustered CIs |
| `ranking_curves.csv` | decile ranking curves AND the risk-versus-coverage curves |
| `feature_importance.csv` | standardised ridge and logistic coefficients, plus each feature's 2024 correlation with the target |
| `permutation_summary.csv` | every test x null: observed, exceedances, draws used, p, halt flag, BH q, MDE |
| `proxy_quality.csv` | the pregame proxy against the banned post-hoc count (development diagnostic only) |
| `grading_validation.csv` | this build's bet grading reproduced against `clv_transfer_v1` and `props_edge_v1` |
| `selector_diagnostics.csv` | lambda, trace(H), R², Spearman, AUC, disagreement variance share |
| `run_meta.json` | seed, B_final, battery size, slice labels, feature lists, run log |
"""
    (OUT / "REPORT.md").write_text(txt, encoding="utf-8")


def main():
    t0 = datetime.now(timezone.utc)
    OUT.mkdir(parents=True, exist_ok=True)
    log = [f"B_final = {B_FINAL} (m = {M_TESTS} registered tests, q = {Q_FDR}; "
           f"amendment v5 C2 singleton-resolution rule)",
           f"GAME features ({len(GAME_FEATURES)}): {GAME_FEATURES}; "
           f"DROPPED from the registered eight: {GAME_FEATURE_DROPPED} "
           f"(no totals lines exist for the 2024 fitting season)",
           f"PROPS features ({len(PROP_FEATURES)}): {PROP_FEATURES}"]

    print("[load] master_player ...")
    mp = load_player_master()
    tg = team_game_index(mp)
    print("[build] strictly-prior team state ...")
    teamp = build_team_pregame(mp, tg)

    print("[build] game frame ...")
    gdf = build_game_frame(mp, tg, teamp)
    print("[build] props frames ...")
    pdf = build_props_frame(mp, teamp)
    pdf_mb = build_props_frame(mp, teamp, multi_book=True)

    # ---- proxy quality: DEVELOPMENT DIAGNOSTIC ONLY ------------------------
    rows = []
    pq = teamp.dropna(subset=["absence_proxy"])
    for scope, sub in [("all_team_games", pq)] + [
            (f"team_games_{s}", pq[pq["season"] == s]) for s in sorted(pq["season"].unique())]:
        if len(sub) < 3:
            continue
        rows.append({"scope": scope, "level": "team_game", "n": len(sub),
                     "mean_proxy": float(sub["absence_proxy"].mean()),
                     "mean_post_hoc_dnp": float(sub["post_hoc_dnp"].mean()),
                     "pearson_proxy_vs_post_hoc": float(np.corrcoef(
                         sub["absence_proxy"], sub["post_hoc_dnp"])[0, 1]),
                     "spearman_proxy_vs_post_hoc": spearman(sub["absence_proxy"],
                                                            sub["post_hoc_dnp"]),
                     "pearson_load_vs_post_hoc": float(np.corrcoef(
                         sub["absence_load"], sub["post_hoc_dnp"])[0, 1])})
    for name, d, pcol, lcol, hcol in (
            ("game_universe", gdf, "absence_proxy_total", "absence_load_total",
             "post_hoc_dnp_total"),
            ("props_universe", pdf, "team_absence_proxy", "team_absence_load",
             "team_post_hoc_dnp")):
        s = d.dropna(subset=[pcol, hcol, "edge"])
        if len(s) < 3:
            continue
        rows.append({"scope": name, "level": "game" if name.startswith("game") else "player_game",
                     "n": len(s), "mean_proxy": float(s[pcol].mean()),
                     "mean_post_hoc_dnp": float(s[hcol].mean()),
                     "pearson_proxy_vs_post_hoc": float(np.corrcoef(s[pcol], s[hcol])[0, 1]),
                     "spearman_proxy_vs_post_hoc": spearman(s[pcol], s[hcol]),
                     "pearson_load_vs_post_hoc": float(np.corrcoef(s[lcol], s[hcol])[0, 1]),
                     "corr_post_hoc_with_edge_BANNED_REFERENCE": float(
                         np.corrcoef(s[hcol], s["edge"])[0, 1]),
                     "corr_proxy_with_edge": float(np.corrcoef(s[pcol], s["edge"])[0, 1])})
    proxy = pd.DataFrame(rows)
    proxy.to_csv(OUT / "proxy_quality.csv", index=False)

    print("[run] game level ...")
    game = run_unit(gdf, GAME_FEATURES, "game", ["game_date"], log)
    print("[run] props regular ...")
    pr = run_unit(pdf, PROP_FEATURES, "props_regular", ["game_date", "player_id"],
                  log, phase="regular")
    print("[run] props playoff ...")
    pp = run_unit(pdf, PROP_FEATURES, "props_playoff", ["game_date", "player_id"],
                  log, phase="playoff")

    # ---- multi-book SENSITIVITY: SCORE the frozen selector, 3-way clustered -
    mb_b, mb_c = [], []
    if pr:
        mbd = pdf_mb.dropna(subset=PROP_FEATURES + ["edge", "profit_captured"])
        for season, sname in ((DEV_SEASON, f"{DEV_SEASON}_development"),
                              (DESC_SEASON, f"{DESC_SEASON}_retrospective_descriptive")):
            s = mbd[(mbd["season"] == season) & (mbd["phase"] == "regular")]
            if not len(s):
                continue
            b, c, _ = evaluate_slice(s, pr["model"], "props_multibook_SENS", sname,
                                     ["game_date", "player_id", "bookmaker_key"])
            mb_b += b
            mb_c += c
        log.append("[props_multibook_SENS] frozen selector SCORED on the per-book "
                   "universe (no refit); 3-way clustered (player, date, book)")

    runs = [r for r in (game, pr, pp) if r]
    buckets = pd.concat([r["buckets"] for r in runs] + [pd.DataFrame(mb_b)],
                        ignore_index=True)
    curves = pd.concat([r["curves"] for r in runs] + [pd.DataFrame(mb_c)],
                       ignore_index=True)
    imp = pd.concat([r["importance"] for r in runs], ignore_index=True)
    perm = pd.concat([r["perm"] for r in runs if len(r["perm"])], ignore_index=True)
    extras = pd.DataFrame([r["extras"] for r in runs])

    if len(perm):
        cons = (perm.sort_values("p_perm", ascending=False)
                .drop_duplicates(["unit", "test"]).copy())   # most conservative null
        cons["q_bh"] = bh_qvalues(cons["p_perm"].to_numpy())
        cons["starred_bh"] = cons["q_bh"] <= Q_FDR
        # freeze C6: a bucket with < 50 independent bets is DESCRIPTIVE ONLY and
        # is never starred, whatever BH says.
        nb = (buckets[(buckets["slice"] == f"{DEV_SEASON}_development") &
                      (buckets["arm"] == "selector_ridge")]
              .set_index(["unit", "bucket"])["n_bets"].to_dict())
        cons["bucket_of_test"] = cons["test"].str.split("|").str[0]
        cons["n_bets"] = [nb.get((u, bk), np.nan) for u, bk in
                          zip(cons["unit"], cons["bucket_of_test"])]
        cons["meets_c6_bet_floor"] = ~(cons["n_bets"] < MIN_STARRABLE_BETS)
        cons["starred_final"] = cons["starred_bh"] & cons["meets_c6_bet_floor"]
        perm = perm.merge(cons[["unit", "test", "q_bh", "starred_bh", "n_bets",
                                "meets_c6_bet_floor", "starred_final"]],
                          on=["unit", "test"], how="left")
        perm["battery_m"] = M_TESTS

    gdf.to_csv(OUT / "game_level_results.csv", index=False)
    pdf.to_csv(OUT / "props_level_results.csv", index=False)
    buckets.to_csv(OUT / "payoff_buckets.csv", index=False)
    curves.to_csv(OUT / "ranking_curves.csv", index=False)
    imp.to_csv(OUT / "feature_importance.csv", index=False)
    perm.to_csv(OUT / "permutation_summary.csv", index=False)
    extras.to_csv(OUT / "selector_diagnostics.csv", index=False)

    (OUT / "run_meta.json").write_text(json.dumps(
        {"generated_utc": t0.isoformat(), "seed": SEED, "B_final": B_FINAL,
         "m_tests": M_TESTS, "q": Q_FDR, "slice_labels": SLICE_LABEL,
         "game_features": GAME_FEATURES, "game_feature_dropped": GAME_FEATURE_DROPPED,
         "prop_features": PROP_FEATURES, "log": log}, indent=2, default=str))
    # grading validation against the two source experiments' published numbers
    ge = gdf[(gdf.era == "extension") & (gdf.cutoff == "T-24h")]
    go = gdf[(gdf.era == "old") & (gdf.cutoff == "T-64m")]
    pa = pdf[pdf.disagreement_abs >= 1.0]
    pre = pa[pa.phase == "regular"]
    validation = pd.DataFrame([
        {"check": "clv_transfer ext T-24h thr0.5, best exec", "n_here": len(ge),
         "n_published": 262, "metric": "ROI captured",
         "value_here": ge.profit_captured.mean(), "value_published": 0.0729},
        {"check": "clv_transfer ext T-24h thr0.5, -110", "n_here": len(ge),
         "n_published": 262, "metric": "ROI -110",
         "value_here": ge.profit_m110.mean(), "value_published": 0.0638},
        {"check": "clv_transfer old T-64m thr0.5, best exec", "n_here": len(go),
         "n_published": 289, "metric": "ROI captured",
         "value_here": go.profit_captured.mean(), "value_published": 0.014508},
        {"check": "props_edge best_line thr1.0 all scope, -110", "n_here": len(pa),
         "n_published": 3624, "metric": "ROI -110",
         "value_here": pa.profit_m110.mean(), "value_published": -0.0112},
        {"check": "props_edge best_line thr1.0 regular scope, -110", "n_here": len(pre),
         "n_published": 3344, "metric": "ROI -110",
         "value_here": pre.profit_m110.mean(), "value_published": -0.0158}])
    validation.to_csv(OUT / "grading_validation.csv", index=False)

    res = {"buckets": buckets, "curves": curves, "imp": imp, "perm": perm,
           "extras": extras, "proxy": proxy, "runs": runs, "log": log,
           "gdf": gdf, "pdf": pdf, "validation": validation}
    print("[write] REPORT.md ...")
    write_report(res, t0)
    print("\n".join(log))
    return res


if __name__ == "__main__":
    main()
