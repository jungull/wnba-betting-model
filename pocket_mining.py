"""pocket_mining.py — preregistered measurement study ``bet_pocket_mining_v1``.

Registered 2026-07-31T14:19:57Z in experiments/registry.jsonl (binding record;
regime A, primary metric ``pocket_roi_flat_stake``, incumbent
``market_at_matched_timing``). MEASUREMENT STUDY — no promotion. Retrospective
mining can only produce CANDIDATES; the confirmation channel is the live
prospective log (surviving pockets get preregistered as paper-trade cells in
prospective registrations and graded on future games only).

The registration's features_desc IS the closed slice battery — nothing added,
nothing dropped:

  disagreement threshold {0.5, 1, 1.5, 2, 3}
  x timing {T-24h, near-tip}            (T-24h exists only in the extension era)
  x bet type {spread, total, moneyline} (totals/ML extension era only)
  x execution {consensus, best-book}
  x ONE conditioning dimension at a time:
      none (the unconditioned base cell)
      line-magnitude terciles  |consensus spread| {small, mid, large}
      market-total terciles    consensus total {low, mid, high}   (extension only)
      bet side {home, away, fav, dog} (spread/ML) / {over, under} (totals)
      rest-differential sign {home_more, equal, away_more}
      season phase (team game number) {early <=10, mid 11-30, late >30}
      weekend flag {weekend, weekday}

Cells are the CROSS of (threshold, timing, bet type, execution) with one
conditioner level — NOT the full cross of all conditioners. ENUMERATION.md
documents the count.

Era discipline is ABSOLUTE (the registration's rule): the old era
(data/drive_masters/master_odds.csv — spreads only, single ~T-64m snapshot,
2022-2025/07) and the extension era (data/odds_capture/
master_odds_extension*.csv — spreads/totals/h2h with line paths, 2025/07+)
are NEVER pooled in one number; every output row carries its era.

Frozen model inputs: ``str_margin_cal`` + ``str_total_cal`` from
experiments/channel_reval/predictions_v2.csv; Gaussian cover machinery
(center = str_margin_cal, sigma = 12.9022) from
experiments/dist_margin_cover/game_level_dist.csv. Moneyline model prob =
P(margin > 0) = Phi(center / sigma) — the cover formula at spread 0 — vs the
proportionally devigged h2h consensus.

HONESTY MACHINERY (registered): 90% date-clustered bootstrap CI per cell;
null calibration by 200 within-era permutations of the model column across
games (margin + total shuffled JOINTLY, one draw per battery recompute);
per-cell p = fraction of permuted batteries with equal-or-better ROI in that
cell; Benjamini-Hochberg at 10% across all starred-eligible (n >= 40) cells;
survivors always reported next to the expected-false companion count.
Zero survivors is a legitimate result.

Run:  python pocket_mining.py --smoke   # the ONLY mode this study runs:
                                        #   scratch registry copy (guard; this
                                        #   study makes no registry calls),
                                        #   full data, artifacts to
                                        #   experiments/pocket_mining/
      python pocket_mining.py           # identical outputs; ledger recording,
                                        #   if any, is the orchestrator's job
Dev-only knobs: --outdir, --n-perms, --n-boot (defaults are the registered
200 / 2000; reduce ONLY for scratch iterations, never for the real artifact).

This script NEVER runs git, NEVER calls registry.register / evaluate /
record_evaluation / render_leaderboards, NEVER writes experiments/registry.jsonl,
and touches nothing outside experiments/pocket_mining/ (plus this file).
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# read-only imports: bootstrap CI (house convention) + the Gaussian primitives
# of the dist_margin_cover machinery (registration: cover machinery reused).
from evalharness.compare import cluster_bootstrap_ci, ComparisonError  # noqa: E402
from dist_margin_cover import norm_cdf, norm_ppf  # noqa: E402

PRED = REPO / "experiments" / "channel_reval" / "predictions_v2.csv"
DIST = REPO / "experiments" / "dist_margin_cover" / "game_level_dist.csv"
ODDS_OLD = REPO / "data" / "drive_masters" / "master_odds.csv"
ODDS_EXT = REPO / "data" / "odds_capture" / "master_odds_extension.csv"
ODDS_EXT_OTHER = REPO / "data" / "odds_capture" / "master_odds_extension_other_markets.csv"
MASTER_TEAM = REPO / "data" / "masters" / "master_team.csv"
CLV_SIM = REPO / "experiments" / "clv_transfer" / "flat_stake_sim.csv"
DEFAULT_OUTDIR = REPO / "experiments" / "pocket_mining"
EXPERIMENT_ID = "bet_pocket_mining_v1"

THRESHOLDS = [0.5, 1.0, 1.5, 2.0, 3.0]
EXECUTIONS = ["consensus", "best_book"]
WIN_110 = 100.0 / 110.0
PUSH_TOL = 1e-9
PRICE_ANOMALY_ABS = 10000        # |american price| >= this -> unusable (counted)
P_CLIP = 1e-4                    # devig prob clip before norm_ppf (counted)
SEED = 20260731
N_PERMS_DEFAULT = 200            # registered
N_BOOT_DEFAULT = 2000            # house convention (clv_transfer)
MIN_CELL_N = 40                  # registered starred-eligibility floor
BH_Q = 0.10                      # registered FDR level
ROI_TIE_EPS = 1e-12

# timing battery per era (registration: T-24h extension only; near-tip = the
# latest pre-tip per-book convention in the extension era and the single
# ~T-64m snapshot — which IS the latest pre-tip line — in the old era)
TIMING_SPEC = {
    "extension": [("T-24h", 24.0), ("near-tip", None)],
    "old": [("near-tip", None)],
}
BET_TYPES = {"extension": ["spread", "total", "moneyline"], "old": ["spread"]}
CLV_TIMING = "T-24h"             # the only timing with a later reference line

KNOWN_PRIOR_POCKET = dict(era="extension", timing="T-24h", bet_type="spread",
                          threshold=0.5, execution="consensus",
                          cond_dim="none", cond_level="all")


# ---------------------------------------------------------------------------
# small primitives
# ---------------------------------------------------------------------------

def _mult(price: float) -> float:
    """American price -> flat-stake profit multiplier on a win."""
    return 100.0 / abs(price) if price < 0 else price / 100.0


def _amer_prob(price: float) -> float:
    """American price -> implied probability (with vig)."""
    return (-price) / ((-price) + 100.0) if price < 0 else 100.0 / (price + 100.0)


def _settle(actual: float, line_value: float, side: int) -> str:
    """Grade side (+1 = home/over, -1 = away/under) vs a line value on the
    same scale as ``actual`` (margin vs market_margin; total vs total line)."""
    if abs(actual - line_value) <= PUSH_TOL:
        return "push"
    won = actual > line_value if side > 0 else actual < line_value
    return "win" if won else "loss"


_OUT_CODE = {"win": 1, "push": 0, "loss": -1}


def self_test() -> None:
    assert _settle(5.0, 5.0 + 1e-12, 1) == "push"
    assert _settle(3.0, 2.5, 1) == "win" and _settle(3.0, 2.5, -1) == "loss"
    assert abs(_mult(-110) - WIN_110) < 1e-12 and abs(_mult(150) - 1.5) < 1e-12
    qh, qa = _amer_prob(-250), _amer_prob(207)
    assert abs(qh / (qh + qa) - 0.6868) < 1e-3
    assert abs(_amer_prob(-110) / (2 * _amer_prob(-110)) - 0.5) < 1e-12
    assert abs(float(norm_cdf(0.0)) - 0.5) < 1e-12
    assert abs(float(norm_ppf(float(norm_cdf(1.0)))) - 1.0) < 1e-9
    # BH toy: p=[0.01, 1x9] at q=0.10 -> exactly the first rejected
    q = bh_qvalues(np.array([0.01] + [1.0] * 9))
    assert q[0] <= 0.10 and (q[1:] > 0.10).all()


def bh_qvalues(p: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg adjusted q-values (step-up, plain BH)."""
    p = np.asarray(p, float)
    m = len(p)
    order = np.argsort(p, kind="stable")
    ranked = p[order] * m / (np.arange(m) + 1.0)
    q_sorted = np.minimum.accumulate(ranked[::-1])[::-1]
    q = np.empty(m)
    q[order] = np.minimum(q_sorted, 1.0)
    return q


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def load_predictions() -> pd.DataFrame:
    p = pd.read_csv(PRED)
    p["game_id"] = p["GAME_ID"].astype(str)
    p["game_date"] = pd.to_datetime(p["GAME_DATE_h"])
    out = p[["game_id", "game_date", "season_h", "season_type_h",
             "TEAM_ABBREVIATION_h", "TEAM_ABBREVIATION_a",
             "margin_true", "total_true", "str_margin_cal",
             "str_total_cal"]].rename(
        columns={"season_h": "season", "season_type_h": "season_type",
                 "TEAM_ABBREVIATION_h": "home_abbr",
                 "TEAM_ABBREVIATION_a": "away_abbr",
                 "str_margin_cal": "model_margin",
                 "str_total_cal": "model_total"})
    assert not out["game_id"].duplicated().any()
    assert (out["margin_true"] != 0).all(), "zero margin (tie) impossible in WNBA"
    return out


def load_sigma(pred: pd.DataFrame) -> float:
    d = pd.read_csv(DIST, usecols=["game_id", "center", "sigma"])
    d["game_id"] = d["game_id"].astype(str)
    sig = d["sigma"].unique()
    assert len(sig) == 1, f"sigma not unique: {sig}"
    j = pred.merge(d, on="game_id", how="inner")
    assert len(j) == len(pred), "game_level_dist does not cover all prediction games"
    dev = (j["center"] - j["model_margin"]).abs().max()
    assert dev < 1e-9, f"dist center != str_margin_cal (max dev {dev})"
    return float(sig[0])


def load_spread_odds(path: Path, era: str) -> pd.DataFrame:
    """Identical conventions to clv_transfer.load_odds (audited there): tidy
    per (game_id, book, snap) with home_spread/home_price/away_price; tip =
    commence at the game's LATEST listing; pre-tip rows only."""
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
    last = t.sort_values("snap").groupby("game_id").tail(1)[["game_id", "tip_raw"]]
    tipmap = dict(zip(last["game_id"], last["tip_raw"]))
    t["tip"] = t["game_id"].map(tipmap)
    t = t[t["snap"] < t["tip"]].copy()
    t["era"] = era
    return t.reset_index(drop=True)


