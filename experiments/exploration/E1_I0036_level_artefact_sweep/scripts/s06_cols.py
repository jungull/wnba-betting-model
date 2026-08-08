"""S06 -- print the exact columns of every screen result file the census will harvest."""
import os
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, "experiments", "exploration")

FILES = [
    "E0_I0014_residual_heterogeneity/screen_results.csv",
    "E0_I0016_efficiency_predictors/screen_results.csv",
    "E0_I0017_shot_quality_efficiency/screen_results.csv",
    "E0_I0019_availability_forecast/screen_results_repaired.csv",
    "E0_I0024_reb_ast_characterisation/upstream_signals.csv",
    "E0_I0029_freethrow_hurdle/screen_results.csv",
    "E1_I0018_teammate_volume_channel/screen_results.csv",
    "E1_I0023_usage_defence_interaction/interaction_forecast.csv",
]
for f in FILES:
    p = os.path.join(EXP, *f.split("/"))
    print("=" * 100)
    print(f)
    if not os.path.exists(p):
        print("  MISSING")
        continue
    d = pd.read_csv(p)
    print("  shape", d.shape)
    print("  cols", list(d.columns))
    for c in d.columns:
        if d[c].dtype == object and d[c].nunique() <= 25:
            print("    VALUES", c, "->", sorted(d[c].dropna().astype(str).unique().tolist()))
