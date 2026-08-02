#!/usr/bin/env python3
"""prediction_contract_v3.py -- the AVAILABILITY-CAUSAL pregame candidate universe.

Registered: prediction_contract_v3.  SUPERSEDES prediction_contract_v2, which is preserved
as a superseded artifact and MUST NOT be consumed once v3 is registered.  v2's files are
frozen and are neither modified nor deleted by this producer; it only READS them, to prove
that the one thing that changed is the thing that was meant to change.

WHAT WAS WRONG WITH v2, conceded in full
    D5 THE LOOKBACK WAS POSITIONAL, NOT CAUSAL.  `build_candidates` selected the five
       POSITIONALLY prior same-season team games (`for j in range(lo, i)`) and never asked
       whether those games' player-appearance data was ADMITTED before the target row's
       forecast cutoff.  On the second leg of a back-to-back under the date-only cutoff
       policy the previous night's box score does not exist yet at 18:00 UTC the day before
       the game: its conservative availability bound is NOON UTC THE DAY AFTER it was played,
       which is AFTER the cutoff.  v2 nonetheless read that game's appearances to decide who
       was a candidate.  That is a small leak, but it is the same KIND of leak D1 was about:
       membership decided by information the forecaster did not hold.
    D6 OBLIGATIONS WERE SILENTLY DEDUPLICATED.  v2 ended `build_candidates` with
       `drop_duplicates("row_uid")`, and `row_uid = pg_uid(player_id, game_id)` carries NO
       team.  When a player traded mid-season is a recency-roster candidate for BOTH clubs in
       a game those clubs play against each other, the two obligations collide on row_uid and
       v2 deleted one of them without a receipt.  There are 14 such obligations across the
       six seasons (e.g. 2024-08-23 CHI@CON, three players; 2026-05-27 NYL@PHX, Anneli
       Maley).  A dropped obligation is a row an arm is never asked to predict and is never
       scored on -- silently, which is the failure mode this whole contract exists to stop.
       v3 keeps one row PER OBLIGATION `(team_id, game_id, player_id)` and says so.
    D7 LABELS WERE JOINED TEAM-BLIND.  Because the join key was row_uid, the label
       `appeared` answered "did this player play in this game AT ALL", not "did this player
       play FOR THIS TEAM".  With obligations kept (D6) that is no longer merely imprecise,
       it would double-count one appearance across two teams.  v3 joins labels on
       `(game_id, team_id, player_id)` and carries `appeared_for_other_team` so the traded-
       player rows are visible rather than smoothed away.

THE REGISTERED RULE OF v3, verbatim
    A candidate for (team, game) is a player who appeared in one of the LATEST FIVE PRIOR
    SAME-SEASON TEAM GAMES WHOSE APPEARANCE SOURCE BOUND IS STRICTLY EARLIER THAN THE ROW'S
    FORECAST CUTOFF.  Latest five ADMITTED, not latest five scheduled.  The appearance source
    bound is the registered conservative policy `postgame_policy_lag_36h_from_game_date_utc/1`:
    floor_to_day(game_date) + 36 hours = noon UTC the day AFTER the game.  Equality is a
    VIOLATION, not a pass: a prior game whose bound EQUALS the cutoff is NOT admitted.

WHAT IS PRESERVED FROM v2, deliberately and unchanged
    * the cutoff machinery -- `resolve_tip_times` and `apply_cutoff_policy` are IMPORTED from
      the frozen v2 module rather than copied, and this producer REFUSES TO EMIT unless every
      game's `forecast_cutoff` and `cutoff_policy` equal v2's registered game.parquet exactly.
      That refusal is what makes the row diff attributable to the lookback rule ALONE;
    * the season reset -- the lookback never crosses a season boundary, so each season's
      opener still yields zero candidates;
    * zero-candidate team-games stay VISIBLE: every one of the 2,990 team-games is a row in
      team_game.parquet carrying `n_candidates` and, when that is zero, a named reason;
    * the `pg_uid` row_uid construction, imported from v2 and unchanged.  It is no longer a
      UNIQUE key (see D6) and this file says so loudly instead of restoring uniqueness by
      deleting rows.  `obligation_uid` is the unique key;
    * the target game's own rows are never read to decide membership.

WHAT v3 IS STILL NOT
    Everything v2's docstring conceded about the RECENCY-ROSTER PROXY remains true: this is
    not the complete slate, a player who missed the whole admitted window is not a candidate,
    a debut cannot be one at all.  v3 makes the proxy CAUSAL, not COMPLETE.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

import asof_invariant as ai                                          # noqa: E402
import prediction_contract_v2 as v2                                  # noqa: E402
# Imported, never modified.  These are pure functions of frames.
from prediction_contract_v2 import (                                 # noqa: E402
    CUTOFF_MINUTES_BEFORE_TIP, POLICY_DATE_ONLY, POLICY_EXACT, PREDICTION_SCHEMA,
    QUANTILES, REQUIRED_COLS, TARGETS, apply_cutoff_policy, g_uid, pg_uid,
    resolve_tip_times, stable_hash, tg_uid, validate_predictions,
)

OUT = REPO / "experiments" / "prediction_contract_v3"
V2_OUT = REPO / "experiments" / "prediction_contract_v2"
MASTER = REPO / "data" / "masters" / "master_player.parquet"

CONTRACT_VERSION = "player_game_contract/3"
SUPERSEDES = "player_game_contract/2"
SUPERSEDES_REASON = (
    "v2's candidate lookback was POSITIONAL, not availability-causal: it took the five "
    "positionally prior same-season team games without asking whether those games' "
    "player-appearance data was admitted before the target row's forecast cutoff, so on the "
    "second leg of a back-to-back under the date-only cutoff policy it read a box score that "
    "did not yet exist at the cutoff. v2 also deduplicated obligations on a team-blind "
    "row_uid, silently deleting 14 real (team, game, player) obligations.")

ROSTER_LOOKBACK = 5          # ADMITTED team games looked back to establish candidacy

#: The registered conservative availability policy, identical to
#: `cbs_v7.OUTCOME_AVAILABILITY_POLICY_LAG_HOURS` / `cbs_real_frames.availability_of` and,
#: for a bare game DATE, identical to `asof_invariant.bound_from_dates`.  Reproduced here so
#: this producer has no import-time dependency on the CBS stack; `verify_availability_policy`
#: proves the reproduction is exact and its receipt is written into contract.json.
AVAILABILITY_POLICY_ID = "postgame_policy_lag_36h_from_game_date_utc/1"
AVAILABILITY_POLICY_LAG_HOURS = 36.0

#: The rule, as registered.  Quoted verbatim into contract.json.
ADMISSION_RULE = (
    "A candidate for (team, game) is a player who appeared in one of the LATEST FIVE PRIOR "
    "SAME-SEASON TEAM GAMES WHOSE APPEARANCE SOURCE BOUND IS STRICTLY EARLIER THAN THE ROW'S "
    "FORECAST CUTOFF. Latest five ADMITTED, not latest five scheduled. The appearance source "
    "bound is floor_to_day(game_date) + 36 hours (policy id "
    "'postgame_policy_lag_36h_from_game_date_utc/1'), i.e. noon UTC on the day AFTER the "
    "game. Admission is STRICT: a prior game whose bound EQUALS the cutoff is NOT admitted. "
    "The window never crosses a season boundary, so each season's opener has zero admitted "
    "prior games and therefore zero candidates.")

#: What the coordinator's independent reconstruction predicted.  Recorded so the receipt
#: either agrees with it in public or disagrees with it in public.
EXPECTED_DIFF = {
    "granularity": "obligation (team_id, game_id, player_id)",
    "v2_rows": 35615, "v3_rows": 35627,
    "v2_only": 6, "v3_only": 18, "team_games_affected": 21,
}

DIFF_SAMPLE_CAP = 50


# --------------------------------------------------------------------------- #
# identity
# --------------------------------------------------------------------------- #
def ob_uid(team_id, player_id, game_id) -> str:
    """The UNIQUE key of a v3 row: the obligation, which is team-bearing.

    `row_uid = pg_uid(player_id, game_id)` is preserved verbatim from v2 for join
    compatibility, but it cannot be the primary key here: a player traded mid-season can owe
    two DIFFERENT teams a forecast in the SAME game, and those are two obligations, not one.
    """
    return "ob_" + stable_hash(int(team_id), int(player_id), str(game_id))


# --------------------------------------------------------------------------- #
# the availability gate
# --------------------------------------------------------------------------- #
def availability_bound(game_date) -> pd.Series:
    """The registered +36h conservative POLICY bound. Policy, never an observation.

    Reproduces `cbs_real_frames.availability_of` exactly: floor the game date to its UTC day
    and add 36 hours, i.e. noon UTC the day after.  It is deliberately NOT derived from
    `observed_time`, which in this repo is a LOCAL FILE MTIME and says nothing about when a
    box score became knowable.
    """
    s = game_date if isinstance(game_date, pd.Series) else pd.Series(game_date)
    d = pd.to_datetime(s, utc=True)
    return d.dt.floor("D") + pd.Timedelta(hours=AVAILABILITY_POLICY_LAG_HOURS)


def verify_availability_policy() -> dict:
    """Prove the local reproduction of the policy is byte-for-byte the registered one.

    Checked against BOTH sources of truth: `cbs_v7`'s constant (the CBS stack's policy) and
    `asof_invariant.bound_from_dates` (the manifest convention).  A silent divergence between
    the three would be exactly the kind of "two policies wearing one name" this repo keeps
    getting burned by, so it is a receipt, not a comment.
    """
    rec: dict = {"policy_id": AVAILABILITY_POLICY_ID,
                 "lag_hours": AVAILABILITY_POLICY_LAG_HOURS,
                 "formula": "floor_to_day_utc(game_date) + 36h"}
    try:
        from cbs_v7 import (OUTCOME_AVAILABILITY_POLICY_ID,
                            OUTCOME_AVAILABILITY_POLICY_LAG_HOURS)
        rec["matches_cbs_v7_id"] = (OUTCOME_AVAILABILITY_POLICY_ID == AVAILABILITY_POLICY_ID)
        rec["matches_cbs_v7_lag"] = (float(OUTCOME_AVAILABILITY_POLICY_LAG_HOURS)
                                     == AVAILABILITY_POLICY_LAG_HOURS)
    except Exception as exc:                                    # pragma: no cover
        rec["matches_cbs_v7_id"] = rec["matches_cbs_v7_lag"] = False
        rec["cbs_v7_import_error"] = f"{type(exc).__name__}: {exc}"
    probe = pd.to_datetime(pd.Series(["2024-05-14", "2026-07-31", "2021-08-15"]))
    mine = availability_bound(probe)
    theirs = [ai.bound_from_dates([x]) for x in probe]
    rec["matches_bound_from_dates"] = all(
        pd.Timestamp(a) == pd.Timestamp(b) for a, b in zip(mine, theirs))
    rec["ok"] = bool(rec["matches_cbs_v7_id"] and rec["matches_cbs_v7_lag"]
                     and rec["matches_bound_from_dates"])
    return rec


# --------------------------------------------------------------------------- #
# tip-time sources
# --------------------------------------------------------------------------- #
#: `data/odds_capture/` is gitignored, so it is ABSENT from every git worktree checkout while
#: still being repository-level data shared by all of them.  A producer that quietly ran
#: without it would resolve 2 exact tips instead of 407, silently change 1,086 games' cutoff
#: policy, and then attribute the resulting row diff to the lookback rule -- a completely
#: fabricated finding.  So the resolution order is EXPLICIT, RECORDED in contract.json, and
#: backstopped by `assert_cutoffs_match_v2`, which refuses to emit if the cutoffs moved.
SOURCE_SPECS = (
    ("props_historical", "data/props_capture/historical/master_props_historical.csv",
     "WNBA_PROPS_HIST"),
    ("odds_extension", "data/odds_capture/master_odds_extension.csv", "WNBA_ODDS_EXT"),
)


def _worktree_parent(repo: Path) -> Path | None:
    """If `repo` is a git worktree under `<main>/.claude/worktrees/<name>`, return `<main>`."""
    parts = repo.parts
    for i in range(len(parts) - 2):
        if parts[i] == ".claude" and parts[i + 1] == "worktrees":
            return Path(*parts[:i])
    return None


def resolve_sources() -> dict:
    """Locate each tip-observation source and RECORD which path was used, with its sha256."""
    parent = _worktree_parent(REPO)
    out: dict = {"repo": str(REPO), "worktree_parent": str(parent) if parent else None,
                 "sources": {}}
    for name, rel, env in SOURCE_SPECS:
        tried: list[str] = []
        chosen: Path | None = None
        for cand in ([Path(os.environ[env])] if os.environ.get(env) else []) + \
                    [REPO / rel] + ([parent / rel] if parent else []):
            tried.append(str(cand))
            if cand.exists():
                chosen = cand
                break
        rec = {"relpath": rel, "env_override": env, "paths_tried": tried,
               "resolved": str(chosen) if chosen else None, "found": chosen is not None}
        if chosen is not None:
            rec["sha256"] = ai.content_hash(chosen)
            rec["bytes"] = chosen.stat().st_size
            rec["from_worktree_parent"] = bool(parent and chosen == parent / rel)
        out["sources"][name] = rec
    return out


def load_tip_observations(sources: dict) -> pd.DataFrame:
    """Every (game_id, tip, observed_at, source) we ever saw -- v2's loader, path-resolved.

    Reproduced from `prediction_contract_v2.load_tip_observations` rather than imported ONLY
    because v2 hard-codes its two input paths at module scope; the parsing, the columns and
    the NO-IMPUTATION rule are identical, and `assert_cutoffs_match_v2` proves the output is.
    """
    obs = []
    p = sources["sources"]["props_historical"]["resolved"]
    if p:
        h = pd.read_csv(p, dtype=str)
        h = h[h.game_id.notna()]
        obs.append(pd.DataFrame({
            "game_id": h.game_id.astype(str),
            "tip": pd.to_datetime(h.commence_time, errors="coerce", utc=True),
            "observed_at": pd.to_datetime(h.snapshot_returned_utc, errors="coerce", utc=True),
            "source": "props_historical"}))
    o_path = sources["sources"]["odds_extension"]["resolved"]
    if o_path:
        o = pd.read_csv(o_path, dtype=str)
        o = o[o.game_id.notna()]
        obs.append(pd.DataFrame({
            "game_id": o.game_id.astype(str),
            "tip": pd.to_datetime(o.odds_commence_time, errors="coerce", utc=True),
            "observed_at": pd.to_datetime(o.odds_snapshot_timestamp, errors="coerce", utc=True),
            "source": "odds_extension"}))
    if not obs:
        return pd.DataFrame(columns=["game_id", "tip", "observed_at", "source"])
    d = pd.concat(obs, ignore_index=True).dropna(subset=["tip"])
    # NO IMPUTATION: a missing observed_at is not evidence of timing and is never filled in.
    d["observed_at_missing"] = d.observed_at.isna()
    return d.drop_duplicates(["game_id", "tip", "observed_at", "source"])


def assert_cutoffs_match_v2(games: pd.DataFrame) -> dict:
    """REFUSE TO EMIT unless every game's cutoff is identical to v2's registered one.

    The entire claim of v3 is "the ONLY thing that changed is the lookback rule".  If the tip
    evidence available to this run differs from the evidence v2 was built on -- a missing
    gitignored CSV, a refreshed odds capture -- the cutoffs move, and every row of the diff
    would be measuring that instead.  This is the guard that makes the receipt honest, and it
    fails closed.
    """
    p = V2_OUT / "game.parquet"
    if not p.exists():
        raise SystemExit(f"cannot verify cutoffs: {p} is missing. v3's row diff is only "
                         f"interpretable against the registered v2 artifact.")
    g2 = pd.read_parquet(p)[["game_id", "forecast_cutoff", "cutoff_policy",
                             "exact_cutoff_ok"]].copy()
    g2["game_id"] = g2.game_id.astype(str)
    m = games[["game_id", "forecast_cutoff", "cutoff_policy", "exact_cutoff_ok"]].merge(
        g2, on="game_id", how="outer", suffixes=("_v3", "_v2"), indicator=True)
    problems = []
    if (m._merge != "both").any():
        problems.append(f"{int((m._merge != 'both').sum())} games present in one contract "
                        f"and not the other")
    both = m[m._merge == "both"]
    cut3 = pd.to_datetime(both.forecast_cutoff_v3, utc=True)
    cut2 = pd.to_datetime(both.forecast_cutoff_v2, utc=True)
    n_cut = int((cut3 != cut2).sum())
    n_pol = int((both.cutoff_policy_v3.astype(str) != both.cutoff_policy_v2.astype(str)).sum())
    if n_cut:
        problems.append(f"{n_cut} games whose forecast_cutoff differs from v2's")
    if n_pol:
        problems.append(f"{n_pol} games whose cutoff_policy differs from v2's")
    rec = {"games_compared": int(len(both)), "cutoff_mismatches": n_cut,
           "policy_mismatches": n_pol, "ok": not problems, "problems": problems}
    if problems:
        raise SystemExit(
            "REFUSING TO EMIT -- v3's cutoffs do not match v2's registered game.parquet:\n  "
            + "\n  ".join(problems)
            + "\nThe row diff would then be measuring a change of tip evidence, not the "
              "change of lookback rule. Check that both tip sources resolved (see "
              "resolve_sources(); data/odds_capture/ is gitignored and absent from worktree "
              "checkouts -- set WNBA_ODDS_EXT or run from a checkout that has it).")
    return rec


# --------------------------------------------------------------------------- #
# D5: the availability-causal candidate roster
# --------------------------------------------------------------------------- #
def build_candidates(mp: pd.DataFrame, cutoffs, lookback: int = ROSTER_LOOKBACK
                     ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Candidates and per-team-game window accounting under the ADMITTED-window rule.

    `cutoffs` maps game_id -> tz-aware forecast cutoff.  For team-game i the admitted set is
    every strictly-prior same-season team game j whose availability bound is STRICTLY earlier
    than cutoff(i); the window is the LAST `lookback` of those.  Index i is excluded by
    construction, so deleting the target game's player rows cannot change the candidate set --
    v2's central invariant, retained.

    Returns (candidates, windows).  `windows` has one row per team-game INCLUDING the ones
    with no candidates at all: a coverage failure is reported, never hidden.
    """
    d = mp[["game_id", "team_id", "player_id", "game_date", "season"]].dropna().copy()
    d["game_date"] = pd.to_datetime(d.game_date)
    d["game_id"] = d.game_id.astype(str)

    team_games = (d[["team_id", "game_id", "game_date", "season"]].drop_duplicates()
                  .sort_values(["team_id", "season", "game_date", "game_id"])
                  .reset_index(drop=True))
    by_team_players = {k: v.player_id.unique()
                       for k, v in d.groupby(["team_id", "game_id"], sort=False)}
    cut = {str(k): pd.Timestamp(v) for k, v in dict(cutoffs).items()}

    rows: list[tuple] = []
    windows: list[dict] = []
    # Grouped by (team_id, SEASON): the window RESETS at every season boundary, so a season
    # opener cannot inherit candidates from the previous season's final games.
    for (team_id, season), grp in team_games.groupby(["team_id", "season"], sort=False):
        gids = grp.game_id.tolist()
        dates = [pd.Timestamp(x) for x in grp.game_date.tolist()]
        avail = list(availability_bound(pd.Series(dates)))
        for i, gid in enumerate(gids):
            if gid not in cut:
                raise SystemExit(f"no forecast cutoff for game {gid}; refusing to guess one")
            c = cut[gid]
            if pd.isna(c):
                raise SystemExit(f"null forecast cutoff for game {gid}")
            # STRICT: equality is a violation, not a pass.
            admitted = [j for j in range(i) if avail[j] < c]
            window = admitted[-lookback:]
            positional = list(range(max(0, i - lookback), i))
            pool: set = set()
            for j in window:
                pool.update(by_team_players.get((team_id, gids[j]), ()))
            bound = max((avail[j] for j in window), default=pd.NaT)
            windows.append({
                "team_id": team_id, "game_id": gid, "season": season,
                "game_date": dates[i], "team_game_index": i,
                "prior_games_in_season": i,
                "prior_games_admitted": len(admitted),
                "prior_games_excluded_unadmitted": i - len(admitted),
                "lookback_games_used": len(window),
                "lookback_games_positional": len(positional),
                "admitted_window_bound": bound,
                "admitted_window_first_game": gids[window[0]] if window else None,
                "admitted_window_last_game": gids[window[-1]] if window else None,
                "window_shifted_vs_positional": window != positional,
                "n_candidates": len(pool),
                "zero_candidate_reason": (
                    None if pool else
                    "season_opener_no_prior_in_season_game" if i == 0 else
                    "no_prior_in_season_game_admitted_before_cutoff" if not window else
                    "admitted_window_contained_no_player_rows"),
            })
            for pid in pool:
                rows.append((gid, team_id, pid, dates[i], season, len(window), bound,
                             i - len(admitted), window != positional))

    c = pd.DataFrame(rows, columns=[
        "game_id", "team_id", "player_id", "game_date", "season", "lookback_games_used",
        "admitted_window_bound", "prior_games_excluded_unadmitted",
        "lookback_window_shifted_vs_positional"])
    # row_uid: v2's construction, preserved verbatim. NOT unique -- see D6 and obligation_uid.
    c["row_uid"] = [pg_uid(p, g) for p, g in zip(c.player_id, c.game_id)]
    c["obligation_uid"] = [ob_uid(t, p, g)
                           for t, p, g in zip(c.team_id, c.player_id, c.game_id)]
    shared = c.row_uid.duplicated(keep=False)
    c["row_uid_shared_with_other_team"] = shared.to_numpy()
    if c.obligation_uid.duplicated().any():                      # pragma: no cover
        raise SystemExit("obligation_uid is not unique -- identity is broken")
    return c, pd.DataFrame(windows)


