#!/usr/bin/env python
"""test_run_player_oof_v14.py — the player generation run, and the owed `mkdir` correction.

`run_player_oof_v14.py` is the player counterpart of the corrected team runner. It inherits that
file's producer gate, immutable attempts and fail-closed resume, and adds the three things the
fan-out required: disjoint per-season write lanes, a per-worker producer-byte invariant that does
not trust the digest it was handed, and one receipt-checked fan-in that revalidates every persisted
byte instead of reading worker exit codes.

  §1  the producer gate: a dirty tree is refused, and the override needs two explicit tokens
  §2  a REFUSED run creates nothing -- the owed correction, tested behaviourally, both runners
  §3  the producing source set is digested before any frame is built, and a worker re-derives it
  §4  lanes are disjoint, and a stray or missing file is detected by set equality
  §5  the target chain: four targets from ONE call, minutes constant held fixed
  §6  a genuine, untouched fold validates -- and each of the fourteen failure modes is named
  §7  attempts are immutable; carry-forward copies, revalidates, and never overwrites
  §8  the fan-in is receipt-checked: a 0 exit code over substituted bytes is still refused
  §9  the scope claim is stated at its actual width, and nothing is scored
  §10 the producer gate is not fail-open under an inherited git environment

Season 2021 is the only season generated here: its training window is empty, so it fits nothing.
No score, accuracy, calibration, threshold, edge, return or profitability figure is computed
anywhere in this file.

Run as a script::

    python tests/test_run_player_oof_v14.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asof_invariant as aso                     # noqa: E402
import cbs_real_frames_v3 as rf3                 # noqa: E402
import cbs_v14 as v14                            # noqa: E402
import run_player_oof_v14 as rp                  # noqa: E402
import run_team_oof_v12_2 as r2                  # noqa: E402

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
SRC = (ROOT / "run_player_oof_v14.py").read_text(encoding="utf-8")
TEAM_SRC = (ROOT / "run_team_oof_v12_2.py").read_text(encoding="utf-8")


# ==========================================================================
print("\n1. the producer gate: a dirty tree is refused")
# ==========================================================================
check("1 this is a new run id in a new output namespace",
      rp.RUN_ID == "cbs_v14_player_oof/1"
      and rp.OUT_DIR == "experiments/cbs_v14_player_oof"
      and rp.OUT_DIR != r2.OUT_DIR)
check("1 it targets the accepted v14 arm, not v12 or v13",
      v14.ARM_ID == "contract_baseline_suite_v14"
      and rp.v14.REGISTERED_CONFIG_HASH == v14.REGISTERED_CONFIG_HASH)
check("1 and the registered config hash still recomputes from the registry",
      v14.recompute_registered_config_hash() == v14.REGISTERED_CONFIG_HASH)

_dirty = [ln for ln in rp._git(ROOT, "status", "--porcelain").splitlines() if ln.strip()]
if _dirty:
    refuses("1 a dirty producing tree is REFUSED outright",
            lambda: rp.require_clean_producer(ROOT),
            contains="not reconstructible", exc=rp.DirtyProducer)
    REC = rp.require_clean_producer(ROOT, allow_dirty=True)
    check("1 the override records not_reproducible rather than hiding the state",
          REC["ok"] is False and REC["not_reproducible"] is True
          and REC["n_dirty_paths"] == len(_dirty))
else:
    REC = rp.require_clean_producer(ROOT)
    check("1 a CLEAN producing tree passes", REC["ok"] is True)
    check("1 and records zero dirty paths", REC["n_dirty_paths"] == 0)

check("1 --allow-dirty requires a second independent token",
      "--i-am-not-generating-evidence" in SRC
      and "refused without --i-am-not-generating-evidence" in SRC)
check("1 the gate says it was measured before any output existed",
      REC["measured_before_any_output_existed"] is True)
check("1 and warns the reader that the run's own output is not undeclared dirt",
      "not undeclared dirt" in REC["note_for_reviewers"])
PDIG = REC["producer_source_set_digest"]

# the standing correction for the path/label defect class: the run records the generating
# checkout itself, so a handoff quotes an artifact instead of recalling a path
check("1 the run records the generating checkout it actually ran from",
      Path(REC["producer_checkout_path"]).resolve() == ROOT
      and REC["producer_checkout_name"] == ROOT.name)
check("1 and says the path was recorded by the run, not transcribed afterwards",
      REC["producer_checkout_recorded_by"].startswith("the run itself"))
check("1 the recorded checkout path resolves to a real directory",
      Path(REC["producer_checkout_path"]).is_dir())


# ==========================================================================
print("\n2. a REFUSED run creates nothing (the owed mkdir correction)")
# ==========================================================================
# Structural: in BOTH runners the directory creation must appear after the producer gate.
# Measured on the CODE, with the module docstring stripped -- the team runner's correction log
# quotes the offending call, and an index over the raw text would find the prose first.
def _code_only(text: str) -> str:
    import ast as _ast
    mod = _ast.parse(text)
    if _ast.get_docstring(mod) is None:
        return text
    return "".join(text.splitlines(keepends=True)[mod.body[0].end_lineno:])


for _name, _s in (("player", _code_only(SRC)), ("team", _code_only(TEAM_SRC))):
    check(f"2 the {_name} runner creates its base dir AFTER the producer gate",
          _s.index("base.mkdir") > _s.index("producer = require_clean_producer("),
          "mkdir still precedes the gate")

# Behavioural, against a genuinely dirty tree that is not this repository.
#: EVERY git call this suite makes against a fixture goes through here, with the inherited git
#: environment scrubbed. This is not hygiene, it is damage control learned the hard way: this suite
#: runs inside the `pre-push` hook, which exports GIT_DIR, and `git init <path>` under an inherited
#: GIT_DIR does not create the repository at `<path>` -- it REINITIALISES the repository GIT_DIR
#: points at, and records `core.bare = true` in it, which breaks `git status` for the real checkout
#: and every worktree. That happened once. It must not happen twice.
def _git_fixture(*args, cwd=None):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          env=rp._git_env(), cwd=cwd)


#: The canary. If a fixture git call ever escapes its sandbox again, this is what catches it.
_REAL_CONFIG = Path(rp._git(ROOT, "rev-parse", "--git-common-dir") or ".") / "config"
_REAL_CONFIG_BEFORE = _REAL_CONFIG.read_bytes() if _REAL_CONFIG.is_file() else None

_TG = Path(tempfile.mkdtemp(prefix="cbs_dirty_root_"))
_git_fixture("init", "-q", str(_TG))
check("2 creating the fixture repository did not touch the REAL repository's config",
      _REAL_CONFIG.is_file() and _REAL_CONFIG.read_bytes() == _REAL_CONFIG_BEFORE,
      f"{_REAL_CONFIG} changed -- a fixture git call escaped its sandbox")
check("2 and this repository still has a work tree",
      rp._git(ROOT, "rev-parse", "--is-inside-work-tree") == "true",
      "core.bare may have been set on the real repository")
for _rel in sorted(set(rp.PRODUCER_SOURCES) | set(r2.PRODUCER_SOURCES)):
    shutil.copy2(ROOT / _rel, _TG / _rel)
_TG_DIRTY = [ln for ln in rp._git(_TG, "status", "--porcelain").splitlines() if ln.strip()]
check("2 the fixture tree really is dirty", len(_TG_DIRTY) > 0, _TG_DIRTY[:3])

_OUT_P = Path(tempfile.mkdtemp(prefix="cbs_refused_")) / "would_be_created"
refuses("2 the player runner refuses to generate from it",
        lambda: rp.main(["--root", str(_TG), "--out", str(_OUT_P),
                         "--seasons", str(SEASON)]),
        contains="not reconstructible", exc=rp.DirtyProducer)
check("2 and left NO output directory behind", not _OUT_P.exists(), str(_OUT_P))

_OUT_T = Path(tempfile.mkdtemp(prefix="cbs_refused_team_")) / "would_be_created"
_argv = sys.argv[:]
sys.argv = ["run_team_oof_v12_2.py", "--root", str(_TG), "--out", str(_OUT_T)]
refuses("2 the team runner refuses to generate from it",
        r2.main, contains="not reconstructible", exc=r2.DirtyProducer)
sys.argv = _argv
check("2 and it too left NO output directory behind -- this is the defect that was owed",
      not _OUT_T.exists(), str(_OUT_T))

# the second refusal path -- one token is not enough -- must also create nothing
_OUT_1TOK = Path(tempfile.mkdtemp(prefix="cbs_onetoken_")) / "would_be_created"
refuses("2 --allow-dirty alone is refused",
        lambda: rp.main(["--root", str(ROOT), "--out", str(_OUT_1TOK), "--allow-dirty"]),
        contains="i-am-not-generating-evidence", exc=rp.DirtyProducer)
check("2 and that refusal creates nothing either", not _OUT_1TOK.exists())


# ==========================================================================
print("\n3. the producing source set is digested before any frame is built")
# ==========================================================================
check("3 every producer source is named", len(rp.PRODUCER_SOURCES) >= 20)
check("3 and every named source exists in the tree",
      all((ROOT / s).exists() for s in rp.PRODUCER_SOURCES),
      [s for s in rp.PRODUCER_SOURCES if not (ROOT / s).exists()])
check("3 the runner itself is in the set -- a change to it changes the digest",
      "run_player_oof_v14.py" in rp.PRODUCER_SOURCES)
check("3 all three corrected v14 components are in the set",
      {"cbs_v14.py", "cbs_player_runner_v14.py", "cbs_player_history_v14.py",
       "cbs_obligation_order_v3.py"} <= set(rp.PRODUCER_SOURCES))
check("3 as are the modelling core, the frame adapter and the strict validator",
      {"cbs_v8.py", "cbs_generator.py", "cbs_real_frames_v3.py",
       "contract_validator_v4_strict.py"} <= set(rp.PRODUCER_SOURCES))
check("3 the digest is a 64-hex sha over the whole set", len(PDIG) == 64)
check("3 and is stable across calls on an unchanged tree",
      rp.require_clean_producer(ROOT, allow_dirty=True)["producer_source_set_digest"] == PDIG)

# the per-worker invariant: it recomputes rather than trusting what it was handed
_BR = rp.require_producer_bytes(ROOT, PDIG)
check("3 a worker verifies the producing bytes itself",
      _BR["ok"] is True and _BR["trusted_the_supplied_digest"] is False)
refuses("3 and REFUSES a digest that does not match the bytes on disk",
        lambda: rp.require_producer_bytes(ROOT, "0" * 64),
        contains="did not produce it", exc=rp.DirtyProducer)
check("3 tree cleanliness and producer-byte identity are separated on purpose",
      rp.require_clean_producer.__doc__ and "cannot be re-checked inside a worker"
      in rp.require_clean_producer.__doc__)


# ==========================================================================
print("\n4. lanes are disjoint, and set equality catches a stray or missing file")
# ==========================================================================
_L21, _L22 = set(rp.lane_files(2021)), set(rp.lane_files(2022))
check("4 two seasons' lanes share no filename", not (_L21 & _L22))
check("4 a lane holds four forecasts, a sidecar, a receipt, their manifests and a log",
      len(_L21) == 4 + 1 + 1 + 6 + 1, sorted(_L21))
check("4 every registered target has its own file in the lane",
      all(f"predictions__{t}__2021.parquet" in _L21 for t in rp.PLAYER_TARGETS))
check("4 the coordinator's files are not in any season lane",
      not (set(rp.COORDINATOR_FILES) & (_L21 | _L22)))

_LD = Path(tempfile.mkdtemp(prefix="cbs_lane_"))
for _n in rp.lane_files(2021):
    (_LD / _n).write_text("x", encoding="utf-8")
(_LD / "runtime_log__coordinator.jsonl").write_text("x", encoding="utf-8")
_ld = rp.require_lane_discipline(_LD, [2021])
check("4 a complete, tidy lane passes", _ld["ok"] is True, _ld)
(_LD / "predictions__p_active__2099.parquet").write_text("x", encoding="utf-8")
_ld2 = rp.require_lane_discipline(_LD, [2021])
check("4 a file written outside every lane is caught by set equality",
      _ld2["ok"] is False
      and "predictions__p_active__2099.parquet" in _ld2["files_written_outside_any_lane"])
_LD3 = Path(tempfile.mkdtemp(prefix="cbs_lane_gap_"))
for _n in rp.lane_files(2021):
    if "p_active" not in _n:
        (_LD3 / _n).write_text("x", encoding="utf-8")
_ld3 = rp.require_lane_discipline(_LD3, [2021])
check("4 and a missing EVIDENTIARY lane file is caught too",
      _ld3["ok"] is False and any("p_active" in n for n in _ld3["lane_files_absent"]))

# a runtime log is operational, not evidence: its absence must not refuse a receipted attempt
_LD4 = Path(tempfile.mkdtemp(prefix="cbs_lane_nolog_"))
for _n in rp.lane_required(2021):
    (_LD4 / _n).write_text("x", encoding="utf-8")
_ld4 = rp.require_lane_discipline(_LD4, [2021])
check("4 a missing runtime LOG does not refuse an otherwise complete lane",
      _ld4["ok"] is True and "runtime_log__2021.jsonl" in _ld4["optional_files_absent"],
      _ld4)
check("4 and the receipt says which files are operational rather than evidentiary",
      _ld4["optional_files_are"].startswith("runtime logs only"))
check("4 the required set is the evidentiary set: forecasts, sidecar, receipt, manifests",
      set(rp.lane_required(2021)) == set(rp.lane_files(2021)) - {"runtime_log__2021.jsonl"}
      and len(rp.lane_required(2021)) == 12)


# ==========================================================================
print("\n5. the target chain: four targets from ONE call, minutes held fixed")
# ==========================================================================
check("5 the four registered player targets are the fan-out's indivisible unit",
      sorted(rp.PLAYER_TARGETS) == sorted(
          ["p_active", "e_minutes_given_active", "attempts_usage",
           "player_scoring_distribution"]))
_ok_chain = rp.require_target_chain(
    {"selected": {"minutes_alpha": 0.3, "minutes_alpha_held_fixed_at": 0.3}},
    {t: pd.DataFrame() for t in rp.PLAYER_TARGETS})
check("5 a fitted fold whose minutes constant was held fixed passes",
      _ok_chain["ok"] is True and _ok_chain["fold_was_fitted"] is True)
_bad_chain = rp.require_target_chain(
    {"selected": {"minutes_alpha": 0.3, "minutes_alpha_held_fixed_at": 0.9}},
    {t: pd.DataFrame() for t in rp.PLAYER_TARGETS})
check("5 a fold whose rate targets re-selected minutes is REFUSED",
      _bad_chain["ok"] is False
      and any("held fixed" in p for p in _bad_chain["problems"]))
_short = rp.require_target_chain(
    {"selected": {}}, {t: pd.DataFrame() for t in list(rp.PLAYER_TARGETS)[:2]})
check("5 a fold missing targets is REFUSED, naming them",
      _short["ok"] is False and "attempts_usage" in str(_short["problems"]))
_cold = rp.require_target_chain({"selected": {}},
                                {t: pd.DataFrame() for t in rp.PLAYER_TARGETS})
check("5 a cold-start fold selects no constant, so the clause is vacuous and says so",
      _cold["ok"] is True and _cold["fold_was_fitted"] is False)
check("5 the receipt records WHY the fan-out unit is the fold and not the target",
      "four minutes constants where it has one"
      in _cold["why_the_fan_out_unit_is_the_fold"])


# ==========================================================================
print("\n6. a genuine, untouched fold validates, and every failure mode is named")
# ==========================================================================
TMP = Path(tempfile.mkdtemp(prefix="cbs_player_oof_"))
ATT = TMP / "attempt_001"
ATT.mkdir(parents=True)
BUILT = rf3.build_player_frame(SEASON, ROOT, require_attested=True)


def _log(msg, **kw):
    pass


FOLD = rp.run_fold(SEASON, ROOT, ATT, _log, PDIG)
check("6 the real 2021 player fold ran and wrote five artifacts",
      len(FOLD["written"]) == 5, FOLD["written"])
check("6 it is the cold start, so nothing was fitted",
      FOLD["model_was_fitted"] is False
      and FOLD["cold_start_declared_constant_only"] is True)
check("6 all four targets were emitted from the one call",
      sorted(FOLD["targets"]) == sorted(rp.PLAYER_TARGETS)
      and FOLD["target_chain"]["ok"] is True
      and FOLD["target_chain"]["n_targets_from_one_call"] == 4)
check("6 every target received a forecast for every obligation",
      set(FOLD["n_emitted_by_target"].values()) == {FOLD["n_test_rows"]},
      FOLD["n_emitted_by_target"])
check("6 the receipt names the three corrected v14 components",
      FOLD["obligation_order_id"] == "cbs_obligation_order/3"
      and FOLD["player_history_id"] == "cbs_player_history/14"
      and FOLD["player_runner_id"] == "cbs_player_runner/14")
check("6 the receipt records the producing source set digest",
      FOLD["producer_source_set_digest"] == PDIG)
check("6 and states the three scope claims explicitly",
      FOLD["own_outcome_never_informed_its_forecast"] is True
      and FOLD["forecast_scored_against_outcome"] is False
      and FOLD["evaluation_metric_calculated"] is False)
check("6 obligation completeness is labelled as such, not as coverage",
      "NOT statistical coverage" in FOLD["obligation_completeness_note"])
check("6 the fold wrote only files inside its own lane",
      set(FOLD["written"]) <= set(rp.lane_files(SEASON)))

_ok, _reasons, _rr = rp.validate_existing_fold(SEASON, ATT, ROOT, BUILT,
                                               expected_producer_digest=PDIG)
check("6 the untouched fold validates and is reusable", _ok is True, _reasons)
check("6 and the receipt lists what was actually checked", len(_rr["checked"]) >= 13)
check("6 including the strict validators re-run on the artifacts as READ BACK",
      any("read back" in c for c in _rr["checked"]))
check("6 all fourteen failure modes are enumerated",
      _rr["enumerated_failure_modes"] == list(rp.RESUME_FAILURES)
      and len(rp.RESUME_FAILURES) == 14)
check("6 the same routine serves resume and fan-in, so neither is trusted more cheaply",
      "both resume and fan-in" in _rr["applied_to"])


def damaged(fn, label, expect):
    """Copy the good attempt, damage the copy, and assert the validator names `expect`."""
    global PASSED
    d = Path(tempfile.mkdtemp(prefix="cbs_p_dmg_")) / "attempt_001"
    shutil.copytree(ATT, d)
    fn(d)
    ok_, reasons, _ = rp.validate_existing_fold(SEASON, d, ROOT, BUILT,
                                                expected_producer_digest=PDIG)
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


def _pred_path(d, target="p_active"):
    return d / f"predictions__{target}__{SEASON}.parquet"


damaged(lambda d: _receipt(d).unlink(),
        "6 a missing fold receipt", "receipt_absent")
damaged(lambda d: _receipt(d).write_text("not json", encoding="utf-8"),
        "6 an unreadable fold receipt", "receipt_unreadable")
damaged(lambda d: Path(str(_receipt(d)) + aso.MANIFEST_SUFFIX).unlink(),
        "6 a missing receipt manifest", "receipt_manifest_invalid")
damaged(lambda d: _pred_path(d).unlink(),
        "6 a missing prediction artifact", "artifact_absent")
damaged(lambda d: _pred_path(d).write_bytes(_pred_path(d).read_bytes() + b"\x00"),
        "6 a prediction artifact whose bytes no longer match its manifest",
        "artifact_hash_mismatch")
damaged(lambda d: Path(str(_pred_path(d)) + aso.MANIFEST_SUFFIX).unlink(),
        "6 a missing artifact manifest", "artifact_manifest_invalid")
damaged(lambda d: _edit_receipt(d, arm_id="contract_baseline_suite_v13"),
        "6 a receipt claiming the wrong arm", "wrong_arm")
damaged(lambda d: _edit_receipt(d, config_hash="c" * 64),
        "6 a receipt claiming the wrong config", "wrong_config")
damaged(lambda d: _edit_receipt(d, season=2099, fold_id="season:2099"),
        "6 a receipt claiming the wrong season", "wrong_season")
damaged(lambda d: _edit_receipt(d, producer_source_set_digest="e" * 64),
        "6 a receipt attributing the output to different producing bytes",
        "wrong_producer_digest")
damaged(lambda d: _edit_receipt(d, targets=["p_active"]),
        "6 a receipt claiming fewer than the four registered targets", "wrong_target_set")
damaged(lambda d: _edit_receipt(d, frames={**json.loads(
            _receipt(d).read_text(encoding="utf-8"))["frames"], "test": "f" * 64}),
        "6 a receipt whose frame digest no longer describes the rebuilt frame",
        "wrong_snapshot")
damaged(lambda d: _edit_receipt(d, artifacts={
            k: "0" * 64 for k in json.loads(
                _receipt(d).read_text(encoding="utf-8"))["artifacts"]}),
        "6 a receipt whose input artifact digests no longer match disk", "wrong_snapshot")
damaged(lambda d: _edit_receipt(d, provenance_sidecar_digest="d" * 64),
        "6 a sidecar digest that no longer recomputes", "sidecar_digest_mismatch")


def _substitute_predictions(d):
    """Replace the forecasts with different rows, keeping the manifest consistent."""
    p = _pred_path(d)
    df = pd.read_parquet(p)
    df["row_uid"] = "ob_substituted_" + df.index.astype(str)
    df.to_parquet(p, index=False)
    man = aso.read_manifest(p)
    aso.write_manifest(p, producer=man["producer"], fit_through_date=man["fit_through_date"],
                       fit_through_season=man["fit_through_season"],
                       fit_seasons=man["fit_seasons"], notes=man.get("notes", ""))


damaged(_substitute_predictions,
        "6 a SUBSTITUTED forecast file whose manifest was rewritten to match",
        "validator_rejected")


def _inject_outcome(d):
    """Smuggle the target's own outcome into an emitted forecast, manifest kept consistent."""
    p = _pred_path(d)
    df = pd.read_parquet(p)
    df["minutes"] = 0.0
    df.to_parquet(p, index=False)
    man = aso.read_manifest(p)
    aso.write_manifest(p, producer=man["producer"], fit_through_date=man["fit_through_date"],
                       fit_through_season=man["fit_through_season"],
                       fit_seasons=man["fit_seasons"], notes=man.get("notes", ""))


