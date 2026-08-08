"""S07 -- build CENSUS.csv: every recorded candidate cell, with LEVEL, POWER and KILL REASON.

Per PREREG section 4. Level is taken ONLY from a source screen's own recorded level column;
it is never inferred from a candidate's name.
"""
import os
import numpy as np
import pandas as pd

pd.set_option("display.width", 300)
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_rows", 400)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, "experiments", "exploration")
OUT = os.path.join(EXP, "E1_I0036_level_artefact_sweep")

FLOOR_1CELL = 0.00102
FLOOR_132 = 0.00235
BEST_LIVE = 0.002057


def hdr(s):
    print("\n" + "=" * 100 + "\n" + s + "\n" + "=" * 100)


# ---------------------------------------------------------------- harvest
# (screen, decision, path, colmap). Explicit -- no name-based discovery.
SPECS = [
    dict(screen="E0_I0014_residual_heterogeneity", decision="D078/D082",
         path="E0_I0014_residual_heterogeneity/screen_results.csv",
         candidate="candidate", target="dependent", level="correct_null_level",
         dr2="delta_r2_plain_unweighted", p_correct="p_correct_level",
         p_fw="p_familywise_whole_screen", n=None, stratum=None, base=None, ceiling=None),
    dict(screen="E0_I0016_efficiency_predictors", decision="D085",
         path="E0_I0016_efficiency_predictors/screen_results.csv",
         candidate="candidate", target="outcome", level="entity_level",
         dr2="dr2", p_correct="p_correct_level", p_fw="p_familywise_maxt",
         n="n", stratum=None, base=None, ceiling=None),
    dict(screen="E0_I0017_shot_quality_efficiency", decision="D087",
         path="E0_I0017_shot_quality_efficiency/screen_results.csv",
         candidate="candidate", target="outcome", level="entity",
         dr2="dR2", p_correct="p_correct_entityswap", p_fw="p_familywise_maxz",
         n="n", stratum=None, base=None, ceiling=None),
    dict(screen="E0_I0019_availability_forecast", decision="D090",
         path="E0_I0019_availability_forecast/screen_results_repaired.csv",
         candidate="candidate", target="dependent", level=None,
         dr2=None, p_correct="p_between", p_fw="p_familywise",
         n="n", stratum=None, base=None, ceiling=None),
    dict(screen="E0_I0024_reb_ast_characterisation", decision="D097",
         path="E0_I0024_reb_ast_characterisation/upstream_signals.csv",
         candidate="candidate", target="target", level="level",
         dr2="dr2", p_correct="p_correct_level", p_fw="fw_p",
         n="n", stratum="stratum", base="base", ceiling="CEILING_dr2_D089form"),
    dict(screen="E0_I0029_freethrow_hurdle", decision="D108",
         path="E0_I0029_freethrow_hurdle/screen_results.csv",
         candidate="candidate", target="target", level="level",
         dr2="dR2", p_correct="p_correct_level", p_fw="p_family_wise",
         n="n", stratum="stratum", base="base", ceiling=None),
    dict(screen="E1_I0018_teammate_volume_channel", decision="D089",
         path="E1_I0018_teammate_volume_channel/screen_results.csv",
         candidate="candidate", target="outcome", level=None,
         dr2="dr2", p_correct="p_correct_level", p_fw="p_familywise_maxt",
         n="n", stratum="stratum", base="base", ceiling=None),
    dict(screen="E1_I0023_usage_defence_interaction", decision="D098/D099",
         path="E1_I0023_usage_defence_interaction/interaction_forecast.csv",
         candidate="defence", target="response", level=None,
         dr2="dr2_a_minus_b", p_correct="p_cluster", p_fw=None,
         n="n_scored", stratum="stratum", base="base", ceiling=None),
]

rows = []
for sp in SPECS:
    p = os.path.join(EXP, *sp["path"].split("/"))
    d = pd.read_csv(p)
    r = pd.DataFrame({
        "screen": sp["screen"], "decision": sp["decision"], "source_file": sp["path"],
        "candidate": d[sp["candidate"]].astype(str),
        "target": d[sp["target"]].astype(str),
    })
    for key, out in [("level", "level_recorded"), ("dr2", "dr2_reported"),
                     ("p_correct", "p_correct_level"), ("p_fw", "p_familywise"),
                     ("n", "n"), ("stratum", "stratum"), ("base", "base"),
                     ("ceiling", "ceiling_recorded")]:
        c = sp.get(key)
        r[out] = d[c].values if (c is not None and c in d.columns) else np.nan
    r["level_recorded"] = r["level_recorded"].astype(object)
    r.loc[r["level_recorded"].isna(), "level_recorded"] = "NOT_RECORDED"
    rows.append(r)
    print(f"  harvested {len(r):5d}  {sp['screen']}")

