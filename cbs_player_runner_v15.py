"""`cbs_player_runner/15` — `cbs_player_runner/14`, forked at ONE line.

The permitted diff against `cbs_player_runner_v14.run_player_fold` is **exactly one line**: the
identity-binding call, rebound from v14's registration to v15's. **No estimator, standardizer,
mask, tuning rule, lambda or alpha selection, calibration, dispersion, availability gate,
conditional history or grouping rule differs**, because none of them is inside the diff.

The fork is **generated at import time from `inspect.getsource`** and one textual substitution
asserted to match exactly once, so the copy is exact by construction and cannot drift. If `/14`
changes, either the substitution still applies to the new source or import fails loudly.

The function then executes in `cbs_player_runner_v14`'s own module namespace plus a single
override, so every name it does not redefine — `logistic_fit`, `Standardizer`, `player_split`,
`select_alpha_bound`, `select_lambda_chronological`, `walk_forward_ewma`, `conditional_center`,
`stage_a_features_v8`, `_emit`, `_finish`, `_provenance_rows`, `player_fallback_level`,
`dispersion`, `residuals`, `DECLARED`, `QUANTILE_Z` — resolves to the **same object** `/14` uses.

`source_diff()` returns the exact unified diff for a reviewer, and
`tests/test_cbs_v15.py` asserts it is one changed line.
"""

from __future__ import annotations

import difflib
import inspect

import cbs_player_runner_v14 as _v14runner
import cbs_v15 as _v15

RUNNER_ID = "cbs_player_runner/15"
FORKED_FROM = "cbs_player_runner_v14.run_player_fold"
SUPERSEDES = None
INHERITS_FROM = _v14runner.RUNNER_ID

#: The one permitted seam, and the only authorised reason for it.
_SEAM_OLD = "    identity = require_registered_identity("
_SEAM_NEW = "    identity = require_registered_identity_v15("
_SEAM_REASON = "contract identity: bind to cbs_v15_player_oof_v5/2 instead of v14's registration"


class RunnerForkError(RuntimeError):
    """The fork could not be derived from the inherited source."""


def _forked_source() -> str:
    src = inspect.getsource(_v14runner.run_player_fold)
    n = src.count(_SEAM_OLD)
    if n != 1:
        raise RunnerForkError(
            f"the identity seam matched {n} times in {FORKED_FROM}; it must match exactly once. "
            f"`/14` has changed and this fork must be re-derived rather than silently re-applied.")
    return src.replace(_SEAM_OLD, _SEAM_NEW, 1)


_SRC = _forked_source()

_NS = dict(_v14runner.__dict__)
_NS["require_registered_identity_v15"] = _v15.require_registered_identity_v15
exec(compile(_SRC, f"<{RUNNER_ID} generated from {FORKED_FROM}>", "exec"), _NS)

#: The fitted core. Same name, same signature, same body but for the one bound line.
run_player_fold = _NS["run_player_fold"]


def source_diff() -> dict:
    """The exact diff against the LIVE `/14` source, for review."""
    a = inspect.getsource(_v14runner.run_player_fold).splitlines()
    b = _SRC.splitlines()
    diff = [ln for ln in difflib.unified_diff(a, b, FORKED_FROM, f"{RUNNER_ID}.run_player_fold",
                                              lineterm="", n=0)]
    changed = [ln for ln in diff if ln.startswith(("+", "-"))
               and not ln.startswith(("+++", "---"))]
    return {
        "runner": RUNNER_ID, "forked_from": FORKED_FROM,
        "generated_at_import_from_inspect_getsource": True,
        "n_permitted_seams": 1,
        "seam": {"old": _SEAM_OLD.strip(), "new": _SEAM_NEW.strip(), "reason": _SEAM_REASON},
        "n_changed_lines": len(changed),
        "n_changed_lines_expected": 2,
        "changed_lines": changed,
        "unchanged": ("every estimator, standardizer, mask, tuning rule, lambda and alpha "
                      "selection, calibration, dispersion, availability gate, conditional "
                      "history and grouping rule — none is inside the diff"),
        "name_resolution": ("executes in cbs_player_runner_v14's namespace, so every name it "
                            "does not redefine is the SAME OBJECT /14 uses"),
    }


def assert_minimal_fork() -> dict:
    d = source_diff()
    if d["n_changed_lines"] != 2:
        raise RunnerForkError(
            f"the fork changes {d['n_changed_lines']} lines, not 2 (one removed, one added): "
            f"{d['changed_lines']}")
    return d


if __name__ == "__main__":
    import json
    print(json.dumps(assert_minimal_fork(), indent=2))
