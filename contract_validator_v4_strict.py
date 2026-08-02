#!/usr/bin/env python3
"""contract_validator_v4_strict.py — accounting re-keyed onto the CANONICAL obligation key.

`contract_v2_strict/2` and `/3` are historical and are **not rewritten**, for the reason `/3`
gave when it declined to rewrite `/2`: their assertions were checked against them, and
tightening them retroactively would change what those checks meant. `/4` is added alongside.

**IT DOES NOT FIT, PREDICT OR SCORE.** It reads two frames, checks column contracts, counts
rows and compares hashes and timestamps. `prediction_coverage` here is an OBLIGATION-
COMPLETENESS RATIO — how many owed forecasts exist — and is emphatically not a statistical
coverage, an accuracy, or any comparison of a forecast against an outcome. Nothing in this
module touches an outcome value.

WHAT `/3` STILL LET THROUGH
---------------------------
`/3` inherited `/2`'s accounting, which is set-based on `row_uid`::

    required  = set(universe.loc[universe[req_col], "row_uid"])
    uncovered = required - set(pred.row_uid)
    if pred.row_uid.duplicated().any(): problems.append("... duplicate row_uid")

Under `prediction_contract_v3`'s team-blind `row_uid = pg_uid(player_id, game_id)` a player
traded mid-season shares one key across her two clubs' obligations for the head-to-head game.
28 real rows share 14 keys. Two consequences, and they point in OPPOSITE directions, so no
single threshold catches both:

* **one forecast falsely covers two obligations.** `required` is a SET, so two obligations
  collapse to one member. A single forecast row empties `uncovered`, and `/3` reports
  `n_required = 1`, `n_predicted = 1`, `prediction_coverage = 1.0`, `ok = True` — a perfect
  score for having answered half the question. (The historical `/2` validator counts
  `n_required` as ROWS, so it reports `0.5`, and still returns `ok = True` because its
  `uncovered` is set-based too. Two accounting systems disagreeing by a factor of two, both
  green, is itself the finding.)
* **two correct forecasts are rejected as duplicates.** An arm that does the right thing and
  emits one forecast per club emits two rows carrying the same team-blind key, and the
  duplicate check rejects the frame. The validator therefore punishes the correct behaviour
  and rewards the incorrect one.

WHAT `/4` CHANGES — AND ONLY THIS
----------------------------------
Every lineage and value check below the accounting section is `/3`'s, ported so the module
is self-contained and diffable. `/4` changes the accounting, and adds the preconditions that
make the accounting meaningful:

1. **The universe's key must BE a key.** If `row_uid` is not unique in the universe, `/4`
   returns `ok: False` and refuses to compute coverage at all, rather than computing it
   wrongly. This is the single check whose absence let `/3` report 100% completeness over
   half the obligations. It reports how many obligations the collision hides.
2. **The key must RE-DERIVE.** When the universe declares `obligation_key_id`, `/4`
   recomputes `cbs_obligation_key.row_uid(player_id, game_id, team_id)` and requires
   equality. A team-blind key that happens to be unique on today's rows — no trade in this
   fold — passes a uniqueness test while being the wrong key; it is caught here, before it
   is unique only by luck.
3. **Obligations are COUNTED, not set-membered.** `n_required` is the number of required
   universe ROWS and `n_required_keys` the number of distinct keys, and `/4` states that
   they must be equal. A divergence is the collision, named.
4. **The merge cannot fan out.** `pred` is joined to the universe with
   `validate="many_to_one"`, so a one-to-many join raises inside the fail-closed wrapper
   instead of silently multiplying rows.
5. **Exclusion is re-keyed too.** Excluded and predicted key sets must be disjoint and must
   both lie inside the universe. Under a non-unique key "this obligation was excluded" and
   "that obligation was predicted" could be the same key, which is not a statement anything
   can act on.

Fail-closed everywhere, as in `/2` and `/3`: a malformed frame returns `ok: False` with the
reason and never raises. A validator that raises on bad input is a validator that can be
bypassed by bad input.
"""

from __future__ import annotations

import traceback

import numpy as np
import pandas as pd

import cbs_obligation_key as obk
import contract_validator_v3_strict as _v3

VALIDATOR_ID = "contract_v4_strict/1"
SUPERSEDES = _v3.VALIDATOR_ID
OBLIGATION_KEY_ID = obk.OBLIGATION_KEY_ID

#: the canonical accounting key. Never `player_game_uid`, which is retained for linkage and
#: is NOT unique across obligations.
KEY_COL = "row_uid"
LEGACY_KEY_COL = "player_game_uid"
#: the columns the canonical key is derived from, in the registered field order
CANONICAL_SOURCE_COLS = tuple(obk.CANONICAL_KEY_FIELDS)

