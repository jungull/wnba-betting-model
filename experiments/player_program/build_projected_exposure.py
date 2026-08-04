#!/usr/bin/env python3
"""build_projected_exposure.py — producer for `projected_player_possessions_v1`.

Builds, from frozen inputs only:

  * ``team_possession_prior_v1.parquet``        — prior-games-only projected team possessions
  * ``projected_team_rotations_v1.parquet``     — team-game x regime allocation summary
  * ``projected_player_possessions_v1.parquet`` — per-player projected minutes and possessions
  * ``PROJECTED_EXPOSURE_RECEIPT.json``         — identities, hashes, counts, distributions

Registered before execution in ``arm_registry.jsonl`` as ``team_possession_prior_v1`` and
``projected_player_possessions_v1``. This module is the ONLY sanctioned producer of those
artifacts.

**Nothing here is fitted and nothing here is scored.** No realised minute, lineup, pace or
possession of a TARGET game is read. Realised possessions enter only as the history of STRICTLY
EARLIER games, which is the ordinary meaning of a prior-games-only estimate.

The producer FAILS CLOSED: every constraint is asserted before anything is written, and a failure
writes no artifact.

Run::

    python experiments/player_program/build_projected_exposure.py
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
OUT = HERE / "projected_exposure_v1"

CONTRACT = ROOT / "experiments/prediction_contract_v5/player_game_enriched.parquet"
POSS = ROOT / "experiments/player_program/possessions_v2/possessions_raw_v2.parquet"
PRED_DIR = ROOT / "experiments/cbs_v15_player_oof_v5/attempt_001"

# ---- frozen constants, all declared in the registration ------------------------- #
WINDOW_K = 10               # trailing games in the pace window
MIN_HISTORY_M = 3           # minimum qualifying games before a window level is used
REGULATION_MIN = 40.0       # WNBA regulation length
TEAM_MINUTES = 200.0        # 5 players x 40 minutes
PLAYER_MAX_MIN = 40.0
MICRO = 1_000_000           # micro-minutes per minute
TEAM_MICRO = int(TEAM_MINUTES * MICRO)
CAP_MICRO = int(PLAYER_MAX_MIN * MICRO)
MIN_VIABLE = 5              # fewer than five viable candidates -> unresolved

REGIMES = {
    "tier_a_only": ("A_primary",),
    "tier_a_plus_tx_b": ("A_primary", "B_transaction_sensitivity"),
    "tier_a_plus_tx_b_plus_s2": ("A_primary", "B_transaction_sensitivity", "B_s2_weak_fallback"),
}
PRIMARY_REGIME = "tier_a_only"

#: policy s2_weak_evidence_diagnostic/1, as corrected by
#: exposure_evidence__erratum_availability_vs_plausibility.
#:
#: EVIDENCE AVAILABILITY and FORECAST PLAUSIBILITY are different questions and are recorded
#: separately. A regime can be cutoff-available and still produce unusable rotations (S2); another
#: can be unavailable at the cutoff regardless of how its rotations look (transaction Tier B).
REGIME_EVIDENCE = {
    "tier_a_only": {
        "evidence_class": "primary",
        "roster_evidence_basis": "captured_asof",
        "information_available_at_cutoff": True,
        "historically_captured_asof": True,
        "operationally_plausible": True,
        "production_eligible": False,
    },
    "tier_a_plus_tx_b": {
        "evidence_class": "sensitivity_transaction",
        "roster_evidence_basis": "captured_asof + retrospective_effective_date",
        "information_available_at_cutoff": False,
        "historically_captured_asof": False,
        "operationally_plausible": False,
        "production_eligible": False,
    },
    "tier_a_plus_tx_b_plus_s2": {
        "evidence_class": "weak_diagnostic_s2",
        "roster_evidence_basis": "captured_asof + retrospective_effective_date + weak_prior_season",
        "information_available_at_cutoff": True,
        "historically_captured_asof": False,
        "operationally_plausible": False,
        "production_eligible": False,
    },
}

#: prose for the receipt only; not written per row
REGIME_EVIDENCE_REASONS = {
    "tier_a_only": {
        "information_available_at_cutoff": (
            "all 35,629 A_primary rows carry candidate_evidence_time, candidate_published_time and "
            "candidate_observed_time at or before the forecast cutoff; zero rows were observed "
            "after it"),
        "historically_captured_asof": "roster_evidence_regime == captured_asof on every row",
        "operationally_plausible": (
            "median effective rotation size 8.97, consistent with a real WNBA rotation"),
        "plausibility_limitation": (
            "MAXIMUM effective rotation size is 14.2, which EXCEEDS the 12-player standard active "
            "roster, and 994 of 2,914 allocated team-games name more candidates than that roster "
            "allows. The primary regime is plausible AT THE MEDIAN, not uniformly. This is a "
            "limitation of v1, not a blocker for the registered experiment, and it stays visible."),
        "production_eligible": (
            "research artifact only. Not promoted. Production eligibility requires downstream "
            "validation and explicit authorisation."),
    },
    "tier_a_plus_tx_b": {
        "information_available_at_cutoff": (
            "NO. All 4,169 B_transaction_sensitivity rows carry candidate_observed_time "
            "2026-07-30T17:42Z -- after every one of their cutoffs -- and candidate_published_time "
            "is null. The transaction evidence was retrospectively scraped, so it was not "
            "available at the historical decision time regardless of its backdated effective date."),
        "historically_captured_asof": "NO. src_asof_roster is null on every row.",
        "operationally_plausible": (
            "NO. 1,271 of 2,988 allocated team-games exceed the standard active roster, 225 show "
            "extreme scaling, and the maximum allocation reaches 44 players."),
        "production_eligible": "NO, on both grounds independently.",
    },
    "tier_a_plus_tx_b_plus_s2": {
        "information_available_at_cutoff": (
            "YES for the S2 component itself. All 5,053 B_s2_weak_fallback rows carry "
            "candidate_evidence_time and candidate_observed_time at season-start markers, and ZERO "
            "rows were observed after their cutoff. Prior-season affiliation was knowable at the "
            "decision time. The S2 SOURCE contains no retrospective contamination. NOTE: this "
            "regime is cumulative and also contains the transaction rows, which are not "
            "cutoff-available; the availability verdict here is about the S2 component."),
        "historically_captured_asof": (
            "NO. src_asof_roster and candidate_published_time are null; this is not a captured "
            "point-in-time roster feed, it is a derived prior-season affiliation."),
        "operationally_plausible": (
            "NO. Maximum 70 allocated players, maximum effective rotation size 67.8, and at the "
            "5th percentile only ONE player clears 10 projected minutes. This is not a rotation."),
        "production_eligible": "NO.",
        "correction": (
            "an earlier record labelled S2 non-achievable for the same reason as transaction "
            "Tier B. That was wrong. S2 is cutoff-AVAILABLE but operationally IMPLAUSIBLE; "
            "transaction Tier B is neither."),
    },
}

#: declared plausibility thresholds. Labels only -- neither changes a single allocated minute.
STANDARD_ACTIVE_ROSTER = 12          # WNBA standard maximum active roster
SCALE_BAND = (0.8, 1.25)             # reciprocal-symmetric: 1/1.25 == 0.8

#: contract columns that describe the TARGET game's outcome. None may reach the artifact.
OUTCOME_COLS = [
    "minutes", "pts", "fga", "appeared", "in_target_box",
    "outcome_scoreable__p_active", "outcome_scoreable__e_minutes_given_active",
    "outcome_scoreable__attempts_usage", "outcome_scoreable__player_scoring_distribution",
    "p_active_unscoreable_reason", "appearances_exceed_obligations",
    # derived from which club holds the target box row -> outcome information
    "team_assignment_ambiguity_state",
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _sha_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class ProducerFailure(RuntimeError):
    """Raised on any constraint violation. Nothing is written."""


# --------------------------------------------------------------------------- #
# inputs
# --------------------------------------------------------------------------- #
def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    contract = pd.read_parquet(CONTRACT)

    pa = pd.concat(
        [pd.read_parquet(f, columns=["row_uid", "pred_point", "is_fallback", "fallback_level",
                                     "model_hash", "config_hash", "data_snapshot_hash"])
         for f in sorted(PRED_DIR.glob("predictions__p_active__*.parquet"))],
        ignore_index=True)
    em = pd.concat(
        [pd.read_parquet(f, columns=["row_uid", "pred_point", "is_fallback", "fallback_level",
                                     "model_hash", "config_hash", "data_snapshot_hash"])
         for f in sorted(PRED_DIR.glob("predictions__e_minutes_given_active__*.parquet"))],
        ignore_index=True)

    for name, df in (("p_active", pa), ("e_minutes_given_active", em)):
        if df["row_uid"].duplicated().any():
            raise ProducerFailure(f"{name}: duplicate row_uid in the v15 predictions")
        if df["pred_point"].isna().any():
            raise ProducerFailure(f"{name}: null pred_point in the v15 predictions")

    hashes = {
        "p_active": {k: sorted(pa[k].unique().tolist())
                     for k in ("model_hash", "config_hash", "data_snapshot_hash")},
        "e_minutes_given_active": {k: sorted(em[k].unique().tolist())
                                   for k in ("model_hash", "config_hash", "data_snapshot_hash")},
    }

    pa = pa.rename(columns={"pred_point": "p_active",
                            "is_fallback": "p_active_is_fallback",
                            "fallback_level": "p_active_fallback_level"})
    em = em.rename(columns={"pred_point": "e_minutes_given_active",
                            "is_fallback": "e_min_is_fallback",
                            "fallback_level": "e_min_fallback_level"})

    keep = ["row_uid", "obligation_uid", "game_id", "team_id", "player_id", "game_date", "season",
            "forecast_cutoff", "fold_id", "universe_tier", "evaluation_tier", "candidate_source",
            "team_assignment_source", "team_assignment_confidence", "roster_evidence_regime",
            "cutoff_source", "cutoff_policy", "is_cold_start", "contract_version",
            "n_teams_claiming_this_player_game", "n_prior_appearances", "n_prior_team_games"]
    missing = [c for c in keep if c not in contract.columns]
    if missing:
        raise ProducerFailure(f"contract is missing expected columns: {missing}")

    base = contract[keep].copy()
    base = base.merge(pa[["row_uid", "p_active", "p_active_is_fallback", "p_active_fallback_level"]],
                      on="row_uid", how="left", validate="1:1")
    base = base.merge(em[["row_uid", "e_minutes_given_active", "e_min_is_fallback",
                          "e_min_fallback_level"]],
                      on="row_uid", how="left", validate="1:1")
    if base[["p_active", "e_minutes_given_active"]].isna().any().any():
        raise ProducerFailure("a contract obligation has no v15 prediction bound to it")

    base["candidate_claimed_by_multiple_teams"] = base["n_teams_claiming_this_player_game"] > 1
    base = base.drop(columns=["n_teams_claiming_this_player_game"])
    base["raw_expected_minutes"] = base["p_active"] * base["e_minutes_given_active"]
    base["pred_is_fallback"] = base["p_active_is_fallback"] | base["e_min_is_fallback"]

    return base, contract, hashes


# --------------------------------------------------------------------------- #
# pace: team_possession_prior/1
# --------------------------------------------------------------------------- #
def build_pace(base: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (per-game realised pace frame, per-team-game projected pace frame)."""
    p = pd.read_parquet(POSS, columns=["game_id", "season_type", "period", "offense_team_id"])

    n_off = (p.groupby(["game_id", "offense_team_id"]).size()
             .rename("n_off_poss").reset_index()
             .rename(columns={"offense_team_id": "team_id"}))
    gmeta = (p.groupby("game_id")
             .agg(max_period=("period", "max"), season_type=("season_type", "first"))
             .reset_index())
    gmeta["game_minutes"] = REGULATION_MIN + 5.0 * np.maximum(0, gmeta["max_period"] - 4)

    n_off = n_off.merge(gmeta[["game_id", "game_minutes"]], on="game_id", how="left",
                        validate="m:1")
    n_off["reg_equiv_off_poss"] = n_off["n_off_poss"] * REGULATION_MIN / n_off["game_minutes"]

    # pace is a property of the GAME: the mean of the two sides' regulation-equivalent counts
    gpace = (n_off.groupby("game_id")["reg_equiv_off_poss"].mean()
             .rename("game_pace").reset_index())

    # schedule identities, from the contract (canonical), not from the possession stream
    sched = (base[["game_id", "team_id", "game_date", "season"]]
             .drop_duplicates(["game_id", "team_id"]).reset_index(drop=True))
    G = (sched[["game_id", "game_date", "season"]].drop_duplicates("game_id")
         .merge(gpace, on="game_id", how="left", validate="1:1")
         .merge(gmeta[["game_id", "season_type", "max_period"]], on="game_id", how="left",
                validate="1:1"))
    if G["game_pace"].isna().any():
        raise ProducerFailure("a contract game has no realised possession record")
    G = G.sort_values(["game_date", "game_id"]).reset_index(drop=True)

    # league mean of game_pace over all games on STRICTLY EARLIER dates
    by_date = G.groupby("game_date")["game_pace"].agg(["sum", "count"]).sort_index()
    league_prior_mean = (by_date["sum"].cumsum().shift(1) /
                         by_date["count"].cumsum().shift(1))
    league_prior_n = by_date["count"].cumsum().shift(1)

    TG = sched.merge(G[["game_id", "game_pace", "season_type"]], on="game_id", how="left",
                     validate="m:1")
    TG = TG.sort_values(["team_id", "game_date", "game_id"]).reset_index(drop=True)

    # per-team chronological history of game_pace
    hist: dict[int, list[tuple[pd.Timestamp, int, float]]] = {}
    for t, sub in TG.groupby("team_id", sort=True):
        hist[t] = list(zip(sub["game_date"], sub["season"], sub["game_pace"]))

    rows = []
    for r in TG.itertuples(index=False):
        h = hist[r.team_id]
        same = [v for (d, s, v) in h if d < r.game_date and s == r.season]
        prev = [v for (d, s, v) in h if d < r.game_date and s == r.season - 1]
        if len(same) >= MIN_HISTORY_M:
            level, src, vals = 1, "team_window_same_season", same[-WINDOW_K:]
            est, n_hist = float(np.mean(vals)), len(vals)
        elif len(prev) >= MIN_HISTORY_M:
            level, src, vals = 2, "team_window_prior_season", prev[-WINDOW_K:]
            est, n_hist = float(np.mean(vals)), len(vals)
        else:
            lm = league_prior_mean.get(r.game_date, np.nan)
            ln = league_prior_n.get(r.game_date, np.nan)
            if pd.notna(lm):
                level, src = 3, "league_prior_all"
                est, n_hist = float(lm), int(ln)
            else:
                level, src = 4, "unresolved_no_prior_games"
                est, n_hist = np.nan, 0
        rows.append((r.game_id, r.team_id, r.game_date, r.season, r.season_type,
                     level, src, n_hist, est))

    P = pd.DataFrame(rows, columns=["game_id", "team_id", "game_date", "season", "season_type",
                                    "pace_level", "pace_source", "n_history_games",
                                    "team_pace_estimate"])

    # the GAME's projected possessions: the mean of the two sides' estimates; unresolved if
    # either side is unresolved
    # NB: size(), not count() -- count() drops NaN and would hide an unresolved side
    agg = P.groupby("game_id")["team_pace_estimate"].agg(
        game_est_mean="mean", n_sides="size", n_unresolved=lambda s: s.isna().sum())
    if (agg["n_sides"] != 2).any():
        raise ProducerFailure("a game does not have exactly two team-games")
    agg["projected_team_off_possessions"] = np.where(
        agg["n_unresolved"] > 0, np.nan, agg["game_est_mean"])
    P = P.merge(agg[["projected_team_off_possessions"]], on="game_id", how="left", validate="m:1")
    P["pace_resolved"] = P["projected_team_off_possessions"].notna()
    return G, P


