import pandas as pd,os,json
HERE=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0040_audit_extension"
AT=pd.read_csv(os.path.join(HERE,"AUDIT_TABLE_EXT.csv"))
C=pd.read_csv(os.path.join(HERE,"COVERAGE_EXT.csv"))
haz=set(C[C.draw_archives_on_disk>0].screen)
none=AT[AT.null_mean_source=="NONE"]
print("cells with NO null mean extracted:",len(none))
print("  ...in a screen that HAS raw draw archives on disk (recoverable, not recovered):",int(none.screen.isin(haz).sum()))
print("  ...in a screen with NO draw archive at all:",int((~none.screen.isin(haz)).sum()))
print(none[~none.screen.isin(haz)].screen.value_counts().to_string())
K=AT[AT.is_kill]
print("\nz<-1 trips among KILLS:",int((K.flag_z_lt_neg1==True).sum()),"of",int(K.z_obs_vs_null.notna().sum()),"computable")
print("bare flag trips among KILLS:",int((K.flag_null_mean_gt_observed==True).sum()))
print("\nz<-1 by screen:"); print(K[K.flag_z_lt_neg1==True].groupby(["screen","EXPOSURE"]).size().to_string())
print("\nflag as a detector on the thirty (kills with computable z):")
d=K[K.z_obs_vs_null.notna()]
print(pd.crosstab(d.flag_z_lt_neg1,d.EXPOSURE).to_string())
print("\nbare flag:"); print(pd.crosstab(d.flag_null_mean_gt_observed,d.EXPOSURE).to_string())
print("\nceiling kills detail:"); print(AT[AT.is_ceiling][["screen","source_file","candidate","target","observed_stat"]].to_string())
