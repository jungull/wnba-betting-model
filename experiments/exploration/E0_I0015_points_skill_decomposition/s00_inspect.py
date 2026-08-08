import pandas as pd, numpy as np
p = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E0_I0014_residual_heterogeneity\analysis_frame.parquet"
f = pd.read_parquet(p)
print("shape", f.shape)
print("seasons", sorted(f["season"].unique()))
print("maxdate", f["gdate"].max())
print("--- columns ---")
for c in sorted(f.columns):
    print("  ", c, str(f[c].dtype))
print("--- head of key cols ---")
kc = [c for c in ["row_uid","season","gdate","player_id","team_id","game_id","minutes","pts","fga",
                  "y_pts","y_minutes","y_fga","pts__pred_point","minutes__pred_point","fga__pred_point",
                  "ref_pts","ref_minutes","ref_fga"] if c in f.columns]
print(f[kc].head(5).to_string())
print("--- describe outcomes ---")
print(f[["y_pts","y_minutes","y_fga"]].describe().to_string())
print("--- zero minutes rows:", int((f["y_minutes"]<=0).sum()))
print("--- zero fga rows:", int((f["y_fga"]<=0).sum()))
print("--- pred minutes <=0:", int((f["minutes__pred_point"]<=0).sum()))
print("--- pred fga <=0:", int((f["fga__pred_point"]<=0).sum()))
print("--- min pred minutes", f["minutes__pred_point"].min(), "min pred fga", f["fga__pred_point"].min())
print("--- n players", f["player_id"].nunique(), "n player-seasons", f.groupby(["season","player_id"]).ngroups)
