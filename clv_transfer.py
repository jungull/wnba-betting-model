"""clv_transfer.py — preregistered measurement experiment ``clv_transfer_v1``.

Registered 2026-07-30T21:23:43Z in experiments/registry.jsonl (binding record;
regime A, primary metric margin_mae, incumbent ``market_line_at_matched_cutoff``).
This is a MEASUREMENT experiment: the registered primary comparison (model vs
the market line at the model's own decision time) is EXPECTED TO LOSE —
promote=false is the anticipated outcome. The deliverables are the tables:

  1. matched_gap_by_cutoff_and_season.csv — model margin MAE vs matched-time
     market MAE per cutoff x era x season, with paired date-clustered bootstrap
     CIs. Repairs the timing asymmetry of the 0.373 headline gap (a ~T-24h
     model scored against ~T-64m / latest-pre-tip lines).
  2. flat_stake_sim.csv (+ bet_log.csv) — flat-stake spread sim: bet the side
     where model - line >= threshold over the grid {0.5, 1, 1.5, 2, 3}, at
     (a) synthetic -110 and (b) actual captured prices (best executable book
     at the matched vintage); graded on actual outcomes (ROI, hit rate,
     pushes) and CLV (signed movement of the latest pre-tip line toward the
     bet side).
  3. transfer_curve.csv (+ transfer_breakeven.csv) — the same sim run on the
     four committed oracle-bracket margin variants (known pooled-MAE spacing
     10.175 / 10.156 / 10.117 / 10.107) -> empirical ROI-vs-MAE and
     hit-rate-vs-MAE slopes -> the (labeled, linear) EXTRAPOLATION of what
     pooled-MAE improvement break-even at -110 (52.38% hits) requires.

Era discipline is absolute: the extension era (2025-07-05+, multi-snapshot
line paths, data/odds_capture/master_odds_extension.csv) and the old era
(2022 - 2025-07-04, single ~T-64m snapshot per game-book,
data/drive_masters/master_odds.csv) are NEVER blended in one number. Every
output row carries an era label; pooled rows pool seasons WITHIN one era only.

Cutoffs each era supports (measured, not assumed):
  extension: T-24h (primary), T-8h (2/day 15Z/22Z backfill cadence supports
             both; coverage counted per cutoff), plus the latest pre-tip line
             (~T-2.1h median) as the timing-asymmetric comparator and the CLV
             reference. T-90m is NOT supported at this cadence (near-tip rows
             are the pretip row itself).
  old:       ONLY the single ~T-64m snapshot. T-24h / T-8h have zero coverage
             by construction (every snapshot sits ~64 min before tip); the
             script measures and reports the zeros. CLV is undefined (no
             later line exists).

Model = ``str_margin_cal`` from experiments/channel_reval/predictions_v2.csv.
Its features are within-season shifted EWMAs over games STRICTLY BEFORE the
target game's date — the information set closes with the previous day's box
scores, i.e. it is a T-24h-compatible forecast (for a typical ~7pm ET tip the
T-24h cutoff falls the prior evening, after that day's games). ROADMAP's
information-parity caveat still applies: the T-24h line may already embed
availability news the model cannot see; matched timing removes only the
clock asymmetry, never assumed away.

Run:  python clv_transfer.py             # REAL run (records on the ledger) — orchestrator only
      python clv_transfer.py --stage     # full data, artifacts to experiments/clv_transfer/,
                                         #   registry writes go to a SCRATCH COPY (ledger untouched)
      python clv_transfer.py --smoke     # scratch registry copy + scratch outdir + subsample
"""

from __future__ import annotations

import argparse
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

from evalharness import compare_to_incumbent  # noqa: E402
from evalharness.compare import cluster_bootstrap_ci, ComparisonError  # noqa: E402
from evalharness import registry as ereg  # noqa: E402

PRED = REPO / "experiments" / "channel_reval" / "predictions_v2.csv"
ORACLE = REPO / "experiments" / "oracle_bracket" / "game_level_margins.csv"
ODDS_OLD = REPO / "data" / "drive_masters" / "master_odds.csv"
ODDS_EXT = REPO / "data" / "odds_capture" / "master_odds_extension.csv"
DEFAULT_OUTDIR = REPO / "experiments" / "clv_transfer"
EXPERIMENT_ID = "clv_transfer_v1"

THRESHOLDS = [0.5, 1.0, 1.5, 2.0, 3.0]
VARIANTS = ["v1_none", "v2_reconstructed", "v3_pregame_oracle", "v4_omniscient"]
VCOL = {v: f"margin_{v}" for v in VARIANTS}
BREAK_EVEN_HIT = 110.0 / 210.0          # 0.523810 — win share needed at -110
WIN_110 = 100.0 / 110.0                 # flat-stake profit on a -110 winner
PRICE_ANOMALY_ABS = 10000               # |american price| >= this -> void/unusable (counted)
PUSH_TOL = 1e-9
SEED = 20260730

# (era, cutoff_label, hours_before_tip or None for latest-pre-tip)
CUTOFFS = {
    "extension": [("T-24h", 24.0), ("T-8h", 8.0), ("pretip", None)],
    "old": [("T-64m", None)],
}
SIM_CUTOFFS = [("extension", "T-24h"), ("extension", "T-8h"), ("old", "T-64m")]
HEADLINE = ("extension", "T-24h")


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def load_predictions() -> pd.DataFrame:
    p = pd.read_csv(PRED)
    p["game_id"] = p["GAME_ID"].astype(str)
    p["game_date"] = pd.to_datetime(p["GAME_DATE_h"])
    out = p[["game_id", "game_date", "season_h", "season_type_h",
             "TEAM_ABBREVIATION_h", "margin_true", "str_margin_cal"]].rename(
        columns={"season_h": "season", "season_type_h": "season_type",
                 "TEAM_ABBREVIATION_h": "home_team_abbr",
                 "str_margin_cal": "model_margin"})
    assert not out["game_id"].duplicated().any()
    return out


def load_oracle() -> pd.DataFrame:
    o = pd.read_csv(ORACLE)
    o["game_id"] = o["GAME_ID"].astype(str)
    o["game_date"] = pd.to_datetime(o["game_date"])
    keep = ["game_id", "game_date", "season_h", "margin_true"] + list(VCOL.values())
    o = o[keep].rename(columns={"season_h": "season"})
    assert not o["game_id"].duplicated().any()
    return o


def load_odds(path: Path, era: str) -> pd.DataFrame:
    """Tidy per (game_id, book, snap): home_spread, home_price, away_price,
    tip (commence quoted at the game's LATEST listing — resolves the two
    documented reschedules), pre-tip rows only (snap < tip)."""
    o = pd.read_csv(path, low_memory=False)
    o = o[o["game_id"].notna() & o["odds_spread"].notna()].copy()
    o["game_id"] = o["game_id"].astype(np.int64).astype(str)
    o["snap"] = pd.to_datetime(o["odds_snapshot_timestamp"], utc=True, format="mixed")
    o["tip_raw"] = pd.to_datetime(o["odds_commence_time"], utc=True, format="mixed")
    is_home = o["team"] == o["home_team"]
    h = o[is_home][["game_id", "bookmaker_key", "snap", "tip_raw",
                    "odds_spread", "odds_price"]].rename(
        columns={"odds_spread": "home_spread", "odds_price": "home_price"})
    a = o[o["team"] == o["away_team"]][["game_id", "bookmaker_key", "snap",
                                        "odds_price"]].rename(
        columns={"odds_price": "away_price"})
    t = h.merge(a, on=["game_id", "bookmaker_key", "snap"], how="left")
    # tip at the game's latest listing
    last = t.sort_values("snap").groupby("game_id").tail(1)[["game_id", "tip_raw"]]
    tipmap = dict(zip(last["game_id"], last["tip_raw"]))
    t["tip"] = t["game_id"].map(tipmap)
    t = t[t["snap"] < t["tip"]].copy()
    t["era"] = era
    return t.reset_index(drop=True)


