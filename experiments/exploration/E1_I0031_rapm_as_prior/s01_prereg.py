"""STEP 0/PREREG -- build the analysis frame, reproduce D094's winners, hash the candidate list.

ORDER MATTERS.  The candidate list is written and hashed BEFORE any statistic relating a candidate
to an outcome is computed (constraint 7).  The only things computed before the hash are:
  * the analysis frame itself (features, no outcomes touched beyond the D094 reproduction),
  * D094's SELECTED cells, which are read from that screen's frozen _s04.json -- not re-selected.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rp_base as B  # noqa: E402

# ============================================================================== frame
B.hdr("BUILD -- base frame + RAPM + D094 estimators + raw plus-minus")
r, prov = B.load_rapm(verbose=False)
f = B.load_frame()
f = B.attach_rapm(f, r)

# --- coverage / imputation policy (preregistered below) --------------------------------------
RAPM_COLS = ["z_net_100", "z_orapm_100", "z_drapm_100",
             "net_100_lam500", "net_100_lam1000", "net_100_lam2000", "net_100_lam5000",
             "log_total_poss"]
for c in RAPM_COLS:
    m = f.groupby("season")[c].transform("mean")
    f[c + "_imp"] = f[c].astype(float).fillna(m)
f["has_rapm_f"] = f["has_rapm"].astype(float)
f["z_net_x_poss"] = f["z_net_100_imp"] * f["log_total_poss_imp"]

# RAPM is player-season-constant: verify on values (this is what licences the correct-level null).
sub = f[f["has_rapm"]]
for c in ["net_100_lam2000", "z_net_100", "z_orapm_100", "z_drapm_100"]:
    B.assert_constant_within(sub, c)
print("  VERIFIED: every RAPM column is CONSTANT within (season, player_id) -> the honest null "
      "relabels whole player-seasons, not rows.")

# ============================================================================== D094 estimators
B.sub("Rebuilding D094's walk-forward-selected best simple estimator per target")
surf = pd.read_csv(B.SURFACE)
sel = json.load(open(os.path.join(B.D094, "_s04.json")))["selection"]
KEY = ["target", "mode", "memory_kind", "memory_param", "shrink_target", "shrink_k", "floor"]

codes, starts, ns = B.group_bounds(f)
mins = f["y_minutes"].to_numpy(float)
bucket_role = B.role_bucket(f)
BASE_MODES = [(t, m) for t in B.TARGETS for m in
              {"pts": ["equal", "minutes_weighted"], "minutes": ["equal", "minutes_weighted"],
               "fga": ["equal", "minutes_weighted"],
               "ppm": ["ratio_of_prior_sums", "mean_of_prior_ratios"]}[t]]
ND, TGT = {}, {}
for t, mode in BASE_MODES:
    num, den = B.numden(f, t, mode)
    ND[(t, mode)] = (num, den)
    TGT[(t, mode)], _ = B.build_shrink_targets(f, num, den, bucket_role,
                                               float(num.sum() / den.sum()))


def est_for(cell):
    """Rebuild one D094 grid cell's forecast on this frame."""
    t, mode = cell["target"], cell["mode"]
    mem = (cell["memory_kind"], float(cell["memory_param"]))
    sh = (cell["shrink_target"], float(cell["shrink_k"]))
    fl = float(cell["floor"])
    if t == "pts" and mode == "composite":
        a = B.apply_shrink(*B.prior_sums(*ND[("minutes", "equal")], mins, starts, ns, fl, mem),
                           TGT[("minutes", "equal")], sh)
        b = B.apply_shrink(*B.prior_sums(*ND[("ppm", "ratio_of_prior_sums")], mins, starts, ns,
                                         fl, mem), TGT[("ppm", "ratio_of_prior_sums")], sh)
        return a * b
    return B.apply_shrink(*B.prior_sums(*ND[(t, mode)], mins, starts, ns, fl, mem),
                          TGT[(t, mode)], sh)


