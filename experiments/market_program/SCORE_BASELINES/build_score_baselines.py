"""SCORE_BASELINES -- D043 score-family composite baselines.

Authorities (BINDING): D043_CYCLE2_SCORE_AND_EFFICIENCY and
D036_SCOREBOARD_MEASUREMENT_SEMANTICS, both in
experiments/player_program/orchestration/DECISION_LEDGER.jsonl.

What this node builds (D043 item 1, the IMMEDIATE no-gate mandate):
composite naive baselines for game total, margin and win probability --
the VERIFIED incumbent pace ingredient (team_possession_prior_v1's
projected_team_off_possessions, the frozen trailing-window champion that
survived the P40 challenger sweep) times strictly-lagged efficiency
(points-per-possession EWMAs, offense and defense), plus two simpler
baselines -- evaluated walk-forward with D036 provenance, and compared to
the measured market bars on the MATCHED universe only.

EVIDENCE CLASS: COMPOSITE_BASELINE, with NAIVE_BASELINE semantics per
D036 point 6 -- these are honest floors every future score-family model
must beat, never tuned models, never market-timing claims. Nothing here
is fitted to the evaluation data except the win-probability logistic,
which is calibrated ONLY on strictly-prior seasons (walk-forward, never
pooled) and is therefore itself strictly out-of-sample.

STRICT LAG: every input to a predicted game comes from games on strictly
earlier calendar dates. Cold-start rules and exclusion counts are stated
in the outputs, never silently dropped.

This node NEVER touches experiments/player_program/stage2b/SEALED_RESULTS.
No git, no network, no subagents. Stdlib + pandas + numpy + pyarrow only,
plus read-only reuse of BOOKIE_BASELINE's frozen join and M11's frozen
de-vig machinery (never reimplemented).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program")
OUT_DIR = ROOT / "experiments/market_program/SCORE_BASELINES"

MASTER_TEAM_PATH = ROOT / "data/masters/master_team.parquet"
PACE_PRIOR_PATH = ROOT / "experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet"
POSSESSIONS_PATH = ROOT / "experiments/player_program/possessions_v2/possessions_raw_v2.parquet"
BOOKIE_DIR = ROOT / "experiments/market_program/BOOKIE_BASELINE"
BOOKIE_METRICS_PATH = BOOKIE_DIR / "baseline_metrics.json"

# ---------------------------------------------------------------------------
# Frozen conventions -- PICKED ONCE, documented here, mirrored in TESTS.py.
# ---------------------------------------------------------------------------
EFF_EWMA_SPAN = 10          # simple span; alpha = 2/(span+1). Chosen to echo
                            # the incumbent pace WINDOW_K=10 flavour. This is
                            # the ONE picked efficiency convention (D043 asked
                            # for K=200-style shrinkage OR a simple span; we
                            # picked the simple span, no shrinkage). BASELINE,
                            # not a tuned model -- the span was not searched.
EFF_ALPHA = 2.0 / (EFF_EWMA_SPAN + 1.0)
EFF_MIN_HISTORY = 3         # >=3 strictly-prior games per team required to
                            # emit an efficiency EWMA (mirrors the incumbent
                            # MIN_HISTORY_M=3); efficiency history is
                            # CONTINUOUS ACROSS SEASONS (a deliberate,
                            # documented simplification vs the incumbent
                            # pace prior's same-season-first windows).
BLEND = 0.5                 # simple average of own-offense and opponent-defense
Z95 = 1.959963984540054     # normal 97.5% quantile for 95% CIs

# D043's measured market bars (LATE cross_book pooled, BOOKIE_BASELINE):
D043_MARKET_BARS = {"spread_mae": 9.70, "total_mae": 13.74, "brier": 0.202}

MODEL_VERSIONS = {
    "composite": "composite_pace_x_eff_v1",
    "league_avg": "league_average_v1",
    "team_avg": "team_scoring_avg_v1",
}

EVIDENCE_CLASS = "COMPOSITE_BASELINE"
EVIDENCE_CLASS_SEMANTICS = (
    "COMPOSITE_BASELINE carries NAIVE_BASELINE semantics per D036 point 6: "
    "an untuned, strictly-lagged floor computed from owned data, never a "
    "fitted model, never predictive evidence for any challenger. It exists "
    "so every future score-family model has an honest number to beat."
)


# ---------------------------------------------------------------------------
# Small numeric machinery (each function has known-answer fixtures in TESTS.py)
# ---------------------------------------------------------------------------

def lagged_ewma(values, alpha=EFF_ALPHA):
    """EWMA over `values` (oldest first), recursive form:
    e_1 = v_1; e_k = alpha*v_k + (1-alpha)*e_{k-1}. Returns None if empty."""
    e = None
    for v in values:
        e = v if e is None else alpha * v + (1.0 - alpha) * e
    return e


def clustered_mean_ci(x, clusters):
    """Mean of x with a game-date-clustered 95% CI (CR1 sandwich for the
    mean: var = G/(G-1) * sum_d T_d^2 / N^2, T_d = within-cluster sum of
    (x_i - mean)). Returns (mean, half_width, n, n_clusters)."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n == 0:
        return None, None, 0, 0
    m = float(x.mean())
    sums = defaultdict(float)
    for xi, c in zip(x, clusters):
        sums[c] += xi - m
    g = len(sums)
    if g <= 1:
        return m, None, n, g
    var = (g / (g - 1.0)) * sum(t * t for t in sums.values()) / (n * n)
    return m, Z95 * math.sqrt(var), n, g


