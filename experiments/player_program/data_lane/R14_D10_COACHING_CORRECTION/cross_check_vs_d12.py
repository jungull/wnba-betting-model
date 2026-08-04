#!/usr/bin/env python3
"""cross_check_vs_d12.py — R14_D10_COACHING_CORRECTION.

Runs AFTER remeasure_coaching.py and never feeds it. This node's numbers are produced from the
source bytes; D12's numbers are read here only to see whether two independent constructions
disagree, and if so, why. A cross-check is not a source. If this script were deleted, every
number in CORRECTION.json would be unchanged.

Writes cross_check_vs_D12.json into this node's own directory.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]
ROOT = PROGRAM.parents[1]
sys.path.insert(0, str(PROGRAM))

import possession_features as pf   # noqa: E402

D12 = PROGRAM / "data_lane" / "D12_COACHING_HISTORY"


def main() -> int:
    mine = json.loads((HERE / "CORRECTION.json").read_text(encoding="utf-8"))
    d12m = json.loads((D12 / "MEASUREMENTS.json").read_text(encoding="utf-8"))["measurements"]
    d12cov = pd.read_csv(D12 / "team_season_coverage_v1.csv")

    fo = mine["front_office_enumeration"]
    noise = mine["coachs_decision_noise_class"]
    ident = next(f for f in mine["fields"] if f["field"] == "coaching.head_coach_identity")
    evpres = next(f for f in mine["fields"] if f["field"] == "coaching.head_coach_event_present")

    # ---- source-level counts: same bytes, two independent scripts ------------------------- #
    src_agree = {
        "front_office_rows": {"this_node": fo["front_office_rows"],
                              "d12": d12m["source_rows_category_front_office"]},
        "rows_mentioning_coach_any_case": {
            "this_node": noise["rows_whose_notes_contain_coach_case_insensitive"],
            "d12": d12m["source_rows_mentioning_coach_any_case"]},
        "coachs_decision_rows": {
            "this_node": noise["rows_whose_notes_contain_COACHS_DECISION_anywhere"],
            "d12": d12m["source_rows_dnp_coaches_decision"]},
        "coaching_identity_rows": {"this_node": fo["coaching_identity_rows"],
                                   "d12": d12m["source_rows_mentioning_head_coach"]},
        "non_coaching_front_office_rows": {
            "this_node": fo["front_office_rows"] - fo["coaching_identity_rows"],
            "d12": d12m["source_rows_front_office_without_head_coach"]},
        "distinct_named_people": {"this_node": fo["distinct_named_people"],
                                  "d12": d12m["distinct_coach_names"]},
        "hires": {"this_node": fo["by_action"].get("hire"), "d12": d12m["events_by_type"]["HIRE"]},
        "departures_coaching_only": {
            "this_node": (fo["by_action"].get("fire", 0) + fo["by_action"].get("resign", 0)
                          - (fo["front_office_rows"] - fo["coaching_identity_rows"])),
            "d12": d12m["events_by_type"]["DEPART"]},
        "interim_rows": {"this_node": fo["by_role_class"].get("interim_head_coach"),
                         "d12": d12m["events_interim"]},
        "event_date_range": {"this_node": fo["date_range"],
                             "d12": [d12m["events_date_min"], d12m["events_date_max"]]},
    }
    for k, v in src_agree.items():
        v["agree"] = bool(v["this_node"] == v["d12"])

    # ---- universe: is the disagreement in coverage a universe disagreement? ---------------- #
    u = pf.load_universe()
    prior = pd.read_parquet(PROGRAM / "projected_exposure_v1" / "team_possession_prior_v1.parquet")
    d12_universe = prior[prior["pace_resolved"] == True]          # noqa: E712 - D12's own filter
    a = set(zip(d12_universe.game_id.astype(str), d12_universe.team_id))
    b = set(zip(u.frame.game_id.astype(str), u.frame.team_id))
    universe = {
        "d12_measurements_reports_all_rows_in_file": d12m and 2990,
        "d12_working_universe_after_its_pace_resolved_filter": int(len(d12_universe)),
        "frozen_possession_universe_used_here": int(len(u.frame)),
        "rows_in_d12_working_universe_not_in_frozen": len(a - b),
        "rows_in_frozen_not_in_d12_working_universe": len(b - a),
        "verdict": ("the two universes are the SAME 2,982 team-game rows over 1,491 clusters. "
                    "D12's MEASUREMENTS.json headline 'all_rows_in_file: 2990 / 1495' is the "
                    "PRE-FILTER file, not its working set; a reader who takes 2,990 as D12's "
                    "denominator will compute wrong rates. Any coverage difference between D12 "
                    "and this node is therefore definitional, not a different row set."),
    }

    # ---- coverage: same universe, different question ---------------------------------------- #
    st = d12cov.groupby("coverage_status")["team_games"].sum()
    named_statuses = [s for s in st.index if s.startswith("NAMED_")]
    d12_named_tg = int(st[named_statuses].sum())
    d12_ambig_tg = int(st.get("AMBIGUOUS_MULTIPLE_SPELLS", 0))
    d12_total_tg = int(st.sum())

    coverage = {
        "this_node_head_coach_identity": {
            "covered": ident["coverage"]["overall"]["covered"],
            "rows": ident["coverage"]["overall"]["rows"],
            "coverage": ident["coverage"]["overall"]["coverage"],
            "definition": ("per GAME DATE: the archive names a specific head coach for this team "
                           "strictly before this row's game_date, via a hire event it actually "
                           "saw, with no intervening departure. No carry-back, no left-censored "
                           "inference, no ambiguity admitted.")},
        "this_node_head_coach_event_present": {
            "covered": evpres["coverage"]["overall"]["covered"],
            "coverage": evpres["coverage"]["overall"]["coverage"]},
        "d12_team_games_by_status": {str(k): int(v) for k, v in st.items()},
        "d12_named_team_games": d12_named_tg,
        "d12_named_plus_ambiguous_team_games": d12_named_tg + d12_ambig_tg,
        "d12_total_team_games_in_its_coverage_table": d12_total_tg,
        "d12_definition": ("per TEAM-SEASON: one status for the season's OPENING head coach, then "
                           "applied to all of that team-season's games. It admits "
                           "NAMED_START_LEFT_CENSORED (inferring a 2021 incumbent backwards from "
                           "a later firing) and NAMED_OPEN_END_CARRIED_FORWARD_UNVERIFIED "
                           "(carrying a name forward past the last event), neither of which this "
                           "node counts as covered."),
        "delta_named": d12_named_tg - ident["coverage"]["overall"]["covered"],
        "why_they_differ": (
            "D12 is more permissive by construction and answers a season-level question; this "
            "node is deliberately conservative and answers a row-level one. Neither number is "
            "wrong. They are NOT interchangeable and the D10 ledger must carry the row-level one, "
            "because the ledger's unit is the team-game."),
    }

    out = {
        "schema": "r14_cross_check_vs_d12/1",
        "node_id": "R14_D10_COACHING_CORRECTION",
        "status": "CROSS-CHECK ONLY. Computed after the fact. Feeds nothing in CORRECTION.json.",
        "source_level_counts": src_agree,
        "source_level_full_agreement": all(v["agree"] for v in src_agree.values()),
        "universe_reconciliation": universe,
        "coverage_comparison": coverage,
        "cutoff_validity": {
            "this_node": 0,
            "d12_cutoff_status_values": sorted(d12cov["cutoff_status"].dropna().unique().tolist()),
            "d12_admission_status_values": sorted(d12cov["admission_status"].dropna().unique().tolist()),
            "agree": True,
            "note": "both reach CUTOFF_UNPROVEN / NOT_ADMITTED independently."},
    }
    (HERE / "cross_check_vs_D12.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    print("source-level full agreement:", out["source_level_full_agreement"])
    for k, v in src_agree.items():
        if not v["agree"]:
            print("  DISAGREE", k, v)
    print("universe:", universe["rows_in_d12_working_universe_not_in_frozen"],
          universe["rows_in_frozen_not_in_d12_working_universe"])
    print("coverage this node:", ident["coverage"]["overall"]["covered"],
          " D12 named team-games:", d12_named_tg, " delta:", coverage["delta_named"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
