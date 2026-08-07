r"""S33R - build SPEC_V2.json from the BYTE-FROZEN S33 SPEC.json by applying the S34
dispositions.  The S33 draft is never edited; SPEC_V2 supersedes it and both remain.

ROOT: C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program
Run:  python BUILD_SPEC_V2.py
"""
import copy
import hashlib
import json
import math
import os
import sys

import pandas as pd

WORKTREE = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
S3 = os.path.join(WORKTREE, "experiments", "player_program", "stage3_score")
HERE = os.path.join(S3, "S33R_PREREGISTRATION_REPAIR")
sys.path.insert(0, HERE)
from VALIDATE import validate, cross_field, UnhandledKeyword  # noqa: E402

SPEC_PATH = os.path.join(S3, "S33_PREREGISTRATION_DRAFT", "SPEC.json")
SCHEMA_PATH = os.path.join(S3, "S32B_K0_CONTRACT", "K0_MATCHED_SCHEMA_SCORE.json")


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def canon(v):
    if isinstance(v, float):
        return "nan" if math.isnan(v) else repr(float(v))
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(int(v))
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if v is None:
        return "nan"
    return str(v)


def col_digest(series):
    return hashlib.sha256("\u001f".join(canon(v) for v in series).encode("utf-8")).hexdigest()


spec = json.load(open(SPEC_PATH, encoding="utf-8"))
schema = json.load(open(SCHEMA_PATH, encoding="utf-8"))
v2 = copy.deepcopy(spec)

MT = "data/masters/master_team.parquet"
MT_SHA = "ad79ce5cdda7e058ba24be45243037252e3795a3e9f0c18cc41b3f12f3c38528"
SB = "experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet"
SB_SHA = "5d1fc4c9af2334a6edd6ddffab91fe7cff5596578d9995937859a86cfc1e1452"
PP = "experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet"
PP_SHA = "c37c075148553920b79c9320ea03afb37986bfc752fc84dd695f154887c3db18"
TC = "data/reference/team_cities.csv"
TC_SHA = "10a544fdc52a9c80c1573437c9838b11815c9eafe6ac2cf052be17a2128ac42d"

COMPOSITE_COL_SHA = {
    "pred_home": "e754709cfc7b0779502af153b4b89e8a5d3ee3223b2e365bdc0d046e974d4525",
    "pred_away": "9178138c5f94cc4dbe981ebdc2a94d2e8d030e4b9337f9cb8c0f7d12e98adebe",
    "pred_total": "16c312aba2f964682f4d20a694b09890f4488f0e5bcdf31f827946158e145f3d",
    "pred_margin": "1d79ff3adeda3d66e26f3bda1702d36301da447d87828c474d488d793de44ff4",
    "p_home": "8a92c017e4f8606c3a7405116a455dc746493581454dc4dcbe1aab6d00b41989",
}

# ---- measure the pace-prior column pin (no pin existed for it before this node) -----
pp = pd.read_parquet(os.path.join(WORKTREE, PP.replace("/", os.sep)))
pp_sorted = pp.sort_values(["game_id", "team_id"], key=lambda s: s.astype(str))
PACE_PIN = {
    "pin_kind": "frozen_store_column_digest_extended_grain",
    "artifact_path": PP,
    "artifact_sha256": sha256_file(os.path.join(WORKTREE, PP.replace("/", os.sep))),
    "sort_rule": "lexicographic on (str(game_id), str(team_id)) ascending",
    "canonicalisation": "floats via repr(float(v)) (NaN->'nan'); ints via str(int(v)); "
                        "timestamps via .isoformat(); else str(v); joined with U+001F; "
                        "UTF-8; sha256 hexdigest",
    "join_key_columns": ["game_id", "team_id"],
    "join_key_sha256": col_digest(
        pp_sorted.game_id.astype(str) + "\u001e" + pp_sorted.team_id.astype(str)),
    "column": "projected_team_off_possessions",
    "column_sha256": col_digest(pp_sorted.projected_team_off_possessions),
    "n_values": int(len(pp_sorted)),
    "n_nan": int(pp_sorted.projected_team_off_possessions.isna().sum()),
}
assert PACE_PIN["artifact_sha256"] == PP_SHA, "pace prior artifact drifted from the S33 pin"

# =====================================================================================
# 0. header
# =====================================================================================
v2["schema"] = "stage3_score/S33R/preregistration/2"
v2["node"] = "S33R_PREREGISTRATION_REPAIR"
v2["supersedes"] = {
    "artifact": "experiments/player_program/stage3_score/S33_PREREGISTRATION_DRAFT/SPEC.json",
    "artifact_sha256": sha256_file(SPEC_PATH),
    "relationship": "SPEC_V2 SUPERSEDES the reviewed S33 draft for every registrable purpose. "
                    "The S33 draft is BYTE-FROZEN and is not edited; both files remain in the "
                    "repo so the reviewed bytes stay auditable.",
    "review_dispositioned": "S34_PREREGISTRATION_RED_TEAM (RETRY, top tier), agent_returned "
                            "2026-08-07T13:53:36Z in orchestration/GRAPH_EVENTS.jsonl: "
                            "VERDICT FAIL, 4 Severity A, 8 Severity B, 4 Severity C.",
}
v2["epistemic_status"] = (
    "REPAIR. Dispositions S34's findings against the REVIEWED draft, which stays byte-frozen "
    "and auditable. Emits SPEC_V2.json; authorizes nothing to fit.")

# =====================================================================================
# A1 - game_date cutoff promotion
# =====================================================================================
a1 = json.load(open(os.path.join(HERE, "A1_DATE_WITNESS_RECEIPT.json"), encoding="utf-8"))
tt = a1["s33_named_measurement_as_written"]
wa = a1["replacement_witness_A_shotchart_endpoint"]
wb = a1["replacement_witness_B_release_ordinal"]

