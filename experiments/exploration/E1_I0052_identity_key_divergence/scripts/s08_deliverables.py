"""E1_I0052 s08 -- KEY_CENSUS.csv, BLAST_RADIUS.csv, FINDINGS.json.

Ranks every screen in the research lane by (rows changed) x (live verdict), and establishes
cheaply how many screens are untouched.
"""
import os, sys, json, re
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ik_base as B

HERE = os.path.dirname(B.OUT)
ops = pd.read_csv(os.path.join(B.OUT, "_s01_ops.csv"))
cls = pd.read_csv(os.path.join(B.OUT, "_s05_frame_classes.csv"))
guard = pd.read_csv(os.path.join(B.OUT, "_s07_frame_divergence_guarded.csv"))
s04 = json.load(open(os.path.join(B.OUT, "_s04.json")))


def screen_of(path):
    parts = str(path).split("/")
    if len(parts) >= 2:
        return parts[0] + "/" + parts[1]
    return parts[0]


ops["screen"] = ops["file"].map(screen_of)
cls["screen"] = cls["path"].map(screen_of)

# ------------------------------------------------------------------ KEY_CENSUS
B.banner("KEY_CENSUS.csv")
STRUCT = ["JOIN", "GROUPBY", "DEDUP", "SETINDEX", "PIVOT", "LOOKUP", "MEMBERSHIP", "UNIQUE"]
kc = ops[ops.op.isin(STRUCT)].copy()

# measured divergence, attached to the sites where it was measured
MEASURED = {
    ("exploration/E0_I0006_usage_redistribution/analyze_clean.py", 20): (0, "NONE",
        "690 vs 690 baseline rows; high-usage pool 200 vs 200; anchor 200 reproduced EXACT"),
    ("exploration/E0_I0006_usage_redistribution/analyze_clean.py", 87): (0, "NONE",
        "4,983 vs 4,983 teammate rows; anchor 4,983 reproduced EXACT"),
    ("exploration/E0_I0006_usage_redistribution/analyze_clean.py", 92): (0, "NONE",
        "inner join; 578 vs 578 events, top1_share mean identical to 1e-15"),
    ("exploration/E0_I0006_usage_redistribution/build_redistribution.py", 29): (0, "VOID_ARM",
        "E0_I0006/NOTES.md declares this script VOID (contaminated source, 'must not be cited'); "
        "superseded by analyze_clean.py, which measures 0"),
    ("exploration/E0_I0006_usage_redistribution/build_redistribution.py", 74): (0, "VOID_ARM",
        "VOID per E0_I0006/NOTES.md"),
    ("exploration/E0_I0006_usage_redistribution/build_redistribution.py", 80): (0, "VOID_ARM",
        "VOID per E0_I0006/NOTES.md"),
    ("exploration/E0_I0006_usage_redistribution/placebo_check.py", 50): (0, "VOID_ARM",
        "VOID per E0_I0006/NOTES.md"),
    ("exploration/E0_I0006_usage_redistribution/placebo_check.py", 56): (0, "VOID_ARM",
        "VOID per E0_I0006/NOTES.md"),
    ("exploration/E1_I0045_roster_currency/scripts/s04_coverage_and_exposure.py", 88): (0, "NONE",
        "10 name-groups == 10 id-groups; removal set holds ONE spelling per identity "
        "(exhaustive: head(20) does not bind on 10 groups)"),
}


ADJUDICATED = {
    "exploration/E1_I0048_shipped_roster_path": (
        0, "BY DESIGN: the name key IS this screen's treatment arm. Its published divergence "
           "(196/1940 windows) is the measurement, not a defect in it. Reproduced EXACT here "
           "(A9-A12).", 0),
    "player_program/ops_lane": (
        0, "BY DESIGN: O14 fix_entity_resolution.py holds the PRE-REPAIR reproduction arm; "
           "repro_entity_resolution.py measures the name-binding failure it replaced. The "
           "shipped module keys on player_id (entity_resolution.py:238).", 0),
    "exploration/MEASURE_F1_m13_fitpool": (
        0, "MEASURED s09: dedup on [game_id,player_name,book,line] vs [game_id,player_id,"
           "book,line] gives 11,167 vs 11,167 survivors on the identical resolved row set. "
           "The fit pool itself is assembled on (game_id, player_id) with validate='one_to_one'.",
        0),
    "player_program/future_research": (
        14, "MEASURED s09/s10/s11: F16/props carry NO player_id at source, so the name is the "
            "only available key. 62 of 11,229 priced rows (0.55%) fail normalized-exact "
            "resolution -- all one person, Cheyenne Parker / Cheyenne Parker-Tyus (204323) -- "
            "and are EXCLUDED. Upper bound <=14 fit-pool rows of 1,740 (0.80%). DIRECTION = DROP.",
        2),
}


