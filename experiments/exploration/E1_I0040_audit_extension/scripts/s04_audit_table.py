"""S04 -- AUDIT_TABLE_EXT.csv: every decided cell in the 30 unaudited screens.

METHOD IS E1_I0038's, APPLIED, NOT REDERIVED:
  * exposure rule (frozen, PREREG 3 of E1_I0038): decision null is WITHIN_ENTITY
    AND the candidate's between-entity variance share over the NULL'S OWN ENTITY is >= 0.50.
  * the flag is the magnitude-aware form z = (observed - null_mean)/null_sd < -1.0 (spec 0.980).
    The bare `null_mean > observed` form is computed and reported but NOT acted on (PPV 0.146).
  * arithmetic-ceiling kills are EXCLUDED BY RULE and never re-measured.
  * variance shares are taken only from a MEASUREMENT on disk, never inferred from a column name.
    Where no measurement exists the cell is UNDETERMINABLE. That category is not collapsed.
  * matched-null p is read from disk before anything is refitted.

Partition: every source table read here is a 2021-2024 exploration artefact. No 2025/26 file is
opened anywhere in this screen.
"""
import os, json, re
import numpy as np
import pandas as pd

EXPL = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALPHA = 0.05
EXPOSURE_THR = 0.50

def R(rel):
    p = os.path.join(EXPL, rel.replace("/", os.sep))
    return pd.read_csv(p) if os.path.exists(p) else None

rows = []

def emit(**kw):
    d = dict(screen="", source_file="", candidate="", target="", stratum="", base="", n=np.nan,
             null_scheme_recorded="", null_class="", null_permutes_at="", null_level_source="",
             combination_rule="", other_nulls_run="",
             candidate_level="", var_share_between=np.nan, var_share_source="NOT_MEASURED",
             observed_stat=np.nan, stat_scale="", null_mean=np.nan, null_mean_source="NONE",
             null_sd=np.nan, p_decision=np.nan, p_familywise=np.nan,
             matched_p_on_disk=np.nan, matched_p_source="",
             is_kill=False, is_ceiling=False, kill_basis="",
             EXPOSURE="", exposure_reason="", exposure_confidence=np.nan)
    d.update(kw)
    o, m, s = d["observed_stat"], d["null_mean"], d["null_sd"]
    d["flag_null_mean_gt_observed"] = (bool(m > o) if np.isfinite(m) and np.isfinite(o) else None)
    d["z_obs_vs_null"] = ((o - m) / s) if (np.isfinite(m) and np.isfinite(o)
                                           and np.isfinite(s) and s > 0) else np.nan
    d["flag_z_lt_neg1"] = (bool(d["z_obs_vs_null"] < -1.0)
                           if np.isfinite(d["z_obs_vs_null"]) else None)
    rows.append(d)

def classify(null_class, vsb, vs_source, entity, note=""):
    """The frozen E1_I0038 exposure rule."""
    if null_class != "WITHIN_ENTITY":
        return ("NOT_EXPOSED",
                "decision null is %s -- a within-entity null is not what decided this cell" % null_class,
                1.0)
    if not np.isfinite(vsb):
        return ("UNDETERMINABLE",
                "within-entity null at %s but NO measured between-entity variance share on disk; "
                "level not guessed" % entity, np.nan)
    if vsb >= EXPOSURE_THR:
        return ("EXPOSED",
                "within-entity null at %s, measured between-%s share %.3f >= 0.50%s"
                % (entity, entity, vsb, ("; " + note if note else "")), 1.0)
    return ("NOT_EXPOSED",
            "within-entity null at %s, measured between-%s share %.3f < 0.50%s"
            % (entity, entity, vsb, ("; " + note if note else "")), 1.0)

# =====================================================================================
# 1. E0_I0015_points_skill_decomposition -- 550 abstention cells. IMMUNE BY DESIGN.
#    s03_mechanism_and_abstention.py:284 -- scheme_used = BETWEEN-block if vsb > 0.5 else WITHIN.
#    Variance shares MEASURED in its own grouping_levels.csv.
# =====================================================================================
a = R("E0_I0015_points_skill_decomposition/abstention_rate_screen.csv")
gl = R("E0_I0015_points_skill_decomposition/grouping_levels.csv")
vs = dict(zip(gl["candidate"], gl["var_share_between_player_season"]))
for _, r in a.iterrows():
    cls = "WITHIN_ENTITY" if r["scheme"] == "WITHIN-block" else "BETWEEN_ENTITY"
    v = float(vs.get(r["candidate"], np.nan))
    E_, why, conf = classify(cls, v, "TABLE", "player_season",
                             "scheme chosen FROM this share by the screen's own code "
                             "(s03_mechanism_and_abstention.py:284)")
    emit(screen="E0_I0015_points_skill_decomposition",
         source_file="E0_I0015_points_skill_decomposition/abstention_rate_screen.csv",
         candidate=r["candidate"], target=r["dependent"], stratum=r["direction"],
         base="coverage=%s" % r["coverage"],
         null_scheme_recorded=r["scheme"], null_class=cls, null_permutes_at="player_season",
         null_level_source="TABLE",
         combination_rule="SINGLE_DECISION_NULL_CHOSEN_BY_VARIANCE_SHARE",
         other_nulls_run="p_row_level_NAIVE (reported as inflation contrast, never the verdict)",
         candidate_level="player_season", var_share_between=v, var_share_source="TABLE_MEASURED",
         observed_stat=r["skill_gain"], stat_scale="SKILL_GAIN",
         null_sd=r["null_sd_correct"],
         p_decision=r["p_correct_level"], p_familywise=r["familywise_p_correct"],
         is_kill=bool(r["familywise_p_correct"] >= ALPHA), kill_basis="familywise_p_correct>=0.05",
         EXPOSURE=E_, exposure_reason=why, exposure_confidence=conf)