def metric_block(errs, dates):
    """MAE / RMSE / bias with clustered CIs for a list of signed errors."""
    errs = np.asarray(errs, dtype=float)
    if len(errs) == 0:
        return None
    mae, mae_hw, n, g = clustered_mean_ci(np.abs(errs), dates)
    bias, bias_hw, _, _ = clustered_mean_ci(errs, dates)
    mse, mse_hw, _, _ = clustered_mean_ci(errs ** 2, dates)
    rmse = math.sqrt(mse)
    rmse_ci = None
    if mse_hw is not None:
        rmse_ci = [math.sqrt(max(mse - mse_hw, 0.0)), math.sqrt(mse + mse_hw)]
    return {
        "mae": mae, "mae_ci95": [mae - mae_hw, mae + mae_hw] if mae_hw is not None else None,
        "rmse": rmse, "rmse_ci95": rmse_ci,
        "bias": bias, "bias_ci95": [bias - bias_hw, bias + bias_hw] if bias_hw is not None else None,
        "n": int(n), "n_date_clusters": int(g),
    }


def prob_block(probs, ys, dates, n_bins=10):
    """Brier / log-loss / 10-bin calibration with clustered CIs."""
    probs = np.asarray(probs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    if len(probs) == 0:
        return None
    sq = (probs - ys) ** 2
    eps = 1e-12
    p = np.clip(probs, eps, 1 - eps)
    ll = -(ys * np.log(p) + (1 - ys) * np.log(1 - p))
    brier, b_hw, n, g = clustered_mean_ci(sq, dates)
    logloss, l_hw, _, _ = clustered_mean_ci(ll, dates)
    table = []
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        mask = (probs >= lo) & (probs < hi) if i < n_bins - 1 else (probs >= lo)
        nb = int(mask.sum())
        table.append({
            "bin": f"[{lo:.1f},{hi:.1f})", "n": nb,
            "mean_predicted_p_home": float(probs[mask].mean()) if nb else None,
            "empirical_home_win_rate": float(ys[mask].mean()) if nb else None,
        })
    return {
        "brier": brier, "brier_ci95": [brier - b_hw, brier + b_hw] if b_hw is not None else None,
        "log_loss": logloss, "log_loss_ci95": [logloss - l_hw, logloss + l_hw] if l_hw is not None else None,
        "n": int(n), "n_date_clusters": int(g),
        "calibration_10bin": table,
    }


def fit_logistic_1d(margins, ys, max_iter=200, tol=1e-10, ridge=1e-9):
    """Two-parameter logistic p = sigmoid(b0 + b1*margin) via Newton/IRLS.
    Deterministic; tiny ridge for numerical stability only. Known-answer
    fixture in TESTS.py."""
    X = np.column_stack([np.ones(len(margins)), np.asarray(margins, float)])
    y = np.asarray(ys, float)
    beta = np.zeros(2)
    for _ in range(max_iter):
        z = X @ beta
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))
        w = np.maximum(p * (1 - p), 1e-12)
        grad = X.T @ (y - p) - ridge * beta
        H = (X * w[:, None]).T @ X + ridge * np.eye(2)
        step = np.linalg.solve(H, grad)
        beta = beta + step
        if float(np.abs(step).max()) < tol:
            break
    return beta


def apply_logistic(beta, margins):
    z = beta[0] + beta[1] * np.asarray(margins, float)
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 1. Load the owned game universe (one row per game, home perspective)
# ---------------------------------------------------------------------------