v2["a1_game_date_cutoff_promotion"] = {
    "finding": "S34 A1 - the S33-named S37 promotion measurement is barred by S30 section 8's "
               "own exclusion, cannot falsify, and leaves 272 clusters unwitnessed.",
    "s33_measurement_withdrawn": {
        "witness_1": "data/reference/tip_times.csv",
        "why_inadmissible": "P2B F3 closed the chain: tip_times.csv DESCENDS FROM the "
                            "retrospective odds archive (builder data/reference/collect_bios.py"
                            "::phase_tips lines 241-291; per-season counts match exactly). It is "
                            "not merely that 406 of its 1,219 universe rows carry "
                            "source_table == 'extension' - EVERY row is archive-derived, and "
                            "S30 section 8 excludes the promotion channel for any field whose "
                            "cutoff validity rests on vendor-asserted timestamps from a "
                            "retrospective pull.",
        "measured_provenance": tt["witness_1_provenance"],
        "why_it_cannot_falsify": "tip_times.game_date is a projection of the same settled date "
                                 "field; re-derived deviations = "
                                 f"{tt['date_deviations_found']}/{tt['universe_clusters_witnessed']['n']}, "
                                 "zero BY CONSTRUCTION.",
        "coverage_hole": tt["universe_clusters_UNWITNESSED"],
        "reschedule_column_never_consulted": "n_commence_variants (36 universe games flagged)",
        "witness_2": "data/refresh_2026/gamelog_team_*.parquet",
        "witness_2_independence": "NONE - master_team.source names those files as its own "
                                  "build inputs; measured file-level hole "
                                  "gamelog_team_2024_regular_season.parquet is absent from "
                                  "refresh_2026 (its 240 clusters are supplied by "
                                  "data/wnba_team_gamelog_2024.parquet, which is equally "
                                  "upstream).",
    },
    "replacement_measurement_registered": {
        "id": "M_A1_GAME_DATE_CUTOFF_V2",
        "runs_at": "S37_IMPLEMENTATION_AUDIT, re-run byte-for-byte from "
                   "S33R_PREREGISTRATION_REPAIR/MEASURE_A1_DATE_WITNESS.py against the frozen "
                   "artifacts; this node has already run it and pins the result below, so S37 "
                   "verifies rather than discovers.",
        "independent_of_market_archive": True,
        "covers_2021": True,
        "tests_reschedule_directly": True,
        "witness_A": {
            "name": "independent NBA-Stats shotchartdetail endpoint",
            "artifacts": wa["artifacts"],
            "in_master_team_build_chain": False,
            "market_archive_derived": False,
            "coverage": wa["universe_clusters_witnessed"],
            "hole": wa["universe_clusters_UNWITNESSED"],
            "hole_game_ids": wa["unwitnessed_game_ids"],
            "measured_date_deviations_vs_master_team": wa["date_deviations_vs_master_team"],
            "games_with_internally_conflicting_dates": wa[
                "games_with_internally_conflicting_dates"],
            "scope_limit": wa["what_it_can_and_cannot_show"],
        },
        "witness_B": {
            "name": "schedule-release ordinal order test (reschedule-direct)",
            "definition": "the trailing five digits of a WNBA REGULAR-SEASON game_id are the "
                          "league's schedule-release sequence number, fixed at publication "
                          "before any game is played; a game moved to another date keeps its "
                          "number and lands out of date order. Playoff ids encode "
                          "round/series/game, not a linear counter, and are reported "
                          "separately as STRUCTURAL, never as reschedule evidence.",
            "coverage": wb["universe_clusters_witnessed"],
            "hole": wb["universe_clusters_UNWITNESSED"],
            "measured_displaced_games": wb["n_displaced_games"],
            "displaced_games": wb["displaced_games_localised"],
            "scope_limit": wb["what_it_can_and_cannot_show"],
        },
        "alarm_only_probe": {
            "source": "data/reference/tip_times.csv n_commence_variants",
            "status": "ALARM_ONLY - the barred archive may RAISE a flag, never clear one, and "
                      "never contributes to promoting the field. Using an excluded channel to "
                      "attempt falsification is not promotion through that channel; using it "
                      "to confirm would be, and is forbidden here.",
            "market_flagged": a1["cross_check_alarm_probe_only"][
                "market_flagged_n_commence_variants_gt_1"],
            "convergent_with_witness_B": a1["cross_check_alarm_probe_only"]["intersection"],
        },
        "result_this_node": {
            "cross_endpoint_date_disagreements": wa["date_deviations_vs_master_team"],
            "clusters_cross_endpoint_witnessed": wa["universe_clusters_witnessed"]["n"],
            "clusters_NOT_cross_endpoint_witnessed": wa["universe_clusters_UNWITNESSED"]["n"],
            "release_order_displacements": wb["n_displaced_games"],
            "material_displacement": {
                "game_id": "1022300038",
                "played": "2023-07-28",
                "release_order_neighbours": ["1022300037", "1022300039"],
                "days_after_its_next_ordinal_game": 51,
                "universe_games_inside_the_displacement_window": 103,
                "reading": "the textbook signature of a postponed-and-replayed fixture. The "
                           "S33-named measurement returns zero deviations and could never have "
                           "surfaced it.",
            },
            "one_day_displacements": 8,
            "three_day_displacement": "1022600183 (2026-07-20) - also the ONLY game the barred "
                                      "archive independently flags with n_commence_variants > 1",
        },
        "verdict_on_the_field": "master_team.game_date is corroborated as the AS-PLAYED date by "
                               "an endpoint outside its own build chain on 1,485 of 1,491 "
                               "clusters with ZERO disagreements, including all 205 clusters of "
                               "2021 that the S33 measurement could not reach. It is NOT "
                               "promoted to CUTOFF_VALID unconditionally: 10 clusters carry a "
                               "release-order displacement and 6 clusters (all 2026) have no "
                               "second-endpoint witness, so the field is promoted to "
                               "CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS and the exception set is "
                               "carried as a mandatory receipt.",
        "enumerated_exception_set": {
            "release_order_displaced": [m["game_id"] for m in wb["displaced_games_localised"]],
            "no_second_endpoint_witness": wa["unwitnessed_game_ids"],
            "total_exception_clusters": len(
                set(m["game_id"] for m in wb["displaced_games_localised"])
                | set(wa["unwitnessed_game_ids"])),
        },
        "binding_handling_rule": {
            "mandatory_sealed_receipt": "R-A1-EXCEPTIONS: every element's sealed run additionally "
                                        "reports its primary metric with the enumerated exception "
                                        "clusters removed, on the identical universe string for "
                                        "arm and K0. Non-gating, mandatory; its absence is a card "
                                        "defect.",
            "kill": "A1-SENSITIVITY KILL (SC06 only, the primary consumer): if removing the "
                    "enumerated exception clusters flips the sign of SC06's affected-subset "
                    "Delta, the arm dies - a rest/travel result that depends on 10 clusters "
                    "whose scheduling is in question is not a result.",
            "scope": "the exception set is slate-wide because the (game_date, game_id) "
                     "sequencing of every EWMA construction consumes the field; SC06 is the "
                     "only arm whose TREATMENT reads it directly.",
        },
        "what_remains_unestablished": "No committed artifact in this branch witnesses what the "
                                      "schedule SAID before tip. Both admissible witnesses are "
                                      "postgame records, so a postponement agreed by both "
                                      "endpoints is invisible to witness A; witness B detects it "
                                      "only when it breaks release order. A pre-tip schedule "
                                      "witness would require a point-in-time schedule capture, "
                                      "which begins prospectively and cannot cover 2021-2026.",
    },
    "arms_withdrawn_or_recarded": "None withdrawn. SC06 is RE-CARDED with the A1-SENSITIVITY "
                                  "kill and the R-A1-EXCEPTIONS receipt; every other element "
                                  "inherits the slate-wide receipt through its second-order "
                                  "EWMA-sequencing exposure.",
}

v2["leakage_receipt_obligations"]["cutoff_unproven_register"] = [
    "CUTOFF_UNPROVEN -> promoted at this node to CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS: "
    "master_team.game_date. The S33-named S37 promotion measurement is WITHDRAWN as inadmissible "
    "(it rests entirely on the P2B-barred retrospective odds archive; P2B F3 closes the chain) "
    "and is replaced by M_A1_GAME_DATE_CUTOFF_V2 - see the a1_game_date_cutoff_promotion block. "
    "The replacement is independent of the market archive, covers 2021, tests reschedule "
    "directly, was RUN at this node (0 cross-endpoint date disagreements on 1,485/1,491 "
    "clusters; 10 release-order displaced clusters enumerated; 6 clusters unwitnessed by the "
    "second endpoint), and S37 re-runs it byte-for-byte. Consumers: SC06 (rest/travel features, "
    "direct), and the (date, game_id) sequencing of every EWMA construction (second-order)."
]

# =====================================================================================
# A2 - schedule-identity set extension + column-grain lineage
# =====================================================================================
EXT_JUSTIFICATION = (
    "Frozen, hash-pinned, strictly-lagged pregame construction. It is a PREDICTION about the "
    "current game computed only from strictly earlier calendar dates - build_score_baselines.py "
    "line 286 restricts every efficiency input to prior_idx = [j for j in range(len(sub)) if "
    "dates[j] < dates[i]] (strictly earlier dates, never same-day), and the win-probability "
    "logistic is calibrated on strictly-prior SEASONS only, walk-forward, never pooled "
    "(lines 411-437). It contains no realized fact about the current game. It is admitted to "
    "the identity set because a deletion-invariance receipt that nulls it would delete the "
    "null-strength floor itself, which S30 section 4 REQUIRES every K0 to carry.")

v2["schedule_identity_set_extension_s34_adjudicated"] = {
    "authority": "S30 section 1: schedule-identity is 'a closed, enumerated set of columns - "
                 "scheduled game date, opponent/matchup identity, home/away designation, "
                 "season - extendable only by S34 adjudication'. S34 adjudicated the draft and "
                 "found the receipt UNSATISFIABLE for all 17 elements without this extension; "
                 "this block IS the registered extension and is itself reviewable.",
    "why_required": "Every one of the 17 elements consumes the CURRENT game's row of "
                    "score_baseline_rows.parquet - the null-granted composite column that S30 "
                    "section 4 obliges each K0 to carry. Those prediction columns sit outside "
                    "the S30 section-1 closed set, so the receipt as carded could never be "
                    "byte-identical. The same artifact carries actual_total, actual_margin and "
                    "y_home_win ON THE SAME ROWS (measured: score_baseline_rows.parquet columns "
                    "= game_id, pred_home, pred_away, pred_total, pred_margin, p_home, "
                    "game_date, season, actual_total, actual_margin, y_home_win, method), which "
                    "is exactly why source-grain retention proves nothing and the receipt must "
                    "run at COLUMN grain.",
    "base_closed_set_unchanged": ["scheduled game date", "opponent/matchup identity",
                                  "home/away designation", "season"],
    "extension_members": [
        {"column": c, "artifact": SB, "artifact_sha256": SB_SHA,
         "method_filter": "composite_pace_x_eff_v1",
         "column_sha256": COMPOSITE_COL_SHA[c], "n_values": 1465,
         "n_nan": 188 if c == "p_home" else 0,
         "consumed_on_the_current_game_row": True,
         "justification": EXT_JUSTIFICATION}
        for c in ("pred_home", "pred_away", "pred_total", "pred_margin", "p_home")
    ] + [
        {"column": "projected_team_off_possessions", "artifact": PP,
         "artifact_sha256": PP_SHA, "byte_pin": PACE_PIN,
         "consumed_on_the_current_game_row": True,
         "justification": "The frozen VERIFIED regulation-equivalent pace prior, which S30 "
                          "section 8 declares 'consumable as-is, frozen, declared "
                          "regulation-equivalent'. Strictly-lagged by construction (prior "
                          "window means; the artifact's own pace_source column marks the "
                          "no-prior-games rows unresolved rather than back-filling them). "
                          "Hash-pinned; the column digest above was computed at this node "
                          "because no column-level pin for it existed before."}
    ],
    "columns_explicitly_NOT_extended": {
        SB: ["actual_total", "actual_margin", "y_home_win"],
        MT: ["pts", "opp_pts", "wl", "plus_minus", "minutes", "and every other box-score "
             "column - consumable ONLY on strictly-prior rows, never on the current game's row"],
    },
    "receipt_semantics_after_extension": (
        "The current-game-deletion invariance receipt recomputes every feature matrix with the "
        "current game's rows RETAINED, the base identity columns AND the extension columns "
        "above intact, and EVERY OTHER COLUMN of EVERY consumed source nulled - including "
        "actual_total, actual_margin, y_home_win, pts and opp_pts on the current game's rows. "
        "Byte-identity of the two matrices is then a satisfiable and meaningful proof: it shows "
        "no same-game REALIZED information entered the prediction path, while allowing the "
        "frozen pregame predictions the null-strength floor requires."),
    "reviewability": "This extension is a preregistered, reviewable adjudication, not a "
                     "self-grant. If a later reviewer rejects any member, every element whose "
                     "column-grain lineage marks that member "
                     "consumed_on_the_current_game_row = true is affected, and the affected set "
                     "is mechanically readable from arms[].features_lineage.",
}

