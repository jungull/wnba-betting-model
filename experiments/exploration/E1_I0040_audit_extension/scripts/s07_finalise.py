"""S07 -- Final consolidation of AUDIT_TABLE_EXT.csv.

Fixes and resolutions applied here, each recorded in DEFECTS.md:
  * MY OWN DEFECT: s04 matched E1_I0034 candidates by substring and mis-attached `u_minutes`'s
    variance share to `FREED_minutes`. Replaced with an EXPLICIT map. This is the trap the brief
    named; it caught this screen too, and it is reported rather than quietly corrected.
  * E1_I0030 (12 cells) resolved from UNDETERMINABLE by direct measurement (S05).
  * E1_I0031 (32 cells) resolved to EXPOSED by direct measurement + its own draw archive.
  * E1_I0034 (4 cells) resolved by its own candidate_level_audit.csv, matched exactly.
  * E1_I0036's 2 N_CYCLIC rows are a RE-MEASUREMENT of a D097 census cell already counted among
    E1_I0038's 83. Reclassified EXPOSED_ALREADY_COUNTED and excluded from this screen's total so
    the programme-wide figure does not double-count.
"""
import os, json
import numpy as np
import pandas as pd

EXPL = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALPHA, THR = 0.05, 0.50
D103_SINGLE_CELL_FLOOR = 0.00102   # E1_I0038 PREREG 5.1, unchanged

AT = pd.read_csv(os.path.join(HERE, "AUDIT_TABLE_EXT.csv"))
M = pd.read_csv(os.path.join(HERE, "MEASURED_VARIANCE_SHARES.csv"))
def share(sc, c):
    r = M[(M.screen == sc) & (M.candidate == c)]
    return float(r.var_share_between.iloc[0]) if len(r) else np.nan

def setrow(mask, **kw):
    for k, v in kw.items():
        AT.loc[mask, k] = v

# ------------------------------------------------------------------ E1_I0030 (measured)
m = (AT.screen == "E1_I0030_home_advantage_accounting") & \
    (AT.source_file.str.endswith("heterogeneity.csv"))
v = share("E1_I0030_home_advantage_accounting", "is_home")
setrow(m, var_share_between=v, var_share_source="COMPUTED_ON_FROZEN_FRAME",
       EXPOSURE="NOT_EXPOSED",
       exposure_reason="within-player cyclic null; MEASURED between-player variance share of "
                       "is_home = %.6f << 0.50 on E1_I0030/_player_frame.parquet (21,462 rows). "
                       "The null is matched to the candidate." % v,
       exposure_confidence=1.0)

ARM = {"eastbound": "eastbound", "westbound": "westbound", "same_zone_travel": "same_zone_travel"}
for arm, col in ARM.items():
    vv = share("E1_I0030_home_advantage_accounting", col)
    mm = (AT.source_file.str.endswith("travel_directional.csv")) & (AT.candidate == arm)
    setrow(mm, var_share_between=vv, var_share_source="COMPUTED_ON_FROZEN_FRAME",
           EXPOSURE="NOT_EXPOSED",
           exposure_reason="within-team-season cyclic null; MEASURED between-team-season variance "
                           "share of %s = %.6f << 0.50 on E1_I0030/_team_frame.parquet "
                           "(1,940 rows)." % (col, vv),
           exposure_confidence=1.0)

# ------------------------------------------------------------------ E1_I0034 (EXPLICIT map)
EXPLICIT_I0034 = {
    # primary_cells 'cell' -> (candidate_level_audit row, share column, null entity)
    "P02_TILT_minutes":           ("uz_minutes (P02/P05 candidate)", "frac_between_teamgame", "team_game"),
    "P02_TILT_fga":               ("uz_fga",                          "frac_between_teamgame", "team_game"),
    "P02_TILT_pts":               ("uz_pts",                          "frac_between_teamgame", "team_game"),
    "P05_POSITION_MATCH_minutes": ("u*posmatch (P05 candidate)",      "frac_between_teamgame", "team_game"),
    # P01's candidate FREED_* has NO row in candidate_level_audit.csv and no share at the null's
    # own entity (season). It stays UNDETERMINABLE. s04's substring match to `u_minutes` was WRONG.
}
cla = pd.read_csv(os.path.join(EXPL, "E1_I0034_redistribution", "candidate_level_audit.csv"))
cla_ix = cla.set_index("candidate")
for cell, (row, col, ent) in EXPLICIT_I0034.items():
    if row not in cla_ix.index:
        print("!! candidate_level_audit has no row named %r" % row)
        continue
    vv = float(cla_ix.loc[row, col])
    mm = (AT.screen == "E1_I0034_redistribution") & (AT.base == cell)
    E_ = "EXPOSED" if vv >= THR else "NOT_EXPOSED"
    setrow(mm, var_share_between=vv, var_share_source="TABLE_MEASURED_EXPLICIT_MAP",
           EXPOSURE=E_,
           exposure_reason="within-%s shuffle; MEASURED between-%s share of %s = %.4f %s 0.50 "
                           "(E1_I0034's own candidate_level_audit.csv, exact row match)"
                           % (ent, ent, row, vv, ">=" if vv >= THR else "<"),
           exposure_confidence=1.0)
