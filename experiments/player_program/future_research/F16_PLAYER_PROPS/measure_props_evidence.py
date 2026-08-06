"""F16_PLAYER_PROPS -- read-only inventory of the player-prop evidence base.

Run from the repository root:

    python experiments/player_program/future_research/F16_PLAYER_PROPS/measure_props_evidence.py

Writes MEASUREMENTS.json next to this file. Reads nothing under stage2b/SEALED_RESULTS.
Fits nothing, scores nothing, joins no settlement.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent / "MEASUREMENTS.json"

PROPS_LIVE = ROOT / "data" / "props_capture" / "master_props.csv"
PROPS_HIST = ROOT / "data" / "props_capture" / "historical" / "master_props_historical.csv"
BACKFILL = ROOT / "data" / "props_capture" / "historical" / "backfill_done.csv"
UNIVERSE = (ROOT / "experiments" / "player_program" / "turnover_targets_v1"
            / "team_turnover_reconciliation_v1.parquet")
PLAYER_TARGETS = (ROOT / "experiments" / "player_program" / "turnover_targets_v1"
                  / "player_turnover_targets_v1.parquet")
MASTER_PLAYER = ROOT / "data" / "masters" / "master_player.parquet"


def norm(s: object) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", "", s.lower()).strip()


def main() -> None:
    m: dict[str, object] = {}

    # ---- M1  the prospective (witnessed) props stream ------------------------------------
    live = pd.read_csv(PROPS_LIVE)
    m["M1_prospective_stream"] = {
        "path": "data/props_capture/master_props.csv",
        "rows": int(len(live)),
        "distinct_api_events": int(live["api_event_id"].nunique()),
        "distinct_snapshots": sorted(live["snapshot_utc"].astype(str).unique().tolist()),
        "markets": sorted(live["market_key"].unique().tolist()),
        "rows_by_market": {k: int(v) for k, v in live["market_key"].value_counts().items()},
        "distinct_player_name_strings": int(live["player_name"].nunique()),
        "event_player_pairs": int(live[["api_event_id", "player_name"]].drop_duplicates().shape[0]),
        "event_player_market_cells": int(
            live[["api_event_id", "player_name", "market_key"]].drop_duplicates().shape[0]),
        "commence_min": str(live["commence_time"].min()),
        "commence_max": str(live["commence_time"].max()),
        "has_player_id_column": bool("player_id" in live.columns),
        "has_settlement_or_result_column": bool(
            any(c.lower() in {"result", "settled", "graded", "outcome", "actual"}
                for c in live.columns)),
        "columns": list(live.columns),
    }

    # ---- M2  the retrospective props archive ---------------------------------------------
    hist = pd.read_csv(PROPS_HIST)
    back = pd.read_csv(BACKFILL)
    back["req"] = pd.to_datetime(back["snapshot_requested_utc"], utc=True)
    back["ret"] = pd.to_datetime(back["snapshot_returned_utc"], utc=True)
    back["fin"] = pd.to_datetime(back["finished_utc"], utc=True)
    commence = (pd.to_datetime(hist["commence_time"], utc=True)
                .groupby(hist["game_id"]).min().rename("commence"))
    j = back.set_index("game_id").join(commence)
    lead = (j["commence"] - j["ret"]).dt.total_seconds() / 60.0

    m["M2_retrospective_archive"] = {
        "path": "data/props_capture/historical/master_props_historical.csv",
        "rows": int(len(hist)),
        "games": int(hist["game_id"].nunique()),
        "markets": sorted(hist["market_key"].unique().tolist()),
        "commence_min": str(hist["commence_time"].min()),
        "commence_max": str(hist["commence_time"].max()),
        "rows_by_book": {k: int(v) for k, v in hist["bookmaker_key"].value_counts().items()},
        "has_player_id_column": bool("player_id" in hist.columns),
        "has_settlement_or_result_column": bool(
            any(c.lower() in {"result", "settled", "graded", "outcome", "actual"}
                for c in hist.columns)),
        "distinct_requested_snapshots_per_game_max": int(
            hist.groupby("game_id")["snapshot_requested_utc"].nunique().max()),
        "distinct_returned_snapshots_per_game_max": int(
            hist.groupby("game_id")["snapshot_returned_utc"].nunique().max()),
        "requested_minute_of_hour_counts": {
            int(k): int(v) for k, v in back["req"].dt.minute.value_counts().items()},
        "lead_minutes_min": float(lead.min()),
        "lead_minutes_median": float(lead.median()),
        "lead_minutes_max": float(lead.max()),
        "rows_with_snapshot_after_commence": int((lead < 0).sum()),
        "harvest_finished_utc_min": str(back["fin"].min()),
        "harvest_finished_utc_max": str(back["fin"].max()),
        "harvest_burst_seconds": float((back["fin"].max() - back["fin"].min()).total_seconds()),
        "backfill_status_counts": {k: int(v) for k, v in back["status"].value_counts().items()},
        "priced_players_per_game_mean": float(back["n_players"].mean()),
        "priced_players_per_game_min": int(back["n_players"].min()),
        "priced_players_per_game_max": int(back["n_players"].max()),
    }

    # ---- M3  overlap with the modelling universe -----------------------------------------
    uni = pd.read_parquet(UNIVERSE)
    tgt = pd.read_parquet(PLAYER_TARGETS)
    seasons = tgt.groupby("game_id")[["season", "season_type"]].first()
    uni2 = uni.set_index("game_id").join(seasons)
    props_gids = set(back["game_id"].astype(str))
    uni2["has_props"] = uni2.index.astype(str).isin(props_gids)
    by_season = uni2.groupby("season")["has_props"].agg(["sum", "count"])

    m["M3_universe_overlap"] = {
        "universe_artifact": ("experiments/player_program/turnover_targets_v1/"
                              "team_turnover_reconciliation_v1.parquet"),
        "universe_team_game_rows": int(len(uni)),
        "universe_games": int(uni["game_id"].nunique()),
        "props_games": len(props_gids),
        "props_games_inside_universe": int(len(props_gids & set(uni["game_id"].astype(str)))),
        "props_rows_inside_universe": int(
            hist["game_id"].astype(str).isin(set(uni["game_id"].astype(str))).sum()),
        "team_game_rows_with_props_by_season": {
            int(s): {"with_props": int(r["sum"]), "total": int(r["count"])}
            for s, r in by_season.iterrows()},
    }

    # ---- M4  identity join, archive side --------------------------------------------------
    mp = pd.read_parquet(MASTER_PLAYER)
    mp["n"] = mp["player_name"].map(norm)
    mp["gid"] = mp["game_id"].astype(str)
    key = set(zip(mp["gid"], mp["n"]))
    hp = hist[["game_id", "player_name"]].drop_duplicates().copy()
    hp["gid"] = hp["game_id"].astype(str)
    hp["n"] = hp["player_name"].map(norm)
    hp["matched"] = [(g, n) in key for g, n in zip(hp["gid"], hp["n"])]
    unmatched = hp.loc[~hp["matched"]]
    all_names = set(mp["n"])

    m["M4_identity_join_archive"] = {
        "priced_player_games": int(len(hp)),
        "matched_same_game_box_row": int(hp["matched"].sum()),
        "match_rate": float(hp["matched"].mean()),
        "unmatched_player_games": int(len(unmatched)),
        "unmatched_distinct_name_strings": int(unmatched["player_name"].nunique()),
        "unmatched_whose_name_exists_elsewhere_in_master": int(
            unmatched["n"].isin(all_names).sum()),
        "top_unmatched_names": {str(k): int(v) for k, v in
                                unmatched["player_name"].value_counts().head(10).items()},
        "distinct_priced_players": int(hp["n"].nunique()),
        "note": ("normalized-exact name join only; no player_id exists on either props file. "
                 "A non-match is not evidence of a settlement error and was not treated as one."),
    }

    # ---- M5  settleability of the outcome column ------------------------------------------
    m["M5_outcome_column"] = {
        "master_player_rows": int(len(mp)),
        "master_player_max_game_date": str(mp["game_date"].astype(str).max()),
        "rows_with_dnp_reason": int(mp["dnp_reason"].notna().sum()),
        "rows_with_null_pts": int(mp["pts"].isna().sum()),
        "null_pts_share": float(mp["pts"].isna().mean()),
    }

    # ---- M6  gradeability of the prospective stream today ---------------------------------
    live["date"] = (pd.to_datetime(live["commence_time"], utc=True)
                    .dt.tz_convert("US/Eastern").dt.date.astype(str))
    sub = live[["date", "player_name"]].drop_duplicates().copy()
    sub["n"] = sub["player_name"].map(norm)
    datekey = set(zip(mp["game_date"].astype(str).str[:10], mp["n"]))
    sub["matched"] = [(d, n) in datekey for d, n in zip(sub["date"], sub["n"])]
    m["M6_prospective_gradeability"] = {
        "live_priced_player_games": int(len(sub)),
        "with_a_box_row_on_that_date_in_master": int(sub["matched"].sum()),
        "without": int((~sub["matched"]).sum()),
        "reason_checked": ("master_player.parquet ends at "
                          f"{mp['game_date'].astype(str).max()}; the live stream prices games "
                          "commencing after that date."),
    }

    OUT.write_text(json.dumps(m, indent=2, sort_keys=False), encoding="utf-8")
    print(json.dumps(m, indent=2)[:400])
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
