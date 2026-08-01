#!/usr/bin/env python3
"""calibrated_prob_edge_v1 -- calibrated P(over) x executable odds -> frozen EV policy.

Registered: calibrated_prob_edge_v1 (regime A, primary metric realised_roi_frozen_rule,
incumbent bet_everything_at_best_price), as amended by executability_fixed_notional_v1.
This script never registers; it evaluates.

THE TARGET, AND WHY IT IS NOT COMPARATIVE ERROR
    The predecessor targeted |line - actual| - |projection - actual|.  That is bounded by
    |projection - line| (reverse triangle inequality), so when the model is worse than the
    market on average -- our situation in every market measured -- the target is maximised by
    AGREEING with the line, i.e. by having nothing to say.  It rewards abstention, not skill.
    tests/test_edge_target_identity.py makes that permanent.

    Here the model learns P(points > line): a binary, low-noise, well-posed label.  Realised
    ROI JUDGES the frozen policy but is never the training label, because return is far too
    noisy to fit and would simply produce a differently-overfit selector.

EVERY CONSTANT BELOW IS FIXED BEFORE ANY RESULT IS VIEWED.
    This file is committed BEFORE it is first run, so the freeze is auditable in git history
    rather than asserted in prose.  Changing any of them after seeing output is a new
    registration that consumes its own evaluation slice.

SLICES (conditional_edge_design_freeze_v2, unchanged)
    2024 = FITTING.  2025 = development check, may inform nothing that is then called
    confirmation.  2026 = retrospective descriptive only.  THE PROSPECTIVE LOG IS THE ONLY
    HOLDOUT capable of supporting promotion.  No number this script prints is confirmatory.

EXECUTABILITY (executability_fixed_notional_v1)
    Simultaneity IS enforced: last_update is joined back and stale quotes are excluded.
    Book limits are NOT obtainable -- no odds feed publishes them -- so evaluation is at a
    FIXED NOTIONAL and capacity is reported as UNMEASURED, never as unlimited.  The bias from
    ignoring limits is systematic and UPWARD, because books cut limits precisely where they
    judge a market soft, so limits correlate with edge.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
import evalharness as eh                                     # noqa: E402

EXPERIMENT_ID = "calibrated_prob_edge_v1"
OUT = REPO / "experiments" / "calibrated_prob_edge"

UNIVERSE = REPO / "experiments" / "props_edge" / "bet_universe_per_book.csv"
HIST = REPO / "data" / "props_capture" / "historical" / "master_props_historical.csv"

# ---------------------------------------------------------------------------
# REGISTERED CONSTANTS -- fixed before any result is viewed
# ---------------------------------------------------------------------------
FIT_SEASON = 2024                 # freeze_v2: fitting slice
DEV_SEASON = 2025                 # development check, never confirmation
DESC_SEASON = 2026                # retrospective description only

STALENESS_MAX_MIN = 120.0         # a quote whose last_update precedes the snapshot by more
                                  # than this is NOT simultaneous and is excluded
MIN_DISAGREE_PTS = 1.0            # minimum |projection - line| in POINTS. The mandatory
                                  # defence: without a floor the policy can drift toward rows
                                  # where the model has no independent opinion
EV_THRESHOLD = 0.02               # bet only above 2% expected value per unit staked
NOTIONAL = 100                    # fixed stake per bet (executability_fixed_notional_v1 E1)
LAMBDA_GRID = [0.1, 0.3, 1, 3, 10, 30, 100, 300]   # freeze_v2 (3)
TRACE_H_CAP = 10.0                # freeze_v2 (4) effective d.o.f. cap
N_PERM = 2000                     # amendment v5 C2: fixed before the first draw
PERM_SEED = 20260801

#: At most EIGHT features, named here and unchangeable (freeze_v2 (2)).  The disagreement
#: term is included DELIBERATELY so its dominance can be measured rather than assumed --
#: that is how the predecessor's defect was found.
FEATURES = ["disagree", "exp_min", "n_prior", "line", "is_starter", "is_home",
            "mkt_imp_over", "cons_dev"]


def _amer_profit(price: np.ndarray) -> np.ndarray:
    """Profit per 1 unit staked if the bet wins."""
    p = np.asarray(price, float)
    return np.where(p > 0, p / 100.0, 100.0 / np.abs(p))


def _amer_imp(price: np.ndarray) -> np.ndarray:
    """Vig-inclusive implied probability from American odds."""
    p = np.asarray(price, float)
    return np.where(p > 0, 100.0 / (p + 100.0), np.abs(p) / (np.abs(p) + 100.0))


def load() -> pd.DataFrame:
    d = pd.read_csv(UNIVERSE)
    h = pd.read_csv(HIST, dtype=str)
    h = h[h.market_key == "player_points"].copy()

    # The join is one-to-one on this key (verified: 36,946 rows -> 36,946 distinct keys),
    # so attaching last_update CANNOT change which price row is used.
    key = ["game_id", "bookmaker_key", "player_name", "line"]
    h["line"] = h["line"].astype(float)
    h = h[key + ["last_update", "snapshot_returned_utc"]].drop_duplicates(key)
    d["game_id"] = d["game_id"].astype(str)
    h["game_id"] = h["game_id"].astype(str)
    n0 = len(d)
    d = d.merge(h, on=key, how="left")
    assert len(d) == n0, "join changed row count -- not one-to-one"

    lu = pd.to_datetime(d.last_update, errors="coerce", utc=True)
    sn = pd.to_datetime(d.snapshot_returned_utc, errors="coerce", utc=True)
    d["stale_min"] = (sn - lu).dt.total_seconds() / 60.0
    return d


def prepare(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Eligibility ladder -- every drop counted, none silent."""
    acct = {"rows_in": int(len(d))}

    d = d[d.resolve_status.astype(str).str.startswith("resolved")]
    acct["after_resolved"] = int(len(d))
    d = d[~d.void.astype(bool)]
    acct["after_void_removed"] = int(len(d))
    d = d[d.actual_pts.notna() & d.proj_used.notna() & d.line.notna()]
    acct["after_outcome_present"] = int(len(d))
    d = d[d.over_price.notna() & d.under_price.notna()]
    acct["after_two_sided_price"] = int(len(d))

    acct["last_update_missing"] = int(d.stale_min.isna().sum())
    d = d[d.stale_min.notna() & (d.stale_min <= STALENESS_MAX_MIN)]
    acct["after_simultaneity"] = int(len(d))

    d = d.copy()
    d["disagree"] = d.proj_used - d.line
    d = d[d.disagree.abs() >= MIN_DISAGREE_PTS]
    acct["after_min_disagreement_band"] = int(len(d))

    # A push (actual == line) is neither over nor under; excluded, and counted.
    push = d.actual_pts == d.line
    acct["pushes_removed"] = int(push.sum())
    d = d[~push].copy()

    d["y_over"] = (d.actual_pts > d.line).astype(int)
    d["is_starter"] = (d.role.astype(str) == "starter").astype(int)
    d["is_home"] = (d.venue.astype(str) == "home").astype(int)
    d["mkt_imp_over"] = _amer_imp(d.over_price.to_numpy())
    d["cons_dev"] = d.line - d.cons_line
    d["exp_min"] = d.exp_min.fillna(d.exp_min.median())
    d["n_prior"] = d.n_prior.fillna(0)
    acct["rows_eligible"] = int(len(d))
    return d, acct


