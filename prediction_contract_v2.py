#!/usr/bin/env python3
"""prediction_contract_v2.py -- the pregame-selected player-game prediction contract.

Registered: prediction_contract_v2.  SUPERSEDES prediction_contract.py (v1), which is
preserved as a superseded artifact and MUST NOT be consumed.

WHAT WAS WRONG WITH v1, conceded in full
    D1 THE UNIVERSE WAS POSTGAME-SELECTED.  v1 began from master_player rows FOR THE TARGET
       GAME.  STATED PRECISELY (an earlier draft of this note overstated it): v1 DID include
       recorded DNPs -- about 5,390 rows, an active rate near 84%, NOT ~100% -- so the defect
       is not that everyone in the universe had appeared.  The defect is that MEMBERSHIP was
       selected using postgame knowledge: a player absent from the target box never entered
       the universe at all.  The target-game boxscore cannot define a pregame candidate
       roster.
    D2 OBLIGATION WAS CONFLATED WITH SCORING.  v1 required E[minutes|active] only for players
       who appeared, so an arm could buy perfect coverage by dropping everyone later inactive.
    D3 THE CUTOFF WAS FABRICATED.  game_date + 22:30 UTC labelled "T-90m" assumes every game
       tips at 00:00 UTC.  Measured: 199 of 784 games with known tips start 15:00-22:00 UTC,
       so v1's cutoff fell AFTER TIP for those -- leakage, not conservatism.
    D4 TEAM ROWS WERE DUPLICATED per player, weighting teams by roster size.

THE CENTRAL INVARIANT OF v2
    Deleting every target-game player row before constructing the candidate roster MUST NOT
    change which candidates the contract says were forecastable for that game.  The roster is
    built only from strictly-prior team games; target-game rows are joined afterwards, as
    LABELS, and never as membership.

WHAT THIS UNIVERSE IS, honestly named
    A RECENCY-ROSTER PROXY.  Exact historical rosters, transactions and inactive lists are not
    reconstructable for every season from what the project holds, so candidacy is inferred
    from appearance in the team's previous ROSTER_LOOKBACK games.  It is NOT the complete
    slate and is not described as one.  Known biases, recorded rather than assumed away:
      * a player who missed the whole lookback window is not a candidate even if rostered;
      * a debut or new signing with no prior appearance cannot be a candidate at all;
      * conversely, rows v2 has that v1 lacked are ADDITIONAL PROXY CANDIDATES, not players
        v1 "should have predicted" -- some were traded, waived or otherwise no longer
        rostered by the target game.
    Consequently the appearance rate below is the rate WITHIN THIS PROXY UNIVERSE, and is not
    the WNBA's player-availability rate.
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

OUT = REPO / "experiments" / "prediction_contract_v2"
MASTER = REPO / "data" / "masters" / "master_player.parquet"
PROPS_HIST = REPO / "data" / "props_capture" / "historical" / "master_props_historical.csv"
ODDS_EXT = REPO / "data" / "odds_capture" / "master_odds_extension.csv"

CONTRACT_VERSION = "player_game_contract/2"
ROSTER_LOOKBACK = 5          # team games looked back to establish candidacy
CUTOFF_MINUTES_BEFORE_TIP = 90

#: Cutoff policies.  These are NOT interchangeable and the names are load-bearing.
POLICY_EXACT = "exact_tip_T-90m"
POLICY_DATE_ONLY = "date_only_prior_day_cutoff"


@dataclass(frozen=True)
class Target:
    key: str
    description: str
    prediction_required: str      # WHO the arm must predict for
    outcome_scoreable: str        # WHERE the label supports scoring
    uncertainty: str
    clustering: str
    table: str                    # which canonical table the target lives on


TARGETS: dict[str, Target] = {
    "p_active": Target(
        "p_active", "Probability the candidate appears in the game.",
        "every candidate_at_cutoff", "every candidate_at_cutoff",
        "the probability IS the uncertainty; calibration is scored", "game_date", "player_game"),
    "e_minutes_given_active": Target(
        "e_minutes_given_active", "Expected minutes CONDITIONAL on appearing.",
        "EVERY candidate_at_cutoff, including eventual DNPs -- at the cutoff we do not know "
        "who appears, and E[minutes] = P(active) x E[minutes|active] needs the conditional "
        "term for everyone",
        "only rows where the player appeared (minutes > 0)",
        "predictive sd of minutes, strictly > 0", "game_date", "player_game"),
    "attempts_usage": Target(
        "attempts_usage", "Field-goal attempts conditional on appearing.",
        "every candidate_at_cutoff", "only rows where the player appeared and fga is resolved",
        "predictive sd of attempts, strictly > 0", "game_date", "player_game"),
    "player_scoring_distribution": Target(
        "player_scoring_distribution", "Predictive distribution of player points, conditional "
        "on appearing.",
        "every candidate_at_cutoff",
        "only rows where the player appeared and pts is resolved",
        "predictive sd PLUS the named quantiles", "game_date", "player_game"),
    "team_game_distribution": Target(
        "team_game_distribution", "Team points distribution.",
        "every team-game row", "every team-game row with a resolved final score",
        "predictive sd of team points", "game_date", "team_game"),
}

QUANTILES = [0.05, 0.25, 0.50, 0.75, 0.95]

PREDICTION_SCHEMA: dict[str, str] = {
    "row_uid": "pg_/tg_/g_ id from this module; the join key",
    "target_key": "one of TARGETS",
    "arm_id": "stable arm name",
    "fold_id": "exact OOF fold identity; must match the contract fold map",
    "forecast_cutoff": "tz-aware ISO8601, from the row's cutoff policy",
    "pred_point": "point prediction on the target's support",
    "pred_sd": "predictive sd; > 0 except where the target says otherwise",
    "pred_q05": "5th percentile (distribution targets; else null)",
    "pred_q25": "25th percentile", "pred_q50": "median",
    "pred_q75": "75th percentile", "pred_q95": "95th percentile",
    "is_fallback": "bool: a fallback path produced this",
    "is_cold_start": "bool: insufficient prior history at this cutoff",
    "n_prior_games": "int: strictly-prior appearances readable at the cutoff",
    "feature_asof": "tz-aware ISO8601; MUST be strictly < forecast_cutoff",
    "model_hash": "hash of fitted parameters",
    "config_hash": "hash of the arm's configuration",
    "data_snapshot_hash": "hash of the input snapshot",
    "exclusion_reason": "null if predicted; else why. A silently missing row is a violation",
}
REQUIRED_COLS = tuple(PREDICTION_SCHEMA)


def stable_hash(*parts: object) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8")); h.update(b"\x1f")
    return h.hexdigest()[:16]


def pg_uid(player_id, game_id) -> str:
    return "pg_" + stable_hash(int(player_id), str(game_id))


def tg_uid(team_id, game_id) -> str:
    return "tg_" + stable_hash(int(team_id), str(game_id))


def g_uid(game_id) -> str:
    return "g_" + stable_hash(str(game_id))


# --------------------------------------------------------------------------- #
# D3: real tip times
# --------------------------------------------------------------------------- #
def load_tip_observations() -> pd.DataFrame:
    """Every (game_id, tip_time, observed_at, source) we ever saw.

    ``observed_at`` is when WE learned that tip time, which is what makes
    revision-awareness possible: at a cutoff we may only use a version observed before it.
    """
    obs = []
    if PROPS_HIST.exists():
        h = pd.read_csv(PROPS_HIST, dtype=str)
        h = h[h.game_id.notna()]
        obs.append(pd.DataFrame({
            "game_id": h.game_id.astype(str),
            "tip": pd.to_datetime(h.commence_time, errors="coerce", utc=True),
            "observed_at": pd.to_datetime(h.snapshot_returned_utc, errors="coerce", utc=True),
            "source": "props_historical"}))
    if ODDS_EXT.exists():
        o = pd.read_csv(ODDS_EXT, dtype=str)
        o = o[o.game_id.notna()]
        obs.append(pd.DataFrame({
            "game_id": o.game_id.astype(str),
            "tip": pd.to_datetime(o.odds_commence_time, errors="coerce", utc=True),
            "observed_at": pd.to_datetime(o.odds_snapshot_timestamp, errors="coerce", utc=True),
            "source": "odds_extension"}))
    if not obs:
        return pd.DataFrame(columns=["game_id", "tip", "observed_at", "source"])
    d = pd.concat(obs, ignore_index=True).dropna(subset=["tip"])
    # NO IMPUTATION.  An earlier version filled a missing observed_at with (tip - 7 days),
    # which MANUFACTURES information availability that was never demonstrated: it asserts we
    # knew the tip a week ahead purely because we know the tip now.  Observations with no
    # real observed_at are retained ONLY so they can be counted and rejected downstream.
    d["observed_at_missing"] = d.observed_at.isna()
    return d.drop_duplicates(["game_id", "tip", "observed_at", "source"])


def resolve_tip_times(games: pd.DataFrame, obs: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Per game: the tip KNOWABLE IN TIME, or nothing.  FAIL CLOSED.

    THE RULE, single pass and self-consistent:
        an observation qualifies iff  observed_at < (its own reported tip) - 90 minutes.
        Among qualifying observations take the LATEST observed_at -- the most current version
        a forecaster could actually have held at the cutoff.
        If NO observation qualifies, exact reconstruction is UNAVAILABLE and the game is
        downgraded to the date-only policy.

    Using each observation's OWN reported tip removes the circularity (cutoff depends on tip,
    tip depends on cutoff) without a provisional pass, and it is strictly conservative: an
    observation recorded after its own tip-minus-90 cannot support a T-90 cutoff no matter
    what any other observation says.

    WHAT WAS REMOVED, and why it mattered:
      * imputing observed_at as (tip - 7 days) -- asserted week-ahead knowledge purely
        because the tip is known NOW.  Pure manufacture of availability.
      * the earliest-observation fallback -- it accepted an observation regardless of when it
        became available, so a tip first seen minutes before tip-off, or even after the game,
        could back a "T-90m" label.
    Both could certify point-in-time knowledge that was never demonstrated.
    """
    audit = {"observations_total": int(len(obs)),
             "observations_missing_observed_at": 0,
             "observations_rejected_too_late": 0,
             "games_with_any_observation": 0,
             "games_exact_available": 0,
             "games_downgraded_to_date_only": 0}

    empty = games[["game_id"]].copy()
    empty["scheduled_tip_time"] = pd.NaT
    empty["tip_time_observed_at"] = pd.NaT
    empty["tip_time_source"] = None
    empty["tip_time_quality"] = "none"
    empty["tip_revisions_seen"] = 0
    if obs.empty:
        return empty, audit

    o = obs.copy()
    audit["observations_missing_observed_at"] = int(o.observed_at.isna().sum())
    audit["games_with_any_observation"] = int(o.game_id.nunique())

    # A missing observed_at can NEVER qualify -- it is not evidence of timing.
    o = o[o.observed_at.notna()]
    qualifies = o.observed_at < (o.tip - pd.Timedelta(minutes=CUTOFF_MINUTES_BEFORE_TIP))
    audit["observations_rejected_too_late"] = int((~qualifies).sum())
    q = o[qualifies]

    nrev = obs.groupby("game_id").tip.nunique().rename("tip_revisions_seen")
    if q.empty:
        out = empty.merge(nrev, on="game_id", how="left", suffixes=("", "_n"))
        out["tip_revisions_seen"] = out.pop("tip_revisions_seen_n").fillna(0).astype(int) \
            if "tip_revisions_seen_n" in out else 0
        audit["games_downgraded_to_date_only"] = int(len(games))
        return out, audit

    chosen = q.sort_values(["game_id", "observed_at"]).groupby("game_id").tail(1)
    res = chosen[["game_id", "tip", "observed_at", "source"]].rename(columns={
        "tip": "scheduled_tip_time", "observed_at": "tip_time_observed_at",
        "source": "tip_time_source"})
    res = res.merge(nrev, on="game_id", how="left")
    res["tip_time_quality"] = np.where(res.tip_revisions_seen > 1,
                                       "observed_revised", "observed_single")

    out = games[["game_id"]].merge(res, on="game_id", how="left")
    out["tip_time_quality"] = out.tip_time_quality.fillna("none")
    out["tip_revisions_seen"] = out.tip_revisions_seen.fillna(0).astype(int)
    audit["games_exact_available"] = int(out.scheduled_tip_time.notna().sum())
    audit["games_downgraded_to_date_only"] = int(out.scheduled_tip_time.isna().sum())
    return out, audit


