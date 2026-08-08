"""S00 -- Reproduce prior-screen anchor numbers EXACTLY before generating anything new.

Anchors (from E1_I0038/VERDICT.md and E1_I0036):
  A1  213 killed cells at player_season + 337 at opp_team_season = 550    (D115's level count)
  A2  dR2 = 0.0064881160 on exactly 13784 rows (D097 R08_player_ra_share -> y_oreb, B_COMPLETE)
  A3  213 arithmetic-ceiling kills (E1_I0036 verdict / E1_I0038 CEILING_EXCLUSIONS)
  A4  E1_I0038: 1999 audit rows, 83 EXPOSED, 0 UNDETERMINABLE, 846 null_mean recorded by screen,
      117 destroyed by standardisation.
Read-only. Writes only into this screen's directory.
"""
import os, json
import pandas as pd

EXPL = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

out = {}

at = pd.read_csv(os.path.join(EXPL, "E1_I0038_within_entity_null_audit", "AUDIT_TABLE.csv"))
cen = pd.read_csv(os.path.join(EXPL, "E1_I0036_level_artefact_sweep", "CENSUS.csv"))

print("AUDIT_TABLE rows:", len(at), " CENSUS rows:", len(cen))
out["audit_table_rows"] = int(len(at))
out["census_rows"] = int(len(cen))

# ---- A4: E1_I0038 headline counts -------------------------------------------------
exp = at["EXPOSURE"].value_counts().to_dict()
print("EXPOSURE tally:", exp)
out["A4_exposure_tally"] = {k: int(v) for k, v in exp.items()}
out["A4_null_mean_recorded_by_screen"] = int(at["null_mean_recorded_by_screen"].sum())

# ---- A1: 550 = 213 player_season + 337 opp_team_season -----------------------------
# D115's claim is about KILLED cells sitting at exposed entity levels.
kills = at[at["is_kill"] == True]
lv = kills["candidate_level_recorded"].value_counts()
print("\nkilled-cell candidate levels:\n", lv.head(20))
out["A1_killed_by_candidate_level"] = {str(k): int(v) for k, v in lv.items()}

# also with survivors (the 299/427 anchor)
lv_all = at["candidate_level_recorded"].value_counts()
out["A1_all_by_candidate_level"] = {str(k): int(v) for k, v in lv_all.items()}
print("\nALL rows candidate levels:\n", lv_all.head(20))

# ---- A3: ceiling kills -------------------------------------------------------------
n_ceiling = int((at["is_ceiling"] == True).sum())
n_ceiling_excl = int((at["EXPOSURE"] == "CEILING_EXCLUDED").sum())
print("\nis_ceiling:", n_ceiling, " EXPOSURE==CEILING_EXCLUDED:", n_ceiling_excl)
out["A3_is_ceiling"] = n_ceiling
out["A3_ceiling_excluded"] = n_ceiling_excl

# ---- A2: the dR2 anchor ------------------------------------------------------------
m = at[(at["screen"].str.contains("E0_I0024")) &
       (at["candidate"].astype(str).str.contains("R08_player_ra_share")) &
       (at["target"].astype(str) == "y_oreb")]
cols = ["candidate", "target", "base", "n", "dr2_reported", "observed_stat", "null_mean", "p_decision"]
print("\nA2 candidate rows:\n", m[cols].to_string())
out["A2_rows"] = m[cols].astype(object).where(pd.notnull(m[cols]), None).to_dict("records")

with open(os.path.join(HERE, "scripts", "_s00.json"), "w") as f:
    json.dump(out, f, indent=2, default=str)
print("\nwrote _s00.json")