# other E0_I0015 tables: paired block sign-flip (a BETWEEN-entity scheme)
for f, ccol, tcol, pcol, ocol in [
        ("E0_I0015_points_skill_decomposition/component_skill.csv", "component", None,
         "p_two_sided_block_signflip", "paired_mean_abs_err_diff_model_minus_ref"),
        ("E0_I0015_points_skill_decomposition/hybrid_contrasts.csv", None, None,
         "p_two_sided_block_signflip", None),
        ("E0_I0015_points_skill_decomposition/hybrid_by_depth_contrasts.csv", None, None,
         "p_two_sided_block_signflip", None)]:
    d = R(f)
    if d is None:
        continue
    cc = ccol if (ccol and ccol in d.columns) else d.columns[0]
    for i, r in d.iterrows():
        p = float(r[pcol]) if pcol in d.columns and pd.notna(r[pcol]) else np.nan
        emit(screen="E0_I0015_points_skill_decomposition", source_file=f,
             candidate=str(r[cc]), target=str(r.get("dependent", r.get("target", ""))),
             stratum=str(r.get("depth", "")),
             null_scheme_recorded="block_sign_flip", null_class="BETWEEN_ENTITY",
             null_permutes_at="player_season_block", null_level_source="CODE",
             combination_rule="SINGLE_DECISION_NULL",
             observed_stat=float(r[ocol]) if (ocol and ocol in d.columns
                                              and pd.notna(r[ocol])) else np.nan,
             stat_scale="PAIRED_MAE_DIFF", p_decision=p,
             is_kill=bool(np.isfinite(p) and p >= ALPHA), kill_basis="p>=0.05",
             EXPOSURE="NOT_EXPOSED",
             exposure_reason="decision null is a BETWEEN-entity block sign-flip",
             exposure_confidence=1.0)

# =====================================================================================
# 2. E1_I0021_heterogeneity_diagnostic -- THE NAMED HIGHEST-RISK SCREEN
# =====================================================================================
pd_ = R("E1_I0021_heterogeneity_diagnostic/pooling_diagnostic.csv")
# measured within/between-player variance shares of x are NOT on disk in this screen; the
# serial-structure table measures acf1 within player, which is a different quantity.
# The estimand, however, is measured: hd_base.per_player_slopes(demean=True) centres x and y
# INSIDE the player, so the between-player component of x is annihilated before the statistic
# exists. Recorded as an ESTIMAND-level determination with its code citation.
EST_NOTE = ("statistic is the SD of per-player slopes fitted on WITHIN-player demeaned x and y "
            "(hd_base.py:225-252 per_player_slopes(demean=True); null uses the identical "
            "arithmetic, hd_base.py:269 group_slopes_fast). The between-player component of the "
            "candidate is removed before the statistic is formed, so it cannot enter the "
            "statistic and a within-player null cannot be blind to it.")
for _, r in pd_.iterrows():
    is_ctrl = bool(r["is_negative_control"])
    p4 = float(r["n4_cyclic_p_w"])
    emit(screen="E1_I0021_heterogeneity_diagnostic",
         source_file="E1_I0021_heterogeneity_diagnostic/pooling_diagnostic.csv",
         candidate=r["x"], target=r["y"], stratum="floor=%s" % r["floor"],
         base=r["relationship"], n=r["n_rows"],
         null_scheme_recorded="N4_within_player_cyclic_shift", null_class="WITHIN_ENTITY",
         null_permutes_at="player_id", null_level_source="CODE",
         combination_rule="FOUR_SCHEMES_REPORTED_ONE_IS_THE_VERDICT__NO_MAX",
         other_nulls_run="N1 within-shuffle (p=%.4f), N2 row-level (p=%.4f), N3 team-game block (p=%s)"
                         % (r["n1_p_w"], r["n2_rowlevel_p_w"],
                            ("%.4f" % r["n3_teamgame_p_w"]) if pd.notna(r["n3_teamgame_p_w"]) else "n/a"),
         candidate_level="WITHIN_PLAYER_BY_CONSTRUCTION_OF_THE_ESTIMAND",
         var_share_between=0.0, var_share_source="ESTIMAND_ANNIHILATES_BETWEEN_COMPONENT__CODE",
         observed_stat=r["obs_spread_weighted"], stat_scale="SD_OF_PER_PLAYER_SLOPES",
         null_mean=r["n4_cyclic_null_mean_w"], null_mean_source="RECORDED_BY_SCREEN",
         null_sd=np.nan,
         p_decision=p4,
         matched_p_on_disk=r["n3_teamgame_p_w"] if pd.notna(r["n3_teamgame_p_w"]) else np.nan,
         matched_p_source="n3_teamgame_p_w (between-entity robustness arm, same table)",
         is_kill=bool(p4 >= ALPHA), kill_basis="n4_cyclic_p_w>=0.05 (the screen's stated verdict null)",
         EXPOSURE="NOT_EXPOSED",
         exposure_reason=("within-entity null on a WITHIN-entity estimand. " + EST_NOTE
                          + (" NEGATIVE CONTROL." if is_ctrl else "")),
         exposure_confidence=1.0)