# --------------------------------------------------------------------------- #
# the row-diff receipt
# --------------------------------------------------------------------------- #
def _sample(records: list[dict]) -> list[dict]:
    return sorted(records, key=lambda r: (r["season"], r["game_date"], r["team_id"],
                                          r["player_id"]))[:DIFF_SAMPLE_CAP]


def row_diff_vs_v2(cand: pd.DataFrame, mp: pd.DataFrame) -> dict:
    """Membership accounting ONLY: row counts and set differences, at BOTH granularities.

    Nothing here is fitted, predicted or scored.  The obligation level is the headline,
    because an obligation is what an arm owes a forecast for; the row_uid level is reported
    beside it because v2's dedupe means the two do not agree, and hiding that disagreement
    would be the same silence D6 is about.
    """
    p2 = V2_OUT / "player_game.parquet"
    if not p2.exists():
        raise SystemExit(f"cannot build the row diff: {p2} is missing")
    pg2 = pd.read_parquet(p2)
    pg2["game_id"] = pg2.game_id.astype(str)

    name = dict(zip(mp.player_id.astype("int64"), mp.player_name)) \
        if "player_name" in mp.columns else {}
    abbr = dict(zip(mp.team_id.astype("int64"), mp.team_abbreviation)) \
        if "team_abbreviation" in mp.columns else {}
    gdate = {str(g): str(pd.Timestamp(d).date())
             for g, d in zip(mp.game_id.astype(str), pd.to_datetime(mp.game_date))}
    gseason = {str(g): int(s) for g, s in zip(mp.game_id.astype(str), mp.season)}

    def triples(df):
        return {(int(t), str(g), int(p))
                for t, g, p in df[["team_id", "game_id", "player_id"]].to_numpy()}

    t2, t3 = triples(pg2), triples(cand)
    only2, only3 = t2 - t3, t3 - t2
    uid2, uid3 = set(pg2.row_uid), set(cand.row_uid)

    def rec(tr, side):
        t, g, p = tr
        counterpart = uid3 if side == "v2_only" else uid2
        return {"side": side, "season": gseason.get(g, -1), "game_date": gdate.get(g, ""),
                "game_id": g, "team_id": t, "team": abbr.get(t, ""),
                "player_id": p, "player": name.get(p, ""),
                "row_uid": pg_uid(p, g), "obligation_uid": ob_uid(t, p, g),
                # True => this obligation is INVISIBLE in a team-blind row_uid diff, because
                # the counterpart universe holds the same row_uid under the other team.
                "row_uid_present_in_counterpart": pg_uid(p, g) in counterpart}

    r2 = [rec(x, "v2_only") for x in only2]
    r3 = [rec(x, "v3_only") for x in only3]
    affected = {(t, g) for t, g, _ in only2} | {(t, g) for t, g, _ in only3}

    seasons = sorted({int(s) for s in set(gseason.values())})
    per_season = {}
    for s in seasons:
        a2 = {x for x in t2 if gseason.get(x[1]) == s}
        a3 = {x for x in t3 if gseason.get(x[1]) == s}
        o2, o3 = a2 - a3, a3 - a2
        per_season[str(s)] = {
            "v2_obligations": len(a2), "v3_obligations": len(a3),
            "v2_only": len(o2), "v3_only": len(o3),
            "team_games_affected": len({(t, g) for t, g, _ in o2}
                                       | {(t, g) for t, g, _ in o3}),
        }

    u_only2, u_only3 = uid2 - uid3, uid3 - uid2
    collapsed = int(len(cand) - cand.row_uid.nunique())

    obs = {
        "granularity": "obligation (team_id, game_id, player_id)",
        "v2_rows": len(t2), "v3_rows": len(t3),
        "v2_only_count": len(only2), "v3_only_count": len(only3),
        "net_change": len(t3) - len(t2),
        "team_games_affected": len(affected),
        "v2_only_sample": _sample(r2), "v3_only_sample": _sample(r3),
        "per_season": per_season,
    }
    match = {k: (obs[{"v2_rows": "v2_rows", "v3_rows": "v3_rows", "v2_only": "v2_only_count",
                      "v3_only": "v3_only_count",
                      "team_games_affected": "team_games_affected"}[k]] == val)
             for k, val in EXPECTED_DIFF.items() if k != "granularity"}

    return {
        "receipt": "row_diff/1",
        "contract_version": CONTRACT_VERSION,
        "compared_against": {
            "artifact": str(p2.relative_to(REPO).as_posix()),
            "sha256": ai.content_hash(p2), "rows": int(len(pg2)),
        },
        "rule_change": ADMISSION_RULE,
        "granularity_note": (
            "v2's player_game.parquet holds 35,615 rows because build_candidates ended with "
            "drop_duplicates('row_uid') and row_uid = pg_uid(player_id, game_id) carries no "
            "team. v3 keeps one row per OBLIGATION (team_id, game_id, player_id). The "
            "headline diff is therefore taken at obligation granularity against v2's rows, "
            "each of which IS one obligation; the row_uid-level diff is reported beside it "
            "so the 14 obligations v2 deduplicated away are counted, not implied."),
        "obligation_level": obs,
        "row_uid_level": {
            "granularity": "row_uid = pg_uid(player_id, game_id), team-blind",
            "v2_distinct_row_uids": len(uid2),
            "v3_distinct_row_uids": int(cand.row_uid.nunique()),
            "v3_rows": int(len(cand)),
            "v3_rows_sharing_a_row_uid_with_another_team": collapsed * 2,
            "obligations_v2_dedupe_deleted": collapsed,
            "v2_only_count": len(u_only2), "v3_only_count": len(u_only3),
            "v2_only_sample": sorted(u_only2)[:DIFF_SAMPLE_CAP],
            "v3_only_sample": sorted(u_only3)[:DIFF_SAMPLE_CAP],
            "note": ("14 of the v3-only OBLIGATIONS carry a row_uid v2 already contained "
                     "under the other team, so they are invisible at row_uid granularity. "
                     "That invisibility is the defect, not an artefact of the diff."),
        },
        "independent_reconstruction": {
            "expected": EXPECTED_DIFF, "matches": match,
            "all_match": bool(all(match.values())),
        },
    }