season = f["season"].to_numpy()
YCOL = {"pts": "y_pts", "minutes": "y_minutes", "fga": "y_fga", "ppm": "r_ppm"}
D081REF = {"pts": "ref_pts", "minutes": "ref_minutes", "fga": "ref_fga", "ppm": "refB_ppm"}
CHAMP = {"pts": "pts__pred_point", "minutes": "minutes__pred_point",
         "fga": "fga__pred_point", "ppm": "mdl_ppm"}
M_WF = np.isin(season, [2023, 2024])
repro = []
SELCELL = {}
for t in B.TARGETS:
    cA = surf.loc[sel[t]["idx_A"], KEY].to_dict()
    cB = surf.loc[sel[t]["idx_B"], KEY].to_dict()
    eA, eB = est_for(cA), est_for(cB)
    # WALK-FORWARD splice, exactly D094's: cell tuned on 2022 scores 2023; tuned on 2022+23 scores
    # 2024.  2022 rows take cell A (they are that cell's OWN tuning rows -> in-sample, and 2022 is
    # therefore EXCLUDED from the headline evaluation stratum, as D094 excluded it).
    e = np.where(season == 2024, eB, eA)
    f["est_" + t] = e
    f["estA_" + t] = eA
    f["estB_" + t] = eB
    SELCELL[t] = {"A": cA, "B": cB}
    got = B.mae(f[YCOL[t]].to_numpy(float)[M_WF], e[M_WF])
    want = float(sel[t]["mae_wf_global"])
    repro.append({"target": t, "mae_wf_rebuilt": got, "mae_wf_D094_stored": want,
                  "abs_diff": abs(got - want),
                  "cellA": " ".join(str(cA[k]) for k in KEY),
                  "cellB": " ".join(str(cB[k]) for k in KEY)})
    print("    %-8s rebuilt wf MAE=%.10f  D094 stored=%.10f  diff=%.2e"
          % (t, got, want, abs(got - want)))
rep = pd.DataFrame(repro)
assert (rep["abs_diff"] < 1e-9).all(), "D094 REPRODUCTION FAILED -- refusing to build on it"
print("  D094 REPRODUCED EXACTLY (all four targets, <1e-9).  Standing on the same ground.")
B.wcsv(rep, "d094_reproduction.csv")

# ============================================================================== plus-minus (STEP 5)
B.sub("Raw per-game plus_minus -> strictly-prior aggregates (a DIFFERENT OBJECT from RAPM)")
man = __import__("screenkit").check_manifest(B.MASTER, verbose=True)
mp = pd.read_parquet(B.MASTER, columns=["game_id", "player_id", "season", "game_date", "minutes",
                                        "plus_minus"])
mp = mp[mp["season"].isin(B.PARTITION)].copy()                     # FILTER-POINT
mp["gdate"] = pd.to_datetime(mp["game_date"])
assert mp["gdate"].max() < pd.Timestamp("2025-01-01")
B.guard(mp, "master_player after filter")
mp["minutes"] = pd.to_numeric(mp["minutes"], errors="coerce").fillna(0.0)
mp["pm"] = pd.to_numeric(mp["plus_minus"], errors="coerce")
mp["appeared"] = mp["minutes"] > 0
mp = mp[mp["appeared"] & mp["pm"].notna()].copy()
mp = mp.sort_values(["season", "player_id", "gdate", "game_id"], kind="stable").reset_index(
    drop=True)
print("  master_player appeared rows with a finite plus_minus, 2021-2024: %d  (seasons %s)"
      % (len(mp), sorted(mp["season"].unique())))

g = mp.groupby(["season", "player_id"], sort=False)
mp["pm_run_mean"] = g["pm"].transform(lambda x: x.shift(1).expanding().mean())
mp["_pmsum"] = g["pm"].transform(lambda x: x.shift(1).cumsum())
mp["_minsum"] = g["minutes"].transform(lambda x: x.shift(1).cumsum())
mp["pm_per36_prior"] = np.where(mp["_minsum"] > 0, 36.0 * mp["_pmsum"] / mp["_minsum"], np.nan)
lam5 = 0.5 ** (1.0 / 5.0)
mp["pm_ewma5"] = g["pm"].transform(
    lambda x: (x.shift(1).ewm(alpha=1 - lam5, adjust=True).mean()))
