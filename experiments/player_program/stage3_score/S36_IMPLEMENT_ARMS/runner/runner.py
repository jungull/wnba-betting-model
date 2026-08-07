#!/usr/bin/env python3
"""runner.py -- the shared runner: one entry point, eleven arms, seventeen elements.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

WHAT THE RUNNER GUARANTEES, in the order it enforces them:

  1. O2 first          -- `universe.build_universe()` refuses to exist before the pre-build
                          game_id digest receipt does, so no design matrix can precede it.
  2. Layer-A parity    -- every design pair goes through `runner_interface.validate_design`,
                          which reconstructs the K0 from the arm and refuses any pair that is not
                          arm-minus-treatment.
  3. Blinding at FIT   -- `blinding.assert_may_fit` refuses real-fold structure without the S38
                          flag. Building is authorised; fitting is not, and the two boundaries are
                          separate functions so the distinction cannot blur.
  4. Paired draws      -- the bootstrap index for draw b depends only on (master_seed, fold_id,
                          purpose, b), so arm and null are paired by derivation.
  5. Symmetric NA      -- a failed refit or a constant indicator on either side voids the draw for
                          BOTH.
  6. Obligations stamped -- every receipt carries the C1 alpha disclosure; SC06's era table and
                          SC11's cross-estimand number cannot be emitted without their labels.

`run_element` is written and tested, but at S36 it can only run against synthetic data. That is
the point, not a limitation: S35 says in terms that this freeze does NOT authorise fitting.
"""
from __future__ import annotations

import importlib.util
import json
import platform
import sys
from pathlib import Path

import numpy as np

import blinding
import cluster_bootstrap as CB
import runner_constants as K
import seed_manifest
from canon import canonical_json_sha256, sha256_file
from estimators import (EstimationFailure, fit_logit_irls, fit_ols)
from obligations import stamp_program_alpha, verify_obligation_text
from runner_interface import validate_design, validate_module

ARMS_DIR = K.NODE_DIR / "arms"
ARM_MODULE_FILES = ("sc01_opp_adj_interacting.py", "sc02_a07_score_transient.py",
                    "sc03_season_carryover_prior.py", "sc04_hca_league_drift.py",
                    "sc05_hca_team_offsets.py", "sc06_sched_fatigue_diff.py",
                    "sc08_sigma_margin_map.py", "sc09_fav_gap_compression.py",
                    "sc10_form_trend.py", "sc11_league_total_drift.py",
                    "sc12_robust_input_winsor.py")


def load_modules() -> dict:
    """Import the eleven arm modules and validate each against the frozen contract."""
    sys.path.insert(0, str(ARMS_DIR))
    sys.path.insert(0, str(K.NODE_DIR / "runner"))
    mods = {}
    for fname in ARM_MODULE_FILES:
        path = ARMS_DIR / fname
        if not path.exists():
            raise FileNotFoundError(f"arm module missing: {path}")
        spec = importlib.util.spec_from_file_location(path.stem, path)
        m = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = m
        spec.loader.exec_module(m)
        validate_module(m)
        mods[m.ARM_ID] = m
    missing = set(K.ARM_IDS) - set(mods)
    if missing:
        raise RuntimeError(f"retained arms with no module: {sorted(missing)}")
    extra = set(mods) - set(K.ARM_IDS)
    if extra:
        raise RuntimeError(f"modules for non-retained arms: {sorted(extra)} "
                           f"(SC07 was WITHDRAWN by measurement and must not be implemented)")
    return mods


def all_elements(mods: dict) -> list:
    out = []
    for arm_id in K.ARM_IDS:
        out.extend(mods[arm_id].ELEMENTS)
    return out


