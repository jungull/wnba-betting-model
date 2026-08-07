r"""S35_FREEZE_TASK_CARDS - independent verification that the S33R repair reproduces.

ROOT (the only admissible root, stated explicitly):
  C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program

Nothing here fits, reads a performance number, or touches any SEALED_RESULTS path.
Writes exactly one file: VERIFICATION.json, alongside this script.

Every claim S33R/S34 makes that this node relies on is RE-RUN here, not trusted:
  V1  input byte pins in SPEC_V2.inputs_verified_sha256 re-hashed from disk
  V2  VALIDATE.py (S33R's own validator) re-run over all 17 SPEC_V2 K0 records
  V3  the same validator re-run over the FROZEN S33 draft bytes (B1, mechanical)
  V4  A3 stratum pin (max<=12 -> 472) re-derived from master_team.parquet
  V5  A2 identity-set extension: six members, every column digest recomputed
  V6  A4 R_SC08_FLOOR present in the BINDING records, not only in prose
  V7  B1 ERA2024 literal key present on both SC06 records, all four field groups
  V8  N1/N2/N3/N5/N7/N8 repair-specific checks re-derived independently
  V9  C2 power arithmetic re-derived from SC06's own carded habitat numbers
  V10 supersedes pin: the frozen S33 draft's sha256
  V11 registry pre-append baseline (read-only; no append performed here)
"""
import hashlib
import json
import os
import sys

import pandas as pd

WORKTREE = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
PP = os.path.join(WORKTREE, "experiments", "player_program")
S3 = os.path.join(PP, "stage3_score")
S33R = os.path.join(S3, "S33R_PREREGISTRATION_REPAIR")
HERE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, S33R)
from VALIDATE import validate, cross_field, UnhandledKeyword  # noqa: E402

SPEC_V2_PATH = os.path.join(S33R, "SPEC_V2.json")
S33_SPEC_PATH = os.path.join(S3, "S33_PREREGISTRATION_DRAFT", "SPEC.json")
SCHEMA_PATH = os.path.join(S3, "S32B_K0_CONTRACT", "K0_MATCHED_SCHEMA_SCORE.json")
REGISTRY_PATH = os.path.join(PP, "arm_registry.jsonl")


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def canon(v):
    """S32B column-digest canonicalisation, transcribed from S32B/MEASURE.py."""
    import numpy as np
    if v is None:
        return "None"
    if isinstance(v, (float, np.floating)):
        return repr(float(v))
    if isinstance(v, (bool, np.bool_)):
        return str(bool(v))
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def column_digest(series):
    vals = [canon(v) for v in series.tolist()]
    return {"sha256": hashlib.sha256("\x1f".join(vals).encode("utf-8")).hexdigest(),
            "n_values": len(vals), "n_nan": int(pd.isna(series).sum())}


R = {"node": "S35_FREEZE_TASK_CARDS", "root": WORKTREE,
     "purpose": "independent reproduction of the S33R repair claims before freezing",
     "checks": {}}
spec2 = json.load(open(SPEC_V2_PATH, encoding="utf-8"))
R["spec_v2_sha256"] = sha256_file(SPEC_V2_PATH)

# ---------------------------------------------------------------- V1 input pins
v1 = {"claim": "SPEC_V2.inputs_verified_sha256 re-hashed from the program worktree",
      "results": {}, "mismatches": [], "absent": []}
for rel, pin in spec2["inputs_verified_sha256"].items():
    p = os.path.join(WORKTREE, rel.replace("/", os.sep))
    if not os.path.exists(p):
        v1["absent"].append(rel)
        v1["results"][rel] = {"pinned": pin, "measured": None, "match": None}
        continue
    m = sha256_file(p)
    v1["results"][rel] = {"pinned": pin, "measured": m, "match": m == pin}
    if m != pin:
        v1["mismatches"].append(rel)
v1["verdict"] = "PASS" if not v1["mismatches"] and not v1["absent"] else "REVIEW"
R["checks"]["V1_input_byte_pins"] = v1

