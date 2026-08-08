"""S01 -- probe the specific columns that decide exposure, per source screen.

Question per screen:
  (a) which recorded p is THE decision p (`p_correct_level` etc.)?
  (b) which null scheme produced it?  -- established by NUMERIC MATCH of the decision p
      against each candidate null's p column, never by guessing.
  (c) is a null_mean recorded for that scheme?
  (d) is a between-entity variance share recorded, and OVER WHICH ENTITY?
"""
import os
import numpy as np
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 80)
pd.set_option("display.max_rows", 200)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, "experiments", "exploration")


def hdr(s):
    print("\n" + "=" * 100 + "\n" + s + "\n" + "=" * 100)


def match(dec, cands, d):
    """For each row, which candidate p column equals the decision p (exactly, to 1e-12)?"""
    out = []
    for i in range(len(d)):
        dv = d[dec].iloc[i]
        hits = [c for c in cands if c in d.columns and pd.notna(d[c].iloc[i])
                and pd.notna(dv) and abs(float(d[c].iloc[i]) - float(dv)) < 1e-12]
        out.append("+".join(hits) if hits else ("NA" if pd.isna(dv) else "NO_MATCH"))
    return pd.Series(out, index=d.index)


# ---------------------------------------------------------------- E0_I0014
hdr("E0_I0014_residual_heterogeneity (D078/D082)")
d = pd.read_csv(os.path.join(EXP, "E0_I0014_residual_heterogeneity", "screen_results.csv"))
print("perm_scheme:\n", d["perm_scheme"].value_counts().to_string())
print("\ncorrect_null_level:\n", d["correct_null_level"].value_counts().to_string())
d["_which"] = match("p_correct_level", ["p_between_block_null", "p_within_block_null",
                                        "p_conservative_both", "p_row_level_NAIVE"], d)
print("\ndecision p traced to:\n", d["_which"].value_counts().to_string())
print("\ncrosstab correct_null_level x which:")
print(pd.crosstab(d["correct_null_level"], d["_which"]).to_string())
print("\nvar_share_between_blocks describe:\n", d["var_share_between_blocks"].describe().to_string())
print("\nnull MEAN columns present?", [c for c in d.columns if "mean" in c.lower()])

# ---------------------------------------------------------------- E0_I0016
hdr("E0_I0016_efficiency_predictors (D085)")
d = pd.read_csv(os.path.join(EXP, "E0_I0016_efficiency_predictors", "screen_results.csv"))
print("entity_level:\n", d["entity_level"].value_counts().to_string())
d["_which"] = match("p_correct_level", ["p_N1_within_entity", "p_N2_entity_swap",
                                        "p_row_level_NAIVE"], d)
print("\ndecision p traced to:\n", d["_which"].value_counts().to_string())
print("\ncrosstab entity_level x which:")
print(pd.crosstab(d["entity_level"], d["_which"]).to_string())
print("\nvar_share_between_entity describe:\n", d["var_share_between_entity"].describe().to_string())
print("\nnull_mean_N1 non-null:", int(d["null_mean_N1"].notna().sum()),
      " null_mean_N2 non-null:", int(d["null_mean_N2"].notna().sum()))
print("dr2 describe:\n", d["dr2"].describe().to_string())

# ---------------------------------------------------------------- E0_I0017
hdr("E0_I0017_shot_quality_efficiency (D087)")
d = pd.read_csv(os.path.join(EXP, "E0_I0017_shot_quality_efficiency", "screen_results.csv"))
print("entity:\n", d["entity"].value_counts().to_string())
print("\nnull MEAN columns present?", [c for c in d.columns if "mean" in c.lower()])
vs = pd.read_csv(os.path.join(EXP, "E0_I0017_shot_quality_efficiency", "var_share_between.csv"))
print("\nvar_share_between.csv head:\n", vs.head(12).to_string())
print("shape", vs.shape, " entities:", vs["entity"].unique()[:8])

# ---------------------------------------------------------------- E0_I0019
hdr("E0_I0019_availability_forecast (D090)")
d = pd.read_csv(os.path.join(EXP, "E0_I0019_availability_forecast",
                              "screen_results_repaired.csv"))
print("scheme_between:\n", d["scheme_between"].value_counts().to_string())
d["_which"] = match("p_familywise", ["p_between", "p_within", "p_row"], d)
print("\nfamilywise p traced to (expect NO_MATCH; it is corrected):\n",
      d["_which"].value_counts().to_string())