# ------------------------------------------------------------------------------------------
# Building (AUTHORISED on the real universe)
# ------------------------------------------------------------------------------------------
def build_designs(universe, mods: dict, *, fold_ids=K.FOLD_IDS, skip=()) -> dict:
    """Materialise every element's arm/K0 design pair on every fold and validate parity.

    No fit, no metric, no comparison. Elements in `skip` are recorded with their reason rather
    than silently omitted -- SC09 is the only member, because its feature is a transform of a
    FITTED K0 and fitting is not authorised here."""
    blinding.assert_may_build()
    n = len(universe.games)
    out = {"schema": "s36_design_build/1", "n_clusters": n,
           "game_id_digest": universe.game_id_digest, "elements": {}, "skipped": {}}
    for spec in all_elements(mods):
        if spec.element_id in skip or spec.arm_id in skip:
            out["skipped"][spec.element_id] = skip[spec.arm_id] if isinstance(skip, dict) else \
                "declared skip"
            continue
        cache: dict = {}
        per_fold = {}
        # Column NAME sets must be identical across folds; values may vary through train-only
        # constants. The ONLY admissible exception is a fold whose card-declared structural
        # deactivation drops a term, and then the fold's set must be a strict SUBSET of the
        # active set -- never a different set, which would be a silently different design.
        active_names: tuple | None = None
        deact_names: dict[str, tuple] = {}
        for fid in fold_ids:
            fold = universe.fold(fid)
            dp = spec.build(universe, fold, cache)
            per_fold[fid] = validate_design(spec, dp, n)
            names = tuple(sorted(set(dp.arm_cols)))
            declared_deact = (fid in spec.structurally_deactivated_folds
                              or not per_fold[fid]["treatment_cols"]
                              or dp.fold_constants.get("era_terms_active") is False)
            if declared_deact:
                deact_names[fid] = names
                continue
            if active_names is None:
                active_names = names
            elif names != active_names:
                raise RuntimeError(
                    f"{spec.element_id}: column NAME set drifted across folds ({active_names} -> "
                    f"{names}); values may vary through train-only constants, names may not")
        for fid, names in deact_names.items():
            if active_names is not None and not set(names) < set(active_names):
                raise RuntimeError(
                    f"{spec.element_id}/{fid}: declared deactivation must yield a strict SUBSET "
                    f"of the active design ({names} vs {active_names})")
        out["elements"][spec.element_id] = {
            "arm_id": spec.arm_id, "estimand": spec.estimand,
            "primary_metric": spec.primary_metric, "arm_kind": spec.arm_kind,
            "family_primary": spec.family_primary, "card_sha256": spec.card_sha256,
            "kill_conditions": list(spec.kill_conditions),
            "mandatory_receipts": list(spec.mandatory_receipts),
            "structurally_deactivated_folds": list(spec.structurally_deactivated_folds),
            "sign_pin": spec.sign_pin, "notes": list(spec.notes),
            "per_fold": per_fold}
    return stamp_program_alpha(out)


# ------------------------------------------------------------------------------------------
# Fitting (NOT authorised on the real universe -- synthetic / S38 only)
# ------------------------------------------------------------------------------------------
def _fit_side(estimand: str, X: np.ndarray, y: np.ndarray, cols):
    if estimand == "E3_HOME_WIN_PROB":
        return fit_logit_irls(X, y, cols)
    return fit_ols(X, y, cols)


def _predict(estimand: str, fit, X: np.ndarray) -> np.ndarray:
    eta = X @ fit.coef
    if estimand == "E3_HOME_WIN_PROB":
        p = 1.0 / (1.0 + np.exp(-eta))
        return np.clip(p, *K.E3_P_CLIP)
    return eta


def _metric(estimand: str, y: np.ndarray, pred: np.ndarray) -> float:
    """MAE for E1/E2; Brier on the raw (clipped) model probability for E3. The metric is a
    property of the estimand, never of the arm."""
    if estimand == "E3_HOME_WIN_PROB":
        return float(np.mean((pred - y) ** 2))
    return float(np.mean(np.abs(pred - y)))