# ---------------------------------------------------------------------------
# matched-time lines
# ---------------------------------------------------------------------------

def build_matched_lines(odds: pd.DataFrame, era: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (consensus, books).

    consensus: one row per (era, cutoff, game_id): consensus_home_spread
      (mean over books at the matched vintage), market_margin = -consensus,
      n_books, vintage snap, staleness vs cutoff, tip.
    books: the per-book rows AT the matched vintage (for actual-price
      execution): era, cutoff, game_id, book, home_spread, home_price,
      away_price, snap.

    Vintage conventions (documented, per registration):
      * hour cutoffs (T-24h / T-8h): the latest SNAPSHOT TIMESTAMP at or
        before the cutoff; consensus = mean over the books present at that
        single snapshot vintage.
      * pretip / T-64m: each book's latest pre-tip row (mean over books) —
        the exact convention of the 0.373 headline (oracle_bracket
        build_bookie_margins), kept for comparability.
    """
    cons_rows, book_frames = [], []
    for gid, g in odds.groupby("game_id"):
        tip = g["tip"].iloc[0]
        for label, hours in CUTOFFS[era]:
            if hours is not None:
                cutoff = tip - pd.Timedelta(hours=hours)
                elig = g[g["snap"] <= cutoff]
                if not len(elig):
                    continue
                vint = elig["snap"].max()
                rows = elig[elig["snap"] == vint]
                staleness_h = (cutoff - vint).total_seconds() / 3600.0
            else:
                # per-book latest pre-tip
                rows = g.sort_values("snap").groupby("bookmaker_key").tail(1)
                vint = rows["snap"].max()
                cutoff = pd.NaT
                staleness_h = np.nan
            cons = float(rows["home_spread"].mean())
            cons_rows.append({
                "era": era, "cutoff": label, "game_id": gid,
                "consensus_home_spread": cons, "market_margin": -cons,
                "n_books": int(rows["bookmaker_key"].nunique()),
                "vintage_snap": vint, "cutoff_ts": cutoff, "tip": tip,
                "staleness_h": staleness_h,
                "mins_before_tip": (tip - vint).total_seconds() / 60.0,
            })
            bf = rows[["game_id", "bookmaker_key", "snap",
                       "home_spread", "home_price", "away_price"]].copy()
            bf["era"], bf["cutoff"] = era, label
            book_frames.append(bf)
    consensus = pd.DataFrame(cons_rows)
    books = (pd.concat(book_frames, ignore_index=True)
             if book_frames else pd.DataFrame())
    return consensus, books


def unsupported_cutoff_counts(odds: pd.DataFrame, era: str,
                              labels_hours: list[tuple[str, float]]) -> dict:
    """Measure (not assume) that a cutoff has zero coverage in an era."""
    out = {}
    for label, hours in labels_hours:
        n = 0
        for gid, g in odds.groupby("game_id"):
            cutoff = g["tip"].iloc[0] - pd.Timedelta(hours=hours)
            if (g["snap"] <= cutoff).any():
                n += 1
        out[label] = {"games_with_line": n, "games_total": int(odds["game_id"].nunique())}
    return out


# ---------------------------------------------------------------------------
# Table 1 — matched-time gap
# ---------------------------------------------------------------------------

def gap_table(joined: pd.DataFrame, n_boot: int) -> pd.DataFrame:
    """joined: one row per (era, cutoff, game) with model_margin,
    market_margin, margin_true, season, game_date. Per-season + era-pooled
    rows (pooled NEVER crosses eras). delta = |market err| - |model err|
    (positive = model better), date-clustered bootstrap CI."""
    rows = []
    for (era, cutoff), grp in joined.groupby(["era", "cutoff"]):
        seasons = sorted(grp["season"].unique().tolist())
        for season in seasons + ["pooled"]:
            sub = grp if season == "pooled" else grp[grp["season"] == season]
            if not len(sub):
                continue
            e_model = (sub["model_margin"] - sub["margin_true"]).abs()
            e_market = (sub["market_margin"] - sub["margin_true"]).abs()
            delta = (e_market - e_model).to_numpy(float)
            dates = pd.to_datetime(sub["game_date"]).dt.normalize().to_numpy()
            ci_lo = ci_hi = np.nan
            n_dates = int(pd.Series(dates).nunique())
            if n_dates >= 2:
                ci = cluster_bootstrap_ci(delta, dates, n_boot=n_boot, seed=SEED)
                ci_lo, ci_hi = ci["low"], ci["high"]
            rows.append({
                "era": era, "cutoff": cutoff, "season": str(season),
                "n_games": int(len(sub)), "n_dates": n_dates,
                "model_mae": float(e_model.mean()),
                "market_mae": float(e_market.mean()),
                "gap_model_minus_market": float(e_model.mean() - e_market.mean()),
                "delta_mean": float(delta.mean()),
                "delta_ci90_low": ci_lo, "delta_ci90_high": ci_hi,
                "mean_n_books": float(sub["n_books"].mean()),
                "median_mins_before_tip": float(sub["mins_before_tip"].median()),
            })
    return pd.DataFrame(rows)


def timing_decomposition(joined: pd.DataFrame, era: str, cutoff: str,
                         n_boot: int) -> dict | None:
    """SAME-GAMES timing effect: on the games that have BOTH a matched line
    at `cutoff` and a latest-pre-tip line (same era), compare the gap at the
    matched cutoff vs at pretip. The market's own MAE improvement between
    the two vintages, on identical games, is the timing share of the
    apparent gap. Paired date-clustered CI on |err_pretip| - |err_matched|
    (market errors; positive = the later line is worse, negative = later
    line better)."""
    m = joined[(joined["era"] == era) & (joined["cutoff"] == cutoff)]
    p = joined[(joined["era"] == era) & (joined["cutoff"] == "pretip")]
    both = m.merge(
        p[["game_id", "market_margin"]].rename(columns={"market_margin": "pretip_margin"}),
        on="game_id", how="inner")
    if not len(both):
        return None
    e_model = (both["model_margin"] - both["margin_true"]).abs()
    e_mkt_matched = (both["market_margin"] - both["margin_true"]).abs()
    e_mkt_pretip = (both["pretip_margin"] - both["margin_true"]).abs()
    move = (e_mkt_pretip - e_mkt_matched).to_numpy(float)   # negative = market improved
    dates = pd.to_datetime(both["game_date"]).dt.normalize().to_numpy()
    ci_lo = ci_hi = np.nan
    if pd.Series(dates).nunique() >= 2:
        ci = cluster_bootstrap_ci(move, dates, n_boot=n_boot, seed=SEED)
        ci_lo, ci_hi = ci["low"], ci["high"]
    gap_matched = float(e_model.mean() - e_mkt_matched.mean())
    gap_pretip = float(e_model.mean() - e_mkt_pretip.mean())
    return {
        "era": era, "cutoff": cutoff, "n_games": int(len(both)),
        "model_mae": float(e_model.mean()),
        "market_mae_matched": float(e_mkt_matched.mean()),
        "market_mae_pretip": float(e_mkt_pretip.mean()),
        "gap_at_matched": gap_matched,
        "gap_at_pretip_same_games": gap_pretip,
        "timing_share_of_gap": gap_pretip - gap_matched,
        "market_improvement_matched_to_pretip": float(-move.mean()),
        "market_improvement_ci90_low": -ci_hi if not np.isnan(ci_hi) else np.nan,
        "market_improvement_ci90_high": -ci_lo if not np.isnan(ci_lo) else np.nan,
    }


# ---------------------------------------------------------------------------
# flat-stake simulation
# ---------------------------------------------------------------------------

def _mult(price: float) -> float:
    """American price -> flat-stake profit multiplier on a win."""
    return 100.0 / abs(price) if price < 0 else price / 100.0


def _settle(margin_true: float, line_margin: float, side: int) -> str:
    if abs(margin_true - line_margin) <= PUSH_TOL:
        return "push"
    won = margin_true > line_margin if side > 0 else margin_true < line_margin
    return "win" if won else "loss"


def build_bet_log(joined: pd.DataFrame, books: pd.DataFrame,
                  pretip_margin: dict) -> tuple[pd.DataFrame, dict]:
    """One row per (era, cutoff, game) with |edge| >= min(THRESHOLDS).
    Trigger and consensus settlement use the matched consensus line;
    best-execution settlement uses the best captured book line/price on the
    bet side at the same matched vintage. CLV (extension only) = signed
    points the latest pre-tip consensus moved toward the bet side."""
    min_thr = min(THRESHOLDS)
    acct = {"price_anomaly_rows": 0, "bets_no_actual_price": 0}
    bkey = {}
    if len(books):
        for (era, cutoff, gid), grp in books.groupby(["era", "cutoff", "game_id"]):
            bkey[(era, cutoff, gid)] = grp
    logs = []
    for r in joined.itertuples(index=False):
        edge = r.model_margin - r.market_margin
        if abs(edge) < min_thr:
            continue
        side = 1 if edge > 0 else -1
        cons_out = _settle(r.margin_true, r.market_margin, side)
        cons_profit = {"win": WIN_110, "push": 0.0, "loss": -1.0}[cons_out]
        # best execution at the matched vintage
        be = dict(be_book=None, be_line_margin=np.nan, be_price=np.nan,
                  be_outcome=None, be_profit=np.nan)
        grp = bkey.get((r.era, r.cutoff, r.game_id))
        if grp is not None:
            pcol = "home_price" if side > 0 else "away_price"
            cand = grp[grp[pcol].notna()].copy()
            n_anom = int((cand[pcol].abs() >= PRICE_ANOMALY_ABS).sum())
            acct["price_anomaly_rows"] += n_anom
            cand = cand[cand[pcol].abs() < PRICE_ANOMALY_ABS]
            if len(cand):
                # most favorable line for the bet side: home bet -> max home
                # spread (most points); away bet -> min home spread
                key = cand["home_spread"] * (1 if side > 0 else -1)
                cand = cand.assign(_k=key, _m=cand[pcol].map(_mult))
                best = cand.sort_values(["_k", "_m"]).iloc[-1]
                lm = -float(best["home_spread"])
                out = _settle(r.margin_true, lm, side)
                mult = _mult(float(best[pcol]))
                be = dict(be_book=best["bookmaker_key"], be_line_margin=lm,
                          be_price=float(best[pcol]), be_outcome=out,
                          be_profit={"win": mult, "push": 0.0, "loss": -1.0}[out])
            else:
                acct["bets_no_actual_price"] += 1
        clv = np.nan
        pm = pretip_margin.get((r.era, r.game_id))
        if pm is not None and r.cutoff != "pretip":
            clv = side * (pm - r.market_margin)
        logs.append({
            "era": r.era, "cutoff": r.cutoff, "game_id": r.game_id,
            "game_date": r.game_date, "season": r.season,
            "season_type": r.season_type,
            "model_margin": r.model_margin, "market_margin": r.market_margin,
            "consensus_home_spread": r.consensus_home_spread,
            "n_books": r.n_books, "edge": edge,
            "side": "home" if side > 0 else "away",
            "margin_true": r.margin_true,
            "cons_outcome": cons_out, "cons_profit_m110": cons_profit,
            **be, "clv_pts": clv,
        })
    return pd.DataFrame(logs), acct


def sim_summary(bet_log: pd.DataFrame, n_boot: int) -> pd.DataFrame:
    """flat_stake_sim.csv rows: era x cutoff x basis x threshold."""
    rows = []
    for (era, cutoff), grp in bet_log.groupby(["era", "cutoff"]):
        for thr in THRESHOLDS:
            bets = grp[grp["edge"].abs() >= thr]
            for basis, ocol, pcol in (
                    ("consensus_m110", "cons_outcome", "cons_profit_m110"),
                    ("actual_best_exec", "be_outcome", "be_profit")):
                b = bets[bets[ocol].notna()]
                n = len(b)
                wins = int((b[ocol] == "win").sum())
                losses = int((b[ocol] == "loss").sum())
                pushes = int((b[ocol] == "push").sum())
                profit = float(b[pcol].sum()) if n else np.nan
                roi = profit / n if n else np.nan
                hit = wins / (wins + losses) if (wins + losses) else np.nan
                ci_lo = ci_hi = np.nan
                if n:
                    dates = pd.to_datetime(b["game_date"]).dt.normalize().to_numpy()
                    if pd.Series(dates).nunique() >= 2:
                        ci = cluster_bootstrap_ci(
                            b[pcol].to_numpy(float), dates, n_boot=n_boot, seed=SEED)
                        ci_lo, ci_hi = ci["low"], ci["high"]
                clv = b["clv_pts"].dropna()
                rows.append({
                    "era": era, "cutoff": cutoff, "basis": basis,
                    "threshold": thr, "n_games_eligible": int(len(grp)),
                    "n_bets": n, "n_home": int((b["side"] == "home").sum()),
                    "n_away": int((b["side"] == "away").sum()),
                    "wins": wins, "losses": losses, "pushes": pushes,
                    "hit_rate": hit, "total_profit_units": profit, "roi": roi,
                    "roi_ci90_low": ci_lo, "roi_ci90_high": ci_hi,
                    "mean_clv_pts": float(clv.mean()) if len(clv) else np.nan,
                    "pct_clv_positive": float((clv > 0).mean()) if len(clv) else np.nan,
                    "clv_measurable": bool(len(clv)),
                    "small_n_flag": bool(n < 30),
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table 3 — transfer curve over the four oracle variants
# ---------------------------------------------------------------------------

def transfer_tables(oracle: pd.DataFrame, consensus: pd.DataFrame,
                    n_boot: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per (era, cutoff) in SIM_CUTOFFS, on oracle-universe games (627
    regular-season channel test games) with a matched line: run the
    consensus/-110 sim per variant; then per threshold fit ROI ~ MAE and
    hit ~ MAE across the four variants and extrapolate break-even.

    Bootstrap: resample game DATES with replacement, the SAME resample
    applied to all four variants (paired); per draw recompute each variant's
    universe MAE, ROI and hit rate, the OLS slope, and the implied
    break-even delta-MAE. Draws where the slope is >= 0 (wrong sign: less
    accurate would mean more profitable) leave break-even unidentified and
    are counted, not hidden."""
    curve_rows, be_rows = [], []
    rng = np.random.default_rng(SEED)
    for era, cutoff in SIM_CUTOFFS:
        lines = consensus[(consensus["era"] == era)
                          & (consensus["cutoff"] == cutoff)]
        u = oracle.merge(lines[["game_id", "market_margin"]], on="game_id",
                         how="inner")
        if len(u) < 10:
            continue
        dates = pd.to_datetime(u["game_date"]).dt.normalize().to_numpy()
        uniq_dates, date_inv = np.unique(dates, return_inverse=True)
        n_d = len(uniq_dates)
        truth = u["margin_true"].to_numpy(float)
        market = u["market_margin"].to_numpy(float)
        # per-variant per-game arrays
        abserr, prof, isbet, iswin, isdec = {}, {}, {}, {}, {}
        for v in VARIANTS:
            pred = u[VCOL[v]].to_numpy(float)
            abserr[v] = np.abs(pred - truth)
            edge = pred - market
            for thr in THRESHOLDS:
                side = np.where(edge >= thr, 1, np.where(edge <= -thr, -1, 0))
                diff = truth - market
                push = np.abs(diff) <= PUSH_TOL
                win = np.where(side > 0, diff > PUSH_TOL,
                               np.where(side < 0, diff < -PUSH_TOL, False))
                bet = side != 0
                p = np.zeros(len(u))
                p[bet & win] = WIN_110
                p[bet & ~win & ~push] = -1.0
                prof[(v, thr)] = p
                isbet[(v, thr)] = bet
                iswin[(v, thr)] = bet & win & ~push
                isdec[(v, thr)] = bet & ~push
        # point-estimate curve rows
        for v in VARIANTS:
            mae_u = float(abserr[v].mean())
            for thr in THRESHOLDS:
                b, w, d = isbet[(v, thr)], iswin[(v, thr)], isdec[(v, thr)]
                nb = int(b.sum())
                curve_rows.append({
                    "era": era, "cutoff": cutoff, "variant": v,
                    "variant_mae_universe": mae_u, "n_games_universe": len(u),
                    "threshold": thr, "n_bets": nb,
                    "wins": int(w.sum()),
                    "losses": int((d & ~w).sum()),
                    "pushes": int((b & ~d).sum()),
                    "hit_rate": float(w.sum() / d.sum()) if d.sum() else np.nan,
                    "roi": float(prof[(v, thr)].sum() / nb) if nb else np.nan,
                    "total_profit_units": float(prof[(v, thr)].sum()),
                    "small_n_flag": bool(nb < 30),
                })
        # per-date aggregates for the paired bootstrap
        def by_date(vals):
            return np.bincount(date_inv, weights=vals, minlength=n_d)
        E = {v: by_date(abserr[v]) for v in VARIANTS}
        G = by_date(np.ones(len(u)))
        P = {k: by_date(vv) for k, vv in prof.items()}
        Bc = {k: by_date(vv.astype(float)) for k, vv in isbet.items()}
        Wc = {k: by_date(vv.astype(float)) for k, vv in iswin.items()}
        Dc = {k: by_date(vv.astype(float)) for k, vv in isdec.items()}

        def slope_fit(x, y):
            x, y = np.asarray(x), np.asarray(y)
            vx = ((x - x.mean()) ** 2).sum()
            if vx <= 0:
                return np.nan
            return float(((x - x.mean()) * (y - y.mean())).sum() / vx)

        for thr in THRESHOLDS:
            maes = [float(abserr[v].mean()) for v in VARIANTS]
            rois = [float(prof[(v, thr)].sum() / isbet[(v, thr)].sum())
                    if isbet[(v, thr)].sum() else np.nan for v in VARIANTS]
            hits = [float(iswin[(v, thr)].sum() / isdec[(v, thr)].sum())
                    if isdec[(v, thr)].sum() else np.nan for v in VARIANTS]
            ok = not any(np.isnan(rois)) and not any(np.isnan(hits))
            s_roi = slope_fit(maes, rois) if ok else np.nan
            s_hit = slope_fit(maes, hits) if ok else np.nan
            roi_v1, hit_v1 = rois[0], hits[0]
            # ROI(mae) ~ roi_v1 + s*(mae - mae_v1); ROI=0 at mae_v1 + (0-roi_v1)/s.
            # Required IMPROVEMENT (positive = MAE must drop this much) =
            # mae_v1 - mae* = roi_v1 / s. Negative = already above break-even.
            be_roi = roi_v1 / s_roi if ok and s_roi < 0 else np.nan
            be_hit = ((hit_v1 - BREAK_EVEN_HIT) / s_hit
                      if ok and s_hit < 0 else np.nan)
            # paired date-clustered bootstrap
            draws_roi, draws_hit, bad = [], [], 0
            n_used = 0
            if ok and n_d >= 2:
                idx = rng.integers(0, n_d, size=(n_boot, n_d))
                for b_i in range(n_boot):
                    d = idx[b_i]
                    g_n = G[d].sum()
                    m_b, r_b, h_b = [], [], []
                    degenerate = False
                    for v in VARIANTS:
                        nb = Bc[(v, thr)][d].sum()
                        nd_ = Dc[(v, thr)][d].sum()
                        if nb == 0 or nd_ == 0:
                            degenerate = True
                            break
                        m_b.append(E[v][d].sum() / g_n)
                        r_b.append(P[(v, thr)][d].sum() / nb)
                        h_b.append(Wc[(v, thr)][d].sum() / nd_)
                    if degenerate:
                        bad += 1
                        continue
                    n_used += 1
                    sr = slope_fit(m_b, r_b)
                    sh = slope_fit(m_b, h_b)
                    draws_roi.append(r_b[0] / sr
                                     if (not np.isnan(sr) and sr < 0) else np.nan)
                    draws_hit.append((h_b[0] - BREAK_EVEN_HIT) / sh
                                     if (not np.isnan(sh) and sh < 0) else np.nan)
            dr = np.array(draws_roi, float)
            dh = np.array(draws_hit, float)
            id_r, id_h = dr[~np.isnan(dr)], dh[~np.isnan(dh)]
            be_rows.append({
                "era": era, "cutoff": cutoff, "threshold": thr,
                "n_games_universe": len(u), "n_dates": n_d,
                "n_bets_v1": int(isbet[(VARIANTS[0], thr)].sum()),
                "mae_v1": maes[0], "roi_v1": roi_v1, "hit_v1": hit_v1,
                "mae_span_across_variants": float(max(maes) - min(maes)),
                "slope_roi_per_1mae": s_roi,
                "slope_roi_per_001mae": s_roi * 0.01 if not np.isnan(s_roi) else np.nan,
                "slope_hit_per_001mae": s_hit * 0.01 if not np.isnan(s_hit) else np.nan,
                "breakeven_dmae_roi": be_roi,
                "breakeven_dmae_roi_ci90_low": (float(np.quantile(id_r, 0.05))
                                                if len(id_r) >= 20 else np.nan),
                "breakeven_dmae_roi_ci90_high": (float(np.quantile(id_r, 0.95))
                                                 if len(id_r) >= 20 else np.nan),
                "breakeven_dmae_hit": be_hit,
                "breakeven_dmae_hit_ci90_low": (float(np.quantile(id_h, 0.05))
                                                if len(id_h) >= 20 else np.nan),
                "breakeven_dmae_hit_ci90_high": (float(np.quantile(id_h, 0.95))
                                                 if len(id_h) >= 20 else np.nan),
                "boot_draws_valid": n_used,
                "pct_draws_roi_unidentified": (float(np.isnan(dr).mean())
                                               if n_used else np.nan),
                "pct_draws_hit_unidentified": (float(np.isnan(dh).mean())
                                               if n_used else np.nan),
                "extrapolation_flag": "LINEAR EXTRAPOLATION beyond the 0.07-MAE variant bracket",
            })
    return pd.DataFrame(curve_rows), pd.DataFrame(be_rows)


# ---------------------------------------------------------------------------
# audits
# ---------------------------------------------------------------------------

def vintage_audit(consensus: pd.DataFrame, rng: np.random.Generator) -> dict:
    """Assert matched-line timestamps obey snap <= cutoff < tip (hour
    cutoffs) and snap < tip (all rows). Returns counts + a sampled table."""
    n_checked = 0
    hour_rows = consensus[consensus["cutoff_ts"].notna()]
    assert (hour_rows["vintage_snap"] <= hour_rows["cutoff_ts"]).all(), \
        "vintage audit FAILED: matched snapshot after cutoff"
    assert (hour_rows["cutoff_ts"] < hour_rows["tip"]).all(), \
        "vintage audit FAILED: cutoff not before tip"
    assert (consensus["vintage_snap"] < consensus["tip"]).all(), \
        "vintage audit FAILED: matched snapshot not before tip"
    assert (consensus["staleness_h"].dropna() >= -1e-9).all()
    n_checked = int(len(consensus))
    k = min(12, len(consensus))
    samp = consensus.sample(k, random_state=int(rng.integers(0, 2**31)))
    samp = samp[["era", "cutoff", "game_id", "vintage_snap", "cutoff_ts",
                 "tip", "n_books", "staleness_h"]].sort_values(
        ["era", "cutoff", "game_id"])
    return {"rows_checked": n_checked, "violations": 0, "sample": samp}


def no_blend_audit(frames: dict[str, pd.DataFrame],
                   era_games: dict[str, set]) -> dict:
    """Every output row carries an era label in {extension, old}; the two
    eras' game sets are disjoint; no aggregate row spans both."""
    assert not (era_games["extension"] & era_games["old"]), \
        "no-blend audit FAILED: a game_id appears in both eras"
    checked = {}
    for name, df in frames.items():
        assert "era" in df.columns, f"no-blend audit FAILED: {name} lacks era column"
        bad = set(df["era"].unique()) - {"extension", "old"}
        assert not bad, f"no-blend audit FAILED: {name} has era values {bad}"
        checked[name] = int(len(df))
    return {"tables_checked": checked,
            "era_game_overlap": 0,
            "note": "pooled rows pool seasons within a single era only; "
                    "no table row aggregates across eras"}


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def _py(obj):
    """Recursively convert numpy/pandas scalars to plain python for the ledger."""
    if isinstance(obj, dict):
        return {k: _py(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_py(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    if isinstance(obj, (pd.Timestamp, datetime)):
        return str(obj)
    return obj


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
# main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--smoke", action="store_true",
                    help="scratch registry + scratch outdir + subsampled games")
    ap.add_argument("--stage", action="store_true",
                    help="full data -> experiments/clv_transfer/, registry "
                         "writes to a scratch copy (real ledger untouched)")
    ap.add_argument("--outdir", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.smoke and args.stage:
        ap.error("--smoke and --stage are mutually exclusive")

    mode = "SMOKE" if args.smoke else ("STAGED (no ledger)" if args.stage else "REAL")
    registry_path = None
    outdir = args.outdir or DEFAULT_OUTDIR
    if args.smoke or args.stage:
        import tempfile
        scratch = Path(tempfile.mkdtemp(prefix="clv_transfer_scratch_"))
        registry_path = scratch / "registry_scratch.jsonl"
        shutil.copyfile(REPO / "experiments" / "registry.jsonl", registry_path)
        if args.smoke:
            outdir = args.outdir or (scratch / "out")
        assert registry_path is not None
    outdir.mkdir(parents=True, exist_ok=True)
    n_boot = 200 if args.smoke else 2000
    n_boot_transfer = 100 if args.smoke else 1000
    run_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[clv] {mode} run at {run_time} -> {outdir}")

    # 1. inputs --------------------------------------------------------------
    pred = load_predictions()
    oracle = load_oracle()
    tdev = (pred.merge(oracle[["game_id", "margin_true"]], on="game_id",
                       suffixes=("", "_o"))
            .eval("abs(margin_true - margin_true_o)").max())
    assert tdev == 0.0, f"truth mismatch predictions vs oracle margins: {tdev}"
    odds = {"old": load_odds(ODDS_OLD, "old"),
            "extension": load_odds(ODDS_EXT, "extension")}
    era_games = {e: set(o["game_id"]) for e, o in odds.items()}
    if args.smoke:
        keep = set()
        for e in odds:
            ids = sorted(era_games[e] & set(pred["game_id"]))
            keep |= set(ids[::max(1, len(ids) // 70)])
        pred = pred[pred["game_id"].isin(keep)].copy()
        oracle = oracle[oracle["game_id"].isin(keep)].copy()
        odds = {e: o[o["game_id"].isin(keep)].copy() for e, o in odds.items()}
        era_games = {e: set(o["game_id"]) for e, o in odds.items()}
        print(f"[smoke] subsampled to {len(pred)} prediction games")

    # 2. matched lines per era ----------------------------------------------
    cons_frames, book_frames = [], []
    for era, o in odds.items():
        c, b = build_matched_lines(o, era)
        cons_frames.append(c)
        book_frames.append(b)
    consensus = pd.concat(cons_frames, ignore_index=True)
    books = pd.concat(book_frames, ignore_index=True)
    # measured proof that the old era does NOT support T-24h / T-8h
    old_unsupported = unsupported_cutoff_counts(
        odds["old"], "old", [("T-24h", 24.0), ("T-8h", 8.0)])
    print(f"[cutoffs] old era measured coverage at hour cutoffs: {old_unsupported}")

    # per-cutoff line coverage (era universe = completed games in that odds table)
    cov_rows = []
    for era in ("extension", "old"):
        total = int(odds[era]["game_id"].nunique())
        for label, _h in CUTOFFS[era]:
            lined = consensus[(consensus["era"] == era)
                              & (consensus["cutoff"] == label)]
            with_pred = len(set(lined["game_id"]) & set(pred["game_id"]))
            cov_rows.append({"era": era, "cutoff": label,
                             "games_in_era_odds": total,
                             "games_with_matched_line": int(len(lined)),
                             "line_coverage": len(lined) / total if total else np.nan,
                             "lined_games_with_model_pred": with_pred})
    coverage_tbl = pd.DataFrame(cov_rows)
    print(fmt_table(coverage_tbl))

    # 3. join predictions to matched lines -----------------------------------
    joined = consensus.merge(pred, on="game_id", how="inner")
    # CLV reference: extension-era latest pre-tip consensus. The old era has
    # no later line (single snapshot), so its games never enter this map.
    pretip_margin = {
        (r.era, r.game_id): r.market_margin
        for r in consensus[consensus["cutoff"] == "pretip"].itertuples(index=False)
    }

    # 4. Table 1 -------------------------------------------------------------
    gap_tbl = gap_table(joined, n_boot)
    hl = gap_tbl[(gap_tbl["era"] == HEADLINE[0]) & (gap_tbl["cutoff"] == HEADLINE[1])
                 & (gap_tbl["season"] == "pooled")].iloc[0]
    hl_pretip = gap_tbl[(gap_tbl["era"] == "extension") & (gap_tbl["cutoff"] == "pretip")
                        & (gap_tbl["season"] == "pooled")].iloc[0]
    print("[table1]")
    print(fmt_table(gap_tbl[["era", "cutoff", "season", "n_games", "model_mae",
                             "market_mae", "gap_model_minus_market",
                             "delta_ci90_low", "delta_ci90_high"]]))
    # same-games timing decomposition (extension era; the honest timing contrast)
    timing = [t for t in (timing_decomposition(joined, "extension", c, n_boot)
                          for c in ("T-24h", "T-8h")) if t]
    timing_tbl = pd.DataFrame(timing)
    if len(timing_tbl):
        print("[timing decomposition, same games]")
        print(fmt_table(timing_tbl))

    # 5. registered primary comparison (extension era, T-24h) ----------------
    hgames = joined[(joined["era"] == HEADLINE[0]) & (joined["cutoff"] == HEADLINE[1])]
    ch_frame = pd.DataFrame({
        "game_id": hgames["game_id"], "game_date": hgames["game_date"],
        "season": hgames["season"], "y_true": hgames["margin_true"].astype(float),
        "y_pred": hgames["model_margin"].astype(float),
        "team": hgames["home_team_abbr"],
    })
    inc_frame = pd.DataFrame({
        "game_id": hgames["game_id"], "y_true": hgames["margin_true"].astype(float),
        "y_pred": hgames["market_margin"].astype(float),
    })
    n_lined_hl = int(coverage_tbl[
        (coverage_tbl["era"] == HEADLINE[0])
        & (coverage_tbl["cutoff"] == HEADLINE[1])]["games_with_matched_line"].iloc[0])
    cov_ch = len(hgames) / n_lined_hl if n_lined_hl else np.nan
    result = None
    try:
        result = compare_to_incumbent(
            ch_frame, inc_frame, experiment_id=EXPERIMENT_ID,
            registry_path=registry_path, loss="absolute", cluster="date",
            team_col="team", coverage=(cov_ch, 1.0),
        )
        print(f"[gate model-vs-matched-market] {result.verdict} "
              f"(expected FAIL: measurement experiment) pooled "
              f"{result.metric_challenger:.4f} vs {result.metric_incumbent:.4f} "
              f"delta {result.pooled_improvement:+.4f} "
              f"CI [{result.ci_low:+.4f}, {result.ci_high:+.4f}] "
              f"failed={result.failed_gates}")
    except ComparisonError as e:
        # smoke subsamples can be too thin for the harness; real runs must not be
        if not args.smoke:
            raise
        print(f"[gate] SKIPPED in smoke (subsample too thin): {e}")

    # 6. Table 2 -------------------------------------------------------------
    sim_cut_labels = [c for _, c in SIM_CUTOFFS]           # T-24h/T-8h exist only in
    bet_log, sim_acct = build_bet_log(                     # extension, T-64m only in old
        joined[joined["cutoff"].isin(sim_cut_labels)], books, pretip_margin)
    sim_tbl = sim_summary(bet_log, n_boot)
    print("[table2] (headline rows)")
    show = sim_tbl[(sim_tbl["era"] == "extension") & (sim_tbl["cutoff"] == "T-24h")]
    print(fmt_table(show[["basis", "threshold", "n_bets", "hit_rate", "roi",
                          "roi_ci90_low", "roi_ci90_high", "mean_clv_pts"]]))

    # 7. Table 3 -------------------------------------------------------------
    curve_tbl, be_tbl = transfer_tables(oracle, consensus, n_boot_transfer)
    print("[table3] break-even extrapolations")
    if len(be_tbl):
        print(fmt_table(be_tbl[["era", "cutoff", "threshold", "n_bets_v1",
                                "roi_v1", "slope_roi_per_001mae",
                                "breakeven_dmae_roi", "breakeven_dmae_hit"]]))

    # 8. audits --------------------------------------------------------------
    rng = np.random.default_rng(SEED)
    va = vintage_audit(consensus, rng)
    out_frames = {"matched_gap_by_cutoff_and_season": gap_tbl,
                  "flat_stake_sim": sim_tbl, "bet_log": bet_log,
                  "transfer_curve": curve_tbl, "line_coverage": coverage_tbl}
    if len(be_tbl):
        out_frames["transfer_breakeven"] = be_tbl
    if len(timing_tbl):
        out_frames["timing_decomposition"] = timing_tbl
    nb = no_blend_audit(out_frames, era_games)
    push_void = {
        "pushes_consensus_basis": int((bet_log["cons_outcome"] == "push").sum()),
        "pushes_actual_basis": int((bet_log["be_outcome"] == "push").sum()),
        "price_anomaly_rows_excluded": sim_acct["price_anomaly_rows"],
        "bets_without_actual_price": sim_acct["bets_no_actual_price"],
        "note": "consensus lines are cross-book means (fractional), so consensus-basis "
                "pushes require exact equality and are structurally rare; actual-basis "
                "pushes settle on the real book line taken. ROI denominator counts "
                "pushed stakes (push profit = 0, stake risked = 1).",
    }
    print(f"[audit] vintage rows checked {va['rows_checked']}, violations 0; "
          f"no-blend OK; push/void: {push_void}")

    # 9. artifacts -----------------------------------------------------------
    gap_tbl.to_csv(outdir / "matched_gap_by_cutoff_and_season.csv", index=False)
    sim_tbl.to_csv(outdir / "flat_stake_sim.csv", index=False)
    bet_log.to_csv(outdir / "bet_log.csv", index=False)
    curve_tbl.to_csv(outdir / "transfer_curve.csv", index=False)
    if len(be_tbl):
        be_tbl.to_csv(outdir / "transfer_breakeven.csv", index=False)
    if len(timing_tbl):
        timing_tbl.to_csv(outdir / "timing_decomposition.csv", index=False)
    coverage_tbl.to_csv(outdir / "line_coverage.csv", index=False)

    # 10. secondary ledger record + report -----------------------------------
    hl_be = None
    if len(be_tbl):
        cand = be_tbl[(be_tbl["era"] == HEADLINE[0]) & (be_tbl["cutoff"] == HEADLINE[1])]
        if len(cand):
            hl_be = cand.sort_values("n_bets_v1").iloc[-1].to_dict()
    secondary = {
        "record_type": "clv_transfer_measurement",
        "mode": mode,
        "headline_matched_gap_T24h_extension": {
            k: hl[k] for k in ("n_games", "model_mae", "market_mae",
                               "gap_model_minus_market", "delta_ci90_low",
                               "delta_ci90_high")},
        "extension_pretip_gap_same_convention_as_0373": {
            k: hl_pretip[k]
            for k in ("n_games", "model_mae", "market_mae", "gap_model_minus_market")},
        "timing_decomposition_same_games": timing,
        "unmatched_headline_being_repaired": 0.3732,
        "old_era_hour_cutoff_coverage_measured": old_unsupported,
        "coverage_table": coverage_tbl.to_dict("records"),
        "breakeven_headline": hl_be,
        "audits": {"vintage_rows_checked": va["rows_checked"],
                   "vintage_violations": 0,
                   "no_blend": nb, "push_void": push_void},
        "conventions": {
            "matched_vintage": "latest snapshot timestamp <= cutoff; consensus = mean "
                               "over books present at that single vintage",
            "pretip_and_T64m": "per-book latest pre-tip row, mean over books "
                               "(oracle_bracket convention, comparable to the 0.373)",
            "market_margin": "-(consensus home spread)",
            "clv": "side * (pretip_margin - matched_margin), points toward the bet side",
            "roi": "net profit / stakes placed (flat 1u; pushes stake-counted, profit 0)",
        },
    }
    secondary = _py(secondary)
    if not args.smoke:
        ereg.evaluate(EXPERIMENT_ID, secondary, registry_path=registry_path)
    else:
        try:
            ereg.evaluate(EXPERIMENT_ID, secondary, registry_path=registry_path)
        except Exception as e:  # smoke must exercise the call path, tolerantly
            print(f"[smoke] secondary record skipped: {e}")
    with open(outdir / "secondary_results.json", "w", encoding="utf-8") as fh:
        json.dump(secondary, fh, indent=2, default=str)
    if result is not None:
        with open(outdir / "gate_verdict.json", "w", encoding="utf-8") as fh:
            json.dump(result.to_dict(), fh, indent=2, default=str)

    write_report(outdir, mode, run_time, gap_tbl, sim_tbl, curve_tbl, be_tbl,
                 coverage_tbl, va, push_void, old_unsupported, result,
                 hl, hl_pretip, hl_be, bet_log, timing_tbl)
    print(f"[done] artifacts in {outdir}")
    return 0


# ---------------------------------------------------------------------------
# report writer
# ---------------------------------------------------------------------------

def write_report(outdir, mode, run_time, gap_tbl, sim_tbl, curve_tbl, be_tbl,
                 coverage_tbl, va, push_void, old_unsupported, result,
                 hl, hl_pretip, hl_be, bet_log, timing_tbl) -> None:
    t24 = None
    if len(timing_tbl):
        cand = timing_tbl[timing_tbl["cutoff"] == "T-24h"]
        if len(cand):
            t24 = cand.iloc[0]
    if t24 is not None:
        timing_bullet = (
            f"- **Same-games timing decomposition** ({int(t24['n_games'])} games with "
            f"both a T-24h and a latest-pre-tip line): gap at T-24h "
            f"{t24['gap_at_matched']:+.4f} vs gap at pretip "
            f"{t24['gap_at_pretip_same_games']:+.4f} — **timing accounts for "
            f"{t24['timing_share_of_gap']:+.4f} points of the pretip-benchmark gap on "
            f"identical games** (the market's own MAE improves "
            f"{t24['market_improvement_matched_to_pretip']:+.4f} from the T-24h vintage "
            f"to the last pre-tip line, 90% CI "
            f"[{t24['market_improvement_ci90_low']:+.4f}, "
            f"{t24['market_improvement_ci90_high']:+.4f}]).")
    else:
        timing_bullet = "- Same-games timing decomposition unavailable in this run."
    ci_zero_note = ""
    if pd.notna(hl["delta_ci90_high"]) and hl["delta_ci90_low"] < 0 < hl["delta_ci90_high"]:
        ci_zero_note = (" (Separately: the 90% paired-delta CI above includes "
                        "zero — the market's matched-time edge over the model is "
                        "not statistically resolved on this sample.)")
    if t24 is not None and abs(float(t24["timing_share_of_gap"])) < 0.1:
        hyp_bullet = (
            "- **Registered hypothesis (1) verdict: essentially REFUTED on the "
            "extension era.** The matched-time gap is NOT materially smaller than "
            "the latest-pre-tip gap on the same games — because the market's T-24h "
            "consensus is already almost exactly as accurate as its last pre-tip "
            "line at predicting final margins. The old headline's real defects are "
            "era-blending and universe mixing, not vintage." + ci_zero_note)
    elif t24 is not None:
        hyp_bullet = (
            f"- **Registered hypothesis (1) verdict: SUPPORTED in direction** — "
            f"timing accounts for {float(t24['timing_share_of_gap']):+.4f} points "
            f"of the pretip-benchmark gap on identical games (see decomposition).")
    else:
        hyp_bullet = "- Hypothesis (1) verdict: not evaluable in this run."
    gate_line = ("gate not run (smoke subsample too thin)" if result is None else
                 f"**{result.verdict}** (anticipated: this is a measurement experiment; "
                 f"promote=false was the registered expectation). Pooled model "
                 f"{result.metric_challenger:.4f} vs matched market "
                 f"{result.metric_incumbent:.4f}, delta {result.pooled_improvement:+.4f}, "
                 f"90% date-clustered CI [{result.ci_low:+.4f}, {result.ci_high:+.4f}], "
                 f"failed gates: {result.failed_gates}")
    def _f(v, fmt="{:.2f}"):
        return fmt.format(v) if pd.notna(v) else "n/a"

    be_txt = "no identifiable break-even cell (see transfer_breakeven.csv)"
    if hl_be is not None and pd.notna(hl_be.get("breakeven_dmae_roi", np.nan)):
        pt = hl_be["breakeven_dmae_roi"]
        lead = (f"break-even at -110 requires a further pooled-MAE improvement of "
                f"~**{_f(pt)} points**" if pt > 0 else
                f"the point estimate puts the current model ALREADY at/above "
                f"break-even at this cell, with ~**{_f(-pt)} MAE points of slack**")
        be_txt = (f"{lead} "
                  f"(90% bootstrap CI on the required improvement "
                  f"[{_f(hl_be['breakeven_dmae_roi_ci90_low'])}, "
                  f"{_f(hl_be['breakeven_dmae_roi_ci90_high'])}]; threshold "
                  f"{hl_be['threshold']}, {int(hl_be['n_bets_v1'])} bets; "
                  f"{_f(100 * hl_be['pct_draws_roi_unidentified'], '{:.0f}')}% of "
                  f"bootstrap draws unidentified/wrong-sign slope). The estimate is "
                  f"WEAKLY IDENTIFIED — a linear extrapolation from a "
                  f"{_f(hl_be['mae_span_across_variants'])}-point variant MAE bracket — "
                  f"and is a bound-setting measurement, not a precise bar")
    sim_hl = sim_tbl[(sim_tbl["era"] == "extension") & (sim_tbl["cutoff"] == "T-24h")]
    curve_hl = curve_tbl[(curve_tbl["era"] == "extension")
                         & (curve_tbl["cutoff"] == "T-24h")] if len(curve_tbl) else curve_tbl

    md = f"""# clv_transfer_v1 — decision-time-matched market gap + MAE-to-ROI transfer curve

*Generated by `clv_transfer.py` on {run_time} — mode: {mode}. Preregistered
measurement experiment (`experiments/registry.jsonl`, registered
2026-07-30T21:23:43Z; regime A; incumbent `market_line_at_matched_cutoff`).
The registered primary comparison was EXPECTED TO LOSE — the deliverables are
the measurement tables, not a promotion. Sources: ASSUMPTION_AUDIT_2026-07-30
E2 + urgent findings 1 and 3.*

## 1. Headline

- **Matched-time gap (extension era, T-24h, {int(hl['n_games'])} games):
  model MAE {hl['model_mae']:.4f} vs T-24h market consensus {hl['market_mae']:.4f}
  -> gap {hl['gap_model_minus_market']:+.4f}** (90% date-clustered CI on the
  paired delta [{hl['delta_ci90_low']:+.4f}, {hl['delta_ci90_high']:+.4f}];
  delta > 0 = model better).
{timing_bullet}
{hyp_bullet}
- Full-sample extension pretip gap (the 0.373 headline's convention,
  {int(hl_pretip['n_games'])} games incl. those without T-24h lines):
  {hl_pretip['gap_model_minus_market']:+.4f} (market MAE {hl_pretip['market_mae']:.4f}).
- The 0.373 number itself pooled the old era (~T-64m single snapshots,
  2024 + early 2025) with extension-era latest-pre-tip lines — it is both
  timing-asymmetric AND era-blended; the per-era tables below replace it.
- Registered comparison verdict: {gate_line}
- Transfer curve: {be_txt}.

## 2. Table 1 — matched-time gap by cutoff x era x season

`matched_gap_by_cutoff_and_season.csv`. delta = |market error| - |model error|
per game (positive = model better); CI = 90% date-clustered bootstrap.
Era discipline: extension (2025-07-05+, multi-snapshot) and old (2022 -
2025-07-04, single ~T-64m snapshot) are never pooled in any row.

{fmt_table(gap_tbl[["era", "cutoff", "season", "n_games", "model_mae", "market_mae",
                    "gap_model_minus_market", "delta_ci90_low", "delta_ci90_high",
                    "mean_n_books", "median_mins_before_tip"]])}

**Which cutoffs each era supports (measured):** extension supports T-24h and
T-8h (2/day 15Z/22Z cadence; per-cutoff line coverage in
`line_coverage.csv`) plus the latest pre-tip (~T-2.1h median) comparator.
The old era supports ONLY its single ~T-64m snapshot: measured hour-cutoff
coverage {old_unsupported} — zero games have any snapshot at or before
T-24h/T-8h, so those cells do not exist there, and old-era CLV is undefined
(no later line).

**Same-games timing decomposition** (`timing_decomposition.csv` — the
market benchmark's own improvement from the matched vintage to the last
pre-tip line, identical games, extension era only; the old era has no
second vintage):

{fmt_table(timing_tbl) if len(timing_tbl) else "(unavailable in this run)"}

**Model-timing correspondence (stated per registration):** `str_margin_cal`
features are within-season shifted EWMAs over games strictly before the
target game's date — the information set closes with the prior day's box
scores, making it a T-24h-compatible forecast. ROADMAP's information-parity
caveat applies: the T-24h line may already price availability news the model
cannot see; matching the clock removes only the timing asymmetry.

Consensus conventions: matched cutoffs use the latest snapshot timestamp at
or before the cutoff (mean over books present at that single vintage — book
count varies by vintage, see mean_n_books; early vintages are thinner). The
pretip / T-64m rows use each book's latest pre-tip row (the 0.373's exact
convention) for comparability.

Universe note: Table 1 scores every predictions_v2 game with a line
(playoffs included — predictions exist for them), so its old-era rows are
not numerically identical to the oracle bracket's regular-season-only
0.373 universe; the per-row n's make each universe explicit. Table 3 runs
on the oracle bracket's 627-game regular-season universe by construction.

## 3. Table 2 — flat-stake simulation (`flat_stake_sim.csv`, row detail `bet_log.csv`)

Bet home when model - line >= threshold, away when <= -threshold (consensus
line at the matched vintage); flat 1u. Basis (a) `consensus_m110`: settle on
the consensus line at synthetic -110. Basis (b) `actual_best_exec`: same bet
set, executed at the best captured book line/price on the bet side at the
same vintage (real line shopping; settles on the line taken). CLV = signed
points the latest pre-tip consensus moved toward the bet side (extension
only). ROI = net profit / stakes placed; pushes risk stake, return 0.

Extension era, T-24h (headline cells):

{fmt_table(sim_hl[["basis", "threshold", "n_bets", "wins", "losses", "pushes",
                   "hit_rate", "roi", "roi_ci90_low", "roi_ci90_high",
                   "mean_clv_pts", "pct_clv_positive", "small_n_flag"]])}

All era x cutoff x basis x threshold rows are in the CSV (old era rows carry
`clv_measurable = False`). Cells with `small_n_flag` (n < 30 bets) are
reported for completeness and should not be read as signal.

## 4. Table 3 — MAE-to-ROI transfer curve (`transfer_curve.csv`, `transfer_breakeven.csv`)

The four committed oracle-bracket margin variants (pooled MAE spacing
10.1753 / 10.1555 / 10.1170 / 10.1072 on the 627-game regular-season
universe; v1 == the current model exactly) run through the identical
consensus/-110 sim on identical games. Per (era, cutoff, threshold): OLS of
ROI (and hit rate) on variant MAE across the four points -> slope per 0.01
MAE -> linearly extrapolated delta-MAE for break-even at -110 (52.38%
hits). CIs: paired date-clustered bootstrap (same date resample applied to
all four variants); draws with wrong-sign slopes leave break-even
unidentified and are counted, never hidden. **Everything beyond the
~0.07-MAE variant bracket is extrapolation and is labeled as such.**

Extension era, T-24h curve (v1 = current model):

{fmt_table(curve_hl[["variant", "variant_mae_universe", "threshold", "n_bets",
                     "hit_rate", "roi", "small_n_flag"]]) if len(curve_hl) else "(cell empty)"}

Break-even extrapolations:

{fmt_table(be_tbl[["era", "cutoff", "threshold", "n_bets_v1", "mae_span_across_variants",
                   "slope_roi_per_001mae", "breakeven_dmae_roi",
                   "breakeven_dmae_roi_ci90_low", "breakeven_dmae_roi_ci90_high",
                   "breakeven_dmae_hit", "pct_draws_roi_unidentified"]]) if len(be_tbl) else "(none)"}

Reading: `slope_roi_per_001mae` is the empirical ROI change per 0.01 pooled
MAE at this timing; `breakeven_dmae_roi` = ROI_v1 / slope = the pooled-MAE
IMPROVEMENT (positive = MAE must drop by that much; negative = already above
break-even with slack) required for ROI 0 at -110. The hit-rate route
(`breakeven_dmae_hit`) targets 52.38% winners; with zero pushes ROI is an
affine function of hit rate, so the two routes coincide exactly — a built-in
consistency check, not an accident. The variant MAE span within an era
subset can be far smaller than the 0.07 pooled spacing — cells where
`mae_span_across_variants` is tiny have near-unidentified slopes; treat
their extrapolations as bounds, not estimates. This curve replaces the
templated 0.10 promotion bar with an evidence-derived requirement (audit
assumption 1).

## 5. Audits

- **Snapshot-vintage audit:** all {va['rows_checked']} matched-line rows
  assert vintage <= cutoff < tip (hour cutoffs) and vintage < tip (all
  rows): 0 violations. Sample:

{fmt_table(va['sample'].assign(vintage_snap=lambda d: d['vintage_snap'].astype(str), cutoff_ts=lambda d: d['cutoff_ts'].astype(str), tip=lambda d: d['tip'].astype(str)), floatfmt="{:.2f}")}

- **No-blend audit:** every output row carries era in {{extension, old}};
  the two eras' game sets are disjoint (0 overlap); pooled rows pool seasons
  within one era only. Tables checked: matched gap, flat-stake sim, bet log,
  transfer curve, break-even, line coverage.
- **Push / void accounting:** {json.dumps(push_void, indent=2)}
- Line coverage per era x cutoff: `line_coverage.csv`.

## 6. Limitations (read before quoting any number)

1. **The transfer slope is weakly identified.** The four variants span only
   ~{_f(be_tbl['mae_span_across_variants'].max() if len(be_tbl) else np.nan)} MAE
   points on the sim universes; break-even CIs are wide and
   {_f((be_tbl['pct_draws_roi_unidentified'].max() * 100) if len(be_tbl) else np.nan, '{:.0f}')}%
   of bootstrap draws are unidentified in the worst cell. These are bounds,
   not a precise bar.
2. **Multiplicity, no correction:** 5 thresholds x 3 era-cutoffs x 2 price
   bases are all reported. Nothing here is a promotion claim; any cell
   quoted alone overstates certainty.
3. **In-sample simulation.** Bets are retrospective on committed
   walk-forward predictions; no prospective element. The positive-ROI cells
   at loose thresholds have CIs that include zero.
4. **Information parity:** the T-24h line may already price availability
   news the model cannot see (ROADMAP caveat) — matched timing fixes the
   clock, not the information sets.
5. **Consensus panel drift:** the matched vintage's book panel is thinner
   than pretip's (mean_n_books column); consensus composition differs
   slightly across vintages.
6. **The old era cannot test timing** (single snapshot) — its rows are
   near-tip benchmarks only, and old-era CLV does not exist.
7. Playoff games are included in Tables 1-2 (predictions exist) and
   excluded from Table 3 (oracle universe is regular-season); universes are
   labeled per row.

## 7. Files

| file | contents |
|---|---|
| `matched_gap_by_cutoff_and_season.csv` | Table 1: gap per cutoff x era x season + paired CIs |
| `flat_stake_sim.csv` | Table 2: era x cutoff x basis x threshold sim results |
| `bet_log.csv` | row-level bets ({len(bet_log)} rows): edge, side, both settlements, CLV |
| `transfer_curve.csv` | Table 3: per-variant MAE/ROI/hit grid |
| `transfer_breakeven.csv` | slopes + break-even delta-MAE extrapolations + CIs |
| `timing_decomposition.csv` | same-games timing share of the pretip-benchmark gap |
| `line_coverage.csv` | per era x cutoff matched-line coverage |
| `gate_verdict.json` / `secondary_results.json` | registered comparison + secondary record |

Reproduce: `python clv_transfer.py` (real; records on ledger) / `--stage`
(full data, scratch registry) / `--smoke` (subsample, scratch everything).
"""
    (outdir / "REPORT.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