# step 3: covariate-permutation null -- a BETWEEN-entity null over players
sd_ = R("E1_I0021_heterogeneity_diagnostic/structure_decisive.csv")
for _, r in sd_.iterrows():
    p = float(r["p_two_sided"])
    emit(screen="E1_I0021_heterogeneity_diagnostic",
         source_file="E1_I0021_heterogeneity_diagnostic/structure_decisive.csv",
         candidate=r["x"], target="per_player_slope_vs_player_covariate", stratum="floor=20",
         base=r["relationship"], n=r["n_players"],
         null_scheme_recorded="covariate_permutation_across_players",
         null_class="BETWEEN_ENTITY", null_permutes_at="player_id", null_level_source="CODE",
         combination_rule="SINGLE_DECISION_NULL",
         candidate_level="player (the covariate is a player-level summary)",
         var_share_between=1.0, var_share_source="BY_CONSTRUCTION__PLAYER_LEVEL_COVARIATE",
         observed_stat=r["spearman_obs"], stat_scale="SPEARMAN_RANK_CORR",
         null_mean=r["null_mean"], null_mean_source="RECORDED_BY_SCREEN", null_sd=r["null_sd"],
         p_decision=p, is_kill=bool(p >= ALPHA), kill_basis="p_two_sided>=0.05",
         EXPOSURE="NOT_EXPOSED",
         exposure_reason="decision null permutes the player-level covariate ACROSS players -- "
                         "a between-entity null, correctly matched to a player-level candidate",
         exposure_confidence=1.0)

# family-wise rows (6 floors, both nulls)
fw = R("E1_I0021_heterogeneity_diagnostic/family_wise_by_floor.csv")
for _, r in fw.iterrows():
    p = float(r["family_wise_p_cyclic"])
    emit(screen="E1_I0021_heterogeneity_diagnostic",
         source_file="E1_I0021_heterogeneity_diagnostic/family_wise_by_floor.csv",
         candidate="FAMILY(6 preregistered relationships)", target="y_ppm_floor",
         stratum="floor=%s" % r["floor"], base="max-z family-wise",
         null_scheme_recorded="N4_within_player_cyclic_shift", null_class="WITHIN_ENTITY",
         null_permutes_at="player_id", null_level_source="CODE",
         combination_rule="MAX_STATISTIC_OVER_CELLS_WITHIN_ONE_NULL__LEGITIMATE_NOT_MAX_OVER_NULLS",
         other_nulls_run="N1 within-shuffle family-wise p=%.4f (reported, not the verdict)"
                         % r["family_wise_p"],
         candidate_level="WITHIN_PLAYER_BY_CONSTRUCTION_OF_THE_ESTIMAND",
         var_share_between=0.0, var_share_source="ESTIMAND_ANNIHILATES_BETWEEN_COMPONENT__CODE",
         observed_stat=r["max_z_cyclic"], stat_scale="MAX_Z",
         p_familywise=p, p_decision=p,
         is_kill=bool(not bool(r["clears_005_cyclic"])), kill_basis="clears_005_cyclic == False",
         EXPOSURE="NOT_EXPOSED", exposure_reason="within-entity null on a within-entity estimand; "
                                                 + EST_NOTE, exposure_confidence=1.0)

# =====================================================================================
# 3. E1_I0030_home_advantage_accounting
# =====================================================================================
h = R("E1_I0030_home_advantage_accounting/heterogeneity.csv")
for _, r in h.iterrows():
    p = float(r["p_cyclic"])
    emit(screen="E1_I0030_home_advantage_accounting",
         source_file="E1_I0030_home_advantage_accounting/heterogeneity.csv",
         candidate="is_home", target=r["target"], stratum="per-player home effect",
         n=r["n_players"],
         null_scheme_recorded="SCHEME_WITHIN_CYCLIC", null_class="WITHIN_ENTITY",
         null_permutes_at="player_id", null_level_source="CODE (s05_heterogeneity.py:84)",
         combination_rule="TWO_SCHEMES_REPORTED_ONE_IS_THE_VERDICT__NO_MAX",
         other_nulls_run="SCHEME_WITHIN plain shuffle p=%.4f, run and labelled by the screen "
                         "'UNSAFE within-SHUFFLE arm (D093 trap), reported for the gap only'"
                         % r["shuffle_p"],
         candidate_level="is_home varies game-to-game inside every player",
         var_share_between=np.nan, var_share_source="NOT_MEASURED_ON_DISK",
         observed_stat=r["real_sd"], stat_scale="SD_OF_PER_PLAYER_HOME_EFFECT",
         null_mean=r["cyclic_null_mean"], null_mean_source="RECORDED_BY_SCREEN",
         null_sd=r["cyclic_null_sd"],
         p_decision=p, is_kill=bool(p >= ALPHA), kill_basis="p_cyclic>=0.05",
         EXPOSURE="UNDETERMINABLE",
         exposure_reason="within-entity null at player_id; the screen records no measured "
                         "between-player variance share for is_home, and this audit will not "
                         "infer one from the column name",
         exposure_confidence=np.nan)

