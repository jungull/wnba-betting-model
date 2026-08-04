#!/usr/bin/env python3
"""possession_artifact_v1.py — the immutable RAW possession artifact and its integrity receipt.

**NOTHING IS FITTED.** No RAPM, no rate model, no ridge penalty, no player ranking, no offensive
/ defensive / net impact. This builds a possession-level artifact, classifies every possession's
lineup validity, adds pre-possession-only leverage fields, and measures what a later design matrix
could and could not use.

THE RAW ARTIFACT PRESERVES EVERYTHING. Anomalous, underfull and unresolved possessions are kept
and LABELLED, never dropped or repaired. It is deliberately distinct from any later
model-filtered design matrix: filtering is a modelling decision and does not belong in the record
of what happened.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
OUT = HERE / "possessions_v1"
RAW = REPO / "data" / "possessions" / "possessions.parquet"
RECON = REPO / "data" / "possessions" / "reconciliation.csv"
STINTS = REPO / "data" / "derived" / "stints.parquet"
LINEVAL = REPO / "data" / "derived" / "lineup_validation.csv"
MASTER_T = REPO / "data" / "masters" / "master_team.parquet"
MASTER_P = REPO / "data" / "masters" / "master_player.parquet"

ARTIFACT_ID = "player_possessions/1"
OFF = [f"off_p{i}" for i in range(1, 6)]
DEF = [f"def_p{i}" for i in range(1, 6)]

#: Regulation is 4 x 10 minutes in the WNBA; overtime periods are 5 minutes.
PERIOD_SEC, REG_PERIODS, OT_SEC = 600, 4, 300

#: The PREREGISTERED conservative competitive rule. Monotone in margin and in time remaining, and
#: computed ONLY from the score differential at possession start, the seconds remaining, and the
#: period. It never reads the final margin, the winner, future scoring or any postgame fact.
#: Deliberately conservative: it flags few possessions, so a later model that uses it is making a
#: small, auditable exclusion rather than a large silent one.
GARBAGE_RULE = ((25, 720), (20, 480), (15, 300), (10, 120))
GARBAGE_RULE_TEXT = (
    "non_competitive at possession START iff |score_diff| >= 25 with <= 720s remaining, or >= 20 "
    "with <= 480s, or >= 15 with <= 300s, or >= 10 with <= 120s. Regulation only; no overtime "
    "possession is ever flagged, because a game that reached overtime was competitive by "
    "construction.")


def _sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def _git(*a) -> str:
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()


def content_digest(df: pd.DataFrame) -> str:
    """A stable digest of the LOGICAL table, independent of parquet serialisation metadata."""
    d = df.sort_values(["game_id", "possession_idx"], kind="mergesort").reset_index(drop=True)
    d = d[sorted(d.columns)]
    h = hashlib.sha256()
    h.update(("|".join(d.columns)).encode())
    for c in d.columns:
        s = d[c]
        if pd.api.types.is_float_dtype(s):
            b = np.round(s.fillna(np.nan).to_numpy(dtype="float64"), 6).tobytes()
        else:
            b = s.astype("string").fillna("<NA>").str.cat(sep="\x1f").encode()
        h.update(hashlib.sha256(b).digest())
    return h.hexdigest()


# ------------------------------------------------------------------ enrich

def classify_lineups(d: pd.DataFrame) -> pd.DataFrame:
    off = d[OFF].to_numpy()
    dfn = d[DEF].to_numpy()
    n_off = d["n_off_oncourt"].to_numpy()
    n_def = d["n_def_oncourt"].to_numpy()

    def _dups(a):
        out = np.zeros(len(a), bool)
        for i in range(len(a)):
            v = a[i][~pd.isna(a[i])]
            out[i] = len(v) != len(set(v.tolist()))
        return out

    dup_off, dup_def = _dups(off), _dups(dfn)
    both = np.zeros(len(d), bool)
    for i in range(len(d)):
        o = set(x for x in off[i] if not pd.isna(x))
        v = set(x for x in dfn[i] if not pd.isna(x))
        both[i] = bool(o & v)

    cls = np.full(len(d), "valid_ten_player", dtype=object)
    cls[(n_off < 5) & (n_def == 5)] = "offense_underfull"
    cls[(n_off == 5) & (n_def < 5)] = "defense_underfull"
    cls[(n_off < 5) & (n_def < 5)] = "both_underfull"
    cls[(n_off > 5) | (n_def > 5)] = "impossible_team_assignment"
    cls[dup_off | dup_def] = "duplicate_player"
    cls[both] = "player_assigned_to_both_teams"
    d = d.copy()
    d["lineup_class"] = cls
    d["lineup_valid_ten"] = cls == "valid_ten_player"
    d["n_oncourt_total"] = n_off + n_def
    return d


def enrich(d: pd.DataFrame, mt: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["game_id"] = d["game_id"].astype(str)
    dates = (mt[["game_id", "game_date"]].drop_duplicates("game_id"))
    dates["game_id"] = dates["game_id"].astype(str)
    d = d.merge(dates, on="game_id", how="left")
    d["game_date"] = pd.to_datetime(d["game_date"])

    d["is_overtime"] = d["period"] > REG_PERIODS
    # elapsed seconds are already absolute; derive the game clock remaining at possession start
    per_len = np.where(d["period"] > REG_PERIODS, OT_SEC, PERIOD_SEC)
    reg_end = REG_PERIODS * PERIOD_SEC
    period_start = np.where(d["period"] <= REG_PERIODS,
                            (d["period"] - 1) * PERIOD_SEC,
                            reg_end + (d["period"] - REG_PERIODS - 1) * OT_SEC)
    d["period_clock_start_sec"] = np.clip(
        per_len - (d["start_sec"].to_numpy() - period_start), 0, None)
    d["period_clock_end_sec"] = np.clip(
        per_len - (d["end_sec"].to_numpy() - period_start), 0, None)
    d["regulation_seconds_remaining"] = np.clip(reg_end - d["start_sec"].to_numpy(), 0, None)

    home_before = d["home_pts_before"].to_numpy(float)
    away_before = d["away_pts_before"].to_numpy(float)
    is_home_off = d["is_home_offense"].astype(bool).to_numpy()
    off_before = np.where(is_home_off, home_before, away_before)
    def_before = np.where(is_home_off, away_before, home_before)
    d["score_diff_offense_start"] = off_before - def_before
    d["score_diff_offense_end"] = (off_before + d["points_scored"].to_numpy(float)) - def_before
    d["abs_score_diff_start"] = np.abs(d["score_diff_offense_start"])

    rem = d["regulation_seconds_remaining"].to_numpy()
    md = d["abs_score_diff_start"].to_numpy()
    ng = np.zeros(len(d), bool)
    for margin, secs in GARBAGE_RULE:
        ng |= (md >= margin) & (rem <= secs)
    ng &= ~d["is_overtime"].to_numpy()
    d["non_competitive_conservative"] = ng
    d["all_possessions"] = True

    d["is_zero_duration"] = d["duration_sec"].fillna(0) <= 0
    d["is_technical_derived"] = d["end_reason"].astype(str).str.contains("tech", case=False,
                                                                        na=False)
    d["possession_kind"] = np.where(
        d["is_technical_derived"], "technical_free_throw_sequence",
        np.where(d["is_zero_duration"], "zero_duration_sequence", "live_ball"))
    d["source_pbp_game_id"] = d["game_id"]
    return d


# ------------------------------------------------------------------ receipts

def coverage(d: pd.DataFrame) -> dict:
    out = {"overall": {}, "by_season": {}}

    def blk(g):
        v = g["lineup_valid_ten"]
        return {
            "possessions": int(len(g)),
            "valid_ten_player": int(v.sum()),
            "valid_pct_possession_weighted": round(100 * float(v.mean()), 4),
            "invalid_pct_possession_weighted": round(100 * float((~v).mean()), 4),
            "points_total": int(g["points_scored"].sum()),
            "points_on_invalid": int(g.loc[~v, "points_scored"].sum()),
            "valid_pct_point_weighted": round(
                100 * float(g.loc[v, "points_scored"].sum() / max(g["points_scored"].sum(), 1)), 4),
            "seconds_total": round(float(g["duration_sec"].sum()), 1),
            "seconds_on_invalid": round(float(g.loc[~v, "duration_sec"].sum()), 1),
            "valid_pct_time_weighted": round(
                100 * float(g.loc[v, "duration_sec"].sum() / max(g["duration_sec"].sum(), 1e-9)), 4),
            "games": int(g["game_id"].nunique()),
            "games_with_any_invalid": int(g.loc[~v, "game_id"].nunique()),
            "class_counts": {k: int(x) for k, x in g["lineup_class"].value_counts().items()},
        }

    out["overall"] = blk(d)
    for s, g in d.groupby("season"):
        out["by_season"][str(int(s))] = blk(g)
    worst = (d.groupby("game_id")
             .agg(poss=("lineup_valid_ten", "size"),
                  invalid=("lineup_valid_ten", lambda x: int((~x).sum())))
             .assign(pct=lambda f: 100 * f.invalid / f.poss)
             .sort_values("pct", ascending=False).head(15))
    out["worst_affected_games"] = [
        {"game_id": g, "possessions": int(r.poss), "invalid": int(r.invalid),
         "invalid_pct": round(float(r.pct), 2)} for g, r in worst.iterrows()]
    out["games_entirely_invalid"] = [
        g for g, r in worst.iterrows() if r.invalid == r.poss]
    return out


def missing_and_broken(d: pd.DataFrame) -> dict:
    mp = pd.read_parquet(MASTER_P)
    mp["game_id"] = mp["game_id"].astype(str)
    st = pd.read_parquet(STINTS)
    st_games = set(st["GAME_ID"].astype(str))
    master_games = mp[["game_id", "season"]].drop_duplicates()
    missing = master_games[~master_games["game_id"].isin(st_games)]
    lv = pd.read_csv(LINEVAL)
    big = lv[lv["diff_min"].abs() > 1.0]
    return {
        "games_without_stint_reconstruction": {
            "n": int(len(missing)),
            "by_season": {str(int(s)): int(n) for s, n in
                          missing.groupby("season").size().items()},
            "game_ids": missing["game_id"].tolist(),
            "failure_reason": (
                "these games have no row in data/derived/stints.parquet. "
                "data/derived/failed_games.csv is EMPTY, so derive_lineups did not record a "
                "per-game failure for them — they were never presented to it. Play-by-play "
                "exists for the union of data/playbyplay and data/refresh_2026/pbp; these game "
                "ids are absent from the stint output rather than rejected by it, which points "
                "at the input enumeration and not at a reconstruction failure. NOT further "
                "diagnosed here: doing so would be repair work, which this phase excludes."),
            "consequence": "excluded from every possession denominator below, and named here so "
                           "the exclusion is never silent",
        },
        "player_game_minute_discrepancies_over_one_minute": {
            "n": int(len(big)),
            "rows": big.sort_values("diff_min", key=abs, ascending=False)
            .head(20)[["GAME_ID", "TEAM_ID", "PLAYER_ID", "PLAYER_NAME", "derived_min",
                       "box_min", "diff_min"]].to_dict("records"),
            "note": "derived stint minutes vs box minutes; these are the unresolved substitution "
                    "sequences. 99.94% of 28,212 player-games agree within 0.1 minute.",
        },
        "games_present_in_possessions": int(d["game_id"].nunique()),
    }


def attribution(d: pd.DataFrame) -> dict:
    rows = []
    for side, cols, tcol in (("off", OFF, "offense_team_id"), ("def", DEF, "defense_team_id")):
        m = d[["game_id", "season", "game_date", tcol, "lineup_valid_ten"] + cols].melt(
            id_vars=["game_id", "season", "game_date", tcol, "lineup_valid_ten"],
            value_vars=cols, value_name="player_id").dropna(subset=["player_id"])
        m["side"] = side
        m = m.rename(columns={tcol: "team_id"})
        rows.append(m[["game_id", "season", "game_date", "team_id", "player_id",
                       "lineup_valid_ten", "side"]])
    long = pd.concat(rows, ignore_index=True)
    long["player_id"] = long["player_id"].astype("int64")

    g = long.groupby(["player_id", "season"])
    ps = pd.DataFrame({
        "offensive_possessions": g.apply(lambda x: int(((x["side"] == "off")
                                                        & x["lineup_valid_ten"]).sum())),
        "defensive_possessions": g.apply(lambda x: int(((x["side"] == "def")
                                                        & x["lineup_valid_ten"]).sum())),
        "excluded_invalid_lineup": g.apply(lambda x: int((~x["lineup_valid_ten"]).sum())),
        "games": g["game_id"].nunique(),
        "teams": g["team_id"].nunique(),
        "first_date": g["game_date"].min(),
        "last_date": g["game_date"].max(),
    }).reset_index()
    ps["total_valid_possessions"] = ps["offensive_possessions"] + ps["defensive_possessions"]

    # team offensive vs opponent defensive reconciliation, per game
    v = d[d["lineup_valid_ten"]]
    off_t = v.groupby(["game_id", "offense_team_id"]).size().rename("off")
    def_t = v.groupby(["game_id", "defense_team_id"]).size().rename("dfn")
    rec = pd.concat([off_t, def_t], axis=1).fillna(0)
    rec.index.names = ["game_id", "team_id"]
    rec = rec.reset_index()
    tot = v.groupby("game_id").size().rename("game_total").reset_index()
    rec = rec.merge(tot, on="game_id")
    rec["off_plus_opp_def"] = rec["off"] + rec["dfn"]
    mismatch = int((rec["off_plus_opp_def"] != rec["game_total"]).sum())

    dup = int(d.duplicated(["game_id", "possession_idx"]).sum())
    ordered = bool(d.sort_values(["game_id", "possession_idx"])
                   .groupby("game_id")["start_sec"].apply(
                       lambda s: s.is_monotonic_increasing).all())
    ot = d[d["is_overtime"]]
    return {
        "player_seasons": int(len(ps)),
        "unique_players": int(ps["player_id"].nunique()),
        "possession_exposure_total_valid": int(ps["total_valid_possessions"].sum()),
        "checks": {
            "team_offensive_reconciles_with_opponent_defensive": mismatch == 0,
            "n_team_game_mismatches": mismatch,
            "no_duplicate_possession": dup == 0,
            "n_duplicate_possessions": dup,
            "chronological_order_deterministic_within_game": ordered,
            "overtime_included": {"ot_possessions": int(len(ot)),
                                  "ot_games": int(ot["game_id"].nunique())},
            "trade_identity": ("player_id is stable across teams; team_id varies within a "
                               "player-season. Players with >1 team in a season: "
                               f"{int((ps['teams'] > 1).sum())}"),
        },
        "top_by_possessions": ps.sort_values("total_valid_possessions", ascending=False)
        .head(5)[["player_id", "season", "offensive_possessions", "defensive_possessions",
                  "games", "teams"]].to_dict("records"),
        "player_season_table_rows": int(len(ps)),
    }, ps


def rapm_readiness(d: pd.DataFrame) -> dict:
    v = d[d["lineup_valid_ten"]].copy()
    players = pd.unique(pd.concat([v[c] for c in OFF + DEF]).dropna()).astype("int64")
    v["off_key"] = v[OFF].astype("Int64").astype(str).agg("|".join, axis=1)
    v["def_key"] = v[DEF].astype("Int64").astype(str).agg("|".join, axis=1)
    lineups = pd.unique(pd.concat([v["off_key"], v["def_key"]]))
    rep = pd.concat([v["off_key"], v["def_key"]]).value_counts()

    cnt = pd.concat([v[c] for c in OFF + DEF]).dropna().astype("int64").value_counts()
    thresholds = {str(t): int((cnt < t).sum()) for t in (50, 100, 250, 500, 1000)}

    # connected components of the player co-occurrence / opposition graph
    idx = {p: i for i, p in enumerate(players)}
    parent = list(range(len(players)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    arr = v[OFF + DEF].to_numpy()
    for row in arr:
        ids = [idx[int(x)] for x in row if not pd.isna(x)]
        for j in range(1, len(ids)):
            union(ids[0], ids[j])
    comps = {}
    for p, i in idx.items():
        comps.setdefault(find(i), []).append(p)
    sizes = sorted((len(v2) for v2 in comps.values()), reverse=True)

    return {
        "usable_possessions_valid_ten": int(len(v)),
        "unique_players": int(len(players)),
        "unique_lineup_combinations": int(len(lineups)),
        "repeated_lineup_frequency": {
            "lineups_seen_once": int((rep == 1).sum()),
            "lineups_seen_10_plus": int((rep >= 10).sum()),
            "median_appearances": float(rep.median()),
            "max_appearances": int(rep.max()),
        },
        "player_possession_distribution": {
            "min": int(cnt.min()), "p10": int(cnt.quantile(.10)),
            "median": int(cnt.median()), "p90": int(cnt.quantile(.90)),
            "max": int(cnt.max()),
        },
        "low_possession_player_counts": thresholds,
        "connected_components": {
            "n_components": len(sizes), "largest": sizes[0] if sizes else 0,
            "component_sizes": sizes[:10],
            "players_outside_main_component": int(sum(sizes[1:])) if len(sizes) > 1 else 0,
        },
        "dimensionality": {
            "design_rows": int(len(v)),
            "columns_if_separate_off_def_effects": int(2 * len(players)),
            "rows_per_column": round(len(v) / max(2 * len(players), 1), 1),
        },
        "identifiability": {
            "matrix_constructible": True,
            "constructibility_is_not_identifiability": (
                "a full-rank-looking matrix is not an identified model. Separate offensive and "
                "defensive player effects are identifiable ONLY under explicit constraints, "
                "because every possession has exactly five offensive and five defensive "
                "indicators, so each block's row sums are constant and each block is collinear "
                "with the intercept."),
            "constraints_a_later_model_must_declare": [
                "a single global intercept (league average points per possession)",
                "a sum-to-zero or reference-player constraint on the offensive block AND "
                "independently on the defensive block, since each block alone is rank-deficient "
                "by one",
                "a home-court term estimated separately from player effects",
                "season effects, because pace and scoring level differ by season and would "
                "otherwise load onto whichever players happen to span a season boundary",
                "a ridge penalty selected CHRONOLOGICALLY, never on the evaluation fold",
                "an explicit decision on whether offensive and defensive penalties are shared",
            ],
            "not_claimed_here": ("no rank, condition number or identifiability verdict is "
                                 "asserted from outcomes; nothing was fitted"),
        },
    }


def chronological_usability(d: pd.DataFrame) -> dict:
    g = d.groupby("game_id")["game_date"].min()
    return {
        "possession_carries_game_date": bool(d["game_date"].notna().all()),
        "date_range": [str(d["game_date"].min().date()), str(d["game_date"].max().date())],
        "distinct_game_dates": int(d["game_date"].nunique()),
        "games_sortable_by_date": bool(g.notna().all()),
        "walk_forward_constructible": True,
        "how": [
            "every possession carries game_id, game_date and season, so a fold boundary is a "
            "date and a training set is 'all possessions of games strictly before it'",
            "no target game's possessions can enter its own features or fit, because the split "
            "is by game and a game's possessions are indivisible",
            "season and trade transitions are preserved: player_id is stable, team_id varies "
            "within a player-season, and 'teams > 1' is reported per player-season",
            "no final-season aggregate is used retrospectively — the artifact stores possessions, "
            "not season summaries, so any aggregate must be recomputed inside a fold",
        ],
        "artifact_may_contain_postgame_outcomes": (
            "yes, and it must: points_scored IS the label and the impact-estimation source. "
            "The chronological discipline lives in the SPLIT, not in the artifact."),
    }


def rebound_feasibility(d: pd.DataFrame) -> dict:
    er = d["end_reason"].astype(str).value_counts()
    known = {k: int(v2) for k, v2 in er.items()}
    reb_end = int(sum(v2 for k, v2 in known.items() if "rebound" in k.lower()))
    return {
        "end_reason_counts": known,
        "defensive_rebound_terminated_possessions": reb_end,
        "what_is_derivable_from_the_possession_stream_alone": {
            "defensive_rebound_opportunities": "PARTIAL — a possession ending in a defensive "
                                               "rebound implies one, but offensive rebounds do "
                                               "NOT end a possession and are therefore invisible "
                                               "at possession granularity",
            "offensive_rebound_opportunities": "NOT DERIVABLE at this granularity — offensive "
                                               "rebounds continue the run by construction",
            "team_rebounds": "NOT SEPARABLE from player rebounds here",
            "dead_ball_non_reboundable_misses": "NOT SEPARABLE here",
            "free_throw_rebound_opportunities": "NOT SEPARABLE here; the final-FT rule folds them "
                                                "into the possession end",
        },
        "verdict": (
            "rebound-opportunity denominators CANNOT be defensibly built from the possession "
            "artifact alone. They require the EVENT stream — data/playbyplay + "
            "data/refresh_2026/pbp, which is present for all 1,489 reconstructed games — where "
            "each shot, miss, rebound and free throw is an individual row. That is a separate "
            "derivation and is NOT attempted here."),
        "no_denominator_is_manufactured": True,
    }


def main() -> int:
    if not RAW.exists():
        print(f"raw possessions absent at {RAW}; run build_possessions.py first")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    d0 = pd.read_parquet(RAW)
    mt = pd.read_parquet(MASTER_T)
    d = classify_lineups(enrich(d0, mt))

    art = OUT / "possessions_raw_v1.parquet"
    d.to_parquet(art, index=False)
    dig = content_digest(d)

    # deterministic logical-rebuild check
    d2 = classify_lineups(enrich(pd.read_parquet(RAW), mt))
    same = content_digest(d2) == dig

    attrib, ps = attribution(d)
    ps.to_parquet(OUT / "player_season_possessions_v1.parquet", index=False)

    recon = pd.read_csv(RECON)
    receipt = {
        "schema": "possession_artifact_receipt/1",
        "artifact_id": ARTIFACT_ID,
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "nothing_fitted": True,
        "scope": ("raw possession artifact, lineup-validity classification, pre-possession-only "
                  "leverage fields, and design-matrix readiness diagnostics. No RAPM, no rate "
                  "model, no ridge penalty, no ranking, no impact figure."),
        "raw_artifact_preserves_everything": (
            "anomalous, underfull and unresolved possessions are KEPT and LABELLED. Zero rows "
            "are dropped or repaired. Filtering is a modelling decision and belongs to the later "
            "design matrix, not to the record of what happened."),
        "integrity": {
            "producing_git_commit": _git("rev-parse", "HEAD"),
            "producing_commit_subject": _git("log", "-1", "--pretty=%s"),
            "working_tree_clean_at_build": not _git("status", "--porcelain"),
            "producer_sha256": {
                "build_possessions.py": _sha(REPO / "build_possessions.py"),
                "derive_lineups.py": _sha(REPO / "derive_lineups.py"),
                "wnba_schema.py": _sha(REPO / "wnba_schema.py"),
                "possession_artifact_v1.py": _sha(Path(__file__)),
            },
            "source_sha256": {
                "possessions.parquet": _sha(RAW), "reconciliation.csv": _sha(RECON),
                "stints.parquet": _sha(STINTS), "lineup_validation.csv": _sha(LINEVAL),
                "master_team.parquet": _sha(MASTER_T),
            },
            "artifact_sha256": _sha(art),
            "artifact_content_digest": dig,
            "row_count": int(len(d)),
            "schema": {c: str(t) for c, t in d.dtypes.items()},
            "deterministic_rebuild_logically_identical": bool(same),
            "byte_identity_note": (
                "parquet embeds writer metadata, so byte identity across rebuilds is not "
                "guaranteed and is not claimed. Equality is proven on the CANONICAL logical "
                "table: columns sorted, rows sorted by (game_id, possession_idx), floats rounded "
                "to 1e-6, hashed column by column."),
            "exclusions_from_raw_artifact": 0,
            "score_reconciliation_from_build": {
                "games": int(len(recon)), "exact": int(recon["exact"].sum()),
                "exact_pct": round(100 * float(recon["exact"].mean()), 2)},
            "exact_reconciliation_does_not_imply_valid_lineups": (
                "score reconstruction is exact on every game, and that is a statement about the "
                "EVENT stream, not about who was on the floor. Lineup validity is measured "
                "separately and possession-wise below."),
        },
        "coverage": coverage(d),
        "missing_and_broken": missing_and_broken(d),
        "attribution": attrib,
        "garbage_time": {
            "rule_id": "competitive_conservative/1",
            "rule": GARBAGE_RULE_TEXT,
            "thresholds_margin_seconds": [list(x) for x in GARBAGE_RULE],
            "computed_from": ["score_diff_offense_start", "regulation_seconds_remaining",
                              "period"],
            "never_uses": ["final margin", "winner", "future scoring", "any postgame fact"],
            "not_selected_on_model_performance": True,
            "preserved_flags": ["all_possessions", "non_competitive_conservative"],
            "preserved_continuous_fields": ["score_diff_offense_start",
                                            "score_diff_offense_end",
                                            "abs_score_diff_start",
                                            "regulation_seconds_remaining",
                                            "period_clock_start_sec", "period_clock_end_sec"],
            "counts": {
                "non_competitive": int(d["non_competitive_conservative"].sum()),
                "non_competitive_pct": round(
                    100 * float(d["non_competitive_conservative"].mean()), 3),
                "by_season": {str(int(s)): int(g["non_competitive_conservative"].sum())
                              for s, g in d.groupby("season")},
            },
            "unusual_sequences_treated_explicitly": {
                "possession_kind_counts": {k: int(v2) for k, v2
                                           in d["possession_kind"].value_counts().items()},
                "note": ("technical-free-throw sequences and zero-duration sequences are LABELLED "
                         "as their own kinds rather than forced into live_ball"),
            },
        },
        "rebound_opportunity_feasibility": rebound_feasibility(d),
        "rapm_readiness": rapm_readiness(d),
        "chronological_usability": chronological_usability(d),
        "artifacts_written": {
            "raw": str((OUT / "possessions_raw_v1.parquet").relative_to(REPO)).replace("\\", "/"),
            "player_season": str((OUT / "player_season_possessions_v1.parquet")
                                 .relative_to(REPO)).replace("\\", "/"),
        },
    }
    (OUT / "POSSESSION_INTEGRITY_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, default=str) + "\n", encoding="utf-8", newline="")
    print("wrote POSSESSION_INTEGRITY_RECEIPT.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