v2["leakage_receipt_obligations"]["current_game_deletion_invariance"] = (
    "COLUMN grain, per S30 section 1, WITH the S34-adjudicated identity-set extension registered "
    "in schedule_identity_set_extension_s34_adjudicated. Retained on the current game's rows: "
    "the base closed set {scheduled game date, opponent/matchup identity, home/away designation, "
    "season} PLUS the six byte-pinned frozen pregame construction columns (pred_home, pred_away, "
    "pred_total, pred_margin, p_home, projected_team_off_possessions). Nulled on the current "
    "game's rows: every other column of every consumed source, naming explicitly "
    "score_baseline_rows.actual_total / actual_margin / y_home_win and master_team.pts / "
    "opp_pts. Byte-identity of the two feature matrices is required for arm and K0 alike. The "
    "per-source COLUMN classification the receipt runs against is carried on every "
    "arms[].features_lineage[].sources[].columns entry, so S37 has a per-source classification "
    "to check rather than an artifact-grain assertion.")
v2["leakage_receipt_obligations"]["feature_lineage"] = (
    "each arm block carries its frozen feature-lineage table at CONSUMED-SOURCE-COLUMN grain: "
    "feature -> source artifact + sha256 -> each consumed column with its identity "
    "classification, whether the CURRENT game's row of that column is consumed, and the lag "
    "semantics (S34 finding A2).")

# ---- column classification helpers ---------------------------------------------------
ID = "SCHEDULE_IDENTITY_S30_SECTION_1"
EXT = "IDENTITY_SET_EXTENSION_S34_ADJUDICATED"
LAG = "LAGGED_OUTCOME_STRICTLY_PRIOR_ROWS_ONLY"
REF = "IMMUTABLE_REFERENCE_METADATA"
NEVER = "PRESENT_IN_ARTIFACT_NEVER_READ_BY_ANY_ARM"


def cols(pairs):
    return [{"column": c, "classification": k, "current_game_row_consumed": cur}
            for c, k, cur in pairs]


MT_IDENTITY = [("game_id", ID, True), ("season", ID, True), ("season_type", ID, True),
               ("game_date", ID, True), ("team_id", ID, True), ("opp_team_id", ID, True),
               ("is_home", ID, True)]
MT_SCORES = [("pts", LAG, False), ("opp_pts", LAG, False)]
MT_NEVER = [("wl", NEVER, False), ("plus_minus", NEVER, False), ("minutes", NEVER, False)]

SB_COLS_FOR = {
    "E1_GAME_TOTAL": "pred_total", "E2_FINAL_MARGIN_HOME": "pred_margin",
    "E3_HOME_WIN_PROB": "p_home",
}


def composite_source(columns_used):
    return {
        "path": SB, "sha256": SB_SHA,
        "columns": cols([("game_id", ID, True), ("method", REF, True)]
                        + [(c, EXT, True) for c in columns_used]
                        + [("actual_total", NEVER, False), ("actual_margin", NEVER, False),
                           ("y_home_win", NEVER, False)]),
    }


ARM_COMPOSITE_COLUMNS = {
    "SC01_OPP_ADJ_INTERACTING": ["pred_total", "pred_margin", "p_home"],
    "SC02_A07_SCORE_TRANSIENT": ["pred_total", "pred_margin"],
    "SC03_SEASON_CARRYOVER_PRIOR": ["pred_total", "pred_margin"],
    "SC04_HCA_LEAGUE_DRIFT": ["pred_margin"],
    "SC05_HCA_TEAM_OFFSETS": ["pred_margin"],
    "SC06_SCHED_FATIGUE_DIFF": ["pred_margin", "p_home"],
    "SC08_SIGMA_MARGIN_MAP": ["pred_margin", "p_home"],
    "SC09_FAV_GAP_COMPRESSION": ["pred_margin"],
    "SC10_FORM_TREND": ["pred_total", "pred_margin"],
    "SC11_LEAGUE_TOTAL_DRIFT": ["pred_total"],
    "SC12_ROBUST_INPUT_WINSOR": ["pred_margin"],
}
# which arms' TREATMENT features read master_team score columns at all
ARM_TREATMENT_MT = {
    "SC01_OPP_ADJ_INTERACTING": MT_IDENTITY + MT_SCORES,
    "SC02_A07_SCORE_TRANSIENT": MT_IDENTITY + [("pts", LAG, False)],
    "SC03_SEASON_CARRYOVER_PRIOR": MT_IDENTITY + MT_SCORES,
    "SC04_HCA_LEAGUE_DRIFT": MT_IDENTITY + MT_SCORES,
    "SC05_HCA_TEAM_OFFSETS": MT_IDENTITY + MT_SCORES,
    "SC06_SCHED_FATIGUE_DIFF": MT_IDENTITY,
    "SC08_SIGMA_MARGIN_MAP": MT_IDENTITY + MT_SCORES,
    "SC09_FAV_GAP_COMPRESSION": [],
    "SC10_FORM_TREND": MT_IDENTITY + MT_SCORES,
    "SC11_LEAGUE_TOTAL_DRIFT": MT_IDENTITY + MT_SCORES,
    "SC12_ROBUST_INPUT_WINSOR": MT_IDENTITY + MT_SCORES,
}

ROW_BASE = ("PINNED (S34 finding B2): every strictly-prior construction in this slate, arm and "
            "K0 alike, draws its prior rows from the 1,491-cluster / 2,982-row RESOLVED "
            "UNIVERSE - never from the 1,495-cluster full schedule. Measured consequence of the "
            "pin: 187 universe clusters have different same-season strictly-prior counts under "
            "the two bases (all 187 are 2021 games, i.e. training-only rows in every fold; zero "
            "in any test season). Carded stratum counts under the pinned base vs the full "
            "schedule: SC01 max<=12 472 vs 470, SC02 min<=5 249 vs 245, SC03 min<10 399 vs 394 "
            "- no test-season stratum count changes.")

for arm in v2["arms"]:
    aid = arm["arm_id"]
    new_lineage = []
    for entry in arm["features_lineage"]:
        if entry["feature"].startswith("composite_"):
            e = dict(entry)
            e["feature"] = ("composite_{" + "|".join(ARM_COMPOSITE_COLUMNS[aid])
                            + "} (null-granted, both sides)")
            e["sources"] = [composite_source(ARM_COMPOSITE_COLUMNS[aid])]
            e["cutoff_status"] = "CUTOFF_VALID"
            e["identity_set_status"] = ("consumed on the CURRENT game's row under the "
                                        "S34-adjudicated identity-set extension")
            new_lineage.append(e)
            continue
        e = dict(entry)
        srcs = []
        for s in entry["sources"]:
            if s["path"] == MT:
                srcs.append({"path": MT, "sha256": MT_SHA,
                             "columns": cols(ARM_TREATMENT_MT[aid] + MT_NEVER),
                             "strictly_prior_row_base": ROW_BASE})
            elif s["path"] == TC:
                srcs.append({"path": TC, "sha256": TC_SHA,
                             "columns": cols([("team_id", REF, True),
                                              ("timezone", REF, True),
                                              ("city", REF, True), ("arena", REF, True)])})
            elif s["path"] == PP:
                srcs.append({"path": PP, "sha256": PP_SHA,
                             "columns": cols([("game_id", ID, True), ("team_id", ID, True),
                                              ("game_date", ID, True), ("season", ID, True),
                                              ("projected_team_off_possessions", EXT, True)]),
                             "byte_pin": PACE_PIN})
            elif s["path"] == SB:
                srcs.append(composite_source(ARM_COMPOSITE_COLUMNS[aid]))
            else:
                srcs.append(s)
        e["sources"] = srcs
        new_lineage.append(e)
    arm["features_lineage"] = new_lineage
    arm["strictly_prior_row_base"] = ROW_BASE
    arm["p22_guard_obligation"] = ("every column listed in features_lineage[].sources[].columns "
                                   "with classification != PRESENT_IN_ARTIFACT_NEVER_READ_BY_ANY_ARM "
                                   "passes the P22 postgame_surrogate_guard invocation at S37, "
                                   "per column, with S37 first verifying the guard is fit for "
                                   "purpose on SCORE surrogates (S30 section 1).")

