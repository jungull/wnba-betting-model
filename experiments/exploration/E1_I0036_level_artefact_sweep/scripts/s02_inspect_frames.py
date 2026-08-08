"""S02 -- inspect the frames and the cross-screen result inventory. Read-only."""
import os
import pandas as pd

pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 80)
pd.set_option("display.max_rows", 300)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, "experiments", "exploration")

print("#" * 100)
print("# RESULT FILE INVENTORY (from E1_I0026 detection floor s01)")
inv = pd.read_csv(os.path.join(EXP, "E1_I0026_detection_floor", "out", "s01_result_file_inventory.csv"))
print(inv.shape, list(inv.columns))
print(inv.to_string())

print("\n" + "#" * 100)
print("# FAMILY SIZES")
fs = pd.read_csv(os.path.join(EXP, "E1_I0026_detection_floor", "out", "s01_family_sizes.csv"))
print(fs.shape, list(fs.columns))
print(fs.to_string())

print("\n" + "#" * 100)
print("# D097 screen_frame.parquet")
sf = pd.read_parquet(os.path.join(EXP, "E0_I0024_reb_ast_characterisation", "screen_frame.parquet"))
print("shape", sf.shape)
print("cols", list(sf.columns))
if "season" in sf.columns:
    print("SEASONS:", sf["season"].value_counts().sort_index().to_dict())
print(sf.head(4).to_string())
