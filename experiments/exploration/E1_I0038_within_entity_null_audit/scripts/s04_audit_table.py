"""S04 -- BUILD THE FULL AUDIT TABLE.  PREREG sections 2, 3, 4.

For every recorded cell: null scheme used, level the CANDIDATE varies at, level the NULL
permutes at, null mean, observed statistic, p, recorded verdict -> EXPOSURE classification.

NOTHING is inferred from a candidate's name.  Every level and every variance share carries its
source (TABLE / PREREG / CODE / RECORDED / COMPUTED) and every count below is reported split
by that source.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab38 import (EXP, EXPOSURE_THRESHOLD, OUT, SENSITIVITY_THRESHOLDS, hdr,
                   var_share_between)

CEN = os.path.join(EXP, "E1_I0036_level_artefact_sweep", "CENSUS.csv")

# ============================================================ 0. ANCHOR: reproduce D115's 550
hdr("0. PRIOR-SCREEN ANCHOR -- reproduce D115/E1_I0036's exposed-level counts EXACTLY")
cen = pd.read_csv(CEN)
print(f"  CENSUS.csv: {len(cen)} cells, {cen['screen'].nunique()} screens")
killed = cen[~cen["kill_reason"].isin(["SURVIVOR", "SURVIVOR_PERCELL_ONLY"])]
print(f"  killed cells: {len(killed)}   (E1_I0036 recorded 1,580)")
n_ps_kill = int((killed["level_recorded"] == "player_season").sum())
n_ots_kill = int((killed["level_recorded"] == "opp_team_season").sum())
n_ps_all = int((cen["level_recorded"] == "player_season").sum())
n_ots_all = int((cen["level_recorded"] == "opp_team_season").sum())
print(f"  killed at player_season   = {n_ps_kill}   (E1_I0036/D115 recorded 213)")
print(f"  killed at opp_team_season = {n_ots_kill}   (E1_I0036/D115 recorded 337)")
print(f"  ALL cells  player_season  = {n_ps_all}    (recorded 299)")
print(f"  ALL cells  opp_team_seas. = {n_ots_all}    (recorded 427)")
print(f"  SUM of the two killed levels = {n_ps_kill + n_ots_kill}  (D115's '550 exposed cells')")
assert len(cen) == 1999, "census size changed"
assert len(killed) == 1580, f"killed count {len(killed)} != 1580"
assert n_ps_kill == 213 and n_ots_kill == 337, "D115's 550 does not reproduce -- HALT"
assert n_ps_all == 299 and n_ots_all == 427, "the 299/427 variant does not reproduce -- HALT"
print("  >>> ANCHOR REPRODUCED: 213 + 337 = 550, and 299 / 427.  Gate passed.")

# ============================================================ 1. per-screen null adapters
hdr("1. DECISION-NULL ADAPTERS (one per screen; every classification cites its source)")


def trace(dec_col, cand_cols, d):
    """Which candidate p column(s) does the decision p EXACTLY equal?  (PREREG 3)"""
    out = []
    for i in range(len(d)):
        dv = d[dec_col].iloc[i]
        if pd.isna(dv):
            out.append(())
            continue
        hits = tuple(c for c in cand_cols if c in d.columns and pd.notna(d[c].iloc[i])
                     and abs(float(d[c].iloc[i]) - float(dv)) < 1e-12)
        out.append(hits)
    return out


CLASS = {}   # p-column -> (null_class, human name)
rows = []

# ---------------------------------------------------------------- E0_I0014  D078/D082
d = pd.read_csv(os.path.join(EXP, "E0_I0014_residual_heterogeneity", "screen_results.csv"))
# CODE FACT (E0_I0014/s04_screen.py:229,287): use_between = var_share_between_blocks > 0.5 and
# correct_null_level is BETWEEN-block iff use_between.  The scheme was CHOSEN BY THE SHARE.
# CODE FACT (rh_base.py:23-24): PLAYER scheme = (season, player_id) blocks; TEAM = (season, team_id).
z14 = np.load(os.path.join(EXP, "E0_I0014_residual_heterogeneity", "permutation_nulls.npz"),
              allow_pickle=True)
n14 = list(z14["names"]); dep14 = list(z14["dependents"])
for i, r in d.iterrows():
    within = (r["correct_null_level"] == "WITHIN-block")
    ent = {"PLAYER": "player_season", "TEAM": "team_season"}[r["perm_scheme"]]
    # null mean recoverable from the raw |t| draws (stat scale is ABS_T)
    nm = np.nan
    try:
        ci, di = n14.index(r["candidate"]), dep14.index(r["dependent"])
        key = ("win__" if within else "bet__") + r["dependent"]
        nm = float(np.nanmean(np.abs(z14[key][:, ci])))
    except Exception:
        pass
    rows.append(dict(
        screen="E0_I0014_residual_heterogeneity", candidate=r["candidate"],
        target=r["dependent"], stratum=np.nan, base=np.nan,
        null_scheme_recorded=("p_within_block_null" if within else "p_between_block_null"),
        null_class=("WITHIN_ENTITY" if within else "BETWEEN_ENTITY"),
        null_permutes_at=ent, null_level_source="TABLE",
        null_source_cite="E0_I0014/screen_results.csv:perm_scheme + rh_base.py:23-24",
        candidate_level_recorded=ent, candidate_level_source="TABLE",
        var_share_between=float(r["var_share_between_blocks"]), var_share_entity=ent,
        var_share_source="RECORDED",
        stat_scale="ABS_T", observed_stat=abs(float(r["t_classical"])),
        null_mean=nm, null_mean_source=("FROM_DRAWS" if np.isfinite(nm) else "NONE"),
        null_mean_recorded_by_screen=False,
        p_decision=r["p_correct_level"], p_familywise=r["p_familywise_whole_screen"],
        dr2_reported=r["delta_r2_plain_unweighted"], n=np.nan))

# ---------------------------------------------------------------- E0_I0016  D085
d = pd.read_csv(os.path.join(EXP, "E0_I0016_efficiency_predictors", "screen_results.csv"))
# CODE FACT (E0_I0016/s02_screen.py:146,167-186): lvl_cols = declared entity_level; vsb is
# var_share_between over THE SAME lvl_cols; N1 = SCHEME_WITHIN at lvl_cols; N2 = entity_swap at
# lvl_cols; p_correct_level = max(p_N1, p_N2).  -> the WITHIN arm can veto.
tr = trace("p_correct_level", ["p_N1_within_entity", "p_N2_entity_swap"], d)
for i, r in d.iterrows():
    h = tr[i]
    if h == ("p_N1_within_entity",):
        cls, sch, nm = "WITHIN_ENTITY", "p_N1_within_entity", r["null_mean_N1"]
    elif "p_N2_entity_swap" in h:            # tie resolves AGAINST the hypothesis (PREREG 3)
        cls, sch, nm = "BETWEEN_ENTITY", "p_N2_entity_swap", r["null_mean_N2"]
    else:
        cls, sch, nm = "UNDETERMINABLE", "NO_MATCH", np.nan
    rows.append(dict(
        screen="E0_I0016_efficiency_predictors", candidate=r["candidate"], target=r["outcome"],
        stratum=np.nan, base=np.nan,
        null_scheme_recorded=sch, null_class=cls,
        null_permutes_at=r["entity_level"], null_level_source="TABLE",
        null_source_cite="E0_I0016/screen_results.csv:entity_level + s02_screen.py:167-186",
        candidate_level_recorded=r["entity_level"], candidate_level_source="TABLE",
        var_share_between=float(r["var_share_between_entity"]),
        var_share_entity=r["entity_level"], var_share_source="RECORDED",
        stat_scale="DR2", observed_stat=float(r["dr2"]),
        null_mean=float(nm) if pd.notna(nm) else np.nan,
        null_mean_source=("RECORDED" if pd.notna(nm) else "NONE"),
        null_mean_recorded_by_screen=True,
        p_decision=r["p_correct_level"], p_familywise=r["p_familywise_maxt"],
        dr2_reported=r["dr2"], n=r["n"]))

# ---------------------------------------------------------------- E0_I0017  D087
d = pd.read_csv(os.path.join(EXP, "E0_I0017_shot_quality_efficiency", "screen_results.csv"))
vs17 = pd.read_csv(os.path.join(EXP, "E0_I0017_shot_quality_efficiency",
                                "var_share_between.csv"))
vmap = {(a, b): c for a, b, c in vs17[["candidate", "entity", "var_share_between"]].values}
for i, r in d.iterrows():
    # ONLY an entity-swap null was recorded -> BETWEEN_ENTITY.  Draws are STANDARDISED on disk,
    # which erases the null mean irrecoverably (reported as a defect, not a gap in this screen).
    rows.append(dict(
        screen="E0_I0017_shot_quality_efficiency", candidate=r["candidate"],
        target=r["outcome"], stratum=np.nan, base=np.nan,
        null_scheme_recorded="p_correct_entityswap", null_class="BETWEEN_ENTITY",
        null_permutes_at=r["entity"], null_level_source="TABLE",
        null_source_cite="E0_I0017/screen_results.csv:entity",
        candidate_level_recorded=r["entity"], candidate_level_source="TABLE",
        var_share_between=vmap.get((r["candidate"], r["entity"]), np.nan),
        var_share_entity=r["entity"],
        var_share_source=("RECORDED" if (r["candidate"], r["entity"]) in vmap else "NONE"),
        stat_scale="STANDARDISED", observed_stat=float(r["dR2"]),
        null_mean=np.nan, null_mean_source="NONE", null_mean_recorded_by_screen=False,
        p_decision=r["p_correct_entityswap"], p_familywise=r["p_familywise_maxz"],
        dr2_reported=r["dR2"], n=r["n"]))

# ---------------------------------------------------------------- E0_I0019  D090
d = pd.read_csv(os.path.join(EXP, "E0_I0019_availability_forecast",
                             "screen_results_repaired.csv"))
z19 = np.load(os.path.join(EXP, "E0_I0019_availability_forecast", "permutation_nulls.npz"))
CANDS19 = list(pd.read_csv(os.path.join(EXP, "E0_I0019_availability_forecast",
                                        "grouping_levels.csv"))["candidate"])
DEP19 = list(pd.unique(d["dependent"]))
# CODE FACT (s05_spreads_and_decomposition.py:34-63): the repair explicitly REMOVED the max()
# over schemes -- "two schemes, two questions, no max()".  The published family-wise p is built
# from maxt_primary, i.e. the BETWEEN scheme.  The decision null is therefore BETWEEN_ENTITY.
# The SUPERSEDED pre-repair rule was p_correct_level_WORST = max(between, within); the
# counterfactual exposure under that superseded rule is reported separately, not here.
for i, r in d.iterrows():
    prim = r["scheme_between"]     # player_between | teamgame_between
    ent = {"player_between": "player_season", "teamgame_between": "team_game"}[prim]
    nm = np.nan
    try:
        ci, di = CANDS19.index(r["candidate"]), DEP19.index(r["dependent"])
        a = z19["null_%s" % prim][:, ci, di]
        a = a[np.isfinite(a)]
        nm = float(np.mean(np.abs(a)))       # ABS_T form -- the signed mean recorded by the
    except Exception:                        # screen is NOT the right comparison (see DEFECTS)
        pass
    rows.append(dict(
        screen="E0_I0019_availability_forecast", candidate=r["candidate"],
        target=r["dependent"], stratum=np.nan, base=np.nan,
        null_scheme_recorded="p_between(" + prim + ")", null_class="BETWEEN_ENTITY",
        null_permutes_at=ent, null_level_source="TABLE",
        null_source_cite="E0_I0019/screen_results_repaired.csv:scheme_between + s04_screen.py:143-147",
        candidate_level_recorded="NOT_RECORDED", candidate_level_source="NONE",
        var_share_between=float(r["var_share_between"]), var_share_entity=ent,
        var_share_source="RECORDED",
        stat_scale="ABS_T", observed_stat=abs(float(r["t"])),
        null_mean=nm, null_mean_source=("FROM_DRAWS" if np.isfinite(nm) else "NONE"),
        null_mean_recorded_by_screen=True,   # recorded, but in the WRONG (signed) form
        p_decision=r["p_between"], p_familywise=r["p_familywise"],
        dr2_reported=np.nan, n=r["n"]))

# ---------------------------------------------------------------- E0_I0024  D097
d = pd.read_csv(os.path.join(EXP, "E0_I0024_reb_ast_characterisation", "upstream_signals.csv"))
z24 = np.load(os.path.join(EXP, "E0_I0024_reb_ast_characterisation", "permutation_draws.npz"))
# CODE FACT (E0_I0024/s04_screen.py:44,108-158): level comes from the FROZEN PREREG per
# candidate; both the cyclic shift and the entity swap operate on (season, LEVEL_ENT[level]);
# p_correct_level = max(p_entity_swap, p_cyclic_shift).  -> the CYCLIC arm can veto.
tr = trace("p_correct_level", ["p_entity_swap", "p_cyclic_shift", "p_row_level_NAIVE"], d)
for i, r in d.iterrows():
    h = tr[i]
    if h == ("p_cyclic_shift",):
        cls, sch = "WITHIN_ENTITY", "p_cyclic_shift"
    elif "p_entity_swap" in h:
        cls, sch = "BETWEEN_ENTITY", "p_entity_swap"
    elif h == ("p_row_level_NAIVE",):
        cls, sch = "ROW", "p_row_level_NAIVE"
    else:
        cls, sch = "UNDETERMINABLE", "NO_MATCH"
    key = "%s|%s|%s|%s" % (r["stratum"], r["target"], r["base"], r["candidate"])
    nm = float(np.mean(z24[key])) if key in z24.files else np.nan
    rows.append(dict(
        screen="E0_I0024_reb_ast_characterisation", candidate=r["candidate"],
        target=r["target"], stratum=r["stratum"], base=r["base"],
        null_scheme_recorded=sch, null_class=cls,
        null_permutes_at=r["level"], null_level_source="PREREG",
        null_source_cite="E0_I0024/_prereg.json:candidates[].level via s04_screen.py:44,108-158",
        candidate_level_recorded=r["level"], candidate_level_source="PREREG",
        var_share_between=np.nan, var_share_entity=r["level"], var_share_source="PENDING",
        stat_scale="DR2", observed_stat=float(r["dr2"]),
        null_mean=nm, null_mean_source=("FROM_DRAWS" if np.isfinite(nm) else "NONE"),
        null_mean_recorded_by_screen=False,
        p_decision=r["p_correct_level"], p_familywise=r["fw_p"],
        dr2_reported=r["dr2"], n=r["n"]))

# ---------------------------------------------------------------- E0_I0029  D108
d = pd.read_csv(os.path.join(EXP, "E0_I0029_freethrow_hurdle", "screen_results.csv"))
NMCOL = {"N_ROW": "nullmean_N_ROW", "N_CYCLIC": "nullmean_N_CYCLIC",
         "N_PSWAP": "nullmean_N_PSWAP", "N_ENTITY": "nullmean_N_ENTITY"}
for i, r in d.iterrows():
    used = str(r["correct_null_used"])
    if used.startswith("N_ROW"):
        cls, sch, nm = "ROW", "N_ROW", r["nullmean_N_ROW"]
    elif "N_PSWAP" in used or "N_ENTITY" in used:
        # both are whole-series SWAPS -> BETWEEN_ENTITY.  The cyclic arm was computed and
        # EXPLICITLY EXCLUDED (column p_N_CYCLIC_EXCLUDED_no_power).
        sch = "N_PSWAP" if "N_PSWAP" in used else "N_ENTITY"
        cls, nm = "BETWEEN_ENTITY", r[NMCOL[sch]]
    else:
        cls, sch, nm = "UNDETERMINABLE", used, np.nan
    rows.append(dict(
        screen="E0_I0029_freethrow_hurdle", candidate=r["candidate"], target=r["target"],
        stratum=r["stratum"], base=r["base"],
        null_scheme_recorded=sch, null_class=cls,
        null_permutes_at=r["level"], null_level_source="TABLE",
        null_source_cite="E0_I0029/screen_results.csv:level + correct_null_used",
        candidate_level_recorded=r["level"], candidate_level_source="TABLE",
        var_share_between=np.nan, var_share_entity=r["level"], var_share_source="PENDING",
        stat_scale="DR2", observed_stat=float(r["dR2"]),
        null_mean=float(nm) if pd.notna(nm) else np.nan,
        null_mean_source=("RECORDED" if pd.notna(nm) else "NONE"),
        null_mean_recorded_by_screen=True,
        p_decision=r["p_correct_level"], p_familywise=r["p_family_wise"],
        dr2_reported=r["dR2"], n=r["n"]))

# ---------------------------------------------------------------- E1_I0018  D089
d = pd.read_csv(os.path.join(EXP, "E1_I0018_teammate_volume_channel", "screen_results.csv"))
# CODE FACT (E1_I0018/s03_screen.py:170 `ent = ENTITY_TEAM` UNCONDITIONALLY; tv_base.py:198
# ENTITY_TEAM = ("team_season", ["team_id","season"]); s03_screen.py:187 var_share_between over
# THE SAME ent[1]; tv_base.py:224 p_correct_level = max(p_N1, p_N2)).
# E1_I0036 D-01 called this level "implied but not recorded".  IT IS RECORDED -- IN THE CODE.
tr = trace("p_correct_level", ["p_N1_within_entity", "p_N2_entity_swap"], d)
for i, r in d.iterrows():
    h = tr[i]
    if h == ("p_N1_within_entity",):
        cls, sch, nm = "WITHIN_ENTITY", "p_N1_within_entity", r["null_mean_N1"]
    elif "p_N2_entity_swap" in h:
        cls, sch, nm = "BETWEEN_ENTITY", "p_N2_entity_swap", r["null_mean_N2"]
    else:
        cls, sch, nm = "UNDETERMINABLE", "NO_MATCH", np.nan
    rows.append(dict(
        screen="E1_I0018_teammate_volume_channel", candidate=r["candidate"],
        target=r["outcome"], stratum=r["stratum"], base=r["base"],
        null_scheme_recorded=sch, null_class=cls,
        null_permutes_at="team_season", null_level_source="CODE",
        null_source_cite="E1_I0018/s03_screen.py:170 + tv_base.py:198,202-232",
        candidate_level_recorded="NOT_RECORDED", candidate_level_source="NONE",
        var_share_between=float(r["var_share_between_team_season"]),
        var_share_entity="team_season", var_share_source="RECORDED",
        stat_scale="DR2", observed_stat=float(r["dr2"]),
        null_mean=float(nm) if pd.notna(nm) else np.nan,
        null_mean_source=("RECORDED" if pd.notna(nm) else "NONE"),
        null_mean_recorded_by_screen=True,
        p_decision=r["p_correct_level"], p_familywise=r["p_familywise_maxt"],
        dr2_reported=r["dr2"], n=r["n"]))

# ---------------------------------------------------------------- E1_I0023  D098/D099
d = pd.read_csv(os.path.join(EXP, "E1_I0023_usage_defence_interaction",
                             "interaction_forecast.csv"))
# CODE FACT (uid_base.py:237-263): the null is a WHOLE-CLUSTER SIGN-FLIP at opponent-team-season
# (s02_interaction_forecast.py:35,68-71).  A sign flip of a whole cluster destroys the cluster's
# alignment -> BETWEEN_ENTITY.  Its draws are symmetric about 0 BY CONSTRUCTION, so the
# null_mean > observed diagnostic is VACUOUS there and is not applied.
for i, r in d.iterrows():
    rows.append(dict(
        screen="E1_I0023_usage_defence_interaction", candidate=r["defence"],
        target=r["response"], stratum=r["stratum"], base=r["base"],
        null_scheme_recorded="p_cluster(whole-cluster sign-flip)", null_class="BETWEEN_ENTITY",
        null_permutes_at="opp_team_season", null_level_source="CODE",
        null_source_cite="E1_I0023/s02_interaction_forecast.py:35,68-71 + uid_base.py:237-263",
        candidate_level_recorded="NOT_RECORDED", candidate_level_source="NONE",
        var_share_between=np.nan, var_share_entity="opp_team_season", var_share_source="NONE",
        stat_scale="SIGNED_SYMMETRIC", observed_stat=float(r["dr2_a_minus_b"]),
        null_mean=np.nan, null_mean_source="NONE", null_mean_recorded_by_screen=False,
        p_decision=r["p_cluster"], p_familywise=np.nan,
        dr2_reported=r["dr2_a_minus_b"], n=r["n_scored"]))

A = pd.DataFrame(rows)
print(f"  adapter rows built: {len(A)}   (census has {len(cen)})")
print(A.groupby("screen").size().to_string())

# ============================================================ 2. join the census verdicts
hdr("2. JOIN CENSUS VERDICTS (kill_reason, eligibility, power) BY POSITION WITHIN SCREEN")
# Both tables are built by iterating the SAME source files in the SAME order, so a positional
# join within screen is exact.  Verified below on candidate+target.
A["_i"] = A.groupby("screen").cumcount()
cen["_i"] = cen.groupby("screen").cumcount()
M = A.merge(cen[["screen", "_i", "candidate", "target", "kill_reason", "kill_reason_corrected",
                 "ceiling_recorded", "mde80_fw_used", "blind_used", "level_recorded",
                 "ELIGIBLE"]],
            on=["screen", "_i"], suffixes=("", "_cen"), how="left", validate="1:1")
bad = M[(M["candidate"] != M["candidate_cen"]) | (M["target"] != M["target_cen"])]
print(f"  positional join mismatches on (candidate,target): {len(bad)} / {len(M)}")
assert len(bad) == 0, "POSITIONAL JOIN FAILED -- halt"
print("  >>> join verified exact on candidate AND target for all rows")

# ============================================================ 3. COMPUTED variance shares
hdr("3. COMPUTED BETWEEN-ENTITY VARIANCE SHARES (PREREG 2.2) -- D097 only")
# Computed ONLY where it can change a classification: E0_I0024's 104 cyclic-decision cells are
# the ONLY within-entity decision cells in the census with no recorded share.  For every other
# screen either the share is RECORDED or the decision null is not within-entity (E2 is moot).
need = M[(M["screen"] == "E0_I0024_reb_ast_characterisation")
         & (M["var_share_source"] == "PENDING")]
print(f"  D097 cells needing a computed share: {len(need)}")

BASE_COLS = {"B_SINGLE": ["ref_mean"],
             "B_COMPLETE": ["ref_mean", "ref_ewma", "ref_trail5", "ref_rate_x_min",
                            "ref_mean_minutes", "ref_trail5_minutes", "ref_pct",
                            "ref_mean_pace", "n_prior", "is_home"]}
LEVEL_ENT = {"opp_team_season": "opp_team_id", "team_season": "team_id",
             "player_season": "player_id", "row": None}
PERTARGET = ("ref_mean", "ref_ewma", "ref_trail5", "ref_rate_x_min", "ref_pct")


def basecols_for(target, base):
    cols = [c + "__" + target if c in PERTARGET else c
            for c in BASE_COLS["B_SINGLE" if base == "B_SINGLE" else "B_COMPLETE"]]
    if base == "B_COMPLETE_PLUS_R10":
        cols.append("R10_opp_allowed_oreb_pg")
    return cols


F24 = pd.read_parquet(os.path.join(EXP, "E0_I0024_reb_ast_characterisation",
                                   "screen_frame.parquet"))
assert set(pd.unique(F24["season"])) <= {2021, 2022, 2023, 2024}, "PARTITION BREACH"
F24 = F24[F24["season"].isin((2022, 2023, 2024))].reset_index(drop=True)
print(f"  D097 headline frame {F24.shape}, seasons {sorted(set(F24['season']))}")
SM = {"POOLED": np.ones(len(F24), bool), "DECISION": (F24["DECISION"] == 1).to_numpy()}

vs_computed, n_rows_computed = {}, {}
for i, r in need.iterrows():
    lvl = r["null_permutes_at"]
    ent = LEVEL_ENT.get(lvl)
    if ent is None:
        continue
    bcols = basecols_for(r["target"], r["base"])
    cand = r["candidate"]
    nd = [r["target"]] + bcols + ([] if cand == "G02_placebo_noop" else [cand])
    sub = F24.loc[SM[r["stratum"]]].dropna(subset=[c for c in nd if c in F24.columns])
    if len(sub) < 300 or cand not in sub.columns:
        continue
    g = sub["season"].astype(str) + "_" + sub[ent].astype(str)
    vs_computed[i] = var_share_between(sub[cand].to_numpy(float), g.to_numpy())
    n_rows_computed[i] = len(sub)

M.loc[list(vs_computed), "var_share_between"] = pd.Series(vs_computed)
M.loc[list(vs_computed), "var_share_source"] = "COMPUTED"
M.loc[list(n_rows_computed), "n_rows_for_var_share"] = pd.Series(n_rows_computed)
M.loc[M["var_share_source"] == "PENDING", "var_share_source"] = "NONE"
print(f"  computed shares for {len(vs_computed)} D097 cells")
print("  var_share_source counts:\n" + M["var_share_source"].value_counts().to_string())

# ============================================================ 4. EXPOSURE (PREREG 3)
hdr("4. EXPOSURE CLASSIFICATION (frozen rule, PREREG section 3)")
M["is_kill"] = ~M["kill_reason"].isin(["SURVIVOR", "SURVIVOR_PERCELL_ONLY"])
M["is_ceiling"] = M["kill_reason"] == "CEILING"


def classify(r, thr):
    if not r["is_kill"]:
        return "NOT_A_KILL", "surviving cell"
    if r["is_ceiling"]:
        return "CEILING_EXCLUDED", "arithmetic ceiling kill -- survives every revision"
    if r["null_class"] == "UNDETERMINABLE":
        return "UNDETERMINABLE", "decision null scheme not establishable from an admissible record"
    if r["null_class"] in ("BETWEEN_ENTITY", "ROW"):
        return "NOT_EXPOSED", f"decision null is {r['null_class']} -- E1 fails"
    # null_class == WITHIN_ENTITY
    if r["var_share_source"] in ("NONE",) or not np.isfinite(r["var_share_between"]):
        return "UNDETERMINABLE", "within-entity null, but no admissible between-entity share"
    if str(r["var_share_entity"]) != str(r["null_permutes_at"]):
        return "UNDETERMINABLE", "recorded share is over a different entity than the null"
    if r["var_share_between"] >= thr:
        return "EXPOSED", (f"within-entity null at {r['null_permutes_at']}, "
                           f"between-share {r['var_share_between']:.3f} >= {thr}")
    return "NOT_EXPOSED", (f"within-entity null at {r['null_permutes_at']}, "
                           f"between-share {r['var_share_between']:.3f} < {thr}")


for thr in SENSITIVITY_THRESHOLDS:
    col = "EXPOSURE" if thr == EXPOSURE_THRESHOLD else f"EXPOSURE_thr{thr}"
    res = M.apply(lambda r: classify(r, thr), axis=1)
    M[col] = [a for a, _ in res]
    if thr == EXPOSURE_THRESHOLD:
        M["exposure_reason"] = [b for _, b in res]

M["exposure_confidence"] = np.where(
    (M["null_level_source"] == "TABLE") & (M["var_share_source"] == "RECORDED"), 1.00,
    np.where(M["var_share_source"] == "COMPUTED", 0.50, 0.70))

print("\nEXPOSURE (threshold 0.50, the headline):")
print(M["EXPOSURE"].value_counts().to_string())
print("\nby screen:")
print(pd.crosstab(M["screen"], M["EXPOSURE"]).to_string())
print("\nnull_class over KILLED cells only:")
print(M.loc[M["is_kill"], "null_class"].value_counts().to_string())
print("\nSENSITIVITY -- exposed count at each threshold:")
for thr in SENSITIVITY_THRESHOLDS:
    col = "EXPOSURE" if thr == EXPOSURE_THRESHOLD else f"EXPOSURE_thr{thr}"
    vc = M[col].value_counts()
    print(f"  thr={thr:.2f}   EXPOSED={vc.get('EXPOSED', 0):5d}  "
          f"NOT_EXPOSED={vc.get('NOT_EXPOSED', 0):5d}  "
          f"UNDETERMINABLE={vc.get('UNDETERMINABLE', 0):5d}")

# ============================================================ 5. THE FLAG (PREREG 4)
hdr("5. THE null_mean > observed FLAG")
M["flag_applicable"] = M["stat_scale"].isin(["DR2", "ABS_T"])
M["flag_computable"] = M["flag_applicable"] & M["null_mean"].notna() & M["observed_stat"].notna()
M["flag_null_mean_gt_observed"] = np.where(
    M["flag_computable"], M["null_mean"] > M["observed_stat"], np.nan)

print(f"  cells total                                  : {len(M)}")
print(f"  stat scale allows the flag at all            : {int(M['flag_applicable'].sum())}")
print(f"  ... of which the SCREEN ITSELF recorded a mean: "
      f"{int((M['flag_applicable'] & (M['null_mean_source'] == 'RECORDED')).sum())}")
print(f"  ... recovered by this screen FROM RAW DRAWS   : "
      f"{int((M['flag_applicable'] & (M['null_mean_source'] == 'FROM_DRAWS')).sum())}")
print(f"  ... NO null mean available anywhere           : "
      f"{int((M['flag_applicable'] & (M['null_mean_source'] == 'NONE')).sum())}")
print(f"  flag COMPUTABLE                              : {int(M['flag_computable'].sum())}")
print(f"  flag TRIPS (null_mean > observed)            : "
      f"{int((M['flag_null_mean_gt_observed'] == 1).sum())}")
print("\nnull_mean_source x stat_scale:")
print(pd.crosstab(M["null_mean_source"], M["stat_scale"]).to_string())
print("\nflag trips by screen (killed cells only):")
k = M[M["is_kill"]]
print(pd.crosstab(k["screen"], k["flag_null_mean_gt_observed"], dropna=False).to_string())

hdr("5b. FLAG vs STRUCTURAL EXPOSURE (killed, non-ceiling, flag computable)")
sub = M[M["is_kill"] & ~M["is_ceiling"] & M["flag_computable"]]
ct = pd.crosstab(sub["flag_null_mean_gt_observed"], sub["EXPOSURE"])
print(ct.to_string())
det = sub[sub["EXPOSURE"].isin(["EXPOSED", "NOT_EXPOSED"])]
if len(det):
    tp = int(((det["flag_null_mean_gt_observed"] == 1) & (det["EXPOSURE"] == "EXPOSED")).sum())
    fn = int(((det["flag_null_mean_gt_observed"] == 0) & (det["EXPOSURE"] == "EXPOSED")).sum())
    fp = int(((det["flag_null_mean_gt_observed"] == 1)
              & (det["EXPOSURE"] == "NOT_EXPOSED")).sum())
    tn = int(((det["flag_null_mean_gt_observed"] == 0)
              & (det["EXPOSURE"] == "NOT_EXPOSED")).sum())
    print(f"\n  determinate cells with a computable flag: {len(det)}")
    print(f"  TP={tp}  FN={fn}  FP={fp}  TN={tn}")
    print(f"  sensitivity (flag | EXPOSED)     = "
          f"{tp / (tp + fn) if (tp + fn) else float('nan'):.4f}")
    print(f"  specificity (no flag | NOT_EXP)  = "
          f"{tn / (tn + fp) if (tn + fp) else float('nan'):.4f}")
    ct.to_csv(os.path.join(OUT, "FLAG_AGREEMENT.csv"))
    pd.DataFrame([dict(TP=tp, FN=fn, FP=fp, TN=tn, n=len(det),
                       sensitivity=tp / (tp + fn) if (tp + fn) else np.nan,
                       specificity=tn / (tn + fp) if (tn + fp) else np.nan)]).to_csv(
        os.path.join(OUT, "FLAG_AGREEMENT_SUMMARY.csv"), index=False)

# ============================================================ 6. the D090 counterfactual
hdr("6. THE SUPERSEDED-RULE COUNTERFACTUAL (D090 only, reported not adopted)")
d19 = pd.read_csv(os.path.join(EXP, "E0_I0019_availability_forecast",
                               "screen_results_repaired.csv"))
worse_within = (d19["p_within"] > d19["p_between"])
hi = d19["var_share_between"] >= EXPOSURE_THRESHOLD
print("  D090's PUBLISHED (repaired) rule uses the BETWEEN null only -> 0 exposed.")
print(f"  Under the SUPERSEDED pre-repair rule p_correct = max(between, within), the within arm "
      f"would have decided {int(worse_within.sum())} of {len(d19)} cells,")
print(f"  and {int((worse_within & hi).sum())} of those also have "
      f"var_share_between >= {EXPOSURE_THRESHOLD} -- i.e. would have been EXPOSED.")
print(f"  D090 also self-flagged within_null_degenerate on "
      f"{int(d19['within_null_degenerate'].sum())} of {len(d19)} cells, in its OWN repair, "
      f"months before D115.")
pd.DataFrame([dict(
    screen="E0_I0019_availability_forecast", published_rule="between-only (repaired, DEF-4)",
    exposed_under_published=0, superseded_rule="max(p_between, p_within)",
    cells=len(d19), within_arm_would_decide=int(worse_within.sum()),
    would_be_exposed=int((worse_within & hi).sum()),
    screen_self_flagged_within_degenerate=int(d19["within_null_degenerate"].sum()))]).to_csv(
        os.path.join(OUT, "D090_COUNTERFACTUAL.csv"), index=False)

# ============================================================ 7. write
hdr("7. WRITE AUDIT_TABLE.csv")
COLS = ["screen", "candidate", "target", "stratum", "base", "n",
        "null_scheme_recorded", "null_class", "null_permutes_at", "null_level_source",
        "null_source_cite",
        "candidate_level_recorded", "candidate_level_source", "level_recorded",
        "var_share_between", "var_share_entity", "var_share_source", "n_rows_for_var_share",
        "stat_scale", "observed_stat", "dr2_reported",
        "null_mean", "null_mean_source", "null_mean_recorded_by_screen",
        "flag_applicable", "flag_computable", "flag_null_mean_gt_observed",
        "p_decision", "p_familywise", "kill_reason", "kill_reason_corrected",
        "ceiling_recorded", "mde80_fw_used", "blind_used", "is_kill", "is_ceiling",
        "EXPOSURE", "exposure_reason", "exposure_confidence",
        "EXPOSURE_thr0.3", "EXPOSURE_thr0.8"]
for c in COLS:
    if c not in M.columns:
        M[c] = np.nan
M[COLS].to_csv(os.path.join(OUT, "AUDIT_TABLE.csv"), index=False)
print(f"  wrote AUDIT_TABLE.csv  {M[COLS].shape}")

summ = M[M["is_kill"]].groupby(["screen", "null_class", "EXPOSURE"]).size().reset_index(
    name="cells")
summ.to_csv(os.path.join(OUT, "EXPOSURE_BY_SCREEN.csv"), index=False)
print("  wrote EXPOSURE_BY_SCREEN.csv")

# the named ceiling exclusions, auditable
ceil = M[M["is_ceiling"]]
pd.DataFrame(dict(candidate=sorted(pd.unique(ceil["candidate"])))).assign(
    n_cells=lambda t: t["candidate"].map(ceil["candidate"].value_counts()),
    screen="E0_I0024_reb_ast_characterisation",
    note="ARITHMETIC CEILING KILL -- NOT RE-MEASURED (PREREG 5.1)").to_csv(
        os.path.join(OUT, "CEILING_EXCLUSIONS.csv"), index=False)
print(f"  wrote CEILING_EXCLUSIONS.csv  ({len(ceil)} cells, "
      f"{ceil['candidate'].nunique()} distinct candidates)")

json.dump(dict(
    census_cells=len(cen), killed=int(M["is_kill"].sum()),
    exposure=M["EXPOSURE"].value_counts().to_dict(),
    null_class_killed=M.loc[M["is_kill"], "null_class"].value_counts().to_dict(),
    flag_applicable=int(M["flag_applicable"].sum()),
    flag_computable=int(M["flag_computable"].sum()),
    flag_trips=int((M["flag_null_mean_gt_observed"] == 1).sum()),
    null_mean_source=M["null_mean_source"].value_counts().to_dict(),
), open(os.path.join(OUT, "scripts", "_s04.json"), "w"), indent=1)
print("\nDONE.")