cen = pd.concat(rows, ignore_index=True)
hdr(f"CENSUS RAW: {len(cen)} cells from {cen['screen'].nunique()} screens")
print(cen["screen"].value_counts().to_string())
print("\nLEVELS AS RECORDED:")
print(cen["level_recorded"].value_counts().to_string())

# ---------------------------------------------------------------- join D103 power
cv = pd.read_csv(os.path.join(EXP, "E1_I0026_detection_floor", "out", "s08_cell_verdicts.csv"))
hdr("D103 POWER TABLE")
print("cells", len(cv), " screens", cv["screen"].nunique())
# D103 keys cells as free-form strings per screen; join at SCREEN level for the summary
# statistics and at CELL level only where the key is reconstructible. Report which.
pw = cv.groupby("screen").agg(
    d103_cells=("cell", "size"),
    d103_mde80_fw_med=("mde80_fw", "median"),
    d103_mde80_percell_med=("mde80_percell", "median"),
    d103_frac_blind_best_lead=("blind_to_best_lead_fw", "mean"),
    d103_K=("family_size_K", "max"),
).reset_index()
print(pw.to_string(index=False))

cen = cen.merge(pw, on="screen", how="left")

# per-cell join where D103's `cell` string contains the candidate token
hdr("PER-CELL POWER JOIN")
joined = 0
cen["mde80_fw"] = np.nan
cen["mde80_percell"] = np.nan
cen["blind_to_best_lead_fw"] = np.nan
for scr, g in cen.groupby("screen"):
    sub = cv[cv["screen"] == scr]
    if len(sub) == 0:
        continue
    # exact-token map: candidate name appears in the D103 cell string
    for i, row in g.iterrows():
        cand = row["candidate"]
        m = sub[sub["cell"].astype(str).str.contains(cand, regex=False, na=False)]
        if len(m):
            cen.at[i, "mde80_fw"] = float(m["mde80_fw"].median())
            cen.at[i, "mde80_percell"] = float(m["mde80_percell"].median())
            cen.at[i, "blind_to_best_lead_fw"] = float(m["blind_to_best_lead_fw"].mean())
            joined += 1
print(f"  per-cell power joined for {joined} / {len(cen)} cells "
      f"({joined / len(cen):.1%}); the rest carry screen-level medians only")
cen["mde80_fw_used"] = cen["mde80_fw"].fillna(cen["d103_mde80_fw_med"])
cen["blind_used"] = cen["blind_to_best_lead_fw"].fillna(cen["d103_frac_blind_best_lead"])

# ---------------------------------------------------------------- kill reason
hdr("KILL REASON (PREREG 4.2, first match wins)")


def kill_reason(r):
    pfw = r["p_familywise"]
    pc = r["p_correct_level"]
    ceil = r["ceiling_recorded"]
    if pd.notna(pfw) and pfw < 0.05:
        return "SURVIVOR"
    if pd.isna(pfw) and pd.notna(pc) and pc < 0.05:
        return "SURVIVOR_PERCELL_ONLY"
    if pd.notna(ceil) and ceil < FLOOR_1CELL:
        return "CEILING"
    b = r["blind_used"]
    if pd.notna(b) and b >= 0.5:
        return "UNINFORMATIVE_NULL"
    return "POWERED_NULL"


cen["kill_reason"] = cen.apply(kill_reason, axis=1)
print(cen["kill_reason"].value_counts().to_string())

# --- DEFECT D-02 CORRECTION, recorded ALONGSIDE the frozen rule, never replacing it ---
# The frozen 4.2 ladder sends a cell with NO D103 power record to POWERED_NULL, which asserts
# power that was never measured.  E0_I0029 (560 cells) post-dates D103 entirely.  The frozen
# label is kept so the preregistered triage selection is unaltered; the corrected label is
# published beside it.
cen["kill_reason_corrected"] = cen["kill_reason"]
noknow = cen["mde80_fw_used"].isna() & (cen["kill_reason"] == "POWERED_NULL")
cen.loc[noknow, "kill_reason_corrected"] = "POWER_NOT_ASSESSED"
print("\nDEFECT D-02 correction: %d cells relabelled POWERED_NULL -> POWER_NOT_ASSESSED"
      % int(noknow.sum()))