# =====================================================================================
# A3 - SC01 stratum pinned to ONE predicate
# =====================================================================================
a3 = json.load(open(os.path.join(HERE, "A3_B_STRATA_RECEIPT.json"), encoding="utf-8"))
S = a3["A3_strata"]["universe_1491"]
sc01 = S["SC01_max_le_12_BOTH_TEAMS_EARLY"]
v2["a3_sc01_stratum_resolution"] = {
    "finding": "S34 A3 - the carded PREDICATE says BOTH teams (max<=12) while the carded NUMBER "
               "(516) is the min reading; 9.3% apart; the kill terminates all three SC01 "
               "elements.",
    "pinned_predicate": "min(n_H, n_A) >= 0 AND max(n_H, n_A) <= 12 - i.e. BOTH teams have at "
                        "most 12 same-season strictly-prior completed games at the cutoff. "
                        "The predicate text of the S33 card is kept; the NUMBER is corrected.",
    "pinned_count_pooled": sc01["pooled"],
    "pinned_count_per_test_season": sc01["per_test_season"],
    "clusters_in_2021_training_only": sc01["in_2021_training_only"],
    "rejected_reading": {"predicate": "min(n_H, n_A) <= 12 (AT LEAST ONE team early)",
                         "count": S["SC01_min_le_12_AT_LEAST_ONE_TEAM_EARLY"]["pooled"]},
    "j12_correction": "S33 judgment call J12 asserted that 'each team <= 12 is exactly "
                      "min <= 12'. That is false: 'each/both teams <= 12' is max(n_H, n_A) <= 12. "
                      "J12 also declared the BOTH reading the intended conservative one, so the "
                      "predicate was right and the arithmetic was wrong. Corrected here.",
    "kill_checkability": "non-empty in every test season under the pinned reading "
                         f"({sc01['per_test_season']}), so the arm-killing stratum diagnostic "
                         "is checkable in all five folds.",
    "row_base": ROW_BASE,
    "other_arms_unchanged": {
        "SC02 min(n_H,n_A) <= 5": S["SC02_min_le_5"]["pooled"],
        "SC03 min(n_H,n_A) < 10": S["SC03_min_lt_10"]["pooled"],
        "note": "SC02 and SC03 card their clock as min(...) explicitly and their predicate and "
                "number agree; re-derived here and unchanged. Every stratum now states its "
                "reducer explicitly.",
    },
}

# =====================================================================================
# A4 - SC08::E3 null strength
# =====================================================================================
v2["a4_sc08_null_strength_receipt"] = {
    "finding": "S34 A4 - SC08's K0 map is per-fold train-OLS to MARGIN plus a Gaussian MLE on "
               "margin residuals; it is never fitted to the win outcome, unlike SC01/SC06 whose "
               "per-fold logistic reproduces the frozen builder's own walk-forward p_home "
               "construction. SC08::E3 was therefore eligible for the unqualified label over a "
               "null never shown to reach the public floor, and the defence lived only in the "
               "S33 report (J3), not in the binding record.",
    "route_taken": "MANDATORY SEALED RECEIPT + PREREGISTERED BELOW-FLOOR RULE (not a refit). "
                   "Refitting SC08's mean map to the win outcome would change the element's "
                   "estimation objective and its K0 structure, which S30 section 11 makes a "
                   "STOP CONDITION for this node. The receipt route leaves the K0 structure "
                   "untouched and closes the labelling hole.",
    "receipt": {
        "id": "R_SC08_FLOOR",
        "mandatory": True,
        "computation": "on the pooled out-of-fold test clusters, and per fold, compute the "
                       "Brier of (i) SC08::E3's own K0_MATCHED probability path Phi(mu_hat/"
                       "sigma0) and (ii) the frozen store's byte-pinned p_home column, on the "
                       "identical matched universe string with identical handling of the 188 "
                       "structural NaN p_home rows. Both are CONTROL objects; the challenger's "
                       "number is not part of this receipt.",
        "absence_is_a_card_defect": True,
    },
    "preregistered_below_floor_rule": (
        "If SC08::E3's K0_MATCHED does not achieve a strictly better pooled Brier than the "
        "frozen p_home column on that matched universe, the K0 is declared NOT TO HAVE REACHED "
        "THE PUBLIC FLOOR. Consequences, all automatic and registered before any fit: the "
        "element's verdict label becomes 'FEATURE VALUE OVER OWN NULL ONLY - BELOW-FLOOR NULL'; "
        "the label is inseparable from every citation of the result; the element is never "
        "counted in any unqualified pass tally; S40 routes any would-be promotion to the S42 "
        "USER gate rather than promoting it; and the element additionally reports (non-gating) "
        "its metric against the D045 floor recomputed on its exact universe."),
    "floor_bar_discipline_check": "This rule references the floor ARTIFACT COLUMN that S30 "
                                  "section 4 already obliges every K0 to carry by byte pin. It "
                                  "prints no floor or bar VALUE, and it is a LABELLING rule, "
                                  "not a kill, stopping rule, coverage predicate or grid "
                                  "choice - the four things S30 section 4 forbids from "
                                  "referencing floor values.",
    "why_sc01_and_sc06_e3_are_different": "their E3 K0s fit a per-fold logistic of the composite "
                                          "margin on train seasons < Y, which is exactly the "
                                          "frozen builder's walk-forward construction of p_home "
                                          "(build_score_baselines.py lines 411-437), so the "
                                          "control structurally reproduces the public floor. "
                                          "R_SC08_FLOOR is nevertheless registered for those two "
                                          "elements as well, as a non-gating agreement receipt.",
}

# =====================================================================================
# per-record K0 edits
# =====================================================================================
K = v2["k0_matched"]
EXT_NOTE = ("IDENTITY-SET EXTENSION (S34-adjudicated, registered in SPEC_V2 "
            "schedule_identity_set_extension_s34_adjudicated): this element consumes the CURRENT "
            "game's row of the byte-pinned frozen composite column(s) above. Those columns are "
            "admitted to the schedule-identity set as frozen, hash-pinned, strictly-lagged "
            "pregame constructions; every other column of every consumed source - naming "
            "score_baseline_rows.actual_total / actual_margin / y_home_win and master_team.pts / "
            "opp_pts - is nulled on the current game's rows in the deletion-invariance receipt.")

for eid, rec in K.items():
    rec["notes"] = list(rec.get("notes", [])) + [EXT_NOTE]
    rec["invariants"]["rows"] = rec["invariants"]["rows"] + " STRICTLY-PRIOR ROW BASE: " + ROW_BASE

# --- B1: SC06 R5 literal key closure -------------------------------------------------
for eid in ("SC06_SCHED_FATIGUE_DIFF::E2_FINAL_MARGIN_HOME",
            "SC06_SCHED_FATIGUE_DIFF::E3_HOME_WIN_PROB"):
    rec = K[eid]
    for side in ("arm_spec", "k0_spec"):
        st = rec[side]["structural_terms"]
        rec[side]["structural_terms"] = ["ERA2024" if t == "era_2024_main_effect" else t
                                         for t in st]
        dr = rec[side]["declaration_routing"]
        rec[side]["declaration_routing"] = {
            ("ERA2024" if k2 == "era_2024_main_effect" else k2): v for k2, v in dr.items()}
    rec["invariants"]["nuisance_terms"] = ["ERA2024"]
    rec["invariants"]["lower_order_structural_terms"] = ["ERA2024"]
    rec["notes"] = [n.replace(
        "R5 lower-order closure: ERA2024:fatigue_diff requires the era_2024 main effect, "
        "carried as a structural nuisance term on BOTH sides (identical routing).",
        "R5 lower-order closure, LITERAL: the treatment term is 'ERA2024:fatigue_diff' and the "
        "main effect is declared under the byte-identical key 'ERA2024' in both sides' "
        "structural_terms, declaration_routing, nuisance_terms and "
        "lower_order_structural_terms. S34 finding B1: the S33 bytes named the main effect "
        "'era_2024_main_effect', so a literal R5 key match FAILED while S33's self_validation "
        "reported PASS by matching intent instead of keys.") for n in rec["notes"]]

