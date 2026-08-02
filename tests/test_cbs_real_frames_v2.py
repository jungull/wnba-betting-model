#!/usr/bin/env python
"""test_cbs_real_frames_v2.py — synthetic suite for `cbs_real_frames/2`.

**Synthetic only.** Every section builds its own miniature contract and masters
inside a `TemporaryDirectory`; the real artifacts are never read. No model is
fitted, no prediction is produced, no accuracy, coverage or profitability figure
is computed, and no feature is related to any outcome. The suite builds frames,
counts rows and timestamps, and compares them to values computed by hand in the
comments below.

  T1  the frozen DNP taxonomy: all 22 known strings, the unknown fall-through,
      and the reclassification count against the prefix rule
  T2  THE CENTRAL REGRESSION — a returning player whose TEAM history is newer
      than his own, whose composite `feature_asof` must equal the TEAM bound
  T3  each source bound against a hand-computed expected value
  T4  `no_prior_game_admitted` only where a source genuinely consumed nothing
  T5  the availability-admitted history rule: availability == cutoff is EXCLUDED
  T6  the channel identity pts == ftm + 3*fg3m + 2*(fgm - fg3m)

THE FIXTURE ARITHMETIC, ONCE
----------------------------
One game per calendar date, teams 10 and 20 playing each other. For game index
`i` on date `D_i = <season>-05-(1+i)`:

    availability(j) = floor(D_j) + 36h  =  <season>-05-(2+j) 12:00Z
    schedule bound  = floor(D_i) - 1d + 12h  =  <season>-05-(i) 12:00Z
    default cutoff  = D_i - 6h  =  <season>-05-(i) 18:00Z

so under the default cutoff a prior game `j` is admitted iff `2+j <= i`, i.e.
`j <= i-2`, and the admitted count is `max(i-1, 0)`. The two special rows below
carry deliberately different cutoffs to move that boundary.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asof_invariant as aoi  # noqa: E402
import cbs_provenance_v3 as prov  # noqa: E402  (v10 artifact set)
import cbs_real_frames_v2 as rf2  # noqa: E402

PASSED = 0
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")


def raises(name, exc, fn, *a, **kw) -> None:
    try:
        fn(*a, **kw)
        check(name, False, "no exception raised")
    except exc:
        check(name, True)
    except Exception as other:
        check(name, False, f"raised {type(other).__name__}: {other}")


def T(s: str) -> pd.Timestamp:
    """A UTC instant, written the way the fixture arithmetic writes it."""
    return pd.Timestamp(s, tz="UTC")


# --------------------------------------------------------------------------
# T1 -- the frozen DNP taxonomy
# --------------------------------------------------------------------------

#: The 22 exact strings in `data/masters/master_player.parquet`, each with the
#: class this module freezes for it. Hand-written here so the test states the
#: expectation independently of the table it is testing.
EXPECTED_DNP = {
    "DNP - Coach's Decision": "CD",
    "DND - Coach's Decision": "CD",
    "DNP - Rest": "CD",
    "DND - Rest": "CD",
    "NWT - Injury/Illness": "NWT",
    "NWT - Not With Team": "NWT",
    "NWT - Personal": "NWT",
    "NWT - Health and Safety Protocols": "NWT",
    "NWT - Rest": "NWT",
    "NWT - League Suspension": "NWT",
    "NWT_CONCUSSION_PROTOCOL": "NWT",
    "NWT_TEAM_SUSPENSION": "NWT",
    "DND - Injury/Illness": "INJ",
    "DNP - Injury/Illness": "INJ",
    "DND - Concussion Protocol": "INJ",
    "DNP - Concussion Protocol": "INJ",
    "DND - Health and Safety Protocols": "INJ",
    "DND_HEALTH_AND_SAFETY_PROTOCOLS": "INJ",
    "DND-Return to Competition Reconditioning": "INJ",
    "DND - Personal": "UNKNOWN",
    "DNP - Personal": "UNKNOWN",
    "DND_INELIGIBLE_TO_PLAY": "UNKNOWN",
}

check("T1 the table covers exactly 22 reason strings",
      len(rf2.DNP_CLASS_TABLE) == 22, str(len(rf2.DNP_CLASS_TABLE)))
check("T1 the table's keys are exactly the 22 known strings",
      set(rf2.DNP_CLASS_TABLE) == set(EXPECTED_DNP),
      str(set(rf2.DNP_CLASS_TABLE) ^ set(EXPECTED_DNP)))

_wrong = {k: (rf2.dnp_class(k), v) for k, v in EXPECTED_DNP.items()
          if rf2.dnp_class(k) != v}
check("T1 every one of the 22 strings maps to its expected class",
      not _wrong, f"{len(_wrong)} disagree: {_wrong}")

check("T1 the SCREAMING_SNAKE variants are classed by meaning",
      rf2.dnp_class("NWT_CONCUSSION_PROTOCOL") == "NWT"
      and rf2.dnp_class("DND_HEALTH_AND_SAFETY_PROTOCOLS") == "INJ"
      and rf2.dnp_class("NWT_TEAM_SUSPENSION") == "NWT"
      and rf2.dnp_class("DND_INELIGIBLE_TO_PLAY") == "UNKNOWN")
check("T1 the no-space reconditioning string is INJ",
      rf2.dnp_class("DND-Return to Competition Reconditioning") == "INJ")

check("T1 an unrecognised reason maps to UNKNOWN, not INJ",
      rf2.dnp_class("DND - Visa Issue") == "UNKNOWN",
      rf2.dnp_class("DND - Visa Issue"))
check("T1 a DNP-prefixed unrecognised reason maps to UNKNOWN, not CD",
      rf2.dnp_class("DNP - Something Nobody Has Seen") == "UNKNOWN")
check("T1 an NWT-prefixed unrecognised reason maps to UNKNOWN, not NWT",
      rf2.dnp_class("NWT - Something Nobody Has Seen") == "UNKNOWN",
      "the NWT prefix is honoured through the TABLE, never by prefix guessing")
check("T1 no reason is None and blank is None",
      rf2.dnp_class(None) is None and rf2.dnp_class("") is None
      and rf2.dnp_class("   ") is None and rf2.dnp_class(float("nan")) is None)
check("T1 every table value is a declared class",
      set(rf2.DNP_CLASS_TABLE.values()) <= set(rf2.DNP_CLASSES))
check("T1 UNKNOWN is a real class, not a sentinel string",
      "UNKNOWN" in rf2.DNP_CLASSES and "UNKNOWN" in set(rf2.DNP_CLASS_TABLE.values()))

# the reclassification, counted per (prefix-rule class -> semantic class)
_pairs: dict[str, int] = {}
for _r, _new in EXPECTED_DNP.items():
    _old = rf2.legacy_prefix_dnp_class(_r)
    if _old != _new:
        _pairs[f"{_old}->{_new}"] = _pairs.get(f"{_old}->{_new}", 0) + 1
check("T1 exactly seven distinct reason strings are reclassified",
      sum(_pairs.values()) == 7, f"{_pairs}")
check("T1 the reclassification is CD->INJ x2, INJ->CD x2, INJ->UNKNOWN x2, CD->UNKNOWN x1",
      _pairs == {"CD->INJ": 2, "INJ->CD": 2, "INJ->UNKNOWN": 2, "CD->UNKNOWN": 1},
      str(_pairs))
check("T1 no NWT-prefixed string changes class",
      not any(r.upper().startswith("NWT") for r in EXPECTED_DNP
              if rf2.legacy_prefix_dnp_class(r) != EXPECTED_DNP[r]))


# --------------------------------------------------------------------------
# a miniature, fully-known synthetic contract + masters
# --------------------------------------------------------------------------

TEAMS = (10, 20)
BASE_ROSTER = {10: (101, 102), 20: (201, 202)}

#: pid -> (game indices missed, reason). Applied in EVERY season.
ABSENCES = {
    101: ((3, 4), "DND - Injury/Illness"),   # semantic INJ, prefix INJ  (agrees)
    102: ((6,), "DND - Rest"),               # semantic CD,  prefix INJ  (differs)
    201: ((5,), "DND - Personal"),           # semantic UNKNOWN, prefix INJ
}

N_DATES = 14
SEASONS = (2098, 2099)
#: the returning player: team 10, season 2099 only, first obligation at index 9,
#: and his obligations carry a LATE (exact-tip-style) cutoff of D + 22h.
RETURNER, RETURNER_FIRST_GI = 103, 9
#: the equality probe: team 20, season 2099 only, obligations at indices 11 and
#: 12; the index-12 row's cutoff is set to EXACTLY availability(index 11).
EQUALITY, EQUALITY_GIS = 104, (11, 12)


def roster_for(season: int, tid: int, gi: int) -> tuple[int, ...]:
    r = list(BASE_ROSTER[tid])
    if season == 2099 and tid == 10 and gi >= RETURNER_FIRST_GI:
        r.append(RETURNER)
    if season == 2099 and tid == 20 and gi in EQUALITY_GIS:
        r.append(EQUALITY)
    return tuple(r)


def cutoff_for(season: int, pid: int, gi: int, dates) -> pd.Timestamp:
    d = dates[gi]
    if season == 2099 and pid == RETURNER:
        # late, exact-tip-style: the evening of game day
        return (d + pd.Timedelta(hours=22)).tz_localize("UTC")
    if season == 2099 and pid == EQUALITY and gi == 12:
        # EXACTLY availability(game 11): floor(D_11) + 36h
        return (dates[11] + pd.Timedelta(hours=36)).tz_localize("UTC")
    return (d - pd.Timedelta(hours=6)).tz_localize("UTC")


def synth(root: Path):
    """Two teams, one game per date, every quantity hand-checkable.

    The box score is constructed to satisfy the identity the adapter enforces,
    `pts == ftm + 3*fg3m + 2*(fgm - fg3m)`, rather than chosen for looks.
    """
    (root / "data" / "masters").mkdir(parents=True)
    # reconciled at fan-in: the required artifact set is the v3 contract, so
    # the synthetic tree must mirror the v3 layout the code now reads
    (root / "experiments" / "prediction_contract_v3").mkdir(parents=True)
    prow, trow, crow = [], [], []
    for season in SEASONS:
        dates = pd.date_range(f"{season}-05-01", periods=N_DATES, freq="D")
        for gi, d in enumerate(dates):
            gid = f"G{season}{gi:03d}"
            for ti, tid in enumerate(TEAMS):
                ftm, fgm, fg3m, paint = 10, 30 + gi, 5, 30
                trow.append({"game_id": gid, "team_id": tid, "season": season,
                             "game_date": d.strftime("%Y-%m-%d"),
                             "is_home": 1 if ti == 0 else 0,
                             "pts": ftm + 3 * fg3m + 2 * (fgm - fg3m),
                             "ftm": ftm, "fgm": fgm, "fg3m": fg3m,
                             "points_paint": paint})
                for pid in roster_for(season, tid, gi):
                    gis, reason = ABSENCES.get(pid, ((), None))
                    out = gi in gis
                    prow.append({
                        "game_id": gid, "player_id": pid, "team_id": tid,
                        "season": season, "game_date": d.strftime("%Y-%m-%d"),
                        "minutes": None if out else 20.0 + (gi % 5),
                        "starter_flag": 0 if out else 1,
                        "dnp_reason": reason if out else None,
                        "is_home": 1 if ti == 0 else 0,
                        "pts": None if out else 10, "fga": None if out else 8})
                    crow.append({
                        "game_id": gid, "player_id": pid, "team_id": tid,
                        "season": season, "game_date": d,
                        "forecast_cutoff": cutoff_for(season, pid, gi, dates),
                        "appeared": not out,
                        "minutes": None if out else 20.0 + (gi % 5),
                        "pts": None if out else 10, "fga": None if out else 8,
                        "fold_id": f"season:{season}"})
    mp = pd.DataFrame(prow)
    mt = pd.DataFrame(trow)

    pg = pd.DataFrame(crow)
    pg["row_uid"] = [f"pg_{i:05d}" for i in range(len(pg))]
    pg = pg[["row_uid", "game_id", "player_id", "team_id", "season", "game_date",
             "forecast_cutoff", "fold_id", "appeared", "minutes", "pts", "fga"]]

    tg = mt.copy()
    tg["row_uid"] = [f"tg_{i:05d}" for i in range(len(tg))]
    tg["game_date"] = pd.to_datetime(tg["game_date"])
    tg["forecast_cutoff"] = (tg["game_date"]
                             - pd.Timedelta(hours=6)).dt.tz_localize("UTC")
    tg["fold_id"] = "season:" + tg["season"].astype(str)
    tg = tg[["row_uid", "game_id", "team_id", "season", "game_date",
             "forecast_cutoff", "fold_id"]]

    mp.to_parquet(root / prov.MASTER_PLAYER, index=False)
    mt.to_parquet(root / prov.MASTER_TEAM, index=False)
    pg.to_parquet(root / prov.PLAYER_GAME, index=False)
    tg.to_parquet(root / prov.TEAM_GAME, index=False)
    (root / prov.CONTRACT_JSON).write_text('{"contract_version":"synthetic/2"}',
                                           encoding="utf-8")
    return pg, tg, mp, mt


def attest_all(root: Path):
    """Attest the artifacts BEFORE any frame is built; the adapter refuses
    unattested inputs and that refusal is itself tested."""
    for rel in (prov.MASTER_PLAYER, prov.MASTER_TEAM, prov.TEAM_GAME,
                prov.PLAYER_GAME):
        prov.attest_artifact(rel, root=root, producer="synthetic",
                             granularity="row", dry_run=False)
    aoi.write_manifest(root / prov.CONTRACT_JSON, producer="synthetic",
                       fit_through_date=aoi.bound_from_dates(["2099-05-20"]),
                       fit_through_season=2099, fit_seasons=list(SEASONS),
                       asof_granularity="artifact", notes="synthetic")


with tempfile.TemporaryDirectory() as td:
    R = Path(td)
    pg_syn, _tg_syn, _mp_syn, _mt_syn = synth(R)
    raises("T2 the adapter REFUSES to build from unattested inputs",
           rf2.RealFrameError, rf2.build_player_frame, 2099, R)
    attest_all(R)

    fold = rf2.build_player_frame(2099, R)
    tr, te = fold["train"], fold["test"]
    rec = fold["receipts"]
    t = te.set_index("row_uid")

    uid = {(int(r.player_id), r.game_id): r.row_uid
           for r in pg_syn.itertuples()}

    def U(pid: int, gi: int, season: int = 2099) -> str:
        return uid[(pid, f"G{season}{gi:03d}")]

    def ts(u: str, col: str) -> pd.Timestamp:
        return pd.Timestamp(t.loc[u, col])

    # ----------------------------------------------------------------------
    # T1b -- the taxonomy diff, counted on the SYNTHETIC master
    # ----------------------------------------------------------------------
    # 8 DNP rows total: 101 out twice per season (4 x 'DND - Injury/Illness'),
    # 102 out once per season (2 x 'DND - Rest'), 201 out once per season
    # (2 x 'DND - Personal'). The prefix rule calls all eight INJ.
    diff = rf2.dnp_taxonomy_diff(R)
    check("T1b the synthetic master has the 8 hand-counted DNP rows",
          diff["n_dnp_rows"] == 8, str(diff["n_dnp_rows"]))
    check("T1b the prefix rule classes all eight as INJ",
          diff["class_counts_prefix_rule"] == {"INJ": 8},
          str(diff["class_counts_prefix_rule"]))
    check("T1b the semantic taxonomy splits them 4 INJ / 2 CD / 2 UNKNOWN",
          diff["class_counts_semantic"] == {"INJ": 4, "CD": 2, "UNKNOWN": 2},
          str(diff["class_counts_semantic"]))
    check("T1b exactly four rows change class, and no parity is claimed",
          diff["n_rows_changed"] == 4
          and diff["changes_by_pair"] == {"INJ->CD": 2, "INJ->UNKNOWN": 2},
          str(diff["changes_by_pair"]))
    check("T1b no synthetic reason string falls outside the frozen table",
          diff["n_reasons_not_in_table"] == 0)

    # ----------------------------------------------------------------------
    # T2 -- THE CENTRAL REGRESSION
    # ----------------------------------------------------------------------
    # Player 103 joins team 10 at game index 9 (2099-05-10) and has NO prior
    # obligation of his own. His row's cutoff is 2099-05-10 22:00Z.
    #   admitted team games: availability(j) = 2099-05-(2+j) 12:00Z < 22:00Z on
    #     05-10  <=>  2+j <= 10  <=>  j <= 8, so k = 9
    #   team bound      = availability(8) = 2099-05-10 12:00Z
    #   schedule bound  = 2099-05-09 12:00Z
    #   gamelog bound   = nothing consumed -> falls back to 2099-05-09 12:00Z
    #   roster window   = he appeared in none of the 9, so the missed-streak scan
    #                     walks all 9; window = max(min(9,10), 9) = 9
    #   roster bound    = availability(8) = 2099-05-10 12:00Z
    #   composite       = 2099-05-10 12:00Z  == the TEAM bound, 24h newer than
    #                     the bound `/1` would have reported.
    u = U(RETURNER, RETURNER_FIRST_GI)
    TEAM_BOUND = T("2099-05-10 12:00")
    OWN_BOUND = T("2099-05-09 12:00")

    check("T2 the returner consumed no player history of his own",
          int(t.loc[u, "n_src_player_rows_consumed"]) == 0,
          str(t.loc[u, "n_src_player_rows_consumed"]))
    check("T2 the returner DID consume nine admitted team games",
          int(t.loc[u, "n_src_team_games_consumed"]) == 9
          and float(t.loc[u, "team_gp_season"]) == 9.0,
          f"{t.loc[u, 'n_src_team_games_consumed']} / {t.loc[u, 'team_gp_season']}")
    check("T2 the TEAM bound is newer than the player's own bound",
          ts(u, "src_asof_team_gamelog") > ts(u, "src_asof_gamelog"),
          f"{t.loc[u, 'src_asof_team_gamelog']} vs {t.loc[u, 'src_asof_gamelog']}")
    check("T2 THE REGRESSION: the composite equals the TEAM bound",
          ts(u, rf2.FEATURE_ASOF_COL) == TEAM_BOUND,
          f"{t.loc[u, rf2.FEATURE_ASOF_COL]} != {TEAM_BOUND.isoformat()}")
    check("T2 the composite does NOT equal the player's own bound",
          ts(u, rf2.FEATURE_ASOF_COL) != OWN_BOUND,
          "`/1` reported the player bound and understated the row by 24h")
    check("T2 the understatement `/1` would have made is exactly 24h",
          (TEAM_BOUND - OWN_BOUND) == pd.Timedelta(hours=24))
    check("T2 the composite is still strictly before the row's own cutoff",
          ts(u, rf2.FEATURE_ASOF_COL)
          < pd.Timestamp(t.loc[u, "forecast_cutoff"]),
          f"cutoff={t.loc[u, 'forecast_cutoff']}")

    # ----------------------------------------------------------------------
    # T3 -- every source bound against a hand-computed value
    # ----------------------------------------------------------------------
    check("T3 the returner's gamelog bound is the schedule fallback 2099-05-09 12:00Z",
          ts(u, "src_asof_gamelog") == OWN_BOUND, str(t.loc[u, "src_asof_gamelog"]))
    check("T3 the returner's team-gamelog bound is 2099-05-10 12:00Z",
          ts(u, "src_asof_team_gamelog") == TEAM_BOUND,
          str(t.loc[u, "src_asof_team_gamelog"]))
    check("T3 the returner's roster bound is 2099-05-10 12:00Z, not the gamelog copy",
          ts(u, "src_asof_roster") == TEAM_BOUND
          and ts(u, "src_asof_roster") != ts(u, "src_asof_gamelog"),
          str(t.loc[u, "src_asof_roster"]))
    check("T3 the returner's roster window is the nine games candidacy actually read",
          int(t.loc[u, "n_roster_games_consumed"]) == 9,
          str(t.loc[u, "n_roster_games_consumed"]))
    check("T3 the returner's schedule bound is 2099-05-09 12:00Z",
          ts(u, "src_asof_schedule") == T("2099-05-09 12:00"),
          str(t.loc[u, "src_asof_schedule"]))

    # A regular row: player 101 at game index 13, default cutoff 2099-05-13 18:00Z.
    #   admitted team games j <= 11  ->  k = 12, latest availability(11) =
    #     2099-05-13 12:00Z
    #   his own admitted obligations are the same 12 games, so the player bound
    #     is ALSO 2099-05-13 12:00Z
    #   candidacy window: he played game 11, so the missed-streak scan stops at
    #     1; window = max(min(12,10), 1) = 10  ->  strictly fewer records than
    #     team_gp_season reads, which is the point of tracking it separately
    #   schedule bound = 2099-05-13 12:00Z
    u13 = U(101, 13)
    check("T3 a regular row's team-gamelog bound is 2099-05-13 12:00Z",
          ts(u13, "src_asof_team_gamelog") == T("2099-05-13 12:00"),
          str(t.loc[u13, "src_asof_team_gamelog"]))
    check("T3 a regular row's player-gamelog bound is 2099-05-13 12:00Z",
          ts(u13, "src_asof_gamelog") == T("2099-05-13 12:00"),
          str(t.loc[u13, "src_asof_gamelog"]))
    check("T3 a regular row consumed twelve admitted team games",
          int(t.loc[u13, "n_src_team_games_consumed"]) == 12,
          str(t.loc[u13, "n_src_team_games_consumed"]))
    check("T3 candidacy read only the ten-game window, not all twelve",
          int(t.loc[u13, "n_roster_games_consumed"]) == 10,
          str(t.loc[u13, "n_roster_games_consumed"]))
    check("T3 the composite of a regular row is 2099-05-13 12:00Z",
          ts(u13, rf2.FEATURE_ASOF_COL) == T("2099-05-13 12:00"))

    # the composite is a maximum, on every row, of every reported source
    _srcs = ["src_asof_gamelog", "src_asof_team_gamelog", "src_asof_roster",
             "src_asof_schedule"]
    _comp = pd.to_datetime(te[rf2.FEATURE_ASOF_COL], utc=True)
    _mx = te[_srcs].apply(pd.to_datetime, utc=True).max(axis=1)
    check("T3 feature_asof is the maximum of all four sources on every row",
          bool((_comp == _mx).all()),
          f"{int((_comp != _mx).sum())} rows disagree")
    _cut = pd.to_datetime(te["forecast_cutoff"], utc=True)
    check("T3 no source is at or after its own cutoff, on any row",
          bool(all((pd.to_datetime(te[c], utc=True) < _cut).all() for c in _srcs)))
    check("T3 no row has a TEAM source newer than the composite",
          int((pd.to_datetime(te["src_asof_team_gamelog"], utc=True)
               > _comp).sum()) == 0)
    check("T3 the receipt reports zero at-cutoff and zero after-cutoff rows",
          rec["timestamps"]["n_at_cutoff"] == 0
          and rec["timestamps"]["n_after_cutoff"] == 0,
          str(rec["timestamps"]))
    check("T3 the receipt reports zero sources above the composite",
          all(v["n_newer_than_composite"] == 0
              for v in rec["timestamps"]["per_source"].values()),
          str(rec["timestamps"]["per_source"]))
    check("T3 the receipt names the team gamelog among the player sources",
          "src_asof_team_gamelog" in rec["timestamps"]["sources"]
          and not rec["schema_check"]["sources_missing"])
    check("T3 the roster window never exceeds the admitted team index",
          bool((te["n_roster_games_consumed"]
                <= te["n_src_team_games_consumed"]).all()))
    check("T3 the build is deterministic",
          rec["identity"] == rf2.build_player_frame(2099, R)["receipts"]["identity"])

    # ----------------------------------------------------------------------
    # T4 -- `no_prior_game_admitted` only where nothing was consumed
    # ----------------------------------------------------------------------
    NP = rf2.NO_EVIDENCE_POLICY
    for pol, cnt in (("src_policy_gamelog", "n_src_player_rows_consumed"),
                     ("src_policy_team_gamelog", "n_src_team_games_consumed"),
                     ("src_policy_roster", "n_roster_games_consumed")):
        empty = te[cnt] == 0
        labelled = te[pol] == NP
        check(f"T4 {pol} labels no-evidence exactly when {cnt} == 0",
              bool((empty == labelled).all()),
              f"{int((empty != labelled).sum())} rows disagree")
    check("T4 the returner's gamelog IS labelled no-evidence",
          t.loc[u, "src_policy_gamelog"] == NP)
    check("T4 but his team and roster sources are NOT",
          t.loc[u, "src_policy_team_gamelog"] == "prior_team_game_availability"
          and t.loc[u, "src_policy_roster"] == "admitted_team_game_candidacy",
          f"{t.loc[u, 'src_policy_team_gamelog']} / {t.loc[u, 'src_policy_roster']}")
    check("T4 the receipt carries a policy count for each of the four sources",
          {"src_policy_gamelog", "src_policy_team_gamelog", "src_policy_roster",
           "src_policy_schedule"} <= set(rec["provenance"]["row_level_policies"]),
          str(list(rec["provenance"]["row_level_policies"])))
    check("T4 every emitted policy label is defined in SOURCE_POLICIES",
          all(k in rf2.SOURCE_POLICIES
              for d in rec["provenance"]["row_level_policies"].values()
              for k in d))

    # ----------------------------------------------------------------------
    # T5 -- availability == cutoff is EXCLUDED
    # ----------------------------------------------------------------------
    # Player 104's index-12 row carries a cutoff of EXACTLY availability(11) =
    # 2099-05-13 12:00Z.
    #   team games: availability(j) < cutoff  <=>  2+j <= 12  <=>  j <= 10, so
    #     k = 11 -- game 11 is excluded on the strict inequality alone. A `<=`
    #     gate would report 12.
    #   his own only prior obligation is game 11, whose availability is likewise
    #     EXACTLY the cutoff, so it is excluded and the player source consumed
    #     nothing at all.
    ue = U(EQUALITY, 12)
    check("T5 a prior TEAM game whose availability equals the cutoff is excluded",
          int(t.loc[ue, "n_src_team_games_consumed"]) == 11
          and float(t.loc[ue, "team_gp_season"]) == 11.0,
          f"{t.loc[ue, 'n_src_team_games_consumed']} (a <= gate would give 12)")
    check("T5 a prior PLAYER row whose availability equals the cutoff is excluded",
          int(t.loc[ue, "n_src_player_rows_consumed"]) == 0,
          str(t.loc[ue, "n_src_player_rows_consumed"]))
    check("T5 and that exclusion is reported as no-evidence for the player source",
          t.loc[ue, "src_policy_gamelog"] == NP)
    check("T5 the team bound is availability(10) = 2099-05-12 12:00Z",
          ts(ue, "src_asof_team_gamelog") == T("2099-05-12 12:00"),
          str(t.loc[ue, "src_asof_team_gamelog"]))
    check("T5 the composite stays strictly before the cutoff it equals nothing of",
          ts(ue, rf2.FEATURE_ASOF_COL) < T("2099-05-13 12:00"))

    # the same rule, seen through the DNP carry-forward: 101 sits out indices
    # 3 and 4; index 4 is admitted only from index 6 onward
    _p101 = te[te.player_id == 101].sort_values("game_date")
    _gi = {r.row_uid: i for i, r in enumerate(_p101.itertuples())}
    _early = [k for k, i in _gi.items() if i <= 4]
    _late = [k for k, i in _gi.items() if i >= 6]
    check("T5 a DNP is not visible before its outcome was available",
          bool((t.loc[_early, "prev_dnp_inj"] == 0).all()))
    check("T5 the DNP IS visible once it was available, and it is INJ",
          bool((t.loc[_late, "prev_dnp_inj"] == 1).all())
          and bool((t.loc[_late, "prev_dnp_cd"] == 0).all()),
          str(t.loc[_late, "prev_dnp_inj"].tolist()))
    check("T5 the season resets: 2099's opener carries none of 2098",
          float(_p101.iloc[0].team_gp_season) == 0.0
          and float(_p101.iloc[0].games_missed_streak) == 0.0)
    check("T5 the train fold is season 2098 and the test fold season 2099",
          set(tr.season) == {2098} and set(te.season) == {2099})

    # the semantic taxonomy, seen in the features
    _u102 = U(102, 10)     # 'DND - Rest' at index 6, admitted from index 8
    check("T5 'DND - Rest' carries forward as CD, not INJ",
          float(t.loc[_u102, "prev_dnp_cd"]) == 1.0
          and float(t.loc[_u102, "prev_dnp_inj"]) == 0.0,
          f"cd={t.loc[_u102, 'prev_dnp_cd']} inj={t.loc[_u102, 'prev_dnp_inj']}")
    _u201 = U(201, 7)      # 'DND - Personal' at index 5, admitted from index 7
    check("T5 'DND - Personal' carries forward as UNKNOWN and sets no indicator",
          float(t.loc[_u201, "prev_dnp_unknown"]) == 1.0
          and float(t.loc[_u201, "prev_dnp_cd"]) == 0.0
          and float(t.loc[_u201, "prev_dnp_inj"]) == 0.0
          and float(t.loc[_u201, "prev_dnp_nwt"]) == 0.0,
          f"unknown={t.loc[_u201, 'prev_dnp_unknown']} "
          f"inj={t.loc[_u201, 'prev_dnp_inj']}")
    check("T5 an UNKNOWN prior DNP does not set returning_flag",
          float(t.loc[_u201, "returning_flag"]) == 0.0
          and float(t.loc[_u201, "played_last_team_game"]) == 0.0,
          "the prefix rule called it INJ and would have flagged a return")
    check("T5 UNKNOWN is distinguishable from 'no prior DNP at all'",
          float(t.loc[U(202, 7), "prev_dnp_unknown"]) == 0.0
          and float(t.loc[_u201, "prev_dnp_unknown"]) == 1.0)

    # ----------------------------------------------------------------------
    # T6 -- the channel identity
    # ----------------------------------------------------------------------
    tf = rf2.build_team_frame(2099, R)
    tt = tf["test"]
    check("T6 the four channels reconstruct team_points exactly",
          float(((tt.ch_ft + tt.ch_3pt + tt.ch_paint + tt.ch_np2)
                 - tt.team_points).abs().max()) < 1e-9)
    check("T6 pts == ftm + 3*fg3m + 2*(fgm - fg3m) on the source master",
          bool((_mt_syn["pts"] == _mt_syn["ftm"] + 3 * _mt_syn["fg3m"]
                + 2 * (_mt_syn["fgm"] - _mt_syn["fg3m"])).all()))
    check("T6 side is derived from is_home as home/away",
          set(tt.side) == {"home", "away"}
          and bool((tt.groupby("game_id").side.nunique() == 2).all()))
    check("T6 the team frame carries the composite too",
          rf2.FEATURE_ASOF_COL in tt.columns
          and bool((pd.to_datetime(tt[rf2.FEATURE_ASOF_COL], utc=True)
                    < pd.to_datetime(tt["forecast_cutoff"], utc=True)).all()))
    check("T6 the team receipt reports a clean join",
          tf["receipts"]["join"]["unmatched"] == 0)

# a corrupted box score must be REFUSED, not silently carried
with tempfile.TemporaryDirectory() as td2:
    R2 = Path(td2)
    synth(R2)
    _bad = pd.read_parquet(R2 / prov.MASTER_TEAM)
    _bad.loc[0, "pts"] = int(_bad.loc[0, "pts"]) + 7      # breaks the identity
    _bad.to_parquet(R2 / prov.MASTER_TEAM, index=False)
    attest_all(R2)
    raises("T6 a box score that breaks the channel identity is refused",
           rf2.RealFrameError, rf2.build_team_frame, 2099, R2)


print(f"{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAILED  {f}")
sys.exit(1 if FAILED else 0)
