#!/usr/bin/env python
"""test_cbs_v10.py — the fan-in suite for `contract_baseline_suite_v10`.

The three branch suites each prove their own piece. This one proves the pieces
were **composed**, which is the part no branch could check alone: that the runner
binds the `/3` identity, refuses every earlier manifest generation, enforces the
exact five artifacts of the **v3** contract, and that the row universe, the
adapter and the provenance layer all name the same contract.

**Synthetic only.** No real artifact is read. Nothing is fitted, predicted or
scored, no accuracy, coverage or profitability figure is computed, and no feature
is related to any outcome.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cbs_identity_v3 as fid3  # noqa: E402
import cbs_provenance as prov2  # noqa: E402
import cbs_provenance_v3 as p3  # noqa: E402
import cbs_real_frames_v2 as rf2  # noqa: E402
import cbs_v8  # noqa: E402
import cbs_v9  # noqa: E402
import cbs_v10 as v10  # noqa: E402
import prediction_contract_v3 as pc3  # noqa: E402

PASSED = 0
FAILED: list[str] = []
CFG = v10.SYNTHETIC_CONFIG_HASH


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")


def raises(name, exc, fn, *a, **kw) -> None:
    try:
        fn(*a, **kw)
        check(name, False, "no exception raised")
    except exc:
        check(name, True)
    except Exception as other:
        check(name, False, f"raised {type(other).__name__}: {other}")


# --------------------------------------------------------------------------
# I1 -- one contract, named the same way everywhere
# --------------------------------------------------------------------------

check("I1 the required set is exactly five", len(p3.CBS_REQUIRED_ARTIFACTS) == 5)
check("I1 every required artifact must be attested",
      set(p3.MUST_BE_ATTESTED) == set(p3.CBS_REQUIRED_ARTIFACTS))
check("I1 the row universe is prediction_contract_v3",
      sum(a.startswith("experiments/prediction_contract_v3/")
          for a in p3.CBS_REQUIRED_ARTIFACTS) == 3)
check("I1 no superseded v2 contract artifact is in the required set",
      not any(a.startswith("experiments/prediction_contract_v2/")
              for a in p3.CBS_REQUIRED_ARTIFACTS),
      "enforcing 'exactly five' against the superseded universe would pass while "
      "binding the wrong contract")
check("I1 the superseded v2 set is retained for audit rather than erased",
      set(p3.CBS_REQUIRED_ARTIFACTS_V2_SUPERSEDED)
      == set(prov2.CBS_REQUIRED_ARTIFACTS))
check("I1 the adapter reads the same contract the provenance layer enforces",
      rf2.prov.CBS_REQUIRED_ARTIFACTS == p3.CBS_REQUIRED_ARTIFACTS)
check("I1 the contract producer targets the same directory",
      pc3.OUT.name == "prediction_contract_v3"
      if hasattr(pc3, "OUT") else p3.CONTRACT_DIR.endswith("prediction_contract_v3"))
check("I1 the two masters are shared with the superseded set",
      {a for a in p3.CBS_REQUIRED_ARTIFACTS if a.startswith("data/masters/")}
      == {a for a in prov2.CBS_REQUIRED_ARTIFACTS if a.startswith("data/masters/")})


# --------------------------------------------------------------------------
# I2 -- the identity generations are in lockstep and mutually exclusive
# --------------------------------------------------------------------------

check("I2 v10 declares cbs_snapshot_manifest/4",
      v10.SNAPSHOT_MANIFEST_SCHEMA == "cbs_snapshot_manifest/4")
check("I2 the provenance layer emits that same schema",
      p3.SNAPSHOT_MANIFEST_SCHEMA == v10.SNAPSHOT_MANIFEST_SCHEMA,
      "a manifest whose schema number claims an identity encoding it does not use "
      "is worse than no version number")
check("I2 v10 binds cbs_frame_identity/3",
      v10.FRAME_IDENTITY_SCHEMA == fid3.FRAME_IDENTITY_SCHEMA == "cbs_frame_identity/3")
check("I2 every earlier manifest generation is refused",
      set(v10.REJECTED_MANIFEST_SCHEMAS)
      == {"cbs_snapshot_manifest/1", "cbs_snapshot_manifest/2",
          "cbs_snapshot_manifest/3"})
check("I2 v9 and v10 do not accept each other's manifest schema",
      cbs_v9.SNAPSHOT_MANIFEST_SCHEMA != v10.SNAPSHOT_MANIFEST_SCHEMA
      and cbs_v9.SNAPSHOT_MANIFEST_SCHEMA in v10.REJECTED_MANIFEST_SCHEMAS)
check("I2 the real path is the scalar-only identity mode",
      fid3.REAL_PATH_MODE == "scalar_only")


# --------------------------------------------------------------------------
# fixtures for the runner
# --------------------------------------------------------------------------

def pframe(season, n_players=8, n_dates=40, seed=3):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(f"{season}-05-01", periods=n_dates, freq="D")
    rows = []
    for gi, d in enumerate(dates):
        for pid in range(n_players):
            ap = int(rng.random() < 0.6)
            mn = float(rng.uniform(9, 33)) if ap else 0.0
            cut = (d - pd.Timedelta(hours=6)).tz_localize("UTC")
            r = {"row_uid": f"pg_{season}_{gi:04d}_{pid}", "player_id": f"P{pid}",
                 "season": season, "game_id": f"G{season}{gi:04d}", "game_date": d,
                 "forecast_cutoff": cut.isoformat(),
                 "feature_asof": (cut - pd.Timedelta(hours=6)).isoformat(),
                 "appeared": ap, "minutes": mn,
                 "fga": float(rng.poisson(max(mn, .1) * .35)) if ap else 0.0,
                 "points": float(rng.poisson(max(mn, .1) * .45)) if ap else 0.0}
            for k, lag in zip(v10.REQUIRED_PLAYER_FEATURE_SOURCES, (9, 8, 30)):
                r[k] = (cut - pd.Timedelta(hours=lag)).isoformat()
            rows.append(r)
    return pd.DataFrame(rows).reset_index(drop=True)


FOLD = "season:2100"
TRAIN, TEST = pframe(2099), pframe(2100, seed=9, n_dates=14)
UNI = pd.DataFrame({"row_uid": TEST.row_uid, "fold_id": FOLD,
                    "forecast_cutoff": TEST.forecast_cutoff,
                    "appeared": TEST.appeared.astype(bool)})
for _t in v10.PLAYER_TARGETS:
    UNI[f"prediction_required__{_t}"] = True
    UNI[f"outcome_scoreable__{_t}"] = (UNI["appeared"] if _t != "p_active" else True)


def manifest(frames):
    return {"schema": v10.SNAPSHOT_MANIFEST_SCHEMA,
            "frame_identity_schema": fid3.FRAME_IDENTITY_SCHEMA,
            "frame_identity_mode": fid3.REAL_PATH_MODE,
            "captured_at": "2100-09-01T00:00:00+00:00",
            "artifacts": {rel: {"sha256": "a" * 64, "bytes": 1}
                          for rel in p3.CBS_REQUIRED_ARTIFACTS},
            "frames": fid3.frames_digest(frames, mode=fid3.REAL_PATH_MODE)}


MAN = manifest({"train": TRAIN, "test": TEST, "universe": UNI})
SNAP = v10.snapshot_identity(MAN)
res = v10.run_player_fold(TRAIN, TEST, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                          snapshot_manifest=MAN, universe=UNI)


# --------------------------------------------------------------------------
# I3 -- the composed run
# --------------------------------------------------------------------------

check("I3 the v10 fold passes every receipt", res["scoring_permitted"],
      str(res["failed_receipts"]))
check("I3 all eight receipts are required", len(res["required_receipts"]) == 8)
P = res["predictions"]
check("I3 emitted rows carry the v10 arm",
      all((p.arm_id == v10.ARM_ID).all() for p in P.values()))
check("I3 emitted rows carry the v10 identity",
      all((p.config_hash == CFG).all() and (p.data_snapshot_hash == SNAP).all()
          for p in P.values()))
check("I3 no earlier arm identity survives the restamp",
      not any((p.arm_id.isin([cbs_v8.ARM_ID, cbs_v9.ARM_ID])).any()
              for p in P.values()))
check("I3 the sidecar carries the v10 arm",
      bool((res["provenance_sidecar"].arm_id == v10.ARM_ID).all()))
check("I3 the prediction receipt was re-validated against the v10 values",
      res["receipts"]["prediction_validation"]["ok"])
check("I3 the frame-binding receipt names the /3 identity and its mode",
      res["receipts"]["frame_binding"]["frame_identity_schema"]
      == fid3.FRAME_IDENTITY_SCHEMA
      and res["receipts"]["frame_binding"]["frame_identity_mode"]
      == fid3.REAL_PATH_MODE)


# --------------------------------------------------------------------------
# I4 -- what the runner must refuse
# --------------------------------------------------------------------------

for bad in v10.REJECTED_MANIFEST_SCHEMAS:
    raises(f"I4 a {bad} manifest is refused", v10.AdapterBoundaryError,
           v10.snapshot_identity, {**MAN, "schema": bad})
raises("I4 a manifest without the /3 identity schema is refused",
       v10.AdapterBoundaryError, v10.snapshot_identity,
       {**MAN, "frame_identity_schema": "cbs_frame_identity/2"})
raises("I4 a manifest without the real-path identity mode is refused",
       v10.AdapterBoundaryError, v10.snapshot_identity,
       {**MAN, "frame_identity_mode": "strict_containers"})

_sub = dict(MAN)
_sub["artifacts"] = {k: v for k, v in list(MAN["artifacts"].items())[:1]}
raises("I4 an artifact SUBSET is refused at the runner, not only at construction",
       p3.ArtifactSetError, v10.snapshot_identity, _sub)
_sup = dict(MAN)
_sup["artifacts"] = {**MAN["artifacts"], "experiments/extra.parquet": "b" * 64}
raises("I4 an artifact SUPERSET is refused too", p3.ArtifactSetError,
       v10.snapshot_identity, _sup)

MUT = TEST.copy()
MUT.loc[MUT.index[0], "minutes"] = 999.0
raises("I4 a mutated frame is refused", v10.FrameBindingError, v10.run_player_fold,
       TRAIN, MUT, FOLD, config_hash=CFG, snapshot_hash=SNAP,
       snapshot_manifest=MAN, universe=UNI)

NULLSWAP = TEST.copy()
NULLSWAP["feature_asof"] = NULLSWAP["feature_asof"].astype(object)
NULLSWAP.loc[NULLSWAP.index[0], "feature_asof"] = None
raises("I4 a null-for-value swap is refused", v10.FrameBindingError,
       v10.run_player_fold, TRAIN, NULLSWAP, FOLD, config_hash=CFG,
       snapshot_hash=SNAP, snapshot_manifest=MAN, universe=UNI)

# the three /2 domain collisions, now refused rather than silently hashed
INTCOL = TEST.copy()
INTCOL[1] = 1
raises("I4 an integer-labelled column is refused (v9 DROPPED it from the hash)",
       v10.FrameBindingError, v10.run_player_fold, TRAIN, INTCOL, FOLD,
       config_hash=CFG, snapshot_hash=SNAP, snapshot_manifest=MAN, universe=UNI)
LISTCELL = TEST.copy()
LISTCELL["feature_asof"] = LISTCELL["feature_asof"].astype(object)
LISTCELL.at[LISTCELL.index[0], "feature_asof"] = [1, 2]
raises("I4 a container cell is refused", v10.FrameBindingError, v10.run_player_fold,
       TRAIN, LISTCELL, FOLD, config_hash=CFG, snapshot_hash=SNAP,
       snapshot_manifest=MAN, universe=UNI)

# zero fits before rejection -- the property that makes the ordering meaningful
_fits = {"n": 0}
_real = cbs_v8.logistic_fit
try:
    cbs_v8.logistic_fit = lambda *a, **k: (_fits.__setitem__("n", _fits["n"] + 1)
                                           or _real(*a, **k))
    for frame in (MUT, INTCOL, LISTCELL):
        try:
            v10.run_player_fold(TRAIN, frame, FOLD, config_hash=CFG,
                                snapshot_hash=SNAP, snapshot_manifest=MAN,
                                universe=UNI)
        except Exception:
            pass
    check("I4 ZERO fits ran before any of the three rejections", _fits["n"] == 0,
          f"{_fits['n']} fits ran first")
finally:
    cbs_v8.logistic_fit = _real

raises("I4 a wrong but valid 64-hex config digest is refused",
       v10.AdapterBoundaryError, v10.run_player_fold, TRAIN, TEST, FOLD,
       config_hash="c" * 64, snapshot_hash=SNAP, snapshot_manifest=MAN, universe=UNI)
raises("I4 a real run without artifact_root is refused", v10.AdapterBoundaryError,
       v10.require_registered_identity, v10.REGISTERED_CONFIG_HASH, SNAP, MAN,
       frames={"train": TRAIN}, synthetic=False)


# --------------------------------------------------------------------------
# I5 -- the config helper, and the earlier arms still intact
# --------------------------------------------------------------------------

check("I5 the config helper defaults to the v10 arm",
      v10.recompute_registered_config_hash.__module__ == "cbs_v10")
try:
    _r = v10.recompute_registered_config_hash()
    check("I5 the v10 config digest recomputes from the registry",
          _r == v10.REGISTERED_CONFIG_HASH,
          f"registry {_r} vs module {v10.REGISTERED_CONFIG_HASH}")
    check("I5 and it is not v9's digest", _r != cbs_v9.REGISTERED_CONFIG_HASH)
except v10.AdapterBoundaryError as exc:
    check("I5 the v10 config digest recomputes from the registry", False, str(exc))

check("I5 v8 and v9 remain importable and unchanged",
      cbs_v8.ARM_ID == "contract_baseline_suite_v8"
      and cbs_v9.ARM_ID == "contract_baseline_suite_v9"
      and cbs_v9.REGISTERED_CONFIG_HASH
      == "aa4b3cc53785b9004b88aed748e12e7e4a803c3665c298a6cdd2b0523f6ee260")
check("I5 v9's own config digest still recomputes despite the appended erratum",
      cbs_v9.recompute_registered_config_hash() == cbs_v9.REGISTERED_CONFIG_HASH,
      "the erratum carries a distinct experiment_id precisely so it cannot shadow "
      "the record it corrects")

print(f"{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAIL  {f}")
sys.exit(1 if FAILED else 0)