# --- A4 records ----------------------------------------------------------------------
K["SC08_SIGMA_MARGIN_MAP::E3_HOME_WIN_PROB"]["verdict_label_policy"] = (
    "substantive_feature arm under the canonical containment reading, CONDITIONAL on the "
    "mandatory sealed receipt R_SC08_FLOOR: eligible for the unqualified feature-value label "
    "via challenger_vs_k0 ONLY IF this element's K0_MATCHED achieves a strictly better pooled "
    "Brier than the frozen byte-pinned p_home column on the identical matched universe. If it "
    "does not, the label is 'FEATURE VALUE OVER OWN NULL ONLY - BELOW-FLOOR NULL', inseparable "
    "from every citation, excluded from every unqualified pass tally, and S40 routes any "
    "would-be promotion to the S42 USER gate. Kills evaluated uncorrected.")
K["SC08_SIGMA_MARGIN_MAP::E3_HOME_WIN_PROB"]["notes"].append(
    "R_SC08_FLOOR (MANDATORY sealed receipt, absence is a card defect): this K0's probability "
    "path is Phi(mu_hat/sigma0) with mu_hat a per-fold train-OLS map of the composite MARGIN and "
    "sigma0 a Gaussian MLE on train margin residuals - it is never fitted to the win outcome, so "
    "unlike SC01::E3 and SC06::E3 it does not structurally reproduce the frozen builder's "
    "walk-forward p_home. The receipt reports the K0's pooled and per-fold Brier against the "
    "frozen p_home column's Brier on the identical universe; the preregistered below-floor rule "
    "in SPEC_V2 a4_sc08_null_strength_receipt then governs the label. Both quantities are "
    "CONTROL objects; no challenger number enters this receipt.")
for eid in ("SC01_OPP_ADJ_INTERACTING::E3_HOME_WIN_PROB",
            "SC06_SCHED_FATIGUE_DIFF::E3_HOME_WIN_PROB"):
    K[eid]["notes"].append(
        "R_SC08_FLOOR analogue (non-gating agreement receipt): this element's K0 probability "
        "path is a per-fold logistic of the composite margin fitted on seasons < Y, which is "
        "exactly the frozen builder's own walk-forward construction of p_home "
        "(build_score_baselines.py lines 411-437); the sealed run receipts the K0-vs-frozen-"
        "p_home Brier agreement so the structural claim is checked rather than asserted.")

# --- B8: SC09 re-carded as calibration_only ------------------------------------------
r9 = K["SC09_FAV_GAP_COMPRESSION::E2_FINAL_MARGIN_HOME"]
r9["arm_kind"] = "calibration_only"
r9["verdict_label_policy"] = (
    "calibration_only arm (S34 finding B8, re-carded at S33R): the treatment term is a "
    "deterministic shape-restricted transform of the K0's OWN fitted prediction and introduces "
    "no information the null lacks. Per P26 1.5 as carried by the S32B schema, this element may "
    "NEVER be reported as feature value however large challenger_vs_k0 is; it is eligible only "
    "for a CALIBRATION-IMPROVEMENT label on E2, and any citation must say that the improvement "
    "is a re-shaping of the public floor's own prediction, not new information. Kills evaluated "
    "uncorrected; the BELOW-FLOOR path is never invoked (null-granted ingredients carried).")
CF9 = ("none (no post-fit rescaling, recentring, isotonic or affine fix-up; the null-granted "
       "composite column carries a train-fitted linear coefficient inside the single head fit, "
       "identically on both sides). DECLARED EXPLICITLY (S34 finding B8): 'none' describes the "
       "POST-FIT machine dimension only. This element's treatment term is a monotone hinge of "
       "the K0's own within-head fitted prediction, so the arm IS a shape-restricted "
       "recalibration of the null's prediction in the scientific sense; that is why the record "
       "is carded arm_kind = calibration_only and can never claim feature value. The dimension "
       "string is byte-identical on both sides; the K0 simply has no hinge term.")
r9["arm_spec"]["comparison_gate_sidespec"]["calibration_freedom"] = CF9
r9["k0_spec"]["comparison_gate_sidespec"]["calibration_freedom"] = CF9
r9["notes"].append(
    "S34 finding B8 disposition: calibration_freedom = 'none' was accurate for the machine "
    "dimension but the record's arm_kind (substantive_feature) contradicted the treatment, "
    "which is a hinge on g_hat = the K0's own fitted prediction. Re-carded calibration_only. "
    "Consequence recorded before any fit: SC09 can no longer be reported as feature value even "
    "if it passes the gate.")

# --- B3: SC12 inertness kill --------------------------------------------------------
b3 = a3["B3_sc12_clip_incidence"]
b3b = a3["B3b_realised_transform_bite"]
r12 = K["SC12_ROBUST_INPUT_WINSOR::E2_FINAL_MARGIN_HOME"]
r12["notes"] = [
    "S34 finding B3 disposition: the S33 inertness kill ('< 8% of prior-game inputs clipped at "
    f"the frozen cap') CANNOT FIRE. Measured on the pinned row base: {b3['rows_exceeding_cap']} "
    f"of {b3['team_game_rows_in_universe']} team-game margin observations exceed the +/-15 cap "
    f"= {round(b3['share'] * 100, 2)}%, and the LOWEST per-season share is "
    f"{round(b3['minimum_per_season_share'] * 100, 2)}% (2024) - the 8% floor is unreachable "
    "from above. The S33 card's justification ('so the floor is live, not vacuous') reads the "
    "same measurement backwards: 26% incidence proves the floor VACUOUS, not live.",
    "REPLACEMENT (registered before any fit): the incidence table survives as a MANDATORY "
    "NON-GATING receipt, and the kill moves onto the statistic that actually carries the "
    "mechanism's bite - |w_H - w_A|, the realised winsorised-minus-raw EWMA correction "
    f"differential. Measured pre-registration distribution over the 1,491 clusters: median "
    f"{b3b['median']}, p75 3.0684, p90 {b3b['p90']}, max {b3b['max']} points; "
    f"{b3b['share_below_0_25_points'] * 100:.2f}% of clusters sit below 0.25 points.",
    "the transform-incidence table (count and share of clipped prior-game inputs per fold) "
    "remains a receipted sealed output, now NON-GATING.",
    EXT_NOTE,
]

# --- B4: SC10 orthogonalisation covariate lineage ------------------------------------
b45 = json.load(open(os.path.join(HERE, "B4_B5_SUPPORT_RECEIPT.json"), encoding="utf-8"))
b4 = b45["B4_sc10_orthogonalisation_covariate_support"]
ORTHO_NOTE = (
    "S34 finding B4 disposition: the orthogonalisation covariate is now a first-class lineage "
    "entry on the SC10 arm block (feature 'trailing_opponent_strength_diff') with its source "
    "artifact and sha256, its consumed columns and their identity classification, its lag "
    "semantics, its support floor and fallback, and an explicit per-column P22 obligation. "
    f"Measured support on the pinned row base: both sides have >= 4 same-season strictly-prior "
    f"games on {b4['clusters_with_both_sides_ge_4_same_season_prior_games']['pooled']} of 1,491 "
    f"clusters ({b4['clusters_with_both_sides_ge_4_same_season_prior_games']['share'] * 100:.2f}%); "
    f"the remaining {b4['clusters_taking_the_zero_spread_fallback']['pooled']} take the declared "
    "zero-spread fallback, identically on both sides. The covariate enters ONLY the declared "
    "kill-bearing orthogonalised variant, never the primary head, and requires no source the "
    "slate does not already consume.")
for eid in ("SC10_FORM_TREND::E1_GAME_TOTAL", "SC10_FORM_TREND::E2_FINAL_MARGIN_HOME"):
    K[eid]["notes"].append(ORTHO_NOTE)

# --- B5: SC02 retirement threshold ---------------------------------------------------
b5 = b45["B5_sc02_design_condition_numbers"]
B5_NOTE = (
    "S34 finding B5 disposition - the retirement kill now carries a NUMERIC threshold: a fold is "
    "UNEVALUABLE when kappa_2, the 2-norm condition number of that fold's TRAINING design matrix "
    "[intercept, standardised null-granted column, standardised treatment term], is >= 1000. "
    "kappa_2 >= 1000 is a pinned convention, not a value read off the data, and no floor or bar "
    "value informs it. Pre-registration feasibility measurement on the pinned row base (no "
    "target and no metric enters a condition number): per-fold maxima "
    f"{b5['per_fold']}, overall max {b5['max_observed']} - far below the threshold, so the kill "
    "is a live guard against an implementation that actually degenerates rather than a "
    "pre-satisfied formality. Failure in >= 2 folds retires the arm UNEVALUATED (cycle-1 "
    "retirement rule); the per-fold kappa_2 table is a mandatory sealed receipt.")