# --------------------------------------------------------------------------- #
def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    mp = pd.read_parquet(MASTER)
    mp["game_id"] = mp.game_id.astype(str)
    mp["game_date"] = pd.to_datetime(mp.game_date)
    acct: dict = {"master_rows": int(len(mp))}

    pol = verify_availability_policy()
    if not pol["ok"]:
        raise SystemExit(f"availability policy reproduction is not exact: {pol}")
    acct["availability_policy"] = pol

    # ---- cutoffs: v2's machinery, unchanged, and PROVEN unchanged -----------
    sources = resolve_sources()
    acct["tip_source_resolution"] = sources
    games = (mp[["game_id", "game_date", "season"]].drop_duplicates()
             .sort_values("game_date").reset_index(drop=True))
    tips, tip_audit = resolve_tip_times(games, load_tip_observations(sources))
    games = games.merge(tips, on="game_id", how="left")
    games = apply_cutoff_policy(games)
    acct["cutoff_identity_vs_v2"] = assert_cutoffs_match_v2(games)
    acct["games_total"] = int(len(games))
    acct["games_exact_tip"] = int(games.exact_cutoff_ok.sum())
    acct["games_date_only"] = int((~games.exact_cutoff_ok).sum())
    acct["games_with_tip_revisions"] = int((games.tip_revisions_seen > 1).sum())
    acct["tip_provenance_audit"] = tip_audit

    cutoffs = dict(zip(games.game_id, pd.to_datetime(games.forecast_cutoff, utc=True)))

    # ---- D5: candidates from ADMITTED strictly-prior games only -------------
    cand, win = build_candidates(mp, cutoffs)
    acct["admission_rule"] = ADMISSION_RULE
    acct["roster_lookback_admitted_games"] = ROSTER_LOOKBACK
    acct["candidate_obligations"] = int(len(cand))
    acct["candidate_distinct_row_uids"] = int(cand.row_uid.nunique())
    acct["candidate_games"] = int(cand.game_id.nunique())
    acct["obligations_sharing_a_row_uid"] = int(cand.row_uid_shared_with_other_team.sum())
    acct["row_uid_collision_note"] = (
        "row_uid = pg_uid(player_id, game_id) is preserved from v2 and carries NO team, so a "
        "player traded mid-season who is a candidate for both clubs in their head-to-head "
        "game produces two obligations with one row_uid. v2 deleted one of each pair via "
        "drop_duplicates('row_uid'); v3 keeps both and exposes obligation_uid as the unique "
        "key. Joining v3 on row_uid alone will silently fan out or drop these rows.")

    # ---- the gate's own accounting: what the causal rule actually changed ----
    acct["team_games_total"] = int(len(win))
    acct["team_games_window_shifted_vs_positional"] = int(win.window_shifted_vs_positional.sum())
    acct["prior_games_excluded_unadmitted_total"] = int(win.prior_games_excluded_unadmitted.sum())
    acct["team_games_with_an_unadmitted_prior_game"] = int(
        (win.prior_games_excluded_unadmitted > 0).sum())
    shifted = win[win.window_shifted_vs_positional]
    acct["window_shift_by_cutoff_policy"] = {
        str(k): int(v) for k, v in
        shifted.merge(games[["game_id", "cutoff_policy"]], on="game_id", how="left")
        .groupby("cutoff_policy").size().items()}
    acct["window_shift_note"] = (
        "Every shifted window is the second leg of a back-to-back under the date-only cutoff "
        "policy: the previous night's box score has availability bound noon UTC the following "
        "day, which is AFTER an 18:00 UTC prior-day cutoff. Under the exact-tip policy the "
        "same prior game IS admitted, because tip-90m falls later in the day than noon UTC. "
        "The two policies therefore admit genuinely different windows, and that is a fact "
        "about what was knowable, not an inconsistency.")

    # COVERAGE FAILURES STAY VISIBLE.
    acct["team_games_with_zero_candidates"] = int((win.n_candidates == 0).sum())
    acct["zero_candidate_reasons"] = {
        str(k): int(v) for k, v in win.zero_candidate_reason.dropna().value_counts().items()}
    acct["games_with_zero_candidates"] = int(len(set(games.game_id) - set(cand.game_id)))
    acct["lookback_games_used_distribution"] = {
        str(k): int(v) for k, v in win.lookback_games_used.value_counts().sort_index().items()}
    acct["candidate_count_distribution"] = {
        str(k): float(v) for k, v in
        cand.groupby("game_id").size().describe(
            percentiles=[.05, .25, .5, .75, .95]).round(2).items()}
    openers = win[win.team_game_index == 0]
    acct["season_openers"] = int(len(openers))
    acct["season_openers_with_candidates"] = int((openers.n_candidates > 0).sum())
    acct["season_opener_coverage_note"] = (
        "season openers legitimately have ZERO candidates: the window resets at every season "
        "boundary, so no in-season prior game exists. They are reported, not hidden.")
    tt = mp[["team_id", "season"]].drop_duplicates().groupby("team_id").season.agg(
        ["min", "max", "count"])
    acct["teams_total"] = int(len(tt))
    acct["teams_not_in_every_season"] = int((tt["count"] < mp.season.nunique()).sum())

    # ---- the row-diff receipt ------------------------------------------------
    diff = row_diff_vs_v2(cand, mp)
    (OUT / "row_diff_vs_v2.json").write_text(json.dumps(diff, indent=1, default=str),
                                             encoding="utf-8")
    acct["row_diff_vs_v2"] = {
        "v2_obligations": diff["obligation_level"]["v2_rows"],
        "v3_obligations": diff["obligation_level"]["v3_rows"],
        "v2_only": diff["obligation_level"]["v2_only_count"],
        "v3_only": diff["obligation_level"]["v3_only_count"],
        "team_games_affected": diff["obligation_level"]["team_games_affected"],
        "matches_independent_reconstruction": diff["independent_reconstruction"]["all_match"],
    }

    # ---- cutoff fields onto the candidate rows -------------------------------
    cand = cand.drop(columns=["season"]).merge(
        games[["game_id", "season", "scheduled_tip_time", "tip_time_source",
               "tip_time_observed_at", "tip_time_quality", "tip_revisions_seen",
               "cutoff_policy", "forecast_cutoff", "exact_cutoff_ok"]],
        on="game_id", how="left")

    # HARD POST-CONDITION of the whole contract: the evidence behind a row's candidacy must
    # strictly predate that row's cutoff. If this fires, the gate did not gate.
    bad = int((pd.to_datetime(cand.admitted_window_bound, utc=True)
               >= pd.to_datetime(cand.forecast_cutoff, utc=True)).sum())
    if bad:
        raise SystemExit(f"{bad} rows whose admitted_window_bound is NOT strictly before "
                         f"their forecast_cutoff -- the availability gate is not causal")
    acct["rows_failing_window_bound_before_cutoff"] = bad

    # ---- D7: labels attached AFTERWARDS, joined ON THE OBLIGATION'S TEAM -----
    lab = mp[["game_id", "team_id", "player_id", "minutes", "pts", "fga"]].copy()
    lab = lab.drop_duplicates(["game_id", "team_id", "player_id"])
    pg = cand.merge(lab, on=["game_id", "team_id", "player_id"], how="left")
    pg["appeared"] = pd.to_numeric(pg.minutes, errors="coerce").fillna(0) > 0
    pg["in_target_box"] = pg.minutes.notna()
    played_elsewhere = {(str(g), int(p)) for g, p, m in
                        zip(mp.game_id, mp.player_id, pd.to_numeric(mp.minutes,
                                                                    errors="coerce").fillna(0))
                        if m > 0}
    pg["appeared_for_other_team"] = [
        (not a) and ((g, int(p)) in played_elsewhere)
        for a, g, p in zip(pg.appeared, pg.game_id, pg.player_id)]
    acct["candidates_not_in_target_box"] = int((~pg.in_target_box).sum())
    acct["candidates_appeared"] = int(pg.appeared.sum())
    acct["candidates_dnp_or_absent"] = int((~pg.appeared).sum())
    acct["candidates_who_appeared_for_the_other_team"] = int(pg.appeared_for_other_team.sum())
    # what the team-aware join changed vs v2's team-blind one, measured not asserted
    blind = mp[["game_id", "player_id", "minutes"]].copy()
    blind["row_uid"] = [pg_uid(p, g) for p, g in zip(blind.player_id, blind.game_id)]
    blind = blind.drop_duplicates("row_uid")[["row_uid", "minutes"]].rename(
        columns={"minutes": "minutes_blind"})
    chk = pg[["row_uid", "appeared"]].merge(blind, on="row_uid", how="left")
    acct["rows_where_team_blind_label_would_differ"] = int(
        ((pd.to_numeric(chk.minutes_blind, errors="coerce").fillna(0) > 0) != chk.appeared).sum())
    acct["label_join_note"] = (
        "labels join on (game_id, team_id, player_id), NOT on row_uid. A team-blind join "
        "would tell the club a traded player left that he 'appeared' for them, because he "
        "appeared for the club he was traded to in the very same game.")

    # ---- obligation vs scoring, three independent flags ---------------------
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
        pg[f"outcome_scoreable__{t}"] = np.asarray(score)
        acct[f"required__{t}"] = int(pg[f"prediction_required__{t}"].sum())
        acct[f"scoreable__{t}"] = int(pg[f"outcome_scoreable__{t}"].sum())

    pg["fold_id"] = "season:" + pg.season.astype(int).astype(str)
    pg["train_boundary"] = pg.season.astype(int).map(lambda s: f"seasons < {s}")
    pg["clustering_unit"] = pg.game_date.dt.date.astype(str)

    # ---- team-game and game tables ------------------------------------------
    tg = (mp[["game_id", "team_id", "game_date", "season"]].drop_duplicates()
          .merge(games[["game_id", "forecast_cutoff", "cutoff_policy", "exact_cutoff_ok",
                        "scheduled_tip_time"]], on="game_id", how="left")
          .merge(win[["game_id", "team_id", "n_candidates", "lookback_games_used",
                      "prior_games_admitted", "prior_games_excluded_unadmitted",
                      "admitted_window_bound", "window_shifted_vs_positional",
                      "zero_candidate_reason"]],
                 on=["game_id", "team_id"], how="left"))
    tg["row_uid"] = [tg_uid(t, g) for t, g in zip(tg.team_id, tg.game_id)]
    tg["fold_id"] = "season:" + tg.season.astype(int).astype(str)
    tg["clustering_unit"] = tg.game_date.dt.date.astype(str)
    tg["prediction_required__team_game_distribution"] = True
    tg["outcome_scoreable__team_game_distribution"] = True
    acct["team_game_rows"] = int(len(tg))
    acct["team_game_unique"] = int(tg.row_uid.nunique())
    acct["team_game_zero_candidate_rows_retained"] = int((tg.n_candidates.fillna(0) == 0).sum())

    gm = games.copy()
    gm["row_uid"] = [g_uid(g) for g in gm.game_id]
    acct["game_rows"] = int(len(gm))

    pg.to_parquet(OUT / "player_game.parquet", index=False)
    tg.to_parquet(OUT / "team_game.parquet", index=False)
    gm.to_parquet(OUT / "game.parquet", index=False)

    spec = {
        "contract_version": CONTRACT_VERSION,
        "supersedes": SUPERSEDES,
        "supersedes_reason": SUPERSEDES_REASON,
        "admission_rule": ADMISSION_RULE,
        "availability_policy": {
            "policy_id": AVAILABILITY_POLICY_ID,
            "lag_hours": AVAILABILITY_POLICY_LAG_HOURS,
            "formula": "floor_to_day_utc(game_date) + 36h = noon UTC the day AFTER the game",
            "identical_to": ["cbs_v7.OUTCOME_AVAILABILITY_POLICY_LAG_HOURS",
                             "cbs_real_frames.availability_of",
                             "asof_invariant.bound_from_dates (for a bare game date)"],
            "kind": "POLICY, never an observation; deliberately NOT derived from "
                    "observed_time, which is a local file mtime",
            "strictness": "admission requires bound < cutoff; EQUALITY IS A VIOLATION",
        },
        "universe_kind": "RECENCY-ROSTER PROXY, made availability-causal; still not the "
                         "complete slate",
        "preserved_from_v2": [
            "the cutoff machinery (resolve_tip_times / apply_cutoff_policy imported from the "
            "frozen v2 module) and, proven per game against v2's registered game.parquet, the "
            "resulting forecast_cutoff and cutoff_policy",
            "the season reset: the window never crosses a season boundary and each season's "
            "opener yields zero candidates",
            "zero-candidate team-games remain VISIBLE, as rows of team_game.parquet carrying "
            "n_candidates and a named zero_candidate_reason",
            "the pg_uid row_uid construction, unchanged",
            "the central invariant: the target game's own rows are never read to decide "
            "membership",
        ],
        "changed_vs_v2": [
            "D5 the lookback is over ADMITTED prior games, not positionally prior ones",
            "D6 one row per OBLIGATION (team_id, game_id, player_id); v2's "
            "drop_duplicates('row_uid') deleted 14 obligations without a receipt",
            "D7 labels join on (game_id, team_id, player_id), not on the team-blind row_uid",
        ],
        "new_columns": {
            "lookback_games_used": "count of ADMITTED prior same-season team games actually "
                                   "pooled for this row (0-5)",
            "admitted_window_bound": "the LATEST availability bound among the admitted games "
                                     "used; strictly < forecast_cutoff on every row, enforced",
            "prior_games_excluded_unadmitted": "prior same-season team games whose bound was "
                                               "not strictly before this row's cutoff",
            "lookback_window_shifted_vs_positional": "True where the admitted window differs "
                                                     "from v2's positional five",
            "obligation_uid": "ob_ -- the UNIQUE key (team, player, game)",
            "row_uid_shared_with_other_team": "True on both rows of a row_uid collision",
            "appeared_for_other_team": "the player appeared in this game, for the other club",
        },
        "universe_limitations": [
            f"candidacy is inferred from appearance in the team's latest {ROSTER_LOOKBACK} "
            "ADMITTED games because exact historical rosters, transactions and inactive lists "
            "are not reconstructable for every season",
            "a player who missed the entire admitted window is NOT a candidate even if "
            "rostered -- this understates the true slate",
            "a debut or new signing with no prior appearance cannot be a candidate at all",
            "the first game of each team-season has no admitted prior game and yields none",
            "the availability bound is a POLICY, so it is conservative by construction: where "
            "a box score really was published sooner, v3 still refuses to use it",
        ],
        "central_invariant": (
            "deleting every target-game player row before constructing the candidate roster "
            "does not change the candidate set; candidacy reads only same-season games that "
            "are strictly prior AND whose appearance data was admitted strictly before the "
            "row's forecast cutoff"),
        "cutoff_policies": {
            POLICY_EXACT: f"forecast_cutoff = scheduled_tip_time - "
                          f"{CUTOFF_MINUTES_BEFORE_TIP} minutes; the ONLY rows usable for "
                          f"exact-cutoff market comparisons",
            POLICY_DATE_ONLY: "18:00 UTC on the day BEFORE the game. Conservative, reported "
                              "separately, and NEVER described as T-90m",
        },
        "targets": {k: asdict(v) for k, v in TARGETS.items()},
        "quantiles": QUANTILES,
        "prediction_schema": PREDICTION_SCHEMA,
        "tables": {"player_game": "one row per pregame OBLIGATION (team x player x game)",
                   "team_game": "tg_ -- one row per team x game, including zero-candidate ones",
                   "game": "g_ -- one row per game"},
        "obligation_vs_scoring": (
            "prediction_required and outcome_scoreable are INDEPENDENT. E[minutes|active] is "
            "required for every candidate including eventual DNPs, and scored only where the "
            "player appeared FOR THAT TEAM, so an arm cannot buy coverage by dropping the "
            "inactive."),
        "accounting": acct,
        "row_diff_receipt": "row_diff_vs_v2.json",
    }
    (OUT / "contract.json").write_text(json.dumps(spec, indent=1, default=str),
                                       encoding="utf-8")

    # ---- as-of manifests for EVERY artifact ---------------------------------
    seasons = sorted(int(s) for s in pd.unique(gm.season))
    bound = ai.bound_from_dates(pd.to_datetime(gm.game_date))
    inherit = ("As-of bound derived from GAME DATES via asof_invariant.bound_from_dates "
               "(max(game_date) + 1 day at 12:00 UTC). The master's observed_time column is a "
               "LOCAL FILE MTIME and is deliberately NOT used as an as-of bound.")
    ai.write_manifest(
        OUT / "player_game.parquet", producer="prediction_contract_v3.py",
        fit_through_date=ai.bound_from_dates(pd.to_datetime(pg.game_date)),
        fit_through_season=int(pg.season.max()),
        fit_seasons=sorted(int(x) for x in pd.unique(pg.season)),
        asof_granularity="row",
        notes=("Availability-causal pregame candidate universe. Nothing is fitted. Candidacy "
               "reads only same-season prior team games whose appearance bound is strictly "
               "before the row's forecast cutoff; target-game rows are attached as LABELS "
               "only, joined on (game_id, team_id, player_id). Each row carries its own "
               "forecast_cutoff, cutoff_policy and admitted_window_bound; only exact_cutoff_ok "
               "rows may be used for exact-cutoff market comparisons. row_uid is NOT unique "
               "here -- join on obligation_uid. " + inherit),
        extra={"contract_version": CONTRACT_VERSION,
               "bound_source": "game_date via asof_invariant.bound_from_dates",
               "supersedes": SUPERSEDES})
    ai.write_manifest(
        OUT / "team_game.parquet", producer="prediction_contract_v3.py",
        fit_through_date=ai.bound_from_dates(pd.to_datetime(tg.game_date)),
        fit_through_season=int(tg.season.max()),
        fit_seasons=sorted(int(x) for x in pd.unique(tg.season)),
        asof_granularity="row",
        notes=("One row per team-game, INCLUDING every zero-candidate team-game, which "
               "carries n_candidates=0 and a named zero_candidate_reason. " + inherit),
        extra={"contract_version": CONTRACT_VERSION,
               "bound_source": "game_date via asof_invariant.bound_from_dates",
               "supersedes": SUPERSEDES})
    ai.write_manifest(
        OUT / "game.parquet", producer="prediction_contract_v3.py",
        fit_through_date=bound, fit_through_season=int(gm.season.max()),
        fit_seasons=seasons, asof_granularity="row",
        notes=("One row per game with its resolved tip provenance and cutoff policy. "
               + inherit),
        extra={"contract_version": CONTRACT_VERSION,
               "bound_source": "game_date via asof_invariant.bound_from_dates",
               "supersedes": SUPERSEDES})
    ai.write_manifest(
        OUT / "contract.json", producer="prediction_contract_v3.py",
        fit_through_date=bound, fit_through_season=int(gm.season.max()),
        fit_seasons=seasons, asof_granularity="artifact",
        notes=("contract.json is a POLICY DOCUMENT: it has no game_date and no timestamp of "
               "its own. This bound is INHERITED from the tables it describes via "
               "asof_invariant.bound_from_dates and is not a measurement of this file. "
               f"Cross-check: accounting records candidate_obligations="
               f"{acct['candidate_obligations']}, team_game_rows={acct['team_game_rows']}, "
               f"master_rows={acct['master_rows']}."),
        extra={"contract_version": CONTRACT_VERSION,
               "bound_source": "INHERITED from player_game.parquet and team_game.parquet",
               "document_has_no_dates_of_its_own": True, "supersedes": SUPERSEDES})
    ai.write_manifest(
        OUT / "row_diff_vs_v2.json", producer="prediction_contract_v3.py",
        fit_through_date=bound, fit_through_season=int(gm.season.max()),
        fit_seasons=seasons, asof_granularity="artifact",
        notes=("Membership accounting only: row counts and set differences between the v2 and "
               "v3 candidate universes. No model, no prediction, no score. The bound is "
               "INHERITED from the game dates of the two universes it compares."),
        extra={"contract_version": CONTRACT_VERSION,
               "bound_source": "INHERITED from the compared universes' game dates",
               "compared_against": "experiments/prediction_contract_v2/player_game.parquet",
               "supersedes": SUPERSEDES})

    d = diff["obligation_level"]
    print(f"contract {CONTRACT_VERSION}  (supersedes {SUPERSEDES})")
    print(f"  admitted-window rule: latest {ROSTER_LOOKBACK} prior same-season team games "
          f"with bound < cutoff (bound = game_date + 36h, STRICT)")
    print(f"  obligations         {acct['candidate_obligations']}  over "
          f"{acct['candidate_games']} games ({acct['candidate_distinct_row_uids']} distinct "
          f"row_uids; {acct['obligations_sharing_a_row_uid']} rows share one)")
    print(f"  windows shifted     {acct['team_games_window_shifted_vs_positional']} team-games "
          f"had >=1 unadmitted prior game inside v2's positional five")
    print(f"  zero-candidate tg   {acct['team_games_with_zero_candidates']} "
          f"({acct['zero_candidate_reasons']})")
    print(f"  appeared / not      {acct['candidates_appeared']} / "
          f"{acct['candidates_dnp_or_absent']}")
    print(f"  tips: exact {acct['games_exact_tip']} | date-only {acct['games_date_only']} "
          f"| cutoffs identical to v2: {acct['cutoff_identity_vs_v2']['ok']}")
    print(f"\n  ROW DIFF vs v2 (obligation granularity)")
    print(f"    v2 {d['v2_rows']} -> v3 {d['v3_rows']}   ({d['net_change']:+d})")
    print(f"    v2-only {d['v2_only_count']}   v3-only {d['v3_only_count']}   "
          f"team-games affected {d['team_games_affected']}")
    print(f"    matches the independent reconstruction: "
          f"{diff['independent_reconstruction']['all_match']}")
    print(f"    per season: " + ", ".join(
        f"{s}:{v['v2_only']}-/{v['v3_only']}+" for s, v in d["per_season"].items()))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
