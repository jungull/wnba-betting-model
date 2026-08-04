#!/usr/bin/env python3
"""TESTS.py — P25_OFFSET_DEPENDENCY_GUARD.

Standalone. No pytest. `main()` returns 1 on any failure.

Every real-data number is measured here, from the frozen artifacts, at run time. Nothing is
asserted from prose. Synthetic cases exist only where a defect must be constructed on purpose
(a near-affine candidate, a fold-degenerate contrast, an edited preregistration record).

Run:  python experiments/player_program/stage2b/P25_OFFSET_DEPENDENCY_GUARD/TESTS.py
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]                                   # experiments/player_program
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PP))

import feature_gate as fg                                                     # noqa: E402
import offset_dependency_guard as G                                           # noqa: E402

PRIOR = PP / "projected_exposure_v1" / "team_possession_prior_v1.parquet"
POSS = PP / "possessions_v2" / "possessions_raw_v2.parquet"
PREREG = HERE / "PREREGISTERED_CONTRASTS.json"

MEASURED: dict = {}
_FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        _FAIL.append(f"{name}: {detail}")


def expect_block(name: str, kinds_required: set[str], fn) -> dict:
    """Run `fn`; require it to raise OffsetDependencyFailure carrying every kind in kinds_required."""
    try:
        fn()
    except G.OffsetDependencyFailure as exc:
        kinds = {b["kind"] for b in exc.blocking}
        missing = kinds_required - kinds
        check(name, not missing, f"blocked but missing kinds {sorted(missing)}; got {sorted(kinds)}")
        return {"blocked": True, "kinds": sorted(kinds)}
    check(name, False, "guard did NOT block")
    return {"blocked": False, "kinds": []}


# ----------------------------------------------------------------------------- panel construction
def build_panel() -> pd.DataFrame:
    """The frozen incumbent panel, with own/opp estimates and the regulation-equivalent target.

    own_est  = this row's team_pace_estimate
    opp_est  = the other side's team_pace_estimate in the same game
    offset   = projected_team_off_possessions (the incumbent's own projection)
    target   = n_off_poss * 40 / game_minutes, game_minutes = 40 + 5*max(0, max_period-4)
    """
    prior = pd.read_parquet(PRIOR)
    MEASURED["prior_rows_total"] = int(len(prior))
    MEASURED["prior_games_total"] = int(prior.game_id.nunique())
    MEASURED["prior_rows_unresolved"] = int((~prior.pace_resolved).sum())

    s = prior.groupby("game_id")["team_pace_estimate"].transform("sum")
    prior = prior.assign(own_est=prior.team_pace_estimate, opp_est=s - prior.team_pace_estimate)

    d = prior[prior.pace_resolved].copy()
    d = d[np.isfinite(d.own_est) & np.isfinite(d.opp_est)
          & np.isfinite(d.projected_team_off_possessions)].reset_index(drop=True)

    poss = pd.read_parquet(POSS, columns=["game_id", "offense_team_id", "period"])
    gm = poss.groupby("game_id")["period"].max().rename("max_period").reset_index()
    gm["game_minutes"] = 40 + 5 * np.maximum(0, gm.max_period - 4)
    n = (poss.groupby(["game_id", "offense_team_id"]).size().rename("n_off_poss").reset_index()
         .rename(columns={"offense_team_id": "team_id"}))
    n = n.merge(gm[["game_id", "game_minutes"]], on="game_id", validate="m:1")
    n["target"] = n.n_off_poss * 40.0 / n.game_minutes

    d = d.merge(n[["game_id", "team_id", "target"]], on=["game_id", "team_id"],
                how="left", validate="1:1")
    d["contrast_own_minus_opp_pace_estimate"] = d.own_est - d.opp_est
    return d


# ------------------------------------------------------------------------------------- the tests
def t01_feature_gate_byte_unchanged():
    digest = G.feature_gate_digest()
    MEASURED["feature_gate_sha256"] = digest
    MEASURED["feature_gate_bytes"] = int((PP / "feature_gate.py").stat().st_size)
    check("t01_feature_gate_byte_unchanged", digest == G.FEATURE_GATE_SHA256,
          f"{digest} != {G.FEATURE_GATE_SHA256}")
    # the guard must not have shadowed the frozen constants
    check("t01_constants_reused", (fg.RANK_TOL == 1e-8 and fg.COND_MAX == 1e6
                                   and G.NEAR_R2 == 0.999 ** 2),
          f"RANK_TOL={fg.RANK_TOL} COND_MAX={fg.COND_MAX} NEAR_R2={G.NEAR_R2}")


def t02_identity_reproduced(d):
    dev = (d.own_est + d.opp_est) - 2 * d.projected_team_off_possessions
    MEASURED["identity_rows"] = int(len(d))
    MEASURED["identity_game_clusters"] = int(d.game_id.nunique())
    MEASURED["identity_max_abs_deviation"] = float(np.abs(dev).max())
    MEASURED["identity_rows_exactly_zero"] = int((dev == 0).sum())
    MEASURED["corr_own_projected"] = round(
        float(np.corrcoef(d.own_est, d.projected_team_off_possessions)[0, 1]), 6)
    MEASURED["corr_own_opp"] = round(float(np.corrcoef(d.own_est, d.opp_est)[0, 1]), 6)
    MEASURED["corr_contrast_projected"] = round(
        float(np.corrcoef(d.contrast_own_minus_opp_pace_estimate,
                          d.projected_team_off_possessions)[0, 1]), 12)
    MEASURED["sd_projected"] = round(float(d.projected_team_off_possessions.std(ddof=1)), 6)
    MEASURED["var_projected"] = round(float(d.projected_team_off_possessions.var(ddof=1)), 6)
    check("t02_rows", len(d) == 2982, f"{len(d)}")
    check("t02_clusters", d.game_id.nunique() == 1491, f"{d.game_id.nunique()}")
    check("t02_identity_exact", MEASURED["identity_max_abs_deviation"] == 0.0,
          str(MEASURED["identity_max_abs_deviation"]))
    check("t02_corr_own_projected", abs(MEASURED["corr_own_projected"] - 0.7738) < 5e-5,
          str(MEASURED["corr_own_projected"]))
    check("t02_corr_own_opp", abs(MEASURED["corr_own_opp"] - 0.1977) < 5e-5,
          str(MEASURED["corr_own_opp"]))
    # both pairwise correlations sit far below feature_gate's blocking threshold
    check("t02_below_gate_threshold",
          max(abs(MEASURED["corr_own_projected"]), abs(MEASURED["corr_own_opp"])) < 0.999, "")


def t03_feature_gate_passes_the_dependent_design(d):
    """The hole, reproduced against the frozen gate. This test PASSES when the gate PASSES."""
    off = d.projected_team_off_possessions.to_numpy(float)
    y = d.target.to_numpy(float)
    rec = fg.audit(d, ["own_est", "opp_est"], offset=off, target=y)
    MEASURED["feature_gate_on_own_opp"] = {
        "passed": bool(rec["passed"]),
        "findings": [f["kind"] for f in rec["findings"]],
        "feature_only_numerical_rank": rec["design_rank"]["numerical_rank"],
        "feature_only_n_features": rec["design_rank"]["n_features"],
        "feature_only_condition_number": round(rec["design_rank"]["condition_number"], 6),
    }
    check("t03_gate_passes_dependent_design", rec["passed"] and not rec["findings"],
          json.dumps(MEASURED["feature_gate_on_own_opp"]))


def t04_guard_rejects_the_dependent_design(d):
    off = d.projected_team_off_possessions.to_numpy(float)
    r = expect_block("t04_guard_rejects_own_opp",
                     {"pair_reconstructs_offset", "design_reconstructs_offset",
                      "augmented_rank_deficient", "fold_local_rank_deficient",
                      "fold_local_reconstructs_offset"},
                     lambda: G.audit_augmented_design(
                         d, ["own_est", "opp_est"], off,
                         incumbent_projection=off, fold_ids=d.season))
    MEASURED["guard_on_own_opp_kinds"] = r["kinds"]
    rec = G.audit_augmented_design(d, ["own_est", "opp_est"], off,
                                   incumbent_projection=off, fold_ids=d.season,
                                   raise_on_block=False)
    MEASURED["augmented_rank"] = {
        "numerical_rank": rec["augmented_rank"]["numerical_rank"],
        "n_columns": rec["augmented_rank"]["n_features"],
        "singular_values": rec["augmented_rank"]["singular_values"],
        "condition_number": rec["augmented_rank"]["condition_number"],
    }
    MEASURED["r2_offset_on_own_opp"] = rec["r2_offset_on_design"]
    MEASURED["audited_columns"] = rec["audited_columns"]
    MEASURED["per_fold_own_opp"] = {
        k: {"n_rows": v["n_rows"], "rank": v["rank_report"]["numerical_rank"],
            "n_columns": v["rank_report"]["n_features"],
            "r2_offset_on_design": v["r2_offset_on_design"]}
        for k, v in rec["folds"].items()}
    check("t04_augmented_rank_2_of_3", rec["augmented_rank"]["numerical_rank"] == 2
          and rec["augmented_rank"]["n_features"] == 3, json.dumps(MEASURED["augmented_rank"]))
    check("t04_smallest_sv_zero", rec["augmented_rank"]["singular_values"][-1] == 0.0, "")
    check("t04_r2_one", rec["r2_offset_on_design"] == 1.0, str(rec["r2_offset_on_design"]))
    check("t04_audited_columns_include_offset",
          rec["audited_columns"] == ["__offset__", "own_est", "opp_est"],
          str(rec["audited_columns"]))
    check("t04_all_six_folds_degenerate",
          len(rec["folds"]) == 6 and all(v["r2_offset_on_design"] == 1.0
                                         for v in rec["folds"].values()), "")


def t05_isolation_would_miss_it(d):
    """The criterion 'never on candidate features in isolation', demonstrated rather than asserted."""
    off = d.projected_team_off_possessions.to_numpy(float)
    rec = G.audit_augmented_design(d, ["own_est"], off, fold_ids=d.season, raise_on_block=False)
    MEASURED["r2_offset_on_own_alone"] = rec["r2_offset_on_design"]
    check("t05_own_alone_passes", rec["passed"],
          f"own_est alone should not be blocked; kinds={[f['kind'] for f in rec['blocking']]}")
    check("t05_own_alone_r2", 0.59 < rec["r2_offset_on_design"] < 0.60,
          str(rec["r2_offset_on_design"]))
    # the SAME two columns, split across nuisance and candidate, must still be caught
    expect_block("t05_split_across_nuisance_and_candidate",
                 {"design_reconstructs_offset", "augmented_rank_deficient"},
                 lambda: G.audit_augmented_design(d, ["own_est"], off,
                                                  nuisance_features=["opp_est"],
                                                  fold_ids=d.season))


def t06_exact_affine_candidate(d):
    off = d.projected_team_off_possessions.to_numpy(float)
    x = d.assign(cal=2.0 * off + 3.0)
    expect_block("t06_exact_affine_of_offset",
                 {"candidate_affine_in_offset", "calibration_parameter_in_substantive_arm"},
                 lambda: G.audit_augmented_design(x, ["cal"], off, fold_ids=d.season))


def t07_near_exact_affine_candidate(d):
    off = d.projected_team_off_possessions.to_numpy(float)
    rng = np.random.default_rng(20260804)
    noise = rng.standard_normal(len(off))
    noise = (noise - noise.mean()) / noise.std()
    cand = off + 0.030 * off.std() * noise
    r = float(np.corrcoef(cand, off)[0, 1])
    MEASURED["near_affine_corr"] = round(r, 6)
    MEASURED["near_affine_r2"] = round(r * r, 6)
    check("t07_construction_is_near_not_exact", G.NEAR_R2 <= r * r < 1.0, f"r2={r*r}")
    x = d.assign(cal_near=cand)
    expect_block("t07_near_exact_affine_of_offset", {"candidate_affine_in_offset"},
                 lambda: G.audit_augmented_design(x, ["cal_near"], off, fold_ids=d.season))


def t08_independent_candidate_passes(d):
    """Boundary sanity: the guard must not reject an honestly informative column."""
    off = d.projected_team_off_possessions.to_numpy(float)
    rng = np.random.default_rng(7)
    cand = off + 0.6 * off.std() * rng.standard_normal(len(off))
    r = float(np.corrcoef(cand, off)[0, 1])
    MEASURED["benign_candidate_corr"] = round(r, 6)
    rec = G.audit_augmented_design(d.assign(benign=cand), ["benign"], off,
                                   fold_ids=d.season, raise_on_block=False)
    check("t08_benign_candidate_passes", rec["passed"],
          f"kinds={[f['kind'] for f in rec['blocking']]}, corr={r}")


def t09_exact_function_of_incumbent_projection(d):
    """The `incumbent_projection` argument is load-bearing, demonstrated rather than asserted.

    A downstream turnover-style arm carries offset = log(exposure) where
    exposure = projected_team_off_possessions * rotation_share. The projection is then NOT
    recoverable from the offset, so every offset-side test correctly stays silent -- and a
    candidate equal to the incumbent's own output slips through unless the projection is supplied
    separately. The rotation share here is a deterministic synthetic stand-in; only its role in the
    offset matters, not its values.
    """
    proj = d.projected_team_off_possessions.to_numpy(float)
    rng = np.random.default_rng(909)
    share = 0.10 + 0.15 * rng.random(len(proj))
    off = np.log(proj * share)
    x = d.assign(raw_proj=proj)
    MEASURED["t09_corr_candidate_offset"] = round(float(np.corrcoef(proj, off)[0, 1]), 6)
    rec_no_proj = G.audit_augmented_design(x, ["raw_proj"], off, fold_ids=d.season,
                                           raise_on_block=False)
    MEASURED["t09_without_projection_argument_passes"] = bool(rec_no_proj["passed"])
    MEASURED["t09_r2_offset_on_candidate"] = rec_no_proj["r2_offset_on_design"]
    check("t09_offset_side_tests_are_silent", rec_no_proj["passed"],
          f"kinds={[f['kind'] for f in rec_no_proj['blocking']]}")
    expect_block("t09_exact_function_of_projection",
                 {"candidate_is_function_of_incumbent_projection",
                  "calibration_parameter_in_substantive_arm"},
                 lambda: G.audit_augmented_design(x, ["raw_proj"], off,
                                                  incumbent_projection=proj, fold_ids=d.season))


def t10_monotone_nonlinear_transform(d):
    off = d.projected_team_off_possessions.to_numpy(float)
    x = d.assign(sq=np.exp(off / 10.0))
    rec = G.audit_augmented_design(x, ["sq"], off, fold_ids=d.season, raise_on_block=False)
    kinds = {f["kind"] for f in rec["blocking"]}
    MEASURED["monotone_transform_kinds"] = sorted(kinds)
    check("t10_monotone_transform_blocked",
          bool(kinds & {"candidate_affine_in_offset",
                        "candidate_monotone_transform_of_offset",
                        "candidate_exactly_determined_by_offset"}),
          f"kinds={sorted(kinds)}")


def t11_synthetic_pair_low_pairwise_correlation():
    """A pair that jointly reconstructs the offset while BOTH pairwise correlations are ~0."""
    rng = np.random.default_rng(11)
    n = 2000
    u = rng.standard_normal(n)
    w = rng.standard_normal(n)
    a, b = u + w, u - w
    off = (a + b) / 2.0                       # == u exactly
    df = pd.DataFrame({"a": a, "b": b})
    MEASURED["synthetic_pair_corr_ab"] = round(float(np.corrcoef(a, b)[0, 1]), 6)
    MEASURED["synthetic_pair_corr_a_offset"] = round(float(np.corrcoef(a, off)[0, 1]), 6)
    check("t11_pairwise_corrs_below_gate_threshold",
          abs(MEASURED["synthetic_pair_corr_ab"]) < 0.999
          and abs(MEASURED["synthetic_pair_corr_a_offset"]) < 0.999, "")
    rec = fg.audit(df, ["a", "b"], offset=off)
    MEASURED["feature_gate_on_synthetic_pair_passed"] = bool(rec["passed"])
    check("t11_feature_gate_passes_it", rec["passed"], "")
    expect_block("t11_guard_rejects_synthetic_pair",
                 {"pair_reconstructs_offset", "design_reconstructs_offset",
                  "augmented_rank_deficient"},
                 lambda: G.audit_augmented_design(df, ["a", "b"], off))


def _prereg():
    return json.loads(PREREG.read_text())["contrasts"]


def t12_preregistered_contrast_permitted(d):
    off = d.projected_team_off_possessions.to_numpy(float)
    pre = _prereg()
    digest = G.canonical_digest(pre)
    MEASURED["prereg_digest"] = digest
    rec = G.audit_augmented_design(
        d, ["contrast_own_minus_opp_pace_estimate"], off,
        incumbent_projection=off, fold_ids=d.season,
        preregistered_contrasts=pre, prereg_digest_expected=digest, raise_on_block=False)
    MEASURED["contrast_permitted"] = bool(rec["passed"])
    MEASURED["contrast_formula_max_abs_deviation"] = rec["contrasts"][
        "contrast_own_minus_opp_pace_estimate"]["max_abs_deviation"]
    MEASURED["contrast_augmented_rank"] = {
        "numerical_rank": rec["augmented_rank"]["numerical_rank"],
        "n_columns": rec["augmented_rank"]["n_features"],
        "condition_number": rec["augmented_rank"]["condition_number"]}
    MEASURED["contrast_r2_offset_on_design"] = rec["r2_offset_on_design"]
    MEASURED["contrast_per_fold"] = {
        k: {"n_rows": v["n_rows"], "rank": v["rank_report"]["numerical_rank"],
            "n_columns": v["rank_report"]["n_features"],
            "condition_number": round(v["rank_report"]["condition_number"], 9),
            "r2_offset_on_design": v["r2_offset_on_design"]}
        for k, v in rec["folds"].items()}
    check("t12_contrast_permitted", rec["passed"],
          f"kinds={[f['kind'] for f in rec['blocking']]}")
    check("t12_contrast_exact", rec["contrasts"][
        "contrast_own_minus_opp_pace_estimate"]["max_abs_deviation"] == 0.0, "")
    check("t12_contrast_full_rank_every_fold",
          all(v["rank_report"]["full_rank"] for v in rec["folds"].values()), "")
    check("t12_contrast_no_offset_reconstruction",
          all(v["r2_offset_on_design"] < G.NEAR_R2 for v in rec["folds"].values()), "")
    # and the pair is still rejected when BOTH the contrast and its inputs are present
    expect_block("t12_contrast_plus_inputs_rejected",
                 {"design_reconstructs_offset", "augmented_rank_deficient"},
                 lambda: G.audit_augmented_design(
                     d, ["contrast_own_minus_opp_pace_estimate", "own_est", "opp_est"], off,
                     fold_ids=d.season, preregistered_contrasts=pre,
                     prereg_digest_expected=digest))


def t13_contrast_not_preregistered(d):
    off = d.projected_team_off_possessions.to_numpy(float)
    expect_block("t13_contrast_not_preregistered", {"contrast_not_preregistered"},
                 lambda: G.audit_augmented_design(
                     d, ["contrast_own_minus_opp_pace_estimate"], off,
                     fold_ids=d.season, preregistered_contrasts=[]))


def t14_contrast_formula_mismatch(d):
    off = d.projected_team_off_possessions.to_numpy(float)
    pre = _prereg()
    x = d.copy()
    v = x["contrast_own_minus_opp_pace_estimate"].to_numpy(float).copy()
    v[0] += 1e-6                                  # one row, one micro-edit
    x["contrast_own_minus_opp_pace_estimate"] = v
    expect_block("t14_contrast_formula_mismatch", {"contrast_formula_mismatch"},
                 lambda: G.audit_augmented_design(
                     x, ["contrast_own_minus_opp_pace_estimate"], off, fold_ids=d.season,
                     preregistered_contrasts=pre,
                     prereg_digest_expected=G.canonical_digest(pre)))


def t15_prereg_digest_mismatch(d):
    off = d.projected_team_off_possessions.to_numpy(float)
    pre = _prereg()
    edited = json.loads(json.dumps(pre))
    edited[0]["formula"] = "own_est - opp_est + 0"       # same values, edited record
    expect_block("t15_prereg_digest_mismatch", {"contrast_prereg_digest_mismatch"},
                 lambda: G.audit_augmented_design(
                     d, ["contrast_own_minus_opp_pace_estimate"], off, fold_ids=d.season,
                     preregistered_contrasts=edited,
                     prereg_digest_expected=G.canonical_digest(pre)))


def t16_fold_local_degeneracy(d):
    off = d.projected_team_off_possessions.to_numpy(float)
    pre = _prereg()
    x = d.copy()
    m = (x.season == 2021).to_numpy()
    v = x["contrast_own_minus_opp_pace_estimate"].to_numpy(float).copy()
    v[m] = 0.0                                     # constant inside one chronological fold only
    x["contrast_own_minus_opp_pace_estimate"] = v
    pooled = G.audit_augmented_design(x, ["contrast_own_minus_opp_pace_estimate"], off,
                                      preregistered_contrasts=pre,
                                      prereg_digest_expected=G.canonical_digest(pre),
                                      contrast_atol=1e9,
                                      raise_on_block=False)          # no fold_ids: pooled only
    MEASURED["fold_degenerate_pooled_passes"] = bool(pooled["passed"])
    check("t16_pooled_audit_misses_it", pooled["passed"], "pooled audit should not catch it")
    expect_block("t16_fold_local_degeneracy",
                 {"fold_local_zero_variance", "fold_local_rank_deficient"},
                 lambda: G.audit_augmented_design(
                     x, ["contrast_own_minus_opp_pace_estimate"], off, fold_ids=x.season,
                     preregistered_contrasts=pre, prereg_digest_expected=G.canonical_digest(pre),
                     contrast_atol=1e9))            # formula check relaxed to isolate the fold check


def t17_recalibration_family(d):
    off = d.projected_team_off_possessions.to_numpy(float)
    x = d.assign(cal=off)
    # (a) declared SUBSTANTIVE -> the calibration parameter is hiding
    expect_block("t17a_calibration_hidden_in_substantive_arm",
                 {"calibration_parameter_in_substantive_arm"},
                 lambda: G.audit_augmented_design(x, ["cal"], off, incumbent_projection=off,
                                                  fold_ids=d.season))
    # (b) declared RECALIBRATION but with no nested null / multiplicity accounting
    expect_block("t17b_recalibration_family_incomplete", {"recalibration_family_incomplete"},
                 lambda: G.audit_augmented_design(
                     x, ["cal"], off, incumbent_projection=off, fold_ids=d.season,
                     declared_family=G.RECALIBRATION,
                     recalibration_declaration={"family_id": "RECAL_OFFSET_SLOPE"}))
    decl = {"family_id": "RECAL_OFFSET_SLOPE", "nested_null_id": "K0_MATCHED_SLOPE",
            "k0_carries_offset_slope": True, "n_hypotheses_in_family": 3,
            "multiplicity_procedure": "holm", "family_alpha": 0.05}
    # (c) declared RECALIBRATION with the nested null, but K0 lacks the same slope freedom
    bad = dict(decl, k0_carries_offset_slope=False)
    expect_block("t17c_k0_must_carry_the_same_slope", {"recalibration_family_incomplete"},
                 lambda: G.audit_augmented_design(
                     x, ["cal"], off, incumbent_projection=off, fold_ids=d.season,
                     declared_family=G.RECALIBRATION, recalibration_declaration=bad))
    # (d) complete declaration -> permitted
    rec = G.audit_augmented_design(x, ["cal"], off, incumbent_projection=off, fold_ids=d.season,
                                   declared_family=G.RECALIBRATION,
                                   recalibration_declaration=decl, raise_on_block=False)
    MEASURED["complete_recalibration_family_passes"] = bool(rec["passed"])
    check("t17d_complete_recalibration_permitted", rec["passed"],
          f"kinds={[f['kind'] for f in rec['blocking']]}")
    # (e) a substantive column may not ride along inside a recalibration arm
    x2 = x.assign(other=d.contrast_own_minus_opp_pace_estimate)
    expect_block("t17e_mixed_family_arm", {"mixed_family_arm"},
                 lambda: G.audit_augmented_design(
                     x2, ["cal", "other"], off, incumbent_projection=off, fold_ids=d.season,
                     declared_family=G.RECALIBRATION, recalibration_declaration=decl))


def t18_offset_is_mandatory_and_must_be_real(d):
    rec = G.audit_augmented_design(d, ["own_est", "opp_est"], None, raise_on_block=False)
    check("t18_offset_missing_blocks",
          {f["kind"] for f in rec["blocking"]} == {"offset_missing"},
          str([f["kind"] for f in rec["blocking"]]))
    expect_block("t18_placeholder_offset_blocks", {"offset_is_placeholder"},
                 lambda: G.audit_augmented_design(d, ["own_est", "opp_est"],
                                                  np.zeros(len(d))))


def t19_recalibration_slope_is_not_one(d):
    """S4's premise, measured directly rather than inferred from a variance ratio.

    This is a property of the FROZEN INCUMBENT's own calibration on its own target. It is not a
    comparative performance figure for any challenger.
    """
    m = np.isfinite(d.target)
    y = d.target.to_numpy(float)[m]
    p = d.projected_team_off_possessions.to_numpy(float)[m]
    X = np.column_stack([np.ones(len(p)), p])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    MEASURED["target_n"] = int(m.sum())
    MEASURED["var_target"] = round(float(np.var(y, ddof=1)), 5)
    MEASURED["var_projected_over_var_target"] = round(float(np.var(p, ddof=1) / np.var(y, ddof=1)), 6)
    MEASURED["variance_explained_vs_target"] = round(
        float(1 - np.var(y - p, ddof=1) / np.var(y, ddof=1)), 6)
    MEASURED["incumbent_calibration_intercept"] = round(float(b[0]), 6)
    MEASURED["incumbent_calibration_slope"] = round(float(b[1]), 6)
    check("t19_slope_is_not_one", abs(b[1] - 1.0) > 0.05, str(b[1]))
    check("t19_var_ratio_agrees_with_packet",
          abs(MEASURED["var_projected_over_var_target"] - 0.157) < 5e-4,
          str(MEASURED["var_projected_over_var_target"]))
    check("t19_variance_explained_agrees_with_packet",
          abs(MEASURED["variance_explained_vs_target"] - 0.11608) < 5e-5,
          str(MEASURED["variance_explained_vs_target"]))


def t20_conditions_the_contrast_depends_on(d):
    """Two structural facts the contrast's admissibility rests on. Measured, not assumed."""
    # (a) the exact orthogonality corr(contrast, offset) == 0 holds because the offset is shared
    #     within a game and the contrast is antisymmetric. It requires BOTH sides of every game.
    sides = d.groupby("game_id").size()
    MEASURED["games_with_two_resolved_sides"] = int((sides == 2).sum())
    MEASURED["games_with_one_resolved_side"] = int((sides == 1).sum())
    MEASURED["games_where_projection_differs_between_sides"] = int(
        (d.groupby("game_id")["projected_team_off_possessions"].nunique() > 1).sum())
    check("t20_all_games_two_sided", (sides == 1).sum() == 0, str(int((sides == 1).sum())))
    check("t20_projection_shared_within_game",
          MEASURED["games_where_projection_differs_between_sides"] == 0, "")
    # if one side of a game is dropped, the exact orthogonality is destroyed
    one_sided = d.drop(index=d.groupby("game_id").head(1).index[:400])
    r_broken = float(np.corrcoef(one_sided.contrast_own_minus_opp_pace_estimate,
                                 one_sided.projected_team_off_possessions)[0, 1])
    MEASURED["contrast_offset_corr_if_400_games_become_one_sided"] = round(r_broken, 6)
    check("t20_orthogonality_is_conditional", abs(r_broken) > 0.0,
          "dropping one side should break exact orthogonality")

    # (b) the exact-determination (nonlinear) test is informative only if the offset has ties
    off = d.projected_team_off_possessions
    vc = off.value_counts()
    MEASURED["offset_distinct_values"] = int(len(vc))
    MEASURED["offset_tie_groups_size_ge_2"] = int((vc >= 2).sum())
    g = d.groupby("projected_team_off_possessions")["own_est"].nunique()
    MEASURED["offset_tie_groups_where_own_est_constant"] = int((g == 1).sum())
    check("t20_determination_test_informative",
          MEASURED["offset_tie_groups_size_ge_2"] >= G.MIN_TIE_GROUPS, "")

    # (c) the incumbent's possession MAE, by overtime stratum -- reconciles the packet's two figures
    err = np.abs(d.target - d.projected_team_off_possessions)
    poss = pd.read_parquet(POSS, columns=["game_id", "period"])
    ot = poss.groupby("game_id")["period"].max().gt(4).rename("is_ot")
    m = d.game_id.map(ot).to_numpy(bool)
    MEASURED["possession_mae_pooled"] = round(float(err.mean()), 5)
    MEASURED["possession_mae_regulation"] = round(float(err[~m].mean()), 5)
    MEASURED["possession_mae_overtime"] = round(float(err[m].mean()), 5)
    MEASURED["overtime_rows"] = int(m.sum())


def t21_residual_gap_nonlinear_joint_reconstruction():
    """NEGATIVE RESULT, recorded on purpose: the guard's joint tests are LINEAR.

    A pair that reconstructs the offset through a nonlinear map (offset == a * b) is not caught by
    the R^2 / SVD machinery. The per-candidate exact-determination test is pairwise (candidate vs
    offset), not subset-wise, so it does not cover this either. This asserts nothing; it measures
    and records the gap so a passing guard record is never read as more than it is.
    """
    rng = np.random.default_rng(21)
    n = 2000
    a = rng.uniform(0.5, 3.0, n)
    b = rng.uniform(0.5, 3.0, n)
    off = a * b
    df = pd.DataFrame({"a": a, "b": b})
    rec = G.audit_augmented_design(df, ["a", "b"], off, raise_on_block=False)
    MEASURED["residual_gap_nonlinear_pair"] = {
        "relation": "offset == a * b (exact)",
        "r2_offset_on_pair_linear": rec["r2_offset_on_design"],
        "augmented_numerical_rank": rec["augmented_rank"]["numerical_rank"],
        "augmented_n_columns": rec["augmented_rank"]["n_features"],
        "guard_passed": bool(rec["passed"]),
        "blocking_kinds": [f["kind"] for f in rec["blocking"]],
    }


def main() -> int:
    d = build_panel()
    for fn, args in [
        (t01_feature_gate_byte_unchanged, ()), (t02_identity_reproduced, (d,)),
        (t03_feature_gate_passes_the_dependent_design, (d,)),
        (t04_guard_rejects_the_dependent_design, (d,)),
        (t05_isolation_would_miss_it, (d,)), (t06_exact_affine_candidate, (d,)),
        (t07_near_exact_affine_candidate, (d,)), (t08_independent_candidate_passes, (d,)),
        (t09_exact_function_of_incumbent_projection, (d,)),
        (t10_monotone_nonlinear_transform, (d,)),
        (t11_synthetic_pair_low_pairwise_correlation, ()),
        (t12_preregistered_contrast_permitted, (d,)), (t13_contrast_not_preregistered, (d,)),
        (t14_contrast_formula_mismatch, (d,)), (t15_prereg_digest_mismatch, (d,)),
        (t16_fold_local_degeneracy, (d,)), (t17_recalibration_family, (d,)),
        (t18_offset_is_mandatory_and_must_be_real, (d,)),
        (t19_recalibration_slope_is_not_one, (d,)),
        (t20_conditions_the_contrast_depends_on, (d,)),
        (t21_residual_gap_nonlinear_joint_reconstruction, ()),
    ]:
        try:
            fn(*args)
        except Exception:                                                    # noqa: BLE001
            _FAIL.append(f"{fn.__name__}: EXCEPTION\n{traceback.format_exc()}")

    (HERE / "MEASUREMENTS.json").write_text(
        json.dumps(MEASURED, indent=2, sort_keys=True, default=str))
    print(json.dumps(MEASURED, indent=2, sort_keys=True, default=str))
    if _FAIL:
        print("\nFAILURES:")
        for f in _FAIL:
            print(" -", f)
        print(f"\n{len(_FAIL)} failure(s)")
        return 1
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