for eid in ("SC02_A07_SCORE_TRANSIENT::E1_GAME_TOTAL",
            "SC02_A07_SCORE_TRANSIENT::E2_FINAL_MARGIN_HOME"):
    K[eid]["notes"].append(B5_NOTE)

# --- B7: SC05 disputed assignment on its own record ----------------------------------
K["SC05_HCA_TEAM_OFFSETS::E2_FINAL_MARGIN_HOME"]["notes"].append(
    "S34 finding B7 disposition - DISPUTED FAMILY ASSIGNMENT, registered on this element's own "
    "record: primary partition places SC05 in FAM_S2_HOME_COURT with SC04 (2 elements); the "
    "registered alternative partition merges SC04 with SC11 into FAM_S2_LAGGED_LEAGUE_DRIFT and "
    "leaves SC05 ALONE (1 element). This element must survive family-Holm under BOTH readings "
    "and the stricter result governs. The S33 draft carried the dispute only in the multiplicity "
    "block, so the card itself did not disclose it.")

# --- B6: SC10 <-> SC12 dispute carried -----------------------------------------------
B6_NOTE = (
    "S34 finding B6 disposition - the SC10 <-> SC12 family dispute is now CARRIED as registered "
    "partition D (FAM_S2_LAGGED_OWN_FORM = {SC10_FORM_TREND, SC12_ROBUST_INPUT_WINSOR}, 3 "
    "elements). Both mechanisms are level-free contrasts of an EWMA over each side's own "
    "strictly-prior settled results, differenced across sides, added to the same null-granted "
    "composite head - at least as close a kinship as the SC04 <-> SC11 lagged-league-drift merge "
    "the S33 draft already carried. Partition D is a MERGE, so it raises no family count; it "
    "makes Holm STRICTER for these three elements, which must survive under every registered "
    "partition they appear in.")
for eid in ("SC10_FORM_TREND::E1_GAME_TOTAL", "SC10_FORM_TREND::E2_FINAL_MARGIN_HOME",
            "SC12_ROBUST_INPUT_WINSOR::E2_FINAL_MARGIN_HOME"):
    K[eid]["notes"].append(B6_NOTE)

# --- A3 on the SC01 records ----------------------------------------------------------
for eid in ("SC01_OPP_ADJ_INTERACTING::E2_FINAL_MARGIN_HOME",
            "SC01_OPP_ADJ_INTERACTING::E3_HOME_WIN_PROB",
            "SC01_OPP_ADJ_INTERACTING::E1_GAME_TOTAL"):
    K[eid]["notes"].append(
        "S34 finding A3 disposition - the arm-killing early-season stratum is pinned to ONE "
        f"predicate: BOTH teams at most 12 same-season strictly-prior completed games, "
        f"max(n_H, n_A) <= 12, measured {sc01['pooled']} pooled clusters "
        f"({sc01['per_test_season']} per test season, plus "
        f"{sc01['in_2021_training_only']} in 2021 which is never a test season). The S33 card's "
        "number (516) was the min reading (AT LEAST ONE team early) and contradicted its own "
        "predicate text; J12's reconciliation was false. Non-empty in every fold, so the kill is "
        "checkable.")

# --- A1 on the SC06 records ----------------------------------------------------------
A1_NOTE = (
    "S34 finding A1 disposition - this arm is the direct consumer of master_team.game_date. The "
    "S33-named S37 promotion measurement is WITHDRAWN as inadmissible (it rests entirely on the "
    "P2B-barred retrospective odds archive) and replaced by M_A1_GAME_DATE_CUTOFF_V2, which was "
    "RUN at S33R: an endpoint outside master_team's build chain corroborates the played date on "
    "1,485 of 1,491 clusters (including all 205 of 2021) with ZERO disagreements, and a "
    "schedule-release-ordinal test covering all 1,491 clusters localises 10 displaced games, one "
    "of them material (1022300038, played 51 days out of release order, 103 universe games "
    "inside the window). BINDING: the enumerated exception set is a mandatory sealed sensitivity "
    "receipt (R-A1-EXCEPTIONS) for every element, and for THIS arm an A1-SENSITIVITY KILL fires "
    "if removing those clusters flips the sign of the affected-subset Delta.")
for eid in ("SC06_SCHED_FATIGUE_DIFF::E2_FINAL_MARGIN_HOME",
            "SC06_SCHED_FATIGUE_DIFF::E3_HOME_WIN_PROB"):
    K[eid]["notes"].append(A1_NOTE)

# =====================================================================================
# arm-block edits (kills, families, strata)
# =====================================================================================
arms = {a["arm_id"]: a for a in v2["arms"]}

# A3 -> SC01
arms["SC01_OPP_ADJ_INTERACTING"]["expected_failure_mode"] = (
    "ratings and the null-granted composite converge by mid-season; the increment lives in the "
    f"first ~10-12 games per season (pinned stratum: {sc01['pooled']} pooled clusters with "
    "max(n_H, n_A) <= 12 - BOTH sides early). Cycle-1 caveat carried honestly: A26 showed "
    "SOS-adjustment null ON PACE; opponent adjustment for EFFICIENCY is untested and is exactly "
    "this arm's question.")
arms["SC01_OPP_ADJ_INTERACTING"]["kill_conditions"][0]["kill"] = (
    "early-season stratum failure: Delta-MAE(E2) vs K0 <= 0 in the early stratum, pinned to ONE "
    f"predicate - BOTH teams at most 12 same-season strictly-prior completed games "
    f"(max(n_H, n_A) <= 12; measured stratum {sc01['pooled']} pooled / "
    f"{'/'.join(str(sc01['per_test_season'][s]) for s in sorted(sc01['per_test_season']))} per "
    "test season) - the mechanism's only theorized locus of large gain failing kills the arm "
    "regardless of pooled noise")

# A1 -> SC06
arms["SC06_SCHED_FATIGUE_DIFF"]["kill_conditions"].append({
    "kill": "A1-SENSITIVITY: removing the enumerated game_date exception clusters (10 "
            "release-order displaced + 6 without a second-endpoint witness, listed in "
            "a1_game_date_cutoff_promotion.enumerated_exception_set) flips the SIGN of the "
            "affected-subset Delta - a rest/travel result that depends on clusters whose "
            "scheduling is in question is not a result",
    "receipted_diagnostic": "R-A1-EXCEPTIONS: sealed exception-removed Delta table on the "
                            "identical universe string for arm and K0",
    "scope": "kills the arm",
})
for e in arms["SC06_SCHED_FATIGUE_DIFF"]["features_lineage"]:
    if e["feature"].startswith("fatigue_diff"):
        e["cutoff_status"] = (
            "CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS (promoted at S33R by "
            "M_A1_GAME_DATE_CUTOFF_V2; see a1_game_date_cutoff_promotion). Exceptions: the 10 "
            "release-order displaced clusters and the 6 clusters with no second-endpoint "
            "witness, all enumerated; both are carried as the mandatory R-A1-EXCEPTIONS receipt "
            "and, for this arm, the A1-SENSITIVITY kill.")

# B3 -> SC12 kills
k12 = arms["SC12_ROBUST_INPUT_WINSOR"]["kill_conditions"]
k12[0] = {
    "kill": "BITE-CONCENTRATION KILL (replaces the S33 incidence kill, which S34 finding B3 "
            "showed cannot fire): pooled Delta-MAE(E2) <= 0 on the high-bite subset "
            "|w_H - w_A| >= 2.0 points, where w = EWMA(clip(margin, +/-15)) - EWMA(margin). "
            "Measured habitat on the pinned row base: 652 pooled clusters (43.7%), per test "
            "season 97/118/102/141/107 and 87 in 2021 - non-empty in every fold. The arm claims "
            "its gain exactly where the correction is large; no improvement there means the "
            "pooled number is not this mechanism.",
    "receipted_diagnostic": "sealed high-bite subset Delta-MAE table with game-clustered CIs "
                            "plus the realised |w_H - w_A| distribution",
    "scope": "kills the element",
}
k12.insert(1, {
    "kill": "IMPLEMENTATION-INTEGRITY inertness kill (not a scientific kill): p90 of "
            "|w_H - w_A| over pooled test clusters < 1.0 point means the built transform is not "
            "the registered one. Pre-registration measurement on the frozen construction: "
            f"median {b3b['median']}, p90 {b3b['p90']}, max {b3b['max']} - so a p90 below 1.0 "
            "can only mean a build defect.",
    "receipted_diagnostic": "sealed |w_H - w_A| quantile receipt per fold",
    "scope": "kills the element",
})
arms["SC12_ROBUST_INPUT_WINSOR"]["s34_b3_correction"] = (
    "The S33 inertness kill and its justification are RETIRED. Measured: "
    f"{b3['rows_exceeding_cap']}/{b3['team_game_rows_in_universe']} team-game margin "
    f"observations exceed the +/-15 cap ({round(b3['share'] * 100, 2)}%), minimum per-season "
    f"share {round(b3['minimum_per_season_share'] * 100, 2)}%. A '< 8% clipped' kill is "
    "unreachable, and the S33 justification stated the inference backwards.")