def load_other_markets() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Extension-era totals + h2h, tidied per (game_id, book, snap).

    totals: total_line (Over row's point; Under's when Over missing),
            over_price, under_price. Over/Under point mismatches counted.
    h2h:    home_price, away_price (team-name matched).
    Both: tip at the game's latest listing IN THIS TABLE, pre-tip rows only.
    """
    o = pd.read_csv(ODDS_EXT_OTHER, low_memory=False)
    o = o[o["game_id"].notna()].copy()
    o["game_id"] = o["game_id"].astype(np.int64).astype(str)
    o["snap"] = pd.to_datetime(o["odds_snapshot_timestamp"], utc=True, format="mixed")
    o["tip_raw"] = pd.to_datetime(o["odds_commence_time"], utc=True, format="mixed")
    last = o.sort_values("snap").groupby("game_id").tail(1)[["game_id", "tip_raw"]]
    tipmap = dict(zip(last["game_id"], last["tip_raw"]))
    o["tip"] = o["game_id"].map(tipmap)
    o = o[o["snap"] < o["tip"]].copy()
    acct: dict = {}

    t = o[o["market_key"] == "totals"]
    ov = t[t["outcome_name"] == "Over"][
        ["game_id", "bookmaker_key", "snap", "tip", "outcome_point",
         "outcome_price"]].rename(columns={"outcome_point": "over_point",
                                           "outcome_price": "over_price"})
    un = t[t["outcome_name"] == "Under"][
        ["game_id", "bookmaker_key", "snap", "outcome_point",
         "outcome_price"]].rename(columns={"outcome_point": "under_point",
                                           "outcome_price": "under_price"})
    tot = ov.merge(un, on=["game_id", "bookmaker_key", "snap"], how="outer")
    tip_fill = tot["game_id"].map(tipmap)
    tot["tip"] = tot["tip"].fillna(tip_fill)
    both = tot["over_point"].notna() & tot["under_point"].notna()
    mism = both & (tot["over_point"] != tot["under_point"])
    acct["totals_point_mismatch_rows"] = int(mism.sum())
    tot = tot[~mism].copy()
    tot["total_line"] = tot["over_point"].fillna(tot["under_point"])
    tot = tot[tot["total_line"].notna()].copy()
    tot["era"] = "extension"

    h = o[o["market_key"] == "h2h"]
    hh = h[h["outcome_name"] == h["home_team"]][
        ["game_id", "bookmaker_key", "snap", "tip", "outcome_price"]].rename(
        columns={"outcome_price": "home_price"})
    ha = h[h["outcome_name"] == h["away_team"]][
        ["game_id", "bookmaker_key", "snap", "outcome_price"]].rename(
        columns={"outcome_price": "away_price"})
    n_h2h_raw = len(h)
    n_named = int((h["outcome_name"] == h["home_team"]).sum()
                  + (h["outcome_name"] == h["away_team"]).sum())
    acct["h2h_rows_not_matching_either_team"] = n_h2h_raw - n_named
    h2 = hh.merge(ha, on=["game_id", "bookmaker_key", "snap"], how="outer")
    h2["tip"] = h2["tip"].fillna(h2["game_id"].map(tipmap))
    h2["era"] = "extension"
    return tot.reset_index(drop=True), h2.reset_index(drop=True), acct


def schedule_features(pred: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Walk-forward-safe schedule context from master_team game dates
    (registration: schedule is known pregame).

    Per game: rest_h/rest_a (days since the team's previous game, same season,
    both season types, NaN at season opener), gameno_h/gameno_a (season game
    number INCLUDING this game), phase (mean of the two game numbers: early
    <=10 / mid <=30 / late >30), rest_sign, weekend (Sat/Sun by game date).
    """
    mt = pd.read_csv(MASTER_TEAM, low_memory=False,
                     usecols=["game_id", "season", "season_type", "game_date",
                              "team_abbreviation", "is_home"])
    mt["game_id"] = mt["game_id"].astype(str)
    mt["game_date"] = pd.to_datetime(mt["game_date"])
    mt = mt.sort_values(["team_abbreviation", "season", "game_date"])
    grp = mt.groupby(["team_abbreviation", "season"], sort=False)
    mt["game_no"] = grp.cumcount() + 1
    mt["rest_days"] = grp["game_date"].diff().dt.days
    home = mt[mt["is_home"] == 1][["game_id", "game_date", "game_no", "rest_days"]]
    away = mt[mt["is_home"] == 0][["game_id", "game_no", "rest_days"]]
    assert not home["game_id"].duplicated().any()
    assert not away["game_id"].duplicated().any()
    g = home.rename(columns={"game_date": "date_master", "game_no": "gameno_h",
                             "rest_days": "rest_h"}).merge(
        away.rename(columns={"game_no": "gameno_a", "rest_days": "rest_a"}),
        on="game_id", how="inner")
    feats = pred[["game_id", "game_date"]].merge(g, on="game_id", how="left")
    missing = int(feats["date_master"].isna().sum())
    assert missing == 0, f"{missing} prediction games missing from master_team"
    date_mismatch = int((feats["date_master"] != feats["game_date"]).sum())

    mean_no = (feats["gameno_h"] + feats["gameno_a"]) / 2.0
    feats["phase"] = np.where(mean_no <= 10, "early",
                              np.where(mean_no <= 30, "mid", "late"))
    diff = feats["rest_h"] - feats["rest_a"]
    feats["rest_sign"] = np.where(feats["rest_h"].isna() | feats["rest_a"].isna(),
                                  None,
                                  np.where(diff > 0, "home_more",
                                           np.where(diff < 0, "away_more", "equal")))
    feats["weekend"] = np.where(feats["date_master"].dt.dayofweek >= 5,
                                "weekend", "weekday")
    acct = {"pred_games": int(len(feats)),
            "master_date_mismatches_vs_predictions": date_mismatch,
            "rest_undefined_games": int(feats["rest_sign"].isna().sum()),
            "phase_counts": feats["phase"].value_counts().to_dict(),
            "note": "phase = mean of the two teams' season game numbers "
                    "(incl. this game); rest across both season types within "
                    "a season; weekend by master_team game date."}
    keep = feats[["game_id", "rest_sign", "phase", "weekend",
                  "gameno_h", "gameno_a", "rest_h", "rest_a"]]
    return keep, acct


# ---------------------------------------------------------------------------
# matched vintages (clv_transfer conventions, generalized to three markets)
# ---------------------------------------------------------------------------

def _iter_vintages(tidy: pd.DataFrame, era: str):
    """Yield (game_id, timing, rows, vintage, cutoff_ts, tip) per the house
    convention: hour cutoffs = latest snapshot timestamp <= cutoff (all books
    present at that single vintage); near-tip = each book's latest pre-tip row."""
    for gid, g in tidy.groupby("game_id"):
        tip = g["tip"].iloc[0]
        for label, hours in TIMING_SPEC[era]:
            if hours is not None:
                cutoff = tip - pd.Timedelta(hours=hours)
                elig = g[g["snap"] <= cutoff]
                if not len(elig):
                    continue
                vint = elig["snap"].max()
                rows = elig[elig["snap"] == vint]
            else:
                rows = g.sort_values("snap").groupby("bookmaker_key").tail(1)
                vint = rows["snap"].max()
                cutoff = pd.NaT
            yield gid, label, rows, vint, cutoff, tip