def load_games():
    mt = pd.read_parquet(MASTER_TEAM_PATH)
    home = mt[mt["is_home"] == 1][[
        "game_id", "game_date", "season", "season_type",
        "team_id", "team_abbreviation", "opp_team_id", "opp_team_abbreviation",
        "pts", "opp_pts",
    ]].rename(columns={
        "team_id": "home_team_id", "team_abbreviation": "home_abbr",
        "opp_team_id": "away_team_id", "opp_team_abbreviation": "away_abbr",
        "pts": "home_pts", "opp_pts": "away_pts",
    }).copy()
    home["game_date"] = pd.to_datetime(home["game_date"])
    home["actual_total"] = home["home_pts"] + home["away_pts"]
    home["actual_margin"] = home["home_pts"] - home["away_pts"]
    home["y_home_win"] = (home["home_pts"] > home["away_pts"]).astype(float)
    home = home.sort_values(["game_date", "game_id"]).reset_index(drop=True)
    return home


# ---------------------------------------------------------------------------
# 2. Realized per-team-game possessions and points-per-possession
# ---------------------------------------------------------------------------

def load_realized_ppp(games):
    """Per (game_id, team_id): raw offensive possession count from the owned
    possession stream (possessions_raw_v2, includes OT possessions) and
    ppp = box-score points / raw offensive possessions. The numerator is the
    BOX final score (what we predict); the denominator is the possession
    stream count -- the same stream the incumbent pace prior was built from,
    so the pace x ppp product is scale-consistent with the pace ingredient."""
    poss = pd.read_parquet(POSSESSIONS_PATH, columns=["game_id", "offense_team_id"])
    n_off = (poss.groupby(["game_id", "offense_team_id"]).size()
             .rename("n_off_poss").reset_index()
             .rename(columns={"offense_team_id": "team_id"}))

    mt = pd.read_parquet(MASTER_TEAM_PATH)[
        ["game_id", "team_id", "game_date", "pts", "opp_pts"]].copy()
    mt["team_id"] = mt["team_id"].astype("int64")
    mt["game_date"] = pd.to_datetime(mt["game_date"])
    tg = mt.merge(n_off, on=["game_id", "team_id"], how="left", validate="1:1")

    missing = tg["n_off_poss"].isna()
    n_missing = int(missing.sum())
    tg = tg[~missing].copy()

    # opponent's offensive possession count in the same game = this team's
    # defensive possessions faced
    opp = tg[["game_id", "team_id", "n_off_poss"]].rename(columns={
        "team_id": "opp_team_id_join", "n_off_poss": "n_def_poss"})
    tg = tg.merge(opp, left_on="game_id", right_on="game_id", how="left")
    tg = tg[tg["team_id"] != tg["opp_team_id_join"]].drop(columns=["opp_team_id_join"])

    tg["ppp_off"] = tg["pts"] / tg["n_off_poss"]
    tg["ppp_def"] = tg["opp_pts"] / tg["n_def_poss"]
    return tg.sort_values(["team_id", "game_date", "game_id"]).reset_index(drop=True), n_missing


def build_eff_ewmas(tg):
    """Strictly-lagged efficiency EWMAs. For each team-game: EWMA (span
    EFF_EWMA_SPAN) of ppp_off and ppp_def over the team's games on STRICTLY
    EARLIER calendar dates, continuous across seasons; None until
    EFF_MIN_HISTORY prior games exist. Returns dict
    (game_id, team_id) -> (off_ewma, def_ewma, n_prior) or None fields."""
    out = {}
    for team_id, sub in tg.groupby("team_id", sort=True):
        sub = sub.sort_values(["game_date", "game_id"])
        dates = sub["game_date"].to_list()
        offs = sub["ppp_off"].to_list()
        defs = sub["ppp_def"].to_list()
        gids = sub["game_id"].to_list()
        for i in range(len(sub)):
            # strictly earlier DATES (never same-day info; matches the
            # incumbent pace prior's d < game_date convention)
            prior_idx = [j for j in range(len(sub)) if dates[j] < dates[i]]
            n_prior = len(prior_idx)
            if n_prior >= EFF_MIN_HISTORY:
                off_e = lagged_ewma([offs[j] for j in prior_idx])
                def_e = lagged_ewma([defs[j] for j in prior_idx])
            else:
                off_e = def_e = None
            out[(gids[i], team_id)] = (off_e, def_e, n_prior)
    return out


# ---------------------------------------------------------------------------
# 3. The three baselines, strictly lagged
# ---------------------------------------------------------------------------

