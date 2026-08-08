import pandas as pd,os
H=pd.read_csv(r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0040_audit_extension\SCHEME_CODE_HITS.csv")
w=H[H.scheme=="WITHIN_ENTITY"]
for sc in ["E1_I0021_heterogeneity_diagnostic","E1_I0022_optimal_simple_estimator","E1_I0025_threshold_vs_refit","E1_I0026_detection_floor","E1_I0027_reference_ladder","E1_I0030_home_advantage_accounting","E0_I0028_degeneracy_sweep"]:
    g=w[w.screen==sc]
    print("\n### %s (%d)"%(sc,len(g)))
    for _,r in g.iterrows(): print("   %s:%d  %s"%(os.path.basename(r["file"]),r["line"],str(r["code"])[:160]))
