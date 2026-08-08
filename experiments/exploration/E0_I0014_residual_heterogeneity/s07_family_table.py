import os
import numpy as np
import pandas as pd
import rh_base as B
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 400)
R = pd.read_csv(os.path.join(B.OUT, "screen_results.csv"))
Ra = R[R["dependent"].str.endswith("absres")].copy()
B.hdr("EVERY CANDIDATE x |resid| DEPENDENT, GROUPED BY FAMILY")
for fam in sorted(Ra["family"].unique()):
    g = Ra[Ra.family == fam].sort_values(["candidate", "dependent"])
    print("\n--- FAMILY: %s ---" % fam)
    print(g[["candidate", "dependent", "correct_null_level", "var_share_between_blocks",
             "beta_per_sd", "t_classical", "p_correct_level", "p_row_level_NAIVE",
             "null_inflation_factor", "p_familywise_absres_family", "dec_lo_mean", "dec_hi_mean",
             "dec_ratio"]].to_string(index=False))
B.hdr("FAMILY SUMMARY: best |t| and best decile ratio per family")
s = Ra.assign(abs_t=Ra["t_classical"].abs(),
              dev_ratio=(Ra["dec_ratio"] - 1).abs()).groupby("family").agg(
    n_cells=("candidate", "size"), best_abs_t=("abs_t", "max"),
    n_p_correct_lt_05=("p_correct_level", lambda x: int((x < 0.05).sum())),
    n_fw_lt_05=("p_familywise_absres_family", lambda x: int((x < 0.05).sum())),
    max_dec_ratio_dev=("dev_ratio", "max"))
print(s.sort_values("max_dec_ratio_dev", ascending=False).to_string())
s.to_csv(os.path.join(B.OUT, "family_summary.csv"))
B.hdr("SCHEDULE / ROSTER / OPPONENT FAMILIES IN FULL (the ones expected to die)")
for fam in ["schedule_state", "roster_stability", "opponent_unfamiliarity", "game_context",
            "player_availability"]:
    g = Ra[Ra.family == fam].sort_values("dec_ratio")
    print("\n--- %s ---" % fam)
    print(g[["candidate", "dependent", "t_classical", "p_correct_level",
             "p_familywise_absres_family", "dec_lo_mean", "dec_hi_mean",
             "dec_ratio"]].to_string(index=False))
