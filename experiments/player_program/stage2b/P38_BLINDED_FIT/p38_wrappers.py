#!/usr/bin/env python3
"""p38_wrappers.py -- P38 executor task-specific call-site wrappers (D039 EXEC-M1..M7).

Every object here is a CALL-SITE wrapper in the sense of standing rule 3 and the D039
executor mandates: no frozen file (guards, runner, arm modules, registry) is edited; the
wrappers interpose at the P38 invocation only, in-process, and every interposition is
recorded in the per-arm P38 sidecar and in stage2b/P38_BLINDED_FIT/EXECUTION_LOG.md.

Mandate map (P37 SPEC.json proposed_rulings.severity_b_mandate_map, ratified D039):

  EXEC-M1  P27GuardHarnessView + FoldGovernor: honour the P27 guard's PER-FOLD UNEVALUABLE
           verdicts symmetrically for arm and null, continue with the remaining folds, and
           implement A07's ">= 2 folds" retirement arithmetic. The runner's own escalation
           (guard_harness.p27_check raises on overall FAIL, runner.run_arm aborts the arm)
           is R-F1's fail-closed divergence; this view tolerates a FAIL if and ONLY if every
           offending fold is already excluded from fitting by the P38 fold-governor record,
           and re-raises otherwise. The frozen guard and harness bytes are untouched; the
           interposition is a rebinding of the loaded runner module's `gh` attribute for the
           duration of one run_arm call.
  EXEC-M4  history_bound_a09 / history_bound_a10: constructor-bind the 2,990-row contract
           schedule archive as the n_t/d_t (and c_t) clock, exactly as A11/A12/A13 bind
           theirs, using ONLY the arm's own frozen pure functions (align_n_t_d_t_by_key /
           align_n_t_d_t_c_t_by_key / kappa_contrast). The 2,982-row universe is never used
           as the clock (the barred clock, P35 n_clock_pin).
  EXEC-M5  a03_tier_records: invoke A03's own tier_symmetry_check per fold, arm and null
           identically (the check conditions only on training-row depth values and cluster
           ids, so one evaluation governs both members; exclusion is applied through the
           symmetric fold-governor, which deactivates a fold for BOTH members).
  EXEC-M1/A07  a07_near_affinity_records: the card's S7 near-affinity trigger (R2 >=
           0.998001 OR |spearman| >= 0.999 of exp(-n_i/5) vs pace_evidence_depth on the
           fold's TRAINING rows), evaluated at the call site because the frozen module
           declares the rule but exposes no per-fold callable; ">= 2 unevaluable folds
           retires the hypothesis" is applied by the driver.

Nothing in this file reads, prints or returns any comparative performance number.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FINAL_FOLD_ID = "FINAL_ASSEMBLED_DESIGN"


# --------------------------------------------------------------------------------- EXEC-M1 --
class P27GuardHarnessView:
    """Delegating view of the guard_harness module for ONE run_arm invocation (EXEC-M1).

    Delegates every attribute to the real guard_harness module. p27_check invokes the real
    wrapper; when the frozen guard returns overall FAIL (which the frozen harness escalates
    to a whole-arm refusal, finding R-F1), this view honours the guard's own per-fold
    verdicts instead, provided EVERY offending fold is already in the P38 deactivation set
    (so it enters neither member's fits) and the failure basis is strictly fold-local:
    games-not-split must hold, and the FINAL_ASSEMBLED_DESIGN must itself be estimable and
    parameter-reconciled. Any other failure basis re-raises -- fail closed.
    """

    def __init__(self, real_gh, allowed_excluded_folds):
        self._real = real_gh
        self._allowed = set(str(f) for f in allowed_excluded_folds)
        self.tolerated_record = None
        self.tolerance_basis = None

    def __getattr__(self, name):
        return getattr(self._real, name)

    def p27_check(self, *args, **kwargs):
        try:
            return self._real.p27_check(*args, **kwargs)
        except Exception as e:  # GuardHarnessFailure carries .record
            rec = getattr(e, "record", None)
            if not isinstance(rec, dict) or rec.get("schema") != \
                    "s7_fold_local_estimability_receipt/1":
                raise
            offending = set(rec.get("folds_marked_unevaluable", []) or [])
            offending |= set(rec.get("folds_with_unreconciled_parameter_counts", []) or [])
            recon = rec.get("pooled_vs_fold_reconciliation", {}) or {}
            ungoverned = set(recon.get("affected_folds_without_an_explicit_verdict", []) or [])
            split_ok = bool((rec.get("games_not_split_check") or {}).get("ok"))
            final_bad = (FINAL_FOLD_ID in offending) or (FINAL_FOLD_ID in ungoverned)
            fold_level = (offending | ungoverned) - {FINAL_FOLD_ID}
            if split_ok and not final_bad and fold_level and \
                    fold_level.issubset(self._allowed):
                self.tolerated_record = rec
                self.tolerance_basis = {
                    "mandate": "EXEC-M1 (R-F1)",
                    "guard_overall": rec.get("overall"),
                    "offending_folds": sorted(fold_level),
                    "all_offending_folds_excluded_from_fits": True,
                    "final_design_estimable": True,
                    "games_not_split": True,
                    "action": ("per-fold UNEVALUABLE verdicts honoured symmetrically for "
                               "arm and null via the P38 fold governor; remaining folds "
                               "proceed; the frozen guard record is carried unmodified in "
                               "the receipt"),
                }
                return rec
            raise


class FoldGovernor:
    """Symmetric per-fold deactivation wrapper around one arm-module instance (EXEC-M1).

    Delegates every hook to the wrapped module. structurally_deactivated_folds() returns the
    union of the module's own card-pinned deactivations and the P38 per-fold exclusions
    (P27 UNEVALUABLE verdicts, preregistered-rule collapses, A03 tier symmetry, A07 near-
    affinity). The runner's deactivation mechanism is the ONLY exclusion path used: it skips
    the fold for arm AND null identically, excludes it from the pooled delta and from every
    kill's evaluable-fold set, and excludes its seed streams from the manifest.

    LABELLING CAVEAT (recorded, not hidden): the frozen runner marks every deactivated fold
    "STRUCTURALLY_DEACTIVATED / card-pinned structural deactivation". For folds excluded by
    the P38 governor the true basis lives in the per-arm sidecar's fold_exclusions map and
    in EXECUTION_LOG.md; the receipt string is the frozen runner's own wording and is not
    edited.
    """

    def __init__(self, inner, extra_deactivated: dict, build_design_override=None):
        # extra_deactivated: {fold_id: basis_string}
        self._inner = inner
        self._extra = {str(k): str(v) for k, v in (extra_deactivated or {}).items()}
        self._bd = build_design_override

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def structurally_deactivated_folds(self):
        hook = getattr(self._inner, "structurally_deactivated_folds", None)
        base = list(hook()) if callable(hook) else []
        return sorted(set(base) | set(self._extra))

    def build_design(self, fold, universe):
        if self._bd is not None:
            return self._bd(fold, universe)
        return self._inner.build_design(fold, universe)

    @property
    def p38_fold_exclusions(self):
        return dict(self._extra)


# --------------------------------------------------------------------------------- EXEC-M4 --
def history_bound_a09(a09_module, inner, history: pd.DataFrame):
    """build_design override for one A09 instance: the arm's OWN frozen pure functions run
    with the contract-schedule archive as the clock (n_clock_pin), the universe supplying
    target keys only. Column names, design structure and the null are byte-identical to the
    frozen module's return."""
    def build_design(fold, universe):
        n_t, d_t = a09_module.align_n_t_d_t_by_key(
            history, universe, key_cols=("team_id", "game_id"))
        contrast = a09_module.kappa_contrast(n_t, d_t, inner.kappa)
        return {
            "treatment_cols": [a09_module.TREATMENT_COL],
            "nuisance_cols": [a09_module.NUISANCE_COL],
            "k0_matched_design": {"treatment_cols": [],
                                  "nuisance_cols": [a09_module.NUISANCE_COL],
                                  "comparison": "term_removal"},
            "indicator_cols": [],
            "columns": {a09_module.NUISANCE_COL: d_t, a09_module.TREATMENT_COL: contrast},
        }
    return build_design


def history_bound_a10(a10_module, inner, history: pd.DataFrame):
    """As history_bound_a09, for A10 (adds the EWMA recency contrast c_t)."""
    def build_design(fold, universe):
        n_t, d_t, c_t = a10_module.align_n_t_d_t_c_t_by_key(
            history, universe, inner.lam, key_cols=("team_id", "game_id"))
        return {
            "treatment_cols": [a10_module.TREATMENT_COL],
            "nuisance_cols": [a10_module.NUISANCE_COL],
            "k0_matched_design": {"treatment_cols": [],
                                  "nuisance_cols": [a10_module.NUISANCE_COL],
                                  "comparison": "term_removal"},
            "indicator_cols": [],
            "columns": {a10_module.NUISANCE_COL: d_t, a10_module.TREATMENT_COL: c_t},
        }
    return build_design


def measure_clock_divergence(align_fn, universe: pd.DataFrame, history: pd.DataFrame,
                             key_cols=("team_id", "game_id")) -> dict:
    """Structural (non-performance) measurement: how many universe rows' (n_t, d_t) differ
    between the barred universe-row clock and the pinned contract-schedule clock. Feature
    construction facts only; no target, no error, no metric."""
    u_n, u_d = align_fn(universe, universe, key_cols=key_cols)
    c_n, c_d = align_fn(history, universe, key_cols=key_cols)
    n_diff = int(np.sum(u_n != c_n))
    d_diff = int(np.sum(~np.isclose(u_d, c_d, rtol=0.0, atol=0.0, equal_nan=True)))
    return {"rows_compared": int(len(u_n)),
            "n_t_rows_differing_universe_vs_contract_clock": n_diff,
            "d_t_rows_differing_universe_vs_contract_clock": d_diff}


# --------------------------------------------------------------------------------- EXEC-M5 --
def a03_tier_records(a03_module, universe: pd.DataFrame, folds: list) -> dict:
    """A03 tier_symmetry_check per real fold. The check conditions only on training-row
    depth and cluster ids -- identical inputs for arm and null -- so one evaluation per fold
    governs both members; symmetry of APPLICATION is delivered by the fold governor, which
    deactivates a triggered fold for both members at once."""
    out = {}
    for f in folds:
        rec = a03_module.tier_symmetry_check(universe, f["train_idx"])
        out[str(f["fold_id"])] = rec
    return out


# ---------------------------------------------------------------------------- A07 (EXEC-M1) --
def _spearman_abs(x: np.ndarray, y: np.ndarray) -> float:
    rx = pd.Series(x).rank(method="average").to_numpy(float)
    ry = pd.Series(y).rank(method="average").to_numpy(float)
    if np.std(rx) == 0.0 or np.std(ry) == 0.0:
        return 0.0
    return float(abs(np.corrcoef(rx, ry)[0, 1]))


def _r2_on_intercept_and_x(y: np.ndarray, x: np.ndarray) -> float:
    """R2 of regressing y on [1, x] (the near-affinity R2 of the card's condition check)."""
    X = np.column_stack([np.ones(len(x)), np.asarray(x, float)])
    beta, *_ = np.linalg.lstsq(X, np.asarray(y, float), rcond=None)
    resid = y - X @ beta
    sst = float(np.sum((y - np.mean(y)) ** 2))
    if sst == 0.0:
        return 1.0
    return float(1.0 - float(np.sum(resid ** 2)) / sst)


def a07_near_affinity_records(transient: np.ndarray, depth: np.ndarray,
                              folds: list, r2_threshold: float,
                              spearman_threshold: float) -> dict:
    """The A07 card's S7 near-affinity trigger per fold, training rows only (both columns
    are pre-outcome constructions; nothing here touches the target)."""
    out = {}
    for f in folds:
        tr = np.asarray(f["train_idx"], int)
        t, d = np.asarray(transient, float)[tr], np.asarray(depth, float)[tr]
        r2 = _r2_on_intercept_and_x(t, d)
        sp = _spearman_abs(t, d)
        fired = bool(r2 >= r2_threshold or sp >= spearman_threshold)
        out[str(f["fold_id"])] = {
            "r2_transient_on_depth": r2, "abs_spearman": sp,
            "r2_threshold": r2_threshold, "spearman_threshold": spearman_threshold,
            "trigger_fired": fired,
            "verdict": "UNEVALUABLE_PROSPECTIVELY" if fired else "ESTIMABLE"}
    return out