# ------------------------------------------------- V2 validator over SPEC_V2 records
schema = json.load(open(SCHEMA_PATH, encoding="utf-8"))
v2 = {"claim": "self_validation.results = 17/17 PASS schema + cross-field",
      "validator": "S33R_PREREGISTRATION_REPAIR/VALIDATE.py (imported, not re-implemented)",
      "schema_sha256_measured": sha256_file(SCHEMA_PATH),
      "schema_sha256_declared": spec2["self_validation"]["schema_sha256"],
      "results": {}, "n_failed": 0}
for eid, rec in spec2["k0_matched"].items():
    try:
        serr = validate(rec, schema, schema, f"record[{eid}]")
    except UnhandledKeyword as e:
        serr = [f"UnhandledKeyword: {e}"]
    cerr = cross_field(rec)
    v2["results"][eid] = {"schema_validation": "PASS" if not serr else "FAIL",
                          "cross_field_checks": "PASS" if not cerr else "FAIL"}
    if serr:
        v2["results"][eid]["schema_errors"] = serr
    if cerr:
        v2["results"][eid]["cross_field_errors"] = cerr
    if serr or cerr:
        v2["n_failed"] += 1
v2["n_elements"] = len(v2["results"])
v2["matches_declared_self_validation"] = (
    v2["results"] == {k: {kk: vv for kk, vv in val.items()}
                      for k, val in spec2["self_validation"]["results"].items()})
v2["verdict"] = "PASS" if (v2["n_failed"] == 0 and v2["n_elements"] == 17
                           and v2["schema_sha256_measured"] == v2["schema_sha256_declared"]
                           ) else "FAIL"
R["checks"]["V2_validator_over_SPEC_V2"] = v2

# ------------------------------- V3 same validator over the FROZEN S33 draft (B1)
s33 = json.load(open(S33_SPEC_PATH, encoding="utf-8"))
v3 = {"claim": "the same validator fails the frozen S33 bytes on EXACTLY the two SC06 "
               "records, on literal R5 (S34 finding B1 made mechanical)",
      "s33_spec_sha256": sha256_file(S33_SPEC_PATH), "failures": {}}
s33_records = s33.get("k0_matched", {})
for eid, rec in s33_records.items():
    try:
        serr = validate(rec, schema, schema, f"record[{eid}]")
    except UnhandledKeyword as e:
        serr = [f"UnhandledKeyword: {e}"]
    cerr = cross_field(rec)
    if serr or cerr:
        v3["failures"][eid] = {"schema_validation": "PASS" if not serr else "FAIL",
                               "cross_field_checks": "PASS" if not cerr else "FAIL",
                               "schema_errors": serr, "cross_field_errors": cerr}
v3["n_records_in_s33"] = len(s33_records)
v3["n_failed"] = len(v3["failures"])
v3["failed_ids"] = sorted(v3["failures"])
v3["all_failures_are_R5_on_SC06"] = (
    v3["n_failed"] == 2
    and all(e.startswith("SC06_SCHED_FATIGUE_DIFF::") for e in v3["failures"])
    and all(any(x.startswith("R5:") for x in f["cross_field_errors"])
            for f in v3["failures"].values()))
v3["verdict"] = "PASS" if v3["all_failures_are_R5_on_SC06"] else "FAIL"
R["checks"]["V3_validator_over_frozen_S33"] = v3

# ------------------------------------------------------------ V4 A3 stratum re-derivation
mt_path = os.path.join(WORKTREE, "data", "masters", "master_team.parquet")
mt = pd.read_parquet(mt_path)
home = mt[mt.is_home == 1]
first_date = home[home.season == 2021].game_date.min()
uni_ids = set(home[home.game_date > first_date].game_id)

by_game = {}
for gid, grp in mt[mt.game_id.isin(uni_ids)].groupby("game_id"):
    h = grp[grp.is_home == 1].iloc[0]
    a = grp[grp.is_home != 1].iloc[0]
    by_game[gid] = (h.team_id, a.team_id, int(h.season))

base = mt[mt.game_id.isin(uni_ids)][["game_id", "team_id", "season", "game_date"]].copy()
base = base.sort_values(["team_id", "game_date", "game_id"])
n_prior = {}
for tid, grp in base.groupby("team_id"):
    seen = {}
    for _, r in grp.iterrows():
        n_prior[(tid, r.game_id)] = seen.get(r.season, 0)
        seen[r.season] = seen.get(r.season, 0) + 1