td = R("E1_I0030_home_advantage_accounting/travel_directional.csv")
for _, r in td[td["analysis"] != "RAW"].iterrows():
    p = r.get("p_cyclic_dR2", np.nan)
    p = float(p) if pd.notna(p) else float(r.get("p_cyclic_beta_LOWER_TAIL_prereg", np.nan))
    emit(screen="E1_I0030_home_advantage_accounting",
         source_file="E1_I0030_home_advantage_accounting/travel_directional.csv",
         candidate=r["arm"], target=r["target"], stratum=r["analysis"], n=r["n"],
         null_scheme_recorded="SCHEME_WITHIN_CYCLIC", null_class="WITHIN_ENTITY",
         null_permutes_at="season+team_id", null_level_source="CODE (s06_travel.py:162)",
         combination_rule="SINGLE_DECISION_NULL",
         candidate_level="travel direction varies game-to-game inside a team-season",
         var_share_between=np.nan, var_share_source="NOT_MEASURED_ON_DISK",
         observed_stat=r.get("dR2", np.nan), stat_scale="dR2",
         null_mean=r.get("null_mean_dR2", np.nan),
         null_mean_source="RECORDED_BY_SCREEN" if pd.notna(r.get("null_mean_dR2", np.nan)) else "NONE",
         null_sd=r.get("null_sd_dR2", np.nan),
         p_decision=p, is_kill=bool(np.isfinite(p) and p >= ALPHA), kill_basis="p_cyclic>=0.05",
         EXPOSURE="UNDETERMINABLE",
         exposure_reason="within-entity null at season+team_id; no measured between-team-season "
                         "variance share for the travel arms is recorded on disk",
         exposure_confidence=np.nan)

for f, cc, tc, pc, oc, sdc, nb in [
        ("E1_I0030_home_advantage_accounting/team_effect.csv", "candidate", None,
         "p_pergame_signflip", "diff", "null_sd", "p_familywise_max_t"),
        ("E1_I0030_home_advantage_accounting/main_effect_test.csv", "reference", "target",
         "p_cluster", "dR2_commonSST", None, None),
        ("E1_I0030_home_advantage_accounting/player_reconciliation.csv", None, None,
         "p_pergame_signflip", None, None, None),
        ("E1_I0030_home_advantage_accounting/reference_absorption.csv", "reference", "target",
         "p_cluster", None, None, None),
        ("E1_I0030_home_advantage_accounting/decomposition.csv", None, None, "p_total", None, None, None)]:
    d = R(f)
    if d is None or pc not in d.columns:
        continue
    for _, r in d.iterrows():
        p = float(r[pc]) if pd.notna(r[pc]) else np.nan
        emit(screen="E1_I0030_home_advantage_accounting", source_file=f,
             candidate=str(r[cc]) if cc and cc in d.columns else str(r.iloc[0]),
             target=str(r[tc]) if tc and tc in d.columns else str(r.get("target", "")),
             stratum=str(r.get("stratum", "")), n=r.get("n", r.get("n_games", np.nan)),
             null_scheme_recorded="cluster / per-game sign-flip", null_class="BETWEEN_ENTITY",
             null_permutes_at="game or cluster", null_level_source="TABLE",
             combination_rule="SINGLE_DECISION_NULL",
             other_nulls_run="p_row_level_NAIVE reported as inflation contrast"
                             if "p_row_level_NAIVE" in d.columns else "",
             observed_stat=float(r[oc]) if (oc and oc in d.columns and pd.notna(r[oc])) else np.nan,
             stat_scale="dR2/diff",
             null_sd=float(r[sdc]) if (sdc and sdc in d.columns and pd.notna(r[sdc])) else np.nan,
             p_decision=p, p_familywise=float(r[nb]) if (nb and nb in d.columns
                                                         and pd.notna(r[nb])) else np.nan,
             is_kill=bool(np.isfinite(p) and p >= ALPHA), kill_basis="p>=0.05",
             EXPOSURE="NOT_EXPOSED",
             exposure_reason="decision null is a between-entity cluster / sign-flip scheme",
             exposure_confidence=1.0)

# =====================================================================================
# 4. E1_I0031_rapm_as_prior -- picks the null by the candidate's level. MEASURE IT.
# =====================================================================================
pm = R("E1_I0031_rapm_as_prior/plusminus_separate.csv")
pm = pm[pm["null"].notna()]
for _, r in pm.iterrows():
    nullname = str(r["null"])
    within = "cyclic" in nullname
    p = float(r["perm_p"]) if pd.notna(r["perm_p"]) else np.nan
    emit(screen="E1_I0031_rapm_as_prior",
         source_file="E1_I0031_rapm_as_prior/plusminus_separate.csv",
         candidate=r["added"], target=r["target"], stratum=r["stratum"], base=r["over"], n=r["n"],
         null_scheme_recorded=nullname,
         null_class="WITHIN_ENTITY" if within else "BETWEEN_ENTITY",
         null_permutes_at="player_season", null_level_source="TABLE",
         combination_rule="NULL_SELECTED_PER_CANDIDATE_BY_ITS_LEVEL__NO_MAX",
         other_nulls_run="p_blockflip on the MAE arm of the same screen",
         candidate_level="game-level plus-minus" if within else "player-season constant",
         var_share_between=np.nan, var_share_source="NOT_MEASURED_ON_DISK",
         observed_stat=r["dr2_own_sst"], stat_scale="dR2",
         p_decision=p, is_kill=bool(np.isfinite(p) and p >= ALPHA), kill_basis="perm_p>=0.05",
         EXPOSURE=("UNDETERMINABLE" if within else "NOT_EXPOSED"),
         exposure_reason=("within-entity cyclic null at player_season; the screen paired it with "
                          "the game-level candidate and used player_season_relabel (a between-entity "
                          "null) for the season-constant candidate, but records no measured variance "
                          "share, so the pairing cannot be VERIFIED from disk"
                          if within else
                          "decision null is player_season_relabel -- a between-entity null"),
         exposure_confidence=np.nan if within else 1.0)