lam2 = 0.5 ** (1.0 / 2.0)
mp["pm_ewma2"] = g["pm"].transform(
    lambda x: (x.shift(1).ewm(alpha=1 - lam2, adjust=True).mean()))
ps = mp.groupby(["season", "player_id"])["pm"].mean()
lut = {(int(s) + 1, int(p)): float(v) for (s, p), v in ps.items()}
mp["pm_prev_season"] = [lut.get((int(s), int(p)), np.nan)
                        for s, p in zip(mp["season"], mp["player_id"])]
PMC = ["pm_run_mean", "pm_per36_prior", "pm_ewma5", "pm_ewma2", "pm_prev_season"]
f = f.merge(mp[["game_id", "player_id"] + PMC], on=["game_id", "player_id"], how="left",
            validate="1:1")
print("  plus-minus feature coverage on the scored frame:")
print(f[PMC].notna().mean().to_string())
for c in PMC:
    f[c + "_imp"] = f[c].astype(float).fillna(f.groupby("season")[c].transform("mean"))
    f["has_" + c] = f[c].notna().astype(float)

# ============================================================================== base reference cols
B.sub("COMPLETE base reference: EVERY prior measurement of the target already in the frame")
for t in B.TARGETS:
    num, den = ND[(t, "equal" if t != "ppm" else "mean_of_prior_ratios")]
    tg, _ = B.build_shrink_targets(f, num, den, bucket_role, float(num.sum() / den.sum()))
    f["prevseason_" + t] = tg["prior_season"]
    f["prevseason_raw_" + t] = tg["_prior_season_raw"]
    f["lgexp_" + t] = tg["league"]
    f["role_" + t] = tg["role"]
f["rolebucket"] = bucket_role
f["y_ppm"] = f["r_ppm"].astype(float)
f["ref_ppm"] = f["refB_ppm"].astype(float)

BASE_COLS = {
    "pts": ["est_pts", "ref_pts", "pl_pts_mean5", "pl_pts_sd5", "prevseason_pts", "lgexp_pts",
            "role_pts", "pl_games_prior", "pl_minutes_prior", "pl_career_games_prior",
            "pl_prior_season_games"],
    "minutes": ["est_minutes", "ref_minutes", "pl_min_mean5", "pl_min_sd5", "prevseason_minutes",
                "lgexp_minutes", "role_minutes", "pl_games_prior", "pl_minutes_prior",
                "pl_career_games_prior", "pl_prior_season_games"],
    "fga": ["est_fga", "ref_fga", "pl_fga_mean5", "pl_fga_sd5", "prevseason_fga", "lgexp_fga",
            "role_fga", "pl_games_prior", "pl_minutes_prior", "pl_career_games_prior",
            "pl_prior_season_games"],
    "ppm": ["est_ppm", "ref_ppm", "refA_ppm", "prevseason_ppm", "lgexp_ppm", "role_ppm",
            "pl_games_prior", "pl_minutes_prior", "pl_career_games_prior",
            "pl_prior_season_games"],
}
for t, cs in BASE_COLS.items():
    miss = [c for c in cs if c not in f.columns]
    assert not miss, (t, miss)
    nn = f[cs].notna().all(axis=1).mean()
    print("    %-8s %2d base columns, all-finite on %.4f of rows" % (t, len(cs), nn))

# strata
f["m_wf"] = np.isin(f["season"].to_numpy(), [2023, 2024])
f["m_stratum"] = ((f["pl_games_prior"] >= 8) & (f["pl_min_mean5"] >= 24))
f["m_datapoor"] = f["pl_games_prior"] < 3
print("  strata: wf_eval=%d  decision_stratum=%d  decision_stratum&wf=%d  data_poor=%d  "
      "data_poor&wf=%d" % (int(f["m_wf"].sum()), int(f["m_stratum"].sum()),
                           int((f["m_wf"] & f["m_stratum"]).sum()), int(f["m_datapoor"].sum()),
                           int((f["m_wf"] & f["m_datapoor"]).sum())))