def build_composite(games, pace, eff):
    """predicted score = incumbent projected game pace x blended efficiency.
    Blend = simple average of own offense EWMA and opponent defense EWMA."""
    pace_by_game = {}
    for r in pace.drop_duplicates("game_id").itertuples(index=False):
        pace_by_game[r.game_id] = (
            r.projected_team_off_possessions if r.pace_resolved else None)

    rows, excl = [], Counter()
    for g in games.itertuples(index=False):
        p = pace_by_game.get(g.game_id)
        if p is None or (isinstance(p, float) and math.isnan(p)):
            excl["PACE_UNRESOLVED_NO_PRIOR_GAMES"] += 1
            continue
        h = eff.get((g.game_id, int(g.home_team_id)))
        a = eff.get((g.game_id, int(g.away_team_id)))
        if h is None or a is None:
            excl["TEAM_MISSING_FROM_POSSESSION_STREAM"] += 1
            continue
        h_off, h_def, _ = h
        a_off, a_def, _ = a
        if h_off is None or a_off is None:
            excl["EFF_HISTORY_LT_%d_PRIOR_GAMES" % EFF_MIN_HISTORY] += 1
            continue
        home_score = p * (BLEND * h_off + (1 - BLEND) * a_def)
        away_score = p * (BLEND * a_off + (1 - BLEND) * h_def)
        rows.append({
            "game_id": g.game_id, "pred_home": home_score, "pred_away": away_score,
            "pred_total": home_score + away_score,
            "pred_margin": home_score - away_score,
        })
    return pd.DataFrame(rows), excl


def build_league_average(games):
    """League-average baseline: predicted total / margin / home win prob =
    the strictly-lagged expanding league means (all games on strictly
    earlier dates, continuous across seasons). The margin mean IS the
    league home-court advantage; the win prob is the lagged home win rate.
    Cold start: the first game date in the data has no prior games ->
    excluded and counted."""
    by_date = games.groupby("game_date").agg(
        total_sum=("actual_total", "sum"),
        margin_sum=("actual_margin", "sum"),
        win_sum=("y_home_win", "sum"),
        n=("game_id", "size"),
    ).sort_index()
    cum_n = by_date["n"].cumsum().shift(1)
    lag_total = by_date["total_sum"].cumsum().shift(1) / cum_n
    lag_margin = by_date["margin_sum"].cumsum().shift(1) / cum_n
    lag_winrate = by_date["win_sum"].cumsum().shift(1) / cum_n

    rows, excl = [], Counter()
    for g in games.itertuples(index=False):
        t = lag_total.get(g.game_date)
        if t is None or pd.isna(t):
            excl["NO_PRIOR_LEAGUE_GAMES"] += 1
            continue
        rows.append({
            "game_id": g.game_id, "pred_total": float(t),
            "pred_margin": float(lag_margin.get(g.game_date)),
            "p_home": float(lag_winrate.get(g.game_date)),
        })
    return pd.DataFrame(rows), excl


def build_team_avg(games, mt=None):
    """Team season-to-date scoring-average baseline, NO pace decomposition:
    predicted home score = mean(home team's season-to-date points scored,
    away team's season-to-date points allowed); away analogously.
    Cold start: each team needs >=1 same-season game on a strictly earlier
    date; otherwise excluded and counted. `mt` is injectable for fixtures."""
    if mt is None:
        mt = pd.read_parquet(MASTER_TEAM_PATH)
    mt = mt[["game_id", "team_id", "season", "game_date", "pts", "opp_pts"]].copy()
    mt["team_id"] = mt["team_id"].astype("int64")
    mt["game_date"] = pd.to_datetime(mt["game_date"])
    mt = mt.sort_values(["team_id", "game_date", "game_id"])

    hist = {}
    for (team_id, season), sub in mt.groupby(["team_id", "season"], sort=True):
        hist[(team_id, season)] = list(zip(
            sub["game_date"], sub["pts"].astype(float), sub["opp_pts"].astype(float)))

    def s2d(team_id, season, date):
        h = [(p, o) for (d, p, o) in hist.get((team_id, season), []) if d < date]
        if not h:
            return None
        return (sum(p for p, _ in h) / len(h), sum(o for _, o in h) / len(h))

    rows, excl = [], Counter()
    for g in games.itertuples(index=False):
        hs = s2d(int(g.home_team_id), int(g.season), g.game_date)
        as_ = s2d(int(g.away_team_id), int(g.season), g.game_date)
        if hs is None or as_ is None:
            excl["NO_SAME_SEASON_PRIOR_GAME_EITHER_TEAM"] += 1
            continue
        h_for, h_against = hs
        a_for, a_against = as_
        home_score = 0.5 * (h_for + a_against)
        away_score = 0.5 * (a_for + h_against)
        rows.append({
            "game_id": g.game_id, "pred_home": home_score, "pred_away": away_score,
            "pred_total": home_score + away_score,
            "pred_margin": home_score - away_score,
        })
    return pd.DataFrame(rows), excl


# ---------------------------------------------------------------------------
# 4. Walk-forward win-probability calibration (strictly-prior seasons only)
# ---------------------------------------------------------------------------

