#!/usr/bin/env python
"""test_cbs_v12.py — the fit boundary, exercised rather than described.

WHY THIS FILE EXISTS
--------------------

`contract_baseline_suite_v11` shipped a green 27-check gate over a runner that could not
execute. Every defect the supervisor found in `cbs_v11._run` — and the three more found while
correcting it — survived for one reason: **no test ever called `cbs_v11.run_player_fold` or
`cbs_v11.run_team_fold` with a universe.** The v11 real gate builds real frames and stops at a
bound snapshot manifest, and the v11 unit suite tests `snapshot_identity` and
`require_canonical_keys` in isolation. Between those two lies the function a chronological OOF
would actually call, and nothing entered it.

So section 6 of this file RUNS the runner, nondegenerately, all the way to emitted predictions
through a fitted Stage-A ridge logistic, and asserts the eight receipts against the artifacts
actually returned. Section 2 pins each v11 defect as a standing regression, so a future arm
cannot quietly reintroduce one. Section 7 proves each pre-fit control rejects with ZERO fits
having run first — the property that makes the ordering of the checks meaningful rather than
decorative.

Everything fitted here is fitted on SYNTHETIC fixtures. Nothing in this file reads a real
artifact except the registry, and nothing is scored against any outcome.

Run as a script (this repository has no pytest installed)::

    python tests/test_cbs_v12.py
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import cbs_generator as gen                     # noqa: E402
import cbs_obligation_key as obk                # noqa: E402
import cbs_provenance_v3 as prov3               # noqa: E402
import cbs_provenance_v4 as prov4               # noqa: E402
import cbs_v8                                   # noqa: E402
import cbs_v10                                  # noqa: E402
import cbs_v11                                  # noqa: E402
import cbs_v12 as v12                           # noqa: E402
import contract_validator_v4_strict as cv4      # noqa: E402
from cbs_identity_v3 import (FRAME_IDENTITY_SCHEMA, REAL_PATH_MODE,  # noqa: E402
                             frame_digest, frames_digest)
from cbs_v7 import AdapterBoundaryError, SIDECAR_COLS   # noqa: E402

REGISTRY = REPO / "experiments" / "registry.jsonl"

_n = 0


def ok(cond, label):
    global _n
    _n += 1
    if not cond:
        print(f"  FAIL {label}")
        raise SystemExit(1)
    print(f"  ok   {label}")


def raises(fn, label, contains=None, exc=Exception):
    global _n
    _n += 1
    try:
        fn()
    except exc as e:                                             # noqa: BLE001
        if contains and contains.lower() not in str(e).lower():
            print(f"  FAIL {label} -- raised but message lacked {contains!r}: {e}")
            raise SystemExit(1)
        print(f"  ok   {label}")
        return
    print(f"  FAIL {label} -- did not raise")
    raise SystemExit(1)


def _registry_records():
    return [json.loads(ln) for ln in REGISTRY.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


# =========================================================================== #
print("\n1. registration is append-only and both new records are present")
# =========================================================================== #
recs = _registry_records()
ids = [r.get("experiment_id") for r in recs]

# Bound to INDICES, never to the tail. `recs[-1]` asserts "this arm is the newest record", which
# is false the moment the next arm appends -- and that is exactly how v11's own suite came to
# fail this gate, defect 10 below. The registry may grow; v12's record does not move.
V12_INDEX, V11_ERRATUM_INDEX = 92, 91

ok(len(recs) >= 93, f"registry holds at least the 93 records v12 registered (got {len(recs)})")
ok(ids[V12_INDEX] == "contract_baseline_suite_v12", "v12's record sits at its registered index")
ok(ids[V11_ERRATUM_INDEX] == "contract_baseline_suite_v11__erratum_20260802",
   "the v11 erratum immediately precedes it")
ok(ids.count("contract_baseline_suite_v12") == 1, "v12's own record appears exactly once")
ok(ids.count("contract_baseline_suite_v11") == 1, "v11's own record appears exactly once")
ok(recs[V11_ERRATUM_INDEX]["kind"] == "erratum"
   and recs[V11_ERRATUM_INDEX]["errata_for"] == "contract_baseline_suite_v11",
   "the erratum is kind=erratum and names v11")
ok(recs[V11_ERRATUM_INDEX]["prior_records_mutated"] is False,
   "the erratum mutates no prior record")
ok(len(recs[V11_ERRATUM_INDEX]["corrections"]) == 6,
   f"the erratum records all six v11 runner defects "
   f"(got {len(recs[V11_ERRATUM_INDEX]['corrections'])})")

rec12 = recs[V12_INDEX]
ok(rec12["kind"] == "experiment", "v12 is kind=experiment")
ok(rec12["primary_metric"].endswith("NOT_YET_COMPUTED"),
   "v12's primary_metric is explicitly NOT_YET_COMPUTED")
ok(rec12["extra"]["no_real_model_result"] is True, "v12 declares no real model result")
ok(rec12["extra"]["computed_nothing_on_real_data"] is False,
   "v12 declares computed_nothing_on_real_data FALSE -- it does read and build real data")

FC = rec12["extra"]["frozen_config"]
ok(FC["row_universe"] == "prediction_contract_v4" and FC["row_universe_unchanged"] is True,
   "v12 consumes prediction_contract_v4 unchanged")
ok(FC["v11_left_immutable"] and FC["v10_left_immutable"]
   and FC["prediction_contract_v4_left_immutable"],
   "v11, v10 and contract v4 are all declared immutable")
ok(FC["snapshot_manifest_schema"] == "cbs_snapshot_manifest/5"
   and FC["snapshot_manifest_schema_unchanged"] is True,
   "the /5 manifest contract is inherited, not re-minted for a caller's defect")

# config hashes: v12's recomputes, and no earlier arm is shadowed by the new records
ok(v12.recompute_registered_config_hash() == v12.REGISTERED_CONFIG_HASH,
   "v12's registered config hash recomputes from the registry")
for mod in (cbs_v11, cbs_v10):
    ok(mod.recompute_registered_config_hash() == mod.REGISTERED_CONFIG_HASH,
       f"{mod.ARM_ID}'s config hash still recomputes despite the appended records")
ok(cbs_v8.recompute_registered_config_hash(experiment_id=cbs_v8.ARM_ID)
   == cbs_v8.REGISTERED_CONFIG_HASH, "v8's config hash still recomputes")
ok(v12.REGISTERED_CONFIG_HASH != cbs_v11.REGISTERED_CONFIG_HASH,
   "v11 and v12 are different registered configurations")
raises(lambda: v12.recompute_registered_config_hash(
    experiment_id="contract_baseline_suite_v11__erratum_20260802"),
    "an erratum record has no frozen_config and cannot be config-hashed",
    contains="frozen_config")

# the registry file's committed prefix is untouched
_raw = REGISTRY.read_text(encoding="utf-8").splitlines()
ok(len(_raw) >= 93 and all(_raw[i].strip() for i in range(91)),
   "the 91 prior registry lines are still present and non-empty")

# defect 10, found by running this arm's own gate: v11's suite asserted `recs[-1]` and pinned
# len(recs) == 91, i.e. "v11 is the NEWEST record" -- which an append-only registry falsifies on
# the very next arm. It failed the moment v12 registered. Rebound there to registered indices,
# and written that way here from the start.
_v11_test = (REPO / "tests" / "test_cbs_v11.py").read_text(encoding="utf-8")
ok("v11 = recs[V11_INDEX]" in _v11_test
   and not any(ln.strip().startswith("ok(") and "recs[-" in ln
               for ln in _v11_test.splitlines()),
   "v11's suite no longer identifies its own record by tail position")
ok("len(recs) >= 91" in _v11_test,
   "and no longer forbids the registry from growing")


# =========================================================================== #
print("\n2. the six v11 runner defects, pinned as standing regressions")
# =========================================================================== #
# (1) require_registered_identity documented three checks it never called
_v11_src = (REPO / "cbs_v11.py").read_text(encoding="utf-8")
_v11_ident = _v11_src.split("def require_registered_identity", 1)[1].split("\ndef ", 1)[0]
for missing in ("require_real_snapshot_manifest", "verify_artifact_bytes", "bind_frames"):
    ok(missing not in _v11_ident,
       f"v11's identity binder never calls {missing} -- the defect is real, not misread")
_v12_src = (REPO / "cbs_v12.py").read_text(encoding="utf-8")
_v12_ident = _v12_src.split("def require_registered_identity", 1)[1].split("\ndef ", 1)[0]
for present in ("require_real_snapshot_manifest", "verify_artifact_bytes", "bind_frames",
                "require_canonical_keys"):
    ok(present in _v12_ident, f"v12's identity binder calls {present}")

# (2) the v11 shim declares no frames
_v11_run = _v11_src.split("def _run(", 1)[1].split("\ndef ", 1)[0]
_shim = _v11_run.split("shim = {", 1)[1].split("}", 1)[0]
ok('"frames"' not in _shim,
   "v11's delegation shim declares no 'frames' member, so the inherited binder refuses it")

# (5) and it could not have reached that refusal anyway: the v10 wrapper's exact artifact set
#     names the v3 contract directory, and a v4 manifest names the v4 one
ok(set(prov3.CBS_REQUIRED_ARTIFACTS) != set(prov4.CBS_REQUIRED_ARTIFACTS),
   "the v3 and v4 required artifact sets are different sets")
raises(lambda: prov3.require_exact_artifact_set(list(prov4.CBS_REQUIRED_ARTIFACTS),
                                                where="probe"),
       "a contract-v4 artifact set is REFUSED by the v10 wrapper's exact-five check",
       exc=prov3.ArtifactSetError)
_v12_run = _v12_src.split("\ndef _run(", 1)[1].split("\ndef ", 1)[0]
ok(v12._core is cbs_v8
   and "_core.run_player_fold" in _v12_run and "_core.run_team_fold" in _v12_run
   and "_v10.run_" not in _v12_run,
   "v12 therefore delegates to the modelling core directly, not through the v10 wrapper")
ok(v12.FRAME_BINDING_SCHEMA == cbs_v10.FRAME_BINDING_SCHEMA == "cbs_frame_binding/3",
   "and still binds frames under the v10-era cbs_frame_identity/3 contract")

# (3) v11 copies the inner receipts and replaces only prediction_validation
ok("receipts = dict(out[\"receipts\"])" in _v11_run
   and "receipts[\"identity_binding\"]" not in _v11_run
   and "receipts[\"provenance_history\"]" not in _v11_run,
   "v11 copies the inner receipts and never reinstalls identity_binding or provenance_history")

# (4) v11 delegates with synthetic=True, which defaults declared Stage-A defaults ON
ok("synthetic=True" in _v11_run and "allow_declared_defaults" not in _v11_run,
   "v11 delegates synthetic=True and never forces declared Stage-A defaults off")
import inspect  # noqa: E402
_sig = inspect.signature(cbs_v8.run_player_fold)
ok(_sig.parameters["allow_declared_defaults"].default is None,
   "the inherited player runner defaults allow_declared_defaults to None...")
ok("allow_declared_defaults = bool(synthetic)" in inspect.getsource(cbs_v8.run_player_fold),
   "...which it then resolves to bool(synthetic), i.e. True under v11's delegation")

# (6) v11 calls the /4 validator without the required keyword-only expected_fold_id
_v4sig = inspect.signature(cv4.validate_arm_output_v4)
ok(_v4sig.parameters["expected_fold_id"].default is inspect.Parameter.empty,
   "validate_arm_output_v4 declares expected_fold_id keyword-only and REQUIRED")
_call = _v11_run.split("validate_arm_output_v4(", 1)[1].split(")", 1)[0]
ok("expected_fold_id" not in _call,
   "v11's call omits it, so any v11 run with a universe raises TypeError before receipting")
ok("expected_fold_id=fold_id" in _v12_src, "v12 passes expected_fold_id")


# =========================================================================== #
print("\n3. the /5 manifest boundary and the PER-FOLD frame map")
# =========================================================================== #
ok(v12.SNAPSHOT_MANIFEST_SCHEMA == "cbs_snapshot_manifest/5",
   "v12 binds cbs_snapshot_manifest/5, the schema v11 registered")
for s in ("cbs_snapshot_manifest/1", "cbs_snapshot_manifest/2",
          "cbs_snapshot_manifest/3", "cbs_snapshot_manifest/4"):
    ok(s in v12.REJECTED_MANIFEST_SCHEMAS, f"{s} is refused by v12")
raises(lambda: v12.snapshot_identity({"schema": "cbs_snapshot_manifest/4"}),
       "a genuine v10-era /4 manifest is refused by name", contains="REFUSED")

_f = pd.DataFrame({"row_uid": ["ob_a", "ob_b"]})
_man3 = {"frames": {"train": "0" * 64, "test": "1" * 64, "universe": "2" * 64}}
raises(lambda: v12.require_fold_frame_map(_man3, {"train": _f, "test": _f}),
       "a manifest declaring a frame the fold did not supply is refused",
       contains="declared-but-not-supplied")
raises(lambda: v12.require_fold_frame_map({"frames": {"train": "0" * 64}},
                                          {"train": _f, "test": _f}),
       "a manifest that omits a frame the fold DID supply is refused",
       contains="supplied-but-not-declared")
raises(lambda: v12.require_fold_frame_map({"frames": {"train": "0" * 64, "test": "1" * 64,
                                                      "holdout": "2" * 64}},
                                          {"train": _f, "test": _f}),
       "a manifest naming a role that is not a fold role is refused", contains="only")
raises(lambda: v12.require_fold_frame_map({"frames": {"test": "1" * 64}}, {"test": _f}),
       "a fold that supplies no train frame is refused", contains="train")
ok(v12.require_fold_frame_map({"frames": {"train": "0" * 64, "test": "1" * 64}},
                              {"train": _f, "test": _f, "universe": None})["ok"],
   "a manifest naming exactly the supplied frames passes, and a null role is not a frame")


# =========================================================================== #
print("\n4. fixtures: a nondegenerate synthetic fold that supplies every real input")
# =========================================================================== #
DERIVED = {"p_plays_prior", "player_gp_season"}
SUPPLIED_FEATURES = [c for c in gen.P_ACTIVE_FEATURES if c not in DERIVED]
TEAM = 1611661320


def pframe(season, n_players=8, n_dates=40, seed=3, team=TEAM):
    """A synthetic player fold carrying ALL twelve non-derived Stage-A inputs.

    v10's fixture supplied none of them and relied on declared defaults. v12 forbids those
    outright, so a fixture that does not supply them cannot reach a fit at all -- which is
    itself asserted in section 7.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(f"{season}-05-01", periods=n_dates, freq="D")
    rows = []
    for gi, d in enumerate(dates):
        for pid in range(n_players):
            ap = int(rng.random() < 0.6)
            mn = float(rng.uniform(9, 33)) if ap else 0.0
            cut = (d - pd.Timedelta(hours=6)).tz_localize("UTC")
            game = f"G{season}{gi:04d}"
            r = {"row_uid": obk.row_uid(1000 + pid, game, team),
                 "obligation_key_id": obk.OBLIGATION_KEY_ID,
                 "player_id": 1000 + pid, "team_id": team, "game_id": game,
                 "season": season, "game_date": d,
                 "forecast_cutoff": cut.isoformat(),
                 "feature_asof": (cut - pd.Timedelta(hours=6)).isoformat(),
                 "appeared": ap, "minutes": mn,
                 "fga": float(rng.poisson(max(mn, .1) * .35)) if ap else 0.0,
                 "points": float(rng.poisson(max(mn, .1) * .45)) if ap else 0.0}
            for k, lag in zip(v12.REQUIRED_PLAYER_FEATURE_SOURCES, (9, 8, 30)):
                r[k] = (cut - pd.Timedelta(hours=lag)).isoformat()
            for c in SUPPLIED_FEATURES:
                r[c] = float(rng.uniform(0, 1))
            r["days_since_last_appearance"] = float(rng.integers(1, 12))
            r["team_gp_season"] = float(gi)
            rows.append(r)
    return pd.DataFrame(rows).reset_index(drop=True)