def fit_logistic(X: np.ndarray, y: np.ndarray, lam: float, iters: int = 200):
    """L2 logistic via Newton-IRLS.  Model class fixed by freeze_v2 (1)."""
    Xb = np.column_stack([np.ones(len(X)), X])
    w = np.zeros(Xb.shape[1])
    R = np.eye(Xb.shape[1]) * lam
    R[0, 0] = 0.0                                    # never penalise the intercept
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(Xb @ w, -30, 30)))
        W = np.clip(p * (1 - p), 1e-9, None)
        g = Xb.T @ (y - p) - R @ w
        H = Xb.T @ (Xb * W[:, None]) + R
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        w += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return w


def predict(w: np.ndarray, X: np.ndarray) -> np.ndarray:
    Xb = np.column_stack([np.ones(len(X)), X])
    return 1.0 / (1.0 + np.exp(-np.clip(Xb @ w, -30, 30)))


def trace_H(X: np.ndarray, w: np.ndarray, lam: float) -> float:
    Xb = np.column_stack([np.ones(len(X)), X])
    p = predict(w, X)
    W = np.clip(p * (1 - p), 1e-9, None)
    R = np.eye(Xb.shape[1]) * lam
    R[0, 0] = 0.0
    A = Xb.T @ (Xb * W[:, None])
    return float(np.trace(np.linalg.solve(A + R, A)))