TEST_SEASONS = [2022, 2023, 2024, 2025, 2026]


def stratum_census(reducer, thresh, strict=False):
    hits = []
    for g in uni_ids:
        th, ta, _s = by_game[g]
        val = reducer(n_prior[(th, g)], n_prior[(ta, g)])
        if (val < thresh) if strict else (val <= thresh):
            hits.append(g)
    return {"pooled": len(hits),
            "per_test_season": {str(s): sum(1 for g in hits if by_game[g][2] == s)
                                for s in TEST_SEASONS},
            "in_2021_training_only": sum(1 for g in hits if by_game[g][2] == 2021)}


a3 = spec2["a3_sc01_stratum_resolution"]
m_max12 = stratum_census(max, 12)
m_min12 = stratum_census(min, 12)
m_sc02 = stratum_census(min, 5)
m_sc03 = stratum_census(min, 10, strict=True)
v4 = {"claim": "A3 pin: SC01 stratum predicate is max(n_H,n_A)<=12 with pooled count 472, "
               "per test season 75/76/74/81/92, 74 in 2021; rejected min<=12 reading = 516; "
               "SC02 min<=5 = 249; SC03 min<10 = 399",
      "row_base": "the pinned 1,491-cluster resolved universe (S34 finding B2)",
      "universe_clusters_measured": len(uni_ids),
      "team_game_rows_measured": int(mt[mt.game_id.isin(uni_ids)].shape[0]),
      "measured": {"SC01_max_le_12": m_max12, "SC01_min_le_12": m_min12,
                   "SC02_min_le_5": m_sc02, "SC03_min_lt_10": m_sc03},
      "declared": {"SC01_max_le_12_pooled": a3["pinned_count_pooled"],
                   "SC01_max_le_12_per_test_season": a3["pinned_count_per_test_season"],
                   "SC01_2021_training_only": a3["clusters_in_2021_training_only"],
                   "SC01_min_le_12_pooled": a3["rejected_reading"]["count"],
                   "SC02_min_le_5": a3["other_arms_unchanged"]["SC02 min(n_H,n_A) <= 5"],
                   "SC03_min_lt_10": a3["other_arms_unchanged"]["SC03 min(n_H,n_A) < 10"]}}
v4["agreements"] = {
    "universe_1491": len(uni_ids) == spec2["shared_universe"]["game_clusters"] == 1491,
    "rows_2982": v4["team_game_rows_measured"] == spec2["shared_universe"]["team_game_rows"] == 2982,
    "sc01_max12_pooled": m_max12["pooled"] == a3["pinned_count_pooled"] == 472,
    "sc01_max12_per_test_season": (
        m_max12["per_test_season"] == {k: int(v) for k, v in
                                       a3["pinned_count_per_test_season"].items()}),
    "sc01_max12_2021": m_max12["in_2021_training_only"] == a3["clusters_in_2021_training_only"],
    "sc01_min12_rejected_count": m_min12["pooled"] == a3["rejected_reading"]["count"] == 516,
    "sc02": m_sc02["pooled"] == a3["other_arms_unchanged"]["SC02 min(n_H,n_A) <= 5"],
    "sc03": m_sc03["pooled"] == a3["other_arms_unchanged"]["SC03 min(n_H,n_A) < 10"],
    "kill_checkable_every_fold": all(c > 0 for c in m_max12["per_test_season"].values()),
    "predicate_text_is_the_max_reading": "max(n_H, n_A) <= 12" in a3["pinned_predicate"]}
v4["verdict"] = "PASS" if all(v4["agreements"].values()) else "FAIL"
R["checks"]["V4_A3_stratum_pin"] = v4

# --------------------------------------------- V5 A2 identity-set extension + column pins
ext = spec2["schedule_identity_set_extension_s34_adjudicated"]
members = ext["extension_members"]
v5 = {"claim": "the S34-adjudicated identity-set extension is registered with SIX members, "
               "each byte-pinned at column grain; every digest recomputed here from the "
               "pinned artifacts",
      "n_members": len(members),
      "member_columns": [m["column"] for m in members],
      "recomputed": {}, "mismatches": []}

