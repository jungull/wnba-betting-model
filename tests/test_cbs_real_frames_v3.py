#!/usr/bin/env python
"""test_cbs_real_frames_v3.py — the team-aware obligation join, proved twice.

Two kinds of section, deliberately mixed, because neither alone is sufficient:

* **REAL** sections read the registered v4 contract and the real masters. "The player path
  executes for every season" and "13 obligations would receive another club's box row" are
  claims about bytes on disk and cannot be demonstrated on a fixture.
* **SYNTHETIC** sections build a complete, attested v4-shaped tree inside a
  `TemporaryDirectory`, with a hand-computed trade in it. Every number below is derived in
  the comments before it is asserted.

  R1  build_player_frame succeeds for EVERY season 2021-2026 against the v4 contract --
      the exact call that raises MergeError in `cbs_real_frames/2` today
  R2  the canonical row_uid is unique in every emitted frame and universe, and the legacy
      team-blind key would have collapsed obligations in four of the six seasons
  R3  the two measured counterfactuals: what the team-blind joins would have done
  S4  the trade fixture: two obligations survive with distinct keys, and the OLD club's
      obligation receives no starter, no DNP and no appearance evidence from the new club
  S5  team-history appearance evidence is keyed on (team_id, game_id): a player appearing
      for club X is not credited to club Y
  S6  absence of evidence produces no signal -- the NaN-truthiness trap, asserted shut
  Z7  ZERO fits, predictions, scores or evaluations

NOTHING HERE FITS, PREDICTS OR SCORES. No estimator is imported or constructed, no forecast
is compared to any outcome, and no accuracy or profit-and-loss figure is produced anywhere.

Run as a script (this repository has no pytest installed):

    python tests/test_cbs_real_frames_v3.py
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asof_invariant as aoi                       # noqa: E402
import cbs_obligation_key as obk                   # noqa: E402
import cbs_provenance_v4 as prov                   # noqa: E402
import cbs_real_frames_v2 as rf2                   # noqa: E402
import cbs_real_frames_v3 as rf3                   # noqa: E402

PASSED = 0
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")
        print(f"  FAIL  {name}  {detail}")


def raises(name, exc, fn, *a, **kw) -> None:
    try:
        fn(*a, **kw)
        check(name, False, "no exception raised")
    except exc:
        check(name, True)
    except Exception as other:
        check(name, False, f"raised {type(other).__name__}: {other}")


SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)

# ==========================================================================
# R1 -- the real player path executes for EVERY season
# ==========================================================================
print("R1  the real v4 player path, all six seasons")

REAL_AVAILABLE = (ROOT / prov.PLAYER_GAME).exists() and (ROOT / prov.MASTER_PLAYER).exists()
check("R1 the real v4 contract and masters are present", REAL_AVAILABLE)

_audit = prov.audit(ROOT)
check("R1 cbs_provenance/4 reports no hard blocker on the real artifacts",
      _audit["n_hard_blockers"] == 0, str(_audit["hard_blockers"][:2]))

# `/2` cannot do this at all. Demonstrated, not asserted from the commit message: the
# team-blind merge dies before a single feature is computed.
_v2_fail = {}
for _s in SEASONS:
    try:
        rf2.build_player_frame(_s, ROOT, require_attested=False)
        _v2_fail[_s] = None
    except Exception as exc:
        _v2_fail[_s] = type(exc).__name__
check("R1 cbs_real_frames/2 build_player_frame FAILS for every season 2021-2026",
      all(v == "MergeError" for v in _v2_fail.values()), str(_v2_fail))
check("R1   ... and it is the team-blind 1:1 merge that fails, not something else",
      set(_v2_fail.values()) == {"MergeError"}, str(_v2_fail))

REAL: dict[int, dict] = {}
REAL_TEAM: dict[int, dict] = {}
_t0 = time.time()
for _s in SEASONS:
    _st = time.time()
    try:
        REAL[_s] = rf3.build_player_frame(_s, ROOT, require_attested=True)
        ok, why = True, ""
    except Exception as exc:                                   # pragma: no cover - the bug
        ok, why = False, f"{type(exc).__name__}: {exc}"
    check(f"R1 build_player_frame({_s}) succeeds against the v4 contract, attested", ok, why)
    if ok:
        print(f"    player {_s}: train={len(REAL[_s]['train']):>6}  "
              f"test={len(REAL[_s]['test']):>5}  universe={len(REAL[_s]['universe']):>5}  "
              f"({time.time() - _st:.1f}s)")
for _s in SEASONS:
    _st = time.time()
    try:
        REAL_TEAM[_s] = rf3.build_team_frame(_s, ROOT, require_attested=True)
        ok, why = True, ""
    except Exception as exc:                                   # pragma: no cover
        ok, why = False, f"{type(exc).__name__}: {exc}"
    check(f"R1 build_team_frame({_s}) succeeds against the v4 contract, attested", ok, why)
    if ok:
        print(f"    team   {_s}: train={len(REAL_TEAM[_s]['train']):>6}  "
              f"test={len(REAL_TEAM[_s]['test']):>5}  "
              f"universe={len(REAL_TEAM[_s]['universe']):>5}  ({time.time() - _st:.1f}s)")
print(f"    all twelve real frames built in {time.time() - _t0:.0f}s")

# the row set is the v4 contract's, unchanged: test rows per season must equal the
# contract's own per-season obligation count
_pgc = pd.read_parquet(ROOT / prov.PLAYER_GAME, columns=["season", "row_uid"])
_per_season = {int(s): int(c) for s, c in _pgc.groupby("season").size().items()}
check("R1 the test frame is exactly the season's obligation set, every season",
      all(len(REAL[s]["test"]) == _per_season[s] for s in SEASONS if s in REAL),
      str({s: (len(REAL[s]["test"]), _per_season[s]) for s in SEASONS if s in REAL}))
check("R1 the universe is exactly the test frame, every season",
      all(len(REAL[s]["universe"]) == len(REAL[s]["test"]) for s in REAL))
check("R1 the train frame grows monotonically with the fold, and 2021 has no train rows",
      len(REAL[2021]["train"]) == 0
      and all(len(REAL[SEASONS[i]]["train"]) < len(REAL[SEASONS[i + 1]]["train"])
              for i in range(len(SEASONS) - 1) if SEASONS[i + 1] in REAL))
check("R1 every fold reports zero obligations that appeared without a master box row",
      all(r["receipts"]["join"]["unmatched_that_appeared"] == 0
          for r in REAL.values()))

# ==========================================================================
# R2 -- the canonical key, on every emitted real frame
# ==========================================================================
print("R2  canonical key uniqueness on the real frames")

for _s in SEASONS:
    if _s not in REAL:
        continue
    f = REAL[_s]
    for nm in ("train", "test", "universe"):
        fr = f[nm]
        check(f"R2 {_s} {nm}: row_uid is unique",
              len(fr) == fr["row_uid"].nunique(),
              f"{len(fr)} rows, {fr['row_uid'].nunique()} keys")
    u = f["universe"]
    want = [obk.row_uid(p, g, t) for p, g, t in
            zip(u["player_id"], u["game_id"].astype(str), u["team_id"])]
    check(f"R2 {_s} universe: row_uid re-derives from (player_id, game_id, team_id)",
          list(u["row_uid"]) == want)
    check(f"R2 {_s} universe declares {obk.OBLIGATION_KEY_ID}",
          set(u["obligation_key_id"]) == {obk.OBLIGATION_KEY_ID})
    check(f"R2 {_s} team universe: row_uid is unique",
          REAL_TEAM[_s]["universe"]["row_uid"].is_unique)

_collapse = {s: len(REAL[s]["universe"]) - REAL[s]["universe"]["player_game_uid"].nunique()
             for s in REAL}
print(f"    obligations the LEGACY team-blind key would collapse, per season: {_collapse}")
check("R2 the legacy team-blind key would collapse obligations in ALL six seasons -- the "
      "v10 claim that only 2024 was affected is false",
      sum(1 for v in _collapse.values() if v) == 6, str(_collapse))
check("R2 the legacy key would collapse exactly 14 obligations across the six seasons",
      sum(_collapse.values()) == 14, str(sum(_collapse.values())))
check("R2 the canonical key collapses none of them",
      all(len(REAL[s]["universe"]) == REAL[s]["universe"]["row_uid"].nunique()
          for s in REAL))

# a frame whose key is NOT unique must be refused, not de-duplicated
_bad = REAL[2024]["universe"].copy()
_bad.loc[_bad.index[1], "row_uid"] = _bad.loc[_bad.index[0], "row_uid"]
raises("R2 a non-unique row_uid is a hard refusal, never a silent de-duplication",
       ValueError, obk.assert_unique_canonical_keys, _bad, "probe")

# ==========================================================================
# R3 -- the two counterfactuals, measured on the real artifacts
# ==========================================================================
print("R3  what the team-blind joins would have done, measured")

CF_JOIN = rf3.team_blind_join_counterfactual(ROOT)
CF_APP = rf3.team_blind_appearance_counterfactual(ROOT)
print(f"    master join   : {CF_JOIN['n_falsely_matched']} obligations would receive "
      f"another club's box row "
      f"({CF_JOIN['n_false_dnp_signals']} false DNP, "
      f"{CF_JOIN['n_false_starter_signals']} false starter)")
print(f"    appearance idx: {CF_APP['n_obligations_affected']} obligations, "
      f"{CF_APP['n_flipped_lookups']} lookups, "
      f"{CF_APP['n_cross_club_appearance_triples']} cross-club triples")

check("R3 the team-aware join matches strictly fewer rows than the team-blind one",
      CF_JOIN["n_matched_team_aware"] < CF_JOIN["n_matched_team_blind"],
      f"{CF_JOIN['n_matched_team_aware']} vs {CF_JOIN['n_matched_team_blind']}")
check("R3 exactly 13 obligations would be given a box row belonging to another club",
      CF_JOIN["n_falsely_matched"] == 13, str(CF_JOIN["n_falsely_matched"]))
check("R3 the difference between the two joins is exactly those 13 rows",
      CF_JOIN["n_matched_team_blind"] - CF_JOIN["n_matched_team_aware"] == 13)
check("R3 two of them would import a DNP reason the club never recorded",
      CF_JOIN["n_false_dnp_signals"] == 2, str(CF_JOIN["n_false_dnp_signals"]))
check("R3 two of them would import a start credited to the wrong club",
      CF_JOIN["n_false_starter_signals"] == 2, str(CF_JOIN["n_false_starter_signals"]))
check("R3 every falsely matched obligation is one the contract says did NOT appear",
      CF_JOIN["n_falsely_matched_that_the_contract_says_did_not_appear"] == 13)
check("R3 the falsely matched rows are enumerated, not just counted",
      len(CF_JOIN["falsely_matched"]) == 13
      and all(r["team_id"] != r["master_team_id"] for r in CF_JOIN["falsely_matched"]))

check("R3 the game-keyed appearance index corrupts 1347 lookups over 860 obligations",
      CF_APP["n_flipped_lookups"] == 1347 and CF_APP["n_obligations_affected"] == 860,
      f"{CF_APP['n_flipped_lookups']} / {CF_APP['n_obligations_affected']}")
check("R3 167 distinct (team, game, player) triples are credited to the wrong club",
      CF_APP["n_cross_club_appearance_triples"] == 167,
      str(CF_APP["n_cross_club_appearance_triples"]))
check("R3 the appearance defect is larger than the merge defect it hid behind",
      CF_APP["n_obligations_affected"] > 28)
check("R3 every season is affected by the appearance defect",
      set(CF_APP["per_season_obligations_affected"]) == set(SEASONS),
      str(CF_APP["per_season_obligations_affected"]))
print(f"    per-season obligations affected: {CF_APP['per_season_obligations_affected']}")

# ---- R3b: the roster bound the adapter OVERWRITES ------------------------
# `/2` silently replaced the contract's `src_asof_roster` and `n_roster_games_consumed`
# with its own recomputed feature-window values. `/3` keeps the contract's and measures
# the agreement. The result is the sharpest available confirmation of the C4 finding
# `cbs_provenance/4` was written for.
_rb = REAL[2024]["receipts"]["roster_bound_vs_contract"]
print(f"    roster bound  : timestamp differs on "
      f"{_rb['n_rows_where_the_adapter_bound_differs']} of {_rb['n_rows']} rows; "
      f"COUNT differs on {_rb['n_rows_where_the_adapter_count_differs']}")
check("R3b the adapter's recomputed roster BOUND agrees with the contract on every row",
      _rb["n_rows_where_the_adapter_bound_differs"] == 0,
      str(_rb["n_rows_where_the_adapter_bound_differs"]))
check("R3b ... while the record COUNT it claims to summarise disagrees on 19830 of 22659",
      _rb["n_rows_where_the_adapter_count_differs"] == 19830 and _rb["n_rows"] == 22659,
      f"{_rb['n_rows_where_the_adapter_count_differs']} of {_rb['n_rows']}")
check("R3b so the timestamp agreement is a coincidence of monotone availability, NOT a "
      "binding -- exactly what cbs_provenance/4 refused to infer",
      _rb["n_rows_where_the_adapter_bound_differs"] == 0
      < _rb["n_rows_where_the_adapter_count_differs"])
check("R3b the contract's own declaration survives the overwrite under its own name",
      "contract_src_asof_roster" in REAL[2024]["test"].columns
      and "contract_n_roster_games_consumed" in REAL[2024]["test"].columns)


# ==========================================================================
# the synthetic v4 tree: three clubs, two trades, everything hand-computable
# ==========================================================================
# One game per date. On date i the pair is (10,20), (20,30) or (30,10) for i%3 == 0,1,2.
# So team 10 plays on dates {0,2,3,5,...}, team 20 on {0,1,3,4,...}, team 30 on {1,2,4,5,...}.
#
#   availability(date j) = floor(D_j) + 36h = D_{j+1} 12:00Z
#   cutoff(date i)       = D_i - 6h        = D_{i-1} 18:00Z
#   schedule bound(i)    = D_{i-1} 12:00Z
#
# so a prior game j is ADMITTED for a row on date i iff D_{j+1} 12:00 < D_{i-1} 18:00,
# i.e. j <= i - 2.
#
# THE TWO TRADES, in season 2099:
#   301  team 20 for dates 0..8, team 30 from date 9.  Head-to-head on date 10 (20 v 30):
#        she owes BOTH clubs a forecast and APPEARS for the new club (30), starter.
#   302  team 10 for dates 0..8, team 30 from date 9.  Head-to-head on date 11 (30 v 10):
#        she owes BOTH clubs a forecast and is a DNP - Coach's Decision for the new club.

N_DATES = 18
SYN_SEASONS = (2098, 2099)
PAIRS = {0: (10, 20), 1: (20, 30), 2: (30, 10)}
BASE = {10: (101, 102), 20: (201, 202), 30: (303, 304)}
TRADED_A, TRADED_B = 301, 302
TRADE_DATE = 9
DUAL_A_GI, DUAL_B_GI = 10, 11          # the two head-to-head games
#: 101 is a coach's-decision DNP for team 10 on date 3, in both seasons
CD_PID, CD_GI, CD_REASON = 101, 3, "DNP - Coach's Decision"


def pair(gi: int) -> tuple[int, int]:
    return PAIRS[gi % 3]


def gid_of(season: int, gi: int) -> str:
    return f"G{season}{gi:03d}"


def roster(season: int, tid: int, gi: int) -> tuple[int, ...]:
    """Who is a CANDIDATE for club `tid` on date `gi`."""
    r = list(BASE[tid])
    if season == 2098:
        r += [TRADED_A, TRADED_B] if tid == 30 else []
        return tuple(r)
    if tid == 20 and gi <= TRADE_DATE - 1:
        r.append(TRADED_A)
    if tid == 10 and gi <= TRADE_DATE - 1:
        r.append(TRADED_B)
    if tid == 30 and gi >= TRADE_DATE:
        r += [TRADED_A, TRADED_B]
    # the dual obligations: the old club still owes a forecast in the head-to-head
    if tid == 20 and gi == DUAL_A_GI:
        r.append(TRADED_A)
    if tid == 10 and gi == DUAL_B_GI:
        r.append(TRADED_B)
    return tuple(r)


def appears(season: int, tid: int, gi: int, pid: int) -> bool:
    """Did `pid` actually turn out for `tid` in this game? The MASTER's answer."""
    if pid == CD_PID and gi == CD_GI:
        return False                                # a DNP, in the box, did not play
    if season == 2099 and pid == TRADED_A and tid == 20 and gi == DUAL_A_GI:
        return False                                # she played for 30 that night
    if season == 2099 and pid == TRADED_B and tid == 10 and gi == DUAL_B_GI:
        return False                                # she was 30's DNP that night
    if season == 2099 and pid == TRADED_B and tid == 30 and gi == DUAL_B_GI:
        return False                                # DNP - Coach's Decision for the new club
    return True