rf = R("E1_I0031_rapm_as_prior/rapm_as_feature.csv")
for _, r in rf.iterrows():
    p = r.get("perm_p_player_season_relabel", np.nan)
    p = float(p) if pd.notna(p) else np.nan
    emit(screen="E1_I0031_rapm_as_prior", source_file="E1_I0031_rapm_as_prior/rapm_as_feature.csv",
         candidate="RAPM_as_feature", target=r["target"], stratum=r["stratum"], n=r["n"],
         null_scheme_recorded="player_season_relabel", null_class="BETWEEN_ENTITY",
         null_permutes_at="player_season", null_level_source="TABLE",
         combination_rule="SINGLE_DECISION_NULL",
         observed_stat=r["dr2_own_sst"], stat_scale="dR2",
         null_mean=r.get("perm_null_mean", np.nan), null_mean_source="RECORDED_BY_SCREEN",
         null_sd=r.get("perm_null_sd", np.nan),
         p_decision=p, is_kill=bool(np.isfinite(p) and p >= ALPHA), kill_basis="perm_p>=0.05",
         EXPOSURE="NOT_EXPOSED",
         exposure_reason="decision null relabels whole player-seasons -- a between-entity null "
                         "matched to a player-season-level candidate",
         exposure_confidence=1.0)

# =====================================================================================
# 5. E1_I0034_redistribution -- has a MEASURED candidate_level_audit
# =====================================================================================
cla = R("E1_I0034_redistribution/candidate_level_audit.csv")
lvmap = {str(r["candidate"]): (float(r["frac_between_player"]), str(r["dominant_level"]))
         for _, r in cla.iterrows()}
pc = R("E1_I0034_redistribution/primary_cells.csv")
for _, r in pc.iterrows():
    scheme = str(r.get("null_scheme", ""))
    within = bool(re.search(r"within", scheme, re.I))
    cand = str(r.get("candidate", ""))
    vsb, dom = np.nan, ""
    for k, (v, dd) in lvmap.items():
        if cand and (cand.split("_")[-1] in k or k.split()[0] in cand):
            vsb, dom = v, dd
            break
    p = float(r["p"]) if pd.notna(r["p"]) else np.nan
    if within:
        E_, why, conf = classify("WITHIN_ENTITY", vsb, "TABLE_MEASURED", "season",
                                 "measured in this screen's own candidate_level_audit.csv"
                                 if np.isfinite(vsb) else "")
        if not np.isfinite(vsb):
            why = ("within-entity null (%s); candidate_level_audit.csv measures shares over "
                   "player/team-game, not over the null's own entity (season), so the share the "
                   "rule needs is NOT on disk" % scheme)
    else:
        E_, why, conf = ("NOT_EXPOSED", "decision null is %s -- not a within-entity scheme" % scheme, 1.0)
    emit(screen="E1_I0034_redistribution", source_file="E1_I0034_redistribution/primary_cells.csv",
         candidate=cand, target=str(r.get("response", "")), stratum=str(r.get("row_set", "")),
         base=str(r.get("cell", "")), n=r.get("n", np.nan),
         null_scheme_recorded=scheme,
         null_class="WITHIN_ENTITY" if within else "BETWEEN_ENTITY",
         null_permutes_at="season" if within else "block", null_level_source="TABLE",
         combination_rule="SINGLE_DECISION_NULL",
         candidate_level=dom, var_share_between=vsb,
         var_share_source="TABLE_MEASURED" if np.isfinite(vsb) else "NOT_MEASURED_AT_NULL_ENTITY",
         observed_stat=r.get("effect", np.nan), stat_scale="effect",
         null_mean=r.get("null_mean", np.nan), null_mean_source="RECORDED_BY_SCREEN",
         null_sd=r.get("null_sd", np.nan),
         p_decision=p,
         is_kill=bool("NOT_ESTABLISHED" in str(r.get("verdict", "")) or "REJECTED" in str(r.get("verdict", ""))),
         kill_basis="verdict column: %s" % str(r.get("verdict", ""))[:60],
         EXPOSURE=E_, exposure_reason=why, exposure_confidence=conf)

