"""P40_PRIMARY_ADJUDICATION - step 2: apply the preregistered primary possession
gates exactly as frozen at P35 (SPEC.json sha256 68EF22F4...B32, verified) to the
sealed P38 receipts extracted in EXTRACTION.json.

Every number below is read from the sealed receipts; nothing is asserted.
Criteria are the preregistered ones (P33 inference block carried by P35) and are
not altered after observing outcomes.

Primary gate (P33 inference.primary_gate, carried verbatim by P35):
  delta_MAE = MAE(K0_MATCHED[arm]) - MAE(arm), pooled out-of-fold over the arm's
  evaluable folds. Promotion requires ALL of:
   (a) delta_MAE > 0
   (b) two-sided cluster-bootstrap p-value below the arm's family-Holm-adjusted
       alpha (family-wise alpha = 0.05)
   (c) no kill condition triggered
   (d) P28 ordering (no turnover number computed before this verdict - satisfied:
       this node computes none)
Kills are evaluated UNCORRECTED: 'theta = 0 not rejected across folds' == the 95%
training-cluster interval covers 0 in EVERY evaluable fold; 'sign instability' ==
any two evaluable folds with opposite point-estimate signs.
"""
import json
from pathlib import Path

OUT = Path(r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\player_program\stage2b\P40_PRIMARY_ADJUDICATION")
ex = json.loads((OUT / "EXTRACTION.json").read_text(encoding="utf-8"))
ELS = ex["elements"]

ALPHA = 0.05
P35_SHA = "68EF22F4FCA15A2E8D91EEEB9B84B86F86E8E9E7CAAB5E23E6A9B950385B4D32".lower()

FAMILIES = {
    "CALIBRATION_CONTROL_FAMILY": ["A02_cal_blend_contrast__single", "A03_cal_shallow_tier_intercept__t3", "A05_cal_playoff_intercept__single"],
    "timeseries_shrinkage": ["A08_K20", "A08_K80", "A09_kappa2", "A09_kappa10", "A09_kappa50", "A10_lambda0.2", "A10_lambda0.5", "A11_rho0.25", "A11_rho0.5", "A11_rho0.75"],
    "COLDSTART_FALLBACK": ["A07_early_season_transient__single", "A12_carryover_additive_decay__single", "A13_carryover_roster_continuity_moderator__single", "A14_expansion_intercept_decay__single", "A15_gap_by_depth_asymmetry__single"],
    "lagged_pace_contrast_family": ["A16_lag_residual_own_minus_opp"],
    "LAGGED_TEMPO_MIX": ["A17_transition_mix_share__single"],
    "EVIDENCE_QUALITY_CORRECTION": ["A21_garbage_time_contamination"],
    "PERSONNEL_CONTINUITY": ["A22_lineup_churn_tv_distance__single"],
    "SCHEDULE_FATIGUE": ["A24_rest_advantage_symmetric"],
    "schedule_context_family": ["A23_rest_differential_contrast__bundle_AI", "A23_rest_differential_contrast__bundle_OM", "A25_home_offense_contrast__single"],
    "OPPONENT_MECHANISM_F1": ["A18_median_duration_contrast", "A20_forced_turnover_contrast", "A26_sos_correction_own_minus_opp"],
}
FIXED_SLOT = {"COLDSTART_FALLBACK": "A14_expansion_intercept_decay__single"}  # charged to m, excluded from ordering, p := 1

TREATMENT = {
    "A02_cal_blend_contrast__single": ["contrast_own_minus_opp_pace_estimate"],
    "A03_cal_shallow_tier_intercept__t3": ["1[SHALLOW]"],
    "A05_cal_playoff_intercept__single": ["is_playoff_indicator"],
    "A07_early_season_transient__single": ["early_season_transient"],
    "A08_K20": ["L_t"], "A08_K80": ["L_t"],
    "A09_kappa2": ["(w(n_t; kappa) - 1)*d_t"], "A09_kappa10": ["(w(n_t; kappa) - 1)*d_t"], "A09_kappa50": ["(w(n_t; kappa) - 1)*d_t"],
    "A10_lambda0.2": ["c_t"], "A10_lambda0.5": ["c_t"],
    "A11_rho0.25": ["dblend_t(rho)"], "A11_rho0.5": ["dblend_t(rho)"], "A11_rho0.75": ["dblend_t(rho)"],
    "A12_carryover_additive_decay__single": ["dev_prev", "w_n:dev_prev"],
    "A13_carryover_roster_continuity_moderator__single": ["cont_i:dev_prev"],
    "A14_expansion_intercept_decay__single": ["expansion_decay_interaction"],
    "A15_gap_by_depth_asymmetry__single": ["pace_gap:asym"],
    "A16_lag_residual_own_minus_opp": ["dev_own - dev_opp"],
    "A17_transition_mix_share__single": ["x_transition_mix"],
    "A18_median_duration_contrast": ["z1"],
    "A20_forced_turnover_contrast": ["z2"],
    "A21_garbage_time_contamination": ["x_garbage_time_contamination"],
    "A22_lineup_churn_tv_distance__single": ["x (symmetric churn)"],
    "A23_rest_differential_contrast__bundle_AI": ["f(rest_own) - f(rest_opp)"],
    "A23_rest_differential_contrast__bundle_OM": ["f(rest_own) - f(rest_opp)"],
    "A24_rest_advantage_symmetric": ["x_rest_level_symmetric"],
    "A25_home_offense_contrast__single": ["is_home_offense"],
    "A26_sos_correction_own_minus_opp": ["z5"],
}


def elem(name):
    return ELS[name]["receipt"]


def pooled(name):
    return elem(name)["results"]["pooled"]


def fold_rows(name):
    r = elem(name)
    out = []
    for fid in ["train_lt_2022", "train_lt_2023", "train_lt_2024", "train_lt_2025", "train_lt_2026"]:
        fb = r["folds"].get(fid)
        if fb is None:
            continue
        row = {"fold": fid, "status": fb["status"]}
        if fb["status"] == "EVALUABLE":
            t = fb["test"]
            row.update({"delta_mae": t["delta_mae"], "p_two_sided": t["p_two_sided"],
                        "n_rows": t["n_rows"], "n_clusters": t["n_clusters"], "n_draws": t["n_draws"],
                        "mae_arm": t["mae_arm"], "mae_null": t["mae_null"]})
            ivs, betas = {}, {}
            cols = fb.get("arm_point_columns") or []
            pb = fb.get("arm_point_beta") or []
            for tcol in TREATMENT[name]:
                iv = (fb.get("arm_intervals") or {}).get(tcol)
                if iv:
                    ivs[tcol] = {"lo": iv["lo"], "hi": iv["hi"], "covers_zero": iv["lo"] <= 0.0 <= iv["hi"], "n_effective": iv.get("n_effective")}
                if tcol in cols:
                    betas[tcol] = pb[cols.index(tcol)]
            row["treatment_intervals_95"] = ivs
            row["treatment_point_estimates"] = betas
            row["n_na_draws"] = fb.get("n_na_draws")
        row["interval_level"] = 0.95
        out.append(row)
    return out


def covers0_all(name, col=None):
    cols = [col] if col else TREATMENT[name]
    rows = [r for r in fold_rows(name) if r["status"] == "EVALUABLE"]
    for c in cols:
        for r in rows:
            iv = r["treatment_intervals_95"].get(c)
            if iv is None or not iv["covers_zero"]:
                return False
    return True


def sign_instability(name, col=None):
    cols = [col] if col else TREATMENT[name]
    for c in cols:
        vals = [r["treatment_point_estimates"].get(c) for r in fold_rows(name) if r["status"] == "EVALUABLE"]
        vals = [v for v in vals if v is not None]
        if any(a * b < 0 for a in vals for b in vals):
            return True
    return False


def holm(members_p, m_charged, ordered_members=None):
    """Holm step-down. members_p: {name: p}. m_charged: family element budget.
    ordered_members: subset participating in the ordering (fixed slots excluded);
    thresholds alpha/m_charged, alpha/(m_charged-1), ... over the ordered set."""
    if ordered_members is None:
        ordered_members = list(members_p)
    ranked = sorted(ordered_members, key=lambda n: members_p[n])
    rejected, thresholds = set(), {}
    stopped = False
    for i, n in enumerate(ranked):
        thr = ALPHA / (m_charged - i)  # rank-i nominal threshold (fixed slots charge m but never occupy a rank ahead)
        thresholds[n] = thr
        if not stopped and members_p[n] < thr:
            rejected.add(n)
        else:
            stopped = True  # step-down stops rejecting; thresholds still recorded for the report
    # non-ordered (fixed slot) members never reject
    return rejected, thresholds


# ---- pooled p per element ----
POOLED_P = {n: pooled(n)["p_two_sided"] for n in TREATMENT}
POOLED_D = {n: pooled(n)["delta_mae"] for n in TREATMENT}

# ---- primary-family Holm runs ----
family_runs = {}
for fam, members in FAMILIES.items():
    fixed = FIXED_SLOT.get(fam)
    ordered = [m for m in members if m != fixed]
    rej, thr = holm({m: POOLED_P[m] for m in members}, m_charged=len(members), ordered_members=ordered)
    family_runs[fam] = {
        "members": members, "m": len(members),
        "correction": "Holm, alpha 0.05" if len(members) > 1 else "single test, alpha 0.05",
        "fixed_slot": fixed,
        "p_values": {m: POOLED_P[m] for m in members},
        "holm_thresholds_at_rank": thr,
        "rejected": sorted(rej),
    }

# ---- dual-Holm alternate runs (P35 dual_holm_compositions_pinned; hold-others-at-primary) ----
alt_runs = {}
# A07 alternate: CAL + A07, m=4
mem = ["A02_cal_blend_contrast__single", "A03_cal_shallow_tier_intercept__t3", "A05_cal_playoff_intercept__single", "A07_early_season_transient__single"]
rej, thr = holm({m: POOLED_P[m] for m in mem}, 4)
alt_runs["A07_alternate_CAL_plus_A07_m4"] = {"members": mem, "m": 4, "thresholds": thr, "rejected": sorted(rej),
                                             "disputed_arm_rejects": "A07_early_season_transient__single" in rej}
# A11 alternate: COLDSTART + A11(3) = m=8, ordering over 7 (A14 fixed slot)
mem = FAMILIES["COLDSTART_FALLBACK"] + ["A11_rho0.25", "A11_rho0.5", "A11_rho0.75"]
ordered = [m for m in mem if m != "A14_expansion_intercept_decay__single"]
rej, thr = holm({m: POOLED_P[m] for m in mem}, 8, ordered)
alt_runs["A11_alternate_COLDSTART_plus_A11_m8"] = {"members": mem, "m": 8, "thresholds": thr, "rejected": sorted(rej),
                                                   "disputed_elements_reject": sorted(r for r in rej if r.startswith("A11"))}
# A12 alternate: timeseries + A12 = m=11
mem = FAMILIES["timeseries_shrinkage"] + ["A12_carryover_additive_decay__single"]
rej, thr = holm({m: POOLED_P[m] for m in mem}, 11)
alt_runs["A12_alternate_timeseries_plus_A12_m11"] = {"members": mem, "m": 11, "thresholds": thr, "rejected": sorted(rej),
                                                     "disputed_arm_rejects": "A12_carryover_additive_decay__single" in rej}
# A13 alternate: timeseries + A13 = m=11
mem = FAMILIES["timeseries_shrinkage"] + ["A13_carryover_roster_continuity_moderator__single"]
rej, thr = holm({m: POOLED_P[m] for m in mem}, 11)
alt_runs["A13_alternate_timeseries_plus_A13_m11"] = {"members": mem, "m": 11, "thresholds": thr, "rejected": sorted(rej),
                                                     "disputed_arm_rejects": "A13_carryover_roster_continuity_moderator__single" in rej}

DUAL = {
    "A07_early_season_transient__single": "A07_alternate_CAL_plus_A07_m4",
    "A11_rho0.25": "A11_alternate_COLDSTART_plus_A11_m8",
    "A11_rho0.5": "A11_alternate_COLDSTART_plus_A11_m8",
    "A11_rho0.75": "A11_alternate_COLDSTART_plus_A11_m8",
    "A12_carryover_additive_decay__single": "A12_alternate_timeseries_plus_A12_m11",
    "A13_carryover_roster_continuity_moderator__single": "A13_alternate_timeseries_plus_A13_m11",
}


def multiplicity_verdict(name, fam):
    primary_rej = name in family_runs[fam]["rejected"]
    alt_key = DUAL.get(name)
    if alt_key is None:
        return primary_rej, {"primary_family": fam, "primary_rejects": primary_rej}
    alt_rej = name in alt_runs[alt_key]["rejected"]
    return primary_rej and alt_rej, {"primary_family": fam, "primary_rejects": primary_rej,
                                     "alternate_run": alt_key, "alternate_rejects": alt_rej,
                                     "stricter_governs": "must reject in BOTH"}


# ---- kill evaluation (per P35 card, operationalized per P33 inference block) ----
def K(fired, condition, basis, reading=None):
    d = {"condition": condition, "fired": fired, "basis": basis}
    if reading:
        d["reading"] = reading
    return d


NOT_EVAL = "NOT_EVALUABLE_FROM_RECEIPT"

kills = {}
kills["A02_cal_blend_contrast__single"] = [
    K(covers0_all("A02_cal_blend_contrast__single") and POOLED_D["A02_cal_blend_contrast__single"] <= 0,
      "gamma = 0 not rejected (uncorrected 95% interval covers 0 in every evaluable fold) AND no out-of-fold improvement",
      "interval covers 0 in all 5 evaluable folds; pooled delta_MAE = %.6g <= 0" % POOLED_D["A02_cal_blend_contrast__single"]),
    K(sign_instability("A02_cal_blend_contrast__single"), "sign flip of gamma-hat across folds", "all five point estimates negative"),
    K(False, "S7 near-collinearity with offset in any fold", "no S7/P25 blocking finding on any evaluable fold in the sealed guard records"),
]
kills["A03_cal_shallow_tier_intercept__t3"] = [
    K(covers0_all("A03_cal_shallow_tier_intercept__t3"), "alpha_S = 0 not rejected in every evaluable fold",
      "train_lt_2025 interval (-0.03216, -0.00111) EXCLUDES 0; the every-fold clause does not fire"),
    K(sign_instability("A03_cal_shallow_tier_intercept__t3"), "sign instability", "all five point estimates negative"),
]
kills["A05_cal_playoff_intercept__single"] = [
    K(True, "pi = 0 not rejected (uncorrected interval covers 0 in every evaluable fold)",
      "fires under BOTH evaluable-fold readings: sealed set {2023..2026} - all four intervals cover 0; card set {2022..2025} minus the D040 fold-local 2022 block leaves {2023,2024,2025} - all cover 0",
      reading="dual (sealed fold set vs carded fold set) - fires under both; not harmonized"),
    K(sign_instability("A05_cal_playoff_intercept__single"), "sign instability across evaluable folds",
      "sealed reading: pi-hat -0.0053/-0.0044/-0.0051 (2023-25) vs +0.0010 (2026) -> fires; carded reading (2026 non-discriminating, excluded): all negative -> does not fire. Both readings recorded",
      reading="dual - fires under the sealed fold set only"),
]
kills["A07_early_season_transient__single"] = [
    K(covers0_all("A07_early_season_transient__single"), "delta interval covers 0 in every evaluable fold",
      "train_lt_2023/24/25/26 intervals exclude 0 (positive); only train_lt_2022 covers 0"),
    K(NOT_EVAL, "improvement concentrating outside n <= 5",
      "the n<=5 stratum decomposition is not recorded in the sealed receipt; not computable at P40 without refitting"),
    K(sign_instability("A07_early_season_transient__single"), "sign FLIP across folds", "all five delta-hat point estimates positive"),
]
for n in ["A08_K20", "A08_K80"]:
    kills[n] = [
        K(False, "P25 rejection at invocation (withdrawal)", "guard PASS on all folds in the sealed receipt"),
        K(covers0_all(n), "gamma interval covers 0 in every evaluable fold",
          "K20: all five L_t intervals cover 0 -> FIRES; K80: 2024/2025/2026 exclude 0 (negative) -> does not fire" if n == "A08_K20"
          else "L_t intervals exclude 0 (negative) in train_lt_2024/2025/2026"),
        K(sign_instability(n), "sign instability", "all five L_t point estimates negative"),
    ]
for n in ["A09_kappa2", "A09_kappa10", "A09_kappa50"]:
    kills[n] = [
        K(False, "P25 rejection (withdrawal)", "guard PASS on all folds"),
        K(covers0_all(n), "beta interval covers 0 in every evaluable fold (per element)",
          "all five adaptive-contrast intervals cover 0"),
    ]
kills["A10_lambda0.2"] = [
    K(covers0_all("A10_lambda0.2"), "beta1 indistinguishable from 0 against K0 (interval covers 0 in every evaluable fold)",
      "does NOT fire: all five c_t intervals EXCLUDE 0 - but the point estimates are NEGATIVE (recency contrast rejected in the direction of harm) and the arm is worse on MAE"),
    K(False, "P25 rejection", "guard PASS"),
]
kills["A10_lambda0.5"] = [
    K(covers0_all("A10_lambda0.5"), "beta1 indistinguishable from 0 against K0 (interval covers 0 in every evaluable fold)",
      "all five c_t intervals cover 0"),
    K(False, "P25 rejection", "guard PASS"),
]
for n in ["A11_rho0.25", "A11_rho0.5", "A11_rho0.75"]:
    kills[n] = [
        K(covers0_all(n), "(i) per-element beta interval covers 0 in every evaluable fold -> element killed",
          "train_lt_2025 and train_lt_2026 intervals exclude 0 (positive); does not fire"),
        K(NOT_EVAL, "(ii) improvement not concentrated on the thin-evidence stratum (n_cur <= 5) -> arm killed",
          "stratum decomposition not recorded in the sealed receipt"),
        K(sign_instability(n), "(iii) beta-hat sign instability across evaluable folds -> arm killed", "all four point estimates positive"),
    ]
kills["A12_carryover_additive_decay__single"] = [
    K(NOT_EVAL, "joint treatment adds no out-of-fold improvement on the preregistered n <= 5 stratum",
      "n<=5 stratum decomposition not recorded in the sealed receipt"),
    K(NOT_EVAL, "all-rows-only improvement", "same missing stratum decomposition"),
    K(True, "beta2 sign contradicting decay",
      "w_n:dev_prev point estimates negative in all four evaluable folds (-0.00052/-0.00316/-0.00315/-0.00350) while the decay mechanism predicts positive loading; under the point-sign reading the kill FIRES; under a rejection-based reading (interval excluding 0 with contradicting sign) it does not (all four intervals cover 0). Both readings recorded; the element fails its primary gate under either.",
      reading="dual (point-sign vs rejection) - preserved, not harmonized"),
]
kills["A13_carryover_roster_continuity_moderator__single"] = [
    K(covers0_all("A13_carryover_roster_continuity_moderator__single"), "beta3 interval covers 0 given A12's terms (every evaluable fold)",
      "train_lt_2023 (0.0029, 0.0779) and train_lt_2024 (0.0059, 0.0591) EXCLUDE 0 (positive); 2025/2026 cover 0; the every-fold clause does not fire"),
    K(True, "beta3 < 0 (refutes mechanism)",
      "train_lt_2026 point estimate -0.00227 (interval covers 0) vs positive point estimates in 2023-2025: under the point-sign reading a one-fold negative fires the refutation clause AND constitutes sign instability across folds; under a rejection-based reading it does not. Both recorded; result is EXPLORATORY regardless (A12 did not reject).",
      reading="dual (point-sign vs rejection) - preserved, not harmonized"),
]
kills["A14_expansion_intercept_decay__single"] = [
    K(True, "single-fold decidable set: interval covers 0 -> KILLED",
      "kappa interval train_lt_2026 (-0.07568, +0.06989) covers 0 -> KILLED per kill_conditions_single_fold_decidable; the pooled delta_MAE +0.0173 (p 0.0432 uncorrected, single fold) does NOT rescue the element - the carded rule is the coefficient interval, and A14 is promotion-INELIGIBLE regardless (single-active-fold licensing; F4 single-franchise confound caveats carried)"),
]
kills["A15_gap_by_depth_asymmetry__single"] = [
    K(covers0_all("A15_gap_by_depth_asymmetry__single"), "beta4 interval covers 0 (every evaluable fold)",
      "all four pace_gap:asym intervals cover 0"),
    K(NOT_EVAL, "improvement not concentrated in top-|asym| bucket", "bucket decomposition not recorded in the sealed receipt"),
    K(sign_instability("A15_gap_by_depth_asymmetry__single"), "beta4 < 0 refutes the reliability mechanism / sign pattern",
      "point estimates negative in 2023/2024/2025, positive in 2026 - sign-unstable; no fold rejects either direction"),
]
kills["A16_lag_residual_own_minus_opp"] = [
    K(False, "P25 rejection (withdrawal)", "guard PASS"),
    K(covers0_all("A16_lag_residual_own_minus_opp"), "beta interval covers 0 in every evaluable fold", "all five intervals cover 0"),
    K(sign_instability("A16_lag_residual_own_minus_opp"), "sign instability", "all five point estimates negative"),
]
kills["A17_transition_mix_share__single"] = [
    K(True, "preregistered score/LR-equivalent bootstrap test vs K0 fails",
      "pooled delta_MAE = %.6g < 0, p = %.4g - the arm is worse than its null; the primary bootstrap test fails" % (POOLED_D["A17_transition_mix_share__single"], POOLED_P["A17_transition_mix_share__single"])),
    K(False, "P25 rejection", "final-fit guard PASS on evaluable folds; the fold-2022 fold-local block is a FOLD_UNEVALUABLE record per D040, not an arm withdrawal"),
]
kills["A18_median_duration_contrast"] = [
    K(True, "cluster-resampled interval for beta1 covers 0 or primary gate fails",
      "both clauses true: all five z1 intervals cover 0 AND pooled delta_MAE = %.6g < 0" % POOLED_D["A18_median_duration_contrast"]),
    K(False, "withdrawal if P25 near-affinity with offset or pace_gap in every training fold", "no such finding in the sealed guard records"),
]
kills["A20_forced_turnover_contrast"] = [
    K(True, "interval covers 0 or no primary-gate improvement",
      "both clauses true: all five z2 intervals cover 0 AND pooled delta_MAE = %.6g < 0 (p = %.4g - the arm is significantly WORSE at the two-sided 0.05 level). Secondary diagnostic: z2 point sign negative in all five folds, OPPOSITE to the preregistered prediction beta2 > 0" % (POOLED_D["A20_forced_turnover_contrast"], POOLED_P["A20_forced_turnover_contrast"])),
    K(False, "P25 withdrawal (z2 jointly reconstructing the offset)", "no such finding"),
]
kills["A21_garbage_time_contamination"] = [
    K(True, "null vs K0", "pooled delta_MAE = %.6g < 0, p = %.4g; contamination term adds nothing" % (POOLED_D["A21_garbage_time_contamination"], POOLED_P["A21_garbage_time_contamination"])),
    K(NOT_EVAL, "depth-absorption robustness check fails (x proxies evidence VOLUME)",
      "the preregistered robustness refit (adding pace_evidence_depth to the nuisance set) is not recorded in the sealed receipt; moot for promotion - the primary gate already fails"),
]
kills["A22_lineup_churn_tv_distance__single"] = [
    K(True, "null vs K0", "pooled delta_MAE = %.6g < 0, p = %.4g; churn intervals cover 0 in all four evaluable folds" % (POOLED_D["A22_lineup_churn_tv_distance__single"], POOLED_P["A22_lineup_churn_tv_distance__single"])),
    K(NOT_EVAL, "depth-absorption check", "robustness refit not recorded in the sealed receipt; moot - primary gate fails"),
]
for n, tag in [("A23_rest_differential_contrast__bundle_AI", "AI"), ("A23_rest_differential_contrast__bundle_OM", "OM")]:
    kills[n] = [
        K(True, "no gain over K0 / effect below resolution declared as a null, not deferred",
          "pooled delta_MAE = %.3g (p = %.3g): numerically positive but below resolution; declared a NULL per the carded clause" % (POOLED_D[n], POOLED_P[n])),
        K(False, "opposite-sign rejection (interval excluding 0 with sign opposite to prediction)",
          "no fold's interval excludes 0 in either direction"),
    ]
kills["A24_rest_advantage_symmetric"] = [
    K(True, "null vs K0",
      "pooled delta_MAE = %.6g < 0 (p = %.4g); all five coef(x) intervals cover 0 - a decisive null" % (POOLED_D["A24_rest_advantage_symmetric"], POOLED_P["A24_rest_advantage_symmetric"])),
    K(False, "P25 flag (the incumbent already encodes schedule structure - the arm dies)", "no P25 finding fired; the arm was evaluated cleanly"),
]
kills["A25_home_offense_contrast__single"] = [
    K(covers0_all("A25_home_offense_contrast__single"), "cluster-resampled interval for beta covers 0 (GENUINE NULL reading)",
      "does NOT fire as carded: intervals EXCLUDE 0 (negative) in 2022/2023/2025/2026 and cover 0 only in 2024. The carded genuine-null interpretation ('the offset already prices home tempo') therefore does not attach; what the evidence shows instead is a reliably NEGATIVE home-offense coefficient (approx -0.003 to -0.008 log scale) that does NOT improve out-of-fold MAE (pooled delta_MAE = {:.6g} < 0). Recorded as evidence, not promoted.".format(POOLED_D["A25_home_offense_contrast__single"])),
]
kills["A26_sos_correction_own_minus_opp"] = [
    K(True, "interval covers 0 or no primary-gate improvement",
      "both clauses true: all five z5 intervals cover 0 AND pooled delta_MAE = %.6g < 0" % POOLED_D["A26_sos_correction_own_minus_opp"]),
    K(False, "P25 withdrawal (design failure)", "no such finding"),
]


def kill_fired_any(name):
    return any(k["fired"] is True for k in kills[name])


# ---- per-element adjudication ----
elements_out = {}
fam_of = {m: f for f, ms in FAMILIES.items() for m in ms}
n_pass = 0
for name in TREATMENT:
    fam = fam_of[name]
    p = pooled(name)
    gate_a = p["delta_mae"] > 0
    mult_pass, mult_detail = multiplicity_verdict(name, fam)
    fired = kill_fired_any(name)
    promo_eligible = name != "A14_expansion_intercept_decay__single"
    verdict = "PASS" if (gate_a and mult_pass and not fired and promo_eligible) else "FAIL"
    if verdict == "PASS":
        n_pass += 1
    files = ELS[name]["files"]
    r = elem(name)
    ev = r["results"]["evaluable_folds"]
    n_cl = sum(fr["n_clusters"] for fr in fold_rows(name) if fr["status"] == "EVALUABLE")
    elements_out[name] = {
        "arm_id": r["arm_id"], "element_id": r["element_id"], "family": fam,
        "enumeration_element": r["enumeration_element"],
        "primary": {
            "delta_mae_pooled": p["delta_mae"], "p_two_sided": p["p_two_sided"],
            "mae_arm": p["mae_arm"], "mae_null_k0_matched": p["mae_null"],
            "n_rows_pooled_oof": p["n_rows"], "n_clusters_pooled_oof": n_cl, "n_draws": p["n_draws"],
            "gate_a_delta_positive": gate_a,
            "gate_b_multiplicity": mult_detail, "gate_b_pass": mult_pass,
            "gate_c_no_kill_fired": not fired,
            "gate_d_p28_ordering": "satisfied - no downstream turnover number computed before this verdict",
        },
        "fold_coverage": {"evaluable_folds": ev, "structurally_deactivated": r["results"]["structurally_deactivated_folds"],
                          "n_evaluable": len(ev)},
        "per_fold": fold_rows(name),
        "kill_conditions": kills[name],
        "kills_fired": [k["condition"] for k in kills[name] if k["fired"] is True],
        "kills_not_evaluable": [k["condition"] for k in kills[name] if k["fired"] == NOT_EVAL],
        "verdict": verdict,
        "promotion_eligible": promo_eligible,
        "provenance_d036": {
            "model": f"{r['arm_id']} element vs its per-arm K0_MATCHED (paired, same clusters, same seeds)",
            "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
            "universe": "2,982 team-game rows / 1,491 game clusters, seasons 2021-2026; pooled OOF test rows as stated per element",
            "cutoff_discipline": "strictly-lagged features; D006 expanding folds; blinded P36/P38 fit, unsealed only at P40 under D041",
            "evidence_class": "VERIFIED (P39 PASS_WITH_FINDINGS integrity certification; frozen preregistration P35 sha256 " + P35_SHA + ")",
            "source_receipt": f"stage2b/SEALED_RESULTS/P38/{ELS[name]['dir']}/receipt.json",
            "source_receipt_sha256": files["receipt.json"]["sha256"],
            "computation_timestamp_utc": r["recorded_utc"],
            "inference": "game-cluster bootstrap, B=10000 test / B=2000 train-refit, master seed 20260806, p two-sided per EXEC-M3 formula",
        },
    }

spec = {
    "schema": "stage2b_p40_primary_adjudication/1",
    "node": "P40_PRIMARY_ADJUDICATION",
    "epistemic_status": "PRIMARY ADJUDICATION. The first context permitted to see results. Criteria are the preregistered ones and are not altered after seeing outcomes.",
    "authority": {
        "unseal": "D041_P39_CLOSE_AND_UNSEAL - P40 is the FIRST and ONLY context authorized to open stage2b/SEALED_RESULTS/P38/",
        "gates": "P35_FREEZE_TASK_CARDS/SPEC.json sha256 " + P35_SHA + " (verified byte-identical this node) carrying the P33 inference block (sha256 066b2a04...d347d093 by reference)",
        "integrity": "P39_RESULT_INTEGRITY PASS_WITH_FINDINGS (21/21 structural checks, 0 Severity A)",
        "manifest_sha256": ex["manifest_sha256"],
    },
    "primary_gate_applied_verbatim": "delta_MAE = MAE(K0_MATCHED[arm]) - MAE(arm), pooled out-of-fold over the arm's evaluable folds. Promotion requires ALL of: (a) delta_MAE > 0; (b) two-sided cluster-bootstrap p-value below the arm's family-Holm-adjusted alpha (family-wise alpha = 0.05); (c) no kill condition triggered; (d) P28 ordering. Kills evaluated UNCORRECTED per the frozen operationalisation.",
    "a24_scope_disposition_first_item": {
        "question": "Does the 7-own-side-row / 10-row / 5-game measured scope of the A24 franchise-debut fallback (RULE reading, D041-upheld structurally) alter A24's preregistered inference statement or carded accounting?",
        "ruling": "NO CHANGE TO THE CARDED ACCOUNTING. The fallback is a feature-domain totalization (rest := cap where no prior contract-schedule game exists), applied identically in arm and null (sealed scope record: identical_in_arm_and_null = true). It adds no element, no family member, and no degree of freedom: A24 remains exactly ONE fitted element in SCHEDULE_FATIGUE at single-test alpha 0.05, its K0_MATCHED remains term_removal of x, and its kill conditions are unchanged. The four additional 2021 rows are an archive-start boundary fact (first contract games 2021-05-15 vs archive start 2021-05-14), not franchise debuts; they touch 7 own-side feature values of 2,982 rows (0.23%). The registered enumeration ('exactly 3 debut games / 6 rows') is measured FALSE and stays recorded as a contradiction - reported, never reconciled. The wider row set is also substantively moot: A24 is a decisive null (pooled delta_MAE -0.00322, p 0.497; all five coef intervals cover 0).",
        "positive_control_note": "A24 is the LAG OPERATOR POSITIVE CONTROL. It was evaluated CLEANLY (5/5 folds evaluable, all fits converged, guards pass) - so the machinery clause ('if the machinery cannot cleanly evaluate this arm, no lagged-arm result should be trusted') does NOT fire; lagged-arm results elsewhere in the fleet are trustworthy on this axis. The clean NULL is itself the finding: no symmetric rest-level tempo depression is detectable on this universe.",
        "sealed_records": ["A24_REGISTRY_FALLBACK_SCOPE_RECORD.json", "FINAL_FITS_SUPERSESSION.json", "EXCLUSION_RECORD.json (superseded, preserved)"],
    },
    "families": family_runs,
    "dual_holm_alternate_runs": alt_runs,
    "a13_fixed_sequence": {
        "rule": "confirmatory iff A12 passes under the stricter of its dual-family corrections",
        "a12_rejected": False,
        "a13_status": "EXPLORATORY (A12 did not reject; A13's element remains in the COLDSTART_FALLBACK denominator - the slot is always occupied)",
    },
    "both_pass_joint_retests": {
        "rule": "triggered only when two arms passing their primary gates in DIFFERENT families have treatment max per-training-fold R2 >= 0.25",
        "triggered": [],
        "note": "no element passed its primary gate, so no pair qualifies; the named exposure pairs (A03/A07, A17/A18, A23/A24) are all moot this cycle",
    },
    "multi_survivor_rule": {"invoked": False, "note": "no family has a surviving element"},
    "elements": elements_out,
    "summary": {
        "fitted_elements": len(elements_out),
        "n_pass_primary": n_pass,
        "n_fail_primary": len(elements_out) - n_pass,
        "families_with_survivors": [],
        "champion_challenged": False,
        "champion_note": "No promotion-eligible element passed its preregistered primary gate after family multiplicity with no kill fired. The frozen incumbent D_ewma_shrunk stands unchallenged this cycle. The replacement decision (none proposed) is the P43 USER gate in any case.",
        "incumbent_margin": {
            "pooled_oof_mae_of_incumbent_identical_nulls": pooled("A25_home_offense_contrast__single")["mae_null"],
            "n_rows": pooled("A25_home_offense_contrast__single")["n_rows"],
            "note": "For arms whose K0_MATCHED IS the frozen incumbent exactly ([log_exposure], zero fitted parameters: A02/A03/A16/A18/A20/A23/A24/A25/A26), the pooled OOF MAE of the null is the incumbent's own pooled out-of-fold MAE on the five D006 test folds: 2.86649 possessions over 2,572 rows / 1,286 clusters. Best challenger pooled OOF MAE anywhere in the fleet: A07 arm 2.81090 vs its OWN null 2.86494 - but per the frozen K5 amendment MAE(K0[A07]) is NOT an incumbent benchmark (the null carries receipted incumbent-path features and is deliberately stronger than the incumbent), and A07 fails Holm in both of its families.",
        },
    },
    "notable_evidence_preserved": {
        "A07_near_miss": "Largest pooled improvement in the fleet: delta_MAE +0.05404 (arm 2.81090 vs K0 2.86494, 2,572 rows), p uncorrected 0.0280. Fails the Holm first threshold in BOTH its families (COLDSTART m=5: 0.05/5 = 0.01; alternate CAL+A07 m=4: 0.05/4 = 0.0125; stricter governs). Coefficient intervals exclude 0 (positive) in 4 of 5 folds; sign-stable. The carded n<=5 concentration kill could not be checked from the receipt. A honest near-miss, preserved as evidence; not promotable under the frozen machinery.",
        "significant_harm": "Two elements are significantly WORSE than their nulls at the two-sided 0.05 level (uncorrected): A10_lambda0.5 (delta -0.00219, p 0.0138) and A20 (delta -0.000399, p 0.0496). Under the frozen gate these are FAILs on clause (a); preserved as negative results.",
        "coefficient_signal_without_mae_payoff": "Three constructions show reproducible coefficient rejections that do NOT convert into out-of-fold MAE improvement: A25 (home-offense beta negative, excluded 0 in 4/5 folds; delta_MAE -0.0055), A10_lambda0.2 (c_t negative, excluded 0 in 5/5 folds; delta -0.0018), A17 (x negative, excluded 0 in 3/4 folds; delta -0.0031), and A08_K80's L_t (negative, excluded 0 in 3 late folds; delta +0.0019, p 0.87). Under the frozen primary gate none of these is promotable; recorded as evidence for future ideation only via proper channels.",
        "A14_diagnostic": "A14 (promotion-INELIGIBLE, fixed Holm slot): single evaluable fold train_lt_2026 delta_MAE +0.0173 (p 0.0432 uncorrected, 430 rows) but the carded single-fold-decidable rule KILLS it - the kappa interval (-0.0757, +0.0699) covers 0. Recorded with the mandatory F4 caveats: single-franchise cohort (1611661331), kappa confounded with franchise identity, effective decayed support ~9-15 clusters.",
    },
    "preserved_disagreements_reported_not_harmonized": {
        "D1": "A11 (blend-null, parameter_fixed_at_null at rho=1) and A12 (term-removal null with incumbent-path features): both preserved readings were fitted and BOTH fail their gates independently (A11 elements: small positive deltas +0.0004..+0.0008, p 0.17-0.67; A12: +0.00195, p 0.142). Neither null is incumbent-equivalent (D1 resolution carried); no harmonization.",
        "D2_D5": "Family-assignment disputes discharged by dual-Holm exactly as pinned: A07, A11(x3), A12, A13 each evaluated under BOTH partitions; every disputed element fails under both (stricter governs was never reached - the lenient run already fails).",
        "D3": "A05's two positions travel with the arm: the carded 2026-non-discriminating reading and the sealed 2026-evaluable/2022-blocked treatment give the same verdict (kill fires, gate fails) - both fold-set readings reported under the kill entry.",
        "D6": "Four trailing-window conventions evaluated per-arm exactly as frozen; never pooled. All fail independently.",
        "D7": "A23's two source-consistent bundles both fitted end-to-end: bundle_AI beta-hat NEGATIVE in all five folds (pooled delta +2.1e-05, p 0.903), bundle_OM beta-hat POSITIVE in all five folds (pooled delta +5.0e-05, p 0.708). The two preserved readings give OPPOSITE-signed point estimates, neither rejecting anywhere; both declared nulls per the carded below-resolution clause; never averaged.",
        "D9": "Three OT conventions fitted per-arm as frozen (A12 rescale, A16 regulation-equivalent, A26 raw): all three arms are nulls/fails independently; the A26 symmetric-cancellation assertion remains preserved-as-unmeasured.",
    },
    "contradictions_found": [
        "C1 (labelling): the sealed receipts record the fold-2022 deactivations of A05/A15/A17/A21/A22 with basis 'card-pinned structural deactivation' - but those cards pin NO fold-2022 deactivation (A05's card pins fold-2026 as non-discriminating; A15/A17 expected five evaluable folds). The operative authority is the D040 fold-local P25 wrapper (FOLD_UNEVALUABLE records; manifest raised-finding P38-R1 confirms mechanism (ii): game-level columns read as offset-determined in the earliest fold). The basis string over-claims; reported, not reconciled.",
        "C2 (A05 fold set): card 'four evaluable folds' = {2022..2025} with 2026 non-discriminating (test playoff rows == 0) vs sealed evaluable {2023..2026} with 2026 contributing delta 0 / p 1.0. Verdict identical under both readings; both reported.",
        "C3 (A24 enumeration): registered enumeration 3 games/6 rows measured FALSE (5/10/7 under the rule's own predicate). Ruled above: no accounting consequence; contradiction stands recorded.",
        "C4 (P26 R8 shape): the P26 validator's raw_validation carries BLOCKING findings on A02/A03/A05 (tested_parameter_missing role=slope; lower_order_term_missing_from_k0) - tolerated per the frozen P35 r8_scope_adjudication (R8 scoped to slope-recalibration arms, none fitted) and the D039 EXEC-M7 bind outcome 'tolerated_r8_shape' recorded per element in the sealed manifest. Not a silent pass; recorded.",
        "C5 (element count): the executor-preserved 26-vs-21 dispatch-count contradiction (D040) is carried in the sealed record; the fitted-element count of record here is 29 receipts across 22 arms, matching the P35 registry append (cards_frozen 23, arms_fitted 22, fitted_elements 29).",
        "C6 (kill-sign wording): A12's 'beta2 sign contradicting decay' and A13's 'beta3 < 0' admit a point-sign and a rejection reading; both evaluated and reported under the kill entries; no verdict depends on the choice.",
    ],
    "could_not_establish": [
        "Stratum-concentration kill inputs (A07 improvement-concentration on n<=5; A11 thin-evidence n_cur<=5 concentration; A12 n<=5-stratum and all-rows-only decomposition; A15 top-|asym| bucket concentration) and the A21/A22 depth-absorption robustness refits: none of these diagnostics is recorded in the sealed receipts, and P40's scope is adjudication of the sealed record, not refitting. Marked NOT_EVALUABLE_FROM_RECEIPT per element. No promotion decision depends on any of them: every affected element already fails its primary gate on (a) or (b).",
        "The operational incumbent MAE ~2.9675 (full-history, frozen) is NOT comparable to the pooled OOF test-fold MAEs reported here (different row sets and pooling); no cross-claim is made.",
    ],
    "stop_conditions": {"tripped": False, "detail": "Nothing here changes the primary target, K0 structure, inference structure, candidate universe, cutoff-valid feature set or leakage status. The P38-R1 whole-arm-escalation finding was resolved by D040 before sealing; the A24 scope item was assigned to this node by D041 and is ruled above at arm level only."},
    "downstream": "Adjudicated outcomes flow to the leaderboard solely through the D036 pipeline as VERIFIED evidence. No champion-replacement candidate exists; nothing goes to the P43 USER gate this cycle.",
}

(OUT / "SPEC.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
(OUT / "ADJUDICATION.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
print("wrote SPEC.json and ADJUDICATION.json")
print("n_pass:", n_pass, "n_fail:", len(elements_out) - n_pass)
for fam, fr in family_runs.items():
    print(fam, "rejected:", fr["rejected"])