def stable_id_available(row):
    """Was a stable id available AT THAT POINT? Answered from the frame the op runs on."""
    if row["class"] == "PLAYER_ID_KEYED":
        return "YES_AND_USED"
    if row["class"] in ("PLAYER_NAME_KEYED", "MIXED"):
        return "YES"          # every player-level frame in the lane carries player_id (s05)
    return "NOT_APPLICABLE"


SCREEN_ADJ = {
    "exploration/E1_I0048_shipped_roster_path": (
        0, "BY_DESIGN", "the name key is this screen's treatment arm; its published divergence "
                        "(196/1940 windows, 10.10%) reproduced EXACT here as anchors A9-A12"),
    "player_program/ops_lane": (
        0, "BY_DESIGN", "O14 pre-repair reproduction arm; the shipped module keys on player_id "
                        "(entity_resolution.py:238)"),
    "exploration/MEASURE_F1_m13_fitpool": (
        0, "NONE", "s09: 11,167 vs 11,167 survivors on the identical resolved row set"),
    "player_program/future_research": (
        62, "DROP", "s09/s10: props feed carries no player_id; 62 of 11,229 priced rows "
                    "(0.5521%) unresolved and excluded, all player_id 204323"),
}

rows = []
for _, r in kc.iterrows():
    m = MEASURED.get((r["file"], int(r["line"])))
    if m is None and r["class"] in ("PLAYER_NAME_KEYED", "MIXED"):
        sa = SCREEN_ADJ.get(r["screen"])
        if sa:
            m = (sa[0], sa[1], sa[2])
    rows.append({
        "screen": r["screen"], "file": r["file"], "line": int(r["line"]),
        "operation": r["op"], "method": r["method"], "key_used": r["keys"],
        "key_class": r["class"],
        "stable_id_available": stable_id_available(r),
        "rows_diverging_2021_2024": (m[0] if m else (0 if r["class"] in
                                     ("PLAYER_ID_KEYED", "NOT_PLAYER_KEYED") else "")),
        "direction": (m[1] if m else ("NONE" if r["class"] in
                      ("PLAYER_ID_KEYED", "NOT_PLAYER_KEYED") else "NOT_MEASURED")),
        "evidence": (m[2] if m else ""),
    })
KC = pd.DataFrame(rows).sort_values(
    ["key_class", "screen", "file", "line"],
    key=lambda s: s.map({"PLAYER_NAME_KEYED": 0, "MIXED": 1, "PLAYER_ID_KEYED": 2,
                         "UNRESOLVED_KEY": 3, "NOT_PLAYER_KEYED": 4}) if s.name == "key_class" else s)
KC.to_csv(os.path.join(HERE, "KEY_CENSUS.csv"), index=False)
print("  rows: %d" % len(KC))
print(KC.key_class.value_counts().to_string())

# ------------------------------------------------------------------ BLAST_RADIUS
B.banner("BLAST_RADIUS.csv")
screens = sorted(set(ops.screen) | set(cls.screen))
# live verdict detection: a VERDICT.md / a decision line in NOTES.md
VERDICT_RE = re.compile(r"^\s*(?:\*\*)?(kill|keep|promote|adopt|advance|abstain|"
                        r"inconclusive|no-go|reject|retain)(?:\*\*)?\s*$", re.I)