FOLD = "season:2100"
TRAIN, TEST = pframe(2099), pframe(2100, seed=9, n_dates=14)
UNI = pd.DataFrame({"row_uid": TEST.row_uid, "obligation_key_id": obk.OBLIGATION_KEY_ID,
                    "player_id": TEST.player_id, "game_id": TEST.game_id,
                    "team_id": TEST.team_id, "fold_id": FOLD,
                    "forecast_cutoff": TEST.forecast_cutoff,
                    "appeared": TEST.appeared.astype(bool)})
for _t in v12.PLAYER_TARGETS:
    UNI[f"prediction_required__{_t}"] = True
    UNI[f"outcome_scoreable__{_t}"] = (UNI["appeared"] if _t != "p_active" else True)


def manifest(frames, **over):
    man = {"schema": prov4.SNAPSHOT_MANIFEST_SCHEMA,
           "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
           "frame_identity_mode": REAL_PATH_MODE,
           "obligation_key_id": obk.OBLIGATION_KEY_ID,
           "membership_rule_id": prov4.MEMBERSHIP_RULE_ID,
           "roster_binding_id": prov4.ROSTER_BINDING_ID,
           "captured_at": "2100-09-01T00:00:00+00:00",
           "artifacts": {rel: {"sha256": "a" * 64, "bytes": 1}
                         for rel in prov4.CBS_REQUIRED_ARTIFACTS},
           "frames": frames_digest(frames, mode=REAL_PATH_MODE)}
    man.update(over)
    return man