def run_element(universe, spec, *, fold_ids=K.FOLD_IDS, env=None, b_test=None,
                b_train=None, cache=None) -> dict:
    """Fit one element and its K0 across folds. REFUSES real folds without the S38 flag."""
    blind = blinding.assert_may_fit(
        n_rows=len(universe.team_rows), n_clusters=len(universe.games),
        fold_ids=list(fold_ids), env=env)

    cache = {} if cache is None else cache
    b_test = K.B_TEST if b_test is None else int(b_test)
    b_train = K.B_TRAIN_REFIT if b_train is None else int(b_train)
    y = universe.games[spec.estimand].to_numpy(dtype=float)
    n = len(y)

    per_fold = {}
    for fid in fold_ids:
        fold = universe.fold(fid) if fid in K.FOLDS else cache["folds"][fid]
        dp = spec.build(universe, fold, cache)
        parity = validate_design(spec, dp, n)
        Xa, Xk = dp.matrix(dp.arm_cols), dp.matrix(dp.k0_cols)
        tr, te = fold["train_idx"], fold["test_idx"]
        try:
            fa = _fit_side(spec.estimand, Xa[tr], y[tr], dp.arm_cols)
            fk = _fit_side(spec.estimand, Xk[tr], y[tr], dp.k0_cols)
        except EstimationFailure as e:
            per_fold[fid] = {"unevaluable": True, "reason": str(e), "symmetric": True,
                             "parity": parity}
            continue

        pa, pk = _predict(spec.estimand, fa, Xa[te]), _predict(spec.estimand, fk, Xk[te])
        # PAIRED bootstrap deltas. This is the ONLY place a comparison number exists, and it is
        # unreachable on real folds without the S38 flag (see assert_may_fit above).
        deltas = np.empty(b_test)
        for b in range(b_test):
            idx = CB.draw_cluster_indices(np.arange(len(te)), K.SEED_PURPOSE_TEST, fid, b)
            deltas[b] = _metric(spec.estimand, y[te][idx], pk[idx]) - \
                _metric(spec.estimand, y[te][idx], pa[idx])
        per_fold[fid] = {
            "unevaluable": False, "parity": parity,
            "n_train_clusters": int(len(tr)), "n_test_clusters": int(len(te)),
            "arm_coef": dict(zip(dp.arm_cols, fa.coef.tolist())),
            "k0_coef": dict(zip(dp.k0_cols, fk.coef.tolist())),
            "delta_ci95": CB.percentile_ci(deltas),
            "two_sided_p": CB.two_sided_p(deltas),
            "b_test": b_test, "b_train_refit": b_train,
            "deactivated": dp.deactivated, "fold_constants": dp.fold_constants}

    return stamp_program_alpha({
        "schema": "s36_element_run/1", "element_id": spec.element_id, "arm_id": spec.arm_id,
        "estimand": spec.estimand, "primary_metric": spec.primary_metric,
        "arm_kind": spec.arm_kind, "card_sha256": spec.card_sha256,
        "blinding": blind, "seed_manifest": seed_manifest.build_manifest(
            list(fold_ids), b_test, b_train),
        "bootstrap_pins": CB.BOOTSTRAP_PINS, "per_fold": per_fold,
        "kill_conditions": list(spec.kill_conditions),
        "mandatory_receipts": list(spec.mandatory_receipts)})


# ------------------------------------------------------------------------------------------
# Environment / code-state receipt
# ------------------------------------------------------------------------------------------
def code_state() -> dict:
    files = {}
    for p in sorted(list((K.NODE_DIR / "runner").glob("*.py"))
                    + list((K.NODE_DIR / "arms").glob("*.py"))
                    + list((K.NODE_DIR / "prebuild").glob("*.py"))
                    + list((K.NODE_DIR / "tests").glob("*.py"))):
        files[str(p.relative_to(K.NODE_DIR)).replace("\\", "/")] = sha256_file(p)
    import numpy
    import pandas
    return {"schema": "s36_code_state/1", "source_sha256": files,
            "environment": {"python": platform.python_version(), "numpy": numpy.__version__,
                            "pandas": pandas.__version__, "platform": platform.platform()},
            "git_not_run": ("GRAPH_POLICY: agents write files; the coordinator makes the "
                            "task-scoped commit")}


def obligation_state() -> dict:
    return verify_obligation_text()


def manifest_digest(obj) -> str:
    return canonical_json_sha256(json.loads(json.dumps(obj, default=str)))
