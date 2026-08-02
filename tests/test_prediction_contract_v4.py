"""prediction_contract_v4 -- one unique team-bearing key, honestly named, provably bound.

v3's universe was availability-causal and its ROW SET was right.  Four things were not:

    C1  `row_uid` was `pg_uid(player_id, game_id)` -- team-blind, and 28 rows shared 14 values,
        so `cbs_real_frames_v2.build_player_frame(2024, require_attested=True)` raised
        MergeError while the v10 gate reported green;
    C3  the registered prose said candidates "APPEARED in a prior game" while the producer
        pooled every prior ADMITTED box row, DNP rows included;
    C4  `src_asof_roster` / `n_roster_games_consumed` were recomputed downstream from a
        feature-history window that merely shared the same maximum timestamp;
    C5  cutoff identity against the frozen v2 contract was proven on two fields out of eight.

Sections 0-4 and 7 are SYNTHETIC: every frame is built in this file, so a stale or absent
parquet cannot make them pass or fail.  Sections 5 and 6 deliberately read the REAL emitted
artifacts, because "the key is unique" is a claim about bytes on disk and cannot be
demonstrated on a fixture.  Nothing anywhere fits, predicts or scores.

Runnable two ways:
    python -m pytest tests/ -q
    python tests/test_prediction_contract_v4.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import asof_invariant as ai                                          # noqa: E402
import cbs_obligation_key as obk                                     # noqa: E402
import prediction_contract_v2 as v2                                  # noqa: E402
import prediction_contract_v3 as v3                                  # noqa: E402
import prediction_contract_v4 as v4                                  # noqa: E402
from prediction_contract_v4 import (                                 # noqa: E402
    CONTRACT_VERSION, CUTOFF_IDENTITY_FIELDS, EXPECTED_APPEARED_ONLY, EXPECTED_ROW_SET,
    MEMBERSHIP_APPEARED_ONLY, MEMBERSHIP_BOX_INCLUDING_DNP, ROSTER_BINDING_ID,
    ROSTER_LOOKBACK, SUPERSEDES, appeared_only_counterfactual, attach_roster_provenance,
    build_candidates, compare_cutoff_fields, require_cutoff_identity,
)

OUT = REPO / "experiments" / "prediction_contract_v4"
V3_OUT = REPO / "experiments" / "prediction_contract_v3"

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
    """spec: (game_id, 'YYYY-MM-DD', team_id, season, [player_ids or (pid, minutes)])."""
    rows = []
    for gid, date, team, season, pids in spec:
        for entry in pids:
            pid, mins = entry if isinstance(entry, tuple) else (entry, 20.0)
            rows.append({"game_id": gid, "team_id": team, "player_id": pid,
                         "game_date": pd.Timestamp(date), "season": season,
                         "minutes": mins, "pts": 10.0 if mins else None,
                         "fga": 8.0 if mins else None})
    return pd.DataFrame(rows)


def date_only(date: str) -> pd.Timestamp:
    """v2's date-only policy: 18:00 UTC on the day BEFORE the game."""
    return pd.Timestamp(date, tz="UTC") - pd.Timedelta(days=1) + pd.Timedelta(hours=18)


def cand_for(cand: pd.DataFrame, team, gid) -> set:
    return set(cand[(cand.team_id == team) & (cand.game_id == gid)].player_id)


def window_for(win: pd.DataFrame, team, gid) -> pd.Series:
    return win[(win.team_id == team) & (win.game_id == gid)].iloc[0]


# The back-to-back fixture, carried from the v3 suite so the gate itself is re-proved here.
B2B = [
    ("g1", "2024-06-01", 10, 2024, [1, 2, 3, 91]),
    ("g2", "2024-06-03", 10, 2024, [1, 2, 3]),
    ("g3", "2024-06-05", 10, 2024, [1, 2, 3]),
    ("g4", "2024-06-07", 10, 2024, [1, 2, 3]),
    ("g5", "2024-06-09", 10, 2024, [1, 2, 3]),
    ("g6", "2024-06-10", 10, 2024, [1, 2, 3, 96]),
    ("g7", "2024-06-11", 10, 2024, [1, 2, 3, 77]),
]
B2B_CUT = {g: date_only(d) for g, d, *_ in B2B}