FRAMES = {"train": TRAIN, "test": TEST, "universe": UNI}
MAN = manifest(FRAMES)
SNAP = v12.snapshot_identity(MAN)
CFG = v12.SYNTHETIC_CONFIG_HASH

ok(len(TRAIN) == 320 and len(TEST) == 112, "the fixture folds are the sizes the run expects")
ok(TEST.row_uid.is_unique and TRAIN.row_uid.is_unique,
   "every fixture obligation is canonically keyed and unique")
ok(all(c in TEST.columns for c in SUPPLIED_FEATURES),
   "the fixture supplies every non-derived Stage-A feature, as the real path demands")


# =========================================================================== #
print("\n5. real-data semantics are forced, and the synthetic escapes are unreachable")
# =========================================================================== #
_src_receipt, _asof = v12.require_real_sources(
    TRAIN, TEST, v12.REQUIRED_PLAYER_FEATURE_SOURCES)
ok(_src_receipt["ok"] and _src_receipt["frames_validated"] == ["test", "train"],
   "both frames' feature sources are validated, and the receipt names both")
ok(_src_receipt["synthetic"] is False
   and _src_receipt["declared_feature_asof_fallback_reachable"] is False,
   "the receipt states the declared-feature_asof fallback is not on this path")
ok(_src_receipt["receipt"] == "cbs_source_provenance/2"
   and _src_receipt["recomputed_by"] == v12.ARM_ID,
   "the source receipt is v12's own /2, not the inherited /1")

