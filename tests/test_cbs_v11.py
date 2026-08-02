"""Fan-in suite for `contract_baseline_suite_v11`.

Written by the integration coordinator, not by a branch. It tests the seams the branches could
not see: the registration, the `/5` manifest boundary, the canonical-key precondition at the
runner, and the reconciliations made at fan-in.

Run as a script (pytest is not installed in this environment)::

    python tests/test_cbs_v11.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cbs_obligation_key as obk          # noqa: E402
import cbs_provenance_v4 as prov4         # noqa: E402
import cbs_v10                            # noqa: E402
import cbs_v11                            # noqa: E402
from cbs_identity_v3 import FRAME_IDENTITY_SCHEMA, REAL_PATH_MODE  # noqa: E402
from cbs_v7 import AdapterBoundaryError   # noqa: E402

REPO = Path(__file__).resolve().parents[1]
REGISTRY = REPO / "experiments" / "registry.jsonl"

_n = 0


def ok(cond, label):
    global _n
    _n += 1
    if not cond:
        print(f"  FAIL {label}")
        raise SystemExit(1)
    print(f"  ok   {label}")


def raises(fn, label, contains=None):
    global _n
    _n += 1
    try:
        fn()
    except Exception as e:                                   # noqa: BLE001
        if contains and contains.lower() not in str(e).lower():
            print(f"  FAIL {label} -- raised but message lacked {contains!r}: {e}")
            raise SystemExit(1)
        print(f"  ok   {label}")
        return
    print(f"  FAIL {label} -- did not raise")
    raise SystemExit(1)


def _registry_records():
    out = []
    for line in REGISTRY.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


# --------------------------------------------------------------------------- #
print("\n1. registration is append-only and both new records are present")
# --------------------------------------------------------------------------- #
recs = _registry_records()
ids = [r.get("experiment_id") for r in recs]

ok(len(recs) == 91, f"registry holds 91 records (got {len(recs)})")
ok(ids[-1] == "contract_baseline_suite_v11", "the last record is v11")
ok(ids[-2] == "contract_baseline_suite_v10__erratum_20260802", "the v10 erratum precedes it")
ok(ids.count("contract_baseline_suite_v10") == 1, "v10's own record appears exactly once")
ok(recs[-2]["kind"] == "erratum" and recs[-2]["errata_for"] == "contract_baseline_suite_v10",
   "the erratum is kind=erratum and names v10")
ok(recs[-2]["prior_records_mutated"] is False, "the erratum mutates no prior record")

v11 = recs[-1]
ok(v11["kind"] == "experiment", "v11 is kind=experiment")
ok(v11["primary_metric"].endswith("NOT_YET_COMPUTED"),
   "v11's primary_metric is explicitly NOT_YET_COMPUTED")
ok(v11["extra"]["no_real_model_result"] is True, "v11 declares no real model result")
ok(v11["extra"]["computed_nothing_on_real_data"] is False,
   "v11 declares computed_nothing_on_real_data FALSE -- it does read and build real data")
ok(v11["extra"]["definition_only"] is True, "v11 is definition/correction only")

# --------------------------------------------------------------------------- #
print("\n2. config hashes recompute, and the errata do not shadow their subjects")
# --------------------------------------------------------------------------- #
ok(cbs_v11.recompute_registered_config_hash() == cbs_v11.REGISTERED_CONFIG_HASH,
   "v11's registered config hash recomputes from the registry")
ok(cbs_v10.recompute_registered_config_hash() == cbs_v10.REGISTERED_CONFIG_HASH,
   "v10's still recomputes despite the appended v10 erratum")

import cbs_v9  # noqa: E402
ok(cbs_v9.recompute_registered_config_hash() == cbs_v9.REGISTERED_CONFIG_HASH,
   "v9's still recomputes despite its own appended erratum")
ok(cbs_v11.REGISTERED_CONFIG_HASH != cbs_v10.REGISTERED_CONFIG_HASH,
   "v11 and v10 are different registered configurations")

# the erratum deliberately carries a DISTINCT experiment_id; prove the helper would
# otherwise have been shadowed
raises(lambda: cbs_v11.recompute_registered_config_hash(
    experiment_id="contract_baseline_suite_v10__erratum_20260802"),
    "an erratum record has no frozen_config and cannot be config-hashed",
    contains="frozen_config")

# --------------------------------------------------------------------------- #
print("\n3. cbs_snapshot_manifest/5 is a NEW id, and /1-/4 are refused")
# --------------------------------------------------------------------------- #
ok(cbs_v11.SNAPSHOT_MANIFEST_SCHEMA == "cbs_snapshot_manifest/5",
   "v11 binds cbs_snapshot_manifest/5")
ok(prov4.SNAPSHOT_MANIFEST_SCHEMA == cbs_v11.SNAPSHOT_MANIFEST_SCHEMA,
   "provenance/4 and v11 agree on the manifest schema")
ok(cbs_v10.SNAPSHOT_MANIFEST_SCHEMA == "cbs_snapshot_manifest/4",
   "v10's schema constant is untouched at /4")
for s in ("cbs_snapshot_manifest/1", "cbs_snapshot_manifest/2",
          "cbs_snapshot_manifest/3", "cbs_snapshot_manifest/4"):
    ok(s in cbs_v11.REJECTED_MANIFEST_SCHEMAS, f"{s} is refused by v11")

# This is the fan-in reconciliation itself: the branch reused /4 while adding three required
# fields to the body. A /4 manifest must be refused BY NAME, not merely fail a field check.
raises(lambda: cbs_v11.snapshot_identity({"schema": "cbs_snapshot_manifest/4"}),
       "a genuine v10-era /4 manifest is refused by name", contains="REFUSED")
raises(lambda: cbs_v11.snapshot_identity({"schema": "cbs_snapshot_manifest/9"}),
       "an unknown manifest schema is refused")
raises(lambda: cbs_v11.snapshot_identity("not a mapping"),
       "a non-mapping manifest is refused")
raises(lambda: cbs_v11.snapshot_identity(
    {"schema": "cbs_snapshot_manifest/5", "obligation_key_id": "something/else"}),
    "a /5 manifest that names the WRONG obligation key is refused",
    contains="obligation_key_id")
raises(lambda: cbs_v11.snapshot_identity({"schema": "cbs_snapshot_manifest/5"}),
       "a /5 manifest that names NO obligation key is refused",
       contains="obligation_key_id")

_base = {"schema": "cbs_snapshot_manifest/5",
         "obligation_key_id": obk.OBLIGATION_KEY_ID,
         "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
         "frame_identity_mode": REAL_PATH_MODE}
raises(lambda: cbs_v11.snapshot_identity({**_base, "frame_identity_mode": "scalar_only"}),
       "a /5 manifest declaring the wrong frame-identity MODE is refused")
raises(lambda: cbs_v11.snapshot_identity(dict(_base)),
       "a /5 manifest listing no artifacts is refused", contains="artifact")

# The refusal list must be ENFORCED, not merely declared. The real-integration gate measured
# that require_real_snapshot_manifest never read `schema`, so a document stamped /4 but
# otherwise /5-shaped was accepted; a genuine v10 document was refused only incidentally, for
# lacking obligation_key_id. A refusal list nothing consults is a comment.
_shaped = {"schema": "cbs_snapshot_manifest/4",
           "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
           "frame_identity_mode": REAL_PATH_MODE,
           "obligation_key_id": obk.OBLIGATION_KEY_ID,
           "artifacts": {}, "frames": {"x": "0" * 64}, "captured_at": "2026-08-02T00:00:00Z"}
raises(lambda: prov4.require_real_snapshot_manifest(dict(_shaped)),
       "provenance/4 REFUSES a /4-stamped manifest even when it is otherwise /5-shaped",
       contains="REFUSED")
raises(lambda: prov4.require_real_snapshot_manifest({**_shaped, "schema": "cbs_snapshot_manifest/9"}),
       "provenance/4 refuses an unknown manifest schema")
raises(lambda: prov4.require_real_snapshot_manifest(
    {**_shaped, "schema": "cbs_snapshot_manifest/5", "obligation_key_id": None}),
    "provenance/4 still refuses a /5 manifest that names no obligation key",
    contains="obligation_key_id")

# --------------------------------------------------------------------------- #
print("\n4. the canonical-key precondition -- the check v10 did not have")
# --------------------------------------------------------------------------- #
ok(obk.OBLIGATION_KEY_ID == "cbs_obligation_key/1", "the key rule is cbs_obligation_key/1")

good = pd.DataFrame({"row_uid": ["ob_a", "ob_b"], "obligation_key_id": [obk.OBLIGATION_KEY_ID] * 2})
dup = pd.DataFrame({"row_uid": ["ob_a", "ob_a"], "obligation_key_id": [obk.OBLIGATION_KEY_ID] * 2})
wrong = pd.DataFrame({"row_uid": ["ob_a", "ob_b"], "obligation_key_id": ["legacy/0"] * 2})

checked = cbs_v11.require_canonical_keys({"test": good})
ok(checked["test"]["rows"] == 2 and checked["test"]["distinct_row_uid"] == 2,
   "a uniquely keyed frame passes and is reported")
raises(lambda: cbs_v11.require_canonical_keys({"test": dup}),
       "a frame with a duplicated canonical key is REJECTED, not de-duplicated",
       contains="not unique")
raises(lambda: cbs_v11.require_canonical_keys({"test": wrong}),
       "a frame declaring a different key rule is rejected", contains="obligation_key_id")
ok(cbs_v11.require_canonical_keys({"test": None}) == {},
   "a null frame is skipped rather than crashing")

# the failure mode this whole arm exists to prevent
raises(lambda: obk.assert_unique_canonical_keys(dup, where="fixture"),
       "the shared guard raises rather than silently dropping a duplicate obligation")

# --------------------------------------------------------------------------- #
print("\n5. identity binding refuses wrong config and undeclared snapshots")
# --------------------------------------------------------------------------- #
raises(lambda: cbs_v11.require_registered_identity(
    "not-a-hash", "x", {"schema": "cbs_snapshot_manifest/5"},
    frames={}, synthetic=True),
    "a wrong config_hash is refused before anything else", contains="config_hash")
raises(lambda: cbs_v11.require_registered_identity(
    cbs_v11.SYNTHETIC_CONFIG_HASH, "x", None, frames={}, synthetic=True),
    "a missing snapshot manifest is refused: identity is DERIVED, never asserted",
    contains="mandatory")
ok(cbs_v11.SYNTHETIC_CONFIG_HASH != cbs_v11.REGISTERED_CONFIG_HASH,
   "the synthetic config digest is distinct from the registered one")

# --------------------------------------------------------------------------- #
print("\n6. the arm fits, predicts and scores NOTHING")
# --------------------------------------------------------------------------- #
import ast  # noqa: E402

BANNED_CALLS = {"fit", "predict", "predict_proba", "fit_transform", "score",
                "roc_auc_score", "log_loss", "brier_score_loss", "accuracy_score"}
BANNED_IMPORTS = {"sklearn", "catboost", "lightgbm", "xgboost", "tabpfn", "statsmodels"}

src = (REPO / "cbs_v11.py").read_text(encoding="utf-8")
tree = ast.parse(src)
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
   f"cbs_v11.py calls no estimator method (offenders: {sorted(called & BANNED_CALLS)})")
ok(not (imported & BANNED_IMPORTS),
   f"cbs_v11.py imports no estimator library (offenders: {sorted(imported & BANNED_IMPORTS)})")
ok(not (set(obk.__dict__) & BANNED_CALLS), "the key module exposes no estimator entry point")

fc = v11["extra"]["frozen_config"]
ok("No real MODEL fit" in fc["evidence_label"],
   "the registered evidence label states no real model fit exists")
ok("OBLIGATION COMPLETENESS" in fc["evidence_label"],
   "the registered label defines 'coverage' as obligation completeness, not accuracy")

# --------------------------------------------------------------------------- #
print("\n7. the registered numbers match the artifacts they describe")
# --------------------------------------------------------------------------- #
key = fc["obligation_key"]["measured"]
pg = pd.read_parquet(REPO / "experiments/prediction_contract_v4/player_game.parquet")
ok(len(pg) == key["obligations"] == 35627, "the registered obligation count matches the artifact")
ok(pg["row_uid"].nunique() == key["distinct_canonical"] == 35627,
   "the registered canonical-key count matches the artifact and is unique")
ok(pg["player_game_uid"].nunique() == key["distinct_legacy"] == 35613,
   "the registered legacy-key count matches the artifact")
ok(int(pg["player_game_uid"].duplicated(keep=False).sum()) == key["rows_sharing_a_legacy_id"] == 28,
   "the registered collision row count matches the artifact")
ok(pg["row_uid"].is_unique, "the canonical key is unique over the real emitted universe")

diff = json.loads((REPO / "experiments/prediction_contract_v4/row_diff_vs_v3.json").read_text())
closes = fc["what_v11_closes"]["1_canonical_unique_team_bearing_key"]["row_set_unchanged"]
ok(closes["v3"] == closes["v4"] == 35627 and closes["v3_only"] == closes["v4_only"] == 0,
   "the registration claims the row SET is unchanged and only the key changed")
ok(json.dumps(diff).count("35627") >= 1, "the row-diff receipt exists and names the row count")

# every implementation file the registration names must exist
missing = [f for f in fc["implementation"] if not (REPO / f).exists()]
ok(not missing, f"every registered implementation file exists (missing: {missing})")

print(f"\n{_n}/{_n} tests passed")
