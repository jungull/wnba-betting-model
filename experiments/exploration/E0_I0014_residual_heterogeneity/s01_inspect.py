import pandas as pd, numpy as np, json, os, sys
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 200)
R = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OOF = os.path.join(R, "experiments", "cbs_v15_player_oof_v5", "attempt_001")

for tgt in ["player_scoring_distribution", "e_minutes_given_active", "attempts_usage", "p_active"]:
    p = os.path.join(OOF, f"predictions__{tgt}__2023.parquet")
    df = pd.read_parquet(p)
    print("=" * 90)
    print(tgt, df.shape)
    print(list(df.columns))
    print(df.head(3).to_string())

p = os.path.join(OOF, "provenance_sidecar__2023.parquet")
df = pd.read_parquet(p)
print("=" * 90); print("provenance_sidecar", df.shape); print(list(df.columns)); print(df.head(3).to_string())

mp = pd.read_parquet(os.path.join(R, "data", "masters", "master_player.parquet"))
print("=" * 90); print("master_player", mp.shape); print(list(mp.columns))
print(mp.head(3).to_string())