# the inherited resolver's escape, demonstrated -- and then shown to be off v12's path
_no_src = TEST.drop(columns=list(v12.REQUIRED_PLAYER_FEATURE_SOURCES))
_asof2, _per = cbs_v8.resolve_fold_sources(
    TRAIN, _no_src, v12.REQUIRED_PLAYER_FEATURE_SOURCES, synthetic=True)
ok(_per == {}, "the INHERITED resolver falls back to a declared feature_asof and receipts "
              "nothing when a synthetic caller supplies no source columns")
raises(lambda: v12.require_real_sources(TRAIN, _no_src,
                                        v12.REQUIRED_PLAYER_FEATURE_SOURCES),
       "v12's resolver has no such branch and refuses the same frame",
       contains="source timestamp columns absent")

# an empty training frame is validated for SCHEMA, and says so rather than being skipped
_empty = TRAIN.iloc[0:0]
_r_empty, _ = v12.require_real_sources(_empty, TEST, v12.REQUIRED_PLAYER_FEATURE_SOURCES)
ok(_r_empty["ok"] and _r_empty["train_frame_empty"] is True
   and _r_empty["per_frame"]["train"]["row_level_clauses_vacuous"] is True,
   "an empty training frame is validated for schema and labelled vacuous, not omitted")
raises(lambda: v12.require_real_sources(
    _empty.drop(columns=["src_asof_roster"]), TEST, v12.REQUIRED_PLAYER_FEATURE_SOURCES),
    "an empty training frame missing a registered source column is still refused",
    contains="provenance schema")

