import pandas as pd,os
HERE=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0040_audit_extension"
T=pd.read_csv(os.path.join(HERE,"INVENTORY_TABLES.csv"))
T=T[(T.p_cols.notna())&(T.p_cols!="")&(~T.is_draw_dump.fillna(False))]
T=T.sort_values(["screen","rows"],ascending=[True,False])
for sc,g in T.groupby("screen"):
    print("\n### %s"%sc)
    for _,rr in g.iterrows():
        print("   %-52s rows=%-6s p=%s"%(os.path.basename(str(rr["file"])),rr["rows"],str(rr["p_cols"])[:120]))
