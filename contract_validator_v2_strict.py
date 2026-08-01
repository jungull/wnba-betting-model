#!/usr/bin/env python3
"""contract_validator_v2_strict.py — a STRICTER validator, plus a composed gate.

`prediction_contract_v2.validate_predictions()` is historical and is **not
rewritten** here: other registered artifacts were checked against it, and
tightening it retroactively would change what those checks meant. But it is
weaker than its own documented contract — it never compares `fold_id` or
`forecast_cutoff` to the universe, never enforces target identity or support,
never validates hash format, and never type-checks the flag fields.

**Passing the historical validator is necessary but not sufficient.**
`validate_arm_output` composes both and returns a single fail-closed receipt.

Fail-closed everywhere: a malformed frame returns `ok: False` with the reason,
and never raises. A validator that raises on bad input is a validator that can
be bypassed by bad input.
"""

from __future__ import annotations

import re
import traceback

import numpy as np
import pandas as pd

VALIDATOR_ID = "contract_v2_strict/2"

QUANTILE_COLS = ["pred_q05", "pred_q25", "pred_q50", "pred_q75", "pred_q95"]
IDENTITY_COLS = ["row_uid", "target_key", "arm_id", "fold_id", "forecast_cutoff",
                 "model_hash", "config_hash", "data_snapshot_hash"]

#: target -> (support_low, support_high, needs_sd, needs_quantiles)
TARGET_RULES = {
    "p_active":                    (0.0, 1.0, False, False),
    "e_minutes_given_active":      (0.0, 48.0, True, True),
    "attempts_usage":              (0.0, None, True, True),
    "player_scoring_distribution": (0.0, None, True, True),
    "team_game_distribution":      (1e-6, None, True, True),
}

HEX64 = re.compile(r"^[0-9a-f]{64}$")

_MISSING = object()


def _is_real_bool(series: pd.Series) -> bool:
    """True only for genuine booleans.

    Numeric 0/1 — including floats — is NOT a boolean. Accepting it lets a
    column that is really a count masquerade as a flag.
    """
    if series.dtype == bool:
        return True
    return all(isinstance(v, (bool, np.bool_)) for v in series.tolist())


def validate_strict(pred: pd.DataFrame, universe: pd.DataFrame, target_key: str, *,
                    expected_arm_id=_MISSING, expected_fold_id=_MISSING,
                    expected_config_hash=_MISSING, expected_snapshot_hash=_MISSING,
                    require_universe_identity: bool = True) -> dict:
    """Reject anything the historical validator lets through.

    The four `expected_*` identities are **required**. They previously defaulted
    to `None`, which made identity enforcement opt-in — a production gate must
    not be able to forget to bind the arm it is checking.
    """
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

        missing_cols = [c for c in IDENTITY_COLS + QUANTILE_COLS +
                        ["pred_point", "pred_sd", "is_fallback", "is_cold_start",
                         "n_prior_games", "feature_asof", "exclusion_reason"]
                        if c not in pred.columns]
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
        j = pred.merge(universe[ucols], on="row_uid", how="left",
                       suffixes=("", "__uni"))

        if j[req_col].isna().any():
            problems.append(f"{int(j[req_col].isna().sum())} predictions on row_uids "
                            f"absent from the universe")
        required = set(universe.loc[universe[req_col].astype(bool), "row_uid"])
        uncovered = required - set(pred.row_uid)
        if uncovered:
            problems.append(f"{len(uncovered)} REQUIRED rows neither predicted nor excluded")
        if pred.row_uid.duplicated().any():
            problems.append(f"{int(pred.row_uid.duplicated().sum())} duplicate row_uid")

        # ---- identity, on EVERY row including excluded ones -----------------
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

        # ---- excluded rows: null values, intact lineage ---------------------
        if len(excluded):
            for c in ["pred_point", "pred_sd"] + QUANTILE_COLS:
                if excluded[c].notna().any():
                    problems.append(f"excluded rows must have null {c}")
            for c in IDENTITY_COLS:
                if excluded[c].isna().any():
                    problems.append(f"excluded rows must retain {c}")

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

            # ---- sd ----------------------------------------------------------
            raw_sd = predicted.pred_sd
            if needs_sd:
                sd = pd.to_numeric(raw_sd, errors="coerce")
                if sd.isna().any() or not np.isfinite(sd).all() or (sd <= 0).any():
                    problems.append("pred_sd must be finite and strictly positive")
            else:
                # must be ACTUALLY null -- not merely non-numeric text that
                # to_numeric would quietly coerce to NaN
                if raw_sd.notna().any():
                    problems.append("pred_sd must be null for this target")

            # ---- quantiles ---------------------------------------------------
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
            else:
                if predicted[QUANTILE_COLS].notna().any().any():
                    problems.append("quantiles must be null for this target")

            # ---- genuine booleans, integer prior counts ----------------------
            for c in ("is_fallback", "is_cold_start"):
                if predicted[c].isna().any():
                    problems.append(f"{c} must not be null")
                elif not _is_real_bool(predicted[c]):
                    problems.append(f"{c} must be a real boolean, not numeric 0/1")
            npg = pd.to_numeric(predicted.n_prior_games, errors="coerce")
            if npg.isna().any() or not np.isfinite(npg).all() \
                    or (npg < 0).any() or (npg % 1 != 0).any():
                problems.append("n_prior_games must be a finite non-negative integer")

            # ---- hashes -------------------------------------------------------
            for h, exp in (("config_hash", expected_config_hash),
                           ("data_snapshot_hash", expected_snapshot_hash),
                           ("model_hash", None)):
                col = predicted[h]
                if col.isna().any():
                    problems.append(f"{h} missing on some predicted rows")
                    continue
                if not col.astype(str).str.match(HEX64).all():
                    problems.append(f"{h} is not a 64-hex digest on every row")
                if exp is not None and not (col.astype(str) == exp).all():
                    problems.append(f"{h} does not equal the expected value")

            # ---- strict feature-as-of ------------------------------------------
            fa = pd.to_datetime(predicted.feature_asof, utc=True, errors="coerce")
            fc = pd.to_datetime(predicted.forecast_cutoff, utc=True, errors="coerce")
            if fa.isna().any() or fc.isna().any():
                problems.append("unparseable feature_asof or forecast_cutoff")
            elif (fa >= fc).any():
                problems.append(f"{int((fa >= fc).sum())} rows where "
                                f"feature_asof >= forecast_cutoff")

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


def validate_arm_output(pred: pd.DataFrame, universe: pd.DataFrame, target_key: str, *,
                        expected_arm_id, expected_fold_id,
                        expected_config_hash, expected_snapshot_hash) -> dict:
    """The composed gate: historical validator AND strict arm validator.

    Returns one fail-closed receipt. `ok` requires BOTH to pass, so tightening
    the strict validator can never be bypassed by satisfying only the historical
    one, and a malformed frame yields a verdict rather than a traceback.
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

    strict = validate_strict(pred, universe, target_key,
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