def walkforward_winprob(df, games):
    """For each season S with at least one strictly-prior season of predicted
    margins, fit logistic(margin) on ALL seasons < S and apply to season S.
    NEVER pooled, NEVER same-season. Seasons with no prior seasons (2021)
    get no win probability -- counted as a stated exclusion."""
    d = df.merge(games[["game_id", "season", "y_home_win"]], on="game_id",
                 how="left", validate="1:1")
    seasons = sorted(d["season"].unique())
    p_home = pd.Series(np.nan, index=d.index)
    fits = {}
    for s in seasons:
        train = d[d["season"] < s]
        if len(train) == 0:
            fits[int(s)] = None
            continue
        beta = fit_logistic_1d(train["pred_margin"].to_numpy(),
                               train["y_home_win"].to_numpy())
        fits[int(s)] = {"intercept": float(beta[0]), "slope": float(beta[1]),
                        "n_train": int(len(train)),
                        "train_seasons": sorted(int(x) for x in train["season"].unique())}
        mask = d["season"] == s
        p_home[mask] = apply_logistic(beta, d.loc[mask, "pred_margin"].to_numpy())
    d["p_home"] = p_home
    return d[["game_id", "p_home"]], fits


# ---------------------------------------------------------------------------
# 5. Evaluation
# ---------------------------------------------------------------------------

def evaluate(df, games, has_scores):
    """Per-season + pooled metric blocks for one method's prediction frame
    (columns: game_id, pred_total, pred_margin, optional p_home)."""
    d = df.merge(games, on="game_id", how="left", validate="1:1")
    d["date_str"] = d["game_date"].dt.strftime("%Y-%m-%d")
    out = {}
    buckets = [("POOLED", d)] + [(int(s), d[d["season"] == s])
                                 for s in sorted(d["season"].unique())]
    for name, sub in buckets:
        if len(sub) == 0:
            continue
        blk = {
            "n_games": int(len(sub)),
            "date_range": [sub["date_str"].min(), sub["date_str"].max()],
            "total": metric_block((sub["pred_total"] - sub["actual_total"]).to_numpy(),
                                  sub["date_str"].to_numpy()),
            "margin": metric_block((sub["pred_margin"] - sub["actual_margin"]).to_numpy(),
                                   sub["date_str"].to_numpy()),
        }
        if "p_home" in sub.columns:
            wp = sub[sub["p_home"].notna()]
            blk["win_prob"] = (prob_block(wp["p_home"].to_numpy(),
                                          wp["y_home_win"].to_numpy(),
                                          wp["date_str"].to_numpy())
                               if len(wp) else None)
            blk["n_win_prob_excluded_no_prior_season_calibration"] = int(
                sub["p_home"].isna().sum())
        out[str(name)] = blk
    return out


# ---------------------------------------------------------------------------
# 6. Market comparison on the MATCHED universe (reuses BOOKIE_BASELINE's
#    frozen join, read-only; LATE snapshot class; cross_book consensus)
# ---------------------------------------------------------------------------

def load_market_matched():
    sys.path.insert(0, str(BOOKIE_DIR))
    import build_baseline as bb  # noqa: E402  (read-only reuse; main() NOT run)

    mt, by_pair = bb.load_outcomes()
    per_game, _ = bb.load_archive()

    market = {}
    for gid, rec in per_game.items():
        meta = rec["meta"]
        home, away = meta["home_team"], meta["away_team"]
        home_abbrs = bb.NAME_TO_ABBR.get(home)
        away_abbrs = bb.NAME_TO_ABBR.get(away)
        if not home_abbrs or not away_abbrs:
            continue
        ct = bb.parse_dt(meta["commence_time"])
        et_date = (ct - dt.timedelta(hours=bb.ET_OFFSET_HOURS)).date()
        row, reason = bb.match_outcome(home_abbrs, away_abbrs, et_date, by_pair)
        if row is None:
            continue
        snap = rec["snaps"].get("LATE")
        if snap is None:
            continue

        # cross_book moneyline via M11 (identical to build_baseline.main)
        h2h = bb.extract_market(snap, "h2h", home, away)
        per_book = []
        for book, q in h2h.items():
            try:
                quote = bb.m11.make_quote(
                    bookmaker=book, price=q["home_price"],
                    capture_ts=snap["retrieval_ts"], tier="T1",
                    vendor_ts=snap["vendor_snapshot_ts"],
                    vendor_ts_semantics=snap["vendor_ts_semantics"],
                    market="h2h", outcome="HOME")
                quote["opposite_price"] = q["away_price"]
                per_book.append(quote)
            except Exception:
                continue
        p_home = None
        if per_book:
            c = bb.m11.consensus_fair_value(per_book, allow_t1=True, game_id=gid)
            p_home = c["consensus_fair_prob"] if c else None

        sp = bb.extract_market(snap, "spreads", home, away)
        pts = [q["home_point"] for q in sp.values() if q.get("home_point") is not None]
        pred_margin = -(sum(pts) / len(pts)) if pts else None

        tt = bb.extract_market(snap, "totals", home, away)
        tps = [q["point"] for q in tt.values() if q.get("point") is not None]
        pred_total = sum(tps) / len(tps) if tps else None

        market[row.game_id] = {
            "market_p_home": p_home, "market_margin": pred_margin,
            "market_total": pred_total, "archive_game_id": gid,
        }
    caveat = {"caveat_text": bb.CAVEAT_TEXT, "caveat_sha256": bb.CAVEAT_SHA256}
    return market, caveat


