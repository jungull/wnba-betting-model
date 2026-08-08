import pandas as pd, numpy as np, os
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 300)
R = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
pg = pd.read_parquet(os.path.join(R, "experiments", "prediction_contract_v4", "player_game.parquet"))
print("shape", pg.shape)
print(list(pg.columns))
print(pg.dtypes.to_string())
print(pg.head(3).to_string())
print("seasons:", sorted(pg['season'].unique()) if 'season' in pg.columns else 'no season col')
