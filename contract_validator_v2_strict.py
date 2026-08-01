#!/usr/bin/env python3
"""contract_validator_v2_strict.py — a STRICTER validator for the unchanged
`player_game_contract/2` row universe.

WHY A SECOND VALIDATOR
----------------------
`prediction_contract_v2.validate_predictions()` is historical and is **not
rewritten here** — other registered artifacts were checked against it, and
silently tightening it would retroactively change what those checks meant. But
it is weaker than its own documented contract: it never compares `fold_id` or
`forecast_cutoff` against the universe, never enforces target identity or
support, never validates hash format or expected hashes, and never type-checks
the fallback / cold-start / prior-count fields.

**Passing the historical validator is necessary but not sufficient.** This
module adds the missing checks as a separate, versioned artifact so both
verdicts are available and neither is disturbed.

The row universe is unchanged: same `row_uid`s, same
`prediction_required__<target>` / `outcome_scoreable__<target>` columns.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

VALIDATOR_ID = "contract_v2_strict/1"

QUANTILE_COLS = ["pred_q05", "pred_q25", "pred_q50", "pred_q75", "pred_q95"]

#: target -> (support_low, support_high, needs_sd, needs_quantiles)
TARGET_RULES = {
    "p_active":                    (0.0, 1.0, False, False),
    "e_minutes_given_active":      (0.0, 48.0, True, True),
    "attempts_usage":              (0.0, None, True, True),
    "player_scoring_distribution": (0.0, None, True, True),
    "team_game_distribution":      (1e-6, None, True, True),
}

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def validate_strict(pred: pd.DataFrame, universe: pd.DataFrame, target_key: str, *,
                    expected_fold_id: str | None = None,
                    expected_arm_id: str | None = None,
                    expected_config_hash: str | None = None,
                    expected_snapshot_hash: str | None = None,
                    require_hex_hashes: bool = True) -> dict:
    """Reject anything the historical validator would have let through."""
    problems: list[str] = []
    if target_key not in TARGET_RULES:
        return {"ok": False, "validator": VALIDATOR_ID,
                "problems": [f"unknown target_key {target_key!r}"]}
    low, high, needs_sd, needs_q = TARGET_RULES[target_key]

    req_col = f"prediction_required__{target_key}"
    if req_col not in universe.columns:
        return {"ok": False, "validator": VALIDATOR_ID,
                "problems": [f"universe lacks {req_col}"]}

    # ---- join to the universe; this is what the historical validator omits --
    ucols = ["row_uid", req_col]
    for c in ("fold_id", "forecast_cutoff"):
        if c in universe.columns:
            ucols.append(c)
    j = pred.merge(universe[ucols], on="row_uid", how="left", suffixes=("", "__uni"))

    if j[req_col].isna().any():
        problems.append(f"{int(j[req_col].isna().sum())} predictions on row_uids "
                        f"absent from the universe")

    required = set(universe.loc[universe[req_col], "row_uid"])
    missing = required - set(pred.row_uid)
    if missing:
        problems.append(f"{len(missing)} REQUIRED rows neither predicted nor excluded")
    if pred.row_uid.duplicated().any():
        problems.append(f"{int(pred.row_uid.duplicated().sum())} duplicate row_uid")

    # ---- exact target / arm / fold identity --------------------------------
    if not (pred.target_key == target_key).all():
        problems.append(f"target_key is not uniformly {target_key!r}")
    if expected_arm_id is not None and not (pred.arm_id == expected_arm_id).all():
        problems.append(f"arm_id is not uniformly {expected_arm_id!r}")
    if expected_fold_id is not None and not (pred.fold_id == expected_fold_id).all():
        problems.append(f"fold_id is not uniformly {expected_fold_id!r}")
    if "fold_id__uni" in j.columns:
        bad = int((j.fold_id.astype(str) != j.fold_id__uni.astype(str)).sum())
        if bad:
            problems.append(f"{bad} rows whose fold_id disagrees with the universe")

    # ---- forecast_cutoff must equal the universe's, not merely parse --------
    if "forecast_cutoff__uni" in j.columns:
        a = pd.to_datetime(j.forecast_cutoff, utc=True, errors="coerce")
        b = pd.to_datetime(j.forecast_cutoff__uni, utc=True, errors="coerce")
        bad = int((a != b).sum())
        if bad:
            problems.append(f"{bad} rows whose forecast_cutoff disagrees with the universe")

    predicted = pred[pred.exclusion_reason.isna()]

    # ---- support ------------------------------------------------------------
    if len(predicted):
        pt = pd.to_numeric(predicted.pred_point, errors="coerce")
        if pt.isna().any():
            problems.append("null or non-numeric pred_point on a predicted row")
        if low is not None and (pt < low).any():
            problems.append(f"{int((pt < low).sum())} pred_point below the support floor {low}")
        if high is not None and (pt > high).any():
            problems.append(f"{int((pt > high).sum())} pred_point above the support ceiling {high}")

        # ---- sd -------------------------------------------------------------
        sd = pd.to_numeric(predicted.pred_sd, errors="coerce")
        if needs_sd:
            if not np.isfinite(sd).all() or (sd <= 0).any():
                problems.append("pred_sd must be finite and strictly positive")
        elif sd.notna().any():
            problems.append("pred_sd must be null for this target")

        # ---- quantiles ------------------------------------------------------
        if needs_q:
            q = predicted[QUANTILE_COLS].apply(pd.to_numeric, errors="coerce")
            if q.isna().any().any():
                problems.append("quantiles required and must be non-null")
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

        # ---- booleans and prior counts --------------------------------------
        for c in ("is_fallback", "is_cold_start"):
            vals = set(pd.unique(predicted[c].dropna()))
            if not vals <= {True, False, np.True_, np.False_, 0, 1}:
                problems.append(f"{c} must be boolean, got {sorted(map(str, vals))[:4]}")
            if predicted[c].isna().any():
                problems.append(f"{c} must not be null")
        npg = pd.to_numeric(predicted.n_prior_games, errors="coerce")
        if npg.isna().any() or (npg < 0).any() or (npg % 1 != 0).any():
            problems.append("n_prior_games must be a non-negative integer")

        # ---- hashes ----------------------------------------------------------
        for h, exp in (("config_hash", expected_config_hash),
                       ("data_snapshot_hash", expected_snapshot_hash),
                       ("model_hash", None)):
            col = predicted[h]
            if col.isna().any():
                problems.append(f"{h} missing on some predicted rows")
                continue
            if require_hex_hashes and not col.astype(str).str.match(HEX64).all():
                problems.append(f"{h} is not a 64-hex digest on every row")
            if exp is not None and not (col.astype(str) == exp).all():
                problems.append(f"{h} does not equal the expected value")

        # ---- strict feature-as-of --------------------------------------------
        fa = pd.to_datetime(predicted.feature_asof, utc=True, errors="coerce")
        fc = pd.to_datetime(predicted.forecast_cutoff, utc=True, errors="coerce")
        if fa.isna().any() or fc.isna().any():
            problems.append("unparseable feature_asof or forecast_cutoff")
        else:
            bad = int((fa >= fc).sum())
            if bad:
                problems.append(f"{bad} rows where feature_asof >= forecast_cutoff")

    n_req = len(required)
    return {
        "ok": not problems, "validator": VALIDATOR_ID, "problems": problems,
        "n_required": n_req, "n_predicted": int(len(predicted)),
        "n_excluded": int(pred.exclusion_reason.notna().sum()),
        "prediction_coverage": float(len(predicted) / n_req) if n_req else float("nan"),
    }