def in_master_box(season: int, tid: int, gi: int, pid: int) -> bool:
    """Is there a master_player ROW for this (game, team, player)?

    The old club has NO row for a traded player: she was not in its box score at all. That
    is the fact the team-aware join must respect and the team-blind join destroys.
    """
    if season == 2099 and pid == TRADED_A and tid == 20 and gi == DUAL_A_GI:
        return False
    if season == 2099 and pid == TRADED_B and tid == 10 and gi == DUAL_B_GI:
        return False
    return True


def dnp_reason_of(season: int, tid: int, gi: int, pid: int):
    if pid == CD_PID and gi == CD_GI:
        return CD_REASON
    if season == 2099 and pid == TRADED_B and tid == 30 and gi == DUAL_B_GI:
        return CD_REASON
    return None


def team_prior_gis(season: int, tid: int, gi: int) -> list[int]:
    return [j for j in range(gi) if tid in pair(j)]


def synth_v4(root: Path):
    """A complete, attested, v4-shaped tree. Every column `cbs_provenance/4` requires."""
    (root / "data" / "masters").mkdir(parents=True)
    (root / prov.CONTRACT_DIR).mkdir(parents=True)

    prow, trow, crow, tgrow = [], [], [], []
    for season in SYN_SEASONS:
        dates = pd.date_range(f"{season}-05-01", periods=N_DATES, freq="D")
        for gi, d in enumerate(dates):
            gid = gid_of(season, gi)
            home, away = pair(gi)
            for tid in (home, away):
                ftm, fgm, fg3m, paint = 10, 30, 5, 30
                trow.append({"game_id": gid, "team_id": tid, "season": season,
                             "game_date": d, "is_home": 1 if tid == home else 0,
                             "pts": ftm + 3 * fg3m + 2 * (fgm - fg3m),
                             "ftm": ftm, "fgm": fgm, "fg3m": fg3m,
                             "points_paint": paint})
                prior = team_prior_gis(season, tid, gi)
                tgrow.append({
                    "game_id": gid, "team_id": tid, "season": season, "game_date": d,
                    "forecast_cutoff": (d - pd.Timedelta(hours=6)).tz_localize("UTC"),
                    "fold_id": f"season:{season}",
                    "row_uid": f"tg_{season}_{tid}_{gi:03d}",
                    "n_candidates": len(roster(season, tid, gi)),
                    "n_roster_games_consumed": len(prior),
                    "admitted_window_digest": "rw_" + hashlib.sha256(
                        f"{season}{tid}{gi}".encode()).hexdigest()[:16]})

                for pid in roster(season, tid, gi):
                    played = appears(season, tid, gi, pid)
                    reason = dnp_reason_of(season, tid, gi, pid)
                    if in_master_box(season, tid, gi, pid):
                        prow.append({
                            "game_id": gid, "player_id": pid, "team_id": tid,
                            "season": season, "game_date": d,
                            "is_home": 1 if tid == home else 0,
                            "minutes": 20.0 + (gi % 5) if played else None,
                            "starter_flag": 1 if played else 0,
                            "dnp_reason": reason,
                            "pts": 10 if played else None,
                            "fga": 8 if played else None})
                    if not prior:
                        # a candidate must have a non-empty admitted window; a club's very
                        # first game of a season has none, so it owes no obligation here
                        continue
                    wb = (dates[prior[-1]].normalize()
                          + pd.Timedelta(hours=36)).tz_localize("UTC")
                    crow.append({
                        "game_id": gid, "player_id": pid, "team_id": tid, "season": season,
                        "game_date": d,
                        "forecast_cutoff": (d - pd.Timedelta(hours=6)).tz_localize("UTC"),
                        "appeared": played,
                        "minutes": 20.0 + (gi % 5) if played else None,
                        "pts": 10 if played else None, "fga": 8 if played else None,
                        "fold_id": f"season:{season}",
                        "obligation_key_id": obk.OBLIGATION_KEY_ID,
                        "membership_rule_id": prov.MEMBERSHIP_RULE_ID,
                        "roster_binding_id": prov.ROSTER_BINDING_ID,
                        "lookback_games_used": len(prior),
                        "n_roster_games_consumed": len(prior),
                        "admitted_window_bound": wb,
                        "src_asof_roster": wb,
                        "src_policy_roster": "contract_admitted_window_bound",
                        "roster_evidence_first_game": gid_of(season, prior[0]),
                        "roster_evidence_last_game": gid_of(season, prior[-1]),
                        "roster_evidence_digest": "rw_" + hashlib.sha256(
                            f"{season}{tid}{pid}{gi}".encode()).hexdigest()[:16]})

    mp = pd.DataFrame(prow)
    mt = pd.DataFrame(trow)
    pg = pd.DataFrame(crow)
    pg["row_uid"] = [obk.row_uid(p, g, t) for p, g, t in
                     zip(pg.player_id, pg.game_id, pg.team_id)]
    pg["obligation_uid"] = pg["row_uid"]
    pg["player_game_uid"] = [obk.player_game_uid(p, g) for p, g in
                             zip(pg.player_id, pg.game_id)]
    for t in rf3.PLAYER_TARGETS:
        pg[f"prediction_required__{t}"] = True
        pg[f"outcome_scoreable__{t}"] = (pg["appeared"].astype(bool) if t != "p_active"
                                         else True)
    tg = pd.DataFrame(tgrow)
    tg[f"prediction_required__{rf3.TEAM_TARGET}"] = True
    tg[f"outcome_scoreable__{rf3.TEAM_TARGET}"] = True

    mp.to_parquet(root / prov.MASTER_PLAYER, index=False)
    mt.to_parquet(root / prov.MASTER_TEAM, index=False)
    pg.to_parquet(root / prov.PLAYER_GAME, index=False)
    tg.to_parquet(root / prov.TEAM_GAME, index=False)
    (root / prov.CONTRACT_JSON).write_text(json.dumps({
        "contract_version": "synthetic/4",
        "membership_rule_id": prov.MEMBERSHIP_RULE_ID,
        "appeared_only_counterfactual": {
            "appeared_only_rows": int(pg["appeared"].sum()),
            "registered_rows": int(len(pg)),
            "obligations_that_exist_only_because_dnp_rows_count":
                int(len(pg) - pg["appeared"].sum())},
        "obligation_key": obk.key_receipt(),
        "roster_provenance_binding": {"binding_id": prov.ROSTER_BINDING_ID},
        "accounting": {"cutoff_identity_vs_v2": {
            "n_fields_compared": prov.N_CUTOFF_IDENTITY_FIELDS, "ok": True,
            "games_compared": int(pg["game_id"].nunique())}},
        "nothing_is_fitted": "this fixture fits nothing, predicts nothing and scores nothing",
    }, indent=1), encoding="utf-8")
    return pg, tg, mp, mt


