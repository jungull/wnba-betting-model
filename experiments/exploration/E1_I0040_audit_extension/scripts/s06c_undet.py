import pandas as pd, numpy as np, os
EXPL=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0040_audit_extension"
AT=pd.read_csv(os.path.join(HERE,"AUDIT_TABLE_EXT.csv"))
u=AT[AT.EXPOSURE=="UNDETERMINABLE"]
print("UNDETERMINABLE by screen/file:")
print(u.groupby(["screen","source_file"]).size().to_string())
print("\n--- E1_I0036 undeterminable rows ---")
print(u[u.screen=="E1_I0036_level_artefact_sweep"][["source_file","candidate","target","stratum","null_scheme_recorded","observed_stat","p_decision"]].to_string())
print("\n--- E1_I0034 undeterminable rows ---")
print(u[u.screen=="E1_I0034_redistribution"][["source_file","candidate","target","stratum","base","null_scheme_recorded","observed_stat","null_mean","p_decision"]].to_string())
print("\n=== E1_I0034 primary_cells null_scheme values ===")
p=pd.read_csv(os.path.join(EXPL,"E1_I0034_redistribution","primary_cells.csv"))
print(p[["cell","candidate","null_scheme","effect","p","null_mean","null_sd","null_mean_over_observed","verdict"]].to_string())
print("\n=== E1_I0036 D097_COMPONENT_NULLS ===")
print(pd.read_csv(os.path.join(EXPL,"E1_I0036_level_artefact_sweep","D097_COMPONENT_NULLS.csv")).to_string())