def standardise(Xf: pd.DataFrame, mu=None, sd=None):
    if mu is None:
        mu, sd = Xf.mean(), Xf.std().replace(0, 1.0)
    return ((Xf - mu) / sd).to_numpy(float), mu, sd


def brier(y, p):  return float(np.mean((p - y) ** 2))
def logloss(y, p):
    q = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)))


def calib_slope_intercept(y, p):
    q = np.clip(p, 1e-6, 1 - 1e-6)
    z = np.log(q / (1 - q))
    w = fit_logistic(z.reshape(-1, 1), y, lam=0.0)
    return float(w[1]), float(w[0])            # slope, intercept


def reliability(y, p, bins=10) -> list[dict]:
    edges = np.linspace(0, 1, bins + 1)
    out = []
    idx = np.digitize(p, edges[1:-1])
    for b in range(bins):
        m = idx == b
        if m.sum() == 0:
            continue
        out.append({"bin": f"{edges[b]:.1f}-{edges[b+1]:.1f}", "n": int(m.sum()),
                    "mean_pred": float(p[m].mean()), "emp_rate": float(y[m].mean())})
    return out


def decide(d: pd.DataFrame, p_over: np.ndarray) -> pd.DataFrame:
    """ONE frozen decision layer.  Overs and unders are formed separately and never pooled."""
    g = d.copy()
    g["p_over"] = p_over
    g["ev_over"] = g.p_over * _amer_profit(g.over_price.to_numpy()) - (1 - g.p_over)
    g["ev_under"] = (1 - g.p_over) * _amer_profit(g.under_price.to_numpy()) - g.p_over
    g["bet_over"] = g.ev_over >= EV_THRESHOLD
    g["bet_under"] = g.ev_under >= EV_THRESHOLD
    return g


def roi_of(g: pd.DataFrame, side: str) -> tuple[float, int, np.ndarray]:
    """Per-unit return of the frozen rule on one side.  Never pooled across sides."""
    if side == "over":
        sel = g[g.bet_over]
        win = sel.y_over == 1
        prof = np.where(win, _amer_profit(sel.over_price.to_numpy()), -1.0)
    else:
        sel = g[g.bet_under]
        win = sel.y_over == 0
        prof = np.where(win, _amer_profit(sel.under_price.to_numpy()), -1.0)
    if len(sel) == 0:
        return float("nan"), 0, np.array([])
    return float(prof.mean()), int(len(sel)), prof


