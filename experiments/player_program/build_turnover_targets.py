#!/usr/bin/env python3
"""build_turnover_targets.py — realised turnover targets. P0 construction only.

Registered before execution as `turnover_target_contract_v1`. **Nothing is fitted and nothing is
scored.** No model, no window, no decay, no steal linkage.

Run::  python experiments/player_program/build_turnover_targets.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from register_turnover_targets import MECHANISM_CROSSWALK  # noqa: E402

OUT = HERE / "turnover_targets_v1"
EVENTS = HERE / "event_contract_v1/canonical_player_events_v1.parquet"
POSS = HERE / "possessions_v2/possessions_raw_v2.parquet"
MP = ROOT / "data/masters/master_player.parquet"
MT = ROOT / "data/masters/master_team.parquet"


class ProducerFailure(RuntimeError):
    pass


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# flatten the crosswalk into lookup maps
LEG2MECH, CDN2MECH, MECH2GROUP = {}, {}, {}
for mech, d in MECHANISM_CROSSWALK.items():
    MECH2GROUP[mech] = d["group"]
    for k in d["legacy"]:
        LEG2MECH[k] = mech
    for k in d["cdn"]:
        CDN2MECH[k] = mech


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    started = _utc()
    producer_sha = _sha(Path(__file__))

    E = pd.read_parquet(EVENTS)
    T = E[E["event_family"] == "turnover"].copy()
    if len(T) == 0:
        raise ProducerFailure("no turnover events")

    # ---- mechanism mapping ---------------------------------------------------- #
    is_leg = T["source_system"] == "nba_playbyplayv2"
    mech = np.where(is_leg,
                    T["source_subtype_raw"].map(LEG2MECH),
                    T["event_subtype"].astype("string").fillna("").map(CDN2MECH))
    T["mechanism"] = pd.Series(mech, index=T.index).fillna("unresolved")
    T["mechanism_unmapped"] = pd.Series(mech, index=T.index).isna()
    T["mechanism_group"] = T["mechanism"].map(MECH2GROUP).fillna("unknown")

    # ---- team vs player attribution ------------------------------------------- #
    mt = pd.read_parquet(MT, columns=["game_id", "team_id"]).drop_duplicates()
    mt["game_id"] = mt["game_id"].astype(str)
    team_ids = set(mt["team_id"].astype("int64"))
    p1 = T["player1_id"]
    T["is_team_turnover"] = p1.isna() | p1.astype("Int64").isin(team_ids)
    T["attributed_player_id"] = p1.where(~T["is_team_turnover"]).astype("Int64")

    # the event team: for a team turnover the person field IS the team
    T["turnover_team_id"] = np.where(
        T["is_team_turnover"] & p1.notna(), p1, T["event_team_id"])
    T["turnover_team_id"] = pd.to_numeric(T["turnover_team_id"], errors="coerce").astype("Int64")

    # Registered scoreability rule: an event with NO resolvable team and NO player is UNRESOLVED.
    # It stays visible and counted; it is never silently dropped and never assigned to a club.
    no_team = T["turnover_team_id"].isna()
    T["disposition"] = np.where(
        no_team, "unresolved_no_team",
        np.where(T["is_team_turnover"], "team_unattributed", "player_attributed"))
    unresolved_events = T[no_team][["game_id", "source_system", "period",
                                    "source_subtype_raw", "description"]].to_dict("records")

    # ---- exposure: realised offensive possessions ----------------------------- #
    P = pd.read_parquet(POSS, columns=["game_id", "offense_team_id", "lineup_valid"]
                        if "lineup_valid" in pd.read_parquet(POSS).columns[:60] else
                        ["game_id", "offense_team_id"])
    P["game_id"] = P["game_id"].astype(str)
    pl = pd.read_parquet(POSS, columns=["game_id", "offense_team_id"] +
                         [f"off_p{i}" for i in range(1, 6)])
    pl["game_id"] = pl["game_id"].astype(str)
    long = pl.melt(id_vars=["game_id", "offense_team_id"],
                   value_vars=[f"off_p{i}" for i in range(1, 6)], value_name="player_id")
    long = long[long["player_id"].notna()]
    long["player_id"] = long["player_id"].astype("int64")
    expo = (long.groupby(["game_id", "offense_team_id", "player_id"]).size()
            .rename("realised_off_possessions").reset_index()
            .rename(columns={"offense_team_id": "team_id"}))
    team_expo = (P.groupby(["game_id", "offense_team_id"]).size()
                 .rename("team_off_possessions").reset_index()
                 .rename(columns={"offense_team_id": "team_id"}))

    # ---- row universe --------------------------------------------------------- #
    box = pd.read_parquet(MP, columns=["game_id", "team_id", "player_id", "minutes", "tov",
                                       "season", "season_type"])
    box["game_id"] = box["game_id"].astype(str)
    appeared = box[box["minutes"].notna()].copy()
    universe = appeared[["game_id", "team_id", "player_id", "season", "season_type",
                         "minutes", "tov"]].rename(columns={"tov": "external_tov"})
    universe = universe.merge(expo, on=["game_id", "team_id", "player_id"], how="left")
    universe["zero_possession_exposure"] = universe["realised_off_possessions"].isna()
    universe["realised_off_possessions"] = universe["realised_off_possessions"].fillna(0).astype(int)

    # ---- player targets ------------------------------------------------------- #
    pa = T[T["disposition"] == "player_attributed"]
    tot = (pa.groupby(["game_id", "turnover_team_id", "attributed_player_id"]).size()
           .rename("turnovers").reset_index()
           .rename(columns={"turnover_team_id": "team_id",
                            "attributed_player_id": "player_id"}))
    tot["player_id"] = tot["player_id"].astype("int64")
    tot["team_id"] = tot["team_id"].astype("int64")

    mech_wide = (pa.groupby(["game_id", "turnover_team_id", "attributed_player_id",
                             "mechanism"]).size().unstack(fill_value=0).reset_index()
                 .rename(columns={"turnover_team_id": "team_id",
                                  "attributed_player_id": "player_id"}))
    mech_cols = [c for c in mech_wide.columns if c in MECH2GROUP]
    mech_wide["player_id"] = mech_wide["player_id"].astype("int64")
    mech_wide["team_id"] = mech_wide["team_id"].astype("int64")

    players = universe.merge(tot, on=["game_id", "team_id", "player_id"], how="left")
    players["turnovers"] = players["turnovers"].fillna(0).astype(int)
    players = players.merge(mech_wide, on=["game_id", "team_id", "player_id"], how="left")
    for c in mech_cols:
        players[c] = players[c].fillna(0).astype(int)
    players["scoreable"] = True
    players["rate_defined"] = players["realised_off_possessions"] > 0
    players["turnovers_per_100_off_poss"] = np.where(
        players["rate_defined"],
        100.0 * players["turnovers"] / players["realised_off_possessions"].replace(0, np.nan),
        np.nan)

    # turnovers attributed to a player who has no scoreable row -> counted, never dropped
    orphan = tot.merge(universe[["game_id", "team_id", "player_id"]],
                       on=["game_id", "team_id", "player_id"], how="left", indicator=True)
    orphan = orphan[orphan["_merge"] == "left_only"]

    # ---- team reconciliation -------------------------------------------------- #
    T_team = T[T["disposition"] != "unresolved_no_team"]
    team_tot = (T_team.groupby(["game_id", "turnover_team_id"]).size()
                .rename("team_turnovers_total").reset_index()
                .rename(columns={"turnover_team_id": "team_id"}))
    team_pa = (pa.groupby(["game_id", "turnover_team_id"]).size()
               .rename("player_attributed").reset_index()
               .rename(columns={"turnover_team_id": "team_id"}))
    team_un = (T_team[T_team["disposition"] == "team_unattributed"]
               .groupby(["game_id", "turnover_team_id"]).size()
               .rename("team_unattributed").reset_index()
               .rename(columns={"turnover_team_id": "team_id"}))
    teams = (mt.assign(team_id=mt["team_id"].astype("int64"))
             .merge(team_tot, on=["game_id", "team_id"], how="left")
             .merge(team_pa, on=["game_id", "team_id"], how="left")
             .merge(team_un, on=["game_id", "team_id"], how="left")
             .merge(team_expo.assign(team_id=team_expo["team_id"].astype("int64")),
                    on=["game_id", "team_id"], how="left"))
    for c in ["team_turnovers_total", "player_attributed", "team_unattributed"]:
        teams[c] = teams[c].fillna(0).astype(int)
    src = E.drop_duplicates("game_id")[["game_id", "source_system"]]
    teams = teams.merge(src, on="game_id", how="left")
    mtv = pd.read_parquet(MT, columns=["game_id", "team_id", "tov"])
    mtv["game_id"] = mtv["game_id"].astype(str)
    mtv["team_id"] = mtv["team_id"].astype("int64")
    teams = teams.merge(mtv.rename(columns={"tov": "external_team_tov"}),
                        on=["game_id", "team_id"], how="left")
    teams["diff_vs_external"] = teams["team_turnovers_total"] - teams["external_team_tov"]
    teams["player_sum_from_artifact"] = (
        players.groupby(["game_id", "team_id"])["turnovers"].sum()
        .reindex(pd.MultiIndex.from_frame(teams[["game_id", "team_id"]])).fillna(0).astype(int).values)

    # ---- fail-closed conservation --------------------------------------------- #
    if not (teams["player_attributed"] + teams["team_unattributed"]
            == teams["team_turnovers_total"]).all():
        raise ProducerFailure("player + team components do not sum to the team total")
    if mech_cols:
        s = players[mech_cols].sum(axis=1)
        bad = int((s != players["turnovers"]).sum())
        if bad:
            raise ProducerFailure(f"{bad} player rows: mechanism counts != total turnovers")
    if players.duplicated(["game_id", "team_id", "player_id"]).any():
        raise ProducerFailure("duplicate player-game rows")
    both = pa.groupby(["game_id", "attributed_player_id"])["turnover_team_id"].nunique()
    if (both > 1).any():
        raise ProducerFailure(f"{int((both > 1).sum())} players attributed to both clubs in a game")

    players.to_parquet(OUT / "player_turnover_targets_v1.parquet", index=False)
    teams.to_parquet(OUT / "team_turnover_reconciliation_v1.parquet", index=False)

    by_src = T.groupby("source_system")
    receipt = {
        "schema": "turnover_target_receipt/1",
        "artifact_id": "player_turnover_targets/1",
        "experiment_id": "turnover_target_contract_v1",
        "generated_utc": started, "finished_utc": _utc(),
        "nothing_fitted": True, "nothing_scored": True, "no_steal_linkage": True,
        "producer_sha256": producer_sha,
        "inputs": {"events": _sha(EVENTS), "possessions": _sha(POSS),
                   "master_player": _sha(MP), "master_team": _sha(MT)},
        "counts": {
            "turnover_events": int(len(T)),
            "player_attributed": int((T["disposition"] == "player_attributed").sum()),
            "team_unattributed": int((T["disposition"] == "team_unattributed").sum()),
            "unresolved_no_team": int((T["disposition"] == "unresolved_no_team").sum()),
            "mechanism_unmapped": int(T["mechanism_unmapped"].sum()),
            "player_game_rows": int(len(players)),
            "player_game_rows_with_zero_turnovers": int((players["turnovers"] == 0).sum()),
            "team_game_rows": int(len(teams)),
            "orphan_attributions_not_in_box": int(len(orphan)),
        },
        "unresolved_no_team_events": unresolved_events,
        "disposition_counts": T["disposition"].value_counts().to_dict(),
        "mechanism_distribution": T["mechanism"].value_counts().to_dict(),
        "mechanism_group_distribution": T["mechanism_group"].value_counts().to_dict(),
        "by_source": {
            "events": by_src.size().to_dict(),
            "player_attributed": by_src["disposition"].apply(
                lambda s: int((s == "player_attributed").sum())).to_dict(),
            "team_unattributed": by_src["disposition"].apply(
                lambda s: int((s == "team_unattributed").sum())).to_dict(),
            "mechanism_counts": {str(src): sub["mechanism"].value_counts().to_dict()
                                 for src, sub in T.groupby("source_system")},
            "mechanism_share": {str(src): (sub["mechanism"].value_counts()
                                           / len(sub)).round(5).to_dict()
                                for src, sub in T.groupby("source_system")},
            "unresolved_rate": by_src["mechanism"].apply(
                lambda s: round(float((s == "unresolved").mean()), 6)).to_dict(),
        },
        "exposure": {
            "denominator_name": "offensive-possession exposure",
            "source": "realised player offensive possessions from player_possessions/2",
            "not_a_complete_opportunity_denominator": True,
            "player_rows_with_positive_exposure": int((players["realised_off_possessions"] > 0).sum()),
            "player_rows_zero_exposure": int(players["zero_possession_exposure"].sum()),
            "rate_defined_rows": int(players["rate_defined"].sum()),
        },
        "external_reconciliation_preview": {
            "team_exact": int((teams["diff_vs_external"] == 0).sum()),
            "team_off_by_one": int((teams["diff_vs_external"].abs() == 1).sum()),
            "team_larger": int((teams["diff_vs_external"].abs() > 1).sum()),
            "team_missing_external": int(teams["external_team_tov"].isna().sum()),
        },
        "artifact_sha256": {
            "player": _sha(OUT / "player_turnover_targets_v1.parquet"),
            "team": _sha(OUT / "team_turnover_reconciliation_v1.parquet"),
        },
    }
    (OUT / "TURNOVER_TARGET_RECEIPT.json").write_text(json.dumps(receipt, indent=2, default=str),
                                                      encoding="utf-8")
    print(f"turnover events {len(T):,}  player-attributed "
          f"{receipt['counts']['player_attributed']:,}  team {receipt['counts']['team_unattributed']:,}")
    print(f"player-game rows {len(players):,} ({receipt['counts']['player_game_rows_with_zero_turnovers']:,} zero)")
    print(f"team-game rows {len(teams):,}")
    print(f"external team: exact {receipt['external_reconciliation_preview']['team_exact']}, "
          f"off-by-one {receipt['external_reconciliation_preview']['team_off_by_one']}, "
          f"larger {receipt['external_reconciliation_preview']['team_larger']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ProducerFailure as exc:
        print(f"PRODUCER FAILED CLOSED: {exc}", file=sys.stderr)
        sys.exit(2)