damaged(_inject_outcome,
        "6 a forecast carrying an outcome column, detected on the bytes as READ BACK",
        "validator_rejected")


# ==========================================================================
print("\n7. attempts are immutable; carry-forward copies and never overwrites")
# ==========================================================================
_base = Path(tempfile.mkdtemp(prefix="cbs_p_att_"))
_p1, _n1 = rp.resolve_attempt_dir(_base)
check("7 the first attempt is attempt_001", _n1 == "attempt_001")
_p1.mkdir()
_p2, _n2 = rp.resolve_attempt_dir(_base)
check("7 with one present, the resolver returns a NEW directory", _n2 == "attempt_002")
check("7 and never returns an existing one", _p2 != _p1 and not _p2.exists())
check("7 nothing in the runner deletes or truncates an artifact",
      not any(tok in SRC for tok in ("shutil.rmtree", ".unlink(", "os.remove")))

_CF = Path(tempfile.mkdtemp(prefix="cbs_p_cf_")) / "attempt_002"
_CF.mkdir(parents=True)
_cf = rp.carry_forward(ATT, _CF, SEASON)
check("7 carry-forward copies every file in the lane",
      _cf["ok"] and _cf["n_files_copied"] == len(FOLD["written"]) * 2 + 2,
      _cf["n_files_copied"])