def perm_mde(g: pd.DataFrame, side: str, rng: np.random.Generator) -> dict:
    """MDE from a permutation null BLOCKED BY GAME DATE, permuted over ALL eligible rows.

    The blocking respects the per-date common shock and within-date player/game dependence;
    a row-exchangeable null would be anti-conservative here (v5 C1).

    CORRECTED 2026-08-01.  The first implementation permuted outcomes only among the
    SELECTED bets.  That is far too narrow: within-date outcome variance (0.148) is well
    below overall variance (0.249), so shuffling inside an already-chosen set barely moved
    the mean and the null SD came out roughly 20x too small -- an MDE of 0.003 where the
    naive SE alone implies 0.074.  An MDE that small would have let ordinary noise be read
    as a real effect.  The permuted label must flow through the whole downstream path
    (screening_protocol_amendment_v2 P3), so outcomes are now shuffled within a date across
    EVERY eligible row and the fixed bet selection is then scored against them.  This makes
    the null strictly wider, i.e. more conservative.
    """
    mask = g.bet_over if side == "over" else g.bet_under
    if not mask.any():
        return {"n_perm": 0, "null_sd": float("nan"), "mde_roi": float("nan")}
    price = (g.over_price if side == "over" else g.under_price).to_numpy()
    prof_win = _amer_profit(price)
    y = g.y_over.to_numpy()
    target = 1 if side == "over" else 0
    sel = mask.to_numpy()

    dates = g.game_date.to_numpy()
    order = np.argsort(dates, kind="stable")
    blocks = [b for b in np.split(order, np.unique(dates[order], return_index=True)[1][1:])
              if len(b) > 1]

    stats = np.empty(N_PERM)
    for i in range(N_PERM):
        yp = y.copy()
        for b in blocks:
            yp[b] = rng.permutation(y[b])
        stats[i] = np.where(yp[sel] == target, prof_win[sel], -1.0).mean()
    sd = float(stats.std(ddof=1))
    return {"n_perm": N_PERM, "null_sd": sd, "mde_roi": float(2.802 * sd),
            "null_mean": float(stats.mean())}


def date_clustered_ci(g: pd.DataFrame, side: str, rng: np.random.Generator,
                      n_boot: int = 2000, alpha: float = 0.10) -> dict:
    """90% ROI interval from a bootstrap over GAME DATES, not rows.

    Bets on the same slate share a common shock, so resampling rows would understate the
    interval.  Dates are the resampling unit.
    """
    sel = g[g.bet_over] if side == "over" else g[g.bet_under]
    if len(sel) == 0:
        return {"roi_ci90_low": float("nan"), "roi_ci90_high": float("nan")}
    price = (sel.over_price if side == "over" else sel.under_price).to_numpy()
    win = (sel.y_over == (1 if side == "over" else 0)).to_numpy()
    prof = np.where(win, _amer_profit(price), -1.0)
    dates = sel.game_date.to_numpy()
    uniq = np.unique(dates)
    idx_by_date = {d: np.flatnonzero(dates == d) for d in uniq}

    out = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        out[i] = prof[np.concatenate([idx_by_date[d] for d in pick])].mean()
    lo, hi = np.quantile(out, [alpha / 2, 1 - alpha / 2])
    return {"roi_ci90_low": float(lo), "roi_ci90_high": float(hi)}