sbr_path = os.path.join(WORKTREE, "experiments", "market_program", "SCORE_BASELINES",
                        "score_baseline_rows.parquet")
sbr = pd.read_parquet(sbr_path)
comp = sbr[sbr["method"] == "composite_pace_x_eff_v1"]
if pd.api.types.is_integer_dtype(comp["game_id"]):
    comp = comp.sort_values("game_id", kind="mergesort")
    sort_rule = "int64 ascending"
else:
    comp = comp.assign(_k=comp["game_id"].astype(str)).sort_values(
        "_k", kind="mergesort").drop(columns=["_k"])
    sort_rule = "lexicographic on str(game_id) ascending"
v5["composite_sort_rule_used"] = sort_rule
v5["composite_rows"] = int(len(comp))

pos_path = os.path.join(WORKTREE, "experiments", "player_program", "projected_exposure_v1",
                        "team_possession_prior_v1.parquet")
pos = pd.read_parquet(pos_path)
pos = pos.assign(_g=pos["game_id"].astype(str), _t=pos["team_id"].astype(str))
pos = pos.sort_values(["_g", "_t"], kind="mergesort").drop(columns=["_g", "_t"])

for m in members:
    col = m["column"]
    pin = m.get("column_sha256") or m.get("byte_pin", {}).get("column_sha256")
    if col == "projected_team_off_possessions":
        got = column_digest(pos[col])
        declared_n = m["byte_pin"]["n_values"]
        declared_nan = m["byte_pin"]["n_nan"]
    else:
        got = column_digest(comp[col])
        declared_n = m["n_values"]
        declared_nan = m["n_nan"]
    ok = (got["sha256"] == pin and got["n_values"] == declared_n
          and got["n_nan"] == declared_nan)
    v5["recomputed"][col] = {"pinned_sha256": pin, "measured_sha256": got["sha256"],
                             "pinned_n_values": declared_n, "measured_n_values": got["n_values"],
                             "pinned_n_nan": declared_nan, "measured_n_nan": got["n_nan"],
                             "match": ok}
    if not ok:
        v5["mismatches"].append(col)

# the join-key digest the possession pin also carries
bp = [m for m in members if m["column"] == "projected_team_off_possessions"][0]["byte_pin"]
jk_vals = []
for g, t in zip(pos["game_id"].tolist(), pos["team_id"].tolist()):
    jk_vals.append(canon(g))
    jk_vals.append(canon(t))
jk = hashlib.sha256("\x1f".join(jk_vals).encode("utf-8")).hexdigest()
v5["join_key_digest"] = {"pinned": bp["join_key_sha256"], "measured_under_interleaved_reading": jk,
                         "match": jk == bp["join_key_sha256"],
                         "note": "the pin states join_key_columns [game_id, team_id] but not the "
                                 "inter-column separator convention; a mismatch here is a "
                                 "documentation gap in the pin's own rule, not evidence the "
                                 "column digest is wrong"}
v5["not_extended_named"] = ext["columns_explicitly_NOT_extended"]
v5["six_members_expected"] = ["pred_home", "pred_away", "pred_total", "pred_margin", "p_home",
                              "projected_team_off_possessions"]
v5["member_set_correct"] = sorted(v5["member_columns"]) == sorted(v5["six_members_expected"])
v5["verdict"] = "PASS" if (v5["n_members"] == 6 and v5["member_set_correct"]
                           and not v5["mismatches"]) else "FAIL"
R["checks"]["V5_A2_identity_set_extension"] = v5

# -------------------------------------------------- V6 A4 R_SC08_FLOOR in binding records
v6 = {"claim": "R_SC08_FLOOR is registered in the BINDING per-element records, not only in "
               "the a4_ prose block",
      "in_a4_block": spec2["a4_sc08_null_strength_receipt"]["receipt"]["id"],
      "elements_carrying_the_receipt_id": [],
      "sc08_e3_fields_carrying_it": []}
