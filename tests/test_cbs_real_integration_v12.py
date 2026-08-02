#!/usr/bin/env python
"""test_cbs_real_integration_v12.py — the REAL fit boundary, entered.

WHY THIS FILE EXISTS SEPARATELY FROM `test_cbs_real_integration_v11.py`
------------------------------------------------------------------------

v11's real gate is the reason contract v4 can be trusted: it builds both real folds for every
season 2021-2026, proves universe coverage by `row_uid` set equality, and binds twenty-four
frame digests into a `cbs_snapshot_manifest/5`. It passes 268/268, and it is unchanged and
still runs.

It also stops exactly there. A bound manifest is the LAST thing that happens before a runner is
entered, and nothing in the v11 gate enters one. That is why six defects lived inside
`cbs_v11._run` behind a green 27-check gate, and why running the corrected boundary on real
frames immediately surfaced three more that no synthetic fixture could have shown.

So this file crosses the boundary the v11 gate stops at:

  R0  the checkout: the five required artifacts exist, are attested, and their recorded digests
      equal the bytes on disk
  R1  a per-fold `/5` manifest is BUILT from the real 2021 team fold's actual train, test and
      universe frames, and the identity is DERIVED from it
  R2  the real 2021 TEAM fold is run END TO END through `cbs_v12.run_team_fold` on the real
      path — real manifest stamps, real artifact bytes, real frame digests, real feature-source
      timestamps — and all eight v12-owned receipts pass
  R3  it is a COLD START and it fitted nothing: 2021 is the first contracted season, its
      training window is empty, every component is a declared constant, and a runtime sentinel
      installed before the first real byte was read never fires
  R4  the real PLAYER fold is BLOCKED, and the block is measured rather than described: the
      inherited ordering key is team-blind, the affected obligations are exactly the contract's
      28 dual-team rows in all six seasons, adding `team_id` resolves every one, and zero
      estimator calls run before the refusal
  R5  real-path negative controls: a tampered artifact digest, an absent `artifact_root`, a
      stale frame digest and a synthetic-stamped manifest are each refused against real bytes
  Z6  ZERO fits, predictions, scores or evaluations, proved by the runtime sentinel and by an
      inspection of what the emitted rows actually contain

WHAT IS AND IS NOT DONE HERE
----------------------------

The real team fold DOES emit prediction rows. They are the inherited runner's DECLARED CONSTANTS
— the same value on every row, because there is no prior season to learn from — and R3 asserts
that with a sentinel that would have fired on any estimator call. No coefficient is fitted, no
forecast is compared to any outcome, and no accuracy, coverage-quality or profitability figure
is computed anywhere in this file. "Coverage" means OBLIGATION COMPLETENESS throughout.

Reading the real artifacts is the point of the file and is authorized. Handing them to an
estimator is not, and Z6 exists to prove it did not happen.

Run as a script (this repository has no pytest installed)::

    python tests/test_cbs_real_integration_v12.py
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
# An AST scan can prove no fitting call is WRITTEN on the path; it cannot prove none was
# EXECUTED. These wrappers answer the executed question directly. They are installed before a
# single real byte is read, they delegate to the real function so nothing is disabled, and Z6
# asserts that none of them ever fired.
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


for _nm in ("logistic_fit", "logistic_predict", "fit_side_maps", "select_alpha_bound"):
    if hasattr(gen, _nm):
        setattr(gen, _nm, _sentinel(_nm, getattr(gen, _nm)))

import cbs_v8                                                   # noqa: E402

for _nm in ("logistic_fit", "logistic_predict", "fit_side_maps", "select_alpha_bound"):
    if hasattr(cbs_v8, _nm) and hasattr(gen, _nm):
        setattr(cbs_v8, _nm, getattr(gen, _nm))

import cbs_obligation_key as obk                                # noqa: E402
import cbs_provenance_v4 as prov4                               # noqa: E402
import cbs_real_frames_v3 as rf3                                # noqa: E402
import cbs_v12 as v12                                           # noqa: E402
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


# ==========================================================================
print("\nR0  the checkout: five required artifacts, attested, matching their bytes")
# ==========================================================================
status = prov4.attestation_status(ROOT, prov4.CBS_REQUIRED_ARTIFACTS)
check("R0 exactly five artifacts are required", len(prov4.CBS_REQUIRED_ARTIFACTS) == 5,
      prov4.CBS_REQUIRED_ARTIFACTS)
for rel in sorted(prov4.CBS_REQUIRED_ARTIFACTS):
    e = status[rel]
    check(f"R0 {rel} exists, is attested and matches its bytes",
          e["exists"] and e["manifest_valid"] and e["hash_ok"] is not False,
          e.get("problem"))
check("R0 the contract directory is prediction_contract_v4, unchanged by this arm",
      prov4.CONTRACT_DIR == "experiments/prediction_contract_v4")


# ==========================================================================
print("\nR1  a PER-FOLD /5 manifest, built from the frames the run will consume")
# ==========================================================================
t0 = time.time()
TEAM = rf3.build_team_frame(SEASON, ROOT, require_attested=True)
BUILD_SECONDS = time.time() - t0
TR, TE, UNI = TEAM["train"], TEAM["test"], TEAM["universe"]

check(f"R1 the real {SEASON} team fold builds from attested artifacts", len(TE) > 0,
      f"train={len(TR)} test={len(TE)} universe={len(UNI)}")
check("R1 it is a COLD START: the training window is genuinely empty", len(TR) == 0,
      f"{len(TR)} training rows")
check("R1 the universe and the test frame name the same obligations",
      set(UNI["row_uid"]) == set(TE["row_uid"]),
      f"{len(set(UNI['row_uid']) ^ set(TE['row_uid']))} keys differ")

MAN = v12.build_fold_manifest(TR, TE, UNI, root=ROOT)
SNAP = v12.snapshot_identity(MAN)

check("R1 the manifest declares cbs_snapshot_manifest/5",
      MAN["schema"] == "cbs_snapshot_manifest/5", MAN["schema"])
check("R1 it names EXACTLY this fold's three frames and no others",
      sorted(MAN["frames"]) == ["test", "train", "universe"], sorted(MAN["frames"]))
for role, frame in (("train", TR), ("test", TE), ("universe", UNI)):
    check(f"R1 the declared {role} digest is that frame's cbs_frame_identity/3 digest",
          MAN["frames"][role] == frame_digest(frame, mode=REAL_PATH_MODE))
check("R1 the manifest carries the real artifact digests, not placeholders",
      all(MAN["artifacts"][rel]["sha256"] == status[rel]["sha256"]
          for rel in prov4.CBS_REQUIRED_ARTIFACTS))
check("R1 it passes the REAL-manifest stamps rather than merely parsing",
      prov4.require_real_snapshot_manifest(MAN)["ok"])
check("R1 the snapshot identity is DERIVED from it, and is 64 hex characters",
      isinstance(SNAP, str) and len(SNAP) == 64)


# ==========================================================================
print("\nR2  the real TEAM fold, run END TO END through the real v12 boundary")
# ==========================================================================
RES = v12.run_team_fold(TR, TE, FOLD,
                        config_hash=v12.REGISTERED_CONFIG_HASH, snapshot_hash=SNAP,
                        snapshot_manifest=MAN, universe=UNI,
                        synthetic=False, artifact_root=ROOT)

check("R2 the run passed every v12 receipt", RES["scoring_permitted"] is True,
      f"failed={RES['failed_receipts']} inherited={RES['inherited_receipts']}")
for name in v12.V12_REQUIRED_RECEIPTS:
    r = RES["receipts"][name]
    check(f"R2 {name} passes and was recomputed by v12",
          r.get("ok") and r.get("recomputed_by") == v12.ARM_ID,
          r.get("problems"))

IB = RES["receipts"]["identity_binding"]
check("R2 the identity binding ran on the REAL path, not a synthetic one",
      IB["synthetic"] is False)
check("R2 it verified the real-manifest stamps",
      IB["real_snapshot_manifest"] is not None and IB["real_snapshot_manifest"]["ok"])
check("R2 it verified all five artifact digests against the BYTES ON DISK",
      IB["artifact_bytes"]["ok"] and IB["artifact_bytes"]["n_verified"] == 5,
      IB["artifact_bytes"])
check("R2 it recomputed the registered config hash from the registry",
      IB["config_hash_recomputed_from_registry"] == v12.REGISTERED_CONFIG_HASH)
check("R2 it bound every supplied frame's digest",
      sorted(IB["frame_binding"]["per_frame"]) == ["test", "train", "universe"]
      and all(p["match"] for p in IB["frame_binding"]["per_frame"].values()))

SP = RES["receipts"]["source_provenance"]
check("R2 both frames' registered feature sources were validated",
      SP["frames_validated"] == ["test", "train"], SP["frames_validated"])
check("R2 the empty training frame was schema-validated, not skipped",
      SP["train_frame_empty"] is True
      and SP["per_frame"]["train"]["row_level_clauses_vacuous"] is True
      and SP["per_frame"]["train"]["schema_validated"] is True)
check("R2 no test row read a feature source at or after its own cutoff",
      SP["per_frame"]["test"]["n_at_cutoff"] == 0
      and SP["per_frame"]["test"]["n_after_cutoff"] == 0)
check("R2 the declared-feature_asof fallback was not on this path",
      SP["declared_feature_asof_fallback_reachable"] is False and SP["synthetic"] is False)

PV = RES["receipts"]["prediction_validation"]
check("R2 the prediction validator RAN, under contract_v4_strict/1",
      PV["validator"] == "contract_v4_strict/1" and bool(PV["per_target"]))
check("R2 the team target's key rule is the tg_ rule, and it was enforced here",
      PV["require_declared_key"] is False and PV["key_rule"] == v12.TEAM_KEY_ID
      and PV["team_universe_key"]["ok"])
check("R2 obligation completeness is EXACT over the real universe",
      RES["receipts"]["coverage"]["per_target"][v12.TEAM_TARGET]["n_covered"] == len(UNI),
      RES["receipts"]["coverage"]["per_target"])

PH = RES["receipts"]["provenance_history"]
SC = RES["provenance_sidecar"]
check("R2 the sidecar digest names the RESTAMPED sidecar the run returned",
      PH["digest"] == v12.sidecar_identity(SC) == RES["provenance_sidecar_digest"])
check("R2 and it is taken under cbs_sidecar_identity/2",
      PH["digest_schema"] == "cbs_sidecar_identity/2")
check("R2 the inherited digest could NOT have produced it on this real sidecar",
      "forecast_cutoff" in PH["probe_substituted_columns"]
      or "feature_asof" in PH["probe_substituted_columns"],
      PH["probe_substituted_columns"])
for tgt, p in RES["predictions"].items():
    check(f"R2 {tgt}: every emitted row carries the v12 arm and identity",
          (p["arm_id"] == v12.ARM_ID).all()
          and (p["config_hash"] == v12.REGISTERED_CONFIG_HASH).all()
          and (p["data_snapshot_hash"] == SNAP).all())
check("R2 the emitted sidecar carries the same identity",
      (SC["arm_id"] == v12.ARM_ID).all()
      and (SC["data_snapshot_hash"] == SNAP).all())
check("R2 the inner receipts are retained but took no part in the verdict",
      RES["inner_receipts"]["identity_binding"]["config_hash"] == cbs_v8.SYNTHETIC_CONFIG_HASH
      and RES["receipts"]["identity_binding"]["config_hash"] == v12.REGISTERED_CONFIG_HASH)
check("R2 the legacy identity shim declares itself unfit for a real boundary",
      RES["legacy_identity_shim"] == "cbs_legacy_identity_shim/1")


# ==========================================================================
print("\nR3  it is a cold start, and it fitted NOTHING")
# ==========================================================================
check("R3 the run reports itself degenerate with an empty training window",
      RES["diagnostics"]["degenerate"] is True, RES["diagnostics"]["reason"])
COMPONENTS = sorted({c for p in RES["predictions"].values() for c in p["component_id"].unique()})
check("R3 every emitted component is a DECLARED CONSTANT, not a fitted model",
      all(c.endswith("/declared_constant") for c in COMPONENTS), COMPONENTS)
check("R3 every emitted row sits at the MAXIMUM fallback level -- nothing was estimated",
      all(set(p["fallback_level"].unique()) == {cbs_v8.MAX_FALLBACK_LEVEL}
          for p in RES["predictions"].values()),
      {t: sorted(p["fallback_level"].unique()) for t, p in RES["predictions"].items()})
check("R3 every emitted point forecast is the SAME value, as a constant must be",
      all(p["pred_point"].nunique(dropna=True) <= 1 for p in RES["predictions"].values()))
check("R3 one model_hash covers every row, because one declared state produced them all",
      all(p["model_hash"].nunique() == 1 for p in RES["predictions"].values()))
check("R3 the runtime sentinel never fired: zero estimator calls on the real path",
      FIT_CALLS == [], FIT_CALLS)
# a label the emitted rows do NOT support, recorded so nobody later reads it as one they do.
# `is_cold_start` marks an obligation with no prior admitted same-season team game -- 12 season
# openers. It is NOT a statement that no model was fitted; 406 rows carry False while the run
# fitted nothing at all. The no-fit claim rests on the sentinel, the fallback level and the
# declared-constant component, never on this column.
_cold = RES["predictions"][v12.TEAM_TARGET]["is_cold_start"]
check("R3 is_cold_start is a PRIOR-GAME flag, not a no-fit flag, and does not claim to be",
      bool(_cold.any()) and not bool(_cold.all()),
      f"{int(_cold.sum())} of {len(_cold)} rows flagged")


# ==========================================================================
print("\nR4  BLOCKER: the real PLAYER fold cannot enter the modelling core")
# ==========================================================================
t1 = time.time()
PLAYER = rf3.build_player_frame(SEASON, ROOT, require_attested=True)
BUILD_SECONDS += time.time() - t1
PTR, PTE, PUNI = PLAYER["train"], PLAYER["test"], PLAYER["universe"]
check(f"R4 the real {SEASON} player FRAME still builds -- v11's correction holds",
      len(PTE) > 0 and PTE["row_uid"].is_unique,
      f"train={len(PTR)} test={len(PTE)}")

PMAN = v12.build_fold_manifest(PTR, PTE, PUNI, root=ROOT)
PSNAP = v12.snapshot_identity(PMAN)
check("R4 and it can still be identity-bound into a /5 manifest",
      sorted(PMAN["frames"]) == ["test", "train", "universe"])

_before = len(FIT_CALLS)
refuses("R4 but the RUNNER refuses it, at the v12 boundary, before delegation",
        lambda: v12.run_player_fold(
            PTR, PTE, FOLD, config_hash=v12.REGISTERED_CONFIG_HASH, snapshot_hash=PSNAP,
            snapshot_manifest=PMAN, universe=PUNI, synthetic=False, artifact_root=ROOT),
        contains="TEAM-BLIND")
check("R4 and zero estimator calls ran before the refusal", len(FIT_CALLS) == _before,
      FIT_CALLS[_before:])

REP = v12.order_collisions(PTE)
check("R4 the inherited ordering key is the team-blind tuple",
      REP["ordering_key"] == ["player_id", "season", "forecast_cutoff", "game_id"])
check(f"R4 season {SEASON}'s player fold collides on exactly 2 rows in 1 group",
      REP["n_colliding_rows"] == 2 and REP["n_groups"] == 1, REP)
check("R4 adding team_id resolves them", REP["resolved_by_team_id"] is True)

# measured over the WHOLE contract, not just this fold: the blocker is not seasonal
PG = pd.read_parquet(ROOT / prov4.PLAYER_GAME)
KEY = ["player_id", "season", "forecast_cutoff", "game_id"]
DUP = PG.duplicated(subset=KEY, keep=False)
BY_SEASON = {int(s): int(n) for s, n in PG.loc[DUP].groupby("season").size().items()}
check("R4 across the whole contract the ordering key hides exactly 28 obligations",
      int(DUP.sum()) == 28, int(DUP.sum()))
check("R4 in exactly 14 groups", int(PG.loc[DUP].groupby(KEY).ngroups) == 14)
check("R4 in EVERY season 2021-2026, so no real player fold can run",
      sorted(BY_SEASON) == [2021, 2022, 2023, 2024, 2025, 2026], BY_SEASON)
check("R4 they are exactly the rows sharing a legacy player_game_uid",
      set(PG.loc[DUP, "row_uid"])
      == set(PG.loc[PG["player_game_uid"].duplicated(keep=False), "row_uid"]))
check("R4 and team_id resolves all 28, leaving none",
      int(PG.duplicated(subset=KEY + ["team_id"], keep=False).sum()) == 0)
check("R4 the canonical key itself is still unique -- the CONTRACT is not at fault",
      PG["row_uid"].is_unique and len(PG) == 35627, len(PG))
check("R4 the defect is in the inherited generator, which is registered and immutable",
      "cbs_generator.py" in [Path(p).name for p in
                             [gen.__file__]] or gen.__name__ == "cbs_generator")


# ==========================================================================
print("\nR5  real-path negative controls, against real bytes")
# ==========================================================================
_tampered = {**MAN, "artifacts": {**MAN["artifacts"]}}
_first = sorted(_tampered["artifacts"])[0]
_tampered["artifacts"][_first] = {**_tampered["artifacts"][_first], "sha256": "0" * 64}
refuses("R5 a declared artifact digest that does not match disk is refused",
        lambda: v12.run_team_fold(
            TR, TE, FOLD, config_hash=v12.REGISTERED_CONFIG_HASH,
            snapshot_hash=v12.snapshot_identity(_tampered), snapshot_manifest=_tampered,
            universe=UNI, synthetic=False, artifact_root=ROOT),
        contains="do not match their bytes on disk")

refuses("R5 a real run that supplies no artifact_root is refused",
        lambda: v12.run_team_fold(
            TR, TE, FOLD, config_hash=v12.REGISTERED_CONFIG_HASH, snapshot_hash=SNAP,
            snapshot_manifest=MAN, universe=UNI, synthetic=False),
        contains="artifact_root")

_mutated = TE.copy()
_num = [c for c in _mutated.columns if pd.api.types.is_numeric_dtype(_mutated[c])]
_mutated.loc[_mutated.index[0], _num[0]] = -12345
refuses("R5 a mutated frame against the same manifest is refused (stale frame digest)",
        lambda: v12.run_team_fold(
            TR, _mutated, FOLD, config_hash=v12.REGISTERED_CONFIG_HASH, snapshot_hash=SNAP,
            snapshot_manifest=MAN, universe=UNI, synthetic=False, artifact_root=ROOT),
        contains="does not match the manifest")

_synth = {**MAN, "synthetic": True, "real_path_permitted": False,
          "why_not_real": "stamped for this control"}
refuses("R5 a manifest stamped real_path_permitted=False is refused by the real run",
        lambda: v12.run_team_fold(
            TR, TE, FOLD, config_hash=v12.REGISTERED_CONFIG_HASH,
            snapshot_hash=v12.snapshot_identity(_synth), snapshot_manifest=_synth,
            universe=UNI, synthetic=False, artifact_root=ROOT),
        contains="must not be consumed")

refuses("R5 the SYNTHETIC config digest is refused on the real path",
        lambda: v12.run_team_fold(
            TR, TE, FOLD, config_hash=v12.SYNTHETIC_CONFIG_HASH, snapshot_hash=SNAP,
            snapshot_manifest=MAN, universe=UNI, synthetic=False, artifact_root=ROOT),
        contains="config_hash")

_reused = v12.build_fold_manifest(TR, TE, None, root=ROOT)
refuses("R5 a manifest built for a DIFFERENT fold shape is refused",
        lambda: v12.run_team_fold(
            TR, TE, FOLD, config_hash=v12.REGISTERED_CONFIG_HASH,
            snapshot_hash=v12.snapshot_identity(_reused), snapshot_manifest=_reused,
            universe=UNI, synthetic=False, artifact_root=ROOT),
        contains="does not describe THIS fold")


# ==========================================================================
print("\nZ6  zero fits, predictions against outcomes, scores or evaluations")
# ==========================================================================
check("Z6 the runtime sentinel never fired, across every real call in this file",
      FIT_CALLS == [], FIT_CALLS)
check("Z6 no estimator library is loaded in this process",
      not ({"sklearn", "catboost", "lightgbm", "xgboost", "tabpfn", "statsmodels"}
           & set(sys.modules)),
      sorted({"sklearn", "catboost", "lightgbm", "xgboost", "tabpfn", "statsmodels"}
             & set(sys.modules)))
check("Z6 the run computed no accuracy, coverage-quality or profitability figure",
      not any(k in RES for k in ("accuracy", "auc", "log_loss", "brier", "profit", "roi")))
check("Z6 'coverage' here is an obligation count, and the receipt says so",
      set(RES["receipts"]["coverage"]["per_target"][v12.TEAM_TARGET])
      >= {"n_required", "n_covered", "n_emitted"})
check("Z6 no outcome column was read back against any forecast",
      "team_points" not in set().union(*(set(p.columns) for p in RES["predictions"].values())))
check("Z6 the module's own scoring note states nothing is scored",
      "computes no accuracy" in RES["scoring_note"])
check("Z6 the canonical key rule is unchanged from v11",
      obk.OBLIGATION_KEY_ID == "cbs_obligation_key/1"
      and RES["obligation_key_id"] == obk.OBLIGATION_KEY_ID)


print(f"\n    total runtime {time.time() - T_START:.0f}s "
      f"(real frame builds: {BUILD_SECONDS:.0f}s)")
print(f"\n{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAILED  {f}")
sys.exit(1 if FAILED else 0)
