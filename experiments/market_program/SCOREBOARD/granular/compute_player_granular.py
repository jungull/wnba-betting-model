#!/usr/bin/env python3
"""compute_player_granular.py -- D037 GRANULAR PLAYER METRICS generator.

Computes, under the D036 measurement semantics (DECISION_LEDGER.jsonl lines 36-37):

  TASK 1  NAIVE_BASELINE evidence class: trailing-5-game mean, season-to-date
          mean, and league mean for eight player stats (points, rebounds,
          assists, steals, blocks, threes made, turnovers, minutes), every
          player-game 2022-2026, strictly-prior-games-only by construction.
  TASK 3  MARKET_THRESHOLD evidence class where prop lines exist: de-vigged
          over/under accuracy, Brier, and THRESHOLD MAE (line vs realized --
          never presented as projection MAE, D036 point 5), with full join
          audit (no silent drops).

Outputs (this directory):
  player_granular_metrics.json    every number with a D036 provenance block
  player_granular_coverage.json   universes, join audit, cold-start counts,
                                  unmatched row listings

DATA SOURCES (documented per D036 point 8)
-------------------------------------------
Stats 2022-2024: data/wnba_gamelog_2022..2024.parquet (the owned per-player
  gamelogs; regular season only; verified COMPLETE against
  data/masters/master_player.parquet game counts: 216/240/240 games).
  Columns used: GAME_ID, PLAYER_ID, PLAYER_NAME, SEASON, MIN, FG3M, REB, AST,
  STL, BLK, TO, PTS. These files carry NO game date; GAME_DATE is joined from
  data/masters/master_player.parquet (game_id -> game_date lookup ONLY -- no
  stat value is taken from the master).
Stats 2025: data/wnba_gamelog_2025.parquet is TRUNCATED -- it holds only 108
  of the season's 286 regular-season games (2025-05-16..2025-06-29). 2025 is
  therefore taken from data/refresh_2026/gamelog_player_2025_regular_season
  .parquet (all 286 games), after verifying that the two sources agree
  EXACTLY on every one of the 2072 overlapping player-game rows (identical
  row counts and identical sums of PTS/REB/AST/TOV/FG3M/STL/BLK).
Stats 2026: data/wnba_gamelog_2026.parquet DOES NOT EXIST on this worktree.
  The only 2026 per-player gamelog on disk is
  data/refresh_2026/gamelog_player_2026_regular_season.parquet.
  Refresh-file columns used: GAME_ID, GAME_DATE, PLAYER_ID, PLAYER_NAME, MIN,
  FG3M, REB, AST, STL, BLK, TOV, PTS. Refresh MIN is integer-minute
  resolution, unlike the mm:ss strings of the 2022-2024 files; recorded in
  the coverage artifact.
Props: data/props_capture/historical/master_props_historical.csv on the LIVE
  worktree (read-only; D027 bounded use, T1 vendor-asserted snapshots). The
  archive holds ONE market family (player_points), one snapshot per game.

CUTOFF DISCIPLINE
-----------------
All three baselines are leakage-free BY CONSTRUCTION:
  trailing-5      mean of the player's last min(5, k) games strictly earlier
                  in the same season's player sequence (ordered by game_date,
                  then GAME_ID).
  season-to-date  mean of ALL the player's strictly earlier same-season games.
  league mean     mean of the stat over ALL league player-games on strictly
                  earlier CALENDAR DATES of the same season (same-day games
                  are concurrent and excluded).
COLD-START RULE (stated per the task): a player-game where the baseline has
zero strictly-prior observations (player's first game of the season for
trailing-5/season-to-date; the season's first calendar date for league mean)
receives NO prediction from that baseline, is EXCLUDED from that baseline's
error metrics, and is COUNTED in the coverage artifact. History never crosses
seasons.

Vig math is delegated to experiments/market_program/M11_CONSENSUS_MODEL/
consensus.py (preregistered multiplicative method).

Stdlib + pandas/numpy. No git, no network. Deterministic: SEED below.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[3]                     # .../player-model-program
LIVE_ROOT = Path(r"C:\Users\jgallagher\wnba-betting-model")

M11 = WORKTREE / "experiments" / "market_program" / "M11_CONSENSUS_MODEL"
sys.path.insert(0, str(M11))
import consensus  # noqa: E402  (no_vig, PREREGISTERED_VIG_METHOD)

SEED = 20260806
N_BOOT = 1000

GAMELOG_FILES = {s: WORKTREE / "data" / f"wnba_gamelog_{s}.parquet"
                 for s in (2022, 2023, 2024)}
REFRESH_FILES = {s: (WORKTREE / "data" / "refresh_2026" /
                     f"gamelog_player_{s}_regular_season.parquet")
                 for s in (2025, 2026)}
MASTER_PLAYER = WORKTREE / "data" / "masters" / "master_player.parquet"
PROPS_CSV = (LIVE_ROOT / "data" / "props_capture" / "historical" /
             "master_props_historical.csv")

STATS = ["points", "rebounds", "assists", "steals", "blocks",
         "threes_made", "turnovers", "minutes"]
# stat -> column in the assembled frame
STAT_COL = {"points": "pts", "rebounds": "reb", "assists": "ast",
            "steals": "stl", "blocks": "blk", "threes_made": "fg3m",
            "turnovers": "tov", "minutes": "minutes"}
BASELINES = ["trailing_5_mean", "season_to_date_mean", "league_mean"]

MARKET_TO_STAT = {"player_points": "points"}

EVIDENCE_NAIVE = "NAIVE_BASELINE"
EVIDENCE_MARKET = "MARKET_THRESHOLD"


# ---------------------------------------------------------------------------
# small utilities
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


_MIN_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)(?::(\d{1,2}))?\s*$")


def parse_min(v) -> float:
    """Parse the gamelog MIN field.

    Observed formats: '30.000000:46' (minutes-with-noise-decimals : seconds),
    '33:02', bare numbers, ints (2026 file), None/NaN -> 0.0.
    """
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return 0.0
    if isinstance(v, (int, np.integer)):
        return float(v)
    if isinstance(v, (float, np.floating)):
        return float(v)
    m = _MIN_RE.match(str(v))
    if not m:
        raise ValueError(f"unparseable MIN value: {v!r}")
    minutes = float(m.group(1))
    seconds = float(m.group(2)) if m.group(2) is not None else 0.0
    return minutes + seconds / 60.0


def normalize_name(name: str) -> str:
    """Accent-fold, lowercase, strip punctuation -- for the props join."""
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[.'`\-]", " ", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def mae_rmse_bias(pred: np.ndarray, actual: np.ndarray) -> dict:
    err = pred - actual
    return {"mae": float(np.mean(np.abs(err))),
            "rmse": float(np.sqrt(np.mean(err ** 2))),
            "bias": float(np.mean(err))}


def cluster_bootstrap_ci(values: np.ndarray, clusters: np.ndarray,
                         n_boot: int = N_BOOT, seed: int = SEED,
                         alpha: float = 0.05) -> dict:
    """95% CI on the MEAN of `values`, cluster-bootstrapped over `clusters`
    (game dates). Resamples clusters with replacement; statistic is the
    cluster-size-weighted mean, i.e. exactly the plain mean of the pooled
    resampled rows. Percentile interval. Deterministic under `seed`."""
    values = np.asarray(values, dtype=float)
    codes, _ = pd.factorize(clusters, sort=True)
    n_clusters = int(codes.max()) + 1
    sums = np.zeros(n_clusters)
    counts = np.zeros(n_clusters)
    np.add.at(sums, codes, values)
    np.add.at(counts, codes, 1.0)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n_clusters, size=(n_boot, n_clusters))
    boot = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    lo, hi = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"lo": float(lo), "hi": float(hi), "n_boot": int(n_boot),
            "n_clusters": int(n_clusters), "seed": int(seed),
            "method": "cluster_bootstrap_over_game_dates_percentile"}


# ---------------------------------------------------------------------------
# data assembly
# ---------------------------------------------------------------------------

COLS_PINNED = ["GAME_ID", "PLAYER_ID", "PLAYER_NAME", "SEASON", "MIN",
               "FG3M", "REB", "AST", "STL", "BLK", "TO", "PTS"]
COLS_REFRESH = ["GAME_ID", "GAME_DATE", "PLAYER_ID", "PLAYER_NAME", "MIN",
                "FG3M", "REB", "AST", "STL", "BLK", "TOV", "PTS"]


def load_gamelogs() -> tuple[pd.DataFrame, dict]:
    """Assemble the 2022-2026 player-game frame. Returns (df, audit)."""
    audit = {"sources": {}, "n_duplicate_rows_dropped": 0,
             "n_gameid_without_date": 0}
    frames = []
    date_map = (pd.read_parquet(MASTER_PLAYER, columns=["game_id", "game_date"])
                .drop_duplicates("game_id"))
    date_map["game_id"] = date_map["game_id"].astype(str)
    date_lookup = dict(zip(date_map["game_id"], date_map["game_date"]))

    for season, path in GAMELOG_FILES.items():
        g = pd.read_parquet(path, columns=COLS_PINNED)
        df = pd.DataFrame({
            "game_id": g["GAME_ID"].astype(str),
            "player_id": g["PLAYER_ID"].astype("int64"),
            "player_name": g["PLAYER_NAME"].astype(str),
            "season": int(season),
            "minutes": g["MIN"].map(parse_min),
            "fg3m": g["FG3M"].astype(float),
            "reb": g["REB"].astype(float),
            "ast": g["AST"].astype(float),
            "stl": g["STL"].astype(float),
            "blk": g["BLK"].astype(float),
            "tov": g["TO"].astype(float),
            "pts": g["PTS"].astype(float),
        })
        df["game_date"] = df["game_id"].map(date_lookup)
        frames.append(df)
        audit["sources"][str(season)] = {
            "path": str(path.relative_to(WORKTREE)).replace("\\", "/"),
            "sha256": sha256_file(path), "n_rows": int(len(g)),
            "columns_used": COLS_PINNED,
            "date_source": "data/masters/master_player.parquet (game_id->game_date lookup only)",
        }

    refresh_notes = {
        2025: ("data/wnba_gamelog_2025.parquet is TRUNCATED (108/286 "
               "regular-season games, 2025-05-16..2025-06-29); this refresh "
               "file holds all 286 and agrees exactly with the pinned file "
               "on every overlapping player-game row (verified: identical "
               "row counts and PTS/REB/AST/TOV/FG3M/STL/BLK sums over the "
               "2072 common rows)."),
        2026: ("data/wnba_gamelog_2026.parquet is ABSENT from this worktree; "
               "this refresh_2026 regular-season file is the only 2026 "
               "per-player gamelog on disk."),
    }
    for season, path in REFRESH_FILES.items():
        gr = pd.read_parquet(path, columns=COLS_REFRESH)
        dfr = pd.DataFrame({
            "game_id": gr["GAME_ID"].astype(str),
            "player_id": gr["PLAYER_ID"].astype("int64"),
            "player_name": gr["PLAYER_NAME"].astype(str),
            "season": int(season),
            "minutes": gr["MIN"].map(parse_min),
            "fg3m": gr["FG3M"].astype(float),
            "reb": gr["REB"].astype(float),
            "ast": gr["AST"].astype(float),
            "stl": gr["STL"].astype(float),
            "blk": gr["BLK"].astype(float),
            "tov": gr["TOV"].astype(float),
            "pts": gr["PTS"].astype(float),
            "game_date": pd.to_datetime(gr["GAME_DATE"]).dt.strftime("%Y-%m-%d"),
        })
        frames.append(dfr)
        audit["sources"][str(season)] = {
            "path": str(path.relative_to(WORKTREE)).replace("\\", "/"),
            "sha256": sha256_file(path), "n_rows": int(len(gr)),
            "columns_used": COLS_REFRESH,
            "note": refresh_notes[season] + (" Refresh MIN is integer-minute "
                    "resolution (coarser than the pinned mm:ss strings)."),
        }
    audit["sources"]["date_lookup"] = {
        "path": "data/masters/master_player.parquet",
        "sha256": sha256_file(MASTER_PLAYER),
        "columns_used": ["game_id", "game_date"],
        "role": "GAME_ID -> game_date only; no stat values taken",
    }

    full = pd.concat(frames, ignore_index=True)
    n_missing_date = int(full["game_date"].isna().sum())
    audit["n_gameid_without_date"] = n_missing_date
    if n_missing_date:
        missing_ids = sorted(full.loc[full["game_date"].isna(), "game_id"].unique())
        audit["gameids_without_date"] = missing_ids
        full = full.dropna(subset=["game_date"])
    full["game_date"] = full["game_date"].astype(str)

    before = len(full)
    full = full.drop_duplicates(subset=["game_id", "player_id"], keep="first")
    audit["n_duplicate_rows_dropped"] = int(before - len(full))

    full = full.sort_values(["season", "player_id", "game_date", "game_id"],
                            kind="mergesort").reset_index(drop=True)
    return full, audit


# ---------------------------------------------------------------------------
# baseline predictions (strictly-prior by construction)
# ---------------------------------------------------------------------------

def add_baseline_predictions(df: pd.DataFrame) -> pd.DataFrame:
    """Adds, per stat, columns pred_t5__<col>, pred_std__<col>, pred_lg__<col>.
    NaN prediction == cold start for that baseline (excluded + counted).
    df must be sorted by (season, player_id, game_date, game_id)."""
    out = df.copy()
    grp = out.groupby(["season", "player_id"], sort=False)
    for col in STAT_COL.values():
        shifted = grp[col].shift(1)
        # trailing-5: mean of last min(5, k) strictly-prior games
        out[f"pred_t5__{col}"] = (
            shifted.groupby([out["season"], out["player_id"]])
            .rolling(5, min_periods=1).mean()
            .reset_index(level=[0, 1], drop=True))
        # season-to-date: expanding mean of strictly-prior games
        out[f"pred_std__{col}"] = (
            shifted.groupby([out["season"], out["player_id"]])
            .expanding(min_periods=1).mean()
            .reset_index(level=[0, 1], drop=True))
    # league mean: per season, over strictly earlier calendar dates
    for col in STAT_COL.values():
        out[f"pred_lg__{col}"] = np.nan
    for season, sdf in out.groupby("season", sort=False):
        daily = (sdf.groupby("game_date")[list(STAT_COL.values())]
                 .agg(["sum", "count"]).sort_index())
        for col in STAT_COL.values():
            csum = daily[(col, "sum")].cumsum().shift(1)
            ccnt = daily[(col, "count")].cumsum().shift(1)
            lg = (csum / ccnt)  # NaN on the season's first date
            out.loc[sdf.index, f"pred_lg__{col}"] = (
                sdf["game_date"].map(lg).to_numpy())
    return out


BASELINE_PREFIX = {"trailing_5_mean": "pred_t5",
                   "season_to_date_mean": "pred_std",
                   "league_mean": "pred_lg"}


def baseline_metric_cell(df: pd.DataFrame, stat: str, baseline: str,
                         season) -> tuple[dict, dict]:
    """Returns (metrics_cell, coverage_cell) for one stat x baseline x
    season ('pooled' for all seasons)."""
    col = STAT_COL[stat]
    pcol = f"{BASELINE_PREFIX[baseline]}__{col}"
    sub = df if season == "pooled" else df[df["season"] == season]
    valid = sub[pcol].notna()
    n_cold = int((~valid).sum())
    ev = sub[valid]
    cell_cov = {"n_player_games_in_universe": int(len(sub)),
                "n_evaluated": int(len(ev)),
                "n_cold_start_excluded": n_cold}
    if len(ev) == 0:
        return {"status": "NO_EVALUABLE_ROWS", **cell_cov}, cell_cov
    m = mae_rmse_bias(ev[pcol].to_numpy(float), ev[col].to_numpy(float))
    ci = cluster_bootstrap_ci(np.abs(ev[pcol].to_numpy(float) -
                                     ev[col].to_numpy(float)),
                              ev["game_date"].to_numpy())
    cell = {
        "evidence_class": EVIDENCE_NAIVE,
        "model_version": f"naive/{baseline}/1",
        "target": stat,
        "cutoff": ("pregame-by-construction: strictly prior same-season "
                   "games only (league mean: strictly earlier calendar dates)"),
        "universe": ("regular-season player-games: pinned owned gamelogs "
                     "2022-2024 + refresh_2026 regular-season files for "
                     "2025 (pinned file truncated) and 2026 (no pinned file)"),
        "season": season,
        "n_player_games": int(len(ev)),
        "date_range": [str(ev["game_date"].min()), str(ev["game_date"].max())],
        "mae": m["mae"], "rmse": m["rmse"], "bias": m["bias"],
        "mae_ci95": ci,
        "n_cold_start_excluded": n_cold,
    }
    return cell, cell_cov


# ---------------------------------------------------------------------------
# market threshold metrics
# ---------------------------------------------------------------------------

def devig_p_over(over_price, under_price) -> float:
    """Two-way de-vig via the M11 preregistered method. Returns P(over)."""
    probs, _param, _method, _hash = consensus.no_vig(
        [over_price, under_price], method=consensus.PREREGISTERED_VIG_METHOD)
    return probs[0]


def market_rows(props: pd.DataFrame, outcomes: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Join prop lines to realized outcomes. Returns (joined, join_audit).
    One row per (game_id, bookmaker, player, line-quote). No silent drops:
    every exclusion is counted, unmatched player-games listed."""
    audit = {}
    p = props.copy()
    audit["n_raw_rows"] = int(len(p))
    p = p[p["market_key"].isin(MARKET_TO_STAT)]
    audit["n_rows_supported_market_families"] = int(len(p))
    before = len(p)
    p = p.drop_duplicates()
    audit["n_exact_duplicate_rows_dropped"] = int(before - len(p))
    two_sided = p["over_price"].notna() & p["under_price"].notna()
    audit["n_rows_missing_a_side_excluded"] = int((~two_sided).sum())
    p = p[two_sided]

    p["stat"] = p["market_key"].map(MARKET_TO_STAT)
    p["game_id"] = p["game_id"].astype(str)
    p["norm_name"] = p["player_name"].map(normalize_name)

    o = outcomes.copy()
    o["norm_name"] = o["player_name"].map(normalize_name)
    o = o[["game_id", "norm_name", "season", "game_date"] + list(STAT_COL.values())]

    j = p.merge(o, on=["game_id", "norm_name"], how="left", indicator=True)
    matched = j["_merge"] == "both"
    audit["n_quote_rows_matched"] = int(matched.sum())
    audit["n_quote_rows_unmatched"] = int((~matched).sum())
    unmatched_keys = (j.loc[~matched, ["game_id", "player_name"]]
                      .drop_duplicates().sort_values(["game_id", "player_name"]))
    games_in_universe = set(o["game_id"])
    def _reason(game_id: str) -> str:
        if game_id in games_in_universe:
            return "GAME_IN_UNIVERSE_PLAYER_ROW_ABSENT (DNP or name variant)"
        if len(game_id) >= 4 and game_id[:4] == "1042":
            return "PLAYOFF_GAME_OUTSIDE_REGULAR_SEASON_UNIVERSE"
        return "GAME_NOT_IN_OUTCOME_UNIVERSE"
    unmatched_keys = unmatched_keys.assign(
        reason=[_reason(g) for g in unmatched_keys["game_id"]])
    audit["n_unmatched_player_games"] = int(len(unmatched_keys))
    audit["unmatched_player_game_reasons"] = (
        unmatched_keys["reason"].value_counts().to_dict())
    audit["unmatched_player_games"] = [
        {"game_id": r.game_id, "player_name": r.player_name, "reason": r.reason}
        for r in unmatched_keys.itertuples()]
    matched_pg = j.loc[matched, ["game_id", "norm_name"]].drop_duplicates()
    audit["n_matched_player_games"] = int(len(matched_pg))
    j = j[matched].drop(columns=["_merge"])

    j["realized"] = [row[STAT_COL[s]] for s, row in
                     zip(j["stat"], j.to_dict("records"))]
    j["p_over"] = [devig_p_over(ov, un) for ov, un in
                   zip(j["over_price"], j["under_price"])]
    j["is_push"] = j["realized"] == j["line"]
    j["over_hit"] = (j["realized"] > j["line"]).astype(float)
    j["pick_correct"] = np.where(
        j["p_over"] >= 0.5, j["over_hit"], 1.0 - j["over_hit"])
    audit["n_push_rows_excluded_from_ou_and_brier"] = int(j["is_push"].sum())
    return j, audit


