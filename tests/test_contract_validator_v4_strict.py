#!/usr/bin/env python
"""test_contract_validator_v4_strict.py — the accounting, re-keyed, shown against `/3`.

The central section runs the OLD validator (`contract_validator_v3_strict`) and the NEW one
(`contract_validator_v4_strict`) over the SAME frames, side by side, and asserts the exact
verdicts each returns. Both are the real, imported functions; nothing here is mocked.

The colliding obligation pair is not invented. It is lifted from the registered artifacts:
player 203824 in game 1022400175 owes a forecast to BOTH 1611661320 and 1611661321, and
`experiments/prediction_contract_v3/player_game.parquet` really does give those two rows one
`row_uid`. The fixture is those two real rows, keyed the two ways.

  V1  the key precondition, on the REAL v3 and v4 artifacts
  V2  OLD vs NEW, six scenarios, verdict by verdict
  V3  exclusion and duplicate accounting, re-keyed
  V4  every lineage check `/3` makes, `/4` still makes -- ported, not weakened
  V5  fail-closed: a malformed frame yields a verdict, never a traceback
  V6  the composed gate
  Z7  ZERO fits, predictions, scores or evaluations

The `pred_point` values below are CONSTANTS chosen to satisfy the schema. No model produces
them, no outcome is read, and nothing here is scored, evaluated or compared to truth. The
validator's `prediction_coverage` is an obligation-completeness count, not an accuracy.

Run as a script (this repository has no pytest installed):

    python tests/test_contract_validator_v4_strict.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cbs_obligation_key as obk                          # noqa: E402
import contract_validator_v3_strict as v3                 # noqa: E402
import contract_validator_v4_strict as v4                 # noqa: E402
from prediction_contract_v2 import validate_predictions   # noqa: E402

PASSED = 0
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")
        print(f"  FAIL  {name}  {detail}")


def has(rec: dict, needle: str) -> bool:
    return any(needle in p for p in rec.get("problems", []))


TARGET = "p_active"
FOLD = "season:2024"
ARM = "arm_probe"
CUT = pd.Timestamp("2024-08-01T18:00:00Z")
ASOF = pd.Timestamp("2024-08-01T12:00:00Z")
#: 64 lowercase hex characters each -- the shape the validators require
H = {"config_hash": "c" * 64, "data_snapshot_hash": "d" * 64, "model_hash": "ab" * 32}
BIND = dict(expected_arm_id=ARM, expected_fold_id=FOLD,
            expected_config_hash=H["config_hash"],
            expected_snapshot_hash=H["data_snapshot_hash"])

# the real collision, from experiments/prediction_contract_v3/player_game.parquet
PID, GID = 203824, "1022400175"
OLD_TEAM, NEW_TEAM = 1611661321, 1611661320       # she appeared for 1611661320


def universe(rows, *, keying: str, declare_key: bool = True) -> pd.DataFrame:
    """`rows` is [(player_id, game_id, team_id), ...].

    `keying="canonical"` uses `cbs_obligation_key.row_uid`; `keying="team_blind"` uses the
    v3 key, `pg_uid(player_id, game_id)`, which is what the registered v3 artifact holds.
    """
    u = pd.DataFrame(rows, columns=["player_id", "game_id", "team_id"])
    u["row_uid"] = [obk.row_uid(p, g, t) if keying == "canonical"
                    else obk.player_game_uid(p, g)
                    for p, g, t in rows]
    u["player_game_uid"] = [obk.player_game_uid(p, g) for p, g, _ in rows]
    if declare_key:
        u["obligation_key_id"] = obk.OBLIGATION_KEY_ID
    u["fold_id"] = FOLD
    u["forecast_cutoff"] = CUT
    u[f"prediction_required__{TARGET}"] = True
    u[f"outcome_scoreable__{TARGET}"] = True
    return u


def predictions(uids, *, excluded=(), **over) -> pd.DataFrame:
    """A schema-valid prediction frame over `uids`. The numbers are CONSTANTS."""
    p = pd.DataFrame({"row_uid": list(uids)})
    p["target_key"] = TARGET
    p["arm_id"] = ARM
    p["fold_id"] = FOLD
    p["forecast_cutoff"] = CUT
    p["pred_point"] = 0.5
    p["pred_sd"] = None
    for q in v4.QUANTILE_COLS:
        p[q] = None
    p["is_fallback"] = False
    p["is_cold_start"] = False
    p["n_prior_games"] = 3
    p["feature_asof"] = ASOF
    for k, val in H.items():
        p[k] = val
    p["exclusion_reason"] = [("candidate_withdrawn" if u in set(excluded) else None)
                             for u in uids]
    p["fallback_level"] = 0
    p["component_id"] = "probe"
    p.loc[p.exclusion_reason.notna(), ["pred_point"]] = None
    for k, val in over.items():
        p[k] = val
    return p


# ==========================================================================
# V1 -- the key precondition, on the REAL artifacts
# ==========================================================================
print("V1  the key precondition, measured on the registered artifacts")

V4_PG = ROOT / "experiments" / "prediction_contract_v4" / "player_game.parquet"
V3_PG = ROOT / "experiments" / "prediction_contract_v3" / "player_game.parquet"
check("V1 the registered v3 and v4 contracts are both present",
      V3_PG.exists() and V4_PG.exists())

_v4u = pd.read_parquet(V4_PG, columns=["row_uid", "player_game_uid", "obligation_key_id",
                                       "player_id", "team_id", "game_id", "season"])
_v3u = pd.read_parquet(V3_PG, columns=["row_uid", "player_id", "team_id", "game_id",
                                       "season"])

ks4 = v4.key_status(_v4u, where="v4 contract")
check("V1 the v4 contract's key is unique", ks4["unique"] is True)
check("V1 the v4 contract's key re-derives from (player_id, game_id, team_id)",
      ks4["recomputes"] is True)
check("V1 the v4 contract declares the key rule it follows", ks4["declared"] is True)
check("V1 the v4 contract passes the key precondition outright", ks4["ok"] is True,
      str(ks4["problems"]))
check("V1 the legacy key would collapse 14 of the v4 contract's obligations",
      ks4["n_obligations_the_legacy_key_would_collapse"] == 14,
      str(ks4["n_obligations_the_legacy_key_would_collapse"]))

ks3 = v4.key_status(_v3u, where="v3 contract", require_declared_key=False)
check("V1 the v3 contract's key is NOT unique -- 28 rows share 14 keys",
      ks3["unique"] is False and ks3["n_rows_sharing_a_key"] == 28
      and ks3["n_obligations_hidden_by_key_collision"] == 14,
      f"{ks3['n_rows_sharing_a_key']} / {ks3['n_obligations_hidden_by_key_collision']}")
check("V1 /4 names what the collision costs: 14 obligations invisible to a set-based count",
      has(ks3, "14 obligation(s) are invisible"), str(ks3["problems"]))
check("V1 the v3 contract declares no key rule at all", ks3["declared"] is None)
_v3_2024 = _v3u[_v3u.season == 2024]
check("V1 the collision is present in 2024 alone, so a single-fold gate cannot dodge it",
      int(_v3_2024.row_uid.duplicated(keep=False).sum()) == 8,
      str(int(_v3_2024.row_uid.duplicated(keep=False).sum())))

# a key that is unique BY LUCK -- no trade in this fold -- but is still the wrong rule
_lucky = _v4u[_v4u.season == 2024].head(50).copy()
_lucky["row_uid"] = _lucky["player_game_uid"]
ksl = v4.key_status(_lucky, where="team-blind but unique")
check("V1 a team-blind key that happens to be unique still fails: it does not re-derive",
      ksl["unique"] is True and ksl["recomputes"] is False and ksl["ok"] is False)
check("V1   ... and /4 says exactly which wrong key it is holding",
      ksl["n_rows_holding_the_team_blind_legacy_key"] == 50, str(ksl["problems"]))


# ==========================================================================
# V2 -- OLD vs NEW, side by side, on the real colliding pair
# ==========================================================================
print("V2  the old validator and the new one, on the same frames")

ROWS = [(PID, GID, NEW_TEAM), (PID, GID, OLD_TEAM)]
U_BLIND = universe(ROWS, keying="team_blind")
U_CANON = universe(ROWS, keying="canonical")
K_NEW, K_OLD = obk.row_uid(PID, GID, NEW_TEAM), obk.row_uid(PID, GID, OLD_TEAM)
K_BLIND = obk.player_game_uid(PID, GID)

check("V2 the fixture really is two obligations under one team-blind key",
      len(U_BLIND) == 2 and U_BLIND.row_uid.nunique() == 1 and K_NEW != K_OLD)

# --- scenario A: ONE forecast against TWO team-blind obligations ----------
A3 = v3.validate_strict_v3(predictions([K_BLIND]), U_BLIND, TARGET, **BIND)
A4 = v4.validate_strict_v4(predictions([K_BLIND]), U_BLIND, TARGET, **BIND)
AH = validate_predictions(predictions([K_BLIND]), U_BLIND, TARGET)
print(f"    A  one forecast, two obligations (team-blind key)")
print(f"       /3 ok={A3['ok']}  n_required={A3['n_required']}  "
      f"coverage={A3['prediction_coverage']}")
print(f"       /4 ok={A4['ok']}  accounting_performed={A4['accounting_performed']}")
check("V2-A /3 ACCEPTS one forecast for two obligations", A3["ok"] is True,
      str(A3["problems"]))
check("V2-A /3 counts the two obligations as ONE required row",
      A3["n_required"] == 1, str(A3["n_required"]))
check("V2-A /3 reports 100% completeness over half the obligations",
      A3["prediction_coverage"] == 1.0, str(A3["prediction_coverage"]))
check("V2-A the historical validator disagrees with /3 by a factor of two, and is also ok",
      AH["ok"] is True and AH["n_required"] == 2 and AH["prediction_coverage"] == 0.5,
      f"{AH['ok']} {AH['n_required']} {AH['prediction_coverage']}")
check("V2-A /4 REFUSES: the universe's key is not unique", A4["ok"] is False)
check("V2-A /4 refuses to compute coverage rather than computing it wrongly",
      A4["accounting_performed"] is False and "prediction_coverage" not in A4)
check("V2-A /4 says why, in obligations", has(A4, "is NOT unique"),
      str(A4["problems"]))

# --- scenario B: TWO correct forecasts, team-blind key --------------------
B3 = v3.validate_strict_v3(predictions([K_BLIND, K_BLIND]), U_BLIND, TARGET, **BIND)
B4 = v4.validate_strict_v4(predictions([K_BLIND, K_BLIND]), U_BLIND, TARGET, **BIND)
print(f"    B  two forecasts, two obligations (team-blind key)")
print(f"       /3 ok={B3['ok']}  problems={B3['problems']}")
print(f"       /4 ok={B4['ok']}  accounting_performed={B4['accounting_performed']}")
check("V2-B /3 REJECTS the correct behaviour as a duplicate", B3["ok"] is False)
check("V2-B   ... and the reason it gives is 'duplicate row_uid'",
      has(B3, "duplicate row_uid"), str(B3["problems"]))
check("V2-B so /3 rewards answering half the question and punishes answering all of it",
      A3["ok"] is True and B3["ok"] is False)
check("V2-B /4 refuses both frames for the same, correct reason: the key is not a key",
      B4["ok"] is False and B4["accounting_performed"] is False
      and has(B4, "is NOT unique"))

# --- scenario C: canonical key, ONE forecast -> correctly uncovered -------
C4 = v4.validate_strict_v4(predictions([K_NEW]), U_CANON, TARGET, **BIND)
print(f"    C  one forecast, two obligations (canonical key)")
print(f"       /4 ok={C4['ok']}  n_required={C4['n_required']}  "
      f"n_predicted={C4['n_predicted']}  coverage={C4['prediction_coverage']}")
check("V2-C /4 accounts, and finds the missing obligation",
      C4["ok"] is False and C4["accounting_performed"] is True)
check("V2-C /4 counts TWO required obligations, not one",
      C4["n_required"] == 2 and C4["n_required_keys"] == 2)
check("V2-C /4 reports 50% completeness, which is the truth",
      C4["prediction_coverage"] == 0.5)
check("V2-C /4 names the uncovered obligation count",
      C4["n_uncovered"] == 1 and has(C4, "1 REQUIRED obligations neither predicted"),
      str(C4["problems"]))
check("V2-C one forecast can no longer cover two obligations",
      C4["max_obligations_per_forecast"] == 1)

# --- scenario D: canonical key, TWO forecasts -> accepted -----------------
D3 = v3.validate_strict_v3(predictions([K_NEW, K_OLD]), U_CANON, TARGET, **BIND)
D4 = v4.validate_strict_v4(predictions([K_NEW, K_OLD]), U_CANON, TARGET, **BIND)
print(f"    D  two forecasts, two obligations (canonical key)")
print(f"       /3 ok={D3['ok']}   /4 ok={D4['ok']}  n_required={D4['n_required']}  "
      f"coverage={D4['prediction_coverage']}")
check("V2-D /4 ACCEPTS two forecasts for two obligations", D4["ok"] is True,
      str(D4["problems"]))
check("V2-D /4 counts both obligations and both forecasts",
      D4["n_required"] == 2 and D4["n_predicted"] == 2
      and D4["n_predicted_keys"] == 2 and D4["prediction_coverage"] == 1.0)
check("V2-D no duplicate is reported: two clubs are two obligations, not one answered twice",
      D4["n_duplicate_prediction_rows"] == 0)
check("V2-D with the canonical key /3's ARITHMETIC also works -- what /3 lacks is the "
      "PRECONDITION that forces the canonical key to be used", D3["ok"] is True,
      str(D3["problems"]))

# --- scenario E: unique by luck, but the wrong key rule -------------------
ROWS_E = [(PID, GID, NEW_TEAM), (1629477, "1022100007", 1611661313)]
U_LUCKY = universe(ROWS_E, keying="team_blind")
E_UIDS = list(U_LUCKY.row_uid)
E3 = v3.validate_strict_v3(predictions(E_UIDS), U_LUCKY, TARGET, **BIND)
E4 = v4.validate_strict_v4(predictions(E_UIDS), U_LUCKY, TARGET, **BIND)
print(f"    E  a team-blind key that is unique in THIS fold")
print(f"       /3 ok={E3['ok']}   /4 ok={E4['ok']}")
check("V2-E the fixture's team-blind key is unique here, so uniqueness alone cannot catch it",
      U_LUCKY.row_uid.is_unique)
check("V2-E /3 ACCEPTS a frame keyed by the rule that breaks on the next trade",
      E3["ok"] is True, str(E3["problems"]))
check("V2-E /4 REJECTS it: the key does not re-derive from (player_id, game_id, team_id)",
      E4["ok"] is False and has(E4, "does not recompute") is False
      and has(E4, "is not cbs_obligation_key.row_uid"), str(E4["problems"]))
check("V2-E /4 identifies it as the team-blind legacy key by name",
      has(E4, "TEAM-BLIND"), str(E4["problems"]))

# --- scenario F: a universe that declares nothing -------------------------
U_UNDECL = universe(ROWS, keying="canonical", declare_key=False)
F4 = v4.validate_strict_v4(predictions([K_NEW, K_OLD]), U_UNDECL, TARGET, **BIND)
F4_OPT = v4.validate_strict_v4(predictions([K_NEW, K_OLD]), U_UNDECL, TARGET,
                               require_declared_key=False, **BIND)
check("V2-F an undeclared key rule is a problem by default",
      F4["ok"] is False and has(F4, "carries no obligation_key_id"))
check("V2-F   ... and the escape is explicit, named, and must be asked for",
      F4_OPT["ok"] is True, str(F4_OPT["problems"]))

# --- the module's own comparison helper agrees with the assertions above ---
CMP = v4.compare_v3_v4(predictions([K_BLIND]), U_BLIND, TARGET, **BIND)
check("V2 compare_v3_v4 reproduces the disagreement without a test harness",
      CMP["verdicts_agree"] is False and CMP["v3"]["ok"] is True
      and CMP["v4"]["ok"] is False, str(CMP))


# ==========================================================================
# V3 -- exclusion and duplicate accounting, re-keyed
# ==========================================================================
print("V3  exclusion and duplicate accounting")

G4 = v4.validate_strict_v4(predictions([K_NEW, K_OLD], excluded=[K_OLD]), U_CANON,
                           TARGET, **BIND)
check("V3 an excluded obligation still covers its own key, and only its own",
      G4["ok"] is True and G4["n_predicted"] == 1 and G4["n_excluded"] == 1
      and G4["n_excluded_keys"] == 1 and G4["n_uncovered"] == 0, str(G4["problems"]))
check("V3 completeness counts the forecast, not the exclusion",
      G4["prediction_coverage"] == 0.5)

_both = pd.concat([predictions([K_NEW]), predictions([K_NEW], excluded=[K_NEW])],
                  ignore_index=True)
H4 = v4.validate_strict_v4(_both, U_CANON, TARGET, **BIND)
check("V3 one obligation cannot be predicted AND excluded",
      has(H4, "both predicted and excluded"), str(H4["problems"]))
check("V3   ... and that is reported alongside the duplicate, not instead of it",
      has(H4, "prediction rows share"), str(H4["problems"]))

I4 = v4.validate_strict_v4(predictions([K_NEW, K_NEW]), U_CANON, TARGET, **BIND)
check("V3 two forecasts for the SAME obligation are still a duplicate",
      I4["ok"] is False and I4["n_duplicate_prediction_rows"] == 2
      and has(I4, "genuine double-answer"), str(I4["problems"]))

J4 = v4.validate_strict_v4(predictions([K_NEW, obk.row_uid(999, "G999", 1)]), U_CANON,
                           TARGET, **BIND)
check("V3 a forecast on an obligation that does not exist is rejected",
      J4["ok"] is False and has(J4, "absent from the universe"), str(J4["problems"]))
check("V3 the universe join cannot fan out", J4.get("n_join_fanout_rows") == 0)


# ==========================================================================
# V4 -- every lineage check /3 makes, /4 still makes
# ==========================================================================
print("V4  the ported lineage checks still bite")

PAIR = ([K_NEW, K_OLD], U_CANON)
CASES = {
    "a malformed config_hash on an EXCLUDED row":
        dict(over={"config_hash": "not-a-hash"}, excluded=[K_OLD]),
    "a numeric 0/1 where a boolean belongs":
        dict(over={"is_fallback": 0}),
    "a negative n_prior_games": dict(over={"n_prior_games": -1}),
    "feature_asof at or after the cutoff": dict(over={"feature_asof": CUT}),
    "a fallback_level that disagrees with is_fallback": dict(over={"fallback_level": 2}),
    "a fallback_level off the registered ladder": dict(over={"fallback_level": 9}),
    "a null component_id": dict(over={"component_id": None}),
    "a pred_point outside the target's support": dict(over={"pred_point": 1.5}),
    "a non-null pred_sd on a target that forbids it": dict(over={"pred_sd": 0.1}),
    "a fold_id that disagrees with the universe": dict(over={"fold_id": "season:1999"}),
}
for _name, _kw in CASES.items():
    _p = predictions(PAIR[0], excluded=_kw.get("excluded", ()), **_kw["over"])
    r3 = v3.validate_strict_v3(_p, PAIR[1], TARGET, **BIND)
    r4 = v4.validate_strict_v4(_p, PAIR[1], TARGET, **BIND)
    check(f"V4 /4 rejects {_name}", r4["ok"] is False, str(r4["problems"]))
    check(f"V4   ... exactly as /3 did (no check was dropped in the port)",
          r3["ok"] is False and r4["ok"] is False)

_p_excl = predictions(PAIR[0], excluded=[K_OLD])
_p_excl.loc[_p_excl.exclusion_reason.notna(), "pred_point"] = 0.5
check("V4 an excluded row that keeps its VALUES is rejected",
      v4.validate_strict_v4(_p_excl, U_CANON, TARGET, **BIND)["ok"] is False)

for _missing in ("expected_arm_id", "expected_fold_id", "expected_config_hash",
                 "expected_snapshot_hash"):
    _b = {k: v for k, v in BIND.items() if k != _missing}
    _r = v4.validate_strict_v4(predictions(PAIR[0]), U_CANON, TARGET, **_b)
    check(f"V4 identity binding is mandatory: {_missing}",
          _r["ok"] is False and has(_r, _missing))

_r = v4.validate_strict_v4(predictions(PAIR[0]), U_CANON, "not_a_target", **BIND)
check("V4 an unregistered target_key is refused", _r["ok"] is False)
_r = v4.validate_strict_v4(predictions(PAIR[0]).drop(columns=["component_id"]), U_CANON,
                           TARGET, **BIND)
check("V4 a missing required column is refused, not defaulted",
      _r["ok"] is False and has(_r, "missing required columns"))


# ==========================================================================
# V5 -- fail closed
# ==========================================================================
print("V5  fail-closed behaviour")

for _name, _pred, _uni in (
        ("an empty prediction frame", pd.DataFrame(), U_CANON),
        ("an empty universe", predictions(PAIR[0]), pd.DataFrame()),
        ("a universe with no row_uid", predictions(PAIR[0]),
         U_CANON.drop(columns=["row_uid"])),
        ("garbage in place of a frame", predictions(PAIR[0]),
         pd.DataFrame({"row_uid": [None, None],
                       f"prediction_required__{TARGET}": [True, True],
                       "fold_id": [FOLD, FOLD], "forecast_cutoff": [CUT, CUT]})),
):
    try:
        _r = v4.validate_strict_v4(_pred, _uni, TARGET, **BIND)
        _ok, _why = isinstance(_r, dict) and _r["ok"] is False, str(_r)[:120]
    except Exception as exc:
        _ok, _why = False, f"RAISED {type(exc).__name__}: {exc}"
    check(f"V5 {_name} yields a verdict, never a traceback", _ok, _why)


# ==========================================================================
# V6 -- the composed gate
# ==========================================================================
print("V6  the composed gate")

CG = v4.validate_arm_output_v4(predictions([K_NEW, K_OLD]), U_CANON, TARGET,
                               expected_arm_id=ARM, expected_fold_id=FOLD,
                               expected_config_hash=H["config_hash"],
                               expected_snapshot_hash=H["data_snapshot_hash"])
check("V6 the composed gate passes a correct two-obligation frame", CG["ok"] is True,
      str(CG["problems"]))
check("V6 it reports the historical validator's numbers separately, never merged",
      "historical" in CG and "strict" in CG and CG["n_required"] == 2)
CG_BAD = v4.validate_arm_output_v4(predictions([K_BLIND]), U_BLIND, TARGET,
                                   expected_arm_id=ARM, expected_fold_id=FOLD,
                                   expected_config_hash=H["config_hash"],
                                   expected_snapshot_hash=H["data_snapshot_hash"])
check("V6 the composed gate REFUSES the colliding universe the historical one accepts",
      CG_BAD["ok"] is False and CG_BAD["historical"]["ok"] is True,
      str(CG_BAD["problems"]))
check("V6 /4 declares what it supersedes", v4.SUPERSEDES == v3.VALIDATOR_ID
      and v4.VALIDATOR_ID != v3.VALIDATOR_ID)
check("V6 /3 is imported and untouched -- its checks are shared objects, not copies",
      v4.TARGET_RULES is v3.TARGET_RULES and v4.LINEAGE_COLS is v3.LINEAGE_COLS)


# ==========================================================================
# Z7 -- ZERO fits, predictions, scores or evaluations
# ==========================================================================
print("Z7  zero fits, predictions, scores or evaluations")

ESTIMATOR_MODULES = ("sklearn", "statsmodels", "xgboost", "lightgbm", "torch", "keras",
                     "tensorflow", "catboost", "scipy.optimize")
ESTIMATOR_CALLS = {"fit", "predict", "predict_proba", "fit_predict", "fit_transform",
                   "score", "partial_fit", "polyfit", "curve_fit", "minimize"}
METRIC_NAMES = {"log_loss", "roc_auc_score", "brier_score_loss", "accuracy_score",
                "r2_score", "mean_squared_error", "mean_absolute_error"}

_src = (ROOT / "contract_validator_v4_strict.py").read_text(encoding="utf-8")
_tree = ast.parse(_src)
_imports, _calls, _names = [], [], []
for _n in ast.walk(_tree):
    if isinstance(_n, ast.Import):
        _imports += [a.name for a in _n.names]
    elif isinstance(_n, ast.ImportFrom):
        _imports.append(_n.module or "")
    elif isinstance(_n, ast.Call):
        f = _n.func
        if isinstance(f, ast.Attribute) and f.attr in ESTIMATOR_CALLS:
            _calls.append(f.attr)
        if isinstance(f, ast.Name) and f.id in ESTIMATOR_CALLS | METRIC_NAMES:
            _calls.append(f.id)
    elif isinstance(_n, ast.Name) and _n.id in METRIC_NAMES:
        _names.append(_n.id)
check("Z7 the validator imports no estimator library",
      not [m for m in _imports if any(m == e or m.startswith(e + ".")
                                      for e in ESTIMATOR_MODULES)], str(_imports))
check("Z7 the validator calls no fit/predict/score method", not _calls, str(_calls))
check("Z7 the validator references no accuracy or error metric", not _names, str(_names))
check("Z7 the validator never reads an outcome column",
      not any(c in _src for c in ("outcome_scoreable__p", "y_true", "actual_", "residual")),
      "")
check("Z7 the completeness ratio is labelled as an obligation count, not an accuracy",
      "not an accuracy" in D4["coverage_semantics"])
check("Z7 the verdict carries no accuracy, error or profit-and-loss field",
      not [k for k in D4
           if any(m in k.lower() for m in ("accuracy", "auc", "brier", "rmse", "bankroll",
                                           "pnl", "profit"))], str(sorted(D4)))


print(f"\n{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAILED  {f}")
sys.exit(1 if FAILED else 0)
