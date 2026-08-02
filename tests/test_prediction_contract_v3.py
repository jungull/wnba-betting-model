"""prediction_contract_v3 -- the availability-causal candidate universe, on SYNTHETIC frames.

v2's universe was pregame by construction but not AVAILABILITY-CAUSAL: it pooled the five
POSITIONALLY prior same-season team games without asking whether those games' appearance data
existed yet at the row's forecast cutoff.  These tests target the gate, on hand-built fixtures
whose right answer is known by hand:

    the load-bearing case is the second leg of a back-to-back under the date-only cutoff.
    The previous night's box score has availability bound NOON UTC THE NEXT DAY, which is
    AFTER an 18:00 UTC prior-day cutoff, so it is NOT admitted -- and the window reaches one
    game FURTHER BACK rather than shrinking.  "Latest five ADMITTED", not "latest five
    scheduled".

Nothing here reads the real artifacts: every frame is built in this file, so a stale or
absent parquet cannot make these tests pass or fail.

Runnable two ways:
    python -m pytest tests/ -q
    python tests/test_prediction_contract_v3.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from prediction_contract_v3 import (          # noqa: E402
    ADMISSION_RULE, AVAILABILITY_POLICY_LAG_HOURS, CONTRACT_VERSION, POLICY_DATE_ONLY,
    POLICY_EXACT, ROSTER_LOOKBACK, SUPERSEDES, apply_cutoff_policy, availability_bound,
    build_candidates, ob_uid, pg_uid, resolve_tip_times, verify_availability_policy,
)

PASSED = 0
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
        print(f"  ok   {name}")
    else:
        FAILED.append(f"{name}: {detail}")
        print(f"  FAIL {name}  {detail}")


# --------------------------------------------------------------------------- #
# fixture helpers
# --------------------------------------------------------------------------- #
def master(spec: list[tuple]) -> pd.DataFrame:
    """spec: (game_id, 'YYYY-MM-DD', team_id, season, [player_ids]) -> a master_player frame."""
    rows = []
    for gid, date, team, season, pids in spec:
        for pid in pids:
            rows.append({"game_id": gid, "team_id": team, "player_id": pid,
                         "game_date": pd.Timestamp(date), "season": season,
                         "minutes": 20.0, "pts": 10.0, "fga": 8.0})
    return pd.DataFrame(rows)


def date_only(date: str) -> pd.Timestamp:
    """v2's date-only policy, reproduced: 18:00 UTC on the day BEFORE the game."""
    return pd.Timestamp(date, tz="UTC") - pd.Timedelta(days=1) + pd.Timedelta(hours=18)


def exact(tip: str) -> pd.Timestamp:
    """The exact-tip policy: tip - 90 minutes."""
    return pd.Timestamp(tip, tz="UTC") - pd.Timedelta(minutes=90)


def cand_for(cand: pd.DataFrame, team, gid) -> set:
    return set(cand[(cand.team_id == team) & (cand.game_id == gid)].player_id)


def window_for(win: pd.DataFrame, team, gid) -> pd.Series:
    return win[(win.team_id == team) & (win.game_id == gid)].iloc[0]


# The back-to-back fixture, used by several tests.
#   g1..g5 are every other day; g6 is the night BEFORE the target g7.
#   player 91 appears ONLY in g1 (the game a positional five would have dropped)
#   player 96 appears ONLY in g6 (the game the availability gate refuses)
B2B = [
    ("g1", "2024-06-01", 10, 2024, [1, 2, 3, 91]),
    ("g2", "2024-06-03", 10, 2024, [1, 2, 3]),
    ("g3", "2024-06-05", 10, 2024, [1, 2, 3]),
    ("g4", "2024-06-07", 10, 2024, [1, 2, 3]),
    ("g5", "2024-06-09", 10, 2024, [1, 2, 3]),
    ("g6", "2024-06-10", 10, 2024, [1, 2, 3, 96]),
    ("g7", "2024-06-11", 10, 2024, [1, 2, 3, 77]),          # 77 debuts in the target only
]
B2B_CUT = {g: date_only(d) for g, d, *_ in B2B}