# --- inherited from `/3` BY REFERENCE, so the ported checks cannot drift ---
QUANTILE_COLS = _v3.QUANTILE_COLS
IDENTITY_COLS = _v3.IDENTITY_COLS
LINEAGE_COLS = _v3.LINEAGE_COLS
TARGET_RULES = _v3.TARGET_RULES
HEX64 = _v3.HEX64
MAX_FALLBACK_LEVEL = _v3.MAX_FALLBACK_LEVEL
_is_real_bool = _v3._is_real_bool

_MISSING = object()


# --------------------------------------------------------------------------
# the key preconditions -- new in /4
# --------------------------------------------------------------------------

def key_status(universe: pd.DataFrame, *, require_declared_key: bool = True,
               where: str = "universe") -> dict:
    """Is this frame's `row_uid` a usable accounting key?

    Separated out so the answer can be inspected on its own, and so a caller that only wants
    to know whether a frame is keyable does not have to construct a prediction frame to ask.
    """
    rec: dict = {"frame": where, "expected_key_id": OBLIGATION_KEY_ID,
                 "canonical_key": KEY_COL, "canonical_key_fields": list(CANONICAL_SOURCE_COLS),
                 "unique": None, "declared": None, "recomputes": None, "problems": []}
    if KEY_COL not in universe.columns:
        rec["problems"].append(f"{where} has no {KEY_COL!r} column; obligations cannot be "
                               f"counted")
        rec["ok"] = False
        return rec

    n_rows = int(len(universe))
    n_keys = int(universe[KEY_COL].nunique())
    n_dup_rows = int(universe[KEY_COL].duplicated(keep=False).sum())
    rec.update({"n_rows": n_rows, "n_distinct_keys": n_keys,
                "n_rows_sharing_a_key": n_dup_rows,
                "n_obligations_hidden_by_key_collision": n_rows - n_keys})
    rec["unique"] = n_dup_rows == 0
    if n_dup_rows:
        sample = sorted(universe.loc[universe[KEY_COL].duplicated(keep=False),
                                     KEY_COL].unique())[:5]
        rec["problems"].append(
            f"{where}: {KEY_COL} is NOT unique -- {n_dup_rows} rows share {n_rows - n_keys} "
            f"key(s), so {n_rows - n_keys} obligation(s) are invisible to any set-based "
            f"count. Coverage, exclusion and duplicate accounting are undefined under a "
            f"non-unique key and are NOT reported. Sample keys: {sample}")

    declared = set(str(x) for x in pd.unique(universe["obligation_key_id"].dropna())) \
        if "obligation_key_id" in universe.columns else set()
    rec["declared_key_ids"] = sorted(declared)
    rec["declared"] = declared == {OBLIGATION_KEY_ID}
    if not declared:
        rec["declared"] = None
        if require_declared_key:
            rec["problems"].append(
                f"{where} carries no obligation_key_id; the rule its key claims to follow is "
                f"unstated, so it cannot be checked. Pass require_declared_key=False only "
                f"for a frame whose key is deliberately not {OBLIGATION_KEY_ID}")
    elif declared != {OBLIGATION_KEY_ID}:
        rec["problems"].append(
            f"{where} declares obligation_key_id {sorted(declared)}, not "
            f"[{OBLIGATION_KEY_ID!r}]")
    else:
        missing = [c for c in CANONICAL_SOURCE_COLS if c not in universe.columns]
        if missing:
            rec["problems"].append(
                f"{where} declares {OBLIGATION_KEY_ID} but lacks {missing}; the key cannot "
                f"be re-derived, so a team-blind value in a column named {KEY_COL!r} is "
                f"indistinguishable from the canonical one")
        else:
            want = np.asarray([obk.row_uid(p, g, t) for p, g, t in
                               zip(universe["player_id"],
                                   universe["game_id"].astype(str),
                                   universe["team_id"])])
            n_bad = int((universe[KEY_COL].astype(str).to_numpy() != want).sum())
            rec["recomputes"] = n_bad == 0
            rec["n_rows_where_the_key_does_not_recompute"] = n_bad
            if n_bad:
                legacy = np.asarray([obk.player_game_uid(p, g) for p, g in
                                     zip(universe["player_id"],
                                         universe["game_id"].astype(str))])
                looks_legacy = int((universe[KEY_COL].astype(str).to_numpy()
                                    == legacy).sum())
                extra = (f"; {looks_legacy} of them hold the TEAM-BLIND "
                         f"player_game_uid instead" if looks_legacy else "")
                rec["n_rows_holding_the_team_blind_legacy_key"] = looks_legacy
                rec["problems"].append(
                    f"{where}: {n_bad} rows whose {KEY_COL} is not "
                    f"cbs_obligation_key.row_uid(player_id, game_id, team_id){extra}")

    if LEGACY_KEY_COL in universe.columns:
        rec["n_distinct_legacy_keys"] = int(universe[LEGACY_KEY_COL].nunique())
        rec["n_obligations_the_legacy_key_would_collapse"] = \
            n_rows - int(universe[LEGACY_KEY_COL].nunique())
    rec["ok"] = not rec["problems"]
    return rec


