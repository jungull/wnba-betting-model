"""S19 -- flag the Type-I-uncalibrated survivors and assemble FINDINGS.json."""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)

BN = pd.read_csv(os.path.join(HERE, "BROKEN_NULLS.csv"))
CS = pd.read_csv(os.path.join(HERE, "COMPOSITE_SWEEP.csv"))
TI = pd.read_csv(os.path.join(HERE, "TYPE_I_CALIBRATION.csv"))
IJ = pd.read_csv(os.path.join(HERE, "INJECTION_VERIFICATION.csv"))
S00 = json.load(open(os.path.join(HERE, "scripts", "_s00.json")))

TI["candidate"] = TI["cell"].str.split("|").str[0]
timap = TI.set_index("candidate")["typeI_composed2"].to_dict()
print("Type-I measured on candidates:", timap)

out = {}
for pre in ["A4", "A1"]:
    p = os.path.join(HERE, "SURVIVOR_RANKING_%s.csv" % pre)
    S = pd.read_csv(p)
    S["candidate"] = S["cell"].str.split("|").str[0]
    S["typeI_composed2_measured_on_this_candidate"] = S["candidate"].map(timap)
    S["typeI_source"] = np.where(S["candidate"].isin(timap),
                                 "MEASURED on one cell of this candidate, applied to its "
                                 "siblings -- an EXTRAPOLATION, labelled as such",
                                 "NOT MEASURED")
    S["typeI_flag"] = np.where(
        S["typeI_composed2_measured_on_this_candidate"] > 0.0728,   # 0.05 + 2 MC se
        "TYPE_I_UNCALIBRATED", "OK_OR_UNMEASURED")
    # injection-verified floors where available
    ij = IJ.set_index("cell")
    S["E_inj"] = [ij.loc[c, "E_inj"] if c in ij.index else np.nan for c in S["cell"]]
    S["floor_basis"] = np.where(S["E_inj"].notna(), "INJECTION_VERIFIED", "ANALYTIC")
    S.to_csv(p, index=False)
    n_bad = int((S["typeI_flag"] == "TYPE_I_UNCALIBRATED").sum())
    print("\n%s survivors: %d, of which TYPE_I_UNCALIBRATED %d -> credible %d"
          % (pre, len(S), n_bad, len(S) - n_bad))
    print(S[["cell", "%s_observed_dr2" % pre, "%s_p_familywise" % pre,
             "typeI_composed2_measured_on_this_candidate", "typeI_flag",
             "floor_basis"]].to_string(index=False))
    out["survivors_%s" % pre] = dict(
        n=len(S), n_type_I_uncalibrated=n_bad, n_credible=len(S) - n_bad,
        cells=S["cell"].tolist(),
        credible_cells=S.loc[S["typeI_flag"] != "TYPE_I_UNCALIBRATED", "cell"].tolist())

IS_COMP = CS["candidate_class"].astype(str).str.startswith(("COMPOSITE", "BUNDLE"))
adeq = BN[BN["d103_classification"] == "ADEQUATELY_POWERED"]
rem = BN[BN["resolution"] == "RE_MEASURED_COMPOSED2"]