def apply_cutoff_policy(games: pd.DataFrame) -> pd.DataFrame:
    """forecast_cutoff = tip - 90m where a tip is known; otherwise a SEPARATELY NAMED
    conservative policy that is never called T-90m."""
    g = games.copy()
    has = g.scheduled_tip_time.notna()
    g["cutoff_policy"] = np.where(has, POLICY_EXACT, POLICY_DATE_ONLY)
    exact = g.scheduled_tip_time - pd.Timedelta(minutes=CUTOFF_MINUTES_BEFORE_TIP)
    # date-only: 18:00 UTC on the DAY BEFORE. Strictly before any plausible tip, so it is
    # genuinely conservative rather than assumed-conservative.
    dateonly = (pd.to_datetime(g.game_date).dt.tz_localize("UTC")
                - pd.Timedelta(days=1) + pd.Timedelta(hours=18))
    g["forecast_cutoff"] = exact.where(has, dateonly)
    g["exact_cutoff_ok"] = has          # only these may be used for market comparisons

    # HARD POST-CONDITION.  Every exact row must prove its tip was observed before its own
    # cutoff.  If this ever fires, an exact label is certifying knowledge we cannot show we
    # had, which is the failure the fail-closed rule exists to prevent.
    ex = g[g.exact_cutoff_ok]
    bad = int((ex.tip_time_observed_at >= ex.forecast_cutoff).sum())
    if bad:
        raise SystemExit(f"{bad} exact rows have tip_time_observed_at >= forecast_cutoff -- "
                         f"exact reconstruction is not defensible; refusing to emit")
    g.attrs["exact_rows_failing_observed_before_cutoff"] = bad
    return g


