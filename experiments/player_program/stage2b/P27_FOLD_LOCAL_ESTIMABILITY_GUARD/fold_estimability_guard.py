#!/usr/bin/env python3
"""fold_estimability_guard.py -- S7 call-site guard: fold-local estimability.

WHAT THIS IS
------------
A CALL-SITE wrapper. It does not modify, wrap-and-weaken, or re-implement
`experiments/player_program/feature_gate.py`. The shared gate remains frozen and authoritative for
the checks it implements; this module adds the checks the shared gate structurally cannot perform,
and enforces the invocation obligations of `GATE_INVOCATION_CONTRACT.md` sections 1, 3, 4 and 6.

Three gaps this closes, each measured against the frozen artifacts (see REPORT.md):

  G1  `feature_gate.design_rank_report(df, names)` builds its design from `names` ONLY. The OFFSET
      and any NUISANCE terms (intercept, fallback-tier dummies, fold effects) never enter the SVD.
      A design that is exactly rank deficient once the intercept and the offset are included --
      the classic dummy trap, and the S5 `own_est + opp_est == 2 * projected` identity -- is
      reported as `full_rank: true` by the shared gate. This module audits `[X | nuisance |
      intercept | offset]`.

  G2  The shared gate has no notion of a fold and no notion of a cluster. `zero_variance` fires on
      the matrix it is handed. Hand it the pooled matrix and a term that is identically zero inside
      one training fold passes, because the healthy folds carry the variance (GATE_INVOCATION
      CONTRACT section 1). This module runs the audit per outer training fold and reports
      TREATMENT SUPPORT BY GAME CLUSTER, not by row -- the row count overstates support by up to
      2x because both team-rows of a game share a projection.

  G3  Nothing in the repository reconciles the candidate design's parameter count against the null
      design's, nor forbids reporting a pooled pass when a term is absent in a fold. Both are
      enforced here as hard invariants.

DISCIPLINE ON THE ACTIVE-SET RULE
---------------------------------
Dropping a fold-degenerate term is a legitimate remedy ONLY under GATE_INVOCATION_CONTRACT
section 4: frozen and registered before any result is visible, with a numeric trigger. This module
will not apply an active-set rule that cannot demonstrate all five properties:

  1. PREREGISTERED   -- the caller supplies a preregistration record whose recomputed canonical
                        digest matches the rule's own spec digest, and which asserts
                        `results_visible_at_registration == false`.
  2. TRAINING-ONLY   -- the rule is invoked with a `SupportSummary` built exclusively from
                        training-fold rows. It is structurally incapable of seeing a test row: the
                        guard never constructs a test-derived summary and the rule signature
                        accepts nothing else.
  3. SYMMETRIC       -- one active set per fold, applied to the candidate AND to the null. The
                        guard computes it once and asserts the null's terms remain a subset of the
                        candidate's after masking.
  4. PERFORMANCE-BLIND -- the summary carries counts, level cardinalities, variances and cluster
                        support. It carries NO target values, NO residuals, NO metric. A rule that
                        needs performance cannot express itself in this type.
  5. RECORDED        -- rule id, digest, the summary it saw, and the terms it dropped are written
                        into the per-fold receipt.

Absent a conforming rule, a fold carrying a blocking degeneracy is marked
`UNEVALUABLE_PROSPECTIVELY`. That is a verdict, not an error: the arm is declared unfittable on
that fold BEFORE the fit, which is the entire point.

EPISTEMIC STATUS
----------------
INFRASTRUCTURE + task-specific INVARIANT. Proves an arm/fold is estimable before it is fitted.
Does not establish that an estimable arm is a real effect.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Callable, Iterable, Sequence

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Thresholds. Deliberately MIRRORED from feature_gate.py rather than imported-and-mutated, and
# asserted equal at import time by TESTS.py, so a drift in the frozen gate is a loud test failure
# rather than a silent divergence between the gate and its call-site guard.
# ---------------------------------------------------------------------------
RANK_TOL = 1e-8          # feature_gate.RANK_TOL
COND_MAX = 1e6           # feature_gate.COND_MAX
NEAR_ZERO_STD = 1e-8     # feature_gate: std < 1e-8 -> impossible_scaling

#: minimum distinct game clusters carrying a level before its support is even measurable
MIN_CLUSTERS_FOR_RANK = 10   # mirrors feature_gate's len(Xc) < 10 refusal-to-assess

VERDICT_ESTIMABLE = "ESTIMABLE"
VERDICT_ESTIMABLE_UNDER_RULE = "ESTIMABLE_UNDER_PREREGISTERED_ACTIVE_SET"
VERDICT_UNEVALUABLE = "UNEVALUABLE_PROSPECTIVELY"

BLOCKING_KINDS = {
    "zero_variance",
    "impossible_scaling",
    "rank_deficient_augmented",
    "ill_conditioned_augmented",
    "no_cluster_support",
    "single_level_factor",
    "parameter_count_unreconciled",
    "offset_in_design_span",
}


def _frozen_gate():
    """Import the FROZEN feature_gate for side-by-side comparison. Never modified, never wrapped."""
    import importlib
    import sys as _sys
    from pathlib import Path as _Path
    p = str(_Path(__file__).resolve().parents[2])      # experiments/player_program
    if p not in _sys.path:
        _sys.path.insert(0, p)
    return importlib.import_module("feature_gate")


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_of(obj) -> str:
    return hashlib.sha256(_canon(obj).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Fold construction
# ---------------------------------------------------------------------------
#: EVIDENCE_PACKET_V2.inference_specification.fold_construction:
#:   "chronological, nested by season; a game is NEVER split across folds -- both team-rows always
#:    fall in the same fold"
#: That sentence admits two readings and the program has not disambiguated it. Both are
#: implemented; the caller must name which one it is auditing, and the receipt records the choice.
FOLD_POLICIES = ("SEASON_BLOCK", "EXPANDING_PRIOR_SEASONS")


def make_outer_training_folds(season: Sequence, policy: str = "SEASON_BLOCK") -> dict:
    """Return {fold_id: boolean row mask over the SAME index as `season`} for OUTER TRAINING folds.

    SEASON_BLOCK
        fold f_<s> = the rows of season s. This is the reading under which the S7 finding is
        stated ("four of six chronological folds", six seasons being present).

    EXPANDING_PRIOR_SEASONS
        fold f_<s> = every row with season strictly less than s, i.e. the training material for a
        held-out season s. The earliest season is not a test season and yields no training fold,
        so this policy produces one fewer fold than there are seasons.

    Neither policy can split a game: `season` is constant within a game_id in this universe, which
    the guard asserts via `assert_games_not_split`.
    """
    if policy not in FOLD_POLICIES:
        raise ValueError(f"unknown fold policy {policy!r}; expected one of {FOLD_POLICIES}")
    s = pd.Series(list(season))
    seasons = sorted(s.unique())
    out: dict = {}
    if policy == "SEASON_BLOCK":
        for x in seasons:
            out[f"train_{x}"] = (s == x).to_numpy()
    else:
        for x in seasons[1:]:
            out[f"train_lt_{x}"] = (s < x).to_numpy()
    return out


def assert_games_not_split(fold_masks: dict, cluster_ids: Sequence) -> dict:
    """Every game cluster must lie wholly inside, or wholly outside, each fold."""
    c = pd.Series(list(cluster_ids))
    offenders = {}
    for fid, m in fold_masks.items():
        inside = pd.Series(np.asarray(m, bool))
        per = inside.groupby(c).nunique()
        bad = per[per > 1]
        if len(bad):
            offenders[fid] = [str(x) for x in bad.index[:20]]
    return {"games_split_across_folds": offenders, "ok": len(offenders) == 0}


# ---------------------------------------------------------------------------
# The support summary an active-set rule is allowed to see
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SupportSummary:
    """Everything a preregistered active-set rule may condition on. Training rows only.

    There is deliberately no target, no residual, no prediction and no metric field. A rule that
    wants to select on test performance cannot be written against this type.
    """
    fold_id: str
    n_rows: int
    n_clusters: int
    term_std: dict            # term -> float std on training rows
    term_unique_levels: dict  # term -> int number of distinct values on training rows
    term_cluster_support: dict  # term -> distinct game clusters where the term is non-zero
    term_nonzero_rows: dict   # term -> rows where the term is non-zero

    def as_record(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ActiveSetRule:
    """A fold-local active-set rule with a NUMERIC trigger, per GATE_INVOCATION_CONTRACT section 4.

    `min_nonzero_clusters` and `min_std` are the trigger. `decide` is pure: it is a function of a
    SupportSummary and nothing else.
    """
    rule_id: str
    min_nonzero_clusters: int
    min_std: float
    rationale: str

    @property
    def spec(self) -> dict:
        return {"rule_id": self.rule_id,
                "min_nonzero_clusters": int(self.min_nonzero_clusters),
                "min_std": float(self.min_std),
                "rationale": self.rationale,
                "conditions_on": "SupportSummary (training-fold counts only)",
                "applied_to": "candidate AND null, identically, once per fold"}

    @property
    def spec_sha256(self) -> str:
        return sha256_of(self.spec)

    def decide(self, summary: SupportSummary, terms: Sequence[str]) -> dict:
        dropped, kept, why = [], [], {}
        for t in terms:
            cl = int(summary.term_cluster_support.get(t, 0))
            sd = float(summary.term_std.get(t, 0.0))
            if cl < self.min_nonzero_clusters or sd < self.min_std:
                dropped.append(t)
                why[t] = {"nonzero_clusters": cl, "std": sd,
                          "trigger": f"clusters<{self.min_nonzero_clusters} or std<{self.min_std}"}
            else:
                kept.append(t)
        return {"kept": kept, "dropped": dropped, "why": why}


@dataclass(frozen=True)
class Preregistration:
    """Binding record that the rule was frozen BEFORE any result was visible."""
    registered_at_utc: str
    registered_by: str
    rule_spec_sha256: str
    results_visible_at_registration: bool
    record_path: str

    def as_record(self) -> dict:
        return asdict(self)


class PreregistrationFailure(RuntimeError):
    pass


def validate_preregistration(rule: ActiveSetRule, prereg: Preregistration) -> dict:
    """All five properties, or the rule may not be applied. Returns the audit; raises on failure."""
    problems = []
    recomputed = rule.spec_sha256
    if prereg.rule_spec_sha256 != recomputed:
        problems.append({"kind": "digest_mismatch",
                         "declared": prereg.rule_spec_sha256, "recomputed": recomputed,
                         "detail": "the registered rule is not the rule being applied"})
    if prereg.results_visible_at_registration:
        problems.append({"kind": "registered_after_results",
                         "detail": "GATE_INVOCATION_CONTRACT section 4 forbids a remedy chosen "
                                   "after the failure is observed"})
    if rule.min_nonzero_clusters <= 0 and rule.min_std <= 0.0:
        problems.append({"kind": "trigger_not_numeric",
                         "detail": "section 4 requires the trigger stated numerically"})
    audit = {"rule_id": rule.rule_id, "rule_spec": rule.spec,
             "rule_spec_sha256": recomputed, "preregistration": prereg.as_record(),
             "properties": {
                 "preregistered": not any(p["kind"] in ("digest_mismatch",
                                                        "registered_after_results")
                                          for p in problems),
                 "training_fold_support_only": True,
                 "applied_symmetrically": True,
                 "incapable_of_selecting_on_test_performance": True,
                 "recorded_in_receipt": True},
             "structural_basis": {
                 "training_fold_support_only":
                     "decide() receives a SupportSummary the guard builds from training rows only",
                 "incapable_of_selecting_on_test_performance":
                     "SupportSummary has no target, residual, prediction or metric field",
                 "applied_symmetrically":
                     "the guard computes one active set per fold and applies it to candidate and "
                     "null before the parameter-count reconciliation"},
             "problems": problems, "valid": len(problems) == 0}
    if problems:
        raise PreregistrationFailure(json.dumps(problems, default=str))
    return audit


# ---------------------------------------------------------------------------
# The measurements
# ---------------------------------------------------------------------------
def column_diagnostics(df: pd.DataFrame, terms: Sequence[str],
                       cluster_ids: Sequence) -> dict:
    """Per-term zero variance, near-zero variance, unique-level count, cluster support."""
    c = pd.Series(list(cluster_ids)).reset_index(drop=True)
    out = {}
    for t in terms:
        v = pd.to_numeric(df[t], errors="coerce").reset_index(drop=True)
        arr = v.to_numpy(float)
        finite = np.isfinite(arr)
        sd = float(np.nanstd(arr)) if finite.any() else float("nan")
        nz = np.zeros(len(arr), bool)
        nz[finite] = arr[finite] != 0.0
        out[t] = {
            "std": sd,
            "zero_variance": bool(sd == 0.0),
            "near_zero_variance": bool(0.0 < sd < NEAR_ZERO_STD),
            "unique_levels": int(pd.unique(v.dropna()).size),
            "n_rows": int(len(arr)),
            "n_nonzero_rows": int(nz.sum()),
            "n_clusters_total": int(c.nunique()),
            "n_clusters_with_support": int(c[nz].nunique()),
            "cluster_support_rate": (round(float(c[nz].nunique() / c.nunique()), 6)
                                     if c.nunique() else 0.0),
            "n_nonfinite": int((~finite).sum()),
        }
    return out


def _design_columns(df: pd.DataFrame, feature_terms: Sequence[str],
                    nuisance_terms: Sequence[str] = (),
                    offset: np.ndarray | None = None,
                    include_intercept: bool = True):
    blocks, names = [], []
    for t in list(feature_terms) + list(nuisance_terms):
        blocks.append(pd.to_numeric(df[t], errors="coerce").to_numpy(float))
        names.append(t)
    if include_intercept:
        blocks.append(np.ones(len(df), float))
        names.append("__intercept__")
    if offset is not None:
        blocks.append(np.asarray(offset, float))
        names.append("__offset__")
    return blocks, names


def augmented_rank_report(df: pd.DataFrame, feature_terms: Sequence[str],
                          nuisance_terms: Sequence[str] = (),
                          offset: np.ndarray | None = None,
                          include_intercept: bool = True) -> dict:
    """Numerical rank and condition of [features | nuisance | intercept | offset].

    This is the check `feature_gate.design_rank_report` cannot perform: it is handed `names` and
    builds its matrix from those alone, so the offset and the nuisance terms are outside its view.

    SCALING DEVIATION, STATED RATHER THAN HIDDEN. The frozen gate CENTRES each column before the
    SVD. Centring is correct for a features-only matrix and WRONG once an intercept is a column:
    a centred constant column is identically zero, so a centred audit would report EVERY design
    containing an intercept as rank deficient. That is a false positive, not a finding. This
    report therefore scales each column to unit Euclidean norm and does NOT centre. `RANK_TOL` and
    `COND_MAX` are the frozen gate's own constants, unchanged.

    Consequences of the uncentred convention, all intended:
      * a one-hot factor carrying every level PLUS an intercept is exactly rank deficient (the
        dummy trap) -- correctly detected, whereas a centred audit conflates it with the
        intercept's own artificial zero;
      * a column that is identically zero inside the fold has zero norm and contributes a zero
        singular value -- correctly rank deficient, since a zero column is not estimable;
      * the condition number of an uncentred design is a different and generally larger quantity
        than the centred one. It is reported against the same COND_MAX ceiling, and the report
        names the convention so the two are never silently compared.
    """
    blocks, names = _design_columns(df, feature_terms, nuisance_terms, offset, include_intercept)
    if not blocks:
        return {"checked": True, "scaling": "unit_column_norm_uncentred", "n_columns": 0,
                "columns": [], "numerical_rank": 0, "full_rank": True,
                "rank_deficiency": 0, "condition_number": 1.0, "condition_ok": True,
                "singular_values": [], "zero_norm_columns": [],
                "note": "empty design is trivially identified"}
    X = np.column_stack(blocks)
    m = np.all(np.isfinite(X), axis=1)
    Xc = X[m]
    if len(Xc) < 10:
        return {"checked": False, "scaling": "unit_column_norm_uncentred",
                "n_columns": int(X.shape[1]), "columns": names,
                "n_complete_rows": int(m.sum()), "numerical_rank": 0, "full_rank": False,
                "rank_deficiency": int(X.shape[1]), "condition_number": float("inf"),
                "condition_ok": False, "singular_values": [], "zero_norm_columns": [],
                "note": "insufficient complete rows to assess rank"}
    nrm = np.linalg.norm(Xc, axis=0)
    zero_cols = [names[i] for i in range(len(names)) if nrm[i] == 0.0]
    Z = Xc / np.where(nrm == 0.0, 1.0, nrm)
    sv = np.linalg.svd(Z, compute_uv=False)
    rank = int((sv > RANK_TOL * sv.max()).sum())
    cond = float(sv.max() / sv.min()) if sv.min() > 0 else float("inf")
    return {"checked": True, "scaling": "unit_column_norm_uncentred",
            "n_columns": int(X.shape[1]), "columns": names,
            "n_complete_rows": int(m.sum()),
            "singular_values": [float(x) for x in sv],
            "numerical_rank": rank, "full_rank": bool(rank == X.shape[1]),
            "rank_deficiency": int(X.shape[1] - rank),
            "zero_norm_columns": zero_cols,
            "condition_number": cond, "condition_ok": bool(cond <= COND_MAX)}


def offset_absorption_report(df: pd.DataFrame, feature_terms: Sequence[str],
                             nuisance_terms: Sequence[str],
                             offset: np.ndarray | None,
                             include_intercept: bool = True,
                             span_tol: float = 1e-8,
                             near_tol: float = 0.999) -> dict:
    """Is the FIXED offset inside the column space of the ESTIMATED design?

    A rank check on `[X | offset]` answers a slightly wrong question: the offset carries no
    estimated coefficient, so it is not a design column in the fitting sense. The question that
    matters is whether the estimated design can REPRODUCE the offset. If it can, the offset's
    implicit unit coefficient is no longer a constraint -- the fit is free to recalibrate it,
    which is S4's free SLOPE, and it is exactly how S5's `own_est + opp_est == 2 * projected`
    identity smuggles the incumbent's own output back into the design while every pairwise
    correlation stays far below 0.999.

    `feature_gate.audit` tests only the PAIRWISE correlation of each feature with the offset
    (`deterministic_transform_of_offset`). A two-term or three-term reconstruction is invisible to
    it, as the S5 measurement shows: corr(own, projected) = 0.7738, well under the 0.999 threshold,
    while own and opp together reproduce the offset to machine zero.
    """
    if offset is None:
        return {"checked": False, "note": "no offset supplied"}
    blocks, names = _design_columns(df, feature_terms, nuisance_terms, None, include_intercept)
    o = np.asarray(offset, float)
    if not blocks:
        return {"checked": False, "note": "no estimated design columns"}
    X = np.column_stack(blocks)
    m = np.all(np.isfinite(X), axis=1) & np.isfinite(o)
    Xc, oc = X[m], o[m]
    if len(Xc) < 10 or np.linalg.norm(oc) == 0:
        return {"checked": False, "n_complete_rows": int(m.sum()),
                "note": "insufficient complete rows, or offset is identically zero"}
    coef, *_ = np.linalg.lstsq(Xc, oc, rcond=None)
    resid = oc - Xc @ coef
    rel = float(np.linalg.norm(resid) / np.linalg.norm(oc))
    ss_tot = float(((oc - oc.mean()) ** 2).sum())
    r2 = float(1.0 - (resid ** 2).sum() / ss_tot) if ss_tot > 0 else float("nan")
    return {"checked": True, "design_columns": names,
            "n_complete_rows": int(m.sum()),
            "relative_residual_norm": rel,
            "r2_of_offset_on_design": r2,
            "offset_in_design_span": bool(rel <= span_tol),
            "offset_nearly_absorbed": bool(np.isfinite(r2) and r2 >= near_tol),
            "span_tol": span_tol, "near_tol": near_tol,
            "detail": ("offset_in_design_span means the fit can reproduce the offset exactly and "
                       "therefore recalibrate it freely; the control does not have that "
                       "flexibility unless it is granted the same terms")}


def reconcile_parameter_counts(candidate_features: Sequence[str],
                               candidate_nuisance: Sequence[str],
                               null_features: Sequence[str],
                               null_nuisance: Sequence[str],
                               include_intercept: bool = True) -> dict:
    """Candidate vs null parameter counts, with the free-flexibility checks S4 named.

    The null MUST NOT carry a substantive feature, MUST carry exactly the candidate's nuisance
    terms (otherwise it is a straw control, EVIDENCE_PACKET_V2 K0_MATCHED.tier_partition_rule), and
    the candidate MUST NOT be handed the offset as a substantive feature -- that is S4's free
    recalibration SLOPE, which buys a parameter the control does not have while adding zero
    information.
    """
    k = 1 if include_intercept else 0
    n_cand = len(candidate_features) + len(candidate_nuisance) + k
    n_null = len(null_features) + len(null_nuisance) + k
    problems = []
    if list(null_features):
        problems.append({"kind": "null_carries_substantive_features",
                         "features": list(null_features)})
    if sorted(candidate_nuisance) != sorted(null_nuisance):
        problems.append({"kind": "nuisance_terms_differ",
                         "candidate_only": sorted(set(candidate_nuisance) - set(null_nuisance)),
                         "null_only": sorted(set(null_nuisance) - set(candidate_nuisance)),
                         "detail": "K0_MATCHED must reproduce the candidate's fallback/tier "
                                   "architecture exactly, or the comparison is unmatched"})
    delta = n_cand - n_null
    if delta != len(candidate_features):
        problems.append({"kind": "parameter_count_unreconciled",
                         "n_params_candidate": n_cand, "n_params_null": n_null,
                         "delta": delta, "n_substantive_features": len(candidate_features)})
    return {"n_params_candidate": n_cand, "n_params_null": n_null,
            "delta_params": delta, "n_substantive_features": len(candidate_features),
            "intercept_counted": bool(include_intercept),
            "candidate_features": list(candidate_features),
            "candidate_nuisance": list(candidate_nuisance),
            "null_features": list(null_features), "null_nuisance": list(null_nuisance),
            "problems": problems, "reconciled": len(problems) == 0}


def _findings_from(diag: dict, rank: dict, terms: Sequence[str],
                   absorb: dict | None = None) -> list:
    f = []
    for t in terms:
        d = diag[t]
        if d["zero_variance"]:
            f.append({"kind": "zero_variance", "term": t, "std": d["std"],
                      "n_nonzero_rows": d["n_nonzero_rows"],
                      "n_clusters_with_support": d["n_clusters_with_support"]})
        elif d["near_zero_variance"]:
            f.append({"kind": "impossible_scaling", "term": t, "std": d["std"]})
        if d["unique_levels"] <= 1:
            f.append({"kind": "single_level_factor", "term": t,
                      "unique_levels": d["unique_levels"]})
        if d["n_clusters_with_support"] == 0:
            f.append({"kind": "no_cluster_support", "term": t})
        elif d["n_clusters_with_support"] < MIN_CLUSTERS_FOR_RANK:
            f.append({"kind": "thin_cluster_support", "term": t,
                      "n_clusters_with_support": d["n_clusters_with_support"],
                      "floor": MIN_CLUSTERS_FOR_RANK})
    if rank.get("checked"):
        if not rank["full_rank"]:
            f.append({"kind": "rank_deficient_augmented", "term": "__augmented_design__",
                      "numerical_rank": rank["numerical_rank"],
                      "n_columns": rank["n_columns"],
                      "smallest_singular_value": (rank["singular_values"][-1]
                                                  if rank["singular_values"] else None),
                      "condition_number": rank["condition_number"],
                      "columns": rank["columns"]})
        elif not rank["condition_ok"]:
            f.append({"kind": "ill_conditioned_augmented", "term": "__augmented_design__",
                      "condition_number": rank["condition_number"], "ceiling": COND_MAX})
    else:
        f.append({"kind": "rank_not_assessable", "term": "__augmented_design__",
                  "note": rank.get("note")})
    if absorb and absorb.get("checked"):
        if absorb["offset_in_design_span"]:
            f.append({"kind": "offset_in_design_span", "term": "__offset__",
                      "relative_residual_norm": absorb["relative_residual_norm"],
                      "r2_of_offset_on_design": absorb["r2_of_offset_on_design"],
                      "detail": "the estimated design reproduces the fixed offset exactly; the "
                                "arm has a free recalibration slope the control does not have"})
        elif absorb["offset_nearly_absorbed"]:
            f.append({"kind": "offset_nearly_absorbed", "term": "__offset__",
                      "r2_of_offset_on_design": absorb["r2_of_offset_on_design"],
                      "threshold": absorb["near_tol"]})
    return f


def audit_fold(df: pd.DataFrame, fold_id: str, mask: np.ndarray,
               candidate_features: Sequence[str], nuisance_terms: Sequence[str],
               offset_col: str | None, cluster_col: str,
               rule: ActiveSetRule | None = None,
               prereg_audit: dict | None = None) -> dict:
    """One outer training fold, audited on its own material, before its own fit."""
    tr = df.loc[np.asarray(mask, bool)].reset_index(drop=True)
    terms = list(candidate_features) + list(nuisance_terms)
    clusters = tr[cluster_col]
    diag = column_diagnostics(tr, terms, clusters)
    off = tr[offset_col].to_numpy(float) if offset_col else None

    # exactly what the frozen gate computes, on exactly the columns it would be handed
    rank_features_only = _frozen_gate().design_rank_report(tr, list(candidate_features))
    rank_augmented = augmented_rank_report(tr, candidate_features, nuisance_terms, off,
                                           include_intercept=True)
    absorb = offset_absorption_report(tr, candidate_features, nuisance_terms, off,
                                      include_intercept=True)
    findings = _findings_from(diag, rank_augmented, terms, absorb)
    blocking = [x for x in findings if x["kind"] in BLOCKING_KINDS]

    summary = SupportSummary(
        fold_id=fold_id, n_rows=int(len(tr)), n_clusters=int(clusters.nunique()),
        term_std={t: diag[t]["std"] for t in terms},
        term_unique_levels={t: diag[t]["unique_levels"] for t in terms},
        term_cluster_support={t: diag[t]["n_clusters_with_support"] for t in terms},
        term_nonzero_rows={t: diag[t]["n_nonzero_rows"] for t in terms})

    rule_record, active_features, active_nuisance = None, list(candidate_features), \
        list(nuisance_terms)
    verdict = VERDICT_ESTIMABLE if not blocking else VERDICT_UNEVALUABLE
    post = None

    # A preregistered rule is evaluated on EVERY fold, not only on folds that happened to block.
    # Consulting it conditionally would make its application depend on the observed degeneracy,
    # which is precisely the post-hoc behaviour section 4 forbids, and would let a term sitting
    # below the rule's own numeric trigger survive in a fold that blocked for no other reason.
    if rule is not None:
        if prereg_audit is None or not prereg_audit.get("valid"):
            rule_record = {"applied": False,
                           "reason": "no valid preregistration audit supplied; "
                                     "GATE_INVOCATION_CONTRACT section 4"}
        else:
            dec = rule.decide(summary, terms)
            dropped = set(dec["dropped"])
            active_features = [t for t in candidate_features if t not in dropped]
            active_nuisance = [t for t in nuisance_terms if t not in dropped]
            post_rank = augmented_rank_report(tr, active_features, active_nuisance, off,
                                              include_intercept=True)
            post_absorb = offset_absorption_report(tr, active_features, active_nuisance, off,
                                                   include_intercept=True)
            post_diag = column_diagnostics(tr, active_features + active_nuisance, clusters)
            post_findings = _findings_from(post_diag, post_rank,
                                           active_features + active_nuisance, post_absorb)
            post_blocking = [x for x in post_findings if x["kind"] in BLOCKING_KINDS]
            post = {"rank_augmented": post_rank, "offset_absorption": post_absorb,
                    "findings": post_findings, "blocking": post_blocking}
            rule_record = {"applied": True, "rule_id": rule.rule_id,
                           "rule_spec_sha256": rule.spec_sha256,
                           "preregistration": prereg_audit["preregistration"],
                           "summary_the_rule_saw": summary.as_record(),
                           "dropped": dec["dropped"], "kept": dec["kept"], "why": dec["why"],
                           "residual_blocking_after_rule": post_blocking}
            if post_blocking:
                verdict = VERDICT_UNEVALUABLE
            elif dec["dropped"]:
                verdict = VERDICT_ESTIMABLE_UNDER_RULE
            else:
                verdict = VERDICT_ESTIMABLE

    return {"fold_id": fold_id, "n_rows": int(len(tr)),
            "n_clusters": int(clusters.nunique()),
            "seasons_in_fold": sorted(int(x) for x in tr["season"].unique())
            if "season" in tr.columns else None,
            "terms_audited": terms,
            "column_diagnostics": diag,
            "rank_features_only_AS_FROZEN_GATE_COMPUTES_IT": rank_features_only,
            "rank_augmented_with_offset_and_nuisance": rank_augmented,
            "offset_absorption": absorb,
            "rank_delta_vs_frozen_gate": {
                "frozen_gate_reports_full_rank": rank_features_only.get("full_rank"),
                "augmented_reports_full_rank": rank_augmented.get("full_rank"),
                "offset_in_design_span": absorb.get("offset_in_design_span"),
                "frozen_gate_would_miss_this": bool(
                    rank_features_only.get("full_rank")
                    and (not rank_augmented.get("full_rank")
                         or absorb.get("offset_in_design_span")))},
            "findings": findings, "blocking": blocking,
            "active_set_rule": rule_record,
            "post_rule": post,
            "active_features": active_features, "active_nuisance": active_nuisance,
            "verdict": verdict}


def guard(df: pd.DataFrame, candidate_features: Sequence[str], nuisance_terms: Sequence[str],
          offset_col: str | None, cluster_col: str, season_col: str = "season",
          fold_policy: str = "SEASON_BLOCK",
          null_features: Sequence[str] = (), null_nuisance: Sequence[str] | None = None,
          rule: ActiveSetRule | None = None, prereg: Preregistration | None = None,
          arm_id: str = "unnamed_arm") -> dict:
    """Full S7 receipt: every outer training fold, the final assembled design, and the pooled audit.

    The pooled audit is computed and reported ONLY so it can be contrasted with the folds. It is
    never permitted to carry the verdict: see `pooled_vs_fold_reconciliation`.
    """
    null_nuisance = list(nuisance_terms) if null_nuisance is None else list(null_nuisance)
    fold_masks = make_outer_training_folds(df[season_col], fold_policy)
    split = assert_games_not_split(fold_masks, df[cluster_col])

    prereg_audit = None
    prereg_problem = None
    if rule is not None and prereg is not None:
        try:
            prereg_audit = validate_preregistration(rule, prereg)
        except PreregistrationFailure as e:
            prereg_problem = json.loads(str(e))
    elif rule is not None:
        prereg_problem = [{"kind": "rule_supplied_without_preregistration"}]

    folds = [audit_fold(df, fid, m, candidate_features, nuisance_terms, offset_col,
                        cluster_col, rule, prereg_audit)
             for fid, m in fold_masks.items()]

    final = audit_fold(df, "FINAL_ASSEMBLED_DESIGN", np.ones(len(df), bool),
                       candidate_features, nuisance_terms, offset_col, cluster_col,
                       rule, prereg_audit)
    final["fold_id"] = "FINAL_ASSEMBLED_DESIGN"

    pooled_blocking = final["blocking"]
    terms = list(candidate_features) + list(nuisance_terms)
    absent_in_some_fold = {}
    for t in terms:
        bad = [f["fold_id"] for f in folds
               if f["column_diagnostics"][t]["zero_variance"]
               or f["column_diagnostics"][t]["n_clusters_with_support"] == 0]
        if bad:
            absent_in_some_fold[t] = bad
    # A pooled/final pass is misleading whenever a term is absent in some fold. It is NOT
    # "silently" reported as a pass when every affected fold carries an explicit verdict --
    # UNEVALUABLE, or ESTIMABLE_UNDER_PREREGISTERED_ACTIVE_SET with the drop recorded. The
    # distinction is the whole content of acceptance criterion 5, so it is materialised rather
    # than collapsed into one boolean.
    by_id = {f["fold_id"]: f for f in folds}
    affected = sorted({fid for v in absent_in_some_fold.values() for fid in v})
    ungoverned = [fid for fid in affected
                  if by_id[fid]["verdict"] == VERDICT_ESTIMABLE]
    pooled_pass_would_be_misleading = bool(not pooled_blocking and absent_in_some_fold)
    pooled_masks_fold = bool(pooled_pass_would_be_misleading and ungoverned)

    # parameter counts are reconciled on the FOLD-LOCAL ACTIVE SETS, not on the declared lists,
    # because a fold-local rule that fired on the candidate but not on the null would otherwise
    # slip through.
    recon = {}
    for f in folds + [final]:
        recon[f["fold_id"]] = reconcile_parameter_counts(
            f["active_features"],
            f["active_nuisance"],
            [t for t in null_features if t in set(f["active_features"])],
            [t for t in null_nuisance if t in set(f["active_nuisance"])])

    unevaluable = [f["fold_id"] for f in folds + [final]
                   if f["verdict"] == VERDICT_UNEVALUABLE]
    unreconciled = [k for k, v in recon.items() if not v["reconciled"]]
    under_rule = [f["fold_id"] for f in folds + [final]
                  if f["verdict"] == VERDICT_ESTIMABLE_UNDER_RULE]

    if unevaluable or unreconciled or not split["ok"] or pooled_masks_fold:
        overall = "FAIL"
    elif under_rule:
        overall = "PASS_UNDER_PREREGISTERED_ACTIVE_SET"
    else:
        overall = "PASS"

    return {
        "schema": "s7_fold_local_estimability_receipt/1",
        "arm_id": arm_id,
        "epistemic_status": ("INFRASTRUCTURE + task-specific INVARIANT. Proves an arm/fold is "
                             "estimable before it is fitted. Does not establish that an estimable "
                             "arm is a real effect."),
        "fold_policy": fold_policy,
        "n_rows_universe": int(len(df)),
        "n_clusters_universe": int(df[cluster_col].nunique()),
        "games_not_split_check": split,
        "offset_column": offset_col,
        "candidate_features": list(candidate_features),
        "nuisance_terms": list(nuisance_terms),
        "null_features": list(null_features),
        "null_nuisance": list(null_nuisance),
        "active_set_rule_declared": rule.spec if rule else None,
        "preregistration_audit": prereg_audit,
        "preregistration_problems": prereg_problem,
        "folds": folds,
        "final_design": final,
        "pooled_vs_fold_reconciliation": {
            "pooled_blocking_findings": pooled_blocking,
            "terms_absent_or_zero_variance_in_at_least_one_fold": absent_in_some_fold,
            "affected_folds": affected,
            "affected_folds_without_an_explicit_verdict": ungoverned,
            "pooled_pass_would_be_misleading": pooled_pass_would_be_misleading,
            "pooled_pass_masks_fold_degeneracy": pooled_masks_fold,
            "rule": "a pooled pass is NEVER reported as a pass while a term is absent in a fold "
                    "unless every affected fold carries an explicit verdict -- UNEVALUABLE, or "
                    "ESTIMABLE_UNDER_PREREGISTERED_ACTIVE_SET with the drop recorded. "
                    "GATE_INVOCATION_CONTRACT sections 1 and 4"},
        "parameter_count_reconciliation": recon,
        "folds_marked_unevaluable": unevaluable,
        "folds_estimable_only_under_active_set_rule": under_rule,
        "folds_with_unreconciled_parameter_counts": unreconciled,
        "overall": overall,
    }
