#!/usr/bin/env python
"""test_cbs_real_integration_v14.py — the corrected prior count, on real obligations.

v13's real gate proved the player path could be entered. This one proves the quantity that path
computes is the registered one: the real 2021 player fold traverses the complete boundary, the
real dual-team siblings receive the SAME prior-obligation count, and the seam that changed it is
confined to the two columns it was allowed to touch — all measured on the real frames the runner
consumes, not on fixtures.

  Q0  the checkout: five required artifacts, attested, matching their bytes
  Q1  the real 2021 player fold builds and orders under `cbs_obligation_order/3`
  Q2  the corrected prior count on the REAL combined history frame: the seam is confined, every
      equal-cutoff group agrees, and nothing availability-gated moved
  Q3  the fold runs END TO END and all eight v14-owned receipts pass
  Q4  it is a COLD START and it fitted NOTHING
  Q5  the real collision: both obligations forecast, and now the SAME prior count
  Q6  real-path negative controls against real bytes
  Z7  zero fits, no outcome read back, no score of any kind

**No real fitted player output exists.** 2021's training window is empty, so the inherited runner
takes its declared-constant path and a runtime sentinel installed before the first real byte never
fires. Seasons 2022-2026 are deliberately NOT run: the ruling forbids a real fitted player fold
before review. Where a 2022 figure is asserted it is computed from the history COMPONENT over real
frames, which fits nothing.

Run as a script::

    python tests/test_cbs_real_integration_v14.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

T_START = time.time()

FIT_CALLS: list[str] = []

import numpy as np                                              # noqa: E402

_np_polyfit = np.polyfit
np.polyfit = lambda *a, **k: (FIT_CALLS.append("numpy.polyfit"), _np_polyfit(*a, **k))[1]

import cbs_generator as gen                                     # noqa: E402


def _sentinel(name, fn):
    def wrapped(*a, **k):
        FIT_CALLS.append(f"cbs_generator.{name}")
        return fn(*a, **k)
    return wrapped


_WATCHED = ("logistic_fit", "logistic_predict", "select_alpha_bound")
for _nm in _WATCHED:
    if hasattr(gen, _nm):
        setattr(gen, _nm, _sentinel(_nm, getattr(gen, _nm)))

import cbs_v8                                                   # noqa: E402
import cbs_player_runner_v14 as fork                            # noqa: E402

for _mod in (cbs_v8, fork):
    for _nm in _WATCHED:
        if hasattr(_mod, _nm) and hasattr(gen, _nm):
            setattr(_mod, _nm, getattr(gen, _nm))

import cbs_obligation_key as obk                                # noqa: E402
import cbs_obligation_order as order2                           # noqa: E402
import cbs_obligation_order_v3 as order3                        # noqa: E402
import cbs_player_history_v14 as hist14                         # noqa: E402
import cbs_provenance_v4 as prov4                               # noqa: E402
import cbs_real_frames_v3 as rf3                                # noqa: E402
import cbs_v7                                                   # noqa: E402
import cbs_v14 as v14                                           # noqa: E402
from cbs_identity_v3 import REAL_PATH_MODE, frame_digest        # noqa: E402
from cbs_v5 import PLAYER_SORT_KEYS                             # noqa: E402
from cbs_v7 import PLAYER_SHORT_HISTORY_MAX                     # noqa: E402

PASSED = 0
FAILED: list[str] = []


def check(label, cond, detail=""):
    global PASSED
    if cond:
        PASSED += 1
        print(f"  ok   {label}")
    else:
        FAILED.append(f"{label}{(' -- ' + str(detail)) if detail else ''}")
        print(f"  FAIL {label}{(' -- ' + str(detail)) if detail else ''}")


def refuses(label, fn, contains=None):
    global PASSED
    try:
        fn()
    except Exception as e:                                       # noqa: BLE001
        if contains and contains.lower() not in str(e).lower():
            FAILED.append(f"{label} -- raised but message lacked {contains!r}: {e}")
            print(f"  FAIL {label} -- message lacked {contains!r}")
            return
        PASSED += 1
        print(f"  ok   {label}")
        return
    FAILED.append(f"{label} -- did not refuse")
    print(f"  FAIL {label} -- did not refuse")


SEASON, FOLD = 2021, "season:2021"
IK, OK_ = list(order2.INHERITED_KEY), list(order2.ORDER_KEY)


def band(n):
    return "none" if n <= 0 else ("short" if n <= PLAYER_SHORT_HISTORY_MAX else "long")


# ==========================================================================
print("\nQ0  the checkout: five required artifacts, attested, matching their bytes")
# ==========================================================================
status = prov4.attestation_status(ROOT, prov4.CBS_REQUIRED_ARTIFACTS)
check("Q0 exactly five artifacts are required", len(prov4.CBS_REQUIRED_ARTIFACTS) == 5)
for rel in sorted(prov4.CBS_REQUIRED_ARTIFACTS):
    e = status[rel]
    check(f"Q0 {rel} exists, is attested and matches its bytes",
          e["exists"] and e["manifest_valid"] and e["hash_ok"] is not False, e.get("problem"))
check("Q0 the contract is prediction_contract_v4, unchanged by this arm",
      prov4.CONTRACT_DIR == "experiments/prediction_contract_v4"
      and v14.ROW_UNIVERSE == "prediction_contract_v4")


# ==========================================================================
print("\nQ1  the real 2021 player fold builds and orders under /3")
# ==========================================================================
t0 = time.time()
BUILT = rf3.build_player_frame(SEASON, ROOT, require_attested=True)
BUILD_SECONDS = time.time() - t0
TR, TE, UNI = BUILT["train"], BUILT["test"], BUILT["universe"]
check(f"Q1 the real {SEASON} player fold builds", len(TE) > 0,
      f"train={len(TR)} test={len(TE)} universe={len(UNI)}")
check("Q1 it is a COLD START: the training window is genuinely empty", len(TR) == 0)

ORDERED = order3.order_obligations_v3(TE, where="real test frame")
check("Q1 /3 orders it with no obligation left indistinguishable",
      int(ORDERED.duplicated(subset=OK_, keep=False).sum()) == 0)
REC = order3.order_receipt_v3(TE, ORDERED, role="test")
check("Q1 and its row_set_unchanged is a canonical-key SET comparison",
      REC["row_set_unchanged"] is True and REC["row_set_comparison"]["compared_on"] == "row_uid"
      and REC["row_set_comparison"]["n_only_before"] == 0
      and REC["row_set_comparison"]["n_only_after"] == 0)
check("Q1 the inherited order still refuses this frame",
      order2.inherited_would_refuse(TE)[0] is True)


# ==========================================================================
print("\nQ2  the corrected prior count, on the REAL combined history frame")
# ==========================================================================
COMB = cbs_v7.combine_history_frames(TR, TE)
if "appeared" not in COMB.columns:
    COMB = COMB.assign(appeared=pd.NA)
PLAN = cbs_v7.build_walk_forward_plan(COMB, group_cols=list(hist14.GROUP_COLS),
                                      sort_cols=list(PLAYER_SORT_KEYS))
SEAM = hist14.assert_only_the_count_moved(COMB, PLAN)
check("Q2 the seam is confined to the count and its derived flag",
      SEAM["ok"] and SEAM["replaced_columns"] == list(hist14.REPLACED_COLUMNS))
for col in ("n_prior_available_obligations", "n_prior_appearances", "p_plays_prior",
            "has_prior_appearance", "has_prior_available_obligation"):
    check(f"Q2 the availability-gated {col} is the inherited value, untouched",
          col in SEAM["columns_unchanged"])
check("Q2 the correction never counts MORE than the positional prefix did",
      SEAM["max_overcount"] >= 0
      and SEAM["n_rows_overcounted_by_the_positional_prefix"] == SEAM["n_rows_corrected"])
check(f"Q2 {SEAM['n_rows_corrected']} real 2021 rows were overcounted, each by exactly one",
      SEAM["max_overcount"] == 1 and SEAM["n_rows_corrected"] >= 1, SEAM["n_rows_corrected"])
AGREE = hist14.equal_cutoff_agreement(COMB, PLAN)
check("Q2 every equal-cutoff group in the real fold now agrees with itself",
      AGREE["ok"] and AGREE["n_groups_whose_members_disagree"] == 0, AGREE)
check(f"Q2 the real fold has {AGREE['n_equal_cutoff_groups']} equal-cutoff groups",
      AGREE["n_equal_cutoff_groups"] >= 1)

# the count is over OBLIGATIONS, not distinct game ids: prove it on a real two-game group
_g = COMB.groupby(["player_id", "season", "forecast_cutoff"])
_two = COMB.assign(_n=_g["game_id"].transform("nunique"),
                   _s=_g["row_uid"].transform("size"))
_two_game = _two[(_two["_s"] == 2) & (_two["_n"] == 2)]
if len(_two_game):
    _h = hist14.player_history_v14(COMB, PLAN)
    _sub = COMB.assign(n=_h["n_prior_candidate_games"].to_numpy())
    _sub = _sub[_sub["row_uid"].isin(set(_two_game["row_uid"]))]
    check("Q2 a real same-cutoff TWO-GAME group also receives one shared count",
          _sub.groupby(["player_id", "season", "forecast_cutoff"])["n"].nunique().eq(1).all(),
          _sub[["row_uid", "game_id", "n"]].to_dict("records"))
else:
    check("Q2 (no two-game equal-cutoff group in this fold; asserted contract-wide in the "
          "unit suite)", True)


# ==========================================================================
print("\nQ3  the fold runs END TO END through the real v14 boundary")
# ==========================================================================
MAN = v14.build_fold_manifest(TR, TE, UNI, root=ROOT)
SNAP = v14.snapshot_identity(MAN)
for role, frame in (("train", TR), ("test", TE), ("universe", UNI)):
    check(f"Q3 the declared {role} digest is that frame's cbs_frame_identity/3 digest",
          MAN["frames"][role] == frame_digest(frame, mode=REAL_PATH_MODE))

RES = v14.run_player_fold(TR, TE, FOLD,
                          config_hash=v14.REGISTERED_CONFIG_HASH, snapshot_hash=SNAP,
                          snapshot_manifest=MAN, universe=UNI,
                          synthetic=False, artifact_root=ROOT)
check("Q3 the run passed every v14 receipt", RES["scoring_permitted"] is True,
      f"failed={RES['failed_receipts']} inherited={RES['inherited_receipts']}")
for name in v14.V14_REQUIRED_RECEIPTS:
    r = RES["receipts"][name]
    check(f"Q3 {name} passes and was recomputed by v14",
          r.get("ok") and r.get("recomputed_by") == v14.ARM_ID, r.get("problems"))
IB = RES["receipts"]["identity_binding"]
check("Q3 the identity binding ran on the REAL path and verified all five artifact digests",
      IB["synthetic"] is False and IB["artifact_bytes"]["n_verified"] == 5
      and IB["real_snapshot_manifest"]["ok"])
check("Q3 and names all three corrected components",
      IB["obligation_order_id"] == "cbs_obligation_order/3"
      and IB["player_history_id"] == "cbs_player_history/14"
      and RES["player_runner_id"] == "cbs_player_runner/14")
OB = RES["receipts"]["obligation_order"]
check("Q3 the ordering receipt validated the ORDERED frame",
      OB["per_frame"]["test"]["validated_on"] == "the ORDERED frame")
check("Q3 and history grouping is unchanged, read from the fork's own source AST",
      OB["history_grouping"]["group_cols"] == ["player_id", "season"]
      and "AST" in OB["history_grouping"]["read_from"])
check("Q3 the prior-count receipt is present and passing",
      OB["prior_obligation_count"]["ok"]
      and OB["prior_obligation_count"]["history_id"] == "cbs_player_history/14")
check("Q3 and declares the count is over obligations and not availability-gated",
      OB["prior_obligation_count"]["counts_obligations_not_distinct_game_ids"] is True
      and OB["prior_obligation_count"]["availability_gated"] is False)
check(f"Q3 every one of the {len(UNI)} real obligations received a forecast slot",
      all(len(p) == len(UNI) for p in RES["predictions"].values()))
COV = RES["receipts"]["coverage"]["per_target"]
check("Q3 obligation completeness is EXACT over the real universe",
      all(v["n_covered"] == len(UNI) for v in COV.values()))


# ==========================================================================
print("\nQ4  it is a cold start, and it fitted NOTHING")
# ==========================================================================
check("Q4 the run reports itself degenerate with an empty training window",
      RES["diagnostics"]["degenerate"] is True)
COMPONENTS = sorted({c for p in RES["predictions"].values()
                     for c in pd.unique(p["component_id"])})
check("Q4 every emitted component is a DECLARED CONSTANT",
      all(c.endswith("/declared_constant") for c in COMPONENTS), COMPONENTS)
check("Q4 THE RUNTIME SENTINEL NEVER FIRED: zero estimator calls on the real player path",
      FIT_CALLS == [], FIT_CALLS)
check("Q4 no real fitted player output exists, which is what this arm claims",
      not FIT_CALLS and all(c.endswith("/declared_constant") for c in COMPONENTS))


# ==========================================================================
print("\nQ5  the REAL collision: both forecast, and now the SAME prior count")
# ==========================================================================
DUAL = TE[TE.duplicated(subset=IK, keep=False)]
UIDS = set(DUAL["row_uid"])
check("Q5 the real 2021 collision is one pair, two clubs, one game, one cutoff",
      len(DUAL) == 2 and DUAL["team_id"].nunique() == 2
      and DUAL["game_id"].nunique() == 1 and DUAL["forecast_cutoff"].nunique() == 1)
for tgt, p in RES["predictions"].items():
    check(f"Q5 {tgt}: BOTH obligations received a forecast",
          UIDS <= set(p["row_uid"]) and int(p["row_uid"].isin(UIDS).sum()) == 2)
check("Q5 the real validator accepts them against their canonical keys",
      RES["receipts"]["prediction_validation"]["ok"])

SC = RES["provenance_sidecar"]
PAIR = SC[(SC["row_uid"].isin(UIDS)) & (SC["target_key"] == "p_active")]
check("Q5 the siblings now receive the SAME prior-obligation count -- the v13 defect, closed",
      PAIR["n_prior_candidate_games"].nunique() == 1,
      PAIR["n_prior_candidate_games"].tolist())
check("Q5 and still agree on every availability-gated quantity, as they did under v13",
      PAIR["n_prior_available_obligations"].nunique() == 1
      and PAIR["n_prior_appearances"].nunique() == 1)
# Recomputed here from the raw frame, independently of the component, so the assertion is a
# check and not a restatement: 2021's training window is empty, so the player's whole season is
# in TE.
_pid = DUAL["player_id"].iloc[0]
_own = pd.to_datetime(DUAL["forecast_cutoff"].iloc[0], utc=True)
_all = pd.to_datetime(TE.loc[TE["player_id"] == _pid, "forecast_cutoff"], utc=True)
_expected = int((_all < _own).sum())
check("Q5 neither counts the other: the shared count equals the number of the player's "
      "obligations with a STRICTLY EARLIER cutoff, recomputed from the raw frame",
      int(PAIR["n_prior_candidate_games"].iloc[0]) == _expected,
      f"got {PAIR['n_prior_candidate_games'].tolist()}, expected {_expected}")
# the contrast, computed from the INHERITED function on the same frame and plan
_old = cbs_v8.player_history_walk_forward(COMB, PLAN)["n_prior_candidate_games"]
_old_pair = sorted(_old[COMB["row_uid"].isin(UIDS)].astype(int).tolist())
_new_pair = sorted(hist14.player_history_v14(COMB, PLAN)["n_prior_candidate_games"]
                   [COMB["row_uid"].isin(UIDS)].astype(int).tolist())
check("Q5 the INHERITED function disagrees with itself on this pair by exactly one",
      len(_old_pair) == 2 and _old_pair[1] - _old_pair[0] == 1, _old_pair)
check("Q5 while the corrected one gives both the same value, equal to the lower of the two",
      _new_pair == [_expected, _expected] and _expected == _old_pair[0],
      f"inherited {_old_pair} -> corrected {_new_pair}")


# ==========================================================================
print("\nQ6  real-path negative controls, against real bytes")
# ==========================================================================
_tampered = {**MAN, "artifacts": {**MAN["artifacts"]}}
_first = sorted(_tampered["artifacts"])[0]
_tampered["artifacts"][_first] = {**_tampered["artifacts"][_first], "sha256": "0" * 64}
refuses("Q6 a declared artifact digest that does not match disk is refused",
        lambda: v14.run_player_fold(
            TR, TE, FOLD, config_hash=v14.REGISTERED_CONFIG_HASH,
            snapshot_hash=v14.snapshot_identity(_tampered), snapshot_manifest=_tampered,
            universe=UNI, synthetic=False, artifact_root=ROOT),
        contains="do not match their bytes on disk")
refuses("Q6 a real run that supplies no artifact_root is refused",
        lambda: v14.run_player_fold(
            TR, TE, FOLD, config_hash=v14.REGISTERED_CONFIG_HASH, snapshot_hash=SNAP,
            snapshot_manifest=MAN, universe=UNI, synthetic=False),
        contains="artifact_root")
_mut = TE.copy()
_mut.loc[_mut.index[0], "min_ewma"] = -12345.0
refuses("Q6 a mutated frame against the same manifest is refused",
        lambda: v14.run_player_fold(
            TR, _mut, FOLD, config_hash=v14.REGISTERED_CONFIG_HASH, snapshot_hash=SNAP,
            snapshot_manifest=MAN, universe=UNI, synthetic=False, artifact_root=ROOT),
        contains="does not match the manifest")
refuses("Q6 a genuine duplicate is refused even under the full key",
        lambda: v14.run_player_fold(
            TR, pd.concat([TE, TE.iloc[[0]]], ignore_index=True), FOLD,
            config_hash=v14.REGISTERED_CONFIG_HASH, snapshot_hash=SNAP,
            snapshot_manifest=MAN, universe=UNI, synthetic=False, artifact_root=ROOT))
refuses("Q6 the SYNTHETIC config digest is refused on the real path",
        lambda: v14.run_player_fold(
            TR, TE, FOLD, config_hash=v14.SYNTHETIC_CONFIG_HASH, snapshot_hash=SNAP,
            snapshot_manifest=MAN, universe=UNI, synthetic=False, artifact_root=ROOT),
        contains="config_hash")
check("Q6 none of the refusals ran an estimator", FIT_CALLS == [], FIT_CALLS)


# ==========================================================================
print("\nZ7  zero fits, no outcome read back, no score of any kind")
# ==========================================================================
check("Z7 the runtime sentinel never fired across every real call in this file",
      FIT_CALLS == [], FIT_CALLS)
check("Z7 no estimator library is loaded in this process",
      not ({"sklearn", "catboost", "lightgbm", "xgboost", "tabpfn", "statsmodels"}
           & set(sys.modules)))
check("Z7 the run computed no accuracy, calibration or profitability figure",
      not any(k in RES for k in ("accuracy", "auc", "log_loss", "brier", "profit", "roi")))
_cols = set().union(*(set(p.columns) for p in RES["predictions"].values()))
check("Z7 no outcome column was carried into any emitted forecast",
      not ({"minutes", "points", "fga", "appeared"} & _cols))
check("Z7 seasons 2022-2026 were not run: the ruling forbids a real fitted player fold",
      True)
check("Z7 the canonical key and the contract universe are unchanged from v11",
      obk.OBLIGATION_KEY_ID == "cbs_obligation_key/1"
      and RES["obligation_key_id"] == obk.OBLIGATION_KEY_ID)


print(f"\n    total runtime {time.time() - T_START:.0f}s "
      f"(real frame build: {BUILD_SECONDS:.0f}s)")
print(f"\n{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAILED  {f}")
sys.exit(1 if FAILED else 0)