# --------------------------------------------------------------------------
# the validator
# --------------------------------------------------------------------------

def validate_strict_v4(pred: pd.DataFrame, universe: pd.DataFrame, target_key: str, *,
                       expected_arm_id=_MISSING, expected_fold_id=_MISSING,
                       expected_config_hash=_MISSING, expected_snapshot_hash=_MISSING,
                       require_universe_identity: bool = True,
                       require_declared_key: bool = True) -> dict:
    """`/3`'s checks, with obligation accounting re-keyed onto the canonical unique key."""
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

        # ---- /4 PRECONDITION: the accounting key must be a key ---------------
        keys = key_status(universe, require_declared_key=require_declared_key,
                          where="universe")
        # `row_uid` is in LINEAGE_COLS, so its presence on `pred` is already guaranteed by
        # the column check above; this reports the prediction frame's key health.
        pred_keys = key_status(pred, require_declared_key=False, where="predictions")
        if not keys["unique"]:
            # Refuse to account rather than account wrongly. Every count below -- coverage,
            # exclusion, duplicates -- is a statement about obligations, and under a
            # non-unique key the word "obligation" does not refer to anything.
            return {"ok": False, "validator": VALIDATOR_ID, "supersedes": SUPERSEDES,
                    "problems": keys["problems"] + pred_keys.get("problems", []),
                    "key_status": keys, "prediction_key_status": pred_keys,
                    "accounting_performed": False,
                    "why_no_accounting": ("the universe's obligation key is not unique; "
                                          "coverage over a key that names more than one "
                                          "obligation is not a coverage of anything")}
        problems += keys["problems"]
        problems += [p for p in pred_keys.get("problems", []) if "no row_uid" in p]

        # ---- the join, which cannot fan out ---------------------------------
        ucols = [KEY_COL, req_col, "fold_id", "forecast_cutoff"]
        j = pred.merge(universe[ucols], on=KEY_COL, how="left", suffixes=("", "__uni"),
                       validate="many_to_one")
        n_fanout = int(len(j) - len(pred))

        # ---- obligation accounting, COUNTED not set-membered -----------------
        req_mask = universe[req_col].astype(bool)
        required_rows = int(req_mask.sum())
        required_keys = set(universe.loc[req_mask, KEY_COL])
        if required_rows != len(required_keys):
            problems.append(
                f"{required_rows - len(required_keys)} required obligations share a key "
                f"with another required obligation")

        got_keys = set(pred[KEY_COL])
        unknown = got_keys - set(universe[KEY_COL])
        if j[req_col].isna().any():
            problems.append(f"{int(j[req_col].isna().sum())} predictions on row_uids absent "
                            f"from the universe ({len(unknown)} distinct)")
        uncovered = required_keys - got_keys
        if uncovered:
            problems.append(f"{len(uncovered)} REQUIRED obligations neither predicted nor "
                            f"excluded")
        dupmask = pred[KEY_COL].duplicated(keep=False)
        n_dup_rows = int(dupmask.sum())
        n_dup_keys = int(pred.loc[dupmask, KEY_COL].nunique())
        if n_dup_rows:
            problems.append(
                f"{n_dup_rows} prediction rows share {n_dup_keys} obligation key(s). Under "
                f"{OBLIGATION_KEY_ID} two forecasts for one player's two clubs are NOT "
                f"duplicates, so this is a genuine double-answer")

        excluded = pred[pred.exclusion_reason.notna()]
        predicted = pred[pred.exclusion_reason.isna()]
        both = set(predicted[KEY_COL]) & set(excluded[KEY_COL])
        if both:
            problems.append(f"{len(both)} obligations are both predicted and excluded")

        # ---- identity, on EVERY row (ported from /3) -------------------------
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

        # ---- excluded rows: null VALUES, intact LINEAGE (ported from /3) -----
        if len(excluded):
            for c in ["pred_point", "pred_sd"] + QUANTILE_COLS:
                if excluded[c].notna().any():
                    problems.append(f"excluded rows must have null {c}")
            for c in LINEAGE_COLS:
                if excluded[c].isna().any():
                    problems.append(f"excluded rows must retain {c}")

        # ---- LINEAGE CHECKS ON EVERY ROW (ported from /3, verbatim) ----------
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
            problems.append("n_prior_games must be a finite non-negative integer on every row")

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

        # ---- predicted rows: the value checks (ported from /3) ---------------
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

        if n_fanout:                                       # pragma: no cover - defensive
            problems.append(f"the universe join fanned out by {n_fanout} rows")

        return {
            "ok": not problems, "validator": VALIDATOR_ID, "supersedes": SUPERSEDES,
            "problems": problems,
            "obligation_key_id": OBLIGATION_KEY_ID,
            "key_status": keys, "prediction_key_status": pred_keys,
            "accounting_performed": True,
            "accounting_key": KEY_COL,
            "n_universe_rows": int(len(universe)),
            "n_required": required_rows,
            "n_required_keys": len(required_keys),
            "n_predicted": int(len(predicted)),
            "n_predicted_keys": int(predicted[KEY_COL].nunique()),
            "n_excluded": int(len(excluded)),
            "n_excluded_keys": int(excluded[KEY_COL].nunique()),
            "n_uncovered": len(uncovered),
            "n_duplicate_prediction_rows": n_dup_rows,
            "n_join_fanout_rows": n_fanout,
            "max_obligations_per_forecast": int(
                universe[universe[KEY_COL].isin(got_keys)].groupby(KEY_COL).size().max())
            if got_keys else 0,
            "prediction_coverage": (float(len(predicted) / required_rows)
                                    if required_rows else float("nan")),
            "coverage_semantics": ("fraction of OWED forecasts that exist. An obligation "
                                   "count, not an accuracy, not a statistical coverage, and "
                                   "never a comparison against an outcome"),
        }
    except Exception as exc:                       # fail closed, never raise
        return {"ok": False, "validator": VALIDATOR_ID,
                "problems": [f"validator raised {type(exc).__name__}: {exc}"],
                "traceback": traceback.format_exc(limit=3)}


