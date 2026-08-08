import os
import pandas as pd
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
p = os.path.join(ROOT, "experiments", "exploration", "E0_I0029_freethrow_hurdle",
                 "screen_frame.parquet")
d = pd.read_parquet(p)
print("shape", d.shape)
print("SEASONS:", d["season"].value_counts().sort_index().to_dict())
for c in list(d.columns):
    print("  ", c, "|", str(d[c].dtype), "| nonnull %.4f" % d[c].notna().mean())
