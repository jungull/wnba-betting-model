"""s08_named_list.py -- STEP 2's DELIVERABLE: the NAMED list of recorded nulls that could not
have seen an effect the size of the programme's best-ever lead (dR2 +0.0023, D089).

A cell is flagged UNINFORMATIVE when its own design -- its published null width, its sample
size and its screen's family size -- gives MDE80 > 0.0023.  Nothing about the cell's RESULT is
used to decide this (preregistration s7 item 7).
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from df_base import OUT, hdr

BEST_LEAD = 0.0023
CEIL_D079 = 0.001127
CEIL_D084 = 0.000129

R = pd.read_csv(os.path.join(OUT, "retrospective_power.csv"))
pd.set_option("display.width", 260)
pd.set_option("display.max_rows", 400)

# A screen's verdict is taken on its WORSE (larger) correct-level MDE, because the programme's
# own convention is p_correct_level = max over the correct-level nulls (D085/D089 machinery).
worst = (R.groupby(["screen", "decision", "family_size_K", "cell"])
         .agg(mde80_fw=("mde80_fw", "max"), mde80_percell=("mde80_percell", "max"),
              n=("n", "max"), stat_family=("stat_family", "first"),
              reported_dr2=("reported_dr2", "max"), reported_p_fw=("reported_p_fw", "min"))
         .reset_index())
worst["blind_to_best_lead_fw"] = worst["mde80_fw"] > BEST_LEAD
worst["blind_to_D079_ceiling_fw"] = worst["mde80_fw"] > CEIL_D079
worst["blind_to_D084_ceiling_fw"] = worst["mde80_fw"] > CEIL_D084
worst["blind_to_best_lead_percell"] = worst["mde80_percell"] > BEST_LEAD
worst.to_csv(os.path.join(OUT, "s08_cell_verdicts.csv"), index=False)

hdr("A. PER-SCREEN VERDICT -- share of recorded cells BLIND to each benchmark")
g = worst.groupby(["screen", "decision", "family_size_K"]).agg(
    cells=("cell", "size"), n_med=("n", "median"),
    mde80_fw_median=("mde80_fw", "median"),
    mde80_fw_p25=("mde80_fw", lambda s: s.quantile(0.25)),
    mde80_fw_p75=("mde80_fw", lambda s: s.quantile(0.75)),
    blind_best_lead=("blind_to_best_lead_fw", "mean"),
    blind_D079=("blind_to_D079_ceiling_fw", "mean"),
    blind_D084=("blind_to_D084_ceiling_fw", "mean"),
).reset_index().sort_values("blind_best_lead", ascending=False)
g["blind_best_lead_cells"] = (g["blind_best_lead"] * g["cells"]).round().astype(int)
g.to_csv(os.path.join(OUT, "s08_screen_verdicts.csv"), index=False)
print(g.to_string(index=False))

tot = len(worst)
print("\n  TOTAL recorded cells with a published null width: %d" % tot)
print("  BLIND to the best-ever lead (0.0023) family-wise:  %d  (%.1f%%)"
      % (worst["blind_to_best_lead_fw"].sum(), 100 * worst["blind_to_best_lead_fw"].mean()))
print("  BLIND to the D079 ceiling  (0.001127) family-wise: %d  (%.1f%%)"
      % (worst["blind_to_D079_ceiling_fw"].sum(), 100 * worst["blind_to_D079_ceiling_fw"].mean()))
print("  BLIND to the D084 ceiling  (0.000129) family-wise: %d  (%.1f%%)"
      % (worst["blind_to_D084_ceiling_fw"].sum(), 100 * worst["blind_to_D084_ceiling_fw"].mean()))

hdr("B. THE NAMED LIST -- reported NULLS whose design could not have seen 0.0023")
naming = worst[worst["blind_to_best_lead_fw"]].copy()
# a reported null = a cell that was NOT cleared.  Use the screen's own p_fw where published.
naming["was_reported_null_at_fw05"] = naming["reported_p_fw"].fillna(1.0) >= 0.05
nn = naming[naming["was_reported_null_at_fw05"]]
print("  %d of the %d blind cells were ALSO reported as family-wise nulls (p_fw >= 0.05)."
      % (len(nn), len(naming)))
by = nn.groupby(["screen", "decision"]).agg(
    uninformative_nulls=("cell", "size"), mde80_fw_median=("mde80_fw", "median"),
    n_med=("n", "median"), K=("family_size_K", "max")).reset_index().sort_values(
    "uninformative_nulls", ascending=False)
by.to_csv(os.path.join(OUT, "s08_uninformative_nulls_by_screen.csv"), index=False)
print(by.to_string(index=False))
nn.sort_values("mde80_fw", ascending=False).to_csv(
    os.path.join(OUT, "s08_uninformative_nulls_named.csv"), index=False)
print("\n  worst 30 by MDE80:")
print(nn.sort_values("mde80_fw", ascending=False)
      [["screen", "cell", "n", "mde80_fw", "reported_p_fw"]].head(30).to_string(index=False))