B.assert_partition_values(f[[c for c in f.columns if c not in ("row_uid",)]], "analysis frame")
f.to_parquet(os.path.join(B.OUT, "analysis_frame.parquet"), index=False)
print("  wrote analysis_frame.parquet  shape=%s" % (f.shape,))

# ============================================================================== PREREGISTRATION
B.hdr("PREREGISTRATION -- candidate list frozen and hashed BEFORE any candidate/outcome statistic")
RAPM_CANDIDATES = [
    ("R01", "net_100_lam2000_imp", "PRIMARY. Net RAPM at FIXED lambda=2000 -> comparable across "
                                   "emit seasons. Season-level, strictly prior."),
    ("R02", "net_100_lam500_imp", "Net RAPM, weakest regularisation (most player-specific)."),
    ("R03", "net_100_lam1000_imp", "Net RAPM, lambda=1000."),
    ("R04", "net_100_lam5000_imp", "Net RAPM, strongest fixed regularisation."),
    ("R05", "z_net_100_imp", "Net RAPM at the artifact's own lambda_chosen, z-scored WITHIN emit "
                             "season (lambda varies 50x across seasons -- see s00)."),
    ("R06", "z_orapm_100_imp", "OFFENSIVE RAPM, within-season z."),
    ("R07", "z_drapm_100_imp", "DEFENSIVE RAPM, within-season z."),
    ("R08", "log_total_poss_imp", "log(1+total possessions) behind the RAPM fit = its reliability."),
    ("R09", "has_rapm_f", "Indicator that a RAPM value EXISTS. Its absence is itself information "
                          "(a true rookie has no prior-season possessions)."),
    ("R10", "z_net_x_poss", "z_net_100 x log_total_poss: does RAPM matter more when better "
                            "estimated?"),
]
PM_CANDIDATES = [
    ("P01", "pm_ewma5_imp", "EWMA (half-life 5) of the player's own prior SAME-SEASON per-game "
                            "plus_minus. GAME-level -- can move within season."),
    ("P02", "pm_ewma2_imp", "EWMA half-life 2 of prior same-season plus_minus (short memory)."),
    ("P03", "pm_run_mean_imp", "Expanding mean of prior same-season plus_minus."),
    ("P04", "pm_per36_prior_imp", "sum(prior plus_minus)/sum(prior minutes) x 36, same season."),
    ("P05", "pm_prev_season_imp", "The player's PREVIOUS-SEASON mean plus_minus (unadjusted "
                                  "season-level analogue of RAPM)."),
]
CONTROLS = [
    ("N01", "rapm_negcontrol", "NEGATIVE CONTROL. R01's values relabelled across player-seasons "
                               "WITHIN emit season, fixed seed 20260808. Must show ~zero."),
    ("N02", "rapm_noop_placebo", "NO-OP PLACEBO. R01 multiplied by 1.0 and re-derived through the "
                                 "same code path; VERIFIED to change no value (and therefore to "
                                 "reproduce the real statistic to machine precision)."),
    ("N03", "rapm_perturbed_placebo", "PERTURBED PLACEBO. R01 + 1e-6*sd; VERIFIED to actually "
                                      "change every value, so the placebo machinery is live."),
]
REFERENCE_VARIANTS = [
    ("V0", "D094 selected cell, UNCHANGED (shrink target as selected).  THE INCUMBENT."),
    ("V1", "shrink target := RAPM-only map g_S(rapm), g fitted on seasons < S."),
    ("V2", "shrink target := 0.5*prior_season_mean + 0.5*g_S(rapm)  (fixed weight, no fitting)."),
    ("V3", "shrink target := prior_season_mean where it exists, else g_S(rapm)  (coverage fill)."),
    ("V4", "shrink target := h_S(prior_season_mean, rapm), h an OLS fitted on seasons < S."),
    ("V5", "shrink target := h_S(prior_season_mean) only -- V4 WITHOUT RAPM.  This is the "
           "DECOMPOSITION control: it isolates 'refit the map' from 'add RAPM'."),
]
COLDSTART_VARIANTS = [
    ("C0", "D092 P5d_blend_k2: lambda(n)*own_running_mean + (1-lambda)*(league+depth+draft), "
           "lambda(n)=n/(n+2).  THE INCUMBENT, read from E1_I0020 (READ ONLY, credited)."),
    ("C1", "C0 with the structural prior REPLACED by g_S(rapm)."),
    ("C2", "C0 with the structural prior AUGMENTED by g_S(rapm) (equal-weight average)."),
    ("C3", "C0's structural prior + a RAPM term fitted walk-forward on seasons < S."),
    ("C4", "structural prior = g_S(rapm) ONLY, no depth, no draft.  Isolates RAPM's own content."),
]
lines = []
lines.append("# E1_I0031 -- PRESELECTED CANDIDATES (frozen before any candidate/outcome statistic)")
lines.append("")
lines.append("Seed 20260808.  Exploration partition 2021-2024; RAPM emit seasons 2025 and 2026 "
             "dropped at the filter-point (579 of 1,177 rows).")