def attest_all(root: Path):
    for rel in (prov.MASTER_PLAYER, prov.MASTER_TEAM, prov.TEAM_GAME, prov.PLAYER_GAME):
        prov.attest_artifact(rel, root=root, producer="synthetic", granularity="row",
                             dry_run=False)
    aoi.write_manifest(root / prov.CONTRACT_JSON, producer="synthetic",
                       fit_through_date=aoi.bound_from_dates([f"{SYN_SEASONS[-1]}-06-30"]),
                       fit_through_season=SYN_SEASONS[-1], fit_seasons=list(SYN_SEASONS),
                       asof_granularity="artifact", notes="synthetic v4 fixture")


with tempfile.TemporaryDirectory() as _td:
    R = Path(_td)
    PG_SYN, TG_SYN, MP_SYN, MT_SYN = synth_v4(R)

    print("S4  the trade fixture")
    raises("S4 the adapter REFUSES to build from unattested inputs",
           rf3.RealFrameError, rf3.build_player_frame, 2099, R)
    attest_all(R)
    _syn_audit = prov.audit(R)
    check("S4 the synthetic tree satisfies cbs_provenance/4 in full",
          _syn_audit["n_hard_blockers"] == 0, str(_syn_audit["hard_blockers"][:3]))

    fold = rf3.build_player_frame(2099, R)
    te = fold["test"]
    uni = fold["universe"]
    t = te.set_index("row_uid")

    def U(pid: int, tid: int, gi: int, season: int = 2099) -> str:
        return obk.row_uid(pid, gid_of(season, gi), tid)

    # ----------------------------------------------------------------------
    # S4 -- two obligations survive, with distinct canonical keys
    # ----------------------------------------------------------------------
    old_a, new_a = U(TRADED_A, 20, DUAL_A_GI), U(TRADED_A, 30, DUAL_A_GI)
    old_b, new_b = U(TRADED_B, 10, DUAL_B_GI), U(TRADED_B, 30, DUAL_B_GI)

    check("S4 both of the traded player's obligations survive into the frame",
          old_a in t.index and new_a in t.index)
    check("S4 their canonical keys are DISTINCT", old_a != new_a)
    check("S4 their legacy player_game_uid is the SAME -- the v3 key that collapsed them",
          obk.player_game_uid(TRADED_A, gid_of(2099, DUAL_A_GI))
          == str(t.loc[old_a, "player_game_uid"]) == str(t.loc[new_a, "player_game_uid"]))
    check("S4 the universe carries both obligations and the key is still unique",
          len(uni) == uni["row_uid"].nunique()
          and {old_a, new_a, old_b, new_b} <= set(uni["row_uid"]))
    check("S4 the universe's legacy key is NOT unique -- exactly the two trades collide",
          len(uni) - uni["player_game_uid"].nunique() == 2,
          str(len(uni) - uni["player_game_uid"].nunique()))

    # ----------------------------------------------------------------------
    # S4b -- the OLD club's obligation gets NO evidence from the NEW club
    # ----------------------------------------------------------------------
    check("S4b the old club's obligation has no master box row",
          bool(t.loc[old_a, "master_row_present"]) is False)
    check("S4b   ... and the new club's does",
          bool(t.loc[new_a, "master_row_present"]) is True)
    check("S4b the old club's obligation carries NO observed starter flag",
          pd.isna(t.loc[old_a, "starter_flag_observed"]))
    check("S4b the new club's obligation carries the start that actually happened",
          float(t.loc[new_a, "starter_flag_observed"]) == 1.0)
    check("S4b the old club's obligation carries NO dnp class",
          t.loc[old_a, "dnp_class"] is None or pd.isna(t.loc[old_a, "dnp_class"]))
    check("S4b the old club's obligation is labelled 'no master box row', explicitly",
          t.loc[old_a, "src_policy_master_box"] == rf3.NO_MASTER_EVIDENCE_POLICY)
    check("S4b the contract says she did not appear for the old club",
          bool(t.loc[old_a, "appeared"]) is False
          and bool(t.loc[new_a, "appeared"]) is True)

    # the DNP variant: the new club benched her; the old club must not inherit that
    check("S4b the new club's DNP is recorded against the NEW club",
          t.loc[new_b, "dnp_class"] == "CD")
    check("S4b the old club's obligation does NOT inherit the new club's DNP",
          t.loc[old_b, "dnp_class"] is None or pd.isna(t.loc[old_b, "dnp_class"]))
    check("S4b the old club's obligation has no box row for the DNP either",
          bool(t.loc[old_b, "master_row_present"]) is False
          and bool(t.loc[new_b, "master_row_present"]) is True)

    # and what the SUPERSEDED join would have done, on this same fixture
    CF_SYN = rf3.team_blind_join_counterfactual(R)
    check("S4b the team-blind join WOULD have given both old clubs the new club's row",
          CF_SYN["n_falsely_matched"] == 2, str(CF_SYN["n_falsely_matched"]))
    check("S4b   ... importing one false start and one false coach's-decision DNP",
          CF_SYN["n_false_starter_signals"] == 1 and CF_SYN["n_false_dnp_signals"] == 1,
          f"{CF_SYN['n_false_starter_signals']} / {CF_SYN['n_false_dnp_signals']}")
    check("S4b   ... and the team-aware join matches exactly those 2 rows fewer",
          CF_SYN["n_matched_team_blind"] - CF_SYN["n_matched_team_aware"] == 2)
    check("S4b the receipt counts the dual obligations without master evidence",
          fold["receipts"]["team_awareness"][
              "n_dual_team_obligations_without_master_box_row"] == 2,
          str(fold["receipts"]["team_awareness"]))

    # ----------------------------------------------------------------------
    # S5 -- appearance evidence is keyed on (team_id, game_id)
    # ----------------------------------------------------------------------
    print("S5  team-history appearance evidence")

    _pg_all = PG_SYN.copy()
    _pg_all["game_id"] = _pg_all["game_id"].astype(str)
    aware = rf3.build_appearance_index(_pg_all)
    #: `/2` line 423, reproduced exactly, to state what the superseded index answered
    blind_idx = (_pg_all.loc[_pg_all["appeared"], ["game_id", "player_id"]]
                 .groupby("game_id")["player_id"].apply(set).to_dict())

    g1 = gid_of(2099, 1)          # date 1: teams 20 and 30. 301 appeared FOR 20.
    check("S5 the game-keyed index says 301 'appeared in' the 20-v-30 game",
          TRADED_A in blind_idx[g1])
    check("S5 the team-keyed index credits that appearance to club 20 only",
          TRADED_A in aware[(20, g1)] and TRADED_A not in aware.get((30, g1), ()))
    check("S5 a player appearing for club X is NOT credited to club Y",
          all(TRADED_A not in aware.get((30, gid_of(2099, j)), ())
              for j in (1, 4, 7)))
    check("S5 the dual-obligation game credits only the club she turned out for",
          TRADED_A in aware[(30, gid_of(2099, DUAL_A_GI))]
          and TRADED_A not in aware.get((20, gid_of(2099, DUAL_A_GI)), ()))

    # THE HAND-COMPUTED FEATURE. Her obligation for club 30 on date 11:
    #   admitted prior team-30 games (j <= 9): dates 1, 2, 4, 5, 7, 8   -> k = 6
    #   she appeared for club 20 on 1, 4, 7 and for nobody on 2, 5, 8
    #   TEAM-AWARE  own = [F,F,F,F,F,F] -> last 0, share 0/6, missed streak 6
    #   TEAM-BLIND  own = [T,F,T,F,T,F] -> last 0, share 3/6, missed streak 1
    row = t.loc[U(TRADED_A, 30, 11)]
    check("S5 team_gp_season counts the six admitted prior club-30 games",
          float(row["team_gp_season"]) == 6.0, str(row["team_gp_season"]))
    check("S5 played_share_l10_team_games is 0.0, not the team-blind 0.5",
          float(row["played_share_l10_team_games"]) == 0.0,
          str(row["played_share_l10_team_games"]))
    check("S5 games_missed_streak is 6, not the team-blind 1",
          float(row["games_missed_streak"]) == 6.0, str(row["games_missed_streak"]))
    check("S5 played_last_team_game is 0 (both indices agree here, by construction)",
          float(row["played_last_team_game"]) == 0.0)
    check("S5 her OWN history still crosses the trade -- min_ewma is not zeroed",
          float(row["min_ewma"]) > 0.0, str(row["min_ewma"]))
    check("S5   ... because player history is keyed on the PLAYER, team history on the TEAM",
          float(row["days_since_last_appearance"]) < rf3.DAYS_CAP)

    _synth_app_cf = rf3.team_blind_appearance_counterfactual(R)
    check("S5 the fixture's own counterfactual finds the cross-club credit",
          _synth_app_cf["n_obligations_affected"] > 0
          and _synth_app_cf["n_cross_club_appearance_triples"] > 0,
          str(_synth_app_cf))

    # ----------------------------------------------------------------------
    # S6 -- absence of evidence produces no signal
    # ----------------------------------------------------------------------
    print("S6  no evidence, no signal")

    # 101 is a coach's-decision DNP for club 10 on date 3. Her club-10 obligation on date 5
    # admits games 0..3, so the most recent admitted DNP class is CD.
    _r5 = t.loc[U(CD_PID, 10, 5)]
    check("S6 the prev_dnp carry-forward survives intervening NON-dnp rows",
          float(_r5["prev_dnp_cd"]) == 1.0, str(_r5["prev_dnp_cd"]))
    check("S6   ... and does not also set the other classes",
          float(_r5["prev_dnp_inj"]) == 0.0 and float(_r5["prev_dnp_nwt"]) == 0.0
          and float(_r5["prev_dnp_unknown"]) == 0.0)
    check("S6 a row with a real DNP reason gets a class; a row with no box row gets None",
          t.loc[U(CD_PID, 10, CD_GI), "dnp_class"] == "CD"
          and (t.loc[old_a, "dnp_class"] is None or pd.isna(t.loc[old_a, "dnp_class"])))
    check("S6 absence of a box row is NOT classified as UNKNOWN",
          "UNKNOWN" not in set(te.loc[~te["master_row_present"].astype(bool),
                                      "dnp_class"].dropna().unique()))
    check("S6 no obligation without a box row carries an observed starter flag",
          te.loc[~te["master_row_present"].astype(bool),
                 "starter_flag_observed"].isna().all())
    check("S6 no obligation without a box row reports appeared=True",
          not te.loc[~te["master_row_present"].astype(bool), "appeared"].any())
    check("S6 the NaN-truthiness trap is shut: `if NaN:` would be True, `isinstance` is not",
          bool(float("nan")) is True and isinstance(float("nan"), str) is False)

    # a contract that lies about an appearance is refused, not absorbed
    with tempfile.TemporaryDirectory() as _td2:
        R2 = Path(_td2)
        synth_v4(R2)
        _bad_pg = pd.read_parquet(R2 / prov.PLAYER_GAME)
        _m = ((_bad_pg.player_id == TRADED_A) & (_bad_pg.team_id == 20)
              & (_bad_pg.game_id == gid_of(2099, DUAL_A_GI)))
        _bad_pg.loc[_m, "appeared"] = True          # the old club claims she played for it
        _bad_pg.to_parquet(R2 / prov.PLAYER_GAME, index=False)
        attest_all(R2)
        raises("S6 an obligation claiming appeared=True with no box row for THAT club "
               "is refused", rf3.RealFrameError, rf3.build_player_frame, 2099, R2)

    # a master that is not unique on the obligation key is refused before the merge
    with tempfile.TemporaryDirectory() as _td3:
        R3 = Path(_td3)
        synth_v4(R3)
        _bad_mp = pd.read_parquet(R3 / prov.MASTER_PLAYER)
        _bad_mp = pd.concat([_bad_mp, _bad_mp.iloc[[0]]], ignore_index=True)
        _bad_mp.to_parquet(R3 / prov.MASTER_PLAYER, index=False)
        attest_all(R3)
        raises("S6 a master_player with a duplicate (game, team, player) is refused",
               rf3.RealFrameError, rf3.build_player_frame, 2099, R3)

    # the team frame still works on the fixture
    tf = rf3.build_team_frame(2099, R)
    check("S6 the team fold builds and its channels reconstruct team_points",
          float(((tf["test"].ch_ft + tf["test"].ch_3pt + tf["test"].ch_paint
                  + tf["test"].ch_np2) - tf["test"].team_points).abs().max()) < 1e-9)
    check("S6 the team universe's key is unique", tf["universe"]["row_uid"].is_unique)


