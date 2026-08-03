#!/usr/bin/env python
"""test_cbs_real_integration_v13.py — the REAL player fold, through the complete boundary.

This is the eighth property the supervisor's ruling named: *a real 2021 player cold-start fold
traverses the complete boundary with zero estimator fits*. Every earlier real gate in this project
stops short of it. `test_cbs_real_integration_v11` builds real frames and stops at a bound
snapshot manifest. `test_cbs_real_integration_v12` crosses the fit boundary but only on the TEAM
path, because the player path could not be ordered at all.

So this file does the thing that has never been done: it takes the real contract-v4 player
obligations for 2021 — including the real dual-team collision that blocked every previous arm —
and runs them through `cbs_v13.run_player_fold` on the real path, end to end.

  P0  the checkout: five required artifacts, attested, matching their bytes
  P1  the real 2021 player fold builds, and the inherited order still REFUSES it
  P2  `cbs_obligation_order/2` orders it, totally, adding and removing no obligation
  P3  the fold runs END TO END through the real `/5` boundary and all eight v13-owned
      receipts pass
  P4  it is a COLD START and it fitted NOTHING — 2021's training window is empty and a runtime
      sentinel installed before the first real byte never fires
  P5  the REAL collision: both obligations forecast, distinct canonical keys, neither in the
      other's availability-gated history — and the one quantity where that is NOT true,
      measured
  P6  real-path negative controls against real bytes
  Z7  zero fits, no outcome read back against any forecast, no score of any kind

WHAT IS AND IS NOT DONE HERE
----------------------------

Real player forecasts ARE emitted. They are the inherited runner's DECLARED CONSTANTS, because
2021 is the first contracted season and has no prior season to learn from, and P4 proves that
with a sentinel that would have fired on any estimator call. **No real fitted player output
exists, and none is authorized before supervisory review of this pushed unit.** No forecast is
compared to any outcome and no accuracy, calibration, threshold, edge, return or profitability
figure is computed anywhere in this file. "Coverage" means OBLIGATION COMPLETENESS.

Run as a script (this repository has no pytest installed)::

    python tests/test_cbs_real_integration_v13.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

T_START = time.time()

# ==========================================================================
# the RUNTIME no-fit sentinel, installed BEFORE any real module is imported
# ==========================================================================
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
import cbs_player_runner_v13 as fork                            # noqa: E402

# the fork imports these names into its OWN namespace, so both have to be armed or the sentinel
# would be watching a function the real path never reaches
for _mod in (cbs_v8, fork):
    for _nm in _WATCHED:
        if hasattr(_mod, _nm) and hasattr(gen, _nm):
            setattr(_mod, _nm, getattr(gen, _nm))

import cbs_obligation_key as obk                                # noqa: E402
import cbs_obligation_order as order2                           # noqa: E402
import cbs_provenance_v4 as prov4                               # noqa: E402
import cbs_real_frames_v3 as rf3                                # noqa: E402
import cbs_v13 as v13                                           # noqa: E402
from cbs_identity_v3 import REAL_PATH_MODE, frame_digest        # noqa: E402

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


SEASON = 2021
FOLD = f"season:{SEASON}"
IK, OK_ = list(order2.INHERITED_KEY), list(order2.ORDER_KEY)


# ==========================================================================
print("\nP0  the checkout: five required artifacts, attested, matching their bytes")
# ==========================================================================
status = prov4.attestation_status(ROOT, prov4.CBS_REQUIRED_ARTIFACTS)
check("P0 exactly five artifacts are required", len(prov4.CBS_REQUIRED_ARTIFACTS) == 5)
for rel in sorted(prov4.CBS_REQUIRED_ARTIFACTS):
    e = status[rel]
    check(f"P0 {rel} exists, is attested and matches its bytes",
          e["exists"] and e["manifest_valid"] and e["hash_ok"] is not False, e.get("problem"))
check("P0 the contract is prediction_contract_v4, unchanged by this arm",
      prov4.CONTRACT_DIR == "experiments/prediction_contract_v4")


# ==========================================================================
print("\nP1  the real player fold builds, and the INHERITED order still refuses it")
# ==========================================================================
t0 = time.time()
BUILT = rf3.build_player_frame(SEASON, ROOT, require_attested=True)
BUILD_SECONDS = time.time() - t0
TR, TE, UNI = BUILT["train"], BUILT["test"], BUILT["universe"]

check(f"P1 the real {SEASON} player fold builds from attested artifacts", len(TE) > 0,
      f"train={len(TR)} test={len(TE)} universe={len(UNI)}")
check("P1 it is a COLD START: the training window is genuinely empty", len(TR) == 0,
      f"{len(TR)} training rows")
check("P1 every obligation carries a unique canonical key", TE["row_uid"].is_unique)
check("P1 the universe and the test frame name the same obligations",
      set(UNI["row_uid"]) == set(TE["row_uid"]))

refused, why = order2.inherited_would_refuse(TE)
check("P1 the INHERITED order refuses this frame -- measured, not assumed", refused, why[:160])
check("P1 and its reason is the team-blind tie", "indistinguishable" in why, why[:160])
N_INH = int(TE.duplicated(subset=IK, keep=False).sum())
check(f"P1 season {SEASON} carries exactly 2 obligations the inherited key cannot name",
      N_INH == 2, N_INH)


# ==========================================================================
print("\nP2  cbs_obligation_order/2 orders it, totally")
# ==========================================================================
ORDERED = order2.order_obligations_v2(TE, where="real test frame")
check("P2 the full v13 key leaves NO obligation indistinguishable",
      int(ORDERED.duplicated(subset=OK_, keep=False).sum()) == 0)
check("P2 ordering adds and removes no obligation",
      len(ORDERED) == len(TE) and set(ORDERED["row_uid"]) == set(TE["row_uid"]))
check("P2 the canonical key is still unique after ordering", ORDERED["row_uid"].is_unique)
REC_ORD = order2.order_receipt(TE, ORDERED, role="test")
check("P2 the order receipt names the discriminator and the terminal tie-breaker",
      REC_ORD["discriminator"] == "team_id" and REC_ORD["terminal_tie_breaker"] == "row_uid")
check("P2 and reports the count the inherited key could not name",
      REC_ORD["n_rows_indistinguishable_under_the_inherited_key"] == 2, REC_ORD)


# ==========================================================================
print("\nP3  the real fold runs END TO END through the real v13 boundary")
# ==========================================================================
MAN = v13.build_fold_manifest(TR, TE, UNI, root=ROOT)
SNAP = v13.snapshot_identity(MAN)
check("P3 a per-fold /5 manifest is built from the frames this run consumes",
      MAN["schema"] == "cbs_snapshot_manifest/5"
      and sorted(MAN["frames"]) == ["test", "train", "universe"])
for role, frame in (("train", TR), ("test", TE), ("universe", UNI)):
    check(f"P3 the declared {role} digest is that frame's cbs_frame_identity/3 digest",
          MAN["frames"][role] == frame_digest(frame, mode=REAL_PATH_MODE))

RES = v13.run_player_fold(TR, TE, FOLD,
                          config_hash=v13.REGISTERED_CONFIG_HASH, snapshot_hash=SNAP,
                          snapshot_manifest=MAN, universe=UNI,
                          synthetic=False, artifact_root=ROOT)

check("P3 the run passed every v13 receipt", RES["scoring_permitted"] is True,
      f"failed={RES['failed_receipts']} inherited={RES['inherited_receipts']}")
for name in v13.V13_REQUIRED_RECEIPTS:
    r = RES["receipts"][name]
    check(f"P3 {name} passes and was recomputed by v13",
          r.get("ok") and r.get("recomputed_by") == v13.ARM_ID, r.get("problems"))

IB = RES["receipts"]["identity_binding"]
check("P3 the identity binding ran on the REAL path", IB["synthetic"] is False)
check("P3 it verified the real-manifest stamps",
      IB["real_snapshot_manifest"] is not None and IB["real_snapshot_manifest"]["ok"])
check("P3 it verified all five artifact digests against the BYTES ON DISK",
      IB["artifact_bytes"]["ok"] and IB["artifact_bytes"]["n_verified"] == 5)
check("P3 it recomputed the registered config hash from the registry",
      IB["config_hash_recomputed_from_registry"] == v13.REGISTERED_CONFIG_HASH)
check("P3 it names the ordering component it ran under",
      IB["obligation_order_id"] == "cbs_obligation_order/2")

SP = RES["receipts"]["source_provenance"]
check("P3 both frames' registered feature sources were validated",
      SP["frames_validated"] == ["test", "train"], SP["frames_validated"])
check("P3 the empty training frame was schema-validated, not skipped",
      SP["train_frame_empty"] is True
      and SP["per_frame"]["train"]["row_level_clauses_vacuous"] is True)
check("P3 no test row read a feature source at or after its own cutoff",
      SP["per_frame"]["test"]["n_at_cutoff"] == 0
      and SP["per_frame"]["test"]["n_after_cutoff"] == 0)

OB = RES["receipts"]["obligation_order"]
check("P3 the ordering receipt records that the inherited order would have refused",
      OB["inherited_order_would_have_refused"]["test"]["refused"] is True)
check("P3 and that history grouping is unchanged, read from the fork's own source",
      OB["history_grouping"]["group_cols"] == ["player_id", "season"]
      and "AST" in OB["history_grouping"]["read_from"])

check("P3 all four player targets emitted forecasts",
      sorted(RES["predictions"]) == sorted(v13.PLAYER_TARGETS))
check(f"P3 every one of the {len(UNI)} real obligations received a forecast slot",
      all(len(p) == len(UNI) for p in RES["predictions"].values()),
      {t: len(p) for t, p in RES["predictions"].items()})
COV = RES["receipts"]["coverage"]["per_target"]
check("P3 obligation completeness is EXACT over the real universe",
      all(v["n_covered"] == len(UNI) for v in COV.values()), COV)
for tgt, p in RES["predictions"].items():
    check(f"P3 {tgt}: every emitted row carries the v13 arm and identity",
          (p["arm_id"] == v13.ARM_ID).all()
          and (p["config_hash"] == v13.REGISTERED_CONFIG_HASH).all()
          and (p["data_snapshot_hash"] == SNAP).all())
SC = RES["provenance_sidecar"]
check("P3 the sidecar digest names the restamped sidecar the run returned",
      RES["receipts"]["provenance_history"]["digest"] == v13.sidecar_identity(SC)
      == RES["provenance_sidecar_digest"])
check("P3 the run names the forked runner it used",
      RES["player_runner_id"] == "cbs_player_runner/13")


# ==========================================================================
print("\nP4  it is a cold start, and it fitted NOTHING")
# ==========================================================================
check("P4 the run reports itself degenerate with an empty training window",
      RES["diagnostics"]["degenerate"] is True, RES["diagnostics"].get("reason"))
COMPONENTS = sorted({c for p in RES["predictions"].values()
                     for c in pd.unique(p["component_id"])})
check("P4 every emitted component is a DECLARED CONSTANT, not a fitted model",
      all(c.endswith("/declared_constant") for c in COMPONENTS), COMPONENTS)
check("P4 every emitted point forecast is constant within its target",
      all(p["pred_point"].nunique(dropna=True) <= 1 for p in RES["predictions"].values()))
check("P4 THE RUNTIME SENTINEL NEVER FIRED: zero estimator calls on the real player path",
      FIT_CALLS == [], FIT_CALLS)
check("P4 no real fitted player output exists, which is what this arm claims",
      not FIT_CALLS and all(c.endswith("/declared_constant") for c in COMPONENTS))


# ==========================================================================
print("\nP5  the REAL collision, through the real path")
# ==========================================================================
DUAL = TE[TE.duplicated(subset=IK, keep=False)]
UIDS = set(DUAL["row_uid"])
check("P5 the real 2021 collision is one pair", len(DUAL) == 2 and len(UIDS) == 2)
check("P5 same player, same game, same cutoff, two clubs",
      DUAL["player_id"].nunique() == 1 and DUAL["game_id"].nunique() == 1
      and DUAL["forecast_cutoff"].nunique() == 1 and DUAL["team_id"].nunique() == 2,
      DUAL[["player_id", "game_id", "team_id"]].to_dict("records"))
check("P5 their canonical keys re-derive from (player_id, game_id, team_id)",
      all(obk.row_uid(r.player_id, r.game_id, r.team_id) == r.row_uid
          for r in DUAL.itertuples()))
for tgt, p in RES["predictions"].items():
    check(f"P5 {tgt}: BOTH obligations received a forecast",
          UIDS <= set(p["row_uid"]) and int(p["row_uid"].isin(UIDS).sum()) == 2)
    check(f"P5 {tgt}: one forecast does not cover two obligations", p["row_uid"].is_unique)
check("P5 the real validator accepts both against their canonical keys",
      RES["receipts"]["prediction_validation"]["ok"],
      RES["receipts"]["prediction_validation"].get("problems"))

PAIR = SC[(SC["row_uid"].isin(UIDS)) & (SC["target_key"] == "p_active")]
check("P5 both siblings appear in the emitted provenance", len(PAIR) == 2)
check("P5 neither entered the other's ADMITTED history: n_prior_available_obligations agrees",
      PAIR["n_prior_available_obligations"].nunique() == 1,
      PAIR["n_prior_available_obligations"].tolist())
check("P5 nor its appearance history: n_prior_appearances agrees",
      PAIR["n_prior_appearances"].nunique() == 1, PAIR["n_prior_appearances"].tolist())

# and the one quantity where the claim does NOT hold, measured rather than omitted
M = OB["equal_cutoff_candidate_count"]
check("P5 the POSITIONAL candidate count does count the sibling, and v13 measures it",
      M["n_rows_where_positional_exceeds_causal"] >= 1, M)
check("P5 the two siblings therefore disagree on n_prior_candidate_games by exactly one",
      PAIR["n_prior_candidate_games"].nunique() == 2
      and int(PAIR["n_prior_candidate_games"].max()
              - PAIR["n_prior_candidate_games"].min()) == 1,
      PAIR["n_prior_candidate_games"].tolist())
check("P5 it carries no outcome, so it is not an outcome leak", M["outcome_leak"] is False)
check(f"P5 on this fold it changes no p_active fallback band "
      f"({M['n_rows_whose_p_active_fallback_band_would_differ']} rows)",
      M["n_rows_whose_p_active_fallback_band_would_differ"] == 0, M)


# ==========================================================================
print("\nP6  real-path negative controls, against real bytes")
# ==========================================================================
_tampered = {**MAN, "artifacts": {**MAN["artifacts"]}}
_first = sorted(_tampered["artifacts"])[0]
_tampered["artifacts"][_first] = {**_tampered["artifacts"][_first], "sha256": "0" * 64}
refuses("P6 a declared artifact digest that does not match disk is refused",
        lambda: v13.run_player_fold(
            TR, TE, FOLD, config_hash=v13.REGISTERED_CONFIG_HASH,
            snapshot_hash=v13.snapshot_identity(_tampered), snapshot_manifest=_tampered,
            universe=UNI, synthetic=False, artifact_root=ROOT),
        contains="do not match their bytes on disk")
refuses("P6 a real run that supplies no artifact_root is refused",
        lambda: v13.run_player_fold(
            TR, TE, FOLD, config_hash=v13.REGISTERED_CONFIG_HASH, snapshot_hash=SNAP,
            snapshot_manifest=MAN, universe=UNI, synthetic=False),
        contains="artifact_root")

_mut = TE.copy()
_mut.loc[_mut.index[0], "min_ewma"] = -12345.0
refuses("P6 a mutated frame against the same manifest is refused (stale frame digest)",
        lambda: v13.run_player_fold(
            TR, _mut, FOLD, config_hash=v13.REGISTERED_CONFIG_HASH, snapshot_hash=SNAP,
            snapshot_manifest=MAN, universe=UNI, synthetic=False, artifact_root=ROOT),
        contains="does not match the manifest")

_dup = pd.concat([TE, TE.iloc[[0]]], ignore_index=True)
refuses("P6 a genuine duplicate -- tying even under the FULL v13 key -- is refused",
        lambda: v13.run_player_fold(
            TR, _dup, FOLD, config_hash=v13.REGISTERED_CONFIG_HASH, snapshot_hash=SNAP,
            snapshot_manifest=MAN, universe=UNI, synthetic=False, artifact_root=ROOT))
refuses("P6 the SYNTHETIC config digest is refused on the real path",
        lambda: v13.run_player_fold(
            TR, TE, FOLD, config_hash=v13.SYNTHETIC_CONFIG_HASH, snapshot_hash=SNAP,
            snapshot_manifest=MAN, universe=UNI, synthetic=False, artifact_root=ROOT),
        contains="config_hash")
_reused = v13.build_fold_manifest(TR, TE, None, root=ROOT)
refuses("P6 a manifest built for a DIFFERENT fold shape is refused",
        lambda: v13.run_player_fold(
            TR, TE, FOLD, config_hash=v13.REGISTERED_CONFIG_HASH,
            snapshot_hash=v13.snapshot_identity(_reused), snapshot_manifest=_reused,
            universe=UNI, synthetic=False, artifact_root=ROOT),
        contains="does not describe THIS fold")
check("P6 none of the refusals ran an estimator", FIT_CALLS == [], FIT_CALLS)


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
_pred_cols = set().union(*(set(p.columns) for p in RES["predictions"].values()))
check("Z7 no outcome column was carried into any emitted forecast",
      not ({"minutes", "points", "fga", "appeared"} & _pred_cols),
      sorted({"minutes", "points", "fga", "appeared"} & _pred_cols))
check("Z7 'coverage' here is an obligation count and the receipt says so",
      set(COV["p_active"]) >= {"n_required", "n_covered", "n_emitted"})
check("Z7 the module's own scoring note states nothing is scored",
      "computes no accuracy" in RES["scoring_note"])
check("Z7 the canonical key rule is unchanged from v11",
      obk.OBLIGATION_KEY_ID == "cbs_obligation_key/1"
      and RES["obligation_key_id"] == obk.OBLIGATION_KEY_ID)
check("Z7 and the contract universe is unchanged from v11",
      v13.ROW_UNIVERSE == "prediction_contract_v4")


print(f"\n    total runtime {time.time() - T_START:.0f}s "
      f"(real frame build: {BUILD_SECONDS:.0f}s)")
print(f"\n{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAILED  {f}")
sys.exit(1 if FAILED else 0)