# The traded-player fixture: 55 moves from club 30 to club 40, and the two clubs then meet.
TRADED = [
    ("t1", "2024-06-01", 30, 2024, [1, 2, 55]),
    ("t2", "2024-06-04", 30, 2024, [1, 2, 55]),
    ("u1", "2024-06-01", 40, 2024, [7, 8]),
    ("u2", "2024-06-04", 40, 2024, [7, 8, 55]),
    ("x9", "2024-06-08", 30, 2024, [1, 2]),
    ("x9", "2024-06-08", 40, 2024, [7, 8, 55]),
]
TRADED_CUT = {g: date_only(d) for g, d, *_ in TRADED}

# A DNP fixture: 88 is LISTED in the window with null minutes and never plays.
DNP = [
    ("d1", "2024-06-01", 20, 2024, [1, 2, (88, None)]),
    ("d2", "2024-06-04", 20, 2024, [1, 2, (88, None)]),
    ("d3", "2024-06-07", 20, 2024, [1, 2]),
]
DNP_CUT = {g: date_only(d) for g, d, *_ in DNP}


def v4_key_probe() -> list[tuple]:
    """(player_id, game_id, team_id) for the two real dual-team collisions."""
    return [(1641653, "1022300169", 1611661317), (1641653, "1022300169", 1611661322),
            (203824, "1022400175", 1611661319), (203824, "1022400175", 1611661324)]


def ref_games() -> pd.DataFrame:
    """A minimal `game` frame carrying all eight compared cutoff fields."""
    return pd.DataFrame({
        "game_id": ["exact_tip", "date_only"],
        "forecast_cutoff": pd.to_datetime(["2024-06-11T22:30Z", "2024-06-10T18:00Z"],
                                          utc=True),
        "cutoff_policy": [v2.POLICY_EXACT, v2.POLICY_DATE_ONLY],
        "exact_cutoff_ok": [True, False],
        "scheduled_tip_time": pd.to_datetime(["2024-06-12T00:00Z", None], utc=True),
        "tip_time_source": ["props_historical", None],
        "tip_time_observed_at": pd.to_datetime(["2024-06-05T00:00Z", None], utc=True),
        "tip_time_quality": ["observed_pre_cutoff", "none"],
        "tip_revisions_seen": [1, 0],
    })


PERTURB = {
    "forecast_cutoff": pd.Timestamp("2024-06-11T22:31Z"),
    "cutoff_policy": "some_other_policy",
    "exact_cutoff_ok": False,
    "scheduled_tip_time": pd.Timestamp("2024-06-12T00:05Z"),
    "tip_time_source": "odds_extension",
    "tip_time_observed_at": pd.Timestamp("2024-06-05T00:01Z"),
    "tip_time_quality": "observed_post_cutoff",
    "tip_revisions_seen": 3,
}


