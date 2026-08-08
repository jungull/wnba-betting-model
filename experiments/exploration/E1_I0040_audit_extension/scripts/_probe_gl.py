import pandas as pd
E=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
g=pd.read_csv(E+r"\E0_I0015_points_skill_decomposition\grouping_levels.csv")
print(g.columns.tolist()); print(len(g))
print(g[["candidate","var_share_between_player_season","scheme_used"]].to_string() if "scheme_used" in g.columns else g.head(20).to_string())
print("\nmax vsb among WITHIN-block:",g[g.scheme_used=="WITHIN-block"].var_share_between_player_season.max())
print("min vsb among BETWEEN-block:",g[g.scheme_used=="BETWEEN-block"].var_share_between_player_season.min())