check("7 the source attempt is left exactly as it was",
      _cf["source_left_untouched"] is True
      and rp.validate_existing_fold(SEASON, ATT, ROOT, BUILT,
                                    expected_producer_digest=PDIG)[0] is True)
_ok_cf, _r_cf, _ = rp.validate_existing_fold(SEASON, _CF, ROOT, BUILT,
                                             expected_producer_digest=PDIG)
check("7 and the copy revalidates in its NEW location, so the attempt is self-contained",
      _ok_cf is True, _r_cf)
refuses("7 carrying the same season forward twice REFUSES rather than overwriting",
        lambda: rp.carry_forward(ATT, _CF, SEASON),
        contains="refusing to overwrite", exc=rp.LaneViolation)


# ==========================================================================
print("\n8. the fan-in is receipt-checked, not exit-code-checked")
# ==========================================================================
_FI = rp.fan_in([SEASON], ROOT, ATT, PDIG, _log, frames={SEASON: BUILT})
check("8 a genuine attempt is accepted", _FI["ok"] is True and _FI["seasons_accepted"] == [SEASON],
      _FI["seasons_refused"])
check("8 the fan-in declares that it trusted no worker exit code",
      _FI["trusted_worker_exit_codes"] is False and _FI["revalidated_from_disk"] is True)
