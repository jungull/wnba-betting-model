"""S14 -- census summary numbers used verbatim in the write-ups."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import OUT, hdr

pd.set_option("display.width", 300)
pd.set_option("display.max_rows", 300)

C = pd.read_csv(os.path.join(OUT, "CENSUS.csv"))
hdr("CENSUS SHAPE")
print("cells", len(C), " screens", C["screen"].nunique())
print(C.groupby(["screen", "decision"]).size().to_string())

hdr("KILL REASON x LEVEL")
print(pd.crosstab(C["level_recorded"], C["kill_reason"]).to_string())

hdr("KILLED ONLY (the census proper)")
K = C[C["kill_reason"].isin(["CEILING", "UNINFORMATIVE_NULL", "POWERED_NULL"])]
print("killed cells", len(K))
print(K["kill_reason"].value_counts().to_string())
print("\nkilled cells whose level was NEVER RECORDED:",
      int((K["level_recorded"] == "NOT_RECORDED").sum()),
      f"({(K['level_recorded'] == 'NOT_RECORDED').mean():.1%})")
print("killed cells at a ROSTER-CONSTANT level (team/opp/matchup):",
      int(K["T2_roster_constant"].sum()))
print("killed cells at a player/row level (re-levelling UP cannot help):",
      int(K["level_recorded"].isin(["player_season", "row", "player_id+season",
                                    "WITHIN-block"]).sum()))

hdr("ELIGIBLE FOR RE-LEVELLING")
E = K[K["ELIGIBLE"]]
print("eligible killed cells:", len(E), f"({len(E) / len(K):.2%} of killed)")
print(E.groupby(["screen", "level_recorded"]).size().to_string())
print("\nCEILING KILLS -- NOT RESURRECTED, listed for the record:")
CK = C[C["kill_reason"] == "CEILING"]
print("count:", len(CK))
print(CK.groupby(["screen", "candidate", "target"]).size().head(40).to_string())
print("\nceiling-kill candidates (distinct):",
      sorted(CK["candidate"].unique().tolist()))

hdr("POWER")
print("cells with a D103 MDE:", int(C["mde80_fw_used"].notna().sum()))
print("median mde80_fw over killed cells: %.6f" % K["mde80_fw_used"].median())
print("killed cells flagged blind to the programme's best live effect (0.002057): %d (%.1f%%)"
      % (int((K["blind_used"] >= 0.5).sum()), 100 * (K["blind_used"] >= 0.5).mean()))

hdr("THE FOUR RE-RUNS + THE DEBT")
for f in ["LEVEL_FAIRTEST_CELLS.csv", "D097_NULL_COMPARISON.csv",
          "D097_COMPONENT_NULLS.csv", "D097_RELEVEL_CELLS.csv"]:
    p = os.path.join(OUT, f)
    if os.path.exists(p):
        print("\n---", f)
        print(pd.read_csv(p).to_string(index=False))