for eid, rec in spec2["k0_matched"].items():
    blob = json.dumps(rec)
    if "R_SC08_FLOOR" in blob:
        v6["elements_carrying_the_receipt_id"].append(eid)
        if eid == "SC08_SIGMA_MARGIN_MAP::E3_HOME_WIN_PROB":
            for f in ("verdict_label_policy", "notes", "null_strength_floor",
                      "estimation_objective"):
                if "R_SC08_FLOOR" in json.dumps(rec.get(f)):
                    v6["sc08_e3_fields_carrying_it"].append(f)
v6["sc08_e3_present"] = "SC08_SIGMA_MARGIN_MAP::E3_HOME_WIN_PROB" in \
    v6["elements_carrying_the_receipt_id"]
v6["also_on_sc01_e3_and_sc06_e3"] = all(
    e in v6["elements_carrying_the_receipt_id"]
    for e in ("SC01_OPP_ADJ_INTERACTING::E3_HOME_WIN_PROB",
              "SC06_SCHED_FATIGUE_DIFF::E3_HOME_WIN_PROB"))
v6["below_floor_label_string_present_on_sc08_e3"] = "BELOW-FLOOR" in json.dumps(
    spec2["k0_matched"]["SC08_SIGMA_MARGIN_MAP::E3_HOME_WIN_PROB"])
v6["mandatory_flag"] = spec2["a4_sc08_null_strength_receipt"]["receipt"]["mandatory"]
v6["verdict"] = "PASS" if (v6["sc08_e3_present"] and v6["mandatory_flag"]
                           and v6["below_floor_label_string_present_on_sc08_e3"]) else "FAIL"
R["checks"]["V6_A4_R_SC08_FLOOR_binding"] = v6

# ------------------------------------------------------ V7 B1 ERA2024 literal key on SC06
v7 = {"claim": "the R5 repair renames the era main effect to the byte-identical key 'ERA2024' "
               "in BOTH sides' structural_terms, declaration_routing, nuisance_terms and "
               "lower_order_structural_terms, on BOTH SC06 records",
      "per_record": {}}
for eid in ("SC06_SCHED_FATIGUE_DIFF::E2_FINAL_MARGIN_HOME",
            "SC06_SCHED_FATIGUE_DIFF::E3_HOME_WIN_PROB"):
    rec = spec2["k0_matched"][eid]
    d = {}
    for side in ("arm_spec", "k0_spec"):
        s = rec[side]
        d[side] = {
            "structural_terms": s.get("structural_terms"),
            "ERA2024_in_structural_terms": "ERA2024" in s.get("structural_terms", []),
            "ERA2024_in_declaration_routing": "ERA2024" in s.get("declaration_routing", {}),
            "old_key_absent": "era_2024_main_effect" not in json.dumps(s),
        }
    inv = rec.get("invariants", {})
    d["invariants_lower_order_structural_terms"] = inv.get("lower_order_structural_terms")
    d["ERA2024_in_lower_order"] = "ERA2024" in (inv.get("lower_order_structural_terms") or [])
    d["nuisance_terms_mentions_ERA2024"] = "ERA2024" in json.dumps(
        rec.get("estimation_objective", {}).get("nuisance_terms", "")) or \
        "ERA2024" in json.dumps(inv.get("nuisance_terms", ""))
    d["treatment_terms"] = rec["treatment_mechanism"]["treatment_terms"]
    d["r5_passes_now"] = not [e for e in cross_field(rec) if e.startswith("R5:")]
    # The retired key must be gone from every BINDING field. It legitimately survives in the
    # notes prose, which cites S34 finding B1 by name; that citation is provenance, not a term.
    binding = {k: v for k, v in rec.items() if k != "notes"}
    d["old_key_absent_from_every_binding_field"] = "era_2024_main_effect" not in json.dumps(binding)
    d["old_key_occurrences_in_notes"] = sum(
        1 for n in rec.get("notes", []) if "era_2024_main_effect" in n)
    d["notes_occurrence_is_a_B1_history_citation"] = all(
        "S34 finding B1" in n for n in rec.get("notes", []) if "era_2024_main_effect" in n)
    v7["per_record"][eid] = d