def build_spread_lines(odds: pd.DataFrame, era: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    cons_rows, book_frames = [], []
    for gid, label, rows, vint, cutoff, tip in _iter_vintages(odds, era):
        cons_rows.append({
            "era": era, "timing": label, "game_id": gid,
            "consensus_home_spread": float(rows["home_spread"].mean()),
            "n_books": int(rows["bookmaker_key"].nunique()),
            "vintage_snap": vint, "cutoff_ts": cutoff, "tip": tip})
        bf = rows[["game_id", "bookmaker_key", "home_spread",
                   "home_price", "away_price"]].copy()
        bf["era"], bf["timing"] = era, label
        book_frames.append(bf)
    cons = pd.DataFrame(cons_rows)
    if len(cons):
        cons["market_margin"] = -cons["consensus_home_spread"]
    books = pd.concat(book_frames, ignore_index=True) if book_frames else pd.DataFrame()
    return cons, books


def build_total_lines(tot: pd.DataFrame, era: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    cons_rows, book_frames = [], []
    for gid, label, rows, vint, cutoff, tip in _iter_vintages(tot, era):
        cons_rows.append({
            "era": era, "timing": label, "game_id": gid,
            "consensus_total": float(rows["total_line"].mean()),
            "n_books": int(rows["bookmaker_key"].nunique()),
            "vintage_snap": vint, "cutoff_ts": cutoff, "tip": tip})
        bf = rows[["game_id", "bookmaker_key", "total_line",
                   "over_price", "under_price"]].copy()
        bf["era"], bf["timing"] = era, label
        book_frames.append(bf)
    return (pd.DataFrame(cons_rows),
            pd.concat(book_frames, ignore_index=True) if book_frames else pd.DataFrame())


def build_h2h_lines(h2h: pd.DataFrame, era: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Consensus devigged home prob (mean over books with a VALID two-sided
    pair) + consensus execution multipliers (mean payout multiplier over books
    validly quoting that side) + per-book rows for best execution."""
    acct = {"h2h_price_anomaly_rows": 0, "h2h_games_no_valid_pair": 0}
    cons_rows, book_frames = [], []
    for gid, label, rows, vint, cutoff, tip in _iter_vintages(h2h, era):
        r = rows.copy()
        for c in ("home_price", "away_price"):
            bad = r[c].abs() >= PRICE_ANOMALY_ABS
            acct["h2h_price_anomaly_rows"] += int(bad.sum())
            r.loc[bad, c] = np.nan
        pair = r[r["home_price"].notna() & r["away_price"].notna()]
        if not len(pair):
            acct["h2h_games_no_valid_pair"] += 1
            continue
        qh = pair["home_price"].map(_amer_prob)
        qa = pair["away_price"].map(_amer_prob)
        p_home = float((qh / (qh + qa)).mean())
        overround = float((qh + qa).mean())
        mh = r.loc[r["home_price"].notna(), "home_price"].map(_mult)
        ma = r.loc[r["away_price"].notna(), "away_price"].map(_mult)
        cons_rows.append({
            "era": era, "timing": label, "game_id": gid,
            "p_home_cons": p_home, "n_books_pair": int(len(pair)),
            "overround_mean": overround,
            "cons_mult_home": float(mh.mean()) if len(mh) else np.nan,
            "cons_mult_away": float(ma.mean()) if len(ma) else np.nan,
            "vintage_snap": vint, "cutoff_ts": cutoff, "tip": tip})
        bf = r[["game_id", "bookmaker_key", "home_price", "away_price"]].copy()
        bf["era"], bf["timing"] = era, label
        book_frames.append(bf)
    return (pd.DataFrame(cons_rows),
            pd.concat(book_frames, ignore_index=True) if book_frames else pd.DataFrame(),
            acct)


def vintage_audit(frames: list[pd.DataFrame]) -> dict:
    """snap <= cutoff < tip for hour cutoffs; snap < tip everywhere."""
    n = 0
    for f in frames:
        if not len(f):
            continue
        hour = f[f["cutoff_ts"].notna()]
        assert (hour["vintage_snap"] <= hour["cutoff_ts"]).all(), "vintage > cutoff"
        assert (hour["cutoff_ts"] < hour["tip"]).all(), "cutoff >= tip"
        assert (f["vintage_snap"] < f["tip"]).all(), "vintage >= tip"
        n += int(len(f))
    return {"rows_checked": n, "violations": 0}


# ---------------------------------------------------------------------------
# best-execution precompute (both sides, per candidate game)
# ---------------------------------------------------------------------------

def _best_exec_spread(grp: pd.DataFrame, side: int, margin_true: float) -> dict:
    """clv_transfer's exact selection: most favorable line for the side, then
    best price multiplier; settle on the line taken."""
    pcol = "home_price" if side > 0 else "away_price"
    cand = grp[grp[pcol].notna()]
    cand = cand[cand[pcol].abs() < PRICE_ANOMALY_ABS]
    if not len(cand):
        return dict(book=None, line=np.nan, price=np.nan, outcome=np.nan,
                    profit=np.nan, anomalies=0)
    key = cand["home_spread"] * (1 if side > 0 else -1)
    cand = cand.assign(_k=key, _m=cand[pcol].map(_mult))
    best = cand.sort_values(["_k", "_m"]).iloc[-1]
    lm = -float(best["home_spread"])
    out = _settle(margin_true, lm, side)
    mult = _mult(float(best[pcol]))
    return dict(book=best["bookmaker_key"], line=float(best["home_spread"]),
                price=float(best[pcol]), outcome=_OUT_CODE[out],
                profit={"win": mult, "push": 0.0, "loss": -1.0}[out],
                anomalies=0)


def _best_exec_total(grp: pd.DataFrame, side: int, total_true: float) -> dict:
    """Over: lowest line is most favorable; Under: highest. Then best price."""
    pcol = "over_price" if side > 0 else "under_price"
    cand = grp[grp[pcol].notna() & grp["total_line"].notna()]
    cand = cand[cand[pcol].abs() < PRICE_ANOMALY_ABS]
    if not len(cand):
        return dict(book=None, line=np.nan, price=np.nan, outcome=np.nan,
                    profit=np.nan)
    key = cand["total_line"] * (-1 if side > 0 else 1)   # over wants MIN line
    cand = cand.assign(_k=key, _m=cand[pcol].map(_mult))
    best = cand.sort_values(["_k", "_m"]).iloc[-1]
    line = float(best["total_line"])
    out = _settle(total_true, line, side)
    mult = _mult(float(best[pcol]))
    return dict(book=best["bookmaker_key"], line=line, price=float(best[pcol]),
                outcome=_OUT_CODE[out],
                profit={"win": mult, "push": 0.0, "loss": -1.0}[out])


def _best_exec_ml(grp: pd.DataFrame, side: int, home_won: bool) -> dict:
    pcol = "home_price" if side > 0 else "away_price"
    cand = grp[grp[pcol].notna()]
    cand = cand[cand[pcol].abs() < PRICE_ANOMALY_ABS]
    if not len(cand):
        return dict(book=None, price=np.nan, outcome=np.nan, profit=np.nan)
    cand = cand.assign(_m=cand[pcol].map(_mult))
    best = cand.sort_values("_m").iloc[-1]
    won = home_won if side > 0 else (not home_won)
    return dict(book=best["bookmaker_key"], price=float(best[pcol]),
                outcome=1 if won else -1,
                profit=float(best["_m"]) if won else -1.0)


# ---------------------------------------------------------------------------
# candidate frames
# ---------------------------------------------------------------------------

class Frame:
    """One (era, timing, bet_type) candidate universe with everything
    precomputed for both possible bet sides. The model column enters ONLY via
    ``gidx`` into the era's model vector — that is what permutations shuffle."""

    def __init__(self, era, timing, bet_type, df, era_games):
        self.era, self.timing, self.bet_type = era, timing, bet_type
        self.df = df.reset_index(drop=True)
        gmap = {g: i for i, g in enumerate(era_games)}
        self.gidx = self.df["game_id"].map(gmap).to_numpy(int)
        self.market_ref = self.df["market_ref"].to_numpy(float)
        self.dates = pd.to_datetime(self.df["game_date"]).dt.normalize().to_numpy()
        for c in ("cons_profit_pos", "cons_profit_neg", "be_profit_pos",
                  "be_profit_neg", "clv_pos"):
            setattr(self, c, self.df[c].to_numpy(float))
        for c in ("cons_out_pos", "cons_out_neg", "be_out_pos", "be_out_neg"):
            setattr(self, c, self.df[c].to_numpy(float))
        self.model_source = "total" if bet_type == "total" else "margin"
        # static conditioner masks
        self.levels: list[tuple[str, str, str, object]] = []
        self.levels.append(("none", "all", "static",
                            np.ones(len(self.df), bool)))
        for lvl in ("small", "mid", "large"):
            self.levels.append(("line_terc", lvl, "static",
                                (self.df["line_terc"] == lvl).to_numpy()))
        if era == "extension":
            for lvl in ("low", "mid", "high"):
                self.levels.append(("total_terc", lvl, "static",
                                    (self.df["total_terc"] == lvl).to_numpy()))
        if bet_type in ("spread", "moneyline"):
            for lvl in ("home", "away", "fav", "dog"):
                self.levels.append(("side", lvl, "side", lvl))
        else:
            for lvl in ("over", "under"):
                self.levels.append(("side", lvl, "side", lvl))
        for lvl in ("home_more", "equal", "away_more"):
            self.levels.append(("rest_sign", lvl, "static",
                                (self.df["rest_sign"] == lvl).to_numpy()))
        for lvl in ("early", "mid", "late"):
            self.levels.append(("phase", lvl, "static",
                                (self.df["phase"] == lvl).to_numpy()))
        for lvl in ("weekend", "weekday"):
            self.levels.append(("weekend", lvl, "static",
                                (self.df["weekend"] == lvl).to_numpy()))
        self.fav_side = self.df["fav_side"].to_numpy(float)  # +1 home fav, -1, 0/nan

    def side_mask(self, level: str, side: np.ndarray) -> np.ndarray:
        if level in ("home", "over"):
            return side > 0
        if level in ("away", "under"):
            return side < 0
        if level == "fav":
            return (self.fav_side != 0) & ~np.isnan(self.fav_side) & (side == self.fav_side)
        if level == "dog":
            return (self.fav_side != 0) & ~np.isnan(self.fav_side) & (side == -self.fav_side)
        raise ValueError(level)


def tercile_levels(values: pd.Series, labels: tuple[str, str, str]):
    """Game-level terciles; returns (mapping game->label, boundaries)."""
    v = values.dropna()
    if len(v) < 6:
        return {}, (np.nan, np.nan)
    q1, q2 = np.quantile(v.to_numpy(float), [1.0 / 3.0, 2.0 / 3.0])
    def lab(x):
        if np.isnan(x):
            return None
        return labels[0] if x <= q1 else (labels[1] if x <= q2 else labels[2])
    return {g: lab(x) for g, x in values.items()}, (float(q1), float(q2))


def attach_context(df, sched, line_map, total_map):
    df = df.merge(sched, on="game_id", how="left")
    df["line_terc"] = df["game_id"].map(line_map).astype(object)
    df["total_terc"] = df["game_id"].map(total_map).astype(object) if total_map \
        else None
    return df


# ---------------------------------------------------------------------------
# frame builders
# ---------------------------------------------------------------------------

def make_spread_frame(era, timing, cons, books, pred, sched, line_map,
                      total_map, pretip_margin, era_games, acct):
    c = cons[(cons["era"] == era) & (cons["timing"] == timing)]
    df = c.merge(pred, on="game_id", how="inner").copy()
    df["market_ref"] = df["market_margin"]
    bkey = {g: grp for g, grp in
            books[(books["era"] == era) & (books["timing"] == timing)]
            .groupby("game_id")}
    rows = {k: [] for k in ("cons_profit_pos", "cons_profit_neg", "cons_out_pos",
                            "cons_out_neg", "be_profit_pos", "be_profit_neg",
                            "be_out_pos", "be_out_neg", "be_book_pos",
                            "be_book_neg", "be_line_pos", "be_line_neg",
                            "be_price_pos", "be_price_neg")}
    for r in df.itertuples(index=False):
        for side, tag in ((1, "pos"), (-1, "neg")):
            out = _settle(r.margin_true, r.market_ref, side)
            rows[f"cons_out_{tag}"].append(_OUT_CODE[out])
            rows[f"cons_profit_{tag}"].append(
                {"win": WIN_110, "push": 0.0, "loss": -1.0}[out])
            be = _best_exec_spread(bkey.get(r.game_id, books.iloc[0:0]),
                                   side, r.margin_true)
            rows[f"be_profit_{tag}"].append(be["profit"])
            rows[f"be_out_{tag}"].append(be["outcome"])
            rows[f"be_book_{tag}"].append(be["book"])
            rows[f"be_line_{tag}"].append(be["line"])
            rows[f"be_price_{tag}"].append(be["price"])
    for k, v in rows.items():
        df[k] = v
    # CLV: signed points the latest pre-tip consensus moved toward a HOME bet
    if timing == CLV_TIMING:
        pm = df["game_id"].map(pretip_margin)
        df["clv_pos"] = pm - df["market_ref"]
    else:
        df["clv_pos"] = np.nan
    df["fav_side"] = np.where(df["consensus_home_spread"] < 0, 1.0,
                              np.where(df["consensus_home_spread"] > 0, -1.0, 0.0))
    df = attach_context(df, sched, line_map, total_map)
    df["model_value"] = df["model_margin"]
    return Frame(era, timing, "spread", df, era_games)


def make_total_frame(era, timing, cons_t, books_t, pred, sched, line_map,
                     total_map, pretip_total, era_games, acct):
    c = cons_t[(cons_t["era"] == era) & (cons_t["timing"] == timing)]
    df = c.merge(pred, on="game_id", how="inner").copy()
    df["market_ref"] = df["consensus_total"]
    bkey = {g: grp for g, grp in
            books_t[(books_t["era"] == era) & (books_t["timing"] == timing)]
            .groupby("game_id")}
    rows = {k: [] for k in ("cons_profit_pos", "cons_profit_neg", "cons_out_pos",
                            "cons_out_neg", "be_profit_pos", "be_profit_neg",
                            "be_out_pos", "be_out_neg", "be_book_pos",
                            "be_book_neg", "be_line_pos", "be_line_neg",
                            "be_price_pos", "be_price_neg")}
    for r in df.itertuples(index=False):
        for side, tag in ((1, "pos"), (-1, "neg")):
            out = _settle(r.total_true, r.market_ref, side)
            rows[f"cons_out_{tag}"].append(_OUT_CODE[out])
            rows[f"cons_profit_{tag}"].append(
                {"win": WIN_110, "push": 0.0, "loss": -1.0}[out])
            be = _best_exec_total(bkey.get(r.game_id, books_t.iloc[0:0]),
                                  side, r.total_true)
            rows[f"be_profit_{tag}"].append(be["profit"])
            rows[f"be_out_{tag}"].append(be["outcome"])
            rows[f"be_book_{tag}"].append(be["book"])
            rows[f"be_line_{tag}"].append(be["line"])
            rows[f"be_price_{tag}"].append(be["price"])
    for k, v in rows.items():
        df[k] = v
    if timing == CLV_TIMING:
        pt = df["game_id"].map(pretip_total)
        df["clv_pos"] = pt - df["market_ref"]     # market total rising favors Over
    else:
        df["clv_pos"] = np.nan
    df["fav_side"] = 0.0                          # fav/dog undefined for totals
    df = attach_context(df, sched, line_map, total_map)
    df["model_value"] = df["model_total"]
    return Frame(era, timing, "total", df, era_games)


def make_ml_frame(era, timing, cons_h, books_h, pred, sched, line_map,
                  total_map, pretip_implied, sigma, era_games, acct):
    c = cons_h[(cons_h["era"] == era) & (cons_h["timing"] == timing)].copy()
    p_raw = c["p_home_cons"].to_numpy(float)
    clipped = int(((p_raw < P_CLIP) | (p_raw > 1 - P_CLIP)).sum())
    acct["ml_probs_clipped"] = acct.get("ml_probs_clipped", 0) + clipped
    c["implied_mkt_margin"] = sigma * norm_ppf(np.clip(p_raw, P_CLIP, 1 - P_CLIP))
    df = c.merge(pred, on="game_id", how="inner").copy()
    df["market_ref"] = df["implied_mkt_margin"]
    df["model_p_home"] = norm_cdf(df["model_margin"].to_numpy(float) / sigma)
    bkey = {g: grp for g, grp in
            books_h[(books_h["era"] == era) & (books_h["timing"] == timing)]
            .groupby("game_id")}
    rows = {k: [] for k in ("cons_profit_pos", "cons_profit_neg", "cons_out_pos",
                            "cons_out_neg", "be_profit_pos", "be_profit_neg",
                            "be_out_pos", "be_out_neg", "be_book_pos",
                            "be_book_neg", "be_price_pos", "be_price_neg")}
    for r in df.itertuples(index=False):
        home_won = r.margin_true > 0
        for side, tag in ((1, "pos"), (-1, "neg")):
            won = home_won if side > 0 else not home_won
            mult = r.cons_mult_home if side > 0 else r.cons_mult_away
            if np.isnan(mult):
                rows[f"cons_out_{tag}"].append(np.nan)
                rows[f"cons_profit_{tag}"].append(np.nan)
            else:
                rows[f"cons_out_{tag}"].append(1 if won else -1)
                rows[f"cons_profit_{tag}"].append(float(mult) if won else -1.0)
            be = _best_exec_ml(bkey.get(r.game_id, books_h.iloc[0:0]),
                               side, home_won)
            rows[f"be_profit_{tag}"].append(be["profit"])
            rows[f"be_out_{tag}"].append(be["outcome"])
            rows[f"be_book_{tag}"].append(be["book"])
            rows[f"be_price_{tag}"].append(be["price"])
    for k, v in rows.items():
        df[k] = v
    df["be_line_pos"] = np.nan
    df["be_line_neg"] = np.nan
    if timing == CLV_TIMING:
        pi = df["game_id"].map(pretip_implied)
        df["clv_pos"] = pi - df["market_ref"]     # implied-margin points toward home
    else:
        df["clv_pos"] = np.nan
    df["fav_side"] = np.where(df["p_home_cons"] > 0.5, 1.0,
                              np.where(df["p_home_cons"] < 0.5, -1.0, 0.0))
    df = attach_context(df, sched, line_map, total_map)
    df["model_value"] = df["model_margin"]
    return Frame(era, timing, "moneyline", df, era_games)


# ---------------------------------------------------------------------------
# battery evaluation
# ---------------------------------------------------------------------------

def build_cells(frames: list[Frame]) -> pd.DataFrame:
    rows = []
    for fi, f in enumerate(frames):
        for thr in THRESHOLDS:
            for ex in EXECUTIONS:
                for dim, level, kind, _payload in f.levels:
                    rows.append({"frame_idx": fi, "era": f.era,
                                 "timing": f.timing, "bet_type": f.bet_type,
                                 "threshold": thr, "execution": ex,
                                 "cond_dim": dim, "cond_level": level,
                                 "level_kind": kind})
    return pd.DataFrame(rows)


def frame_bets(f: Frame, margin_vec: np.ndarray, total_vec: np.ndarray):
    """Edges + chosen-side arrays for one model vector (observed or permuted)."""
    model = (total_vec if f.model_source == "total" else margin_vec)[f.gidx]
    edge = model - f.market_ref
    side = np.where(edge > 0, 1.0, np.where(edge < 0, -1.0, 0.0))
    pos = side > 0
    prof = {
        "consensus": np.where(pos, f.cons_profit_pos, f.cons_profit_neg),
        "best_book": np.where(pos, f.be_profit_pos, f.be_profit_neg),
    }
    out = {
        "consensus": np.where(pos, f.cons_out_pos, f.cons_out_neg),
        "best_book": np.where(pos, f.be_out_pos, f.be_out_neg),
    }
    return edge, side, prof, out


def eval_battery_fast(frames, cells_by_frame, margin_vec, total_vec,
                      roi_out: np.ndarray) -> None:
    """Fill roi_out (len n_cells) with each cell's own-basis ROI (NaN if the
    cell settles zero bets). Used for the permutation null."""
    for fi, f in enumerate(frames):
        edge, side, prof, _ = frame_bets(f, margin_vec, total_vec)
        abs_edge = np.abs(edge)
        settled = {ex: ~np.isnan(prof[ex]) for ex in EXECUTIONS}
        static_cache = {}
        for ci, thr, ex, dim, level, kind, payload in cells_by_frame[fi]:
            bet = (abs_edge >= thr) & (side != 0) & settled[ex]
            if kind == "static":
                m = bet & payload
            else:
                key = (level, id(side))
                if key not in static_cache:
                    static_cache[key] = f.side_mask(level, side)
                m = bet & static_cache[key]
            n = int(m.sum())
            roi_out[ci] = (prof[ex][m].sum() / n) if n else np.nan


def eval_battery_rich(frames, cells: pd.DataFrame, margin_vec, total_vec,
                      n_boot: int) -> pd.DataFrame:
    """Observed pass: full per-cell stats."""
    recs = []
    per_frame = {}
    for fi, f in enumerate(frames):
        per_frame[fi] = frame_bets(f, margin_vec, total_vec)
    for r in cells.itertuples(index=False):
        f = frames[r.frame_idx]
        edge, side, prof, out = per_frame[r.frame_idx]
        bet0 = (np.abs(edge) >= r.threshold) & (side != 0)
        if r.level_kind == "static":
            payload = next(p for d, l, k, p in f.levels
                           if d == r.cond_dim and l == r.cond_level)
            lm = payload
        else:
            lm = f.side_mask(r.cond_level, side)
        base = bet0 & lm
        stats = {}
        for ex in EXECUTIONS:
            m = base & ~np.isnan(prof[ex])
            n = int(m.sum())
            o = out[ex][m]
            wins, losses, pushes = int((o == 1).sum()), int((o == -1).sum()), \
                int((o == 0).sum())
            roi = float(prof[ex][m].sum() / n) if n else np.nan
            stats[ex] = dict(n=n, wins=wins, losses=losses, pushes=pushes,
                             roi=roi, mask=m)
        own = stats[r.execution]
        hit = (own["wins"] / (own["wins"] + own["losses"])
               if (own["wins"] + own["losses"]) else np.nan)
        ci_lo = ci_hi = np.nan
        n_dates = 0
        if own["n"]:
            m = own["mask"]
            d = f.dates[m]
            n_dates = int(pd.Series(d).nunique())
            if n_dates >= 2:
                try:
                    ci = cluster_bootstrap_ci(
                        prof[r.execution][m], d, n_boot=n_boot, seed=SEED)
                    ci_lo, ci_hi = ci["low"], ci["high"]
                except ComparisonError:
                    pass
        clv_vals = np.where(side > 0, f.clv_pos, -f.clv_pos)[own["mask"]] \
            if own["n"] else np.array([])
        clv_vals = clv_vals[~np.isnan(clv_vals)]
        recs.append({
            "n_bets": own["n"], "wins": own["wins"], "losses": own["losses"],
            "pushes": own["pushes"], "hit_rate": hit, "roi": own["roi"],
            "n_cons": stats["consensus"]["n"], "roi_cons": stats["consensus"]["roi"],
            "n_best": stats["best_book"]["n"], "roi_best": stats["best_book"]["roi"],
            "roi_ci90_low": ci_lo, "roi_ci90_high": ci_hi, "n_dates": n_dates,
            "mean_clv_pts": float(clv_vals.mean()) if len(clv_vals) else np.nan,
            "pct_clv_positive": float((clv_vals > 0).mean()) if len(clv_vals) else np.nan,
            "clv_measurable": bool(len(clv_vals)),
        })
    return pd.concat([cells.reset_index(drop=True), pd.DataFrame(recs)], axis=1)


# ---------------------------------------------------------------------------
# universe CSV
# ---------------------------------------------------------------------------

def universe_frame(f: Frame, margin_vec, total_vec) -> pd.DataFrame:
    edge, side, prof, out = frame_bets(f, margin_vec, total_vec)
    d = f.df
    pos = side > 0
    side_lbl = np.where(side == 0, "none",
                        np.where(pos,
                                 "over" if f.bet_type == "total" else "home",
                                 "under" if f.bet_type == "total" else "away"))
    u = pd.DataFrame({
        "era": f.era, "timing": f.timing, "bet_type": f.bet_type,
        "game_id": d["game_id"], "game_date": d["game_date"],
        "season": d["season"], "season_type": d["season_type"],
        "model_value": d["model_value"], "market_ref": f.market_ref,
        "edge": edge, "side": side_lbl,
        "bet_at_min_threshold": np.abs(edge) >= min(THRESHOLDS),
        "cons_profit": prof["consensus"], "cons_outcome": out["consensus"],
        "be_profit": prof["best_book"], "be_outcome": out["best_book"],
        "be_book": np.where(pos, d["be_book_pos"], d["be_book_neg"]),
        "be_price": np.where(pos, d["be_price_pos"], d["be_price_neg"]),
        "be_line": np.where(pos, d.get("be_line_pos", np.nan),
                            d.get("be_line_neg", np.nan)),
        "clv_pts": np.where(pos, f.clv_pos, -f.clv_pos),
        "line_terc": d["line_terc"], "total_terc": d["total_terc"],
        "fav_side": d["fav_side"], "rest_sign": d["rest_sign"],
        "phase": d["phase"], "weekend": d["weekend"],
        "n_books": d.get("n_books", d.get("n_books_pair")),
    })
    if f.bet_type == "moneyline":
        u["p_home_cons"] = d["p_home_cons"].values
        u["model_p_home"] = d["model_p_home"].values
    return u


# ---------------------------------------------------------------------------
# audits
# ---------------------------------------------------------------------------

def crosscheck_clv_transfer(all_cells: pd.DataFrame) -> pd.DataFrame:
    """The unconditioned extension/T-24h and old/near-tip spread cells must
    reproduce clv_transfer_v1's flat_stake_sim rows exactly (same conventions,
    same universe)."""
    ref = pd.read_csv(CLV_SIM)
    basis_map = {"consensus": "consensus_m110", "best_book": "actual_best_exec"}
    timing_map = {("extension", "T-24h"): "T-24h", ("old", "near-tip"): "T-64m"}
    rows = []
    for (era, t_mine), t_ref in timing_map.items():
        for thr in THRESHOLDS:
            for ex, basis in basis_map.items():
                mine = all_cells[(all_cells["era"] == era)
                                 & (all_cells["timing"] == t_mine)
                                 & (all_cells["bet_type"] == "spread")
                                 & (all_cells["threshold"] == thr)
                                 & (all_cells["execution"] == ex)
                                 & (all_cells["cond_dim"] == "none")]
                theirs = ref[(ref["era"] == era) & (ref["cutoff"] == t_ref)
                             & (ref["basis"] == basis)
                             & (ref["threshold"] == thr)]
                assert len(mine) == 1 and len(theirs) == 1, \
                    f"crosscheck cell lookup failed {era} {t_mine} {thr} {ex}"
                mi, th = mine.iloc[0], theirs.iloc[0]
                d_n = int(mi["n_bets"]) - int(th["n_bets"])
                d_w = int(mi["wins"]) - int(th["wins"])
                d_roi = (mi["roi"] - th["roi"]) if pd.notna(th["roi"]) else np.nan
                rows.append({"era": era, "timing": t_mine, "threshold": thr,
                             "execution": ex, "n_mine": int(mi["n_bets"]),
                             "n_ref": int(th["n_bets"]), "dn": d_n, "dw": d_w,
                             "droi": float(d_roi)})
                assert d_n == 0 and d_w == 0 and abs(d_roi) < 1e-9, \
                    (f"clv_transfer crosscheck MISMATCH {era} {t_mine} thr {thr} "
                     f"{ex}: dn={d_n} dw={d_w} droi={d_roi}")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# stories for the John-facing ledger
# ---------------------------------------------------------------------------

_STORIES = {
    ("side", "dog"): "favorite-longshot bias - books shade lines toward favorites; disagreement bets on dogs harvest the shade",
    ("side", "fav"): "model catches strength moves the market is slow to shade onto favorites",
    ("side", "home"): "market underprices home court where the model's strength gap disagrees",
    ("side", "away"): "public home bias inflates home lines; away disagreements fade it",
    ("side", "over"): "model pace/efficiency signal ahead of totals anchored on stale scoring rates",
    ("side", "under"): "public over bias inflates totals; model unders fade it",
    ("line_terc", "small"): "near pick'em games - the margin signal is worth the most per point where the line says the least",
    ("line_terc", "large"): "lopsided games - blowout-range lines are less policed (low handle, garbage-time noise)",
    ("total_terc", "low"): "slow-pace games - lower variance, a margin edge converts to covers more often",
    ("total_terc", "high"): "fast-pace games - the model's possession/pace signal matters most",
    ("rest_sign", "home_more"): "market underweights rest advantage (schedule spots public but underpriced)",
    ("rest_sign", "away_more"): "market underweights rest advantage (schedule spots public but underpriced)",
    ("phase", "early"): "early season - books anchored on preseason priors; within-season form not yet priced",
    ("phase", "late"): "late season - seeding/rest/tank motivations that lines underprice",
    ("weekend", "weekend"): "weekend slates draw public money; lines shade toward popular sides",
    ("none", "all"): "broad model-vs-market disagreement at this timing/threshold (the base grid cell)",
}


def mechanism(row) -> tuple[str, bool]:
    key = (row["cond_dim"], row["cond_level"])
    story = _STORIES.get(key)
    anomaly = story is None
    if anomaly:
        story = ("ANOMALY - no mechanism we can defend for this slice; kept, "
                 "never dropped (registration rule)")
    extra = []
    if row["timing"] == "T-24h":
        extra.append("T-24h lines are pre-sharp-action and softest")
    if row["execution"] == "best_book":
        extra.append("line shopping captures the loose book")
    if extra and not anomaly:
        story = story + " (" + "; ".join(extra) + ")"
    return story, anomaly


def season_stability_table(frames: list[Frame], model_by_era: dict) -> pd.DataFrame:
    """Descriptive per-season splits (WITHIN era only) for three headline
    families — context for the report, NOT battery cells, ungated."""
    specs = [
        ("extension", "T-24h", "moneyline", 0.5, None, None,
         "ML disagreement (base)"),
        ("extension", "T-24h", "total", 0.5, "rest_sign", "home_more",
         "totals, home rested"),
        ("old", "near-tip", "spread", 2.0, "rest_sign", "home_more",
         "spread, home rested"),
        ("extension", "near-tip", "total", 3.0, "total_terc", "mid",
         "totals thr3, mid-total (top anomaly)"),
    ]
    rows = []
    for era, timing, bt, thr, dim, level, label in specs:
        f = next((x for x in frames if x.era == era and x.timing == timing
                  and x.bet_type == bt), None)
        if f is None:
            continue
        mv, tv = model_by_era[era]
        edge, side, prof, _out = frame_bets(f, mv, tv)
        m = (np.abs(edge) >= thr) & (side != 0) & ~np.isnan(prof["consensus"])
        if dim is not None:
            m &= (f.df[dim] == level).to_numpy()
        sub = f.df[m]
        p = prof["consensus"][m]
        for season in sorted(sub["season"].unique()):
            sm = (sub["season"] == season).to_numpy()
            rows.append({"family": label, "era": era, "season": int(season),
                         "n_bets": int(sm.sum()),
                         "roi_consensus": float(p[sm].sum() / sm.sum())
                         if sm.sum() else np.nan})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# report helpers
# ---------------------------------------------------------------------------

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


def cell_name(r) -> str:
    return (f"{r['era']}/{r['timing']}/{r['bet_type']}/thr{r['threshold']:g}/"
            f"{r['execution']}/{r['cond_dim']}={r['cond_level']}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--smoke", action="store_true",
                    help="scratch registry copy as a guard (this study makes "
                         "no registry calls); full data; artifacts to the "
                         "real outdir")
    ap.add_argument("--outdir", type=Path, default=None)
    ap.add_argument("--n-perms", type=int, default=N_PERMS_DEFAULT)
    ap.add_argument("--n-boot", type=int, default=N_BOOT_DEFAULT)
    args = ap.parse_args(argv)

    mode = "SMOKE (no ledger interaction)" if args.smoke else "REAL (records nothing)"
    if args.smoke:
        import tempfile
        scratch = Path(tempfile.mkdtemp(prefix="pocket_mining_scratch_"))
        shutil.copyfile(REPO / "experiments" / "registry.jsonl",
                        scratch / "registry_scratch.jsonl")
        # guard only: this study performs no compare/evaluate/record calls.
    outdir = args.outdir or DEFAULT_OUTDIR
    outdir.mkdir(parents=True, exist_ok=True)
    run_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    degraded = (args.n_perms != N_PERMS_DEFAULT) or (args.n_boot != N_BOOT_DEFAULT)
    print(f"[pocket] {mode} run at {run_time} -> {outdir} "
          f"(n_perms={args.n_perms}, n_boot={args.n_boot}"
          f"{' — DEV SETTINGS, NOT THE REGISTERED ARTIFACT' if degraded else ''})")
    t0 = time.time()
    self_test()

    # 1. inputs ---------------------------------------------------------------
    pred = load_predictions()
    sigma = load_sigma(pred)
    sched, sched_acct = schedule_features(pred)
    odds_old = load_spread_odds(ODDS_OLD, "old")
    odds_ext = load_spread_odds(ODDS_EXT, "extension")
    tot_ext, h2h_ext, om_acct = load_other_markets()
    era_games_odds = {"old": set(odds_old["game_id"]),
                      "extension": (set(odds_ext["game_id"])
                                    | set(tot_ext["game_id"])
                                    | set(h2h_ext["game_id"]))}
    assert not (era_games_odds["old"] & era_games_odds["extension"]), \
        "no-blend audit FAILED: game_id in both eras"
    print(f"[load] pred {len(pred)} games; sigma {sigma:.4f}; "
          f"odds old {odds_old['game_id'].nunique()} games / "
          f"ext {odds_ext['game_id'].nunique()} spread, "
          f"{tot_ext['game_id'].nunique()} totals, "
          f"{h2h_ext['game_id'].nunique()} h2h games ({time.time()-t0:.0f}s)")

    # 2. matched lines --------------------------------------------------------
    cons_sp_old, books_sp_old = build_spread_lines(odds_old, "old")
    cons_sp_ext, books_sp_ext = build_spread_lines(odds_ext, "extension")
    cons_sp = pd.concat([cons_sp_old, cons_sp_ext], ignore_index=True)
    books_sp = pd.concat([books_sp_old, books_sp_ext], ignore_index=True)
    cons_tot, books_tot = build_total_lines(tot_ext, "extension")
    cons_h2h, books_h2h, h2h_acct = build_h2h_lines(h2h_ext, "extension")
    va = vintage_audit([cons_sp, cons_tot, cons_h2h])
    print(f"[vintage] {va['rows_checked']} matched rows, 0 violations "
          f"({time.time()-t0:.0f}s)")

    # pretip references for CLV (extension near-tip consensus per market)
    nt_sp = cons_sp[(cons_sp["era"] == "extension") & (cons_sp["timing"] == "near-tip")]
    pretip_margin = dict(zip(nt_sp["game_id"], nt_sp["market_margin"]))
    nt_tot = cons_tot[cons_tot["timing"] == "near-tip"]
    pretip_total = dict(zip(nt_tot["game_id"], nt_tot["consensus_total"]))
    nt_h = cons_h2h[cons_h2h["timing"] == "near-tip"]
    pretip_implied = dict(zip(
        nt_h["game_id"],
        sigma * norm_ppf(np.clip(nt_h["p_home_cons"].to_numpy(float),
                                 P_CLIP, 1 - P_CLIP))))

    # 3. conditioner context per (era, timing) --------------------------------
    pred_ids = set(pred["game_id"])
    terc_bounds = {}
    line_maps, total_maps = {}, {}
    for era in TIMING_SPEC:
        for timing, _h in TIMING_SPEC[era]:
            sp = cons_sp[(cons_sp["era"] == era) & (cons_sp["timing"] == timing)]
            sp = sp[sp["game_id"].isin(pred_ids)]
            lm, b = tercile_levels(
                pd.Series(sp["consensus_home_spread"].abs().to_numpy(),
                          index=sp["game_id"]), ("small", "mid", "large"))
            line_maps[(era, timing)] = lm
            terc_bounds[(era, timing, "line_abs_spread")] = b
            tt = cons_tot[(cons_tot["era"] == era) & (cons_tot["timing"] == timing)]
            tt = tt[tt["game_id"].isin(pred_ids)]
            if len(tt):
                tm, bt = tercile_levels(
                    pd.Series(tt["consensus_total"].to_numpy(),
                              index=tt["game_id"]), ("low", "mid", "high"))
            else:
                tm, bt = {}, (np.nan, np.nan)
            total_maps[(era, timing)] = tm
            terc_bounds[(era, timing, "market_total")] = bt

    # 4. candidate frames -----------------------------------------------------
    misc_acct: dict = {}
    frames: list[Frame] = []
    era_games = {}
    for era in ("extension", "old"):
        ids = set()
        for timing, _h in TIMING_SPEC[era]:
            for cons in (cons_sp, cons_tot, cons_h2h):
                sub = cons[(cons.get("era") == era) & (cons["timing"] == timing)] \
                    if len(cons) else cons
                if len(sub):
                    ids |= set(sub["game_id"]) & pred_ids
        era_games[era] = sorted(ids)
    for era in ("extension", "old"):
        for timing, _h in TIMING_SPEC[era]:
            lm, tm = line_maps[(era, timing)], total_maps[(era, timing)]
            if "spread" in BET_TYPES[era]:
                frames.append(make_spread_frame(
                    era, timing, cons_sp, books_sp, pred, sched, lm, tm,
                    pretip_margin, era_games[era], misc_acct))
            if "total" in BET_TYPES[era]:
                frames.append(make_total_frame(
                    era, timing, cons_tot, books_tot, pred, sched, lm, tm,
                    pretip_total, era_games[era], misc_acct))
            if "moneyline" in BET_TYPES[era]:
                frames.append(make_ml_frame(
                    era, timing, cons_h2h, books_h2h, pred, sched, lm, tm,
                    pretip_implied, sigma, era_games[era], misc_acct))
    for f in frames:
        print(f"[frame] {f.era}/{f.timing}/{f.bet_type}: {len(f.df)} candidate games")

    # model vectors per era (observed)
    model_by_era = {}
    for era, ids in era_games.items():
        sub = pred.set_index("game_id").loc[ids]
        model_by_era[era] = (sub["model_margin"].to_numpy(float),
                             sub["model_total"].to_numpy(float))

    # 5. observed battery -----------------------------------------------------
    cells = build_cells(frames)
    n_cells = len(cells)
    print(f"[battery] {n_cells} cells enumerated ({time.time()-t0:.0f}s)")
    frames_by_era = {era: [(fi, f) for fi, f in enumerate(frames) if f.era == era]
                     for era in era_games}
    obs_by_era = {}
    all_rows = []
    for era in ("extension", "old"):
        sub_frames = [f for _fi, f in frames_by_era[era]]
        sub_cells = cells[cells["era"] == era].reset_index(drop=True).copy()
        remap = {fi: i for i, (fi, _f) in enumerate(frames_by_era[era])}
        sub_cells["frame_idx"] = sub_cells["frame_idx"].map(remap)
        mv, tv = model_by_era[era]
        rich = eval_battery_rich(sub_frames, sub_cells, mv, tv, args.n_boot)
        obs_by_era[era] = (sub_frames, sub_cells, rich)
        all_rows.append(rich)
    all_cells = pd.concat(all_rows, ignore_index=True)
    print(f"[observed] battery + bootstrap done ({time.time()-t0:.0f}s)")

    # 6. permutation null -----------------------------------------------------
    perm_summ_rows = []
    p_cols = {"n_perm_ge": [], "n_perm_nonempty": [], "perm_roi_mean": [],
              "perm_roi_q95": []}
    for era_i, era in enumerate(("extension", "old")):
        sub_frames, sub_cells, rich = obs_by_era[era]
        cbf = {}
        for i, f in enumerate(sub_frames):
            cbf[i] = []
        for ci, r in sub_cells.iterrows():
            f = sub_frames[r["frame_idx"]]
            payload = None
            if r["level_kind"] == "static":
                payload = next(p for d, l, k, p in f.levels
                               if d == r["cond_dim"] and l == r["cond_level"])
            cbf[r["frame_idx"]].append(
                (ci, r["threshold"], r["execution"], r["cond_dim"],
                 r["cond_level"], r["level_kind"], payload))
        mv, tv = model_by_era[era]
        n_g = len(mv)
        roi_obs = rich["roi"].to_numpy(float)
        elig_obs = (rich["n_bets"].to_numpy(int) >= MIN_CELL_N) & ~np.isnan(roi_obs)
        rng = np.random.default_rng(SEED + era_i)
        perm_mat = np.empty((args.n_perms, len(sub_cells)), np.float32)
        buf = np.empty(len(sub_cells))
        for pi in range(args.n_perms):
            perm = rng.permutation(n_g)
            eval_battery_fast(sub_frames, cbf, mv[perm], tv[perm], buf)
            perm_mat[pi] = buf
        ge = (perm_mat >= (roi_obs[None, :] - ROI_TIE_EPS))
        ge = np.where(np.isnan(perm_mat), False, ge)
        nonempty = ~np.isnan(perm_mat)
        p_cols["n_perm_ge"].append(ge.sum(axis=0))
        p_cols["n_perm_nonempty"].append(nonempty.sum(axis=0))
        with np.errstate(invalid="ignore"):
            p_cols["perm_roi_mean"].append(np.nanmean(
                np.where(nonempty, perm_mat, np.nan), axis=0))
            p_cols["perm_roi_q95"].append(np.nanquantile(
                np.where(nonempty, perm_mat, np.nan), 0.95, axis=0))
        # per-perm global stats over the observed-eligible cells
        if elig_obs.any():
            pm = perm_mat[:, elig_obs]
            max_perm = np.nanmax(np.where(np.isnan(pm), -np.inf, pm), axis=1)
            max_obs = float(np.nanmax(roi_obs[elig_obs]))
            for pi in range(args.n_perms):
                perm_summ_rows.append({
                    "era": era, "perm_idx": pi,
                    "max_roi_over_eligible_cells": float(max_perm[pi]),
                    "n_eligible_cells_perm_beats_obs": int(ge[pi, elig_obs].sum()),
                })
            frac_max = float((max_perm >= max_obs - ROI_TIE_EPS).mean())
        else:
            max_obs, frac_max = np.nan, np.nan
        obs_by_era[era] = (sub_frames, sub_cells, rich, max_obs, frac_max)
        print(f"[perm] {era}: {args.n_perms} permutations over {n_g} games; "
              f"P(best null cell >= best observed) = {frac_max if frac_max==frac_max else float('nan'):.3f} "
              f"({time.time()-t0:.0f}s)")
    for k in p_cols:
        all_cells[k] = np.concatenate(p_cols[k])
    all_cells["p_perm"] = all_cells["n_perm_ge"] / args.n_perms
    all_cells["p_perm_phipson_smyth"] = (all_cells["n_perm_ge"] + 1) / (args.n_perms + 1)
    all_cells.loc[all_cells["roi"].isna(), ["p_perm", "p_perm_phipson_smyth"]] = np.nan

    # 7. BH across starred-eligible cells -------------------------------------
    all_cells["eligible"] = (all_cells["n_bets"] >= MIN_CELL_N) & all_cells["roi"].notna()
    all_cells["small_n_flag"] = ~all_cells["eligible"]
    all_cells["q_bh"] = np.nan
    elig = all_cells["eligible"].to_numpy()
    if elig.any():
        q = bh_qvalues(all_cells.loc[elig, "p_perm"].to_numpy(float))
        all_cells.loc[elig, "q_bh"] = q
    all_cells["starred"] = all_cells["eligible"] & (all_cells["q_bh"] <= BH_Q)
    n_elig = int(all_cells["eligible"].sum())
    survivors = all_cells[all_cells["starred"]].sort_values("roi", ascending=False)
    n_surv = int(len(survivors))
    expected_false = BH_Q * n_surv
    print(f"[bh] eligible cells {n_elig}; survivors {n_surv} "
          f"(expected false among them ~{expected_false:.1f})")

    # known prior pocket
    kp = all_cells
    for k, v in KNOWN_PRIOR_POCKET.items():
        kp = kp[kp[k] == v]
    assert len(kp) == 1, "known prior pocket cell not found"
    kp = kp.iloc[0]

    # 8. audits ---------------------------------------------------------------
    xchk = crosscheck_clv_transfer(all_cells)
    print(f"[crosscheck] {len(xchk)} clv_transfer cells reproduced exactly "
          f"(max |droi| {xchk['droi'].abs().max():.2e})")
    for col in ("era",):
        assert all_cells[col].isin(["extension", "old"]).all()
    push_acct = {
        "pushes_consensus_basis": int(all_cells[
            (all_cells["cond_dim"] == "none") & (all_cells["threshold"] == min(THRESHOLDS))
            & (all_cells["execution"] == "consensus")]["pushes"].sum()),
        "note": "per-cell push counts in all_cells.csv; pushes risk stake, return 0",
    }

    # 9. universe CSVs --------------------------------------------------------
    uni = {era: [] for era in era_games}
    for f in frames:
        mv, tv = model_by_era[f.era]
        uni[f.era].append(universe_frame(f, mv, tv))
    uni_paths = {}
    for era, lst in uni.items():
        u = pd.concat(lst, ignore_index=True)
        p = outdir / f"bet_universe_{era}.csv"
        u.to_csv(p, index=False)
        uni_paths[era] = (p, len(u), int(u["bet_at_min_threshold"].sum()))

    # 10. artifacts -----------------------------------------------------------
    out_cells = all_cells.drop(columns=["frame_idx", "level_kind"])
    out_cells.to_csv(outdir / "all_cells.csv", index=False)
    perm_summ = pd.DataFrame(perm_summ_rows)
    perm_summ.to_csv(outdir / "permutation_summary.csv", index=False)

    season_stability = season_stability_table(frames, model_by_era)
    write_enumeration(outdir, frames, cells, terc_bounds, sched_acct, om_acct,
                      h2h_acct, misc_acct, sigma, args)
    write_ledger(outdir, survivors, expected_false, n_elig, args)
    write_report(outdir, mode, run_time, all_cells, survivors, expected_false,
                 n_elig, kp, obs_by_era, xchk, va, sched_acct, om_acct,
                 h2h_acct, misc_acct, push_acct, uni_paths, terc_bounds,
                 sigma, frames, args, degraded, season_stability)

    # console summary
    n_pos = int((survivors["roi"] > 0).sum())
    print("=" * 70)
    print(f"[summary] cells {n_cells} | eligible {n_elig} | starred survivors "
          f"{n_surv} (expected false ~{expected_false:.1f}) | profitable "
          f"pockets {n_pos} | negative-ROI survivors {n_surv - n_pos}")
    if n_surv:
        for _i, r in survivors[survivors["roi"] > 0].head(5).iterrows():
            print(f"  * {cell_name(r)}: n={int(r['n_bets'])} roi={r['roi']:+.4f} "
                  f"CI[{r['roi_ci90_low']:+.4f},{r['roi_ci90_high']:+.4f}] "
                  f"p={r['p_perm']:.3f} q={r['q_bh']:.3f}")
    print(f"  known prior pocket (ext/T-24h/spread/thr0.5/consensus/none): "
          f"roi={kp['roi']:+.4f} p={kp['p_perm']:.3f} "
          f"q={kp['q_bh'] if pd.notna(kp['q_bh']) else float('nan'):.3f} "
          f"starred={bool(kp['starred'])}")
    print(f"[done] artifacts in {outdir} ({time.time()-t0:.0f}s)")
    return 0


# ---------------------------------------------------------------------------
# writers
# ---------------------------------------------------------------------------

def write_enumeration(outdir, frames, cells, terc_bounds, sched_acct, om_acct,
                      h2h_acct, misc_acct, sigma, args) -> None:
    lines = []
    lines.append("# bet_pocket_mining_v1 — battery enumeration (closed, preregistered)")
    lines.append("")
    lines.append("*The registration's features_desc is the closed battery; this document "
                 "enumerates it. No slices added, none dropped.*")
    lines.append("")
    lines.append("## Cell definition")
    lines.append("")
    lines.append("A cell = (era, timing, bet type, disagreement threshold, execution) "
                 "x ONE conditioning dimension level. The battery is the cross of the "
                 "base grid with each conditioner separately — NOT the full cross of "
                 "all conditioners with each other.")
    lines.append("")
    lines.append("## Dimensions")
    lines.append("")
    lines.append("- threshold: {0.5, 1, 1.5, 2, 3} points of model-vs-market disagreement")
    lines.append("- timing: extension era {T-24h, near-tip}; old era {near-tip} only "
                 "(the single ~T-64m snapshot IS the near-tip line; T-24h has zero "
                 "coverage there — measured in clv_transfer_v1)")
    lines.append("- bet type: extension {spread, total, moneyline}; old {spread} only "
                 "(the old master captured spreads only)")
    lines.append("- execution: consensus (no shopping) vs best_book (line shopping at "
                 "the same vintage)")
    lines.append("- conditioners (one at a time): none; |consensus spread| terciles "
                 "{small, mid, large}; market-total terciles {low, mid, high} "
                 "(extension only — the old era has no totals market to condition on); "
                 "bet side {home, away, fav, dog} for spread/moneyline and "
                 "{over, under} for totals; rest-differential sign "
                 "{home_more, equal, away_more}; season phase {early <=10, mid 11-30, "
                 "late >30} team game number; weekend flag {weekend, weekday}")
    lines.append("")
    lines.append("## Cell count")
    lines.append("")
    cnt = cells.groupby(["era", "timing", "bet_type"]).size().reset_index(name="n_cells")
    lines.append(fmt_table(cnt))
    lines.append("")
    lines.append(f"**Total cells: {len(cells)}.** Per (era, timing, bet type): "
                 "5 thresholds x 2 executions x conditioner levels "
                 "(extension spread/moneyline 19 = 1 none + 3 line + 3 total + 4 side "
                 "+ 3 rest + 3 phase + 2 weekend; extension totals 17 (side has 2 "
                 "levels); old spread 16 (no market-total terciles)).")
    lines.append("")
    lines.append("Note: side levels overlap (a home bet on a home favorite sits in "
                 "both side=home and side=fav) and every bet sits in the none/all "
                 "cell; within the other dimensions levels partition their frame. "
                 "Overlap is a property of the registered battery, handled honestly "
                 "by the permutation null + BH (each cell's null is its own).")
    lines.append("")
    lines.append("## Conventions (binding for reproduction)")
    lines.append("")
    lines.append("- Consensus vintages: hour cutoffs use the latest snapshot "
                 "timestamp <= cutoff (mean over books present at that single "
                 "vintage); near-tip uses each book's latest pre-tip row "
                 "(clv_transfer_v1 conventions, reproduced exactly — see the "
                 "crosscheck audit).")
    lines.append("- Spread edge = str_margin_cal - market_margin, market_margin = "
                 "-(consensus home spread). Total edge = str_total_cal - consensus "
                 "total. Moneyline edge (points scale, so the registered thresholds "
                 "apply unchanged) = str_margin_cal - sigma*ppf(devigged consensus "
                 f"home prob), sigma = {sigma:.4f} from dist_margin_cover; model "
                 "home-win prob = Phi(center/sigma) = the Gaussian cover formula at "
                 "spread 0.")
    lines.append("- h2h devig: proportional, per book with a valid two-sided pair "
                 "(|american price| < 10000); consensus prob = mean over books.")
    lines.append("- Pricing: spread/total consensus basis settles on the consensus "
                 "line at synthetic -110; best_book basis takes the most favorable "
                 "captured line (tie-break: best price) and settles on the line "
                 "taken. MONEYLINE ADAPTATION (documented deviation): a synthetic "
                 "-110 is meaningless for moneylines (favorites pay far less), so "
                 "the consensus basis pays the MEAN payout multiplier over books "
                 "quoting the bet side at the vintage; best_book pays the best "
                 "multiplier. Both remain flat-stake.")
    lines.append("- Grading: margin_true vs line (spread), total_true vs line "
                 "(total), margin_true > 0 (moneyline; no ties exist). Pushes risk "
                 "the stake and return 0; ROI = net profit / stakes settled.")
    lines.append("- CLV (T-24h cells only; the only timing with a later reference): "
                 "signed points the near-tip consensus moved toward the bet side; "
                 "moneyline CLV in implied-margin points via the same sigma*ppf map.")
    lines.append("- Terciles are computed per (era, timing) over candidate games "
                 "with a model prediction; boundaries:")
    for (era, timing, what), (q1, q2) in sorted(terc_bounds.items()):
        if q1 == q1:
            lines.append(f"    - {era}/{timing} {what}: q33 {q1:.3f} / q67 {q2:.3f}")
    lines.append("- Season phase = mean of the two teams' season game numbers "
                 "(including the target game, both season types, from master_team "
                 "dates — schedule known pregame, walk-forward safe). Rest = days "
                 "since the team's previous game within the season; season openers "
                 "have undefined rest sign and are excluded from rest cells only. "
                 "Weekend = Sat/Sun by game date.")
    lines.append("- Null calibration: per era, "
                 f"{args.n_perms} permutations of the model column (margin + total "
                 "shuffled JOINTLY, one draw per battery) across the era's candidate "
                 "games; per-cell p = fraction of permuted batteries with "
                 "equal-or-better ROI in that cell (empty permuted cells count as "
                 "not-better; min resolvable p = 1/n_perms; a Phipson-Smyth "
                 "companion column is reported). BH at 10% across all "
                 "starred-eligible (n >= 40) cells.")
    lines.append("")
    lines.append(f"Accounting: {json.dumps({**om_acct, **h2h_acct, **misc_acct}, default=str)}")
    lines.append(f"Schedule features: {json.dumps(sched_acct, default=str)}")
    (outdir / "ENUMERATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_ledger(outdir, survivors, expected_false, n_elig, args) -> None:
    pos = survivors[survivors["roi"] > 0]
    neg = survivors[survivors["roi"] <= 0]
    lines = []
    lines.append("# POCKET LEDGER — bet_pocket_mining_v1")
    lines.append("")
    lines.append("**candidates only - confirmed by the live log going forward.**")
    lines.append("")
    lines.append(f"Mined retrospectively from the frozen committed model over the "
                 f"registered closed battery; {n_elig} cells were large enough to "
                 f"star (n >= 40). {len(survivors)} cells passed the "
                 f"{args.n_perms}-permutation within-era null + Benjamini-Hochberg "
                 f"at 10 percent — **expected false discoveries among them: "
                 f"~{expected_false:.1f}**. Of those, **{len(pos)} are profitable "
                 f"(ROI > 0) — the pockets below**; {len(neg)} beat the null while "
                 "still LOSING money (listed at the bottom; they are evidence the "
                 "model column carries placement information, not bettable "
                 "pockets). A pocket on this list is a hypothesis to paper-trade "
                 "in the prospective log, not an edge to bet.")
    lines.append("")
    lines.append("**These are NOT independent discoveries.** Survivors are "
                 "overlapping slices of a handful of phenomena (family view in "
                 "section 2); a single hot family fans out across thresholds, "
                 "executions and conditioners. Count phenomena, not rows.")
    lines.append("")
    if not len(survivors):
        lines.append("## No surviving pockets")
        lines.append("")
        lines.append("Zero cells survived the null calibration at FDR 10 percent. "
                     "That is a legitimate result: on this sample the committed "
                     "model's disagreements with the market show no conditioning "
                     "slice distinguishable from luck after multiplicity control. "
                     "The live prospective log remains the only confirmation "
                     "channel; nothing graduates from this study.")
    elif not len(pos):
        lines.append("## No PROFITABLE surviving pockets")
        lines.append("")
        lines.append(f"All {len(survivors)} survivors have ROI <= 0 (see the "
                     "bottom table): the model column beats shuffled placement "
                     "but no slice makes money. Nothing graduates to "
                     "paper-trading from this study.")
    else:
        lines.append(f"## 1. {len(pos)} profitable pocket(s), ranked by ROI")
        lines.append("")
        lines.append("`CI+` = the 90% date-clustered CI sits entirely above zero "
                     "(the strongest tier). `mech` is a one-line hypothesis "
                     "written AFTER seeing the result; ANOMALY = no mechanism we "
                     "can defend — kept, never dropped (registration rule).")
        lines.append("")
        show = pos.copy()
        show["cell"] = show.apply(cell_name, axis=1)
        show["tier"] = np.where(show["roi_ci90_low"] > 0, "CI+", "")
        stories = show.apply(mechanism, axis=1)
        show["mech"] = [s for s, _a in stories]
        show["mech"] = np.where([a for _s, a in stories],
                                "ANOMALY - no defensible mechanism; kept",
                                show["mech"])
        tbl = show[["cell", "n_bets", "roi", "roi_ci90_low", "roi_ci90_high",
                    "hit_rate", "p_perm", "q_bh", "mean_clv_pts", "tier", "mech"]]
        lines.append(fmt_table(tbl))
        lines.append("")
        lines.append("## 2. The phenomena behind the rows (family view)")
        lines.append("")
        fam = pos.groupby(["era", "timing", "bet_type"]).agg(
            n_cells=("roi", "size"), best_roi=("roi", "max"),
            median_roi=("roi", "median")).reset_index()
        lines.append(fmt_table(fam))
        lines.append("")
        lines.append("Cross-corroboration worth naming (still candidates):")
        rest_fams = pos[pos["cond_level"] == "home_more"]
        if len(rest_fams):
            fams = sorted(set(zip(rest_fams["era"], rest_fams["bet_type"])))
            lines.append(f"- **Rest advantage (home_more)** stars in "
                         f"{len(fams)} independent bet-type/era families "
                         f"({', '.join(f'{e} {b}' for e, b in fams)}) — the same "
                         "mechanism surfacing in disjoint data is the closest "
                         "thing to internal replication this study can offer.")
        clv_pos = pos[(pos["mean_clv_pts"].notna()) & (pos["mean_clv_pts"] > 0.2)]
        if len(clv_pos):
            lines.append(f"- **CLV corroboration:** {len(clv_pos)} profitable "
                         "T-24h pockets also show mean CLV > +0.2 pts (the "
                         "near-tip market moved toward these bets) — an "
                         "independent honesty signal, since CLV does not depend "
                         "on game outcomes.")
        lines.append("- The moneyline family is dog-heavy by construction (the "
                     "calibrated model shrinks margins ~0.78 toward the mean, so "
                     "it systematically sees favorites as overpriced); its ROI "
                     "rides a small number of big-payout wins — n is bets, not "
                     "effective sample.")
        lines.append("")
        if len(neg):
            lines.append(f"## 3. {len(neg)} negative-ROI survivor(s) — NOT pockets")
            lines.append("")
            lines.append("These cells beat the permutation null while losing "
                         "money. The permuted-model null for totals is an "
                         "anti-informative strategy (a shuffled model mostly "
                         "bets against extreme market totals and loses far more "
                         "than the vig — null means of -10% to -21% in these "
                         "cells), so 'better than null' does not mean "
                         "profitable. Kept for the record:")
            lines.append("")
            shn = neg.copy()
            shn["cell"] = shn.apply(cell_name, axis=1)
            lines.append(fmt_table(shn[["cell", "n_bets", "roi", "roi_ci90_low",
                                        "roi_ci90_high", "p_perm", "q_bh",
                                        "perm_roi_mean"]]))
            lines.append("")
        lines.append("Every mechanism line above is a HYPOTHESIS written after "
                     "seeing the result — it earns nothing until the live log "
                     "confirms it. Anomaly-flagged pockets are kept per the "
                     "registration: unexplained survivors are reported, never "
                     "dropped.")
    lines.append("")
    lines.append("**candidates only - confirmed by the live log going forward.**")
    (outdir / "POCKET_LEDGER.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(outdir, mode, run_time, all_cells, survivors, expected_false,
                 n_elig, kp, obs_by_era, xchk, va, sched_acct, om_acct,
                 h2h_acct, misc_acct, push_acct, uni_paths, terc_bounds,
                 sigma, frames, args, degraded, season_stability) -> None:
    L = []
    L.append("# bet_pocket_mining_v1 — where (if anywhere) does the model have "
             "specific edge?")
    L.append("")
    L.append(f"*Generated by `pocket_mining.py` on {run_time} — mode: {mode}. "
             "Preregistered measurement study (`experiments/registry.jsonl`, "
             "registered 2026-07-31T14:19:57Z; regime A; primary metric "
             "`pocket_roi_flat_stake`; incumbent `market_at_matched_timing`). "
             "SENTINEL GATES BY DESIGN: retrospective mining produces CANDIDATES "
             "only; the confirmation channel is the live prospective log. "
             "Directive John 2026-07-31: we do not need to beat the books on "
             "average - we need to identify where we have specific edge.*")
    if degraded:
        L.append("")
        L.append(f"**WARNING: DEV SETTINGS (n_perms={args.n_perms}, "
                 f"n_boot={args.n_boot}) — NOT the registered artifact.**")
    L.append("")
    n_surv = len(survivors)
    pos = survivors[survivors["roi"] > 0]
    neg = survivors[survivors["roi"] <= 0]
    L.append("## 1. Headline")
    L.append("")
    L.append(f"- Battery: **{len(all_cells)} cells** (enumeration in "
             f"`ENUMERATION.md`); **{n_elig} starred-eligible** (n >= 40 bets); "
             f"**{n_surv} survivor(s)** of the {args.n_perms}-permutation null + "
             f"Benjamini-Hochberg at 10% — **expected false among survivors "
             f"~{expected_false:.1f}**. Of the survivors, **{len(pos)} are "
             f"profitable pockets (ROI > 0)** and {len(neg)} beat the null while "
             "still losing money (see section 5 — 'better than a shuffled model' "
             "is not 'profitable').")
    L.append(f"- Survivors are OVERLAPPING slices of a few phenomena, not "
             f"{n_surv} independent discoveries — family view in section 5 and "
             "the ledger.")
    for era in ("extension", "old"):
        tup = obs_by_era[era]
        max_obs, frac_max = tup[3], tup[4]
        if max_obs == max_obs:
            L.append(f"- {era} era global null check: best observed eligible-cell "
                     f"ROI {max_obs:+.4f}; fraction of permuted batteries whose "
                     f"BEST eligible cell beats it: {frac_max:.3f} "
                     f"(a family-wise sanity number, complementary to per-cell BH).")
    if len(pos):
        top = pos.iloc[0]
        strong = pos[pos["roi_ci90_low"] > 0]
        L.append(f"- Top profitable pocket: **{cell_name(top)}** — "
                 f"n={int(top['n_bets'])}, "
                 f"ROI {top['roi']:+.4f} (90% CI [{top['roi_ci90_low']:+.4f}, "
                 f"{top['roi_ci90_high']:+.4f}]), p={top['p_perm']:.3f}, "
                 f"q={top['q_bh']:.3f}. **{len(strong)} pockets have their whole "
                 f"90% CI above zero.** Full ranked list with mechanism "
                 f"hypotheses: `POCKET_LEDGER.md`.")
    elif n_surv:
        L.append("- **No profitable pockets:** every survivor has ROI <= 0; "
                 "nothing graduates to paper-trading from this study.")
    else:
        L.append("- **Zero pockets survived.** On this sample, no registered "
                 "slice of the committed model's disagreements is distinguishable "
                 "from luck at FDR 10% — reported plainly per the registration; "
                 "nothing graduates to paper-trading from this study.")
    L.append(f"- Known prior pocket (clv_transfer_v1's extension/T-24h thr-0.5 "
             f"consensus cell, +6.4% there): in this battery it shows "
             f"ROI {kp['roi']:+.4f}, p={kp['p_perm']:.3f}, "
             f"q={kp['q_bh']:.3f}, **starred: {bool(kp['starred'])}** — it got "
             "no special treatment, per the registration.")
    L.append("")
    L.append("## 2. The base grid (unconditioned cells)")
    L.append("")
    base = all_cells[all_cells["cond_dim"] == "none"].copy()
    base = base.sort_values(["era", "timing", "bet_type", "execution", "threshold"])
    L.append(fmt_table(base[["era", "timing", "bet_type", "threshold", "execution",
                             "n_bets", "hit_rate", "roi", "roi_ci90_low",
                             "roi_ci90_high", "mean_clv_pts", "p_perm", "q_bh",
                             "starred"]]))
    L.append("")
    L.append("Reading: consensus basis = consensus line at -110 (moneyline: mean "
             "quoted payout, see ENUMERATION); best_book = line shopping at the "
             "same vintage. Every row carries its era; extension and old are "
             "never pooled.")
    L.append("")
    L.append("## 3. Most extreme cells by permutation p (starred-eligible only)")
    L.append("")
    el = all_cells[all_cells["eligible"]].sort_values(
        ["p_perm", "roi"], ascending=[True, False]).head(15).copy()
    if len(el):
        el["cell"] = el.apply(cell_name, axis=1)
        L.append(fmt_table(el[["cell", "n_bets", "hit_rate", "roi",
                               "roi_ci90_low", "roi_ci90_high", "p_perm",
                               "q_bh", "starred"]]))
    else:
        L.append("(no eligible cells)")
    L.append("")
    L.append(f"p granularity: {args.n_perms} permutations resolve p no finer than "
             f"{1.0/args.n_perms:.4f}; ties at p=0 are ranked by ROI. The "
             "Phipson-Smyth companion (never exactly zero) is in `all_cells.csv`.")
    L.append("")
    L.append("## 4. Null calibration (the honesty machinery)")
    L.append("")
    L.append(f"- Design: per era, {args.n_perms} permutations shuffle the model "
             "column (str_margin_cal + str_total_cal JOINTLY, one draw per "
             "battery recompute) across the era's candidate games; market lines, "
             "outcomes and every conditioner stay put. The full battery is "
             "recomputed per permutation; a cell's p is the fraction of permuted "
             "batteries producing an equal-or-better ROI in that cell (empty "
             "permuted cells count as not-better).")
    L.append(f"- Multiplicity: BH at 10% across the {n_elig} starred-eligible "
             f"cells; {n_surv} rejections; the FDR contract itself is the "
             f"expected-false companion: ~{expected_false:.1f} of the survivors "
             "are expected to be false.")
    L.append("- Per-cell null context (perm_roi_mean, perm_roi_q95, "
             "n_perm_nonempty) is in `all_cells.csv`; per-permutation battery "
             "maxima are in `permutation_summary.csv`.")
    L.append("- **The null is NOT uniformly the vig.** Spread nulls center near "
             "-4.5% (a shuffled model is a coin flip at -110). The totals nulls "
             "center far LOWER (-10% to -21% in conditioned cells): a shuffled "
             "model's totals edge is dominated by -(market deviation), i.e. it "
             "systematically bets AGAINST extreme market totals, and the market "
             "wins that fight. Consequence: some totals cells star with "
             "NEGATIVE ROI — the model places totals bets far better than "
             "shuffled placement, but not profitably. Those cells are separated "
             "in section 5 and in the ledger; they are never called pockets.")
    L.append("")
    L.append("## 5. Survivor families (correlated slices, not independent finds)")
    L.append("")
    fam_rows = []
    for (era, timing, bt), grp in survivors.groupby(["era", "timing", "bet_type"]):
        gpos = grp[grp["roi"] > 0]
        fam_rows.append({
            "era": era, "timing": timing, "bet_type": bt,
            "survivor_cells": len(grp), "profitable_cells": len(gpos),
            "best_roi": float(grp["roi"].max()),
            "median_roi": float(grp["roi"].median()),
            "ci_above_zero_cells": int((gpos["roi_ci90_low"] > 0).sum()),
        })
    if fam_rows:
        L.append(fmt_table(pd.DataFrame(fam_rows)))
    else:
        L.append("(no survivors)")
    L.append("")
    L.append("Reading: a hot in-sample family fans out across thresholds, "
             "executions and conditioners (5 x 2 x 19 = 190 cells per era-timing "
             "bet type), so survivor COUNTS measure family footprint, not "
             "evidence strength. The distinct candidate phenomena and their "
             "cross-corroboration are named in `POCKET_LEDGER.md`.")
    L.append("")
    if len(pos):
        L.append("### Season stability of the top families (descriptive context "
                 "only — NOT battery cells, ungated)")
        L.append("")
        L.append(fmt_table(season_stability))
        L.append("")
        L.append("Within-era season splits of the headline families. A "
                 "candidate whose ROI lives entirely in one season is weaker "
                 "than its pooled row suggests; this table exists so nobody "
                 "quotes a pooled pocket without seeing its season mix. (Season "
                 "splits within one era only — era discipline unchanged.)")
        L.append("")
    L.append("## 6. Universes")
    L.append("")
    urows = []
    for f in frames:
        urows.append({"era": f.era, "timing": f.timing, "bet_type": f.bet_type,
                      "candidate_games": len(f.df)})
    L.append(fmt_table(pd.DataFrame(urows)))
    L.append("")
    for era, (p, n_rows, n_bets) in uni_paths.items():
        L.append(f"- `{p.name}`: {n_rows} candidate rows, {n_bets} bets at the "
                 f"0.5 minimum threshold (era {era}).")
    L.append("")
    L.append("## 7. Audits")
    L.append("")
    L.append(f"- **Vintage audit:** {va['rows_checked']} matched consensus rows "
             "(all three markets) assert snapshot <= cutoff < tip (hour cutoffs) "
             "and snapshot < tip (all): 0 violations.")
    L.append(f"- **clv_transfer reproduction:** the {len(xchk)} unconditioned "
             "spread cells shared with clv_transfer_v1 (extension/T-24h and "
             "old/near-tip a.k.a. T-64m, all thresholds, both executions) "
             "reproduce its flat_stake_sim.csv EXACTLY (n, wins, ROI; max |dROI| "
             f"{xchk['droi'].abs().max():.1e}) — same universe, same conventions, "
             "independent implementation.")
    L.append("- **No-blend audit:** every output row carries era in "
             "{extension, old}; era game sets are disjoint (asserted); no "
             "number in any artifact pools the two eras.")
    L.append(f"- **Moneyline sanity:** margin_true != 0 asserted for all games; "
             f"devig pairs require |price| < {PRICE_ANOMALY_ABS}; "
             f"{h2h_acct['h2h_price_anomaly_rows']} anomalous prices excluded, "
             f"{h2h_acct['h2h_games_no_valid_pair']} game-vintages dropped for "
             f"no valid pair; {misc_acct.get('ml_probs_clipped', 0)} devigged "
             f"probs clipped at {P_CLIP}.")
    L.append(f"- **Totals hygiene:** {om_acct['totals_point_mismatch_rows']} "
             "Over/Under point-mismatch rows excluded; "
             f"{om_acct['h2h_rows_not_matching_either_team']} h2h rows matched "
             "neither listed team.")
    L.append(f"- **Push accounting:** {json.dumps(push_acct)}")
    L.append(f"- **Schedule features:** {json.dumps(sched_acct, default=str)}")
    L.append("")
    L.append("## 8. Limitations (read before quoting any pocket)")
    L.append("")
    L.append("1. **Retrospective, in-sample mining.** Every number here is "
             "selection-prone by construction; the permutation null + BH controls "
             "luck-mining within the registered battery, not out-of-sample decay. "
             "Confirmation happens ONLY in the live prospective log.")
    L.append("2. **Overlapping cells.** Side slices overlap each other and every "
             "conditioner contains the base cell; the BH family treats cells as "
             "exchangeable hypotheses. Plain BH is valid under the positive "
             "dependence this overlap induces, but the effective number of "
             "independent looks is smaller than the cell count.")
    L.append("3. **Extension-era totals/moneyline samples are small** (one-plus "
             "season, ~300-365 games) and are labeled small-n wherever n < 40; "
             "most conditioned totals/ML cells are descriptive only.")
    L.append("4. **Information parity:** T-24h lines may already price "
             "availability news the model cannot see (ROADMAP caveat); matched "
             "timing fixes the clock, not the information sets.")
    L.append("5. **Consensus panel drift:** book panels are thinner at T-24h "
             "than near tip; consensus composition varies by vintage.")
    L.append("6. **Moneyline pricing adaptation:** synthetic -110 is undefined "
             "for moneylines; consensus basis uses the mean quoted payout "
             "multiplier (documented in ENUMERATION.md). ML CLV is in "
             "implied-margin points via the frozen sigma map.")
    L.append("7. **Old era:** spreads only, single ~T-64m snapshot, no CLV, no "
             "totals conditioning; its battery is structurally smaller — cells "
             "absent there are absent by data reality, not choice.")
    L.append("8. **Props are not minable historically** (registration note): no "
             "props were ever captured; props capture starts 2026-07-31 "
             "forward-only, so the per-player engine's prop edge becomes testable "
             "only as that capture accumulates.")
    L.append("9. p granularity 1/" + str(args.n_perms) + " and BH on plain "
             "permutation p (registered formula); the Phipson-Smyth column is "
             "reported alongside for readers who prefer never-zero p.")
    L.append("")
    L.append("## 9. Files")
    L.append("")
    L.append("| file | contents |")
    L.append("|---|---|")
    L.append("| `all_cells.csv` | every cell: definition, n/wins/losses/pushes, "
             "hit, ROI (own basis) + both-basis ROIs, 90% date-clustered CI, "
             "CLV, permutation p (+ Phipson-Smyth), BH q, starred/eligible flags, "
             "per-cell null context |")
    L.append("| `bet_universe_extension.csv` / `bet_universe_old.csv` | row-level "
             "candidate universe per era: every (timing, bet type, game) with "
             "model/market values, edge, side, both settlements, CLV, all "
             "conditioner levels |")
    L.append("| `permutation_summary.csv` | per era x permutation: best "
             "eligible-cell ROI and count of cells beating observed |")
    L.append("| `ENUMERATION.md` | the closed battery enumerated + binding "
             "conventions (tercile boundaries, ML adaptation, phase/rest "
             "definitions) |")
    L.append("| `POCKET_LEDGER.md` | John-facing ranked survivors with mechanism "
             "hypotheses and anomaly flags |")
    L.append("| `REPORT.md` | this file |")
    L.append("")
    L.append("Reproduce: `python pocket_mining.py --smoke` (full data; no ledger "
             "interaction; deterministic seeds). This study records nothing on "
             "the registry ledger — any recording is the orchestrator's, after "
             "verification.")
    (outdir / "REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