# the team key rule, and the flag that waives only its declaration
_tu = pd.DataFrame({"row_uid": ["tg_a", "tg_b"], "team_id": [1, 2], "game_id": ["g", "g"]})
ok(v12.require_team_universe_key(_tu)["key_id"] == v12.TEAM_KEY_ID,
   "a tg_-keyed team universe passes the v12 team-key precondition")
raises(lambda: v12.require_team_universe_key(
    pd.DataFrame({"row_uid": ["ob_a", "tg_b"]})),
    "a player-obligation key inside a team universe is refused", contains="team-game key")
raises(lambda: v12.require_team_universe_key(
    pd.DataFrame({"row_uid": ["tg_a", "tg_a"]})),
    "a duplicated team-game key is refused", contains="share")
ok(cv4.key_status(_tu, require_declared_key=False)["unique"] is True,
   "require_declared_key=False still enforces uniqueness -- it waives only the declaration")


# =========================================================================== #
print("\n6. THE RUN: nondegenerate, end to end, all the way to predictions")
# =========================================================================== #
RES = v12.run_player_fold(TRAIN, TEST, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                          snapshot_manifest=MAN, universe=UNI)

ok(RES["scoring_permitted"] is True,
   f"the fold passes every v12 receipt (failed={RES['failed_receipts']}, "
   f"inherited={RES['inherited_receipts']})")
ok(RES["diagnostics"]["degenerate"] is False,
   "the run is NONDEGENERATE -- it did not fall back to declared constants wholesale")
_components = {c for p in RES["predictions"].values() for c in p.component_id.unique()}
ok("p_active/ridge_logistic_stage_a" in _components,
   "a Stage-A ridge logistic was actually fitted and used, so the run reached a model")
ok(sorted(RES["predictions"]) == sorted(v12.PLAYER_TARGETS),
   "all four player targets emitted predictions")
ok(all(len(p) == len(TEST) for p in RES["predictions"].values()),
   "every emitted target covers every test obligation")
ok(len(RES["required_receipts"]) == 8 and
   tuple(RES["required_receipts"]) == v12.V12_REQUIRED_RECEIPTS,
   "the verdict rests on the same eight named receipts the inherited runner requires")


# =========================================================================== #
print("\n7. negative PRE-FIT controls, each with zero fits before rejection")
# =========================================================================== #
def with_no_fits(label, fn):
    """Run `fn`, expecting it to raise, and assert no estimator ran first."""
    global _n
    _n += 1
    calls = {"n": 0}
    real_fit, real_pred = cbs_v8.logistic_fit, cbs_v8.logistic_predict

    def counted(inner):
        def f(*a, **k):
            calls["n"] += 1
            return inner(*a, **k)
        return f

    cbs_v8.logistic_fit, cbs_v8.logistic_predict = counted(real_fit), counted(real_pred)
    try:
        try:
            fn()
        except Exception:                                        # noqa: BLE001
            if calls["n"]:
                print(f"  FAIL {label} -- rejected, but {calls['n']} estimator calls ran first")
                raise SystemExit(1)
            print(f"  ok   {label}")
            return
        print(f"  FAIL {label} -- did not reject")
        raise SystemExit(1)
    finally:
        cbs_v8.logistic_fit, cbs_v8.logistic_predict = real_fit, real_pred


def run(**over):
    kw = dict(config_hash=CFG, snapshot_hash=SNAP, snapshot_manifest=MAN, universe=UNI)
    kw.update(over)
    train, test = kw.pop("train", TRAIN), kw.pop("test", TEST)
    return v12.run_player_fold(train, test, kw.pop("fold_id", FOLD), **kw)


# (a) a missing required Stage-A feature
_missing_feature = TEST.drop(columns=["min_ewma"])
with_no_fits("a missing required Stage-A feature rejects before any fit",
             lambda: run(test=_missing_feature,
                         snapshot_manifest=manifest({**FRAMES, "test": _missing_feature}),
                         snapshot_hash=v12.snapshot_identity(
                             manifest({**FRAMES, "test": _missing_feature}))))

# ...and the caller cannot buy their way past it
with_no_fits("a caller cannot re-enable declared Stage-A defaults",
             lambda: run(allow_declared_defaults=True))
