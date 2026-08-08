"""s01_harvest_ledger.py -- READ-ONLY harvest of every completed screen's reported cells.

Builds the retrospective inventory needed for STEP 2: for each recorded cell, the screen, the
sample size, the family size (number of cells in that screen's family-wise correction), the
grouping level used, the reported dR2 and the reported p-values.  Nothing is recomputed here;
this is a transcription of what the ledger's screens actually published.
"""
import os, sys, json, glob
import numpy as np
import pandas as pd

EXPL = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE = os.path.join(EXPL, "E1_I0026_detection_floor")
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

# Directories owned by other live agents -- NEVER read.
FORBIDDEN = ("E1_I0027_reference_ladder", "E0_I0028_degeneracy_sweep", "E0_I0029_freethrow_hurdle")

RESULT_FILES = ["screen_results.csv", "screen_results_repaired.csv", "leads.csv",
                "usage_tier_gain.csv", "stress_family_wise.csv", "family_wise_by_floor.csv",
                "efficiency_contrast.csv", "points_contrast.csv", "interaction_forecast.csv",
                "upstream_signals.csv", "ladder_increments.csv", "walkforward_points.csv",
                "pooled_tier_dummy.csv", "champion_vs_best.csv"]

rows = []
log = []
for d in sorted(os.listdir(EXPL)):
    if d.startswith("E1_I0026") or any(d.startswith(f) for f in FORBIDDEN):
        continue
    dd = os.path.join(EXPL, d)
    if not os.path.isdir(dd):
        continue
    for rf in RESULT_FILES:
        p = os.path.join(dd, rf)
        if not os.path.exists(p):
            continue
        try:
            t = pd.read_csv(p)
        except Exception as e:
            log.append("READFAIL %s/%s %r" % (d, rf, e))
            continue
        cols = set(t.columns)
        rec = {"screen": d, "file": rf, "n_cells_in_file": int(len(t)),
               "columns": ";".join(sorted(cols))}
        for c in ["n", "n_scored", "n_rows"]:
            if c in cols:
                v = pd.to_numeric(t[c], errors="coerce").dropna()
                if len(v):
                    rec["n_min"] = int(v.min()); rec["n_med"] = int(v.median())
                    rec["n_max"] = int(v.max())
                break
        for c in ["dr2", "paired_dr2_cand_minus_base", "walkforward_paired_dr2_points", "delta_r2"]:
            if c in cols:
                v = pd.to_numeric(t[c], errors="coerce").dropna()
                if len(v):
                    rec["dr2_col"] = c
                    rec["dr2_max"] = float(v.max()); rec["dr2_med"] = float(v.median())
                break
        for c in ["p_familywise_maxt", "p_familywise_N1", "p_familywise", "p_fw"]:
            if c in cols:
                v = pd.to_numeric(t[c], errors="coerce").dropna()
                if len(v):
                    rec["pfw_col"] = c; rec["pfw_min"] = float(v.min())
                    rec["n_cleared_fw05"] = int((v < 0.05).sum())
                break
        for c in ["p_correct_level", "p_N2_entity_swap", "p_N1_within_entity", "paired_p_cluster"]:
            if c in cols:
                v = pd.to_numeric(t[c], errors="coerce").dropna()
                if len(v):
                    rec["pcorrect_col"] = c; rec["pcorrect_min"] = float(v.min())
                    rec["n_cleared_percell05"] = int((v < 0.05).sum())
                break
        rows.append(rec)

inv = pd.DataFrame(rows)
inv.to_csv(os.path.join(OUT, "s01_result_file_inventory.csv"), index=False)
print(inv.drop(columns=["columns"]).to_string(index=False))

# --- pull the per-screen attrition / family-size blocks out of each FINDINGS.json -------------
fw = []
for d in sorted(os.listdir(EXPL)):
    if d.startswith("E1_I0026") or any(d.startswith(f) for f in FORBIDDEN):
        continue
    for p in glob.glob(os.path.join(EXPL, d, "**", "_s0*.json"), recursive=True) + \
             glob.glob(os.path.join(EXPL, d, "**", "FINDINGS.json"), recursive=True):
        try:
            j = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        found = {}

        def walk(o, path=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    kl = str(k).lower()
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        if any(s in kl for s in ("n_cells", "cell_count", "n_candidates",
                                                 "family_size", "n_tests", "decision_stratum_n",
                                                 "n_screened")):
                            found[path + k] = v
                    walk(v, path + k + ".")
            elif isinstance(o, list):
                for i, v in enumerate(o[:50]):
                    walk(v, path + "[%d]." % i)
        walk(j)
        if found:
            fw.append({"screen": d, "json": os.path.relpath(p, EXPL), **found})

fwd = pd.DataFrame(fw)
fwd.to_csv(os.path.join(OUT, "s01_family_sizes.csv"), index=False)
print("\nfamily-size records: %d -> s01_family_sizes.csv" % len(fwd))
for l in log:
    print(l)
