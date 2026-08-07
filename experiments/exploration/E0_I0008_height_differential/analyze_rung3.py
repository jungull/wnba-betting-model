"""
E0 I0008 -- RUNG 3: actual simultaneous on-court height differential vs which side (offense
or defense) secures the rebound. Uses the ~72%-accurate (I0003) clock-time-to-possession
lineup attribution -- ceiling inherited, not re-measured. Treat any null here as AMBIGUOUS,
not negative, per coordinator redirect.
"""
import pandas as pd
import numpy as np

OUT = "experiments/exploration/E0_I0008_height_differential"
df = pd.read_csv(f"{OUT}/rebound_events_height.csv")
print("loaded:", df.shape)

# off_minus_def_height: positive = offense taller. is_orb=1 means offense secured it.
r = np.corrcoef(df["off_minus_def_height"], df["is_orb"])[0, 1]
print(f"corr(off_minus_def_height, is_orb) = {r:.4f}  n={len(df)}")

# bucket by quintile of height diff, show ORB rate per bucket -- direction check
df["hbin"] = pd.qcut(df["off_minus_def_height"], 5, duplicates="drop")
print(df.groupby("hbin", observed=True)["is_orb"].agg(["mean", "count"]))

# season stability
print("\nby season:")
for season in sorted(df["season"].unique()):
    sub = df[df["season"] == season]
    rs = np.corrcoef(sub["off_minus_def_height"], sub["is_orb"])[0, 1]
    print(f"  season={season}: corr={rs:.4f} n={len(sub)} orb_rate={sub['is_orb'].mean():.3f}")

print("\noverall ORB rate:", df["is_orb"].mean())
print("DONE analyze_rung3")