check("8 there is exactly one fan-in in the coordinator",
      SRC.count("fi = fan_in(") == 1 and SRC.count("def fan_in(") == 1)

_SUB = Path(tempfile.mkdtemp(prefix="cbs_p_sub_")) / "attempt_001"
shutil.copytree(ATT, _SUB)
_substitute_predictions(_SUB)
_FI2 = rp.fan_in([SEASON], ROOT, _SUB, PDIG, _log, frames={SEASON: BUILT})
check("8 and a substituted forecast is REFUSED even though the worker would have exited 0",
      _FI2["ok"] is False and SEASON in _FI2["seasons_refused"]
      and "validator_rejected" in _FI2["refusal_reasons"][str(SEASON)],
      _FI2["refusal_reasons"])
check("8 the fan-in also runs lane discipline over the directory as it is on disk",
      _FI["lane_discipline"]["checked_on"].startswith("the directory as it is on disk"))


# ==========================================================================
print("\n9. the scope claim is stated at its actual width, and nothing is scored")
# ==========================================================================
SC = rp.assert_no_scoring()
check("9 the AST scan declares its scope as this wrapper only",
      SC["scope"] == "THIS WRAPPER MODULE ONLY")
check("9 and says what it cannot establish",
      "imported callees" in SC["cannot_establish"]
      and "walk-forward feature" in SC["cannot_establish"])