def paired_comparison(comp_eval_frame, market):
    """Paired composite-vs-market differences per metric on the intersection
    of (matched archive games with a LATE cross_book quote) and (games the
    composite covers). Deltas are composite - market: negative = composite
    better on error metrics."""
    d = comp_eval_frame.copy()
    d["date_str"] = d["game_date"].dt.strftime("%Y-%m-%d")

    rows = []
    for g in d.itertuples(index=False):
        m = market.get(g.game_id)
        if m is None:
            continue
        rows.append({
            "game_id": g.game_id, "date_str": g.date_str, "season": int(g.season),
            "comp_margin_err": g.pred_margin - g.actual_margin,
            "comp_total_err": g.pred_total - g.actual_total,
            "comp_p_home": g.p_home if not pd.isna(g.p_home) else None,
            "mkt_margin_err": (m["market_margin"] - g.actual_margin)
                if m["market_margin"] is not None else None,
            "mkt_total_err": (m["market_total"] - g.actual_total)
                if m["market_total"] is not None else None,
            "mkt_p_home": m["market_p_home"],
            "y": g.y_home_win,
        })
    pr = pd.DataFrame(rows)

    def paired(metric_comp, metric_mkt, transform):
        sub = pr[pr[metric_comp].notna() & pr[metric_mkt].notna()]
        if len(sub) == 0:
            return None
        a = transform(sub[metric_comp].to_numpy(), sub["y"].to_numpy())
        b = transform(sub[metric_mkt].to_numpy(), sub["y"].to_numpy())
        delta, hw, n, g = clustered_mean_ci(a - b, sub["date_str"].to_numpy())
        return {
            "composite": float(a.mean()), "market": float(b.mean()),
            "paired_delta_composite_minus_market": delta,
            "paired_delta_ci95": [delta - hw, delta + hw] if hw is not None else None,
            "n_pairs": int(n), "n_date_clusters": int(g),
            "date_range": [sub["date_str"].min(), sub["date_str"].max()],
            "seasons": sorted(int(s) for s in sub["season"].unique()),
        }

    abs_err = lambda e, y: np.abs(e)
    sq_err = lambda e, y: e ** 2
    brier_t = lambda p, y: (p - y) ** 2
    eps = 1e-12
    ll_t = lambda p, y: -(y * np.log(np.clip(p, eps, 1 - eps))
                          + (1 - y) * np.log(np.clip(1 - p, eps, 1 - eps)))

    return {
        "margin_mae": paired("comp_margin_err", "mkt_margin_err", abs_err),
        "margin_mse": paired("comp_margin_err", "mkt_margin_err", sq_err),
        "total_mae": paired("comp_total_err", "mkt_total_err", abs_err),
        "total_mse": paired("comp_total_err", "mkt_total_err", sq_err),
        "winprob_brier": paired("comp_p_home", "mkt_p_home", brier_t),
        "winprob_log_loss": paired("comp_p_home", "mkt_p_home", ll_t),
    }, pr


# ---------------------------------------------------------------------------
# 7. Main
# ---------------------------------------------------------------------------

