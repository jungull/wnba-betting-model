#!/usr/bin/env python3
"""SUPERSEDED by prediction_contract_v2.py -- DO NOT CONSUME.

Retained as a superseded artifact per prediction_contract_v2. Three foundational defects,
all conceded:
  D1 the candidate universe was built from TARGET-GAME boxscore rows, so a player absent
     from the target box never entered it and p_active was conditioned on appearing;
  D2 prediction obligation was conflated with scoring eligibility, letting an arm buy
     coverage by dropping everyone later inactive;
  D3 the cutoff game_date + 22:30 UTC was fabricated and labelled T-90m -- for the 199 of
     784 games tipping 15:00-22:00 UTC it fell AFTER TIP.
Plus D4: the team target was duplicated once per player row.
Its VALIDATOR was sound; the universe it validated was not.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
import asof_invariant as ai                                    # noqa: E402

OUT = REPO / "experiments" / "prediction_contract"
MASTER = REPO / "data" / "masters" / "master_player.parquet"

CONTRACT_VERSION = "player_game_contract/1"

# --------------------------------------------------------------------------- #
# Targets.  Each is its own council under council_scope_v2 S6.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Target:
    key: str
    description: str
    support: str                 # what a prediction means
    eligibility: str             # which rows are scoreable for THIS target
    uncertainty: str             # what the uncertainty field must carry
    clustering: str              # inference clustering unit


TARGETS: dict[str, Target] = {
    "p_active": Target(
        "p_active",
        "Probability the player appears in the game at all.",
        "probability in [0, 1]",
        "every row on a slate the player's team plays, INCLUDING players who do not appear "
        "-- excluding them is the selection bias this target exists to measure",
        "the probability IS the uncertainty; calibration is scored, not a variance",
        "game_date"),
    "e_minutes_given_active": Target(
        "e_minutes_given_active",
        "Expected minutes CONDITIONAL on appearing.",
        "minutes >= 0",
        "rows where the player actually appeared (min > 0); conditioning is explicit so it "
        "is never confused with unconditional expected minutes",
        "predictive sd of minutes, strictly > 0",
        "game_date"),
    "attempts_usage": Target(
        "attempts_usage",
        "Scoring opportunity: field-goal attempts per game (usage proxy).",
        "attempts >= 0",
        "rows where the player appeared AND team possessions are reconciled",
        "predictive sd of attempts, strictly > 0",
        "game_date"),
    "player_scoring_distribution": Target(
        "player_scoring_distribution",
        "Full predictive distribution of player points.",
        "distribution over points >= 0",
        "rows where the player appeared and points are resolved",
        "predictive sd PLUS the quantiles named in QUANTILES; a point estimate alone is "
        "NOT contract-compliant for this target",
        "game_date"),
    "team_game_distribution": Target(
        "team_game_distribution",
        "Team score / margin / total distribution.",
        "distribution over team points",
        "one row per team-game with a resolved final score",
        "predictive sd of team points",
        "game_date"),
}

QUANTILES = [0.05, 0.25, 0.50, 0.75, 0.95]

#: Every arm MUST emit exactly these columns.  Extra columns are permitted and ignored;
#: a missing column is a contract violation and the arm is rejected, not patched.
PREDICTION_SCHEMA: dict[str, str] = {
    "row_uid":            "canonical player-game id from this module; the join key",
    "target_key":         "one of TARGETS",
    "arm_id":             "stable arm name, e.g. incumbent_ewma_ridge",
    "fold_id":            "exact OOF fold identity; must match the contract's fold map",
    "forecast_cutoff":    "tz-aware ISO8601; the moment the prediction is committed",
    "pred_point":         "point prediction on the target's support",
    "pred_sd":            "predictive sd; > 0 except where the target says otherwise",
    "pred_q05":           "5th percentile (distribution targets; else null)",
    "pred_q25":           "25th percentile (else null)",
    "pred_q50":           "median (else null)",
    "pred_q75":           "75th percentile (else null)",
    "pred_q95":           "95th percentile (else null)",
    "is_fallback":        "bool: a fallback path produced this, not the arm's normal path",
    "is_cold_start":      "bool: insufficient prior history for this player at this cutoff",
    "n_prior_games":      "int: strictly-prior appearances the arm could read",
    "feature_asof":       "tz-aware ISO8601: LATEST source observation the arm read. MUST be "
                          "strictly < forecast_cutoff",
    "model_hash":         "hash of fitted parameters",
    "config_hash":        "hash of the arm's configuration",
    "data_snapshot_hash": "hash of the input snapshot",
    "exclusion_reason":   "null if predicted; otherwise why this eligible row has no "
                          "prediction. A silently missing row is a violation",
}

REQUIRED_COLS = tuple(PREDICTION_SCHEMA)


def stable_hash(*parts: object) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()[:16]


def row_uid(player_id: int, game_id: str) -> str:
    """Canonical player-game id.

    Deliberately derived from (player_id, game_id) ONLY -- not from date, team or season,
    all of which can be restated or corrected later.  A uid that moves when a team
    abbreviation is fixed would silently break every join that depends on it.
    """
    return "pg_" + stable_hash(int(player_id), str(game_id))


def build_universe(cutoff_policy: str = "T-90m") -> tuple[pd.DataFrame, dict]:
    """The evaluation universe: canonical rows, cutoffs, eligibility and folds.

    Returns the row index every arm must predict onto, plus an accounting dict in which every
    excluded row carries a reason.
    """
    mp = pd.read_parquet(MASTER)
    acct = {"master_rows": int(len(mp))}

    d = mp.copy()
    d["game_date"] = pd.to_datetime(d["game_date"], errors="coerce")
    d = d[d.game_date.notna() & d.player_id.notna() & d.game_id.notna()]
    acct["after_keys_present"] = int(len(d))

    d["row_uid"] = [row_uid(p, g) for p, g in zip(d.player_id, d.game_id)]
    dup = int(d.row_uid.duplicated().sum())
    acct["duplicate_row_uids"] = dup
    if dup:
        raise SystemExit(f"row_uid is not unique ({dup} duplicates) -- contract is unsound")

    # Forecast cutoff.  Tip time is not in the master, so the cutoff is derived from the game
    # DATE with an explicit policy and recorded as such.  It is deliberately conservative:
    # an arm may read nothing at or after it.
    if cutoff_policy != "T-90m":
        raise SystemExit(f"unsupported cutoff policy {cutoff_policy}")
    d["forecast_cutoff"] = (d.game_date.dt.tz_localize("UTC")
                            + pd.Timedelta(hours=22, minutes=30))
    d["cutoff_policy"] = cutoff_policy

    # Per-target eligibility, each recorded rather than implied.
    minutes = pd.to_numeric(d["minutes"], errors="coerce")
    pts = pd.to_numeric(d["pts"], errors="coerce")
    fga = pd.to_numeric(d["fga"], errors="coerce")
    # "Appeared" is minutes > 0, NOT "has a boxscore row". A rostered DNP still has a row,
    # and treating it as an appearance is precisely the selection bias p_active measures.
    appeared = minutes.fillna(0) > 0

    elig = pd.DataFrame({"row_uid": d.row_uid})
    elig["p_active"] = True                                  # every row, by design
    elig["e_minutes_given_active"] = appeared.to_numpy()
    elig["attempts_usage"] = (appeared & fga.notna()).to_numpy()
    elig["player_scoring_distribution"] = (appeared & pts.notna()).to_numpy()
    elig["team_game_distribution"] = True                    # collapsed to team-game later

    # OOF fold identity: expanding walk-forward BY SEASON, which is the repo's standing rule.
    d["fold_id"] = "season:" + d.season.astype(int).astype(str)
    d["train_boundary"] = d.season.astype(int).map(
        lambda s: f"seasons < {s}")

    universe = d[["row_uid", "player_id", "game_id", "season", "game_date",
                  "forecast_cutoff", "cutoff_policy", "fold_id", "train_boundary"]].copy()
    universe["clustering_unit"] = universe.game_date.dt.date.astype(str)

    for t in TARGETS:
        universe[f"eligible__{t}"] = elig[t].to_numpy()
        acct[f"eligible__{t}"] = int(elig[t].sum())
        acct[f"excluded__{t}"] = int((~elig[t]).sum())

    acct["rows"] = int(len(universe))
    acct["players"] = int(universe.player_id.nunique())
    acct["games"] = int(universe.game_id.nunique())
    acct["dates"] = int(universe.clustering_unit.nunique())
    acct["seasons"] = sorted(int(x) for x in universe.season.unique())
    return universe, acct


def validate_predictions(pred: pd.DataFrame, universe: pd.DataFrame,
                         target_key: str) -> dict:
    """Reject a non-compliant arm rather than repair it.

    Returns a report; ``ok`` is False if the arm violated the contract.  Repairing an arm's
    output here would silently make incomparable things comparable, which is the whole
    failure this contract exists to prevent.
    """
    problems: list[str] = []
    missing = [c for c in REQUIRED_COLS if c not in pred.columns]
    if missing:
        problems.append(f"missing required columns: {missing}")
        return {"ok": False, "problems": problems}

    elig = universe[universe[f"eligible__{target_key}"]]
    want, got = set(elig.row_uid), set(pred.row_uid)
    unknown = got - set(universe.row_uid)
    if unknown:
        problems.append(f"{len(unknown)} predictions on row_uids not in the universe")
    uncovered = want - got
    if uncovered:
        problems.append(f"{len(uncovered)} eligible rows with neither prediction nor "
                        f"exclusion_reason")
    if pred.row_uid.duplicated().any():
        problems.append("duplicate row_uid in predictions")

    predicted = pred[pred.exclusion_reason.isna()]
    if predicted.pred_point.isna().any():
        problems.append("null pred_point on a row with no exclusion_reason")
    if (predicted.pred_sd.fillna(-1) <= 0).any() and target_key != "p_active":
        problems.append("pred_sd must be strictly positive on distribution targets")
    if target_key == "player_scoring_distribution":
        qs = ["pred_q05", "pred_q25", "pred_q50", "pred_q75", "pred_q95"]
        if predicted[qs].isna().any().any():
            problems.append("quantiles required for player_scoring_distribution")
        else:
            q = predicted[qs].to_numpy()
            if (np.diff(q, axis=1) < 0).any():
                problems.append("quantiles are not monotone non-decreasing")

    # THE AS-OF INVARIANT, per row: an arm may not read anything at or after its own cutoff.
    fa = pd.to_datetime(predicted.feature_asof, errors="coerce", utc=True)
    fc = pd.to_datetime(predicted.forecast_cutoff, errors="coerce", utc=True)
    bad = int((fa >= fc).sum())
    if bad:
        problems.append(f"{bad} rows where feature_asof >= forecast_cutoff (leakage)")
    if fa.isna().any():
        problems.append("unparseable feature_asof")

    for h in ("model_hash", "config_hash", "data_snapshot_hash"):
        if predicted[h].isna().any():
            problems.append(f"{h} missing on some predicted rows")

    return {"ok": not problems, "problems": problems,
            "n_predicted": int(len(predicted)),
            "n_excluded": int(pred.exclusion_reason.notna().sum()),
            "n_eligible": int(len(elig)),
            "coverage": float(len(predicted) / len(elig)) if len(elig) else float("nan")}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    universe, acct = build_universe()

    universe.to_parquet(OUT / "universe.parquet", index=False)
    universe.to_csv(OUT / "universe.csv", index=False)

    spec = {
        "contract_version": CONTRACT_VERSION,
        "purpose": ("Shared PREDICTION CONTRACT and evaluation universe for the "
                    "target-specific councils (council_scope_v2 S6/S7). Arms may use "
                    "different internal inputs; they must share rows, cutoff, target "
                    "definition and output schema -- NOT one physical feature table."),
        "row_uid": ("pg_ + sha256(player_id, game_id)[:16]. Derived from ids ONLY, never "
                    "from date/team/season, so a later correction to a team abbreviation "
                    "cannot silently move the join key."),
        "cutoff_policy": {
            "value": "T-90m",
            "derivation": ("tip time is absent from master_player, so the cutoff is "
                           "game_date + 22:30 UTC, applied uniformly and recorded. It is "
                           "deliberately conservative; an arm may read nothing at or after "
                           "it. When true tip times are captured this becomes a new "
                           "contract version, not an edit."),
        },
        "targets": {k: asdict(v) for k, v in TARGETS.items()},
        "quantiles": QUANTILES,
        "prediction_schema": PREDICTION_SCHEMA,
        "fold_identity": ("fold_id = season:<S>; expanding walk-forward, train_boundary = "
                          "seasons < S. Every prediction carries its fold so cross-arm "
                          "alignment is checkable rather than assumed."),
        "clustering_unit": "game_date -- the unit all inference must cluster on",
        "compliance": ("validate_predictions() REJECTS a non-compliant arm rather than "
                       "repairing it. Repair would silently make incomparable things "
                       "comparable, which is the failure this contract prevents."),
        "accounting": acct,
    }
    (OUT / "contract.json").write_text(json.dumps(spec, indent=1, default=str),
                                       encoding="utf-8")

    src_max = pd.to_datetime(universe.game_date).max()
    ai.write_manifest(
        OUT / "universe.parquet", producer="prediction_contract.py",
        fit_through_date=src_max, fit_through_season=int(universe.season.max()),
        fit_seasons=sorted(int(x) for x in universe.season.unique()),
        asof_granularity="row",
        notes=("Player-game prediction contract universe. NOTHING IS FITTED HERE -- it is a "
               "row index, cutoff and eligibility map. asof_granularity=row because each row "
               "carries its own forecast_cutoff and consumers must filter on that, not on "
               "the artifact-level bound."),
        extra={"contract_version": CONTRACT_VERSION, "targets": list(TARGETS)})

    print(f"contract {CONTRACT_VERSION}")
    print(f"  rows {acct['rows']} | players {acct['players']} | games {acct['games']} "
          f"| dates {acct['dates']} | seasons {acct['seasons']}")
    for t in TARGETS:
        print(f"  eligible {t:30s} {acct['eligible__'+t]:6d}  "
              f"(excluded {acct['excluded__'+t]})")
    print(f"\nwrote {OUT/'universe.parquet'}, universe.csv, contract.json, manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