def main() -> int:
    print("0. the availability policy is the REGISTERED one, not a look-alike")
    pol = verify_availability_policy()
    check("policy lag is 36h", AVAILABILITY_POLICY_LAG_HOURS == 36.0)
    check("matches cbs_v7's registered policy id and lag",
          pol["matches_cbs_v7_id"] and pol["matches_cbs_v7_lag"], str(pol))
    check("matches asof_invariant.bound_from_dates", pol["matches_bound_from_dates"])
    b = availability_bound(pd.Series([pd.Timestamp("2024-06-10")]))[0]
    check("bound(2024-06-10) is noon UTC on 06-11",
          b == pd.Timestamp("2024-06-11T12:00Z"), str(b))
    check("the contract supersedes v2", (CONTRACT_VERSION, SUPERSEDES)
          == ("player_game_contract/3", "player_game_contract/2"))
    check("the registered rule says ADMITTED, not scheduled",
          "ADMITTED" in ADMISSION_RULE and "STRICTLY EARLIER" in ADMISSION_RULE)

    print("\n1. back-to-back: last night's box score is NOT admitted at a date-only cutoff")
    mp = master(B2B)
    cand, win = build_candidates(mp, B2B_CUT)
    w = window_for(win, 10, "g7")
    check("g7's cutoff is 18:00 UTC the day before",
          B2B_CUT["g7"] == pd.Timestamp("2024-06-10T18:00Z"))
    check("g6's availability bound (2024-06-11 12:00Z) is AFTER that cutoff",
          availability_bound(pd.Series([pd.Timestamp("2024-06-10")]))[0] > B2B_CUT["g7"])
    check("exactly one prior game is excluded as unadmitted",
          int(w.prior_games_excluded_unadmitted) == 1, str(w.prior_games_excluded_unadmitted))
    check("the excluded game is the back-to-back leg g6",
          96 not in cand_for(cand, 10, "g7"),
          "player 96 appeared only in g6 and cannot be known at the cutoff")
    check("the window still USES five games (it reaches back, it does not shrink)",
          int(w.lookback_games_used) == ROSTER_LOOKBACK, str(w.lookback_games_used))
    check("the window is g1..g5",
          (w.admitted_window_first_game, w.admitted_window_last_game) == ("g1", "g5"),
          f"{w.admitted_window_first_game}..{w.admitted_window_last_game}")

    print("\n2. 'latest five SCHEDULED' vs 'latest five ADMITTED' -- the explicit contrast")
    scheduled_five = ["g2", "g3", "g4", "g5", "g6"]          # what v2 would have taken
    admitted_five = ["g1", "g2", "g3", "g4", "g5"]           # what v3 takes
    check("the two windows genuinely differ on this fixture",
          scheduled_five != admitted_five)
    got = cand_for(cand, 10, "g7")
    check("v3 picks the ADMITTED set: 91 (only in g1) IS a candidate", 91 in got)
    check("v3 picks the ADMITTED set: 96 (only in g6) is NOT a candidate", 96 not in got)
    check("the row is flagged as shifted vs the positional five",
          bool(w.window_shifted_vs_positional))
    check("candidates are exactly {1,2,3,91}", got == {1, 2, 3, 91}, str(sorted(got)))
    # g5 follows a two-day rest, so last night's box score question does not arise: its
    # window is the positional one and the flag must stay off. (g6 IS a back-to-back too --
    # it follows g5 by one day -- which is why the negative case is taken on g5.)
    g5w = window_for(win, 10, "g5")
    check("a game with no unadmitted prior is NOT flagged shifted",
          not bool(g5w.window_shifted_vs_positional)
          and int(g5w.prior_games_excluded_unadmitted) == 0,
          f"shifted={g5w.window_shifted_vs_positional} "
          f"excluded={g5w.prior_games_excluded_unadmitted}")

    print("\n3. equality is a VIOLATION, not a pass")
    eq_cut = dict(B2B_CUT)
    eq_cut["g7"] = pd.Timestamp("2024-06-11T12:00Z")         # EXACTLY g6's bound
    c_eq, w_eq = build_candidates(mp, eq_cut)
    check("cutoff == the prior game's bound excludes that game",
          96 not in cand_for(c_eq, 10, "g7"),
          "admission requires bound < cutoff, strictly")
    check("  ... and the window still ends at g5",
          window_for(w_eq, 10, "g7").admitted_window_last_game == "g5")
    lt_cut = dict(B2B_CUT)
    lt_cut["g7"] = pd.Timestamp("2024-06-11T12:00:00.000001Z")   # one microsecond later
    c_lt, _ = build_candidates(mp, lt_cut)
    check("one microsecond later, the same game IS admitted",
          96 in cand_for(c_lt, 10, "g7"),
          "the gate is a strict inequality, not a rounding")
    check("  ... and then 91 drops out again", 91 not in cand_for(c_lt, 10, "g7"))

    print("\n4. exact-tip rows and date-only rows admit genuinely different windows")
    # Same schedule, same games, two cutoff policies. The exact tip is late in the day, so
    # last night's box score IS knowable by then; the date-only cutoff is the prior evening.
    ex_cut = dict(B2B_CUT)
    ex_cut["g7"] = exact("2024-06-12T00:00Z")                # a 20:00 ET tip -> 22:30Z cutoff
    check("the exact cutoff is 2024-06-11T22:30Z",
          ex_cut["g7"] == pd.Timestamp("2024-06-11T22:30Z"), str(ex_cut["g7"]))
    c_ex, w_ex = build_candidates(mp, ex_cut)
    check("under an exact tip the back-to-back leg IS admitted",
          96 in cand_for(c_ex, 10, "g7"),
          "noon UTC on 06-11 is strictly before 22:30Z on 06-11")
    check("  ... so the window matches the positional five",
          not bool(window_for(w_ex, 10, "g7").window_shifted_vs_positional))
    check("  ... and the date-only twin does NOT admit it",
          96 not in cand_for(cand, 10, "g7"))
    check("the two policies therefore yield different candidate sets",
          cand_for(c_ex, 10, "g7") != cand_for(cand, 10, "g7"))
    # and an EARLY tip is stricter than a late one
    early = dict(B2B_CUT)
    early["g7"] = exact("2024-06-11T13:00Z")                 # 09:00 ET tip -> 11:30Z cutoff
    c_early, _ = build_candidates(mp, early)
    check("an early tip (cutoff 11:30Z) excludes last night again",
          96 not in cand_for(c_early, 10, "g7"),
          "the bound is noon UTC, which is after an 11:30Z cutoff")

    print("\n4b. the same two policies, produced by the real cutoff machinery")
    games = pd.DataFrame({"game_id": ["known_tip", "no_tip"],
                          "game_date": pd.to_datetime(["2024-06-11"] * 2),
                          "season": [2024, 2024]})
    obs = pd.DataFrame({"game_id": ["known_tip"],
                        "tip": pd.to_datetime(["2024-06-12T00:00Z"], utc=True),
                        "observed_at": pd.to_datetime(["2024-06-05T00:00Z"], utc=True),
                        "source": ["props"]})
    res, _audit = resolve_tip_times(games, obs)
    gg = apply_cutoff_policy(res.merge(games, on="game_id"))
    kt = gg[gg.game_id == "known_tip"].iloc[0]
    nt = gg[gg.game_id == "no_tip"].iloc[0]
    check("known tip -> exact policy at tip-90m",
          kt.cutoff_policy == POLICY_EXACT
          and kt.forecast_cutoff == pd.Timestamp("2024-06-11T22:30Z"), str(kt.forecast_cutoff))
    check("no tip -> date-only policy at 18:00Z the day before",
          nt.cutoff_policy == POLICY_DATE_ONLY
          and nt.forecast_cutoff == pd.Timestamp("2024-06-10T18:00Z"), str(nt.forecast_cutoff))
    check("the exact cutoff is LATER in the day than the date-only one",
          kt.forecast_cutoff > nt.forecast_cutoff)

    print("\n5. season openers, the season reset, and zero-candidate VISIBILITY")
    two_seasons = B2B + [
        ("h1", "2025-06-01", 10, 2025, [1, 2, 3]),           # opener: no in-season prior
        ("h2", "2025-06-04", 10, 2025, [1, 2, 3]),
        ("k1", "2026-05-01", 10, 2026, [1, 2, 3]),           # opener
        ("k2", "2026-05-02", 10, 2026, [1, 2, 3]),           # b2b with the opener
    ]
    cut2 = {g: date_only(d) for g, d, *_ in two_seasons}
    c2, w2 = build_candidates(master(two_seasons), cut2)
    check("a season opener yields ZERO candidates", cand_for(c2, 10, "h1") == set())
    check("  ... and is still a ROW in the window accounting",
          len(w2[(w2.team_id == 10) & (w2.game_id == "h1")]) == 1,
          "a coverage failure is reported, never dropped")
    check("  ... with a named reason",
          window_for(w2, 10, "h1").zero_candidate_reason
          == "season_opener_no_prior_in_season_game")
    check("the lookback RESETS at the season boundary: 91 cannot leak into 2025",
          91 not in cand_for(c2, 10, "h2"),
          "91 appeared only in 2024 and must not be inherited")
    check("  ... and the 2025 window uses only its own season's one prior game",
          int(window_for(w2, 10, "h2").lookback_games_used) == 1)
    check("in-season lookback still works after the reset",
          cand_for(c2, 10, "h2") == {1, 2, 3})
    k2 = window_for(w2, 10, "k2")
    check("a season's SECOND game played on a back-to-back has zero ADMITTED priors",
          int(k2.prior_games_in_season) == 1 and int(k2.prior_games_admitted) == 0,
          f"prior={k2.prior_games_in_season} admitted={k2.prior_games_admitted}")
    check("  ... so it has zero candidates, for a DIFFERENT named reason",
          int(k2.n_candidates) == 0
          and k2.zero_candidate_reason == "no_prior_in_season_game_admitted_before_cutoff",
          str(k2.zero_candidate_reason))
    check("  ... and it is still visible in the accounting, not deleted",
          {"h1", "k1", "k2"} <= set(w2.game_id))
    check("every team-game appears exactly once in the window accounting",
          len(w2) == master(two_seasons).groupby(["team_id", "game_id"]).ngroups
          and not w2.duplicated(["team_id", "game_id"]).any())

    print("\n6. the target game's own rows are never read for MEMBERSHIP")
    got = cand_for(cand, 10, "g7")
    check("a debut appearing ONLY in the target game is NOT a candidate", 77 not in got)
    blanked = mp.copy()
    m = blanked.game_id == "g7"
    blanked.loc[m, ["minutes", "pts", "fga"]] = np.nan
    c_blank, _ = build_candidates(blanked, B2B_CUT)
    check("blanking the target's labels does not change candidacy",
          cand_for(c_blank, 10, "g7") == got)
    mutated = mp.copy()
    mutated.loc[m, "minutes"] = 48.0
    c_mut, w_mut = build_candidates(mutated, B2B_CUT)
    check("inflating the target's labels does not change candidacy",
          cand_for(c_mut, 10, "g7") == got)
    check("  ... nor lookback_games_used",
          int(window_for(w_mut, 10, "g7").lookback_games_used) == int(w.lookback_games_used))
    dropped = mp[~((mp.game_id == "g7") & (mp.player_id == 1))]
    c_drop, _ = build_candidates(dropped, B2B_CUT)
    check("deleting a player's own target-game row does not remove him as a candidate",
          1 in cand_for(c_drop, 10, "g7"))

    print("\n7. every row's evidence strictly predates that row's cutoff")
    cut_col = cand.game_id.map(B2B_CUT)
    check("admitted_window_bound < forecast_cutoff on EVERY candidate row",
          bool((pd.to_datetime(cand.admitted_window_bound, utc=True)
                < pd.to_datetime(cut_col, utc=True)).all()))
    check("no candidate row carries a null window bound",
          not cand.admitted_window_bound.isna().any())
    check("lookback_games_used is never more than the lookback",
          bool((cand.lookback_games_used <= ROSTER_LOOKBACK).all())
          and bool((win.lookback_games_used <= ROSTER_LOOKBACK).all()))
    check("the window bound is the LATEST bound among the games used",
          window_for(win, 10, "g7").admitted_window_bound
          == pd.Timestamp("2024-06-10T12:00Z"),
          str(window_for(win, 10, "g7").admitted_window_bound) + " (= g5's bound)")

    print("\n8. obligations are per (team, game, player); row_uid is preserved but not unique")
    traded = [
        ("t1", "2024-06-01", 30, 2024, [1, 2, 55]),
        ("t2", "2024-06-04", 30, 2024, [1, 2, 55]),
        ("u1", "2024-06-01", 40, 2024, [7, 8]),
        ("u2", "2024-06-04", 40, 2024, [7, 8, 55]),          # 55 was traded to team 40
        ("x9", "2024-06-08", 30, 2024, [1, 2]),              # 30 vs 40, same game_id
        ("x9", "2024-06-08", 40, 2024, [7, 8, 55]),
    ]
    ct, wt = build_candidates(master(traded), {g: date_only(d) for g, d, *_ in traded})
    x9 = ct[ct.game_id == "x9"]
    check("a traded player is a candidate for BOTH clubs in their head-to-head game",
          {30, 40} <= set(x9[x9.player_id == 55].team_id), str(sorted(x9.team_id.unique())))
    check("  ... which is TWO obligations, not one",
          int((x9.player_id == 55).sum()) == 2)
    check("  ... sharing ONE row_uid, because pg_uid carries no team",
          x9[x9.player_id == 55].row_uid.nunique() == 1
          and pg_uid(55, "x9") in set(x9.row_uid))
    check("  ... flagged as shared on both rows",
          bool(x9[x9.player_id == 55].row_uid_shared_with_other_team.all()))
    check("obligation_uid IS unique and team-bearing",
          ct.obligation_uid.is_unique
          and ob_uid(30, 55, "x9") != ob_uid(40, 55, "x9"))
    check("v2's drop_duplicates('row_uid') would have deleted one of them",
          len(x9.drop_duplicates("row_uid")) == len(x9) - 1)

    print("\n9. the gate fails closed")
    try:
        build_candidates(mp, {g: c for g, c in B2B_CUT.items() if g != "g7"})
        ok = False
    except SystemExit:
        ok = True
    check("a game with no cutoff is refused, never guessed", ok)
    try:
        build_candidates(mp, {**B2B_CUT, "g7": pd.NaT})
        ok = False
    except SystemExit:
        ok = True
    check("a null cutoff is refused", ok)

    print(f"\n{PASSED}/{PASSED + len(FAILED)} tests passed")
    if FAILED:
        for f in FAILED:
            print(f"  - {f}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
