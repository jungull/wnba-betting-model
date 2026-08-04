#!/usr/bin/env python3
"""postgame_surrogate_guard.py — Stage 2 CALL-SITE wrapper enforcing V2 stop-condition S1.

WHAT THIS IS
------------
S1 of ``stage2a/V2_STOP_CONDITION.json`` records that ``master_team.minutes`` is an EXACT
current-game overtime indicator: it is ``5 x game_minutes`` on every row, with zero nulls and zero
variance in the ratio, so ``game_minutes`` is recoverable by division. The ruling prohibits any
function of ``game_minutes`` from the prediction path. S1 states the consequence in one line:

    "A convention is not enough; this needs an enforced invariant."

This module is that invariant. It is a **wrapper at the call site**, not an edit to
``feature_gate.py``. ``feature_gate.py`` is byte-unchanged and this module does not import from it
in a way that could alter it; it calls ``feature_gate.audit`` and adds a check the gate does not
have.

WHY THE EXISTING GATE CANNOT DO THIS (measured, not asserted)
-------------------------------------------------------------
On the 2,982-row / 1,491-game-cluster possession universe:

    corr(master_team.minutes, target)  = -0.0204     gate target_corr_threshold = 0.98
    corr(master_team.minutes, offset)  = -0.0030     gate corr_threshold        = 0.999
    std(master_team.minutes)           =  6.2211     not zero, not degenerate
    nulls                              =  0          no missingness branch can fire

``feature_gate.audit(...)`` with ``offset=``, ``target=`` and ``test_df=`` all supplied returns
``passed=True`` with ``findings == []`` for a design containing ``master_team.minutes``, for
``minutes/5``, for ``3*minutes - 17.5``, and for raw ``game_minutes`` itself. That is not a defect
in ``feature_gate.py``: §7.3 of ``GATE_INVOCATION_CONTRACT.md`` says so in advance —

    "A column derived from post-cutoff information whose values happen not to correlate above
     threshold with the target ... passes. Cutoff validity remains a registration obligation and a
     producer obligation, and is not delegated here."

The gate compares features against the TARGET and against the OFFSET. It has no third comparand.
This wrapper supplies one: the **prohibited basis** — the realised current-game duration of the
row's own game, in every algebraically equivalent form — and blocks any declared feature that is a
function of it, or from which it is recoverable.

THE THREE CHECKS, AND WHY EACH IS SEPARATELY NECESSARY
-------------------------------------------------------
1. **Declaration (fail closed).** Every declared feature must carry a ``LagSpec``. A missing spec
   BLOCKS. A ``SAME_GAME`` spec BLOCKS unconditionally. Absence is failure, never a pass.

2. **Empirical lag verification.** A ``PRIOR_GAME`` claim is re-derived from the declared source
   and compared value-for-value against the column actually presented. A same-game column
   *mislabelled* as prior-game is caught here even though its declaration is clean. A claim that
   cannot be re-derived BLOCKS as unverifiable — it is not credited.

3. **Dependency battery against the prohibited basis.** Runs on every declared feature regardless
   of what it declared, because the declaration is the caller's word:

     - ``function_of_prohibited``   the column is constant within every level of a prohibited
                                    quantity, i.e. col = f(prohibited). Invariant to ANY injective
                                    reparameterisation of the column, so a rename, a rescale, a
                                    unit change or a nonlinear monotone map does not evade it.
     - ``prohibited_recoverable``   the prohibited quantity is constant within every level of the
                                    column, i.e. prohibited = g(col). This is the S1 harm itself:
                                    ``minutes / 5`` recovers ``game_minutes`` on 2,982 of 2,982
                                    rows.
     - ``exact_affine_of_prohibited`` / ``prohibited_exact_affine_of_column``
                                    zero-residual least squares in either direction. Cardinality
                                    free, so it catches a continuous linear transform that the
                                    two partition tests would have to bound.
     - ``near_collinear_with_prohibited``  |r| >= 0.999 against a prohibited quantity. Catches a
                                    noisy near-surrogate that is not an exact function.

WHAT THIS DOES NOT ESTABLISH
----------------------------
Nothing about any candidate's accuracy. Nothing about whether a passing column is cutoff-valid for
reasons OTHER than current-game duration — S3 (injury regimes), S8 (the 32 unadjudicated possession
columns) and the rest of the prohibited-outcome surface are separate obligations with separate
nodes. This guard enforces exactly one invariant: current-game realised duration, and exact or
near-exact surrogates for it, cannot silently enter a prediction frame.

Run::

    python postgame_surrogate_guard.py          # descriptive self-report
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np, pandas as pd                                                 # noqa: E401

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]                    # experiments/player_program
ROOT = PROGRAM.parents[1]                    # repository worktree root

if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

import construction_receipt as cr                                                # noqa: E402
import feature_gate as fg                                                        # noqa: E402

SCHEMA = "postgame_surrogate_guard/1"
RECEIPT_KIND = "postgame_surrogate_guard_audit/1"

#: the byte identity of the gate this wrapper wraps. Recorded so a reviewer can confirm from the
#: audit record alone that no gate edit was made. Verified by TESTS.py, not just stated here.
FEATURE_GATE_SHA256 = "b064c2c4675d354ec5cb5c6647782634c8139ca4233a5d732f408b6c2532f9a7"

#: regulation length in minutes, and the length of one overtime period. Mirrored from
#: possession_features.REGULATION_MIN and build_projected_exposure; stated, not re-derived.
REGULATION_MIN = 40.0
OVERTIME_MIN = 5.0
#: five players on the floor for a team at all times. This is the constant S1 measured: the ratio
#: master_team.minutes / game_minutes is 5.0 with sd 0.0 on 2990 of 2990 rows.
PLAYERS_ON_FLOOR = 5.0

#: relative tolerance for "exact". Float arithmetic on a quantity of order 40-300 leaves residuals
#: near 1e-13; 1e-9 is four orders of magnitude above that and eleven below any real signal.
EXACT_RTOL = 1e-9
#: |r| at or above this against a prohibited quantity is a near-surrogate. Deliberately the same
#: number feature_gate uses for near_collinear, so the two gates speak one language.
NEAR_COLLINEAR_R = 0.999
#: a column needs at most this many times the prohibited quantity's distinct-value count before
#: "the prohibited quantity is constant within each of the column's levels" stops meaning
#: "recoverable" and starts meaning "high cardinality". Bound stated so the reader can audit it.
RECOVERY_CARDINALITY_FACTOR = 4

BLOCKING = frozenset({
    "lag_specification_absent",
    "lag_specification_unrecognised",
    "same_game_join",
    "lag_alignment_violated",
    "lag_unverifiable",
    "function_of_prohibited",
    "prohibited_recoverable",
    "exact_affine_of_prohibited",
    "prohibited_exact_affine_of_column",
    "near_collinear_with_prohibited",
    "prohibited_basis_absent",
    "prohibited_basis_misaligned",
    "prohibited_basis_degenerate",
    "gate_bytes_changed",
})

INFORMATIONAL = frozenset({
    "constant_column_not_assessed",
    "prohibited_level_support",
    "schedule_fact_admitted",
})


class PostgameSurrogateFailure(RuntimeError):
    """Raised on any blocking finding. The call site fails; it does not receive a frame."""


# --------------------------------------------------------------------------------------------
# lag declarations
# --------------------------------------------------------------------------------------------

SAME_GAME = "SAME_GAME"
PRIOR_GAME = "PRIOR_GAME"
SCHEDULE = "SCHEDULE"
DERIVED_NO_JOIN = "DERIVED_NO_JOIN"

LAG_KINDS = (SAME_GAME, PRIOR_GAME, SCHEDULE, DERIVED_NO_JOIN)


@dataclass(frozen=True)
class LagSpec:
    """How ONE declared feature column reached the frame.

    ``kind`` is the caller's claim. It is never taken on trust:

      * ``SAME_GAME``       blocks unconditionally. Declared honestly or not, a join on the target
                            game's own key with no lag is the failure this guard exists to stop.
      * ``PRIOR_GAME``      is re-derived from ``source_path`` and compared value-for-value. The
                            claim survives only if the bytes agree.
      * ``SCHEDULE``        is a fact fixed before tipoff (opponent, venue, playoff flag). It skips
                            lag re-derivation because there is no lag to re-derive, and still faces
                            the full dependency battery.
      * ``DERIVED_NO_JOIN`` is computed from columns already inside the audited frame. Same: no lag
                            to re-derive, full dependency battery.

    ``entity_keys`` / ``order_column`` / ``n_back`` / ``strict`` are the SOURCE KEYS the receipt
    records. ``strict=False`` on a ``PRIOR_GAME`` spec is itself a same-game join and blocks.
    """

    column: str
    kind: str
    source_artifact_id: str = ""
    source_path: str | None = None
    source_value_column: str | None = None
    entity_keys: tuple[str, ...] = ()
    order_column: str | None = None
    n_back: int = 1
    strict: bool = True
    null_policy: str = "null_when_no_prior_observation"
    rationale: str = ""

    def as_record(self) -> dict:
        p = None if self.source_path is None else Path(self.source_path)
        return {
            "column": self.column,
            "lag_kind": self.kind,
            "source_artifact_id": self.source_artifact_id or None,
            "source_path": (None if p is None else str(p)),
            "source_sha256": (None if p is None or not p.exists()
                              else _sha256_file(p)),
            "source_value_column": self.source_value_column,
            "join_keys": list(self.entity_keys),
            "order_column": self.order_column,
            "n_back": int(self.n_back),
            "strict_inequality": bool(self.strict),
            "null_policy": self.null_policy,
            "rationale": self.rationale,
        }


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------------------------
# the prohibited basis
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ProhibitedBasis:
    """The realised current-game duration of each row's OWN game, in every equivalent form.

    One quantity, four parameterisations. They are listed separately not because they carry
    different information — they are mutually determining — but because a finding that names the
    parameterisation a column matched is more useful to a reviewer than one that does not.
    """

    frame: pd.DataFrame
    source: dict
    note: str = ""

    @property
    def names(self) -> list[str]:
        return [str(c) for c in self.frame.columns]

    def as_record(self) -> dict:
        rec = {"names": self.names, "n_rows": int(len(self.frame)), "source": dict(self.source),
               "note": self.note, "levels": {}}
        for c in self.frame.columns:
            v = self.frame[c].dropna()
            vc = v.value_counts().sort_index()
            rec["levels"][str(c)] = {"n_distinct": int(v.nunique()),
                                     "support": {str(k): int(n) for k, n in vc.items()},
                                     "n_null": int(self.frame[c].isna().sum())}
        rec["values_digest"] = {str(c): cr.values_digest(self.frame[c], label=f"prohibited_{c}")
                                for c in self.frame.columns}
        return rec


def realised_duration_basis(index: pd.Index, *, game_id: pd.Series,
                            possessions_path: str | Path,
                            repo_root: str | Path | None = None) -> ProhibitedBasis:
    """Build the prohibited basis for the rows in ``index`` from the frozen possessions artifact.

    ``game_minutes`` is computed exactly as ``possession_features._realised_offensive_possessions``
    computes it — ``40 + 5 * max(0, max_period - 4)`` — because a guard that used a DIFFERENT
    definition of the prohibited quantity than the pipeline uses would be guarding a different
    thing. ``team_minutes`` is ``5 * game_minutes``: that is what ``master_team.minutes`` is, and
    S1's measurement of the identity is re-derived in this node's REPORT.md.

    This function reads the possessions artifact READ-ONLY and hashes the bytes it read.
    """
    p = Path(possessions_path)
    if not p.exists():
        raise PostgameSurrogateFailure(
            f"the prohibited-basis source does not exist at {p}. This guard cannot certify a "
            f"frame against a basis it could not construct; it refuses rather than passing")
    poss = pd.read_parquet(p, columns=["game_id", "period"])
    mp = poss.groupby("game_id")["period"].max().rename("max_period").reset_index()
    n_ot = np.maximum(0, mp["max_period"].to_numpy(float) - 4.0)
    mp["game_minutes"] = REGULATION_MIN + OVERTIME_MIN * n_ot
    mp["overtime_periods"] = n_ot
    mp["is_overtime"] = (n_ot > 0).astype(float)
    mp["team_minutes"] = PLAYERS_ON_FLOOR * mp["game_minutes"]

    g = pd.Series(np.asarray(game_id), index=index, name="game_id")
    B = (g.to_frame().reset_index()
         .merge(mp[["game_id", "game_minutes", "overtime_periods", "is_overtime", "team_minutes"]],
                on="game_id", how="left"))
    B = B.set_index(B.columns[0]).loc[index]
    B = B[["game_minutes", "overtime_periods", "is_overtime", "team_minutes"]]

    src = cr.source_declaration(
        p, role="outcome_source", artifact_id="player_possessions/2", cutoff_valid=False,
        cutoff_rationale=(
            "REALISED possessions and period structure of the target game. Read here ONLY to "
            "construct the PROHIBITED quantity the guard tests against. It contributes no feature "
            "column and is never returned to a caller as one"),
        coverage={"unit": "possession", "role": "prohibited_basis_source"},
        repo_root=(ROOT if repo_root is None else repo_root))

    return ProhibitedBasis(
        frame=B, source=src,
        note=("game_minutes = 40 + 5 * max(0, max_period - 4), identical to the definition used by "
              "possession_features._realised_offensive_possessions; team_minutes = 5 * "
              "game_minutes, which is exactly master_team.minutes (S1)"))


# --------------------------------------------------------------------------------------------
# the dependency battery
# --------------------------------------------------------------------------------------------

def _partition_refines(a: np.ndarray, b: np.ndarray) -> tuple[bool, int, int]:
    """Is ``b`` constant within every level of ``a``? Returns (refines, n_levels_a, n_violating)."""
    df = pd.DataFrame({"a": a, "b": b}).dropna()
    if df.empty:
        return False, 0, 0
    nun = df.groupby("a")["b"].nunique()
    return bool((nun <= 1).all()), int(len(nun)), int((nun > 1).sum())


def _exact_affine(x: np.ndarray, y: np.ndarray) -> tuple[bool, float, float | None, float | None]:
    """Is ``y`` an exact affine function of ``x``? Returns (exact, rel_max_resid, slope, intercept)."""
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 10:
        return False, float("inf"), None, None
    xx, yy = x[m], y[m]
    vx = float(np.var(xx))
    if vx == 0.0:
        return False, float("inf"), None, None
    b = float(np.cov(xx, yy, ddof=0)[0, 1] / vx)
    a = float(yy.mean() - b * xx.mean())
    resid = yy - (a + b * xx)
    scale = float(np.std(yy))
    if scale == 0.0:
        return False, float("inf"), b, a
    rel = float(np.max(np.abs(resid)) / scale)
    return bool(rel <= EXACT_RTOL), rel, b, a


def _corr(x: np.ndarray, y: np.ndarray) -> float | None:
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 10 or np.std(x[m]) == 0 or np.std(y[m]) == 0:
        return None
    return float(np.corrcoef(x[m], y[m])[0, 1])


def dependency_report(values: np.ndarray, prohibited: np.ndarray) -> dict:
    """Every dependency measurement for ONE column against ONE prohibited quantity."""
    col_fn_of_prob, n_prob_levels, n_prob_violating = _partition_refines(prohibited, values)
    prob_fn_of_col, n_col_levels, n_col_violating = _partition_refines(values, prohibited)
    exact_col, rel_col, slope_col, icept_col = _exact_affine(prohibited, values)
    exact_prob, rel_prob, slope_prob, icept_prob = _exact_affine(values, prohibited)
    r = _corr(values, prohibited)
    n_distinct_prob = int(pd.Series(prohibited).dropna().nunique())
    return {
        "column_is_function_of_prohibited": bool(col_fn_of_prob),
        "n_prohibited_levels": n_prob_levels,
        "n_prohibited_levels_with_varying_column": n_prob_violating,
        "prohibited_is_function_of_column": bool(prob_fn_of_col),
        "n_column_levels": n_col_levels,
        "n_column_levels_with_varying_prohibited": n_col_violating,
        "column_cardinality_within_recovery_bound": bool(
            n_col_levels <= max(1, n_distinct_prob) * RECOVERY_CARDINALITY_FACTOR),
        "column_exact_affine_of_prohibited": bool(exact_col),
        "column_affine_rel_max_residual": (None if not np.isfinite(rel_col) else round(rel_col, 15)),
        "column_affine_slope": slope_col, "column_affine_intercept": icept_col,
        "prohibited_exact_affine_of_column": bool(exact_prob),
        "prohibited_affine_rel_max_residual": (None if not np.isfinite(rel_prob)
                                               else round(rel_prob, 15)),
        "prohibited_affine_slope": slope_prob, "prohibited_affine_intercept": icept_prob,
        "pearson_r": (None if r is None else round(r, 9)),
    }


# --------------------------------------------------------------------------------------------
# lag re-derivation
# --------------------------------------------------------------------------------------------

def verify_prior_game_lag(frame: pd.DataFrame, spec: LagSpec, source: pd.DataFrame) -> dict:
    """Re-derive a PRIOR_GAME column from ``source`` and compare it to what the frame carries.

    ``source`` must carry the spec's ``entity_keys``, its ``order_column`` and its
    ``source_value_column``, plus whatever identity columns the audited frame is indexed on. The
    re-derivation groups by the entity keys, orders by the order column, and shifts by ``n_back``.

    A same-game value mislabelled ``PRIOR_GAME`` produces a mismatch on every row where the
    prior game differs from the current one, and is caught here even though its DECLARATION was
    clean. That is the point: the declaration is the caller's word, the bytes are not.
    """
    out: dict = {"column": spec.column, "verified": False, "reason": None}
    need = list(spec.entity_keys) + [spec.order_column, spec.source_value_column]
    missing = [c for c in need if c is None or c not in source.columns]
    if missing:
        out["reason"] = f"the declared lag source lacks {missing}"
        return out
    if not spec.strict:
        out["reason"] = ("strict_inequality=False on a PRIOR_GAME declaration admits the row's own "
                         "game into its own history; that is a same-game join")
        return out
    if spec.n_back < 1:
        out["reason"] = f"n_back={spec.n_back} is not a lag"
        return out

    S = source.copy()
    if S.index.has_duplicates:
        out["reason"] = "the lag source has duplicate row labels; rows cannot be aligned"
        return out
    if not set(frame.index) <= set(S.index):
        out["reason"] = ("the lag source is not indexed on the audited frame's row identities, so "
                         "the re-derivation cannot be aligned to the rows being audited")
        return out
    order = [*spec.entity_keys, spec.order_column]
    S = S.sort_values(order, kind="mergesort")
    S["__expected__"] = S.groupby(list(spec.entity_keys))[spec.source_value_column].shift(spec.n_back)
    exp = S["__expected__"].reindex(frame.index)
    got = frame[spec.column]

    ev = exp.to_numpy(float)
    sd = float(np.nanstd(ev)) if np.isfinite(ev).any() else 0.0
    both_null = exp.isna() & got.isna()
    equal = np.isclose(ev, got.to_numpy(float), rtol=0.0,
                       atol=EXACT_RTOL * max(1.0, sd if np.isfinite(sd) else 1.0),
                       equal_nan=False)
    agree = np.asarray(both_null) | equal
    n_disagree = int((~agree).sum())
    out.update({
        "n_rows": int(len(frame)),
        "n_expected_null": int(exp.isna().sum()),
        "n_presented_null": int(got.isna().sum()),
        "n_rows_disagreeing": n_disagree,
        "verified": bool(n_disagree == 0),
        "expected_digest": cr.values_digest(exp, label="rederived_lag"),
        "presented_digest": cr.values_digest(got, label="presented_lag"),
    })
    if n_disagree:
        bad = frame.index[~agree][:5]
        out["reason"] = (f"{n_disagree} of {len(frame)} rows do not match the lag re-derived from "
                         f"the declared source")
        out["example_rows"] = [str(i) for i in bad]
    return out


# --------------------------------------------------------------------------------------------
# the audit
# --------------------------------------------------------------------------------------------

def audit(frame: pd.DataFrame, names: Sequence[str], *,
          prohibited: ProhibitedBasis | None,
          lag_specs: Mapping[str, LagSpec] | None = None,
          lag_sources: Mapping[str, pd.DataFrame] | None = None,
          raise_on_block: bool = True) -> dict:
    """Enforce S1 on one feature design. Returns a machine-readable audit; raises when blocked.

    ``prohibited=None`` is not a way to skip the check. It BLOCKS: a design audited without a
    prohibited basis has not been shown to be free of one, and this guard fails closed.
    """
    names = [str(c) for c in names]
    lag_specs = dict(lag_specs or {})
    lag_sources = dict(lag_sources or {})
    findings: list[dict] = []
    per_column: dict[str, Any] = {}

    gate_now = _sha256_file(PROGRAM / "feature_gate.py")
    if gate_now != FEATURE_GATE_SHA256:
        findings.append({"kind": "gate_bytes_changed", "feature": "__gate__",
                         "expected_sha256": FEATURE_GATE_SHA256, "observed_sha256": gate_now,
                         "detail": "feature_gate.py is not the frozen artifact this wrapper wraps. "
                                   "A wrapper cannot certify a gate it cannot identify"})

    missing_cols = [c for c in names if c not in frame.columns]
    if missing_cols:
        raise PostgameSurrogateFailure(f"declared features absent from the frame: {missing_cols}")

    #: which prohibited quantities the dependency battery may actually be run against. A basis
    #: that is misaligned or degenerate is recorded as BLOCKING and then NOT used: running a
    #: non-discriminating test and reporting its verdict would be worse than reporting that the
    #: test could not discriminate.
    testable: list[str] = []
    if prohibited is None:
        findings.append({"kind": "prohibited_basis_absent", "feature": "__design__",
                         "detail": "no prohibited basis was supplied. The guard cannot demonstrate "
                                   "the invariant and therefore does not assert it"})
    elif not prohibited.frame.index.equals(frame.index):
        findings.append({"kind": "prohibited_basis_misaligned", "feature": "__design__",
                         "n_basis_rows": int(len(prohibited.frame)),
                         "n_frame_rows": int(len(frame)),
                         "detail": "the prohibited basis is not aligned row-for-row with the "
                                   "audited frame; a per-row invariant cannot be tested against a "
                                   "differently-indexed basis, so no dependency verdict is issued"})
    else:
        degenerate = [str(c) for c in prohibited.frame.columns
                      if int(prohibited.frame[c].dropna().nunique()) < 2]
        testable = [str(c) for c in prohibited.frame.columns if str(c) not in degenerate]
        if degenerate:
            findings.append({"kind": "prohibited_basis_degenerate", "feature": "__design__",
                             "degenerate_quantities": degenerate,
                             "detail": "these prohibited quantities have no variation on the "
                                       "audited rows, so no dependency test against them can "
                                       "discriminate. A non-discriminating test is not a pass, and "
                                       "no verdict is issued against them"})

    for c in names:
        v = frame[c].to_numpy(float)
        rec: dict[str, Any] = {"lag": None, "lag_verification": None, "dependency": {}}

        # ---- 1. declaration, fail closed ----
        spec = lag_specs.get(c)
        if spec is None:
            findings.append({"kind": "lag_specification_absent", "feature": c,
                             "detail": "no LagSpec was declared for this column. Absence of a "
                                       "declaration is a failure, never a pass: an undeclared "
                                       "column is exactly the silent entry S1 requires be stopped"})
        else:
            rec["lag"] = spec.as_record()
            if spec.kind not in LAG_KINDS:
                findings.append({"kind": "lag_specification_unrecognised", "feature": c,
                                 "declared_kind": spec.kind, "known_kinds": list(LAG_KINDS)})
            elif spec.kind == SAME_GAME:
                findings.append({"kind": "same_game_join", "feature": c,
                                 "join_keys": list(spec.entity_keys),
                                 "source_artifact_id": spec.source_artifact_id,
                                 "detail": "the column is joined on the target game's own key with "
                                           "no lag. This blocks unconditionally, whatever the "
                                           "column's measured correlations turn out to be"})
            elif spec.kind == PRIOR_GAME and not spec.strict:
                findings.append({"kind": "same_game_join", "feature": c,
                                 "join_keys": list(spec.entity_keys),
                                 "order_column": spec.order_column,
                                 "strict_inequality": False,
                                 "detail": "a PRIOR_GAME window declared with strict_inequality="
                                           "False admits the row's OWN game into its own history. "
                                           "That is a same-game join written as a lag, and it "
                                           "blocks at the declaration layer, before any bytes are "
                                           "read"})
            elif spec.kind == PRIOR_GAME:
                src = lag_sources.get(c)
                if src is None:
                    findings.append({"kind": "lag_unverifiable", "feature": c,
                                     "detail": "a PRIOR_GAME claim was declared but no source frame "
                                               "was supplied to re-derive it from. An unverified "
                                               "lag claim is not credited"})
                else:
                    ver = verify_prior_game_lag(frame, spec, src)
                    rec["lag_verification"] = ver
                    if not ver["verified"]:
                        kind = ("lag_alignment_violated" if ver.get("n_rows_disagreeing")
                                else "lag_unverifiable")
                        findings.append({"kind": kind, "feature": c, **{
                            k: ver[k] for k in ("reason", "n_rows_disagreeing", "example_rows")
                            if k in ver}})
            elif spec.kind in (SCHEDULE, DERIVED_NO_JOIN):
                findings.append({"kind": "schedule_fact_admitted", "feature": c,
                                 "declared_kind": spec.kind, "rationale": spec.rationale,
                                 "detail": "no lag to re-derive; admitted on the declaration and "
                                           "still subject to the full dependency battery below"})

        # ---- 2 & 3. dependency battery ----
        if prohibited is not None and testable:
            if float(np.nanstd(v)) == 0.0:
                findings.append({"kind": "constant_column_not_assessed", "feature": c,
                                 "detail": "the column is constant, so every partition test is "
                                           "vacuously true. feature_gate.zero_variance blocks it"})
            else:
                for q in testable:
                    p = prohibited.frame[q].to_numpy(float)
                    d = dependency_report(v, p)
                    rec["dependency"][str(q)] = d
                    if d["column_is_function_of_prohibited"]:
                        findings.append({"kind": "function_of_prohibited", "feature": c,
                                         "prohibited_quantity": str(q), **_slim(d),
                                         "detail": "the column is constant within every level of a "
                                                   "realised current-game duration quantity, i.e. "
                                                   "it IS a function of it. Renaming or rescaling "
                                                   "the column does not change this"})
                    if d["prohibited_is_function_of_column"] and \
                            d["column_cardinality_within_recovery_bound"]:
                        findings.append({"kind": "prohibited_recoverable", "feature": c,
                                         "prohibited_quantity": str(q), **_slim(d),
                                         "detail": "the realised current-game duration is "
                                                   "recoverable from this column. This is the S1 "
                                                   "harm: minutes / 5 returns game_minutes"})
                    if d["column_exact_affine_of_prohibited"]:
                        findings.append({"kind": "exact_affine_of_prohibited", "feature": c,
                                         "prohibited_quantity": str(q), **_slim(d),
                                         "detail": "zero-residual affine map from the prohibited "
                                                   "quantity to the column"})
                    if d["prohibited_exact_affine_of_column"]:
                        findings.append({"kind": "prohibited_exact_affine_of_column", "feature": c,
                                         "prohibited_quantity": str(q), **_slim(d),
                                         "detail": "zero-residual affine map from the column back "
                                                   "to the prohibited quantity"})
                    if d["pearson_r"] is not None and abs(d["pearson_r"]) >= NEAR_COLLINEAR_R and \
                            not d["column_exact_affine_of_prohibited"]:
                        findings.append({"kind": "near_collinear_with_prohibited", "feature": c,
                                         "prohibited_quantity": str(q), **_slim(d),
                                         "detail": "not an exact function, but a near-surrogate at "
                                                   "the same |r| threshold feature_gate uses for "
                                                   "near_collinear"})
        per_column[c] = rec

    blocking = [f for f in findings if f["kind"] in BLOCKING]
    out = {
        "schema": SCHEMA,
        "n_features": len(names), "n_rows": int(len(frame)), "features": names,
        "feature_gate_sha256": gate_now,
        "feature_gate_byte_unchanged": bool(gate_now == FEATURE_GATE_SHA256),
        "prohibited_basis": (None if prohibited is None else prohibited.as_record()),
        "per_column": per_column,
        "findings": findings,
        "blocking": blocking,
        "passed": len(blocking) == 0,
        "thresholds": {"EXACT_RTOL": EXACT_RTOL, "NEAR_COLLINEAR_R": NEAR_COLLINEAR_R,
                       "RECOVERY_CARDINALITY_FACTOR": RECOVERY_CARDINALITY_FACTOR},
        "note": ("this guard establishes ONE invariant: no declared feature is, or recovers, the "
                 "realised current-game duration. It establishes nothing about accuracy and "
                 "nothing about any other prohibited-outcome surface"),
    }
    if blocking and raise_on_block:
        raise PostgameSurrogateFailure(json.dumps(blocking[:6], default=str))
    return out


def _slim(d: Mapping[str, Any]) -> dict:
    keep = ("n_prohibited_levels", "n_prohibited_levels_with_varying_column",
            "n_column_levels", "n_column_levels_with_varying_prohibited",
            "column_affine_slope", "column_affine_intercept",
            "column_affine_rel_max_residual", "prohibited_affine_slope",
            "prohibited_affine_intercept", "prohibited_affine_rel_max_residual", "pearson_r")
    return {k: d[k] for k in keep if k in d}


def guarded_audit(frame: pd.DataFrame, names: Sequence[str], *,
                  prohibited: ProhibitedBasis | None,
                  lag_specs: Mapping[str, LagSpec] | None = None,
                  lag_sources: Mapping[str, pd.DataFrame] | None = None,
                  **gate_kwargs: Any) -> dict:
    """S1 guard FIRST, then ``feature_gate.audit``. The composition a Stage 2 call site uses.

    Order matters. The guard runs first so that a prohibited column never reaches the gate and is
    never recorded as gate-passing; a reviewer reading a gate record for a design that contains a
    duration surrogate would otherwise see a clean record and reasonably conclude the design was
    clean. ``feature_gate.audit`` is called unmodified, with whatever arguments the caller supplies,
    and its record is returned alongside — not merged into — the guard's.
    """
    guard = audit(frame, names, prohibited=prohibited, lag_specs=lag_specs,
                  lag_sources=lag_sources, raise_on_block=True)
    gate = fg.audit(frame, list(names), **gate_kwargs)
    return {"schema": SCHEMA, "guard": guard, "feature_gate": gate,
            "passed": bool(guard["passed"] and gate["passed"]),
            "note": ("two independent records. The gate's pass is about the enumerated failure "
                     "modes in GATE_INVOCATION_CONTRACT §3; the guard's is about S1. Neither "
                     "subsumes the other and neither may be cited as the other")}


# --------------------------------------------------------------------------------------------
# receipt
# --------------------------------------------------------------------------------------------

def emit_guard_receipt(*, receipt_path: str | Path, experiment: str, arm: str, fold: str,
                       run_id: str, frame: pd.DataFrame, feature_names: Sequence[str],
                       universe: Mapping[str, Any], fold_identity: Mapping[str, Any],
                       cutoff: Mapping[str, Any], sources: Sequence[Mapping[str, Any]],
                       guard_audit: Mapping[str, Any],
                       lag_specs: Mapping[str, LagSpec],
                       scope: str = "fold", feature_set_id: str = "",
                       gate_arguments: Mapping[str, Any] | None = None,
                       repo_root: str | Path | None = None,
                       notes: Mapping[str, Any] | None = None) -> dict:
    """Emit a real ``construction_receipt/1`` whose transformation block IS the lag record.

    The acceptance criterion is that construction receipts record the lag transformation and the
    source keys. Both go into ``produced_frame_provenance.transformation``, which
    ``construction_receipt`` digests and binds, so the lag declaration cannot later be edited
    without breaking the receipt's own binding digest.
    """
    transformation = {
        "kind": "postgame_surrogate_guard/lag_declaration",
        "statement": ("every declared feature's lag transformation and source keys, as enforced by "
                      "postgame_surrogate_guard.audit. A SAME_GAME kind never reaches this record: "
                      "the guard raises before a frame is emitted"),
        "columns": {c: lag_specs[c].as_record() for c in sorted(lag_specs)},
        "prohibited_basis": (guard_audit.get("prohibited_basis") or {}),
        "guard_verdict": {"passed": bool(guard_audit.get("passed")),
                          "n_findings": len(guard_audit.get("findings") or []),
                          "n_blocking": len(guard_audit.get("blocking") or []),
                          "finding_kinds": sorted({f["kind"] for f
                                                   in (guard_audit.get("findings") or [])})},
        "lag_verification": {c: (guard_audit.get("per_column", {}).get(c) or {}).get(
            "lag_verification") for c in sorted(lag_specs)},
        "feature_gate_sha256": guard_audit.get("feature_gate_sha256"),
        "feature_gate_byte_unchanged": guard_audit.get("feature_gate_byte_unchanged"),
        "thresholds": guard_audit.get("thresholds"),
    }
    return cr.emit_construction_receipt(
        receipt_path=receipt_path, experiment=experiment, arm=arm, fold=fold, run_id=run_id,
        frame=frame, feature_names=list(feature_names), universe=universe,
        fold_identity=fold_identity, cutoff=cutoff, sources=list(sources), scope=scope,
        feature_set_id=feature_set_id, transformation=transformation,
        gate_arguments=gate_arguments, repo_root=repo_root,
        claim_boundary_additions={
            "s1_invariant": (
                "this receipt records that postgame_surrogate_guard enforced S1 on this frame: no "
                "declared feature is, or recovers, the realised current-game duration. It "
                "establishes nothing about any other prohibited-outcome surface and nothing about "
                "accuracy"),
        },
        notes=dict(notes or {}))


def verify_guard_receipt(path: str | Path, **kw: Any) -> dict:
    """``cr.verify_construction_receipt`` PLUS a re-computation of the transformation digest.

    MEASURED DEFECT this closes, at the call site, without editing the frozen module.

    ``construction_receipt.binding_fields`` binds ``transformation_digest`` — the stored scalar —
    and ``verify_construction_receipt`` never recomputes it from the transformation BODY. So the
    lag declaration inside an emitted receipt can be edited in place (``strict_inequality: true``
    flipped to ``false``, a join key removed, a source path swapped) and the receipt still verifies
    with ``verified: true`` and no blocking findings. TESTS.py demonstrates exactly that edit.

    That is a Severity-C defect in a shared frozen artifact: it does not alter the primary target,
    the K0 structure, the inference structure, the candidate universe, the cutoff-valid feature set
    or the leakage status of anything, so it does not trip a stop condition. It DOES mean that
    "the receipt records the lag transformation" is weaker than "the receipt binds the lag
    transformation". This function supplies the missing recomputation, and the S1 acceptance
    criterion is discharged against THIS verifier, not against the unmodified one.
    """
    p = Path(path)
    rep = cr.verify_construction_receipt(p, **kw)
    body, read_findings = cr.read_construction_receipt(p)
    extra: list[dict] = list(read_findings)
    if body is not None:
        prod = dict(body.get("produced_frame_provenance") or {})
        t = prod.get("transformation")
        stored = prod.get("transformation_digest")
        recomputed = (None if t is None else "transformation:sha256=" + hashlib.sha256(
            cr._canonical(t).encode("utf-8")).hexdigest())
        rep["transformation_digest_recomputed"] = recomputed
        rep["transformation_digest_stored"] = stored
        if recomputed != stored:
            extra.append({"kind": "transformation_body_edited",
                          "stored": stored, "recomputed": recomputed,
                          "detail": "the transformation block does not digest to the value bound "
                                    "into the receipt. The lag declaration was edited after the "
                                    "receipt was emitted"})
    if extra:
        rep["blocking"] = list(rep.get("blocking") or []) + extra
        rep["verified"] = False
    rep["verified_by"] = "postgame_surrogate_guard.verify_guard_receipt"
    return rep


def _main() -> int:                                              # pragma: no cover - descriptive
    print("=" * 94)
    print("postgame_surrogate_guard — S1: current-game duration cannot silently enter a frame")
    print("=" * 94)
    print(f"schema                : {SCHEMA}")
    print(f"feature_gate.py sha256: {_sha256_file(PROGRAM / 'feature_gate.py')}")
    print(f"expected (frozen)     : {FEATURE_GATE_SHA256}")
    print(f"blocking kinds        : {len(BLOCKING)}")
    for k in sorted(BLOCKING):
        print(f"    {k}")
    print(f"lag kinds             : {', '.join(LAG_KINDS)}")
    return 0


if __name__ == "__main__":                                       # pragma: no cover
    raise SystemExit(_main())