rec = []
for sc in screens:
    d = os.path.join(B.EXP, sc.replace("/", os.sep))
    if not os.path.isdir(d):
        continue
    files = os.listdir(d)
    has_verdict = any(f.upper().startswith(("VERDICT", "DECISION_PACKET", "FINDINGS"))
                      for f in files)
    verdict_txt = ""
    for cand in ("VERDICT.md", "NOTES.md", "DECISION_PACKET.md"):
        fp = os.path.join(d, cand)
        if os.path.exists(fp):
            txt = open(fp, "r", encoding="utf-8", errors="replace").read()
            m = re.search(r"##+\s*(?:Decision|VERDICT|Verdict)\s*\n+\s*(?:\*\*)?([A-Za-z \-]{2,40})",
                          txt)
            if m:
                verdict_txt = m.group(1).strip()[:40]
                break
    so = ops[ops.screen == sc]
    n_name = int(so["class"].isin(["PLAYER_NAME_KEYED", "MIXED"]).sum())
    n_id = int((so["class"] == "PLAYER_ID_KEYED").sum())
    sc_frames = cls[cls.screen == sc]
    n_ident_frames = int((sc_frames["class"] != "NO_PLAYER_IDENTITY").sum())
    gg = guard[guard.path.map(screen_of) == sc]
    exposed = int(pd.to_numeric(gg.get("rows_exposed_duplication", pd.Series(dtype=float)),
                                errors="coerce").fillna(0).max()) if len(gg) else 0
    measured = sum(1 for (f, l) in MEASURED if screen_of(f) == sc)
    adj = ADJUDICATED.get(sc)
    if n_name == 0:
        rows_changed, note, rank = 0, "no name-keyed operation", 0
    elif measured:
        rows_changed, note, rank = 0, "measured directly, s04/s07", 0
    elif adj:
        rows_changed, note, rank = adj[0], adj[1], adj[2]
    else:
        rows_changed, note, rank = "NOT_MEASURED", "", 1
    rec.append({
        "screen": sc,
        "has_live_verdict": bool(has_verdict),
        "verdict": verdict_txt,
        "name_keyed_ops": n_name,
        "id_keyed_ops": n_id,
        "frames_carrying_player_identity": n_ident_frames,
        "max_rows_exposed_to_an_ambiguous_identity": exposed,
        "rows_changed_under_correct_key": rows_changed,
        "direction": ("NONE" if rows_changed == 0 else
                      ("DROP" if isinstance(rows_changed, int) and rows_changed > 0
                       else "UNKNOWN")),
        "adjudication": note,
        "measured_directly": bool(measured or adj),
        "rank_score": rank,
    })
BR = pd.DataFrame(rec)
BR = BR.sort_values(["rank_score", "name_keyed_ops", "max_rows_exposed_to_an_ambiguous_identity"],
                    ascending=[False, False, False])
BR.to_csv(os.path.join(HERE, "BLAST_RADIUS.csv"), index=False)
print("  screens enumerated: %d" % len(BR))
print("  screens with ZERO name-keyed operations : %d" % int((BR.name_keyed_ops == 0).sum()))
print("  screens with >=1 name-keyed operation   : %d" % int((BR.name_keyed_ops > 0).sum()))
print("  of those, measured directly             : %d" % int(BR.measured_directly.sum()))
print("  screens with rows_changed != 0          : %d"
      % int((BR.rows_changed_under_correct_key.astype(str) != "0").sum()))
print()
print(BR[BR.name_keyed_ops > 0][
    ["screen", "has_live_verdict", "verdict", "name_keyed_ops", "id_keyed_ops",
     "max_rows_exposed_to_an_ambiguous_identity", "rows_changed_under_correct_key",
     "direction"]
].to_string(index=False))

