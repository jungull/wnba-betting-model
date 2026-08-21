"""`cbs_player_runner/17` — `cbs_player_runner/16`, forked at ONE line, for the cold start.

WHY THIS FILE EXISTS
--------------------

`/14` emits the point forecast for a fallback row as::

    raw.where(lvl == 0, fb_mean)

Wherever the fallback ladder fires, the player's own centre is discarded and a single pooled
scalar is broadcast in its place. Measured on the E1_I0020 artifact across 1,061 cold-start
player-games: forecast standard deviation **0.012982** against an actual outcome spread of
**7.22**, and tier MAE **6.063956** on points against **4.2594** for the player's own prior mean.

The line sits one above the dispersion defect `/16` repairs. They are the same shape — a scalar
broadcast where a row-level quantity belongs — and they are repaired the same way.

D092 recommended the rule, D137 authorised it, D139 found the authorisation internally
inconsistent, and D164 resolved that in favour of the specified rule and built the arithmetic as
`cbs_player_coldstart/16`.

WHAT THIS SEAM IS, AND WHAT IT DELIBERATELY IS NOT
---------------------------------------------------

**It is not the full authorised rule, and must never be described as though it were.**

D092's rule shrinks the player's own mean toward a STRUCTURAL prior built from depth-chart rank
and draft slot. **Draft slot is not reachable from this path.** The runner's registered feature
sources are `src_asof_gamelog`, `src_asof_roster` and `src_asof_schedule`; bios is not among them,
and adding it is a contract change with its own provenance and registration consequences, not a
seam.

Substituting the league mean for the structural prior was measured and is WORSE than not blending
at all — tier MAE 4.7611 against 4.2594 — because the pooled mean is the very constant the repair
exists to escape. Shrinkage helps only toward something informative.

So this fork does the part that is reachable and honest: **it stops discarding the player's own
history on the rows where that history is the only information available.** Of the 1,061
cold-start rows, **990 carry at least one prior appearance**, and on those rows `raw` is finite by
construction — `player_fallback_level` assigns level 2 only when `n_prior >= 1` and the centre is
finite. Levels 1, 3 and 4 keep the pooled scalar exactly as before.

Measured worth, against the champion's own baseline:

===========================  ==================  ==================
target                       this fork           full authorised rule
===========================  ==================  ==================
points, tier MAE             4.2594              4.0325
points, pooled skill         +3.077%             +3.492%
minutes, tier MAE            5.4947              5.4487
minutes, pooled skill        +9.728%             +9.795%
===========================  ==================  ==================

From a champion baseline of −0.222% on points, that is **89% of the available gain on points and
99% on minutes**, for one line and no new registered input.

THE ONE SEAM
------------

Generated at import from `inspect.getsource` of `/16`'s forked source, with a single substitution
asserted to match exactly once, so the copy is exact by construction rather than by care — the
same discipline `/16` uses against `/14` and `/15` uses against `cbs_v14._run`.

WHAT DELIBERATELY DOES NOT MOVE
--------------------------------

The estimator, the standardizer, alpha and lambda selection, every mask, the tuning and
calibration split, the availability gate, the conditional history, the grouping rule,
`cbs_v5.dispersion`, `/16`'s per-row dispersion, the quantile offsets, `FittedState`, the
fallback LADDER itself and every receipt. `fb_mean` is still computed and is still what levels 1,
3 and 4 receive. Non-fallback rows are bit-identical.

STATUS
------

**AVAILABLE, NOT BOUND.** This file is not wired into any arm. Binding it changes what a
registered arm emits and therefore requires a new registration and a registered generation run.
Until that happens the production defect remains live. See D165.
"""
from __future__ import annotations

import difflib
import inspect

import cbs_player_coldstart_v16 as _cs
import cbs_player_runner_v14 as _v14
import cbs_player_runner_v16 as _v16

RUNNER_ID = "cbs_player_runner/17"
FORKED_FROM = "cbs_player_runner/16.run_player_fold_v16"
SUPERSEDES = "cbs_player_runner/16"