mm = (AT.screen == "E1_I0034_redistribution") & (AT.base.astype(str).str.startswith("P01_LEAKAGE"))
setrow(mm, var_share_between=np.nan, var_share_source="NOT_MEASURED_AT_NULL_ENTITY",
       EXPOSURE="UNDETERMINABLE",
       exposure_reason="within-season permutation of FREED_*; candidate_level_audit.csv carries no "
                       "row for FREED_* and no share at the null's own entity (season). s04 of this "
                       "screen mis-matched it to `u_minutes` by substring; the match is withdrawn "
                       "and the cell is left UNDETERMINABLE rather than guessed. See DEFECTS D-01.",
       exposure_confidence=np.nan)

# ------------------------------------------------------------------ E1_I0031 (measured + own draws)
det = pd.read_csv(os.path.join(HERE, "E1_I0031_EXPOSURE_DETAIL.csv"))
moments = pd.read_csv(os.path.join(HERE, "E1_I0031_RECOVERED_NULL_MOMENTS.csv"))
# the draw archive carries NO stratum key; s06b proved by exact null_p95 match that it is the
# wf_eval_2023_24 arm ONLY. Attach moments to that arm and to nothing else.
mom = moments[moments.test == "pm_dr2"].set_index(["target", "over", "added"])
for _, r in det.iterrows():
    mm = ((AT.screen == "E1_I0031_rapm_as_prior") &
          (AT.source_file.str.endswith("plusminus_separate.csv")) &
          (AT.candidate == r["added"]) & (AT.target == r["target"]) &
          (AT.stratum == r["stratum"]) & (AT.base == r["over"]))
    if not mm.any():
        continue
    within = bool(r["within"])
    vv = float(r["vsb_max_component"]) if pd.notna(r["vsb_max_component"]) else np.nan
    if within and np.isfinite(vv):
        E_ = "EXPOSED" if vv >= THR else "NOT_EXPOSED"
        why = ("within-player_season cyclic null; MEASURED max between-player_season variance "
               "share over the bundle's own component columns = %.4f %s 0.50 "
               "(computed on E1_I0031/analysis_frame.parquet, 13,879 rows). A cyclic shift "
               "preserves each player-season's mean exactly, so that share of the candidate "
               "survives the null untouched." % (vv, ">=" if vv >= THR else "<"))
        if r["added"] == "pm_all":
            why += (" DECISIVE: pm_all contains pm_prev_season_imp, which the screen itself asserts "
                    "is CONSTANT within player-season (s06_plusminus.py:49) -- a cyclic shift of a "
                    "constant is the identity, so the null cannot move that component at all.")
    else:
        E_, why = ("NOT_EXPOSED",
                   "decision null is player_season_relabel -- a between-entity null matched to a "
                   "candidate that is constant within player-season (measured share 1.000)")
    if r["stratum"] == "wf_eval_2023_24":
        nm, nsd, nms = r.get("null_mean"), r.get("null_sd"), "RECOVERED_FROM_OWN_DRAW_ARCHIVE"
    else:
        nm, nsd, nms = np.nan, np.nan, "UNRECOVERABLE__DRAW_ARCHIVE_OMITS_THE_STRATUM_KEY"
    setrow(mm, var_share_between=vv, var_share_source="COMPUTED_ON_FROZEN_FRAME",
           EXPOSURE=E_, exposure_reason=why, exposure_confidence=1.0,
           null_mean=nm, null_sd=nsd, null_mean_source=nms)

# ------------------------------------------------------------------ E1_I0036: already counted
mm = (AT.screen == "E1_I0036_level_artefact_sweep") & (AT.EXPOSURE == "UNDETERMINABLE")
setrow(mm, EXPOSURE="EXPOSED_ALREADY_COUNTED_IN_E1_I0038",
       var_share_source="ESTABLISHED_BY_E1_I0036_ITSELF",
       exposure_reason="N_CYCLIC on D097's R08_player_ra_share cell. E1_I0036 measured the null's "
                       "power on the BETWEEN component at 0.00 and flagged it blind; E1_I0038 "
                       "already counted this cell among its 83 exposed. It is a RE-MEASUREMENT of "
                       "a census cell, not a new cell, and is excluded from this screen's total so "
                       "the programme-wide figure does not double-count.",
       exposure_confidence=1.0)

