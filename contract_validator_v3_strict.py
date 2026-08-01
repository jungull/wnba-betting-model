#!/usr/bin/env python3
"""contract_validator_v3_strict.py — every check on EVERY row, not only predicted ones.

`contract_v2_strict/2` is historical and is **not rewritten** here, for the same
reason it did not rewrite the v1 validator: `contract_baseline_suite_v6` and its
104 assertions were checked against `/2`, and tightening it retroactively would
change what those checks meant. This module adds `/3` alongside it.

WHAT `/2` STILL LET THROUGH
--------------------------
`/2` scoped its hash-format, feature-as-of, boolean and prior-count checks to
``pred[pred.exclusion_reason.isna()]``. An excluded row therefore had to keep its
identity columns **non-null** and nothing else: it could carry a `config_hash`
that was not 64 hex, a `feature_asof` at or after its own `forecast_cutoff`, a
numeric `0`/`1` where a boolean belongs, or a negative `n_prior_games`. Exclusion
is supposed to remove a row's *values*, never its *lineage* — so every lineage
check must apply to it too. An arm that can launder a bad row by excluding it has
an exclusion mechanism that doubles as a bypass.

`/3` also requires the two columns that make a fallback auditable rather than a
single opaque boolean:

* ``fallback_level`` — an integer 0-4, with ``is_fallback == (fallback_level > 0)``
  enforced, so the flag and the ladder cannot disagree;
* ``component_id`` — which component actually produced the emitted number, so a
  declared-constant fallback and a fitted prediction are distinguishable after
  the fact rather than only inside the runner's diagnostics.

Fail-closed everywhere, as in `/2`: a malformed frame returns ``ok: False`` with
the reason and never raises. A validator that raises on bad input is a validator
that can be bypassed by bad input.
"""

from __future__ import annotations

import re
import traceback

import numpy as np
import pandas as pd

VALIDATOR_ID = "contract_v2_strict/3"

QUANTILE_COLS = ["pred_q05", "pred_q25", "pred_q50", "pred_q75", "pred_q95"]
IDENTITY_COLS = ["row_uid", "target_key", "arm_id", "fold_id", "forecast_cutoff",
                 "model_hash", "config_hash", "data_snapshot_hash"]
#: lineage columns that must be intact on EVERY row, excluded rows included
LINEAGE_COLS = IDENTITY_COLS + ["feature_asof", "is_fallback", "is_cold_start",
                                "n_prior_games", "fallback_level", "component_id"]

#: target -> (support_low, support_high, needs_sd, needs_quantiles)
TARGET_RULES = {
    "p_active":                    (0.0, 1.0, False, False),
    "e_minutes_given_active":      (0.0, 48.0, True, True),
    "attempts_usage":              (0.0, None, True, True),
    "player_scoring_distribution": (0.0, None, True, True),
    "team_game_distribution":      (1e-6, None, True, True),
}

HEX64 = re.compile(r"^[0-9a-f]{64}$")

#: the registered fallback ladder; see cbs_v7.FALLBACK_LADDER
MAX_FALLBACK_LEVEL = 4

_MISSING = object()


def _is_real_bool(series: pd.Series) -> bool:
    """True only for genuine booleans.

    Numeric 0/1 — including floats — is NOT a boolean. Accepting it lets a column
    that is really a count masquerade as a flag.
    """
    if series.dtype == bool:
        return True
    return all(isinstance(v, (bool, np.bool_)) for v in series.tolist())


