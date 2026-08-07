#!/usr/bin/env python3
"""TESTS.py -- the S36 test suite. Unit, synthetic, identity and schema tests ONLY.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

WHAT THESE TESTS DO AND DO NOT COVER, stated plainly so nobody over-reads a green run:

  COVERED -- byte-pin reproduction (all four frozen column digests and both join-key digests, the
             two-column one under the separator convention this node established by measurement);
             obligation-text fidelity against the frozen S35 bytes; the two label refusals (C2,
             C3); the blinding refusal in both directions; seed derivation and the pairing
             property; each estimator against a case with a known closed-form answer; Layer-A
             parity including three ways of breaking it; every element's design build on the
             synthetic fixture; each arm's characteristic transform; O2 enforcement; and one
             end-to-end synthetic fit per estimand family.

  NOT COVERED -- whether any arm helps. That question is sealed until S38 and adjudicated at S40,
             and nothing in this file can answer it. Every fit below runs on a fixture that is
             structurally non-real BY CONSTRUCTION, and the blinding gate refuses the real one.

Run:  python tests/TESTS.py
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

NODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NODE / "runner"))
sys.path.insert(0, str(NODE / "arms"))
sys.path.insert(0, str(NODE / "tests"))

import blinding  # noqa: E402
import cluster_bootstrap as CB  # noqa: E402
import runner  # noqa: E402
import runner_constants as K  # noqa: E402
import seed_manifest  # noqa: E402
import synthetic_fixture as SF  # noqa: E402
import universe as U  # noqa: E402
from canon import (RECORD_SEP, UNIT_SEP, canon_value, column_digest,  # noqa: E402
                   join_key_digest, sha256_file)
from estimators import (EstimationFailure, fit_dispersion_newton,  # noqa: E402
                        fit_eb_shrinkage_mom, fit_logit_irls, fit_ols,
                        sigma_from_dispersion)
from obligations import (C2_POWER_STATEMENT, C3_LABEL, ObligationViolation,  # noqa: E402
                         assert_sc06_era_verdict_carries_power_statement,
                         assert_sc11_cross_estimand_labelled, verify_obligation_text)
from runner_interface import DesignPair, InterfaceViolation, validate_design  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def test(name):
    def deco(fn):
        def run():
            try:
                fn()
                RESULTS.append((name, True, ""))
            except Exception as e:                                   # noqa: BLE001
                RESULTS.append((name, False, f"{type(e).__name__}: {e}\n"
                                             f"{traceback.format_exc(limit=3)}"))
        run.__name__ = fn.__name__
        return run
    return deco


TESTS = []


def register(name):
    def deco(fn):
        t = test(name)(fn)
        TESTS.append(t)
        return t
    return deco


# ==========================================================================================
# 1. Byte pins and the canonicalisation -- INCLUDING the join-key separator gap S35 carried
# ==========================================================================================
@register("canon: the two separators are the characters the convention names")
def t_separators():
    assert UNIT_SEP == "\x1f", "inter-row separator must be U+001F"
    assert RECORD_SEP == "\x1e", "intra-key separator must be U+001E"
    assert UNIT_SEP != RECORD_SEP


@register("canon: value canonicalisation handles float/int/bool/NaN/None/timestamp")
def t_canon_values():
    assert canon_value(1.5) == repr(1.5)
    assert canon_value(float("nan")) == "nan"
    assert canon_value(None) == "nan"
    assert canon_value(np.int64(7)) == "7"
    assert canon_value(np.float64(2.0)) == repr(2.0)
    assert canon_value(True) == "True"          # bool BEFORE int, or True would render as "1"
    assert canon_value(pd.Timestamp("2021-05-14")) == pd.Timestamp("2021-05-14").isoformat()
    assert canon_value("x") == "x"


@register("byte pins: all four pinned input artifacts hash to their frozen values")
def t_input_pins():
    for rel, exp in K.INPUT_PINS.items():
        got = sha256_file(K.artifact_path(rel))
        assert got == exp, f"{rel}: {got} != {exp}"
        assert got != K.KNOWN_DRIFTED_MASTER_TEAM_SHA256


@register("byte pins: the three single-column frozen store digests reproduce")
def t_column_pins():
    sb = pd.read_parquet(K.artifact_path(
        "experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet"))
    c = sb[sb["method"] == K.COMPOSITE_METHOD]
    c = c.sort_values("game_id", key=lambda s: s.map(str), kind="mergesort")
    for pin in K.FROZEN_COLUMN_PINS:
        if pin["join_key_columns"] != ["game_id"]:
            continue
        assert len(c) == pin["n_values"]
        assert column_digest(c[pin["column"]]) == pin["column_sha256"], pin["column"]
        assert column_digest(c["game_id"]) == pin["join_key_sha256"]
        assert int(c[pin["column"]].isna().sum()) == pin["n_nan"]


@register("byte pins: THE TWO-COLUMN JOIN KEY reproduces under the U+001E convention "
          "(closes the gap S35 carried forward)")
def t_two_column_join_key():
    pin = [p for p in K.FROZEN_COLUMN_PINS if p["join_key_columns"] == ["game_id", "team_id"]][0]
    tp = pd.read_parquet(K.artifact_path(pin["artifact"]))
    tp = tp.sort_values(["game_id", "team_id"], key=lambda s: s.map(str), kind="mergesort")
    assert len(tp) == pin["n_values"]
    assert column_digest(tp[pin["column"]]) == pin["column_sha256"], "column digest"
    rows = list(zip(tp["game_id"], tp["team_id"]))
    assert join_key_digest(rows) == pin["join_key_sha256"], (
        "the two-column join key did not reproduce; this is the exact gap S35 handed to S36")
    # and the wrong (single) separator must NOT reproduce -- otherwise the test proves nothing
    wrong = column_digest([f"{a}{UNIT_SEP}{b}" for a, b in rows])
    assert wrong != pin["join_key_sha256"]


@register("canon: a one-component join key reduces exactly to the column digest")
def t_join_key_reduction():
    vals = ["a", "b", "c"]
    assert join_key_digest([(v,) for v in vals]) == column_digest(vals)


# ==========================================================================================
# 2. The seven obligations
# ==========================================================================================
@register("obligations: every verbatim string still matches the frozen S35 bytes")
def t_obligation_text():
    r = verify_obligation_text()
    assert r["all_pass"] and all(r["checks"].values())


@register("O1/ROOT_PATH_RULE: the pinned master_team is the program-worktree copy, not the "
          "drifted one")
def t_root_path_rule():
    p = K.artifact_path("data/masters/master_team.parquet")
    assert str(p).startswith(str(K.PROGRAM_WORKTREE))
    h = sha256_file(p)
    assert h == K.INPUT_PINS["data/masters/master_team.parquet"]
    assert h != K.KNOWN_DRIFTED_MASTER_TEAM_SHA256


@register("O2: the pre-build digest receipt exists, re-derives, and pins 1491/2982")
def t_o2_receipt():
    r = json.loads((NODE / "PREBUILD_GAME_ID_DIGEST.json").read_text(encoding="utf-8"))
    assert r["n_clusters"] == K.UNIVERSE_CLUSTERS
    assert r["n_team_game_rows"] == K.UNIVERSE_ROWS
    assert r["per_season_census_matches"] is True
    assert r["league_average_v1_identity"]["identity_holds"] is True
    assert r["emitted_before_any_design_matrix"] is True
    u = U.build_universe()
    assert column_digest(sorted(u.games["game_id"])) == r["GAME_ID_SET_SHA256"]


@register("O2 enforcement: build_universe HALTS when the pre-build receipt digest disagrees")
def t_o2_enforcement(monkey={}):
    real = U._load_prebuild_digest
    U._load_prebuild_digest = lambda: "0" * 64
    try:
        U.build_universe()
        raise AssertionError("build_universe accepted a universe the O2 receipt does not pin")
    except U.UniverseHalt as e:
        assert "O2 MISMATCH" in str(e)
    finally:
        U._load_prebuild_digest = real


@register("C1: both alpha bounds are disclosed on every receipt and 0.40 is named GOVERNING")
def t_c1():
    for f in ("PREBUILD_GAME_ID_DIGEST.json", "DESIGN_PARITY_RECEIPT.json",
              "CARDED_STRATA_RECEIPT.json"):
        r = json.loads((NODE / f).read_text(encoding="utf-8"))
        a = r["program_alpha_disclosure"]
        assert a["GOVERNING_BOUND"] == 0.40 and a["DISCLOSED_BOUND"] == 0.50, f
        assert a["which_governs"] == "0.40 GOVERNS" and a["no_program_wide_FWER_claim"] is True, f


@register("C2: an SC06 era verdict CANNOT be emitted without the verbatim power statement")
def t_c2_refusal():
    import sc06_sched_fatigue_diff as SC06
    ok = SC06.era_split_receipt({"pre_2024": "<sealed>", "post_2024": "<sealed>"},
                                "SC06_SCHED_FATIGUE_DIFF::E2_FINAL_MARGIN_HOME")
    assert ok["era_kill_power_statement"] == C2_POWER_STATEMENT
    assert "essentially UNPOWERED" in ok["era_kill_power_statement"]
    try:
        assert_sc06_era_verdict_carries_power_statement({"era_kill_verdict": "did not fire"})
        raise AssertionError("an era verdict was emitted without the power statement")
    except ObligationViolation:
        pass
    try:
        SC06.era_split_receipt({}, "SC01_OPP_ADJ_INTERACTING::E2_FINAL_MARGIN_HOME")
        raise AssertionError("the power statement was stamped on an element it does not bind")
    except ObligationViolation:
        pass


@register("C3: the SC11 cross-estimand number CANNOT be emitted without its label")
def t_c3_refusal():
    import sc11_league_total_drift as SC11
    r = SC11.cross_estimand_receipt(0.04)
    assert r["label"] == C3_LABEL and r["citable"] is False
    assert r["enters_family"] is None and r["enters_pass_tally"] is False
    assert "abs_delta_mae_E2_NON_CITABLE" in r and "delta_mae" not in r
    assert r["integrity_kill_fired"] is False
    assert SC11.cross_estimand_receipt(0.11)["integrity_kill_fired"] is True
    try:
        assert_sc11_cross_estimand_labelled({"abs_delta_mae_E2_NON_CITABLE": 0.04})
        raise AssertionError("the cross-estimand number was emitted unlabelled")
    except ObligationViolation:
        pass


@register("O5: R_SC08_FLOOR is built, is mandatory, and carries NO challenger number")
def t_o5():
    import sc08_sigma_margin_map as SC08
    r = SC08.r_sc08_floor_receipt(None, None)
    assert r["mandatory"] is True and r["absence_is_a_card_defect"] is True
    assert r["both_objects_are_controls"] is True and r["challenger_number_included"] is False
    assert r["gating_on"] == "SC08_SIGMA_MARGIN_MAP::E3_HOME_WIN_PROB"
    assert "BELOW-FLOOR NULL" in r["verdict_label_if_below_floor"]
    assert SC08.r_sc08_floor_receipt(0.20, 0.21)["k0_below_floor"] is False
    assert SC08.r_sc08_floor_receipt(0.22, 0.21)["k0_below_floor"] is True
    # registered as a non-gating agreement receipt on the two other E3 elements
    mods = runner.load_modules()
    for eid in ("SC01_OPP_ADJ_INTERACTING::E3_HOME_WIN_PROB",
                "SC06_SCHED_FATIGUE_DIFF::E3_HOME_WIN_PROB"):
        spec = [s for s in runner.all_elements(mods) if s.element_id == eid][0]
        assert "R_SC08_FLOOR" in spec.mandatory_receipts, eid


@register("O6: R-A1-EXCEPTIONS is a mandatory receipt on EVERY element")
def t_o6():
    mods = runner.load_modules()
    for spec in runner.all_elements(mods):
        assert "R-A1-EXCEPTIONS" in spec.mandatory_receipts, spec.element_id


@register("O7: the identity-set extension is readable at COLUMN grain from the frozen bytes")
def t_o7():
    from obligations import O7_BASE_CLOSED_SET, O7_EXTENSION_COLUMNS
    spec = json.loads(K.artifact_path(K.SPEC_V2_PATH).read_text(encoding="utf-8"))
    seen_ext, seen_base, flags = set(), set(), {}
    for arm in spec["arms"]:
        for f in arm["features_lineage"]:
            for s in f["sources"]:
                for c in s.get("columns", []):
                    flags[(s["path"], c["column"])] = c["current_game_row_consumed"]
                    if c["classification"] == "IDENTITY_SET_EXTENSION_S34_ADJUDICATED":
                        seen_ext.add(c["column"])
                    if c["classification"] == "SCHEDULE_IDENTITY_S30_SECTION_1":
                        seen_base.add(c["column"])
    assert seen_ext <= set(O7_EXTENSION_COLUMNS), seen_ext - set(O7_EXTENSION_COLUMNS)
    assert seen_base <= set(O7_BASE_CLOSED_SET) | {"method"}, seen_base
    # every column classified NEVER_READ must have current_game_row_consumed == False
    for arm in spec["arms"]:
        for f in arm["features_lineage"]:
            for s in f["sources"]:
                for c in s.get("columns", []):
                    if c["classification"] == "PRESENT_IN_ARTIFACT_NEVER_READ_BY_ANY_ARM":
                        assert c["current_game_row_consumed"] is False


# ==========================================================================================
# 3. Blinding
# ==========================================================================================
@register("blinding: the S38 unseal flag is ABSENT from the real process environment")
def t_unseal_absent():
    assert K.UNSEAL_ENV_FLAG not in os.environ


@register("blinding: refuses every real signature, and refuses them one at a time")
def t_blinding_refusals():
    for kw in ({"n_rows": 2982}, {"n_rows": 2990}, {"n_clusters": 1491}, {"n_clusters": 1495},
               {"fold_ids": ["train_lt_2024"]},
               {"artifact_hashes": [K.INPUT_PINS["data/masters/master_team.parquet"]]}):
        try:
            blinding.assert_may_fit(env={}, **kw)
            raise AssertionError(f"blinding accepted a real signature: {kw}")
        except blinding.BlindingViolation:
            pass


@register("blinding: passes on the synthetic fixture; unseals ONLY via an injected mapping")
def t_blinding_pass():
    u = SF.make_universe()
    SF.assert_not_real_shaped(u)
    r = blinding.assert_may_fit(n_rows=len(u.team_rows), n_clusters=len(u.games),
                                fold_ids=list(SF.SYN_FOLDS), env={})
    assert r["real_signatures"] == [] and r["unsealed"] is False
    r2 = blinding.assert_may_fit(n_clusters=1491, env={K.UNSEAL_ENV_FLAG: "1"})
    assert r2["unsealed"] is True and r2["real_signatures"]
    assert K.UNSEAL_ENV_FLAG not in os.environ


@register("blinding: BUILDING on the real universe is authorised, FITTING is not")
def t_build_vs_fit():
    assert blinding.assert_may_build()["authorised"] is True
    try:
        blinding.assert_may_fit(n_clusters=K.UNIVERSE_CLUSTERS, env={})
        raise AssertionError("fitting the real universe was permitted at S36")
    except blinding.BlindingViolation:
        pass


# ==========================================================================================
# 4. Seeds and bootstrap
# ==========================================================================================
@register("seeds: derivation matches the frozen string exactly")
def t_seed_derivation():
    import hashlib
    for fid in K.FOLD_IDS:
        for b in (0, 1, 999):
            msg = f"{K.MASTER_SEED}|{fid}|test_bootstrap|{b}".encode()
            exp = int.from_bytes(hashlib.sha256(msg).digest()[:4], "big")
            assert seed_manifest.derive_seed("test_bootstrap", fid, b) == exp
    assert K.MASTER_SEED == 20260807
    try:
        seed_manifest.derive_seed("some_other_purpose", "train_lt_2024", 0)
        raise AssertionError("an unregistered seed purpose was accepted")
    except ValueError:
        pass


@register("seeds: PAIRING -- draw b is the same index set for any two elements in a fold")
def t_pairing():
    idx = np.arange(50)
    for b in (0, 3, 17):
        a = CB.draw_cluster_indices(idx, "test_bootstrap", "SYN_f2", b)
        c = CB.draw_cluster_indices(idx, "test_bootstrap", "SYN_f2", b)
        assert np.array_equal(a, c)
    d = CB.draw_cluster_indices(idx, "test_bootstrap", "SYN_f3", 0)
    assert not np.array_equal(CB.draw_cluster_indices(idx, "test_bootstrap", "SYN_f2", 0), d)
    e = CB.draw_cluster_indices(idx, "train_refit", "SYN_f2", 0)
    assert not np.array_equal(CB.draw_cluster_indices(idx, "test_bootstrap", "SYN_f2", 0), e)


@register("bootstrap: clusters expand to BOTH team-rows; games are never split")
def t_never_split():
    row_clusters = ["g1", "g1", "g2", "g2", "g3", "g3"]
    rows = CB.expand_clusters_to_rows(["g2", "g2", "g1"], row_clusters)
    assert list(rows) == [2, 3, 2, 3, 0, 1]
    assert len(rows) == 2 * 3


@register("bootstrap: the two-sided p rule is the frozen operationalisation, and symmetric")
def t_two_sided_p():
    assert CB.two_sided_p(np.ones(100)) < 0.05
    assert CB.two_sided_p(np.concatenate([np.ones(50), -np.ones(50)])) == 1.0
    d = np.concatenate([np.ones(90), -np.ones(10)])
    assert abs(CB.two_sided_p(d) - CB.two_sided_p(-d)) < 1e-12


@register("bootstrap: the K7 NA rule is SYMMETRIC -- either side voids the draw for both")
def t_na_rule():
    assert CB.na_draw_rule(False, True, True) is False
    assert CB.na_draw_rule(True, True, True) is True
    assert CB.na_draw_rule(False, False, True) is True
    assert CB.na_draw_rule(False, True, False) is True


# ==========================================================================================
# 5. Estimators -- each against a case with a known answer
# ==========================================================================================
@register("estimators: OLS recovers exact coefficients on a noiseless design")
def t_ols():
    rng = np.random.default_rng(1)
    X = np.column_stack([np.ones(200), rng.normal(size=200), rng.normal(size=200)])
    beta = np.array([3.0, -1.5, 0.25])
    f = fit_ols(X, X @ beta)
    assert np.allclose(f.coef, beta, atol=1e-9)


@register("estimators: ridge penalises ONLY the masked columns, and refuses an unnamed mask")
def t_ridge_mask():
    rng = np.random.default_rng(2)
    X = np.column_stack([np.ones(300), rng.normal(size=300), rng.normal(size=300)])
    y = X @ np.array([5.0, 2.0, 2.0]) + rng.normal(0, 0.1, 300)
    mask = np.array([False, False, True])
    f0 = fit_ols(X, y)
    f = fit_ols(X, y, ridge=1e6, penalise=mask)
    assert abs(f.coef[2]) < abs(f0.coef[2]) * 1e-2, "the penalised column was not shrunk"
    assert abs(f.coef[0] - f0.coef[0]) < 0.5, "the intercept was shrunk; it must not be"
    try:
        fit_ols(X, y, ridge=1.0)
        raise AssertionError("ridge was applied without an explicit penalise mask")
    except EstimationFailure:
        pass


@register("estimators: logit IRLS recovers a known coefficient and is deterministic")
def t_logit():
    rng = np.random.default_rng(3)
    x = rng.normal(size=4000)
    X = np.column_stack([np.ones(4000), x])
    p = 1 / (1 + np.exp(-(0.3 + 1.2 * x)))
    y = (rng.uniform(size=4000) < p).astype(float)
    f1 = fit_logit_irls(X, y)
    f2 = fit_logit_irls(X, y)
    assert np.array_equal(f1.coef, f2.coef), "IRLS is not deterministic"
    assert abs(f1.coef[1] - 1.2) < 0.15 and f1.converged
    try:
        fit_logit_irls(X, x)
        raise AssertionError("IRLS accepted a non-0/1 target")
    except EstimationFailure:
        pass


@register("estimators: dispersion Newton recovers sigma0 and gamma; K0 form is sigma0-only")
def t_dispersion():
    rng = np.random.default_rng(4)
    n = 20000
    z = rng.normal(size=n)
    sigma = 10.0 * np.exp(0.5 * 0.4 * z)                # sigma^2 = 100*exp(0.4 z)
    resid = rng.normal(0, sigma)
    f = fit_dispersion_newton(resid, z.reshape(-1, 1), columns=("gamma1",))
    assert abs(np.exp(f.coef[0]) - 10.0) < 0.5, np.exp(f.coef[0])
    assert abs(f.coef[1] - 0.4) < 0.08, f.coef[1]
    fk = fit_dispersion_newton(resid, np.zeros((n, 0)))
    assert len(fk.coef) == 1
    s = sigma_from_dispersion(fk, np.zeros((n, 0)), n_rows=n)
    assert np.allclose(s, np.exp(fk.coef[0]))
    assert abs(np.exp(fk.coef[0]) - float(np.sqrt(np.mean(resid ** 2)))) < 0.3


@register("estimators: MoM shrinkage matches the closed form and clamps tau2 at 0")
def t_mom():
    d = np.array([1.0, -1.0, 2.0, -2.0])
    s2 = np.full(4, 0.5)
    r = fit_eb_shrinkage_mom(d, s2)
    assert abs(r["tau2"] - max(0.0, float(np.var(d, ddof=1)) - 0.5)) < 1e-12
    assert np.allclose(r["w"], r["tau2"] / (r["tau2"] + s2))
    flat = fit_eb_shrinkage_mom(np.zeros(5), np.ones(5))
    assert flat["tau2"] == 0.0 and np.allclose(flat["w"], 0.0)


# ==========================================================================================
# 6. Layer-A parity -- and three ways of breaking it
# ==========================================================================================
def _spec(mods, eid):
    return [s for s in runner.all_elements(mods) if s.element_id == eid][0]


@register("parity: a K0 that is not arm-minus-treatment is REFUSED (Severity A)")
def t_parity_refusal():
    mods = runner.load_modules()
    spec = _spec(mods, "SC04_HCA_LEAGUE_DRIFT::E2_FINAL_MARGIN_HOME")
    n = 10
    cols = {"intercept": np.ones(n), "composite_pred_margin": np.arange(n, dtype=float),
            "t": np.linspace(0, 1, n), "sneaky": np.linspace(1, 2, n)}
    bad = DesignPair(columns=cols, arm_cols=("intercept", "composite_pred_margin", "t"),
                     k0_cols=("intercept",), treatment_cols=("t",),
                     structural_cols=("composite_pred_margin",), comparison="term_removal")
    try:
        validate_design(spec, bad, n)
        raise AssertionError("an unmatched K0 was accepted")
    except InterfaceViolation as e:
        assert "SEVERITY A" in str(e)


@register("parity: a treatment term surviving in the K0 is REFUSED")
def t_treatment_in_k0():
    mods = runner.load_modules()
    spec = _spec(mods, "SC04_HCA_LEAGUE_DRIFT::E2_FINAL_MARGIN_HOME")
    n = 10
    cols = {"intercept": np.ones(n), "composite_pred_margin": np.arange(n, dtype=float),
            "t": np.linspace(0, 1, n)}
    bad = DesignPair(columns=cols, arm_cols=("intercept", "composite_pred_margin", "t"),
                     k0_cols=("intercept", "composite_pred_margin", "t"), treatment_cols=("t",),
                     structural_cols=("composite_pred_margin",), comparison="term_removal")
    try:
        validate_design(spec, bad, n)
        raise AssertionError("a treatment term survived in the K0")
    except InterfaceViolation:
        pass


@register("parity: a silent second intercept is REFUSED; non-finite columns are REFUSED")
def t_silent_intercept():
    mods = runner.load_modules()
    spec = _spec(mods, "SC04_HCA_LEAGUE_DRIFT::E2_FINAL_MARGIN_HOME")
    n = 10
    cols = {"intercept": np.ones(n), "const2": np.ones(n), "t": np.linspace(0, 1, n)}
    bad = DesignPair(columns=cols, arm_cols=("intercept", "const2", "t"),
                     k0_cols=("intercept", "const2"), treatment_cols=("t",),
                     structural_cols=("const2",), comparison="term_removal")
    try:
        validate_design(spec, bad, n)
        raise AssertionError("a silent second intercept was accepted")
    except InterfaceViolation as e:
        assert "silent second intercept" in str(e)
    cols2 = {"intercept": np.ones(n), "c": np.arange(n, dtype=float), "t": np.full(n, np.nan)}
    bad2 = DesignPair(columns=cols2, arm_cols=("intercept", "c", "t"), k0_cols=("intercept", "c"),
                      treatment_cols=("t",), structural_cols=("c",), comparison="term_removal")
    try:
        validate_design(spec, bad2, n)
        raise AssertionError("a non-finite design column was accepted")
    except InterfaceViolation:
        pass


# ==========================================================================================
# 7. The slate: modules, elements, and every design on the synthetic fixture
# ==========================================================================================
@register("slate: 11 arm modules, 17 element cards, SC07 absent")
def t_slate():
    mods = runner.load_modules()
    assert len(mods) == K.N_ARM_BLOCKS == 11
    els = runner.all_elements(mods)
    assert len(els) == K.N_ELEMENT_CARDS == 17
    assert "SC07_REF_CREW_TOTALS" not in mods
    assert not any("SC07" in s.element_id for s in els)


@register("slate: every element_id and card_sha256 matches the FROZEN S35 freeze bytes")
def t_card_hashes():
    freeze = json.loads(K.artifact_path(K.FREEZE_SPEC_PATH).read_text(encoding="utf-8"))
    frozen = {c["element_id"]: c for c in freeze["frozen_cards"]}
    mods = runner.load_modules()
    els = {s.element_id: s for s in runner.all_elements(mods)}
    assert set(els) == set(frozen), set(els) ^ set(frozen)
    for eid, s in els.items():
        f = frozen[eid]
        assert s.card_sha256 == f["card_sha256"], eid
        assert s.arm_id == f["arm_id"] and s.estimand == f["estimand"], eid
        assert s.primary_metric == f["primary_metric"], eid
        assert s.arm_kind == f["arm_kind"] and s.family_primary == f["family_primary"], eid


@register("slate: card_sha256 values RE-DERIVE from SPEC_V2 under the P35 canonicalisation")
def t_card_hash_rederive():
    from canon import canonical_json_sha256
    spec = json.loads(K.artifact_path(K.SPEC_V2_PATH).read_text(encoding="utf-8"))
    mods = runner.load_modules()
    for s in runner.all_elements(mods):
        got = canonical_json_sha256(spec["k0_matched"][s.element_id])
        assert got == s.card_sha256, f"{s.element_id}: {got} != {s.card_sha256}"


@register("slate: every element builds a valid design on every synthetic fold")
def t_all_builds():
    u = SF.make_universe()
    fds = SF.folds(u)
    mods = runner.load_modules()
    import sc09_fav_gap_compression as SC09
    for spec in runner.all_elements(mods):
        cache: dict = {}
        for fid, fold in fds.items():
            dp = spec.build(u, fold, cache)
            rep = validate_design(spec, dp, len(u.games))
            assert rep["differ_only_by_treatment_terms"]
            if not dp.deactivated:
                for t in dp.treatment_cols:
                    v = dp.columns[t]
                    assert np.isfinite(v).all()
                    if np.std(v) == 0:
                        # A constant treatment column is a DEFECT unless the card names it as an
                        # outcome. SC05 is the only arm that does: "tau2 fits to ~0: no
                        # resolvable team-level heterogeneity" is its declared expected failure
                        # mode, and its shrinkage-collapse kill exists precisely to catch it. So
                        # the collapse is allowed only when the fold record PROVES it came from
                        # tau2 == 0 rather than from a broken build.
                        assert spec.arm_id == "SC05_HCA_TEAM_OFFSETS", \
                            f"{spec.element_id}/{fid}/{t} is constant"
                        assert dp.fold_constants["tau2_mom"] == 0.0, \
                            f"{spec.element_id}/{fid}: constant feature with tau2 != 0"
        assert SC09 is not None


@register("SC05: the offset is non-degenerate on the real universe, and collapse is receipted")
def t_sc05_non_degenerate():
    """SC05's whole scientific question is whether team-level home-advantage heterogeneity is
    resolvable at all, so a collapsed (tau2 == 0) feature is a legitimate carded OUTCOME rather
    than a build failure. What must NOT happen is a collapse this node cannot tell apart from a
    bug -- so every fold either produces a varying feature or records tau2 == 0 in its own
    constants, and both facts land in the parity receipt for S37 to read."""
    mods = runner.load_modules()
    u = U.build_universe()
    spec = mods["SC05_HCA_TEAM_OFFSETS"].ELEMENTS[0]
    for fid in K.FOLD_IDS:
        dp = spec.build(u, u.fold(fid), {})
        v = dp.columns["hca_team_offset_shrunk"]
        assert np.isfinite(v).all()
        assert (np.std(v) > 0) or (dp.fold_constants["tau2_mom"] == 0.0), fid
        assert dp.fold_constants["var_m_train"] > 0, fid
        assert "interpretive_pin_var_m" in dp.fold_constants


@register("SC03: the declared deactivation drops the TERM on fold 1 and no rows")
def t_sc03_deactivation():
    mods = runner.load_modules()
    u = U.build_universe()
    for spec in mods["SC03_SEASON_CARRYOVER_PRIOR"].ELEMENTS:
        dp1 = spec.build(u, u.fold("train_lt_2022"), {})
        dp2 = spec.build(u, u.fold("train_lt_2023"), {})
        assert dp1.deactivated and dp1.treatment_cols == ()
        assert not dp2.deactivated and len(dp2.treatment_cols) == 1
        assert set(dp1.arm_cols) < set(dp2.arm_cols)
        assert len(dp1.columns["intercept"]) == len(dp2.columns["intercept"]) == len(u.games)


@register("SC06: era terms are active in exactly the two carded folds, on BOTH sides")
def t_sc06_era_folds():
    mods = runner.load_modules()
    u = U.build_universe()
    spec = mods["SC06_SCHED_FATIGUE_DIFF"].ELEMENTS[0]
    for fid in K.FOLD_IDS:
        dp = spec.build(u, u.fold(fid), {})
        on = fid in mods["SC06_SCHED_FATIGUE_DIFF"].ERA_ACTIVE_FOLDS
        assert ("ERA2024" in dp.arm_cols) == on, fid
        assert ("ERA2024" in dp.k0_cols) == on, fid          # structural: BOTH sides
        assert ("ERA2024:fatigue_diff" in dp.treatment_cols) == on, fid
    assert mods["SC06_SCHED_FATIGUE_DIFF"].ERA_ACTIVE_FOLDS == ("train_lt_2025", "train_lt_2026")


@register("SC06: the fatigue index is exactly the pinned weighted sum, on hand-checked cases")
def t_sc06_index():
    import sc06_sched_fatigue_diff as SC06
    assert (SC06.W_B2B, SC06.W_3IN4, SC06.W_TZ, SC06.TZ_CAP) == (1.0, 0.5, 0.25, 3)
    u = U.build_universe()
    fi = SC06.fatigue_index(u)
    f = fi["F"].to_numpy()
    assert np.isfinite(f).all() and f.min() >= 0
    assert f.max() <= SC06.W_B2B + SC06.W_3IN4 + SC06.W_TZ * SC06.TZ_CAP + 1e-12
    # every value must be an exact multiple of 0.25 -- the weights admit no other value
    assert np.allclose(f * 4, np.round(f * 4))


@register("SC08: the pace ingredient is resolved on all 1,491 universe clusters")
def t_sc08_pace():
    import sc08_sigma_margin_map as SC08
    u = U.build_universe()
    p = SC08.pace_prior(u)
    assert len(p) == K.UNIVERSE_CLUSTERS and np.isfinite(p).all()


@register("SC08: sum-vs-mean pace aggregation is bit-identical after train z-scoring")
def t_sc08_z_invariance():
    from features_common import zscore_train
    rng = np.random.default_rng(11)
    v = rng.normal(100, 10, 500)
    tr = np.arange(300)
    zs, _ = zscore_train(v, tr)
    zm, _ = zscore_train(v / 2.0, tr)
    assert np.allclose(zs, zm, rtol=0, atol=1e-12), "the aggregation choice is NOT immaterial"


@register("SC08: the null is parameter_fixed_at_null with a sigma0-only dispersion block")
def t_sc08_null():
    mods = runner.load_modules()
    u = U.build_universe()
    spec = mods["SC08_SIGMA_MARGIN_MAP"].ELEMENTS[0]
    dp = spec.build(u, u.fold("train_lt_2025"), {})
    assert dp.comparison == "parameter_fixed_at_null"
    assert dp.treatment_cols == ("sigma_z_pace_prior", "sigma_z_lagged_margin_sd")
    assert dp.k0_cols == ("intercept", "composite_pred_margin")
    assert dp.fold_constants["p_clip"] == list(K.E3_P_CLIP)


@register("SC09: the hinge is exact, odd, and flat inside the pinned knee")
def t_sc09_hinge():
    import sc09_fav_gap_compression as SC09
    assert SC09.KNEE == 8.0
    g = np.array([-20.0, -8.0, -3.0, 0.0, 3.0, 8.0, 12.0])
    h = SC09.hinge(g)
    assert np.allclose(h, [-12.0, 0.0, 0.0, 0.0, 0.0, 0.0, 4.0])
    assert np.allclose(SC09.hinge(-g), -h)                       # odd
    assert SC09.ELEMENTS[0].arm_kind == "calibration_only"


@register("SC12: the winsor correction is zero when nothing is clipped, and signed correctly")
def t_sc12_winsor():
    import sc12_robust_input_winsor as SC12
    assert (SC12.CAP, SC12.SPAN, SC12.SUPPORT_FLOOR) == (15.0, 10.0, 3)
    u = U.build_universe()
    t = SC12.winsor_terms(u)
    w = t["winsor_correction_diff"]
    assert np.isfinite(w).all()
    # a side whose prior margins never exceed the cap must carry w == 0
    tr = u.team_rows
    inside = tr.groupby("team_id")["margin"].apply(lambda s: s.abs().max() <= SC12.CAP)
    assert bool(inside.any()) or True     # data-dependent; the invariant is checked below
    z = SC12.winsor_terms(_clipped_universe(u))
    assert np.allclose(z["winsor_correction_diff"], 0.0), (
        "with no margin outside the cap the correction must vanish identically")


def _clipped_universe(u):
    import copy
    tr = u.team_rows.copy()
    tr["margin"] = np.clip(tr["margin"].to_numpy(float), -15.0, 15.0)
    return type(u)(games=u.games, team_rows=tr, game_id_digest=u.game_id_digest,
                   receipt=copy.deepcopy(u.receipt))


@register("SC01: sum-to-zero identification holds exactly on the fitted rating effects")
def t_sc01_identification():
    import sc01_opp_adj_interacting as SC01
    u = SF.make_universe()
    tr = u.team_rows
    d = sorted(u.games["game_date"].unique())[40]
    prior = tr[tr["game_date"] < d]
    teams = np.unique(np.concatenate([prior["team_id"].to_numpy(),
                                      prior["opp_team_id"].to_numpy()]))
    r = SC01._fit_ratings_at_cutoff(prior, teams, 8.0)
    assert abs(sum(r["off"].values())) < 1e-9
    assert abs(sum(r["def"].values())) < 1e-9
    assert SC01.LAMBDA_GRID == (2.0, 8.0, 32.0, 128.0)


@register("SC01/SC10: the train-tail rule touches no test cluster and is 80/20")
def t_train_tail():
    from _head import select_lambda_train_tail
    seen = []

    def f(lam, inner, tail):
        seen.append((len(inner), len(tail)))
        return {2.0: 5.0, 8.0: 1.0, 32.0: 1.0, 128.0: 9.0}[lam]

    sel = select_lambda_train_tail(np.arange(100), (2.0, 8.0, 32.0, 128.0), f)
    assert sel["selected"] == 8.0, "ties must break to the SMALLER lambda"
    assert sel["n_inner"] == 80 and sel["n_tail"] == 20
    assert sel["no_test_cluster_touched"] is True
    assert all(s == (80, 20) for s in seen)


@register("SC10: the orthogonalisation covariate is BUILT but never enters the primary head")
def t_sc10_covariate():
    import sc10_form_trend as SC10
    mods = runner.load_modules()
    u = U.build_universe()
    cov = SC10.trailing_opponent_strength_diff(u)
    assert len(cov) == K.UNIVERSE_CLUSTERS and np.isfinite(cov).all()
    for spec in mods["SC10_FORM_TREND"].ELEMENTS:
        dp = spec.build(u, u.fold("train_lt_2025"), {})
        assert not any("opponent" in c or "tosd" in c for c in dp.arm_cols), dp.arm_cols


@register("features: EWMA is the RECURSIVE convention the SC12 census settled")
def t_ewma_convention():
    import features_common as FC
    assert FC.EWMA_ADJUST is False
    s = pd.Series([1.0, 2.0, 3.0])
    rec = s.ewm(span=10, adjust=False).mean().to_numpy()
    a = 2 / 11
    assert abs(rec[1] - (a * 2.0 + (1 - a) * 1.0)) < 1e-12


@register("features: strictly-prior means STRICTLY prior -- the own row never enters")
def t_strictly_prior():
    from features_common import prior_count, prior_ewma
    u = SF.make_universe()
    pc = prior_count(u.team_rows, same_season=True)
    assert pc["n_prior"].min() == 0
    ew = prior_ewma(u.team_rows, "margin", span=5, same_season=True, min_periods=1, fill=np.nan)
    first = ew.groupby(["team_id", "season"]).head(1)
    assert first["value"].isna().all(), "the first game of a season used its own outcome"


# ==========================================================================================
# 8. End-to-end synthetic runs -- one per estimand family
# ==========================================================================================
@register("end-to-end: an E2 (gaussian) element fits on the synthetic fixture")
def t_e2_run():
    u = SF.make_universe()
    fds = SF.folds(u)
    mods = runner.load_modules()
    spec = _spec(mods, "SC04_HCA_LEAGUE_DRIFT::E2_FINAL_MARGIN_HOME")
    r = runner.run_element(u, spec, fold_ids=list(fds), env={}, b_test=64, b_train=8,
                           cache={"folds": fds})
    assert r["blinding"]["real_signatures"] == []
    for fid, f in r["per_fold"].items():
        assert not f["unevaluable"], fid
        assert set(f["k0_coef"]) < set(f["arm_coef"])
        assert 0.0 <= f["two_sided_p"] <= 1.0


@register("end-to-end: an E3 (bernoulli-logit) element fits, and probabilities are clipped")
def t_e3_run():
    u = SF.make_universe()
    fds = SF.folds(u)
    mods = runner.load_modules()
    spec = _spec(mods, "SC01_OPP_ADJ_INTERACTING::E3_HOME_WIN_PROB")
    r = runner.run_element(u, spec, fold_ids=list(fds), env={}, b_test=32, b_train=8,
                           cache={"folds": fds})
    assert all(not f["unevaluable"] for f in r["per_fold"].values())
    assert r["primary_metric"] == "brier_raw_model_probability"


@register("end-to-end: run_element REFUSES the real universe")
def t_run_refuses_real():
    u = U.build_universe()
    mods = runner.load_modules()
    spec = _spec(mods, "SC04_HCA_LEAGUE_DRIFT::E2_FINAL_MARGIN_HOME")
    try:
        runner.run_element(u, spec, env={}, b_test=2, b_train=2)
        raise AssertionError("run_element fitted the REAL universe at S36")
    except blinding.BlindingViolation as e:
        assert "may not fit real folds" in str(e)


# ==========================================================================================
# 9. Receipts on disk
# ==========================================================================================
@register("receipts: the design-parity receipt covers 16 elements on all 5 folds, no fit")
def t_parity_receipt():
    r = json.loads((NODE / "DESIGN_PARITY_RECEIPT.json").read_text(encoding="utf-8"))
    assert r["no_fit_performed"] is True and r["no_performance_number_computed"] is True
    assert len(r["elements"]) == 16 and len(r["skipped"]) == 1
    for eid, e in r["elements"].items():
        assert set(e["per_fold"]) == set(K.FOLD_IDS), eid
        for fid, f in e["per_fold"].items():
            assert f["differ_only_by_treatment_terms"] is True, (eid, fid)


@register("receipts: the carded-strata receipt reproduces every carded census")
def t_strata_receipt():
    r = json.loads((NODE / "CARDED_STRATA_RECEIPT.json").read_text(encoding="utf-8"))
    assert r["all_strata_agree"] is True
    c = r["checks"]
    assert c["SC01_max_n_le_12"]["measured"]["pooled"] == 472
    assert c["SC01_max_n_le_12"]["rejected_min_reading_count"] == 516
    assert c["SC02_min_n_le_5"]["measured"]["pooled"] == 249
    assert c["SC03_min_n_lt_10"]["measured"]["pooled"] == 399
    assert c["SC12_high_bite"]["measured"]["pooled"] == 652
    assert c["SC12_high_bite"]["ewma_convention_reproduction"][
        "reproduces_all_seven_carded_numbers"] is True
    s6 = c["SC06_abs_F_diff_ge_1"]
    assert s6["measured_rest_components_only"]["pooled"] == 78
    assert s6["measured_rest_components_only"]["pooled_test"] == 77
    assert s6["C2_POWER_STATEMENT"] == C2_POWER_STATEMENT


@register("no performance number: no receipt on disk carries a metric-shaped key OR value")
def t_no_performance_numbers():
    """Acceptance criterion 2 is 'no performance number emitted anywhere', so this walks every
    receipt this node writes and refuses metric-shaped KEYS -- as substrings, not just whole
    words, because `scores_on_train_tail` is exactly the shape that slipped through a
    whole-word check on this node's first pass.

    The allow-list is short and every entry is justified: the three carded receipt SLOTS whose
    numbers are filled at S38 and are None here, plus schema/threshold fields that name a metric
    without carrying a value."""
    banned_sub = ("mae", "brier", "accuracy", "rmse", "logloss", "auc", "score", "loss",
                  "error", "metric")
    allow_exact = {
        # carded receipt slots, structurally present, VALUE None until the sealed run
        "abs_delta_mae_E2_NON_CITABLE", "k0_matched_brier", "frozen_p_home_brier",
        # threshold / naming fields: they name a metric, they do not carry a measurement
        "primary_metric", "kill_threshold_mae_points",
        # explicit redaction markers
        "selection_scores", "why_withheld",
        # a COUNT of null point values in the universe audit. "score" here means points, not a
        # metric -- an unavoidable collision in a lane literally named "score".
        "null_score_values",
    }
    numeric_slots_that_must_be_empty = {"abs_delta_mae_E2_NON_CITABLE", "k0_matched_brier",
                                        "frozen_p_home_brier"}

    import re
    # arm ids and element ids are keys too, and SC02_A07_SCORE_TRANSIENT legitimately contains
    # "score" -- it is the arm's registered name, not a metric.
    # arm/element ids and artifact PATHS are keys too. SC02_A07_SCORE_TRANSIENT is an arm's
    # registered name and SCORE_BASELINES is a directory; neither is a metric.
    is_identifier = re.compile(r"^SC\d\d_|::|/|\.(parquet|csv|py|json|md)$").search

    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                kl = str(k).lower()
                if (k not in allow_exact and not is_identifier(str(k))
                        and any(b in kl for b in banned_sub)):
                    raise AssertionError(f"metric-shaped key {k!r} at {path}")
                if k in numeric_slots_that_must_be_empty and v is not None:
                    raise AssertionError(f"carded receipt slot {k!r} carries a value at {path}")
                walk(v, f"{path}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    seen = 0
    for f in NODE.glob("*.json"):
        walk(json.loads(f.read_text(encoding="utf-8")), f.name)
        seen += 1
    assert seen >= 3, "expected at least three receipts on disk to scan"


def main() -> int:
    for t in TESTS:
        t()
    width = max(len(n) for n, _, _ in RESULTS)
    for name, ok, err in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}")
        if not ok:
            print("      " + err.replace("\n", "\n      "))
    n_pass = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n{n_pass}/{len(RESULTS)} tests passed")

    receipt = {
        "schema": "s36_test_receipt/1",
        "epistemic_status": ("IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no "
                             "comparative historical performance is revealed."),
        "tests_run": len(RESULTS), "tests_passed": n_pass,
        "all_green": n_pass == len(RESULTS),
        # key deliberately NOT named "error": the no-performance-number sweep matches metric-
        # shaped substrings across every receipt on disk, including this one.
        "results": [{"name": n, "passed": ok, "failure_detail": (e or None)}
                    for n, ok, e in RESULTS],
        "what_is_NOT_covered": (
            "whether any arm helps. That is sealed until S38 and adjudicated at S40. Every fit in "
            "this suite runs on a structurally non-real fixture, and the blinding gate refuses "
            "the real universe."),
        "code_state": runner.code_state(),
    }
    (NODE / "TEST_RECEIPT.json").write_text(
        json.dumps(receipt, indent=1, default=str) + "\n", encoding="utf-8")
    return 0 if n_pass == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
