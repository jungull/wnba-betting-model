import json, os, sys
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 100)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
TEAM1 = os.path.join(ROOT, "experiments", "cbs_v12_team_oof")
TEAM2 = os.path.join(ROOT, "experiments", "cbs_v12_team_oof_v2", "attempt_001")
PLAY = os.path.join(ROOT, "experiments", "cbs_v15_player_oof_v5", "attempt_001")

def show(path, label, n=3):
    print("=" * 100)
    print(label, path)
    try:
        df = pd.read_parquet(path)
    except Exception as e:
        print("  FAIL", e)
        return None
    print("  shape", df.shape)
    print("  cols", list(df.columns))
    print("  dtypes:\n", df.dtypes.to_string())
    print(df.head(n).to_string())
    return df

# 1. Team arm, 2023 fold
t = show(os.path.join(TEAM2, "predictions__team_game_distribution__2023.parquet"), "TEAM v2 2023")
tp = show(os.path.join(TEAM2, "provenance_sidecar__2023.parquet"), "TEAM v2 prov 2023")

# 2. Player arm, 2023 fold
for nm in ["player_scoring_distribution", "p_active", "e_minutes_given_active", "attempts_usage"]:
    show(os.path.join(PLAY, "predictions__%s__2023.parquet" % nm), "PLAYER v5 2023 " + nm)
show(os.path.join(PLAY, "provenance_sidecar__2023.parquet"), "PLAYER v5 prov 2023")

# 3. Receipts
print("=" * 100)
for f in ["fold_receipt__2021.json", "fold_receipt__2023.json"]:
    p = os.path.join(TEAM2, f)
    print("--- TEAM v2", f)
    print(json.dumps(json.load(open(p, encoding="utf-8")), indent=1)[:6000])

print("=" * 100)
p = os.path.join(TEAM1, "PROVISIONAL_SUPERSEDED.md")
print(open(p, encoding="utf-8").read())