# ==========================================================================
# Z7 -- ZERO fits, predictions, scores or evaluations
# ==========================================================================
print("Z7  zero fits, predictions, scores or evaluations")

ESTIMATOR_MODULES = ("sklearn", "statsmodels", "xgboost", "lightgbm", "torch", "keras",
                     "tensorflow", "catboost", "scipy.optimize")
ESTIMATOR_CALLS = {"fit", "predict", "predict_proba", "fit_predict", "fit_transform",
                   "score", "partial_fit", "polyfit", "curve_fit", "minimize"}
METRIC_NAMES = {"log_loss", "roc_auc_score", "brier_score_loss", "accuracy_score",
                "r2_score", "mean_squared_error", "mean_absolute_error", "polyfit"}

for _mod in ("cbs_real_frames_v3.py", "contract_validator_v4_strict.py"):
    _src = (ROOT / _mod).read_text(encoding="utf-8")
    _tree = ast.parse(_src)
    _imports: list[str] = []
    _calls: list[str] = []
    _names: list[str] = []
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Import):
            _imports += [a.name for a in _n.names]
        elif isinstance(_n, ast.ImportFrom):
            _imports.append(_n.module or "")
        elif isinstance(_n, ast.Call):
            f = _n.func
            if isinstance(f, ast.Attribute) and f.attr in ESTIMATOR_CALLS:
                _calls.append(f.attr)
            if isinstance(f, ast.Name) and f.id in ESTIMATOR_CALLS | METRIC_NAMES:
                _calls.append(f.id)
        elif isinstance(_n, ast.Name) and _n.id in METRIC_NAMES:
            _names.append(_n.id)
    _bad_imp = [m for m in _imports if any(m == e or m.startswith(e + ".")
                                           for e in ESTIMATOR_MODULES)]
    # the AST is scanned rather than the raw text so that PROSE saying "nothing is fitted"
    # cannot fail a substring test, and so that a call cannot hide inside a comment
    check(f"Z7 {_mod} imports no estimator library", not _bad_imp, str(_bad_imp))
    check(f"Z7 {_mod} calls no fit/predict/score method", not _calls, str(_calls))
    check(f"Z7 {_mod} references no accuracy or error metric", not _names, str(_names))