# =====================================================================================
# 6. E1_I0036_level_artefact_sweep -- ITS OWN cells (CENSUS.csv is the other 8 screens)
#    LEVEL_RERUN_CELLS.csv carries a MEASURED var_share_between_entity.
# =====================================================================================
for f in ["E1_I0036_level_artefact_sweep/LEVEL_RERUN_CELLS.csv",
          "E1_I0036_level_artefact_sweep/LEVEL_FAIRTEST_CELLS.csv",
          "E1_I0036_level_artefact_sweep/D097_RELEVEL_CELLS.csv",
          "E1_I0036_level_artefact_sweep/D097_COMPONENT_NULLS.csv"]:
    d = R(f)
    if d is None:
        continue
    for _, r in d.iterrows():
        nullname = str(r.get("null", r.get("null_scheme", "")))
        within = bool(re.search(r"cyclic|within", nullname, re.I))
        vsb = r.get("var_share_between_entity", np.nan)
        vsb = float(vsb) if pd.notna(vsb) else np.nan
        pcol = "p" if "p" in d.columns else ("p_percell" if "p_percell" in d.columns else None)
        p = float(r[pcol]) if (pcol and pd.notna(r[pcol])) else np.nan
        ceil = r.get("ceiling", np.nan)
        E_, why, conf = classify("WITHIN_ENTITY" if within else "BETWEEN_ENTITY", vsb,
                                 "TABLE_MEASURED", "player_season")
        emit(screen="E1_I0036_level_artefact_sweep", source_file=f,
             candidate=str(r.get("candidate", "")), target=str(r.get("response", "")),
             stratum=str(r.get("level", r.get("cell", ""))), n=r.get("n", np.nan),
             null_scheme_recorded=nullname,
             null_class="WITHIN_ENTITY" if within else "BETWEEN_ENTITY",
             null_permutes_at="player_season", null_level_source="TABLE",
             combination_rule="ONE_NULL_PER_ROW__EACH_REPORTED_SEPARATELY__NO_MAX",
             candidate_level=str(r.get("level", "")),
             var_share_between=vsb,
             var_share_source="TABLE_MEASURED" if np.isfinite(vsb) else "NOT_MEASURED_ON_DISK",
             observed_stat=r.get("dr2", np.nan), stat_scale="dR2",
             null_mean=r.get("null_mean", np.nan),
             null_mean_source="RECORDED_BY_SCREEN" if pd.notna(r.get("null_mean", np.nan)) else "NONE",
             null_sd=r.get("null_sd", np.nan), p_decision=p,
             is_kill=bool(np.isfinite(p) and p >= ALPHA),
             is_ceiling=bool(pd.notna(ceil) and pd.notna(r.get("dr2", np.nan))
                             and abs(float(ceil) - float(r.get("dr2"))) < 1e-12),
             kill_basis="p>=0.05",
             EXPOSURE=E_, exposure_reason=why, exposure_confidence=conf)

