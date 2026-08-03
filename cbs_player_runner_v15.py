"""`cbs_player_runner/15` — `cbs_v14._run`, forked at ONE line.

WHICH LAYER THIS FORKS, AND WHY THE FIRST ATTEMPT WAS WRONG
------------------------------------------------------------
`cbs_v14` has two layers, and forking the wrong one silently loses the arm's whole receipt
discipline. The first version of this file forked `cbs_player_runner_v14.run_player_fold` — the
**inner modelling core** — and the real run refused, correctly, because that core returns
`cbs_source_provenance/1` and no `inherited_receipts`, and its `/1` cannot validate an empty
cold-start training frame.

`cbs_v14._run` is the arm. It calls the inner core in **synthetic** mode behind a legacy identity
shim, then restamps the identity, recomputes `source_provenance` at `/2` (which validates an empty
training frame for schema instead of skipping it), recomputes `provenance_history` at `/4`,
re-runs the strict prediction validator, and refuses on any receipt the inner core left
`inherited`. That layer is the one v15 must be.

So the inner runner is **not forked at all** — v15 uses `cbs_player_runner_v14.run_player_fold`
unchanged, exactly as v14 does, because its identity is synthetic and needs no rebinding.

THE ONE SEAM
------------
The outer `require_registered_identity` call, rebound to v15's registration. Nothing else. The
fork is generated at import from `inspect.getsource` and the substitution is asserted to match
exactly once, so the copy is exact by construction and cannot drift.

The function executes in `cbs_v14`'s own namespace plus two overrides — the identity function, and
`ARM_ID`, so `_restamp` stamps v15's arm id onto the emitted rows and the prediction validator
expects the same one. Every other name — `_player.run_player_fold`, `_restamp`,
`validate_provenance_sidecar`, `coverage_receipt`, `exclusion_receipt`, `build_legacy_identity_shim`,
`resolve_and_receipt_fold_sources` — resolves to the **same object** v14 uses.
"""

from __future__ import annotations

import difflib
import inspect

import cbs_v14 as _v14
import cbs_v15 as _v15

RUNNER_ID = "cbs_player_runner/15"
FORKED_FROM = "cbs_v14._run"
INHERITS_FROM = _v14.ARM_ID
INNER_CORE_UNFORKED = "cbs_player_runner_v14.run_player_fold"

_SEAM_OLD = "    identity = require_registered_identity("
_SEAM_NEW = "    identity = require_registered_identity_v15("
_SEAM_REASON = "contract identity: bind to the v15 registration instead of v14's"


class RunnerForkError(RuntimeError):
    """The fork could not be derived from the inherited source."""


def _forked_source() -> str:
    src = inspect.getsource(_v14._run)
    n = src.count(_SEAM_OLD)
    if n != 1:
        raise RunnerForkError(
            f"the identity seam matched {n} times in {FORKED_FROM}; it must match exactly once. "
            f"v14 has changed and this fork must be re-derived rather than silently re-applied.")
    return src.replace(_SEAM_OLD, _SEAM_NEW, 1).replace("def _run(", "def _run_v15(", 1)


_SRC = _forked_source()

#: v14's namespace, plus exactly two overrides. `ARM_ID` is overridden because `_restamp` and the
#: prediction validator both read it: without it the rows would be stamped `contract_baseline_suite_v14`
#: and then validated against v15, or worse, stamped v14 and accepted.
def _restamp_v15(frame, *, config_hash: str, snapshot_hash: str):
    """`cbs_v14._restamp`, clause for clause, stamping v15's arm id.

    Overriding `ARM_ID` in the copied namespace is NOT enough and the first attempt proved it:
    `_restamp` is a module-level function whose OWN globals are `cbs_v14`'s, so it kept writing
    `contract_baseline_suite_v14` onto every emitted row while the validator — which reads
    `ARM_ID` from the forked function's own namespace — expected v15. The rows carried one arm's
    id and were checked against another's. A namespace override only reaches names the forked
    source reads DIRECTLY; anything it calls keeps its own globals.
    """
    out = frame.copy()
    out["arm_id"] = _v15.ARM_ID
    out["config_hash"] = config_hash
    out["data_snapshot_hash"] = snapshot_hash
    return out


