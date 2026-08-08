import pandas as pd, json, os
E=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
for rel in [r"E0_I0014_residual_heterogeneity\analysis_frame.parquet",
            r"E0_I0019_availability_forecast\analysis_frame.parquet"]:
    p=os.path.join(E,rel)
    d=pd.read_parquet(p)
    print(rel, d.shape)
    for c in ("season","game_date","player_id","team_id","opp_team_id","game_id"):
        if c in d.columns:
            try: print("   ",c, d[c].nunique(), sorted(d[c].unique())[:6] if c=="season" else "")
            except Exception: pass
