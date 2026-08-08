import pandas as pd,json,os
HERE=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0040_audit_extension"
AT=pd.read_csv(os.path.join(HERE,"AUDIT_TABLE_EXT.csv"))
print("AUDIT_TABLE_EXT.csv:",AT.shape[0],"rows x",AT.shape[1],"cols")
print("columns:",list(AT.columns))
K=AT[AT.is_kill]
print("\nFINAL CONSISTENCY CHECK")
print("  kills                      :",len(K))
print("  EXPOSED                    :",int((K.EXPOSURE=='EXPOSED').sum()))
print("  NOT_EXPOSED                :",int((K.EXPOSURE=='NOT_EXPOSED').sum()))
print("  UNDETERMINABLE             :",int((K.EXPOSURE=='UNDETERMINABLE').sum()))
print("  already counted in E1_I0038:",int((K.EXPOSURE=='EXPOSED_ALREADY_COUNTED_IN_E1_I0038').sum()))
print("  sum check                  :",int(K.EXPOSURE.value_counts().sum()),"==",len(K))
print("  combined programme-wide    : 83 +",int((K.EXPOSURE=='EXPOSED').sum()),"=",83+int((K.EXPOSURE=='EXPOSED').sum()))
print("  combined auditable kills   : 1367 +",len(K),"=",1367+len(K))
print("  combined undeterminable    : 0 +",int((K.EXPOSURE=='UNDETERMINABLE').sum()))
print("  var_share_source tally:"); print(AT.var_share_source.value_counts().to_string())
print("\nDeliverables present:")
for f in ["AUDIT_TABLE_EXT.csv","VERDICT.md","FLIPS.md","FINDINGS.json","NOTES.md","DEFECTS.md","EXPOSED_CELLS_EXT.csv","EXPOSED_DISCHARGE.csv","MEASURED_VARIANCE_SHARES.csv","E1_I0021_ESTIMAND_CHECK.csv","E1_I0031_RECOVERED_NULL_MOMENTS.csv","COVERAGE_EXT.csv"]:
    p=os.path.join(HERE,f); print("   %-38s %s" % (f, ("%d bytes"%os.path.getsize(p)) if os.path.exists(p) else "MISSING"))
