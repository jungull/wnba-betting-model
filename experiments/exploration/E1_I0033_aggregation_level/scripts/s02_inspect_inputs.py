import json, os, sys
import pandas as pd
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 120)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
CV4 = os.path.join(ROOT, "experiments", "prediction_contract_v4")

for nm in ["team_game", "player_game", "game"]:
    p = os.path.join(CV4, nm + ".parquet")
    df = pd.read_parquet(p)
    print("=" * 100)
    print(nm, df.shape)
    print(list(df.columns))
    print(df.head(3).to_string())
    if "season" in df.columns:
        print("seasons:", sorted(df["season"].unique().tolist()))
    print("--- manifest ---")
    print(open(p + ".manifest.json", encoding="utf-8").read()[:2500])

print("=" * 100)
print("MASTER manifests")
for nm in ["master_team", "master_player"]:
    p = os.path.join(ROOT, "data", "masters", nm + ".parquet")
    print("---", nm)
    print(open(p + ".manifest.json", encoding="utf-8").read())

print("=" * 100)
mt = pd.read_parquet(os.path.join(ROOT, "data", "masters", "master_team.parquet"))
print("master_team", mt.shape); print(list(mt.columns))
print(mt.head(2).to_string())
mp = pd.read_parquet(os.path.join(ROOT, "data", "masters", "master_player.parquet"))
print("master_player", mp.shape); print(list(mp.columns))
print(mp.head(2).to_string())
