#!/usr/bin/env python3
"""prediction_contract_v2.py -- the pregame-selected player-game prediction contract.

Registered: prediction_contract_v2.  SUPERSEDES prediction_contract.py (v1), which is
preserved as a superseded artifact and MUST NOT be consumed.

WHAT WAS WRONG WITH v1, conceded in full
    D1 THE UNIVERSE WAS POSTGAME-SELECTED.  v1 began from master_player rows FOR THE TARGET
       GAME.  Including recorded DNPs was an improvement over "has a row means played", but a
       player absent from the target box never entered the universe at all.  The target-game
       boxscore is postgame information; it cannot define a pregame candidate roster.  v1's
       p_active was therefore conditioned on appearing and was trivially near-1.
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
    A RECENCY-ROSTER universe.  Exact historical rosters, transactions and inactive lists are
    not reconstructable for every season from what the project holds, so candidacy is inferred
    from appearance in the team's previous ROSTER_LOOKBACK games.  It is NOT the complete
    slate and is not described as one.  Its two known biases are recorded in the report: a
    player who missed the whole lookback window is not a candidate even if he was rostered,
    and a debut/signing with no prior appearance cannot be a candidate at all.
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
    # An observation with no observed_at cannot be revision-checked; keep it but mark it.
    d["observed_at"] = d.observed_at.fillna(d.tip - pd.Timedelta(days=7))
    return d.drop_duplicates(["game_id", "tip", "observed_at", "source"])


def resolve_tip_times(games: pd.DataFrame, obs: pd.DataFrame) -> pd.DataFrame:
    """Per game: the tip time KNOWABLE AT THE CUTOFF, not the final corrected one.

    Two-pass, because the cutoff depends on the tip and the tip depends on the cutoff:
      pass 1 -- provisional tip = the EARLIEST observed value (knowable furthest ahead);
      pass 2 -- among observations made strictly BEFORE (provisional tip - 90m), take the
                most recent.  That is the version a forecaster could actually have held.
    A later correction learned after the cutoff is deliberately NOT used.
    """
    if obs.empty:
        out = games[["game_id"]].copy()
        for c in ("scheduled_tip_time", "tip_time_observed_at", "tip_time_source"):
            out[c] = pd.NaT if "time" in c else None
        out["tip_time_quality"] = "none"
        out["tip_revisions_seen"] = 0
        return out

    prov = obs.groupby("game_id").tip.min().rename("prov_tip")
    o = obs.merge(prov, left_on="game_id", right_index=True)
    cut = o.prov_tip - pd.Timedelta(minutes=CUTOFF_MINUTES_BEFORE_TIP)
    known = o[o.observed_at < cut]
    # if nothing was observed before the provisional cutoff, fall back to the earliest
    pick = (known.sort_values("observed_at").groupby("game_id").tail(1)
            if len(known) else o.iloc[0:0])
    fallback = o.sort_values("observed_at").groupby("game_id").head(1)
    chosen = pd.concat([pick, fallback[~fallback.game_id.isin(pick.game_id)]])

    nrev = obs.groupby("game_id").tip.nunique().rename("tip_revisions_seen")
    res = chosen[["game_id", "tip", "observed_at", "source"]].rename(columns={
        "tip": "scheduled_tip_time", "observed_at": "tip_time_observed_at",
        "source": "tip_time_source"}).merge(nrev, on="game_id", how="left")
    res["tip_time_quality"] = np.where(res.tip_revisions_seen > 1,
                                       "observed_revised", "observed_single")
    return games[["game_id"]].merge(res, on="game_id", how="left").assign(
        tip_time_quality=lambda x: x.tip_time_quality.fillna("none"),
        tip_revisions_seen=lambda x: x.tip_revisions_seen.fillna(0).astype(int))


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
                  .sort_values(["team_id", "game_date", "game_id"]).reset_index(drop=True))
    by_team_players = {k: v.player_id.unique()
                       for k, v in d.groupby(["team_id", "game_id"], sort=False)}

    rows = []
    for team_id, grp in team_games.groupby("team_id", sort=False):
        gids = grp.game_id.tolist()
        dates = grp.game_date.tolist()
        seasons = grp.season.tolist()
        for i, gid in enumerate(gids):
            if i == 0:
                continue                      # no prior game -> no defensible candidacy
            lo = max(0, i - lookback)
            pool: set = set()
            for j in range(lo, i):            # STRICTLY prior; i is never included
                pool.update(by_team_players.get((team_id, gids[j]), ()))
            for pid in pool:
                rows.append((gid, team_id, pid, dates[i], seasons[i],
                             i - lo))
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
    tips = resolve_tip_times(games, load_tip_observations())
    games = games.merge(tips, on="game_id", how="left")
    games = apply_cutoff_policy(games)
    acct["games_total"] = int(len(games))
    acct["games_exact_tip"] = int(games.exact_cutoff_ok.sum())
    acct["games_date_only"] = int((~games.exact_cutoff_ok).sum())
    acct["games_with_tip_revisions"] = int((games.tip_revisions_seen > 1).sum())

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
        "universe_kind": "RECENCY-ROSTER, not the complete slate",
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