print("\nwithin_null_degenerate:\n", d["within_null_degenerate"].value_counts().to_string())
print("\nvar_share_between describe:\n", d["var_share_between"].describe().to_string())
print("\nnullmean_between non-null:", int(d["nullmean_between"].notna().sum()))
print("dr2-like columns?", [c for c in d.columns if "r2" in c.lower() or "dr2" in c.lower()])
gl = pd.read_csv(os.path.join(EXP, "E0_I0019_availability_forecast", "grouping_levels.csv"))
print("\ngrouping_levels.csv cols:", list(gl.columns))
print(gl.head(8).to_string())

# ---------------------------------------------------------------- E0_I0024
hdr("E0_I0024_reb_ast_characterisation (D097)")
d = pd.read_csv(os.path.join(EXP, "E0_I0024_reb_ast_characterisation", "upstream_signals.csv"))
print("level:\n", d["level"].value_counts().to_string())
d["_which"] = match("p_correct_level", ["p_row_level_NAIVE", "p_entity_swap",
                                        "p_cyclic_shift"], d)
print("\ndecision p traced to:\n", d["_which"].value_counts().to_string())
print("\ncrosstab level x which:")
print(pd.crosstab(d["level"], d["_which"]).to_string())
print("\nnull MEAN columns present?", [c for c in d.columns if "mean" in c.lower()])
print("var_share columns?", [c for c in d.columns if "var_share" in c.lower()])

# ---------------------------------------------------------------- E0_I0029
hdr("E0_I0029_freethrow_hurdle (D108)")
d = pd.read_csv(os.path.join(EXP, "E0_I0029_freethrow_hurdle", "screen_results.csv"))
print("level:\n", d["level"].value_counts().to_string())
print("\ncorrect_null_used:\n", d["correct_null_used"].value_counts().to_string())
d["_which"] = match("p_correct_level", ["p_N_ROW", "p_N_CYCLIC", "p_N_PSWAP", "p_N_ENTITY"], d)
print("\ndecision p traced to:\n", d["_which"].value_counts().to_string())
print("\ncrosstab correct_null_used x which:")
print(pd.crosstab(d["correct_null_used"], d["_which"]).to_string())
print("\np_N_CYCLIC_EXCLUDED_no_power:\n",
      d["p_N_CYCLIC_EXCLUDED_no_power"].value_counts(dropna=False).to_string())
print("\nnullmean columns non-null counts:")
for c in [c for c in d.columns if "nullmean" in c]:
    print(f"   {c}: {int(d[c].notna().sum())}")
print("var_share columns?", [c for c in d.columns if "var_share" in c.lower()])
print("\nlevel x correct_null_used:")
print(pd.crosstab(d["level"], d["correct_null_used"]).to_string())

# ---------------------------------------------------------------- E1_I0018
hdr("E1_I0018_teammate_volume_channel (D089)")
d = pd.read_csv(os.path.join(EXP, "E1_I0018_teammate_volume_channel", "screen_results.csv"))
d["_which"] = match("p_correct_level", ["p_N1_within_entity", "p_N2_entity_swap",
                                        "p_row_level_NAIVE"], d)
print("decision p traced to:\n", d["_which"].value_counts().to_string())
print("\nvar_share_between_team_season describe:\n",
      d["var_share_between_team_season"].describe().to_string())
print("\nnull_mean_N1 non-null:", int(d["null_mean_N1"].notna().sum()),
      " null_mean_N2 non-null:", int(d["null_mean_N2"].notna().sum()))
print("level-ish columns?", [c for c in d.columns if "level" in c.lower()])

# ---------------------------------------------------------------- E1_I0023
hdr("E1_I0023_usage_defence_interaction (D098/D099)")
d = pd.read_csv(os.path.join(EXP, "E1_I0023_usage_defence_interaction",
                              "interaction_forecast.csv"))
print("cols with cluster:", [c for c in d.columns if "cluster" in c.lower()])
print("null MEAN columns present?", [c for c in d.columns if "mean" in c.lower()])
print("\nkind:\n", d["kind"].value_counts().to_string())
print("\nstratum:\n", d["stratum"].value_counts().to_string())
print("\nn_clusters_present describe:\n", d["n_clusters_present"].describe().to_string())
