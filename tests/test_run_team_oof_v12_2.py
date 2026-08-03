#!/usr/bin/env python
"""test_run_team_oof_v12_2.py — clean-producer refusal, and a resume that fails closed.

The supervisor's review found two things wrong with how `cbs_v12_team_oof/1` was PRODUCED, not
with what it produced:

  * it ran from a tree with **97 dirty paths**, recorded that honestly, and generated anyway — so
    the exact code behind the artifacts is not reconstructible;
  * its resume check was **fail-open**: it compared rebuilt frame digests and the five input
    artifacts and nothing else, so a missing or substituted OUTPUT could be marked RESUMED and
    still yield `all_folds_receipted=true`.

Both corrections are behavioural, so both are tested behaviourally. The resume tests run one real
2021 team fold into a temporary directory OUTSIDE the repository, then damage a copy of it in each
of the enumerated ways and assert the validator names that failure and refuses.

  §1  the producer gate: a dirty tree is refused, and the override needs two explicit tokens
  §2  the producing source set is digested BEFORE any frame is built
  §3  a genuine, untouched fold validates and is reusable
  §4  each enumerated failure mode is detected and named — twelve of them
  §5  attempt directories are immutable: the resolver never returns an existing one
  §6  the scope claim is stated at its actual width

2021 is the only season run here: its training window is empty, so it fits nothing. No score,
accuracy or profitability figure is computed anywhere in this file.

Run as a script::

    python tests/test_run_team_oof_v12_2.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asof_invariant as aso                    # noqa: E402
import cbs_real_frames_v3 as rf3                # noqa: E402
import cbs_v12 as v12                           # noqa: E402
import run_team_oof_v12_2 as r2                 # noqa: E402
import run_team_oof_v12 as r1                   # noqa: E402

T_START = time.time()
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


def refuses(label, fn, contains=None, exc=Exception):
    global PASSED
    try:
        fn()
    except exc as e:                                             # noqa: BLE001
        if contains and contains.lower() not in str(e).lower():
            FAILED.append(f"{label} -- message lacked {contains!r}: {e}")
            print(f"  FAIL {label} -- message lacked {contains!r}")
            return
        PASSED += 1
        print(f"  ok   {label}")
        return
    FAILED.append(f"{label} -- did not refuse")
    print(f"  FAIL {label} -- did not refuse")


SEASON = 2021


# ==========================================================================
print("\n1. the producer gate: a dirty tree is refused")
# ==========================================================================
check("1 /2 is a new run id with a new output namespace, so /1 is untouched",
      r2.RUN_ID == "cbs_v12_team_oof/2" and r2.SUPERSEDES == "cbs_v12_team_oof/1"
      and r2.OUT_DIR != r1.OUT_DIR)
check("1 and /1's artifacts are still on disk, retained",
      (ROOT / r1.OUT_DIR / "run_index.json").exists())

_dirty = [ln for ln in r2._git(ROOT, "status", "--porcelain").splitlines() if ln.strip()]
if _dirty:
    refuses("1 a dirty producing tree is REFUSED outright",
            lambda: r2.require_clean_producer(ROOT),
            contains="not reconstructible", exc=r2.DirtyProducer)
    _rec = r2.require_clean_producer(ROOT, allow_dirty=True)
    check("1 the override records not_reproducible rather than hiding the state",
          _rec["ok"] is False and _rec["not_reproducible"] is True
          and _rec["n_dirty_paths"] == len(_dirty))
else:
    _rec = r2.require_clean_producer(ROOT)
    check("1 a CLEAN producing tree passes", _rec["ok"] is True)
    check("1 and records zero dirty paths", _rec["n_dirty_paths"] == 0)

# the two-token guard: --allow-dirty alone is not enough
_src = (ROOT / "run_team_oof_v12_2.py").read_text(encoding="utf-8")
check("1 --allow-dirty requires a second independent token",
      "--i-am-not-generating-evidence" in _src
      and "refused without --i-am-not-generating-evidence" in _src)
check("1 /1 by contrast had no producer gate at all",
      "require_clean_producer" not in (ROOT / "run_team_oof_v12.py").read_text(encoding="utf-8"))

# and the defect is real: /1's own index records that it generated from a dirty tree
_i1 = json.loads((ROOT / r1.OUT_DIR / "run_index.json").read_text(encoding="utf-8"))
check("1 /1's index records working_tree_clean_vs_head=false and 97 dirty paths",
      _i1["command_identity"]["working_tree_clean_vs_head"] is False
      and _i1["command_identity"]["n_dirty_paths"] == 97,
      _i1["command_identity"]["n_dirty_paths"])


# ==========================================================================
print("\n2. the producing source set is digested before any frame is built")
# ==========================================================================
check("2 every producer source is named", len(r2.PRODUCER_SOURCES) >= 15)
check("2 and every named source exists in the tree",
      all((ROOT / s).exists() for s in r2.PRODUCER_SOURCES),
      [s for s in r2.PRODUCER_SOURCES if not (ROOT / s).exists()])
check("2 the runner itself is in the set -- a change to it changes the digest",
      "run_team_oof_v12_2.py" in r2.PRODUCER_SOURCES)
check("2 the modelling core and the frame adapter are in the set",
      {"cbs_v8.py", "cbs_generator.py", "cbs_real_frames_v3.py"} <= set(r2.PRODUCER_SOURCES))
_d1 = _rec["producer_source_set_digest"]
check("2 the digest is a 64-hex sha over the whole set", len(_d1) == 64)
_rec2 = r2.require_clean_producer(ROOT, allow_dirty=True)
check("2 and is stable across calls on an unchanged tree",
      _rec2["producer_source_set_digest"] == _d1)
check("2 /1 recorded no producer source digest at all",
      "producer_source_set_digest" not in json.dumps(_i1["command_identity"]))


# ==========================================================================
print("\n3. a genuine, untouched fold validates and is reusable")
# ==========================================================================
TMP = Path(tempfile.mkdtemp(prefix="cbs_v2_resume_"))
ATT = TMP / "attempt_001"
ATT.mkdir(parents=True)
BUILT = rf3.build_team_frame(SEASON, ROOT, require_attested=True)


def _log(msg, **kw):
    pass


REC = r2.run_fold(SEASON, ROOT, ATT, _log, _d1)
check("3 the real 2021 fold ran and wrote its artifacts", len(REC["written"]) == 2,
      REC["written"])
check("3 it is the cold start, so nothing was fitted",
      REC["model_was_fitted"] is False and REC["cold_start_declared_constant_only"] is True)
check("3 the receipt records the producing source set digest",
      REC["producer_source_set_digest"] == _d1)
check("3 and states the three scope claims explicitly",
      REC["own_outcome_never_informed_its_forecast"] is True
      and REC["forecast_scored_against_outcome"] is False
      and REC["evaluation_metric_calculated"] is False)

_ok, _reasons, _rr = r2.validate_existing_fold(SEASON, ATT, ROOT, BUILT,
                                               snapshot_manifest=None)
check("3 the untouched fold validates and is reusable", _ok is True, _reasons)
check("3 and the receipt lists what was actually checked", len(_rr["checked"]) >= 10)
check("3 including the strict validators re-run on the artifacts as READ BACK",
      any("read back" in c for c in _rr["checked"]))
check("3 all twelve failure modes are enumerated",
      _rr["enumerated_failure_modes"] == list(r2.RESUME_FAILURES)
      and len(r2.RESUME_FAILURES) == 12)


# ==========================================================================
print("\n4. each enumerated failure mode is detected and named")
# ==========================================================================
def damaged(fn, label, expect):
    """Copy the good attempt, damage the copy, and assert the validator names `expect`."""
    global PASSED
    d = Path(tempfile.mkdtemp(prefix="cbs_v2_dmg_")) / "attempt_001"
    shutil.copytree(ATT, d)
    fn(d)
    ok_, reasons, _ = r2.validate_existing_fold(SEASON, d, ROOT, BUILT,
                                                snapshot_manifest=None)
    if ok_:
        FAILED.append(f"{label} -- validator ACCEPTED a damaged fold")
        print(f"  FAIL {label} -- validator ACCEPTED a damaged fold")
        return
    if expect not in reasons:
        FAILED.append(f"{label} -- expected {expect!r}, got {reasons}")
        print(f"  FAIL {label} -- expected {expect!r}, got {reasons}")
        return
    PASSED += 1
    print(f"  ok   {label}  [{expect}]")


def _receipt(d):
    return d / f"fold_receipt__{SEASON}.json"


def _edit_receipt(d, **kv):
    p = _receipt(d)
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc.update(kv)
    p.write_text(json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8", newline="")


def _pred_path(d):
    return next(d.glob("predictions__*.parquet"))


damaged(lambda d: _receipt(d).unlink(),
        "4 a missing fold receipt", "receipt_absent")
damaged(lambda d: _receipt(d).write_text("not json", encoding="utf-8"),
        "4 an unreadable fold receipt", "receipt_unreadable")
damaged(lambda d: Path(str(_receipt(d)) + aso.MANIFEST_SUFFIX).unlink(),
        "4 a missing receipt manifest", "receipt_manifest_invalid")
damaged(lambda d: _pred_path(d).unlink(),
        "4 a missing prediction artifact", "artifact_absent")
damaged(lambda d: _pred_path(d).write_bytes(_pred_path(d).read_bytes() + b"\x00"),
        "4 a prediction artifact whose bytes no longer match its manifest",
        "artifact_hash_mismatch")
damaged(lambda d: Path(str(_pred_path(d)) + aso.MANIFEST_SUFFIX).unlink(),
        "4 a missing artifact manifest", "artifact_manifest_invalid")
damaged(lambda d: _edit_receipt(d, arm_id="contract_baseline_suite_v11"),
        "4 a receipt claiming the wrong arm", "wrong_arm")
damaged(lambda d: _edit_receipt(d, config_hash="c" * 64),
        "4 a receipt claiming the wrong config", "wrong_config")
damaged(lambda d: _edit_receipt(d, season=2099, fold_id="season:2099"),
        "4 a receipt claiming the wrong season", "wrong_season")
damaged(lambda d: _edit_receipt(d, frames={**json.loads(
            _receipt(d).read_text(encoding="utf-8"))["frames"], "test": "f" * 64}),
        "4 a receipt whose frame digest no longer describes the rebuilt frame",
        "wrong_snapshot")
damaged(lambda d: _edit_receipt(d, artifacts={
            k: "0" * 64 for k in json.loads(
                _receipt(d).read_text(encoding="utf-8"))["artifacts"]}),
        "4 a receipt whose input artifact digests no longer match disk", "wrong_snapshot")
damaged(lambda d: _edit_receipt(d, provenance_sidecar_digest="d" * 64),
        "4 a sidecar digest that no longer recomputes", "sidecar_digest_mismatch")


def _substitute_predictions(d):
    """Replace the forecasts with different numbers, keeping the manifest consistent."""
    p = _pred_path(d)
    df = pd.read_parquet(p)
    df["row_uid"] = "ob_substituted_" + df.index.astype(str)
    df.to_parquet(p, index=False)
    man = aso.read_manifest(p)
    aso.write_manifest(p, producer=man["producer"], fit_through_date=man["fit_through_date"],
                       fit_through_season=man["fit_through_season"],
                       fit_seasons=man["fit_seasons"], notes=man.get("notes", ""))


damaged(_substitute_predictions,
        "4 a SUBSTITUTED prediction file whose manifest was rewritten to match",
        "validator_rejected")

# the /1 fail-open contrast, on the same damage
_i1_open = r1._digests_still_match(
    json.loads((ATT / f"fold_receipt__{SEASON}.json").read_text(encoding="utf-8")),
    {"train": BUILT["train"], "test": BUILT["test"], "universe": BUILT["universe"]}, ROOT)
check("4 /1's resume check passes on a fold whose OUTPUT FILES do not exist at all",
      _i1_open[0] is True,
      "which is the fail-open defect, reproduced against the same receipt")
_gone = Path(tempfile.mkdtemp(prefix="cbs_v2_gone_")) / "attempt_001"
shutil.copytree(ATT, _gone)
for _f in list(_gone.glob("predictions__*")) + list(_gone.glob("provenance_sidecar__*")):
    _f.unlink()
_ok2, _r2reasons, _ = r2.validate_existing_fold(SEASON, _gone, ROOT, BUILT,
                                                snapshot_manifest=None)
check("4 while /2 refuses the same fold, naming the missing artifacts",
      _ok2 is False and "artifact_absent" in _r2reasons, _r2reasons)


# ==========================================================================
print("\n5. attempt directories are immutable")
# ==========================================================================
_base = Path(tempfile.mkdtemp(prefix="cbs_v2_att_"))
_p1, _n1 = r2.resolve_attempt_dir(_base)
check("5 the first attempt is attempt_001", _n1 == "attempt_001")
_p1.mkdir()
_p2, _n2 = r2.resolve_attempt_dir(_base)
check("5 with one present, the resolver returns a NEW directory", _n2 == "attempt_002")
check("5 and never returns an existing one", _p2 != _p1 and not _p2.exists())
check("5 the runner creates a new attempt rather than writing over a stale one",
      "resolve_attempt_dir(base)" in _src and "NEW immutable attempt directory" in _src)
check("5 nothing in the runner deletes or truncates an artifact",
      not any(tok in _src for tok in ("shutil.rmtree", ".unlink(", "os.remove")))


# ==========================================================================
print("\n6. the scope claim is stated at its actual width")
# ==========================================================================
SC = r2.assert_no_scoring()
check("6 the AST scan declares its scope as this wrapper only",
      SC["scope"] == "THIS WRAPPER MODULE ONLY")
check("6 and says what it cannot establish",
      "imported callees" in SC["cannot_establish"]
      and "walk-forward feature" in SC["cannot_establish"])
check("6 the three claims are the narrow, defensible ones", SC["what_is_claimed"] == [
    "no target row's own outcome informed its forecast",
    "no forecast was scored against its outcome",
    "no evaluation metric was calculated"])
check("6 and the first names the mechanism that enforces it",
      "require_own_outcome_unavailable" in SC["first_claim_enforced_by"]
      and "availability < cutoff" in SC["first_claim_enforced_by"])
check("6 /1's scan by contrast claimed no such limitation",
      "THIS WRAPPER MODULE ONLY" not in
      (ROOT / "run_team_oof_v12.py").read_text(encoding="utf-8"))
check("6 no emitted forecast carries an outcome column",
      not ({"team_points", "ch_ft", "ch_3pt", "ch_paint", "ch_np2"}
           & set(pd.read_parquet(_pred_path(ATT)).columns)))
check("6 and the fold receipt computes no metric",
      not any(k in REC for k in ("accuracy", "auc", "log_loss", "brier", "profit", "roi")))

print(f"\n    temporary fixtures left in place under {TMP.parent} (nothing deleted)")
print(f"    total runtime {time.time() - T_START:.0f}s")
print(f"\n{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAILED  {f}")
sys.exit(1 if FAILED else 0)