v7["scoping_note"] = ("'old key absent' is scored over the BINDING fields only. The string "
                      "'era_2024_main_effect' does appear once in each record's notes[0], "
                      "inside the sentence that cites S34 finding B1 by name. That is the "
                      "repair documenting itself and is required, not a leftover.")
v7["verdict"] = "PASS" if all(
    r["arm_spec"]["ERA2024_in_structural_terms"] and r["k0_spec"]["ERA2024_in_structural_terms"]
    and r["arm_spec"]["ERA2024_in_declaration_routing"]
    and r["k0_spec"]["ERA2024_in_declaration_routing"]
    and r["ERA2024_in_lower_order"] and r["r5_passes_now"]
    and r["old_key_absent_from_every_binding_field"]
    and r["notes_occurrence_is_a_B1_history_citation"]
    for r in v7["per_record"].values()) else "FAIL"
R["checks"]["V7_B1_R5_fix_on_both_SC06_records"] = v7

# ------------------------------------------- V8 repair-specific checks re-derived here
arms = spec2["arms"]
n1 = all("IDENTITY-SET EXTENSION" in json.dumps(rec.get("notes"))
         for rec in spec2["k0_matched"].values())
n2 = n3 = True
missing_class = []
for a in arms:
    for fl in a.get("features_lineage", []):
        for src in fl.get("sources", []):
            if "columns" not in src or not isinstance(src["columns"], list) or not src["columns"]:
                n2 = False
            for c in src.get("columns", []):
                if "classification" not in c or "current_game_row_consumed" not in c:
                    n3 = False
                    missing_class.append((a["arm_id"], src.get("path"), c.get("column")))
n4_missing = [(a["arm_id"], k.get("kill")) for a in arms for k in a.get("kill_conditions", [])
              if not k.get("receipted_diagnostic")]
n5_missing = [a["arm_id"] for a in arms
              if not (a.get("strictly_prior_row_base")
                      or any("strictly_prior_row_base" in s
                             for fl in a.get("features_lineage", [])
                             for s in fl.get("sources", [])))]
v8 = {"claim": "SPEC_V2.self_validation.repair_specific_checks N1-N8 all true",
      "declared": spec2["self_validation"]["repair_specific_checks"],
      "re_derived": {
          "N1_every_element_notes_the_identity_extension": n1,
          "N2_every_lineage_source_has_column_grain": n2,
          "N3_every_lineage_column_has_a_classification": n3,
          "N4_every_kill_has_a_receipted_diagnostic": not n4_missing,
          "N5_every_arm_declares_the_strictly_prior_row_base": not n5_missing,
          "N7_element_count": len(spec2["k0_matched"]) == 17 == spec2["counts"]["elements"],
          "N8_arm_count": len(arms) == 11 == spec2["counts"]["arms_retained"]},
      "N3_missing": missing_class, "N4_missing": n4_missing, "N5_missing": n5_missing,
      "N6_note": "N6 (no D043 bar numeral appears) is NOT re-derivable at this node without "
                 "reading the bar values themselves, which S30 section 4 forbids this author "
                 "from quoting. Carried as S33R's own check, re-checkable only by a node "
                 "already holding the values."}
v8["verdict"] = "PASS" if all(v8["re_derived"].values()) else "FAIL"
R["checks"]["V8_repair_specific_checks"] = v8

# ---------------------------------------------------- V9 C2 power arithmetic from the card
sc06 = [a for a in arms if a["arm_id"] == "SC06_SCHED_FATIGUE_DIFF"][0]
sc06_e2_notes = " ".join(spec2["k0_matched"]["SC06_SCHED_FATIGUE_DIFF::E2_FINAL_MARGIN_HOME"]
                         ["notes"])
import re as _re
mm = _re.search(r"(\d+) pooled clusters with \|F_H - F_A\| >= 1 \(([\d/]+) per test season; "
                r"(\d+) pre-2024 vs (\d+) in 2024\+", sc06_e2_notes)
v9 = {"claim": "S34 C2: SC06's era-instability kill rests on ~17 pooled-TEST clusters of "
               "pre-2024 support, i.e. it is essentially unpowered",
      "carded_text_found": bool(mm)}