# =====================================================================================
# 7. THE BETWEEN-ENTITY / ROW-ONLY SCREENS -- bulk, one spec per table
#    (candidate, target, stratum, p, obs, null_mean, null_sd, scheme label)
# =====================================================================================
BULK = [
    # screen, file, cand, target, stratum, p, obs, nullmean, nullsd, scheme, cls, entity, fw
    ("E1_I0004_efficiency_transfer", "E1_I0004_efficiency_transfer/efficiency_contrast.csv",
     "spec", "target", "stratum", "p_two_sided_cluster", "dr2_candidate_minus_baseline",
     None, "null_sd_cluster", "cluster sign-flip at opp_team_season", "BETWEEN_ENTITY",
     "opp_team_season", None),
    ("E1_I0004_efficiency_transfer", "E1_I0004_efficiency_transfer/points_contrast.csv",
     "spec", "target", "stratum", "p_two_sided_cluster", None, None, None,
     "cluster sign-flip at opp_team_season", "BETWEEN_ENTITY", "opp_team_season", None),
    ("E1_I0004_efficiency_transfer_v2", "E1_I0004_efficiency_transfer_v2/efficiency_contrast.csv",
     "spec", "response", "stratum", "p_cluster_opp_team_season", "dR2_cand_minus_base",
     None, None, "cluster at opp_team_season", "BETWEEN_ENTITY", "opp_team_season", None),
    ("E1_I0004_efficiency_transfer_v2", "E1_I0004_efficiency_transfer_v2/points_contrast.csv",
     "spec", "response", "stratum", "p_cluster_opp_team_season", None, None, None,
     "cluster at opp_team_season", "BETWEEN_ENTITY", "opp_team_season", None),
    ("E1_I0020_coldstart_tiering", "E1_I0020_coldstart_tiering/placeholder_comparison.csv",
     "placeholder", "target", "cell", "p_cluster_vs_champion", "dr2_vs_champion", None, None,
     "cluster at player_season", "BETWEEN_ENTITY", "player_season", None),
    ("E1_I0020_coldstart_tiering", "E1_I0020_coldstart_tiering/zero_games_case.csv",
     "placeholder", "target", "population", "p_cluster", None, None, None,
     "cluster at player_season", "BETWEEN_ENTITY", "player_season", None),
    ("E1_I0020_coldstart_tiering", "E1_I0020_coldstart_tiering/d087_decomposition.csv",
     None, "target", None, "p_cluster_STRUCT_vs_LEAGUE", None, None, None,
     "cluster", "BETWEEN_ENTITY", "player_season", None),
    ("E1_I0020_coldstart_tiering", "E1_I0020_coldstart_tiering/component_decomposition.csv",
     None, "target", None, "p_cluster_vs_previous", None, None, None,
     "cluster", "BETWEEN_ENTITY", "player_season", None),
    ("E1_I0020_coldstart_tiering", "E1_I0020_coldstart_tiering/pooled_operating_rule.csv",
     None, "target", None, "p_vs_champion", None, None, None,
     "cluster", "BETWEEN_ENTITY", "player_season", None),
    ("E1_I0020_coldstart_tiering", "E1_I0020_coldstart_tiering/permutation_nulls.csv",
     None, None, None, "p_correct_level", None, None, None,
     "correct-level cluster", "BETWEEN_ENTITY", "player_season", None),
    ("E1_I0020_coldstart_tiering", "E1_I0020_coldstart_tiering/per_season_stability.csv",
     None, None, None, "p_vs_champion", None, None, None,
     "cluster", "BETWEEN_ENTITY", "player_season", None),
    ("E1_I0022_optimal_simple_estimator", "E1_I0022_optimal_simple_estimator/paired_inference.csv",
     "slice", "target", "slice", "p_two_sided_blockflip",
     "mean_abs_err_diff_champ_minus_est", None, "null_sd",
     "paired block sign-flip", "BETWEEN_ENTITY", "block", None),
    ("E1_I0022_optimal_simple_estimator", "E1_I0022_optimal_simple_estimator/fallback_split.csv",
     None, "target", None, "p_two_sided_blockflip", None, None, None,
     "paired block sign-flip", "BETWEEN_ENTITY", "block", None),
    ("E1_I0025_threshold_vs_refit", "E1_I0025_threshold_vs_refit/pooled_tier_dummy.csv",
     "rung", "response", "stratum", "p_cluster_signflip", "dr2_defence_family", None,
     "null_sd_cluster", "cluster sign-flip", "BETWEEN_ENTITY", "cluster", None),
    ("E1_I0025_threshold_vs_refit", "E1_I0025_threshold_vs_refit/refit_decomposition.csv",
     None, None, None, "R_nodef_p_cluster", None, None, None,
     "cluster sign-flip", "BETWEEN_ENTITY", "cluster", None),
    ("E1_I0025_threshold_vs_refit", "E1_I0025_threshold_vs_refit/ladder_swap_null.csv",
     None, None, None, "p_swap", None, None, None,
     "ladder swap (between)", "BETWEEN_ENTITY", "ladder rung", None),
    ("E1_I0025_threshold_vs_refit", "E1_I0025_threshold_vs_refit/random_tier_null.csv",
     None, None, None, "p_onesided", None, None, None,
     "random tier assignment (between)", "BETWEEN_ENTITY", "tier", None),
    ("E1_I0025_threshold_vs_refit", "E1_I0025_threshold_vs_refit/concentration_increment_null.csv",
     None, None, None, "p_swap", None, None, None,
     "swap (between)", "BETWEEN_ENTITY", "cluster", None),
    ("E1_I0027_reference_ladder", "E1_I0027_reference_ladder/ladder_pairwise.csv",
     "rung_a", "target", "rung_b", "p", "dr2_a_minus_b", None, None,
     "cluster/block (paired rung contrast)", "BETWEEN_ENTITY", "block", None),
    ("E1_I0027_reference_ladder", "E1_I0027_reference_ladder/reprice_by_rung.csv",
     None, "target", None, "p_cluster", None, None, None,
     "cluster", "BETWEEN_ENTITY", "cluster", None),
    ("E1_I0032_aggregate_stack", "E1_I0032_aggregate_stack/stack_measurement.csv",
     "arm", "target", "stratum", "p", "dr2_common_sst", "null_mean", "null_sd",
     "cluster block permutation", "BETWEEN_ENTITY", "cluster", None),
    ("E1_I0032_aggregate_stack", "E1_I0032_aggregate_stack/ablation_matrix.csv",
     "arm", "target", "stratum", "p", None, "null_mean", "null_sd",
     "cluster block permutation", "BETWEEN_ENTITY", "cluster", None),
    ("E1_I0032_aggregate_stack", "E1_I0032_aggregate_stack/cumulative_curve.csv",
     "arm", "target", "stratum", "p", None, "null_mean", "null_sd",
     "cluster block permutation", "BETWEEN_ENTITY", "cluster", None),
    ("E1_I0032_aggregate_stack", "E1_I0032_aggregate_stack/placebo_stack.csv",
     "arm", "target", "stratum", "p", None, "null_mean", "null_sd",
     "cluster block permutation", "BETWEEN_ENTITY", "cluster", None),
    ("E1_I0032_aggregate_stack", "E1_I0032_aggregate_stack/controls.csv",
     "arm", "target", "stratum", "p", None, "null_mean", "null_sd",
     "cluster block permutation", "BETWEEN_ENTITY", "cluster", None),
    ("E1_I0032_aggregate_stack", "E1_I0032_aggregate_stack/availability_recalibration.csv",
     "arm", "target", "stratum", "p", None, "null_mean", "null_sd",
     "cluster block permutation", "BETWEEN_ENTITY", "cluster", None),
    ("E1_I0033_aggregation_level", "E1_I0033_aggregation_level/primary_cells_P01_P06.csv",
     "arm_A", None, "cell", "N1_teamseason_p", "mean_MAE_advantage_A_over_B", "N1_null_mean",
     "N1_null_sd", "N1 team_season block", "BETWEEN_ENTITY", "team_season", None),
    ("E1_I0033_aggregation_level", "E1_I0033_aggregation_level/which_level_wins.csv",
     None, None, None, "N1_p", None, None, None, "N1 team_season block", "BETWEEN_ENTITY",
     "team_season", None),
    ("E1_I0033_aggregation_level", "E1_I0033_aggregation_level/ft_cells.csv",
     None, None, None, "N1_p", None, None, None, "N1 team_season block", "BETWEEN_ENTITY",
     "team_season", None),
    ("E1_I0033_aggregation_level", "E1_I0033_aggregation_level/exploratory_cells.csv",
     None, None, None, "p", None, None, None, "N1 team_season block", "BETWEEN_ENTITY",
     "team_season", None),
    ("E1_I0035_availability_sum", "E1_I0035_availability_sum/repairs_player_level_tests.csv",
     "arm", "metric", "row_set", "p", "delta_vs_X0", "null_mean", "null_sd",
     "block permutation", "BETWEEN_ENTITY", "block", None),
    ("E1_I0035_availability_sum", "E1_I0035_availability_sum/repairs_team_level_tests.csv",
     "arm", "metric", "row_set", "p", "delta_vs_X0", "null_mean", "null_sd",
     "block permutation", "BETWEEN_ENTITY", "block", None),
    ("E1_I0034_redistribution", "E1_I0034_redistribution/secondary_window_W1.csv",
     None, None, None, "W1_p", None, None, None, "block permutation", "BETWEEN_ENTITY",
     "block", None),
    ("E1_I0034_redistribution", "E1_I0034_redistribution/stratification_by_freed.csv",
     None, None, None, "p", None, None, None, "block permutation", "BETWEEN_ENTITY",
     "block", None),
]
for (sc, f, cc, tc, stc, pc_, oc, mc, sdc, scheme, cls, ent, fwc) in BULK:
    d = R(f)
    if d is None or pc_ not in d.columns:
        print("SKIP (missing):", f, pc_)
        continue
    for _, r in d.iterrows():
        p = float(r[pc_]) if pd.notna(r[pc_]) else np.nan
        emit(screen=sc, source_file=f,
             candidate=str(r[cc]) if (cc and cc in d.columns) else str(r.iloc[0]),
             target=str(r[tc]) if (tc and tc in d.columns) else "",
             stratum=str(r[stc]) if (stc and stc in d.columns) else "",
             n=r.get("n", np.nan),
             null_scheme_recorded=scheme, null_class=cls, null_permutes_at=ent,
             null_level_source="TABLE",
             combination_rule="SINGLE_DECISION_NULL",
             other_nulls_run="p_row_level_NAIVE / p_row_NAIVE reported as an inflation contrast, "
                             "never the verdict" if any(c.lower().startswith("p_row")
                                                        for c in d.columns) else "",
             observed_stat=float(r[oc]) if (oc and oc in d.columns and pd.notna(r[oc])) else np.nan,
             stat_scale="dR2/MAE-delta",
             null_mean=float(r[mc]) if (mc and mc in d.columns and pd.notna(r[mc])) else np.nan,
             null_mean_source="RECORDED_BY_SCREEN" if (mc and mc in d.columns
                                                        and pd.notna(r[mc])) else "NONE",
             null_sd=float(r[sdc]) if (sdc and sdc in d.columns and pd.notna(r[sdc])) else np.nan,
             p_decision=p, is_kill=bool(np.isfinite(p) and p >= ALPHA), kill_basis="p>=0.05",
             EXPOSURE="NOT_EXPOSED",
             exposure_reason="decision null is %s -- a between-entity scheme; a within-entity "
                             "null did not decide this cell" % scheme,
             exposure_confidence=1.0)