arms["SC12_ROBUST_INPUT_WINSOR"]["family_disputed"] = (
    "dual-partition with SC09 (blowout discount); ADDITIONALLY partition D "
    "FAM_S2_LAGGED_OWN_FORM = {SC10, SC12} (S34 finding B6, carried at S33R); stricter governs "
    "across every registered partition")

# B4 -> SC10 lineage entry + family dispute
arms["SC10_FORM_TREND"]["features_lineage"].insert(1, {
    "feature": "trailing_opponent_strength_diff (orthogonalisation covariate, declared "
               "kill-bearing sealed variant only - never in the primary head)",
    "construction": "mean strictly-prior season-to-date net rating of the opponents faced in "
                    "each side's last-4-game window, minus the same mean over all that side's "
                    "season opponents to date; differenced across sides; train-fitted projection "
                    "used to residualise the spread block in the declared orthogonalised variant",
    "sources": [{"path": MT, "sha256": MT_SHA,
                 "columns": cols(MT_IDENTITY + MT_SCORES + MT_NEVER),
                 "strictly_prior_row_base": ROW_BASE}],
    "lag_semantics": "same-season strictly-prior settled games only; opponent identity and "
                     "home/away read as as-of-cutoff schedule identity; no current-game row of "
                     "any score column is consumed",
    "cutoff_status": "CUTOFF_VALID",
    "support_floor_and_fallback": "both sides need >= 4 same-season strictly-prior games "
                                  f"(measured: satisfied on "
                                  f"{b4['clusters_with_both_sides_ge_4_same_season_prior_games']['pooled']}"
                                  f" of 1,491 clusters; the remaining "
                                  f"{b4['clusters_taking_the_zero_spread_fallback']['pooled']} "
                                  "take covariate = 0, identically on both sides)",
    "p22_guard_obligation": "per-column P22 postgame_surrogate_guard invocation at S37, exactly "
                            "as for the primary features (S34 finding B4)",
})
arms["SC10_FORM_TREND"]["kill_conditions"][1]["kill"] = (
    "schedule confounding: pooled Delta <= 0 once the spread block is orthogonalized against the "
    "trailing-opponent-strength differential (declared sealed variant; the covariate is "
    "registered with full lineage, byte-pinned source, support floor and per-column P22 "
    "obligation in this arm's features_lineage - S34 finding B4)")
arms["SC10_FORM_TREND"]["family_disputed"] = (
    "partition D FAM_S2_LAGGED_OWN_FORM = {SC10, SC12} (S34 finding B6, carried at S33R) vs the "
    "primary FAM_S2_FORM_DYNAMICS assignment; the element must survive Holm under both; stricter "
    "governs")

# B5 -> SC02 kill threshold
for kc in arms["SC02_A07_SCORE_TRANSIENT"]["kill_conditions"]:
    if kc["kill"].startswith("unevaluable"):
        kc["kill"] = (
            "unevaluable against null-granted columns: kappa_2 (2-norm condition number of the "
            "fold's TRAINING design matrix [intercept, standardised null-granted column, "
            "standardised treatment term]) >= 1000 marks the fold UNEVALUABLE; failure in >= 2 "
            "folds retires the arm UNEVALUATED (cycle-1 retirement rule). The threshold is a "
            "pinned convention informed by no floor or bar value; pre-registration measurement "
            f"gives per-fold maxima {b5['max_observed']} overall, far below it (S34 finding B5).")
        kc["receipted_diagnostic"] = ("sealed per-fold kappa_2 table for both estimand designs, "
                                      "arm and K0")

# B7 -> SC05 card
arms["SC05_HCA_TEAM_OFFSETS"]["family_disputed"] = (
    "dual-partition (S34 finding B7, registered on the card at S33R): partition A "
    "FAM_S2_HOME_COURT = {SC04, SC05}; partition B merges SC04 with SC11 into "
    "FAM_S2_LAGGED_LEAGUE_DRIFT and leaves {SC05} ALONE; the element must survive Holm under "
    "both and the stricter result governs")

# =====================================================================================
# multiplicity: register partition D, restate the alpha arithmetic
# =====================================================================================
m = v2["multiplicity"]
for f in m["families"]:
    if f["family_id"] == "FAM_S2_FORM_DYNAMICS":
        f["disputed"] = ("partition D: FAM_S2_LAGGED_OWN_FORM = {SC10, SC12} (3 elements), "
                         "carried at S33R per S34 finding B6; stricter governs")
    if f["family_id"] == "FAM_S2_BLOWOUT_DISCOUNT":
        f["disputed"] = ("partition A: one family {SC09, SC12}; partition B: each alone; "
                         "partition D: SC12 joins SC10 in FAM_S2_LAGGED_OWN_FORM (S34 finding "
                         "B6); stricter governs across every registered partition")
    if f["family_id"] == "FAM_S2_HOME_COURT":
        f["disputed"] = ("partition A: {SC04, SC05}; partition B: {SC04, SC11} in "
                         "FAM_S2_LAGGED_LEAGUE_DRIFT + {SC05} alone; both readings are now also "
                         "registered on SC05's own card (S34 finding B7); stricter governs")
m["registered_partitions"] = {
    "primary": "8 families: OPP_INTERACTION{SC01} / EARLY_SEASON{SC02,SC03} / "
               "HOME_COURT{SC04,SC05} / SCHEDULE_FATIGUE{SC06} / DISPERSION{SC08} / "
               "BLOWOUT_DISCOUNT{SC09,SC12} / FORM_DYNAMICS{SC10} / LEVEL_DRIFT{SC11}",
    "B_splits": "EARLY_SEASON splits into 2 and BLOWOUT_DISCOUNT splits into 2 -> 10 families "
                "(the maximal count over all registered partitions)",
    "C_merge_sc04_sc11": "SC04 and SC11 merge into FAM_S2_LAGGED_LEAGUE_DRIFT; a merge never "
                         "raises the family count",
    "D_merge_sc10_sc12": "NEW at S33R (S34 finding B6): FAM_S2_LAGGED_OWN_FORM = {SC10, SC12}, "
                         "3 elements; a merge never raises the family count, and it makes Holm "
                         "strictly harder for those three elements",
    "alpha_arithmetic_after_D": "the additive program bound uses the MAXIMUM family count over "
                                "registered partitions. That maximum is still 10 (partition B), "
                                "because D is a merge. The bound is therefore unchanged: "
                                "8 x 0.05 = 0.40 primary, 10 x 0.05 = 0.50 maximal.",
}
m["disputed_partitions_rule"] = (
    "every disputed assignment runs under EVERY registered partition in which it appears "
    "(A, B, C, D); the element must survive family-Holm under all of them; the stricter result "
    "governs (frozen strengthening, S30 section 4).")