def validate_strict_v3(pred: pd.DataFrame, universe: pd.DataFrame, target_key: str, *,
                       expected_arm_id=_MISSING, expected_fold_id=_MISSING,
                       expected_config_hash=_MISSING, expected_snapshot_hash=_MISSING,
                       require_universe_identity: bool = True) -> dict:
    """`/2`'s checks, with every lineage check applied to EVERY row."""
    problems: list[str] = []
    try:
        for name, val in (("expected_arm_id", expected_arm_id),
                          ("expected_fold_id", expected_fold_id),
                          ("expected_config_hash", expected_config_hash),
                          ("expected_snapshot_hash", expected_snapshot_hash)):
            if val is _MISSING:
                problems.append(f"{name} was not supplied; identity binding is mandatory")
        if problems:
            return {"ok": False, "validator": VALIDATOR_ID, "problems": problems}

        if target_key not in TARGET_RULES:
            return {"ok": False, "validator": VALIDATOR_ID,
                    "problems": [f"unknown target_key {target_key!r}"]}
        low, high, needs_sd, needs_q = TARGET_RULES[target_key]

        required_cols = (LINEAGE_COLS + QUANTILE_COLS
                         + ["pred_point", "pred_sd", "exclusion_reason"])
        missing_cols = [c for c in required_cols if c not in pred.columns]
        if missing_cols:
            return {"ok": False, "validator": VALIDATOR_ID,
                    "problems": [f"missing required columns: {missing_cols}"]}

        req_col = f"prediction_required__{target_key}"
        if req_col not in universe.columns:
            return {"ok": False, "validator": VALIDATOR_ID,
                    "problems": [f"universe lacks {req_col}"]}
        if require_universe_identity:
            for c in ("fold_id", "forecast_cutoff"):
                if c not in universe.columns:
                    problems.append(f"universe lacks {c!r}; identity cannot be checked")
            if problems:
                return {"ok": False, "validator": VALIDATOR_ID, "problems": problems}

        ucols = ["row_uid", req_col, "fold_id", "forecast_cutoff"]
        j = pred.merge(universe[ucols], on="row_uid", how="left", suffixes=("", "__uni"))

        if j[req_col].isna().any():
            problems.append(f"{int(j[req_col].isna().sum())} predictions on row_uids "
                            f"absent from the universe")
        required = set(universe.loc[universe[req_col].astype(bool), "row_uid"])
        uncovered = required - set(pred.row_uid)
        if uncovered:
            problems.append(f"{len(uncovered)} REQUIRED rows neither predicted nor excluded")
        if pred.row_uid.duplicated().any():
            problems.append(f"{int(pred.row_uid.duplicated().sum())} duplicate row_uid")

        # ---- identity, on EVERY row -----------------------------------------
        if not (pred.target_key == target_key).all():
            problems.append(f"target_key is not uniformly {target_key!r}")
        if not (pred.arm_id == expected_arm_id).all():
            problems.append(f"arm_id is not uniformly {expected_arm_id!r}")
        if not (pred.fold_id == expected_fold_id).all():
            problems.append(f"fold_id is not uniformly {expected_fold_id!r}")
        bad = int((j.fold_id.astype(str) != j.fold_id__uni.astype(str)).sum())
        if bad:
            problems.append(f"{bad} rows whose fold_id disagrees with the universe")
        a = pd.to_datetime(j.forecast_cutoff, utc=True, errors="coerce")
        b = pd.to_datetime(j.forecast_cutoff__uni, utc=True, errors="coerce")
        if a.isna().any() or b.isna().any():
            problems.append("unparseable forecast_cutoff on predictions or universe")
        bad = int((a != b).sum())
        if bad:
            problems.append(f"{bad} rows whose forecast_cutoff disagrees with the universe")

        excluded = pred[pred.exclusion_reason.notna()]
        predicted = pred[pred.exclusion_reason.isna()]

        # ---- excluded rows: null VALUES, intact LINEAGE ---------------------
        if len(excluded):
            for c in ["pred_point", "pred_sd"] + QUANTILE_COLS:
                if excluded[c].notna().any():
                    problems.append(f"excluded rows must have null {c}")
            for c in LINEAGE_COLS:
                if excluded[c].isna().any():
                    problems.append(f"excluded rows must retain {c}")

        # ---- LINEAGE CHECKS ON EVERY ROW -------------------------------------
        # /2 scoped these to predicted rows, so an excluded row could carry a
        # malformed hash, an as-of at or after its own cutoff, a numeric flag or
        # a negative prior count and still pass. Exclusion removes values, never
        # lineage.
        for h, exp in (("config_hash", expected_config_hash),
                       ("data_snapshot_hash", expected_snapshot_hash),
                       ("model_hash", None)):
            col = pred[h]
            if col.isna().any():
                problems.append(f"{h} missing on some rows")
                continue
            if not col.astype(str).str.match(HEX64).all():
                problems.append(f"{h} is not a 64-hex digest on every row")
            if exp is not None and not (col.astype(str) == exp).all():
                problems.append(f"{h} does not equal the expected value")

        fa = pd.to_datetime(pred.feature_asof, utc=True, errors="coerce")
        fc = pd.to_datetime(pred.forecast_cutoff, utc=True, errors="coerce")
        if fa.isna().any() or fc.isna().any():
            problems.append("unparseable feature_asof or forecast_cutoff on some row")
        elif (fa >= fc).any():
            problems.append(f"{int((fa >= fc).sum())} rows where "
                            f"feature_asof >= forecast_cutoff")

        for c in ("is_fallback", "is_cold_start"):
            if pred[c].isna().any():
                problems.append(f"{c} must not be null on any row")
            elif not _is_real_bool(pred[c]):
                problems.append(f"{c} must be a real boolean, not numeric 0/1")

        npg = pd.to_numeric(pred.n_prior_games, errors="coerce")
        if npg.isna().any() or not np.isfinite(npg).all() \
                or (npg < 0).any() or (npg % 1 != 0).any():
            problems.append("n_prior_games must be a finite non-negative integer "
                            "on every row")

        # ---- the fallback ladder must agree with the flag --------------------
        lvl = pd.to_numeric(pred.fallback_level, errors="coerce")
        if lvl.isna().any() or not np.isfinite(lvl).all() or (lvl % 1 != 0).any():
            problems.append("fallback_level must be a finite integer on every row")
        elif (lvl < 0).any() or (lvl > MAX_FALLBACK_LEVEL).any():
            problems.append(f"fallback_level must lie in 0..{MAX_FALLBACK_LEVEL}")
        elif not pred["is_fallback"].isna().any() and _is_real_bool(pred["is_fallback"]):
            disagree = int((pred["is_fallback"].astype(bool) != (lvl > 0)).sum())
            if disagree:
                problems.append(f"{disagree} rows where is_fallback disagrees with "
                                f"fallback_level > 0")

        if pred["component_id"].isna().any():
            problems.append("component_id must name the producing component on every row")

        # ---- predicted rows: the value checks --------------------------------
        if len(predicted):
            pt = pd.to_numeric(predicted.pred_point, errors="coerce")
            if pt.isna().any():
                problems.append("null or non-numeric pred_point on a predicted row")
            elif not np.isfinite(pt).all():
                problems.append("pred_point must be FINITE (no inf/-inf)")
            else:
                if low is not None and (pt < low).any():
                    problems.append(f"pred_point below the support floor {low}")
                if high is not None and (pt > high).any():
                    problems.append(f"pred_point above the support ceiling {high}")

            raw_sd = predicted.pred_sd
            if needs_sd:
                sd = pd.to_numeric(raw_sd, errors="coerce")
                if sd.isna().any() or not np.isfinite(sd).all() or (sd <= 0).any():
                    problems.append("pred_sd must be finite and strictly positive")
            elif raw_sd.notna().any():
                # must be ACTUALLY null -- not merely non-numeric text that
                # to_numeric would quietly coerce to NaN
                problems.append("pred_sd must be null for this target")

            if needs_q:
                q = predicted[QUANTILE_COLS].apply(pd.to_numeric, errors="coerce")
                if q.isna().any().any():
                    problems.append("quantiles required and must be non-null numerics")
                elif not np.isfinite(q.to_numpy()).all():
                    problems.append("quantiles must be FINITE (no inf/-inf)")
                else:
                    if (np.diff(q.to_numpy(), axis=1) < -1e-12).any():
                        problems.append("quantiles are not monotone non-decreasing")
                    if low is not None and (q.to_numpy() < low - 1e-12).any():
                        problems.append("a quantile falls below the support floor")
                    if high is not None and (q.to_numpy() > high + 1e-12).any():
                        problems.append("a quantile exceeds the support ceiling")
            elif predicted[QUANTILE_COLS].notna().any().any():
                problems.append("quantiles must be null for this target")

        n_req = len(required)
        return {
            "ok": not problems, "validator": VALIDATOR_ID, "problems": problems,
            "n_required": n_req, "n_predicted": int(len(predicted)),
            "n_excluded": int(len(excluded)),
            "prediction_coverage": float(len(predicted) / n_req) if n_req else float("nan"),
        }
    except Exception as exc:                       # fail closed, never raise
        return {"ok": False, "validator": VALIDATOR_ID,
                "problems": [f"validator raised {type(exc).__name__}: {exc}"],
                "traceback": traceback.format_exc(limit=3)}


