import pandas as pd
E=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
a=pd.read_csv(E+r"\E0_I0015_points_skill_decomposition\abstention_rate_screen.csv")
print("rows",len(a))
print(a.scheme.value_counts(dropna=False))
print("\nby scheme x kill(p>=0.05):")
a["kill"]=a.p_correct_level>=0.05
print(pd.crosstab(a.scheme,a.kill))
print("\nfamilywise kill:")
a["fwkill"]=a.familywise_p_correct>=0.05
print(pd.crosstab(a.scheme,a.fwkill))
print("\ncandidates:",a.candidate.nunique(),"dependents:",a.dependent.nunique())
print(a.dependent.value_counts())
print("\nWITHIN-block sample rows:")
print(a[a.scheme=="WITHIN-block"].head(8).to_string())