if mm:
    pooled = int(mm.group(1))
    per_season = [int(x) for x in mm.group(2).split("/")]
    pre24_pooled, post24_pooled = int(mm.group(3)), int(mm.group(4))
    test_total = sum(per_season)
    pre24_test = per_season[0] + per_season[1]      # 2022 + 2023
    v9.update({"pooled_clusters_at_abs_F_diff_ge_1": pooled,
               "per_test_season_2022_to_2026": per_season,
               "pooled_test_total": test_total,
               "pre_2024_TEST_clusters": pre24_test,
               "pre_2024_pooled_incl_2021_training": pre24_pooled,
               "post_2024_pooled": post24_pooled,
               "arithmetic_closes_pooled": pre24_pooled + post24_pooled == pooled,
               "arithmetic_closes_test": test_total == pooled - (pre24_pooled - pre24_test),
               "c2_figure_reproduces": pre24_test == 17 and test_total == 77})
    v9["verdict"] = "PASS" if v9["c2_figure_reproduces"] else "FAIL"
else:
    v9["verdict"] = "FAIL"
v9["era_kill_present"] = any("era instability" in (k.get("kill") or "")
                             for k in sc06["kill_conditions"])
v9["power_statement_already_attached_in_SPEC_V2"] = "unpowered" in json.dumps(sc06).lower()
R["checks"]["V9_C2_era_kill_power"] = v9

# ------------------------------------------------------------------ V10 supersedes pin
v10 = {"claim": "SPEC_V2.supersedes.artifact_sha256 is the frozen S33 draft's sha256",
       "declared": spec2["supersedes"]["artifact_sha256"],
       "measured": v3["s33_spec_sha256"]}
v10["verdict"] = "PASS" if v10["declared"] == v10["measured"] else "FAIL"
R["checks"]["V10_supersedes_pin"] = v10

# ------------------------------------------- V11 registry pre-append baseline (read-only)
raw = open(REGISTRY_PATH, "rb").read()
lines = raw.split(b"\n")
trailing_ok = raw.endswith(b"\n") and lines[-1] == b""
recs = lines[:-1] if trailing_ok else lines
per = []
bad = []
for i, ln in enumerate(recs):
    body = ln[:-1] if ln.endswith(b"\r") else ln
    entry = {"index": i, "bytes_incl_eol": len(ln) + 1,
             "eol": "CRLF" if ln.endswith(b"\r") else "LF",
             "sha256_of_line_without_eol": hashlib.sha256(body).hexdigest()}
    try:
        o = json.loads(body.decode("utf-8"))
        entry["schema"] = o.get("schema")
        entry["kind"] = o.get("kind")
        entry["experiment_id"] = o.get("experiment_id")
        entry["parses"] = True
    except Exception as e:
        entry["parses"] = False
        entry["error"] = str(e)
        bad.append(i)
    per.append(entry)
v11 = {"claim": "every existing registry record read and hashed BEFORE any append",
       "path": "experiments/player_program/arm_registry.jsonl",
       "file_sha256_pre_append": hashlib.sha256(raw).hexdigest(),
       "file_bytes_pre_append": len(raw),
       "n_records": len(per), "all_parse": not bad, "unparseable": bad,
       "file_ends_with_newline": trailing_ok,
       "eol_mix": {"LF": sum(1 for e in per if e["eol"] == "LF"),
                   "CRLF": sum(1 for e in per if e["eol"] == "CRLF")},
       "records": per}
v11["verdict"] = "PASS" if (v11["all_parse"] and v11["file_ends_with_newline"]) else "REVIEW"
R["checks"]["V11_registry_pre_append_baseline"] = v11

R["summary"] = {k: v["verdict"] for k, v in R["checks"].items()}
R["all_pass"] = all(v == "PASS" for v in R["summary"].values())

with open(os.path.join(HERE, "VERIFICATION.json"), "w", encoding="utf-8") as f:
    json.dump(R, f, indent=1)
print(json.dumps(R["summary"], indent=1))
print("all_pass:", R["all_pass"])
for k, v in R["checks"].items():
    if v["verdict"] != "PASS":
        print("---", k)
        print(json.dumps({kk: vv for kk, vv in v.items() if kk != "records"}, indent=1)[:4000])