F = dict(
  screen="E1_I0044_broken_nulls_and_composites",
  prereg_sha256="d25fc5ec7898779da0082e888b974cfb62689a2356729efe07557a2857f24c7e",
  partition="2021-2024 exploration only; 2025/26 never opened; every frame asserted "
            "season<=2024 and gdate<2025-01-01 before use",
  anchors_reproduced_before_any_new_statistic=dict(
      d103_cells=S00["A1_n_cells"], d103_blind=S00["A1_n_blind"], d103_share=S00["A1_share"],
      tstat_family=S00["A2_n_tstat_cells"], degenerate_gt5=S00["A3_n_degenerate_gt5"],
      sd_exactly_zero=S00["A4_n_sd_exactly_zero"], broken_total=S00["A5_n_broken_total"],
      broken_recorded_adequate=S00["A5b_n_broken_recorded_adequate"],
      E0_I0014_vsb_max_abs_error=0.0,
      E0_I0014_t_classical_max_rel_error=3.939e-15,
      E0_I0014_t_classical_bitwise_exact="276 of 348",
      E0_I0014_null_sd_max_abs_error=2.220e-16,
      E0_I0014_p_correct_level_mismatches=0,
      E0_I0019_sd_max_abs_error=1.456e-3, E0_I0019_p_mismatches=0),
  debt1_the_73=dict(
      total=int(len(BN)),
      mechanism_M_VOID=int(BN["mechanism"].str.startswith("M-VOID").sum()),
      mechanism_M_WITHIN=int(BN["mechanism"].str.startswith("M-WITHIN").sum()),
      mechanism_M_BETWEEN=int(BN["mechanism"].str.startswith("M-BETWEEN").sum()),
      resolution=BN["resolution"].value_counts().to_dict(),
      statistic_blindness_min_change=2.303861e-02,
      statistic_blindness_n_immune=0, statistic_blindness_n_tested=72,
      permutation_set_trivially_small_cells=0,
      cells_below_six_blocks=0,
      block_counts=dict(A1_FULL_player=475, A1_FULL_team=36,
                        A4_CLEAN_DEC_player=174, A4_CLEAN_DEC_team=24),
      corrected_classification_like_for_like_A1=BN[
          "corrected_classification_LIKE_FOR_LIKE_A1"].value_counts().to_dict(),
      corrected_classification_decision_stratum_A4=BN[
          "corrected_classification_DECISION_STRATUM_A4"].value_counts().to_dict()),
  the_35=dict(
      n=int(len(adeq)),
      like_for_like_A1=adeq["corrected_classification_LIKE_FOR_LIKE_A1"].value_counts().to_dict(),
      decision_stratum_A4=adeq[
          "corrected_classification_DECISION_STRATUM_A4"].value_counts().to_dict(),
      void_18=sorted(adeq.loc[adeq["mechanism"].str.startswith("M-VOID"), "cell"].tolist())),
  repaired_null=dict(
      name="COMPOSED-2",
      construction="donor block drawn at random within season, then len(b) values resampled "
                   "uniformly from the WHOLE donor block; one shared gather index per draw "
                   "across all 58 candidates so max-|t| stays valid",
      draws=2000, seed=20260808,
      functioning_cells_A1="330 of 348",
      median_degeneracy_ratio_A1=1.3259, median_abs_mean_signed_t_A1=0.0230,
      type_I_measured=TI[["cell", "typeI_composed2",
                          "typeI_e0_i0014_level_matched" if
                          "typeI_e0_i0014_level_matched" in TI.columns
                          else "typeI_E0_I0014_level_matched",
                          "typeI_row_naive"]].to_dict("records"),
      injection=IJ[["cell", "mde80_analytic", "E_inj",
                    "ratio_analytic_over_injected"]].to_dict("records"),
      storage="signed, unstandardised, every arm, nulls/composed2_null_*.npz; np.abs is used "
              "at no storage site"),
  debt2_composite_sweep=dict(
      screens_in_programme=38, screens_that_decide_cells=23,
      cells_in_population=4084, pairs_swept=int(len(CS)),
      composites=int(IS_COMP.sum()),
      atomic=int(CS["candidate_class"].astype(str).str.startswith("ATOMIC").sum()),
      not_a_feature=int(CS["candidate_class"].astype(str).str.startswith("NOT_A_FEATURE").sum()),
      construction_undeterminable=int(
          CS["candidate_class"].astype(str).str.startswith("UNDETERMINABLE").sum()),
      verdicts_among_composites=CS.loc[IS_COMP, "composite_verdict"].value_counts().to_dict(),
      exposed=CS.loc[CS["composite_verdict"] == "EXPOSED",
                     ["screen", "candidate"]].to_dict("records"),
      exposed_previously_known=1,
      exposed_new=int((CS["composite_verdict"] == "EXPOSED").sum()) - 1,
      undeterminable_composites=CS.loc[IS_COMP & (CS["composite_verdict"] == "UNDETERMINABLE"),
                                       ["screen", "candidate"]].to_dict("records"),
      undeterminable_entered=51, undeterminable_resolved_by_measurement=23,
      exposed_under_the_narrow_reading_permutation_nulls_only=5),
  arithmetic_ceiling=dict(named_by_E1_I0036=213,
                          all_in_screen="E0_I0024_reb_ast_characterisation",
                          found_among_the_73=0, found_among_exposed_composites=0,
                          excluded=0,
                          note="a ceiling kill is arithmetic and survives every methodological "
                               "revision; none intersected anything re-measured here"),
  prereg_predictions=dict(
      P1="HELD for composed-2 (54/54 non-void broken cells function on every arm); FAILED for "
         "composed-1 (28/72 on A1) -- see DEFECTS D-1",
      P2="HELD -- the void 18 are PERMANENTLY UNVERIFIABLE on every arm",
      P3="FAILED on A1 (17 of 35 remain adequately powered, predicted at most 5); HELD on A4 "
         "(0 of 35)",
      P4="FAILED -- 37 of 54 re-measured cells have composed-2 p < 0.05 on A4",
      P5="second clause HELD (15 exposed <= 20); first clause FAILED (174/540 = 32.2% "
         "composites, predicted < 25%)"),
)
with open(os.path.join(HERE, "FINDINGS.json"), "w") as fh:
    json.dump(F, fh, indent=2, default=str)
print("\nwrote FINDINGS.json")
print("DONE s19")