ok("allow_declared_defaults" in _v12_src
   and RES["declared_defaults_permitted"] is False,
   "the run records that declared defaults were forbidden")

# (b) ALL source timestamps removed
_no_ts = TEST.drop(columns=list(v12.REQUIRED_PLAYER_FEATURE_SOURCES))
with_no_fits("a test frame with every source timestamp removed rejects before any fit",
             lambda: run(test=_no_ts,
                         snapshot_manifest=manifest({**FRAMES, "test": _no_ts}),
                         snapshot_hash=v12.snapshot_identity(
                             manifest({**FRAMES, "test": _no_ts}))))
_late = TEST.copy()
_late.loc[_late.index[0], "src_asof_roster"] = _late.loc[_late.index[0], "forecast_cutoff"]
with_no_fits("a source read EXACTLY AT its own cutoff rejects before any fit",
             lambda: run(test=_late,
                         snapshot_manifest=manifest({**FRAMES, "test": _late}),
                         snapshot_hash=v12.snapshot_identity(
                             manifest({**FRAMES, "test": _late}))))

# (c) a STALE frame digest -- the manifest is reused while the frame moved
_mutated = TEST.copy()
_mutated.loc[_mutated.index[0], "min_ewma"] = 999.0
with_no_fits("a mutated frame against a reused manifest rejects before any fit",
             lambda: run(test=_mutated))
# (c') a MISSING frame digest
with_no_fits("a manifest that does not declare the universe it was handed rejects",
             lambda: run(snapshot_manifest=manifest({"train": TRAIN, "test": TEST}),
                         snapshot_hash=v12.snapshot_identity(
                             manifest({"train": TRAIN, "test": TEST}))))

# (d) CHANGED artifact bytes -- the real path, where artifact_root is mandatory
_real_kw = dict(config_hash=v12.REGISTERED_CONFIG_HASH, snapshot_manifest=MAN,
                snapshot_hash=SNAP, frames=FRAMES, synthetic=False)
raises(lambda: v12.require_registered_identity(artifact_root=None, **_real_kw),
       "a real run without artifact_root is refused", contains="artifact_root")
with_no_fits("declared artifact bytes that do not match disk reject before any fit",
             lambda: v12.require_registered_identity(artifact_root=REPO, **_real_kw))
_short = dict(MAN)
_short["artifacts"] = {k: v for k, v in list(MAN["artifacts"].items())[:2]}
raises(lambda: v12.snapshot_identity(_short),
       "an artifact SUBSET is refused at the runner, not only at construction",
       exc=prov4.ArtifactSetError)
_wide = dict(MAN)
_wide["artifacts"] = {**MAN["artifacts"], "experiments/extra.parquet": "b" * 64}
raises(lambda: v12.snapshot_identity(_wide), "an artifact SUPERSET is refused too",
       exc=prov4.ArtifactSetError)

# (e) a synthetic-stamped manifest may not be consumed by a real run
_stamped = {**MAN, "synthetic": True, "real_path_permitted": False,
            "why_not_real": "built through the synthetic-only escape"}
raises(lambda: v12.require_registered_identity(
    v12.REGISTERED_CONFIG_HASH, v12.snapshot_identity(_stamped), _stamped,
    frames=FRAMES, synthetic=False, artifact_root=REPO),
    "a manifest stamped real_path_permitted=False is refused by a real run",
    contains="must not be consumed")

# (f) a non-uniquely keyed frame, and a wrong config digest
_dup = pd.concat([TEST, TEST.iloc[[0]]], ignore_index=True)
with_no_fits("a duplicated canonical key rejects before any fit -- it is not de-duplicated",
             lambda: run(test=_dup))
raises(lambda: v12.require_canonical_keys({"test": _dup}),
       "the key precondition itself rejects it rather than dropping the duplicate",
       contains="not unique")
raises(lambda: manifest({**FRAMES, "test": _dup}),
       "and such a frame cannot even be given a manifest identity: the sort is not well defined",
       contains="duplicate")
with_no_fits("a wrong but well-formed config digest rejects before any fit",
             lambda: run(config_hash="c" * 64))
with_no_fits("a snapshot_hash that is not the DERIVED identity rejects before any fit",
             lambda: run(snapshot_hash="d" * 64))


# =========================================================================== #
print("\n8. the receipts name the artifacts that were actually emitted")
# =========================================================================== #
R = RES["receipts"]
for name in v12.V12_REQUIRED_RECEIPTS:
    ok(R[name].get("recomputed_by") == v12.ARM_ID,
       f"the {name} receipt was recomputed by v12, not inherited")
ok(R["identity_binding"]["receipt"] == "identity_binding/5", "identity_binding is v12's /5")
ok(R["provenance_history"]["receipt"] == "provenance_history/2",
   "provenance_history is v12's /2")
ok(R["prediction_validation"]["receipt"] == "prediction_validation/3",
   "prediction_validation is v12's /3")
ok(R["receipt_authorship"]["ok"] and R["receipt_authorship"]["inherited_required_receipts"] == [],
   "the authorship receipt confirms no required receipt was inherited")

