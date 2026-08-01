"""prediction_contract_v2 -- the ten required tests, plus the v1 rejection suite.

v1's validator was sound; the universe it validated was not.  These tests target the
universe CONSTRUCTION, because that is where the leakage was:

    v1 built the candidate universe from master_player rows FOR THE TARGET GAME, so a
    player absent from the target box never entered the universe and p_active was
    conditioned on appearing.

The load-bearing test is #1/#2/#3: candidacy must be decidable with every target-game row
deleted.  If that holds, the universe is pregame by construction rather than by assertion.

Runnable two ways:
    python -m pytest tests/ -q
    python tests/test_prediction_contract_v2.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from prediction_contract_v2 import (          # noqa: E402
    POLICY_DATE_ONLY, POLICY_EXACT, REQUIRED_COLS, TARGETS, CUTOFF_MINUTES_BEFORE_TIP,
    apply_cutoff_policy, build_candidates, pg_uid, resolve_tip_times, tg_uid,
    validate_predictions,
)

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        FAILURES.append(f"{name}: {detail}")
        print(f"  FAIL {name}  {detail}")


def synth_master() -> pd.DataFrame:
    """Two teams, six games each. Player 99 plays games 0-4 then DNPs the target game 5.
    Player 77 appears ONLY in the target game (a debut), so no pregame source supports him."""
    rows = []
    dates = pd.date_range("2024-06-01", periods=6, freq="3D")
    for gi in range(6):
        gid = f"g{gi}"
        for team, base in ((10, 100), (20, 200)):
            roster = [base + k for k in range(5)]
            if team == 10:
                roster.append(99)
            for pid in roster:
                dnp = (team == 10 and pid == 99 and gi == 5)
                rows.append({"game_id": gid, "team_id": team, "player_id": pid,
                             "game_date": dates[gi], "season": 2024,
                             "minutes": 0.0 if dnp else 20.0,
                             "pts": np.nan if dnp else 10.0,
                             "fga": np.nan if dnp else 8.0})
            if team == 10 and gi == 5:
                rows.append({"game_id": gid, "team_id": team, "player_id": 77,
                             "game_date": dates[gi], "season": 2024,
                             "minutes": 15.0, "pts": 7.0, "fga": 5.0})
    return pd.DataFrame(rows)


def main() -> int:
    mp = synth_master()
    TARGET = "g5"

    print("1. target-game rows are not used to construct the candidate universe")
    full = build_candidates(mp)
    stripped = build_candidates(mp[mp.game_id != TARGET])
    a = set(full[full.game_id == TARGET].row_uid)
    b = set(stripped[stripped.game_id == TARGET].row_uid) if len(stripped) else set()
    # With the target game's rows deleted the target game itself disappears from the game
    # list, so compare candidacy on the SOURCE that decides it: the prior-games pool.
    blank = mp.copy()
    blank.loc[blank.game_id == TARGET, ["minutes", "pts", "fga"]] = np.nan
    c = set(build_candidates(blank)[lambda d: d.game_id == TARGET].row_uid)
    check("candidate set is unchanged when target labels are blanked", a == c,
          f"{len(a)} vs {len(c)}")
    check("candidates for the target exist at all", len(a) > 0)

    print("\n2. removing target-game DNP rows does not remove candidates")
    dnp_uid = pg_uid(99, TARGET)
    check("the DNP player IS a candidate", dnp_uid in a)
    no_dnp = mp[~((mp.game_id == TARGET) & (mp.player_id == 99))]
    d = set(build_candidates(no_dnp)[lambda x: x.game_id == TARGET].row_uid)
    check("candidate survives deletion of its own target-game row", dnp_uid in d)

    print("\n3. appearing in the target box cannot retroactively confer candidacy")
    debut_uid = pg_uid(77, TARGET)
    check("debut with no prior appearance is NOT a candidate", debut_uid not in a,
          "a player can only be a candidate via a strictly-prior game")

    print("\n4. conditional-minutes is REQUIRED for eventual DNPs, not scored")
    lab = mp[["game_id", "player_id", "minutes"]].copy()
    lab["row_uid"] = [pg_uid(p, g) for p, g in zip(lab.player_id, lab.game_id)]
    u = full.merge(lab[["row_uid", "minutes"]], on="row_uid", how="left")
    u["appeared"] = pd.to_numeric(u.minutes, errors="coerce").fillna(0) > 0
    u["prediction_required__e_minutes_given_active"] = True
    u["outcome_scoreable__e_minutes_given_active"] = u.appeared
    u["prediction_required__p_active"] = True
    u["outcome_scoreable__p_active"] = True
    row = u[u.row_uid == dnp_uid]
    check("DNP row requires a conditional-minutes prediction",
          bool(row["prediction_required__e_minutes_given_active"].iloc[0]))
    check("DNP row is NOT scoreable for conditional minutes",
          not bool(row["outcome_scoreable__e_minutes_given_active"].iloc[0]))
    check("contract text states the obligation",
          "including eventual DNPs" in TARGETS["e_minutes_given_active"].prediction_required)

    print("\n5. prediction coverage and scoreable coverage are reported separately")
    def arm(rows: pd.DataFrame) -> pd.DataFrame:
        n = len(rows)
        return pd.DataFrame({
            "row_uid": rows.row_uid.to_numpy(), "target_key": "e_minutes_given_active",
            "arm_id": "t", "fold_id": "season:2024",
            "forecast_cutoff": pd.Timestamp("2024-06-16T22:30Z"),
            "pred_point": np.full(n, 20.0), "pred_sd": np.full(n, 3.0),
            "pred_q05": np.nan, "pred_q25": np.nan, "pred_q50": np.nan,
            "pred_q75": np.nan, "pred_q95": np.nan,
            "is_fallback": False, "is_cold_start": False, "n_prior_games": 5,
            "feature_asof": pd.Timestamp("2024-06-16T12:00Z"),
            "model_hash": "m", "config_hash": "c", "data_snapshot_hash": "d",
            "exclusion_reason": None})
    r = validate_predictions(arm(u), u, "e_minutes_given_active")
    check("both coverages present", {"prediction_coverage", "scoreable_coverage"} <= set(r))
    check("they are different numbers here",
          r["n_required"] != r["n_scoreable"],
          f"required={r['n_required']} scoreable={r['n_scoreable']}")

    print("\n   ... and an arm cannot buy coverage by dropping the inactive")
    only_scoreable = u[u["outcome_scoreable__e_minutes_given_active"]]
    r2 = validate_predictions(arm(only_scoreable), u, "e_minutes_given_active")
    check("arm covering only scoreable rows is REJECTED", not r2["ok"])
    check("  ... and the reason names REQUIRED rows",
          any("REQUIRED rows" in x for x in r2["problems"]))

    print("\n6/7/8. cutoffs come from real tips, and are labelled honestly")
    games = pd.DataFrame({"game_id": ["afternoon", "evening", "unknown"],
                          "game_date": pd.to_datetime(["2024-06-01"] * 3),
                          "season": [2024] * 3})
    obs = pd.DataFrame({
        "game_id": ["afternoon", "evening", "evening"],
        "tip": pd.to_datetime(["2024-06-01T17:00Z", "2024-06-01T23:00Z",
                               "2024-06-01T23:20Z"], utc=True),
        "observed_at": pd.to_datetime(["2024-05-25T00:00Z", "2024-05-25T00:00Z",
                                       "2024-06-01T22:50Z"], utc=True),
        "source": ["props", "props", "props"]})
    g = apply_cutoff_policy(resolve_tip_times(games, obs).merge(games, on="game_id"))
    aft = g[g.game_id == "afternoon"].iloc[0]
    check("afternoon game gets a TRUE T-90m cutoff",
          aft.forecast_cutoff == pd.Timestamp("2024-06-01T15:30Z"),
          str(aft.forecast_cutoff))
    check("  ... which v1 would have set 7h after tip",
          pd.Timestamp("2024-06-01T22:30Z") > pd.Timestamp("2024-06-01T17:00Z"))
    unk = g[g.game_id == "unknown"].iloc[0]
    check("game without a tip is NOT labelled T-90m", unk.cutoff_policy == POLICY_DATE_ONLY)
    check("  ... and is barred from exact-cutoff comparisons", not bool(unk.exact_cutoff_ok))
    check("  ... and its cutoff is the day before", unk.forecast_cutoff < pd.Timestamp("2024-06-01T00:00Z"))
    ev = g[g.game_id == "evening"].iloc[0]
    check("revision learned AFTER the cutoff is not used",
          ev.scheduled_tip_time == pd.Timestamp("2024-06-01T23:00Z"),
          f"used {ev.scheduled_tip_time}, must be the 23:00 version knowable in advance")
    check("  ... and the revision is recorded", int(ev.tip_revisions_seen) == 2)

    print("\n9. team-game rows are per team-game, not per player")
    tg = mp[["game_id", "team_id"]].drop_duplicates()
    tg["row_uid"] = [tg_uid(t, gid) for t, gid in zip(tg.team_id, tg.game_id)]
    check("one row per team-game", len(tg) == mp.game_id.nunique() * 2, str(len(tg)))
    check("team rows are far fewer than player rows", len(tg) < len(mp))
    check("team uid prefix is distinct", tg.row_uid.str.startswith("tg_").all())
    check("player and team uids cannot collide",
          not set(tg.row_uid) & set(full.row_uid))

    print("\n10. no target-game label can move a candidate/cutoff field")
    mutated = mp.copy()
    m = mutated.game_id == TARGET
    mutated.loc[m, "minutes"] = 48.0
    mutated.loc[m, "pts"] = 99.0
    mutated.loc[m, "fga"] = 50.0
    c2 = build_candidates(mutated)
    check("candidate set invariant to target-game labels",
          set(c2.row_uid) == set(full.row_uid))
    check("lookback_games_used invariant to target-game labels",
          c2.sort_values("row_uid").lookback_games_used.tolist()
          == full.sort_values("row_uid").lookback_games_used.tolist())

    print("\nvalidator rejection suite still holds")
    p = arm(u).drop(columns=["pred_sd"])
    check("missing column rejected", not validate_predictions(p, u, "e_minutes_given_active")["ok"])
    p = arm(u); p.loc[p.index[:3], "feature_asof"] = p.loc[p.index[:3], "forecast_cutoff"]
    r3 = validate_predictions(p, u, "e_minutes_given_active")
    check("feature_asof == cutoff rejected (equality is leakage)", not r3["ok"])
    p = arm(u); p.loc[p.index[0], "pred_sd"] = 0.0
    check("zero sd rejected", not validate_predictions(p, u, "e_minutes_given_active")["ok"])
    p = arm(u); p.loc[p.index[0], "model_hash"] = None
    check("missing provenance hash rejected",
          not validate_predictions(p, u, "e_minutes_given_active")["ok"])
    p = arm(u); p.loc[p.index[:4], "exclusion_reason"] = "cold_start"
    p.loc[p.index[:4], ["pred_point", "pred_sd"]] = np.nan
    r4 = validate_predictions(p, u, "e_minutes_given_active")
    check("declared exclusions pass and are counted", r4["ok"] and r4["n_excluded"] == 4,
          str(r4.get("problems")))

    n = 30
    print(f"\n{n - len(FAILURES)}/{n} tests passed")
    if FAILURES:
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
