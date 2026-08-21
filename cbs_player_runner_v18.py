"""`cbs_player_runner/18` — `/15`'s arm, with `/17`'s core underneath it.

WHY THIS FILE EXISTS
--------------------

The cold-start repair lives in the inner modelling core (`/17`, which is `/16` forked at the
point line, which is `/14` forked at the dispersion line). The live arm is `/15`, which forks
`cbs_v14._run` — the ARM layer — and calls the inner core by name. Binding the repair therefore
means changing WHICH CORE THE ARM CALLS, and nothing else.

`0108ef86` established why the arm layer is the right place to fork and the core is the wrong
place: `_run` restamps identity, recomputes source provenance at `/2` and provenance history at
`/4`, re-runs the strict prediction validator and refuses on inherited receipts. Forking the core
loses all of that. So this file does not fork anything new. It re-executes **`/15`'s own generated
source, byte for byte**, in a namespace where one name is rebound.

THE ONE REBINDING
-----------------

    _player  ->  a shim over `cbs_player_runner_v14` whose `run_player_fold` is `/17`'s

`_player` is the name `cbs_v14._run` reads to reach the inner core. Every other attribute the
shim might be asked for delegates to `cbs_player_runner_v14` unchanged, so a name this arm has
never needed cannot silently resolve to something new.

This is the same lesson `/15` recorded twice and paid for once: **a namespace override reaches
only the names the forked source reads directly.** `_run` reads `_player` directly, so overriding
it is sufficient and is the whole change.

WHAT THIS INHERITS AND DOES NOT TOUCH
--------------------------------------

* `/15`'s arm source, unchanged — the identity seam, the restamping, the provenance
  recomputation, the validator re-run, the refusal on inherited receipts.
* `/15`'s three ARM_ID rebindings (`ARM_ID`, `_restamp`, `validate_provenance_sidecar`), which
  are verbatim re-executions of `cbs_v14`'s own functions in a namespace where `ARM_ID` is v15's.
* `/16`'s per-row dispersion repair, carried through `/17`.
* `/14`'s estimator, standardizer, alpha and lambda selection, masks, tuning and calibration
  split, availability gate, conditional history, grouping rule and every receipt.

WHAT CHANGES IN THE EMITTED OUTPUT
-----------------------------------

Only the point forecast on fallback level 2 — one or two prior appearances. Levels 0, 1, 3 and 4
are bit-identical. Measured on the E1_I0020 artifact: points tier MAE 6.063956 -> 4.2594, pooled
skill -0.222% -> +3.077%; minutes 9.748011 -> 5.4947, +3.555% -> +9.728%.

**This is 89% of D092's authorised rule on points and 99% on minutes, not the whole of it.** The
authorised rule shrinks toward a structural prior built from depth-chart rank and DRAFT SLOT, and
bios is not a registered feature source on this path. Substituting the pooled mean was measured
WORSE than not blending (4.7611 against 4.2594). D165 records the ladder; the user chose this
rung explicitly.
"""
from __future__ import annotations

import cbs_player_runner_v14 as _core14
import cbs_player_runner_v15 as _v15runner
import cbs_player_runner_v17 as _v17

RUNNER_ID = "cbs_player_runner/18"
FORKED_FROM = "cbs_player_runner/15"
ARM_SOURCE_UNCHANGED = True
CORE = "cbs_player_runner/17"
SUPERSEDES = "cbs_player_runner/15"


class RunnerBindError(RuntimeError):
    """The inherited arm source or core is not what this binding was derived against."""


class _CoreShim:
    """`cbs_player_runner_v14`, except that `run_player_fold` is `/17`'s.

    Attribute access delegates, so a name this arm has never needed cannot resolve to something
    new behind our backs. Only the one entry point is replaced.
    """

    run_player_fold = staticmethod(_v17.run_player_fold)

    def __getattr__(self, name):
        return getattr(_core14, name)

    def __repr__(self):
        return f"<{RUNNER_ID} core shim: {_core14.__name__} with run_player_fold from {CORE}>"


_CORE_SHIM = _CoreShim()

#: `/15`'s namespace, with the one rebinding. `/15`'s own overrides ride along untouched.
_NS = dict(_v15runner._NS)
if "_player" not in _NS:
    raise RunnerBindError(
        "cbs_player_runner/15's namespace has no `_player`; the arm no longer reaches its core "
        "by that name and this binding must be re-derived rather than silently re-applied.")
_NS["_player"] = _CORE_SHIM

#: `/15`'s generated arm source, byte for byte, with only the def renamed.
_SRC = _v15runner._SRC.replace("def _run_v15(", "def _run_v18(", 1)
if _SRC == _v15runner._SRC:
    raise RunnerBindError("could not rename /15's generated arm function; its shape has changed")

exec(compile(_SRC, f"<{RUNNER_ID}: {FORKED_FROM}'s arm bound to {CORE}>", "exec"), _NS)

_run = _NS["_run_v18"]


def run_player_fold(*a, **kw):
    """The arm, unchanged, over the cold-start-repaired core."""
    return _run("player", *a, **kw)


def binding_receipt() -> dict:
    return {
        "runner": RUNNER_ID,
        "forked_from": FORKED_FROM,
        "arm_source_changes": 0,
        "arm_source_identical_to_v15_but_for_the_def_name": True,
        "core": CORE,
        "core_chain": [CORE, "cbs_player_runner/16", "cbs_player_runner/14.run_player_fold"],
        "namespace_rebindings": ["_player"],
        "inherits_from_v15": ["ARM_ID", "_restamp", "validate_provenance_sidecar",
                              "require_registered_identity_v15"],
        "changes_in_emitted_output": ("the point forecast on fallback level 2 only; levels 0, 1, "
                                      "3 and 4 are bit-identical"),
        "is_the_full_authorised_rule": False,
        "why_not": ("D092's rule shrinks toward a structural prior built from depth-chart rank "
                    "and DRAFT SLOT; bios is not a registered feature source on this path, and "
                    "substituting the pooled mean was measured worse than not blending "
                    "(4.7611 vs 4.2594). The user selected this rung in D167."),
    }


def assert_arm_source_unchanged() -> bool:
    """`/18` must be `/15`'s arm with a different core, not a different arm."""
    a = _v15runner._SRC.replace("def _run_v15(", "def _run_v18(", 1)
    if a != _SRC:
        raise RunnerBindError("/18's arm source is not /15's")
    return True


def assert_core_is_v17() -> bool:
    if _NS["_player"].run_player_fold is not _v17.run_player_fold:
        raise RunnerBindError("/18 is not reaching /17's core")
    if getattr(_NS["_player"], "REQUIRED_PLAYER_FEATURE_SOURCES", None) is not \
            _core14.REQUIRED_PLAYER_FEATURE_SOURCES:
        raise RunnerBindError("the core shim stopped delegating to /14")
    return True


if __name__ == "__main__":
    import json
    assert_arm_source_unchanged()
    assert_core_is_v17()
    print(json.dumps(binding_receipt(), indent=2))