def market_metric_cell(j: pd.DataFrame, stat: str, season, book=None) -> dict:
    sub = j[j["stat"] == stat]
    if season != "pooled":
        sub = sub[sub["season"] == season]
    if book is not None:
        sub = sub[sub["bookmaker_key"] == book]
    if len(sub) == 0:
        return {"status": "NO_ROWS", "season": season, "n_quote_rows": 0}
    np_sub = sub[~sub["is_push"]]
    tm_err = np.abs(sub["line"].to_numpy(float) - sub["realized"].to_numpy(float))
    cell = {
        "evidence_class": EVIDENCE_MARKET,
        "model_version": "market_lines/T1_vendor_asserted_snapshot/1",
        "target": stat,
        "cutoff": ("vendor-asserted pre-game snapshot (one per game in this "
                   "archive); T1 -- never a witnessed T0 capture"),
        "universe": ("prop quote rows joined to regular-season player-game "
                     "outcomes" + (f"; bookmaker={book}" if book else
                                   "; all books pooled (per-quote rows)")),
        "season": season,
        "bookmaker": book or "ALL_BOOKS_POOLED",
        "n_quote_rows": int(len(sub)),
        "n_player_games": int(sub[["game_id", "norm_name"]]
                              .drop_duplicates().shape[0]),
        "date_range": [str(sub["game_date"].min()), str(sub["game_date"].max())],
        "threshold_mae": float(tm_err.mean()),
        "threshold_mae_note": ("THRESHOLD MAE (line vs realized stat) per "
                               "D036 point 5 -- NOT a projection MAE"),
        "threshold_mae_ci95": cluster_bootstrap_ci(
            tm_err, sub["game_date"].to_numpy()),
        "threshold_bias_line_minus_realized": float(
            (sub["line"] - sub["realized"]).mean()),
        "threshold_rmse": float(np.sqrt(((sub["line"] - sub["realized"]) ** 2).mean())),
        "n_push_excluded": int(sub["is_push"].sum()),
    }
    if len(np_sub):
        brier = (np_sub["p_over"] - np_sub["over_hit"]) ** 2
        cell["devig_ou_accuracy"] = float(np_sub["pick_correct"].mean())
        cell["devig_ou_accuracy_ci95"] = cluster_bootstrap_ci(
            np_sub["pick_correct"].to_numpy(float),
            np_sub["game_date"].to_numpy())
        cell["devig_brier"] = float(brier.mean())
        cell["devig_brier_ci95"] = cluster_bootstrap_ci(
            brier.to_numpy(float), np_sub["game_date"].to_numpy())
        cell["vig_method"] = consensus.PREREGISTERED_VIG_METHOD
        cell["vig_preregistration_hash"] = consensus.PREREGISTRATION_HASH
    return cell


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ts = datetime.now(timezone.utc).isoformat()
    df, gl_audit = load_gamelogs()
    df = add_baseline_predictions(df)

    seasons = sorted(df["season"].unique().tolist())
    metrics = {"schema": "market_program/SCOREBOARD/granular/player_granular_metrics/1",
               "generated_utc": ts,
               "decision_authority": ["D036_SCOREBOARD_MEASUREMENT_SEMANTICS",
                                      "D037_GRANULAR_PLAYER_SCOREBOARD"],
               "contract_sha256": consensus.CONTRACT_SHA256,
               "commit_sha": ("UNAVAILABLE: worktree exposes no git and the "
                              "task forbids git invocation; source file "
                              "hashes below are the provenance anchor"),
               "seed": SEED, "n_boot": N_BOOT,
               "producer": "compute_player_granular.py",
               "producer_sha256": sha256_file(Path(__file__)),
               "naive_baselines": {}, "market_threshold": {},
               "our_model": {
                   "lifecycle_state": "NOT-YET-EVALUATED-PENDING-AUDIT",
                   "note": ("D037: legacy player-model numbers may only "
                            "surface after the provenance probe is receipted "
                            "by a verification node; see PROBE_LEGACY.md. "
                            "No legacy number appears in this file.")},
               }
    coverage = {"schema": "market_program/SCOREBOARD/granular/player_granular_coverage/1",
                "generated_utc": ts, "seed": SEED,
                "gamelog_assembly": gl_audit,
                "seasons": seasons,
                "n_player_games_total": int(len(df)),
                "unique_game_dates": int(df["game_date"].nunique()),
                "unique_games": int(df["game_id"].nunique()),
                "cold_start": {}, "market_join_audit": None}

    for stat in STATS:
        metrics["naive_baselines"][stat] = {}
        coverage["cold_start"][stat] = {}
        for baseline in BASELINES:
            metrics["naive_baselines"][stat][baseline] = {}
            cov_b = {}
            for season in seasons + ["pooled"]:
                cell, cov = baseline_metric_cell(df, stat, baseline, season)
                metrics["naive_baselines"][stat][baseline][str(season)] = cell
                cov_b[str(season)] = cov
            coverage["cold_start"][stat][baseline] = cov_b

    # ------------------------------------------------------------------ market
    props = pd.read_csv(PROPS_CSV)
    props_sha = sha256_file(PROPS_CSV)
    joined, join_audit = market_rows(props, df)
    join_audit["source"] = {"path": str(PROPS_CSV), "sha256": props_sha,
                            "access": "read-only (LIVE worktree), D027 bounded use, T1"}
    join_audit["market_families_present"] = sorted(
        props["market_key"].unique().tolist())
    join_audit["market_families_supported"] = sorted(MARKET_TO_STAT)
    coverage["market_join_audit"] = join_audit

    mkt_seasons = sorted(joined["season"].dropna().unique().astype(int).tolist())
    for stat in sorted(set(MARKET_TO_STAT.values())):
        metrics["market_threshold"][stat] = {"pooled_books": {}, "per_book": {}}
        for season in mkt_seasons + ["pooled"]:
            metrics["market_threshold"][stat]["pooled_books"][str(season)] = \
                market_metric_cell(joined, stat, season)
        for book in sorted(joined["bookmaker_key"].unique()):
            metrics["market_threshold"][stat]["per_book"][book] = \
                market_metric_cell(joined, stat, "pooled", book=book)
        metrics["market_threshold"][stat]["per_book_note"] = (
            "FIXED bookmaker identities (D036 point 4); per-book universes "
            "differ where books did not quote the same player-games -- no "
            "best/worst ranking is asserted here without a common-sample cut")

    with open(HERE / "player_granular_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=1)
    with open(HERE / "player_granular_coverage.json", "w", encoding="utf-8") as f:
        json.dump(coverage, f, indent=1)

    print(f"player-games: {len(df)}, seasons {seasons}")
    for stat in STATS:
        c = metrics["naive_baselines"][stat]["trailing_5_mean"]["pooled"]
        print(f"  pooled trailing-5 MAE {stat:12s} = {c['mae']:.4f} "
              f"[{c['mae_ci95']['lo']:.4f}, {c['mae_ci95']['hi']:.4f}] "
              f"N={c['n_player_games']}")
    pc = metrics["market_threshold"]["points"]["pooled_books"]["pooled"]
    print(f"  market points: threshold_mae={pc['threshold_mae']:.4f} "
          f"OU acc={pc['devig_ou_accuracy']:.4f} brier={pc['devig_brier']:.4f} "
          f"N_quotes={pc['n_quote_rows']}")


if __name__ == "__main__":
    main()