check("9 the three claims are the narrow, defensible ones", SC["what_is_claimed"] == [
    "no target row's own outcome informed its forecast",
    "no forecast was scored against its outcome",
    "no evaluation metric was calculated"])
check("9 and the first names the mechanism that enforces it",
      "require_own_outcome_unavailable" in SC["first_claim_enforced_by"]
      and "availability < cutoff" in SC["first_claim_enforced_by"])
check("9 the receipt records that scoring is UNAUTHORIZED and escalated to the user",
      "UNAUTHORIZED" in SC["scoring_authorization_state"]
      and "escalated it to the user" in SC["scoring_authorization_state"])
check("9 and that coverage means obligation completeness",
      SC["coverage_means"].startswith("OBLIGATION COMPLETENESS"))
for _t in rp.PLAYER_TARGETS:
    _cols = set(pd.read_parquet(_pred_path(ATT, _t)).columns)
    check(f"9 the emitted {_t} forecast carries no outcome column",
          not (_cols & set(rp.OUTCOME_COLS)), sorted(_cols & set(rp.OUTCOME_COLS)))
check("9 the four target outcomes are all in the forbidden set",
      {"appeared", "minutes", "points", "fga"} <= set(rp.OUTCOME_COLS))
check("9 as are the universe's outcome-availability flags",
      all(f"outcome_scoreable__{t}" in rp.OUTCOME_COLS for t in rp.PLAYER_TARGETS))