lines.append("")
lines.append("## RAPM candidates (STEP 2 / STEP 3 / STEP 4)")
lines.append("")
lines.append("| id | column | what it is |")
lines.append("|---|---|---|")
for i, c, d in RAPM_CANDIDATES:
    lines.append("| %s | `%s` | %s |" % (i, c, d))
lines.append("")
lines.append("## Raw per-game plus-minus candidates (STEP 5 -- tested SEPARATELY, never pooled "
             "with RAPM)")
lines.append("")
lines.append("| id | column | what it is |")
lines.append("|---|---|---|")
for i, c, d in PM_CANDIDATES:
    lines.append("| %s | `%s` | %s |" % (i, c, d))
lines.append("")
lines.append("## Controls")
lines.append("")
lines.append("| id | column | what it is |")
lines.append("|---|---|---|")
for i, c, d in CONTROLS:
    lines.append("| %s | `%s` | %s |" % (i, c, d))
lines.append("")
lines.append("## Reference-component variants (STEP 3)")
lines.append("")
for i, d in REFERENCE_VARIANTS:
    lines.append("- **%s** -- %s" % (i, d))
lines.append("")
lines.append("## Cold-start variants (STEP 4)")
lines.append("")
for i, d in COLDSTART_VARIANTS:
    lines.append("- **%s** -- %s" % (i, d))
lines.append("")
lines.append("## COMPLETE base reference per target (STEP 2)")
lines.append("")
lines.append("Every prior measurement of the target already present in D081's frame, plus D094's "
             "tuned best simple estimator, which is the strongest prior-only forecast known to "
             "this programme.  A reference missing any of these would make a RAPM 'survivor' a "
             "reference-incompleteness artefact -- the top-ranked source of false results here.")
lines.append("")
for t, cs in BASE_COLS.items():
    lines.append("- **%s** (%d): %s" % (t, len(cs), ", ".join("`%s`" % c for c in cs)))
lines.append("")
lines.append("## Evaluation strata (fixed here, not chosen later)")
lines.append("")
lines.append("- `wf_eval`  : seasons 2023+2024 (%d rows).  D094's walk-forward evaluation rows; "
             "2022 is a tuning season and is EXCLUDED from the headline." % int(f["m_wf"].sum()))
lines.append("- `decision_stratum` : `pl_games_prior >= 8 AND pl_min_mean5 >= 24` (D081), "
             "intersected with `wf_eval` (%d rows)." % int((f["m_wf"] & f["m_stratum"]).sum()))