# the inner receipts are retained, and are NOT the ones the verdict used
ok(RES["inner_receipts"]["identity_binding"]["config_hash"] == cbs_v8.SYNTHETIC_CONFIG_HASH,
   "the inner receipt describes the LEGACY SYNTHETIC identity, as v11's verdict would have")
ok(R["identity_binding"]["config_hash"] == CFG,
   "the v12 receipt describes the v12 identity, which is what the verdict used")
ok(RES["inner_receipts"]["identity_binding"] is not R["identity_binding"],
   "the two are distinct documents, retained side by side")

# emitted predictions and sidecar carry the run's identity
for tgt, p in RES["predictions"].items():
    ok((p.arm_id == v12.ARM_ID).all() and (p.config_hash == CFG).all()
       and (p.data_snapshot_hash == SNAP).all(),
       f"{tgt}: emitted predictions carry the v12 arm and identity")
    ok(not p.arm_id.isin([cbs_v8.ARM_ID, cbs_v10.ARM_ID, cbs_v11.ARM_ID]).any(),
       f"{tgt}: no earlier arm identity survives the restamp")
SC = RES["provenance_sidecar"]
ok((SC.arm_id == v12.ARM_ID).all() and (SC.config_hash == CFG).all()
   and (SC.data_snapshot_hash == SNAP).all(),
   "the emitted sidecar carries the v12 arm and identity")

# the sidecar digest names the bytes actually emitted
ok(R["provenance_history"]["digest"] == v12.sidecar_identity(SC)
   == RES["provenance_sidecar_digest"],
   "the reported sidecar digest is the digest of the RESTAMPED sidecar that was returned")
ok(R["provenance_history"]["digest_schema"] == "cbs_sidecar_identity/2",
   "and it is taken under cbs_sidecar_identity/2")
ok(R["provenance_history"]["legacy_probe_digest"] != R["provenance_history"]["digest"],
   "the inherited probe's digest is a DIFFERENT string and is reported separately")
_pre = RES["inner_receipts"]["provenance_history"].get("digest")
ok(_pre != R["provenance_history"]["digest"],
   "the pre-restamp digest differs from the emitted one -- v11 would have reported the former")

# a post-restamp sidecar/identity mismatch is caught
_bad_sc = SC.copy()
_bad_sc.loc[_bad_sc.index[0], "config_hash"] = "e" * 64
ok(not v12.validate_provenance_sidecar(_bad_sc, RES["predictions"], fold_id=FOLD,
                                       config_hash=CFG, snapshot_hash=SNAP)["ok"],
   "a sidecar whose config_hash drifts from the run is REJECTED")
_bad_sc2 = SC.copy()
_bad_sc2["arm_id"] = cbs_v11.ARM_ID
ok(not v12.validate_provenance_sidecar(_bad_sc2, RES["predictions"], fold_id=FOLD,
                                       config_hash=CFG, snapshot_hash=SNAP)["ok"],
   "a sidecar left stamped with an earlier arm is REJECTED")
_bad_pred = {t: p.copy() for t, p in RES["predictions"].items()}
_bad_pred["p_active"]["data_snapshot_hash"] = "f" * 64
ok(not v12.validate_provenance_sidecar(SC, _bad_pred, fold_id=FOLD, config_hash=CFG,
                                       snapshot_hash=SNAP)["ok"],
   "predictions whose snapshot identity drifts from the run are REJECTED")

# an inherited-but-green required receipt still fails the run
_faked = dict(R)
_faked["coverage"] = {**R["coverage"], "recomputed_by": cbs_v8.ARM_ID}
_inh = [n for n in v12.V12_REQUIRED_RECEIPTS
        if _faked.get(n, {}).get("recomputed_by") != v12.ARM_ID]
ok(_inh == ["coverage"],
   "an inherited receipt is detected by authorship even when it reports ok=True")

# the frame binding names the digests of the frames that were handed over
for role, frame in (("train", TRAIN), ("test", TEST), ("universe", UNI)):
    pf = R["frame_binding"]["per_frame"][role]
    ok(pf["match"] and pf["actual"] == frame_digest(frame, mode=REAL_PATH_MODE),
       f"the {role} frame binding names that frame's cbs_frame_identity/3 digest")
ok(R["identity_binding"]["snapshot_hash"] == SNAP == RES["snapshot_hash"],
   "the identity receipt, the run and the emitted rows agree on one snapshot identity")

# cbs_sidecar_identity/2 is total where the inherited digest is not
_ts_sc = SC.copy()
_ts_sc["forecast_cutoff"] = pd.to_datetime(_ts_sc["forecast_cutoff"], utc=True)
from cbs_v7 import sidecar_digest as _legacy_digest      # noqa: E402
raises(lambda: _legacy_digest(_ts_sc),
       "the INHERITED sidecar digest cannot encode a Timestamp -- the real-path defect",
       contains="not JSON serializable")
ok(len(v12.sidecar_identity(_ts_sc)) == 64,
   "cbs_sidecar_identity/2 digests the same sidecar without raising")
