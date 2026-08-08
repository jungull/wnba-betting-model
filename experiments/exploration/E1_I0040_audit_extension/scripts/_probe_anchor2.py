import pandas as pd
EXPL=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
c=pd.read_csv(EXPL+r"\E1_I0036_level_artefact_sweep\CENSUS.csv")
at=pd.read_csv(EXPL+r"\E1_I0038_within_entity_null_audit\AUDIT_TABLE.csv")
print(c.level_recorded.value_counts(dropna=False))
k=c[c.kill_reason.notna()]
print("--- kills only ---"); print(k.level_recorded.value_counts(dropna=False))
print("--- audit_table level_recorded ---"); print(at.level_recorded.value_counts(dropna=False))
kk=at[at.is_kill==True]; print("--- at kills ---"); print(kk.level_recorded.value_counts(dropna=False))