def main() -> int:
    print("0. registration, and the gate is v3's OWN gate, not a look-alike")
    check("the contract supersedes v3",
          (CONTRACT_VERSION, SUPERSEDES) == ("player_game_contract/4",
                                             "player_game_contract/3"))
    check("the availability gate is IMPORTED from the frozen v3 module, not copied",
          v4.availability_bound is v3.availability_bound
          and v4.verify_availability_policy is v3.verify_availability_policy,
          "one gate, or two that will eventually disagree")
    pol = v4.verify_availability_policy()
    check("the +36h policy still reproduces cbs_v7 and asof_invariant exactly", pol["ok"],
          str(pol))
    check("the cutoff machinery is imported from the frozen v2 module",
          v4.apply_cutoff_policy is v2.apply_cutoff_policy
          and v4.resolve_tip_times is v2.resolve_tip_times)
    check("the key module is the registered one",
          v4.row_uid is not None
          and v4.row_uid(1, "g", 2) == obk.row_uid(1, "g", 2)
          and obk.OBLIGATION_KEY_ID == "cbs_obligation_key/1")

    print("\n1. C1 -- a traded player yields TWO obligations with TWO distinct canonical keys")
    ct, wt = build_candidates(master(TRADED), TRADED_CUT)
    x9 = ct[ct.game_id == "x9"]
    p55 = x9[x9.player_id == 55]
    check("55 is a candidate for BOTH clubs in their head-to-head game",
          {30, 40} <= set(p55.team_id), str(sorted(p55.team_id)))
    check("  ... which is TWO obligations, not one", len(p55) == 2)
    check("  ... carrying two DISTINCT canonical row_uids", p55.row_uid.nunique() == 2,
          str(sorted(p55.row_uid)))
    check("  ... and ONE shared legacy player_game_uid",
          p55.player_game_uid.nunique() == 1
          and set(p55.player_game_uid) == {v2.pg_uid(55, "x9")})
    check("  ... flagged as shared on BOTH rows",
          bool(p55.player_game_uid_shared_with_other_team.all()))
    check("row_uid is unique over the whole fixture", ct.row_uid.is_unique)
    check("  ... and equals cbs_obligation_key.row_uid on every row",
          all(r == obk.row_uid(p, g, t) for r, p, g, t
              in zip(ct.row_uid, ct.player_id, ct.game_id, ct.team_id)))
    check("obligation_uid is an alias of row_uid, byte for byte",
          bool((ct.obligation_uid == ct.row_uid).all()))
    check("v3's digest is carried for mapping and is a DIFFERENT string",
          all(u == v3.ob_uid(t, p, g) and u != r for u, r, t, p, g
              in zip(ct.v3_obligation_uid, ct.row_uid, ct.team_id, ct.player_id, ct.game_id)))
    check("the frame declares the key rule it followed",
          set(ct.obligation_key_id) == {obk.OBLIGATION_KEY_ID})
    check("v2's drop_duplicates('row_uid') would have deleted one of the pair -- v4's "
          "does not, because the v4 key is not the colliding one",
          len(x9.drop_duplicates("player_game_uid")) == len(x9) - 1
          and len(x9.drop_duplicates("row_uid")) == len(x9))
    check("build_candidates asserts uniqueness before returning",
          "assert_unique_canonical_keys" in
          (REPO / "prediction_contract_v4.py").read_text(encoding="utf-8"))

    print("\n2. C3 -- membership is BOX MEMBERSHIP INCLUDING DNP ROWS, and says so")
    cd, wd = build_candidates(master(DNP), DNP_CUT)
    got = cand_for(cd, 20, "d3")
    check("a player LISTED with null minutes in the window IS a candidate", 88 in got,
          str(sorted(got)))
    check("  ... and the rule id on the row says box membership, not appearance",
          set(cd.membership_rule_id) == {MEMBERSHIP_BOX_INCLUDING_DNP})
    ca, _ = build_candidates(master(DNP), DNP_CUT, membership=MEMBERSHIP_APPEARED_ONLY)
    check("under the APPEARED-ONLY counterfactual the same player is NOT a candidate",
          88 not in cand_for(ca, 20, "d3"))
    check("  ... and the counterfactual is a strict subset of the registered universe",
          set(map(tuple, ca[["team_id", "game_id", "player_id"]].to_numpy().tolist()))
          < set(map(tuple, cd[["team_id", "game_id", "player_id"]].to_numpy().tolist())))
    cf = appeared_only_counterfactual(master(DNP), DNP_CUT)
    # 88 is listed (and never plays) in d1 and d2, so he is a box-membership candidate for
    # BOTH d2 and d3: the appeared-only rule deletes two obligations here, not one.
    check("the counterfactual receipt counts the gap on the fixture",
          cf["registered_rows"] - cf["appeared_only_rows"]
          == cf["obligations_that_exist_only_because_dnp_rows_count"] == 2,
          str(cf["obligations_that_exist_only_because_dnp_rows_count"]))
    check("  ... and the deleted obligations are exactly 88's, for d2 and d3",
          {(t, g, p) for t, g, p in cd[["team_id", "game_id", "player_id"]].to_numpy()
           .tolist()} - {(t, g, p) for t, g, p in
                         ca[["team_id", "game_id", "player_id"]].to_numpy().tolist()}
          == {(20, "d2", 88), (20, "d3", 88)})
    check("the registered rule NAMES the DNP inclusion",
          "DNP" in v4.MEMBERSHIP_RULE and "BOX MEMBERSHIP, NOT APPEARANCE" in
          v4.MEMBERSHIP_RULE)
    check("no v3 'appeared in a prior game' prose survives in the module's registered rule",
          "APPEARS AS A ROW IN THE TEAM'S BOX SCORE" in v4.MEMBERSHIP_RULE
          and "who appeared in one of the LATEST FIVE" not in v4.ADMISSION_RULE)
    check("the counterfactual changes MEMBERSHIP only, never the team-game index",
          len(wd) == len(build_candidates(master(DNP), DNP_CUT,
                                          membership=MEMBERSHIP_APPEARED_ONLY)[1]),
          "a counterfactual that also shrank the index would confound the two effects")

    print("\n3. C4 -- roster provenance is BOUND to the candidacy record")
    cr = attach_roster_provenance(cd)
    check("src_asof_roster IS admitted_window_bound, not a recomputation",
          bool((pd.to_datetime(cr.src_asof_roster, utc=True)
                == pd.to_datetime(cr.admitted_window_bound, utc=True)).all()))
    check("n_roster_games_consumed IS lookback_games_used",
          bool((cr.n_roster_games_consumed == cr.lookback_games_used).all()))
    check("every emitted row consumed at least one admitted game",
          bool((cr.n_roster_games_consumed >= 1).all()))
    check("the window's IDENTITY travels with the row, which a timestamp cannot carry",
          cr.roster_evidence_digest.notna().all()
          and cr.roster_evidence_first_game.notna().all()
          and cr.roster_evidence_last_game.notna().all())
    check("the digest is a function of the exact ORDERED window",
          v4.window_digest(["a", "b"]) != v4.window_digest(["b", "a"]))
    check("  ... so two different record sets cannot share it",
          v4.window_digest(["a", "b"]) != v4.window_digest(["a", "b", "c"]))
    check("the binding declares itself on every row",
          set(cr.roster_binding_id) == {ROSTER_BINDING_ID})
    rb = v4.roster_binding_receipt(cr, master(DNP), DNP_CUT)
    check("the receipt MEASURES the coincidence rather than resting on it",
          rb["coincidence_measurement"]["rows_where_the_two_maxima_are_the_same_instant"]
          == len(cr),
          "the maxima agree by construction; that is the point being disclosed")

    print("\n4. C5 -- cutoff identity is proven on EIGHT fields and fails closed on each")
    ref = ref_games()
    base = compare_cutoff_fields(ref.copy(), ref)
    check("eight fields are compared, not two",
          base["n_fields_compared"] == 8 and len(CUTOFF_IDENTITY_FIELDS) == 8,
          str(base["fields_compared"]))
    check("v3's two fields are a strict subset of v4's eight",
          set(base["fields_compared_by_v3"]) < set(base["fields_compared"]))
    check("an identical frame passes", base["ok"] and not base["problems"])
    check("NaT == NaT AGREES, so a date-only game is not a false positive",
          base["per_field"]["scheduled_tip_time"]["mismatches"] == 0
          and ref.scheduled_tip_time.isna().any(),
          "a naive != would have flagged every date-only game and got the field dropped")
    for col, _kind in CUTOFF_IDENTITY_FIELDS:
        bad = ref.copy()
        bad.loc[0, col] = PERTURB[col]
        rep = compare_cutoff_fields(bad, ref)
        flagged = rep["per_field"][col]["mismatches"] == 1
        others = all(rep["per_field"][c]["mismatches"] == 0
                     for c, _ in CUTOFF_IDENTITY_FIELDS if c != col)
        try:
            require_cutoff_identity(bad, ref)
            raised = False
        except SystemExit:
            raised = True
        check(f"  a changed {col} is caught, attributed to that field alone, and FAILS CLOSED",
              flagged and others and raised,
              f"flagged={flagged} others_clean={others} raised={raised}")
    missing_null = ref.copy()
    missing_null.loc[1, "scheduled_tip_time"] = pd.Timestamp("2024-06-11T00:00Z")
    rep = compare_cutoff_fields(missing_null, ref)
    check("a null replaced by a value is a mismatch, not a silent pass",
          rep["per_field"]["scheduled_tip_time"]["mismatches"] == 1 and not rep["ok"])
    short = compare_cutoff_fields(ref.iloc[:1].copy(), ref)
    check("a game present on one side only is a mismatch",
          short["games_only_on_one_side"] == 1 and not short["ok"])
    try:
        require_cutoff_identity(ref.iloc[:1].copy(), ref)
        raised = False
    except SystemExit as exc:
        raised = True
        msg = str(exc)
    check("  ... and the refusal names the gitignored odds source as the likely cause",
          raised and "odds_capture" in msg and "WNBA_ODDS_EXT" in msg)

    print("\n5. the REAL emitted artifacts")
    need = ["contract.json", "player_game.parquet", "team_game.parquet", "game.parquet",
            "row_diff_vs_v3.json"]
    present = [n for n in need if (OUT / n).exists()]
    check("all five artifacts were emitted", len(present) == 5,
          f"missing {sorted(set(need) - set(present))}")
    if len(present) == 5:
        pg = pd.read_parquet(OUT / "player_game.parquet")
        doc = json.loads((OUT / "contract.json").read_text(encoding="utf-8"))
        diff = json.loads((OUT / "row_diff_vs_v3.json").read_text(encoding="utf-8"))

        check("row_uid is UNIQUE over the real emitted frame",
              pg.row_uid.is_unique and len(pg) == pg.row_uid.nunique(),
              f"{len(pg)} rows, {pg.row_uid.nunique()} distinct")
        check(f"  ... over all {len(pg)} obligations",
              len(pg) == EXPECTED_ROW_SET["v4_rows"] == 35627, str(len(pg)))
        check("every real row_uid recomputes from (player_id, game_id, team_id)",
              bool((pg.row_uid == [obk.row_uid(p, g, t) for p, g, t
                                   in zip(pg.player_id, pg.game_id, pg.team_id)]).all()))
        check("player_game_uid is BYTE-EQUAL to prediction_contract_v2.pg_uid on every row",
              bool((pg.player_game_uid == [v2.pg_uid(p, g) for p, g
                                           in zip(pg.player_id, pg.game_id)]).all()))
        n_shared = int(pg.player_game_uid.duplicated(keep=False).sum())
        check("the legacy key still collides on the real traded players -- 28 rows, 14 ids",
              n_shared == 28 and pg.player_game_uid.nunique() == len(pg) - 14,
              f"{n_shared} rows share, {pg.player_game_uid.nunique()} distinct")
        check("  ... and those are exactly the rows flagged shared",
              int(pg.player_game_uid_shared_with_other_team.sum()) == n_shared)
        dual = pg[pg.player_game_uid_shared_with_other_team]
        check("  ... each colliding pair is one player, one game, two teams",
              bool(dual.groupby("player_game_uid").team_id.nunique().eq(2).all())
              and bool(dual.groupby("player_game_uid").size().eq(2).all()))

        check("the ROW SET is unchanged vs v3 -- only the key changed",
              diff["obligation_level"]["row_set_unchanged"]
              and diff["obligation_level"]["v3_only_count"] == 0
              and diff["obligation_level"]["v4_only_count"] == 0
              and diff["obligation_level"]["v3_rows"]
              == diff["obligation_level"]["v4_rows"] == 35627,
              json.dumps(diff["obligation_level"])[:200])
        check("  ... and the diff SAYS a row-set change would be a defect, not a finding",
              "DEFECT" in diff["claim"] and diff["obligation_level"]["defect"] is None)
        check("  ... and the legacy key set equals v3's row_uid set exactly",
              diff["key_level"]["player_game_uid_set_equals_v3_row_uid_set"]
              and diff["key_level"]["v4_reproduces_every_v3_obligation_uid"])

        cf = doc["appeared_only_counterfactual"]
        check("the appeared-only counterfactual is 32,438 rows",
              cf["appeared_only_rows"] == EXPECTED_APPEARED_ONLY["rows"] == 32438,
              str(cf["appeared_only_rows"]))
        check("  ... i.e. 3,189 fewer than the registered universe",
              cf["obligations_that_exist_only_because_dnp_rows_count"]
              == EXPECTED_APPEARED_ONLY["fewer_than_registered"] == 3189,
              str(cf["obligations_that_exist_only_because_dnp_rows_count"]))
        check("  ... which AGREES with the supervisor's independent number", cf["all_match"])
        check("the contract registers the box-membership rule id, not an appearance rule",
              doc["membership_rule_id"] == MEMBERSHIP_BOX_INCLUDING_DNP)
        check("  ... and concedes the v3 prose was wrong rather than quietly restating it",
              "Neither statement described the v3 implementation"
              in doc["membership_correction_vs_v3"])

        ci = doc["accounting"]["cutoff_identity_vs_v2"]
        check("the real run proved cutoff identity on all eight fields over 1,495 games",
              ci["ok"] and ci["n_fields_compared"] == 8 and ci["games_compared"] == 1495,
              json.dumps({k: ci[k] for k in ("ok", "n_fields_compared", "games_compared")}))
        check("  ... including the 407 exact tips, so the gitignored odds source resolved",
              doc["accounting"]["games_exact_tip"] == 407
              and doc["accounting"]["games_date_only"] == 1088,
              f"{doc['accounting']['games_exact_tip']} exact")

        check("src_asof_roster equals admitted_window_bound on every real row",
              bool((pd.to_datetime(pg.src_asof_roster, utc=True)
                    == pd.to_datetime(pg.admitted_window_bound, utc=True)).all()))
        check("n_roster_games_consumed equals lookback_games_used on every real row",
              bool((pg.n_roster_games_consumed == pg.lookback_games_used).all()))
        rbm = doc["roster_provenance_binding"]["coincidence_measurement"]
        check("the receipt discloses that the two maxima coincide on 100% of rows",
              rbm["rows_where_the_two_maxima_are_the_same_instant"] == rbm["rows"] == 35627)
        check("  ... while the RECORD SETS differ on most of them, which is why the "
              "coincidence is not a binding",
              rbm["rows_where_the_RECORD_SETS_differ_in_size"] > 0,
              str(rbm["rows_where_the_RECORD_SETS_differ_in_size"]))

        check("every real row's candidacy evidence strictly predates its own cutoff",
              bool((pd.to_datetime(pg.admitted_window_bound, utc=True)
                    < pd.to_datetime(pg.forecast_cutoff, utc=True)).all()))
        check("no real row carries a null canonical key or a null legacy key",
              not pg.row_uid.isna().any() and not pg.player_game_uid.isna().any())

        for n in need:
            m = OUT / f"{n}.manifest.json"
            man = json.loads(m.read_text(encoding="utf-8")) if m.exists() else {}
            ok = (m.exists() and man.get("schema") == "asof_invariant/1"
                  and man.get("content_sha256") == ai.content_hash(OUT / n)
                  and man.get("content_bytes") == (OUT / n).stat().st_size
                  and man.get("producer") == "prediction_contract_v4.py")
            check(f"  {n} carries a valid asof_invariant/1 sidecar bound to its bytes", ok,
                  str({k: man.get(k) for k in ("schema", "producer")}))

        tg = pd.read_parquet(OUT / "team_game.parquet")
        check("team_game keeps every zero-candidate team-game visible, with a named reason",
              int((tg.n_candidates.fillna(0) == 0).sum()) == 76
              and tg.loc[tg.n_candidates.fillna(0) == 0,
                         "zero_candidate_reason"].notna().all(),
              str(int((tg.n_candidates.fillna(0) == 0).sum())))
        check("  ... and team_game's own row_uid is unique", tg.row_uid.is_unique)
        gm = pd.read_parquet(OUT / "game.parquet")
        check("game.parquet holds one unique row per game",
              len(gm) == 1495 and gm.row_uid.is_unique, str(len(gm)))

    print("\n6. the v3 gate itself is unchanged -- the back-to-back case still holds")
    mp = master(B2B)
    cand, win = build_candidates(mp, B2B_CUT)
    w = window_for(win, 10, "g7")
    got = cand_for(cand, 10, "g7")
    check("last night's box score is NOT admitted at a date-only cutoff", 96 not in got)
    check("  ... the window reaches BACK to g1 rather than shrinking",
          91 in got and int(w.lookback_games_used) == ROSTER_LOOKBACK
          and (w.admitted_window_first_game, w.admitted_window_last_game) == ("g1", "g5"))
    check("  ... and is flagged shifted vs the positional five",
          bool(w.window_shifted_vs_positional))
    eq = dict(B2B_CUT, g7=pd.Timestamp("2024-06-11T12:00Z"))
    check("equality with the prior bound is a VIOLATION, not a pass",
          96 not in cand_for(build_candidates(mp, eq)[0], 10, "g7"))
    lt = dict(B2B_CUT, g7=pd.Timestamp("2024-06-11T12:00:00.000001Z"))
    check("  ... and one microsecond later it IS admitted",
          96 in cand_for(build_candidates(mp, lt)[0], 10, "g7"))
    check("a debut appearing ONLY in the target game is not a candidate", 77 not in got)
    blank = mp.copy()
    blank.loc[blank.game_id == "g7", ["minutes", "pts", "fga"]] = None
    check("blanking the target's own rows does not change candidacy",
          cand_for(build_candidates(blank, B2B_CUT)[0], 10, "g7") == got)
    two = B2B + [("h1", "2025-06-01", 10, 2025, [1, 2, 3]),
                 ("h2", "2025-06-04", 10, 2025, [1, 2, 3])]
    c2, w2 = build_candidates(master(two), {g: date_only(d) for g, d, *_ in two})
    check("the season opener yields zero candidates, with a named reason",
          cand_for(c2, 10, "h1") == set()
          and window_for(w2, 10, "h1").zero_candidate_reason
          == "season_opener_no_prior_in_season_game")
    check("  ... and the lookback does not leak across the season boundary",
          91 not in cand_for(c2, 10, "h2"))
    try:
        build_candidates(mp, {g: c for g, c in B2B_CUT.items() if g != "g7"})
        ok = False
    except SystemExit:
        ok = True
    check("a game with no cutoff is refused, never guessed", ok)
    try:
        build_candidates(mp, dict(B2B_CUT, g7=pd.NaT))
        ok = False
    except SystemExit:
        ok = True
    check("a null cutoff is refused", ok)
    try:
        build_candidates(mp, B2B_CUT, membership="something_else")
        ok = False
    except SystemExit:
        ok = True
    check("an unregistered membership rule is refused, never defaulted", ok)

    print("\n7. ZERO fits, predictions, scores or evaluations")
    banned = ("sklearn", "statsmodels", "xgboost", "lightgbm", "torch", ".fit(", ".predict(",
              "predict_proba", "log_loss", "roc_auc", "brier", "accuracy_score", "r2_score",
              "np.polyfit", "mean_squared_error", "roi", "profit")
    for mod in ("prediction_contract_v4.py", "cbs_provenance_v4.py"):
        src = (REPO / mod).read_text(encoding="utf-8")
        hits = [b for b in banned if b in src]
        check(f"{mod} imports no estimator and calls no fit/predict/score", not hits, str(hits))
    if (OUT / "player_game.parquet").exists():
        pg = pd.read_parquet(OUT / "player_game.parquet")
        pred_like = [c for c in pg.columns
                     if ("pred" in c.lower() or "score" in c.lower() or "yhat" in c.lower())
                     and not c.startswith(("prediction_required__", "outcome_scoreable__"))]
        check("the emitted frame carries no prediction or score column -- only the two "
              "obligation FLAGS", not pred_like, str(pred_like))
        check("  ... and prediction_required is True for every obligation, independently of "
              "whether the outcome is scoreable",
              bool(pg["prediction_required__e_minutes_given_active"].all())
              and int(pg["outcome_scoreable__e_minutes_given_active"].sum()) < len(pg))
        doc = json.loads((OUT / "contract.json").read_text(encoding="utf-8"))
        check("the contract states in its own words that nothing is fitted",
              "fits nothing, predicts nothing and scores nothing" in doc["nothing_is_fitted"])

    print("\n8. cbs_provenance/4 makes the key a PRECONDITION, and would have caught v3")
    import tempfile
    import cbs_provenance_v4 as prov4
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / prov4.CONTRACT_DIR).mkdir(parents=True)
        # a frame keyed the v3 way: a 'row_uid' column holding the TEAM-BLIND value
        bad = pd.DataFrame({
            "row_uid": [v2.pg_uid(p, g) for p, g, _ in v4_key_probe()],
            "player_game_uid": [v2.pg_uid(p, g) for p, g, _ in v4_key_probe()],
            "obligation_key_id": ["cbs_obligation_key/1"] * 4,
            "player_id": [p for p, _, _ in v4_key_probe()],
            "game_id": [g for _, g, _ in v4_key_probe()],
            "team_id": [t for _, _, t in v4_key_probe()]})
        bad.to_parquet(root / prov4.PLAYER_GAME, index=False)
        st = prov4.obligation_key_status(root)
        check("a v3-style team-blind key is REJECTED as non-unique",
              st["unique"] is False and st["n_rows_sharing_a_row_uid"] == 4 and not st["ok"])
        check("  ... and the message names the MergeError it caused",
              any("MergeError" in p for p in st["problems"]), str(st["problems"])[:160])
        check("  ... and is separately rejected as non-recomputable from (player, game, team)",
              st["recomputes"] is False)
        check("every key failure is a HARD blocker, not a warning",
              len(prov4.obligation_key_blockers(st)) == len(st["problems"]) >= 2
              and all(b["kind"] == "obligation_key_violation"
                      for b in prov4.obligation_key_blockers(st)))
    st_real = prov4.obligation_key_status(REPO)
    check("the REAL v4 frame passes all four key preconditions",
          st_real["ok"] and st_real["unique"] and st_real["recomputes"]
          and st_real["legacy_recomputes"] and st_real["declared"], str(st_real["problems"]))
    rb_real = prov4.roster_binding_status(REPO)
    check("the REAL v4 frame passes the roster-binding preconditions",
          rb_real["ok"], str(rb_real["problems"]))
    dc_real = prov4.contract_declaration_status(REPO)
    check("the REAL contract.json declares membership, key, binding and 8-field cutoff "
          "identity", dc_real["ok"], str(dc_real["problems"]))
    aud = prov4.audit(REPO)
    check("cbs_provenance/4 reports ZERO hard blockers over the real v4 artifact set",
          aud["n_hard_blockers"] == 0 and aud["provenance_preconditions_met"],
          str(aud["hard_blockers"])[:300])
    check("  ... and still refuses to call that permission to run",
          aud["supervisory_authorization_required"] is True
          and "not authorization to fit" in aud["verdict"]
          and "real_run_permitted" not in aud)
    check("the required artifact set is exactly the five v4 inputs",
          aud["n_required_artifacts"] == 5
          and prov4.PLAYER_GAME.startswith("experiments/prediction_contract_v4"))
    try:
        # `schema` is supplied so this fixture isolates the obligation-key check. The
        # coordinator's fan-in change made require_real_snapshot_manifest enforce the
        # manifest schema too, and without a valid /5 label this manifest would be refused
        # earlier for the wrong reason. Schema refusal is covered in tests/test_cbs_v11.py.
        prov4.require_real_snapshot_manifest(
            {"schema": prov4.SNAPSHOT_MANIFEST_SCHEMA,
             "frame_identity_schema": prov4.FRAME_IDENTITY_SCHEMA,
             "artifacts": {k: {} for k in prov4.CBS_REQUIRED_ARTIFACTS},
             "frames": {"player": "x"}})
        raised = False
    except prov4.ArtifactSetError as exc:
        raised = "obligation_key_id" in str(exc)
    check("a snapshot manifest that does not NAME the obligation key is refused", raised)

    print(f"\n{PASSED}/{PASSED + len(FAILED)} tests passed")
    if FAILED:
        for f in FAILED:
            print(f"  - {f}")
    return 1 if FAILED else 0


def test_prediction_contract_v4() -> None:
    """pytest entry point; the script form below prints the same report."""
    assert main() == 0, FAILED


if __name__ == "__main__":
    sys.exit(main())