def main() -> int:
    reg = eh.get_registration(EXPERIMENT_ID)
    print(f"registration OK: {EXPERIMENT_ID} (registered {reg['registered_at']}, "
          f"regime {reg['regime']}, incumbent {reg['incumbent_id']})")
    print(f"amended by executability_fixed_notional_v1 (fixed notional {NOTIONAL}, "
          f"capacity UNMEASURED)\n")
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(PERM_SEED)

    d, acct = prepare(load())
    for k, v in acct.items():
        print(f"  {k:32s} {v}")

    fit = d[d.season == FIT_SEASON]
    print(f"\nFITTING slice {FIT_SEASON}: {len(fit)} rows, "
          f"{fit.game_id.nunique()} games, {fit.game_date.nunique()} dates, "
          f"{fit.player_id.nunique()} players")
    if len(fit) < 200:
        print("fitting slice too small -- stopping"); return 1

    Xf, mu, sd = standardise(fit[FEATURES])
    yf = fit.y_over.to_numpy()

    # lambda by leave-one-DATE-out CV inside the fitting slice ONLY (freeze_v2 (3))
    dates = fit.game_date.to_numpy()
    uniq = np.unique(dates)
    best = None
    for lam in LAMBDA_GRID:
        ll = []
        for dt in uniq:
            m = dates == dt
            if m.sum() == 0 or (~m).sum() < 50:
                continue
            w = fit_logistic(Xf[~m], yf[~m], lam)
            ll.append(logloss(yf[m], predict(w, Xf[m])))
        s = float(np.mean(ll))
        print(f"  lambda {lam:>6}: LODO log loss {s:.5f}")
        if best is None or s < best[1]:
            best = (lam, s)
    lam = best[0]

    w = fit_logistic(Xf, yf, lam)
    tr = trace_H(Xf, w, lam)
    escalated = []
    while tr > TRACE_H_CAP:                       # freeze_v2 (4): escalate and report
        nxt = [x for x in LAMBDA_GRID if x > lam]
        if not nxt:
            break
        lam = nxt[0]; escalated.append(lam)
        w = fit_logistic(Xf, yf, lam); tr = trace_H(Xf, w, lam)
    print(f"\nchosen lambda {lam} (trace(H) {tr:.2f} <= {TRACE_H_CAP})"
          + (f"  ESCALATED via {escalated}" if escalated else ""))
    print("  coefficients (standardised): " +
          ", ".join(f"{n}={c:+.4f}" for n, c in zip(FEATURES, w[1:])))

    # ONE FIT ONLY (freeze_v2 (5)) -- every later slice merely scores this frozen object.
    results, per_slice = {}, {}
    for label, season in [("fit_2024", FIT_SEASON), ("dev_2025", DEV_SEASON),
                          ("desc_2026", DESC_SEASON)]:
        s = d[d.season == season]
        if not len(s):
            continue
        Xs, _, _ = standardise(s[FEATURES], mu, sd)
        p = predict(w, Xs)
        ys = s.y_over.to_numpy()
        g = decide(s, p)
        slope, icept = calib_slope_intercept(ys, p)
        row = {"n_rows": int(len(s)), "n_games": int(s.game_id.nunique()),
               "n_dates": int(s.game_date.nunique()),
               "n_players": int(s.player_id.nunique()),
               "log_loss": logloss(ys, p), "brier": brier(ys, p),
               "base_rate_over": float(ys.mean()), "mean_pred": float(p.mean()),
               "calib_slope": slope, "calib_intercept": icept,
               "reliability": reliability(ys, p)}
        for side in ("over", "under"):
            roi, n, prof = roi_of(g, side)
            mde = perm_mde(g, side, rng)
            ci = date_clustered_ci(g, side, rng)
            # independent opportunities, not quoted rows: one per player-game
            sel = g[g.bet_over] if side == "over" else g[g.bet_under]
            row[side] = {
                "n_bets_rows": n,
                "n_independent_opportunities": int(
                    sel.drop_duplicates(["game_id", "player_id"]).shape[0]) if n else 0,
                "n_dates": int(sel.game_date.nunique()) if n else 0,
                "roi": roi, "notional": NOTIONAL,
                "mde_roi": mde["mde_roi"], "null_sd": mde["null_sd"],
                "exceeds_mde": bool(n and np.isfinite(roi) and abs(roi) > mde["mde_roi"]),
                **ci,
                "ci_excludes_zero": bool(n and np.isfinite(ci["roi_ci90_low"])
                                         and (ci["roi_ci90_low"] > 0 or ci["roi_ci90_high"] < 0)),
            }
        results[label] = row
        per_slice[label] = g
        print(f"\n{label}: n={row['n_rows']} rows / {row['n_games']} games / "
              f"{row['n_dates']} dates")
        print(f"  log loss {row['log_loss']:.5f} | Brier {row['brier']:.5f} | "
              f"base rate over {row['base_rate_over']:.4f} | mean pred {row['mean_pred']:.4f}")
        print(f"  calibration slope {slope:+.3f} intercept {icept:+.3f} "
              f"(perfect = 1.000 / 0.000)")
        for side in ("over", "under"):
            r = row[side]
            print(f"  {side.upper():5s} bets {r['n_bets_rows']:5d} "
                  f"({r['n_independent_opportunities']} indep, {r['n_dates']} dates) "
                  f"ROI {r['roi']:+.4f} "
                  f"[90% {r['roi_ci90_low']:+.4f}, {r['roi_ci90_high']:+.4f}]  "
                  f"MDE {r['mde_roi']:.4f}  "
                  f"{'exceeds MDE' if r['exceeds_mde'] else 'within noise'}"
                  f"{', CI excludes 0' if r['ci_excludes_zero'] else ''}")

    # Does the disagreement term dominate the decision? (mandatory defence 3)
    gfit = per_slice["fit_2024"]
    bet = gfit.bet_over | gfit.bet_under
    dom = {
        "corr_p_over_vs_disagree": float(np.corrcoef(
            gfit.p_over, gfit.disagree)[0, 1]),
        "corr_p_over_vs_mkt_imp": float(np.corrcoef(
            gfit.p_over, gfit.mkt_imp_over)[0, 1]),
        "mean_abs_disagree_bet": float(gfit.loc[bet, "disagree"].abs().mean()) if bet.any() else None,
        "mean_abs_disagree_all": float(gfit.disagree.abs().mean()),
    }
    print(f"\ndisagreement dominance (fitting slice): "
          f"corr(p_over, disagree) {dom['corr_p_over_vs_disagree']:+.3f}, "
          f"corr(p_over, market implied) {dom['corr_p_over_vs_mkt_imp']:+.3f}")

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "amended_by": "executability_fixed_notional_v1",
        "registered_constants": {
            "staleness_max_min": STALENESS_MAX_MIN, "min_disagree_pts": MIN_DISAGREE_PTS,
            "ev_threshold": EV_THRESHOLD, "notional": NOTIONAL,
            "lambda_grid": LAMBDA_GRID, "trace_h_cap": TRACE_H_CAP,
            "n_perm": N_PERM, "perm_seed": PERM_SEED, "features": FEATURES},
        "chosen_lambda": lam, "trace_H": tr, "lambda_escalated": escalated,
        "coefficients_standardised": dict(zip(FEATURES, map(float, w[1:]))),
        "intercept": float(w[0]),
        "eligibility_ladder": acct,
        "slices": results,
        "disagreement_dominance": dom,
        "slice_labels": {
            "fit_2024": "FITTING", "dev_2025": "development check, NOT confirmation",
            "desc_2026": "retrospective descriptive ONLY",
            "holdout": "the prospective log is the only holdout that can promote"},
        "executability": {
            "simultaneity_enforced": True,
            "staleness_threshold_min": STALENESS_MAX_MIN,
            "book_limits": "NOT OBTAINABLE -- no odds feed publishes them",
            "capacity": "UNMEASURED",
            "bias_direction": "systematic and UPWARD: books cut limits precisely where they "
                              "judge a market soft, so limits correlate with edge and the "
                              "most profitable-looking rows are those you can least get size on",
        },
    }
    (OUT / "results.json").write_text(json.dumps(payload, indent=1, default=str),
                                      encoding="utf-8")
    cols = ["season", "game_id", "game_date", "player_id", "player_name", "bookmaker_key",
            "line", "proj_used", "disagree", "over_price", "under_price", "stale_min",
            "p_over", "ev_over", "ev_under", "bet_over", "bet_under", "y_over", "actual_pts"]
    pd.concat([g[cols] for g in per_slice.values()], ignore_index=True).to_csv(
        OUT / "scored_rows.csv", index=False)
    print(f"\nwrote {OUT/'results.json'} and scored_rows.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