print(cen["kill_reason_corrected"].value_counts().to_string())
print("\nby screen:")
print(pd.crosstab(cen["screen"], cen["kill_reason"]).to_string())

# ---------------------------------------------------------------- eligibility
hdr("ELIGIBILITY (PREREG 4.3)")
ROSTER_CONSTANT_LEVELS = {"team_season", "opp_team_season", "team_game", "matchup"}
SUMMABLE_TARGETS = {"y_pts", "y_reb", "y_oreb", "y_dreb", "y_ast", "y_fga", "y_fta", "y_ftm",
                    "pts", "reb", "oreb", "dreb", "ast", "fga", "fta", "ftm",
                    "y_any_fta", "y_fta_pos"}

cen["T1_not_ceiling"] = cen["kill_reason"] != "CEILING"
cen["T2_roster_constant"] = cen["level_recorded"].isin(ROSTER_CONSTANT_LEVELS)
cen["T3_summable_target"] = cen["target"].isin(SUMMABLE_TARGETS)
cen["T4_power_recorded"] = cen["mde80_fw_used"].notna()
cen["ELIGIBLE"] = (cen["T1_not_ceiling"] & cen["T2_roster_constant"]
                   & cen["T3_summable_target"])

for c in ["T1_not_ceiling", "T2_roster_constant", "T3_summable_target", "T4_power_recorded",
          "ELIGIBLE"]:
    print(f"  {c:22s} {int(cen[c].sum()):5d} / {len(cen)}")

print("\nTARGET VALUES SEEN (for T3 audit):")
print(cen["target"].value_counts().to_string())

# ---------------------------------------------------------------- ranking
hdr("RANKING (PREREG 4.4)")
D111_PEN = {"fga": .496, "y_fga": .496, "pts": .273, "y_pts": .273,
            "reb": .157, "y_reb": .157, "oreb": .157, "y_oreb": .157,
            "dreb": .157, "y_dreb": .157, "ast": .110, "y_ast": .110,
            "fta": .073, "y_fta": .073, "y_any_fta": .073, "y_fta_pos": .073,
            "ftm": .066, "y_ftm": .066}
LEVELBONUS = {"opp_team_season": 0.50, "team_season": 0.25}

el = cen[cen["ELIGIBLE"] & cen["kill_reason"].isin(
    ["UNINFORMATIVE_NULL", "POWERED_NULL"])].copy()
print(f"eligible KILLED cells: {len(el)}")
if len(el):
    agg = el.groupby(["candidate", "target", "level_recorded", "screen", "decision"]).agg(
        dr2_max=("dr2_reported", "max"), n_max=("n", "max"),
        p_correct_min=("p_correct_level", "min"), p_fw_min=("p_familywise", "min"),
        mde80=("mde80_fw_used", "median"), cells=("candidate", "size"),
        kill=("kill_reason", lambda s: s.mode().iloc[0]),
    ).reset_index()
    agg["EV"] = (np.log10(agg["dr2_max"].clip(lower=1e-6))
                 + agg["level_recorded"].map(LEVELBONUS).fillna(0.0)
                 + agg["target"].map(D111_PEN).fillna(0.0))
    agg = agg.sort_values(["EV", "n_max"], ascending=[False, False]).reset_index(drop=True)
    print(agg.head(30).to_string())
    agg.to_csv(os.path.join(OUT, "TRIAGE_RANKING.csv"), index=False)
    print("\nwrote TRIAGE_RANKING.csv", agg.shape)

# ---------------------------------------------------------------- write
cols = ["screen", "decision", "source_file", "candidate", "target", "stratum", "base",
        "level_recorded", "n", "dr2_reported", "p_correct_level", "p_familywise",
        "ceiling_recorded", "d103_K", "mde80_fw", "mde80_percell", "mde80_fw_used",
        "blind_to_best_lead_fw", "blind_used", "kill_reason", "kill_reason_corrected",
        "T1_not_ceiling", "T2_roster_constant", "T3_summable_target", "T4_power_recorded",
        "ELIGIBLE"]
cen[cols].to_csv(os.path.join(OUT, "CENSUS.csv"), index=False)
print("\nwrote CENSUS.csv", cen[cols].shape)
