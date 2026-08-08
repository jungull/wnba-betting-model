"""S08 -- Can the 32 exposed cells be discharged from disk, without a refit?

E1_I0038 discharged all 83 of its exposed cells with zero refitting because the conjunction
screens ran BOTH arms. E1_I0031 ran ONE null per candidate, chosen by that candidate's level, so
there is no matched arm for the exposed bundles. But the screen decomposed its own candidate:

    pm_game_level = [pm_ewma5_imp, pm_ewma2_imp, pm_run_mean_imp, pm_per36_prior_imp]  -> cyclic
    pm_prev_season = [pm_prev_season_imp]                                              -> RELABEL
    pm_all         = pm_game_level + pm_prev_season                                    -> cyclic

so for `pm_all` the component the cyclic null is blind to -- pm_prev_season_imp, constant within
player-season -- WAS tested on its own, on the same rows, same statistic, under its correctly
matched between-entity null. That p is already on disk.

Also verified here: that pm_prev_season_imp really is constant within player-season, which is what
makes the cyclic shift the identity on it.
"""
import os, json
import numpy as np
import pandas as pd

EXPL = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALPHA = 0.05
FLOOR = 0.00102          # D103 single-cell floor, as used by E1_I0038 PREREG 5.1
out = {}

# ---------------------------------------------------------------- 1. the constancy check
fr = pd.read_parquet(os.path.join(EXPL, "E1_I0031_rapm_as_prior", "analysis_frame.parquet"))
assert pd.to_numeric(fr["season"], errors="coerce").max() <= 2024, "PARTITION VIOLATION"
g = fr.groupby(["player_id", "season"])["pm_prev_season_imp"]
nun = g.nunique(dropna=True)
spread = g.agg(lambda s: float(np.nanmax(s) - np.nanmin(s)) if s.notna().any() else 0.0)
print("pm_prev_season_imp, over %d player-seasons:" % len(nun))
print("   player-seasons with more than one distinct value : %d" % int((nun > 1).sum()))
print("   max within-player-season spread                  : %.3e" % float(spread.max()))
print("   => a cyclic shift within player-season is the IDENTITY on this column.")
out["pm_prev_season_imp_player_seasons"] = int(len(nun))
out["pm_prev_season_imp_nonconstant_groups"] = int((nun > 1).sum())
out["pm_prev_season_imp_max_within_spread"] = float(spread.max())

# contrast: the game-level columns are NOT constant, so the cyclic shift does move them
for c in ["pm_run_mean_imp", "pm_ewma5_imp"]:
    n2 = fr.groupby(["player_id", "season"])[c].nunique(dropna=True)
    print("   %-20s player-seasons with >1 distinct value: %d of %d"
          % (c, int((n2 > 1).sum()), len(n2)))

# ---------------------------------------------------------------- 2. the on-disk discharge
pm = pd.read_csv(os.path.join(EXPL, "E1_I0031_rapm_as_prior", "plusminus_separate.csv"))
pm = pm[pm["null"].notna() & pm["perm_p"].notna()]
key = ["target", "over", "stratum"]
gl = pm[pm.added == "pm_game_level"].set_index(key)
al = pm[pm.added == "pm_all"].set_index(key)
ps = pm[pm.added == "pm_prev_season"].set_index(key)

rows = []
for k in al.index:
    if k not in gl.index or k not in ps.index:
        continue
    a, gg, p = al.loc[k], gl.loc[k], ps.loc[k]
    rows.append(dict(
        target=k[0], over=k[1], stratum=k[2], n=a["n"],
        dr2_pm_all=a["dr2_own_sst"], p_pm_all_CYCLIC_BLIND=a["perm_p"],
        dr2_pm_game_level=gg["dr2_own_sst"], p_pm_game_level_CYCLIC_BLIND=gg["perm_p"],
        dr2_increment_from_the_blind_component=a["dr2_own_sst"] - gg["dr2_own_sst"],
        dr2_pm_prev_season_alone=p["dr2_own_sst"],
        p_pm_prev_season_MATCHED_RELABEL_NULL=p["perm_p"],
        blind_component_null_is=p["null"],
        blind_component_killed_under_its_own_matched_null=bool(p["perm_p"] >= ALPHA),
        over_d103_single_cell_floor=bool(abs(a["dr2_own_sst"]) > FLOOR)))
