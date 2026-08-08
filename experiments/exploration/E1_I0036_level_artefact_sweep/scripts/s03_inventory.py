"""S03 -- compact inventory of every screened-cell result file, and whether it records a LEVEL. Read-only."""
import os
import pandas as pd

pd.set_option("display.width", 300)
pd.set_option("display.max_colwidth", 90)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, "experiments", "exploration")

inv = pd.read_csv(os.path.join(EXP, "E1_I0026_detection_floor", "out", "s01_result_file_inventory.csv"))
print("### D103 HARVESTED RESULT FILES ###")
print(inv[["screen", "file", "n_cells_in_file", "pcorrect_col", "dr2_col", "pfw_col",
           "n_med", "dr2_max", "pfw_min", "n_cleared_fw05"]].to_string(index=False))

print("\n\n### SCAN: every exploration CSV that looks like a cell-result table, does it record LEVEL? ###")
LEVEL_HINTS = ("level", "grain", "unit", "varies_at", "null_level", "entity")
P_HINTS = ("p_correct", "p_fw", "fw_p", "p_perm", "p_value", "pval")
D_HINTS = ("dr2", "d_r2", "delta_r2", "dR2")
rows = []
for dirpath, dirnames, filenames in os.walk(EXP):
    if "E1_I0036" in dirpath:
        continue
    for fn in filenames:
        if not fn.lower().endswith(".csv"):
            continue
        fp = os.path.join(dirpath, fn)
        try:
            cols = list(pd.read_csv(fp, nrows=0).columns)
        except Exception:
            continue
        lc = [c.lower() for c in cols]
        has_p = any(any(h in c for h in P_HINTS) for c in lc)
        has_d = any(any(h.lower() in c for h in D_HINTS) for c in lc)
        if not (has_p and has_d):
            continue
        levcols = [c for c in cols if any(h == c.lower() or h in c.lower() for h in LEVEL_HINTS)]
        try:
            n = len(pd.read_csv(fp, usecols=[cols[0]]))
        except Exception:
            n = -1
        rows.append({
            "screen": os.path.relpath(dirpath, EXP).split(os.sep)[0],
            "file": os.path.relpath(fp, EXP),
            "n_rows": n,
            "level_cols": ";".join(levcols) if levcols else "",
        })
out = pd.DataFrame(rows).sort_values(["screen", "file"])
print(out.to_string(index=False))
print("\nfiles with an explicit level column:", int((out["level_cols"] != "").sum()), "of", len(out))