# --------------------------------------------------------------------------- #
# D1: the pregame candidate roster
# --------------------------------------------------------------------------- #
def build_candidates(mp: pd.DataFrame, lookback: int = ROSTER_LOOKBACK) -> pd.DataFrame:
    """Candidates for (team, game) = players who appeared for that team in its previous
    ``lookback`` games. STRICTLY PRIOR: the target game's own rows are never read.

    Implementation note that IS the invariant: we build a per-team ordered game list, and for
    game index i we take players from games [i-lookback, i-1].  Index i itself is excluded by
    construction, so deleting the target game's player rows cannot change the candidate set.
    """
    d = mp[["game_id", "team_id", "player_id", "game_date", "season"]].dropna()
    d = d.copy()
    d["game_date"] = pd.to_datetime(d.game_date)
    d["game_id"] = d.game_id.astype(str)

    team_games = (d[["team_id", "game_id", "game_date", "season"]].drop_duplicates()
                  .sort_values(["team_id", "season", "game_date", "game_id"])
                  .reset_index(drop=True))
    by_team_players = {k: v.player_id.unique()
                       for k, v in d.groupby(["team_id", "game_id"], sort=False)}

    rows = []
    # Grouped by (team_id, SEASON), not team alone.  Grouping by team only would let a season
    # opener inherit candidates from the previous season's final games -- players who may have
    # been traded, waived or retired in the interim.  The lookback window therefore RESETS at
    # every season boundary, and each season's opener legitimately yields zero candidates.
    for (team_id, season), grp in team_games.groupby(["team_id", "season"], sort=False):
        gids = grp.game_id.tolist()
        dates = grp.game_date.tolist()
        for i, gid in enumerate(gids):
            if i == 0:
                continue                      # season opener: no prior in-season game
            lo = max(0, i - lookback)
            pool: set = set()
            for j in range(lo, i):            # STRICTLY prior, and strictly in-season
                pool.update(by_team_players.get((team_id, gids[j]), ()))
            for pid in pool:
                rows.append((gid, team_id, pid, dates[i], season, i - lo))
    c = pd.DataFrame(rows, columns=["game_id", "team_id", "player_id", "game_date",
                                    "season", "lookback_games_used"])
    c["row_uid"] = [pg_uid(p, g) for p, g in zip(c.player_id, c.game_id)]
    return c.drop_duplicates("row_uid")