DIS = pd.DataFrame(rows)
DIS.to_csv(os.path.join(HERE, "EXPOSED_DISCHARGE.csv"), index=False)
print("\n" + "=" * 78)
print("DISCHARGE OF THE `pm_all` EXPOSED CELLS -- MATCHED ARM ALREADY ON DISK")
print("=" * 78)
print(DIS.to_string())
nd = int(DIS.blind_component_killed_under_its_own_matched_null.sum())
print("\n  blind component (pm_prev_season_imp) killed under its OWN correctly matched "
      "between-entity relabel null in %d of %d pm_all cells." % (nd, len(DIS)))
print("  max |dR2 the blind component adds to pm_all| = %.3e"
      % float(DIS.dr2_increment_from_the_blind_component.abs().max()))
out["pm_all_cells"] = int(len(DIS))
out["pm_all_blind_component_killed_matched"] = nd
out["pm_all_max_blind_increment"] = float(DIS.dr2_increment_from_the_blind_component.abs().max())

# ---------------------------------------------------------------- 3. triage of what remains
print("\n" + "=" * 78)
print("TRIAGE -- THE FROZEN E1_I0038 RULE (PREREG 5.1) APPLIED UNCHANGED")
print("=" * 78)
AT = pd.read_csv(os.path.join(HERE, "AUDIT_TABLE_EXT.csv"))
EX = AT[(AT.is_kill) & (AT.EXPOSURE == "EXPOSED")].copy()
EX["dischargeable_from_disk"] = EX.candidate == "pm_all"
EX["eligible_for_remeasurement"] = (EX.over_d103_single_cell_floor & ~EX.dischargeable_from_disk)
print("exposed kills                                              : %d" % len(EX))
print("  ... dischargeable from disk (pm_all: blind component      : %d"
      % int(EX.dischargeable_from_disk.sum()))
print("      independently killed under its matched relabel null)")
print("  ... below D103's single-cell floor of %.5f, where no null : %d"
      % (FLOOR, int((~EX.over_d103_single_cell_floor).sum())))
print("      can produce a lead")
print("  ... ELIGIBLE for re-measurement under the frozen rule      : %d"
      % int(EX.eligible_for_remeasurement.sum()))
el = EX[EX.eligible_for_remeasurement]
print("\n", el[["candidate", "target", "base", "stratum", "n", "observed_stat", "p_decision",
                "null_mean", "z_obs_vs_null"]].to_string())
print("\n  of those eligible, null mean recoverable from disk: %d"
      % int(el.null_mean.notna().sum()))
EX.to_csv(os.path.join(HERE, "EXPOSED_CELLS_EXT.csv"), index=False)
out["exposed_kills"] = int(len(EX))
out["dischargeable"] = int(EX.dischargeable_from_disk.sum())
out["below_floor"] = int((~EX.over_d103_single_cell_floor).sum())
out["eligible_for_remeasurement"] = int(EX.eligible_for_remeasurement.sum())
out["eligible_with_recoverable_null_mean"] = int(el.null_mean.notna().sum())

# ---------------------------------------------------------------- 4. null-width contrast on disk
print("\n" + "=" * 78)
print("HOW WIDE IS THE BLIND NULL?  Same screen, same rows, same statistic, two schemes.")
print("(reported as evidence of null width only; D101 forbids treating it as a repriced p)")
print("=" * 78)
w = []
for k in gl.index:
    if k not in ps.index:
        continue
    w.append(dict(target=k[0], over=k[1], stratum=k[2],
                  null_p95_CYCLIC_within=gl.loc[k, "null_p95"],
                  null_p95_RELABEL_between=ps.loc[k, "null_p95"],
                  ratio=gl.loc[k, "null_p95"] / ps.loc[k, "null_p95"]))
W = pd.DataFrame(w)
W.to_csv(os.path.join(HERE, "NULL_WIDTH_CONTRAST.csv"), index=False)
print(W.to_string())
print("\n  median cyclic/relabel null p95 ratio = %.2fx" % float(W.ratio.median()))
out["median_null_width_ratio_cyclic_over_relabel"] = float(W.ratio.median())

with open(os.path.join(HERE, "scripts", "_s08.json"), "w") as fh:
    json.dump(out, fh, indent=2)
print("\n", json.dumps(out, indent=2))