_null_sc, _empty_sc = SC.copy(), SC.copy()
_null_sc["exclusion_reason"] = None
_empty_sc["exclusion_reason"] = ""
ok(v12.sidecar_identity(_null_sc) != v12.sidecar_identity(_empty_sc),
   "and a null and an empty string no longer share one sidecar identity")


# =========================================================================== #
print("\n9. BLOCKER: the inherited obligation ordering is team-blind")
# =========================================================================== #
_collide = pd.concat([
    TEST.iloc[[0]].assign(team_id=TEAM, row_uid="ob_left"),
    TEST.iloc[[0]].assign(team_id=TEAM + 1, row_uid="ob_right"),
], ignore_index=True)
_rep = v12.order_collisions(_collide)
ok(_rep["n_colliding_rows"] == 2 and _rep["n_groups"] == 1,
   "two obligations differing only in team_id are indistinguishable to the inherited key")
ok(_rep["resolved_by_team_id"] is True, "adding team_id to the key resolves them")
raises(lambda: v12.require_orderable_obligations({"train": TRAIN, "test": _collide}),
       "v12 fails CLOSED on them, at its own boundary, with the count and the keys",
       exc=v12.InheritedOrderingCollision, contains="TEAM-BLIND")
raises(lambda: gen.order_obligations(_collide),
       "the inherited guard's own refusal is the underlying cause",
       exc=gen.ObligationOrderError, contains="indistinguishable")
ok(v12.require_orderable_obligations({"train": TRAIN, "test": TEST})["ok"],
   "a fold with no dual-team obligation passes the same check")
ok("order_obligations" not in inspect.getsource(cbs_v8.run_team_fold),
   "the inherited TEAM runner does not call the ordering guard, so the team path is unaffected")

# the blocker is registered, with its measurement, rather than left in a comment
BLK = FC["blockers"]["9_inherited_obligation_ordering_is_team_blind"]
ok(BLK["measured"]["colliding_rows_in_the_contract"] == 28
   and BLK["measured"]["groups"] == 14
   and BLK["measured"]["rows_still_colliding_once_team_id_joins_the_key"] == 0,
   "the registration records the measured extent: 28 rows, 14 groups, 0 after team_id")
ok(sorted(BLK["measured"]["by_season"]) == ["2021", "2022", "2023", "2024", "2025", "2026"],
   "and records that every season is affected")
ok("ruling_requested" in BLK,
   "and asks the supervisor to rule, rather than choosing how to correct an immutable module")


# =========================================================================== #
print("\n10. the arm scores nothing, and reads nothing it has not declared")
# =========================================================================== #
BANNED_CALLS = {"fit_transform", "predict_proba", "score", "roc_auc_score", "log_loss",
                "brier_score_loss", "accuracy_score", "mean_squared_error"}
BANNED_IMPORTS = {"sklearn", "catboost", "lightgbm", "xgboost", "tabpfn", "statsmodels"}

tree = ast.parse(_v12_src)
called, imported = set(), set()
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute):
            called.add(f.attr)
        elif isinstance(f, ast.Name):
            called.add(f.id)
    elif isinstance(node, ast.Import):
        for a in node.names:
            imported.add(a.name.split(".")[0])
    elif isinstance(node, ast.ImportFrom) and node.module:
        imported.add(node.module.split(".")[0])

ok(not (called & BANNED_CALLS),
   f"cbs_v12.py calls no scoring method (offenders: {sorted(called & BANNED_CALLS)})")
ok(not (imported & BANNED_IMPORTS),
   f"cbs_v12.py imports no estimator library (offenders: {sorted(imported & BANNED_IMPORTS)})")
ok(not any(n in v12.__dict__ for n in ("score", "evaluate", "backtest", "profit")),
   "the module exposes no scoring, evaluation or profitability entry point")
ok("NOT_YET_COMPUTED" in rec12["primary_metric"]
   and "No real MODEL fit" in FC["evidence_label"],
   "the registered evidence label states no real model fit exists")
ok("OBLIGATION COMPLETENESS" in FC["evidence_label"],
   "the registered label defines 'coverage' as obligation completeness, not accuracy")
ok(FC["real_path_status"]["player"].startswith("BLOCKED"),
   "the registration states plainly that the real player path is blocked")

_missing_impl = [f for f in FC["implementation"] if not (REPO / f).exists()]
ok(not _missing_impl, f"every registered implementation file exists (missing: {_missing_impl})")
ok(set(SIDECAR_COLS) <= set(SC.columns),
   "the emitted sidecar carries every registered provenance column")

# v11 and v10 are byte-untouched by this arm
ok("cbs_v11" in _v12_src and "def snapshot_identity" in _v11_src,
   "v12 IMPORTS v11's manifest gate rather than copying it")
ok(v12.snapshot_identity.__doc__ and "v11" in v12.snapshot_identity.__doc__,
   "and says so, so a reader knows which module owns the rule")


print(f"\n{_n}/{_n} tests passed")