# ------------------------------------------------------------------ FINDINGS
B.banner("FINDINGS.json")
anch = pd.read_csv(os.path.join(B.OUT, "ANCHOR_REPRODUCTION.csv"))
strat = pd.read_csv(os.path.join(B.OUT, "_s07_stratum.csv"))
F = {
    "screen": "E1_I0052_identity_key_divergence",
    "partition": "2021-2024 exploration only; 2025/2026 SEALED and never read for measurement",
    "question": ("Where does the research lane key on player names, how many rows diverge "
                 "under the stable key, and does any published verdict change?"),
    "headline": {
        "structural_operations_censused": int(len(KC)),
        "player_name_keyed_operations": int((KC.key_class == "PLAYER_NAME_KEYED").sum()),
        "mixed_id_and_name_keyed_operations": int((KC.key_class == "MIXED").sum()),
        "player_id_keyed_operations": int((KC.key_class == "PLAYER_ID_KEYED").sum()),
        "share_of_player_keyed_ops_that_are_name_keyed": round(
            float((KC.key_class.isin(["PLAYER_NAME_KEYED", "MIXED"])).sum())
            / max(1, int(KC.key_class.isin(["PLAYER_NAME_KEYED", "MIXED",
                                            "PLAYER_ID_KEYED"]).sum())), 6),
        "persisted_frames_scanned": int(len(cls)),
        "frames_with_no_player_identity": int((cls["class"] == "NO_PLAYER_IDENTITY").sum()),
        "frames_id_only": int((cls["class"] == "ID_ONLY").sum()),
        "frames_id_and_name": int((cls["class"] == "ID_AND_NAME").sum()),
        "frames_name_only": int((cls["class"] == "NAME_ONLY").sum()),
        "key_shaped_variable_bindings_recovered": json.load(
            open(os.path.join(B.OUT, "_s13.json")))["n_bindings"],
        "key_shaped_bindings_naming_a_player_name_column": json.load(
            open(os.path.join(B.OUT, "_s13.json")))["n_mentioning_player_name"],
        "rows_diverging_id_vs_name_within_owned_frames": 0,
        "rows_diverging_cross_feed_props_lane": 62,
        "cross_feed_direction": "DROP",
        "cross_feed_upper_bound_on_fit_pool_rows": 14,
        "cross_feed_fit_pool_denominator": 1740,
        "published_verdicts_that_change": 0,
    },
    "anchors": anch.to_dict("records"),
    "e0_i0006_measurement": s04,
    "decision_stratum": {
        "definition": "n_prior >= 8 AND trailing-5 minutes >= 24 (D081, per E1_I0023/s00_prereg)",
        "screen_frame_18212": {"stratum_rows": 6431, "of_rows": 18212,
                               "materialised_DECISION_column_agrees": "18212/18212",
                               "stratum_rows_belonging_to_an_ambiguous_identity": 164,
                               "share_pct": 2.5501},
        "E1_I0045__PF_20084": {"stratum_rows": 4964, "of_rows": 20084,
                               "stratum_rows_belonging_to_an_ambiguous_identity": 123,
                               "share_pct": 2.4778},
        "note": ("These are EXPOSURE, not divergence: both surfaces are joined and grouped on "
                 "player_id, so the stratum row set is identical under both keys."),
    },
    "drop_mode": {"instances_in_research_lane": 0,
                  "names_with_multiple_player_ids_2021_2024": 0,
                  "note": "confirms E1_I0048's finding holds in the research lane"},
    "ambiguous_identities": {
        "in_exploration_partition_2021_2024": 12,
        "thirteenth": "player_id 1643490 (Eliska Hamzova | Eliska Joklova) is 2026-only, SEALED",
        "allowlist": B.AMBIGUOUS_IDS_2021_2024,
    },
    "identity_map_coverage": json.load(open(os.path.join(B.OUT, "_s06.json"))),
    "market_lane": json.load(open(os.path.join(B.OUT, "_s09.json"))),
    "cross_feed_drop_case": json.load(open(os.path.join(B.OUT, "_s10.json"))),
    "cross_feed_drop_reach": json.load(open(os.path.join(B.OUT, "_s11.json"))),
    "residual": json.load(open(os.path.join(B.OUT, "_s12.json"))),
    "key_variable_bindings": json.load(open(os.path.join(B.OUT, "_s13.json"))),
}
json.dump(F, open(os.path.join(HERE, "FINDINGS.json"), "w"), indent=2, default=str)
print("  written: FINDINGS.json")
print(json.dumps(F["headline"], indent=2))
