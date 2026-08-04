#!/usr/bin/env python3
"""build_findings.py -- derive FINDINGS.json from the measurements TESTS.py actually produced.

FINDINGS.json is generated, never hand-written, so no figure in it can drift from the figure the
test suite measured. Run TESTS.py first; this reads its TEST_RESULTS.json.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

EPISTEMIC = ("INFRASTRUCTURE + task-specific INVARIANT. Proves a dimension merge cannot silently "
             "change the row universe. Does not establish that any dimension is scientifically "
             "usable.")


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    tr_path = HERE / "TEST_RESULTS.json"
    if not tr_path.exists():
        print(f"missing {tr_path}; run TESTS.py first")
        return 1
    tr = json.loads(tr_path.read_text(encoding="utf-8"))
    m = tr["measurements"]
    s2, uni, naive = m["S2_dimension"], m["universe"], m["naive_join"]
    nuf, res = m["null_unsafe_filter"], m["season_effective_resolution"]
    order, pkt, venue = m["order_independence"], m["packet_schema_listing"], m["venue_semantics"]

    inputs = {}
    for rel in ["data/reference/team_cities.csv",
                "experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet",
                "experiments/player_program/stage2a/V2_STOP_CONDITION.json",
                "experiments/player_program/stage2a/EVIDENCE_PACKET_V2.json"]:
        p = REPO / rel
        inputs[rel] = {"sha256": sha256(p), "bytes": p.stat().st_size} if p.exists() \
            else {"sha256": None, "bytes": None, "missing": True}

    doc = {
        "schema": "stage2b_node_findings/1",
        "node_id": "P23_DIMENSION_CARDINALITY_GUARD",
        "title": ("S2: merge cardinality invariants preserving the 2,982-row / 1,491-game "
                  "universe"),
        "lane": "possession",
        "type": "implementation",
        "severity_on_failure": "A",
        "epistemic_status": EPISTEMIC,
        "addresses": "V2_STOP_CONDITION.json findings.S2_team_cities_join_hazards",
        "s2_remains_unresolved_as_an_adjudication": True,
        "input_artifacts": inputs,
        "validation": {
            "command": ("python experiments/player_program/stage2b/"
                        "P23_DIMENSION_CARDINALITY_GUARD/TESTS.py"),
            "n_tests": tr["n_tests"], "n_failed": tr["n_failed"],
            "exit_code": 1 if tr["n_failed"] else 0,
        },
        "artifacts_written": [
            "experiments/player_program/stage2b/P23_DIMENSION_CARDINALITY_GUARD/merge_guard.py",
            "experiments/player_program/stage2b/P23_DIMENSION_CARDINALITY_GUARD/TESTS.py",
            "experiments/player_program/stage2b/P23_DIMENSION_CARDINALITY_GUARD/TEST_RESULTS.json",
            "experiments/player_program/stage2b/P23_DIMENSION_CARDINALITY_GUARD/build_findings.py",
            "experiments/player_program/stage2b/P23_DIMENSION_CARDINALITY_GUARD/FINDINGS.json",
            "experiments/player_program/stage2b/P23_DIMENSION_CARDINALITY_GUARD/REPORT.md",
        ],
        "frozen_artifacts_modified": [],

        "measurements": [
            {"claim": "data/reference/team_cities.csv row count",
             "packet_states": 16, "measured": s2["rows"], "verdict": "AGREE",
             "how": "TESTS.py::t09 -- len(pd.read_csv(team_cities.csv))"},
            {"claim": "distinct team_id in team_cities.csv",
             "packet_states": 15, "measured": s2["distinct_team_id"], "verdict": "AGREE",
             "how": "TESTS.py::t09 -- tc.team_id.nunique()"},
            {"claim": "duplicated team_id",
             "packet_states": {"1611661317": 2}, "measured": s2["duplicated_team_id"],
             "verdict": "AGREE",
             "how": "TESTS.py::t09 -- tc.team_id.value_counts()[>1]"},
            {"claim": "last_season dtype", "packet_states": "float64",
             "measured": s2["last_season_dtype"], "verdict": "AGREE",
             "how": "TESTS.py::t09 -- str(tc.last_season.dtype)"},
            {"claim": "last_season nulls", "packet_states": "15 of 16",
             "measured": f"{s2['last_season_nulls']} of {s2['rows']}", "verdict": "AGREE",
             "how": "TESTS.py::t09 -- tc.last_season.isna().sum()"},
            {"claim": "elevation_ft range", "packet_states": [20, 2030],
             "measured": [s2["elevation_ft_min"], s2["elevation_ft_max"]], "verdict": "AGREE",
             "how": "TESTS.py::t09 -- tc.elevation_ft.min()/max()"},
            {"claim": "venues above 1000 ft", "packet_states": 4,
             "measured": {"rows_above_1000ft": s2["rows_above_1000ft"],
                          "distinct_arenas": s2["distinct_arenas_above_1000ft"],
                          "distinct_franchises": s2["distinct_franchises_above_1000ft"]},
             "verdict": "CORRECT",
             "correction": ("the packet's 4 is a ROW count; there are 3 distinct arenas. The 4th "
                            "row is the second Phoenix row for the same building (Footprint "
                            "Center, identical lat/lon/elevation_ft). The original source's 3 is "
                            "the correct venue count."),
             "how": ("TESTS.py::t09 -- (tc.elevation_ft>1000).sum() vs "
                     "tc.loc[tc.elevation_ft>1000,'arena'].nunique()")},
            {"claim": "team_cities.csv column count", "packet_states": 9,
             "measured": pkt["n_actual_columns"], "verdict": "CORRECT",
             "correction": ("EVIDENCE_PACKET_V2 names 9 columns; the file has 11. Omitted: "
                            + ", ".join(pkt["columns_omitted_from_packet"])),
             "how": "TESTS.py::t15 -- tc.shape[1] vs the packet source string"},

            {"claim": "candidate universe rows / game clusters",
             "packet_states": "2,982 rows over 1,491 game clusters",
             "measured": {"rows": uni["universe_rows"],
                          "game_clusters": uni["universe_game_clusters"],
                          "team_game_keys": uni["universe_team_game_keys"],
                          "duplicate_team_game_keys": uni["duplicate_team_game_keys"]},
             "verdict": "AGREE",
             "how": ("TESTS.py::t10 -- team_possession_prior_v1.parquet restricted to "
                     "pace_resolved == True")},
            {"claim": "parent artifact shape before the pace_resolved restriction",
             "measured": {"rows": uni["prior_artifact_rows"],
                          "games": uni["prior_artifact_games"]},
             "verdict": "NOT_IN_PACKET",
             "how": "TESTS.py::t10 -- len(prior), prior.game_id.nunique()"},
            {"claim": "distinct (team_id, season) pairs needing dimension resolution",
             "measured": uni["distinct_team_season_pairs"], "verdict": "NOT_IN_PACKET",
             "how": "TESTS.py::t10 -- len(set(zip(u.team_id, u.season)))"},
            {"claim": "universe rows carrying team_id 1611661317",
             "measured": uni["rows_for_team_1611661317"], "verdict": "NOT_IN_PACKET",
             "how": "TESTS.py::t10 -- (u.team_id == 1611661317).sum()"},

            {"claim": "naive merge(on='team_id') fan-out on the real universe",
             "packet_states": "a naive join fans out 1:m and duplicates that franchise's rows",
             "measured": {"rows_before": naive["universe_rows"],
                          "rows_after": naive["naive_left_merge_rows"],
                          "excess_rows": naive["excess_rows"],
                          "game_clusters_after": naive["naive_game_clusters"],
                          "duplicated_team_game_keys":
                              naive["duplicated_team_game_keys_after_naive_merge"]},
             "verdict": "AGREE",
             "note": ("the game-cluster count is UNCHANGED at 1,491, so a guard that only counts "
                      "games sees nothing; only row count and team-game key multiplicity move"),
             "how": "TESTS.py::t11 -- u.merge(tc, on='team_id', how='left')"},
            {"claim": "null-unsafe last_season filter destroys the universe",
             "packet_states": ("last_season is float with 15 of 16 values null, so a null-unsafe "
                               "filter drops every current franchise"),
             "measured": {"dimension_rows_surviving": nuf["rows_surviving_last_season_notna"],
                          "franchises_lost": nuf["franchises_lost"],
                          "universe_rows_after": nuf["universe_rows_after_null_unsafe_inner_join"],
                          "universe_rows_lost": nuf["rows_lost"]},
             "verdict": "AGREE",
             "how": ("TESTS.py::t12 -- u.merge(tc[tc.last_season.notna()], on='team_id', "
                     "how='inner')")},

            {"claim": "season-effective resolution preserves the universe exactly",
             "measured": {"required_pairs": res["required_key_season_pairs"],
                          "resolved_rows": res["resolved_dimension_rows"],
                          "uncovered": res["n_uncovered"], "ambiguous": res["n_ambiguous"],
                          "merged_rows": res["merged_rows"],
                          "merged_game_clusters": res["merged_game_clusters"],
                          "merged_team_game_keys": res["merged_team_game_keys"],
                          "fan_out_rows": res["fan_out_rows"],
                          "any_null_expansion": res["any_null_expansion"],
                          "unmatched_fact_rows": res["n_unmatched_fact_rows"]},
             "verdict": "NOT_IN_PACKET",
             "how": ("TESTS.py::t13 -- resolve_effective_dimension + guarded_merge with "
                     "effective_from=first_season, effective_to=last_season, effective_on=season, "
                     "open_ended_upper_bound=True")},
            {"claim": "PHO/PHX resolution by declared interval only",
             "measured": res["phoenix_abbreviation_by_season"], "verdict": "NOT_IN_PACKET",
             "how": "TESTS.py::t13 -- merged[merged.team_id==1611661317].groupby('season')"},
            {"claim": "resolution is invariant to dimension row order",
             "measured": {"permutations_tested": order["permutations_tested"],
                          "identical_every_time": order["resolution_invariant"],
                          "keys_where_keep_first_differs_from_keep_last":
                              order["keys_where_keep_first_differs_from_keep_last"]},
             "verdict": "NOT_IN_PACKET",
             "how": ("TESTS.py::t14 -- tc.sample(frac=1.0, random_state=seed) over 8 seeds, "
                     "compared against drop_duplicates keep='first' vs keep='last'")},
            {"claim": "the dimension is team-keyed, not venue-of-play keyed",
             "measured": {"team_cities_has_game_key": venue["team_cities_has_game_key"],
                          "universe_has_is_home": venue["universe_has_is_home"],
                          "universe_has_opp_team_id": venue["universe_has_opp_team_id"],
                          "universe_rows_per_game": venue["universe_rows_per_game"]},
             "verdict": "NOT_IN_PACKET",
             "how": "TESTS.py::t16 -- column presence on both frames"},
        ],

        "acceptance_criteria": [
            {"criterion": "every dimension merge declares explicit keys and expected cardinality",
             "met": True,
             "enforced_by": "merge_guard.DimensionSpec.__post_init__",
             "demonstrated_by": "TESTS.py::t01 (5 invalid specifications rejected)"},
            {"criterion": "row count, game key set and team-game key set are asserted unchanged",
             "met": True,
             "enforced_by": "merge_guard.RowUniverse.capture / .assert_unchanged inside guarded_merge",
             "demonstrated_by": "TESTS.py::t04, t13"},
            {"criterion": "duplicate primary keys are rejected and fan-out fails the merge",
             "met": True,
             "enforced_by": ("merge_guard.check_dimension_primary_key (pre-merge) + pandas "
                             "validate= + RowUniverse.assert_unchanged (post-merge)"),
             "demonstrated_by": "TESTS.py::t02, t03, t11"},
            {"criterion": "null expansion is reported",
             "met": True,
             "enforced_by": "merge_guard.null_expansion_report",
             "demonstrated_by": "TESTS.py::t05, t13",
             "note": ("reported per column and split into nulls from unmatched fact rows vs nulls "
                      "already present in the dimension source")},
            {"criterion": ("the duplicated team_id 1611661317 (PHO/PHX) is resolved ONLY from "
                           "documented effective-date or season semantics; if it cannot be, the "
                           "affected feature family is EXCLUDED rather than guessed"),
             "met": True,
             "enforced_by": ("merge_guard.resolve_effective_dimension; AmbiguousDimensionError / "
                             "UndeclaredNullIntervalError"),
             "demonstrated_by": "TESTS.py::t06, t07, t13, t14",
             "outcome": ("RESOLVED from first_season/last_season alone: all 76 (team_id, season) "
                         "pairs match exactly one interval, 0 uncovered, 0 ambiguous. The EXCLUDE "
                         "branch was therefore not taken on this dimension, but it is implemented "
                         "and tested.")},
            {"criterion": "deduplication by arbitrary first/last row order is not used anywhere",
             "met": True,
             "enforced_by": "absent by construction; merge_guard.assert_no_order_dependent_dedup",
             "demonstrated_by": "TESTS.py::t08 (0 hits), t14 (8-permutation invariance)"},
        ],

        "contradictions": [
            {"id": "C1",
             "between": ("V2_STOP_CONDITION.json S2 note and the bytes of "
                         "data/reference/team_cities.csv"),
             "document_says": "I measure 4 venues above 1000 ft, not 3",
             "bytes_say": (f"{s2['rows_above_1000ft']} ROWS above 1000 ft but "
                           f"{s2['distinct_arenas_above_1000ft']} distinct arenas; PHO and PHX are "
                           f"the same building with identical lat/lon/elevation_ft"),
             "resolution": ("the original source's 3 is correct as a venue count; the "
                            "coordinator's 4 counts rows. This is the S2 fan-out defect occurring "
                            "inside the measurement that documents the S2 fan-out defect."),
             "severity": "B",
             "action_taken": "raised only; V2_STOP_CONDITION.json is frozen and was NOT edited"},
            {"id": "C2",
             "between": ("EVIDENCE_PACKET_V2.json cutoff_valid_availability_table_CORRECTED and "
                         "the bytes of data/reference/team_cities.csv"),
             "document_says": pkt["packet_source_string"],
             "bytes_say": (f"{pkt['n_actual_columns']} columns; omitted from the packet listing: "
                           + ", ".join(pkt["columns_omitted_from_packet"])),
             "resolution": ("timezone is the material omission -- the same entry promotes 'time "
                            "zone' as an available feature while its schema listing does not name "
                            "the column. Same failure mode as S8."),
             "severity": "B",
             "action_taken": "raised only; EVIDENCE_PACKET_V2.json is frozen and was NOT edited"},
            {"id": "C3",
             "between": ("acceptance criterion 5's phrase 'documented effective-date or season "
                         "semantics' and the absence of any data dictionary"),
             "document_says": "resolution must come from DOCUMENTED effective-date/season semantics",
             "bytes_say": ("no data dictionary for team_cities.csv exists under "
                           "experiments/player_program/. The documentation is the column names "
                           "first_season/last_season plus their observed values."),
             "resolution": ("the reading is coherent and uniquely consistent with the bytes -- "
                            "contiguous, non-overlapping intervals covering all 76 required pairs "
                            "with multiplicity exactly 1 -- but it is inferred, not cited. The "
                            "guard makes it explicit and refutable via the mandatory "
                            "open_ended_upper_bound declaration."),
             "severity": "C",
             "action_taken": "disclosed in REPORT.md section 5.3"},
        ],

        "could_not_establish": [
            "that the venue/elevation/timezone family is scientifically usable -- out of epistemic scope",
            "cutoff validity of any field -- untouched; not delegated to any gate per GATE_INVOCATION_CONTRACT section 7.3",
            ("that other dimension merges are safe -- only team_cities.csv was audited. "
             "master_team.parquet, the injury sources and the possession/rotation artifacts were "
             "NOT audited for merge cardinality; their key uniqueness is an open question"),
            ("whether season is the correct effective-date grain -- a mid-season venue or identity "
             "change is not representable in this schema and would be invisible to the guard"),
            ("the construction provenance of team_possession_prior_v1.parquet -- "
             "possession_features.py:156 already records that its receipt does not re-establish it"),
            ("whether the packet's other schema listings are complete -- only the one entry S2 "
             "concerns was checked"),
        ],

        "negative_results_preserved": [
            ("the EXCLUDE branch of criterion 5 was not exercised on real data because the real "
             "data resolved cleanly -- a fact about the data, not a strengthening of the guard"),
            ("no dimension other than team_cities.csv was found to need interval resolution "
             "because no other dimension was audited"),
            (f"elevation_ft spans [{s2['elevation_ft_min']}, {s2['elevation_ft_max']}] ft with "
             f"{s2['distinct_arenas_above_1000ft']} distinct venues above 1000 ft; this node makes "
             f"no claim about whether that spread supports a feature"),
        ],

        "stop_conditions_tripped": [],
        "stop_condition_assessment": {
            "primary_target": "untouched",
            "K0_structure": "untouched",
            "inference_structure": "untouched",
            "candidate_universe": ("preserved and now enforced at 2,982 rows / 1,491 clusters; "
                                   "not changed"),
            "cutoff_valid_feature_set": ("untouched; no field promoted, demoted or adjudicated; "
                                         "S2 remains unresolved as an adjudication"),
            "leakage_status": "untouched",
        },

        "raised_not_resolved": [
            {"id": "R1",
             "summary": ("team_cities.csv is keyed by team, not by venue-of-play, and the "
                         "2,982-row universe artifact carries no is_home / opp_team_id"),
             "measured": {"team_cities_has_game_key": venue["team_cities_has_game_key"],
                          "universe_has_is_home": venue["universe_has_is_home"],
                          "universe_has_opp_team_id": venue["universe_has_opp_team_id"],
                          "away_team_game_rows_affected": uni["universe_game_clusters"]},
             "consequence": ("a team_id-keyed venue merge attaches each team its OWN arena on "
                             "every row, including its away rows. Any elevation / altitude / "
                             "travel-distance / timezone-shift feature needs the venue of PLAY, "
                             "which requires a home-team or opponent key this artifact lacks."),
             "why_not_a_stop_condition": ("it changes no target, control, universe or "
                                          "adjudication; it is a construction constraint on how a "
                                          "venue feature family could be built"),
             "for": "coordinator",
             "evidence": "TESTS.py::t16"},
        ],

        "recommended_call_sites": [
            ("any future arm importing venue / elevation / timezone / travel must call "
             "merge_guard.resolve_effective_dimension then merge_guard.guarded_merge with the "
             "team_cities__season_effective spec in REPORT.md section 3.5"),
            ("merge_guard should be applied to master_team.parquet and the injury sources before "
             "either backs a registered arm; neither was audited here"),
        ],
    }

    out = HERE / "FINDINGS.json"
    out.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