def validate_predictions(pred: pd.DataFrame, universe: pd.DataFrame,
                         target_key: str) -> dict:
    """Reject a non-compliant arm rather than repair it.

    v2 difference that matters: obligation is checked against ``prediction_required__<t>``,
    NOT against ``outcome_scoreable__<t>``.  An arm must cover every candidate including
    those who later recorded a DNP; covering only the scoreable rows is the exact loophole
    D2 identified, and it is rejected here.

    Prediction coverage and scoreable coverage are returned SEPARATELY and never combined.
    """
    problems: list[str] = []
    missing = [c for c in REQUIRED_COLS if c not in pred.columns]
    if missing:
        return {"ok": False, "problems": [f"missing required columns: {missing}"]}

    req_col, sc_col = f"prediction_required__{target_key}", f"outcome_scoreable__{target_key}"
    if req_col not in universe.columns:
        return {"ok": False, "problems": [f"universe lacks {req_col}"]}

    required = universe[universe[req_col]]
    scoreable = universe[universe[sc_col]] if sc_col in universe.columns else required

    got = set(pred.row_uid)
    unknown = got - set(universe.row_uid)
    if unknown:
        problems.append(f"{len(unknown)} predictions on row_uids not in the universe")
    uncovered = set(required.row_uid) - got
    if uncovered:
        problems.append(f"{len(uncovered)} REQUIRED rows with neither prediction nor "
                        f"exclusion_reason")
    if pred.row_uid.duplicated().any():
        problems.append("duplicate row_uid in predictions")

    predicted = pred[pred.exclusion_reason.isna()]
    if predicted.pred_point.isna().any():
        problems.append("null pred_point on a row with no exclusion_reason")
    if target_key != "p_active" and (predicted.pred_sd.fillna(-1) <= 0).any():
        problems.append("pred_sd must be strictly positive on distribution targets")
    if target_key == "player_scoring_distribution":
        qs = ["pred_q05", "pred_q25", "pred_q50", "pred_q75", "pred_q95"]
        if predicted[qs].isna().any().any():
            problems.append("quantiles required for player_scoring_distribution")
        elif (np.diff(predicted[qs].to_numpy(), axis=1) < 0).any():
            problems.append("quantiles are not monotone non-decreasing")

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

    n_req, n_sc = len(required), len(scoreable)
    pred_sc = predicted[predicted.row_uid.isin(set(scoreable.row_uid))]
    return {
        "ok": not problems, "problems": problems,
        "n_required": n_req, "n_predicted": int(len(predicted)),
        "n_excluded": int(pred.exclusion_reason.notna().sum()),
        "prediction_coverage": float(len(predicted) / n_req) if n_req else float("nan"),
        "n_scoreable": n_sc, "n_scoreable_predicted": int(len(pred_sc)),
        "scoreable_coverage": float(len(pred_sc) / n_sc) if n_sc else float("nan"),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    mp = pd.read_parquet(MASTER)
    mp["game_id"] = mp.game_id.astype(str)
    mp["game_date"] = pd.to_datetime(mp.game_date)
    acct: dict = {"master_rows": int(len(mp))}

    # ---- D1: candidates from strictly-prior games only ----------------------
    cand = build_candidates(mp)
    acct["candidate_rows"] = int(len(cand))
    acct["candidate_games"] = int(cand.game_id.nunique())
    acct["roster_lookback_games"] = ROSTER_LOOKBACK

    # ---- D3: real tip times and cutoff policies ------------------------------
    games = (mp[["game_id", "game_date", "season"]].drop_duplicates()
             .sort_values("game_date").reset_index(drop=True))
    tips, tip_audit = resolve_tip_times(games, load_tip_observations())
    games = games.merge(tips, on="game_id", how="left")
    games = apply_cutoff_policy(games)
    acct["games_total"] = int(len(games))
    acct["games_exact_tip"] = int(games.exact_cutoff_ok.sum())
    acct["games_date_only"] = int((~games.exact_cutoff_ok).sum())
    acct["games_with_tip_revisions"] = int((games.tip_revisions_seen > 1).sum())
    acct["tip_provenance_audit"] = tip_audit
    ex = games[games.exact_cutoff_ok]
    acct["exact_rows_failing_observed_before_cutoff"] = int(
        (ex.tip_time_observed_at >= ex.forecast_cutoff).sum())

    # COVERAGE FAILURES STAY VISIBLE. A game with zero candidates is a coverage failure to be
    # reported, never a row that quietly disappears from evaluation.
    cand_per_game = cand.groupby("game_id").size()
    all_gids = set(games.game_id)
    acct["games_with_zero_candidates"] = int(len(all_gids - set(cand_per_game.index)))
    tg_keys = mp[["game_id", "team_id"]].drop_duplicates()
    cand_tg = set(map(tuple, cand[["game_id", "team_id"]].drop_duplicates().to_numpy()))
    acct["team_games_with_zero_candidates"] = int(
        sum(1 for t in map(tuple, tg_keys.to_numpy()) if t not in cand_tg))
    acct["candidate_count_distribution"] = {
        str(k): int(v) for k, v in
        cand_per_game.describe(percentiles=[.05, .25, .5, .75, .95]).round(2).items()}
    openers = (mp[["team_id", "season", "game_id", "game_date"]].drop_duplicates()
               .sort_values(["team_id", "season", "game_date"])
               .groupby(["team_id", "season"]).head(1))
    acct["season_openers"] = int(len(openers))
    acct["season_openers_with_candidates"] = int(
        len(set(map(tuple, openers[["game_id", "team_id"]].to_numpy())) & cand_tg))
    acct["season_opener_coverage_note"] = (
        "season openers legitimately have ZERO candidates: the lookback resets at every "
        "season boundary, so no in-season prior game exists. They are reported, not hidden.")
    tt = mp[["team_id", "season"]].drop_duplicates().groupby("team_id").season.agg(
        ["min", "max", "count"])
    acct["teams_total"] = int(len(tt))
    acct["teams_not_in_every_season"] = int((tt["count"] < mp.season.nunique()).sum())
    acct["franchise_transition_note"] = (
        "team_id is the join key, so a franchise that changes abbreviation keeps its "
        "candidates; a franchise that changes team_id would present as a new team whose "
        "first season has no prior games. Teams absent from some seasons are counted above "
        "(expansion: GSV 2025, TOR/PDX 2026).")

    cand = cand.drop(columns=["game_date", "season"]).merge(
        games[["game_id", "game_date", "season", "scheduled_tip_time", "tip_time_source",
               "tip_time_observed_at", "tip_time_quality", "tip_revisions_seen",
               "cutoff_policy", "forecast_cutoff", "exact_cutoff_ok"]],
        on="game_id", how="left")

    # ---- labels attached AFTERWARDS, never as membership ---------------------
    lab = mp[["game_id", "player_id", "minutes", "pts", "fga"]].copy()
    lab["row_uid"] = [pg_uid(p, g) for p, g in zip(lab.player_id, lab.game_id)]
    lab = lab.drop_duplicates("row_uid")[["row_uid", "minutes", "pts", "fga"]]
    pg = cand.merge(lab, on="row_uid", how="left")
    pg["appeared"] = pd.to_numeric(pg.minutes, errors="coerce").fillna(0) > 0
    pg["in_target_box"] = pg.minutes.notna()
    acct["candidates_not_in_target_box"] = int((~pg.in_target_box).sum())
    acct["candidates_appeared"] = int(pg.appeared.sum())
    acct["candidates_dnp_or_absent"] = int((~pg.appeared).sum())

    # ---- D2: obligation vs scoring, three independent flags ------------------
    pg["candidate_at_cutoff"] = True
    for t, T in TARGETS.items():
        if T.table != "player_game":
            continue
        pg[f"prediction_required__{t}"] = True          # EVERY candidate, all targets
        if t == "p_active":
            score = pg.candidate_at_cutoff
        elif t == "e_minutes_given_active":
            score = pg.appeared
        elif t == "attempts_usage":
            score = pg.appeared & pd.to_numeric(pg.fga, errors="coerce").notna()
        else:
            score = pg.appeared & pd.to_numeric(pg.pts, errors="coerce").notna()
        pg[f"outcome_scoreable__{t}"] = score.to_numpy()
        acct[f"required__{t}"] = int(pg[f"prediction_required__{t}"].sum())
        acct[f"scoreable__{t}"] = int(pg[f"outcome_scoreable__{t}"].sum())

    pg["fold_id"] = "season:" + pg.season.astype(int).astype(str)
    pg["train_boundary"] = pg.season.astype(int).map(lambda s: f"seasons < {s}")
    pg["clustering_unit"] = pg.game_date.dt.date.astype(str)

    # ---- D4: separate team-game and game tables ------------------------------
    tg = (mp[["game_id", "team_id", "game_date", "season"]].drop_duplicates()
          .merge(games[["game_id", "forecast_cutoff", "cutoff_policy", "exact_cutoff_ok",
                        "scheduled_tip_time"]], on="game_id", how="left"))
    tg["row_uid"] = [tg_uid(t, g) for t, g in zip(tg.team_id, tg.game_id)]
    tg["fold_id"] = "season:" + tg.season.astype(int).astype(str)
    tg["clustering_unit"] = tg.game_date.dt.date.astype(str)
    tg["prediction_required__team_game_distribution"] = True
    tg["outcome_scoreable__team_game_distribution"] = True
    acct["team_game_rows"] = int(len(tg))
    acct["team_game_unique"] = int(tg.row_uid.nunique())

    gm = games.copy()
    gm["row_uid"] = [g_uid(g) for g in gm.game_id]
    acct["game_rows"] = int(len(gm))

    pg.to_parquet(OUT / "player_game.parquet", index=False)
    tg.to_parquet(OUT / "team_game.parquet", index=False)
    gm.to_parquet(OUT / "game.parquet", index=False)

    spec = {
        "contract_version": CONTRACT_VERSION,
        "supersedes": "player_game_contract/1 -- postgame-selected universe, fabricated "
                      "cutoff, conflated obligation/scoring, duplicated team rows",
        "universe_kind": "RECENCY-ROSTER PROXY, not the complete slate",
        "added_rows_vs_v1": ("rows v2 has that v1 lacked are ADDITIONAL RECENCY-ROSTER-PROXY CANDIDATES, not players v1 should have predicted -- some were traded, waived or otherwise no longer rostered. The appearance rate is the rate WITHIN THIS PROXY UNIVERSE, not the WNBA player-availability rate."),
        "universe_limitations": [
            "candidacy is inferred from appearance in the team's previous "
            f"{ROSTER_LOOKBACK} games because exact historical rosters, transactions and "
            "inactive lists are not reconstructable for every season",
            "a player who missed the entire lookback window is NOT a candidate even if "
            "rostered -- this understates the true slate",
            "a debut or new signing with no prior appearance cannot be a candidate at all",
            "the first game of each team-season has no prior game and yields no candidates",
        ],
        "central_invariant": ("deleting every target-game player row before constructing the "
                             "candidate roster does not change the candidate set; candidacy "
                             "reads only games strictly before the target"),
        "cutoff_policies": {
            POLICY_EXACT: "forecast_cutoff = scheduled_tip_time - 90 minutes; the ONLY rows "
                          "usable for exact-cutoff market comparisons",
            POLICY_DATE_ONLY: "18:00 UTC on the day BEFORE the game. Conservative, reported "
                              "separately, and NEVER described as T-90m",
        },
        "tip_time_resolution": ("two-pass: provisional tip = earliest observed; final = the "
                                "most recent observation made strictly before "
                                "(provisional tip - 90m). A correction learned after the "
                                "cutoff is deliberately not used."),
        "targets": {k: asdict(v) for k, v in TARGETS.items()},
        "quantiles": QUANTILES,
        "prediction_schema": PREDICTION_SCHEMA,
        "tables": {"player_game": "pg_ -- one row per pregame candidate x game",
                   "team_game": "tg_ -- one row per team x game",
                   "game": "g_ -- one row per game"},
        "obligation_vs_scoring": ("prediction_required and outcome_scoreable are INDEPENDENT. "
                                  "E[minutes|active] is required for every candidate including "
                                  "eventual DNPs, and scored only where the player appeared, "
                                  "so an arm cannot buy coverage by dropping the inactive."),
        "accounting": acct,
    }
    (OUT / "contract.json").write_text(json.dumps(spec, indent=1, default=str),
                                       encoding="utf-8")

    ai.write_manifest(
        OUT / "player_game.parquet", producer="prediction_contract_v2.py",
        fit_through_date=pd.to_datetime(pg.game_date).max(),
        fit_through_season=int(pg.season.max()),
        fit_seasons=sorted(int(x) for x in pg.season.unique()),
        asof_granularity="row",
        notes=("Pregame candidate universe (recency-roster). Nothing is fitted. Candidacy "
               "reads only strictly-prior team games; target-game rows are attached as "
               "LABELS only. Each row carries its own forecast_cutoff and cutoff_policy; "
               "only exact_cutoff_ok rows may be used for exact-cutoff market comparisons."),
        extra={"contract_version": CONTRACT_VERSION})

    print(f"contract {CONTRACT_VERSION}  (supersedes v1)")
    print(f"  candidate rows      {acct['candidate_rows']}  over {acct['candidate_games']} games")
    print(f"  not in target box   {acct['candidates_not_in_target_box']}  "
          f"<- rows v1 COULD NOT SEE")
    print(f"  appeared / not      {acct['candidates_appeared']} / {acct['candidates_dnp_or_absent']}")
    print(f"  tips: exact {acct['games_exact_tip']} | date-only {acct['games_date_only']} "
          f"| revised {acct['games_with_tip_revisions']}")
    print(f"  team-game rows      {acct['team_game_rows']} (v1 duplicated this per player)")
    for t in TARGETS:
        if TARGETS[t].table == "player_game":
            print(f"  {t:28s} required {acct['required__'+t]:6d}  "
                  f"scoreable {acct['scoreable__'+t]:6d}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
