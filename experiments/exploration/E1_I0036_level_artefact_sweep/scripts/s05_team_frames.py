"""S05 -- inspect E1_I0033's team frames + test whether D097's screen_frame aggregates
cleanly to team-game level (roster completeness / D087 reference-incompleteness guard)."""
import os
import numpy as np
import pandas as pd

pd.set_option("display.width", 300)
pd.set_option("display.max_columns", 80)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, "experiments", "exploration")
A33 = os.path.join(EXP, "E1_I0033_aggregation_level")

for f in ["_team_frame.parquet", "_team_frame_scored.parquet", "_player_frame.parquet",
          "_master_player_partition.parquet"]:
    p = os.path.join(A33, f)
    print("=" * 100)
    print(f)
    if not os.path.exists(p):
        print("  MISSING")
        continue
    d = pd.read_parquet(p)
    print("  shape", d.shape)
    print("  cols", list(d.columns))
    if "season" in d.columns:
        print("  SEASONS:", d["season"].value_counts().sort_index().to_dict())
    print(d.head(3).to_string())

print("\n" + "=" * 100)
print("### ROSTER COMPLETENESS OF D097 screen_frame WHEN AGGREGATED TO TEAM-GAME ###")
sf = pd.read_parquet(os.path.join(EXP, "E0_I0024_reb_ast_characterisation", "screen_frame.parquet"))
g = sf.groupby(["season", "game_id", "team_id"]).agg(
    n_players=("player_id", "size"),
    tot_min=("minutes", "sum"),
    tot_fga=("fga", "sum"),
    tot_reb=("y_reb", "sum"),
    tot_pts=("y_pts", "sum"),
).reset_index()
print("team-games:", len(g))
print(g[["n_players", "tot_min", "tot_fga", "tot_reb", "tot_pts"]].describe().to_string())
print("\nminutes==200 exactly:", int((np.abs(g["tot_min"] - 200.0) < 1e-6).sum()),
      " within 1.0:", int((np.abs(g["tot_min"] - 200.0) < 1.0).sum()),
      " within 5.0:", int((np.abs(g["tot_min"] - 200.0) < 5.0).sum()))
print("n_players distribution:", g["n_players"].value_counts().sort_index().to_dict())
print("\nteam-games per season:", g.groupby("season").size().to_dict())
bad = g[np.abs(g["tot_min"] - 200.0) >= 5.0]
print("\nteam-games failing the 200-minute completeness check:", len(bad))
print(bad.head(10).to_string(index=False))