lines.append("- `data_poor` : `pl_games_prior < 3` (D092's tier), %d rows total, %d in wf_eval."
             % (int(f["m_datapoor"].sum()), int((f["m_wf"] & f["m_datapoor"]).sum())))
lines.append("")
lines.append("## Denominator rule (D099)")
lines.append("")
lines.append("Every dR2 reported for a SUBSET is additionally reported on the FULL stratum's SST "
             "so the two are comparable; the column `sst_basis` names which is which.")
lines.append("")
lines.append("## Null construction (constraint 4)")
lines.append("")
lines.append("RAPM is CONSTANT within (season, player_id) -- verified on values in this script. "
             "The null therefore RELABELS WHOLE PLAYER-SEASONS.  A within-player shuffle would be "
             "anticonservative and the kit refuses it; where a within-group null is needed for a "
             "game-level series (the plus-minus candidates) the CYCLIC SHIFT variant is used "
             "(credit: E1_I0021/hd_base.py, D093).  Cluster-robust SEs are NOT used as a "
             "substitute anywhere.")
txt = "\n".join(lines) + "\n"

canon = "\n".join(
    ["RAPM|%s|%s" % (i, c) for i, c, _ in RAPM_CANDIDATES]
    + ["PM|%s|%s" % (i, c) for i, c, _ in PM_CANDIDATES]
    + ["CTRL|%s|%s" % (i, c) for i, c, _ in CONTROLS]
    + ["REFVAR|%s" % i for i, _ in REFERENCE_VARIANTS]
    + ["COLD|%s" % i for i, _ in COLDSTART_VARIANTS]
    + ["BASE|%s|%s" % (t, ",".join(cs)) for t, cs in sorted(BASE_COLS.items())])
h = B.sha256_text(canon)
txt += "\n---\n\n**CANDIDATE LIST SHA256 (canonical form, sorted-stable):** `%s`\n" % h
txt += "\n- RAPM candidates: %d\n- plus-minus candidates: %d\n- controls: %d\n" \
       "- reference variants: %d\n- cold-start variants: %d\n- base columns: %d across 4 targets\n" \
       % (len(RAPM_CANDIDATES), len(PM_CANDIDATES), len(CONTROLS), len(REFERENCE_VARIANTS),
          len(COLDSTART_VARIANTS), sum(len(v) for v in BASE_COLS.values()))
txt += "\n**ADDED after preregistration: 0.  DROPPED after preregistration: 0.**  " \
       "(Re-asserted by every downstream step against this hash; a mismatch aborts the step.)\n"
open(os.path.join(B.OUT, "CANDIDATES_PRESELECTED.md"), "w").write(txt)
print("  CANDIDATE LIST SHA256 = %s" % h)
print("  wrote CANDIDATES_PRESELECTED.md  (%d RAPM, %d plus-minus, %d controls, %d ref variants, "
      "%d cold-start variants)" % (len(RAPM_CANDIDATES), len(PM_CANDIDATES), len(CONTROLS),
                                   len(REFERENCE_VARIANTS), len(COLDSTART_VARIANTS)))

B.jdump({"candidate_sha256": h,
         "n_added_after_prereg": 0, "n_dropped_after_prereg": 0,
         "rapm_candidates": RAPM_CANDIDATES, "pm_candidates": PM_CANDIDATES,
         "controls": CONTROLS, "reference_variants": REFERENCE_VARIANTS,
         "coldstart_variants": COLDSTART_VARIANTS, "base_cols": BASE_COLS,
         "d094_selected_cells": SELCELL,
         "d094_reproduction": rep.to_dict("records"),
         "strata": {"wf_eval": int(f["m_wf"].sum()),
                    "decision_stratum_wf": int((f["m_wf"] & f["m_stratum"]).sum()),
                    "data_poor": int(f["m_datapoor"].sum()),
                    "data_poor_wf": int((f["m_wf"] & f["m_datapoor"]).sum())},
         "rapm_row_coverage": float(f["has_rapm"].mean())}, "_prereg.json")
print("\nPREREG COMPLETE.")