_SEAM_OLD = "            test, tgt, raw.where(lvl == 0, fb_mean),"
_SEAM_NEW = "            test, tgt, _cs.fold_point(raw, lvl, fb_mean),"
_SEAM_REASON = (
    "the cold-start point forecast: keep the player's own centre on short-history rows "
    "(level 2, one or two prior appearances) instead of broadcasting the pooled scalar. "
    "Levels 1, 3 and 4 are unchanged. D092/D137/D139/D164.")


class RunnerForkError(RuntimeError):
    """The inherited source is not what this fork was derived against."""


def _forked_source() -> str:
    src = _v16._SRC
    n = src.count(_SEAM_OLD)
    if n != 1:
        raise RunnerForkError(
            f"the seam line appears {n} times in {FORKED_FROM}, not once; /16 has changed and "
            f"this fork must be re-derived rather than silently re-applied.")
    return src.replace(_SEAM_OLD, _SEAM_NEW, 1).replace(
        "def run_player_fold_v16(", "def run_player_fold_v17(", 1)


_SRC = _forked_source()

#: `/16`'s namespace, plus the one new name this seam introduces. Every other name the forked
#: source reads — including `_disp`, `/16`'s own override — resolves to the SAME object `/16`
#: uses, which in turn resolves to `/14`'s.
_NS = dict(_v16._NS)
_NS["_cs"] = _cs
exec(compile(_SRC, f"<{RUNNER_ID} generated from {FORKED_FROM}>", "exec"), _NS)

run_player_fold = _NS["run_player_fold_v17"]


def source_diff() -> dict:
    a = _v16._SRC.splitlines()
    b = _SRC.splitlines()
    diff = [ln for ln in difflib.unified_diff(a, b, FORKED_FROM,
                                              f"{RUNNER_ID}.run_player_fold_v17",
                                              lineterm="", n=0)]
    changed = [ln for ln in diff if ln.startswith(("+", "-"))
               and not ln.startswith(("+++", "---"))]
    return {
        "runner": RUNNER_ID, "forked_from": FORKED_FROM,
        "generated_at_import_from_inspect_getsource": True,
        "n_permitted_seams": 1,
        "seam": {"old": _SEAM_OLD.strip(), "new": _SEAM_NEW.strip(), "reason": _SEAM_REASON},
        "namespace_overrides": ["_cs"],
        "n_changed_lines": len(changed),
        "n_changed_lines_expected": 4,
        "changed_lines": changed,
        "is_the_full_authorised_rule": False,
        "why_not": ("the authorised rule shrinks toward a structural prior built from "
                    "depth-chart rank and DRAFT SLOT; bios is not a registered feature source "
                    "on this path, and blending toward the pooled mean instead was measured "
                    "WORSE than not blending (4.7611 vs 4.2594)"),
        "unchanged": ("the estimator, the standardizer, alpha and lambda selection, every mask, "
                      "the tuning and calibration split, the availability gate, the conditional "
                      "history, the grouping rule, cbs_v5.dispersion, /16's per-row dispersion, "
                      "the quantile offsets, FittedState, the fallback ladder itself, and every "
                      "receipt. Non-fallback rows are bit-identical."),
    }


def assert_minimal_fork() -> dict:
    d = source_diff()
    if d["n_changed_lines"] != 4:
        raise RunnerForkError(
            f"the fork changes {d['n_changed_lines']} lines, not 4 (the def rename and the one "
            f"seam, each one removed and one added): {d['changed_lines']}")
    return d


def assert_inherits_dispersion_repair() -> bool:
    """`/17` must still carry `/16`'s repair; a fork that silently dropped it would be a
    regression wearing an improvement's name."""
    if "_disp.fold_sd" not in _SRC:
        raise RunnerForkError("/17 lost /16's per-row dispersion seam")
    return True


if __name__ == "__main__":
    import json
    assert_inherits_dispersion_repair()
    print(json.dumps(assert_minimal_fork(), indent=2))