# ------------------------------------------------------------------ recompute the flags
o, m_, s = AT.observed_stat, AT.null_mean, AT.null_sd
AT["flag_null_mean_gt_observed"] = np.where(m_.notna() & o.notna(), m_ > o, None)
AT["z_obs_vs_null"] = np.where(m_.notna() & o.notna() & s.notna() & (s > 0), (o - m_) / s, np.nan)
AT["flag_z_lt_neg1"] = np.where(AT.z_obs_vs_null.notna(), AT.z_obs_vs_null < -1.0, None)

# ------------------------------------------------------------------ E1_I0021 mechanical-rule column
# The frozen E1_I0038 rule applied MECHANICALLY, i.e. ignoring the estimand, so a reader can see
# exactly what the unmodified rule would have said and how much of the answer rests on the
# scope condition this screen adds.
i21 = AT.screen == "E1_I0021_heterogeneity_diagnostic"
CAND_SHARE = {c: share("E1_I0021_heterogeneity_diagnostic", c)
              for c in M[M.screen == "E1_I0021_heterogeneity_diagnostic"].candidate.unique()}
CAND_SHARE["refA_ppm_floor"] = CAND_SHARE.get("refA_ppm", np.nan)   # same series, floor-filtered
AT["mech_var_share_between"] = np.nan
AT.loc[i21, "mech_var_share_between"] = AT.loc[i21, "candidate"].map(CAND_SHARE)
AT["EXPOSURE_MECHANICAL_RULE"] = AT["EXPOSURE"]
mechmask = i21 & (AT.null_class == "WITHIN_ENTITY") & AT.mech_var_share_between.notna()
AT.loc[mechmask, "EXPOSURE_MECHANICAL_RULE"] = np.where(
    AT.loc[mechmask, "mech_var_share_between"] >= THR, "EXPOSED", "NOT_EXPOSED")

AT["over_d103_single_cell_floor"] = AT.observed_stat.abs() > D103_SINGLE_CELL_FLOOR
AT.to_csv(os.path.join(HERE, "AUDIT_TABLE_EXT.csv"), index=False)

# ================================================================== REPORT
K = AT[AT.is_kill]
print("=" * 78)
print("AUDIT_TABLE_EXT -- FINAL")
print("=" * 78)
print("rows %d over %d screens with decided cells; KILLS %d" % (len(AT), AT.screen.nunique(), len(K)))
print("\nnull_class over KILLS:\n", K.null_class.value_counts().to_string())
print("\nEXPOSURE over KILLS:\n", K.EXPOSURE.value_counts().to_string())
print("\nby screen (kills):")
print(K.groupby(["screen", "EXPOSURE"]).size().unstack(fill_value=0).to_string())
print("\nCEILING kills found in the thirty:", int(AT.is_ceiling.sum()))
print("\nnull mean available:")
print(AT.null_mean_source.value_counts().to_string())
print("\nz computable on %d cells; z<-1.0 trips on %d; bare flag trips on %d"
      % (int(AT.z_obs_vs_null.notna().sum()), int((AT.flag_z_lt_neg1 == True).sum()),
         int((AT.flag_null_mean_gt_observed == True).sum())))
EX = K[K.EXPOSURE == "EXPOSED"]
print("\n--- EXPOSED KILLS (%d) ---" % len(EX))
print(EX[["screen", "candidate", "target", "stratum", "base", "n", "observed_stat", "p_decision",
          "null_mean", "z_obs_vs_null", "var_share_between",
          "over_d103_single_cell_floor"]].to_string())
print("\nE1_I0021 under the MECHANICAL rule vs as adjudicated:")
print(pd.crosstab(AT.loc[i21 & AT.is_kill, "EXPOSURE_MECHANICAL_RULE"],
                  AT.loc[i21 & AT.is_kill, "EXPOSURE"]).to_string())

summary = dict(
    rows=int(len(AT)), kills=int(len(K)),
    exposed=int((K.EXPOSURE == "EXPOSED").sum()),
    not_exposed=int((K.EXPOSURE == "NOT_EXPOSED").sum()),
    undeterminable=int((K.EXPOSURE == "UNDETERMINABLE").sum()),
    already_counted=int((K.EXPOSURE == "EXPOSED_ALREADY_COUNTED_IN_E1_I0038").sum()),
    ceiling=int(AT.is_ceiling.sum()),
    z_computable=int(AT.z_obs_vs_null.notna().sum()),
    flag_z_trips=int((AT.flag_z_lt_neg1 == True).sum()),
    flag_bare_trips=int((AT.flag_null_mean_gt_observed == True).sum()),
    i21_mechanical_exposed=int((AT.loc[i21 & AT.is_kill, "EXPOSURE_MECHANICAL_RULE"] == "EXPOSED").sum()),
)
with open(os.path.join(HERE, "scripts", "_s07.json"), "w") as fh:
    json.dump(summary, fh, indent=2)
print("\n", json.dumps(summary, indent=2))
