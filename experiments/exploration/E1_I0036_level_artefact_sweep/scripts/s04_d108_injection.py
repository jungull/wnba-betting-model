"""S04 -- read D108's injection-power evidence (E0_I0029_freethrow_hurdle) and the
cell-naming convention used by D103's verdict table. Read-only."""
import os
import pandas as pd

pd.set_option("display.width", 300)
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_rows", 200)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, "experiments", "exploration")

print("### D108 injection_power.csv (the degeneracy proof) ###")
ip = pd.read_csv(os.path.join(EXP, "E0_I0029_freethrow_hurdle", "injection_power.csv"))
print("shape", ip.shape, "\ncols", list(ip.columns))
print(ip.to_string(index=False))

print("\n### D108 injection_power_per_cell / E1_I0033 injection tables ###")
for f in ["E1_I0033_aggregation_level/injection_power.csv",
          "E1_I0033_aggregation_level/injection_power_per_cell.csv",
          "E1_I0033_aggregation_level/absence_injection_power.csv"]:
    p = os.path.join(EXP, *f.split("/"))
    print("--", f)
    if os.path.exists(p):
        d = pd.read_csv(p)
        print(d.to_string(index=False))
    else:
        print("   MISSING")

print("\n### CELL NAMING in D103 verdicts, for E0_I0024 ###")
cv = pd.read_csv(os.path.join(EXP, "E1_I0026_detection_floor", "out", "s08_cell_verdicts.csv"))
sub = cv[cv["screen"] == "E0_I0024_reb_ast_characterisation"]
print(sub.head(12).to_string(index=False))
print("...")
print("\n### retrospective_power.csv level column values ###")
rp = pd.read_csv(os.path.join(EXP, "E1_I0026_detection_floor", "out", "retrospective_power.csv"))
print("shape", rp.shape, "cols", list(rp.columns))
print("level values:", rp["level"].value_counts().to_dict())
print(rp.head(8).to_string(index=False))
