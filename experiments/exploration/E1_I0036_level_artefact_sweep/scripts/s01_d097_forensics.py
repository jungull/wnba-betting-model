"""S01 -- forensics on D097's rebound kill (E0_I0024_reb_ast_characterisation).

Read-only. Establishes WHICH candidate was the strongest rebound candidate,
WHICH null killed it, and whether the kill was a ceiling kill or a null kill.
"""
import os
import pandas as pd

pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_rows", 400)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
D097 = os.path.join(ROOT, "experiments", "exploration", "E0_I0024_reb_ast_characterisation")

us = pd.read_csv(os.path.join(D097, "upstream_signals.csv"))
print("upstream_signals shape", us.shape)
print("\nLEVELS:", us["level"].value_counts().to_dict())
print("STRATA:", us["stratum"].value_counts().to_dict())
print("TARGETS:", us["target"].value_counts().to_dict())
print("BASES:", us["base"].value_counts().to_dict())
print("FAMILIES:", us["family"].value_counts().to_dict())
print("CANDIDATES:", sorted(us["candidate"].unique().tolist()))

# Which null does p_correct_level equal, by level?
print("\n### WHICH NULL IS 'correct_level', BY LEVEL ###")
for lv, g in us.groupby("level"):
    eq_row = (g["p_correct_level"] == g["p_row_level_NAIVE"]).mean()
    eq_swap = (g["p_correct_level"] == g["p_entity_swap"]).mean()
    eq_cyc = (g["p_correct_level"] == g["p_cyclic_shift"]).mean()
    print(f"  {lv:18s} n={len(g):4d}  ==row {eq_row:.2f}  ==entity_swap {eq_swap:.2f}  ==cyclic {eq_cyc:.2f}")

REB = ["y_reb", "y_dreb", "y_oreb"]
reb = us[us["target"].isin(REB)].copy()
print(f"\n### REBOUND CELLS: {len(reb)} ###")
cols = ["stratum", "target", "base", "candidate", "level", "n", "dr2",
        "p_row_level_NAIVE", "p_entity_swap", "p_cyclic_shift", "p_correct_level",
        "CEILING_dr2_D089form", "fw_p"]
top = reb.sort_values("dr2", ascending=False).head(25)
print(top[cols].to_string(index=False))

print("\n### THE STRONGEST REBOUND CANDIDATE ###")
s = reb.sort_values("dr2", ascending=False).iloc[0]
for k, v in s.items():
    print(f"  {k:32s} {v}")

print("\n### ALL R08_player_ra_share CELLS (every target/stratum/base) ###")
r08 = us[us["candidate"] == "R08_player_ra_share"]
print(r08[cols].to_string(index=False))

print("\n### ALL player_season-LEVEL CELLS ###")
ps = us[us["level"] == "player_season"]
print(ps[cols].sort_values("dr2", ascending=False).to_string(index=False))
