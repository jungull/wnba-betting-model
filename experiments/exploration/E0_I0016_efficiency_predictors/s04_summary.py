"""E0_I0016 s04 -- per-family attrition, grouping-level audit, and the tables NOTES.md quotes."""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ep_base import OUT, hdr

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_rows", 200)

res = pd.read_csv(os.path.join(OUT, "screen_results.csv"))
with open(os.path.join(OUT, "_s02.json"), encoding="utf-8") as fh:
    s02 = json.load(fh)

FAMNAME = {"A": "opponent defensive matchup quality", "B": "foul-draw / free-throw channel",
           "C": "teammate context", "D": "pace / transition", "E": "shot-mix / shot-quality proxy",
           "F": "rest & load x shooting (interactions only)", "G": "negative control"}

hdr("PER-FAMILY ATTRITION (cells = candidates x 3 outcomes)")
g = res.groupby("family")
tab = pd.DataFrame({
    "cells": g.size(),
    "candidates": g["candidate"].nunique(),
    "max_dr2": g["dr2"].max(),
    "cleared_N1_p05": g.apply(lambda d: int((d["p_N1_within_entity"] < 0.05).sum()), include_groups=False),
    "cleared_N2_p05": g.apply(lambda d: int((d["p_N2_entity_swap"] < 0.05).sum()), include_groups=False),
    "cleared_BOTH_p05": g.apply(lambda d: int((d["p_correct_level"] < 0.05).sum()), include_groups=False),
    "cleared_FAMILYWISE_p05": g.apply(lambda d: int((d["p_familywise_maxt"] < 0.05).sum()), include_groups=False),
    "would_clear_ROW_NAIVE_p05": g.apply(lambda d: int((d["p_row_level_NAIVE"] < 0.05).sum()), include_groups=False),
})
tab["family_name"] = [FAMNAME[i] for i in tab.index]
print(tab.to_string())
tab.to_csv(os.path.join(OUT, "family_attrition.csv"))

hdr("EVERY CELL, RANKED BY dR2 -- the kill/keep log")
cols = ["outcome", "candidate", "family", "entity_level", "n", "n_entity_seasons", "dr2",
        "dr2_sign", "p_N1_within_entity", "p_N2_entity_swap", "p_correct_level",
        "p_familywise_maxt", "p_row_level_NAIVE", "spread_refresid_decile",
        "corr_with_abs_resid", "skill_vs_reference", "dr2_over_refA"]
log = res.sort_values("dr2", ascending=False)[cols]
log["VERDICT"] = np.where(log["p_familywise_maxt"] < 0.05, "KEEP (lead)", "KILL")
log.to_csv(os.path.join(OUT, "kill_keep_log.csv"), index=False)
print(log.head(45).to_string(index=False))
print("\n  ... full 132-row kill/keep log written to kill_keep_log.csv")

hdr("GROUPING-LEVEL AUDIT (screenkit.detect_grouping_level on every cell)")
gl = pd.DataFrame(s02["grouping_levels"]).T
gl.index.name = "cell"
print("  status counts: %s" % gl["status"].value_counts().to_dict())
print("  declared entity vs kit's coarsest constant level:")
print(gl.groupby(["declared_entity_level", "status"]).size().to_string())
print("\n  n_groups at declared entity (distinct values): %s"
      % sorted(gl["n_groups_at_declared_entity"].unique().tolist()))
print("  any cell where the feature IS constant within the declared entity: %d"
      % int(gl["constant_within_declared_entity"].sum()))
print("  -> every candidate varies within its entity-season, which is exactly why neither of the")
print("     kit's two schemes alone covers the between-entity question (see NOTES kit feedback).")
gl.to_csv(os.path.join(OUT, "grouping_levels.csv"))

hdr("ROW-LEVEL NULL: how much would it have over-passed?")
print("  cells clearing per-candidate on the NAIVE row-level null : %d of %d"
      % (int((res["p_row_level_NAIVE"] < 0.05).sum()), len(res)))
print("  cells clearing on BOTH correct-level nulls                : %d of %d"
      % (int((res["p_correct_level"] < 0.05).sum()), len(res)))
print("  cells clearing FAMILY-WISE                                : %d of %d"
      % (int((res["p_familywise_maxt"] < 0.05).sum()), len(res)))
print("  median sd inflation N1/row = %.3f   N2/row = %.3f   max N1/row = %.3f"
      % (res["inflation_N1_over_row"].median(), res["inflation_N2_over_row"].median(),
         res["inflation_N1_over_row"].max()))
print("  cells where the row-level null passes but BOTH correct nulls fail: %d"
      % int(((res["p_row_level_NAIVE"] < 0.05) & (res["p_correct_level"] >= 0.05)).sum()))

hdr("REFERENCE ROBUSTNESS: dR2 over REF-B vs over REF-A, for the 8 family-wise survivors")
sv = res[res["p_familywise_maxt"] < 0.05].sort_values("dr2", ascending=False)
print(sv[["outcome", "candidate", "dr2", "dr2_over_refA", "paired_dr2_cand_minus_ref",
          "paired_p_cluster", "paired_p_row_NAIVE"]].to_string(index=False))