# --------------------------------------------------------------------------- #
# allocation
# --------------------------------------------------------------------------- #
def allocate(raw: np.ndarray, uids: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Capped-proportional water-filling, settled in integer micro-minutes.

    Returns (micro_minutes int64, was_capped bool). Deterministic: capping order follows the
    values themselves and the largest-remainder settlement breaks ties on ascending row_uid.
    """
    n = len(raw)
    capped = np.zeros(n, dtype=bool)
    alloc = np.zeros(n, dtype=float)

    while True:
        free = ~capped
        remaining = TEAM_MINUTES - PLAYER_MAX_MIN * capped.sum()
        if not free.any():
            break
        s = raw[free].sum()
        if s <= 0:
            raise ProducerFailure("non-positive raw mass among viable candidates")
        alloc[free] = raw[free] * (remaining / s)
        over = free & (alloc > PLAYER_MAX_MIN + 1e-12)
        if not over.any():
            break
        capped |= over
        alloc[over] = PLAYER_MAX_MIN

    # integer settlement, largest remainder, ties on ascending row_uid
    exact = alloc * MICRO
    floor = np.floor(exact).astype(np.int64)
    floor = np.minimum(floor, CAP_MICRO)
    deficit = TEAM_MICRO - int(floor.sum())
    if deficit < 0:
        raise ProducerFailure("integer settlement overshot the team minute total")
    if deficit > 0:
        frac = exact - np.floor(exact)
        headroom = CAP_MICRO - floor
        order = np.lexsort((uids, -frac))          # primary -frac desc, secondary uid asc
        for i in order:
            if deficit == 0:
                break
            take = min(deficit, int(headroom[i]))
            floor[i] += take
            deficit -= take
        if deficit != 0:
            raise ProducerFailure("integer settlement could not place the full team minute total")
    return floor, capped


def rotation_diagnostics(minutes: np.ndarray, scale_factor: float) -> dict:
    """Declared plausibility diagnostics for one allocated team-game x regime.

    Every field here is a LABEL. None of them feeds back into the allocation: the minutes are
    identical whether or not these are computed. Reported for EVERY regime so the primary is not
    exempt from its own test.
    """
    n = int(len(minutes))
    share = minutes / TEAM_MINUTES
    ssq = float(np.sum(share ** 2))
    top = np.sort(minutes)[::-1]
    over_roster = n > STANDARD_ACTIVE_ROSTER
    extreme = not (SCALE_BAND[0] <= scale_factor <= SCALE_BAND[1])
    if over_roster and extreme:
        plaus = "degraded_both"
    elif over_roster:
        plaus = "degraded_roster_cardinality"
    elif extreme:
        plaus = "degraded_extreme_scaling"
    else:
        plaus = "plausible"
    return {
        "n_players_ge_10_min": int((minutes >= 10.0).sum()),
        "n_players_ge_20_min": int((minutes >= 20.0).sum()),
        "effective_rotation_size": float(1.0 / ssq) if ssq > 0 else float("nan"),
        "top5_minute_share": float(top[:5].sum() / TEAM_MINUTES),
        "max_player_minutes": float(minutes.max()),
        "min_player_minutes": float(minutes.min()),
        "exceeds_standard_active_roster": bool(over_roster),
        "extreme_scaling": bool(extreme),
        "rotation_plausibility": plaus,
    }


def build_allocations(base: pd.DataFrame, P: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    pace_by_tg = P.set_index(["game_id", "team_id"])
    # opponent identity and each side's projected possessions
    sides = P[["game_id", "team_id", "projected_team_off_possessions", "pace_level",
               "pace_source"]].copy()
    opp = sides.rename(columns={
        "team_id": "opp_team_id",
        "projected_team_off_possessions": "projected_opp_off_possessions",
        "pace_level": "opp_pace_level", "pace_source": "opp_pace_source"})
    pair = sides.merge(opp, on="game_id")
    pair = pair[pair["team_id"] != pair["opp_team_id"]].reset_index(drop=True)
    if len(pair) != len(sides):
        raise ProducerFailure("opponent pairing did not produce exactly one opponent per team-game")

    player_rows, team_rows = [], []
    grouped = {k: v for k, v in base.groupby(["game_id", "team_id"], sort=True)}

    for r in pair.itertuples(index=False):
        key = (r.game_id, r.team_id)
        sub_all = grouped.get(key)
        if sub_all is None:
            raise ProducerFailure(f"no contract rows for team-game {key}")
        meta = pace_by_tg.loc[key]

        for regime, tiers in REGIMES.items():
            sub = sub_all[sub_all["evaluation_tier"].isin(tiers)]
            sub = sub.sort_values("row_uid").reset_index(drop=True)
            n_cand = len(sub)
            viable_mask = sub["raw_expected_minutes"].to_numpy() > 0
            n_viable = int(viable_mask.sum())

            common = dict(
                game_id=r.game_id, team_id=r.team_id, opp_team_id=r.opp_team_id,
                game_date=meta["game_date"], season=meta["season"],
                season_type=meta["season_type"], regime=regime,
                n_candidates=n_cand, n_viable=n_viable,
                pace_level=int(meta["pace_level"]), pace_source=meta["pace_source"],
                n_pace_history_games=int(meta["n_history_games"]),
                projected_team_off_possessions=r.projected_team_off_possessions,
                projected_opp_off_possessions=r.projected_opp_off_possessions,
                **REGIME_EVIDENCE[regime],
            )
            _na_diag = {k: (np.nan if not isinstance(v, (bool, str)) else
                            (False if isinstance(v, bool) else "unresolved"))
                        for k, v in rotation_diagnostics(np.array([1.0]), 1.0).items()}

            if n_viable < MIN_VIABLE:
                team_rows.append({**common, **_na_diag,
                                  "status": "unresolved_insufficient_candidates",
                                  "n_allocated": 0, "n_capped": 0,
                                  "sum_raw_expected_minutes": float(
                                      sub["raw_expected_minutes"].sum()),
                                  "scale_factor": np.nan, "redistributed_minutes": np.nan,
                                  "projected_minutes_sum": np.nan,
                                  "projected_minutes_micro_sum": 0,
                                  "n_fallback_predictions": int(sub["pred_is_fallback"].sum()),
                                  "n_ambiguous_candidates": int(
                                      sub["candidate_claimed_by_multiple_teams"].sum())})
                continue

            v = sub[viable_mask].reset_index(drop=True)
            raw = v["raw_expected_minutes"].to_numpy(dtype=float)
            uids = v["row_uid"].to_numpy()
            uid_rank = np.argsort(np.argsort(uids)).astype(np.int64)
            micro, capped = allocate(raw, uid_rank)
            minutes = micro / MICRO
            raw_sum = float(raw.sum())

            pace_ok = pd.notna(r.projected_team_off_possessions)
            if pace_ok:
                off = r.projected_team_off_possessions * (minutes / REGULATION_MIN)
                dfn = r.projected_opp_off_possessions * (minutes / REGULATION_MIN)
                status = "normal"
            else:
                off = np.full(len(minutes), np.nan)
                dfn = np.full(len(minutes), np.nan)
                status = "minutes_only_no_pace"

            out = v.copy()
            out["regime"] = regime
            out["opp_team_id"] = r.opp_team_id
            out["season_type"] = meta["season_type"]
            out["projected_minutes"] = minutes
            out["projected_minutes_micro"] = micro
            out["was_capped"] = capped
            out["projected_off_possessions"] = off
            out["projected_def_possessions"] = dfn
            out["projected_team_off_possessions"] = r.projected_team_off_possessions
            out["projected_opp_off_possessions"] = r.projected_opp_off_possessions
            out["pace_level"] = int(meta["pace_level"])
            out["pace_source"] = meta["pace_source"]
            out["opp_pace_level"] = int(r.opp_pace_level)
            out["opp_pace_source"] = r.opp_pace_source
            out["team_game_status"] = status
            for _k, _v in REGIME_EVIDENCE[regime].items():
                out[_k] = _v
            player_rows.append(out)

            scale = TEAM_MINUTES / raw_sum if raw_sum > 0 else np.nan
            team_rows.append({**common, **rotation_diagnostics(minutes, scale),
                              "status": status,
                              "n_allocated": int(len(v)), "n_capped": int(capped.sum()),
                              "sum_raw_expected_minutes": raw_sum,
                              "scale_factor": scale,
                              "redistributed_minutes": TEAM_MINUTES - raw_sum,
                              "projected_minutes_sum": float(minutes.sum()),
                              "projected_minutes_micro_sum": int(micro.sum()),
                              "n_fallback_predictions": int(v["pred_is_fallback"].sum()),
                              "n_ambiguous_candidates": int(
                                  v["candidate_claimed_by_multiple_teams"].sum())})

    players = pd.concat(player_rows, ignore_index=True)
    teams = pd.DataFrame(team_rows)
    return players, teams


# --------------------------------------------------------------------------- #
# fail-closed checks
# --------------------------------------------------------------------------- #
def assert_producer_invariants(players: pd.DataFrame, teams: pd.DataFrame) -> None:
    leaked = [c for c in OUTCOME_COLS if c in players.columns or c in teams.columns]
    if leaked:
        raise ProducerFailure(f"outcome columns reached the artifact: {leaked}")

    ok = teams[teams["status"].isin(("normal", "minutes_only_no_pace"))]
    bad = ok[ok["projected_minutes_micro_sum"] != TEAM_MICRO]
    if len(bad):
        raise ProducerFailure(f"{len(bad)} allocated team-games do not sum to exactly 200 minutes")

    if (players["projected_minutes"] < 0).any():
        raise ProducerFailure("negative projected minutes")
    if (players["projected_minutes_micro"] > CAP_MICRO).any():
        raise ProducerFailure("a player exceeds the 40 minute cap")

    if players.duplicated(["game_id", "team_id", "player_id", "regime"]).any():
        raise ProducerFailure("duplicate player-team obligation within a regime")

    # every allocated player belongs to the team-game they were allocated to
    if (players["team_id"] == players["opp_team_id"]).any():
        raise ProducerFailure("a player was assigned to its own opponent")

    res = players[players["team_game_status"] == "normal"]
    for col, tgt in (("projected_off_possessions", "projected_team_off_possessions"),
                     ("projected_def_possessions", "projected_opp_off_possessions")):
        g = res.groupby(["game_id", "team_id", "regime"]).agg(
            got=(col, "sum"), want=(tgt, "first"))
        err = (g["got"] - 5.0 * g["want"]).abs()
        tol = 1e-9 * np.maximum(1.0, 5.0 * g["want"].abs())
        if (err > tol).any():
            raise ProducerFailure(
                f"{int((err > tol).sum())} team-games violate the {col} mass constraint")

    # home/away reconciliation: team A's defensive mass equals team B's offensive mass
    for regime in REGIMES:
        sub = res[res["regime"] == regime]
        tg = sub.groupby(["game_id", "team_id"]).agg(
            off=("projected_off_possessions", "sum"), dfn=("projected_def_possessions", "sum"))
        tg = tg.reset_index()
        m = tg.merge(tg, on="game_id", suffixes=("_a", "_b"))
        m = m[m["team_id_a"] != m["team_id_b"]]
        d = (m["dfn_a"] - m["off_b"]).abs()
        if len(d) and (d > 1e-9 * np.maximum(1.0, m["off_b"].abs())).any():
            raise ProducerFailure(f"{regime}: home/away possession accounting does not reconcile")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def build_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
                            pd.DataFrame, pd.DataFrame, dict]:
    """Load -> pace -> allocate -> assert. Writes nothing.

    The validator calls this with the module's input paths patched to perturbed copies, so the
    perturbation tests exercise the REAL producer rather than a re-implementation of it.
    """
    base, contract, pred_hashes = load_inputs()
    G, P = build_pace(base)
    players, teams = build_allocations(base, P)
    assert_producer_invariants(players, teams)
    return base, contract, G, P, players, teams, pred_hashes


def _sorted_outputs(P: pd.DataFrame, players: pd.DataFrame,
                    teams: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pace_out = P[["game_id", "team_id", "game_date", "season", "season_type", "pace_level",
                  "pace_source", "n_history_games", "team_pace_estimate",
                  "projected_team_off_possessions", "pace_resolved"]].copy()
    pace_out = pace_out.sort_values(["game_date", "game_id", "team_id"]).reset_index(drop=True)
    players = players.sort_values(["game_date", "game_id", "team_id", "regime", "row_uid"]
                                  ).reset_index(drop=True)
    teams = teams.sort_values(["game_date", "game_id", "team_id", "regime"]).reset_index(drop=True)
    return pace_out, players, teams


def main() -> int:
    started = _utc()
    producer_sha_before = _sha(Path(__file__))

    base, contract, G, P, players, teams, pred_hashes = build_frames()

    producer_sha_after = _sha(Path(__file__))
    if producer_sha_before != producer_sha_after:
        raise ProducerFailure("the producer changed while it was running")

    OUT.mkdir(parents=True, exist_ok=True)

    pace_out, players, teams = _sorted_outputs(P, players, teams)

    pace_out.to_parquet(OUT / "team_possession_prior_v1.parquet", index=False)
    teams.to_parquet(OUT / "projected_team_rotations_v1.parquet", index=False)
    players.to_parquet(OUT / "projected_player_possessions_v1.parquet", index=False)

    cfg = {
        "WINDOW_K": WINDOW_K, "MIN_HISTORY_M": MIN_HISTORY_M,
        "REGULATION_MIN": REGULATION_MIN, "TEAM_MINUTES": TEAM_MINUTES,
        "PLAYER_MAX_MIN": PLAYER_MAX_MIN, "MICRO": MICRO, "MIN_VIABLE": MIN_VIABLE,
        "REGIMES": {k: list(v) for k, v in REGIMES.items()},
        "REGIME_EVIDENCE": REGIME_EVIDENCE,
        "STANDARD_ACTIVE_ROSTER": STANDARD_ACTIVE_ROSTER,
        "SCALE_BAND": list(SCALE_BAND),
    }
    config_hash = _sha_str(json.dumps(cfg, sort_keys=True))

    def _dist(s: pd.Series) -> dict:
        s = s.dropna()
        if not len(s):
            return {}
        q = s.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
        return {"n": int(len(s)), "mean": round(float(s.mean()), 6),
                "min": round(float(s.min()), 6), "max": round(float(s.max()), 6),
                "p05": round(float(q.loc[0.05]), 6), "p25": round(float(q.loc[0.25]), 6),
                "p50": round(float(q.loc[0.50]), 6), "p75": round(float(q.loc[0.75]), 6),
                "p95": round(float(q.loc[0.95]), 6)}

    prim = teams[teams["regime"] == PRIMARY_REGIME]
    pl_prim = players[players["regime"] == PRIMARY_REGIME]

    def _regime_block(regime: str) -> dict:
        t = teams[teams["regime"] == regime]
        p = players[players["regime"] == regime]
        norm = t[t["status"] == "normal"]
        fb = norm[(norm["pace_level"] > 1) | (norm["n_fallback_predictions"] > 0)]
        alloc = t[t["status"].isin(("normal", "minutes_only_no_pace"))]
        cnt = (alloc.groupby("game_id").size()
               .reindex(sorted(teams["game_id"].unique()), fill_value=0))
        contract_rows = int(contract["evaluation_tier"].isin(REGIMES[regime]).sum())
        stranded = int(t.loc[t["status"] == "unresolved_insufficient_candidates",
                             "n_candidates"].sum())
        nn = p[p["team_game_status"] == "normal"].groupby("game_id")["team_id"].nunique()
        return {
            "team_games": int(len(t)),
            "evidence": REGIME_EVIDENCE[regime],
            "evidence_reasons": REGIME_EVIDENCE_REASONS[regime],
            "reconciliation": {
                "team_game_rows": int(len(t)),
                "allocated_rows": int(len(alloc)),
                "unresolved_rows": int(len(t) - len(alloc)),
                "complete_two_team_games": int((cnt == 2).sum()),
                "one_sided_games": int((cnt == 1).sum()),
                "zero_sided_games": int((cnt == 0).sum()),
                "player_obligations_allocated": int(len(p)),
                "player_obligations_stranded": stranded,
                "player_obligations_total": contract_rows,
                "games_with_both_clubs_normal": int((nn == 2).sum()),
                "directed_possession_reconciliation_checks": int((nn == 2).sum()) * 2,
                "identities": [
                    "allocated_rows + unresolved_rows == team_game_rows",
                    "2*complete_two_team_games + one_sided_games == allocated_rows",
                    "complete_two_team_games + one_sided_games + zero_sided_games == games",
                    "player_obligations_allocated + player_obligations_stranded "
                    "== player_obligations_total",
                ],
            },
            "status_counts": t["status"].value_counts().to_dict(),
            "rotation_plausibility_counts": t["rotation_plausibility"].value_counts().to_dict(),
            "plausibility_diagnostics_over_allocated_team_games": {
                "allocated_team_games": int(len(alloc)),
                "exceeds_standard_active_roster": int(alloc["exceeds_standard_active_roster"].sum()),
                "extreme_scaling": int(alloc["extreme_scaling"].sum()),
                "standard_active_roster_threshold": STANDARD_ACTIVE_ROSTER,
                "scale_band": list(SCALE_BAND),
                "n_allocated": _dist(alloc["n_allocated"]),
                "effective_rotation_size": _dist(alloc["effective_rotation_size"]),
                "n_players_ge_10_min": _dist(alloc["n_players_ge_10_min"]),
                "n_players_ge_20_min": _dist(alloc["n_players_ge_20_min"]),
                "top5_minute_share": _dist(alloc["top5_minute_share"]),
                "max_player_minutes": _dist(alloc["max_player_minutes"]),
                "min_player_minutes": _dist(alloc["min_player_minutes"]),
            },
            "normal_no_fallback": int(len(norm) - len(fb)),
            "fallback": int(len(fb)),
            "unresolved": int((t["status"] == "unresolved_insufficient_candidates").sum()),
            "minutes_only_no_pace": int((t["status"] == "minutes_only_no_pace").sum()),
            "player_rows": int(len(p)),
            "allocated_players_per_team_game": _dist(t.loc[t["n_allocated"] > 0, "n_allocated"]),
            "projected_minutes": _dist(p["projected_minutes"]),
            "n_capped_players": int(p["was_capped"].sum()),
            "scale_factor": _dist(t["scale_factor"]),
            "redistributed_minutes": _dist(t["redistributed_minutes"]),
            "ambiguous_candidate_rows": int(p["candidate_claimed_by_multiple_teams"].sum()),
            "rows_by_season": p.groupby("season").size().to_dict(),
            "games_by_season": p.groupby("season")["game_id"].nunique().to_dict(),
        }

    receipt = {
        "schema": "projected_exposure_receipt/1",
        "artifact_id": "projected_player_possessions/1",
        "pace_artifact_id": "team_possession_prior/1",
        "registered_arms": ["projected_player_possessions_v1", "team_possession_prior_v1"],
        "registry": "experiments/player_program/arm_registry.jsonl",
        "generated_utc": started,
        "finished_utc": _utc(),
        "nothing_fitted": True,
        "nothing_scored": True,
        "producer": {
            "path": "experiments/player_program/build_projected_exposure.py",
            "sha256_before": producer_sha_before,
            "sha256_after": producer_sha_after,
        },
        "config": cfg,
        "config_hash": config_hash,
        "inputs": {
            "contract_v5": {"path": str(CONTRACT.relative_to(ROOT)).replace("\\", "/"),
                            "sha256": _sha(CONTRACT), "rows": int(len(contract))},
            "possessions": {"path": str(POSS.relative_to(ROOT)).replace("\\", "/"),
                            "sha256": _sha(POSS), "artifact_id": "player_possessions/2",
                            "role": "REALISED possessions of STRICTLY EARLIER games only"},
            "v15_predictions": {"dir": str(PRED_DIR.relative_to(ROOT)).replace("\\", "/"),
                                "hashes": pred_hashes},
        },
        "universe": {
            "contract_obligations": int(len(contract)),
            "games": int(base["game_id"].nunique()),
            "team_games": int(base.groupby(["game_id", "team_id"]).ngroups),
            "rows_by_season": base.groupby("season").size().to_dict(),
            "games_by_season": base.groupby("season")["game_id"].nunique().to_dict(),
            "team_games_by_season_type": pace_out.groupby("season_type").size().to_dict(),
        },
        "pace": {
            "level_counts": pace_out["pace_level"].value_counts().sort_index().to_dict(),
            "source_counts": pace_out["pace_source"].value_counts().to_dict(),
            "resolved_team_games": int(pace_out["pace_resolved"].sum()),
            "unresolved_team_games": int((~pace_out["pace_resolved"]).sum()),
            "unresolved_games": sorted(
                pace_out.loc[~pace_out["pace_resolved"], "game_id"].unique().tolist()),
            "projected_team_off_possessions": _dist(pace_out["projected_team_off_possessions"]),
            "realised_game_pace_for_reference": _dist(G["game_pace"]),
            "overtime_games_normalised": int((G["max_period"] > 4).sum()),
        },
        "regimes": {r: _regime_block(r) for r in REGIMES},
        "primary_regime": PRIMARY_REGIME,
        "possession_accounting": {
            "rule_off": "sum(player_off) == 5 * projected_team_off_possessions",
            "rule_def": "sum(player_def) == 5 * projected_opp_off_possessions",
            "checked_in_producer": True,
            "off_equals_def_by_construction": True,
            "why": ("the pace estimate is symmetric, so a player's projected offensive and "
                    "defensive possessions are equal. Disclosed in the registration."),
        },
        "tier_b_historical_observation_influence": {
            "policy": "tier_a_target_fit_with_observed_history/1",
            "statement": ("Tier B rows contribute no Tier B target loss, but realised Tier B games "
                          "can influence later Tier A history features once those games occur. "
                          "That influence is already inside the bound v15 predictions and is "
                          "therefore inherited by this artifact unchanged."),
            "tier_b_rows_in_universe": int((contract["universe_tier"] == "B").sum()),
        },
        "outputs": {
            "team_possession_prior_v1.parquet": {
                "rows": int(len(pace_out)),
                "sha256": _sha(OUT / "team_possession_prior_v1.parquet")},
            "projected_team_rotations_v1.parquet": {
                "rows": int(len(teams)),
                "sha256": _sha(OUT / "projected_team_rotations_v1.parquet")},
            "projected_player_possessions_v1.parquet": {
                "rows": int(len(players)),
                "sha256": _sha(OUT / "projected_player_possessions_v1.parquet")},
        },
        "primary_regime_headline": {
            "team_games": int(len(prim)),
            "player_rows": int(len(pl_prim)),
            "status_counts": prim["status"].value_counts().to_dict(),
        },
    }
    (OUT / "PROJECTED_EXPOSURE_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, default=str), encoding="utf-8")

    print(f"players : {len(players):>7,} rows -> {OUT / 'projected_player_possessions_v1.parquet'}")
    print(f"teams   : {len(teams):>7,} rows -> {OUT / 'projected_team_rotations_v1.parquet'}")
    print(f"pace    : {len(pace_out):>7,} rows -> {OUT / 'team_possession_prior_v1.parquet'}")
    print(f"receipt : {OUT / 'PROJECTED_EXPOSURE_RECEIPT.json'}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ProducerFailure as exc:
        print(f"PRODUCER FAILED CLOSED: {exc}", file=sys.stderr)
        sys.exit(2)
