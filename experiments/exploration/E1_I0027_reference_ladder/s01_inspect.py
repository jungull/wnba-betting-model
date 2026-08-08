"""E1_I0027 s01 -- READ-ONLY inspection of the frames this screen may stand on.

Nothing is written outside E1_I0027_reference_ladder/.
"""
import os

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")

FRAMES = {
    "D081_decomp": r"E0_I0015_points_skill_decomposition\decomp_frame.parquet",
    "D089_screen": r"E1_I0018_teammate_volume_channel\screen_frame.parquet",
    "D092_tier": r"E1_I0020_coldstart_tiering\tier_frame.parquet",
    "D092_placeholder": r"E1_I0020_coldstart_tiering\placeholder_frame.parquet",
    "D097_rebast": r"E0_I0024_reb_ast_characterisation\screen_frame.parquet",
    "D079_fga": r"E1_I0004_fga_forecast\forecast_frame.parquet",
    "D079_fga_gate": r"E1_I0004_fga_forecast\forecast_frame_pregame_gate.parquet",
}

for k, rel in FRAMES.items():
    p = os.path.join(EXP, rel)
    print("\n" + "=" * 110)
    print("%s  ->  %s" % (k, rel))
    if not os.path.exists(p):
        print("  MISSING")
        continue
    f = pd.read_parquet(p)
    print("  shape=%s" % (f.shape,))
    print("  dtypes/cols:")
    for c in f.columns:
        s = f[c]
        extra = ""
        if pd.api.types.is_numeric_dtype(s):
            v = pd.to_numeric(s, errors="coerce")
            extra = "  min=%s max=%s nan=%d" % (np.nanmin(v) if v.notna().any() else "NA",
                                                np.nanmax(v) if v.notna().any() else "NA",
                                                int(v.isna().sum()))
        elif pd.api.types.is_datetime64_any_dtype(s):
            extra = "  min=%s max=%s" % (s.min(), s.max())
        else:
            extra = "  nuniq=%d  ex=%s" % (s.nunique(), list(s.dropna().unique()[:3]))
        print("    %-42s %-16s %s" % (c, str(s.dtype), extra))
    for sc in ("season", "SEASON", "year"):
        if sc in f.columns:
            print("  season counts: %s" % f[sc].value_counts().sort_index().to_dict())
            break