def main():
    generated = dt.datetime.now(dt.timezone.utc).isoformat()
    games = load_games()
    pace = pd.read_parquet(PACE_PRIOR_PATH)
    tg, n_poss_missing = load_realized_ppp(games)
    eff = build_eff_ewmas(tg)

    # pace ingredient coverage, documented per D043
    per_game_pace = pace.drop_duplicates("game_id")
    pace_coverage = {
        "team_game_rows": int(len(pace)),
        "team_game_rows_resolved": int(pace["pace_resolved"].sum()),
        "games": int(len(per_game_pace)),
        "games_resolved": int(per_game_pace["pace_resolved"].sum()),
        "pace_source_counts": {k: int(v) for k, v in
                               pace["pace_source"].value_counts().items()},
        "note": ("projected_team_off_possessions is GAME-level (mean of the two "
                 "sides' trailing-window estimates) and identical on both team "
                 "rows; unresolved only where neither team nor the league has "
                 "any strictly-prior game (the first game date of 2021). No "
                 "EWMA reconstruction is possible for those games -- zero "
                 "history exists -- so they are excluded and counted."),
    }

    comp, comp_excl = build_composite(games, pace, eff)
    lg, lg_excl = build_league_average(games)
    ta, ta_excl = build_team_avg(games)

    comp_p, comp_fits = walkforward_winprob(comp, games)
    comp = comp.merge(comp_p, on="game_id", validate="1:1")
    ta_p, ta_fits = walkforward_winprob(ta, games)
    ta = ta.merge(ta_p, on="game_id", validate="1:1")
    # league-average baseline's win prob is the lagged home win rate itself

    results = {
        "composite": evaluate(comp, games, True),
        "league_avg": evaluate(lg, games, False),
        "team_avg": evaluate(ta, games, True),
    }

    # ---- matched-universe market comparison ----
    market, caveat = load_market_matched()
    comp_full = comp.merge(games, on="game_id", how="left", validate="1:1")
    paired, paired_rows = paired_comparison(comp_full, market)
    n_market_late = len(market)
    n_market_with_composite = int(paired_rows["game_id"].nunique()) if len(paired_rows) else 0

    # ---- provenance ----
    inputs = {
        "master_team": {"path": "data/masters/master_team.parquet",
                        "sha256": sha256_file(MASTER_TEAM_PATH),
                        "rows": int(len(pd.read_parquet(MASTER_TEAM_PATH)))},
        "team_possession_prior_v1": {
            "path": "experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet",
            "sha256": sha256_file(PACE_PRIOR_PATH), "rows": int(len(pace)),
            "role": "VERIFIED incumbent pace ingredient (D042 champion), consumed as-is"},
        "possessions_raw_v2": {
            "path": "experiments/player_program/possessions_v2/possessions_raw_v2.parquet",
            "sha256": sha256_file(POSSESSIONS_PATH),
            "role": "realized offensive possession counts (PPP denominators)"},
        "bookie_baseline_metrics": {
            "path": "experiments/market_program/BOOKIE_BASELINE/baseline_metrics.json",
            "sha256": sha256_file(BOOKIE_METRICS_PATH),
            "role": "frozen market bars + join conventions (read-only reuse)"},
    }

    conventions = {
        "pace_ingredient": {
            "source": "team_possession_prior_v1.projected_team_off_possessions",
            "status": "VERIFIED (P40-adjudicated incumbent champion, D042)",
            "definition": ("game-level regulation-equivalent offensive possessions per "
                           "side: mean of the two teams' trailing WINDOW_K=10 same-season "
                           "window means (prior-season window, then strictly-lagged "
                           "league mean, as receipted fallbacks)"),
            "coverage": pace_coverage,
        },
        "efficiency_ingredient": {
            "definition": ("strictly-lagged EWMA of points-per-possession scored "
                           "(offense) and allowed (defense) per team; "
                           "ppp = box-score points / raw offensive-possession count "
                           "from possessions_raw_v2 (both include OT, so ppp is a "
                           "true rate)"),
            "ewma_span": EFF_EWMA_SPAN, "ewma_alpha": EFF_ALPHA,
            "shrinkage": ("NONE -- the picked convention is the simple span, not "
                          "K=200-style shrinkage (D043 offered either; one was "
                          "picked and is documented here; the span was NOT tuned)"),
            "history": ("continuous across seasons, strictly earlier calendar "
                        "dates only; minimum %d prior games else excluded"
                        % EFF_MIN_HISTORY),
        },
        "composite": ("predicted team score = pace x (%.1f*own_off_ewma + %.1f*"
                      "opp_def_ewma); total = sum of sides; margin = home - away. "
                      "NO home-court-advantage term by construction -- the margin "
                      "bias this creates is reported, not hidden."
                      % (BLEND, 1 - BLEND)),
        "win_prob": ("logistic(intercept + slope*pred_margin), fitted ONLY on "
                     "strictly-prior seasons, walk-forward, never pooled; 2021 has "
                     "no prior season and gets no win probability"),
        "ot_note": ("predicted scores are regulation-equivalent (the pace "
                    "ingredient is reg-equivalent); realized totals include OT "
                    "points, contributing a small negative total bias shared by "
                    "all pace-based rows"),
        "ci": ("95% CIs are game-date-clustered (CR1 sandwich for the mean, "
               "z=1.96); every model-vs-market delta is PAIRED per game and "
               "clustered by game date per D036 point 7"),
        "walk_forward_logistic_fits": {"composite": comp_fits, "team_avg": ta_fits},
    }

    exclusions = {
        "composite": dict(comp_excl),
        "league_avg": dict(lg_excl),
        "team_avg": dict(ta_excl),
        "team_game_rows_missing_from_possession_stream": n_poss_missing,
    }

    def prov_row(model, target, universe, date_range, n):
        return {
            "model_version": model, "target": target,
            "cutoff": "pregame_strictly_lagged_all_inputs_prior_dates",
            "universe": universe, "date_range": date_range, "n": n,
            "evidence_class": EVIDENCE_CLASS,
            "commit": "NO_GIT_WORKTREE (worktree is not a git repo; see top-level producer.sha256)",
            "computed_at": generated,
        }

    out = {
        "schema": "market_program/SCORE_BASELINES/metrics/1",
        "node": "experiments/market_program/SCORE_BASELINES",
        "generated_utc": generated,
        "authorities": ["D043_CYCLE2_SCORE_AND_EFFICIENCY",
                        "D036_SCOREBOARD_MEASUREMENT_SEMANTICS"],
        "evidence_class": EVIDENCE_CLASS,
        "evidence_class_semantics": EVIDENCE_CLASS_SEMANTICS,
        "producer": {
            "path": "experiments/market_program/SCORE_BASELINES/build_score_baselines.py",
            "sha256": sha256_file(Path(__file__)),
        },
        "inputs": inputs,
        "conventions": conventions,
        "exclusions": exclusions,
        "methods": {},
        "market_comparison": {
            "universe": ("MATCHED universe only: BOOKIE_BASELINE's frozen join of the "
                         "2022-2026 T1 odds archive to owned outcomes, LATE snapshot "
                         "class, cross_book consensus, intersected with games the "
                         "composite covers. NEVER an unmatched-universe verdict."),
            "snapshot_class": "LATE", "variant": "cross_book",
            "provenance_class": "T1_VENDOR_ASSERTED",
            "vendor_ts_semantics": "vendor_asserted_unwitnessed",
            "t1_timing_caveat_verbatim": caveat["caveat_text"],
            "caveat_sha256": caveat["caveat_sha256"],
            "n_matched_games_with_late_quote": n_market_late,
            "n_paired_with_composite": n_market_with_composite,
            "d036_market_bars_context": {
                "value": D043_MARKET_BARS,
                "note": ("D043's quoted bars (LATE cross_book POOLED over the FULL "
                         "matched archive, from BOOKIE_BASELINE); shown for context "
                         "only -- the verdict numbers are the PAIRED rows below, "
                         "computed on the identical game set for both sides."),
            },
            "paired_metrics": paired,
            "provenance": prov_row(
                MODEL_VERSIONS["composite"],
                "total,margin,win_prob vs market consensus",
                "matched_2022_2026_late_cross_book_with_composite_coverage",
                (paired["margin_mae"]["date_range"] if paired["margin_mae"] else None),
                (paired["margin_mae"]["n_pairs"] if paired["margin_mae"] else 0)),
        },
    }

    universe_desc = {
        "composite": "owned gamelog universe 2021-2026, composite-covered games",
        "league_avg": "owned gamelog universe 2021-2026, league-average-covered games",
        "team_avg": "owned gamelog universe 2021-2026, season-to-date-covered games",
    }
    for key, res in results.items():
        blocks = {}
        for season, blk in res.items():
            blk = dict(blk)
            blk["provenance"] = prov_row(
                MODEL_VERSIONS[key], "total,margin" + (",win_prob" if "win_prob" in blk else ""),
                universe_desc[key] + f", season={season}",
                blk["date_range"], blk["n_games"])
            blocks[season] = blk
        out["methods"][MODEL_VERSIONS[key]] = blocks

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "score_baselines.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)

    # per-game prediction rows for downstream leaderboard reuse
    all_rows = []
    for key, df in (("composite", comp), ("league_avg", lg), ("team_avg", ta)):
        d = df.merge(games[["game_id", "game_date", "season", "actual_total",
                            "actual_margin", "y_home_win"]], on="game_id",
                     how="left", validate="1:1")
        d["method"] = MODEL_VERSIONS[key]
        all_rows.append(d)
    pd.concat(all_rows, ignore_index=True).to_parquet(
        OUT_DIR / "score_baseline_rows.parquet", index=False)
    paired_rows.to_parquet(OUT_DIR / "market_paired_rows.parquet", index=False)

    print("composite games:", len(comp), "| league_avg:", len(lg), "| team_avg:", len(ta))
    print("exclusions:", exclusions)
    print("market matched LATE:", n_market_late, "| paired with composite:",
          n_market_with_composite)
    for m, blk in paired.items():
        if blk:
            print(f"{m}: composite={blk['composite']:.4f} market={blk['market']:.4f} "
                  f"delta={blk['paired_delta_composite_minus_market']:+.4f} "
                  f"ci={blk['paired_delta_ci95']} n={blk['n_pairs']}")
    return out


if __name__ == "__main__":
    main()
