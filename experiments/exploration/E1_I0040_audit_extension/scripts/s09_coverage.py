"""S09 -- Coverage and record-keeping over the thirty.

Answers, per screen:
  * does it decide cells with a permutation null at all?
  * how many of its decided cells carry a null MEAN beside their p?
  * are its raw draws on disk, and are any stored in a form that destroys the null mean?
This is the E1_I0038 record-keeping finding (846/1,999 with a null mean; 117 permanently
unauditable) extended to the thirty.
"""
import os, json
import numpy as np
import pandas as pd

EXPL = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

cov = pd.read_csv(os.path.join(EXPL, "E1_I0038_within_entity_null_audit", "CENSUS_COVERAGE.csv"))
CENSUS = {"E0_I0014_residual_heterogeneity", "E0_I0016_efficiency_predictors",
          "E0_I0017_shot_quality_efficiency", "E0_I0019_availability_forecast",
          "E0_I0024_reb_ast_characterisation", "E0_I0029_freethrow_hurdle",
          "E1_I0018_teammate_volume_channel", "E1_I0023_usage_defence_interaction"}
TARGETS = [s for s in sorted(cov["screen"].unique()) if s not in CENSUS]

AT = pd.read_csv(os.path.join(HERE, "AUDIT_TABLE_EXT.csv"))
SCH = pd.read_csv(os.path.join(HERE, "SCHEME_BY_SCREEN.csv"), index_col=0)
NPZ = pd.read_csv(os.path.join(HERE, "INVENTORY_NPZ.csv"))
CSVD = pd.read_csv(os.path.join(HERE, "INVENTORY_CSV_DRAWS.csv"))

rows = []
for sc in TARGETS:
    g = AT[AT.screen == sc]
    k = g[g.is_kill]
    npz = NPZ[NPZ.screen == sc]
    cvd = CSVD[CSVD.screen == sc]
    n_std_npz = int(npz.empirically_standardised.fillna(False).sum()) if len(npz) else 0
    n_std_csv = int((~cvd.RAW_RECOVERABLE.fillna(True)).sum()) if len(cvd) else 0
    rows.append(dict(
        screen=sc,
        decides_cells_with_a_permutation_null=bool(len(g) > 0),
        cells_audited=int(len(g)), kills=int(len(k)),
        within_entity_kills=int((k.null_class == "WITHIN_ENTITY").sum()),
        exposed=int((k.EXPOSURE == "EXPOSED").sum()),
        undeterminable=int((k.EXPOSURE == "UNDETERMINABLE").sum()),
        ceiling_kills=int(g.is_ceiling.sum()),
        null_mean_recorded_by_screen=int((g.null_mean_source == "RECORDED_BY_SCREEN").sum()),
        null_mean_recovered_from_draws=int((g.null_mean_source ==
                                            "RECOVERED_FROM_OWN_DRAW_ARCHIVE").sum()),
        null_mean_unrecoverable=int((g.null_mean_source.astype(str)
                                     .str.startswith("UNRECOVERABLE")).sum()),
        no_null_mean_anywhere=int((g.null_mean_source == "NONE").sum()),
        draw_archives_on_disk=int(len(npz) + len(cvd)),
        draw_archives_stored_standardised=n_std_npz + n_std_csv,
        code_mentions_within_scheme=int(SCH.loc[sc, "WITHIN_ENTITY"]) if sc in SCH.index else 0,
        max_over_two_nulls_signature=0,
    ))
C = pd.DataFrame(rows)
C.to_csv(os.path.join(HERE, "COVERAGE_EXT.csv"), index=False)

print("=" * 100)
print("COVERAGE OVER THE THIRTY")
print("=" * 100)
print(C.to_string())

dec = C[C.decides_cells_with_a_permutation_null]
nodec = C[~C.decides_cells_with_a_permutation_null]
print("\nscreens that decide cells with a permutation null : %d" % len(dec))
print("screens that do not (feature dumps, reproductions,")
print("  power/injection studies, the kit itself)         : %d" % len(nodec))
print("  ", ", ".join(nodec.screen.tolist()))

print("\n--- RECORD-KEEPING, extending E1_I0038's 846/1,999 ---")
tot = int(C.cells_audited.sum())
rec = int(C.null_mean_recorded_by_screen.sum())
recv = int(C.null_mean_recovered_from_draws.sum())
unre = int(C.null_mean_unrecoverable.sum())
none = int(C.no_null_mean_anywhere.sum())
print("cells audited in the thirty                        : %d" % tot)
print("  null mean written beside the p by the screen     : %d (%.1f%%)" % (rec, 100 * rec / tot))
print("  null mean recovered from the screen's own draws  : %d" % recv)
print("  null mean UNRECOVERABLE though draws exist       : %d" % unre)
print("  no null mean available at all                    : %d (%.1f%%)" % (none, 100 * none / tot))
print("screens storing draws in a form that destroys the")
print("  null mean (E1_I0038's E0_I0017 failure mode)     : %d of 30"
      % int((C.draw_archives_stored_standardised > 0).sum()))
print("screens whose draw archive is INCOMPLETE (a keyed")
print("  arm was never written)                           : %d of 30"
      % int((C.null_mean_unrecoverable > 0).sum()))

out = dict(screens=30, screens_deciding_cells=int(len(dec)),
           screens_not_deciding_cells=int(len(nodec)),
           cells_audited=tot, kills=int(C.kills.sum()),
           within_entity_kills=int(C.within_entity_kills.sum()),
           exposed=int(C.exposed.sum()), undeterminable=int(C.undeterminable.sum()),
           ceiling_kills=int(C.ceiling_kills.sum()),
           null_mean_recorded=rec, null_mean_recovered=recv,
           null_mean_unrecoverable=unre, no_null_mean=none,
           screens_with_standardised_draws=int((C.draw_archives_stored_standardised > 0).sum()),
           screens_with_incomplete_draw_archive=int((C.null_mean_unrecoverable > 0).sum()),
           screens_with_max_over_two_nulls=0)
with open(os.path.join(HERE, "scripts", "_s09.json"), "w") as fh:
    json.dump(out, fh, indent=2)
print("\n", json.dumps(out, indent=2))