check("9 the fold receipt computes no metric",
      not any(k in FOLD for k in ("accuracy", "auc", "log_loss", "brier", "profit", "roi")))
check("9 and no metric name appears anywhere in the persisted receipt",
      not any(k in json.dumps(FOLD).lower()
              for k in ("log_loss", "roc_auc", "brier", "profitability", "\"roi\"")))


# ==========================================================================
print("\n10. the producer gate is not fail-open under an inherited git environment")
# ==========================================================================
# Found by the pre-push hook, which runs this whole gate and therefore exports GIT_DIR into every
# suite. With GIT_DIR inherited, `git -C <other-repo> status --porcelain` returns the EMPTY STRING
# and `rev-parse HEAD` returns the HOOK's commit -- so a gate that swallowed git failures and read
# "" as "no dirty lines" would certify a tree it never measured, under a foreign commit.
check("10 the scrub list covers the variables git exports into hooks",
      {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"} <= set(rp._GIT_ENV_TO_SCRUB)
      and {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"} <= set(r2._GIT_ENV_TO_SCRUB))
check("10 the scrubbed env really removes them",
      not any(k in rp._git_env() for k in rp._GIT_ENV_TO_SCRUB))

# reproduce the exact conditions: point git at THIS repository while asking about the fixture.
# --absolute-git-dir is used rather than ROOT/".git" because in a worktree that path is a FILE.
_REAL_GITDIR = rp._git(ROOT, "rev-parse", "--absolute-git-dir")
check("10 the fixture's git dir was resolvable for the reproduction",
      bool(_REAL_GITDIR), _REAL_GITDIR)
_saved = {k: os.environ.get(k) for k in ("GIT_DIR", "GIT_WORK_TREE")}
os.environ["GIT_DIR"] = _REAL_GITDIR
try:
    _raw = subprocess.run(["git", "-C", str(_TG), "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    check("10 the raw, unscrubbed call is the one that lies -- it answers for the WRONG repo",
          _raw.returncode == 0 and _raw.stdout.strip() == rp._git(ROOT, "rev-parse", "HEAD"),
          f"unscrubbed rev-parse in the fixture returned {_raw.stdout.strip()[:12]!r}; "
          f"if this no longer reproduces, the environment changed")
    # both runners must still measure the FIXTURE, and so must still refuse it
    refuses("10 the player gate still refuses the dirty fixture despite GIT_DIR",
            lambda: rp.require_clean_producer(_TG),
            contains="not reconstructible", exc=rp.DirtyProducer)
    refuses("10 and the team gate does too",
            lambda: r2.require_clean_producer(_TG),
            contains="not reconstructible", exc=r2.DirtyProducer)
    _under_hook = rp.require_clean_producer(ROOT, allow_dirty=True)
    check("10 and this repository is still measured as ITSELF under GIT_DIR",
          Path(_under_hook["producer_checkout_path"]).resolve() == ROOT
          and _under_hook["n_dirty_paths"] == len(_dirty))
finally:
    for _k, _v in _saved.items():
        if _v is None:
            os.environ.pop(_k, None)
        else:
            os.environ[_k] = _v

# a root that is not a repository top level is refused rather than measured elsewhere
_NOTREPO = Path(tempfile.mkdtemp(prefix="cbs_notrepo_"))
for _rel in sorted(set(rp.PRODUCER_SOURCES) | set(r2.PRODUCER_SOURCES)):
    shutil.copy2(ROOT / _rel, _NOTREPO / _rel)
refuses("10 a --root that is not a git repository is REFUSED, not assumed clean",
        lambda: rp.require_clean_producer(_NOTREPO), exc=rp.DirtyProducer)
refuses("10 a subdirectory of a repository is REFUSED as not its top level",
        lambda: rp.require_clean_producer(ROOT / "tests"), exc=rp.DirtyProducer)
check("10 a failed git call is a refusal, not an empty string that reads as clean",
      "must not report it clean" in (rp._git_checked.__doc__ or "")
      or "must not report it clean" in SRC)
check("10 the receipt records the three guards",
      REC["git_toplevel_matched_root"] is True
      and REC["git_failure_is_a_refusal_not_a_clean_verdict"] is True
      and "GIT_DIR" in REC["inherited_git_env_scrubbed"])

print(f"\n    temporary fixtures left in place under {TMP.parent} (nothing deleted)")
print(f"    total runtime {time.time() - T_START:.0f}s")
print(f"\n{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAILED  {f}")
sys.exit(1 if FAILED else 0)
