#!/usr/bin/env python
"""test_cbs_accounting_v11.py — verification suite for `cbs_accounting/11`.

**REAL-DATA SUITE, and deliberately so.** Unlike the four `contract_baseline_suite`
suites, which are synthetic by construction, this one exists precisely to check
that numbers quoted in prose still hold against the artifact bytes on disk. It
therefore reads the real contract tables and the real masters, and it REBUILDS
the real player frame twice (about two and a half minutes). It fits nothing,
predicts nothing, scores nothing, and hands nothing to an estimator.

Every documented value is written out here as a hand-transcribed literal, taken
from `project_docs/CONTRACT_BASELINE_SUITE_V10.md`, so the suite states its
expectation independently of the module and of the emitted receipt. Three things
are then asserted for each number:

    1. the emitted receipt's recorded digest matches its own bytes, and its
       sidecar is a well-formed `asof_invariant/1` manifest;
    2. the value RECOMPUTED here from real data equals the value the receipt
       claims;
    3. the recomputed value equals the DOCUMENTED value — or, where it does not,
       the receipt records the mismatch explicitly rather than hiding it.

  A  receipt bytes, sidecars and digests
  B  7a candidate-count distribution per team-game, recomputed independently
  C  7b per-season team presence and the franchise transitions
  D  7c source maxima: 185 -> 0, 23 -> 0, 1,060 -> 0, 881, 25,498
  E  7c DNP taxonomy: 107 rows, 57/42/7/1
  F  7c downstream: 368 / 424 / 146
  G  7d the A15 receipt digests, raw and LF-normalized
  H  the v3 entry-point status, recorded as a measured fact
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asof_invariant as aoi  # noqa: E402
import cbs_accounting_v11 as acc  # noqa: E402
import cbs_provenance as prov2  # noqa: E402
import cbs_provenance_v3 as prov  # noqa: E402
import cbs_real_frames_v2 as rf2  # noqa: E402

PASSED = 0
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")


OUT = ROOT / acc.OUT_REL
RECEIPTS = ("candidate_count_per_team_game", "team_season_presence",
            "source_maxima", "dnp_taxonomy", "a15_receipt_digest", "index")


def load(name: str) -> dict:
    return json.loads((OUT / f"{name}.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# A -- the emitted receipts are hash-bound to their own bytes
# --------------------------------------------------------------------------

for _n in RECEIPTS:
    _p = OUT / f"{_n}.json"
    _m = OUT / f"{_n}.json.manifest.json"
    check(f"A {_n}.json exists", _p.exists(), str(_p))
    check(f"A {_n}.json.manifest.json exists", _m.exists(), str(_m))
    if not (_p.exists() and _m.exists()):
        continue
    _doc = json.loads(_m.read_text(encoding="utf-8"))
    _raw = hashlib.sha256(_p.read_bytes()).hexdigest()
    check(f"A {_n} sidecar declares the asof_invariant/1 schema",
          _doc.get("schema") == "asof_invariant/1", str(_doc.get("schema")))
    check(f"A {_n} sidecar content_sha256 equals the SHA-256 of the bytes",
          _doc.get("content_sha256") == _raw,
          f"{_doc.get('content_sha256')} != {_raw}")
    check(f"A {_n} sidecar content_bytes equals the file size",
          _doc.get("content_bytes") == _p.stat().st_size,
          f"{_doc.get('content_bytes')} != {_p.stat().st_size}")
    check(f"A {_n} sidecar names this module as the producer",
          _doc.get("producer") == "cbs_accounting_v11.py", str(_doc.get("producer")))
    check(f"A {_n} sidecar carries the accounting id",
          _doc.get("accounting_id") == acc.ACCOUNTING_ID,
          str(_doc.get("accounting_id")))
    check(f"A {_n} sidecar reads back through asof_invariant.read_manifest",
          aoi.read_manifest(_p)["content_sha256"] == _raw)
    check(f"A {_n} sidecar bound is the contract's own bound convention",
          _doc.get("fit_through_date") == "2026-08-01T12:00:00+00:00",
          str(_doc.get("fit_through_date")))

# a digest that is NOT the bytes must be detectable -- the negative control
_p = OUT / "index.json"
check("A a one-byte change would break the recorded digest",
      hashlib.sha256(_p.read_bytes() + b" ").hexdigest()
      != json.loads((OUT / "index.json.manifest.json").read_text(
          encoding="utf-8"))["content_sha256"])

_index = load("index")
check("A the index records every other receipt",
      set(_index["receipts"]) == set(RECEIPTS) - {"index"},
      str(sorted(_index["receipts"])))
for _n in RECEIPTS:
    if _n == "index":
        continue
    _claim = _index["receipts"][_n]["sha256"]
    _actual = hashlib.sha256((OUT / f"{_n}.json").read_bytes()).hexdigest()
    check(f"A the index's digest for {_n} matches its bytes",
          _claim == _actual, f"{_claim} != {_actual}")

for _n in RECEIPTS:
    if _n == "index":
        continue
    _r = load(_n)
    check(f"A {_n} declares the accounting receipt schema",
          _r.get("schema") == acc.RECEIPT_SCHEMA and
          _r.get("accounting_id") == acc.ACCOUNTING_ID, str(_r.get("schema")))
    check(f"A {_n} states that no model is involved",
          _r.get("no_model_involved") is True)

# the inputs each receipt names are still the bytes on disk
for _n in ("candidate_count_per_team_game", "team_season_presence",
           "source_maxima", "dnp_taxonomy"):
    _bad = []
    for _i in load(_n)["inputs"]:
        _f = ROOT / _i["relpath"]
        if (not _f.exists()) or acc.sha256_bytes(_f) != _i["sha256"]:
            _bad.append(_i["relpath"])
    check(f"A {_n}'s declared input digests still match the artifacts on disk",
          not _bad, str(_bad))
    _lie = [i["relpath"] for i in load(_n)["inputs"]
            if i.get("manifest_agrees_with_bytes") is False]
    check(f"A no input of {_n} has a sidecar that disagrees with its bytes",
          not _lie, str(_lie))


# --------------------------------------------------------------------------
# B -- 7a, recomputed independently of the module
# --------------------------------------------------------------------------

_a = load("candidate_count_per_team_game")["result"]
_pg = pd.read_parquet(ROOT / prov.PLAYER_GAME_V3,
                      columns=["team_id", "game_id", "player_id"])
_tg = pd.read_parquet(ROOT / prov.TEAM_GAME_V3,
                      columns=["team_id", "game_id", "n_candidates",
                               "zero_candidate_reason"])
_n = (_pg.groupby(["team_id", "game_id"]).size().rename("k").reset_index())
_m = _tg.merge(_n, on=["team_id", "game_id"], how="left")
_m["k"] = _m["k"].fillna(0).astype("int64")
_k = _m["k"]

check("B the obligation key (team_id, game_id, player_id) is unique",
      not _pg.duplicated(["team_id", "game_id", "player_id"]).any())
check("B 35,627 obligations over 2,990 team-games",
      _a["obligations_total"] == 35627 == len(_pg)
      and _a["team_games_total"] == 2990 == len(_m),
      f"{_a['obligations_total']} / {_a['team_games_total']}")
check("B the recomputed per-team-game count equals the contract's n_candidates",
      bool((_m["k"] == _m["n_candidates"]).all())
      and _a["recomputed_matches_contract_n_candidates"] is True)

_inc = _a["including_zero_candidate_team_games"]
check("B including zeros: min 0, max 17, median 12",
      (_inc["min"], _inc["max"], _inc["median"]) == (int(_k.min()),
                                                     int(_k.max()),
                                                     float(_k.median()))
      == (0, 17, 12.0), str(_inc))
check("B including zeros: the mean is the receipt's mean",
      abs(_inc["mean"] - float(_k.mean())) < 5e-7, str(_inc["mean"]))
check("B including zeros: the counts sum to the obligation total",
      _inc["sum"] == int(_k.sum()) == 35627)

_exc = _a["excluding_zero_candidate_team_games"]
_nz = _k[_k > 0]
check("B excluding zeros: 2,914 team-games, min 9, max 17",
      (_exc["n_team_games"], _exc["min"], _exc["max"])
      == (int(len(_nz)), int(_nz.min()), int(_nz.max())) == (2914, 9, 17),
      str(_exc))
check("B excluding zeros: the mean is the receipt's mean",
      abs(_exc["mean"] - float(_nz.mean())) < 5e-7, str(_exc["mean"]))

_hist = {str(int(a)): int(b) for a, b in _k.value_counts().sort_index().items()}
check("B the full histogram is reproduced exactly",
      _a["histogram"] == _hist, str(_a["histogram"]))
check("B the histogram's frequencies sum to the team-game total",
      sum(_a["histogram"].values()) == 2990)
check("B the histogram's weighted sum is the obligation total",
      sum(int(k) * v for k, v in _a["histogram"].items()) == 35627)

check("B the 76 zero-candidate team-games are all season openers",
      _a["anomalies"]["zero_candidate_team_games"] == int((_k == 0).sum()) == 76
      and _a["anomalies"]["zero_candidate_reasons"]
      == {"season_opener_no_prior_in_season_game": 76},
      str(_a["anomalies"]["zero_candidate_reasons"]))
check("B exactly six nonzero team-games are below ten candidates",
      _a["anomalies"]["n_thin_team_games"] == int(((_k > 0) & (_k < 10)).sum()) == 6,
      str(_a["anomalies"]["n_thin_team_games"]))
check("B two of the six thin team-games had a FULL five-game admitted window",
      _a["anomalies"]["thin_by_lookback_games_used"].get("5") == 2,
      str(_a["anomalies"]["thin_by_lookback_games_used"]))
check("B counts above twelve are reported and named non-anomalous",
      _a["anomalies"]["n_above_twelve"] == int((_k > 12).sum()) == 993,
      str(_a["anomalies"]["n_above_twelve"]))
check("B the sole 17-candidate team-game is the 2025 Valkyries row",
      len(_a["extreme_high_team_games"]) == 1
      and _a["extreme_high_team_games"][0]["team_id"] == 1611661331
      and _a["extreme_high_team_games"][0]["n_candidates"] == 17,
      str(_a["extreme_high_team_games"]))
check("B this receipt is keyed per TEAM-GAME, not per game like the contract block",
      _a["key"] == "(team_id, game_id)"
      and "1458" in _a["distinguished_from_the_contract_block"][
          "contract_block_is_keyed_per"])
_contract = json.loads((ROOT / prov.CONTRACT_JSON_V3).read_text(encoding="utf-8"))
check("B the contract's own candidate_count_distribution really is per GAME",
      _contract["accounting"]["candidate_count_distribution"]["count"] == 1458.0
      and _contract["accounting"]["candidate_games"] == 1458,
      "the per-game block and the per-team-game block are different quantities")


# --------------------------------------------------------------------------
# C -- 7b, per-season team presence
# --------------------------------------------------------------------------

_b = load("team_season_presence")["result"]
_mt = pd.read_parquet(ROOT / prov2.MASTER_TEAM,
                      columns=["team_id", "team_abbreviation", "season"])
_grid = pd.crosstab(_mt["team_id"], _mt["season"])

#: hand-transcribed: the three ids the contract says are not in every season
EXPECTED_ABSENT = {
    1611661331: {"franchise": "Golden State Valkyries", "abbr": "GSV",
                 "absent": [2021, 2022, 2023, 2024], "first": 2025},
    1611661327: {"franchise": "Portland Fire", "abbr": "PDX",
                 "absent": [2021, 2022, 2023, 2024, 2025], "first": 2026},
    1611661332: {"franchise": "Toronto Tempo", "abbr": "TOR",
                 "absent": [2021, 2022, 2023, 2024, 2025], "first": 2026},
}

check("C fifteen team ids across six seasons 2021-2026",
      _b["teams_total"] == int(_grid.shape[0]) == 15
      and _b["seasons_covered"] == [2021, 2022, 2023, 2024, 2025, 2026],
      f"{_b['teams_total']} / {_b['seasons_covered']}")
check("C exactly three team ids are absent from at least one season",
      _b["teams_not_in_every_season"] == int((_grid == 0).any(axis=1).sum()) == 3,
      str(_b["teams_not_in_every_season"]))
check("C the three absent ids are the expected three",
      set(_b["team_ids_not_in_every_season"]) == set(EXPECTED_ABSENT),
      str(_b["team_ids_not_in_every_season"]))
check("C the contract's own accounting agrees: 15 teams, 3 not in every season",
      _contract["accounting"]["teams_total"] == 15
      and _contract["accounting"]["teams_not_in_every_season"] == 3)
check("C the master presence grid equals the v3 contract presence grid",
      _b["presence_grid_master_equals_contract"] is True)

for _tid, _exp in EXPECTED_ABSENT.items():
    _e = _b["per_team"][str(_tid)]
    _c = _b["absent_ids_classified"][str(_tid)]
    _measured_absent = [int(s) for s in _grid.columns if _grid.loc[_tid, s] == 0]
    check(f"C {_exp['abbr']} is absent exactly in {_exp['absent']}",
          _e["seasons_absent"] == _measured_absent == _exp["absent"],
          str(_e["seasons_absent"]))
    check(f"C {_exp['abbr']} first appears in {_exp['first']}",
          _e["first_season_in_data"] == _exp["first"],
          str(_e["first_season_in_data"]))
    check(f"C team_cities.csv independently declares {_exp['abbr']}'s first season",
          _e["declared_first_season_matches_data"] is True,
          str(_e["first_season_declared_in_team_cities_csv"]))
    check(f"C {_exp['abbr']}'s absence is classed REAL_FRANCHISE_HISTORY",
          _c["verdict"] == "REAL_FRANCHISE_HISTORY", _c["verdict"])
    check(f"C {_exp['abbr']} is named as {_exp['franchise']}",
          _c["franchise"] == _exp["franchise"], str(_c["franchise"]))
    check(f"C {_exp['abbr']}'s pre-2021 history is left UNDETERMINED",
          _c["pre_2021_history_undetermined"] is True
          and "not determinable" in _c["pre_2021_history_note"].lower())
    check(f"C every {_exp['abbr']} absence precedes its first season",
          max(_e["seasons_absent"]) < _e["first_season_in_data"],
          "a gap AFTER the first season would be a data gap, not franchise history")

check("C the twelve continuous franchises are present in all six seasons",
      int((_grid > 0).all(axis=1).sum()) == 12,
      str(int((_grid > 0).all(axis=1).sum())))

check("C exactly one franchise transition is measured in the window",
      _b["franchise_transition_count"] == 1, str(_b["franchise_transition_count"]))
_t = _b["franchise_transitions"][0]
check("C the transition is the Phoenix Mercury PHO -> PHX abbreviation change",
      _t["team_id"] == 1611661317 and _t["abbreviations"] == ["PHO", "PHX"]
      and _t["franchise"] == "Phoenix Mercury", str(_t["abbreviations"]))
check("C the transition keeps a STABLE team_id across the rename",
      _t["kind"] == "abbreviation_change_on_a_STABLE_team_id"
      and bool((_grid.loc[1611661317] > 0).all()),
      "the id is present in every season; only the abbreviation moves")
check("C PHO runs 2021-2024 and PHX from 2025, measured from the master",
      [k for k, v in _t["abbreviation_by_season"].items() if v == ["PHO"]]
      == ["2021", "2022", "2023", "2024"]
      and [k for k, v in _t["abbreviation_by_season"].items() if v == ["PHX"]]
      == ["2025", "2026"], str(_t["abbreviation_by_season"]))
check("C the rename is MEASURED not to be a relocation",
      _t["relocation"] is False and _t["location_fields_that_changed"] == {}
      and set(_t["location_fields_compared"])
      >= {"city", "arena", "lat", "lon"},
      str(_t["location_fields_that_changed"]))
check("C no relocation occurs anywhere in the window",
      _b["relocations_in_window"] == 0)
check("C the abbreviation is flagged as an unsafe cross-season join key",
      "not a stable join key" in _t["consequence"].lower()
      or "NOT a stable join key" in _t["consequence"])
check("C 2026's shorter per-team game counts are labelled in-progress, not a gap",
      "mid-flight" in _b["2026_is_in_progress"]["note"]
      and _b["2026_is_in_progress"]["max_game_date_in_master"] == "2026-07-31")


# --------------------------------------------------------------------------
# the two real frame builds, done once and shared by D, E and F
# --------------------------------------------------------------------------

print("  ... rebuilding the real player frame twice (v2 universe); "
      "this takes a couple of minutes", flush=True)
FRAMES = acc.build_v2_universe_frames(ROOT)
check("D the two builds cover the same 35,615-obligation universe",
      len(FRAMES["semantic"]) == len(FRAMES["legacy"]) == 35615,
      f"{len(FRAMES['semantic'])} / {len(FRAMES['legacy'])}")


# --------------------------------------------------------------------------
# D -- 7c, the source maxima corrections
# --------------------------------------------------------------------------

#: hand-transcribed from CONTRACT_BASELINE_SUITE_V10.md section 4
DOC_SOURCE_MAXIMA = {
    "team_source_newer_than_reported__before": 185,
    "team_source_newer_than_reported__after": 0,
    "newer_than_the_reported_maximum__before": 23,
    "newer_than_the_reported_maximum__after": 0,
    "false_no_prior_game_admitted__before": 1060,
    "false_no_prior_game_admitted__after": 0,
    "roster_bound_differs_from_player_bound_rows": 881,
    "roster_and_team_different_record_sets_rows": 25498,
    "roster_and_team_bounds_coincide_rows": 35615,
    "roster_and_team_bounds_coincide_of": 35615,
}
check("D the suite's transcription of the doc matches the module's",
      DOC_SOURCE_MAXIMA == {k: acc.DOCUMENTED[k] for k in DOC_SOURCE_MAXIMA},
      "two independent transcriptions of the same doc paragraph disagree")

_d = load("source_maxima")["result"]
_live = acc.source_maxima(ROOT, frames=FRAMES)

for _k, _want in DOC_SOURCE_MAXIMA.items():
    _receipt = _d["comparison"][_k]["recomputed"]
    _now = _live["comparison"][_k]["recomputed"]
    check(f"D {_k}: recomputed now == the receipt's value",
          _now == _receipt, f"{_now} != {_receipt}")
    check(f"D {_k}: recomputed {_now} == documented {_want}",
          _now == _want,
          f"DOCUMENTED VALUE DOES NOT REPRODUCE: doc says {_want}, data says {_now}")
    check(f"D {_k}: the receipt records the reproduction verdict",
          _d["comparison"][_k]["reproduces"] == (_receipt == _want))

check("D the receipt claims every section-4 number reproduces",
      _d["all_reproduce"] is True and _d["mismatches"] == {},
      str(_d["mismatches"]))
check("D the receipt names the v2 universe, not v3",
      "prediction_contract_v2" in _d["universe"] and _d["universe_rows"] == 35615,
      _d["universe"])

# the definitions are checked by re-deriving them from the frame here
_fr = FRAMES["semantic"]
_gl = pd.to_datetime(_fr["src_asof_gamelog"], utc=True)
_tm = pd.to_datetime(_fr["src_asof_team_gamelog"], utc=True)
_rs = pd.to_datetime(_fr["src_asof_roster"], utc=True)
_sc = pd.to_datetime(_fr["src_asof_schedule"], utc=True)
_cp = pd.to_datetime(_fr[rf2.FEATURE_ASOF_COL], utc=True)
_v1max = pd.concat([_gl, _sc], axis=1).max(axis=1)

check("D 185 is independently reproduced from the frame's own columns",
      int((_tm > _gl).sum()) == 185, str(int((_tm > _gl).sum())))
check("D 23 is independently reproduced from the frame's own columns",
      int((_tm > _v1max).sum()) == 23, str(int((_tm > _v1max).sum())))
check("D the 23 are a subset of the 185",
      bool(((_tm > _v1max) <= (_tm > _gl)).all()))
check("D 1,060 is independently reproduced from the frame's own columns",
      int(((_fr["src_policy_gamelog"] == rf2.NO_EVIDENCE_POLICY)
           & (_fr["n_src_team_games_consumed"] > 0)).sum()) == 1060)
check("D 881 is independently reproduced from the frame's own columns",
      int((_rs != _gl).sum()) == 881, str(int((_rs != _gl).sum())))
check("D 25,498 is independently reproduced from the frame's own columns",
      int((_fr["n_roster_games_consumed"]
           != _fr["n_src_team_games_consumed"]).sum()) == 25498)
check("D the roster and team bounds coincide on all 35,615 rows",
      int((_rs == _tm).sum()) == 35615)
check("D AFTER: no source anywhere exceeds the composite feature_asof",
      all(int((s > _cp).sum()) == 0 for s in (_gl, _tm, _rs, _sc)))
check("D AFTER: every remaining no-evidence label is genuine",
      int(((_fr["src_policy_gamelog"] == rf2.NO_EVIDENCE_POLICY)
           & (_fr["n_src_player_rows_consumed"] > 0)).sum()) == 0
      and int((_fr["src_policy_team_gamelog"]
               == rf2.NO_EVIDENCE_POLICY).sum()) == 0
      and int((_fr["src_policy_roster"] == rf2.NO_EVIDENCE_POLICY).sum()) == 0)
check("D all 1,060 surviving gamelog no-evidence labels consumed zero player rows",
      int(((_fr["src_policy_gamelog"] == rf2.NO_EVIDENCE_POLICY)
           & (_fr["n_src_player_rows_consumed"] == 0)).sum()) == 1060)

_23 = _d["the_23_detail"]
check("D the 23 split 22 in 2026 and 1 in 2025, as documented",
      _23["by_season"] == {"2025": 1, "2026": 22}, str(_23["by_season"]))
check("D 22 of the 23 consumed zero player rows, as documented",
      _23["n_that_consumed_zero_player_rows"] == 22,
      str(_23["n_that_consumed_zero_player_rows"]))
check("D the composite moved by at most 24.0 hours, as documented",
      _23["max_composite_shift_hours"] == 24.0,
      str(_23["max_composite_shift_hours"]))
_sel = _fr.loc[(_tm > _v1max).values, "row_uid"]
_pol = (pd.read_parquet(ROOT / prov2.PLAYER_GAME,
                        columns=["row_uid", "cutoff_policy"])
        .set_index("row_uid")["cutoff_policy"])
check("D every one of the 23 carries cutoff_policy == exact_tip_T-90m",
      len(_sel) == 23
      and set(_pol.reindex(_sel).unique()) == {"exact_tip_T-90m"},
      f"{len(_sel)} rows, policies {sorted(set(_pol.reindex(_sel).dropna()))}")
check("D the date-only rows can never trip this defect",
      int((_tm > _v1max)[(_pol.reindex(_fr['row_uid']).values
                          == 'date_only_prior_day_cutoff')].sum()) == 0,
      "under an 18:00Z prior-day cutoff the team bound cannot exceed noon that day")


# --------------------------------------------------------------------------
# E -- 7c, the DNP taxonomy reclassification
# --------------------------------------------------------------------------

#: hand-transcribed from CONTRACT_BASELINE_SUITE_V10.md section 6
DOC_DNP_ROWS_CHANGED = 107
DOC_DNP_PAIRS = {"INJ->CD": 57, "CD->INJ": 42, "INJ->UNKNOWN": 7, "CD->UNKNOWN": 1}

_e = load("dnp_taxonomy")["result"]
_diff = rf2.dnp_taxonomy_diff(ROOT)

check("E the taxonomy diff comes from the immutable dnp_taxonomy_diff()",
      "dnp_taxonomy_diff" in _e["taxonomy_source"])
check("E 107 rows change class: recomputed == receipt",
      int(_diff["n_rows_changed"])
      == _e["comparison"]["dnp_rows_changing_class"]["recomputed"],
      str(_diff["n_rows_changed"]))
check("E 107 rows change class: recomputed == documented",
      int(_diff["n_rows_changed"]) == DOC_DNP_ROWS_CHANGED,
      f"DOCUMENTED VALUE DOES NOT REPRODUCE: doc says {DOC_DNP_ROWS_CHANGED}, "
      f"data says {_diff['n_rows_changed']}")
check("E the breakdown 57/42/7/1: recomputed == receipt",
      dict(_diff["changes_by_pair"])
      == _e["comparison"]["dnp_changes_by_pair"]["recomputed"],
      str(_diff["changes_by_pair"]))
check("E the breakdown 57/42/7/1: recomputed == documented",
      dict(_diff["changes_by_pair"]) == DOC_DNP_PAIRS,
      f"DOCUMENTED VALUE DOES NOT REPRODUCE: doc says {DOC_DNP_PAIRS}, "
      f"data says {dict(_diff['changes_by_pair'])}")
check("E the four transitions sum to the 107 total",
      sum(DOC_DNP_PAIRS.values()) == DOC_DNP_ROWS_CHANGED == 107)
check("E no NWT row changes class",
      not any(k.startswith("NWT") or k.endswith("NWT")
              for k in _diff["changes_by_pair"]),
      str(list(_diff["changes_by_pair"])))
check("E every reason string in the master is in the frozen 22-string table",
      int(_diff["n_reasons_not_in_table"]) == 0
      and int(_diff["n_distinct_reasons"]) == 22,
      f"{_diff['n_reasons_not_in_table']} outside / "
      f"{_diff['n_distinct_reasons']} distinct")
check("E the per-class totals move CD 2869->2883, INJ 1776->1754, NWT 739->739",
      _diff["class_counts_prefix_rule"] == {"CD": 2869, "INJ": 1776, "NWT": 739}
      and _diff["class_counts_semantic"] == {"CD": 2883, "INJ": 1754,
                                             "NWT": 739, "UNKNOWN": 8},
      f"{_diff['class_counts_prefix_rule']} -> {_diff['class_counts_semantic']}")
check("E the class totals are conserved: 5,384 DNP rows either way",
      sum(_diff["class_counts_prefix_rule"].values())
      == sum(_diff["class_counts_semantic"].values())
      == int(_diff["n_dnp_rows"]) == 5384, str(_diff["n_dnp_rows"]))
check("E the taxonomy diff is universe-independent and says so",
      _e["taxonomy_is_universe_independent"] is True,
      "it counts master_player rows, not contract obligations")


# --------------------------------------------------------------------------
# F -- 7c, the downstream effect of the taxonomy change
# --------------------------------------------------------------------------

#: hand-transcribed from CONTRACT_BASELINE_SUITE_V10.md section 6
DOC_DOWNSTREAM = {"prev_dnp_cd": 368, "prev_dnp_inj": 424,
                  "prev_dnp_nwt": 0, "returning_flag": 146}

_sem = FRAMES["semantic"].set_index("row_uid")
_leg = FRAMES["legacy"].set_index("row_uid").reindex(_sem.index)
_moves = {c: int((_sem[c] != _leg[c]).sum()) for c in DOC_DOWNSTREAM}

check("F the legacy build reindexes onto the semantic build's row_uids without loss",
      not bool(_leg.isna().all(axis=1).any()),
      "the two builds must be over identical rows for the diff to mean anything")
for _c, _want in DOC_DOWNSTREAM.items():
    _key = f"downstream_{_c}_moves"
    check(f"F {_c} moves on {_want} rows: recomputed == receipt",
          _moves[_c] == _e["comparison"][_key]["recomputed"],
          f"{_moves[_c]} != {_e['comparison'][_key]['recomputed']}")
    check(f"F {_c} moves on {_want} rows: recomputed == documented",
          _moves[_c] == _want,
          f"DOCUMENTED VALUE DOES NOT REPRODUCE: doc says {_want}, "
          f"data says {_moves[_c]}")
check("F the receipt claims every section-6 number reproduces",
      _e["all_reproduce"] is True and _e["mismatches"] == {}, str(_e["mismatches"]))
check("F prev_dnp_nwt is unmoved, consistent with no NWT reclassification",
      _moves["prev_dnp_nwt"] == 0)
check("F the two builds differ ONLY in the taxonomy, and the receipt says so",
      "dnp_class" in _e["isolation"] and "not modified" in _e["isolation"])
check("F cbs_real_frames_v2.dnp_class is restored after the swapped build",
      rf2.dnp_class is not rf2.legacy_prefix_dnp_class
      and rf2.dnp_class("DND - Rest") == "CD",
      "a leaked monkeypatch would silently corrupt every later import")
check("F prev_dnp_unknown moves on 56 rows and is NOT a frozen feature",
      _e["downstream_all_moves"]["prev_dnp_unknown"] == 56
      and "P_ACTIVE_FEATURES" in _e["prev_dnp_unknown_note"],
      str(_e["downstream_all_moves"]))


# --------------------------------------------------------------------------
# G -- 7d, the A15 receipt digests
# --------------------------------------------------------------------------

#: hand-transcribed: the truncated value quoted in the v10 handoff and in
#: handoff/correspondence/state/CURRENT_STATE.md, and the supervisor's raw value
DOC_QUOTED_TRUNCATED = "9ba369cc0186fdfd"
DOC_SUPERVISOR_RAW = ("697595497db7eb97fe50ba4b1e5b92b043306b25ea7d9de6f64d"
                      "4060af7de5a7")

_g = load("a15_receipt_digest")["result"]
_a15 = Path(_g["artifact"])
check("G the A15 receipt file is present", _a15.exists(), str(_a15))
if _a15.exists():
    _bytes = _a15.read_bytes()
    _raw = hashlib.sha256(_bytes).hexdigest()
    _lf = hashlib.sha256(_bytes.replace(b"\r\n", b"\n")).hexdigest()
    check("G the raw digest recomputed here matches the receipt",
          _raw == _g["raw_sha256"], f"{_raw} != {_g['raw_sha256']}")
    check("G the LF-normalized digest recomputed here matches the receipt",
          _lf == _g["lf_normalized_sha256"], f"{_lf} != {_g['lf_normalized_sha256']}")
    check("G the RAW digest is the supervisor's correction-7 value",
          _raw == DOC_SUPERVISOR_RAW and _g["raw_matches_supervisor_correction_7"],
          _raw)
    check("G the quoted 9ba369cc… prefix is the LF-NORMALIZED digest, not the raw one",
          _lf.startswith(DOC_QUOTED_TRUNCATED)
          and not _raw.startswith(DOC_QUOTED_TRUNCATED),
          f"raw={_raw[:16]} lf={_lf[:16]}")
    check("G the two digests genuinely differ",
          _raw != _lf and _g["raw_differs_from_lf"] is True)
    _n_cr, _n_crlf, _n_lf = (_bytes.count(b"\r"), _bytes.count(b"\r\n"),
                             _bytes.count(b"\n"))
    check("G the file on disk is CRLF: 205 CR bytes, every LF preceded by a CR",
          _n_cr == 205 == _n_crlf == _n_lf == _g["cr_bytes"]
          and _g["file_is_crlf"] is True,
          f"CR={_n_cr} CRLF={_n_crlf} LF={_n_lf}")
    check("G there are no bare LF line endings",
          _g["bare_lf_line_endings"] == 0)
    check("G the quoted digest was also truncated to 16 hex characters",
          _g["quoted_value_truncated_to_hex_chars"] == 16 == len(DOC_QUOTED_TRUNCATED)
          and len(_raw) == 64)
    check("G the receipt names the RAW digest as authoritative",
          _g["authoritative"] == "raw_sha256", _g["authoritative"])
    check("G the receipt's byte count matches the file",
          _g["content_bytes"] == len(_bytes) == 5455, str(len(_bytes)))
    check("G an LF-normalizing digest is labelled a diagnostic, never an identity",
          "diagnostic" in acc.sha256_lf_normalized.__doc__.lower())


# --------------------------------------------------------------------------
# H -- the v3 entry-point status, as a measured fact
# --------------------------------------------------------------------------

_h = _d["v3_entry_point_status"]
check("H the registered v3 player_game has 35,627 rows",
      _h["player_game_rows"] == 35627)
check("H v3 carries 28 duplicated (game_id, player_id) rows in 14 pairs",
      _h["duplicate_game_id_player_id_rows"] == 28
      and _h["duplicate_game_id_player_id_pairs"] == 14,
      f"{_h['duplicate_game_id_player_id_rows']} rows")
check("H every duplicate is a flagged row_uid collision, not a data error",
      _h["all_duplicates_flagged_row_uid_shared_with_other_team"] is True)
check("H the duplicate count matches the contract's own accounting",
      _contract["accounting"]["obligations_sharing_a_row_uid"] == 28)
check("H build_player_frame RAISES MergeError on the registered v3 universe",
      _h["build_player_frame"]["raised"] is True
      and _h["build_player_frame"]["type"] == "MergeError",
      str(_h["build_player_frame"]))
check("H build_team_frame DOES build on v3, so the break is player-side only",
      _h["build_team_frame"]["builds"] is True
      and _h["build_team_frame"]["rows"] == 2990,
      str(_h["build_team_frame"]))
_live_raised = False
try:
    rf2.build_player_frame(2026, ROOT)
except Exception as _exc:
    _live_raised = type(_exc).__name__ == "MergeError"
check("H the v3 player-frame failure reproduces when re-run here",
      _live_raised, "build_player_frame did not raise MergeError on v3")
check("H the receipt states the consequence for the doc's numbers",
      "can be recomputed on the registered v3 universe" in _h["consequence"]
      and _h["consequence"].startswith("no section-4 or section-6 number"),
      _h["consequence"][:80])
check("H the receipt states that the immutable module was NOT repaired here",
      "IMMUTABLE" in _h["not_fixed_here"])
check("H no receipt claims the section-4/6 numbers hold for the v3 universe",
      "prediction_contract_v2" in _d["universe"]
      and "prediction_contract_v2" in _e["downstream_universe"])

check("H the suite fitted, predicted and scored nothing",
      acc.SCOPE.startswith("row counting")
      and "Nothing is fitted" in acc.SCOPE)


print(f"{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAILED  {f}")
sys.exit(1 if FAILED else 0)
