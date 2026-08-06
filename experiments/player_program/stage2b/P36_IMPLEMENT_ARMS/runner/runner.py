#!/usr/bin/env python3
"""runner.py -- the P36 shared task-specific runner (`p36_shared_runner/1`).

Single entry point `run_arm`: blinding -> guard byte pins -> arm-module conformance -> P26
(before P25) -> per-fold P22/P25 -> P27 -> paired quasi-Poisson point fits -> paired test
bootstrap -> training-cluster refit bootstrap (K7 symmetric NA rule) -> K0_FLAT diagnostic ->
I13-convention receipt. Frozen semantics documented in RUNNER_INTERFACE.md; frozen values in
runner_constants.py.

The runner never selects among enumeration elements, never adds an intercept, never deviates
from the frozen estimation objective, and REFUSES real folds without the P38_UNSEALED flag.

Optional module hook honoured here (documented in RUNNER_INTERFACE.md section 2a):
`structurally_deactivated_folds() -> list[str]` -- folds a card structurally deactivates for
arm AND null identically (A11: train_lt_2022). Missing hook == no deactivation.
"""
from __future__ import annotations

import numpy as np

import blinding
import cluster_bootstrap as cb
import guard_harness as gh
import k0_flat as kf
import quasipoisson_irls as qp
import receipts
import runner_interface as ri
import seed_manifest as sm
from runner_constants import (B_TEST_BOOTSTRAP, B_TRAIN_REFIT, CLUSTER_COL,
                              DECLARED_FAMILY_ALL_FITTED_ARMS, INTERCEPT_COL, OFFSET_COL,
                              TARGET_COL_REAL)

FINAL_FOLD_ID = "FINAL_ASSEMBLED_DESIGN"


class RunnerRefusal(RuntimeError):
    """Raised when a frozen precondition fails. The arm/fold is not fitted."""


def _materialise(universe, bundle):
    W = universe.copy()
    for name, v in bundle["columns"].items():
        W[name] = np.asarray(v, float)
    return W


def _design_matrix(W, cols, idx):
    if not cols:
        return np.empty((len(idx), 0)), []
    X = np.column_stack([W[c].to_numpy(float)[idx] for c in cols])
    return X, list(cols)