_NS = dict(_v14.__dict__)
_NS["require_registered_identity_v15"] = _v15.require_registered_identity_v15
_NS["ARM_ID"] = _v15.ARM_ID
#: `cbs_v14.validate_provenance_sidecar` checks that the sidecar and every emitted prediction
#: carry `ARM_ID` — read from ITS OWN globals, with no parameter to override. Under v15 the rows
#: correctly say `cbs_v15_player_oof_v5` and v14's validator correctly objects that they are not
#: v14's. Both are right; the validator is simply bound to the wrong arm.
#:
#: So it is re-executed, VERBATIM, in a namespace whose `ARM_ID` is v15's. Zero source changes —
#: `assert_no_source_change` proves it — because the defect was never in the logic. This is the
#: same lesson `_restamp` taught: a namespace override reaches only what the forked source reads
#: directly, so every callee that reads `ARM_ID` needs the same treatment.
_PROV_SRC = inspect.getsource(_v14.validate_provenance_sidecar)
_PROV_NS = dict(_v14.__dict__)
_PROV_NS["ARM_ID"] = _v15.ARM_ID
exec(compile(_PROV_SRC, f"<{RUNNER_ID}: cbs_v14.validate_provenance_sidecar rebound to v15>",
             "exec"), _PROV_NS)
_validate_provenance_sidecar_rebound = _PROV_NS["validate_provenance_sidecar"]


def assert_no_source_change() -> dict:
    """The rebound validator is byte-identical to v14's; only its ARM_ID binding differs."""
    live = inspect.getsource(_v14.validate_provenance_sidecar)
    if live != _PROV_SRC:
        raise RunnerForkError("cbs_v14.validate_provenance_sidecar changed after it was rebound")
    return {"rebound": "cbs_v14.validate_provenance_sidecar",
            "source_changes": 0, "namespace_overrides": ["ARM_ID"],
            "why": ("the validator checks arm_id against ARM_ID read from its own globals and "
                    "takes no parameter for it; the logic is correct and is not touched")}


def _validate_provenance_sidecar_v15(*a, **kw):
    """The rebound validator, stamped as recomputed BY THIS ARM."""
    out = _validate_provenance_sidecar_rebound(*a, **kw)
    return dict(out, recomputed_by=_v15.ARM_ID)


_NS["_restamp"] = _restamp_v15
_NS["validate_provenance_sidecar"] = _validate_provenance_sidecar_v15
exec(compile(_SRC, f"<{RUNNER_ID} generated from {FORKED_FROM}>", "exec"), _NS)

_run_v15 = _NS["_run_v15"]


def run_player_fold(train, test, fold_id, **kw) -> dict:
    """All four player targets over the v5 universe, with v14's estimator unchanged."""
    return _run_v15("player", train, test, fold_id, **kw)


def source_diff() -> dict:
    a = inspect.getsource(_v14._run).splitlines()
    b = _SRC.splitlines()
    diff = [ln for ln in difflib.unified_diff(a, b, FORKED_FROM, f"{RUNNER_ID}._run_v15",
                                              lineterm="", n=0)]
    changed = [ln for ln in diff if ln.startswith(("+", "-"))
               and not ln.startswith(("+++", "---"))]
    return {
        "runner": RUNNER_ID, "forked_from": FORKED_FROM,
        "inner_core_unforked": INNER_CORE_UNFORKED,
        "why_this_layer": ("cbs_v14._run is the ARM: it calls the inner core in synthetic mode "
                           "behind a legacy identity shim, restamps identity, recomputes "
                           "source_provenance at /2 and provenance_history at /4, re-runs the "
                           "strict prediction validator, and refuses on any inherited receipt. "
                           "Forking the inner core instead loses all of that."),
        "generated_at_import_from_inspect_getsource": True,
        "n_permitted_seams": 1,
        "seam": {"old": _SEAM_OLD.strip(), "new": _SEAM_NEW.strip(), "reason": _SEAM_REASON},
        "namespace_overrides": ["require_registered_identity_v15", "ARM_ID", "_restamp",
                                "validate_provenance_sidecar"],
        "why_arm_id_is_overridden": ("_restamp writes ARM_ID onto every emitted row and the "
                                     "prediction validator checks it; both must say v15. "
                                     "_restamp itself must ALSO be overridden: a namespace "
                                     "override only reaches names the forked source reads "
                                     "directly, and _restamp keeps cbs_v14's own globals."),
        "n_changed_lines": len(changed),
        "n_changed_lines_expected": 4,
        "changed_lines": changed,
        "unchanged": ("every estimator, standardizer, mask, tuning rule, lambda and alpha "
                      "selection, calibration, dispersion, availability gate, conditional "
                      "history and grouping rule — none is inside the diff, and the modelling "
                      "core is not forked at all"),
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