def validate_arm_output_v3(pred: pd.DataFrame, universe: pd.DataFrame, target_key: str, *,
                           expected_arm_id, expected_fold_id,
                           expected_config_hash, expected_snapshot_hash) -> dict:
    """The composed prediction gate: historical validator AND `/3`.

    `ok` requires BOTH, so tightening `/3` can never be bypassed by satisfying
    only the historical one, and a malformed frame yields a verdict rather than
    a traceback.
    """
    receipt = {"ok": False, "gate": f"historical+{VALIDATOR_ID}",
               "target_key": target_key, "problems": []}
    try:
        from prediction_contract_v2 import validate_predictions
        hist = validate_predictions(pred, universe, target_key)
    except Exception as exc:
        hist = {"ok": False, "problems": [f"historical validator raised "
                                          f"{type(exc).__name__}: {exc}"]}
    receipt["historical"] = hist

    strict = validate_strict_v3(pred, universe, target_key,
                                expected_arm_id=expected_arm_id,
                                expected_fold_id=expected_fold_id,
                                expected_config_hash=expected_config_hash,
                                expected_snapshot_hash=expected_snapshot_hash)
    receipt["strict"] = strict
    receipt["problems"] = ([f"historical: {p}" for p in hist.get("problems", [])]
                           + [f"strict: {p}" for p in strict.get("problems", [])])
    receipt["ok"] = bool(hist.get("ok")) and bool(strict.get("ok"))
    for k in ("n_required", "n_predicted", "n_excluded", "prediction_coverage"):
        if k in strict:
            receipt[k] = strict[k]
    if "scoreable_coverage" in hist:
        receipt["scoreable_coverage"] = hist["scoreable_coverage"]
    return receipt