def run_arm(arm_module, universe, folds, *, target_col: str = TARGET_COL_REAL,
            cluster_col: str = CLUSTER_COL, season_col: str = "season",
            p27_fold_policy: str = "SEASON_BLOCK",
            prohibited_basis=None, input_paths: dict | None = None,
            out_path=None, env=None, run_git: bool = False) -> dict:
    """Execute one arm-module instance (one arm x one enumeration element) end-to-end.

    `folds`: list of {"fold_id", "train_idx", "test_idx"} with positional indices into
    `universe`. `prohibited_basis`: a postgame_surrogate_guard.ProhibitedBasis aligned to
    `universe.index` (P38 builds it with realised_duration_basis; tests build a synthetic one).
    """
    fold_ids = [f["fold_id"] for f in folds]

    # 1 -- blinding, fail closed before anything else
    blind = blinding.assert_not_real_frame(
        universe, cluster_col, fold_ids=fold_ids,
        artifact_paths=list((input_paths or {}).values()), env=env)

    # 2 -- frozen guard byte pins
    pins = gh.verify_guard_pins()

    # 3 -- module conformance (declared_family / recalibration / intercept table / hooks)
    conformance = ri.validate_arm_module(arm_module)

    # 4 -- P26 wrapper at fit initialisation, BEFORE P25 (P35 call-site pin)
    p26 = gh.p26_check(arm_module.p26_k0_record())

    # 5 -- P23 franchise-continuity receipt enforcement (card-conditional)
    p23 = gh.p23_check(requires_franchise_continuity=bool(arm_module.requires_franchise_continuity()),
                       receipts=arm_module.p23_receipts())

    deact = list(getattr(arm_module, "structurally_deactivated_folds", lambda: [])())

    guard_records = {"p26": p26, "p23": p23, "p22_per_fold": {}, "p25_per_fold": {}}
    fold_results = []
    bundles = {}
    W_final = None
    arm_cols_ref = null_cols_ref = None

    all_folds = list(folds) + [{
        "fold_id": FINAL_FOLD_ID,
        "train_idx": np.arange(len(universe)),
        "test_idx": np.empty(0, int)}]

    for fold in all_folds:
        fid = str(fold["fold_id"])
        bundle = arm_module.build_design(fold, universe)
        bval = ri.validate_design_bundle(bundle, universe,
                                         bool(arm_module.uses_global_intercept()), fid)
        arm_cols = list(bundle["treatment_cols"]) + list(bundle["nuisance_cols"])
        k0 = bundle["k0_matched_design"]
        null_cols = list(k0["treatment_cols"]) + list(k0["nuisance_cols"])
        if arm_cols_ref is None:
            arm_cols_ref, null_cols_ref = arm_cols, null_cols
        elif arm_cols != arm_cols_ref or null_cols != null_cols_ref:
            raise RunnerRefusal(f"design column names drift across folds at {fid}: "
                                f"{arm_cols} vs {arm_cols_ref}")
        W = _materialise(universe, bundle)
        bundles[fid] = {"bundle": bundle, "W": W, "validation": bval,
                        "arm_cols": arm_cols, "null_cols": null_cols}

        # P22 on the complete design (provenance + prohibited-quantity battery). The explicit
        # intercept column is a constructed constant with no provenance to declare and is
        # excluded from the audited name list; everything else must carry a LagSpec.
        audit_names = [c for c in dict.fromkeys(arm_cols + null_cols) if c != INTERCEPT_COL]
        guard_records["p22_per_fold"][fid] = gh.p22_check(
            W, audit_names, prohibited_basis=prohibited_basis,
            lag_specs=arm_module.lag_specs(), lag_sources=arm_module.lag_sources())

        # P25 on the fold's TRAINING design [offset | nuisance | candidate]
        tr = np.asarray(fold["train_idx"], int)
        W_tr = W.iloc[tr].reset_index(drop=True)
        guard_records["p25_per_fold"][fid] = gh.p25_check(
            W_tr,
            candidate_features=[c for c in bundle["treatment_cols"] if c != INTERCEPT_COL],
            nuisance_features=[c for c in bundle["nuisance_cols"] if c != INTERCEPT_COL],
            preregistered_contrasts=arm_module.preregistered_contrasts(),
            prereg_digest_expected=arm_module.prereg_digest_expected())

        if fid == FINAL_FOLD_ID:
            W_final = W

    # 6 -- P27 once, on the final assembled frame (audits its own folds internally)
    rule = arm_module.p27_rule()
    rule_kwargs, prereg_kwargs = (rule if rule is not None else (None, None))
    final_bundle = bundles[FINAL_FOLD_ID]["bundle"]
    guard_records["p27"] = gh.p27_check(
        W_final,
        candidate_features=[c for c in final_bundle["treatment_cols"] if c != INTERCEPT_COL],
        nuisance_terms=[c for c in final_bundle["nuisance_cols"] if c != INTERCEPT_COL],
        cluster_col=cluster_col, season_col=season_col, fold_policy=p27_fold_policy,
        null_features=[c for c in final_bundle["k0_matched_design"]["treatment_cols"]
                       if c != INTERCEPT_COL],
        null_nuisance=[c for c in final_bundle["k0_matched_design"]["nuisance_cols"]
                       if c != INTERCEPT_COL],
        rule_kwargs=rule_kwargs, prereg_kwargs=prereg_kwargs,
        arm_id=arm_module.arm_id)

    # 7 -- fits and paired inference, per real fold
    evaluable_folds = []

    for fold in folds:
        fid = str(fold["fold_id"])
        entry = {"fold_id": fid}
        if fid in deact:
            entry["status"] = "STRUCTURALLY_DEACTIVATED"
            entry["basis"] = "card-pinned structural deactivation, arm AND null identically"
            fold_results.append(entry)
            continue
        binfo = bundles[fid]
        W, arm_cols, null_cols = binfo["W"], binfo["arm_cols"], binfo["null_cols"]
        tr = np.asarray(fold["train_idx"], int)
        te = np.asarray(fold["test_idx"], int)
        y = W[target_col].to_numpy(float)
        off = W[OFFSET_COL].to_numpy(float)
        cl = W[cluster_col].to_numpy()

        Xa_tr, _ = _design_matrix(W, arm_cols, tr)
        Xn_tr, _ = _design_matrix(W, null_cols, tr)
        fit_arm = qp.fit(Xa_tr, y[tr], off[tr], column_names=tuple(arm_cols))
        fit_null = qp.fit(Xn_tr, y[tr], off[tr], column_names=tuple(null_cols))
        entry["point_fits"] = {"arm": fit_arm.as_record(), "null": fit_null.as_record()}

        if not (fit_arm.converged and fit_null.converged):
            # K7: point-fit non-convergence of EITHER member -> arm/fold UNEVALUABLE, symmetric
            entry["status"] = "UNEVALUABLE"
            entry["basis"] = ("K7 estimator_symmetry_rules.point_fit_nonconvergence: IRLS cap "
                              "or numerical failure in a point fit of arm or null")
            fold_results.append(entry)
            continue

        Xa_te, _ = _design_matrix(W, arm_cols, te)
        Xn_te, _ = _design_matrix(W, null_cols, te)
        mu_arm = qp.predict_mu(Xa_te, fit_arm.beta, off[te])
        mu_null = qp.predict_mu(Xn_te, fit_null.beta, off[te])
        err_arm = np.abs(y[te] - mu_arm)
        err_null = np.abs(y[te] - mu_null)

        deltas = cb.paired_delta_mae_draws(fid, err_arm, err_null, cl[te],
                                           n_draws=B_TEST_BOOTSTRAP)
        entry["test"] = {
            "n_rows": int(te.size), "n_clusters": int(len(np.unique(cl[te]))),
            "mae_arm": float(np.mean(err_arm)), "mae_null": float(np.mean(err_null)),
            "delta_mae": float(np.mean(err_null) - np.mean(err_arm)),
            "n_draws": int(B_TEST_BOOTSTRAP),
            "p_two_sided": cb.two_sided_bootstrap_p(deltas),
            "delta_draw_mean": float(np.mean(deltas)),
        }

        entry["train_refit"] = cb.train_refit_bootstrap(
            fid, X_arm=np.column_stack([W[c].to_numpy(float) for c in arm_cols])[tr]
            if arm_cols else np.empty((tr.size, 0)),
            arm_cols=arm_cols,
            X_null=np.column_stack([W[c].to_numpy(float) for c in null_cols])[tr]
            if null_cols else np.empty((tr.size, 0)),
            null_cols=null_cols,
            y=y[tr], offset=off[tr], cluster_ids=cl[tr],
            indicator_cols=binfo["bundle"]["indicator_cols"],
            n_draws=B_TRAIN_REFIT)

        entry["k0_flat"] = kf.fit_k0_flat(y[tr], off[tr], y[te], off[te])
        entry["status"] = "EVALUABLE"
        entry["_pool"] = (err_arm, err_null, cl[te])   # stripped before the receipt
        evaluable_folds.append(fid)
        fold_results.append(entry)

    # 8 -- pooled delta_MAE over evaluable folds (equal per-row weight); pooled draw b combines
    #      each evaluable fold's OWN seeded draw b (stratified by fold, paired across arms)
    results = {"evaluable_folds": evaluable_folds,
               "structurally_deactivated_folds": deact, "pooled": None}
    ev = [e for e in fold_results if e.get("status") == "EVALUABLE"]
    if ev:
        sums_a = np.zeros(B_TEST_BOOTSTRAP)
        sums_n = np.zeros(B_TEST_BOOTSTRAP)
        counts = np.zeros(B_TEST_BOOTSTRAP)
        for e in ev:
            err_arm, err_null, cl_te = e["_pool"]
            _, rows = cb.cluster_row_map(cl_te)
            for b in range(B_TEST_BOOTSTRAP):
                idx = cb.test_bootstrap_draw_indices(e["fold_id"], b, rows)
                sums_a[b] += float(np.sum(err_arm[idx]))
                sums_n[b] += float(np.sum(err_null[idx]))
                counts[b] += idx.size
        ea = np.concatenate([e["_pool"][0] for e in ev])
        en = np.concatenate([e["_pool"][1] for e in ev])
        pooled_deltas = (sums_n - sums_a) / counts
        results["pooled"] = {
            "n_rows": int(ea.size),
            "mae_arm": float(np.mean(ea)), "mae_null": float(np.mean(en)),
            "delta_mae": float(np.mean(en) - np.mean(ea)),
            "n_draws": int(B_TEST_BOOTSTRAP),
            "p_two_sided": cb.two_sided_bootstrap_p(pooled_deltas)}
    for e in fold_results:
        e.pop("_deltas", None)
        e.pop("_pool", None)

    # 9 -- receipt (I13 conventions)
    manifest = sm.build_manifest([str(f["fold_id"]) for f in folds if str(f["fold_id"])
                                  not in deact], B_TEST_BOOTSTRAP, B_TRAIN_REFIT)
    rec = receipts.build_receipt(
        arm_id=arm_module.arm_id, element_id=arm_module.element_id(),
        enumeration_element=arm_module.enumeration_element(),
        declared_family=DECLARED_FAMILY_ALL_FITTED_ARMS,
        blinding=blind, guard_pins=pins,
        guard_records={**guard_records, "module_conformance": conformance,
                       "design_bundle_validation": {fid: b["validation"]
                                                    for fid, b in bundles.items()}},
        seed_manifest=manifest, folds=fold_results, results=results,
        input_paths=input_paths, run_git=run_git)
    if out_path is not None:
        rec["receipt_file_sha256"] = receipts.write_receipt(rec, out_path)
    return rec