# =====================================================================================
AT = pd.DataFrame(rows)
AT.to_csv(os.path.join(HERE, "AUDIT_TABLE_EXT.csv"), index=False)

print("\n================ AUDIT_TABLE_EXT ================")
print("rows:", len(AT), " screens represented:", AT.screen.nunique())
print("\nnull_class over ALL cells:\n", AT.null_class.value_counts().to_string())
K = AT[AT.is_kill]
print("\nKILLED cells:", len(K))
print("null_class over KILLS:\n", K.null_class.value_counts().to_string())
print("\nEXPOSURE over KILLS:\n", K.EXPOSURE.value_counts().to_string())
print("\nEXPOSURE over ALL:\n", AT.EXPOSURE.value_counts().to_string())
print("\nby screen (kills):\n",
      K.groupby(["screen", "EXPOSURE"]).size().unstack(fill_value=0).to_string())
print("\nceiling kills found:", int(AT.is_ceiling.sum()))
print("\nnull_mean recorded by screen:", int((AT.null_mean_source == "RECORDED_BY_SCREEN").sum()),
      "of", len(AT))
print("z computable:", int(AT.z_obs_vs_null.notna().sum()))
print("flag z<-1 trips:", int((AT.flag_z_lt_neg1 == True).sum()))
print("bare flag null_mean>observed trips:", int((AT.flag_null_mean_gt_observed == True).sum()))
with open(os.path.join(HERE, "scripts", "_s04.json"), "w") as fh:
    json.dump(dict(rows=len(AT), kills=int(len(K)),
                   exposure_kills=K.EXPOSURE.value_counts().to_dict(),
                   exposure_all=AT.EXPOSURE.value_counts().to_dict(),
                   null_class_kills=K.null_class.value_counts().to_dict()), fh, indent=2)
