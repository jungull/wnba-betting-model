#!/usr/bin/env python3
"""universe.py -- the pinned 1,491-cluster / 2,982-row universe and the shared row base.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

Two frames, and the distinction is load-bearing:

  * `team_rows`  -- 2,982 team-game rows. THE PINNED STRICTLY-PRIOR ROW BASE (S34 finding B2).
                    Every strictly-prior construction in this slate, arm and K0 alike, draws its
                    prior rows from HERE and never from the 1,495-cluster full schedule.
  * `games`      -- 1,491 game-cluster rows, one per game. The head's design grain
                    ("game-level: one row per game cluster; no player->team or side->game
                    aggregation stage in the head").

O2 ENFORCEMENT. `build_universe()` refuses to return anything unless
`PREBUILD_GAME_ID_DIGEST.json` exists AND the game_id set it builds re-derives to the digest
pinned there. That is what converts `invariants.rows` from a deferral into a receipted invariant:
no design matrix in this node can exist over a row set the pre-build receipt did not pin.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

import runner_constants as K
from canon import column_digest, sha256_file

PREBUILD_RECEIPT = K.NODE_DIR / "PREBUILD_GAME_ID_DIGEST.json"


class UniverseHalt(RuntimeError):
    """Fail-closed universe error. HALT, do not build."""


@dataclass(frozen=True)
class Universe:
    games: pd.DataFrame        # 1,491 rows, one per game cluster
    team_rows: pd.DataFrame    # 2,982 rows, the pinned strictly-prior row base
    game_id_digest: str
    receipt: dict

    def fold(self, fold_id: str) -> dict:
        """Positional index arrays into `games`. Games are never split: a cluster is one row here,
        so 'never split' is enforced by the grain itself."""
        spec = K.FOLDS[fold_id]
        s = self.games["season"].to_numpy()
        train = np.flatnonzero(np.isin(s, spec["train_seasons"]))
        test = np.flatnonzero(s == spec["test_season"])
        if len(train) != spec["train_clusters"] or len(test) != spec["test_clusters"]:
            raise UniverseHalt(
                f"fold {fold_id}: measured {len(train)}/{len(test)} train/test clusters, pinned "
                f"{spec['train_clusters']}/{spec['test_clusters']}")
        return {"fold_id": fold_id, "train_idx": train, "test_idx": test}

    def all_folds(self) -> list[dict]:
        return [self.fold(f) for f in K.FOLD_IDS]


def _verify_input_pins() -> dict:
    out = {}
    for rel, exp in K.INPUT_PINS.items():
        p = K.artifact_path(rel)
        if not p.exists():
            raise UniverseHalt(f"pinned input missing from the PROGRAM WORKTREE: {p}")
        got = sha256_file(p)
        if rel.endswith("master_team.parquet") and got == K.KNOWN_DRIFTED_MASTER_TEAM_SHA256:
            raise UniverseHalt(f"ROOT_PATH_RULE: {p} is the KNOWN DRIFTED copy. HALT. "
                               f"{K.ROOT_PATH_RULE}")
        if got != exp:
            raise UniverseHalt(f"byte pin failed for {rel}: {got} != {exp}. HALT, do not build.")
        out[rel] = got
    return out


def _load_prebuild_digest() -> str:
    if not PREBUILD_RECEIPT.exists():
        raise UniverseHalt(
            "O2 NOT DISCHARGED: PREBUILD_GAME_ID_DIGEST.json does not exist. The obligation is "
            "'before any design matrix is constructed'; run prebuild/PREBUILD_GAME_ID_DIGEST.py "
            "first. HALT before fitting.")
    r = json.loads(PREBUILD_RECEIPT.read_text(encoding="utf-8"))
    d = r.get("GAME_ID_SET_SHA256")
    if not d:
        raise UniverseHalt("O2 receipt exists but carries no GAME_ID_SET_SHA256. HALT.")
    return d


def _composite_columns(game_ids: list[str]) -> pd.DataFrame:
    """The null-granted composite columns, with the card's shared fallback.

    invariants.fallback_machinery (identical on both sides, all 17 cards): the 26
    composite-uncovered clusters take the frozen store's league_average_v1 row for the SAME
    game_id as the null-granted column value. The rule string is declared on both sides; the K0
    simply has no treatment term the arm-side half of the rule can touch."""
    sb = pd.read_parquet(K.artifact_path(
        "experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet"))
    sb["game_id"] = sb["game_id"].astype(str)
    comp = sb[sb["method"] == K.COMPOSITE_METHOD].set_index("game_id")
    fallb = sb[sb["method"] == K.FALLBACK_METHOD].set_index("game_id")

    rows = []
    for g in game_ids:
        if g in comp.index:
            src, r = K.COMPOSITE_METHOD, comp.loc[g]
        elif g in fallb.index:
            src, r = K.FALLBACK_METHOD, fallb.loc[g]
        else:
            raise UniverseHalt(f"game {g} covered by neither {K.COMPOSITE_METHOD} nor "
                               f"{K.FALLBACK_METHOD}; the fallback rule is not total. HALT.")
        rows.append({"game_id": g, "composite_source": src,
                     "C_margin": float(r["pred_margin"]), "C_total": float(r["pred_total"]),
                     "C_p_home": float(r["p_home"]) if pd.notna(r["p_home"]) else np.nan})
    return pd.DataFrame(rows).set_index("game_id")


def build_universe(*, verify_pins: bool = True) -> Universe:
    """The single entry point. Fails closed on any pin, count or O2 mismatch."""
    K.assert_program_worktree()
    pins = _verify_input_pins() if verify_pins else {}
    pinned_digest = _load_prebuild_digest()

    mt = pd.read_parquet(K.artifact_path("data/masters/master_team.parquet"))
    mt["game_id"] = mt["game_id"].astype(str)
    mt["game_date"] = mt["game_date"].astype(str)

    keep = mt[(mt["is_home"] == 1) & (mt["game_date"] != K.D010_EXCLUDED_DATE)]["game_id"]
    ids = set(keep.astype(str))
    team_rows = mt[mt["game_id"].isin(ids)].copy()
    game_ids = sorted(ids)

    digest = column_digest(game_ids)
    if digest != pinned_digest:
        raise UniverseHalt(
            f"O2 MISMATCH: the built game_id set digests to {digest}, the pre-build receipt pins "
            f"{pinned_digest}. HALT before fitting.")
    if len(game_ids) != K.UNIVERSE_CLUSTERS or len(team_rows) != K.UNIVERSE_ROWS:
        raise UniverseHalt(f"universe is {len(game_ids)}/{len(team_rows)}, pinned "
                           f"{K.UNIVERSE_CLUSTERS}/{K.UNIVERSE_ROWS}. HALT.")

    # --- the strictly-prior row base: sequenced (game_date, game_id), the pinned ordering -------
    team_rows = team_rows.sort_values(["game_date", "game_id", "team_id"],
                                      kind="mergesort").reset_index(drop=True)
    team_rows["margin"] = (team_rows["pts"] - team_rows["opp_pts"]).astype(float)
    team_rows["env"] = (team_rows["pts"] + team_rows["opp_pts"]).astype(float)
    team_rows["team_id"] = team_rows["team_id"].astype("int64")
    team_rows["opp_team_id"] = team_rows["opp_team_id"].astype("int64")
    team_rows["pts"] = team_rows["pts"].astype(float)
    team_rows["opp_pts"] = team_rows["opp_pts"].astype(float)

    # --- the game-cluster frame ----------------------------------------------------------------
    h = team_rows[team_rows["is_home"] == 1][
        ["game_id", "season", "season_type", "game_date", "team_id", "opp_team_id",
         "pts", "opp_pts"]].rename(columns={"team_id": "home_team_id",
                                            "opp_team_id": "away_team_id",
                                            "pts": "home_pts", "opp_pts": "away_pts"})
    games = h.sort_values(["game_date", "game_id"], kind="mergesort").reset_index(drop=True)

    # Estimand targets (D049: full-game settled quantities, OT included).
    games["E1_GAME_TOTAL"] = games["home_pts"] + games["away_pts"]
    games["E2_FINAL_MARGIN_HOME"] = games["home_pts"] - games["away_pts"]
    games["E3_HOME_WIN_PROB"] = (games["E2_FINAL_MARGIN_HOME"] > 0).astype(float)
    if int((games["E2_FINAL_MARGIN_HOME"] == 0).sum()):
        raise UniverseHalt("settled ties present: E3_HOME_WIN_PROB is not well defined. HALT.")

    comp = _composite_columns(games["game_id"].tolist())
    games = games.join(comp, on="game_id")
    n_fallback = int((games["composite_source"] == K.FALLBACK_METHOD).sum())
    if n_fallback != K.N_COMPOSITE_UNCOVERED:
        raise UniverseHalt(f"composite fallback touched {n_fallback} clusters, card measures "
                           f"{K.N_COMPOSITE_UNCOVERED}. HALT.")

    games["era_2024"] = (games["season"] >= 2024).astype(float)
    games = games.reset_index(drop=True)

    receipt = {
        "schema": "s36_universe/1",
        "game_id_digest": digest,
        "o2_prebuild_digest_matched": True,
        "n_clusters": len(games), "n_team_game_rows": len(team_rows),
        "per_season_clusters": {int(k): int(v) for k, v in
                                games.groupby("season")["game_id"].nunique().items()},
        "input_pins_verified": pins,
        "strictly_prior_row_base": K.STRICTLY_PRIOR_ROW_BASE,
        "independent_unit": K.INDEPENDENT_UNIT,
        "games_never_split": K.GAMES_NEVER_SPLIT,
        "d010_caveat": K.D010_CAVEAT,
        "composite_fallback_clusters": n_fallback,
        "composite_fallback_rule": ("the 26 composite-uncovered clusters take the frozen store's "
                                    "league_average_v1 row for the same game_id; identical on "
                                    "both sides"),
        "p_home_structural_nan_rows": int(games["C_p_home"].isna().sum()),
    }
    return Universe(games=games, team_rows=team_rows, game_id_digest=digest, receipt=receipt)


# ------------------------------------------------------------------------------------------
# Strictly-prior helpers -- shared by every arm so that "strictly prior" means ONE thing.
# ------------------------------------------------------------------------------------------
def prior_counts_same_season(team_rows: pd.DataFrame) -> pd.DataFrame:
    """n = same-season strictly-prior COMPLETED resolved-universe games, per (game_id, team_id).

    'Strictly prior' is by the pinned sequencing (game_date, game_id): a row's own game and every
    game on a later date/id is excluded. Same-day games are ordered by game_id, and a same-day
    earlier game_id DOES count as prior -- the same convention every EWMA in this slate uses."""
    tr = team_rows.sort_values(["team_id", "season", "game_date", "game_id"], kind="mergesort")
    tr = tr.copy()
    tr["n_prior_same_season"] = tr.groupby(["team_id", "season"]).cumcount()
    return tr[["game_id", "team_id", "season", "n_prior_same_season"]]


def side_frame(universe: Universe) -> pd.DataFrame:
    """Per-game home/away view of any per-(game_id, team_id) quantity: join twice on team_id."""
    g = universe.games
    return pd.DataFrame({"game_id": g["game_id"], "season": g["season"],
                         "game_date": g["game_date"],
                         "home_team_id": g["home_team_id"], "away_team_id": g["away_team_id"]})


def attach_side(games: pd.DataFrame, per_team: pd.DataFrame, value_col: str,
                out_home: str, out_away: str, fill: float = 0.0) -> pd.DataFrame:
    """Attach a per-(game_id, team_id) column to the game frame as (home, away) columns."""
    idx = per_team.set_index([per_team["game_id"].astype(str),
                              per_team["team_id"].astype("int64")])[value_col]
    out = games.copy()
    hk = list(zip(out["game_id"].astype(str), out["home_team_id"].astype("int64")))
    ak = list(zip(out["game_id"].astype(str), out["away_team_id"].astype("int64")))
    out[out_home] = pd.Series(idx.reindex(hk).to_numpy(), index=out.index).fillna(fill).astype(float)
    out[out_away] = pd.Series(idx.reindex(ak).to_numpy(), index=out.index).fillna(fill).astype(float)
    return out