# =====================================================================================
# stop conditions / judgment-call corrections / C notes
# =====================================================================================
v2["s33r_judgment_call_corrections"] = {
    "J12_stratum_clocks": "CORRECTED. 'each team <= 12' is max(n_H, n_A) <= 12, not min. SC01's "
                          "stratum is pinned to the max reading with its own measured count "
                          f"({sc01['pooled']}).",
    "J3_e3_k0_probability_path": "PARTIALLY UPHELD. The reading is correct for SC01::E3 and "
                                 "SC06::E3, whose per-fold logistic reproduces the frozen "
                                 "builder's walk-forward p_home. It does NOT hold for SC08::E3, "
                                 "whose map is never fitted to the win outcome; that gap is "
                                 "closed by R_SC08_FLOOR and the below-floor rule, and the "
                                 "justification now lives in the binding records rather than in "
                                 "the report.",
    "J11_rows_digest_deferred_to_S36": "UPHELD WITH A STRENGTHENING. invariants.rows still "
                                       "carries the TO_BE_EMITTED_AT_S36_BUILD contract, but it "
                                       "now also pins the strictly-prior ROW BASE explicitly "
                                       "(S34 finding B2), so the deferred digest is the only "
                                       "thing outstanding.",
    "J6_sc12_clip": "UPHELD as a choice, but its kill is replaced: see s34_b3_correction on the "
                    "SC12 arm block.",
}
v2["s34_severity_c_notes"] = {
    "status": "NOT RECOVERABLE FROM THE PROGRAM RECORD - stated plainly rather than invented.",
    "why": "S34 wrote no artifact directory; the only surviving text is the agent_returned event "
           "in orchestration/GRAPH_EVENTS.jsonl (ts 2026-08-07T13:53:36Z), which enumerates the "
           "four Severity A findings and gives counts only for B and C. The eight Severity B "
           "findings reached this node through its own acceptance criteria; the four Severity C "
           "notes did not, and no other file in the repo carries them.",
    "what_was_done_instead": "The four items the S33 draft itself escalated to S34 for review "
                             "are dispositioned here, clearly labelled as a RECONSTRUCTION and "
                             "not as quotations of the C notes.",
    "reconstructed_items": [
        {"item": "S33 J3 asked S34 to review the E3 K0 probability-path reading explicitly.",
         "disposition": "ANSWERED - see a4_sc08_null_strength_receipt and "
                        "s33r_judgment_call_corrections.J3."},
        {"item": "S33 J11 asked S34 to confirm the deferred invariants.rows digest or demand a "
                 "pre-build digest of the game_id set.",
         "disposition": "ACCEPTED WITH REASON - the deferral stands because no feature matrix "
                        "exists before S36, but the row BASE is now pinned in invariants.rows "
                        "and the universe is already pinned by count, per-season census and the "
                        "measured identity with the frozen store's league_average_v1 id set. A "
                        "pre-build game_id-set digest remains available to S35 at zero cost and "
                        "is recommended."},
        {"item": "The pooled-floor denominator reading (S32B section 5.5) remains unresolved.",
         "disposition": "ACCEPTED WITH REASON - measured moot for this slate (100% retention "
                        "under both readings, re-derived at this node); every element continues "
                        "to report both denominators and the stricter governs. The reading "
                        "itself stays flagged for any future boundary card."},
        {"item": "pipeline_id is asserted, not demonstrated (the frozen gate's documented open "
                 "gap).",
         "disposition": "ACCEPTED WITH REASON - this is a property of the frozen "
                        "comparison_gate, which this node may not modify. Recorded as an "
                        "inherited limitation, not repaired here."},
    ],
    "recommendation_to_the_verifier": "if the S34 reviewer's Severity C text can be recovered "
                                      "from its session transcript, re-run this section against "
                                      "the real notes before S35 freezes.",
}
v2["stop_condition"] = (
    "per S30 section 11. NOTHING in this repair changes the cycle-2 estimands (E1/E2/E3), the K0 "
    "structure, the inference structure, the declared universe, or the leakage status. Two items "
    "touch the boundary and are recorded rather than smuggled: (1) the CUTOFF-VALID FEATURE SET "
    "does change - master_team.game_date moves from CUTOFF_UNPROVEN to "
    "CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS on the strength of a measurement this node ran, and "
    "the schedule-identity column set is EXTENDED by the S34-adjudicated extension. Both are "
    "changes S30 explicitly provides for at this stage (section 8's promotion path, section 1's "
    "'extendable only by S34 adjudication'), both are recorded as reviewable registrations "
    "rather than assertions, and both are the specific repairs the node was created to make. "
    "(2) The A4 repair deliberately took the receipt route rather than refitting SC08's mean map "
    "to the win outcome, precisely because the refit WOULD change the element's estimation "
    "objective and K0 structure and would therefore have been a stop condition. The one item "
    "raised-not-resolved from S32B (the pooled-floor denominator reading) stays measured-moot "
    "and flagged.")

# =====================================================================================
# self-validation, actually run
# =====================================================================================
def run_validation(records):
    res, nfail = {}, 0
    for eid, rec in records.items():
        serr = validate(rec, schema, schema, f"record[{eid}]")
        cerr = cross_field(rec)
        res[eid] = {"schema_validation": "PASS" if not serr else "FAIL",
                    "cross_field_checks": "PASS" if not cerr else "FAIL"}
        if serr:
            res[eid]["schema_errors"] = serr
        if cerr:
            res[eid]["cross_field_errors"] = cerr
        if serr or cerr:
            nfail += 1
    return res, nfail


try:
    v1_res, v1_fail = run_validation(spec["k0_matched"])
except UnhandledKeyword as e:
    print("validator refused:", e)
    raise
v2_res, v2_fail = run_validation(v2["k0_matched"])

# N-checks that are specific to this repair
n_checks = {}
n_checks["N1_every_element_notes_the_identity_extension"] = all(
    any(n.startswith("IDENTITY-SET EXTENSION") for n in r["notes"])
    for r in v2["k0_matched"].values())
n_checks["N2_every_lineage_source_has_column_grain"] = all(
    all("columns" in s for e in a["features_lineage"] for s in e["sources"])
    for a in v2["arms"])
n_checks["N3_every_lineage_column_has_a_classification"] = all(
    all("classification" in c and "current_game_row_consumed" in c
        for e in a["features_lineage"] for s in e["sources"] for c in s["columns"])
    for a in v2["arms"])
n_checks["N4_every_kill_has_a_receipted_diagnostic"] = all(
    all(k.get("receipted_diagnostic") for k in a["kill_conditions"]) for a in v2["arms"])
n_checks["N5_every_arm_declares_the_strictly_prior_row_base"] = all(
    "strictly_prior_row_base" in a for a in v2["arms"])
n_checks["N6_no_floor_or_bar_numeral_appears"] = not any(
    tok in json.dumps(v2) for tok in ("9.70", "13.74", "0.202"))
n_checks["N7_element_count"] = len(v2["k0_matched"]) == 17
n_checks["N8_arm_count"] = len(v2["arms"]) == 11

v2["self_validation"] = {
    "validator": "S33R_PREREGISTRATION_REPAIR/VALIDATE.py - a subset JSON Schema 2020-12 "
                 "validator that RAISES UnhandledKeyword on any keyword it does not implement "
                 "(the S33 validator silently ignored unknown keywords), plus the S32B "
                 "cross-field rules R1-R5 and R11 with R5 matched LITERALLY BY KEY, the P26 1.5 "
                 "tested_parameters rule, and full 17-dimension Layer-A sidespec byte-identity.",
    "schema_sha256": sha256_file(SCHEMA_PATH),
    "results": v2_res,
    "n_elements": len(v2_res),
    "n_failed": v2_fail,
    "repair_specific_checks": n_checks,
    "same_validator_run_against_the_frozen_S33_bytes": {
        "purpose": "demonstrates S34 finding B1 mechanically rather than asserting it",
        "n_failed": v1_fail,
        "failures": {k: v for k, v in v1_res.items() if "cross_field_errors" in v
                     or "schema_errors" in v},
    },
    "limits_stated": [
        "No conformant third-party JSON Schema 2020-12 processor is importable in this "
        "environment (jsonschema absent - the same gap S32B, P26 and S33 recorded). This "
        "validator is stricter than S33's in that it refuses unknown keywords instead of "
        "ignoring them, but it is still not a certified processor; hand the records to one when "
        "available.",
        "R6 (truth-before-visibility), R7 (no CANNOT_HOST element exists in this slate), R8 "
        "(moot at 100% retention), R9 (an S36-time check) and R10 (validator recomputation of "
        "every byte pin from the artifact) remain audit-time rules assigned to S36/S37. R10 was "
        "discharged HERE for the one pin this node created (projected_team_off_possessions, "
        "computed from the parquet); the five composite column pins were re-verified by S34 "
        "against the parquet and are carried unchanged.",
        "pipeline_id remains asserted-not-demonstrated (the frozen gate's documented open gap).",
    ],
}
v2["counts"]["families_registered_partitions"] = 4
v2["prohibitions_honoured"] = (
    "No fit performed; no performance number computed or read; nothing under stage2b/"
    "SEALED_RESULTS or stage3_score/SEALED_RESULTS was read, listed or globbed; no frozen "
    "artifact modified and the reviewed S33 draft was NOT edited; git not run; all writes inside "
    "experiments/player_program/stage3_score/S33R_PREREGISTRATION_REPAIR/. Every measurement in "
    "this file was run against the PROGRAM WORKTREE "
    "(.claude/worktrees/player-model-program), whose data/masters/master_team.parquet matches "
    "the S33 pin ad79ce5c...8528; the main working tree's copy has drifted to e8e35b53... and is "
    "inadmissible. This node does not mark its own work accepted.")

OUT = os.path.join(HERE, "SPEC_V2.json")
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(v2, f, indent=1)

print(json.dumps({"spec_v2_bytes": os.path.getsize(OUT),
                  "elements": len(v2["k0_matched"]),
                  "arms": len(v2["arms"]),
                  "v2_failed": v2_fail,
                  "v1_failed_under_same_validator": v1_fail,
                  "repair_checks": n_checks,
                  "v1_failures": {k: v.get("cross_field_errors")
                                  for k, v in v1_res.items() if "cross_field_errors" in v},
                  "v2_failures": {k: v for k, v in v2_res.items()
                                  if v["schema_validation"] != "PASS"
                                  or v["cross_field_checks"] != "PASS"}}, indent=1))
