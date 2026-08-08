"""S00 -- inspect the two source screens that anchor this sweep.

Read-only. Prints structure of:
  - E1_I0026_detection_floor/out/s08_cell_verdicts.csv   (D103 per-cell power census)
  - E0_I0024_reb_ast_characterisation/*.csv              (D097 rebound kill)
"""
import os
import pandas as pd

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 100)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, "experiments", "exploration")


def head(path, n=6):
    print("=" * 110)
    print(path.replace(EXP + os.sep, ""))
    if not os.path.exists(path):
        print("  MISSING")
        return None
    df = pd.read_csv(path)
    print("  shape", df.shape)
    print("  cols", list(df.columns))
    print(df.head(n).to_string())
    return df


cv = head(os.path.join(EXP, "E1_I0026_detection_floor", "out", "s08_cell_verdicts.csv"))
if cv is not None:
    for c in cv.columns:
        if cv[c].dtype == object and cv[c].nunique() < 40:
            print("  VALUES", c, "->", sorted(cv[c].dropna().unique().tolist())[:40])
    print("  n unique screens:", cv.get("screen", pd.Series(dtype=object)).nunique())

head(os.path.join(EXP, "E1_I0026_detection_floor", "out", "s08_screen_verdicts.csv"), 40)
head(os.path.join(EXP, "E1_I0026_detection_floor", "out", "s06_retrospective_by_screen.csv"), 40)
head(os.path.join(EXP, "E1_I0026_detection_floor", "out", "s08_uninformative_nulls_by_screen.csv"), 40)

print("\n\n########## D097 SCREEN (E0_I0024) ##########")
for f in ["ladder_summary.csv", "arithmetic_ceiling.csv", "per_season_consistency.csv",
          "response_distributions.csv", "baseline_accuracy.csv", "history_floor_curve.csv",
          "leakage_probes.csv", "propagation_walkforward.csv"]:
    head(os.path.join(EXP, "E0_I0024_reb_ast_characterisation", f), 10)

us = head(os.path.join(EXP, "E0_I0024_reb_ast_characterisation", "upstream_signals.csv"), 10)
if us is not None:
    for c in us.columns:
        if us[c].dtype == object and us[c].nunique() < 60:
            print("  VALUES", c, "->", sorted(us[c].dropna().astype(str).unique().tolist())[:60])
