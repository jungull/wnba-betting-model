"""`cbs_player_runner/16` — `cbs_player_runner_v14.run_player_fold`, forked at ONE line.

WHY THIS FILE EXISTS, AND WHY IT IS NOT AN EDIT TO `/14`
--------------------------------------------------------

D136 established on bytes that the shipped per-row uncertainty is a per-season constant, and D137
authorised repairing it. The defect is one line of `/14`::

    pd.Series(sd_v, index=test.index)

`cbs_v5.dispersion` returns a scalar and the runner broadcasts it across every test row, so every
emitted `pred_sd` — and the `q50`/`q75` offsets with it — carries zero row-level information.

The repair is a NEW RUNNER rather than an edit to `/14` for two independent reasons, either of
which alone would be sufficient:

* **`/14` is diff-locked.** `tests/test_cbs_v14.py` section 8 re-derives `/14`'s diff against the
  live `cbs_v8.run_player_fold` at test time, asserts an identical LINE COUNT, and fails on any
  line differing outside `PERMITTED_DIFF_LINES = (25, 26, 39)`. That check is in the repository
  gate. An in-place repair breaks it by construction.
* **`/14` is a shipped arm's estimator.** `contract_baseline_suite_v14` ran through it, and the
  v14 control receipt and the v14/v15 scoring comparison quote numbers produced by it. Repairing
  it in place would move published figures of an arm that is not being repaired — the exact
  failure mode this programme records as a defect.

So `/14` is left alone, byte for byte, and `/16` is generated FROM it.

THE ONE SEAM
------------

Generated at import from `inspect.getsource(cbs_player_runner_v14.run_player_fold)`, with a single
substitution asserted to match exactly once, so the copy is exact by construction rather than by
care — the same discipline `cbs_player_runner_v15` uses against `cbs_v14._run`::

    -            pd.Series(sd_v, index=test.index), off, fold_id=fold_id,
    +            _disp.fold_sd(sd_v, plan_all, combined, act_all, tgt, ycol, ...), off, ...

Every argument in the replacement is a name already bound at that point in the inherited source.
Nothing else moves: the estimator, the standardizer, the lambda and alpha selection, the masks,
the calibration pool, `cbs_v5.dispersion` itself, the quantile offsets, the availability gate, the
conditional history, the grouping rule, `FittedState` and every receipt are the inherited objects,
reached through `/14`'s own module namespace.

WHAT DELIBERATELY DOES NOT MOVE
--------------------------------

`sd_v` — the scalar `cbs_v5.dispersion` returned — is still what `FittedState.dispersion_sd` and
`diag["dispersion"][tgt]["sd"]` record, and still what `off` (the additive quantile offsets) was
built from. It is the ANCHOR the per-row multiplier is centred on, so recording it is accurate,
not stale. The repair re-allocates the fold's dispersion across rows; it does not re-estimate it.

Consequently the `q05`/`q25`/`q50`/`q75`/`q95` OFFSETS are still fold-level. Making the offsets
per-row as well is a larger change than D137 authorised and is not attempted here.

NOT YET BOUND TO A LIVE ARM
----------------------------

`cbs_player_runner_v15.py` — the live inner-core binding — is byte-locked by
`experiments/player_program/arm_registry.jsonl` through `cbs_v15.verify_implementation_bytes`.
Pointing the live arm at this runner therefore requires an arm-registry revision, which is the
coordinator's write scope, not this change's. This module is the repair, tested and measured;
binding it is a separate, deliberate act.
"""

from __future__ import annotations

import difflib
import inspect

import cbs_player_dispersion_v16 as _disp
import cbs_player_runner_v14 as _v14

RUNNER_ID = "cbs_player_runner/16"
FORKED_FROM = "cbs_player_runner_v14.run_player_fold"
INHERITS_ESTIMATOR_FROM = _v14.RUNNER_ID

_SEAM_OLD = "            pd.Series(sd_v, index=test.index), off, fold_id=fold_id,"
_SEAM_NEW = ("            _disp.fold_sd(sd_v, plan_all, combined, act_all, tgt, ycol, "
             "minutes_alpha=m_alpha, rate_alpha=alpha, n_prior=n_prior, train=train, "
             "test=test), off, fold_id=fold_id,")
_SEAM_REASON = ("per-row dispersion: replace the per-season constant broadcast with "
                "cbs_player_dispersion/16, conditioned on strictly pre-game state (D136/D137)")


class RunnerForkError(RuntimeError):
    """The fork could not be derived from the inherited source."""


def _forked_source() -> str:
    src = inspect.getsource(_v14.run_player_fold)
    n = src.count(_SEAM_OLD)
    if n != 1:
        raise RunnerForkError(
            f"the dispersion seam matched {n} times in {FORKED_FROM}; it must match exactly once. "
            f"/14 has changed and this fork must be re-derived rather than silently re-applied.")
    return src.replace(_SEAM_OLD, _SEAM_NEW, 1).replace(
        "def run_player_fold(", "def run_player_fold_v16(", 1)


_SRC = _forked_source()

#: `/14`'s own namespace, plus the one new name the seam introduces. Every other name the forked
#: source reads — `dispersion`, `residuals`, `_emit`, `FittedState`, `conditional_center`,
#: `player_fallback_level`, `_history`, `_order` — resolves to the SAME object `/14` uses.
_NS = dict(_v14.__dict__)
_NS["_disp"] = _disp
exec(compile(_SRC, f"<{RUNNER_ID} generated from {FORKED_FROM}>", "exec"), _NS)

run_player_fold = _NS["run_player_fold_v16"]


def source_diff() -> dict:
    a = inspect.getsource(_v14.run_player_fold).splitlines()
    b = _SRC.splitlines()
    diff = [ln for ln in difflib.unified_diff(a, b, FORKED_FROM,
                                              f"{RUNNER_ID}.run_player_fold_v16",
                                              lineterm="", n=0)]
    changed = [ln for ln in diff if ln.startswith(("+", "-"))
               and not ln.startswith(("+++", "---"))]
    return {
        "runner": RUNNER_ID, "forked_from": FORKED_FROM,
        "generated_at_import_from_inspect_getsource": True,
        "n_permitted_seams": 1,
        "seam": {"old": _SEAM_OLD.strip(), "new": _SEAM_NEW.strip(), "reason": _SEAM_REASON},
        "namespace_overrides": ["_disp"],
        "n_changed_lines": len(changed),
        "n_changed_lines_expected": 4,
        "changed_lines": changed,
        "unchanged": ("cbs_v5.dispersion itself, the scalar it returns, the quantile offsets "
                      "built from it, the estimator, the standardizer, every mask, the tuning "
                      "and calibration split, the availability gate, the conditional history and "
                      "the grouping rule"),
    }


def assert_minimal_fork() -> dict:
    d = source_diff()
    if d["n_changed_lines"] != 4:
        raise RunnerForkError(
            f"the fork changes {d['n_changed_lines']} lines, not 4 (the def rename and the one "
            f"seam, each one removed and one added): {d['changed_lines']}")
    return d


if __name__ == "__main__":
    import json
    print(json.dumps(assert_minimal_fork(), indent=2))