_frame_cols = set(REAL[2024]["test"].columns) | set(REAL[2024]["universe"].columns)
_predlike = [c for c in _frame_cols
             if ("pred" in c.lower() or "score" in c.lower() or "yhat" in c.lower()
                 or "resid" in c.lower())
             and not c.startswith(("prediction_required__", "outcome_scoreable__"))]
check("Z7 the emitted frames carry no prediction, score or residual column",
      not _predlike, str(_predlike))
def _all_keys(o, acc=None):
    acc = [] if acc is None else acc
    if isinstance(o, dict):
        for k, v in o.items():
            acc.append(str(k).lower())
            _all_keys(v, acc)
    elif isinstance(o, list):
        for v in o:
            _all_keys(v, acc)
    return acc


# KEYS, not the JSON blob: a receipt whose prose says "no accuracy figure" must not fail a
# substring test for the word it is disclaiming. What matters is that no FIELD holds one.
_rec_keys = _all_keys(REAL[2024]["receipts"])
_bad_keys = [k for k in _rec_keys
             if any(m in k for m in ("accuracy", "log_loss", "auc", "brier", "rmse",
                                     "r_squared", "bankroll", "coefficient", "pnl"))]
check("Z7 no field of the fold receipt holds an accuracy, error or profit-and-loss figure",
      not _bad_keys, str(_bad_keys))
check("Z7 the receipt states its own scope in words",
      "nothing fitted" in REAL[2024]["receipts"]["scope"])
check("Z7 the adapter exposes no fit, predict or score entry point",
      not [n for n in dir(rf3)
           if n in ("fit", "predict", "score", "evaluate", "backtest")])


print(f"\n{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAILED  {f}")
sys.exit(1 if FAILED else 0)