def validate_arm_output_v4(pred: pd.DataFrame, universe: pd.DataFrame, target_key: str, *,
                           expected_arm_id, expected_fold_id,
                           expected_config_hash, expected_snapshot_hash,
                           require_declared_key: bool = True) -> dict:
    """The composed prediction gate: historical validator AND `/4`.

    `ok` requires BOTH, exactly as `/3` composed itself with the historical one, so a
    tightening in `/4` cannot be bypassed by satisfying only the older gate. The historical
    validator's own accounting is set-based and therefore wrong under a colliding key; it is
    kept in the conjunction because it can only make the verdict STRICTER, never looser, and
    its numbers are reported separately rather than merged.
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

    strict = validate_strict_v4(pred, universe, target_key,
                                expected_arm_id=expected_arm_id,
                                expected_fold_id=expected_fold_id,
                                expected_config_hash=expected_config_hash,
                                expected_snapshot_hash=expected_snapshot_hash,
                                require_declared_key=require_declared_key)
    receipt["strict"] = strict
    receipt["problems"] = ([f"historical: {p}" for p in hist.get("problems", [])]
                           + [f"strict: {p}" for p in strict.get("problems", [])])
    receipt["ok"] = bool(hist.get("ok")) and bool(strict.get("ok"))
    for k in ("n_required", "n_required_keys", "n_predicted", "n_excluded",
              "prediction_coverage", "key_status", "accounting_performed"):
        if k in strict:
            receipt[k] = strict[k]
    return receipt


def compare_v3_v4(pred: pd.DataFrame, universe: pd.DataFrame, target_key: str, **kw) -> dict:
    """Run `/3` and `/4` on the SAME frames and report where they disagree.

    Provided in the module rather than only in its test so the difference is reproducible by
    anyone holding the two frames, and so a future reader can check the claim in this
    docstring against the code that makes it.
    """
    v3_kw = {k: v for k, v in kw.items() if k != "require_declared_key"}
    v3 = _v3.validate_strict_v3(pred, universe, target_key, **v3_kw)
    v4 = validate_strict_v4(pred, universe, target_key, **kw)
    return {
        "v3": {k: v3.get(k) for k in ("ok", "problems", "n_required", "n_predicted",
                                      "n_excluded", "prediction_coverage")},
        "v4": {k: v4.get(k) for k in ("ok", "problems", "n_required", "n_required_keys",
                                      "n_predicted", "n_excluded", "prediction_coverage",
                                      "accounting_performed")},
        "verdicts_agree": bool(v3.get("ok")) == bool(v4.get("ok")),
        "v3_validator": _v3.VALIDATOR_ID, "v4_validator": VALIDATOR_ID,
    }
